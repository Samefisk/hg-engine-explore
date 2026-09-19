"""Native crash observer host controls; no generated receipt is game proof."""
from pathlib import Path
import struct
import subprocess
import unittest

from tools.overworld.devtools_mounted_crash_observer import NativeMountedCrashObserver, SYMBOLS, STOCK
from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
from tools.overworld import test_devtools_stomp_observer as stomp_fixture


class MountedCrashObserverTests(unittest.TestCase):
    def fixture(self):
        old,s,actor,regs,put=stomp_fixture.StompObserverTests().fixture()
        path=s.rt.REPO/'build/overworld_mount_overlay_linked.o'
        for symbol in SYMBOLS.values():
            address,size=_elf_function_extent(path,symbol);code=_elf_code(path,address,size)
            s.code_regions.append((address,code));put(address,code)
        arm9=(s.rt.REPO/'base/arm9.bin').read_bytes()
        for address,size in STOCK.values():
            code=arm9[address-0x02000000:address-0x02000000+size]
            s.code_regions.append((address,code));put(address,code)
        s.native_observation.elf_code=_elf_code
        return NativeMountedCrashObserver(s,old.subject,600),s,actor,regs,put

    def test_header_offsets_are_current_arm_layout(self):
        root=Path(__file__).resolve().parents[2]
        code='#include "include/overworld_mount_internal.h"\n'
        for field,offset in [('snapshot.motionMode',102),('motionFrameCount',144),('motionElapsed',146)]:
            code+=f'_Static_assert(__builtin_offsetof(OverworldMountRuntimeState,{field})=={offset},"{field}");\n'
        code+='_Static_assert(sizeof(OverworldMountRuntimeState)==184,"state size");\n'
        run=subprocess.run(['clang','-target','armv5te-none-eabi','-fsyntax-only','-Wno-unknown-attributes',
            '-Wno-gnu-folding-constant','-I',str(root),'-x','c','-'],input=code,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)

    def test_scoped_calls_and_frame_32_before_clear(self):
        r,s,actor,regs,put=self.fixture();r.arm()
        for name in ('update','presentation','finish','sound','soundStart'):
            self.assertIsNone(r._entry(name))
        self.assertEqual(sum(r.counts.values()),0)
        put(r.mount_state+102,b'\x03');put(r.mount_state+144,struct.pack('<HH',32,31))
        value=r._entry('update');put(r.mount_state+146,struct.pack('<H',32))
        returned=r._returned(value,dict(returnValue=0,returned=r.observer._clock()))
        self.assertEqual((returned['before']['elapsed'],returned['after']['elapsed']),(31,32))
        r.completed_boundary();self.assertEqual(r.result()['latestCompleted']['elapsed'],32)
        value=r._entry('finish');put(r.mount_state+102,b'\x00');put(r.mount_state+144,b'\0'*4)
        actor['commitSequence']+=1  # Mutable public state is retained, not treated as owner drift.
        returned=r._returned(value,dict(returnValue=0,returned=r.observer._clock()))
        self.assertEqual((returned['before']['mode'],returned['after']['mode']),(3,0))
        self.assertIn('unk88_z',returned['after']['pose']['player'])
        self.assertEqual(len(bytes.fromhex(returned['after']['mountStateHex'])),184)
        r.close();self.assertEqual(r.close(),r.result());self.assertFalse(r.observer.hooks.callbacks)

    def test_code_identity_and_bounds_fail_closed(self):
        for fault in ('code','identity','bound'):
            r,s,actor,regs,put=self.fixture()
            if fault=='code':
                address,size=_elf_function_extent(s.rt.REPO/'build/overworld_mount_overlay_linked.o',SYMBOLS['start'])
                put(address+size-1,b'\xff')
            elif fault=='identity':actor['species']=1
            else:r.maximum=601
            with self.subTest(fault=fault),self.assertRaises(Exception):r.arm()
            r.close();self.assertFalse(r.observer.hooks.callbacks)

    def test_partial_install_cleanup(self):
        r,s,actor,regs,put=self.fixture();old=r.linked;calls=[]
        def fail(*args,**kwargs):
            old(*args,**kwargs);calls.append(args[0])
            if len(calls)==3:raise RuntimeError('host partial install')
        r.linked=fail
        with self.assertRaisesRegex(RuntimeError,'partial install'):r.arm()
        self.assertTrue(r.closed);self.assertFalse(r.observer.hooks.callbacks)
        self.assertFalse(r.observer.tokens)

    def test_nested_sound_and_pending_close(self):
        r,s,actor,regs,put=self.fixture();r.arm();regs.r0=1536
        outer=r._entry('crashSound');sound=r._entry('sound')
        regs.sp=0x02250000;put(regs.sp,struct.pack('<I',1536))
        start=r._entry('soundStart')
        for value in (start,sound,outer):r._returned(value,dict(returnValue=1,returned=r.observer._clock()))
        self.assertEqual(r.counts['soundStart'],1)
        r._entry('start');r.close()
        self.assertIn('pending',r.failure);self.assertEqual(r.result()['pending'],0)
        self.assertFalse(r.observer.hooks.callbacks)


if __name__=='__main__':unittest.main()
