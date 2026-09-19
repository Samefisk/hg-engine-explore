"""Full shared replay and controller negatives; no guest acceptance claim."""
from copy import deepcopy
import json
import unittest

from tools.overworld.control import _replay_shared_test
from tools.overworld.devtools_walk_policy_control_proof import (
    KIND, RULES, FAULTS, measurements, validate_negative_result,
)
from tools.overworld.test_devtools_walk_policy_control_measurement import fixture


class WalkPolicyControlProofTests(unittest.TestCase):
    def test_complete_motion_can_change_lookup_movement_flags(self):
        for role in ("WILD", "MOUNTED"):
            test, rows = fixture(role)
            def decorate(value):
                if isinstance(value, dict):
                    identity = value.get("engineIdentity")
                    if isinstance(identity, dict):
                        identity["id_lookup"] = {"matching_objects": [{
                            "pointer": identity["pointer"], "flags": 1066017,
                            "active": True, "flag25": False, "lookup_eligible": True}]}
                    for child in value.values(): decorate(child)
                elif isinstance(value, list):
                    for child in value: decorate(child)
            decorate(rows)
            for row in rows:
                for snapshot in row.get("samples", []):
                    for actor in snapshot["actors"]:
                        if actor.get("motionPhase") == "MOVING":
                            actor["engineIdentity"]["id_lookup"]["matching_objects"][0]["flags"] = 1065987
            original = deepcopy(rows)
            replay = _replay_shared_test(test, rows)
            self.assertTrue(replay["passed"], replay["failures"])
            self.assertEqual(rows, original)

    def test_persisted_evaluation_equals_independent_replay(self):
        for role in ("WILD", "MOUNTED"):
            for first_elapsed in (0, 1):
                test, rows = fixture(role, first_elapsed=first_elapsed)
                replay = _replay_shared_test(test, rows)
                self.assertTrue(replay["passed"], replay["failures"])
                self.assertEqual(replay, json.loads(json.dumps(replay)))

    def test_fourteen_motion_parity_survives_storage(self):
        from tools.overworld.test_devtools_acceleration_contract import integration_fixture, replay as replay_parity
        test, rows = integration_fixture()
        replay = replay_parity(test, rows).finish()
        self.assertTrue(replay["passed"], replay["failures"])
        self.assertEqual(replay, json.loads(json.dumps(replay)))

    def test_elapsed_one_complete_replay_and_all_controls(self):
        for role in ("WILD", "MOUNTED"):
            test, rows = fixture(role, first_elapsed=1)
            baseline = _replay_shared_test(test, rows)
            self.assertTrue(baseline["passed"], baseline["failures"])
            for fault in FAULTS:
                with self.subTest(role=role, fault=fault):
                    validate_negative_result(_replay_shared_test(test, rows, fault=fault), fault)

    def test_prior_pose_error_is_not_missing_start_proof(self):
        test, rows = fixture("MOUNTED", first_elapsed=1)
        arm = next(r for r in rows if r.get("action") == "arm")
        arm["snapshot"]["player"]["pos_x"] += 1
        arm["receipt"]["snapshot"]["player"]["pos_x"] += 1
        result = _replay_shared_test(test, rows)
        self.assertFalse(result["passed"])
        with self.assertRaisesRegex(ValueError, "unrelated reason"):
            validate_negative_result(result, "walk-policy-missing-start")

    def test_both_roles_complete_exact_four_rows(self):
        for role in ("WILD", "MOUNTED"):
            test, rows = fixture(role)
            replay = _replay_shared_test(test, rows)
            self.assertTrue(replay["passed"], replay["failures"])
            record = dict(sessionId="session-host", sessionCleanup=dict(sessionId="session-host", closed=True, errors=[]))
            result = measurements(replay, record, policy_address=0x022005BC)
            self.assertEqual([(r["claim"], r["name"]) for r in result], list(RULES))
            self.assertTrue(all(type(r["value"]) is int and r["value"] == 1 for r in result))

    def test_same_replay_rejects_each_changed_meaning(self):
        test, rows = fixture()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                result = _replay_shared_test(test, rows, fault=fault)
                validate_negative_result(result, fault)

    def test_no_cleanup_wrong_address_and_missing_lifecycle_reject(self):
        test, rows = fixture()
        baseline = _replay_shared_test(test, rows)
        for fault in ("cleanup", "address", "trace", "subject", "motion", "pending"):
            replay = deepcopy(baseline)
            record = dict(sessionId="session-host", sessionCleanup=dict(sessionId="session-host", closed=True, errors=[]))
            meter = replay["measurements"][KIND]
            address = 0x022005BC
            if fault == "cleanup": record["sessionCleanup"]["closed"] = False
            elif fault == "address": address += 32
            elif fault == "trace": meter["traces"] = []
            elif fault == "subject": meter["control"]["subject"]["authorityGeneration"] += 1
            elif fault == "motion": meter["motions"] = []
            else: meter["control"]["cleanupPending"] = True
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                measurements(replay, record, policy_address=address)


if __name__ == "__main__":
    unittest.main()
