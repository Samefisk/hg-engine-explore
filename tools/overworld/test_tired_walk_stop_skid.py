"""S1 regressions for normal Wild-Walk stop handoffs.

The Tired timer is lifecycle state, not Movement Chain state.  When a Tired
Walk naturally ends, the Wild adapter must submit a genuine Walk NONE before
it changes lanes so the shared policy can start a stop skid.  The direction
planner must use the same direct handoff when every next Walk step is blocked.
"""

from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harness_source() -> str:
    extract = load_module(
        "tired_stop_extract",
        ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py",
    )
    blocked_body = extract.production_function(
        WILD.read_text(), "OverworldWildSpawns_TryStartBlockedWalkStopSkid", "BOOL"
    )
    tired_body = extract.production_function(
        WILD.read_text(), "OverworldWildSpawns_TickTiredEmote", "BOOL"
    )
    return SUPPORT + blocked_body + tired_body + DRIVER


SUPPORT = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0

#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 3
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 6
#define OW_WILD_SPAWNER_ASLEEP_REST_TIMER 255
#define OW_WILD_BEHAVIOR_STOP_SKID_MASK 0x80
#define OW_WILD_BEHAVIOR_STOPS_WITH_SKID(options) \
    (((options) & OW_WILD_BEHAVIOR_STOP_SKID_MASK) != 0)

typedef struct LocalMapObject { u8 active; } LocalMapObject;
typedef struct OverworldWildBehaviorProfileData {
    u8 marker;
    u8 tilesBeforeTurnSkid;
} OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile {
    u8 tiredState;
    OverworldWildBehaviorProfileData owner;
    OverworldWildBehaviorProfileData active;
    OverworldWildBehaviorProfileData tired;
} OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { u8 tiredLocomotion; } OverworldWildBehaviorPrimitives;
typedef struct OverworldWildSpawnState {
    u8 movementSpotStates[10];
    u8 movementEmoteTimers[10];
} OverworldWildSpawnState;

static OverworldWildBehaviorProfile resolvedProfile;
static OverworldWildBehaviorPrimitives resolvedPrimitives;
static unsigned stopSkidCalls;
static unsigned cooldownCalls;
static BOOL startStopSkid;
static u8 stopLaneMarker;
static u8 stopLaneState;

static BOOL OverworldWildSpawns_BehaviorKindUsesMovement(u8 tiredState)
{
    return tiredState == 1;
}

static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetBehaviorStateLane(
    const OverworldWildBehaviorProfile *profile, u8 spotState)
{
    return spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? &profile->tired : &profile->owner;
}

static BOOL OverworldWildSpawns_TryStartWalkStopSkid(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorProfileData *lane)
{
    (void)state;
    (void)slot;
    (void)profile;
    stopSkidCalls++;
    stopLaneMarker = lane->marker;
    stopLaneState = state->movementSpotStates[slot];
    return startStopSkid;
}

static void OverworldWildSpawns_StartTiredCooldown(
    OverworldWildSpawnState *state, int slot)
{
    cooldownCalls++;
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
}

static BOOL MapObject_IsSingleMovementActive(LocalMapObject *object)
{
    return object != NULL && object->active;
}

static void MapObject_ClearSingleMovementActive(LocalMapObject *object)
{
    object->active = 0;
}
"""


DRIVER = r"""
static void Reset(OverworldWildSpawnState *state)
{
    memset(state, 0, sizeof(*state));
    memset(&resolvedProfile, 0, sizeof(resolvedProfile));
    memset(&resolvedPrimitives, 0, sizeof(resolvedPrimitives));
    state->movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_TIRED;
    resolvedProfile.tiredState = 1;
    stopSkidCalls = 0;
    cooldownCalls = 0;
    startStopSkid = FALSE;
    resolvedProfile.tired.marker = 7;
    resolvedProfile.tired.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_STOP_SKID_MASK;
    stopLaneMarker = 0;
    stopLaneState = 0;
}

int main(void)
{
    OverworldWildSpawnState state;
    LocalMapObject object = {0};
    BOOL started;

    Reset(&state);
    state.movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    resolvedProfile.owner.marker = 8;
    resolvedProfile.owner.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_STOP_SKID_MASK;
    startStopSkid = TRUE;
    started = OverworldWildSpawns_TryStartBlockedWalkStopSkid(
        &state, 0, &resolvedProfile, &resolvedProfile.owner,
        OW_WILD_BEHAVIOR_LOCOMOTION_WANDER, FALSE, TRUE, 4);
    if (!started
        || stopSkidCalls != 1 || stopLaneMarker != 8
        || stopLaneState != OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        fprintf(stderr, "blocked Walk did not enter direct stop skid: %d %u %u %u\n",
            started, stopSkidCalls, stopLaneMarker, stopLaneState);
        return 1;
    }

    Reset(&state);
    state.movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    resolvedProfile.owner.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_STOP_SKID_MASK;
    startStopSkid = TRUE;
    if (!OverworldWildSpawns_TryStartBlockedWalkStopSkid(
            &state, 0, &resolvedProfile, &resolvedProfile.owner,
            OW_WILD_BEHAVIOR_LOCOMOTION_WANDER, FALSE, FALSE, 0)
        || stopSkidCalls != 1) {
        fprintf(stderr, "empty Walk direction set did not enter direct stop skid\n");
        return 2;
    }

    for (u8 rejected = 0; rejected < 4; rejected++) {
        BOOL enabled = rejected != 0;
        BOOL locked = rejected == 1;
        u8 locomotion = rejected == 2
            ? OW_WILD_BEHAVIOR_LOCOMOTION_HOP
            : OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
        BOOL blocked = rejected != 3;

        Reset(&state);
        state.movementSpotStates[0] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
        resolvedProfile.owner.tilesBeforeTurnSkid = enabled
            ? OW_WILD_BEHAVIOR_STOP_SKID_MASK : 0;
        startStopSkid = TRUE;
        if (OverworldWildSpawns_TryStartBlockedWalkStopSkid(
                &state, 0, &resolvedProfile, &resolvedProfile.owner,
                locomotion, locked, blocked, 4)
            || stopSkidCalls != 0) {
            fprintf(stderr, "non-stop Walk state entered blocked stop skid\n");
            return 3;
        }
    }

    Reset(&state);
    state.movementEmoteTimers[0] = 1;
    resolvedPrimitives.tiredLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
    startStopSkid = TRUE;
    if (!OverworldWildSpawns_TickTiredEmote(
            &state, 0, &object, &resolvedProfile, &resolvedPrimitives, FALSE)
        || state.movementEmoteTimers[0] != 0
        || state.movementSpotStates[0] != OW_WILD_SPAWNER_SPOT_STATE_TIRED
        || stopSkidCalls != 1 || cooldownCalls != 0
        || stopLaneMarker != 7
        || stopLaneState != OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        fprintf(stderr, "natural Tired Walk stop bypassed stop skid\n");
        return 4;
    }

    startStopSkid = FALSE;
    if (!OverworldWildSpawns_TickTiredEmote(
            &state, 0, &object, &resolvedProfile, &resolvedPrimitives, FALSE)
        || stopSkidCalls != 2 || cooldownCalls != 1
        || state.movementSpotStates[0] != OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        fprintf(stderr, "finished stop skid did not enter Chill\n");
        return 5;
    }

    for (u8 locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
         locomotion <= OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
         locomotion += OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT
            - OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        Reset(&state);
        resolvedPrimitives.tiredLocomotion = locomotion;
        startStopSkid = TRUE;
        if (!OverworldWildSpawns_TickTiredEmote(
                &state, 0, &object, &resolvedProfile, &resolvedPrimitives, FALSE)
            || stopSkidCalls != 0 || cooldownCalls != 1
            || state.movementSpotStates[0] != OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
            fprintf(stderr, "non-Walk Tired lane entered Walk stop skid\n");
            return 6;
        }
    }

    Reset(&state);
    resolvedPrimitives.tiredLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
    resolvedProfile.tired.tilesBeforeTurnSkid = 0;
    startStopSkid = TRUE;
    if (!OverworldWildSpawns_TickTiredEmote(
            &state, 0, &object, &resolvedProfile, &resolvedPrimitives, FALSE)
        || stopSkidCalls != 0 || cooldownCalls != 1
        || state.movementSpotStates[0] != OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        fprintf(stderr, "Walk lane without stop skid entered a skid\n");
        return 7;
    }

    Reset(&state);
    state.movementEmoteTimers[0] = 1;
    resolvedPrimitives.tiredLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
    startStopSkid = TRUE;
    if (!OverworldWildSpawns_TickTiredEmote(
            &state, 0, &object, &resolvedProfile, &resolvedPrimitives, TRUE)
        || state.movementEmoteTimers[0] != 0
        || state.movementSpotStates[0] != OW_WILD_SPAWNER_SPOT_STATE_TIRED
        || stopSkidCalls != 0 || cooldownCalls != 0) {
        fprintf(stderr, "settling Tired Walk did not defer stop skid\n");
        return 8;
    }
    if (!OverworldWildSpawns_TickTiredEmote(
            &state, 0, &object, &resolvedProfile, &resolvedPrimitives, FALSE)
        || state.movementSpotStates[0] != OW_WILD_SPAWNER_SPOT_STATE_TIRED
        || stopSkidCalls != 1 || cooldownCalls != 0) {
        fprintf(stderr, "idle Tired Walk did not start deferred stop skid\n");
        return 9;
    }

    puts("Tired Walk stop uses the normal Walk stop-skid handoff");
    return 0;
}
"""


class WildWalkStopSkidTests(unittest.TestCase):
    def test_wild_walk_stop_boundaries_use_direct_stop_input(self):
        with tempfile.TemporaryDirectory(prefix="ow-tired-stop-") as directory:
            source = Path(directory) / "tired_stop.c"
            binary = Path(directory) / "tired_stop"
            source.write_text(harness_source())
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=gnu11",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(source),
                    "-o",
                    str(binary),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(
                [str(binary)], cwd=ROOT, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
