"""Fixture checks for the versioned, read-only player HP memory receipt."""

import hashlib
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_player_health_observer import (
    EXPECTED_OFFSETS, EXPECTED_OWNER_OFFSETS, EXPECTED_SAVE,
    observe_player_health,
)
from tools.overworld.devtools_runtime import DevtoolsFailure


BASE = 0x01FFA580
FIELD = 0x02010000
SAVE = 0x02100000
RUNTIME = BASE + 0x100


class Fixture:
    def __init__(self, root):
        self.root = root
        self.memory = {}
        self.image = bytearray(0x5A80)
        struct.pack_into("<IHH", self.image, 0, 0x484C5048, 2, 0x34)
        struct.pack_into("<I", self.image, 16, BASE + 0x41)
        self.record = bytearray(0x3C)
        struct.pack_into("<IIHHH", self.record, 0, 12, 2, 300, 0, 0)
        self.record[14] = 67
        self.record[19] = 33
        struct.pack_into("<II", self.record, 20, SAVE, FIELD)
        self.record[56] = 1
        self.write(BASE, self.image)
        self.write(RUNTIME, self.record)
        self.write(FIELD + 0x0C, struct.pack("<II", SAVE, 0))
        header = SAVE + 0x2F014 + 9 * 0x10
        self.write(header, struct.pack("<IIIHH", 9, 0x2E0, 0x100, 0, 0))
        self.write(SAVE + 0x10 + 0x100 + 0x2D5, b"PH\x01")
        self.write(SAVE + 0x10 + 0x100 + 0x2DD, bytes((67, 23, 0)))
        self.write(SAVE + 0x2F014 + 1 * 0x10,
                   struct.pack("<IIIHH", 1, 0x40, 0x400, 0, 0))
        self.write(SAVE + 0x10 + 0x400 + 24,
                   struct.pack("<I", 3000))
        self.write(SAVE + 0x2F014 + 3 * 0x10,
                   struct.pack("<IIIHH", 3, 2448, 0x800, 0, 0))
        self.write(SAVE + 0x10 + 0x800, bytes(2448))
        self.descriptor = {
            "formatVersion": 1,
            "overlay": {"id": 161, "base": BASE, "capacity": 0x5A80,
                        "fileSize": len(self.image),
                        "sha256": hashlib.sha256(self.image).hexdigest()},
            "entry": {"address": BASE, "size": 0x34,
                      "magic": 0x484C5048, "version": 2,
                      "getState": BASE + 0x41,
                      "bytesHex": self.image[:0x34].hex()},
            "runtime": {"address": RUNTIME, "size": 0x3C,
                        "stateSize": 20, "runtimeSize": 0x3C,
                        "stateOffsets": EXPECTED_OFFSETS,
                        "ownerOffsets": EXPECTED_OWNER_OFFSETS,
                        "maxHp": 100, "save": EXPECTED_SAVE},
        }
        self.save_descriptor()
        self.session = SimpleNamespace(
            emu=object(), latest_frame={"frame": 12}, sample_error=None,
            native_bridge_active=False, pending_samples=None,
            overlay_code_regions={161: (BASE, bytes(self.image))},
            rt=SimpleNamespace(REPO=root, EXECUTED_FRAME_COUNT=1000,
                               actor_memory_read=lambda _emu, address, size:
                               self.read(address, size)),
            rom_hash="a" * 64, field_pointer=lambda: FIELD, read=self.read,
        )

    def add_presentation(self):
        self.session.latest_frame.update({"context": {"fieldEpoch": 1,
            "mapGeneration": 1, "mapId": 33}, "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion"})
        capsule = BASE + 0x180
        getter = BASE + 0x80
        code = struct.pack("<4HI", 0x4801, 0x3030, 0x4770, 0x46C0, capsule)
        self.image[0x80:0x8C] = code
        self.write(getter, code)
        self.descriptor["overlay"]["sha256"] = hashlib.sha256(self.image).hexdigest()
        self.session.overlay_code_regions = {161: (BASE, bytes(self.image))}
        self.descriptor["presentation"] = {
            "version": 3, "address": capsule, "size": 0x38,
            "fieldOffset": 0, "receiptOffset": 0x30, "receiptSize": 4,
            "receiptOffsets": {"requestedFill": 0, "drawnFill": 1,
                               "danger": 2, "submittedSprites": 3},
            "boundOffset": 0x34, "textureKeyOffset": 0x35,
            "paletteSlotOffset": 0x36,
            "getter": {"address": getter, "size": 12, "bytesHex": code.hex()},
        }
        self.write(capsule, struct.pack("<I", FIELD))
        palette_source = 0x02210000
        palette = bytes(range(32))
        self.write(capsule + 0x1C, struct.pack("<I", palette_source))
        self.write(palette_source, palette)
        self.write(0x05000200 + 5 * 32, palette)
        self.write(capsule + 0x30, bytes((30, 30, 0, 1)))
        self.write(capsule + 0x34, bytes((1, 134, 5)))
        self.save_descriptor()
        return capsule, getter

    def write(self, address, data):
        self.memory.update((address + index, byte)
                           for index, byte in enumerate(data))

    def read(self, address, size):
        return bytes(self.memory.get(address + index, 0)
                     for index in range(size))

    def save_descriptor(self):
        path = Path(self.root) / "build/player-health.debug.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.descriptor))


class PlayerHealthObserverTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(Path(self.temp.name))

    def assert_rejected(self, code):
        with self.assertRaises(DevtoolsFailure) as caught:
            observe_player_health(self.fixture.session)
        self.assertEqual(caught.exception.code, code)

    def test_checked_receipt_and_clock_delta(self):
        first = observe_player_health(self.fixture.session)
        self.assertEqual((first["hp"], first["checkpointSpawn"],
                          first["lastDamage"], first["dangerBand"]),
                         (67, 23, 33, 1))
        self.assertIsNone(first["pause"]["healthClockPaused"])
        self.assertFalse(first["barDraw"]["available"])
        self.assertEqual(first["economy"], {
            "version": 1, "money": 3000,
            "bagSize": 2448,
            "bagSha256": hashlib.sha256(bytes(2448)).hexdigest()})
        self.fixture.session.latest_frame["frame"] = 13
        second = observe_player_health(self.fixture.session)
        self.assertTrue(second["pause"]["healthClockPaused"])

    def test_missing_or_wrong_descriptor_rejected(self):
        (self.fixture.root / "build/player-health.debug.json").unlink()
        self.assert_rejected("hp-identity")
        self.fixture.descriptor["formatVersion"] = 2
        self.fixture.save_descriptor()
        self.assert_rejected("hp-identity")

    def test_wrong_rom_package_and_live_table_rejected(self):
        self.fixture.session.overlay_code_regions = {}
        self.assert_rejected("hp-identity")
        self.fixture.session.overlay_code_regions = {161: (BASE, b"x" * 0x200)}
        self.assert_rejected("hp-identity")
        self.fixture.session.overlay_code_regions = {161: (BASE, bytes(self.fixture.image))}
        self.fixture.write(BASE, b"BAD!")
        self.assert_rejected("hp-identity")

    def test_wrong_field_save_owner_rejected(self):
        self.fixture.write(FIELD + 0x0C, struct.pack("<I", SAVE + 4))
        self.assert_rejected("hp-owner")

    def test_wrong_save_version_or_hp_rejected(self):
        address = SAVE + 0x10 + 0x100
        self.fixture.write(address + 0x2D5, b"PH\x02")
        self.assert_rejected("hp-save-version")
        self.fixture.write(address + 0x2D5, b"PH\x01")
        self.fixture.write(address + 0x2DD, bytes((0, 23, 0)))
        self.assert_rejected("hp-state")

    def test_damage_is_numeric_and_bounded(self):
        self.assertEqual(observe_player_health(self.fixture.session)["lastDamage"], 33)
        self.fixture.write(RUNTIME + 19, bytes((50,)))
        self.assertEqual(observe_player_health(self.fixture.session)["lastDamage"], 50)
        self.fixture.write(RUNTIME + 19, bytes((51,)))
        self.assert_rejected("hp-state")

    def test_economy_reads_current_save_blocks_and_rejects_bad_owners(self):
        first = observe_player_health(self.fixture.session)["economy"]
        self.fixture.write(SAVE + 0x10 + 0x800 + 12, b"\x01")
        later = observe_player_health(self.fixture.session)["economy"]
        self.assertEqual(later["money"], first["money"])
        self.assertNotEqual(later["bagSha256"], first["bagSha256"])
        self.fixture.write(SAVE + 0x2F014 + 3 * 0x10,
                           struct.pack("<I", 2))
        self.assert_rejected("hp-owner")
        self.fixture.write(SAVE + 0x2F014 + 3 * 0x10,
                           struct.pack("<I", 3))
        self.fixture.write(SAVE + 0x10 + 0x400 + 24,
                           struct.pack("<I", 1000000))
        self.assert_rejected("hp-economy")

    def test_native_submission_and_freshness_are_separate(self):
        self.fixture.add_presentation()
        receipt = observe_player_health(self.fixture.session)
        self.assertTrue(receipt["barDraw"]["completeSubmission"])
        self.assertEqual(receipt["barDraw"]["drawnFill"], 30)
        self.assertIsNone(receipt["barDraw"]["freshHealthFrame"])
        self.assertIsNone(receipt["barDraw"]["hardwareApplied"])
        self.fixture.session.latest_frame["frame"] = 13
        receipt = observe_player_health(self.fixture.session)
        self.assertFalse(receipt["barDraw"]["freshHealthFrame"])
        self.fixture.session.latest_frame["frame"] = 14
        self.fixture.write(RUNTIME, struct.pack("<I", 13))
        receipt = observe_player_health(self.fixture.session)
        self.assertTrue(receipt["barDraw"]["freshHealthFrame"])

    def test_native_partial_submission_is_not_a_complete_draw(self):
        capsule, _ = self.fixture.add_presentation()
        # Reader fixture: native receipt after a bar submission rejects.
        # This is not a live recorder control or S4 acceptance.
        self.fixture.write(capsule + 0x30, bytes((30, 0, 0, 0)))
        receipt = observe_player_health(self.fixture.session)
        self.assertEqual(receipt["barDraw"]["requestedFill"], 30)
        self.assertFalse(receipt["barDraw"]["completeSubmission"])

    def test_palette_source_and_vram_are_checked_separately(self):
        capsule, _ = self.fixture.add_presentation()
        resource = observe_player_health(self.fixture.session)["barResources"]
        self.assertTrue(resource["paletteSourceDmaReadable"])
        self.assertTrue(resource["paletteSourceHasColors"])
        self.assertTrue(resource["paletteVramMatchesSource"])
        self.fixture.write(capsule + 0x1C, struct.pack("<I", capsule + 0x38))
        resource = observe_player_health(self.fixture.session)["barResources"]
        self.assertFalse(resource["paletteSourceDmaReadable"])
        self.fixture.write(capsule + 0x1C, struct.pack("<I", 0x02210000))
        self.fixture.write(0x05000200 + 5 * 32, bytes(32))
        resource = observe_player_health(self.fixture.session)["barResources"]
        self.assertFalse(resource["paletteVramMatchesSource"])

    def test_bar_fill_tracks_hp_from_one_to_one_hundred(self):
        capsule, _ = self.fixture.add_presentation()
        saved_state = SAVE + 0x10 + 0x100 + 0x2DD
        for hp in (1, 33, 34, 67, 99, 100):
            fill = (hp * 44 + 99) // 100
            self.fixture.write(RUNTIME + 14, bytes((hp,)))
            self.fixture.write(saved_state, bytes((hp, 23, 0)))
            self.fixture.write(capsule + 0x30, bytes((fill, fill, 0, 1)))
            self.fixture.write(capsule + 0x34, bytes((1, hp * 2, 5)))
            result = observe_player_health(self.fixture.session)
            self.assertEqual(result["barDraw"]["drawnFill"], fill)
            self.assertTrue(result["barDraw"]["completeSubmission"])
            self.fixture.write(capsule + 0x31, bytes((fill - 1,)))
            self.assert_rejected("hp-presentation-state")

    def test_live_warning_has_a_distinct_uploaded_tile(self):
        capsule, _ = self.fixture.add_presentation()
        self.fixture.write(capsule + 0x30, bytes((30, 30, 1, 1)))
        self.fixture.write(capsule + 0x35, bytes((135,)))
        result = observe_player_health(self.fixture.session)
        self.assertTrue(result["barDraw"]["danger"])
        self.assertEqual(result["barResources"]["textureKey"], 135)
        self.fixture.write(capsule + 0x35, bytes((134,)))
        self.assert_rejected("hp-presentation-state")

    def test_stale_owner_and_false_complete_draw_are_rejected(self):
        capsule, _ = self.fixture.add_presentation()
        self.fixture.write(capsule, struct.pack("<I", FIELD + 4))
        self.assert_rejected("hp-presentation-state")
        self.fixture.write(capsule, struct.pack("<I", FIELD))
        self.fixture.write(capsule + 0x33, bytes((12,)))
        self.assert_rejected("hp-presentation-state")

    def test_presentation_getter_and_layout_are_authenticated(self):
        _, getter = self.fixture.add_presentation()
        self.fixture.write(getter, b"BAD!")
        self.assert_rejected("hp-presentation-identity")
        self.fixture.add_presentation()
        self.fixture.descriptor["presentation"]["receiptOffset"] = 0x34
        self.fixture.save_descriptor()
        self.assert_rejected("hp-presentation-identity")

    def test_unbound_and_suppressed_draws_are_valid(self):
        capsule, _ = self.fixture.add_presentation()
        self.fixture.write(capsule, bytes(0x38))
        receipt = observe_player_health(self.fixture.session)
        self.assertFalse(receipt["barResources"]["bound"])
        self.fixture.add_presentation()
        self.fixture.write(capsule + 0x30, bytes((30, 0, 0, 0)))
        receipt = observe_player_health(self.fixture.session)
        self.assertFalse(receipt["barDraw"]["completeSubmission"])

    def test_recovery_hides_zero_hp_bar(self):
        capsule, _ = self.fixture.add_presentation()
        self.fixture.write(RUNTIME + 14, bytes((0,)))
        self.fixture.write(RUNTIME + 18, bytes((1,)))
        self.fixture.write(SAVE + 0x10 + 0x100 + 0x2DD,
                           bytes((0, 23, 0)))
        self.fixture.write(capsule + 0x30, bytes((0, 0, 0, 0)))
        result = observe_player_health(self.fixture.session)
        self.assertFalse(result["barDraw"]["completeSubmission"])
        self.fixture.write(capsule + 0x32, bytes((1,)))
        self.assert_rejected("hp-presentation-state")

    def test_context_change_resets_freshness_and_missing_context_fails(self):
        self.fixture.add_presentation()
        observe_player_health(self.fixture.session)
        self.fixture.session.latest_frame["frame"] = 13
        self.fixture.session.latest_frame["context"]["mapGeneration"] = 2
        self.fixture.write(RUNTIME, struct.pack("<I", 13))
        receipt = observe_player_health(self.fixture.session)
        self.assertIsNone(receipt["barDraw"]["freshHealthFrame"])
        self.fixture.session.latest_frame.pop("context")
        self.assert_rejected("hp-presentation-identity")


if __name__ == "__main__":
    unittest.main()
