"""Exercise the real Make condition-service ABI gate."""

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


class ConditionPackagingAbiTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((REPO / "scripts/make.py").read_text())
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "VerifyOverworldFollowerSelectorOverlay"
        )
        self.callback_names = (
            "OverworldFollowerSelector_ValidateImpl",
            "OverworldFollowerSelectorUI_Open",
            "OverworldFollowerSelectorUI_SetSelection",
            "OverworldFollowerSelectorUI_Update",
            "OverworldFollowerSelectorUI_Close",
            "OverworldFollowerSelectorUI_IsOpen",
            "OverworldFollowerSelectorInput_Filter",
            "OverworldFollowerSelectorInput_Cancel",
            "OverworldFollowerSelectorInput_IsActive",
            "OverworldFollowerSelector_GetSelectedPokemon",
            "OverworldFollowerSelector_GetReleaseDistance",
            "OverworldFollowerSelector_IsReleaseTileAvailable",
            "OverworldFollowerSelector_BuildDirectedDirections",
        )
        self.condition_callback_names = (
            "OverworldBehaviorCondition_PrepareActor",
            "OverworldBehaviorCondition_EvaluatePrepared",
            "OverworldBehaviorCondition_ValidateResolveRequest",
        )
        self.callback_addresses = tuple(
            0x023C0500 + index * 0x20
            for index in range(len(self.callback_names))
        )
        self.condition_callback_addresses = (
            0x023C2300,
            0x023C2320,
            0x023C2340,
        )
        symbols = [
            "023c0400 g O .text 0000003c gOverworldFollowerSelectorOverlayEntry",
            "023c22a0 g O .text 00000018 gOverworldBehaviorConditionServiceEntry",
            "023c22b8 g F .text 00000018 OverworldBehaviorConditionService_Get",
        ]
        symbols.extend(
            f"{address:08x} g F .text 00000010 {name}"
            for name, address in zip(self.callback_names, self.callback_addresses)
        )
        symbols.extend(
            f"{address:08x} g F .text 00000010 {name}"
            for name, address in zip(
                self.condition_callback_names,
                self.condition_callback_addresses,
            )
        )
        namespace = {
            "subprocess": types.SimpleNamespace(
                check_output=lambda _: "\n".join(symbols).encode()
            ),
            "struct": struct,
            "hashlib": hashlib,
            "OBJDUMP": "unused-test-objdump",
        }
        exec(
            compile(
                ast.Module(body=[function], type_ignores=[]),
                "scripts/make.py",
                "exec",
            ),
            namespace,
        )
        self.verify = namespace[function.name]

    def check_version(self, version: int) -> None:
        overlay = bytearray(0x1ED0)
        struct.pack_into(
            "<IHH13I",
            overlay,
            0,
            0x3153464F,
            5,
            60,
            *(address | 1 for address in self.callback_addresses),
        )
        struct.pack_into(
            "<IHH4I",
            overlay,
            0x1EA0,
            0x4342574F,
            version,
            24,
            *(address | 1 for address in self.condition_callback_addresses),
            0,
        )
        with tempfile.TemporaryDirectory(prefix="ow-condition-abi-") as directory:
            linked = Path(directory) / "linked.bin"
            packaged = Path(directory) / "packaged.bin"
            linked.write_bytes(overlay)
            packaged.write_bytes(overlay)
            with contextlib.redirect_stdout(io.StringIO()):
                self.verify("synthetic-symbols.elf", str(linked), str(packaged))

    def test_version_8_is_accepted(self):
        self.check_version(8)

    def test_stale_version_7_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "condition service ABI"):
            self.check_version(7)


if __name__ == "__main__":
    unittest.main()
