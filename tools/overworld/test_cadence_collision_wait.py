"""Native-event to cadence integration, without an emulator or fake verdicts."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.test_devtools_cadence_measurement import Route, player


def collision(route, mask=2, *, frame=None):
    route.seq += 1
    frame = route.frame+1 if frame is None else frame
    before = player()
    return {"kind":"native-observation", "frame":frame, "data": {
        "observation":"player-collision", "sequence":route.seq, "setupMode":"normal",
        "objectPointer":0x02030000, "callerReturn":0x0205D4C6, "direction":3,
        "origin":[0,0], "target":[1,0], "collisionMask":mask, "returnValue":mask,
        "context":{**route.context, "fieldPointer":0x02040000, "statePointer":0x02050000},
        "objectBefore":deepcopy(before), "objectAfter":deepcopy(before),
        "entryActorFrame":frame, "returnActorFrame":frame,
        "entryNativeCycle":frame*2, "returnNativeCycle":frame*2}}


def route_with_wait(*, mask=2, missing=False, stale=False):
    route=Route();route.setup_bind()
    start=route.frame+1
    blocked=collision(route,mask)
    if stale: blocked["data"]["context"]["fieldEpoch"]+=1
    if missing:
        route.seq-=1
    for index in range(17):
        route.p.update(flags=0x31 if index==16 else 0x11, movement_cmd=31,
                       movement_step=2 if index==16 else 1)
        route.append("route-0",events=[] if missing or index else [blocked])
    clear=collision(route,0)
    first_motion_index=len(route.records)
    route.move(1)
    route.records[first_motion_index]["events"].insert(0,clear)
    return route,start,first_motion_index


def feed(route):
    meter=UnmountedCadenceMeasurement(route.test,max_frames=1200)
    for row in route.records:
        result=meter.observe_record(row,full_report=False)
        if result["failures"]: break
    return meter,result


class CadenceCollisionWaitTests(unittest.TestCase):
    def test_raw_collision_requires_exact_caller_return_clock_and_unchanged_pose(self):
        mutations = {
            "caller": (lambda d:d.__setitem__("callerReturn",0x0205D4C8), "stock walking collision caller/result missing"),
            "result": (lambda d:d.__setitem__("returnValue",0), "stock walking collision caller/result missing"),
            "future": (lambda d:d.__setitem__("returnNativeCycle",99), "walking collision outside completed frame"),
            "old": (lambda d:d.__setitem__("entryNativeCycle",1), "walking collision outside completed frame"),
            "pose": (lambda d:d["objectAfter"].__setitem__("pos_x",0), "walking collision changed native player pose"),
        }
        for name,(change,message) in mutations.items():
            with self.subTest(name=name):
                route,_,_=route_with_wait()
                event=next(e for row in route.records for e in row.get("events",[])
                           if e["kind"]=="native-observation")
                change(event["data"])
                meter,result=feed(route)
                self.assertEqual(result["failures"][0]["code"],"cadence-observation-invalid")
                self.assertEqual(result["failures"][0]["detail"],message)
                self.assertEqual(meter.active_frames,0)

    def test_raw_collision_cannot_replace_player_pointer_established_by_real_motion(self):
        route=Route();route.setup_bind();route.move(1)
        route.p.update(x_prev=1,flags=1,movement_cmd=3)
        event=collision(route)
        event["data"].update(objectPointer=0x02030004,origin=[1,0],target=[2,0],
                             objectBefore=deepcopy(route.p),objectAfter=deepcopy(route.p))
        route.append("route-0",events=[event])
        meter,result=feed(route)
        self.assertEqual(meter.player_motions,1)
        self.assertEqual(result["failures"][0]["detail"],"walking collision player changed without handoff")

    def test_native_object_wait_then_clear_admission_and_complete_motion(self):
        route,start,motion_index=route_with_wait()
        meter=UnmountedCadenceMeasurement(route.test,max_frames=1200)
        for row in route.records[:motion_index]:
            result=meter.observe_record(row,full_report=False)
            self.assertEqual(result["failures"],[])
        self.assertEqual(meter.active_frames,0)
        self.assertEqual(meter.player_motions,0)
        self.assertEqual(meter.step["samples"],[])
        self.assertIsNotNone(meter.player_collision_wait.active)
        for row in route.records[motion_index:]:
            result=meter.observe_record(row,full_report=False)
            self.assertEqual(result["failures"],[])
        self.assertTrue(meter.player_collision_wait.ready)
        proof=meter.player_collision_wait.proofs[0]
        self.assertEqual((proof["startFrame"],proof["endFrame"],proof["waitingFrames"]),(start,start+17,17))
        self.assertEqual(meter.active_frames,32)
        self.assertEqual(meter.player_motions,1)
        self.assertEqual(meter.follower_motions,1)
        self.assertIsNone(meter.step)

    def test_missing_native_receipt_keeps_original_two_frame_admission_limit(self):
        meter,result=feed(route_with_wait(missing=True)[0])
        self.assertTrue(result["failures"])
        self.assertEqual(result["failures"][0]["code"],"player-input-not-admitted")
        self.assertEqual(meter.active_frames,0)
        self.assertEqual(meter.player_motions,0)

    def test_terrain_mixed_mask_or_stale_native_receipt_cannot_authorize_wait(self):
        for options in ({"mask":1},{"mask":3},{"stale":True}):
            with self.subTest(options=options):
                meter,result=feed(route_with_wait(**options)[0])
                self.assertTrue(result["failures"])
                self.assertEqual(meter.active_frames,0)
                self.assertEqual(meter.player_motions,0)

    def test_admission_cannot_end_wait_without_native_clear(self):
        route,_,index=route_with_wait()
        route.records[index]["events"].pop(0)
        for row in route.records[index:]:
            for event in row.get("events",[]):
                if event["kind"]=="native-observation":event["data"]["sequence"]-=1
            for snapshot in row.get("samples",[]):snapshot["nativeObservation"]["sequence"]-=1
        meter,result=feed(route)
        self.assertEqual(result["failures"][0]["code"],"cadence-observation-invalid")
        self.assertIn("admission lacks exact clear receipt",result["failures"][0]["detail"])
        self.assertEqual(meter.active_frames,0)

    def test_collision_cannot_forgive_stalled_already_admitted_player(self):
        route=Route();route.setup_bind()
        begin=len(route.records)
        clear=collision(route,0)
        route.move(1)
        route.records[begin]["events"].insert(0,clear)
        route.records=route.records[:begin+4]
        # Only alter native player render. Keep the real admission, follower
        # motion, semantic clocks, CPU intervals, and original classifier.
        for index,row in enumerate(route.records[begin:]):
            row["samples"][0]["player"]["pos_x"]=32768
            if index:
                native=collision(route,2,frame=row["samples"][0]["frame"])
                # Renumber all native observations in actual stream order;
                # this control targets pose, not an accidental sequence gap.
                row["events"].append(native)
        sequence=0
        for row in route.records:
            for event in row.get("events",[]):
                if event["kind"]=="native-observation":
                    sequence+=1;event["data"]["sequence"]=sequence
            for snapshot in row.get("samples",[]):snapshot["nativeObservation"]["sequence"]=sequence
        meter,result=feed(route)
        self.assertTrue(result["failures"])
        self.assertEqual(meter.active_frames,0)
        self.assertEqual(meter.player_motions,0)
        self.assertEqual(result["failures"][0]["code"],"cadence-observation-invalid")
        self.assertEqual(result["failures"][0]["detail"],"walking collision outside unadmitted request")

    def test_retained_missing_collision_still_fails_at_original_1157(self):
        root=Path(__file__).resolve().parents[2]
        path=root/"build/overworld-devtools/test-2a32e0781e064d748d42e0a670706012/observations.jsonl"
        if not path.is_file():self.skipTest("optional immutable memory data is absent")
        from tools.overworld.control import _replay_shared_test
        from tools.overworld.devtools_test_contract import validate_test
        recipe=validate_test(json.loads((root/"tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json").read_text()))
        with path.open() as stream:
            result=_replay_shared_test(recipe,(json.loads(line) for line in stream))
        meter=result["measurements"]["unmounted-cadence-v1"]
        self.assertFalse(result["passed"])
        self.assertEqual(meter["failures"][0]["code"],"player-input-not-admitted")
        self.assertEqual(meter["failures"][0]["frame"],1157)
        self.assertEqual(meter["playerCollisionWaits"],[])


if __name__=="__main__":unittest.main()
