"""Internal compact reports preserve checks; public proof exports stay detached."""
from copy import deepcopy
import unittest
from unittest.mock import PropertyMock, patch

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.test_devtools_cadence_measurement import Route
from tools.overworld import test_devtools_prepared_sequence as prepared


class CompactReportTests(unittest.TestCase):
    def test_full_and_compact_replay_preserve_every_frame_and_fault(self):
        for fault in (False, True):
            route=Route(); route.setup_bind(); route.move(1)
            if fault:
                route.records[-4]["samples"][0]["actors"][0]["engineObject"]["flags"] &= ~0x40000
            meters=[]; clocks=[]
            for full in (True,False):
                meter=UnmountedCadenceMeasurement(route.test,max_frames=32000)
                seen=[]
                for record in route.records:
                    result=meter.observe_record(record,full_report=full,
                        frame_callback=lambda s,e,m: seen.append((s["frame"],len(e),m.native_cycles)))
                    if result["failures"]: break
                meters.append(meter.result()); clocks.append(seen)
            self.assertEqual(meters[0],meters[1])
            self.assertEqual(clocks[0],clocks[1])
            self.assertEqual(bool(meters[0]["failures"]),fault)

    def test_internal_evaluator_does_not_export_retained_history(self):
        evaluator,commands=prepared.PreparedSequenceTests().fixture()
        meter=evaluator.measurements["unmounted-cadence-v1"]
        with patch.object(meter,"result",side_effect=AssertionError("full export on hot path")):
            for command in commands:
                result=evaluator.observe_record(command,full_report=False)
                self.assertEqual(result["failures"],[])
                self.assertNotIn("measurements",result)
        self.assertEqual(evaluator.last_sequence,{1:75})
        self.assertIn("preparedSetup",evaluator.result()["measurements"]["unmounted-cadence-v1"])

    def test_public_and_compact_results_are_detached(self):
        meter=UnmountedCadenceMeasurement(Route().test,max_frames=32000)
        meter.subject={"handle":{"value":1}}
        meter.motion_tail.append({"inputPhase":[{"frame":1}]})
        meter.prepared_commands=[{"receipt":{"events":[{"frame":1}]}}]
        full=meter.result(); compact=meter.progress_result()
        full["motionTail"][0]["inputPhase"][0]["frame"]=99
        full["preparedSetup"][0]["receipt"]["events"].clear()
        compact["subject"]["handle"]["value"]=99
        self.assertEqual(meter.motion_tail[0]["inputPhase"][0]["frame"],1)
        self.assertEqual(len(meter.prepared_commands[0]["receipt"]["events"]),1)
        self.assertEqual(meter.subject["handle"]["value"],1)

    def test_normal_raw_frames_and_ready_poll_never_export_proof_history(self):
        from tools.overworld.test_devtools_cadence_integration import installed, KIND
        route=Route(); route.setup_bind(); route.move(1)
        evaluator=installed(route)
        remaining=iter(route.records)
        for record in remaining:
            evaluator.observe_record(record,full_report=False)
            if record.get("command")=="bind": break
        meter=evaluator.measurements[KIND]
        frames=[]
        with patch.object(meter,"result",side_effect=AssertionError("full export in movement loop")):
            for record in remaining:
                result=evaluator.observe_record(record,full_report=False,
                    frame_callback=lambda sample,current: frames.append(sample["frame"]))
                self.assertEqual(result["failures"],[])
            self.assertFalse(evaluator.check({"kind":"measurement-complete","measurement":KIND}))
        self.assertEqual(len(frames),32)
        self.assertEqual(meter.player_motions,1)
        self.assertEqual(meter.follower_motions,1)

    def test_incomplete_report_names_pending_recovery(self):
        meter=UnmountedCadenceMeasurement(Route().test,max_frames=32000)
        meter.handoffs=[{"canceledMotion":{}}]
        with patch.object(type(meter.crash_presentation), "ready", new_callable=PropertyMock) as ready:
            ready.return_value=False
            detail=meter.finish()["failures"][0]["detail"]
        self.assertTrue(detail["crashPresentationPending"])
        self.assertTrue(detail["handoffRecoveryPending"])


if __name__ == "__main__": unittest.main()
