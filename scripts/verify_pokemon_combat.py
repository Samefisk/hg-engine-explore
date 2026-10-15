#!/usr/bin/env python3
"""Run the production Pokémon HP adapter with host engine stubs.

This checks HP ownership, limits, hit guards, recycled identities, and the HP
adapter's Crash handoff. The shared movement owner is a stubbed native seam;
this does not prove its reducer, DS encryption, collision, or rendered motion.
"""

from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]

STUBS = r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define OVERWORLD_MOTION_HOST
#include "overworld_motion_model.h"
#define __attribute__(ignored)
typedef int BOOL;
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define SPECIES_NONE 0
#define SPECIES_SHEDINJA 292
#define PERSONAL_BASE_HP 0
#define OVERWORLD_MOUNT_OVERLAY_MAGIC 0x544E554D
#define OVERWORLD_MOUNT_OVERLAY_VERSION 11
#define OVERWORLD_MOUNT_PHASE_RIDING 3
#define OW_WILD_OBJECT_ID_START 0xE0
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED 0
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK 1

enum {
    MON_DATA_PERSONALITY, MON_DATA_SPECIES, MON_DATA_FORM, MON_DATA_LEVEL,
    MON_DATA_IS_EGG, MON_DATA_HP, MON_DATA_MAXHP, TEST_MON_FIELDS
};
typedef struct LocalMapObject { s16 xCurr, yCurr; } LocalMapObject;
struct PartyPokemon { u32 data[TEST_MON_FIELDS]; };
struct Party { int count; struct PartyPokemon members[6]; };
typedef struct SaveData { struct Party party; } SaveData;
typedef struct TestLocation { u16 mapId; } TestLocation;
typedef struct FieldSystem {
    TestLocation *location;
    SaveData *savedata;
} FieldSystem;
typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u32 personality;
    u16 mapId, species;
    u8 form, level, terrain, shiny, active, objectId;
    u16 encounterGeneration;
} OverworldWildSpawn;
typedef struct OverworldWildSpawnState {
    FieldSystem *movementFieldSystem;
    void *movementRuntimeState;
    u16 mapId, mapGeneration;
    u8 activeFollowerPartySlot;
    u8 movementBehaviorClasses[OW_WILD_MAX_SPAWNS];
    u8 movementActorControlModes[OW_WILD_MAX_SPAWNS];
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
} OverworldWildSpawnState;
typedef int OverworldWildSpawnTerrain;
typedef struct OverworldWildRolledEncounter {
    u32 personality;
    u16 species;
    u8 form, level;
} OverworldWildRolledEncounter;
typedef struct OverworldWildResidentData {
    u16 savedHp[OW_WILD_MAX_SPAWNS];
} OverworldWildResidentData;
typedef struct TestWildRuntime {
    OverworldWildResidentData *residentData;
    u8 playerBallCatchValues[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorLimitKeys[OW_WILD_MAX_SPAWNS];
    struct {
        s16 lastKnownX[OW_WILD_MAX_SPAWNS], lastKnownY[OW_WILD_MAX_SPAWNS];
        u16 managerRestoreMask, distanceDespawnPendingMask;
        u8 farSamples[OW_WILD_MAX_SPAWNS];
    } spawnPresentations;
} TestWildRuntime;
#define OW_WILD_RUNTIME(state) ((TestWildRuntime *)(state)->movementRuntimeState)
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
typedef struct OverworldMountOverlayEntry { u32 magic; u16 version, size; }
    OverworldMountOverlayEntry;
typedef struct OverworldMountRuntimeState {
    FieldSystem *fieldSystem;
    struct { u8 phase; } snapshot;
} OverworldMountRuntimeState;
typedef struct OverworldActorPolicyView { u8 motionPhase; }
    OverworldActorPolicyView;
typedef struct OverworldActorStateSnapshot {
    struct { u8 slot; u16 fieldEpoch, mapGeneration, encounterGeneration; } handle;
    u32 subjectIdentity;
    u16 species, reservationId;
    u8 active, role, motionPhase;
} OverworldActorStateSnapshot;
typedef struct OverworldActorRuntimeSlot {
    OverworldActorStateSnapshot snapshot;
    OverworldMotionState motion;
} OverworldActorRuntimeSlot;
typedef struct OverworldActorSystemState {
    u16 fieldEpoch, mapGeneration;
    OverworldActorRuntimeSlot slots[OW_WILD_MAX_SPAWNS];
} OverworldActorSystemState;
typedef struct OverworldActorWalkPolicyCall {
    u16 version, size;
    u8 actorSlot, operation, flags, effect;
    u8 reserved[4];
} OverworldActorWalkPolicyCall;
static BOOL TestCrashOwner(OverworldActorWalkPolicyCall *call);
typedef struct TestPolicy {
    BOOL (*reduceWalk)(OverworldActorWalkPolicyCall *);
} TestPolicy;
static const TestPolicy testPolicy = {TestCrashOwner};
static const struct {
    const TestPolicy *policy;
} testPolicyEntry = {&testPolicy};
static OverworldActorSystemState testActors;
#define OVERWORLD_ACTOR_SYSTEM_STATE_ADDR ((uintptr_t)&testActors)
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&testPolicyEntry)
static FieldSystem *gFieldSysPtr;
static OverworldWildResidentData gOverworldWildResidentData;
static OverworldMountOverlayEntry testMountEntry;
static OverworldMountRuntimeState testMount;
#define OVERWORLD_MOUNT_OVERLAY_ENTRY (&testMountEntry)
#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR ((uintptr_t)&testMount)
static unsigned monWrites, dirtyCalls, locks, unlocks, metadataReads, planCalls;
static u8 policyPhase[OW_WILD_MAX_SPAWNS];
static BOOL planAccepted;
static BOOL actorReady, crashStartAccepted, crashSettleAccepted;
static u16 crashStartIdentity;
static unsigned crashStartCalls, crashSettleCalls, crashPublications;
static unsigned conditionCrashNotifications;
static void OverworldWildConditions_NotifyWorldEffect(
    const OverworldWildSpawnState *state, const void *subject, u32 effect);
static BOOL OverworldActorSystem_IsReady(void) { return actorReady; }
static s16 OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object) { return object->xCurr; }
static s16 OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object) { return object->yCurr; }
static void OverworldWildSpawns_ResetSlotSpotState(OverworldWildSpawnState *state, int slot) {
    assert(state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS);
}
#define OverworldWildSpawns_ClearCachedBehaviorProfile OverworldWildSpawns_ResetSlotSpotState
#define OverworldWildSpawns_ClearMankeyTreeTopCache OverworldWildSpawns_ResetSlotSpotState
#define OverworldWildSpawns_ClearMovementSlotInProgress OverworldWildSpawns_ResetSlotSpotState
static struct Party *SaveData_GetPlayerPartyPtr(SaveData *save) {
    return &save->party;
}
static struct PartyPokemon *Party_GetMonByIndex(struct Party *party, int slot) {
    assert(slot >= 0 && slot < party->count);
    return &party->members[slot];
}
static u32 GetMonData(struct PartyPokemon *pokemon, int attr, void *unused) {
    (void)unused;
    assert(attr >= 0 && attr < TEST_MON_FIELDS);
    return pokemon->data[attr];
}
static void SetMonData(struct PartyPokemon *pokemon, int attr, void *value) {
    assert(attr == MON_DATA_HP);
    pokemon->data[attr] = *(u16 *)value;
    ++monWrites;
}
static BOOL TestAcquireMonLock(struct PartyPokemon *pokemon) {
    assert(pokemon != NULL);
    ++locks;
    return TRUE;
}
static BOOL TestReleaseMonLock(struct PartyPokemon *pokemon, BOOL locked) {
    assert(pokemon != NULL && locked);
    ++unlocks;
    return TRUE;
}
static void OverworldFollowerSelector_SetPartySnapshotDirty(void) {
    ++dirtyCalls;
}
static u32 PokeFormNoPersonalParaGet(u16 species, u8 form, int attr) {
    assert(species != SPECIES_NONE && form <= 1 && attr == PERSONAL_BASE_HP);
    ++metadataReads;
    return 50;
}
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *view) {
    view->motionPhase = policyPhase[slot];
    return TRUE;
}
static BOOL OverworldCombat_Plan(FieldSystem *field, LocalMapObject *object,
    u8 options, u8 direction, OverworldMotionPlan *plan) {
    assert(field == gFieldSysPtr && object != NULL && options != 0 && direction < 4);
    ++planCalls;
    if (!planAccepted) return FALSE;
    *plan = (OverworldMotionPlan){.version = OVERWORLD_MOTION_MODEL_VERSION};
    return TRUE;
}
"""

CASES = r"""
static void OverworldWildConditions_NotifyWorldEffect(
    const OverworldWildSpawnState *state, const void *subject, u32 effect) {
    assert(state != NULL && effect == OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    for (unsigned slot = 0; slot < OW_WILD_MAX_SPAWNS; ++slot) {
        if (subject == &testActors.slots[slot].snapshot.handle) {
            assert(testActors.slots[slot].snapshot.active);
            assert(state->spawns[slot].active);
            assert(testActors.slots[slot].snapshot.handle.mapGeneration == state->mapGeneration);
            ++conditionCrashNotifications;
            return;
        }
    }
    assert(!"condition Crash did not use the accepted actor handle");
}
/* This is a native boundary response, not a copy of the movement reducer.
 * Each case supplies its accepted identity and the resulting native phase. */
static BOOL TestCrashOwner(OverworldActorWalkPolicyCall *call) {
    OverworldActorRuntimeSlot *actor = &testActors.slots[call->actorSlot];
    assert(call->version == OVERWORLD_ACTOR_WALK_POLICY_VERSION);
    assert(call->size == sizeof(*call));
    assert(call->operation == OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH);
    assert(*(u16 *)(void *)&call->reserved[2] == actor->snapshot.handle.fieldEpoch);
    if (call->flags == OVERWORLD_ACTOR_WALK_HIT_CRASH_SETTLE) {
        ++crashSettleCalls;
        assert(*(u16 *)(void *)call->reserved == crashStartIdentity);
        if (!crashSettleAccepted) return FALSE;
        actor->motion.phase = actor->snapshot.motionPhase = OVERWORLD_MOTION_PHASE_IDLE;
        actor->snapshot.reservationId = 0;
        policyPhase[call->actorSlot] = OVERWORLD_MOTION_PHASE_IDLE;
        return TRUE;
    }
    assert(call->flags == OVERWORLD_ACTOR_WALK_HIT_CRASH_START);
    ++crashStartCalls;
    if (!crashStartAccepted) return FALSE;
    call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_CRASH;
    *(u16 *)(void *)call->reserved = crashStartIdentity;
    ++crashPublications;
    actor->motion.phase = actor->snapshot.motionPhase = crashStartIdentity != 0
        ? OVERWORLD_MOTION_PHASE_SUSPENDED : OVERWORLD_MOTION_PHASE_IDLE;
    actor->snapshot.reservationId = crashStartIdentity;
    policyPhase[call->actorSlot] = actor->snapshot.motionPhase;
    return TRUE;
}

static SaveData save;
static TestLocation location;
static FieldSystem field;
static OverworldWildSpawnState wild;
static LocalMapObject objects[OW_WILD_MAX_SPAWNS];
static TestWildRuntime runtime;

static void reset_fixture(void) {
    OverworldCombat_Reset();
    memset(&save, 0, sizeof(save));
    memset(&wild, 0, sizeof(wild));
    memset(&runtime, 0, sizeof(runtime));
    memset(&testMount, 0, sizeof(testMount));
    memset(&testMountEntry, 0, sizeof(testMountEntry));
    memset(&testActors, 0, sizeof(testActors));
    memset(&gOverworldWildResidentData, 0, sizeof(gOverworldWildResidentData));
    memset(policyPhase, 0, sizeof(policyPhase));
    monWrites = dirtyCalls = locks = unlocks = metadataReads = planCalls = 0;
    planAccepted = TRUE;
    actorReady = crashSettleAccepted = TRUE;
    crashStartAccepted = FALSE;
    crashStartIdentity = 41;
    crashStartCalls = crashSettleCalls = crashPublications = 0;
    conditionCrashNotifications = 0;
    testActors.fieldEpoch = 9;
    testActors.mapGeneration = 1;
    location.mapId = 29;
    field = (FieldSystem){&location, &save};
    gFieldSysPtr = &field;
    wild.movementFieldSystem = &field;
    wild.movementRuntimeState = &runtime;
    runtime.residentData = &gOverworldWildResidentData;
    wild.mapId = location.mapId;
    wild.mapGeneration = 1;
    save.party.count = 3;
}

static void spawn(u8 slot, u16 species, u32 personality) {
    OverworldWildRolledEncounter encounter = {
        .personality = personality, .species = species, .level = 5
    };
    OverworldWildSpawns_InitSpawnSlotState(&wild, &field, 0, slot, &objects[slot],
        &encounter, FALSE, 0, 0, 0);
}

static void advance_guard(void) {
    for (unsigned frame = 0; frame < 60; ++frame) OverworldCombat_BeginFrame(&wild);
}

static OverworldActorRuntimeSlot *bind_actor(u8 slot, u8 role) {
    OverworldActorRuntimeSlot *actor = &testActors.slots[slot];
    const OverworldWildSpawn *subject = &wild.spawns[slot];
    actor->snapshot.handle.slot = slot;
    actor->snapshot.handle.fieldEpoch = testActors.fieldEpoch;
    actor->snapshot.handle.mapGeneration = wild.mapGeneration;
    actor->snapshot.handle.encounterGeneration = subject->encounterGeneration;
    actor->snapshot.subjectIdentity = subject->personality;
    actor->snapshot.species = subject->species;
    actor->snapshot.active = TRUE;
    actor->snapshot.role = role;
    actor->snapshot.motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
    actor->snapshot.reservationId = crashStartIdentity;
    actor->motion.phase = OVERWORLD_MOTION_PHASE_MOVING;
    actor->motion.plan = (OverworldMotionPlan){
        .version = OVERWORLD_MOTION_MODEL_VERSION,
        .kind = OVERWORLD_MOTION_KIND_SKID,
        .fieldEpoch = testActors.fieldEpoch,
        .reservationId = crashStartIdentity,
        .startX = 8, .startY = 9, .startBaseY = 100
    };
    policyPhase[slot] = OVERWORLD_MOTION_PHASE_MOVING;
    crashStartAccepted = TRUE;
    return actor;
}

static void prepare_crash_fixture(u8 options) {
    reset_fixture();
    spawn(0, 55, 0x3F);
    bind_actor(0, OVERWORLD_ACTOR_ROLE_WILD);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, 0, 1, options, 0));
    assert(crashStartCalls == 1 && crashPublications == 1);
    assert(sCombat.targets[0].crashMotionIdentity == 41);
}

static void check_wild_limits_and_guards(void) {
    u16 hp, maxHp;
    OverworldMotionPlan plan;
    reset_fixture();
    spawn(0, 55, 0x3F); /* IV31 gives max HP21 at level5/base50. */
    spawn(1, 55, 0x40); /* IV0 gives max HP20. */
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 21 && maxHp == 21);
    assert(OverworldCombat_ReadHp(&wild, 1, &hp, &maxHp) && hp == 20 && maxHp == 20);
    for (unsigned read = 0; read < 5; ++read) {
        assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp));
    }
    assert(metadataReads == 2); /* Per-encounter cache, no repeated stat reads. */
    assert(!OverworldCombat_TryHit(&wild, 0, 0, 0, 0));
    assert(!OverworldCombat_TryHit(&wild, 0, 51, 0, 0));
    assert(!OverworldCombat_TryHit(&wild, 10, 20, 0, 0));
    assert(OverworldCombat_TryHit(&wild, 0, 50, 0, 0));
    assert(gOverworldWildResidentData.savedHp[0] == 11);
    assert(sCombat.targets[0].lastDamage == 10 && sCombat.targets[0].hitCount == 1);
    assert(!OverworldCombat_TryHit(&wild, 0, 50, 0, 0));
    assert(OverworldCombat_TryHit(&wild, 1, 50, 0, 0)); /* Separate target guard. */
    assert(gOverworldWildResidentData.savedHp[1] == 10);
    for (unsigned frame = 0; frame < 59; ++frame) {
        OverworldCombat_BeginFrame(&wild);
        assert(!OverworldCombat_TryHit(&wild, 0, 50, 0, 0));
    }
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, 0, 50, 0, 0));
    assert(gOverworldWildResidentData.savedHp[0] == 1);
    advance_guard();
    assert(OverworldCombat_TryHit(&wild, 0, 50, 0, 0));
    assert(gOverworldWildResidentData.savedHp[0] == 0);
    assert(sCombat.targets[0].lastDamage == 1);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 0);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_FAINTED);

    /* New native publication replaces the fainted encounter and its hit guard. */
    spawn(0, 55, 0x60);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 20);
    assert(sCombat.targets[0].hitCount == 0 && sCombat.targets[0].lastDamage == 0);
    assert(sCombat.targets[0].immunityFrames == 0 && !sCombat.targets[0].knockbackPending);
    assert(OverworldCombat_TryHit(&wild, 0, 1, 0, 0));
}

static void check_reused_slot_and_presentation_hp(void) {
    u16 hp, maxHp;
    u16 oldGeneration;
    OverworldMotionPlan plan;
    reset_fixture();
    spawn(0, 55, 0x3F);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 21);
    assert(OverworldCombat_TryHit(&wild, 0, 2, 0, 0));
    assert(gOverworldWildResidentData.savedHp[0] == 19);
    oldGeneration = wild.spawns[0].encounterGeneration;
    /* Measured failure: publication reused the prior resident's numeric HP. */
    spawn(0, 55, 0x40);
    assert(wild.spawns[0].encounterGeneration != oldGeneration);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 20 && maxHp == 20);
    assert(sCombat.targets[0].hitCount == 0 && sCombat.targets[0].lastDamage == 0);
    assert(sCombat.targets[0].immunityFrames == 0 && !sCombat.targets[0].knockbackPending);

    /* Presentation rebind and cache reload retain numeric HP, including zero. */
    assert(OverworldCombat_TryHit(&wild, 0, 3, 0, 0));
    ++wild.mapGeneration;
    wild.spawns[0].object = &objects[1];
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 17);
    OverworldCombat_Reset();
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 17);
    gOverworldWildResidentData.savedHp[0] = 7; /* Native battle-flee write. */
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 7);
    assert(OverworldCombat_TryHit(&wild, 0, 50, 0, 0));
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 0);
    ++wild.mapGeneration;
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 0);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_FAINTED);
    OverworldCombat_Reset();
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 0);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_FAINTED);
}

static void check_map_rebind_stat_reuse(void) {
    static const u16 species[7] = {95, 163, 95, 74, 74, 70, 143};
    u16 hp, maxHp;
    reset_fixture();
    for (u8 slot = 0; slot < 7; ++slot) {
        spawn(slot, species[slot], 0x3F + 32 * slot);
        assert(OverworldCombat_ReadHp(&wild, slot, &hp, &maxHp));
        assert(hp == 21 && maxHp == 21);
        gOverworldWildResidentData.savedHp[slot] = slot == 6 ? 0
            : slot == 5 ? 25 : 10 + slot;
        sCombat.targets[slot].immunityFrames = 19;
        sCombat.targets[slot].knockbackPending = TRUE;
        sCombat.targets[slot].hitCount = 3;
        sCombat.targets[slot].lastDamage = 2;
    }
    assert(metadataReads == 7);
    location.mapId = wild.mapId = 67;
    ++wild.mapGeneration;
    for (u8 slot = 0; slot < 7; ++slot) wild.spawns[slot].mapId = 67;
    OverworldCombat_BeginFrame(&wild);
    for (u8 slot = 0; slot < 7; ++slot) {
        assert(!sCombat.targets[slot].initialized);
        assert(sCombat.targets[slot].immunityFrames == 0);
        assert(!sCombat.targets[slot].knockbackPending);
        assert(OverworldCombat_ReadHp(&wild, slot, &hp, &maxHp));
        assert(hp == (slot == 6 ? 0 : slot == 5 ? 21 : 10 + slot));
        assert(maxHp == 21 && gOverworldWildResidentData.savedHp[slot] == hp);
        assert(Combat_Matches(&sCombat.targets[slot], &wild, slot));
        assert(sCombat.targets[slot].mapId == 67);
        assert(sCombat.targets[slot].mapGeneration == wild.mapGeneration);
        assert(sCombat.targets[slot].hitCount == 0 && sCombat.targets[slot].lastDamage == 0);
    }
    fprintf(stderr, "Map-rebind personal reads: %u (expected seven total).\n", metadataReads);
    assert(metadataReads == 7); /* Seven retained Wild must not reload personal data. */
    puts("Map-only rebind: seven current Wild reused stats, retained/clamped HP, and reset combat.");
}

static void check_stat_reuse_boundaries(void) {
    u16 hp, maxHp;
    for (unsigned changed = 0; changed < 7; ++changed) {
        reset_fixture();
        spawn(0, 55, 0x3F);
        assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp));
        assert(metadataReads == 1);
        switch (changed) {
        case 0: ++wild.spawns[0].personality; break;
        case 1: ++wild.spawns[0].species; break;
        case 2: ++wild.spawns[0].form; break;
        case 3: ++wild.spawns[0].level; break;
        case 4: ++wild.spawns[0].encounterGeneration; break;
        case 5: sCombat.targets[0].maxHp = 0; break;
        case 6: OverworldCombat_Reset(); break;
        }
        sCombat.targets[0].immunityFrames = 19;
        sCombat.targets[0].knockbackPending = TRUE;
        sCombat.targets[0].hitCount = 3;
        gOverworldWildResidentData.savedHp[0] = 0;
        OverworldCombat_BeginFrame(&wild);
        assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp));
        assert(metadataReads == 2 && hp == 0 && maxHp != 0);
        assert(Combat_Matches(&sCombat.targets[0], &wild, 0));
        assert(sCombat.targets[0].personality == wild.spawns[0].personality);
        assert(sCombat.targets[0].encounterGeneration == wild.spawns[0].encounterGeneration);
        assert(sCombat.targets[0].species == wild.spawns[0].species);
        assert(sCombat.targets[0].form == wild.spawns[0].form);
        assert(sCombat.targets[0].level == wild.spawns[0].level);
        if (changed != 5) {
            assert(sCombat.targets[0].immunityFrames == 0);
            assert(!sCombat.targets[0].knockbackPending);
            assert(sCombat.targets[0].hitCount == 0);
        }
    }
    for (unsigned invalid = 0; invalid < 9; ++invalid) {
        OverworldCombatTarget cached;
        reset_fixture();
        spawn(0, 55, 0x3F);
        assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp));
        cached = sCombat.targets[0];
        switch (invalid) {
        case 0: wild.movementFieldSystem = NULL; break;
        case 1: gFieldSysPtr = NULL; break;
        case 2: field.savedata = NULL; break;
        case 3: ++location.mapId; break;
        case 4: wild.mapGeneration = 0; break;
        case 5: wild.spawns[0].active = FALSE; break;
        case 6: wild.spawns[0].encounterGeneration = 0; break;
        case 7: wild.spawns[0].species = SPECIES_NONE; break;
        case 8: wild.spawns[0].level = 0; break;
        }
        hp = maxHp = 777;
        assert(!OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp));
        assert(metadataReads == 1 && hp == 777 && maxHp == 777);
        assert(memcmp(&cached, &sCombat.targets[0], sizeof(cached)) == 0);
    }
    puts("Stat reuse rejects every changed tuple/encounter or empty cache; current-owner guards stay strict.");
}

static void check_party_owner_and_faint(void) {
    struct PartyPokemon *pokemon;
    u16 hp, maxHp;
    OverworldMotionPlan plan;
    reset_fixture();
    spawn(OW_WILD_FOLLOWER_SLOT, 55, 99);
    wild.activeFollowerPartySlot = 2;
    pokemon = &save.party.members[2];
    pokemon->data[MON_DATA_PERSONALITY] = 99;
    pokemon->data[MON_DATA_SPECIES] = 55;
    pokemon->data[MON_DATA_LEVEL] = 5;
    pokemon->data[MON_DATA_HP] = 33;
    pokemon->data[MON_DATA_MAXHP] = 40;
    save.party.members[1].data[MON_DATA_HP] = 100;
    gOverworldWildResidentData.savedHp[OW_WILD_FOLLOWER_SLOT] = 777;
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, OW_WILD_FOLLOWER_SLOT, &hp, &maxHp)
        && hp == 33 && maxHp == 40);
    assert(OverworldCombat_TryHit(&wild, OW_WILD_FOLLOWER_SLOT, 50, 0, 0));
    assert(pokemon->data[MON_DATA_HP] == 13 && monWrites == 1 && dirtyCalls == 1);
    assert(gOverworldWildResidentData.savedHp[OW_WILD_FOLLOWER_SLOT] == 777);
    assert(save.party.members[1].data[MON_DATA_HP] == 100);
    assert(!OverworldCombat_TryHit(&wild, OW_WILD_FOLLOWER_SLOT, 50, 0, 0));
    ++wild.spawns[OW_WILD_FOLLOWER_SLOT].encounterGeneration;
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, OW_WILD_FOLLOWER_SLOT, 50, 0, 0));
    assert(pokemon->data[MON_DATA_HP] == 0 && monWrites == 2);
    assert(OverworldCombat_Prepare(&wild, OW_WILD_FOLLOWER_SLOT, &plan)
        == OVERWORLD_COMBAT_FAINTED);
    assert(locks == unlocks);

    pokemon->data[MON_DATA_HP] = 33;
    pokemon->data[MON_DATA_PERSONALITY] = 100; /* Stale party-slot identity. */
    assert(!OverworldCombat_ReadHp(&wild, OW_WILD_FOLLOWER_SLOT, &hp, &maxHp));
    assert(!OverworldCombat_TryHit(&wild, OW_WILD_FOLLOWER_SLOT, 20, 0, 0));
    assert(pokemon->data[MON_DATA_HP] == 33 && monWrites == 2);
}

static void check_shedinja_and_pending_motion(void) {
    u16 hp, maxHp;
    OverworldMotionPlan plan;
    u8 jump = OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(OW_WILD_BEHAVIOR_KNOCKBACK_JUMP, 3);
    reset_fixture();
    spawn(0, SPECIES_SHEDINJA, 0x3F);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_ReadHp(&wild, 0, &hp, &maxHp) && hp == 1 && maxHp == 1);
    assert(OverworldCombat_TryHit(&wild, 0, 50, jump, 0));
    assert(sCombat.targets[0].lastDamage == 1 && !sCombat.targets[0].knockbackPending);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_FAINTED);

    reset_fixture();
    spawn(0, 55, 0x3F);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, 0, 1, jump, 0));
    policyPhase[0] = OVERWORLD_MOTION_PHASE_MOVING;
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_KNOCKBACK);
    assert(plan.version == 0 && planCalls == 0 && sCombat.targets[0].knockbackPending);
    policyPhase[0] = OVERWORLD_MOTION_PHASE_IDLE;
    planAccepted = FALSE;
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_KNOCKBACK);
    assert(plan.version == 0 && sCombat.targets[0].knockbackPending);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(!sCombat.targets[0].knockbackPending);
    advance_guard();
    planAccepted = TRUE;
    assert(OverworldCombat_TryHit(&wild, 0, 1, jump, 0));
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_KNOCKBACK);
    assert(plan.version == OVERWORLD_MOTION_MODEL_VERSION);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(!sCombat.targets[0].knockbackPending);
}

static void check_crash_without_knockback_and_dedup(void) {
    OverworldMotionPlan plan;
    prepare_crash_fixture(0);
    assert(sCombat.targets[0].knockbackPending == OVERWORLD_COMBAT_PENDING_SETTLE);
    assert(sCombat.targets[0].currentHp == 20 && sCombat.targets[0].hitCount == 1);
    assert(!OverworldCombat_TryHit(&wild, 0, 1, 0, 0));
    OverworldCombat_AcceptedHit(&wild, 0); /* Rider + mount receipt must deduplicate. */
    assert(crashStartCalls == 1 && crashPublications == 1);
    assert(conditionCrashNotifications == 1);
    assert(OverworldCombat_Prepare(&wild, OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_CRASH_SETTLE);
    assert(OverworldCombat_Prepare(&wild, OVERWORLD_COMBAT_PROBE_URGENT, &plan)
        == OVERWORLD_COMBAT_NONE); /* Urgent probes cannot hand off a plan. */
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_CRASH_SETTLE);
    assert(plan.reservationId == 41 && plan.fieldEpoch == testActors.fieldEpoch);
    assert(plan.startX == 8 && plan.startY == 9 && plan.startBaseY == 100);
    crashSettleAccepted = FALSE;
    OverworldCombat_Acknowledge(&wild, 0);
    assert(crashSettleCalls == 1);
    assert(sCombat.targets[0].knockbackPending == OVERWORLD_COMBAT_PENDING_SETTLE);
    crashSettleAccepted = TRUE;
    OverworldCombat_Acknowledge(&wild, 0);
    assert(crashSettleCalls == 2 && crashPublications == 1);
    assert(conditionCrashNotifications == 1);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_CRASH_PLAYING);
    assert(planCalls == 0 && sCombat.targets[0].knockbackPending == OVERWORLD_COMBAT_PENDING_CRASH);
    OverworldCombat_Acknowledge(&wild, 0); /* Only the adapter ends presentation. */
    assert(!sCombat.targets[0].knockbackPending);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_NONE);
    assert(planCalls == 0 && crashPublications == 1);
}

static void check_crash_preserves_queued_knockback(void) {
    OverworldMotionPlan plan;
    u8 jump = OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(OW_WILD_BEHAVIOR_KNOCKBACK_JUMP, 3);
    prepare_crash_fixture(jump);
    assert(sCombat.targets[0].knockbackPending
        == (OVERWORLD_COMBAT_PENDING_SETTLE | OVERWORLD_COMBAT_PENDING_KNOCKBACK));
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_CRASH_SETTLE);
    assert(planCalls == 0);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_CRASH_PLAYING);
    assert(planCalls == 0 && (sCombat.targets[0].knockbackPending
        & OVERWORLD_COMBAT_PENDING_KNOCKBACK) != 0);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(sCombat.targets[0].knockbackPending == OVERWORLD_COMBAT_PENDING_KNOCKBACK);
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_KNOCKBACK);
    assert(planCalls == 1 && plan.version == OVERWORLD_MOTION_MODEL_VERSION);
    assert(sCombat.targets[0].knockbackOptions == jump);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(!sCombat.targets[0].knockbackPending && crashPublications == 1);
}

static void check_stale_crash_receipts(void) {
    u8 jump = OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(OW_WILD_BEHAVIOR_KNOCKBACK_JUMP, 3);
    for (unsigned fault = 0; fault < 8; ++fault) {
        OverworldActorRuntimeSlot *actor;
        prepare_crash_fixture(jump);
        actor = &testActors.slots[0];
        switch (fault) {
        case 0: ++actor->snapshot.reservationId; break;
        case 1: ++actor->motion.plan.reservationId; break;
        case 2: ++actor->motion.plan.fieldEpoch; break;
        case 3: ++actor->snapshot.handle.fieldEpoch; break;
        case 4: actor->snapshot.role = OVERWORLD_ACTOR_ROLE_SCRIPTED; break;
        case 5: actor->snapshot.motionPhase = OVERWORLD_MOTION_PHASE_MOVING; break;
        case 6: actor->motion.phase = OVERWORLD_MOTION_PHASE_MOVING; break;
        case 7: ++location.mapId; break;
        }
        OverworldCombat_Acknowledge(&wild, 0);
        assert(crashSettleCalls == 0); /* No ground command for a stale receipt. */
        assert((sCombat.targets[0].knockbackPending & OVERWORLD_COMBAT_PENDING_SETTLE) != 0);
        assert(OverworldCombat_Prepare(&wild, OVERWORLD_COMBAT_PROBE_URGENT, NULL)
            == OVERWORLD_COMBAT_NONE);
        assert(sCombat.targets[0].knockbackPending == OVERWORLD_COMBAT_PENDING_KNOCKBACK);
        assert(sCombat.targets[0].crashMotionIdentity == 0 && crashPublications == 1);
        assert(planCalls == 0);
    }
    prepare_crash_fixture(jump);
    ++wild.spawns[0].encounterGeneration;
    OverworldCombat_BeginFrame(&wild);
    assert(!sCombat.targets[0].knockbackPending); /* A replacement owns no old Crash. */
    assert(OverworldCombat_Prepare(&wild, OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_NONE);
    assert(crashSettleCalls == 0);
}

static void check_due_crash_and_fatal_hit(void) {
    OverworldMotionPlan plan;
    reset_fixture();
    spawn(0, 55, 0x3F);
    crashStartIdentity = 0; /* Owner accepted a due skid without an old motion. */
    bind_actor(0, OVERWORLD_ACTOR_ROLE_WILD);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, 0, 1, 0, 0));
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_CRASH_SETTLE);
    assert(plan.version == 0 && sCombat.targets[0].crashMotionIdentity == 0);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(crashSettleCalls == 0); /* Zero receipt cannot cancel a native motion. */
    assert(OverworldCombat_Prepare(&wild, 0, &plan) == OVERWORLD_COMBAT_CRASH_PLAYING);
    OverworldCombat_Acknowledge(&wild, 0);
    assert(!sCombat.targets[0].knockbackPending && crashPublications == 1);

    reset_fixture();
    spawn(0, 55, 0x3F);
    crashStartIdentity = 0;
    bind_actor(0, OVERWORLD_ACTOR_ROLE_WILD);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, 0, 1, 0, 0));
    testActors.slots[0].snapshot.reservationId = 90;
    testActors.slots[0].snapshot.motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
    OverworldCombat_Acknowledge(&wild, 0);
    assert(crashSettleCalls == 0);
    assert(sCombat.targets[0].knockbackPending == OVERWORLD_COMBAT_PENDING_SETTLE);
    assert(OverworldCombat_Prepare(&wild, OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_NONE);
    assert(!sCombat.targets[0].knockbackPending);

    reset_fixture();
    spawn(0, SPECIES_SHEDINJA, 0x3F);
    bind_actor(0, OVERWORLD_ACTOR_ROLE_WILD);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, 0, 1, 0, 0));
    assert(crashStartCalls == 0 && crashPublications == 0);
    assert(OverworldCombat_Prepare(&wild, 0, NULL) == OVERWORLD_COMBAT_FAINTED);
    assert(OverworldCombat_Prepare(&wild, OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_NONE);
}

static void check_mounted_latch_and_urgent_reads(void) {
    const u8 slot = OW_WILD_FOLLOWER_SLOT;
    struct PartyPokemon *pokemon;
    unsigned priorLocks;
    reset_fixture();
    spawn(slot, 55, 99);
    wild.activeFollowerPartySlot = 2;
    pokemon = &save.party.members[2];
    pokemon->data[MON_DATA_PERSONALITY] = 99;
    pokemon->data[MON_DATA_SPECIES] = 55;
    pokemon->data[MON_DATA_LEVEL] = 5;
    pokemon->data[MON_DATA_HP] = 33;
    pokemon->data[MON_DATA_MAXHP] = 40;
    testMountEntry = (OverworldMountOverlayEntry){OVERWORLD_MOUNT_OVERLAY_MAGIC,
        OVERWORLD_MOUNT_OVERLAY_VERSION, sizeof(testMountEntry)};
    testMount.fieldSystem = &field;
    testMount.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    bind_actor(slot, OVERWORLD_ACTOR_ROLE_MOUNTED);
    OverworldCombat_BeginFrame(&wild);
    assert(OverworldCombat_TryHit(&wild, slot, 1, 0, 0));
    assert(OverworldCombat_MountedCrashPending(&field));
    OverworldCombat_AcceptedHit(&wild, slot);
    assert(crashStartCalls == 1 && crashPublications == 1);
    priorLocks = locks;
    assert(OverworldCombat_Prepare(&wild, slot | OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_CRASH_SETTLE);
    assert(locks == priorLocks); /* No native party work on the urgent phase path. */
    OverworldCombat_Acknowledge(&wild, slot);
    assert(OverworldCombat_MountedCrashPending(&field));
    assert(OverworldCombat_Prepare(&wild, slot | OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_CRASH_PLAYING);
    OverworldCombat_Acknowledge(&wild, slot);
    assert(!OverworldCombat_MountedCrashPending(&field));
    pokemon->data[MON_DATA_HP] = 0;
    priorLocks = locks;
    assert(OverworldCombat_Prepare(&wild, slot | OVERWORLD_COMBAT_PROBE_URGENT, NULL)
        == OVERWORLD_COMBAT_NONE);
    assert(locks == priorLocks);
    assert(OverworldCombat_Prepare(&wild, slot, NULL) == OVERWORLD_COMBAT_FAINTED);
    assert(locks == priorLocks + 1 && locks == unlocks);
    assert(!OverworldCombat_MountedCrashPending(NULL));
}

int main(void) {
    check_wild_limits_and_guards();
    check_reused_slot_and_presentation_hp();
    check_map_rebind_stat_reuse();
    check_stat_reuse_boundaries();
    check_party_owner_and_faint();
    check_shedinja_and_pending_motion();
    check_crash_without_knockback_and_dedup();
    check_crash_preserves_queued_knockback();
    check_stale_crash_receipts();
    check_due_crash_and_fatal_hit();
    check_mounted_latch_and_urgent_reads();
    puts("Production Pokemon HP and Crash handoff checks passed (native owner stubbed).");
    return 0;
}
"""


def production_source() -> str:
    source = (ROOT / "src/player_health_pokemon.c").read_text()
    source = source[:source.index("static int COMBAT_CODE Combat_BattleTargetSlot")]
    source = re.sub(r'^#include[^\n]*\n', '', source, flags=re.MULTILINE)
    for name, stub in (
        ("COMBAT_ACQUIRE_MON_LOCK", "TestAcquireMonLock"),
        ("COMBAT_RELEASE_MON_LOCK", "TestReleaseMonLock"),
    ):
        source, count = re.subn(rf'^#define {name}[^\n]*', f'#define {name} {stub}',
                               source, flags=re.MULTILINE)
        if count != 1:
            raise ValueError(f"Native boundary changed: {name}")
    return source


def spawn_publication_source() -> str:
    source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    start = source.index("static void OverworldWildSpawns_InitSpawnSlotState(")
    end = source.index("static void OverworldWildSpawns_StartSpawnAppearHop(", start)
    return source[start:end]


def profile_constants() -> str:
    source = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    lines = source.splitlines(keepends=True)
    selected = []
    continuation = False
    for line in lines:
        if line.startswith("#define OW_WILD_BEHAVIOR_KNOCKBACK_") or continuation:
            selected.append(line)
            continuation = line.rstrip().endswith("\\")
    resident = (ROOT / "include/overworld_wild_spawns_internal.h").read_text()
    selected.extend(re.findall(r'^#define OW_WILD_HP_UNINITIALIZED[^\n]*\n',
                              resident, re.MULTILINE))
    combat = (ROOT / "include/overworld_combat.h").read_text()
    selected.extend(re.findall(r'^#define OVERWORLD_COMBAT_(?:NONE|KNOCKBACK|FAINTED|CRASH_[A-Z_]+|MOUNT_[A-Z_]+|PENDING_[A-Z_]+|PROBE_URGENT)[^\n]*\n',
                              combat, re.MULTILINE))
    movement = (ROOT / "include/overworld_wild_movement.h").read_text()
    selected.extend(re.findall(r'^#define OVERWORLD_ACTOR_WALK_(?:POLICY_VERSION|HIT_CRASH_[A-Z_]+)[^\n]*\n',
                              movement, re.MULTILINE))
    actor = (ROOT / "include/overworld_actor_system.h").read_text()
    for source, names in (
        (movement, ("OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH",)),
        (actor, ("OVERWORLD_ACTOR_ROLE_WILD", "OVERWORLD_ACTOR_ROLE_FOLLOWER",
                 "OVERWORLD_ACTOR_ROLE_MOUNTED", "OVERWORLD_ACTOR_ROLE_SCRIPTED",
                 "OVERWORLD_ACTOR_WORLD_EFFECT_CRASH")),
    ):
        for name in names:
            match = re.search(rf'\b{name}\s*=\s*(\d+)\s*,', source)
            if match is None:
                raise ValueError(f"Native constant changed: {name}")
            selected.append(f"#define {name} {match[1]}\n")
    return "".join(selected)


def main() -> None:
    production = production_source()
    publication = spawn_publication_source()
    hp_marker = "OW_WILD_RUNTIME(state)->residentData->savedHp[slot] = OW_WILD_HP_UNINITIALIZED;"
    zero_faint = "if (currentHp > maximumHp) {"
    if production.count(zero_faint) != 1 or publication.count(hp_marker) != 1:
        raise ValueError("Production HP lifecycle changed")
    faint_negative = production.replace(zero_faint,
        "if (currentHp == 0 || currentHp > maximumHp) {", 1)
    receipt_guard = "actor->reservationId != target->crashMotionIdentity"
    if production.count(receipt_guard) != 1:
        raise ValueError("Production Crash receipt guard changed")
    with tempfile.TemporaryDirectory(prefix="pokemon-combat-") as temporary:
        directory = Path(temporary)
        for label, module, lifecycle in (
            ("production", production, publication),
            ("cap-negative", production.replace("hitLimit = maxHp / 2;",
                                                 "hitLimit = maxHp;", 1), publication),
            ("reuse-negative", production, publication.replace(hp_marker, "", 1)),
            ("faint-negative", faint_negative, publication),
            ("crash-identity-negative", production.replace(receipt_guard, "FALSE", 1),
             publication),
        ):
            if label != "production" and module == production and lifecycle == publication:
                raise ValueError(f"Mutation did not match production source: {label}")
            source = directory / f"{label}.c"
            binary = directory / label
            source.write_text(STUBS + profile_constants() + module + lifecycle + CASES)
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "include"), str(source), "-o", str(binary)],
                           check=True)
            if label == "production":
                subprocess.run([str(binary)], check=True)
            else:
                result = subprocess.run([str(binary)], capture_output=True)
                if result.returncode == 0:
                    raise AssertionError(f"Host proof accepted broken production rule: {label}")
                print(f"Negative production mutation rejected: {label}.")


if __name__ == "__main__":
    main()
