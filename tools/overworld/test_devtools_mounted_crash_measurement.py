"""Replay the retained native Crash sample and focused wrong-data controls.

The fixture is diagnostic memory data, never accepted game proof. Only the
zero-advance close receipt is synthesized; it checks the pure API lifecycle.
Missing retained evidence fails rather than manufacturing a replacement run.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mounted_crash_measurement import MountedCrashMeasurement

ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/'build/overworld-devtools/session-zfgkx946/recording-28a166107404.json'
SHA='aa878865ab8f41ee9a71fe06333401efd3454145ea7bd970c5db524f4c7e5450'


def fixture():
    raw=PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA:raise ValueError('retained Crash fixture hash differs')
    value=json.loads(raw)
    if value['truncated']:raise ValueError('retained Crash fixture truncated')
    events={s['frame']:[] for s in value['snapshots']}
    for e in value['events']:
        e=deepcopy(e);d=e['data']
        if d.get('detailsOmitted'):
            artifact=d['artifact'];p=Path(artifact['path'])
            # Resolve only this fixture's own adjacent file, independent of checkout location.
            p=PATH.parent/p.name;raw=p.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=artifact['sha256']:raise ValueError('Crash event hash differs')
            e['data']=json.loads(raw)
        events[e['frame']].append(e)
    return deepcopy(value['snapshots']),events


def replay(snapshots, events, close=True):
    meter=MountedCrashMeasurement(120)
    first=snapshots[0];r=first['crashFeedback']
    meter.arm(r['subject'],first,r)
    frame=first['frame']
    for n,keys in ((16,['UP']),(32,[]),(8,['RIGHT']),(8,[])):
        meter.command(dict(op='step',startFrame=frame,args=dict(frames=n,keys=keys)),
            dict(requestedGameFrames=n,completedGameFrames=n,observedFieldFrames=n))
        frame+=n
    for s in snapshots[1:]:
        meter.observe(s,events[s['frame']])
        if meter.failures:break
    if close and meter.ready:
        last=snapshots[-1]
        closed=deepcopy(last);closed['crashFeedback']=dict(last['crashFeedback'],closed=True)
        meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,
            snapshot=deepcopy(closed),crashFeedback=deepcopy(closed['crashFeedback'])),closed)
    return meter


class MountedCrashMeasurementTests(unittest.TestCase):
    def setUp(self):self.snapshots,self.events=fixture()

    def test_retained_32_tick_crash_and_completed_restoration_then_recovery(self):
        meter=replay(self.snapshots,self.events)
        self.assertEqual(meter.failures,[])
        result=meter.finish()
        self.assertTrue(result['passed'],result)
        self.assertFalse(result['acceptedProof'])
        self.assertEqual(result['restoredFrame'],823)
        self.assertEqual(result['counts'],dict(start=1,update=33,presentation=32,finish=1,crashSound=1,sound=1,soundStart=1))
        self.assertEqual(result['proofEvidence']['frame-pacing'][0]['actual'],list(range(1,33)))
        self.assertEqual(set(result['proofEvidence']),{'natural-input','live-actor-identity','engine-boundary',
            'frame-pacing','feedback-effect','control-release'})

    def assert_rejected(self):
        try:
            meter=replay(self.snapshots,self.events)
            result=meter.finish()
        except (ValueError,KeyError,StopIteration):return
        self.assertFalse(result['passed'])
        self.assertTrue(result['failures'])
        self.assertEqual(result['proofEvidence'],{})

    def call(self,kind):
        return next(e['data'] for rows in self.events.values() for e in rows
            if e['data'].get('observation')=='mounted-crash-'+kind)

    def test_missing_actor_or_changed_generation_fails(self):
        self.snapshots[12]['actors']=[a for a in self.snapshots[12]['actors'] if a['role']!='MOUNTED']
        self.assert_rejected()
        self.setUp()
        next(a for a in self.snapshots[12]['actors'] if a['role']=='MOUNTED')['authorityGeneration']+=1
        self.assert_rejected()

    def test_missing_event_and_missing_native_coverage_fail(self):
        frame=next(f for f,es in self.events.items() if any(e['data'].get('observation')=='mounted-crash-presentation' for e in es))
        self.events[frame]=[e for e in self.events[frame] if e['data'].get('observation')!='mounted-crash-presentation']
        self.assert_rejected()
        self.setUp();self.snapshots[20]['nativeObservation']['coverageComplete']=False;self.assert_rejected()

    def test_shifted_elapsed_displacement_and_wrong_sound_fail(self):
        self.call('presentation')['after']['elapsed']+=1;self.assert_rejected()
        self.setUp();self.call('presentation')['after']['pose']['mount']['face_z']+=1;self.assert_rejected()
        self.setUp();self.call('sound')['args'][0]=2183;self.assert_rejected()
        self.setUp();self.call('soundStart')['returnValue']=0;self.assert_rejected()

    def test_base_motion_and_early_reset_fail(self):
        self.call('presentation')['after']['pose']['player']['pos_x']+=65536;self.assert_rejected()
        self.setUp();self.call('finish')['before']['elapsed']=31;self.assert_rejected()
        self.setUp();self.snapshots[20]['crashFeedback']['latestCompleted']['mode']=0;self.assert_rejected()

    def test_finish_return_does_not_substitute_for_completed_restoration(self):
        self.snapshots= [s for s in self.snapshots if s['frame']<=822]
        self.assert_rejected()
        self.setUp()
        s=next(s for s in self.snapshots if s['frame']==823)
        s['crashFeedback']['latestCompleted']['pose']['mount']['face_x']=-8192
        self.assert_rejected()

    def test_no_recovery_wrong_input_or_close_missing_fail(self):
        self.snapshots=[s for s in self.snapshots if s['frame']<=831];self.assert_rejected()
        self.setUp();self.snapshots[10]['selector']['heldKeys']=0;self.assert_rejected()
        self.setUp();meter=replay(self.snapshots,self.events,close=False)
        self.assertFalse(meter.finish()['passed'])

    def test_completed_frame_gap_fails(self):
        del self.snapshots[20];self.assert_rejected()

    def test_extra_crash_commit_and_changed_close_boundary_fail(self):
        next(a for a in self.snapshots[20]['actors'] if a['role']=='MOUNTED')['commitSequence']+=1
        self.assert_rejected()
        self.setUp();meter=replay(self.snapshots,self.events,close=False)
        last=self.snapshots[-1];wrong=deepcopy(last);wrong['frame']+=1
        with self.assertRaisesRegex(ValueError,'boundary'):
            meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=wrong,
                crashFeedback=dict(last['crashFeedback'],closed=True)),last)
