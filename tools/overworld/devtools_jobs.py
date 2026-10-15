"""Bounded test jobs over the SAME shared devtools session and commands.

No emulator, subprocess, arbitrary code, or alternative input driver lives here.
Status and cancellation use a separate short lock, never the worker-call lock.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import shutil
import threading
import time
import uuid

from .devtools_test_contract import (
    TestEvaluator, validate_test, ROUTE_CONTROL, CHAIN_RETRY, ACCELERATION,
    RAW_BOUNDARY_MEASUREMENTS, TURN_SKID, SPAWN_WORK_BUDGET,
    UNMOUNTED_ZERO_STUTTER,
    PLAYER_HEALTH_ZERO_LOAD, DISTANCE_KINDS,
    RAM_BRIEF_NOTICE,
)

RAW_BOUNDARY_READERS = RAW_BOUNDARY_MEASUREMENTS | {"route30-sentret-throw-pacing-v1", "population-headroom-v1", "emote-three-slots-v1", ACCELERATION, "follower-throw-approach-cargo-v1", "follower-throw-query-priority-v1", "wild-throw-ground-lock-soak-v1"}


def _valid_completed_frame_batch(requested, completed, samples, allow_extra=False):
    if type(completed) is not int or completed < requested or len(samples) != completed:
        return False
    return completed == requested or allow_extra or (
        all(isinstance(sample, dict) for sample in samples)
        and any(sample.get("fieldAvailable") is False for sample in samples))


def _uncredited_dense_wait(phase, action, evaluator):
    if phase == "setup":
        return action["op"] == "wait" and evaluator.uses_raw_records
    return (phase == "observe" and action["id"] == "route29-current-follower"
        and action["op"] == "wait" and evaluator.uses_raw_records
        and evaluator.test["id"] == "population.failed-series-retry"
        and "natural-refill-retry-v1" in evaluator.measurements
        and action["args"] == dict(predicate=dict(kind="follower-settled", species=56, partySlot=2, when="final")))


def _walk_matrix_args(evaluator, subject, snapshot):
    method = evaluator.turn_skid_args if TURN_SKID in evaluator.measurements \
        else evaluator.matrix_args
    return method(subject, snapshot)
from .devtools_test_efficiency import setup_efficiency_report
from .devtools_manifest_limits import MANIFEST_MAX_BYTES
from .devtools_evidence_stream import open_observations
from .devtools_contract import PREPARED_OPS
from .runs import file_record, source_record


def _require_evidence_space(path, *, starting=False):
    """Keep room for failure evidence; never prune user or test files here.

    This is a safety floor, not a promise that other processes cannot fill the
    disk. Check outside native timing before boot and at progress boundaries.
    """
    required = (1024 if starting else 192) * 1024 * 1024
    free = shutil.disk_usage(path).free
    if free < required:
        raise ValueError(f"test-storage-low: {free} bytes free; {required} bytes required "
                         "to retain test evidence. No files were deleted.")


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_json(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"


def _command_snapshot(op, receipt, current):
    # The control receipt is one native observation. The UI cache can also
    # hold older optional terrain diagnostics; these are not part of that
    # exact boundary and cannot be substituted into its proof record.
    return deepcopy(receipt["snapshot"] if op in ("chain-retry", "acceleration.begin", "notice-hop.prepare", "appearance-line.prepare", "held-throw-pocket.prepare", "held-throw-line.prepare") else current)


def _bind_snapshot(service, evaluator, action, phase, current):
    # Only this high-before-capture fixture needs a fresh terrain witness after
    # neutral setup frames. The ordinary bind remains a cached completed read.
    if (phase != "setup" or action["id"] != "bind-mankey"
            or "follower-throw-target-below-v1" not in evaluator.measurements):
        return current
    with service.lock:
        fresh = service.worker.call("snapshot", {"radius": 7})
        keys = ("frame", "nativeCycle", "actorFrame", "context", "fieldControl",
                "actors", "player", "pokemonCombat", "fieldAvailable",
                "observationBoundary", "romSha256")
        if (any(type(fresh.get(k)) is not int for k in ("frame", "nativeCycle", "actorFrame"))
                or any(k not in current or k not in fresh or current[k] != fresh[k] for k in keys)):
            raise ValueError("signed-height Below bind snapshot changed its completed owner boundary")
        terrain = fresh.get("terrain", {}).get("observation", {})
        if (terrain.get("nativeCycle") != fresh["nativeCycle"]
                or terrain.get("lastCompletedGameFrame") != fresh["frame"]
                or terrain.get("context") != fresh["context"]):
            raise ValueError("signed-height Below bind snapshot lacks fresh native support")
        service._observe(fresh)
    return deepcopy(fresh)


def _guard_manifest_size(record, mode):
    """Never publish a control proof that its dependent reader cannot load.

    Retain the entire oversized failed record. This is a publication failure,
    not permission to trim native observations or change a gameplay verdict.
    """
    if mode != "observer-control" or record.get("acceptedProof") is not True:
        return
    size = len(_manifest_json(record).encode("utf-8"))
    if size > MANIFEST_MAX_BYTES:
        record.update(state="failed", passed=False, acceptedProof=False,
            manifestSizeFailure={"code": "manifest-size-limit", "actualBytes": size,
                                 "maximumBytes": MANIFEST_MAX_BYTES, "serialization": "compact-json-utf8"},
            nextAction="Control proof exceeds the shared manifest read limit. Full failure evidence is retained; do not accept this run.")
        record["proofAcceptance"] = {**record.get("proofAcceptance", {}), "eligible": False,
            "reason": "serialized observer-control manifest exceeds the shared read limit"}


def _write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(_manifest_json(value), encoding="utf-8")
    temporary.replace(path)


def _name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", name) or ".." in name:
        raise ValueError("test name must use lowercase letters, digits, dot, dash or underscore")
    return name


class TestJobs:
    CHUNK_FRAMES = 8

    def __init__(self, service):
        self.service = service
        self.lock = threading.RLock()
        self.current = None
        self.cancel_event = threading.Event()
        self.thread = None

    @property
    def directory(self):
        return self.service.root / "tests/overworld/test-recipes"

    def catalog(self):
        tests = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                test = self.load(path.stem)
                tests.append({"id": test["id"], "title": test["title"], "mode": test["mode"],
                              "budgets": test["budgets"], "requirements": test["requirements"], "valid": True,
                              "setupEfficiency": setup_efficiency_report(test)})
            except (ValueError, OSError) as error:
                tests.append({"id": path.stem, "valid": False, "error": str(error)})
        return {"tests": tests, "execution": "shared-devtools"}

    def load(self, name):
        path = self.directory / (_name(name) + ".json")
        if path.is_symlink():
            raise ValueError("test recipes must be regular source files, not links")
        if not path.is_file():
            raise ValueError("test recipe is missing; create and validate it before execution")
        if path.stat().st_size > 262144:
            raise ValueError("test recipe exceeds 256 KiB")
        test = validate_test(json.loads(path.read_text()))
        if test["id"] != name:
            raise ValueError("test ID must match its source filename")
        return test

    def save(self, name, value):
        test = validate_test(value)
        if test["id"] != _name(name):
            raise ValueError("test ID must match its source filename")
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / (name + ".json")
        with path.open("x") as stream:
            stream.write(json.dumps(test, indent=2) + "\n")
        return {"path": str(path), "test": name, "acceptedProof": False}

    def active(self):
        with self.lock:
            return self.current is not None and self.current["state"] in ("starting", "running", "canceling")

    def status(self, run_id=None):
        with self.lock:
            if run_id is not None and (self.current is None or run_id != self.current["runId"]):
                if not isinstance(run_id, str) or not re.fullmatch(r"test-[0-9a-f]{32}", run_id):
                    raise ValueError("invalid test run ID")
                parent = self.service.root / "build/overworld-devtools"
                path = parent / run_id / "manifest.json"
                if path.is_symlink() or not path.resolve().is_relative_to(parent.resolve()) or not path.is_file():
                    raise ValueError("unknown test run")
                if path.stat().st_size > MANIFEST_MAX_BYTES:
                    raise ValueError("saved manifest exceeds its read limit")
                saved = json.loads(path.read_text())
                if saved.get("runId") != run_id or saved.get("execution") != "shared-devtools":
                    raise ValueError("saved manifest identity differs")
                saved["historical"] = True
                if saved.get("state") in ("starting", "running", "canceling"):
                    saved.update(state="interrupted", passed=False, acceptedProof=False,
                                 nextAction="The recorded job has no live owner in this service. Retain its incomplete evidence; it cannot pass.")
                return saved
            if self.current is None:
                return {"state": "idle", "execution": "shared-devtools", "acceptedProof": False}
            result = deepcopy(self.current)
            if result["state"] in ("starting", "running", "canceling"):
                result["elapsedSeconds"] = round(time.monotonic() - result.pop("clockStarted"), 3)
            else:
                result.pop("clockStarted", None)
            return result

    def cancel(self, run_id):
        with self.lock:
            if self.current is None or run_id != self.current["runId"]:
                raise ValueError("cancellation requires the exact current test run ID")
            if self.active():
                self.cancel_event.set()
                self.current.update(state="canceling", nextAction="Waiting for the current bounded command to return; no further input will run.")
            return self.status(run_id)

    def start(self, name):
        test = self.load(name)
        efficiency = setup_efficiency_report(test)
        if any(warning["code"] == "avoidable-dialogue-setup" for warning in efficiency["warnings"]):
            raise ValueError("avoidable test setup: use checked party/follower setup for cadence; "
                             "nurse/dialogue input belongs in healing or selection tests")
        if self.active():
            raise ValueError("a test is active; inspect or cancel that exact run first")
        if self.service.worker is not None:
            raise ValueError("a live session exists; stop only your owned session before a fresh test")
        _require_evidence_space(self.service.root, starting=True)
        run_id = "test-" + uuid.uuid4().hex
        directory = self.service.root / "build/overworld-devtools" / run_id
        directory.mkdir(parents=True, exist_ok=False)
        with self.lock:
            self.cancel_event = threading.Event()
            self.current = {"runId": run_id, "test": name, "state": "starting", "phase": "boot",
                            "execution": "shared-devtools", "acceptedProof": False, "passed": False,
                            "clockStarted": time.monotonic(), "elapsedSeconds": 0,
                            "action": None, "completedActions": 0,
                            "totalActions": len(test["setup"]) + len(test["actions"]),
                            "observedFrames": 0, "nativeCycles": 0, "subjects": [],
                            "budgets": test["budgets"], "lastProgressFrame": 0,
                            "setupEfficiency": efficiency,
                            "manifest": str(directory / "manifest.json"),
                            "nextAction": "Booting one private session from copies of the declared ROM and save."}
        try:
            _write(directory / "test.json", test)
            _write(directory / "manifest.json", self.status())
            self.thread = threading.Thread(target=self._execute, args=(test, directory), daemon=True)
            self.thread.start()
        except Exception as error:
            with self.lock:
                self.current.update(state="failed", passed=False, acceptedProof=False,
                                    evidenceWriteError=str(error), nextAction="Fix the artifact write failure before a new run.")
            raise
        return self.status()

    def _publish(self, directory, **values):
        _require_evidence_space(directory)
        with self.lock:
            self.current.update(values)
            result = self.status()
        _write(directory / "progress.json", result)

    def _limit(self, test, started, action=None, action_started=None):
        if self.cancel_event.is_set():
            raise RuntimeError("test-canceled")
        now = time.monotonic()
        if now - started >= test["budgets"]["maxSeconds"]:
            raise RuntimeError("test-wall-budget")
        if action and now - action_started >= action["budget"]["maxSeconds"]:
            raise RuntimeError("action-wall-budget")

    def _command(self, op, args):
        with self.service.lock:
            return self.service._dispatch(op, args, retain_worker_receipt=op in PREPARED_OPS)

    def _spawn_after_busy_queue(self, op, args, phase, action, test, started, action_start, stream, evaluator):
        """One prepared spawn; a busy native queue gets retained neutral frames and a repeat.

        The refused request changed no game state, but native cycles ran. Its
        events and a fresh completed boundary are retained so the next raw chunk
        continues exactly. Any other failure ends the job as before.
        """
        from .devtools_population_headroom_measurement import (
            FULL_CODE, FULL_MESSAGE, SPAWN_RETRY_FRAMES, STARTUP_CODE, STARTUP_MESSAGE,
            refusal_of, spawn_with_neutral_retry)

        def busy_refusal(error):
            self._limit(test, started, action, action_start)
            with self.service.lock:
                fresh = self.service.worker.call("snapshot", {})
                self.service._observe(fresh)
            refused = {"phase": phase, "action": action["id"], "command": "spawn-refused",
                       "receipt": {"code": refusal_of(error)[0], "message": refusal_of(error)[1],
                                   "events": deepcopy((getattr(error, "details", None) or {})
                                                      .get("preparedRetainedEvents", []))},
                       "snapshot": deepcopy(fresh)}
            stream.write(_manifest_json(refused)); stream.flush()
            if evaluator.observe_record(refused)["state"] == "failed":
                raise RuntimeError("spawn-refusal-observation-failed")

        def neutral_retry_frames():
            self._limit(test, started, action, action_start)
            step_args = {"frames": SPAWN_RETRY_FRAMES, "keys": [],
                         "releaseAtEnd": False, "diagnosticDetails": False}
            with self.service.lock:
                result = self.service.worker.call("step", step_args)
                self.service._observe(result)
            raw = {key: value for key, value in result.items() if key != "snapshot"}
            row = dict(raw, phase=phase, action=action["id"], requestedInput=deepcopy(step_args))
            stream.write(_manifest_json(row)); stream.flush()
            if not _valid_completed_frame_batch(
                    SPAWN_RETRY_FRAMES, result.get("completedGameFrames"), result.get("samples", [])):
                raise RuntimeError("incomplete-frame-evidence")
            if evaluator.observe_record(row)["state"] == "failed":
                raise RuntimeError("spawn-retry-observation-failed")
            self._limit(test, started, action, action_start)

        def population_full(error):
            # Refused before any native work: the six regular slots are occupied.
            self._limit(test, started, action, action_start)
            with self.service.lock:
                fresh = self.service.worker.call("snapshot", {})
                self.service._observe(fresh)
            return {"populationFull": True, "code": FULL_CODE, "message": FULL_MESSAGE,
                    "events": deepcopy((getattr(error, "details", None) or {})
                                       .get("preparedRetainedEvents", [])),
                    "snapshot": deepcopy(fresh)}

        def startup_skipped(error):
            # The native finalize found no startup for this tile in bounded tries.
            full = population_full(error)
            return {"startupSkipped": True, "code": STARTUP_CODE, "message": STARTUP_MESSAGE,
                    "events": full["events"], "snapshot": full["snapshot"]}

        return spawn_with_neutral_retry(lambda: self._command(op, args), busy_refusal,
                                        neutral_retry_frames, population_full, startup_skipped)

    def _failure_bundle(self, directory, error):
        details = {"captureErrors": [], "commandError": {"code": getattr(error, "code", type(error).__name__),
                   "message": str(error), "details": deepcopy(getattr(error, "details", None))}}
        with self.service.lock:
            details["lastSnapshot"] = deepcopy(self.service.snapshot)
            if self.service.worker is not None:
                try:
                    details["native"] = self.service.worker.call("diagnostics")
                except Exception as error:
                    details["captureErrors"].append(str(error))
            details["lastError"] = deepcopy(self.service.last_error)
        _write(directory / "failure.json", details)
        return {"path": str(directory / "failure.json"), "sha256": _hash(directory / "failure.json")}

    def _execute(self, test, directory):
        evaluator = TestEvaluator(test)
        started = time.monotonic()
        owned_session = None
        result, failure = None, None
        fixture_proof = None
        zero_fixture = None
        stream_path = directory / "observations.jsonl.gz"
        frame_count, native_count = 0, 0
        timing = {"observedNativeCycles": 0, "cpuNs": 0, "maximumCycleCpuNs": 0,
                  "wallNs": 0, "clock": "native-cycle", "scope": "measured cost, not a gameplay pass"}
        source_hash = None
        control_cleanup = None
        chain_retry_cleanup = None
        session_cleanup = None
        observation_setup = None
        save_reloads = []
        height_control = any(m["kind"] == "live-spawn-height-control-v1" for m in test.get("measurements", []))
        route_control = any(m["kind"] == ROUTE_CONTROL for m in test.get("measurements", []))
        chain_retry = any(m["kind"] == CHAIN_RETRY for m in test.get("measurements", []))
        late_control = route_control or any(m["kind"] == "live-observer-control-v1" for m in test.get("measurements", []))
        control_operation = "route-control" if route_control else "observer-control"
        def close_control(stream=None):
            nonlocal control_cleanup
            with self.service.lock:
                worker = self.service.worker
                deadline, cancel = getattr(worker, "job_deadline", None), getattr(worker, "job_cancel", None)
                # Cancellation stops gameplay, not the bounded restoration of
                # our own one-bit fault. This operation never advances frames.
                worker.job_deadline, worker.job_cancel = time.monotonic() + 5, None
                try:
                    control_cleanup = worker.call(control_operation + ".close")
                    self.service._observe(control_cleanup)
                finally:
                    worker.job_deadline, worker.job_cancel = deadline, cancel
            row = {"phase": "cleanup", "command": control_operation + ".close",
                   "receipt": control_cleanup, "snapshot": deepcopy(control_cleanup.get("snapshot"))}
            encoded = json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
            if stream is not None:
                stream.write(encoded); stream.flush()
            elif stream_path.is_file():
                with open_observations(stream_path, "at") as output:
                    output.write(encoded)
        try:
            source_hash = _hash(self.directory / (test["id"] + ".json"))
            self.service.job_deadline = started + test["budgets"]["maxSeconds"]
            self.service.job_cancel = self.cancel_event
            attempt = {"schemaVersion": 1, "source": source_record(self.service.root),
                       "testSourceSha256": source_hash,
                       "files": {key: file_record(path, self.service.root) for key, path in (
                           ("rom", Path(test["fixture"]["rom"])), ("save", Path(test["fixture"]["save"])),
                           ("debugDescriptor", Path("build/overworld-system.debug.json")))}}
            self._publish(directory, phase="preflight", attemptIdentity=attempt, testSourceSha256=source_hash)
            _write(directory / "manifest.json", self.status())
            if PLAYER_HEALTH_ZERO_LOAD in {item["kind"] for item in test.get("measurements", [])}:
                from .player_health_zero_load_fixture import create_fixture
                zero_fixture = create_fixture(self.service.root / test["fixture"]["save"],
                                              directory / "zero-load-fixture")
            from .devtools_test_inputs import measurement_inputs
            evaluator.install_measurements(measurement_inputs(test, self.service.root))
            self._limit(test, started)
            from .control import prepare_shared_test
            fixture_proof = prepare_shared_test(test, repo=self.service.root,
                                                deadline=self.service.job_deadline, cancel_event=self.cancel_event)
            if fixture_proof.get("passed") is not True:
                raise RuntimeError("fixture-preflight-failed")
            self._limit(test, started)
            normal_baseline = test["mode"] in ("normal", "observer-control") or chain_retry
            record_from_setup = (normal_baseline or evaluator.uses_raw_records
                                 or test["id"] == "spawn.move-entry.arrival"
                                 or bool({"blocked-notice-hop-v1", "throw-notice-walk-commit-v1",
                                          "follower-throw-hit-abort-v1"}.intersection(evaluator.measurements)))
            initial_events = []
            initial_event_start_frame = None
            boot_fixture = {**test["fixture"]}
            if zero_fixture is not None:
                boot_fixture["save"] = str(Path(zero_fixture["fixturePath"]).relative_to(self.service.root))
            self._command("start", {**boot_fixture,
                "mode": "normal" if normal_baseline else "prepared",
                "_spawnHeightControl": height_control})
            owned_session = self.service.session["id"]
            identity = deepcopy(self.service.session["identity"])
            if record_from_setup and zero_fixture is None:
                # Zero-HP Continue is paused in the stock blackout message.
                # The semantic recorder needs a complete field frame, which
                # cannot exist until normal A input resumes this task. Its
                # native task history is already in bootRecovery/preBootFrames
                # and every following step sample, so no recorder is needed.
                with self.service.lock:
                    initial_event_start_frame = self.service.snapshot["frame"]
                    record_args = {"maxFrames": test["budgets"]["maxFrames"]}
                    if any(item["kind"] in ("pokemon-damage-palette-v1", "pokemon-cooldown-palette-v1", "pokemon-ambush-cooldown-palette-v1", "follower-throw-hit-abort-v1")
                           for item in test.get("measurements", [])):
                        record_args["appearancePalette"] = True
                    if any(item["kind"] == "actor-binding-context-v1" for item in test.get("measurements", [])):
                        record_args["bindingContext"] = True
                    if any(item["kind"] in ("route30-sentret-throw-pacing-v1", UNMOUNTED_ZERO_STUTTER, "natural-refill-retry-v1", "natural-water-spawn-v1", "held-throw-search-v1", "follower-throw-moving-cargo-v1", "follower-throw-away-non45-v1", "follower-throw-approach-cargo-v1", "follower-throw-player-damage-v1", "follower-throw-query-priority-v1", "wild-throw-ground-lock-soak-v1", "throw-cargo-competition-v1", "throw-cargo-retarget-v1", "throw-mutual-pickup-v1", "follower-ram-pokemon-v1", "basic-attack-v1", "wild-throw-moving-candidate-v1", "throw-notice-walk-commit-v1", "follower-throw-hit-abort-v1", "player-health-throw-contact-v1", "throw-cargo-flee-v1", "follower-throw-target-above-v1", "follower-throw-target-below-v1", "follower-target-access-signpost-v1", "follower-target-access-ground-v1", "player-health-mounted-throw-v1", *DISTANCE_KINDS) for item in test.get("measurements", [])):
                        record_args["throwInteractions"] = True
                    if test["id"] == "spawn.move-entry.arrival":
                        record_args["throwInteractions"] = True
                    record_started = self.service.worker.call("record.start", record_args)
                    self.service._observe(record_started)
                    initial_events = record_started.get("events", [])
            if evaluator.uses_raw_records:
                initial_record = {"phase": "setup", "initialSnapshot": deepcopy(self.service.snapshot)}
                if zero_fixture is not None:
                    initial_record["zeroLoadFixture"] = deepcopy(zero_fixture)
                if RAW_BOUNDARY_READERS.intersection(evaluator.measurements):
                    initial_record.update(initialEvents=initial_events, initialEventStartFrame=initial_event_start_frame)
                evaluator.observe_record(initial_record)
            elif {"actor-binding-context-v1", "live-spawn-height-control-v1"}.intersection(
                    evaluator.measurements):
                evaluator.observe_initial(deepcopy(self.service.snapshot), initial_events,
                                          start_frame=initial_event_start_frame)
            else:
                evaluator.observe(deepcopy(self.service.snapshot), count_frame=False)
            self._publish(directory, state="running", sessionId=owned_session, identity=identity)
            # Each chunk is written before another action. A failed/closed
            # worker cannot erase prior progress or turn missing frames green.
            with open_observations(stream_path, "xt") as stream:
                initial_row = {"phase": "setup", "initialSnapshot": self.service.snapshot}
                if zero_fixture is not None:
                    initial_row["zeroLoadFixture"] = deepcopy(zero_fixture)
                if ({"actor-binding-context-v1", "live-spawn-height-control-v1"}
                        | RAW_BOUNDARY_READERS).intersection(evaluator.measurements):
                    initial_row.update(initialEvents=initial_events, initialEventStartFrame=initial_event_start_frame)
                stream.write(_manifest_json(initial_row))
                stream.flush()
                if evaluator.result()["state"] == "failed": raise RuntimeError("initial-observation-failed")
                for phase, actions in (("setup", test["setup"]), ("observe", test["actions"])):
                    if phase == "observe":
                        with self.service.lock:
                            if not self.service.session or self.service.session["id"] != owned_session:
                                raise RuntimeError("observation-prepare-session-ownership")
                            observation_args = {}
                            if "pokemon-cooldown-palette-v1" in evaluator.measurements:
                                observation_args["appearanceSubject"] = evaluator.subjects["onix"]
                            if "pokemon-ambush-cooldown-palette-v1" in evaluator.measurements:
                                observation_args["appearanceSubject"] = evaluator.subjects["weepinbell"]
                            if "follower-throw-hit-abort-v1" in evaluator.measurements:
                                observation_args["appearanceSubject"] = evaluator.subjects["mankey"]
                            observation_setup = self.service.worker.call("observation.prepare", observation_args)
                            if {SPAWN_WORK_BUDGET, UNMOUNTED_ZERO_STUTTER}.intersection(
                                    evaluator.measurements):
                                observation_setup["mainLoopPacing"] = self.service.worker.call(
                                    "main-loop-pacing.arm", {"maxFrames": test["budgets"]["maxFrames"]})
                            if "spawnObserverCost" in test:
                                observation_setup["spawnObserverCost"] = self.service.worker.call(
                                    "spawn-cost.probe", {"mode": test["spawnObserverCost"]})
                    if phase == "observe" and not record_from_setup:
                        with self.service.lock:
                            start_frame = self.service.snapshot["frame"]
                            record_args = {"maxFrames": test["budgets"]["maxFrames"]}
                            if test["id"] == "mount.begin-current-follower":
                                record_args["roleProfile"] = True
                            if {"ram-until-crash-v1", "ram-behind-entry-v1", "ram-ledge-continuity-v1", "ram-brief-notice-v1"}.intersection(evaluator.measurements):
                                record_args["appearancePalette"] = True
                            started_record = self.service.worker.call("record.start", record_args)
                            self.service._observe(started_record)
                            if {"ram-until-crash-v1", "ram-behind-entry-v1", "ram-ledge-continuity-v1", "ram-brief-notice-v1"}.intersection(evaluator.measurements):
                                self.service.worker.call("observation.prepare", {
                                    "appearanceSubject": evaluator.subjects["onix"]})
                        boundary = deepcopy(self.service.snapshot)
                        boundary_row = {"phase": phase, "boundarySnapshot": boundary}
                        if test["id"] == "mount.begin-current-follower":
                            boundary_row.update(startEvents=started_record["events"], startFrame=start_frame)
                        stream.write(_manifest_json(boundary_row))
                        stream.flush()
                        if test["id"] == "mount.begin-current-follower":
                            evaluator.observe_start_boundary(boundary, started_record["events"], start_frame=start_frame)
                            if evaluator.result()["state"] == "failed": raise RuntimeError("start-boundary-invalid")
                        elif boundary["frame"] > evaluator.latest["frame"]:
                            evaluator.observe(boundary, count_frame=False)
                    for action in actions:
                        if action.get("skipIf") and evaluator.check(action["skipIf"], self.service.snapshot):
                            skipped = {"phase": phase, "action": action["id"], "command": "skip", "snapshot": self.service.snapshot}
                            stream.write(json.dumps(skipped, separators=(",", ":"), allow_nan=False) + "\n")
                            stream.flush()
                            if evaluator.uses_raw_records and evaluator.observe_record(skipped)["state"] == "failed":
                                raise RuntimeError("setup-skip-observation-failed")
                            self._publish(directory, completedActions=self.current["completedActions"] + 1)
                            continue
                        self._limit(test, started)
                        self._publish(directory, phase=phase, action=action["id"], nextAction="Running this bounded action; inspect or cancel by run ID.")
                        action_start, action_frames = time.monotonic(), 0
                        self.service.worker.job_deadline = min(started + test["budgets"]["maxSeconds"], action_start + action["budget"]["maxSeconds"])
                        before = deepcopy(self.service.snapshot)
                        last_progress = before.get("frame", 0)
                        progress_key = self._progress_key(action, before, evaluator)
                        progress_budget = min(action["budget"]["noProgressFrames"], test["budgets"]["noProgressFrames"])

                        def check_progress(sample, current_evaluator):
                            nonlocal progress_key, last_progress
                            key = self._progress_key(action, sample, current_evaluator)
                            if key != progress_key:
                                progress_key, last_progress = key, sample["frame"]
                            if sample["frame"] - last_progress >= progress_budget:
                                # A true stop condition on this exact frame is
                                # completion, even if only a ready bit changed.
                                predicate = action["args"].get("predicate", action["args"].get("until"))
                                if predicate and current_evaluator.check(predicate, sample):
                                    return
                                # A fixed-length step also completes on its
                                # exact final frame. Its next action can change
                                # input after a bounded stationary hold.
                                if action["op"] == "step" and not predicate \
                                        and action_frames >= action["args"]["frames"]:
                                    return
                                raise RuntimeError("no-progress: " + action["id"])

                        while True:
                            self._limit(test, started, action, action_start)
                            op, args = action["op"], action["args"]
                            snapshot = deepcopy(evaluator.latest if RAW_BOUNDARY_READERS.intersection(evaluator.measurements) else self.service.snapshot)
                            if op == "bind":
                                snapshot = _bind_snapshot(self.service, evaluator, action, phase, snapshot)
                                receipt = evaluator.bind(args["subject"], snapshot)
                                bound_record = {"phase": phase, "action": action["id"], "command": "bind", "receipt": receipt, "snapshot": snapshot}
                                stream.write(_manifest_json(bound_record))
                                stream.flush()
                                if evaluator.uses_raw_records and evaluator.observe_record(bound_record)["state"] == "failed":
                                    raise RuntimeError("binding-observation-failed")
                                break
                            if op in ("wait", "assert") and evaluator.check(args["predicate"], snapshot):
                                break
                            if op == "step" and args.get("until") and evaluator.check(args["until"], snapshot):
                                break
                            if op == "assert":
                                raise RuntimeError("assertion-failed: " + action["id"])
                            if op not in ("step", "wait"):
                                if op == "save.reload":
                                    receipt = self._command(op, args)
                                    owned_session = self.service.session["id"]
                                    loaded_frame = receipt["snapshot"]["frame"]
                                    with self.service.lock:
                                        restarted_record = self.service.worker.call("record.start", {
                                            "maxFrames": test["budgets"]["maxFrames"]})
                                        self.service._observe(restarted_record)
                                    receipt["recordingRestart"] = {"frame": self.service.snapshot["frame"],
                                        "nativeCycle": self.service.snapshot["nativeCycle"],
                                        "advancedGameFrames": self.service.snapshot["frame"] - loaded_frame,
                                        "eventCount": len(restarted_record.get("events", []))}
                                    receipt["snapshot"] = deepcopy(self.service.snapshot)
                                    save_reloads.append(deepcopy(receipt["saveReload"]))
                                    self._publish(directory, sessionId=owned_session,
                                                  reloadIdentity=deepcopy(self.service.session["identity"]))
                                elif op == "crash.arm":
                                    receipt = self._command(op, evaluator.crash_args(args["subject"], snapshot))
                                elif op == "walk-matrix.arm":
                                    receipt = self._command(op, _walk_matrix_args(
                                        evaluator, args["subject"], snapshot))
                                elif op == "stomp.arm":
                                    receipt = self._command(op, evaluator.stomp_args(args["subject"], snapshot))
                                elif op in ("walk-corner.arm", "walk-corner.probe"):
                                    receipt = self._command(op, evaluator.corner_args(args["subject"], snapshot, probe=op.endswith("probe")))
                                elif op == "walk-corner.recovery":
                                    receipt = {"snapshot": deepcopy(snapshot), "advancedFrames": 0, "acceptedProof": False}
                                elif op == "wild-walk.arm":
                                    receipt = self._command(op, evaluator.wild_walk_args(args["subject"], snapshot))
                                elif op == "wild-ledge.arm":
                                    receipt = self._command(op, evaluator.wild_ledge_args(args["subject"], snapshot))
                                elif op == "condition-controller.arm":
                                    receipt = self._command(
                                        op, evaluator.condition_controller_args(
                                            args["subject"], snapshot))
                                elif op == "mount-pacing.arm":
                                    receipt = self._command(op, evaluator.mount_pacing_args(args["subject"], snapshot))
                                elif op == "mount-pacing.recovery":
                                    # This marks a measurement window only. No guest command or clock advance.
                                    receipt = {"snapshot": deepcopy(snapshot), "advancedFrames": 0, "acceptedProof": False}
                                elif op == "walk-policy-control.arm":
                                    receipt = self._command(op, evaluator.walk_policy_control_args(args["subject"], snapshot))
                                elif op == "walk-policy-control.close":
                                    receipt = self._command(op, args)
                                elif op == "appearance-line.prepare":
                                    from tools.overworld.devtools_appearance_measurement import COOLDOWN, AMBUSH_COOLDOWN, prepare_current_line
                                    def line_command(command, command_args):
                                        if command != "step":
                                            return self._command(command, command_args)
                                        self._limit(test, started, action, action_start)
                                        with self.service.lock:
                                            result = self.service.worker.call("step", command_args)
                                            self.service._observe(result)
                                        raw = {key:value for key,value in result.items() if key != "snapshot"}
                                        row = dict(raw, phase="observe", action=action["id"],
                                                   requestedInput=deepcopy(command_args))
                                        stream.write(_manifest_json(row)); stream.flush()
                                        if evaluator.observe_record(row)["state"] == "failed":
                                            raise RuntimeError("current-line-normal-input-observation-failed")
                                        self._limit(test, started, action, action_start)
                                        return result
                                    receipt = prepare_current_line(line_command, snapshot,
                                        evaluator.subjects[args["subject"]], evaluator.measurements[AMBUSH_COOLDOWN if args["subject"] == "weepinbell" else COOLDOWN])
                                elif op in ("held-throw-pocket.prepare", "held-throw-line.prepare"):
                                    from tools.overworld.devtools_held_throw_search_measurement import KIND, prepare_pocket, prepare_line
                                    def held_command(command, command_args):
                                        self._limit(test, started, action, action_start)
                                        if command != "step":
                                            return self._command(command, command_args)
                                        with self.service.lock:
                                            result = self.service.worker.call("step", command_args)
                                            self.service._observe(result)
                                        raw = {key:value for key,value in result.items() if key != "snapshot"}
                                        row = dict(raw, phase=phase, action=action["id"], requestedInput=deepcopy(command_args))
                                        stream.write(_manifest_json(row)); stream.flush()
                                        if evaluator.observe_record(row)["state"] == "failed":
                                            raise RuntimeError("held-throw-normal-input-observation-failed")
                                        self._limit(test, started, action, action_start)
                                        return result
                                    prepare = prepare_pocket if op == "held-throw-pocket.prepare" else prepare_line
                                    receipt = prepare(held_command, snapshot, evaluator.measurements[KIND])
                                elif op == "notice-hop.prepare":
                                    from tools.overworld.devtools_blocked_notice_hop_measurement import KIND, prepare_neighbor
                                    def notice_command(command, command_args):
                                        if command != "step":
                                            return self._command(command, command_args)
                                        with self.service.lock:
                                            result = self.service.worker.call("step", command_args)
                                            self.service._observe(result)
                                            return result
                                    receipt = prepare_neighbor(notice_command, snapshot,
                                        evaluator.subjects[args["subject"]], evaluator.measurements[KIND],
                                        trace_sequences=evaluator.last_sequence)
                                elif op == "acceleration.begin":
                                    reset_args = evaluator.acceleration_begin_args(args["subject"], snapshot)
                                    receipt = self._command("walk-policy.reset", reset_args)
                                elif op == "acceleration.end":
                                    receipt = evaluator.acceleration_end_receipt(args["subject"], snapshot)
                                elif op == "spawn" and "population-headroom-v1" in evaluator.measurements:
                                    receipt = self._spawn_after_busy_queue(
                                        op, args, phase, action, test, started, action_start, stream, evaluator)
                                elif op == "walk-intent.arm":
                                    receipt = self._command(op, evaluator.walk_intent_args(args, snapshot))
                                elif op == "walk-intent.close":
                                    receipt = self._command(op, args)
                                elif op == "obstacle-intent.arm":
                                    receipt = self._command(op, evaluator.obstacle_intent_args(args, snapshot))
                                elif op == "obstacle-intent.close":
                                    receipt = self._command(op, args)
                                elif op == "chain-retry":
                                    control_args = evaluator.chain_retry_args(args["subject"])
                                    with self.service.lock:
                                        receipt = self.service.worker.call("chain-retry.arm", control_args)
                                        self.service._observe(receipt)
                                elif op == "observer-control":
                                    # The evaluator must freeze a passing natural
                                    # baseline and approve this exact subject and
                                    # fault before the worker can be armed.
                                    control_args = evaluator.observer_control_args(args["subject"], args["fault"])
                                    with self.service.lock:
                                        receipt = self.service.worker.call(control_operation + ".arm", control_args)
                                        self.service._observe(receipt)
                                else:
                                    if op == "emote-three.arm":
                                        args = {name: evaluator.subjects[name]["handle"]["value"] for name in "abcd"}
                                    elif op == "actor-inspect.probe":
                                        args = evaluator.actor_inspect_args(args["subject"], snapshot)
                                    elif op == "walk-policy.reset":
                                        args = evaluator.walk_reset_args(args["subject"], snapshot)
                                    elif op == "mount-walk.configure":
                                        args = evaluator.mount_walk_fixture_args(args, snapshot)
                                    elif op == "mount-teleport.configure":
                                        args = evaluator.mount_teleport_fixture_args(args, snapshot)
                                    elif op == "mount-teleport.restore":
                                        args = evaluator.mount_teleport_restore_args(args, snapshot)
                                    receipt = self._command(op, args)
                                # The read-only HP receipt has no snapshot and
                                # does not advance this exact completed boundary.
                                endpoint = (deepcopy(snapshot) if op in ("player-health.observe", "acceleration.end", "walk-intent.close", "obstacle-intent.close", "walk-policy-control.close", "mount-pacing.close", "wild-walk.close", "wild-ledge.close", "condition-controller.close", "walk-corner.close", "walk-matrix.close", "stomp.close", "main-loop-pacing.arm", "cpu-work.start", "cpu-work.read") else
                                            deepcopy(receipt["snapshot"]) if RAW_BOUNDARY_READERS.intersection(evaluator.measurements) else
                                            _command_snapshot(op, receipt, self.service.snapshot))
                                command_record = {"phase": phase, "action": action["id"], "command": op,
                                                  "receipt": receipt, "snapshot": endpoint}
                                stream.write(_manifest_json(command_record))
                                stream.flush()
                                if op == "chain-retry":
                                    if evaluator.measurements[CHAIN_RETRY].observe_control(receipt, endpoint)["state"] == "failed":
                                        raise RuntimeError("chain-retry-arm-observation-failed")
                                action_frames = (endpoint["frame"] if op == "save.reload"
                                                 else endpoint["frame"] - before["frame"])
                                frame_count += action_frames
                                if action_frames < 0 or action_frames > action["budget"]["maxFrames"]:
                                    raise RuntimeError("action-frame-budget: " + action["id"])
                                if frame_count > test["budgets"]["maxFrames"]:
                                    raise RuntimeError("test-frame-budget")
                                self._limit(test, started, action, action_start)
                                if op == "save.reload":
                                    observed = (evaluator.observe_record(command_record)
                                                if evaluator.uses_raw_records else
                                                evaluator.observe_save_reload(receipt))
                                    if observed["state"] == "failed":
                                        raise RuntimeError("save-reload-observation-failed")
                                elif evaluator.uses_raw_records:
                                    if evaluator.observe_record(command_record)["state"] == "failed":
                                        raise RuntimeError("prepared-setup-observation-failed")
                                elif ((op in ("party", "spawn", "notice-hop.prepare")
                                       or (op == "teleport" and {"throw-notice-walk-commit-v1",
                                            "follower-throw-hit-abort-v1"}.intersection(evaluator.measurements)))
                                      and "setupBoundary" in receipt):
                                    if evaluator.observe_prepared_command(command_record)["state"] == "failed":
                                        raise RuntimeError("prepared-setup-observation-failed")
                                elif op == "terrain" and RAM_BRIEF_NOTICE in evaluator.measurements:
                                    if evaluator.observe_brief_terrain(command_record)["state"] == "failed":
                                        raise RuntimeError("brief-ram-terrain-observation-failed")
                                elif endpoint["frame"] > evaluator.latest["frame"]:
                                    evaluator.observe(endpoint, count_frame=False)
                                break
                            remaining = action["budget"]["maxFrames"] - action_frames
                            if op == "step":
                                remaining = min(remaining, args["frames"] - action_frames)
                            if remaining <= 0:
                                if op == "step" and not args.get("until") and action_frames >= args["frames"]:
                                    break
                                raise RuntimeError("action-frame-budget: " + action["id"])
                            remaining = min(remaining, test["budgets"]["maxFrames"] - frame_count)
                            if remaining <= 0:
                                raise RuntimeError("test-frame-budget")
                            count = self._chunk_frames(action, evaluator, remaining, phase)
                            # Never step beyond the earliest possible watchdog
                            # deadline. Progress within this chunk is checked
                            # below, in frame order, not from its final pose.
                            count = min(count, max(1, last_progress + progress_budget - snapshot["frame"]))
                            # The shared step owns exact key-release and coherent
                            # frame sampling; this layer contains no emulator API.
                            command_args = {"frames": count, "keys": args.get("keys", []),
                                "releaseAtEnd": False, "diagnosticDetails": False}
                            with self.service.lock:
                                chunk = self.service.worker.call("step", command_args)
                                self.service._observe(chunk)
                            samples = chunk.get("samples", [])
                            completed = chunk.get("completedGameFrames", 0)
                            # Preserve even a rejected native chunk. An endpoint
                            # alone cannot explain missing/extra frame evidence.
                            retained_chunk = {key: value for key, value in chunk.items() if key != "snapshot"}
                            raw_record = {"phase": phase, "action": action["id"], **retained_chunk,
                                "requestedInput": deepcopy(command_args)}
                            if ((test["id"] == "player-hp.hop-contact" and action["id"] == "wait-crossing-hop")
                                    or (test["id"] == "player-hp.ambush-jump"
                                        and action["id"] == "wait-ambush-contact")
                                    or (test["id"] == "player-hp.running-hit"
                                        and action["id"] == "run-to-contact")
                                    or (test["id"] in ("player-hp.moving-heal-on-foot", "player-hp.moving-heal-mounted")
                                        and action["id"] == "wait-contact")
                                    or (test["id"] in ("pokemon-hp.collision-knockback",
                                                       "pokemon-hp.skid-hit-crash-knockback", "follower.ram-pokemon", "profile.basic-attack", "pokemon-appearance.damage-palette", "wild.throw-cargo-flee", "wild.baby-player-fear", "wild.igglybuff-player-fear-cry", "wild.baby-pokemon-fear", "follower.baby-seek-safety", "profile.playful.in-place-hop", "follower.baby-damage-seek-safety", "wild.damage-flee", "profile.stomp-slam.player-contact", "profile.stomp-slam.mounted-player-contact", "mount.rattata-walking-ledge")
                                        and phase == "observe")):
                                endpoint = chunk["snapshot"]
                                raw_record["profileCache"] = {
                                    "frame": endpoint["frame"], "nativeCycle": endpoint["nativeCycle"],
                                    "resolvedProfiles": endpoint["nativeObservation"]["resolvedProfiles"]}
                            stream.write(json.dumps(raw_record, separators=(",", ":"), allow_nan=False) + "\n")
                            stream.flush()
                            # A neutral setup wait may cross several complete
                            # queues in its final native cycle. Raw meters check
                            # every dense sample and its real cycle ownership.
                            # Input and observation durations remain exact.
                            neutral_setup = _uncredited_dense_wait(phase, action, evaluator)
                            if not _valid_completed_frame_batch(
                                    count, completed, samples, neutral_setup):
                                raise RuntimeError("incomplete-frame-evidence")
                            action_frames += completed
                            frame_count += completed
                            native_count += chunk.get("nativeCycles", 0)
                            if action_frames > action["budget"]["maxFrames"]:
                                raise RuntimeError("action-frame-budget: " + action["id"])
                            for interval in chunk.get("cycleIntervals", []):
                                if type(interval.get("cpuNs")) is not int or type(interval.get("wallNs")) is not int:
                                    raise RuntimeError("invalid-native-timing")
                                timing["observedNativeCycles"] += 1
                                timing["cpuNs"] += interval["cpuNs"]
                                timing["wallNs"] += interval["wallNs"]
                                timing["maximumCycleCpuNs"] = max(timing["maximumCycleCpuNs"], interval["cpuNs"])
                            if frame_count > test["budgets"]["maxFrames"]:
                                raise RuntimeError("test-frame-budget")
                            by_frame = {}
                            for event in chunk.get("events", []):
                                by_frame.setdefault(event.get("frame"), []).append(event)
                            if set(by_frame) - {sample.get("frame") for sample in samples}:
                                raise RuntimeError("event-outside-observed-frames")
                            if evaluator.uses_raw_records:
                                result = evaluator.observe_record(raw_record, frame_callback=check_progress, full_report=False)
                                if result["state"] == "failed":
                                    raise RuntimeError("observation-failed")
                            else:
                                for sample in samples:
                                    result = evaluator.observe(sample, by_frame.get(sample.get("frame"), ()), count_frame=phase == "observe")
                                    if result["state"] == "failed":
                                        raise RuntimeError("observation-failed")
                                    check_progress(sample, evaluator)
                            current = deepcopy(self.service.snapshot)
                            self._publish(directory, observedFrames=result.get("observedFrames", 0),
                                          nativeCycles=native_count, actionFrames=action_frames,
                                          lastProgressFrame=last_progress, subjects=result.get("subjects", []),
                                          lastObservation={"frame": current.get("frame"), "context": current.get("context"),
                                                           "player": current.get("player")})
                        if action["op"] not in ("crash.calibrate", "crash.close"):
                            with self.service.lock:
                                self.service.worker.job_deadline = started + test["budgets"]["maxSeconds"]
                                self.service.worker.call("release")
                        self._publish(directory, completedActions=self.current["completedActions"] + 1)
                if late_control:
                    close_control(stream)
                    evaluator.observer_control_cleanup(control_cleanup)
            result = evaluator.finish()
            if not result.get("passed"):
                raise RuntimeError("final-assertions-failed")
            if _hash(self.directory / (test["id"] + ".json")) != source_hash:
                raise RuntimeError("test-source-changed")
            for item in identity.get("toolInputs", []):
                if _hash(self.service.root / item["path"]) != item["sha256"]:
                    raise RuntimeError("tool-source-changed")
            for key in ("rom", "save", "debugDescriptor"):
                item = identity.get(key)
                if item and _hash(item["path"]) != item["sha256"]:
                    raise RuntimeError("input-changed")
        except Exception as error:
            result = evaluator.fail(getattr(error, "code", str(error).split(":", 1)[0]), str(error), getattr(error, "details", None))
            try:
                failure = self._failure_bundle(directory, error)
            except Exception as capture_error:
                failure = {"captureError": str(capture_error)}
        finally:
            with self.service.lock:
                if owned_session and self.service.session and self.service.session["id"] == owned_session:
                    if self.service.worker is not None:
                        if chain_retry:
                            worker = self.service.worker
                            deadline, cancel = worker.job_deadline, worker.job_cancel
                            worker.job_deadline, worker.job_cancel = time.monotonic() + 5, None
                            try:
                                chain_retry_cleanup = worker.call("chain-retry.close")
                            except Exception as error:
                                chain_retry_cleanup = {"closed": False, "error": str(error)}
                            finally:
                                worker.job_deadline, worker.job_cancel = deadline, cancel
                        if late_control and control_cleanup is None:
                            try:
                                close_control()
                            except Exception as error:
                                control_cleanup = {"closed": False, "error": str(error)}
                        try:
                            self.service.worker.call("release")
                        except Exception:
                            pass  # Stop still releases the owned core on failure.
                    session_cleanup = self.service._stop()
                self.service.job_deadline = None
                self.service.job_cancel = None
            result = result or {"passed": False, "failures": [{"code": "missing-result"}]}
            # Claim acceptance is separate from successful tool execution.
            # The registry adapter must verify every requirement before credit.
            record = {**self.status(), "state": "canceled" if self.cancel_event.is_set() else "completed" if result.get("passed") else "failed",
                      "passed": bool(result.get("passed")), "acceptedProof": False,
                      "elapsedSeconds": round(time.monotonic() - started, 3),
                      "evaluation": result, "failureArtifact": failure, "visualArtifact": None,
                      "visualArtifactPolicy": "No automatic screenshots; screenshots are not test proof.",
                      "fixtureProof": fixture_proof,
                      **({"zeroLoadFixture": zero_fixture} if zero_fixture is not None else {}),
                      "timing": timing,
                      "sessionCleanup": session_cleanup,
                      **({"chainRetryCleanup": chain_retry_cleanup} if chain_retry else {}),
                      "observationSetup": observation_setup,
                      "saveReloads": save_reloads,
                      **({"observerControlCleanup": control_cleanup} if late_control else {}),
                      "testSourceSha256": source_hash, "totalGameFrames": frame_count,
                      "nextAction": "Review the saved result and exact failure before another run."}
            if stream_path.is_file():
                record["observationsArtifact"] = {"path": str(stream_path), "sha256": _hash(stream_path), "size": stream_path.stat().st_size}
            acceptance_started = time.monotonic()
            record["executionSeconds"] = round(acceptance_started - started, 3)
            try:
                self._publish(directory, phase="acceptance", action=None, acceptedProof=False,
                              executionSeconds=record["executionSeconds"],
                              nextAction="The private game session is stopped. Checking saved memory data; wait for this run's final result.")
                from .control import finalize_shared_test
                record.update(finalize_shared_test(test, record, repo=self.service.root))
                if not record.get("passed") and record["state"] == "completed":
                    record["state"] = "failed"
            except Exception as error:
                record.update(state="failed", passed=False, acceptedProof=False,
                              proofAcceptance={"error": str(error)})
            finally:
                completed_at = time.monotonic()
                # Diagnostic wall time includes controller replay and controls;
                # these fields do not change any proof or game-frame budget.
                record.update(phase="terminal", action=None,
                              proofAcceptanceSeconds=round(completed_at - acceptance_started, 3),
                              elapsedSeconds=round(completed_at - started, 3))
            with self.lock:
                # Cancel may arrive while replay runs after the core stops.
                # Serialize that decision with terminal publication so an
                # acknowledged cancellation cannot become an accepted pass.
                if self.cancel_event.is_set():
                    record.update(state="canceled", passed=False, acceptedProof=False,
                                  nextAction="This run was canceled. Retain its memory data; it is not accepted proof.")
                elif record.get("state") == "completed" and record.get("passed") is True \
                        and record.get("acceptedProof") is True:
                    record["nextAction"] = "Accepted proof is complete. No further action is required for this run."
                elif record.get("passed") is True:
                    record["nextAction"] = "Execution passed, but proof was not accepted. Review proofAcceptance before another run."
                else:
                    record["nextAction"] = "Review the saved result and exact failure before another run."
                try:
                    _guard_manifest_size(record, test["mode"])
                    _write(directory / "manifest.json", record)
                except Exception as error:
                    record.update(state="failed", passed=False, acceptedProof=False,
                                  evidenceWriteError=str(error), nextAction="Final evidence could not be saved; do not accept this run.")
                self.current = record

    @classmethod
    def _chunk_frames(cls, action, evaluator, remaining, phase):
        args = action["args"]
        if action["op"] == "wait":
            # A measurement cannot pass before its bound-frame floor. Batch
            # only that guaranteed-incomplete interval, then return to exact
            # single-frame stopping. Setup and fault-stage waits stay exact.
            floor_left = evaluator.test["budgets"]["minObservedFrames"] - evaluator.frames
            if phase == "observe" and args["predicate"]["kind"] == "measurement-complete" and floor_left > 0:
                return min(cls.CHUNK_FRAMES, remaining, floor_left)
            return 1
        return min(1 if args.get("until") else cls.CHUNK_FRAMES, remaining)

    @staticmethod
    def _progress_key(action, snapshot, evaluator):
        predicate = action["args"].get("predicate", action["args"].get("until", {}))
        if predicate.get("kind") in ("player-settled-at", "player-step-count"):
            player = snapshot.get("player", {})
            # Ready flags and command retries can churn in a control lock.
            # Only travel or a native tile admission extends this deadline.
            return (player.get("pos_x"), player.get("pos_z"),
                    snapshot.get("nativeObservation", {}).get("playerStepCount"))
        if predicate.get("kind") == "party-field":
            return snapshot.get("party")
        if predicate.get("kind") == "selector-field":
            return snapshot.get("selector")
        if predicate.get("kind") in ("measurement-complete", "measurement-stage"):
            measurement = evaluator.measurements.get(predicate["measurement"])
            result = (measurement.progress_result() if predicate["measurement"] in ("unmounted-cadence-v1", "unmounted-game-cadence-v1", ROUTE_CONTROL)
                      else measurement.result()) if measurement else {}
            subject = result.get("subject") or {}
            actor = None
            if (predicate["measurement"] == SPAWN_WORK_BUDGET
                    and predicate.get("kind") == "measurement-stage"
                    and predicate.get("stage") == "complete"
                    and result.get("entry") is not None):
                # This wait follows the created Wild actor. Its saved Follower
                # can be idle while the exact accepted Fly In keeps moving.
                from .devtools_records import select_current_actor
                entry = result["entry"]
                if not isinstance(entry, dict):
                    return ("spawn-work-entry-invalid",)
                subject = {key: entry.get(key) for key in ("handle", "subjectIdentity", "species")}
                subject["role"] = "WILD"
                try:
                    select_current_actor(snapshot, subject)
                except (ValueError, TypeError, KeyError):
                    # Other actors or a changing clock cannot renew this wait.
                    return ("spawn-work-entry-invalid",)
                actor = next(item for item in snapshot["actors"]
                    if item.get("active") is True and item.get("identityVerified") is True
                    and item.get("handle") == subject["handle"])
            if actor is None:
                actor = next((item for item in snapshot.get("actors", []) if item.get("handle") == subject.get("handle")), {})
            engine = actor.get("engineObject") or {}
            # Looking, flags and native command bookkeeping are not motion
            # progress. A stationary pause must still fit the recipe's declared
            # no-progress budget; advancing travel elapsed/position does count.
            return (subject.get("handle"), subject.get("subjectIdentity"), subject.get("species"), subject.get("role"),
                    result.get("completeMotions"), result.get("eligibleMoves"), result.get("spawnPassed"),
                    actor.get("commitSequence"), actor.get("motionPhase"), actor.get("motionElapsed"),
                    engine.get("pos_x"), engine.get("pos_y"), engine.get("pos_z"))
        if action["op"] == "wait" and predicate.get("kind") != "frame-count":
            # A healthy global heartbeat cannot hide a motion/subject wait.
            subject = predicate.get("subject")
            spec = evaluator.specs.get(subject, {})
            bound = evaluator.subjects.get(subject)
            return [(actor.get("handle"), actor.get("commitSequence"), actor.get("logical"),
                     actor.get("motionPhase"), actor.get("motionElapsed"))
                    for actor in snapshot.get("actors", [])
                    if (actor.get("handle") == bound.get("handle") if bound else
                        actor.get("species") == spec.get("species") and actor.get("role") == spec.get("role"))]
        if action["op"] == "step" and action["args"].get("keys"):
            player = snapshot.get("player", {})
            return (player.get("pos_x"), player.get("pos_z"),
                    snapshot.get("nativeObservation", {}).get("playerStepCount"))
        return snapshot.get("frame")

    def export(self, run_id):
        status = self.status(run_id)
        if status["state"] in ("starting", "running", "canceling"):
            raise ValueError("test is still active; read status or cancel it before export")
        path = self.service.root / "build/overworld-devtools" / run_id / "manifest.json"
        return {"artifact": {"path": str(path), "sha256": _hash(path),
                             "url": f"/api/v2/devtools/artifacts/{path.parent.name}/{path.name}"},
                "run": status}
