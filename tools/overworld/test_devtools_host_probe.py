"""Fixed-work probe controls; no emulator or workload timing thresholds."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from tools.overworld import devtools_host_probe as probe


class HostProbeTests(unittest.TestCase):
    def receipt(self):
        return probe.measure_host_probe(iter((100, 125)).__next__)

    def test_fixed_result_two_reads_and_identity_validation(self):
        with patch.object(probe.time, "thread_time_ns", side_effect=(100,125)) as clock:
            value=probe.measure_host_probe()
        self.assertEqual(clock.call_count,2)
        self.assertEqual(value,dict(version=1,iterations=64,result=3263322488,
            cpuNs=25,scope="fixed-work-host-thread-diagnostic-not-guest-timing"))
        self.assertIs(probe.validate_host_probe(value),value)

    def test_clock_faults_produce_no_receipt(self):
        for times in ((-1,3),(3,2),(True,3),(1,False),(1.0,2),(0,10**12+1)):
            with self.subTest(times=times),self.assertRaises(ValueError):
                probe.measure_host_probe(iter(times).__next__)
        with self.assertRaises(StopIteration):probe.measure_host_probe(iter((1,)).__next__)
        self.assertEqual(probe.measure_host_probe(lambda:0)["cpuNs"],0)

    def test_incomplete_or_changed_receipts_fail_without_mutation(self):
        original=self.receipt()
        for key in original:
            value=deepcopy(original);del value[key]
            with self.subTest(missing=key),self.assertRaises(ValueError):probe.validate_host_probe(value)
        for key,bad in (("version",True),("version",2),("iterations",63),("iterations",True),
                        ("result",0),("result",3263322488.0),("cpuNs",-1),("cpuNs",True),
                        ("cpuNs",10**12+1),("scope","guest cycles"),("extra",1)):
            value=deepcopy(original);value[key]=bad;saved=deepcopy(value)
            with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):probe.validate_host_probe(value)
            self.assertEqual(value,saved)

    def test_changed_iteration_work_cannot_issue_valid_result(self):
        with patch.object(probe,"ITERATIONS",63),self.assertRaises(ValueError):
            self.receipt()


if __name__ == "__main__": unittest.main()
