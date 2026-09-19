#include "../../include/overworld_behavior_semantic_compare.h"

static u8 OverworldBehaviorSemantic_IsDirectedTarget(u8 targetSelector)
{
    return targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_TOWARD
        || targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_PLAYFUL_ORBIT
        || targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_NEXT_TO
        || targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_CARDINAL_LINE
        || targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_CIRCLE;
}

OverworldBehaviorSemantic OverworldBehaviorSemantic_FromLegacy(
    const OverworldBehaviorLegacySemanticInput *input)
{
    if (input == 0 || !input->enabled) {
        return OVERWORLD_BEHAVIOR_SEMANTIC_NO_RESPONSE;
    }
    if (input->responseState == OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ALERT) {
        return OVERWORLD_BEHAVIOR_SEMANTIC_ALERT_PRESENTATION;
    }
    if (input->responseState == OVERWORLD_BEHAVIOR_LEGACY_RESPONSE_ACTIVE) {
        if (input->targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_AWAY) {
            return OVERWORLD_BEHAVIOR_SEMANTIC_FLEE;
        }
        if (OverworldBehaviorSemantic_IsDirectedTarget(input->targetSelector)) {
            return OVERWORLD_BEHAVIOR_SEMANTIC_CHASE;
        }
    }
    return OVERWORLD_BEHAVIOR_SEMANTIC_ORDINARY_OWNER;
}

OverworldBehaviorSemantic OverworldBehaviorSemantic_FromConditional(
    const OverworldBehaviorConditionalSemanticInput *input)
{
    if (input == 0 || !input->enabled) {
        return OVERWORLD_BEHAVIOR_SEMANTIC_NO_RESPONSE;
    }
    if (input->conditionTriggered && input->alertPresentationRequested) {
        return OVERWORLD_BEHAVIOR_SEMANTIC_ALERT_PRESENTATION;
    }
    if (input->activeApplicationMask == 0) {
        return OVERWORLD_BEHAVIOR_SEMANTIC_ORDINARY_OWNER;
    }
    if (input->targetKind != OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_REFERENCE_NONE) {
        if (input->targetSelector == OVERWORLD_BEHAVIOR_SEMANTIC_TARGET_AWAY) {
            return OVERWORLD_BEHAVIOR_SEMANTIC_FLEE;
        }
        if (OverworldBehaviorSemantic_IsDirectedTarget(input->targetSelector)) {
            return OVERWORLD_BEHAVIOR_SEMANTIC_CHASE;
        }
    }
    return OVERWORLD_BEHAVIOR_SEMANTIC_ORDINARY_OWNER;
}
