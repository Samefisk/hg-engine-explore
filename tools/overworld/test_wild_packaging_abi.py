"""Exercise the real Make callback gate without running Make's packing work."""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import os
import re
import struct
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]


class OverlayLoadOriginTests(unittest.TestCase):
    """Copied private code must not become the main overlay's load address."""

    @classmethod
    def setUpClass(cls):
        tree = ast.parse((REPO / "scripts/make.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "ReadOverlayLoadAddress")
        namespace = {"re": re}
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     "scripts/make.py", "exec"), namespace)
        cls.read_origin = staticmethod(namespace[function.name])

    def test_current_wild_uses_main_rom_after_private_slam_region(self):
        text = (REPO / "src/overworld_wild_spawns_overlay/linker.ld").read_text()
        first_origin = next(line for line in text.splitlines() if "ORIGIN" in line)
        self.assertIn("slamJump", first_origin)
        self.assertIn("0x023B8800", first_origin)
        self.assertEqual(self.read_origin(text), 0x023CCFD8)

    def test_non_rom_regions_and_order_do_not_change_main_origin(self):
        rom = "    rom : ORIGIN = 0x023CCFD8, LENGTH = 0xB028\n"
        others = ["    slamJump : ORIGIN = 0x023B8800, LENGTH = 0xA20\n",
                  "    combat : ORIGIN = 0x01FFF580, LENGTH = 0x180\n",
                  "    ewram : ORIGIN = 0x023CCFD8, LENGTH = 0xB028\n"]
        for position in range(len(others) + 1):
            rows = others[:position] + [rom] + others[position:]
            with self.subTest(position=position):
                self.assertEqual(self.read_origin("MEMORY {\n" + "".join(rows) + "}\n"),
                                 0x023CCFD8)
        self.assertEqual(self.read_origin(
            "romCopy : ORIGIN = 0x023B8800, LENGTH = 0xA20\n" + rom), 0x023CCFD8)

    def test_missing_duplicate_and_nonliteral_rom_origins_are_rejected(self):
        rom = "rom : ORIGIN = 0x023CCFD8, LENGTH = 0xB028\n"
        for text in ("slamJump : ORIGIN = 0x023B8800, LENGTH = 0xA20\n",
                     rom + rom,
                     rom + "rom : ORIGIN = 0x023B8800, LENGTH = 0xA20\n",
                     rom + "rom : ORIGIN = BASE, LENGTH = 0xB028\n",
                     "rom : ORIGIN = 37408728, LENGTH = 0xB028\n",
                     "rom : ORIGIN = BASE, LENGTH = 0xB028\n",
                     "rom : ORIGIN = 0x023CCFD8 + 4, LENGTH = 0xB028\n",
                     "rom : ORIGIN = 0x023CCFD8 LENGTH = 0xB028\n",
                     "romCopy : ORIGIN = 0x023CCFD8, LENGTH = 0xB028\n"):
            with self.subTest(text=text), self.assertRaises((ValueError, RuntimeError)):
                self.read_origin(text)

    def test_old_private_home_y9_row_still_fails_current_package_contract(self):
        from scripts import verify_overworld_learnset_cache as gate
        native = REPO / "build/overworld_wild_spawns_overlay_linked.o"
        output = REPO / "build/output_overworld_wild_spawns_overlay.bin"
        current_symbols = gate.symbols(native)
        bss = gate.section_size(native, ".bss")
        payload = output.read_bytes()
        self.assertEqual(current_symbols["__text_start"][0], 0x023CCFD8)
        self.assertEqual((len(payload), bss), (0xB000, 0x24))
        with tempfile.TemporaryDirectory(prefix="ow-overlay-origin-") as directory:
            repo = Path(directory)
            (repo / "build").mkdir()
            (repo / "base/overlay").mkdir(parents=True)
            (repo / "build" / output.name).write_bytes(payload)
            (repo / "build" / native.name).write_bytes(native.read_bytes())
            (repo / "base/overlay/overlay_0149.bin").write_bytes(payload)
            row = (149, 0x023CCFD8, len(payload), bss, 0, 0, 149, 0)
            table = bytearray(150 * 0x20)
            struct.pack_into("<8I", table, 149 * 0x20, *row)
            (repo / "base/overarm9.bin").write_bytes(table)
            with patch.object(gate, "OVERLAY_PACKAGING", {149: gate.OVERLAY_PACKAGING[149]}), \
                    patch.object(gate, "symbols", return_value=current_symbols), \
                    patch.object(gate, "section_size", return_value=bss), \
                    contextlib.redirect_stdout(io.StringIO()):
                gate.verify_packaged_overlays(repo)
                struct.pack_into("<I", table, 149 * 0x20 + 4, 0x023B8800)
                (repo / "base/overarm9.bin").write_bytes(table)
                with self.assertRaisesRegex(SystemExit, "overlay 149 y9 row mismatch"):
                    gate.verify_packaged_overlays(repo)


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


class BorrowedMountHopCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts import verify_overworld_query_code_addon as gate
        cls.gate = gate
        native = REPO / "build/overworld_mount_overlay_linked.o"
        if not native.is_file():
            raise unittest.SkipTest("current native Mount ELF is required")
        names = tuple(gate.MOUNT_CALLBACK_TABLES) + tuple(
            name for _size, _start, targets in gate.MOUNT_CALLBACK_TABLES.values()
            for name in targets)
        cls.symbols = gate.elf_helper_bindings(native, names)
        cls.tables = {name: gate.elf_bytes_at(native, cls.symbols[name][0], size)
                      for name, (size, _start, _targets) in gate.MOUNT_CALLBACK_TABLES.items()}

    def test_current_words_and_every_wrong_target_or_mode(self):
        self.gate.mount_callback_contract(self.tables, self.symbols)
        for table, (_size, start, targets) in self.gate.MOUNT_CALLBACK_TABLES.items():
            for index, _target in enumerate(targets):
                offset = start + index * 4
                for change in (1, 2):
                    with self.subTest(offset=offset, change=change):
                        tables = dict(self.tables)
                        raw = bytearray(tables[table])
                        value = struct.unpack_from("<I", raw, offset)[0]
                        struct.pack_into("<I", raw, offset, value ^ change)
                        tables[table] = raw
                        with self.assertRaises(ValueError):
                            self.gate.mount_callback_contract(tables, self.symbols)
        for name in self.gate.MOUNT_ABSOLUTE_CALLBACKS:
            for bad in (None, (self.symbols[name][0] & ~1, 0, "FUNC", "ABS"),
                        (self.symbols[name][0], 0, "NOTYPE", "ABS")):
                with self.subTest(name=name, metadata=bad):
                    symbols = dict(self.symbols)
                    symbols[name] = bad
                    with self.assertRaises(ValueError):
                        self.gate.mount_callback_contract(self.tables, symbols)


class BorrowedWildCallbackTests(unittest.TestCase):
    """Use the real native tables; every bad indirect call must fail the gate."""

    @classmethod
    def setUpClass(cls):
        from scripts import verify_overworld_query_code_addon as gate
        cls.gate = gate
        cls.wild = Path(os.environ.get("OW_WILD_CALLBACK_ELF", str(
            REPO / "build/overworld_wild_spawns_overlay_linked.o")))
        if not cls.wild.is_file():
            raise unittest.SkipTest("current native Wild ELF is required")
        names = tuple(gate.WILD_CALLBACK_TABLES) + tuple(name for _size, _start, targets
                    in gate.WILD_CALLBACK_TABLES.values() for name in targets if isinstance(name, str))
        cls.symbols = gate.elf_helper_bindings(cls.wild, names)
        cls.tables = {name: gate.elf_bytes_at(cls.wild, cls.symbols[name][0], size)
                      for name, (size, _start, _targets) in gate.WILD_CALLBACK_TABLES.items()}

    def test_current_native_callback_words_and_modes(self):
        self.gate.wild_callback_contract(self.tables, self.symbols)

    def test_every_callable_word_and_absolute_metadata_is_required(self):
        for table, (_size, start, targets) in self.gate.WILD_CALLBACK_TABLES.items():
            for index, target in enumerate(targets):
                if target in (0x020FD4CC, 0x020FD4BC):
                    continue  # These are data table addresses, not function words.
                offset = start + index * 4
                for change in (1, 2):
                    with self.subTest(table=table, offset=offset, change=change):
                        tables = dict(self.tables)
                        raw = bytearray(tables[table])
                        value = struct.unpack_from("<I", raw, offset)[0]
                        struct.pack_into("<I", raw, offset, value ^ change)
                        tables[table] = raw
                        with self.assertRaisesRegex(ValueError, "target/mode differs|not its exact Thumb function"):
                            self.gate.wild_callback_contract(tables, self.symbols)
        for name in self.gate.WILD_ABSOLUTE_CALLBACKS:
            wrong_kind = "FUNC" if name in self.gate.WILD_NOTYPE_CALLBACKS else "NOTYPE"
            for bad in (None, (self.symbols[name][0] & ~1, 0, "FUNC", "ABS"),
                        (self.symbols[name][0], 0, wrong_kind, "ABS")):
                with self.subTest(name=name, metadata=bad):
                    symbols = dict(self.symbols)
                    symbols[name] = bad
                    with self.assertRaisesRegex(ValueError, "Thumb function metadata"):
                        self.gate.wild_callback_contract(self.tables, symbols)

    def test_packaged_table_and_real_callback_owner_bytes_are_required(self):
        from scripts.verify_overworld_field_capsule import rom_overlays
        overlays = rom_overlays((REPO / "test.nds").read_bytes())
        # A scratch ELF can test the named eight-word fix before a ROM build.
        # This copy is a package fixture, never live or acceptance evidence.
        for name, raw in self.tables.items():
            overlay_id = 1 if name == "sOverworldWildHopOps" else 149
            row, image = overlays[overlay_id]
            image = bytearray(image)
            offset = self.symbols[name][0] - row[1]
            image[offset:offset + len(raw)] = raw
            overlays[overlay_id] = row, bytes(image)
        actual_read = self.gate.elf_helper_bindings
        actual_bytes = self.gate.elf_bytes_at
        native = REPO / "build/overworld_wild_spawns_overlay_linked.o"
        with patch.object(self.gate, "elf_helper_bindings", side_effect=lambda p, n:
                          actual_read(self.wild if p == native else p, n)), \
                patch.object(self.gate, "elf_bytes_at", side_effect=lambda p, a, z:
                             actual_bytes(self.wild if p == native else p, a, z)):
            self.gate.verify_wild_callbacks(REPO / "build", overlays)
            for overlay, address, error in ((149, self.symbols["sOverworldWildRouteOps"][0] + 8,
                                            "callback linked/package bytes differ"),
                                           (153, 0x023C03D0, "implementation linked/package bytes differ")):
                with self.subTest(overlay=overlay):
                    altered = dict(overlays)
                    owner, body = altered[overlay]
                    body = bytearray(body)
                    body[address - owner[1]] ^= 1
                    altered[overlay] = owner, bytes(body)
                    with self.assertRaisesRegex(ValueError, error):
                        self.gate.verify_wild_callbacks(REPO / "build", altered)

    def test_stock_direction_predicates_keep_exact_thumb_targets(self):
        rom = (REPO / "test.nds").read_bytes()
        offset, _entry, base, size = struct.unpack_from("<4I", rom, 0x20)
        arm9 = rom[offset:offset + size]
        self.gate.verify_direction_callbacks(arm9, base)
        for address in self.gate.DIRECTION_BLOCKS:
            for index in range(4):
                with self.subTest(address=address, index=index):
                    altered = bytearray(arm9)
                    altered[address - base + index * 4] ^= 1
                    with self.assertRaisesRegex(ValueError, "direction predicate table Thumb targets"):
                        self.gate.verify_direction_callbacks(altered, base)


if __name__ == "__main__":
    unittest.main()


class CurrentQueryAcquireTests(unittest.TestCase):
    """Check the current compiled private boundary and exact packaged bytes."""

    @classmethod
    def setUpClass(cls):
        from scripts import verify_overworld_query_code_addon as gate
        cls.gate = gate
        cls.selector = Path(os.environ.get("OW_QUERY_SELECTOR_ELF", str(
            REPO / "build/overworld_follower_selector_overlay_linked.o")))
        cls.wild = Path(os.environ.get("OW_WILD_CALLBACK_ELF", str(
            REPO / "build/overworld_wild_spawns_overlay_linked.o")))
        cls.selector_bytes = gate.elf_bytes_at(cls.selector, gate.PUBLIC_ENTRY,
                                              0x023C3000-gate.PUBLIC_ENTRY)
        caller = gate.elf_helper_bindings(cls.wild, ("OverworldWildSpawns_QueryAddon",))["OverworldWildSpawns_QueryAddon"]
        cls.caller_bytes = gate.elf_bytes_at(cls.wild, caller[0]&~1, caller[1])

    def check(self, selector_bytes=None, caller_bytes=None):
        return self.gate.verify_current_acquire(self.selector, self.wild,
            self.selector_bytes if selector_bytes is None else selector_bytes,
            self.caller_bytes if caller_bytes is None else caller_bytes)

    def test_exact_current_compiled_private_boundary(self):
        self.check()

    def test_wrong_packaged_helper_and_caller_bytes_fail(self):
        selector=bytearray(self.selector_bytes)
        selector[0x023C2A80-self.gate.PUBLIC_ENTRY]^=1
        with self.assertRaisesRegex(ValueError,"linked/package"):
            self.check(selector_bytes=selector)
        caller=bytearray(self.caller_bytes);caller[0]^=1
        with self.assertRaisesRegex(ValueError,"linked/package"):
            self.check(caller_bytes=caller)

    def test_missing_or_even_private_entry_metadata_fails(self):
        actual=self.gate.elf_helper_bindings
        for bad in (None,(0x023C2A80,96,"FUNC",".text")):
            def changed(path,names):
                symbols=actual(path,names)
                if path==self.selector:
                    symbols["OverworldQueryCodeAddonField_AcquireCurrent"]=bad
                return symbols
            with self.subTest(metadata=bad), patch.object(self.gate,"elf_helper_bindings",side_effect=changed):
                with self.assertRaisesRegex(ValueError,"Thumb function"):
                    self.check()


class NativeConditionDispatchTests(unittest.TestCase):
    """Use current linked leaves and reject copied native layout faults."""

    @classmethod
    def setUpClass(cls):
        from scripts import verify_overworld_query_code_addon as gate
        cls.gate = gate
        image = REPO / "build/overworld_query_code_addon/image.elf"
        names = tuple(gate.CONDITION_NATIVE_OWNERS) + (
            "__query_cargo_code_end", "__query_return_code_end")
        cls.symbols = gate.elf_helper_bindings(image, names)
        cls.bodies = {address: gate.elf_bytes_at(image, address, size)
                      for address, size in gate.CONDITION_NATIVE_OWNERS.values()}
        cls.bodies[0x02080098] = gate.elf_bytes_at(image, 0x02080098, 4)

    def check(self, bodies=None, symbols=None):
        bodies = self.bodies if bodies is None else bodies
        self.gate.condition_native_contract(
            self.symbols if symbols is None else symbols,
            lambda address, size: bodies[address][:size])

    def test_current_native_dispatcher_access_and_moving_leaves(self):
        self.check()

    def test_exact_tail_owner_modes_sizes_and_boundaries_are_required(self):
        for name in self.gate.CONDITION_NATIVE_OWNERS:
            current = self.symbols[name]
            for bad in (None, (current[0] & ~1, *current[1:]),
                        (current[0], current[1] + 2, *current[2:]),
                        (*current[:3], "ABS")):
                with self.subTest(name=name, metadata=bad):
                    symbols = dict(self.symbols)
                    symbols[name] = bad
                    with self.assertRaisesRegex(ValueError, "hosted Thumb"):
                        self.check(symbols=symbols)
        for name in ("__query_cargo_code_end", "__query_return_code_end"):
            symbols = dict(self.symbols)
            symbols[name] = (symbols[name][0] + 4, *symbols[name][1:])
            with self.subTest(boundary=name), self.assertRaisesRegex(ValueError, "code boundaries"):
                self.check(symbols=symbols)

    def test_callback_packet_operation_and_all_direct_targets_are_required(self):
        for address, offsets, error in (
                (0x02080098, (0, 1), "callback152"),
                (0x020899A0, (0x12, 0x24, 0x2A, 0x2E, 0x46, 0x48, 0x4A,
                              0x1B4, 0x1B6, 0x1B8, 0x1BC, 0x1C0), "packet/operation"),
                (0x020899A0, (0x1FC, 0x242, 0x280, 0x2B2, 0x3B8, 0x402),
                 "direct target"),
                (0x02089784, (0, 0x24, 0x118, 0x124, 0x14C, 0x1C6,
                              0x1EA, 0x20A, 0x218), "Hop presentation")):
            for offset in offsets:
                with self.subTest(address=address, offset=offset):
                    bodies = dict(self.bodies)
                    altered = bytearray(bodies[address])
                    altered[offset] ^= 1
                    bodies[address] = altered
                    with self.assertRaisesRegex(ValueError, error):
                        self.check(bodies=bodies)

    def test_original_subject_and_visibility_import_guards_remain_required(self):
        for address, offsets, error in (
                (0x020895D0, (0x90, 0x194), "Subject population"),
                (0x020894F0, (0xD4, 0xD8, 0xDC), "coordinate/solid trace")):
            for offset in offsets:
                with self.subTest(address=address, offset=offset):
                    bodies = dict(self.bodies)
                    altered = bytearray(bodies[address])
                    altered[offset] ^= 1
                    bodies[address] = altered
                    with self.assertRaisesRegex(ValueError, error):
                        self.check(bodies=bodies)
