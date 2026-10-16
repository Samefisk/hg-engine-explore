"""Exercise the real Make condition-service ABI gate."""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import struct
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


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
            "OverworldQueryCodeAddon_ConditionPrepare",
            "OverworldQueryCodeAddon_ConditionEvaluate",
            "OverworldQueryCodeAddon_ResolverCall",
            "OverworldQueryCodeAddon_ConditionNotify",
        )
        self.callback_addresses = tuple(
            0x023C0500 + index * 0x20
            for index in range(len(self.callback_names))
        )
        self.condition_callback_addresses = (
            0x023C2300,
            0x023C2320,
            0x023C2340,
            0x023C2360,
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
        self.symbols = symbols
        self.ownership_calls = []
        namespace = {
            "VerifyOverworldQueryCodeAddonOwnership": lambda *args: self.ownership_calls.append(args),
            "subprocess": types.SimpleNamespace(
                check_output=lambda _: "\n".join(self.symbols).encode()
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

    def check_version(self, version: int, notify_pointer: int | None = None) -> None:
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
        )
        if notify_pointer is not None:
            struct.pack_into("<I", overlay, 0x1EA0 + 20, notify_pointer)
        with tempfile.TemporaryDirectory(prefix="ow-condition-abi-") as directory:
            linked = Path(directory) / "linked.bin"
            packaged = Path(directory) / "packaged.bin"
            linked.write_bytes(overlay)
            packaged.write_bytes(overlay)
            with contextlib.redirect_stdout(io.StringIO()):
                self.verify("synthetic-symbols.elf", str(linked), str(packaged))

    def test_version_13_delegates_are_accepted(self):
        self.check_version(13)
        self.assertEqual(len(self.ownership_calls), 1)

    def test_stale_versions_are_rejected(self):
        for version in (9, 10, 12):
            with self.subTest(version=version):
                with self.assertRaisesRegex(RuntimeError, "condition service ABI"):
                    self.check_version(version)

    def test_retired_validate_callback_cannot_replace_resolver_call(self):
        self.symbols = [row.replace("OverworldQueryCodeAddon_ResolverCall",
                                   "OverworldQueryCodeAddon_ConditionValidate")
                        for row in self.symbols]
        with self.assertRaisesRegex(RuntimeError, "missing linked symbols.*ResolverCall"):
            self.check_version(13)

    def test_notify_pointer_must_match_the_linked_thumb_callback(self):
        for pointer in (0, 0x023C2360, 0x023C2363, 0x02208901):
            with self.subTest(pointer=pointer):
                with self.assertRaisesRegex(RuntimeError, "condition service ABI"):
                    self.check_version(13, pointer)


class CurrentLinkedPackagingTests(unittest.TestCase):
    """Run the actual gate against frozen native artifacts, using scratch copies."""

    @classmethod
    def setUpClass(cls):
        cls.files = (
            "overworld_follower_selector_overlay_linked.o",
            "output_overworld_follower_selector_overlay.bin",
            "overworld_wild_runtime_overlay_linked.o",
            "output_overworld_wild_runtime_overlay.bin",
            "overworld_query_code_addon/image.elf",
            "overworld_query_code_addon/query.bin",
            "overworld_query_code_addon/package.json",
            "overworld_query_code_addon/overworld_query_code_addon_package.h",
        )
        if not shutil.which("arm-none-eabi-objdump") or not all(
                (REPO / "build" / name).is_file() for name in cls.files):
            raise unittest.SkipTest("current native package artifacts are required")
        names = ("VerifyOverworldQueryCodeAddonOwnership",
                 "VerifyOverworldFollowerSelectorOverlay",
                 "VerifyOverworldWildRuntimeOverlay")
        tree = ast.parse((REPO / "scripts/make.py").read_text())
        namespace = {"subprocess": subprocess, "struct": struct,
                     "hashlib": hashlib, "Path": Path,
                     "OBJDUMP": "arm-none-eabi-objdump"}
        exec(compile(ast.Module(body=[node for node in tree.body
                                      if isinstance(node, ast.FunctionDef)
                                      and node.name in names], type_ignores=[]),
                     "scripts/make.py", "exec"), namespace)
        cls.gates = namespace

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ow-current-package-")
        self.addCleanup(self.directory.cleanup)
        self.build = Path(self.directory.name)
        for name in self.files:
            destination = self.build / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / "build" / name, destination)

    def check_gate(self, slug):
        name = ("VerifyOverworldFollowerSelectorOverlay" if slug == "follower_selector"
                else "VerifyOverworldWildRuntimeOverlay")
        linked = self.build / f"overworld_{slug}_overlay_linked.o"
        output = self.build / f"output_overworld_{slug}_overlay.bin"
        packaged = self.build / "packaged.bin"
        packaged.write_bytes(output.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            self.gates[name](str(linked), str(output), str(packaged))

    def change_binary_word(self, slug, offset, value):
        binary = self.build / f"output_overworld_{slug}_overlay.bin"
        raw = bytearray(binary.read_bytes())
        struct.pack_into("<I", raw, offset, value)
        binary.write_bytes(raw)

    def test_current_selector_and_runtime_pass(self):
        self.check_gate("follower_selector")
        self.check_gate("wild_runtime")

    def test_missing_condition_delegate_is_rejected(self):
        linked = self.build / "overworld_follower_selector_overlay_linked.o"
        raw = linked.read_bytes()
        old = b"OverworldQueryCodeAddon_ConditionPrepare\0"
        self.assertEqual(raw.count(old), 1)
        linked.write_bytes(raw.replace(old, b"X" + old[1:]))
        with self.assertRaisesRegex(RuntimeError, "missing linked symbols"):
            self.check_gate("follower_selector")

    def test_moved_condition_export_is_required_in_the_addon(self):
        linked = self.build / "overworld_query_code_addon/image.elf"
        raw = linked.read_bytes()
        old = b"OverworldBehaviorCondition_PrepareActor\0"
        self.assertEqual(raw.count(old), 1)
        linked.write_bytes(raw.replace(old, b"X" + old[1:]))
        with self.assertRaisesRegex(ValueError, "typed callback is not its exact hosted Thumb function"):
            self.check_gate("follower_selector")

    def test_addon_condition_pointer_must_be_thumb_and_exact(self):
        from verify_pokemon_move_history_capture import elf_bytes_at
        linked = self.build / "overworld_query_code_addon/image.elf"
        raw = bytearray(linked.read_bytes())
        image = elf_bytes_at(linked, 0x02080000, 144)
        offset = raw.index(image)
        pointer = struct.unpack_from("<I", raw, offset + 60)[0]
        struct.pack_into("<I", raw, offset + 60, pointer & ~1)
        linked.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "typed callback is not its exact hosted Thumb function"):
            self.check_gate("follower_selector")

    def test_changed_addon_package_is_rejected(self):
        binary = self.build / "overworld_query_code_addon/query.bin"
        raw = bytearray(binary.read_bytes()); raw[128] ^= 1
        binary.write_bytes(raw)
        with self.assertRaisesRegex(RuntimeError, "package differs from its linked image"):
            self.check_gate("follower_selector")

    def test_changed_addon_image_is_rejected(self):
        from verify_pokemon_move_history_capture import elf_bytes_at
        linked = self.build / "overworld_query_code_addon/image.elf"
        raw = bytearray(linked.read_bytes())
        image = elf_bytes_at(linked, 0x02080000, 144)
        raw[raw.index(image) + 144] ^= 1
        linked.write_bytes(raw)
        with self.assertRaises((RuntimeError, ValueError)):
            self.check_gate("follower_selector")

    def test_addon_receipt_and_generated_header_are_required(self):
        for name, pattern in (("package.json", "receipt differs"),
                              ("overworld_query_code_addon_package.h", "header differs")):
            with self.subTest(name=name):
                target = self.build / "overworld_query_code_addon" / name
                original = target.read_bytes()
                target.write_text("{}" if name.endswith(".json") else "stale header")
                with self.assertRaisesRegex(RuntimeError, pattern):
                    self.check_gate("follower_selector")
                target.write_bytes(original)

    def test_bootstrap_code_must_match_linked_bytes(self):
        from verify_pokemon_move_history_capture import elf_helper_bindings
        name = "OverworldQueryCodeAddon_ConditionNotify"
        symbols = elf_helper_bindings(
            self.build / "overworld_follower_selector_overlay_linked.o", (name,))
        binary = self.build / "output_overworld_follower_selector_overlay.bin"
        raw = bytearray(binary.read_bytes())
        raw[(symbols[name][0] & ~1) - 0x023C0400] ^= 1
        binary.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "linked/package bootstrap bytes differ"):
            self.check_gate("follower_selector")

    def test_runtime_stale_version_is_rejected(self):
        binary = self.build / "output_overworld_wild_runtime_overlay.bin"
        raw = bytearray(binary.read_bytes()); struct.pack_into("<H", raw, 4, 17)
        binary.write_bytes(raw)
        with self.assertRaisesRegex(RuntimeError, "magic/version/size"):
            self.check_gate("wild_runtime")

    def test_runtime_height_slot_requires_exact_thumb_callback(self):
        binary = self.build / "output_overworld_wild_runtime_overlay.bin"
        original = binary.read_bytes()
        pointer = struct.unpack_from("<I", original, 24)[0]
        for invalid in (0, pointer & ~1, pointer + 2):
            with self.subTest(pointer=invalid):
                binary.write_bytes(original)
                self.change_binary_word("wild_runtime", 24, invalid)
                with self.assertRaisesRegex(RuntimeError, "exactly match its linked"):
                    self.check_gate("wild_runtime")

    def test_runtime_retired_slot_7_remains_zero(self):
        self.change_binary_word("wild_runtime", 36, 0x023BC989)
        with self.assertRaisesRegex(RuntimeError, "exactly match its linked|retired"):
            self.check_gate("wild_runtime")

    def test_runtime_height_callback_body_must_match_linked_bytes(self):
        from verify_pokemon_move_history_capture import elf_helper_bindings
        name = "OverworldWildRuntime_ResolveBaseYAt"
        symbols = elf_helper_bindings(
            self.build / "overworld_wild_runtime_overlay_linked.o", (name,))
        binary = self.build / "output_overworld_wild_runtime_overlay.bin"
        raw = bytearray(binary.read_bytes())
        raw[(symbols[name][0] & ~1) - 0x023BC800] ^= 1
        binary.write_bytes(raw)
        with self.assertRaisesRegex(RuntimeError, "callback body differs"):
            self.check_gate("wild_runtime")


if __name__ == "__main__":
    unittest.main()
