"""Host contract checks for the bounded ordinary-spawn refill work.

The small selection fixture checks ``TryRefill`` scan/RNG/warmup limits.
The existing Move Entry fixture also executes the real asynchronous queue,
COMMIT, retry receipt and Population reducers through named native seams.
These host checks do not build a ROM or start an emulator.
"""

from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
import re

try:
    from tools.overworld.test_spawn_spatial import extract_function
except ModuleNotFoundError:
    # The feature manifest runs this file directly. Keep module execution useful
    # for local unittest calls without making the checked command depend on
    # PYTHONPATH.
    from test_spawn_spatial import extract_function


ROOT = Path(__file__).resolve().parents[2]
# Registered checks can run this module as a direct file.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import verify_overworld_spawn_move_entry as entry_host
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
HELPER_SOURCE = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
ENTRY_SOURCE = ROOT / "lib/overworld/overworld_entry_route.c"
RUNTIME_HEADER = ROOT / "include/overworld_wild_runtime_state_internal.h"
ENTRY_HEADER = ROOT / "include/overworld_entry_route.h"
RETRY_FIXTURE = ROOT / "tools/overworld/fixtures/spawn_refill_retry_harness.c"


PRELUDE = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef int BOOL;
#define OVERWORLD_POPULATION_HOST 1
#include "overworld_population_model.h"

#define TRUE 1
#define FALSE 0
#define SPECIES_BULBASAUR 1
#define OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_CHECKS 16
#define OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES 1
/* CURRENT_SPAWN_PENDING_CONSTANTS */
/* CURRENT_REFILL_CONTRACT */

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
#define OW_WILD_REFILL_FULL_DENSITY_COUNT 4
#define OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES 8

#define OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING (1u << 0)

/* CURRENT_POPULATION_OPERATIONS */
static struct {
    OverworldPopulationState population;
    u16 fieldEpoch;
} gOverworldActorSystemState;
static BOOL transitionActive;
static void ActorSystem_EnsureInitialized(void) {}
static BOOL ActorSystem_TransitionIsActive(void) { return transitionActive; }
static void ActorSystem_InitPopulationInput(OverworldPopulationInput *input,
    u8 kind, u16 epoch)
{
    memset(input, 0, sizeof(*input));
    input->version = OVERWORLD_POPULATION_INPUT_VERSION;
    input->size = sizeof(*input);
    input->kind = kind; input->fieldEpoch = epoch;
}
static OverworldPopulationDecision ActorSystem_ApplyPopulationInput(
    const OverworldPopulationInput *input, OverworldPopulationResult *result)
{
    return OverworldPopulation_Apply(&gOverworldActorSystemState.population,
        input, result);
}
static u8 OverworldActorSystem_PopulationControlImpl(u8 operation, u16 refillDelay);
static void populationFrame(u8 flags)
{
    OverworldPopulationInput input;
    OverworldPopulationResult result;
    ActorSystem_InitPopulationInput(&input, OVERWORLD_POPULATION_INPUT_FRAME,
        gOverworldActorSystemState.fieldEpoch);
    input.flags = flags;
    (void)ActorSystem_ApplyPopulationInput(&input, &result);
}
/* CURRENT_POPULATION_WORK */

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
    u32 queuedSpawnSerial, refillQueuedSerial;
    u8 refillFailureStreak;
} OverworldWildOverlayRuntimeState;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    void *movementRuntimeState;
    int headbuttSpawnCooldown;
    int fishingSpawnCooldown;
    BOOL justSpawned;
    u16 mapGeneration;
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
static int advanceCalls, nextMaintenanceWork, waitQueries;
static int scheduleControl(int operation, int argument)
{
    if (operation == OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE) {
        assert(argument == 0);
        advanceCalls++;
        return nextMaintenanceWork;
    }
    if (operation == OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT) {
        waitQueries++;
        return OverworldActorSystem_PopulationControlImpl(operation, argument);
    }
    assert(operation == OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL);
    assert(scheduleCount < (int)(sizeof(scheduleArguments) / sizeof(scheduleArguments[0])));
    scheduleArguments[scheduleCount++] = argument;
    return OverworldActorSystem_PopulationControlImpl(operation, argument);
}

static u8 OverworldWildSpawns_PopulationControl(
    u8 operation,
    u16 refillDelay)
{
    return (u8)populationEntry.control(operation, refillDelay);
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
        OW_WILD_RUNTIME(state)->queuedSpawnTerrain = terrain;
        OW_WILD_RUNTIME(state)->queuedSpawnSerial++;
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
    gOverworldActorSystemState.fieldEpoch = 1;
    transitionActive = FALSE;
    (void)OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_RESET, 0);
    scheduleCount = 0; waitQueries = 0;
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

static void test_ready_cancels_remaining_without_counting_queue(void)
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
    /* READY ends the series except the alternate Land/Surf step (bit 8): the
     * destination is only placed at commit, and a failed commit still owes
     * one alternate attempt. A successful commit clears it. */
    assert(runtime.refillTerrainMask == 8);
    assert(runtime.queuedSpawnSlotPlusOne == OW_WILD_HEADBUTT_SLOT_START + 1);
    assert(scheduleCount == 1);
    assert(scheduleArguments[0] == OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);
    assert(runtime.refillQueuedSerial == runtime.queuedSpawnSerial);
    /* READY is admission only. The actual native-queue fixture below proves
     * completion and the next exact Population wait, rather than pretending
     * that clearing this stub queue means a successful native construction. */
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

static void test_gates_roll_once_without_counting_queued_candidate(void)
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
    /* The queued preferred Land spawn keeps its alternate step until commit. */
    assert(runtime.refillTerrainMask == 8);
    assert(scheduleCount == 1);
    assert(scheduleArguments[0] == OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);
    assert(runtime.refillQueuedSerial == runtime.queuedSpawnSerial);
    /* Only a real completed construction counts density; see the native
     * COMMIT/Population controls in the shared Entry fixture. */
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


static void test_new_batch_cannot_bypass_existing_wait(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const BOOL failures[] = { FALSE, FALSE };
    resetFixture(&state, &runtime, &resident, &field);
    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    setSpawnResults(failures, 2);
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL, 59);
    scheduleCount = 0;
    for (unsigned i = 0; i < 60; i++) {
        /* Dirty Player maintenance still visits refill. It must not roll a
         * new ordinary batch or restart this timer. */
        assert(OverworldWildSpawns_TryRefill(&state, &field));
        assert(spawnCalls == 0 && freeSlotCalls == 0 && randomIndex == 0);
        assert(scheduleCount == 0 && runtime.refillTerrainMask == 0);
        populationFrame(0); /* Ineligible time is not spent. */
        assert(gOverworldActorSystemState.population.refillArmed);
        populationFrame(OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE);
    }
    assert(!gOverworldActorSystemState.population.refillArmed);
    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(spawnCalls == 1 && scheduleCount == 1);
    assert(scheduleArguments[0] == 59);
}

static void test_wait_keeps_follower_and_started_attempt_work(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    const OverworldWildHelperPrepareResult pending[] = {
        OW_WILD_HELPER_PREPARE_POSITION_PENDING, OW_WILD_HELPER_PREPARE_FAILED };
    resetFixture(&state, &runtime, &resident, &field);
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL, 59);
    scheduleCount = 0;
    followerSpawnResult = TRUE;
    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(followerSpawnCalls == 1 && waitQueries == 0 && spawnCalls == 0);
    assert(scheduleCount == 0);

    state.spawns[OW_WILD_FOLLOWER_SLOT].active = TRUE;
    runtime.refillTerrainMask = 8;
    runtime.refillLandSurfSlot = 0;
    runtime.refillPositionChecksRemaining = 1;
    setPrepareResults(pending, 2);
    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(spawnCalls == 1 && waitQueries == 0);
    assert(runtime.refillTerrainMask == 8);
    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(spawnCalls == 2 && waitQueries == 0);
}

static void test_wait_read_is_only_a_value_and_maintenance_still_runs(void)
{
    OverworldWildSpawnState state;
    OverworldWildOverlayRuntimeState runtime;
    OverworldWildResidentData resident;
    FieldSystem field;
    OverworldPopulationState before;
    resetFixture(&state, &runtime, &resident, &field);
    assert(!OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT, 0));
    (void)OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL, 59);
    (void)OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE, 0);
    before = gOverworldActorSystemState.population;
    assert(OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT, 0));
    assert(memcmp(&before, &gOverworldActorSystemState.population, sizeof(before)) == 0);
    assert(OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE, 0) == 0);
    assert(OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE, 0) == OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN);
    assert(OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE, 0) == OVERWORLD_ACTOR_POPULATION_WORK_REFILL);
    assert(OverworldActorSystem_PopulationControlImpl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE, 0) == OVERWORLD_ACTOR_POPULATION_WORK_REVEAL);
    assert(gOverworldActorSystemState.population.refillTimer == 59);
    enabledMap = FALSE;
    assert(OverworldWildSpawns_TryRefill(&state, &field));
    assert(waitQueries == 0 && spawnCalls == 0);
}

int main(void)
{
    test_new_batch_cannot_bypass_existing_wait();
    test_wait_keeps_follower_and_started_attempt_work();
    test_wait_read_is_only_a_value_and_maintenance_still_runs();
    test_position_search_uses_one_sixteen_check_batch_per_terrain();
    test_warmup_never_creates_an_unscheduled_refill();
    test_cold_data_has_separate_updates_before_follower_or_timer();
    test_one_attempt_and_priority();
    test_ready_cancels_remaining_without_counting_queue();
    test_full_optional_groups_are_skipped_without_spawn_search();
    test_alternate_keeps_original_slot_and_cancels_if_occupied();
    test_gates_roll_once_without_counting_queued_candidate();
    test_follower_has_immediate_priority();
    return 0;
}
'''


def build_host_binary(*, wild_source=None, actor_source=None):
    source = SOURCE.read_text() if wild_source is None else wild_source
    body = extract_function(source, "OverworldWildSpawns_TryRefill", "BOOL")
    frame = extract_function(source, "OverworldWildSpawns_FrameMovementTask", "void")
    dispatch = frame[frame.index("    if (runtime->queuedSpawnSlotPlusOne != 0) {"):
                     frame.index("    if (populationWork == OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN)")]
    chooser = ("\nstatic int chooseMaintenanceWork(OverworldWildSpawnState *state, FieldSystem *fieldSystem) {\n"
               "OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);\n"
               "BOOL playerStepMaintenanceRan = FALSE; u8 populationWork; u16 newlyCreatedMask = 0;\n"
               + dispatch + "\n(void)playerStepMaintenanceRan; (void)newlyCreatedMask; return populationWork;\n}\n")
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-refill-budget-")
    root = Path(temp_dir.name)
    source_path = root / "spawn_refill_budget_host.c"
    binary_path = root / "spawn_refill_budget_host"
    actor = ((ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
             if actor_source is None else actor_source)
    control = extract_function(actor, "OverworldActorSystem_PopulationControlImpl", "u8")
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    operations = internal[internal.index("typedef enum OverworldActorPopulationControlOperation"):
                          internal.index("} OverworldActorPopulationControlOperation;") + len("} OverworldActorPopulationControlOperation;")]
    work = internal[internal.index("typedef enum OverworldActorPopulationWork"):
                    internal.index("} OverworldActorPopulationWork;") + len("} OverworldActorPopulationWork;")]
    prelude = PRELUDE.replace("/* CURRENT_POPULATION_OPERATIONS */", operations).replace(
        "/* CURRENT_POPULATION_WORK */", work)
    pending_names = (
        "OW_WILD_PROFILE_DESTINATION_SCAN_PENDING",
        "OW_WILD_SPAWN_STARTUP_PENDING",
        "OW_WILD_SPAWN_MOVE_DESTINATION_PENDING",
    )
    pending_lines = [line for line in RUNTIME_HEADER.read_text().splitlines()
                     if line.split()[:2] in [["#define", name] for name in pending_names]]
    if len(pending_lines) != len(pending_names):
        raise ValueError("expected each current spawn pending constant exactly once")
    prelude = prelude.replace("/* CURRENT_SPAWN_PENDING_CONSTANTS */", "\n".join(pending_lines))
    contract_names = ("OVERWORLD_ENTRY_REFILL_BACKOFF", "OVERWORLD_ENTRY_REFILL_FAILED",
                      "OVERWORLD_ENTRY_REFILL_BASE_FRAMES", "OVERWORLD_ENTRY_REFILL_RETRY_FRAMES",
                      "OVERWORLD_ENTRY_REFILL_SHORT_LIMIT", "OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE",
                      "OVERWORLD_ENTRY_REFILL_FAILURE_COUNT")
    contract_lines = [line for line in ENTRY_HEADER.read_text().splitlines()
                      if line.split()[:2] in [["#define", name] for name in contract_names]]
    if len(contract_lines) != len(contract_names):
        raise ValueError("expected each current retry contract constant exactly once")
    prelude = prelude.replace("/* CURRENT_REFILL_CONTRACT */", "\n".join(contract_lines))
    delay = extract_function(ENTRY_SOURCE.read_text(), "NativeRefillDelay", "u16")
    reset = extract_function(source, "OverworldWildSpawns_ResetRefillRetry", "void")
    # Selection-only fixture keeps the named native lease/spawn/slot seams.
    # The queue fixture below checks the real current owner and exact packets.
    native = extract_function(ENTRY_SOURCE.read_text(), "NativeOrdinaryRefill", "u32")
    native = native.replace("NativeRefillSlot(", "OverworldWildSpawns_TryGetFreeSlot(")
    contract = "\n".join(line for line in ENTRY_HEADER.read_text().splitlines()
                          if line.startswith("#define OVERWORLD_ENTRY_SPAWN_")
                          or line.startswith("#define OVERWORLD_ENTRY_COMMIT_REFILL_DELAY"))
    seams = r'''
#define OVERWORLD_ENTRY_NATIVE_SPAWN 8
    typedef struct OverworldActorSystemState {u16 fieldEpoch;} OverworldActorSystemState;
    static const OverworldActorSystemState selectionActors={1};
    typedef struct OverworldEntryRouteNativeOps {const OverworldActorSystemState *(*actors)(void);} OverworldEntryRouteNativeOps;
    typedef struct OverworldEntryRouteNativeControl {
        const OverworldEntryRouteNativeOps *ops;OverworldWildSpawnState *state;FieldSystem *field;
        u8 operation,queryOperation;
    } OverworldEntryRouteNativeControl;
    typedef struct OverworldCargoQueryWildCall {int unused;} OverworldCargoQueryWildCall;
    static const OverworldActorSystemState *SelectionActors(void){return &selectionActors;}
    static const OverworldEntryRouteNativeOps selectionOps={SelectionActors};
    static BOOL NativeRefillOwner(const OverworldEntryRouteNativeControl *c,
        const OverworldWildOverlayRuntimeState *runtime,
        const OverworldActorSystemState *actors,u16 epoch,u16 generation)
    {return c->state && c->field && runtime==OW_WILD_RUNTIME(c->state)
        && actors==&selectionActors && epoch==actors->fieldEpoch && generation==c->state->mapGeneration;}
    static OverworldWildHelperPrepareResult NativeSpawn(const OverworldCargoQueryWildCall *base,
        const OverworldEntryRouteNativeControl *c,OverworldWildSpawnState *state,
        FieldSystem *field,OverworldWildSpawnTerrain terrain,int slot)
    {(void)base;(void)c;return OverworldWildSpawns_SpawnOne(state,field,terrain,slot);}
    static u16 NativeFinishRefill(const OverworldEntryRouteNativeControl *c)
    {
        OverworldWildOverlayRuntimeState *runtime=OW_WILD_RUNTIME(c->state);
        if (!(runtime->refillFailureStreak & OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE)
            || runtime->queuedSpawnSlotPlusOne || runtime->refillQueuedSerial
            || runtime->refillTerrainMask || runtime->refillPositionChecksRemaining) return 0;
        return NativeRefillDelay(c->state,c->queryOperation==OVERWORLD_ENTRY_REFILL_FAILED);
    }
    '''
    caller = r'''
static u32 OverworldWildSpawns_EntryControl(OverworldWildSpawnState *state,
    FieldSystem *field,u8 slot,void *profile,OverworldEntryRouteNativeControl *c)
    {assert(slot==0 && profile==NULL && c->operation==OVERWORLD_ENTRY_NATIVE_SPAWN
        && c->queryOperation==OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL);
     c->state=state;c->field=field;c->ops=&selectionOps;return NativeOrdinaryRefill(NULL,c);}
    '''
    apply = extract_function(source, "OverworldWildSpawns_ApplyRefillDelay", "void")
    source_path.write_text(prelude + contract + "\n" + control + delay + reset + seams + native + caller + apply + body + chooser + DRIVER)
    command = [
        "cc",
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-DOVERWORLD_POPULATION_HOST=1",
        "-I", str(ROOT / "include"),
        str(ROOT / "lib/overworld/overworld_population_model.c"),
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
#define OW_WILD_HELPER_SPAWN_MAX_DISTANCE 10
#define OW_WILD_HELPER_SPAWN_MIN_DISTANCE 4
#define OW_WILD_HELPER_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_HELPER_SPAWN_POSITION_CHECKS_PER_UPDATE 32
#define OW_WILD_HELPER_SPAWN_POSITION_DIAMETER 21
#define OW_WILD_HELPER_SPAWN_POSITION_TILE_COUNT (21 * 21)
#define OW_WILD_HELPER_SPAWN_POSITION_STRIDE 73
#define OW_WILD_HELPER_SPAWN_FRONT_MIN_AHEAD 4
#define OW_WILD_HELPER_DIRECTION_NONE 0xFF
#define OW_WILD_HELPER_DIRECTION_UP 0
#define OW_WILD_HELPER_DIRECTION_DOWN 1
#define OW_WILD_HELPER_DIRECTION_LEFT 2
#define OW_WILD_HELPER_DIRECTION_RIGHT 3

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
    BOOL (*tryGetSpawnTerrain)(void *, int, int, u32 *);
    BOOL (*isTileOccupied)(void *, int, int);
    BOOL (*isNearActiveSpawn)(void *, int, int, int);
} OverworldWildHelperSpawnCallbacks;

static u16 sOverworldWildHelperSpawnPositionCursor[2];
static BOOL frontMode;
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
    playerState->facing = frontMode ? OW_WILD_HELPER_DIRECTION_UP : 0xFF;
    playerState->hasObject = TRUE;
    return TRUE;
}

static BOOL tryGetSpawnTerrain(
    void *context,
    int x,
    int y,
    u32 *terrain)
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
    assert(position.startX == 100);
    assert(position.startY == 93);

    /* The cursor must still traverse the complete 21x21 reservoir. Each
     * update exposes at most 32 distance-eligible tiles; 392 tiles lie at
     * least four away, so the thirteenth update wraps onto the first tiles. */
    memset(sOverworldWildHelperSpawnPositionCursor, 0,
        sizeof(sOverworldWildHelperSpawnPositionCursor));
    memset(queriedX, 0, sizeof(queriedX));
    memset(queriedY, 0, sizeof(queriedY));
    terrainCalls = occupiedCalls = nearCalls = 0;
    rejectEveryTerrain = TRUE;
    position.startX = 1234;
    position.startY = 5678;
    for (int i = 0; i < 13; i++) {
        int before = terrainCalls;
        assert(OverworldWildHelper_TryPickSpawnPosition(
            &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, &position)
            == OW_WILD_HELPER_PREPARE_POSITION_PENDING);
        assert(terrainCalls == before + 32);
        assert(position.startX == 1234);
        assert(position.startY == 5678);
    }
    assert(occupiedCalls == 0);
    assert(nearCalls == 0);
    for (int i = 0; i < 416 - 392; i++) {
        assert(queriedX[392 + i] == queriedX[i] && queriedY[392 + i] == queriedY[i]);
    }

    {
        BOOL seen[21 * 21] = { FALSE };
        int cursor = 0;
        int query = 0;
        for (int visited = 0; visited < 21 * 21; visited++) {
            int candidate = cursor;
            int dx = candidate % 21 - 10;
            int dy = candidate / 21 - 10;
            int distance = OverworldWildHelper_Max(
                OverworldWildHelper_Abs(dx),
                OverworldWildHelper_Abs(dy));
            cursor = (cursor + 73) % (21 * 21);
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
        assert(query == 392);
        assert(cursor == 0);
        for (int i = 0; i < 21 * 21; i++) {
            assert(seen[i]);
        }
    }

    /* Facing up, only tiles at least four ahead are checked, so a run keeps
     * finding Pokemon in front of the player. Every fourth starting cursor
     * checks the whole ring so a front without a valid tile cannot stall. */
    frontMode = TRUE;
    memset(sOverworldWildHelperSpawnPositionCursor, 0,
        sizeof(sOverworldWildHelperSpawnPositionCursor));
    terrainCalls = occupiedCalls = nearCalls = 0;
    rejectEveryTerrain = TRUE;
    {
        int frontAttempts = 0;
        int ringAttempts = 0;
        int ringBehind = 0;
        for (int attempt = 0; attempt < 12; attempt++) {
            unsigned stored = sOverworldWildHelperSpawnPositionCursor[0];
            unsigned start = stored == 0 ? 0 : stored - 1;
            int before = terrainCalls;
            assert(OverworldWildHelper_TryPickSpawnPosition(
                &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, &position)
                == OW_WILD_HELPER_PREPARE_POSITION_PENDING);
            assert(terrainCalls == before + 32);
            if ((start & 3) != 0) {
                frontAttempts++;
                for (int i = before; i < terrainCalls; i++) {
                    assert(100 - queriedY[i] >= OW_WILD_HELPER_SPAWN_FRONT_MIN_AHEAD);
                }
            } else {
                ringAttempts++;
                for (int i = before; i < terrainCalls; i++) {
                    ringBehind += 100 - queriedY[i] < OW_WILD_HELPER_SPAWN_FRONT_MIN_AHEAD;
                }
            }
        }
        assert(frontAttempts >= 6);
        assert(ringAttempts >= 1);
        assert(ringBehind != 0);
    }
    rejectEveryTerrain = FALSE;
    assert(OverworldWildHelper_TryPickSpawnPosition(
        &callbacks, 0, OW_WILD_SPAWN_TERRAIN_LAND, &position)
        == OW_WILD_HELPER_PREPARE_READY);
    frontMode = FALSE;
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



# The callback crosses independently compiled overlays.  Extract the real
# output contract and bodies; short enum storage must not size this buffer.
def build_helper_terrain_output_host_binary(budgeted, fault=None):
    header = (ROOT / "include/overworld_wild_helper.h").read_text()
    data = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    callback = re.search(
        r"typedef BOOL \(\*OverworldWildHelperTryGetSpawnTerrainFunc\)\([^;]*;",
        header, re.S,
    ).group(0)
    terrain_enum = re.search(
        r"typedef enum OverworldWildSpawnTerrain \{[^}]*\} OverworldWildSpawnTerrain;",
        data, re.S,
    ).group(0)
    helper = HELPER_SOURCE.read_text()
    if fault == "old-enum-output":
        assert helper.count("u32 terrain;") == 3
        helper = helper.replace("u32 terrain;", "OverworldWildSpawnTerrain terrain;")
    elif fault is not None:
        raise ValueError(fault)
    scan = extract_function(helper, "OverworldWildHelper_TryPickSpawnPosition",
                            "OverworldWildHelperPrepareResult")
    fishing = extract_function(helper, "OverworldWildHelper_TryPickFishingSpawnPosition", "BOOL")
    prelude = re.sub(
        r"typedef enum OverworldWildSpawnTerrain \{[^}]*\} OverworldWildSpawnTerrain;",
        terrain_enum + "\n" + callback, SCAN_PRELUDE, count=1,
    )
    prelude = prelude.replace(
        "BOOL (*tryGetSpawnTerrain)(void *, int, int, u32 *);",
        "OverworldWildHelperTryGetSpawnTerrainFunc tryGetSpawnTerrain;", 1,
    ).replace("#define OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH 1",
              f"#define OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH {int(budgeted)}")
    start = prelude.index("static BOOL tryGetSpawnTerrain(")
    end = prelude.index("static BOOL isTileOccupied(", start)
    prelude = prelude[:start] + TERRAIN_OUTPUT_CALLBACK + prelude[end:]
    prelude = prelude.replace("static BOOL rejectEveryTerrain;\n", "").replace(
        "static int queriedX[512];\nstatic int queriedY[512];\n", "")
    # No enum enters the fixed-width output boundary. The two TUs deliberately
    # use different enum flags, as the production overlays did.
    common = """#include <assert.h>
#include <stddef.h>
#include <stdint.h>
typedef int BOOL;
typedef uint8_t u8;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
typedef struct FieldSystem { int unused; } FieldSystem;
""" + terrain_enum + "\n"
    guard = extract_function(
        (ROOT / "src/pokemon_move_history_overlay/overworld_spawn_guard.c").read_text(),
        "OverworldWildSpawnGuard_IsSurfBehavior", "BOOL",
    )
    native = common + """
typedef struct { FieldSystem *fieldSystem; } OverworldWildSpawnPrepContext;
extern u8 HostSelectedBehavior(void *, int, int);
#define GetMetatileBehaviorAt HostSelectedBehavior
#define OverworldWildSpawns_IsSurfBehavior OverworldWildSpawnGuard_IsSurfBehavior
#define OW_WILD_TILE_ENCOUNTER_GRASS 2
#define OW_WILD_TILE_LONG_GRASS 3
""" + guard + "\n" + "\n".join(extract_function(SOURCE.read_text(), name, "BOOL") for name in (
        "OverworldWildSpawns_TryGetSpawnTerrain", "OverworldWildSpawns_HelperTryGetSpawnTerrain",
    )) + """
BOOL HostNativeTerrain(void *context, int x, int y, u32 *terrain)
{
    (void)context;
    assert(sizeof(OverworldWildSpawnTerrain) == 4);
    FieldSystem field = {0};
    OverworldWildSpawnPrepContext prep = { &field };
    return OverworldWildSpawns_HelperTryGetSpawnTerrain(&prep, x, y, terrain);
}
"""
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-helper-terrain-")
    fixture = Path(temp_dir.name)
    native_path = fixture / "wild_terrain.c"
    helper_path = fixture / "helper_selector.c"
    native_object = fixture / "wild_terrain.o"
    binary = fixture / "helper_selector"
    native_path.write_text(native)
    helper_path.write_text(prelude + TERRAIN_OUTPUT_OFFSETS + scan + fishing + TERRAIN_OUTPUT_DRIVER)
    flags = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror"]
    try:
        subprocess.run(flags + ["-fno-short-enums", "-c", str(native_path), "-o", str(native_object)],
                       check=True, capture_output=True, text=True)
        subprocess.run(flags + ["-fshort-enums", str(helper_path), str(native_object), "-o", str(binary)],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        temp_dir.cleanup()
        raise RuntimeError(error.stderr) from error
    return temp_dir, binary


TERRAIN_OUTPUT_CALLBACK = r'''
extern BOOL HostNativeTerrain(void *, int, int, u32 *);
static u8 selectedBehavior = 16;
u8 HostSelectedBehavior(void *context, int x, int y)
{
    (void)context; (void)x; (void)y;
    return selectedBehavior;
}
static BOOL tryGetSpawnTerrain(void *context, int x, int y, u32 *terrain)
{
    /* This is checked at every actual selector call, before the Wild write. */
    assert(((uintptr_t)terrain & 3u) == 0);
    assert(sizeof(*terrain) == 4);
    terrainCalls++;
    return HostNativeTerrain(context, x, y, terrain);
}
'''

TERRAIN_OUTPUT_OFFSETS = r'''
#define OW_WILD_HELPER_NELEMS(a) (sizeof(a) / sizeof((a)[0]))
typedef struct { int8_t dx, dy; } OverworldWildHelperCoordOffset;
static const OverworldWildHelperCoordOffset sOverworldWildHelperCardinalOffsets[] = {
    {0,1}, {0,-1}, {-1,0}, {1,0},
};
'''

TERRAIN_OUTPUT_DRIVER = r'''
int main(void)
{
    assert(sizeof(OverworldWildSpawnTerrain) == 1);
    assert(OW_WILD_SPAWN_TERRAIN_LAND == 0 && OW_WILD_SPAWN_TERRAIN_SURF == 1);
    OverworldWildHelperSpawnCallbacks callbacks = {
        getPlayerState, tryGetSpawnTerrain, isTileOccupied, isNearActiveSpawn,
    };
    OverworldWildSpawnPosition position = {0};
    selectedBehavior = 16;
    assert(OverworldWildHelper_TryPickSpawnPosition(&callbacks, 0,
        OW_WILD_SPAWN_TERRAIN_SURF, &position) == OW_WILD_HELPER_PREPARE_READY);
    assert(terrainCalls > 0 && terrainCalls <= 392);
    terrainCalls = occupiedCalls = nearCalls = 0;
    assert(OverworldWildHelper_TryPickFishingSpawnPosition(&callbacks, 0, &position));
    assert(terrainCalls == 1 && occupiedCalls == 1 && nearCalls == 0);
    assert(position.startX == 100 && position.startY == 101);
    u32 out = 0x5a6b7c8du;
    assert(HostNativeTerrain(0, 1, 1, &out) && out == 1);
    selectedBehavior = 2;
    assert(HostNativeTerrain(0, 1, 1, &out) && out == 0);
    selectedBehavior = 0xff;
    out = 0x5a6b7c8du;
    assert(!HostNativeTerrain(0, 1, 1, &out) && out == 0x5a6b7c8du);
    assert(!HostNativeTerrain(0, -1, 1, &out) && out == 0x5a6b7c8du);
    assert(!HostNativeTerrain(0, 1, 1, 0));
    terrainCalls = occupiedCalls = nearCalls = 0;
    memset(sOverworldWildHelperSpawnPositionCursor, 0, sizeof(sOverworldWildHelperSpawnPositionCursor));
    position.startX = 1234; position.startY = 5678;
#if OW_WILD_HELPER_BUDGETED_SPAWN_POSITION_SEARCH
    assert(OverworldWildHelper_TryPickSpawnPosition(&callbacks, 0,
        OW_WILD_SPAWN_TERRAIN_SURF, &position) == OW_WILD_HELPER_PREPARE_POSITION_PENDING);
    assert(terrainCalls == 32);
#else
    assert(OverworldWildHelper_TryPickSpawnPosition(&callbacks, 0,
        OW_WILD_SPAWN_TERRAIN_SURF, &position) == OW_WILD_HELPER_PREPARE_FAILED);
    assert(terrainCalls == 392);
#endif
    assert(position.startX == 1234 && position.startY == 5678);
    assert(occupiedCalls == 0 && nearCalls == 0);
    return 0;
}
'''


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


RETRY_FAULTS = (
    "premature-density", "manual-owner", "unbounded-retry", "stale-serial",
    "stale-field", "reset-leak", "two-attempts", "repeat-terminal",
    "finish-repeat", "typed-value", "post-owner",
)

def retry_host_program(fault=None):
 W=SOURCE.read_text()
 EXTRA,DRIVER=RETRY_FIXTURE.read_text().split("/* REFILL RETRY CONTROLS */",1)
 for name in ('OW_WILD_LAND_SURF_MAX_SPAWNS','OW_WILD_HEADBUTT_SLOT_START','OW_WILD_FISH_SLOT_START','OW_WILD_SPAWN_TERRAIN_LAND','OW_WILD_SPAWN_TERRAIN_SURF','OW_WILD_SPAWN_TERRAIN_HEADBUTT','OW_WILD_SPAWN_TERRAIN_FISHING','OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES'):
  EXTRA='\n'.join(line for line in EXTRA.split('\n') if not line.startswith('#define '+name+' '))
 files=entry_host.guided_program(ROOT);s=files['check.c']
 s=s.replace('static const OverworldActorSystemState *NativeActors(void){return &actors;}', 'static BOOL retryFieldCurrent=TRUE;static unsigned retryMutation;static const OverworldActorSystemState *NativeActors(void){return retryFieldCurrent?&actors:NULL;}')
 s=entry_host.mutate(s,'u32 queuedSpawnSerial;u32 refillQueuedSerial;u8 refillFailureStreak,refillTerrainMask,refillLandSurfSlot;u8 queuedSpawnSlotPlusOne;','u32 queuedSpawnSerial;u32 refillQueuedSerial;u8 refillFailureStreak,refillTerrainMask,refillLandSurfSlot;struct{u32 pendingFlags;}*residentData;u8 queuedSpawnSlotPlusOne;')
 s=s.replace('u16 captureTargetMask;u8 justSpawned;', 'int headbuttSpawnCooldown,fishingSpawnCooldown;u16 captureTargetMask;u8 justSpawned;')
 # Populate only native callback boundaries; all retry/COMMIT/queue/body decisions are real product C.
 s=s.replace('static BOOL destinationReady,occupiedOrigin;', 'static BOOL destinationReady,occupiedOrigin,destinationTerminal;')
 s=s.replace('refillPositionChecksRemaining=0xFF;return FALSE;', 'refillPositionChecksRemaining=destinationTerminal?0:0xFF;return FALSE;')
 s=s.replace('return constructorReady;}','if(constructorReady)s->spawns[slot].active=1;switch(retryMutation){case1:actors.fieldEpoch++;break;case2:actors.mapGeneration++;break;case3:s->mapGeneration++;break;case4:s->movementFieldSystem=NULL;break;case5:s->movementRuntimeState=NULL;break;case6:s->movementRuntimeState->queuedSpawnSerial++;break;}return constructorReady;}'.replace('case1','case 1').replace('case2','case 2').replace('case3','case 3').replace('case4','case 4').replace('case5','case 5').replace('case6','case 6'))
 s=s.replace('int main(void){return NativeControls();}', '')
 # Needed helpers precede the actual sole resident COMMIT caller.
 helper='\n'.join(entry_host.wild_function(W,n) for n in ['OverworldWildSpawns_ResetRefillRetry'])
 anchor=entry_host.wild_function(W,'OverworldWildSpawns_ApplyRefillDelay')
 assert s.count(anchor)==1
 s=entry_host.mutate(s,'static u8 OverworldWildSpawns_PopulationControl(u8 operation,u16 delay) {(void)operation;(void)delay;NEVER();}', '')
 s=s.replace(anchor,EXTRA+'\n#define OW_WILD_REFILL_FULL_DENSITY_COUNT 4\n#define OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES 8\nstatic void OverworldWildSpawns_ApplyRefillDelay(u16 delay);\n'+helper+'\n'+anchor)
 # Extract just the existing exact FieldBusy cleanup branch; run it with real reset helper.
 busy=entry_host.wild_function(W,'OverworldWildSpawns_OverlayOnFieldBusy')
 start=busy.index('    if (state->movementRuntimeState != NULL) {');end=busy.index('    OverworldWildSpawns_MountCancel(',start)
 reset='static void RetryFieldBusy(OverworldWildSpawnState*state){\n'+busy[start:end]+'}\n'
 s += '\nstatic typeof(*runtime.residentData) retryResident;\n'+entry_host.wild_function(W,'OverworldWildSpawns_TryRefill')+'\n'+reset+DRIVER
 s=s.replace('static typeof(*runtime.residentData) retryResident;','static struct{u32 pendingFlags;}retryResident;')
 # Give resident pointer a named type to avoid a host-only anonymous-type warning.
 s=s.replace('typedef struct OverworldWildOverlayRuntimeState {','typedef struct RetryResident{u32 pendingFlags;}RetryResident;\ntypedef struct OverworldWildOverlayRuntimeState {',1)
 s=s.replace('struct{u32 pendingFlags;}*residentData;', 'RetryResident*residentData;')
 s=s.replace('static struct{u32 pendingFlags;}retryResident;', 'static RetryResident retryResident;')
 if fault=='premature-density':s=entry_host.mutate(s,'        runtime->refillTerrainMask &= 8;\n        if (runtime->queuedSpawnSlotPlusOne == slot + 1','        runtime->refillTerrainMask &= 8;\n        (void)NativeRefillDelay(state,0);\n        if (runtime->queuedSpawnSlotPlusOne == slot + 1')
 elif fault=='manual-owner':s=entry_host.mutate(s,'    return runtime->queuedSpawnSerial;\n}', '    runtime->refillQueuedSerial=runtime->queuedSpawnSerial;runtime->refillFailureStreak|=OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE;\n    return runtime->queuedSpawnSerial;\n}')
 elif fault=='unbounded-retry':s=entry_host.mutate(s,'failures<OVERWORLD_ENTRY_REFILL_SHORT_LIMIT','failures<99')
 elif fault=='stale-serial':s=entry_host.mutate(s,'serial==runtime->queuedSpawnSerial','1');s=entry_host.mutate(s,'        || runtime->queuedSpawnSerial!=serial || runtime->refillQueuedSerial!=serial','        || runtime->refillQueuedSerial!=serial')
 elif fault=='stale-field':s=entry_host.mutate(s,'return actors!=NULL && c->ops->actors()==actors','return TRUE || (actors!=NULL && c->ops->actors()==actors');s=entry_host.mutate(s,'&& c->field->playerAvatar!=NULL;', '&& c->field->playerAvatar!=NULL);')
 elif fault=='reset-leak':s=entry_host.mutate(s,'    runtime->refillFailureStreak = 0;\n}', '    /* stale failure streak retained */\n}')
 elif fault=='two-attempts':s=entry_host.mutate(s,'        break; /* Never start a second terrain search in this update. */','        continue; /* copied fault: two attempts in one update */')
 elif fault=='repeat-terminal':
  s=entry_host.mutate(s,'        && runtime->queuedSpawnSlotPlusOne!=0\n', '')
  s=entry_host.mutate(s,'        && (runtime->refillFailureStreak&OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE)\n', '')
  s=entry_host.mutate(s,'    runtime->refillQueuedSerial=0;\n    if(outcome==OVERWORLD_ENTRY_COMMIT_SUCCESS)', '    if(outcome==OVERWORLD_ENTRY_COMMIT_SUCCESS)')
  s=entry_host.mutate(s,'        return OVERWORLD_ENTRY_COMMIT_NONE;', '        return OVERWORLD_ENTRY_COMMIT_FAILED;')
 elif fault=='finish-repeat':s=entry_host.mutate(s,'runtime->refillFailureStreak=failures+1;', 'runtime->refillFailureStreak=(failures+1)|OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE;')
 elif fault=='typed-value':s=entry_host.mutate(s,'if(c->value || c->slot || c->terrain', 'if(c->slot || c->terrain')
 elif fault=='post-owner':s=entry_host.mutate(s,'        || !NativeRefillOwner(c,runtime,actors,epoch,generation)\n', '')
 elif fault is not None:raise ValueError(fault)
 # Actual Population timer, not a simulated count down.
 s += '\n'+entry_host.without_includes((ROOT/'lib/overworld/overworld_population_model.c').read_text())
 files['check.c']=s;return files


def build_retry_host_binary(fault=None):
    temp_dir = tempfile.TemporaryDirectory(prefix="spawn-refill-native-")
    try:
        binary = entry_host.compile_program(temp_dir.name, retry_host_program(fault), ROOT, linked=True)
    except Exception:
        temp_dir.cleanup()
        raise
    return temp_dir, binary


class SpawnRefillBudgetTests(unittest.TestCase):
    def test_terrain_output_is_fixed_width_with_short_enums(self):
        for budgeted in (True, False):
            with self.subTest(budgeted=budgeted):
                temp_dir, binary = build_helper_terrain_output_host_binary(budgeted)
                try:
                    subprocess.run([str(binary)], check=True, capture_output=True, text=True)
                finally:
                    temp_dir.cleanup()

    def test_old_enum_output_locals_are_rejected(self):
        for budgeted in (True, False):
            with self.subTest(budgeted=budgeted):
                with self.assertRaisesRegex(RuntimeError, "incompatible pointer"):
                    build_helper_terrain_output_host_binary(budgeted, "old-enum-output")

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
        entry_source = ENTRY_SOURCE.read_text()
        help_children = extract_function(source, "OverworldWildSpawns_SpawnQueuedHelpChildren", "void")
        refill = extract_function(source, "OverworldWildSpawns_TryRefill", "BOOL")
        spawn_one = extract_function(source, "OverworldWildSpawns_SpawnOne", "OverworldWildHelperPrepareResult")
        commit = extract_function(source, "OverworldWildSpawns_CommitQueuedSpawn", "void")
        entry_control = extract_function(source, "OverworldWildSpawns_EntryControl", "u32")
        native_spawn = extract_function(entry_source, "NativeSpawn", "OverworldWildHelperPrepareResult")
        native_commit = extract_function(entry_source, "NativeCommitOnce", "u32")
        terminal = extract_function(entry_source, "NativeCommit", "u32")
        native_finalize = extract_function(entry_source, "NativeFinalize", "BOOL")
        native_control = extract_function(entry_source, "OverworldEntryRoute_NativeControl", "OverworldPickupRouteStatus")
        frame = extract_function(source, "OverworldWildSpawns_FrameMovementTask", "void")
        ordinary = extract_function(entry_source, "NativeOrdinaryRefill", "u32")
        self.assertIn("OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL", refill)
        self.assertIn("OW_WILD_HELPER_PREPARE_POSITION_PENDING", ordinary)
        self.assertIn("refillLandSurfSlot", ordinary)
        self.assertIn("refillPositionChecksRemaining", refill)
        self.assertIn("OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES", ordinary)
        self.assertIn("OW_WILD_SPAWN_MOVE_DESTINATION_PENDING", ordinary)
        # Wild owns scheduling. The synchronous Entry reducer now owns the
        # unchanged preparation/finalization/commit sequence through this seam.
        self.assertIn("c.operation=OVERWORLD_ENTRY_NATIVE_SPAWN", spawn_one)
        self.assertIn("c.terrain=terrain", spawn_one)
        self.assertIn("OverworldWildSpawns_EntryControl(state,field,slot,NULL,&c)", spawn_one)
        self.assertIn("c.operation=OVERWORLD_ENTRY_NATIVE_COMMIT", commit)
        self.assertIn("OverworldWildSpawns_EntryControl(state,field,0,NULL,&c)", commit)
        self.assertIn("command.nativeControl=control", entry_control)
        self.assertIn("call.routeOperation=OVERWORLD_FIELD_ROUTE_ENTRY", entry_control)
        self.assertIn("entry->cargoWildTick(&call,&result)", entry_control)
        self.assertIn("OVERWORLD_PICKUP_ROUTE_REACHABLE?control->value:rejected", entry_control)
        self.assertIn("case OVERWORLD_ENTRY_NATIVE_SPAWN:", native_control)
        self.assertIn("NativeOrdinaryRefill(base,c)", native_control)
        self.assertIn("NativeSpawn(base,c,c->state,c->field,c->terrain,c->slot)", native_control)
        self.assertEqual(ordinary.count("NativeSpawn(base,c,state,fieldSystem,preferredTerrain,slot)"),1)
        self.assertIn("case OVERWORLD_ENTRY_NATIVE_COMMIT:", native_control)
        self.assertIn("c->value=NativeCommit(base,c,c->state,c->field)", native_control)
        self.assertIn("case OVERWORLD_ENTRY_NATIVE_FINISH_REFILL:", native_control)
        self.assertIn("c->value=NativeFinishRefill(c)", native_control)
        self.assertIn("NativeCommitOnce(base,c,state,field)", terminal)
        self.assertIn("runtime->refillQueuedSerial=0", terminal)
        self.assertIn("OVERWORLD_ENTRY_COMMIT_REFILL_DELAY(value)", commit)
        self.assertEqual(native_spawn.count("c->ops->prepare("), 1)
        self.assertLess(native_spawn.index("c->ops->prepare("), native_spawn.index("NativeArm("))
        self.assertLess(native_spawn.index("NativeArm("), native_spawn.index("NativeFinalize("))
        self.assertIn("queuedSpawnTerrain", native_spawn)
        self.assertIn("queuedSpawnSlotPlusOne", native_spawn)
        self.assertIn("OW_WILD_SPAWN_MOVE_DESTINATION_PENDING", native_spawn)
        self.assertIn("OW_WILD_PROFILE_DESTINATION_SCAN_PENDING", native_finalize)
        self.assertIn("OW_WILD_SPAWN_STARTUP_PENDING", native_finalize)
        self.assertIn("NativeFinalize(", native_commit)
        self.assertIn("OW_WILD_SPAWN_MOVE_DESTINATION_PENDING", native_commit)
        consume = native_commit.index("runtime->queuedSpawnSlotPlusOne = 0;", native_commit.index("x = prepared->startup.targetX"))
        reset = native_commit.index("runtime->refillPositionChecksRemaining = 0;", consume)
        self.assertLess(consume, reset)
        self.assertLess(reset, native_commit.index("c->ops->guard("))
        self.assertLess(native_commit.index("c->ops->guard("), native_commit.index("c->ops->placementBlocked("))
        self.assertLess(native_commit.index("c->ops->placementBlocked("), native_commit.index("c->ops->spawn("))
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

    def test_native_queue_completion_and_bounded_refill_retry(self):
        temp_dir, binary = build_retry_host_binary()
        try:
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        finally:
            temp_dir.cleanup()


    def test_ordinary_refill_subtype_rejects_unused_inputs_and_changed_owner(self):
        files = retry_host_program()
        program = files['check.c']
        program = program.replace('static unsigned prepares,guards,placements,constructors;',
            'static unsigned retryPrepareMutation;static unsigned prepares,guards,placements,constructors;', 1)
        program = entry_host.mutate(program, 'prepares++;if(prepareResult!=1)return prepareResult;',
            'prepares++;if(prepareResult!=1){switch(retryPrepareMutation){case 1:actors.fieldEpoch++;break;case 2:actors.mapGeneration++;break;case 3:s->mapGeneration++;break;case 4:s->movementFieldSystem=NULL;break;case 5:s->movementRuntimeState=NULL;break;case 6:retryFieldCurrent=FALSE;break;}return prepareResult;}')
        controls = r"""
static int OrdinaryPacketControls(void) {
 for(int bad=0;bad<14;bad++) {
  RetryReset();
  OverworldEntryRouteNativeControl packet={.version=1,.size=sizeof(packet),.ops=&sOverworldWildEntryNativeOps,.state=&spawns,.field=&field,.operation=OVERWORLD_ENTRY_NATIVE_SPAWN,.queryOperation=OVERWORLD_ENTRY_SPAWN_ORDINARY_REFILL};
  OverworldEntryRouteCommand command={0};command.nativeControl=&packet;
  call.entry=&command;call.routeOperation=1;call.heapId=4;world.slot=0;
  switch(bad){case 0:packet.value=1;break;case 1:packet.slot=world.slot=1;break;case 2:packet.terrain=1;break;case 3:packet.accepted=1;break;case 4:packet.usableIdle=1;break;case 5:packet.profile=&profile;break;case 6:packet.primitives=&primitives;break;case 7:packet.prepared=&runtime.queuedSpawn;break;case 8:packet.object=&objects[0];break;case 9:packet.receipt=&runtime.entryRouteReceipt;break;case 10:packet.startCommitSequence=1;break;case 11:packet.reserved[0]=1;break;case 12:packet.reserved[1]=1;break;case 13:packet.queryOperation=2;break;}
  OverworldWildOverlayRuntimeState prior=runtime;
  OverworldEntryRouteNativeControl before=packet;
  CHECK(OverworldCargoQueryWild_Tick(&call,&output)==INVALID);
  CHECK(!memcmp(&runtime,&prior,sizeof(runtime)) && !memcmp(&packet,&before,sizeof(packet)) && !prepares);
 }
 puts("ordinary SPAWN fourteen unused-input/subtype rejections preserve packet/Runtime and make no attempt PASS");
 for(int fault=1;fault<=6;fault++) {
  RetryReset();retryPrepareMutation=fault;prepareResult=0;
  CHECK(OverworldWildSpawns_TryRefill(&spawns,&field));
  CHECK(prepares==1 && runtime.refillTerrainMask==8 && runtime.refillPositionChecksRemaining==1);
  CHECK(runtime.refillFailureStreak==OVERWORLD_ENTRY_REFILL_SERIES_ACTIVE && retryScheduleCount==1 && !runtime.refillQueuedSerial);
 }
 puts("prepare callback owner/epoch/map/Field/Runtime changes cannot retain writes or publish a natural delay PASS");
 return 0;
}
"""
        program = entry_host.mutate(program, 'int main(void){if(NativeControls())return 1;return RetryControls();}',
            controls+'\nint main(void){return OrdinaryPacketControls();}')
        files['check.c'] = program
        with tempfile.TemporaryDirectory(prefix='spawn-refill-subtype-') as directory:
            binary = entry_host.compile_program(directory, files, ROOT, linked=True)
            subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        # Removing the post-callback owner check must lose the saved pending
        # state in this exact real-C sequence, not merely change a source label.
        files['check.c'] = entry_host.mutate(program,
            '        if(!NativeRefillOwner(c,runtime,actors,epoch,generation)) return prepareResult;', '')
        with tempfile.TemporaryDirectory(prefix='spawn-refill-subtype-bad-') as directory:
            binary = entry_host.compile_program(directory, files, ROOT, linked=True)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertNotEqual(completed.returncode,0)

    def test_native_retry_controls_reject_known_bad_product_copies(self):
        for fault in RETRY_FAULTS:
            with self.subTest(fault=fault):
                temp_dir, binary = build_retry_host_binary(fault)
                try:
                    completed = subprocess.run([str(binary)], capture_output=True, text=True)
                    self.assertNotEqual(completed.returncode, 0, fault)
                finally:
                    temp_dir.cleanup()

    def test_wait_gate_controls_reject_bypass_and_blocked_progress(self):
        source = SOURCE.read_text()
        actor = (ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
        gate = """        if (OverworldWildSpawns_PopulationControl(
                OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_REFILL_WAIT, 0)) {
            return TRUE;
        }
"""
        self.assertEqual(source.count(gate), 1)
        mutants = {
            "new-batch-bypass": (source.replace(gate, "", 1), actor),
            "follower-blocked": (source.replace(gate, "", 1).replace(
                "    if (!OverworldWildSpawns_ReconcileFollowerSelection(",
                gate + "    if (!OverworldWildSpawns_ReconcileFollowerSelection(", 1), actor),
            "started-search-blocked": (source.replace(gate, "", 1).replace(
                "    if (runtime->refillPositionChecksRemaining == 0\n",
                gate + "    if (runtime->refillPositionChecksRemaining == 0\n", 1), actor),
            "consuming-wait-read": (source, actor.replace(
                "return gOverworldActorSystemState.population.refillArmed;",
                "return gOverworldActorSystemState.population.refillArmed = 0;", 1)),
        }
        for name, (wild, native) in mutants.items():
            with self.subTest(name=name):
                temp_dir, binary = build_host_binary(wild_source=wild, actor_source=native)
                try:
                    completed = subprocess.run([str(binary)], capture_output=True, text=True)
                    self.assertNotEqual(completed.returncode, 0, name)
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
            self.assertIn("OverworldWildSpawns_ResetRefillRetry", body, function_name)

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
