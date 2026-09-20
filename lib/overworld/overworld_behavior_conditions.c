#include "overworld_behavior_conditions.h"

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

typedef struct OverworldBehaviorConditionTruth {
    OverworldBehaviorConditionTargetReference target;
    u8 value;
} OverworldBehaviorConditionTruth;

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
    return left->slot == right->slot
        && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

static u8 OverworldBehaviorCondition_InFacingLine(
    s32 dx,
    s32 dy,
    u8 distance,
    u8 facing)
{
    switch (facing) {
    case 0:
        return dx == 0 && dy < 0
            && OverworldBehaviorCondition_Abs(dy) <= distance;
    case 1:
        return dx == 0 && dy > 0
            && OverworldBehaviorCondition_Abs(dy) <= distance;
    case 2:
        return dy == 0 && dx < 0
            && OverworldBehaviorCondition_Abs(dx) <= distance;
    case 3:
        return dy == 0 && dx > 0
            && OverworldBehaviorCondition_Abs(dx) <= distance;
    default:
        return 0;
    }
}

static u8 OverworldBehaviorCondition_InCardinalLine(
    s32 dx,
    s32 dy,
    u8 distance)
{
    return ((dx == 0 && dy != 0)
            || (dy == 0 && dx != 0))
        && OverworldBehaviorCondition_Distance(dx, dy) <= distance;
}

static u8 OverworldBehaviorCondition_InRadius(
    s32 dx,
    s32 dy,
    u8 distance)
{
    return (dx != 0 || dy != 0)
        && OverworldBehaviorCondition_Abs(dx) <= distance
        && OverworldBehaviorCondition_Abs(dy) <= distance;
}

static u8 OverworldBehaviorCondition_InRange(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionWorldView *world,
    s16 x,
    s16 y)
{
    s32 dx = (s32)x - world->subjectX;
    s32 dy = (s32)y - world->subjectY;

    switch (definition->rangeKind) {
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_CARDINAL_LINE:
        return OverworldBehaviorCondition_InCardinalLine(
            dx, dy, definition->distance);
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS:
        return OverworldBehaviorCondition_InRadius(
            dx, dy, definition->distance);
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE_CLOSE_RADIUS:
        return OverworldBehaviorCondition_InFacingLine(
                dx, dy, definition->distance, world->subjectFacing)
            || OverworldBehaviorCondition_InRadius(dx, dy, 1);
    case OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE:
        return OverworldBehaviorCondition_InFacingLine(
            dx, dy, definition->distance, world->subjectFacing);
    default:
        return 0;
    }
}

static u8 OverworldBehaviorCondition_Reached(u32 now, u32 deadline)
{
    return now - deadline < 0x80000000u;
}

static void OverworldBehaviorCondition_ClearTarget(
    OverworldBehaviorConditionTargetReference *target)
{
    memset(target, 0, sizeof(*target));
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
    state->targetSlot = 0;
    state->targetGeneration = 0;
    state->targetEncounterGeneration = 0;
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

static OverworldBehaviorConditionTruth __attribute__((noinline))
OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED OverworldBehaviorCondition_Truth(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world)
{
    OverworldBehaviorConditionTruth truth;
    u16 bestDistance = 0xFFFF;
    u8 i;

    memset(&truth, 0, sizeof(truth));
    OverworldBehaviorCondition_ClearTarget(&truth.target);
    if (definition->kind == OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED) {
        u16 explicitMask = definition->terrainOverrideMask;
        u16 acceptedMask = definition->terrainMask & explicitMask;

        truth.value = !(
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
        truth.value = world->playerValid
            && OverworldBehaviorCondition_InRange(
                definition, world, world->playerX, world->playerY);
        if (truth.value
            && definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER) {
            truth.target.kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
        }
    } else if (definition->kind
        == OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED) {
        for (i = 0; i < world->actorCount; i++) {
            const OverworldBehaviorConditionActorObservation *candidate =
                &world->actors[i];
            u16 distance;

            if ((input->eligibleActorMask & (1u << i)) == 0
                || !candidate->valid
                || OverworldBehaviorCondition_SameHandle(
                    &world->subject, &candidate->actor)
                || !OverworldBehaviorCondition_InRange(
                    definition, world, candidate->x, candidate->y)) {
                continue;
            }
            distance = OverworldBehaviorCondition_Distance(
                candidate->x - world->subjectX,
                candidate->y - world->subjectY);
            if (truth.value && distance >= bestDistance) {
                continue;
            }
            truth.value = 1;
            bestDistance = distance;
            if (definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR) {
                truth.target.kind =
                    OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
                truth.target.actor = candidate->actor;
            }
        }
    }
    if (truth.value
        && definition->chance < 100
        && input->chanceRoll >= definition->chance) {
        truth.value = 0;
        OverworldBehaviorCondition_ClearTarget(&truth.target);
    }
    return truth;
}

u8 OverworldBehaviorCondition_DefinitionValid(
    const OverworldBehaviorConditionDefinition *definition)
{
    if (definition->conditionId == OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY
        || definition->applicationIndex
            >= OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS
        || definition->kind
            > OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED
        || definition->activationMode
            > OVERWORLD_BEHAVIOR_CONDITION_TIMED
        || definition->targetKind
            > OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
        || definition->chance > 100
        || (definition->kind != OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED
            && (definition->rangeKind
                    < OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE
                || definition->rangeKind
                    > OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS))
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_TIMED
            && definition->durationFrames == 0)
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE
            && (definition->durationFrames != 0
                || definition->cooldownFrames != 0))
        || definition->terrainMask
            > OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX
        || definition->terrainOverrideMask
            > OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX
        || (definition->minMovementSpeed != 0
            && definition->maxMovementSpeed != 0
            && definition->minMovementSpeed
                > definition->maxMovementSpeed)
        || (definition->targetKind
                != OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE
            && definition->targetKind != definition->kind + 1)) {
        return 0;
    }
    return 1;
}

static u8 __attribute__((noinline)) OVERWORLD_BEHAVIOR_CONDITION_SIZE_OPTIMIZED
OverworldBehaviorCondition_RequiredTargetAvailable(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionTruth *truth)
{
    if (definition->targetKind
            == OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE) {
        return 1;
    }
    return truth->target.kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
}

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluateEntry(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionEntryState *state,
    OverworldBehaviorConditionEntryResult *result)
{
    OverworldBehaviorConditionTruth truth;
    OverworldBehaviorConditionTargetReference activeTarget;
    s16 targetX = 0;
    s16 targetY = 0;
    u8 cooldownFinished;
    u8 wasActive;

    if (definition == NULL || input == NULL || world == NULL
        || state == NULL || result == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    memset(result, 0, sizeof(*result));
    result->conditionId = definition->conditionId;
    result->applicationIndex = definition->applicationIndex;
    OverworldBehaviorCondition_ClearTarget(&result->target);
    if (!OverworldBehaviorCondition_DefinitionValid(definition)
        || world->actorCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS
        || input->chanceRoll >= 100) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    }

    wasActive = OverworldBehaviorCondition_StateActive(state);
    OverworldBehaviorCondition_ClearTarget(&activeTarget);
    truth = OverworldBehaviorCondition_Truth(definition, input, world);
    result->conditionTrue = truth.value;
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
            && !OverworldBehaviorCondition_InRange(
                definition, world, targetX, targetY)) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        }
        if (!truth.value
            || !OverworldBehaviorCondition_RequiredTargetAvailable(
                definition, &truth)) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        } else if (!OverworldBehaviorCondition_StateActive(state)
            && !wasActive) {
            OverworldBehaviorCondition_SetStateActive(state, 1);
            OverworldBehaviorCondition_CaptureTarget(state, &truth.target);
            activeTarget = truth.target;
            result->triggered = 1;
        }
    } else {
        if (OverworldBehaviorCondition_StateActive(state)
            && OverworldBehaviorCondition_Reached(
                world->frame, state->activeUntil)) {
            OverworldBehaviorCondition_SetStateActive(state, 0);
            OverworldBehaviorCondition_ClearStoredTarget(state);
        }
        cooldownFinished = !OverworldBehaviorCondition_StateHasTriggered(state)
            || definition->cooldownFrames == 0
            || OverworldBehaviorCondition_Reached(
                world->frame, state->cooldownUntil);
        if (cooldownFinished
            && truth.value
            && OverworldBehaviorCondition_RequiredTargetAvailable(
                definition, &truth)) {
            OverworldBehaviorCondition_SetStateActive(state, 1);
            state->activeUntil =
                world->frame + definition->durationFrames;
            state->cooldownUntil =
                world->frame + definition->cooldownFrames;
            OverworldBehaviorCondition_CaptureTarget(state, &truth.target);
            OverworldBehaviorCondition_SetStateHasTriggered(state);
            activeTarget = truth.target;
            result->triggered = 1;
        }
    }

    result->active = OverworldBehaviorCondition_StateActive(state);
    if (result->active) {
        result->target = activeTarget;
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
