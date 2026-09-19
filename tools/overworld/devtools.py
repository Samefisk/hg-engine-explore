"""One owned emulator session behind both the Workshop and agent commands.

Interactive work and checked test jobs share this control plane. Claim credit
requires the separate registered measurement check, not a successful command.
All emulator access is serialized; reset replaces the worker process.
"""
from __future__ import annotations

import atexit
import base64
from collections import OrderedDict, deque
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import uuid

from .devtools_contract import OPERATIONS, PREPARED_OPS, command_help, validate_command, source_paths
from .devtools_copy import copy_private_file, remove_private_rom
from .evidence_store import scenario_lock
from .runs import HEADLESS_PYTHON_FLAGS, headless_python


class DevtoolsError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.details = code, details


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(data)
    return sha.hexdigest()


def _write_json(path, data):
    # Session-owned output only. Replacement is atomic for concurrent UI reads.
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def _write_json_gzip(path, data):
    # Memory-data exports can approach the recording cap. Store one lossless
    # compressed artifact instead of retaining a large plain duplicate.
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = (json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    temporary.write_bytes(gzip.compress(encoded, compresslevel=1, mtime=0))
    temporary.replace(path)


def _recordable_snapshot(snapshot):
    value = {k: v for k, v in snapshot.items() if k not in {"screenshot", "samples", "events"}}
    if "screenshot" in snapshot:
        value["screenshot"] = {k: v for k, v in snapshot["screenshot"].items() if k != "url"}
    return value


class Worker:
    """Bounded line protocol; emulator chatter never becomes a response."""
    def __init__(self, root, directory):
        self.sequence = 0
        self.responses = queue.Queue()
        self.errors = deque(maxlen=200)
        self.directory = directory
        env = {**os.environ, "SDL_AUDIODRIVER": "dummy", "SDL_VIDEODRIVER": "dummy"}
        self.process = subprocess.Popen(
            [str(headless_python(root)), *HEADLESS_PYTHON_FLAGS,
             str(root / "scripts/overworld_devtools_worker.py")],
            cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.responses.put(json.loads(line))
                except ValueError:
                    self.responses.put({"protocolError": line[:300]})
        finally:
            self.responses.put({"eof": True})

    def _stderr(self):
        for line in self.process.stderr:
            self.errors.append(line.rstrip()[:2000])

    def call(self, op, args=None):
        self.sequence += 1
        request = {"id": self.sequence, "op": op, "args": args or {}}
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            timeout = 120 if op in {"open", "teleport"} else max(55, request["args"].get("frames", 1) * 0.1)
            deadline = getattr(self, "job_deadline", None)
            if deadline is None:
                response = self.responses.get(timeout=timeout)
            else:
                deadline = min(deadline, time.monotonic() + timeout)
                while True:
                    canceled = getattr(self, "job_cancel", None)
                    if canceled is not None and canceled.is_set():
                        self.close()
                        raise DevtoolsError("test-canceled", "The owned test was canceled during a native command.", {"command": op, "workerTail": list(self.errors)})
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self.close()
                        raise DevtoolsError("command-wall-budget", "The native command exceeded the test/action deadline.", {"command": op, "workerTail": list(self.errors)})
                    try:
                        response = self.responses.get(timeout=min(0.2, remaining))
                        break
                    except queue.Empty:
                        continue
        except (BrokenPipeError, OSError, queue.Empty) as error:
            self.close()
            raise DevtoolsError("worker-unavailable", "Emulator command did not finish; reset the session.", list(self.errors)) from error
        if not isinstance(response, dict) or response.get("id") != self.sequence:
            self.close()
            raise DevtoolsError("worker-protocol", "Emulator worker stopped or returned an invalid response.", list(self.errors))
        if response.get("ok") is not True:
            error = response.get("error") or {}
            if error.get("fatal"):
                self.close()
                raise DevtoolsError("unsafe-runtime-state", error.get("message", "Native operation failed; the disposable worker was closed."), error)
            raise DevtoolsError(error.get("code", "operation-failed"), error.get("message", "Emulator operation failed."), error.get("details"))
        return response.get("result", {})

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            if stream:
                stream.close()
        if self.errors:
            try:
                (self.directory / "worker-tail.log").write_text("\n".join(self.errors) + "\n")
            except OSError as error:
                # Keep the native/transport failure as the command's result.
                # Losing a log file must not prevent Service from closing the
                # session, recording and lease using that original error code.
                self.errors.append("worker-tail.log could not be saved: " + str(error)[:512])


class Service:
    def __init__(self, root, worker_factory=Worker):
        self.root = Path(root).resolve()
        self.worker_factory = worker_factory
        self.lock = threading.RLock()
        self.worker = None
        self.session = None
        self.snapshot = {}
        self.recording = None
        self.recording_active = False
        self.actions = []
        self.action_tail_mergeable = False
        self.events = deque(maxlen=120)
        self.requests = OrderedDict()
        self.used_request_ids = set()
        self.capacity_stop_response = None
        self.lease = None
        self.playing = False
        self.play_generation = 0
        self.start_args = None
        self.directory = None
        self.last_error = None
        from .devtools_jobs import TestJobs
        self.tests = TestJobs(self)

    def status(self):
        # Return the last complete snapshot. Status does not advance the game.
        with self.lock:
            return {"ok": True, "session": deepcopy(self.session), "result": {
                **deepcopy(self.snapshot), "playing": self.playing,
                "recording": self.recording_active, "events": list(self.events),
                "lastError": deepcopy(self.last_error),
            }}

    def command(self, request):
        # These job controls never wait behind a native operation. Cancellation
        # names one exact run; it cannot affect a later session by retry.
        if isinstance(request, dict) and request.get("op") in {"test.status", "test.cancel"}:
            try:
                if set(request) - {"op", "args", "requestId"}:
                    raise ValueError("unknown request field")
                args = validate_command(request["op"], request.get("args"))
                result = self.tests.status(args.get("runId")) if request["op"] == "test.status" else self.tests.cancel(args["runId"])
                return {"ok": True, "result": result}
            except ValueError as error:
                return {"ok": False, "error": {"code": "invalid-command", "message": str(error)}}
        with self.lock:
            request_id = request.get("requestId") if isinstance(request, dict) else None
            try:
                if not isinstance(request, dict) or set(request) - {"op", "args", "requestId"}:
                    raise ValueError("request must contain op, optional args and optional requestId")
                if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 128):
                    raise ValueError("requestId must be text, 1..128 characters")
                signature = json.dumps(request, sort_keys=True)
                if request_id in self.requests:
                    old_signature, response = self.requests[request_id]
                    if signature != old_signature:
                        raise DevtoolsError("request-id-conflict", "This requestId was used for a different command.")
                    return deepcopy(response)
                if request_id in self.used_request_ids:
                    raise DevtoolsError("request-expired", "This requestId is older than the retained reply window; it will not be executed again.")
                op = request.get("op")
                args = validate_command(op, request.get("args"))
                if self.tests.active() and op not in {"help", "status", "test.list", "test.validate", "test.status", "test.cancel"}:
                    raise DevtoolsError("test-busy", "A checked test owns this session; inspect or cancel its exact run before another command.")
                if len(self.used_request_ids) >= 10000:
                    # One bounded, stable recovery receipt. No new session
                    # work (including no-ID commands) can run until restart,
                    # so retrying this Stop cannot close a later session.
                    if op == "stop":
                        if self.capacity_stop_response is None:
                            result = self._dispatch(op, args)
                            self.capacity_stop_response = {"ok": True, "session": deepcopy(self.session), "result": result}
                        return deepcopy(self.capacity_stop_response)
                    if op not in {"status", "help"}:
                        raise DevtoolsError("request-capacity", "The service reached its request-ID limit. Stop the session and restart Workshop.")
                if (self.session and self.session.get("recipe", {}).get("state") == "running"
                        and op not in {"help", "status", "inspect", "capture", "terrain", "stop", "reset", "recording.export"}):
                    raise DevtoolsError("recipe-busy", "A recipe is running. Inspect status or stop/reset it before another command.")
                result = self._dispatch(op, args)
                response = {"ok": True, "session": deepcopy(self.session), "result": result}
            except (ValueError, OSError, DevtoolsError) as error:
                code = getattr(error, "code", "invalid-command" if isinstance(error, ValueError) else "io-error")
                response = {"ok": False, "session": deepcopy(self.session),
                            "error": {"code": code, "message": str(error)}}
                if getattr(error, "details", None) is not None:
                    response["error"]["details"] = error.details
                self.last_error = response["error"]
                self._event("error", response["error"])
                if code == "observation-integrity":
                    self.recording_active = False
                if self.session:
                    self.session["lastError"] = deepcopy(response["error"])
                    try:
                        self._persist()
                    except OSError:
                        pass  # Preserve the original failure in the response.
                if code in {"worker-unavailable", "worker-protocol", "native-call-timeout", "unsafe-runtime-state"}:
                    self._stop()
                response["session"] = deepcopy(self.session)
            if (request_id is not None and isinstance(request_id, str) and 1 <= len(request_id) <= 128
                    and request_id not in self.requests and len(self.used_request_ids) < 10000):
                self.requests[request_id] = (json.dumps(request, sort_keys=True), deepcopy(response))
                self.used_request_ids.add(request_id)
                while len(self.requests) > 128:
                    self.requests.popitem(last=False)
            return response

    def _event(self, kind, data, frame=None):
        frame = self.snapshot.get("frame", 0) if frame is None else frame
        # A complete native failure can contain several actor snapshots. Keep
        # that evidence outside the bounded event ring, never let its size
        # replace the original error or prevent worker/lease cleanup.
        if len(json.dumps(data).encode("utf-8")) > 8192:
            original = data
            data = {"detailsOmitted": True, "fullDetails": "artifact or command response"}
            for key in ("op", "ok", "code", "message", "startFrame"):
                if key in original:
                    item = original[key]
                    data[key] = item[:512] if isinstance(item, str) else item
            try:
                if self.directory is None:
                    raise OSError("no session directory")
                data["artifact"] = self._artifact("event-details", original)
            except OSError as error:
                data["artifactError"] = str(error)[:512]
        self.events.append({"frame": frame, "kind": kind, "data": deepcopy(data)})
        if self.recording_active:
            self.recording.add_event(frame, kind, data)

    def _observe(self, result):
        snapshot = result.get("snapshot", {k: v for k, v in result.items() if k not in {"samples", "events"}})
        if not isinstance(snapshot, dict):
            raise DevtoolsError("worker-protocol", "Worker snapshot is not an object.")
        from .devtools_records import FIELD_OWNED_KEYS, validate_field_absence
        if snapshot.get("fieldAvailable") is False:
            validate_field_absence(snapshot)
            self.snapshot = {key: value for key, value in self.snapshot.items() if key not in FIELD_OWNED_KEYS}
        elif snapshot.get("fieldAvailable") is True:
            self.snapshot.pop("fieldAvailability", None)
            self.snapshot.pop("observationErrors", None)
        self.snapshot = {**self.snapshot, **snapshot}
        for event in result.get("events", []):
            self._event(event.get("kind", "native"), event.get("data", event), event.get("frame", self.snapshot.get("frame", 0)))
        if self.recording_active:
            samples = result.get("samples") or [snapshot]
            for sample in samples:
                self.recording.add_snapshot(sample.get("frame", self.snapshot.get("frame", 0)), _recordable_snapshot(sample))
            failures = self.recording.failure_summary()
            if failures["hasDefiniteFailures"]:
                self.playing = False
                self.play_generation += 1
                self.last_error = {"code": "observation-integrity", "message": "Recording paused on a definite identity/data contradiction.",
                                   "details": failures["latest"]}
                raise DevtoolsError("observation-integrity", self.last_error["message"], failures["latest"])
        return deepcopy(self.snapshot)

    def _require_session(self):
        if self.worker is None or not self.session or self.session["state"] != "ready":
            raise DevtoolsError("no-session", "Start a session first.")

    def _start(self, args):
        if self.worker is not None:
            raise DevtoolsError("session-exists", "Stop or reset the current session first.")
        rom = (self.root / args["rom"]).resolve()
        save = (self.root / args["save"]).resolve()
        if rom.suffix.lower() != ".nds" or save.suffix.lower() not in {".dsv", ".sav"}:
            raise ValueError("start requires an .nds ROM and .dsv or .sav save")
        for path in (rom, save):
            if not path.is_file():
                raise ValueError(f"missing input file: {path.name}")
        self.lease = scenario_lock(self.root)
        try:
            self.lease.__enter__()
        except Exception as error:
            self.lease = None
            raise DevtoolsError("emulator-busy", str(error)) from error
        try:
            parent = self.root / "build/overworld-devtools"
            parent.mkdir(parents=True, exist_ok=True)
            self.directory = Path(tempfile.mkdtemp(prefix="session-", dir=parent))
        except Exception:
            self.lease.__exit__(None, None, None)
            self.lease = None
            raise
        self.events.clear()
        self.snapshot = {}
        self.actions = []
        self.action_tail_mergeable = False
        self.recording = None
        self.recording_active = False
        self.last_error = None
        self.start_args = deepcopy(args)
        self.session = {"id": self.directory.name, "state": "starting", "mode": args["mode"],
                        "acceptedProof": False, "startedAt": _utc(), "directory": str(self.directory)}
        try:
            identity = {"sessionId": self.directory.name, "startedAt": self.session["startedAt"]}
            for kind, source in (("rom", rom), ("save", save)):
                target = self.directory / ("game" + source.suffix.lower())
                before = _digest(source)
                copy_method = copy_private_file(source, target)
                if before != _digest(target) or before != _digest(source):
                    raise DevtoolsError("input-changed", "Source changed while the session copy was made.")
                identity[kind] = {"path": str(source), "copy": str(target), "sha256": before,
                                  "size": target.stat().st_size, "copyMethod": copy_method}
                self.session["identity"] = identity
            descriptor = self.root / "build/overworld-system.debug.json"
            if descriptor.is_file():
                identity["debugDescriptor"] = {"sha256": _digest(descriptor), "path": str(descriptor)}
            identity["toolInputs"] = [{"path": path, "sha256": _digest(self.root / path)}
                                     for path in source_paths(self.root) if (self.root / path).is_file()]
            self.session["identity"] = identity
            self._persist()
            self.worker = self.worker_factory(self.root, self.directory)
            self.worker.job_deadline = getattr(self, "job_deadline", None)
            self.worker.job_cancel = getattr(self, "job_cancel", None)
            result = self.worker.call("open", {"rom": identity["rom"]["copy"], "save": identity["save"]["copy"], "sessionDir": str(self.directory)})
            self._observe(result)
            self.session["state"] = "ready"
            self._persist()
            self._event("session-started", {"mode": args["mode"]})
            return deepcopy(self.snapshot)
        except Exception:
            self._stop()
            raise

    def _persist(self):
        if self.directory and self.session:
            _write_json(self.directory / "session.json", self.session)

    def _stop(self):
        self.playing = False
        self.recording_active = False
        self.play_generation += 1
        cleanup_errors = []
        try:
            if self.worker:
                self.worker.close()
        except Exception as error:
            cleanup_errors.append(str(error))
        finally:
            self.worker = None
            if self.lease:
                self.lease.__exit__(None, None, None)
                self.lease = None
        if self.session:
            previous = self.session.get("romCopyCleanup", {})
            if previous.get("reason") == "worker-close-failed" and not cleanup_errors:
                cleanup_errors.append("previous worker close failed; core shutdown remains unconfirmed")
            if cleanup_errors:
                self.session["romCopyCleanup"] = {"status": "retained", "reason": "worker-close-failed"}
            elif previous.get("reason") != "worker-close-failed" \
                    and previous.get("status") not in ("removed", "absent"):
                rom = self.session.get("identity", {}).get("rom")
                if rom:
                    try:
                        self.session["romCopyCleanup"] = remove_private_rom(self.directory, rom)
                    except (OSError, ValueError) as error:
                        cleanup_errors.append(str(error))
                        self.session["romCopyCleanup"] = {"status": "retained", "reason": str(error)}
            self.session["state"] = "stopped"
            self.session["stoppedAt"] = _utc()
            if self.session.get("recipe", {}).get("state") == "running":
                self.session["recipe"]["state"] = "stopped"
            try:
                self._persist()
            except OSError as error:
                cleanup_errors.append(str(error))
        if cleanup_errors:
            self.last_error = {"code": "cleanup-error", "message": "; ".join(cleanup_errors)}
        return {"sessionId": self.session.get("id") if self.session else None,
                "closed": not cleanup_errors and self.worker is None and self.lease is None,
                "errors": cleanup_errors}

    def _play(self, generation):
        while True:
            started = time.monotonic()
            with self.lock:
                if not self.playing or generation != self.play_generation:
                    return
                response = self.command({"op": "step", "args": {"frames": 1}})
                if not response["ok"]:
                    self.playing = False
                    return
            time.sleep(max(0, 1 / 60 - (time.monotonic() - started)))

    def _export(self):
        if self.recording is None:
            raise DevtoolsError("no-recording", "Start a recording first.")
        return self.recording.export(self.session["identity"], self.session["mode"])

    def _remember_action(self, action, *, succeeded):
        """Compact only the recipe view; raw command events remain unchanged.

        A released-key interval is equivalent to a longer released-key
        interval. Keyed steps must retain their separate release boundaries.
        Failed actions are retained, form a merge boundary, and prohibit an
        implicit replay recipe even after the bounded history rolls over.
        """
        action = deepcopy(action)
        mergeable = succeeded and action["op"] == "step" and action["args"]["keys"] == []
        if mergeable and self.action_tail_mergeable and self.actions:
            previous = self.actions[-1]
            maximum = OPERATIONS["step"]["frames"]["maximum"]
            take = min(action["args"]["frames"], maximum - previous["args"]["frames"])
            previous["args"]["frames"] += take
            action["args"]["frames"] -= take
        if not mergeable or action["args"]["frames"]:
            self.actions.append(action)
        self.action_tail_mergeable = mergeable
        if not succeeded:
            self.session["actionsFailed"] = self.session.get("actionsFailed", 0) + 1
        if len(self.actions) > 2000:
            self.actions = self.actions[-2000:]
            self.session["actionsTruncated"] = True

    def _execute_recipe(self, recipe, session_id):
        for index, action in enumerate(recipe["actions"]):
            with self.lock:
                if not self.session or self.session["id"] != session_id or self.session["state"] != "ready":
                    return
                progress = self.session["recipe"]
                progress["currentAction"] = index + 1
                try:
                    self._dispatch(action["op"], action["args"])
                    progress["completedActions"] = index + 1
                except Exception as error:
                    progress["state"] = "failed"
                    progress["error"] = {"code": getattr(error, "code", "recipe-step-failed"),
                                         "message": str(error), "action": index + 1}
                    if getattr(error, "details", None) is not None:
                        progress["error"]["details"] = deepcopy(error.details)
                    self.last_error = progress["error"]
                    self.session["lastError"] = deepcopy(progress["error"])
                    self._event("recipe-failed", progress["error"])
                    if getattr(error, "code", None) in {"worker-unavailable", "worker-protocol", "native-call-timeout", "unsafe-runtime-state"}:
                        self._stop()
                    try:
                        self._persist()
                    except OSError as persist_error:
                        progress["error"]["persistError"] = str(persist_error)
                    return
            # Yield ownership between bounded commands so stop/status remain usable.
            time.sleep(0.001)
        with self.lock:
            if self.session and self.session["id"] == session_id and self.session["state"] == "ready":
                self.session["recipe"]["state"] = "completed"
                self._event("recipe-completed", {"name": self.session["recipe"]["name"]})
                self._persist()

    def _artifact(self, label, value, *, compress=False):
        name = f"{label}-{uuid.uuid4().hex[:12]}.json" + (".gz" if compress else "")
        target = self.directory / name
        (_write_json_gzip if compress else _write_json)(target, value)
        return {"path": str(target), "url": f"/api/v2/devtools/artifacts/{self.directory.name}/{name}",
                "sha256": _digest(target), **({"encoding": "gzip", "mediaType": "application/json"} if compress else {})}

    def artifact(self, relative):
        # Artifacts are data exports only; never serve ROM/save/core files.
        parts = Path(relative).parts
        if len(parts) != 2 or not parts[0].startswith(("session-", "test-")) or not parts[1].endswith((".json", ".json.gz", ".jsonl", ".jsonl.gz", ".png")):
            raise ValueError("invalid artifact")
        parent = (self.root / "build/overworld-devtools").resolve()
        path = parent.joinpath(*parts)
        if path.is_symlink() or not path.resolve().is_relative_to(parent) or not path.is_file():
            raise ValueError("artifact not found")
        media_type = "application/gzip" if path.suffix == ".gz" else \
            mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return path.read_bytes(), media_type

    def _dispatch(self, op, args, *, retain_worker_receipt=False):
        if op.startswith("test."):
            from .devtools_test_contract import validate_test
            if op == "test.list": return self.tests.catalog()
            if op == "test.validate":
                from .devtools_test_efficiency import setup_efficiency_report
                test = validate_test(args["test"])
                return {"valid": True, "test": test, "setupEfficiency": setup_efficiency_report(test),
                        "acceptedProof": False}
            if op == "test.save": return self.tests.save(args["name"], args["test"])
            if op == "test.start": return self.tests.start(args["name"])
            if op == "test.export": return self.tests.export(args["runId"])
            if op == "test.status": return self.tests.status(args.get("runId"))
            if op == "test.cancel": return self.tests.cancel(args["runId"])
        if op == "help":
            return command_help()
        if op == "catalog":
            from .devtools_catalog import catalog
            return catalog(self.root, args["kind"], args.get("query", ""), args["limit"])
        if op == "status":
            return self.status()["result"]
        if op == "compare":
            from .devtools_insight import first_difference
            values = []
            for path in (args["left"], args["right"]):
                raw, mime = self.artifact(path)
                if len(raw) > 4 * 1024 * 1024 or not path.endswith(".json"):
                    raise ValueError("compare requires two saved JSON artifacts of at most 4 MiB each")
                values.append(json.loads(raw))
            return first_difference(*values)
        if op == "start":
            return self._start(args)
        if op == "stop":
            self._stop()
            return {"stopped": True}
        if op == "recipe.list":
            directory = self.root / "tests/overworld/recipes"
            return {"recipes": sorted(p.stem for p in directory.glob("*.json"))}
        if op == "reset":
            if self.start_args is None:
                raise DevtoolsError("no-session", "Start a session first.")
            start = deepcopy(self.start_args)
            self._stop()
            return self._start(start)
        if op not in {"recording.export", "scenario.draft", "record.stop", "recipe.save"}:
            self._require_session()
        elif not self.session:
            raise DevtoolsError("no-session", "Start a session first.")
        if op == "pause":
            self.playing = False
            self.play_generation += 1
            return {"playing": False}
        if op == "play":
            if not self.playing:
                self.playing = True
                self.play_generation += 1
                threading.Thread(target=self._play, args=(self.play_generation,), daemon=True).start()
            return {"playing": True}
        if op == "inspect":
            self._observe(self.worker.call("snapshot"))
            result = deepcopy(self.snapshot)
            if "handle" in args:
                result["actors"] = [a for a in result.get("actors", [])
                                    if (a.get("handle", {}).get("value") if isinstance(a.get("handle"), dict)
                                        else a.get("handle")) == args["handle"]]
                if not result["actors"]:
                    raise DevtoolsError("actor-not-present", "That actor is not present in the current snapshot.")
            return result
        if op == "explain":
            from .devtools_insight import explain_actor
            self._observe(self.worker.call("snapshot"))
            schema = json.loads((self.root / "tools/overworld/behavior_schema.json").read_text())
            return explain_actor(self.snapshot, args["handle"], schema)
        if op == "events":
            retained = list(self.events)
            if "handle" in args:
                def belongs(event):
                    data = event.get("data", {})
                    return data.get("actorHandle") == args["handle"] or any(
                        data.get(key, {}).get("handle", {}).get("value") == args["handle"]
                        for key in ("publicSubject", "publicSubjectAfter"))
                retained = [event for event in retained if belongs(event)]
            return {"events": deepcopy(retained[-args["limit"]:]), "retainedCount": len(retained),
                    "completeHistory": False, "scope": "bounded recent event tail; use checked observations.jsonl for complete test evidence"}
        if op == "checkpoint":
            self._observe(self.worker.call("snapshot"))
            return {"artifact": self._artifact("checkpoint", {"identity": self.session["identity"], "snapshot": self.snapshot})}
        if op == "terrain":
            result = self.worker.call("terrain", args)
            self.snapshot["terrain"] = result.get("terrain", result)
            return {"terrain": deepcopy(self.snapshot["terrain"])}
        if op == "diagnostics":
            result = self.worker.call("diagnostics")
            return {"diagnostics": result, "artifact": self._artifact("diagnostics", result)}
        if op == "snapshot.probe":
            if self.playing:
                raise DevtoolsError("session-playing", "Pause the session before measuring snapshot cost.")
            result = self.worker.call("snapshot.probe", args)
            artifact = self._artifact("snapshot-probe", result)
            fields = (
                "schemaVersion", "scope", "acceptedProof", "proofStatus", "frame", "nativeCycle",
                "iterations", "snapshotsEqual", "gameClocksUnchanged", "snapshotSha256",
                "snapshotBytes", "intervals",
            )
            missing = [key for key in fields if key not in result]
            if missing:
                raise DevtoolsError("worker-protocol", "Snapshot probe result is missing: " + ", ".join(missing))
            return {"probe": {key: deepcopy(result[key]) for key in fields}, "artifact": artifact}
        if op in ("spawn-cost.probe", "main-loop-pacing.arm", "cpu-work.start", "cpu-work.read"):
            if self.playing:
                raise DevtoolsError("session-playing", "Pause before controlling CPU or spawn cost measurement.")
            result = self.worker.call(op, args)
            return {"probe": result, "artifact": self._artifact(op.replace(".", "-"), result)}
        if op == "capture":
            path = self.directory / f"screen-{uuid.uuid4().hex[:12]}.png"
            result = self.worker.call("capture", {"path": str(path)})
            if not path.is_file():
                raise DevtoolsError("capture-missing", "Worker did not create the requested screenshot.")
            data = path.read_bytes()
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise DevtoolsError("capture-invalid", "Worker screenshot is not a PNG.")
            screenshot = {"url": "data:image/png;base64," + base64.b64encode(data).decode(),
                          "path": str(path), "frame": result.get("frame", self.snapshot.get("frame")),
                          "nativeCycle": result.get("nativeCycle"),
                          "sha256": hashlib.sha256(data).hexdigest()}
            self.snapshot["screenshot"] = screenshot
            return {"screenshot": screenshot}
        if op in PREPARED_OPS or op == "step":
            if op in PREPARED_OPS:
                self.playing = False
                self.play_generation += 1
                self.session["mode"] = "prepared"
                mutations = self.session.setdefault("setupMutations", [])
                mutations.append({"op": op, "frame": self.snapshot.get("frame", 0)})
                self.session["setupMutationCount"] = self.session.get("setupMutationCount", 0) + 1
                if len(mutations) > 256:
                    del mutations[:-256]
                    self.session["setupMutationsTruncated"] = True
                self._persist()  # Mark BEFORE dispatch, including failure/timeout.
            event = {"op": op, "args": deepcopy(args)}
            start_frame = self.snapshot.get("frame", 0)
            self._event("command-request", event)
            receipt = {}
            try:
                result = self.worker.call(op, args)
                receipt = {key: value for key, value in result.items() if key not in {"snapshot", "samples", "events", "party", "terrain", "actors", "player"}}
                snapshot = self._observe(result)
                self._event("command", {**event, "ok": True, "startFrame": start_frame, "receipt": receipt})
                self._remember_action(event, succeeded=True)
                if receipt:
                    snapshot["operation"] = receipt
                if retain_worker_receipt and op in PREPARED_OPS:
                    return result
                return snapshot
            except Exception as error:
                self._remember_action(event, succeeded=False)
                self._event("command", {**event, "ok": False, "startFrame": start_frame,
                            "error": {"code": getattr(error, "code", "command-failed"), "message": str(error)},
                            "receipt": receipt})
                raise
        from .devtools_records import Recording, load_recipe, save_recipe, recording_to_draft
        if op == "record.start":
            if self.recording_active:
                raise DevtoolsError("already-recording", "Stop the current recording before starting another.")
            result = self.worker.call("record.start", {"maxFrames": args["maxFrames"]})
            # The worker keeps the complete semantic trace window. Diagnostic
            # snapshots stay on the existing 1,800-frame memory cap; checked
            # jobs retain every evaluated frame in their compressed stream.
            self.recording = Recording(max_frames=min(args["maxFrames"], 1800), max_events=args["maxEvents"])
            self.recording_active = True
            self._observe(result)
            self.recording.add_snapshot(self.snapshot.get("frame", 0), _recordable_snapshot(self.snapshot))
            return {"recording": True}
        if op == "record.stop":
            if self.worker is not None and self.session["state"] == "ready":
                self._observe(self.worker.call("record.stop"))
            self.recording_active = False
            return {"recording": False}
        if op == "recording.export":
            record = self._export()
            summary = {key: record[key] for key in ("status", "acceptedProof", "mode", "counts", "truncated", "subjects", "definiteFailures")}
            return {"artifact": self._artifact("recording", record, compress=True), "recording": summary}
        if op == "scenario.draft":
            draft = recording_to_draft(self._export(), args["name"], args["expectation"], args.get("subject"))
            return {"artifact": self._artifact("draft", draft), "draft": draft}
        if op == "recipe.save":
            recipe = args.get("recipe")
            if recipe is None:
                if self.session.get("actionsFailed"):
                    raise DevtoolsError("recipe-failed-history", "Session contains failed commands; review their receipts and supply an explicit recipe.")
                if self.session.get("actionsTruncated"):
                    raise DevtoolsError("recipe-truncated", "Session command history is incomplete; supply an explicit recipe.")
                recipe = {"schemaVersion": 1, "mode": self.session["mode"], "actions": self.actions}
            path = save_recipe(self.root / "tests/overworld/recipes", args["name"], recipe)
            return {"recipe": args["name"], "path": str(path)}
        if op == "recipe.load":
            recipe = load_recipe(self.root / "tests/overworld/recipes", args["name"])
            start = deepcopy(self.start_args)
            self._stop()
            self._start({**start, "mode": recipe["mode"]})
            self.start_args = start
            self.session["recipe"] = {"name": args["name"], "state": "running", "currentAction": 0,
                                      "completedActions": 0, "totalActions": len(recipe["actions"])}
            self._persist()
            threading.Thread(target=self._execute_recipe, args=(recipe, self.session["id"]), daemon=True).start()
            return {"recipe": deepcopy(self.session["recipe"]), "started": True}
        raise ValueError("unknown operation")


_services = {}
_services_lock = threading.Lock()


def get_service(root):
    key = str(Path(root).resolve())
    with _services_lock:
        if key not in _services:
            _services[key] = Service(key)
            atexit.register(_services[key]._stop)
        return _services[key]
