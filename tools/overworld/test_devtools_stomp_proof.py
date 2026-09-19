"""Host proof and copied-data controls; synthetic fixtures are not ROM proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_stomp_contract import validate_stomp
from tools.overworld.devtools_stomp_proof import (KIND,RULES,FAULTS,StompNegative,contract,
    measurements,validate_negative_result,replay_records)
from tools.overworld.test_devtools_stomp_contract import fixture


class StompProofTests(unittest.TestCase):
    def test_full_typed_stream_and_all_copied_fault_causes(self):
        from tools.overworld.test_devtools_stomp_measurement import raw_records
        test,rows=raw_records()
        baseline=replay_records(test,rows)
        self.assertTrue(baseline['passed'],baseline['failures'])
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        self.assertEqual(len(measurements(baseline,record)),6)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                failed=replay_records(test,rows,fault=fault)
                validate_negative_result(failed,fault)

    def test_exact_rows_recomputed_and_cleanup_required(self):
        cases,subject,terminal=fixture()
        value=dict(passed=True,ready=True,closed=True,acceptedProof=False,failures=[],cases=cases,
            subject=subject,initial=cases[0]['initial'],terminalSnapshot=terminal,
            proofEvidence=validate_stomp(cases,subject,terminal)['proofEvidence'])
        replay=dict(passed=True,failures=[],measurements={KIND:value})
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        self.assertEqual(len(measurements(replay,record)),6)
        self.assertEqual(sum(map(len,contract().values())),len(RULES))
        for fault in ('summary','case','cleanup'):
            changed,seal=deepcopy(replay),deepcopy(record)
            if fault=='summary':changed['measurements'][KIND]['proofEvidence']={}
            elif fault=='case':changed['measurements'][KIND]['cases'][0]['feedback']['calls'][-1]['feedback']['sound']=[]
            else:seal['sessionCleanup']['closed']=False
            with self.assertRaises(ValueError):measurements(changed,seal)

    def test_positive_sink_controls_reject_through_same_contract(self):
        for fault in ('stomp-missing-dust','stomp-missing-sound','stomp-negative-effect'):
            cases,subject,terminal=fixture();negative=StompNegative(fault)
            for case in cases:
                events=[dict(kind='native-observation',data=dict(call,observation='stomp-policy'))
                    for call in case['feedback']['calls']]
                changed=negative.mutate(dict(phase='observe',samples=[],events=events),{'actor':subject})
                case['feedback']['calls']=[{k:v for k,v in e['data'].items() if k!='observation'}
                    for e in changed['events']]
            self.assertTrue(negative.applied)
            with self.assertRaises(ValueError) as failure:validate_stomp(cases,subject,terminal)
            validate_negative_result(dict(passed=False,failures=[str(failure.exception)]),fault)

    def test_no_matching_record_and_unrelated_failure_are_not_controls(self):
        for fault in FAULTS:
            negative=StompNegative(fault);row=dict(phase='observe',events=[],samples=[])
            self.assertIs(negative.mutate(row,{}),row);self.assertFalse(negative.applied)
            with self.assertRaisesRegex(ValueError,'unrelated'):
                validate_negative_result(dict(passed=False,failures=['generic incomplete']),fault)


if __name__=='__main__':unittest.main()
