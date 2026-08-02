#ifndef OVERWORLD_WILD_RUNTIME_LAYERS_INTERNAL_H
#define OVERWORLD_WILD_RUNTIME_LAYERS_INTERNAL_H

#include "../overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"

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
    u8 reserved[2];
} OverworldWildRuntimeDefinition;

typedef char OverworldWildRuntimeDefinitionSizeMustRemain24[
    sizeof(OverworldWildRuntimeDefinition) == 24 ? 1 : -1];

BOOL OverworldWildRuntime_CopyInstalledDefinition(
    u16 definitionId,
    OverworldWildRuntimeDefinition *definitionOut);
u8 OverworldWildRuntime_CountInstalledTiredTranslations(
    u8 tiredOriginKind,
    u16 destinationControllerId,
    BOOL authoredTiredBound,
    u16 *candidateDefinitionIdOut);

void OverworldWildBehavior_ReleaseValidatedBundle(void *projection);
void OverworldWildBehavior_FreeValidatedBundle(void *projection);

/* Task-7 calls this before publishing a wrapped slot generation. */
void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlotIndex);

#endif
