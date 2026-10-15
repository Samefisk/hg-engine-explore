"""Actual linked identities and installed callbacks; no game or native core."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_observer import NativeObservation, NativeObservationError
from tools.overworld.devtools_runtime import _elf_code
from tools.overworld.devtools_engine import REPO
from tools.overworld.devtools_query_observer import relocated_image
from tools.overworld.pack_query_code_addon import package

spec = importlib.util.spec_from_file_location('slam_admission_draft', Path(__file__).with_name('devtools_slam_admission_observer.py'))
draft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(draft)


class Hooks:
    def __init__(self): self.callbacks, self.sequence = {}, 0
    def add(self, address, callback):
        self.sequence += 1
        self.callbacks[self.sequence] = (address & ~1, callback)
        return self.sequence
    def remove(self, token): self.callbacks.pop(token)
    def call(self, address):
        for owner, callback in list(self.callbacks.values()):
            if owner == address & ~1: callback()


class Fixture:
    def __init__(self):
        self.repo = REPO
        self.memory, self.reads, self.code_regions = {}, [], []
        self.prepared, self._throw_interactions_window = False, True
        self.regs = SimpleNamespace(**{f'r{i}': 0 for i in range(13)}, sp=0x027E3800, lr=0)
        self.emu = SimpleNamespace(memory=SimpleNamespace(register_arm9=self.regs))
        self.hooks = Hooks()
        self.world = dict(fieldPointer=0x02231000, statePointer=0x02230100, mapId=33, fieldEpoch=2, mapGeneration=3)
        self.subject = dict(status='observed-public-subject', slot=0, species=143, form=0, level=50,
            role='WILD', subjectIdentity=99, handle=dict(slot=0, generation=1, fieldEpoch=2, mapGeneration=3,
            encounterGeneration=4, value=0x10000), authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1)
        self.source = dict(object=0x02211000, species=143, form=0, level=50, personality=99, encounter_generation=4, active=1)
        self.engine = dict(pointer=self.source['object'], current_manager=0x02222000, manager_index=0, object_manager=0x02222000)
        self.mount = dict(active=True, role='MOUNTED', inputOwnership=1, presentationAttached=True,
            handle=dict(slot=7, generation=1, fieldEpoch=2, mapGeneration=3, encounterGeneration=9, value=0x10007))
        self.mount_source = dict(object=0x02212000, species=155, object_id=0xE7, active=1)
        self.poses = {0x02210000: dict(x=585, y=407, flags=1, pos_x=(585<<16)+32768, pos_z=(407<<16)+32768),
                      0x02212000: dict(x=585, y=407, flags=1, pos_x=(585<<16)+32768, pos_z=(407<<16)+32768)}
        self.rt = SimpleNamespace(REPO=self.repo, WILD_STATE=self.world['statePointer'],
            actor_state=lambda _e, slot: deepcopy(self.mount if slot == 7 else self.subject),
            wild_spawn=lambda _e, slot: deepcopy(self.mount_source if slot == 7 else self.source),
            object_state=lambda _e, pointer: deepcopy(self.poses[pointer]),
            player_ptr=lambda _e: 0x02210000,
            live_wild_object_identity=lambda _e, slot: dict(pointer=self.mount_source['object']) if slot==7 else deepcopy(self.engine))
        for file, _name, address, size, _sha in draft.PINS.values():
            code = _elf_code(self.repo/'build'/file, address, size)
            self.code_regions.append((address, code)); self.put(address, code)
        self.observer = NativeObservation(self, self.hooks, _elf_code)
        self.observer._clock = lambda: dict(actorFrame=100, nativeCycle=10)
        self.observer._subject = lambda _slot: deepcopy(self.subject)
        self.observer._world_context = lambda: deepcopy(self.world)
        self.observer._chain_current = lambda _slot: (deepcopy(self.subject), deepcopy(self.source), deepcopy(self.engine), deepcopy(self.world))
        rawelf = (self.repo/'build/overworld_query_code_addon/image.elf').read_bytes()
        blob, receipt = package(rawelf)
        image = blob[64:64+receipt['imageBytes']]
        loaded = relocated_image(image, receipt, 0x02180000)
        raw_owner = struct.pack('<4I2HIB3s', 0x0217FFC0, len(blob), 0x02180000, self.world['fieldPointer'], 2, 3, 21, 1, bytes(3))
        self.query = SimpleNamespace(active=True, image=image, state=0x023C2308,
            loaded=dict(field=self.world['fieldPointer'], fieldEpoch=2, mapGeneration=3, entry=0x02180000,
                        expected=loaded, rawHex=raw_owner.hex()))
        self.observer.query = self.query
        self.put(self.query.state, raw_owner); self.put(0x02180000, loaded)
        self.probe = draft.SlamAdmissionObserver(self.observer)
        offset, size, _sha = draft.QUERY_OCCUPANCY
        expected = loaded[offset:offset+size]
        sites = [n for n in range(0, len(expected)-1, 2)
                 if int.from_bytes(expected[n:n+2],'little') & 0xFF87 == 0x4780]
        if sites != [0x60, 0x15C]: raise AssertionError(sites)
        self.query_call = (0x02180000+draft.QUERY_OCCUPANCY[0])+draft.QUERY_OCCUPANCY_CALL
        self.query_register = int.from_bytes(expected[draft.QUERY_OCCUPANCY_CALL:draft.QUERY_OCCUPANCY_CALL+2], 'little') >> 3 & 15
    def put(self, address, raw): self.memory.update({address+i:b for i,b in enumerate(raw)})
    def read(self, address, size):
        self.reads.append((address,size)); return bytes(self.memory.get(address+i,0) for i in range(size))
    def packaged_code(self, address, size):
        for base, raw in self.code_regions:
            if base <= address and address+size <= base+len(raw): return raw[address-base:address-base+size]
        return b''
    def write(self, *_a): raise AssertionError('diagnostic wrote guest data')
    def native_call(self, *_a): raise AssertionError('diagnostic called guest code')
    def enter(self, key, words, args, sp, lr):
        self.put(sp, struct.pack('<'+'I'*len(words), *words))
        self.regs.sp, self.regs.lr = sp, lr
        for i, value in enumerate(args): setattr(self.regs, f'r{i}', value)
        self.hooks.call(draft.PINS[key][2])
    def returned(self, value, sp, lr):
        self.regs.r0, self.regs.sp = value, sp
        self.hooks.call(lr)
    def begin(self):
        self.enter('attempt', [1,585,407,585,407,0,0x40040408],
                   [self.world['statePointer'],self.world['fieldPointer'],0,0x02229000],0x027E3800,0x023D6883)
    def landing(self):
        self.enter('landing', [585,407,585,407],
                   [self.world['statePointer'],0,self.world['fieldPointer'],0x4001],0x027E37A0,0x023D0FBF)
    def occupancy(self, occupied):
        setattr(self.regs, f'r{self.query_register}', draft.PINS['occupancy'][2] | 1)
        self.enter('occupancy',[407,0,1], [self.world['fieldPointer'],self.source['object'],0,585],
                   0x027E36A0, self.query_call+3)
        self.returned(int(occupied),0x027E36A0,self.query_call+2)
    def finish(self, occupied):
        self.returned(5 if occupied else 0,0x027E37A0,0x023D0FBE)
        self.returned(int(not occupied),0x027E3800,0x023D6882)
        return self.observer.pending[-1]


class SlamAdmissionObserverTests(unittest.TestCase):
    def check_receipt(self, occupied):
        f=Fixture(); f.begin(); f.landing(); f.occupancy(occupied); row=f.finish(occupied)
        self.assertEqual(row['observation'],'slam-admission')
        self.assertEqual(row['started'],not occupied)
        landing=row['landings'][0]; detail=landing['occupancy'][0]
        self.assertEqual(landing['decisionName'],'OCCUPIED' if occupied else 'ACCEPTED')
        self.assertEqual(detail['mode'],1)
        self.assertEqual(detail['ignoredObject'],f.source['object'])
        self.assertEqual(detail['collisionIgnoredObject'],0)
        self.assertNotEqual(detail['player']['pointer'], detail['followerSlot']['object']['pointer'])
        self.assertEqual(detail['player']['pose']['x'], detail['followerSlot']['object']['pose']['x'])
        self.assertEqual(detail['followerSlot']['actor']['role'],'MOUNTED')
        self.assertFalse(row['acceptedProof'])
        self.assertLess(max(size for _,size in f.reads), 3000)
        # Cleanup owns only its listeners, preserving other record-window taps.
        other=f.hooks.add(0x02001000, lambda:None); f.observer.tokens.append(other)
        f.probe.close(); self.assertEqual(f.observer.tokens,[other]); self.assertFalse(f.probe.contexts)
    def test_rejected_landing_red_receipt(self): self.check_receipt(True)
    def test_accepted_landing_green_receipt(self): self.check_receipt(False)
    def test_changed_full_subject_owner_rejects(self):
        f=Fixture(); f.begin(); f.subject['handle']['encounterGeneration'] += 1
        with self.assertRaisesRegex(NativeObservationError,'full subject or world owner changed'): f.landing()
        self.assertFalse(f.observer.pending)
        f.probe.close(); self.assertFalse(f.hooks.callbacks)
    def test_changed_loaded_query_owner_rejects(self):
        f=Fixture(); f.begin(); f.landing(); f.put(f.query.state,bytes(28))
        with self.assertRaisesRegex(NativeObservationError,'loaded Query owner changed'): f.occupancy(True)
        self.assertFalse(f.observer.pending)
        f.probe.close(); self.assertFalse(f.hooks.callbacks)
    def test_wrong_callback_site_rejects(self):
        f=Fixture(); f.begin(); f.landing()
        f.query_call = (0x02180000+draft.QUERY_OCCUPANCY[0]) + 0x60
        expected = f.query.loaded['expected']
        f.query_register = int.from_bytes(expected[draft.QUERY_OCCUPANCY[0]+0x60:draft.QUERY_OCCUPANCY[0]+0x62], 'little') >> 3 & 15
        with self.assertRaisesRegex(NativeObservationError,'occupancy caller site differs'): f.occupancy(True)
        self.assertFalse(f.observer.pending)
        f.probe.close(); self.assertFalse(f.hooks.callbacks)

    def test_exact_query_owner_rejects_wrong_duplicate_and_ambiguous_selector(self):
        image=(REPO/'build/overworld_query_code_addon/image.elf').read_bytes()
        table=struct.unpack_from('<I',image,32)[0];stride,count=struct.unpack_from('<HH',image,46)
        sections=[struct.unpack_from('<10I',image,table+i*stride) for i in range(count)]
        owners=[]
        for row in sections:
            if row[1]!=2:continue
            names=sections[row[6]];strings=image[names[4]:names[4]+names[5]]
            for offset in range(row[4],row[4]+row[5],16):
                label,address,size,info,_other,index=struct.unpack_from('<IIIBBH',image,offset)
                if strings[label:].split(b'\0',1)[0]==b'Occupancy':owners.append((offset,address,size,index))
        self.assertEqual(len(owners),2)
        selected=next(row for row in owners if (row[1]&~1,row[2])==(0x02080000+draft.QUERY_OCCUPANCY[0],436))
        other=next(row for row in owners if row is not selected)
        self.assertEqual(draft._query_occupancy_owner(SimpleNamespace(read_bytes=lambda:image)),(selected[1]&~1,436))
        for fault in ('wrong-duplicate','ambiguous','body'):
            with self.subTest(control=fault):
                bad=bytearray(image)
                if fault=='wrong-duplicate':struct.pack_into('<II',bad,selected[0]+4,other[1],other[2])
                elif fault=='ambiguous':struct.pack_into('<II',bad,other[0]+4,selected[1],selected[2])
                else:
                    section=sections[selected[3]];body=section[4]+(selected[1]&~1)-section[3];bad[body+435]^=1
                with self.assertRaisesRegex(NativeObservationError,'exact owner|full linked body'):
                    draft._query_occupancy_owner(SimpleNamespace(read_bytes=lambda:bytes(bad)))


if __name__=='__main__': unittest.main()
