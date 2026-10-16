"""Copied-data checks for the moving Wild Throw candidate proof."""

from copy import deepcopy
import json
import struct
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_player_health_throw_contact_measurement import (
    ROM, OVERLAY, actor as base_actor, snapshot, step_row,
)
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import (
    KIND, GEODUDE_TILE, THROW_APPLICATION, THROW_APPLICATION_LOCAL, THROW_APPLICATION_BIT, THROW_POSITION_BIT, THROW_RELEASE_BIT, WildThrowMovingCandidateMeasurement,
    verify_wander_spawn, TRIGGER_CONDITION, CARGO_CONDITION,
    BUBBLE_SOUND_ID, BUBBLE_PLAY_CALLER, QUIET_BUBBLE_STOP_CALLER, moving_pickup_witness,
)
from tools.overworld.devtools_wild_throw_moving_candidate_proof import (
    FAULTS, SOUND_FAULTS, PICKUP_FAULTS, contract, faulted_rows, measurements,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = {"contractVersion": 1, "romSha256": ROM, "overlaySha256": OVERLAY}


def passive():
    a=base_actor(155,7,15520,408);a.update(role="FOLLOWER",level=20,matchedLayerMask=0)
    return a


def interactions(snap, claimed):
    from tools.overworld.devtools_follower_throw_measurement import raw_handle
    geo=next(a for a in snap["actors"] if a["species"]==74)
    cargo=next(a for a in snap["actors"] if a["species"]==234)
    def binding(kind, condition):
        raw=(raw_handle(cargo["handle"]) if kind=="ACTOR" else bytes(12))+bytes([2 if kind=="ACTOR" else 1,0])+struct.pack("<HIBBBB",condition,0,THROW_APPLICATION_LOCAL,0,1,0)
        return dict(bound=True,flags=1,targetCurrent=True,target=dict(kind=kind,actor=deepcopy(cargo["handle"]) if kind=="ACTOR" else None),sourceConditionId=condition,expiresAt=0,sourceApplication=THROW_APPLICATION,sourceApplicationLocal=THROW_APPLICATION_LOCAL,lifetime=0,reason=0,rawHex=raw.hex())
    bindings=dict(trigger=binding("PLAYER",TRIGGER_CONDITION),cargo=binding("ACTOR",CARGO_CONDITION))
    targets=[0]*10;targets[geo["handle"]["slot"]]=(cargo["handle"]["slot"]+1 | (128 if claimed == "held" else 0)) if claimed else 0
    tm=1<<cargo["handle"]["slot"] if claimed else 0;cm=1<<geo["handle"]["slot"] if claimed else 0
    row=dict(handle=deepcopy(geo["handle"]),role="WILD",available=True,bindings=bindings,
        rawBindingsHex=(raw_handle(geo["handle"])+bytes.fromhex(bindings["trigger"]["rawHex"])+bytes.fromhex(bindings["cargo"]["rawHex"])).hex(),
        throw=dict(targetRaw=targets[geo["handle"]["slot"]],targetSlot=cargo["handle"]["slot"] if claimed else None,carried=claimed == "held",windup=False,targeted=False,carrier=bool(claimed),recovering=False))
    return dict(schemaVersion=1,available=True,frame=snap["frame"],nativeCycle=snap["nativeCycle"],observationBoundary=snap["observationBoundary"],fieldSystem=snap["fieldControl"]["fieldPointer"],identity=dict(romSha256=ROM),carriers=[row],throwState=dict(targets=targets,targetMask=tm,carrierMask=cm,recoveringMask=0,rawHex=(bytes(targets)+struct.pack("<3H",tm,cm,0)).hex()))


def current(frame, target=False, source=False, launch=False):
    snap = snapshot(frame, player_map=33, target_present=target,
                    source_present=source, target_y=403,
                    source_y=404 if frame < 22 else 403 if frame < 24 else 401,
                    hop=launch)
    if target:
        actor = snap["actors"][0]
        actor["species"] = 234
        if frame in (17, 18, 20, 21, 22):
            actor.update(motionKind="WALK", motionPhase="MOVING",
                         motionElapsed=2 if frame in (17, 18) else frame - 18, motionDuration=14,
                         reservationId=31,
                         origin={"x": 585, "y": 403},
                         target={"x": 585, "y": 402})
    if source and frame in (20, 21):
        actor = snap["actors"][1]
        actor["matchedLayerMask"] = THROW_APPLICATION_BIT
        if frame == 21:
            actor.update(motionKind="WALK", motionPhase="MOVING",
                         motionElapsed=2, motionDuration=16, reservationId=32,
                         origin={"x": 585, "y": 404},
                         target={"x": 585, "y": 403})
    if target and source and frame in (23, 24):
        snap["actors"][0].update(motionKind="NONE", motionPhase="CANCELED", motionElapsed=4,
                                 motionDuration=14, inputOwnership=0, reservationId=0)
        snap["actors"][1]["matchedLayerMask"] = THROW_POSITION_BIT
    if source and launch:
        snap["actors"][1]["matchedLayerMask"] = THROW_RELEASE_BIT
    if source and frame <= 18:
        actor = snap["actors"][1]
        for key in ("logical", "render", "origin", "target"):
            actor[key] = dict(x=GEODUDE_TILE[0], y=GEODUDE_TILE[1])
        actor["engineObject"].update(x=GEODUDE_TILE[0], y=GEODUDE_TILE[1],
            pos_x=(GEODUDE_TILE[0] << 16) + 32768,
            pos_z=(GEODUDE_TILE[1] << 16) + 32768)
    snap["actorFrame"] = frame + 100
    snap["party"]=[dict(slot=0,species=155,level=20,isEgg=False,personality=15520,identityVerified=True)]
    if frame>=12:snap["actors"].append(passive())
    snap["fieldControl"]["fieldPointer"]=0x2200000
    if target and source:
        snap["pokemonCombat"]=dict(schemaVersion=1, available=True,frame=frame,nativeCycle=snap["nativeCycle"],
            observationBoundary=snap["observationBoundary"],fieldSystem=snap["fieldControl"]["fieldPointer"],
            identity=dict(romSha256=ROM,overlaySha256=OVERLAY),
            interactions=interactions(snap, "held" if frame in (23,24) else frame in (20,21,22)),
            targets=[], movementTimers=[])
        for a in snap["actors"]:
            a.setdefault("inputOwnership", 0)
            a["sourceIdentity"] = dict(object=a["engineIdentity"]["pointer"], personality=a["subjectIdentity"],
                map_id=33,species=a["species"],form=a["form"],level=a["level"],active=1,
                object_id=0xE0+a["handle"]["slot"],encounter_generation=a["handle"]["encounterGeneration"])
            canceled = a["species"] == 234 and frame in (23,24)
            snap["pokemonCombat"]["targets"].append(dict(handle=deepcopy(a["handle"]),role=a["role"],
                                                        motion=native_motion(a,canceled)))
            snap["pokemonCombat"]["movementTimers"].append(dict(handle=deepcopy(a["handle"]),
                slot=a["handle"]["slot"],sourceIdentity=deepcopy(a["sourceIdentity"]),
                movementActorControlMode=int(canceled)))
    return snap


def native_motion(actor, canceled=False):
    from tools.overworld.devtools_walk_matrix_observer import decode_motion
    raw = bytearray(52)
    kind = {"NONE":0,"WALK":1,"HOP":2}[actor["motionKind"]]
    phase = {"IDLE":0,"MOVING":2,"CANCELED":6}[actor["motionPhase"]]
    origin = list(actor["origin"].values()); target = list(actor["target"].values())
    elapsed, duration, reservation = actor["motionElapsed"],actor["motionDuration"],actor["reservationId"]
    if canceled:
        kind,origin,target,duration,reservation = 1,[585,403],[585,402],14,31
    struct.pack_into("<HBBHH",raw,0,1,kind,0,actor["handle"]["fieldEpoch"],0)
    struct.pack_into("<4h2iHH",raw,8,*origin,*target,0,0,duration,reservation)
    raw[29] = max(abs(a-b) for a,b in zip(origin,target))
    struct.pack_into("<4H4B",raw,40,elapsed,0,0,0,phase,0,0,16 if canceled else 0)
    if phase == 2:
        for axis,key in zip(range(2),("pos_x","pos_z")):
            delta=(target[axis]-origin[axis])<<16
            actor["engineObject"][key]=(origin[axis]<<16)+32768+(1 if delta>=0 else -1)*(abs(delta)*elapsed//duration)
    return decode_motion(bytes(raw))


def pickup_events(sample):
    cargo = next(a for a in sample["actors"] if a["species"] == 234)
    def event(name, a, b, sequence):
        return dict(frame=sample["frame"], kind="native", data=dict(event=name,valueA=a,valueB=b,
            sequence=sequence,reason="CONTEXT_LOST",frame=sample["actorFrame"],actorFrame=sample["actorFrame"],
            actorHandle=cargo["handle"]["value"],actor={k:v for k,v in cargo["handle"].items() if k!="value"}))
    return [event("MOTION_CANCELED",1,0,110),event("CONTROL_RETURNED",0,0,111)]


def rows():
    initial = snapshot(10, player_map=34)
    tile = current(11)
    target = current(12, target=True)
    both = current(12, target=True, source=True)
    target_bound = select_current_actor(target, target["actors"][0])
    source_bound = select_current_actor(both, both["actors"][1])
    waiting = step_row("walk-stantler-before-notice",
                       [current(13, target=True, source=True)])
    waiting["phase"] = "setup"
    prewalk = step_row("walk-stantler-before-notice",
                       [current(frame, target=True, source=True) for frame in range(14, 19)])
    prewalk["phase"] = "setup"
    samples = [current(frame, target=True, source=True, launch=frame == 25)
               for frame in range(19, 26)]
    stream = [
        {"phase": "setup", "initialSnapshot": initial},
        {"phase": "setup", "action": "throw-tile", "command": "teleport",
         "snapshot": tile, "receipt": {}},
        {"phase": "setup", "action": "prepare-passive-follower", "command": "party", "snapshot":tile,"receipt":{}},
        {"phase": "setup", "action": "create-passive-follower", "command": "spawn", "snapshot":current(12),
         "receipt":dict(lifecycle="prepared-native-follower-lifecycle",requestedSubject=dict(slot=0,role="FOLLOWER",species=155,form=0,level=20,personality=15520))},
        {"phase": "setup", "action": "spawn-stantler", "command": "spawn",
         "snapshot": target,
         "receipt": wander_receipt(target)},
        {"phase": "setup", "action": "bind-stantler", "command": "bind",
         "snapshot": target, "receipt": target_bound},
        {"phase": "setup", "action": "spawn-geodude", "command": "spawn",
         "snapshot": both,
         "receipt": {"value": {"species": 74, "slot": 1, "personality": 740}}},
        {"phase": "setup", "action": "bind-geodude", "command": "bind",
         "snapshot": both, "receipt": source_bound},
        waiting,
        prewalk,
        step_row("natural-moving-pickup-and-launch", samples),
    ]
    stream[-1]["events"] = bubble_events(next(s for s in samples if s["frame"] == 20)) + pickup_events(next(s for s in samples if s["frame"] == 23))
    return stream


def bubble_events(sample):
    def event(kind, sequence, caller):
        return {"frame": sample["frame"], "kind": "native-observation", "data": {
            "observation": kind, "sequence": sequence, "caller": caller,
            "sequenceId": BUBBLE_SOUND_ID, "entryActorFrame": sample["actorFrame"],
            "returnActorFrame": sample["actorFrame"],
            "entryNativeCycle": sample["nativeCycle"], "returnNativeCycle": sample["nativeCycle"]}}
    return [event("sound-play", 100, BUBBLE_PLAY_CALLER),
            event("sound-stop", 101, QUIET_BUBBLE_STOP_CALLER)]


def wander_receipt(snap, position=None):
    actor = snap["actors"][0]
    position = position or [actor["logical"]["x"], actor["logical"]["y"]]
    destination = position
    raw = (position[0].to_bytes(4, "little", signed=True)
           + position[1].to_bytes(4, "little", signed=True)
           + bytes(4) + (700).to_bytes(4, "little")
           + (234).to_bytes(2, "little") + bytes([0, 5])
           + destination[0].to_bytes(2, "little", signed=True)
           + destination[1].to_bytes(2, "little", signed=True)
           + destination[0].to_bytes(2, "little", signed=True)
           + destination[1].to_bytes(2, "little", signed=True)
           + bytes([7, 0]))
    common = {"slot": 0, "terrain": 0, "statePointer": 0x2300000,
              "fieldPointer": 0x2200000, "preparedPointer": 0x2400000,
              "preparedPrefixHex": raw.hex(), "position": position,
              "preparedEncounter": {"personality": 700, "species": 234,
                                    "form": 0, "level": 5},
              "startup": {"target": destination, "origin": destination,
                          "locomotion": 7, "hopDirection": 0, "targetBaseY": 0},
              "worldContext": {"mapId": 33, "fieldEpoch": 1,
                               "mapGeneration": 1}}
    final = {**common, "returnValue": 1, "pairEligible": True,
             "returnWorldContext": common["worldContext"],
             "inputPosition": [585, 403],
             "inputEncounter": common["preparedEncounter"]}
    event = {**common, "observation": "spawn-prepared", "returnValue": 1,
             "finalization": {"status": "matched", "receipt": final},
             "publicSubject": actor}
    return {"value": {"species": 234, "slot": 0, "personality": 700},
            "events": [{"kind": "native-observation", "data": event}]}


def witness_subjects(stream):
    return {name: deepcopy(next(r["receipt"] for r in stream if r.get("action") == "bind-"+name))
            for name in ("stantler", "geodude")}


def evaluate(stream):
    meter = WildThrowMovingCandidateMeasurement(SOURCE)
    for row in stream:
        result = meter.observe_record(row)
        if result["failures"]:
            break
    return meter.finish(), meter.result()


class WildThrowMovingCandidateMeasurementTest(unittest.TestCase):
    def test_authored_contract(self):
        recipe = json.loads((ROOT / "tests/overworld/test-recipes/wild.throw-moving-candidate.json").read_text())
        scenario = json.loads((ROOT / "tests/overworld/scenarios/wild.throw-moving-candidate.json").read_text())
        self.assertEqual(recipe["measurements"],
                         [{"kind": KIND, "subjects": ["stantler", "geodude"]}])
        self.assertEqual(scenario["adapter"]["claims"], list(contract()))
        from tools.overworld.devtools_test_contract import validate_test
        self.assertEqual(validate_test(recipe)["setup"][3]["args"]["z"], 403)
        self.assertEqual((recipe["setup"][5]["args"]["x"], recipe["setup"][5]["args"]["z"]), GEODUDE_TILE)
        for wrong_tile in ((582, 402), (583, 402), (585, 404)):
            bad = deepcopy(recipe)
            bad["setup"][5]["args"].update(x=wrong_tile[0], z=wrong_tile[1])
            with self.subTest(wrong_tile=wrong_tile), self.assertRaisesRegex(ValueError, "exact two actors"):
                validate_test(bad)
        for wrong_start in (400, 402, 404):
            bad = deepcopy(recipe)
            bad["setup"][3]["args"]["z"] = wrong_start
            with self.subTest(wrong_start=wrong_start), self.assertRaisesRegex(ValueError, "exact two actors"):
                validate_test(bad)
        catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
        from scripts.overworld_behavior_profile_viewer import _runtime_source_behavior_catalog
        catalog = _runtime_source_behavior_catalog(catalog)
        indexes = {row["id"]: i for i, row in enumerate(catalog["applications"])}
        self.assertEqual(recipe["subjects"][0]["species"], 234)
        old_attack = deepcopy(recipe)
        old_attack["subjects"][0]["species"] = old_attack["setup"][3]["args"]["species"] = 143
        with self.assertRaisesRegex(ValueError, "exact two actors"):
            validate_test(old_attack)
        from tools.overworld.devtools_application_bank import canonical_bank, local_application
        bank = canonical_bank(ROOT)
        from tools.overworld.devtools_application_bank import species_applications
        self.assertIn(indexes["apply-sprint"], species_applications(bank, 234))
        profiles = {row["id"]: row for row in catalog["profiles"]}
        self.assertFalse(any(profiles[catalog["applications"][i]["profile"]].get("kind") == "conditional"
                             for i in species_applications(bank, 234)))
        self.assertEqual(THROW_APPLICATION_BIT, 1 << local_application(bank, 74, indexes["apply-throw"]))
        self.assertEqual(THROW_RELEASE_BIT, 1 << local_application(bank, 74, indexes["apply-throw-release"]))
        bad = rows()
        next(row for row in bad if row.get("action") == "bind-geodude")["snapshot"]["actors"][1]["logical"] = dict(x=585, y=404)
        done, result = evaluate(bad)
        self.assertFalse(done["passed"], result)
        self.assertIn("moving Throw subject left its prepared native spawn", result["failures"])

    def test_current_claim_allows_unrelated_population_and_rejects_passive_faults(self):
        stream=rows()
        for sample in stream[-1]["samples"]:sample["actors"].append(base_actor(95,3,9500,390))
        done,result=evaluate(stream);self.assertTrue(done["passed"],result["failures"])
        for fault in ("party","receipt","follower","stale","active-throw"):
            bad=rows()
            if fault=="party":bad[2]["snapshot"]["party"][0]["species"]=56
            elif fault=="receipt":bad[3]["receipt"]["lifecycle"]="wrong"
            elif fault=="follower":bad[3]["snapshot"]["actors"][-1]["subjectIdentity"]+=1
            elif fault=="stale":bad[-1]["samples"][0]["actors"][-1]["handle"]["fieldEpoch"]+=1
            else:bad[-1]["samples"][0]["actors"][-1]["matchedLayerMask"]=1<<31
            with self.subTest(fault=fault):
                done,result=evaluate(bad);self.assertFalse(done["passed"],result)

    def test_walking_candidate_then_same_launch(self):
        finished, result = evaluate(rows())
        self.assertTrue(finished["passed"], result["failures"])
        self.assertEqual((result["preNoticeWalkFrame"], result["movingCandidateFrame"],
                          result["walkPursuitFrame"], result["launchFrame"]),
                         (18, 20, 21, 25))

    def test_copied_faults_reject(self):
        baseline = rows()
        for fault in FAULTS:
            with self.subTest(fault=fault):
                finished, result = evaluate(faulted_rows(baseline, fault))
                self.assertFalse(finished["passed"])
                named = {"wrong-cargo-binding": "current cargo binding differs",
                         "wrong-trigger-binding": "current trigger binding differs",
                         "missing-cargo-claim": "lacks its exact native Cargo claim",
                         "stale-claim-clock": "absent, stale or unauthenticated",
                         "stale-cargo-handle": "current cargo binding differs"}
                if fault in named:
                    self.assertTrue(any(named[fault] in message for message in result["failures"]), result)

    def test_motion_faults_select_bound_cargo_with_same_species_decoy(self):
        stream = rows()
        for row in stream:
            for sample in row.get("samples", []):
                sample["actors"].insert(0, base_actor(234, 3, 23401, 390))
        done, result = evaluate(stream)
        self.assertTrue(done["passed"], result)
        cargo = witness_subjects(stream)["stantler"]
        for fault in ("no-prewalk", "idle-candidate", "wrong-launch-target", "stale-candidate"):
            with self.subTest(fault=fault):
                changed = faulted_rows(stream, fault)
                changed_cargo = False
                for before, after in zip(stream, changed):
                    for old_sample, new_sample in zip(before.get("samples", []), after.get("samples", [])):
                        self.assertEqual(new_sample["actors"][0], old_sample["actors"][0])
                        old_actor = next(a for a in old_sample["actors"] if a["handle"] == cargo["handle"])
                        new_actor = next(a for a in new_sample["actors"] if a["handle"] == cargo["handle"])
                        changed_cargo |= new_actor != old_actor
                self.assertTrue(changed_cargo)
                done, result = evaluate(changed)
                self.assertFalse(done["passed"], result)

    def test_claim_faults_select_full_owner_and_skip_unbound_windows(self):
        stream = rows()
        samples = stream[-1]["samples"]
        # A real observation also includes unbound Cargo and Follower owners.
        for sample in samples:
            decoy = base_actor(74, 3, 7401, 390)
            decoy["matchedLayerMask"] = THROW_APPLICATION_BIT
            sample["actors"].insert(0, decoy)
            value = sample["pokemonCombat"]["interactions"]
            other = deepcopy(value["carriers"][0])
            other["handle"] = deepcopy(sample["actors"][0]["handle"])
            for binding in other["bindings"].values():
                binding.update(bound=False, flags=0, targetCurrent=False,
                               target={"kind": "NONE", "actor": None})
            value["carriers"].insert(0, other)
        # Throw can be resolved before the native free claim is published.
        early = samples[0]
        next(a for a in early["actors"] if a["species"] == 74 and a["handle"]["slot"] == 1)["matchedLayerMask"] = THROW_APPLICATION_BIT
        for binding in early["pokemonCombat"]["interactions"]["carriers"][1]["bindings"].values():
            binding.update(bound=False, flags=0, targetCurrent=False,
                           target={"kind": "NONE", "actor": None})
        faults = FAULTS[5:10]
        for fault in faults:
            with self.subTest(fault=fault):
                changed = faulted_rows(stream, fault)
                for index, sample in enumerate(samples):
                    self.assertEqual(changed[-1]["samples"][index]["pokemonCombat"]
                                     ["interactions"]["carriers"][0],
                                     sample["pokemonCombat"]["interactions"]["carriers"][0])
                self.assertEqual(changed[-1]["samples"][0], early)
                self.assertNotEqual(changed[-1]["samples"][1], samples[1])
                done, result = evaluate(changed)
                self.assertFalse(done["passed"], result)
        unclaimed = deepcopy(stream)
        for sample in unclaimed[-1]["samples"]:
            state = sample["pokemonCombat"]["interactions"]["throwState"]
            state["targets"] = [0] * 10
        with self.assertRaisesRegex(ValueError, "current bound Cargo claim"):
            faulted_rows(unclaimed, "wrong-cargo-binding")

    def test_plain_walk_without_geodude_pursuit_rejects(self):
        stream = deepcopy(rows())
        source = stream[-1]["samples"][2]["actors"][1]
        source["matchedLayerMask"] = 0
        finished, _ = evaluate(stream)
        self.assertFalse(finished["passed"])

    def test_wrong_stage_bits_cannot_prove_cargo_or_release(self):
        for old_cargo, old_release in ((True, False), (False, True)):
            with self.subTest(old_cargo=old_cargo, old_release=old_release):
                stream = rows()
                for sample in stream[-1]["samples"]:
                    carrier = next(a for a in sample["actors"] if a["species"] == 74)
                    if old_cargo and carrier["matchedLayerMask"] == THROW_APPLICATION_BIT:
                        carrier["matchedLayerMask"] = THROW_POSITION_BIT
                    if old_release and carrier["matchedLayerMask"] == THROW_RELEASE_BIT:
                        carrier["matchedLayerMask"] = THROW_POSITION_BIT
                finished, result = evaluate(stream)
                self.assertFalse(finished["passed"])
                self.assertIsNone(result["launchFrame"])

    def test_ordinary_same_stantler_hop_does_not_stop_before_exact_release(self):
        stream = rows()
        ordinary = stream[-1]["samples"][0]["actors"][0]
        ordinary.update(motionKind="HOP", motionPhase="MOVING", motionDuration=7,
                        origin={"x": 585, "y": 400}, target={"x": 587, "y": 400})
        meter = WildThrowMovingCandidateMeasurement(SOURCE)
        for row in stream[:-1]:
            meter.observe_record(row)
        first = deepcopy(stream[-1])
        first["samples"] = first["samples"][:1]
        # Raw chunk receipts must describe this one completed frame exactly.
        first = step_row("natural-moving-pickup-and-launch", first["samples"])
        result = meter.observe_record(first)
        self.assertEqual(result["failures"], [])
        self.assertFalse(result["ready"])
        self.assertIsNone(result["launchFrame"])
        from tools.overworld.devtools_test_contract import TestEvaluator
        predicate = {"kind": "measurement-complete", "measurement": KIND, "when": "final"}
        evaluator = SimpleNamespace(specs={}, latest=meter.latest, uses_raw_records=False,
            measurements={KIND: meter}, frames=2, test={"budgets": {"minObservedFrames": 2}})
        self.assertFalse(TestEvaluator.check(evaluator, predicate))
        rest = step_row("natural-moving-pickup-and-launch", stream[-1]["samples"][1:])
        rest["events"] = deepcopy(stream[-1]["events"])
        result = meter.observe_record(rest)
        self.assertTrue(result["ready"], result["failures"])
        self.assertEqual(result["launchFrame"], 25)
        evaluator.latest = meter.latest
        self.assertTrue(TestEvaluator.check(evaluator, predicate))

    def test_current_sealed_initializer_keeps_exact_retained_quiet_pair(self):
        # Exact native pair retained from test-a963d36ae7fc44968c54cd128d564fe6.
        sample = {"frame": 831, "actorFrame": 363, "nativeCycle": 2140}
        def pair():
            return [{"frame": 831, "kind": "native-observation", "data": {
                "observation": kind, "sequence": sequence, "caller": caller,
                "sequenceId": 1501, "entryActorFrame": 363, "returnActorFrame": 363,
                "entryNativeCycle": 2139, "returnNativeCycle": 2139}}
                for kind, sequence, caller in (("sound-play", 1667, 0x02203C1E),
                                              ("sound-stop", 1668, 0x01FFF3C0))]
        def meter():
            value = WildThrowMovingCandidateMeasurement.__new__(WildThrowMovingCandidateMeasurement)
            value.latest = {"nativeCycle": 2137}
            value.sound_sequence = 1666
            value.quiet_bubble_pairs = []
            return value
        value = meter()
        value._bubble_sounds(sample, pair())
        self.assertEqual(len(value.quiet_bubble_pairs), 1)
        self.assertEqual(value.quiet_bubble_pairs[0]["playCaller"], 0x02203C1E)
        for fault in ("old-play-caller", "missing-play", "missing-stop", "wrong-stop-caller",
                      "wrong-id", "reversed-order", "late-stop", "wrong-actor-frame"):
            with self.subTest(fault=fault):
                events = pair()
                if fault == "old-play-caller": events[0]["data"]["caller"] = 0x02203C8E
                elif fault == "missing-play": events.pop(0)
                elif fault == "missing-stop": events.pop()
                elif fault == "wrong-stop-caller": events[1]["data"]["caller"] += 2
                elif fault == "wrong-id": events[1]["data"]["sequenceId"] += 1
                elif fault == "reversed-order": events.reverse()
                elif fault == "late-stop": events[1]["data"]["returnNativeCycle"] = 2141
                else: events[1]["data"]["entryActorFrame"] = 364
                with self.assertRaisesRegex(ValueError, "bubble sound"):
                    meter()._bubble_sounds(sample, events)

    def test_active_bubble_redundant_stop_keeps_real_pair_without_extra_credit(self):
        stream = rows()
        sample = stream[-1]["samples"][2]
        stop = bubble_events(sample)[1]
        stop["data"]["sequence"] = 102
        stream[-1]["events"].append(stop)
        done, result = evaluate(stream)
        self.assertTrue(done["passed"], result)
        self.assertEqual(len(result["quietBubbleSoundPairs"]), 1)
        for fault in ("no-pair", "old-cycle", "future-cycle", "actor-frame",
                      "completed-frame", "reused-sequence", "wrong-id"):
            bad = deepcopy(stream)
            call = bad[-1]["events"][-1]
            data = call["data"]
            if fault == "no-pair":
                bad[-1]["events"] = [call]
            elif fault == "old-cycle":
                data["entryNativeCycle"] = stream[-1]["samples"][1]["nativeCycle"]
            elif fault == "future-cycle":
                data["returnNativeCycle"] = sample["nativeCycle"] + 1
            elif fault == "actor-frame":
                data["entryActorFrame"] -= 1
            elif fault == "completed-frame":
                call["frame"] -= 1
            elif fault == "reused-sequence":
                data["sequence"] = 101
            else:
                data["sequenceId"] += 1
            with self.subTest(fault=fault):
                done, result = evaluate(bad)
                self.assertFalse(done["passed"], result)
                self.assertTrue(any("bubble sound" in message for message in result["failures"]), result)

    def test_quiet_bubble_pairs_and_exact_sound_fault_guards(self):
        done, result = evaluate(rows())
        self.assertTrue(done["passed"], result)
        self.assertEqual(len(result["quietBubbleSoundPairs"]), 1)
        from tools.overworld.test_devtools_cargo_route_continuity import alert_fixture
        route_meter, route_rows = alert_fixture()
        for sample, events, actor in route_rows: route_meter._route_sample(sample, events, actor)
        # Synthetic method fixture supplies only the new route claim. The old
        # copied stream still owns the original motion and quiet-audio checks.
        result["routeContinuity"] = route_meter.route_witness
        # Bind that finite synthetic route owner to this synthetic stream.
        subject=result['subjects']['geodude'];w=result['routeContinuity']
        for q in (w['baseline'],w['postAlert']):
            q['workspace']['owner']=deepcopy(subject['handle']);q['before']['owner']=deepcopy(subject['handle'])
        w['walk'].update(handle=deepcopy(subject['handle']),subjectIdentity=subject['subjectIdentity'])
        for q in w['walk']['queries']:
            q['workspace']['owner']=deepcopy(subject['handle']);q['before']['owner']=deepcopy(subject['handle'])
        for event in w['walk']['lifecycle']:
            event['data'].update(actorHandle=subject['handle']['value'],actor={k:v for k,v in subject['handle'].items() if k!='value'})
        w['nativeStart']['data'].update(actorHandle=subject['handle']['value'],
            actor={k:v for k,v in subject['handle'].items() if k!='value'})
        replay = {"passed": True, "observedFrames": result["observedFrames"],
                  "measurements": {KIND: result}}
        self.assertEqual(measurements(rows(), replay)["quietBubbleSoundPairs"],
                         result["quietBubbleSoundPairs"])
        bad = deepcopy(replay); bad["measurements"][KIND]["quietBubbleSoundPairs"][0]["stopCaller"] += 2
        with self.assertRaisesRegex(ValueError, "quiet bubble sound proof"):
            measurements(rows(), bad)
        for fault in ("play-return-reversed", "stop-overlaps-play", "stop-return-reversed", "late-stop"):
            bad=deepcopy(replay);pair=bad["measurements"][KIND]["quietBubbleSoundPairs"][0]
            if fault=="play-return-reversed":pair["playReturnNativeCycle"]=pair["playEntryNativeCycle"]-1
            elif fault=="stop-overlaps-play":pair["stopEntryNativeCycle"]=pair["playReturnNativeCycle"]-1
            elif fault=="stop-return-reversed":pair["stopReturnNativeCycle"]=pair["stopEntryNativeCycle"]-1
            else:pair["stopReturnNativeCycle"]=pair["completedNativeCycle"]+1
            with self.subTest(proof_clock=fault),self.assertRaisesRegex(ValueError,"quiet bubble sound proof"):
                measurements(rows(),bad)
        for fault in SOUND_FAULTS:
            with self.subTest(fault=fault):
                done, result = evaluate(faulted_rows(rows(), fault))
                self.assertFalse(done["passed"], result)
                self.assertTrue(any("bubble sound" in message for message in result["failures"]), result)
        # A zero-queue native cycle can follow the synchronous pair before
        # its completed snapshot. Keep both calls inside that frame interval.
        stream = rows(); sample = stream[-1]["samples"][1]
        def next_cycle(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    if key == "nativeCycle": value[key] += 1
                    else: next_cycle(nested)
            elif isinstance(value, list):
                for nested in value: next_cycle(nested)
        for later in stream[-1]["samples"][1:]: next_cycle(later)
        stream[-1]["cycleIntervals"].insert(1, {"completedGameFrame": 19, "cpuNs": 1, "wallNs": 1})
        stream[-1]["nativeCycles"] += 1
        done, result = evaluate(stream)
        self.assertTrue(done["passed"], result)
        # Play can cross VBlank. Stop follows its return, within this same
        # completed queue and Actor frame; it cannot overlap or escape it.
        for delayed_entry in (False,True):
            split=deepcopy(stream);play,stop=split[-1]["events"][:2]
            completed=split[-1]["samples"][1]["nativeCycle"]
            play["data"]["returnNativeCycle"]=completed if not delayed_entry else completed-1
            stop["data"].update(entryNativeCycle=completed,returnNativeCycle=completed)
            done,result=evaluate(split)
            with self.subTest(delayed_entry=delayed_entry):self.assertTrue(done["passed"],result)
            pair=result["quietBubbleSoundPairs"][0]
            self.assertLessEqual(pair["playReturnNativeCycle"],pair["stopEntryNativeCycle"])
            for fault in ("overlap","reversed-play","reversed-stop","old-entry","future-return",
                          "actor-frame","completed-frame","reused-sequence"):
                bad=deepcopy(split);p,t=bad[-1]["events"][:2]
                if fault=="overlap":t["data"]["entryNativeCycle"]=p["data"]["returnNativeCycle"]-1
                elif fault=="reversed-play":p["data"]["returnNativeCycle"]=p["data"]["entryNativeCycle"]-1
                elif fault=="reversed-stop":t["data"]["returnNativeCycle"]=t["data"]["entryNativeCycle"]-1
                elif fault=="old-entry":p["data"]["entryNativeCycle"]=bad[-1]["samples"][0]["nativeCycle"]
                elif fault=="future-return":t["data"]["returnNativeCycle"]=completed+1
                elif fault=="actor-frame":t["data"]["entryActorFrame"]+=1
                elif fault=="completed-frame":t["frame"]+=1
                else:t["data"]["sequence"]=p["data"]["sequence"]
                done,result=evaluate(bad)
                with self.subTest(delayed_entry=delayed_entry,fault=fault):
                    self.assertFalse(done["passed"],result)
                    self.assertTrue(any("bubble sound" in m for m in result["failures"]),result)

    def test_moving_pickup_requires_exact_native_cancel_then_held(self):
        baseline = rows()
        done, result = evaluate(baseline)
        self.assertTrue(done["passed"], result)
        witness = result["movingPickup"]
        self.assertEqual((witness["previous"]["frame"], witness["frame"], witness["motionIdentity"]), (22, 23, 31))
        for fault in PICKUP_FAULTS:
            with self.subTest(fault=fault):
                changed = faulted_rows(baseline, fault)
                self.assertNotEqual(changed, baseline)
                self.assertEqual(baseline, rows())
                done, result = evaluate(changed)
                self.assertFalse(done["passed"], result)
                self.assertTrue(any("moving pickup" in m for m in result["failures"]), result)
        # Missing/stale full owner, native bytes, current Field, and claim are
        # checked again by the same helper used for accepted proof.
        for fault in ("stale-owner", "raw-plan", "timer-owner", "clock", "carrier-cancel", "old-commit", "missing-mask", "stopped-body"):
            bad = deepcopy(witness)
            before, after = bad["previous"],bad["current"]
            target = next(a for a in before["actors"] if a["species"] == 234)
            if fault == "stale-owner": target["handle"]["generation"] += 1
            elif fault == "raw-plan": before["pokemonCombat"]["targets"][0]["motion"]["plan"]["reservationId"] += 1
            elif fault == "timer-owner": before["pokemonCombat"]["movementTimers"][0]["sourceIdentity"]["object"] += 4
            elif fault == "clock": after["actorFrame"] += 1
            elif fault == "carrier-cancel":
                e = deepcopy(bad["events"][0]);owner=witness_subjects(baseline)["geodude"]["handle"]
                e["data"].update(actorHandle=owner["value"],actor={k:v for k,v in owner.items() if k!="value"})
                bad["events"].append(e)
            elif fault == "old-commit": bad["events"][0]["data"]["event"] = "LOGICAL_COMMIT"
            elif fault == "stopped-body": target["engineObject"]["pos_z"]=(target["origin"]["y"]<<16)+32768
            else:
                state=after["pokemonCombat"]["interactions"]["throwState"];state["targetMask"]=0
                state["rawHex"]=(bytes(state["targets"])+struct.pack("<3H",0,state["carrierMask"],0)).hex()
            with self.subTest(fault=fault), self.assertRaises((ValueError, KeyError)):
                moving_pickup_witness(before,after,bad["events"],SOURCE,witness_subjects(baseline))

    def test_moving_pickup_keeps_native_owner_when_movement_flags_change(self):
        stream = rows()
        _, result = evaluate(stream)
        witness = deepcopy(result["movingPickup"])
        for sample, flags in ((witness["previous"], 58373), (witness["current"], 312321)):
            cargo = next(a for a in sample["actors"] if a["species"] == 234)
            pointer = cargo["engineIdentity"]["pointer"]
            cargo["engineIdentity"].update(manager_index=10, in_manager=True, active=True,
                object_id=224, object_map_id=33, script_id=2074,
                object_manager=0x02101000, current_manager=0x02101000,
                id_lookup=dict(status="complete", source="stock-first-active-id-semantics",
                    requested_id=224, object_count=64, capacity_limit=64,
                    first_active_pointer=pointer, first_active_index=10,
                    eligible_count=1, pointer_matches=True,
                    matching_objects=[dict(pointer=pointer, manager_index=10,
                        object_id=224, object_map_id=33, script_id=2074,
                        flags=flags, active=True, flag25=False, lookup_eligible=True)]))
        saved = deepcopy(witness)
        subjects = witness_subjects(stream)
        def check(value):
            return moving_pickup_witness(value["previous"], value["current"],
                                         value["events"], SOURCE, subjects)
        self.assertEqual(check(witness)["motionIdentity"], 31)
        self.assertEqual(witness, saved)
        for fault in ("pointer", "object_manager", "current_manager", "manager_index",
                      "object_id", "object_map_id", "script_id", "lookup-pointer",
                      "lookup-id", "lookup-map", "lookup-script", "full-handle",
                      "unverified", "inactive-flags", "excluded-flags"):
            bad = deepcopy(witness)
            cargo = next(a for a in bad["current"]["actors"] if a["species"] == 234)
            engine = cargo["engineIdentity"]
            if fault in engine:
                engine[fault] += 1
            elif fault.startswith("lookup-"):
                key = {"pointer":"pointer", "id":"object_id", "map":"object_map_id", "script":"script_id"}[fault[7:]]
                engine["id_lookup"]["matching_objects"][0][key] += 1
            elif fault == "full-handle":
                cargo["handle"]["generation"] += 1
            elif fault == "unverified":
                cargo["identityVerified"] = False
            elif fault == "inactive-flags":
                engine["id_lookup"]["matching_objects"][0]["flags"] &= ~1
            else:
                engine["id_lookup"]["matching_objects"][0]["flags"] |= 1 << 25
            with self.subTest(fault=fault), self.assertRaises((ValueError, KeyError)):
                check(bad)

    def test_native_wander_spawn_accepts_relocation_and_rejects_wrong_input(self):
        snap = current(12, target=True)
        snap["actors"][0]["logical"] = {"x": 587, "y": 396}
        receipt = wander_receipt(snap)
        self.assertEqual(verify_wander_spawn(receipt, snap)["position"],
                         (587, 396))
        for wrong_start in (400, 401, 404):
            bad = deepcopy(receipt)
            bad["events"][0]["data"]["finalization"]["receipt"]["inputPosition"] = [585, wrong_start]
            with self.subTest(wrong_start=wrong_start), self.assertRaisesRegex(ValueError, "finalization"):
                verify_wander_spawn(bad, snap)


if __name__ == "__main__":
    unittest.main()
