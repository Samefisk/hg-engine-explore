"""Shared evaluator integration controls; synthetic data is not game proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.test_devtools_test_contract import recipe
from tools.overworld.test_devtools_chain_measurement import SCHEMA, SOURCE, Stream


def measured_recipe():
    value = recipe()
    value["subjects"][0]["acquire"] = "spawn"
    value["measurements"] = [{"kind": "ledyba-chain-v1", "subject": "subject"}]
    value["assertions"] = [{"kind": "measurement-complete", "measurement": "ledyba-chain-v1"}]
    return value


class MeasurementContractTests(unittest.TestCase):
    def test_measurement_is_explicit_and_normal_exact_subject_only(self):
        value = measured_recipe()
        self.assertEqual(validate_test(value)["measurements"], value["measurements"])
        for edit in (
            lambda t: t.update(mode="prepared"),
            lambda t: t["subjects"][0].update(species=19),
            lambda t: t["subjects"][0].update(role="FOLLOWER"),
            lambda t: t["subjects"][0].update(acquire="existing"),
            lambda t: t["measurements"][0].update(kind="arbitrary-module"),
            lambda t: t.update(measurements=[]),
            lambda t: t["measurements"].append(deepcopy(t["measurements"][0])),
        ):
            invalid = deepcopy(value); edit(invalid)
            with self.subTest(value=invalid), self.assertRaises(ValueError): validate_test(invalid)

    def test_missing_current_measurement_inputs_cannot_pass(self):
        evaluator = TestEvaluator(measured_recipe())
        with self.assertRaises(ValueError): evaluator.install_measurements({})
        self.assertFalse(evaluator.finish()["passed"])

    def test_fixed_inputs_install_once_before_observation(self):
        evaluator = TestEvaluator(measured_recipe())
        inputs = {"ledyba-chain-v1": {"schema": SCHEMA, "sourceSha256": SOURCE}}
        evaluator.install_measurements(inputs)
        self.assertFalse(evaluator.result()["measurements"]["ledyba-chain-v1"]["ready"])
        with self.assertRaises(ValueError): evaluator.install_measurements(inputs)
        final = evaluator.finish()
        self.assertFalse(final["passed"])
        self.assertFalse(final["measurements"]["ledyba-chain-v1"]["passed"])

    def test_complete_stream_and_exact_binding_reach_same_evaluator(self):
        stream = Stream().complete()
        items = deepcopy(stream.items)
        handle = items[1][0]["actors"][0]["handle"]
        attached = {"frame": items[1][0]["frame"], "kind": "native", "data": {
            "traceStream": 1, "sequence": 1, "event": "ACTOR_ATTACHED", "actorHandle": handle["value"],
            "actor": {key: value for key, value in handle.items() if key != "value"},
            "valueA": 0, "valueB": 0}}
        for _, events in items:
            for event in events:
                if event["kind"] == "native": event["data"]["sequence"] += 1
        items[1][1].insert(0, attached)
        value = measured_recipe()
        value["budgets"].update(maxFrames=len(items) + 1)
        evaluator = TestEvaluator(value)
        evaluator.install_measurements({"ledyba-chain-v1": {"schema": SCHEMA, "sourceSha256": SOURCE}})
        for index, (snapshot, events) in enumerate(items):
            observed = evaluator.observe(snapshot, events, count_frame=index > 1)
            self.assertFalse(observed["failures"], observed["failures"])
            if index == 1: evaluator.bind("subject", snapshot)
        self.assertTrue(evaluator.check(value["assertions"][0]))
        result = evaluator.finish()
        self.assertTrue(result["passed"], result)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["measurements"]["ledyba-chain-v1"]["completeMotions"], 45)


if __name__ == "__main__":
    unittest.main()
