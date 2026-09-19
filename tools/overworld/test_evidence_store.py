"""Proof storage regressions: no emulator or user save is needed."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest import mock

from tools.overworld import control
from tools.overworld.evidence_store import artifact_directory, require_command_output
from tools.overworld.validation import ValidationFailure


class EvidenceStorageTests(unittest.TestCase):
    def test_success_failure_and_timeout_keep_both_exact_streams(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = artifact_directory(root)
            for index, outcome in enumerate(("success", "failure", "timeout")):
                with self.subTest(outcome=outcome):
                    stdout = b"FIRST diagnostic\r\n" + b"x" * 9000 + b"\xff"
                    stderr = b"FIRST error\r\n" + b"y" * 9000 + b"\xfe"
                    completed = subprocess.CompletedProcess(["collector"],
                        0 if outcome == "success" else 1, stdout, stderr)
                    effect = subprocess.TimeoutExpired(["collector"], 120,
                        output=stdout, stderr=stderr) if outcome == "timeout" else None
                    with (mock.patch.object(control, "REPO", root),
                          mock.patch.object(control.subprocess, "run", return_value=completed,
                                            side_effect=effect)):
                        record = control._run_command(["collector"], "exit-zero",
                            log_directory=directory, log_index=index)
                    self.assertEqual(record["passed"], outcome == "success")
                    if outcome == "timeout":
                        self.assertIsNone(record["returnCode"])
                        self.assertIn("exceeded", record["resultError"])
                    for name, data in (("stdout", stdout), ("stderr", stderr)):
                        saved = record[name + "Artifact"]
                        self.assertEqual((root / saved["path"]).read_bytes(), data)
                        self.assertEqual(saved["size"], len(data))
                        self.assertEqual(saved["sha256"], hashlib.sha256(data).hexdigest())
                        self.assertEqual(len(record[name + "Tail"]), 2000)
                    require_command_output(record, root)

    def test_long_failed_json_survives_in_run_manifest_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stdout = json.dumps({"passed": False, "error": "FIRST specific failure",
                                 "sampling": "x" * 50000}).encode()
            stderr = b"FIRST traceback\n" + b"y" * 8000
            # A real short child proves byte capture, not only a mocked result.
            command = [sys.executable, "-c", "import json, sys; "
                       "sys.stdout.write(json.dumps({'passed': False, "
                       "'error': 'FIRST specific failure', 'sampling': 'x' * 50000})); "
                       "sys.stderr.buffer.write(b'FIRST traceback\\n' + b'y' * 8000); sys.exit(1)"]
            scenario = {"id": "case", "status": "active", "proofLevel": "S1", "costTier": 1,
                        "fixture": {"rom": "test.nds"}, "stop": {"frameBudget": 100},
                        "adapter": {"kind": "command-sequence", "commands": [command],
                                    "result": "json-passed"}}
            args = SimpleNamespace(scenario_id="case", evidence=None, dry_run=False,
                                   json=True, manifest_output=None)
            with (mock.patch.object(control, "REPO", root),
                  mock.patch.object(control, "_load_contracts", return_value=({}, {"case": scenario})),
                  mock.patch.object(control, "_scenario_inputs", return_value={"source": "same"}),
                  mock.patch("tools.overworld.runs.git_provenance", return_value={}),
                  mock.patch("tools.overworld.runs.emulator_record", return_value={}),
                  mock.patch.object(control, "_json")):
                self.assertEqual(control._scenario_run(args), 1)
            document = json.loads(next((root / "build/overworld-runs").glob("**/*.json")).read_text())
            record = document["result"]["steps"][0]
            self.assertFalse(document["result"]["passed"])
            self.assertNotIn("FIRST specific failure", record["stdoutTail"])
            self.assertNotIn("FIRST traceback", record["stderrTail"])
            self.assertEqual((root / record["stdoutArtifact"]["path"]).read_bytes(), stdout)
            self.assertEqual((root / record["stderrArtifact"]["path"]).read_bytes(), stderr)
            # No large result payload is copied into the manifest step.
            self.assertLess(len(json.dumps(record)), 6000)

    def test_logs_cannot_be_overwritten_or_changed_without_rejection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = artifact_directory(root)
            with mock.patch.object(control, "REPO", root):
                record = control._command_record(["collector"],
                    subprocess.CompletedProcess([], 0, b"first", b""), log_directory=directory)
                second = control._command_record(["collector"],
                    subprocess.CompletedProcess([], 0, b"other", b""), log_directory=directory)
            self.assertFalse(second["passed"])
            self.assertEqual((root / record["stdoutArtifact"]["path"]).read_bytes(), b"first")
            require_command_output(record, root)
            path = root / record["stdoutArtifact"]["path"]
            path.write_bytes(b"other")  # Same size: the digest must reject this.
            with self.assertRaisesRegex(ValidationFailure, "identity differs"):
                require_command_output(record, root)
            path.unlink()
            with self.assertRaises(OSError):
                require_command_output(record, root)
            del record["stdoutArtifact"]
            with self.assertRaisesRegex(ValidationFailure, "missing or invalid"):
                require_command_output(record, root)

    def test_archive_failure_cannot_be_overridden_by_passed_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = artifact_directory(root)
            (directory / "0-stdout.log").write_bytes(b"previous")
            completed = subprocess.CompletedProcess([], 0, b'{"passed":true}', b"still useful")
            with (mock.patch.object(control, "REPO", root),
                  mock.patch.object(control.subprocess, "run", return_value=completed)):
                record = control._run_command(["collector"], "json-passed", log_directory=directory)
            self.assertFalse(record["passed"])
            self.assertIn("could not be preserved", record["resultError"])
            self.assertEqual((root / record["stderrArtifact"]["path"]).read_bytes(), b"still useful")

    def test_failed_result_parser_keeps_logs_in_failed_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scenario = {"id": "case", "status": "active", "proofLevel": "S1", "costTier": 1,
                        "fixture": {"rom": "test.nds"}, "stop": {"frameBudget": 100},
                        "adapter": {"kind": "command-sequence", "commands": [["collector"]],
                                    "result": "json-passed"}}
            args = SimpleNamespace(scenario_id="case", evidence=None, dry_run=False,
                                   json=True, manifest_output=None)
            completed = subprocess.CompletedProcess([], 0, b'{"passed":true}', b"details")
            # Raise after the real command-record path has saved the output.
            original_loads = json.loads
            def reject_result(value, *args, **kwargs):
                if value == completed.stdout:
                    raise FileNotFoundError("result parser failed")
                return original_loads(value, *args, **kwargs)
            with (mock.patch.object(control, "REPO", root),
                  mock.patch.object(control, "_load_contracts", return_value=({}, {"case": scenario})),
                  mock.patch.object(control, "_scenario_inputs", return_value={"source": "same"}),
                  mock.patch("tools.overworld.runs.git_provenance", return_value={}),
                  mock.patch("tools.overworld.runs.emulator_record", return_value={}),
                  mock.patch.object(control.subprocess, "run", return_value=completed),
                  mock.patch.object(control.json, "loads", side_effect=reject_result),
                  mock.patch.object(control, "_json")):
                self.assertEqual(control._scenario_run(args), 1)
            document = json.loads(next((root / "build/overworld-runs").glob("**/*.json")).read_text())
            record = document["result"]["steps"][0]
            self.assertFalse(document["result"]["passed"])
            self.assertIn("result parser failed", record["resultError"])
            self.assertEqual(record["failureStage"], "runtime")
            for name in ("stdout", "stderr"):
                self.assertEqual((root / record[name + "Artifact"]["path"]).read_bytes(),
                                 getattr(completed, name))

    def test_malformed_recording_is_preserved_and_gets_failed_manifest(self):
        from tools.overworld.runs import write_run_manifest
        from tools.overworld.validation import ValidationFailure
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / "latest.json"
            raw.write_bytes(b"{invalid")
            scenario = {"id": "case", "status": "active", "proofLevel": "S1", "costTier": 1,
                        "fixture": {"rom": "test.nds"}, "stop": {"frameBudget": 100},
                        "adapter": {"kind": "actor-observation", "checks": [], "commands": []}}
            args = SimpleNamespace(scenario_id="case", evidence=raw, dry_run=False,
                                   json=True, manifest_output=None)
            with (mock.patch.object(control, "REPO", root),
                  mock.patch.object(control, "_load_contracts", return_value=({}, {"case": scenario})),
                  mock.patch.object(control, "_scenario_inputs", return_value={"source": "same"}),
                  mock.patch("tools.overworld.runs.source_record", return_value={"content": "same"}),
                  mock.patch("tools.overworld.runs.git_provenance", return_value={}),
                  mock.patch("tools.overworld.runs.emulator_record", return_value={}),
                  mock.patch.object(control, "load_trace_schema", return_value={}),
                  mock.patch.object(control, "load_evidence", side_effect=ValidationFailure("invalid recording")),
                  mock.patch.object(control, "_json")):
                self.assertEqual(control._scenario_run(args), 1)
            manifests = list((root / "build/overworld-runs").glob("**/*.json"))
            self.assertEqual(len(manifests), 1)
            document = json.loads(manifests[0].read_text())
            self.assertFalse(document["result"]["passed"])
            saved = document["result"]["steps"][0]["evidence"]["path"]
            self.assertEqual((root / saved).read_bytes(), b"{invalid")

    def test_observer_changes_during_run_cannot_receive_new_identity_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scenario = {"id": "case", "status": "active", "proofLevel": "S1", "costTier": 1,
                        "fixture": {"rom": "test.nds"}, "stop": {"frameBudget": 100},
                        "adapter": {"kind": "command-sequence", "commands": [["true"]], "result": "exit-zero"}}
            args = SimpleNamespace(scenario_id="case", evidence=None, dry_run=False,
                                   json=True, manifest_output=None)
            with (mock.patch.object(control, "REPO", root),
                  mock.patch.object(control, "_load_contracts", return_value=({}, {"case": scenario})),
                  mock.patch.object(control, "_scenario_inputs", side_effect=[{"source": "before"}, {"source": "after"}]),
                  mock.patch("tools.overworld.runs.source_record", return_value={"content": "after"}),
                  mock.patch("tools.overworld.runs.git_provenance", return_value={}),
                  mock.patch("tools.overworld.runs.emulator_record", return_value={}),
                  mock.patch.object(control, "_run_command", return_value={"passed": True, "returnCode": 0}),
                  mock.patch.object(control, "_json")):
                self.assertEqual(control._scenario_run(args), 1)
            document = json.loads(next((root / "build/overworld-runs").glob("**/*.json")).read_text())
            self.assertFalse(document["result"]["passed"])
            self.assertEqual(document["inputIdentityAtStart"], {"source": "before"})
            self.assertEqual(document["result"]["steps"][-1]["resultKind"], "input-identity-error")

    def test_repeated_runs_keep_both_original_observations(self):
        from tools.overworld.evidence_store import archive_step, artifact_directory
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            staging = root / "latest.json"
            records = []
            for data in (b'{"frame": 1}', b'{"frame": 2}'):
                staging.write_bytes(data)
                step = {"evidence": {"path": "latest.json", "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()}}
                archive_step(step, root, artifact_directory(root), 0)
                records.append(step["evidence"])
            self.assertNotEqual(records[0]["path"], records[1]["path"])
            self.assertEqual((root / records[0]["path"]).read_bytes(), b'{"frame": 1}')
            self.assertEqual((root / records[1]["path"]).read_bytes(), b'{"frame": 2}')

    def test_changed_artifact_is_not_archived_as_original_proof(self):
        from tools.overworld.evidence_store import archive_step, artifact_directory
        from tools.overworld.validation import ValidationFailure
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "latest.png").write_bytes(b"changed")
            step = {"visualArtifact": {"path": "latest.png", "size": 3,
                    "sha256": hashlib.sha256(b"old").hexdigest()}}
            with self.assertRaises(ValidationFailure):
                archive_step(step, root, artifact_directory(root), 0)

    def test_parallel_fixed_output_collectors_fail_without_waiting(self):
        from tools.overworld.evidence_store import scenario_lock
        from tools.overworld.validation import ValidationFailure
        with tempfile.TemporaryDirectory() as folder:
            with scenario_lock(Path(folder)):
                with self.assertRaises(ValidationFailure):
                    with scenario_lock(Path(folder)):
                        self.fail("second collector entered")
            with scenario_lock(Path(folder)):
                pass

    def test_recheck_uses_run_evidence_not_latest_staging_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "saved.json").write_text("{}")
            (root / "latest.json").write_text("different")
            record = {"path": "saved.json", "size": 2,
                      "sha256": hashlib.sha256(b"{}").hexdigest()}
            positive = {"passed": True, "resultKind": "actor-observation"}
            negative = {"passed": True}
            evaluation = {**positive, "subjectNegativeControl": negative,
                          "behaviorNegativeControl": negative, "evidence": record}
            scenario = {"adapter": {"kind": "actor-observation", "evidence": "latest.json"}}
            with (mock.patch.object(control, "REPO", root),
                  mock.patch.object(control, "load_evidence", return_value={}) as loader,
                  mock.patch.object(control, "load_debug_descriptor", return_value={}),
                  mock.patch.object(control, "require_descriptor_identity"),
                  mock.patch.object(control, "require_scenario_provenance"),
                  mock.patch.object(control, "_actor_evidence_session", return_value="session"),
                  mock.patch.object(control, "evaluate_scenario_evidence", return_value=positive),
                  mock.patch.object(control, "evaluate_subject_negative_control", return_value=negative),
                  mock.patch.object(control, "evaluate_behavior_negative_control", return_value=negative)):
                self.assertIsNone(control._roadmap_actor_evaluation_rejection(scenario, [evaluation]))
                self.assertEqual(loader.call_args.args[0], root / "saved.json")


if __name__ == "__main__":
    unittest.main()
