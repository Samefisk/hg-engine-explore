"""Host controls for the real live-tool smoke checker, not runtime proof.

The transport below supplies synthetic responses and temporary files. The
production checker, exact actor selector, file reads, and cleanup logic run
unchanged. No emulator or Workshop server is started.
"""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/verify_overworld_devtools_session.py"


def load_checker():
    spec = importlib.util.spec_from_file_location("devtools_live_smoke_host_subject", SOURCE)
    module = importlib.util.module_from_spec(spec)
    old_path = list(sys.path)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = old_path
    return module


class FakeTransport:
    """Only substitute the remote boundary, with named independent bad outcomes."""
    def __init__(self, checker, args, directory, fault=None):
        self.checker, self.args, self.directory, self.fault = checker, args, directory, fault
        self.calls = []
        self.session = None
        self.generation = 0
        self.recipe_polls = 0
        self.export_count = 0
        self.replies = {}
        self.frames_advanced = 0
        self.playing = False
        self.play_status_reads = 0
        self.pause_status_reads = None
        self.timeouts = []
        self.initial = {
            "frame": 100,
            "context": {"fieldEpoch": 4, "mapGeneration": 5, "mapId": 34},
            "player": {"x": 550, "y": 376, "facing": 1}, "actors": [],
            "party": [{"slot": 0, "species": 155, "personality": 12345, "level": 8,
                       "hp": 24, "status": 0, "moves": [33, 43, 0, 0], "identityVerified": True}],
            "partyObservation": {"nativeGetterChecks": ["species", "hp", "status"]},
        }
        self.snapshot = deepcopy(self.initial)
        if fault == "existing_session":
            self.session = {"id": "someone-elses-session", "state": "ready", "mode": "normal"}

    def response(self, result):
        return {"ok": True, "session": deepcopy(self.session), "result": deepcopy(result)}

    def fresh_session(self):
        self.generation += 1
        self.session = {"id": f"owned-{self.generation}", "state": "ready", "mode": "normal",
                        "identity": {"rom": {"path": str(self.args.rom)}, "save": {"path": str(self.args.save)}}}
        self.snapshot = deepcopy(self.initial)
        self.playing = False
        self.pause_status_reads = None

    def actor(self, role, species, personality, slot):
        context = self.snapshot["context"]
        return {
            "handle": {"value": (2 << 16) | slot, "slot": slot, "generation": 2,
                       "fieldEpoch": context["fieldEpoch"], "mapGeneration": context["mapGeneration"],
                       "encounterGeneration": 6},
            "subjectIdentity": personality, "species": species, "role": role,
            "active": True, "identityVerified": True, "presentationAttached": True,
            "authorityGeneration": 2, "engineAnchorGeneration": 2, "presentationGeneration": 2,
            "engineIdentity": {"pointer": 0x02202000, "in_manager": True},
        }

    def __call__(self, url, envelope, timeout):
        self.calls.append(deepcopy(envelope))
        op, args = envelope["op"], envelope.get("args", {})
        self.timeouts.append((op, timeout))
        if op == "teleport" and self.fault in {"server_code_changed", "server_code_changed_and_missing_source"}:
            return {"ok": False, "session": deepcopy(self.session), "error": {
                "code": "server_restart_required", "message": "Devtools code changed."}}
        if op == "status":
            if self.session and "recipe" in self.session:
                self.recipe_polls += 1
                if self.recipe_polls >= 2:
                    self.session["recipe"]["state"] = "completed"
            if self.playing:
                self.play_status_reads += 1
                self.snapshot["nativeCycle"] = self.snapshot.get("nativeCycle", 0) + 2
                if self.fault not in {"play_stalled", "native_cycles_only"}:
                    if self.fault != "only_two_play_frames" or self.play_status_reads <= 2:
                        self.snapshot["frame"] += 1
            if self.pause_status_reads is not None:
                self.pause_status_reads += 1
                drift_read = {"pause_drift_first": 2, "pause_drift_second": 3}.get(self.fault)
                if self.pause_status_reads == drift_read:
                    self.snapshot["frame"] += 1
            return self.response({**self.snapshot, "playing": self.playing})
        if op == "start":
            self.fresh_session()
            return self.response(self.snapshot)
        if op == "inspect":
            if args.get("handle") == 0xffffffff:
                return {"ok": False, "session": deepcopy(self.session),
                        "error": {"code": "actor-not-present", "message": "not present"}}
            return self.response(self.snapshot)
        if op == "terrain":
            return self.response({"terrain": {"cells": [
                {"loaded": True, "collision": False, "terrain_class": 0, "x": x, "z": z}
                for x in range(548, 553) for z in range(374, 379)]}})
        if op == "capture":
            raise AssertionError("automated smoke must not capture images")
        if op in {"record.start", "record.stop"}:
            return self.response({"recording": op == "record.start"})
        if op == "step":
            request_id = envelope["requestId"]
            if request_id not in self.replies:
                self.frames_advanced += args["frames"]
                observed = 11 if self.fault == "short_observed_step" else 12
                completed = 11 if self.fault == "short_completed_step" else 12
                self.replies[request_id] = self.response({"operation": {
                    "completedGameFrames": completed, "observedFieldFrames": observed}})
            return deepcopy(self.replies[request_id])
        if op == "recording.export":
            self.export_count += 1
            artifact = self.directory / f"recording-{self.export_count}.json"
            events = [] if self.fault == "no_native_events" else [{"kind": "native", "data": {"routine": "transition"}}]
            artifact.write_text(json.dumps({"events": events}))
            # A claimed event in the response must not replace absent events in
            # the actual exported artifact that the checker is meant to read.
            return self.response({"recording": {"acceptedProof": False},
                                  "events": [{"kind": "native"}],
                                  "artifact": {"path": str(artifact)}})
        if op == "scenario.draft":
            return self.response({"draft": {"acceptedProof": False, "verificationStatus": "unverified"}})
        if op == "teleport":
            if self.fault != "unchanged_teleport_context":
                self.snapshot["player"].update(x=args["x"], y=args["z"], facing=args["facing"])
            self.snapshot["operation"] = {"calls": [] if self.fault == "no_teleport_call" else [{"routine": "create_field_task"}]}
            self.session["mode"] = "prepared"
            return self.response(self.snapshot)
        if op == "party":
            self.snapshot["party"][0].update(args)
            return self.response(self.snapshot)
        if op == "spawn":
            role = args["role"].upper()
            if role == "WILD":
                receipt = {"personality": 24680, "slot": 2}
                personality = receipt["personality"] + (1 if self.fault == "wrong_wild_pid" else 0)
                slot = receipt["slot"] + (1 if self.fault == "wrong_wild_slot" else 0)
                actor = self.actor(role, 165, personality, slot)
                self.snapshot["operation"] = {"value": receipt}
            else:
                actor = self.actor(role, 56, self.snapshot["party"][0]["personality"], 6 if role == "FOLLOWER" else 7)
            self.snapshot["actors"] = [] if role == "MOUNTED" and self.fault == "absent_mounted" else [actor]
            return self.response(self.snapshot)
        if op == "reset":
            self.fresh_session()
            return self.response(self.snapshot)
        if op == "recipe.load":
            self.fresh_session()
            self.session["recipe"] = {"state": "running"}
            return self.response({"started": True})
        if op == "play":
            self.playing = True
            return self.response({"playing": True})
        if op == "pause":
            self.playing = self.fault == "pause_keeps_playing"
            self.pause_status_reads = 0
            return self.response({"playing": self.playing})
        if op == "stop":
            if self.fault == "stop_error":
                raise RuntimeError("synthetic stop failure")
            self.session["state"] = "stopped"
            if self.fault == "source_changed_during_cleanup":
                self.args.save.write_bytes(b"synthetic changed source")
            if self.fault in {"missing_source", "unreadable_source", "server_code_changed_and_missing_source"}:
                self.args.save.unlink()
                if self.fault == "unreadable_source":
                    self.args.save.mkdir()  # A directory cannot be read as the original file.
            return self.response({"stopped": True})
        raise AssertionError(f"Unexpected smoke command: {op}")


class DevtoolsLiveSmokeTests(unittest.TestCase):
    def setUp(self):
        self.checker = load_checker()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.args = SimpleNamespace(url="http://host-only.invalid", rom=self.directory / "source.nds",
                                    save=self.directory / "source.sav")
        self.args.rom.write_bytes(b"synthetic source ROM, never loaded")
        self.args.save.write_bytes(b"synthetic source save, never loaded")

    def run_case(self, fault=None):
        transport = FakeTransport(self.checker, self.args, self.directory, fault)
        clock = [0.0]
        transport.sleep_durations = []

        def sleep(duration):
            transport.sleep_durations.append(duration)
            clock[0] += duration

        with mock.patch.object(self.checker, "request", side_effect=transport), \
                mock.patch.object(self.checker.time, "sleep", side_effect=sleep), \
                mock.patch.object(self.checker.time, "monotonic", side_effect=lambda: clock[0]):
            report = self.checker.run(self.args)
        transport.elapsed = clock[0]
        self.assertIs(report["acceptedProof"], False)
        return report, transport

    def reject(self, fault, failed_check):
        report, transport = self.run_case(fault)
        self.assertFalse(report["passed"], report)
        self.assertIn(failed_check, report["error"])
        self.assertIn({"name": failed_check, "passed": False}, report["checks"])
        self.assertEqual(transport.calls[-1]["op"], "stop")
        self.assertTrue(report["sourceFilesUnchanged"])

    def test_complete_synthetic_path_stays_diagnostic_and_cleans_own_session(self):
        report, transport = self.run_case()
        self.assertTrue(report["passed"], report.get("error"))
        self.assertTrue(report["sourceFilesUnchanged"])
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        self.assertEqual(transport.frames_advanced, 12)
        self.assertEqual(transport.generation, 3)
        self.assertEqual(transport.session["state"], "stopped")
        self.assertEqual(sum(call["op"] == "stop" for call in transport.calls), 1)
        operations = [call["op"] for call in transport.calls]
        self.assertEqual(operations.count("play"), 1)
        self.assertEqual(operations.count("pause"), 1)
        self.assertGreater(operations.index("play"), operations.index("recipe.load"))
        self.assertNotIn("recipe.save", operations)
        self.assertGreaterEqual(transport.play_status_reads, 3)
        # Immediate baseline plus both delayed reads, followed by cleanup status.
        self.assertEqual(transport.pause_status_reads, 4)
        self.assertTrue(all(0 < seconds <= 0.1 for seconds in transport.sleep_durations[1:]))

    def test_play_must_advance_three_actual_completed_frames(self):
        for fault in ("play_stalled", "native_cycles_only", "only_two_play_frames"):
            with self.subTest(fault=fault):
                report, transport = self.run_case(fault)
                self.assertFalse(report["passed"])
                failed_check = "play advances at least three completed game frames"
                self.assertIn({"name": failed_check, "passed": False}, report["checks"])
                self.assertEqual(transport.calls[-1]["op"], "stop")
                self.assertTrue(report["sourceFilesUnchanged"])
                self.assertLessEqual(transport.elapsed, 10.25 + 1e-6)  # Includes old recipe's 0.25s wait.
                play_index = next(i for i, call in enumerate(transport.calls) if call["op"] == "play")
                waits = transport.timeouts[play_index:-2]  # Cleanup calls keep their old timeout.
                self.assertTrue(all(0 < timeout <= 10 for _, timeout in waits))

    def test_pause_must_release_playback(self):
        self.reject("pause_keeps_playing", "pause releases live playback")

    def test_pause_must_hold_across_both_delayed_reads(self):
        for fault in ("pause_drift_first", "pause_drift_second"):
            with self.subTest(fault=fault):
                self.reject(fault, "pause holds the completed game frame across delayed status reads")

    def test_short_completed_step_is_rejected(self):
        self.reject("short_completed_step", "step advances exactly twelve observed game frames")

    def test_short_observed_step_is_rejected(self):
        self.reject("short_observed_step", "step advances exactly twelve observed game frames")

    def test_unchanged_location_does_not_prove_a_teleport(self):
        self.reject("unchanged_teleport_context", "teleport returns the requested loaded location")

    def test_changed_context_without_transition_call_is_not_a_teleport(self):
        self.reject("no_teleport_call", "teleport performed a real transition, not a no-op")

    def test_right_wild_species_with_wrong_personality_is_rejected(self):
        self.reject("wrong_wild_pid", "the exact spawned Ledyba really exists")

    def test_right_wild_species_with_wrong_slot_is_rejected(self):
        self.reject("wrong_wild_slot", "the exact spawned Ledyba really exists")

    def test_mounted_command_success_without_mounted_actor_is_rejected(self):
        self.reject("absent_mounted", "exact mounted exists")

    def test_claimed_events_do_not_replace_empty_actual_recording(self):
        self.reject("no_native_events", "recording contains real native events")

    def test_existing_live_session_is_neither_started_over_nor_stopped(self):
        report, transport = self.run_case("existing_session")
        self.assertFalse(report["passed"])
        self.assertIn("does not take over an existing session", report["error"])
        self.assertEqual([call["op"] for call in transport.calls], ["status"])
        self.assertEqual(transport.session["state"], "ready")
        self.assertTrue(report["sourceFilesUnchanged"])

    def test_changed_source_during_cleanup_prevents_a_pass(self):
        report, transport = self.run_case("source_changed_during_cleanup")
        self.assertFalse(report["passed"])
        self.assertFalse(report["sourceFilesUnchanged"])
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        self.assertEqual(transport.calls[-1]["op"], "stop")

    def test_cleanup_failure_prevents_a_pass(self):
        report, _ = self.run_case("stop_error")
        self.assertFalse(report["passed"])
        self.assertEqual(report["cleanupError"], "synthetic stop failure")
        self.assertTrue(report["sourceFilesUnchanged"])

    def test_missing_source_returns_a_failed_report_instead_of_raising(self):
        report, transport = self.run_case("missing_source")
        self.assertFalse(report["passed"])
        self.assertFalse(report["sourceFilesUnchanged"])
        self.assertEqual(report["sourceCheckErrors"][0]["path"], str(self.args.save))
        self.assertIn("FileNotFoundError", report["sourceCheckErrors"][0]["error"])
        self.assertEqual(transport.calls[-1]["op"], "stop")

    def test_unreadable_source_returns_a_failed_report_instead_of_raising(self):
        report, _ = self.run_case("unreadable_source")
        self.assertFalse(report["passed"])
        self.assertFalse(report["sourceFilesUnchanged"])
        self.assertIn("IsADirectoryError", report["sourceCheckErrors"][0]["error"])

    def test_server_change_preserves_the_known_failed_stage(self):
        report, transport = self.run_case("server_code_changed")
        self.assertFalse(report["passed"])
        self.assertIn("teleport:", report["error"])
        self.assertIn("server_restart_required", report["error"])
        failures = [entry for entry in report["responses"] if not entry["response"]["ok"]]
        self.assertEqual(failures[-1]["op"], "teleport")
        self.assertEqual(failures[-1]["response"]["error"]["code"], "server_restart_required")
        self.assertEqual(transport.calls[-1]["op"], "stop")
        self.assertTrue(report["sourceFilesUnchanged"])

    def test_cleanup_hash_error_does_not_replace_the_original_failed_stage(self):
        report, _ = self.run_case("server_code_changed_and_missing_source")
        self.assertFalse(report["passed"])
        self.assertIn("teleport:", report["error"])
        self.assertIn("server_restart_required", report["error"])
        self.assertFalse(report["sourceFilesUnchanged"])
        self.assertIn("FileNotFoundError", report["sourceCheckErrors"][0]["error"])


if __name__ == "__main__":
    unittest.main()
