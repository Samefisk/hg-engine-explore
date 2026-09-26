"""Host rejection controls for shared-job proof and retired runtime dispatch."""
from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
import io
import json
import struct
from pathlib import Path
import tempfile
import sys
import threading
import time
import zlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.test_devtools_test_contract import recipe, snapshot
from tools.overworld.validation import ValidationFailure, cross_validate, validate_runtime_migration, validate_scenario
from scripts.verify_overworld_runtime_fixture import _run_bounded


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


class SharedProofTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in ("tools/overworld", "tests/overworld/test-recipes", "build/overworld-devtools/test-proof"):
            (self.root / path).mkdir(parents=True)
        self.test = recipe(); self.test["mode"] = "prepared"
        self.test["requirements"] = ["shared.actor-identity.prepared-v1"]
        self.test = validate_test(self.test)
        source = self.root / "tests/overworld/test-recipes/test.actor.json"
        source.write_text(json.dumps(self.test))
        self.registration = {"evaluator": "current-actor-identity-v1", "proofLevel": "S3", "mode": "prepared",
            "recipeSha256": sha(source), "requirements": self.test["requirements"], "claims": ["live-actor-identity"],
            "minimumObservedFrames": 2, "scope": "identity only"}
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
            "sharedTests": {self.test["id"]: self.registration}}))
        identity = {"sessionId": "session-proof"}
        for key, path in (("rom", "test.nds"), ("save", "test.sav"), ("debugDescriptor", "build/overworld-system.debug.json")):
            file = self.root / path; file.write_bytes(b"host fixture, not a game image")
            identity[key] = {"path": str(file), "sha256": sha(file), "size": file.stat().st_size}
        start = self.current(0)
        evaluator = TestEvaluator(self.test); evaluator.observe(start, count_frame=False)
        binding = evaluator.bind("subject", start)
        samples = [self.current(1), self.current(2)]
        for sample in samples: evaluator.observe(sample)
        self.rows = [{"phase": "setup", "initialSnapshot": start},
                     {"phase": "setup", "action": "bind-subject", "command": "bind", "snapshot": start, "receipt": binding},
                     {"phase": "observe", "action": "sample", "samples": samples, "events": [], "completedGameFrames": 2}]
        # Bind is a declared action in the retained contract, not a worker label.
        self.test["setup"] = [{"id": "bind-subject", "op": "bind", "args": {"subject": "subject"},
            "budget": {"maxSeconds": 1, "maxFrames": 1, "noProgressFrames": 1}}]
        source.write_text(json.dumps(self.test)); self.registration["recipeSha256"] = sha(source)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
            "sharedTests": {self.test["id"]: self.registration}}))
        self.observations = self.root / "build/overworld-devtools/test-proof/observations.jsonl"
        self.write_rows()
        self.record = {"runId": "test-proof", "sessionId": "session-proof", "state": "completed", "passed": True,
            "execution": "shared-devtools", "identity": identity, "evaluation": evaluator.finish(),
            "testSourceSha256": sha(source), "observationsArtifact": self.artifact(),
            "fixtureProof": {"passed": True, "eligible": True, "source": {"hash": "source"},
                "registration": self.registration, "testSourceSha256": sha(source),
                "fixture": {"passed": True, "rom": {"sha256": identity["rom"]["sha256"]}}}}

    def current(self, frame):
        current = snapshot(frame); current["context"]["mapId"] = 33
        current["actors"][0].update(sourceIdentity={"active": 1, "species": 165, "personality": 123,
            "encounter_generation": 1, "object_id": 0xE0, "map_id": 33, "object": 0x020A0100},
            engineIdentity={"in_manager": True, "active": True, "pointer": 0x020A0100, "manager_index": 0,
                "current_manager": 0x020B0000, "object_manager": 0x020B0000, "script_id": 2074,
                "object_id": 0xE0, "object_map_id": 33, "current_map_id": 33})
        return current

    def write_rows(self): self.observations.write_text("".join(json.dumps(row) + "\n" for row in self.rows))
    def artifact(self): return {"path": str(self.observations), "sha256": sha(self.observations), "size": self.observations.stat().st_size}
    def finish(self, record=None):
        with patch.object(control, "source_record", return_value={"hash": "source"}):
            return control.finalize_shared_test(self.test, self.record if record is None else record, self.root)

    def test_narrow_current_identity_proof_replays_and_rejects_subject_controls(self):
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        self.assertEqual(result["proofAcceptance"]["claims"], ["live-actor-identity"])
        self.assertTrue(all(item["rejected"] for item in result["proofAcceptance"]["controls"].values()))

    def test_gzip_uses_same_replay_and_rejects_hash_or_integrity_changes(self):
        from tools.overworld.devtools_evidence_stream import open_observations
        plain = self.finish()
        compressed = self.observations.with_name("observations.jsonl.gz")
        with open_observations(compressed, "xt") as stream:
            stream.write(self.observations.read_text())
        self.observations = compressed
        self.record["observationsArtifact"] = self.artifact()
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        self.assertEqual(result, plain)
        compressed.write_bytes(compressed.read_bytes()[:-4])
        self.assertFalse(self.finish()["acceptedProof"])
        self.record["observationsArtifact"] = self.artifact()
        self.assertFalse(self.finish()["acceptedProof"])

    def test_s3_image_is_irrelevant_and_cannot_supply_unmeasured_claims(self):
        expected = self.finish()
        image = self.root / "unrelated.png"
        image.write_bytes(SharedLedybaProofTests.png_bytes())
        self.record["visualArtifact"] = {"screenshot": {"path": str(image), "sha256": sha(image),
            "frame": 0, "nativeCycle": 0}}
        self.assertEqual(self.finish(), expected)
        image.write_bytes(b"changed optional image")
        self.assertEqual(self.finish(), expected)
        image.write_bytes(SharedLedybaProofTests.png_bytes())
        for claim in ("rendered-motion", "terrain-selection"):
            with self.subTest(claim=claim):
                self.registration["claims"] = ["live-actor-identity", claim]
                (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
                    "sharedTests": {self.test["id"]: self.registration}}))
                self.assertFalse(self.finish()["acceptedProof"])

    def configure_soak(self, frames=5000):
        self.registration.update(proofLevel="S5", minimumObservedFrames=frames)
        self.test["budgets"].update(maxFrames=max(frames, 20), minObservedFrames=frames, maxSeconds=3600)
        self.test["actions"] = [{"id": "sample-" + str(start), "op": "step",
            "args": {"frames": min(500, frames + 1 - start), "keys": []},
            "budget": {"maxSeconds": 300, "maxFrames": min(500, frames + 1 - start),
                       "noProgressFrames": min(500, frames + 1 - start)}} for start in range(1, frames + 1, 500)]
        source = self.root / "tests/overworld/test-recipes/test.actor.json"
        source.write_text(json.dumps(self.test))
        self.registration["recipeSha256"] = sha(source)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
            "sharedTests": {self.test["id"]: self.registration}}))
        self.record["testSourceSha256"] = sha(source)
        self.record["fixtureProof"]["testSourceSha256"] = sha(source)

    def test_identity_soak_requires_5000_continuous_real_subject_samples(self):
        self.configure_soak()
        self.rows = self.rows[:2] + [{"phase": "observe", "action": "sample-" + str(start),
            "samples": [self.current(frame) for frame in range(start, min(start + 500, 5001))],
            "events": [], "completedGameFrames": min(500, 5001 - start)}
            for start in range(1, 5001, 500)]
        self.write_rows(); self.record["observationsArtifact"] = self.artifact()
        self.record["evaluation"] = control._replay_shared_test(self.test, self.rows)
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        self.assertEqual(result["proofAcceptance"]["proofLevel"], "S5")
        self.assertEqual(result["proofAcceptance"]["observedFrames"], 5000)
        self.record["visualArtifact"] = {"screenshot": {"path": "/unrelated/not-present.png",
            "sha256": "not an image digest", "frame": -1}}
        self.assertEqual(self.finish(), result, "S5 proof uses native samples, never image metadata")
        # An unmeasured boundary must not hide a gap halfway through a soak.
        for row in self.rows[7:]:
            for sample in row["samples"]: sample["frame"] += 1
        self.rows.insert(7, {"phase": "observe", "boundarySnapshot": self.current(2501)})
        self.write_rows(); self.record["observationsArtifact"] = self.artifact()
        self.record["evaluation"] = control._replay_shared_test(self.test, self.rows)
        self.assertTrue(self.record["evaluation"]["passed"])
        self.assertFalse(self.finish()["acceptedProof"])

    def test_short_soak_registration_and_unmeasured_visual_claim_rejected(self):
        self.configure_soak(frames=2)
        self.assertFalse(self.finish()["acceptedProof"])
        self.registration["proofLevel"] = "S4"
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
            "sharedTests": {self.test["id"]: self.registration}}))
        self.assertFalse(self.finish()["acceptedProof"])

    def test_failure_cancel_missing_preflight_or_evaluation_cannot_pass(self):
        for mutate in (lambda r: r.update(state="canceled"), lambda r: r.update(passed=False),
                       lambda r: r.pop("fixtureProof"), lambda r: r["evaluation"].update(observedFrames=99),
                       lambda r: r["identity"].update(sessionId="other")):
            record = deepcopy(self.record); mutate(record)
            self.assertFalse(self.finish(record)["acceptedProof"])

    def test_native_session_identity_is_required_without_an_image(self):
        for session_id in (None, "", "unscoped", "../session-other", "session-other/child"):
            with self.subTest(session_id=session_id):
                record = deepcopy(self.record)
                record["sessionId"] = record["identity"]["sessionId"] = session_id
                self.assertFalse(self.finish(record)["acceptedProof"])

    def test_artifact_tamper_and_fake_identity_boolean_rejected(self):
        self.observations.write_text("{}\n")
        self.assertFalse(self.finish()["acceptedProof"])
        self.write_rows()
        self.rows[-1]["samples"][0]["actors"][0]["engineIdentity"]["in_manager"] = False
        self.write_rows(); self.record["observationsArtifact"] = self.artifact()
        self.assertFalse(self.finish()["acceptedProof"])

    def test_product_recipe_or_fixture_changes_reject(self):
        with patch.object(control, "source_record", return_value={"hash": "changed"}):
            self.assertFalse(control.finalize_shared_test(self.test, self.record, self.root)["acceptedProof"])
        (self.root / "test.nds").write_bytes(b"changed")
        self.assertFalse(self.finish()["acceptedProof"])

    def test_unregistered_tool_test_does_not_gain_proof_by_passing(self):
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text("{}")
        result = self.finish()
        self.assertTrue(result["passed"])
        self.assertFalse(result["acceptedProof"])


class SharedPoolProofTests(unittest.TestCase):
    """Controller replay and rejection, never a live-game pass."""
    write_rows = SharedProofTests.write_rows
    artifact = SharedProofTests.artifact
    current = SharedProofTests.current

    def setUp(self):
        SharedProofTests.setUp(self)
        from tools.overworld.test_devtools_spawn_measurement import landing_stream, AUTHORED
        from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE
        self.inputs = {"pool-spawn-v1": {"schema": SCHEMA, "sourceSha256": SOURCE, "authoredProfiles": AUTHORED}}
        self.test.update(mode="normal", requirements=[control._POOL_REQUIREMENT],
            measurements=[{"kind": "pool-spawn-v1", "subject": "subject"}],
            assertions=[{"kind": "measurement-complete", "measurement": "pool-spawn-v1"}])
        self.test["subjects"][0]["acquire"] = "spawn"
        self.test["budgets"].update(maxFrames=100, minObservedFrames=16)
        self.test = validate_test(self.test)
        self.registration.update(evaluator="pool-spawn-v1", proofLevel="S3", mode="normal",
            requirements=self.test["requirements"], minimumObservedFrames=16, claims=control._POOL_CLAIMS,
            recorderControlRequirement="legacy.live-observer-controls")
        source = self.root / "tests/overworld/test-recipes/test.actor.json"
        source.write_text(json.dumps(self.test))
        self.registration["recipeSha256"] = sha(source)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps({
            "sharedTests": {self.test["id"]: self.registration}}))
        stream = landing_stream()
        # Give the synthetic 8-frame Hop the same bound-subject floor as the
        # registered scenario. Idle frames add no completed motion credit.
        stream.sequence += 1
        for _ in range(10): stream.append()
        items = stream.items
        for sample, _ in items:
            for actor in sample["actors"]: actor["engineIdentity"]["manager_index"] = 0
        attachment = deepcopy(next(e for e in items[1][1] if e["kind"] == "native"))
        attachment["data"]["event"] = "ACTOR_ATTACHED"
        for _, events in items:
            for event in events:
                if event["kind"] == "native": event["data"]["sequence"] += 1
        items[1][1].insert(0, attachment)
        binding = select_current_actor(items[1][0], items[1][0]["actors"][0])
        self.rows = [{"phase": "setup", "initialSnapshot": items[0][0]},
            {"phase": "setup", "samples": [items[1][0]], "snapshot": items[1][0],
             "events": items[1][1], "completedGameFrames": 1},
            {"phase": "setup", "command": "bind", "action": "bind-subject", "snapshot": items[1][0], "receipt": binding},
            {"phase": "observe", "samples": [s for s, _ in items[2:]], "snapshot": items[-1][0],
             "events": [e for _, events in items[2:] for e in events], "completedGameFrames": len(items) - 2}]
        self.write_rows()
        evaluation = self.replay()
        self.assertTrue(evaluation["passed"], evaluation)
        self.record.update(test=self.test["id"], evaluation=evaluation, observationsArtifact=self.artifact(),
                           testSourceSha256=sha(source))
        self.record["fixtureProof"].update(registration=self.registration, testSourceSha256=sha(source))

    def replay(self, fault=None):
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            return control._replay_shared_test(self.test, self.rows, fault=fault, repo=self.root)

    def test_complete_pool_replay_has_narrow_measurements_and_distinct_controls(self):
        result = self.replay()
        self.assertEqual([m["claim"] for m in control._shared_pool_measurements(result)], control._POOL_CLAIMS)
        for fault in ("absent-subject", "stale-subject", "pool-missing-finalization", "pool-replaced-site",
                      *("pool-missing-meaning:" + name for name in control._LEDYBA_REQUIRED_MEANINGS)):
            with self.subTest(fault=fault):
                bad = self.replay(fault)
                self.assertFalse(bad["passed"])
                self.assertTrue(bad["failures"])
        self.assertTrue(result["measurements"]["pool-spawn-v1"]["placement"]["passed"],
                        "copied controls must not alter retained input")

    def test_controller_acceptance_requires_current_recorder_and_exact_registration(self):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs), \
                patch.object(control, "_shared_recorder_control", return_value={"revalidated": True}) as recorder:
            result = control.finalize_shared_test(self.test, self.record, self.root)
            self.assertTrue(result["acceptedProof"], result)
            recorder.assert_called_once()
            self.assertEqual(result["proofAcceptance"]["proofLevel"], "S3")
            self.assertNotIn("rendered-motion", result["proofAcceptance"]["claims"])
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs), \
                patch.object(control, "_shared_recorder_control", side_effect=ValidationFailure("missing current control")):
            self.assertFalse(control.finalize_shared_test(self.test, self.record, self.root)["acceptedProof"])


class SharedLedybaProofTests(unittest.TestCase):
    """Synthetic evidence checks the real S4 replay; not live calibration."""
    write_rows = SharedProofTests.write_rows
    artifact = SharedProofTests.artifact
    current = SharedProofTests.current

    def setUp(self):
        SharedProofTests.setUp(self)
        from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE, Stream
        self.inputs = {"ledyba-chain-v1": {"schema": SCHEMA, "sourceSha256": SOURCE}}
        self.test.update(mode="normal", requirements=["legacy.ledyba-normal-profile"],
            measurements=[{"kind": "ledyba-chain-v1", "subject": "subject"}],
            assertions=[{"kind": "measurement-complete", "measurement": "ledyba-chain-v1"}])
        self.test["subjects"][0]["acquire"] = "spawn"
        self.test["budgets"].update(maxFrames=6000, minObservedFrames=16)
        self.test = validate_test(self.test)
        self.registry = json.loads((control.REPO / "tools/overworld/runtime_proof_registry.json").read_text())
        self.registration.update(evaluator="ledyba-chain-v1", proofLevel="S4", mode="normal",
            requirements=self.test["requirements"], minimumObservedFrames=16,
            claims=self.registry["runners"]["legacy.ledyba-normal-profile"],
            recorderControlRequirement="legacy.live-observer-controls")
        self.registry["sharedTests"] = {self.test["id"]: self.registration}
        self.save_registration()
        items = Stream().complete().items
        for sample, _ in items:
            for actor in sample["actors"]: actor["engineIdentity"]["manager_index"] = 0
        attachment = deepcopy(items[1][1][0]); attachment["data"]["event"] = "ACTOR_ATTACHED"
        for _, events in items:
            for event in events:
                if event["kind"] == "native": event["data"]["sequence"] += 1
        items[1][1].insert(0, attachment)
        binding = select_current_actor(items[1][0], items[1][0]["actors"][0])
        self.rows = [{"phase": "setup", "initialSnapshot": items[0][0]},
            {"phase": "setup", "samples": [items[1][0]], "snapshot": items[1][0],
             "events": items[1][1], "completedGameFrames": 1},
            {"phase": "setup", "command": "bind", "action": "bind-subject", "snapshot": items[1][0], "receipt": binding},
            {"phase": "observe", "samples": [s for s, _ in items[2:]], "snapshot": items[-1][0],
             "events": [e for _, events in items[2:] for e in events], "completedGameFrames": len(items) - 2}]
        self.write_rows()
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            evaluation = control._replay_shared_test(self.test, self.rows, repo=self.root)
        self.assertTrue(evaluation["passed"], evaluation)
        self.record.update(test=self.test["id"], evaluation=evaluation, observationsArtifact=self.artifact())
        image_dir = self.root / "build/overworld-devtools/session-proof"; image_dir.mkdir()
        self.png = image_dir / "screen-final.png"
        self.png.write_bytes(self.png_bytes())
        self.record["visualArtifact"] = {"screenshot": {"path": str(self.png), "sha256": sha(self.png),
            "frame": evaluation["lastFrame"], "nativeCycle": items[-1][0]["nativeCycle"]}}

    @staticmethod
    def png_bytes(width=256, height=384, *, flat=False):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        raw = b"".join(b"\0" + bytes(0 if flat else (x * 17 + y * 13) % 256 for x in range(width * 3))
                       for y in range(height))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

    def save_registration(self):
        path = self.root / "tests/overworld/test-recipes/test.actor.json"
        path.write_text(json.dumps(self.test))
        self.registration["recipeSha256"] = sha(path)
        (self.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps(self.registry))
        self.record["testSourceSha256"] = sha(path)
        self.record["fixtureProof"].update(registration=self.registration, testSourceSha256=sha(path))

    def finish(self, record=None, *, calibrated=True):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            if not calibrated:
                return control.finalize_shared_test(self.test, record or self.record, self.root)
            with patch.object(control, "_shared_recorder_control", create=True,
                              return_value={"requirement": "legacy.live-observer-controls", "revalidated": True}):
                return control.finalize_shared_test(self.test, record or self.record, self.root)

    def test_exact_s4_replays_all_seven_measurements_and_meaning_controls(self):
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        proof = result["proofAcceptance"]
        self.assertEqual(proof["claims"], self.registry["runners"]["legacy.ledyba-normal-profile"])
        self.assertEqual(len(proof["measurements"]), 7)
        for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
            rejected = proof["controls"]["missing-meaning:" + name]
            self.assertTrue(rejected["rejected"])
            self.assertIn("missing-", json.dumps(rejected["failures"]))
            self.assertNotIn("sequence is missing", json.dumps(rejected["failures"]))

    def test_normal_preflight_stops_before_boot_without_current_live_control(self):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.proof_inputs.proof_inputs", return_value={"schema": "test-scope"}), \
                patch("scripts.verify_overworld_runtime_fixture.verify", return_value=self.record["fixtureProof"]["fixture"]):
            result = control.prepare_shared_test(self.test, self.root)
        self.assertFalse(result["passed"], result)
        self.assertIn("required current live recorder control unavailable", result["reason"])
        self.assertNotIn("recorderControlArtifact", result)

    def test_pure_chain_pass_does_not_replace_separate_live_control(self):
        result = self.finish(calibrated=False)
        self.assertFalse(result["acceptedProof"])
        self.assertIn("recorder control", result["proofAcceptance"]["reason"])

    def linked_control(self):
        directory = self.root / "build/overworld-devtools/test-calibration"; directory.mkdir()
        control_test = recipe(); control_test.update(id="test.calibration", mode="observer-control",
            requirements=["legacy.live-observer-controls"])
        (self.root / "tests/overworld/test-recipes/test.calibration.json").write_text(json.dumps(control_test))
        self.registry["sharedTests"]["test.calibration"] = {
            "mode": "observer-control", "evaluator": "live-observer-control-v1",
            "requirements": ["legacy.live-observer-controls"]}
        self.save_registration()
        linked = {"runId": "test-calibration", "test": "test.calibration", "sessionId": "session-calibration",
                  "identity": deepcopy(self.record["identity"]), "fixtureProof": deepcopy(self.record["fixtureProof"]),
                  "passed": True, "acceptedProof": True}
        linked["identity"]["sessionId"] = linked["sessionId"]
        path = directory / "manifest.json"
        def save():
            path.write_text(json.dumps(linked))
            self.record["recorderControlArtifact"] = {"path": str(path), "sha256": sha(path), "size": path.stat().st_size}
        save()
        return linked, save

    def test_recorded_accepted_boolean_does_not_replace_control_revalidation(self):
        self.linked_control()
        with self.assertRaisesRegex(ValidationFailure, "independent current acceptance"):
            control._shared_recorder_control(self.record, self.registration, self.root)

    def test_linked_control_cannot_be_self_nested_stale_or_wrong_mode(self):
        linked, save = self.linked_control()
        for fault in ("self", "nested", "same-session", "stale-rom", "stale-source", "wrong-mode", "identity-only"):
            with self.subTest(fault=fault):
                original_link, original_registry = deepcopy(linked), deepcopy(self.registry)
                if fault == "self": self.record["runId"] = linked["runId"]
                elif fault == "nested": linked["recorderControlArtifact"] = deepcopy(self.record["recorderControlArtifact"])
                elif fault == "same-session": linked["sessionId"] = self.record["sessionId"]
                elif fault == "stale-rom": linked["identity"]["rom"]["sha256"] = "0" * 64
                elif fault == "stale-source": linked["fixtureProof"]["source"] = {"hash": "older"}
                elif fault == "wrong-mode": self.registry["sharedTests"]["test.calibration"]["mode"] = "normal"
                else: self.registry["sharedTests"]["test.calibration"]["evaluator"] = "current-actor-identity-v1"
                save(); self.save_registration()
                with patch.object(control, "finalize_shared_test") as revalidate:
                    with self.assertRaises(ValidationFailure):
                        control._shared_recorder_control(self.record, self.registration, self.root)
                    revalidate.assert_not_called()
                self.record["runId"] = "test-proof"
                linked.clear(); linked.update(original_link)
                self.registry = original_registry; self.registry["sharedTests"][self.test["id"]] = self.registration
                save(); self.save_registration()

    def test_linked_control_requires_exact_revalidated_control_requirement(self):
        self.linked_control()
        for accepted, mode, requirements in ((False, "observer-control", ["legacy.live-observer-controls"]),
                (True, "normal", ["legacy.live-observer-controls"]), (True, "observer-control", ["different"]),
                (True, "observer-control", ["legacy.live-observer-controls"])):
            value = {"passed": accepted, "acceptedProof": accepted, "proofAcceptance": {
                "mode": mode, "requirements": requirements, "claims": ["live-actor-identity", "controlled-action"]}}
            with patch.object(control, "finalize_shared_test", return_value=value) as revalidate:
                if accepted and mode == "observer-control" and requirements == ["legacy.live-observer-controls"]:
                    self.assertTrue(control._shared_recorder_control(self.record, self.registration, self.root)["revalidated"])
                else:
                    with self.assertRaises(ValidationFailure): control._shared_recorder_control(self.record, self.registration, self.root)
                revalidate.assert_called_once()
                self.assertEqual(revalidate.call_args.args[0]["mode"], "observer-control")

    def test_s4_scope_or_original_measurements_cannot_be_weakened(self):
        changes = [lambda: self.registration.update(claims=["live-actor-identity"]),
                   lambda: self.registration.update(recorderControlRequirement="another"),
                   lambda: self.test["subjects"][0].update(species=166),
                   lambda: self.registry["measurementContracts"]["legacy.ledyba-normal-profile"]["natural-input"][0].update(minimum=1)]
        for change in changes:
            original_test, original_registration, original_registry = deepcopy(self.test), deepcopy(self.registration), deepcopy(self.registry)
            change(); self.save_registration()
            self.assertFalse(self.finish()["acceptedProof"])
            self.test, self.registration, self.registry = original_test, original_registration, original_registry
            self.registry["sharedTests"][self.test["id"]] = self.registration
            self.save_registration()

    def test_s4_native_proof_is_identical_without_or_with_any_screenshot(self):
        expected = self.finish()
        self.assertTrue(expected["acceptedProof"], expected)
        for fault in ("missing", "unrelated", "frame", "nativeCycle", "hash", "format", "unreadable"):
            with self.subTest(fault=fault):
                record = deepcopy(self.record)
                image = record["visualArtifact"]["screenshot"]
                if fault == "missing": record.pop("visualArtifact")
                elif fault == "unrelated": image["path"] = str(self.root / "another-session/unrelated.png")
                elif fault in ("frame", "nativeCycle"): image[fault] -= 1
                elif fault == "hash": image["sha256"] = "0" * 64
                elif fault == "format":
                    self.png.write_bytes(b"not a PNG"); image["sha256"] = sha(self.png)
                else: record["visualArtifact"] = {"error": "optional image unavailable"}
                actual = self.finish(record)
                self.assertTrue(actual["acceptedProof"], actual)
                self.assertEqual(actual, expected)
                self.assertNotIn("visualArtifact", actual["proofAcceptance"])

    def test_valid_png_cannot_rescue_missing_or_wrong_native_evidence(self):
        original_rows = deepcopy(self.rows)
        for fault in ("render", "identity", "terminal", "profile"):
            with self.subTest(fault=fault):
                self.rows = deepcopy(original_rows)
                sample = self.rows[-1]["samples"][2]
                actor = sample["actors"][0]
                if fault == "render":
                    frozen = deepcopy(self.rows[-1]["samples"][0]["actors"][0]["engineObject"])
                    for stalled in self.rows[-1]["samples"][1:3]:
                        stalled["actors"][0]["engineObject"] = deepcopy(frozen)
                elif fault == "identity": actor["engineIdentity"]["in_manager"] = False
                elif fault == "profile": actor["behaviorFingerprint"] += 1
                else:
                    terminal = next(event for event in self.rows[-1]["events"]
                                    if event.get("data", {}).get("event") == "MOTION_FINISHED")
                    terminal["data"]["event"] = "WORLD_EFFECT"
                self.write_rows()
                record = deepcopy(self.record)
                record["observationsArtifact"] = self.artifact()
                with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
                    if fault == "identity":
                        with self.assertRaises(ValidationFailure):
                            control._replay_shared_test(self.test, self.rows, repo=self.root)
                    else:
                        bad = control._replay_shared_test(self.test, self.rows, repo=self.root)
                        self.assertFalse(bad["passed"], bad["failures"])
                        record["evaluation"] = bad
                self.assertFalse(self.finish(record)["acceptedProof"])


class SharedLiveControlProofTests(unittest.TestCase):
    """Controller replay of the real native-control byte-RAM host fixture."""
    write_rows = SharedProofTests.write_rows
    artifact = SharedProofTests.artifact
    current = SharedProofTests.current
    save_registration = SharedLedybaProofTests.save_registration

    def setUp(self):
        SharedProofTests.setUp(self)
        from tools.overworld.test_devtools_observer_control_measurement import shared_job_fixture, KIND, SCHEMA, SOURCE
        self.inputs = {KIND: {"schema": SCHEMA, "sourceSha256": SOURCE}}
        self.test, self.rows = shared_job_fixture()
        self.test["requirements"] = ["legacy.live-observer-controls"]
        self.test = validate_test(self.test)
        self.registry = json.loads((control.REPO / "tools/overworld/runtime_proof_registry.json").read_text())
        self.registration.update(evaluator=KIND, proofLevel="S3", mode="observer-control",
            requirements=self.test["requirements"], minimumObservedFrames=2,
            claims=self.registry["runners"]["legacy.live-observer-controls"])
        self.registry["sharedTests"] = {self.test["id"]: self.registration}
        self.save_registration()
        with patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            evaluation = control._replay_shared_test(self.test, self.rows, repo=self.root)
        self.assertTrue(evaluation["passed"], evaluation)
        self.write_rows()
        self.record.update(test=self.test["id"], evaluation=evaluation, observationsArtifact=self.artifact(),
                           observerControlCleanup=self.rows[-1]["receipt"])

    def finish(self, record=None):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            return control.finalize_shared_test(self.test, record or self.record, self.root)

    def test_actual_control_fixture_accepts_only_separate_live_control_claims(self):
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        proof = result["proofAcceptance"]
        self.assertEqual(proof["claims"], ["live-actor-identity", "controlled-action"])
        self.assertEqual([item["value"] for item in proof["measurements"]], [1, [1, 1, 1], 2])
        self.assertEqual(proof["recorderControlCleanup"], self.record["observerControlCleanup"])
        self.assertEqual(proof["observedFrames"], sum(row.get("completedGameFrames", 0) for row in self.rows if row["phase"] == "observe"))

    def test_missing_or_changed_cleanup_does_not_pass(self):
        changed = deepcopy(self.record); changed.pop("observerControlCleanup")
        self.assertFalse(self.finish(changed)["acceptedProof"])
        changed = deepcopy(self.record); changed["observerControlCleanup"]["observerControl"]["receipts"][-1]["afterFlags"] ^= 2
        self.assertFalse(self.finish(changed)["acceptedProof"])
        self.rows.pop(); self.write_rows(); self.record["observationsArtifact"] = self.artifact()
        self.assertFalse(self.finish()["acceptedProof"])

    def test_missing_real_write_or_changed_readback_does_not_pass(self):
        original = deepcopy(self.rows)
        for fault in ("missing-write", "wrong-readback"):
            self.rows = deepcopy(original)
            row = next(row for row in self.rows if "samples" in row and row["samples"][0].get("observerControl", {}).get("kind") == "render-stall")
            sample = row["samples"][-1]
            if fault == "missing-write": sample["observerControl"]["receipts"].pop()
            else: sample["actors"][0]["engineObject"]["pos_x"] += 1
            self.write_rows(); self.record["observationsArtifact"] = self.artifact()
            self.assertFalse(self.finish()["acceptedProof"])

    def save_accepted_control(self):
        result = self.finish()
        self.assertTrue(result["acceptedProof"], result)
        manifest = self.observations.parent / "manifest.json"
        manifest.write_text(json.dumps({**self.record, **result}))
        return manifest

    def find_current_control(self):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            return control._find_shared_recorder_control(self.test,
                {"recorderControlRequirement": "legacy.live-observer-controls"}, {"hash": "source"}, self.root)

    def test_preflight_lookup_replays_actual_control_and_rechecks_pinned_artifact(self):
        manifest = self.save_accepted_control()
        artifact = self.find_current_control()
        self.assertEqual(artifact, {"path": str(manifest), "sha256": sha(manifest), "size": manifest.stat().st_size})
        normal = deepcopy(self.record)
        normal.update(runId="test-normal", sessionId="session-normal")
        normal["fixtureProof"]["recorderControlArtifact"] = artifact
        registration = {"recorderControlRequirement": "legacy.live-observer-controls"}
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs):
            result = control._shared_recorder_control(normal, registration, self.root)
            self.assertTrue(result["revalidated"])
            normal["recorderControlArtifact"] = {**artifact, "sha256": "changed"}
            with self.assertRaisesRegex(ValidationFailure, "changed after normal preflight"):
                control._shared_recorder_control(normal, registration, self.root)
            normal.pop("recorderControlArtifact")
            manifest.write_text(manifest.read_text() + " ")
            with self.assertRaisesRegex(ValidationFailure, "hash/size differs"):
                control._shared_recorder_control(normal, registration, self.root)

    def test_lookup_rejects_stale_forged_or_malformed_accepted_records(self):
        manifest = self.save_accepted_control()
        original = json.loads(manifest.read_text())
        for fault in ("stale", "failed", "fake-evaluation", "missing-acceptance", "missing-rom"):
            with self.subTest(fault=fault):
                changed = deepcopy(original)
                if fault == "stale": changed["fixtureProof"]["source"] = {"hash": "old"}
                elif fault == "failed": changed["passed"] = False
                elif fault == "fake-evaluation": changed["evaluation"]["observedFrames"] += 1
                elif fault == "missing-acceptance": changed["proofAcceptance"] = None
                else: changed["identity"]["rom"] = None
                manifest.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValidationFailure, "no independently accepted current"):
                    self.find_current_control()
        canceled = threading.Event(); canceled.set()
        with self.assertRaisesRegex(ValidationFailure, "lookup canceled"):
            control._find_shared_recorder_control(self.test, {}, {}, self.root, cancel_event=canceled)
        with self.assertRaisesRegex(ValidationFailure, "wall budget"):
            control._find_shared_recorder_control(self.test, {}, {}, self.root, deadline=time.monotonic() - 1)


class SharedControlReplayTransportTests(unittest.TestCase):
    """Replay transport only; the real control-measurement tests own fault detection."""
    def fixture(self):
        order, subject = [], {"handle": {"value": 65536}, "species": 165}
        args = {"subject": subject, "kind": "render-stall", "maxFrames": 1200}
        class Evaluator:
            uses_raw_records = False  # This fixture exercises the non-cadence replay route.
            def __init__(self, test):
                self.latest, self.subjects = {"frame": 10}, {"s": subject}
                self.observed_fault = False
            def install_measurements(self, inputs): pass
            def observer_control_args(self, name, kind):
                order.append(("arm", name, kind)); return deepcopy(args)
            def observe(self, snapshot, events=(), count_frame=True):
                self.latest = snapshot; self.observed_fault = snapshot.get("expectedFault") is True
                order.append(("observe", snapshot["frame"]))
            def expected_control_identity_failure(self, snapshot, selected):
                return self.observed_fault and selected is subject
            def observer_control_cleanup(self, receipt):
                order.append(("cleanup", receipt["frame"]))
            def finish(self): return {"passed": True}
        test = {"mode": "observer-control", "setup": [], "actions": [{"id": "arm", "op": "observer-control",
                "args": {"subject": "s", "fault": "render-stall"}}]}
        native = {"kind": args["kind"], "subject": subject, "state": "armed",
            "receipts": [{**args, "action": "armed", "frame": 10}]}
        rows = [{"phase": "observe", "action": "arm", "command": "observer-control",
            "receipt": {"armed": True, "prepared": True, "frame": 10, "observerControl": native},
            "snapshot": {"frame": 10}},
            {"phase": "observe", "samples": [{"frame": 11, "expectedFault": True}, {"frame": 12}],
             "events": [], "completedGameFrames": 2}]
        return Evaluator, test, rows, order

    def test_arm_replays_before_samples_and_only_detected_fault_skips_post_observation_check(self):
        evaluator, test, rows, order = self.fixture()
        with patch("tools.overworld.devtools_test_contract.TestEvaluator", evaluator), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={}), \
                patch.object(control, "_verify_shared_subject_observation", side_effect=lambda s, _: order.append(("verify", s["frame"]))):
            self.assertTrue(control._replay_shared_test(test, rows)["passed"])
        self.assertEqual(order, [("arm", "s", "render-stall"), ("observe", 11), ("observe", 12), ("verify", 12)])

    def test_wrong_arm_subject_kind_bound_or_normal_mode_fails_before_samples(self):
        for fault in ("subject", "kind", "maxFrames", "frame", "mode", "action"):
            evaluator, test, rows, order = self.fixture()
            receipt = rows[0]["receipt"]
            if fault == "mode": test["mode"] = "normal"
            elif fault == "action": rows[0]["action"] = "undeclared"
            elif fault == "frame": receipt["frame"] += 1
            elif fault == "maxFrames": receipt["observerControl"]["receipts"][0]["maxFrames"] -= 1
            else: receipt["observerControl"][fault] = "wrong"
            with patch("tools.overworld.devtools_test_contract.TestEvaluator", evaluator), \
                    patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={}):
                with self.assertRaises(ValidationFailure): control._replay_shared_test(test, rows)
            self.assertFalse(any(item[0] == "observe" for item in order))

    def test_cleanup_is_replayed_once_without_counting_a_duplicate_frame(self):
        evaluator, test, rows, order = self.fixture()
        receipt = {"frame": 12, "snapshot": {"frame": 12}, "closed": True}
        rows.append({"phase": "cleanup", "command": "observer-control.close",
                     "receipt": receipt, "snapshot": receipt["snapshot"]})
        with patch("tools.overworld.devtools_test_contract.TestEvaluator", evaluator), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value={}), \
                patch.object(control, "_verify_shared_subject_observation"):
            control._replay_shared_test(test, rows)
        self.assertEqual(order, [("arm", "s", "render-stall"), ("observe", 11), ("observe", 12), ("cleanup", 12)])


class RuntimeRetirementTests(unittest.TestCase):
    def test_registered_identity_scenario_routes_shared_start_without_emulator_lock(self):
        _, scenarios = control._load_contracts(audit_runtime_proof_sources=True)
        scenario = scenarios["devtools.actor-identity"]
        self.assertEqual(scenario["adapter"]["kind"], "devtools-test")
        self.assertEqual(scenario["status"], "active")
        migration = control._runtime_migration_summary()
        self.assertEqual(migration["requirementCount"], 41)
        requirements = json.loads((control.REPO / "tools/overworld/runtime_proof_migration.json").read_text())["requirements"]
        expected_pending = {key for key, value in requirements.items() if value["status"] == "pending"}
        self.assertEqual(migration["pendingCount"], len(expected_pending))
        self.assertEqual({item["requirement"] for item in migration["pending"]}, expected_pending)
        self.assertFalse({"legacy.ledyba-normal-profile", "legacy.live-observer-controls", "legacy.live-route-observer-controls"}
                         & {item["requirement"] for item in migration["pending"]})
        registered = json.loads((control.REPO / "tools/overworld/runtime_proof_registry.json").read_text())["sharedTests"]
        for item in scenarios.values():
            if item["proofLevel"] not in ("S3", "S4", "S5") or item["status"] == "planned":
                continue
            self.assertEqual(item["adapter"]["kind"], "devtools-test")
            self.assertIn(item["adapter"]["test"], registered)
        args = SimpleNamespace(scenario_id=scenario["id"], dry_run=False, evidence=None, manifest_output=None,
                               url="http://127.0.0.1:8766")
        with patch("tools.overworld.devtools_cli.request", return_value={"ok": True, "result": {"state": "starting"}}) as request, \
             patch.object(control, "scenario_lock") as lock, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(control._scenario_run(args), 0)
        request.assert_called_once_with(args.url, {"op": "test.start", "args": {"name": scenario["id"]}})
        lock.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())["acceptedProof"])

    def test_shared_scenario_cannot_drift_from_reviewed_recipe_scope(self):
        features, scenarios = control._load_contracts()
        for mutate in (lambda s: s["subjects"][0].update(species=165),
                       lambda s: s.update(proofLevel="S5"),
                       lambda s: s["fixture"].update(rom="another.nds"),
                       lambda s: s["adapter"].update(minimumFrames=1),
                       lambda s: s["verification"].update(kind="normal-play")):
            changed = deepcopy(scenarios); mutate(changed["devtools.actor-identity"])
            with self.assertRaises(ValidationFailure): cross_validate(features, changed, control.REPO)

    def test_old_runtime_command_never_launches_subprocess(self):
        with patch.object(control.subprocess, "run") as run:
            with self.assertRaisesRegex(ValidationFailure, "retired"):
                control._run_command(["python", "scripts/verify_overworld_walk_runtime.py", "--scenario", "wild_walk"], "json-passed")
        run.assert_not_called()

    def test_runtime_scenario_rejected_before_parent_lock_or_commands(self):
        scenario = {"id": "old", "status": "active", "proofLevel": "S3", "adapter": {"kind": "command-sequence"}}
        args = SimpleNamespace(scenario_id="old", dry_run=False, evidence=None, manifest_output=None)
        with patch.object(control, "_load_contracts", return_value=({}, {"old": scenario})), \
             patch.object(control, "scenario_lock") as lock, patch.object(control, "_run_command") as command:
            with self.assertRaisesRegex(ValidationFailure, "migration"):
                control._scenario_run(args)
        lock.assert_not_called(); command.assert_not_called()

    def test_all_41_requirements_retained_and_contract_change_rejected(self):
        repo = control.REPO
        registry = json.loads((repo / "tools/overworld/runtime_proof_registry.json").read_text())
        migration = json.loads((repo / "tools/overworld/runtime_proof_migration.json").read_text())
        self.assertEqual(len(validate_runtime_migration(migration, registry)["requirements"]), 41)
        self.assertFalse([key for key, item in migration["requirements"].items()
                          if item["status"] == "pending"])
        key = "legacy.turn-skid"
        for operation in (lambda m: m["requirements"].pop(key),
                          lambda m: m["requirements"][key].update(claims=[]),
                          lambda m: m["requirements"][key].update(
                              measurementContractSha256="0" * 64)):
            changed = deepcopy(migration); operation(changed)
            with self.assertRaises(ValidationFailure): validate_runtime_migration(changed, registry)


class FixtureBudgetTests(unittest.TestCase):
    def test_timeout_stops_only_owned_check_and_keeps_prior_output(self):
        started = time.monotonic()
        result = _run_bounded([sys.executable, "-c",
            "import time; print('retained-before-timeout', flush=True); time.sleep(10)"], deadline=started + 0.2)
        self.assertEqual(result.returncode, 124)
        self.assertIn("fixture-wall-budget", result.stderr)
        self.assertIn("retained-before-timeout", result.stdout)
        self.assertLess(time.monotonic() - started, 3)

    def test_canceled_preflight_never_starts_a_process(self):
        canceled = threading.Event(); canceled.set()
        with patch("scripts.verify_overworld_runtime_fixture.subprocess.Popen") as process:
            result = _run_bounded(["not-executed"], cancel_event=canceled)
        process.assert_not_called()
        self.assertEqual(result.stderr, "fixture-canceled")

    def test_success_inside_budget_returns_real_output(self):
        result = _run_bounded([sys.executable, "-c", "print('bounded-check')"], deadline=time.monotonic() + 3)
        self.assertEqual(result.returncode, 0)
        self.assertIn("bounded-check", result.stdout)


if __name__ == "__main__": unittest.main()
