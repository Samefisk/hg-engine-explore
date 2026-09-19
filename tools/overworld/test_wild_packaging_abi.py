"""Exercise the real Make callback gate without running Make's packing work."""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import struct
import tempfile
import types
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


class WildPackagingAbiTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((REPO / "scripts/make.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "VerifyOverworldWildSpawnsOverlay")
        # Independent contract: slot 7 receives a service version, not a state pointer.
        self.names = (
            "OverworldWildSpawns_OverlayOnPlayerStep",
            "OverworldWildSpawns_OverlayTryPrimeBattleFromTalk",
            "OverworldWildSpawns_OverlayCleanupPendingBattle",
            "OverworldWildSpawns_CleanupResidentData",
            "OverworldWildSpawns_OverlayOnPlayerFrame",
            "OverworldWildSpawns_OverlayOnFieldBusy",
            "OverworldWildSpawns_ApplyTransitionWork",
            "OverworldWildSpawns_ValidateHopLandingValue",
            "OverworldWildSpawns_CopyNativeShadowValue",
            "OverworldWildSpawns_BeginMountSelectedFollower",
        )
        self.addresses = [0x023CD100 + slot * 0x20 for slot in range(10)]
        self.addresses[8] = 0x023CD028
        self.old_landing_address = 0x023CD400
        self.symbols = ["023cd000 g O .text 00000028 gOverworldWildSpawnsOverlayEntry"]
        self.symbols += [f"{address:08x} g F .text 00000010 {name}"
                         for name, address in zip(self.names, self.addresses)]
        self.symbols += [f"{self.old_landing_address:08x} l F .text 00000010 "
                         "OverworldWildSpawns_IsBehaviorAllowedHopLandingTile"]
        namespace = {
            "subprocess": types.SimpleNamespace(check_output=lambda _: "\n".join(self.symbols).encode()),
            "struct": struct, "hashlib": hashlib, "OBJDUMP": "unused-test-objdump",
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), "scripts/make.py", "exec"), namespace)
        self.verify = namespace[function.name]

    def check_entry(self, *, old_landing=False, packaged_mismatch=False):
        callbacks = [address | 1 for address in self.addresses]
        if old_landing:
            callbacks[7] = self.old_landing_address | 1
        binary = b"\0" * 0x28 + struct.pack("<10I", *callbacks)
        with tempfile.TemporaryDirectory(prefix="ow-wild-abi-") as directory:
            output = Path(directory) / "linked.bin"
            package = Path(directory) / "package.bin"
            output.write_bytes(binary)
            package.write_bytes(binary + (b"\0" if packaged_mismatch else b""))
            with contextlib.redirect_stdout(io.StringIO()):
                self.verify("synthetic-symbols.elf", str(output), str(package))

    def test_versioned_value_callback_is_accepted(self):
        self.check_entry()

    def test_old_private_state_callback_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "does not exactly match"):
            self.check_entry(old_landing=True)

    def test_missing_value_callback_is_rejected(self):
        self.symbols = [line for line in self.symbols if self.names[7] not in line]
        with self.assertRaisesRegex(RuntimeError, "missing linked symbols"):
            self.check_entry()

    def test_different_packaged_bytes_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "differs from its linked binary"):
            self.check_entry(packaged_mismatch=True)


if __name__ == "__main__":
    unittest.main()
