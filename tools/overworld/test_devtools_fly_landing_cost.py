"""Guest-cost observer controls; host receipts are not gameplay proof."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import struct
import unittest
from unittest.mock import patch

from tools.overworld.devtools_observer import NativeObservation
from tools.overworld.devtools_fly_landing_cost import FlyLandingCost, PINS, QUERY_NATIVE
from tools.overworld.devtools_runtime import _elf_code

REPO = Path(__file__).resolve().parents[2]

class FlyLandingCostTests(unittest.TestCase):
    def fixture(self):
        actor = dict(active=True, species=163, form=0, level=2, subjectIdentity=123,
            role="WILD", handle=dict(value=65540,slot=4,generation=1,fieldEpoch=4,mapGeneration=4,encounterGeneration=1),
            motionKind="FLY_IN", motionPhase="COMMIT_PENDING", motionElapsed=144,
            motionDuration=144, origin=dict(x=562,y=404), target=dict(x=562,y=388))
        source = dict(object=0x02220000,personality=123,species=163,form=0,level=2,active=1,
            object_id=220,map_id=67,encounter_generation=1)
        world = dict(statePointer=0x023DF160,fieldPointer=0x02230000,mapId=67,fieldEpoch=4,mapGeneration=4)
        engine = dict(pointer=source['object'], id_lookup=dict(status='complete',pointer_matches=True,eligible_count=1))
        regs = SimpleNamespace(r0=0,r1=world['statePointer'],r2=0,r3=0,lr=0x02001001,sp=0x027E3000)
        memory={}
        def read(addr,n): return bytes(memory.get(addr+i,0) for i in range(n))
        def put(addr,raw): memory.update({addr+i:v for i,v in enumerate(raw)})
        rt=SimpleNamespace(REPO=REPO,WILD_STATE=world['statePointer'],
            actor_state=lambda e,s: deepcopy(actor) if s==4 else {},
            wild_spawn=lambda e,s: deepcopy(source) if s==4 else {},
            live_wild_object_identity=lambda e,s: deepcopy(engine))
        session=SimpleNamespace(rt=rt,emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=regs)),
            prepared=False,completed_frames=3532,read=read,packaged_code=lambda a,n:b'x'*n,rom=str(REPO/'test.nds'))
        obs=SimpleNamespace(session=session,_subject=lambda s: deepcopy(actor) if s==4 else {},
            _world_context=lambda:deepcopy(world),_chain_identity=NativeObservation._chain_identity,
            _live_code=lambda a,b:b)
        reader=object.__new__(FlyLandingCost);reader.observer=obs;reader.session=session
        reader.frame=None;reader.bubbles=[];reader.windows=0;reader.code={k:b'x'*p[3] for k,p in PINS.items()}
        reader.conditions=[];reader.native_pending=[];reader.native_target=None
        from tools.overworld.pack_query_code_addon import package
        from tools.overworld.devtools_query_observer import relocated_image
        blob,receipt=package((REPO/'build/overworld_query_code_addon/image.elf').read_bytes())
        image=blob[64:64+receipt['imageBytes']];entry=0x02270000
        expected=relocated_image(image,receipt,entry)
        raw=struct.pack('<4I2HIB3s',entry-64,len(blob),entry,world['fieldPointer'],4,4,21,1,bytes(3))
        owner=dict(stateAddress=0x023C2308,fieldEpoch=4,mapGeneration=4,entry=entry,rawHex=raw.hex())
        reader.query_blob=blob;reader.query_receipt=receipt;reader.query_image=image
        reader.query_loaded=owner;reader.query_expected=expected
        obs.hooks=SimpleNamespace(add=lambda a,c:a);obs.tokens=[]
        put(owner['stateAddress'],raw);put(entry,expected)
        from tools.overworld.devtools_field_cleanup import symbol
        selector=REPO/'build/overworld_follower_selector_overlay_linked.o'
        flag=symbol((REPO/'build/field_linked.o').read_bytes(),'gOverworldFollowerSelectorStateStorage',1,expected_size=1)[0]
        put(flag,b'\x40')
        rt.ACTOR_DESCRIPTOR=json.loads((REPO/'build/overworld-system.debug.json').read_text())
        actor_state=rt.ACTOR_DESCRIPTOR['state']['address']
        put(actor_state+12,struct.pack('<H',4));put(actor_state+46,struct.pack('<H',4))
        session.field_pointer=lambda:world['fieldPointer']
        session._field_actor_availability=lambda field:dict(authenticated=True,reason=None)
        session.packaged_code=lambda address,size:_elf_code(selector,address,size)
        reader.native_code=image[QUERY_NATIVE[0]:QUERY_NATIVE[0]+QUERY_NATIVE[1]]
        runtime=0x02240000;native=0x02260000
        put(rt.WILD_STATE+0xE0,struct.pack('<2I',world['fieldPointer'],native))
        put(native+0x514,struct.pack('<I',runtime))
        put(runtime+0x6BC,struct.pack('<6HI',4,1,4,4,1,0,3118)+bytes(248-16))
        identity=patch('tools.overworld.devtools_fly_landing_cost.actor_identity_checks',return_value={'valid':True})
        identity.start();self.addCleanup(identity.stop)
        return reader,obs,session,actor,source,engine,world,regs,put

    def condition_call(self,p,o,s,w,r,put,forced=-1,operation=0,binding=0):
        runtime=0x02240000;size=999;blob=0x02250000
        r.r0=runtime;r.r1=s.rt.WILD_STATE;r.r2=w['fieldPointer'];r.r3=blob
        put(r.sp,struct.pack('<11I',size,4,1,0x02251000,0x023CF001,forced & 0xFFFFFFFF,
            0x023CF101,0x023CF201,0x023CF301,0x023CF401,0x027E2D00))
        put(runtime+0x6BC+247,bytes([binding]))
        outer=p.before('condition')
        packet=struct.pack('<10IHH4B I H2B',runtime,s.rt.WILD_STATE,w['fieldPointer'],blob,size,
            0x02251000,0x023CF001,0x023CF101,0x023CF301,forced & 0xFFFFFFFF,
            2,56,4,1,operation,0,0,0,255,0)
        r.r0=0x027E2E00;put(r.r0,packet)
        return outer,packet

    def test_local_query_lease_without_throw_collector_authenticates_full_current_owner(self):
        p,o,s,a,src,eng,w,r,put=self.fixture()
        self.assertFalse(hasattr(o,'query'));self.assertFalse(getattr(s,'_throw_interactions_window',False))
        frame=p.before('frame');self.assertEqual(p.native_target[0],p.query_loaded['entry']+QUERY_NATIVE[0])
        p.after('frame',frame,{'returnValue':0})
        for fault in ('unloaded','phase','member','reserved','size','field','epoch','map','availability','actor-epoch','actor-map','whole-image','service'):
            with self.subTest(fault=fault):
                p,o,s,a,src,eng,w,r,put=self.fixture();owner=p.query_loaded;raw=bytearray.fromhex(owner['rawHex'])
                if fault=='phase':raw[24]=2
                if fault=='member':struct.pack_into('<I',raw,20,20)
                if fault=='reserved':raw[25]=1
                if fault=='size':struct.pack_into('<I',raw,4,len(p.query_blob)-4)
                if fault=='field':struct.pack_into('<I',raw,12,w['fieldPointer']+4)
                if fault=='epoch':struct.pack_into('<H',raw,16,5)
                if fault=='map':struct.pack_into('<H',raw,18,5)
                put(owner['stateAddress'],raw)
                if fault=='unloaded':
                    from tools.overworld.devtools_field_cleanup import symbol
                    flag=symbol((REPO/'build/field_linked.o').read_bytes(),'gOverworldFollowerSelectorStateStorage',1,expected_size=1)[0]
                    put(flag,b'\x00')
                if fault=='availability':s._field_actor_availability=lambda field:dict(authenticated=False,reason='unavailable')
                if fault=='actor-epoch':put(s.rt.ACTOR_DESCRIPTOR['state']['address']+12,struct.pack('<H',5))
                if fault=='actor-map':put(s.rt.ACTOR_DESCRIPTOR['state']['address']+46,struct.pack('<H',5))
                if fault=='whole-image':put(owner['entry']+len(p.query_expected)-1,b'!')
                if fault=='service':s.packaged_code=lambda address,size:bytes(size)
                with self.assertRaises(ValueError):p.before('frame')

    def test_condition_normal_moving_warm_modes_and_nested_native_cost_identity(self):
        for forced,operation,binding,mode in ((-1,0,0,'Normal'),(-3,1,0,'Moving'),(-2,2,1,'Warm')):
            with self.subTest(mode=mode):
                p,o,s,a,src,eng,w,r,put=self.fixture();frame=p.before('frame')
                outer,packet=self.condition_call(p,o,s,w,r,put,forced,operation,binding)
                value=p.native_before();got=p.native_after(value,{'returnValue':0})
                self.assertEqual((got['evaluationMode'],got['operation'],got['forcedOverrideProfileIndex']),
                    (mode,operation,forced))
                self.assertEqual(got['worldBefore']['reservedBinding'],binding)
                self.assertEqual(got['conditionOwner']['subject']['handle'],a['handle'])
                self.assertEqual(got['nativeAddress'],p.query_loaded['entry']+QUERY_NATIVE[0])
                p.after('condition',outer,{'returnValue':0});p.after('frame',frame,{'returnValue':0})
                self.assertEqual(p.native_pending,[])

    def test_condition_packet_lease_generation_body_mode_and_reused_returns_reject(self):
        for fault in ('version','size','operation','slot','runtime','generation','query-owner','native-body','descriptor','descriptor-version','descriptor-tail','mode'):
            with self.subTest(fault=fault):
                p,o,s,a,src,eng,w,r,put=self.fixture();p.before('frame')
                outer,packet=self.condition_call(p,o,s,w,r,put)
                raw=bytearray(packet)
                if fault=='version':raw[40]=3
                if fault=='size':raw[42]=55
                if fault=='operation':raw[46]=7
                if fault=='slot':raw[44]=3
                if fault=='runtime':raw[0]^=4
                if fault in ('version','size','operation','slot','runtime'):put(r.r0,bytes(raw))
                if fault=='generation':a['handle']['generation']+=1
                if fault=='query-owner':p.query_loaded['fieldEpoch']+=1
                if fault=='native-body':put(p.query_loaded['entry']+QUERY_NATIVE[0]+QUERY_NATIVE[1]-1,b'!')
                if fault=='descriptor':put(p.query_loaded['entry']+152,bytes(4))
                if fault=='descriptor-version':put(p.query_loaded['entry']+4,b'\x08')
                if fault=='descriptor-tail':put(p.query_loaded['entry']+195,b'!')
                if fault=='mode':put(0x02240000+0x6BC+247,b'\x04')
                with self.assertRaises(ValueError):p.native_before()
        p,o,s,a,src,eng,w,r,put=self.fixture();p.before('frame')
        outer,packet=self.condition_call(p,o,s,w,r,put);value=p.native_before()
        p.native_after(value,{'returnValue':0})
        with self.assertRaisesRegex(ValueError,'reused'):p.native_after(value,{'returnValue':0})
        p.after('condition',outer,{'returnValue':0})
        with self.assertRaisesRegex(ValueError,'reused'):p.after('condition',outer,{'returnValue':0})

    def test_condition_return_checks_owner_packet_status_and_parent_order(self):
        for fault in ('generation','owner','packet','status','parent','window','pending-native'):
            with self.subTest(fault=fault):
                p,o,s,a,src,eng,w,r,put=self.fixture();p.before('frame')
                outer,packet=self.condition_call(p,o,s,w,r,put);value=p.native_before();status=0
                if fault=='generation':a['handle']['generation']+=1
                if fault=='owner':put(p.query_loaded['stateAddress'],bytes(28))
                if fault=='packet':put(r.r0+44,b'\x03')
                if fault=='status':status=5
                if fault=='parent':p.conditions.append(dict(outer))
                if fault=='window':p.frame['windowId']+=1
                with self.assertRaises(ValueError):
                    p.after('condition',outer,{'returnValue':0}) if fault=='pending-native' else p.native_after(value,{'returnValue':status})

    def timed_fixture(self):
        from collections import deque
        p,o,s,a,src,eng,w,r,put=self.fixture();callbacks={};clock={'ticks':10,'frame':1}
        o.MAX_DEPTH=NativeObservation.MAX_DEPTH;o.MAX_EVENTS=NativeObservation.MAX_EVENTS
        o.hooks=SimpleNamespace(add=lambda address,callback:callbacks.__setitem__(address,callback) or address,
            remove=lambda token:callbacks.pop(token))
        o.contexts=[];o.return_tokens=[];o.pending=deque();o.sequence=0;o.events_dropped=0
        o._clock=lambda:dict(actorFrame=3118,nativeCycle=1)
        o._guest_clock=lambda:dict(arm9Timestamp=clock['ticks'],arm7Timestamp=clock['ticks'],frameSequence=clock['frame'])
        o._queue=lambda kind,context,data:NativeObservation._queue(o,kind,context,data)
        frame=p.before('frame')
        return p,o,s,a,src,eng,w,r,put,callbacks,clock,frame

    def test_dynamic_native_hook_times_return_and_rejects_reuse_backwards_and_depth(self):
        p,o,s,a,src,eng,w,r,put,callbacks,clock,frame=self.timed_fixture()
        outer,packet=self.condition_call(p,o,s,w,r,put)
        callbacks[p.native_target[0]]();returned=callbacks[r.lr];clock['ticks']=35
        r.r0=0;r.sp-=4;returned()
        self.assertEqual(len(o.pending),0);self.assertEqual(len(o.contexts),1)
        r.sp+=4;returned()
        self.assertEqual(o.pending[-1]['guestTiming']['arm9Ticks'],25)
        self.assertEqual(o.pending[-1]['evaluationMode'],'Normal')
        self.assertEqual(o.contexts,[]);self.assertEqual(o.return_tokens,[]);self.assertEqual(p.native_pending,[])
        with self.assertRaisesRegex(ValueError,'consumed'):returned()
        p.after('condition',outer,{'returnValue':0});p.after('frame',frame,{'returnValue':0})
        for fault in ('ticks','frame','depth'):
            with self.subTest(fault=fault):
                p,o,s,a,src,eng,w,r,put,callbacks,clock,frame=self.timed_fixture()
                self.condition_call(p,o,s,w,r,put);callbacks[p.native_target[0]]();r.r0=0
                if fault=='depth':o.contexts.append({})
                elif fault=='ticks':clock['ticks']=9
                else:clock['frame']=0
                with self.assertRaisesRegex(ValueError,'nesting' if fault=='depth' else 'backwards'):
                    callbacks[r.lr]()

    def test_nested_moving_then_target_access_native_hooks_require_lifo(self):
        for reversed_return in (False,True):
            with self.subTest(reversed_return=reversed_return):
                p,o,s,a,src,eng,w,r,put,callbacks,clock,frame=self.timed_fixture()
                outer,moving=self.condition_call(p,o,s,w,r,put,-3,1,0)
                moving_pointer=r.r0;moving_sp=r.sp;moving_lr=r.lr
                callbacks[p.native_target[0]]();moving_return=callbacks[moving_lr]
                target=bytearray(moving);target[46]=2;struct.pack_into('<I',target,36,0x40)
                r.r0=moving_pointer-0x100;r.sp=moving_sp-0x100;r.lr=moving_lr+4;put(r.r0,target)
                put(0x02240000+0x6BC+247,b'\x02');clock['ticks']=15
                callbacks[p.native_target[0]]();target_return=callbacks[r.lr]
                self.assertEqual([v['operation'] for v in p.native_pending],[1,2])
                if reversed_return:
                    r.r0=0;r.sp=moving_sp
                    with self.assertRaisesRegex(ValueError,'nesting'):moving_return()
                    self.assertEqual(len(o.pending),0);self.assertEqual(len(p.native_pending),2)
                    continue
                r.r0=0;clock['ticks']=20;target_return()
                self.assertEqual([v['operation'] for v in p.native_pending],[1])
                r.sp=moving_sp;r.lr=moving_lr;clock['ticks']=30;moving_return()
                self.assertEqual([v['operation'] for v in o.pending],[2,1])
                self.assertEqual([v['guestTiming']['arm9Ticks'] for v in o.pending],[5,20])
                self.assertEqual(o.pending[0]['indexFieldMeaning'],'allowedTerrainMask')
                self.assertEqual(o.pending[0]['forcedProfileIndex'],0x40)
                self.assertEqual(o.pending[0]['forcedOverrideProfileIndex'],-3)
                self.assertTrue(all(v['evaluationMode']=='Moving' for v in o.pending))
                self.assertEqual(o.contexts,[]);self.assertEqual(o.return_tokens,[]);self.assertEqual(p.native_pending,[])
                p.after('condition',outer,{'returnValue':0});p.after('frame',frame,{'returnValue':0})

    def test_terminal_window_and_children_keep_exact_object_and_identity(self):
        p,o,s,a,src,eng,w,r,put=self.fixture()
        frame=p.before('frame');self.assertEqual(frame['owner']['subject']['handle']['value'],65540)
        r.r0=w['fieldPointer'];r.r1=src['object'];r.r2=562;r.r3=388
        height=p.before('height');self.assertEqual(height['tile'],[562,388])
        p.after('height',height,{'returnValue':0})
        r.r0=0x02240000;r.r1=src['object'];r.r2=0
        admit=p.before('admit');self.assertEqual(admit['effectOwner']['slot'],4)
        owner=0x02250000;slot=owner+28
        words=[r.r0,1,0x02250100,0x02250200,0x02250300,0x02250400,0]
        words += [owner,src['object'],0,0,0,0,0,0,0,1] + [0]*20
        put(owner,struct.pack('<37I',*words))
        r.r0=slot;r.r1=admit['context'];r.r2=admit['emote']
        prepare=p.before('prepare');p.after('prepare',prepare,{'returnValue':1})
        r.r0=0x02260000;r.r1=0x02261000
        init=p.before('initialize')
        put(r.r1+44,struct.pack('<5I',slot,admit['context'],owner,src['object'],0x02262000))
        self.assertIn('bindingHex',p.after('initialize',init,{'returnValue':1}))
        self.assertFalse(p.after('admit',admit,{'returnValue':0x02260000})['acceptedProof'])
        a.update(motionKind='NONE',motionPhase='IDLE')
        self.assertEqual(p.after('frame',frame,{'returnValue':0})['motionAfter']['motionKind'],'NONE')
        self.assertIsNone(p.frame);self.assertEqual(p.bubbles,[])

    def test_wrong_generation_world_object_slot_code_and_bounds_reject(self):
        for fault in ('generation','world','object','live','slot','limit'):
            p,o,s,a,src,eng,w,r,put=self.fixture();frame=p.before('frame')
            r.r0=w['fieldPointer'];r.r1=src['object']
            with self.subTest(fault=fault):
                if fault=='generation':a['handle']['generation']+=1
                if fault=='world':w['mapGeneration']+=1
                if fault=='object':src['object']+=4
                if fault=='live':o._live_code=lambda *_:b'bad'
                if fault=='slot':eng['id_lookup']['pointer_matches']=False
                if fault=='limit':p.frame['children']=p.MAX_CHILDREN
                with self.assertRaises(ValueError):
                    p.owner(4) if fault=='slot' else p.before('height')

    def test_prepared_early_nonfly_inactive_and_unrelated_object_do_not_capture(self):
        for fault in ('prepared','early','nonfly','inactive','limit','wrong-map','before-window','after-window'):
            p,o,s,a,src,eng,w,r,put=self.fixture()
            if fault=='prepared':s.prepared=True
            if fault=='early':a['motionElapsed']=140
            if fault=='nonfly':a['motionKind']='HOP'
            if fault=='inactive':a['species']=16
            if fault=='limit':p.windows=p.MAX_WINDOWS
            if fault=='wrong-map':w['mapId']=33
            if fault=='before-window':s.completed_frames=3515
            if fault=='after-window':s.completed_frames=3549
            with self.subTest(fault=fault):self.assertIsNone(p.before('frame'))
        p,o,s,a,src,eng,w,r,put=self.fixture();p.before('frame');r.r1+=4
        self.assertIsNone(p.before('height'));self.assertIsNone(p.before('admit'))

    def test_native_full_owner_pins_match_current_linked_and_packaged_bodies(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        import ndspy.rom
        rom=ndspy.rom.NintendoDSRom.fromFile(str(REPO/'test.nds'))
        overlays=rom.loadArm9Overlays()
        for key,(file,name,address,size,sha) in PINS.items():
            with self.subTest(key=key):
                path=REPO/'build'/file
                self.assertEqual(_elf_function_extent(path,name),(address,size))
                code=_elf_code(path,address,size)
                self.assertEqual(hashlib.sha256(code).hexdigest(),sha)
                number=1 if address<0x02300000 else 158 if file.startswith('overworld_actor') else 149
                overlay=overlays[number]
                self.assertEqual(bytes(overlay.data[address-overlay.ramAddress:address-overlay.ramAddress+size]),code)
                for index in (0,len(code)-1):
                    wrong=bytearray(code);wrong[index]^=1
                    self.assertNotEqual(hashlib.sha256(wrong).hexdigest(),sha)

    def test_query_native_full_body_and_descriptor_match_current_linked_staged_rom(self):
        from tools.overworld.devtools_query_observer import sealed_package
        from tools.overworld.devtools_runtime import _elf_function_extent
        import ndspy.narc
        import ndspy.rom
        directory=REPO/'build/overworld_query_code_addon';elf=(directory/'image.elf').read_bytes()
        staged=(directory/'query.bin').read_bytes()
        rom=ndspy.rom.NintendoDSRom.fromFile(str(REPO/'test.nds'))
        member=ndspy.narc.NARC(rom.getFileByName('a/0/2/8')).files[21]
        blob,image,receipt=sealed_package(elf,staged,member)
        from tools.overworld.devtools_resolver_parity import packaged_query_identity
        identity,owned_blob,owned_receipt=packaged_query_identity(REPO,REPO/'test.nds')
        from tools.overworld.devtools_query_observer import CARGO_WILD_START, CARGO_WILD_END
        def same_package_receipt(authenticated_receipt):
            base_receipt = dict(authenticated_receipt)
            self.assertEqual(base_receipt.pop('cargoWildRange'), (CARGO_WILD_START, CARGO_WILD_END))
            self.assertEqual((owned_blob,owned_receipt),(blob,base_receipt))
        same_package_receipt(receipt)
        with self.assertRaises(AssertionError):
            same_package_receipt(dict(receipt, cargoWildRange=(CARGO_WILD_START, CARGO_WILD_END - 4)))
        self.assertEqual(identity['queryPackageSha256'],hashlib.sha256(blob).hexdigest())
        offset,size,sha=QUERY_NATIVE
        self.assertEqual(_elf_function_extent(directory/'image.elf','OverworldConditionNative_Run'),(0x02080000+offset,size))
        self.assertEqual(image[offset:offset+size],_elf_code(directory/'image.elf',0x02080000+offset,size))
        self.assertEqual(hashlib.sha256(image[offset:offset+size]).hexdigest(),sha)
        self.assertEqual(struct.unpack_from('<IHH',image),(0x51444F57,9,196))
        self.assertEqual(struct.unpack_from('<I',image,152)[0],0x02080000+offset|1)
        for byte in (64+152,64+offset+size-1):
            bad=bytearray(member);bad[byte]^=1
            with self.assertRaisesRegex(ValueError,'ROM member21'):sealed_package(elf,staged,bytes(bad))

    def test_install_rejects_bad_typed_extent_linked_tail_and_packaged_body(self):
        from tools.overworld.devtools_runtime import _elf_function_extent
        codes={key:_elf_code(REPO/"build"/pin[0],pin[2],pin[3]) for key,pin in PINS.items()}
        for key,pin in PINS.items():
            for fault in ("extent","linked-tail","package"):
                with self.subTest(owner=key,fault=fault):
                    def extent(path,name):
                        got=_elf_function_extent(path,name)
                        return (got[0]+4,got[1]) if fault=="extent" and name==pin[1] else got
                    def linked(path,address,size):
                        data=_elf_code(path,address,size)
                        return data[:-1]+bytes([data[-1]^1]) if fault=="linked-tail" and address==pin[2] else data
                    regions=[]
                    for own,p in PINS.items():
                        data=codes[own]
                        if fault=="package" and own==key:
                            data=bytes([data[0]^1])+data[1:]
                        regions.append((p[2],data))
                    obs=SimpleNamespace(session=SimpleNamespace(rt=SimpleNamespace(REPO=REPO),code_regions=regions,rom=str(REPO/"test.nds")),
                        elf_code=linked,_tap=lambda *a,**kw:None)
                    with patch("tools.overworld.devtools_fly_landing_cost._elf_function_extent",side_effect=extent):
                        with self.assertRaisesRegex(ValueError,"differs"):FlyLandingCost(obs)

    def test_install_seals_packaged_bodies_before_wild_overlay_is_loaded(self):
        regions=[(p[2],_elf_code(REPO/"build"/p[0],p[2],p[3])) for p in PINS.values()]
        calls=[]
        session=SimpleNamespace(rt=SimpleNamespace(REPO=REPO),code_regions=regions,rom=str(REPO/"test.nds"))
        obs=SimpleNamespace(session=session,elf_code=_elf_code,
                            _tap=lambda *args,**kwargs:calls.append((args,kwargs)))
        reader=FlyLandingCost(obs)
        self.assertEqual(len(reader.code),8)
        self.assertEqual(len(calls),8)
        self.assertFalse(calls[0][1]['resident'])
        self.assertTrue(all(c[1]['resident'] for c in calls[1:]))

    def test_shared_tap_times_real_entry_return_and_rejects_backward_guest_clock(self):
        from collections import deque
        callbacks={};state={'ticks':10}
        regs=SimpleNamespace(sp=0x027E3000,lr=0x02001001,r0=0)
        code=bytes(32);address=0x02002000
        session=SimpleNamespace(prepared=False,code_regions=[(address,code)],read=lambda a,n:code,
            emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=regs)))
        obs=object.__new__(NativeObservation);obs.session=session
        obs.hooks=SimpleNamespace(add=lambda a,c:callbacks.__setitem__(a,c) or a,
            remove=lambda a:callbacks.pop(a));obs.contexts=[];obs.return_tokens=[];obs.tokens=[];obs.calls={}
        obs.pending=deque();obs.sequence=0;obs.events_dropped=0
        obs._clock=lambda:dict(actorFrame=3118,nativeCycle=1)
        obs._guest_clock=lambda:dict(arm9Timestamp=state['ticks'],arm7Timestamp=state['ticks'],frameSequence=1)
        obs._tap('fly-landing-cost-frame',address,code,lambda:{},lambda v,c:{'diagnosticOnly':True},timed=True)
        callbacks[address]();state['ticks']=35
        regs.sp-=4;callbacks[regs.lr]()
        self.assertEqual(len(obs.pending),0);self.assertEqual(len(obs.contexts),1)
        regs.sp+=4;callbacks[regs.lr]()
        self.assertEqual(obs.pending[-1]['guestTiming']['arm9Ticks'],25)
        self.assertEqual(obs.contexts,[]);self.assertEqual(obs.return_tokens,[])
        callbacks[address]();state['ticks']=34
        with self.assertRaisesRegex(ValueError,'backwards'):callbacks[regs.lr]()

if __name__=='__main__':unittest.main()
