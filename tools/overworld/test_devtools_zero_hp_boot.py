"""Zero-save boot recognition uses real readers; no emulator or save edits."""
import binascii
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.overworld.test_devtools_engine import fresh_engine, BootTests


def save_bytes(hp=0, count=2, checkpoint=3):
    data = bytearray(0x80000)
    for base, seq in ((0, count), (0x40000, count - 1)):
        data[base + 0x28E9:base + 0x28EC] = b"PH\x01"
        struct.pack_into("<BH", data, base + 0x28F1, hp, checkpoint)
        crc = binascii.crc_hqx(data[base:base + 0xFF90], 0xFFFF)
        struct.pack_into("<IIIHH", data, base + 0xFF90, seq, 0xFFA0, 0x20060623, 0, crc)
    return bytes(data)


def reseal(data, base=0):
    struct.pack_into("<H", data, base + 0xFF9E,
                     binascii.crc_hqx(data[base:base + 0xFF90], 0xFFFF))


class ZeroBootTests(unittest.TestCase):
    def fixture(self):
        engine = fresh_engine()
        engine.G_FIELD_SYS_PTR = 0x02000080
        field, save, root, stock, child = 0x02100000, 0x02200000, 0x02110000, 0x02110100, 0x02110200
        code = {"PlayerHealthRecovery_BlackoutTask": (0x01FFA600, 4, b"ROOT"),
                "PlayerHealthRecovery_StockBlackoutTask": (0x01FFA610, 4, b"WRAP")}
        data = {"sPlayerHealth": (0x01FFB000, 60, None),
                "sBlackoutFieldSystem": (0x01FFB040, 4, None),
                "sBlackoutFailed": (0x01FFB044, 1, None)}
        memory = {}
        def write(address, value):
            memory.update({address + i: byte for i, byte in enumerate(value)})
        def word(address, value): write(address, struct.pack("<I", value))
        for address, _, value in code.values(): write(address, value)
        word(engine.G_FIELD_SYS_PTR, field)
        word(field + 12, save)
        word(field + 16, child)
        word(data['sBlackoutFieldSystem'][0], field)
        health = bytearray(60); health[18] = health[56] = 1
        struct.pack_into('<I', health, 20, save)
        write(data['sPlayerHealth'][0], health)
        write(save + 0x2F014 + 9 * 16, struct.pack('<III', 9, 0x2E4, 0x2614))
        misc = save + 0x10 + 0x2614
        write(misc + 0x2D5, b'PH\x01'); write(misc + 0x2DD, b'\0\3\0')
        for task, prev, callback, state in ((root, 0, 0x01FFA601, 2),
                (stock, root, 0x01FFA611, 6), (child, stock, 0x0203FF45, 0)):
            write(task, struct.pack('<8I', prev, callback, state, 0, 0, 0, field, 0))
        class Memory:
            def __getitem__(self, key):
                return bytes(memory.get(i, 0) for i in range(key.start, key.stop))
        engine._zero_hp_boot_layout = lambda: (code, data)
        emu = SimpleNamespace(memory=SimpleNamespace(unsigned=Memory()))
        return engine, emu, write, word, field, save, root, stock, child

    def test_valid_zero_preserves_pending_boundary_without_input(self):
        engine, emu, *_ = self.fixture()
        result = engine._zero_hp_boot_boundary(emu, save_bytes())
        self.assertEqual(result['kind'], 'player-health-pending-blackout')
        self.assertEqual(result['hp'], 0)
        self.assertFalse(result['actorClockReady'])
        self.assertFalse(result['acceptedProof'])
        self.assertFalse(result['recoveryInputSent'])
        self.assertEqual(len(result['tasks']), 3)

    def test_wrong_or_missing_native_state_cannot_open_paused_session(self):
        for fault in ('code', 'owner', 'hp', 'pending', 'save-owner', 'marker',
                      'checkpoint', 'task-owner', 'task-root', 'task-phase', 'cycle', 'failed'):
            with self.subTest(fault=fault):
                engine, emu, write, word, field, save, root, stock, child = self.fixture()
                changes = {'code': (0x01FFA600,b'BAD!'), 'owner': (0x01FFB040,b'\0'*4),
                    'hp':(0x01FFB00E,b'\x64'), 'pending':(0x01FFB012,b'\0'),
                    'save-owner':(0x01FFB014,b'\0'*4),
                    'marker':(save+0x10+0x2614+0x2D5,b'XX\1'),
                    'checkpoint':(save+0x10+0x2614+0x2DE,b'\4\0'),
                    'task-owner':(child+24,b'\0'*4), 'task-root':(root+4,b'\1\0\0\2'),
                    'task-phase':(root+8,b'\1\0\0\0'),
                    'cycle':(root,struct.pack('<I',child)), 'failed':(0x01FFB044,b'\1')}
                write(*changes[fault])
                self.assertIsNone(engine._zero_hp_boot_boundary(emu, save_bytes()))

    def test_only_selected_checksum_valid_zero_record_qualifies(self):
        engine = fresh_engine()
        for hp in (1, 67, 100, 255):
            self.assertIsNone(engine._zero_hp_save_record(save_bytes(hp)))
        for fault in ('marker', 'checkpoint', 'checksum'):
            data=bytearray(save_bytes())
            for base in (0,0x40000):
                data[base + {'marker':0x28E9,'checkpoint':0x28F2,'checksum':0x100}[fault]] ^= 0x80
                if fault != 'checksum': reseal(data,base)
            self.assertIsNone(engine._zero_hp_save_record(bytes(data)))
        data=bytearray(save_bytes()); data[0x28F1]=67; reseal(data)
        self.assertIsNone(engine._zero_hp_save_record(bytes(data)))
        self.assertIsNone(engine._zero_hp_save_record(b''))

    def test_boot_returns_checked_recovery_without_extra_taps_or_new_timeout(self):
        for ready in (True, False):
            engine, emu, calls=BootTests().fixture(field_ready=ready,clock_moves=False)
            receipt={'kind':'player-health-pending-blackout','acceptedProof':False}
            engine._zero_hp_boot_boundary=lambda emu,raw:receipt
            with tempfile.TemporaryDirectory() as tmp:
                save=Path(tmp)/'game.sav'; save.write_bytes(b'save')
                self.assertEqual(engine.boot(emu,save,False),receipt)
            self.assertEqual(engine.BOOT_RECOVERY_RECEIPT,receipt)
            self.assertEqual(len([c for c in calls if c[0]=='tap']),1)
            self.assertLess(sum(c[1] for c in calls if c[0]=='cycle'),1200)

    def test_current_package_and_elf_recovery_reader_agree(self):
        engine=fresh_engine()
        code,data=engine._zero_hp_boot_layout()
        self.assertEqual(set(code), {'PlayerHealthRecovery_BlackoutTask',
                                    'PlayerHealthRecovery_StockBlackoutTask'})
        self.assertEqual(data['sPlayerHealth'][1],60)

    def test_boot_recovery_receipt_is_retained_in_session_snapshot(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        session = object.__new__(DevtoolsSession)
        session.sample_error = None
        session.latest_frame = {'fieldAvailable': False, 'frame': 1}
        session.native_observation = None
        session.boot_recovery = {'kind': 'player-health-pending-blackout',
                                 'acceptedProof': False}
        self.assertEqual(session.snapshot(diagnostic_details=False)['bootRecovery'],
                         session.boot_recovery)


if __name__ == '__main__':
    unittest.main()
