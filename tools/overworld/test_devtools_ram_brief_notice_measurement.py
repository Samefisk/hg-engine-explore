"""Host controls for the bounded brief Ram notice contract; not game proof."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from tools.overworld.devtools_appearance_observer import decode_conditions, HANDLE_KEYS
from tools.overworld.devtools_ram_brief_notice_measurement import (
    ACTIVE, KIND, PENDING, UNTIL_CRASH, RamBriefNoticeMeasurement,
    validate_recipe,
)
from tools.overworld.devtools_profile_feature_measurement import ProfileFeatureMeasurement
from tools.overworld.devtools_ram_until_crash_measurement import RAM_MASK
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld.proof_adapters import ADAPTERS
from tools.overworld.test_devtools_player_health_ram_rest_measurement import ONIX


ROOT = Path(__file__).resolve().parents[2]


def decoded_state(flags):
    actor = deepcopy(ONIX)
    blob = bytearray(128)
    struct.pack_into("<IHH", blob, 52, 80, 1, 48)
    struct.pack_into("<I", blob, 60, 128)
    struct.pack_into("<H", blob, 80 + 32, 20305)
    blob[80 + 34] = 7
    blob[80 + 38] = 2
    prepared = bytearray(52)
    struct.pack_into("<6H", prepared, 0,
                     *(actor["handle"][key] for key in HANDLE_KEYS), 0)
    struct.pack_into("<I", prepared, 12, 0x2200100)
    struct.pack_into("<BBH", prepared, 48, 1, 1, 32)
    state = struct.pack("<II3H2B", 0, 0, 0xffff, 0, 0, 1, flags)

    def read(pointer, count):
        value = {0x2200000: bytes(prepared), 0x2200100: state}[pointer]
        assert len(value) == count
        return value

    return decode_conditions(read, 0x2200000, actor, bytes(blob), 17, 1 << 7)


class RamBriefNoticeHostTests(unittest.TestCase):
    def test_exact_recipe_is_registered(self):
        path = ROOT / "tests/overworld/test-recipes/profile.ram.brief-notice.json"
        recipe = validate_test(json.loads(path.read_text()))
        validate_recipe(recipe)
        self.assertEqual(ADAPTERS[KIND].requirement, "current.ram-brief-notice")
        changed = deepcopy(recipe)
        changed["actions"][3]["args"]["keys"] = ["DOWN"]
        with self.assertRaises(ValueError):
            validate_recipe(changed)
        changed = deepcopy(recipe)
        changed["setup"][-1]["args"]["radius"] = 2
        with self.assertRaises(ValueError):
            validate_recipe(changed)

    def test_presentation_bits_are_known_but_unknown_bit_stays_rejected(self):
        pending = decoded_state(ACTIVE | UNTIL_CRASH | PENDING | (1 << 6))
        self.assertTrue(pending["available"])
        self.assertEqual(pending["states"][0]["flags"], ACTIVE | UNTIL_CRASH | PENDING | (1 << 6))
        with self.assertRaisesRegex(ValueError, "condition state values differ"):
            decoded_state(1 << 7)

    def test_sight_activates_during_same_walk_and_intent_consumes_presentation(self):
        meter = RamBriefNoticeMeasurement()
        plan = {"version": 1, "kind": 1, "fieldEpoch": ONIX["handle"]["fieldEpoch"],
                "behaviorFingerprint": 0x5678, "reservationId": 77,
                "origin": [602, 402], "target": [601, 402],
                "duration": 16, "facing": 2}
        meter.ordinary = {"startFrame": 838, "origin": {"x": 602, "y": 402},
                          "target": {"x": 601, "y": 402}, "duration": 16,
                          "reservationId": 77, "plan": deepcopy(plan),
                          "planFingerprint": plan["behaviorFingerprint"],
                          "facing": 2, "commitBefore": 4}
        actor = {"handle": deepcopy(ONIX["handle"]), "motionKind": "WALK",
                 "motionPhase": "MOVING", "motionElapsed": 3,
                 "origin": {"x": 602, "y": 402}, "target": {"x": 601, "y": 402},
                 "motionDuration": 16, "reservationId": 77,
                 "behaviorFingerprint": 0x1234, "matchedLayerMask": RAM_MASK,
                 "engineObject": {"facing": 2}}
        state = {"flags": ACTIVE | UNTIL_CRASH | PENDING,
                 "targetKind": 1, "targetSlot": 0xffff,
                 "targetGeneration": 0, "targetEncounterGeneration": 0,
                 "activeUntil": 0, "cooldownUntil": 0}
        meter._condition_state = lambda _snapshot, _actor: (state, {}, {})

        def snapshot(frame, y):
            return {"frame": frame, "observationBoundary": "main-task-queue-completion",
                    "romSha256": "a" * 64, "nativeCycle": frame + 1000,
                    "fieldControl": {"taskPointer": 0}, "context": {"mapId": 33},
                    "player": {"x": 606, "y": y,
                               "x_prev": 606, "y_prev": 403,
                               "movement_cmd": 88, "movement_step": 1,
                               "facing": 0,
                               "pos_z": ((403 << 16) + 0x4000 if y == 402
                                         else (y << 16) + 0x8000)},
                    "pokemonCombat": {"schemaVersion": 1, "available": True,
                        "frame": frame, "nativeCycle": frame + 1000,
                        "observationBoundary": "main-task-queue-completion",
                        "identity": {"romSha256": "a" * 64},
                        "targets": [{"handle": deepcopy(actor["handle"]),
                                     "role": "WILD", "species": 95,
                                     "motion": {"phase": actor["motionPhase"],
                                                "plan": deepcopy(plan)}}]},
                    }

        terrain = snapshot(837, 403)
        terrain["terrain"] = {"observation": {
            "boundary": "paused-native-cycle-end", "nativeCycle": 1837,
            "lastCompletedGameFrame": 837, "context": {"mapId": 33},
            "center": {"x": 603, "z": 402}},
            "cells": [{"x": x, "y": y, "loaded": True,
                       "collision": False, "provenance": {
                           "mapHeaderId": 33,
                           "landDataIdentity": "current-map-matrix"}}
                      for y in range(399, 406) for x in range(600, 607)]}
        wrong = deepcopy(terrain)
        wrong["terrain"]["observation"]["nativeCycle"] += 1
        with self.assertRaisesRegex(ValueError, "exact current native boundary"):
            meter.observe_terrain(wrong)
        meter.observe_terrain(terrain)

        with patch.object(ProfileFeatureMeasurement, "_sample"):
            state["flags"] = ACTIVE | UNTIL_CRASH | PENDING
            with self.assertRaisesRegex(ValueError, "before the brief player sighting"):
                meter._sample(snapshot(839, 403), {"onix": actor})
            meter._sample(snapshot(840, 402), {"onix": actor})
            self.assertEqual(meter.trigger["frame"], 840)
            self.assertEqual(meter.pending_frame, 840)
            self.assertEqual(meter.ordinary["reservationId"], actor["reservationId"])
            actor["behaviorFingerprint"] = 0x9999 # Current profile may change; plan may not.
            state["flags"] = UNTIL_CRASH | PENDING
            with self.assertRaisesRegex(ValueError, "active with pending presentation"):
                meter._sample(snapshot(841, 402), {"onix": actor})
            state["flags"] = ACTIVE | UNTIL_CRASH | PENDING
            actor["engineObject"]["facing"] = 3
            with self.assertRaisesRegex(ValueError, "replaced or retimed"):
                meter._sample(snapshot(841, 402), {"onix": actor})
            actor["engineObject"]["facing"] = 2
            plan["behaviorFingerprint"] ^= 1
            with self.assertRaisesRegex(ValueError, "replaced or retimed"):
                meter._sample(snapshot(841, 402), {"onix": actor})
            plan["behaviorFingerprint"] ^= 1
            meter._sample(snapshot(848, 403), {"onix": actor})
            self.assertTrue(meter.pending_after_exit)
            self.assertEqual(meter.off_line_active["flags"] & (ACTIVE | PENDING),
                             ACTIVE | PENDING)
            state["flags"] = ACTIVE | UNTIL_CRASH
            meter.ordinary_complete = {"finishFrame": 854}
            with self.assertRaisesRegex(ValueError, "before a legal intent"):
                meter._sample(snapshot(855, 403), {"onix": actor})
            meter.current_events = [{"kind": "native", "frame": 855, "data": {
                "actorHandle": actor["handle"]["value"],
                "actor": {key: value for key, value in actor["handle"].items()
                          if key != "value"},
                "event": "INTENT_CREATED", "sequence": 1}},
                {"kind": "native", "frame": 855, "data": {
                    "actorHandle": actor["handle"]["value"],
                    "event": "MOTION_STARTED", "valueA": 1, "sequence": 2}}]
            actor["origin"] = {"x": 601, "y": 402}
            actor["target"] = {"x": 602, "y": 402}
            meter._sample(snapshot(855, 403), {"onix": actor})
            self.assertEqual(meter.presentation["frame"], 855)
            self.assertEqual(meter.charge_heading, (1, 0))
            self.assertEqual(meter.first_charge["frame"], 855)

    def test_same_frame_terrain_receipt_is_bound_to_current_actor_snapshot(self):
        evaluator = TestEvaluator.__new__(TestEvaluator)
        evaluator.test = {"id": "profile.ram.brief-notice"}
        evaluator.subjects = {"onix": {}}
        evaluator.latest = {"frame": 837, "nativeCycle": 1837,
                            "context": {"mapId": 33}, "actors": [{"species": 95}]}
        class TerrainMeter:
            def __init__(self):
                self.receipts = []
            def observe_terrain(self, snapshot):
                self.receipts.append(snapshot["terrain"])
        meter = TerrainMeter()
        evaluator.measurements = {KIND: meter}
        evaluator.result = lambda: {"state": "running"}
        failures = []
        evaluator.fail = lambda *args: failures.append(args)
        snapshot = deepcopy(evaluator.latest)
        snapshot["terrain"] = {"observation": {"nativeCycle": 1837}}
        row = {"phase": "setup", "action": "read-current-line-terrain",
               "command": "terrain", "snapshot": snapshot,
               "receipt": {"terrain": deepcopy(snapshot["terrain"])}}
        evaluator.observe_brief_terrain(row)
        self.assertEqual(meter.receipts, [snapshot["terrain"]])
        self.assertEqual(failures, [])
        wrong = deepcopy(row)
        wrong["snapshot"]["nativeCycle"] += 1
        evaluator.observe_brief_terrain(wrong)
        self.assertEqual(len(failures), 1)
        self.assertEqual(len(meter.receipts), 1)


if __name__ == "__main__":
    unittest.main()
