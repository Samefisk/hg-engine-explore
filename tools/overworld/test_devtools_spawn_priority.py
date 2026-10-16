"""Host predicate controls only; these fixtures grant no game acceptance."""
from copy import deepcopy
import struct
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_spawn_outcome_records import creation_delay_anchor, quality
from tools.overworld.devtools_spawn_priority_measurement import (
    RETRY, WATER, CASES, MAX_TOTAL_FRAMES, WARMUP_FRAMES, max_total_frames,
    SpawnPriorityMeasurement, retry_witnesses, validate_recipe, warmup_setup)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_spawn_surface_measurement import check_natural_water_surface
from tools.overworld.test_devtools_spawn_surface_measurement import surface_fixture


def creation_fixture(frame=320, attempt=1, *, sample=None):
    spawn, original = surface_fixture()
    sample = deepcopy(original if sample is None else sample)
    world = dict(fieldPointer=0x2200000, statePointer=0x2300000,
                 mapId=67, fieldEpoch=2, mapGeneration=2)
    sample.update(frame=frame, nativeCycle=frame * 2, actorFrame=frame,
        context={k:world[k] for k in ("mapId", "fieldEpoch", "mapGeneration")},
        fieldControl=dict(taskPointer=0, fieldPointer=world["fieldPointer"]))
    actor = deepcopy(original["actors"][0])
    actor["handle"] = dict(value=65537, slot=1, generation=1,
        fieldEpoch=2, mapGeneration=2, encounterGeneration=1)
    actor.update(active=True, identityVerified=True, presentationAttached=True)
    actor["sourceIdentity"]["map_id"] = 67
    actor["engineIdentity"].update(object_map_id=67, current_map_id=67)
    sample["actors"] = [a for a in sample["actors"] if a.get("role") != "WILD"] + [actor]
    subject = {k:deepcopy(actor[k]) for k in ("handle", "species", "role", "form", "level",
        "subjectIdentity", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")}
    subject["status"] = "observed-public-subject"
    clocks = dict(entryActorFrame=frame, returnActorFrame=frame,
                  entryNativeCycle=frame * 2, returnNativeCycle=frame * 2)
    finalizer = dict(observation="spawn-finalized", sequence=frame * 10 - 1,
        returnValue=1, querySerial=attempt, spawnAttemptId=attempt, slot=1, terrain=0,
        statePointer=world["statePointer"], fieldPointer=world["fieldPointer"],
        worldContext=deepcopy(world), preparedPointer=spawn["preparedPointer"],
        preparedPrefixHex="01" * 30, **clocks)
    constructor = dict(observation="spawn-prepared", sequence=frame * 10 + 2,
        returnValue=1, setupMode="normal", slot=1, terrain=0,
        statePointer=world["statePointer"], fieldPointer=world["fieldPointer"],
        worldContext=deepcopy(world), preparedPointer=spawn["preparedPointer"],
        preparedPrefixHex=finalizer["preparedPrefixHex"], publicSubject=subject,
        finalization=dict(status="matched", receipt=deepcopy(finalizer)), **clocks)
    create = dict(observation="spawn-object-create", sequence=frame * 10 + 1,
        slot=1, returnValue=actor["sourceIdentity"]["object"], **clocks)
    control = dict(observation="entry-native-control", sequence=frame * 10 + 3,
        boundary="native-entry-control-tick-return", returnValue=1,
        entry=dict(kind="native-control", operation=7, outcome=3, value=3 | (60 << 8), refillDelay=60),
        imageIdentity=dict(loaderOwner=struct.pack("<4I2HIB3s",
            0x2100000, 69072, 0x2100040, world["fieldPointer"], 2, 2, 21, 1, bytes(3)).hex()),
        admission=dict(serial=attempt, actor=deepcopy(actor["handle"]), constructorSequence=constructor["sequence"]),
        **clocks)
    events = [dict(frame=frame, kind="native-observation", data=d) for d in (create, constructor, control)]
    return sample, events


def water_fixture():
    spawn, sample = surface_fixture()
    spawn.update(observation="spawn-prepared", setupMode="prepared", returnValue=1,
        terrain=1, position=[16, 0], startup=dict(locomotion=7, target=[16, 0], origin=[16, 0]))
    height = deepcopy(spawn["jumpReceipts"][0]["landingHeight"])
    height["initialPlacement"] = True
    for key in ("loadedTerrainBefore", "loadedTerrain"):
        cell = height[key]["cell"]
        cell.update(attribute=16, behavior=16)
        cell["provenance"]["rawWord"] = 16
    spawn["initialLandingHeight"] = height
    sample["prepared"] = True
    return spawn, sample


def natural_recipe(kind):
    from tools.overworld.devtools_test_contract import validate_test
    root = Path(__file__).resolve().parents[2]
    return validate_test(json.loads((root / "tests/overworld/test-recipes" /
                                    (CASES[kind]["test"] + ".json")).read_text()))


def warmup_fixture(map_id=67, x=564, y=392, steps=0, epoch=2):
    from tools.overworld.test_devtools_movement_predicates import snapshot
    sample, _ = creation_fixture()
    sample.update(prepared=True, fieldAvailable=True, observationBoundary="main-task-queue-completion")
    sample["context"].update(mapId=map_id, fieldEpoch=epoch, mapGeneration=epoch)
    sample["player"] = deepcopy(snapshot()["player"])
    sample["player"].update(x=x, y=y, x_prev=x, y_prev=y, movement_cmd=255,
                           pos_x=(x << 16) + 0x8000, pos_z=(y << 16) + 0x8000)
    sample["selector"] = dict(physicalPressed=0, heldKeys=0, newKeys=0, simulatedKeys=0, activeFollowerPartySlot=2)
    sample["nativeObservation"].update(playerStepCount=steps, playerStepFrame=sample["frame"],
        coverageComplete=True, installedBeforeBoot=True, eventsDropped=0, profilesEvicted=0,
        pendingUnframedEvents=0, error=None)
    actor = sample["actors"][0]
    actor.update(species=56, role="FOLLOWER", motionPhase="IDLE", motionKind="NONE", reservationId=0)
    actor["sourceIdentity"].update(active=1, species=56, personality=actor["subjectIdentity"],
        form=actor["form"], level=actor["level"], map_id=map_id, object_id=231,
        encounter_generation=actor["handle"]["encounterGeneration"], object=0x2201000)
    actor["engineIdentity"].update(pointer=0x2201000, object_id=231, spawn_object_id=231,
        object_map_id=map_id, current_map_id=map_id, script_id=2074,
        active=True, in_manager=True, object_manager=0x2202000, current_manager=0x2202000)
    sample["party"] = [dict(slot=i,species=56 if i==2 else 155,
        personality=actor["subjectIdentity"] if i==2 else 100+i, identityVerified=True,
        isEgg=False, form=actor["form"], level=actor["level"], hp=10,maxHp=20,status=0) for i in range(3)]
    sample["partyObservation"] = dict(frame=sample["frame"],boundary="main-task-queue-completion")
    actor["handle"].update(slot=7, value=65543, fieldEpoch=epoch, mapGeneration=epoch)
    return sample


def raw_warmup_step(previous, *, with_event=True):
    sample = deepcopy(previous)
    sample.update(frame=previous["frame"] + 1, nativeCycle=previous["nativeCycle"] + 1)
    sample["nativeObservation"].update(playerStepCount=1, playerStepFrame=sample["frame"])
    sample["partyObservation"]["frame"] = sample["frame"]
    event = dict(frame=sample["frame"], kind="native-observation", data=dict(
        observation="player-step-admitted", setupMode="prepared", stepIndex=1, direction=3,
        mapId=67, origin=[564,392], target=[565,392], objectPointer=0x2201000,
        returnValue=0x2201000, objectBefore=dict(x=564,y=392), objectAfter=dict(x=565,y=392)))
    return dict(phase="setup", action="warmup-east", samples=[sample],
        events=[event] if with_event else [], requestedInput=dict(keys=["RIGHT","B"]),
        cycleIntervals=[dict(cpuNs=1, wallNs=1, completedGameFrame=sample["frame"])],
        completedGameFrames=1, observedFieldFrames=1, nativeCycles=1)


class SpawnPriorityTests(unittest.TestCase):
    def test_natural_recipes_pin_warmup_and_keep_exact_test_window(self):
        self.assertEqual(sum(a["budget"]["maxFrames"] for a in warmup_setup()), WARMUP_FRAMES)
        for kind in (RETRY, WATER):
            value = natural_recipe(kind)
            validate_recipe(value)
            self.assertEqual((len(value["setup"]), value["budgets"]["maxFrames"],
                              value["budgets"]["minObservedFrames"], value["budgets"]["maxSeconds"]),
                             (16, max_total_frames(kind), 600, 240))
            for fault in ("early-warp", "keys", "warmup-budget", "frames", "time", "credit"):
                bad = deepcopy(value)
                if fault == "early-warp": bad["setup"] = bad["setup"][12:]
                elif fault == "keys": bad["setup"][1]["args"]["keys"] = []
                elif fault == "warmup-budget": bad["setup"][1]["budget"]["maxFrames"] += 1
                elif fault == "frames": bad["budgets"]["maxFrames"] += 1
                elif fault == "time": bad["budgets"]["maxSeconds"] += 1
                else: bad["budgets"]["minObservedFrames"] -= 1
                with self.subTest(kind=kind,fault=fault), self.assertRaises(ValueError):
                    validate_recipe(bad)

    def test_warmup_raw_native_step_earns_no_measurement_credit(self):
        initial = warmup_fixture()
        for fault in (None, "missing-native", "changed-origin", "wrong-mode", "wrong-input"):
            meter = SpawnPriorityMeasurement(natural_recipe(RETRY), dict(contractVersion=1))
            meter.observe_record(dict(phase="setup", initialSnapshot=initial))
            row = raw_warmup_step(initial, with_event=fault != "missing-native")
            if fault == "changed-origin": row["events"][0]["data"]["origin"][0] += 1
            elif fault == "wrong-mode": row["events"][0]["data"]["setupMode"] = "normal"
            elif fault == "wrong-input": row["requestedInput"]["keys"] = []
            calls = []
            meter.observe_record(row, on_sample=lambda s,f: calls.append(f))
            if fault:
                self.assertTrue(meter.failures, fault)
            else:
                self.assertEqual((meter.setup_index,meter.warmup_steps,meter.warmup_frames), (2,1,1))
                self.assertEqual(calls, [0])
                self.assertEqual(meter.windows, [dict(snapshots=[],events=[]),dict(snapshots=[],events=[])])
            self.assertEqual(meter.observed_frames, 0)
            self.assertFalse(meter.result()["ready"])

    def test_warmup_bind_requires_real_settled_released_full_follower(self):
        for fault in (None, "identity", "unverified", "fractional", "counter", "held", "missing-step", "moving", "reserved"):
            meter = SpawnPriorityMeasurement(natural_recipe(WATER), dict(contractVersion=1))
            sample = warmup_fixture(33,585,406,35)
            actor = sample["actors"][0]
            meter.setup_index, meter.warmup_steps = 12, 35
            meter.warmup_identity = actor["subjectIdentity"]
            if fault == "identity": meter.warmup_identity += 1
            elif fault == "unverified": actor["identityVerified"] = False
            elif fault == "fractional": sample["player"]["pos_x"] -= 1
            elif fault == "counter": sample["nativeObservation"]["playerStepCount"] -= 1
            elif fault == "held": sample["selector"]["physicalPressed"] = 18
            elif fault == "missing-step": meter.warmup_steps -= 1
            elif fault == "moving": actor.update(motionPhase="MOVING",motionKind="HOP")
            elif fault == "reserved": actor["reservationId"] = 10
            meter.latest = deepcopy(sample)
            meter.observe_record(dict(phase="setup", action="warmup-bind-current-field",
                                     command="bind", receipt=actor, snapshot=sample))
            self.assertEqual(bool(meter.failures), fault is not None)
            if fault is None:
                self.assertEqual(meter.setup_index,13)
                self.assertFalse(meter.warmup_boundary["credited"])
            self.assertEqual(meter.observed_frames,0)

    def test_follower_wait_uses_full_existing_predicate_and_has_no_setup_credit(self):
        meter=SpawnPriorityMeasurement(natural_recipe(RETRY),dict(contractVersion=1))
        previous=warmup_fixture(33,585,406,35)
        previous["actors"][0].update(motionPhase="MOVING",motionKind="HOP",reservationId=10)
        meter.setup_index,meter.warmup_steps=11,35
        meter.warmup_identity=previous["actors"][0]["subjectIdentity"]
        meter.latest=previous
        calls=[]
        for settled in (False,True):
            sample=deepcopy(meter.latest)
            sample.update(frame=sample["frame"]+1,nativeCycle=sample["nativeCycle"]+1)
            sample["nativeObservation"]["playerStepFrame"]=sample["frame"]
            sample["partyObservation"]["frame"]=sample["frame"]
            if settled:sample["actors"][0].update(motionPhase="IDLE",motionKind="NONE",reservationId=0)
            row=dict(phase="setup",action="warmup-follower-settled",samples=[sample],events=[],
                requestedInput=dict(keys=[]),completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,
                cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=sample["frame"])])
            meter.observe_record(row,on_sample=lambda s,f:calls.append(f))
            self.assertEqual(meter.failures,[])
            self.assertEqual(meter.setup_index,12 if settled else 11)
        self.assertEqual(calls,[0,0])
        self.assertEqual(meter.observed_frames,0)
        self.assertFalse(any(w["events"] or w["snapshots"] for w in meter.windows))
        sample=meter.latest
        meter.observe_record(dict(phase="setup",action="warmup-bind-current-field",command="bind",
                                 snapshot=sample,receipt=sample["actors"][0]))
        self.assertEqual(meter.failures,[])
        self.assertEqual(meter.setup_index,13)

    def test_follower_wait_rejects_changed_party_and_120_frame_overrun(self):
        for fault in ("party","overrun","input"):
            meter=SpawnPriorityMeasurement(natural_recipe(WATER),dict(contractVersion=1))
            previous=warmup_fixture(33,585,406,35)
            previous["actors"][0].update(motionPhase="MOVING",motionKind="HOP",reservationId=10)
            meter.setup_index,meter.warmup_steps=11,35
            meter.latest=previous
            sample=deepcopy(previous)
            sample.update(frame=sample["frame"]+1,nativeCycle=sample["nativeCycle"]+1)
            sample["nativeObservation"]["playerStepFrame"]=sample["frame"]
            sample["partyObservation"]["frame"]=sample["frame"]
            row=dict(phase="setup",action="warmup-follower-settled",samples=[sample],events=[],
                requestedInput=dict(keys=[]),completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,
                cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=sample["frame"])])
            if fault=="party":sample["party"][2]["personality"]+=1
            elif fault=="overrun":meter.setup_action_frames=120
            else:row["requestedInput"]["keys"]=["RIGHT"]
            meter.observe_record(row)
            self.assertTrue(meter.failures,fault)
            self.assertEqual(meter.observed_frames,0)

    def test_natural_warp_is_after_warmup_and_requires_exact_different_map_receipt(self):
        for kind in (RETRY,WATER):
            for fault in (None, "no-warmup", "same-map", "receipt-clock"):
                meter = SpawnPriorityMeasurement(natural_recipe(kind), dict(contractVersion=1))
                meter.setup_index=13
                meter.latest=warmup_fixture(33,585,406,35)
                meter.warmup_boundary=dict(credited=False)
                map_id,x,y=CASES[kind]["start"]
                sample=warmup_fixture(map_id,x,y,35,3)
                receipt=dict(preparedOnly=True,snapshot=deepcopy(sample),setupBoundary=dict(
                    frame=sample["frame"],nativeCycle=sample["nativeCycle"],eventsDrained=True))
                if fault=="no-warmup":meter.warmup_boundary=None
                elif fault=="same-map":sample["context"]["mapId"]=33
                elif fault=="receipt-clock":receipt["setupBoundary"]["frame"]+=1
                meter.observe_record(dict(phase="setup",action="natural-window",command="teleport",
                                         receipt=receipt,snapshot=sample))
                self.assertEqual(bool(meter.failures), fault is not None)
                self.assertEqual(meter.observed_frames,0)

    def test_natural_rebind_preserves_personality_and_rejects_inactive_engine(self):
        for fault in (None,"personality","engine"):
            meter=SpawnPriorityMeasurement(natural_recipe(RETRY),dict(contractVersion=1))
            meter.setup_index=14
            sample=warmup_fixture(67,543,393,35,3)
            actor=sample["actors"][0]
            meter.warmup_identity=actor["subjectIdentity"]
            if fault=="personality":meter.warmup_identity+=1
            elif fault=="engine":actor["identityVerified"]=False
            meter.latest=deepcopy(sample)
            meter.observe_record(dict(phase="setup",action="bind-current-field",command="bind",
                                     receipt=actor,snapshot=sample))
            self.assertEqual(bool(meter.failures),fault is not None)
            if fault is None:self.assertEqual(meter.setup_index,16)
            self.assertEqual(meter.observed_frames,0)

    def natural_evaluator_at_warp(self, kind):
        from tools.overworld.devtools_test_contract import TestEvaluator
        evaluator = TestEvaluator(natural_recipe(kind))
        evaluator.install_measurements({kind:dict(contractVersion=1)})
        meter = evaluator.measurements[kind]
        warmup = warmup_fixture(33,585,406,35)
        evaluator.latest = deepcopy(warmup)
        meter.latest = deepcopy(warmup)
        meter.setup_index, meter.warmup_steps = 12,35
        meter.warmup_identity = warmup["actors"][0]["subjectIdentity"]
        bound = evaluator.bind("mankey",warmup)
        evaluator.observe_record(dict(phase="setup",action="warmup-bind-current-field",
            command="bind",snapshot=warmup,receipt=bound))
        self.assertEqual(evaluator.failures,[])
        self.assertEqual(meter.setup_index,13)
        map_id,x,y=CASES[kind]["start"]
        current=warmup_fixture(map_id,x,y,35,3)
        current.update(frame=warmup["frame"]+2,nativeCycle=warmup["nativeCycle"]+2)
        current["partyObservation"]["frame"]=current["frame"]
        current["actors"]=[]
        receipt=dict(preparedOnly=True,snapshot=deepcopy(current),setupBoundary=dict(
            frame=current["frame"],nativeCycle=current["nativeCycle"],eventsDrained=True))
        row=dict(phase="setup",action="natural-window",command="teleport",
                 snapshot=current,receipt=receipt)
        return evaluator,meter,bound,row

    def test_natural_evaluator_releases_only_validated_old_binding(self):
        for kind in (RETRY,WATER):
            for fault in (None,"prepared","receipt-clock","old-epoch","old-map-generation","old-binding"):
                with self.subTest(kind=kind,fault=fault):
                    evaluator,meter,bound,row=self.natural_evaluator_at_warp(kind)
                    evaluator.subjects["unrelated"]=deepcopy(bound)
                    if fault=="prepared":row["receipt"]["preparedOnly"]=False
                    elif fault=="receipt-clock":row["receipt"]["setupBoundary"]["nativeCycle"]+=1
                    elif fault in ("old-epoch","old-map-generation"):
                        key="fieldEpoch" if fault=="old-epoch" else "mapGeneration"
                        row["snapshot"]["context"][key]=meter.latest["context"][key]
                        row["receipt"]["snapshot"]=deepcopy(row["snapshot"])
                    elif fault=="old-binding":evaluator.subjects["mankey"]["handle"]["fieldEpoch"]+=1
                    evaluator.observe_record(row)
                    self.assertEqual(bool(evaluator.failures),fault is not None)
                    self.assertEqual("mankey" in evaluator.subjects,fault is not None)
                    self.assertEqual(evaluator.subjects["unrelated"],bound)
                    self.assertEqual(meter.warmup_identity,bound["subjectIdentity"])
                    self.assertEqual(meter.observed_frames,0)

    def test_natural_new_field_wait_and_bind_use_same_saved_full_follower(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        for kind in (RETRY,WATER):
            for fault in (None,"personality","engine","stale","moving"):
                with self.subTest(kind=kind,fault=fault):
                    evaluator,meter,bound,row=self.natural_evaluator_at_warp(kind)
                    evaluator.observe_record(row)
                    self.assertEqual(evaluator.failures,[])
                    action=evaluator.test["setup"][14]
                    self.assertEqual(action["args"]["predicate"]["kind"],"follower-settled")
                    self.assertFalse(evaluator.check(action["args"]["predicate"],evaluator.latest))
                    map_id,x,y=CASES[kind]["start"]
                    current=warmup_fixture(map_id,x,y,35,3)
                    current.update(frame=row["snapshot"]["frame"]+1,nativeCycle=row["snapshot"]["nativeCycle"]+1)
                    current["partyObservation"]["frame"]=current["frame"]
                    actor=current["actors"][0]
                    if fault=="personality":
                        actor["subjectIdentity"]+=1
                        actor["sourceIdentity"]["personality"]+=1
                        current["party"][2]["personality"]+=1
                    elif fault=="engine":actor["engineIdentity"]["active"]=False
                    elif fault=="stale":actor["handle"]["fieldEpoch"]-=1
                    elif fault=="moving":actor.update(motionPhase="MOVING",motionKind="HOP",reservationId=10)
                    raw=dict(phase="setup",action="current-follower",samples=[current],events=[],
                        requestedInput=dict(keys=[]),completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,
                        cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=current["frame"])])
                    evaluator.observe_record(raw)
                    if fault in ("engine","stale"):
                        self.assertTrue(evaluator.failures)
                        self.assertNotIn("mankey",evaluator.subjects)
                    elif fault=="moving":
                        self.assertEqual(evaluator.failures,[])
                        self.assertEqual(meter.setup_index,14)
                        self.assertNotIn("mankey",evaluator.subjects)
                    else:
                        fresh=evaluator.bind("mankey",current)
                        evaluator.observe_record(dict(phase="setup",action="bind-current-field",command="bind",
                            snapshot=current,receipt=fresh))
                        self.assertEqual(bool(evaluator.failures),fault is not None)
                        if fault is None:
                            self.assertEqual(meter.setup_index,16)
                            self.assertEqual(meter.subject["handle"],current["actors"][0]["handle"])
                            self.assertEqual(meter.subject["subjectIdentity"],bound["subjectIdentity"])
                            generic=TestEvaluator(evaluator.test)
                            generic.subjects["mankey"]=bound
                            with self.assertRaises(ValueError):generic.bind("mankey",current)
                    self.assertEqual(meter.observed_frames,0)

    def natural_evaluator_at_second_warp(self):
        from tools.overworld.devtools_test_contract import TestEvaluator
        evaluator = TestEvaluator(natural_recipe(RETRY))
        evaluator.install_measurements({RETRY:dict(contractVersion=1)})
        meter = evaluator.measurements[RETRY]
        old = warmup_fixture(67,543,393,35,3)
        evaluator.latest = deepcopy(old)
        bound = evaluator.bind("mankey",old)
        meter.latest, meter.subject = deepcopy(old), deepcopy(bound)
        meter.follower_identity = meter.warmup_identity = bound["subjectIdentity"]
        meter.setup_index, meter.action_index, meter.observed_frames = 16,4,240
        current = warmup_fixture(33,585,406,35,4)
        current.update(frame=old["frame"]+2,nativeCycle=old["nativeCycle"]+2)
        current["partyObservation"]["frame"] = current["frame"]
        current["actors"] = []
        row = dict(phase="observe",action="route29-window",command="teleport",snapshot=current,
            receipt=dict(preparedOnly=True,snapshot=deepcopy(current),setupBoundary=dict(
                frame=current["frame"],nativeCycle=current["nativeCycle"],eventsDrained=True)))
        return evaluator,meter,bound,row

    def second_field_wait_row(self, warp, *, dense=3):
        samples = []
        for i in range(1,dense+1):
            sample = warmup_fixture(33,585,406,35,4)
            sample.update(frame=warp["frame"]+i,nativeCycle=warp["nativeCycle"]+i)
            sample["partyObservation"]["frame"] = sample["frame"]
            if i < dense: sample["actors"] = []
            samples.append(sample)
        return dict(phase="observe",action="route29-current-follower",samples=samples,events=[],
            requestedInput=dict(frames=1,keys=[],releaseAtEnd=False,diagnosticDetails=False),
            completedGameFrames=dense,observedFieldFrames=dense,nativeCycles=dense,
            cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=s["frame"]) for s in samples])

    def test_retry_second_warp_releases_only_authenticated_old_binding(self):
        for fault in (None,"prepared","receipt-clock","epoch","map-generation","old-binding","early-window"):
            with self.subTest(fault=fault):
                evaluator,meter,bound,row = self.natural_evaluator_at_second_warp()
                evaluator.subjects["unrelated"] = deepcopy(bound)
                if fault == "prepared": row["receipt"]["preparedOnly"] = False
                elif fault == "receipt-clock": row["receipt"]["setupBoundary"]["nativeCycle"] += 1
                elif fault in ("epoch","map-generation"):
                    key = "fieldEpoch" if fault == "epoch" else "mapGeneration"
                    row["snapshot"]["context"][key] = meter.latest["context"][key]
                    row["receipt"]["snapshot"] = deepcopy(row["snapshot"])
                elif fault == "old-binding": evaluator.subjects["mankey"]["handle"]["fieldEpoch"] += 1
                elif fault == "early-window": meter.observed_frames -= 1
                evaluator.observe_record(row)
                self.assertEqual(bool(evaluator.failures),fault is not None)
                self.assertEqual("mankey" in evaluator.subjects,fault is not None)
                self.assertEqual(evaluator.subjects["unrelated"],bound)
                if fault is None:
                    self.assertEqual((meter.action_index,meter.window,meter.observed_frames),(5,1,240))
                    self.assertEqual(meter.window_transition["subject"]["handle"],bound["handle"])
                    self.assertFalse(meter.window_transition["credited"])

    def test_retry_second_field_dense_wait_and_bind_preserve_all_identity_guards(self):
        for fault in (None,"keys","scope","frame-gap","personality","stale","engine",
                      "moving","timeout","sequence-gap","bind-personality","bind-moving","missing-bind"):
            with self.subTest(fault=fault):
                evaluator,meter,bound,warp = self.natural_evaluator_at_second_warp()
                evaluator.observe_record(warp)
                self.assertEqual(evaluator.failures,[])
                row = self.second_field_wait_row(warp["snapshot"])
                sample = row["samples"][-1]
                actor = sample["actors"][0]
                if fault == "keys": row["requestedInput"]["keys"] = ["RIGHT"]
                elif fault == "scope": sample["context"]["fieldEpoch"] += 1
                elif fault == "frame-gap": row["samples"][0]["frame"] += 1
                elif fault == "personality": actor["subjectIdentity"] += 1
                elif fault == "stale": actor["handle"]["fieldEpoch"] -= 1
                elif fault == "engine": actor["engineIdentity"]["active"] = False
                elif fault == "moving": actor.update(motionPhase="MOVING",motionKind="HOP",reservationId=1)
                elif fault == "timeout": meter.action_frames = 63
                elif fault == "sequence-gap":
                    meter.last_sequence = 3
                    row["events"] = [dict(frame=sample["frame"],kind="native-observation",data=dict(
                        observation="unrelated",sequence=5,entryActorFrame=sample["actorFrame"],
                        returnActorFrame=sample["actorFrame"],entryNativeCycle=sample["nativeCycle"],
                        returnNativeCycle=sample["nativeCycle"]))]
                evaluator.observe_record(row)
                self.assertEqual(meter.observed_frames,240)
                self.assertEqual(meter.windows[1],dict(snapshots=[],events=[]))
                if fault == "moving":
                    self.assertEqual(evaluator.failures,[])
                    self.assertEqual(meter.action_index,5)
                    self.assertNotIn("mankey",evaluator.subjects)
                elif fault in (None,"bind-personality","bind-moving","missing-bind"):
                    self.assertEqual(evaluator.failures,[])
                    self.assertEqual((meter.action_index,meter.transition_wait_frames),(6,3))
                    if fault == "bind-personality":
                        actor["subjectIdentity"] += 1
                        actor["sourceIdentity"]["personality"] += 1
                        sample["party"][2]["personality"] += 1
                    elif fault == "bind-moving": actor.update(motionPhase="MOVING",motionKind="HOP",reservationId=1)
                    if fault == "missing-bind":
                        row["action"] = "route29-1"
                        evaluator.observe_record(row)
                    else:
                        fresh = evaluator.bind("mankey",sample)
                        evaluator.observe_record(dict(phase="observe",action="route29-bind-current-field",
                            command="bind",snapshot=sample,receipt=fresh))
                    self.assertEqual(bool(evaluator.failures),fault is not None)
                    if fault is None:
                        self.assertEqual(meter.subject["subjectIdentity"],bound["subjectIdentity"])
                        self.assertNotEqual(meter.subject["handle"],bound["handle"])
                        self.assertEqual((meter.action_index,meter.observed_frames),(7,240))
                else:
                    self.assertTrue(evaluator.failures)
                    self.assertNotIn("mankey",evaluator.subjects)

    def test_retry_replay_second_field_wait_has_no_credit_and_rechecks_present_body(self):
        from unittest.mock import patch
        from tools.overworld.control import _replay_shared_test
        for fault in (None, "pointer", "manager", "stale", "personality", "keys", "scope", "timeout", "missing-bind"):
            with self.subTest(fault=fault):
                evaluator,meter,bound,warp = self.natural_evaluator_at_second_warp()
                wait = self.second_field_wait_row(warp["snapshot"])
                sample = wait["samples"][-1]
                actor = sample["actors"][0]
                actor["engineIdentity"]["manager_index"] = 10
                if fault == "pointer": actor["sourceIdentity"]["object"] += 4
                elif fault == "manager": actor["engineIdentity"]["current_manager"] += 4
                elif fault == "stale": actor["handle"]["fieldEpoch"] -= 1
                elif fault == "personality": actor["subjectIdentity"] += 1
                elif fault == "keys": wait["requestedInput"]["keys"] = ["RIGHT"]
                elif fault == "scope": sample["context"]["fieldEpoch"] += 1
                elif fault == "timeout": meter.action_frames = 63
                rows = [warp,wait]
                if fault is None:
                    # This is a bounded prefix, not a complete timing proof.
                    rows.append(dict(phase="observe",action="route29-bind-current-field",command="bind",
                        snapshot=sample,receipt=select_current_actor(sample,actor)))
                elif fault == "missing-bind":
                    missing = deepcopy(wait)
                    missing["action"] = "route29-1"
                    rows.append(missing)
                with patch("tools.overworld.devtools_test_contract.TestEvaluator", return_value=evaluator), \
                        patch.object(evaluator,"install_measurements",return_value=None):
                    result = _replay_shared_test(evaluator.test,rows)
                self.assertFalse(result["passed"])
                self.assertEqual(meter.observed_frames,240)
                self.assertEqual(meter.windows[1],dict(snapshots=[],events=[]))
                if fault is None:
                    self.assertEqual(meter.failures,["natural spawn bounded window is incomplete"])
                    self.assertEqual(meter.subject["subjectIdentity"],bound["subjectIdentity"])
                    self.assertNotEqual(meter.subject["handle"],bound["handle"])
                    self.assertEqual((meter.action_index,meter.transition_wait_frames),(7,3))
                else:
                    self.assertNotEqual(meter.failures,["natural spawn bounded window is incomplete"])
                    if fault in ("pointer","manager"):
                        self.assertIn("retained actor/source/engine identity does not agree",meter.failures)

    def test_retry_second_wait_can_be_skipped_only_at_an_already_settled_boundary(self):
        for ready in (False,True):
            evaluator,meter,bound,warp = self.natural_evaluator_at_second_warp()
            settled = warmup_fixture(33,585,406,35,4)
            settled.update(frame=warp["snapshot"]["frame"],nativeCycle=warp["snapshot"]["nativeCycle"])
            settled["partyObservation"]["frame"] = settled["frame"]
            if ready:
                warp["snapshot"] = deepcopy(settled)
                warp["receipt"]["snapshot"] = deepcopy(settled)
            evaluator.observe_record(warp)
            self.assertEqual(evaluator.failures,[])
            fresh = evaluator.bind("mankey",settled)
            evaluator.observe_record(dict(phase="observe",action="route29-bind-current-field",command="bind",
                snapshot=settled,receipt=fresh))
            self.assertEqual(bool(evaluator.failures),not ready)
            self.assertEqual(meter.observed_frames,240)

    def test_retry_second_wait_recipe_is_finite_and_water_is_unchanged(self):
        value = natural_recipe(RETRY)
        self.assertEqual(value["budgets"]["maxFrames"],1266)
        self.assertEqual(natural_recipe(WATER)["budgets"]["maxFrames"],1201)
        for fault in ("missing-wait","wait-frames","wait-seconds","bind-frames","predicate","credit"):
            bad = deepcopy(value)
            if fault == "missing-wait": del bad["actions"][5]
            elif fault == "wait-frames": bad["actions"][5]["budget"]["maxFrames"] += 1
            elif fault == "wait-seconds": bad["actions"][5]["budget"]["maxSeconds"] += 1
            elif fault == "bind-frames": bad["actions"][6]["budget"]["maxFrames"] += 1
            elif fault == "predicate": bad["actions"][5]["args"]["predicate"]["partySlot"] = 1
            else: bad["budgets"]["minObservedFrames"] += 1
            with self.subTest(fault=fault),self.assertRaises(ValueError): validate_recipe(bad)

    def test_natural_ring_notice_is_only_exact_read_overwrite(self):
        notice = dict(code="ring-overwrite", traceStream=1, diagnosticOnly=True, count=4, unreadEventsLost=0)
        changes = [dict(code=code) for code in ("unread-events-lost", "sequence-reset", "trace-filter-changed",
                    "invalid-native-ring", "ring-overflow", "unknown")]
        changes += [dict(unreadEventsLost=value) for value in (1, None, False, "0")]
        changes += [dict(traceStream=value) for value in (0, -1, True, "1")]
        changes += [dict(count=value) for value in (0, -1, True, "4")]
        changes += [dict(diagnosticOnly=value) for value in (False, 1)]
        changes += [dict(coverageComplete=True)]
        cases = [("valid", None)] + [(str(change), change) for change in changes]
        cases += [("missing-"+key, key) for key in notice]
        cases += [("sequence-gap", None), ("sequence-duplicate", None), ("frame-gap", None)]
        for kind in (RETRY, WATER):
            for name, change in cases:
                with self.subTest(kind=kind, fault=name):
                    value = natural_recipe(kind)
                    meter = SpawnPriorityMeasurement(value, dict(contractVersion=1))
                    map_id, x, y = CASES[kind]["start"]
                    previous = warmup_fixture(map_id, x, y, 35)
                    meter.latest, meter.setup_index = previous, len(value["setup"])
                    meter.subject = deepcopy(previous["actors"][0])
                    meter.follower_identity, meter.last_sequence = meter.subject["subjectIdentity"], 3
                    sample = deepcopy(previous)
                    sample.update(frame=previous["frame"]+1, nativeCycle=previous["nativeCycle"]+1)
                    sample["partyObservation"]["frame"] = sample["frame"]
                    data = deepcopy(notice)
                    if isinstance(change, dict): data.update(change)
                    elif isinstance(change, str): data.pop(change)
                    events = [dict(frame=sample["frame"], kind="trace-status", data=data)]
                    for sequence in (4, 5):
                        events.append(dict(frame=sample["frame"], kind="native-observation", data=dict(
                            observation="unrelated-receipt", sequence=sequence,
                            entryActorFrame=sample["actorFrame"], returnActorFrame=sample["actorFrame"],
                            entryNativeCycle=sample["nativeCycle"], returnNativeCycle=sample["nativeCycle"])))
                    if name == "sequence-gap": events[-1]["data"]["sequence"] = 6
                    elif name == "sequence-duplicate": events[-1]["data"]["sequence"] = 4
                    elif name == "frame-gap":
                        sample["frame"] += 1
                        for event in events: event["frame"] = sample["frame"]
                    row = dict(phase="observe", action=value["actions"][0]["id"], samples=[sample], events=events,
                        requestedInput=dict(keys=[]), completedGameFrames=1, observedFieldFrames=1, nativeCycles=1,
                        cycleIntervals=[dict(cpuNs=1, wallNs=1, completedGameFrame=sample["frame"])])
                    result = meter.observe_record(row)
                    self.assertEqual(bool(result["failures"]), name != "valid", result)
                    if name == "valid":
                        self.assertEqual((meter.observed_frames, meter.last_sequence), (1, 5))
                        self.assertFalse(any(e["kind"] == "trace-status" for e in meter.windows[0]["events"]))
                    else:
                        reason = ("natural spawn native receipt sequence has a gap or duplicate"
                                  if name.startswith("sequence-") else "raw completed samples skip, duplicate or reverse"
                                  if name == "frame-gap" else "natural spawn raw event coverage is incomplete")
                        self.assertEqual(result["failures"], [reason])
                        self.assertEqual(meter.observed_frames, 0)

    def test_water_constructor_control_requires_its_exact_owned_constructor_rejection(self):
        from tools.overworld.devtools_spawn_priority_proof import SpawnPriorityNegative, validate_negative_result
        sample,events = creation_fixture()
        events[1]["data"]["terrain"] = 1
        row = dict(phase="observe",samples=[sample],events=events)
        negative = SpawnPriorityNegative(WATER,"water-ready-without-constructor")
        changed = negative.mutate(row,{})
        expected = deepcopy(row)
        expected["events"][1]["data"]["returnValue"] = 0
        self.assertTrue(negative.applied)
        self.assertEqual(changed,expected)
        self.assertEqual(row["events"][1]["data"]["returnValue"],1)
        for reason in ("Commit SUCCESS has no exact admitted constructor/world/queue",
                       "natural spawn native receipt sequence has a gap or duplicate",
                       "refill control return boundary differs", "creation refill anchor has a stale Field owner"):
            result = dict(passed=False,failures=[],measurements={WATER:dict(failures=[reason])})
            if reason == "Commit SUCCESS has no exact admitted constructor/world/queue":
                validate_negative_result(WATER,result,"water-ready-without-constructor")
            else:
                with self.assertRaisesRegex(ValueError,"failed for an unrelated reason"):
                    validate_negative_result(WATER,result,"water-ready-without-constructor")

    def test_actual_creation_anchor_and_copied_faults(self):
        sample, events = creation_fixture()
        anchor = creation_delay_anchor(sample, events[-1], events)
        self.assertEqual((anchor["querySerial"], anchor["refillDelay"]), (1, 60))
        for fault in ("constructor", "object", "serial", "handle", "owner", "delay"):
            s, e = creation_fixture()
            if fault == "constructor": del e[1]
            elif fault == "object": e[0]["data"]["returnValue"] += 4
            elif fault == "serial": e[-1]["data"]["admission"]["serial"] += 1
            elif fault == "handle": e[-1]["data"]["admission"]["actor"]["generation"] += 1
            elif fault == "owner": s["context"]["fieldEpoch"] += 1
            else: e[-1]["data"]["entry"].update(value=3 | (15 << 8), refillDelay=15)
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                creation_delay_anchor(s, e[-1], e)

    def test_ready_is_never_a_creation_anchor(self):
        sample, events = creation_fixture()
        event = deepcopy(events[-1])
        event["data"]["observation"] = "spawn-queued"
        event["data"].update(returnValue=1, queued=True)
        self.assertIsNone(creation_delay_anchor(sample, event, events))
        events[-1]["data"]["entry"].update(outcome=1, value=1, refillDelay=0)
        self.assertIsNone(creation_delay_anchor(sample, events[-1], events))

    def test_short_retry_and_long_failure_fault(self):
        sample, events = creation_fixture(frame=100)
        control = deepcopy(events[-1])
        control["data"]["entry"].update(outcome=2, value=2 | (15 << 8), refillDelay=15)
        world = events[1]["data"]["worldContext"]
        report = dict(naturalAttempts=[dict(startProven=True, spawnAttemptId=2,
            world=world, start=dict(sequence=control["data"]["sequence"] + 1, entryActorFrame=115), controls=[])])
        failures, density = retry_witnesses(report, [control])
        self.assertEqual(len(failures), 1); self.assertEqual(density, [])
        control["data"]["entry"].update(value=2 | (60 << 8), refillDelay=60)
        with self.assertRaisesRegex(ValueError, "failed refill ignored its decoded delay"):
            retry_witnesses(report, [control])
        report["naturalAttempts"][0]["start"]["entryActorFrame"] = 160
        self.assertEqual(retry_witnesses(report, [control]), ([], []))

    def test_density_requires_constructor_and_full_delay(self):
        world = dict(fieldPointer=1, statePointer=2, mapId=67, fieldEpoch=2, mapGeneration=2)
        first = dict(world=world, startProven=True, start=dict(sequence=1, entryActorFrame=90), controls=[dict(operation=7, outcome=3, refillDelay=60,
            sequence=2, returnActorFrame=100)], creations=[dict(handle={"value": 65537})])
        next_attempt = dict(world=world, startProven=True, spawnAttemptId=2,
            start=dict(sequence=3, entryActorFrame=160), controls=[])
        self.assertEqual(len(retry_witnesses(dict(naturalAttempts=[first, next_attempt]), [])[1]), 1)
        first["controls"][0]["refillDelay"] = 15
        with self.assertRaisesRegex(ValueError, "success refill delay lacks its actual constructor"):
            retry_witnesses(dict(naturalAttempts=[first, next_attempt]), [])

    def test_shared_water_height_and_rejections(self):
        spawn, sample = water_fixture()
        self.assertTrue(check_natural_water_surface(spawn, sample, species=165)["passed"])
        for fault in ("land", "height", "collision", "handle", "unknown", "offset", "surface"):
            s, p = water_fixture()
            h = s["initialLandingHeight"]
            if fault == "land": h["loadedTerrain"]["cell"].update(attribute=2, behavior=2, provenance=dict(h["loadedTerrain"]["cell"]["provenance"], rawWord=2))
            elif fault == "height": h["positionAfter"]["pos_y"] += 4096
            elif fault == "collision": h["loadedTerrain"]["cell"]["collision"] = True
            elif fault == "handle": p["actors"][0]["handle"]["generation"] += 1
            elif fault == "unknown": h["loadedTerrain"] = dict(status="unknown", cell=None)
            elif fault == "offset": p["actors"][0]["engineObject"]["unk88_y"] = 4096
            else: h["surfaceQuery"].update(returnValue=1, hit={"surfaceType":0})
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                check_natural_water_surface(s, p, species=165)


if __name__ == "__main__":
    unittest.main()
