#ifndef OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H
#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H

#include "overworld_behavior_conditions.h"
#include "overworld_behavior_resolver.h"
#include "overworld_wild_behavior_data.h"

#define OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION 2
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY_ADDR 0x023C22A0

typedef struct OverworldBehaviorConditionCandidate {
    OverworldWildBehaviorContext context;
    u8 roleMask;
    u8 reserved[3];
} OverworldBehaviorConditionCandidate;

typedef struct OverworldBehaviorConditionPreparedActor {
    OverworldActorHandle subject;
    OverworldBehaviorConditionEntryState
        states[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    u16 catalogEntryIndexes[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    u8 count;
    u8 valid;
    u16 reserved;
} OverworldBehaviorConditionPreparedActor;

typedef struct OverworldBehaviorConditionScratch {
    OverworldBehaviorConditionDefinition
        definitions[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    OverworldBehaviorConditionEntryInput
        inputs[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    OverworldBehaviorConditionEntryResult
        entryResults[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
} OverworldBehaviorConditionScratch;

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
} OverworldBehaviorConditionServiceEntry;

#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC 0x4342574F /* OWBC */

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY \
    ((const OverworldBehaviorConditionServiceEntry *) \
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY_ADDR)
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

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldBehaviorConditionPreparedActorBudgetMustRemain848Bytes[
    sizeof(OverworldBehaviorConditionPreparedActor) == 848 ? 1 : -1];
typedef char OverworldBehaviorConditionScratchBudgetMustRemain1408Bytes[
    sizeof(OverworldBehaviorConditionScratch) == 1408 ? 1 : -1];
typedef char OverworldBehaviorConditionServiceEntrySizeMustRemain20Bytes[
    sizeof(OverworldBehaviorConditionServiceEntry) == 20 ? 1 : -1];
#endif

#endif // OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_H
