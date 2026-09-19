#include "overworld_actor_transition_model.h"

#include <stdio.h>
#include <string.h>

static int sFailures;

#define CHECK(condition, label) \
    do { \
        if (!(condition)) { \
            fprintf(stderr, "FAIL: %s\n", label); \
            sFailures++; \
        } \
    } while (0)

static OverworldActorTransitionCall MakeCall(
    u32 sequence,
    u16 fieldEpoch,
    u8 disposition)
{
    OverworldActorTransitionCall call;

    memset(&call, 0, sizeof(call));
    call.version = OVERWORLD_ACTOR_TRANSITION_CALL_VERSION;
    call.size = sizeof(call);
    call.sequence = sequence;
    call.expectedFieldEpoch = fieldEpoch;
    call.previousMapId = 10;
    call.currentMapId = 11;
    call.previousMapGeneration = 20;
    call.disposition = disposition;
    return call;
}

static OverworldActorResult Apply(
    OverworldActorTransitionState *state,
    OverworldActorTransitionCall *call,
    u16 fieldEpoch,
    u16 mapGeneration,
    u16 activeMask,
    u16 resumeMask,
    u8 *effects)
{
    return OverworldActorTransition_Apply(
        state, call, fieldEpoch | ((u32)mapGeneration << 16),
        activeMask, resumeMask, effects);
}

static void CheckPreserveOrderAndIdempotence(void)
{
    OverworldActorTransitionState state;
    OverworldActorTransitionCall call = MakeCall(
        100, 7, OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE);
    u8 effects = 0;

    OverworldActorTransition_Reset(&state);
    CHECK(Apply(&state, &call, 7, 20, 0x0007, 0x0002, &effects)
            == OVERWORLD_ACTOR_RESULT_OK,
        "preserve transition begins");
    CHECK(call.work == OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_SUSPEND,
        "begin requests canonicalize after one suspend effect");
    CHECK(call.nextFieldEpoch == 8 && call.nextMapGeneration == 21,
        "begin computes one next epoch and map generation");
    CHECK(call.retainedActorMask == 0x0007
            && call.resumeMotionMask == 0x0002
            && call.discardActorMask == 0,
        "preserve snapshots retained and resumable actors");

    effects = 0xFF;
    CHECK(Apply(&state, &call, 7, 20, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE,
        "repeating begin does not suspend twice");

    call.acknowledgements =
        OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED;
    CHECK(Apply(&state, &call, 7, 20, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_ADVANCE_FIELD,
        "canonicalize acknowledgement advances the field once");
    CHECK(Apply(&state, &call, 8, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE,
        "repeated canonicalize acknowledgement does not advance twice");

    call.acknowledgements |=
        OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND;
    CHECK(Apply(&state, &call, 8, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_RESUME
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE,
        "presentation acknowledgement requests resume");

    call.acknowledgements |= OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED;
    CHECK(Apply(&state, &call, 8, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_FINALIZE,
        "final acknowledgement completes exactly once");
    CHECK(Apply(&state, &call, 8, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE,
        "completed sequence is idempotent");
}

static void CheckOrderingAndConcurrency(void)
{
    OverworldActorTransitionState state;
    OverworldActorTransitionCall call = MakeCall(
        200, 9, OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE);
    OverworldActorTransitionCall concurrent;
    u8 effects;

    OverworldActorTransition_Reset(&state);
    CHECK(Apply(&state, &call, 9, 20, 1, 1, &effects)
            == OVERWORLD_ACTOR_RESULT_OK,
        "ordering fixture begins");
    call.acknowledgements =
        OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND;
    CHECK(Apply(&state, &call, 9, 20, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_REJECTED
            && call.reason == OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT
            && state.phase == OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE,
        "presentation cannot acknowledge before canonicalize");

    concurrent = MakeCall(
        201, 9, OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD);
    CHECK(Apply(&state, &concurrent, 9, 20, 1, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_RETRY
            && concurrent.reason == OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY,
        "a newer transition retries while one is active");

    concurrent.sequence = 199;
    CHECK(Apply(&state, &concurrent, 9, 20, 1, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_REJECTED
            && concurrent.reason == OVERWORLD_ACTOR_REASON_STALE_SEQUENCE,
        "an older transition is rejected");
}

static void CheckDiscardAndGenerationWrap(void)
{
    OverworldActorTransitionState state;
    OverworldActorTransitionCall call = MakeCall(
        300, 0xFFFF,
        OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD);
    u8 effects;

    call.previousMapGeneration = 0xFFFF;
    OverworldActorTransition_Reset(&state);
    CHECK(Apply(&state, &call, 0xFFFF, 0xFFFF,
            0x000B, 0x0002, &effects)
            == OVERWORLD_ACTOR_RESULT_OK,
        "discard transition begins");
    CHECK(call.nextFieldEpoch == 1 && call.nextMapGeneration == 1,
        "zero is skipped when generations wrap");
    CHECK(call.retainedActorMask == 0
            && call.resumeMotionMask == 0
            && call.discardActorMask == 0x000B,
        "discard transition snapshots all active actors for discard");
    call.acknowledgements =
        OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED;
    CHECK(Apply(&state, &call, 0xFFFF, 0xFFFF, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND,
        "discard still follows canonicalize then rebind");
    call.acknowledgements |=
        OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND;
    CHECK(Apply(&state, &call, 1, 1, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD,
        "discard work follows presentation rebind");
}

static void CheckAdapterFailureDowngradesPreserve(void)
{
    OverworldActorTransitionState state;
    OverworldActorTransitionCall call = MakeCall(
        350, 14, OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE);
    u8 effects = 0;

    OverworldActorTransition_Reset(&state);
    CHECK(Apply(&state, &call, 14, 20, 0x0005, 0x0001, &effects)
            == OVERWORLD_ACTOR_RESULT_OK,
        "adapter-failure fixture begins");
    call.acknowledgements =
        OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED;
    CHECK(Apply(&state, &call, 14, 20, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_ADVANCE_FIELD,
        "adapter-failure fixture reaches rebind");

    call.disposition = OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD;
    CHECK(Apply(&state, &call, 15, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.disposition
                == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
            && call.retainedActorMask == 0
            && call.resumeMotionMask == 0
            && call.discardActorMask == 0x0005,
        "failed preserve rebind downgrades to discard");

    call.acknowledgements |=
        OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND;
    CHECK(Apply(&state, &call, 15, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD,
        "discard fallback reaches finalization");
    call.acknowledgements |= OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED;
    CHECK(Apply(&state, &call, 15, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_OK
            && call.work == OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE
            && effects == OVERWORLD_ACTOR_TRANSITION_EFFECT_FINALIZE,
        "discard fallback releases the transition gate");

    call = MakeCall(
        351, 15, OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE);
    call.previousMapGeneration = 20;
    CHECK(Apply(&state, &call, 15, 21, 0, 0, &effects)
            == OVERWORLD_ACTOR_RESULT_REJECTED
            && call.reason == OVERWORLD_ACTOR_REASON_STALE_FIELD,
        "actor owner rejects a stale map generation");
}

static void CheckRetainedHandleValidation(void)
{
    OverworldActorTransitionCall call = MakeCall(
        400, 12, OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE);
    OverworldActorHandle handle;

    memset(&handle, 0, sizeof(handle));
    call.work = OVERWORLD_ACTOR_TRANSITION_WORK_REBIND;
    call.nextFieldEpoch = 13;
    call.nextMapGeneration = 31;
    call.retainedActorMask = 1u << 3;
    handle.slot = 3;
    handle.generation = 9;
    handle.fieldEpoch = 13;
    handle.mapGeneration = 31;
    handle.encounterGeneration = 22;
    CHECK(OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "matching retained handle is accepted");

    handle.fieldEpoch--;
    CHECK(!OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "stale field epoch is rejected");
    handle.fieldEpoch++;
    handle.mapGeneration--;
    CHECK(!OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "stale map generation is rejected");
    handle.mapGeneration++;
    handle.encounterGeneration--;
    CHECK(!OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "stale encounter generation is rejected");
    handle.encounterGeneration++;
    handle.slot--;
    CHECK(!OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "wrong actor slot is rejected");
    handle.slot++;
    call.retainedActorMask = 0;
    CHECK(!OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "actor absent from retained mask is rejected");
    call.retainedActorMask = 1u << 3;
    call.work = OVERWORLD_ACTOR_TRANSITION_WORK_RESUME;
    CHECK(!OverworldActorTransition_RetainedHandleMatches(
            &call, &handle, 3, 22),
        "retained handle is only valid during rebind");
}

int main(void)
{
    CHECK(sizeof(OverworldActorTransitionCall) == 32,
        "public transition call stays 32 bytes");
    CHECK(sizeof(OverworldActorTransitionState) == 20,
        "packed transition state stays 20 bytes");
    CheckPreserveOrderAndIdempotence();
    CheckOrderingAndConcurrency();
    CheckDiscardAndGenerationWrap();
    CheckAdapterFailureDowngradesPreserve();
    CheckRetainedHandleValidation();
    if (sFailures != 0) {
        fprintf(stderr, "%d transition model checks failed\n", sFailures);
        return 1;
    }
    puts("overworld actor transition model: ok");
    return 0;
}
