#ifndef OVERWORLD_BEHAVIOR_RESOLVER_H
#define OVERWORLD_BEHAVIOR_RESOLVER_H

#include "overworld_wild_behavior_data.h"

#define BEHAVIOR_RESOLVER_CLASS_AUTO 0xFF
#define BEHAVIOR_RESOLVER_NO_SOURCE 0xFFFF

typedef enum BehaviorResolveStatus {
    BEHAVIOR_RESOLVE_OK = 0,
    BEHAVIOR_RESOLVE_INVALID_ARGUMENT = 1,
    BEHAVIOR_RESOLVE_INVALID_BLOB = 2,
    BEHAVIOR_RESOLVE_INVALID_CONTEXT = 3,
    BEHAVIOR_RESOLVE_TRACE_TRUNCATED = 4,
} BehaviorResolveStatus;

typedef enum BehaviorResolutionLane {
    BEHAVIOR_RESOLUTION_LANE_OWNER = 0,
    BEHAVIOR_RESOLUTION_LANE_ACTIVE = 1,
    BEHAVIOR_RESOLUTION_LANE_TIRED = 2,
    BEHAVIOR_RESOLUTION_LANE_NONE = 0xFF,
} BehaviorResolutionLane;

typedef enum BehaviorResolutionStepKind {
    BEHAVIOR_RESOLUTION_STEP_CLASS_RULE = 0,
    BEHAVIOR_RESOLUTION_STEP_SPECIES_CLASS_RULE = 1,
    BEHAVIOR_RESOLUTION_STEP_BASE = 2,
    BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE = 3,
    BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE = 4,
    BEHAVIOR_RESOLUTION_STEP_LANE_REFERENCE = 5,
    BEHAVIOR_RESOLUTION_STEP_NORMALIZE = 6,
} BehaviorResolutionStepKind;

#define BEHAVIOR_RESOLUTION_STEP_MATCHED     (1u << 0)
#define BEHAVIOR_RESOLUTION_STEP_APPLIED     (1u << 1)
#define BEHAVIOR_RESOLUTION_STEP_FORCED      (1u << 2)
#define BEHAVIOR_RESOLUTION_STEP_CONDITIONAL (1u << 3)

typedef struct BehaviorResolveRequest {
    OverworldWildBehaviorContext context;
    u32 forcedOverrideMask;
    /* AUTO selects from catalog rules. Other values preserve legacy match
     * tokens while out-of-range base classes normalize to Default. */
    u8 behaviorClass;
    u8 reserved[3];
} BehaviorResolveRequest;

typedef struct BehaviorResolutionStep {
    u16 sourceIndex;
    u8 lane;
    u8 kind;
    u8 flags;
    u8 reserved[3];
    /* State after this step. Class-selection steps contain zeroes. */
    OverworldWildBehaviorProfileData profile;
} BehaviorResolutionStep;

typedef struct BehaviorResolutionTrace {
    BehaviorResolutionStep *steps;
    u16 capacity;
    u16 count;
    u16 dropped;
    u16 reserved;
} BehaviorResolutionTrace;

typedef struct BehaviorResolveResult {
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u8 behaviorClass;
    u8 behaviorLimitKey;
    u16 speciesClassRuleIndex;
    u32 matchedClassRuleMask;
    u32 matchedOverrideMask;
    u32 forcedOverrideMask;
    u32 conditionalOverrideMask;
    u32 appliedOverrideMask;
    u32 fingerprint;
} BehaviorResolveResult;

typedef struct BehaviorClassSelection {
    u32 matchedClassRuleMask;
    u16 speciesClassRuleIndex;
    u8 behaviorClass;
    u8 reserved;
} BehaviorClassSelection;

/*
 * Resolve one immutable behavior value from the compact v72 blob.
 *
 * The function has no engine dependency, performs no allocation, and accepts
 * no Nintendo DS pointers. The blob bytes must stay alive only for this call.
 * A NULL trace disables provenance recording without changing the result.
 */
BehaviorResolveStatus BehaviorResolver_Resolve(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request,
    BehaviorResolveResult *result,
    BehaviorResolutionTrace *trace);

/*
 * Select only the class and its match provenance. This uses the same request
 * validation and class-rule order as Resolve without constructing a profile.
 */
BehaviorResolveStatus BehaviorResolver_InspectClass(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request,
    BehaviorClassSelection *selection,
    BehaviorResolutionTrace *trace);

#endif // OVERWORLD_BEHAVIOR_RESOLVER_H
