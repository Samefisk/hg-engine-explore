"""Host controls for fixed native route faults; not live calibration proof."""
from copy import deepcopy
from pathlib import Path
import re
import struct
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_route_control import NativeRouteControl, RouteControlFailure
from tools.overworld.test_devtools_cadence_measurement import Route, player


class NativeRouteControlTests(unittest.TestCase):
    def test_pin_offsets_match_actual_arm32_object_header(self):
        source = '#include "map_events_internal.h"\nconst unsigned offsets[]={sizeof(LocalMapObject),__builtin_offsetof(LocalMapObject,posVec),__builtin_offsetof(LocalMapObject,posVec)+2*sizeof(u32)};\n'
        result = subprocess.run(["clang","-target","armv5te-none-eabi","-ffreestanding","-w",
            "-Iinclude","-I.","-x","c","-S","-emit-llvm","-o","-","-"], input=source,
            cwd=Path(__file__).resolve().parents[2],text=True,capture_output=True,check=True,timeout=15)
        row=next(line for line in result.stdout.splitlines() if line.startswith("@offsets ="))
        self.assertEqual(tuple(map(int,re.findall(r"i32 (\d+)",row))),(0x12C,0x70,0x78))

    def fixture(self):
        actor=deepcopy(Route().actor);pose=player();pointer=0x02030000;manager=0x02020000
        memory={0x02100000:0x5353574F,0x0210000C:2,0x0210002E:3,
                manager+0x124:pointer,manager+4:1,pointer+0xB4:manager}
        writes=[]
        def write(emu,address,data):
            writes.append((address,data))
            pose[{pointer+0x70:"pos_x",pointer+0x78:"pos_z"}[address]]=struct.unpack("<i",data)[0]
        rt=SimpleNamespace(EXECUTED_FRAME_COUNT=20,
            ACTOR_DESCRIPTOR={"state":{"address":0x02100000,"offsets":{"fieldEpoch":12,"mapGeneration":46}}},
            unsigned=lambda emu,a,n=4:memory[a],field_map_id=lambda emu:33,
            actor_state=lambda emu,slot:actor,wild_spawn=lambda emu,slot:actor["sourceIdentity"],
            live_wild_object_identity=lambda emu,slot:actor["engineIdentity"],player_ptr=lambda emu:pointer,
            object_state=lambda emu,p:deepcopy(pose),actor_memory_write=write)
        s=SimpleNamespace(rt=rt,emu=object(),closed=False,native_bridge_active=False,completed_frames=10)
        return NativeRouteControl(s,actor),s,actor,pose,memory,writes

    def arm_player(self,control,session):
        control.arm("cpu-hitch")
        with patch("tools.overworld.devtools_route_control.time.process_time_ns",side_effect=[0,100_000_000,100_000_000]):
            control.before_cycle()
        session.rt.EXECUTED_FRAME_COUNT+=1
        control.arm("player-start-stall",max_frames=8)

    def admission(self,pose):
        before=deepcopy(pose);after=deepcopy(before)
        after.update(x=1,x_prev=0,y_prev=0)
        return {"objectPointer":0x02030000,"mapId":33,"objectBefore":before,"objectAfter":after,
                "origin":[0,0],"target":[1,0],"stepIndex":1}

    def test_cpu_work_is_measured_once_and_marks_actual_next_cycle(self):
        control,s,*_=self.fixture();control.arm("cpu-hitch")
        with patch("tools.overworld.devtools_route_control.time.process_time_ns",side_effect=[5,100_000_005,100_000_006]) as timer:
            control.before_cycle();control.before_cycle()
        self.assertEqual(timer.call_count,3)
        row=control.result()["receipts"][-1]
        self.assertEqual((row["nativeCycleBefore"],row["targetNativeCycle"],row["workCpuNs"]),(20,21,100_000_001))
        self.assertFalse(control.close()["requiresCoreClose"])

    def test_pin_uses_admission_origin_not_advanced_pose_and_requires_core_close(self):
        control,s,actor,pose,memory,writes=self.fixture();self.arm_player(control,s)
        receipt=self.admission(pose)
        pose.update(x=1,pos_x=49152)
        control.player_step_admitted(receipt)
        for frame in (11,12,13):
            pose["pos_x"]=49152;s.completed_frames=frame
            control.completed_boundary();control.completed_boundary()
            self.assertEqual(pose["pos_x"],32768)
        self.assertEqual(len(writes),6)
        closed=control.close()
        self.assertTrue(closed["requiresCoreClose"])
        self.assertTrue(s.route_control_nonresumable)
        control.completed_boundary()
        self.assertEqual(len(writes),6)
        closed["receipts"].clear()
        self.assertTrue(control.result()["receipts"])

    def test_wrong_follower_player_or_context_never_writes(self):
        for fault in ("pid","role","manager","inactive","context","generation"):
            with self.subTest(fault=fault):
                control,s,actor,pose,memory,writes=self.fixture();self.arm_player(control,s)
                if fault=="pid":actor["subjectIdentity"]+=1
                elif fault=="role":actor["role"]="MOUNTED"
                elif fault=="manager":memory[0x02030000+0xB4]=0
                elif fault=="inactive":pose["flags"]=0
                elif fault=="context":memory[0x0210000C]=3
                else:actor["presentationGeneration"]+=1
                with self.assertRaises(RouteControlFailure):control.player_step_admitted(self.admission(pose))
                self.assertEqual(writes,[])

    def test_order_bounds_and_second_admission_reject(self):
        control,s,*_=self.fixture()
        with self.assertRaises(RouteControlFailure):control.arm("player-start-stall")
        for maximum in (0,121,True):
            control,s,*_=self.fixture()
            with self.assertRaises(ValueError):control.arm("cpu-hitch",maximum)
        control,s,actor,pose,*_=self.fixture();self.arm_player(control,s)
        control.player_step_admitted(self.admission(pose))
        with self.assertRaises(RouteControlFailure):control.player_step_admitted(self.admission(pose))

    def test_missed_frame_and_bad_origin_fail(self):
        for fault in ("gap","origin","limit"):
            control,s,actor,pose,*_=self.fixture();self.arm_player(control,s)
            receipt=self.admission(pose)
            if fault=="origin":
                receipt["objectBefore"]["pos_x"]+=1
                with self.assertRaises(RouteControlFailure):control.player_step_admitted(receipt)
            else:
                control.player_step_admitted(receipt)
                s.completed_frames=12 if fault=="gap" else 19
                with self.assertRaises(RouteControlFailure):control.completed_boundary()

    def test_failed_write_is_fatal_and_never_restored_for_gameplay(self):
        control,s,actor,pose,memory,writes=self.fixture();self.arm_player(control,s)
        control.player_step_admitted(self.admission(pose));s.completed_frames=11
        s.rt.actor_memory_write=lambda *args:(_ for _ in ()).throw(RuntimeError("write"))
        with self.assertRaises(RouteControlFailure) as caught:control.completed_boundary()
        self.assertTrue(caught.exception.fatal)
        self.assertTrue(control.close()["requiresCoreClose"])


if __name__ == "__main__":unittest.main()
