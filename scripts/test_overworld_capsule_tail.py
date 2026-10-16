"""Check the exact linked Wild leaves borrowed by fixed capsules."""

import subprocess
import unittest
from pathlib import Path

from scripts import verify_overworld_field_capsule as field
from scripts import verify_overworld_mount as mount
from scripts.pack_overworld_combat_capsules import section_bytes
from scripts.verify_pokemon_move_history_capture import (
    elf_bytes_at, elf_helper_bindings, layout_symbols,
)


WILD = Path(__file__).resolve().parents[1] / "build/overworld_wild_spawns_overlay_linked.o"


class WildCapsuleTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        names = (field.NOTICE_CLEAR_THROW, field.NOTICE_CLEAR_RELATIONS)
        cls.bindings = elf_helper_bindings(WILD, names)
        cls.notice = section_bytes(WILD, ".overworld_wild_notice_callers",
                                   field.NOTICE_CALLERS, field.NOTICE_CALLERS_SIZE)
        cls.wrapper = elf_bytes_at(WILD, field.NOTICE_CLEAR_THROW_ADDR,
                                   field.NOTICE_CLEAR_THROW_SIZE)
        cls.symbol = layout_symbols(WILD, "arm-none-eabi-objdump")[
            "OverworldWildSpawns_RetainedMaskNamesActiveSpawns"]
        cls.retained = elf_bytes_at(WILD, cls.symbol[0], cls.symbol[1])
        cls.carrier = elf_bytes_at(WILD, 0x01FFF800, 0x180)
        cls.caller = subprocess.check_output([
            "arm-none-eabi-objdump", "-d",
            "--disassemble=OverworldWildSpawns_ApplyTransitionWork", str(WILD)], text=True)

    def notice_contract(self, wrapper=None, target=None, body=None, linked=None):
        field.notice_tail_contract(
            self.bindings[field.NOTICE_CLEAR_THROW] if wrapper is None else wrapper,
            self.bindings[field.NOTICE_CLEAR_RELATIONS] if target is None else target,
            self.notice if body is None else body,
            self.wrapper if linked is None else linked,
        )

    def retained_contract(self, symbol=None, body=None, packaged=None, caller=None):
        mount.retained_mask_capsule_contract(
            self.symbol if symbol is None else symbol,
            self.retained if body is None else body,
            self.carrier if packaged is None else packaged,
            self.caller if caller is None else caller,
        )

    def test_exact_linked_leaves(self):
        self.notice_contract()
        self.retained_contract()

    def test_notice_wrong_owner_extent_body_and_filler(self):
        wrapper = self.bindings[field.NOTICE_CLEAR_THROW]
        target = self.bindings[field.NOTICE_CLEAR_RELATIONS]
        for kwargs in (
            {"wrapper": (wrapper[0] + 2, *wrapper[1:])},
            {"wrapper": (wrapper[0], wrapper[1] - 2, *wrapper[2:])},
            {"target": (target[0] + 2, *target[1:])},
            {"body": self.notice[:340] + bytes([self.notice[340] ^ 1]) + self.notice[341:]},
            {"body": self.notice[:-1] + bytes([self.notice[-1] ^ 1])},
            {"linked": self.wrapper[:-1] + bytes([self.wrapper[-1] ^ 1])},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.notice_contract(**kwargs)

    def test_retained_wrong_owner_body_package_and_call(self):
        for kwargs in (
            {"symbol": (self.symbol[0] + 2, *self.symbol[1:])},
            {"symbol": (self.symbol[0], 30, *self.symbol[2:])},
            {"symbol": (*self.symbol[:2], ".text", self.symbol[3])},
            {"body": bytes([self.retained[0] ^ 1]) + self.retained[1:]},
            {"packaged": self.carrier[:0x130] + bytes([self.carrier[0x130] ^ 1])
                         + self.carrier[0x131:]},
            {"caller": self.caller.replace("bl\t1fff930", "bl\t1fff932")},
            {"caller": self.caller.replace("23d3b7c:", "23d3f04:")},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(SystemExit):
                self.retained_contract(**kwargs)


if __name__ == "__main__":
    unittest.main()
