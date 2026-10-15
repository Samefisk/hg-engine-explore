#include "../../include/overworld_behavior_condition_runtime.h"
#include "../../include/overworld_application_bank.h"
#include "../../include/overworld_target_bindings.h"
#include "../../include/overworld_condition_publication_native.h"
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#define OVERWORLD_CONDITION_PUBLICATION_RUNTIME_ONLY
#include "overworld_condition_publication_native.c"
#undef OVERWORLD_CONDITION_PUBLICATION_RUNTIME_ONLY
#endif

/* The fixed follower-selector tail is small.  Its ROM build compiles the
 * portable evaluator and catalog adapter as one unit so GCC can share their
 * validation and target-handling paths.  Host tests keep the two public
 * sources separate. */
#if defined(OVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME)
#define OVERWORLD_BEHAVIOR_RUNTIME_ONLY 1
#include "overworld_behavior_conditions.c"
#include "overworld_vision.c"
#endif

#if !defined(OVERWORLD_BEHAVIOR_HOST) \
    && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include "../../include/constants/file.h"
#endif

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <string.h>
#endif

/* Both binding helpers are linked into this same Query image. Engine imports
 * retain their long calls. */
#if defined(__arm__)
extern __typeof__(OverworldTargetBindings_Resolve) OverworldTargetBindings_Resolve __attribute__((short_call));
extern __typeof__(OverworldTargetBindings_CaptureEntry) OverworldTargetBindings_CaptureEntry __attribute__((short_call));
#endif


/* All local callees fit inside the fixed Query image, below the Thumb branch
 * range. Leave calls into the engine under the normal long-call policy. */
#if defined(__arm__)
#define CONDITION_RUNTIME_LOCAL_CALL __attribute__((short_call))
#else
#define CONDITION_RUNTIME_LOCAL_CALL
#endif

#define CONDITION_RUNTIME_MATCH_ANY_SPECIES 0
#define CONDITION_RUNTIME_MATCH_ANY_U8 0xFF
#define CONDITION_RUNTIME_MATCH_LEVEL_ANY 0

#if defined(OVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME)
#define OverworldBehaviorCondition_HandleEquals \
    OverworldBehaviorCondition_SameHandle
#else
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
#endif

void OverworldBehaviorCondition_NotifyWorldEffect(
    OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldActorHandle *subject,
    u32 effect)
{
    u8 index;

    if (effect != OVERWORLD_ACTOR_WORLD_EFFECT_CRASH
        || prepared == NULL || subject == NULL || !prepared->valid
        || prepared->states == NULL || prepared->count > prepared->stateCapacity
        || !OverworldBehaviorCondition_HandleEquals(
            &prepared->subject, subject)) {
        return;
    }
    for (index = 0; index < prepared->count; index++) {
        OverworldBehaviorConditionEntryState *state = &prepared->states[index];

        if (state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING) {
            state->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING;
            state->targetKind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
        }

        if ((state->flags & (OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE
                | OVERWORLD_BEHAVIOR_CONDITION_STATE_UNTIL_CRASH))
                == (OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE
                    | OVERWORLD_BEHAVIOR_CONDITION_STATE_UNTIL_CRASH)) {
            state->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING;
        }
    }
}

static u8 __attribute__((noinline, optimize("Os")))
CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_ResolveConditionMatches(
    const OverworldWildBehaviorDataBlob *blob,
    u16 application,
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
    const BehaviorResolveRequest *request,
    OverworldApplicationBank *validatedBank)
{
    u32 validOverrideMask;
    u8 winningApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    OverworldApplicationBank bank;
    u16 i;

    if (validatedBank == NULL
        || !OverworldApplicationBank_Select(blob, request->context.species, &bank))
        return FALSE;
    validOverrideMask = bank.count
            >= OWBD_MASKABLE_APPLICATION_COUNT
        ? 0xFFFFFFFFu
        : ((1u << bank.count) - 1u);
    if ((request->forcedOverrideMask & ~validOverrideMask) != 0
        || request->context.level > 100
        || request->context.terrain > OW_WILD_SPAWN_TERRAIN_FISHING
        || request->context.shiny > 1
        || request->requestVersion != BEHAVIOR_RESOLVE_REQUEST_VERSION) {
        return FALSE;
    }
    if ((request->activeConditionalMask & ~validOverrideMask) != 0
        || request->resolvedTarget.kind > BEHAVIOR_RESOLVE_TARGET_ACTOR) {
        return FALSE;
    }
    for (i = 0; i < bank.count; i++) {
        u32 bit = 1u << i;
        u8 conditional = OverworldApplicationBank_Profile(blob, &bank, i)->profileKind
            == OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;

        if (request->activeConditionalMask & bit) {
            if (!conditional) {
                return FALSE;
            }
            winningApplication = (u8)i;
        }
        if ((request->forcedOverrideMask & bit) != 0
            && conditional) {
            return FALSE;
        }
    }
    if (winningApplication == BEHAVIOR_RESOLVER_NO_APPLICATION) {
        if (request->winningConditionId != BEHAVIOR_RESOLVER_NO_CONDITION) {
            return FALSE;
        }
    } else if (!OverworldBehaviorCondition_ResolveConditionMatches(
                   blob,
                   OverworldApplicationBank_Global(&bank, winningApplication),
                   request->winningConditionId,
                   0,
                   FALSE)) {
        return FALSE;
    }
    if (request->resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_NONE) {
        if (request->targetSourceApplication
                == BEHAVIOR_RESOLVER_NO_APPLICATION
            && request->resolvedTargetConditionId
                == BEHAVIOR_RESOLVER_NO_CONDITION) {
            *validatedBank = bank;
            return TRUE;
        }
        return FALSE;
    }
    if (request->targetSourceApplication >= bank.count
        || request->resolvedTargetConditionId
            == BEHAVIOR_RESOLVER_NO_CONDITION
        || (request->activeConditionalMask
            & (1u << request->targetSourceApplication)) == 0) {
        return FALSE;
    }
    if (!OverworldBehaviorCondition_ResolveConditionMatches(
        blob,
        OverworldApplicationBank_Global(&bank, request->targetSourceApplication),
        request->resolvedTargetConditionId,
        request->resolvedTarget.kind,
        TRUE))
        return FALSE;
    *validatedBank = bank;
    return TRUE;
}

static u8 OverworldBehaviorCondition_MatchApplies(
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorMatch *match)
{
    return (match->species == CONDITION_RUNTIME_MATCH_ANY_SPECIES
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
    u16 memberCount,
    u8 speciesOnly)
{
    if (speciesOnly) {
        if (match->species != CONDITION_RUNTIME_MATCH_ANY_SPECIES
            && match->species != context->species)
            return 0;
    } else if (!OverworldBehaviorCondition_MatchApplies(context, match)) {
        return 0;
    }
    if (mode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL) {
        return 1;
    }
    return mode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS
        && OverworldBehaviorCondition_MemberMatches(
            blob, memberStart, memberCount, context->species);
}

static u8 CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_SubjectApplies(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionEntry *entry,
    const OverworldWildBehaviorContext *context,
    u16 globalSubjectApplication,
    u8 speciesOnly)
{
    const OverworldWildBehaviorMatch *match = &entry->subjectMatch;
    u8 mode = entry->subjectMode;
    u16 memberStart = entry->subjectMemberStart;
    u16 memberCount = entry->subjectMemberCount;

    if (globalSubjectApplication != 0xFFFFu) {
        const OverworldWildBehaviorOverrideProfile *application;

        if (globalSubjectApplication >= blob->header.overrideProfileCount) {
            return 0;
        }
        application =
            &blob->overrideProfiles[globalSubjectApplication];
        if (application->profileKind
                != OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL) {
            return 0;
        }
        match = &application->match;
        mode = application->targetMode;
        memberStart = application->memberStart;
        memberCount = application->memberCount;
    }
    return OverworldBehaviorCondition_TargetsContext(
        blob,
        context,
        match,
        mode,
        memberStart,
        memberCount,
        speciesOnly);
}

static u8 OverworldBehaviorCondition_TargetPoolMatches(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionEntry *entry,
    const OverworldBehaviorConditionCandidate *candidate)
{
    if ((candidate->reserved[0]
            & OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE) != 0
        || (entry->targetRoleMask & candidate->roleMask) == 0) {
        return 0;
    }
    if ((candidate->context.groupFlags & entry->targetGroupMask) != 0) {
        return 1;
    }
    if (entry->targetGroupMask == 0 && entry->targetMemberCount == 0) {
        return 1;
    }
    return OverworldBehaviorCondition_MemberMatches(
        blob,
        entry->targetMemberStart,
        entry->targetMemberCount,
        candidate->context.species);
}

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
static void __attribute__((noinline, optimize("Os")))
CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_BuildDefinition(
    const OverworldWildBehaviorConditionEntry *entry,
    OverworldBehaviorConditionDefinition *definition)
{
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
    definition->reserved = entry->rangeKind
            == OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM
        ? entry->minMovementSpeed
        : 0;
}
#else
static void __attribute__((naked, noinline))
CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_BuildDefinition(
    const OverworldWildBehaviorConditionEntry *entry,
    OverworldBehaviorConditionDefinition *definition)
{
    (void)entry;
    (void)definition;
    __asm__(
        "ldrh r2, [r0, #16]\n"
        "strh r2, [r1, #6]\n"
        "ldrh r2, [r0, #18]\n"
        "strh r2, [r1, #8]\n"
        "ldrh r2, [r0, #20]\n"
        "strh r2, [r1, #2]\n"
        "ldrh r2, [r0, #22]\n"
        "strh r2, [r1, #4]\n"
        "add r0, #32\n"
        "ldrh r2, [r0, #0]\n"
        "strh r2, [r1, #0]\n"
        "ldrb r2, [r0, #2]\n"
        "strb r2, [r1, #10]\n"
        "ldrb r2, [r0, #5]\n"
        "strb r2, [r1, #11]\n"
        "ldrb r2, [r0, #6]\n"
        "strb r2, [r1, #12]\n"
        "ldrb r2, [r0, #7]\n"
        "strb r2, [r1, #13]\n"
        "ldrh r2, [r0, #10]\n"
        "strh r2, [r1, #14]\n"
        "ldrh r2, [r0, #12]\n"
        "strh r2, [r1, #16]\n"
        "lsr r3, r2, #8\n"
        "ldrb r2, [r0, #14]\n"
        "strb r2, [r1, #18]\n"
        "ldrb r2, [r0, #10]\n"
        "cmp r2, #6\n"
        "beq 1f\n"
        "mov r3, #0\n"
        "1:\n"
        "strb r3, [r1, #19]\n"
        "bx lr\n");
}
#endif

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

static u8 __attribute__((noinline)) CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_OptionsValid(
    const OverworldWildBehaviorConditionOptions *options)
{
    return (options->subjectRoleMask & ~7u) == 0
        && options->captureBinding <= OVERWORLD_TARGET_BINDING_COUNT
        && options->usesBinding <= OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
        && (options->usesBinding != OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
            || options->captureBinding == OVERWORLD_TARGET_BINDING_CARGO+1)
        && options->bindingLifetime <= OVERWORLD_TARGET_BINDING_FRAMES
        && options->bindOnly <= 1 && options->mustBeReachableForPickup <= 1
        && options->pickupDistance <= 8 && options->pickupHeight <= 64
        && (!options->mustBeReachableForPickup || options->pickupDistance != 0)
        && options->failureResponse <= 1
        && options->boundTargetDistance <= 1 && !options->reservedDependency
        && (options->boundTargetDistance
            ? (options->usesBinding == OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST+1
                && options->maxTargetDistance >= 1 && options->maxTargetDistance <= 32
                && options->minTargetDistance <= options->maxTargetDistance)
            : (!options->minTargetDistance && !options->maxTargetDistance))
        && (!options->bindOnly || options->captureBinding)
        && (!options->captureBinding
            || (options->bindingLifetime == OVERWORLD_TARGET_BINDING_FRAMES
                ? options->bindingDurationFrames != 0
                : options->bindingDurationFrames == 0));
}

static u8 __attribute__((noinline)) CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_BindingAllows(
    const OverworldWildBehaviorConditionOptions *options,
    const OverworldBehaviorConditionWorldView *world,
    OverworldTargetBindingPosition *position)
{
    if (!OverworldBehaviorCondition_RoleApplies(
            options->subjectRoleMask, world->subjectRoleMask)) return 0;
    if (options->captureBinding) {
        if (world->bindings == NULL) return 0;
        if (options->bindOnly
            && (world->bindings->bindings[options->captureBinding-1].flags
                & OVERWORLD_TARGET_BINDING_BOUND)) return 0;
    }
    return !options->usesBinding || (world->bindings != NULL
        && OverworldTargetBindings_Resolve(world->bindings, world,
            options->usesBinding == OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
                ? OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST
                : options->usesBinding-1,
            position) == OVERWORLD_TARGET_BINDING_OK);
}

static u8 __attribute__((noinline)) CONDITION_RUNTIME_LOCAL_CALL OverworldBehaviorCondition_DependencyAllows(
    const OverworldWildBehaviorConditionOptions *options,
    const OverworldApplicationBank *bank,
    const OverworldBehaviorConditionResult *result,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldTargetBindingPosition *position,
    u8 targetKind)
{
    u8 local = 0;
    s32 dx, dy;

    if (options->requiredApplication) {
        local = OverworldApplicationBank_Local(bank, options->requiredApplication-1);
        if (local >= bank->count || !(result->activeApplicationMask & (1u << local))) return 0;
    }
    if (!options->boundTargetDistance) return 1;
    if (position->target.kind != targetKind) return 0;
    if (options->requiredApplication
        && (result->targets[local].kind != position->target.kind
            || (position->target.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                && !OverworldBehaviorCondition_HandleEquals(
                    &result->targets[local].actor, &position->target.actor)))) return 0;
    dx = (s32)position->x - world->subjectX;
    dy = (s32)position->y - world->subjectY;
    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;
    if (dy > dx) dx = dy;
    return dx >= options->minTargetDistance && dx <= options->maxTargetDistance;
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
    OverworldApplicationBank bank;
    u16 i;

    if (subjectContext == NULL || subject == NULL || prepared == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    prepared->count = 0;
    prepared->valid = 0;
    prepared->subjectDamagePending = 0;
    if (!OverworldConditionPublication_BlobValid(blob, blobSize)
        || !OverworldApplicationBank_Select(blob, subjectContext->species, &bank)) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
    prepared->subject = *subject;
    prepared->subjectSpecies = subjectContext->species;
    for (i = 0; i < blob->header.conditionEntryCount; i++) {
        if (OverworldApplicationBank_Local(
                &bank, blob->conditionGlobalApplications[i]) < 0
            || !OverworldBehaviorCondition_SubjectApplies(blob,
                &blob->conditionEntries[i], subjectContext,
                blob->conditionGlobalSubjectApplications[i], TRUE)) {
            continue;
        }
        if (prepared->count >= OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES)
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        prepared->catalogEntryIndexes[prepared->count++] = i;
    }
    if (prepared->count > prepared->stateCapacity
        || (prepared->count != 0 && prepared->states == NULL)) {
#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST) \
    || defined(OVERWORLD_BEHAVIOR_CONDITION_RELOCATABLE_CODE)
        return OVERWORLD_BEHAVIOR_CONDITION_STORAGE_REQUIRED;
#else
        if (prepared->states != NULL) {
            return OVERWORLD_BEHAVIOR_CONDITION_STORAGE_REQUIRED;
        }
        prepared->states = sys_AllocMemory(
            HEAPID_WORLD,
            prepared->count * sizeof(*prepared->states));
        if (prepared->states == NULL) {
            return OVERWORLD_BEHAVIOR_CONDITION_STORAGE_REQUIRED;
        }
        prepared->stateCapacity = prepared->count;
#endif
    }
    if (prepared->count != 0) {
        memset(
            prepared->states,
            0,
            prepared->count * sizeof(*prepared->states));
    }
    prepared->valid = 1;
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

/* Image-private character comparison; the20-byte span has no padding. */
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
extern u8 OverworldPickupRoute_EqualValues(const void *, const void *, u8) __attribute__((pure));
#else
extern u8 OverworldPickupRoute_EqualValues(const void *, const void *, u8) __attribute__((short_call, pure));
#endif
/* The production full Query link needs the same size policy as its Resolver.
 * The shared C stage matrix remains the behavioral check for this leaf. */
OverworldBehaviorConditionStatus __attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,no-if-conversion,no-tree-loop-im,no-schedule-insns2"))) OverworldBehaviorCondition_EvaluatePrepared(
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
    OverworldBehaviorConditionDefinition definition;
    OverworldBehaviorConditionEntryInput input;
    OverworldBehaviorConditionEntryResult entryResult;
    OverworldBehaviorConditionEntryState warmState;
    OverworldBehaviorConditionStatus status;
    OverworldApplicationBank bank;
    const OverworldWildBehaviorContext *currentSubjectContext = NULL;
    u8 priorPublication[OVERWORLD_CONDITION_PUBLICATION_BYTES];
    u32 i;

    if (prepared == NULL || world == NULL || candidates == NULL
        || scratch == NULL || result == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    scratch->entryFlags[0] &= ~OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED;
    if (!OverworldConditionPublication_BlobValid(blob, blobSize)
        || !prepared->valid
        || prepared->count > OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        || prepared->count > prepared->stateCapacity
        || (prepared->count != 0 && prepared->states == NULL)
        || world->reservedBinding > OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY
        || candidateCount != world->actorCount
        || candidateCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || !OverworldBehaviorCondition_HandleEquals(
            &prepared->subject, &world->subject)) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
    if (!OverworldApplicationBank_Select(blob, prepared->subjectSpecies, &bank))
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    for (i = 0; i < candidateCount; ++i) {
        if (OverworldBehaviorCondition_HandleEquals(
                &world->actors[i].actor, &prepared->subject)) {
            currentSubjectContext = &candidates[i].context;
            break;
        }
    }
    if (currentSubjectContext == NULL
        || currentSubjectContext->species != prepared->subjectSpecies)
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    OverworldConditionPublication_InitResult(result);
    /* Validate the complete prepared batch before any timer or target state
     * is changed. This keeps malformed later entries atomic with the portable
     * evaluator. */
    for (i = 0; i < prepared->count; i++) {
        const OverworldWildBehaviorConditionEntry *entry;
        const OverworldWildBehaviorConditionOptions *options;
        u16 sourceIndex = prepared->catalogEntryIndexes[i];
        u8 application;

        if (sourceIndex >= blob->header.conditionEntryCount) {
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
        entry = &blob->conditionEntries[sourceIndex];
        options = &blob->conditionOptions[sourceIndex];
        OverworldBehaviorCondition_BuildDefinition(entry, &definition);
        if (options->boundTargetDistance)
            definition.reserved = OVERWORLD_BEHAVIOR_CONDITION_RADIUS_SAME_TILE;
        application = OverworldApplicationBank_Local(
            &bank, blob->conditionGlobalApplications[sourceIndex]);
        if (application >= bank.count)
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        definition.applicationIndex = application;
        if (!OverworldBehaviorCondition_DefinitionValid(&definition)
            || !OverworldBehaviorCondition_OptionsValid(options)
            || (options->requiredApplication
                && (options->requiredApplication-1 >= blob->conditionGlobalApplications[sourceIndex]
                    || blob->overrideProfiles[options->requiredApplication-1].profileKind
                        != OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL))
            || (options->boundTargetDistance
                && (entry->activationMode != OW_WILD_BEHAVIOR_CONDITION_WHILE_TRUE
                    || entry->targetKind == OW_WILD_BEHAVIOR_CONDITION_TARGET_NONE))
            || (options->captureBinding == 2
                && entry->targetKind != OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR)) {
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
        if (options->captureBinding && world->bindings != NULL) {
            const OverworldTargetBinding *capture =
                &world->bindings->bindings[options->captureBinding-1];
            if ((capture->flags & OVERWORLD_TARGET_BINDING_BOUND)
                && capture->sourceApplication == application
                && capture->sourceConditionId != entry->conditionId) continue;
        }
        if (OverworldBehaviorCondition_SubjectApplies(blob, entry,
                currentSubjectContext,
                blob->conditionGlobalSubjectApplications[sourceIndex], FALSE)
            && world->reservedBinding != OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY
            && (prepared->states[i].flags
                & OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)
            && !options->bindOnly) {
            application = definition.applicationIndex;
            result->activeApplicationMask |= 1u << application;
            result->winningConditionIds[application] = entry->conditionId;
            result->targets[application].kind = prepared->states[i].targetKind;
            /* This first pass needs only the captured winner's row. */
            result->targets[application].actor.slot = i;
        }
    }
    if (world->reservedBinding != OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY)
        OverworldConditionPublication_CapturePrior(prepared, result, priorPublication);
    for (i = 0; i < prepared->count; i++) {
        const OverworldWildBehaviorConditionEntry *entry;
        const OverworldWildBehaviorConditionOptions *options;
        OverworldTargetBindingPosition boundPosition;
        OverworldBehaviorConditionEntryState *entryState;
        u16 sourceIndex = prepared->catalogEntryIndexes[i];
        u32 candidateIndex;
        u8 application;
        u8 pendingPresentation;
        u8 wasTimedActive;

        entry = &blob->conditionEntries[sourceIndex];
        options = &blob->conditionOptions[sourceIndex];
        OverworldBehaviorCondition_BuildDefinition(entry, &definition);
        if (options->boundTargetDistance)
            definition.reserved = OVERWORLD_BEHAVIOR_CONDITION_RADIUS_SAME_TILE;
        application = OverworldApplicationBank_Local(
            &bank, blob->conditionGlobalApplications[sourceIndex]);
        if (application >= bank.count)
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        definition.applicationIndex = application;
        if (world->reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO
            && (options->captureBinding != OVERWORLD_TARGET_BINDING_CARGO+1
                || !options->mustBeReachableForPickup
                || definition.kind != OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS)) {
            continue;
        }
        entryState = &prepared->states[i];
        wasTimedActive = definition.activationMode == OVERWORLD_BEHAVIOR_CONDITION_TIMED
            && (entryState->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE);
        if (world->reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO) {
            warmState = *entryState;
            entryState = &warmState;
        }
        if (!OverworldBehaviorCondition_SubjectApplies(blob, entry,
                currentSubjectContext,
                blob->conditionGlobalSubjectApplications[sourceIndex], FALSE)
            || !OverworldBehaviorCondition_BindingAllows(
                options, world, &boundPosition)
            || !OverworldBehaviorCondition_DependencyAllows(options, &bank, result,
                world, &boundPosition, entry->targetKind)) {
            /* End only this condition's contribution. The role owner
             * handles claims and held control at the action boundary. */
            scratch->entryFlags[i] = 0;
            if (world->reservedBinding != OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY) {
                u8 pendingEnd = entryState->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING;
                memset(entryState, 0, sizeof(*entryState));
                if (world->reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING_NOTICE
                    && (wasTimedActive || pendingEnd))
                    entryState->flags = OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING;
                else if (world->reservedBinding == 0 && pendingEnd)
                    scratch->entryFlags[i] = OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TIMED_ENDED;
            }
            continue;
        }
        input.eligibleActorMask = 0;
        input.reserved = world->reservedBinding >= OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING_NOTICE
            ? world->reservedBinding - 1 : 0;
        input.chanceRoll =
            OverworldBehaviorCondition_ChanceRoll(
                chanceSeed, &prepared->subject, entry->conditionId);
        if (entry->targetKind
                == OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR) {
            for (candidateIndex = 0;
                 candidateIndex < candidateCount;
                 candidateIndex++) {
                if (!OverworldBehaviorCondition_TargetPoolMatches(
                        blob, entry, &candidates[candidateIndex])
                    || ((options->usesBinding >= OVERWORLD_TARGET_BINDING_CARGO+1
                            || options->boundTargetDistance)
                        && !OverworldBehaviorCondition_HandleEquals(
                            &world->actors[candidateIndex].actor,
                            &boundPosition.target.actor))
                    || (options->mustBeReachableForPickup
                        && !(((u16)world->reserved[1] | ((u16)world->reserved[2] << 8))
                            & (1u << world->actors[candidateIndex].actor.slot)))
                    || ((definition.terrainMask
                            & OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP)
                        && !(world->incomingClaimMask
                            & (1u << world->actors[candidateIndex].actor.slot)))) {
                    continue;
                }
                if (options->captureBinding == OVERWORLD_TARGET_BINDING_CARGO+1
                    && world->bindings != NULL
                    && ((options->usesBinding != OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST
                        && world->bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]
                            .target.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                        && OverworldBehaviorCondition_HandleEquals(
                            &world->actors[candidateIndex].actor,
                            &world->bindings->bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor))
                        || ((world->bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
                                & OVERWORLD_TARGET_BINDING_BOUND)
                            && !OverworldBehaviorCondition_HandleEquals(
                                &world->actors[candidateIndex].actor,
                                &world->bindings->bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor)))) {
                    continue;
                }
                input.eligibleActorMask |= 1u << candidateIndex;
            }
        }
        pendingPresentation = entryState->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING;
        status = OverworldBehaviorCondition_EvaluateEntry(
            &definition,
            &input,
            world,
            entryState,
            &entryResult);
        if (status != OVERWORLD_BEHAVIOR_CONDITION_OK) {
            return status;
        }
        if (world->reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY) {
            scratch->entryFlags[i] = entryResult.conditionTrue << 1;
            if (entryResult.conditionTrue
                || definition.kind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT) {
                if (definition.kind == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED
                    || definition.targetKind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER) {
                    result->triggeredApplicationMask |= OVERWORLD_BEHAVIOR_CONDITION_NOTICE_PLAYER_MASK;
                }
                result->activeApplicationMask |= entryResult.target.actor.slot;
                if (definition.kind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT
                    && definition.targetKind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR) {
                    for (candidateIndex = 0; candidateIndex < candidateCount; candidateIndex++)
                        if ((input.eligibleActorMask & (1u << candidateIndex))
                            && world->actors[candidateIndex].valid
                            && !OverworldBehaviorCondition_HandleEquals(&world->subject,
                                &world->actors[candidateIndex].actor)
                            && world->actors[candidateIndex].actor.slot < OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS)
                            result->activeApplicationMask |= 1u << world->actors[candidateIndex].actor.slot;
                }
            }
            continue;
        }
        if (options->captureBinding && entryResult.active
            && entryResult.conditionTrue && entryResult.triggered) {
            status = (OverworldBehaviorConditionStatus)
                OverworldTargetBindings_CaptureEntry(world->bindings, world,
                    &prepared->subject, &entryResult, options->captureBinding-1,
                    options->bindingLifetime, options->bindingDurationFrames);
            if ((u32)status != OVERWORLD_TARGET_BINDING_OK
                && (u32)status != OVERWORLD_TARGET_BINDING_ALREADY_BOUND) {
                memset(entryState, 0, sizeof(*entryState));
                scratch->entryFlags[i] = 0;
                continue;
            }
        }
        if (options->captureBinding && !options->bindOnly && entryResult.active
            && world->bindings->bindings[options->captureBinding-1].sourceApplication == application
            && (world->bindings->bindings[options->captureBinding-1].flags
                & OVERWORLD_TARGET_BINDING_BOUND)) {
            if (OverworldTargetBindings_Resolve(world->bindings, world,
                    options->captureBinding-1, &boundPosition) != OVERWORLD_TARGET_BINDING_OK) {
                scratch->entryFlags[i] = 0;
                continue;
            }
            entryResult.target = boundPosition.target;
            entryResult.conditionId = world->bindings->bindings[options->captureBinding-1].sourceConditionId;
        }
        scratch->entryFlags[i] =
            entryResult.active
            | (entryResult.conditionTrue << 1)
            | (entryResult.triggered << 2);
        if (world->reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_MOVING_NOTICE
            && wasTimedActive && !entryResult.active)
            entryState->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING;
        if (world->reservedBinding == 0
            && (entryState->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING)) {
            scratch->entryFlags[i] |= OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TIMED_ENDED;
            entryState->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING;
        }
        if (world->reservedBinding == 0 && pendingPresentation
            && entryResult.active && entryResult.triggered)
            scratch->entryFlags[i] |= OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PRESENTATION_ENTERED;
        if (!entryResult.active || options->bindOnly) {
            continue;
        }
        application = definition.applicationIndex;
        result->activeApplicationMask |= 1u << application;
        if (entryResult.triggered) {
            result->triggeredApplicationMask |= 1u << application;
        } else {
            result->triggeredApplicationMask &= ~(1u << application);
        }
        result->winningConditionIds[application] =
            entryResult.conditionId;
        result->targets[application] = entryResult.target;
    }
    if (world->reservedBinding == OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_NOTICE_GEOMETRY)
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    OverworldConditionPublication_FoldResult(result);
    if (!OverworldPickupRoute_EqualValues(priorPublication,
            &result->resolvedTarget, sizeof(priorPublication))) {
        scratch->entryFlags[0] |= OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED;
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}
