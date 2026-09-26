#include "../../include/overworld_behavior_conditions.h"

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <string.h>
#endif

#if defined(__GNUC__) && !defined(__clang__)
#define OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED \
    __attribute__((optimize("Os")))
#else
#define OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED
#endif

typedef u16 OverworldBehaviorConditionHandleHalfword
    __attribute__((may_alias));

_Static_assert(
    OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED + 1
        == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER,
    "player condition target ordering changed");
_Static_assert(
    OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED + 1
        == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR,
    "Pokemon condition target ordering changed");

static u16 OverworldBehaviorCondition_Abs(s32 value)
{
    return (u16)(value < 0 ? -value : value);
}

static u16 OverworldBehaviorCondition_Distance(s32 dx, s32 dy)
{
    u16 x = OverworldBehaviorCondition_Abs(dx);
    u16 y = OverworldBehaviorCondition_Abs(dy);

    return x > y ? x : y;
}

static u8 OverworldBehaviorCondition_SameHandle(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    const OverworldBehaviorConditionHandleHalfword *leftValues =
        (const OverworldBehaviorConditionHandleHalfword *)left;
    const OverworldBehaviorConditionHandleHalfword *rightValues =
        (const OverworldBehaviorConditionHandleHalfword *)right;
    u8 index;

    /* Actor observations can start at a halfword boundary. Keep this safe for
     * ARM9 instead of casting the handle to u32 words. */
    for (index = 0; index < 5; index++) {
        if (leftValues[index] != rightValues[index]) {
            return 0;
        }
    }
    return 1;
}

static u8 OverworldBehaviorCondition_InRange(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionWorldView *world,
    s16 x,
    s16 y)
{
    s32 dx = (s32)x - world->subjectX;
    s32 dy = (s32)y - world->subjectY;
    u16 ax = OverworldBehaviorCondition_Abs(dx);
    u16 ay = OverworldBehaviorCondition_Abs(dy);

    if ((dx == 0 && dy == 0)
        || ax > definition->distance
        || ay > definition->distance) {
        return 0;
    }
    switch (definition->rangeKind) {
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_CARDINAL_LINE:
        return dx == 0 || dy == 0;
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS:
        return 1;
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE_CLOSE_RADIUS:
        if (ax <= 1 && ay <= 1) {
            return 1;
        }
        /* fall through */
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE:
        switch (world->subjectFacing) {
        case 0:
            return dx == 0 && dy < 0;
        case 1:
            return dx == 0 && dy > 0;
        case 2:
            return dy == 0 && dx < 0;
        case 3:
            return dy == 0 && dx > 0;
        }
        return 0;
    default:
        return 0;
    }
}

static u8 OverworldBehaviorCondition_UsesVision(
    const OverworldBehaviorConditionDefinition *definition)
{
    return definition->rangeKind
            == OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT
        || definition->rangeKind
            == OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;
}

#if defined(OVERWORLD_BEHAVIOR_HOST) \
    || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
static OverworldVisionSpec OverworldBehaviorCondition_VisionSpec(
    const OverworldBehaviorConditionDefinition *definition,
    u8 currentRange,
    u8 currentOptions)
{
    OverworldVisionSpec spec;

    if (definition->rangeKind
            == OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM) {
        spec.range = definition->distance;
        spec.options = definition->reserved;
    } else {
        spec.range = currentRange;
        spec.options = currentOptions;
    }
    return spec;
}

static u8 __attribute__((noinline)) OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED
OverworldBehaviorCondition_CanSee(
    const OverworldBehaviorConditionDefinition *definition,
    u8 currentRange,
    u8 currentOptions,
    s16 observerX,
    s16 observerY,
    u8 observerFacing,
    s16 targetX,
    s16 targetY,
    u8 occluded)
{
    OverworldVisionSpec spec = OverworldBehaviorCondition_VisionSpec(
        definition,
        currentRange,
        currentOptions);

    return OverworldVision_CanSee(
        &spec,
        observerX,
        observerY,
        observerFacing,
        targetX,
        targetY,
        occluded);
}
#else
static u8 __attribute__((naked, noinline))
OverworldBehaviorCondition_CanSee(
    const OverworldBehaviorConditionDefinition *definition,
    u8 currentRange,
    u8 currentOptions,
    s16 observerX,
    s16 observerY,
    u8 observerFacing,
    s16 targetX,
    s16 targetY,
    u8 occluded)
{
    (void)definition;
    (void)currentRange;
    (void)currentOptions;
    (void)observerX;
    (void)observerY;
    (void)observerFacing;
    (void)targetX;
    (void)targetY;
    (void)occluded;
    __asm__(
        "push {r4, lr}\n"
        "mov r4, r0\n"
        "ldr r0, [sp, #24]\n"
        "cmp r0, #0\n"
        "beq 2f\n"
        "mov r0, #0\n"
        "pop {r4, pc}\n"
        "2:\n"
        "sub sp, #16\n"
        "str r3, [sp, #8]\n"
        "ldrb r3, [r4, #14]\n"
        "cmp r3, #6\n"
        "bne 1f\n"
        "ldrb r1, [r4, #15]\n"
        "ldrb r2, [r4, #19]\n"
        "1:\n"
        "add r0, sp, #12\n"
        "strb r1, [r0, #0]\n"
        "strb r2, [r0, #1]\n"
        "ldr r1, [sp, #32]\n"
        "str r1, [sp, #0]\n"
        "ldr r1, [sp, #36]\n"
        "str r1, [sp, #4]\n"
        "ldr r1, [sp, #8]\n"
        "ldr r2, [sp, #24]\n"
        "ldr r3, [sp, #28]\n"
        "bl OverworldVision_IsInView\n"
        "add sp, #16\n"
        "pop {r4, pc}\n");
}
#endif

static u8 OverworldBehaviorCondition_Reached(u32 now, u32 deadline)
{
    return now - deadline < 0x80000000u;
}

static void OverworldBehaviorCondition_ClearTarget(
    OverworldBehaviorConditionTargetReference *target)
{
    target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
}

static u8 OverworldBehaviorCondition_StateActive(
    const OverworldBehaviorConditionEntryState *state)
{
    return (state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE) != 0;
}

static void OverworldBehaviorCondition_SetStateActive(
    OverworldBehaviorConditionEntryState *state,
    u8 active)
{
    if (active) {
        state->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    } else {
        state->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    }
}

static u8 OverworldBehaviorCondition_StateHasTriggered(
    const OverworldBehaviorConditionEntryState *state)
{
    return (state->flags
        & OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED) != 0;
}

static void OverworldBehaviorCondition_SetStateHasTriggered(
    OverworldBehaviorConditionEntryState *state)
{
    state->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
}

static void OverworldBehaviorCondition_ClearStoredTarget(
    OverworldBehaviorConditionEntryState *state)
{
    state->targetKind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
}

static void OverworldBehaviorCondition_CaptureTarget(
    OverworldBehaviorConditionEntryState *state,
    const OverworldBehaviorConditionTargetReference *target)
{
    OverworldBehaviorCondition_ClearStoredTarget(state);
    state->targetKind = target->kind;
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        state->targetSlot = target->actor.slot;
        state->targetGeneration = target->actor.generation;
        state->targetEncounterGeneration =
            target->actor.encounterGeneration;
    }
}

static u8 OverworldBehaviorCondition_StoredTargetMatchesActor(
    const OverworldBehaviorConditionEntryState *state,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldActorHandle *actor)
{
    return state->targetKind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
        && actor->slot == state->targetSlot
        && actor->generation == state->targetGeneration
        && actor->encounterGeneration == state->targetEncounterGeneration
        && actor->fieldEpoch == world->subject.fieldEpoch
        && actor->mapGeneration == world->subject.mapGeneration;
}

static u8 OverworldBehaviorCondition_RestoreTarget(
    const OverworldBehaviorConditionEntryState *state,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionTargetReference *target,
    s16 *targetX,
    s16 *targetY)
{
    u8 i;

    OverworldBehaviorCondition_ClearTarget(target);
    *targetX = world->subjectX;
    *targetY = world->subjectY;
    if (state->targetKind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
        return 1;
    }
    if (state->targetKind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
        if (!world->playerValid) {
            return 0;
        }
        target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
        *targetX = world->playerX;
        *targetY = world->playerY;
        return 1;
    }
    if (state->targetKind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        return 0;
    }
    for (i = 0; i < world->actorCount; i++) {
        if ((input->eligibleActorMask & (1u << i)) != 0
            && world->actors[i].valid
            && OverworldBehaviorCondition_StoredTargetMatchesActor(
                state, world, &world->actors[i].actor)) {
            target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
            target->actor = world->actors[i].actor;
            *targetX = world->actors[i].x;
            *targetY = world->actors[i].y;
            return 1;
        }
    }
    return 0;
}

static u8 __attribute__((noinline)) OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED
OverworldBehaviorCondition_Truth(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionTargetReference *target)
{
    u16 bestDistance = 0xFFFF;
    u8 value = 0;
    u8 i;

    OverworldBehaviorCondition_ClearTarget(target);
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED) {
        u16 explicitMask = definition->terrainOverrideMask;
        u16 acceptedMask = definition->terrainMask & explicitMask;

        value = !(
            (explicitMask != 0
                && (world->subjectTerrainMask == 0
                    || (acceptedMask != 0
                        && (world->subjectTerrainMask & acceptedMask) == 0)
                    || (world->subjectTerrainMask
                        & (explicitMask & ~acceptedMask)) != 0))
            || (definition->minMovementSpeed != 0
                && world->subjectMovementSpeed
                    < definition->minMovementSpeed)
            || (definition->maxMovementSpeed != 0
                && world->subjectMovementSpeed
                    > definition->maxMovementSpeed));
    } else if (definition->kind
        == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED) {
        value = world->playerValid
            && (OverworldBehaviorCondition_UsesVision(definition)
                ? OverworldBehaviorCondition_CanSee(
                    definition,
                    world->subjectVisionRange,
                    world->subjectVisionOptions,
                    world->subjectX,
                    world->subjectY,
                    world->subjectFacing,
                    world->playerX,
                    world->playerY,
                    (world->playerFacingAndOcclusion
                        & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT)
                        != 0)
                : OverworldBehaviorCondition_InRange(
                    definition, world, world->playerX, world->playerY));
        if (value
            && definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER) {
            target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
        }
    } else if (definition->kind
            == OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT
        && definition->targetKind
            == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER) {
        value = world->playerValid
            && !OverworldBehaviorCondition_CanSee(
                    definition,
                    world->playerVisionRange,
                    world->playerVisionOptions,
                    world->playerX,
                    world->playerY,
                    world->playerFacingAndOcclusion
                        & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_FACING_MASK,
                    world->subjectX,
                    world->subjectY,
                    (world->playerFacingAndOcclusion
                        & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT)
                        != 0);
        if (value) {
            target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
        }
    } else {
        u8 inverse = definition->kind
            == OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT;

        for (i = 0; i < world->actorCount; i++) {
            const OverworldBehaviorConditionActorObservation *candidate =
                &world->actors[i];
            u8 matches;
            u16 distance;

            if ((input->eligibleActorMask & (1u << i)) == 0
                || !candidate->valid
                || OverworldBehaviorCondition_SameHandle(
                    &world->subject, &candidate->actor)) {
                continue;
            }
            if (inverse) {
                matches = !OverworldBehaviorCondition_CanSee(
                    definition,
                    candidate->visionRange,
                    candidate->visionOptions,
                    candidate->x,
                    candidate->y,
                    candidate->facingAndOcclusion
                        & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_FACING_MASK,
                    world->subjectX,
                    world->subjectY,
                    (candidate->facingAndOcclusion
                        & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT)
                        != 0);
            } else if (OverworldBehaviorCondition_UsesVision(definition)) {
                matches = OverworldBehaviorCondition_CanSee(
                        definition,
                        world->subjectVisionRange,
                        world->subjectVisionOptions,
                        world->subjectX,
                        world->subjectY,
                        world->subjectFacing,
                        candidate->x,
                        candidate->y,
                        (candidate->facingAndOcclusion
                            & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT)
                            != 0);
            } else {
                matches = OverworldBehaviorCondition_InRange(
                    definition, world, candidate->x, candidate->y);
            }
            if (!matches) {
                continue;
            }
            distance = OverworldBehaviorCondition_Distance(
                candidate->x - world->subjectX,
                candidate->y - world->subjectY);
            if (value && distance >= bestDistance) {
                continue;
            }
            value = 1;
            bestDistance = distance;
            if (definition->targetKind
                    == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR) {
                target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
                target->actor = candidate->actor;
            }
        }
    }
    if (value && input->chanceRoll >= definition->chance) {
        value = 0;
        OverworldBehaviorCondition_ClearTarget(target);
    }
    return value;
}

u8 OverworldBehaviorCondition_DefinitionValid(
    const OverworldBehaviorConditionDefinition *definition)
{
    if (definition->conditionId == OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY
        || definition->applicationIndex
            >= OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS
        || definition->kind
            > OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT
        || definition->activationMode
            > OVERWORLD_BEHAVIOR_CONDITION_TIMED
        || definition->targetKind
            > OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
        || definition->chance > 100
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_TIMED
            && definition->durationFrames == 0)
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE
            && (definition->durationFrames != 0
                || definition->cooldownFrames != 0))
        || definition->terrainMask > OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX
        || definition->terrainOverrideMask > OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX
        || (definition->minMovementSpeed && definition->maxMovementSpeed
            && definition->minMovementSpeed > definition->maxMovementSpeed)) {
        return 0;
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED) {
        return definition->targetKind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;
    }
    if (definition->rangeKind < OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE
        || definition->rangeKind > OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM) {
        return 0;
    }
    if (definition->rangeKind == OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT
        && (definition->distance || definition->reserved)) {
        return 0;
    }
    if (definition->rangeKind == OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM) {
        OverworldVisionSpec spec = { definition->distance, definition->reserved };

        if (!OverworldVision_IsValidSpec(&spec)) {
            return 0;
        }
    }
    return (0x6153u
        & (1u << (definition->kind * 4 + definition->targetKind))) != 0;
}

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluateEntry(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionEntryState *state,
    OverworldBehaviorConditionEntryResult *result)
{
    OverworldBehaviorConditionTargetReference truthTarget;
    OverworldBehaviorConditionTargetReference activeTarget;
    s16 targetX = 0;
    s16 targetY = 0;
    u8 truth;
    u8 wasActive;

#if !defined(OVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME)
    if (definition == NULL || input == NULL || world == NULL
        || state == NULL || result == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
#endif
    memset(result, 0, sizeof(*result));
    result->conditionId = definition->conditionId;
    result->applicationIndex = definition->applicationIndex;
    OverworldBehaviorCondition_ClearTarget(&result->target);
#if !defined(OVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME)
    if (!OverworldBehaviorCondition_DefinitionValid(definition)
        || world->actorCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || input->chanceRoll >= 100) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
#endif

    wasActive = OverworldBehaviorCondition_StateActive(state);
    OverworldBehaviorCondition_ClearTarget(&activeTarget);
    truth = OverworldBehaviorCondition_Truth(
        definition, input, world, &truthTarget);
    result->conditionTrue = truth;
    if (wasActive
        && !OverworldBehaviorCondition_RestoreTarget(
            state, input, world, &activeTarget, &targetX, &targetY)) {
        OverworldBehaviorCondition_SetStateActive(state, 0);
        OverworldBehaviorCondition_ClearStoredTarget(state);
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    }

    if (definition->activationMode
        == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE) {
        if (OverworldBehaviorCondition_StateActive(state)
            && state->targetKind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE
            && !OverworldBehaviorCondition_UsesVision(definition)
            && !OverworldBehaviorCondition_InRange(
                definition, world, targetX, targetY)) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        }
        if (OverworldBehaviorCondition_StateActive(state)
            && OverworldBehaviorCondition_UsesVision(definition)
            && truth
            && activeTarget.kind
                == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
            && (truthTarget.kind
                    != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                || !OverworldBehaviorCondition_SameHandle(
                    &activeTarget.actor, &truthTarget.actor))) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        }
        if (!truth
            || (definition->targetKind != OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE
                && truthTarget.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE)) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        } else if (!OverworldBehaviorCondition_StateActive(state)
            && !wasActive) {
            OverworldBehaviorCondition_SetStateActive(state, 1);
            OverworldBehaviorCondition_CaptureTarget(state, &truthTarget);
            activeTarget = truthTarget;
            result->triggered = 1;
        }
    } else {
        if (OverworldBehaviorCondition_StateActive(state)
            && OverworldBehaviorCondition_Reached(
                world->frame, state->activeUntil)) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        }
        if ((!OverworldBehaviorCondition_StateHasTriggered(state)
                || definition->cooldownFrames == 0
                || OverworldBehaviorCondition_Reached(
                    world->frame, state->cooldownUntil))
            && truth
            && (definition->targetKind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE
                || truthTarget.kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE)) {
            OverworldBehaviorCondition_SetStateActive(state, 1);
            state->activeUntil =
                world->frame + definition->durationFrames;
            state->cooldownUntil =
                world->frame + definition->cooldownFrames;
            OverworldBehaviorCondition_CaptureTarget(state, &truthTarget);
            OverworldBehaviorCondition_SetStateHasTriggered(state);
            activeTarget = truthTarget;
            result->triggered = 1;
        }
    }

    result->active = OverworldBehaviorCondition_StateActive(state);
    if (result->active) {
        result->target.kind = activeTarget.kind;
        if (activeTarget.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
            result->target.actor = activeTarget.actor;
        }
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

#ifndef OVERWORLD_BEHAVIOR_RUNTIME_ONLY
OverworldBehaviorConditionStatus OverworldBehaviorCondition_Evaluate(
    const OverworldBehaviorConditionDefinition *definitions,
    const OverworldBehaviorConditionEntryInput *inputs,
    OverworldBehaviorConditionEntryState *states,
    u16 count,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionResult *result)
{
    return OverworldBehaviorCondition_EvaluateWithResults(
        definitions,
        inputs,
        states,
        count,
        world,
        result,
        NULL);
}

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluateWithResults(
    const OverworldBehaviorConditionDefinition *definitions,
    const OverworldBehaviorConditionEntryInput *inputs,
    OverworldBehaviorConditionEntryState *states,
    u16 count,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionResult *result,
    OverworldBehaviorConditionEntryResult *entryResults)
{
    OverworldBehaviorConditionEntryResult entry;
    OverworldBehaviorConditionStatus status;
    u16 i;

    if (definitions == NULL || inputs == NULL || states == NULL
        || world == NULL || result == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    if (count > OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        || world->actorCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
    for (i = 0; i < count; i++) {
        if (!OverworldBehaviorCondition_DefinitionValid(&definitions[i])
            || inputs[i].chanceRoll >= 100) {
            return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
        }
    }
    memset(result, 0, sizeof(*result));
    result->resolvedTargetConditionId =
        OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    result->resolvedTargetSourceApplication =
        OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
    result->winningConditionId = OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    result->winningConditionSourceApplication =
        OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
    OverworldBehaviorCondition_ClearTarget(&result->resolvedTarget);
    for (i = 0; i < OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS; i++) {
        result->winningConditionIds[i] =
            OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
        OverworldBehaviorCondition_ClearTarget(&result->targets[i]);
    }
    for (i = 0; i < count; i++) {
        u8 application = definitions[i].applicationIndex;
        u32 bit;

        status = OverworldBehaviorCondition_EvaluateEntry(
            &definitions[i], &inputs[i], world, &states[i], &entry);
        if (status != OVERWORLD_BEHAVIOR_CONDITION_OK) {
            return status;
        }
        if (entryResults != NULL) {
            entryResults[i] = entry;
        }
        if (!entry.active) {
            continue;
        }
        bit = 1u << application;
        result->activeApplicationMask |= bit;
        if (entry.triggered) {
            result->triggeredApplicationMask |= bit;
        } else {
            result->triggeredApplicationMask &= ~bit;
        }
        result->winningConditionIds[application] = entry.conditionId;
        result->targets[application] = entry.target;
    }
    for (i = 0; i < OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS; i++) {
        if ((result->activeApplicationMask & (1u << i)) == 0) {
            continue;
        }
        result->winningConditionId = result->winningConditionIds[i];
        result->winningConditionSourceApplication = (u8)i;
        if (result->targets[i].kind
                != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
            result->resolvedTarget = result->targets[i];
            result->resolvedTargetConditionId = result->winningConditionIds[i];
            result->resolvedTargetSourceApplication = (u8)i;
        }
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}
#endif
