"""The diagnostic queue prefix preserves the normal route setup and input."""
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import validate_test

ROOT=Path(__file__).resolve().parents[2]
RECIPES=ROOT/'tests/overworld/test-recipes'


class QueueClockPrefixRecipeTests(unittest.TestCase):
    def test_exact_setup_and_sixteen_leg_prefix_without_acceptance(self):
        full=json.loads((RECIPES/'diagnostic.unmounted.host-hitch-followthrough.json').read_text())
        short=json.loads((RECIPES/'diagnostic.unmounted.queue-clock-prefix.json').read_text())
        validate_test(short)
        self.assertEqual(len(short['setup']),7)
        self.assertEqual(short['setup'],full['setup'])
        self.assertEqual(len(short['actions']),32)
        self.assertEqual(short['actions'],full['actions'][:32])
        self.assertEqual(short['fixture'],full['fixture'])
        self.assertEqual(short['subjects'],full['subjects'])
        self.assertEqual(short['mode'],full['mode'])
        self.assertEqual(short['expectationSource'],full['expectationSource'])
        self.assertEqual(short['requirements'],[])
        self.assertEqual(short['measurements'],full['measurements'])
        self.assertIs(short['diagnosticContinueHostHitches'],True)
        self.assertEqual(short['spawnObserverCost'],'baseline')
        self.assertEqual(short['diagnosticContinueHostHitches'],full['diagnosticContinueHostHitches'])
        self.assertEqual(short['budgets'],dict(maxSeconds=240,maxFrames=2500,
            noProgressFrames=600,minObservedFrames=1))
        self.assertEqual(short['assertions'],[full['actions'][31]['args']['predicate']])
        self.assertEqual(short['assertions'],[dict(kind='player-settled-at',map=67,x=543,z=393)])
        self.assertIn('no acceptance',short['title'])

    def test_full_route_prefix_keeps_exact_setup_and_stops_at_route_087(self):
        source = json.loads((RECIPES/'world.unmounted.long-travel-cadence.json').read_text())
        prefix = json.loads((RECIPES/'diagnostic.unmounted.queue-clock-full-route-prefix.json').read_text())
        validate_test(prefix)
        self.assertEqual(prefix['setup'], source['setup'])
        self.assertEqual(prefix['actions'], source['actions'][:174])
        self.assertEqual(prefix['actions'][-1]['id'], 'route-087-settle')
        self.assertEqual(prefix['fixture'], source['fixture'])
        self.assertEqual(prefix['subjects'], source['subjects'])
        self.assertEqual(prefix['expectationSource'],
                         'tests/overworld/scenarios/world.unmounted.long-travel-cadence.json')
        self.assertEqual(prefix['requirements'], [])
        self.assertTrue(prefix['diagnosticContinueHostHitches'])
        self.assertEqual(prefix['spawnObserverCost'], 'baseline')
        self.assertEqual(prefix['budgets'], dict(maxSeconds=900, maxFrames=9000,
            noProgressFrames=600, minObservedFrames=1))
        self.assertEqual(prefix['assertions'], [dict(kind='player-settled-at',
            map=67, x=555, z=393)])
        self.assertIn('no acceptance', prefix['title'])


if __name__=='__main__':unittest.main()
