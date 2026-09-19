"""Synthetic host checks; no game proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from .test_devtools_mount_control_stress import StressFixture
from .test_devtools_mounted_teleport_matrix import config_receipt
from .devtools_warp_gate_measurement import WarpGateMeasurement,replay
from .devtools_warp_gate_proof import REQUIREMENT,contract,measurements,negative,FAULTS,validate_negative_result


def sample():
    f=StressFixture('legacy.cyndaquil-control-stress');f.xy=[555,392]
    f.actor.update(logical=dict(x=555,y=392));f.pose((555<<16)+32768,(392<<16)+32768,0)
    f.snapshot['selector'].update(physicalPressed=0,simulatedKeys=0)
    f.snapshot['context']['mapId']=67
    f.actor['sourceIdentity']['map_id']=67
    for key in ('object_map_id','spawn_map_id','current_map_id'):f.actor['engineIdentity'][key]=67
    f.snapshot['terrain']=dict(warps=[dict(x=555,y=391,header=68)])
    m=WarpGateMeasurement();m.arm(f.subject,f.snapshot,door=[555,391])
    original=None
    for index in range(2):
        receipt=config_receipt(f,index)
        if index==0:
            raw=bytearray.fromhex(receipt['before']['mountStateHex']);raw[20]=1
            receipt['before']['mountStateHex']=raw.hex();receipt['before']['profileHex']=raw[8:80].hex();original=raw[8:80]
        m.configure(receipt,f.snapshot)
        start=list(f.xy);target=[555,398] if index==0 else [555,392];commit=f.actor['commitSequence']
        for elapsed in range(1,9):
            done=elapsed==8;a=f.actor
            a.update(motionKind='NONE' if done else 'TELEPORT',motionKindId=0 if done else 3,
                motionPhase='IDLE' if done else 'MOVING',motionDuration=7,motionElapsed=min(elapsed,7),
                reservationId=0 if done else 1,commitSequence=commit+int(done),
                origin=dict(zip(('x','y'),start)),target=dict(zip(('x','y'),target)),logical=dict(zip(('x','y'),target if done else start)))
            f.xy=target if done else start;f.pose((f.xy[0]<<16)+32768,(f.xy[1]<<16)+32768,0 if index==0 else 1)
            meanings=[]
            if elapsed==1:meanings=[('MOTION_STARTED',3,7)]
            if done:meanings=[('LOGICAL_COMMIT',commit+1,3),('MOTION_FINISHED',commit+1,3),('CONTROL_RETURNED',1,commit+1)]
            snapshot,events=f.frame(meanings);mask=(128 if index==0 else 64) if elapsed==1 else 0
            snapshot['selector'].update(heldKeys=mask,rawHeld=mask)
            m.observe(snapshot,events);f.subject=deepcopy(m.subject)
            if m.failures:return m.finish()
    restore=config_receipt(f,1);a=bytearray.fromhex(restore['before']['mountStateHex']);b=a[:8]+original+a[80:]
    restore['after'].update(mountStateHex=b.hex(),profileHex=original.hex())
    m.restore(restore,f.snapshot)
    f.actor.update(motionKind='NONE',motionKindId=0,motionPhase='IDLE',reservationId=0,logical=dict(x=555,y=392))
    snapshot,events=f.frame([]);snapshot['selector'].update(heldKeys=64,rawHeld=64)
    snapshot['player'].update(x=555,y=391,facing=0);snapshot['fieldControl']=dict(taskPointer=1)
    m.observe(snapshot,events)
    for same_native_cycle in (False,True):
        snapshot,events=f.frame([]);snapshot['fieldAvailable']=False
        if same_native_cycle:snapshot['nativeCycle']=m.last['nativeCycle']
        m.observe(snapshot,events)
    snapshot,events=f.frame([]);snapshot['nativeCycle']=m.last['nativeCycle'];snapshot['selector'].update(heldKeys=0,rawHeld=0);snapshot['context']['mapId']=68;snapshot['fieldControl']=dict(taskPointer=1)
    m.observe(snapshot,events)
    snapshot,events=f.frame([]);snapshot['selector'].update(heldKeys=0,rawHeld=0);snapshot['context']['mapId']=68;snapshot['context']['fieldEpoch']+=1;snapshot['context']['mapGeneration']+=1
    events.insert(0,dict(frame=snapshot['frame'],kind='trace-status',data=dict(code='field-epoch-changed',traceStream=1,
        diagnosticOnly=True,previousEpoch=m.initial['context']['fieldEpoch'],fieldEpoch=snapshot['context']['fieldEpoch'],sequenceReset=False)))
    m.observe(snapshot,events);return m.finish()


class WarpGateTests(unittest.TestCase):
    def test_exact_contract(self):
        registry=json.loads(Path('tools/overworld/runtime_proof_registry.json').read_text())
        self.assertEqual(contract(),registry['measurementContracts'][REQUIREMENT])

    def test_complete_route_replays(self):
        result=sample();self.assertTrue(result['passed'],result['failures'])
        self.assertTrue(replay(result)['passed'])
        self.assertTrue(replay(json.loads(json.dumps(result)))['passed'])
        rows=measurements(result,dict(sessionId='x',sessionCleanup=dict(sessionId='x',closed=True,errors=[])))
        self.assertEqual(len(rows),5);self.assertEqual(rows[3]['value']['destinationMap'],68)

    def test_named_faults(self):
        result=sample();self.assertTrue(result['passed'],result['failures'])
        for fault in FAULTS:
            with self.subTest(fault=fault):
                try:checked=replay(negative(result,fault))
                except ValueError as error:checked=dict(passed=False,failures=[str(error)])
                validate_negative_result(checked,fault)

    def test_restore_extra_byte_and_missing_receipt_fail(self):
        result=sample()
        for row in result['journal']:
            if row['op']=='restore':
                raw=bytearray.fromhex(row['receipt']['after']['mountStateHex']);raw[0]=1
                row['receipt']['after']['mountStateHex']=raw.hex()
        self.assertIn('warp restore changed unrelated state',replay(result)['failures'])
        result=sample();result['journal']=[r for r in result['journal'] if r['op']!='restore']
        self.assertFalse(replay(result)['passed'])


if __name__=='__main__':unittest.main()
