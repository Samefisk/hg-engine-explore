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

#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 9
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
static OverworldWildHelperOverlayEntry helper_entry;

static BOOL OverworldWildHelper_IsPickupThrowMovementContextCurrent(
    OverworldWildSpawnState *state)
{
    return state != 0;
}

static BOOL OverworldWildHelper_IsExactObject(
    void *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    (void)fieldSystem;
    return state != 0 && state->spawns[slot].object != 0;
}

static void MapObject_SetBits(LocalMapObject *object, uint32_t bits)
{
    object->flags |= bits;
}

static void MapObject_ClearBits(LocalMapObject *object, uint32_t bits)
{
    object->flags &= ~bits;
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


DRIVER = r'''
static void ReleaseMask(OverworldWildSpawnState *state, u16 mask)
{
    int slot;

    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        if ((mask & (1u << slot)) != 0) {
            OverworldWildSpawns_ReleaseHeldActorControl(state, slot);
        }
    }
}

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
        &state, &throwState, &presentation, 0);
    assert(restoreMask == (1u << 1));
    ReleaseMask(&state, restoreMask);
    assert(state.movementActorControlModes[1]
        == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(state.movementBehaviorClasses[1] == 2);
    assert(mode_when_walk_cleared == OW_WILD_ACTOR_CONTROL_AUTONOMOUS);
    assert(clear_walk_count == 1 && normalize_count == 1 && shadow_count == 1);

    /* Target cleanup, used by drop/despawn paths, releases the same state. */
    assert(OverworldWildHelper_StartCarriedThrowTarget(
        &state, &throwState, &presentation, 0, 1));
    restoreMask = OverworldWildHelper_ClearPickupThrowState(
        &state, &throwState, &presentation, 1);
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


class PickedUpActorControlTests(unittest.TestCase):
    def test_pickup_clear_and_release_keep_real_behavior_class(self) -> None:
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
                DRIVER,
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
            "if (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG)"
        )
        approach = movement.index(
            "movementTarget = OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE;",
            carried,
        )
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
        self.assertIn("OverworldWildSpawns_ReleaseHeldActorControl", cleanup)
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
