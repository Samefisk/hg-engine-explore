"""Reject stale or different resolver inputs before any prepared call."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure


class ResolverAuthTests(unittest.TestCase):
    def test_inputs_bound_to_live_service_blob_and_natural_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "build").mkdir()
            blob = b"test blob"
            (root / "build/OverworldWildBehaviorData.bin").write_bytes(blob)
            s = DevtoolsSession.__new__(DevtoolsSession)
            service = dict(name="resolver", status="available", version=1, size=16,
                address=0x02300000, callbacks=dict(resolve=0x02301001, inspectClass=0x02302001))
            s.rt = SimpleNamespace(REPO=root, ACTOR_DESCRIPTOR={"privateServices": [service]})
            discovery = dict(blobAddress=0x02200000, blobSize=len(blob), fieldPointer=0x02210000,
                             heapGeneration=7, status=0, requestHex=bytes(20).hex(),
                             entryNativeCycle=10, returnNativeCycle=11)
            s.native_observation = SimpleNamespace(resolver_discovery=deepcopy(discovery))
            s.native_heap_generation = 7
            s.field_pointer = lambda: 0x02210000
            s.target = lambda name: 0x02301000
            memory = {0x02300000: struct.pack("<IHHII", 0x5250574F,1,16,0x02301001,0x02302001),
                      0x02301000: b"C"*32, 0x02200000: blob}
            s.packaged_code = lambda address, size: memory[address][:size]
            s.read = lambda address, size: memory[address][:size]
            inputs = s._resolver_probe_inputs()
            self.assertEqual(inputs["blob_bytes"], blob)
            self.assertEqual(inputs["blob_address"], 0x02200000)
            self.assertEqual(inputs["service_identity"]["resolveAddress"], 0x02301001)
            for field, value in (("heapGeneration",8),("fieldPointer",0x02220000),("blobSize",1),("status",2)):
                with self.subTest(field=field):
                    s.native_observation.resolver_discovery = {**discovery, field:value}
                    with self.assertRaises(DevtoolsFailure): s._resolver_probe_inputs()
            s.native_observation.resolver_discovery = discovery
            memory[0x02200000] = b"wrongblob"
            with self.assertRaises(DevtoolsFailure): s._resolver_probe_inputs()
            memory[0x02200000] = blob
            memory[0x02300000] = bytes(16)
            with self.assertRaises(DevtoolsFailure): s._resolver_probe_inputs()


if __name__ == "__main__": unittest.main()
