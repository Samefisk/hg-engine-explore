"""Single-row, single-meaning controller mutation checks."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tools.overworld.route_control_negatives import FAULTS, MEANINGS, RouteControlNegative, validate_negative_result
from tools.overworld.test_devtools_cadence_measurement import Route


class RouteControlNegativeTests(unittest.TestCase):
    def fixture(self):
        route=Route();subject=deepcopy(route.actor)
        row={"phase":"observe","samples":[route.snapshot()],"events":[]}
        for meaning in MEANINGS.values():
            event=route.trace(meaning,1,1);event["frame"]=row["samples"][0]["frame"]
            row["events"].append(event)
        return subject,row

    def test_only_selected_row_is_copied_and_only_once(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                subject,row=self.fixture()
                if fault in ("route-missing-cpu","route-missing-pin"):
                    row["samples"][0]["routeControl"]={"receipts":[
                        {"action":"cpu-work","workCpuNs":100000000},
                        {"action":"player-pinned","after":[10,20]}]}
                elif fault=="route-missing-cleanup":
                    row={"phase":"cleanup","command":"route-control.close","receipt":{
                        "routeControl":{"receipts":[{"action":"closed","requiresCoreClose":True}]}}}
                original=deepcopy(row);control=RouteControlNegative(fault)
                untouched={"phase":"setup","initialSnapshot":{}}
                self.assertIs(control.mutate(untouched,{"cyndaquil":subject}),untouched)
                self.assertFalse(control.applied)
                result=control.mutate(row,{"cyndaquil":subject})
                self.assertTrue(control.applied);self.assertIsNot(result,row)
                self.assertEqual(row,original);self.assertNotEqual(result,row)
                self.assertIs(control.mutate(row,{"cyndaquil":subject}),row)
                if fault in MEANINGS:
                    before=deepcopy(row["events"])
                    after=deepcopy(result["events"])
                    for event in after:
                        if event["data"]["event"]=="WORLD_EFFECT":event["data"]["event"]=MEANINGS[fault]
                    self.assertEqual(after,before)
                    self.assertEqual(result["samples"],row["samples"])

    def test_no_bound_subject_no_mutation(self):
        _,row=self.fixture()
        for fault in FAULTS:
            control=RouteControlNegative(fault)
            self.assertIs(control.mutate(row,{}),row)
            self.assertFalse(control.applied)

    def test_baseline_meaning_never_targets_later_fault_window(self):
        subject,row=self.fixture();row["samples"][0]["routeControl"]={}
        for fault in MEANINGS:
            control=RouteControlNegative(fault)
            self.assertIs(control.mutate(row,[subject]),row)
            self.assertFalse(control.applied)

    def test_unknown_control_is_rejected(self):
        with self.assertRaises(ValueError):RouteControlNegative("other")

    def test_exact_reason_required_for_each_control(self):
        details={"absent-subject":"exact follower is absent or duplicated",
                 "stale-subject":"selected actor belongs to a stale fieldEpoch",
                 "route-missing-cpu":"CPU work receipt is not one measured cycle",
                 "route-missing-pin":"player pin sequence differs"}
        for fault in FAULTS:
            with self.subTest(fault=fault):
                if fault in MEANINGS:
                    key=dict(zip(MEANINGS,("start","commit","finish","control")))[fault]
                    error={"code":"follower-terminal-trace-gap","detail":{
                        name:0 if name==key else 1 for name in ("start","commit","finish","control")}}
                elif fault=="route-missing-cleanup":
                    error={"code":"route-control-cleanup-rejected","message":"player fault cleanup must close the core"}
                else:error={"code":"cadence-observation-invalid","detail":details[fault]}
                result={"passed":False,"failures":[error] if fault=="route-missing-cleanup" else [],
                        "measurements":{"live-route-control-v1":{"failures":[error]}}}
                self.assertTrue(validate_negative_result(fault,result))
                for bad in ({**result,"passed":True},{**result,"passed":0},{"passed":False},
                            {**result,"failures":[],"measurements":{"live-route-control-v1":{"failures":[{"code":"other"}]}}}):
                    with self.assertRaises(ValueError):validate_negative_result(fault,bad)
                if fault in MEANINGS:
                    error["detail"][key]=False
                    with self.assertRaises(ValueError):validate_negative_result(fault,result)

    def test_real_cadence_baseline_replay_requires_each_terminal_meaning(self):
        from tools.overworld import test_devtools_route_control_measurement as fixtures
        from tools.overworld.devtools_route_control_measurement import LiveRouteControlMeasurement
        records=[]; arguments={}
        original_init=LiveRouteControlMeasurement.__init__
        original_observe=LiveRouteControlMeasurement.observe_record
        def initialize(meter,test,**kwargs):
            arguments.update(test=deepcopy(test),kwargs=deepcopy(kwargs))
            original_init(meter,test,**kwargs)
        def observe(meter,row,**kwargs):
            records.append(deepcopy(row))
            return original_observe(meter,row,**kwargs)
        with patch.object(LiveRouteControlMeasurement,"__init__",initialize), patch.object(LiveRouteControlMeasurement,"observe_record",observe):
            fixtures.LiveRouteControlTests().baseline()
        for fault in ("absent-subject","stale-subject",*MEANINGS):
            meter=LiveRouteControlMeasurement(arguments["test"],**arguments["kwargs"])
            control=RouteControlNegative(fault)
            for row in records:
                result=meter.observe_record(control.mutate(row,{"cyndaquil":meter.subject} if meter.subject else {}),full_report=False)
                if result["failures"]:break
            self.assertTrue(control.applied)
            validate_negative_result(fault,{"passed":False,"measurements":{"live-route-control-v1":meter.result()}})


if __name__ == "__main__":unittest.main()
