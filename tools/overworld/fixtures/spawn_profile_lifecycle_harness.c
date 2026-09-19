/* Production InitSpawnSlotState and StartSpawnStartup are inserted unchanged.
 * Only their engine/cache boundary calls below are host stubs. CacheLookup
 * deliberately models the existing MISS-publishes/HIT-does-not-publish seam;
 * this is not a test of the complete resolver or a DS memory-layout claim.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_actor_system.h"
typedef int BOOL;
#define TRUE 1
#define FALSE 0
/* @CONSTANTS@ */
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
typedef struct LocalMapObject { int xCurr, yCurr; } LocalMapObject;
typedef struct Location { int mapId; } Location;
typedef struct FieldSystem { Location *location; } FieldSystem;
typedef int OverworldWildSpawnTerrain;
typedef struct OverworldWildRolledEncounter {
    u32 personality; u16 species; u8 form, level;
} OverworldWildRolledEncounter;
typedef struct OverworldWildSpawn {
    LocalMapObject *object; u32 personality; u16 mapId, species;
    u8 form, level, terrain, shiny, active, objectId; u16 encounterGeneration;
} OverworldWildSpawn;
typedef struct OverworldWildSpawnStartup {
    int startX, startY, targetX, targetY; u8 locomotion;
} OverworldWildSpawnStartup;
typedef struct OverworldWildPreparedSpawn {
    OverworldWildSpawnStartup startup;
    struct {
        u32 matchedClassRuleMask;
        u32 appliedOverrideMask;
        u32 fingerprint;
    } behaviorResolution;
} OverworldWildPreparedSpawn;
typedef struct Runtime {
    u8 playerBallCatchValues[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorLimitKeys[OW_WILD_MAX_SPAWNS];
    struct {
        s16 lastKnownX[OW_WILD_MAX_SPAWNS], lastKnownY[OW_WILD_MAX_SPAWNS];
        u16 managerRestoreMask; u8 farSamples[OW_WILD_MAX_SPAWNS];
    } spawnPresentations;
} Runtime;
typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorClasses[OW_WILD_MAX_SPAWNS];
    Runtime runtime;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) (&(state)->runtime)

static unsigned checks, cases, bindCalls, unbindCalls, lookups, misses, hits;
static unsigned runCalls, hopCalls, appearCalls, activeSlot;
static BOOL actorActive, rejectBind, hopAccepted, cacheValid;
static u32 fingerprint, matchedMask;
static OverworldActorHandle acceptedHandle, unboundHandle;
#define CHECK(expression) do { checks++; if (!(expression)) { \
    fprintf(stderr, "spawn profile invariant failed at line %d: %s\n", __LINE__, #expression); \
    exit(1); } } while (0)

static void HarnessProfileLookup(int slot)
{
    lookups++;
    CHECK(actorActive && bindCalls == 1 && slot == (int)activeSlot);
    if (!cacheValid) {
        misses++;
        cacheValid = TRUE;
        fingerprint = 3976342989u ^ activeSlot;
        matchedMask = 192;
    } else {
        hits++;
    }
}
static u32 OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object) { return object->xCurr; }
static u32 OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object) { return object->yCurr; }
static void OverworldWildSpawns_ResetSlotSpotState(OverworldWildSpawnState *state, int slot) { (void)state; (void)slot; }
static void OverworldWildSpawns_ClearCachedBehaviorProfile(OverworldWildSpawnState *state, int slot)
{ (void)state; (void)slot; cacheValid = FALSE; }
static void OverworldWildSpawns_ClearMankeyTreeTopCache(OverworldWildSpawnState *state, int slot) { (void)state; (void)slot; }
static void OverworldWildSpawns_ClearMovementSlotInProgress(OverworldWildSpawnState *state, int slot) { (void)state; (void)slot; }
static void __attribute__((unused)) OverworldWildSpawns_SetObjectTile(LocalMapObject *object, int x, int y)
{ object->xCurr = x; object->yCurr = y; }
static void OverworldWildSpawns_ApplySpawnPassThroughFlag(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; }
static void OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(OverworldWildSpawnState *state, FieldSystem *field, int slot, LocalMapObject *object)
{ (void)state; (void)field; (void)object; HarnessProfileLookup(slot); }
static void __attribute__((unused)) OverworldWildSpawns_SeedPreparedBehaviorProfile(
    OverworldWildSpawnState *state, int slot,
    const OverworldWildPreparedSpawn *prepared)
{
    (void)state;
    CHECK(actorActive && bindCalls == 1 && slot == (int)activeSlot);
    cacheValid = TRUE;
    fingerprint = prepared->behaviorResolution.fingerprint;
    matchedMask = prepared->behaviorResolution.matchedClassRuleMask
        | prepared->behaviorResolution.appliedOverrideMask;
}
static BOOL BindActor(FieldSystem *field, OverworldWildSpawnState *state, int slot, OverworldActorHandle *handle)
{
    (void)field;
    bindCalls++;
    if (rejectBind || actorActive) return FALSE;
    CHECK(state->spawns[slot].active);
    CHECK(state->spawns[slot].encounterGeneration != 0);
    actorActive = TRUE;
    fingerprint = matchedMask = 0; /* Fresh Actor policy reset is required. */
    acceptedHandle = (OverworldActorHandle){.slot = slot, .generation = 17,
        .fieldEpoch = 4, .mapGeneration = 4,
        .encounterGeneration = state->spawns[slot].encounterGeneration};
    *handle = acceptedHandle;
    return TRUE;
}
static OverworldActorResult UnbindActor(const OverworldActorHandle *handle, u16 reason)
{
    unbindCalls++;
    CHECK(reason == OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
    CHECK(memcmp(handle, &acceptedHandle, sizeof(*handle)) == 0);
    unboundHandle = *handle;
    actorActive = FALSE;
    return OVERWORLD_ACTOR_RESULT_OK;
}
static struct { BOOL (*bindActor)(FieldSystem *, OverworldWildSpawnState *, int, OverworldActorHandle *); }
    runtimeEntry = { BindActor };
static struct { OverworldActorResult (*unbind)(const OverworldActorHandle *, u16); }
    compatEntry = { UnbindActor };
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compatEntry)
#define HARNESS_SKIP_UNBIND(handle, reason) ((void)compatEntry.unbind, (void)(handle), (void)(reason), 0)
static void OverworldWildSpawns_StartSpawnRun(OverworldWildSpawnState *state, FieldSystem *field, int slot, int x, int y)
{ (void)state; (void)field; (void)slot; (void)x; (void)y; runCalls++; }
static BOOL OverworldWildSpawns_StartSpawnHop(OverworldWildSpawnState *state, FieldSystem *field, int slot, int sx, int sy, int tx, int ty)
{ (void)state; (void)field; (void)sx; (void)sy; (void)tx; (void)ty; hopCalls++; HarnessProfileLookup(slot); return hopAccepted; }
static void OverworldWildSpawns_StartSpawnAppearHop(OverworldWildSpawnState *state, FieldSystem *field, int slot)
{ (void)state; (void)field; (void)slot; appearCalls++; }

/* @INIT_SLOT@ */
/* @STARTUP@ */

static void RunCase(int slot, int mode, BOOL reject, BOOL hopSucceeds, u16 oldGeneration)
{
    OverworldWildSpawnState state = {0};
    LocalMapObject object = {548, 389};
    Location location = {34};
    FieldSystem field = {&location};
    OverworldWildRolledEncounter encounter = {393047622, 165, 0, 4};
    OverworldWildPreparedSpawn prepared = {
        .startup = {548, 373, 548, 389, mode},
        .behaviorResolution = {
            .matchedClassRuleMask = 192,
            .fingerprint = 3976342989u ^ slot,
        },
    };
    activeSlot = slot;
    actorActive = rejectBind = reject;
    hopAccepted = hopSucceeds;
    cacheValid = TRUE;
    fingerprint = 0xABCDEF;
    matchedMask = 0x55;
    bindCalls = unbindCalls = lookups = misses = hits = 0;
    runCalls = hopCalls = appearCalls = 0;
    memset(&acceptedHandle, 0, sizeof(acceptedHandle));
    state.spawns[slot].encounterGeneration = oldGeneration;
    OverworldWildSpawns_InitSpawnSlotState(&state, &field, 0, slot, &object,
        &encounter, FALSE, 2, 3, 100);
    BOOL started = OverworldWildSpawns_StartSpawnStartup(&state, &field, slot, &prepared);
    cases++;
    CHECK(bindCalls == 1);
    CHECK(state.spawns[slot].encounterGeneration == (oldGeneration == 65535 ? 1 : oldGeneration + 1));
    if (reject) {
        CHECK(!started && actorActive && unbindCalls == 0);
        CHECK(lookups == 0 && fingerprint == 0xABCDEF && matchedMask == 0x55);
        CHECK(runCalls == 0 && hopCalls == 0 && appearCalls == 0);
        return;
    }
    CHECK(misses == 0 && fingerprint == (3976342989u ^ activeSlot) && matchedMask == 192);
    CHECK(hopCalls == (mode == OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN));
    CHECK(runCalls == (mode == OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN));
    CHECK(appearCalls == (mode == OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP));
    if (!hopSucceeds && mode == OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN) {
        CHECK(!started && !actorActive && unbindCalls == 1);
        CHECK(memcmp(&unboundHandle, &acceptedHandle, sizeof(acceptedHandle)) == 0);
        return;
    }
    CHECK(started && actorActive && unbindCalls == 0);
    HarnessProfileLookup(slot); /* A hit must not need to repair erased provenance. */
    CHECK(misses == 0 && hits >= 1 && fingerprint == (3976342989u ^ activeSlot));
}
int main(void)
{
    const int modes[] = {OW_WILD_BEHAVIOR_LOCOMOTION_NONE,
        OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN,
        OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN,
        OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP};
    const int slots[] = {0, OW_WILD_FOLLOWER_SLOT};
    for (unsigned slot = 0; slot < 2; slot++) {
        for (unsigned mode = 0; mode < 4; mode++) {
            RunCase(slots[slot], modes[mode], FALSE, TRUE, 0);
            RunCase(slots[slot], modes[mode], FALSE, TRUE, 65535);
            RunCase(slots[slot], modes[mode], TRUE, TRUE, 5);
        }
        RunCase(slots[slot], OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN, FALSE, FALSE, 5);
    }
    printf("PASS %u spawn-order cases, %u assertions\n", cases, checks);
    return 0;
}
