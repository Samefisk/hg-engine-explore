#ifndef OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H
#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H

#include "overworld_behavior_conditions.h"
#include "overworld_behavior_resolver.h"
#include "overworld_wild_behavior_data.h"

#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION 8
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY_ADDR 0x023C22A0
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE_ADDR 0x023C22B8

typedef struct OverworldBehaviorConditionCandidate {
    OverworldWildBehaviorContext context;
    u8 roleMask;
    u8 reserved[3];
} OverworldBehaviorConditionCandidate;

typedef struct OverworldBehaviorConditionPreparedActor {
    OverworldActorHandle subject;
    /* State storage belongs only to the conditions that match this actor.
     * Host callers can supply it after a sizing pass.  The ROM service
     * allocates missing storage from the world heap. */
    OverworldBehaviorConditionEntryState *states;
    /* The whole catalog is capped at 32 entries, so one byte identifies a
     * prepared source entry without narrowing the authored limit. */
    u8 catalogEntryIndexes[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    u8 count;
    u8 valid;
    u16 stateCapacity;
} OverworldBehaviorConditionPreparedActor;

typedef struct OverworldBehaviorConditionScratch {
    /* EvaluatePrepared builds one entry at a time.  These flags retain the
     * bounded per-entry observation needed by the adapter and proof tools. */
    u8 entryFlags[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
} OverworldBehaviorConditionScratch;

#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_ACTIVE    (1u << 0)
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE      (1u << 1)
#define OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED (1u << 2)

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

typedef BOOL (*OverworldBehaviorConditionValidateResolveRequestFunc)(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request);

typedef struct OverworldBehaviorConditionServiceEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldBehaviorConditionPrepareActorFunc prepareActor;
    OverworldBehaviorConditionEvaluatePreparedFunc evaluatePrepared;
    OverworldBehaviorConditionValidateResolveRequestFunc validateResolveRequest;
    u32 reserved;
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
    const BehaviorResolveRequest *request);

const OverworldBehaviorConditionServiceEntry *
OverworldBehaviorConditionService_Get(void);

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldBehaviorConditionPreparedActorBudgetMustRemain52Bytes[
    sizeof(OverworldBehaviorConditionPreparedActor) == 52 ? 1 : -1];
typedef char OverworldBehaviorConditionPreparedStatesOffsetMustRemain12[
    offsetof(OverworldBehaviorConditionPreparedActor, states) == 12 ? 1 : -1];
typedef char OverworldBehaviorConditionPreparedCatalogOffsetMustRemain16[
    offsetof(OverworldBehaviorConditionPreparedActor, catalogEntryIndexes) == 16
        ? 1
        : -1];
typedef char OverworldBehaviorConditionPreparedCountOffsetMustRemain48[
    offsetof(OverworldBehaviorConditionPreparedActor, count) == 48 ? 1 : -1];
typedef char OverworldBehaviorConditionPreparedCapacityOffsetMustRemain50[
    offsetof(OverworldBehaviorConditionPreparedActor, stateCapacity) == 50
        ? 1
        : -1];
typedef char OverworldBehaviorConditionScratchBudgetMustRemain32Bytes[
    sizeof(OverworldBehaviorConditionScratch) == 32 ? 1 : -1];
typedef char OverworldBehaviorConditionServiceEntrySizeMustRemain24Bytes[
    sizeof(OverworldBehaviorConditionServiceEntry) == 24 ? 1 : -1];
#endif

#endif // OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H
