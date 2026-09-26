"""Actual shared hook dispatch and native header layout; no gameplay claim."""
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import struct
import unittest

from tools.overworld import test_devtools_mount_pacing_observer as mount_fixture
from tools.overworld.devtools_wild_walk_observer import NativeWildWalkObserver, check_cleared_state
from tools.overworld.devtools_observer import NativeObservationError
from tools.overworld.devtools_records import select_current_actor


class WildWalkObserverTests(unittest.TestCase):
    def fixture(self):
        old,s,a,e,regs,put,calls,poses=mount_fixture.MountPacingTests().fixture()
        a.update(role="WILD",species=19,inputOwnership=0)
        a["handle"].update(slot=0,value=131072)
        source=s.rt.wild_spawn(s.emu,0)
        source.update(species=19,object_id=224,active=1)
        s.rt.wild_spawn=lambda emu,slot:deepcopy(source)
        e.update(object_id=224,spawn_object_id=224)
        checked={**a,"identityVerified":True,"engineIdentity":e,"sourceIdentity":source}
        subject=select_current_actor(dict(frame=12,context=dict(fieldEpoch=2,mapGeneration=3),actors=[checked]),checked)
        address=0x02300000
        s.rt.WILD_SYMBOLS={"OverworldWildSpawns_ClearCustomJumpLocal":address}
        s.rt.linked_symbols=lambda path:{"OverworldWildRuntime_RequestMotion":address+0x100}
        s.code_regions=[(p,bytes(range(32))) for p in (address,address+0x100)]
        put(address+0x100,bytes(range(32)))
        old_unsigned=s.rt.unsigned
        memory={s.rt.WILD_STATE+0xE4:0x02290000,0x0229000A:1,0x022903D6:1,source["object"]:0x12005}
        s.rt.unsigned=lambda emu,address,size=4:memory.get(address,old_unsigned(emu,address,size))
        regs.r0=s.rt.WILD_STATE;regs.r1=0
        reader=NativeWildWalkObserver(s,subject,10)
        return reader,s,a,e,regs,put,calls,memory

    def invoke(self,r,address):
        for callback in tuple(r.observer.hooks.callbacks[address]): callback()

    def test_arm_native_before_after_and_close(self):
        r,s,a,e,regs,put,calls,memory=self.fixture()
        self.assertEqual(calls,[])
        r.arm();before=vars(regs).copy()
        self.invoke(r,0x02300000)
        memory[0x0229000A]=memory[0x022903D6]=0;memory[e["pointer"]]=1
        self.invoke(r,regs.lr & ~1)
        event=r.observer.pending[-1]
        self.assertEqual(event["observation"],"wild-walk-clear")
        self.assertEqual(event["before"]["active"],1)
        self.assertTrue(check_cleared_state(event["after"]))
        self.assertEqual(vars(regs),before)
        self.assertNotIn("frame",event)
        self.assertEqual(r.result()["counts"],{"clear":1})
        self.assertIsNone(r.close()["failure"])
        self.assertEqual(r.observer.hooks.callbacks,{})

    def test_wrong_slot_filtered_before_identity(self):
        r,s,a,e,regs,*_=self.fixture();r.arm()
        s.rt.actor_state=lambda *_:(_ for _ in ()).throw(AssertionError("expensive read"))
        regs.r1=1;self.invoke(r,0x02300000)
        self.assertEqual(r.counts,{"clear":0});r.close()

    def test_wrong_state_and_changed_owner_fail(self):
        for fault in ("state","owner"):
            r,s,a,e,regs,*_=self.fixture();r.arm()
            if fault=="state":regs.r0+=4
            else:a["subjectIdentity"]+=1
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):self.invoke(r,0x02300000)
            r.close()

    def test_real_read_seam_reports_bad_memory(self):
        r,s,a,e,regs,put,calls,memory=self.fixture();r.arm()
        memory[0x0229000A]=memory[0x022903D6]=0;memory[e["pointer"]]=1
        current=r._current();clean=r._read_clear_state(current)
        self.assertTrue(check_cleared_state(clean))
        memory[0x0229000A]=1
        with self.assertRaises(ValueError):check_cleared_state(r._read_clear_state(current))
        memory[0x0229000A]=0
        self.assertEqual(clean,r._read_clear_state(current));r.close()

    def test_pending_cleanup_removes_owned_returns(self):
        r,s,a,e,regs,*_=self.fixture();r.arm();self.invoke(r,0x02300000)
        result=r.close()
        self.assertIsNotNone(result["failure"])
        self.assertFalse(r.observer.contexts);self.assertFalse(r.observer.hooks.callbacks)
        self.assertEqual(result,r.close())

    def test_bounds_drops_and_packaged_code_fail(self):
        for fault in ("deadline","drops","code","max"):
            r,s,a,e,regs,put,*_=self.fixture()
            if fault=="max":r.maximum=1201
            if fault=="code":s.code_regions=[]
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):
                r.arm()
                if fault=="deadline":s.completed_frames=23
                if fault=="drops":r.observer.events_dropped=1
                r.completed_boundary()
            r.close()

    def test_selected_unknown_overlay_fails(self):
        r,s,a,e,regs,put,*_=self.fixture();r.arm()
        put(0x02300000,bytes(32))
        with self.assertRaises(NativeObservationError):self.invoke(r,0x02300000)
        r.close()

    def test_clear_limit_and_runtime_pointer_fail(self):
        for fault in ("limit","pointer"):
            r,s,a,e,regs,put,calls,memory=self.fixture();r.arm()
            if fault=="limit":r.counts["clear"]=64
            else:memory[s.rt.WILD_STATE+0xE4]=1
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):self.invoke(r,0x02300000)
            r.close()

    def test_offsets_against_actual_c_layout(self):
        root=Path(__file__).resolve().parents[2]
        native=(root/"src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        destination_scan=re.search(r"typedef struct OverworldWildSpawnDestinationScan \{.*?\} OverworldWildSpawnDestinationScan;",native,re.S)[0]
        definition=re.search(r"typedef struct OverworldWildOverlayRuntimeState \{.*?\} OverworldWildOverlayRuntimeState;",native,re.S)[0]
        source='#include "include/overworld_wild_spawns_internal.h"\n#include "include/map_events_internal.h"\n'
        source+='#include "include/overworld_wild_helper.h"\n#include "include/overworld_spawn_guard.h"\n'
        source+='#include "include/overworld_behavior_condition_adapter.h"\n'
        source+='typedef struct OverworldWildBehaviorSlotCache OverworldWildBehaviorSlotCache;\n'+destination_scan+'\n'+definition
        source+='\n_Static_assert((BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13)==0x12004,"owned flags");'
        for owner,member,offset in (("OverworldWildSpawnState","movementRuntimeState",0xE4),
            ("OverworldWildSpawnState","movementCooldowns",0xED),
            ("OverworldWildOverlayRuntimeState","movementMotionIdentities",0xDC),
            ("OverworldWildOverlayRuntimeState","movementCustomJumpActive",0xA),
            ("OverworldWildOverlayRuntimeState","movementCustomMotionModes",0x3D6)):
            source+=f'\n_Static_assert(__builtin_offsetof({owner},{member})=={offset},"{member}");'
        result=subprocess.run(["clang","-target","armv5te-none-eabi","-fsyntax-only","-Wno-unknown-attributes",
                              "-Wno-gnu-folding-constant","-I",str(root),"-x","c","-"],
                              input=source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_request_receipt_keeps_native_rejection_and_before_after(self):
        r,s,a,e,regs,put,calls,memory=self.fixture();r.arm()
        a.update(motionPhase="SETTLING",commitSequence=1)
        regs.r3=1
        put(regs.sp,struct.pack("<7I",0,0,3,4,0,0,2))
        memory[s.rt.WILD_STATE+0xED]=0
        memory[0x022900DC]=17
        before=vars(regs).copy()
        self.invoke(r,0x02300100)
        self.assertEqual(vars(regs),before)
        memory[0x022900DC]=0
        regs.r0=9
        returned=vars(regs).copy()
        self.invoke(r,regs.lr & ~1)
        event=r.observer.pending[-1]
        self.assertEqual(event["observation"],"wild-walk-request")
        self.assertEqual(event["decisionName"],"ALREADY_ACTIVE")
        self.assertEqual(event["before"]["motionIdentity"],17)
        self.assertEqual(event["after"]["motionIdentity"],0)
        self.assertEqual(event["before"]["cooldown"],0)
        self.assertEqual(event["before"]["current"]["publicSubject"]["motionPhase"],"SETTLING")
        self.assertEqual(event["request"]["duration"],4)
        self.assertEqual(vars(regs),returned)
        self.assertEqual(r.result()["counts"],{"clear":0})
        self.assertEqual(r.result()["requestCount"],1)
        self.assertEqual(r.result()["latestRequest"]["decision"],9)
        self.assertFalse(r.result()["acceptedProof"])
        self.assertIsNone(r.close()["failure"])
        self.assertFalse(r.observer.hooks.callbacks)

    def test_request_slot_filter_and_pending_cleanup(self):
        r,s,a,e,regs,put,calls,memory=self.fixture();r.arm()
        regs.r1=1
        self.invoke(r,0x02300100)
        self.assertEqual(r.request_count,0)
        regs.r1=0;regs.r3=1
        self.invoke(r,0x02300100)
        self.assertIsNotNone(r.close()["failure"])
        self.assertFalse(r.observer.contexts)
        self.assertFalse(r.observer.hooks.callbacks)

    def test_request_invalid_arguments_return_owner_and_limit_fail(self):
        for fault in ("state","stack","width","lane","decision","owner","limit"):
            r,s,a,e,regs,put,calls,memory=self.fixture();r.arm();regs.r3=1
            if fault=="state":regs.r0=0
            if fault=="stack":regs.sp=1
            if fault=="width":put(regs.sp,struct.pack("<I",256))
            if fault=="lane":regs.r2=1
            if fault=="limit":r.request_count=256
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):
                self.invoke(r,0x02300100)
                if fault=="decision":regs.r0=99
                if fault=="owner":a["subjectIdentity"]+=1
                self.invoke(r,regs.lr & ~1)
            r.close()
            self.assertFalse(r.observer.hooks.callbacks)


if __name__=="__main__":unittest.main()
