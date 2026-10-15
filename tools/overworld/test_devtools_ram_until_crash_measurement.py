"""Copied recorder controls and typed routing; these are not game proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import struct
import hashlib
from types import SimpleNamespace
import textwrap

from tools.overworld.devtools_ram_until_crash_measurement import (
    RamUntilCrashMeasurement, KIND, BEHIND, RAM_MASK, APPLICATION, CONDITION,
)
from tools.overworld.devtools_ram_until_crash_proof import (
    RamUntilCrashNegative, RamFeatureNegative, FAULTS, measurements, validate_negative_result,
)
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.test_devtools_player_health_ram_rest_measurement import ONIX

ROOT = Path(__file__).resolve().parents[2]


def fixture(charge_walks=14, *, east=False):
    crash_frame = 100 + charge_walks * 10
    samples, events = [], []
    for frame in range(98, crash_frame + 17):
        actor = deepcopy(ONIX)
        actor.update(motionKind="NONE", motionPhase="IDLE", motionElapsed=0, motionDuration=0,
                     behaviorFingerprint=123456, matchedLayerMask=RAM_MASK if 100 <= frame <= crash_frame else 0,
                     inputOwnership=0, reservationId=0)
        completed = max(0, min(charge_walks, (frame-99)//10))
        y = 412-completed
        actor.update(origin={"x":585,"y":y},target={"x":585,"y":y},
                     logical={"x":585,"y":y},commitSequence=completed)
        engine = {"pos_x":(585<<16)+0x8000,"pos_y":0,"pos_z":(y<<16)+0x8000,
                  "unk88_y":0,"facing":0,"flags":0,"movement_cmd":255}
        for index in range(charge_walks):
            start, origin = 100+index*10, 412-index
            if start <= frame <= start+8:
                elapsed = frame-start
                actor.update(motionKind="WALK",motionPhase="MOVING" if elapsed<8 else "COMMIT_PENDING",
                             motionElapsed=elapsed,motionDuration=8,commitSequence=index,
                             origin={"x":585,"y":origin},target={"x":585,"y":origin-1},
                             logical={"x":585,"y":origin},inputOwnership=1,reservationId=index+1)
                engine["pos_z"] = (origin<<16)+0x8000-elapsed*8192
        actor["engineObject"] = engine
        sample = {"frame":frame,"actorFrame":frame,"nativeCycle":frame+1000,
                  "context":{"mapId":33,"fieldEpoch":1,"mapGeneration":1},
                  "player":{"x":585 if frame<105 else 587,"y":407,"facing":3},"actors":[actor]}
        samples.append(sample)
        def native(name,a=0,b=0,reason=0):
            events.append({"kind":"native","frame":frame,"data":{
                "actorHandle":actor["handle"]["value"],"actorFrame":frame,
                "event":name,"valueA":a,"valueB":b,"reasonId":reason,
                "sequence":len(events)+1, "actor":{k:v for k,v in actor["handle"].items() if k!="value"}}})
        if frame == 100 or frame in range(110, crash_frame, 10):
            reason = APPLICATION | (APPLICATION<<5) | (1<<10) | (1<<14)
            if frame == 100: reason |= (1<<12) | (1<<13)
            native("CONDITIONAL_RESOLVED",CONDITION | (1<<31),0,reason)
        if frame in range(100,crash_frame,10):
            native("MOTION_STARTED",1,8)
            request = bytearray(28)
            request[:4] = b"\x01\x00\x1c\x00";request[9]=1;request[11]=1
            response=bytearray(request);response[16]=2;response[19]=8
            before=bytearray(36);before[2]=before[25]=8;before[3]=16
            events.append({"kind":"native-observation","frame":frame,"data":{
                "observation":"walk-policy","slot":0,"operation":1,"returnValue":1,
                "publicSubject":deepcopy(actor),"publicSubjectAfter":deepcopy(actor),
                "requestHex":request.hex(),"responseHex":response.hex(),"policyBeforeHex":before.hex()}})
        if frame in range(109,crash_frame,10):
            native("LOGICAL_COMMIT",actor["commitSequence"],1)
            native("MOTION_FINISHED",actor["commitSequence"],1)
            native("CONTROL_RETURNED",0,actor["commitSequence"])
        if frame == crash_frame: native("WORLD_EFFECT",3,14)
        add_native_condition_state(sample, actor, frame, crash_frame)
    if east:
        def rotate(actor):
            for key in ("origin","target","logical"):
                old=actor[key];actor[key]={"x":602+412-old["y"],"y":402}
            engine=actor["engineObject"]
            engine["pos_x"]=(602+412)*65536+65536-engine["pos_z"]
            engine["pos_z"]=(402<<16)+0x8000;engine["facing"]=3
        for sample in samples:
            rotate(sample["actors"][0]);rotate(sample["pokemonAppearance"]["conditions"]["0"]["owner"]["actor"])
            sample["player"].update(x=607,y=402 if sample["frame"]<105 else 404)
        for sample in samples:
            if sample['frame']<100:sample['actors'][0]['engineObject']['facing']=1
        for event in events:
            if event["kind"] != "native-observation":continue
            data=event["data"]
            for key in ("publicSubject","publicSubjectAfter"):rotate(data[key])
            response=bytearray.fromhex(data["responseHex"]);response[17]=3;data["responseHex"]=response.hex()
    return {"samples":samples,"events":events}


def behind_fixture(charge_walks=14):
    row=fixture(charge_walks)
    def translate(a):
        for k in ('origin','target','logical'):
            a[k]['x']+=9;a[k]['y']-=8
        e=a['engineObject'];e['pos_x']+=9*65536;e['pos_z']-=8*65536
    for sample in row['samples']:
        a=sample['actors'][0];translate(a)
        passive=deepcopy(ONIX)
        passive.update(species=155,role='FOLLOWER',level=20,subjectIdentity=456,matchedLayerMask=0)
        passive['handle'].update(value=0x10007,slot=7)
        sample['actors'].append(passive)
        sample['pokemonCombat']={'targets':[{'handle':deepcopy(passive['handle']),
            'role':'FOLLOWER','hpMirrorMatches':True,'hp':50,'maxHp':50}]}
        if sample['frame']<100:a['engineObject']['facing']=1
        translate(sample['pokemonAppearance']['conditions']['0']['owner']['actor'])
        sample['player']['x']+=9;sample['player']['y']-=8
    for event in row['events']:
        if event['kind']=='native-observation':
            for key in ('publicSubject','publicSubjectAfter'):translate(event['data'][key])
    return row


def crash_terminal_fixture():
    row = fixture()
    old_crash, crash, start = 240, 239, 230
    for sample in row["samples"]:
        frame, actor = sample["frame"], sample["actors"][0]
        if start <= frame < crash:
            actor.update(motionPhase="MOVING", motionDuration=9, motionElapsed=frame-start)
            actor["engineObject"]["pos_z"] = (399<<16)+0x8000-(frame-start)*65536//9
        if frame == crash:
            actor.update(motionElapsed=9, motionDuration=9,
                         origin={"x":585,"y":399}, target={"x":585,"y":398})
            actor["engineObject"]["pos_x"] -= 256
            actor["engineObject"]["pos_z"] += 256
        if frame >= crash:
            actor["matchedLayerMask"] = RAM_MASK if frame == crash else 0
        add_native_condition_state(sample, actor, frame, crash)
    for event in row["events"]:
        data = event["data"]
        if event["frame"] == old_crash and data.get("event") == "WORLD_EFFECT":
            event["frame"] = crash; data["actorFrame"] = crash
            # Commit/finish/control in this queue must precede Crash.
        if event["frame"] == start:
            if data.get("event") == "MOTION_STARTED": data["valueB"] = 9
            if event["kind"] == "native-observation":
                response=bytearray.fromhex(data["responseHex"]);response[19]=9;data["responseHex"]=response.hex()
                before=bytearray.fromhex(data["policyBeforeHex"]);before[2]=before[25]=9;data["policyBeforeHex"]=before.hex()
    return row


def add_native_condition_state(sample, actor, frame, crash_frame):
    # Reuse the real prepared-state decoder. This is copied host data, not native proof.
    from tools.overworld.devtools_appearance_observer import decode_conditions, HANDLE_KEYS
    blob=(ROOT/"build/OverworldWildBehaviorData.bin").read_bytes()
    offset,count,stride=struct.unpack_from("<IHH",blob,52)
    indices=[i for i in range(count) if struct.unpack_from("<H",blob,offset+i*stride+32)[0]==CONDITION
             and blob[offset+i*stride+34]==APPLICATION]
    assert len(indices)==1
    prepared=bytearray(52)
    struct.pack_into("<6H",prepared,0,*[actor["handle"][k] for k in HANDLE_KEYS],0)
    struct.pack_into("<I",prepared,12,0x022B1000)
    prepared[16]=indices[0];struct.pack_into("<BBH",prepared,48,1,1,32)
    flags=0 if frame<100 else 11 if frame<crash_frame else 13 if frame==crash_frame else 26
    state=struct.pack("<II3H2B",0,crash_frame+101 if frame>crash_frame else 0,0xffff,0,0,
                      1 if flags&1 else 0,flags)
    def read(pointer,size):
        value={0x022B0000:bytes(prepared),0x022B1000:state}[pointer]
        assert len(value)==size
        return value
    conditions=decode_conditions(read,0x022B0000,actor,blob,frame,RAM_MASK)
    assert conditions["available"] is True
    conditions["owner"]=dict(actor=deepcopy(actor),actorPointer=0x023BA170,
        objectPointer=actor["engineIdentity"]["pointer"],fieldPointer=0x022B125C,
        context=deepcopy(sample["context"]))
    sample["romSha256"]="a"*64
    sample["pokemonAppearance"]=dict(schemaVersion=1,available=True,frame=sample["frame"],
        nativeCycle=sample["nativeCycle"],observationBoundary="main-task-queue-completion",
        identity=dict(romSha256="a"*64,capsuleElfSha256="b"*64,
                      behaviorBlobSha256=hashlib.sha256(blob).hexdigest()),conditions={"0":conditions})


def replay(row, test=None):
    kind=test["measurements"][0]["kind"] if test is not None else KIND
    meter=RamUntilCrashMeasurement(kind=kind,test=test)
    for sample in row["samples"]:
        meter.observe(sample,[e for e in row["events"] if e["frame"]==sample["frame"]])
    result=meter.finish()
    return {"passed":result["passed"],"failures":result["failures"],"measurements":{kind:result}}


class RamUntilCrashTests(unittest.TestCase):
    def test_behind_scope_reuses_charge_engine_without_duplicate_long_gate(self):
        test=validate_test(json.loads((ROOT/'tests/overworld/test-recipes/profile.ram.behind-entry.json').read_text()))
        result=replay(behind_fixture(7),test);self.assertTrue(result['passed'],result['failures'])
        entry=result['measurements'][BEHIND]['entryWitness']
        self.assertEqual(entry['geometry'],'behind');self.assertEqual(entry['delta'],[0,-5])
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        rows=measurements(BEHIND,result,record)
        self.assertNotIn('ram-charge-survives-old-96-frame-expiry',[r['name'] for r in rows])
        self.assertIn('ram-complete-charge-walks',[r['name'] for r in rows])
        evaluator=TestEvaluator(test);evaluator.install_measurements(measurement_inputs(test,ROOT))
        self.assertEqual(evaluator.measurements[BEHIND].kind,BEHIND)

    def test_behind_requires_passive_native_setup_without_weakening_ram(self):
        test=validate_test(json.loads((ROOT/'tests/overworld/test-recipes/profile.ram.behind-entry.json').read_text()))
        self.assertEqual([(a['op'],a['args']) for a in test['setup'][1:3]],[
            ('party',dict(slot=0,species=155,level=20)),
            ('spawn',dict(species=155,form=0,role='follower',slot=0,level=20))])
        for fault in ('missing','mankey','wrong-role','stale','hurt','throw-profile'):
            row=behind_fixture(7);first=row['samples'][0];a=first['actors'][1]
            if fault=='missing': first['actors'].pop()
            elif fault=='mankey':a['species']=56
            elif fault=='wrong-role':a['role']='MOUNTED'
            elif fault=='stale':a['identityVerified']=False
            elif fault=='hurt':first['pokemonCombat']['targets'][0]['hp']=49
            else:a['matchedLayerMask']=1<<__import__('tools.overworld.devtools_profile_feature_measurement',fromlist=['application_index']).application_index('apply-throw')
            with self.subTest(fault=fault):self.assertFalse(replay(row,test)['passed'])
        for index in (1,2):
            bad=deepcopy(test);bad['setup'].pop(index)
            with self.subTest(missing_setup=index),self.assertRaises(ValueError):validate_test(bad)
        result=replay(behind_fixture(7),test)
        self.assertTrue(result['passed'],result['failures'])
        self.assertEqual(result['measurements'][BEHIND]['passiveFollower']['actor']['species'],155)

    def test_entry_requires_native_idle_inactive_facing_and_current_owner(self):
        for behind in (False,True):
            test=validate_test(json.loads((ROOT/('tests/overworld/test-recipes/profile.ram.behind-entry.json' if behind else 'tests/overworld/test-recipes/profile.ram.until-crash.json')).read_text()))
            for fault in ('facing','busy','active','stale-owner','offset','old-idle'):
                with self.subTest(behind=behind,fault=fault):
                    row=behind_fixture() if behind else fixture(east=True)
                    sample=next(s for s in row['samples'] if s['frame']==99);a=sample['actors'][0]
                    if fault=='facing':a['engineObject']['facing']=0 if behind else 3
                    elif fault=='busy':a['engineObject']['flags']|=2
                    elif fault=='active':sample['pokemonAppearance']['conditions']['0']['states'][0]['flags']|=1
                    elif fault=='stale-owner':sample['pokemonAppearance']['conditions']['0']['owner']['actor']['handle']['generation']+=1
                    elif fault=='offset':a['engineObject']['unk88_y']=1
                    else:sample['actors'][0]['motionKind']='WALK'
                    self.assertFalse(replay(row,test)['passed'])

    def test_behind_retains_all_original_copied_fault_controls(self):
        test=validate_test(json.loads((ROOT/'tests/overworld/test-recipes/profile.ram.behind-entry.json').read_text()))
        for reset_at_entry in (False, True):
            baseline=behind_fixture()
            if reset_at_entry:
                first=next(e for e in baseline['events'] if e['kind']=='native-observation')
                reset=deepcopy(first);data=reset['data'];data['operation']=0;data['sequence']=1
                request=bytearray.fromhex(data['requestHex']);request[9]=0
                data['requestHex']=data['responseHex']=request.hex()
                after=bytearray(36);after[0]=after[4]=after[20]=255
                after[8:16]=struct.pack('<II',123456,RAM_MASK)
                first['data'].update(sequence=2,policyBeforeHex=after.hex())
                baseline['events'].insert(baseline['events'].index(first),reset)
                result=replay(baseline,test)
                self.assertTrue(result['passed'],result['failures'])
            for old in FAULTS:
                fault=BEHIND+':'+old.rsplit(':',1)[1];row=deepcopy(baseline)
                negative=RamFeatureNegative(BEHIND,fault)
                changed=negative.mutate(row,{'onix':row['samples'][0]['actors'][0]})
                self.assertTrue(negative.applied,fault)
                with self.subTest(reset_at_entry=reset_at_entry,fault=fault):
                    validate_negative_result(BEHIND,replay(changed,test),fault)

    def test_same_queue_crash_hides_only_its_uncredited_terminal_endpoint(self):
        row = crash_terminal_fixture()
        result = replay(row)
        self.assertTrue(result["passed"], result["failures"])
        meter = result["measurements"][KIND]
        hidden = meter["crashTerminalOverlap"]
        self.assertEqual(hidden["frame"], 239)
        self.assertEqual(hidden["motion"]["travelEnd"], None)
        self.assertNotIn(hidden["motion"], meter["completedChargeWalks"])
        self.assertEqual(len(meter["cooldownSamples"]), 17)
        for fault in ("pose", "gap", "commit", "control", "owner", "crash-order"):
            bad = deepcopy(row)
            if fault == "pose":
                next(s for s in bad["samples"] if s["frame"] == 239)["actors"][0]["engineObject"]["pos_x"] -= 1
            elif fault == "gap": bad["samples"].pop(next(i for i,s in enumerate(bad["samples"]) if s["frame"] == 237))
            else:
                event=next(e for e in bad["events"] if e["frame"] == 239 and e["data"].get("event") == ("LOGICAL_COMMIT" if fault == "commit" else "CONTROL_RETURNED"))
                if fault == "owner": event["data"]["actor"]["generation"] += 1
                elif fault == "crash-order": event["data"]["sequence"] += 10
                else: event["data"]["event"] = "UNRELATED"
            with self.subTest(fault=fault): self.assertFalse(replay(bad)["passed"])

    def test_measured_east_fixture_requires_exact_first_start_and_real_long_charge(self):
        test=validate_test(json.loads((ROOT/'tests/overworld/test-recipes/profile.ram.until-crash.json').read_text()))
        self.assertEqual(test["setup"][0]["args"],dict(map=33,x=607,z=402,facing=2))
        self.assertEqual((test["setup"][1]["args"]["x"],test["setup"][1]["args"]["z"]),(602,402))
        row=fixture(east=True);result=replay(row,test)
        self.assertTrue(result["passed"],result["failures"])
        self.assertEqual(result["measurements"][KIND]["heading"],3)
        for fault in ("west","wrong-row","wrong-origin"):
            bad=deepcopy(row);actor=next(s for s in bad["samples"] if s["frame"]==100)["actors"][0]
            if fault=="west":actor["target"]["x"]=actor["origin"]["x"]-1
            elif fault=="wrong-row":actor["origin"]["y"]=actor["target"]["y"]=403
            else:actor["origin"]["x"]-=1;actor["target"]["x"]-=1
            rejected=replay(bad,test)
            with self.subTest(fault=fault):
                self.assertFalse(rejected["passed"]);self.assertIn("measured East",str(rejected["failures"]))
        short=replay(fixture(charge_walks=7,east=True),test)
        self.assertFalse(short["passed"]);self.assertIn("old96-frame",str(short["failures"]))

    def test_complete_current_owner_charge_crash_yields_exact_claims(self):
        test=validate_test(json.loads((ROOT/'tests/overworld/test-recipes/profile.ram.until-crash.json').read_text()))
        result=replay(fixture(east=True),test)
        self.assertTrue(result["passed"],result["failures"])
        rows=measurements(result,{"sessionId":"host","sessionCleanup":{
            "sessionId":"host","closed":True,"errors":[]}})
        self.assertEqual(len(rows),10)
        self.assertTrue(all(r["passed"] for r in rows))

    def test_each_copied_fault_fails_its_exact_recorder_rule(self):
        for east in (False, True):
            for fault in FAULTS:
                with self.subTest(east=east, fault=fault):
                    row = fixture(east=east)
                    # Native Routine input can precede the Ram trigger. It
                    # cannot consume the one Ram speed-reset mutation.
                    routine = deepcopy(next(e for e in row["events"]
                        if e["kind"] == "native-observation"))
                    routine["frame"] = 99
                    row["events"].insert(0, routine)
                    selected = {"onix": row["samples"][0]["actors"][0]}
                    negative = RamUntilCrashNegative(fault)
                    changed = negative.mutate(row, selected)
                    self.assertTrue(negative.applied)
                    validate_negative_result(replay(changed), fault)

    def test_missing_policy_gap_and_stale_policy_owner_reject(self):
        for failure in ("policy","gap","owner"):
            with self.subTest(failure=failure):
                row=fixture()
                if failure=="policy":row["events"]=[e for e in row["events"] if e["kind"]!="native-observation"]
                elif failure=="gap":row["samples"].pop(20)
                else:
                    next(e for e in row["events"] if e["kind"]=="native-observation")["data"]["publicSubject"]["handle"]["generation"]=2
                self.assertFalse(replay(row)["passed"])

    def test_registered_recipe_uses_shared_factory_and_exact_normal_dodge(self):
        test=validate_test(json.loads((ROOT/'tests/overworld/test-recipes/profile.ram.until-crash.json').read_text()))
        evaluator=TestEvaluator(test);evaluator.install_measurements(measurement_inputs(test,ROOT))
        self.assertIsInstance(evaluator.measurements[KIND],RamUntilCrashMeasurement)
        changed=deepcopy(test)
        changed["actions"][1]["args"]["keys"]=["UP"]
        with self.assertRaises(ValueError):validate_test(changed)

    def test_real_reader_closes_without_inactive_semantic_trace(self):
        row=fixture()
        self.assertTrue(all(e["data"].get("reasonId",0)&(1<<14)
            for e in row["events"] if e["kind"]=="native"
            and e["data"]["event"]=="CONDITIONAL_RESOLVED"))
        result=replay(row)
        self.assertTrue(result["passed"],result["failures"])
        meter=result["measurements"][KIND]
        self.assertEqual(meter["closedCondition"]["source"],"authenticated-prepared-state")
        self.assertEqual(meter["closedCondition"]["cooldownUntil"]-meter["closedCondition"]["actorFrame"],100)
        self.assertEqual(len(meter["cooldownSamples"]),16)

    def test_current_short_wall_still_rejects_sub96_charge(self):
        result=replay(fixture(charge_walks=7))
        self.assertFalse(result["passed"])
        self.assertIn("old96-frame expiry",str(result["failures"]))
        self.assertFalse(result["measurements"][KIND]["longCharge"])

    def test_native_state_missing_stale_wrong_cd_and_state_profile_conflicts_reject(self):
        faults=("missing","entry","stale-owner","context","object","clock","package",
                "cd0","cd99","duration","state-active","mask-active","early-end","crash-owner",
                "pending-not-consumed","missing-rearm")
        for fault in faults:
            with self.subTest(fault=fault):
                row=fixture()
                for sample in row["samples"]:
                    frame=sample["frame"]
                    state=sample["pokemonAppearance"]["conditions"]["0"]
                    if frame==241:
                        if fault=="missing":sample.pop("pokemonAppearance")
                        elif fault=="entry":state["states"]=[]
                        elif fault=="stale-owner":state["owner"]["actor"]["handle"]["generation"]+=1
                        elif fault=="context":state["owner"]["context"]["fieldEpoch"]+=1
                        elif fault=="object":state["owner"]["objectPointer"]+=4
                        elif fault=="clock":state["frame"]-=1
                        elif fault=="package":sample["pokemonAppearance"]["identity"]["capsuleElfSha256"]="c"*64
                        elif fault in ("cd0","cd99"):state["states"][0]["cooldownUntil"]=frame+(0 if fault=="cd0" else 99)
                        elif fault=="duration":state["states"][0]["durationFrames"]=96
                        elif fault=="mask-active":sample["actors"][0]["matchedLayerMask"]|=RAM_MASK
                        elif fault=="pending-not-consumed":state["states"][0]["flags"]=14
                        elif fault=="missing-rearm":state["states"][0]["flags"]=10
                    if fault=="state-active" and frame>=241:state["states"][0]["flags"]|=1
                    if fault=="early-end" and frame==200:state["states"][0]["flags"]=26
                if fault=="crash-owner":
                    event=next(e for e in row["events"] if e["data"].get("event")=="WORLD_EFFECT"
                               and e["data"].get("valueA")==3)
                    event["data"]["actor"]["fieldEpoch"]+=1
                result=replay(row)
                self.assertFalse(result["passed"])


    def test_actual_nonraw_record_wiring_is_opt_in_and_selects_exact_onix(self):
        source=(ROOT/"tools/overworld/devtools_jobs.py").read_text()
        start=source.index('                            if test["id"] == "mount.begin-current-follower":')
        end=source.index('                        boundary = deepcopy(self.service.snapshot)',start)
        block=textwrap.dedent(source[start:end])
        for kind,id_ in ((KIND,"profile.ram.until-crash"),(BEHIND,"profile.ram.behind-entry"),("other","other"),
                         ("other","mount.begin-current-follower")):
            calls=[]
            worker=SimpleNamespace(call=lambda op,args: calls.append((op,deepcopy(args))) or {})
            service=SimpleNamespace(worker=worker,_observe=lambda value:None)
            self_=SimpleNamespace(service=service)
            evaluator=SimpleNamespace(measurements={kind:object()},subjects={"onix":deepcopy(ONIX)})
            args={"maxFrames":850}
            exec(block,dict(self=self_,test={"id":id_},evaluator=evaluator,record_args=args))
            self.assertEqual(calls[0][0],"record.start")
            if kind in (KIND,BEHIND):
                self.assertIs(calls[0][1]["appearancePalette"],True)
                self.assertEqual(calls[1],("observation.prepare",{"appearanceSubject":ONIX}))
            else:
                self.assertNotIn("appearancePalette",calls[0][1])
                self.assertEqual(len(calls),1)
            if id_=="mount.begin-current-follower":self.assertIs(calls[0][1]["roleProfile"],True)



class LinearRamReceiptTests(unittest.TestCase):
    def test_reset_is_allowed_once_at_the_measured_charge_entry_only(self):
        actor = deepcopy(ONIX)
        event = deepcopy(next(e for e in fixture()["events"]
                              if e["kind"] == "native-observation"))
        data = event["data"]
        data["operation"] = 0
        for key in ("requestHex", "responseHex"):
            raw = bytearray.fromhex(data[key]); raw[9] = 0
            data[key] = raw.hex()
        after = bytearray(36); after[0] = after[4] = after[20] = 255
        # The native Reset keeps profile identity at bytes 8..15.
        after[8:16] = struct.pack("<II", 123456, RAM_MASK)
        data["sequence"] = 1
        following = deepcopy(next(e for e in fixture()["events"]
                                  if e["kind"] == "native-observation"))
        following["data"]["sequence"] = 2
        following["data"]["policyBeforeHex"] = after.hex()

        def meter():
            value = RamUntilCrashMeasurement()
            value.trigger = {"frame": 100}
            value.first_walk = {"frame": 100}
            value.entry_witness = {"geometry": "behind"}
            value.current_events = [event, following]
            return value

        value = meter(); value._policy({"frame": 100}, actor)
        self.assertEqual(value.entry_reset, event)
        with self.assertRaisesRegex(ValueError, "outside fresh charge"):
            value._policy({"frame": 100}, actor)
        for fault in ("late", "no-entry", "not-cleared", "no-walk", "missing-input"):
            value = meter(); bad = deepcopy(event); next_input = deepcopy(following)
            if fault == "late": bad["frame"] = 101
            elif fault == "no-entry": value.entry_witness = None
            elif fault == "no-walk": value.first_walk = None
            elif fault == "not-cleared":
                raw = bytearray(after); raw[2] = 8
                next_input["data"]["policyBeforeHex"] = raw.hex()
            value.current_events = [bad] if fault == "missing-input" else [bad, next_input]
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "outside fresh charge"):
                value._policy({"frame": bad["frame"]}, actor)

    def test_linear_fraction_can_add_one_frame_without_speed_reset(self):
        actor=deepcopy(ONIX)
        row=fixture()
        event=deepcopy(next(e for e in row["events"] if e["kind"]=="native-observation"))
        event["frame"]=100
        data=event["data"]
        lane=bytearray(80);lane[7]=16;lane[50]=180;lane[51]=2;lane[71]=34
        before=bytearray(36);before[2]=before[25]=5;before[3]=16
        before[32]=52;before[33]=227;before[34]=1
        data["laneHex"]=lane.hex();data["policyBeforeHex"]=before.hex()
        response=bytearray.fromhex(data["responseHex"]);response[19]=6
        data["responseHex"]=response.hex()
        value=RamUntilCrashMeasurement();value.trigger={};value.heading=0
        value.current_events=[event]
        value._policy(dict(frame=100),actor)
        self.assertEqual(value.policy_calls[0]["travelTime"],6)
        for changed_time in (5,7,32):
            with self.subTest(travelTime=changed_time):
                bad=deepcopy(event);b=bytearray.fromhex(bad["data"]["responseHex"])
                b[19]=changed_time;bad["data"]["responseHex"]=b.hex()
                value.current_events=[bad]
                with self.assertRaisesRegex(ValueError,"slowed or reset"):
                    value._policy(dict(frame=100),actor)
        bad=deepcopy(event);bad["data"]["laneHex"]="00"
        value.current_events=[bad]
        with self.assertRaisesRegex(ValueError,"Linear timing lane"):
            value._policy(dict(frame=100),actor)


if __name__=="__main__":unittest.main()
