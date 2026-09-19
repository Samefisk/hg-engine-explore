"""Read-only role-profile callback controls; no emulator/gameplay proof."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import subprocess
import tempfile
import unittest

from tools.overworld.devtools_role_profile import RoleProfileObserver, NativeObservationError
from tools.overworld.devtools_runtime import DevtoolsHooks


class RoleProfileTests(unittest.TestCase):
    def fixture(self):
        memory={}
        def put(p,b):memory.update({p+i:v for i,v in enumerate(b)})
        def read(p,n):return bytes(memory.get(p+i,0) for i in range(n))
        handle=dict(slot=7,value=131079,generation=2,fieldEpoch=2,mapGeneration=3,encounterGeneration=4)
        actor=dict(active=True,presentationAttached=True,handle=handle,species=155,form=0,level=6,
            subjectIdentity=123,role="FOLLOWER",behaviorFingerprint=1,matchedLayerMask=2,
            authorityGeneration=1,engineAnchorGeneration=1,presentationGeneration=1)
        source=dict(object=0x02240000,personality=123,species=155,form=0,level=6,active=3,
                    encounter_generation=4,object_id=231,map_id=33)
        engine=dict(pointer=source["object"],in_manager=True,active=True,object_manager=0x02250000,
                    current_manager=0x02250000,object_id=231,object_map_id=33,script_id=2074)
        regs=SimpleNamespace(r0=0x02200000,r1=7,r2=0x02210000,r3=0x02211000,sp=0x027E3000)
        regs_calls=[]
        emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=regs,
            register_exec=lambda a,c:regs_calls.append((a,c))))
        rt=SimpleNamespace(REPO=Path(__file__).resolve().parents[2],WILD_STATE=0x02200000,
            MOUNT_SYMBOLS={"sOverworldMountState":0x023BC744},WILD_SYMBOLS={},
            linked_symbol=lambda sy,n:sy[n],actor_state=lambda e,s:deepcopy(actor),
            wild_spawn=lambda e,s:deepcopy(source),live_wild_object_identity=lambda e,s:deepcopy(engine),
            field_map_id=lambda e:33,unsigned=lambda e,p,n=4:2 if p==0x0226000C else 3,
            ACTOR_DESCRIPTOR={"state":{"address":0x02260000,"offsets":{"fieldEpoch":12,"mapGeneration":46}}})
        s=SimpleNamespace(emu=emu,rt=rt,read=read,prepared=True,native_heap_generation=1,
                          field_pointer=lambda:0x02270000)
        hooks=DevtoolsHooks(rt,emu)
        observer=SimpleNamespace(session=s,hooks=hooks,tokens=[],return_tokens=[],contexts=[],sequence=10,
            _subject=lambda slot:deepcopy({k:v for k,v in actor.items() if k not in ("active","presentationAttached")}))
        def linked(label,path,symbols,name,before,after,**kwargs):
            observer.tokens.append(hooks.add(0x02300000+(0x40 if label.endswith("mount") else 0),before))
        reader=RoleProfileObserver(observer,linked);reader.mount_state=0x023BC744
        put(regs.r2,bytes(range(144)));put(regs.r3,bytes(range(8)))
        return reader,s,actor,source,engine,regs,put,regs_calls

    def mount(self,f):
        reader,s,actor,source,engine,regs,put,_=f
        regs.r0=s.field_pointer();regs.r1=0x02212000
        binding=struct.pack("<IHHHHBBBB",123,155,33,3,4,0,6,1,0)
        put(regs.r1,binding);put(regs.sp,struct.pack("<I",0x02213000))
        before=reader.mount_before()
        put(reader.mount_state,struct.pack("<II",s.field_pointer(),0x02213000)+bytes(range(72))+
            binding+struct.pack("<IBBBB",7,1,0,0,0))
        return before

    def test_getter_returns_exact_output_and_bound_subject(self):
        f=self.fixture();reader=f[0]
        before=reader.getter_before();result=reader.getter_after(before,{})
        self.assertEqual(result["profileHex"],bytes(range(144)).hex())
        self.assertEqual(result["primitivesHex"],bytes(range(8)).hex())
        self.assertEqual(result["ownerAfter"]["publicSubject"]["subjectIdentity"],123)
        self.assertIsNone(result["returnValue"])
        # Getter observes changed bytes faithfully; host equality is the consumer's job.
        f[6](f[5].r2,b"\xff")
        self.assertTrue(reader.getter_after(before,{})["profileHex"].startswith("ff"))

    def test_wrong_native_identity_stale_return_and_invalid_output_pointer(self):
        for fault in ("pid","object","state","output","return-owner"):
            f=self.fixture();r,s,a,source,e,regs,put,_=f
            before=r.getter_before()
            if fault=="pid":source["personality"]+=1
            if fault=="object":e["pointer"]+=4
            if fault=="state":regs.r0+=4
            if fault=="output":regs.r2=1
            if fault=="return-owner":s.native_heap_generation+=1
            with self.subTest(fault=fault),self.assertRaises(NativeObservationError):
                r.getter_after(before,{}) if fault=="return-owner" else r.getter_before()

    def test_nullable_getter_outputs_have_no_transfer_credit(self):
        for profile,primitives in ((0,0x02211000),(0x02210000,0),(0,0)):
            r,s,a,source,e,regs,put,_=self.fixture()
            regs.r2,regs.r3=profile,primitives
            with self.subTest(profile=profile,primitives=primitives):
                self.assertIsNone(r.getter_before())
                self.assertEqual(r.count,0);self.assertEqual(r.owned_data,[])
                regs.r2,regs.r3=0x02210000,0x02211000
                self.assertIsNotNone(r.getter_before())
                self.assertEqual(r.count,1)

    def test_partial_getter_still_rejects_nonzero_invalid_output(self):
        for profile,primitives in ((1,0),(0,1),(0x02ffffff,0),(0,0x02ffffff)):
            r,s,a,source,e,regs,put,_=self.fixture()
            regs.r2,regs.r3=profile,primitives
            with self.subTest(profile=profile,primitives=primitives),self.assertRaises(NativeObservationError):
                r.getter_before()

    def test_nullable_getter_source_contract_and_profile_only_caller(self):
        source=(Path(__file__).resolve().parents[2]/
            "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        body=source.split("\nOverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(",1)[1]
        body=body.split("\n}",1)[0]
        self.assertIn("if (profileOut != NULL)",body)
        self.assertIn("if (primitivesOut != NULL)",body)
        caller=source.split("static BOOL OverworldWildSpawns_IsCanopyHopperTreeTopSlot(",1)[1]
        caller=caller.split("\n}",1)[0]
        self.assertRegex(caller, r"state,\s*slot,\s*&profile,\s*NULL\);")

    def test_mount_exact_owner_transfer_and_wrong_output_controls(self):
        for fault in (None,"owner","binding","phase","generation","return","subject"):
            f=self.fixture();r=f[0];before=self.mount(f)
            if fault=="owner":f[6](r.mount_state+8,b"\xff")
            if fault=="binding":f[6](r.mount_state+80,b"\xff")
            if fault=="phase":f[6](r.mount_state+100,b"\x02")
            if fault=="generation":f[6](r.mount_state+96,bytes(4))
            if fault=="subject":f[3]["personality"]+=1
            context={"returnValue":0 if fault=="return" else 1}
            if fault is None:
                result=r.mount_after(before,context)
                self.assertEqual(result["ownerHex"],bytes(range(72)).hex())
                self.assertEqual(result["sessionGeneration"],7)
            else:
                with self.subTest(fault=fault),self.assertRaises(NativeObservationError):r.mount_after(before,context)

    def test_capture_has_no_idle_hooks_preserves_shared_and_cleans_on_error(self):
        f=self.fixture();r=f[0];hooks=r.observer.hooks
        self.assertEqual(f[7],[])
        shared=hooks.add(0x02300000,lambda:None)
        original=RuntimeError("first fault")
        with self.assertRaisesRegex(RuntimeError,"first fault"):
            with r.capture():
                self.assertTrue(r.active)
                raise original
        self.assertFalse(r.active)
        self.assertIn(shared[1],hooks.callbacks[shared[0]])
        self.assertNotIn(0x02300040,hooks.callbacks)
        self.assertEqual(r.observer.tokens,[])

    def test_lifetime_capture_limit_and_first_error_survives_cleanup_failure(self):
        f=self.fixture();r=f[0]
        for _ in range(16):
            with r.capture():pass
        registered=len(f[7])
        with self.assertRaisesRegex(NativeObservationError,"capture limit"):
            with r.capture():pass
        self.assertEqual(len(f[7]),registered)
        f=self.fixture();r=f[0]
        r.observer.hooks.retire_empty=lambda _address: (_ for _ in ()).throw(ValueError("cleanup"))
        failure=RuntimeError("original")
        with self.assertRaises(RuntimeError) as caught:
            with r.capture():raise failure
        self.assertIs(caught.exception,failure)
        self.assertEqual(failure.role_profile_cleanup_errors,["cleanup","cleanup"])

    def test_actual_halfword_surface_pointer_and_invalid_odd_pointer(self):
        f=self.fixture();r=f[0];before=self.mount(f)
        f[6](f[5].sp,struct.pack("<I",0x022B976A))
        before=r.mount_before()
        f[6](r.mount_state+4,struct.pack("<I",0x022B976A))
        self.assertEqual(r.mount_after(before,{"returnValue":1})["surfacePointer"],0x022B976A)
        f[6](f[5].sp,struct.pack("<I",0x022B976B))
        with self.assertRaises(NativeObservationError):r.mount_before()

    def test_pending_owned_return_rejects_success_and_keeps_shared_context(self):
        f=self.fixture();r=f[0];o=r.observer
        shared={"data":{}}
        o.contexts.append(shared)
        with self.assertRaisesRegex(NativeObservationError,"pending owned"):
            with r.capture():
                own=r.getter_before()
                o.contexts.append({"data":own})
        self.assertEqual(o.contexts,[shared])

    def test_tracks_only_its_entry_created_return_and_preserves_first_fault(self):
        f=self.fixture();r=f[0];o=r.observer
        def linked(label,path,symbols,name,before,after,**kwargs):
            def entry():
                data=before()
                if data is not None:
                    o.contexts.append({"data":data})
                    o.return_tokens.append(o.hooks.add(0x02001000,lambda:None))
            o.tokens.append(o.hooks.add(0x02300000+(0x40 if label.endswith("mount") else 0),entry))
        r.linked=linked
        original=RuntimeError("native failed")
        shared_context={"data":{}}
        with self.assertRaises(RuntimeError) as caught:
            with r.capture():
                o.tokens[0][1]()
                shared_return=o.hooks.add(0x02001040,lambda:None)
                o.return_tokens.append(shared_return)
                o.contexts.append(shared_context)
                raise original
        self.assertIs(caught.exception,original)
        self.assertEqual(o.contexts,[shared_context])
        self.assertEqual(o.return_tokens,[shared_return])
        self.assertIn("pending owned",original.role_profile_cleanup_errors[0])
        self.assertNotIn(0x02001000,o.hooks.callbacks)
        self.assertIn(0x02001040,o.hooks.callbacks)

    def test_completed_owned_return_dispatcher_is_retired(self):
        f=self.fixture();r=f[0];o=r.observer
        with r.capture():
            token=o.hooks.add(0x02001000,lambda:None)
            r.owned_returns.append(token)
            o.hooks.remove(token)
        self.assertNotIn(0x02001000,o.hooks.callbacks)

    def test_opt_in_control_changes_real_byte_rejects_and_restores_without_execution(self):
        f=self.fixture();r,s=f[:2];writes=[]
        s.completed_frames=734;s.rt.EXECUTED_FRAME_COUNT=1860
        s.rt.actor_memory_write=lambda emu,p,b:(writes.append((p,bytes(b))),f[6](p,b))[-1]
        with r.capture(control=True):
            before=self.mount(f)
            clean=s.read(r.mount_state,104)
            result=r.mount_after(before,{"returnValue":1})
        proof=result["readerControl"]
        self.assertTrue(proof["rejected"])
        self.assertFalse(proof["acceptedProof"])
        self.assertEqual(len(writes),2)
        self.assertEqual(writes[0],(r.mount_state+8,b"\x01"))
        self.assertEqual(writes[1],(r.mount_state+8,b"\x00"))
        self.assertEqual(s.read(r.mount_state,104),clean)
        self.assertEqual(proof["beforeClock"],proof["afterClock"])

    def test_default_control_has_no_writes(self):
        f=self.fixture();r,s=f[:2]
        s.rt.actor_memory_write=lambda *args:self.fail("read-only capture wrote memory")
        with r.capture():
            result=r.mount_after(self.mount(f),{"returnValue":1})
        self.assertNotIn("readerControl",result)

    def test_control_restores_after_fault_read_failure_and_rejects_missing_check(self):
        for fault in ("read","missing-check","advance"):
            f=self.fixture();r,s=f[:2];writes=[]
            s.completed_frames=734;s.rt.EXECUTED_FRAME_COUNT=1860
            def write(emu,p,b):
                writes.append((p,bytes(b)));f[6](p,b)
                if fault=="advance" and len(writes)==1:s.rt.EXECUTED_FRAME_COUNT+=1
            s.rt.actor_memory_write=write
            real_read=s.read;failed=False
            def read(p,n):
                nonlocal failed
                if fault=="read" and len(writes)==1 and not failed:
                    failed=True;raise RuntimeError("changed read failed")
                return real_read(p,n)
            s.read=read
            if fault=="missing-check":
                r._check_mount_snapshot=lambda v,o,b:(b[8:],7,1)
            with self.subTest(fault=fault),self.assertRaises(Exception) as caught:
                with r.capture(control=True):
                    before=self.mount(f);clean=real_read(r.mount_state,104)
                    r.mount_after(before,{"returnValue":1})
            self.assertEqual(real_read(r.mount_state,104),clean)
            self.assertEqual(len(writes),2)
            self.assertIn({"read":"changed read failed","missing-check":"accepted the changed",
                           "advance":"guest advanced"}[fault],str(caught.exception))

    def test_restoration_failure_marks_original_read_error_fatal(self):
        f=self.fixture();r,s=f[:2];writes=[]
        s.completed_frames=734;s.rt.EXECUTED_FRAME_COUNT=1860
        def write(emu,p,b):
            writes.append(bytes(b))
            if len(writes)==1:f[6](p,b)
        s.rt.actor_memory_write=write
        real=s.read
        first=RuntimeError("first failed read")
        failed=False
        def read(p,n):
            nonlocal failed
            if len(writes)==1 and not failed:failed=True;raise first
            return real(p,n)
        s.read=read
        with self.assertRaises(RuntimeError) as caught:
            with r.capture(control=True):r.mount_after(self.mount(f),{"returnValue":1})
        self.assertIs(caught.exception,first)
        self.assertTrue(first.fatal)
        self.assertIn("restoration differs",first.role_profile_restoration_error)

    def test_public_layout_compiled_and_arm_runtime_prefix_anchored(self):
        root=Path(__file__).resolve().parents[2]
        header=(root/"include/overworld_mount.h").read_text()
        structs=""
        for name in ("OverworldMountBinding","OverworldMountSnapshot"):
            structs+="typedef struct "+name+" {"+header.split("typedef struct "+name+" {",1)[1].split("} "+name+";",1)[0]+"} "+name+";\n"
        code='#include <stdio.h>\n#include <stddef.h>\n#include "overworld_behavior_resolver.h"\n'+structs+'''
int main(void){ printf("%zu %zu %zu %zu %zu %zu %zu", sizeof(OverworldWildBehaviorProfile),
sizeof(OverworldWildBehaviorPrimitives),sizeof(OverworldMountBinding),sizeof(OverworldMountSnapshot),
offsetof(OverworldMountSnapshot,binding),offsetof(OverworldMountSnapshot,sessionGeneration),
_Alignof(OverworldWildSurfaceCatalog)); }
'''
        with tempfile.TemporaryDirectory() as d:
            exe=str(Path(d)/"layout")
            subprocess.run(["cc","-DOVERWORLD_BEHAVIOR_HOST","-I",str(root/"include"),"-x","c","-","-o",exe],
                input=code,text=True,capture_output=True,check=True)
            self.assertEqual(subprocess.check_output([exe]).decode(),"144 8 16 96 72 88 2")
        internal=(root/"include/overworld_mount_internal.h").read_text()
        prefix=internal.split("typedef struct OverworldMountRuntimeState {",1)[1].split("OverworldMountSnapshot snapshot;",1)[0]
        self.assertEqual(prefix.split(),["FieldSystem","*fieldSystem;","const","OverworldWildSurfaceCatalog","*surfaceCatalog;"])


if __name__=="__main__":unittest.main()
