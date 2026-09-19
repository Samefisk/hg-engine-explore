"""Typed Wild Walk setup and binding controls; no game execution."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_test_contract import (TestEvaluator, validate_test, WILD_WALK,
    WILD_CLEAR_CONTROL, _wild_spawn_setup, _handle)
from tools.overworld.test_devtools_test_contract import recipe as generic_recipe, snapshot as generic_snapshot
from tools.overworld.test_devtools_wild_walk_measurement import wild_fixture


def recipe(control=False):
    name = "observation.wild-clear-control" if control else "walk.wild.exact-frame"
    return json.loads(Path("tests/overworld/test-recipes",name+".json").read_text())


def spawn_setup(species=19, locomotion=0):
    snapshot,subject,_,_ = wild_fixture()
    actor = snapshot["actors"][0]
    actor["species"] = species
    actor["sourceIdentity"]["species"] = species
    encounter = dict(species=species,form=actor["form"],level=actor["level"],personality=actor["subjectIdentity"])
    world = dict(snapshot["context"],statePointer=0x02040000,fieldPointer=0x02050000)
    raw = struct.pack("<iiB3xIHBB4hBB",0,0,0,encounter["personality"],species,actor["form"],actor["level"],0,0,0,0,locomotion,0).hex()
    common = dict(slot=actor["handle"]["slot"],terrain=0,statePointer=world["statePointer"],fieldPointer=world["fieldPointer"],
        preparedPointer=0x02060000,worldContext=world,preparedPrefixHex=raw,preparedEncounter=encounter,
        startup=dict(target=[0,0],origin=[0,0],locomotion=locomotion,hopDirection=0),position=[0,0],returnValue=1)
    final = dict(common,observation="spawn-finalized",sequence=1,returnWorldContext=world,pairEligible=True)
    native = dict(common,observation="spawn-prepared",sequence=2,publicSubject=deepcopy(actor),finalization=dict(status="matched",receipt=final))
    receipt = dict(value=dict(slot=actor["handle"]["slot"],species=species,personality=actor["subjectIdentity"]),
        events=[dict(frame=snapshot["frame"],kind="native-observation",data=native)])
    return receipt,snapshot


def raw_replay(control=False, fault=None, startup_noop=False):
    """Drive the actual raw evaluator, including prepared native acquisition."""
    from tools.overworld.test_devtools_wild_clear_control_measurement import fixture as control_fixture
    value = recipe(control)
    kind = WILD_CLEAR_CONTROL if control else WILD_WALK
    evaluator = TestEvaluator(value);evaluator.install_measurements({kind:{"contractVersion":1}})
    baseline,_,reader,rows,calibration,close = control_fixture(startup_noop=startup_noop)
    initial=deepcopy(baseline);initial["actors"]=[];initial["fieldAvailable"]=True
    evaluator.observe_record(dict(phase="setup",initialSnapshot=initial,initialEvents=[],initialEventStartFrame=initial["frame"]))
    receipt,baseline=spawn_setup(); baseline["fieldAvailable"]=True
    spawn_event=receipt["events"][0]; final=spawn_event["data"]["finalization"]["receipt"]
    actor=baseline["actors"][0]
    receipt["events"].insert(0,dict(frame=baseline["frame"],kind="native-observation",data=deepcopy(final)))
    receipt["events"].append(dict(frame=baseline["frame"],kind="native",data=dict(traceStream=1,sequence=1,event="ACTOR_ATTACHED",
        actorHandle=actor["handle"]["value"],actor={k:v for k,v in actor["handle"].items() if k!="value"})))
    baseline["nativeObservation"]["sequence"]=2
    receipt.update(preparedOnly=True,snapshot=deepcopy(baseline),setupBoundary=dict(eventsDrained=True,
        frame=baseline["frame"],nativeCycle=baseline["nativeCycle"],endpointNativeCycle=baseline["nativeCycle"],traceSequences={"1":1}))
    evaluator.observe_record(dict(phase="setup",action="spawn-own-rattata",command="spawn",snapshot=baseline,receipt=receipt))
    bound=evaluator.bind("rattata",baseline)
    evaluator.observe_record(dict(phase="setup",action="bind-new-rattata",command="bind",snapshot=baseline,receipt=bound))
    def rebind(item):
        if isinstance(item,dict):
            for k,v in item.items():
                if k=="subject":item[k]=deepcopy(bound)
                else:rebind(v)
        elif isinstance(item,list):
            for v in item:rebind(v)
    rebind(reader);arm=deepcopy(baseline);arm["wildWalk"]=deepcopy(reader)
    evaluator.observe_record(dict(phase="observe",action="arm-native-clear",command="wild-walk.arm",snapshot=arm,
        receipt=dict(armed=True,advancedFrames=0,acceptedProof=False,snapshot=arm,wildWalk=reader)))
    if fault:
        if control:
            from tools.overworld.devtools_wild_clear_control_proof import WildClearControlNegative
            negative=WildClearControlNegative(fault)
        else:
            from tools.overworld.devtools_wild_walk_proof import WildWalkNegative
            negative=WildWalkNegative(fault)
    else:negative=None
    def normalize(snapshot):
        rebind(snapshot);snapshot["fieldAvailable"]=True;snapshot["nativeObservation"]["sequence"]+=2
    for sample,events in rows:
        normalize(sample);rebind(events)
        for e in events:
            e["data"]["sequence"]+=2 if e["kind"]=="native-observation" else 1
        prior=evaluator.latest
        row=dict(phase="observe",action="natural-clear-baseline" if control else "natural-walk-complete",
            requestedGameFrames=1,completedGameFrames=1,nativeCycles=2,observedFieldFrames=1,samples=[sample],events=events,
            cycleIntervals=[dict(cpuNs=1,wallNs=1,completedGameFrame=prior["frame"]),dict(cpuNs=1,wallNs=1,completedGameFrame=sample["frame"])])
        if negative:row=negative.mutate(row,evaluator.subjects)
        if evaluator.observe_record(row)["state"]=="failed":return evaluator.result()
    if control:
        rebind(calibration);normalize(calibration["snapshot"])
        calibration["snapshot"]["nativeObservation"]["resolvedProfiles"]=[]
        calibration["receipt"]["snapshot"]=deepcopy(calibration["snapshot"])
        calibration["action"]="calibrate-same-reader"
        if negative:calibration=negative.mutate(calibration,evaluator.subjects)
        if evaluator.observe_record(calibration)["state"]=="failed":return evaluator.result()
    terminal=deepcopy(evaluator.latest)
    if control:
        rebind(close);normalize(close["snapshot"])
        close["snapshot"]["nativeObservation"]["resolvedProfiles"]=[]
    else:
        closed_reader=deepcopy(terminal["wildWalk"]);closed_reader["closed"]=True
        close=dict(closed=True,advancedFrames=0,acceptedProof=False,wildWalk=closed_reader,snapshot=dict(terminal,wildWalk=closed_reader))
    evaluator.observe_record(dict(phase="observe",action="close-native-clear",command="wild-walk.close",snapshot=terminal,receipt=close))
    return evaluator.finish()


class WildWalkContractTests(unittest.TestCase):
    def test_runtime_feature_runs_single_walk_shared_scenario(self):
        repo = Path(__file__).resolve().parents[2]
        features = json.loads((repo / "tools/overworld/system_features.yaml").read_text())
        runtime = next(item for item in features["checks"] if item["id"] == "runtime.wild-walk")
        value = recipe()
        self.assertEqual(runtime["command"][-1], value["requirements"][0])
        self.assertEqual(value["actions"][1]["args"]["predicate"], {
            "kind": "measurement-complete",
            "measurement": WILD_WALK,
        })
        result = raw_replay()
        meter = result["measurements"][WILD_WALK]
        self.assertTrue(result["passed"], result["failures"])
        self.assertEqual(meter["completeMotions"], 1)
        self.assertEqual(sum(event["data"].get("event") == "MOTION_STARTED"
            for event in meter["traces"]), 1)

    def test_registered_recorder_dependencies_have_matching_adapters(self):
        from tools.overworld.control import _shared_recorder_kind, _shared_test_registration
        repo = Path(__file__).resolve().parents[2]
        registry = json.loads((repo / "tools/overworld/runtime_proof_registry.json").read_text())
        registrations = registry["sharedTests"]
        for name, entry in registrations.items():
            requirement = entry.get("recorderControlRequirement")
            if requirement is None:
                continue
            with self.subTest(test=name):
                kind = _shared_recorder_kind(requirement)
                self.assertTrue(any(control.get("requirements") == [requirement]
                    and control.get("evaluator") == kind and control.get("mode") == "observer-control"
                    for control in registrations.values()))
                value = json.loads((repo / "tests/overworld/test-recipes" / (name + ".json")).read_text())
                self.assertIsNotNone(_shared_test_registration(value, repo)[0])

    def test_wild_control_dependency_reaches_artifact_validation(self):
        from tools.overworld.control import _shared_recorder_control, ValidationFailure
        with self.assertRaisesRegex(ValidationFailure, "required live recorder control artifact is missing"):
            _shared_recorder_control({}, {"recorderControlRequirement":
                "shared.wild-clear-recorder-control-v1"}, Path.cwd())

    def test_unknown_dependency_fails_before_evidence_scan(self):
        from tools.overworld.control import _find_shared_recorder_control, ValidationFailure
        with self.assertRaisesRegex(ValidationFailure, "unknown live recorder requirement: missing-control"):
            _find_shared_recorder_control({}, {"recorderControlRequirement": "missing-control"}, {},
                Path("/nonexistent-recorder-fixture"))

    def test_full_raw_stream_and_command_boundaries(self):
        for control in (False,True):
            for startup_noop in (False,True):
                result=raw_replay(control, startup_noop=startup_noop)
                with self.subTest(control=control,startup_noop=startup_noop):self.assertTrue(result["passed"],result["failures"])

    def test_all_copied_controls_through_raw_evaluator(self):
        from tools.overworld.devtools_wild_walk_proof import FAULTS, validate_negative_result
        from tools.overworld.devtools_wild_clear_control_proof import FAULTS as CONTROL_FAULTS, validate_negative_result as validate_control
        for control,faults,validate in ((False,FAULTS,validate_negative_result),(True,CONTROL_FAULTS,validate_control)):
            for fault in faults:
                for startup_noop in (False, True):
                    with self.subTest(control=control,fault=fault,startup_noop=startup_noop):
                        validate(raw_replay(control,fault,startup_noop=startup_noop),fault)
    def test_both_recipes_have_separate_exact_contracts(self):
        for control,kind in ((False,WILD_WALK),(True,WILD_CLEAR_CONTROL)):
            value = validate_test(recipe(control))
            evaluator = TestEvaluator(value)
            evaluator.install_measurements({kind:{"contractVersion":1}})
            self.assertIn(kind,evaluator.measurements)

    def test_no_forced_movement_or_alternate_identity(self):
        for fault in ("species","role","existing","mode","input","reset","missing-close","extra-calibration"):
            value = recipe()
            if fault == "species": value["subjects"][0]["species"] = 95
            elif fault == "role": value["subjects"][0]["role"] = "MOUNTED"
            elif fault == "existing": value["subjects"][0]["acquire"] = "existing"
            elif fault == "mode": value["mode"] = "normal"
            elif fault == "input": value["actions"][1].update(op="step",args=dict(frames=1,keys=["RIGHT"]))
            elif fault == "reset": value["setup"][0].update(op="walk-policy.reset",args=dict(subject="rattata"))
            elif fault == "missing-close": value["actions"].pop()
            else: value["actions"].insert(-1,dict(id="calibrate",op="wild-walk.calibrate",args={},budget=deepcopy(value["actions"][0]["budget"])))
            with self.subTest(fault=fault), self.assertRaises(ValueError): validate_test(value)

    def test_matching_finalized_spawn_has_own_site(self):
        receipt,snapshot=spawn_setup()
        value=_wild_spawn_setup(receipt,snapshot)
        self.assertEqual(value["destination"],[0,0])
        self.assertEqual(value["subject"]["handle"],snapshot["actors"][0]["handle"])

    def test_runner_spawn_accepts_its_profile_appear_hop(self):
        receipt,snapshot=spawn_setup(species=234,locomotion=7)
        value=_wild_spawn_setup(receipt,snapshot,species=234,locomotion=7)
        self.assertEqual(value["nativeSpawn"]["data"]["startup"]["locomotion"],7)
        with self.assertRaisesRegex(ValueError,"identity or own native destination"):
            _wild_spawn_setup(receipt,snapshot,species=234,locomotion=0)

    def test_other_species_destination_or_command_identity_rejected(self):
        for fault in ("pid","slot","site","raw","world","finalization","other-actor"):
            receipt,snapshot=spawn_setup(); native=receipt["events"][0]["data"]
            if fault == "pid": receipt["value"]["personality"] += 1
            elif fault == "slot": receipt["value"]["slot"] += 1
            elif fault == "site": native["startup"]["target"][0] += 1
            elif fault == "raw": native["preparedPrefixHex"] = "00"*30
            elif fault == "world": snapshot["context"]["mapId"] += 1
            elif fault == "finalization": native["finalization"]["status"] = "missing"
            else: snapshot["actors"][0]["logical"]["x"] += 1
            with self.subTest(fault=fault),self.assertRaises(ValueError): _wild_spawn_setup(receipt,snapshot)

    def test_spawn_filters_old_same_species_before_ambiguity(self):
        value = generic_recipe(); value["subjects"][0]["acquire"] = "spawn"
        evaluator = TestEvaluator(value)
        first = generic_snapshot()
        evaluator.observe(first,count_frame=False)
        after = deepcopy(first); after["frame"] += 1
        new = deepcopy(first["actors"][0]); new["handle"].update(value=65537,slot=1); new["subjectIdentity"] += 1
        after["actors"].append(new)
        event=dict(frame=after["frame"],kind="native",data=dict(traceStream=1,sequence=1,event="ACTOR_ATTACHED",
            actorHandle=new["handle"]["value"],actor={k:v for k,v in new["handle"].items() if k != "value"}))
        evaluator.observe(after,[event],count_frame=False)
        self.assertEqual(evaluator.bind("subject",after)["handle"],new["handle"])
        self.assertEqual(evaluator.bind("subject",after)["handle"],new["handle"])

    def test_new_handle_still_needs_native_attachment(self):
        value=generic_recipe();value["subjects"][0]["acquire"]="spawn"
        evaluator=TestEvaluator(value); first=generic_snapshot();evaluator.observe(first,count_frame=False)
        after=deepcopy(first);after["frame"]+=1
        after["actors"][0]["handle"].update(value=131072,generation=2)
        with self.assertRaisesRegex(ValueError,"native attachment"): evaluator.bind("subject",after)

    def test_validated_prepared_attachment_retained_without_event_credit(self):
        evaluator=TestEvaluator(recipe()); evaluator.install_measurements({WILD_WALK:{"contractVersion":1}})
        receipt,snapshot=spawn_setup(); snapshot["fieldAvailable"]=True
        actor=snapshot["actors"][0]; snapshot["nativeObservation"]["sequence"]=0
        event=dict(frame=snapshot["frame"],kind="native",data=dict(traceStream=1,sequence=1,event="ACTOR_ATTACHED",
            actorHandle=actor["handle"]["value"],actor={k:v for k,v in actor["handle"].items() if k != "value"}))
        evaluator._acceleration_prefix(snapshot,[event],start_frame=snapshot["frame"])
        self.assertIn(_handle(actor["handle"]),evaluator._prepared_attached)
        self.assertEqual(sum(evaluator.events.values()),0)
        evaluator.first_handles=set()
        self.assertEqual(evaluator.bind("rattata",snapshot)["handle"],actor["handle"])


if __name__=="__main__":unittest.main()
