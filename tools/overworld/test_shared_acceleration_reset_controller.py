"""Two authenticated setup calls are required; neither grants motion credit."""
from copy import deepcopy
import unittest

from tools.overworld.control import _shared_acceleration_resets
from tools.overworld.test_devtools_acceleration_proof import proof_fixture


def fixture():
    test = dict(measurements=[dict(kind="acceleration-parity-v1", subjects={"WILD": "wild", "MOUNTED": "mount"})],
                subjects=[], setup=[])
    rows = []
    for role, name in (("WILD", "wild"), ("MOUNTED", "mount")):
        row, subject, oracle = proof_fixture(role)
        test["subjects"].append(dict(id=name, species=subject["species"], role=role))
        for op in ("bind", "acceleration.begin"):
            action_id = name + "-" + op
            test["setup"].append(dict(id=action_id, op=op, args=dict(subject=name)))
            if op == "bind":
                rows.append(dict(command=op, action=action_id, phase="setup", receipt=deepcopy(subject), snapshot=row["snapshot"]))
            else:
                rows.append(dict(row, command=op, action=action_id, phase="setup"))
    return test, rows, oracle


class AccelerationResetControllerTests(unittest.TestCase):
    def test_both_exact_bound_roles(self):
        test, rows, oracle = fixture()
        result = _shared_acceleration_resets(test, rows, oracle=oracle)
        self.assertEqual(set(result), {"wild", "mount"})
        self.assertTrue(all(r["nativeCalls"] == 1 and r["observedFrames"] == 0
                            and r["acceptedProof"] is False for r in result.values()))

    def test_lost_duplicate_rebound_foreign_and_bad_package_reject(self):
        for fault in ("missing", "duplicate", "rebound", "species", "role", "action", "phase", "package"):
            test, rows, oracle = fixture()
            if fault == "missing": rows.pop()
            elif fault == "duplicate": rows.append(deepcopy(rows[-1]))
            elif fault == "rebound": rows.insert(1, deepcopy(rows[0]))
            elif fault == "species": rows[0]["receipt"]["species"] += 1
            elif fault == "role": rows[0]["receipt"]["role"] = "MOUNTED"
            elif fault == "action": rows[1]["action"] = "undeclared"
            elif fault == "phase": rows[1]["phase"] = "observe"
            else: oracle["serviceIdentity"]["entrySha256"] = "00" * 32
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                _shared_acceleration_resets(test, rows, oracle=oracle)


if __name__ == "__main__":
    unittest.main()
