"""Synthetic host controls for the shared Select/current-follower witness."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mount_begin_measurement import MountBeginMeasurement, HOP, negative_controls
from tools.overworld import test_devtools_role_profile_proof as profile_tests
from tools.overworld import control


def fixture():
    profile, initial, final = profile_tests.RoleProfileProofTests().fixture()
    snapshots = []
    for frame in range(100, 112):
        s = deepcopy(final if frame >= 106 else initial)
        s.update(frame=frame, nativeCycle=frame + 100)
        a = s["actors"][0]
        a["sourceIdentity"] = deepcopy(profile[0]["data"]["ownerBefore"]["sourceIdentity"])
        a.update(motionPhase="IDLE", motionKind="NONE", reservationId=0,
                 commitSequence=0, origin=[1,1], target=[2,1], logical=[1,1])
        if frame >= 106:
            a["authorityGeneration"] += 1
            a["engineAnchorGeneration"] += 1
        if frame < 104:
            a.update(species=174, subjectIdentity=123)
            a["sourceIdentity"].update(species=174, personality=123)
        s["selector"].update(state=2 if frame in (101,102) else 0, highlight=2,
            activeFollowerPartySlot=3 if frame < 104 else 2, rawHeld=0,rawNew=0,newKeys=0,heldKeys=0)
        bit = {101:2048,103:2048,105:4,107:16}.get(frame,0)
        s["selector"].update(rawHeld=bit,rawNew=bit,newKeys=bit,heldKeys=bit)
        if frame == 107:
            a.update(motionPhase="MOVING",motionKind="HOP",motionDuration=3)
        if frame >= 108:
            a.update(commitSequence=1,logical=[2,1])
        snapshots.append(s)
    events = []
    for e in profile:
        e["frame"] = 106
        e["data"].update(entryNativeCycle=205,returnNativeCycle=205)
        events.append(e)
    handle=initial["actors"][0]["handle"]
    for seq,(frame,name,a,b) in enumerate([(106,"ACTOR_REBOUND",2,3),(106,"CONTROL_REBOUND",0,1),
            (107,"MOTION_STARTED",2,3),(108,"LOGICAL_COMMIT",1,2),
            (109,"MOTION_FINISHED",1,2),(110,"CONTROL_RETURNED",1,1)],1):
        events.append(dict(frame=frame,kind="native",data=dict(event=name,reason="OK",valueA=a,valueB=b,
            traceStream=1,sequence=seq,actorHandle=handle["value"],actor={k:v for k,v in handle.items() if k!="value"})))
    return [dict(boundarySnapshot=snapshots[0]),dict(samples=snapshots[1:],events=events,completedGameFrames=11)]


def replay(rows):
    meter=MountBeginMeasurement()
    for row in rows:meter.observe_record(row)
    return meter.finish()


class MountBeginMeasurementTests(unittest.TestCase):
    def test_real_registration_and_controller_preserve_original_seven_rows(self):
        root=Path(__file__).resolve().parents[2]
        test=json.loads((root/"tests/overworld/test-recipes/mount.begin-current-follower.json").read_text())
        registration,_=control._shared_test_registration(test,root)
        self.assertEqual(registration["recorderControlRequirement"],"shared.owner-reader-control-v1")
        rows=fixture();chunk=rows.pop()
        actions={101:"open-y-menu",102:"release-y",103:"confirm-current-follower",104:"wait-current-slot",
                 105:"press-select",106:"wait-current-mount",107:"request-one-hop"}
        for sample in chunk["samples"]:
            frame=sample["frame"]
            rows.append(dict(phase="observe",action=actions.get(frame,"wait-hop-terminal"),samples=[sample],
                             completedGameFrames=1,events=[e for e in chunk["events"] if e["frame"]==frame]))
        result=control._shared_mount_begin(test,rows,dict(sessionId="session-host",
            sessionCleanup=dict(sessionId="session-host",closed=True,errors=[])),root)
        self.assertEqual(len(result["measurements"]),7)
        self.assertEqual(len(result["mountBeginControls"]),11)
        rows[1]["action"]="release-y"
        with self.assertRaisesRegex(control.ValidationFailure,"recorded recipe action"):
            control._shared_mount_begin(test,rows,dict(sessionId="session-host"),root)

    def test_copied_controls_are_applied_and_rejected(self):
        rows=fixture();before=deepcopy(rows);result=negative_controls(rows)
        self.assertTrue(result["passed"],{k:v["failures"] for k,v in result["controls"].items()})
        self.assertEqual(rows,before)

    def test_setup_and_post_mount_getters_are_outside_select_transaction(self):
        rows=fixture();events=rows[1]["events"]
        earlier=deepcopy(events[0]);earlier["frame"]=101
        earlier["data"]["ownerBefore"]["publicSubject"]["species"]=174
        later=deepcopy(events[0]);later["frame"]=111
        later["data"]["ownerBefore"]["publicSubject"]["role"]="MOUNTED"
        events.extend([earlier,later])
        self.assertTrue(replay(rows)["passed"])
        for event in events:
            if event["frame"]==106 and event["data"].get("observation")=="role-profile-getter":
                event["data"]["observation"]="removed"
        self.assertFalse(replay(rows)["passed"])

    def test_complete_exact_witness_is_pure_and_seven_rows(self):
        rows=fixture();before=deepcopy(rows);result=replay(rows)
        self.assertEqual(result["failures"],[])
        self.assertEqual(result["state"],"passed")
        self.assertEqual(len(result["measurements"]),7)
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(rows,before)

    def test_missing_input_subject_object_and_terminal_fail_closed(self):
        for fault in ("previous","current","select","select-unsettled","object","reservation","frame","role","control",*HOP,"getter","begin"):
            rows=fixture();samples=rows[1]["samples"];events=rows[1]["events"]
            if fault=="previous":rows[0]["boundarySnapshot"]["actors"][0]["species"]=56
            if fault=="current":samples[3]["actors"][0]["subjectIdentity"]+=1
            if fault=="select":samples[4]["selector"]["rawNew"]=0
            if fault=="select-unsettled":samples[4]["actors"][0].update(motionPhase="MOVING",motionKind="HOP",reservationId=1)
            if fault=="object":samples[-1]["actors"][0]["engineIdentity"]["pointer"]+=4
            if fault=="reservation":samples[-1]["actors"][0]["reservationId"]=1
            if fault=="frame":samples[2]["frame"]+=1
            names={"role":"ACTOR_REBOUND","control":"CONTROL_REBOUND","getter":"role-profile-getter","begin":"role-profile-mount"}
            name=names.get(fault,fault)
            for e in events:
                if e["data"].get("event")==name:e["data"]["event"]="CONTROL_REMOVED"
                if e["data"].get("observation")==name:e["data"]["observation"]="control-removed"
            with self.subTest(fault=fault):
                r=replay(rows);self.assertEqual(r["state"],"failed");self.assertEqual(r["measurements"],{})


if __name__=="__main__":unittest.main()
