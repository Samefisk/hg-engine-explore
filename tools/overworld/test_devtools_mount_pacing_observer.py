"""Actual shared _tap dispatch with host memory; no gameplay proof."""
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import unittest

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
        s.rt.object_state = lambda emu,pointer: deepcopy(poses[pointer])
        names = {"OverworldMount_SyncPresentation":0x02300000,"OverworldMount_PlayerStepBridge":0x02300100}
        s.rt.MOUNT_SYMBOLS = names
        code = bytes(range(32))
        s.code_regions = [(a,code) for a in names.values()]
        for address in names.values(): put(address,code)
        regs.lr=0x02010001
        observer = NativeObservation(s, _.observer.hooks, lambda path,address,size:code)
        s.native_observation=observer
        checked = {**actor,"identityVerified":True,"engineIdentity":{**engine,"anchorPointer":player,"anchorInCurrentManager":True}}
        bound = select_current_actor(dict(frame=12,context=dict(fieldEpoch=2,mapGeneration=3),actors=[checked]),checked)
        reader=NativeMountedPacingObserver(s,bound,10)
        return reader,s,actor,engine,regs,put,calls,poses

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
