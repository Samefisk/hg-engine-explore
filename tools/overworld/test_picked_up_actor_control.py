"""Focused host and source proof for internal held-actor control."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
SPAWNS_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
RESOLVER_SOURCE = ROOT / "lib/overworld/overworld_behavior_resolver.c"
INTERNAL_HEADER = ROOT / "include/overworld_wild_spawns_internal.h"


def extract_function(source: str, name: str, returns: str) -> str:
    pattern = re.compile(
        r"\b(?:static\s+)?"
        + re.escape(returns)
        + r"\b[^;{}]*?\b"
        + re.escape(name)
        + r"\s*\([^;{}]*\)\s*\{"
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected one definition of {name}")
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            start = source.index(name, match.start(), match.end())
            return f"static {returns} " + source[start : end + 1]
    raise ValueError(f"unterminated {name}")


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
#define OW_WILD_HELPER_THROW_TARGET_NONE 0
#define OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG 0x80
#define OW_WILD_HELPER_THROW_TARGET_SLOT_MASK 0x3F
#define OW_WILD_HELPER_THROW_TARGET_ENCODE(slot) ((u8)((slot) + 1))
#define OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(slot) \
    ((u8)(OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG | OW_WILD_HELPER_THROW_TARGET_ENCODE(slot)))
#define OW_WILD_HELPER_THROW_TARGET_DECODE(value) \
    ((u8)(((value) & OW_WILD_HELPER_THROW_TARGET_SLOT_MASK) - 1))
#define OW_WILD_HELPER_PRESENTATION_NORMALIZE_SLOT 0
#define MAPOBJECTFLAG_UNK18 (1u << 18)
#define BIT_VANISH (1u << 0)

typedef struct LocalMapObject {
    uint32_t flags;
} LocalMapObject;

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u8 active;
} OverworldWildSpawn;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    void *movementFieldSystem;
    u8 movementSpotStates[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteTimers[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorClasses[OW_WILD_MAX_SPAWNS];
    u8 movementActorControlModes[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;

typedef struct OverworldWildThrowState {
    u8 targets[OW_WILD_MAX_SPAWNS];
    u16 targetMask;
    u16 carrierMask;
    u16 recoveringMask;
} OverworldWildThrowState;

typedef struct OverworldWildPresentationState {
    u8 farSamples[OW_WILD_MAX_SPAWNS];
} OverworldWildPresentationState;

typedef struct OverworldWildHelperOverlayEntry {
    int available;
} OverworldWildHelperOverlayEntry;

static int clear_walk_count;
static int normalize_count;
static int shadow_count;
static int sync_count;
static int held_when_synced;
static int mode_when_walk_cleared;
/* This fixture has no condition state; the condition owner is covered by the joined composition fixture. */
static void OverworldWildSpawns_ClearPendingNotices(OverworldWildSpawnState *state,int slot) { (void)state;(void)slot; }
static BOOL context_current = TRUE;
static OverworldWildHelperOverlayEntry helper_entry;

static BOOL OverworldWildHelper_IsPickupThrowMovementContextCurrent(
    OverworldWildSpawnState *state)
{
    return state != 0 && context_current;
}

static BOOL OverworldWildHelper_IsExactObject(
    void *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    (void)fieldSystem;
    return state != 0 && state->spawns[slot].object != 0;
}

static void OverworldWildHelper_SyncCarriedThrowTarget(
    void *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int carrierSlot,
    int targetSlot)
{
    (void)fieldSystem;
    (void)presentation;
    (void)carrierSlot;
    sync_count++;
    held_when_synced = state->movementActorControlModes[targetSlot];
}

static void OverworldWildSpawns_ClearWalkMovementState(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    (void)object;
    clear_walk_count++;
    mode_when_walk_cleared = state->movementActorControlModes[slot];
}

static const OverworldWildHelperOverlayEntry *
OverworldWildSpawns_GetHelperOverlayEntry(void)
{
    return &helper_entry;
}

static BOOL OverworldWildSpawns_ApplyPresentationCommand(
    void *fieldSystem,
    OverworldWildSpawnState *state,
    int command,
    u8 slot)
{
    (void)fieldSystem;
    (void)state;
    (void)command;
    (void)slot;
    normalize_count++;
    return TRUE;
}

static void OverworldWildSpawns_ReconcileNativeShadow(
    void *fieldSystem,
    LocalMapObject *object)
{
    (void)fieldSystem;
    (void)object;
    shadow_count++;
}
'''


DRIVER_PRELUDE = r'''
static void ReleaseMask(OverworldWildSpawnState *state, u16 mask)
{
    int slot;

    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        if ((mask & (1u << slot)) != 0) {
            OverworldWildSpawns_ReleaseHeldActorControl(state, slot);
        }
    }
}
'''

DRIVER = DRIVER_PRELUDE + r'''
int main(void)
{
    OverworldWildSpawnState state;
    OverworldWildThrowState throwState;
    OverworldWildPresentationState presentation;
    LocalMapObject carrier;
    LocalMapObject target;
    u16 restoreMask;

    memset(&state, 0, sizeof(state));
    memset(&throwState, 0, sizeof(throwState));
    memset(&presentation, 0, sizeof(presentation));
    memset(&carrier, 0, sizeof(carrier));
    memset(&target, 0, sizeof(target));
    state.spawns[0].active = TRUE;
    state.spawns[0].object = &carrier;
    state.spawns[1].active = TRUE;
    state.spawns[1].object = &target;
    state.movementBehaviorClasses[1] = 2;
    throwState.targets[0] = OW_WILD_HELPER_THROW_TARGET_ENCODE(1);
    throwState.targetMask = 1u << 1;
    throwState.carrierMask = 1u << 0;

    assert(OverworldWildHelper_StartCarriedThrowTarget(
        &state, &throwState, &presentation, 0, 1));
    assert(state.movementActorControlModes[1] == OW_WILD_ACTOR_CONTROL_HELD);
    assert(state.movementBehaviorClasses[1] == 2);
    assert(held_when_synced == OW_WILD_ACTOR_CONTROL_HELD);
    assert(sync_count == 1);
    assert(throwState.targets[0]
        == OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(1));
    assert((throwState.targetMask & (1u << 1)) != 0);
    assert((throwState.carrierMask & (1u << 0)) != 0);

    /* Carrier cancellation releases its held target without changing class. */
    restoreMask = OverworldWildHelper_ClearPickupThrowState(
        &state, &throwState, &presentation, 0, TRUE);
    assert(restoreMask == (1u << 1));
    ReleaseMask(&state, restoreMask);
    assert(state.movementActorControlModes[1]
        == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(state.movementBehaviorClasses[1] == 2);
    assert(mode_when_walk_cleared == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(clear_walk_count == 1 && normalize_count == 1 && shadow_count == 1);

    /* Target cleanup, used by drop/despawn paths, releases the same state. */
    throwState.targets[0] = OW_WILD_HELPER_THROW_TARGET_ENCODE(1);
    throwState.targetMask = 1u << 1;
    throwState.carrierMask = 1u << 0;
    assert(OverworldWildHelper_StartCarriedThrowTarget(
        &state, &throwState, &presentation, 0, 1));
    restoreMask = OverworldWildHelper_ClearPickupThrowState(
        &state, &throwState, &presentation, 1, TRUE);
    assert(restoreMask == (1u << 1));
    ReleaseMask(&state, restoreMask);
    assert(state.movementActorControlModes[1]
        == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(state.movementBehaviorClasses[1] == 2);

    /* Throw completion can release directly after movement ends. */
    state.movementActorControlModes[1] = OW_WILD_ACTOR_CONTROL_HELD;
    OverworldWildSpawns_ReleaseHeldActorControl(&state, 1);
    assert(state.movementActorControlModes[1]
        == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(state.movementBehaviorClasses[1] == 2);
    return 0;
}
'''


RECOVERY_DRIVER = DRIVER_PRELUDE + r'''
static void PrepareRecoveringCargo(
    OverworldWildSpawnState *state,
    OverworldWildThrowState *throwState,
    OverworldWildPresentationState *presentation,
    LocalMapObject *carrier,
    LocalMapObject *target)
{
    memset(state, 0, sizeof(*state));
    memset(throwState, 0, sizeof(*throwState));
    memset(presentation, 0, sizeof(*presentation));
    memset(carrier, 0, sizeof(*carrier));
    memset(target, 0, sizeof(*target));
    state->spawns[0].active = TRUE;
    state->spawns[0].object = carrier;
    state->spawns[1].active = TRUE;
    state->spawns[1].object = target;
    state->movementSpotStates[1] = 3; /* TIRED after its own Throw. */
    state->movementEmoteTimers[1] = 59;
    state->movementEmoteTimers[2] = 44;
    state->movementBehaviorClasses[1] = 2;
    throwState->targets[0] = OW_WILD_HELPER_THROW_TARGET_ENCODE(1);
    throwState->targetMask = 1u << 1;
    throwState->carrierMask = 1u << 0;
    throwState->recoveringMask = (1u << 1) | (1u << 2) | (1u << 4);
    context_current = TRUE;
}

int main(void)
{
    OverworldWildSpawnState state, beforeState;
    OverworldWildThrowState throwState, beforeThrow;
    OverworldWildPresentationState presentation, beforePresentation;
    LocalMapObject carrier, target, beforeCarrier, beforeTarget;
    int fault, beforeSync;
    u16 restoreMask;

    /* Both carrier roles use the same physical transition into held control. */
    for (int slot=0;slot<=OW_WILD_FOLLOWER_SLOT;slot+=OW_WILD_FOLLOWER_SLOT) {
        PrepareRecoveringCargo(&state,&throwState,&presentation,&carrier,&target);
        if (slot) {
            state.spawns[slot]=state.spawns[0];
            throwState.targets[slot]=throwState.targets[0];throwState.targets[0]=0;
            throwState.carrierMask=1u<<slot;
        }
        assert(state.movementActorControlModes[1]==OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
        assert(state.movementSpotStates[1]==3&&state.movementEmoteTimers[1]==59);
        assert(OverworldWildHelper_StartCarriedThrowTarget(
            &state,&throwState,&presentation,slot,1));
        assert(state.movementActorControlModes[1]==OW_WILD_ACTOR_CONTROL_HELD);
        assert(state.movementSpotStates[1]==0&&state.movementEmoteTimers[1]==0);
        assert(throwState.targets[slot]==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(1));
        assert(held_when_synced==OW_WILD_ACTOR_CONTROL_HELD);
    }

    /* Failed pickup must not erase recovery or change any owned state. */
    for (fault = 0; fault < 6; fault++) {
        PrepareRecoveringCargo(
            &state, &throwState, &presentation, &carrier, &target);
        if (fault == 0) throwState.targets[0] = 0;
        if (fault == 1) throwState.targetMask = 0;
        if (fault == 2) throwState.carrierMask = 0;
        if (fault == 3) context_current = FALSE;
        if (fault == 4) state.spawns[0].object = 0;
        if (fault == 5) state.spawns[1].object = 0;
        beforeState = state;
        beforeThrow = throwState;
        beforePresentation = presentation;
        beforeCarrier = carrier;
        beforeTarget = target;
        beforeSync = sync_count;
        assert(!OverworldWildHelper_StartCarriedThrowTarget(
            &state, &throwState, &presentation, 0, 1));
        assert(memcmp(&state, &beforeState, sizeof(state)) == 0);
        assert(memcmp(&throwState, &beforeThrow, sizeof(throwState)) == 0);
        assert(memcmp(&presentation, &beforePresentation, sizeof(presentation)) == 0);
        assert(memcmp(&carrier, &beforeCarrier, sizeof(carrier)) == 0);
        assert(memcmp(&target, &beforeTarget, sizeof(target)) == 0);
        assert(sync_count == beforeSync);
    }

    PrepareRecoveringCargo(
        &state, &throwState, &presentation, &carrier, &target);
    assert(OverworldWildHelper_StartCarriedThrowTarget(
        &state, &throwState, &presentation, 0, 1));
    assert(state.movementActorControlModes[1] == OW_WILD_ACTOR_CONTROL_HELD);
    assert(state.movementSpotStates[1] == 0);
    assert(state.movementEmoteTimers[1] == 0);
    assert((throwState.recoveringMask & (1u << 1)) == 0);
    assert(throwState.recoveringMask == ((1u << 2) | (1u << 4)));
    assert(state.movementEmoteTimers[2] == 44);
    assert(state.movementBehaviorClasses[1] == 2);
    assert(held_when_synced == OW_WILD_ACTOR_CONTROL_HELD);
    assert(throwState.targets[0]
        == OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(1));

    restoreMask = OverworldWildHelper_ClearPickupThrowState(
        &state, &throwState, &presentation, 0, TRUE);
    ReleaseMask(&state, restoreMask);
    assert(state.movementActorControlModes[1] == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(throwState.recoveringMask == ((1u << 2) | (1u << 4)));
    return 0;
}
'''


class PickedUpActorControlTests(unittest.TestCase):
    def run_host_driver(self, driver: str) -> None:
        helper = HELPER_SOURCE.read_text(encoding="utf-8")
        spawns = SPAWNS_SOURCE.read_text(encoding="utf-8")
        source = "\n".join(
            (
                PRELUDE,
                extract_function(
                    helper,
                    "OverworldWildHelper_ClearPickupThrowState",
                    "u16",
                ),
                extract_function(
                    helper,
                    "OverworldWildHelper_StartCarriedThrowTarget",
                    "BOOL",
                ),
                extract_function(
                    spawns,
                    "OverworldWildSpawns_ReleaseHeldActorControl",
                    "void",
                ),
                driver,
            )
        )
        with tempfile.TemporaryDirectory(prefix="held-actor-control-") as directory:
            source_path = Path(directory) / "held_actor_control.c"
            executable = Path(directory) / "held_actor_control"
            source_path.write_text(source, encoding="utf-8")
            compiled = subprocess.run(
                [
                    "cc",
                    "-std=c99",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    str(source_path),
                    "-o",
                    str(executable),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            completed = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_pickup_clear_and_release_keep_real_behavior_class(self) -> None:
        self.run_host_driver(DRIVER)

    def test_pickup_ends_only_cargo_recovery_and_failed_pickup_changes_nothing(self) -> None:
        self.run_host_driver(RECOVERY_DRIVER)

    def test_runtime_no_longer_uses_the_picked_up_class(self) -> None:
        product_sources = (
            HELPER_SOURCE,
            SPAWNS_SOURCE,
            RESOLVER_SOURCE,
        )
        for path in product_sources:
            self.assertNotIn(
                "OW_WILD_BEHAVIOR_CLASS_PICKED_UP",
                path.read_text(encoding="utf-8"),
                path.name,
            )
        resolver = RESOLVER_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("RESOLVER_BEHAVIOR_CLASS_PICKED_UP", resolver)

    def test_carried_throw_approaches_a_throw_line_independent_of_routine(self) -> None:
        spawns = SPAWNS_SOURCE.read_text(encoding="utf-8")
        movement = extract_function(
            spawns,
            "OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand",
            "BOOL",
        )
        carried = movement.index(
            "if ((throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) != 0)"
        )
        approach = movement.index("read.dx = read.playerX - read.objectX;", carried)
        self.assertIn("read.dy = read.playerY - read.objectY;", movement[approach:])
        random_target = movement.index(
            "if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY)",
            carried,
        )
        self.assertLess(approach, random_target)

    def test_control_state_is_internal_and_all_terminal_seams_clear_it(self) -> None:
        header = INTERNAL_HEADER.read_text(encoding="utf-8")
        helper = HELPER_SOURCE.read_text(encoding="utf-8")
        spawns = SPAWNS_SOURCE.read_text(encoding="utf-8")

        self.assertIn("OW_WILD_ACTOR_CONTROL_AUTONOMOUS", header)
        self.assertIn("OW_WILD_ACTOR_CONTROL_HELD", header)
        self.assertGreater(
            header.index("movementActorControlModes"),
            header.index("followerReleaseState"),
        )

        pickup = extract_function(
            helper, "OverworldWildHelper_StartCarriedThrowTarget", "BOOL"
        )
        self.assertLess(
            pickup.index("OW_WILD_ACTOR_CONTROL_HELD"),
            pickup.index("movementSpotStates"),
        )
        cleanup = extract_function(
            spawns, "OverworldWildSpawns_ClearThrowStateForSlot", "void"
        )
        self.assertIn("OverworldWildSpawns_ClearThrowRelations(state, slot, TRUE)", cleanup)
        relations = extract_function(spawns, "OverworldWildSpawns_ClearThrowRelations", "void")
        self.assertIn("OverworldWildSpawns_ReleaseHeldActorControl", relations)
        finished = extract_function(
            spawns, "OverworldWildSpawns_HandleFinishedMovementCommand", "void"
        )
        self.assertIn("OW_WILD_ACTOR_CONTROL_HELD", finished)
        self.assertIn("OverworldWildSpawns_ReleaseHeldActorControl", finished)
        reset = extract_function(
            spawns, "OverworldWildSpawns_ResetSlotState", "void"
        )
        initialize = extract_function(
            spawns, "OverworldWildSpawns_InitSpawnSlotState", "void"
        )
        rebind = extract_function(
            spawns, "OverworldWildSpawns_ApplyTransitionWork", "BOOL"
        )
        for body in (reset, initialize, rebind):
            self.assertIn("OW_WILD_ACTOR_CONTROL_AUTONOMOUS", body)


if __name__ == "__main__":
    unittest.main()
