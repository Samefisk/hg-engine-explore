"""Pure synthetic controls plus a retained-data reader smoke check; no ROM proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mount_control_stress import (
    KIND, MountControlStressMeasurement, CONTRACTS, check_snapshot_pair,
)
from tools.overworld.devtools_test_contract import TestEvaluator
from tools.overworld.test_devtools_acceleration_measurement import fixture
from tools.overworld.control import _verify_shared_subject_observation


class StressFixture:
    def __init__(self, requirement):
        self.requirement, self.rules = requirement, CONTRACTS[requirement]
        self.snapshot, _, _ = fixture(role="MOUNTED", species=self.rules["species"],durations=(3,),counters=(0,),speeds=(3,))
        s = self.snapshot
        s.update(fieldAvailable=True,fieldControl={"taskPointer":0},selector={"rawNew":0,"newKeys":0,"rawHeld":0})
        a = s["actors"][0]
        a["handle"].update(slot=7,value=(a["handle"]["generation"]<<16)|7)
        a["sourceIdentity"]["object_id"] = 231
        a["engineIdentity"].update(object_id=231,spawn_object_id=231)
        self.subject = {k:deepcopy(a[k]) for k in ("handle","species","role","subjectIdentity")}
        self.sequence = 0
        self.xy = [0,0]
        self.pose()

    @property
    def actor(self): return self.snapshot["actors"][0]

    def pose(self, x=None, z=None, facing=3):
        p = self.snapshot["player"]
        p.update(x=self.xy[0],y=self.xy[1],x_prev=self.xy[0],y_prev=self.xy[1],
                 pos_x=(self.xy[0]<<16)+32768 if x is None else x,
                 pos_z=(self.xy[1]<<16)+32768 if z is None else z,
                 flags=1,movement_cmd=facing,movement_step=0,facing=facing)
        for prefix in ("face_","unk88_","unk94_"):
            for axis in "xyz": p[prefix+axis]=0
        self.actor["engineObject"] = deepcopy(p)
        if self.actor["role"] == "MOUNTED":
            p["face_y"]=32768
            p["face_x"],p["face_z"]={0:(0,32768),1:(0,-32768),2:(32768,0),3:(-32768,0)}[facing]

    def frame(self, meanings=(), select=False):
        s = self.snapshot
        s["frame"] += 1; s["nativeCycle"] += 2; s["actorFrame"] += 1
        s["selector"].update(rawNew=4 if select else 0,newKeys=4 if select else 0,rawHeld=4 if select else 16)
        events=[]
        for name,a,b in meanings:
            self.sequence += 1
            events.append(dict(frame=s["frame"],kind="native",data=dict(event=name,reason="OK",valueA=a,valueB=b,
                actorHandle=self.actor["handle"]["value"],actor={k:v for k,v in self.actor["handle"].items() if k!="value"},
                sequence=self.sequence,traceStream=1,actorFrame=s["actorFrame"])))
        return deepcopy(s),events

    def move(self, direction=1, kind=None):
        a = self.actor
        motion = kind or self.rules["motion"]
        motion_kind = {"WALK": 1, "HOP": 2, "SKID": 4}[motion]
        duration=3 if motion in ("WALK", "SKID") else 26
        origin=list(self.xy);target=[origin[0]+direction,origin[1]]
        before=a["commitSequence"]
        a.update(origin=dict(zip(("x","y"),origin)),target=dict(zip(("x","y"),target)),
                 motionKind=motion,motionKindId=motion_kind,motionDuration=duration,reservationId=before+1)
        for elapsed in range(1,duration+1):
            a.update(motionElapsed=elapsed,motionPhase="MOVING",logical=dict(zip(("x","y"),target if elapsed==duration else origin)))
            if elapsed==duration: a["commitSequence"]=before+1
            self.pose((origin[0]<<16)+32768+direction*(65536*elapsed//duration),facing=3 if direction>0 else 2)
            events=[]
            if elapsed==1: events.append(("MOTION_STARTED",motion_kind,duration))
            if elapsed==duration: events.append(("LOGICAL_COMMIT",before+1,motion_kind))
            yield self.frame(events)
        self.xy=target
        a.update(motionPhase="IDLE",motionKind="NONE",motionKindId=0,reservationId=0)
        self.pose(facing=3 if direction>0 else 2)
        yield self.frame((("MOTION_FINISHED",before+1,motion_kind),("CONTROL_RETURNED",1,before+1)))

    def detach_recovery(self):
        a=self.actor
        a.update(role="FOLLOWER",inputOwnership=0,authorityGeneration=a["authorityGeneration"]+1,
                 engineAnchorGeneration=a["engineAnchorGeneration"]+1)
        self.pose()
        yield self.frame((("ACTOR_REBOUND",3,2),),select=True)
        self.pose(x=(self.xy[0]<<16)+32768+32768)
        yield self.frame()
        self.xy[0]+=1
        self.pose()
        yield self.frame()
        a.update(role="MOUNTED",inputOwnership=1,authorityGeneration=a["authorityGeneration"]+1,
                 engineAnchorGeneration=a["engineAnchorGeneration"]+1)
        self.pose()
        yield self.frame((("ACTOR_REBOUND",2,3),("CONTROL_REBOUND",0,1)),select=True)
        yield from self.move()


def complete(requirement):
    f=StressFixture(requirement)
    meter=MountControlStressMeasurement(requirement)
    meter.arm(f.subject,f.snapshot)
    for i in range(f.rules["motions"]):
        for s,e in f.move(1 if i%2==0 else -1): meter.observe(s,e)
        if meter.failures: raise AssertionError(meter.failures)
    # The real typed recipe uses normal Select input, not a custom phase op.
    for s,e in f.detach_recovery(): meter.observe(s,e)
    return meter,f


class MountControlStressTests(unittest.TestCase):
    def test_unarmed_setup_is_ignored_and_aliases_are_exact(self):
        for alias,requirement in (("walk","legacy.cyndaquil-control-stress"),("hop","legacy.mankey-control-stress")):
            m=MountControlStressMeasurement(alias)
            self.assertEqual(m.contract,requirement)
            self.assertEqual(m.observe({},[])["failures"],[])
            self.assertEqual(m.frames,0)
    def test_both_full_contracts_and_bounded_storage(self):
        for requirement in CONTRACTS:
            with self.subTest(requirement=requirement):
                meter,_=complete(requirement)
                result=meter.finish()
                self.assertTrue(result["passed"],result["failures"])
                self.assertEqual(len(result["motionSummaries"]),meter.rules["motions"]+1)
                self.assertEqual(meter.recorder.completed,[])
                self.assertEqual(meter.traces,[])
                self.assertFalse(result["acceptedProof"])

    def test_both_typed_evaluators_arm_at_bind_and_own_the_role_transfer(self):
        root = Path(__file__).resolve().parents[2]
        cases = (("mount.detach-restores-control", "cyndaquil", "legacy.cyndaquil-control-stress"),
                 ("hop.mounted-single-motion", "mankey", "legacy.mankey-control-stress"))
        for name, subject, requirement in cases:
            with self.subTest(name=name):
                test = json.loads((root / "tests/overworld/test-recipes" / (name + ".json")).read_text())
                evaluator = TestEvaluator(test)
                evaluator.install_measurements({KIND: {"contractVersion": 1}})
                fixture = StressFixture(requirement)
                initial = deepcopy(fixture.snapshot)
                self.assertEqual(evaluator.observe_record({"phase": "setup", "initialSnapshot": initial,
                    "initialEvents": [], "initialEventStartFrame": initial["frame"]})["state"], "running")
                bind = test["setup"][-1]
                receipt = evaluator.bind(subject, initial)
                evaluator.observe_record({"phase": "setup", "action": bind["id"], "command": "bind",
                    "receipt": receipt, "snapshot": initial})
                meter = evaluator.measurements[KIND]
                meter.rules.update(motions=1, turns=0, frames=4)
                evaluator.test["budgets"]["minObservedFrames"] = 1
                rows = [*fixture.move(), *fixture.detach_recovery()]
                action = evaluator.test["actions"][0]
                action["args"]["frames"] = action["budget"]["maxFrames"] = len(rows)
                intervals = []
                completed = initial["frame"]
                for snapshot, _ in rows:
                    intervals.extend(({"cpuNs": 1, "wallNs": 1, "completedGameFrame": completed},
                                      {"cpuNs": 1, "wallNs": 1,
                                       "completedGameFrame": snapshot["frame"]}))
                    completed = snapshot["frame"]
                evaluator.observe_record({"phase": "observe", "action": action["id"],
                    "requestedGameFrames": len(rows), "completedGameFrames": len(rows),
                    "observedFieldFrames": len(rows), "nativeCycles": len(intervals),
                    "cycleIntervals": intervals, "samples": [snapshot for snapshot, _ in rows],
                    "events": [event for _, events in rows for event in events]})
                self.assertTrue(evaluator.check({"kind": "actor-field", "subject": subject,
                    "path": "motionPhase", "operator": "eq", "value": "IDLE", "when": "final"}))
                result = evaluator.finish()
                self.assertTrue(result["passed"], result["failures"])
                self.assertEqual(result["measurements"][KIND]["phase"], "recovery")

    def test_shared_replay_identity_allows_only_the_declared_mount_role_rebound(self):
        fixture = StressFixture("legacy.cyndaquil-control-stress")
        fixture.actor["engineIdentity"]["manager_index"] = 0
        bound = {
            **fixture.subject,
            **{
                key: fixture.actor[key]
                for key in (
                    "authorityGeneration",
                    "engineAnchorGeneration",
                    "presentationGeneration",
                )
            },
        }
        snapshot, _ = next(fixture.detach_recovery())
        with self.assertRaisesRegex(ValueError, "different subject or role"):
            _verify_shared_subject_observation(snapshot, bound)
        _verify_shared_subject_observation(
            snapshot,
            bound,
            allow_mounted_rebound=True,
        )
        snapshot["actors"][0]["role"] = "WILD"
        with self.assertRaisesRegex(ValueError, "mounted rebound must name one current stable subject"):
            _verify_shared_subject_observation(
                snapshot,
                bound,
                allow_mounted_rebound=True,
            )

    def test_missing_each_lifecycle_is_rejected(self):
        for meaning in ("MOTION_STARTED","LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"):
            f=StressFixture("legacy.cyndaquil-control-stress");m=MountControlStressMeasurement(f.requirement);m.arm(f.subject,f.snapshot)
            for s,e in f.move():
                for event in e:
                    if event["data"]["event"]==meaning: event["data"]["event"]="UNRELATED"
                m.observe(s,e)
            self.assertTrue(m.failures,meaning)

    def test_bad_subject_pair_kind_coverage_and_clock_fail(self):
        for fault in ("species","role","pointer","pair","kind","event-gap","clock","coverage"):
            f=StressFixture("legacy.cyndaquil-control-stress");m=MountControlStressMeasurement(f.requirement);m.arm(f.subject,f.snapshot)
            s,e=next(f.move());a=s["actors"][0]
            if fault=="species": a["species"]=56
            if fault=="role": a["role"]="WILD"
            if fault=="pointer": a["engineIdentity"]["pointer"]+=4
            if fault=="pair": a["engineObject"]["pos_x"]+=1
            if fault=="kind": a["motionKindId"]=2
            if fault=="event-gap": s["nativeObservation"]["sequence"]+=1
            if fault=="clock": s["frame"]+=1
            if fault=="coverage": s["nativeObservation"]["eventsDropped"]=1
            m.observe(s,e)
            self.assertTrue(m.failures,fault)

    def test_short_run_and_unearned_detach_fail(self):
        f=StressFixture("legacy.cyndaquil-control-stress");m=MountControlStressMeasurement(f.requirement);m.arm(f.subject,f.snapshot)
        for s,e in f.move():m.observe(s,e)
        with self.assertRaisesRegex(ValueError,"floors"):m.begin_detach(f.snapshot)
        self.assertFalse(m.finish()["passed"])

    def test_walk_stress_validates_skids_without_counting_them_as_walks(self):
        f=StressFixture("legacy.cyndaquil-control-stress")
        m=MountControlStressMeasurement(f.requirement)
        m.arm(f.subject,f.snapshot)
        for direction,kind in ((1,"WALK"),(-1,"SKID"),(-1,"WALK")):
            for s,e in f.move(direction,kind):m.observe(s,e)
        self.assertEqual(m.failures,[])
        self.assertEqual((m.motions,m.turns),(2,1))
        self.assertEqual([row["kind"] for row in m.motion_summaries],["WALK","SKID","WALK"])

    def test_retained_sample_pair_and_actual_rebound_shape(self):
        path=Path(__file__).resolve().parents[2]/"build/overworld-devtools/session-ukwmk5ak/recording-561c06d964f3.json"
        if not path.exists():self.skipTest("retained diagnostic sample is absent")
        d=json.loads(path.read_text());checked=0
        for s in d["snapshots"]:
            a=next((a for a in s["actors"] if a["handle"]["slot"]==7),None)
            if a and a["role"]=="MOUNTED" and a["inputOwnership"]==1:
                check_snapshot_pair(s,a);checked+=1
        self.assertGreater(checked,20)
        rebound=[(e["data"]["valueA"],e["data"]["valueB"]) for e in d["events"]
                 if e["kind"]=="native" and e["data"]["event"]=="ACTOR_REBOUND"]
        self.assertIn((3,2),rebound);self.assertIn((2,3),rebound)
        first=d["snapshots"][0]
        actor=next(a for a in first["actors"] if a["handle"]["slot"]==7)
        subject={k:actor[k] for k in ("handle","subjectIdentity","species","role")}
        m=MountControlStressMeasurement("walk");m.arm(subject,first)
        for snapshot in d["snapshots"][1:]:
            m.observe(snapshot,[e for e in d["events"] if e["frame"]==snapshot["frame"]])
            if m.failures:break
        self.assertEqual(m.motions,4)
        self.assertEqual(m.failures,["unexpected motion cancellation"])


if __name__ == "__main__":unittest.main()
