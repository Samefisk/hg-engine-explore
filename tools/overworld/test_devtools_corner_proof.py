"""Host controls; no synthetic fixture is accepted live proof."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from tools.overworld.test_devtools_corner_measurement import fixture, replay_fixture
from tools.overworld.devtools_corner_measurement import CornerMeasurement
from tools.overworld.devtools_corner_proof import (KIND, REQUIREMENT, FAULTS, CornerNegative,
    contract, measurements, validate_negative_result, replay_records)


def good_result():
    meter,reader,rows=replay_fixture()
    value=meter.result()
    value['cleanup']=dict(closed=True,advancedFrames=0,acceptedProof=False,
        snapshot=deepcopy(rows[-1][0]),walkCorner=value['cleanup'])
    return dict(passed=True,failures=[],measurements={KIND:value}),dict(
        sessionId='private',sessionCleanup=dict(sessionId='private',closed=True,errors=[]))


class CornerProofTests(unittest.TestCase):
    def test_exact_original_seven_rows(self):
        registry=json.loads((Path(__file__).resolve().parents[2]/'tools/overworld/runtime_proof_registry.json').read_text())
        contracts=next(v for v in registry.values() if isinstance(v,dict) and isinstance(v.get(REQUIREMENT),dict)
            and 'natural-input' in v[REQUIREMENT])
        self.assertEqual(contract(),contracts[REQUIREMENT])
        result,record=good_result()
        self.assertTrue(result['measurements'][KIND]['passed'],result)
        rows=measurements(result,record)
        self.assertEqual(len(rows),7)
        self.assertEqual([r['value'] for r in rows[:2]],[2,[1,'MOUNTED',155,1]])

    def test_no_green_summary_can_replace_missing_native_meaning(self):
        for name in ('CANDIDATE_REJECTED','MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED'):
            result,record=good_result();meter=result['measurements'][KIND]
            meter['traces']=[e for e in meter['traces'] if e['data']['event']!=name]
            with self.subTest(name=name),self.assertRaises(ValueError):measurements(result,record)
        for fault in ('collision','landing','blocked','count','close'):
            result,record=good_result();meter=result['measurements'][KIND]
            if fault=='collision':meter['strictCalls'][0]['collisions'][0]['rawMask']^=1
            elif fault=='landing':meter['query']['diagonals'][2]['result']=0
            elif fault=='blocked':meter['blocked']['commitSequence']+=1
            elif fault=='count':meter['proofEvidence']['logical-commit'][0]['actual']=2
            else:record['sessionCleanup']['closed']=False
            with self.subTest(fault=fault),self.assertRaises(ValueError):measurements(result,record)

    def test_copied_controls_feed_actual_meter(self):
        for fault in FAULTS:
            baseline,subject,query,reader,rows=fixture()
            negative=CornerNegative(fault)
            probe=negative.mutate(dict(phase='setup',command='walk-corner.probe',receipt=query),{'actor':subject})
            meter=CornerMeasurement(50)
            try:
                meter.probe(probe['receipt'],baseline);meter.arm(subject,baseline,reader)
                for index,(sample,events) in enumerate(rows):
                    row=negative.mutate(dict(phase='observe',samples=[sample],events=events),{'actor':subject})
                    meter.observe(row['samples'][0],row['events'])
                    if meter.failures:break
                    if index==1:meter.begin_recovery(row['samples'][0])
                start=baseline['frame']
                recovery=next(s['selector']['heldKeys'] for s,_ in rows[2:] if s['selector']['heldKeys'])
                name={16:'RIGHT',32:'LEFT',64:'UP',128:'DOWN'}[recovery]
                for count,keys in ((1,['DOWN','LEFT']),(1,[]),(1,[name]),(5,[])):
                    meter.command(dict(op='step',args=dict(frames=count,keys=keys),startFrame=start),
                        dict(requestedGameFrames=count,completedGameFrames=count,observedFieldFrames=count))
                    start+=count
                meter.finish()
            except (ValueError,KeyError,TypeError) as error:
                meter.failures.append(str(error))
            result=dict(passed=False,failures=[],measurements={KIND:meter.result()})
            with self.subTest(fault=fault):
                self.assertTrue(negative.applied)
                self.assertTrue(meter.failures)
                validate_negative_result(result,fault)

    def test_unrelated_failure_never_accepts_a_negative(self):
        for fault in FAULTS:
            with self.assertRaises(ValueError):validate_negative_result(dict(passed=False,failures=['boot failed']),fault)


if __name__=='__main__':unittest.main()
