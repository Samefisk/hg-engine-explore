"""Copied moving-heal controls; native game acceptance remains separate."""
from copy import deepcopy
from pathlib import Path
import json
import struct
import sys
import unittest

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.overworld import devtools_player_health_moving_heal_measurement as leaf
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_player_health_moving_heal_proof import MovingHealNegative, faults, validate_negative_result
ROOT=Path(__file__).resolve().parents[2]
SOURCE = {"contractVersion": 1, "romSha256": "a"*64,
          "overlaySha256": "b"*64, "profileSha256": "c"*64}
CONTEXT = dict(fieldEpoch=3, mapGeneration=4, mapId=33)
FIELD = 0x022B125C


def actor(slot, species, role, x, z):
    handle = dict(value=(1<<16)|slot, slot=slot, generation=1,
                  fieldEpoch=3, mapGeneration=4, encounterGeneration=5)
    return dict(handle=handle, species=species, role=role, subjectIdentity=99+slot,
                authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1,
                form=0,level=5 if species==70 else 50 if species==155 else 10,
                active=True, identityVerified=True, presentationAttached=True,
                inputOwnership=1 if role=="MOUNTED" else 0,
                engineIdentity=dict(anchorInCurrentManager=role=="MOUNTED"),
                motionKind="NONE", motionPhase="IDLE", logical=dict(x=x,y=z),
                engineObject=pose(x,z), behaviorFingerprint=1234,
                matchedLayerMask=0)


def pose(x,z, *, command=12, y=0):
    return dict(x=x,y=z,pos_x=x*65536+32768,pos_y=y,pos_z=z*65536+32768,
                face_x=0,face_y=0,face_z=0,unk88_y=0,movement_cmd=command)


def snapshot(frame, mode, count=0):
    # A bounded east/west road loop. Every rendered move is a whole tile in
    # this copied positive fixture; live travel must come from actual poses.
    x=585+(count%4 if count%8<4 else 8-count%8)
    sample=dict(frame=frame,nativeCycle=frame+1000,actorFrame=frame+17,
                observationBoundary="main-task-queue-completion",fieldAvailable=True,
                romSha256=SOURCE["romSha256"],context=deepcopy(CONTEXT),
                fieldControl=dict(fieldPointer=FIELD,taskPointer=0),
                dialogue=dict(known=True,state="idle"),player=pose(x,407),
                actors=[actor(5,70,"WILD",585,402)],
                nativeObservation=dict(profileFingerprints=[1234]))
    if mode=="mounted":
        mount=actor(7,155,"MOUNTED",x,407)
        mount["motionKind"]="WALK";mount["motionPhase"]="MOVING"
        sample["actors"].append(mount)
        sample["player"]["face_y"]=32768
    return sample


def read(sample, action, hp, rest, rem, *, hits=1, damage=20, clock=None, hit=False):
    health=dict(schemaVersion=1,identity=dict(descriptorVersion=1,overlayId=161,
                        romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
                frame=sample["frame"],nativeCycle=sample["nativeCycle"],fieldSystem=FIELD,
                context=deepcopy(CONTEXT),hp=hp,savedHp=hp,maxHp=100,restFrames=rest,
                healRemainder=rem,acceptedHits=hits,lastDamage=damage,frameActive=False,
                recoveryPending=False,pause=dict(fieldTaskActive=False,healthClockPaused=False),
                lastHealthFrame=clock or sample["frame"]+100,hitThisFrame=hit,
                protectionFrames=60 if hit else 0,economy=dict(money=3000,bagSha256="d"*64),
                checkpointSpawn=1)
    return dict(phase="observe",action=action,command="player-health.observe",
                snapshot=deepcopy(sample),receipt=dict(playerHealth=health))


def raw(action, samples, profiles=None):
    row=dict(phase="observe",action=action,samples=samples,events=[],
             completedGameFrames=len(samples),observedFieldFrames=len(samples),nativeCycles=len(samples),
             cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=s["frame"]) for s in samples])
    if profiles is not None: row["profileCache"]=profiles
    return row


def spawn_receipt(sample, selected, locomotion):
    a=selected;x,z=a["logical"]["x"],a["logical"]["y"]
    raw=struct.pack("<iiB3xIHBB4hBB",x,z,0,a["subjectIdentity"],a["species"],0,a["level"],x,z,x,z,locomotion,0)
    world=sample["context"];encounter=dict(personality=a["subjectIdentity"],species=a["species"],form=0,level=a["level"])
    common=dict(slot=a["handle"]["slot"],terrain=0,statePointer=0x02140000,fieldPointer=FIELD,preparedPointer=0x02150000,
        worldContext=world,preparedPrefixHex=raw.hex(),preparedEncounter=encounter,
        startup=dict(target=[x,z],origin=[x,z],locomotion=locomotion,hopDirection=0,targetBaseY=0),position=[x,z],returnValue=1)
    final=dict(common,sequence=1,returnWorldContext=world,pairEligible=True)
    return dict(preparedOnly=True,value=dict(slot=a["handle"]["slot"],species=a["species"],personality=a["subjectIdentity"]),
        events=[dict(kind="native-observation",data=dict(common,sequence=2,observation="spawn-prepared",publicSubject=a,
                finalization=dict(status="matched",receipt=final)))])


def rows(mode):
    kind=leaf.FOOT if mode=="on-foot" else leaf.MOUNTED
    initial=snapshot(10,mode);initial["actors"]=[]
    stream=[dict(phase="setup",initialSnapshot=initial)];frame=10
    for name,op,args in leaf.setup(mode):
        if op=="step":
            frames=[snapshot(frame+i,mode) for i in range(1,17)]
            row=raw(name,frames);row["phase"]="setup";stream.append(row);frame+=16;continue
        frame+=1;sample=snapshot(frame,mode)
        if name.startswith("spawn-passive-"):
            selected=actor((69,43,44,45,182).index(args["species"]),args["species"],"WILD",args["x"],args["z"])
            sample["actors"].append(selected);receipt=spawn_receipt(sample,selected,7)
        elif name=="spawn-weepinbell":receipt=spawn_receipt(sample,sample["actors"][0],0)
        elif op=="bind":receipt=select_current_actor(sample,sample["actors"][0 if args["subject"]=="weepinbell" else 1])
        else:receipt=dict(preparedOnly=True)
        stream.append(dict(phase="setup",action=name,command=op,snapshot=sample,receipt=receipt))
    before=stream[-1]["snapshot"]
    stream.append(read(before,"before-contact",100,0,0,hits=0,damage=0))
    frame+=1;at=snapshot(frame,mode)
    attacker=at["actors"][0];attacker["motionKind"]="HOP";attacker["motionPhase"]="MOVING"
    attacker["engineObject"]=pose(585,407);attacker["matchedLayerMask"]=leaf.AMBUSH_BIT
    profile=bytearray(216);profile[72:75]=bytes((1,16,20));profile[79]=6
    cache=dict(frame=frame,nativeCycle=frame+1000,resolvedProfiles=[dict(resolved=True,fingerprint=1234,
        sourceSha256=SOURCE["profileSha256"],appliedOverrides=leaf.AMBUSH_BIT,resultHex=profile.hex())])
    stream.extend([raw("wait-contact",[at],cache),read(at,"at-contact",80,0,0,hit=True)])
    after=0
    for name,op,args in leaf.action_spec(kind)[3:]:
        if op=="step":
            frames=[snapshot(frame+i,mode,after+i) for i in range(1,args["frames"]+1)]
            stream.append(raw(name,frames));frame+=args["frames"];after+=args["frames"]
        else:
            _,elapsed,hp,wait,rem=next(c for c in leaf.CHECKPOINTS if c[0]==name)
            stream.append(read(stream[-1]["samples"][-1],name,hp,wait,rem))
    return stream


def evaluate(mode, change=None, fault=None):
    kind=leaf.FOOT if mode=="on-foot" else leaf.MOUNTED
    stream=rows(mode)
    if change is not None:change(stream)
    test=validate_test(json.loads((ROOT/("tests/overworld/test-recipes/player-hp.moving-heal-"+mode+".json")).read_text()))
    evaluator=TestEvaluator(test);evaluator.install_measurements({kind:SOURCE});callbacks=[]
    negative=MovingHealNegative(kind,fault) if fault else None
    for row in stream:
        if negative:row=negative.mutate(row,evaluator.subjects)
        result=evaluator.observe_record(row,frame_callback=lambda s,e:callbacks.append((s["frame"],e.frames)))
        if result["state"]=="failed":break
    done=evaluator.finish();result=done["measurements"][kind]
    return done,result,callbacks


def health_at(stream, action):
    return next(row["receipt"]["playerHealth"] for row in stream if row.get("action")==action)


class MovingHealLeafTest(unittest.TestCase):
    def test_named_recorder_controls_fail_in_actual_shared_dispatch(self):
        for mode in ("on-foot","mounted"):
            kind=leaf.FOOT if mode=="on-foot" else leaf.MOUNTED
            for fault in faults(kind):
                with self.subTest(mode=mode,fault=fault):
                    done,_,_=evaluate(mode,fault=fault)
                    validate_negative_result(kind,done,fault)

    def test_exact_recipe_rejects_post_hit_setup_wrong_keys_and_duration(self):
        original=json.loads((ROOT/"tests/overworld/test-recipes/player-hp.moving-heal-on-foot.json").read_text())
        for patch in (lambda t:t["actions"][3].update(op="teleport"),
                      lambda t:t["actions"][3]["args"].update(keys=[]),
                      lambda t:t["actions"][3]["args"].update(frames=19)):
            changed=deepcopy(original);patch(changed)
            with self.assertRaises(ValueError):validate_test(changed)

    def test_exact_delay_rate_and_normal_movement_in_both_roles(self):
        for mode in ("on-foot","mounted"):
            with self.subTest(mode=mode):
                done,result,callbacks=evaluate(mode)
                self.assertTrue(done["passed"],done["failures"])
                self.assertEqual((result["hpAfter"],result["eligibleHealthFrames"],result["observedFrames"]),(90,360,361))
                self.assertEqual(len([c for c in callbacks if c[1]>0]),361)
                self.assertGreaterEqual(result["movingFrames"]["first-heal"],3)

    def test_current_catalog_ambush_contact_and_adjacent_mask_control(self):
        catalog=json.loads((ROOT/"data/overworld_behavior_profiles.json").read_text())
        index=next(i for i,a in enumerate(catalog["applications"])
                   if a["id"]=="apply-ambush")
        current_mask=1<<index
        adjacent_mask=1<<((index-1)%32)
        def contact_mask(stream,mask):
            row=next(r for r in stream if r.get("action")=="wait-contact")
            row["samples"][0]["actors"][0]["matchedLayerMask"]=mask
            row["profileCache"]["resolvedProfiles"][0]["appliedOverrides"]=mask
        for mode in ("on-foot","mounted"):
            with self.subTest(mode=mode,mask="current-ambush"):
                done,_,_=evaluate(mode,lambda stream:contact_mask(stream,current_mask))
                self.assertTrue(done["passed"],done["failures"])
            with self.subTest(mode=mode,mask="adjacent-non-ambush"):
                done,_,_=evaluate(mode,lambda stream:contact_mask(stream,adjacent_mask))
                self.assertFalse(done["passed"])

    def test_old_moving_reset_and_wrong_heal_timing_are_rejected(self):
        faults={"old-movement-reset":("after-delay",{"restFrames":0}),
                "heal-at-delay-frame":("after-delay",{"hp":81,"savedHp":81}),
                "lost-fraction":("before-first-heal",{"healRemainder":0}),
                "wrong-rate":("after-one-second",{"hp":89,"savedHp":89}),
                "hidden-pause":("after-delay",{"lastHealthFrame":410}),
                "second-hit":("after-one-second",{"acceptedHits":2}),
                "stale-save":("first-heal",{"savedHp":80}),
                "wrong-owner":("first-heal",{"fieldSystem":FIELD+4})}
        for name,(action,patch) in faults.items():
            with self.subTest(name=name):
                done,_,_=evaluate("on-foot",lambda rows:health_at(rows,action).update(patch))
                self.assertFalse(done["passed"])

    def test_missing_natural_hit_or_profile_does_not_pass(self):
        def no_hit(stream):health_at(stream,"at-contact").update(hp=100,savedHp=100,acceptedHits=0)
        def no_profile(stream):next(r for r in stream if r.get("action")=="wait-contact")["profileCache"]["resolvedProfiles"]=[]
        for change in (no_hit,no_profile):
            done,_,_=evaluate("on-foot",change)
            self.assertFalse(done["passed"])

    def test_stationary_or_forced_jump_only_cannot_prove_moving_heal(self):
        def stationary(stream):
            for row in stream:
                if not row.get("action", "").startswith("move-"):continue
                for sample in row.get("samples",[]):sample["player"].update(pose(585,407))
                if "snapshot" in row:row["snapshot"]["player"].update(pose(585,407))
        def forced(stream):
            for row in stream:
                if not row.get("action", "").startswith("move-"):continue
                for sample in row.get("samples",[]):sample["player"]["movement_cmd"]=62
                if "snapshot" in row:row["snapshot"]["player"]["movement_cmd"]=62
        for change in (stationary,forced):
            done,_,_=evaluate("on-foot",change)
            self.assertFalse(done["passed"])

    def test_lost_mount_stale_generation_and_guest_setup_reject(self):
        def lost_mount(stream):next(r for r in stream if r.get("action")=="move-escape-north")["samples"][0]["actors"]=next(r for r in stream if r.get("action")=="move-escape-north")["samples"][0]["actors"][:1]
        def stale(stream):next(r for r in stream if r.get("action")=="move-escape-north")["samples"][0]["actors"][1]["handle"]["generation"]=2
        def split(stream):next(r for r in stream if r.get("action")=="move-escape-north")["samples"][0]["actors"][1]["engineObject"]["pos_x"]+=1
        for change in (lost_mount,stale,split):
            done,_,_=evaluate("mounted",change)
            self.assertFalse(done["passed"])
        done,_,_=evaluate("on-foot",lambda rows:next(r for r in rows if r.get("action")=="move-escape-north").update(command="teleport"))
        self.assertFalse(done["passed"])


if __name__=="__main__":unittest.main()
