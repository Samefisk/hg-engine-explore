"""Host regression checks for deferred distance despawn.

The C rules under test are extracted from the shipped translation units. Run:

    python3 -m unittest tools.overworld.test_distance_despawn -v
"""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
SPAWNS_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


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
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef int BOOL;
typedef int16_t s16;
typedef uint8_t u8;
typedef uint16_t u16;

#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_DISTANCE_DESPAWN_TILES 16
#define OW_WILD_DISTANCE_DESPAWN_SAMPLES 2
#define OW_WILD_SPAWN_ENTRY_NONE 0
#define OW_WILD_SPAWN_ENTRY_MOVE 1
#define OW_WILD_SPAWN_ENTRY_HOP 2
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) ((u16)(1u << (slot)))

typedef struct LocalMapObject {
    int x;
    int y;
} LocalMapObject;

typedef struct PlayerAvatar {
    int x;
    int y;
} PlayerAvatar;

typedef struct FieldSystem {
    PlayerAvatar *playerAvatar;
} FieldSystem;

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u16 encounterGeneration;
    u8 active;
    u8 shiny;
} OverworldWildSpawn;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    u8 movementSpawnRunActive[OW_WILD_MAX_SPAWNS];
    void *movementRuntimeState;
} OverworldWildSpawnState;

typedef struct OverworldWildPresentationState {
    s16 lastKnownX[OW_WILD_MAX_SPAWNS];
    s16 lastKnownY[OW_WILD_MAX_SPAWNS];
    u8 farSamples[OW_WILD_MAX_SPAWNS];
    u16 managerRestoreMask;
    u16 distanceDespawnPendingMask;
} OverworldWildPresentationState;

typedef struct OverworldWildDespawnTelemetry { int unused; } OverworldWildDespawnTelemetry;
typedef void (*OverworldWildHelperResetSlotFunc)(OverworldWildSpawnState *, int, BOOL);

#define OW_WILD_DESPAWN_REASON_DISTANCE 3

static BOOL host_exact_object = TRUE;

static BOOL OverworldWildHelper_IsExactObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    (void)fieldSystem;
    return host_exact_object && state->spawns[slot].object != NULL;
}

static int MapObject_GetCurrentX(LocalMapObject *object) { return object->x; }
static int MapObject_GetCurrentY(LocalMapObject *object) { return object->y; }
static int GetPlayerXCoord(PlayerAvatar *avatar) { return avatar->x; }
static int GetPlayerYCoord(PlayerAvatar *avatar) { return avatar->y; }

static int host_remove_count;
static BOOL OverworldWildHelper_RemoveEncounter(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    int reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot)
{
    (void)fieldSystem;
    (void)state;
    (void)presentation;
    (void)telemetry;
    (void)slot;
    (void)expectedGeneration;
    (void)reason;
    (void)distance;
    (void)resetSlot;
    host_remove_count++;
    return TRUE;
}
'''


DRIVER = r'''
#define CHECK(condition, message) do { \
    if (!(condition)) { fprintf(stderr, "%s\n", message); return 1; } \
} while (0)

int main(void)
{
    FieldSystem field;
    PlayerAvatar player;
    LocalMapObject object;
    OverworldWildSpawnState state;
    OverworldWildPresentationState presentation;
    OverworldWildDespawnTelemetry telemetry;
    u8 distance = 0;

    memset(&state, 0, sizeof(state));
    memset(&presentation, 0, sizeof(presentation));
    memset(&telemetry, 0, sizeof(telemetry));
    player.x = 0;
    player.y = 0;
    object.x = 17;
    object.y = 0;
    field.playerAvatar = &player;
    state.spawns[0].active = TRUE;
    state.spawns[0].object = &object;
    state.spawns[0].encounterGeneration = 1;

    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, TRUE, &distance),
        "first moving far sample must defer removal");
    CHECK(presentation.farSamples[0] == 1 && distance == 17,
        "first moving far sample must be retained");
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, TRUE, &distance),
        "second moving far sample must still defer removal");
    CHECK(presentation.farSamples[0] == 2
            && presentation.distanceDespawnPendingMask == 1,
        "moving actor must reach confirmed-far state");

    CHECK(OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, FALSE, &distance),
        "terminal actor must consume retained far samples");

    object.x = 16;
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, FALSE, &distance),
        "exactly sixteen tiles must not despawn");
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0,
        "returning in range must cancel pending removal");

    object.x = 17;
    presentation.farSamples[0] = 2;
    presentation.distanceDespawnPendingMask = 1;
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, TRUE, FALSE, &distance),
        "hard protection must suppress removal");
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0,
        "hard protection must clear stale far samples");

    presentation.farSamples[0] = 1;
    presentation.distanceDespawnPendingMask = 1;
    state.movementSpawnRunActive[0] = OW_WILD_SPAWN_ENTRY_MOVE;
    OverworldWildHelper_DespawnFarEncounters(
        &field, &state, &presentation, &telemetry, 0, 0, NULL);
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0
            && host_remove_count == 0,
        "Move From Off Screen must stay hard protected");
    presentation.farSamples[0] = 1;
    presentation.distanceDespawnPendingMask = 1;
    state.movementSpawnRunActive[0] = OW_WILD_SPAWN_ENTRY_HOP;
    OverworldWildHelper_DespawnFarEncounters(
        &field, &state, &presentation, &telemetry, 0, 0, NULL);
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0
            && host_remove_count == 0,
        "Hop From Off Screen must stay hard protected");
    state.movementSpawnRunActive[0] = OW_WILD_SPAWN_ENTRY_NONE;

    host_exact_object = FALSE;
    presentation.farSamples[0] = 2;
    presentation.distanceDespawnPendingMask = 1;
    CHECK(!OverworldWildHelper_ConfirmDistanceDespawn(
        &field, &state, &presentation, 0, FALSE, FALSE, &distance),
        "identity mismatch must suppress distance removal");
    CHECK(presentation.farSamples[0] == 0
            && presentation.distanceDespawnPendingMask == 0,
        "identity mismatch must clear stale far samples");
    return 0;
}
'''


class DistanceDespawnRegression(unittest.TestCase):
    def test_moving_samples_defer_and_offscreen_entry_is_hard_protected(self):
        helper = HELPER_SOURCE.read_text()
        source = (
            PRELUDE
            + extract_function(
                helper, "OverworldWildHelper_ConfirmDistanceDespawn", "BOOL"
            )
            + "\n"
            + extract_function(
                helper, "OverworldWildHelper_DespawnFarEncounters", "void"
            )
            + DRIVER
        )
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "distance_despawn.c"
            executable = Path(directory) / "distance_despawn"
            source_path.write_text(source)
            compiled = subprocess.run(
                ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source_path), "-o", str(executable)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            ran = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_terminal_boundary_blocks_follow_on_movement(self):
        source = SPAWNS_SOURCE.read_text()
        walk = extract_function(
            source,
            "OverworldWildSpawns_HandleFinishedWalkMovement",
            "BOOL",
        )
        terminal = extract_function(
            source,
            "OverworldWildSpawns_HandleFinishedMovementCommand",
            "void",
        )
        self.assertLess(
            walk.index("stopAfterCommit"),
            walk.index("OverworldWildSpawns_ExecuteWalkPolicy"),
        )
        self.assertIn("distanceDespawnPendingMask", terminal)
        self.assertIn(
            "OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE", terminal
        )
        first_terminal_gate = terminal.index("pendingDistanceDespawn")
        self.assertLess(
            first_terminal_gate,
            terminal.index("OverworldWildSpawns_RunChainReposition"),
        )
        self.assertLess(
            terminal.index("pendingDistanceDespawn", first_terminal_gate + 1),
            terminal.index("OverworldWildSpawns_ApplyUniversalChainMovementPause"),
        )

    def test_pending_slot_cannot_restart_in_same_frame(self):
        source = SPAWNS_SOURCE.read_text()
        tick = extract_function(
            source,
            "OverworldWildSpawns_TickMovementParams",
            "void",
        )
        pending_guard = tick.index("distanceDespawnPendingMask")
        first_ai_action = tick.index("OverworldWildSpawns_EnterAggroState")
        self.assertLess(pending_guard, first_ai_action)
        self.assertIn("continue;", tick[pending_guard:first_ai_action])


if __name__ == "__main__":
    unittest.main()
