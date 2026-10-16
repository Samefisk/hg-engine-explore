"""Build-boundary checks for packed Walk acceleration settings."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from scripts import validate_overworld_wild_blobs as validator


class WildBlobAccelerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wild-blob-acceleration-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "counts.h"
        counts = {
            "OVERWORLD_WILD_BEHAVIOR_DATA_VERSION": 85,
            "OWBD_CLASS_PROFILE_COUNT": 1,
            "OWBD_CLASS_RULE_COUNT": 0,
            "OWBD_SPECIES_CLASS_RULE_COUNT": 0,
            "OWBD_OVERRIDE_PROFILE_COUNT": 1,
            "OWBD_OVERRIDE_MEMBER_COUNT": 0,
            "OWBD_CONDITION_ENTRY_COUNT": 0,
            "OWBD_SURFACE_MODEL_COUNT": 0,
            "OWBD_SURFACE_INSTANCE_COUNT": 0,
            "OWBD_SURFACE_TEMPLATE_COUNT": 0,
        }
        self.source.write_text("".join(
            f"#define {key} {value}\n" for key, value in counts.items()
        ))
        self.target = root / "behavior.bin"
        self.class_base = 84
        self.override_base = self.class_base + 80
        end = self.override_base + 228
        self.blob = bytearray(end)
        struct.pack_into(
            "<IHHI IHH IHH IHH IHH IHH IHH IHH IHH IHH",
            self.blob, 0,
            validator.OWBD_MAGIC, 85, 84, end,
            self.class_base, 1, 80,
            self.override_base, 0, 16,
            self.override_base, 0, 4,
            self.override_base, 1, 228,
            end, 0, 2, end, 0, 48, end, 0, 6, end, 0, 8, end, 0, 2,
        )
        # Synthetic valid profile; no ROM, save, or generated data is needed.
        for offset, value in {
            7: 8, 15: 1, 50: 120, 51: 4, 57: 1, 60: 8, 61: 1,
            71: 34, 76: 1, 79: 4,
        }.items():
            self.blob[self.class_base + offset] = value
        self.value_base = self.override_base + 32
        self.interval_bit = validator.OWBD_TILES_TO_ACCELERATE_FIELD_BIT
        self.mode_bit = validator.OWBD_WALK_ACCELERATION_STEP_FIELD_BIT
        struct.pack_into("<I", self.blob, self.override_base + 28,
                         self.interval_bit | self.mode_bit)
        self.blob[self.value_base + 50] = 120
        self.blob[self.value_base + 71] = 34

    def validate(self, blob: bytearray) -> None:
        self.target.write_bytes(blob)
        validator.validate_owbd(self.target, self.source)

    def test_linear_ramp_accepts_full_frame_range(self) -> None:
        for interval in (1, 32, 120, 255):
            with self.subTest(interval=interval):
                blob = self.blob.copy()
                blob[self.class_base + 50] = interval
                blob[self.value_base + 50] = interval
                self.validate(blob)

    def test_duration_override_can_inherit_linear_mode(self) -> None:
        blob = self.blob.copy()
        struct.pack_into("<I", blob, self.override_base + 28, self.interval_bit)
        blob[self.value_base + 71] = 0
        self.validate(blob)

    def test_existing_acceleration_modes_still_pass(self) -> None:
        for mode in (0, 1, 32, 33):
            with self.subTest(mode=mode):
                blob = self.blob.copy()
                for base in (self.class_base, self.value_base):
                    blob[base + 50] = 3
                    blob[base + 71] = mode
                self.validate(blob)

    def test_zero_duration_and_unknown_mode_still_fail(self) -> None:
        for base in (self.class_base, self.value_base):
            for offset, value, error in (
                (50, 0, "acceleration interval"),
                (71, 35, "acceleration"),
            ):
                with self.subTest(base=base, offset=offset):
                    blob = self.blob.copy()
                    blob[base + offset] = value
                    with self.assertRaisesRegex(ValueError, error):
                        self.validate(blob)

    def test_duration_bounds_accept_frames_and_keep_positive_minimum(self) -> None:
        for mask_offset in (132, 144):
            for interval in (120, 255):
                with self.subTest(mask_offset=mask_offset, interval=interval):
                    blob = self.blob.copy()
                    struct.pack_into("<I", blob, self.override_base + mask_offset,
                                     self.interval_bit)
                    blob[self.value_base + 50] = interval
                    self.validate(blob)
            blob[self.value_base + 50] = 0
            with self.assertRaisesRegex(ValueError, "positive field bound"):
                self.validate(blob)

    def test_linear_mode_requires_exact_replacement(self) -> None:
        blob = self.blob.copy()
        struct.pack_into("<I", blob, self.override_base + 120, self.mode_bit)
        with self.assertRaisesRegex(ValueError, "Linear speed.*exact replacement"):
            self.validate(blob)

    def test_v91_in_place_hops_keep_old_slices_and_reject_invalid_values(self) -> None:
        self.source.write_text(self.source.read_text().replace("VERSION 85", "VERSION 91"))
        blob = self.blob.copy()
        struct.pack_into("<H", blob, 4, 91)
        blob.extend(bytes(4 + validator.OWBD_CONDITION_OPTIONS_SIZE))
        struct.pack_into("<I", blob, 8, len(blob))
        blob[self.class_base + 42] = 4  # Valid existing Cargo interval.
        new_bits = ((1 << 28) | (1 << 29))
        struct.pack_into("<I", blob, self.override_base + 24, new_bits)
        struct.pack_into("<I", blob, self.override_base + 28,
                         self.interval_bit | self.mode_bit | (1 << 11))
        for count in range(3):
            for chance in (0, 1, 50, 100):
                valid = blob.copy()
                for base in (self.class_base, self.value_base):
                    valid[base + 57] = 8 | (count << 4)
                    valid[base + 43] = 1 | (chance << 1)
                self.validate(valid)
        # The shared count byte must keep a relative/divide/bound operand
        # separate from the independently active extra-Hop slice.
        for operand, operator_offsets in ((14, (120,)), (8, (132, 144)),
                                           (8, (132,)), (8, (144,))):
            valid = blob.copy()
            valid[self.value_base + 57] = 0x10 | operand
            for offset in operator_offsets:
                struct.pack_into("<I", valid, self.override_base + offset, 1 << 11)
            self.validate(valid)
        for base in (self.class_base, self.value_base):
            for offset, value, error in (
                (57, 0x31, "extra in-place Hops"),
                (43, 203, "extra in-place Hop chance"),
                (57, 0x10, "reposition-jump count"),
            ):
                with self.subTest(base=base, offset=offset):
                    invalid = blob.copy()
                    invalid[self.value_base + 57] = 1
                    invalid[base + offset] = value
                    with self.assertRaisesRegex(ValueError, error):
                        self.validate(invalid)
        for bit in (30, 31):
            invalid = blob.copy()
            struct.pack_into("<I", invalid, self.override_base + 24, 1 << bit)
            with self.assertRaisesRegex(ValueError, "mask2 has undefined bits"):
                self.validate(invalid)
        # A v90 blob must still reject the new override bits.
        self.source.write_text(self.source.read_text().replace("VERSION 91", "VERSION 90"))
        struct.pack_into("<H", blob, 4, 90)
        with self.assertRaisesRegex(ValueError, "mask2 has undefined bits"):
            self.validate(blob)

    def test_v92_hop_effects_keep_count_and_pickup_slices(self) -> None:
        self.source.write_text(self.source.read_text().replace("VERSION 85", "VERSION 92"))
        blob = self.blob.copy()
        struct.pack_into("<H", blob, 4, 92)
        blob.extend(bytes(4 + validator.OWBD_CONDITION_OPTIONS_SIZE))
        struct.pack_into("<I", blob, 8, len(blob))
        blob[self.class_base + 42] = 4
        struct.pack_into("<I", blob, self.override_base + 24,
                         (1 << 16) | (1 << 28) | (1 << 29) | (1 << 30) | (1 << 31))
        struct.pack_into("<I", blob, self.override_base + 28,
                         self.interval_bit | self.mode_bit | (1 << 11))
        for count in range(3):
            for heart in range(4):
                for cry in range(4):
                    for pickup in range(2):
                        valid = blob.copy()
                        for base in (self.class_base, self.value_base):
                            valid[base + 57] = 8 | (count << 4) | (heart << 6)
                            valid[base + 43] = 101
                            valid[base + 75] = pickup | (cry << 6)
                        self.validate(valid)
        for base in (self.class_base, self.value_base, self.override_base + 148):
            for reserved in (1 << bit for bit in range(1, 6)):
                invalid = blob.copy()
                invalid[self.value_base + 57] = 1
                invalid[base + 75] = reserved
                with self.assertRaisesRegex(ValueError, "throw settings|on-reach option bits"):
                    self.validate(invalid)
        # Effects are replace-only, including the mask2 top-bit boundary.
        for bit in (30, 31):
            invalid = blob.copy()
            invalid[self.value_base + 57] = 1
            struct.pack_into("<I", invalid, self.override_base + 116, 1 << bit)
            with self.assertRaisesRegex(ValueError, "non-numeric relative field"):
                self.validate(invalid)
        self.source.write_text(self.source.read_text().replace("VERSION 92", "VERSION 91"))
        struct.pack_into("<H", blob, 4, 91)
        with self.assertRaisesRegex(ValueError, "mask2 has undefined bits"):
            self.validate(blob)


if __name__ == "__main__":
    unittest.main()
