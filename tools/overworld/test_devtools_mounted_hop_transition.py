"""Synthetic pure replay; these controls do not supply game acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_hop_transition_measurement import MountedHopTransitionMeasurement, validate_elapsed
from tools.overworld.devtools_mounted_hop_transition_proof import contract, measurements
from tools.overworld.test_devtools_mount_control_stress import StressFixture

TEST=dict(mode='prepared',fixture=dict(rom='test.nds',save='test.sav'),
          subjects=[dict(id='mankey',species=56,role='MOUNTED',acquire='existing')])


def set_map(f,map_id,rebind=False):
    s,a=f.snapshot,f.actor
    s['context']['mapId']=map_id
    if rebind:
        for key in ('fieldEpoch','mapGeneration'):
            s['context'][key]+=1;a['handle'][key]=s['context'][key]
    a['sourceIdentity']['map_id']=map_id
    for key in ('object_map_id','spawn_map_id','current_map_id'):a['engineIdentity'][key]=map_id


def replay(fault=None, soak=5000):
    f=StressFixture('legacy.mankey-control-stress');set_map(f,33)
    f.xy=[670,402];f.pose();f.actor['logical']=dict(x=670,y=402)
    meter=MountedHopTransitionMeasurement(TEST,max_frames=6000)
    meter.arm(f.subject,f.snapshot)
    n=5500
    meter.command(dict(op='step',startFrame=f.snapshot['frame'],args=dict(frames=n,keys=['RIGHT'])),
                  dict(requestedGameFrames=n,completedGameFrames=n,observedFieldFrames=n))
    old=deepcopy(f.actor['handle'])
    for elapsed in range(1,6):
        a=f.actor;done=elapsed==5
        a.update(origin=dict(x=670,y=402),target=dict(x=674,y=402),motionKind='NONE' if done else 'HOP',
                 motionKindId=0 if done else 2,motionPhase='IDLE' if done else 'MOVING',motionDuration=4,
                 motionElapsed=min(elapsed,4),reservationId=0 if done else 1,commitSequence=int(elapsed>=4),
                 logical=dict(x=674 if elapsed>=4 else 670,y=402))
        f.xy=[674 if elapsed>=4 else 670,402];f.pose((670<<16)+32768+65536*min(elapsed,4))
        if elapsed<4:
            a['engineObject']['face_y']+=4096;f.snapshot['player']['face_y']+=4096
        meanings=[]
        if elapsed==1:meanings=[('MOTION_STARTED',2,4)]
        if elapsed==2:
            set_map(f,60,True);meanings=[('CONTEXT_CHANGED',old['fieldEpoch'],a['handle']['fieldEpoch']),('ACTOR_REBOUND',33,60)]
        if elapsed==4:meanings=[('LOGICAL_COMMIT',1,2)]
        if done:meanings=[('MOTION_FINISHED',1,2),('CONTROL_RETURNED',1,1)]
        snapshot,events=f.frame(meanings)
        snapshot['selector'].update(heldKeys=16,simulatedKeys=0)
        if elapsed==2:
            next(e for e in events if e['data']['event']=='CONTEXT_CHANGED')['data'].update(
                reason='CONTEXT_LOST',actorHandle=old['value'],
                actor={k:v for k,v in old.items() if k!='value'})
            events.insert(0,dict(frame=snapshot['frame'],kind='trace-status',data=dict(
                code='field-epoch-changed',traceStream=1,diagnosticOnly=True,
                previousEpoch=old['fieldEpoch'],fieldEpoch=a['handle']['fieldEpoch'],
                sequenceReset=False)))
        if fault:fault(elapsed,snapshot,events)
        meter.observe(snapshot,events)
        if meter.failures:return meter
    for snapshot,events in f.move():
        snapshot['selector'].update(heldKeys=16,simulatedKeys=0)
        meter.observe(snapshot,events)
        if meter.failures:return meter
    while meter.input_frames<soak:
        snapshot,events=f.frame();snapshot['selector'].update(heldKeys=16,simulatedKeys=0)
        meter.observe(snapshot,events)
        if meter.failures:return meter
    return meter


class HopTransitionTests(unittest.TestCase):
    def test_inflight_rebind_recovery_and_full_input_floor(self):
        meter=replay()
        result=meter.finish()
        self.assertTrue(result['passed'],result['failures'])
        self.assertFalse(result['acceptedProof'])
        self.assertEqual(result['elapsed'],[2,3,4])
        self.assertEqual(result['postTransitionInputFrames'],5000)
        rows=measurements(dict(passed=True,failures=[],measurements={result['kind']:result}),
                          dict(sessionId='synthetic',sessionCleanup=dict(sessionId='synthetic',closed=True,errors=[])))
        self.assertEqual(len(rows),8)
        self.assertEqual(next(r['value'] for r in rows if r['name']=='mounted-map-change'),[33,60])

    def test_soak_cannot_be_shortened(self):
        result=replay(soak=40).finish()
        self.assertFalse(result['passed'])
        self.assertTrue(result['failures'])

    def test_copied_transition_faults_fail_closed(self):
        for name in ('elapsed','pair','rebind','identity'):
            def fault(elapsed,snapshot,events):
                if elapsed!=2:return
                if name=='elapsed':snapshot['actors'][0]['motionElapsed']=0
                elif name=='pair':snapshot['player']['pos_x']+=1
                elif name=='identity':snapshot['actors'][0]['subjectIdentity']+=1
                else:next(e for e in events if e.get('data',{}).get('event')=='ACTOR_REBOUND')['data']['event']='WORLD_EFFECT'
            with self.subTest(name=name):
                result=replay(fault,soak=40).finish()
                self.assertFalse(result['passed']);self.assertTrue(result['failures'])

    def test_exact_registry_and_partial_elapsed_contract(self):
        r=json.loads((Path(__file__).resolve().parents[2]/'tools/overworld/runtime_proof_registry.json').read_text())
        def find(v):
            if isinstance(v,dict):
                if isinstance(v.get('legacy.mounted-transition'),dict) and 'natural-input' in v['legacy.mounted-transition']:
                    return v['legacy.mounted-transition']
                for child in v.values():
                    found=find(child)
                    if found:return found
        self.assertEqual(contract(),find(r))
        validate_elapsed(2,4,[2,3,4])
        for start,duration,values in ((0,4,[0,1,2,3]),(2,4,[2,4]),(4,4,[4])):
            with self.assertRaises(ValueError):validate_elapsed(start,duration,values)


if __name__=='__main__':unittest.main()
