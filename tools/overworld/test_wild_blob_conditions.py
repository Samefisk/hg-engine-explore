"""Packed condition validation for the current Ram contract."""

import struct
import unittest

from tools.overworld import test_wild_blob_acceleration as acceleration
from scripts import validate_overworld_wild_blobs as validator


class WildBlobConditionTests(unittest.TestCase):
    def setUp(self):
        acceleration.WildBlobAccelerationTests.setUp(self)
        self.source.write_text(self.source.read_text().replace(
            "OWBD_CONDITION_ENTRY_COUNT 0", "OWBD_CONDITION_ENTRY_COUNT 1"))
        self.entry = len(self.blob)
        self.blob.extend(bytes(48))
        end = len(self.blob)
        struct.pack_into("<I", self.blob, 8, end)
        struct.pack_into("<IHH", self.blob, 52, self.entry, 1, 48)
        for offset in (60, 68, 76):
            struct.pack_into("<I", self.blob, offset, end)
        struct.pack_into("<BBB", self.blob, self.override_base + 17, 1, 0, 1)
        struct.pack_into("<9H", self.blob, self.entry + 16,
                         0, 0, 0, 100, 0, 0, 0, 0, 1)
        struct.pack_into("<13B", self.blob, self.entry + 34,
                         0, 2, 255, 0, 2, 1, 0, 0, 6, 32, 100, 2, 0)

    validate = acceleration.WildBlobAccelerationTests.validate

    def test_current_ram_until_crash_and_forward_line_pass(self):
        self.validate(self.blob)

    def test_both_supported_cones_with_or_without_adjacent_awareness(self):
        for options in (1, 2, 5, 6):
            with self.subTest(options=options):
                blob = self.blob.copy()
                blob[self.entry + 45] = options
                self.validate(blob)

    def test_unknown_cones_remain_invalid(self):
        for options in (0, 3, 4, 7):
            with self.subTest(options=options):
                blob = self.blob.copy()
                blob[self.entry + 45] = options
                with self.assertRaisesRegex(ValueError, "invalid options"):
                    self.validate(blob)

    def test_crash_mode_cannot_have_a_duration(self):
        blob = self.blob.copy()
        struct.pack_into("<H", blob, self.entry + 20, 96)
        with self.assertRaisesRegex(ValueError, "until-crash.*duration"):
            self.validate(blob)

    def test_old_modes_keep_their_timer_rules(self):
        blob = self.blob.copy()
        blob[self.entry + 38] = 1
        with self.assertRaisesRegex(ValueError, "timed.*no duration"):
            self.validate(blob)
        struct.pack_into("<H", blob, self.entry + 20, 96)
        self.validate(blob)
        blob[self.entry + 38] = 0
        with self.assertRaisesRegex(ValueError, "while-true.*timers"):
            self.validate(blob)
        struct.pack_into("<HH", blob, self.entry + 20, 0, 0)
        self.validate(blob)

    def test_unknown_activation_mode_remains_invalid(self):
        blob = self.blob.copy()
        blob[self.entry + 38] = 3
        with self.assertRaisesRegex(ValueError, "invalid activation mode"):
            self.validate(blob)

    def current_blob(self):
        self.source.write_text(self.source.read_text().replace(
            "OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 85",
            "OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 87"))
        blob = self.blob.copy()
        struct.pack_into("<H", blob, 4, 87)
        # Current native tail: physical rest mask followed by one options row.
        blob.extend(struct.pack("<I", 1))
        self.options = len(blob)
        blob.extend(bytes(12))
        struct.pack_into("<I", blob, 8, len(blob))
        return blob

    def test_current_damage_recipients_keep_knockback_bits_separate(self):
        blob = self.current_blob()
        bits = (1 << 20) | (1 << 21) | (1 << 22)
        struct.pack_into("<I", blob, self.override_base + 24, bits)
        for recipients in range(8):
            for knockback_type in (0, 1, 2):
                for distance in (1, 7):
                    with self.subTest(recipients=recipients, type=knockback_type,
                                      distance=distance):
                        packed = (recipients << 5) | (distance << 2) | knockback_type
                        blob[self.class_base + 79] = packed
                        blob[self.value_base + 79] = packed
                        self.validate(blob)
        for base in (self.class_base, self.value_base):
            for packed in ((7 << 5) | 3 | (1 << 2), (7 << 5) | 2):
                with self.subTest(base=base, invalid=packed):
                    invalid = blob.copy()
                    invalid[base + 79] = packed
                    with self.assertRaisesRegex(ValueError, "collision attack|knockback"):
                        self.validate(invalid)

    def test_recipient_mask_is_exact_replacement_only_and_unknown_bits_reject(self):
        blob = self.current_blob()
        struct.pack_into("<I", blob, self.override_base + 24, 1 << 22)
        self.validate(blob)
        for offset in (116, 128, 140):
            with self.subTest(operator_word=offset):
                invalid = blob.copy()
                struct.pack_into("<I", invalid, self.override_base + offset, 1 << 22)
                with self.assertRaisesRegex(ValueError, "non-numeric"):
                    self.validate(invalid)
        for bit in (23, 31):
            with self.subTest(unknown_bit=bit):
                invalid = blob.copy()
                struct.pack_into("<I", invalid, self.override_base + 24, (1 << 22) | (1 << bit))
                with self.assertRaisesRegex(ValueError, "mask2 has undefined bits"):
                    self.validate(invalid)

    def test_current_actor_facts_can_select_cargo_with_valid_options(self):
        blob = self.current_blob()
        struct.pack_into("<4H", blob, self.entry + 16, 16, 10, 0, 0)
        struct.pack_into("<13B", blob, self.entry + 34,
                         0, 2, 255, 4, 0, 2, 1, 0, 0, 0, 100, 0, 0)
        struct.pack_into("<4BH6B", blob, self.options,
                         3, 2, 0, 0, 0, 1, 1, 1, 16, 1, 32)
        self.validate(blob)
        for offset, value, error in (
            (16, 64, "invalid actor facts"),
            (18, 16, "invalid actor facts"),
            (39, 1, "actor-facts.*invalid fields"),
            (40, 0, "actor-facts.*invalid fields"),
            (40, 4, "invalid target roles"),
            (41, 1, "actor-facts.*invalid fields"),
        ):
            with self.subTest(offset=offset, value=value):
                invalid = blob.copy()
                invalid[self.entry + offset] = value
                with self.assertRaisesRegex(ValueError, error):
                    self.validate(invalid)

    def test_every_notice_kind_rejects_unknown_or_overlapping_actor_facts(self):
        blob = self.current_blob()
        blob[self.entry + 39] = 2
        blob[self.entry + 40] = 1
        for kind in (1, 3):
            with self.subTest(kind=kind):
                blob[self.entry + 37] = kind
                struct.pack_into("<HH", blob, self.entry + 16, 1, 0)
                self.validate(blob)
                for required, forbidden in ((64, 0), (0, 64), (1, 1)):
                    invalid = blob.copy()
                    struct.pack_into("<HH", invalid, self.entry + 16, required, forbidden)
                    with self.assertRaisesRegex(ValueError, "invalid actor facts"):
                        self.validate(invalid)

    def test_current_tail_rejects_bad_size_role_binding_and_pickup_options(self):
        blob = self.current_blob()
        self.validate(blob)
        for delta in (-1, 1):
            invalid = blob[:delta] if delta < 0 else blob + bytes(delta)
            struct.pack_into("<I", invalid, 8, len(invalid))
            with self.assertRaisesRegex(ValueError, "condition options tail size"):
                self.validate(invalid)
        for offset, value in ((0, 8), (1, 3), (2, 2), (3, 2), (6, 3),
                              (7, 2), (8, 9), (9, 65), (10, 2)):
            with self.subTest(option=offset):
                invalid = blob.copy()
                invalid[self.options + offset] = value
                with self.assertRaisesRegex(ValueError, "invalid binding/pickup options"):
                    self.validate(invalid)
        for offset in (3, 7):
            invalid = blob.copy()
            invalid[self.options + offset] = 1
            with self.assertRaisesRegex(ValueError, "invalid binding/pickup options"):
                self.validate(invalid)
        invalid = blob.copy()
        invalid[self.options + 1] = 2  # Cargo capture needs an Actor target.
        with self.assertRaisesRegex(ValueError, "invalid binding/pickup options"):
            self.validate(invalid)
        for lifetime, duration in ((0, 1), (1, 0)):
            invalid = blob.copy()
            struct.pack_into("<4BH", invalid, self.options, 0, 1, lifetime, 0, duration)
            with self.assertRaisesRegex(ValueError, "invalid binding/pickup options"):
                self.validate(invalid)
        struct.pack_into("<4BH", blob, self.options, 0, 1, 1, 0, 1)
        self.validate(blob)

    def test_current_constants_match_declared_native_fields(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        header = (root / "include/overworld_wild_behavior_data.h").read_text()
        self.assertIn("#define OW_WILD_BEHAVIOR_OVERRIDE2_DAMAGE_RECIPIENTS (1u << 22)", header)
        self.assertIn("#define OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_MASK 0x1C", header)
        self.assertEqual(validator.OWBD_MASK2_ALLOWED, (1 << 23) - 1)
        self.assertEqual(validator.OWBD_KNOCKBACK_DISTANCE_MASK, 0x1C)


if __name__ == "__main__":
    unittest.main()
