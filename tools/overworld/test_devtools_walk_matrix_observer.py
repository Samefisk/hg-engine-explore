"""Host native-boundary controls; no generated sample is accepted ROM proof."""
from copy import deepcopy
from pathlib import Path
import json
import struct
import subprocess
import unittest

from tools.overworld.devtools_field_cleanup import symbol
from tools.overworld.devtools_walk_matrix_observer import (NativeWalkMatrixObserver, decode_motion,
    MAX_CALLBACKS, SLOT_STRIDE, SNAPSHOT_BYTES, MOTION_BYTES, POLICY_BYTES, SAMPLE_BYTES,
    ACTORS_OFFSET, ACTOR_CAPACITY)
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld import test_devtools_mount_pacing_observer as native_fixture


def motion(duration=1, elapsed=0, phase=2):
    raw=bytearray(MOTION_BYTES)
    struct.pack_into('<HBBHH',raw,0,1,1,3,2,17)
    struct.pack_into('<4h2i',raw,8,1,2,2,2,0,0)
    struct.pack_into('<HH',raw,24,duration,42)
    raw[28:38]=bytes((3,1,0,0,0,0,0,2,1,0))
    struct.pack_into('<4H4B',raw,40,elapsed,0,0,0,phase,0,0,0)
    return bytes(raw)


class WalkMatrixTests(unittest.TestCase):
    def fixture(self):
        old,s,actor,engine,regs,put,calls,poses=native_fixture.MountPacingTests().fixture()
        p=s.rt.REPO/'build/overworld_actor_system_overlay_linked.o'
        if not p.exists():self.skipTest('current linked Actor object required for native code authentication')
        image=p.read_bytes()
        address,size,code=symbol(image,'OverworldMotion_Tick',2)
        s.code_regions.append((address,code));put(address,code)
        s.packaged_code=lambda at,n: code[at-address:at-address+n] if address<=at<=address+len(code)-n else b''
        s.rt.ACTOR_DESCRIPTOR=json.loads((s.rt.REPO/'build/overworld-system.debug.json').read_text())
        state=s.rt.ACTOR_DESCRIPTOR['state']['address']
        original_unsigned=s.rt.unsigned
        values={state+8:9,state+12:2,state+46:3}
        s.rt.unsigned=lambda emu,at,size=4: values[at] if at in values else original_unsigned(emu,at,size)
        s.native_bridge_active=False
        s.directory=Path('/tmp/walk-matrix-private-fixture');s.rom=s.directory/'session.nds'
        s._selector_observation=lambda:dict(heldKeys=16,newKeys=16,rawHeld=16,rawNew=16,simulatedKeys=0)
        actor.update(motionKind='WALK',motionPhase='MOVING',motionElapsed=0,motionDuration=1,reservationId=42)
        reader=NativeWalkMatrixObserver(s,old.subject,4096)
        reader.arm()
        put(reader.motion_pointer,motion())
        sample_pointer=0x027E2F00
        put(sample_pointer,bytes(SAMPLE_BYTES))
        regs.r0,regs.r1,regs.r2=reader.motion_pointer,2,sample_pointer
        regs.lr=0x02010001
        return reader,s,actor,regs,put

    def invoke(self,r,address):
        for callback in tuple(r.observer.hooks.callbacks.get(address,())):callback()

    def start(self,r,regs):
        regs.r0,regs.r1,regs.r2=r.motion_pointer,2,0x027E2F00
        regs.lr=0x02010001
        self.invoke(r,r.code[0])

    def finish_tick(self,r,regs,put,duration=1,elapsed=1,phase=3,flags=15):
        put(r.motion_pointer,motion(duration,elapsed,phase))
        sample=struct.pack('<6i5H2B',2*65536+32768,0,2*65536+32768,0,0,0,
                           elapsed,duration,1,1,flags,3,1)
        put(0x027E2F00,sample)
        regs.r0=flags
        self.invoke(r,0x02010000)

    def test_one_frame_retains_actual_zero_entry_and_one_return(self):
        r,s,actor,regs,put=self.fixture()
        self.start(r,regs);self.finish_tick(r,regs,put)
        event=r.observer.pending[-1]
        self.assertEqual(event['observation'],'walk-matrix-tick')
        self.assertEqual(event['before']['elapsed'],0)
        self.assertEqual(event['after']['elapsed'],1)
        self.assertEqual(event['sample']['elapsed'],1)
        self.assertEqual(event['beforeCurrent']['publicSubject']['motionElapsed'],0)
        self.assertEqual(event['afterCurrent']['publicSubject']['motionElapsed'],0)
        self.assertTrue(event['movingWalk'])
        self.assertEqual(event['qualification'],'moving-walk')
        self.assertEqual(event['returnFlags'],15)
        self.assertEqual(event['before']['rawHex'],motion().hex())
        self.assertEqual(len(bytes.fromhex(event['sample']['rawHex'])),SAMPLE_BYTES)
        result=r.result()
        self.assertEqual(result['counts'],dict(ticks=1,movingWalk=1))
        self.assertEqual(result['returned'],1)
        self.assertNotIn('calls',result)
        self.assertNotIn('before',result)
        self.assertLess(len(json.dumps(result)),5000)
        self.assertFalse(result['acceptedProof'])
        self.assertEqual(result['guestMemoryWrites'],0)
        self.assertIsNone(r.close()['failure'])
        self.assertEqual(r.observer.hooks.callbacks,{})

    def test_every_native_call_is_retained_including_identical_clocks_and_idle(self):
        r,s,actor,regs,put=self.fixture()
        for _ in range(2):
            put(r.motion_pointer,motion());self.start(r,regs);self.finish_tick(r,regs,put)
        put(r.motion_pointer,motion(1,1,0));self.start(r,regs)
        put(0x027E2F00,bytes(SAMPLE_BYTES));regs.r0=0;self.invoke(r,0x02010000)
        events=list(r.observer.pending)
        self.assertEqual(len(events),3)
        self.assertEqual([e['movingWalk'] for e in events],[True,True,False])
        self.assertEqual(events[0]['entryNativeCycle'],events[1]['entryNativeCycle'])
        self.assertEqual(r.result()['counts'],dict(ticks=3,movingWalk=2))
        r.close()

    def test_retired_return_closures_are_not_retained_by_reader(self):
        import weakref
        import gc
        r,s,actor,regs,put=self.fixture()
        entries=list(r.entries)
        retired=[]
        for _ in range(20):
            put(r.motion_pointer,motion())
            self.start(r,regs)
            self.assertEqual(len(r.returns),1)
            self.assertEqual(r.returns,r.observer.return_tokens)
            self.assertEqual(len(r.data),1)
            retired.append(weakref.ref(r.returns[0][1]))
            self.finish_tick(r,regs,put)
            self.assertEqual(r.returns,[])
            self.assertEqual(r.data,[])
            self.assertEqual(r.observer.return_tokens,[])
            self.assertEqual(r.observer.contexts,[])
            self.assertEqual(r.entries,entries)
        gc.collect()
        self.assertTrue(all(reference() is None for reference in retired))
        self.assertEqual(r.result()['returned'],20)
        self.assertEqual(len(r.observer.pending),20)
        r.close()

    def test_continuation_one_is_not_rewritten_to_zero(self):
        r,s,actor,regs,put=self.fixture()
        put(r.motion_pointer,motion(4,1));self.start(r,regs)
        self.finish_tick(r,regs,put,4,2,2,1)
        self.assertEqual(r.observer.pending[-1]['before']['elapsed'],1)
        self.assertEqual(r.observer.pending[-1]['after']['elapsed'],2)
        r.close()

    def test_other_real_slots_are_scoped_out_unknown_pointer_fails(self):
        r,s,actor,regs,put=self.fixture()
        regs.r0=r.motion_pointer-SLOT_STRIDE
        self.invoke(r,r.code[0])
        self.assertEqual(r.result()['ignoredOtherSlots'],1)
        self.assertEqual(r.result()['counts']['ticks'],0)
        regs.r0=r.motion_pointer+4
        with self.assertRaisesRegex(NativeObservationError,'not an actor slot'):self.invoke(r,r.code[0])
        r.close()

    def test_epoch_identity_motion_state_sample_and_code_faults(self):
        for fault in ('epoch','plan-epoch','identity','state','sample-pointer','reservation','code','frame-bound','call-bound'):
            r,s,actor,regs,put=self.fixture()
            if fault=='epoch':regs.r1=3
            elif fault=='plan-epoch':put(r.motion_pointer+4,struct.pack('<H',3))
            elif fault=='identity':actor['authorityGeneration']+=1
            elif fault=='state':put(r.motion_pointer+48,b'\xff')
            elif fault=='sample-pointer':regs.r2=r.motion_pointer
            elif fault=='reservation':put(r.motion_pointer+26,struct.pack('<H',43))
            elif fault=='code':put(r.code[0]+40,b'\xff')
            elif fault=='frame-bound':s.completed_frames+=4097
            else:r.counts['ticks']=MAX_CALLBACKS
            with self.subTest(fault=fault),self.assertRaises((ValueError,NativeObservationError)):
                self.invoke(r,r.code[0])
            r.close()

    def test_return_changed_plan_raw_state_flags_and_owner_fail(self):
        for fault in ('plan','state','flags','owner'):
            r,s,actor,regs,put=self.fixture();self.start(r,regs)
            put(r.motion_pointer,motion(1,1,3));put(0x027E2F00,bytes(SAMPLE_BYTES));regs.r0=0
            if fault=='plan':put(r.motion_pointer+12,struct.pack('<h',77))
            elif fault=='state':put(r.motion_pointer+40,struct.pack('<H',99))
            elif fault=='flags':regs.r0=0x100
            else:actor['authorityGeneration']+=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,NativeObservationError)):
                self.invoke(r,0x02010000)
            self.assertEqual(r.result()['returned'],0)
            r.close()

    def test_pending_call_cleanup_is_failed_and_complete(self):
        r,s,actor,regs,put=self.fixture();self.start(r,regs)
        result=r.close()
        self.assertIn('pending callback',result['failure'])
        self.assertEqual(r.observer.contexts,[])
        self.assertEqual(r.observer.hooks.callbacks,{})
        self.assertEqual(r.result()['pending'],0)

    def test_descriptor_and_full_package_wrong_data_reject_arm(self):
        for fault in ('stride','offset','state','package','private'):
            r,s,actor,regs,put=self.fixture();r.close()
            state=s.rt.ACTOR_DESCRIPTOR['state']
            if fault=='stride':state['actorStride']+=4
            elif fault=='offset':state['offsets']['actors']+=4
            elif fault=='state':state['address']+=4
            elif fault=='package':s.packaged_code=lambda at,size:b'\xff'*size
            else:s.rom=s.rt.REPO/'test.nds'
            reader=NativeWalkMatrixObserver(s,r.subject,4096)
            with self.subTest(fault=fault),self.assertRaises((ValueError,NativeObservationError)):
                reader.arm()

    def test_actual_compiled_arm_headers_anchor_every_decoded_field(self):
        root=Path(__file__).resolve().parents[2]
        code='#include "include/overworld_actor_system_internal.h"\n'
        sizes={'OverworldActorRuntimeSlot':SLOT_STRIDE,'OverworldActorStateSnapshot':SNAPSHOT_BYTES,
               'OverworldMotionState':MOTION_BYTES,'OverworldActorPolicyState':POLICY_BYTES,
               'OverworldMotionSample':SAMPLE_BYTES,'OverworldMotionPlan':40}
        for owner,size in sizes.items():code+=f'_Static_assert(sizeof({owner})=={size},"{owner}");\n'
        fields={'OverworldActorSystemState':{'slots':ACTORS_OFFSET},
                'OverworldActorRuntimeSlot':{'motion':SNAPSHOT_BYTES,
                    'policy':SNAPSHOT_BYTES+MOTION_BYTES},
                'OverworldMotionPlan':{'version':0,'kind':2,'facing':3,'fieldEpoch':4,'behaviorFingerprint':6,
                    'startX':8,'startY':10,'targetX':12,'targetY':14,'startBaseY':16,'targetBaseY':20,'duration':24,
                    'reservationId':26,'direction':28,'distance':29,'arcHeightQ4':30,'spinSpeed':31,'swayWidth':32,
                    'visibilityPolicy':33,'pauseFrames':34,'pathAdvancePolicy':35,'commitPolicy':36,'flags':37},
                'OverworldMotionState':{'elapsed':40,'settleRemaining':42,'pathAdvancesPublished':44,
                    'commitSequence':46,'phase':48,'phaseBeforeSuspend':49,'commitPublished':50,'cancelReason':51},
                'OverworldMotionSample':{'renderX':0,'renderY':4,'renderZ':8,'baseY':12,'heightOffset':16,'swayOffset':20,
                    'elapsed':24,'duration':26,'firstPathAdvance':28,'lastPathAdvance':30,'flags':32,'facing':34,'visible':35}}
        for owner,members in fields.items():
            for name,offset in members.items():
                code+=f'_Static_assert(__builtin_offsetof({owner},{name})=={offset},"{owner}.{name}");\n'
        code+=f'_Static_assert(OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS=={ACTOR_CAPACITY},"actor count");\n'
        code+='_Static_assert(OVERWORLD_MOTION_PHASE_MOVING==2 && OVERWORLD_MOTION_KIND_WALK==1,"qualification");\n'
        code+='u16 (*typed_tick)(OverworldMotionState *,u16,OverworldMotionSample *)=&OverworldMotion_Tick;\n'
        result=subprocess.run(['clang','-target','armv5te-none-eabi','-fsyntax-only','-Wno-unknown-attributes',
            '-Wno-gnu-folding-constant','-I',str(root),'-x','c','-'],input=code,text=True,capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
