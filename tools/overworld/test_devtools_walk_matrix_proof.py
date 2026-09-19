"""Copied host-data controls. Generated fixtures are not ROM proof."""
from copy import deepcopy
import json
import struct
from pathlib import Path
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_contract import CASES, validate_matrix
from tools.overworld.devtools_walk_matrix_proof import (KIND, REQUIREMENT, RULES, FAULTS, MatrixNegative,
    contract, measurements, validate_negative_result)
from tools.overworld.test_devtools_acceleration_measurement import fixture as actor_fixture
from tools.overworld.test_devtools_walk_matrix_contract import fixture as motion_fixture


def synthetic_stream(fault=None, *, native_fault=None):
    """Exercise all 65 cases in the real pure meter; no guest data or ROM claim."""
    from tools.overworld.devtools_walk_matrix_measurement import WalkMatrixMeasurement, DELTAS
    from tools.overworld.devtools_walk_matrix_observer import decode_motion, decode_sample
    meter = WalkMatrixMeasurement(4096)
    snapshot, _, _ = actor_fixture(role="MOUNTED",species=155,durations=())
    actor = snapshot["actors"][0]
    actor.update(motionKind="NONE",motionPhase="IDLE",reservationId=0,logical=dict(x=588,y=406))
    actor["movementPolicy"] = dict(pending=0,skid=0,pendingSkid=0)
    for obj in (snapshot["player"],actor["engineObject"]):
        for prefix in ("face_","unk88_","unk94_"):
            for axis in "xyz":obj[prefix+axis]=0
    snapshot["player"].update(face_x=32768,face_y=32768)
    snapshot.update(frame=10,nativeCycle=100,actorFrame=20,selector=dict(heldKeys=0,rawHeld=0,simulatedKeys=0))
    subject = select_current_actor(snapshot,actor)
    pointer = 0x02300000+68+7*172+88
    reader = dict(armed=True,closed=False,failure=None,acceptedProof=False,guestMemoryWrites=0,
        subject=subject,startFrame=10,pending=0,returned=0,counts=dict(ticks=0,movingWalk=0),
        layout=dict(stateAddress=0x02300000,actorsOffset=68,actorStride=172,snapshotBytes=88,
                    motionBytes=52,policyOffset=140,policyBytes=32,capacity=10),
        motionPointer=pointer)
    snapshot["walkMatrix"] = deepcopy(reader)
    state = bytearray(184);state[20]=1
    negative = MatrixNegative(fault) if fault else None
    trace_seq = 0

    def mutate(row):
        return negative.mutate(row,{"actor":subject}) if negative else row

    def trace(name, frame):
        nonlocal trace_seq
        trace_seq += 1
        return dict(kind="native",frame=frame,data=dict(event=name,reason="OK",valueA=1,valueB=1,
            actorHandle=subject["handle"]["value"],actor={k:v for k,v in subject["handle"].items() if k!="value"},
            traceStream=1,sequence=trace_seq,actorFrame=snapshot["actorFrame"]+1))

    def advance(keys, case, elapsed=None):
        nonlocal snapshot, actor
        mask = sum(dict(LEFT=32,RIGHT=16,UP=64,DOWN=128)[k] for k in keys)
        command=dict(op="step",args=dict(frames=1,keys=list(keys)),startFrame=snapshot["frame"])
        meter.command(command,dict(completedGameFrames=1,requestedGameFrames=1,observedFieldFrames=1))
        next_snapshot=deepcopy(snapshot);next_actor=next_snapshot["actors"][0]
        frame=snapshot["frame"]+1
        next_snapshot.update(frame=frame,nativeCycle=snapshot["nativeCycle"]+10,actorFrame=snapshot["actorFrame"]+1)
        next_snapshot["selector"].update(heldKeys=mask,rawHeld=mask)
        events=[]
        if elapsed is not None:
            duration=case["duration"];reservation=case["index"]+1
            origin=meter.current["origin"];dx,dy=DELTAS[case["direction"]]
            # The target is diagonal; mounted motion retains a cardinal heading.
            heading={4:2,7:3}.get(case["direction"],case["direction"])
            if case["index"]==32 and native_fault=="wrong-heading":heading=3
            raw=bytearray(52)
            struct.pack_into("<HBBHH",raw,0,1,1,heading,subject["handle"]["fieldEpoch"],1)
            target_x=origin["x"]+dx+int(case["index"]==32 and native_fault=="wrong-target")
            struct.pack_into("<4h",raw,8,origin["x"],origin["y"],target_x,origin["y"]+dy)
            struct.pack_into("<HH",raw,24,duration,reservation);raw[28]=heading;raw[29]=1
            struct.pack_into("<H",raw,40,elapsed);raw[48]=2
            before=decode_motion(bytes(raw))
            struct.pack_into("<H",raw,40,elapsed+1);raw[48]=3 if elapsed+1==duration else 2
            after=decode_motion(bytes(raw))
            sample=bytearray(36);struct.pack_into("<HH",sample,24,elapsed+1,duration)
            sample[34]=heading
            public=deepcopy(actor);public["reservationId"]=reservation
            current=dict(subject=subject,publicSubject=public,sourceIdentity=actor["sourceIdentity"],
                engineIdentity=actor["engineIdentity"],worldContext=snapshot["context"],
                playerPointer=actor["engineIdentity"]["anchorPointer"],mountPointer=actor["engineIdentity"]["pointer"],avatarPointer=1)
            clock=dict(actorFrame=next_snapshot["actorFrame"],nativeCycle=snapshot["nativeCycle"]+1)
            data=dict(observation="walk-matrix-tick",sequence=snapshot["nativeObservation"]["sequence"]+1,
                normalReturn=True,motionPointer=pointer,completedFrame=snapshot["frame"],before=before,after=after,
                sample=decode_sample(bytes(sample)),returnFlags=0,returnValue=0,beforeCurrent=current,afterCurrent=deepcopy(current),
                entryClock=clock,returnClock=deepcopy(clock),entryActorFrame=clock["actorFrame"],returnActorFrame=clock["actorFrame"],
                entryNativeCycle=clock["nativeCycle"],returnNativeCycle=clock["nativeCycle"],movingWalk=True,qualification="moving-walk",
                input=dict(heldKeys=mask,rawHeld=mask,simulatedKeys=0))
            next_snapshot["nativeObservation"]["sequence"]=data["sequence"]
            events.append(dict(kind="native-observation",frame=frame,data=data))
            reader["returned"]+=1;reader["counts"]["ticks"]+=1;reader["counts"]["movingWalk"]+=1
            reader["lastTick"]=dict(completedFrame=snapshot["frame"],entryElapsed=elapsed,returnElapsed=elapsed+1,
                reservationId=reservation,qualification="moving-walk")
            if elapsed==0:events.append(trace("MOTION_STARTED",frame))
            if elapsed+1==duration:
                events.extend(trace(name,frame) for name in ("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"))
                next_actor.update(motionKind="NONE",motionPhase="IDLE",reservationId=0,
                    logical=dict(x=origin["x"]+dx,y=origin["y"]+dy),commitSequence=actor["commitSequence"]+1)
                for obj in (next_snapshot["player"],next_actor["engineObject"]):
                    obj.update(x=origin["x"]+dx,y=origin["y"]+dy,pos_x=((origin["x"]+dx)<<16)+32768,
                        pos_z=((origin["y"]+dy)<<16)+32768)
            else:next_actor.update(motionKind="WALK",motionPhase="MOVING",reservationId=reservation)
        next_snapshot["walkMatrix"]=deepcopy(reader)
        row=mutate(dict(phase="observe",samples=[next_snapshot],events=events))
        meter.observe(row["samples"][0],row["events"])
        snapshot,actor=next_snapshot,next_actor

    try:
        for case in CASES:
            if case["index"] and not meter.stage("case-complete"):break
            before=dict(mountStateHex=state.hex(),profileHex=state[8:80].hex(),bindingHex=state[80:96].hex(),sessionGeneration=1,
                clock=dict(frame=snapshot["frame"],nativeCycle=snapshot["nativeCycle"]),readiness=dict(actor=deepcopy(actor)))
            for offset,value in ((7,case["duration"]),(19,case["mode"]),(50,0),(51,case["duration"])):state[8+offset]=value
            after=dict(deepcopy(before),mountStateHex=state.hex(),profileHex=state[8:80].hex())
            config=dict(completed=True,prepared=True,acceptedProof=False,guestAdvanced=False,
                scope="prepared-idle-mounted-walk-fixture",directionMode=case["mode"],travelTime=case["duration"],
                changedOffsets=[7,19,50,51],before=before,after=after,expectedStateHex=state.hex(),subject=subject)
            row=mutate(dict(phase="setup",command="mount-walk.configure",receipt=config))
            meter.configure(row["receipt"],snapshot)
            if case["index"]==0:meter.arm(subject,snapshot,reader)
            if case["index"]==64:
                advance(["LEFT"],case)
                if meter.failures:break
                advance([],case)
            for elapsed in range(case["duration"]):
                advance(case["keys"] if elapsed==0 else [],case,elapsed)
                if meter.failures:break
            if meter.failures:break
        if meter.ready:
            meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=deepcopy(snapshot),
                walkMatrix=dict(reader,closed=True)),snapshot)
    except (ValueError,KeyError,TypeError) as error:
        meter.failures.append(str(error))
    return meter, negative


def good_result():
    initial, _, _ = actor_fixture(role="MOUNTED", species=155, durations=())
    actor = initial["actors"][0]
    actor.update(motionKind="NONE", motionPhase="IDLE", reservationId=0)
    subject = select_current_actor(initial, actor)
    cases = [motion_fixture(i) for i in range(65)]
    for motion in cases:
        motion["subject"] = deepcopy(subject)
        for tick in motion["ticks"]:
            for endpoint in tick.values():
                endpoint["subject"] = deepcopy(subject)
        for event in motion["events"]:
            event["subject"] = deepcopy(subject)
    gate = dict(before=[588,406], after=[588,406], mode="IDLE", pending=0)
    matrix = validate_matrix(cases, gate)
    profile = bytearray(72)
    configurations = []
    for case in CASES:
        before = profile.hex()
        for offset, value in ((7,case["duration"]),(19,case["mode"]),(50,0),(51,case["duration"])):
            profile[offset] = value
        configurations.append(dict(caseIndex=case["index"], profileHex=profile.hex(), beforeProfileHex=before,
            changedOffsets=[7,19,50,51], bindingHex="00"*16, sessionGeneration=1))
    actuals = [65,[1,"MOUNTED",155,1],matrix["counts"],matrix["elapsed"],65,["IDLE",0]]
    proof = {}
    for (claim,name,_),actual in zip(RULES,actuals):
        proof.setdefault(claim,[]).append(dict(name=name,actual=deepcopy(actual)))
    value = dict(passed=True,ready=True,closed=True,acceptedProof=False,failures=[],prefixOnly=False,
        expectedCases=65, completedCases=65,startedMotions=65,completedMotions=65,subject=subject,
        initial=initial,terminalSnapshot=deepcopy(initial),terminal=dict(phase="IDLE",pending=0),
        cases=cases,diagonalAttempt=gate,configurations=configurations,proofEvidence=proof)
    return dict(passed=True,failures=[],measurements={KIND:value}), dict(sessionId="private",
        sessionCleanup=dict(sessionId="private",closed=True,errors=[]))


class MatrixProofTests(unittest.TestCase):
    def test_saved_full_matrix_replay_and_all_controller_faults(self):
        from tools.overworld.control import _replay_shared_test, _shared_artifact, load_observations
        root=Path(__file__).resolve().parents[2]
        directory=root/'build/overworld-devtools/test-32c9c4d92ffd42408c2585939a75c740'
        if not directory.exists():self.skipTest('optional full matrix32c9 memory data absent')
        manifest=json.loads((directory/'manifest.json').read_text())
        test=json.loads((directory/'test.json').read_text())
        rows=load_observations(_shared_artifact(manifest['observationsArtifact'],directory))
        baseline=_replay_shared_test(test,rows,repo=root)
        self.assertTrue(baseline['passed'],baseline['failures'])
        self.assertEqual(baseline,manifest['evaluation'])
        self.assertEqual(len(measurements(baseline,manifest)),6)
        for fault in FAULTS:
            with self.subTest(fault=fault):
                validate_negative_result(_replay_shared_test(test,rows,repo=root,fault=fault),fault)

    def test_diagonal_heading_is_cardinal_and_wrong_heading_or_target_fails(self):
        meter,_=synthetic_stream()
        self.assertTrue(meter.finish()['passed'],meter.finish()['failures'])
        self.assertEqual(meter.lastMovingTick['before']['plan']['direction'],2)
        self.assertEqual(meter.lastMovingTick['before']['plan']['facing'],2)
        for fault in ('wrong-heading','wrong-target'):
            meter,_=synthetic_stream(native_fault=fault)
            with self.subTest(fault=fault):
                self.assertEqual(len(meter.cases),32)
                self.assertFalse(meter.finish()['passed'])
                self.assertIn('matrix native plan differs',meter.finish()['failures'])

    def test_saved_first_diagonal_replays_past_tick_without_full_proof(self):
        from tools.overworld.control import _replay_shared_test, _shared_artifact, load_observations
        root=Path(__file__).resolve().parents[2]
        directory=root/'build/overworld-devtools/test-9eb93088b4c547dcb869e08635e3e022'
        if not directory.exists():self.skipTest('optional first-diagonal9eb9 memory data absent')
        test=json.loads((directory/'test.json').read_text())
        manifest=json.loads((directory/'manifest.json').read_text())
        rows=load_observations(_shared_artifact(manifest['observationsArtifact'],directory))
        from tools.overworld.devtools_test_contract import validate_test
        current=validate_test(json.loads((root/'tests/overworld/test-recipes/walk.cardinal.frames-1-32.json').read_text()))
        # This retained failure stops inside the first diagonal Tick, before
        # the new post-completion field-step drain. Its observed prefix is
        # unchanged; missing future actions cannot become a passing result.
        self.assertEqual(test['setup'],current['setup'])
        self.assertEqual(test['actions'][:99],current['actions'][:99])
        replay=_replay_shared_test(current,rows,repo=root)
        value=replay['measurements'][KIND]
        self.assertFalse(replay['passed'])
        self.assertFalse(value['ready'])
        self.assertEqual(value['startedMotions'],33)
        self.assertEqual(value['completedCases'],32)
        self.assertEqual(value['failures'],['matrix exact lifecycle missing: LOGICAL_COMMIT'])
        self.assertFalse(manifest['acceptedProof'])

    def test_all_65_cases_and_proof_survive_json_roundtrip_exactly(self):
        # The controller compares fresh replay with the JSON-stored evaluation.
        # Tuples hidden inside case records make valid dependency proof stale.
        self.assertEqual(list(CASES),json.loads(json.dumps(CASES)))
        self.assertEqual(contract(),json.loads(json.dumps(contract())))
        meter,_=synthetic_stream()
        result=meter.finish()
        self.assertTrue(result['passed'],result['failures'])
        stored=json.loads(json.dumps(result))
        self.assertEqual(result,stored)
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        fresh_rows=measurements(dict(passed=True,failures=[],measurements={KIND:result}),record)
        stored_rows=measurements(dict(passed=True,failures=[],measurements={KIND:stored}),record)
        self.assertEqual(fresh_rows,stored_rows)
        self.assertEqual(fresh_rows,json.loads(json.dumps(fresh_rows)))

    def test_all_copied_faults_feed_the_actual_full_matrix_meter(self):
        meter,_ = synthetic_stream()
        result = meter.finish()
        self.assertTrue(result["passed"],result["failures"])
        record = dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[]))
        self.assertEqual(len(measurements(dict(passed=True,failures=[],measurements={KIND:result}),record)),6)
        for fault in FAULTS:
            meter,negative = synthetic_stream(fault)
            value = meter.finish()
            with self.subTest(fault=fault):
                self.assertTrue(negative.applied)
                self.assertFalse(value["passed"])
                validate_negative_result(dict(passed=False,failures=[],measurements={KIND:value}),fault)

    def test_full_retained_pilot_cannot_supply_the_matrix_proof(self):
        from tools.overworld.test_devtools_walk_matrix_measurement import pilot
        result = pilot(case_limit=65).finish()
        self.assertFalse(result["passed"])
        self.assertEqual(result["completedCases"],2)
        _,record = good_result()
        with self.assertRaises(ValueError):
            measurements(dict(passed=True,failures=[],measurements={KIND:result}),record)

    def test_unrelated_or_generic_failure_cannot_credit_any_control(self):
        for fault in FAULTS:
            for failure in ("boot failed", "matrix incomplete", "matrix frame budget exceeded"):
                with self.subTest(fault=fault,failure=failure),self.assertRaises(ValueError):
                    validate_negative_result(dict(passed=False,failures=[failure]),fault)
        with self.assertRaises(ValueError): MatrixNegative("unknown")

    def test_subject_control_changes_a_copy_once(self):
        replay,_ = good_result(); value = replay["measurements"][KIND]
        row = dict(phase="observe",samples=[value["initial"]],events=[])
        original = deepcopy(row)
        negative = MatrixNegative("matrix-stale-subject")
        changed = negative.mutate(row,{"actor":value["subject"]})
        self.assertEqual(row,original)
        self.assertTrue(negative.applied)
        self.assertNotEqual(changed,row)
        self.assertIs(negative.mutate(row,{"actor":value["subject"]}),row)

    def test_exact_original_six_rows(self):
        registry = json.loads((Path(__file__).resolve().parents[2]/"tools/overworld/runtime_proof_registry.json").read_text())
        owner = next(v for v in registry.values() if isinstance(v,dict)
            and isinstance(v.get(REQUIREMENT),dict) and "natural-input" in v[REQUIREMENT])
        self.assertEqual(contract(),owner[REQUIREMENT])
        replay,record = good_result()
        self.assertEqual(len(measurements(replay,record)),6)

    def test_green_summary_cannot_replace_exact_raw_case_vectors(self):
        for fault in ("missing-final","elapsed","reservation","clock","cancel","lifecycle","gate"):
            replay,record = good_result(); value = replay["measurements"][KIND]
            motion = value["cases"][0]
            if fault == "missing-final": value["cases"].pop()
            elif fault == "elapsed": motion["ticks"][0]["before"]["elapsed"] = 1
            elif fault == "reservation": motion["ticks"][0]["after"]["reservationId"] += 1
            elif fault == "clock": motion["ticks"][0]["after"]["frame"] += 1
            elif fault == "cancel": motion["events"].append(dict(event="MOTION_CANCELED"))
            elif fault == "lifecycle": motion["events"].pop()
            else: value["diagonalAttempt"]["after"][0] += 1
            with self.subTest(fault=fault),self.assertRaises(ValueError): measurements(replay,record)

    def test_green_summary_cannot_replace_owner_profile_cleanup_or_full_scope(self):
        for fault in ("absent","stale","terminal","profile","config-count","summary","cleanup","prefix"):
            replay,record = good_result(); value = replay["measurements"][KIND]
            if fault == "absent": value["initial"]["actors"] = []
            elif fault == "stale": value["initial"]["actors"][0]["authorityGeneration"] += 1
            elif fault == "terminal": value["terminalSnapshot"]["actors"][0]["reservationId"] = 1
            elif fault == "profile": value["configurations"][0]["profileHex"] = "00"*72
            elif fault == "config-count": value["configurations"].pop()
            elif fault == "summary": value["proofEvidence"]["natural-input"][0]["actual"] = 64
            elif fault == "cleanup": record["sessionCleanup"]["closed"] = False
            else: value.update(prefixOnly=True,expectedCases=2,cases=value["cases"][:2])
            with self.subTest(fault=fault),self.assertRaises(ValueError): measurements(replay,record)


if __name__ == "__main__": unittest.main()
