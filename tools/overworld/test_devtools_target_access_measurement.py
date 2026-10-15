"""Focused controls for the shared native target access cases."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import sys
import unittest
if __package__ in (None, ""):sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_target_access_measurement import (
    KINDS, CASES, WINDOW, TargetAccessMeasurement, setup, actions, validate_recipe,
)
from tools.overworld.devtools_target_access_proof import (
    TargetAccessNegative, faults, measurements, validate_negative_result,
)
from tools.overworld.devtools_follower_throw_measurement import APPLICATION, APPLICATION_LOCAL, FOLLOWER, raw_handle
from tools.overworld.devtools_test_contract import validate_test, TestEvaluator, _wild_spawn_setup
from tools.overworld.devtools_walk_matrix_observer import decode_motion
from tools.overworld.proof_adapters import ADAPTERS
from tools.overworld.test_devtools_follower_throw_measurement import binding, profile
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

ROOT=Path(__file__).resolve().parents[2]
SOURCE=dict(contractVersion=1,romSha256="a"*64,overlaySha256="b"*64,profileSha256="c"*64)


def snapshot(frame,kind):
    raised=CASES[kind]["raised"]
    m=actor(56,7,107,398);m.update(role="FOLLOWER",level=20,inputOwnership=0,commitSequence=0,
        reservationId=0,matchedLayerMask=FOLLOWER|(0 if raised else 1<<APPLICATION_LOCAL),behaviorFingerprint=1000)
    t=actor(CASES[kind]["species"],0,700,CASES[kind]["target"][1])
    t.update(inputOwnership=0,commitSequence=0,reservationId=0,motionPhase="IDLE",motionKind="NONE")
    for a,x,z,y in ((m,580,398,65536),(t,*CASES[kind]["target"],230912 if raised else 65536)):
        for f in ("logical","render","origin","target"):a[f]=dict(x=x,y=z)
        a["engineObject"]=dict(x=x,y=z,pos_x=(x<<16)+32768,pos_z=(z<<16)+32768,pos_y=y,
            face_y=0,unk88_y=0,facing=0)
    raw=bytearray(52)
    if raised and frame>=9:
        origin,target=(580,398),(580,399);elapsed=min(7,frame-9)
        logical=origin if frame<16 else target
        phase=2 if frame<16 else 4 if frame<21 else 0
        m.update(origin=dict(zip(("x","y"),origin)),target=dict(zip(("x","y"),target)),
            logical=dict(zip(("x","y"),logical)),motionKind="HOP" if phase else "NONE",
            motionPhase=("MOVING" if phase==2 else "SETTLING" if phase==4 else "IDLE"),
            reservationId=21 if phase==2 else 0,motionElapsed=elapsed,motionDuration=7,commitSequence=int(frame>=16))
        m["engineObject"].update(x=logical[0],y=logical[1],pos_z=(398<<16)+32768+65536*elapsed//7,
            unk88_y=16384 if 0<elapsed<7 else 0)
        struct.pack_into("<HBBHH4h2iHH",raw,0,1,2,1,1,1000,*origin,*target,65536,65536,7,21)
        raw[28:38]=bytes((1,1,16,0,0,0,5,1,0,0))
        struct.pack_into("<4H4B",raw,40,elapsed,max(0,21-frame) if phase==4 else 0,0,0,phase,0,int(frame>=16),0)
    trigger=binding(t if not raised else None,12365,APPLICATION_LOCAL);cargo=binding(None,26783)
    state_raw=bytearray(16)
    if not raised:
        struct.pack_into("<3H",state_raw,8,*(t["handle"][k] for k in ("slot","generation","encounterGeneration")))
        state_raw[14:16]=bytes((2,1))
    prepared=bytearray(88);prepared[:12]=raw_handle(m["handle"])
    struct.pack_into("<I",prepared,12,0x2201000)
    struct.pack_into("<H",prepared,16,4)
    struct.pack_into("<BBHH",prepared,80,1,1,1,56)
    capture=dict(preparedIndex=0,catalogIndex=4,conditionId=12365,application=APPLICATION,
        applicationLocal=APPLICATION_LOCAL,statesPointer=0x2201000,activationMode=0,
        durationFrames=0,cooldownFrames=0,activeUntil=0,cooldownUntil=0,flags=state_raw[15],
        target=deepcopy(trigger["target"]),targetCurrent=not raised,rawHex=state_raw.hex(),preparedRawHex=prepared.hex())
    carrier=dict(slot=7,handle=deepcopy(m["handle"]),role="FOLLOWER",available=True,
        bindings=dict(trigger=trigger,cargo=cargo),rawBindingsHex=(raw_handle(m["handle"])
            +bytes.fromhex(trigger["rawHex"])+bytes.fromhex(cargo["rawHex"])).hex(),conditionCaptures=[capture],
        throw=dict(targetRaw=0,targetSlot=None,carried=False,windup=False,targeted=False,carrier=False,recovering=False))
    context=dict(mapId=33,fieldEpoch=1,mapGeneration=1)
    cell=dict(x=CASES[kind]["target"][0],z=CASES[kind]["target"][1],loaded=True,collision=raised,
        provenance=dict(mapHeaderId=33,fieldPointer=0x2200000,chunkModelLoaded=1),
        surface=dict(known=True,present=raised,type="signpost" if raised else None,surfaceId=9313 if raised else 0,
            heightMode="absolute",finalHeightKnown=True,heightFx32=230912 if raised else 65536))
    return dict(frame=frame,nativeCycle=1000+frame,actorFrame=frame,fieldAvailable=True,romSha256=SOURCE["romSha256"],
        observationBoundary="main-task-queue-completion",fieldControl=dict(fieldPointer=0x2200000,taskPointer=0),
        context=context,actors=[m,t],player=dict(x=580,y=397),
        pokemonCombat=dict(available=True,frame=frame,nativeCycle=1000+frame,
            identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
            targets=[dict(handle=m["handle"],role="FOLLOWER",motion=decode_motion(bytes(raw)))],
            interactions=dict(schemaVersion=1,available=True,frame=frame,nativeCycle=1000+frame,
                observationBoundary="main-task-queue-completion",fieldSystem=0x2200000,
                identity=dict(romSha256=SOURCE["romSha256"]),carriers=[carrier],
                throwState=dict(targets=[0]*10,targetMask=0,carrierMask=0,recoveringMask=0,rawHex=bytes(16).hex()))),
        terrain=dict(observation=dict(nativeCycle=1000+frame,lastCompletedGameFrame=frame,context=context),cells=[cell]))


def events(s):
    m=s["actors"][0];p=profile(m["matchedLayerMask"],m["behaviorFingerprint"])
    data=bytearray.fromhex(p["resultHex"]);struct.pack_into("<H",data,32,0x45)
    p.update(resultHex=data.hex(),lanes=[data[:80].hex(),data[80:160].hex()])
    result=[dict(frame=s["frame"],kind="native-observation",data=p)]
    names=([("MOTION_STARTED",2,7)] if s["frame"]==9 else [("LOGICAL_COMMIT",1,2)]
        if s["frame"]==16 else [("MOTION_FINISHED",1,2),("CONTROL_RETURNED",0,1)] if s["frame"]==21 else [])
    for n,a,b in names:
        result.append(dict(frame=s["frame"],kind="native",data=dict(event=n,valueA=a,valueB=b,
            actorHandle=m["handle"]["value"],actor={k:v for k,v in m["handle"].items() if k!="value"},
            sequence=s["frame"]*10+len(result))))
    return result


def seeded(kind,control=None):
    meter=TargetAccessMeasurement(SOURCE,kind);s=snapshot(0,kind)
    meter.subjects={n:select_current_actor(s,a) for n,a in zip(("mankey","target"),s["actors"])}
    meter.latest=deepcopy(s);meter.setup_index=len(setup(kind))
    terrainrow=dict(phase="setup",command="terrain",snapshot=s)
    if control:terrainrow=control.mutate(terrainrow,meter.subjects)
    try:meter._terrain(terrainrow["snapshot"])
    except ValueError as error:meter.failures.append(str(error))
    return meter


def before_target_settle(kind):
    meter=TargetAccessMeasurement(SOURCE,kind);s=snapshot(0,kind)
    meter.subjects["target"]=select_current_actor(s,s["actors"][1])
    meter.latest=deepcopy(s)
    meter.setup_index=next(i for i,a in enumerate(setup(kind)) if a[0]=="settle-target")
    return meter,s


def run(kind,control=None):
    meter=seeded(kind,control)
    for frame in range(1,22 if CASES[kind]["raised"] else WINDOW+1):
        if meter.failures:break
        row=dict(phase="observe",samples=[snapshot(frame,kind)],events=events(snapshot(frame,kind)))
        if control:row=control.mutate(row,meter.subjects)
        try:meter._sample(row["samples"][0],row["events"])
        except (ValueError,KeyError,TypeError,StopIteration,struct.error) as error:meter.failures.append(str(error))
    return meter.finish()


def fly_in_spawn():
    """A matched native Fly In starts offscreen above its raised destination."""
    sample = snapshot(0, KINDS[0]); target = sample["actors"][1]
    destination, origin, base_y = [581,397], [581,413], 230912
    target.update(motionKind="FLY_IN", motionPhase="MOVING", motionElapsed=2,
        motionDuration=144, reservationId=10,
        logical=dict(zip(("x","y"),origin)), origin=dict(zip(("x","y"),origin)),
        target=dict(zip(("x","y"),destination)))
    raw = bytearray(52)
    struct.pack_into("<HBBHH4h2iHH",raw,0,1,6,0,1,1000,*origin,*destination,
        base_y+6*65536,base_y,144,10)
    raw[28:38]=bytes((0,16,0,0,0,0,0,0,2,0))
    struct.pack_into("<4H4B",raw,40,2,0,0,0,2,0,0,0)
    sample["pokemonCombat"]["targets"].append(dict(handle=deepcopy(target["handle"]),
        motion=decode_motion(bytes(raw))))
    encounter={k:target[k] for k in ("species","form","level")}
    encounter["personality"]=target["subjectIdentity"]
    world=dict(sample["context"],statePointer=0x02040000,fieldPointer=0x02200000)
    common=dict(slot=0,terrain=0,statePointer=world["statePointer"],fieldPointer=world["fieldPointer"],
        preparedPointer=0x02060000,worldContext=world,preparedEncounter=encounter,
        position=destination,returnValue=1,
        preparedPrefixHex=struct.pack("<iiB3xIHBB4hBB",*destination,0,
            encounter["personality"],encounter["species"],encounter["form"],encounter["level"],
            *destination,*origin,9,0).hex(),
        startupHex=struct.pack("<4hBB2xi",*destination,*origin,9,0,base_y).hex(),
        startup=dict(target=destination,origin=origin,locomotion=9,hopDirection=0,targetBaseY=base_y))
    final=dict(deepcopy(common),sequence=1,pairEligible=True,returnWorldContext=deepcopy(world))
    native=dict(common,observation="spawn-prepared",sequence=2,publicSubject=deepcopy(target),
        finalization=dict(status="matched",receipt=final))
    receipt=dict(value=dict(slot=0,species=16,personality=target["subjectIdentity"]),
        events=[dict(frame=0,kind="native-observation",data=native)])
    return receipt,sample


class TargetAccessHostTests(unittest.TestCase):
    def test_settled_target_wait_may_be_skipped_or_executed(self):
        for kind in KINDS:
            with self.subTest(kind=kind,wait="skipped"):
                meter,s=before_target_settle(kind);index=meter.setup_index
                result=meter.observe_record(dict(phase="setup",action="read-target-terrain",
                    command="terrain",snapshot=s))
                self.assertEqual(result["failures"],[])
                self.assertEqual(meter.setup_index,index+2)
                self.assertEqual(meter.terrain["target"]["handle"],s["actors"][1]["handle"])
            with self.subTest(kind=kind,wait="executed"):
                meter,_=before_target_settle(kind);index=meter.setup_index;s=snapshot(1,kind)
                row=dict(phase="setup",action="settle-target",samples=[s],events=events(s),
                    completedGameFrames=1,nativeCycles=1,observedFieldFrames=1,
                    cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=1)])
                self.assertEqual(meter.observe_record(row)["failures"],[])
                self.assertEqual(meter.setup_index,index+1)
                self.assertEqual(meter.observe_record(dict(phase="setup",action="read-target-terrain",
                    command="terrain",snapshot=s))["failures"],[])
                self.assertEqual(meter.setup_index,index+2)

    def test_skipped_wait_needs_the_last_full_target_to_be_settled(self):
        for kind in KINDS:
            for fault in ("moving","reservation","offset","tile","owner","identity"):
                with self.subTest(kind=kind,fault=fault):
                    meter,s=before_target_settle(kind);index=meter.setup_index
                    target=meter.latest["actors"][1]
                    if fault=="moving":target["motionPhase"]="MOVING"
                    elif fault=="reservation":target["reservationId"]=10
                    elif fault=="offset":target["engineObject"]["unk88_y"]=1
                    elif fault=="tile":target["logical"]["x"]+=1
                    elif fault=="owner":target["handle"]["generation"]+=1
                    else:target["identityVerified"]=False
                    result=meter.observe_record(dict(phase="setup",action="read-target-terrain",
                        command="terrain",snapshot=s))
                    self.assertTrue(result["failures"])
                    self.assertEqual(meter.setup_index,index)
                    self.assertIsNone(meter.terrain)

    def test_skipped_wait_still_rechecks_incoming_target_and_terrain(self):
        for kind in KINDS:
            for fault in ("owner","tile","offset","clock","foreign-terrain"):
                with self.subTest(kind=kind,fault=fault):
                    meter,s=before_target_settle(kind);target=s["actors"][1]
                    if fault=="owner":target["handle"]["generation"]+=1
                    elif fault=="tile":target["logical"]["x"]+=1
                    elif fault=="offset":target["engineObject"]["unk88_y"]=1
                    elif fault=="clock":s["terrain"]["observation"]["lastCompletedGameFrame"]+=1
                    else:s["terrain"]["cells"][0]["provenance"]["fieldPointer"]+=4
                    result=meter.observe_record(dict(phase="setup",action="read-target-terrain",
                        command="terrain",snapshot=s))
                    self.assertTrue(result["failures"])
                    self.assertIsNone(meter.terrain)
        meter,s=before_target_settle(KINDS[1]);index=meter.setup_index
        result=meter.observe_record(dict(phase="setup",action="prepare-mankey",command="party",snapshot=s))
        self.assertEqual(result["failures"],["target access action order differs"])
        self.assertEqual(meter.setup_index,index)

    def test_fly_in_spawn_has_its_exact_native_origin_height_and_plan(self):
        receipt,sample=fly_in_spawn()
        result=_wild_spawn_setup(receipt,sample,species=16,locomotion=9)
        self.assertEqual(result["destination"],[581,397])
        self.assertEqual(result["subject"]["handle"],sample["actors"][1]["handle"])

    def test_fly_in_spawn_rejects_copied_startup_owner_and_plan_faults(self):
        for fault in ("paired-startup","raw-startup","plan-height","plan-origin","plan-reservation",
                      "plan-owner","missing-plan","actor-phase","logical-origin"):
            with self.subTest(fault=fault):
                receipt,sample=fly_in_spawn();spawn=receipt["events"][0]["data"]
                motion=sample["pokemonCombat"]["targets"][-1]
                if fault=="paired-startup":spawn["finalization"]["receipt"]["startupHex"]=bytes(16).hex()
                elif fault=="raw-startup":
                    spawn["startupHex"]=spawn["finalization"]["receipt"]["startupHex"]=bytes(16).hex()
                elif fault=="missing-plan":sample["pokemonCombat"]["targets"].pop()
                elif fault=="plan-owner":motion["handle"]["generation"]+=1
                elif fault=="actor-phase":sample["actors"][1]["motionPhase"]="SETTLING"
                elif fault=="logical-origin":sample["actors"][1]["logical"]["y"]-=1
                else:
                    raw=bytearray.fromhex(motion["motion"]["rawHex"])
                    offset={"plan-height":20,"plan-origin":8,"plan-reservation":26}[fault]
                    raw[offset]^=1;motion["motion"]=decode_motion(bytes(raw))
                with self.assertRaises(ValueError):_wild_spawn_setup(receipt,sample,species=16,locomotion=9)

    def test_fly_in_admission_does_not_change_old_walk_startup_rules(self):
        for locomotion in (0,3,7):
            receipt,sample=fly_in_spawn()
            with self.subTest(locomotion=locomotion),self.assertRaises(ValueError):
                _wild_spawn_setup(receipt,sample,species=16,locomotion=locomotion)

    def test_exact_normal_raw_queues_and_counter_fail_closed(self):
        for kind in KINDS:
            meter=seeded(kind);callbacks=[]
            for frame in range(1,22 if CASES[kind]["raised"] else WINDOW+1):
                s=snapshot(frame,kind)
                if CASES[kind]["raised"] and frame>=9:s["player"]["y"]=398
                row=dict(phase="observe",action=actions(kind)[meter.action_index][0],samples=[s],events=events(s),
                    completedGameFrames=1,nativeCycles=1,observedFieldFrames=1,
                    cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=frame)])
                result=meter.observe_record(row,on_sample=lambda sample,count:callbacks.append((sample["frame"],count)))
                self.assertEqual(result["failures"],[])
            self.assertTrue(meter.finish()["passed"])
            self.assertEqual(callbacks,[(f,f) for f in range(1,meter.observed_frames+1)])
            meter=seeded(kind);s=snapshot(1,kind)
            row=dict(phase="observe",action=actions(kind)[0][0],samples=[s],events=events(s),
                completedGameFrames=2,nativeCycles=1,observedFieldFrames=1,
                cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=1)])
            self.assertIn("raw chunk has missing samples",meter.observe_record(row)["failures"][0])
            self.assertEqual(meter.observed_frames,0)

    def test_exact_registered_native_recipes_and_inputs(self):
        for kind in KINDS:
            recipe=validate_test(json.loads((ROOT/"tests/overworld/test-recipes"/(CASES[kind]["id"]+".json")).read_text()))
            validate_recipe(recipe)
            evaluator=TestEvaluator(recipe);evaluator.install_measurements({kind:SOURCE})
            self.assertTrue(evaluator.uses_raw_records)
            self.assertEqual(ADAPTERS[kind].requirement,recipe["requirements"][0])
            ids=[a["id"] for a in recipe["setup"]]
            if not CASES[kind]["raised"]:
                self.assertLess(ids.index("settle-passive"),ids.index("spawn-target"))
                self.assertLess(ids.index("bind-mankey"),ids.index("spawn-target"))
                self.assertEqual(ids[-4:],["spawn-target","bind-target","settle-target","read-target-terrain"])
                wrong=deepcopy(recipe)
                follower=wrong["setup"].pop(ids.index("create-mankey"))
                wrong["setup"].append(follower)
                with self.assertRaisesRegex(ValueError,"fixed native fixture differs"):validate_recipe(wrong)
            changed=deepcopy(recipe);changed["setup"][ids.index("spawn-target")]["args"]["species"]=74
            with self.assertRaises(ValueError):validate_recipe(changed)

    def test_both_finite_controls_and_named_copied_faults(self):
        for kind in KINDS:
            result=run(kind);self.assertTrue(result["passed"],result["failures"])
            replay=dict(passed=True,failures=[],observedFrames=result["observedFrames"],measurements={kind:result})
            proof=measurements(kind,replay,dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[])))
            self.assertEqual(len(proof),5 if CASES[kind]["raised"] else 4)
            for fault in faults(kind):
                control=TargetAccessNegative(kind,fault);rejected=run(kind,control)
                self.assertTrue(control.applied,fault);self.assertFalse(rejected["passed"],fault)
                validate_negative_result(kind,dict(passed=False,measurements={kind:rejected}),fault)

    def test_missing_or_foreign_native_surface_never_earns_rejection(self):
        for kind in KINDS:
            for mutation in (lambda s:s["terrain"]["cells"][0].update(loaded=False),
                lambda s:s["terrain"]["cells"][0]["provenance"].update(fieldPointer=0x2300000),
                lambda s:s["terrain"]["observation"].update(lastCompletedGameFrame=9)):
                meter=TargetAccessMeasurement(SOURCE,kind);s=snapshot(0,kind)
                meter.subjects={n:select_current_actor(s,a) for n,a in zip(("mankey","target"),s["actors"])}
                mutation(s)
                with self.assertRaises(ValueError):meter._terrain(s)

    def test_unknown_condition_owner_and_surface_permission_reject(self):
        kind=KINDS[0]
        meter=seeded(kind);s=snapshot(1,kind)
        # A retained old-format record must not masquerade as PreparedActor88.
        s["pokemonCombat"]["interactions"]["carriers"][0]["conditionCaptures"][0]["preparedRawHex"]=bytes(52).hex()
        with self.assertRaisesRegex(ValueError,"full owner differ"):meter._sample(s,events(s))
        meter=seeded(kind);s=snapshot(1,kind);observations=events(s)
        p=observations[0]["data"];data=bytearray.fromhex(p["resultHex"])
        struct.pack_into("<H",data,32,1|0x80)
        p.update(resultHex=data.hex(),lanes=[data[:80].hex(),data[80:160].hex()])
        with self.assertRaisesRegex(ValueError,"permits actual Signpost"):meter._sample(s,observations)

    def test_current_prepared_owner_species_and_u16_catalog_index(self):
        for fault in ("old-format","full-handle","species-bank","catalog-high-byte",
                      "states-pointer","missing-valid","wrong-capacity","invalid-damage-pending2","invalid-damage-pending65535"):
            with self.subTest(fault=fault):
                kind=KINDS[1];meter=seeded(kind);s=snapshot(1,kind)
                carrier=s["pokemonCombat"]["interactions"]["carriers"][0]
                capture=carrier["conditionCaptures"][0]
                prepared=bytearray.fromhex(capture["preparedRawHex"])
                if fault=="old-format":prepared=prepared[:52]
                elif fault=="full-handle":prepared[2]^=1
                elif fault=="species-bank":struct.pack_into("<H",prepared,84,35)
                elif fault=="catalog-high-byte":prepared[17]=1
                elif fault=="states-pointer":prepared[12]^=4
                elif fault=="missing-valid":prepared[81]=0
                elif fault=="wrong-capacity":prepared[82]=0
                else:struct.pack_into("<H",prepared,86,2 if fault=="invalid-damage-pending2" else 65535)
                capture["preparedRawHex"]=prepared.hex()
                with self.assertRaisesRegex(ValueError,"full owner differ"):
                    meter._condition(carrier,s["actors"][0])

    def test_current_prepared_subject_damage_pending_is_boolean(self):
        for pending in (0,1):
            with self.subTest(pending=pending):
                kind=KINDS[1];meter=seeded(kind);s=snapshot(1,kind)
                carrier=s["pokemonCombat"]["interactions"]["carriers"][0]
                capture=carrier["conditionCaptures"][0]
                prepared=bytearray.fromhex(capture["preparedRawHex"])
                struct.pack_into("<H",prepared,86,pending)
                capture["preparedRawHex"]=prepared.hex()
                meter._condition(carrier,s["actors"][0])

    def test_old_global_throw_mask_and_binding_source_do_not_grant_notice(self):
        kind=KINDS[1]
        meter=seeded(kind);s=snapshot(1,kind)
        mankey=s["actors"][0]
        mankey["matchedLayerMask"]=FOLLOWER|(1<<APPLICATION)
        with self.assertRaisesRegex(ValueError,"exact current Notice capture"):
            meter._sample(s,events(s))
        meter=seeded(kind);s=snapshot(1,kind)
        carrier=s["pokemonCombat"]["interactions"]["carriers"][0]
        bound=carrier["bindings"]["trigger"]
        raw=bytearray.fromhex(bound["rawHex"]);raw[20]=APPLICATION
        bound["sourceApplicationLocal"]=APPLICATION;bound["rawHex"]=raw.hex()
        carrier["rawBindingsHex"]=(raw_handle(s["actors"][0]["handle"])+raw+
            bytes.fromhex(carrier["bindings"]["cargo"]["rawHex"])).hex()
        with self.assertRaisesRegex(ValueError,"exact current Notice capture"):
            meter._sample(s,events(s))
        meter=seeded(kind);s=snapshot(1,kind)
        s["pokemonCombat"]["interactions"]["carriers"][0]["bindings"]["trigger"]["sourceApplication"]=APPLICATION-1
        with self.assertRaisesRegex(ValueError,"exact current Notice capture"):
            meter._sample(s,events(s))

    def test_ground_target_requires_land_permission_even_with_other_surfaces(self):
        kind=KINDS[1];meter=seeded(kind);s=snapshot(1,kind);observations=events(s)
        p=observations[0]["data"];data=bytearray.fromhex(p["resultHex"])
        struct.pack_into("<H",data,32,0x44)
        p.update(resultHex=data.hex(),lanes=[data[:80].hex(),data[80:160].hex()])
        with self.assertRaisesRegex(ValueError,"cannot reach actual LAND"):meter._sample(s,observations)

    def test_proof_rejects_a_wrong_permission_for_the_actual_target(self):
        for kind in KINDS:
            result=run(kind)
            witness=(result["visibleWitnesses"][0] if CASES[kind]["raised"] else result["noticeWitness"])
            witness["allowedTerrainMask"]=(0xC5 if CASES[kind]["raised"] else 0x44)
            p=witness["profile"];data=bytearray.fromhex(p["resultHex"])
            struct.pack_into("<H",data,32,witness["allowedTerrainMask"])
            p.update(resultHex=data.hex(),lanes=[data[:80].hex(),data[80:160].hex()])
            replay=dict(passed=True,failures=[],observedFrames=result["observedFrames"],measurements={kind:result})
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,"actual target permission"):
                measurements(kind,replay,dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[])))


if __name__=="__main__":unittest.main()
