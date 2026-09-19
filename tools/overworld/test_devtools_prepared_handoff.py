"""Prepared trace handoff continuity, with no setup assertion credit."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_test_contract import TestEvaluator,validate_test
from tools.overworld.test_devtools_test_contract import recipe,snapshot,event


class PreparedHandoffTests(unittest.TestCase):
    def fixture(self):
        test=recipe();test["mode"]="prepared"
        test["setup"]=[dict(id="prepare",op="spawn",args=dict(species=165,role="wild"),
                           budget=dict(maxSeconds=10,maxFrames=10,noProgressFrames=10))]
        e=TestEvaluator(test)
        first=snapshot(1);first.update(nativeCycle=10,fieldAvailable=True,observationBoundary="main-task-queue-completion");e.observe(first,count_frame=False)
        last=snapshot(2);last.update(prepared=True,nativeCycle=12,fieldAvailable=True,observationBoundary="main-task-queue-completion")
        receipt=dict(preparedOnly=True,snapshot=deepcopy(last),events=[event(2,sequence=1),event(2,sequence=2)],
            setupBoundary=dict(frame=2,nativeCycle=12,endpointNativeCycle=12,eventsDrained=True,traceSequences={"1":2}))
        return e,dict(phase="setup",action="prepare",command="spawn",receipt=receipt,snapshot=last)

    def test_contiguous_handoff_no_frame_or_event_credit_then_normal_sequence(self):
        e,r=self.fixture();result=e.observe_prepared_command(r)
        self.assertFalse(result["failures"])
        self.assertEqual(e.last_sequence,{1:2})
        self.assertEqual((e.frames,e.sampled_frames,len(e.events)),(0,0,0))
        s=snapshot(3);s.update(prepared=True,nativeCycle=14)
        e.observe(s,[event(3,sequence=3)])
        self.assertFalse(e.failures)

    def test_boot_diagnostics_have_no_setup_trace_credit(self):
        e,r=self.fixture()
        r["receipt"]["events"].insert(0,dict(frame=0,kind="native-observation",
            data=dict(observation="walk-policy",sequence=99)))
        self.assertFalse(e.observe_prepared_command(r)["failures"])
        self.assertEqual(e.last_sequence,{1:2})
        self.assertEqual(len(e.events),0)

    def test_missing_rollback_mismatch_bound_duplicate_and_status_fail_closed(self):
        for fault in ("missing","rollback","mismatch","bound","duplicate","status","frame","watermark","action"):
            e,r=self.fixture()
            if fault=="missing":r["receipt"]["events"].pop(0)
            if fault=="rollback":e.last_sequence={1:4}
            if fault=="mismatch":r["receipt"]["snapshot"]["frame"]+=1
            if fault=="bound":e.bind("subject",e.latest)
            if fault=="duplicate":e.observe_prepared_command(r)
            if fault=="status":r["receipt"]["events"].append(dict(frame=2,kind="trace-status",data={"coverageComplete":False}))
            if fault=="frame":r["receipt"]["events"][0]["frame"]=0
            if fault=="watermark":r["receipt"]["setupBoundary"]["traceSequences"]["1"]=3
            if fault=="action":r["action"]="other"
            old=deepcopy(e.last_sequence)
            with self.subTest(fault=fault):
                self.assertTrue(e.observe_prepared_command(r)["failures"])
                self.assertEqual(e.last_sequence,old)

    def test_validated_same_frame_refresh_is_not_general_permission(self):
        e,r=self.fixture()
        for s in (r["snapshot"],r["receipt"]["snapshot"]):s.update(frame=1,nativeCycle=10)
        r["receipt"]["setupBoundary"].update(frame=1,nativeCycle=10,endpointNativeCycle=10)
        for v in r["receipt"]["events"]:v["frame"]=1
        self.assertFalse(e.observe_prepared_command(r)["failures"])
        self.assertTrue(e.observe(r["snapshot"],count_frame=False)["failures"])

    def test_retained_failure_generic_endpoint_red_and_shared_handoff_green(self):
        root=Path(__file__).resolve().parents[2]
        path=root/"build/overworld-devtools/test-3de99b0ee8014f349939e299b6712ef8/observations.jsonl"
        if not path.is_file():self.skipTest("optional retained failing native stream absent")
        with path.open() as stream:rows=[json.loads(line) for line in stream]
        test=validate_test(json.loads((root/"tests/overworld/test-recipes/profile.owner-reader-control.json").read_text()))
        for fixed in (False,True):
            e=TestEvaluator(test);e.observe(rows[0]["initialSnapshot"],count_frame=False)
            if fixed:e.observe_prepared_command(rows[1])
            else:e.observe(rows[1]["snapshot"],count_frame=False)
            e.bind("mankey",rows[2]["snapshot"])
            for s in rows[3]["samples"]:
                e.observe(s,[v for v in rows[3]["events"] if v["frame"]==s["frame"]])
            with self.subTest(fixed=fixed):
                if fixed:self.assertFalse(e.failures,e.failures)
                else:self.assertIn("native event sequence",str(e.failures))

    def test_same_frame_party_refresh_rejects_field_drift(self):
        for field in (None,"context","player","nativeCycle","fieldAvailable","observationBoundary"):
            e,r=self.fixture()
            for s in (r["snapshot"],r["receipt"]["snapshot"]):
                s.update(frame=1,nativeCycle=10,party=[{"hp":21}])
                if field=="context":s["context"]["fieldEpoch"]+=1
                if field=="player":s["player"]["x"]+=1
                if field=="nativeCycle":s["nativeCycle"]+=1
                if field=="fieldAvailable":s["fieldAvailable"]=False
                if field=="observationBoundary":s["observationBoundary"]="other"
            r["receipt"]["setupBoundary"].update(frame=1,nativeCycle=r["snapshot"]["nativeCycle"],endpointNativeCycle=11)
            for v in r["receipt"]["events"]:v["frame"]=1
            with self.subTest(field=field):self.assertEqual(bool(e.observe_prepared_command(r)["failures"]),field is not None)


if __name__=="__main__":unittest.main()
