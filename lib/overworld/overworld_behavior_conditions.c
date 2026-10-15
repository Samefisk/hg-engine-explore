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


/* The combined native unit shares one fixed Query image. These branches move
 * with that image and need no absolute local call pointer. */
#if defined(__arm__)
#define CONDITION_LOCAL_CALL __attribute__((short_call))
#else
#define CONDITION_LOCAL_CALL
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

static u8 __attribute__((noinline)) CONDITION_LOCAL_CALL OverworldBehaviorCondition_SameHandle(
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

static u8 CONDITION_LOCAL_CALL OverworldBehaviorCondition_InRange(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionWorldView *world,
    s16 x,
    s16 y)
{
    s32 dx = (s32)x - world->subjectX;
    s32 dy = (s32)y - world->subjectY;
    u16 ax = OverworldBehaviorCondition_Abs(dx);
    u16 ay = OverworldBehaviorCondition_Abs(dy);

    if (dx == 0 && dy == 0) {
        return definition->rangeKind == OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS
            && (definition->reserved & OVERWORLD_BEHAVIOR_CONDITION_RADIUS_SAME_TILE);
    }
    if (ax > definition->distance || ay > definition->distance) {
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
        if (world->subjectFacing < 2) {
            return dx == 0
                && (world->subjectFacing == 0 ? dy < 0 : dy > 0);
        }
        return world->subjectFacing < 4
            && dy == 0
            && (world->subjectFacing == 2 ? dx < 0 : dx > 0);
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

static u8 OverworldBehaviorCondition_FactsMatch(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionWorldView *world)
{
    u8 facts;

    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED) {
        return 1;
    }
    facts = world->reserved[0];
    return (facts & definition->terrainMask) == definition->terrainMask
        && (facts & definition->terrainOverrideMask) == 0;
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
CONDITION_LOCAL_CALL OverworldBehaviorCondition_CanSee(
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
CONDITION_LOCAL_CALL OverworldBehaviorCondition_CanSee(
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

static void __attribute__((noinline)) CONDITION_LOCAL_CALL OverworldBehaviorCondition_Deactivate(
    OverworldBehaviorConditionEntryState *state)
{
    OverworldBehaviorCondition_SetStateActive(state, 0);
    state->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING;
    OverworldBehaviorCondition_ClearStoredTarget(state);
}

static void __attribute__((noinline)) CONDITION_LOCAL_CALL OverworldBehaviorCondition_CaptureTarget(
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
CONDITION_LOCAL_CALL __attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,no-if-conversion,no-tree-loop-im,no-schedule-insns2"))) OverworldBehaviorCondition_FindActor(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionTargetReference *target,
    u8 playerOpened)
{
    u16 bestDistance = 0xFFFF;
    u8 found = 0;
    u8 inverse = definition->kind
        == OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT;
    u8 i;

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
        if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED) {
            matches = (candidate->facingAndOcclusion
                & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE) != 0;
        } else if (playerOpened) {
            matches = 1;
        } else if (inverse) {
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
        if (input->reserved == OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY) {
            /* This private pass returns all candidate slots for native
             * traces. It cannot capture or publish this transient value. */
            if (candidate->actor.slot < OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS)
                target->actor.slot |= 1u << candidate->actor.slot;
            found = 1;
            continue;
        }
        distance = OverworldBehaviorCondition_Distance(
            candidate->x - world->subjectX,
            candidate->y - world->subjectY);
        if (found && distance >= bestDistance) {
            continue;
        }
        found = 1;
        bestDistance = distance;
        if (definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR) {
            target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
            target->actor = candidate->actor;
        }
    }
    return found;
}

static u8 __attribute__((noinline)) OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED
CONDITION_LOCAL_CALL __attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,no-if-conversion,no-tree-loop-im,no-schedule-insns2"))) OverworldBehaviorCondition_Truth(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionTargetReference *target)
{
    u8 value = 0;

    OverworldBehaviorCondition_ClearTarget(target);
    target->actor.slot = 0;
    if (input->chanceRoll >= definition->chance) {
        return 0;
    }
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
        if (value) {
            if (definition->targetKind
                    == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER) {
                target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
            } else if (definition->targetKind
                    == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR) {
                /* The player opens the intent. Cargo selection is map-wide;
                 * the actor pool and runtime eligibility filter the mask. */
                value = OverworldBehaviorCondition_FindActor(
                    definition, input, world, target, 1);
            }
        }
    } else if (definition->kind
        == OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED) {
        value = (world->playerFacingAndOcclusion
            & OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED) != 0;
        if (value && definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER) {
            value = world->playerValid;
            target->kind = value ? OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER
                : OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
        }
    } else if (definition->kind
        == OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS) {
        value = definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
            ? OverworldBehaviorCondition_FindActor(
                definition, input, world, target, 1)
            : 1;
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
        value = OverworldBehaviorCondition_FindActor(
            definition, input, world, target, 0);
    }
    return value;
}

u8 CONDITION_LOCAL_CALL __attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,no-if-conversion,no-tree-loop-im,no-schedule-insns2,no-tree-dominator-opts"))) OverworldBehaviorCondition_DefinitionValid(
    const OverworldBehaviorConditionDefinition *definition)
{
    if (definition->conditionId == OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY
        || definition->applicationIndex
            >= OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS
        || definition->kind
            > OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED
        || definition->activationMode
            > OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH
        || definition->targetKind
            > OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
        || definition->chance > 100
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_TIMED
            ? definition->durationFrames == 0
            : (definition->durationFrames != 0
                || (definition->activationMode
                        == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE
                    && definition->cooldownFrames != 0)))
        || ((definition->terrainMask | definition->terrainOverrideMask)
            & ~OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX) != 0
        || (definition->maxMovementSpeed
            && definition->minMovementSpeed > definition->maxMovementSpeed)) {
        return 0;
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED) {
        return definition->targetKind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;
    }
    if (((definition->terrainMask | definition->terrainOverrideMask)
            & ~OVERWORLD_BEHAVIOR_ACTOR_FACT_MASK) != 0
        || (definition->terrainMask & definition->terrainOverrideMask) != 0) {
        return 0;
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS) {
        return definition->targetKind != OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER
            && definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED) {
        return definition->targetKind == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
            && definition->activationMode == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE
            && definition->rangeKind == 0 && definition->distance == 0
            && definition->reserved == 0;
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED) {
        return definition->targetKind != OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
            && definition->rangeKind == 0 && definition->distance == 0
            && definition->reserved == 0 && definition->chance == 100
            && definition->minMovementSpeed == 0 && definition->maxMovementSpeed == 0;
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
        if (definition->distance == 0
            || definition->distance > OVERWORLD_VISION_MAX_RANGE
            || (definition->reserved & ~OVERWORLD_VISION_OPTIONS_MASK) != 0
            || (definition->reserved & OVERWORLD_VISION_CONE_MASK) == 0) {
            return 0;
        }
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED) {
        return 1;
    }
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED) {
        return definition->targetKind
            != OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    }
    return definition->targetKind
        != OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;
}

OverworldBehaviorConditionStatus CONDITION_LOCAL_CALL __attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,no-if-conversion,no-tree-loop-im,no-schedule-insns2"))) OverworldBehaviorCondition_EvaluateEntry(
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
#if !defined(OVERWORLD_BEHAVIOR_CONDITION_COMBINED_RUNTIME)
    if (!OverworldBehaviorCondition_DefinitionValid(definition)
        || world->actorCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || input->chanceRoll >= 100
        || input->reserved > OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }
#endif

    wasActive = OverworldBehaviorCondition_StateActive(state);
    /* A fact gate is a lifetime guard even for a timed condition. A picked-up
     * target must retire the search profile at this intent boundary. */
    if (!OverworldBehaviorCondition_FactsMatch(definition, world)) {
        if (input->reserved != OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY)
            OverworldBehaviorCondition_Deactivate(state);
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    }
    if (input->reserved == OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY
        && definition->activationMode == OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH
        && (wasActive || (!(state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM)
            && OverworldBehaviorCondition_StateHasTriggered(state)
            && !OverworldBehaviorCondition_Reached(world->frame, state->cooldownUntil))))
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    truth = OverworldBehaviorCondition_Truth(
        definition, input, world, &truthTarget);
    result->conditionTrue = truth;
    if (input->reserved == OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY) {
        result->target.actor.slot = truthTarget.actor.slot;
        return OVERWORLD_BEHAVIOR_CONDITION_OK;
    }
    if (definition->activationMode
            == OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH) {
        state->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_UNTIL_CRASH;
        if ((state->flags
                & OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING) != 0) {
            OverworldBehaviorCondition_Deactivate(state);
            state->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING;
            state->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM;
            state->cooldownUntil = world->frame + definition->cooldownFrames;
            return OVERWORLD_BEHAVIOR_CONDITION_OK;
        }
        if ((state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM) != 0) {
            if (!truth && OverworldBehaviorCondition_Reached(
                    world->frame, state->cooldownUntil)) {
                state->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM;
            }
            return OVERWORLD_BEHAVIOR_CONDITION_OK;
        }
    }
    if (wasActive
        && !OverworldBehaviorCondition_RestoreTarget(
            state, input, world, &activeTarget, &targetX, &targetY)) {
        OverworldBehaviorCondition_Deactivate(state);
        return OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
    }

    if (definition->activationMode
        == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE) {
        if (!truth
            || (definition->targetKind != OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE
                && truthTarget.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE)) {
            OverworldBehaviorCondition_Deactivate(state);
        } else if (wasActive) {
            u8 usesVision = OverworldBehaviorCondition_UsesVision(definition);

            if ((!usesVision
                    && definition->kind != OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS
                    && definition->kind != OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED
                    && definition->kind != OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED
                    && state->targetKind
                        != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE
                    && !OverworldBehaviorCondition_InRange(
                        definition, world, targetX, targetY))
                || (usesVision
                    && activeTarget.kind
                        == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                    && (truthTarget.kind
                            != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
                        || !OverworldBehaviorCondition_SameHandle(
                            &activeTarget.actor, &truthTarget.actor)))) {
                OverworldBehaviorCondition_Deactivate(state);
            }
        } else {
            OverworldBehaviorCondition_SetStateActive(state, 1);
            OverworldBehaviorCondition_CaptureTarget(state, &truthTarget);
            activeTarget = truthTarget;
            result->triggered = 1;
        }
    } else if (definition->activationMode
            == OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH) {
        if (!wasActive && truth
            && (!OverworldBehaviorCondition_StateHasTriggered(state)
                || OverworldBehaviorCondition_Reached(
                    world->frame, state->cooldownUntil))) {
            OverworldBehaviorCondition_SetStateActive(state, 1);
            OverworldBehaviorCondition_SetStateHasTriggered(state);
            OverworldBehaviorCondition_CaptureTarget(state, &truthTarget);
            state->activeUntil = 0;
            activeTarget = truthTarget;
            result->triggered = 1;
        }
    } else {
        if (OverworldBehaviorCondition_StateActive(state)
            && OverworldBehaviorCondition_Reached(
                world->frame, state->activeUntil)) {
            OverworldBehaviorCondition_Deactivate(state);
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
        if (input->reserved == OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE) {
            if (result->triggered)
                state->flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING;
        } else if (state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING) {
            result->triggered = 1;
            state->flags &= ~OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING;
        }
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
