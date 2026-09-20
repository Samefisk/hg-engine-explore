"""Transport-only CLI tests. No emulator or gameplay proof."""

import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

from tools.overworld import devtools_cli


class DevtoolsCliTests(unittest.TestCase):
    def test_job_summary_omits_repeated_measurement_history_not_failures(self):
        history = [{"laneHex": "ab" * 72, "samples": list(range(100))}] * 100
        measure = {"ready": False, "completeMotions": 55, "eligibleMoves": 54,
            "intervals": history, "actions": history, "interruptedIntervals": history,
            "selectedProfileReceipt": {"resultHex": "cd" * 200},
            "failures": [{"code": "stalled", "details": {"lastCommit": 55}}],
            "measurementErrors": [{"reason": "chain-boundary-overdue", "actual": 15}]}
        response = {"ok": True, "result": {"execution": "shared-devtools", "runId": "test-example",
            "state": "failed", "passed": False, "acceptedProof": False,
            "manifest": "/workspace/run/manifest.json", "evaluation": {"measurements": {"ledyba-chain-v1": measure}}}}
        original = copy.deepcopy(response)
        summary = devtools_cli.summarize_response(response)
        measured = summary["result"]["evaluation"]["measurements"]["ledyba-chain-v1"]
        self.assertEqual(measured["failures"], measure["failures"])
        self.assertEqual(measured["measurementErrors"], measure["measurementErrors"])
        self.assertEqual(measured["completeMotions"], 55)
        self.assertFalse("intervals" in measured, "summary must omit the repeated history")
        self.assertEqual(measured["historyCounts"]["intervals"], 100)
        self.assertLess(len(json.dumps(summary)), 4000)
        self.assertEqual(response, original)

    def parser(self):
        parser = argparse.ArgumentParser()
        devtools_cli.register(parser.add_subparsers(required=True))
        return parser

    def run_cli(self, words, response=None):
        args = self.parser().parse_args(["dev", *words])
        with mock.patch.object(devtools_cli, "request", return_value=response or {"ok": True, "session": None, "result": {}}) as call:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = args.handler(args)
        return code, call.call_args

    def test_commands_share_the_http_envelope(self):
        cases = [
            (["help", "--json"], "help", {}),
            (["diagnostics", "--json"], "diagnostics", {}),
            (["terrain", "--x", "558", "--z", "373", "--radius", "0", "--json"],
             "terrain", {"x": 558, "z": 373, "radius": 0}),
            (["explain", "--handle", "0x20001"], "explain", {"handle":131073}),
            (["events", "--handle", "0x20001", "--limit", "30"], "events", {"handle":131073,"limit":30}),
            (["checkpoint"], "checkpoint", {}),
            (["compare", "session-a/left.json", "session-b/right.json"], "compare", {"left":"session-a/left.json","right":"session-b/right.json"}),
            (["test", "list"], "test.list", {}),
            (["test", "start", "ledyba"], "test.start", {"name": "ledyba"}),
            (["test", "status"], "test.status", {}),
            (["test", "status", "--run-id", "test-exact"], "test.status", {"runId": "test-exact"}),
            (["test", "cancel", "--run-id", "test-exact"], "test.cancel", {"runId": "test-exact"}),
            (["test", "export", "--run-id", "test-exact"], "test.export", {"runId": "test-exact"}),
            (["catalog", "species", "--query", "ledyba"], "catalog", {"kind": "species", "query": "ledyba", "limit": 20}),
            (["start", "--save", "test.sav", "--mode", "prepared"], "start", {"save": "test.sav", "mode": "prepared"}),
            (["step", "8", "--keys", "up", "b"], "step", {"frames": 8, "keys": ["UP", "B"]}),
            (["step", "--frames", "8", "--keys", "up"], "step", {"frames": 8, "keys": ["UP"]}),
            (["step"], "step", {"frames": 1, "keys": []}),
            (["teleport", "34", "550", "376"], "teleport", {"map": 34, "x": 550, "z": 376, "facing": 1}),
            (["spawn", "165", "--role", "wild", "--level", "5"], "spawn", {"species": 165, "role": "wild", "level": 5}),
            (["spawn", "1075", "--form", "31"], "spawn", {"species": 1075, "form": 31, "role": "wild"}),
            (["party", "0", "--form", "0"], "party", {"slot": 0, "form": 0}),
            (["party", "0", "--species", "56", "--moves", "1", "2", "0", "0"], "party", {"slot": 0, "species": 56, "moves": [1, 2, 0, 0]}),
            (["inspect", "--handle", "0x20001"], "inspect", {"handle": 131073}),
            (["record", "start"], "record.start", {}),
            (["record", "start", "--max-frames", "1800", "--max-events", "4000", "--json"], "record.start", {"maxFrames": 1800, "maxEvents": 4000}),
            (["record", "start", "--max-frames", "600"], "record.start", {"maxFrames": 600}),
            (["record", "start", "--max-events", "1000"], "record.start", {"maxEvents": 1000}),
            (["record", "export", "--json"], "recording.export", {}),
            (["recipe", "load", "route-30"], "recipe.load", {"name": "route-30"}),
            (["scenario-draft", "jump", "--expectation", "same actor lands"], "scenario.draft", {"name": "jump", "expectation": "same actor lands"}),
            (["command", "record.start", "--args", '{"maxFrames":600}'], "record.start", {"maxFrames": 600}),
        ]
        for words, op, expected in cases:
            with self.subTest(words=words):
                code, called = self.run_cli(words)
                self.assertEqual(code, 0)
                self.assertEqual(called.args[1], {"op": op, "args": expected})

    def test_transport_flags_work_before_and_after_subcommand(self):
        for words in (["--url", "http://localhost:9000", "status", "--request-id", "same-1"],
                      ["status", "--url", "http://localhost:9000", "--request-id", "same-1"],
                      ["--url", "http://localhost:9000", "recipe", "list", "--request-id", "same-1"]):
            with self.subTest(words=words):
                _, call = self.run_cli(words)
                self.assertEqual(call.args[0], "http://localhost:9000")
                self.assertEqual(call.args[1]["requestId"], "same-1")

    def test_checked_file_is_sent_unchanged_only_once_and_does_not_run(self):
        test = {"id": "ledyba", "title": "Ledyba", "actions": [{"op": "step", "args": {"frames": 8}}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.json"
            path.write_text(json.dumps(test))
            for operation in ("validate", "save"):
                words = ["test", operation, *(["ledyba"] if operation == "save" else []), "--file", str(path)]
                code, call = self.run_cli(words)
                self.assertEqual(code, 0)
                expected = {"test": test, **({"name": "ledyba"} if operation == "save" else {})}
                self.assertEqual(call.args[1], {"op": "test." + operation, "args": expected})

    def test_invalid_test_files_never_send_and_report_argument_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.json"
            for raw in (b"[]", b"{", b"\xff", b" " * 262145, None):
                if raw is None:
                    path.unlink()
                else:
                    path.write_bytes(raw)
                args = self.parser().parse_args(["dev", "test", "validate", "--file", str(path), "--json"])
                output = io.StringIO()
                with mock.patch.object(devtools_cli, "request") as send, contextlib.redirect_stdout(output):
                    self.assertEqual(args.handler(args), 2)
                send.assert_not_called()
                self.assertEqual(json.loads(output.getvalue())["error"]["code"], "invalid_arguments")

    def test_checked_mutations_require_file_or_exact_run_id(self):
        for words in (["test", "validate"], ["test", "save", "x"], ["test", "cancel"], ["test", "export"]):
            with self.subTest(words=words), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                self.parser().parse_args(["dev", *words])

    def test_checked_start_response_never_becomes_accepted_proof(self):
        response = {"ok": True, "result": {"runId": "test-exact", "state": "starting", "acceptedProof": False}}
        args = self.parser().parse_args(["dev", "test", "start", "ledyba", "--json", "--summary"])
        output = io.StringIO()
        with mock.patch.object(devtools_cli, "request", return_value=response) as send, contextlib.redirect_stdout(output):
            self.assertEqual(args.handler(args), 0)
        send.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())["result"], response["result"])

    def test_bad_json_and_nonpositive_frames_do_not_send(self):
        for words in (["command", "step", "--args", "[]"], ["command", "step", "--args", "{"], ["step", "0"],
                      ["record", "start", "--max-frames", "0"], ["record", "start", "--max-events", "-1"],
                      ["record", "start", "--max-frames", "1.5"]):
            with self.subTest(words=words), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit), mock.patch.object(devtools_cli, "request") as send:
                    self.parser().parse_args(["dev", *words])
                send.assert_not_called()

    def test_record_start_limits_are_not_accepted_by_stop_or_export(self):
        for command in ("stop", "export"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.parser().parse_args(["dev", "record", command, "--max-frames", "600"])

    def test_service_error_has_nonzero_exit(self):
        code, _ = self.run_cli(["status", "--json"], {"ok": False, "error": {"code": "busy", "message": "already owned"}})
        self.assertEqual(code, 2)

    def test_summary_is_optional_and_does_not_change_transport(self):
        response = {"ok": True, "session": {"id": "session-test", "mode": "prepared"},
                    "result": {"frame": 73, "events": [{"kind": "native-event"}]}}
        for flags in ([], ["--summary"]):
            args = self.parser().parse_args(["dev", "status", "--json", *flags])
            output = io.StringIO()
            with mock.patch.object(devtools_cli, "request", return_value=response) as send, \
                    contextlib.redirect_stdout(output):
                self.assertEqual(args.handler(args), 0)
            self.assertEqual(send.call_args.args[1], {"op": "status", "args": {}})
            actual = json.loads(output.getvalue())
            if flags:
                self.assertFalse(actual["outputView"]["complete"])
                self.assertEqual(actual["result"]["events"]["reportedCount"], 1)
            else:
                self.assertEqual(actual, response)
        for words in (["--summary", "status"], ["recipe", "--summary", "list"],
                      ["recipe", "list", "--summary"]):
            with self.subTest(words=words):
                self.assertTrue(self.parser().parse_args(["dev", *words]).summary)

    def test_status_summary_compacts_resolved_profile_bytes(self):
        profiles = [{
            "fingerprint": 1000 + index,
            "resolved": True,
            "appliedOverrides": index,
            "sourceSha256": format(index + 1, "064x"),
            "lanes": [(f"{index + 10:02x}" * 72)] * 2,
            "resultHex": f"{index + 20:02x}" * 200,
            "requestHex": f"{index + 30:02x}" * 44,
        } for index in range(6)]
        response = {"ok": True, "session": {"id": "session-profiles", "state": "ready"},
                    "result": {"frame": 12, "nativeObservation": {
                        "profileFingerprints": [profile["fingerprint"] for profile in profiles],
                        "resolvedProfiles": profiles,
                    }}}
        before = copy.deepcopy(response)
        summary = devtools_cli.summarize_response(response)
        compact = summary["result"]["nativeObservation"]["resolvedProfiles"]
        self.assertEqual(compact["reportedCount"], 6)
        self.assertEqual(compact["fingerprints"], [profile["fingerprint"] for profile in profiles])
        self.assertEqual([profile["fingerprint"] for profile in compact["profiles"]],
                         compact["fingerprints"])
        encoded = json.dumps(summary, separators=(",", ":"))
        for field in ("lanes", "resultHex", "requestHex"):
            self.assertNotIn(field, compact["profiles"][0])
            self.assertIn(field, summary["outputView"]["omitted"]
                          ["result.nativeObservation.resolvedProfiles[*]"]["fields"])
        self.assertLess(len(encoded), 3000)
        self.assertEqual(response, before)

    def test_summary_keeps_exact_identity_motion_receipts_and_sample_clocks(self):
        actor = {"handle": {"value": 131072, "generation": 2}, "active": True,
                 "species": 165, "role": "WILD", "subjectIdentity": 0xF1234567,
                 "identityVerified": False, "identityChecks": {"in-manager": False},
                 "identityFailures": ["in-manager"], "logical": {"x": 550, "y": 381},
                 "render": {"x": 551, "y": 381}, "origin": {"x": 550, "y": 381},
                 "target": {"x": 552, "y": 381}, "motionKind": "HOP", "motionPhase": "TRAVEL",
                 "motionElapsed": 3, "motionDuration": 8, "commitSequence": 0xFFFFFFFF,
                 "lastDecision": 9, "lastDecisionName": "ENGINE_BUSY", "behaviorFingerprint": 999,
                 "movementPolicy": {"speed": 4}, "engineObject": {"raw": "detail"},
                 "sourceIdentity": {"raw": "detail"}, "version": 1}
        observation = {"boundary": "paused-native-cycle-end", "nativeCycle": 91,
                       "lastCompletedGameFrame": 73, "center": {"x": 550, "z": 381}}
        response = {"ok": True, "session": {"id": "s", "mode": "prepared", "state": "ready"},
                    "result": {"frame": 74, "actorFrame": 65, "nativeCycle": 92,
                               "context": {"mapId": 34, "fieldEpoch": 8}, "actors": [actor],
                               "party": [{"slot": 0, "species": 56, "personality": 99, "hp": 5,
                                          "status": 0, "moves": [1, 2, 0, 0]}],
                               "screenshot": {"url": "data:image/png;base64,AAAA", "path": "s/screen.png",
                                              "sha256": "abc", "frame": 70, "observation": {"nativeCycle": 86}},
                               "terrain": {"cells": [{"loaded": True, "collision": True},
                                                      {"loaded": True, "collision": False},
                                                      {"loaded": False}, {}],
                                           "observation": observation, "warps": [{"x": 550, "y": 381}]},
                               "operation": {"name": "spawn", "calls": [{"return": 1}],
                                             "events": [{"name": "native-call"}]},
                               "proofStatus": "diagnostic-only", "acceptedProof": False}}
        before = copy.deepcopy(response)
        result = devtools_cli.summarize_response(response)
        self.assertEqual(response, before, "display projection must not mutate its response")
        self.assertEqual(result["session"], response["session"])
        kept = result["result"]
        for key in ("frame", "actorFrame", "nativeCycle", "context", "party", "operation",
                    "proofStatus", "acceptedProof"):
            self.assertEqual(kept[key], response["result"][key])
        for key, value in actor.items():
            if key not in {"engineObject", "sourceIdentity", "version"}:
                self.assertEqual(kept["actors"][0][key], value)
        self.assertFalse(kept["actors"][0]["identityVerified"])
        self.assertNotIn("engineObject", kept["actors"][0])
        self.assertEqual(kept["screenshot"], {k: v for k, v in response["result"]["screenshot"].items() if k != "url"})
        self.assertEqual(kept["terrain"]["observation"], observation)
        self.assertNotIn("cells", kept["terrain"])
        counts = kept["terrain"]["cellSummary"]
        self.assertEqual([counts[k] for k in ("reported", "loaded", "unknown", "blocked")], [4, 2, 2, 1])
        self.assertIn("not prove", counts["scope"])
        self.assertEqual(result["outputView"]["scope"], "display only; not behavior proof")
        self.assertFalse(result["outputView"]["complete"])
        self.assertIn("result.actors[*]", result["outputView"]["omitted"])

    def test_summary_drops_only_reported_passing_checks(self):
        checks = {"manager": True, "mapGeneration": False, "pending": None,
                  "numeric": 1, "text": "true"}
        actors = [
            {"handle": {"value": 65536}, "identityVerified": False,
             "identityChecks": checks, "identityFailures": ["mapGeneration"]},
            {"handle": {"value": 65537}, "identityVerified": True,
             "identityChecks": {"manager": True}, "identityFailures": []},
            {"handle": {"value": 65538}},
            {"handle": {"value": 65539}, "identityVerified": None, "identityChecks": {}},
        ]
        response = {"ok": True, "result": {"actors": actors, "partyObservation": {
            "frame": 40, "nativeGetterChecks": [{"passed": True, "slot": 0},
                {"passed": False, "slot": 1}, {"slot": 2}, {"passed": 1, "slot": 3}]}}}
        summary = devtools_cli.summarize_response(response)
        actual = summary["result"]["actors"]
        self.assertEqual(actual[0]["identityChecks"], {k: v for k, v in checks.items() if v is not True})
        self.assertFalse(actual[0]["identityVerified"])
        self.assertEqual(actual[0]["identityFailures"], ["mapGeneration"])
        self.assertNotIn("identityChecks", actual[1])
        self.assertNotIn("identityVerified", actual[2])
        self.assertNotIn("identityChecks", actual[2])
        self.assertIsNone(actual[3]["identityVerified"])
        self.assertEqual(actual[3]["identityChecks"], {})
        omitted = summary["outputView"]["omitted"]
        self.assertEqual(omitted["result.actors[*].identityChecks"], {"count": 2})
        getters = summary["result"]["partyObservation"]["nativeGetterChecks"]
        self.assertEqual(getters["reportedCount"], 4)
        self.assertEqual(getters["nonPassing"], response["result"]["partyObservation"]["nativeGetterChecks"][1:])
        self.assertIn("not proof", summary["outputView"]["checks"])

    def test_summary_preserves_session_provenance_and_marks_cached_error_details(self):
        session = {"id": "session-example", "mode": "prepared", "state": "ready", "acceptedProof": False,
                   "startedAt": "2026-09-05T12:00:00Z", "directory": "/workspace/build/session-example",
                   "setupMutations": [{"op": "party", "frame": 6}], "setupMutationCount": 300,
                   "setupMutationsTruncated": True,
                   "identity": {"sessionId": "session-example", "startedAt": "2026-09-05T12:00:00Z",
                       "rom": {"path": "/workspace/test.nds", "copy": "/workspace/build/session-example/game.nds", "sha256": "a" * 64, "size": 100},
                       "save": {"path": "/workspace/test.sav", "sha256": "b" * 64},
                       "debugDescriptor": {"sha256": "c" * 64},
                       "toolInputs": [{"path": "tool.py", "sha256": "d" * 64}]},
                   "lastError": {"code": "spawn-failed", "message": "subject missing", "details": {"actors": []}}}
        result = devtools_cli.summarize_response({"ok": True, "session": session,
                    "result": {"lastError": session["lastError"]}})
        actual = result["session"]
        for key in ("id", "mode", "state", "acceptedProof", "startedAt", "setupMutationCount", "setupMutationsTruncated"):
            self.assertEqual(actual[key], session[key])
        self.assertEqual(actual["retainedSetupMutationCount"], 1)
        for key in ("rom", "save", "debugDescriptor"):
            self.assertEqual(actual["identity"][key]["sha256"], session["identity"][key]["sha256"])
        self.assertEqual(actual["identity"]["save"]["path"], "/workspace/test.sav")
        self.assertEqual(actual["identity"]["toolInputCount"], 1)
        self.assertNotIn("toolInputs", actual["identity"])
        self.assertNotIn("sessionId", actual["identity"])
        self.assertTrue(actual["lastError"]["detailsOmitted"])
        self.assertEqual(result["result"]["lastError"], actual["lastError"])
        self.assertIn("session.lastError", result["outputView"]["omitted"])
        # Conflicting identities must remain visible, not deduplicated away.
        session["identity"]["sessionId"] = "different-session"
        mismatch = devtools_cli.summarize_response({"session": session})
        self.assertEqual(mismatch["session"]["identity"]["sessionId"], "different-session")

    def _failed_checked_job(self):
        # The failed live-job manifest shape, with invented paths, hashes and
        # values. No save, ROM, screenshot or generated package data is used.
        digest = "a" * 64
        artifact = lambda name: {"path": "/workspace/build/test-example/" + name, "sha256": digest}
        identity = {"sessionId": "session-example", "startedAt": "2026-09-06T12:00:00Z",
            "rom": {"path": "/workspace/test.nds", "copy": "/workspace/build/session-example/game.nds", "sha256": digest, "size": 100},
            "save": {"path": "/workspace/test.sav", "copy": "/workspace/build/session-example/game.sav", "sha256": digest, "size": 20},
            "debugDescriptor": artifact("descriptor.json"),
            "toolInputs": [{"path": f"tools/overworld/devtools_fixture_{i}.py", "sha256": digest} for i in range(22)]}
        checks = [{"name": name, "passed": True, "returnCode": 0, "stdout": "package diagnostic " * 40, "stderr": ""}
                  for name in ("make-target-current", "sealed-build-manifest", "packaged-actor-system", "packaged-mount-system")]
        checks += [{"name": "overworld-product-outputs", "passed": True,
                    "outputs": {f"module{i}": {"output": artifact(f"output-{i}.bin"),
                        "packaged": artifact(f"overlay-{i}"), "matched": True} for i in range(12)}}]
        checks += [{"name": name, "passed": True, "bytes": "00" * 64, "returnAddress": 0x02000000}
                   for name in ("runtime-linked-symbol-inputs", "debug-descriptor-overlay",
                                "stock-main-queue-observation", "shared-devtools-isolated-startup")]
        return {"ok": True, "session": None, "result": {
            "runId": "test-example", "test": "devtools.actor-identity", "execution": "shared-devtools",
            "state": "failed", "phase": "setup", "action": "spawn-follower", "completedActions": 1, "totalActions": 4,
            "elapsedSeconds": 49.074, "observedFrames": 0, "nativeCycles": 1200, "lastProgressFrame": 700,
            "budgets": {"maxSeconds": 300, "maxFrames": 2000, "noProgressFrames": 300, "minObservedFrames": 16},
            "subjects": [{"id": "follower", "species": 56, "role": "FOLLOWER", "handle": {"value": 131079},
                          "subjectIdentity": 1923031320, "identityVerified": False, "identityFailures": ["presentationAttached"]}],
            "identity": identity, "passed": False, "acceptedProof": False,
            "evaluation": {"state": "failed", "passed": False, "acceptedProof": False,
                "observedFrames": 0, "sampledFrames": 0, "lastFrame": 735, "subjects": {},
                "requirements": ["shared.actor-identity.prepared-v1"],
                "assertions": [{"kind": "actor-field", "path": "presentationAttached", "value": True}],
                "failures": [{"code": "spawn-failed", "message": "native selection did not produce the exact follower", "frame": 735,
                              "details": {"omitted": True, "captureError": None, "scope": "see failure artifact"}}]},
            "fixtureProof": {"schemaVersion": 1, "passed": True, "eligible": True, "acceptedProof": False,
                "source": {"schema": "overworld-proof-inputs-v2", "sha256": digest, "fileCount": 30000, "byteCount": 100000,
                           "roots": {f"root{i}": {"sha256": digest, "fileCount": 1000, "byteCount": 10000} for i in range(30)}},
                "registration": {"evaluator": "current-actor-identity-v1", "proofLevel": "S3", "mode": "prepared",
                                 "minimumObservedFrames": 16, "claims": ["live-actor-identity"]},
                "fixture": {"schemaVersion": 1, "passed": True, "rom": artifact("test.nds"),
                            "buildManifest": artifact("build.json"), "checks": checks}},
            "proofAcceptance": {"eligible": True, "reason": "shared test did not complete successfully"},
            "manifest": artifact("manifest.json")["path"], "failureArtifact": artifact("failure.json"),
            "observationsArtifact": artifact("observations.jsonl"),
            "visualArtifact": {"screenshot": {**artifact("screen.png"), "frame": 731, "nativeCycle": 1857,
                                              "url": "data:image/png;base64,NOT_AN_IMAGE"}},
            "nextAction": "Review the saved result and exact failure before another run."}}

    def test_failed_checked_job_summary_keeps_decision_data_and_bounds_preflight_noise(self):
        response = self._failed_checked_job()
        response["result"]["attemptIdentity"] = {
            "schemaVersion": 1, "source": copy.deepcopy(response["result"]["fixtureProof"]["source"]),
            "testSourceSha256": "b" * 64, "files": {"save": {"path": "test.sav", "present": False}}}
        original = copy.deepcopy(response)
        output = io.StringIO()
        args = self.parser().parse_args(["dev", "test", "status", "--json", "--summary"])
        with mock.patch.object(devtools_cli, "request", return_value=response) as send, contextlib.redirect_stdout(output):
            self.assertEqual(args.handler(args), 0)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1], {"op": "test.status", "args": {}})
        summary = json.loads(output.getvalue())
        result = summary["result"]
        self.assertNotIn("roots", result["attemptIdentity"]["source"])
        self.assertEqual(result["attemptIdentity"]["source"]["rootCount"], 30)
        self.assertEqual(result["attemptIdentity"]["files"], response["result"]["attemptIdentity"]["files"])
        self.assertEqual(result["identity"]["toolInputCount"], 22)
        self.assertNotIn("toolInputs", result["identity"])
        for key in ("runId", "test", "state", "phase", "action", "completedActions", "totalActions", "elapsedSeconds",
                    "observedFrames", "nativeCycles", "lastProgressFrame", "budgets", "subjects", "passed", "acceptedProof",
                    "evaluation", "proofAcceptance", "manifest", "failureArtifact", "observationsArtifact", "nextAction"):
            self.assertEqual(result[key], response["result"][key], key)
        preflight = result["fixtureProof"]
        self.assertTrue(preflight["passed"])
        self.assertFalse(preflight["acceptedProof"])
        self.assertEqual(preflight["source"]["sha256"], "a" * 64)
        self.assertNotIn("roots", preflight["source"])
        self.assertEqual(preflight["source"]["rootCount"], 30)
        checks = preflight["fixture"]["checks"]
        self.assertEqual(checks["reportedCount"], 9)
        self.assertEqual(checks["passingCount"], 9)
        self.assertEqual(checks["nonPassing"], [])
        self.assertEqual(checks["passingNames"], [item["name"] for item in response["result"]["fixtureProof"]["fixture"]["checks"]])
        self.assertIn("not proof", checks["scope"])
        for path in ("result.identity.toolInputs", "result.fixtureProof.source.roots", "result.fixtureProof.fixture.checks"):
            self.assertIn(path, summary["outputView"]["omitted"])
        self.assertFalse(summary["outputView"]["complete"])
        self.assertLess(len(output.getvalue()), 7000, "checked status must stay near 2k tokens, not print package internals")
        self.assertEqual(response, original)
        # The default view is still byte-for-byte equivalent JSON data.
        full = io.StringIO()
        args = self.parser().parse_args(["dev", "test", "status", "--json"])
        with mock.patch.object(devtools_cli, "request", return_value=response), contextlib.redirect_stdout(full):
            self.assertEqual(args.handler(args), 0)
        self.assertEqual(json.loads(full.getvalue()), original)

    def test_checked_job_summary_preserves_nonpassing_checks_and_exact_errors(self):
        response = self._failed_checked_job()
        checks = response["result"]["fixtureProof"]["fixture"]["checks"]
        bad = [{"name": "failed", "passed": False, "outputs": {"wrong": "hash"}, "stdout": "required detail"},
               {"name": "unknown", "passed": None}, {"name": "numeric", "passed": 1},
               {"name": "missing", "stderr": "check never completed"}, "unexpected check"]
        checks.extend(bad)
        error = {"code": "native-call-failed", "message": "exact command error", "details": {
            "events": [1, 2], "samples": [{"frame": 7}], "lastError": {"details": {"required": True}}}}
        response["result"]["commandError"] = error
        response["result"]["evaluation"]["failures"] = [error]
        response["result"]["fixtureProof"].update(passed=False, eligible=False)
        result = devtools_cli.summarize_response(response)["result"]
        self.assertEqual(result["fixtureProof"]["fixture"]["checks"]["nonPassing"], bad)
        self.assertFalse(result["fixtureProof"]["passed"])
        self.assertFalse(result["fixtureProof"]["eligible"])
        self.assertEqual(result["commandError"], error)
        self.assertEqual(result["evaluation"]["failures"], [error])

    def test_realistic_eight_actor_status_has_a_bounded_compact_json_view(self):
        actors = []
        for slot in range(8):
            actors.append({
                "version": 2, "size": 88, "active": True, "species": 165 + slot,
                "form": 0, "level": 5, "role": "FOLLOWER" if slot == 7 else "WILD", "roleId": 1,
                "handle": {"value": 131072 + slot, "slot": slot, "generation": 2,
                           "fieldEpoch": 3, "mapGeneration": 4, "encounterGeneration": 5},
                "subjectIdentity": 0xF1234500 + slot, "identityVerified": slot != 0,
                "identityFailures": ["mapGeneration"] if slot == 0 else [],
                "identityChecks": {**{f"check{i}": True for i in range(18)}, "mapGeneration": slot != 0},
                "logical": {"x": 550 + slot, "y": 381}, "render": {"x": 550 + slot, "y": 381},
                "origin": {"x": 550 + slot, "y": 381}, "target": {"x": 552 + slot, "y": 381},
                "motionKind": "HOP", "motionPhase": "MOVING", "motionElapsed": 3, "motionDuration": 8,
                "motionKindId": 2, "motionPhaseId": 1, "lane": "OWNER", "laneId": 0,
                "commitSequence": 9, "reservationId": 7, "inputOwnership": 0, "streamState": 0,
                "authorityGeneration": 2, "engineAnchorGeneration": 2, "presentationGeneration": 2,
                "presentationAttached": True, "presentationState": 1, "controllerState": 0,
                "lastCommandSequence": 0, "lastIntent": 2, "lastDecision": 0, "lastDecisionName": "OK",
                "lastCancelReason": 0, "lastCancelReasonName": "OK", "behaviorFingerprint": 12345678,
                "matchedLayerMask": 32,
                "movementPolicy": {name: i for i, name in enumerate(("direction", "counter", "speed", "base", "spotState",
                    "skid", "turn", "resume", "chain", "ticks", "action", "variance", "buffered", "stop", "pending", "pendingSkid", "streamState"))},
                "engineObject": {f"raw{i}": 38371328 for i in range(18)},
                "engineIdentity": {f"raw{i}": 38371328 for i in range(18)},
                "sourceIdentity": {f"raw{i}": 38371328 for i in range(18)},
            })
        response = {"ok": True, "session": {"id": "session-size", "mode": "normal", "state": "ready", "acceptedProof": False,
            "identity": {"rom": {"sha256": "a" * 64, "path": "/workspace/test.nds"}, "save": {"sha256": "b" * 64, "path": "/workspace/test.sav"},
                "debugDescriptor": {"sha256": "c" * 64}, "toolInputs": [{"path": f"tools/overworld/tool{i}.py", "sha256": "d" * 64} for i in range(12)]}},
            "result": {"frame": 800, "nativeCycle": 1600, "actorFrame": 711, "context": {"mapId": 34, "fieldEpoch": 3, "mapGeneration": 4},
                "actors": actors, "party": [{"slot": i, "species": 56, "personality": 123 + i, "hp": 10, "maxHp": 20,
                                             "moves": [10, 43, 116, 343], "level": 10, "identityVerified": True} for i in range(6)],
                "partyObservation": {"frame": 800, "boundary": "main-task-queue-completion", "nativeGetterChecks": [
                    {"slot": i // 3, "field": ("species", "hp", "level")[i % 3], "native": 10, "decoded": 10,
                     "passed": True, "boundary": "natural-GetMonData-return"} for i in range(18)]},
                "terrain": {"cells": [{"x": x, "y": y, "loaded": True, "collision": False, "attribute": 0} for x in range(15) for y in range(15)]},
                "events": [{"frame": i, "kind": "command", "data": {"op": "step", "ok": True}} for i in range(120)]}}
        before = copy.deepcopy(response)
        args = self.parser().parse_args(["dev", "status", "--json", "--summary"])
        output = io.StringIO()
        with mock.patch.object(devtools_cli, "request", return_value=response), contextlib.redirect_stdout(output):
            self.assertEqual(args.handler(args), 0)
        text = output.getvalue()
        self.assertLess(len(text), 12500, "the agent summary must not grow back into an internals dump")
        self.assertLess(len(text), len(json.dumps(response, separators=(",", ":"))) * .4)
        self.assertEqual(text.count("\n"), 1)
        self.assertEqual(response, before)
        summary = json.loads(text)
        for expected, actual in zip(actors, summary["result"]["actors"]):
            for key in ("handle", "subjectIdentity", "species", "role", "logical", "render", "origin", "target",
                        "motionKind", "motionPhase", "motionElapsed", "motionDuration", "movementPolicy", "lastDecision",
                        "identityVerified", "identityFailures"):
                self.assertEqual(actual[key], expected[key])
        omitted = summary["outputView"]["omitted"]
        self.assertEqual(omitted["result.actors[*].identityChecks"]["count"], 151)
        self.assertLess(len(json.dumps(omitted)), 1000)
        self.assertFalse(any("[0]" in path for path in omitted))

    def test_summary_keeps_service_failure_and_nested_snapshot(self):
        error = {"code": "wrong-subject", "message": "identity failed", "details": {"events": [1, 2]}}
        response = {"ok": False, "session": None, "error": error}
        args = self.parser().parse_args(["dev", "status", "--json", "--summary"])
        output = io.StringIO()
        with mock.patch.object(devtools_cli, "request", return_value=response), contextlib.redirect_stdout(output):
            self.assertEqual(args.handler(args), 2)
        self.assertEqual(json.loads(output.getvalue())["error"], error)
        nested = devtools_cli.summarize_response({"ok": True, "result": {"snapshot": {
            "screenshot": {"url": "/api/v2/devtools/artifacts/s/screen.png", "frame": 7},
            "samples": [{"frame": 1}], "actors": [{"handle": 1, "subjectIdentity": 3}],
        }}})["result"]["snapshot"]
        self.assertEqual(nested["screenshot"]["frame"], 7)
        self.assertTrue(nested["screenshot"]["url"].startswith("/api/"))
        self.assertTrue(nested["samples"]["itemsOmitted"])
        self.assertEqual(nested["actors"][0]["subjectIdentity"], 3)

    def test_positional_and_flag_frames_are_not_silently_combined(self):
        args = self.parser().parse_args(["dev", "step", "8", "--frames", "3"])
        with mock.patch.object(devtools_cli, "request") as send, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(args.handler(args), 2)
        send.assert_not_called()

    def test_http_body_preserves_exact_request_id(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b'{"ok":true,"result":{}}'
        with mock.patch.object(devtools_cli.urllib.request, "urlopen", return_value=response) as opened:
            self.assertTrue(devtools_cli.request("http://localhost:8766", {"op": "step", "args": {"frames": 8}, "requestId": "same-1"})["ok"])
        req = opened.call_args.args[0]
        self.assertEqual(req.full_url, "http://localhost:8766/api/v2/devtools")
        self.assertEqual(json.loads(req.data)["requestId"], "same-1")
        self.assertEqual(req.method, "POST")

    def test_network_error_is_not_automatically_retried(self):
        with mock.patch.object(devtools_cli.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")) as opened:
            with self.assertRaisesRegex(ValueError, "Request ID: existing-id"):
                devtools_cli.request("http://localhost:8766", {"op": "spawn", "requestId": "existing-id"})
        self.assertEqual(opened.call_count, 1)

    def test_invalid_and_non_json_http_responses_fail(self):
        for raw in (b"html", b"[]", b'{"ok":"yes"}'):
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = raw
            with self.subTest(raw=raw), mock.patch.object(devtools_cli.urllib.request, "urlopen", return_value=response):
                with self.assertRaises(ValueError):
                    devtools_cli.request("http://localhost:8766", {"op": "help"})


if __name__ == "__main__":
    unittest.main()
