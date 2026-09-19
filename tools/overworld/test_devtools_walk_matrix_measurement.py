"""Retained native pilot replay and copied-data controls; no emulator driver."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement

REPO=Path(__file__).resolve().parents[2]
PILOT=REPO/'build/overworld-devtools/session-2pzeigtv'
SETUPS=(('a429df22c4b0','3154f217a2239ea1f22856832304d3036759af7aa42c9bfc0afe89858c1b96c7'),
        ('3b50f905b920','0b06bac9858146cf402057ead49a55d448d96fbdd0211bb7a259e7226c5b1eeb'))


def pilot(mutate=None,case_limit=2,close=False,meter=None):
    recording=PILOT/'recording-10d5d86b182e.json'
    if not recording.exists():raise unittest.SkipTest('optional actual two-case pilot data absent')
    raw=json.loads(recording.read_text());events=[];configs=[]
    for name,digest in SETUPS:
        content=(PILOT/('event-details-'+name+'.json')).read_bytes()
        assert hashlib.sha256(content).hexdigest()==digest,'pilot setup artifact changed'
        configs.append(json.loads(content)['receipt'])
    for event in raw['events']:
        data=event['data']
        if data.get('detailsOmitted'):
            artifact=data['artifact'];content=(PILOT/Path(artifact['path']).name).read_bytes()
            assert hashlib.sha256(content).hexdigest()==artifact['sha256'],'pilot native artifact changed'
            data=json.loads(content)
        events.append(dict(event,data=data))
    if mutate:mutate(raw,events,configs)
    snapshots={s['frame']:s for s in raw['snapshots']}
    arm=next(e['data']['receipt'] for e in events if e['kind']=='command' and e['data'].get('op')=='walk-matrix.arm')
    if meter is None:meter=WalkMatrixMeasurement(100,case_limit=case_limit)
    meter.configure(configs[0],snapshots[767])
    meter.arm(arm['walkMatrix']['subject'],snapshots[767],arm)
    commands=[e['data'] for e in events if e['kind']=='command' and e['data'].get('op')=='step']
    for command in commands:
        if command['startFrame']==770:meter.configure(configs[1],snapshots[770])
        meter.command(dict(op='step',args=command['args'],startFrame=command['startFrame']),command['receipt'])
        for frame in range(command['startFrame']+1,command['startFrame']+command['args']['frames']+1):
            meter.observe(snapshots[frame],[e for e in events if e['frame']==frame and e['kind'] in
                ('native','native-observation','trace-status')])
            if meter.failures:return meter
    close_receipt=next(e['data']['receipt'] for e in events if e['kind']=='command' and e['data'].get('op')=='walk-matrix.close')
    if close:meter.close(close_receipt,snapshots[773])
    return meter


class WalkMatrixMeasurementTests(unittest.TestCase):
    def test_finish_keeps_missing_return_in_later_result(self):
        meter=WalkMatrixMeasurement(100)
        meter.current={'ticks':[{}],'events':[dict(event=name) for name in
            ('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED')]}
        expected=['matrix exact lifecycle missing: CONTROL_RETURNED']
        self.assertEqual(meter.finish()['failures'],expected)
        self.assertEqual(meter.result()['failures'],expected)
        self.assertEqual(meter.finish()['failures'],expected)

    def test_actual_two_case_prefix(self):
        result=pilot().finish()
        self.assertTrue(result['ready'],result['failures'])
        self.assertFalse(result['passed'])  # Old diagnostic close has no snapshot witness.
        self.assertEqual(result['completedCases'],2)
        self.assertTrue(result['prefixOnly']);self.assertFalse(result['acceptedProof'])
        self.assertEqual([r['ticks'][0]['before']['elapsed'] for r in result['cases']],[0,0])
        self.assertEqual([r['reservation'] for r in result['cases']],[22,23])

    def test_pilot_never_satisfies_full_matrix(self):
        result=pilot(case_limit=65).finish()
        self.assertFalse(result['passed']);self.assertFalse(result['ready'])
        self.assertEqual(result['expectedCases'],65)

    def test_close_needs_actual_endpoint_witness(self):
        with self.assertRaisesRegex(ValueError,'close snapshot differs'):pilot(close=True)
        # Synthetic host shape only. This receipt is not written to game evidence.
        meter=pilot();snapshot=deepcopy(meter.last);reader=deepcopy(snapshot['walkMatrix']);reader['closed']=True
        receipt=dict(closed=True,advancedFrames=0,acceptedProof=False,walkMatrix=reader,snapshot=deepcopy(snapshot))
        bad=deepcopy(receipt);bad['snapshot']['player']['pos_x']+=1
        with self.assertRaisesRegex(ValueError,'close snapshot differs'):meter.close(bad,snapshot)
        self.assertTrue(meter.close(receipt,snapshot)['passed'])

    def test_copied_native_faults(self):
        for field in ('raw','input','sequence','identity','pose','lifecycle'):
            def mutate(raw,events,configs):
                tick=next(e for e in events if e['data'].get('observation')=='walk-matrix-tick')
                if field=='raw':tick['data']['before']['elapsed']+=1
                elif field=='input':tick['data']['input']['heldKeys']=0
                elif field=='sequence':tick['data']['sequence']+=1
                elif field=='identity':tick['data']['beforeCurrent']['subject']['species']=1
                elif field=='pose':next(s for s in raw['snapshots'] if s['frame']==770)['player']['pos_x']+=1
                else:next(e for e in events if e['kind']=='native' and e['data']['event']=='MOTION_FINISHED')['data']['event']='WORLD_EFFECT'
            with self.subTest(field=field):
                result=pilot(mutate).finish()
                self.assertFalse(result['passed']);self.assertTrue(result['failures'])

    def test_configure_rejects_extra_byte_and_non_idle_edit(self):
        for field in ('bytes','clock'):
            def mutate(raw,events,configs):
                if field=='bytes':configs[0]['after']['mountStateHex']='ff'+configs[0]['after']['mountStateHex'][2:]
                else:configs[0]['after']['clock']['nativeCycle']+=1
            with self.subTest(field=field),self.assertRaises(ValueError):pilot(mutate)


if __name__=='__main__':unittest.main()
