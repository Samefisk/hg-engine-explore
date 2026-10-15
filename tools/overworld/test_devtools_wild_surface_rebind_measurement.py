"""Copied native-shaped records test the checker, not the running game."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_wild_surface_rebind_measurement import (
    CONFIG, ROOF, SIGN, WildSurfaceRebindMeasurement,
)
from tools.overworld.devtools_wild_surface_rebind_proof import (
    WildSurfaceRebindNegative, faults, measurements, validate_negative_result,
)

ROOT = Path(__file__).resolve().parents[2]


def recipe(kind):
    return json.loads((ROOT / "tests/overworld/test-recipes" / (CONFIG[kind]["id"] + ".json")).read_text())


def snapshot(kind, frame, *, rebound=False, grounded=False):
    c = CONFIG[kind]
    epoch = 5 if rebound else 4
    map_id = c["newMap"] if rebound else c["oldMap"]
    target = [566, 403] if kind == ROOF else [581, 397]
    origin = [target[0], target[1] + 16]
    handle = dict(value=65539, slot=3, generation=1, encounterGeneration=1,
                  fieldEpoch=epoch, mapGeneration=epoch)
    height = 261456 if kind == ROOF else 230912
    pose = dict(x=target[0], y=target[1], pos_x=(target[0] << 16) + 0x8000,
                pos_z=((target[1] if grounded else origin[1]) << 16) + 0x8000,
                pos_y=height if grounded else 202112, unk88_y=0 if grounded else 452560,
                unk94_y=0, movement_cmd=255 if grounded else 62, flags=1)
    actor = dict(active=True, role="WILD", species=c["species"], subjectIdentity=1637592900,
                 handle=handle, identityVerified=True, presentationAttached=True,
                 authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1,
                 sourceIdentity=dict(active=1, personality=1637592900, species=c["species"],
                                     object=0x022B3620, map_id=map_id),
                 engineIdentity=dict(pointer=0x022B3620, current_manager=0x022B2000, object_id=227,
                                     active=True, in_manager=True, object_map_id=map_id,
                                     current_map_id=map_id, script_id=2074),
                 engineObject=pose, target=dict(zip(("x", "y"), target)),
                 origin=dict(zip(("x", "y"), origin)), logical=dict(zip(("x", "y"), target if grounded else origin)),
                 motionKind="NONE" if grounded else "FLY_IN", motionPhase="CANCELED" if rebound and kind==ROOF else "IDLE" if grounded else "MOVING",
                 motionDuration=144, motionElapsed=2, reservationId=0 if grounded else 12,
                 commitSequence=1 if grounded else 0)
    px, pz = c["recovery"] if rebound else ([575, 400] if kind == ROOF else [589, 400])
    player = dict(x=px,y=pz,x_prev=px,y_prev=pz,pos_x=(px << 16)+0x8000,
                  pos_z=(pz << 16)+0x8000,unk88_y=0,flags=1,movement_cmd=255)
    return dict(frame=frame,nativeCycle=frame*2,context=dict(mapId=map_id,fieldEpoch=epoch,mapGeneration=epoch),
                observationBoundary="main-task-queue-completion",actors=[actor],player=player,
                fieldControl=dict(fieldPointer=0x022B1000,taskPointer=0),
                nativeObservation=dict(installedBeforeBoot=True,coverageComplete=True,error=None,
                                       eventsDropped=0,profilesEvicted=0))


def surface(snapshot_value, kind):
    c = CONFIG[kind]
    target = snapshot_value["actors"][0]["target"]
    return dict(observation=dict(context=deepcopy(snapshot_value["context"]),lastCompletedGameFrame=snapshot_value["frame"],nativeCycle=snapshot_value["nativeCycle"]),
                cells=[dict(x=target["x"],z=target["y"],loaded=True,
                    provenance=dict(fieldPointer=0x022B1000),
                    surface=dict(known=True,present=True,finalHeightKnown=True,heightMode="absolute",
                                 type=c["surfaceType"],surfaceId=c["surfaceId"],
                                 heightFx32=261456 if kind==ROOF else 230912))])


def meter(kind):
    value = WildSurfaceRebindMeasurement(recipe(kind),max_frames=420)
    initial = snapshot(kind,10)
    actor = initial["actors"][0]
    value.spawn = dict(publicSubject=deepcopy(actor),worldContext=deepcopy(initial["context"]),
                       startup=dict(locomotion=9,target=list(actor["target"].values()),origin=list(actor["origin"].values()),
                                    targetBaseY=261456 if kind==ROOF else 230912))
    value.arm(initial,actor)
    value.capture_surface(surface(initial,kind),initial)
    return value


def transition_events(kind, frame):
    old, new = snapshot(kind,frame-1)["actors"][0],snapshot(kind,frame,rebound=True,grounded=True)["actors"][0]
    result=[]
    for name in (["MOTION_CANCELED"] if kind==ROOF else [])+["CONTEXT_CHANGED","ACTOR_REBOUND"]:
        handle = new["handle"] if name=="ACTOR_REBOUND" else old["handle"]
        result.append(dict(frame=frame,kind="native",data=dict(event=name,actorHandle=handle["value"],
            actor={k:v for k,v in handle.items() if k!="value"},reason="OK" if name=="ACTOR_REBOUND" else "CONTEXT_LOST",
            valueA=CONFIG[kind]["oldMap"] if name=="ACTOR_REBOUND" else 4,
            valueB=CONFIG[kind]["newMap"] if name=="ACTOR_REBOUND" else 5)))
    return result


class WildSurfaceRebindTests(unittest.TestCase):
    def run_case(self,kind,fault=None):
        value=meter(kind)
        first=11
        if kind==SIGN:
            value.observe(snapshot(kind,11,grounded=True),[])
            self.assertTrue(value.stage("settled-on-signpost"));first=12
        control=WildSurfaceRebindNegative(kind,fault) if fault else None
        for frame in range(first,first+4):
            row=dict(phase="observe",samples=[snapshot(kind,frame,rebound=True,grounded=True)],
                     events=transition_events(kind,frame) if frame==first else [])
            if control:row=control.mutate(row,{CONFIG[kind]["subject"]:value.subject})
            value.observe(row["samples"][0],row["events"])
        result=value.finish()
        if control:self.assertTrue(control.applied)
        return result

    def test_two_witnesses_and_exact_native_height_controls(self):
        for kind in CONFIG:
            with self.subTest(kind=kind):
                result=self.run_case(kind)
                self.assertTrue(result["passed"],result["failures"])
                self.assertEqual(result["groundFrames"],4)
                replay=dict(passed=True,failures=[],measurements={kind:result})
                proof=measurements(kind,replay,dict(sessionId="copied",sessionCleanup=dict(sessionId="copied",closed=True,errors=[])))
                self.assertEqual(len(proof),6)
                for fault in faults(kind)[1:]:
                    failed=self.run_case(kind,fault)
                    self.assertFalse(failed["passed"],fault)
                    validate_negative_result(kind,failed,fault)

    def test_missing_or_wrong_surface_cannot_admit(self):
        for kind in CONFIG:
            initial=snapshot(kind,10)
            value=meter(kind);value.surface=None
            row=dict(command="terrain",receipt=dict(terrain=surface(initial,kind)))
            control=WildSurfaceRebindNegative(kind,faults(kind)[0])
            bad=control.mutate(row,{CONFIG[kind]["subject"]:value.subject})
            with self.assertRaisesRegex(ValueError,"absolute surface height"):
                value.capture_surface(bad["receipt"]["terrain"],initial)
            wrong=surface(initial,kind);wrong["cells"][0]["x"]+=1
            with self.assertRaisesRegex(ValueError,"actual Fly In target"):
                value.capture_surface(wrong,initial)

    def test_clock_gap_and_completed_roof_flight_cannot_substitute(self):
        value=meter(ROOF)
        value.observe(snapshot(ROOF,12,rebound=True,grounded=True),transition_events(ROOF,12))
        self.assertIn("queue clock gap",value.finish()["failures"][0])
        value=meter(ROOF)
        value.latest=snapshot(ROOF,10,grounded=True)
        value.observe(snapshot(ROOF,11,rebound=True,grounded=True),transition_events(ROOF,11))
        self.assertIn("missed active Fly In",value.finish()["failures"][0])

    def test_transition_order_and_owner_epoch_are_required(self):
        for kind in CONFIG:
            for fault in ("order", "epoch"):
                with self.subTest(kind=kind, fault=fault):
                    value=meter(kind)
                    first=11
                    if kind==SIGN:
                        value.observe(snapshot(kind,11,grounded=True),[])
                        first=12
                    events=transition_events(kind,first)
                    if fault=="order":
                        events[-2:]=list(reversed(events[-2:]))
                    else:
                        next(e for e in events if e["data"]["event"]=="CONTEXT_CHANGED")["data"]["valueB"]+=1
                    for frame in range(first,first+4):
                        value.observe(snapshot(kind,frame,rebound=True,grounded=True),events if frame==first else [])
                    result=value.finish()
                    self.assertFalse(result["passed"])
                    self.assertIn("transition trace",result["failures"][0])


def shared_records(kind):
    """Real shared evaluator shape: native setup, read, then completed queues."""
    from tools.overworld.devtools_records import select_current_actor
    def native(frame, **kwargs):
        row=snapshot(kind,frame,**kwargs)
        row.update(prepared=True,fieldAvailable=True,party=[])
        for actor in row["actors"]:
            actor.update(form=0,level=5)
            actor["sourceIdentity"].update(object_id=227,encounter_generation=1)
            actor["engineIdentity"].update(object_manager=0x022B2000,manager_index=3)
        return row
    initial=native(8);initial["actors"]=[]
    teleported=native(9);teleported["actors"]=[]
    def prepared(snapshot_value, events, sequences, value):
        return dict(preparedOnly=True,snapshot=deepcopy(snapshot_value),events=events,value=value,
                    setupBoundary=dict(eventsDrained=True,frame=snapshot_value["frame"],
                        nativeCycle=snapshot_value["nativeCycle"],endpointNativeCycle=snapshot_value["nativeCycle"],traceSequences=sequences))
    rows=[dict(phase="setup",initialSnapshot=initial),
          dict(phase="setup",action="surface-range",command="teleport",snapshot=teleported,
               receipt=prepared(teleported,[],{},{}))]
    spawned=native(10);actor=spawned["actors"][0];handle=actor["handle"]
    target=list(actor["target"].values());origin=list(actor["origin"].values())
    world=dict(spawned["context"],statePointer=0x022A0000,fieldPointer=0x022B1000)
    prefix=struct.pack("<iiB3xIHBB4hBB",*target,0,actor["subjectIdentity"],CONFIG[kind]["species"],0,5,*target,*origin,9,0).hex()
    common=dict(slot=3,terrain=0,statePointer=world["statePointer"],fieldPointer=world["fieldPointer"],
        preparedPointer=0x027E3900,worldContext=world,preparedPrefixHex=prefix,
        preparedEncounter=dict(species=CONFIG[kind]["species"],form=0,level=5,personality=actor["subjectIdentity"]),
        startup=dict(target=target,origin=origin,locomotion=9,hopDirection=0,targetBaseY=261456 if kind==ROOF else 230912),position=target)
    final=dict(common,sequence=1,returnValue=1,pairEligible=True,returnWorldContext=world,observation="spawn-finalized",setupMode="prepared")
    spawn=dict(common,sequence=2,returnValue=1,setupMode="prepared",observation="spawn-prepared",publicSubject=deepcopy(actor),finalization=dict(status="matched",receipt=final))
    events=[dict(frame=10,kind="native-observation",data=final),dict(frame=10,kind="native-observation",data=spawn),
            dict(frame=10,kind="native",data=dict(event="ACTOR_ATTACHED",traceStream=1,sequence=1,
                actorHandle=handle["value"],actor={k:v for k,v in handle.items() if k!="value"}))]
    rows.append(dict(phase="setup",action="spawn-surface-bird",command="spawn",snapshot=spawned,
        receipt=prepared(spawned,events,{"1":1},dict(slot=3,species=CONFIG[kind]["species"],personality=actor["subjectIdentity"]))))
    rows.append(dict(phase="setup",action="bind-real-bird",command="bind",snapshot=spawned,receipt=select_current_actor(spawned,actor)))
    rows.append(dict(phase="setup",action="read-actual-target-surface",command="terrain",snapshot=spawned,receipt=dict(terrain=surface(spawned,kind))))
    first=11
    def chunk(sample,events,phase,action):
        return dict(phase=phase,action=action,requestedGameFrames=1,completedGameFrames=1,nativeCycles=2,observedFieldFrames=1,
                    samples=[sample],events=events,cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=sample["frame"]-1),dict(cpuNs=1,wallNs=1,completedGameFrame=sample["frame"])])
    if kind==SIGN:
        rows.append(chunk(native(11,grounded=True),[],"setup","settle-on-signpost"));first=12
    for frame in range(first,first+4):
        events=transition_events(kind,frame) if frame==first else []
        for sequence,event in enumerate(events,2):event["data"].update(traceStream=1,sequence=sequence)
        rows.append(chunk(native(frame,rebound=True,grounded=True),events,"observe","cross-one-normal-step" if frame==first else "retain-surface-and-control"))
    return rows


class WildSurfaceRebindWiringTests(unittest.TestCase):
    def test_exact_terrain_factory_registration_and_input_are_shared(self):
        from tools.overworld.devtools_test_contract import TestEvaluator,validate_test
        from tools.overworld.devtools_test_inputs import measurement_inputs
        from tools.overworld.control import _shared_test_registration
        from tools.overworld.proof_adapters import get_adapter
        for kind in CONFIG:
            value=validate_test(recipe(kind));inputs=measurement_inputs(value,ROOT)
            self.assertEqual(inputs,{kind:dict(contractVersion=1)})
            evaluator=TestEvaluator(value);evaluator.install_measurements(inputs)
            self.assertIsInstance(evaluator.measurements[kind],WildSurfaceRebindMeasurement)
            registration,_=_shared_test_registration(value,ROOT)
            self.assertEqual(registration["evaluator"],kind)
            self.assertEqual(get_adapter(kind).requirement,CONFIG[kind]["requirement"])
            for wrong in (dict(CONFIG[kind]["terrainArgs"],radius=3),dict(CONFIG[kind]["terrainArgs"],x=1)):
                bad=recipe(kind)
                next(a for a in bad["setup"] if a["op"]=="terrain")["args"]=wrong
                with self.assertRaisesRegex(ValueError,"exact setup"):validate_test(bad)
            bad=recipe(kind);bad["id"]="world.transition.wild-invalidation"
            with self.assertRaisesRegex(ValueError,"terrain probe requires"):validate_test(bad)

    def test_controller_replays_current_rebound_and_all_copied_faults(self):
        from tools.overworld.control import _replay_shared_test
        from tools.overworld.proof_adapters import get_adapter
        for kind in CONFIG:
            rows=shared_records(kind)
            good=_replay_shared_test(recipe(kind),rows,repo=ROOT)
            self.assertTrue(good["passed"],good["failures"])
            self.assertEqual(good["subjects"][CONFIG[kind]["subject"]]["handle"]["fieldEpoch"],5)
            adapter=get_adapter(kind)
            for fault in adapter.faults:
                bad=_replay_shared_test(recipe(kind),rows,fault=fault,repo=ROOT)
                self.assertFalse(bad["passed"],fault)
                adapter.validate_negative_result(bad["measurements"][kind],fault)

    def test_prepared_watermarks_and_duplicate_reads_fail_closed(self):
        from tools.overworld.control import _replay_shared_test
        for kind in CONFIG:
            rows=shared_records(kind)
            bad=deepcopy(rows);bad[2]["receipt"]["setupBoundary"]["traceSequences"]={"1":2}
            result=_replay_shared_test(recipe(kind),bad,repo=ROOT)
            self.assertFalse(result["passed"])
            self.assertIn("watermark",str(result["failures"]))
            bad=deepcopy(rows);bad.insert(5,deepcopy(bad[4]))
            result=_replay_shared_test(recipe(kind),bad,repo=ROOT)
            self.assertFalse(result["passed"])
            self.assertIn("sealed setup",str(result["failures"]))
            bad=deepcopy(rows)
            spawn=next(e["data"] for e in bad[2]["receipt"]["events"] if e["data"].get("observation")=="spawn-prepared")
            spawn["preparedPrefixHex"]=spawn["finalization"]["receipt"]["preparedPrefixHex"]="00"
            result=_replay_shared_test(recipe(kind),bad,repo=ROOT)
            self.assertFalse(result["passed"])
            self.assertIn("prefix size",str(result["failures"]))


class SurfaceBoundaryPublicationTests(unittest.TestCase):
    def test_roof_canceled_kind_clears_on_exact_next_queue(self):
        for fault in (None,"trace","elapsed","reservation","second-queue"):
            with self.subTest(fault=fault):
                value=meter(ROOF)
                first=snapshot(ROOF,11,rebound=True,grounded=True)
                actor=first["actors"][0]
                actor.update(motionKind="FLY_IN",inputOwnership=0,
                             logical=deepcopy(actor["origin"]))
                events=transition_events(ROOF,11)
                events[0]["data"].update(valueA=6,valueB=0)
                if fault=="trace":events.pop(0)
                elif fault=="elapsed":actor["motionElapsed"]+=1
                elif fault=="reservation":actor["reservationId"]=12
                value.observe(first,events)
                if fault in (None,"second-queue"):
                    second=snapshot(ROOF,12,rebound=True,grounded=True)
                    if fault=="second-queue":second["actors"][0]["motionKind"]="FLY_IN"
                    value.observe(second,[])
                self.assertEqual(bool(value.failures),fault is not None,value.failures)
                if fault is None:self.assertEqual(value.ground_frames,2)

    def test_sign_commit_waits_only_one_queue_for_public_tile(self):
        for fault in (None,"missing-commit","wrong-commit","wrong-height","second-queue"):
            with self.subTest(fault=fault):
                value=meter(SIGN)
                first=snapshot(SIGN,11,grounded=True);actor=first["actors"][0]
                actor.update(logical=deepcopy(actor["origin"]),motionElapsed=144,commitSequence=1)
                events=[]
                for name,a,b in (("LOGICAL_COMMIT",1,6),("MOTION_FINISHED",1,6),("CONTROL_RETURNED",0,1)):
                    events.append(dict(frame=11,kind="native",data=dict(event=name,reason="OK",valueA=a,valueB=b,
                        actorHandle=actor["handle"]["value"],actor={k:v for k,v in actor["handle"].items() if k!="value"})))
                if fault=="missing-commit":events.pop(0)
                elif fault=="wrong-commit":events[0]["data"]["valueA"]=2
                elif fault=="wrong-height":actor["engineObject"]["pos_y"]+=16
                value.observe(first,events)
                if fault in (None,"second-queue"):
                    self.assertFalse(value.settled)
                    second=snapshot(SIGN,12,grounded=True)
                    if fault=="second-queue":second["actors"][0]["logical"]=deepcopy(second["actors"][0]["origin"])
                    value.observe(second,[])
                self.assertEqual(bool(value.failures),fault is not None,value.failures)
                if fault is None:self.assertTrue(value.settled)

    def test_sign_commit_requires_each_current_frame_and_full_handle(self):
        for terminal_index in range(3):
            for fault in ("missing", "stale-epoch", "wrong-frame"):
                with self.subTest(terminal_index=terminal_index, fault=fault):
                    value=meter(SIGN)
                    first=snapshot(SIGN,11,grounded=True);actor=first["actors"][0]
                    actor.update(logical=deepcopy(actor["origin"]),motionElapsed=144,commitSequence=1)
                    events=[]
                    for name,a,b in (("LOGICAL_COMMIT",1,6),("MOTION_FINISHED",1,6),("CONTROL_RETURNED",0,1)):
                        events.append(dict(frame=11,kind="native",data=dict(event=name,reason="OK",valueA=a,valueB=b,
                            actorHandle=actor["handle"]["value"],actor={k:v for k,v in actor["handle"].items() if k!="value"})))
                    if fault=="missing":events.pop(terminal_index)
                    elif fault=="stale-epoch":events[terminal_index]["data"]["actor"]["fieldEpoch"]-=1
                    elif fault=="wrong-frame":events[terminal_index]["frame"]-=1
                    value.observe(first,events)
                    self.assertIn("retained surface: signpost never committed its own target",value.failures)
                    self.assertIsNone(value.sign_commit_frame)
                    self.assertFalse(value.settled)


if __name__=="__main__":
    unittest.main()
