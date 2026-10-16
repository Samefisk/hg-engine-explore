"""Actual shared _tap dispatch with host memory; no gameplay proof."""
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools.overworld import test_devtools_role_profile as role_fixture
from tools.overworld.devtools_observer import NativeObservation, NativeObservationError
from tools.overworld.devtools_mount_pacing_observer import NativeMountedPacingObserver, MAX_CALLBACKS
from tools.overworld.devtools_records import select_current_actor


class MountPacingTests(unittest.TestCase):
    def test_avatar_offsets_from_actual_arm_header(self):
        header = (Path(__file__).resolve().parents[2] / "include/map_events_internal.h").read_text()
        definition = re.search(r"typedef struct FIELD_PLAYER_AVATAR \{.*?\} FIELD_PLAYER_AVATAR;", header, re.S)
        self.assertIsNotNone(definition)
        source = "typedef unsigned int u32; typedef unsigned char u8;\n" \
            "typedef struct LocalMapObject LocalMapObject;\n" \
            "typedef struct FIELD_PLAYER_AVATAR_SUB FIELD_PLAYER_AVATAR_SUB;\n" + definition[0]
        for member, offset in (("unk0", 0), ("unk10", 0x10), ("unk14", 0x14), ("mapObject", 0x30)):
            source += f'\n_Static_assert(__builtin_offsetof(FIELD_PLAYER_AVATAR,{member}) == {offset}, "{member}");'
        source += '\n_Static_assert(sizeof(FIELD_PLAYER_AVATAR)==0x40,"avatar size");'
        result = subprocess.run(["clang", "-target", "armv5te-none-eabi", "-fsyntax-only", "-x", "c", "-"],
                                input=source, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def fixture(self):
        _, s, actor, source, engine, regs, put, calls = role_fixture.RoleProfileTests().fixture()
        actor.update(role="MOUNTED", inputOwnership=1, motionKind="NONE", motionPhase="IDLE", commitSequence=0)
        engine.update(manager_index=1, spawn_object_id=231)
        s.completed_frames = 12
        s.rt.EXECUTED_FRAME_COUNT = 30
        s.rt.ACTOR_DESCRIPTOR["capacities"] = {"actors": 8}
        field, player, manager = s.field_pointer(), 0x02230000, engine["current_manager"]
        avatar = 0x02240000
        values = {manager+0x124:player, manager+4:64, player:1, player+0xB4:manager,
            s.rt.ACTOR_DESCRIPTOR["state"]["address"]+8:9,
            s.rt.ACTOR_DESCRIPTOR["state"]["address"]+12:2,
            s.rt.ACTOR_DESCRIPTOR["state"]["address"]+46:3, 0x02280000:field,
            field+0x40:avatar, avatar+0x30:player, avatar:17, avatar+0x10:2, avatar+0x14:3}
        s.rt.G_FIELD_SYS_PTR = 0x02280000
        s.rt.unsigned = lambda emu, address, size=4: values.get(address,0)
        s.rt.signed = lambda emu, address, size=4: -7 if address % 0x100 == 0x90 else 3
        s.rt.player_ptr = lambda emu: player
        poses = {player:dict(pos_x=100,pos_y=200,pos_z=300,x=1,y=2), source["object"]:dict(pos_x=100,pos_y=200,pos_z=300,x=1,y=2)}
        values.update({0x01FFA500 + 60: 1, 0x01FFA500 + 64: player,
                       0x01FFA500 + 68: 1, 0x023BC744 + 0x68: 1,
                       0x023BC744 + 0x18: 0x5A})
        previous_signed = s.rt.signed
        def signed(emu, address, size=4):
            if 0x01FFA500 <= address < 0x01FFA500 + 56:
                offset = (address - 0x01FFA500) % 28
                return 100 if offset == 0 else 300 if offset == 4 else 0
            if address in (player + 0x70, player + 0x78):
                return poses[player]['pos_x' if address == player + 0x70 else 'pos_z']
            return previous_signed(emu, address, size)
        s.rt.signed = signed
        s.rt.object_state = lambda emu,pointer: deepcopy(poses[pointer])
        names = {"OverworldMount_SyncPresentation":0x02300000,"OverworldMount_PlayerStepBridge":0x02300100}
        s.rt.MOUNT_SYMBOLS = names
        code = bytes(range(32))
        s.code_regions = [(a,code) for a in names.values()]
        for address in names.values(): put(address,code)
        from scripts.verify_pokemon_move_history_capture import elf_bytes_at
        gait_object = s.rt.REPO / 'build/overworld_mount_chain_overlay_linked.o'
        s.rom_hash, s.save_hash = "host-fixture-rom", "host-fixture-save"
        s.packaged_code = lambda address, size: elf_bytes_at(gait_object, address, size)
        gait_state = bytearray(72)
        for offset in (0, 28):
            struct.pack_into("<4i4hHBx", gait_state, offset, 100, 300, 0, 0, 0, 0, 0, 0, 0, 0)
        struct.pack_into("<3IB", gait_state, 56, 0, 1, player, 1)
        s.rt.actor_memory_read = lambda emu, address, size: (
            bytes(gait_state[:size]) if address == 0x01FFA500 else
            elf_bytes_at(gait_object, address, size))
        regs.lr=0x02010001
        observer = NativeObservation(s, _.observer.hooks, lambda path,address,size:code)
        s.native_observation=observer
        checked = {**actor,"identityVerified":True,"engineIdentity":{**engine,"anchorPointer":player,"anchorInCurrentManager":True}}
        bound = select_current_actor(dict(frame=12,context=dict(fieldEpoch=2,mapGeneration=3),actors=[checked]),checked)
        reader=NativeMountedPacingObserver(s,bound,10)
        return reader,s,actor,engine,regs,put,calls,poses

    def test_shared_gait_auth_rejects_code_or_layout_mismatch_without_hooks(self):
        from scripts.verify_pokemon_move_history_capture import elf_section_layout
        from tools.overworld.devtools_mount_gait import authenticate_gait
        for fault in ("gait-live", "presentation-live", "gait-package", "presentation-package",
                      "missing-gait", "missing-presentation", "missing-state", "short-state"):
            r, s, a, e, regs, put, calls, poses = self.fixture()
            sections = elf_section_layout(s.rt.REPO / 'build/overworld_mount_chain_overlay_linked.o')
            address = 0x01FFA100 if "presentation" in fault else 0x01FFA500 if "state" in fault else 0x01FF9D00
            if fault.startswith("missing"):
                sections = [row for row in sections if row[2] != address]
            elif fault == "short-state":
                sections = [(*row[:3], 71) if row[2] == address else row for row in sections]
            elif fault.endswith("live"):
                original = s.rt.actor_memory_read
                s.rt.actor_memory_read = lambda emu, target, size, original=original, address=address: (
                    bytes(size) if target == address else original(emu, target, size))
            else:
                original = s.packaged_code
                s.packaged_code = lambda target, size, original=original, address=address: (
                    bytes(size) if target == address else original(target, size))
            with self.subTest(fault=fault), patch(
                    'scripts.verify_pokemon_move_history_capture.elf_section_layout', return_value=sections):
                with self.assertRaises(NativeObservationError):
                    authenticate_gait(s)
            self.assertFalse(hasattr(s, "_mounted_gait_identity"))
            self.assertEqual(calls, [])
            self.assertEqual(r.observer.hooks.callbacks, {})

    def test_shared_gait_input_reads_current_mount_layout(self):
        from tools.overworld.devtools_mount_gait import read_gait_pair
        r, s, a, e, regs, put, calls, poses = self.fixture()
        reads, original = [], s.rt.unsigned
        def unsigned(emu, address, size=4):
            reads.append((address, size))
            return {0x023BC744 + 0x60: 65539, 0x023BC744 + 0x67: 0,
                    0x023BC744 + 0x68: 1, 0x023BC744 + 0x6F: 4}.get(
                        address, original(emu, address, size))
        s.rt.unsigned = unsigned
        pair = read_gait_pair(s, dict(playerPointer=e['anchorPointer'] if 'anchorPointer' in e
                                     else s.rt.player_ptr(s.emu), mountPointer=e['pointer']))
        self.assertEqual(pair['gait']['input']['session'], 1)
        self.assertEqual(pair['gait']['input']['mode'], 1)
        self.assertIn((0x023BC744 + 0x68, 4), reads)
        self.assertIn((0x023BC744 + 0x6F, 1), reads)
        self.assertNotIn((0x023BC744 + 0x60, 4), reads)
        self.assertNotIn((0x023BC744 + 0x67, 1), reads)

    def test_shared_gait_auth_rejects_changed_input_loads(self):
        from scripts.verify_pokemon_move_history_capture import elf_bytes_at
        from tools.overworld.devtools_mount_gait import authenticate_gait
        for offset in (0x12, 0x1A, 0x1C, 0x32):
            r, s, a, e, regs, put, calls, poses = self.fixture()
            def bytes_at(linked, address, size):
                value = bytearray(elf_bytes_at(linked, address, size))
                if address == 0x01FF9D00:
                    value[offset] ^= 1
                return bytes(value)
            with self.subTest(offset=offset), patch(
                    'scripts.verify_pokemon_move_history_capture.elf_bytes_at', side_effect=bytes_at):
                with self.assertRaisesRegex(NativeObservationError, 'input layout differs'):
                    authenticate_gait(s)
            self.assertFalse(hasattr(s, '_mounted_gait_identity'))
            self.assertEqual(calls, [])

    def test_shared_gait_auth_cache_is_only_for_current_session_emu_and_rom(self):
        from tools.overworld.devtools_mount_gait import authenticate_gait
        r, s, a, e, regs, put, calls, poses = self.fixture()
        reads, original = [], s.rt.actor_memory_read
        def read(emu, address, size):
            reads.append((emu, address, size))
            return original(emu, address, size)
        s.rt.actor_memory_read = read
        identity = authenticate_gait(s)
        self.assertEqual(authenticate_gait(s), identity)
        self.assertEqual(len(reads), 2)
        s.rom_hash = "other-rom"
        self.assertEqual(authenticate_gait(s), identity)
        self.assertEqual(len(reads), 4)
        s.emu = SimpleNamespace(**vars(s.emu))
        self.assertEqual(authenticate_gait(s), identity)
        self.assertEqual(len(reads), 6)
        other = SimpleNamespace(**vars(s))
        self.assertEqual(authenticate_gait(other), identity)
        self.assertEqual(len(reads), 8)
        self.assertEqual(calls, [])

    def test_shared_gait_pair_collects_exact_bounded_state_without_pose_checks(self):
        from tools.overworld.devtools_mount_gait import POSE_KEYS, read_gait_pair
        r, s, a, e, regs, put, calls, poses = self.fixture()
        current = r._current()
        reads, original = [], s.rt.actor_memory_read
        def read(emu, address, size):
            reads.append((address, size))
            return original(emu, address, size)
        s.rt.actor_memory_read = read
        before, clock = vars(regs).copy(), r.observer._clock()
        poses[e['pointer']]['pos_x'] += 9
        with patch('tools.overworld.devtools_mount_gait.check_gait', side_effect=AssertionError("collector judged pose")):
            pair = read_gait_pair(s, current)
        self.assertEqual((pair['playerPointer'], pair['mountPointer']),
                         (current['playerPointer'], e['pointer']))
        self.assertEqual((pair['player']['pos_x'], pair['mount']['pos_x']), (100, 109))
        self.assertEqual(pair['gait']['schemaVersion'], 1)
        self.assertEqual(pair['gait']['address'], 0x01FFA500)
        self.assertEqual(set(pair['gait']['pose']), set(POSE_KEYS))
        self.assertEqual(pair['gait']['pose'], pair['gait']['previous'])
        self.assertEqual((pair['gait']['owner'], pair['gait']['initialized']),
                         (current['playerPointer'], 1))
        self.assertEqual([item for item in reads if item[0] == 0x01FFA500], [(0x01FFA500, 72)])
        self.assertEqual(vars(regs), before)
        self.assertEqual(r.observer._clock(), clock)
        self.assertEqual(calls, [])
        s.rt.object_state = lambda *args: (_ for _ in ()).throw(AssertionError("reread supplied pose"))
        self.assertEqual(read_gait_pair(s, current, player=poses[current['playerPointer']],
                                       mount=poses[e['pointer']]), pair)
        self.assertNotIn('unk88_z', poses[e['pointer']])
        for fault in ("short-state", "playerPointer", "mountPointer"):
            bad = dict(current)
            if fault == "short-state":
                s.rt.actor_memory_read = lambda emu, address, size: bytes(71)
            else:
                bad[fault] = 0x02400000
            with self.subTest(fault=fault), self.assertRaises(NativeObservationError):
                read_gait_pair(s, bad)

    def test_session_snapshot_attaches_only_verified_same_boundary_gait_pair(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        r, s, a, e, regs, put, calls, poses = self.fixture()
        a.update(lastDecision=0, lastCancelReason=0)
        original_actor, original_identity = s.rt.actor_state, s.rt.live_wild_object_identity
        s.rt.actor_state = lambda emu, slot: original_actor(emu, slot) if slot == 7 else {'active': False}
        s.rt.live_wild_object_identity = lambda emu, slot, **kwargs: original_identity(emu, slot)
        s.rt.movement_policy_state = lambda *args: {}
        s.rt.actor_probe = SimpleNamespace(_enum_name=lambda *args: 'NONE')
        s._crash_presentation_reader = SimpleNamespace(boundary=lambda read: None,
                                                      observe=lambda *args: {'known': False})
        s.native_observation = None
        before, clock = vars(regs).copy(), r.observer._clock()
        poses[e['pointer']]['pos_x'] += 9
        value = DevtoolsSession._snapshot(s, 0, details=False)
        pair = value['mountedPair']
        self.assertTrue(value['actors'][0]['identityVerified'])
        self.assertEqual(pair['player']['pos_x'], value['player']['pos_x'])
        self.assertEqual(pair['mount']['pos_x'], value['actors'][0]['engineObject']['pos_x'])
        self.assertEqual((pair['player']['pos_x'], pair['mount']['pos_x']), (100, 109))
        self.assertEqual((value['frame'], value['nativeCycle']), (12, 30))
        self.assertEqual(vars(regs), before)
        self.assertEqual(r.observer._clock(), clock)
        self.assertEqual(calls, [])
        a['subjectIdentity'] += 1
        unverified = DevtoolsSession._snapshot(s, 0, details=False)
        self.assertFalse(unverified['actors'][0]['identityVerified'])
        self.assertNotIn('mountedPair', unverified)

    def invoke(self, reader, address):
        for callback in tuple(reader.observer.hooks.callbacks[address]): callback()

    def test_disabled_then_exact_pair_return_and_registers_unchanged(self):
        r,s,a,e,regs,put,calls,poses=self.fixture()
        self.assertEqual(calls,[])
        r.arm()
        before=vars(regs).copy()
        self.invoke(r,0x02300000)
        poses[e["pointer"]]["pos_x"]+=9
        self.invoke(r,regs.lr & ~1)
        event=r.observer.pending[-1]
        self.assertEqual(event["mount"]["pos_x"],109) # Capture a bad pose; never repair it.
        self.assertEqual(event["player"]["pos_x"],100)
        self.assertEqual(event["player"]["unk88_z"],-7)
        self.assertEqual(event["player"]["unk94_z"],3)
        self.assertEqual(event["avatarControl"],dict(flags=17,moveState=2,playerMoveState=3))
        self.assertEqual(event["entryNativeCycle"],30)
        self.assertEqual(vars(regs),before)
        self.assertNotIn("frame",event)
        self.assertIsNone(r.close()["failure"])
        self.assertEqual(r.observer.hooks.callbacks,{})
        count=len(calls);r.close();self.assertEqual(len(calls),count)

    def test_player_step_actual_field_and_return(self):
        r,s,a,e,regs,*_=self.fixture();r.arm()
        regs.r0=s.field_pointer();self.invoke(r,0x02300100)
        regs.r0=1;self.invoke(r,regs.lr & ~1)
        self.assertEqual(r.observer.pending[-1]["eventConsumed"],1)
        self.assertEqual(r.observer.pending[-1]["fieldPointer"],s.field_pointer())
        r.close()

    def test_completed_pose_detects_post_callback_overwrite_and_keeps_exact_clocks(self):
        r,s,a,e,regs,put,calls,poses=self.fixture()
        r.completed_boundary()
        self.assertIsNone(r.result()["latestCompletedPose"])
        self.assertEqual(calls,[])
        r.arm()
        self.invoke(r,0x02300000)
        self.invoke(r,regs.lr & ~1)
        callback=deepcopy(r.observer.pending[-1])
        self.assertIsNone(r.result()["latestCompletedPose"])
        poses[e["pointer"]]["pos_x"]+=1
        s.completed_frames=13;s.rt.EXECUTED_FRAME_COUNT=32
        r.completed_boundary()
        sample=r.result()["latestCompletedPose"]
        self.assertEqual((sample["frame"],sample["nativeCycle"],sample["actorFrame"]),(13,32,9))
        self.assertEqual(sample["boundary"],"main-task-queue-completion")
        self.assertEqual(callback["player"]["pos_x"],callback["mount"]["pos_x"])
        self.assertNotEqual(sample["player"]["pos_x"],sample["mount"]["pos_x"])
        self.assertEqual(len(r.observer.pending),1)
        poses[e["pointer"]]["pos_x"]-=1
        s.completed_frames=14
        r.completed_boundary()
        restored=r.result()["latestCompletedPose"]
        self.assertEqual(restored["player"]["pos_x"],restored["mount"]["pos_x"])
        self.assertEqual(sample["mount"]["pos_x"],101)
        self.assertEqual(restored["frame"],14)
        r.close()
        s.completed_frames=15;r.completed_boundary()
        self.assertEqual(r.result()["latestCompletedPose"],restored)

    def test_same_pose_reader_observes_bad_memory_and_restore_without_advancing(self):
        r,s,a,e,regs,put,calls,poses=self.fixture();r.arm()
        current=r._current();registers=vars(regs).copy();clock=r.observer._clock()
        clean=r._read_pose(current)
        poses[e["pointer"]]["pos_x"]+=1
        bad=r._read_pose(current)
        poses[e["pointer"]]["pos_x"]-=1
        restored=r._read_pose(current)
        same_pair=lambda value:value["player"]["pos_x"]==value["mount"]["pos_x"]
        self.assertTrue(same_pair(clean));self.assertFalse(same_pair(bad));self.assertTrue(same_pair(restored))
        self.assertEqual(clean,restored)
        self.assertEqual(vars(regs),registers);self.assertEqual(r.observer._clock(),clock)
        self.assertEqual(len(r.observer.pending),0)
        r.close()

    def test_completed_pose_rechecks_owner(self):
        r,s,a,e,regs,*_=self.fixture();r.arm()
        a["authorityGeneration"]+=1
        with self.assertRaises((ValueError,NativeObservationError)):r.completed_boundary()
        self.assertIsNone(r.result()["latestCompletedPose"])
        r.close()

    def test_wrong_identity_field_deadline_and_callback_bound(self):
        for fault in ("identity","field","deadline","bound"):
            r,s,a,e,regs,*_=self.fixture();r.arm()
            if fault=="identity":a["authorityGeneration"]+=1
            elif fault=="field":regs.r0=0
            elif fault=="deadline":s.completed_frames+=11
            else:r.counts["presentation"]=MAX_CALLBACKS
            with self.subTest(fault=fault),self.assertRaises((ValueError,NativeObservationError)):
                r.completed_boundary() if fault=="deadline" else self.invoke(r,0x02300100 if fault=="field" else 0x02300000)
            self.assertIsNotNone(r.close()["failure"])
            self.assertEqual(r.observer.hooks.callbacks,{})

    def test_packaged_identity_pending_cleanup_and_shared_tokens(self):
        r,s,a,e,regs,put,*_=self.fixture()
        s.code_regions=[]
        with self.assertRaises(NativeObservationError):r.arm()
        self.assertEqual(r.observer.hooks.callbacks,{})
        r,s,a,e,regs,*_=self.fixture();r.arm()
        shared=r.observer.hooks.add(0x02300000,lambda:None)
        self.invoke(r,0x02300000)
        self.assertIn("pending callback",r.close()["failure"])
        self.assertEqual(r.observer.contexts,[])
        self.assertEqual(r.observer.hooks.callbacks[0x02300000],[shared[1]])
        self.assertEqual(r.observer.return_tokens,[])

    def test_second_install_failure_retires_first_and_cannot_rearm(self):
        r,s,a,e,regs,put,*_=self.fixture()
        s.code_regions=s.code_regions[:1]
        with self.assertRaises(NativeObservationError):r.arm()
        self.assertEqual(r.observer.hooks.callbacks,{})
        self.assertTrue(r.closed)
        with self.assertRaises(NativeObservationError):r.arm()


if __name__=="__main__":unittest.main()
