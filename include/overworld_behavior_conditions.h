#ifndef OVERWORLD_BEHAVIOR_CONDITIONS_H
#define OVERWORLD_BEHAVIOR_CONDITIONS_H

#include "overworld_actor_system.h"

#define OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS 32
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES 32
#define OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS \
    OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
#define OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY 0xFFFF
#define OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_MASK_MAX 0x03FF

typedef enum OverworldBehaviorConditionStatus {
    OVERWORLD_BEHAVIOR_CONDITION_OK = 0,
    OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT = 1,
    OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION = 2,
} OverworldBehaviorConditionStatus;

typedef enum OverworldBehaviorConditionKind {
    OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED = 0,
    OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED = 1,
    OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED = 2,
} OverworldBehaviorConditionKind;

typedef enum OverworldBehaviorConditionActivationMode {
    OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE = 0,
    OVERWORLD_BEHAVIOR_CONDITION_TIMED = 1,
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
} OverworldBehaviorConditionRangeKind;

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
    u8 reserved[3];
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
    OverworldBehaviorConditionActorObservation
        actors[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
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
    OverworldBehaviorConditionTargetReference target;
    u8 active;
    u8 hasTriggered;
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
    u16 winningConditionIds[OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS];
    OverworldBehaviorConditionTargetReference
        targets[OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS];
} OverworldBehaviorConditionResult;

typedef char OverworldBehaviorConditionTargetReferenceSizeMustRemain14Bytes[
    sizeof(OverworldBehaviorConditionTargetReference) == 14 ? 1 : -1];
typedef char OverworldBehaviorConditionDefinitionSizeMustRemain20Bytes[
    sizeof(OverworldBehaviorConditionDefinition) == 20 ? 1 : -1];
typedef char OverworldBehaviorConditionEntryStateSizeMustRemain24Bytes[
    sizeof(OverworldBehaviorConditionEntryState) == 24 ? 1 : -1];
typedef char OverworldBehaviorConditionActorStateBudgetMustRemain768Bytes[
    sizeof(OverworldBehaviorConditionEntryState)
            * OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        == 768
        ? 1
        : -1];
typedef char OverworldBehaviorConditionSystemStateBudgetMustRemain7680Bytes[
    sizeof(OverworldBehaviorConditionEntryState)
            * OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
            * OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        == 7680
        ? 1
        : -1];
typedef char OverworldBehaviorConditionResultSizeMustRemain520Bytes[
    sizeof(OverworldBehaviorConditionResult) == 520 ? 1 : -1];

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

#endif // OVERWORLD_BEHAVIOR_CONDITIONS_H
