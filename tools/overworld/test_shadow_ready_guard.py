"""Instruction-level circle-shadow failed allocation and later retry checks."""
import unittest
from scripts import verify_overworld_shadow_ready_guard as guard


class ShadowReadyGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stock=guard.read_blocks(guard.ROOT/'rom.nds')
        cls.code=guard.candidate_blocks(cls.stock)

    def test_authentic_stock_callback_and_product_halfword_seam(self):
        guard.authenticate(self.stock)
        guard.source_guard()
        with self.assertRaisesRegex(ValueError,'ready instruction'):
            guard.authenticate(self.stock,guard.SHIFT)

    def test_null_retries_then_ready_draw_and_single_free(self):
        for pointer in guard.MAIN_MODEL_POINTERS:
            with self.subTest(pointer=pointer):
                self.assertEqual(guard.verify_lifecycle(self.code,pointer),
                                 dict(allocationAttempts=3,failedAttempts=2,ready=1,modelOperations=5,frees=1,nullModelFreeCalls=0))

    def test_old_mov_wrong_shift_and_skipped_ready_store_reject(self):
        report=guard.verify(self.code)
        self.assertEqual(report['copiedFaultsRejected'],
                         ['stock-mov1','wrong-shift24','skip-ready-store'])
        with self.assertRaisesRegex(ValueError,'failed circle shadow admission'):
            guard.verify_lifecycle(self.stock)

    def test_changed_native_call_store_and_extents_reject(self):
        for name,offset in (('initialize',0x3C),('initialize',0x40),('draw',0x64),('destroy',0xA)):
            with self.subTest(name=name,offset=offset):
                bad=dict(self.code);body=bytearray(bad[name]);body[offset]^=4;bad[name]=bytes(body)
                with self.assertRaisesRegex(ValueError,'full body|stores'):
                    guard.authenticate(bad,guard.SHIFT)
        bad=dict(self.code);bad['update']+=b'\x00\x00'
        with self.assertRaisesRegex(ValueError,'extent'):
            guard.authenticate(bad,guard.SHIFT)

    def test_unknown_pointer_and_unowned_draw_reject(self):
        for pointer in (0x01FFFFFC,0x02400000,guard.MODEL+1):
            with self.subTest(pointer=pointer),self.assertRaisesRegex(ValueError,'allocation range'):
                guard.verify_lifecycle(self.code,pointer)
        callbacks=guard.ShadowCallbacks(self.code,[guard.MODEL]);callbacks.run('initialize')
        callbacks.owned.clear()
        with self.assertRaisesRegex(ValueError,'NULL/unowned'):
            callbacks.run('draw')


if __name__=='__main__':unittest.main()
