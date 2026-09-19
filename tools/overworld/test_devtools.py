"""Control-plane tests. Fake worker tests never count as gameplay proof."""
import ast
from collections import deque
import errno
import gzip
import io
import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.overworld.devtools import DevtoolsError, Service, Worker
from tools.overworld import devtools_copy
from tools.overworld.runs import HEADLESS_PYTHON_FLAGS
from tools.overworld.devtools_contract import command_help, validate_command


class FakeWorker:
    instances = []

    def __init__(self, root, directory):
        self.directory = directory
        self.calls = []
        self.closed = False
        self.frame = 0
        self.fail = None
        self.instances.append(self)

    def call(self, op, args=None):
        self.calls.append((op, args))
        if self.fail:
            raise self.fail
        if op == "step":
            self.frame += args["frames"]
        if op == "snapshot.probe":
            return {
                "schemaVersion": 1, "scope": "paused-snapshot-reader-diagnostic",
                "acceptedProof": False, "proofStatus": "diagnostic-only",
                "frame": self.frame, "nativeCycle": self.frame,
                "iterations": args["iterations"], "snapshotsEqual": True,
                "gameClocksUnchanged": True, "snapshotSha256": "a" * 64,
                "snapshotBytes": 128,
                "intervals": [{"cpuNs": 20, "threadCpuNs": 13, "wallNs": 50,
                               "readCalls": 2, "readBytes": 16}] * args["iterations"],
            }
        return {"frame": self.frame, "player": {"map": 34}, "actors": [
            {"handle": {"value": 77}, "species": 165},
        ], "party": [{"slot": 0, "species": 56}]}

    def close(self):
        self.closed = True


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "test.nds").write_bytes(b"copied-rom")
        (self.root / "test.sav").write_bytes(b"source-save")
        self.service = Service(self.root, FakeWorker)

    def tearDown(self):
        self.service._stop()
        self.temp.cleanup()

    def command(self, op, args=None, **extra):
        return self.service.command({"op": op, "args": args or {}, **extra})

    def start(self):
        result = self.command("start")
        self.assertTrue(result["ok"], result)
        return result

    def test_snapshot_probe_is_bounded_paused_and_artifact_backed(self):
        self.assertEqual(validate_command("snapshot.probe", {}), {"iterations": 128})
        for value in (0, 257, True):
            with self.assertRaises(ValueError):
                validate_command("snapshot.probe", {"iterations": value})
        self.start()
        result = self.command("snapshot.probe", {"iterations": 2})
        self.assertTrue(result["ok"], result)
        self.assertIn("artifact", result["result"])
        self.assertEqual(self.service.worker.calls[-1], ("snapshot.probe", {"iterations": 2}))
        self.service.playing = True
        before = len(self.service.worker.calls)
        rejected = self.command("snapshot.probe")
        self.assertEqual(rejected["error"]["code"], "session-playing")
        self.assertEqual(len(self.service.worker.calls), before)

    def test_snapshot_probe_response_is_compact_and_artifact_keeps_worker_detail(self):
        self.start()
        worker_result = {
            "schemaVersion": 1,
            "scope": "paused-snapshot-reader-diagnostic",
            "acceptedProof": False,
            "proofStatus": "diagnostic-only",
            "frame": 12,
            "nativeCycle": 30,
            "iterations": 2,
            "snapshotsEqual": True,
            "gameClocksUnchanged": True,
            "snapshotSha256": "a" * 64,
            "snapshotBytes": 128,
            "intervals": [{"cpuNs": 20, "threadCpuNs": 13, "wallNs": 50,
                           "readCalls": 2, "readBytes": 16}],
            "events": [{"frame": 0, "kind": "boot-backlog", "data": {"large": "x" * 4096}}],
        }
        with patch.object(self.service.worker, "call", return_value=worker_result) as call:
            response = self.command("snapshot.probe", {"iterations": 2})
        self.assertTrue(response["ok"], response)
        call.assert_called_once_with("snapshot.probe", {"iterations": 2})
        probe = response["result"]["probe"]
        self.assertEqual(set(probe), set(worker_result) - {"events"})
        self.assertNotIn("boot-backlog", json.dumps(response))
        artifact = Path(response["result"]["artifact"]["path"])
        self.assertEqual(json.loads(artifact.read_text()), worker_result)

    def test_copies_both_rom_and_save_before_open(self):
        self.start()
        args = self.service.worker.calls[0][1]
        self.assertEqual(Path(args["rom"]).parent, self.service.directory)
        self.assertEqual(Path(args["save"]).parent, self.service.directory)
        for kind, name in (("rom", "test.nds"), ("save", "test.sav")):
            self.assertFalse(Path(args[kind]).samefile(self.root / name))
            self.assertIn(self.service.session["identity"][kind]["copyMethod"], ("clonefile", "copy"))
        Path(args["rom"]).write_bytes(b"core-autosave-bug")
        Path(args["save"]).write_bytes(b"changed-party")
        self.assertEqual((self.root / "test.nds").read_bytes(), b"copied-rom")
        self.assertEqual((self.root / "test.sav").read_bytes(), b"source-save")

    def test_owned_stop_receipt_keeps_cleanup_failures(self):
        for broken in (False, True):
            with self.subTest(broken=broken):
                self.start()
                session_id = self.service.session["id"]
                if broken:
                    self.service.worker.close = Mock(side_effect=RuntimeError("close failed"))
                receipt = self.service._stop()
                self.assertEqual(receipt, {"sessionId": session_id, "closed": not broken,
                    "errors": ["close failed"] if broken else []})
                self.assertIsNone(self.service.worker)
                self.assertIsNone(self.service.lease)

    def test_stop_removes_only_private_rom_after_worker_closed(self):
        self.start()
        worker = self.service.worker
        rom = Path(self.service.session["identity"]["rom"]["copy"])
        save = Path(self.service.session["identity"]["save"]["copy"])
        evidence = self.service.directory / "evidence.json"
        evidence.write_text('{"keep":true}')
        real_remove = devtools_copy.remove_private_rom

        def checked_remove(*args):
            self.assertTrue(worker.closed)
            return real_remove(*args)

        with patch("tools.overworld.devtools.remove_private_rom", side_effect=checked_remove):
            self.assertTrue(self.service._stop()["closed"])
        self.assertFalse(rom.exists())
        self.assertEqual(save.read_bytes(), b"source-save")
        self.assertEqual(evidence.read_text(), '{"keep":true}')
        self.assertEqual((self.root / "test.nds").read_bytes(), b"copied-rom")
        self.assertEqual((self.root / "test.sav").read_bytes(), b"source-save")
        self.assertEqual(self.service.session["romCopyCleanup"]["status"], "removed")
        self.assertTrue(self.service._stop()["closed"])

    def test_failed_worker_close_never_removes_rom_even_on_repeat_stop(self):
        self.start()
        rom = Path(self.service.session["identity"]["rom"]["copy"])
        self.service.worker.close = Mock(side_effect=RuntimeError("close failed"))
        self.assertFalse(self.service._stop()["closed"])
        repeated = self.service._stop()
        self.assertFalse(repeated["closed"])
        self.assertIn("unconfirmed", str(repeated["errors"]))
        self.assertTrue(rom.exists())
        self.assertEqual(self.service.session["romCopyCleanup"]["reason"], "worker-close-failed")

    def test_point_terrain_routes_exact_read_without_capture_or_setup(self):
        self.start()
        self.service.worker.calls.clear()
        reply = self.command("terrain", {"x": 558, "z": 373, "radius": 0})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(self.service.worker.calls, [("terrain", {"x": 558, "z": 373, "radius": 0})])
        self.assertEqual(self.service.session["mode"], "normal")

    def test_point_terrain_rejects_partial_center_before_worker_call(self):
        self.start()
        self.service.worker.calls.clear()
        for args in ({"x": 558}, {"z": 373}, {"radius": -1}, {"x": True, "z": 373},
                     {"x": 558, "z": 32768}):
            with self.subTest(args=args):
                self.assertFalse(self.command("terrain", args)["ok"])
        self.assertEqual(self.service.worker.calls, [])

    def test_saved_comparison_works_after_owned_session_stops(self):
        self.start()
        first = self.service._artifact("first", {"x": 1})
        second = self.service._artifact("second", {"x": 2})
        directory = self.service.directory.name
        self.service._stop()
        reply = self.command("compare", {"left": directory + "/" + Path(first["path"]).name,
                                         "right": directory + "/" + Path(second["path"]).name})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(reply["result"]["firstDifference"]["path"], ["x"])
        self.assertIsNone(self.service.worker)

    def test_actor_event_filter_keeps_native_policy_receipts(self):
        self.start()
        self.service._event("native-observation", {"publicSubject": {"handle": {"value": 77}}, "observation": "walk-policy"})
        self.service._event("native", {"actorHandle": 77, "event": "MOTION_STARTED"})
        self.service._event("native", {"actorHandle": 78, "event": "MOTION_STARTED"})
        reply = self.command("events", {"handle": 77})
        self.assertTrue(reply["ok"], reply)
        self.assertEqual(len(reply["result"]["events"]), 2)

    def test_copy_failure_does_not_open_worker_or_change_inputs(self):
        before = len(FakeWorker.instances)
        with patch("tools.overworld.devtools.copy_private_file", side_effect=OSError(errno.ENOSPC, "disk full")):
            reply = self.command("start")
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["code"], "io-error")
        self.assertIn("disk full", reply["error"]["message"])
        self.assertEqual(len(FakeWorker.instances), before)
        self.assertIsNone(self.service.worker)
        self.assertIsNone(self.service.lease)
        self.assertEqual(reply["session"]["state"], "stopped")
        self.assertEqual((self.root / "test.nds").read_bytes(), b"copied-rom")
        self.assertEqual((self.root / "test.sav").read_bytes(), b"source-save")

    def test_private_copy_still_checks_source_and_copy_hashes(self):
        def wrong_copy(source, target):
            target.write_bytes(b"incorrect copy")
            return "copy"

        before = len(FakeWorker.instances)
        with patch("tools.overworld.devtools.copy_private_file", side_effect=wrong_copy):
            reply = self.command("start")
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["code"], "input-changed")
        self.assertEqual(len(FakeWorker.instances), before)
        self.assertIsNone(self.service.lease)
        self.assertEqual((self.root / "test.nds").read_bytes(), b"copied-rom")
        self.assertEqual((self.root / "test.sav").read_bytes(), b"source-save")

    def test_failure_still_marks_prepared_before_worker(self):
        self.start()
        self.service.worker.fail = DevtoolsError("not-ready", "busy")
        result = self.command("teleport", {"map": 34, "x": 10, "z": 12})
        self.assertFalse(result["ok"])
        self.assertEqual(self.service.session["mode"], "prepared")
        self.assertEqual(json.loads((self.service.directory / "session.json").read_text())["mode"], "prepared")

    def test_validation_failure_does_not_mutate_or_taint(self):
        self.start()
        before = len(self.service.worker.calls)
        result = self.command("teleport", {"map": 34, "x": True, "z": 12})
        self.assertFalse(result["ok"])
        self.assertEqual(self.service.session["mode"], "normal")
        self.assertEqual(len(self.service.worker.calls), before)

    def test_reset_replaces_process_and_uses_original_save(self):
        self.start()
        old = self.service.worker
        old_dir = self.service.directory
        self.command("party", {"slot": 0, "species": 56})
        result = self.command("reset")
        self.assertTrue(result["ok"], result)
        self.assertTrue(old.closed)
        self.assertIsNot(old, self.service.worker)
        self.assertNotEqual(old_dir, self.service.directory)
        self.assertEqual(self.service.session["mode"], "normal")

    def test_retries_do_not_repeat_commands(self):
        self.start()
        first = self.command("step", {"frames": 10}, requestId="input-1")
        repeat = self.command("step", {"frames": 10}, requestId="input-1")
        self.assertEqual(first, repeat)
        self.assertEqual(self.service.worker.frame, 10)
        conflict = self.command("step", {"frames": 11}, requestId="input-1")
        self.assertEqual(conflict["error"]["code"], "request-id-conflict")
        self.assertEqual(self.command("step", {"frames": 10}, requestId="input-1"), first)

    def test_status_does_not_cycle_or_claim_proof(self):
        self.start()
        before = len(self.service.worker.calls)
        result = self.command("status")
        self.assertEqual(before, len(self.service.worker.calls))
        self.assertFalse(result["session"]["acceptedProof"])

    def test_recording_arms_native_trace_and_preserves_existing_recording(self):
        self.start()
        self.assertTrue(self.command("record.start", {"maxFrames": 120})["ok"])
        self.assertIn(("record.start", {"maxFrames": 120}), self.service.worker.calls)
        recorder = self.service.recording
        self.assertEqual(self.command("record.start")["error"]["code"], "already-recording")
        self.assertIs(self.service.recording, recorder)
        self.assertTrue(self.command("record.stop")["ok"])
        self.assertIn(("record.stop", None), self.service.worker.calls)

    def test_long_trace_keeps_the_bounded_diagnostic_snapshot_window(self):
        self.start()
        self.assertEqual(validate_command("record.start", {"maxFrames": 7000}),
                         {"maxFrames": 7000, "maxEvents": 4000})
        self.assertTrue(self.command("record.start", {"maxFrames": 7000})["ok"])
        self.assertIn(("record.start", {"maxFrames": 7000}), self.service.worker.calls)
        self.assertEqual(self.service.recording.max_frames, 1800)

    def test_failed_trace_arm_does_not_claim_recording(self):
        self.start()
        self.service.worker.fail = DevtoolsError("trace-busy", "native trace is already armed")
        self.assertFalse(self.command("record.start")["ok"])
        self.assertFalse(self.service.recording_active)

    def test_observation_failure_returns_error_and_retains_completed_command(self):
        self.start()
        self.command("record.start")
        with patch.object(self.service.recording, "failure_summary", return_value={
                "hasDefiniteFailures": True, "latest": [{"reason": "duplicate active handle"}]}):
            reply = self.command("step", {"frames": 2})
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["code"], "observation-integrity")
        self.assertFalse(self.service.recording_active)
        record = self.service._export()
        commands = [e for e in record["events"] if e["kind"] == "command"]
        self.assertEqual(len(commands), 1)
        self.assertFalse(commands[0]["data"]["ok"])
        self.assertEqual(commands[0]["data"]["receipt"]["frame"], 2)
        self.assertTrue(any(e["kind"] == "error" for e in record["events"]))

    def test_inspect_rejects_absent_subject_and_accepts_handle(self):
        self.start()
        self.assertTrue(self.command("inspect", {"handle": 77})["ok"])
        self.assertEqual(self.command("inspect", {"handle": 78})["error"]["code"], "actor-not-present")

    def test_lease_prevents_two_sessions_and_releases_on_stop(self):
        self.start()
        second = Service(self.root, FakeWorker)
        try:
            self.assertEqual(second.command({"op": "start"})["error"]["code"], "emulator-busy")
            self.command("stop")
            self.assertTrue(second.command({"op": "start"})["ok"])
        finally:
            second._stop()

    def test_worker_timeout_stops_session_and_retains_error(self):
        self.start()
        old = self.service.worker
        old.fail = DevtoolsError("worker-unavailable", "timeout")
        result = self.command("step")
        self.assertFalse(result["ok"])
        self.assertTrue(old.closed)
        self.assertIsNone(self.service.worker)
        self.assertEqual(self.service.status()["session"]["state"], "stopped")

    def test_real_worker_log_failure_cannot_replace_fatal_error_or_keep_lease(self):
        native_error = {"fatal": True, "code": "native-call-timeout", "message": "native timeout",
                        "details": {"cpu": {"pc": 0x02000000}, "checkpoint": [1, 2, 3]}}
        for response, code in ((queue.Empty(), "worker-unavailable"),
                               ({"id": 99}, "worker-protocol"),
                               ({"id": 1, "ok": False, "error": native_error}, "unsafe-runtime-state")):
            with self.subTest(code=code):
                self.command("stop")
                self.start()
                self.command("record.start")
                self.service.worker.close()
                # Keep the actual Worker.call/close and service error path;
                # replace only process I/O and time-dependent queue delivery.
                worker = Worker.__new__(Worker)
                worker.sequence = 0
                worker.directory = self.service.directory
                worker.errors = deque(["native worker diagnostic"], maxlen=200)
                worker.responses = SimpleNamespace(get=Mock(
                    side_effect=response if isinstance(response, Exception) else None,
                    return_value=response))
                running = [True]
                worker.process = SimpleNamespace(
                    stdin=io.StringIO(), stdout=io.StringIO(), stderr=io.StringIO(),
                    poll=lambda: None if running[0] else 0,
                    terminate=lambda: running.__setitem__(0, False), wait=Mock(return_value=0))
                self.service.worker = worker
                original_write = Path.write_text

                def write(path, *args, **kwargs):
                    if path.name == "worker-tail.log":
                        raise OSError("worker log disk full")
                    return original_write(path, *args, **kwargs)

                with patch.object(Path, "write_text", write):
                    reply = self.command("step", requestId=code)
                self.assertFalse(reply["ok"])
                self.assertEqual(reply["error"]["code"], code)
                if code == "unsafe-runtime-state":
                    self.assertEqual(reply["error"]["details"], native_error)
                else:
                    self.assertIn("native worker diagnostic", reply["error"]["details"])
                self.assertFalse(running[0])
                self.assertTrue(worker.process.stdin.closed)
                self.assertTrue(worker.process.stdout.closed)
                self.assertTrue(worker.process.stderr.closed)
                self.assertIsNone(self.service.worker)
                self.assertIsNone(self.service.lease)
                self.assertFalse(self.service.recording_active)
                self.assertEqual(reply["session"]["state"], "stopped")
                self.assertEqual(self.command("step", requestId=code), reply)

    def test_live_play_recipe_compacts_without_changing_raw_commands(self):
        self.start()
        self.command("record.start")
        self.service.playing = True
        generation = self.service.play_generation

        def stop_after_605(_delay):
            if self.service.worker.frame >= 605:
                self.service.playing = False

        with patch("tools.overworld.devtools.time.sleep", side_effect=stop_after_605):
            self.service._play(generation)
        reply = self.command("recipe.save", {"name": "idle-play"})
        self.assertTrue(reply["ok"], reply)
        recipe = json.loads(Path(reply["result"]["path"]).read_text())
        self.assertEqual(recipe["actions"], [
            {"op": "step", "args": {"frames": 600, "keys": []}},
            {"op": "step", "args": {"frames": 5, "keys": []}},
        ])
        commands = [e["data"] for e in self.service._export()["events"] if e["kind"] == "command"]
        self.assertEqual(len(commands), 605)
        self.assertTrue(all(e["ok"] is True and e["args"] == {"frames": 1, "keys": []} for e in commands))
        self.assertEqual([e["startFrame"] for e in commands], list(range(605)))

    def test_recipe_compaction_preserves_keys_setup_order_and_split_bound(self):
        self.start()
        actions = [("step", {"frames": 599}), ("step", {"frames": 3}),
                   ("step", {"frames": 1, "keys": ["RIGHT"]}),
                   ("step", {"frames": 1, "keys": ["RIGHT"]}),
                   ("party", {"slot": 0, "species": 56}),
                   ("step", {"frames": 2}), ("step", {"frames": 3})]
        for op, args in actions:
            self.assertTrue(self.command(op, args)["ok"])
        reply = self.command("recipe.save", {"name": "mixed"})
        self.assertTrue(reply["ok"], reply)
        recipe = json.loads(Path(reply["result"]["path"]).read_text())
        self.assertEqual(recipe["mode"], "prepared")
        expected = [("step", {"frames": 600}), ("step", {"frames": 2}),
                    *actions[2:5], ("step", {"frames": 5})]
        self.assertEqual(recipe["actions"], [{"op": op, "args": validate_command(op, args)} for op, args in expected])

    def test_failed_action_cannot_be_removed_from_a_successful_default_recipe(self):
        for op, args in (("party", {"slot": 0, "species": 56}), ("step", {"frames": 1})):
            with self.subTest(op=op):
                self.command("stop")
                self.start()
                self.command("record.start")
                self.assertTrue(self.command("step")["ok"])
                self.service.worker.fail = DevtoolsError("not-ready", "busy")
                self.assertFalse(self.command(op, args)["ok"])
                self.service.worker.fail = None
                for _ in range(260):
                    self.assertTrue(self.command("step")["ok"])
                reply = self.command("recipe.save", {"name": "failed-" + op})
                self.assertFalse(reply["ok"])
                self.assertEqual(reply["error"]["code"], "recipe-failed-history")
                self.assertFalse((self.root / "tests/overworld/recipes" / ("failed-" + op + ".json")).exists())
                commands = [e["data"] for e in self.service._export()["events"] if e["kind"] == "command"]
                self.assertEqual(len([e for e in commands if e["ok"] is False]), 1)
                self.assertEqual(commands[1]["op"], op)

    def test_compaction_keeps_history_bounded_and_rejects_truncation(self):
        self.start()
        keyed = {"op": "step", "args": {"frames": 1, "keys": ["RIGHT"]}}
        self.service.actions = [dict(keyed) for _ in range(2000)]
        self.assertTrue(self.command("step", {"keys": ["RIGHT"]})["ok"])
        self.assertLessEqual(len(self.service.actions), 2000)
        reply = self.command("recipe.save", {"name": "truncated"})
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["code"], "recipe-truncated")

    def test_large_native_error_is_retained_without_blocking_cleanup_or_retry(self):
        self.start()
        self.command("record.start")
        worker = self.service.worker
        details = {"latestCompleteFrame": {"actors": [{"raw": "x" * 20000}]}}
        worker.fail = DevtoolsError("unsafe-runtime-state", "native call stopped", details)
        reply = self.command("party", {"slot": 0, "species": 56}, requestId="large-failure")
        self.assertFalse(reply["ok"])
        self.assertEqual(reply["error"]["details"], details)
        self.assertTrue(worker.closed)
        self.assertIsNone(self.service.lease)
        self.assertFalse(self.service.status()["result"]["recording"])
        self.assertEqual(reply["session"]["state"], "stopped")
        self.assertEqual(self.command("party", {"slot": 0, "species": 56}, requestId="large-failure"), reply)
        error_event = next(e for e in self.service._export()["events"] if e["kind"] == "error")
        data = error_event["data"]
        self.assertTrue(data["detailsOmitted"])
        self.assertEqual(json.loads(Path(data["artifact"]["path"]).read_text()), reply["error"])
        self.assertLess(len(json.dumps(data).encode()), 8192)

    def test_error_artifact_write_failure_does_not_hide_native_failure(self):
        self.start()
        self.command("record.start")
        worker = self.service.worker
        worker.fail = DevtoolsError("unsafe-runtime-state", "native call stopped", {"raw": "x" * 20000})
        with patch.object(self.service, "_artifact", side_effect=OSError("disk full")):
            reply = self.command("step")
        self.assertEqual(reply["error"]["code"], "unsafe-runtime-state")
        self.assertTrue(worker.closed)
        event = next(e for e in self.service._export()["events"] if e["kind"] == "error")
        self.assertIn("disk full", event["data"]["artifactError"])

    def test_recipe_failure_retains_native_details_and_stops_owned_core(self):
        self.start()
        worker = self.service.worker
        details = {"cpu": {"pc": 0x02000000}, "actors": ["x" * 20000]}
        worker.fail = DevtoolsError("unsafe-runtime-state", "native call stopped", details)
        self.service.session["recipe"] = {"name": "failed", "state": "running", "completedActions": 0}
        self.service._execute_recipe({"actions": [{"op": "party", "args": {"slot": 0, "species": 56}}]},
                                     self.service.session["id"])
        progress = self.service.status()["session"]["recipe"]
        self.assertEqual(progress["state"], "failed")
        self.assertEqual(progress["completedActions"], 0)
        self.assertEqual(progress["error"]["details"], details)
        self.assertTrue(worker.closed)

    def test_failure_recording_can_export_after_worker_stops(self):
        self.start()
        self.assertTrue(self.command("record.start")["ok"])
        self.service.worker.fail = DevtoolsError("worker-unavailable", "timeout")
        self.assertFalse(self.command("party", {"slot": 0, "species": 56})["ok"])
        exported = self.command("recording.export")
        self.assertTrue(exported["ok"], exported)
        self.assertEqual(exported["result"]["recording"]["mode"], "prepared")
        artifact = Path(exported["result"]["artifact"]["path"])
        self.assertEqual(artifact.suffixes[-2:], [".json", ".gz"])
        self.assertEqual(exported["result"]["artifact"]["encoding"], "gzip")
        data = json.loads(gzip.decompress(artifact.read_bytes()))
        self.assertTrue(any(e["kind"] == "command" and e["data"].get("ok") is False for e in data["events"]))

    def test_recording_does_not_embed_large_screenshot(self):
        self.start()
        self.service.snapshot["screenshot"] = {"url": "x" * 200000, "frame": 0, "sha256": "a" * 64}
        self.assertTrue(self.command("record.start")["ok"])
        record = self.service._export()
        self.assertNotIn("url", record["snapshots"][0]["screenshot"])

    def test_large_native_rows_allow_record_inspect_and_checkpoint(self):
        from tools.overworld.test_devtools_records import large_snapshot
        self.start()
        sample = large_snapshot()
        with patch.object(self.service.worker, "call", return_value=sample):
            for op in ("record.start", "inspect", "checkpoint"):
                reply = self.command(op)
                self.assertTrue(reply["ok"], reply)
        record = self.service._export()
        self.assertEqual(record["snapshots"][-1]["terrain"], sample["terrain"])
        self.assertEqual(record["snapshots"][-1]["nativeObservation"], sample["nativeObservation"])
        self.assertFalse(record["acceptedProof"])

    def test_copy_directory_failure_releases_lease(self):
        with patch("tools.overworld.devtools.tempfile.mkdtemp", side_effect=OSError("disk full")):
            self.assertFalse(self.command("start")["ok"])
        self.assertIsNone(self.service.lease)
        self.assertTrue(self.command("start")["ok"])

    def test_expired_request_is_rejected_not_replayed(self):
        self.start()
        self.command("step", requestId="old-step")
        for index in range(130):
            self.command("status", requestId=f"status-{index}")
        self.assertEqual(self.command("step", requestId="old-step")["error"]["code"], "request-expired")
        self.assertEqual(self.service.worker.frame, 1)

    def test_exhausted_request_budget_keeps_stop_safe_and_blocks_new_work(self):
        self.start()
        self.command("record.start")
        cached = self.command("step", {"frames": 3}, requestId="cached-step")
        self.service.used_request_ids.update(f"used-{index}" for index in range(9999))
        self.assertEqual(len(self.service.used_request_ids), 10000)
        worker = self.service.worker
        self.service.playing = True
        for request in ({"op": "step", "args": {"frames": 1}, "requestId": "new-step"},):
            reply = self.service.command(request)
            self.assertFalse(reply["ok"])
            self.assertEqual(reply["error"]["code"], "request-capacity")
        self.assertEqual(self.command("step", {"frames": 3}, requestId="cached-step"), cached)
        conflict = self.command("stop", requestId="cached-step")
        self.assertEqual(conflict["error"]["code"], "request-id-conflict")
        self.assertIs(self.service.worker, worker, "a conflicting mutation ID must not become Stop")
        expired = self.command("stop", requestId="used-0")
        self.assertEqual(expired["error"]["code"], "request-expired")
        invalid = self.command("stop", {"unexpected": 1}, requestId="bad-stop")
        self.assertEqual(invalid["error"]["code"], "invalid-command")
        stopped = self.command("stop", requestId="emergency-stop")
        self.assertTrue(stopped["ok"], stopped)
        self.assertEqual(stopped["session"]["state"], "stopped")
        self.assertTrue(worker.closed)
        self.assertIsNone(self.service.lease)
        self.assertIsNone(self.service.worker)
        self.assertFalse(self.service.playing)
        self.assertFalse(self.service.recording_active)
        self.assertEqual(self.command("stop", requestId="emergency-stop"), stopped)
        self.assertEqual(self.command("stop", requestId="another-stop"), stopped)
        self.assertEqual(self.command("stop"), stopped)
        self.assertEqual(len(self.service.used_request_ids), 10000)
        self.assertLessEqual(len(self.service.requests), 128)
        for op in ("status", "help"):
            self.assertTrue(self.command(op, requestId="recovery-" + op)["ok"])
        for request in ({"op": "start"}, {"op": "reset"}, {"op": "play"},
                        {"op": "reset", "requestId": "new-reset"},
                        {"op": "party", "args": {"slot": 0, "species": 56}}):
            reply = self.service.command(request)
            self.assertEqual(reply["error"]["code"], "request-capacity")
        self.assertIsNone(self.service.worker)

    def test_artifacts_cannot_read_rom_or_outside_session(self):
        self.start()
        for name in ("../test.sav", f"{self.service.directory.name}/game.nds", "session-foo/../../test.sav"):
            with self.assertRaises(ValueError):
                self.service.artifact(name)
        artifact = self.service._artifact("recording", {"acceptedProof": False})
        relative = "/".join(Path(artifact["path"]).parts[-2:])
        data, kind = self.service.artifact(relative)
        self.assertEqual(json.loads(data), {"acceptedProof": False})
        self.assertEqual(kind, "application/json")
        compressed = self.service._artifact("recording", {"acceptedProof": False}, compress=True)
        relative = "/".join(Path(compressed["path"]).parts[-2:])
        data, kind = self.service.artifact(relative)
        self.assertEqual(json.loads(gzip.decompress(data)), {"acceptedProof": False})
        self.assertEqual(kind, "application/gzip")


class PrivateCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.source, self.target = self.directory / "source", self.directory / "copy"
        self.source.write_bytes(b"private copy fixture" * 32)

    def tearDown(self):
        self.temp.cleanup()

    def assert_isolated_copy(self):
        original = self.source.read_bytes()
        self.assertEqual(self.target.read_bytes(), original)
        self.assertFalse(self.source.samefile(self.target))
        self.assertEqual(self.target.stat().st_nlink, 1)
        self.target.write_bytes(b"changed session copy")
        self.assertEqual(self.source.read_bytes(), original)

    def test_real_platform_copy_is_distinct_and_writable(self):
        self.source.chmod(0o400)
        method = devtools_copy.copy_private_file(self.source, self.target)
        self.assertIn(method, ("clonefile", "copy"))
        self.assert_isolated_copy()
        self.assertEqual(self.source.stat().st_mode & 0o777, 0o400)

    def test_unsupported_clone_uses_exclusive_ordinary_copy(self):
        with patch.object(devtools_copy, "_clone_file", return_value=False):
            self.assertEqual(devtools_copy.copy_private_file(self.source, self.target), "copy")
        self.assert_isolated_copy()

    def test_native_unsupported_errors_fall_back_but_allocation_errors_do_not(self):
        for code in (errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV,
                     errno.ENOSPC, errno.EACCES, errno.EINVAL):
            with self.subTest(errno=code):
                target = self.directory / ("copy-" + str(code))
                # ENOTSUP and EOPNOTSUPP can alias on the host.
                if target.exists():
                    continue
                native = Mock(return_value=-1)
                with patch.object(devtools_copy.sys, "platform", "darwin"), \
                     patch.object(devtools_copy.ctypes, "CDLL", return_value=SimpleNamespace(clonefile=native)), \
                     patch.object(devtools_copy.ctypes, "get_errno", return_value=code):
                    if code in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV}:
                        self.assertEqual(devtools_copy.copy_private_file(self.source, target), "copy")
                        self.assertFalse(self.source.samefile(target))
                        self.assertEqual(target.read_bytes(), self.source.read_bytes())
                    else:
                        with patch.object(devtools_copy.shutil, "copyfileobj") as fallback:
                            with self.assertRaises(OSError) as raised:
                                devtools_copy.copy_private_file(self.source, target)
                        self.assertEqual(raised.exception.errno, code)
                        fallback.assert_not_called()
                        self.assertFalse(target.exists())
                    self.assertEqual(native.call_args.args[2], 3)

    def test_missing_native_symbol_uses_ordinary_copy(self):
        with patch.object(devtools_copy.sys, "platform", "darwin"), \
             patch.object(devtools_copy.ctypes, "CDLL", return_value=SimpleNamespace()):
            self.assertEqual(devtools_copy.copy_private_file(self.source, self.target), "copy")
        self.assert_isolated_copy()

    def test_existing_destination_is_never_replaced_or_opened(self):
        self.target.write_bytes(b"existing session output")
        with patch.object(devtools_copy, "_clone_file") as clone:
            with self.assertRaises(FileExistsError):
                devtools_copy.copy_private_file(self.source, self.target)
        clone.assert_not_called()
        self.assertEqual(self.target.read_bytes(), b"existing session output")
        self.assertEqual(self.source.read_bytes(), b"private copy fixture" * 32)


class ContractTests(unittest.TestCase):
    def test_map_and_move_help_matches_existing_native_bounds(self):
        operations = command_help()["operations"]
        self.assertEqual(operations["teleport"]["map"]["maximum"], 539)
        self.assertEqual(operations["party"]["moves"]["itemMaximum"], 922)
        self.assertEqual(validate_command("teleport", {"map": 539, "x": 0, "z": 0})["map"], 539)
        self.assertEqual(validate_command("party", {"slot": 0, "moves": [0, 1, 921, 922]})["moves"], [0, 1, 921, 922])
        for op, args in (("teleport", {"map": 540, "x": 0, "z": 0}),
                         ("party", {"slot": 0, "moves": [0, 1, 2, 923]})):
            with self.assertRaises(ValueError):
                validate_command(op, args)
        # Source-derived native validation is the independent operation bound.
        source = Path(__file__).with_name("devtools_runtime.py")
        calls = [node for node in ast.walk(ast.parse(source.read_text()))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "integer" and len(node.args) == 4
                 and isinstance(node.args[1], ast.Constant)]
        for label, maximum in (("mapId", 539), ("move", 922)):
            bounds = [(ast.literal_eval(n.args[2]), ast.literal_eval(n.args[3]))
                      for n in calls if n.args[1].value == label]
            self.assertEqual(bounds, [(0, maximum)])

    def test_worker_uses_exact_isolated_repository_python3(self):
        root = Path("/example/repo")
        with patch("tools.overworld.devtools.subprocess.Popen") as popen, patch("tools.overworld.devtools.threading.Thread"):
            Worker(root, root / "build/session")
        command = popen.call_args.args[0]
        self.assertEqual(command[:1 + len(HEADLESS_PYTHON_FLAGS)],
                         [str(root / ".venv/bin/python3"), *HEADLESS_PYTHON_FLAGS])

    def test_step_limits_and_types(self):
        for args in ({"frames": 0}, {"frames": 601}, {"frames": True}, {"frames": "1"},
                     {"keys": ["UP", "DOWN"]}, {"keys": ["UP", "UP"]}, {"foo": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate_command("step", args)
        self.assertEqual(validate_command("step", {}), {"frames": 1, "keys": []})

    def test_no_arbitrary_memory_or_eval_commands(self):
        for op in ("write", "read-memory", "eval", "exec", "set-pc"):
            with self.assertRaises(ValueError):
                validate_command(op, {})

    def test_mutation_fields_are_explicit(self):
        for op, args in (("party", {"slot": 0}), ("party", {"slot": 6, "hp": 1}),
                         ("spawn", {"species": 165, "x": 1}), ("party", {"slot": 0, "moves": [1, 2]}),
                         ("recipe.save", {"name": "../test"})):
            with self.subTest(op=op, args=args), self.assertRaises(ValueError):
                validate_command(op, args)


if __name__ == "__main__":
    unittest.main()
