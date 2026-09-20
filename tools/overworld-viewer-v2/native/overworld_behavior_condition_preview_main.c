#include "../../../include/overworld_behavior_condition_runtime.h"

#include <stdio.h>
#include <string.h>

#define HOST_TRACE_CAPACITY 96
#define PREVIEW_HEADER_VALUES 23
#define PREVIEW_CANDIDATE_VALUES 15
#define PREVIEW_STATE_VALUES 7
#define HOST_REQUEST_VERSION 2

extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static void PrintHex(const void *bytes, size_t size)
{
    static const char digits[] = "0123456789abcdef";
    const unsigned char *cursor = bytes;
    size_t i;

    for (i = 0; i < size; i++) {
        putchar(digits[cursor[i] >> 4]);
        putchar(digits[cursor[i] & 15]);
    }
}

static void CopyTarget(
    const OverworldBehaviorConditionTargetReference *source,
    BehaviorResolveTargetReference *target)
{
    memset(target, 0, sizeof(*target));
    target->kind = source->kind;
    target->actorSlot = source->actor.slot;
    target->actorGeneration = source->actor.generation;
    target->fieldEpoch = source->actor.fieldEpoch;
    target->mapGeneration = source->actor.mapGeneration;
    target->encounterGeneration = source->actor.encounterGeneration;
    target->actorReserved = source->actor.reserved;
}

static int ReadValues(long long *values, int count)
{
    int i;

    for (i = 0; i < count; i++) {
        if (scanf("%lld", &values[i]) != 1) {
            return 0;
        }
    }
    return 1;
}

static int FindPreparedCondition(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldBehaviorConditionPreparedActor *prepared,
    u16 conditionId)
{
    int i;

    for (i = 0; i < prepared->count; i++) {
        u16 sourceIndex = prepared->catalogEntryIndexes[i];

        if (sourceIndex < blob->header.conditionEntryCount
            && blob->conditionEntries[sourceIndex].conditionId == conditionId) {
            return i;
        }
    }
    return -1;
}

static void PrintTarget(
    const OverworldBehaviorConditionTargetReference *target)
{
    printf("{\"kind\":%u,\"actorSlot\":%u,\"actorGeneration\":%u,"
           "\"fieldEpoch\":%u,\"mapGeneration\":%u,"
           "\"encounterGeneration\":%u}",
        (unsigned)target->kind,
        (unsigned)target->actor.slot,
        (unsigned)target->actor.generation,
        (unsigned)target->actor.fieldEpoch,
        (unsigned)target->actor.mapGeneration,
        (unsigned)target->actor.encounterGeneration);
}

static void TargetFromState(
    const OverworldBehaviorConditionEntryState *state,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionTargetReference *target)
{
    int i;

    memset(target, 0, sizeof(*target));
    target->kind = state->targetKind;
    if (state->targetKind
            != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        return;
    }
    for (i = 0; i < world->actorCount; i++) {
        const OverworldBehaviorConditionActorObservation *actor =
            &world->actors[i];

        if (actor->valid
            && actor->actor.slot == state->targetSlot
            && actor->actor.generation == state->targetGeneration
            && actor->actor.encounterGeneration
                == state->targetEncounterGeneration) {
            target->actor = actor->actor;
            return;
        }
    }
    target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
}

static void PrintResolver(
    const BehaviorResolveResult *result,
    BehaviorResolveStatus status,
    const BehaviorResolutionTrace *trace)
{
    int i;

    printf("{\"status\":%u,\"behaviorClass\":%u,"
           "\"behaviorLimitKey\":%u,\"speciesClassRuleIndex\":%u,"
           "\"matchedClassRuleMask\":%u,\"matchedOverrideMask\":%u,"
           "\"forcedOverrideMask\":%u,\"conditionalOverrideMask\":%u,"
           "\"appliedOverrideMask\":%u,\"fingerprint\":%u,"
           "\"profileHex\":\"",
        (unsigned)status,
        (unsigned)result->behaviorClass,
        (unsigned)result->behaviorLimitKey,
        (unsigned)result->speciesClassRuleIndex,
        (unsigned)result->matchedClassRuleMask,
        (unsigned)result->matchedOverrideMask,
        (unsigned)result->forcedOverrideMask,
        (unsigned)result->conditionalOverrideMask,
        (unsigned)result->appliedOverrideMask,
        (unsigned)result->fingerprint);
    PrintHex(&result->profile, sizeof(result->profile));
    printf("\",\"primitivesHex\":\"");
    PrintHex(&result->primitives, sizeof(result->primitives));
    printf("\",\"resolvedTarget\":{\"kind\":%u,\"actorSlot\":%u,"
           "\"actorGeneration\":%u,\"fieldEpoch\":%u,"
           "\"mapGeneration\":%u,\"encounterGeneration\":%u},"
           "\"winningConditionId\":%u,\"targetSourceApplication\":%u,"
           "\"resolvedTargetConditionId\":%u,\"traceDropped\":%u,"
           "\"trace\":[",
        (unsigned)result->resolvedTarget.kind,
        (unsigned)result->resolvedTarget.actorSlot,
        (unsigned)result->resolvedTarget.actorGeneration,
        (unsigned)result->resolvedTarget.fieldEpoch,
        (unsigned)result->resolvedTarget.mapGeneration,
        (unsigned)result->resolvedTarget.encounterGeneration,
        (unsigned)result->winningConditionId,
        (unsigned)result->targetSourceApplication,
        (unsigned)result->resolvedTargetConditionId,
        (unsigned)trace->dropped);
    for (i = 0; i < trace->count; i++) {
        const BehaviorResolutionStep *step = &trace->steps[i];

        if (i != 0) putchar(',');
        printf("{\"sourceIndex\":%u,\"lane\":%u,\"kind\":%u,"
               "\"flags\":%u,\"profileHex\":\"",
            (unsigned)step->sourceIndex,
            (unsigned)step->lane,
            (unsigned)step->kind,
            (unsigned)step->flags);
        PrintHex(&step->profile, sizeof(step->profile));
        printf("\"}");
    }
    printf("]}");
}

int main(void)
{
    const OverworldWildBehaviorDataBlob *blob = &gOverworldWildBehaviorDataBlob;
    long long header[PREVIEW_HEADER_VALUES];
    OverworldWildBehaviorContext subjectContext;
    OverworldBehaviorConditionPreparedActor prepared;
    OverworldBehaviorConditionEntryState
        preparedStates[OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES];
    OverworldBehaviorConditionWorldView world;
    OverworldBehaviorConditionCandidate candidates[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult conditionResult;
    BehaviorResolveRequest request;
    BehaviorResolveResult resolveResult;
    BehaviorResolutionStep traceSteps[HOST_TRACE_CAPACITY];
    BehaviorResolutionTrace trace;
    BehaviorClassSelection selection;
    OverworldBehaviorConditionStatus conditionStatus;
    BehaviorResolveStatus resolveStatus;
    u8 candidateCount;
    u16 stateCount;
    int i;

    if (!ReadValues(header, PREVIEW_HEADER_VALUES)) {
        fprintf(stderr, "invalid condition preview header\n");
        return 2;
    }
    candidateCount = (u8)header[21];
    stateCount = (u16)header[22];
    if (candidateCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || stateCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES) {
        fprintf(stderr, "condition preview exceeds runtime bounds\n");
        return 2;
    }

    memset(&subjectContext, 0, sizeof(subjectContext));
    subjectContext.species = (u16)header[0];
    subjectContext.level = (u8)header[1];
    subjectContext.terrain = (u8)header[2];
    subjectContext.shiny = (u8)header[3];
    subjectContext.groupFlags = (u32)header[4];
    subjectContext.behaviorClass = (u8)header[5];

    memset(&request, 0, sizeof(request));
    request.context = subjectContext;
    request.behaviorClass = subjectContext.behaviorClass;
    request.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    request.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.requestVersion = HOST_REQUEST_VERSION;
    trace.steps = traceSteps;
    trace.capacity = HOST_TRACE_CAPACITY;
    trace.count = 0;
    trace.dropped = 0;
    trace.reserved = 0;
    resolveStatus = BehaviorResolver_InspectClass(
        blob, sizeof(*blob), &request, &selection, &trace);
    if (resolveStatus != BEHAVIOR_RESOLVE_OK
        && resolveStatus != BEHAVIOR_RESOLVE_TRACE_TRUNCATED) {
        fprintf(stderr, "condition preview class selection failed: %u\n",
            (unsigned)resolveStatus);
        return 1;
    }
    subjectContext.behaviorClass = selection.behaviorClass;

    memset(&world, 0, sizeof(world));
    world.subject.slot = (u16)header[7];
    world.subject.generation = (u16)header[8];
    world.subject.fieldEpoch = (u16)header[9];
    world.subject.mapGeneration = (u16)header[10];
    world.subject.encounterGeneration = (u16)header[11];
    world.frame = (u32)header[12];
    world.subjectX = (s16)header[13];
    world.subjectY = (s16)header[14];
    world.playerX = (s16)header[15];
    world.playerY = (s16)header[16];
    world.playerValid = (u8)header[17];
    world.subjectFacing = (u8)header[18];
    world.subjectMovementSpeed = (u8)header[19];
    world.subjectTerrainMask = (u16)header[6];
    world.actorCount = candidateCount;

    memset(candidates, 0, sizeof(candidates));
    for (i = 0; i < candidateCount; i++) {
        long long values[PREVIEW_CANDIDATE_VALUES];

        if (!ReadValues(values, PREVIEW_CANDIDATE_VALUES)) {
            fprintf(stderr, "invalid condition preview candidate\n");
            return 2;
        }
        candidates[i].context.species = (u16)values[0];
        candidates[i].context.level = (u8)values[1];
        candidates[i].context.terrain = (u8)values[2];
        candidates[i].context.shiny = (u8)values[3];
        candidates[i].context.groupFlags = (u32)values[4];
        candidates[i].context.behaviorClass = (u8)values[5];
        candidates[i].roleMask = (u8)values[6];
        world.actors[i].actor.slot = (u16)values[7];
        world.actors[i].actor.generation = (u16)values[8];
        world.actors[i].actor.fieldEpoch = (u16)values[9];
        world.actors[i].actor.mapGeneration = (u16)values[10];
        world.actors[i].actor.encounterGeneration = (u16)values[11];
        world.actors[i].x = (s16)values[12];
        world.actors[i].y = (s16)values[13];
        world.actors[i].valid = (u8)values[14];
    }

    memset(&prepared, 0, sizeof(prepared));
    prepared.states = preparedStates;
    prepared.stateCapacity = OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES;
    conditionStatus = OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared);
    if (conditionStatus != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        fprintf(stderr, "condition preview preparation failed: %u\n",
            (unsigned)conditionStatus);
        return 1;
    }
    for (i = 0; i < stateCount; i++) {
        long long values[PREVIEW_STATE_VALUES];
        int preparedIndex;
        OverworldBehaviorConditionEntryState *entryState;

        if (!ReadValues(values, PREVIEW_STATE_VALUES)) {
            fprintf(stderr, "invalid condition preview state\n");
            return 2;
        }
        preparedIndex = FindPreparedCondition(blob, &prepared, (u16)values[0]);
        if (preparedIndex < 0) continue;
        entryState = &prepared.states[preparedIndex];
        entryState->flags = 0;
        if (values[1]) {
            entryState->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
        }
        if (values[2]) {
            entryState->flags |=
                OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
        }
        entryState->activeUntil = (u32)values[3];
        entryState->cooldownUntil = (u32)values[4];
        entryState->targetKind = (u8)values[5];
        if (entryState->targetKind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
            && values[6] >= 0 && values[6] < candidateCount) {
            entryState->targetSlot = world.actors[values[6]].actor.slot;
            entryState->targetGeneration =
                world.actors[values[6]].actor.generation;
            entryState->targetEncounterGeneration =
                world.actors[values[6]].actor.encounterGeneration;
        }
    }

    conditionStatus = OverworldBehaviorCondition_EvaluatePrepared(
        blob,
        sizeof(*blob),
        &prepared,
        &world,
        candidates,
        candidateCount,
        (u32)header[20],
        &scratch,
        &conditionResult);
    if (conditionStatus != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        fprintf(stderr, "condition preview evaluation failed: %u\n",
            (unsigned)conditionStatus);
        return 1;
    }

    memset(&request, 0, sizeof(request));
    request.context = subjectContext;
    request.behaviorClass = selection.behaviorClass;
    request.requestVersion = HOST_REQUEST_VERSION;
    request.activeConditionalMask = conditionResult.activeApplicationMask;
    request.winningConditionId = conditionResult.winningConditionId;
    request.targetSourceApplication = conditionResult.resolvedTargetSourceApplication;
    request.resolvedTargetConditionId = conditionResult.resolvedTargetConditionId;
    CopyTarget(&conditionResult.resolvedTarget, &request.resolvedTarget);
    trace.count = 0;
    trace.dropped = 0;
    memset(&resolveResult, 0, sizeof(resolveResult));
    resolveStatus = BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &resolveResult, &trace);

    printf("{\"evaluatorStatus\":%u,\"preparedCount\":%u,"
           "\"activeApplicationMask\":%u,"
           "\"triggeredApplicationMask\":%u,"
           "\"winningConditionId\":%u,"
           "\"winningConditionSourceApplication\":%u,"
           "\"resolvedTargetConditionId\":%u,"
           "\"resolvedTargetSourceApplication\":%u,"
           "\"resolvedTarget\":",
        (unsigned)conditionStatus,
        (unsigned)prepared.count,
        (unsigned)conditionResult.activeApplicationMask,
        (unsigned)conditionResult.triggeredApplicationMask,
        (unsigned)conditionResult.winningConditionId,
        (unsigned)conditionResult.winningConditionSourceApplication,
        (unsigned)conditionResult.resolvedTargetConditionId,
        (unsigned)conditionResult.resolvedTargetSourceApplication);
    PrintTarget(&conditionResult.resolvedTarget);
    printf(",\"entries\":[");
    for (i = 0; i < prepared.count; i++) {
        u16 sourceIndex = prepared.catalogEntryIndexes[i];
        const OverworldWildBehaviorConditionEntry *entry =
            &blob->conditionEntries[sourceIndex];
        const OverworldBehaviorConditionEntryState *entryState = &prepared.states[i];
        OverworldBehaviorConditionTargetReference entryTarget;
        u8 entryFlags = scratch.entryFlags[i];

        TargetFromState(entryState, &world, &entryTarget);

        if (i != 0) putchar(',');
        printf("{\"sourceCatalogIndex\":%u,\"conditionId\":%u,"
               "\"applicationIndex\":%u,\"conditionTrue\":%u,"
               "\"triggered\":%u,\"active\":%u,\"winsProfile\":%u,"
               "\"activeUntil\":%u,"
               "\"cooldownUntil\":%u,\"hasTriggered\":%u,\"target\":",
            (unsigned)sourceIndex,
            (unsigned)entry->conditionId,
            (unsigned)entry->applicationIndex,
            (unsigned)((entryFlags
                & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE) != 0),
            (unsigned)((entryFlags
                & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED) != 0),
            (unsigned)((entryFlags
                & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_ACTIVE) != 0),
            (unsigned)((entryFlags
                    & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_ACTIVE) != 0
                && conditionResult.winningConditionIds[entry->applicationIndex]
                    == entry->conditionId),
            (unsigned)entryState->activeUntil,
            (unsigned)entryState->cooldownUntil,
            (unsigned)((entryState->flags
                & OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED) != 0));
        PrintTarget(&entryTarget);
        printf("}");
    }
    printf("],\"resolver\":");
    PrintResolver(&resolveResult, resolveStatus, &trace);
    printf("}\n");
    return resolveStatus == BEHAVIOR_RESOLVE_OK
            || resolveStatus == BEHAVIOR_RESOLVE_TRACE_TRUNCATED
        ? 0
        : 1;
}
