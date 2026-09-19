"""Synthetic reader/evaluator controls; these grant no ROM proof."""
from copy import deepcopy
import unittest

from .devtools_mounted_hop_arc import MountedHopArcMeasurement, arc_height
from .test_devtools_mount_control_stress import StressFixture


def replay(fault=None):
    fixture = StressFixture('legacy.mankey-control-stress')
    meter = MountedHopArcMeasurement()
    meter.arm(fixture.subject, fixture.snapshot)
    native_sequence = fixture.snapshot['nativeObservation']['sequence']
    for index, (dx, dz, mask, facing) in enumerate(((0,1,128,1),(1,0,16,3),(-1,0,32,2))):
        a=fixture.actor; origin=list(fixture.xy); target=[origin[0]+dx,origin[1]+dz]
        before=a['commitSequence']; duration=4
        for elapsed in range(1,duration+2):
            done=elapsed>duration
            a.update(origin=dict(zip(('x','y'),origin)), target=dict(zip(('x','y'),target)),
                     logical=dict(zip(('x','y'),target if elapsed>=duration else origin)),
                     motionKind='NONE' if done else 'HOP',motionKindId=0 if done else 2,
                     motionPhase='IDLE' if done else 'MOVING',motionDuration=duration,
                     motionElapsed=min(elapsed,duration),reservationId=0 if done else before+1,
                     commitSequence=before+int(elapsed>=duration))
            fixture.xy=target if elapsed>=duration else origin
            fixture.pose((origin[0]<<16)+32768+dx*65536*min(elapsed,duration)//duration,
                         (origin[1]<<16)+32768+dz*65536*min(elapsed,duration)//duration,facing)
            height=arc_height(min(elapsed,duration),duration)
            fixture.snapshot['player']['face_y']+=height;a['engineObject']['face_y']+=height
            meanings=[]
            if elapsed==1:meanings.append(('MOTION_STARTED',2,duration))
            if elapsed==duration:meanings.append(('LOGICAL_COMMIT',before+1,2))
            if done:meanings.extend((('MOTION_FINISHED',before+1,2),('CONTROL_RETURNED',1,before+1)))
            snapshot,events=fixture.frame(meanings)
            snapshot['selector'].update(rawHeld=mask,heldKeys=mask)
            if elapsed==1:
                native_sequence+=1
                receipt=dict(frame=snapshot['frame'],kind='native-observation',data=dict(
                    observation='mounted-hop-start',sequence=native_sequence,subject=deepcopy(fixture.subject),
                    entryNativeCycle=snapshot['nativeCycle']-1,returnNativeCycle=snapshot['nativeCycle'],
                    start=dict(elapsed=0,duration=duration,origin=dict(zip(('x','y'),origin)),target=dict(zip(('x','y'),target)),
                               motionIdentity=before+1,baseFaceY=0,faceY=0)))
                events.append(receipt)
            snapshot['nativeObservation']['sequence']=native_sequence
            if fault:fault(index,elapsed,snapshot,events)
            meter.observe(snapshot,events)
            if meter.failures:return meter.finish()
    return meter.finish()


class HopArcTests(unittest.TestCase):
    def test_three_observed_arcs_and_terminal_recoveries(self):
        result=replay();self.assertTrue(result['passed'],result['failures'])
        self.assertFalse(result['acceptedProof']);self.assertEqual(len(result['cases']),3)
        self.assertEqual(result['cases'][0]['samples'],[[0,0],[1,49152],[2,65536],[3,49152],[4,0]])

    def test_missing_native_zero_is_not_replaced_by_idle(self):
        def fault(i,e,s,events):
            events[:]=[v for v in events if v['kind']!='native-observation']
            s['nativeObservation']['sequence']=0
        result=replay(fault);self.assertFalse(result['passed'])
        self.assertIn('missing real native Hop start receipt',str(result['failures']))

    def test_wrong_start_identity_geometry_and_duration_fail(self):
        for key,value in [('duration',5),('elapsed',1),('motionIdentity',999),('origin',dict(x=9,y=9))]:
            def fault(i,e,s,events):
                for event in events:
                    if event['kind']=='native-observation':event['data']['start'][key]=value
            self.assertFalse(replay(fault)['passed'],key)

    def test_bad_arc_input_and_missing_lifecycle_fail(self):
        def arc(i,e,s,events):
            if i==0 and e==2:s['actors'][0]['engineObject']['face_y']+=1;s['player']['face_y']+=1
        def input_fault(i,e,s,events):s['selector'].update(rawHeld=0,heldKeys=0)
        def lifecycle(i,e,s,events):
            for event in events:
                if event['data'].get('event')=='CONTROL_RETURNED':event['data']['event']='WORLD_EFFECT'
        for fault in (arc,input_fault,lifecycle):self.assertFalse(replay(fault)['passed'])
