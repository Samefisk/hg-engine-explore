"""Host route controls. Synthetic rows do not prove a route in the game."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld.devtools_d1_routes import GOLDENROD, GOLDENROD35, descriptor, warmup_admissions
from tools.overworld import control
from tools.overworld.devtools_test_contract import (
    validate_test, _d1_warmup_initial, _d1_warmup_observe, _d1_warmup_arm,
)
from tools.overworld import test_devtools_spawn_work_budget as short_fixture
from tools.overworld import test_devtools_unmounted_zero_stutter as long_fixture
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
NAMES = ("population.spawn-work-budget", "world.unmounted.spawn-zero-stutter")


def recipe(name):
    return json.loads((ROOT / "tests/overworld/test-recipes" / (name + ".json")).read_text())


def remap_context(value):
    """Reuse the old independent work/clock fault corpus on the second map pair."""
    if isinstance(value, list):
        return [remap_context(v) for v in value]
    if isinstance(value, dict):
        return {k: ({33: 76, 67: 38}.get(v, v) if k in (
            "mapId", "map_id", "object_map_id", "current_map_id", "spawn_map_id") else remap_context(v))
                for k, v in value.items()}
    return value


def goldenrod_replay(fixture, fault=None):
    original_type = fixture.SpawnWorkBudgetMeasurement if fixture is short_fixture else fixture.UnmountedZeroStutterMeasurement
    meter_name = "SpawnWorkBudgetMeasurement" if fixture is short_fixture else "UnmountedZeroStutterMeasurement"
    selected = []

    def construct(test, source, *, max_frames):
        test = deepcopy(test)
        test["measurements"] = [{"kind": fixture.KIND, "subject": "mankey", "route": GOLDENROD}]
        meter = original_type(test, source, max_frames=max_frames)
        arm, observe = meter.arm, meter.observe

        def arm_route(subject, snapshot, **kwargs):
            snapshot = remap_context(snapshot)
            snapshot["context"]["mapId"] = 76
            snapshot["player"].update(x=358, y=383, x_prev=358, y_prev=383)
            return arm(subject, snapshot, **kwargs)

        def observe_route(snapshot, events):
            snapshot, events = remap_context(snapshot), remap_context(events)
            player = snapshot["player"]
            if fixture is short_fixture and snapshot["frame"] == 101:
                player.update(x=358, y=384)
            if fixture is long_fixture and player["x"] == player["x_prev"] == 565:
                player.update(x=358, x_prev=358, y=385, y_prev=385,
                              pos_x=358 * 65536 + 32768, pos_z=385 * 65536 + 32768)
            return observe(snapshot, events)

        meter.arm, meter.observe = arm_route, observe_route
        selected.append(meter)
        return meter

    negative_name = "SpawnWorkBudgetNegative" if fixture is short_fixture else "UnmountedZeroStutterNegative"
    negative_type = getattr(fixture, negative_name)

    def construct_negative(fault, **kwargs):
        negative = negative_type(fault, measurement=selected[0])
        mutate = negative.mutate

        def mutate_route(row, subjects):
            row = remap_context(row)
            if fixture is long_fixture:
                for sample in row.get("samples", []):
                    player = sample["player"]
                    if player["x"] == player["x_prev"] == 565:
                        player.update(x=358, x_prev=358, y=385, y_prev=385,
                            pos_x=358 * 65536 + 32768, pos_z=385 * 65536 + 32768)
            return mutate(row, subjects)

        negative.mutate = mutate_route
        return negative

    with patch.object(fixture, meter_name, construct), patch.object(fixture, negative_name, construct_negative):
        return fixture.replay(fault) if fixture is short_fixture else fixture.run(fault)


class D1GoldenrodRouteTests(unittest.TestCase):
    def test_current_recipes_are_sealed_and_registered(self):
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())["sharedTests"]
        for name in NAMES:
            value = recipe(name)
            self.assertEqual(validate_test(value)["measurements"][0]["route"],
                             GOLDENROD35 if name == "population.spawn-work-budget" else GOLDENROD)
            self.assertEqual(registry[name]["recipeSha256"], hashlib.sha256(
                (ROOT / "tests/overworld/test-recipes" / (name + ".json")).read_bytes()).hexdigest())
            for fault in ("start", "warmup", "pause", "corner", "skip", "frames", "unknown-route"):
                changed = deepcopy(value)
                if fault == "start": changed["setup"][0]["args"]["predicate"]["x"] += 1
                elif fault == "warmup": changed["setup"][1]["args"]["keys"] = ["LEFT", "B"]
                elif fault == "pause": changed["actions"][-1]["budget"]["maxFrames"] += 1
                elif fault == "corner": changed["actions"][3]["args"]["predicate"] = {"kind": "player-settled-at", "map": 38, "x": 357, "z": 399}
                elif fault == "skip": changed["setup"][1]["skipIf"] = {"kind": "player-field", "path": "x", "operator": "eq", "value": 358}
                elif fault == "frames": changed["budgets"]["minObservedFrames"] -= 1
                else: changed["measurements"][0]["route"] = "unreviewed-route"
                with self.subTest(name=name, fault=fault), self.assertRaises(ValueError):
                    validate_test(changed)

    def test_goldenrod_warmup_requires_all17_exact_native_admissions(self):
        subject = {"active": True, "species": 56, "role": "FOLLOWER", "identityVerified": True,
                   "subjectIdentity": 2920357538}
        current = {"frame": 1, "prepared": False, "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion",
            "fieldControl": {"taskPointer": 0}, "context": {"mapId": 76},
            "actors": [subject], "party": [{"species": 56, "personality": 2920357538,
                "identityVerified": True, "hp": 15}], "selector": {"physicalPressed": 0},
            "nativeObservation": {"playerStepCount": 0, "coverageComplete": True,
                "error": None, "eventsDropped": 0}, "player": {"x": 358, "y": 366}}
        state = _d1_warmup_initial(current, GOLDENROD)
        for count in range(1, 18):
            origin, target = [358, 365 + count], [358, 366 + count]
            event = {"kind": "native-observation", "data": {
                "observation": "player-step-admitted", "setupMode": "normal", "stepIndex": count,
                "mapId": 76, "direction": 1, "origin": origin, "target": target,
                "objectBefore": dict(x=origin[0], y=origin[1]),
                "objectAfter": dict(x=target[0], y=target[1]), "objectPointer": 100, "returnValue": 100}}
            current["frame"] += 1
            current["player"].update(x=358, y=target[1])
            current["nativeObservation"]["playerStepCount"] = count
            for fault in ("missing", "direction", "map", "identity", "prepared"):
                copied, bad_event = deepcopy(current), deepcopy(event)
                if fault == "direction": bad_event["data"]["direction"] = 3
                elif fault == "map": bad_event["data"]["mapId"] = 38
                elif fault == "identity": copied["actors"][0]["subjectIdentity"] += 1
                elif fault == "prepared": copied["prepared"] = True
                with self.subTest(count=count, fault=fault), self.assertRaises(ValueError):
                    _d1_warmup_observe(deepcopy(state), copied, [] if fault == "missing" else [bad_event])
            _d1_warmup_observe(state, current, [event])
        current["player"].update(x_prev=358, y_prev=383, flags=1, movement_cmd=1,
            pos_x=358 * 65536 + 32768, pos_z=383 * 65536 + 32768, unk88_y=0)
        _d1_warmup_arm(state, current, subject)
        self.assertEqual(len(warmup_admissions(GOLDENROD)), 17)
        for key in ("x", "y", "pos_z"):
            copied = deepcopy(current);copied["player"][key] += 1
            with self.subTest(terminal=key), self.assertRaises(ValueError):
                _d1_warmup_arm(state, copied, subject)

    def test_full_short_work_witness_and_each_existing_fault_stay_effective(self):
        result = goldenrod_replay(short_fixture)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["route"], GOLDENROD)
        rows = short_fixture.measurements(
            {"passed": True, "failures": [], "measurements": {short_fixture.KIND: result}},
            {"sessionId": "host", "sessionCleanup": {"sessionId": "host", "closed": True, "errors": []}})
        self.assertTrue(all(row["passed"] for row in rows))
        for fault in short_fixture.FAULTS:
            with self.subTest(fault=fault):
                changed = goldenrod_replay(short_fixture, fault)
                self.assertFalse(changed["passed"])
                short_fixture.validate_negative_result({"passed": False, "measurements": {short_fixture.KIND: changed}}, fault)

    def test_full_long_work_witness_and_each_existing_fault_stay_effective(self):
        result = goldenrod_replay(long_fixture)
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(result["frames"], 2600)
        self.assertGreaterEqual(result["pacing"]["movingFrameCount"], 1800)
        self.assertEqual(result["pacing"]["lateMainLoopCount"], 0)
        rows = long_fixture.measurements(
            {"passed": True, "failures": [], "measurements": {long_fixture.KIND: result}},
            {"sessionId": "host", "sessionCleanup": {"sessionId": "host", "closed": True, "errors": []}})
        self.assertTrue(all(row["passed"] for row in rows))
        for fault in long_fixture.FAULTS:
            with self.subTest(fault=fault):
                changed = goldenrod_replay(long_fixture, fault)
                self.assertFalse(changed["passed"])
                long_fixture.validate_negative_result({"passed": False, "measurements": {long_fixture.KIND: changed}}, fault)


class D1GoldenrodTailDetourTests(unittest.TestCase):
    def test_long_tail_has_one_fixed_east_detour_per_remaining_lap(self):
        value = recipe("world.unmounted.spawn-zero-stutter")
        actions = value["actions"]
        first = next(i for i, a in enumerate(actions) if a["id"] == "route-042-detour-east")
        self.assertEqual(first, 82)
        self.assertEqual([a["id"] for a in actions[:first]], [
            name for i in range(1, 42) for name in (f"route-{i:03d}", f"route-{i:03d}-settle")])
        detours = [a for a in actions if a["op"] == "step" and a["id"].endswith("-detour-east")]
        self.assertEqual([a["id"] for a in detours], [f"route-{i:03d}-detour-east" for i in range(42, 83, 4)])
        for index in range(42, 83, 4):
            begin = next(i for i, a in enumerate(actions) if a["id"] == f"route-{index:03d}-detour-east")
            lap = actions[begin:begin + 10]
            self.assertEqual([a["args"]["keys"] for a in lap[::2]],
                             [["RIGHT"], ["DOWN"], ["LEFT"], ["UP"], ["RIGHT"]])
            self.assertEqual([(a["args"]["predicate"]["x"], a["args"]["predicate"]["z"])
                              for a in lap[1::2]],
                             [(359, 385), (359, 399), (356, 399), (356, 385), (358, 385)])
            self.assertTrue(all("skipIf" not in a for a in lap))
        self.assertEqual(value["budgets"], {"maxSeconds": 900, "maxFrames": 4000,
            "noProgressFrames": 600, "minObservedFrames": 2600})
        self.assertEqual(actions[-1]["args"]["predicate"], {
            "kind": "measurement-complete", "measurement": "unmounted-zero-stutter-v1", "when": "final"})

    def test_copied_tail_changes_fail_the_sealed_controller_even_with_new_recipe_hash(self):
        original = recipe("world.unmounted.spawn-zero-stutter")
        registration = D1ControllerRegistrationTests().registration
        registration(original)
        for fault in ("missing-detour", "wrong-road", "wide-detour", "skip-detour", "frame-floor"):
            changed = deepcopy(original)
            begin = next(i for i, a in enumerate(changed["actions"]) if a["id"] == "route-042-detour-east")
            if fault == "missing-detour":
                del changed["actions"][begin:begin + 2]
            elif fault == "wrong-road":
                changed["actions"][begin + 3]["args"]["predicate"]["x"] = 358
            elif fault == "wide-detour":
                changed["actions"][begin]["args"]["until"]["value"] = 360
            elif fault == "skip-detour":
                changed["actions"][begin]["skipIf"] = {"kind": "player-field", "path": "x",
                    "operator": "eq", "value": 358, "when": "final"}
            else:
                changed["budgets"]["minObservedFrames"] -= 1
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                registration(changed)


class D1ControllerRegistrationTests(unittest.TestCase):
    """Reach the actual pre-session guard, after recipe validation and sealing."""

    def registration(self, value, registry=None):
        if registry is None:
            registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        with TemporaryDirectory(prefix="d1-controller-registration-") as directory:
            root = Path(directory)
            target = root / "tests/overworld/test-recipes" / (value["id"] + ".json")
            table = root / "tools/overworld/runtime_proof_registry.json"
            target.parent.mkdir(parents=True)
            table.parent.mkdir(parents=True)
            content = json.dumps(value).encode()
            target.write_bytes(content)
            registry = deepcopy(registry)
            registry["sharedTests"][value["id"]]["recipeSha256"] = hashlib.sha256(content).hexdigest()
            table.write_text(json.dumps(registry))
            return control._shared_test_registration(value, root)

    def test_canonical_goldenrod_recipes_reach_the_actual_controller_guard(self):
        for name in NAMES:
            with self.subTest(name=name):
                actual, digest = control._shared_test_registration(recipe(name), ROOT)
                self.assertEqual(actual["recipeSha256"], digest)
                self.assertEqual(actual["mode"], "normal")

    def test_original_cherrygrove_routes_still_pass_the_controller_guard(self):
        from tools.overworld.test_devtools_test_contract import D1WarmupTests
        for name in NAMES:
            with self.subTest(name=name):
                original = D1WarmupTests().load(name)
                actual, digest = self.registration(original)
                self.assertEqual(actual["recipeSha256"], digest)

    def test_copied_bad_routes_are_rejected_even_with_a_matching_recipe_hash(self):
        for name in NAMES:
            for fault in ("unknown-route", "missing-route", "wrong-corner", "skipped-move", "frame-floor"):
                changed = recipe(name)
                if fault == "unknown-route": changed["measurements"][0]["route"] = "unreviewed-route"
                elif fault == "missing-route": changed["measurements"][0].pop("route")
                elif fault == "wrong-corner":
                    settle = next(a for a in changed["actions"] if a["op"] == "wait"
                                  and "x" in a["args"]["predicate"])
                    settle["args"]["predicate"]["x"] += 1
                elif fault == "skipped-move":
                    changed["actions"][0]["skipIf"] = {"kind": "player-field", "path": "x", "operator": "eq", "value": 358}
                else: changed["budgets"]["minObservedFrames"] -= 1
                with self.subTest(name=name, fault=fault), self.assertRaises(ValueError):
                    self.registration(changed)

    def test_runtime_route_guard_still_rejects_when_the_recipe_guard_is_removed(self):
        # A copied faulty validator must not make a sealed but wrong action
        # sequence acceptable to the controller's independent route check.
        for name in NAMES:
            for fault in ("wrong-corner", "skipped-move", "missing-route"):
                changed = recipe(name)
                if fault == "wrong-corner":
                    settle = next(a for a in changed["actions"] if a["op"] == "wait"
                                  and "x" in a["args"]["predicate"])
                    settle["args"]["predicate"]["x"] += 1
                elif fault == "skipped-move":
                    changed["actions"][0]["skipIf"] = {"kind": "player-field", "path": "x", "operator": "eq", "value": 358}
                else:
                    changed["measurements"][0].pop("route")
                with self.subTest(name=name, fault=fault), patch(
                        "tools.overworld.devtools_test_contract.validate_test", side_effect=lambda value: value), \
                        self.assertRaisesRegex(control.ValidationFailure, "sealed route actions"):
                    self.registration(changed)

    def test_copied_registration_guards_keep_claims_work_and_zero_late_limits(self):
        original = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        for name in NAMES:
            for fault in ("claim", "proof-level", "requirements", "preparation-or-moving-floor", "late-loops"):
                registry = deepcopy(original)
                entry = registry["sharedTests"][name]
                if fault == "claim": entry["claims"].pop()
                elif fault == "proof-level": entry["proofLevel"] = "S4"
                elif fault == "requirements": entry["requirements"] = ["unreviewed-requirement"]
                else:
                    rows = entry["measurementContract"]
                    if fault == "late-loops":
                        row = next(r for r in rows["frame-pacing"] if r["name"].endswith("late-main-loop-count"))
                        row["expected"] = 1
                    elif name == NAMES[0]:
                        rows["profile-resolution"][0]["expected"] = 2
                    else:
                        rows["natural-input"][0]["minimum"] -= 1
                with self.subTest(name=name, fault=fault), self.assertRaisesRegex(
                        control.ValidationFailure, "exact .*contract|exact spawn-work route"):
                    self.registration(recipe(name), registry)



class D1Route35Tests(unittest.TestCase):
    """The short route changes location; every work and pacing gate remains."""
    def current(self, map_id=76, x=358, z=366, epoch=2, generation=2, frame=1):
        handle=dict(value=(generation<<16)|7,slot=7,generation=generation,
                    fieldEpoch=epoch,mapGeneration=generation,encounterGeneration=1)
        actor=dict(active=True,species=56,role="FOLLOWER",subjectIdentity=2920357538,
            identityVerified=True,presentationAttached=True,authorityGeneration=1,
            engineAnchorGeneration=1,presentationGeneration=1,handle=handle,engineIdentity={})
        return dict(frame=frame,nativeCycle=frame*2,actorFrame=frame,prepared=False,
            fieldAvailable=True,observationBoundary="main-task-queue-completion",
            fieldControl=dict(taskPointer=0),context=dict(mapId=map_id,fieldEpoch=epoch,mapGeneration=generation),
            actors=[actor],party=[dict(species=56,personality=2920357538,identityVerified=True,hp=15)],
            selector=dict(physicalPressed=0),nativeObservation=dict(sequence=0,playerStepCount=0,
                coverageComplete=True,error=None,eventsDropped=0),
            player=dict(x=x,y=z,x_prev=x,y_prev=z,pos_x=(x<<16)+32768,pos_z=(z<<16)+32768,
                        flags=1,movement_cmd=1,unk88_y=0))

    def absent(self, frame, count):
        return dict(frame=frame,nativeCycle=frame*2,prepared=False,fieldAvailable=False,
            observationBoundary="main-task-queue-completion",fieldAvailability=dict(fieldPointer=0,
                actorStateMagic=0,reasons=["null-field-pointer","actor-system-uninitialized"]),
            nativeObservation=dict(sequence=0,playerStepCount=count,coverageComplete=True,error=None,eventsDropped=0),
            observationErrors=[],romSha256="a"*64,sourceSaveSha256="b"*64)

    def test_gate_input_stops_at_admission_before_neutral_arrival(self):
        from tools.overworld.devtools_d1_routes import route35_actions
        from tools.overworld.devtools_movement_predicates import check_movement_predicate
        from tools.overworld.devtools_jobs import TestJobs
        actions=route35_actions(short_fixture.KIND)
        gate,arrival,follower=actions[:3]
        start=self.current(101,5,3,3,3,986);start['nativeObservation']['playerStepCount']=50
        admitted=self.current(101,5,2,3,3,987);admitted['nativeObservation']['playerStepCount']=51
        ready=self.current(39,358,316,4,4,1029);ready['nativeObservation']['playerStepCount']=51
        for sample in (start,admitted,ready):sample['nativeObservation']['playerStepFrame']=sample['frame']
        self.assertFalse(check_movement_predicate(gate['args']['until'],start))
        self.assertTrue(check_movement_predicate(gate['args']['until'],admitted))
        self.assertFalse(check_movement_predicate(arrival['args']['predicate'],admitted))
        self.assertTrue(check_movement_predicate(arrival['args']['predicate'],ready))
        self.assertEqual(gate['args']['keys'],['UP'])
        self.assertEqual(arrival['op'],'wait')
        self.assertNotIn('keys',arrival['args'])
        self.assertEqual(follower['id'],'route35-current-follower')
        self.assertEqual(TestJobs._chunk_frames(gate,None,16,'observe'),1)
        self.assertEqual(sum(a['budget']['maxFrames'] for a in (gate,arrival)),160)
        self.assertEqual(sum(a['budget']['maxSeconds'] for a in (gate,arrival)),45)
        value=recipe('population.spawn-work-budget')
        self.assertEqual(value['actions'],actions)
        validate_test(value)
        for fault in ('hold-through-arrival','early-count','late-count','arrival-map','arrival-tile','held-wait','cap'):
            changed=deepcopy(value)
            if fault=='hold-through-arrival':changed['actions'][0]['args']['until']=deepcopy(arrival['args']['predicate'])
            elif fault=='early-count':changed['actions'][0]['args']['until']['value']=50
            elif fault=='late-count':changed['actions'][0]['args']['until']['value']=52
            elif fault=='arrival-map':changed['actions'][1]['args']['predicate']['map']=101
            elif fault=='arrival-tile':changed['actions'][1]['args']['predicate']['z']=315
            elif fault=='held-wait':changed['actions'][1]['args']['keys']=['UP']
            else:changed['actions'][1]['budget']['maxFrames']+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_test(changed)

    def test_route35_warmup_has_no_extra_wait_or_prepared_action(self):
        from tools.overworld.devtools_test_contract import _d1_warmup_setup
        value=recipe('population.spawn-work-budget');setup=value['setup']
        self.assertEqual((setup[0]['id'],setup[1]['id']),
                         ('warmup-city-start','warmup-north-gate'))
        self.assertEqual(setup[:6],_d1_warmup_setup(GOLDENROD35))
        self.assertFalse(any(a['id']=='warmup-city-hold' for a in setup))
        self.assertEqual(len(warmup_admissions(GOLDENROD35)),50)
        self.assertEqual((value['budgets']['maxFrames'],value['budgets']['maxSeconds'],
                          value['budgets']['minObservedFrames']),(720,180,120))
        for fault in ('extra-wait','held-wait','prepared-op','skip','counter'):
            changed=deepcopy(value)
            if fault in ('extra-wait','held-wait'):
                changed['setup'].insert(1,{'id':'warmup-city-hold','op':'step',
                    'args':{'frames':64,'keys':['UP'] if fault=='held-wait' else []},
                    'budget':{'maxSeconds':30,'maxFrames':64,'noProgressFrames':64}})
            elif fault=='prepared-op':changed['setup'][1]['op']='spawn'
            elif fault=='skip':changed['setup'][1]['skipIf']={'kind':'player-step-count','operator':'eq','value':0,'when':'final'}
            else:changed['setup'][1]['args']['until']['value']=40
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_test(changed)

    def test_all50_native_admissions_and_fresh_gatehouse_handle(self):
        state=_d1_warmup_initial(self.current(),GOLDENROD35)
        old=deepcopy(state["initialHandle"])
        for count,(map_id,direction,origin,target) in enumerate(warmup_admissions(GOLDENROD35),1):
            if count==42:
                missing=self.absent(43,41)
                _d1_warmup_observe(state,missing,[])
                arrival=self.current(101,5,12,3,3,44);arrival["nativeObservation"]["playerStepCount"]=41
                _d1_warmup_observe(state,arrival,[])
            sample=self.current(map_id,*target,2 if map_id==76 else 3,2 if map_id==76 else 3,count+1 if count<=41 else count+3)
            sample["nativeObservation"]["playerStepCount"]=count
            data=dict(observation="player-step-admitted",setupMode="normal",stepIndex=count,
                mapId=map_id,direction=direction,origin=origin,target=target,
                objectBefore=dict(x=origin[0],y=origin[1]),objectAfter=dict(x=target[0],y=target[1]),
                objectPointer=100 if map_id==76 else 200,returnValue=100 if map_id==76 else 200)
            event=dict(kind="native-observation",data=data)
            for fault in ("missing","wrong-map","prepared","changed-party"):
                changed,copied=deepcopy(sample),deepcopy(event)
                if fault=="wrong-map":copied["data"]["mapId"]=38
                elif fault=="prepared":changed["prepared"]=True
                elif fault=="changed-party":changed["actors"][0]["subjectIdentity"]+=1
                with self.subTest(count=count,fault=fault),self.assertRaises(ValueError):
                    _d1_warmup_observe(deepcopy(state),changed,[] if fault=="missing" else [copied])
            _d1_warmup_observe(state,sample,[event])
        _d1_warmup_arm(state,sample,sample["actors"][0])
        stale=deepcopy(sample["actors"][0]);stale["handle"]=old
        with self.assertRaisesRegex(ValueError,"new full field handle"):
            _d1_warmup_arm(state,sample,stale)
        with self.assertRaises(ValueError):
            _d1_warmup_observe(_d1_warmup_initial(self.current(),GOLDENROD35),self.absent(2,0),[])

    def test_gate_field_can_arrive_before_actor_context_rebind(self):
        # Current3713 frame901: stock Field101 is present and busy, while the
        # previous full follower handle is canceled and Actor context is2/2.
        state=_d1_warmup_initial(self.current(frame=712),GOLDENROD35)
        state.update(count=41,gateAdmitted=True,gateFrames=10,object=100)
        old=deepcopy(state)
        pending=self.current(101,5,12,2,2,901)
        pending['nativeObservation']['playerStepCount']=41
        pending['fieldControl']['taskPointer']=36573584
        pending['actors'][0]['motionPhase']='CANCELED'
        _d1_warmup_observe(state,pending,[])
        self.assertEqual(state,dict(old,gateFrames=11))
        with self.assertRaisesRegex(ValueError,'normal field control'):
            _d1_warmup_arm(state,pending,pending['actors'][0])

        ready=self.current(101,5,12,3,3,902)
        ready['nativeObservation']['playerStepCount']=41
        _d1_warmup_observe(state,ready,[])
        self.assertTrue(state['gateRebound'])
        self.assertEqual(state['reboundHandle'],ready['actors'][0]['handle'])
        self.assertNotEqual(state['reboundHandle'],old['initialHandle'])
        self.assertIsNone(state['object'])

        faults=('prepared','not-admitted','wrong-count','wrong-map','wrong-tile','not-busy',
                'unknown-task','changed-party','missing-party','dead-party','unverified-party',
                'new-admission','over-bound','second-rebuild','one-epoch-only')
        for fault in faults:
            copied=deepcopy(old);sample=deepcopy(pending);events=[]
            if fault=='prepared':sample['prepared']=True
            elif fault=='not-admitted':copied['gateAdmitted']=False
            elif fault=='wrong-count':copied['count']=40
            elif fault=='wrong-map':sample['context']['mapId']=39
            elif fault=='wrong-tile':sample['player']['x']+=1
            elif fault=='not-busy':sample['fieldControl']['taskPointer']=0
            elif fault=='unknown-task':sample['fieldControl']['taskPointer']=None
            elif fault=='changed-party':sample['party'][0]['personality']+=1
            elif fault=='missing-party':sample['party']=[]
            elif fault=='dead-party':sample['party'][0]['hp']=0
            elif fault=='unverified-party':sample['party'][0]['identityVerified']=False
            elif fault=='new-admission':events=[dict(kind='native-observation',data=dict(observation='player-step-admitted'))]
            elif fault=='over-bound':copied['gateFrames']=120
            elif fault=='second-rebuild':copied['gateRebound']=True
            else:sample['context']['fieldEpoch']=3
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                _d1_warmup_observe(copied,sample,events)

        for fault in ('old-pair','one-half','old-handle','wrong-pid','unverified-source'):
            copied=deepcopy(old);sample=deepcopy(ready)
            if fault=='old-pair':sample['context']=deepcopy(pending['context'])
            elif fault=='one-half':sample['context']['mapGeneration']=2
            elif fault=='old-handle':sample['actors'][0]['handle']=deepcopy(old['initialHandle'])
            elif fault=='wrong-pid':sample['actors'][0]['subjectIdentity']+=1
            else:sample['actors'][0]['identityVerified']=False
            with self.subTest(ready_fault=fault),self.assertRaises(ValueError):
                _d1_warmup_observe(copied,sample,[])

    def test_sealed_gatehouse_steps_wait_for_follower_before_arm(self):
        state=_d1_warmup_initial(self.current(),GOLDENROD35)
        state.update(count=41,gateAdmitted=True,gateFrames=42,object=100)
        arrived=self.current(101,5,12,3,3,933)
        arrived['actors']=[];arrived['nativeObservation']['playerStepCount']=41
        _d1_warmup_observe(state,arrived,[])
        self.assertEqual(state['count'],41)
        self.assertNotIn('reboundHandle',state)
        for count,(map_id,direction,origin,target) in enumerate(warmup_admissions(GOLDENROD35)[41:],42):
            sample=self.current(map_id,*target,3,3,935+count-42)
            sample['actors']=[];sample['nativeObservation']['playerStepCount']=count
            data=dict(observation='player-step-admitted',setupMode='normal',stepIndex=count,
                mapId=map_id,direction=direction,origin=origin,target=target,
                objectBefore=dict(zip(('x','y'),origin)),objectAfter=dict(zip(('x','y'),target)),
                objectPointer=200,returnValue=200)
            event=dict(kind='native-observation',data=data)
            _d1_warmup_observe(state,sample,[event])
        self.assertEqual(state['count'],50)
        self.assertNotIn('reboundHandle',state)
        with self.assertRaisesRegex(ValueError,'normal field control'):
            _d1_warmup_arm(state,sample,dict(subjectIdentity=state['identity']))

        for fault in ('path','map','count51','party','stale-handle','bound','not-admitted','no-paired-context',
                      'wrong-tile','wrong-native-count'):
            copied=deepcopy(state);bad=deepcopy(sample);bad_events=[]
            if fault=='path':
                copied['count']=49;bad_events=[deepcopy(event)]
                bad_events[0]['data']['target']=[6,3]
            elif fault=='map':bad['context']['mapId']=39
            elif fault=='count51':copied['count']=51;bad['nativeObservation']['playerStepCount']=51
            elif fault=='party':bad['party'][0]['personality']+=1
            elif fault=='stale-handle':
                bad['actors']=deepcopy(self.current()['actors'])
                bad['actors'][0]['handle']=deepcopy(state['initialHandle'])
            elif fault=='bound':copied['gateFrames']=120
            elif fault=='not-admitted':copied['gateAdmitted']=False
            elif fault=='wrong-tile':bad['player']['x']+=1
            elif fault=='wrong-native-count':bad['nativeObservation']['playerStepCount']=49
            else:copied['context']['fieldEpoch']=bad['context']['fieldEpoch']=2
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                _d1_warmup_observe(copied,bad,bad_events)
        ready=self.current(101,5,3,3,3,945)
        ready['nativeObservation']['playerStepCount']=50
        _d1_warmup_observe(state,ready,[])
        self.assertEqual(state['reboundHandle'],ready['actors'][0]['handle'])
        _d1_warmup_arm(state,ready,ready['actors'][0])

    def test_normal_observation_warp_counts_all_queues_and_rebinds_once(self):
        from tools.overworld.devtools_spawn_work_budget_measurement import SpawnWorkBudgetMeasurement
        test=short_fixture.recipe();test["measurements"]=[dict(kind=short_fixture.KIND,subject="mankey",route=GOLDENROD35)]
        meter=SpawnWorkBudgetMeasurement(test,dict(schema={},sourceSha256="a"*64),max_frames=400)
        start=self.current(101,5,3);meter.arm(start["actors"][0],start)
        busy=self.current(101,5,2,frame=2);busy["fieldControl"]["taskPointer"]=0x02210000
        entry=dict(kind="native-observation",data=dict(observation="player-step-admitted",
            setupMode="normal",mapId=101,direction=0,origin=[5,3],target=[5,2]))
        self.assertTrue(meter.observe(busy,[entry])["gatePending"])
        self.assertTrue(meter.observe(self.absent(3,51),[])["gatePending"])
        restored=self.current(39,358,316,3,3,4)
        bad=deepcopy(meter);stale=deepcopy(restored);stale["actors"][0]["handle"]=start["actors"][0]["handle"]
        self.assertFalse(bad.observe(stale,[])["passed"])
        self.assertIn("new full follower handle",repr(bad.failures))
        result=meter.observe(restored,[])
        self.assertEqual(result["failures"],[])
        self.assertFalse(result["gatePending"])
        self.assertEqual(result["elapsedFrames"],3)
        self.assertEqual(result["frames"],1)
        self.assertEqual(result["subject"]["handle"],restored["actors"][0]["handle"])

    def test_current_bird_mask456_keeps_full_work_and_all_cost_faults(self):
        original=short_fixture.events
        def current(index):
            rows=deepcopy(original(index))
            for event in rows:
                if event.get("data",{}).get("observation")=="spawn-destination-search":
                    event["data"]["destinationMask"]=456
            return rows
        with patch.object(short_fixture,"events",current):
            result=short_fixture.replay()
            self.assertTrue(result["passed"],result["failures"])
            self.assertEqual(result["attempt"]["candidateQueryCount"],240)
            for fault in short_fixture.FAULTS:
                with self.subTest(fault=fault):
                    bad=short_fixture.replay(fault);self.assertFalse(bad["passed"])
                    short_fixture.validate_negative_result({"passed":False,"measurements":{short_fixture.KIND:bad}},fault)


    def test_unknown_destination_mask_still_cannot_supply_scan_proof(self):
        original=short_fixture.events
        def wrong(index):
            rows=deepcopy(original(index))
            for event in rows:
                if event.get("data",{}).get("observation")=="spawn-destination-search":
                    event["data"]["destinationMask"]=69
            return rows
        with patch.object(short_fixture,"events",wrong):
            result=short_fixture.replay()
            self.assertFalse(result["passed"])
            self.assertIn("complete explicit scan",repr(result["failures"]))


if __name__ == "__main__":
    unittest.main()
