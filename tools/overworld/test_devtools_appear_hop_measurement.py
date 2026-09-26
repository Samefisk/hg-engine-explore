from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_appear_hop_measurement import AppearHopMeasurement
from tools.overworld.devtools_appear_hop_proof import AppearHopNegative
from tools.overworld.devtools_test_contract import TestEvaluator


def snapshot(frame, command, face_y, controller_state):
    handle = {
        "value": 65536, "slot": 0, "generation": 1,
        "fieldEpoch": 1, "mapGeneration": 1, "encounterGeneration": 1,
    }
    source = {
        "active": 1, "species": 35, "personality": 123,
        "object": 0x020A0100, "object_id": 0xE0, "map_id": 33,
        "encounter_generation": 1,
    }
    engine = {
        "pointer": 0x020A0100, "in_manager": True, "active": True,
        "object_manager": 0x020B0000, "current_manager": 0x020B0000,
        "object_id": 0xE0, "spawn_object_id": 0xE0,
        "object_map_id": 33, "spawn_map_id": 33, "current_map_id": 33,
        "encounter_generation": 1, "script_id": 2074,
    }
    actor = {
        "handle": handle, "subjectIdentity": 123, "species": 35,
        "form": 0, "level": 5, "role": "WILD", "active": True,
        "presentationAttached": True, "identityVerified": True,
        "authorityGeneration": 1, "engineAnchorGeneration": 1,
        "presentationGeneration": 1, "behaviorFingerprint": 99,
        "matchedLayerMask": 1, "inputOwnership": 0,
        "motionKind": "NONE", "motionPhase": "IDLE",
        "controllerState": controller_state,
        "sourceIdentity": source, "engineIdentity": engine,
        "engineObject": {
            "movement_cmd": command, "movement_step": 1,
            "face_y": face_y,
        },
    }
    return {
        "frame": frame, "nativeCycle": frame * 2,
        "context": {"fieldEpoch": 1, "mapGeneration": 1, "mapId": 33},
        "actors": [actor], "prepared": True, "fieldAvailable": True,
        "observationBoundary": "main-task-queue-completion",
        "selector": {"heldKeys": 0, "newKeys": 0,
                     "physicalPressed": 0, "simulatedKeys": 0},
    }


def stream(terminal_state):
    rows = []
    frame = 100
    for command, faces in (
            (49, (0, 32768, 49152, 24576, 0)),
            (62, (0, 0, 0, 0, 0)),
            (74, (0,)),
            (255, (0,))):
        for face in faces:
            rows.append(snapshot(frame, command, face, 1))
            frame += 1
    rows.append(snapshot(frame, 62, 0, terminal_state))
    return rows


class AppearHopMeasurementTests(unittest.TestCase):
    def test_flat_arc_control_finds_prebind_prepared_actor(self):
        row = {"samples": [snapshot(100, 49, 32768, 1)]}
        control = AppearHopNegative("appear-hop-flat-arc")
        changed = control.mutate(row, {})
        self.assertTrue(control.applied)
        self.assertEqual(changed["samples"][0]["actors"][0]["engineObject"]["face_y"], 0)

    def test_prepared_baseline_before_spawn_is_not_measured(self):
        root = Path(__file__).resolve().parents[2]
        recipe = json.loads((root / "tests/overworld/test-recipes/spawn.appear-hop-timing.json").read_text())
        evaluator = TestEvaluator(recipe)
        evaluator.install_measurements({"appear-hop-timing-v1": {"contractVersion": 1}})
        evaluator.observe({
            "frame": 0,
            "nativeCycle": 0,
            "context": {"fieldEpoch": 1, "mapGeneration": 1, "mapId": 33},
            "actors": [],
            "player": {"x": 585, "y": 406},
            "prepared": True,
            "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion",
        }, count_frame=False)
        self.assertEqual(evaluator.result()["failures"], [])
        self.assertIsNone(evaluator.spawn_setup)

    def test_idle_publication_releases_control_on_the_next_frame(self):
        meter = AppearHopMeasurement()
        for row in stream(0):
            meter.observe(row, [])
        self.assertTrue(meter.finish()["passed"])
        self.assertEqual(meter.result()["samples"][-1]["controllerState"], 0)
        self.assertEqual(meter.result()["terminal"]["frame"], meter.result()["idleFrame"] + 1)

    def test_late_control_release_fails_after_idle_publication(self):
        meter = AppearHopMeasurement()
        for row in stream(1):
            meter.observe(deepcopy(row), [])
        result = meter.finish()
        self.assertFalse(result["passed"])
        self.assertIn("stayed locked", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
