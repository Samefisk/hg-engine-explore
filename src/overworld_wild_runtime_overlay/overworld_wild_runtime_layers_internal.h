#ifndef OVERWORLD_WILD_RUNTIME_LAYERS_INTERNAL_H
#define OVERWORLD_WILD_RUNTIME_LAYERS_INTERNAL_H

#include "../overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"

#define OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE 1
#define OW_WILD_RUNTIME_DEFINITION_MODIFIER 2
#define OW_WILD_RUNTIME_SELECTOR_EXACT 1
#define OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE 2
#define OW_WILD_RUNTIME_OPERATOR_SET 1
#define OW_WILD_RUNTIME_OPERATOR_ADD 2
#define OW_WILD_RUNTIME_OPERATOR_AT_LEAST 3
#define OW_WILD_RUNTIME_OPERATOR_AT_MOST 4
#define OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST 5
#define OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST 6
#define OW_WILD_RUNTIME_FIELD_STATE 1
#define OW_WILD_RUNTIME_FIELD_CONTROLLER 2

/* Value-copy projection of one validated v40 definition/applicability pair.
 * The authoritative serialized record remains owned by the resident bundle. */
typedef struct OverworldWildRuntimeDefinition {
    u32 immutableContextMask;
    u16 stableId;
    u16 controllerId;
    u16 nodeId;
    u16 requiredOwnerId;
    u16 effectiveProfileId;
    u8 kind;
    u8 selectorKind;
    u8 semanticRole;
    u8 tiredOriginKind;
    u8 flags;
    u8 mapLifetime;
    u8 battleLifetime;
    u8 applicabilitySemanticRole;
    u8 channel;
    u8 priority;
} OverworldWildRuntimeDefinition;

typedef char OverworldWildRuntimeDefinitionSizeMustRemain24[
    sizeof(OverworldWildRuntimeDefinition) == 24 ? 1 : -1];

BOOL OverworldWildRuntime_CopyInstalledDefinition(
    u16 definitionId,
    OverworldWildRuntimeDefinition *definitionOut);
BOOL OverworldWildRuntime_CopyInstalledCatalogIdentity(u32 *identityOut);

typedef struct OverworldWildRuntimeStaticComposition {
    u32 catalogIdentity;
    u32 staticContextIdentity;
    u32 staticSetHash;
    u32 immutableContextMask;
    OverworldWildRuntimeStaticContext staticContext;
    u16 controllerId;
    u16 baseNodeId;
    u16 baseProfileId;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u8 baseSemanticRole;
    u8 valid;
    u8 nodeCount;
    u8 boundNodeCount;
    u8 semanticRoleMask;
    u8 staticModifierCount;
    u8 reserved;
    u8 padding[3];
    u8 stateValues[OW_WILD_RUNTIME_STATE_VALUE_COUNT];
    u8 controllerValues[OW_WILD_RUNTIME_CONTROLLER_VALUE_COUNT];
    OverworldWildRuntimeResolvedNode
        resolvedNodes[OW_WILD_RUNTIME_MAX_RESOLVED_NODES];
    OverworldWildRuntimeStaticModifierContribution
        staticModifiers[OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS];
} OverworldWildRuntimeStaticComposition;

typedef struct OverworldWildRuntimeModifierOperation {
    signed short operand;
    u8 fieldNamespace;
    u8 fieldId;
    u8 operatorKind;
    u8 bound;
} OverworldWildRuntimeModifierOperation;

BOOL OverworldWildRuntime_CopyInstalledStaticComposition(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    OverworldWildRuntimeStaticComposition *compositionOut);
BOOL OverworldWildRuntime_CopyInstalledStaticCache(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    u32 staticContextGeneration,
    OverworldWildRuntimeStaticCache *cacheOut);
OverworldWildRuntimeStatus OverworldWildRuntime_ResolveRetainedStaticCache(
    const OverworldWildRuntimeStaticCache *retainedCache,
    const OverworldWildRuntimeStaticContext *staticContext,
    u32 staticContextGeneration,
    OverworldWildRuntimeStaticCache *resolvedOut);
BOOL OverworldWildRuntime_ApplicabilityMatchesStaticCache(
    const OverworldWildRuntimeApplicabilityInput *input,
    const OverworldWildRuntimeStaticCache *cache);
OverworldWildRuntimeStatus OverworldWildRuntime_ValidateStaticCache(
    const OverworldWildRuntimeStaticCache *cache,
    u32 staticContextGeneration);
BOOL OverworldWildRuntime_CopyInstalledResolvedNode(
    const OverworldWildRuntimeStaticComposition *composition,
    const OverworldWildRuntimeDefinition *definition,
    OverworldWildRuntimeResolvedNode *nodeOut);
BOOL OverworldWildRuntime_CopyResolvedCachedNode(
    const OverworldWildRuntimeStaticCache *cache,
    const OverworldWildRuntimeDefinition *definition,
    OverworldWildRuntimeResolvedNode *nodeOut);
BOOL OverworldWildRuntime_CopyInstalledModifierOperations(
    u16 definitionId,
    OverworldWildRuntimeModifierOperation *operationsOut,
    u8 capacity,
    u8 *operationCountOut);

/* Exact Task-5 v40 scalar-domain implementation, resident once in overlay
 * 155 and imported into overlay 158 through a package-verified typed shard. */
#ifndef OW_WILD_RUNTIME_HOST_TEST
extern const u8 sOwbdStateValueMax[OW_WILD_RUNTIME_STATE_VALUE_COUNT];
extern const u32 sOwbdNumericFieldMasks[4];
BOOL OwbdStaticValueValid(u8 kind, u8 field, u8 value);
BOOL OwbdModifierPayloadValid(
    u8 kind,
    u8 field,
    u8 operatorKind,
    signed char delta,
    u8 bound);
#endif

u8 OverworldWildRuntime_CountInstalledTiredTranslations(
    u8 tiredOriginKind,
    u16 destinationControllerId,
    BOOL authoredTiredBound,
    u16 *candidateDefinitionIdOut);

void OverworldWildBehavior_ReleaseValidatedBundle(void *projection);
void OverworldWildBehavior_FreeValidatedBundle(void *projection);

/* Overlay 155 delegates every live destructive reset through this typed
 * overlay-158 entry; it owns both the ordinary and generation-wrap routes. */
void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlotIndex);

#endif
