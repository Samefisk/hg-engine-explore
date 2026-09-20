"""Shared registration/replay/acceptance wiring; fake package is not live proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.overworld import control
from tools.overworld import test_devtools_test_proof as fixtures
from tools.overworld import test_devtools_resolver_proof as native_fixtures
from tools.overworld.devtools_test_contract import validate_test


class SharedResolverControllerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SharedProofTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        real = Path(__file__).resolve().parents[2]
        self.test = validate_test(json.loads((real/'tests/overworld/test-recipes/profile.resolve.packaged-rom-parity.json').read_text()))
        source = self.f.root/'tests/overworld/test-recipes/profile.resolve.packaged-rom-parity.json'
        source.write_text(json.dumps(self.test))
        registry = json.loads((real/'tools/overworld/runtime_proof_registry.json').read_text())
        self.registration = registry['sharedTests'][self.test['id']]
        self.registration['recipeSha256'] = fixtures.sha(source)
        (self.f.root/'tools/overworld/runtime_proof_registry.json').write_text(json.dumps(registry))
        _, self.rows, self.oracle = native_fixtures.ResolverProofTests().fixture()
        self.rows[0]['initialSnapshot'].update(prepared=False,fieldAvailable=True,actors=[])
        row=self.rows[1]; row.update(phase='observe',action='resolve-eight-cases')
        row['snapshot'].update(prepared=True,fieldAvailable=True,actors=[])
        row['receipt']['snapshot']=deepcopy(row['snapshot'])
        row['receipt']['events']=[]
        self.record = deepcopy(self.f.record)
        self.record.update(test=self.test['id'],testSourceSha256=fixtures.sha(source),
            sessionCleanup=dict(sessionId='session-proof',closed=True,errors=[]))
        self.record['fixtureProof'].update(registration=self.registration,testSourceSha256=fixtures.sha(source))
        self.refresh()

    def refresh(self):
        self.f.rows=self.rows; self.f.write_rows()
        self.record['observationsArtifact']=self.f.artifact()
        self.record['evaluation']=control._replay_shared_test(self.test,self.rows,repo=self.f.root)

    def finish(self):
        with patch.object(control,'source_record',return_value={'hash':'source'}), \
                patch.object(control,'_resolver_probe_oracle',return_value=self.oracle):
            return control.finalize_shared_test(self.test,self.record,self.f.root)

    def test_subjectless_service_accepts_only_exact_eight_measurements(self):
        result=self.finish()
        self.assertTrue(result['acceptedProof'],result)
        proof=result['proofAcceptance']
        self.assertEqual(proof['subjects'],{})
        self.assertEqual(proof['claims'],['profile-resolution'])
        self.assertEqual(len(proof['measurements']),8)
        self.assertEqual(proof['observedFrames'],1)
        self.assertEqual(proof['observedFrameUnit'],'native-resolver-cycles')
        self.assertEqual(proof['completedGameFrames'],0)
        self.assertEqual(len(proof['controls']),7)

    def test_missing_cleanup_and_changed_source_cannot_pass(self):
        self.record['sessionCleanup']['closed']=False
        self.assertFalse(self.finish()['acceptedProof'])
        self.record['sessionCleanup']['closed']=True
        self.record['fixtureProof']['source']={'hash':'old'}
        self.assertFalse(self.finish()['acceptedProof'])

    def test_plausible_readiness_with_wrong_result_still_fails_full_comparison(self):
        case=self.rows[1]['receipt']['value']['receipts'][0]
        case['resultHex']='ff'+case['resultHex'][2:]
        self.refresh()
        self.assertTrue(self.record['evaluation']['passed'])
        result=self.finish()
        self.assertFalse(result['acceptedProof'])
        self.assertIn('full result bytes differ',result['proofAcceptance']['reason'])

    def test_wrong_action_missing_snapshot_and_duplicate_probe_fail_replay(self):
        for fault in ('action','snapshot','duplicate'):
            rows=deepcopy(self.rows)
            if fault=='action': rows[1]['action']='unlisted'
            if fault=='snapshot': rows[1]['receipt'].pop('snapshot')
            if fault=='duplicate': rows.append(deepcopy(rows[1]))
            with self.subTest(fault=fault):
                result=control._replay_shared_test(self.test,rows,repo=self.f.root)
                self.assertFalse(result['passed'])


if __name__=='__main__': unittest.main()
