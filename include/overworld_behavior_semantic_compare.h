#ifndef OVERWORLD_BEHAVIOR_SEMANTIC_COMPARE_H
#define OVERWORLD_BEHAVIOR_SEMANTIC_COMPARE_H

#ifdef OVERWORLD_BEHAVIOR_HOST
#include <stdint.h>
typedef uint8_t u8;
typedef uint32_t u32;
#else
#include "types.h"
#endif

typedef enum OverworldBehaviorSemantic {
    OVERWORLD_BEHAVIOR_SEMANTIC_NO_RESPONSE = 0,
    OVERWORLD_BEHAVIOR_SEMANTIC_ALERT_PRESENTATION = 1,
    OVERWORLD_BEHAVIOR_SEMANTIC_CHASE = 2,
    OVERWORLD_BEHAVIOR_SEMANTIC_FLEE = 3,
    OVERWORLD_BEHAVIOR_SEMANTIC_ORDINARY_OWNER = 4,
} OverworldBehaviorSemantic;

typedef enum OverworldBehaviorLegacyResponseState {
    OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_OWNER = 0,
    OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ALERT = 1,
    OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ACTIVE = 2,
} OverworldBehaviorLegacyResponseState;

typedef enum OverworldBehaviorSemanticTargetSelector {
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_NONE = 0,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_RANDOM_NEARBY = 1,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_TOWARD = 2,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_AWAY = 3,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_TREE_TOP = 4,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_PLAYFUL_ORBIT = 5,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_NEXT_TO = 6,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_CARDINAL_LINE = 8,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_CIRCLE = 9,
} OverworldBehaviorSemanticTargetSelector;

typedef enum OverworldBehaviorSemanticTargetKind {
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_NONE = 0,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_PLAYER = 1,
    OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_ACTOR = 2,
} OverworldBehaviorSemanticTargetKind;

typedef struct OverworldBehaviorLegacySemanticInput {
    u8 enabled;
    u8 responseState;
    u8 targetSelector;
    u8 reserved;
} OverworldBehaviorLegacySemanticInput;

typedef struct OverworldBehaviorConditionalSemanticInput {
    u32 activeApplicationMask;
    u8 enabled;
    u8 conditionTriggered;
    u8 alertPresentationRequested;
    u8 targetSelector;
    u8 targetKind;
    u8 reserved[3];
} OverworldBehaviorConditionalSemanticInput;

OverworldBehaviorSemantic OverworldBehaviorSemantic_FromLegacy(
    const OverworldBehaviorLegacySemanticInput *input);

OverworldBehaviorSemantic OverworldBehaviorSemantic_FromConditional(
    const OverworldBehaviorConditionalSemanticInput *input);

#endif // OVERWORLD_BEHAVIOR_SEMANTIC_COMPARE_H
