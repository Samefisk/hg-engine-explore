#include "overworld_behavior_conditions.h"

#include <string.h>

typedef struct OverworldBehaviorConditionTruth {
    OverworldBehaviorConditionTargetReference target;
    u8 value;
} OverworldBehaviorConditionTruth;

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
    return (s32)(now - deadline) >= 0;
}

static void OverworldBehaviorCondition_ClearTarget(
    OverworldBehaviorConditionTargetReference *target)
{
    memset(target, 0, sizeof(*target));
    target->kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
}

static u8 OverworldBehaviorCondition_TargetValid(
    const OverworldBehaviorConditionTargetReference *target,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world)
{
    u8 i;

    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
        return 1;
    }
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
        return world->playerValid != 0;
    }
    if (target->kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        return 0;
    }
    for (i = 0; i < world->actorCount; i++) {
        if ((input->eligibleActorMask & (1u << i)) != 0
            && world->actors[i].valid
            && OverworldBehaviorCondition_SameHandle(
                &target->actor, &world->actors[i].actor)) {
            return 1;
        }
    }
    return 0;
}

static u8 OverworldBehaviorCondition_CapturedTargetInRange(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldBehaviorConditionTargetReference *target)
{
    u8 i;

    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
        return 1;
    }
    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
        return world->playerValid
            && OverworldBehaviorCondition_InRange(
                definition, world, world->playerX, world->playerY);
    }
    if (target->kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        return 0;
    }
    for (i = 0; i < world->actorCount; i++) {
        if ((input->eligibleActorMask & (1u << i)) != 0
            && world->actors[i].valid
            && OverworldBehaviorCondition_SameHandle(
                &target->actor, &world->actors[i].actor)
            && OverworldBehaviorCondition_InRange(
                definition,
                world,
                world->actors[i].x,
                world->actors[i].y)) {
            return 1;
        }
    }
    return 0;
}

static OverworldBehaviorConditionTruth OverworldBehaviorCondition_Truth(
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

static u8 OverworldBehaviorCondition_DefinitionValid(
    const OverworldBehaviorConditionDefinition *definition)
{
    if (definition->applicationIndex
            >= OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS
        || definition->kind
            > OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED
        || definition->activationMode
            > OVERWORLD_BEHAVIOR_CONDITION_TIMED
        || definition->targetKind
            > OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR
        || definition->chance > 100
        || (definition->kind != OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED
            && definition->rangeKind
                > OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE)
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_TIMED
            && definition->durationFrames == 0)
        || (definition->activationMode
                == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE
            && (definition->durationFrames != 0
                || definition->cooldownFrames != 0))
        || (definition->kind
                == OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED
            && definition->targetKind
                != OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE)
        || (definition->kind
                == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED
            && definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR)
        || (definition->kind
                == OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED
            && definition->targetKind
                == OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER)) {
        return 0;
    }
    return 1;
}

static u8 OverworldBehaviorCondition_RequiredTargetAvailable(
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
    u8 targetValid;
    u8 cooldownFinished;

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

    truth = OverworldBehaviorCondition_Truth(definition, input, world);
    result->conditionTrue = truth.value;
    targetValid = OverworldBehaviorCondition_TargetValid(
        &state->target, input, world);
    if (state->active && !targetValid) {
        state->active = 0;
        OverworldBehaviorCondition_ClearTarget(&state->target);
    }

    if (definition->activationMode
        == OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE) {
        if (state->active
            && !OverworldBehaviorCondition_CapturedTargetInRange(
                definition, input, world, &state->target)) {
            state->active = 0;
            OverworldBehaviorCondition_ClearTarget(&state->target);
        }
        if (!truth.value
            || !OverworldBehaviorCondition_RequiredTargetAvailable(
                definition, &truth)) {
            state->active = 0;
            OverworldBehaviorCondition_ClearTarget(&state->target);
        } else if (!state->active) {
            state->active = 1;
            state->target = truth.target;
            result->triggered = 1;
        }
    } else {
        if (state->active
            && OverworldBehaviorCondition_Reached(
                world->frame, state->activeUntil)) {
            state->active = 0;
            OverworldBehaviorCondition_ClearTarget(&state->target);
        }
        cooldownFinished = !state->hasTriggered
            || definition->cooldownFrames == 0
            || OverworldBehaviorCondition_Reached(
                world->frame, state->cooldownUntil);
        if (cooldownFinished
            && truth.value
            && OverworldBehaviorCondition_RequiredTargetAvailable(
                definition, &truth)) {
            state->active = 1;
            state->activeUntil =
                world->frame + definition->durationFrames;
            state->cooldownUntil =
                world->frame + definition->cooldownFrames;
            state->target = truth.target;
            state->hasTriggered = 1;
            result->triggered = 1;
        }
    }

    result->active = state->active;
    if (state->active) {
        result->target = state->target;
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}

OverworldBehaviorConditionStatus OverworldBehaviorCondition_Evaluate(
    const OverworldBehaviorConditionDefinition *definitions,
    const OverworldBehaviorConditionEntryInput *inputs,
    OverworldBehaviorConditionEntryState *states,
    u16 count,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionResult *result)
{
    OverworldBehaviorConditionEntryResult entry;
    OverworldBehaviorConditionStatus status;
    u16 i;

    if (definitions == NULL || inputs == NULL || states == NULL
        || world == NULL || result == NULL) {
        return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;
    }
    memset(result, 0, sizeof(*result));
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
        if (!entry.active) {
            continue;
        }
        bit = 1u << application;
        result->activeApplicationMask |= bit;
        if (entry.triggered) {
            result->triggeredApplicationMask |= bit;
        }
        result->winningConditionIds[application] = entry.conditionId;
        result->targets[application] = entry.target;
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}
