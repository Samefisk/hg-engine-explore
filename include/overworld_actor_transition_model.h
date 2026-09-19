#ifndef OVERWORLD_ACTOR_TRANSITION_MODEL_H
#define OVERWORLD_ACTOR_TRANSITION_MODEL_H

#include "overworld_actor_system.h"

typedef enum OverworldActorTransitionPhase {
    OVERWORLD_ACTOR_TRANSITION_PHASE_NONE = 0,
    OVERWORLD_ACTOR_TRANSITION_PHASE_CANONICALIZE = 1,
    OVERWORLD_ACTOR_TRANSITION_PHASE_REBIND = 2,
    OVERWORLD_ACTOR_TRANSITION_PHASE_FINALIZE = 3,
    OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE = 4,
} OverworldActorTransitionPhase;

#define OVERWORLD_ACTOR_TRANSITION_EFFECT_NONE          0
#define OVERWORLD_ACTOR_TRANSITION_EFFECT_SUSPEND       (1u << 0)
#define OVERWORLD_ACTOR_TRANSITION_EFFECT_ADVANCE_FIELD (1u << 1)
#define OVERWORLD_ACTOR_TRANSITION_EFFECT_FINALIZE      (1u << 2)

/* Pointer-free lifecycle state shared by the ROM owner and host model. */
typedef struct OverworldActorTransitionState {
    u32 sequence;
    __extension__ union {
        __extension__ struct {
            u16 previousMapId;
            u16 currentMapId;
        };
        u32 mapIdentity;
    };
    __extension__ union {
        __extension__ struct {
            u16 previousFieldEpoch;
            u16 previousMapGeneration;
        };
        u32 previousFieldContext;
    };
    u16 actorMask;
    u16 resumeMotionMask;
    u8 phase;
    u8 disposition;
} OverworldActorTransitionState;

static inline u8 OverworldActorTransition_RetainedHandleMatches(
    const OverworldActorTransitionCall *call,
    const OverworldActorHandle *handle,
    u16 actorSlot,
    u16 encounterGeneration)
{
    return call != NULL
        && handle != NULL
        && call->work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
        && actorSlot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        && (call->retainedActorMask & (1u << actorSlot)) != 0
        && handle->slot == actorSlot
        && handle->generation != 0
        && handle->fieldEpoch == call->nextFieldEpoch
        && handle->mapGeneration == call->nextMapGeneration
        && handle->encounterGeneration == encounterGeneration;
}

void OverworldActorTransition_Reset(OverworldActorTransitionState *state);
OverworldActorResult OverworldActorTransition_Apply(
    OverworldActorTransitionState *state,
    OverworldActorTransitionCall *call,
    u32 currentFieldContext,
    u16 activeActorMask,
    u16 resumeMotionCandidateMask,
    u8 *effects);

typedef char OverworldActorTransitionStateSizeMustRemain20Bytes[
    sizeof(OverworldActorTransitionState) == 20 ? 1 : -1];
typedef char OverworldActorTransitionStateMapIdentityOffsetMustRemain4[
    offsetof(OverworldActorTransitionState, mapIdentity) == 4 ? 1 : -1];
typedef char OverworldActorTransitionStateFieldContextOffsetMustRemain8[
    offsetof(OverworldActorTransitionState, previousFieldContext) == 8
        ? 1
        : -1];

#endif // OVERWORLD_ACTOR_TRANSITION_MODEL_H
