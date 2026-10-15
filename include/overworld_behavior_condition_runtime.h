#ifndef OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H
#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H

#include "overworld_behavior_conditions.h"
#include "overworld_behavior_resolver.h"
#include "overworld_application_bank.h"
#include "overworld_behavior_resolver_private_call.h"
#include "overworld_wild_behavior_data.h"

#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION 13
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY_ADDR 0x023C22A0
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE_ADDR 0x023C22B8

typedef struct OverworldBehaviorConditionCandidate {
    OverworldWildBehaviorContext context;
    u8 roleMask;
    /* Borrowed, subject-specific native facts refreshed before each reducer
     * call. Zero preserves portable callers' supplied eligible candidates. */
    u8 reserved[3];
} OverworldBehaviorConditionCandidate;

#define OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE (1u << 0)

typedef struct OverworldBehaviorConditionPreparedActor {
    OverworldActorHandle subject;
    /* State storage belongs only to the conditions that match this actor.
     * Host callers can supply it after a sizing pass.  The ROM service
     * allocates missing storage from the world heap. */
    OverworldBehaviorConditionEntryState *states;
    /* The subject retains at most 32 entries. Their source IDs address the
     * full global u16 condition catalog. */
    u16 catalogEntryIndexes[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    u8 count;
    u8 valid;
    u16 stateCapacity;
    /* Private full-species bank identity; no public mask ABI change. */
    u16 subjectSpecies;
    /* Uses the native record's old two-byte tail pad. Cleared with this
     * exact prepared handle by the existing actor lifecycle. */
    u16 subjectDamagePending;
} OverworldBehaviorConditionPreparedActor;

typedef struct OverworldBehaviorConditionScratch {
    /* EvaluatePrepared builds one entry at a time.  These flags retain the
     * bounded per-entry observation needed by the adapter and proof tools. */
    u8 entryFlags[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
} OverworldBehaviorConditionScratch;

#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_ACTIVE    (1u << 0)
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE      (1u << 1)
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED (1u << 2)
/* Transient overall target/provenance change, carried only in entryFlags[0]. */
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED (1u << 3)
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PRESENTATION_ENTERED (1u << 4)
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TIMED_ENDED (1u << 5)
/* Private synchronous WorldView.reservedBinding operation, reset by adapter. */
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO 1u
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING 2u
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_GEOMETRY 3u
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING_NOTICE OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_GEOMETRY
/* Transient visibility mask in WorldView.reserved[1:3]. Actor bits use
 * their current slots; bit15 selects Player. Only moving mode consumes it. */
#define OVERWORLD_BEHAVIOR_CONDITION_NOTICE_PLAYER_MASK 0x8000u

typedef OverworldBehaviorConditionStatus
(*OverworldBehaviorConditionPrepareActorFunc)(
    const void *blobBytes,
    u32 blobSize,
    const OverworldWildBehaviorContext *subjectContext,
    const OverworldActorHandle *subject,
    OverworldBehaviorConditionPreparedActor *prepared);

typedef OverworldBehaviorConditionStatus
(*OverworldBehaviorConditionEvaluatePreparedFunc)(
    const void *blobBytes,
    u32 blobSize,
    OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldBehaviorConditionCandidate *candidates,
    u8 candidateCount,
    u32 chanceSeed,
    OverworldBehaviorConditionScratch *scratch,
    OverworldBehaviorConditionResult *result);

typedef void (*OverworldBehaviorConditionNotifyWorldEffectFunc)(
    OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldActorHandle *subject,
    u32 effect);

typedef struct OverworldBehaviorConditionServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldBehaviorConditionPrepareActorFunc prepareActor;
    OverworldBehaviorConditionEvaluatePreparedFunc evaluatePrepared;
    OverworldBehaviorResolverCallFunc resolverCall;
    OverworldBehaviorConditionNotifyWorldEffectFunc notifyWorldEffect;
} OverworldBehaviorConditionServiceEntry;

typedef const OverworldBehaviorConditionServiceEntry *
(*OverworldBehaviorConditionServiceGetFunc)(void);

#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC 0x4342574F /* OWBC */

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY \
    ((const OverworldBehaviorConditionServiceEntry *) \
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY_ADDR)
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE \
    ((OverworldBehaviorConditionServiceGetFunc) \
        (OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE_ADDR | 1u))
#endif

OverworldBehaviorConditionStatus OverworldBehaviorCondition_PrepareActor(
    const void *blobBytes,
    u32 blobSize,
    const OverworldWildBehaviorContext *subjectContext,
    const OverworldActorHandle *subject,
    OverworldBehaviorConditionPreparedActor *prepared);

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluatePrepared(
    const void *blobBytes,
    u32 blobSize,
    OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldBehaviorConditionCandidate *candidates,
    u8 candidateCount,
    u32 chanceSeed,
    OverworldBehaviorConditionScratch *scratch,
    OverworldBehaviorConditionResult *result);

BOOL OverworldBehaviorCondition_ValidateResolveRequest(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request,
    OverworldApplicationBank *validatedBank);

void OverworldBehaviorCondition_NotifyWorldEffect(
    OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldActorHandle *subject,
    u32 effect);

const OverworldBehaviorConditionServiceEntry *
OverworldBehaviorConditionService_Get(void);

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldBehaviorConditionPreparedActorBudgetMustRemain88Bytes[
    sizeof(OverworldBehaviorConditionPreparedActor) == 88 ? 1 : -1];
typedef char OverworldBehaviorConditionPreparedStatesOffsetMustRemain12[
    offsetof(OverworldBehaviorConditionPreparedActor, states) == 12 ? 1 : -1];
typedef char OverworldBehaviorConditionPreparedCatalogOffsetMustRemain16[
    offsetof(OverworldBehaviorConditionPreparedActor, catalogEntryIndexes) == 16
        ? 1
        : -1];
typedef char OverworldBehaviorConditionPreparedCountOffsetMustRemain80[
    offsetof(OverworldBehaviorConditionPreparedActor, count) == 80 ? 1 : -1];
typedef char OverworldBehaviorConditionPreparedCapacityOffsetMustRemain82[
    offsetof(OverworldBehaviorConditionPreparedActor, stateCapacity) == 82
        ? 1
        : -1];
typedef char OverworldBehaviorConditionScratchBudgetMustRemain32Bytes[
    sizeof(OverworldBehaviorConditionScratch) == 32 ? 1 : -1];
typedef char OverworldBehaviorConditionServiceEntrySizeMustRemain24Bytes[
    sizeof(OverworldBehaviorConditionServiceEntry) == 24 ? 1 : -1];
#endif

#endif // OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H
