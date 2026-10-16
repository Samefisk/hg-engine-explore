"""Host proof that selection can reserve motion while pickup still waits."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.overworld.test_picked_up_actor_control import extract_function


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>

typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_SPAWN_ENTRY_HOP 2
#define OW_WILD_HELPER_THROW_TARGET_NONE 0
#define OW_WILD_HELPER_THROW_TARGET_ENCODE(slot) ((u8)((slot) + 1))
#define OW_WILD_HELPER_THROW_RESERVATION_DECISIONS 120
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID 0
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE 1
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_PAUSE 2
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE 3
#define BIT_VANISH 1

typedef struct LocalMapObject { u8 activeMovement; unsigned flags; } LocalMapObject;
typedef struct OverworldWildSpawn { LocalMapObject *object; u8 active; } OverworldWildSpawn;
typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    void *movementFieldSystem;
    u8 movementActorControlModes[OW_WILD_MAX_SPAWNS];
    int movementQueuedBattleSlot, pendingSlot;
    u8 movementSpotStates[OW_WILD_MAX_SPAWNS];
    u8 movementSpawnRunActive[OW_WILD_MAX_SPAWNS];
    u8 movementStagedHopPending[OW_WILD_MAX_SPAWNS];
    u8 movementRamCrashShakeTimers[OW_WILD_MAX_SPAWNS];
    u8 movementTeleportHidden[OW_WILD_MAX_SPAWNS];
    u8 movementTeleportFlickerTimers[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementTeleportFlickerObjects[OW_WILD_MAX_SPAWNS];
    u16 movementInProgressMask;
    u8 movementEmoteTimers[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;
typedef struct OverworldWildThrowState {
    u8 targets[OW_WILD_MAX_SPAWNS];
    u16 targetMask, carrierMask;
} OverworldWildThrowState;
typedef struct OverworldWildPresentationState {
    u8 farSamples[OW_WILD_MAX_SPAWNS];
} OverworldWildPresentationState;

static BOOL exactObject = TRUE;
static BOOL OverworldWildHelper_IsPickupThrowMovementContextCurrent(
    OverworldWildSpawnState *state) { return state->movementFieldSystem != 0; }
static BOOL OverworldWildHelper_IsExactObject(
    void *fieldSystem, OverworldWildSpawnState *state, int slot)
{ (void)fieldSystem; (void)state; (void)slot; return exactObject; }
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *object)
{ return object->activeMovement != 0; }
'''

DRIVER = r'''
static BOOL TryReserve(OverworldWildSpawnState *state,
    OverworldWildThrowState *relations,
    OverworldWildPresentationState *presentation, u16 walkMask)
{
    return OverworldWildHelper_TryStartPickupThrowAction(
        state, relations, presentation, 0, 1, 1u << 1, walkMask);
}

int main(void)
{
    OverworldWildSpawnState state;
    OverworldWildThrowState relations;
    OverworldWildPresentationState presentation;
    LocalMapObject carrier, target;
    /* Wild and Follower selection changes relations, never target state. */
    for (int slot=0;slot<=OW_WILD_FOLLOWER_SLOT;slot+=OW_WILD_FOLLOWER_SLOT) {
        memset(&state,0,sizeof(state));memset(&relations,0,sizeof(relations));
        memset(&presentation,0,sizeof(presentation));
        memset(&carrier,0,sizeof(carrier));memset(&target,0,sizeof(target));
        state.movementFieldSystem=&state;
        state.spawns[slot].active=state.spawns[1].active=TRUE;
        state.spawns[slot].object=&carrier;state.spawns[1].object=&target;
        target.activeMovement=TRUE;target.flags=8;
        state.movementInProgressMask=2;state.movementSpotStates[1]=1;
        state.movementEmoteTimers[1]=33;state.movementStagedHopPending[1]=1;
        OverworldWildSpawnState before=state;LocalMapObject beforeTarget=target;
        assert(OverworldWildHelper_TryStartPickupThrowAction(
            &state,&relations,&presentation,slot,1,2,0));
        assert(relations.targets[slot]==OW_WILD_HELPER_THROW_TARGET_ENCODE(1));
        assert(relations.targetMask==2&&relations.carrierMask==(1u<<slot));
        assert(memcmp(&state,&before,sizeof(state))==0);
        assert(memcmp(&target,&beforeTarget,sizeof(target))==0);
        assert(!OverworldWildHelper_QueryPickupThrowTarget(
            &state,&relations,slot,1,OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_PAUSE,0));
    }
    memset(&state, 0, sizeof(state));
    memset(&relations, 0, sizeof(relations));
    memset(&presentation, 0, sizeof(presentation));
    memset(&carrier, 0, sizeof(carrier));
    memset(&target, 0, sizeof(target));
    state.movementFieldSystem = &state;
    state.movementQueuedBattleSlot = -1;
    state.pendingSlot = -1;
    state.spawns[0].active = state.spawns[1].active = TRUE;
    state.spawns[0].object = &carrier;
    state.spawns[1].object = &target;
    target.activeMovement = TRUE;
    state.movementInProgressMask = 1u << 1;

    /* Selection reserves an ordinary Walk. Physical pickup still waits. */
    assert(TryReserve(&state, &relations, &presentation, 0));
    assert(relations.targets[0] == OW_WILD_HELPER_THROW_TARGET_ENCODE(1));
    assert(relations.targetMask == (1u << 1));
    assert(relations.carrierMask == (1u << 0));
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE,
        1u << 1));
    target.activeMovement = FALSE;
    state.movementInProgressMask = 0;
    assert(OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE, 0));

    /* Selection keeps a current actor, while stable pickup rejects motion. */
    memset(&relations, 0, sizeof(relations));
    target.activeMovement = TRUE;
    state.movementInProgressMask = 1u << 1;
    state.movementSpotStates[1] = 1;
    assert(OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE, 0));
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE, 0));
    state.movementSpotStates[1] = 0;
    state.movementSpawnRunActive[1] = OW_WILD_SPAWN_ENTRY_HOP;
    assert(OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE, 0));
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE, 0));
    state.movementSpawnRunActive[1] = 0;
    state.movementStagedHopPending[1] = 1;
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE, 0));
    state.movementStagedHopPending[1] = 0;
    state.movementTeleportHidden[1] = 1;
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE, 0));
    state.movementTeleportHidden[1] = 0;
    state.movementActorControlModes[1] = OW_WILD_ACTOR_CONTROL_HELD;
    assert(OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE, 0));
    state.movementActorControlModes[1] = 0;
    exactObject = FALSE;
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE, 0));
    exactObject = TRUE;
    target.flags = BIT_VANISH;
    assert(OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE, 0));
    assert(!OverworldWildHelper_QueryPickupThrowTarget(
        &state, &relations, 0, 1, OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE, 0));
    return 0;
}
'''


class MovingThrowTargetTests(unittest.TestCase):
    def test_moving_walk_reserves_then_waits_for_safe_pickup(self):
        source = HELPER.read_text(encoding="utf-8")
        functions = (
            ("BOOL", "OverworldWildHelper_IsValidPickupThrowTarget"),
            ("BOOL", "OverworldWildHelper_IsEligiblePickupThrowTarget"),
            ("BOOL", "OverworldWildHelper_ShouldPauseReservedPickupTarget"),
            ("BOOL", "OverworldWildHelper_QueryPickupThrowTarget"),
            ("BOOL", "OverworldWildHelper_TryStartPickupThrowAction"),
        )
        harness = "\n".join(
            [PRELUDE]
            + [extract_function(source, name, returns) for returns, name in functions]
            + [DRIVER]
        )
        with tempfile.TemporaryDirectory(prefix="moving-throw-target-") as directory:
            source_path = Path(directory) / "test.c"
            executable = Path(directory) / "test"
            source_path.write_text(harness, encoding="utf-8")
            compiled = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 str(source_path), "-o", str(executable)],
                capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
