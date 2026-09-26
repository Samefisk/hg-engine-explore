"""Queued ordinary spawns: compile the actual C bodies against a stub engine.

Run: python3 -m unittest tools.overworld.test_queued_spawn -v
"""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
GUARD_HEADER = ROOT / "include/overworld_spawn_guard.h"
GUARD_SOURCE = ROOT / "src/pokemon_move_history_overlay/overworld_spawn_guard.c"


def function(source, name, returns, exported=False):
    prefix = r"\b" + returns + r"\b" if exported else r"\bstatic\b"
    matches = list(re.finditer(prefix + r"[^;{}]*?\b" + name + r"\s*\([^;{}]*\)\s*\{", source))
    if len(matches) != 1:
        raise ValueError("expected one definition of " + name)
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            start = source.index(name, match.start(), match.end())
            return "static " + returns + " " + source[start:end + 1]
    raise ValueError("unterminated " + name)


def struct_typedef(source, name):
    matches = list(re.finditer(r"\btypedef\s+struct\s+" + name + r"\s*\{", source))
    if len(matches) != 1:
        raise ValueError("expected one typedef of " + name)
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            suffix = re.match(r"\s*" + name + r"\s*;", source[end + 1:])
            if suffix is None:
                raise ValueError("typedef name missing for " + name)
            return source[match.start():end + 1 + suffix.end()]
    raise ValueError("unterminated typedef " + name)


def function_pointer_typedef(source, name):
    matches = list(re.finditer(
        r"\btypedef\b[^;{}]*?\(\s*\*\s*" + name + r"\s*\)\s*\([^;{}]*\)\s*;",
        source))
    if len(matches) != 1:
        raise ValueError("expected one function typedef of " + name)
    return matches[0].group(0)


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int BOOL;
typedef int16_t s16;
typedef int32_t s32;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef u32 OverworldActorFieldContext;
typedef int OverworldWildSpawnTerrain;
typedef enum OverworldWildHelperPrepareResult {
    OW_WILD_HELPER_PREPARE_FAILED = 0,
    OW_WILD_HELPER_PREPARE_READY = 1,
    OW_WILD_HELPER_PREPARE_POSITION_PENDING = 2,
} OverworldWildHelperPrepareResult;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_MAX_SAVED_SHINIES 2
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
#define OW_WILD_SPAWN_STARTUP_PENDING 0xFE
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER (1u << 4)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT (1u << 5)

typedef struct { u16 spawnDestinationMask; } OverworldWildBehaviorProfile;
typedef struct { u8 value; } OverworldWildBehaviorPrimitives;
typedef struct {
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u8 behaviorClass, behaviorLimitKey;
} BehaviorResolveResult;
typedef struct { u32 personality; u16 species; u8 form, level; } OverworldWildRolledEncounter;
typedef struct { int startX, startY; u8 headbuttTreeType; } OverworldWildSpawnPosition;
typedef struct { s16 targetX, targetY, startX, startY; u8 locomotion, hopDirection; s32 targetBaseY; } OverworldWildSpawnStartup;
typedef struct {
    OverworldWildSpawnPosition position;
    OverworldWildRolledEncounter encounter;
    OverworldWildSpawnStartup startup;
    BehaviorResolveResult behaviorResolution;
    int savedShinySlot;
    u8 shiny, playerBallCatchValue;
} OverworldWildPreparedSpawn;
typedef struct { s32 height; u16 surfaceId; u8 surfaceType, nodeId; } OverworldWildSurfaceHit;
typedef struct { u16 mapId, speciesAndForm; u8 level, terrainAndActive; } OverworldWildSavedShiny;
typedef struct { u8 active; u16 encounterGeneration; } OverworldWildSpawn;
typedef struct {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    OverworldWildSavedShiny savedShinies[OW_WILD_MAX_SAVED_SHINIES];
    void *movementRuntimeState;
    u8 justSpawned;
} OverworldWildSpawnState;
typedef struct { u8 curFacing; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; } Avatar;
typedef struct { u16 mapId; } Location;
typedef struct {
    void *mapObjectMan;
    Location *location;
    Avatar *playerAvatar;
} FieldSystem;
'''


AFTER_GUARD = r'''
typedef struct {
    OverworldWildPreparedSpawn queuedSpawn;
    OverworldWildQueuedSpawnGuard queuedSpawnGuard;
    u8 queuedSpawnSlotPlusOne, queuedSpawnTerrain, refillPositionChecksRemaining;
} OverworldWildOverlayRuntimeState;
#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)((state)->movementRuntimeState))

typedef struct { OverworldActorFieldContext (*getContext)(void); } CompatEntry;
static OverworldActorFieldContext get_context(void);
static CompatEntry compat_entry = { get_context };
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compat_entry)

static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime_state;
static LocalMapObject player_object;
static Avatar avatar;
static Location location;
static FieldSystem field;
static int manager_a, manager_b;
static OverworldWildPreparedSpawn fixture, created;
static OverworldActorFieldContext context_value;
static int prepare_calls, create_calls, create_success;
static int player_x, player_y, occupied, near_spawn, behavior_limited;
static u8 target_behavior, origin_behavior;
static int surface_present;
static OverworldWildSurfaceHit surface_hit;
static int created_terrain, created_slot;

static OverworldActorFieldContext get_context(void) { return context_value; }
static int GetPlayerXCoord(Avatar *value) { (void)value; return player_x; }
static int GetPlayerYCoord(Avatar *value) { (void)value; return player_y; }
static u8 GetMetatileBehaviorAt(FieldSystem *value, int x, int y) {
    (void)value;
    if (x == fixture.startup.targetX && y == fixture.startup.targetY) return target_behavior;
    if (x == fixture.position.startX && y == fixture.position.startY) return origin_behavior;
    return 0xEE;
}
static BOOL OverworldWildSpawns_QuerySurface(
    FieldSystem *value, int x, int y, OverworldWildSurfaceHit *hit) {
    (void)value; (void)x; (void)y;
    if (surface_present) *hit = surface_hit;
    return surface_present;
}
static BOOL OverworldWildSpawns_IsPlayerTile(FieldSystem *value, int x, int y) {
    (void)value; return x == player_x && y == player_y;
}
static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *value, int x, int y) {
    (void)value; (void)x; (void)y; return occupied;
}
static BOOL OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(
    FieldSystem *value, void *object, int x, int y) {
    (void)value; (void)object; (void)x; (void)y; return occupied;
}
static BOOL OverworldWildSpawns_IsNearActiveSpawn(
    OverworldWildSpawnState *value, int x, int y, int distance) {
    (void)value; (void)x; (void)y; (void)distance; return near_spawn;
}
static BOOL OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit(
    OverworldWildSpawnState *value, u8 key, const OverworldWildBehaviorProfile *profile) {
    (void)value; (void)key; (void)profile; return behavior_limited;
}
static OverworldWildHelperPrepareResult OverworldWildSpawns_TryPrepareSpawnWithHelper(
    OverworldWildSpawnState *value, FieldSystem *system, OverworldWildSpawnTerrain terrain,
    int slot, OverworldWildPreparedSpawn *prepared) {
    (void)value; (void)system; (void)terrain; (void)slot;
    prepare_calls++;
    fixture.encounter.personality = 0x12340000u + (u32)prepare_calls;
    *prepared = fixture;
    return OW_WILD_HELPER_PREPARE_READY;
}
static BOOL OverworldWildSpawns_FinalizePreparedSpawn(
    OverworldWildSpawnState *value, FieldSystem *system, OverworldWildSpawnTerrain terrain,
    int slot, OverworldWildPreparedSpawn *prepared) {
    (void)value; (void)system; (void)terrain; (void)slot; (void)prepared;
    return TRUE;
}
static BOOL OverworldWildSpawns_SpawnPreparedEncounter(
    OverworldWildSpawnState *value, FieldSystem *system, OverworldWildSpawnTerrain terrain,
    int slot, const OverworldWildPreparedSpawn *prepared) {
    (void)system;
    create_calls++;
    created = *prepared;
    created_terrain = terrain;
    created_slot = slot;
    if (!create_success) return FALSE;
    value->spawns[slot].active = TRUE;
    if (prepared->savedShinySlot >= 0)
        memset(&value->savedShinies[prepared->savedShinySlot], 0,
               sizeof(value->savedShinies[prepared->savedShinySlot]));
    return TRUE;
}

static void reset_fixture(void) {
    memset(&state, 0, sizeof(state));
    memset(&runtime_state, 0, sizeof(runtime_state));
    memset(&fixture, 0, sizeof(fixture));
    memset(&created, 0, sizeof(created));
    player_object.curFacing = 3;
    avatar.mapObject = &player_object;
    location.mapId = 67;
    field.mapObjectMan = &manager_a;
    field.location = &location;
    field.playerAvatar = &avatar;
    state.movementRuntimeState = &runtime_state;
    state.spawns[2].encounterGeneration = 91;
    state.savedShinies[0] = (OverworldWildSavedShiny){67, 155, 12, 0x81};
    state.savedShinies[1] = (OverworldWildSavedShiny){68, 288, 30, 0x82};
    fixture.position.startX = 20;
    fixture.position.startY = 21;
    fixture.startup.targetX = 30;
    fixture.startup.targetY = 31;
    fixture.encounter.species = 155;
    fixture.encounter.form = 2;
    fixture.encounter.level = 12;
    fixture.savedShinySlot = -1;
    fixture.shiny = TRUE;
    fixture.behaviorResolution.behaviorLimitKey = 9;
    context_value = 0x00120034u;
    player_x = 10;
    player_y = 11;
    target_behavior = 44;
    origin_behavior = 45;
    surface_present = TRUE;
    surface_hit = (OverworldWildSurfaceHit){64, 7, 2, 3};
    prepare_calls = create_calls = occupied = near_spawn = behavior_limited = 0;
    create_success = TRUE;
    created_terrain = created_slot = -1;
}
'''


DRIVER = r'''
static void happy(void) {
    reset_fixture();
    int queued = OverworldWildSpawns_SpawnOne(&state, &field, 1, 2);
    int defer_prepare = prepare_calls, defer_create = create_calls;
    int queued_slot = runtime_state.queuedSpawnSlotPlusOne;
    u32 queued_personality = runtime_state.queuedSpawn.encounter.personality;
    u16 queued_species = runtime_state.queuedSpawn.encounter.species;
    int queued_target_x = runtime_state.queuedSpawn.startup.targetX;
    int queued_target_y = runtime_state.queuedSpawn.startup.targetY;
    OverworldWildSpawns_CommitQueuedSpawn(&state, &field);
    int commit_create = create_calls, after_commit_queue = runtime_state.queuedSpawnSlotPlusOne;
    OverworldWildSpawns_CommitQueuedSpawn(&state, &field);
    printf("{\"queued\":%d,\"deferPrepare\":%d,\"deferCreate\":%d,"
           "\"queuedSlot\":%d,\"commitCreate\":%d,\"afterCommitQueue\":%d,"
           "\"duplicateCreate\":%d,\"prepareCalls\":%d,\"justSpawned\":%d,"
           "\"queuedPersonality\":%u,\"queuedSpecies\":%u,\"species\":%u,"
           "\"personality\":%u,\"queuedTarget\":[%d,%d],\"target\":[%d,%d],"
           "\"terrain\":%d,\"slot\":%d}\n",
        queued, defer_prepare, defer_create, queued_slot, commit_create, after_commit_queue,
        create_calls, prepare_calls, state.justSpawned, queued_personality,
        queued_species, created.encounter.species, created.encounter.personality,
        queued_target_x, queued_target_y,
        created.startup.targetX, created.startup.targetY, created_terrain, created_slot);
}

static void cancel(const char *kind) {
    reset_fixture();
    if (!strcmp(kind, "saved-shiny")) fixture.savedShinySlot = 0;
    int queued = OverworldWildSpawns_SpawnOne(&state, &field, 1, 2);
    if (!strcmp(kind, "context")) context_value++;
    else if (!strcmp(kind, "map")) location.mapId++;
    else if (!strcmp(kind, "manager")) field.mapObjectMan = &manager_b;
    else if (!strcmp(kind, "generation")) state.spawns[2].encounterGeneration++;
    else if (!strcmp(kind, "occupied")) occupied = TRUE;
    else if (!strcmp(kind, "surface")) surface_hit.surfaceId++;
    else if (!strcmp(kind, "target-behavior")) target_behavior++;
    else if (!strcmp(kind, "origin-behavior")) origin_behavior++;
    else if (!strcmp(kind, "saved-shiny")) state.savedShinies[0].speciesAndForm++;
    else exit(3);
    OverworldWildSpawns_CommitQueuedSpawn(&state, &field);
    printf("{\"queued\":%d,\"prepareCalls\":%d,\"createCalls\":%d,"
           "\"queueAfter\":%d,\"justSpawned\":%d}\n",
        queued, prepare_calls, create_calls, runtime_state.queuedSpawnSlotPlusOne,
        state.justSpawned);
}

static void failed_create(void) {
    OverworldWildSavedShiny before0, before1;
    reset_fixture();
    fixture.savedShinySlot = 0;
    before0 = state.savedShinies[0];
    before1 = state.savedShinies[1];
    create_success = FALSE;
    int queued = OverworldWildSpawns_SpawnOne(&state, &field, 1, 2);
    u32 queued_personality = runtime_state.queuedSpawn.encounter.personality;
    OverworldWildSpawns_CommitQueuedSpawn(&state, &field);
    OverworldWildSpawns_CommitQueuedSpawn(&state, &field);
    printf("{\"queued\":%d,\"prepareCalls\":%d,\"createCalls\":%d,"
           "\"queueAfter\":%d,\"justSpawned\":%d,\"saved0Same\":%d,"
           "\"saved1Same\":%d,\"queuedPersonality\":%u,\"createdPersonality\":%u}\n",
        queued, prepare_calls, create_calls, runtime_state.queuedSpawnSlotPlusOne,
        state.justSpawned, !memcmp(&before0, &state.savedShinies[0], sizeof(before0)),
        !memcmp(&before1, &state.savedShinies[1], sizeof(before1)),
        queued_personality, created.encounter.personality);
}

static void startup_pending(void) {
    reset_fixture();
    int queued = OverworldWildSpawns_SpawnOne(&state, &field, 1, 2);
    runtime_state.refillPositionChecksRemaining =
        OW_WILD_SPAWN_STARTUP_PENDING;
    OverworldWildSpawns_CommitQueuedSpawn(&state, &field);
    printf("{\"queued\":%d,\"createCalls\":%d,\"queueAfter\":%d,"
           "\"startupAfter\":%d}\n",
        queued, create_calls, runtime_state.queuedSpawnSlotPlusOne,
        runtime_state.refillPositionChecksRemaining);
}

static void queue_rejection(void) {
    reset_fixture();
    int first = OverworldWildSpawns_SpawnOne(&state, &field, 3, 2);
    int pending = OverworldWildSpawns_SpawnOne(&state, &field, 3, 2);
    int pending_prepare = prepare_calls, pending_create = create_calls;
    int pending_queue = runtime_state.queuedSpawnSlotPlusOne;
    reset_fixture();
    target_behavior = 0xFF;
    int invalid = OverworldWildSpawns_SpawnOne(&state, &field, 3, 2);
    int invalid_prepare = prepare_calls, invalid_create = create_calls;
    int invalid_queue = runtime_state.queuedSpawnSlotPlusOne;
    target_behavior = 44;
    int retry = OverworldWildSpawns_SpawnOne(&state, &field, 3, 2);
    printf("{\"first\":%d,\"pending\":%d,\"pendingPrepare\":%d,"
           "\"pendingCreate\":%d,\"pendingQueue\":%d,\"invalid\":%d,"
           "\"invalidPrepare\":%d,\"invalidCreate\":%d,\"invalidQueue\":%d,"
           "\"retry\":%d,\"retryPrepare\":%d,\"retryCreate\":%d,\"retryQueue\":%d}\n",
        first, pending, pending_prepare, pending_create, pending_queue,
        invalid, invalid_prepare, invalid_create, invalid_queue,
        retry, prepare_calls, create_calls, runtime_state.queuedSpawnSlotPlusOne);
}

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    if (!strcmp(argv[1], "happy")) happy();
    else if (!strcmp(argv[1], "cancel") && argc == 3) cancel(argv[2]);
    else if (!strcmp(argv[1], "failed-create")) failed_create();
    else if (!strcmp(argv[1], "startup-pending")) startup_pending();
    else if (!strcmp(argv[1], "queue-rejection")) queue_rejection();
    else return 2;
    return 0;
}
'''


class QueuedSpawnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="queued-spawn-")
        cls.addClassCleanup(cls.directory.cleanup)
        source = SOURCE.read_text()
        guard_source = GUARD_SOURCE.read_text()
        guard_header = GUARD_HEADER.read_text()
        guard = struct_typedef(guard_header, "OverworldWildQueuedSpawnGuard")
        surface_query = function_pointer_typedef(
            guard_header, "OverworldWildSpawnGuardSurfaceQueryFunc")
        bodies = "\n".join((
            function(guard_source, "OverworldWildSpawnGuard_Read", "BOOL", exported=True),
            function(source, "OverworldWildSpawns_CommitQueuedSpawn", "void"),
            function(
                source,
                "OverworldWildSpawns_SpawnOne",
                "OverworldWildHelperPrepareResult",
            ),
        ))
        unit = Path(cls.directory.name) / "queued_spawn.c"
        cls.binary = Path(cls.directory.name) / "queued_spawn"
        unit.write_text(PRELUDE + guard + surface_query + AFTER_GUARD + bodies + DRIVER)
        result = subprocess.run(
            [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2", "-Wall", "-Wextra",
             "-Werror", "-Wno-unused-function", str(unit), "-o", str(cls.binary)],
            text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr)

    def run_case(self, *args):
        return json.loads(subprocess.check_output([str(self.binary), *args], text=True))

    def test_defer_prepares_once_then_commit_creates_exact_value_once(self):
        result = self.run_case("happy")
        self.assertEqual(result["queued"], 1)
        self.assertEqual((result["deferPrepare"], result["deferCreate"]), (1, 0))
        self.assertEqual(result["queuedSlot"], 3)
        self.assertEqual((result["commitCreate"], result["duplicateCreate"]), (1, 1))
        self.assertEqual((result["afterCommitQueue"], result["prepareCalls"]), (0, 1))
        self.assertEqual(result["justSpawned"], 1)
        self.assertEqual(result["personality"], result["queuedPersonality"])
        self.assertEqual(result["species"], result["queuedSpecies"])
        self.assertEqual(result["species"], 155)
        self.assertEqual(result["target"], result["queuedTarget"])
        self.assertEqual(result["target"], [30, 31])
        self.assertEqual((result["terrain"], result["slot"]), (1, 2))

    def test_stale_or_occupied_queue_is_consumed_without_creation(self):
        for change in ("context", "map", "manager", "generation", "occupied",
                       "surface", "target-behavior", "origin-behavior", "saved-shiny"):
            with self.subTest(change=change):
                result = self.run_case("cancel", change)
                self.assertEqual(result, {"queued": 1, "prepareCalls": 1,
                    "createCalls": 0, "queueAfter": 0, "justSpawned": 0})

    def test_failed_create_is_not_retried_rerolled_or_allowed_to_clear_saved_shiny(self):
        result = self.run_case("failed-create")
        self.assertEqual(result["queued"], 1)
        self.assertEqual((result["prepareCalls"], result["createCalls"]), (1, 1))
        self.assertEqual((result["queueAfter"], result["justSpawned"]), (0, 0))
        self.assertEqual((result["saved0Same"], result["saved1Same"]), (1, 1))
        self.assertEqual(result["createdPersonality"], result["queuedPersonality"])

    def test_commit_releases_completed_startup_work(self):
        result = self.run_case("startup-pending")
        self.assertEqual(result, {
            "queued": 1,
            "createCalls": 1,
            "queueAfter": 0,
            "startupAfter": 0,
        })

    def test_pending_and_invalid_guard_reject_without_blocking_next_valid_queue(self):
        result = self.run_case("queue-rejection")
        self.assertEqual((result["first"], result["pending"]), (1, 0))
        self.assertEqual((result["pendingPrepare"], result["pendingCreate"], result["pendingQueue"]),
                         (1, 0, 3))
        self.assertEqual(result["invalid"], 0)
        self.assertEqual((result["invalidPrepare"], result["invalidCreate"], result["invalidQueue"]),
                         (1, 0, 0))
        self.assertEqual(result["retry"], 1)
        self.assertEqual((result["retryPrepare"], result["retryCreate"], result["retryQueue"]),
                         (2, 0, 3))


if __name__ == "__main__":
    unittest.main()
