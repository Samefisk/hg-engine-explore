#include "../../include/overworld_behavior_condition_runtime.h"

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <string.h>
#endif

#define CONDITION_RUNTIME_MATCH_ANY_SPECIES 0
#define CONDITION_RUNTIME_MATCH_ANY_U8 0xFF
#define CONDITION_RUNTIME_MATCH_LEVEL_ANY 0

static u8 OverworldBehaviorCondition_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    return left->slot == right->slot
        && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

static u8 OverworldBehaviorCondition_BlobValid(
    const OverworldWildBehaviorDataBlob *blob,
    u32 blobSize)
{
    return blob != NULL
        && blobSize == sizeof(*blob)
        && blob->header.magic == OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        && blob->header.version == OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        && blob->header.headerSize == sizeof(blob->header)
        && blob->header.blobSize == sizeof(*blob)
        && blob->header.overrideProfileCount <= 32
        && blob->header.overrideMemberCount <= OWBD_OVERRIDE_MEMBER_COUNT
        && blob->header.conditionEntryCount
            <= OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES;
}

static u8 OverworldBehaviorCondition_ResolveConditionMatches(
    const OverworldWildBehaviorDataBlob *blob,
    u8 application,
    u16 conditionId,
    u8 targetKind,
    u8 checkTargetKind)
{
    const OverworldWildBehaviorOverrideProfile *profile;
    u16 end;
    u16 i;

    if (application >= blob->header.overrideProfileCount
        || conditionId == BEHAVIOR_RESOLVER_NO_CONDITION) {
        return 0;
    }
    profile = &blob->overrideProfiles[application];
    end = (u16)(profile->conditionStart + profile->conditionCount);
    if (end > blob->header.conditionEntryCount) {
        return 0;
    }
    for (i = profile->conditionStart; i < end; i++) {
        if (blob->conditionEntries[i].conditionId == conditionId
            && (!checkTargetKind
                || blob->conditionEntries[i].targetKind == targetKind)) {
            return 1;
        }
    }
    return 0;
}

BOOL OverworldBehaviorCondition_ValidateResolveRequest(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request)
{
    u32 validOverrideMask;
    u8 winningApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    u16 i;

    validOverrideMask = blob->header.overrideProfileCount == 32
        ? 0xFFFFFFFFu
        : ((1u << blob->header.overrideProfileCount) - 1u);
    if ((request->forcedOverrideMask & ~validOverrideMask) != 0
        || request->context.level > 100
        || request->context.terrain > OW_WILD_SPAWN_TERRAIN_FISHING
        || request->context.shiny > 1
        || request->conditionInputMode
            > BEHAVIOR_RESOLVE_CONDITIONS_EXPLICIT) {
        return FALSE;
    }
    if (request->conditionInputMode == BEHAVIOR_RESOLVE_CONDITIONS_LEGACY) {
        return TRUE;
    }
    if ((request->activeConditionalMask & ~validOverrideMask) != 0
        || request->resolvedTarget.kind > BEHAVIOR_RESOLVE_TARGET_ACTOR) {
        return FALSE;
    }
    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        u32 bit = 1u << i;

        if ((request->activeConditionalMask & bit) != 0
            && blob->overrideProfiles[i].profileKind
                != OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL) {
            return FALSE;
        }
        if (request->activeConditionalMask & bit) {
            winningApplication = (u8)i;
        }
        if ((request->forcedOverrideMask & bit) != 0
            && blob->overrideProfiles[i].profileKind
                == OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL) {
            return FALSE;
        }
    }
    if (winningApplication == BEHAVIOR_RESOLVER_NO_APPLICATION) {
        if (request->winningConditionId != BEHAVIOR_RESOLVER_NO_CONDITION) {
            return FALSE;
        }
    } else if (!OverworldBehaviorCondition_ResolveConditionMatches(
                   blob,
                   winningApplication,
                   request->winningConditionId,
                   0,
                   FALSE)) {
        return FALSE;
    }
    if (request->resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_NONE) {
        return request->targetSourceApplication
                == BEHAVIOR_RESOLVER_NO_APPLICATION
            && request->resolvedTargetConditionId
                == BEHAVIOR_RESOLVER_NO_CONDITION;
    }
    if (request->targetSourceApplication
            >= blob->header.overrideProfileCount
        || request->resolvedTargetConditionId
            == BEHAVIOR_RESOLVER_NO_CONDITION
        || (request->activeConditionalMask
            & (1u << request->targetSourceApplication)) == 0) {
        return FALSE;
    }
    return OverworldBehaviorCondition_ResolveConditionMatches(
        blob,
        request->targetSourceApplication,
        request->resolvedTargetConditionId,
        request->resolvedTarget.kind,
        TRUE);
}

static u8 OverworldBehaviorCondition_MatchApplies(
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorMatch *match)
{
    return context != NULL
        && match != NULL
        && (match->species == CONDITION_RUNTIME_MATCH_ANY_SPECIES
            || match->species == context->species)
        && (match->groupMask == 0
            || (context->groupFlags & match->groupMask) != 0)
        && (match->terrain == CONDITION_RUNTIME_MATCH_ANY_U8
            || match->terrain == context->terrain)
        && (match->minLevel == CONDITION_RUNTIME_MATCH_LEVEL_ANY
            || context->level >= match->minLevel)
        && (match->maxLevel == CONDITION_RUNTIME_MATCH_LEVEL_ANY
            || context->level <= match->maxLevel)
        && (match->shiny == CONDITION_RUNTIME_MATCH_ANY_U8
            || match->shiny == context->shiny)
        && (match->behaviorClass == CONDITION_RUNTIME_MATCH_ANY_U8
            || match->behaviorClass == context->behaviorClass);
}

static u8 OverworldBehaviorCondition_MemberMatches(
    const OverworldWildBehaviorDataBlob *blob,
    u16 start,
    u16 count,
    u16 species)
{
    u32 end = (u32)start + count;
    u32 i;

    if (count == 0 || end > blob->header.overrideMemberCount) {
        return 0;
    }
    for (i = start; i < end; i++) {
        if (blob->overrideMembers[i] == species) {
            return 1;
        }
    }
    return 0;
}

static u8 OverworldBehaviorCondition_TargetsContext(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorMatch *match,
    u8 mode,
    u16 memberStart,
    u16 memberCount)
{
    if (!OverworldBehaviorCondition_MatchApplies(context, match)) {
        return 0;
    }
    if (mode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL) {
        return 1;
    }
    return mode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS
        && OverworldBehaviorCondition_MemberMatches(
            blob, memberStart, memberCount, context->species);
}

static u8 OverworldBehaviorCondition_SubjectApplies(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionEntry *entry,
    const OverworldWildBehaviorContext *context)
{
    if (entry->subjectApplicationIndex
            != OW_WILD_BEHAVIOR_CONDITION_SUBJECT_APPLICATION_NONE) {
        const OverworldWildBehaviorOverrideProfile *application;

        if (entry->subjectApplicationIndex
                >= blob->header.overrideProfileCount) {
            return 0;
        }
        application =
            &blob->overrideProfiles[entry->subjectApplicationIndex];
        return application->profileKind
                == OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL
            && OverworldBehaviorCondition_TargetsContext(
                blob,
                context,
                &application->match,
                application->targetMode,
                application->memberStart,
                application->memberCount);
    }
    return OverworldBehaviorCondition_TargetsContext(
        blob,
        context,
        &entry->subjectMatch,
        entry->subjectMode,
        entry->subjectMemberStart,
        entry->subjectMemberCount);
}

static u8 OverworldBehaviorCondition_TargetPoolMatches(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionEntry *entry,
    const OverworldBehaviorConditionCandidate *candidate)
{
    u8 groupMatch;
    u8 memberMatch;

    if ((entry->targetRoleMask & candidate->roleMask) == 0) {
        return 0;
    }
    groupMatch = entry->targetGroupMask != 0
        && (candidate->context.groupFlags & entry->targetGroupMask) != 0;
    memberMatch = OverworldBehaviorCondition_MemberMatches(
        blob,
        entry->targetMemberStart,
        entry->targetMemberCount,
        candidate->context.species);
    if (entry->targetGroupMask == 0 && entry->targetMemberCount == 0) {
        return 1;
    }
    return groupMatch || memberMatch;
}

static void OverworldBehaviorCondition_BuildDefinition(
    const OverworldWildBehaviorConditionEntry *entry,
    OverworldBehaviorConditionDefinition *definition)
{
    memset(definition, 0, sizeof(*definition));
    definition->conditionId = entry->conditionId;
    definition->durationFrames = entry->durationFrames;
    definition->cooldownFrames = entry->cooldownFrames;
    definition->terrainMask = entry->terrainMask;
    definition->terrainOverrideMask = entry->terrainOverrideMask;
    definition->applicationIndex = entry->applicationIndex;
    definition->kind = entry->kind;
    definition->activationMode = entry->activationMode;
    definition->targetKind = entry->targetKind;
    definition->rangeKind = entry->rangeKind;
    definition->distance = entry->rangeLength;
    definition->chance = entry->chancePercent;
    definition->minMovementSpeed = entry->minMovementSpeed;
    definition->maxMovementSpeed = entry->maxMovementSpeed;
}

static u8 OverworldBehaviorCondition_ChanceRoll(
    u32 chanceSeed,
    const OverworldActorHandle *subject,
    u16 conditionId)
{
    u32 hash = chanceSeed ^ 2166136261u;

    hash = (hash ^ subject->slot) * 16777619u;
    hash = (hash ^ subject->generation) * 16777619u;
    hash = (hash ^ subject->fieldEpoch) * 16777619u;
    hash = (hash ^ subject->mapGeneration) * 16777619u;
    hash = (hash ^ subject->encounterGeneration) * 16777619u;
    hash = (hash ^ conditionId) * 16777619u;
    return (u8)(hash % 100u);
}

OverworldBehaviorConditionStatus OverworldBehaviorCondition_PrepareActor(
    const void *blobBytes,
    u32 blobSize,
    const OverworldWildBehaviorContext *subjectContext,
    const OverworldActorHandle *subject,
    OverworldBehaviorConditionPreparedActor *prepared)
{
    const OverworldWildBehaviorDataBlob *blob =
        (const OverworldWildBehaviorDataBlob *)blobBytes;
    u16 i;

    if (subjectContext == NULL || subject == NULL || prepared == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    memset(prepared, 0, sizeof(*prepared));
    if (!OverworldBehaviorCondition_BlobValid(blob, blobSize)) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
    prepared->subject = *subject;
    for (i = 0; i < blob->header.conditionEntryCount; i++) {
        if (!OverworldBehaviorCondition_SubjectApplies(
                blob, &blob->conditionEntries[i], subjectContext)) {
            continue;
        }
        if (prepared->count >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES) {
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
        prepared->catalogEntryIndexes[prepared->count++] = i;
    }
    prepared->valid = 1;
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluatePrepared(
    const void *blobBytes,
    u32 blobSize,
    OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldBehaviorConditionCandidate *candidates,
    u8 candidateCount,
    u32 chanceSeed,
    OverworldBehaviorConditionScratch *scratch,
    OverworldBehaviorConditionResult *result)
{
    const OverworldWildBehaviorDataBlob *blob =
        (const OverworldWildBehaviorDataBlob *)blobBytes;
    u16 i;

    if (prepared == NULL || world == NULL || candidates == NULL
        || scratch == NULL || result == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    if (!OverworldBehaviorCondition_BlobValid(blob, blobSize)
        || !prepared->valid
        || candidateCount != world->actorCount
        || candidateCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || !OverworldBehaviorCondition_HandleEquals(
            &prepared->subject, &world->subject)) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
    memset(scratch, 0, sizeof(*scratch));
    for (i = 0; i < prepared->count; i++) {
        const OverworldWildBehaviorConditionEntry *entry;
        u16 sourceIndex = prepared->catalogEntryIndexes[i];
        u8 candidateIndex;

        if (sourceIndex >= blob->header.conditionEntryCount) {
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
        entry = &blob->conditionEntries[sourceIndex];
        OverworldBehaviorCondition_BuildDefinition(
            entry, &scratch->definitions[i]);
        scratch->inputs[i].chanceRoll =
            OverworldBehaviorCondition_ChanceRoll(
                chanceSeed, &prepared->subject, entry->conditionId);
        if (entry->targetKind
                != OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR) {
            continue;
        }
        for (candidateIndex = 0;
             candidateIndex < candidateCount;
             candidateIndex++) {
            if (OverworldBehaviorCondition_TargetPoolMatches(
                    blob, entry, &candidates[candidateIndex])) {
                scratch->inputs[i].eligibleActorMask |=
                    1u << candidateIndex;
            }
        }
    }
    return OverworldBehaviorCondition_EvaluateWithResults(
        scratch->definitions,
        scratch->inputs,
        prepared->states,
        prepared->count,
        world,
        result,
        scratch->entryResults);
}
