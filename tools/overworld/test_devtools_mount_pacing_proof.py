"""Controller rows are recomputed from raw retained observations."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mount_pacing_proof import KIND, REQUIREMENT, FAULTS, contract, measurements, MountedPacingNegative, validate_negative_result
from tools.overworld.devtools_mount_pacing_measurement import MountedPacingMeasurement
from tools.overworld.test_devtools_mount_pacing_measurement import pacing_fixture


def replay(fault=None):
    baseline,subject,receipt,rows=pacing_fixture()
    meter=MountedPacingMeasurement(100)
    meter.arm(subject,baseline,receipt)
    negative=MountedPacingNegative(fault) if fault else None
    for snapshot,events in rows:
        row=dict(phase="observe",samples=[snapshot],events=events)
        if negative: row=negative.mutate(row,{"mounted":subject})
        meter.observe(row["samples"][0],row["events"])
        if meter.failures: break
        if meter.main_complete and len(meter.windows)==1: meter.begin_recovery(snapshot)
    if not meter.failures:
        reader=dict(receipt,closed=True,counts=meter.counts,
                    latestCompletedPose=rows[-1][0]["mountPacing"]["latestCompletedPose"])
        meter.close(dict(closed=True,advancedFrames=0,acceptedProof=False,mountPacing=reader),rows[-1][0])
    value=meter.result()
    return dict(passed=value["passed"],failures=[],measurements={KIND:value})


class MountedPacingProofTests(unittest.TestCase):
    def record(self):
        return dict(sessionId="host",sessionCleanup=dict(sessionId="host",closed=True,errors=[]))

    def test_exact_registry_contract(self):
        registry=json.loads(Path("tools/overworld/runtime_proof_registry.json").read_text())
        contracts=next(v for v in registry.values() if isinstance(v,dict) and isinstance(v.get(REQUIREMENT),dict))
        self.assertEqual(contract(),contracts[REQUIREMENT])

    def test_all_nine_rows_recomputed(self):
        value=replay()
        value["measurements"][KIND]["proofEvidence"]={"fake":True}
        self.assertEqual(len(measurements(value,self.record())),9)

    def test_idle_pose_with_future_origin_is_not_a_motion_start(self):
        value = replay();meter = value['measurements'][KIND]
        window = meter['windows'][0]
        idle = deepcopy(window['callbacks'][0])
        idle['data']['publicSubject']['origin'] = dict(zip(('x','y'),window['motions'][2]['origin']))
        idle['data']['publicSubject']['motionPhase'] = 'IDLE'
        idle['data']['returnActorFrame'] -= 1
        idle['data']['returnNativeCycle'] -= 1
        window['callbacks'].insert(0,idle)
        meter['cleanup']['mountPacing']['counts']['presentation'] += 1
        self.assertEqual(len(measurements(value,self.record())),9)

    def test_each_fault_detected_for_its_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault): validate_negative_result(replay(fault),fault)

    def test_unrelated_failure_not_control(self):
        with self.assertRaisesRegex(ValueError,"unrelated"):
            validate_negative_result(dict(passed=False,failures=["unrelated"]),FAULTS[0])

    def test_raw_changes_reject(self):
        for fault in ("cleanup","closed","pair","steps","trace","control"):
            value=replay(); meter=value["measurements"][KIND]; record=self.record()
            if fault=="cleanup": record["sessionCleanup"]["closed"]=False
            elif fault=="closed": meter["closed"]=False
            elif fault=="pair": meter["windows"][0]["callbacks"][0]["data"]["mount"]["pos_x"]+=1
            elif fault=="steps": meter["windows"][0]["steps"].pop()
            elif fault=="trace": meter["windows"][0]["traces"]=[]
            else: meter["cleanup"]["mountPacing"]["latestCompletedPose"]["avatarControl"]["flags"]=1
            with self.subTest(fault=fault),self.assertRaises(ValueError): measurements(value,record)

    def test_changed_duration_contract_rejected_independently(self):
        value = replay()
        # Exercise the controller's direct retained-vector check separately
        # from the meter's unchanged-stream rejection.
        motions = value["measurements"][KIND]["windows"][0]["motions"]
        motions[3]["duration"] = 8
        with self.assertRaisesRegex(ValueError,"mounted Cyndaquil acceleration duration differs"):
            measurements(value,self.record())


if __name__=="__main__": unittest.main()
