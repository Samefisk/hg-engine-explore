#ifndef OVERWORLD_POPULATION_MODEL_H
#define OVERWORLD_POPULATION_MODEL_H

#ifdef OVERWORLD_POPULATION_HOST
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int16_t s16;
typedef int32_t s32;
#else
#include "types.h"
#endif

#define OVERWORLD_POPULATION_INPUT_VERSION 1
#define OVERWORLD_POPULATION_MAX_WORK_PER_INPUT 1

typedef enum OverworldPopulationInputKind {
    OVERWORLD_POPULATION_INPUT_RESET = 0,
    OVERWORLD_POPULATION_INPUT_SCHEDULE_REFILL,
    OVERWORLD_POPULATION_INPUT_REQUEST_MAINTENANCE,
    OVERWORLD_POPULATION_INPUT_CANCEL_MAINTENANCE,
    OVERWORLD_POPULATION_INPUT_TAKE_WORK,
    OVERWORLD_POPULATION_INPUT_QUERY,
    OVERWORLD_POPULATION_INPUT_FRAME,
    OVERWORLD_POPULATION_INPUT_PATH_ADVANCE,
    OVERWORLD_POPULATION_INPUT_COMMIT,
    OVERWORLD_POPULATION_INPUT_FIELD_EVENT,
} OverworldPopulationInputKind;

typedef enum OverworldPopulationFieldEvent {
    OVERWORLD_POPULATION_FIELD_NONE = 0,
    OVERWORLD_POPULATION_FIELD_SUSPEND,
    OVERWORLD_POPULATION_FIELD_REBIND,
    OVERWORLD_POPULATION_FIELD_RESUME,
    OVERWORLD_POPULATION_FIELD_DISCARD,
} OverworldPopulationFieldEvent;

typedef enum OverworldPopulationWork {
    OVERWORLD_POPULATION_WORK_NONE = 0,
    OVERWORLD_POPULATION_WORK_DESPAWN,
    OVERWORLD_POPULATION_WORK_REFILL,
    OVERWORLD_POPULATION_WORK_REVEAL,
} OverworldPopulationWork;

typedef enum OverworldPopulationDecision {
    OVERWORLD_POPULATION_DECISION_OK = 0,
    OVERWORLD_POPULATION_DECISION_DUPLICATE,
    OVERWORLD_POPULATION_DECISION_STALE_FIELD,
    OVERWORLD_POPULATION_DECISION_INVALID,
    OVERWORLD_POPULATION_DECISION_STALE_SEQUENCE,
} OverworldPopulationDecision;

#define OVERWORLD_POPULATION_INPUT_TIMER_ELIGIBLE  (1u << 0)
#define OVERWORLD_POPULATION_INPUT_PLAYER_CENTERED (1u << 1)
#define OVERWORLD_POPULATION_INPUT_NATIVE_PLAYER   (1u << 2)

#define OVERWORLD_POPULATION_RESULT_REFILL_DUE       (1u << 0)
#define OVERWORLD_POPULATION_RESULT_WORK_PENDING     (1u << 1)
#define OVERWORLD_POPULATION_RESULT_REGION_CHANGED   (1u << 2)
#define OVERWORLD_POPULATION_RESULT_COMMIT_OBSERVED  (1u << 3)
#define OVERWORLD_POPULATION_RESULT_RECONCILE_DUE    (1u << 4)
#define OVERWORLD_POPULATION_RESULT_FIELD_SUSPENDED  (1u << 5)

/*
 * PATH_ADVANCE, COMMIT, and FIELD_EVENT share one non-zero, strictly newer,
 * wrap-safe eventSequence. This keeps repeated and stale world reports from
 * mutating population state.
 */
typedef struct OverworldPopulationInput {
    u16 version;
    u16 size;
    u32 eventSequence;
    s16 logicalX;
    s16 logicalY;
    u16 fieldEpoch;
    u16 value;
    u8 kind;
    u8 event;
    u8 actorSlot;
    u8 actorRole;
    u8 flags;
    u8 reserved0;
    u8 reserved1;
    u8 reserved2;
} OverworldPopulationInput;

typedef struct OverworldPopulationResult {
    u16 decision;
    u16 refillTimer;
    u8 work;
    u8 flags;
    u8 pending;
    u8 reserved;
} OverworldPopulationResult;

typedef struct OverworldPopulationState {
    u32 lastWorldEventSequence;
    u32 reservedWorldEventSequence;
    s16 centerX;
    s16 centerY;
    u16 fieldEpoch;
    u16 refillTimer;
    u8 refillArmed;
    u8 maintenanceState;
    u8 fieldActive;
    u8 reserved;
} OverworldPopulationState;

OverworldPopulationDecision OverworldPopulation_Apply(
    OverworldPopulationState *state,
    const OverworldPopulationInput *input,
    OverworldPopulationResult *result);

typedef char OverworldPopulationInputSizeMustRemain24Bytes[
    sizeof(OverworldPopulationInput) == 24 ? 1 : -1];
typedef char OverworldPopulationResultSizeMustRemain8Bytes[
    sizeof(OverworldPopulationResult) == 8 ? 1 : -1];
typedef char OverworldPopulationStateSizeMustRemain20Bytes[
    sizeof(OverworldPopulationState) == 20 ? 1 : -1];
typedef char OverworldPopulationWorkBoundMustRemainOne[
    OVERWORLD_POPULATION_MAX_WORK_PER_INPUT == 1 ? 1 : -1];

#endif // OVERWORLD_POPULATION_MODEL_H
