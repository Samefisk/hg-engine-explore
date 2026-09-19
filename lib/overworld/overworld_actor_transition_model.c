#include "overworld_actor_transition_model.h"

static u16 OverworldActorTransition_IncrementGeneration(u16 generation)
{
    generation++;
    return generation == 0 ? 1 : generation;
}

static u8 OverworldActorTransition_SequenceIsNewer(
    u32 sequence,
    u32 reference)
{
    return reference == 0 || (s32)(sequence - reference) > 0;
}

static void OverworldActorTransition_FillOutput(
    const OverworldActorTransitionState *state,
    OverworldActorTransitionCall *call)
{
    call->nextFieldEpoch = OverworldActorTransition_IncrementGeneration(
        state->previousFieldEpoch);
    call->nextMapGeneration = OverworldActorTransition_IncrementGeneration(
        state->previousMapGeneration);
    call->retainedActorMask = state->disposition
            == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE
        ? state->actorMask
        : 0;
    call->resumeMotionMask = state->disposition
            == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE
        ? state->resumeMotionMask
        : 0;
    call->discardActorMask = state->disposition
            == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD
        ? state->actorMask
        : 0;
    call->reason = OVERWORLD_ACTOR_REASON_OK;
    switch (state->phase) {
    case OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE:
        call->work = OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE;
        break;
    case OVERWORLD_ACTOR_TRANSITION_PHASE_REBIND:
        call->work = OVERWORLD_ACTOR_TRANSITION_WORK_REBIND;
        break;
    case OVERWORLD_ACTOR_TRANSITION_PHASE_FINALIZE:
        call->work = state->disposition
                == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE
            ? OVERWORLD_ACTOR_TRANSITION_WORK_RESUME
            : OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD;
        break;
    case OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE:
        call->work = OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE;
        break;
    default:
        call->work = OVERWORLD_ACTOR_TRANSITION_WORK_NONE;
        break;
    }
}

static OverworldActorResult OverworldActorTransition_Reject(
    OverworldActorTransitionCall *call,
    u16 reason)
{
    call->work = OVERWORLD_ACTOR_TRANSITION_WORK_NONE;
    call->reason = reason;
    return OVERWORLD_ACTOR_RESULT_REJECTED;
}

void OverworldActorTransition_Reset(OverworldActorTransitionState *state)
{
    u8 *bytes = (u8 *)state;
    u32 remaining;

    if (state == NULL) {
        return;
    }
    remaining = sizeof(*state);
    while (remaining != 0) {
        *bytes++ = 0;
        remaining--;
    }
}

OverworldActorResult OverworldActorTransition_Apply(
    OverworldActorTransitionState *state,
    OverworldActorTransitionCall *call,
    u32 currentFieldContext,
    u16 activeActorMask,
    u16 resumeMotionCandidateMask,
    u8 *effects)
{
    u8 acknowledgements;

    if (effects != NULL) {
        *effects = OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE;
    }
    if (state == NULL || call == NULL || effects == NULL
        || call->version != OVERWORLD_ACTOR_TRANSITION_CALL_VERSION
        || call->size != sizeof(*call)
        || call->sequence == 0
        || call->reserved != 0) {
        return OVERWORLD_ACTOR_RESULT_REJECTED;
    }
    call->work = OVERWORLD_ACTOR_TRANSITION_WORK_NONE;
    call->nextFieldEpoch = 0;
    call->nextMapGeneration = 0;
    call->retainedActorMask = 0;
    call->resumeMotionMask = 0;
    call->discardActorMask = 0;
    call->reason = OVERWORLD_ACTOR_REASON_OK;

    if (state->phase != OVERWORLD_ACTOR_TRANSITION_PHASE_NONE
        && call->sequence == state->sequence) {
        if (call->mapIdentity != state->mapIdentity
            || call->previousFieldContext != state->previousFieldContext) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        }
        if (call->disposition != state->disposition) {
            if (call->disposition
                    != OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD
                || state->phase == OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE) {
                return OverworldActorTransition_Reject(
                    call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
            }
            state->disposition =
                OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD;
        }
        if (state->phase == OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE) {
            OverworldActorTransition_FillOutput(state, call);
            return OVERWORLD_ACTOR_RESULT_OK;
        }
    } else if (state->phase != OVERWORLD_ACTOR_TRANSITION_PHASE_NONE
        && state->phase != OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE) {
        if (OverworldActorTransition_SequenceIsNewer(
                call->sequence, state->sequence)) {
            call->reason = OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY;
            return OVERWORLD_ACTOR_RESULT_RETRY;
        }
        return OverworldActorTransition_Reject(
            call, OVERWORLD_ACTOR_REASON_STALE_SEQUENCE);
    } else {
        if (!OverworldActorTransition_SequenceIsNewer(
                call->sequence, state->sequence)) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_STALE_SEQUENCE);
        }
        if (call->disposition
                != OVERWORLD_ACTOR_TRANSITION_DISPOSITION_PRESERVE
            && call->disposition
                != OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        }
        if (call->previousFieldContext != currentFieldContext) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_STALE_FIELD);
        }
        if (call->acknowledgements != 0) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        }
        state->sequence = call->sequence;
        state->mapIdentity = call->mapIdentity;
        state->previousFieldContext = call->previousFieldContext;
        state->actorMask = activeActorMask;
        state->resumeMotionMask = resumeMotionCandidateMask & activeActorMask;
        state->phase = OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE;
        state->disposition = call->disposition;
        *effects = OVERWORLD_ACTOR_TRANSITION_EFFECT_SUSPEND;
        OverworldActorTransition_FillOutput(state, call);
        return OVERWORLD_ACTOR_RESULT_OK;
    }

    acknowledgements = call->acknowledgements;
    if ((acknowledgements & ~OVERWORLD_ACTOR_TRANSITION_ACK_ALL) != 0) {
        return OverworldActorTransition_Reject(
            call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
    }
    if (state->phase == OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE) {
        if ((acknowledgements
                & (OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND
                    | OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED)) != 0) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        }
        if ((acknowledgements
                & OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED) != 0) {
            state->phase = OVERWORLD_ACTOR_TRANSITION_PHASE_REBIND;
            *effects = OVERWORLD_ACTOR_TRANSITION_EFFECT_ADVANCE_FIELD;
        }
    } else if (state->phase == OVERWORLD_ACTOR_TRANSITION_PHASE_REBIND) {
        if ((acknowledgements
                & OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED) == 0
            || (acknowledgements
                & OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED) != 0) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        }
        if ((acknowledgements
                & OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND) != 0) {
            state->phase = OVERWORLD_ACTOR_TRANSITION_PHASE_FINALIZE;
        }
    } else if (state->phase == OVERWORLD_ACTOR_TRANSITION_PHASE_FINALIZE) {
        if ((acknowledgements
                & (OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED
                    | OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND))
            != (OVERWORLD_ACTOR_TRANSITION_ACK_ENGINE_CANONICALIZED
                | OVERWORLD_ACTOR_TRANSITION_ACK_PRESENTATIONS_REBOUND)) {
            return OverworldActorTransition_Reject(
                call, OVERWORLD_ACTOR_REASON_INVALID_ARGUMENT);
        }
        if ((acknowledgements
                & OVERWORLD_ACTOR_TRANSITION_ACK_FINALIZED) != 0) {
            state->phase = OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE;
            *effects = OVERWORLD_ACTOR_TRANSITION_EFFECT_FINALIZE;
        }
    }
    OverworldActorTransition_FillOutput(state, call);
    return OVERWORLD_ACTOR_RESULT_OK;
}
