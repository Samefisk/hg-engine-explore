"""Host contract checks for the bounded ordinary-spawn refill work.

The test extracts the production ``TryRefill`` definition and supplies small
host stubs for the actor population service, follower path, free-slot scan,
and ``SpawnOne``.  It checks the refill state machine without building a ROM
or starting an emulator.
"""

from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    from tools.overworld.test_spawn_spatial import extract_function
except ModuleNotFoundError:
    # The feature manifest runs this file directly. Keep module execution useful
    # for local unittest calls without making the checked command depend on
    # PYTHONPATH.
    from test_spawn_spatial import extract_function


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"


PRELUDE = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define TRUE 1
#define FALSE 0
#define SPECIES_BULBASAUR 1
#define OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_CHECKS 16
#define OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES 1
#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
#define OW_WILD_SPAWN_STARTUP_PENDING 0xFE

typedef enum OverworldWildHelperPrepareResult {
    OW_WILD_HELPER_PREPARE_FAILED = 0,
    OW_WILD_HELPER_PREPARE_READY = 1,
    OW_WILD_HELPER_PREPARE_POSITION_PENDING = 2,
} OverworldWildHelperPrepareResult;

static struct { u8 spawnWarmupPhase; } sOverworldWildFlags;
static int metadataWarmCalls, behaviorWarmCalls;
static BOOL helperAvailable;
static void *OverworldWildSpawns_GetHelperOverlayEntry(void)
{
    return helperAvailable ? &sOverworldWildFlags : 0;
}
static u32 OverworldWildSpawns_GetSpriteID(int species, int form)
{
    assert(species == SPECIES_BULBASAUR && form == 0);
    metadataWarmCalls++;
    return 0; /* A failed loader is still one bounded, latched attempt. */
}
static void *OverworldWildSpawns_GetBehaviorDataBlob(void)
{
    behaviorWarmCalls++;
    return 0;
}

#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_LAND_SURF_MAX_SPAWNS 6
#define OW_WILD_HEADBUTT_MAX_SPAWNS 2
#define OW_WILD_FISH_MAX_SPAWNS 2
#define OW_WILD_HEADBUTT_SLOT_START OW_WILD_LAND_SURF_MAX_SPAWNS
#define OW_WILD_FISH_SLOT_START (OW_WILD_HEADBUTT_SLOT_START + OW_WILD_HEADBUTT_MAX_SPAWNS)
#define OW_WILD_FOLLOWER_SLOT (OW_WILD_FISH_SLOT_START - 1)

#define OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT 10
#define OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN 10
#define OW_WILD_FISHING_SPAWN_CHANCE_PERCENT 20
#define OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN 4
#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 60

#define OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING (1u << 0)

enum {
    OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL = 1,
    OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE,
};

enum {
    OVERWORLD_ACTOR_POPULATION_WORK_NONE = 0,
    OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN,
    OVERWORLD_ACTOR_POPULATION_WORK_REFILL,
};

typedef enum OverworldWildSpawnTerrain {
    OW_WILD_SPAWN_TERRAIN_LAND = 1,
    OW_WILD_SPAWN_TERRAIN_SURF = 2,
    OW_WILD_SPAWN_TERRAIN_HEADBUTT = 3,
    OW_WILD_SPAWN_TERRAIN_FISHING = 4,
} OverworldWildSpawnTerrain;

typedef struct OverworldWildSpawn {
    BOOL active;
} OverworldWildSpawn;

typedef struct OverworldWildResidentData {
    u32 pendingFlags;
} OverworldWildResidentData;

typedef struct OverworldWildOverlayRuntimeState {
    OverworldWildResidentData *residentData;
    u8 queuedSpawnSlotPlusOne;
    u8 queuedSpawnTerrain;
    u8 refillTerrainMask;
    u8 refillLandSurfSlot;
    u8 refillPositionChecksRemaining;
} OverworldWildOverlayRuntimeState;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    void *movementRuntimeState;
    int headbuttSpawnCooldown;
    int fishingSpawnCooldown;
    BOOL justSpawned;
} OverworldWildSpawnState;

typedef struct FieldSystem {
    int unused;
} FieldSystem;

#define OW_WILD_RUNTIME(state) \
    ((OverworldWildOverlayRuntimeState *)((state)->movementRuntimeState))

typedef struct PopulationEntry {
    int (*control)(int operation, int argument);
} PopulationEntry;

static PopulationEntry populationEntry;
#define OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY (&populationEntry)

static int scheduleArguments[32];
static int scheduleCount;
static int advanceCalls, nextMaintenanceWork;
static int scheduleControl(int operation, int argument)
{
    if (operation == OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE) {
        assert(argument == 0);
        advanceCalls++;
        return nextMaintenanceWork;
    }
    assert(operation == OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL);
    assert(scheduleCount < (int)(sizeof(scheduleArguments) / sizeof(scheduleArguments[0])));
    scheduleArguments[scheduleCount++] = argument;
    return OVERWORLD_ACTOR_POPULATION_WORK_NONE;
}

static u32 randomValues[32];
static int randomCount;
static int randomIndex;
static u32 gf_rand(void)
{
    assert(randomIndex < randomCount);
    return randomValues[randomIndex++];
}

static BOOL reconcileResult;
static int reconcileCalls;
static BOOL OverworldWildSpawns_ReconcileFollowerSelection(
    OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    (void)state;
    (void)fieldSystem;
    reconcileCalls++;
    return reconcileResult;
}

static BOOL followerSpawnResult;
static BOOL followerCandidateResult;
static int followerSpawnCalls;
static BOOL OverworldWildSpawns_TrySpawnFollower(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    BOOL *hasCandidate)
{
    (void)state;
    (void)fieldSystem;
    followerSpawnCalls++;
    if (hasCandidate != NULL) {
        *hasCandidate = followerCandidateResult;
    }
    return followerSpawnResult;
}

static BOOL enabledMap;
static void OverworldWildSpawns_CommitQueuedSpawn(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    (void)state;
    (void)fieldSystem;
    assert(0 && "no queued creation is expected in the warmup dispatch check");
}
static BOOL OverworldWildSpawns_IsEnabledMap(FieldSystem *fieldSystem)
{
    (void)fieldSystem;
    return enabledMap;
}

static int freeSlotCalls;
static int freeSlotStarts[32];
static int freeSlotEnds[32];
static BOOL OverworldWildSpawns_TryGetFreeSlot(
    OverworldWildSpawnState *state,
    u8 start,
    u8 end,
    int *slot)
{
    int i;
    assert(freeSlotCalls < (int)(sizeof(freeSlotStarts) / sizeof(freeSlotStarts[0])));
    freeSlotStarts[freeSlotCalls] = start;
    freeSlotEnds[freeSlotCalls] = end;
    freeSlotCalls++;
    for (i = start; i < end; i++) {
        if (i != OW_WILD_FOLLOWER_SLOT
            && !state->spawns[i].active
            && (OW_WILD_RUNTIME(state)->queuedSpawnSlotPlusOne != i + 1)) {
            *slot = i;
            return TRUE;
        }
    }
    return FALSE;
}

static int spawnCalls;
static int spawnTerrains[32];
static int spawnSlots[32];
static OverworldWildHelperPrepareResult spawnResults[32];
static int configuredSpawnResults;
static OverworldWildHelperPrepareResult OverworldWildSpawns_SpawnOne(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot)
{
    OverworldWildHelperPrepareResult result;
    (void)fieldSystem;
    assert(spawnCalls < configuredSpawnResults);
    spawnTerrains[spawnCalls] = terrain;
    spawnSlots[spawnCalls] = slot;
    result = spawnResults[spawnCalls++];
    if (result == OW_WILD_HELPER_PREPARE_READY) {
        /* Ordinary SpawnOne prepares a queued candidate, not an object. */
        OW_WILD_RUNTIME(state)->queuedSpawnSlotPlusOne = (u8)(slot + 1);
    }
    return result;
}

static void resetFixture(
    OverworldWildSpawnState *state,
    OverworldWildOverlayRuntimeState *runtime,
    OverworldWildResidentData *resident,
    FieldSystem *fieldSystem)
{
    memset(state, 0, sizeof(*state));
    memset(runtime, 0, sizeof(*runtime));
    memset(resident, 0, sizeof(*resident));
    runtime->residentData = resident;
    state->movementRuntimeState = runtime;
    state->headbuttSpawnCooldown = 1;
    state->fishingSpawnCooldown = 1;
    reconcileResult = TRUE;
    followerSpawnResult = FALSE;
    followerCandidateResult = FALSE;
    followerSpawnCalls = 0;
    sOverworldWildFlags.spawnWarmupPhase = 2;
    helperAvailable = TRUE;
    metadataWarmCalls = behaviorWarmCalls = 0;
    enabledMap = TRUE;
    scheduleCount = 0;
    advanceCalls = 0;
    nextMaintenanceWork = OVERWORLD_ACTOR_POPULATION_WORK_NONE;
    freeSlotCalls = 0;
    spawnCalls = 0;
    configuredSpawnResults = 0;
    randomCount = 0;
    randomIndex = 0;
    populationEntry.control = scheduleControl;
    (void)fieldSystem;
}

static void setRandomValues(u32 first, u32 second)
{
    randomValues[0] = first;
    randomValues[1] = second;
    randomCount = 2;
    randomIndex = 0;
}

static void setSpawnResults(const BOOL *results, int count)
{
    int i;
    configuredSpawnResults = count;
    for (i = 0; i < count; i++) {
        spawnResults[i] = results[i];
    }
}

static void setPrepareResults(
    const OverworldWildHelperPrepareResult *results,
    int count)
{
    int i;
    configuredSpawnResults = count;
    for (i = 0; i < count; i++) {
        spawnResults[i] = results[i];
    }
}
'''


DRIVER = r'''
static void test_position_search_uses_one_sixteen_check_batch_per_terrain(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    OverworldWildHelperPrepareResult results[2];
    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    runtime.refillTerrainMask = 4 | 8;
    results[0] = OW_WILD_HELPER_PREPARE_POSITION_PENDING;
    results[1] = OW_WILD_HELPER_PREPARE_READY;
    setPrepareResults(results, 2);

    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(spawnCalls == 1);
    assert(spawnTerrains[0] == OW_WILD_SPAWN_TERRAIN_LAND);
    assert(spawnSlots[0] == 0);
    assert(runtime.refillTerrainMask == 8);
    assert(runtime.refillPositionChecksRemaining == 0);

    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(spawnCalls == 2);
    assert(spawnTerrains[1] == OW_WILD_SPAWN_TERRAIN_SURF);
    assert(spawnSlots[1] == 0);
    assert(runtime.refillTerrainMask == 0);
    assert(runtime.queuedSpawnSlotPlusOne == 1);
}

static void test_one_attempt_and_priority(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL failures[] = { FALSE, FALSE, FALSE, FALSE };

    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    state.headbuttSpawnCooldown = 0;
    state.fishingSpawnCooldown = 0;
    setRandomValues(0, 0); /* Both optional gates pass once. */
    setSpawnResults(failures, 4);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 1);
    assert(spawnTerrains[0] == OW_WILD_SPAWN_TERRAIN_HEADBUTT);
    assert(spawnSlots[0] == OW_WILD_HEADBUTT_SLOT_START);
    assert(runtime.refillTerrainMask == (2 | 4 | 8));
    assert(state.headbuttSpawnCooldown == OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN);
    assert(state.fishingSpawnCooldown == OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN);
    assert(scheduleCount == 1); /* No second base timer while the series is pending. */
    assert(randomIndex == 2);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 2);
    assert(spawnTerrains[1] == OW_WILD_SPAWN_TERRAIN_FISHING);
    assert(spawnSlots[1] == OW_WILD_FISH_SLOT_START);
    assert(runtime.refillTerrainMask == (4 | 8));
    assert(state.headbuttSpawnCooldown == OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN);
    assert(state.fishingSpawnCooldown == OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN);
    assert(scheduleCount == 1);
    assert(randomIndex == 2);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 3);
    assert(spawnTerrains[2] == OW_WILD_SPAWN_TERRAIN_LAND);
    assert(spawnSlots[2] == 0);
    assert(runtime.refillTerrainMask == 8);
    assert(runtime.refillLandSurfSlot == 0);
    assert(randomIndex == 2);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 4);
    assert(spawnTerrains[3] == OW_WILD_SPAWN_TERRAIN_SURF);
    assert(spawnSlots[3] == 0);
    assert(runtime.refillTerrainMask == 0);
    assert(randomIndex == 2);
}

static void test_first_success_cancels_remaining_and_counts_queue(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL success[] = { TRUE, FALSE };

    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    state.headbuttSpawnCooldown = 0;
    state.fishingSpawnCooldown = 0;
    setRandomValues(0, 0);
    setSpawnResults(success, 2);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 1);
    assert(runtime.refillTerrainMask == 0);
    assert(runtime.queuedSpawnSlotPlusOne == OW_WILD_HEADBUTT_SLOT_START + 1);
    assert(scheduleCount == 2);
    assert(scheduleArguments[1] == OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);

    /* A new series is allowed to roll again.  The old remaining bits are gone. */
    runtime.queuedSpawnSlotPlusOne = 0;
    state.headbuttSpawnCooldown = 0;
    state.fishingSpawnCooldown = 0;
    setRandomValues(0, 0);
    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 2);
    assert(spawnTerrains[1] == OW_WILD_SPAWN_TERRAIN_HEADBUTT);
    assert(randomIndex == 2);
}

static void test_full_optional_groups_are_skipped_without_spawn_search(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL failure[] = { FALSE };

    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    state.headbuttSpawnCooldown = 0;
    state.fishingSpawnCooldown = 0;
    state.spawns[OW_WILD_HEADBUTT_SLOT_START].active = TRUE;
    state.spawns[OW_WILD_HEADBUTT_SLOT_START + 1].active = TRUE;
    state.spawns[OW_WILD_FISH_SLOT_START].active = TRUE;
    state.spawns[OW_WILD_FISH_SLOT_START + 1].active = TRUE;
    setRandomValues(0, 0);
    setSpawnResults(failure, 1);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 1);
    assert(spawnTerrains[0] == OW_WILD_SPAWN_TERRAIN_LAND);
    assert(spawnSlots[0] == 0);
    assert(freeSlotCalls == 3);
    assert(freeSlotStarts[0] == OW_WILD_HEADBUTT_SLOT_START);
    assert(freeSlotEnds[0] == OW_WILD_FISH_SLOT_START);
    assert(freeSlotStarts[1] == OW_WILD_FISH_SLOT_START);
    assert(freeSlotEnds[1] == OW_WILD_MAX_SPAWNS);
    assert(freeSlotStarts[2] == 0);
    assert(freeSlotEnds[2] == OW_WILD_LAND_SURF_MAX_SPAWNS);
    assert(runtime.refillTerrainMask == 8);

    /* A full ordinary group cancels its paired alternate without SpawnOne. */
    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    for (int slot = 0; slot < OW_WILD_LAND_SURF_MAX_SPAWNS; slot++) {
        state.spawns[slot].active = TRUE;
    }
    setRandomValues(99, 99);
    setSpawnResults(failure, 1);
    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 0);
    assert(freeSlotCalls == 1);
    assert(freeSlotStarts[0] == 0);
    assert(freeSlotEnds[0] == OW_WILD_LAND_SURF_MAX_SPAWNS);
    assert(runtime.refillTerrainMask == 0);
}

static void test_alternate_keeps_original_slot_and_cancels_if_occupied(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL failure[] = { FALSE };

    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    setSpawnResults(failure, 1);

    /* First update chooses slot 0 and fails preferred Land. */
    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 1);
    assert(spawnSlots[0] == 0);
    assert(spawnTerrains[0] == OW_WILD_SPAWN_TERRAIN_LAND);
    assert(runtime.refillTerrainMask == 8);
    assert(runtime.refillLandSurfSlot == 0);

    /* The original slot becomes occupied before the deferred alternate. */
    state.spawns[0].active = TRUE;
    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 1);
    assert(runtime.refillTerrainMask == 0);
    assert(freeSlotStarts[freeSlotCalls - 1] == 0);
    assert(freeSlotEnds[freeSlotCalls - 1] == 1);
}

static void test_gates_roll_once_and_density_includes_queued_candidate(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL failures[] = { FALSE, TRUE };

    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    state.headbuttSpawnCooldown = 0;
    state.fishingSpawnCooldown = 0;
    state.spawns[1].active = TRUE;
    setRandomValues(0, 99); /* Headbutt passes; fishing does not. */
    setSpawnResults(failures, 2);

    /* Headbutt fails, then the preferred ordinary slot succeeds. */
    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 1);
    assert(randomIndex == 2);
    assert(runtime.refillTerrainMask == (4 | 8));

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(spawnCalls == 2);
    assert(spawnTerrains[1] == OW_WILD_SPAWN_TERRAIN_LAND);
    assert(randomIndex == 2);
    assert(runtime.refillTerrainMask == 0);
    assert(scheduleCount == 2);
    /* One active ordinary slot plus one queued ordinary slot => 2 * interval - 1. */
    assert(scheduleArguments[1] == 2 * OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);
}

static void test_follower_has_immediate_priority(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL noOrdinaryAttempt[] = { FALSE };

    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = FALSE;
    followerSpawnResult = TRUE;
    followerCandidateResult = TRUE;
    setSpawnResults(noOrdinaryAttempt, 1);

    assert(OverworldWildSpawns_TryRefill(&state, &field) == TRUE);
    assert(followerSpawnCalls == 1);
    assert(spawnCalls == 0);
    assert(runtime.refillTerrainMask == 0);
    assert(randomIndex == 0);
}

static void test_cold_data_has_separate_updates_before_follower_or_timer(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    resetFixture(&state, &runtime, &resident, &field);
    sOverworldWildFlags.spawnWarmupPhase = 0;
    helperAvailable = FALSE;
    assert(!OverworldWildSpawns_TryRefill(&state, &field));
    assert(sOverworldWildFlags.spawnWarmupPhase == 0);
    assert(metadataWarmCalls == 0);
    helperAvailable = TRUE;
    assert(!OverworldWildSpawns_TryRefill(&state, &field));
    assert(sOverworldWildFlags.spawnWarmupPhase == 1);
    assert(metadataWarmCalls == 1 && behaviorWarmCalls == 0);
    assert(!OverworldWildSpawns_TryRefill(&state, &field));
    assert(sOverworldWildFlags.spawnWarmupPhase == 2);
    assert(metadataWarmCalls == 1 && behaviorWarmCalls == 1);
    assert(followerSpawnCalls == 0 && spawnCalls == 0);
    assert(scheduleCount == 0 && randomIndex == 0);
    followerSpawnResult = TRUE;
    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(sOverworldWildFlags.spawnWarmupPhase == 2);
    assert(followerSpawnCalls == 1 && spawnCalls == 0);
    assert(metadataWarmCalls == 1 && behaviorWarmCalls == 1);
}

static void test_warmup_never_creates_an_unscheduled_refill(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[0].active = TRUE;
    sOverworldWildFlags.spawnWarmupPhase = 0;
    assert(chooseMaintenanceWork(&state, &field) == OVERWORLD_ACTOR_POPULATION_WORK_REFILL);
    sOverworldWildFlags.spawnWarmupPhase = 1;
    assert(chooseMaintenanceWork(&state, &field) == OVERWORLD_ACTOR_POPULATION_WORK_REFILL);
    assert(advanceCalls == 0);
    sOverworldWildFlags.spawnWarmupPhase = 2;
    assert(chooseMaintenanceWork(&state, &field) == OVERWORLD_ACTOR_POPULATION_WORK_NONE);
    assert(advanceCalls == 1 && spawnCalls == 0 && randomIndex == 0);
    nextMaintenanceWork = OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN;
    assert(chooseMaintenanceWork(&state, &field) == OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN);
    assert(advanceCalls == 2);
}

int main(void)
{
    test_position_search_uses_one_sixteen_check_batch_per_terrain();
    test_warmup_never_creates_an_unscheduled_refill();
    test_cold_data_has_separate_updates_before_follower_or_timer();
    test_one_attempt_and_priority();
    test_first_success_cancels_remaining_and_counts_queue();
    test_full_optional_groups_are_skipped_without_spawn_search();
    test_alternate_keeps_original_slot_and_cancels_if_occupied();
    test_gates_roll_once_and_density_includes_queued_candidate();
    test_follower_has_immediate_priority();
    return 0;
}
'''


def build_host_binary():
    source = SOURCE.read_text()
    body = extract_function(source, "OverworldWildSpawns_TryRefill", "BOOL")
    frame = extract_function(source, "OverworldWildSpawns_FrameMovementTask", "void")
    dispatch = frame[frame.index("    if (runtime->queuedSpawnSlotPlusOne != 0) {"):
                     frame.index("    if (populationWork == OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN)")]
    chooser = ("\nstatic int chooseMaintenanceWork(OverworldWildSpawnState *state, FieldSystem *fieldSystem) {\n"
               "OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);\n"
               "BOOL playerStepMaintenanceRan = FALSE; u8 populationWork;\n"
               + dispatch + "\n(void)playerStepMaintenanceRan; return populationWork;\n}\n")
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-refill-budget-")
    root = Path(temp_dir.name)
    source_path = root / "spawn_refill_budget_host.c"
    binary_path = root / "spawn_refill_budget_host"
    source_path.write_text(PRELUDE + body + chooser + DRIVER)
    command = [
        "cc",
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        str(source_path),
        "-o",
        str(binary_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        temp_dir.cleanup()
        raise RuntimeError(error.stderr) from error
    return temp_dir, binary_path


HELPER_PRELUDE = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define TRUE 1
#define FALSE 0

typedef enum OverworldWildHelperPrepareResult {
    OW_WILD_HELPER_PREPARE_FAILED = 0,
    OW_WILD_HELPER_PREPARE_READY = 1,
    OW_WILD_HELPER_PREPARE_POSITION_PENDING = 2,
} OverworldWildHelperPrepareResult;

typedef enum OverworldWildSpawnTerrain {
    OW_WILD_SPAWN_TERRAIN_LAND = 1,
    OW_WILD_SPAWN_TERRAIN_SURF = 2,
    OW_WILD_SPAWN_TERRAIN_HEADBUTT = 3,
    OW_WILD_SPAWN_TERRAIN_FISHING = 4,
} OverworldWildSpawnTerrain;

typedef struct OverworldWildHelperSpawnCallbacks { int unused; }
    OverworldWildHelperSpawnCallbacks;
typedef struct OverworldWildSpawnPosition {
    int startX;
    int startY;
    u8 headbuttTreeType;
} OverworldWildSpawnPosition;
typedef struct OverworldWildRolledEncounter {
    u32 personality;
    u16 species;
    u8 form;
    u8 level;
} OverworldWildRolledEncounter;
typedef struct OverworldWildPreparedSpawn { int copied; } OverworldWildPreparedSpawn;

static BOOL callbacksValid = TRUE;
static OverworldWildHelperPrepareResult positionResult =
    OW_WILD_HELPER_PREPARE_READY;
static BOOL encounterPrepared = TRUE;
static int positionCalls;
static int encounterCalls;
static int copyCalls;

static BOOL OverworldWildHelper_AreSpawnCallbacksValid(
    const OverworldWildHelperSpawnCallbacks *callbacks)
{
    return callbacks != 0 && callbacksValid;
}

static OverworldWildHelperPrepareResult OverworldWildHelper_TryPickSpawnPositionForTerrain(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    OverworldWildSpawnPosition *position)
{
    (void)callbacks;
    (void)context;
    (void)terrain;
    positionCalls++;
    position->startX = 10;
    position->startY = 11;
    return positionResult;
}

static BOOL OverworldWildHelper_TryPrepareSpawnEncounter(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    const OverworldWildSpawnPosition *position,
    BOOL shinyAlreadySpawned,
    u16 shinyOddsDenominator,
    OverworldWildRolledEncounter *encounter,
    int *savedShinySlot,
    BOOL *shiny)
{
    (void)callbacks;
    (void)context;
    (void)terrain;
    (void)position;
    (void)shinyAlreadySpawned;
    (void)shinyOddsDenominator;
    encounterCalls++;
    encounter->species = 1;
    encounter->level = 5;
    *savedShinySlot = -1;
    *shiny = FALSE;
    return encounterPrepared;
}

static BOOL OverworldWildHelper_CopyPreparedSpawn(
    const OverworldWildSpawnPosition *position,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    OverworldWildPreparedSpawn *prepared)
{
    (void)position;
    (void)encounter;
    (void)shiny;
    (void)savedShinySlot;
    copyCalls++;
    prepared->copied = TRUE;
    return TRUE;
}
'''


HELPER_DRIVER = r'''
static void resetCounters(void)
{
    positionCalls = 0;
    encounterCalls = 0;
    copyCalls = 0;
}

int main(void)
{
    OverworldWildHelperSpawnCallbacks callbacks = {0};
    OverworldWildPreparedSpawn prepared = {0};

    resetCounters();
    positionResult = OW_WILD_HELPER_PREPARE_POSITION_PENDING;
    assert(OverworldWildHelper_TryPrepareSpawn(
        &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, 0, FALSE, 4096, 16,
        &prepared) == OW_WILD_HELPER_PREPARE_POSITION_PENDING);
    assert(positionCalls == 1 && encounterCalls == 0 && copyCalls == 0);

    resetCounters();
    positionResult = OW_WILD_HELPER_PREPARE_POSITION_PENDING;
    assert(OverworldWildHelper_TryPrepareSpawn(
        &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, 0, FALSE, 4096, 1,
        &prepared) == OW_WILD_HELPER_PREPARE_READY);
    assert(positionCalls == 1 && encounterCalls == 1 && copyCalls == 1);

    resetCounters();
    positionResult = OW_WILD_HELPER_PREPARE_READY;
    assert(OverworldWildHelper_TryPrepareSpawn(
        &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, 0, FALSE, 4096, 16,
        &prepared) == OW_WILD_HELPER_PREPARE_READY);
    assert(positionCalls == 1 && encounterCalls == 1 && copyCalls == 1);

    resetCounters();
    positionResult = OW_WILD_HELPER_PREPARE_FAILED;
    assert(OverworldWildHelper_TryPrepareSpawn(
        &callbacks, 0, OW_WILD_SPAWN_TERRAIN_HEADBUTT, 0, FALSE, 4096, 1,
        &prepared) == OW_WILD_HELPER_PREPARE_FAILED);
    assert(positionCalls == 1 && encounterCalls == 0 && copyCalls == 0);
    return 0;
}
'''


SCAN_PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>

typedef int BOOL;
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define TRUE 1
#define FALSE 0
#define OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH 1
#define OW_WILD_HELPER_SPAWN_MAX_DISTANCE 8
#define OW_WILD_HELPER_SPAWN_MIN_DISTANCE 4
#define OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_HELPER_SPAWN_POSITION_CHECKS_PER_UPDATE 16
#define OW_WILD_HELPER_SPAWN_POSITION_DIAMETER 17
#define OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT (17 * 17)
#define OW_WILD_HELPER_SPAWN_POSITION_STRIDE 73

typedef enum OverworldWildSpawnTerrain {
    OW_WILD_SPAWN_TERRAIN_LAND = 1,
    OW_WILD_SPAWN_TERRAIN_SURF = 2,
} OverworldWildSpawnTerrain;

typedef enum OverworldWildHelperPrepareResult {
    OW_WILD_HELPER_PREPARE_FAILED = 0,
    OW_WILD_HELPER_PREPARE_READY = 1,
    OW_WILD_HELPER_PREPARE_POSITION_PENDING = 2,
} OverworldWildHelperPrepareResult;

typedef struct OverworldWildSpawnPosition {
    int startX;
    int startY;
    u8 headbuttTreeType;
} OverworldWildSpawnPosition;

typedef struct OverworldWildHelperPlayerState {
    int playerX;
    int playerY;
    int objectX;
    int objectY;
    u8 facing;
    u8 hasObject;
    u8 reserved[2];
} OverworldWildHelperPlayerState;

typedef struct OverworldWildHelperSpawnCallbacks {
    BOOL (*getPlayerState)(void *, OverworldWildHelperPlayerState *);
    BOOL (*tryGetSpawnTerrain)(void *, int, int, OverworldWildSpawnTerrain *);
    BOOL (*isTileOccupied)(void *, int, int);
    BOOL (*isNearActiveSpawn)(void *, int, int, int);
} OverworldWildHelperSpawnCallbacks;

static u16 sOverworldWildHelperSpawnPositionCursor[2];
static int terrainCalls;
static int occupiedCalls;
static int nearCalls;
static BOOL rejectEveryTerrain;
static int queriedX[512];
static int queriedY[512];

static u32 gf_rand(void)
{
    return 0;
}

static int OverworldWildHelper_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildHelper_Max(int lhs, int rhs)
{
    return lhs > rhs ? lhs : rhs;
}

static BOOL getPlayerState(
    void *context,
    OverworldWildHelperPlayerState *playerState)
{
    (void)context;
    playerState->playerX = 100;
    playerState->playerY = 100;
    return TRUE;
}

static BOOL tryGetSpawnTerrain(
    void *context,
    int x,
    int y,
    OverworldWildSpawnTerrain *terrain)
{
    (void)context;
    assert(terrainCalls < (int)(sizeof(queriedX) / sizeof(queriedX[0])));
    queriedX[terrainCalls] = x;
    queriedY[terrainCalls] = y;
    terrainCalls++;
    if (rejectEveryTerrain) {
        return FALSE;
    }
    *terrain = terrainCalls == 1
        ? OW_WILD_SPAWN_TERRAIN_SURF
        : OW_WILD_SPAWN_TERRAIN_LAND;
    return TRUE;
}

static BOOL isTileOccupied(void *context, int x, int y)
{
    (void)context;
    (void)x;
    (void)y;
    occupiedCalls++;
    return FALSE;
}

static BOOL isNearActiveSpawn(void *context, int x, int y, int radius)
{
    (void)context;
    (void)x;
    (void)y;
    assert(radius == OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE);
    nearCalls++;
    return FALSE;
}
'''


SCAN_DRIVER = r'''
int main(void)
{
    OverworldWildHelperSpawnCallbacks callbacks = {
        getPlayerState,
        tryGetSpawnTerrain,
        isTileOccupied,
        isNearActiveSpawn,
    };
    OverworldWildSpawnPosition position = {0};

    assert(OverworldWildHelper_TryPickSpawnPosition(
        &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, &position)
        == OW_WILD_HELPER_PREPARE_READY);
    assert(terrainCalls == 2);
    assert(occupiedCalls == 1);
    assert(nearCalls == 1);
    assert(position.startX == 97);
    assert(position.startY == 96);

    /* The cursor must still traverse the complete 17x17 reservoir. Each
     * update exposes at most the legacy 16 distance-eligible tile batch. */
    memset(sOverworldWildHelperSpawnPositionCursor, 0,
        sizeof(sOverworldWildHelperSpawnPositionCursor));
    memset(queriedX, 0, sizeof(queriedX));
    memset(queriedY, 0, sizeof(queriedY));
    terrainCalls = occupiedCalls = nearCalls = 0;
    rejectEveryTerrain = TRUE;
    position.startX = 1234;
    position.startY = 5678;
    for (int i = 0; i < 15; i++) {
        int before = terrainCalls;
        assert(OverworldWildHelper_TryPickSpawnPosition(
            &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, &position)
            == OW_WILD_HELPER_PREPARE_POSITION_PENDING);
        assert(terrainCalls == before + 16);
        assert(position.startX == 1234);
        assert(position.startY == 5678);
    }
    assert(occupiedCalls == 0);
    assert(nearCalls == 0);
    assert(sOverworldWildHelperSpawnPositionCursor[0] == 1);

    {
        BOOL seen[17 * 17] = { FALSE };
        int cursor = 0;
        int query = 0;
        for (int visited = 0; visited < 17 * 17; visited++) {
            int candidate = cursor;
            int dx = candidate % 17 - 8;
            int dy = candidate / 17 - 8;
            int distance = OverworldWildHelper_Max(
                OverworldWildHelper_Abs(dx),
                OverworldWildHelper_Abs(dy));
            cursor = (cursor + 73) % (17 * 17);
            assert(!seen[candidate]);
            seen[candidate] = TRUE;
            if (distance < 4) {
                continue;
            }
            assert(query < terrainCalls);
            assert(queriedX[query] == 100 + dx);
            assert(queriedY[query] == 100 + dy);
            query++;
        }
        assert(query == 240);
        assert(cursor == 0);
        for (int i = 0; i < 17 * 17; i++) {
            assert(seen[i]);
        }
    }
    return 0;
}
'''


def build_helper_scan_host_binary():
    source = HELPER_SOURCE.read_text()
    scan = extract_function(
        source,
        "OverworldWildHelper_TryPickSpawnPosition",
        "OverworldWildHelperPrepareResult",
    )
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-helper-scan-")
    root = Path(temp_dir.name)
    source_path = root / "spawn_helper_scan_host.c"
    binary_path = root / "spawn_helper_scan_host"
    source_path.write_text(SCAN_PRELUDE + scan + SCAN_DRIVER)
    command = [
        "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        str(source_path), "-o", str(binary_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        temp_dir.cleanup()
        raise RuntimeError(error.stderr) from error
    return temp_dir, binary_path


def build_helper_incremental_host_binary():
    source = HELPER_SOURCE.read_text()
    prepare = extract_function(
        source,
        "OverworldWildHelper_TryPrepareSpawn",
        "OverworldWildHelperPrepareResult",
    )
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-helper-incremental-")
    root = Path(temp_dir.name)
    source_path = root / "spawn_helper_isolation_host.c"
    binary_path = root / "spawn_helper_isolation_host"
    source_path.write_text(HELPER_PRELUDE + prepare + HELPER_DRIVER)
    command = [
        "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        str(source_path), "-o", str(binary_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        temp_dir.cleanup()
        raise RuntimeError(error.stderr) from error
    return temp_dir, binary_path


class SpawnRefillBudgetTests(unittest.TestCase):
    def test_helper_checks_at_most_sixteen_eligible_tiles_per_update(self):
        temp_dir, binary = build_helper_scan_host_binary()
        try:
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        finally:
            temp_dir.cleanup()

    def test_incremental_helper_preserves_final_land_fallback(self):
        temp_dir, binary = build_helper_incremental_host_binary()
        try:
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        finally:
            temp_dir.cleanup()

    def test_incremental_refill_source_contract(self):
        source = SOURCE.read_text()
        help_children = extract_function(source, "OverworldWildSpawns_SpawnQueuedHelpChildren", "void")
        refill = extract_function(source, "OverworldWildSpawns_TryRefill", "BOOL")
        spawn_one = extract_function(source, "OverworldWildSpawns_SpawnOne", "OverworldWildHelperPrepareResult")
        commit = extract_function(source, "OverworldWildSpawns_CommitQueuedSpawn", "void")
        frame = extract_function(source, "OverworldWildSpawns_FrameMovementTask", "void")
        self.assertIn("OW_WILD_HELPER_PREPARE_POSITION_PENDING", refill)
        self.assertIn("refillLandSurfSlot", refill)
        self.assertIn("refillPositionChecksRemaining", refill)
        self.assertIn("OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES", refill)
        self.assertIn("OW_WILD_SPAWN_STARTUP_PENDING", refill)
        self.assertIn("OW_WILD_PROFILE_DESTINATION_SCAN_PENDING", spawn_one)
        self.assertIn("queuedSpawnTerrain", spawn_one)
        self.assertIn("queuedSpawnSlotPlusOne", spawn_one)
        self.assertIn("OverworldWildSpawns_FinalizePreparedSpawn", commit)
        self.assertIn("OW_WILD_SPAWN_STARTUP_PENDING", commit)
        self.assertIn("runtime->refillPositionChecksRemaining = 0;", commit)
        self.assertLess(
            frame.index("runtime->queuedSpawnSlotPlusOne != 0"),
            frame.index("runtime->refillTerrainMask != 0"),
        )
        self.assertIn("OW_WILD_HELPER_PREPARE_POSITION_PENDING", help_children)
        self.assertIn("movementHelpSpawnPositionChecksRemaining", help_children)
        self.assertNotIn("DiagnosticObjectCreationPaused", source)
        self.assertNotIn("DiagnosticStopAfterPositionScan", HELPER_SOURCE.read_text())

    def test_try_refill_budget_and_priority_contract(self):
        temp_dir, binary = build_host_binary()
        try:
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        finally:
            temp_dir.cleanup()

    def test_pending_refill_is_reset_on_context_abort_paths(self):
        source = SOURCE.read_text()
        for function_name in (
            "OverworldWildSpawns_DetachAllMovementStateOnContextLoss",
            "OverworldWildSpawns_OverlayOnFieldBusy",
            "OverworldWildSpawns_FrameMovementTask",
        ):
            body = extract_function(source, function_name, "void")
            self.assertIn("refillTerrainMask = 0", body, function_name)
            self.assertIn("refillPositionChecksRemaining = 0", body, function_name)

    def test_cold_refill_retries_before_consuming_pending_maintenance(self):
        source = SOURCE.read_text()
        frame = extract_function(source, "OverworldWildSpawns_FrameMovementTask", "void")
        self.assertLess(frame.index("sOverworldWildFlags.spawnWarmupPhase < 2"),
                        frame.index("OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE"))
        self.assertNotIn("spawnWarmupPhase < 3", frame)
        cleanup = extract_function(source, "OverworldWildSpawns_CleanupResidentData", "BOOL")
        self.assertIn("sOverworldWildFlags.spawnWarmupPhase = 0", cleanup)


if __name__ == "__main__":
    unittest.main()
