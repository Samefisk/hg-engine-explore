"""Pure complete matrix and negative evidence, never game proof."""
from copy import deepcopy
import unittest

from .devtools_mounted_teleport_matrix import MountedTeleportMatrixMeasurement, configuration, DIRECTIONS, expected_visibility
from .test_devtools_mount_control_stress import StressFixture


def config_receipt(f,index):
    expected=configuration(index);old=bytearray(184);old[8:80]=bytes(72)
    if index:
        prior=configuration(index-1)
        for off,key in ((12,'locomotion'),(23,'teleportTime'),(24,'teleportPause')):old[8+off]=prior[key]
    new=bytearray(old)
    for off,key in ((12,'locomotion'),(23,'teleportTime'),(24,'teleportPause')):new[8+off]=expected[key]
    def point(raw):return dict(profileHex=raw[8:80].hex(),mountStateHex=raw.hex(),bindingHex=raw[80:96].hex(),
                               sessionGeneration=1,clock=dict(frame=f.snapshot['frame']),readiness=dict(actor=deepcopy(f.actor),subject=deepcopy(f.subject)))
    return dict(completed=True,guestAdvanced=False,subject=deepcopy(f.subject),changedOffsets=[12,23,24],
                before=point(old),after=point(new),**expected)


def run_matrix(fault=None, varying_distances=True, terminal_snapshot_lag=False):
    f=StressFixture('legacy.cyndaquil-control-stress');m=MountedTeleportMatrixMeasurement();m.arm(f.subject,f.snapshot)
    def apply(row):return fault.mutate(row,{'cyndaquil':f.subject}) if fault else row
    try:
        for i in range(10):
            c=apply(dict(op='configure',receipt=config_receipt(f,i),snapshot=deepcopy(f.snapshot)))
            m.configure(c['receipt'],c['snapshot'])
            mask,axis=DIRECTIONS[i];distance=1+i%2 if varying_distances else 1;start=list(f.xy);target=[a+b*distance for a,b in zip(start,axis)]
            duration=(3*distance if i>=5 else 7);commit=f.actor['commitSequence']
            for elapsed in range(1,duration+2):
                done=elapsed>duration;a=f.actor
                phase='IDLE' if done else ('COMMIT_PENDING' if elapsed==duration else 'MOVING')
                stale_terminal=terminal_snapshot_lag and done
                a.update(motionKind='TELEPORT' if stale_terminal else ('NONE' if done else 'TELEPORT'),
                    motionKindId=3 if stale_terminal else (0 if done else 3),
                    motionPhase='COMMIT_PENDING' if stale_terminal else phase,
                    motionDuration=duration,motionElapsed=min(elapsed,duration),
                    reservationId=commit+1 if stale_terminal else (0 if done else commit+1),
                    commitSequence=commit+int(done and not stale_terminal),
                    origin=dict(zip(('x','y'),start)),target=dict(zip(('x','y'),target)),
                    logical=dict(zip(('x','y'),target if done else start)))
                f.xy=target if done else start
                f.pose(((target if done else start)[0]<<16)+32768,
                       ((target if done else start)[1]<<16)+32768,
                       (3,2,0,1,3)[i%5])
                hidden=not (True if done else expected_visibility(i,duration)[elapsed-1])
                if hidden:a['engineObject']['flags']|=512;f.snapshot['player']['flags']|=512
                detached=hidden or (terminal_snapshot_lag and done)
                a['presentationAttached']=a['identityVerified']=not detached
                a['identityFailures']=['presentationAttached'] if detached else []
                a.setdefault('identityChecks',{})['presentationAttached']=not detached
                if a['presentationAttached'] != getattr(f,'presentation_attached',True):
                    a['presentationGeneration']+=1
                f.presentation_attached=a['presentationAttached']
                meanings=[]
                if elapsed==1:meanings.append(('MOTION_STARTED',3,duration))
                if done and not stale_terminal:meanings.extend((('LOGICAL_COMMIT',commit+1,3),
                    ('MOTION_FINISHED',commit+1,3),('CONTROL_RETURNED',1,commit+1)))
                snapshot,events=f.frame(meanings);snapshot['selector'].update(rawHeld=mask if elapsed==1 else 0,heldKeys=mask if elapsed==1 else 0)
                row=apply(dict(op='observe',snapshot=snapshot,events=events));m.observe(row['snapshot'],row['events'])
                f.subject['presentationGeneration']=a['presentationGeneration']
                if m.failures:return m.finish()
            if terminal_snapshot_lag:
                a.update(motionKind='NONE',motionKindId=0,motionPhase='IDLE',reservationId=0,
                         commitSequence=commit+1)
                snapshot,events=f.frame((('LOGICAL_COMMIT',commit+1,3),
                    ('MOTION_FINISHED',commit+1,3),('CONTROL_RETURNED',1,commit+1)))
                snapshot['selector'].update(rawHeld=0,heldKeys=0,newKeys=0,rawNew=0)
                m.observe(snapshot,events)
                if m.failures:return m.finish()
                a['presentationAttached']=a['identityVerified']=True
                a['identityFailures']=[]
                a.setdefault('identityChecks',{})['presentationAttached']=True
                a['presentationGeneration']+=1
                f.presentation_attached=True
                snapshot,events=f.frame([])
                snapshot['selector'].update(rawHeld=0,heldKeys=0,newKeys=0,rawNew=0)
                m.observe(snapshot,events)
                f.subject['presentationGeneration']=a['presentationGeneration']
            assert m.stage('case-complete'), m.result()
        return m.finish()
    except ValueError as error:
        m.failures.append(str(error));return m.finish()


class MatrixTests(unittest.TestCase):
    def test_complete_ten_case_matrix(self):
        result=run_matrix();self.assertTrue(result['passed'],result['failures'])
        self.assertEqual(len(result['cases']),10)
        self.assertEqual(result['cases'][0]['samples'][0]['elapsed'],1)

    def test_one_distance_cannot_pass_the_matrix(self):
        result=run_matrix(varying_distances=False)
        self.assertFalse(result['passed'])
        self.assertIn('fixed Teleport cases need two distances',result['failures'])

    def test_one_terminal_snapshot_lag_is_bounded_by_raw_visible_target(self):
        result=run_matrix(terminal_snapshot_lag=True)
        self.assertTrue(result['passed'],result['failures'])

    def test_configuration_cannot_hide_extra_byte_change(self):
        f=StressFixture('legacy.cyndaquil-control-stress');m=MountedTeleportMatrixMeasurement();m.arm(f.subject,f.snapshot)
        receipt=config_receipt(f,0);raw=bytearray.fromhex(receipt['after']['mountStateHex']);raw[0]=1
        receipt['after']['mountStateHex']=raw.hex()
        with self.assertRaisesRegex(ValueError,'unrelated state'):m.configure(receipt,f.snapshot)


if __name__=='__main__':unittest.main()
