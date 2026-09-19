#include "overworld_population_model.h"

#define POPULATION_PHASE_NONE 0
#define POPULATION_PHASE_QUEUED 1
#define POPULATION_PHASE_DESPAWN 2
#define POPULATION_PHASE_REFILL 3
#define POPULATION_PHASE_REVEAL 4
#define POPULATION_PHASE_MASK 0x0F
#define POPULATION_DIRTY 0x80

static void OverworldPopulation_ClearState(
    OverworldPopulationState *state,
    u16 fieldEpoch,
    s16 centerX,
    s16 centerY)
{
    state->lastWorldEventSequence = 0;
    state->reservedWorldEventSequence = 0;
    state->centerX = centerX;
    state->centerY = centerY;
    state->fieldEpoch = fieldEpoch;
    state->refillTimer = 0;
    state->refillArmed = 0;
    state->maintenanceState = POPULATION_PHASE_NONE;
    state->fieldActive = 1;
    state->reserved = 0;
}

static u8 OverworldPopulation_HasPending(
    const OverworldPopulationState *state)
{
    return state->maintenanceState != POPULATION_PHASE_NONE;
}

static void OverworldPopulation_RequestMaintenance(
    OverworldPopulationState *state)
{
    if (state->maintenanceState == POPULATION_PHASE_NONE) {
        state->maintenanceState = POPULATION_PHASE_QUEUED;
    } else {
        state->maintenanceState |= POPULATION_DIRTY;
    }
}

static u8 OverworldPopulation_TakeWork(OverworldPopulationState *state)
{
    u8 phase = state->maintenanceState & POPULATION_PHASE_MASK;
    u8 work = OVERWORLD_POPULATION_WORK_NONE;

    if (phase == POPULATION_PHASE_QUEUED) {
        state->maintenanceState =
            (state->maintenanceState & POPULATION_DIRTY)
                | POPULATION_PHASE_DESPAWN;
    } else if (phase == POPULATION_PHASE_DESPAWN) {
        state->maintenanceState =
            (state->maintenanceState & POPULATION_DIRTY)
                | POPULATION_PHASE_REFILL;
        work = OVERWORLD_POPULATION_WORK_DESPAWN;
    } else if (phase == POPULATION_PHASE_REFILL) {
        state->maintenanceState =
            (state->maintenanceState & POPULATION_DIRTY)
                | POPULATION_PHASE_REVEAL;
        work = OVERWORLD_POPULATION_WORK_REFILL;
    } else if (phase == POPULATION_PHASE_REVEAL) {
        state->maintenanceState =
            (state->maintenanceState & POPULATION_DIRTY) != 0
                ? POPULATION_PHASE_QUEUED
                : POPULATION_PHASE_NONE;
        work = OVERWORLD_POPULATION_WORK_REVEAL;
    }
    return work;
}

static u8 OverworldPopulation_FieldMatches(
    const OverworldPopulationState *state,
    const OverworldPopulationInput *input)
{
    return input->fieldEpoch == 0 || input->fieldEpoch == state->fieldEpoch;
}

static OverworldPopulationDecision OverworldPopulation_AcceptWorldSequence(
    OverworldPopulationState *state,
    const OverworldPopulationInput *input)
{
    u32 distance;

    if (input->eventSequence == 0) {
        return OVERWORLD_POPULATION_DECISION_INVALID;
    }
    distance = input->eventSequence - state->lastWorldEventSequence;
    if ((s32)distance <= 0) {
        return distance == 0
            ? OVERWORLD_POPULATION_DECISION_DUPLICATE
            : OVERWORLD_POPULATION_DECISION_STALE_SEQUENCE;
    }
    state->lastWorldEventSequence = input->eventSequence;
    return OVERWORLD_POPULATION_DECISION_OK;
}

static OverworldPopulationDecision OverworldPopulation_ApplyFieldEvent(
    OverworldPopulationState *state,
    const OverworldPopulationInput *input,
    OverworldPopulationResult *result)
{
    OverworldPopulationDecision decision;

    if (input->event == OVERWORLD_POPULATION_FIELD_NONE
        || input->event > OVERWORLD_POPULATION_FIELD_DISCARD) {
        return OVERWORLD_POPULATION_DECISION_INVALID;
    }
    if (input->event == OVERWORLD_POPULATION_FIELD_REBIND) {
        if (input->fieldEpoch == 0) {
            return OVERWORLD_POPULATION_DECISION_INVALID;
        }
        decision = OverworldPopulation_AcceptWorldSequence(state, input);
        if (decision != OVERWORLD_POPULATION_DECISION_OK) {
            return decision;
        }
        if (state->centerX != input->logicalX
            || state->centerY != input->logicalY) {
            result->flags |= OVERWORLD_POPULATION_RESULT_REGION_CHANGED;
        }
        state->centerX = input->logicalX;
        state->centerY = input->logicalY;
        state->fieldEpoch = input->fieldEpoch;
        state->fieldActive = 0;
        OverworldPopulation_RequestMaintenance(state);
        result->flags |= OVERWORLD_POPULATION_RESULT_RECONCILE_DUE;
        return OVERWORLD_POPULATION_DECISION_OK;
    }
    if (!OverworldPopulation_FieldMatches(state, input)) {
        return OVERWORLD_POPULATION_DECISION_STALE_FIELD;
    }
    decision = OverworldPopulation_AcceptWorldSequence(state, input);
    if (decision != OVERWORLD_POPULATION_DECISION_OK) {
        return decision;
    }
    if (input->event == OVERWORLD_POPULATION_FIELD_SUSPEND) {
        state->fieldActive = 0;
        result->flags |= OVERWORLD_POPULATION_RESULT_FIELD_SUSPENDED;
    } else if (input->event == OVERWORLD_POPULATION_FIELD_RESUME) {
        state->fieldActive = 1;
    } else {
        state->fieldActive = 1;
    }
    return OVERWORLD_POPULATION_DECISION_OK;
}

static OverworldPopulationDecision OverworldPopulation_ApplyMotionSignal(
    OverworldPopulationState *state,
    const OverworldPopulationInput *input,
    OverworldPopulationResult *result)
{
    OverworldPopulationDecision decision;

    if (!OverworldPopulation_FieldMatches(state, input)) {
        return OVERWORLD_POPULATION_DECISION_STALE_FIELD;
    }
    decision = OverworldPopulation_AcceptWorldSequence(state, input);
    if (decision != OVERWORLD_POPULATION_DECISION_OK) {
        return decision;
    }
    if (input->kind == OVERWORLD_POPULATION_INPUT_COMMIT) {
        result->flags |= OVERWORLD_POPULATION_RESULT_COMMIT_OBSERVED;
        return OVERWORLD_POPULATION_DECISION_OK;
    }
    if ((input->flags & OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED) != 0
        && (state->centerX != input->logicalX
            || state->centerY != input->logicalY)) {
        state->centerX = input->logicalX;
        state->centerY = input->logicalY;
        result->flags |= OVERWORLD_POPULATION_RESULT_REGION_CHANGED;
    }
    return OVERWORLD_POPULATION_DECISION_OK;
}

static void OverworldPopulation_FillResult(
    const OverworldPopulationState *state,
    OverworldPopulationResult *result,
    OverworldPopulationDecision decision)
{
    result->decision = decision;
    result->refillTimer = state->refillTimer;
    result->pending = OverworldPopulation_HasPending(state);
    result->flags |= result->pending
        ? OVERWORLD_POPULATION_RESULT_WORK_PENDING
        : 0;
}

OverworldPopulationDecision OverworldPopulation_Apply(
    OverworldPopulationState *state,
    const OverworldPopulationInput *input,
    OverworldPopulationResult *result)
{
    OverworldPopulationDecision decision = OVERWORLD_POPULATION_DECISION_OK;

    if (state == 0 || input == 0 || result == 0) {
        return OVERWORLD_POPULATION_DECISION_INVALID;
    }
    result->decision = OVERWORLD_POPULATION_DECISION_INVALID;
    result->refillTimer = state->refillTimer;
    result->work = OVERWORLD_POPULATION_WORK_NONE;
    result->flags = 0;
    result->pending = OverworldPopulation_HasPending(state);
    result->reserved = 0;
    if (input->version != OVERWORLD_POPULATION_INPUT_VERSION
        || input->size != sizeof(*input)
        || input->kind > OVERWORLD_POPULATION_INPUT_FIELD_EVENT) {
        return OVERWORLD_POPULATION_DECISION_INVALID;
    }

    switch (input->kind) {
    case OVERWORLD_POPULATION_INPUT_RESET:
        OverworldPopulation_ClearState(
            state, input->fieldEpoch, input->logicalX, input->logicalY);
        break;
    case OVERWORLD_POPULATION_INPUT_FRAME:
        if (!OverworldPopulation_FieldMatches(state, input)) {
            decision = OVERWORLD_POPULATION_DECISION_STALE_FIELD;
        } else if (state->fieldActive
            && (input->flags & OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE) != 0
            && state->refillArmed) {
            if (state->refillTimer != 0) {
                state->refillTimer--;
            } else {
                state->refillArmed = 0;
                result->flags |= OVERWORLD_POPULATION_RESULT_REFILL_DUE;
            }
        }
        break;
    case OVERWORLD_POPULATION_INPUT_PATH_ADVANCE:
    case OVERWORLD_POPULATION_INPUT_COMMIT:
        decision = OverworldPopulation_ApplyMotionSignal(state, input, result);
        break;
    case OVERWORLD_POPULATION_INPUT_FIELD_EVENT:
        decision = OverworldPopulation_ApplyFieldEvent(state, input, result);
        break;
    case OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL:
        state->refillTimer = input->value;
        state->refillArmed = 1;
        break;
    case OVERWORLD_POPULATION_INPUT_REQUEST_MAINTENANCE:
        OverworldPopulation_RequestMaintenance(state);
        break;
    case OVERWORLD_POPULATION_INPUT_CANCEL_MAINTENANCE:
        state->maintenanceState = POPULATION_PHASE_NONE;
        break;
    case OVERWORLD_POPULATION_INPUT_TAKE_WORK:
        result->work = OverworldPopulation_TakeWork(state);
        break;
    case OVERWORLD_POPULATION_INPUT_QUERY:
        break;
    default:
        decision = OVERWORLD_POPULATION_DECISION_INVALID;
        break;
    }
    OverworldPopulation_FillResult(state, result, decision);
    return decision;
}
