#ifndef OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/constants/file.h"
#include "overworld_wild_runtime_layers_internal.h"
#endif

static const u8 *sOverworldWildValidatedV40;

#ifndef OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
OverworldWildBehaviorLoadResult
    __attribute__((section(".overworld_wild_runtime_entry"), noinline, used))
OverworldWildBehavior_LoadValidatedBundle(
    OverworldWildBehaviorSemanticValidator validator,
    void **projectionOut)
{
    void *narc;
    void *workspace;
    u8 *bundle;
    u32 size;

    *projectionOut = NULL;
    if (sOverworldWildValidatedV40 != NULL)
        return OWBD_LOAD_PERMANENT_INVALID;
    narc = NARC_ctor(ARC_CODE_ADDONS, HEAPID_WORLD);
    if (narc == NULL) return OWBD_LOAD_TRANSIENT_FAILURE;
    if (NARC_GetFileCount(narc)
            <= CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_PROJECTION
        || NARC_GetMemberSize(narc, CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA)
            != OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE
        || NARC_GetMemberSize(narc,
                CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_PROJECTION)
            != OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE) {
        NARC_dtor(narc);
        return OWBD_LOAD_PERMANENT_INVALID;
    }
    workspace = sys_AllocMemory(
        HEAPID_WORLD, OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE);
    if (workspace == NULL) {
        NARC_dtor(narc);
        return OWBD_LOAD_TRANSIENT_FAILURE;
    }
    if (!validator(narc, OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE,
            workspace, OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE)) {
        sys_FreeMemoryEz(workspace);
        NARC_dtor(narc);
        return OWBD_LOAD_PERMANENT_INVALID;
    }
    sys_FreeMemoryEz(workspace);
    size = OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE
        + OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE;
    bundle = sys_AllocMemory(HEAPID_WORLD, size);
    if (bundle == NULL) {
        NARC_dtor(narc);
        return OWBD_LOAD_TRANSIENT_FAILURE;
    }
    NARC_ReadWholeMember(narc,
        CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_PROJECTION, bundle);
    NARC_ReadWholeMember(narc, CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA,
        bundle + OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE);
    NARC_dtor(narc);
    if (!validator(NULL, OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE,
            bundle, 0)) {
        sys_FreeMemoryEz(bundle);
        return OWBD_LOAD_PERMANENT_INVALID;
    }
    sOverworldWildValidatedV40 =
        bundle + OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE;
    *projectionOut = bundle;
    return OWBD_LOAD_SUCCESS;
}

void OverworldWildBehavior_ReleaseValidatedBundle(void *projection)
{
    if (projection != NULL
        && sOverworldWildValidatedV40
            == (const u8 *)projection
                + OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE) {
        sOverworldWildValidatedV40 = NULL;
    }
}

void OverworldWildBehavior_FreeValidatedBundle(void *projection)
{
    OverworldWildBehavior_ReleaseValidatedBundle(projection);
    sys_FreeMemoryEz(projection);
}
#endif

BOOL OverworldWildRuntime_CopyInstalledDefinition(
    u16 definitionId,
    OverworldWildRuntimeDefinition *definitionOut)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildOverrideDefinitionRecord *definitions;
    const OverworldWildApplicabilityRecord *applicability;
    const OverworldWildOverrideDefinitionRecord *definition = NULL;
    const OverworldWildApplicabilityRecord *application = NULL;
    u16 index;
    u8 flags = OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE;

    memset(definitionOut, 0, sizeof(*definitionOut));
    if (sOverworldWildValidatedV40 == NULL) return FALSE;
    header = (const void *)sOverworldWildValidatedV40;
    definitions = (const void *)(sOverworldWildValidatedV40
        + header->overrideDefinitions.offset);
    applicability = (const void *)(sOverworldWildValidatedV40
        + header->applicability.offset);
    for (index = 0; index < header->overrideDefinitions.count; index++) {
        if (definitions[index].stableId == definitionId) {
            definition = &definitions[index];
            break;
        }
    }
    if (definition == NULL) return FALSE;
    for (index = 0; index < header->applicability.count; index++) {
        if (applicability[index].stableId == definition->applicabilityId) {
            application = &applicability[index];
            break;
        }
    }
    if (application == NULL) return FALSE;
    if (definition->hasTiredOriginKind)
        flags |= OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN;
    if (definition->hasRequiredOwnerId)
        flags |= OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER;
    if (definition->allowMultipleOwners)
        flags |= OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS;
    if (definition->allowMultipleInstancesPerOwner)
        flags |= OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES;
    definitionOut->immutableContextMask = application->immutableContextMask;
    definitionOut->stableId = definition->stableId;
    definitionOut->controllerId = definition->controllerId != 0
        ? definition->controllerId : application->controllerId;
    definitionOut->nodeId = definition->nodeId;
    definitionOut->requiredOwnerId = definition->requiredOwnerId;
    definitionOut->effectiveProfileId = application->effectiveProfileId;
    definitionOut->kind = definition->kind;
    definitionOut->selectorKind = definition->selectorKind;
    definitionOut->semanticRole = definition->semanticRole;
    definitionOut->tiredOriginKind = definition->tiredOriginKind;
    definitionOut->flags = flags;
    definitionOut->mapLifetime = definition->mapLifetime;
    definitionOut->battleLifetime = definition->battleLifetime;
    definitionOut->applicabilitySemanticRole = application->semanticRole;
    return TRUE;
}

u8 OverworldWildRuntime_CountInstalledTiredTranslations(
    u8 tiredOriginKind,
    u16 destinationControllerId,
    BOOL authoredTiredBound,
    u16 *candidateDefinitionIdOut)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildTiredTranslationRecord *translations;
    u16 index;
    u8 count = 0;

    if (candidateDefinitionIdOut == NULL) return 0;
    *candidateDefinitionIdOut = 0;
    if (sOverworldWildValidatedV40 == NULL) return 0;
    header = (const void *)sOverworldWildValidatedV40;
    translations = (const void *)(sOverworldWildValidatedV40
        + header->tiredTranslations.offset);
    for (index = 0; index < header->tiredTranslations.count; index++) {
        if (translations[index].tiredOriginKind == tiredOriginKind
            && translations[index].destinationControllerId
                == destinationControllerId
            && translations[index].authoredTiredBound
                == (authoredTiredBound != FALSE)) {
            if (count == 0)
                *candidateDefinitionIdOut =
                    translations[index].candidateDefinitionId;
            if (count != 0xFF) count++;
        }
    }
    return count;
}
