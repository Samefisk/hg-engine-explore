"""Instruction-level regression for model admission before bubble ownership."""
import unittest

from scripts import verify_overworld_bubble_effect_guard as guard


class BubbleEffectGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code = guard.assemble()

    def test_real_stock_entry_and_hook_seam(self):
        guard.stock_guard()

    def test_assembled_null_full_and_available_pool_abi(self):
        for name, facts, admitted in guard.CASES:
            with self.subTest(name=name):
                guard.verify_case(self.code, facts, admitted)

    def test_stock_full_pool_red_and_removed_branch_controls(self):
        report = guard.verify(self.code)
        self.assertEqual(report["unguardedStockFullPool"], "RED-resource-admission")
        self.assertEqual(report["unguardedStockNullPool"], "RED-resource-admission")
        self.assertEqual(report["copiedFaultsRejected"], 3)

    def test_wrong_context_owner_and_return_are_rejected(self):
        for offset in (40, 44):
            with self.subTest(offset=offset):
                corrupted = bytearray(self.code)
                corrupted[offset] ^= 4
                with self.assertRaises(ValueError):
                    guard.verify_case(corrupted, {}, True)

    def test_oversize_slot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "48-byte slot"):
            guard.verify(self.code + b"\x00\x00")

    def test_wrong_reject_stack_and_register_restore_are_rejected(self):
        for offset in (36, 38):
            with self.subTest(offset=offset):
                corrupted = bytearray(self.code)
                corrupted[offset] ^= 1
                with self.assertRaises(ValueError):
                    guard.verify_case(corrupted, {"pool": 0}, False)


class EmoteSlotOwnerTests(unittest.TestCase):
    def test_actual_owner_private_keys_admission_and_retirement(self):
        from pathlib import Path
        import re
        import shutil
        import subprocess
        import tempfile

        root = Path(__file__).resolve().parents[2]
        compiler = shutil.which("cc")
        self.assertIsNotNone(compiler, "host C compiler is required")
        source = (root / "lib/overworld/overworld_emote_slots.c").read_text()
        header = (root / "include/overworld_emote_slots_internal.h").read_text()
        fixture = (root / "tools/overworld/fixtures/emote_slots_host.c").read_text()
        quiet_source = (root / "src/player_health_overlay/wild_movement_value.c").read_text()
        quiet = re.search(r"OverworldWildBubble_ShowQuiet\(LocalMapObject \*object, u8 bubbleId\)\s*\{[^}]*\}", quiet_source)
        self.assertIsNotNone(quiet, "real quiet bubble leaf was not found")
        fixture = fixture.replace("/* ACTUAL_QUIET_LEAF */", "void " + quiet.group(0))
        variants = {
            "current": (source, None),
            "missing-same-actor": (source.replace(
                "if (owner->slots[i].state && owner->slots[i].object == object) return NULL;",
                "(void)object; if (FALSE) return NULL;"), "plays==1&&stops==2&&owner->count==1"),
            "shared-destination": (source.replace(
                "data->frames.destination=(slot->textureKey & 0xFFFF) << 3;",
                "data->frames.destination=1024;"), "a->data.frames.destination!=b->data.frames.destination"),
            "early-source-free": (source.replace(
                "if (slot->model) sub_02023DA4(slot->model);",
                "if (slot->iconFile) ov01_021F1448(slot->iconFile);\n    if (slot->model) sub_02023DA4(slot->model);"), "source<"),
            "early-key-release": (source.replace(
                "if (GF_GetNumPendingVramTransferTasks()) return;",
                "if (FALSE) return;"), "transfers[i].type!=0"),
        }
        with tempfile.TemporaryDirectory(prefix="emote-slot-owner-") as folder:
            folder = Path(folder)
            for name, (body, reason) in variants.items():
                with self.subTest(name=name):
                    if reason is not None:
                        self.assertNotEqual(body, source, "copied control must change the owner")
                    unit = folder / name
                    unit.mkdir()
                    (unit / "overworld_emote_slots.c").write_text(body)
                    (unit / "overworld_emote_slots_internal.h").write_text(header)
                    (unit / "emote_slots_host.c").write_text(fixture)
                    build = subprocess.run([compiler, "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-I" + str(root / "include"), "-I" + str(unit),
                        str(unit / "emote_slots_host.c"), "-o", str(unit / "owner-check")],
                        text=True, capture_output=True)
                    self.assertEqual(build.returncode, 0, build.stderr)
                    run = subprocess.run([str(unit / "owner-check")], text=True, capture_output=True)
                    if reason is None:
                        self.assertEqual(run.returncode, 0, run.stderr)
                    else:
                        self.assertNotEqual(run.returncode, 0)
                        self.assertIn(reason, run.stderr)
