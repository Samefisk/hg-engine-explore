"""Focused host controls. These copied receipts are never game proof."""
from copy import deepcopy
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))

from tools.overworld import devtools_appearance_measurement as measurement
from tools.overworld import devtools_appearance_observer as reader
from tools.overworld.devtools_application_bank import decode_application_bank, local_application

class Memory:
    def __init__(self):
        self.ranges={};self.reads=[]
        self.emu=SimpleNamespace(memory=SimpleNamespace(register_arm9=SimpleNamespace(r0=0,r1=0,r2=0)))
    def put(self,pointer,data):self.ranges[pointer]=bytes(data)
    def read(self,pointer,size):
        self.reads.append((pointer,size))
        for base,data in self.ranges.items():
            if base<=pointer and pointer+size<=base+len(data):return data[pointer-base:pointer-base+size]
        raise ValueError("unexpected memory read")


def actor():
    return dict(handle=dict(slot=0,generation=1,fieldEpoch=2,mapGeneration=3,encounterGeneration=4,value=65536),
        subjectIdentity=99,species=95,form=0,level=5,authorityGeneration=1,engineAnchorGeneration=2,
        presentationGeneration=3,role="WILD",roleId=1)

def view(mode=1,strength=4):
    a=actor();original=struct.pack("<16H",*[0x8000|(i*123)&0x7fff for i in range(16)])
    v=deepcopy(a);v.update(owner=dict(actor=deepcopy(a),fieldPointer=0x02204000),recordPointer=0x022A0000,actorPointer=0x023BA170,
        objectPointer=0x022A1000,drawPointer=0x022A2000,modelPointer=0x022A3000,texturePointer=0x022A4000,
        originalPalettePointer=0x022A5000,tintedPalettePointer=0x022A6000,originalPaletteKey=0x03000020,
        privatePaletteKey=0x03000100,appliedMaterials=1,lastOriginalBase=16,lastTintedBase=128,
        paletteBytes=32,mode=mode,strength=strength,yielded=0,drawCommand=4,drawTiming=2,
        originalHex=original.hex(),tintedHex=(original if strength == 0 else
            measurement.blend(original,mode,strength)).hex())
    return v

def observer(v):
    session=Memory();session.put(v["tintedPalettePointer"],bytes.fromhex(v["tintedHex"]))
    session.put(0x021E1600,struct.pack("<I",0x06800000))
    item=reader.NativeAppearanceObserver.__new__(reader.NativeAppearanceObserver)
    item.session=session;item.refresh=[object()];item.vblank=[dict(fieldPointer=0x02204000,callbackAddress=0x021E5900)];item.pending_upload=None;item.upload_count=0
    item.uploads={};item.materials={};item.material_keys=set();item._records=lambda:[deepcopy(v)]
    return item,session

class AppearanceDraftControls(unittest.TestCase):
    def test_current_prepared_damage_pending_boolean_keeps_species_guard(self):
        a=actor();prepared=bytearray(88);blob=bytearray(84)
        struct.pack_into('<H',blob,4,95)
        struct.pack_into('<IHHI',blob,52,84,0,48,84)
        struct.pack_into('<6H',prepared,0,*[a['handle'][k] for k in reader.HANDLE_KEYS],0)
        struct.pack_into('<BBHH',prepared,80,0,1,0,a['species'])
        memory=Memory()
        for pending in (0,1,2,65535):
            with self.subTest(pending=pending):
                struct.pack_into('<H',prepared,86,pending);memory.put(0x022B0000,prepared)
                if pending in (0,1):
                    self.assertEqual(reader.decode_conditions(memory.read,0x022B0000,a,blob,100,0,{})['reason'],'no-condition-states')
                else:
                    with self.assertRaisesRegex(ValueError,'subject species differs'):
                        reader.decode_conditions(memory.read,0x022B0000,a,blob,100,0,{})
        struct.pack_into('<HH',prepared,84,a['species']+1,1);memory.put(0x022B0000,prepared)
        with self.assertRaisesRegex(ValueError,'subject species differs'):
            reader.decode_conditions(memory.read,0x022B0000,a,blob,100,0,{})

    def test_catalog_v89_retains_exact_tint_and_condition_options_tail(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import hashlib

        # Only the catalog changes here. Native owner/code checks have their own controls.
        with TemporaryDirectory() as directory:
            repo=Path(directory);build=repo/'build';build.mkdir()
            (build/'overworld_field_capsule_linked.o').write_bytes(b'host ELF control')
            symbols={'OverworldActorAppearance_RefreshNative':reader.BASE+32,
                     'Appearance_ApplyMaterial':reader.BASE+64}
            session=SimpleNamespace(rt=SimpleNamespace(REPO=repo,linked_symbols=lambda _:symbols),
                packaged_code=lambda address,size:bytes(size))
            native=SimpleNamespace(session=session,elf_code=lambda path,address,size:reader.ENTRY+bytes(size-8))

            def blob(version,count=2):
                rest=88
                options=max(count,1)*12 if version in (87,88,89) else 0
                data=bytearray(rest+4+options)
                struct.pack_into('<4sHHI',data,0,b'OWBD',version,84,len(data))
                struct.pack_into('<H',data,56,count)
                struct.pack_into('<IHH',data,76,84,2,2)
                struct.pack_into('<I',data,rest,0x20)
                return data

            def create(data):
                (build/'OverworldWildBehaviorData.bin').write_bytes(data)
                return reader.NativeAppearanceObserver(native)

            with patch.object(reader,'symbol',return_value=(reader.BASE+128,4,b'')), \
                 patch.object(reader.NativeAppearanceObserver,'_tap'):
                for version,count in ((86,2),(87,2),(88,2),(88,0),(89,2),(89,0)):
                    data=blob(version,count)
                    with self.subTest(version=version,count=count):
                        initialized=create(data)
                        self.assertEqual(initialized.enabled,0x20)
                        self.assertEqual(initialized.blob,bytes(data))
                        self.assertEqual(initialized.blob_hash,hashlib.sha256(data).hexdigest())
                for fault in ('unknown-version','wrong-header','wrong-total','missing-options','extra-tail'):
                    data=blob(88)
                    if fault=='unknown-version':struct.pack_into('<H',data,4,90)
                    elif fault=='wrong-header':struct.pack_into('<H',data,6,85)
                    elif fault=='wrong-total':struct.pack_into('<I',data,8,len(data)-1)
                    elif fault=='missing-options':
                        del data[92:];struct.pack_into('<I',data,8,len(data))
                    else:
                        data+=b'\0'*4;struct.pack_into('<I',data,8,len(data))
                    message='catalog ABI differs' if fault in ('unknown-version','wrong-header','wrong-total') \
                        else 'catalog appended tint/options layout differs'
                    with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,message):create(data)

    def test_off_soft_peak_and_hp_driven_periods(self):
        # Fixed injury bands are independent expectations for the native policy.
        for hp,peak,period in ((99,2,128),(79,3,128),(59,4,64),(39,5,64),(19,6,32)):
            with self.subTest(hp=hp):
                for frame in range(period*2):
                    phase=frame%period
                    triangle=min(phase,period-phase)
                    expected=0 if triangle<=period//4 else peak*(triangle-period//4)//(period//4)
                    pulse=measurement.damage_pulse(hp,100,frame)
                    self.assertEqual(pulse,dict(peak=peak,period=period,phase=phase,strength=expected))
                self.assertEqual(measurement.damage_strength(hp,100,0),0)
                self.assertEqual(measurement.damage_strength(hp,100,period//2),peak)
                self.assertEqual(measurement.damage_strength(hp,100,period),0)
                self.assertEqual(measurement.damage_strength(hp,100,0xffffffff),0)
        self.assertEqual(measurement.damage_strength(100,100,64),0)
        for hp,max_hp,frame in ((-1,100,0),(101,100,0),(0,65536,0),(1,100,-1),(1,100,0x100000000)):
            with self.subTest(hp=hp,max_hp=max_hp,frame=frame),self.assertRaises(ValueError):
                measurement.damage_strength(hp,max_hp,frame)

    def test_actual_reader_upload_completion_and_actual_material(self):
        v=view();obs,session=observer(v);regs=session.emu.memory.register_arm9
        regs.r0=v["tintedPalettePointer"];regs.r1=(v["privatePaletteKey"]&0xffff)<<3;regs.r2=32
        upload=obs._upload_before();self.assertFalse(upload["completed"])
        obs._upload_after(upload,{})
        self.assertIs(obs._end_before(),upload);self.assertEqual(obs.uploads,{})
        upload=obs._end_after(upload,{})
        self.assertTrue(upload["completed"]);self.assertEqual(upload["destinationAddress"],0x06800800)
        state=bytearray(0xb4);struct.pack_into("<I",state,4,v["drawPointer"]+0x30)
        struct.pack_into("<I",state,0xb0,0x027E1200);session.put(0x027E1000,state)
        words=[0]*14;words[4]=3<<26;words[5]=16;session.put(0x027E1200,struct.pack("<14I",*words))
        regs.r0=0x027E1000;material=obs._material_before()
        words[5]=128;session.put(0x027E1200,struct.pack("<14I",*words))
        material=obs._material_after(material,{})
        self.assertEqual(material["beforeWord"],16);self.assertEqual(material["afterWord"],128)
        proof=measurement.verify_palette(v,upload,material,actor(),1,4)
        self.assertEqual(proof["uploadId"],1)
        self.assertIsNone(obs._material_after(deepcopy(material),{}))
        for field,value in (("sourcePointer",v["originalPalettePointer"]),("completed",False),
                            ("uploadedHex",v["originalHex"]),("destinationOffset",0),
                            ("dispatch","actor-refresh"),
                            ("callback",dict(fieldPointer=0x02205000,callbackAddress=0x021E5900))):
            bad=deepcopy(upload);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                measurement.verify_palette(v,bad,material,actor(),1,4)
        for field,value in (("afterWord",16),("textureFormat",2),("renderObjectPointer",v["drawPointer"]),
                            ("uploadId",2)):
            bad=deepcopy(material);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                measurement.verify_palette(v,upload,bad,actor(),1,4)

    def pending_material(self, *, mode=2, strength=2, before=16, texture_format=3):
        v=view(mode,strength);v["uploadPending"]=True
        obs,session=observer(v);regs=session.emu.memory.register_arm9
        regs.r0=v["tintedPalettePointer"];regs.r1=(v["privatePaletteKey"]&0xffff)<<3;regs.r2=32
        upload=obs._upload_before();obs._upload_after(upload,{})
        upload=obs._end_after(obs._end_before(),{})
        state=bytearray(0xb4);struct.pack_into("<I",state,4,v["drawPointer"]+0x30)
        struct.pack_into("<I",state,0xb0,0x027E1200);session.put(0x027E1000,state)
        words=[0]*14;words[4]=texture_format<<26;words[5]=before
        session.put(0x027E1200,struct.pack("<14I",*words));regs.r0=0x027E1000
        return v,obs,session,upload,words,obs._material_before()

    def test_pending_normal_mat_waits_for_the_first_completed_same_upload_mat(self):
        v,obs,session,upload,words,material=self.pending_material()
        self.assertIsNone(obs._material_after(material,{}))
        self.assertEqual(obs.materials,{})
        self.assertEqual(obs.material_keys,set())
        # The same native owner returns next frame after the queue is empty.
        v["uploadPending"]=False
        material=obs._material_before();words[5]=128
        session.put(0x027E1200,struct.pack("<14I",*words))
        material=obs._material_after(material,{})
        self.assertEqual(material["uploadId"],upload["uploadId"])
        self.assertEqual(obs.material_keys,{(0,1)})
        self.assertEqual(obs.materials[0],material)
        proof=measurement.verify_palette(v,upload,material,actor(),2,2)
        self.assertEqual(proof["afterWord"],128)
        self.assertIsNone(obs._material_after(deepcopy(material),{}))
        # The strict meter needs the real later return, not just its cache.
        meter=measurement.AppearanceMeasurement.__new__(measurement.AppearanceMeasurement)
        meter.upload_events={1:upload};meter.material_events={1:material}
        data=dict(records=[v],uploads=obs.uploads,materials=obs.materials)
        self.assertEqual(meter._palette(data,actor(),2,2),proof)
        meter.material_events[1]=dict(material,afterWord=16)
        with self.assertRaisesRegex(ValueError,"real MAT command"):
            meter._palette(data,actor(),2,2)

    def test_pending_entry_does_not_hide_a_completed_first_mat_or_off_phase(self):
        for strength,after in ((2,128),(0,16)):
            with self.subTest(strength=strength):
                v,obs,session,upload,words,material=self.pending_material(mode=1,strength=strength)
                # Native CompleteUpload may clear its entry flag within MAT.
                v["uploadPending"]=False;words[5]=after
                session.put(0x027E1200,struct.pack("<14I",*words))
                material=obs._material_after(material,{})
                self.assertIsNotNone(material)
                self.assertEqual(measurement.verify_palette(v,upload,material,actor(),1,strength)["off"],
                                 strength==0)

    def test_only_a_valid_current_pending_normal_mat_can_defer(self):
        for fault in ("completed-no-op","format","base-low","base-odd","base-high","private-zero",
                      "draw","yielded","command","timing"):
            with self.subTest(fault=fault):
                v,obs,session,upload,words,material=self.pending_material()
                if fault=="completed-no-op":v["uploadPending"]=False
                elif fault=="format":material["textureFormat"]=2
                elif fault.startswith("base-"):
                    words[5] = {"base-low":15,"base-odd":17,"base-high":18}[fault]
                    material["beforeWord"]=words[5]
                    session.put(0x027E1200,struct.pack("<14I",*words))
                elif fault=="draw":material["renderObjectPointer"]-=4
                else:
                    key,value={"private-zero":("privatePaletteKey",0),"yielded":("yielded",1),
                               "command":("drawCommand",0),"timing":("drawTiming",0)}[fault]
                    for value_view in (v,material["view"],upload["view"],obs.uploads[0]["view"]):
                        value_view[key]=value
                event=obs._material_after(material,{})
                self.assertIsNotNone(event) # Wrong MAT is still visible to the strict meter.
                self.assertEqual(obs.material_keys,{(0,1)})
                with self.assertRaises(ValueError):
                    measurement.verify_palette(v,upload,event,actor(),2,2)
        for fault in ("missing-owner","identity","private","palette-bytes","field-owner","owner-context","owner-identity"):
            with self.subTest(fault=fault):
                v,obs,session,upload,words,material=self.pending_material()
                if fault=="missing-owner":obs._records=lambda:[]
                elif fault=="identity":v["handle"]["generation"]+=1
                elif fault=="private":v["privatePaletteKey"]+=2
                elif fault=="palette-bytes":v["tintedHex"]="00"*32
                elif fault=="field-owner":v["owner"]["fieldPointer"]+=4
                elif fault=="owner-context":v["owner"]["context"]=dict(mapId=999)
                else:v["owner"]["actor"]["subjectIdentity"]+=1
                with self.assertRaisesRegex(ValueError,"pending MAT"):
                    obs._material_after(material,{})
                self.assertEqual(obs.materials,{})
                self.assertEqual(obs.material_keys,set())

    def test_injured_off_uploads_original_and_uses_normal_material(self):
        v=view(1,0);obs,session=observer(v);regs=session.emu.memory.register_arm9
        regs.r0=v['tintedPalettePointer'];regs.r1=0x800;regs.r2=32
        upload=obs._upload_before();obs._upload_after(upload,{})
        upload=obs._end_after(obs._end_before(),{})
        state=bytearray(0xb4);struct.pack_into('<I',state,4,v['drawPointer']+0x30)
        struct.pack_into('<I',state,0xb0,0x027E1200);session.put(0x027E1000,state)
        words=[0]*14;words[4]=3<<26;words[5]=16
        session.put(0x027E1200,struct.pack('<14I',*words));regs.r0=0x027E1000
        material=obs._material_before();words[5]=16
        session.put(0x027E1200,struct.pack('<14I',*words))
        material=obs._material_after(material,{})
        proof=measurement.verify_palette(v,upload,material,actor(),1,0)
        self.assertTrue(proof['off'])
        self.assertEqual(upload['uploadedHex'],v['originalHex'])
        self.assertEqual(material['afterWord'],16)
        self.assertEqual(proof['privatePaletteKey'],v['privatePaletteKey'])
        bad=deepcopy(v);bad['tintedHex']=view(1,2)['tintedHex']
        with self.assertRaisesRegex(ValueError,'exact HP/cooldown blend'):
            measurement.verify_palette(bad,upload,material,actor(),1,0)
        for mode in (0,2):
            bad=deepcopy(v);bad['mode']=mode
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'tint mode'):
                measurement.verify_palette(bad,upload,material,actor(),1,0)
        bad=deepcopy(upload);bad['uploadedHex']=view(1,2)['tintedHex']
        with self.assertRaisesRegex(ValueError,'SDK palette upload'):
            measurement.verify_palette(v,bad,material,actor(),1,0)
        bad=deepcopy(material);bad['afterWord']=128
        with self.assertRaisesRegex(ValueError,'MAT command'):
            measurement.verify_palette(v,upload,bad,actor(),1,0)

    def test_real_upload_arguments_and_bank_guard(self):
        v=view();obs,session=observer(v);regs=session.emu.memory.register_arm9
        regs.r0=v["tintedPalettePointer"];regs.r1=0x800;regs.r2=32
        for field,value in (("r0",v["originalPalettePointer"]),("r1",0),("r2",16)):
            old=getattr(regs,field);setattr(regs,field,value)
            with self.subTest(field=field),self.assertRaises(ValueError):obs._upload_before()
            setattr(regs,field,old)
        session.put(0x021E1600,struct.pack("<I",0x02000000))
        with self.assertRaises(ValueError):obs._upload_before()
        session.put(0x021E1600,struct.pack("<I",0x06800001))
        with self.assertRaises(ValueError):obs._upload_before()
        obs.refresh=[];obs.vblank=[];self.assertIsNone(obs._upload_before())

    def test_stock_queue_completes_outside_actor_refresh(self):
        v=view();obs,session=observer(v);regs=session.emu.memory.register_arm9
        obs.refresh=[]
        obs.vblank=[dict(fieldPointer=0x02204000,callbackAddress=0x021E5900,caller=0x02000E11)]
        regs.r0=v["tintedPalettePointer"];regs.r1=0x800;regs.r2=32
        upload=obs._upload_before()
        self.assertEqual(upload["dispatch"],"field-vblank")
        self.assertEqual(upload["callback"],obs.vblank[0])
        self.assertNotIn("displayScanline",upload)
        obs._upload_after(upload,{})
        self.assertIs(obs._end_before(),upload)
        self.assertTrue(obs._end_after(upload,{})["completed"])
        # A native texture upload in the same queue is not borrowed tint proof.
        regs.r0=v["originalPalettePointer"]
        self.assertIsNone(obs._upload_before())

    def test_pending_stock_upload_cannot_be_palette_proof(self):
        v,u,m=palette(actor(),1,4,1)
        v["uploadPending"]=True
        meter=measurement.AppearanceMeasurement.__new__(measurement.AppearanceMeasurement)
        data=dict(records=[v],uploads={0:u},materials={0:m})
        self.assertIsNone(meter._palette(data,actor(),1,4))

    def test_native_snapshot_layout_full_identity_and_exact_blend(self):
        v=view();raw=bytearray(88);h=v["handle"]
        struct.pack_into("<6H",raw,0,*[h[k] for k in reader.HANDLE_KEYS],0)
        names=("subjectIdentity",*reader.GEN_KEYS,*reader.POINTER_KEYS,"originalPaletteKey",
               "privatePaletteKey","appliedMaterials","lastOriginalBase","lastTintedBase")
        struct.pack_into("<16I",raw,12,*[v[k] for k in names])
        struct.pack_into("<HH6B",raw,76,32,95,0,5,1,1,4,0)
        decoded=reader.decode_view(bytes(raw));self.assertEqual(decoded["handle"],h)
        self.assertEqual(decoded["drawPointer"],v["drawPointer"])
        for offset,value in ((1,255),(2,0),(86,1),(83,3),(84,17)):
            bad=bytearray(raw);bad[offset]=value
            with self.subTest(offset=offset),self.assertRaises(ValueError):reader.decode_view(bytes(bad))
        blue=view(2,2);self.assertNotEqual(v["tintedHex"],blue["tintedHex"])
        original=bytes.fromhex(v["originalHex"]);tinted=bytes.fromhex(v["tintedHex"])
        self.assertEqual(original[:2],tinted[:2])
        for old,new in zip(struct.unpack("<16H",original),struct.unpack("<16H",tinted)):
            self.assertEqual(old&0x8000,new&0x8000)

    def test_entire_current_prepared_set_and_natural_cooldown(self):
        blob=(ROOT/"build/OverworldWildBehaviorData.bin").read_bytes()
        offset,count,stride=struct.unpack_from("<IHH",blob,52)
        bank=decode_application_bank(blob,ROOT)
        indices=[i for i in range(count) if bank["conditionOwners"][i] == measurement.RAM]
        enabled=1<<local_application(bank,95,measurement.RAM)
        self.assertGreaterEqual(len(indices),1)
        self.assertLessEqual(len(indices),32)
        a=actor();prepared=bytearray(88);struct.pack_into("<6H",prepared,0,*[a["handle"][k] for k in reader.HANDLE_KEYS],0)
        struct.pack_into("<I",prepared,12,0x022B1000);struct.pack_into("<"+str(len(indices))+"H",prepared,16,*indices)
        struct.pack_into("<BBHHH",prepared,80,len(indices),1,32,a["species"],0)
        states=b"".join(struct.pack("<II3H2B",90,110,0xffff,0,0,0,2) for _ in indices)
        memory=Memory();memory.put(0x022B0000,prepared);memory.put(0x022B1000,states)
        conditions=reader.decode_conditions(memory.read,0x022B0000,a,blob,100,enabled,bank)
        self.assertEqual({s["application"] for s in conditions["states"]},{measurement.RAM})
        self.assertTrue(measurement.rest_eligible(conditions))
        for fault in ("activeCondition","untriggeredCondition","conditionExpired","maskDisabled"):
            bad=deepcopy(conditions);condition=next(s for s in bad["states"] if s["application"]==measurement.RAM)
            if fault=="activeCondition":condition["flags"]|=1
            elif fault=="untriggeredCondition":condition["flags"]=0
            elif fault=="conditionExpired":condition["cooldownUntil"]=100
            else:
                for state in bad["states"]:state["enabled"]=False
            with self.subTest(fault=fault):self.assertFalse(measurement.rest_eligible(bad))
        bad=bytearray(prepared);struct.pack_into("<H",bad,4,9);memory.put(0x022B0000,bad)
        stale=reader.decode_conditions(memory.read,0x022B0000,a,blob,100,enabled,bank)
        self.assertIs(stale["available"],False);self.assertFalse(measurement.rest_eligible(stale))
        def no_read(*args):raise AssertionError("NULL prepared pointer must not be read")
        empty=reader.decode_conditions(no_read,0,a,blob,100,enabled,bank)
        self.assertIs(empty["available"],False);self.assertFalse(measurement.rest_eligible(empty))
        memory.put(0x022B0000,bytes(88))
        unprepared=reader.decode_conditions(memory.read,0x022B0000,a,blob,100,enabled,bank)
        self.assertIs(unprepared["available"],False);self.assertFalse(measurement.rest_eligible(unprepared))
        no_states=bytearray(prepared);struct.pack_into("<I",no_states,12,0)
        memory.put(0x022B0000,no_states)
        self.assertIs(reader.decode_conditions(memory.read,0x022B0000,a,blob,100,enabled,bank)["available"],False)
        wrapping=deepcopy(conditions);wrapping["frame"]=0xfffffff8
        for state in wrapping["states"]:state["cooldownUntil"]=4
        self.assertTrue(measurement.rest_eligible(wrapping))
        for state in wrapping["states"]:state["cooldownUntil"]=0xfffffff0
        self.assertFalse(measurement.rest_eligible(wrapping))

    def test_completed_boundary_reads_new_ram_state_after_appearance_refresh(self):
        blob=(ROOT/'build/OverworldWildBehaviorData.bin').read_bytes()
        offset,count,stride=struct.unpack_from('<IHH',blob,52)
        bank=decode_application_bank(blob,ROOT)
        index=next(i for i in range(count) if bank['conditionOwners'][i]==measurement.RAM)
        a=actor();a['active']=True;context=dict(mapId=33,fieldEpoch=2,mapGeneration=3)
        owner=dict(actor=deepcopy(a),actorPointer=0x023BA170,objectPointer=0x022A1000,
            fieldPointer=0x02204000,context=context)
        prepared=bytearray(88)
        struct.pack_into('<6H',prepared,0,*[a['handle'][k] for k in reader.HANDLE_KEYS],0)
        struct.pack_into('<I',prepared,12,0x022B1000);struct.pack_into('<H',prepared,16,index)
        struct.pack_into('<BBHHH',prepared,80,1,1,32,a['species'],0)
        memory=Memory();memory.put(0x022B0000,prepared)
        memory.put(0x022B1000,struct.pack('<II3H2B',0,0,0,0,0,0,8))
        obs=reader.NativeAppearanceObserver.__new__(reader.NativeAppearanceObserver)
        obs.session=memory;obs.blob=blob;obs.bank=bank;obs.enabled=1<<local_application(bank,95,measurement.RAM)
        cached=reader.decode_conditions(memory.read,0x022B0000,a,blob,99,obs.enabled,bank)
        cached['owner']=deepcopy(owner);obs.conditions={0:cached};obs._owner=lambda slot:deepcopy(owner)
        sample=dict(fieldAvailable=True,actors=[deepcopy(a)],context=context,actorFrame=100)
        # The real condition service activates Ram later in the same queue.
        memory.put(0x022B1000,struct.pack('<II3H2B',0,0,0,0,0,1,9))
        value=obs._completed_conditions(sample)[0]
        self.assertEqual(value['frame'],100);self.assertEqual(value['states'][0]['flags'],9)
        self.assertEqual(value['states'][0]['targetKind'],1)
        self.assertEqual(cached['states'][0]['flags'],8)
        memory.reads.clear()
        for fault in ('field','identity','context'):
            bad=deepcopy(sample)
            if fault=='field':bad['fieldAvailable']=False
            elif fault=='identity':bad['actors'][0]['handle']['generation']+=1
            else:bad['context']['mapGeneration']+=1
            self.assertEqual(obs._completed_conditions(bad),{})
        self.assertEqual(memory.reads,[])
        owner['objectPointer']+=4
        with self.assertRaisesRegex(ValueError,'changed its native owner'):
            obs._completed_conditions(sample)


from tools.overworld.devtools_appearance_proof import (
    AppearanceNegative, faults, measurements as accepted_measurements, validate_negative_result)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.test_devtools_pokemon_combat_measurement import snapshot as combat_snapshot, cache as combat_cache

SOURCE=dict(contractVersion=1,romSha256='a'*64,overlaySha256='b'*64,profileSha256='c'*64,
            capsuleElfSha256='d'*64,behaviorBlobSha256='e'*64)

def recipe(kind):
    return validate_test(__import__('json').loads((ROOT/'tests/overworld/test-recipes'/
        (measurement.CONFIG[kind]['id']+'.json')).read_text()))

def appearance(sample):
    return dict(schemaVersion=1,available=True,frame=sample['frame'],nativeCycle=sample['nativeCycle'],
        observationBoundary='main-task-queue-completion',identity={k:SOURCE[k] for k in
            ('romSha256','capsuleElfSha256','behaviorBlobSha256')},records=[],conditions={},
        uploads={},materials={},clears={},uploadCount=0)

def palette(actor,mode,strength,upload_id):
    v=view(mode,strength)
    for key in ('handle','subjectIdentity','species','form','level',*reader.GEN_KEYS,'role','roleId'):
        v[key]=deepcopy(actor[key])
    v['owner']=dict(actor=deepcopy(actor),fieldPointer=0x02204000)
    v['drawPointer']+=actor['handle']['slot']*0x100
    upload=dict(view=deepcopy(v),completed=True,sourcePointer=v['tintedPalettePointer'],
        paletteBytes=32,uploadedHex=v['tintedHex'],destinationOffset=0x800,destinationAddress=0x06800800,
        uploadId=upload_id,dispatch='field-vblank',
        callback=dict(fieldPointer=0x02204000,callbackAddress=0x021E5900))
    material=dict(view=deepcopy(v),textureFormat=3,beforeWord=16,afterWord=16 if strength==0 else 128,
        renderObjectPointer=v['drawPointer']+0x30,uploadId=upload_id)
    return v,upload,material

def native_palette(frame,upload,material):
    return [dict(frame=frame,kind='native-observation',data=dict(receipt,observation=name))
            for name,receipt in (('appearance-sdk-upload-complete',upload),('Appearance_ApplyMaterial',material))]

def clear(actor,frame):
    return dict(frame=frame,draw=dict(owner=dict(actor=deepcopy(actor)),drawCallback=0,drawCommand=0,
        drawTiming=0,paletteHex=view()['originalHex'],paletteBytes=32))

def raw_sample(sample,events=(),action='two-real-hits'):
    cache=combat_cache(sample)
    cache['resolvedProfiles'][0]['appliedOverrides']=1<<measurement.AMBUSH
    return dict(phase='observe',action=action,samples=[sample],events=list(events),completedGameFrames=1,
        observedFieldFrames=int(sample['fieldAvailable']),nativeCycles=1,
        cycleIntervals=[dict(completedGameFrame=sample['frame'],cpuNs=1,wallNs=1)],
        profileCache=cache)

def bind(sample,name):
    species=next(s[1] for c in measurement.CONFIG.values() for s in c['subjects'] if s[0]==name)
    actor=next(a for a in sample['actors'] if a['species']==species)
    return dict(phase='setup' if name!='healed-cyndaquil' else 'observe',action='bind-'+name,
        command='bind',snapshot=deepcopy(sample),receipt=select_current_actor(sample,actor))

def roles(sample):
    for a in sample['actors']:
        if a['species']==70:a['matchedLayerMask']=1<<measurement.AMBUSH
        a['roleId']=3 if a['role']=='MOUNTED' else 2 if a['role']=='FOLLOWER' else 1
    return sample

def damage_rows():
    initial=roles(combat_snapshot(1));rows=[dict(phase='setup',initialSnapshot=initial)]
    rows.extend(bind(initial,n) for n in ('cyndaquil','snorlax','weepinbell'))
    cached={};upload_id=0
    for frame in range(2,162):
        sample=roles(combat_snapshot(frame));sample['actorFrame']=frame+8;data=appearance(sample);events=[]
        for name,slot,hits in (('cyndaquil',7,2 if frame>=63 else 1),('snorlax',0,1)):
            actor=next(a for a in sample['actors'] if a['handle']['slot']==slot)
            hp=next(h for h in sample['pokemonCombat']['targets'] if h['slot']==slot)
            hp.update(hp=hp['maxHp']-20*hits,currentHp=hp['maxHp']-20*hits,hitCount=hits,immunityFrames=60)
            if slot==7:sample['party'][0]['hp']=hp['hp']
            strength=measurement.damage_strength(hp['hp'],hp['maxHp'],sample['actorFrame'])
            if slot not in cached or cached[slot][0]['strength']!=strength:
                upload_id+=1;cached[slot]=palette(actor,1,strength,upload_id)
                events+=native_palette(frame,*cached[slot][1:])
            v,u,m=deepcopy(cached[slot]);data['records'].append(v);data['uploads'][slot]=u;data['materials'][slot]=m
        sample['pokemonAppearance']=data;rows.append(raw_sample(sample,events))
    center=deepcopy(sample);center['context']['mapId']=69;center['actors']=[]
    rows.append(dict(phase='observe',action='normal-center',command='teleport',snapshot=center,receipt={}))
    healed=deepcopy(center);healed.update(frame=162,nativeCycle=1162);healed['pokemonAppearance']=appearance(healed)
    healed['party'][0]['hp']=healed['party'][0]['maxHp']
    event=dict(frame=162,kind='native-observation',data=dict(observation='appearance-native-heal',
        mapId=69,synthetic=False,subjectIdentity=107,requestedHp=90))
    rows.append(raw_sample(healed,[event],'nurse-yes-consumed'))
    follower=roles(combat_snapshot(162));follower['actors']=follower['actors'][:1]
    a=follower['actors'][0];a.update(role='FOLLOWER',roleId=2)
    a['handle']['generation']=2;a['handle']['value']=2<<16|7
    for k in ('fieldEpoch','mapGeneration','encounterGeneration'):a['handle'][k]=2
    follower['context'].update(fieldEpoch=2,mapGeneration=2)
    follower['pokemonCombat']['targets']=follower['pokemonCombat']['targets'][:1]
    follower['pokemonCombat']['targets'][0]['handle']=deepcopy(a['handle'])
    follower['pokemonAppearance']=appearance(follower)
    rows.append(dict(phase='observe',action='normal-outdoor',command='teleport',snapshot=deepcopy(follower),receipt={}))
    rows.append(bind(follower,'healed-cyndaquil'))
    final=deepcopy(follower);final.update(frame=163,nativeCycle=1163);final['pokemonCombat'].update(frame=163,nativeCycle=1163)
    final['pokemonAppearance']=appearance(final);final['pokemonAppearance']['clears'][7]=clear(a,163)
    rows.append(raw_sample(final,action='full-hp-draw'))
    return rows

def blue_rows():
    initial=roles(combat_snapshot(1));initial['actors']=[initial['actors'][1]]
    actor=initial['actors'][0];actor.update(species=95,level=5,logical=dict(x=585,y=402))
    actor['engineObject'].update(x=585,y=402,facing=1)
    initial['player'].update(flags=1,x_prev=585,y_prev=407,movement_cmd=255)
    initial['pokemonCombat']['targets']=[initial['pokemonCombat']['targets'][1]]
    initial['pokemonCombat']['targets'][0]['species']=95
    initial['pokemonAppearance']=appearance(initial)
    rows=[dict(phase='setup',initialSnapshot=initial),bind(initial,'onix')]
    blue_palette=palette(actor,2,2,1)
    for frame in range(2,111):
        sample=deepcopy(initial);sample.update(frame=frame,actorFrame=frame,nativeCycle=frame+1000)
        sample['actors'][0]['matchedLayerMask']=(1<<measurement.RAM) if frame<10 else 0
        sample['pokemonCombat'].update(frame=frame,nativeCycle=frame+1000);data=appearance(sample)
        state=dict(application=measurement.RAM,enabled=True,flags=3 if frame<10 else 2,
                   durationFrames=0,activeUntil=0,cooldownUntil=110,cooldownFrames=100)
        data['conditions'][0]=dict(available=True,owner=dict(actor=deepcopy(actor)),frame=frame,
                                  enabledMask=1<<measurement.RAM,states=[state])
        events=[]
        if frame==10:
            events.append(dict(frame=frame,kind='native',data=dict(event='WORLD_EFFECT',valueA=3,
                actorHandle=actor['handle']['value'],actor={k:v for k,v in actor['handle'].items() if k!='value'})))
        if 10<=frame<110:
            v,u,m=deepcopy(blue_palette);data['records']=[v];data['uploads'][0]=u;data['materials'][0]=m
            if frame==10:events+=native_palette(frame,u,m)
        if frame==110:data['clears'][0]=clear(actor,frame)
        sample['pokemonAppearance']=data
        rows.append(raw_sample(sample,events,action='blue-and-natural-expiry'))
    return rows


def replay(kind,rows,fault=None):
    meter=measurement.AppearanceMeasurement(kind,recipe(kind),SOURCE)
    control=AppearanceNegative(kind,fault) if fault else None
    for row in rows:
        meter.observe_record(control.mutate(row,meter.subjects) if control else row)
        if meter.failures:break
    result=meter.finish()
    return dict(passed=result['passed'],failures=result['failures'],observedFrames=result['observedFrames'],
                measurements={kind:result}),control

class PaletteReplayControls(unittest.TestCase):
    def test_injured_pulse_requires_off_on_current_hp_clock_and_period(self):
        rows=damage_rows();positive,_=replay(measurement.DAMAGE,rows)
        self.assertTrue(positive['passed'],positive['failures'])
        meter=positive['measurements'][measurement.DAMAGE]
        for name in ('cyndaquil','snorlax'):
            proofs=meter['palettes'][name]
            self.assertTrue(any(p['off'] and p['originalHex']==p['tintedHex'] for p in proofs))
            self.assertTrue(any(not p['off'] and p['originalHex']!=p['tintedHex'] for p in proofs))
            self.assertEqual(len({p['privatePaletteKey'] for p in proofs}),1)

        # Each control keeps real HP ownership and SDK/MAT rows coherent.
        # Only the pulse contract differs; these remain copied host controls.
        for fault in ('old-trough','wrong-period','wrong-hp','reversed-clock','no-off','blue-off'):
            bad=deepcopy(rows)
            for row in bad:
                samples=row.get('samples',[])
                if not samples or row.get('action')!='two-real-hits':continue
                sample=samples[0];frame=sample['actorFrame'];data=sample['pokemonAppearance']
                if fault=='reversed-clock':
                    if sample['frame']==129:sample['actorFrame']-=128
                    continue
                replaced=[]
                for actor in sample['actors']:
                    slot=actor['handle']['slot']
                    if slot not in data['uploads']:continue
                    hp=next(t for t in sample['pokemonCombat']['targets'] if t['slot']==slot)
                    peak=1+((hp['maxHp']-hp['hp'])*5+hp['maxHp']-1)//hp['maxHp']
                    phase=frame%128
                    strength=measurement.damage_strength(hp['hp'],hp['maxHp'],frame)
                    mode=1
                    if fault=='old-trough':
                        trough=(peak+1)//2;old_phase=frame%64
                        strength=trough+((peak-trough)*min(old_phase,64-old_phase)+16)//32
                    elif fault=='wrong-period':strength=peak*min(phase,128-phase)//64
                    elif fault=='wrong-hp':strength=measurement.damage_strength(hp['hp']-20,hp['maxHp'],frame)
                    elif fault=='no-off' and strength==0:strength=1
                    elif fault=='blue-off' and strength==0:mode,strength=2,2
                    v,u,m=palette(actor,mode,strength,sample['frame']*10+slot)
                    data['records']=[r for r in data['records'] if r['handle']['slot']!=slot]+[v]
                    data['uploads'][slot]=u;data['materials'][slot]=m
                    replaced+=native_palette(sample['frame'],u,m)
                row['events']=replaced
            result,_=replay(measurement.DAMAGE,bad)
            with self.subTest(fault=fault):
                self.assertFalse(result['passed'])
                self.assertTrue(result['failures'])
                self.assertNotIn('raw completed samples',str(result['failures']))


    def test_cardinal_front_line_requires_current_settled_pose_and_range(self):
        sample=deepcopy(blue_rows()[0]["initialSnapshot"])
        a=sample["actors"][0]
        a["engineObject"].update(x=588,y=405)
        for facing,x,z in ((0,588,404),(1,588,406),(2,586,405),(3,589,405)):
            with self.subTest(facing=facing):
                a["engineObject"]["facing"]=facing
                sample["player"].update(x=x,y=z,x_prev=x,y_prev=z,
                    pos_x=(x<<16)+32768,pos_z=(z<<16)+32768,movement_cmd=facing)
                self.assertTrue(measurement.AppearanceMeasurement._forward_line(sample,a))
                bad=deepcopy(sample);bad["player"]["pos_x"]-=1
                self.assertFalse(measurement.AppearanceMeasurement._forward_line(bad,a))
                bad=deepcopy(sample);bad["player"]["y"]+=1;bad["player"]["y_prev"]+=1
                bad["player"]["pos_z"]+=65536
                if facing in (2,3):
                    self.assertFalse(measurement.AppearanceMeasurement._forward_line(bad,a))
        a["engineObject"]["facing"]=2
        for x in (588,589,555):
            sample["player"].update(x=x,y=405,x_prev=x,y_prev=405,
                pos_x=(x<<16)+32768,pos_z=(405<<16)+32768,movement_cmd=2)
            self.assertFalse(measurement.AppearanceMeasurement._forward_line(sample,a))

    def test_hits_settled_rejects_hit_frame_idle_and_active_hop(self):
        meter=measurement.AppearanceMeasurement(measurement.DAMAGE,recipe(measurement.DAMAGE),SOURCE)
        for row in damage_rows():
            if row.get("command")=="teleport":break
            meter.observe_record(row)
        self.assertEqual(meter.failures,[])
        self.assertTrue(meter.stage("two-red-hits"))
        # Copied frame974/975 boundary shapes from test-09334f...;
        # these controls grant no native motion or palette proof.
        meter.hits["cyndaquil"][-1]["frame"]=974
        settled=deepcopy(meter.latest);settled["frame"]=988
        player=settled["player"]
        player.update(flags=537945137,x_prev=player["x"],y_prev=player["y"],movement_cmd=255)
        actor=next(a for a in settled["actors"] if a["role"]=="MOUNTED")
        actor.update(motionPhase="IDLE",reservationId=0)
        meter.latest=settled
        self.assertTrue(meter.stage("hits-settled"))
        for fault in ("same-hit-frame","moving-hop","commit-pending","reservation","off-center","native-task","not-ready"):
            bad=deepcopy(settled);a=next(a for a in bad["actors"] if a["role"]=="MOUNTED")
            if fault=="same-hit-frame":bad["frame"]=974
            elif fault=="moving-hop":a.update(motionKind="HOP",motionPhase="MOVING",reservationId=27)
            elif fault=="commit-pending":a.update(motionPhase="COMMIT_PENDING",reservationId=27)
            elif fault=="reservation":a["reservationId"]=27
            elif fault=="off-center":bad["player"]["pos_z"]+=1
            elif fault=="native-task":bad["fieldControl"]["taskPointer"]=0x02204000
            else:bad["player"]["flags"]=2
            meter.latest=bad
            with self.subTest(fault=fault):self.assertFalse(meter.stage("hits-settled"))
        for fault in ("stale-epoch","wrong-role","unverified"):
            bad=deepcopy(settled);a=next(a for a in bad["actors"] if a["role"]=="MOUNTED")
            if fault=="stale-epoch":bad["context"]["fieldEpoch"]+=1
            elif fault=="wrong-role":a["role"]="FOLLOWER"
            else:a["identityVerified"]=False
            meter.latest=bad
            with self.subTest(fault=fault),self.assertRaises(ValueError):meter.stage("hits-settled")
        # The new stage cannot replace any two-hit or palette permission.
        meter.latest=settled;meter.hits["cyndaquil"].pop()
        self.assertFalse(meter.stage("hits-settled"))

    def test_damage_recipe_waits_for_settlement_before_nurse_warp(self):
        test=recipe(measurement.DAMAGE)
        self.assertEqual([a["id"] for a in test["actions"][:3]],
                         ["two-real-hits","settle-last-hit","normal-center"])
        wait=test["actions"][1]
        self.assertEqual(wait["op"],"wait")
        self.assertEqual(wait["args"],dict(predicate=dict(kind="measurement-stage",
            measurement=measurement.DAMAGE,stage="hits-settled",when="final")))
        self.assertEqual(wait["budget"],dict(maxSeconds=30,maxFrames=32,noProgressFrames=32))
        for fault in ("missing-wait","longer-wait","wrong-stage"):
            bad=deepcopy(test)
            if fault=="missing-wait":bad["actions"].pop(1)
            elif fault=="longer-wait":bad["actions"][1]["budget"]["maxFrames"]=33
            else:bad["actions"][1]["args"]["predicate"]["stage"]="two-red-hits"
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_test(bad)

    def test_one_hit_and_two_pulse_strengths_cannot_pass_two_hits(self):
        meter=measurement.AppearanceMeasurement(measurement.DAMAGE,recipe(measurement.DAMAGE),SOURCE)
        for row in damage_rows():
            samples=row.get('samples',[])
            if samples and samples[0]['frame']>=63:break
            meter.observe_record(row)
        self.assertEqual(meter.failures,[])
        self.assertEqual(len(meter.hits['cyndaquil']),1)
        self.assertEqual(meter.pulse_directions['cyndaquil'],{-1,1})
        self.assertGreaterEqual(len(meter.palettes['cyndaquil']),2)
        self.assertFalse(meter.stage('two-red-hits'))

    def test_exact_recipe_source_contract_and_current_shared_install(self):
        for kind in measurement.KINDS:
            with self.subTest(kind=kind):
                test=recipe(kind);evaluator=TestEvaluator(test);evaluator.install_measurements({kind:SOURCE})
                self.assertIn(kind,evaluator.measurements);self.assertTrue(evaluator.uses_raw_records)
                bad=deepcopy(test);bad['setup'][0]['args']['x']+=1
                with self.assertRaises(ValueError):validate_test(bad)
                bad=deepcopy(test);bad['actions'].append(dict(id='fake-heal',op='party',args=dict(slot=0,hp=90),
                    budget=dict(maxSeconds=1,maxFrames=1,noProgressFrames=1)))
                with self.assertRaises(ValueError):validate_test(bad)

    def test_actual_leaf_positive_replay_and_all_copied_faults(self):
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        for kind,factory in ((measurement.DAMAGE,damage_rows),(measurement.COOLDOWN,blue_rows)):
            rows=factory()
            result,_=replay(kind,rows)
            self.assertTrue(result['passed'],result['failures'])
            self.assertTrue(accepted_measurements(kind,result,record))
            for fault in faults(kind):
                with self.subTest(kind=kind,fault=fault):
                    rejected,control=replay(kind,rows,fault)
                    self.assertTrue(control.applied)
                    self.assertFalse(rejected['passed'])
                    self.assertTrue(validate_negative_result(kind,rejected,fault))
            with self.assertRaises(ValueError):validate_negative_result(kind,result,faults(kind)[0])

class PaletteWindowScopeControls(unittest.TestCase):
    def test_exact_owner_filter_and_unchanged_128_upload_cap(self):
        from unittest.mock import patch
        sample=blue_rows()[0]['initialSnapshot'];a=sample['actors'][0]
        v=view()
        for key in ('handle','subjectIdentity','species','roleId',*reader.GEN_KEYS):v[key]=deepcopy(a[key])
        obs,session=observer(v);obs.active=True;obs.refresh=[];obs.subject=None
        session.snapshot=lambda **kwargs:deepcopy(sample)
        bound=select_current_actor(sample,a);obs.select_subject(bound)
        self.assertTrue(obs._selected(v))
        for key in ('handle','subjectIdentity','species','roleId',*reader.GEN_KEYS):
            bad=deepcopy(v)
            if key=='handle':bad[key]['generation']+=1;bad[key]['value']+=1<<16
            else:bad[key]+=1
            with self.subTest(identity=key):self.assertFalse(obs._selected(bad))
        stale=deepcopy(bound);stale['handle']['fieldEpoch']+=1
        with self.assertRaisesRegex(ValueError,'stale fieldEpoch'):obs.select_subject(stale)
        # The actual Refresh prefix rejects unrelated Mankey before owner reads;
        # its SDK callbacks cannot consume any of the selected owner's quota.
        other=deepcopy(a);other.update(species=56,roleId=2)
        other['handle']['slot']=7;other['handle']['value']=other['handle']['generation']<<16|7
        session.rt=SimpleNamespace(ACTOR_DESCRIPTOR={})
        session.put(0x022E0000,struct.pack('<6I',0x022E1000,0,0,0,0,0));session.put(0x022E1000,bytes(88))
        session.emu.memory.register_arm9.r0=0x022E0000
        obs._owner=lambda slot:(_ for _ in ()).throw(AssertionError('excluded owner was read'))
        with patch('tools.overworld.actor_probe.decode_actor_state',return_value=other):
            for _ in range(127):
                self.assertIsNone(obs._refresh_before());self.assertIsNone(obs._upload_before())
        self.assertEqual(obs.upload_count,0)
        for expected in range(1,129):
            value=dict(view=deepcopy(v));obs.pending_upload=value
            self.assertEqual(obs._end_after(value,{})['uploadId'],expected)
        with self.assertRaisesRegex(ValueError,'cold completed boundary'):obs.select_subject(bound)
        value=dict(view=deepcopy(v));obs.pending_upload=value
        with self.assertRaisesRegex(ValueError,'palette upload budget exceeded'):obs._end_after(value,{})

    def test_actual_setup_selection_uses_cached_completed_frame_without_advance(self):
        import ast
        from unittest.mock import Mock
        # Execute the real two Session methods, not a mirrored prepare/snapshot.
        source=globals().get('RUNTIME_SOURCE',ROOT/'tools/overworld/devtools_runtime.py')
        node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='DevtoolsSession')
        methods=[n for n in node.body if isinstance(n,ast.FunctionDef) and n.name in ('prepare_observation','snapshot')]
        self.assertEqual({n.name for n in methods},{'prepare_observation','snapshot'})
        unit=ast.Module(body=[ast.ClassDef(name='CachedSession',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])
        def require(ok,message,*args):
            if not ok:raise ValueError(message)
        namespace=dict(deepcopy=deepcopy,require=require,DevtoolsFailure=ValueError)
        exec(compile(ast.fix_missing_locations(unit),str(source),'exec'),namespace)
        session=namespace['CachedSession']()
        # record.start precedes teleport/spawn/bind. A cold observer stays active
        # through these normal completed setup frames, then binds the current actor.
        sample=blue_rows()[0]['initialSnapshot'];a=sample['actors'][0]
        session.emu=object();session.sample_error=None;session.boot_recovery=None
        session.prepared=True;session.completed_frames=762
        session.rt=SimpleNamespace(EXECUTED_FRAME_COUNT=1200)
        session.latest_frame=deepcopy(sample);session.latest_frame.update(frame=762,nativeCycle=1200)
        session.latest_resolved_profiles={};session.party_getter_hooks=SimpleNamespace(callbacks={},retire_empty=Mock(return_value=True))
        session.party_snapshot=Mock(side_effect=AssertionError('selection scanned party'))
        session.terrain=Mock(side_effect=AssertionError('selection scanned terrain'))
        session._snapshot=Mock(side_effect=AssertionError('selection rebuilt a live frame'))
        session.step=Mock(side_effect=AssertionError('selection advanced the game'))
        obs,_=observer(view());obs.session=session;obs.active=True;obs.refresh=[];obs.subject=None
        session.native_observation=SimpleNamespace(appearance=obs,hooks=SimpleNamespace(error=None))
        before=deepcopy(session.latest_frame)
        receipt=session.prepare_observation(appearance_subject=select_current_actor(session.latest_frame,a))
        self.assertEqual(obs.subject,select_current_actor(session.latest_frame,a))
        self.assertEqual((receipt['frame'],receipt['nativeCycle'],receipt['advancedFrames']),(762,1200,0))
        self.assertEqual(session.latest_frame,before)
        self.assertEqual((session.completed_frames,session.rt.EXECUTED_FRAME_COUNT),(762,1200))
        self.assertEqual(obs.upload_count,0)
        self.assertEqual(len(receipt['removed']),9)
        session.party_snapshot.assert_not_called();session.terrain.assert_not_called()
        session._snapshot.assert_not_called();session.step.assert_not_called()
        self.assertEqual(session.prepare_observation(appearance_subject=obs.subject),receipt)
        self.assertEqual(session.party_getter_hooks.retire_empty.call_count,9)
        # Selecting cannot erase already counted setup uploads to obtain a quota.
        obs.upload_count=1
        with self.assertRaisesRegex(ValueError,'cold completed boundary'):
            session.prepare_observation(appearance_subject=obs.subject)
        self.assertEqual(obs.upload_count,1)



class AmbushCooldownControls(unittest.TestCase):
    """Copied native envelopes; never game proof."""
    @staticmethod
    def rows():
        initial=deepcopy(blue_rows()[0]['initialSnapshot']);actor=initial['actors'][0]
        actor.update(species=70);initial['pokemonCombat']['targets'][0]['species']=70
        initial['player'].update(x=585,y=403,x_prev=585,y_prev=403,
            pos_x=(585<<16)+0x8000,pos_z=(403<<16)+0x8000,flags=1,movement_cmd=255)
        rows=[dict(phase='setup',initialSnapshot=initial),bind(initial,'weepinbell')]
        for frame in range(2,129):
            sample=deepcopy(initial);sample.update(frame=frame,actorFrame=frame+100,nativeCycle=frame+1000)
            sample['pokemonCombat'].update(frame=frame,nativeCycle=frame+1000)
            active=frame<92;sample['actors'][0]['matchedLayerMask']=(1<<measurement.AMBUSH) if active else 0
            data=appearance(sample)
            state=dict(application=measurement.AMBUSH,enabled=True,flags=3 if active else 2,
                durationFrames=90,cooldownFrames=126,activeUntil=192,cooldownUntil=228)
            data['conditions'][0]=dict(available=True,owner=dict(actor=deepcopy(actor)),frame=frame+100,
                enabledMask=1<<measurement.AMBUSH,states=[state])
            events=[]
            if 92<=frame<128:
                v,u,m=palette(actor,2,2,1);data['records']=[v];data['uploads'][0]=u;data['materials'][0]=m
                if frame==92:events=native_palette(frame,u,m)
            if frame==128:data['clears'][0]=clear(actor,frame)
            sample['pokemonAppearance']=data;rows.append(raw_sample(sample,events,action='blue-and-natural-expiry'))
        return rows

    def test_real_own_timed_cooldown_and_all_copied_faults(self):
        kind=measurement.AMBUSH_COOLDOWN;rows=self.rows();result,_=replay(kind,rows)
        self.assertTrue(result['passed'],result['failures'])
        meter=result['measurements'][kind]
        self.assertEqual(meter['firstActivation']['triggerFrame'],102)
        self.assertEqual(meter['firstCooldown']['actorFrame'],192)
        self.assertEqual(meter['blueConditions']['states'][0]['cooldownUntil'],228)
        self.assertEqual(meter['expired']['frame'],128)
        accepted_measurements(kind,result,dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[])))
        for fault in faults(kind):
            with self.subTest(fault=fault):
                rejected,control=replay(kind,rows,fault)
                self.assertTrue(control.applied);self.assertFalse(rejected['passed'])
                self.assertTrue(validate_negative_result(kind,rejected,fault))

    def test_active_only_incomplete_or_wrong_entire_set_cannot_pass(self):
        rows=self.rows();kind=measurement.AMBUSH_COOLDOWN
        early=[r for r in rows if not r.get('samples') or r['samples'][0]['frame']<=91]
        result,_=replay(kind,early);self.assertFalse(result['passed'])
        for fault in ('omitted','unexpected-row','stale-owner','wrong-clock','early-clear'):
            bad=deepcopy(rows)
            for row in bad:
                if not row.get('samples'):continue
                sample=row['samples'][0];data=sample['pokemonAppearance'];conditions=data['conditions'][0]
                if fault=='omitted':conditions['states']=[]
                elif fault=='unexpected-row':conditions['states'].append(dict(conditions['states'][0],application=measurement.RAM))
                elif fault=='stale-owner':conditions['owner']['actor']['handle']['generation']+=1
                elif fault=='wrong-clock':conditions['frame']+=1
                elif sample['frame']>=92:
                    data['records']=[];data['clears'][0]=clear(sample['actors'][0],sample['frame'])
            result,_=replay(kind,bad)
            with self.subTest(fault=fault):self.assertFalse(result['passed'])


if __name__=="__main__":unittest.main()
