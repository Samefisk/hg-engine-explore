"""Synthetic bridge receipts and optional retained memory replay; no live proof."""
from copy import deepcopy
from pathlib import Path
import json
import struct
import unittest
from tools.overworld.devtools_actor_inspect_measurement import ActorInspectMeasurement, actor_bytes
from tools.overworld.devtools_actor_inspect_proof import actor_inspect_measurements, negative_controls
from tools.overworld.devtools_records import select_current_actor


def fixture():
    test = dict(mode="prepared", subjects=[dict(id="mankey", species=56, role="FOLLOWER", acquire="existing")],
        setup=[dict(id="bind-mankey", op="bind", args=dict(subject="mankey"))],
        actions=[dict(id="inspect-current-and-stale", op="actor-inspect.probe", args=dict(subject="mankey"))])
    handle = dict(value=65543, slot=7, generation=1, fieldEpoch=2, mapGeneration=2, encounterGeneration=1)
    a = dict(handle=handle, species=56, subjectIdentity=123, role="FOLLOWER", active=True,
        presentationAttached=True, identityVerified=True, form=0, level=3, roleId=2, laneId=0,
        motionKindId=0, motionPhaseId=0, presentationState=7)
    for key in ("behaviorFingerprint", "matchedLayerMask", "lastCommandSequence", "commitSequence", "motionElapsed",
                "motionDuration", "reservationId", "inputOwnership", "streamState", "controllerState", "lastIntent", "lastDecision", "lastCancelReason"):
        a[key] = 0
    for key in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration"): a[key] = 1
    for key in ("logical", "render", "origin", "target"): a[key] = dict(x=1, y=2)
    a["sourceIdentity"] = dict(object=0x02201000, active=1, personality=123, species=56, form=0, level=3,
        object_id=231, map_id=33, encounter_generation=1)
    a["engineIdentity"] = dict(pointer=0x02201000, manager_index=5, in_manager=True, active=True, object_manager=0x02200000,
        current_manager=0x02200000, object_id=231, spawn_object_id=231, object_map_id=33,
        spawn_map_id=33, current_map_id=33, encounter_generation=1, script_id=2074)
    snapshot = dict(frame=10, nativeCycle=20, context=dict(fieldEpoch=2, mapGeneration=2), actors=[a])
    subject = select_current_actor(snapshot, a)
    service = dict(address=0x02300000, version=1, size=24, facadeHex="00" * 24,
                   inspectAddress=0x02300101, entrySha256="12" * 32)
    oracle = dict(serviceIdentity=service, callAddresses=dict(allocate_work_memory=0x02010000,
        inspect_actor=0x02300100, free=0x02010100))
    work, trampoline, sp = 0x02210000, 0x02220000, 0x027e0000
    cases = []
    current = actor_bytes(a)
    for i, name in enumerate(("current-handle", "stale-generation")):
        query = struct.pack("<HHBBH6HI", 1, 24, 1, 0, 0, 7, 1+i, 2, 2, 1, 0, 0)
        output = bytearray(176)
        struct.pack_into("<HH4B", output, 0, 1, 176, 1, int(i == 0), 0, 0)
        if i == 0: output[20:108] = current
        cases.append(dict(name=name, queryHex=query.hex(), outputHex=output.hex(), currentActorHex=current.hex(),
            currentActorAfterHex=current.hex(), stateBeforeSha256="34"*32, stateAfterSha256="34"*32,
            actor=deepcopy(a), status=2*i, dispatchClock=dict(frame=10, nativeCycle=20),
            returnClock=dict(frame=10, nativeCycle=20), fieldPointer=0x02230000, heapGeneration=1,
            serviceIdentity=deepcopy(service)))
    calls = []
    for name, args, status in (("allocate_work_memory", [11,232], work), ("inspect_actor", [work+16,work+40],0),
                               ("inspect_actor", [work+16,work+40],2), ("free",[work],0)):
        calls.append(dict(routine=name,address=oracle["callAddresses"][name],requestedArguments=args,
            entryArguments=list(args),returnValue=status,entryStack=sp,entryLink=trampoline+0x4c,
            entryCpsr=0x3f,entryBoundary="native-trampoline-BLX-entry"))
    receipt = dict(boundary="native-field-command-trampoline",preparedOnly=True,acceptedProof=False,
        firstBadCheckpoint=None,firstInvalidThreadSwitch=None,nativeHeapAdaptation=[],calls=calls,
        trampoline=dict(address=trampoline,bytes=1536,heapId=11,lifetime="field-system-heap11",
                        fieldPointer=0x02230000,heapGeneration=1),
        stackOwnership=dict(callSp=sp,hostRestoredFrameBytes=0,nativeFrameBytes=80,scratchBytes=268,
                            thread=dict(mode=31,irqDepth=0,stackTop=sp-1000,stackBottom=sp+1000)),
        setupBoundary=dict(frame=10,nativeCycle=20,endpointNativeCycle=20,eventsDrained=True,traceSequences={}),
        value=dict(completed=True,acceptedProof=False,receipts=cases,
                   allocation=dict(pointer=work,bytes=232,heapId=11,released=True)))
    rows = [dict(initialSnapshot=deepcopy(snapshot)),dict(phase="setup",action="bind-mankey",command="bind",
        receipt=subject,snapshot=deepcopy(snapshot)),dict(phase="observe",action="inspect-current-and-stale",
        command="actor-inspect.probe",receipt=receipt,snapshot=deepcopy(snapshot))]
    return test, rows, oracle


class ActorInspectMeasurementTests(unittest.TestCase):
    def test_native_follower_role_anchors_public_header(self):
        import re
        source = (Path(__file__).resolve().parents[2] / "include/overworld_actor_system.h").read_text()
        match = re.search(r"OVERWORLD_ACTOR_ROLE_FOLLOWER\s*=\s*(\d+)\s*,", source)
        self.assertIsNotNone(match)
        self.assertEqual(int(match[1]), 2)

    def test_coherent_native_owner_or_role_replacement_is_rejected(self):
        for fault in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration", "pointer", "roleId"):
            with self.subTest(fault=fault):
                test, rows, oracle = fixture()
                cases = rows[-1]["receipt"]["value"]["receipts"]
                for index, case in enumerate(cases):
                    a = case["actor"]
                    if fault == "pointer":
                        a["sourceIdentity"]["object"] += 300
                        a["engineIdentity"]["pointer"] += 300
                    elif fault == "roleId": a["roleId"] = 3
                    else: a[fault] += 1
                    current = actor_bytes(a)
                    case["currentActorHex"] = case["currentActorAfterHex"] = current.hex()
                    output = bytearray.fromhex(case["outputHex"])
                    if index == 0: output[20:108] = current
                    case["outputHex"] = output.hex()
                with self.assertRaises(ValueError):
                    actor_inspect_measurements(test, rows, {}, None, oracle=oracle)

    def test_exact_fixture_and_twelve_controls(self):
        test, rows, oracle = fixture()
        before = deepcopy(rows)
        proof = actor_inspect_measurements(test, rows, {}, None, oracle=oracle)
        self.assertEqual(proof["observedFrames"], 1)
        self.assertEqual(proof["completedGameFrames"], 0)
        self.assertEqual(len(negative_controls(test, rows, {}, None, oracle=oracle)["controls"]), 12)
        self.assertEqual(rows, before)

    def test_order_phase_missing_duplicate_and_fault(self):
        for fault in ("order", "phase", "missing", "duplicate", "fatal", "clock", "empty-cases", "predates-bind"):
            test, rows, _ = fixture()
            if fault == "order": rows[0], rows[1] = rows[1], rows[0]
            elif fault == "phase": rows[2]["phase"] = "setup"
            elif fault == "missing": rows.pop()
            elif fault == "duplicate": rows.append(deepcopy(rows[-1]))
            elif fault == "fatal": rows[-1]["receipt"]["fatal"] = True
            elif fault == "empty-cases": rows[-1]["receipt"]["value"]["receipts"] = []
            elif fault == "predates-bind": rows[-1]["receipt"]["value"]["receipts"][0]["dispatchClock"]["nativeCycle"] = 19
            else: rows[-1]["receipt"]["value"]["receipts"][0]["returnClock"]["nativeCycle"] = 19
            m = ActorInspectMeasurement(test)
            for row in rows: m.observe_record(row)
            self.assertFalse(m.finish()["passed"], fault)

    def test_retained_manual_receipt_replay_only(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "build/overworld-devtools/session-v2ul19p8/event-details-489b27ee23cf.json"
        if not path.exists(): self.skipTest("retained manual data absent")
        test, rows, _ = fixture()
        receipt = json.loads(path.read_text())["receipt"]
        actor = receipt["value"]["receipts"][0]["actor"]
        boundary = receipt["setupBoundary"]
        snapshot = dict(frame=boundary["frame"], nativeCycle=boundary["nativeCycle"], actors=[actor],
            context={k:actor["handle"][k] for k in ("fieldEpoch", "mapGeneration")})
        initial = deepcopy(snapshot)
        initial.update(receipt["value"]["receipts"][0]["dispatchClock"])
        rows[0] = dict(initialSnapshot=deepcopy(initial))
        rows[1].update(snapshot=deepcopy(initial),receipt=select_current_actor(initial, actor))
        rows[2].update(snapshot=deepcopy(snapshot),receipt=receipt)
        oracle = dict(serviceIdentity=receipt["value"]["receipts"][0]["serviceIdentity"],
                      callAddresses={c["routine"]:c["address"] for c in receipt["calls"]})
        # This oracle comes from memory data only to test parser compatibility;
        # the controller must supply its independent package oracle for proof.
        self.assertEqual(actor_inspect_measurements(test,rows,{},root,oracle=oracle)["observedFrames"],1)
