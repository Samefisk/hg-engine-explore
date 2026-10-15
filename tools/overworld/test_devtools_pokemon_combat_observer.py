"""Positive and known-bad native-memory controls for the combat reader."""

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from scripts.generate_player_health_debug import checked_combat, BASE
from tools.overworld.devtools_pokemon_combat_observer import (observe_pokemon_combat,
    WILD_STATE_SIZE, WILD_SPAWN_SIZE, WILD_MOVEMENT_COOLDOWN,
    WILD_MOVEMENT_EMOTE_TIMER, WILD_TIMER_PREFIX_SIZE, WILD_FIELD_OFFSET,
    WILD_MOVEMENT_SPOT_STATE, WILD_MOVEMENT_ACTOR_CONTROL_MODE,
    WILD_MOVEMENT_CRASH_SHAKE_TIMER, WILD_MOVEMENT_CRASH_SHAKE_BASE_X,
    WILD_MOVEMENT_CRASH_SHAKE_BASE_Z, WILD_CRASH_SHAKE_SIZE,
    WILD_RUNTIME_OFFSET, WILD_RUNTIME_SIZE, RUNTIME_THROW_OFFSET,
    RUNTIME_RETURN_MOVES_OFFSET, RETURN_MOVE_SIZE, RUNTIME_MOTION_IDENTITIES_OFFSET,
    RUNTIME_DESPAWN_PENDING_MASK_OFFSET, WILD_SPAWN_RUN_READ_OFFSET,
    WILD_CAPTURE_MASK_READ_OFFSET, WILD_CONTROL_READ_OFFSET, _return_diagnostics,
    RUNTIME_CONDITIONS_OFFSET, CATALOG_BLOB_VERSION, CONDITIONS_SIZE, CONDITIONS_BINDINGS_OFFSET,
    PREPARED_ACTOR_SIZE, BINDINGS_SIZE, CONDITION_STATE_SIZE,
    CONDITIONS_PUBLICATION_OFFSET, CONDITIONS_PUBLICATION_SIZE, INTERACTION_READ_BUDGET)
from tools.overworld.devtools_runtime import DevtoolsFailure
from tools.overworld.actor_probe import decode_actor_state
from tools.overworld.devtools_field_cleanup import symbol
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_application_bank import decode_application_bank, local_application
from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.test_devtools_player_health_observer import Fixture, FIELD, SAVE


ROOT = Path(__file__).resolve().parents[2]
WILD_IMAGE = (ROOT/'build/linked.o').read_bytes()
WILD_STATE = symbol(WILD_IMAGE,'sOverworldWildSpawnState',1,expected_size=WILD_STATE_SIZE)[0]
RESIDENT = 0x023C0000
COMBAT = BASE + 0x3500
ACTOR_SLOT = 1
RAM_APPLICATION = application_index("apply-ram")
THROW_APPLICATION = application_index("apply-throw")
THROW_CARGO_CONDITION = _stable_condition_id("throw", "condition-throw-selects-cargo")


class CombatObserverTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(Path(self.temp.name))
        f = self.fixture
        for relative in ("data/overworld_behavior_profiles.json",
                         "include/overworld_wild_behavior_data.h",
                         "include/constants/species.h"):
            target=f.root/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/relative,target)
        f.image.extend(bytes(max(0,0x3800-len(f.image))))
        struct.pack_into("<IHH", f.image, 0x3000, 0x434F4D42, 1, 52)
        symbols = dict(sCombat=(COMBAT,292),gOverworldCombatEntry=(BASE+0x3000,52),
                       gOverworldWildResidentData=(RESIDENT,22))
        layout = checked_combat(symbols, f.image, ROOT/'src/player_health_pokemon.c')
        f.descriptor['combat'] = layout
        f.descriptor['overlay'].update(fileSize=len(f.image),sha256=hashlib.sha256(f.image).hexdigest())
        f.session.overlay_code_regions[161] = (BASE,bytes(f.image))
        f.session.rt.WILD_STATE = WILD_STATE
        (f.root/'build/linked.o').write_bytes(WILD_IMAGE)
        f.save_descriptor();f.write(BASE,f.image)
        self.source=dict(object=0x02280000,personality=991,map_id=33,species=143,form=0,
                         level=50,active=1,object_id=0xE0+ACTOR_SLOT,encounter_generation=1)
        wild=bytearray(WILD_TIMER_PREFIX_SIZE)
        struct.pack_into('<IIHHBB2xBBH',wild,ACTOR_SLOT*WILD_SPAWN_SIZE,
                         *self.source.values())
        wild[WILD_MOVEMENT_COOLDOWN+ACTOR_SLOT]=17
        wild[WILD_MOVEMENT_EMOTE_TIMER+ACTOR_SLOT]=0
        wild[WILD_MOVEMENT_SPOT_STATE+ACTOR_SLOT]=2
        wild[WILD_MOVEMENT_COOLDOWN]=93
        wild[WILD_MOVEMENT_EMOTE_TIMER]=94
        wild[WILD_MOVEMENT_SPOT_STATE]=6
        f.write(WILD_STATE,wild)
        control_modes=bytearray(10);control_modes[0]=1
        f.write(WILD_STATE+WILD_MOVEMENT_ACTOR_CONTROL_MODE,control_modes)
        crash_shake=bytearray(WILD_CRASH_SHAKE_SIZE)
        crash_shake[ACTOR_SLOT]=6;crash_shake[0]=93
        for base_offset,values in ((WILD_MOVEMENT_CRASH_SHAKE_BASE_X,(-123456,585*4096)),
                                   (WILD_MOVEMENT_CRASH_SHAKE_BASE_Z,(654321,-405*4096))):
            struct.pack_into('<2i',crash_shake,base_offset-WILD_MOVEMENT_CRASH_SHAKE_TIMER,*values)
        f.write(WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER,crash_shake)
        record=bytearray(292);struct.pack_into('<III',record,0,FIELD,SAVE,WILD_STATE)
        struct.pack_into('<I7H8B',record,12+ACTOR_SLOT*28,991,33,1,1,143,230,210,1,0,50,1,60,6,1,0,20)
        saved=[0]*10;saved[ACTOR_SLOT]=210
        f.write(COMBAT,record);f.write(RESIDENT+2,struct.pack('<10H',*saved))
        actor_descriptor=json.loads((ROOT/'build/overworld-system.debug.json').read_text())
        actor_image=(ROOT/'build/overworld_actor_system_overlay_linked.o').read_bytes()
        address,size,_=symbol(actor_image,'gOverworldActorSystemState',1,'.bss')
        self.assertEqual(actor_descriptor['state']['address'],address)
        # A stopped build can leave the old JSON beside a new ELF. This host
        # fixture uses the exact compiled layout; the live reader never repairs
        # stale descriptors and still rejects that pairing below.
        stride,policy_size={2448:(172,32),2440:(176,36)}[size]
        actor_descriptor['state'].update(size=size,capacity=2448,actorStride=stride)
        actor_descriptor['structures']['actorPolicyState']=policy_size
        f.session.rt.ACTOR_DESCRIPTOR=actor_descriptor
        (f.root/'build/overworld_actor_system_overlay_linked.o').write_bytes(actor_image)
        facade=actor_descriptor['facade']
        facade_bytes=struct.pack('<IHH4I',0x5341574F,2,24,
            *(facade['callbacks'][key] for key in ('validate','apply','tick','inspect')))
        f.write(facade['address'],facade_bytes)
        f.session.packaged_code=lambda address,size:facade_bytes if (address,size)==(facade['address'],24) else b''
        header=bytearray(48);struct.pack_into('<IHHIH',header,0,0x5353574F,2,actor_descriptor['state']['size'],12,1)
        struct.pack_into('<H',header,46,1)
        state_address=actor_descriptor['state']['address'];f.write(state_address,header)
        values=[2,88,ACTOR_SLOT,1,1,1,1,0]+[991,0,0,0,0,1,1,1]
        values += [585,405,585,405,585,405,585,406]+[0,13,42,143]
        values += [0,50,1,0,2,2,0,0,0,2,0,0,1,1,7,0]
        public=struct.pack(actor_descriptor['publicLayouts']['actorState']['format'],*values)
        motion=bytearray(52)
        struct.pack_into('<HBBHH4h2iHH',motion,0,1,2,1,1,0,585,405,585,406,0,0,13,42)
        motion[28:38]=bytes((1,1,16,0,0,0,0,1,1,1))
        struct.pack_into('<4H4B',motion,40,0,0,0,0,2,0,0,0)
        self.actor_pointer=state_address+68+ACTOR_SLOT*actor_descriptor['state']['actorStride']
        f.write(self.actor_pointer,public+motion)
        actor=decode_actor_state(public,actor_descriptor)
        actor.update(identityVerified=True,sourceIdentity=dict(self.source))
        self.snapshot=dict(frame=12,actorFrame=12,nativeCycle=1000,
            context=dict(mapId=33,fieldEpoch=1,mapGeneration=1),party=[],actors=[actor])

    def read(self):
        return observe_pokemon_combat(self.fixture.session,self.snapshot)

    def write_actor_motion(self, raw):
        self.fixture.write(self.actor_pointer,raw)
        actor=decode_actor_state(bytes(raw[:88]),self.fixture.session.rt.ACTOR_DESCRIPTOR)
        actor.update(identityVerified=True,sourceIdentity=dict(self.source))
        self.snapshot['actors']=[actor]

    def committed_pause(self, suspended=False):
        raw=bytearray(self.fixture.read(self.actor_pointer,140))
        struct.pack_into('<3H',raw,64,13,13,0)
        raw[77]=5 if suspended else 4
        raw[88+34]=5
        struct.pack_into('<4H4B',raw,88+40,13,5,1,1,5 if suspended else 4,
                         4 if suspended else 0,1,0)
        self.write_actor_motion(raw)
        return raw

    def use_actor_layout(self, size, stride, policy_size):
        """Change only the copied host ELF and memory fixture, never the build."""
        f=self.fixture
        descriptor=f.session.rt.ACTOR_DESCRIPTOR
        state=descriptor['state']
        raw=f.read(self.actor_pointer,140)
        image_path=f.root/'build/overworld_actor_system_overlay_linked.o'
        image=bytearray(image_path.read_bytes())
        section_offset=struct.unpack_from('<I',image,32)[0]
        section_stride,section_count=struct.unpack_from('<2H',image,46)
        sections=[struct.unpack_from('<10I',image,section_offset+i*section_stride)
                  for i in range(section_count)]
        matches=[]
        for section in sections:
            if section[1]!=2:
                continue
            strings=sections[section[6]]
            names=image[strings[4]:strings[4]+strings[5]]
            for pos in range(section[4],section[4]+section[5],16):
                label,address,old_size,info,_,owner=struct.unpack_from('<IIIBBH',image,pos)
                if names[label:].split(b'\0',1)[0]==b'gOverworldActorSystemState':
                    matches.append((pos,address,old_size,info,owner))
        self.assertEqual(len(matches),1)
        pos,address,old_size,info,owner=matches[0]
        self.assertEqual((address,old_size,info&15),
                         (state['address'],state['size'],1))
        self.assertEqual((sections[owner][3],sections[owner][5]),(address,old_size))
        struct.pack_into('<I',image,pos+8,size)
        struct.pack_into('<I',image,section_offset+owner*section_stride+20,size)
        image_path.write_bytes(image)
        state.update(size=size,capacity=2448,actorStride=stride)
        descriptor['structures']['actorPolicyState']=policy_size
        f.write(state['address']+6,struct.pack('<H',size))
        self.actor_pointer=state['address']+68+ACTOR_SLOT*stride
        f.write(self.actor_pointer,raw)
        if hasattr(f.session,'pokemon_combat_motion_layout'):
            del f.session.pokemon_combat_motion_layout

    def test_native_layout_reads_actual_resident_hp_and_guard(self):
        result=self.read();target=result['targets'][0]
        self.assertEqual((target['hp'],target['maxHp'],target['immunityFrames'],target['hitCount']),
                         (210,230,60,1))
        self.assertEqual(target['hpSource'],'wild-resident')
        self.assertTrue(target['hpMirrorMatches'])
        self.assertEqual(result['observationBoundary'],'main-task-queue-completion')
        self.assertEqual(target['motion']['plan']['origin'],[585,405])
        self.assertEqual(target['motion']['plan']['flags'],1)
        self.assertEqual(target['motion']['plan']['arcHeightQ4'],16)

    def test_wild_timers_read_one_current_prefix_and_refresh_without_a_combat_row(self):
        reads=[]
        self.fixture.session.read=lambda address,size: (reads.append((address,size))
            or self.fixture.read(address,size))
        self.fixture.write(COMBAT+12+ACTOR_SLOT*28+20,b'\0')
        result=self.read()
        self.assertEqual(result['targets'],[])
        timer=result['movementTimers'][0]
        self.assertEqual(timer['handle'],self.snapshot['actors'][0]['handle'])
        self.assertEqual(timer['sourceIdentity'],self.source)
        self.assertEqual((timer['slot'],timer['movementCooldown'],timer['movementEmoteTimer'],
                          timer['movementSpotState'],timer['movementActorControlMode']),
                         (ACTOR_SLOT,17,0,2,0))
        self.assertEqual((timer['movementCrashShakeTimer'],timer['movementCrashShakeBaseX'],
                          timer['movementCrashShakeBaseZ']),(6,585*4096,-405*4096))
        self.assertEqual(timer['rawCrashShakeHex'],struct.pack('<Bii',6,585*4096,-405*4096).hex())
        self.assertEqual(reads.count((WILD_STATE,WILD_TIMER_PREFIX_SIZE)),1)
        self.assertEqual(reads.count((WILD_STATE+WILD_MOVEMENT_ACTOR_CONTROL_MODE,10)),1)
        self.assertEqual(reads.count((WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER,WILD_CRASH_SHAKE_SIZE)),1)
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_COOLDOWN+ACTOR_SLOT,b'\x10')
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_EMOTE_TIMER+ACTOR_SLOT,b'\x09')
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_SPOT_STATE+ACTOR_SLOT,b'\x03')
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_ACTOR_CONTROL_MODE+ACTOR_SLOT,b'\x01')
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER+ACTOR_SLOT,b'\0')
        refreshed=self.read()['movementTimers'][0]
        self.assertEqual((refreshed['movementCooldown'],refreshed['movementEmoteTimer'],
                          refreshed['movementSpotState'],refreshed['movementActorControlMode']),(16,9,3,1))
        self.assertEqual(reads.count((WILD_STATE,WILD_TIMER_PREFIX_SIZE)),2)
        self.assertEqual(reads.count((WILD_STATE+WILD_MOVEMENT_ACTOR_CONTROL_MODE,10)),2)
        self.assertEqual(reads.count((WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER,WILD_CRASH_SHAKE_SIZE)),2)
        self.assertEqual((refreshed['movementCrashShakeTimer'],refreshed['movementCrashShakeBaseX'],
                          refreshed['movementCrashShakeBaseZ']),(0,585*4096,-405*4096))
        self.assertEqual(refreshed['rawCrashShakeHex'],struct.pack('<Bii',0,585*4096,-405*4096).hex())

    def test_wild_crash_shake_preserves_signed_fx32_extremes_and_raw_bytes(self):
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER+ACTOR_SLOT,b'\xff')
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_BASE_X+ACTOR_SLOT*4,
                           struct.pack('<i',-0x80000000))
        self.fixture.write(WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_BASE_Z+ACTOR_SLOT*4,
                           struct.pack('<i',0x7fffffff))
        row=self.read()['movementTimers'][0]
        self.assertEqual((row['movementCrashShakeTimer'],row['movementCrashShakeBaseX'],
                          row['movementCrashShakeBaseZ']),(255,-0x80000000,0x7fffffff))
        self.assertEqual(row['rawCrashShakeHex'],'ff00000080ffffff7f')

    def test_wild_crash_shake_rejects_incomplete_or_nonbyte_span(self):
        wanted=(WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER,WILD_CRASH_SHAKE_SIZE)
        for bad in (bytes(WILD_CRASH_SHAKE_SIZE-1),[0]*WILD_CRASH_SHAKE_SIZE,None):
            with self.subTest(kind=type(bad).__name__):
                self.fixture.session.read=lambda a,n:bad if (a,n)==wanted else self.fixture.read(a,n)
                with self.assertRaisesRegex(DevtoolsFailure,'crash-shake read is incomplete'):self.read()

    def test_wild_control_mode_rejects_unknown_mode_and_incomplete_array(self):
        address=WILD_STATE+WILD_MOVEMENT_ACTOR_CONTROL_MODE
        for mode in (2,255):
            with self.subTest(mode=mode):
                self.fixture.write(address+ACTOR_SLOT,bytes((mode,)))
                with self.assertRaisesRegex(DevtoolsFailure,'actor control mode is invalid'):self.read()
        self.fixture.write(address+ACTOR_SLOT,b'\0')
        self.fixture.session.read=lambda a,n: (
            self.fixture.read(a,n-1) if (a,n)==(address,10) else self.fixture.read(a,n))
        with self.assertRaisesRegex(DevtoolsFailure,'control-mode read is incomplete'):self.read()

    def test_wild_control_mode_has_no_read_without_a_current_combat_owner(self):
        reads=[];self.fixture.session.read=lambda a,n:(reads.append((a,n)) or self.fixture.read(a,n))
        self.fixture.write(COMBAT,struct.pack('<I',FIELD+4))
        self.assertFalse(self.read()['available'])
        self.assertNotIn((WILD_STATE+WILD_MOVEMENT_ACTOR_CONTROL_MODE,10),reads)
        self.assertNotIn((WILD_STATE+WILD_MOVEMENT_CRASH_SHAKE_TIMER,WILD_CRASH_SHAKE_SIZE),reads)

    def test_wild_timers_reject_every_stale_source_identity_field(self):
        for offset in (0,4,8,10,12,13,16,17,18):
            with self.subTest(offset=offset):
                pointer=WILD_STATE+ACTOR_SLOT*WILD_SPAWN_SIZE+offset
                old=self.fixture.read(pointer,1)
                self.fixture.write(pointer,bytes((old[0]^1,)))
                with self.assertRaisesRegex(DevtoolsFailure,'timer source is stale'):
                    self.read()
                self.fixture.write(pointer,old)
        for field in ('fieldEpoch','mapGeneration','encounterGeneration'):
            with self.subTest(field=field):
                handle=self.snapshot['actors'][0]['handle']
                handle[field]+=1
                with self.assertRaisesRegex(DevtoolsFailure,'timer source is stale'):
                    self.read()
                handle[field]-=1
        # Even before the combat row is initialized, its published full Actor
        # handle must match native memory; source personality alone is not enough.
        self.fixture.write(COMBAT+12+ACTOR_SLOT*28+20,b'\0')
        self.fixture.write(self.actor_pointer+4,b'\x02')
        with self.assertRaisesRegex(DevtoolsFailure,'different public actor'):
            self.read()

    def test_wild_timers_reject_short_read_or_a_different_linked_state(self):
        self.fixture.session.read=lambda address,size: (
            self.fixture.read(address,size-1) if (address,size)==(WILD_STATE,WILD_TIMER_PREFIX_SIZE)
            else self.fixture.read(address,size))
        with self.assertRaisesRegex(DevtoolsFailure,'timer read is incomplete'):
            self.read()
        self.fixture.session.read=self.fixture.read
        del self.fixture.session.pokemon_combat_layout
        self.fixture.session.rt.WILD_STATE=WILD_STATE+4
        with self.assertRaisesRegex(DevtoolsFailure,'linked owner'):
            self.read()
        self.fixture.session.rt.WILD_STATE=WILD_STATE
        image=bytearray(WILD_IMAGE)
        offset=struct.unpack_from('<I',image,32)[0]
        stride,count=struct.unpack_from('<2H',image,46)
        sections=[struct.unpack_from('<10I',image,offset+i*stride) for i in range(count)]
        matches=[]
        for section in sections:
            if section[1]!=2:continue
            strings=sections[section[6]]
            names=image[strings[4]:strings[4]+strings[5]]
            for pos in range(section[4],section[4]+section[5],16):
                label=struct.unpack_from('<I',image,pos)[0]
                if names[label:].split(b'\0',1)[0]==b'sOverworldWildSpawnState':matches.append(pos)
        self.assertEqual(len(matches),1)
        struct.pack_into('<I',image,matches[0]+8,WILD_STATE_SIZE-4)
        (self.fixture.root/'build/linked.o').write_bytes(image)
        with self.assertRaisesRegex(ValueError,'wrong-symbol-size'):
            self.read()

    def test_wild_timer_offsets_match_the_actual_arm_header(self):
        source='#include "include/overworld_wild_spawns_internal.h"\n'
        source+=f'\n_Static_assert(sizeof(OverworldWildSpawnState)=={WILD_STATE_SIZE},"state size");'
        source+=f'\n_Static_assert(sizeof(OverworldWildSpawn)=={WILD_SPAWN_SIZE},"spawn size");'
        for member,offset in (('movementCooldowns',WILD_MOVEMENT_COOLDOWN),
                              ('movementEmoteTimers',WILD_MOVEMENT_EMOTE_TIMER),
                              ('movementSpotStates',WILD_MOVEMENT_SPOT_STATE),
                              ('movementActorControlModes',WILD_MOVEMENT_ACTOR_CONTROL_MODE),
                              ('movementCrashShakeTimers',WILD_MOVEMENT_CRASH_SHAKE_TIMER),
                              ('movementCrashShakeBaseX',WILD_MOVEMENT_CRASH_SHAKE_BASE_X),
                              ('movementCrashShakeBaseZ',WILD_MOVEMENT_CRASH_SHAKE_BASE_Z)):
            source+=f'\n_Static_assert(__builtin_offsetof(OverworldWildSpawnState,{member})=={offset},"{member}");'
        for member,size in (('movementSpotStates',10),('movementActorControlModes',10),
                            ('movementCrashShakeTimers',10),('movementCrashShakeBaseX',40),
                            ('movementCrashShakeBaseZ',40)):
            source+=f'\n_Static_assert(sizeof(((OverworldWildSpawnState *)0)->{member})=={size},"{member} extent");'
        source+=f'\n_Static_assert(__builtin_offsetof(OverworldWildSpawnState,movementCrashShakeBaseZ)+40-{WILD_MOVEMENT_CRASH_SHAKE_TIMER}=={WILD_CRASH_SHAKE_SIZE},"crash shake contiguous extent");'
        source+='\n_Static_assert(OW_WILD_ACTOR_CONTROL_AUTONOMOUS==0 && OW_WILD_ACTOR_CONTROL_HELD==1,"control modes");'
        result=subprocess.run(['clang','-target','armv5te-none-eabi','-fsyntax-only',
            '-Wno-unknown-attributes','-Wno-gnu-folding-constant','-I',str(ROOT),'-x','c','-'],
            input=source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_native_crash_flags_preserve_queue_boolean_and_motion_identity(self):
        target=COMBAT+12+ACTOR_SLOT*28
        for flags,identity,phase,pending in ((0,0,'NONE',0),(1,0,'NONE',1),
                (2,7,'NEEDS_SETTLE',0),(3,7,'NEEDS_SETTLE',1),
                (4,7,'PLAYING',0),(5,7,'PLAYING',1)):
            with self.subTest(flags=flags):
                self.fixture.write(target+24,bytes((flags,)))
                self.fixture.write(target+26,struct.pack('<H',identity))
                hp=self.read()['targets'][0]
                self.assertEqual((hp['knockbackRawFlags'],hp['knockbackPending'],
                                  hp['crashPhase'],hp['crashMotionIdentity']),
                                 (flags,pending,phase,identity))

    def test_native_crash_flags_reject_unknown_both_phases_wrong_role_and_orphan_id(self):
        target=COMBAT+12+ACTOR_SLOT*28
        for flags,identity in ((16,0),(6,7),(13,7),(8,0),(1,7)):
            with self.subTest(flags=flags,identity=identity):
                self.fixture.write(target+24,bytes((flags,)))
                self.fixture.write(target+26,struct.pack('<H',identity))
                with self.assertRaisesRegex(DevtoolsFailure,'Crash flags are stale'):
                    self.read()

    def test_motion_read_rejects_stale_public_owner_wrong_elapsed_and_unloaded_facade(self):
        for offset,byte in ((4,1),(88+40,1)):
            with self.subTest(offset=offset):
                original=self.fixture.read(self.actor_pointer+offset,1)
                self.fixture.write(self.actor_pointer+offset,bytes((original[0]^byte,)))
                with self.assertRaisesRegex(DevtoolsFailure,'public actor') as caught:
                    self.read()
                if offset==88+40:
                    error=caught.exception
                    diagnostic=error.details
                    self.assertEqual(error.code,'combat-motion-owner')
                    self.assertEqual(diagnostic['failedPredicates'],['elapsed'])
                    self.assertEqual(diagnostic['predicateValues']['elapsed'],
                                     dict(native=1,published=0))
                    self.assertEqual((diagnostic['species'],diagnostic['role'],diagnostic['frame'],
                                      diagnostic['actorFrame'],diagnostic['nativeCycle']),
                                     (143,self.snapshot['actors'][0]['role'],12,12,1000))
                    self.assertEqual(diagnostic['handle'],self.snapshot['actors'][0]['handle'])
                    self.assertEqual(diagnostic['raw140Hex'],self.fixture.read(self.actor_pointer,140).hex())
                    self.assertEqual(diagnostic['public']['motionElapsed'],0)
                    self.assertEqual(diagnostic['native']['elapsed'],1)
                    self.assertEqual(diagnostic['native']['plan']['duration'],13)
                    self.assertEqual(json.loads(str(error).split('public actor: ',1)[1]),diagnostic)
                self.fixture.write(self.actor_pointer+offset,original)
        facade=self.fixture.session.rt.ACTOR_DESCRIPTOR['facade']['address']
        self.fixture.write(facade,bytes(24))
        with self.assertRaisesRegex(DevtoolsFailure,'current Actor queue'):
            self.read()

    def test_motion_descriptor_wrong_stride_is_rejected(self):
        state=self.fixture.session.rt.ACTOR_DESCRIPTOR['state']
        state['actorStride']=176 if state['actorStride']==172 else 172
        with self.assertRaisesRegex(DevtoolsFailure,'descriptor differs'):
            self.read()

    def test_committed_pause_keeps_the_plan_after_public_reservation_release(self):
        for suspended in (False,True):
            with self.subTest(suspended=suspended):
                self.committed_pause(suspended)
                motion=self.read()['targets'][0]['motion']
                self.assertEqual(motion['phase'],'SUSPENDED' if suspended else 'SETTLING')
                self.assertEqual((motion['commitPublished'],motion['commitSequence'],
                                  motion['elapsed'],motion['settleRemaining']),
                                 (1,1,13,5))
                self.assertEqual(motion['plan']['reservationId'],42)
                self.assertEqual(self.snapshot['actors'][0]['reservationId'],0)

    def test_pause_rejects_uncommitted_incomplete_unreleased_or_invalid_remaining_state(self):
        valid=self.committed_pause()
        changes=(('commitPublished',88+50,'<B',0),('commitSequence',88+46,'<H',0),
                 ('commitSequence',88+46,'<H',2),('completedElapsed',88+40,'<H',12),
                 ('reservationId',68,'<H',42),('settleRemaining',88+42,'<H',0),
                 ('settleRemaining',88+42,'<H',6),('settleRemaining',88+34,'<B',0))
        for predicate,offset,fmt,value in changes:
            with self.subTest(predicate=predicate,value=value):
                raw=bytearray(valid)
                struct.pack_into(fmt,raw,offset,value)
                if predicate=='completedElapsed':
                    struct.pack_into('<H',raw,64,value)
                self.write_actor_motion(raw)
                with self.assertRaisesRegex(DevtoolsFailure,'native motion differs') as caught:
                    self.read()
                self.assertIn(predicate,caught.exception.details['failedPredicates'])
                self.assertEqual(caught.exception.details['raw140Hex'],raw.hex())

    def test_moving_or_suspended_from_moving_cannot_release_its_reservation(self):
        raw=bytearray(self.fixture.read(self.actor_pointer,140))
        struct.pack_into('<H',raw,68,0)
        for suspended in (False,True):
            with self.subTest(suspended=suspended):
                raw[77]=5 if suspended else 2
                raw[88+48]=5 if suspended else 2
                raw[88+49]=2 if suspended else 0
                self.write_actor_motion(raw)
                with self.assertRaisesRegex(DevtoolsFailure,'native motion differs') as caught:
                    self.read()
                self.assertEqual(caught.exception.details['failedPredicates'],['reservationId'])
                self.assertFalse(caught.exception.details['reservationContract']['committedPause'])

    def test_committed_pause_still_rejects_a_stale_public_owner(self):
        raw=self.committed_pause()
        raw[4]^=1
        self.fixture.write(self.actor_pointer,raw)
        with self.assertRaisesRegex(DevtoolsFailure,'different public actor'):
            self.read()

    def test_only_complete_old_and_new_actor_layouts_read_the_nonzero_slot(self):
        for size,stride,policy_size in ((2448,172,32),(2440,176,36)):
            with self.subTest(size=size,stride=stride,policy_size=policy_size):
                self.use_actor_layout(size,stride,policy_size)
                target=self.read()['targets'][0]
                self.assertEqual(target['handle']['slot'],ACTOR_SLOT)
                self.assertEqual(target['motion']['plan']['target'],[585,406])
                self.assertEqual(target['motion']['plan']['duration'],13)
                self.assertEqual(target['motion']['plan']['flags'],1)
                self.assertEqual(target['hp'],210)

    def test_mixed_policy_state_and_compiled_size_are_rejected(self):
        self.use_actor_layout(2440,176,36)
        descriptor=self.fixture.session.rt.ACTOR_DESCRIPTOR
        for size,stride,policy_size,capacity in ((2448,172,36,2448),(2448,176,32,2448),
                (2440,172,36,2448),(2440,176,32,2448),(2440,176,36,2440),
                (2440,176,36,2488),(2488,176,36,2448)):
            with self.subTest(size=size,stride=stride,policy_size=policy_size,capacity=capacity):
                descriptor['state'].update(size=size,capacity=capacity,actorStride=stride)
                descriptor['structures']['actorPolicyState']=policy_size
                with self.assertRaisesRegex(DevtoolsFailure,'descriptor differs'):
                    self.read()
        # A complete descriptor is still rejected if its linked ELF is from
        # the other layout. Native symbol size is not inferred from JSON.
        descriptor['state'].update(size=2448,capacity=2448,actorStride=172)
        descriptor['structures']['actorPolicyState']=32
        with self.assertRaisesRegex(ValueError,'wrong-symbol-size'):
            self.read()

    def test_native_header_size_must_match_the_object_not_block_capacity(self):
        self.use_actor_layout(2440,176,36)
        address=self.fixture.session.rt.ACTOR_DESCRIPTOR['state']['address']
        self.fixture.write(address+6,struct.pack('<H',2448))
        with self.assertRaisesRegex(DevtoolsFailure,'current Actor queue'):
            self.read()

    def test_actual_hp_disagreement_is_rejected(self):
        self.fixture.write(RESIDENT+2+ACTOR_SLOT*2,struct.pack('<H',230))
        with self.assertRaisesRegex(DevtoolsFailure,'resident value'):
            self.read()

    def test_generation_alias_is_rejected(self):
        self.snapshot['actors'][0]['handle']['encounterGeneration']=2
        with self.assertRaisesRegex(DevtoolsFailure,'stale'):
            self.read()

    def test_unloaded_entry_or_stale_owner_never_exposes_targets(self):
        self.fixture.write(BASE+0x3000,bytes(52))
        self.assertFalse(self.read()['available'])
        self.fixture.write(BASE+0x3000,self.fixture.image[0x3000:0x3034])
        self.fixture.write(COMBAT,struct.pack('<I',0x02020000))
        self.assertFalse(self.read()['available'])

    def test_compiled_size_and_source_order_authenticate_offsets(self):
        symbols=dict(sCombat=(COMBAT,292),gOverworldCombatEntry=(BASE+0x3000,52),
                     gOverworldWildResidentData=(RESIDENT,22))
        source=Path(self.temp.name)/'combat.c'
        source.write_text((ROOT/'src/player_health_pokemon.c').read_text().replace(
            'u16 maxHp;\n    u16 currentHp;','u16 currentHp;\n    u16 maxHp;'))
        with self.assertRaisesRegex(ValueError,'field order'):
            checked_combat(symbols,self.fixture.image,source)
        symbols['sCombat']=(COMBAT,288)
        with self.assertRaisesRegex(ValueError,'native layout'):
            checked_combat(symbols,self.fixture.image,ROOT/'src/player_health_pokemon.c')

    def setup_interactions(self):
        f=self.fixture
        self.runtime_pointer=0x02240000
        self.conditions_pointer=0x02250000
        self.snapshot.update(observationBoundary='main-task-queue-completion',fieldAvailable=True)
        wild_elf=ROOT/'build/overworld_wild_spawns_overlay_linked.o'
        (f.root/'build'/wild_elf.name).write_bytes(wild_elf.read_bytes())
        actor_file=f.root/'build/overworld_actor_system_overlay_linked.o'
        actor_image=bytearray(actor_file.read_bytes())
        getter=symbol(wild_elf.read_bytes(),'OverworldWildSpawns_GetConditionRuntime',2)
        blob_getter=symbol(wild_elf.read_bytes(),'OverworldWildSpawns_GetBehaviorDataBlob',2,expected_size=128)
        self.catalog_owner_pointer=symbol(wild_elf.read_bytes(),'sOverworldWildBehaviorDataBlob',1,'.bss',4)[0]
        self.interaction_code={getter[0]:getter[2],blob_getter[0]:blob_getter[2]}
        f.write(self.catalog_owner_pointer,bytes(4))
        section_offset=struct.unpack_from('<I',actor_image,32)[0]
        section_stride,section_count=struct.unpack_from('<2H',actor_image,46)
        for name,size in (('gOverworldActorSystemMovementPolicyServiceEntry',16),
                          ('gOverworldBehaviorConditionAdapterEntry',28),
                          ('gOverworldActorSystemResolverServiceEntry',16)):
            address,_,_=symbol(actor_image,name,1,expected_size=size)
            for n in range(section_count):
                _,kind,flags,base,start,length=struct.unpack_from('<6I',actor_image,
                    section_offset+section_stride*n)
                if kind==1 and flags&2 and base<=address<=base+length-size:
                    table_start=start+address-base
                    if name=='gOverworldBehaviorConditionAdapterEntry':
                        # A stopped build still has v11. This copied memory
                        # fixture uses the current source v12; live collection
                        # never repairs old bytes and rejects v11 below.
                        self.assertIn(struct.unpack_from('<H',actor_image,table_start+4)[0],(11,12))
                        struct.pack_into('<H',actor_image,table_start+4,12)
                    self.interaction_code[address]=bytes(actor_image[table_start:table_start+size])
                    break
        actor_file.write_bytes(actor_image)
        original=f.session.packaged_code
        f.session.packaged_code=lambda address,size: (
            f.read(address,size) if address in self.interaction_code else original(address,size))
        for address,code in self.interaction_code.items():f.write(address,code)
        f.write(WILD_STATE+WILD_FIELD_OFFSET,struct.pack('<2I',FIELD,self.runtime_pointer))
        f.write(self.runtime_pointer+RUNTIME_CONDITIONS_OFFSET,struct.pack('<I',self.conditions_pointer))
        f.write(self.runtime_pointer+RUNTIME_THROW_OFFSET,bytes(16))
        for actor in self.snapshot['actors']:self.prepare_interaction(actor)
        return getter[0]

    @staticmethod
    def handle_bytes(handle):
        return struct.pack('<6H',*(handle[key] for key in
            ('slot','generation','fieldEpoch','mapGeneration','encounterGeneration')),0)

    def prepare_interaction(self,actor):
        slot=actor['handle']['slot']
        prepared=bytearray(PREPARED_ACTOR_SIZE)
        prepared[:12]=self.handle_bytes(actor['handle'])
        prepared[81]=1
        struct.pack_into('<H',prepared,84,actor['species'])
        self.fixture.write(self.conditions_pointer+slot*PREPARED_ACTOR_SIZE,prepared)
        bindings=bytearray(BINDINGS_SIZE);bindings[:12]=prepared[:12]
        for start in (12,36):
            struct.pack_into('<H',bindings,start+14,0xFFFF)
            bindings[start+20]=0xFF;bindings[start+23]=1
        self.fixture.write(self.conditions_pointer+CONDITIONS_BINDINGS_OFFSET+slot*BINDINGS_SIZE,bindings)

    def add_interaction_actor(self,slot):
        f=self.fixture;descriptor=f.session.rt.ACTOR_DESCRIPTOR
        raw=bytearray(f.read(self.actor_pointer,140))
        struct.pack_into('<H',raw,4,slot);struct.pack_into('<I',raw,16,991+slot)
        address=descriptor['state']['address']+68+slot*descriptor['state']['actorStride']
        f.write(address,raw)
        actor=decode_actor_state(bytes(raw[:88]),descriptor)
        source=dict(self.source,object=self.source['object']+slot*0x200,
                    personality=actor['subjectIdentity'],object_id=0xE0+slot)
        f.write(WILD_STATE+slot*WILD_SPAWN_SIZE,struct.pack('<IIHHBB2xBBH',*source.values()))
        actor.update(identityVerified=True,sourceIdentity=source)
        self.snapshot['actors'].append(actor)
        self.prepare_interaction(actor)
        return actor

    def bind_interaction(self,name,target,*,lifetime=0,expires=0):
        if not hasattr(self,'catalog_pointer'):
            blob=self.compiled_capture_blob()
            (self.fixture.root/'build/OverworldWildBehaviorData.bin').write_bytes(blob)
            self.catalog_pointer=0x02260000
            self.catalog_size=len(blob)
            self.fixture.write(self.catalog_pointer,blob)
            self.fixture.write(self.catalog_owner_pointer,struct.pack('<I',self.catalog_pointer))
            self.fixture.session.native_heap_generation=1
            self.fixture.session.native_observation=SimpleNamespace(resolver_discovery=dict(status=0,
                fieldPointer=FIELD,heapGeneration=1,returnNativeCycle=999,
                blobAddress=self.catalog_pointer,blobSize=len(blob)))
        raw=bytearray(24);raw[:12]=self.handle_bytes(target['handle']);raw[12]=2
        application_local=local_application(decode_application_bank(
            self.compiled_capture_blob(),ROOT),self.source['species'],24)
        struct.pack_into('<HIBBBB',raw,14,23 if name=='trigger' else 24,expires,
                         application_local,lifetime,1,0)
        address=self.conditions_pointer+CONDITIONS_BINDINGS_OFFSET+ACTOR_SLOT*BINDINGS_SIZE
        address+=12 if name=='trigger' else 36
        self.fixture.write(address,raw)
        return address

    def interactions(self):
        return observe_pokemon_combat(self.fixture.session,self.snapshot,include_interactions=True)['interactions']

    def capture_subject_species(self, species):
        """Keep the copied Wild, combat row and public Actor one subject."""
        f=self.fixture
        self.source['species']=species
        f.write(WILD_STATE+ACTOR_SLOT*WILD_SPAWN_SIZE+10,struct.pack('<H',species))
        f.write(COMBAT+12+ACTOR_SLOT*28+10,struct.pack('<H',species))
        f.write(self.actor_pointer+70,struct.pack('<H',species))
        public=f.read(self.actor_pointer,88)
        actor=decode_actor_state(public,f.session.rt.ACTOR_DESCRIPTOR)
        actor.update(identityVerified=True,sourceIdentity=dict(self.source))
        self.snapshot['actors']=[actor]

    @staticmethod
    def compiled_capture_blob():
        built=(ROOT/'build/OverworldWildBehaviorData.bin').read_bytes()
        if struct.unpack_from('<H',built,4)[0] == CATALOG_BLOB_VERSION:
            return built
        # During a source-only change, use the reviewed generated Blob95.
        # Its bank decoder still compares every tail row to current source.
        staged=(ROOT/'build/tickets/tkt62/current-blob95.bin').read_bytes()
        decode_application_bank(staged,ROOT)
        return staged

    def setup_condition_capture(self, condition_id=49626, flags=11):
        self.capture_subject_species(74 if condition_id == THROW_CARGO_CONDITION else 95)
        self.setup_interactions()
        target=self.add_interaction_actor(0)
        f=self.fixture;blob=self.compiled_capture_blob()
        self.capture_blob=blob
        (f.root/'build/OverworldWildBehaviorData.bin').write_bytes(blob)
        self.catalog_pointer=0x02260000;self.condition_states_pointer=0x02270000
        self.catalog_size=len(blob)
        f.write(self.catalog_pointer,blob)
        f.write(self.catalog_owner_pointer,struct.pack('<I',self.catalog_pointer))
        f.session.native_heap_generation=1
        f.session.native_observation=SimpleNamespace(resolver_discovery=dict(status=0,
            fieldPointer=FIELD,heapGeneration=1,returnNativeCycle=999,
            blobAddress=self.catalog_pointer,blobSize=len(blob)))
        offset,count,stride=struct.unpack_from('<IHH',blob,52)
        source=next(i for i in range(count) if struct.unpack_from('<H',blob,offset+i*stride+32)[0]==condition_id)
        application = THROW_APPLICATION if condition_id == THROW_CARGO_CONDITION else RAM_APPLICATION
        self.assertEqual(blob[offset+source*stride+34],application)
        bank=decode_application_bank(blob,ROOT)
        application_local=local_application(bank,self.source['species'],application)
        self.prepared_pointer=self.conditions_pointer+ACTOR_SLOT*PREPARED_ACTOR_SIZE
        prepared=bytearray(f.read(self.prepared_pointer,PREPARED_ACTOR_SIZE))
        struct.pack_into('<I',prepared,12,self.condition_states_pointer)
        struct.pack_into('<H',prepared,16,source)
        struct.pack_into('<BBH',prepared,80,1,1,1);f.write(self.prepared_pointer,prepared)
        f.write(self.condition_states_pointer,struct.pack('<II3H2B',0,0,
            target['handle']['slot'],target['handle']['generation'],target['handle']['encounterGeneration'],2,flags))
        publication=bytearray(CONDITIONS_PUBLICATION_SIZE)
        struct.pack_into('<I',publication,ACTOR_SLOT*4,1<<application_local)
        struct.pack_into('<h',publication,80+ACTOR_SLOT*2,target['logical']['x'])
        struct.pack_into('<h',publication,100+ACTOR_SLOT*2,target['logical']['y'])
        struct.pack_into('<H',publication,120,1<<ACTOR_SLOT)
        f.write(self.conditions_pointer+CONDITIONS_PUBLICATION_OFFSET,publication)
        return target

    def test_condition_capture_uses_native_state_with_no_named_binding(self):
        target=self.setup_condition_capture();reads=[]
        self.fixture.session.read=lambda address,size: (
            reads.append((address,size)) or self.fixture.read(address,size))
        result=self.interactions();row=result['carriers'][0];capture=row['conditionCaptures'][0]
        self.assertFalse(row['bindings']['trigger']['bound'])
        self.assertEqual((capture['conditionId'],capture['application'],capture['activationMode'],
            capture['durationFrames'],capture['cooldownFrames'],capture['flags']),(49626,RAM_APPLICATION,2,0,100,11))
        self.assertEqual(capture['target'],dict(kind='ACTOR',actor=target['handle']))
        self.assertTrue(capture['targetCurrent']);self.assertTrue(capture['targetValid'])
        self.assertEqual(capture['targetPosition'],[target['logical'][k] for k in ('x','y')])
        self.assertEqual(capture['activeApplicationMask'],1<<capture['applicationLocal'])
        self.assertEqual(capture['activeGlobalApplications'],(RAM_APPLICATION,))
        self.assertEqual(result['conditionCatalog']['blobSha256'],hashlib.sha256(
            self.capture_blob).hexdigest())
        self.assertEqual(result['readBytes'],28+2*(PREPARED_ACTOR_SIZE+60)+12
                         +PREPARED_ACTOR_SIZE+16*2+124*2+2*328+140+3*(128+4))
        self.assertEqual(result['catalogReadBytes'],self.catalog_size)
        first_blob_reads=[r for r in reads if self.catalog_pointer<=r[0]<self.catalog_pointer+self.catalog_size]
        self.assertTrue(first_blob_reads)
        reads.clear();self.assertEqual(self.interactions()['catalogReadBytes'],0)
        self.assertFalse(any(self.catalog_pointer<=address<self.catalog_pointer+self.catalog_size for address,_ in reads))

    def test_condition_capture_accepts_timed_presentation_bit_only(self):
        self.setup_condition_capture(flags=11 | (1 << 6))
        capture=self.interactions()['carriers'][0]['conditionCaptures'][0]
        self.assertEqual(capture['flags'],11 | (1 << 6))
        self.fixture.write(self.condition_states_pointer+15,bytes((1 << 7,)))
        with self.assertRaises(DevtoolsFailure):
            self.interactions()

    def test_while_true_actor_capture_uses_same_current_raw_owner_and_budget(self):
        target=self.setup_condition_capture(condition_id=THROW_CARGO_CONDITION,flags=1)
        result=self.interactions();capture=result['carriers'][0]['conditionCaptures'][0]
        self.assertEqual((capture['conditionId'],capture['application'],capture['activationMode'],
            capture['durationFrames'],capture['cooldownFrames'],capture['flags']),
            (THROW_CARGO_CONDITION,THROW_APPLICATION,0,0,0,1))
        self.assertEqual(capture['target'],dict(kind='ACTOR',actor=target['handle']))
        self.assertTrue(capture['targetCurrent']);self.assertTrue(capture['targetValid'])
        self.assertEqual(capture['activeApplicationMask'],1<<capture['applicationLocal'])
        self.assertEqual(capture['activeGlobalApplications'],(THROW_APPLICATION,))
        self.assertEqual(capture['rawHex'],self.fixture.read(self.condition_states_pointer,16).hex())
        self.assertLessEqual(result['readBytes'],INTERACTION_READ_BUDGET)
        self.fixture.write(self.condition_states_pointer+14,bytes((0,0)))
        self.fixture.write(self.conditions_pointer+CONDITIONS_PUBLICATION_OFFSET+120,bytes(2))
        cleared=self.interactions()['carriers'][0]['conditionCaptures'][0]
        self.assertEqual(cleared['target'],dict(kind='NONE',actor=None))
        self.assertFalse(cleared['targetCurrent']);self.assertFalse(cleared['targetValid'])

    def test_condition_capture_stale_target_and_unpublished_tile_grant_no_current_target(self):
        self.setup_condition_capture();f=self.fixture
        f.write(self.condition_states_pointer+10,struct.pack('<H',2))
        capture=self.interactions()['carriers'][0]['conditionCaptures'][0]
        self.assertFalse(capture['targetCurrent']);self.assertEqual(capture['target']['actor']['generation'],2)
        f.write(self.condition_states_pointer+14,bytes((0,0)))
        f.write(self.conditions_pointer+CONDITIONS_PUBLICATION_OFFSET+120,bytes(2))
        capture=self.interactions()['carriers'][0]['conditionCaptures'][0]
        self.assertEqual(capture['target'],dict(kind='NONE',actor=None))
        self.assertFalse(capture['targetCurrent']);self.assertFalse(capture['targetValid'])

    def test_condition_capture_catalog_identity_and_current_discovery_are_required(self):
        self.setup_condition_capture();f=self.fixture
        original=f.session.native_observation.resolver_discovery.copy()
        for key,value in (('fieldPointer',FIELD+4),('heapGeneration',2),('returnNativeCycle',1001),
                          ('blobAddress',0x02400000),('blobSize',1)):
            with self.subTest(key=key):
                f.session.native_observation.resolver_discovery=dict(original,**{key:value})
                with self.assertRaises(DevtoolsFailure):self.interactions()
        f.session.native_observation.resolver_discovery=original
        catalog_file=f.root/'build/OverworldWildBehaviorData.bin'
        current_blob=catalog_file.read_bytes()
        self.assertEqual(struct.unpack_from('<H',current_blob,4)[0],CATALOG_BLOB_VERSION)
        for version in (89,91,0xFFFF):
            with self.subTest(version=version):
                changed=bytearray(current_blob);struct.pack_into('<H',changed,4,version)
                catalog_file.write_bytes(changed);reads=[]
                f.session.read=lambda address,size:(reads.append((address,size)) or f.read(address,size))
                with self.assertRaisesRegex(DevtoolsFailure,'catalog layout differs'):self.interactions()
                self.assertFalse(any(self.catalog_pointer<=address<self.catalog_pointer+self.catalog_size
                                     for address,_ in reads))
        catalog_file.write_bytes(current_blob);f.session.read=f.read
        f.write(self.catalog_pointer+32,b'bad!')
        with self.assertRaisesRegex(DevtoolsFailure,'live condition catalog differs'):self.interactions()
        f.write(self.catalog_pointer+32,self.capture_blob[32:36])
        f.session.native_observation.resolver_discovery=None
        row=self.interactions()['carriers'][0]
        self.assertEqual(row['conditionCaptures'],[])
        self.assertIn('natural resolver',row['conditionCaptureReason'])

    def test_condition_catalog_rebinds_current_owner_without_reading_old_discovery(self):
        self.setup_condition_capture();f=self.fixture;old_pointer=self.catalog_pointer
        new_pointer=0x02290000
        f.write(new_pointer,self.capture_blob)
        f.write(self.catalog_owner_pointer,struct.pack('<I',new_pointer))
        f.write(old_pointer,b'old!');reads=[]
        f.session.read=lambda address,size:(reads.append((address,size)) or f.read(address,size))
        result=self.interactions();identity=result['conditionCatalog']
        self.assertEqual(identity['blobAddress'],new_pointer)
        self.assertEqual(identity['naturalDiscoveryBlobAddress'],old_pointer)
        self.assertEqual(identity['blobOwnerAddress'],self.catalog_owner_pointer)
        self.assertEqual(result['catalogReadBytes'],self.catalog_size)
        self.assertTrue(result['carriers'][0]['conditionCaptures'][0]['targetCurrent'])
        self.assertFalse(any(old_pointer<=address<old_pointer+self.catalog_size for address,_ in reads))
        reads.clear();self.assertEqual(self.interactions()['catalogReadBytes'],0)
        self.assertFalse(any(new_pointer<=address<new_pointer+self.catalog_size for address,_ in reads))

    def test_condition_catalog_same_pointer_new_map_context_reauthenticates(self):
        from tools.overworld.devtools_pokemon_combat_observer import _interaction_catalog,_interaction_layout
        self.setup_condition_capture();f=self.fixture
        baseline=self.interactions()['conditionCatalog']
        layout=_interaction_layout(f.session)
        for key in ('fieldEpoch','mapGeneration','mapId'):
            with self.subTest(key=key):
                # The same native owner/address cannot reuse a prior map's seal.
                self.interactions();context=dict(self.snapshot['context'])
                context[key]+=1;reads=[]
                f.session.read=lambda address,size:(reads.append((address,size)) or f.read(address,size))
                result=_interaction_catalog(f.session,layout,FIELD,self.snapshot['nativeCycle'],context=context)
                self.assertEqual(result['authenticatedBytes'],self.catalog_size)
                self.assertEqual(result['identity'][key],context[key])
                self.assertEqual(result['identity']['blobAddress'],baseline['blobAddress'])
                self.assertTrue(any(self.catalog_pointer<=address<self.catalog_pointer+self.catalog_size
                                    for address,_ in reads))

    def test_condition_catalog_changed_current_owner_is_rejected(self):
        self.setup_condition_capture();f=self.fixture
        for stage in ('bulk-authentication','condition-state'):
            with self.subTest(stage=stage):
                f.session.pokemon_combat_condition_catalog=None
                f.write(self.catalog_owner_pointer,struct.pack('<I',self.catalog_pointer))
                def changed(address,size):
                    raw=f.read(address,size)
                    if (stage=='bulk-authentication' and address==self.catalog_pointer) \
                            or (stage=='condition-state' and address==self.condition_states_pointer):
                        f.write(self.catalog_owner_pointer,bytes(4))
                    return raw
                f.session.read=changed
                with self.assertRaisesRegex(DevtoolsFailure,'catalog owner changed during read'):
                    self.interactions()
        f.session.read=f.read

    def test_condition_catalog_getter_full_linked_body_seal_rejects_changed_calls_and_literals(self):
        from tools.overworld.devtools_pokemon_combat_observer import _interaction_layout
        self.setup_interactions();f=self.fixture
        layout=_interaction_layout(f.session)
        address,size,body=layout["blobGetter"]
        self.assertEqual((address,size),(0x023C2C58,128))
        self.assertEqual(hashlib.sha256(body).hexdigest(),
                         "c66911f6b32ba2e470d00dd4f3511df103500d97d3e06c01d04cdef5ca05ce9c")
        linked=f.root/"build/overworld_wild_spawns_overlay_linked.o"
        original=linked.read_bytes()
        table=struct.unpack_from("<I",original,32)[0]
        stride,count=struct.unpack_from("<2H",original,46)
        starts=[]
        for n in range(count):
            _,kind,flags,base,start,length=struct.unpack_from("<6I",original,table+stride*n)
            if kind==1 and flags&6==6 and base<=address<=base+length-size:
                starts.append(start+address-base)
        self.assertEqual(len(starts),1)
        for offset in (0,18,40,56,80,108,124,127):
            with self.subTest(offset=offset):
                changed=bytearray(original);changed[starts[0]+offset]^=1
                linked.write_bytes(changed)
                f.session.pokemon_combat_interaction_layout=None
                with self.assertRaisesRegex(DevtoolsFailure,"catalog owner getter differs"):
                    _interaction_layout(f.session)
        linked.write_bytes(original)
        f.session.pokemon_combat_interaction_layout=None
        self.assertEqual(_interaction_layout(f.session)["blobGetter"],layout["blobGetter"])

    def test_condition_catalog_current_owner_code_and_pointer_are_required(self):
        self.setup_condition_capture();f=self.fixture
        getter=symbol((ROOT/'build/overworld_wild_spawns_overlay_linked.o').read_bytes(),
                      'OverworldWildSpawns_GetBehaviorDataBlob',2,expected_size=128)
        original_package=f.session.packaged_code
        for fault in ('live-code','packaged-code','unaligned-pointer','short-owner'):
            with self.subTest(fault=fault):
                f.write(getter[0],getter[2])
                f.write(self.catalog_owner_pointer,struct.pack('<I',self.catalog_pointer))
                f.session.read=f.read;f.session.packaged_code=original_package
                if fault=='live-code':
                    f.session.packaged_code=lambda address,size:(getter[2] if
                        (address,size)==(getter[0],getter[1]) else original_package(address,size))
                    f.write(getter[0],bytes((getter[2][0]^1,)))
                elif fault=='packaged-code':
                    f.session.packaged_code=lambda address,size:(bytes(size) if
                        (address,size)==(getter[0],getter[1]) else original_package(address,size))
                elif fault=='unaligned-pointer':
                    f.write(self.catalog_owner_pointer,struct.pack('<I',self.catalog_pointer+1))
                else:
                    f.session.read=lambda address,size:(bytes(3) if address==self.catalog_owner_pointer else f.read(address,size))
                with self.assertRaises(DevtoolsFailure):self.interactions()
        f.session.read=f.read;f.session.packaged_code=original_package

    def test_condition_capture_invalid_entry_state_and_extent_fail_before_acceptance(self):
        self.setup_condition_capture();f=self.fixture
        prepared=f.read(self.prepared_pointer,PREPARED_ACTOR_SIZE);state=f.read(self.condition_states_pointer,16)
        for offset,data in ((12,struct.pack('<I',0)),(12,struct.pack('<I',0x023FFFFC)),
                            (16,b'\xFF\xFF'),(82,struct.pack('<H',33)),
                            (86,struct.pack('<H',2)),(86,struct.pack('<H',65535))):
            with self.subTest(offset=offset,data=data):
                f.write(self.prepared_pointer+offset,data)
                with self.assertRaises(DevtoolsFailure):self.interactions()
                f.write(self.prepared_pointer,prepared)
        for offset,data in ((8,struct.pack('<H',10)),(10,bytes(2)),(14,b'\x03'),(15,b'\x80')):
            with self.subTest(offset=offset,data=data):
                f.write(self.condition_states_pointer+offset,data)
                with self.assertRaises(DevtoolsFailure):self.interactions()
                f.write(self.condition_states_pointer,state)
        f.session.read=lambda address,size: (bytes(size-1) if address==self.condition_states_pointer else f.read(address,size))
        with self.assertRaisesRegex(DevtoolsFailure,'read is incomplete'):self.interactions()

    def test_interactions_accept_prepared_subject_damage_pending_boolean(self):
        self.setup_condition_capture()
        for pending in (0,1):
            with self.subTest(pending=pending):
                self.fixture.write(self.prepared_pointer+86,struct.pack('<H',pending))
                self.assertEqual(len(self.interactions()['carriers'][0]['conditionCaptures']),1)

    def test_condition_capture_changed_state_prepared_owner_and_publication_are_rejected(self):
        self.setup_condition_capture();f=self.fixture
        for address,size,offset in ((self.condition_states_pointer,16,15),
                (self.prepared_pointer,PREPARED_ACTOR_SIZE,4),
                (self.conditions_pointer+CONDITIONS_PUBLICATION_OFFSET,124,120)):
            original=f.read(address,size);calls=0
            def changed(read_address,read_size):
                nonlocal calls
                data=f.read(read_address,read_size)
                if (read_address,read_size)==(address,size):
                    calls+=1
                    if calls==1:f.write(address+offset,bytes((original[offset]^1,)))
                return data
            f.session.read=changed
            with self.subTest(address=address):
                with self.assertRaisesRegex(DevtoolsFailure,'changed during read'):self.interactions()
            f.write(address,original)
        f.session.read=f.read

    def test_interactions_opt_in_has_no_default_reads_and_requires_boolean(self):
        reads=[];self.fixture.session.read=lambda address,size: (
            reads.append((address,size)) or self.fixture.read(address,size))
        self.assertNotIn('interactions',self.read())
        self.assertNotIn((WILD_STATE+WILD_FIELD_OFFSET,8),reads)
        with self.assertRaisesRegex(DevtoolsFailure,'must be boolean'):
            observe_pokemon_combat(self.fixture.session,self.snapshot,include_interactions=1)

    def test_interactions_bind_distinct_current_targets_then_preserve_clear_reason(self):
        self.setup_interactions()
        trigger=self.add_interaction_actor(0);cargo=self.add_interaction_actor(2)
        self.bind_interaction('trigger',trigger)
        cargo_address=self.bind_interaction('cargo',cargo,lifetime=1,expires=99)
        throw=bytearray(16);throw[ACTOR_SLOT]=0x80|3
        struct.pack_into('<3H',throw,10,1<<2,1<<ACTOR_SLOT,0)
        self.fixture.write(self.runtime_pointer+RUNTIME_THROW_OFFSET,throw)
        receipt=self.interactions();row=receipt['carriers'][0]
        self.assertTrue(receipt['available'])
        self.assertEqual((receipt['fieldSystem'],receipt['runtimePointer'],receipt['conditionsPointer']),
                         (FIELD,self.runtime_pointer,self.conditions_pointer))
        self.assertEqual(row['handle'],self.snapshot['actors'][0]['handle'])
        self.assertEqual(row['bindings']['trigger']['target']['actor'],trigger['handle'])
        self.assertEqual(row['bindings']['cargo']['target']['actor'],cargo['handle'])
        self.assertTrue(row['bindings']['cargo']['targetCurrent'])
        self.assertEqual((row['bindings']['cargo']['expiresAt'],row['bindings']['cargo']['lifetime']),
                         (99,1))
        self.assertEqual(row['throw'],dict(targetRaw=131,targetSlot=2,carried=True,windup=False,
            targeted=False,carrier=True,recovering=False))
        self.assertEqual(receipt['readBytes'],28+3*(PREPARED_ACTOR_SIZE+60)+12+3*328+140)
        # Actual Clear retains source identity/lifetime but clears target/flags/expiry.
        raw=bytearray(self.fixture.read(cargo_address,24));raw[:14]=bytes(14)
        struct.pack_into('<I',raw,16,0);raw[22]=0;raw[23]=17
        self.fixture.write(cargo_address,raw)
        cleared=self.interactions()['carriers'][0]['bindings']['cargo']
        self.assertEqual((cleared['bound'],cleared['reason'],cleared['sourceConditionId'],
                          cleared['sourceApplication'],cleared['target']),
                         (False,17,24,None,dict(kind='NONE',actor=None)))

    def test_interactions_stale_target_is_retained_without_claiming_it_current(self):
        self.setup_interactions();target=self.add_interaction_actor(2)
        address=self.bind_interaction('cargo',target)
        self.fixture.write(address+2,struct.pack('<H',2))
        binding=self.interactions()['carriers'][0]['bindings']['cargo']
        self.assertTrue(binding['bound']);self.assertFalse(binding['targetCurrent'])
        self.assertEqual(binding['target']['actor']['generation'],2)
        self.assertEqual(self.fixture.read(address+2,2),struct.pack('<H',2))

    def test_interactions_code_auth_fails_before_private_pointer_reads_and_refreshes_cache(self):
        getter=self.setup_interactions();self.interactions()
        layout=self.fixture.session.pokemon_combat_interaction_layout
        # The early pass authenticates these four bodies. The catalog getter
        # has its separate full-body and current-owner controls above.
        early_addresses=(layout["getter"][0],*(layout[key][0] for key in
                         ("service","adapter","resolver")))
        for address in early_addresses:
            with self.subTest(address=address):
                old=self.fixture.read(address,1);self.fixture.write(address,bytes((old[0]^1,)))
                reads=[];self.fixture.session.read=lambda a,n:(reads.append((a,n)) or self.fixture.read(a,n))
                with self.assertRaisesRegex(DevtoolsFailure,'code differs from package'):
                    self.interactions()
                self.assertNotIn((WILD_STATE+WILD_FIELD_OFFSET,8),reads)
                self.fixture.write(address,old)
        first=self.fixture.session.pokemon_combat_interaction_layout
        self.fixture.session.rom_hash='b'*64
        self.interactions()
        self.assertIsNot(first,self.fixture.session.pokemon_combat_interaction_layout)
        second=self.fixture.session.pokemon_combat_interaction_layout
        self.fixture.session.emu=object();self.interactions()
        self.assertIsNot(second,self.fixture.session.pokemon_combat_interaction_layout)
        # A missing symbol cannot be replaced by a hardcoded address.
        del self.fixture.session.pokemon_combat_interaction_layout
        (self.fixture.root/'build/overworld_wild_spawns_overlay_linked.o').unlink()
        with self.assertRaises(FileNotFoundError):self.interactions()

    def test_interactions_null_and_invalid_pointers_are_never_followed(self):
        self.setup_interactions()
        for owner_offset,valid_pointer,reason in (
                (WILD_STATE+WILD_RUNTIME_OFFSET,self.runtime_pointer,'wild runtime is not loaded'),
                (self.runtime_pointer+RUNTIME_CONDITIONS_OFFSET,self.conditions_pointer,'conditions are not prepared')):
            self.fixture.write(owner_offset,bytes(4));reads=[]
            self.fixture.session.read=lambda a,n:(reads.append((a,n)) or self.fixture.read(a,n))
            result=self.interactions()
            self.assertFalse(result['available']);self.assertEqual(result['reason'],reason)
            self.assertFalse(any(0x02250000<=a<0x02250000+CONDITIONS_SIZE for a,n in reads))
            for bad in (1,0x01FFFFFC,0x023FFFFC):
                self.fixture.write(owner_offset,struct.pack('<I',bad));reads.clear()
                with self.assertRaisesRegex(DevtoolsFailure,'pointer is invalid'):self.interactions()
                self.assertFalse(any(a==bad or a==bad+RUNTIME_CONDITIONS_OFFSET for a,n in reads))
            self.fixture.write(owner_offset,struct.pack('<I',valid_pointer))

    def test_interactions_wrong_owner_retains_raw_diagnostics_without_private_reads(self):
        self.setup_interactions()
        for current_field,runtime in ((0,0),(0,self.runtime_pointer),
                                      (FIELD+4,0),(FIELD+4,self.runtime_pointer)):
            owner=struct.pack('<2I',current_field,runtime)
            self.fixture.write(WILD_STATE+WILD_FIELD_OFFSET,owner);reads=[]
            self.fixture.session.read=lambda a,n:(reads.append((a,n)) or self.fixture.read(a,n))
            with self.assertRaisesRegex(DevtoolsFailure,'field owner changed') as error:
                self.interactions()
            self.assertEqual(error.exception.code,'combat-interaction-owner')
            self.assertIn(f'current=0x{current_field:08X}, runtime=0x{runtime:08X}',str(error.exception))
            self.assertIn(f'ownerHex={owner.hex()}',str(error.exception))
            self.assertEqual(error.exception.details,dict(fieldSystem=FIELD,
                currentFieldSystem=current_field,runtimePointer=runtime,ownerHex=owner.hex(),
                wildStateAddress=WILD_STATE,frame=self.snapshot['frame'],
                nativeCycle=self.snapshot['nativeCycle']))
            self.assertFalse(any(a in (self.runtime_pointer+RUNTIME_CONDITIONS_OFFSET,
                                      self.runtime_pointer+RUNTIME_THROW_OFFSET) for a,n in reads))

    def test_interactions_measured_unbound_owner_is_absent_without_runtime_reads(self):
        self.setup_interactions()
        self.snapshot.update(actors=[],frame=799,nativeCycle=2052)
        for runtime in (0,0x022B7C30):
            self.fixture.write(WILD_STATE+WILD_FIELD_OFFSET,struct.pack('<2I',0,runtime));reads=[]
            self.fixture.session.read=lambda a,n:(reads.append((a,n)) or self.fixture.read(a,n))
            result=self.interactions()
            self.assertFalse(result['available'])
            self.assertEqual(result['reason'],'wild field owner is unbound')
            self.assertEqual((result['runtimePointer'],result['conditionsPointer'],result['carriers']),
                             (runtime,0,[]))
            self.assertEqual(result['readBytes'],16)
            self.assertEqual(reads.count((WILD_STATE+WILD_FIELD_OFFSET,8)),2)
            self.assertFalse(any(a in (runtime+RUNTIME_CONDITIONS_OFFSET,
                                      runtime+RUNTIME_THROW_OFFSET) for a,n in reads))

    def test_interactions_unbound_absence_keeps_code_pointer_and_coherence_guards(self):
        getter=self.setup_interactions();actors=self.snapshot['actors'];self.snapshot['actors']=[]
        owner_address=WILD_STATE+WILD_FIELD_OFFSET
        self.fixture.write(owner_address,struct.pack('<2I',FIELD+4,self.runtime_pointer))
        with self.assertRaisesRegex(DevtoolsFailure,'field owner changed'):self.interactions()
        self.fixture.write(owner_address,struct.pack('<2I',0,self.runtime_pointer))
        self.snapshot['actors']=[{**actors[0],'identityVerified':False}]
        with self.assertRaisesRegex(DevtoolsFailure,'field owner changed'):self.interactions()
        self.snapshot['actors']=[]
        original=self.fixture.read(getter,1)
        self.fixture.write(getter,bytes((original[0]^1,)))
        with self.assertRaisesRegex(DevtoolsFailure,'code differs from package'):self.interactions()
        self.fixture.write(getter,original)
        for bad in (1,0x01FFFFFC,0x023FFFFC,0x02400000-1308):
            self.fixture.write(owner_address,struct.pack('<2I',0,bad))
            with self.assertRaisesRegex(DevtoolsFailure,'pointer is invalid'):self.interactions()
        self.fixture.write(owner_address,struct.pack('<2I',0,self.runtime_pointer))
        def changed_owner(address,size):
            raw=self.fixture.read(address,size)
            if (address,size)==(owner_address,8):
                self.fixture.write(owner_address,struct.pack('<2I',FIELD,self.runtime_pointer))
            return raw
        self.fixture.session.read=changed_owner
        with self.assertRaisesRegex(DevtoolsFailure,'owner changed during read'):self.interactions()

    def test_interactions_full_carrier_identity_and_short_reads_fail_closed(self):
        self.setup_interactions()
        prepared=self.conditions_pointer+ACTOR_SLOT*PREPARED_ACTOR_SIZE
        bindings=self.conditions_pointer+CONDITIONS_BINDINGS_OFFSET+ACTOR_SLOT*BINDINGS_SIZE
        for address,label in ((prepared,'prepared subject is stale'),(bindings,'binding subject is stale')):
            for offset in (0,2,4,6,8):
                old=self.fixture.read(address+offset,2)
                self.fixture.write(address+offset,struct.pack('<H',struct.unpack('<H',old)[0]+1))
                with self.assertRaisesRegex(DevtoolsFailure,label):self.interactions()
                self.fixture.write(address+offset,old)
        for address,size in ((WILD_STATE+WILD_FIELD_OFFSET,8),
                (self.runtime_pointer+RUNTIME_CONDITIONS_OFFSET,4),
                (self.runtime_pointer+RUNTIME_THROW_OFFSET,16),(prepared,PREPARED_ACTOR_SIZE),(bindings,60)):
            self.fixture.session.read=lambda a,n:(self.fixture.read(a,n-1)
                if (a,n)==(address,size) else self.fixture.read(a,n))
            with self.assertRaisesRegex(DevtoolsFailure,'read is incomplete'):self.interactions()
        self.fixture.session.read=self.fixture.read
        self.fixture.write(WILD_STATE+WILD_FIELD_OFFSET,struct.pack('<I',FIELD+4))
        with self.assertRaisesRegex(DevtoolsFailure,'field owner changed'):self.interactions()

    def test_interactions_unprepared_slot_is_not_read_as_a_binding(self):
        self.setup_interactions()
        prepared=self.conditions_pointer+ACTOR_SLOT*PREPARED_ACTOR_SIZE
        self.fixture.write(prepared+81,b'\0');reads=[]
        self.fixture.session.read=lambda a,n:(reads.append((a,n)) or self.fixture.read(a,n))
        result=self.interactions()
        self.assertFalse(result['carriers'][0]['available'])
        bindings=self.conditions_pointer+CONDITIONS_BINDINGS_OFFSET+ACTOR_SLOT*BINDINGS_SIZE
        self.assertNotIn((bindings,60),reads)

    def test_interactions_old_linked_adapter_version_is_rejected(self):
        self.setup_interactions()
        actor_file=self.fixture.root/'build/overworld_actor_system_overlay_linked.o'
        image=bytearray(actor_file.read_bytes())
        address,_,_=symbol(image,'gOverworldBehaviorConditionAdapterEntry',1,expected_size=28)
        offset=struct.unpack_from('<I',image,32)[0]
        stride,count=struct.unpack_from('<2H',image,46)
        for n in range(count):
            _,kind,flags,base,start,length=struct.unpack_from('<6I',image,offset+stride*n)
            if kind==1 and flags&2 and base<=address<=base+length-28:
                struct.pack_into('<H',image,start+address-base+4,11);break
        actor_file.write_bytes(image)
        self.fixture.write(address+4,struct.pack('<H',11))
        with self.assertRaisesRegex(DevtoolsFailure,'adapter layout differs'):self.interactions()

    def test_interactions_binding_field_masks_and_changed_owner_are_rejected(self):
        self.setup_interactions()
        bindings=self.conditions_pointer+CONDITIONS_BINDINGS_OFFSET+ACTOR_SLOT*BINDINGS_SIZE
        for offset,value in ((12+13,1),(12+21,2),(12+22,2),(12+23,9)):
            old=self.fixture.read(bindings+offset,1)
            self.fixture.write(bindings+offset,bytes((value,)))
            with self.assertRaisesRegex(DevtoolsFailure,'binding fields are invalid'):self.interactions()
            self.fixture.write(bindings+offset,old)
        self.fixture.write(self.runtime_pointer+RUNTIME_THROW_OFFSET+10,struct.pack('<H',0x400))
        with self.assertRaisesRegex(DevtoolsFailure,'Throw masks are invalid'):self.interactions()
        self.fixture.write(self.runtime_pointer+RUNTIME_THROW_OFFSET+10,bytes(2))
        def changed_owner(address,size):
            data=self.fixture.read(address,size)
            if (address,size)==(bindings,60):
                self.fixture.write(self.runtime_pointer+RUNTIME_CONDITIONS_OFFSET,struct.pack('<I',0x02260000))
            return data
        self.fixture.session.read=changed_owner
        with self.assertRaisesRegex(DevtoolsFailure,'owner changed during read'):self.interactions()

    def test_return_diagnostic_preserves_raw_record_and_native_owner_inputs(self):
        self.setup_interactions();f=self.fixture
        actor=self.snapshot['actors'][0];slot=actor['handle']['slot']
        address=self.runtime_pointer+RUNTIME_RETURN_MOVES_OFFSET+slot*RETURN_MOVE_SIZE
        raw=bytearray(RETURN_MOVE_SIZE);raw[:12]=self.handle_bytes(actor['handle'])
        raw[12:52]=bytes(range(40));raw[52:132]=bytes(range(80))
        struct.pack_into('<IH4BH',raw,132,FIELD,23,2,1,37,2,51)
        f.write(address,raw)
        f.write(WILD_STATE+WILD_MOVEMENT_SPOT_STATE+slot,b'\x02')
        f.write(WILD_STATE+WILD_CONTROL_READ_OFFSET+1+slot,b'\x01')
        f.write(WILD_STATE+WILD_SPAWN_RUN_READ_OFFSET+2+slot,b'\x01')
        f.write(WILD_STATE+WILD_CAPTURE_MASK_READ_OFFSET+2,struct.pack('<H',1<<slot))
        f.write(self.runtime_pointer+RUNTIME_DESPAWN_PENDING_MASK_OFFSET,struct.pack('<H',1<<slot))
        f.write(self.runtime_pointer+RUNTIME_MOTION_IDENTITIES_OFFSET+slot*2,struct.pack('<H',53))
        reads=[];f.session.read=lambda a,n:(reads.append((a,n)) or f.read(a,n))
        result=self.interactions();row=result['carriers'][0]['returnMove'];inputs=row['ownerInputs']
        self.assertEqual(row['rawHex'],raw.hex());self.assertEqual(row['phase'],'OUTWARD')
        self.assertEqual((row['laneState'],row['deferredPause'],row['retryFrames'],row['identityOrRetryFrame']),
                         (2,37,2,51))
        self.assertEqual((row['fieldSystem'],row['originSurfaceId']),(FIELD,23))
        self.assertEqual((row['planRawHex'],row['laneRawHex']),(raw[12:52].hex(),raw[52:132].hex()))
        self.assertTrue(row['subjectMatchesActor']);self.assertTrue(row['diagnosticOnly'])
        self.assertFalse(row['acceptedProof'])
        self.assertEqual((inputs['movementSpotState'],inputs['movementActorControlMode'],
            inputs['spawnRunActive'],inputs['movementMotionIdentity'],inputs['captureTargetMask'],
            inputs['distanceDespawnPendingMask']),(2,1,1,53,1<<slot,1<<slot))
        self.assertEqual(inputs['spawnEntryRawHex'],f.read(WILD_STATE+slot*20,20).hex())
        self.assertEqual(inputs['throwRawHex'],bytes(16).hex())
        self.assertEqual(reads.count((address,RETURN_MOVE_SIZE)),2)
        self.assertEqual(result['returnMoveDiagnostics']['readBytes'],468)
        self.assertLessEqual(result['readBytes'],INTERACTION_READ_BUDGET)
        # A stale private subject/Field is diagnostic data, never a granted owner.
        raw[0]=9;struct.pack_into('<I',raw,132,FIELD+4);raw[139]=2;f.write(address,raw)
        stale=self.interactions()['carriers'][0]['returnMove']
        self.assertFalse(stale['subjectMatchesActor']);self.assertFalse(stale['acceptedProof'])
        self.assertEqual((stale['phase'],stale['fieldSystem']),('PENDING',FIELD+4))

    def test_return_diagnostic_rejects_changed_record_and_every_owner_input(self):
        for address_kind in ('return','spawn','spot','run','capture','control','token','despawn','throw'):
            with self.subTest(address_kind=address_kind):
                self.setup_interactions();f=self.fixture
                locations={'return':(self.runtime_pointer+RUNTIME_RETURN_MOVES_OFFSET+ACTOR_SLOT*144,144),
                    'spawn':(WILD_STATE+ACTOR_SLOT*20,20),'spot':(WILD_STATE+WILD_MOVEMENT_SPOT_STATE,10),
                    'run':(WILD_STATE+WILD_SPAWN_RUN_READ_OFFSET,12),
                    'capture':(WILD_STATE+WILD_CAPTURE_MASK_READ_OFFSET,4),
                    'control':(WILD_STATE+WILD_CONTROL_READ_OFFSET,12),
                    'token':(self.runtime_pointer+RUNTIME_MOTION_IDENTITIES_OFFSET,20),
                    'despawn':(self.runtime_pointer+RUNTIME_DESPAWN_PENDING_MASK_OFFSET,4),
                    'throw':(self.runtime_pointer+RUNTIME_THROW_OFFSET,16)}
                target=locations[address_kind];changed=False
                def changing(address,size):
                    nonlocal changed
                    raw=f.read(address,size)
                    if (address,size)==target and not changed:
                        changed=True;f.write(address,bytes((raw[0]^1,))+raw[1:])
                    return raw
                f.session.read=changing
                with self.assertRaisesRegex(DevtoolsFailure,'return .*changed during read'):self.interactions()
                f.write(target[0],bytes((f.read(target[0],1)[0]^1,)))
                f.session.read=f.read

    def test_return_diagnostic_skips_only_optional_reads_when_existing_cap_is_full(self):
        reads=[]
        def read(address,size):reads.append((address,size));return bytes(size)
        row=dict(available=True,slot=ACTOR_SLOT)
        receipt=_return_diagnostics(read,INTERACTION_READ_BUDGET-12,WILD_STATE,
            0x022A0000,bytes(16),FIELD,{},[row])
        self.assertFalse(receipt['available']);self.assertTrue(receipt['diagnosticOnly'])
        self.assertFalse(receipt['acceptedProof']);self.assertEqual(receipt['readBytes'],0)
        self.assertEqual(reads,[]);self.assertNotIn('returnMove',row)
        self.assertEqual(INTERACTION_READ_BUDGET,12528)

    def test_interactions_maximum_ten_actor_budget_and_arm_layout(self):
        self.setup_interactions()
        for slot in range(10):
            if slot!=ACTOR_SLOT:self.add_interaction_actor(slot)
        result=self.interactions()
        self.assertEqual(len(result['carriers']),10);self.assertEqual(result['readBytes'],4940)
        source='#include "include/overworld_wild_runtime_state_internal.h"\n'
        source+='_Static_assert(OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION==12,"adapter version");\n'
        source+=f'_Static_assert(OVERWORLD_WILD_BEHAVIOR_DATA_VERSION=={CATALOG_BLOB_VERSION},"catalog version");\n'
        sizes={'OverworldWildOverlayRuntimeState':WILD_RUNTIME_SIZE,
               'OverworldWildReturnMove':RETURN_MOVE_SIZE,
               'OverworldWildBehaviorConditionRuntime':CONDITIONS_SIZE,
               'OverworldBehaviorConditionPreparedActor':PREPARED_ACTOR_SIZE,
               'OverworldBehaviorConditionEntryState':CONDITION_STATE_SIZE,
               'OverworldTargetBindingsState':BINDINGS_SIZE,'OverworldWildThrowState':16}
        for kind,size in sizes.items():source+=f'_Static_assert(sizeof({kind})=={size},"{kind}");\n'
        offsets=(('OverworldWildSpawnState','movementFieldSystem',WILD_FIELD_OFFSET),
                 ('OverworldWildSpawnState','movementRuntimeState',WILD_RUNTIME_OFFSET),
                 ('OverworldWildOverlayRuntimeState','throwState',RUNTIME_THROW_OFFSET),
                 ('OverworldWildOverlayRuntimeState','conditions',RUNTIME_CONDITIONS_OFFSET),
                 ('OverworldWildOverlayRuntimeState','pickupQuery',0x518),
                 ('OverworldWildOverlayRuntimeState','returnMoves',RUNTIME_RETURN_MOVES_OFFSET),
                 ('OverworldWildOverlayRuntimeState','movementMotionIdentities',RUNTIME_MOTION_IDENTITIES_OFFSET),
                 ('OverworldWildSpawnState','movementSpawnRunActive',WILD_SPAWN_RUN_READ_OFFSET+2),
                 ('OverworldWildSpawnState','captureTargetMask',WILD_CAPTURE_MASK_READ_OFFSET+2),
                 ('OverworldWildSpawnState','movementActorControlModes',WILD_CONTROL_READ_OFFSET+1),
                 ('OverworldWildReturnMove','subject',0),
                 ('OverworldWildReturnMove','plan',12),
                 ('OverworldWildReturnMove','lane',52),
                 ('OverworldWildReturnMove','fieldSystem',132),
                 ('OverworldWildReturnMove','originSurfaceId',136),
                 ('OverworldWildReturnMove','laneState',138),
                 ('OverworldWildReturnMove','phase',139),
                 ('OverworldWildReturnMove','deferredPause',140),
                 ('OverworldWildReturnMove','retryFrames',141),
                 ('OverworldWildReturnMove','returnMotionIdentity',142),
                 ('OverworldWildReturnMove','retryFrame',142),
                 ('OverworldWildBehaviorConditionRuntime','bindings',CONDITIONS_BINDINGS_OFFSET),
                 ('OverworldWildBehaviorConditionRuntime','activeApplicationMasks',CONDITIONS_PUBLICATION_OFFSET),
                 ('OverworldWildBehaviorConditionRuntime','targetX',2412),
                 ('OverworldWildBehaviorConditionRuntime','targetY',2432),
                 ('OverworldWildBehaviorConditionRuntime','targetValidMask',2452),
                 ('OverworldBehaviorConditionPreparedActor','states',12),
                 ('OverworldBehaviorConditionPreparedActor','catalogEntryIndexes',16),
                 ('OverworldBehaviorConditionPreparedActor','count',80),
                 ('OverworldBehaviorConditionPreparedActor','valid',81),
                 ('OverworldBehaviorConditionPreparedActor','stateCapacity',82),
                 ('OverworldBehaviorConditionPreparedActor','subjectSpecies',84),
                 ('OverworldBehaviorConditionEntryState','targetSlot',8),
                 ('OverworldBehaviorConditionEntryState','targetGeneration',10),
                 ('OverworldBehaviorConditionEntryState','targetEncounterGeneration',12),
                 ('OverworldBehaviorConditionEntryState','targetKind',14),
                 ('OverworldBehaviorConditionEntryState','flags',15),
                 ('OverworldBehaviorConditionTargetReference','kind',12),
                 ('OverworldTargetBinding','sourceConditionId',14),
                 ('OverworldTargetBinding','expiresAt',16),
                 ('OverworldTargetBinding','sourceApplication',20),
                 ('OverworldTargetBinding','lifetime',21),
                 ('OverworldTargetBinding','flags',22),
                 ('OverworldTargetBinding','reason',23),
                 ('OverworldWildThrowState','targetMask',10),
                 ('OverworldWildThrowState','carrierMask',12),
                 ('OverworldWildThrowState','recoveringMask',14))
        for kind,field,offset in offsets:
            source+=f'_Static_assert(__builtin_offsetof({kind},{field})=={offset},"{field}");\n'
        source+=f'_Static_assert(__builtin_offsetof(OverworldWildOverlayRuntimeState,spawnPresentations)+__builtin_offsetof(OverworldWildPresentationState,distanceDespawnPendingMask)=={RUNTIME_DESPAWN_PENDING_MASK_OFFSET},"despawn mask");\n'
        source+='_Static_assert(sizeof(((OverworldWildOverlayRuntimeState *)0)->movementMotionIdentities)==20,"motion identities extent");\n'
        source+='_Static_assert(sizeof(((OverworldWildOverlayRuntimeState *)0)->returnMoves)==10*144,"return rows extent");\n'
        process=subprocess.run(['clang','-target','armv5te-none-eabi','-fsyntax-only',
            '-Wno-unknown-attributes','-Wno-gnu-folding-constant','-I',str(ROOT),'-x','c','-'],
            input=source,text=True,capture_output=True)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(INTERACTION_READ_BUDGET,12528)


if __name__=='__main__':unittest.main()
