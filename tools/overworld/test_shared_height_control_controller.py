"""Real height-control controller replay over sealed host fixtures; no core."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tools.overworld import control, test_devtools_test_proof as pool_tests
from tools.overworld import test_shared_pool_surface_controller as surface_tests
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_spawn_height_control_measurement import control_stream


KIND = "live-spawn-height-control-v1"
REQUIREMENT = "shared.spawn-height-recorder-control-v1"
FAULTS = ("height-control-missing-meaning", "height-control-unrestored")


def mareep_fixture(value):
    if isinstance(value, dict):
        return {
            key: (179 if key == "species" and item == 165
                  else mareep_fixture(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [mareep_fixture(item) for item in value]
    return value


def extendable_control_stream():
    stream, _ = control_stream()
    stream.sequence += 2
    stream.actor["engineIdentity"]["id_lookup"] = {"eligible_count": 1, "pointer_matches": True}
    return stream


class SharedHeightControlControllerTests(unittest.TestCase):
    write_rows = pool_tests.SharedPoolProofTests.write_rows
    artifact = pool_tests.SharedPoolProofTests.artifact
    current = pool_tests.SharedPoolProofTests.current
    replay = pool_tests.SharedPoolProofTests.replay
    save_registration = surface_tests.SharedPoolSurfaceControllerTests.save_registration

    def test_boot_prefix_height_controls_mutate_only_the_copied_receipt(self):
        original = [{"kind": "native-observation", "data": {
            "observation": "spawn-height-read-control",
            "restored": {"positionAfter": {"pos_y": 4096}}}}]
        for fault, expected in (("height-control-missing-meaning", "height-control-meaning-removed"),
                                ("height-control-unrestored", "spawn-height-read-control")):
            with self.subTest(fault=fault):
                copied = deepcopy(original)
                self.assertTrue(control._apply_height_meaning_control(copied, fault))
                self.assertEqual(copied[0]["data"]["observation"], expected)
                self.assertEqual(copied[0]["data"]["restored"]["positionAfter"]["pos_y"],
                                 4097 if fault == "height-control-unrestored" else 4096)
                self.assertEqual(original[0]["data"]["observation"], "spawn-height-read-control")
                self.assertEqual(original[0]["data"]["restored"]["positionAfter"]["pos_y"], 4096)

    def setUp(self):
        pool_tests.SharedPoolProofTests.setUp(self)
        stream = extendable_control_stream()
        for _ in range(6):
            stream.append()
        items = stream.items
        for snapshot, _ in items:
            for actor in snapshot["actors"]:
                actor["engineIdentity"]["manager_index"] = 0
        attachment = deepcopy(next(event for event in items[1][1]
                                   if event["kind"] == "native"))
        attachment["data"]["event"] = "ACTOR_ATTACHED"
        for _, events in items:
            for event in events:
                if event["kind"] == "native":
                    event["data"]["sequence"] += 1
        items[1][1].insert(0, attachment)
        binding = select_current_actor(items[1][0], items[1][0]["actors"][0])
        self.rows = [
            {"phase": "setup", "initialSnapshot": items[0][0]},
            {"phase": "setup", "samples": [items[1][0]], "snapshot": items[1][0],
             "events": items[1][1], "completedGameFrames": 1},
            {"phase": "setup", "command": "bind", "action": "bind-subject",
             "snapshot": items[1][0], "receipt": binding},
            {"phase": "observe", "samples": [snapshot for snapshot, _ in items[2:]],
             "snapshot": items[-1][0],
             "events": [event for _, events in items[2:] for event in events],
             "completedGameFrames": len(items) - 2},
        ]
        self.test["subjects"][0]["species"] = 179
        self.write_rows()
        self.record["observationsArtifact"] = self.artifact()
        self.inputs = {KIND: self.inputs["pool-spawn-v1"]}
        self.test.update(mode="observer-control", requirements=[REQUIREMENT],
            measurements=[{"kind": KIND, "subject": "subject"}],
            assertions=[{"kind": "measurement-complete", "measurement": KIND}])
        self.registration.update(evaluator=KIND, mode="observer-control", requirements=[REQUIREMENT],
                                 claims=list(control._RECORDER_CLAIMS))
        self.registration.pop("recorderControlRequirement", None)
        self.save_registration()
        self.record["evaluation"] = self.replay()
        self.assertTrue(self.record["evaluation"]["passed"], self.record["evaluation"])

    def test_exact_height_control_registration_needs_no_other_calibration(self):
        registration, _ = control._shared_test_registration(self.test, self.root)
        self.assertEqual(registration["requirements"], [REQUIREMENT])
        self.assertNotIn("recorderControlRequirement", registration)
        self.registration["recorderControlRequirement"] = "legacy.live-observer-controls"
        self.save_registration()
        with self.assertRaises(control.ValidationFailure):
            control._shared_test_registration(self.test, self.root)

    def test_copied_controls_reach_exact_height_rejections(self):
        before = deepcopy(self.rows)
        for fault, message in zip(FAULTS, ("control is missing", "clean/restored")):
            with self.subTest(fault=fault):
                result = self.replay(fault)
                self.assertFalse(result["passed"], result)
                meter = result["measurements"][KIND]
                self.assertTrue(meter["baseline"]["passed"], meter)
                self.assertTrue(any(error.get("code") == "invalid-spawn-height-control"
                                    and message in error.get("message", "")
                                    for error in meter["failures"]), meter)
                self.assertEqual(meter["detections"], {})
                self.assertEqual(self.rows, before)
        self.assertTrue(self.replay()["passed"])

    def test_finalize_replays_height_and_subject_controls_without_dependency(self):
        with patch.object(control, "source_record", return_value={"hash": "source"}), \
                patch("tools.overworld.devtools_test_inputs.measurement_inputs", return_value=self.inputs), \
                patch.object(control, "_shared_recorder_control") as dependency, \
                patch.object(control, "_replay_shared_test", wraps=control._replay_shared_test) as replay:
            result = control.finalize_shared_test(self.test, self.record, self.root)
        self.assertTrue(result["acceptedProof"], result)
        dependency.assert_not_called()
        called = {call.kwargs.get("fault") for call in replay.call_args_list}
        for fault in (*FAULTS, "absent-subject", "stale-subject"):
            self.assertIn(fault, called)
            self.assertTrue(result["proofAcceptance"]["controls"][fault]["rejected"])
        self.assertEqual(result["proofAcceptance"]["claims"], control._RECORDER_CLAIMS)


if __name__ == "__main__":
    unittest.main()
