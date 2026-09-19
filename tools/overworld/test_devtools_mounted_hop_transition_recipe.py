"""Registered route and copied-row controls; never boots a ROM."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.control import _shared_test_registration
from tools.overworld.devtools_mounted_hop_transition_proof import (
    KIND, FAULTS, MountedHopTransitionNegative, validate_negative_result,
)
from tools.overworld.test_devtools_mounted_hop_transition import replay

ROOT=Path(__file__).resolve().parents[2]


class HopTransitionRecipeTests(unittest.TestCase):
    def recipe(self):
        return json.loads((ROOT/'tests/overworld/test-recipes/mount.transition-mid-motion.json').read_text())

    def test_registration_installs_exact_meter(self):
        test=validate_test(self.recipe())
        evaluator=TestEvaluator(test)
        evaluator.install_measurements(measurement_inputs(test,ROOT))
        self.assertEqual(list(evaluator.measurements),[KIND])
        registration,_=_shared_test_registration(test,ROOT)
        self.assertEqual(registration['requirements'],['legacy.mounted-transition'])
        self.assertEqual(registration['minimumObservedFrames'],5000)
        self.assertEqual(len(test['actions']),505)

    def test_recipe_rejects_shortened_floor_or_changed_input(self):
        for fault in ('floor','route','subject','setup'):
            value=self.recipe()
            if fault=='floor':value['budgets']['minObservedFrames']=4999
            elif fault=='route':value['actions'][4]['args']['frames']=19
            elif fault=='subject':value['subjects'][0]['species']=155
            else:value['setup'][0]['args']['x']=670
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_test(value)

    def test_controller_copied_rows_hit_the_named_failure(self):
        for fault in FAULTS:
            negative=MountedHopTransitionNegative(fault)
            def mutate(_elapsed,snapshot,events):
                actor=snapshot['actors'][0]
                subject=dict(subjectIdentity=actor['subjectIdentity'],handle=deepcopy(actor['handle']))
                row=dict(phase='observe',samples=[snapshot],events=events)
                changed=negative.mutate(row,{'mankey':subject})
                if changed is not row:
                    snapshot.clear();snapshot.update(changed['samples'][0])
                    events[:]=changed['events']
            with self.subTest(fault=fault):
                result=replay(mutate,soak=40).finish()
                self.assertTrue(negative.applied)
                validate_negative_result(dict(passed=result['passed'],failures=result['failures'],
                                              measurements={KIND:result}),fault)


if __name__=='__main__':unittest.main()
