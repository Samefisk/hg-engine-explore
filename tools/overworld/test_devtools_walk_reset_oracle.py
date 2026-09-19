"""Package/ELF mismatches must reject RESET proof before receipt replay."""
from copy import deepcopy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.control import _walk_reset_oracle


class WalkResetOracleTests(unittest.TestCase):
    def check(self, fault=None):
        base, address = 0x023B0000, 0x023B0080
        entry = struct.pack("<IHHII", 0x504D574F, 4, 16, base + 32, 0)
        table = bytearray(24)
        struct.pack_into("<I", table, 12, address | 1)
        code = bytes(range(32))
        image = bytearray(160)
        image[:16], image[32:56], image[128:] = entry, table, code
        descriptor = dict(privateServices=[dict(name="movementPolicy", address=base,
            policy=base + 32, version=4, size=16, reserved=0, status="available")],
            overlay=dict(id=158, base=base, fileSize=len(image), sha256=hashlib.sha256(image).hexdigest()))
        linked = deepcopy(image)
        if fault == "package": image[128] ^= 1
        elif fault == "elf": linked[128] ^= 1
        elif fault == "callback": struct.pack_into("<I", linked, 44, address + 5)
        elif fault == "version": descriptor["privateServices"][0]["version"] = 3
        elif fault == "duplicate": descriptor["privateServices"] *= 2
        elif fault == "bounds": descriptor["privateServices"][0]["address"] = base - 4
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # A tiny host fixture, never a copied game ROM.
            (root / "test.nds").touch()
            with patch("tools.overworld.control.load_debug_descriptor", return_value=descriptor), \
                 patch("scripts.verify_overworld_runtime_fixture.packaged_overlay", return_value=bytes(image)), \
                 patch("tools.overworld.devtools_engine.linked_symbols", return_value={}), \
                 patch("tools.overworld.devtools_engine.linked_symbol", return_value=address | 1), \
                 patch("tools.overworld.devtools_runtime._elf_code", side_effect=lambda _, a, n: bytes(linked[a-base:a-base+n])):
                return _walk_reset_oracle(root)

    def test_exact_package_and_linked_entry(self):
        result = self.check()
        self.assertEqual(result["callAddresses"], {"reduce_walk": 0x023B0080})
        self.assertEqual(result["serviceIdentity"]["reduceWalkAddress"], 0x023B0081)
        self.assertNotIn("acceptedProof", result)

    def test_mismatches_fail_closed(self):
        for fault in ("package", "elf", "callback", "version", "duplicate", "bounds"):
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                self.check(fault)


if __name__ == "__main__":
    unittest.main()
