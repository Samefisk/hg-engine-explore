"""Natural resolver inputs are discovery only, never synthetic parity proof."""
import tempfile
import unittest
from tools.overworld.test_devtools_observer import Fixture


class ResolverDiscoveryTests(unittest.TestCase):
    def test_capture_actual_blob_and_owner_but_not_controlled_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(directory)
            observer = f.observer
            f.regs.r0, f.regs.r1 = 0x02240000, 1024
            f.regs.r2, f.regs.r3 = 0x02241000, 0x02242000
            f.put(f.regs.r2, bytes(20)); f.put(f.regs.r3, bytes(256))
            f.native_heap_generation = 7
            context = {"returnValue": 0, "entry": {"actorFrame": 100, "nativeCycle": 10},
                       "returned": {"actorFrame": 100, "nativeCycle": 11}}
            before = observer._resolver_before()
            observer._resolver_after(before, context)
            found = observer.resolver_discovery
            self.assertEqual((found["blobAddress"], found["blobSize"]), (0x02240000, 1024))
            self.assertEqual(found["fieldPointer"], 0x02231000)
            self.assertEqual(found["heapGeneration"], 7)
            self.assertEqual(found["returnNativeCycle"], 11)
            self.assertEqual(found["status"], 0)
            f.native_bridge_active = True
            f.regs.r0 = 0x02250000
            observer._resolver_after(observer._resolver_before(), context)
            self.assertEqual(observer.resolver_discovery, found)

    def test_failed_natural_call_does_not_supply_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(directory)
            f.regs.r2 = 0x02241000; f.put(f.regs.r2, bytes(20))
            observer = f.observer
            observer._resolver_after(observer._resolver_before(), {"returnValue": 2})
            self.assertIsNone(observer.resolver_discovery)


if __name__ == "__main__":
    unittest.main()
