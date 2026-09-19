"""Bounded diagnostic recordings, safe recipes, and unverified scenario drafts.

No emulator, memory writes, scenario activation, or proof receipts live here.
The worker supplies coherent snapshots and verifies live engine membership.
This layer checks identity consistency; it cannot replace that observation.
"""
from __future__ import annotations

from collections import deque
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
from tools.overworld.devtools_contract import PREPARED_OPS


HANDLE_FIELDS = ("value", "slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")
SUBJECT_FIELDS = ("handle", "subjectIdentity", "species", "role")
GENERATION_FIELDS = ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
RECIPE_OPS = PREPARED_OPS | {"step"}
MAX_RECIPE_BYTES = 65536
MAX_SNAPSHOT_BYTES = 1024 * 1024
# Source hashes grow with the shared tool set; never omit hashes to fit the
# old 16 KiB limit. Keep one bounded limit for export and draft ingestion.
MAX_IDENTITY_BYTES = 1024 * 1024
# Preserve the former total row budget while allowing richer native rows.
MAX_SNAPSHOT_BYTES_TOTAL = 1800 * 65536


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def _text(value: Any, name: str, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonempty text of at most {maximum} characters")
    return value


def _copy_json(value: Any, maximum: int = 65536) -> Any:
    def check(item: Any, depth: int = 0) -> None:
        if depth > 20:
            raise ValueError("JSON nesting exceeds 20 levels")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON object keys must be strings")
            for child in item.values():
                check(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                check(child, depth + 1)
        elif item is not None and type(item) not in (bool, int, float, str):
            raise ValueError("value is not JSON data")
    check(value)
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("value is not finite JSON data") from error
    if len(encoded.encode("utf-8")) > maximum:
        raise ValueError(f"JSON record exceeds {maximum} bytes")
    return json.loads(encoded)


def _mode(value: Any) -> str:
    if not isinstance(value, str) or value not in ("normal", "prepared"):
        raise ValueError("mode must be normal or prepared")
    return value


def _name(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", value) or ".." in value:
        raise ValueError("name must be 1..64 lowercase letters, digits, dots, underscores or dashes; no paths")
    return value


def _subject(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or any(key not in value for key in SUBJECT_FIELDS):
        raise ValueError("subject needs a full handle, subjectIdentity, species and role")
    handle = value["handle"]
    if not isinstance(handle, dict) or set(handle) != set(HANDLE_FIELDS):
        raise ValueError("subject.handle needs all six generation-safe fields")
    _integer(handle["slot"], "handle.slot", 0, 9)
    for key in HANDLE_FIELDS[2:]:
        _integer(handle[key], "handle." + key, 1, 65535)
    _integer(handle["value"], "handle.value", 1, 0xFFFFFFFF)
    if handle["value"] != ((handle["generation"] << 16) | handle["slot"]):
        raise ValueError("handle.value differs from slot/generation")
    _integer(value["subjectIdentity"], "subjectIdentity", 1, 0xFFFFFFFF)
    _integer(value["species"], "species", 1, 65535)
    if value["role"] not in ("WILD", "FOLLOWER", "MOUNTED", "SCRIPTED"):
        raise ValueError("subject.role is not a known actor role")
    return _copy_json({key: value[key] for key in SUBJECT_FIELDS}, 2048)


def _handle_key(subject: dict[str, Any]) -> tuple[int, ...]:
    return tuple(subject["handle"][key] for key in HANDLE_FIELDS)


def select_current_actor(snapshot: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    """Resolve an exact selection in this snapshot, never by species or slot alone."""
    selected = _subject(subject)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("context"), dict):
        raise ValueError("snapshot needs authoritative current context")
    context = snapshot["context"]
    for key in ("fieldEpoch", "mapGeneration"):
        _integer(context.get(key), "current context." + key, 1, 65535)
        if selected["handle"][key] != context[key]:
            raise ValueError("selected actor belongs to a stale " + key)
    actors = snapshot.get("actors")
    if not isinstance(actors, list):
        raise ValueError("snapshot.actors must be a list")
    matches = [actor for actor in actors if isinstance(actor, dict)
               and actor.get("active") is True and actor.get("handle") == selected["handle"]]
    if len(matches) != 1:
        raise ValueError("selected handle must name exactly one current active actor")
    actor = matches[0]
    if _subject(actor) != selected:
        raise ValueError("selected handle now names a different subject or role")
    if actor.get("presentationAttached") is not True or actor.get("identityVerified") is not True:
        raise ValueError("selected actor lacks current verified engine/presentation identity")
    for key in GENERATION_FIELDS:
        _integer(actor.get(key), key, 1, 0xFFFFFFFF)
        if key in subject and subject[key] != actor[key]:
            raise ValueError("selected actor has a stale " + key)
    return {**selected, **{key: actor[key] for key in GENERATION_FIELDS},
            "observedFrame": _integer(snapshot.get("frame"), "snapshot.frame", 0, 0xFFFFFFFF),
            "identityVerified": True, "engineIdentity": _copy_json(actor.get("engineIdentity"))}


FIELD_OWNED_KEYS = frozenset({"actors", "player", "party", "partyObservation", "terrain", "context",
    "actorFrame", "selector", "dialogue", "fieldControl", "observerControl", "resolvedProfiles", "streaming"})


def engine_binding_identity(value):
    """Stable binding, with checked dynamic object flags kept in raw evidence."""
    result = _copy_json(value)
    if not isinstance(result, dict):
        raise ValueError("engine binding must be an object")
    lookup = result.get("id_lookup")
    if lookup is not None:
        if not isinstance(lookup, dict) or not isinstance(lookup.get("matching_objects"), list):
            raise ValueError("engine lookup rows are missing")
        for row in lookup["matching_objects"]:
            if not isinstance(row, dict):
                raise ValueError("engine lookup row must be an object")
            flags = _integer(row.get("flags"), "engine lookup flags", 0, 0xFFFFFFFF)
            active, flag25 = bool(flags & 1), bool(flags & (1 << 25))
            if row.get("active") is not active or row.get("flag25") is not flag25 \
                    or row.get("lookup_eligible") is not (active and not flag25):
                raise ValueError("engine lookup flags disagree with membership")
            # Movement/animation flags are state, not identity. Keep active,
            # eligibility, every pointer/id, and the full lookup result.
            del row["flags"]
    return result


def validate_field_absence(value):
    """Validate the native sampler's explicit no-field row, never manufacture one."""
    if value.get("fieldAvailable") is not False or value.get("observationBoundary") != "main-task-queue-completion" \
            or type(value.get("prepared")) is not bool or FIELD_OWNED_KEYS.intersection(value):
        raise ValueError("absent field row contains missing provenance or stale field data")
    for key in ("frame", "nativeCycle"): _integer(value.get(key), key, 0, 0xFFFFFFFF)
    availability = value.get("fieldAvailability", {})
    pointer = _integer(availability.get("fieldPointer"), "field pointer", 0, 0xFFFFFFFF)
    magic = _integer(availability.get("actorStateMagic"), "actor magic", 0, 0xFFFFFFFF)
    if pointer and (not 0x02000000 <= pointer < 0x02400000 or pointer & 3):
        raise ValueError("invalid native field pointer")
    reasons = ([] if pointer else ["null-field-pointer"]) + ([] if magic == 0x5353574F else ["actor-system-uninitialized"])
    if "lifecycle" in availability:
        lifecycle = availability["lifecycle"]
        if reasons or pointer > 0x02400000 - 0x70 or not isinstance(lifecycle, dict) or set(lifecycle) != {
                "authenticated", "fieldReady", "controlPointer", "managerPointer",
                "managerExecState", "managerProcState"} or lifecycle["authenticated"] is not True \
                or type(lifecycle["fieldReady"]) is not int or lifecycle["fieldReady"] != 0:
            raise ValueError("invalid native field lifecycle provenance")
        control = _integer(lifecycle["controlPointer"], "field control pointer", 0, 0xFFFFFFFF)
        manager = _integer(lifecycle["managerPointer"], "field manager pointer", 0, 0xFFFFFFFF)
        for address, size in ((control, 16), (manager, 40)):
            if address and (not 0x02000000 <= address <= 0x02400000 - size or address & 3):
                raise ValueError("invalid native field lifecycle pointer")
        execution, procedure = lifecycle["managerExecState"], lifecycle["managerProcState"]
        if not control or not manager:
            if (not control and manager) or execution is not None or procedure is not None:
                raise ValueError("absent field manager contains stale state")
            reasons = ["field-control-absent" if not control else "field-manager-absent"]
        else:
            execution = _integer(execution, "field manager execution state", 0, 3)
            procedure = _integer(procedure, "field manager procedure state", 0,
                                 3 if execution in (0, 1) else 2 if execution == 3 else 0)
            # Stock leave clears ready before the next manager exec changes 2 to 3.
            reasons = ["field-initializing" if execution in (0, 1) else "field-exiting"]
    if not reasons or availability.get("reasons") != reasons or not isinstance(value.get("nativeObservation"), dict) \
            or not isinstance(value.get("observationErrors"), list):
        raise ValueError("invalid native field absence reason or observer data")
    for key in ("romSha256", "sourceSaveSha256"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise ValueError("absent field ROM/save identity missing")


class Recording:
    """Keep the most recent bounded snapshots/events; never infer a stalled game.

    max_frames is the number of retained distinct snapshot records, not a soak
    duration. Repeated samples at the same frame replace the last snapshot and
    are counted. Frame span and sample count are exported separately.
    """

    def __init__(self, max_frames: int = 1800, max_events: int = 4000,
                 *, max_bytes: int = MAX_SNAPSHOT_BYTES_TOTAL):
        self.max_frames = _integer(max_frames, "max_frames", 1, 1800)
        self.max_events = _integer(max_events, "max_events", 1, 4000)
        self.max_bytes = _integer(max_bytes, "max_bytes", 1, MAX_SNAPSHOT_BYTES_TOTAL)
        self._snapshots: deque[dict[str, Any]] = deque()
        self._snapshot_sizes: deque[int] = deque()
        self._snapshot_bytes = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._failures: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._previous: dict[tuple[int, ...], dict[str, Any]] = {}
        self._counts = dict(snapshotsReceived=0, snapshotsDropped=0, snapshotsReplaced=0,
                            eventsReceived=0, eventsDropped=0, failuresReceived=0, failuresDropped=0)
        self._prepared = False

    def _failure(self, frame: int, code: str, detail: Any) -> None:
        self._counts["failuresReceived"] += 1
        self._counts["failuresDropped"] += len(self._failures) == self.max_events
        self._failures.append({"frame": frame, "code": code, "detail": detail})

    def add_snapshot(self, frame: int, snapshot: dict[str, Any]) -> None:
        frame = _integer(frame, "frame", 0, 0xFFFFFFFF)
        value = _copy_json(snapshot, min(MAX_SNAPSHOT_BYTES, self.max_bytes))
        if not isinstance(value, dict) or type(value.get("frame")) is not int or value["frame"] != frame:
            raise ValueError("snapshot.frame must equal the recorded frame")
        if value.get("fieldAvailable") is False:
            validate_field_absence(value)
            self._previous = {}  # No identity comparison can bridge an unobserved field.
            self._prepared |= value["prepared"]
            if value["observationErrors"]:
                self._failure(frame, "field-absence-observer-error", value["observationErrors"])
            self._store_snapshot(frame, value)
            return
        actors = value.get("actors")
        if not isinstance(actors, list) or len(actors) > 32:
            raise ValueError("snapshot.actors must contain at most 32 entries")
        if "context" in value and not isinstance(value["context"], dict):
            raise ValueError("snapshot.context must be an object")
        current: dict[tuple[int, ...], dict[str, Any]] = {}
        slots: set[int] = set()
        for actor in actors:
            if not isinstance(actor, dict):
                raise ValueError("snapshot actor must be an object")
            if actor.get("active") is not True:
                continue
            try:
                subject = _subject(actor)
            except ValueError as error:
                self._failure(frame, "invalid-active-identity", str(error))
                continue
            key = _handle_key(subject)
            slot = subject["handle"]["slot"]
            if key in current or slot in slots:
                self._failure(frame, "duplicate-active-actor", subject)
            # A role rebound keeps the handle and advances authority/anchor
            # generations. Species/form changes are not a new personality.
            # Only replacement of the bound subject itself is definite here.
            if key in self._previous and self._previous[key]["subjectIdentity"] != subject["subjectIdentity"]:
                self._failure(frame, "subject-changed-without-new-handle", subject)
            context = value.get("context", {})
            for field in ("fieldEpoch", "mapGeneration"):
                if actor.get("identityVerified") is True and type(context.get(field)) is int and context[field] > 0 and context[field] != subject["handle"][field]:
                    self._failure(frame, "stale-active-context", {"field": field, "subject": subject})
            for field in ("logical", "render", "origin", "target"):
                if field not in actor:
                    continue
                point = actor[field]
                if not isinstance(point, dict) or set(point) != {"x", "y"} or any(
                    type(point.get(axis)) is not int or not -32768 <= point[axis] <= 32767 for axis in ("x", "y")
                ):
                    self._failure(frame, "invalid-public-position", {"field": field, "subject": subject})
            current[key] = subject
            slots.add(slot)
        self._previous = current
        self._store_snapshot(frame, value)

    def _store_snapshot(self, frame, value):
        size = len(json.dumps(value, allow_nan=False, separators=(",", ":"),
                              ensure_ascii=False).encode("utf-8"))
        self._counts["snapshotsReceived"] += 1
        if self._snapshots and self._snapshots[-1]["frame"] == frame:
            self._snapshots.pop()
            self._snapshot_bytes -= self._snapshot_sizes.pop()
            self._counts["snapshotsReplaced"] += 1
        while self._snapshots and (len(self._snapshots) >= self.max_frames or
                                   self._snapshot_bytes + size > self.max_bytes):
            self._snapshots.popleft()
            self._snapshot_bytes -= self._snapshot_sizes.popleft()
            self._counts["snapshotsDropped"] += 1
        self._snapshots.append(value)
        self._snapshot_sizes.append(size)
        self._snapshot_bytes += size

    def add_event(self, frame: int, kind: str, data: dict[str, Any]) -> None:
        frame = _integer(frame, "frame", 0, 0xFFFFFFFF)
        if not isinstance(kind, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", kind):
            raise ValueError("event kind must be a short lowercase identifier")
        value = _copy_json(data, 8192)
        if not isinstance(value, dict):
            raise ValueError("event data must be an object")
        if kind == "command" and isinstance(value.get("op"), str) and value["op"] in PREPARED_OPS:
            self._prepared = True  # Attempts also taint normal-play provenance.
        self._counts["eventsReceived"] += 1
        self._counts["eventsDropped"] += len(self._events) == self.max_events
        self._events.append({"frame": frame, "kind": kind, "data": value})

    def failure_summary(self) -> dict[str, Any]:
        """Cheap service stop signal for definite data failures, never a stall guess."""
        return {"hasDefiniteFailures": self._counts["failuresReceived"] > 0,
                "total": self._counts["failuresReceived"],
                "retained": len(self._failures), "dropped": self._counts["failuresDropped"],
                "latest": _copy_json(list(self._failures)[-10:], 16384)}

    def export(self, identity: dict[str, Any], mode: str) -> dict[str, Any]:
        requested_mode = _mode(mode)
        fixture = _copy_json(identity, MAX_IDENTITY_BYTES)
        if not isinstance(fixture, dict):
            raise ValueError("recording identity must be an object")
        subjects, unavailable = [], []
        if self._snapshots:
            latest = self._snapshots[-1]
            if latest.get("fieldAvailable") is False:
                unavailable.append("Field is unavailable; there is no current actor identity.")
            for actor in latest.get("actors", []):
                if actor.get("active") is not True:
                    continue
                try:
                    subjects.append(select_current_actor(latest, actor))
                except ValueError as error:
                    unavailable.append(str(error))
        result = {
            "schemaVersion": 1, "kind": "overworld-diagnostic-recording", "status": "diagnostic",
            "acceptedProof": False, "mode": "prepared" if self._prepared else requested_mode,
            "identity": fixture, "limits": {"maxFrames": self.max_frames, "maxEvents": self.max_events,
                "maxSnapshotBytes": min(MAX_SNAPSHOT_BYTES, self.max_bytes),
                "maxSnapshotBytesTotal": self.max_bytes},
            "counts": {**self._counts, "snapshotsRetained": len(self._snapshots),
                "snapshotBytesRetained": self._snapshot_bytes, "eventsRetained": len(self._events)},
            "truncated": any(self._counts[key] > 0 for key in ("snapshotsDropped", "eventsDropped", "failuresDropped")),
            "snapshots": list(self._snapshots), "events": list(self._events),
            "subjects": subjects, "subjectSelectionErrors": unavailable,
            "definiteFailures": list(self._failures),
            "limitations": ["Diagnostic data only; no accepted gameplay proof.",
                            "No automatic stall, timing, pause, or logical/render-equality claim.",
                            "Identity-change detection compares consecutive snapshots; role rebounds and unverified transition actors are not automatic failures.",
                            "Engine membership is supplied by the worker, not independently measured here."],
        }
        return _copy_json(result, MAX_SNAPSHOT_BYTES_TOTAL + 4000 * 32768)


def _expectation(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return _text(value, "expectation")
    if not isinstance(value, dict) or set(value) - {"source", "observable", "forbidden", "limits"}:
        raise ValueError("expectation must be text or source/observable/forbidden/limits fields")
    return {key: _text(item, "expectation." + key) for key, item in value.items()}


def validate_recipe(value: Any) -> dict[str, Any]:
    value = _copy_json(value, MAX_RECIPE_BYTES)
    if not isinstance(value, dict) or set(value) - {"schemaVersion", "mode", "actions", "subject", "expectation"}:
        raise ValueError("recipe has unknown fields")
    if type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1:
        raise ValueError("recipe.schemaVersion must be 1")
    mode = _mode(value.get("mode"))
    actions = value.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 256:
        raise ValueError("recipe needs 1..256 actions")
    from tools.overworld.devtools_contract import validate_command
    normalized = []
    for action in actions:
        if not isinstance(action, dict) or set(action) != {"op", "args"} or not isinstance(action["op"], str) or action["op"] not in RECIPE_OPS:
            raise ValueError("recipe action must be step or a listed prepared operation with args")
        if not isinstance(action["args"], dict):
            raise ValueError("recipe action.args must be an object")
        if mode == "normal" and action["op"] in PREPARED_OPS:
            raise ValueError("setup operations require prepared mode")
        normalized.append({"op": action["op"], "args": validate_command(action["op"], action["args"])})
    result = {"schemaVersion": 1, "mode": mode, "actions": normalized}
    if "subject" in value:
        result["subject"] = _subject(value["subject"])
    if "expectation" in value:
        result["expectation"] = _expectation(value["expectation"])
    return result


def save_recipe(directory: str | Path, name: str, recipe: dict[str, Any]) -> Path:
    """Create a new named recipe only; never replace an existing file or link."""
    name = _name(name)
    value = validate_recipe(recipe)
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if len(encoded.encode("utf-8")) > MAX_RECIPE_BYTES:
        raise ValueError("formatted recipe file is too large")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + ".json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(encoded)
    return path


def load_recipe(directory: str | Path, name: str) -> dict[str, Any]:
    path = Path(directory) / (_name(name) + ".json")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError("recipe must be a regular file")
        data = source.read(MAX_RECIPE_BYTES + 1)
    if len(data) > MAX_RECIPE_BYTES:
        raise ValueError("recipe file is too large")
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate recipe key: " + key)
            result[key] = item
        return result
    return validate_recipe(json.loads(data, object_pairs_hook=pairs))


def recording_to_draft(recording: dict[str, Any], name: str, expectation: Any,
                       subject: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate a review draft, not an executable or accepted scenario."""
    name = _name(name)
    if not isinstance(recording, dict) or recording.get("kind") != "overworld-diagnostic-recording" or recording.get("acceptedProof") is not False:
        raise ValueError("draft source must be an unaccepted diagnostic recording")
    expected = _expectation(expectation)
    mode = _mode(recording.get("mode"))
    identity = _copy_json(recording.get("identity", {}), MAX_IDENTITY_BYTES)
    if not isinstance(identity, dict):
        raise ValueError("recording.identity must be an object")
    blockers = ["Review and implement a permanent scenario/collector before activation.",
                "Validate the observer with known-bad live input; this recording is not acceptance proof."]
    for key in ("rom", "save", "debugDescriptor"):
        digest = identity.get(key, {}).get("sha256") if isinstance(identity.get(key), dict) else None
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            blockers.append("Missing original " + key + " SHA-256.")
    if not isinstance(expected, dict) or not expected.get("source"):
        blockers.append("Expected behavior has no independent source.")
    if not expected or isinstance(expected, dict) and not expected.get("observable"):
        blockers.append("Expected observable behavior is not defined.")
    selected = None
    snapshots = recording.get("snapshots", [])
    events = recording.get("events", [])
    if not isinstance(snapshots, list) or len(snapshots) > 1800 or not isinstance(events, list) or len(events) > 4000:
        raise ValueError("recording snapshot/event bounds differ")
    if subject is not None:
        if not snapshots:
            blockers.append("No snapshot can validate the selected actor.")
        else:
            try:
                selected = select_current_actor(snapshots[-1], subject)
            except ValueError as error:
                blockers.append("Actor selection failed: " + str(error))
    else:
        blockers.append("Choose an exact current actor and role; none was inferred.")
    if any(not isinstance(event, dict) or not isinstance(event.get("data"), dict) for event in events):
        raise ValueError("recording event data must be an object")
    commands = [_copy_json(event, 16384) for event in events if event.get("kind") == "command"]
    actions = []
    for event in commands:
        data = event["data"]
        if not isinstance(data.get("op"), str) or data["op"] not in RECIPE_OPS or type(data.get("ok")) is not bool:
            blockers.append("A recorded command has no replayable result/operation.")
            continue
        if data["op"] in PREPARED_OPS:
            mode = "prepared"
        if data["ok"] is not True:
            blockers.append("A recorded command failed; preserve its receipt and review before replay.")
        actions.append({"op": data["op"], "args": data.get("args")})
    recipe = None
    if actions:
        try:
            recipe = validate_recipe({"schemaVersion": 1, "mode": mode, "actions": actions})
        except ValueError as error:
            blockers.append("Recorded actions need review: " + str(error))
    else:
        blockers.append("No replayable commands were recorded.")
    if recording.get("truncated"):
        blockers.append("The recording is truncated; it cannot establish the complete setup or behavior interval.")
    if recording.get("definiteFailures"):
        blockers.append("The recording contains definite identity/data failures.")
    return {
        "schemaVersion": 1, "kind": "overworld-scenario-draft", "id": "draft." + name,
        "status": "planned", "verificationStatus": "unverified", "acceptedProof": False,
        "origin": {"identity": identity, "mode": mode, "counts": _copy_json(recording.get("counts", {}))},
        "subject": selected, "expectation": expected, "recordedCommands": commands,
        "proposedRecipe": recipe,
        "verification": {"kind": "normal-play" if mode == "normal" else "controlled-case",
                         "setupAudit": "pending", "setupMutations": [event for event in commands if isinstance(event["data"].get("op"), str) and event["data"]["op"] in PREPARED_OPS]},
        "blockers": list(dict.fromkeys(blockers)),
    }
