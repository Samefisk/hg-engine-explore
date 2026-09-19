"""Real shared hook dispatch with host memory; no game acceptance claim."""
from pathlib import Path
import struct
import subprocess
import unittest

from tools.overworld.devtools_mounted_hop_start_observer import NativeMountedHopStartObserver, SYMBOL, STATE_ADDRESS
from tools.overworld.devtools_runtime import _elf_code, _elf_function_extent
from tools.overworld import test_devtools_mount_pacing_observer as pacing_fixture


class HopStartTests(unittest.TestCase):
    def fixture(self):
        old,s,a,e,regs,put,calls,poses = pacing_fixture.MountPacingTests().fixture()
        s.directory = Path('/tmp/hop-start-host-fixture')
        s.rom = s.directory/'test.nds'
        s.native_bridge_active = False
        path = s.rt.REPO/'build/overworld_mount_overlay_linked.o'
        address,size = _elf_function_extent(path,SYMBOL)
        code = _elf_code(path,address,size)
        s.rt.MOUNT_SYMBOLS.update({SYMBOL:address, 'sOverworldMountState':STATE_ADDRESS})
        s.code_regions.append((address,code));put(address,code)
        s.native_observation.elf_code = _elf_code
        s.packaged_code = lambda start,n: next((data[start-base:start-base+n] for base,data in s.code_regions
            if base <= start and start+n <= base+len(data)),b'')
        for pose in poses.values():pose['face_y']=123
        put(STATE_ADDRESS,bytes(184))
        r=NativeMountedHopStartObserver(s,old.subject,100)
        return r,s,a,regs,put,poses

    def accepted(self,a,put):
        a.update(motionKind='HOP',motionPhase='MOVING',motionElapsed=0,motionDuration=12,
            reservationId=51,origin=dict(x=1,y=2),target=dict(x=4,y=2))
        raw=bytearray(184);raw[102]=1;raw[141]=7
        struct.pack_into('<H',raw,126,51);struct.pack_into('<HH',raw,144,12,0)
        struct.pack_into('<4h',raw,152,1,2,4,2);put(STATE_ADDRESS,raw)

    def invoke(self,r,address):
        for callback in tuple(r.observer.hooks.callbacks.get(address,())):callback()

    def test_actual_dispatch_retains_pose_and_clock_not_invented_zero(self):
        r,s,a,regs,put,poses=self.fixture();r.arm()
        self.invoke(r,r.code[0]);self.accepted(a,put)
        poses[r.owner['mountPointer']]['face_y']=456
        regs.r0=1;self.invoke(r,regs.lr&~1)
        receipt=r.observer.pending[-1]
        self.assertEqual(receipt['observation'],'mounted-hop-start')
        self.assertEqual(receipt['start'],dict(elapsed=0,duration=12,origin=dict(x=1,y=2),target=dict(x=4,y=2),
            motionIdentity=51,baseFaceY=123,faceY=456,arcHeightQ4=7))
        self.assertEqual(receipt['subject'],r.subject)
        self.assertGreater(receipt['sequence'],0)
        self.assertEqual((receipt['entryNativeCycle'],receipt['returnNativeCycle']),(30,30))
        self.assertEqual(receipt['current']['publicSubject']['reservationId'],51)
        r.close();self.assertFalse(r.observer.hooks.callbacks);self.assertIsNone(r.failure)

    def test_rejected_start_does_not_supply_a_receipt(self):
        r,s,a,regs,put,poses=self.fixture();r.arm()
        self.invoke(r,r.code[0]);regs.r0=0;self.invoke(r,regs.lr&~1)
        self.assertEqual(r.counts['starts'],0);self.assertIsNone(r.latest)
        self.assertFalse(r.data);r.close()

    def test_changed_identity_elapsed_or_code_fails(self):
        for fault in ('generation','elapsed','identity','duration','code','frame'):
            with self.subTest(fault=fault):
                r,s,a,regs,put,poses=self.fixture();r.arm();before=r._before_start();self.accepted(a,put)
                if fault=='generation':a['authorityGeneration']+=1
                elif fault=='elapsed':a['motionElapsed']=1
                elif fault=='identity':put(STATE_ADDRESS+126,b'\x34\0')
                elif fault=='duration':a['motionDuration']=13
                elif fault=='code':put(r.code[0]+len(r.code[1])-1,b'\xff')
                else:s.completed_frames+=1
                with self.assertRaises(Exception):r._after_start(before,dict(returnValue=1))
                self.assertIsNotNone(r.failure);self.assertIsNone(r.latest);r.close()
                self.assertFalse(r.observer.hooks.callbacks)

    def test_arm_package_mismatch_and_partial_install_cleanup(self):
        r,s,a,regs,put,poses=self.fixture();s.packaged_code=lambda address,size:b''
        with self.assertRaises(Exception):r.arm()
        self.assertFalse(r.observer.hooks.callbacks)
        r,s,a,regs,put,poses=self.fixture();linked=r.linked
        def fail(*args,**kwargs):linked(*args,**kwargs);raise RuntimeError('partial install')
        r.linked=fail
        with self.assertRaisesRegex(RuntimeError,'partial install'):r.arm()
        self.assertFalse(r.observer.hooks.callbacks)

    def test_offsets_match_arm_header(self):
        root=Path(__file__).resolve().parents[2]
        source='#include "include/overworld_mount_internal.h"\n'
        for name,offset in [('snapshot.motionMode',102),('motionIdentity',126),('motionArcHeightQ4',141),
                            ('motionFrameCount',144),('motionElapsed',146),('motionStartX',152),('motionTargetX',156)]:
            source+=f'_Static_assert(__builtin_offsetof(OverworldMountRuntimeState,{name})=={offset},"{name}");\n'
        source+='_Static_assert(sizeof(OverworldMountRuntimeState)==184,"size");\n'
        run=subprocess.run(['clang','-target','armv5te-none-eabi','-fsyntax-only','-Wno-unknown-attributes',
            '-Wno-gnu-folding-constant','-I',str(root),'-x','c','-'],input=source,text=True,capture_output=True,timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)


if __name__=='__main__':unittest.main()
