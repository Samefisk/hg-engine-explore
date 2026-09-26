from copy import deepcopy
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_runtime import DevtoolsFailure, DevtoolsSession


class ConditionAuthTests(unittest.TestCase):
    def test_inputs_bind_live_blob_service_table_and_all_callbacks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "build").mkdir()
            blob = b"condition test blob"
            (root / "build/OverworldWildBehaviorData.bin").write_bytes(blob)
            (root / "build/overworld_follower_selector_overlay_linked.o").write_bytes(b"elf")
            prepare, evaluate, validate = 0x023C2400, 0x023C2500, 0x023C2600
            service = struct.pack("<IHHIIII", 0x4342574F, 8, 24,
                                  prepare | 1, evaluate | 1, validate | 1, 0)
            code = {prepare: b"P" * 32, evaluate: b"E" * 32,
                    validate: b"V" * 32, 0x023C22A0: service}
            session = DevtoolsSession.__new__(DevtoolsSession)
            session.rt = SimpleNamespace(
                REPO=root,
                SELECTOR_SYMBOLS={"validate": validate},
                linked_symbol=lambda table, name: validate,
            )
            discovery = {
                "blobAddress": 0x02200000,
                "blobSize": len(blob),
                "fieldPointer": 0x02210000,
                "heapGeneration": 7,
                "status": 0,
            }
            session.native_observation = SimpleNamespace(
                resolver_discovery=deepcopy(discovery))
            session.native_heap_generation = 7
            session.field_pointer = lambda: 0x02210000
            session.target = lambda name: {
                "prepare_conditions": prepare,
                "evaluate_conditions": evaluate,
            }[name]
            session.packaged_code = lambda address, size: code[address][:size]
            session.read = lambda address, size: (
                blob[:size] if address == 0x02200000 else bytes(size))
            with patch("tools.overworld.devtools_runtime._elf_code",
                       side_effect=lambda path, address, size: code[address][:size]):
                inputs = session._condition_probe_inputs()
                self.assertEqual(inputs["blob_address"], 0x02200000)
                self.assertEqual(inputs["blob_bytes"], blob)
                identity = inputs["service_identity"]
                self.assertEqual(identity["serviceAddress"], 0x023C22A0)
                self.assertEqual(identity["prepareAddress"], prepare | 1)
                self.assertEqual(identity["evaluateAddress"], evaluate | 1)
                self.assertEqual(identity["validateAddress"], validate | 1)
                for field, value in (("heapGeneration", 8),
                                     ("fieldPointer", 0x02220000),
                                     ("blobSize", 1), ("status", 2)):
                    session.native_observation.resolver_discovery = {
                        **discovery, field: value}
                    with self.subTest(field=field), self.assertRaises(DevtoolsFailure):
                        session._condition_probe_inputs()
                session.native_observation.resolver_discovery = discovery
                code[0x023C22A0] = bytes(24)
                with self.assertRaises(DevtoolsFailure):
                    session._condition_probe_inputs()


if __name__ == "__main__":
    unittest.main()
