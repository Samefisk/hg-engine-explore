"""Synthetic packets through the real shared Ledyba reader; no game claim."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_chain_retry_measurement import ChainRetryMeasurement, ChainRetryNegative, RETRY_FAULTS
from tools.overworld.test_devtools_chain_measurement import Stream, SCHEMA, SOURCE
from tools.overworld.devtools_records import select_current_actor


def fixture(*, native_timing=False):
    s = Stream(); s.motion("HOP", (16, 0), pause=2, spawn=True); s.motion("WALK", (1, 0), lane_index=1)
    arm_index = len(s.items) - 1
    bound = select_current_actor(s.items[-1][0], {k: deepcopy(s.actor[k]) for k in ("handle", "species", "role", "subjectIdentity")})
    control = dict(armed=True, injected=False, closed=False, failure=None, acceptedProof=False,
        guestMemoryWrites=0, pendingWrites=0, injection=None, cooldownBoundaries=[], subject=deepcopy(bound))
    armed_snapshot = deepcopy(s.items[-1][0]); armed_snapshot.update(prepared=True, chainRetryControl=deepcopy(control))
    arm = dict(armed=True, prepared=True, frame=s.frame, snapshot=armed_snapshot, chainRetryControl=deepcopy(control))
    for i in range(7): s.motion("WALK", (1, 0), roll=20 if i == 6 else None, selected=i == 6, lane_index=1)
    policy = dict(chainPauseAction=0x85, chainPauseTicks=8, chainStepsRemaining=0)
    public = s.public()
    current = dict(publicSubject=deepcopy(public), sourceIdentity=deepcopy(s.actor["sourceIdentity"]),
        engineIdentity=deepcopy(s.actor["engineIdentity"]), policy=deepcopy(policy))
    regs = {"r" + str(i): i for i in range(15)}; regs["r14"] = 0x02300101
    injection = dict(attemptId=1, landingIndex=0, subject=bound, current=current,
        entryClock={"actorFrame":s.frame,"nativeCycle":s.frame*2},
        entryAddress=0x02300200, returnAddress=regs["r14"], returnReason=8,
        requestedArguments=[regs["r" + str(i)] for i in range(4)], stackArguments=[0]*7,
        registersBefore=regs, registersAfter={**regs,"r0":8}, guestMemoryWrites=0,
        policyBefore=deepcopy(policy))
    def attempt(index, outcome, reason, returned):
        return s.native("chain-reposition-attempt", slot=0, observationVersion=2, attemptId=index,
            nativeOrigin=list(s.actor["logical"].values()),
            publicSubject=deepcopy(public), publicSubjectAfter=deepcopy(public), encodedRemaining=0x20,
            resultHex=bytes([0x20,0,outcome,reason]).hex(), returnValue=returned,
            nativeResult=dict(encodedRemaining=0x20,gridDelta=0,outcome=outcome,
                outcomeName=["RETRY","STARTED"][outcome],reason=reason,reasonName={0:"ACCEPTED",8:"PROFILE"}[reason]),
            preparedStarts=[dict(returnValue=8,accepted=False,hopPlans=[],motionRequests=[])] if not returned else [])
    def parent(control_id):
        return s.native("chain-retry-parent", publicSubject=deepcopy(public), publicSubjectAfter=deepcopy(public),
            **({"frame":s.frame,"nativeCycle":s.frame*2} if native_timing else {}),
            attemptIds=[1 if control_id else 2],
            entryClock={"actorFrame":s.frame,"nativeCycle":s.frame*2},
            returnClock={"actorFrame":s.frame,"nativeCycle":s.frame*2},
            controlAttemptId=control_id, policyBefore=deepcopy(policy), policyAfter=deepcopy(policy),
            movementCooldownBefore=0, movementCooldownAfter=1 if control_id else 0)
    reject_index = len(s.items)
    s.append([attempt(1,0,8,0), parent(1)])
    rejected_frame = s.frame
    row = dict(frame=s.frame,nativeCycle=s.frame*2,publicSubject=deepcopy(public),policy=deepcopy(policy),movementCooldown=0 if native_timing else 1)
    if not native_timing: s.append([])
    retry_index = len(s.items)
    successful = attempt(2,1,0,1); retried = parent(None)
    s.motion("REPOSITION",(2,2)); s.items[retry_index][1][:0] = [successful,retried]
    for delta in ((-2,2),(-2,-2),(2,-2)): s.motion("REPOSITION",delta)
    for index in range(arm_index + 1,len(s.items)):
        snapshot, events = s.items[index]
        snapshot["prepared"] = True
        c = deepcopy(control)
        if index >= reject_index:
            c.update(injected=True,injection=deepcopy(injection),cooldownBoundaries=[deepcopy(row)])
        snapshot["chainRetryControl"] = c
        for event in events:
            if event["kind"] == "native-observation": event["data"]["setupMode"] = "prepared"
    return s.items, arm_index, arm, reject_index, retry_index


def replay(value):
    items, arm_index, arm, _, _ = value
    meter = ChainRetryMeasurement(SCHEMA, SOURCE, max_frames=len(items)+1)
    for i,(snapshot,events) in enumerate(items):
        meter.observe(snapshot,events)
        if i == arm_index: meter.observe_control(arm,arm["snapshot"])
        if meter.failures: break
    return meter, meter.finish()


class ChainRetryMeasurementTests(unittest.TestCase):
    def test_baseline_can_arm_while_natural_chaining_continues(self):
        meter = ChainRetryMeasurement(SCHEMA, SOURCE, max_frames=10)
        handle = {"slot": 0}
        meter.base = SimpleNamespace(
            failures=[],
            result=lambda: {"measurementErrors": [], "spawnPassed": True, "eligibleMoves": 1},
        )
        meter.subject = {"handle": handle}
        meter.latest = {"actors": [{"handle": handle, "motionPhase": "MOVING",
                                     "reservationId": 1, "inputOwnership": 1}]}
        self.assertTrue(meter.stage("baseline"))

    def test_inner_parent_clocks_must_match_native_tap(self):
        for clock in ("entryClock", "returnClock"):
            data=fixture(native_timing=True)
            parent=data[0][data[3]][1][-1]["data"]
            # Keep inner ordering valid; change only the redundant clock.
            parent[clock]["actorFrame"] += -1 if clock=="entryClock" else 1
            _,result=replay(data)
            self.assertFalse(result["passed"],clock)

    def test_native_parent_clock_and_consumed_cooldown(self):
        value=fixture(native_timing=True)
        meter,result=replay(value)
        self.assertTrue(result["passed"],result["failures"] or result["proofChecks"])
        self.assertEqual(meter.rejected["frame"],value[0][value[3]][0]["frame"])
        self.assertEqual(meter.rejected["nativeCompletedFrame"],meter.rejected["frame"]-1)
        self.assertEqual(meter.retried["frame"],meter.rejected["frame"]+1)

    def test_missing_idle_receipt_fails_at_retry_not_deadline(self):
        value=fixture(native_timing=True)
        items,_,_,reject,retry=value
        for snapshot,_ in items[reject:]: snapshot["chainRetryControl"]["cooldownBoundaries"]=[]
        meter,result=replay(value)
        self.assertFalse(result["passed"])
        self.assertEqual(meter.failures[0]["frame"],items[retry][0]["frame"])
        self.assertIn("full cooldown frame",meter.failures[0]["message"])

    def test_native_idle_boundary_cannot_move_or_own_control(self):
        for key,value in (("reservationId",1),("inputOwnership",1)):
            data=fixture(native_timing=True); snapshot=data[0][data[3]][0]
            snapshot["actors"][0][key]=value
            _,result=replay(data)
            self.assertFalse(result["passed"])
        data=fixture(native_timing=True)
        data[0][data[3]][0]["actors"][0]["engineObject"]["pos_x"]+=256
        _,result=replay(data)
        self.assertFalse(result["passed"])

    def test_controller_mutations_run_through_the_same_reader(self):
        for fault in RETRY_FAULTS:
            with self.subTest(fault=fault):
                items,arm_index,arm,_,_=fixture()
                meter=ChainRetryMeasurement(SCHEMA,SOURCE,max_frames=len(items)+1)
                negative=ChainRetryNegative(fault)
                for index,(snapshot,events) in enumerate(items):
                    row=negative.mutate({"samples":[snapshot],"events":events},
                        {"ledyba":meter.subject} if meter.subject else {})
                    meter.observe(row["samples"][0],row["events"])
                    if index==arm_index: meter.observe_control(arm,arm["snapshot"])
                    if meter.failures: break
                self.assertTrue(negative.applied)
                self.assertFalse(meter.finish()["passed"])

    def test_natural_eight_moves_one_denial_then_profile_action(self):
        meter,result = replay(fixture())
        self.assertTrue(result["passed"], result["failures"] or result["measurementErrors"] or result["proofChecks"])
        self.assertEqual(result["intervals"][0]["count"],8)
        self.assertEqual(len(result["actions"]),1)
        self.assertTrue(all(result["proofChecks"].values()))
        self.assertFalse(result["acceptedProof"])

    def test_wrong_or_missing_retry_evidence_fails(self):
        for fault in ("identity","ticks","commit","cooldown","duplicate","request","register","generation","missing-parent","missing-terminal","incomplete"):
            value=fixture(); items,_,_,reject,retry=value
            with self.subTest(fault=fault):
                if fault=="identity": items[reject][1][-1]["data"]["publicSubjectAfter"]["subjectIdentity"]+=1
                elif fault=="ticks": items[reject][1][-1]["data"]["policyAfter"]["chainPauseTicks"]+=1
                elif fault=="commit": items[reject][1][-1]["data"]["publicSubjectAfter"]["commitSequence"]+=1
                elif fault=="duplicate": items[retry][1][1]["data"]["controlAttemptId"]=1
                elif fault=="request": items[reject][1][0]["data"]["preparedStarts"][0]["motionRequests"]=[{}]
                elif fault=="missing-parent": items[reject][1][-1]["data"]["observation"]="unused"
                elif fault=="missing-terminal":
                    for event in items[-1][1]:
                        if event["kind"]=="native" and event["data"]["event"]=="CONTROL_RETURNED": event["data"]["event"]="WORLD_EFFECT"
                elif fault=="incomplete": items.pop()
                else:
                    for snapshot,_ in items[reject:]:
                        c=snapshot["chainRetryControl"]
                        if fault=="cooldown": c["cooldownBoundaries"]=[]
                        elif fault=="generation": c["injection"]["subject"].pop("authorityGeneration")
                        else: c["injection"]["registersAfter"]["r13"]+=4
                _,result=replay(value)
                self.assertFalse(result["passed"])


if __name__ == "__main__": unittest.main()
