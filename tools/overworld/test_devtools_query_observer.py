"""Focused host controls for the real opt-in Cargo entry/return reader."""
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from tools.overworld.devtools_engine import Hooks
from tools.overworld.devtools_observer import NativeObservation, NativeObservationError
from tools.overworld.devtools_query_observer import (
    NativeQueryObserver, LABEL, TICK_OFFSET, FRAME_WORLD, FRAME_VALID, BINDINGS,
    QUERY_OWNER, QUERY_VALID, QUERY_STATE_SIZE, RUNTIME_QUERY, RUNTIME_CONDITIONS, sealed_package,
    relocated_image, READ_BUDGET, INITIAL_READ_BUDGET, CARGO_CODE_START,
    CARGO_CODE_END, CARGO_ABI_OFFSET, CARGO_ABI_SIZE, native_unload_binding,
    CARGO_WILD_START, CARGO_WILD_END, ENTRY_LABEL, ENTRY_CONTROL_LABEL, QUERY_PREFIX_SIZE, QUERY_ENTRY_ACTIVE, ENTRY_LAYOUT)
from tools.overworld.devtools_runtime import DevtoolsSession
from tools.overworld.pack_query_code_addon import CARGO_PREFIX_CAP

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "tools/overworld/devtools_records.py").is_file())
PACKAGE_DIRECTORY = ROOT / "build/overworld_query_code_addon"
WILD_ELF = ROOT / "build/overworld_wild_spawns_overlay_linked.o"
PACKAGE_MEMBER = ROOT / "build/a028/9_21"


def current_package():
    return sealed_package((PACKAGE_DIRECTORY / "image.elf").read_bytes(),
                          (PACKAGE_DIRECTORY / "query.bin").read_bytes(),
                          PACKAGE_MEMBER.read_bytes())


class Fixture:
    def __init__(self):
        self.memory, self.callbacks, self.reads = {}, {}, []
        self.entry, self.field, self.runtime = 0x02250040, 0x02220000, 0x02248000
        self.conditions, self.q, self.wild = 0x02249000, 0x02150000, 0x023DA000
        self.call, self.world, self.output = 0x027E1000, 0x027E1100, 0x027E1200
        self.full = struct.pack("<6H", 1, 2, 3, 3, 1, 0)
        self.other = struct.pack("<6H", 7, 2, 3, 3, 1, 0)
        self.command,self.control,self.object=0x027E1800,0x027E1C00,0x02230000
        self.active_slots={1,7}
        self.regs = SimpleNamespace(r0=self.call, r1=self.output, sp=0x027E3000, lr=0x02004001)
        self.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=self.regs,
            register_exec=lambda address, callback: self.callbacks.__setitem__(address, callback)))
        self.rt = SimpleNamespace(ACTOR_DESCRIPTOR={"state":{"address":0x023BA170},
            "capacities":{"actors":10}}, WILD_STATE=self.wild, EXECUTED_FRAME_COUNT=90,
            unsigned=lambda emu,address,size=4:int.from_bytes(self.read(address,size),"little"),
            actor_state=lambda emu,slot:dict(active=slot in self.active_slots, handle=self.handles.get(slot)))
        from tools.overworld.devtools_query_observer import handle
        self.handles = {1:handle(self.full), 7:handle(self.other)}
        self.prepared = True
        self.field_pointer = lambda:self.field
        self._field_actor_availability = lambda field:dict(authenticated=True,reason=None)
        self._throw_interactions_window = True
        self.hooks = Hooks(self.rt,self.emu)
        self.observer = NativeObservation.__new__(NativeObservation)
        self.observer.session,self.observer.hooks = self,self.hooks
        self.observer.tokens,self.observer.return_tokens = [],[]
        self.rows=[]
        self.observer._clock=lambda:dict(actorFrame=100,nativeCycle=self.rt.EXECUTED_FRAME_COUNT)
        self.observer._queue=lambda label,context,value:self.rows.append(dict(label=label,context=context,data=value))
        self.observer.sequence=0;self.observer.pending=[];self.observer.spawn_contexts=[]
        self.observer._flush_pending=lambda frame:None
        self.observer.calls={"spawn-prepared":{"address":0x023D0802}}
        self.reader = NativeQueryObserver.__new__(NativeQueryObserver)
        r=self.reader
        r.observer,r.session,r.active,r.count=self.observer,self,True,0
        r.count_cycle=None
        r.tokens,r.returns,r.contexts=[],[],[]
        r.loaded=None
        r.pending_detaches={}
        r.tick_token=r.draining=None
        r.unload=0x023C2836; r.unload_bytes=b"U"*88
        r.service,r.state,r.discovery=0x023C22F0,0x023C2308,0x023D0500
        r.service_bytes=struct.pack("<IHH4I",0x53444F57,2,24,r.state,0x023C2401,0x023C2501,0x023C2601)
        r.discovery_bytes=b"D"*32
        r.blob,r.image,r.receipt=current_package()
        self.put(r.discovery,r.discovery_bytes)
        self.put(r.unload,r.unload_bytes)
        self.put(r.service,r.service_bytes)
        self.put(0x023C8148,b"\x40")
        self.put(r.state,struct.pack("<4I2HIB3s",self.entry-64,len(r.blob),self.entry,self.field,3,3,21,1,bytes(3)))
        self.put(self.entry,relocated_image(r.image,r.receipt,self.entry))
        self.put(0x023BA170+12,struct.pack("<I",3))
        self.put(0x023BA170+44,struct.pack("<HH",0,3))
        self.put(self.wild+0xE0,struct.pack("<II",self.field,self.runtime))
        self.put(self.runtime+RUNTIME_CONDITIONS,struct.pack("<II",self.conditions,self.q))
        self.put(self.conditions+FRAME_WORLD,self.full+struct.pack("<I",100))
        self.put(self.conditions+FRAME_VALID-3,struct.pack("<HBB",(1<<1)|(1<<7),0,1))
        self.put(self.conditions+BINDINGS+60,self.full)
        prefix=bytearray(QUERY_PREFIX_SIZE)
        prefix[4:16]=prefix[192:204]=self.full
        struct.pack_into("<H",prefix,148,3)
        prefix[178]=10
        struct.pack_into("<I",prefix,300,self.q+QUERY_STATE_SIZE)
        struct.pack_into("<HH",prefix,364,2,QUERY_STATE_SIZE)
        prefix[375]=1;prefix[327]=1
        self.put(self.q,prefix)
        self.put(self.q+QUERY_OWNER,self.full)
        self.put(self.q+QUERY_VALID,b"\x01\x01\0\0")
        self.put(self.call,struct.pack("<8I",self.world,0x023B0000,0x023B0100,0,0,4,1,0))
        world=bytearray(84)
        struct.pack_into("<HHII",world,0,3,84,self.field,self.wild);world[52]=1
        struct.pack_into("<I",world,28,0x023B1000)
        self.put(0x023B1000,struct.pack("<HH",3,84))
        self.put(self.q+(QUERY_ENTRY_ACTIVE&~3),bytes(4))
        self.put(self.world,world);self.put(self.output,bytes(140))
        self.put(r.discovery,r.discovery_bytes)
        self.packaged_code=lambda address,size:self.read(address,size)
        if ENTRY_LAYOUT:
            r.native_ops_address=0x023B1200;r.native_spawn_address=0x023D0802;r.native_spawn_bytes=b"S"*1390
            r.remove_address=0x023D1000;r.remove_bytes=b"R"*32
            native_ops=bytearray(ENTRY_LAYOUT["ControlOps"])
            struct.pack_into("<IHH",native_ops,0,0x4E454F57,1,len(native_ops))
            for name,offset in ENTRY_LAYOUT.items():
                if name.startswith("ControlOps_") and name not in ("ControlOps_magic","ControlOps_version","ControlOps_size"):
                    struct.pack_into("<I",native_ops,offset,0x02006001+offset*4)
            struct.pack_into("<I",native_ops,ENTRY_LAYOUT["ControlOps_spawn"],r.native_spawn_address|1)
            struct.pack_into("<I",native_ops,ENTRY_LAYOUT["ControlOps_remove"],r.remove_address|1)
            r.native_ops_bytes=bytes(native_ops);self.put(r.native_ops_address,r.native_ops_bytes)
            self.put(r.remove_address,r.remove_bytes);self.put(r.native_spawn_address,r.native_spawn_bytes)
            self.entry_request()
            packet=bytearray(self.read(self.call,32));packet[29]=0;self.put(self.call,packet)
            r._tap(r.remove_address,r._remove_before,r._remove_after,None)
        r._tap(r.discovery,r._discover_before,r._discover_after,None)
        r._tap(r.unload,r._unload_before,r._unload_after,None)

    def entry_request(self, operation=2, actor=None, *, command=None, call=None, world=None, slot=1, serial=91,
                      status=0, queued=0):
        o=ENTRY_LAYOUT; command=command or self.command; call=call or self.call; world=world or self.world
        raw=bytearray(o["Command"])
        struct.pack_into("<HH",raw,0,1,o["Request"])
        for name,value in (("serial",serial),("fieldEpoch",3),("mapGeneration",3)):
            struct.pack_into("<I",raw,o["Request_"+name],value)
        raw[o["Request_slot"]],raw[o["Request_operation"]]=slot,operation
        encoded=actor if actor is not None else (bytes(12) if operation==0 else self.full)
        raw[o["Request_actor"]:o["Request_actor"]+12]=encoded
        receipt=command+o["Command"]
        struct.pack_into("<I",raw,o["Command_receipt"],receipt)
        self.put(command,raw)
        out=bytearray(o["Receipt"]);struct.pack_into("<HHI",out,0,1,o["Receipt"],serial)
        if operation==1:out[o["Receipt_actor"]:o["Receipt_actor"]+12]=encoded
        out[o["Receipt_status"]],out[o["Receipt_queued"]]=status,queued
        self.put(receipt,out)
        w=bytearray(self.read(self.world,84));w[52]=slot;self.put(world,w)
        packet=bytearray(self.read(self.call,32));struct.pack_into("<I",packet,0,world)
        struct.pack_into("<I",packet,8,command);packet[29]=1;self.put(call,packet)
        return command,receipt

    def native_control(self, operation, slot=1, query_operation=0):
        o=ENTRY_LAYOUT
        command=bytearray(o["Command"]);struct.pack_into("<I",command,o["Command_nativeControl"],self.control)
        self.put(self.command,command)
        c=bytearray(o["Control"]);struct.pack_into("<HH",c,0,1,o["Control"])
        for name,value in (("ops",self.reader.native_ops_address),("state",self.wild),("field",self.field),
                           ("profile",0x023B0000),("prepared",self.runtime+o["Runtime_queuedSpawn"]),
                           ("object",self.object)):
            struct.pack_into("<I",c,o["Control_"+name],value)
        c[o["Control_operation"]],c[o["Control_slot"]]=operation,slot
        c[o["Control_queryOperation"]]=query_operation
        if operation in (7,9) or (operation == 8 and query_operation == 1):
            for name in ("profile","primitives","prepared","object","receipt","startCommitSequence"):
                struct.pack_into("<I",c,o["Control_"+name],0)
        self.put(self.control,c)
        packet=bytearray(self.read(self.call,32));struct.pack_into("<I",packet,8,self.command);packet[29]=1
        if operation in (7,9) or (operation == 8 and query_operation == 1):struct.pack_into("<I",packet,4,0)
        self.put(self.call,packet);self.put(self.world+52,bytes((slot,)))
        return self.control

    def control_return(self, value=None, status=1):
        if value is None:
            value=3 if self.read(self.control+ENTRY_LAYOUT["Control_operation"],1)==b"\7" else 0
        self.put(self.control+ENTRY_LAYOUT["Control_value"],struct.pack("<I",value))
        self.returned(status)

    def publish_actor(self, slot=0, generation=2):
        from tools.overworld.devtools_query_observer import handle
        raw=struct.pack("<6H",slot,generation,3,3,1,0)
        self.handles[slot]=handle(raw);self.active_slots.add(slot)
        self.put(self.conditions+BINDINGS+slot*60,raw)
        return raw

    def constructor_event(self, *, slot=0, move=False, **changes):
        actor=self.handles[slot];self.observer.sequence+=1
        event=dict(observation="spawn-prepared",sequence=self.observer.sequence,slot=slot,
            preparedPointer=self.runtime+ENTRY_LAYOUT["Runtime_queuedSpawn"],fieldPointer=self.field,
            statePointer=self.wild,returnValue=1,entryNativeCycle=90,returnNativeCycle=90,setupMode="prepared",
            worldContext=dict(fieldPointer=self.field,statePointer=self.wild,fieldEpoch=3,mapGeneration=3),
            publicSubject=dict(status="observed-public-subject",handle=actor),startup=dict(locomotion=3 if move else 0))
        event.update(changes);self.observer.pending.append(event)
        return event

    def nested_entry(self, *, operation, slot=0, actor=None, status=1, queued=0):
        child_call,child_world,child_command=0x027E1400,0x027E1500,0x027E1600
        self.entry_request(operation,actor,command=child_command,call=child_call,world=child_world,
                           slot=slot,status=status,queued=queued)
        self.regs.sp-=64;self.regs.lr=0x02005001
        self.regs.r0,self.regs.r1=child_call,self.output;self.invoke(self.entry+TICK_OFFSET)
        self.returned(status);self.regs.sp+=64;self.regs.lr=0x02004001

    def put(self,address,data):self.memory.update({address+i:byte for i,byte in enumerate(data)})
    def read(self,address,size):
        self.reads.append((address,size))
        return bytes(self.memory.get(address+i,0) for i in range(size))
    def invoke(self,address):self.callbacks[address&~1](address&~1,2)
    def discover(self):
        self.invoke(self.reader.discovery);self.regs.r0=self.entry;self.invoke(self.regs.lr)
    def start(self):
        self.regs.r0=self.call;self.regs.r1=self.output
        self.invoke(self.entry+TICK_OFFSET)
    def returned(self,status):self.regs.r0=status;self.invoke(self.regs.lr)
    def capture(self,status=0):self.discover();self.start();self.returned(status);return self.rows[-1]["data"]


class QueryObserverTests(unittest.TestCase):
    def test_native_entry_controls_are_distinct_and_metadata_cannot_replace_actor(self):
        for operation,slot in ((0,1),(2,1),(2,7),(8,1)):
            with self.subTest(operation=operation,slot=slot):
                f=Fixture();f.native_control(operation,slot)
                if slot==7:f.put(f.conditions+BINDINGS+slot*60,f.other)
                row=f.capture(1)
                self.assertIsNone(f.hooks.error)
                self.assertEqual(f.rows[-1]["label"],ENTRY_CONTROL_LABEL)
                self.assertEqual(row["entry"],dict(kind="native-control",operation=operation,value=0))
                self.assertFalse(row["cargoOwnerCredited"])
                self.assertEqual(row["subject"],f.handles[slot])
                f=Fixture();f.native_control(operation,slot)
                if slot==7:f.put(f.conditions+BINDINGS+slot*60,f.other)
                f.discover();f.start();f.publish_actor(slot,generation=3);f.returned(1)
                self.assertIn("Subject changed",f.hooks.error)
                self.assertEqual(f.rows,[])

    def test_native_entry_control_typed_input_and_return_faults_reject(self):
        for fault in ("version","size","reserved","bool","unknown","wrong-field","wrong-state",
                      "wrong-slot","wrong-ops","changed-profile","changed-op","changed-call","follower-arm"):
            with self.subTest(fault=fault):
                f=Fixture();f.native_control(2)
                at=lambda name:f.control+ENTRY_LAYOUT["Control_"+name]
                if fault=="version":f.put(at("version"),struct.pack("<H",2))
                if fault=="size":f.put(at("size"),struct.pack("<H",48))
                if fault=="reserved":f.put(at("reserved"),b"\1")
                if fault=="bool":f.put(at("accepted"),b"\2")
                if fault=="unknown":f.put(at("operation"),b"\12")
                if fault=="wrong-field":f.put(at("field"),struct.pack("<I",f.field+4))
                if fault=="wrong-state":f.put(at("state"),struct.pack("<I",f.wild+4))
                if fault=="wrong-slot":f.put(at("slot"),b"\2")
                if fault=="wrong-ops":f.put(f.reader.native_ops_address+8,bytes(4))
                if fault=="follower-arm":
                    f.native_control(0,7);f.put(f.conditions+BINDINGS+420,f.other)
                f.discover();f.start()
                if fault in ("changed-profile","changed-op","changed-call") and f.hooks.error is None:
                    if fault=="changed-profile":f.put(at("profile"),struct.pack("<I",0x023B0004))
                    if fault=="changed-op":f.put(at("operation"),b"\10")
                    if fault=="changed-call":f.put(f.call+8,struct.pack("<I",f.command+4))
                    f.returned(1)
                self.assertIsNotNone(f.hooks.error)
                self.assertEqual(f.rows,[])

    def test_follower_guide_and_update_are_observed_only_as_unchanged_native_rejections(self):
        for operation in (3,4):
            for value in (0,91):
                with self.subTest(operation=operation,value=value):
                    f=Fixture();f.native_control(operation,7)
                    f.put(f.conditions+BINDINGS+420,f.other)
                    f.put(f.control+ENTRY_LAYOUT["Control_value"],struct.pack("<I",value))
                    row=f.capture(3)
                    self.assertIsNone(f.hooks.error)
                    self.assertEqual(f.rows[-1]["label"],ENTRY_CONTROL_LABEL)
                    self.assertEqual(row["entry"],dict(kind="native-control",operation=operation,
                                                      value=value,rejectedFollower=True))
                    self.assertEqual(row["status"],"INVALID")
                    self.assertEqual(row["subject"],f.handles[7])
                    self.assertEqual(row["before"]["subject"],row["after"]["subject"])
                    self.assertIsNone(row["admission"]);self.assertIsNone(row["retirement"])
                    self.assertFalse(row["cargoOwnerCredited"]);self.assertFalse(row["acceptedProof"])
                    self.assertEqual(row["resultHex"],bytes(140).hex())
                    self.assertLessEqual(row["readBytes"]["entry"],READ_BUDGET)
                    self.assertLessEqual(row["readBytes"]["returned"],READ_BUDGET)

    def test_rejected_follower_control_requires_invalid_unchanged_input_and_same_actor(self):
        for operation in (3,4):
            for fault in ("pending","reachable","unreachable","limit","value","profile",
                          "operation","command","ops","actor","missing-actor","result"):
                with self.subTest(operation=operation,fault=fault):
                    f=Fixture();f.native_control(operation,7)
                    f.put(f.conditions+BINDINGS+420,f.other)
                    f.discover();f.start();self.assertIsNone(f.hooks.error)
                    status={"pending":0,"reachable":1,"unreachable":2,"limit":4}.get(fault,3)
                    if fault=="value":f.put(f.control+ENTRY_LAYOUT["Control_value"],struct.pack("<I",1))
                    if fault=="profile":f.put(f.control+ENTRY_LAYOUT["Control_profile"],struct.pack("<I",0x023B0004))
                    if fault=="operation":f.put(f.control+ENTRY_LAYOUT["Control_operation"],b"\2")
                    if fault=="command":f.put(f.command,b"\1")
                    if fault=="ops":f.put(f.reader.native_ops_address+8,bytes(4))
                    if fault=="actor":f.publish_actor(7,generation=3)
                    if fault=="missing-actor":f.active_slots.remove(7)
                    if fault=="result":f.put(f.output,b"\1")
                    f.returned(status)
                    self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])
                    if fault in ("pending","reachable","unreachable","limit","value"):
                        self.assertIn("rejected follower Entry control changed or was not INVALID",f.hooks.error)
                    if fault=="actor":self.assertIn("Tick Subject changed",f.hooks.error)
                    if fault=="missing-actor":self.assertIn("current full Subject differs",f.hooks.error)
                    if fault=="result":
                        self.assertIn("rejected follower Entry control acquired work or changed its result",f.hooks.error)

    def _commit_fixture(self):
        f=Fixture();f.native_control(7,0)
        f.put(f.conditions+BINDINGS,bytes(12))
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSlotPlusOne"],b"\1")
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSerial"],struct.pack("<I",91))
        f.discover();f.start();self.assertIsNone(f.hooks.error)
        return f

    def test_commit_accepts_only_same_queue_full_constructor_and_move_adopt(self):
        for move in (False,True):
            with self.subTest(move=move):
                f=self._commit_fixture();new=f.publish_actor(0)
                if move:
                    f.observer.spawn_contexts.append(dict(slot=0,preparedPointer=f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawn"],
                                                        fieldPointer=f.field,statePointer=f.wild))
                    f.nested_entry(operation=1,slot=0,actor=new)
                    self.assertIsNone(f.hooks.error);f.observer.spawn_contexts.clear()
                f.constructor_event(move=move);f.control_return()
                self.assertIsNone(f.hooks.error)
                row=f.rows[-1]["data"]
                self.assertEqual(row["admission"]["actor"],f.handles[0])
                self.assertEqual(row["admission"]["serial"],91)
                self.assertEqual(row["admission"]["moveAdopted"],move)
                self.assertFalse(row["cargoOwnerCredited"])
                self.assertLessEqual(max(row["readBytes"].values()),READ_BUDGET)

    def test_commit_missing_stale_or_reused_constructor_cannot_replace_subject(self):
        for fault in ("missing","wrong-slot","wrong-pointer","wrong-field","wrong-serial","wrong-handle",
                      "old-sequence","late-return","wrong-setup","duplicate","missing-adopt","wrong-hook","changed-body"):
            with self.subTest(fault=fault):
                f=self._commit_fixture();f.publish_actor(0)
                event=f.constructor_event()
                if fault=="missing":f.observer.pending.clear()
                if fault=="wrong-slot":event["slot"]=2
                if fault=="wrong-pointer":event["preparedPointer"]+=4
                if fault=="wrong-field":event["fieldPointer"]+=4
                if fault=="wrong-serial":f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSerial"],struct.pack("<I",92))
                if fault=="wrong-handle":event["publicSubject"]["handle"]={**f.handles[0],"generation":3}
                if fault=="old-sequence":event["sequence"]=0
                if fault=="late-return":event["returnNativeCycle"]=91
                if fault=="wrong-setup":event["setupMode"]="normal"
                if fault=="duplicate":f.observer.pending.append(dict(event))
                if fault=="missing-adopt":event["startup"]["locomotion"]=3
                if fault=="wrong-hook":f.observer.calls["spawn-prepared"]["address"]+=2
                if fault=="changed-body":f.put(f.reader.native_spawn_address+1390-1,b"!")
                f.control_return()
                self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def test_commit_global_control_keeps_subject_and_records_other_queued_admission(self):
        f=Fixture();f.native_control(7,0)
        f.put(f.conditions+BINDINGS,bytes(12))
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSlotPlusOne"],b"\2")
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSerial"],struct.pack("<I",91))
        f.discover();f.start();f.publish_actor(1,generation=3);f.constructor_event(slot=1);f.control_return()
        self.assertIsNone(f.hooks.error)
        row=f.rows[-1]["data"]
        self.assertEqual(row["slot"],0);self.assertIsNone(row["subject"])
        self.assertEqual(row["admission"]["slot"],1)

    def test_cold_refill_absent_conditions_are_not_prepared_and_never_credit_cargo(self):
        for operation, subtype in ((7,0),(8,1),(9,0),(9,1)):
            for query in (0, "present"):
                with self.subTest(operation=operation, subtype=subtype, query=query):
                    f=Fixture();f.native_control(operation,0,subtype)
                    f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<II",0,f.q if query else 0))
                    f.discover();f.start();self.assertIsNone(f.hooks.error)
                    f.control_return(value=0)
                    self.assertIsNone(f.hooks.error)
                    row=f.rows[-1]["data"]
                    for view in (row["before"],row["after"]):
                        self.assertEqual(view["conditionState"],"not-prepared")
                        self.assertEqual(view["conditions"],0)
                        self.assertFalse(view["frameValid"])
                        self.assertIsNone(view["worldFrame"])
                        self.assertIsNone(view["worldSubject"])
                        self.assertIsNone(view["subject"])
                        if query:self.assertFalse(view["workspace"]["cargoOwnerCredited"])
                    self.assertFalse(row["cargoOwnerCredited"]);self.assertFalse(row["acceptedProof"])
                    self.assertFalse(any(f.conditions <= at < f.conditions+3100 for at,size in f.reads))
                    self.assertLessEqual(max(row["readBytes"].values()),READ_BUDGET)

    def test_cold_commit_can_prepare_conditions_only_with_exact_constructor_admission(self):
        f=Fixture();f.native_control(7,0)
        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",0))
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSlotPlusOne"],b"\1")
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSerial"],struct.pack("<I",91))
        f.discover();f.start();self.assertIsNone(f.hooks.error)
        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",f.conditions))
        f.publish_actor(0);f.constructor_event();f.control_return(value=3)
        self.assertIsNone(f.hooks.error)
        row=f.rows[-1]["data"]
        self.assertIsNone(row["before"]["subject"])
        self.assertEqual(row["after"]["subject"],row["admission"]["actor"])
        self.assertEqual(row["admission"]["serial"],91)
        self.assertFalse(row["cargoOwnerCredited"])

    def test_absent_conditions_still_reject_cargo_ordinary_entry_and_other_native_controls(self):
        cases=[("cargo",None,0),("ordinary-entry",None,0)]
        cases += [("native",op,0) for op in range(7)] + [("native",8,0)]
        for mode,operation,subtype in cases:
            with self.subTest(mode=mode, operation=operation):
                f=Fixture()
                if mode=="ordinary-entry":f.entry_request(operation=2,slot=1)
                elif mode=="native":f.native_control(operation,0,subtype)
                f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",0))
                f.discover();f.start()
                self.assertIn("conditions are absent",f.hooks.error)
                self.assertEqual(f.rows,[])

    def test_cold_refill_keeps_pointer_owner_control_and_active_subject_faults(self):
        for operation,subtype in ((7,0),(8,1),(9,0)):
            for fault in ("unaligned","low","past-end","field","runtime","ops","profile",
                          "wrong-control","world","image","active","active-on-return",
                          "changed-control","invalid-on-return"):
                with self.subTest(operation=operation,fault=fault):
                    f=Fixture();f.native_control(operation,0,subtype)
                    f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",0))
                    if fault in ("unaligned","low","past-end"):
                        value={"unaligned":f.conditions+1,"low":4,"past-end":0x02400000-3096}[fault]
                        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",value))
                    if fault=="field":f.put(f.control+ENTRY_LAYOUT["Control_field"],struct.pack("<I",f.field+4))
                    if fault=="runtime":f.put(f.wild+0xE4,struct.pack("<I",4))
                    if fault=="ops":f.put(f.reader.native_ops_address+8,bytes(4))
                    if fault=="profile":f.put(f.control+ENTRY_LAYOUT["Control_profile"],struct.pack("<I",4))
                    if fault=="wrong-control":f.put(f.control+ENTRY_LAYOUT["Control_operation"],b"\2")
                    if fault=="world":f.put(f.world+4,struct.pack("<I",f.field+4))
                    if fault=="active":f.active_slots.add(0)
                    f.discover()
                    if fault=="image":f.put(f.entry+120,b"!")
                    f.start()
                    if f.hooks.error is None:
                        if fault=="active-on-return":f.active_slots.add(0)
                        if fault=="changed-control":f.put(f.control+ENTRY_LAYOUT["Control_operation"],b"\2")
                        if fault=="invalid-on-return":f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",4))
                        f.control_return(value=0)
                    self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def _cold_follower_finalize_fixture(self):
        f=Fixture();f.native_control(2,7);f.active_slots.remove(7)
        for name in ("profile","object"):
            f.put(f.control+ENTRY_LAYOUT["Control_"+name],struct.pack("<I",0))
        f.put(f.call+4,struct.pack("<I",0))
        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",0))
        return f

    def _cold_prepare_fixture(self):
        f=Fixture();f.entry_request(operation=0,slot=0)
        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",0))
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSlotPlusOne"],b"\1")
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_queuedSpawnSerial"],struct.pack("<I",91))
        return f

    def test_cold_follower_finalize_and_queued_prepare_keep_absence_explicit(self):
        for mode in ("follower","prepare"):
            for query in (0,"present"):
                with self.subTest(mode=mode,query=query):
                    f=self._cold_follower_finalize_fixture() if mode=="follower" else self._cold_prepare_fixture()
                    f.put(f.runtime+RUNTIME_QUERY,struct.pack("<I",f.q if query else 0))
                    f.discover();f.start();self.assertIsNone(f.hooks.error)
                    if mode=="follower":f.control_return(value=1)
                    else:f.returned(0)
                    self.assertIsNone(f.hooks.error)
                    row=f.rows[-1]["data"]
                    for view in (row["before"],row["after"]):
                        self.assertEqual(view["conditionState"],"not-prepared")
                        self.assertIsNone(view["subject"]);self.assertIsNone(view["worldFrame"])
                        self.assertFalse(view["frameValid"])
                    self.assertFalse(row["cargoOwnerCredited"]);self.assertFalse(row["acceptedProof"])
                    self.assertIsNone(row["admission"])
                    self.assertLessEqual(max(row["readBytes"].values()),READ_BUDGET)

    def test_cold_follower_finalize_requires_exact_setup_packet_and_inactive_slot(self):
        for fault in ("no-prepared","unaligned-prepared","outside-prepared","object","profile",
                      "terrain","subtype","slot","active","active-return","changed-owner"):
            with self.subTest(fault=fault):
                f=self._cold_follower_finalize_fixture();o=ENTRY_LAYOUT
                if fault in ("no-prepared","unaligned-prepared","outside-prepared"):
                    value={"no-prepared":0,"unaligned-prepared":f.runtime+1,"outside-prepared":0x02800000-256}[fault]
                    f.put(f.control+o["Control_prepared"],struct.pack("<I",value))
                if fault in ("object","profile"):f.put(f.control+o["Control_"+fault],struct.pack("<I",4))
                if fault=="profile":f.put(f.call+4,struct.pack("<I",4))
                if fault=="terrain":f.put(f.control+o["Control_terrain"],b"\1")
                if fault=="subtype":f.put(f.control+o["Control_queryOperation"],b"\1")
                if fault=="slot":f.put(f.control+o["Control_slot"],b"\0");f.put(f.world+52,b"\0")
                if fault=="active":f.active_slots.add(7)
                f.discover();f.start()
                if f.hooks.error is None:
                    if fault=="active-return":f.active_slots.add(7)
                    if fault=="changed-owner":f.put(f.control+o["Control_field"],struct.pack("<I",f.field+4))
                    f.control_return(value=1)
                self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def _unbound_follower_finalize_fixture(self, *, retained=False):
        f=self._cold_follower_finalize_fixture()
        f.put(f.wild+0xE0,struct.pack("<I",0))
        if retained:
            f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",f.conditions))
            f.put(f.conditions+FRAME_VALID,b"\0")
            f.put(f.conditions+BINDINGS+7*60,bytes(60))
            prepared=bytearray(88);prepared[:12]=f.other
            struct.pack_into("<BBHHH",prepared,80,3,0,3,155,1)
            f.put(f.conditions+7*88,prepared)
            f.put(f.conditions+2332+7*4,bytes(4))
        return f

    def test_unbound_cold_follower_finalize_is_absence_only_at_both_boundaries(self):
        for retained in (False,True):
            for query in (0,"present"):
                for value in (0,1):
                    with self.subTest(retained=retained,query=query,value=value):
                        f=self._unbound_follower_finalize_fixture(retained=retained)
                        f.put(f.runtime+RUNTIME_QUERY,struct.pack("<I",f.q if query else 0))
                        f.discover();f.start();self.assertIsNone(f.hooks.error)
                        f.control_return(value=value);self.assertIsNone(f.hooks.error)
                        row=f.rows[-1]["data"]
                        for view in (row["before"],row["after"]):
                            self.assertEqual(view["wildFieldState"],"unbound")
                            self.assertEqual(view["conditionState"],"not-prepared")
                            self.assertEqual(view["runtime"],f.runtime)
                            self.assertEqual(view["conditions"],f.conditions if retained else 0)
                            self.assertIsNone(view["subject"]);self.assertIsNone(view["worldSubject"])
                            self.assertIsNone(view["worldFrame"]);self.assertFalse(view["frameValid"])
                            if view["workspace"]:
                                self.assertFalse(view["workspace"]["cargoOwnerCredited"])
                        self.assertIsNone(row["subject"]);self.assertIsNone(row["admission"])
                        self.assertIsNone(row["retirement"])
                        self.assertFalse(row["cargoOwnerCredited"]);self.assertFalse(row["acceptedProof"])
                        self.assertLessEqual(max(row["readBytes"].values()),READ_BUDGET)

    def test_unbound_follower_metadata_keeps_exact_owners_packets_and_return(self):
        faults=("foreign-field","no-runtime","unaligned-runtime","outside-runtime",
                "retained-pointer","retained-frame","retained-binding","retained-states",
                "retained-valid","retained-capacity","retained-active-mask","active","no-prepared",
                "guide","update","ordinary-cargo","world-field","control-field","code",
                "active-return","field-return","field-zero-return","runtime-return",
                "conditions-return","retained-conditions-return","query-return","pending-return","value-return")
        for fault in faults:
            with self.subTest(fault=fault):
                f=self._unbound_follower_finalize_fixture(retained=fault.startswith("retained-"));o=ENTRY_LAYOUT
                f.put(f.runtime+RUNTIME_QUERY,bytes(4))
                if fault=="foreign-field":f.put(f.wild+0xE0,struct.pack("<I",f.field+4))
                if fault=="no-runtime":f.put(f.wild+0xE4,bytes(4))
                if fault=="unaligned-runtime":f.put(f.wild+0xE4,struct.pack("<I",f.runtime+1))
                if fault=="outside-runtime":f.put(f.wild+0xE4,struct.pack("<I",0x02400000))
                if fault=="retained-pointer":f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",f.conditions+1))
                if fault=="retained-frame":f.put(f.conditions+FRAME_VALID,b"\1")
                if fault=="retained-binding":f.put(f.conditions+BINDINGS+7*60+59,b"\1")
                if fault=="retained-states":f.put(f.conditions+7*88+12,struct.pack("<I",f.conditions+1024))
                if fault=="retained-valid":f.put(f.conditions+7*88+81,b"\1")
                if fault=="retained-capacity":f.put(f.conditions+7*88+82,struct.pack("<H",33))
                if fault=="retained-active-mask":f.put(f.conditions+2332+7*4,struct.pack("<I",1))
                if fault=="active":f.active_slots.add(7)
                if fault=="no-prepared":f.put(f.control+o["Control_prepared"],bytes(4))
                if fault in ("guide","update"):
                    f.put(f.control+o["Control_operation"],bytes((3 if fault=="guide" else 4,)))
                if fault=="ordinary-cargo":f.put(f.call+29,b"\0")
                if fault=="world-field":f.put(f.world+4,struct.pack("<I",f.field+4))
                if fault=="control-field":f.put(f.control+o["Control_field"],struct.pack("<I",f.field+4))
                if fault=="code":f.put(f.entry+CARGO_WILD_START,b"X")
                if fault=="field-zero-return":f.put(f.wild+0xE0,struct.pack("<I",f.field))
                f.discover()
                if f.hooks.error is None:f.start()
                if f.hooks.error is None:
                    if fault=="active-return":f.active_slots.add(7)
                    if fault=="field-return":f.put(f.wild+0xE0,struct.pack("<I",f.field))
                    if fault=="field-zero-return":f.put(f.wild+0xE0,bytes(4))
                    if fault=="runtime-return":
                        other=f.runtime+0x4000;f.put(other,f.read(f.runtime,2856))
                        f.put(f.wild+0xE4,struct.pack("<I",other))
                    if fault=="conditions-return":
                        cleared=self._unbound_follower_finalize_fixture(retained=True)
                        f.put(f.conditions,cleared.read(cleared.conditions,3100))
                        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",f.conditions))
                    if fault=="retained-conditions-return":f.put(f.runtime+RUNTIME_CONDITIONS,bytes(4))
                    if fault=="query-return":f.put(f.runtime+RUNTIME_QUERY,struct.pack("<I",f.q))
                    f.control_return(value=2 if fault=="value-return" else 1,
                                     status=0 if fault=="pending-return" else 1)
                self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def test_cold_prepare_keeps_exact_serial_world_and_queue_ownership(self):
        for fault in ("missing-queue","wrong-slot","wrong-serial","zero-serial","epoch","generation",
                      "actor","active","world","ops","workspace","changed-command","changed-queue"):
            with self.subTest(fault=fault):
                f=self._cold_prepare_fixture();o=ENTRY_LAYOUT
                if fault in ("missing-queue","wrong-slot"):
                    f.put(f.runtime+o["Runtime_queuedSpawnSlotPlusOne"],b"\0" if fault=="missing-queue" else b"\2")
                if fault=="wrong-serial":f.put(f.runtime+o["Runtime_queuedSpawnSerial"],struct.pack("<I",92))
                if fault=="zero-serial":f.put(f.command+o["Request_serial"],bytes(4))
                if fault=="epoch":f.put(f.command+o["Request_fieldEpoch"],struct.pack("<I",4))
                if fault=="generation":f.put(f.command+o["Request_mapGeneration"],struct.pack("<I",4))
                if fault=="actor":f.put(f.command+o["Request_actor"],f.full)
                if fault=="active":f.active_slots.add(0)
                if fault=="world":f.put(f.world+4,struct.pack("<I",f.field+4))
                if fault=="ops":f.put(0x023B1000,struct.pack("<HH",2,76))
                if fault=="workspace":f.put(f.q+364,bytes(4))
                f.discover();f.start()
                if f.hooks.error is None:
                    if fault=="changed-command":f.put(f.command+o["Request_serial"],struct.pack("<I",92))
                    if fault=="changed-queue":f.put(f.runtime+o["Runtime_queuedSpawnSerial"],struct.pack("<I",92))
                    f.returned(0)
                self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def test_absence_error_names_authenticated_call_and_return_boundary(self):
        f=Fixture();f.native_control(2,0);f.put(f.runtime+RUNTIME_CONDITIONS,bytes(4))
        f.discover();f.start()
        for value in ("boundary=tick-entry","slot=0","routeOperation=1","nativeOperation=2","queryOperation=0"):
            self.assertIn(value,f.hooks.error)
        f=self._cold_prepare_fixture();f.discover();f.start();self.assertIsNone(f.hooks.error)
        f.put(f.runtime+RUNTIME_CONDITIONS,struct.pack("<I",4));f.returned(0)
        for value in ("boundary=tick-return","slot=0","routeOperation=1","nativeOperation=None","entryOperation=0"):
            self.assertIn(value,f.hooks.error)

    def test_refill_control_values_keep_exact_shape_and_do_not_credit_cargo(self):
        for operation,values in ((9,(0,15,60,120,180,240,300,360)),(7,(0,))):
            for value in values:
                with self.subTest(operation=operation,value=value):
                    f=Fixture();f.native_control(operation,0);f.put(f.conditions+BINDINGS,bytes(12))
                    f.discover();f.start();f.control_return(value=value)
                    self.assertIsNone(f.hooks.error)
                    row=f.rows[-1]["data"]
                    self.assertEqual(row["entry"]["refillDelay"],value)
                    self.assertFalse(row["cargoOwnerCredited"]);self.assertFalse(row["acceptedProof"])
        for outcome,value in ((1,1),(2,2),(2,2|(15<<8))):
            f=self._commit_fixture();f.control_return(value=value)
            self.assertIsNone(f.hooks.error)
            self.assertEqual(f.rows[-1]["data"]["entry"]["outcome"],outcome)

    def test_ordinary_refill_spawn_subtype_preserves_queue_and_never_credits_cargo(self):
        for value in (0, 1, 2, 15<<8, 60<<8, 120<<8, 180<<8, 240<<8, 300<<8, 360<<8):
            with self.subTest(value=value):
                f=Fixture();f.native_control(8,0,1);f.put(f.conditions+BINDINGS,bytes(12))
                f.discover();f.start();self.assertIsNone(f.hooks.error)
                f.control_return(value=value)
                self.assertIsNone(f.hooks.error)
                row=f.rows[-1]["data"]
                self.assertEqual(row["entry"],dict(kind="native-control",operation=8,value=value,
                    queryOperation=1,prepareResult=value&255,refillDelay=value>>8))
                self.assertIsNone(row["admission"])
                self.assertFalse(row["cargoOwnerCredited"]);self.assertFalse(row["acceptedProof"])
                self.assertLessEqual(max(row["readBytes"].values()),READ_BUDGET)
        # Direct Spawn keeps its original nonzero pointers and chosen slot.
        f=Fixture();f.native_control(8,1,0);row=f.capture(1)
        self.assertIsNone(f.hooks.error)
        self.assertEqual(row["entry"],dict(kind="native-control",operation=8,value=0))

    def test_ordinary_refill_spawn_subtype_and_outputs_reject_copied_faults(self):
        for fault in ("slot","terrain","profile","primitives","prepared","object","receipt",
                      "startCommitSequence","value","accepted","usableIdle","subtype",
                      "bad-delay","upper-bit","ready-delay","pending-delay","unknown-result",
                      "pending-return","changed-field","changed-subtype","actor-replacement"):
            with self.subTest(fault=fault):
                f=Fixture();f.native_control(8,0,1);f.put(f.conditions+BINDINGS,bytes(12));o=ENTRY_LAYOUT
                if fault in ("profile","primitives","prepared","object","receipt","startCommitSequence","value"):
                    f.put(f.control+o["Control_"+fault],struct.pack("<I",4))
                elif fault in ("slot","terrain","accepted","usableIdle"):
                    f.put(f.control+o["Control_"+fault],b"\2")
                elif fault=="subtype":f.put(f.control+o["Control_queryOperation"],b"\2")
                f.discover();f.start()
                if f.hooks.error is None:
                    value={"bad-delay":16<<8,"upper-bit":1<<24,"ready-delay":1|(15<<8),
                           "pending-delay":2|(15<<8),"unknown-result":3}.get(fault,0)
                    if fault=="changed-field":f.put(f.control+o["Control_field"],struct.pack("<I",f.field+4))
                    if fault=="changed-subtype":f.put(f.control+o["Control_queryOperation"],b"\0")
                    if fault=="actor-replacement":f.publish_actor(0)
                    f.control_return(value=value,status=0 if fault=="pending-return" else 1)
                self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])
        # Direct Spawn cannot use an unknown subtype either.
        f=Fixture();f.native_control(8,1,2);f.discover();f.start()
        self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def test_refill_control_input_output_and_owned_constructor_faults_reject(self):
        for operation in (7,9):
            for fault in ("slot","terrain","profile","primitives","prepared","object","receipt",
                          "startCommitSequence","value","accepted","usableIdle","queryOperation",
                          "bad-delay","upper-bit","pending-return","changed-field"):
                with self.subTest(operation=operation,fault=fault):
                    f=Fixture();f.native_control(operation,0);f.put(f.conditions+BINDINGS,bytes(12))
                    o=ENTRY_LAYOUT;name=fault
                    if fault in ("profile","primitives","prepared","object","receipt","startCommitSequence","value"):
                        f.put(f.control+o["Control_"+name],struct.pack("<I",4))
                    elif fault in ("slot","terrain","accepted","usableIdle","queryOperation"):
                        f.put(f.control+o["Control_"+name],bytes((2,)))
                    f.discover();f.start()
                    if f.hooks.error is None:
                        value=16 if operation==9 else 2|(16<<8)
                        if fault=="upper-bit":value=0x1000000
                        if fault=="changed-field":f.put(f.control+o["Control_field"],struct.pack("<I",f.field+4));value=0
                        f.control_return(value=value,status=0 if fault=="pending-return" else 1)
                    self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])
        for value in (0,1,2):
            f=self._commit_fixture();f.publish_actor(0);f.constructor_event();f.control_return(value=value)
            self.assertIn("outcome and constructor",f.hooks.error)
        f=self._commit_fixture();f.control_return(value=3)
        self.assertIn("outcome and constructor",f.hooks.error)

    def _removal_fixture(self):
        f=Fixture();f.native_control(3);base=f.rt.actor_state
        f.source_cleared=False
        f.rt.actor_state=lambda emu,slot:dict(base(emu,slot),role="WILD",presentationAttached=True,
            species=74,subjectIdentity=1,authorityGeneration=1,engineAnchorGeneration=1,
            presentationGeneration=1,inputOwnership=0,motionKind="NONE",motionPhase="IDLE")
        f.rt.field_map_id=lambda emu:33
        def source(emu,slot):
            row=dict(active=1,object=f.object,species=74,personality=1,encounter_generation=1,
                     object_id=0xE0+slot,map_id=33,form=0,level=3)
            return dict(row,active=0,object=0,species=0,personality=0,map_id=1,form=0,level=0) \
                if f.source_cleared else row
        f.rt.wild_spawn=source
        f.rt.live_wild_object_identity=lambda emu,slot:dict(pointer=f.object,in_manager=True,active=True,
            object_manager=0x02231000,current_manager=0x02231000,object_id=0xE0+slot,
            object_map_id=33,script_id=2074)
        f.put(f.object,struct.pack("<I",1))
        f.put(f.runtime+ENTRY_LAYOUT["Runtime_entryRouteSerial"]+4,struct.pack("<I",91))
        f.discover();f.start();f.nested_entry(operation=2,slot=1,actor=f.full,status=2,queued=2)
        return f

    def _enter_removal(self,f):
        f.regs.sp-=64;f.regs.lr=0x02006001
        f.regs.r0,f.regs.r1,f.regs.r2=f.wild,f.field,1
        f.invoke(f.reader.remove_address)
        if f.hooks.error is None:
            f.nested_entry(operation=3,slot=1,actor=f.full,status=1)
            # Native ResetSlotState retires the path/serial and condition binding;
            # DeleteMapObject clears the object. Actor synchronization is later.
            f.source_cleared=True;f.put(f.object,bytes(4))
            f.put(f.conditions+BINDINGS+60,bytes(12))
            f.put(f.runtime+ENTRY_LAYOUT["Runtime_entryRouteSerial"]+4,bytes(4))
            f.regs.lr=0x02006001;f.returned(0)
            if f.hooks.error is None:
                f.regs.sp+=64;f.regs.lr=0x02004001;f.control_return(value=1)
        return f

    def _detach_sample(self,f,actor_frame=101,cycle=92,**changes):
        f.rt.EXECUTED_FRAME_COUNT=cycle
        f.observer._clock=lambda:dict(actorFrame=actor_frame,nativeCycle=cycle)
        row=dict(frame=1092,actorFrame=actor_frame,nativeCycle=cycle,
                 observationBoundary="main-task-queue-completion",
                 context=dict(fieldEpoch=3,mapGeneration=3,mapId=33),actors=[])
        row.update(changes);return row

    def test_guided_removal_waits_for_exact_later_completed_actor_detach(self):
        f=self._enter_removal(self._removal_fixture())
        self.assertIsNone(f.hooks.error)
        row=f.rows[-1]["data"]
        self.assertIsNone(row["retirement"]);self.assertTrue(row["removal"]["actorDetached"] is False)
        self.assertEqual(row["removal"]["serial"],91);self.assertFalse(row["cargoOwnerCredited"])
        self.assertIn(1,f.reader.pending_detaches);self.assertIn(1,f.active_slots)
        self.assertFalse(any(r["label"]=="entry-actor-detached" for r in f.rows))
        f.reader.completed_snapshot(self._detach_sample(f,100,90,
            actors=[f.rt.actor_state(f.emu,1)]))
        self.assertIn(1,f.reader.pending_detaches)
        f.active_slots.remove(1)
        f.reader.completed_snapshot(self._detach_sample(f))
        self.assertEqual(f.reader.pending_detaches,{})
        self.assertEqual(f.rows[-1]["label"],"entry-actor-detached")
        self.assertEqual(f.rows[-1]["data"]["actor"],f.handles[1])
        self.assertTrue(f.rows[-1]["data"]["actorDetached"])
        self.assertLessEqual(f.rows[-1]["data"]["readBytes"],READ_BUDGET)

    def test_guided_removal_source_delete_and_entry_retire_faults_reject(self):
        for fault in ("no-result","wrong-result","wrong-slot","wrong-object","stale-handle",
                      "no-retire","source-live","deleted-live","serial","binding","wrong-guide",
                      "zero-map","wrong-map"):
            with self.subTest(fault=fault):
                f=self._removal_fixture()
                if fault=="no-result":f.reader.contexts[-1]["data"].pop("guideRetirement")
                if fault=="wrong-result":f.reader.contexts[-1]["data"]["guideRetirement"]["status"]=4
                f.regs.sp-=64;f.regs.lr=0x02006001
                f.regs.r0,f.regs.r1,f.regs.r2=f.wild,f.field,2 if fault=="wrong-slot" else 1
                if fault=="wrong-object":f.rt.live_wild_object_identity=lambda emu,slot:dict(pointer=f.object+4)
                if fault=="stale-handle":f.handles[1]={**f.handles[1],"generation":3}
                if fault in ("zero-map","wrong-map"):
                    source=f.rt.wild_spawn
                    f.rt.wild_spawn=lambda emu,slot:dict(source(emu,slot),
                        map_id=(0 if fault=="zero-map" else 34)) if f.source_cleared else source(emu,slot)
                f.invoke(f.reader.remove_address)
                if f.hooks.error is None:
                    if fault!="no-retire":f.nested_entry(operation=3,slot=1,actor=f.full,status=1)
                    f.source_cleared=fault!="source-live";f.put(f.object,struct.pack("<I",1 if fault=="deleted-live" else 0))
                    f.put(f.conditions+BINDINGS+60,f.full if fault=="binding" else bytes(12))
                    f.put(f.runtime+ENTRY_LAYOUT["Runtime_entryRouteSerial"]+4,struct.pack("<I",91 if fault=="serial" else 0))
                    f.regs.lr=0x02006001;f.returned(0)
                    if f.hooks.error is None:
                        f.regs.sp+=64;f.regs.lr=0x02004001;f.control_return(value=0 if fault=="wrong-guide" else 1)
                self.assertIsNotNone(f.hooks.error)
                self.assertFalse(any(r["label"]=="entry-actor-detached" for r in f.rows))

    def test_pending_detach_world_full_identity_reactivation_and_clock_faults_reject(self):
        faults=("handle","pid","species","role","source-reactivated","object-reactivated","field",
                "epoch","map","serial","binding","runtime","not-completed","backward-clock",
                "active-after-sync","active-row","not-idle","input-owner")
        for fault in faults:
            with self.subTest(fault=fault):
                f=self._enter_removal(self._removal_fixture());self.assertIsNone(f.hooks.error)
                f.active_slots.remove(1);sample=self._detach_sample(f)
                if fault=="handle":f.handles[1]={**f.handles[1],"generation":3}
                if fault in ("pid","species","role","not-idle","input-owner"):
                    original=f.rt.actor_state
                    key,value={"pid":("subjectIdentity",2),"species":("species",75),"role":("role","FOLLOWER"),
                               "not-idle":("motionPhase","ACTIVE"),"input-owner":("inputOwnership",1)}[fault]
                    f.rt.actor_state=lambda emu,slot:dict(original(emu,slot),**{key:value})
                if fault=="source-reactivated":f.source_cleared=False
                if fault=="object-reactivated":f.put(f.object,struct.pack("<I",1))
                if fault=="field":f.field_pointer=lambda:f.field+4
                if fault=="epoch":f.put(f.reader.state+16,struct.pack("<H",4))
                if fault=="map":sample["context"]["mapId"]=34
                if fault=="serial":f.put(f.runtime+ENTRY_LAYOUT["Runtime_entryRouteSerial"]+4,struct.pack("<I",92))
                if fault=="binding":f.put(f.conditions+BINDINGS+60,f.full)
                if fault=="runtime":f.put(f.wild+0xE4,struct.pack("<I",f.runtime+4))
                if fault=="not-completed":sample["observationBoundary"]="paused-native-cycle-end"
                if fault=="backward-clock":sample["nativeCycle"]=89
                if fault=="active-after-sync":f.active_slots.add(1)
                if fault=="active-row":sample["actors"]=[dict(handle=f.handles[1])]
                with self.assertRaises(NativeObservationError):f.reader.completed_snapshot(sample)
                self.assertFalse(any(r["label"]=="entry-actor-detached" for r in f.rows))

    def test_completed_snapshot_dispatches_query_without_a_new_hook(self):
        f=Fixture();seen=[]
        f.observer.query=SimpleNamespace(completed_snapshot=lambda sample:seen.append(sample))
        f.observer._pool_fly_terrain_snapshot=lambda sample:None;f.observer.spawn_height_trace=None
        sample=dict(frame=1092);f.observer.completed_snapshot(sample)
        self.assertEqual(seen,[sample])

    def _readonly_loaded_query_fixture(self):
        from tools.overworld.devtools_field_cleanup import symbol
        f=Fixture();f.rt.REPO=ROOT;f.native_observation=None;f._throw_interactions_window=False
        selector=ROOT/"build/overworld_follower_selector_overlay_linked.o"
        data=selector.read_bytes()
        for name,kind,size in (("gOverworldQueryCodeAddonServiceEntry",1,24),
                              ("gOverworldBehaviorConditionServiceEntry",1,24),
                              ("OverworldQueryCodeAddon_ResolverCall",2,32)):
            address=symbol(data,name,kind)[0]
            from tools.overworld.devtools_runtime import _elf_code
            f.put(address,_elf_code(selector,address,size))
        flag=symbol((ROOT/"build/field_linked.o").read_bytes(),
                    "gOverworldFollowerSelectorStateStorage",1,expected_size=1)[0]
        f.put(flag,b"\x40")
        return f,flag

    def test_readonly_query_owner_needs_no_window_and_rechecks_full_current_lease(self):
        from tools.overworld.devtools_query_observer import authenticate_loaded_query_functions
        from tools.overworld.devtools_runtime import ENTRY_SPAWN_QUERY_OWNERS
        elf=(PACKAGE_DIRECTORY/"image.elf").read_bytes()
        for fault in (None,"phase","member","field","reserved","epoch","map-generation",
                      "selector","unavailable","prefix","tail","named-owner"):
            with self.subTest(fault=fault):
                f,flag=self._readonly_loaded_query_fixture();before=dict(f.callbacks)
                owner=authenticate_loaded_query_functions(f,elf,f.reader.blob,f.reader.blob,ENTRY_SPAWN_QUERY_OWNERS)
                self.assertEqual(owner["entry"],f.entry);self.assertEqual(before,f.callbacks)
                self.assertIsNone(f.native_observation);self.assertFalse(f._throw_interactions_window)
                if fault is None:continue
                if fault=="phase":f.put(f.reader.state+24,b"\0")
                elif fault=="member":f.put(f.reader.state+20,struct.pack("<I",22))
                elif fault=="field":f.put(f.reader.state+12,struct.pack("<I",f.field+4))
                elif fault=="reserved":f.put(f.reader.state+25,b"\1")
                elif fault=="epoch":f.put(f.rt.ACTOR_DESCRIPTOR["state"]["address"]+12,struct.pack("<H",4))
                elif fault=="map-generation":f.put(f.rt.ACTOR_DESCRIPTOR["state"]["address"]+46,struct.pack("<H",4))
                elif fault=="selector":f.put(flag,b"\0")
                elif fault=="unavailable":f._field_actor_availability=lambda _:dict(authenticated=True,reason="transition")
                elif fault=="prefix":f.put(f.entry+120,b"!")
                elif fault=="tail":f.put(f.entry+len(f.reader.image)-1,b"!")
                elif fault=="named-owner":f.put(f.entry+0xDD0C,b"!")
                with self.assertRaises((NativeObservationError,ValueError)):
                    authenticate_loaded_query_functions(f,elf,f.reader.blob,f.reader.blob,ENTRY_SPAWN_QUERY_OWNERS)

    def test_readonly_query_typed_functions_and_package_stay_exact(self):
        from tools.overworld.devtools_query_observer import authenticate_loaded_query_functions
        from tools.overworld.devtools_runtime import ENTRY_SPAWN_QUERY_OWNERS
        elf=(PACKAGE_DIRECTORY/"image.elf").read_bytes()
        for fault in ("name","address","extent","digest","package"):
            with self.subTest(fault=fault):
                f,_=self._readonly_loaded_query_fixture();owners=dict(ENTRY_SPAWN_QUERY_OWNERS)
                name=next(iter(owners));address,size,digest=owners.pop(name)
                if fault=="name":name="NativeQueryEntry"
                elif fault=="address":address+=2
                elif fault=="extent":size-=2
                elif fault=="digest":digest="0"*64
                owners[name]=(address,size,digest)
                member=f.reader.blob[:-1] if fault=="package" else f.reader.blob
                with self.assertRaises(NativeObservationError):
                    authenticate_loaded_query_functions(f,elf,f.reader.blob,member,owners)

    def test_native_entry_owner_bodies_callbacks_and_package_remain_exact(self):
        import hashlib
        import tools.overworld.devtools_query_observer as module
        from scripts.verify_pokemon_move_history_capture import elf_bytes_at
        wild=WILD_ELF
        data=wild.read_bytes();read=lambda at,size:elf_bytes_at(wild,at,size)
        owners=module.native_entry_bindings(data,read,read)
        self.assertEqual({k:(v[0],len(v[1])) for k,v in owners.items()},
                         {k:v[:2] for k,v in module.ENTRY_NATIVE_OWNERS.items()})
        for key in ("ops","remove","spawn"):
            address,body=owners[key]
            def bad(at,size,address=address):
                raw=bytearray(read(at,size))
                if at==address:raw[-1]^=1
                return bytes(raw)
            with self.assertRaises(NativeObservationError):module.native_entry_bindings(data,read,bad)
        # An equal copied Ops mutation cannot redirect either named callback.
        for field in ("remove","spawn"):
            address,body=owners["ops"];changed=bytearray(body)
            struct.pack_into("<I",changed,ENTRY_LAYOUT["ControlOps_"+field],0x023D0101)
            pins={**module.ENTRY_NATIVE_OWNERS,"ops":(address,len(changed),hashlib.sha256(changed).hexdigest())}
            copy=lambda at,size:bytes(changed) if at==address else read(at,size)
            with patch.object(module,"ENTRY_NATIVE_OWNERS",pins):
                with self.assertRaisesRegex(NativeObservationError,"typed Ops/callbacks"):
                    module.native_entry_bindings(data,copy,copy)

    def test_entry_preactor_is_separate_and_cannot_credit_a_cargo_owner(self):
        f=Fixture();f.entry_request(operation=0);f.put(f.call+28,bytes((4,1,0,0)))
        f.put(f.conditions+BINDINGS+60,bytes(12))
        f.rt.actor_state=lambda emu,slot:dict(active=False,handle=None)
        f.put(f.q+QUERY_OWNER,bytes(12));f.put(f.q+QUERY_VALID,bytes(4))
        active=bytearray(4);active[QUERY_ENTRY_ACTIVE&3]=1
        f.put(f.q+(QUERY_ENTRY_ACTIVE&~3),active)
        row=f.capture()
        self.assertEqual(f.rows[-1]["label"],ENTRY_LABEL)
        self.assertEqual(row["boundary"],"native-entry-route-tick-return")
        self.assertEqual(row["routeOperation"],1)
        self.assertIsNone(row["subject"])
        self.assertFalse(row["cargoOwnerCredited"])
        self.assertFalse(row["after"]["workspace"]["cargoOwnerCredited"])
        self.assertTrue(row["after"]["workspace"]["entryActive"])
        self.assertTrue(all(n<=READ_BUDGET for n in row["readBytes"].values()))

    def test_entry_mode_preserves_identity_and_operation_guards(self):
        for fault in ("unknown-op","reserved","changed-op","active-without-handle","stale-handle","wrong-ops","wrong-world"):
            with self.subTest(fault=fault):
                f=Fixture();f.put(f.call+28,bytes((4,1,0,0)))
                if fault=="unknown-op":f.put(f.call+28,bytes((4,2,0,0)))
                if fault=="reserved":f.put(f.call+28,bytes((4,1,1,0)))
                if fault=="active-without-handle":f.put(f.conditions+BINDINGS+60,bytes(12))
                if fault=="stale-handle":f.put(f.conditions+BINDINGS+60,struct.pack("<6H",1,3,3,3,1,0))
                if fault=="wrong-ops":f.put(0x023B1000,struct.pack("<HH",2,76))
                if fault=="wrong-world":f.put(f.world,struct.pack("<HH",2,76))
                f.discover();f.start()
                if fault=="changed-op" and f.hooks.error is None:
                    f.put(f.call+28,bytes((4,0,0,0)));f.returned(0)
                self.assertIsNotNone(f.hooks.error)
                self.assertEqual(f.rows,[])

    def test_unload_rejects_an_in_flight_entry_call_too(self):
        f=Fixture();f.put(f.call+28,bytes((4,1,0,0)));f.discover();f.start()
        self.assertEqual(f.reader.contexts[-1]["label"],ENTRY_LABEL)
        f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
        self.assertIn("in-flight Tick",f.hooks.error)
        self.assertIsNotNone(f.reader.loaded)


    def test_current_actor_publication_owner_extent_and_package_controls(self):
        from scripts.verify_overworld_query_code_addon import actor_evaluation_contract
        from scripts.verify_overworld_field_capsule import frame_reader_contract, FRAME_ADDR, FRAME_SIZE
        from scripts.verify_pokemon_move_history_capture import elf_helper_bindings, elf_bytes_at, thumb_bl_target
        actor = ROOT / "build/overworld_actor_system_overlay_linked.o"
        names = ("OverworldBehaviorConditionAdapter_EvaluateActor",
                 "OverworldBehaviorConditionAdapter_BuildFrame")
        bindings = elf_helper_bindings(actor, names)
        binding, frame = (bindings[name] for name in names)
        body = elf_bytes_at(actor, 0x023B65C0, 880)
        actor_evaluation_contract(binding, frame, body, body)
        frame_body = elf_bytes_at(actor, FRAME_ADDR, FRAME_SIZE)
        frame_reader_contract(frame, frame_body, frame_body)
        for bad in (None, (frame[0], 436, *frame[2:]),
                    (frame[0] & ~1, *frame[1:]),
                    (frame[0], frame[1], "OBJECT", frame[3]),
                    (frame[0], frame[1], "FUNC", "ABS"),
                    (frame[0], frame[1], "FUNC", "UND")):
            with self.assertRaisesRegex(ValueError, "Frame reader mode/extent/owner"):
                frame_reader_contract(bad, frame_body, frame_body)
            with self.assertRaisesRegex(ValueError, "Actor frame reader owner"):
                actor_evaluation_contract(binding, bad, body, body)
        for offset in (0, 0x20, 0xA0, 0xBA, 0x100, 0x128, 0x13A, FRAME_SIZE - 1):
            changed = bytearray(frame_body); changed[offset] ^= 1
            with self.assertRaisesRegex(ValueError, "exact native body"):
                frame_reader_contract(frame, bytes(changed), bytes(changed))
            with self.assertRaisesRegex(ValueError, "linked/package bytes"):
                frame_reader_contract(frame, frame_body, bytes(changed))
        with self.assertRaisesRegex(ValueError, "native extent"):
            frame_reader_contract(frame, frame_body[:-4], frame_body[:-4])
        for bad in ((binding[0], 872, "FUNC", binding[3]),
                    (binding[0], 884, "FUNC", binding[3]),
                    (binding[0] + 2, binding[1], "FUNC", binding[3]),
                    (binding[0] & ~1, binding[1], "FUNC", binding[3]),
                    (binding[0], binding[1], "OBJECT", binding[3]),
                    (binding[0], binding[1], "FUNC", "ABS"),
                    (binding[0], binding[1], "FUNC", "UND")):
            with self.assertRaisesRegex(ValueError, "Actor evaluation owner"):
                actor_evaluation_contract(bad, frame, body, body)
        with self.assertRaisesRegex(ValueError, "Actor frame reader owner"):
            actor_evaluation_contract(binding,
                (frame[0] + 4, *frame[1:]), body, body)
        for offset in (0, binding[1] - 1, binding[1] - 2, 879):
            changed = bytearray(body); changed[offset] ^= 1
            with self.assertRaisesRegex(ValueError, "linked/package bytes"):
                actor_evaluation_contract(binding, frame, body, bytes(changed))
        with self.assertRaisesRegex(ValueError, "linked/package bytes"):
            actor_evaluation_contract(binding, frame, body[:-1], body[:-1])
        # Equal copies still must retain native owner/packet and callback152
        # admission, not merely the function's address and byte count.
        for offset, reason in ((0xA4, "current owner/packet gate"),
                               (0xB8, "current owner/packet gate"),
                               (0x330, "current owner/packet gate"),
                               (0x338, "current owner/packet gate"),
                               (0x33C, "current owner/packet gate"),
                               (0x112, "callback152 dispatch"),
                               (0x21C, "callback152 dispatch"),
                               (0x84, "prior current Frame call")):
            changed = bytearray(body); changed[offset] ^= 1
            with self.assertRaisesRegex(ValueError, reason):
                actor_evaluation_contract(binding, frame, bytes(changed), bytes(changed))
        # Exact native body, with both sides changed equally, still must make
        # precisely one direct call to the current publication mask owner.
        sites = []
        for offset in range(0, binding[1] - 3, 2):
            first, second = struct.unpack_from("<2H", body, offset)
            if first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800:
                if thumb_bl_target(body, 0x023B65C0, 0x023B65C0 + offset) == 0x023C2FCC:
                    sites.append(offset)
        self.assertEqual(len(sites), 1)
        changed = bytearray(body); changed[sites[0]:sites[0]+4] = bytes(4)
        with self.assertRaisesRegex(ValueError, "exact publication mask once"):
            actor_evaluation_contract(binding, frame, bytes(changed), bytes(changed))

    def test_retirement_discovery_exact_fifth_context(self):
        faults=(None,"guide-op","retire-op","route-op","serial","owner","field","state","slot",
                "actor","parent","object","terminal","address","label","body","lease","sixth")
        for fault in faults:
            with self.subTest(fault=fault):
                f=self._removal_fixture()
                f.regs.sp-=64;f.regs.lr=0x02006001;f.regs.r0,f.regs.r1,f.regs.r2=f.wild,f.field,1
                f.invoke(f.reader.remove_address);self.assertIsNone(f.hooks.error)
                # ResetSlotState calls a second native packet, then NativeQueryEntry
                # borrows another ordinary RETIRE packet; neither replaces the outer.
                o=ENTRY_LAYOUT;child_call,child_world,child_command,child_control=0x027E1400,0x027E1500,0x027E1A00,0x027E1B00
                c=bytearray(f.read(f.control,o["Control"]));c[o["Control_operation"]]=6
                for name in ("profile","primitives","prepared","object","receipt","startCommitSequence","value"):
                    struct.pack_into("<I",c,o["Control_"+name],0)
                f.put(child_control,c);command=bytearray(o["Command"])
                struct.pack_into("<I",command,o["Command_nativeControl"],child_control);f.put(child_command,command)
                call=bytearray(f.read(f.call,32));struct.pack_into("<3I",call,0,child_world,0,child_command)
                f.put(child_call,call);f.put(child_world,f.read(f.world,84))
                f.regs.sp-=64;f.regs.lr=0x02007001;f.regs.r0,f.regs.r1=child_call,f.output
                f.invoke(f.entry+TICK_OFFSET);self.assertIsNone(f.hooks.error)
                ordinary_call,ordinary_world,ordinary_command=0x027E2300,0x027E2400,0x027E2100
                f.entry_request(3,f.full,command=ordinary_command,call=ordinary_call,world=ordinary_world,
                                slot=1,status=1)
                f.regs.sp-=64;f.regs.lr=0x02008001;f.regs.r0,f.regs.r1=ordinary_call,f.output
                f.invoke(f.entry+TICK_OFFSET);self.assertIsNone(f.hooks.error)
                self.assertEqual(len(f.reader.contexts),4)
                guide,removal,retire,request=f.reader.contexts
                if fault=="guide-op":guide["data"]["entry"]["nativeControl"]["operation"]=4
                if fault=="retire-op":retire["data"]["entry"]["nativeControl"]["operation"]=4
                if fault=="route-op":request["data"]["entry"]["request"]["operation"]=2
                if fault=="serial":request["data"]["entry"]["request"]["serial"]+=1
                if fault=="owner":request["data"]["owner"]="wrong"
                if fault in ("field","state","slot"):request["data"][fault]+=1
                if fault=="actor":request["data"]["entry"]["request"]["actor"]={**f.handles[1],"generation":3}
                if fault=="parent":removal["data"]["parent"]=dict(guide["data"])
                if fault=="object":removal["data"]["object"]+=4
                if fault=="terminal":guide["data"]["guideRetirement"]["queued"]=0
                if fault=="address":retire["address"]=retire.get("address",0)+4
                if fault=="label":request["label"]=LABEL
                if fault=="body":f.packaged_code=lambda address,size:bytes(size)
                f.regs.sp-=64;f.regs.lr=0x02009001;f.invoke(f.reader.discovery)
                if fault is None or fault in ("lease","sixth"):
                    self.assertIsNone(f.hooks.error);self.assertEqual(len(f.reader.contexts),5)
                    if fault=="lease":f.put(f.reader.state+12,struct.pack("<I",f.field+4))
                    if fault=="sixth":
                        f.regs.sp-=4;f.invoke(f.reader.discovery)
                    else:
                        f.regs.r0=f.entry;f.invoke(f.regs.lr)
                    if fault is None:
                        self.assertIsNone(f.hooks.error);self.assertEqual(len(f.reader.contexts),4)
                        f.regs.sp+=64;f.regs.lr=0x02008001;f.returned(1)
                        f.regs.sp+=64;f.regs.lr=0x02007001;f.returned(1)
                        f.source_cleared=True;f.put(f.object,bytes(4));f.put(f.conditions+BINDINGS+60,bytes(12))
                        f.put(f.runtime+ENTRY_LAYOUT["Runtime_entryRouteSerial"]+4,bytes(4))
                        f.regs.sp+=64;f.regs.lr=0x02006001;f.returned(0)
                        f.regs.sp+=64;f.regs.lr=0x02004001;f.control_return(value=1)
                        self.assertIsNone(f.hooks.error);self.assertEqual(f.reader.contexts,[])
                        self.assertEqual(f.reader.count,4)
                        self.assertEqual(len(f.rows),4)
                        self.assertIsNone(f.rows[-1]["data"]["retirement"])
                        self.assertEqual(f.rows[-1]["data"]["removal"]["actor"],f.handles[1])
                        self.assertIn(1,f.reader.pending_detaches)
                        self.assertTrue(all(not row["data"]["cargoOwnerCredited"] for row in f.rows))
                if fault is not None:self.assertIsNotNone(f.hooks.error)

    def test_same_native_cycle_limit_counts_started_receipts_and_retains_depth_cap(self):
        f=Fixture();f.discover()
        for _ in range(254):f.start();f.returned(0)
        for depth in range(2):
            f.regs.sp=0x027E3000-depth*4;f.start()
        self.assertIsNone(f.hooks.error)
        self.assertEqual((f.reader.count,len(f.reader.contexts),len(f.rows)),(256,2,254))
        # Discovery is not a labelled receipt and must still authenticate at the limit.
        f.regs.sp-=4;f.discover();self.assertIsNone(f.hooks.error);self.assertEqual(f.reader.count,256)
        f.regs.sp-=4;f.start()
        self.assertIn("receipt/depth cap",f.hooks.error)
        self.assertEqual(f.reader.count,256)
        f=Fixture();f.discover()
        for depth in range(4):f.regs.sp=0x027E3000-depth*4;f.start()
        self.assertIsNone(f.hooks.error);self.assertEqual(len(f.reader.contexts),4)
        f.regs.sp-=4;f.start()
        self.assertIn("receipt/depth cap",f.hooks.error)
        self.assertEqual((f.reader.count,len(f.reader.contexts)),(4,4))

    def test_next_native_cycle_resets_entry_budget_and_return_observes_monotonic_clock(self):
        f=Fixture();f.discover()
        for _ in range(256):f.start();f.returned(0)
        f.rt.EXECUTED_FRAME_COUNT+=1;f.start();f.returned(0)
        self.assertIsNone(f.hooks.error)
        self.assertEqual((f.reader.count_cycle,f.reader.count,len(f.rows)),(91,1,257))
        f.start();f.rt.EXECUTED_FRAME_COUNT+=1;f.returned(0)
        self.assertEqual((f.reader.count_cycle,f.reader.count),(92,0))
        f.start();f.returned(0)
        self.assertEqual(f.reader.count,1)
        self.assertEqual(f.rows[-2]["context"]["entry"]["nativeCycle"],91)
        self.assertEqual(f.rows[-2]["context"]["returned"]["nativeCycle"],92)
        f.rt.EXECUTED_FRAME_COUNT-=1;f.start()
        self.assertIn("native cycle moved backwards",f.hooks.error)
        self.assertEqual((f.reader.count_cycle,f.reader.count),(92,1))

    def test_long_window_is_bounded_by_native_cycles_with_constant_actor_frame(self):
        f=Fixture();f.discover()
        for cycle in range(90,190):
            f.rt.EXECUTED_FRAME_COUNT=cycle
            for _ in range(3):
                f.start();self.assertIsNone(f.hooks.error);f.returned(0)
        self.assertIsNone(f.hooks.error);self.assertEqual(len(f.rows),300)
        self.assertEqual((f.reader.count_cycle,f.reader.count),(189,3))
        self.assertEqual({r["context"]["entry"]["actorFrame"] for r in f.rows},{100})
        self.assertTrue(all(r["data"]["readBytes"]["entry"]<=READ_BUDGET and
                            r["data"]["readBytes"]["returned"]<=READ_BUDGET for r in f.rows))

    def test_actor_clock_cannot_reset_budget_and_backwards_return_is_rejected(self):
        f=Fixture();f.discover()
        for _ in range(256):f.start();f.returned(0)
        f.observer._clock=lambda:dict(actorFrame=0,nativeCycle=f.rt.EXECUTED_FRAME_COUNT)
        f.start();self.assertIn("receipt/depth cap",f.hooks.error)
        self.assertEqual((f.reader.count_cycle,f.reader.count,len(f.rows)),(90,256,256))
        f=Fixture();f.discover();f.start()
        f.rt.EXECUTED_FRAME_COUNT-=1;f.returned(0)
        self.assertIn("native cycle moved backwards",f.hooks.error)
        self.assertEqual(f.rows,[])

    def test_current_linked_layout_and_package_seal_reject_other_inputs(self):
        directory=PACKAGE_DIRECTORY
        elf=(directory/"image.elf").read_bytes();blob=(directory/"query.bin").read_bytes()
        current_package()
        selector=(ROOT/"build/overworld_follower_selector_overlay_linked.o").read_bytes()
        address,size,body=native_unload_binding(selector)
        self.assertGreater(size,0);self.assertEqual(len(body),size)
        rows=struct.unpack_from("<I",selector,32)[0]
        count=struct.unpack_from("<H",selector,48)[0]
        sections=[struct.unpack_from("<10I",selector,rows+i*40) for i in range(count)]
        for row in sections:
            if row[1]!=2:continue
            names_row=sections[row[6]]
            names=selector[names_row[4]:names_row[4]+names_row[5]]
            for pos in range(row[4],row[4]+row[5],16):
                label=struct.unpack_from("<I",selector,pos)[0]
                if names[label:].split(b"\0",1)[0]!=b"OverworldQueryCodeAddon_Unload":continue
                changed=bytearray(selector);struct.pack_into("<I",changed,pos+4,address)
                with self.assertRaisesRegex(NativeObservationError,"hosted Thumb"):
                    native_unload_binding(changed)
        for bad_elf,bad_staged,bad_member in ((elf+b"x",blob,blob),(elf,blob+b"x",blob),(elf,blob,blob[:-1])):
            with self.assertRaises(NativeObservationError):sealed_package(bad_elf,bad_staged,bad_member)
        # The mounted-target wrapper moved Cargo by204 bytes; stale seals,
        # callback homes and private layout claims must still reject.
        for key,value,reason in (
                ("ELF_SHA","f1efc8074c32e94095e38bde64396fb147a136564fd088e80249b28458a4c43e","private ARM layout"),
                ("PACKAGE_SHA","d55ab76e61b4e9b0d3def2aa715aeccf23addda5bced52e64bd77459aad9f8cd","ROM member21"),
                ("CARGO_CODE_END",34400,"Cargo code range"),
                ("CARGO_CODE_SHA256","5df31ce3a0055e25aceaa91ff9a7f4f42b5143062d093f8414376c160b5df9a5","private Cargo code"),
                ("TICK_OFFSET",0x4A30,"private CargoWild module seal"),
                ("TICK_OFFSET",0xC258,"typed Cargo callback/layout"),
                ("CARGO_WILD_END",0xD80C,"private CargoWild module seal"),
                ("CARGO_WILD_SHA256","d65a0acb2833f4ae59ec9e98bb154f1fb84f2814a67493e57426a375141009c4","private CargoWild module seal"),
                ("QUERY_SIZE",44940,"native Tick/turn layout"),
                ("FRAME_VALID",FRAME_VALID+1,"native Tick/turn layout")):
            with self.subTest(stale=key), patch("tools.overworld.devtools_query_observer."+key,value):
                with self.assertRaisesRegex(NativeObservationError,reason):
                    sealed_package(elf,blob,blob)

    def test_real_return_is_distinct_from_pending_buffer_and_before_after_are_current(self):
        f=Fixture();f.discover();f.start()
        f.put(f.q+327,b"\0\x01")
        f.put(f.q+148,struct.pack("<H",4));f.put(f.conditions+FRAME_VALID-3,b"\x82\0\0\0")
        f.returned(3)
        row=f.rows[-1]["data"]
        self.assertEqual(row["status"],"INVALID");self.assertEqual(row["resultStatus"],0)
        self.assertTrue(row["before"]["frameValid"]);self.assertFalse(row["after"]["frameValid"])
        self.assertEqual(row["before"]["workspace"]["nodeCount"],3)
        self.assertEqual(row["after"]["workspace"]["nodeCount"],4)
        self.assertEqual(row["before"]["workspace"]["edgeQueries"],1)
        self.assertEqual(row["after"]["workspace"]["goalQueries"],1)
        self.assertTrue(all(n<=READ_BUDGET for n in row["readBytes"].values()))
        self.assertEqual(f.rows[-1]["label"],LABEL)

    def test_current_callback_read_extent_and_overbudget_reject_before_native_read(self):
        f=Fixture();row=f.capture()
        self.assertEqual(len(f.reader.image),68172)
        self.assertEqual(row["readBytes"],dict(entry=CARGO_CODE_END+(CARGO_WILD_END-CARGO_WILD_START)+609,
                         returned=CARGO_CODE_END+(CARGO_WILD_END-CARGO_WILD_START)+661))
        self.assertEqual(READ_BUDGET,0x9000)
        # Full prefix plus entire CargoWild module and measured return
        # metadata must stay below the unchanged 36 KiB cap.
        self.assertEqual(max(row["readBytes"].values()),CARGO_CODE_END+(CARGO_WILD_END-CARGO_WILD_START)+661)
        self.assertEqual(CARGO_PREFIX_CAP,0x8800)
        self.assertLessEqual(CARGO_CODE_END+(CARGO_WILD_END-CARGO_WILD_START)+661,READ_BUDGET)
        f.reader.read_bytes=READ_BUDGET-4;f.reads.clear()
        self.assertEqual(len(f.reader._read(f.output,4)),4)
        self.assertEqual(f.reader.read_bytes,READ_BUDGET)
        before=list(f.reads)
        with self.assertRaisesRegex(NativeObservationError,"callback read budget exceeded"):
            f.reader._read(f.output,1)
        self.assertEqual(f.reads,before)

    def test_initial_full_image_is_chunked_once_then_every_tick_reads_current_cargo(self):
        from tools.overworld.pack_query_code_addon import MAX_IMAGE
        f=Fixture();f.reads.clear();f.discover()
        self.assertIsNone(f.hooks.error)
        image_reads=[(a,n) for a,n in f.reads if f.entry<=a<f.entry+len(f.reader.image)]
        self.assertEqual(image_reads,[(f.entry,READ_BUDGET),(f.entry+READ_BUDGET,len(f.reader.image)-READ_BUDGET)])
        self.assertEqual(f.reader.read_bytes,len(f.reader.image)+37)
        self.assertEqual(INITIAL_READ_BUDGET,MAX_IMAGE+37)
        self.assertTrue(all(n<=READ_BUDGET for _,n in f.reads))
        f.reads.clear();f.start();f.returned(0)
        self.assertIsNone(f.hooks.error)
        image_reads=[(a,n) for a,n in f.reads if f.entry<=a<f.entry+len(f.reader.image)]
        self.assertEqual(image_reads,[(f.entry,CARGO_CODE_END),
            (f.entry+CARGO_WILD_START,CARGO_WILD_END-CARGO_WILD_START)]*2)
        self.assertTrue(all(v<=READ_BUDGET for v in f.rows[-1]["data"]["readBytes"].values()))

    def test_cached_full_identity_cannot_accept_mutated_current_cargo_code_or_abi(self):
        for offset in (0,CARGO_CODE_START,CARGO_CODE_END-1,CARGO_WILD_START,CARGO_WILD_END-1,TICK_OFFSET,CARGO_ABI_OFFSET,112):
            for boundary in ("entry","return","unload"):
                with self.subTest(offset=offset,boundary=boundary):
                    f=Fixture();f.discover();self.assertIsNone(f.hooks.error)
                    if boundary=="return":f.start()
                    old=f.read(f.entry+offset,1);f.put(f.entry+offset,bytes([old[0]^1]))
                    if boundary=="entry":f.start()
                    elif boundary=="return":f.returned(0)
                    else:f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
                    self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])

    def test_current_cargo_range_and_both_read_ceilings_reject_before_overbudget_read(self):
        module="tools.overworld.devtools_query_observer."
        for key,value in (("CARGO_CODE_START",188),("CARGO_CODE_END",CARGO_CODE_END-4),
                          ("CARGO_WILD_START",CARGO_WILD_START+4),("CARGO_WILD_END",CARGO_WILD_END-4),
                          ("CARGO_ABI_OFFSET",104),("CARGO_ABI_SIZE",12)):
            with self.subTest(key=key):
                f=Fixture();f.discover();f.reads.clear()
                with patch(module+key,value):f.start()
                self.assertIn("Cargo code range differs",f.hooks.error)
                self.assertFalse(any(f.entry<=a<f.entry+len(f.reader.image) for a,_ in f.reads))
        f=Fixture();f.discover();f.reader.read_bytes=INITIAL_READ_BUDGET-4
        f.reader.read_limit=INITIAL_READ_BUDGET;f.reads.clear()
        f.reader._read(f.output,4);before=list(f.reads)
        with self.assertRaisesRegex(NativeObservationError,"callback read budget exceeded"):
            f.reader._read(f.output,1)
        self.assertEqual(f.reads,before)
        f.reader.read_bytes=0
        with self.assertRaisesRegex(NativeObservationError,"pointer range differs"):
            f.reader._read(f.output,READ_BUDGET+1)
        self.assertEqual(f.reads,before)

    def test_unseen_active_unload_authenticates_whole_image_before_drain(self):
        for corrupt_tail in (False,True):
            with self.subTest(corrupt_tail=corrupt_tail):
                f=Fixture();f.reads.clear()
                if corrupt_tail:
                    old=f.read(f.entry+len(f.reader.image)-1,1)
                    f.put(f.entry+len(f.reader.image)-1,bytes([old[0]^1]));f.reads.clear()
                f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
                image_reads=[(a,n) for a,n in f.reads if f.entry<=a<f.entry+len(f.reader.image)]
                self.assertEqual(image_reads,[(f.entry,READ_BUDGET),(f.entry+READ_BUDGET,len(f.reader.image)-READ_BUDGET)])
                self.assertEqual(f.reader.read_bytes,len(f.reader.image)+29)
                self.assertEqual(f.hooks.error is not None,corrupt_tail)
                if not corrupt_tail:
                    f.put(f.reader.state,bytes(28));f.regs.r0=0;f.invoke(f.regs.lr)
                    self.assertIsNone(f.hooks.error);self.assertIsNone(f.reader.loaded)

    def test_standing_goal_and_proof_progress_use_existing_sealed_read(self):
        f=Fixture()
        f.put(f.q+288,struct.pack("<hhiHH",586,409,32768,3,0))
        f.put(f.q+236,struct.pack("<hhiHH",587,410,16384,2,0))
        f.put(f.q+256,struct.pack("<I",17))
        f.put(f.q+68,struct.pack("<I",16))
        f.put(f.q+156,struct.pack("<HH",4,2))
        f.put(f.q+172,struct.pack("<H",3))
        f.put(f.q+180,b"\x01")
        f.put(f.q+369,b"\x02")
        f.put(f.q+376,b"\x01\x01")
        row=f.capture()
        self.assertEqual(row["after"]["workspace"]["routeProgress"],dict(
            goal=dict(x=586,y=409,baseY=32768,surfaceId=3,reserved=0),
            cargoPosition=dict(x=587,y=410,baseY=16384,surfaceId=2,reserved=0),
            goalRevision=17,routeGoalRevision=16,goalNode=4,proofNode=2,
            proofLength=3,probeNeeded=1,edgeOwed=2,goalValid=1,goalDirty=1))
        self.assertEqual(sum(address==f.q and size==QUERY_PREFIX_SIZE for address,size in f.reads),2)
        self.assertTrue(all(r["data"]["readBytes"]["returned"]<=READ_BUDGET for r in f.rows))

    def test_different_singleton_owner_and_missing_workspace_are_visible(self):
        f=Fixture();f.put(f.q+QUERY_OWNER,f.other)
        row=f.capture();self.assertEqual(row["after"]["workspace"]["owner"]["slot"],7)
        self.assertTrue(row["after"]["workspace"]["ownerCurrent"])
        f=Fixture();f.put(f.runtime+RUNTIME_QUERY,bytes(4))
        self.assertIsNone(f.capture()["after"]["workspace"])

    def test_saved_compatibility_and_origin_decode_without_more_memory_reads(self):
        f=Fixture()
        f.put(f.q+204,f.other)
        f.put(f.q+216,struct.pack("<4h",544,384,607,447))
        f.put(f.q+224,struct.pack("<hhiHH",585,404,-65536,0xFFFF,0))
        f.put(f.q+248,struct.pack("<4I",0x10203040,0x50607080,11,12))
        f.put(f.q+264,struct.pack("<I",f.q+25000))
        f.put(f.q+280,struct.pack("<H",4))
        f.put(f.q+336,struct.pack("<2I",0x20002,345))
        f.put(f.q+370,bytes((2,3,1,2,1)))
        f.put(f.q+380,b"\1")
        f.discover();f.start()
        f.put(f.q+224,struct.pack("<hhiHH",585,405,-65536,0xFFFF,0))
        f.put(f.q+252,struct.pack("<I",0x50607081))
        f.returned(0)
        row=f.rows[-1]["data"]
        before=row["before"]["workspace"];after=row["after"]["workspace"]
        self.assertEqual(before["compatibility"],dict(cargo=f.handles[7],
            bounds=dict(minX=544,minY=384,maxX=607,maxY=447),
            scopeRevision=0x10203040,movementPolicyRevision=0x50607080,
            edges=f.q+25000,edgeCount=4,requestKey=0x20002,roleMask=1,
            pickupDistance=2,required=1))
        self.assertEqual(before["origin"],dict(x=585,y=404,baseY=-65536,surfaceId=0xFFFF,reserved=0))
        self.assertEqual(after["origin"]["y"],405)
        self.assertEqual(after["compatibility"]["movementPolicyRevision"],0x50607081)
        self.assertEqual({k:v for k,v in before["compatibility"].items() if k!="movementPolicyRevision"},
                         {k:v for k,v in after["compatibility"].items() if k!="movementPolicyRevision"})
        self.assertEqual((before["dynamicRevision"],before["storage"],before["stateFrame"],
            before["candidate"],before["scan"],before["active"]),(12,f.q+QUERY_STATE_SIZE,345,2,3,1))
        self.assertEqual(sum(size for address,size in f.reads if f.q<=address<f.q+QUERY_PREFIX_SIZE),QUERY_PREFIX_SIZE*2)
        self.assertEqual([size for address,size in f.reads if address==f.q],[QUERY_PREFIX_SIZE]*2)

    def test_discovery_adopts_only_authenticated_same_image_rebind(self):
        def owner(f, epoch, generation):
            f.put(f.reader.state+16, struct.pack("<HH", epoch, generation))
            f.put(0x023BA170+12, struct.pack("<I", epoch))
            f.put(0x023BA170+44, struct.pack("<HH", 0, generation))
        for initial, current in (((3, 3), (4, 4)),
                                 ((0xFFFF, 0xFFFF), (1, 1)),
                                 ((3, 3), (3, 4))):
            with self.subTest(initial=initial,current=current):
                f=Fixture(); owner(f, *initial); f.discover()
                taps=len(f.reader.tokens)
                owner(f, *current); f.discover()
                self.assertIsNone(f.hooks.error)
                self.assertEqual((f.reader.loaded["fieldEpoch"],
                                  f.reader.loaded["mapGeneration"]), current)
                self.assertEqual(len(f.reader.tokens), taps)
        for fault in ("skip", "partial", "stale", "zero", "pending", "field", "pointer"):
            with self.subTest(fault=fault):
                f=Fixture(); f.discover(); old=f.reader.loaded
                if fault=="skip": owner(f,5,5)
                if fault=="partial": owner(f,4,3)
                if fault=="stale":
                    f.put(f.reader.state+16, struct.pack("<HH",4,4))
                if fault=="zero": owner(f,0,0)
                if fault=="pending": f.put(f.reader.state+24,b"\x02")
                if fault=="field":
                    f.field+=4; f.put(f.reader.state+12,struct.pack("<I",f.field))
                if fault=="pointer":
                    f.entry+=0x10000
                    f.put(f.reader.state,struct.pack("<4I2HIB3s",f.entry-64,
                        len(f.reader.blob),f.entry,f.field,4,4,21,1,bytes(3)))
                    f.put(f.entry,relocated_image(f.reader.image,f.reader.receipt,f.entry))
                    owner(f,4,4)
                f.discover()
                self.assertIsNotNone(f.hooks.error)
                self.assertIs(f.reader.loaded,old)
        # A paired change DURING one Tick still rejects before returning data.
        f=Fixture(); f.discover(); f.start(); owner(f,4,4); f.returned(0)
        self.assertIsNotNone(f.hooks.error); self.assertEqual(f.rows,[])

    def test_successful_native_unload_empty_retires_old_tap_and_reauthenticates_reload(self):
        f=Fixture();f.discover();old=f.entry;old_token=f.reader.tick_token
        f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
        f.put(f.reader.state,bytes(28));f.regs.r0=0;f.invoke(f.regs.lr)
        self.assertIsNone(f.hooks.error)
        self.assertIsNone(f.reader.loaded);self.assertIsNone(f.reader.tick_token)
        self.assertNotIn(old_token,f.reader.tokens);self.assertNotIn(old_token,f.observer.tokens)
        self.assertNotIn(old+TICK_OFFSET,f.hooks.callbacks)
        f.entry+=0x10000
        f.put(f.reader.state,struct.pack("<4I2HIB3s",f.entry-64,len(f.reader.blob),f.entry,f.field,4,4,21,1,bytes(3)))
        f.put(f.entry,relocated_image(f.reader.image,f.reader.receipt,f.entry))
        f.put(0x023BA170+12,struct.pack("<I",4));f.put(0x023BA170+44,struct.pack("<HH",0,4))
        f.discover()
        self.assertIsNone(f.hooks.error)
        self.assertEqual(f.reader.loaded["entry"],f.entry)
        self.assertEqual(sum(t[0]==(f.entry+TICK_OFFSET) for t in f.reader.tokens),1)
        self.assertNotIn(old+TICK_OFFSET,f.hooks.callbacks)
        f.put(f.conditions+BINDINGS+60,struct.pack("<6H",1,2,4,4,1,0))
        from tools.overworld.devtools_query_observer import handle
        f.handles[1]=handle(struct.pack("<6H",1,2,4,4,1,0))
        f.start();f.returned(0)
        self.assertIsNone(f.hooks.error);self.assertEqual(len(f.rows),1)

    def test_unload_missing_empty_pending_wrong_owner_and_active_tick_do_not_retire(self):
        for fault in ("uncleared", "partial-empty", "pending", "wrong-state", "wrong-field", "image", "unloaded", "body", "active-tick", "unobserved-empty"):
            with self.subTest(fault=fault):
                f=Fixture();f.discover();old=f.reader.loaded;token=f.reader.tick_token
                if fault=="active-tick":f.start()
                if fault=="unobserved-empty":f.put(f.reader.state,bytes(28))
                if fault=="wrong-field":f.put(f.reader.state+12,struct.pack("<I",f.field+4))
                if fault=="image":f.put(f.entry+TICK_OFFSET,b"X")
                if fault=="unloaded":f.put(0x023C8148,b"\0")
                if fault=="body":f.put(f.reader.unload,b"X")
                f.regs.r0=f.reader.state+(4 if fault=="wrong-state" else 0)
                f.invoke(f.reader.unload)
                if f.hooks.error is None:
                    if fault=="partial-empty":f.put(f.reader.state,bytes(24)+b"\1\0\0\0")
                    if fault=="pending":f.put(f.reader.state+24,b"\2")
                    f.regs.r0=5 if fault=="pending" else 0;f.invoke(f.regs.lr)
                self.assertIs(f.reader.loaded,old);self.assertIs(f.reader.tick_token,token)
                self.assertIn(token,f.reader.tokens)
                if fault=="pending":
                    self.assertIsNone(f.hooks.error)
                    f.regs.r0=f.call;f.start()
                self.assertIsNotNone(f.hooks.error)
        f=Fixture();f.discover();old=f.reader.loaded;token=f.reader.tick_token
        f.regs.r0=f.reader.state;f.invoke(f.reader.unload);f.regs.r0=1;f.invoke(f.regs.lr)
        self.assertIsNone(f.hooks.error);self.assertIs(f.reader.loaded,old)
        self.assertIs(f.reader.tick_token,token)
        # A failed drain can be retried; only its final real EMPTY/OK retires.
        f=Fixture();f.discover();f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
        f.put(f.reader.state+24,b"\2");f.regs.r0=5;f.invoke(f.regs.lr)
        f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
        f.put(f.reader.state,bytes(28));f.regs.r0=0;f.invoke(f.regs.lr)
        self.assertIsNone(f.hooks.error);self.assertIsNone(f.reader.loaded)

    def test_current_image_owner_and_full_subject_reject_before_or_after(self):
        for fault in ("image","entry-pointer","field","epoch","generation","unloaded","workspace","subject"):
            with self.subTest(fault=fault):
                f=Fixture();f.discover();f.start()
                if fault=="image":f.put(f.entry+TICK_OFFSET,b"X")
                if fault=="entry-pointer":f.put(f.reader.state+8,struct.pack("<I",f.entry+4))
                if fault=="field":f.put(f.reader.state+12,struct.pack("<I",f.field+4))
                if fault=="epoch":f.put(f.reader.state+16,struct.pack("<H",4))
                if fault=="generation":f.put(f.reader.state+18,struct.pack("<H",4))
                if fault=="unloaded":f.put(0x023C8148,b"\0")
                if fault=="workspace":f.put(f.q+364,struct.pack("<HH",9,QUERY_STATE_SIZE))
                if fault=="subject":f.put(f.conditions+BINDINGS+60,struct.pack("<6H",1,3,3,3,1,0))
                f.returned(0)
                self.assertIsNotNone(f.hooks.error);self.assertEqual(f.rows,[])
        f=Fixture();f.put(f.entry+TICK_OFFSET,b"X");f.discover()
        self.assertIsNotNone(f.hooks.error);self.assertIsNone(f.reader.loaded)

    def test_off_window_and_close_are_read_free_and_return_requires_same_stack(self):
        f=Fixture();f._throw_interactions_window=False;f.reads.clear();f.invoke(f.reader.discovery)
        f.regs.r0=f.reader.state;f.invoke(f.reader.unload)
        self.assertEqual(f.reads,[]);self.assertEqual(f.reader.returns,[])
        f._throw_interactions_window=True;f.discover();f.start();f.regs.sp+=4;f.returned(0)
        self.assertEqual(f.rows,[]);self.assertEqual(len(f.reader.returns),1)
        f.regs.sp-=4;f.returned(0);self.assertEqual(len(f.rows),1)
        f.reader.close();self.assertEqual(f.observer.tokens,[]);self.assertEqual(f.observer.return_tokens,[])

    def test_existing_record_window_only_enables_on_explicit_throw_option(self):
        calls=[]
        def factory(observer):
            calls.append("enabled")
            return SimpleNamespace(close=lambda:calls.append("closed"))
        def session():
            return SimpleNamespace(native_observation=SimpleNamespace(),_record_control=lambda *args:{},
                _close_role_profile_window=lambda:None,prepared=True)
        with patch("tools.overworld.devtools_query_observer.NativeQueryObserver",factory), \
                patch("tools.overworld.devtools_slam_admission_observer.SlamAdmissionObserver",
                      lambda observer:SimpleNamespace(close=lambda:None)):
            s=session();DevtoolsSession.record_start(s);self.assertEqual(calls,[])
            s=session();DevtoolsSession.record_start(s,throw_interactions=True)
            self.assertEqual(calls,["enabled"]);DevtoolsSession.record_stop(s)
            self.assertEqual(calls,["enabled","closed"])


if __name__=="__main__":unittest.main()
