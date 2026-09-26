"""Real callback reader with host memory; not live gameplay/calibration proof."""
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_stomp_observer import NativeStompObserver, STOCK
from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld import test_devtools_corner_observer as corner_fixture


class StompObserverTests(unittest.TestCase):
    def fixture(self):
        old,s,a,regs,put=corner_fixture.CornerTests().fixture()
        s.directory=Path('/tmp/stomp-host-fixture');s.rom=s.directory/'test.nds';s.native_bridge_active=False
        path=s.rt.REPO/'build/overworld_mount_overlay_linked.o'
        for symbol in ('OverworldMount_ApplyWalkPolicyOutput','OverworldMount_PlayerStepBridge'):
            address,size=_elf_function_extent(path,symbol)
            code=_elf_code(path,address,size);s.code_regions.append((address,code));put(address,code)
        s.native_observation.elf_code=_elf_code
        base=struct.unpack_from('<I',(s.rt.REPO/'base/overarm9.bin').read_bytes(),36)[0]
        overlay=(s.rt.REPO/'base/overlay/overlay_0001.bin').read_bytes()
        arm9=(s.rt.REPO/'base/arm9.bin').read_bytes()
        for address,size,is_overlay in STOCK.values():
            blob,origin=(overlay,base) if is_overlay else (arm9,0x02000000)
            data=blob[address-origin:address-origin+size];s.code_regions.append((address,data));put(address,data)
        put(0x023BC744+78,b'\x02')
        reader=NativeStompObserver(s,old.subject,20)
        return reader,s,a,regs,put

    def invoke(self,r,name):
        address=r.code[name][0] if isinstance(name,str) else name
        for callback in tuple(r.observer.hooks.callbacks.get(address,())):callback()

    def start(self,r,regs,put,effect):
        raw=bytearray(28);struct.pack_into('<HHI',raw,0,1,28,r.mount_state+8)
        raw[8]=r.subject['handle']['slot'];raw[21]=effect
        put(0x02250000,raw)
        regs.r0,regs.r1,regs.r2=r.owner['avatarPointer'],r.owner['mountPointer'],0x02250000
        regs.lr=0x02010001;self.invoke(r,'policy')

    def test_disabled_negative_and_missing_positive_coverage(self):
        r,s,a,regs,put=self.fixture()
        self.assertEqual(r.observer.hooks.callbacks,{})
        r.arm();self.invoke(r,'sound');self.assertEqual(r.counts['sound'],0)
        self.start(r,regs,put,0);self.invoke(r,0x02010000)
        self.assertEqual(r.latest['effect'],0);self.assertTrue(r.latest['normalReturn'])
        r.close();self.assertEqual(r.observer.hooks.callbacks,{})

    def test_private_guard_and_actual_step_bridge(self):
        for field,value in (('native_bridge_active',True),('rom',Path('/tmp/not-private.nds'))):
            r,s,a,regs,put=self.fixture();setattr(s,field,value)
            with self.assertRaisesRegex(NativeObservationError,'private session'):r.arm()
            self.assertEqual(r.observer.hooks.callbacks,{})
        r,s,a,regs,put=self.fixture();r.arm()
        regs.r0=r.owner['worldContext']['fieldPointer'];regs.lr=0x02010601
        self.invoke(r,'playerStep');regs.r0=0;self.invoke(r,0x02010600)
        self.assertEqual(r.player_step_count,1)
        r.close();self.assertIsNone(r.failure);self.assertEqual(r.observer.hooks.callbacks,{})
        r,s,a,regs,put=self.fixture();r.arm();self.start(r,regs,put,1)
        with self.assertRaisesRegex(NativeObservationError,'coverage'):self.invoke(r,0x02010000)
        r.close();self.assertEqual(r.observer.hooks.callbacks,{})

    def test_positive_actual_nested_sink_receipts(self):
        r,s,a,regs,put=self.fixture();r.arm();self.start(r,regs,put,1)
        regs.sp-=16;regs.r0=r.owner['mountPointer'];regs.lr=0x02010101;self.invoke(r,'dust')
        regs.sp-=16;regs.r1=STOCK['descriptor'][0];regs.r2=0x02250100;regs.lr=0x02010201
        put(regs.r2,bytes(12));put(regs.sp,struct.pack('<I',0x02250200))
        put(0x02250200,struct.pack('<4I',1,2,3,r.owner['mountPointer']));self.invoke(r,'allocate')
        regs.sp-=16;regs.r0=0x02260000;regs.r1=0x02260100;regs.lr=0x02010301;self.invoke(r,'init')
        put(0x02260100,bytes(28)+struct.pack('<II',r.owner['mountPointer'],0x02261000))
        regs.r0=1;self.invoke(r,0x02010300)
        regs.sp+=16;regs.r0=0x02260000;self.invoke(r,0x02010200)
        regs.sp+=16;self.invoke(r,0x02010100)
        regs.sp+=16;regs.sp-=16;regs.r0=1606;regs.lr=0x02010401;self.invoke(r,'sound')
        regs.sp-=16;put(regs.sp,struct.pack('<I',1606));regs.lr=0x02010501;self.invoke(r,'soundStart')
        regs.r0=1;self.invoke(r,0x02010500)
        regs.sp+=16;self.invoke(r,0x02010400)
        regs.sp+=16;self.invoke(r,0x02010000)
        self.assertEqual(r.counts,dict.fromkeys(('policy','dust','allocate','init','sound','soundStart'),1))
        self.assertEqual(r.latest['feedback']['soundStart'][0]['soundId'],1606)
        self.assertEqual(r.latest['feedback']['allocate'][0]['returnValue'],0x02260000)
        r.close();self.assertIsNone(r.failure);self.assertEqual(r.observer.hooks.callbacks,{})

    def test_wrong_abi_owner_threshold_code_and_pending_cleanup(self):
        for fault in ('abi','object','threshold','code','pending'):
            with self.subTest(fault=fault):
                r,s,a,regs,put=self.fixture();r.arm()
                if fault=='threshold':
                    put(r.mount_state+78,b'\xff')
                    with self.assertRaisesRegex(NativeObservationError,'threshold'):r._read_profile(r._current())
                elif fault=='code':
                    put(r.code['policy'][0],b'\xff')
                    with self.assertRaises(NativeObservationError):self.start(r,regs,put,0)
                elif fault=='object':
                    self.start(r,regs,put,1);regs.r0=0
                    with self.assertRaisesRegex(NativeObservationError,'object'):self.invoke(r,'dust')
                elif fault=='abi':
                    with self.assertRaisesRegex(NativeObservationError,'ABI'):self.start(r,regs,put,255)
                else:self.start(r,regs,put,1)
                r.close();self.assertIsNotNone(r.failure);self.assertEqual(r.observer.hooks.callbacks,{})

    def test_independent_vanilla_sink_and_header_anchors(self):
        root=Path(__file__).resolve().parents[2]
        reference=root/'.codex-reference/pokeheartgold/asm'
        dust=(reference/'overlay_01_021FF6B0.s').read_text()
        self.assertIn('ov01_021FF74C: ; 0x021FF74C',dust)
        self.assertIn('str r0, [r4, #0x20]',dust)
        self.assertIn('ov01_022091EC: ; 0x022091EC',dust)
        sound=(reference/'unk_02005D10.s').read_text()
        self.assertIn('PlaySE: ; 0x0200604C',sound)
        self.assertIn('sub_020060BC: ; 0x020060BC',sound)
        self.assertRegex((root/'include/constants/sndseq.h').read_text(),r'SEQ_SE_DP_SUTYA2\s+1606\b')


if __name__=='__main__':unittest.main()
