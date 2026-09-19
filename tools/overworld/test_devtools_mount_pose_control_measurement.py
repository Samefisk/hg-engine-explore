"""Host-only checks of the restored native calibration contract."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture
from tools.overworld.devtools_mount_pose_control_measurement import MountedPoseControlMeasurement, KIND
from tools.overworld.devtools_mount_pose_control_proof import measurements, MountedPoseControlNegative, FAULTS
from tools.overworld.devtools_test_contract import validate_test
from tools.overworld.devtools_records import select_current_actor


def fixture():
    baseline,subject,reader,rows=pacing_fixture()
    baseline['prepared']=True
    subject=select_current_actor(baseline,subject)
    reader['subject']=deepcopy(subject)
    reader['poseCalibration']=None
    arm=dict(armed=True,prepared=True,acceptedProof=False,snapshot=deepcopy(baseline),mountPacing=deepcopy(reader))
    sample=deepcopy(baseline)
    sample.update(frame=baseline['frame']+1,nativeCycle=baseline['nativeCycle']+2,
                  actorFrame=baseline['actorFrame']+1,observationBoundary='main-task-queue-completion')
    pose=deepcopy(rows[0][0]['mountPacing']['latestCompletedPose'])
    pose.update(frame=sample['frame'],nativeCycle=sample['nativeCycle'],actorFrame=sample['actorFrame'],
        publicSubject=deepcopy(baseline['actors'][0]),worldContext=dict(baseline['context'],fieldPointer=0x02240040,statePointer=0x02280000),avatarPointer=0x02240000)
    pose['subject']=deepcopy(subject)
    for name in ('player','mount'):
        for axis in 'xyz':pose[name]['pos_'+axis]=baseline['player']['pos_'+axis]
    sample['mountPacing']=dict(reader,latestCompletedPose=pose)
    clean=deepcopy(pose)
    bad=deepcopy(clean);bad['mount']['pos_x']+=1
    clock={k:sample[k] for k in ('frame','nativeCycle','actorFrame')}
    control=dict(state='complete',failure=None,cleanupPending=False,acceptedProof=False,guestInstructionAdvance=0,
        clean=clean,bad=bad,restored=deepcopy(clean),poseAddress=pose['mountPointer']+0x70,
        originalHex=clean['mount']['pos_x'].to_bytes(4,'little',signed=True).hex(),
        changedHex=bad['mount']['pos_x'].to_bytes(4,'little',signed=True).hex(),
        clock=clock,restoredClock=deepcopy(clock),registers={**{'r'+str(i):0 for i in range(16)},'cpsr':0,'spsr':0})
    control['restoredRegisters']=deepcopy(control['registers'])
    calibrated=deepcopy(sample)
    calibrated['mountPacing'].update(guestMemoryWrites=2,poseCalibration=control)
    receipt=dict(prepared=True,advancedFrames=0,acceptedProof=False,snapshot=calibrated,mountedPoseControl=control)
    closed=deepcopy(calibrated);closed['mountPacing']['closed']=True
    cleanup=dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=closed,mountPacing=closed['mountPacing'])
    return baseline,subject,arm,sample,receipt,cleanup


class MountedPoseMeasurementTests(unittest.TestCase):
    def run_meter(self, mutate=None):
        baseline,subject,arm,sample,receipt,cleanup=fixture()
        if mutate:mutate(sample,receipt,cleanup)
        m=MountedPoseControlMeasurement(max_frames=10)
        m.arm(subject,baseline,arm)
        m.observe(sample,[])
        if not m.failures:
            m.calibrate(receipt,receipt['snapshot'])
            m.close(cleanup,receipt['snapshot'])
        return m

    def test_idle_control_complete_and_controller_checks_cleanup(self):
        m=self.run_meter();result=m.finish()
        self.assertTrue(result['passed'],result)
        replay=dict(passed=True,failures=[],measurements={KIND:result})
        record=dict(sessionId='private',sessionCleanup=dict(sessionId='private',closed=True,errors=[]))
        self.assertEqual(len(measurements(replay,record)),3)
        record['sessionCleanup']['closed']=False
        with self.assertRaises(ValueError):measurements(replay,record)

    def test_control_mutations_fail_for_named_reason(self):
        for fault in ('mounted-pose-missing-control','mounted-pose-wrong-byte','mounted-pose-unrestored','mounted-pose-clock'):
            baseline,subject,arm,sample,receipt,cleanup=fixture()
            row=dict(phase='observe',command='mount-pacing.calibrate',receipt=receipt)
            negative=MountedPoseControlNegative(fault)
            changed=negative.mutate(row,{'mount':subject})
            self.assertTrue(negative.applied)
            m=MountedPoseControlMeasurement(max_frames=10);m.arm(subject,baseline,arm);m.observe(sample,[])
            with self.subTest(fault=fault),self.assertRaises(ValueError):m.calibrate(changed['receipt'],receipt['snapshot'])

    def test_missing_sample_identity_and_motion_fail(self):
        for fault in ('mounted-pose-absent-subject','mounted-pose-stale-subject','mounted-pose-missing-completed-sample'):
            baseline,subject,arm,sample,receipt,cleanup=fixture()
            negative=MountedPoseControlNegative(fault)
            changed=negative.mutate(dict(phase='observe',samples=[sample]),{'mount':subject})
            m=MountedPoseControlMeasurement(max_frames=10);m.arm(subject,baseline,arm)
            self.assertTrue(m.observe(changed['samples'][0],[])['failures'])
        def motion(sample,*_):sample['actors'][0]['motionPhase']='MOVING'
        self.assertTrue(self.run_meter(motion).failures)

    def test_no_coherent_sample_or_changed_close_cannot_pass(self):
        baseline,subject,arm,sample,receipt,cleanup=fixture()
        m=MountedPoseControlMeasurement(max_frames=10);m.arm(subject,baseline,arm)
        with self.assertRaises(ValueError):m.calibrate(receipt,receipt['snapshot'])
        m.observe(sample,[]);m.calibrate(receipt,receipt['snapshot'])
        cleanup['mountPacing']['failure']='pending return'
        with self.assertRaises(ValueError):m.close(cleanup,receipt['snapshot'])

    def test_checked_recipe_is_exact_control_not_movement(self):
        root=Path(__file__).resolve().parents[2]
        recipe=json.loads((root/'tests/overworld/test-recipes/observation.mount-pose-control.json').read_text())
        validate_test(recipe)
        for mutate in (lambda r:r.update(mode='prepared'),
                       lambda r:r['subjects'][0].update(species=95),
                       lambda r:r['actions'].pop(1),
                       lambda r:r['actions'][1]['args']['predicate'].update(value=0)):
            wrong=deepcopy(recipe);mutate(wrong)
            with self.assertRaises(ValueError):validate_test(wrong)


if __name__=='__main__':unittest.main()
