"""Checked wiring preserves both original feedback cases and separate control."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.control import _shared_test_registration, _shared_recorder_kind

ROOT = Path(__file__).resolve().parents[2]
NAMES = ("walk.stomp.feedback", "observation.stomp-policy-control")


def recipe(name):
    return json.loads((ROOT / "tests/overworld/test-recipes" / (name + ".json")).read_text())


class StompRecipeTests(unittest.TestCase):
    def test_both_recipes_install_their_exact_meter_and_registration(self):
        for name in NAMES:
            test = validate_test(recipe(name))
            evaluator = TestEvaluator(test)
            evaluator.install_measurements(measurement_inputs(test, ROOT))
            self.assertEqual(set(evaluator.measurements), {test['measurements'][0]['kind']})
            registration, _ = _shared_test_registration(test, ROOT)
            self.assertEqual(registration['requirements'], test['requirements'])
        self.assertEqual(_shared_recorder_kind('shared.stomp-recorder-control-v1'), 'live-stomp-control-v1')

    def test_route_cannot_omit_or_change_feedback_witness(self):
        for name in NAMES:
            for fault in ('omit', 'keys', 'positive-time', 'threshold', 'negative-time', 'stop', 'mode'):
                test = recipe(name)
                if fault == 'omit': test['actions'].pop(2)
                elif fault == 'keys': test['actions'][1]['args']['keys'] = ['UP']
                elif fault == 'positive-time': test['setup'][4]['args']['travelTime'] = 3
                elif fault == 'threshold': test['setup'][4]['args']['stompTime'] = 0
                elif fault == 'negative-time': test['actions'][3]['args']['travelTime'] = 2
                elif fault == 'stop': test['actions'][1]['args'].pop('until')
                else: test['mode'] = 'normal'
                with self.subTest(name=name, fault=fault), self.assertRaises(ValueError): validate_test(test)

    def test_fault_control_cannot_enter_gameplay_recipe(self):
        test = recipe(NAMES[0])
        action = deepcopy(test['actions'][-1])
        action.update(id='wrong-control', op='stomp.calibrate')
        test['actions'].insert(-1, action)
        with self.assertRaises(ValueError): validate_test(test)


if __name__ == '__main__': unittest.main()
