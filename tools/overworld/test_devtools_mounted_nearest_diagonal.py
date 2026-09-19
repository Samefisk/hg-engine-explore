"""Host-only raw probe, start and arc controls; no native game proof."""
from copy import deepcopy
from pathlib import Path
import unittest

from .devtools_mounted_nearest_diagonal import MountedNearestDiagonalMeasurement, ORIGIN, candidate_order, validate_probe
from .devtools_mounted_hop_arc import arc_height
from .devtools_mounted_hop_candidate_probe import LANDING, linked_identity
from .test_devtools_mount_control_stress import StressFixture


def fixture_probe(fixture):
    profile=bytearray(72);profile[12]=2;profile[19:22]=bytes((1,1,3))
    raw=bytearray(184);raw[8:80]=profile
    before=dict(frame=fixture.snapshot['frame'],player=deepcopy(fixture.snapshot['player']),
                actor=deepcopy(fixture.actor),mountStateHex=raw.hex(),stateHex='00',inputs={})
    rows=candidate_order(1,3)
    for row in rows:
        row['kind']=row.pop('category');row['result']=int(row['target'] in ([546,390],[547,390]))
    service=linked_identity(Path(__file__).resolve().parents[2]);landing=service[LANDING]['address']
    value=dict(completed=True,prepared=True,acceptedProof=False,batchAdvancedFrames=0,guestMemoryWrites=0,
               scope='prepared-mounted-hop-candidate-query',subject=deepcopy(fixture.subject),direction='UP',origin=ORIGIN,
               minDistance=1,maxDistance=3,profileHex=profile.hex(),before=before,after=deepcopy(before),rows=rows,
               orderedNearTargets=[[546,390]],equalDiagonalTargets=[[547,390]],
               serviceIdentity=service)
    return dict(value=value,preparedOnly=True,acceptedProof=False,snapshot=deepcopy(fixture.snapshot),
                calls=[dict(routine='mount_hop_landing',address=landing,requestedArguments=row['target'],returnValue=row['result']) for row in rows])


def replay(negative=None):
    f=StressFixture('legacy.mankey-control-stress');f.xy=list(ORIGIN);f.pose(facing=0)
    for name in ('origin','target','logical'):f.actor[name]=dict(zip(('x','y'),ORIGIN))
    probe=fixture_probe(f); meter=MountedNearestDiagonalMeasurement()
    if negative:probe=negative.mutate(dict(phase='setup',receipt=probe),{'mankey':f.subject})['receipt']
    try:meter.arm(f.subject,f.snapshot,probe)
    except ValueError as error:return dict(passed=False,failures=[str(error)])
    native_sequence=f.snapshot['nativeObservation']['sequence']
    target=[546,390];duration=4;before=f.actor['commitSequence']
    for elapsed in range(1,duration+2):
        done=elapsed>duration;a=f.actor
        a.update(origin=dict(zip(('x','y'),ORIGIN)),target=dict(zip(('x','y'),target)),
                 logical=dict(zip(('x','y'),target if elapsed>=duration else ORIGIN)),
                 motionKind='NONE' if done else 'HOP',motionKindId=0 if done else 2,
                 motionPhase='IDLE' if done else 'MOVING',motionDuration=duration,motionElapsed=min(elapsed,duration),
                 reservationId=0 if done else before+1,commitSequence=before+int(elapsed>=duration))
        f.xy=target if elapsed>=duration else ORIGIN
        f.pose((ORIGIN[0]<<16)+32768+(target[0]-ORIGIN[0])*65536*min(elapsed,duration)//duration,
               (ORIGIN[1]<<16)+32768+(target[1]-ORIGIN[1])*65536*min(elapsed,duration)//duration,0)
        height=arc_height(min(elapsed,duration),duration)
        f.snapshot['player']['face_y']+=height;a['engineObject']['face_y']+=height
        events=[]
        if elapsed==1:events.append(('MOTION_STARTED',2,duration))
        if elapsed==duration:events.append(('LOGICAL_COMMIT',before+1,2))
        if done:events.extend((('MOTION_FINISHED',before+1,2),('CONTROL_RETURNED',1,before+1)))
        snapshot,events=f.frame(events);snapshot['selector'].update(rawHeld=64,heldKeys=64)
        if elapsed==1:
            native_sequence+=1
            events.append(dict(frame=snapshot['frame'],kind='native-observation',data=dict(observation='mounted-hop-start',
                sequence=native_sequence,subject=deepcopy(f.subject),entryNativeCycle=snapshot['nativeCycle']-1,
                returnNativeCycle=snapshot['nativeCycle'],start=dict(elapsed=0,duration=duration,
                origin=dict(zip(('x','y'),ORIGIN)),target=dict(zip(('x','y'),target)),motionIdentity=before+1,baseFaceY=0,faceY=0))))
        snapshot['nativeObservation']['sequence']=native_sequence
        row=dict(phase='observe',samples=[snapshot],events=events)
        if negative:row=negative.mutate(row,{'mankey':f.subject})
        meter.observe(row['samples'][0],row['events'])
        if meter.failures:break
    return meter.finish()


class NearestTests(unittest.TestCase):
    def test_candidate_order_has_straight_then_near_then_equal_groups(self):
        rows=candidate_order(1,3)
        self.assertEqual([r['target'] for r in rows[:7]],
                         [[545,389],[545,390],[545,391],[546,389],[544,389],[546,390],[544,390]])
        self.assertEqual([r['target'] for r in rows[-6:]],
                         [[548,389],[542,389],[547,390],[543,390],[546,391],[544,391]])

    def test_complete_near_hop_excludes_open_equal_diagonal(self):
        q=replay();self.assertTrue(q['passed'],q['failures']);self.assertFalse(q['acceptedProof'])
        self.assertEqual(q['choice']['chosen'],[546,390]);self.assertEqual(len(q['cases']),1)

    def test_exact_order_and_all_native_returns_are_required(self):
        f=StressFixture('legacy.mankey-control-stress');probe=fixture_probe(f)
        for mutate in (lambda q:q['calls'].pop(),lambda q:q['value']['rows'][0].update(result=1),
                       lambda q:q['value'].update(orderedNearTargets=[]),lambda q:q['value'].update(maxDistance=4),
                       lambda q:q['value']['after'].update(profileHex='00')):
            p=deepcopy(probe);mutate(p)
            with self.assertRaises(ValueError):validate_probe(p,f.subject,f.snapshot)

    def test_one_safe_return_frame_can_close_the_zero_advance_query_batch(self):
        f=StressFixture('legacy.mankey-control-stress');probe=fixture_probe(f)
        endpoint=deepcopy(f.snapshot);endpoint['frame']+=1;probe['snapshot']=deepcopy(endpoint)
        validate_probe(probe,f.subject,endpoint)
