"""Setup-only shared replay controls; no live or long-route acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_cadence_measurement import Route, player

ROOT = Path(__file__).resolve().parents[2]
KIND = "cyndaquil-normal-setup-v1"


def recipe():
    return json.loads((ROOT / "tests/overworld/test-recipes/world.cyndaquil-normal-setup.json").read_text())


def stream():
    route = Route()
    base = route.snapshot()
    mon = base["party"][1]
    mon.update(personality=2046726716, hp=0, maxHp=21)
    actor = base["actors"][0]
    actor["subjectIdentity"] = actor["sourceIdentity"]["personality"] = 2046726716
    actor["sourceIdentity"]["map_id"] = 67
    actor["engineIdentity"].update(manager_index=0, object_map_id=67, spawn_map_id=67, current_map_id=67)
    rows = []
    def snapshot(map_id, x, z, task=0, hp=0, new=0, menu=0, getter=False):
        value = deepcopy(base)
        frame = len(rows)
        value.update(frame=frame, nativeCycle=frame*2)
        value["actors"][0]["crashPresentation"].update(frame=frame, nativeCycle=frame*2)
        value["context"]["mapId"] = map_id
        value["player"] = player(x,z)
        value["fieldControl"]["taskPointer"] = task
        value["fieldControl"]["fieldPointer"] = 0x02080000
        value["party"][1]["hp"] = hp
        value["partyObservation"].update(frame=frame, nativeGetterChecks=[])
        if getter:
            value["partyObservation"]["nativeGetterChecks"] = [{
                "slot":1,"field":"hp","native":21,"decoded":21,"passed":True,
                "personality":2046726716,"species":155,"frame":frame,"decodedAtFrame":frame,
                "boundary":"natural-GetMonData-return"}]
        value["nativeObservation"]["playerStepFrame"] = frame
        count=sum(len(row.get("events",[])) for row in rows)
        value["nativeObservation"].update(sequence=count,playerStepCount=count)
        value["selector"].update(newKeys=new,state=menu,highlight=1,activeFollowerPartySlot=1)
        return value
    rows.append({"phase":"setup","initialSnapshot":snapshot(67,564,392,task=0x02040000)})
    def append(action,*args,**kwargs):
        value=snapshot(*args,**kwargs)
        rows.append({"phase":"setup","action":action,"samples":[value],"events":[],
                     "requestedGameFrames":1,"completedGameFrames":1,"observedFieldFrames":1,
                     "nativeCycles":2,"cycleIntervals":[
                         {"cpuNs":100000,"wallNs":150000,"completedGameFrame":value["frame"]-1},
                         {"cpuNs":100000,"wallNs":150000,"completedGameFrame":value["frame"]}]})
    def automatic(action,direction,origin,target,task,hp):
        append(action,67,564,target,task=task,hp=hp)
        row=rows[-1];s=row["samples"][0]
        before=player(564,origin);before.update(movement_cmd=12+direction,movement_step=0,facing=direction)
        after=deepcopy(before);after["y"]=target
        s["player"]=deepcopy(after)
        s["player"]["pos_z"]+=(target-origin)*8192
        s["player"]["movement_step"]=1
        count=s["nativeObservation"]["sequence"]+1
        s["nativeObservation"].update(sequence=count,playerStepCount=count)
        receipt=dict(observation="player-step-admitted",sequence=count,stepIndex=count,setupMode="normal",
                     objectPointer=0x02030000,returnValue=0x02030000,mapId=67,direction=direction,
                     origin=[564,origin],target=[564,target],objectBefore=before,objectAfter=after,
                     entryActorFrame=s["actorFrame"],returnActorFrame=s["actorFrame"],
                     entryNativeCycle=s["nativeCycle"],returnNativeCycle=s["nativeCycle"])
        row["events"]=[{"frame":s["frame"],"kind":"native-observation","data":receipt}]
    automatic("enter-arrival",0,392,391,0x02040000,0)
    append("enter-arrival",69,8,19)
    append("nurse-start-a",69,8,13,new=1)
    append("nurse-finished",69,8,13,hp=21)
    append("exit-door",69,8,19,task=0x02040004,hp=21)
    append("exit-arrival",67,564,391,task=0x02040004,hp=21)
    automatic("exit-arrival",1,391,392,0x02040004,21)
    append("exit-arrival",67,564,392,hp=21)
    append("selector-open-y",67,564,393,hp=21,new=2048,menu=2,getter=True)
    append("selector-confirm-y",67,564,393,hp=21,new=2048,getter=True)
    last=deepcopy(rows[-1]["samples"][0])
    rows.append({"phase":"setup","action":"bind-cyndaquil","command":"bind",
                 "snapshot":last,"receipt":select_current_actor(last,last["actors"][0])})
    final=deepcopy(rows[-2])
    final.update(phase="observe",action="setup-final-coherent")
    value=final["samples"][0]
    value["frame"]+=1; value["nativeCycle"]+=2
    value["actors"][0]["crashPresentation"].update(frame=value["frame"], nativeCycle=value["nativeCycle"])
    value["partyObservation"]["frame"]=value["frame"]
    value["nativeObservation"]["playerStepFrame"]=value["frame"]
    value["selector"]["newKeys"]=0
    for interval in final["cycleIntervals"]: interval["completedGameFrame"]+=1
    rows.append(final)
    return rows


def evaluate(rows):
    test=validate_test(recipe())
    evaluator=TestEvaluator(test)
    evaluator.install_measurements(measurement_inputs(test,ROOT))
    for row in rows: evaluator.observe_record(row)
    return evaluator


class SetupTests(unittest.TestCase):
    def test_final_wait_requires_a_real_post_bind_frame(self):
        rows = stream()
        evaluator = evaluate(rows[:-1])
        test = validate_test(recipe())
        predicate = test["actions"][-1]["args"]["predicate"]
        self.assertEqual(predicate["kind"], "measurement-complete")
        self.assertEqual(predicate["measurement"], KIND)
        self.assertTrue(evaluator.measurements[KIND].result()["ready"])
        self.assertEqual(evaluator.frames, 0)
        self.assertFalse(evaluator.check(predicate))
        evaluator.observe_record(rows[-1])
        self.assertEqual(evaluator.frames, 1)
        self.assertTrue(evaluator.check(predicate))
        self.assertTrue(evaluator.finish()["passed"])

    def test_selector_cycles_from_any_saved_highlight_with_released_edges(self):
        from tools.overworld.devtools_movement_predicates import check_movement_predicate
        actions=[a for a in recipe()["setup"] if a["id"].startswith("selector-")]
        turns=[a for a in actions if a["args"].get("keys")==["R"]]
        self.assertEqual(len(turns),5)
        for action in turns:
            self.assertEqual(action["args"]["until"],{"kind":"selector-field","path":"newKeys","operator":"eq","value":256})
            self.assertEqual(action["skipIf"],{"kind":"selector-field","path":"highlight","operator":"eq","value":1})
        for action in actions:
            if action["id"].endswith("release"):
                self.assertEqual(action["args"]["predicate"],{"kind":"selector-field","path":"heldKeys","operator":"eq","value":0})
        for initial in (0,1,2,5):
            with self.subTest(initial=initial):
                snapshot=Route().snapshot()
                snapshot["selector"].update(highlight=initial,state=0,heldKeys=0,newKeys=0)
                edges=[]
                def check(predicate):return check_movement_predicate(predicate,snapshot)
                for action in actions:
                    if action["id"]=="selector-issued":break
                    if action.get("skipIf") and check(action["skipIf"]):continue
                    if action["op"]=="assert":
                        self.assertTrue(check(action["args"]["predicate"]));continue
                    if action["op"]=="wait" and check(action["args"]["predicate"]):continue
                    for frame in range(action["budget"]["maxFrames"]):
                        selector=snapshot["selector"]
                        key={"Y":2048,"R":256}.get(next(iter(action["args"].get("keys",[])),""),0)
                        selector["newKeys"]=key & ~selector["heldKeys"]
                        selector["heldKeys"]=key
                        snapshot["frame"]+=1
                        if selector["newKeys"]:
                            edges.append((snapshot["frame"],key))
                            if key==2048:selector["state"]=2 if selector["state"]==0 else 0
                            else:selector["highlight"]=(selector["highlight"]+1)%6
                        predicate=action["args"].get("until",action["args"].get("predicate"))
                        if check(predicate):break
                    else:self.fail("selector action exhausted its bound: "+action["id"])
                self.assertEqual(snapshot["selector"]["highlight"],1)
                self.assertEqual(sum(key==256 for _,key in edges),(1-initial)%6)
                self.assertEqual(sum(key==2048 for _,key in edges),2)
                self.assertTrue(all(b[0]-a[0]>=2 for a,b in zip(edges,edges[1:])))

    def test_automatic_doorway_contract_rejects_unbounded_or_unknown_steps(self):
        for automatic in (True,["anything"],["entry-up","entry-up"],["exit-down"],[False]):
            value=recipe()
            value["measurements"][0]["setupTransitions"][0]["automaticSteps"]=automatic
            with self.subTest(automatic=automatic),self.assertRaises(ValueError):validate_test(value)

    def test_automatic_doorway_receipts_are_exact_and_required(self):
        for index in (1,7):
            for fault in ("missing","duplicate","pointer","command","clock","task","segment","target","return-pose","direction-bool"):
                with self.subTest(index=index,fault=fault):
                    rows=stream();row=rows[index];sample=row["samples"][0];receipt=row["events"][0]["data"]
                    if fault=="missing":
                        row["events"]=[]
                        # Keep global stream/count coherent to isolate the required doorway receipt.
                        for later in rows[index:]:
                            for s in later.get("samples",[]):
                                s["nativeObservation"]["sequence"]-=1;s["nativeObservation"]["playerStepCount"]-=1
                            for event in later.get("events",[]):
                                event["data"]["sequence"]-=1;event["data"]["stepIndex"]-=1
                    elif fault=="duplicate":row["events"].append(deepcopy(row["events"][0]))
                    elif fault=="pointer":receipt["objectPointer"]+=4
                    elif fault=="command":receipt["objectBefore"]["movement_cmd"]=14
                    elif fault=="clock":receipt["returnNativeCycle"]-=1
                    elif fault=="task":sample["fieldControl"]["taskPointer"]+=4
                    elif fault=="segment":sample["player"]["pos_x"]+=1
                    elif fault=="target":receipt["target"][0]+=1
                    elif fault=="direction-bool":receipt["direction"]=False
                    else:receipt["objectAfter"]["pos_z"]+=1
                    self.assertFalse(evaluate(rows).measurements[KIND].finish()["passed"])

    def test_exact_recipe_is_normal_bounded_and_has_seven_checked_a_edges(self):
        test=validate_test(recipe())
        self.assertEqual(test["requirements"],[])
        self.assertEqual(test["mode"],"normal")
        self.assertEqual(test["fixture"],{"rom":"test.nds","save":"test.sav"})
        actions=test["setup"]
        presses=[i for i,a in enumerate(actions) if a["args"].get("keys")==["A"]]
        self.assertEqual(len(presses),7)
        self.assertEqual([actions[i-1]["args"]["predicate"]["state"] for i in presses],
                         ["idle","page-wait","page-wait","yes-no-ready","page-wait","page-wait","script-button-wait"])
        for i in presses:
            self.assertEqual(actions[i]["args"]["frames"],16)
            self.assertEqual(actions[i]["args"]["until"],{
                "kind":"selector-field","path":"newKeys","operator":"eq","value":1,"when":"final"})
            self.assertEqual(actions[i]["budget"]["maxFrames"],16)
            self.assertEqual(actions[i]["budget"]["noProgressFrames"],16)
            self.assertEqual(actions[i+1]["op"],"wait")
        original=json.loads((ROOT/"tests/overworld/test-recipes/world.center-entry-exit.json").read_text())
        end=next(i for i,a in enumerate(original["setup"]) if a["id"]=="enter-arrival")+1
        self.assertEqual(actions[:end],validate_test(original)["setup"][:end])
        transitions=deepcopy(test["measurements"][0]["setupTransitions"])
        self.assertEqual([s.pop("automaticSteps") for s in transitions],[["entry-up"],["exit-down"]])
        self.assertEqual(transitions,original["measurements"][0]["setupTransitions"])
        ids=[a["id"] for a in actions]
        self.assertNotIn("exit-face-down",ids)
        self.assertEqual(ids[ids.index("nurse-return-19-settle")+1],"exit-door")
        for prefix, direction, tiles, first_count in (("nurse-approach","UP",range(18,12,-1),37),
                                         ("nurse-return","DOWN",range(14,20),43)):
            for count,tile in enumerate(tiles,first_count):
                index=ids.index(f"{prefix}-{tile}-admit")
                self.assertEqual(actions[index]["args"]["keys"],[direction])
                self.assertEqual(actions[index]["args"]["until"],
                                 {"kind":"player-step-count","operator":"eq","value":count,"when":"final"})
                settled=actions[index+1]["args"]["predicate"]
                self.assertEqual((settled["kind"],settled["map"],settled["x"],settled["z"]),
                                 ("player-settled-at",69,8,tile))

    def test_real_shared_binding_finishes_setup_without_claiming_route(self):
        evaluator=evaluate(stream())
        meter=evaluator.measurements[KIND]
        result=meter.finish()
        self.assertTrue(result["passed"],result["failures"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["activeMovementFrames"],0)
        self.assertEqual(result["subject"]["subjectIdentity"],2046726716)
        final=evaluator.finish()
        self.assertTrue(final["passed"],final["failures"])

    def test_native_getter_binding_and_transition_controls_fail_closed(self):
        for fault in ("getter","pid","phase","role","exit"):
            with self.subTest(fault=fault):
                rows=stream()
                if fault=="getter":
                    for row in rows:
                        for s in row.get("samples",[]): s["partyObservation"]["nativeGetterChecks"]=[]
                    rows[-2]["snapshot"]["partyObservation"]["nativeGetterChecks"]=[]
                elif fault=="exit":
                    row=next(row for row in rows if row.get("action")=="exit-arrival")
                    row["samples"][0]["player"]["x"]=565
                else:
                    actor=rows[-2]["snapshot"]["actors"][0]
                    if fault=="pid": actor["subjectIdentity"]=99
                    elif fault=="phase": actor["motionPhase"]="MOVING"
                    else: actor["role"]="MOUNTED"
                    rows[-2]["receipt"]=deepcopy(actor)
                self.assertFalse(evaluate(rows).measurements[KIND].finish()["passed"])
