#ifndef OVERWORLD_BEHAVIOR_CONDITIONS_H
#define OVERWORLD_BEHAVIOR_CONDITIONS_H

#include "overworld_actor_system.h"
#include "overworld_vision.h"

#define OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS 32
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES 32
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS \
    OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
#define OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY 0xFFFF
#define OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION 0xFF
#define OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX 0x03FF
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE (1u << 0)
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED (1u << 1)
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING (1u << 2)
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_UNTIL_CRASH (1u << 3)
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM (1u << 4)
/* Conditions apply during motion. Presentation waits for the next legal
 * intent boundary and expires with the condition that owns it. */
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_PRESENTATION_PENDING (1u << 5)
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_TIMED_END_PENDING (1u << 6)
#define OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING 1u
#define OVERWORLD_BEHAVIOR_CONDITION_INPUT_GEOMETRY 2u
/* Compatibility names for the private observation caller and retained proof. */
#define OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING OVERWORLD_BEHAVIOR_CONDITION_STATE_PRESENTATION_PENDING
#define OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING
#define OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY OVERWORLD_BEHAVIOR_CONDITION_INPUT_GEOMETRY

/* Authored zero means all roles. Current roles use Wild/Follower/Mounted
 * bits 1/2/4, as published by the condition adapter. */
static inline u8 OverworldBehaviorCondition_RoleApplies(
    u8 authoredRoleMask, u8 currentRoleMask)
{
    return authoredRoleMask == 0
        || (authoredRoleMask & currentRoleMask) != 0;
}

typedef enum OverworldBehaviorConditionStatus {
    OVERWORLD_BEHAVIOR_CONDITION_OK = 0,
    OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT = 1,
    OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION = 2,
    OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET = 3,
    OVERWORLD_BEHAVIOR_CONDITION_STORAGE_REQUIRED = 4,
} OverworldBehaviorConditionStatus;

typedef enum OverworldBehaviorConditionKind {
    OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED = 0,
    OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED = 1,
    OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED = 2,
    OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT = 3,
    OVERWORLD_BEHAVIOR_CONDITION_ACTOR_FACTS = 4,
    OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED = 5,
    OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED = 6,
} OverworldBehaviorConditionKind;

/* Radius range options in Definition.reserved; Vision keeps its own options. */
#define OVERWORLD_BEHAVIOR_CONDITION_RADIUS_SAME_TILE 1u

/* Facts about the subject's current actor interaction. */
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_RESERVED    (1u << 0)
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD        (1u << 1)
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_THROW_LINE  (1u << 2)
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_RECOVERING  (1u << 3)
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID (1u << 4)
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP (1u << 5)
#define OVERWORLD_BEHAVIOR_ACTOR_FACT_MASK 0x3F

typedef enum OverworldBehaviorConditionActivationMode {
    OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE = 0,
    OVERWORLD_BEHAVIOR_CONDITION_TIMED = 1,
    OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH = 2,
} OverworldBehaviorConditionActivationMode;

typedef enum OverworldBehaviorConditionTargetKind {
    OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE = 0,
    OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER = 1,
    OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR = 2,
} OverworldBehaviorConditionTargetKind;

typedef enum OverworldBehaviorConditionRangeKind {
    OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE = 1,
    OVERWORLD_BEHAVIOR_CONDITION_RANGE_FACING_LINE_CLOSE_RADIUS = 2,
    OVERWORLD_BEHAVIOR_CONDITION_RANGE_CARDINAL_LINE = 3,
    OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS = 4,
    OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT = 5,
    OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM = 6,
} OverworldBehaviorConditionRangeKind;

#define OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_FACING_MASK 0x03
#define OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT \
    (1u << 2)
#define OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT \
    (1u << 3)
#define OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE \
    (1u << 4)
/* Subject-only mark in playerFacingAndOcclusion; never an actor source mark. */
#define OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED (1u << 4)

typedef enum OverworldBehaviorConditionTargetReferenceKind {
    OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE = 0,
    OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER = 1,
    OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR = 2,
} OverworldBehaviorConditionTargetReferenceKind;

typedef struct OverworldBehaviorConditionTargetReference {
    OverworldActorHandle actor;
    u8 kind;
    u8 reserved;
} OverworldBehaviorConditionTargetReference;

typedef struct OverworldBehaviorConditionActorObservation {
    OverworldActorHandle actor;
    s16 x;
    s16 y;
    u8 valid;
    u8 facingAndOcclusion;
    u8 visionRange;
    u8 visionOptions;
} OverworldBehaviorConditionActorObservation;

typedef struct OverworldBehaviorConditionWorldView {
    OverworldActorHandle subject;
    u32 frame;
    s16 subjectX;
    s16 subjectY;
    s16 playerX;
    s16 playerY;
    u16 subjectTerrainMask;
    u8 subjectFacing;
    u8 subjectMovementSpeed;
    u8 playerValid;
    u8 actorCount;
    u8 playerFacingAndOcclusion;
    u8 subjectVisionRange;
    u8 subjectVisionOptions;
    u8 playerVisionRange;
    u8 playerVisionOptions;
    u8 reserved[3];
    OverworldBehaviorConditionActorObservation
        actors[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    /* Borrowed only for this synchronous intent boundary. The Field owner
     * clears these values before it releases the shared query code. */
    struct OverworldTargetBindingsState *bindings;
    u16 incomingClaimMask;
    u8 subjectRoleMask;
    u8 reservedBinding;
} OverworldBehaviorConditionWorldView;

typedef struct OverworldBehaviorConditionDefinition {
    u16 conditionId;
    u16 durationFrames;
    u16 cooldownFrames;
    u16 terrainMask;
    u16 terrainOverrideMask;
    u8 applicationIndex;
    u8 kind;
    u8 activationMode;
    u8 targetKind;
    u8 rangeKind;
    u8 distance;
    u8 chance;
    u8 minMovementSpeed;
    u8 maxMovementSpeed;
    u8 reserved;
} OverworldBehaviorConditionDefinition;

typedef struct OverworldBehaviorConditionEntryInput {
    u16 eligibleActorMask;
    u8 chanceRoll;
    u8 reserved;
} OverworldBehaviorConditionEntryInput;

typedef struct OverworldBehaviorConditionEntryState {
    u32 activeUntil;
    u32 cooldownUntil;
    u16 targetSlot;
    u16 targetGeneration;
    u16 targetEncounterGeneration;
    u8 targetKind;
    u8 flags;
} OverworldBehaviorConditionEntryState;

typedef struct OverworldBehaviorConditionEntryResult {
    OverworldBehaviorConditionTargetReference target;
    u16 conditionId;
    u8 applicationIndex;
    u8 active;
    u8 conditionTrue;
    u8 triggered;
} OverworldBehaviorConditionEntryResult;

typedef struct OverworldBehaviorConditionResult {
    u32 activeApplicationMask;
    u32 triggeredApplicationMask;
    OverworldBehaviorConditionTargetReference resolvedTarget;
    u16 resolvedTargetConditionId;
    u8 resolvedTargetSourceApplication;
    u8 winningConditionSourceApplication;
    u16 winningConditionId;
    u16 winningConditionIds[OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS];
    OverworldBehaviorConditionTargetReference
        targets[OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS];
} OverworldBehaviorConditionResult;

typedef char OverworldBehaviorConditionTargetReferenceSizeMustRemain14Bytes[
    sizeof(OverworldBehaviorConditionTargetReference) == 14 ? 1 : -1];
typedef char OverworldBehaviorConditionDefinitionSizeMustRemain20Bytes[
    sizeof(OverworldBehaviorConditionDefinition) == 20 ? 1 : -1];
typedef char OverworldBehaviorConditionEntryStateSizeMustRemain16Bytes[
    sizeof(OverworldBehaviorConditionEntryState) == 16 ? 1 : -1];
typedef char OverworldBehaviorConditionActorStateBudgetMustRemain512Bytes[
    sizeof(OverworldBehaviorConditionEntryState)
            * OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        == 512
        ? 1
        : -1];
typedef char OverworldBehaviorConditionSystemStateBudgetMustRemain5120Bytes[
    sizeof(OverworldBehaviorConditionEntryState)
            * OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
            * OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        == 5120
        ? 1
        : -1];
typedef char OverworldBehaviorConditionResultSizeMustRemain540Bytes[
    sizeof(OverworldBehaviorConditionResult) == 540 ? 1 : -1];

u8 OverworldBehaviorCondition_DefinitionValid(
    const OverworldBehaviorConditionDefinition *definition);

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluateEntry(
    const OverworldBehaviorConditionDefinition *definition,
    const OverworldBehaviorConditionEntryInput *input,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionEntryState *state,
    OverworldBehaviorConditionEntryResult *result);

OverworldBehaviorConditionStatus OverworldBehaviorCondition_Evaluate(
    const OverworldBehaviorConditionDefinition *definitions,
    const OverworldBehaviorConditionEntryInput *inputs,
    OverworldBehaviorConditionEntryState *states,
    u16 count,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionResult *result);

OverworldBehaviorConditionStatus OverworldBehaviorCondition_EvaluateWithResults(
    const OverworldBehaviorConditionDefinition *definitions,
    const OverworldBehaviorConditionEntryInput *inputs,
    OverworldBehaviorConditionEntryState *states,
    u16 count,
    const OverworldBehaviorConditionWorldView *world,
    OverworldBehaviorConditionResult *result,
    OverworldBehaviorConditionEntryResult *entryResults);

#endif // OVERWORLD_BEHAVIOR_CONDITIONS_H
