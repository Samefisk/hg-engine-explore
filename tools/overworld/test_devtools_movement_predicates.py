"""Pure typed predicate controls. Native recorder controls live in its own test."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_movement_predicates import (
    check_movement_predicate as check, validate_movement_predicate as validate,
)


def snapshot():
    return {"frame": 12, "observationBoundary": "main-task-queue-completion",
            "context": {"mapId": 33}, "fieldControl": {"taskPointer": 0},
            "player": {"flags": 0x31, "x": 585, "y": 406, "x_prev": 584, "y_prev": 406,
                       "pos_x": (585 << 16) + 0x8000, "pos_z": (406 << 16) + 0x8000,
                       "unk88_y": 0, "movement_cmd": 15},
            "nativeObservation": {"coverageComplete": True, "playerStepCount": 7, "playerStepFrame": 12},
            "partyObservation": {"frame": 12, "boundary": "main-task-queue-completion"},
            "party": [{"slot": 0, "species": 155, "personality": 1234, "identityVerified": True,
                       "isEgg": False, "hp": 0, "maxHp": 20, "level": 5, "form": 0, "status": 0}],
            "selector": {"state": 2, "highlight": 0, "queue": {"count": 0}, "heldKeys": 0}}


class MovementPredicateTests(unittest.TestCase):
    def follower(self):
        from tools.overworld.test_devtools_binding_measurement import actor_fixture
        value = snapshot(); actor = actor_fixture()
        actor.update(role="FOLLOWER", species=155, subjectIdentity=1234)
        actor["handle"].update(slot=7, value=65543)
        actor["sourceIdentity"].update(species=155, personality=1234, object_id=231)
        actor["engineIdentity"].update(object_id=231, spawn_object_id=231)
        value.update(actors=[actor], context={"mapId":33,"fieldEpoch":2,"mapGeneration":4})
        value["selector"]["activeFollowerPartySlot"] = 0
        value["party"][0]["hp"] = 20
        return value

    def test_follower_settled_requires_current_idle_not_only_release(self):
        predicate = {"kind":"follower-settled", "species":155, "partySlot":0}
        value = self.follower(); before = deepcopy(value)
        self.assertTrue(check(predicate, value))
        self.assertEqual(value, before)
        value["party"][0]["status"] = 8
        self.assertTrue(check(predicate, value))  # Poison does not mean motion.
        for phase in ("PLANNED", "MOVING", "COMMIT_PENDING", "SETTLING", "CANCELED"):
            value = self.follower(); value["actors"][0].update(motionPhase=phase, motionKind="HOP")
            self.assertFalse(check(predicate, value))
        value = self.follower(); value["actors"][0]["reservationId"] = 9
        self.assertFalse(check(predicate, value))
        value["actors"] = []; self.assertFalse(check(predicate, value))

    def test_follower_settled_rejects_wrong_or_stale_identity(self):
        predicate = {"kind":"follower-settled", "species":155, "partySlot":0}
        for fault in ("pid", "stale", "unverified", "native-pid", "pointer", "party-frame", "unknown-phase", "duplicate"):
            value = self.follower(); actor = value["actors"][0]
            if fault == "pid": actor["subjectIdentity"] += 1
            elif fault == "stale": actor["handle"]["mapGeneration"] += 1
            elif fault == "unverified": actor["identityVerified"] = False
            elif fault == "native-pid": actor["sourceIdentity"]["personality"] += 1
            elif fault == "pointer": actor["engineIdentity"]["pointer"] += 4
            elif fault == "party-frame": value["partyObservation"]["frame"] -= 1
            elif fault == "unknown-phase": actor["motionPhase"] = "UNKNOWN"
            else: value["actors"].append(deepcopy(actor))
            with self.subTest(fault=fault), self.assertRaises(ValueError): check(predicate, value)
        for extra in ({"path":"motionPhase"}, {"partySlot":True}, {"species":0}):
            with self.assertRaises(ValueError): validate({**predicate, **extra})

    target = {"kind": "player-settled-at", "map": 33, "x": 585, "z": 406}

    def test_finished_held_step_retains_cardinal_previous_tile(self):
        value = snapshot()
        self.assertTrue(check(self.target, value))
        for x, z in ((584, 406), (586, 406), (585, 405), (585, 407), (585, 406)):
            value["player"].update(x_prev=x, y_prev=z)
            self.assertTrue(check(self.target, value))

    def test_idle_faces_and_none_require_the_stock_previous_reset(self):
        value = snapshot()
        for command in (0, 1, 2, 3, 255):
            for flags in (1, 0x21, 0x31):
                value["player"].update(movement_cmd=command, flags=flags, x_prev=585)
                self.assertTrue(check(self.target, value))
                value["player"]["x_prev"] = 584
                self.assertFalse(check(self.target, value))

    def test_reserved_target_inflight_and_wrong_previous_do_not_pass(self):
        for field, value in (("flags", 0x11), ("flags", 0x33), ("flags", 0x30),
                             ("pos_x", (584 << 16) + 0x8000), ("pos_z", (406 << 16) + 0x7FFF),
                             ("unk88_y", 1), ("x_prev", 583), ("y_prev", 405),
                             ("x", 584), ("movement_cmd", 200)):
            current = snapshot(); current["player"][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(check(self.target, current))
        current = snapshot(); current["context"]["mapId"] = 34
        self.assertFalse(check(self.target, current))
        current = snapshot(); current["fieldControl"]["taskPointer"] = 0x02212340
        self.assertFalse(check(self.target, current))

    def test_all_stock_ready_flag_combinations(self):
        current = snapshot(); current["player"].update(movement_cmd=255, x_prev=585)
        for flags in range(64):
            current["player"]["flags"] = flags
            # Stock active, no single movement, held absent or complete.
            expected = bool(flags & 1) and not bool(flags & 2) and (not bool(flags & 16) or bool(flags & 32))
            self.assertEqual(check(self.target, current), expected, flags)

    def test_counter_requires_complete_matching_frame(self):
        predicate = {"kind": "player-step-count", "operator": "gte", "value": 7}
        self.assertTrue(check(predicate, snapshot()))
        self.assertFalse(check({**predicate, "value": 8}, snapshot()))
        for field, value in (("coverageComplete", False), ("playerStepFrame", 11), ("playerStepFrame", True), ("playerStepCount", True)):
            current = snapshot(); current["nativeObservation"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): check(predicate, current)

    def test_party_hp_and_selector_are_real_observations_not_actions(self):
        current = snapshot(); unchanged = deepcopy(current)
        hp = {"kind": "party-field", "slot": 0, "path": "hp", "operator": "gte", "value": 1}
        self.assertFalse(check(hp, current))
        self.assertEqual(current, unchanged)
        current["party"][0]["hp"] = 20
        self.assertTrue(check(hp, current))
        self.assertTrue(check({"kind": "selector-field", "path": "state", "operator": "eq", "value": 2}, current))
        self.assertTrue(check({"kind": "selector-field", "path": "queue.count", "operator": "eq", "value": 0}, current))
        current["partyObservation"]["frame"] = 11
        with self.assertRaises(ValueError): check(hp, current)
        current = snapshot(); current["party"][0]["identityVerified"] = False
        with self.assertRaises(ValueError): check(hp, current)
        current = snapshot(); current["party"] = []
        with self.assertRaises(ValueError): check(hp, current)

    def test_missing_fields_wrong_boundaries_and_invalid_values_fail(self):
        current = snapshot(); del current["player"]["flags"]
        with self.assertRaises(ValueError): check(self.target, current)
        current = snapshot(); current["observationBoundary"] = "paused-native-cycle-end"
        with self.assertRaises(ValueError): check(self.target, current)
        for predicate in (
            {**self.target, "map": 540}, {**self.target, "x": True}, {**self.target, "z": -1},
            {**self.target, "private": "ram"}, {"kind": []},
            {"kind": "party-field", "slot": 6, "path": "hp", "operator": "eq", "value": 0},
            {"kind": "party-field", "slot": 0, "path": "isEgg", "operator": "gte", "value": False},
            {"kind": "party-field", "slot": 0, "path": "hp", "operator": "eq", "value": True},
            {"kind": "selector-field", "path": "queue.private", "operator": "eq", "value": 0},
            {"kind": "selector-field", "path": "queue.count", "operator": "eq", "value": 11},
            {"kind": "player-step-count", "operator": [], "value": 0},
        ):
            with self.subTest(predicate=predicate), self.assertRaises(ValueError): validate(predicate)


if __name__ == "__main__":
    unittest.main()
