"""Surface measurement dispatch uses the shared job and sealed profile input."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_pool_contract import pool_recipe, ROOT


KIND = "pool-spawn-surface-v1"


def surface_recipe():
    value = pool_recipe()
    value["measurements"][0]["kind"] = KIND
    value["assertions"][0]["measurement"] = KIND
    return value


class SurfaceContractTests(unittest.TestCase):
    def test_dispatches_new_contract_without_widening_old_one(self):
        from tools.overworld.devtools_spawn_measurement import PoolSpawnSurfaceMeasurement
        value = surface_recipe()
        self.assertEqual(validate_test(value)["measurements"], value["measurements"])
        inputs = measurement_inputs(value, ROOT)
        self.assertEqual(set(inputs[KIND]), {"schema", "sourceSha256", "authoredProfiles"})
        original = measurement_inputs(pool_recipe(), ROOT)["pool-spawn-v1"]
        self.assertEqual(inputs[KIND], original)
        evaluator = TestEvaluator(value)
        evaluator.install_measurements(inputs)
        self.assertIsInstance(evaluator.measurements[KIND], PoolSpawnSurfaceMeasurement)
        self.assertFalse(evaluator.finish()["passed"])

    def test_requires_normal_new_wild_ledyba(self):
        for key, replacement in (("species", 56), ("role", "MOUNTED"), ("acquire", "existing")):
            value = surface_recipe()
            value["subjects"][0][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_test(value)
        for mode in ("prepared", "observer-control"):
            value = surface_recipe(); value["mode"] = mode
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                validate_test(value)

    def test_missing_or_recipe_owned_profiles_cannot_install(self):
        value = surface_recipe()
        inputs = measurement_inputs(value, ROOT)
        for fault in ("missing", "list", "extra"):
            invalid = deepcopy(inputs)
            if fault == "missing": invalid[KIND].pop("authoredProfiles", None)
            elif fault == "list": invalid[KIND]["authoredProfiles"] = []
            else: invalid[KIND]["unexpected"] = True
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                TestEvaluator(value).install_measurements(invalid)
        value["measurements"][0]["authoredProfiles"] = {}
        with self.assertRaises(ValueError): validate_test(value)


if __name__ == "__main__":
    unittest.main()
