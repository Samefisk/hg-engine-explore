"""Host recorder controls through real shared entry/return taps; not live proof."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import re
import struct
import subprocess
import tempfile
import unittest

from tools.overworld.devtools_binding_context import install_binding_context, FUNCTION, LABEL, MAX_RECEIPTS
from tools.overworld.devtools_engine import Hooks
from tools.overworld.devtools_observer import NativeObservation, NativeObservationError

ROOT = Path(__file__).resolve().parents[2]


class Fixture:
    def __init__(self, *, install=True):
        self.memory, self.callbacks = {}, {}
        self.address, self.table, self.state = 0x02300100, 0x02300000, 0x02260000
        self.field, self.manager, self.objects = 0x02210000, 0x02211000, 0x02212000
        self.regs = SimpleNamespace(r0=0, sp=0x027e3000, lr=0x02002001)
        self.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=self.regs,
            register_exec=lambda addr, cb: self.callbacks.__setitem__(addr, cb)))
        self.actor = dict(active=True,presentationAttached=True,presentationState=7,
            handle=dict(value=0x10000,slot=0,generation=1,fieldEpoch=2,mapGeneration=3,encounterGeneration=4),
            species=19,form=0,level=5,subjectIdentity=99,role="WILD",behaviorFingerprint=44,
            matchedLayerMask=7,commitSequence=1,motionPhase="IDLE",motionKind="NONE",
            authorityGeneration=1,engineAnchorGeneration=1,presentationGeneration=1)
        self.source = dict(object=self.objects,personality=99,map_id=33,species=19,form=0,
            level=5,active=1,object_id=224,encounter_generation=4)
        self.engine = dict(pointer=self.objects,manager_index=0,in_manager=True,active=True,
            object_id=224,object_map_id=33,script_id=2074,object_manager=self.manager,
            current_manager=self.manager,current_map_id=33,
            id_lookup=dict(status="complete",pointer_matches=True,eligible_count=1))
        self.pose = dict(flags=0x201,x=550,y=380,pos_x=36077568,pos_y=0,pos_z=24936448)
        self.lifecycle = dict(authenticated=True,fieldReady=1,controlPointer=0x02220000,
            managerPointer=0x02221000,managerExecState=2,managerProcState=0,reason=None)
        descriptor = dict(compatibility=dict(address=self.table,version=3,size=32,
            callbacks=dict(getContext=self.address|1)),state=dict(address=self.state,size=2448,
            offsets=dict(fieldEpoch=12,mapGeneration=46)),capacities=dict(actors=10))
        symbols = {FUNCTION:self.address|1,"gOverworldActorSystemState":self.state}
        self.reads = []
        self.rt = SimpleNamespace(REPO=ROOT,ACTOR_DESCRIPTOR=descriptor,ACTOR_SYMBOLS=symbols,
            linked_symbol=lambda sy,n:sy[n],EXECUTED_FRAME_COUNT=20,
            unsigned=lambda e,a,n=4:int.from_bytes(self.read(a,n),"little"),
            actor_state=lambda e,slot:deepcopy(self.actor) if slot==0 else dict(active=False),
            wild_spawn=lambda e,slot:deepcopy(self.source),
            live_wild_object_identity=lambda e,slot:deepcopy(self.engine),
            object_state=lambda e,p:deepcopy(self.pose),field_map_id=lambda e:33)
        table = struct.pack("<IHH6I",0x4341574f,3,32,0,0,0,0,0,self.address|1)
        self.code_regions = [(self.table,table),(self.address,b"G"*32)]
        for a,data in self.code_regions:self.put(a,data)
        self.put(self.state,struct.pack("<IHHIH",0x5353574f,1,2448,100,2))
        self.put(self.state+46,struct.pack("<H",3))
        self.put(self.field+0x3c,struct.pack("<I",self.manager))
        self.put(self.manager+4,struct.pack("<I",1))
        self.put(self.manager+0x124,struct.pack("<I",self.objects))
        self.prepared = False
        self.field_pointer = lambda:self.field
        self._field_actor_availability = lambda field:deepcopy(self.lifecycle)
        self.hooks = Hooks(self.rt,self.emu)
        self.observer = NativeObservation(self,self.hooks,lambda p,a,n:self.read(a,n))
        def linked(label,path,symbols,name,before,after,**kwargs):
            address=self.rt.linked_symbol(symbols,name)&~1
            self.observer._tap(label,address,self.read(address,32),before,after,**kwargs)
        self.linked=linked
        self.reader=install_binding_context(self.observer,linked) if install else None

    def put(self,address,data):self.memory.update({address+i:v for i,v in enumerate(data)})
    def read(self,address,size):
        self.reads.append((address,size))
        return bytes(self.memory.get(address+i,0) for i in range(size))
    def enter(self):self.callbacks[self.address](self.address,2)
    def returned(self,value=0x00030002):
        self.regs.r0=value
        self.callbacks[self.regs.lr&~1](self.regs.lr&~1,2)
    def receipt(self):
        self.observer.completed_frame(101)
        rows=self.observer.drain()
        return rows[-1]["data"] if rows else None
    def capture(self,value=0x00030002):
        self.reader.enable();self.enter();self.returned(value);return self.receipt()


class BindingContextTests(unittest.TestCase):
    def test_disabled_is_read_free_and_enable_is_idempotent_without_reset(self):
        f=Fixture();f.reads.clear()
        self.assertEqual(f.callbacks,{})
        self.assertEqual(f.reads,[])
        f.reader.enable();f.reader.enable();f.enter();f.returned()
        receipt=f.receipt()
        self.assertEqual(receipt["observation"],LABEL)
        self.assertEqual(receipt["boundary"],"public-getContext-return")
        self.assertEqual(receipt["status"],"observed")
        self.assertEqual(receipt["ownerContext"],dict(fieldEpoch=2,mapGeneration=3,mapId=33))
        self.assertTrue(receipt["returnMatchesResident"])
        self.assertTrue(all(receipt["candidates"][0]["identityChecks"].values()))
        self.assertEqual(receipt["returnActorFrame"],100)
        self.assertEqual(receipt["returnNativeCycle"],20)
        self.assertEqual(receipt["candidates"][0]["engineObject"],f.pose)
        f.reader.enable();f.enter()
        self.assertEqual(f.observer.return_tokens,[])
        self.assertEqual(f.reader.count,1)

    def test_wrong_register_and_stale_actor_remain_visible_through_same_tap(self):
        for fault in ("returned-high","returned-low","actor-high","actor-low","source-pid","source-object"):
            with self.subTest(fault=fault):
                f=Fixture();value=0x00030002
                if fault=="returned-high":value=0x00090002
                if fault=="returned-low":value=0x00030009
                if fault=="actor-high":f.actor["handle"]["mapGeneration"]=9
                if fault=="actor-low":f.actor["handle"]["fieldEpoch"]=9
                if fault=="source-pid":f.source["personality"]=100
                if fault=="source-object":f.source["object"]+=0x12c
                result=f.capture(value)
                self.assertEqual(result["status"],"observed")
                self.assertEqual(result["packedContext"],value)
                self.assertEqual(result["returnValue"],value)
                self.assertEqual(len(result["candidates"]),1)
                self.assertFalse(all(result["candidates"][0]["identityChecks"].values()))
                self.assertEqual(result["candidates"][0]["sourceIdentity"],f.source)

    def test_return_reads_current_actor_not_entry_or_later_snapshot(self):
        f=Fixture();f.reader.enable();f.enter()
        f.actor["handle"]["mapGeneration"]=11
        f.rt.EXECUTED_FRAME_COUNT=21
        f.returned();result=f.receipt()
        f.actor["handle"]["mapGeneration"]=12
        self.assertEqual(result["candidates"][0]["publicSubject"]["handle"]["mapGeneration"],11)
        self.assertEqual(result["returnNativeCycle"],21)
        self.assertFalse(result["candidates"][0]["identityChecks"]["mapGeneration"])

    def test_field_unavailable_never_dereferences_engine_and_absent_is_not_a_match(self):
        f=Fixture();f.lifecycle.update(fieldReady=0,reason="field-exiting")
        f.rt.actor_state=lambda *a: self.fail("actor read during unload")
        result=f.capture()
        self.assertEqual(result["status"],"field-unavailable")
        self.assertEqual(result["candidates"],[])
        f=Fixture();f.actor["species"]=165
        self.assertEqual(f.capture()["candidates"],[])

    def test_bad_state_partial_source_and_unsafe_manager_are_explicit_unknown(self):
        for fault in ("header","manager","partial"):
            with self.subTest(fault=fault):
                f=Fixture()
                if fault=="header":f.put(f.state,b"BAD!")
                if fault=="manager":f.put(f.manager+4,struct.pack("<I",65))
                if fault=="partial":f.rt.wild_spawn=lambda *a:dict(species=19)
                result=f.capture()
                self.assertEqual(result["status"],"unknown")
                self.assertTrue(result["readError"])
                if fault=="partial":self.assertEqual(result["candidates"][0]["sourceIdentity"],dict(species=19))

    def test_code_table_descriptor_and_return_stack_authentication(self):
        for fault in ("entry-code","return-code","entry-table","return-table","stack"):
            with self.subTest(fault=fault):
                f=Fixture();f.reader.enable()
                if fault=="entry-code":f.put(f.address,b"X")
                if fault=="entry-table":f.put(f.table+28,struct.pack("<I",f.address+5))
                f.enter()
                if fault.startswith("entry"):
                    self.assertIsNotNone(f.hooks.error);self.assertEqual(f.observer.pending.__len__(),0);continue
                if fault=="return-code":f.put(f.address,b"X")
                if fault=="return-table":f.put(f.table+28,struct.pack("<I",f.address+5))
                if fault=="stack":f.regs.sp+=4
                f.returned()
                if fault=="return-code":self.assertIsNotNone(f.hooks.error)
                elif fault=="return-table":self.assertEqual(f.receipt()["status"],"unknown")
                else:self.assertIsNone(f.receipt())
        f=Fixture(install=False);f.rt.ACTOR_DESCRIPTOR["compatibility"]["callbacks"]["getContext"]+=4
        with self.assertRaises(NativeObservationError):install_binding_context(f.observer,f.linked).enable()

    def test_frame_and_total_bounds_do_not_reset_or_overflow(self):
        f=Fixture();f.capture();f.reader.count=MAX_RECEIPTS
        f.reader.enable();f.put(f.state+8,struct.pack("<I",101));f.enter();f.returned()
        self.assertIn("receipt limit",f.hooks.error)
        self.assertEqual(f.reader.count,MAX_RECEIPTS)
        f=Fixture();f.capture();f.put(f.state+8,struct.pack("<I",99));f.enter()
        self.assertIn("clock regressed",f.hooks.error)

    def test_real_header_macros_and_actual_c_function_preserve_packed_halves(self):
        header=(ROOT/"include/overworld_actor_system_internal.h").read_text()
        public=header.split("typedef u32 OverworldActorFieldContext;",1)[1].split("typedef OverworldActorFieldContext (*",1)[0]
        source=(ROOT/"src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
        body=re.search(r"OverworldActorFieldContext "+FUNCTION+r"\(void\)\n\{.*?\n\}",source,re.S).group()
        code='''#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32; typedef uint16_t u16;
typedef u32 OverworldActorFieldContext;
struct {u16 fieldEpoch;u16 mapGeneration;} gOverworldActorSystemState;
static int initialized;
static void ActorSystem_EnsureInitialized(void){initialized++;}
'''+public+body+'''
int main(void){u16 values[][2]={{2,3},{65535,1},{1,65535},{0,0}};
for(int i=0;i<4;i++){gOverworldActorSystemState.fieldEpoch=values[i][0];gOverworldActorSystemState.mapGeneration=values[i][1];
u32 p=OverworldActorSystem_CompatibilityGetContextImpl();
printf("%u %u %u\\n",p,OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(p),OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(p));}
return initialized!=4;}
'''
        with tempfile.TemporaryDirectory() as d:
            exe=Path(d)/"context"
            subprocess.run(["cc","-std=c11","-x","c","-","-o",str(exe)],input=code,text=True,capture_output=True,check=True)
            output=subprocess.check_output([str(exe)],text=True)
        self.assertEqual(output,"196610 2 3\n131071 65535 1\n4294901761 1 65535\n0 0 0\n")


if __name__=="__main__":unittest.main()
