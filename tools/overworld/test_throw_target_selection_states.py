"""Actual-C selection checks for TKT-0050 target states and follower cargo."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld.test_picked_up_actor_control import extract_function
from tools.overworld import test_throw_failure_composition as composition
from tools.overworld import test_throw_moving_target_selection as moving


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
HERE = ROOT / "build/tickets/tkt50-target-selection-host"

HELPER_DRIVER = r'''
static OverworldWildSpawnState state;
static OverworldWildThrowState relations;
static LocalMapObject objects[10];
static void Reset(void) {
    memset(&state,0,sizeof(state));memset(&relations,0,sizeof(relations));
    memset(objects,0,sizeof(objects));exactObject=TRUE;
    state.movementFieldSystem=&state;
    state.movementQueuedBattleSlot=state.pendingSlot=-1;
    for(int i=0;i<10;i++) {state.spawns[i].active=TRUE;state.spawns[i].object=&objects[i];}
}
static BOOL Query(int target,u8 mode) {
    return OverworldWildHelper_QueryPickupThrowTarget(
        &state,&relations,0,target,mode,0);
}
int main(void) {
    for(int mode=0;mode<8;mode++) {
        Reset();int target=mode==6?OW_WILD_FOLLOWER_SLOT:1;
        switch(mode) {
        case 0:state.captureTargetMask=1u<<target;break;
        case 1:state.movementActorControlModes[target]=OW_WILD_ACTOR_CONTROL_HELD;break;
        case 2:state.movementQueuedBattleSlot=target;break;
        case 3:state.pendingSlot=target;break;
        case 4:state.movementSpawnRunActive[target]=OW_WILD_SPAWN_ENTRY_HOP;break;
        case 5:relations.targets[target]=OW_WILD_HELPER_THROW_TARGET_ENCODE(2);
               relations.carrierMask=1u<<target;break;
        case 7:objects[target].flags=BIT_VANISH;break;
        }
        assert(Query(target,OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID));
        assert(Query(target,OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE));
        if(mode==4 || mode==7)
            assert(!Query(target,OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE));
    }
    Reset();assert(!Query(0,OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID));
    exactObject=FALSE;assert(!Query(1,OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE));
    exactObject=TRUE;state.spawns[1].active=FALSE;
    assert(!Query(1,OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID));
    state.spawns[1].active=TRUE;state.spawns[1].object=NULL;
    assert(!Query(1,OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE));
    return 0;
}
'''

OBSERVATION_DRIVER = r'''
int main(void) {
    InitCase(FALSE);
    runtime.throwState.targets[0]=0;
    runtime.throwState.carrierMask=0;
    runtime.throwState.targetMask=0;
    u32 facts=OverworldThrowObservationQuery_Observe(&state,0,&profile,blob,&conditions,
        OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,
        OverworldThrowObservation_BindingPosition);
    assert(((facts>>8)&1023)==(1u<<1));
    state.captureTargetMask=1u<<1;
    facts=OverworldThrowObservationQuery_Observe(&state,0,&profile,blob,&conditions,
        OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,
        OverworldThrowObservation_BindingPosition);
    assert(((facts>>8)&1023)==(1u<<1));
    state.captureTargetMask=0;
    runtime.throwState.targets[1]=OW_WILD_HELPER_THROW_TARGET_ENCODE(2);
    runtime.throwState.carrierMask=1u<<1;
    facts=OverworldThrowObservationQuery_Observe(&state,0,&profile,blob,&conditions,
        OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,
        OverworldThrowObservation_BindingPosition);
    assert(((facts>>8)&1023)==(1u<<1));
    runtime.throwState.targets[1]=0;
    runtime.throwState.carrierMask=1u<<0;
    runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_ENCODE(1);
    eligibleMask=(1u<<1)|(1u<<2);
    facts=OverworldThrowObservationQuery_Observe(&state,0,&profile,blob,&conditions,
        OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,
        OverworldThrowObservation_BindingPosition);
    assert(((facts>>8)&1023)==eligibleMask);
    conditions.actors[7].count=1;
    conditions.actors[7].catalogEntryIndexes[0]=cargoIndex;
    conditions.actors[7].subject=Handle(7,8);
    runtime.throwState.targets[7]=OW_WILD_HELPER_THROW_TARGET_ENCODE(1);
    facts=OverworldThrowObservationQuery_Observe(&state,7,&profile,blob,&conditions,
        OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,
        OverworldThrowObservation_BindingPosition);
    assert(((facts>>8)&1023)==(1u<<1));
    runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_ENCODE(1)|0x80;
    facts=OverworldThrowObservationQuery_Observe(&state,0,&profile,blob,&conditions,
        OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,
        OverworldThrowObservation_BindingPosition);
    assert(((facts>>8)&1023)==0);
    free(blob);
    puts("actual Observe candidate projection: all current Wild candidates, bound Follower stays selected");
    return 0;
}
'''


class ThrowTargetSelectionStateTests(unittest.TestCase):
    def test_actual_helper_accepts_each_target_state_and_follower(self):
        source = HELPER.read_text()
        prelude = moving.PRELUDE.replace("#define OW_WILD_FOLLOWER_SLOT 9",
            "#define OW_WILD_FOLLOWER_SLOT 7")
        prelude = prelude.replace("typedef uint16_t u16;", "typedef uint16_t u16;\ntypedef uint32_t u32;")
        prelude = prelude.replace("    u16 movementInProgressMask;",
            "    u16 movementInProgressMask,captureTargetMask;")
        prelude += "\n#define OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_PAUSE 2\n"
        prelude += "#define OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE 3\n"
        names = (("BOOL", "OverworldWildHelper_IsValidPickupThrowTarget"),
                 ("BOOL", "OverworldWildHelper_IsEligiblePickupThrowTarget"),
                 ("BOOL", "OverworldWildHelper_ShouldPauseReservedPickupTarget"),
                 ("BOOL", "OverworldWildHelper_QueryPickupThrowTarget"))
        harness = "\n".join([prelude] + [extract_function(source, name, result)
            for result, name in names] + [HELPER_DRIVER])
        HERE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tkt50-helper-") as directory:
            unit, binary = Path(directory) / "test.c", Path(directory) / "test"
            unit.write_text(harness)
            compiled = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
                str(unit), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_observation_keeps_capture_and_carrier_candidates(self):
        source = composition.fixture().split("int main(void) {", 1)[0] + OBSERVATION_DRIVER
        with patch.object(composition, "HERE", HERE):
            result = composition.run(source, "tkt50-observation")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
