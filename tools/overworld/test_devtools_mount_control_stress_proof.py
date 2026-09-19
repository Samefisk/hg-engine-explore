"""Exact D4 contract rows and copied-data rejection; never runtime acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_mount_control_stress import MountControlStressMeasurement
from tools.overworld.devtools_mount_control_stress_proof import (
    KIND,REQUIREMENTS,FAULTS,contract,measurements,MountControlStressNegative,validate_negative_result,
)
from tools.overworld.test_devtools_mount_control_stress import StressFixture,complete


class MountControlStressProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values={}
        for requirement in REQUIREMENTS:
            meter,_=complete(requirement)
            cls.values[requirement]=meter.finish()

    def test_exact_retained_contracts(self):
        registry=json.loads((Path(__file__).resolve().parents[2]/"tools/overworld/runtime_proof_registry.json").read_text())
        for requirement in REQUIREMENTS:
            specs=next(v[requirement] for v in registry.values() if isinstance(v,dict)
                       and isinstance(v.get(requirement),dict) and "natural-input" in v[requirement])
            self.assertEqual(contract(requirement),specs)

    def test_rows_are_recomputed_not_trusted(self):
        for requirement,count in zip(REQUIREMENTS,(10,6)):
            value=deepcopy(self.values[requirement]);value["proofEvidence"]={"invented":True}
            self.assertEqual(len(measurements(value,requirement)),count)

    def test_later_settled_recovery_frame_keeps_the_completed_motion_proof(self):
        value = deepcopy(self.values[REQUIREMENTS[0]])
        value["frames"] += 24
        value["milestones"]["recovery"] += 24
        value["milestoneEvidence"]["recovery"]["frame"] += 24
        self.assertEqual(len(measurements(value, REQUIREMENTS[0])), 10)

    def test_each_mutant_rejected_for_exact_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                f=StressFixture(REQUIREMENTS[0]);m=MountControlStressMeasurement(f.requirement);m.arm(f.subject,f.snapshot)
                negative=MountControlStressNegative(fault)
                for s,e in f.move():
                    row=negative.mutate(dict(phase="observe",samples=[s],events=e),{"mount":f.subject})
                    m.observe(row["samples"][0],row["events"])
                self.assertTrue(negative.applied)
                validate_negative_result(m.finish(),fault)

    def test_unrelated_failure_is_not_a_negative_pass(self):
        with self.assertRaisesRegex(ValueError,"unrelated"):
            validate_negative_result(dict(passed=False,failures=["something else"]),FAULTS[0])

    def test_raw_motion_counts_milestones_and_kind_mutations_fail(self):
        for fault in ("motion","lifecycle","count","turns","frames","milestones","normal-step","closed","subject"):
            with self.subTest(fault=fault):
                value=deepcopy(self.values[REQUIREMENTS[0]])
                if fault=="motion":value["motionSummaries"][0]["motion"]["samples"][0]["elapsed"]+=1
                if fault=="lifecycle":value["motionSummaries"][0]["lifecycle"].pop()
                if fault=="count":value["motions"]-=1
                if fault=="turns":value["turns"]-=1
                if fault=="frames":value["routeFrames"]-=1
                if fault=="milestones":value["milestones"].pop("remount")
                if fault=="normal-step":value["milestoneEvidence"]["unmounted-step"]["player"]["flags"]=0
                if fault=="closed":value["closed"]=False
                if fault=="subject":value["initial"]["actor"]["species"]=56
                with self.assertRaises((ValueError,KeyError)):measurements(value,REQUIREMENTS[0])


if __name__=="__main__":unittest.main()
