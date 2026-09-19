"""Shared POOL contract/input checks; these are not live spawn proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_test_contract import recipe
from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE


KIND = "pool-spawn-v1"
ROOT = Path(__file__).resolve().parents[2]


def pool_recipe():
    value = recipe()
    value["subjects"][0]["acquire"] = "spawn"
    value["measurements"] = [{"kind": KIND, "subject": "subject"}]
    value["assertions"] = [{"kind": "measurement-complete", "measurement": KIND}]
    return value


class PoolContractTests(unittest.TestCase):
    def test_normal_spawned_wild_ledyba_is_the_only_supported_subject(self):
        value = pool_recipe()
        self.assertEqual(validate_test(value)["measurements"], value["measurements"])
        for edit in (
            lambda t: t.update(mode="prepared"),
            lambda t: t.update(mode="observer-control"),
            lambda t: t["subjects"][0].update(species=166),
            lambda t: t["subjects"][0].update(role="MOUNTED"),
            lambda t: t["subjects"][0].update(acquire="existing"),
            lambda t: t["measurements"][0].update(subject="missing"),
            lambda t: t["measurements"][0].update(authoredProfiles={}),
            lambda t: t["measurements"].append(deepcopy(t["measurements"][0])),
            lambda t: t.update(measurements=[]),
        ):
            invalid = deepcopy(value); edit(invalid)
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                validate_test(invalid)

    def test_profile_json_and_hash_use_one_exact_read(self):
        raw = b'{ "overrideProfiles": [], "name": "original" }\n'
        changed = b'{"overrideProfiles": [], "name": "changed"}'
        reads = []

        def read_bytes(path):
            self.assertEqual(path, ROOT / "data/overworld_behavior_profiles.json")
            reads.append(path)
            return raw if len(reads) == 1 else changed

        with patch.object(Path, "read_bytes", read_bytes), \
                patch.object(Path, "read_text", return_value=json.dumps(SCHEMA)):
            loaded = measurement_inputs(pool_recipe(), ROOT)[KIND]
        self.assertEqual(len(reads), 1)
        self.assertEqual(set(loaded), {"schema", "sourceSha256", "authoredProfiles"})
        self.assertEqual(loaded["sourceSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(loaded["authoredProfiles"], json.loads(raw))

    def test_changed_source_changes_both_retained_inputs(self):
        values = []
        for name in ("old", "new"):
            raw = json.dumps({"overrideProfiles": [], "name": name}).encode()
            with patch.object(Path, "read_bytes", return_value=raw), \
                    patch.object(Path, "read_text", return_value=json.dumps(SCHEMA)):
                values.append(measurement_inputs(pool_recipe(), ROOT)[KIND])
        self.assertNotEqual(values[0]["sourceSha256"], values[1]["sourceSha256"])
        self.assertNotEqual(values[0]["authoredProfiles"], values[1]["authoredProfiles"])

    def test_existing_measurement_inputs_keep_their_exact_two_keys(self):
        for kind in ("ledyba-chain-v1", "live-observer-control-v1"):
            value = {"measurements": [{"kind": kind}]}
            self.assertEqual(set(measurement_inputs(value, ROOT)[kind]), {"schema", "sourceSha256"})
        with patch.object(Path, "read_bytes", side_effect=AssertionError("unexpected source read")):
            self.assertEqual(measurement_inputs({}, ROOT), {})

    def test_missing_or_changed_input_shape_cannot_install(self):
        valid = {"schema": SCHEMA, "sourceSha256": SOURCE, "authoredProfiles": {"overrideProfiles": []}}
        for source in (None, {}, {k: v for k, v in valid.items() if k != "authoredProfiles"},
                       {**valid, "authoredProfiles": []}, {**valid, "unknown": True}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                TestEvaluator(pool_recipe()).install_measurements({KIND: source})

    def test_installs_actual_bounded_pool_measurement_and_does_not_pass_empty(self):
        from tools.overworld.devtools_spawn_measurement import PoolSpawnMeasurement

        value = pool_recipe()
        evaluator = TestEvaluator(value)
        inputs = measurement_inputs(value, ROOT)
        evaluator.install_measurements(inputs)
        self.assertIsInstance(evaluator.measurements[KIND], PoolSpawnMeasurement)
        self.assertFalse(evaluator.result()["measurements"][KIND]["ready"])
        with self.assertRaises(ValueError): evaluator.install_measurements(inputs)
        result = evaluator.finish()
        self.assertFalse(result["passed"])
        self.assertFalse(result["acceptedProof"])
        measured = result["measurements"][KIND]
        self.assertFalse(measured["passed"])
        self.assertTrue({"subject", "failures", "measurementErrors", "completeMotions"} <= set(measured))


if __name__ == "__main__":
    unittest.main()
