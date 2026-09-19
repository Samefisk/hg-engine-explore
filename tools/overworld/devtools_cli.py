"""HTTP client for the Workshop's shared, local development session.

This module never imports an emulator or changes a ROM/save. Both this client
and the browser use the same command endpoint and server-side validation.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


DEFAULT_URL = "http://127.0.0.1:8766"


def summarize_response(response: dict[str, Any]) -> dict[str, Any]:
    """A lossy display projection only; never change the request or its verdict."""
    omitted = {}
    actor_detail = {
        "version", "size", "roleId", "laneId", "motionKindId", "motionPhaseId",
        "engineObject", "engineIdentity", "sourceIdentity", "presentationState",
        "controllerState", "lastCommandSequence",
    }

    def note(path, *, fields=(), count=None):
        # One wildcard entry for a repeated structure, not one list per actor.
        entry = omitted.setdefault(path, {})
        if fields:
            entry["fields"] = sorted(set(entry.get("fields", ())) | set(fields))
        if count is not None:
            entry["count"] = entry.get("count", 0) + count

    def project_identity(value, path):
        identity = dict(value)
        for key in ("rom", "save", "debugDescriptor"):
            source = identity.get(key)
            if isinstance(source, dict):
                removed = set(source) & {"copy", "size"}
                identity[key] = {k: v for k, v in source.items() if k not in removed}
                if removed:
                    note(path + "." + key, fields=removed)
        if isinstance(identity.get("toolInputs"), list):
            inputs = identity.pop("toolInputs")
            identity["toolInputCount"] = len(inputs)
            note(path + ".toolInputs", count=len(inputs))
        return identity

    def project_preflight(value, path):
        # Typed job preflight and early attempt identity share source records.
        # Keep verdicts, registration and artifacts, not each successful output.
        result = dict(value)
        source = result.get("source")
        if isinstance(source, dict) and isinstance(source.get("roots"), dict):
            result["source"] = {k: v for k, v in source.items() if k != "roots"}
            result["source"]["rootCount"] = len(source["roots"])
            note(path + ".source.roots", count=len(source["roots"]))
        fixture = result.get("fixture")
        if isinstance(fixture, dict) and isinstance(fixture.get("checks"), list):
            checks = fixture["checks"]
            passing = [check for check in checks if isinstance(check, dict) and check.get("passed") is True]
            result["fixture"] = {**fixture, "checks": {
                "reportedCount": len(checks), "passingCount": len(passing),
                "passingNames": [check.get("name") for check in passing],
                # Retain exact non-passing entries, including unexpected types.
                "nonPassing": [check for check in checks if not isinstance(check, dict) or check.get("passed") is not True],
                "scope": "reported preflight checks only; omitted details are not proof",
            }}
            if passing:
                note(path + ".fixture.checks", count=len(passing))
        return result

    def project_session(value):
        if not isinstance(value, dict):
            return value
        result = dict(value)
        for key in ("directory",):
            if key in result:
                del result[key]
                note("session", fields=[key])
        identity = value.get("identity")
        if isinstance(identity, dict):
            identity = project_identity(identity, "session.identity")
            for key, session_key in (("sessionId", "id"), ("startedAt", "startedAt")):
                if key in identity and session_key in value and identity[key] == value[session_key]:
                    del identity[key]
                    note("session.identity", fields=[key])
            result["identity"] = identity
        if isinstance(result.get("setupMutations"), list):
            mutations = result.pop("setupMutations")
            # Counts refer only to this response's retained list, not history.
            result["retainedSetupMutationCount"] = len(mutations)
            note("session.setupMutations", count=len(mutations))
        if "lastError" in result:
            result["lastError"] = project_error(result["lastError"], "session.lastError")
        return result

    def project_error(value, path):
        # Cached status errors may repeat a whole snapshot. Direct command
        # errors below remain exact, including their receipt and details.
        if not isinstance(value, dict) or "details" not in value:
            return value
        note(path, fields=["details"])
        return {**{k: v for k, v in value.items() if k != "details"}, "detailsOmitted": True}

    def project(value, path, *, job=False):
        if isinstance(value, list):
            return [project(item, path + "[*]", job=job) for item in value]
        if not isinstance(value, dict):
            return value
        typed_job = value.get("execution") == "shared-devtools" and isinstance(value.get("runId"), str)
        job = job or typed_job
        result = {}
        for key, item in value.items():
            child = f"{path}.{key}"
            if typed_job and key == "identity" and isinstance(item, dict):
                result[key] = project_identity(item, child)
            elif typed_job and key in {"fixtureProof", "attemptIdentity", "proofAcceptance"} and isinstance(item, dict):
                result[key] = project_preflight(item, child)
            elif job and key == "measurements" and isinstance(item, dict):
                # Live status needs the current counters and exact failures,
                # not every earlier lane/chain packet on each poll. The full
                # manifest and unsummarized response retain the proof data.
                result[key] = {}
                for name, measurement in item.items():
                    if not isinstance(measurement, dict):
                        result[key][name] = measurement
                        continue
                    history = {field: len(measurement[field]) for field in
                        ("intervals", "actions", "interruptedIntervals")
                        if isinstance(measurement.get(field), list)}
                    removed = set(history) | ({"selectedProfileReceipt"}
                        if "selectedProfileReceipt" in measurement else set())
                    projected = {field: value for field, value in measurement.items() if field not in removed}
                    if removed:
                        note(child + "." + name, fields=removed)
                        projected["historyCounts"] = history
                    result[key][name] = project(projected, child + "." + name, job=True)
            elif job and key in {"error", "commandError", "failures"}:
                result[key] = item  # Failed job evidence is never truncated.
            elif (key == "resolvedProfiles" and isinstance(item, list)
                  and path.endswith("nativeObservation")):
                profiles = []
                fingerprints = []
                for profile in item:
                    if not isinstance(profile, dict):
                        profiles.append(profile)
                        fingerprints.append(None)
                        continue
                    removed = set(profile) & {"lanes", "resultHex", "requestHex"}
                    if removed:
                        note(child + "[*]", fields=removed)
                    compact = {name: value for name, value in profile.items() if name not in removed}
                    profiles.append(project(compact, child + "[*]", job=job))
                    fingerprints.append(profile.get("fingerprint"))
                result[key] = {
                    "reportedCount": len(item),
                    "fingerprints": fingerprints,
                    "profiles": profiles,
                    "scope": "retained resolver profiles; omit --summary for raw profile bytes",
                }
            elif key == "actors" and isinstance(item, list):
                actors = []
                for actor in item:
                    if not isinstance(actor, dict):
                        actors.append(actor)
                        continue
                    removed = sorted(set(actor) & actor_detail)
                    if removed:
                        note(child + "[*]", fields=removed)
                    projected = {k: v for k, v in actor.items() if k not in actor_detail}
                    checks = actor.get("identityChecks")
                    if isinstance(checks, dict):
                        # Only literal True is omitted. False, null, numeric,
                        # and unfamiliar values remain visible as reported.
                        remaining = {k: v for k, v in checks.items() if v is not True}
                        if len(remaining) != len(checks):
                            note(child + "[*].identityChecks", count=len(checks) - len(remaining))
                        if remaining or not checks:
                            projected["identityChecks"] = remaining
                        else:
                            projected.pop("identityChecks", None)
                    actors.append(project(projected, child + "[*]"))
                result[key] = actors
            elif key == "terrain" and isinstance(item, dict) and isinstance(item.get("cells"), list):
                cells = item["cells"]
                known = [cell for cell in cells if isinstance(cell, dict)
                         and cell.get("loaded") is True and cell.get("known") is not False]
                result[key] = project({k: v for k, v in item.items() if k != "cells"}, child)
                result[key]["cellSummary"] = {
                    "reported": len(cells), "loaded": len(known), "unknown": len(cells) - len(known),
                    "blocked": sum(cell.get("blocked") is True or cell.get("collision") is True for cell in known),
                    "scope": "reported cells only; counts do not prove route passability or full map coverage",
                }
                note(child + ".cells", count=len(cells))
            elif key == "screenshot" and isinstance(item, dict):
                result[key] = {k: v for k, v in item.items()
                               if not (k == "url" and isinstance(v, str) and v.startswith("data:"))}
                if "url" in item and "url" not in result[key]:
                    note(child, fields=["url"])
            elif key in {"events", "samples"} and isinstance(item, list):
                result[key] = {"reportedCount": len(item), "itemsOmitted": True,
                               "scope": "response count only; not complete recording coverage"}
                note(child, count=len(item))
            elif key == "nativeGetterChecks" and isinstance(item, list):
                retained = [check for check in item if not isinstance(check, dict) or check.get("passed") is not True]
                result[key] = {"reportedCount": len(item), "nonPassing": retained}
                note(child, count=len(item) - len(retained))
            elif key == "player" and isinstance(item, dict):
                removed = set(item) & {"face_x", "face_y", "face_z", "unk88_x", "unk88_y", "unk94_x", "unk94_y"}
                result[key] = {k: v for k, v in item.items() if k not in removed}
                if removed:
                    note(child, fields=removed)
            elif key == "lastError":
                result[key] = project_error(item, child)
            elif key == "operation":
                result[key] = item  # Never project a completed command receipt.
            else:
                result[key] = project(item, child, job=job)
        return result

    result = {key: project(value, key) if key == "result" else
              project_session(value) if key == "session" else value
              for key, value in response.items()}
    result["outputView"] = {
        "kind": "summary", "complete": False, "scope": "display only; not behavior proof",
        "fullResponse": "omit --summary", "omitted": omitted,
        "checks": "Only reported passing checks are omitted; omitted or absent checks are not proof.",
    }
    return result


def _object(value: str) -> dict[str, Any]:
    try:
        result = json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"invalid JSON: {error.msg}") from error
    if not isinstance(result, dict):
        raise argparse.ArgumentTypeError("arguments must be a JSON object")
    return result


def _handle(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use the numeric handle value from inspect (decimal or 0x hex)") from error


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("use a whole number") from error
    if number < 1:
        raise argparse.ArgumentTypeError("use a number greater than zero")
    return number


def request(base_url: str, payload: dict[str, Any], timeout: float = 120) -> dict[str, Any]:
    """Send once; a timeout is unknown, not permission to repeat a mutation."""
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc \
            or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("--url must be an HTTP(S) server URL without credentials, query, or fragment")
    if not 0 < timeout <= 600:
        raise ValueError("--timeout must be greater than zero and at most 600 seconds")
    url = base_url.rstrip("/") + "/api/v2/devtools"
    envelope = dict(payload)
    envelope.setdefault("requestId", str(uuid.uuid4()))
    req = urllib.request.Request(
        url, data=json.dumps(envelope).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        raw = error.read(8 * 1024 * 1024 + 1)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ValueError(f"Workshop returned HTTP {error.code}; check the server status") from error
        if isinstance(result, dict) and result.get("ok") is False:
            return result
        raise ValueError(f"Workshop returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ValueError(
            f"No confirmed response from {url}. Check 'owctl dev status' before retrying. "
            f"Request ID: {envelope['requestId']}. {error}"
        ) from error
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Workshop response exceeded 8 MiB")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Workshop did not return JSON; restart V2 if the endpoint is not loaded") from error
    if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
        raise ValueError("Workshop returned an invalid devtools response")
    return result


def _run(args: argparse.Namespace) -> int:
    operation = args.dev_operation
    values = dict(getattr(args, "dev_args", {}) or {})
    for name in getattr(args, "dev_fields", ()):
        value = getattr(args, name, None)
        if value is not None:
            values[name] = value
    argument_error = None
    if getattr(args, "test_file", None) is not None:
        try:
            with Path(args.test_file).open("rb") as stream:
                raw = stream.read(262145)
            if len(raw) > 262144:
                raise ValueError("test file exceeds 256 KiB")
            values["test"] = _object(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError, argparse.ArgumentTypeError) as error:
            argument_error = f"Cannot read checked test: {error}"
    if operation == "step" and hasattr(args, "positional_frames"):
        if args.positional_frames is not None and args.frames is not None:
            argument_error = "Use positional frames or --frames, not both."
        values["frames"] = args.frames if args.frames is not None else args.positional_frames or 1
    payload = {"op": operation, "args": values}
    if args.request_id:
        payload["requestId"] = args.request_id
    try:
        result = ({"ok": False, "error": {"code": "invalid_arguments", "message": argument_error}}
                  if argument_error else request(args.url, payload, args.timeout))
    except ValueError as error:
        result = {"ok": False, "error": {"code": "transport_error", "message": str(error)}}
    if args.summary:
        result = summarize_response(result)
    if args.json:
        # The explicit agent view also avoids whitespace on every scalar.
        print(json.dumps(result, indent=None if args.summary else 2, sort_keys=True,
                         separators=(",", ":") if args.summary else None))
    elif not result["ok"]:
        error = result.get("error", {})
        print(f"owctl dev: {error.get('code', 'error')}: {error.get('message', 'command failed')}", file=sys.stderr)
        if error.get("details"):
            print(json.dumps(error["details"], indent=2), file=sys.stderr)
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


def _transport_options(parser: argparse.ArgumentParser, *, defaults: bool = False) -> None:
    missing = argparse.SUPPRESS
    parser.add_argument("--url", default=os.environ.get("OW_DEVTOOLS_URL", DEFAULT_URL) if defaults else missing,
                        help="Workshop URL (default: OW_DEVTOOLS_URL or localhost:8766)")
    parser.add_argument("--timeout", type=float, default=120 if defaults else missing,
                        help="HTTP wait in seconds, at most 600; no automatic retries")
    parser.add_argument("--json", action="store_true", default=False if defaults else missing,
                        help="print the structured result, including errors (full unless --summary)")
    parser.add_argument("--summary", action="store_true", default=False if defaults else missing,
                        help="compact state/identity view; omit repeated checks, tool hashes and raw lists; command errors/receipts stay full")
    parser.add_argument("--request-id", default=None if defaults else missing,
                        help="reuse the same ID only when checking/retrying the same request")


def register(commands: Any) -> None:
    """Add a discoverable CLI while retaining the generic versioned command seam."""
    dev = commands.add_parser("dev", help="Control the shared Workshop emulator session")
    _transport_options(dev, defaults=True)
    sub = dev.add_subparsers(dest="dev_command", required=True)

    def operation(name, op=None, fields=(), help_text=None):
        parser = sub.add_parser(name, help=help_text)
        _transport_options(parser)
        parser.set_defaults(handler=_run, dev_operation=op or name, dev_fields=fields)
        return parser

    operation("help", help_text="Read available operations and limits from the live service")
    operation("status", help_text="Read session state and last command outcome")
    catalog = operation("catalog", fields=("kind", "query", "limit"), help_text="Find species, map, and move IDs")
    catalog.add_argument("kind", choices=("species", "maps", "moves"))
    catalog.add_argument("--query")
    catalog.add_argument("--limit", type=_positive, default=20)
    start = operation("start", fields=("rom", "save", "mode"), help_text="Start from a private ROM/save copy")
    start.add_argument("--rom")
    start.add_argument("--save")
    start.add_argument("--mode", choices=("normal", "prepared"), default="normal")
    inspect = operation("inspect", fields=("handle",), help_text="Inspect all actors or an exact current handle")
    inspect.add_argument("--handle", type=_handle, help="exact numeric handle value from inspect output")
    explain = operation("explain", fields=("handle",), help_text="Read a current actor and its observed resolver receipt; missing evidence stays unknown")
    explain.add_argument("--handle", type=_handle, required=True)
    events = operation("events", fields=("handle", "limit"), help_text="Read a bounded event tail, not complete test coverage")
    events.add_argument("--handle", type=_handle)
    events.add_argument("--limit", type=_positive)
    operation("checkpoint", help_text="Save one current observation for a later exact JSON comparison")
    compare = operation("compare", fields=("left", "right"), help_text="Compare two saved JSON artifacts; this is diagnostic, not gameplay proof")
    compare.add_argument("left", help="relative artifact path, e.g. session-123/checkpoint-123.json")
    compare.add_argument("right", help="relative artifact path from another checkpoint receipt")
    step = operation("step", fields=("frames", "keys"), help_text="Advance a bounded number of frames with input")
    step.add_argument("positional_frames", metavar="frames", type=_positive, nargs="?")
    step.add_argument("--frames", type=_positive, help="frame count; alias for positional frames (default: 1)")
    step.add_argument("--keys", nargs="*", type=str.upper, default=[], help="UP DOWN LEFT RIGHT A B X Y L R START SELECT")
    for name in ("play", "pause", "capture", "diagnostics", "reset", "stop"):
        operation(name)
    terrain = operation("terrain", fields=("radius", "x", "z"), help_text="Read loaded terrain at a point or near the player; radius 0 reads one tile")
    terrain.add_argument("--radius", type=int)
    terrain.add_argument("--x", type=int)
    terrain.add_argument("--z", type=int)
    teleport = operation("teleport", fields=("map", "x", "z", "facing"), help_text="Request a game-owned map warp; marks the session prepared")
    for name in ("map", "x", "z"):
        teleport.add_argument(name, type=int)
    teleport.add_argument("--facing", type=int, choices=range(4), default=1,
                          help="0 UP, 1 DOWN, 2 LEFT, 3 RIGHT")
    spawn = operation("spawn", fields=("species", "form", "role", "slot", "x", "z", "level"),
                      help_text="Create a subject through the game adapter; marks the session prepared")
    spawn.add_argument("species", type=int, help="numeric species ID")
    spawn.add_argument("--role", choices=("wild", "follower", "mounted"), default="wild")
    for name in ("form", "slot", "x", "z", "level"):
        spawn.add_argument("--" + name, type=int)
    party = operation("party", fields=("slot", "species", "form", "level", "moves", "hp", "status"),
                      help_text="Edit a party slot and mark the session prepared (use inspect to read)")
    party.add_argument("slot", type=int)
    party.add_argument("--species", type=int)
    for name in ("form", "level", "hp", "status"):
        party.add_argument("--" + name, type=int)
    party.add_argument("--moves", nargs="+", type=int)

    record = sub.add_parser("record", help="Start, stop, or export a diagnostic recording")
    _transport_options(record)
    recording = record.add_subparsers(dest="record_command", required=True)
    for name, op in (("start", "record.start"), ("stop", "record.stop"), ("export", "recording.export")):
        parser = recording.add_parser(name)
        _transport_options(parser)
        parser.set_defaults(handler=_run, dev_operation=op, dev_fields=())
        if name == "start":
            parser.set_defaults(dev_fields=("maxFrames", "maxEvents"))
            parser.add_argument("--max-frames", dest="maxFrames", type=_positive,
                                help="retained frame limit; service validates bounds and supplies the default")
            parser.add_argument("--max-events", dest="maxEvents", type=_positive,
                                help="retained event limit; service validates bounds and supplies the default")
    test = sub.add_parser("test", help="Validate and run bounded checked tests through the shared session")
    _transport_options(test)
    tests = test.add_subparsers(dest="test_command", required=True)
    descriptions = {
        "list": "List saved tests and their declared budgets",
        "validate": "Validate a reviewed JSON file without running it",
        "save": "Save a new reviewed JSON test; existing tests are not overwritten",
        "start": "Start a fresh async job; keep its runId and poll status",
        "status": "Read progress independently of boot or input; a start is not accepted proof",
        "cancel": "Cancel the exact run at the next bounded worker boundary",
        "export": "Export the terminal manifest, including acceptedProof and failures",
    }
    for name, description in descriptions.items():
        parser = tests.add_parser(name, help=description, description=description)
        _transport_options(parser)
        parser.set_defaults(handler=_run, dev_operation="test." + name, dev_fields=())
        if name in ("validate", "save"):
            parser.add_argument("--file", dest="test_file", required=True,
                                help="UTF-8 JSON object, at most 256 KiB; sent unchanged for service validation")
        if name in ("save", "start"):
            parser.add_argument("name")
            parser.set_defaults(dev_fields=("name",))
        if name in ("status", "cancel", "export"):
            parser.add_argument("--run-id", dest="runId", required=name != "status",
                                help="exact runId from test start/status; status defaults to the current run")
            parser.set_defaults(dev_fields=("runId",))
    recipe = sub.add_parser("recipe", help="Save, load, or list shared setup recipes")
    _transport_options(recipe)
    recipes = recipe.add_subparsers(dest="recipe_command", required=True)
    for name in ("save", "load", "list"):
        parser = recipes.add_parser(name)
        _transport_options(parser)
        parser.set_defaults(handler=_run, dev_operation="recipe." + name,
                            dev_fields=() if name == "list" else ("name",))
        if name != "list":
            parser.add_argument("name")
    draft = operation("scenario-draft", op="scenario.draft", fields=("name", "expectation"),
                      help_text="Export a draft, not an accepted proof result")
    draft.add_argument("name")
    draft.add_argument("--expectation", required=True)
    generic = operation("command", fields=(), help_text="Call any documented operation with a JSON argument object")
    generic.add_argument("dev_operation", metavar="operation")
    generic.add_argument("--args", dest="dev_args", type=_object, default={})
