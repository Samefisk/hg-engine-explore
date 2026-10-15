#include "overworld_population_model.h"

#include <stdio.h>
#include <stddef.h>
#include <string.h>

static int sFailures;

#define CHECK(condition, label) \
    do { \
        if (!(condition)) { \
            fprintf(stderr, "FAIL: %s\n", label); \
            sFailures++; \
        } \
    } while (0)

static OverworldPopulationInput MakeInput(u8 kind, u16 fieldEpoch)
{
    OverworldPopulationInput input;

    memset(&input, 0, sizeof(input));
    input.version = OVERWORLD_POPULATION_INPUT_VERSION;
    input.size = sizeof(input);
    input.kind = kind;
    input.fieldEpoch = fieldEpoch;
    return input;
}

static OverworldPopulationDecision Apply(
    OverworldPopulationState *state,
    OverworldPopulationInput *input,
    OverworldPopulationResult *result)
{
    return OverworldPopulation_Apply(state, input, result);
}

static void Reset(
    OverworldPopulationState *state,
    u16 fieldEpoch,
    s16 x,
    s16 y)
{
    OverworldPopulationInput input = MakeInput(
        OVERWORLD_POPULATION_INPUT_RESET, fieldEpoch);
    OverworldPopulationResult result;

    memset(state, 0xA5, sizeof(*state));
    input.logicalX = x;
    input.logicalY = y;
    CHECK(Apply(state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK,
        "population reset succeeds");
}

static void CheckExactRefillCadence(void)
{
    OverworldPopulationState state;
    OverworldPopulationResult result;
    OverworldPopulationInput input;

    Reset(&state, 7, 10, 11);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL, 7);
    input.value = 2;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.refillArmed
            && result.refillTimer == 2,
        "refill keeps the exact authored delay");

    input = MakeInput(OVERWORLD_POPULATION_INPUT_FRAME, 7);
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && result.refillTimer == 2,
        "ineligible frames do not change cadence");
    input.flags = OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && result.refillTimer == 1
            && !(result.flags & OVERWORLD_POPULATION_RESULT_REFILL_DUE),
        "first eligible frame decrements once");
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && result.refillTimer == 0
            && !(result.flags & OVERWORLD_POPULATION_RESULT_REFILL_DUE),
        "zero is retained for the old final wait frame");
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && (result.flags & OVERWORLD_POPULATION_RESULT_REFILL_DUE)
            && !state.refillArmed,
        "refill becomes due on the same frame as the old timer");
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && !(result.flags & OVERWORLD_POPULATION_RESULT_REFILL_DUE),
        "refill due is published once");
}

static void CheckBoundedWorkOrderAndDirtyReplay(void)
{
    OverworldPopulationState state;
    OverworldPopulationResult result;
    OverworldPopulationInput input;

    Reset(&state, 3, 0, 0);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL, 3);
    input.value = 31;
    (void)Apply(&state, &input, &result);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_REQUEST_MAINTENANCE, 3);
    (void)Apply(&state, &input, &result);
    CHECK(result.pending
            && result.work == OVERWORLD_POPULATION_WORK_NONE
            && state.refillArmed
            && result.refillTimer == 31,
        "maintenance request queues work without canceling refill cadence");

    input = MakeInput(OVERWORLD_POPULATION_INPUT_FRAME, 3);
    input.flags = OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE;
    (void)Apply(&state, &input, &result);
    CHECK(state.refillArmed && result.refillTimer == 30,
        "maintenance leaves the next refill timer live");

    input = MakeInput(OVERWORLD_POPULATION_INPUT_TAKE_WORK, 3);
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_NONE && result.pending,
        "queued phase preserves the old one-frame preparation");
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_DESPAWN,
        "first bounded item is despawn");

    input.kind = OVERWORLD_POPULATION_INPUT_REQUEST_MAINTENANCE;
    (void)Apply(&state, &input, &result);
    input.kind = OVERWORLD_POPULATION_INPUT_TAKE_WORK;
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_REFILL,
        "dirty request does not reorder the active pass");
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_REVEAL && result.pending,
        "reveal finishes one pass and retains dirty work");
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_NONE && result.pending,
        "dirty replay starts with the same preparation frame");
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_DESPAWN,
        "dirty replay restarts at despawn");

    input.kind = OVERWORLD_POPULATION_INPUT_CANCEL_MAINTENANCE;
    (void)Apply(&state, &input, &result);
    CHECK(!result.pending && result.work == OVERWORLD_POPULATION_WORK_NONE,
        "cancel removes all queued work");
}

static void CheckExplicitPathAndCommitInputs(void)
{
    OverworldPopulationState state;
    OverworldPopulationResult result;
    OverworldPopulationInput input;

    Reset(&state, 9, 2, 2);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_PATH_ADVANCE, 9);
    input.eventSequence = 100;
    input.logicalX = 3;
    input.logicalY = 2;
    input.actorSlot = 4;
    input.actorRole = 1;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.centerX == 2
            && !(result.flags & OVERWORLD_POPULATION_RESULT_REGION_CHANGED),
        "non-player path advance is observed without moving the region");

    input.eventSequence = 101;
    input.actorRole = 3;
    input.flags = OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.centerX == 3
            && (result.flags & OVERWORLD_POPULATION_RESULT_REGION_CHANGED),
        "mounted authority path advance moves the player region");
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_DUPLICATE
            && state.centerX == 3,
        "duplicate path input is idempotent");

    input.eventSequence = 99;
    input.logicalX = 8;
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_STALE_SEQUENCE
            && state.centerX == 3,
        "older path input cannot rewind the population center");

    input = MakeInput(OVERWORLD_POPULATION_INPUT_COMMIT, 9);
    input.eventSequence = 200;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && (result.flags & OVERWORLD_POPULATION_RESULT_COMMIT_OBSERVED),
        "terminal commit is an explicit population input");
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_DUPLICATE
            && !(result.flags & OVERWORLD_POPULATION_RESULT_COMMIT_OBSERVED),
        "duplicate commit does not publish twice");

    input.eventSequence = 201;
    input.fieldEpoch = 8;
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_STALE_FIELD
            && state.lastWorldEventSequence == 200,
        "stale field input cannot mutate population state");
}

static void CheckOneWrapSafeWorldSequence(void)
{
    OverworldPopulationState state;
    OverworldPopulationResult result;
    OverworldPopulationInput input;

    Reset(&state, 4, 0, 0);
    state.lastWorldEventSequence = 0xFFFFFFFDu;
    input = MakeInput(OVERWORLD_POPULATION_INPUT_PATH_ADVANCE, 4);
    input.flags = OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED;
    input.logicalX = 1;
    input.eventSequence = 0xFFFFFFFEu;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.lastWorldEventSequence == 0xFFFFFFFEu,
        "world sequence accepts a value before wrap");

    input.kind = OVERWORLD_POPULATION_INPUT_COMMIT;
    input.eventSequence = 1;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.lastWorldEventSequence == 1,
        "world sequence advances across zero without ambiguity");

    input.kind = OVERWORLD_POPULATION_INPUT_PATH_ADVANCE;
    input.eventSequence = 0xFFFFFFFDu;
    input.logicalX = 9;
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_STALE_SEQUENCE
            && state.centerX == 1,
        "pre-wrap replay is stale after wrap");

    input.eventSequence = 0;
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_INVALID,
        "zero remains outside the world sequence");
}

static void CheckFieldLifecycleAndPausedTimer(void)
{
    OverworldPopulationState state;
    OverworldPopulationResult result;
    OverworldPopulationInput input;

    Reset(&state, 5, 1, 1);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL, 5);
    input.value = 1;
    (void)Apply(&state, &input, &result);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_FIELD_EVENT, 5);
    input.event = OVERWORLD_POPULATION_FIELD_SUSPEND;
    input.eventSequence = 1;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && (result.flags & OVERWORLD_POPULATION_RESULT_FIELD_SUSPENDED),
        "field suspend is explicit");
    input = MakeInput(OVERWORLD_POPULATION_INPUT_FRAME, 5);
    input.flags = OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE;
    (void)Apply(&state, &input, &result);
    CHECK(result.refillTimer == 1,
        "suspended fields pause the refill timer");

    input = MakeInput(OVERWORLD_POPULATION_INPUT_FIELD_EVENT, 6);
    input.event = OVERWORLD_POPULATION_FIELD_REBIND;
    input.eventSequence = 2;
    input.logicalX = 8;
    input.logicalY = 9;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.fieldEpoch == 6
            && state.centerX == 8
            && state.centerY == 9
            && state.refillTimer == 1 && state.refillArmed
            && (result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE)
            && result.pending,
        "field rebind updates region and queues one reconciliation");
    input.event = OVERWORLD_POPULATION_FIELD_RESUME;
    input.eventSequence = 3;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.fieldActive,
        "field resume restarts eligible frame time");
    input = MakeInput(OVERWORLD_POPULATION_INPUT_FRAME, 6);
    input.flags = OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE;
    (void)Apply(&state, &input, &result);
    CHECK(state.refillArmed && result.refillTimer == 0
            && !(result.flags & OVERWORLD_POPULATION_RESULT_REFILL_DUE),
        "rebind retains the old wait and resumes its remaining frame");
    (void)Apply(&state, &input, &result);
    CHECK(!state.refillArmed
            && (result.flags & OVERWORLD_POPULATION_RESULT_REFILL_DUE),
        "map crossing cannot bypass the carried wait expiry");
    input = MakeInput(OVERWORLD_POPULATION_INPUT_FIELD_EVENT, 6);
    input.event = OVERWORLD_POPULATION_FIELD_DISCARD;
    input.eventSequence = 4;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.fieldActive
            && result.pending
            && !(result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "discard finalizes the one reconciliation queued by rebind");
    input.event = 0xFF;
    input.eventSequence = 5;
    CHECK(Apply(&state, &input, &result)
            == OVERWORLD_POPULATION_DECISION_INVALID
            && state.lastWorldEventSequence == 4,
        "invalid field event cannot consume the world sequence");
    input.kind = OVERWORLD_POPULATION_INPUT_TAKE_WORK;
    (void)Apply(&state, &input, &result);
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_DESPAWN,
        "discard reconciliation starts one normal work pass");
    (void)Apply(&state, &input, &result);
    (void)Apply(&state, &input, &result);
    CHECK(result.work == OVERWORLD_POPULATION_WORK_REVEAL && !result.pending,
        "discard reconciliation does not create a dirty second pass");
}

static void CheckNativePlayerRequestsMaintenance(void)
{
    OverworldPopulationState state;
    OverworldPopulationState before;
    OverworldPopulationResult result;
    OverworldPopulationInput input;
    u8 phase;

    Reset(&state, 7, 585, 411);
    input = MakeInput(OVERWORLD_POPULATION_INPUT_PATH_ADVANCE, 7);
    input.eventSequence = 1;
    input.logicalX = 585;
    input.logicalY = 412;
    input.flags = OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED
        | OVERWORLD_POPULATION_INPUT_NATIVE_PLAYER;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_OK
            && state.centerX == 585 && state.centerY == 412
            && state.maintenanceState == 1 && result.pending
            && result.work == OVERWORLD_POPULATION_WORK_NONE
            && (result.flags & OVERWORLD_POPULATION_RESULT_REGION_CHANGED)
            && (result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "changed native Player center queues one maintenance pass");
    before = state;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_DUPLICATE
            && memcmp(&state, &before, sizeof(state)) == 0
            && !(result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "duplicate native Player step cannot dirty or advance the pass");
    input.eventSequence = 2;
    (void)Apply(&state, &input, &result);
    CHECK(state.maintenanceState == 1
            && !(result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "same-center native observation does not request work again");
    before = state;
    input.logicalY = 413;
    input.eventSequence = 1;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_STALE_SEQUENCE
            && memcmp(&state, &before, sizeof(state)) == 0,
        "stale native Player sequence cannot queue another pass");
    input.eventSequence = 3;
    input.fieldEpoch = 8;
    CHECK(Apply(&state, &input, &result) == OVERWORLD_POPULATION_DECISION_STALE_FIELD
            && memcmp(&state, &before, sizeof(state)) == 0,
        "wrong Field native Player step cannot queue another pass");
    input.fieldEpoch = 7;
    input.kind = OVERWORLD_POPULATION_INPUT_COMMIT;
    (void)Apply(&state, &input, &result);
    CHECK(state.centerY == 412 && state.maintenanceState == 1
            && (result.flags & OVERWORLD_POPULATION_RESULT_COMMIT_OBSERVED)
            && !(result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "COMMIT remains observation only even with native Player flags");

    Reset(&state, 7, 585, 411);
    input.kind = OVERWORLD_POPULATION_INPUT_PATH_ADVANCE;
    input.eventSequence = 1;
    input.flags = OVERWORLD_POPULATION_INPUT_NATIVE_PLAYER;
    (void)Apply(&state, &input, &result);
    CHECK(state.centerY == 411 && !result.pending
            && !(result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "non-centered actor input cannot request Player maintenance");
    input.eventSequence = 2;
    input.flags = OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED;
    (void)Apply(&state, &input, &result);
    CHECK(state.centerY == 413 && !result.pending
            && (result.flags & OVERWORLD_POPULATION_RESULT_REGION_CHANGED)
            && !(result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
        "non-native centered input retains center behavior without new work");

    for (phase = 1; phase <= 4; phase++) {
        Reset(&state, 7, 585, 411);
        state.maintenanceState = phase;
        input.eventSequence = 1;
        input.logicalY = 412;
        input.flags = OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED
            | OVERWORLD_POPULATION_INPUT_NATIVE_PLAYER;
        (void)Apply(&state, &input, &result);
        CHECK(state.maintenanceState == (u8)(phase | 0x80)
                && result.pending && result.work == OVERWORLD_POPULATION_WORK_NONE
                && (result.flags & OVERWORLD_POPULATION_RESULT_RECONCILE_DUE),
            "native Player step preserves queued phase and marks dirty replay");
        input.eventSequence = 2;
        input.logicalY = 413;
        (void)Apply(&state, &input, &result);
        CHECK(state.maintenanceState == (u8)(phase | 0x80)
                && result.work == OVERWORLD_POPULATION_WORK_NONE,
            "another native step cannot advance or replace active maintenance");
    }
}

int main(void)
{
    CHECK(offsetof(OverworldPopulationState, centerX) == 8
            && offsetof(OverworldPopulationState, centerY) == 10
            && offsetof(OverworldPopulationInput, logicalX) == 8
            && offsetof(OverworldPopulationInput, logicalY) == 10,
        "paired population center copy stays aligned and adjacent");
    CHECK(sizeof(OverworldPopulationInput) == 24,
        "population input stays 24 bytes");
    CHECK(sizeof(OverworldPopulationResult) == 8,
        "population result stays 8 bytes");
    CHECK(sizeof(OverworldPopulationState) == 20,
        "population state stays 20 bytes");
    CHECK(OVERWORLD_POPULATION_MAX_WORK_PER_INPUT == 1,
        "one input returns at most one engine work item");
    CheckExactRefillCadence();
    CheckBoundedWorkOrderAndDirtyReplay();
    CheckExplicitPathAndCommitInputs();
    CheckOneWrapSafeWorldSequence();
    CheckNativePlayerRequestsMaintenance();
    CheckFieldLifecycleAndPausedTimer();
    if (sFailures != 0) {
        fprintf(stderr, "%d population model checks failed\n", sFailures);
        return 1;
    }
    puts("overworld population model: ok");
    return 0;
}
