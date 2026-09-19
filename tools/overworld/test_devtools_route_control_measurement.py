"""Small real-cadence calibration streams, not synthetic checker outcomes."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_route_control_measurement import LiveRouteControlMeasurement
from tools.overworld import test_devtools_cadence_measurement as fixtures
Route = fixtures.Route


class LiveRouteControlTests(unittest.TestCase):
    def baseline(self):
        original,commands=fixtures.PreparedCadenceSetupTests().fixture()
        route=Route()
        test=deepcopy(route.test); test["mode"]="observer-control"
        test["setup"]=[deepcopy(a) for (phase,_),a in original.actions.items() if phase=="setup"]
        for kind in ("cpu-hitch","player-start-stall"):
            test["actions"].append({"id":kind,"op":"observer-control","args":{"subject":"cyndaquil","fault":kind}})
        meter=LiveRouteControlMeasurement(test,max_frames=1200)
        meter.observe_record({"phase":"setup","initialSnapshot":deepcopy(original.latest)})
        for command in commands: meter.observe_record(command)
        snapshot=commands[-1]["snapshot"]
        meter.observe_record({"phase":"observe","action":"bind","command":"bind",
                              "receipt":snapshot["actors"][0],"snapshot":snapshot})
        route.frame=2; route.getters=deepcopy(snapshot["partyObservation"]["nativeGetterChecks"])
        route.records=[]
        for tile in range(1,5): route.move(tile)
        for record in route.records:
            record["samples"][0]["prepared"]=True
            for event in record["events"]:
                if event["kind"]=="native-observation":event["data"]["setupMode"]="prepared"
            result=meter.observe_record(record,full_report=False)
            self.assertEqual(result["failures"],[])
        self.assertTrue(meter.stage("baseline"))
        return meter,route

    def value(self,meter,kind,rows,state):
        return dict(type="native-route-control-v1",kind=kind,state=state,subject=deepcopy(meter.subject),
                    receipts=deepcopy(rows),failure=None,closed=False,requiresCoreClose=kind=="player-start-stall")

    def receipt(self,meter,kind,action,**extra):
        return dict(action=action,kind=kind,frame=meter.latest["frame"],nativeCycle=meter.latest["nativeCycle"],
            subject=deepcopy(meter.subject),context=deepcopy(meter.latest["context"]),
            playerPointer=0x02030000,playerManager=0x02020000,**extra)

    def arm(self,meter,kind):
        meter.arm_args(meter.subject,kind)
        rows=deepcopy(meter.histories)+[self.receipt(meter,kind,"armed",maxFrames=120)]
        state="cpu-armed" if kind=="cpu-hitch" else "player-armed"
        value=self.value(meter,kind,rows,state)
        snapshot=deepcopy(meter.latest)
        record=dict(phase="observe",action=kind,command="observer-control",snapshot=snapshot,
                    receipt=dict(armed=True,frame=snapshot["frame"],routeControl=value))
        self.assertEqual(meter.observe_record(record)["failures"],[])

    def cpu(self,meter,route,*,fault=None):
        self.arm(meter,"cpu-hitch")
        row=self.receipt(meter,"cpu-hitch","cpu-work",nativeCycleBefore=meter.latest["nativeCycle"],
            targetNativeCycle=meter.latest["nativeCycle"]+1,workStartCpuNs=1000000,
            workEndCpuNs=101000000,workCpuNs=100000000)
        if fault=="wrong-cycle":row["targetNativeCycle"]-=1
        route.append("idle"); record=deepcopy(route.records[-1]); snapshot=record["samples"][0]
        snapshot["prepared"]=True
        snapshot["routeControl"]=self.value(meter,"cpu-hitch",meter.histories+[row],"cpu-injected")
        record["cycleIntervals"][0]["cpuNs"]=100100000
        if fault=="extra-hitch":record["cycleIntervals"][1]["cpuNs"]=100100000
        if fault=="not-a-hitch":record["cycleIntervals"][0]["cpuNs"]=100000
        return meter.observe_record(record)

    def test_real_baseline_is_separate_from_normal_floor(self):
        meter,_=self.baseline()
        self.assertEqual(meter.player_motions,4)
        self.assertGreaterEqual(meter.follower_motions,1)
        self.assertGreaterEqual(meter.baseline_result["cpu"]["sampleCount"],16)
        self.assertEqual(meter.baseline_result["cpu"]["sampleCount"], len(meter.baseline_result["cpuSamples"]))
        self.assertFalse(meter.baseline_result["ready"])
        self.assertFalse(meter.finish()["passed"])

    def test_cpu_requires_exact_live_receipt_and_no_other_hitch(self):
        for fault in (None,"wrong-cycle","extra-hitch","not-a-hitch"):
            with self.subTest(fault=fault):
                meter,route=self.baseline(); result=self.cpu(meter,route,fault=fault)
                self.assertEqual(meter.stage("cpu-detected"),fault is None)
                if fault in ("wrong-cycle","extra-hitch"): self.assertTrue(result["failures"])

    def player_case(self, fault=None):
        meter,route=self.baseline(); self.cpu(meter,route)
        self.arm(meter,"player-start-stall")
        start_count=meter.player_motions
        admission=route.admission([4,0],[5,0])
        native={k:deepcopy(v) for k,v in admission["data"].items() if k not in ("observation","sequence","setupMode")}
        if fault=="wrong-admission": native["stepIndex"]+=1
        admitted=self.receipt(meter,"player-start-stall","player-admitted",admission=native,
                             pinned=[4*65536+32768,32768])
        admitted["frame"]+=1;admitted["nativeCycle"]+=2
        history=deepcopy(meter.histories)+[admitted]
        for index in range(4):
            route.p.update(x=5,x_prev=4,flags=0x11,movement_cmd=15,pos_x=4*65536+32768)
            route.append("route-0",events=[admission] if index==0 else [])
            record=deepcopy(route.records[-1]);snapshot=record["samples"][0];snapshot["prepared"]=True
            for event in record["events"]:event["data"]["setupMode"]="prepared"
            pin=self.receipt(meter,"player-start-stall","player-pinned",before=[300000,32768],
                             after=admitted["pinned"],writeIndex=index+1)
            pin.update(frame=snapshot["frame"],nativeCycle=snapshot["nativeCycle"])
            if fault=="wrong-pin" and index==3: pin["writeIndex"]+=1
            if fault=="different-fault" and index==3: snapshot["player"]["pos_z"]+=1
            history.append(pin)
            snapshot["routeControl"]=self.value(meter,"player-start-stall",history,"player-pinning")
            result=meter.observe_record(record)
            if index==3 and fault:
                self.assertTrue(result["failures"])
                self.assertFalse(meter.stage("player-detected"))
                self.assertEqual(meter.player_motions,start_count)
                return
            self.assertEqual(result["failures"],[])
        self.assertTrue(meter.stage("player-detected"))
        self.assertEqual(meter.player_motions,start_count)
        self.assertIsNotNone(meter.step)
        self.assertEqual(meter.detections["player-start-stall"]["classifier"]["startStall"],1)
        closed=self.receipt(meter,"player-start-stall","closed",requiresCoreClose=True)
        value=self.value(meter,"player-start-stall",history+[closed],"closed");value["closed"]=True
        meter.observe_cleanup(dict(closed=True,frame=meter.latest["frame"],snapshot=deepcopy(meter.latest),routeControl=value))
        self.assertTrue(meter.finish()["passed"])
        self.assertFalse(meter.finish()["acceptedProof"])

    def test_cpu_then_real_player_start_stall_retains_failed_step_without_credit(self):
        self.player_case()

    def test_bad_receipts_and_other_real_pose_fault_cannot_authorize_detection(self):
        for fault in ("wrong-admission","wrong-pin","different-fault"):
            with self.subTest(fault=fault): self.player_case(fault)

    def test_unrelated_player_fault_is_never_swallowed(self):
        meter,route=self.baseline(); self.cpu(meter,route); self.arm(meter,"player-start-stall")
        meter.baseline._fail("player-render-outside-requested-cardinal-segment")
        self.assertTrue(meter.progress_result()["failures"])
        self.assertFalse(meter.stage("player-detected"))

    def test_cpu_stage_waits_for_follower_without_discarding_detection(self):
        meter,route=self.baseline(); self.cpu(meter,route)
        meter.baseline.actor["motionPhase"]="MOVING"
        self.assertIn("cpu-hitch",meter.detections)
        self.assertFalse(meter.stage("cpu-detected"))
        with self.assertRaises(ValueError):meter.arm_args(meter.subject,"player-start-stall")
        meter.baseline.actor["motionPhase"]="IDLE"
        self.assertTrue(meter.stage("cpu-detected"))

    def chunk_case(self, count=5):
        meter,route=self.baseline(); self.cpu(meter,route); self.arm(meter,"player-start-stall")
        route.records=[]; route.move(5)
        records=deepcopy(route.records[:count])
        native={k:v for k,v in records[0]["events"][0]["data"].items()
                if k not in ("observation","sequence","setupMode")}
        pin=[native["objectBefore"]["pos_x"],native["objectBefore"]["pos_z"]]
        admitted=self.receipt(meter,"player-start-stall","player-admitted",admission=native,pinned=pin)
        history=deepcopy(meter.histories)+[admitted]
        for i,record in enumerate(records):
            snapshot=record["samples"][0]; snapshot["prepared"]=True
            snapshot["player"].update(pos_x=pin[0],pos_z=pin[1])
            for event in record["events"]:event["data"]["setupMode"]="prepared"
            row=self.receipt(meter,"player-start-stall","player-pinned",before=[123,456],after=pin,writeIndex=i+1)
            row.update(frame=snapshot["frame"],nativeCycle=snapshot["nativeCycle"])
            history.append(row)
            snapshot["routeControl"]=self.value(meter,"player-start-stall",history,"player-pinning")
        chunk=deepcopy(records[0])
        for key in ("samples","events","cycleIntervals"):
            chunk[key]=[item for record in records for item in record[key]]
        chunk.update(nativeCycles=count*2,completedGameFrames=count,requestedGameFrames=count,observedFieldFrames=count)
        return meter,chunk

    def test_future_pin_cannot_stamp_detection_or_advance_past_it(self):
        meter,chunk=self.chunk_case()
        expected=chunk["samples"][3]["frame"]
        result=meter.observe_record(chunk)
        self.assertEqual(meter.detections["player-start-stall"]["frame"],expected)
        self.assertEqual(meter.latest["frame"],expected)
        self.assertEqual(len(meter.pins),4)
        self.assertTrue(result["failures"])

    def test_earlier_motion_fault_precedes_later_bad_control_receipt(self):
        meter,chunk=self.chunk_case()
        chunk["samples"][0]["player"]["pos_z"]+=1
        chunk["samples"][-1]["routeControl"]["failure"]={"message":"later bad receipt"}
        result=meter.observe_record(chunk)
        self.assertEqual(result["failures"][0]["code"],"player-render-outside-requested-cardinal-segment")
        self.assertEqual(result["failures"][0]["frame"],chunk["samples"][0]["frame"])

    def test_four_row_chunk_detects_at_its_exact_last_sample(self):
        meter,chunk=self.chunk_case(4)
        result=meter.observe_record(chunk)
        self.assertEqual(result["failures"],[])
        self.assertEqual(meter.detections["player-start-stall"]["frame"],chunk["samples"][-1]["frame"])

    def test_new_pin_requires_current_frame_and_native_cycle(self):
        for key in ("frame","nativeCycle"):
            with self.subTest(key=key):
                meter,chunk=self.chunk_case(4)
                chunk["samples"][0]["routeControl"]["receipts"][-1][key]-=1
                result=meter.observe_record(chunk)
                self.assertTrue(result["failures"])
                self.assertNotIn("player-start-stall",meter.detections)


if __name__=="__main__":unittest.main()
