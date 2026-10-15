"""Focused host controls for the accepted Throw notice Walk contract."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld import test_devtools_test_contract as contract_tests
from tools.overworld.devtools_throw_notice_walk_commit_measurement import (
    KIND, NOTICE, THROW_APPLICATION, THROW_MASK, ThrowNoticeWalkCommitMeasurement,
    validate_recipe,
)
from tools.overworld.devtools_throw_notice_walk_commit_proof import (
    FAULTS, ThrowNoticeWalkCommitNegative, measurements,
)
from tools.overworld.proof_adapters import ADAPTERS


ROOT = Path(__file__).resolve().parents[2]


def actor(slot, species, frame):
    handle = {"value": (2 << 16) | slot, "slot": slot, "generation": 2,
              "fieldEpoch": 3, "mapGeneration": 3, "encounterGeneration": 1}
    moving = species == 74 and slot == 1 and 1 <= frame < 17
    return {"handle": handle, "subjectIdentity": 100 + slot, "species": species,
            "role": "WILD", "active": True, "identityVerified": True,
            "presentationAttached": True, "authorityGeneration": 1,
            "engineAnchorGeneration": 1, "presentationGeneration": 1,
            "engineIdentity": {}, "motionKind": "WALK" if moving else "NONE",
            "motionPhase": "MOVING" if moving else "IDLE",
            "motionElapsed": frame - 1 if moving else 0,
            "motionDuration": 16 if moving else 0,
            "reservationId": 16 if moving else 0,
            "commitSequence": int(slot == 1 and frame >= 17),
            "origin": {"x": 586, "y": 412}, "target": {"x": 586, "y": 411},
            "engineObject": {"facing": 0},
            "behaviorFingerprint": (200 if frame >= 2 else 100),
            "matchedLayerMask": THROW_MASK if frame >= 2 else 0,
            "movementPolicy": {"base": 16}}


def frame_row(frame):
    actors = [actor(0, 143, frame), actor(1, 74, frame)]
    geodude = actors[1]
    plan = {"version": 1, "kind": 1, "fieldEpoch": 3,
            "reservationId": 16, "origin": [586, 412], "target": [586, 411],
            "duration": 16, "facing": 0}
    combat = {"schemaVersion": 1, "available": True, "frame": frame,
              "nativeCycle": 1000 + frame,
              "observationBoundary": "main-task-queue-completion",
              "identity": {"romSha256": "a" * 64},
              "targets": [{"handle": geodude["handle"],
                  "role": "WILD", "species": 74,
                  "motion": {"phase": geodude["motionPhase"], "plan": deepcopy(plan)}}],
              "interactions": {"schemaVersion": 1, "available": True,
                  "frame": frame, "nativeCycle": 1000 + frame,
                  "identity": {"romSha256": "a" * 64},
                  "carriers": [{"slot": 1,
                      "handle": geodude["handle"], "bindings": {"trigger": {
                          "bound": True, "targetCurrent": True,
                          "sourceConditionId": NOTICE,
                          "sourceApplication": THROW_APPLICATION,
                          "target": {"kind": "PLAYER"}}}}]}}
    snapshot = {"frame": frame, "nativeCycle": 1000 + frame,
                "romSha256": "a" * 64,
                "context": {"mapId": 33, "fieldEpoch": 3, "mapGeneration": 3},
                "player": {"x": 585, "y": 406 if frame <= 1 else 407}, "actors": actors,
                "pokemonCombat": combat}
    events = []
    if frame == 2:
        events.append({"kind": "native", "frame": frame, "data": {
            "event": "CONDITIONAL_RESOLVED", "actorHandle": geodude["handle"]["value"],
            "valueA": NOTICE, "sequence": 1}})
        lane = bytearray(80)
        lane[7] = 8
        raw = bytearray(216)
        raw[:80] = lane
        raw[80:160] = lane
        raw[188:192] = THROW_MASK.to_bytes(4, "little")
        raw[192:196] = geodude["behaviorFingerprint"].to_bytes(4, "little")
        events.append({"kind": "native-observation", "frame": frame, "data": {
            "observation": "behavior-resolved", "resolved": True,
            "fingerprint": geodude["behaviorFingerprint"],
            "appliedOverrides": THROW_MASK, "resultHex": raw.hex(),
            "lanes": [raw[:80].hex(), raw[80:160].hex()]}})
    if frame == 17:
        for seq, name in enumerate(("LOGICAL_COMMIT", "MOTION_FINISHED",
                                    "CONTROL_RETURNED"), 2):
            events.append({"kind": "native", "frame": frame, "data": {
                "event": name, "actorHandle": geodude["handle"]["value"],
                "sequence": seq, "valueA": 1, "valueB": 1}})
    return {"samples": [snapshot], "events": events}


class ThrowNoticeWalkCommitHostTests(unittest.TestCase):
    def test_prepared_passive_follower_has_exact_separate_handoff(self):
        recipe = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/wild.throw-notice-walk-commit.json").read_text()))
        self.assertLess(next(i for i, a in enumerate(recipe["setup"]) if a["id"] == "spawn-geodude"),
                        next(i for i, a in enumerate(recipe["setup"]) if a["id"] == "bind-snorlax"))
        _, source = contract_tests.RamLedgeAuxiliaryFollowerTests().fixture()
        for fault in (None, "personality", "reserved", "lifecycle"):
            evaluator = TestEvaluator(recipe)
            evaluator.install_measurements({KIND: {"contractVersion": 1}})
            evaluator.latest = deepcopy(source["receipt"]["snapshot"])
            evaluator.latest["frame"] = 1
            evaluator.latest["nativeCycle"] = 1
            evaluator.latest["actors"] = []
            row = deepcopy(source)
            row["action"] = "create-passive-follower"
            row["snapshot"]["actors"][0]["level"] = 20
            row["receipt"]["requestedSubject"]["level"] = 20
            if fault == "personality":
                row["receipt"]["requestedSubject"]["personality"] += 1
            elif fault == "reserved":
                row["snapshot"]["actors"][0]["reservationId"] = 7
            elif fault == "lifecycle":
                row["receipt"]["lifecycle"] = "spawn-prepared"
            result = evaluator.observe_prepared_command(row)
            with self.subTest(fault=fault):
                self.assertEqual(result["state"] == "failed", fault is not None)
                if fault is None:
                    self.assertEqual(evaluator.subjects, {})
                    self.assertEqual(evaluator.measurements[KIND].prepared, [])

    def test_exact_registered_recipe(self):
        path = ROOT / "tests/overworld/test-recipes/wild.throw-notice-walk-commit.json"
        recipe = validate_test(json.loads(path.read_text()))
        validate_recipe(recipe)
        self.assertEqual(ADAPTERS[KIND].requirement, "current.throw-notice-walk-commit")
        wrong = deepcopy(recipe)
        wrong["setup"][5]["args"]["frames"] = 41
        with self.assertRaises(ValueError):
            validate_recipe(wrong)

    def test_same_token_returns_control_and_copied_faults_fail(self):
        rows = [frame_row(frame) for frame in range(26)]
        meter = ThrowNoticeWalkCommitMeasurement()
        for index, row in enumerate(rows):
            result = meter.observe(row["samples"][0], row["events"])
            if index == 1:
                self.assertTrue(meter.stage("ordinary-up-walk"))
                self.assertIsNone(result["notice"])
            if index == 2:
                self.assertEqual(result["notice"]["frame"], 2)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["subject"], result["subjects"]["snorlax"])
        self.assertTrue(meter.stage("ordinary-up-walk"))
        self.assertEqual(result["walk"]["origin"], [586, 412])
        self.assertEqual(result["notice"]["resolvedSpeed"], 8)
        record = {"sessionId": "host", "sessionCleanup": {
            "sessionId": "host", "closed": True, "errors": []}}
        proof = measurements({"passed": True, "failures": [],
                              "measurements": {KIND: result}}, record)
        self.assertEqual(len(proof), 8)
        for fault in FAULTS:
            control = ThrowNoticeWalkCommitNegative(fault)
            meter = ThrowNoticeWalkCommitMeasurement()
            for row in rows:
                changed = control.mutate(row, {})
                for sample in changed["samples"]:
                    result = meter.observe(sample, changed["events"])
                if result["failures"]:
                    break
            self.assertTrue(control.applied, fault)
            self.assertFalse(result["passed"], fault)
            self.assertTrue(result["failures"], fault)

    def test_next_frame_player_tile_and_native_speed_are_required(self):
        for fault in ("player-stayed-outside", "wrong-resolved-speed"):
            rows = [frame_row(frame) for frame in range(3)]
            if fault == "player-stayed-outside":
                rows[2]["samples"][0]["player"]["y"] = 406
            else:
                resolved = next(e["data"] for e in rows[2]["events"]
                                if e["kind"] == "native-observation")
                raw = bytearray.fromhex(resolved["resultHex"])
                raw[7] = raw[87] = 4
                resolved["resultHex"] = raw.hex()
                resolved["lanes"] = [raw[:80].hex(), raw[80:160].hex()]
            meter = ThrowNoticeWalkCommitMeasurement()
            for row in rows:
                result = meter.observe(row["samples"][0], row["events"])
            with self.subTest(fault=fault):
                self.assertFalse(result["passed"])
                self.assertTrue(result["failures"])

    def test_current_in_range_north_origins_keep_the_same_terminal_proof(self):
        for x in (586, 587, 580, 590):
            origin, target = [x, 412], [x, 411]
            rows = [frame_row(frame) for frame in range(26)]
            for row in rows:
                sample = row["samples"][0]
                geodude = sample["actors"][1]
                geodude["origin"] = dict(x=origin[0], y=origin[1])
                geodude["target"] = dict(x=target[0], y=target[1])
                plan = sample["pokemonCombat"]["targets"][0]["motion"]["plan"]
                plan.update(origin=origin, target=target)
            meter = ThrowNoticeWalkCommitMeasurement()
            for index, row in enumerate(rows):
                result = meter.observe(row["samples"][0], row["events"])
                if index == 1:
                    self.assertTrue(meter.stage("ordinary-up-walk"), target)
            with self.subTest(target=target):
                self.assertTrue(result["passed"], result["failures"])
                self.assertEqual(result["walk"]["target"], list(target))
                self.assertEqual(result["walk"]["plan"]["duration"], 16)
                self.assertEqual(result["notice"]["resolvedSpeed"], 8)
                self.assertEqual(result["returned"]["frame"], 17)
                self.assertEqual(result["postFrames"], 8)

    def test_wrong_notice_geometry_or_stale_plan_cannot_open_the_stage(self):
        for fault in ("east", "diagonal", "same-tile", "outside-row", "outside-range",
                      "wrong-facing", "stale-native-origin", "stale-native-target"):
            rows = [frame_row(frame) for frame in range(2)]
            sample = rows[1]["samples"][0]
            geodude = sample["actors"][1]
            plan = sample["pokemonCombat"]["targets"][0]["motion"]["plan"]
            if fault == "stale-native-target":
                plan["target"] = [587, 412]
            elif fault == "stale-native-origin":
                plan["origin"] = [587, 412]
            elif fault == "wrong-facing":
                geodude["engineObject"]["facing"] = plan["facing"] = 1
            else:
                origin, target = {
                    "east": ([586, 412], [587, 412]),
                    "diagonal": ([586, 412], [587, 411]),
                    "same-tile": ([586, 412], [586, 412]),
                    "outside-row": ([586, 413], [586, 412]),
                    "outside-range": ([591, 412], [591, 411]),
                }[fault]
                geodude["origin"] = dict(x=origin[0], y=origin[1])
                geodude["target"] = dict(x=target[0], y=target[1])
                plan.update(origin=origin, target=target)
            meter = ThrowNoticeWalkCommitMeasurement()
            for row in rows:
                meter.observe(row["samples"][0], row["events"])
            with self.subTest(fault=fault):
                self.assertFalse(meter.stage("ordinary-up-walk"))
                result = meter.finish()
                self.assertFalse(result["passed"])
                self.assertTrue(result["failures"])


if __name__ == "__main__":
    unittest.main()
