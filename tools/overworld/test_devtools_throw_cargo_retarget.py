"""Copied native-shaped controls for the registered Cargo retarget case."""
from copy import deepcopy
import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_throw_cargo_retarget_measurement import (
    ThrowCargoRetargetMeasurement, KIND, CASE, SETUP, ACTIONS, validate_recipe,
)
from tools.overworld.devtools_throw_cargo_retarget_proof import (
    FAULTS, ThrowCargoRetargetNegative, contract, measurements,
)
from tools.overworld.test_devtools_throw_cargo_competition import binding
from tools.overworld.test_devtools_player_health_throw_contact_measurement import (
    actor, snapshot, step_row, ROM, OVERLAY,
)
from tools.overworld.test_devtools_wild_throw_moving_candidate_measurement import native_motion
from tools.overworld.test_devtools_cargo_route_continuity import query_event, IMAGE
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import THROW_RELEASE_BIT

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(contractVersion=2, romSha256=ROM, overlaySha256=OVERLAY,
              profileSha256="c" * 64, queryImage=IMAGE)


def sample(frame, *, immediate_pickup=False):
    s = snapshot(frame)
    s.update(actorFrame=frame)
    s["player"].update(x=584, y=402)
    s["fieldControl"]["fieldPointer"] = 0x2200000
    first, geo, near = actor(155, 0, 700, 402), actor(74, 1, 740, 403), actor(70, 2, 701, 403)
    for item, x, y in ((first,585 if frame<=2 else 586,401 if frame<=2 else 402),
                       (geo,589,403 if frame<=2 else 402),(near,588,403)):
        item.update(level=20)
        for key in ("logical", "render", "origin", "target"):
            item[key] = dict(x=x,y=y)
        item["engineObject"].update(x=x,y=y,pos_x=(x<<16)+32768,pos_z=(y<<16)+32768)
        item["sourceIdentity"] = dict(object=item["engineIdentity"]["pointer"],
            personality=item["subjectIdentity"],map_id=33,species=item["species"],
            form=0,level=20,active=1,object_id=224+item["handle"]["slot"],
            encounter_generation=1)
    if frame<=3:
        geo.update(motionKind="WALK", motionPhase="MOVING", motionDuration=4,
                   motionElapsed=frame, reservationId=8,
                   origin=dict(x=589,y=403), target=dict(x=589,y=402))
    if frame>=7:
        near.update(motionKind="HOP",motionPhase="MOVING",motionDuration=20,
                    motionElapsed=0,reservationId=9,origin=dict(x=588,y=403),
                    target=dict(x=587,y=402))
        geo["matchedLayerMask"] = THROW_RELEASE_BIT
    s["actors"] = [first,geo,near]
    encoded = 1 if frame<=2 else 3 if frame<=4 else 131 if frame<=6 else 0
    if immediate_pickup and 3<=frame<=4:
        encoded = 131
    targets = [0]*10;targets[1] = encoded
    target_mask = 1 if frame<=2 else 4 if frame<=6 else 0
    carrier_mask = 2 if encoded else 0
    state = dict(targets=targets,targetMask=target_mask,carrierMask=carrier_mask,
                 recoveringMask=0,rawHex=(bytes(targets)+struct.pack("<3H",
                    target_mask,carrier_mask,0)).hex())
    cargo = first if frame<=2 else near
    binds = dict(trigger=binding("PLAYER"),
                 cargo=binding("ACTOR",cargo["handle"]) if encoded else binding())
    row = dict(handle=deepcopy(geo["handle"]),role="WILD",available=True,
               bindings=binds,rawBindingsHex=(raw_handle(geo["handle"])
                    +bytes.fromhex(binds["trigger"]["rawHex"])
                    +bytes.fromhex(binds["cargo"]["rawHex"])).hex(),
               throw=dict(targetRaw=encoded,targetSlot=(encoded&63)-1 if encoded else None,
                          carried=bool(encoded&128),windup=False,targeted=False,
                          carrier=bool(encoded),recovering=False))
    combat = dict(schemaVersion=1,available=True,frame=frame,nativeCycle=s["nativeCycle"],
                  observationBoundary=s["observationBoundary"],
                  fieldSystem=s["fieldControl"]["fieldPointer"],
                  identity=dict(romSha256=ROM,overlaySha256=OVERLAY),targets=[],movementTimers=[],
                  interactions=dict(schemaVersion=1,available=True,frame=frame,
                    nativeCycle=s["nativeCycle"],observationBoundary=s["observationBoundary"],
                    fieldSystem=s["fieldControl"]["fieldPointer"],identity=dict(romSha256=ROM),
                    carriers=[row],throwState=state))
    for item in s["actors"]:
        combat["targets"].append(dict(handle=deepcopy(item["handle"]),role=item["role"],
                                       motion=native_motion(item)))
        combat["movementTimers"].append(dict(handle=deepcopy(item["handle"]),
            slot=item["handle"]["slot"],sourceIdentity=deepcopy(item["sourceIdentity"]),
            movementActorControlMode=int(item is near and
                (5<=frame<=6 or (immediate_pickup and 3<=frame<=4)))))
    s["pokemonCombat"] = combat
    return s


def events(s):
    if s["frame"] == 1:
        event=query_event(s,s["actors"][1],IMAGE,status=1)
        event["data"]["after"]["workspace"]["compatibility"]["cargo"] = deepcopy(s["actors"][0]["handle"])
        raw=bytearray.fromhex(event["data"]["resultHex"])
        raw[:12]=raw_handle(s["actors"][1]["handle"])
        raw[12:24]=raw_handle(s["actors"][0]["handle"])
        struct.pack_into("<hh",raw,24,589,403)
        struct.pack_into("<hh",raw,48,586,402)
        event["data"]["resultHex"]=raw.hex()
        return [event]
    if s["frame"] == 3:
        event=query_event(s,s["actors"][1],IMAGE,status=1)
        event["data"]["after"]["workspace"]["compatibility"]["cargo"] = deepcopy(s["actors"][2]["handle"])
        raw=bytearray.fromhex(event["data"]["resultHex"])
        raw[:12]=raw_handle(s["actors"][1]["handle"])
        raw[12:24]=raw_handle(s["actors"][2]["handle"])
        struct.pack_into("<hh",raw,24,589,402)
        struct.pack_into("<hh",raw,48,588,402)
        event["data"]["resultHex"]=raw.hex()
        return [event]
    if s["frame"] == 4:
        geo=s["actors"][1]
        return [dict(frame=4,kind="native",data=dict(event="MOTION_FINISHED",
            actorHandle=geo["handle"]["value"],
            actorFrame=s["actorFrame"],reason="OK",valueB=1,
            actor={k:v for k,v in geo["handle"].items() if k!="value"}))]
    if s["frame"] == 7:
        near=s["actors"][2]
        return [dict(frame=7,kind="native",data=dict(event="MOTION_STARTED",
            actorHandle=near["handle"]["value"],
            actor={k:v for k,v in near["handle"].items() if k!="value"}))]
    return []


def meter():
    m = ThrowCargoRetargetMeasurement(SOURCE)
    m.latest = sample(0)
    m.subjects = {name:select_current_actor(m.latest,a) for name,a in
                  (("first-cargo",m.latest["actors"][0]),("geodude",m.latest["actors"][1]))}
    return m


class RetargetTests(unittest.TestCase):
    def test_exact_recipe_adapter_and_registered_contract(self):
        recipe=ROOT/"tests/overworld/test-recipes"/f"{CASE}.json"
        value=json.loads(recipe.read_text());validate_recipe(value)
        from tools.overworld.proof_adapters import ADAPTERS
        from tools.overworld.devtools_test_contract import TestEvaluator
        self.assertEqual(ADAPTERS[KIND].recipe_subjects(),value["subjects"])
        evaluator=TestEvaluator(value);evaluator.install_measurements({KIND:SOURCE})
        self.assertIsInstance(evaluator.measurements[KIND],ThrowCargoRetargetMeasurement)
        registry=json.loads((ROOT/"tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(registry["sharedTests"][CASE]["recipeSha256"],
                         hashlib.sha256(recipe.read_bytes()).hexdigest())
        self.assertEqual(registry["sharedTests"][CASE]["measurementContract"],contract())

    def test_current_switch_finishes_walk_then_held_launch(self):
        m=meter()
        for frame in range(1,8):
            if frame==2:
                m.subjects["near-cargo"]=select_current_actor(sample(frame),sample(frame)["actors"][2])
            s=sample(frame);m._sample(s,events(s))
        result=m.result();self.assertTrue(result["ready"])
        self.assertEqual(result["firstClaim"]["frame"],1)
        self.assertEqual(result["switch"]["frame"],3)
        self.assertEqual(result["heldFrames"],2)
        self.assertEqual(result["launch"]["frame"],7)
        replay=dict(passed=True,failures=[],measurements={KIND:result})
        self.assertEqual(len(measurements(replay,dict(sessionId="test",sessionCleanup=dict(
            sessionId="test",closed=True,errors=[])))),8)

    def test_near_advantage_and_accepted_plan_are_required(self):
        m=meter();s=sample(1);m._sample(s,events(s))
        m.subjects["near-cargo"]=select_current_actor(sample(2),sample(2)["actors"][2])
        s=sample(2);s["actors"][1]["target"]["x"]=590
        s["pokemonCombat"]["targets"][1]["motion"]=native_motion(s["actors"][1])
        with self.assertRaisesRegex(ValueError,"accepted Walk"):
            m._sample(s,events(s))
        m=meter();s=sample(1);m._sample(s,events(s))
        m.subjects["near-cargo"]=select_current_actor(sample(2),sample(2)["actors"][2])
        s=sample(2);m._sample(s,events(s))
        s=sample(3);bad_events=events(s)
        raw=bytearray.fromhex(bad_events[0]["data"]["resultHex"])
        struct.pack_into("<hh",raw,48,587,404)
        bad_events[0]["data"]["resultHex"]=raw.hex()
        with self.assertRaisesRegex(ValueError,"nearer reachable"):
            m._sample(s,bad_events)

    def test_switch_and_atomic_pickup_share_one_native_frame(self):
        m=meter()
        for frame in range(1,8):
            if frame==2:
                m.subjects["near-cargo"]=select_current_actor(sample(frame),sample(frame)["actors"][2])
            s=sample(frame,immediate_pickup=True);m._sample(s,events(s))
        result=m.result();self.assertTrue(result["ready"])
        self.assertEqual(result["switch"]["frame"],result["pickup"]["frame"])
        self.assertEqual(result["heldFrames"],4)
        replay=dict(passed=True,failures=[],measurements={KIND:result})
        self.assertEqual(len(measurements(replay,dict(sessionId="test",sessionCleanup=dict(
            sessionId="test",closed=True,errors=[])))),8)

    def test_same_frame_pickup_requires_prior_free_cargo(self):
        m=meter();s=sample(1);m._sample(s,events(s))
        m.subjects["near-cargo"]=select_current_actor(sample(2),sample(2)["actors"][2])
        s=sample(2);m._sample(s,events(s))
        m.latest["pokemonCombat"]["movementTimers"][2]["movementActorControlMode"]=1
        s=sample(3,immediate_pickup=True)
        with self.assertRaisesRegex(ValueError,"already HELD"):
            m._sample(s,events(s))

    def test_missing_finish_fault_skips_moves_before_the_cargo_claim(self):
        m=meter();subjects=m.subjects
        fault=ThrowCargoRetargetNegative(KIND+":missing-walk-finish")
        early=sample(0)
        early["pokemonCombat"]["interactions"]["carriers"][0]["throw"]["targetRaw"]=0
        done=events(sample(4))[0];done["frame"]=0
        row=dict(samples=[early,sample(1)],events=[done])
        self.assertEqual(fault.mutate(row,subjects),row)
        self.assertFalse(fault.applied)
        row=dict(samples=[sample(4)],events=events(sample(4)))
        changed=fault.mutate(row,subjects)
        self.assertTrue(fault.applied)
        self.assertEqual(changed["events"],[])

    def test_passive_follower_cannot_replace_the_named_first_cargo(self):
        m=meter();s=sample(1)
        s["pokemonCombat"]["interactions"]["throwState"]["targets"][1]=8
        with self.assertRaisesRegex(ValueError,"passive follower"):
            m._sample(s,events(s))

    def test_near_spawn_frame_is_retained_before_binding(self):
        m=meter();s=sample(1);m._sample(s,events(s),observed=False)
        s=sample(2);m._sample(s,events(s),observed=False)
        m.setup_index=8
        new=sample(3)
        spawn=dict(phase="setup",action="spawn-near-cargo",command="spawn",
                   snapshot=new,receipt=dict(events=events(new),
                       setupBoundary=dict(eventsDrained=True)))
        self.assertEqual(m.observe_record(spawn)["failures"],[])
        self.assertIsNone(m.switch)
        bind=dict(phase="setup",action="bind-near-cargo",command="bind",
                  snapshot=new,receipt=select_current_actor(new,new["actors"][2]))
        self.assertEqual(m.observe_record(bind)["failures"],[])
        self.assertEqual(m.switch["frame"],3)
        self.assertIsNone(m.pending_spawn)

    def test_actual_native_shaped_copied_faults_fail(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                m=meter();negative=ThrowCargoRetargetNegative(fault);failed=False
                for frame in range(1,8):
                    if frame==2:
                        s=sample(frame)
                        m.subjects["near-cargo"]=select_current_actor(s,s["actors"][2])
                    s=sample(frame)
                    row=step_row(ACTIONS[0][0],[s]);row["events"]=events(s)
                    altered=negative.mutate(row,m.subjects)
                    try:m._sample(altered["samples"][0],altered["events"])
                    except (ValueError,KeyError,StopIteration):failed=True;break
                self.assertTrue(negative.applied)
                self.assertTrue(failed)


if __name__=="__main__":
    unittest.main()
