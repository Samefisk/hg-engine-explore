import binascii
import struct
import tempfile
import unittest
from pathlib import Path
from tools.overworld import player_health_zero_load_fixture as f


def source():
    raw = bytearray(f.SIZE)
    for base, count in ((0, 10), (0x40000, 9)):
        struct.pack_into('<HH', raw, base + f.STOCK_SPAWN, 3, 0xABCD)
        struct.pack_into('<IIIHH', raw, base + f.FOOTER, count, 0xFFA0, 0x20060623, 0, 0)
        seal(raw, base)
    return bytes(raw)


def seal(raw, base=0):
    struct.pack_into('<H', raw, base + f.FOOTER + 14,
                     binascii.crc_hqx(raw[base:base + f.FOOTER], 0xFFFF))


class FixtureTests(unittest.TestCase):
    def test_legacy_and_existing_record_keep_checkpoint_and_unrelated_bytes(self):
        for existing in (False, True):
            raw = bytearray(source())
            if existing:
                raw[f.MARKER:f.MARKER + 3] = b'PH\1'
                struct.pack_into('<BH', raw, f.HP, 67, 7)
                seal(raw)
            before = bytes(raw)
            prepared, manifest = f.prepare_bytes(before)
            self.assertEqual(bytes(raw), before)
            self.assertEqual(manifest['checkpointSpawn'], 7 if existing else 3)
            self.assertEqual(prepared[0x40000:], before[0x40000:])
            self.assertTrue(all(c['offset'] in manifest['allowedOffsets'] for c in manifest['changedBytes']))
            self.assertEqual(f.verify_fixture(before, prepared), manifest)

    def test_bad_checksums_rejected(self):
        raw = bytearray(source())
        raw[12] = raw[0x4000C] = 1
        with self.assertRaisesRegex(ValueError, 'no checksum-valid'):
            f.prepare_bytes(bytes(raw))
        prepared, _ = f.prepare_bytes(source())
        broken = bytearray(prepared); broken[12] = 1
        with self.assertRaisesRegex(ValueError, 'selected copy changed'):
            f.verify_fixture(source(), bytes(broken))

    def test_resealed_wrong_marker_and_unrelated_mutation_rejected(self):
        for offset, message in ((f.MARKER, 'marker'), (123, 'unrelated')):
            prepared, _ = f.prepare_bytes(source())
            broken = bytearray(prepared); broken[offset] ^= 1; seal(broken)
            with self.assertRaisesRegex(ValueError, message):
                f.verify_fixture(source(), bytes(broken))

    def test_missing_marker_and_wrong_hp_are_rejected(self):
        for fault in ('missing-marker', 'wrong-hp'):
            prepared, _ = f.prepare_bytes(source())
            broken = bytearray(prepared)
            if fault == 'missing-marker':
                broken[f.MARKER:f.MARKER + 3] = b'\0' * 3
            else:
                broken[f.HP] = 100
            seal(broken)
            with self.assertRaisesRegex(ValueError, 'marker|HP'):
                f.verify_fixture(source(), bytes(broken))

    def test_source_is_preserved_and_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.sav'; path.write_bytes(source())
            dest = Path(tmp) / 'fixture'
            manifest = f.create_fixture(path, dest)
            self.assertEqual(path.read_bytes(), source())
            self.assertEqual(manifest['fixtureSha256'], f.digest((dest / 'game.sav').read_bytes()))
            with self.assertRaises(FileExistsError):
                f.create_fixture(path, dest)


if __name__ == '__main__':
    unittest.main()
