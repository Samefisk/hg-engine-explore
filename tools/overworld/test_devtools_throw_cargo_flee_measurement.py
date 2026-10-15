"""Historical Cargo Flee controls; TKT-0059 retired its targeted fear contract."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest

DRAFT = Path(__file__).resolve().parent
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "tools/overworld/devtools_records.py").exists())
sys.path.insert(0, str(ROOT))
for name in ("devtools_throw_cargo_flee_measurement", "devtools_throw_cargo_flee_proof"):
    spec = importlib.util.spec_from_file_location("tools.overworld."+name, DRAFT / (name+".py"))
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)

from tools.overworld.devtools_throw_cargo_flee_measurement import (
    ACTION, APPLICATION, BOUNDARY, CONDITION, KIND, SETUP, ThrowCargoFleeMeasurement, validate_recipe,
)
from tools.overworld.devtools_throw_cargo_flee_proof import (
    FAULTS, ThrowCargoFleeNegative, measurements, validate_negative_result,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

SOURCE = dict(romSha256="a"*64, overlaySha256="b"*64, profileSha256="c"*64)


def sample(frame):
    cargo = actor(173, 0, 173000, 402); pursuer = actor(74, 2, 74000, 404)
    for a, x in ((cargo,587), (pursuer,584)):
        for field in ("logical","origin","target"): a[field]["x"] = x
        a.update(commitSequence=0, inputOwnership=0, reservationId=0, behaviorFingerprint=1717)
        a["engineObject"] = dict(pos_x=(x<<16)+32768, pos_z=(a["logical"]["y"]<<16)+32768,
            pos_y=65536, unk88_y=0, facing=3, flags=1)
    if frame >= 10:
        cargo["matchedLayerMask"] = 1 << APPLICATION
        cargo.update(origin=dict(x=587,y=402),target=dict(x=588,y=402))
        if frame <= 14:
            cargo.update(motionKind="WALK",motionPhase="MOVING" if frame < 14 else "COMMIT_PENDING",
                         motionElapsed=frame-10,motionDuration=4)
            cargo["engineObject"]["pos_x"] += (frame-10)*16384
        else:
            cargo.update(commitSequence=1,motionElapsed=4,motionDuration=4,logical=dict(x=588,y=402))
            cargo["engineObject"]["pos_x"] += 65536
    raw_cargo = raw_handle(cargo["handle"])+bytes([2,0])+struct.pack("<HIBBBB",57932,0,20,0,1,0)
    binding = dict(bound=True,flags=1,targetCurrent=True,target=dict(kind="ACTOR",actor=deepcopy(cargo["handle"])),rawHex=raw_cargo.hex())
    targets = [0]*10; targets[2] = 1 if frame >= 10 else 0
    masks = (1,4,0) if frame >= 10 else (0,0,0)
    native = bytes(targets)+struct.pack("<3H",*masks)
    carrier = dict(handle=deepcopy(pursuer["handle"]),role="WILD",available=True,bindings=dict(cargo=binding),
                   rawBindingsHex=(raw_handle(pursuer["handle"])+bytes(24)+raw_cargo).hex())
    result = dict(frame=frame,nativeCycle=frame+1000,fieldAvailable=True,romSha256=SOURCE["romSha256"],observationBoundary=BOUNDARY,
                  context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),fieldControl=dict(taskPointer=0,fieldPointer=0x2200000),
                  actors=[cargo,pursuer],player=dict(x=585,y=407),
                  nativeObservation=dict(coverageComplete=True,profilesEvicted=0,profileFingerprints=[1717]),
                  pokemonCombat=dict(available=True,frame=frame,nativeCycle=frame+1000,identity=dict(romSha256=SOURCE["romSha256"],overlaySha256=SOURCE["overlaySha256"]),
                    interactions=dict(available=True,schemaVersion=1,frame=frame,nativeCycle=frame+1000,observationBoundary=BOUNDARY,
                      fieldSystem=0x2200000,identity=dict(romSha256=SOURCE["romSha256"]),carriers=[carrier],
                      throwState=dict(targets=targets,targetMask=masks[0],carrierMask=masks[1],recoveringMask=0,rawHex=native.hex()))))
    return result


def stream():
    samples = [sample(f) for f in range(10,16)]; cargo,pursuer = samples[0]["actors"]
    data = bytearray(216); data[0]=4; data[13]=3; struct.pack_into("<I",data,192,1717)
    data[196:210] = raw_handle(pursuer["handle"])+bytes([2,0]); data[212]=APPLICATION; struct.pack_into("<H",data,214,CONDITION)
    events=[]
    for frame,names in ((10,("CONDITIONAL_RESOLVED","INTENT_CREATED","MOTION_STARTED")),
                        (15,("LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"))):
        for seq,name in enumerate(names):
            value = dict(actorHandle=cargo["handle"]["value"],actor={k:v for k,v in cargo["handle"].items() if k!="value"},
                         sequence=frame*10+seq,event=name,actorFrame=frame,valueA=0,valueB=0,reasonId=0)
            if name=="CONDITIONAL_RESOLVED":
                value.update(reasonId=APPLICATION | (APPLICATION<<5) | (2<<10) | (1<<13) | (1<<14),
                             valueA=CONDITION | (pursuer["handle"]["slot"]<<16))
            events.append(dict(frame=frame,kind="native",data=value))
    return [dict(phase="observe",action=ACTION[0],samples=samples,events=events,completedGameFrames=6,observedFieldFrames=6,nativeCycles=6,
        cycleIntervals=[dict(completedGameFrame=s["frame"],cpuNs=1,wallNs=1) for s in samples],
        profileCache=dict(frame=15,nativeCycle=1015,resolvedProfiles=[dict(fingerprint=1717,resolved=True,sourceSha256=SOURCE["profileSha256"],resultHex=data.hex())]))]


def evaluate(rows, negative=None):
    meter=ThrowCargoFleeMeasurement(SOURCE); initial=sample(9); meter.latest=deepcopy(initial); meter.setup_index=len(SETUP)
    meter.subjects={name:select_current_actor(initial,a) for name,a in zip(("cargo","geodude"),initial["actors"])}
    for row in rows: meter.observe_record(negative.mutate(row,meter.subjects) if negative else row)
    result=meter.finish()
    return dict(passed=result["passed"],failures=result["failures"],observedFrames=result["observedFrames"],measurements={KIND:result})


class ThrowCargoFleeTests(unittest.TestCase):
    def test_unsupported_condition_event_cannot_earn_flee_credit(self):
        rows=stream();rows[0]["events"][0]["data"]["event"]="CONDITION_MATCHED"
        self.assertFalse(evaluate(rows)["passed"])

    def test_native_frame_alias_keeps_the_completed_travel_clock(self):
        rows=stream()
        for event in rows[0]["events"]:
            event["data"]["frame"]=event["data"]["actorFrame"]
        result=evaluate(rows)
        self.assertTrue(result["passed"],result)

    def test_current_claim_target_and_completed_away_motion(self):
        result=evaluate(stream()); self.assertTrue(result["passed"],result)
        self.assertEqual(len(measurements(result,dict(sessionId="owned",sessionCleanup=dict(sessionId="owned",closed=True,errors=[])))),5)

    def test_named_player_stale_direction_and_commit_controls(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                negative=ThrowCargoFleeNegative(fault); result=evaluate(stream(),negative)
                self.assertTrue(negative.applied); validate_negative_result(result,fault)

    def test_lost_claim_missing_profile_and_player_notice_do_not_earn_credit(self):
        for fault in ("lost","profile","notice"):
            rows=stream(); row=rows[0]
            if fault=="profile": row.pop("profileCache")
            elif fault=="notice":
                event=row["events"][0]; event["data"]["valueA"] ^= 1
            else:
                snap=row["samples"][2]; state=snap["pokemonCombat"]["interactions"]["throwState"]
                state.update(targets=[0]*10,targetMask=0,carrierMask=0,recoveringMask=0,rawHex=bytes(16).hex())
            self.assertFalse(evaluate(rows)["passed"],fault)

    def test_retired_user_contract_preserves_history_without_active_proof(self):
        archive = json.loads((ROOT/"tests/overworld/retired/wild.throw-cargo-flee.json").read_text())
        registry = json.loads((ROOT/"tools/overworld/runtime_proof_registry.json").read_text())
        features = json.loads((ROOT/"tools/overworld/system_features.yaml").read_text())
        self.assertEqual(archive['status'], 'obsolete')
        self.assertEqual(archive['ticket'], 'TKT-0059')
        self.assertEqual(archive['retainedFailure']['runId'], 'test-abc39a86d71e4985a31497ee7598c76b')
        self.assertFalse(archive['retainedFailure']['acceptedProof'])
        self.assertEqual(archive['registration']['requirements'], [archive['requirement']['id']])
        self.assertNotIn(archive['id'], registry['sharedTests'])
        self.assertNotIn(archive['requirement']['id'], registry['runners'])
        self.assertFalse((ROOT/'tests/overworld/scenarios'/('wild.throw-cargo-flee.json')).exists())
        self.assertFalse([c for c in features['capabilities'] if archive['id'] in c['scenarios']])

    def test_frame_split_and_recipe_contract(self):
        row=stream()[0]; rows=[]
        for snap in row["samples"]:
            r=deepcopy(row); r.update(samples=[snap],events=[e for e in row["events"] if e["frame"]==snap["frame"]],
              completedGameFrames=1,observedFieldFrames=1,nativeCycles=1,cycleIntervals=[dict(completedGameFrame=snap["frame"],cpuNs=1,wallNs=1)])
            rows.append(r)
        self.assertTrue(evaluate(rows)["passed"])
        archive = json.loads((ROOT/"tests/overworld/retired/wild.throw-cargo-flee.json").read_text())
        validate_recipe(archive['recipe'])


if __name__ == "__main__": unittest.main()
