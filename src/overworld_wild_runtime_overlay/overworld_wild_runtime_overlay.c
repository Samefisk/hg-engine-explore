#ifndef OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/constants/file.h"
#include "overworld_wild_runtime_layers_internal.h"
#endif

static const u8 *sOverworldWildValidatedV40;

#ifndef OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
void OverworldWildRuntime_MarkResidentCold(
    OverworldWildBehaviorStackRuntime *runtime)
{
    int slot;
    runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        runtime->dataIncarnation);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        runtime->slots[slot].cacheIncarnation =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->slots[slot].cacheIncarnation);
        memset(&runtime->slots[slot].effectiveCache, 0,
            sizeof(runtime->slots[slot].effectiveCache));
        memset(&runtime->slots[slot].provenance, 0,
            sizeof(runtime->slots[slot].provenance));
    }
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD;
}

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
    definitionOut->channel = definition->channel;
    definitionOut->priority = (u8)definition->priority;
    return TRUE;
}

static u32 RuntimeCatalogMix(u32 value, u32 input)
{
    value ^= input + 0x9E3779B9u + (value << 6) + (value >> 2);
    value ^= value >> 16;
    value *= 0x7FEB352Du;
    return value ^ (value >> 15);
}

static u32 RuntimeCatalogHashBytes(u32 hash, const void *data, u32 size)
{
    const u8 *bytes = data;
    while (size-- != 0) hash = RuntimeCatalogMix(hash, *bytes++);
    return hash != 0 ? hash : 1;
}

static u32 StaticCompositionSetHash(
    const OverworldWildRuntimeStaticComposition *composition)
{
    u32 hash = RuntimeCatalogMix(0x4F575339u,
        composition->catalogIdentity);
    hash = RuntimeCatalogMix(hash, composition->staticContextIdentity);
    return RuntimeCatalogHashBytes(hash, &composition->immutableContextMask,
        sizeof(*composition) - offsetof(OverworldWildRuntimeStaticComposition,
            immutableContextMask));
}

BOOL OverworldWildRuntime_CopyInstalledCatalogIdentity(u32 *identityOut)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    u32 identity;
    if (identityOut == NULL) return FALSE;
    *identityOut = 0;
    if (sOverworldWildValidatedV40 == NULL) return FALSE;
    header = (const void *)sOverworldWildValidatedV40;
    identity = RuntimeCatalogMix(header->schemaFingerprint, header->checksum);
    *identityOut = identity == 0 ? 1 : identity;
    return TRUE;
}

#ifndef OW_WILD_RUNTIME_DISABLE_TRANSITION_VIEW
const OverworldWildBehaviorDataBlobHeader *
OverworldWildRuntime_AcquireInstalledTransitionCatalog(void)
{
    return (const void *)sOverworldWildValidatedV40;
}
#endif

static BOOL CopyProfileValues(
    const OverworldWildBehaviorDataBlobHeader *header,
    u16 profileId,
    u8 *valuesOut)
{
    const OverworldWildProfileIdentityRecord *profiles;
    const OverworldWildStateBodyRecord *bodies;
    u16 bodyId = 0;
    u16 i;

    profiles = (const void *)(sOverworldWildValidatedV40
        + header->profileIdentities.offset);
    bodies = (const void *)(sOverworldWildValidatedV40
        + header->stateBodies.offset);
    for (i = 0; i < header->profileIdentities.count; i++) {
        if (profiles[i].stableId == profileId) {
            bodyId = profiles[i].bodyId;
            break;
        }
    }
    if (bodyId == 0) return FALSE;
    for (i = 0; i < header->stateBodies.count; i++) {
        if (bodies[i].stableId == bodyId
            && bodies[i].valueCount == OW_WILD_RUNTIME_STATE_VALUE_COUNT) {
            memcpy(valuesOut, (void *)bodies[i].values,
                OW_WILD_RUNTIME_STATE_VALUE_COUNT);
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL StaticMatch(
    const OverworldWildRuntimeStaticContext *context,
    const OverworldWildBehaviorMatch *match)
{
    return (match->species == 0 || match->species == context->species)
        && (match->groupMask == 0
            || (match->groupMask & context->groupFlags) != 0)
        && (match->terrain == 0xFF || match->terrain == context->terrain)
        && (match->minLevel == 0 || context->level >= match->minLevel)
        && (match->maxLevel == 0 || context->level <= match->maxLevel)
        && (match->shiny == 0xFF || match->shiny == context->shiny)
        && (match->behaviorClass == 0xFF
            || match->behaviorClass == context->behaviorClass);
}

static BOOL SourceTargetsSpecies(
    const OverworldWildBehaviorDataBlobHeader *header,
    const OverworldWildOverrideSourceRecord *source,
    u16 species)
{
    const u16 *members;
    u16 i;
    if (source->targetMode == 2) return TRUE;
    if (source->targetMode != 1) return FALSE;
    members = (const void *)(sOverworldWildValidatedV40
        + header->overrideMembers.offset);
    for (i = 0; i < source->memberCount; i++)
        if (members[source->memberStart + i] == species) return TRUE;
    return FALSE;
}

static BOOL ApplyStaticScalar(
    u8 kind,
    const OverworldWildStaticActionRecord *action,
    u8 *values,
    u8 fieldIndex,
    OverworldWildRuntimeStaticModifierContribution *recordOut)
{
    const u8 field = action->payload.modifier.fieldId;
    const u8 operation = action->payload.modifier.operatorKind;
    const signed char delta = action->payload.modifier.delta;
    const u8 bound = action->payload.modifier.bound;
    const int maskIndex = kind == 4 ? 0 : kind == 5 ? 1 : kind == 7 ? 2 : 3;
    const BOOL numeric = (sOwbdNumericFieldMasks[maskIndex]
        & (1u << field)) != 0;
    const int minimum = (kind == 4 && field == 3)
        || (kind == 7 && (field == 3 || field == 4)) ? 1 : 0;
    int maximum = 255;
    int result;
    const u8 before = values[fieldIndex];

    if (!OwbdModifierPayloadValid(kind, field, operation, delta, bound)
        || !OwbdStaticValueValid(kind, field, before) || before < minimum)
        return FALSE;
    while (maximum != 0 && !OwbdStaticValueValid(kind, field, maximum))
        maximum--;
    if (!numeric && operation != OW_WILD_RUNTIME_OPERATOR_SET) return FALSE;
    if ((operation == OW_WILD_RUNTIME_OPERATOR_SET
            || operation == OW_WILD_RUNTIME_OPERATOR_AT_LEAST
            || operation == OW_WILD_RUNTIME_OPERATOR_AT_MOST)
        && ((u8)delta < minimum || (u8)delta > maximum)) return FALSE;
    if ((operation == OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST
            || operation == OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST)
        && (bound < minimum || bound > maximum)) return FALSE;
    switch (operation) {
    case OW_WILD_RUNTIME_OPERATOR_SET: result = (u8)delta; break;
    case OW_WILD_RUNTIME_OPERATOR_ADD: result = before + delta; break;
    case OW_WILD_RUNTIME_OPERATOR_AT_LEAST:
        result = before > (u8)delta ? before : (u8)delta; break;
    case OW_WILD_RUNTIME_OPERATOR_AT_MOST:
        result = before < (u8)delta ? before : (u8)delta; break;
    case OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST:
        result = before + delta;
        if (result < minimum) result = minimum;
        if (result > maximum) result = maximum;
        if (result < bound) result = bound;
        break;
    case OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST:
        result = before + delta;
        if (result < minimum) result = minimum;
        if (result > maximum) result = maximum;
        if (result > bound) result = bound;
        break;
    default: return FALSE;
    }
    if (result < minimum) result = minimum;
    if (result > maximum) result = maximum;
    values[fieldIndex] = (u8)result;
    if (recordOut != NULL) {
        recordOut->operand = delta;
        recordOut->fieldNamespace = kind == 4
            ? OW_WILD_RUNTIME_FIELD_STATE : OW_WILD_RUNTIME_FIELD_CONTROLLER;
        recordOut->fieldId = field;
        recordOut->operatorKind = operation;
        recordOut->bound = bound;
        recordOut->before = before;
        recordOut->after = (u8)result;
    }
    return TRUE;
}

static BOOL CopyPolicyValues(
    const OverworldWildBlobSection *section,
    u16 stableId,
    u8 valueOffset,
    u8 valueSize,
    u8 *valuesOut)
{
    const u8 *records = sOverworldWildValidatedV40 + section->offset;
    u16 index;
    for (index = 0; index < section->count; index++) {
        const u8 *record = records + (u32)index * section->entrySize;
        if ((u16)(record[0] | ((u16)record[1] << 8)) != stableId) continue;
        memcpy(valuesOut, (void *)(record + valueOffset), valueSize);
        return TRUE;
    }
    return FALSE;
}

static const OverworldWildOverrideSourceRecord *MatchingSourceAtRank(
    const OverworldWildBehaviorDataBlobHeader *header,
    const OverworldWildOverrideSourceRecord *sources,
    const OverworldWildRuntimeStaticContext *context,
    u16 rank)
{
    u16 candidateIndex;
    for (candidateIndex = 0; candidateIndex < header->overrideSources.count;
            candidateIndex++) {
        const OverworldWildOverrideSourceRecord *candidate =
            &sources[candidateIndex];
        u16 priorIndex;
        u16 candidateRank = 0;
        if (!StaticMatch(context, &candidate->match)
            || !SourceTargetsSpecies(header, candidate, context->species))
            continue;
        for (priorIndex = 0; priorIndex < header->overrideSources.count;
                priorIndex++) {
            const OverworldWildOverrideSourceRecord *prior =
                &sources[priorIndex];
            if (!StaticMatch(context, &prior->match)
                || !SourceTargetsSpecies(header, prior, context->species))
                continue;
            if (prior->priority < candidate->priority
                || (prior->priority == candidate->priority
                    && prior->stableId < candidate->stableId))
                candidateRank++;
        }
        if (candidateRank == rank) return candidate;
    }
    return NULL;
}

static const OverworldWildStaticActionRecord *SourceActionAtRank(
    const OverworldWildOverrideSourceRecord *source,
    const OverworldWildStaticActionRecord *actions,
    u16 rank)
{
    u16 candidateIndex;
    for (candidateIndex = 0; candidateIndex < source->actionCount;
            candidateIndex++) {
        const OverworldWildStaticActionRecord *candidate =
            &actions[source->actionStart + candidateIndex];
        u16 priorIndex;
        u16 candidateRank = 0;
        for (priorIndex = 0; priorIndex < source->actionCount; priorIndex++)
            if (actions[source->actionStart + priorIndex].stableId
                    < candidate->stableId)
                candidateRank++;
        if (candidateRank == rank) return candidate;
    }
    return NULL;
}

static OverworldWildRuntimeResolvedNode *FindResolvedNode(
    OverworldWildRuntimeStaticComposition *composition,
    u16 nodeId)
{
    u8 index;
    for (index = 0; index < composition->nodeCount; index++)
        if (composition->resolvedNodes[index].nodeId == nodeId)
            return &composition->resolvedNodes[index];
    return NULL;
}

static void RecordStaticContribution(
    OverworldWildRuntimeStaticComposition *composition,
    const OverworldWildRuntimeStaticModifierContribution *record)
{
    if (composition->staticModifierCount
            < OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS) {
        composition->staticModifiers[composition->staticModifierCount++] =
            *record;
    } else {
        composition->reserved = 1;
    }
}

static BOOL CanonicalApplicabilityMatches(
    const OverworldWildRuntimeStaticComposition *composition,
    const OverworldWildRuntimeApplicabilityInput *input)
{
    u8 inputIndex = 0;
    u8 nodeIndex;
    if (input->immutableContextMask != composition->immutableContextMask
        || input->controllerId != composition->controllerId
        || input->effectiveProfileId != composition->baseProfileId
        || input->effectiveSemanticRole != composition->baseSemanticRole
        || input->boundNodeCount != composition->boundNodeCount
        || input->semanticRoleMask != composition->semanticRoleMask)
        return FALSE;
    for (nodeIndex = 0; nodeIndex < composition->nodeCount; nodeIndex++) {
        const OverworldWildRuntimeResolvedNode *node =
            &composition->resolvedNodes[nodeIndex];
        if (!node->bound) continue;
        if (inputIndex >= input->boundNodeCount
            || input->boundNodeIds[inputIndex++] != node->nodeId)
            return FALSE;
    }
    return inputIndex == input->boundNodeCount;
}

BOOL OverworldWildRuntime_ResolveInstalledTimerDefinition(
    u16 definitionId,
    const OverworldWildRuntimeStaticCache *staticCache,
    OverworldWildRuntimeTimerDefinition *timerOut)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildOverrideDefinitionRecord *definitions;
    const OverworldWildOverrideSourceRecord *sources;
    const OverworldWildStaticActionRecord *actions;
    const OverworldWildOverrideDefinitionRecord *definition = NULL;
    OverworldWildRuntimeDefinition runtimeDefinition;
    OverworldWildRuntimeResolvedNode node;
    u16 i, j;
    int duration;
    BOOL asleep;

    if (timerOut == NULL) return FALSE;
    memset(timerOut, 0, sizeof(*timerOut));
    if (sOverworldWildValidatedV40 == NULL
        || !OverworldWildRuntime_CopyInstalledDefinition(
            definitionId, &runtimeDefinition)) return FALSE;
    header = (const void *)sOverworldWildValidatedV40;
    definitions = (const void *)(sOverworldWildValidatedV40
        + header->overrideDefinitions.offset);
    sources = (const void *)(sOverworldWildValidatedV40
        + header->overrideSources.offset);
    actions = (const void *)(sOverworldWildValidatedV40
        + header->overrideActions.offset);
    for (i = 0; i < header->overrideDefinitions.count; i++) {
        if (definitions[i].stableId == definitionId) {
            definition = &definitions[i];
            break;
        }
    }
    if (definition == NULL || definition->kind != OWBD_OVERRIDE_KIND_STATE_CANDIDATE)
        return definition != NULL && definition->timerClock == OWBD_TIMER_CLOCK_NONE;
    timerOut->recoveryTransitionId = definition->recoveryTransitionId;
    timerOut->clock = definition->timerClock;
    timerOut->source = definition->timerSource;
    timerOut->hiddenPolicy = definition->hiddenTimerPolicy;
    timerOut->recoveryPolicy = definition->recoveryPolicy;
    if (timerOut->clock == OWBD_TIMER_CLOCK_NONE) {
        timerOut->source = OWBD_TIMER_SOURCE_NONE;
        timerOut->hiddenPolicy = OWBD_HIDDEN_TIMER_NONE;
        timerOut->duration = 0;
        return TRUE;
    }
    if ((timerOut->clock != OWBD_TIMER_CLOCK_FRAME
            && timerOut->clock != OWBD_TIMER_CLOCK_COMPLETED_MOVEMENT)
        || timerOut->source == OWBD_TIMER_SOURCE_NONE
        || timerOut->source > OWBD_TIMER_SOURCE_CANDIDATE_FOLD
        || timerOut->hiddenPolicy < OWBD_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN
        || timerOut->hiddenPolicy > OWBD_HIDDEN_TIMER_EXPIRE_ON_HIDE
        || timerOut->recoveryPolicy != OWBD_RECOVERY_ROUTE_TRANSITION)
        return FALSE;
    /* A NULL cache requests validated timer identity metadata only. */
    if (staticCache == NULL) return TRUE;
    if (staticCache->valid == 0 || staticCache->staticContext.reserved != 0
        || !OverworldWildRuntime_CopyResolvedCachedNode(
            staticCache, &runtimeDefinition, &node)) return FALSE;

    duration = definition->timerValue;
    if (timerOut->source == OWBD_TIMER_SOURCE_CONTROLLER_STAMINA)
        duration = staticCache->controllerValues[6];
    if (timerOut->source == OWBD_TIMER_SOURCE_CANDIDATE_FOLD) {
        for (i = 0; i < header->overrideSources.count; i++) {
            const OverworldWildOverrideSourceRecord *source =
                MatchingSourceAtRank(header, sources,
                    &staticCache->staticContext, i);
            if (source == NULL) break;
            for (j = 0; j < source->actionCount; j++) {
                const OverworldWildStaticActionRecord *action =
                    SourceActionAtRank(source, actions, j);
                int operand;
                if (action == NULL) return FALSE;
                if (action->kind
                        != OWBD_STATIC_ACTION_APPLY_CANDIDATE_TIMER_OPERATOR
                    || action->payload.timer.controllerId
                        != staticCache->controllerId
                    || action->payload.timer.nodeId != node.nodeId)
                    continue;
                if (action->payload.timer.reserved != 0) return FALSE;
                if (action->payload.timer.operatorKind
                        == OWBD_CANDIDATE_TIMER_SET) {
                    duration = action->payload.timer.operand;
                } else if (action->payload.timer.operatorKind
                        == OWBD_CANDIDATE_TIMER_ADD) {
                    operand = (signed char)action->payload.timer.operand;
                    duration += operand;
                    if (duration < 0) duration = 0;
                    if (duration > OWBD_CANDIDATE_TIMER_ADD_CLAMP_MAX)
                        duration = OWBD_CANDIDATE_TIMER_ADD_CLAMP_MAX;
                } else {
                    return FALSE;
                }
            }
        }
    }
    asleep = node.semanticRole == OWBD_ROLE_ASLEEP;
    if (asleep && duration == 0) duration = 255;
    else if (node.semanticRole == OWBD_ROLE_TIRED && duration == 0) duration = 1;
    else if (duration >= 255) duration = 254;
    timerOut->duration = (u8)duration;
    return TRUE;
}

static BOOL CopyInstalledStaticCompositionInternal(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    OverworldWildRuntimeStaticComposition *compositionOut)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildControllerRecord *controllers;
    const OverworldWildControllerNodeRecord *nodes;
    const OverworldWildGenericAssignmentRecord *genericAssignments;
    const OverworldWildSpeciesAssignmentRecord *speciesAssignments;
    const OverworldWildOverrideSourceRecord *sources;
    const OverworldWildStaticActionRecord *actions;
    const OverworldWildControllerRecord *controller = NULL;
    OverworldWildRuntimeResolvedNode *base = NULL;
    u16 selectedControllerId;
    u16 selectedPriority = 0;
    u16 selectedRuleId = 0;
    u16 selectedActionId = 0;
    u16 hookSetId;
    u16 i, j;

    if (compositionOut == NULL) return FALSE;
    memset(compositionOut, 0, sizeof(*compositionOut));
    if (sOverworldWildValidatedV40 == NULL
        || staticContext == NULL || staticContext->reserved != 0
        || staticContext->shiny > 1) return FALSE;
    header = (const void *)sOverworldWildValidatedV40;
    controllers = (const void *)(sOverworldWildValidatedV40
        + header->controllers.offset);
    nodes = (const void *)(sOverworldWildValidatedV40
        + header->controllerNodes.offset);
    genericAssignments = (const void *)(sOverworldWildValidatedV40
        + header->genericAssignments.offset);
    speciesAssignments = (const void *)(sOverworldWildValidatedV40
        + header->speciesAssignments.offset);
    sources = (const void *)(sOverworldWildValidatedV40
        + header->overrideSources.offset);
    actions = (const void *)(sOverworldWildValidatedV40
        + header->overrideActions.offset);
    if (staticContext->behaviorClass >= header->controllers.count) return FALSE;
    selectedControllerId = controllers[staticContext->behaviorClass].stableId;
    for (i = 0; i < header->genericAssignments.count; i++) {
        const OverworldWildGenericAssignmentRecord *assignment =
            &genericAssignments[i];
        const OverworldWildStaticActionRecord *action =
            &actions[assignment->assignmentActionIndex];
        if (!StaticMatch(staticContext, &assignment->match)) continue;
        if (assignment->priority > selectedPriority
            || (assignment->priority == selectedPriority
                && (assignment->stableId > selectedRuleId
                    || (assignment->stableId == selectedRuleId
                        && action->stableId > selectedActionId)))) {
            selectedPriority = assignment->priority;
            selectedRuleId = assignment->stableId;
            selectedActionId = action->stableId;
            selectedControllerId = action->payload.assignController.controllerId;
        }
    }
    for (i = 0; i < header->speciesAssignments.count; i++) {
        const OverworldWildSpeciesAssignmentRecord *assignment =
            &speciesAssignments[i];
        const OverworldWildStaticActionRecord *action =
            &actions[assignment->assignmentActionIndex];
        if (assignment->species != staticContext->species) continue;
        if (assignment->priority > selectedPriority
            || (assignment->priority == selectedPriority
                && (assignment->stableId > selectedRuleId
                    || (assignment->stableId == selectedRuleId
                        && action->stableId > selectedActionId)))) {
            selectedPriority = assignment->priority;
            selectedRuleId = assignment->stableId;
            selectedActionId = action->stableId;
            selectedControllerId = action->payload.assignController.controllerId;
        }
    }
    for (i = 0; i < header->controllers.count; i++) {
        if (controllers[i].stableId == selectedControllerId) {
            controller = &controllers[i];
            break;
        }
    }
    if (controller == NULL) return FALSE;
    if (controller->nodeCount == 0
        || controller->nodeCount > OW_WILD_RUNTIME_MAX_RESOLVED_NODES)
        return FALSE;
    compositionOut->nodeCount = (u8)controller->nodeCount;
    /* Copy the complete controller roster in stable-ID order.  Runtime code
     * never consults the authored node table after this boundary. */
    for (i = 0; i < controller->nodeCount; i++) {
        const OverworldWildControllerNodeRecord *selected = NULL;
        u16 candidateIndex;
        for (candidateIndex = 0; candidateIndex < controller->nodeCount;
                candidateIndex++) {
            const OverworldWildControllerNodeRecord *candidate =
                &nodes[controller->nodeStart + candidateIndex];
            u16 priorIndex;
            u16 rank = 0;
            if (candidate->controllerId != controller->stableId) return FALSE;
            for (priorIndex = 0; priorIndex < controller->nodeCount;
                    priorIndex++)
                if (nodes[controller->nodeStart + priorIndex].stableId
                        < candidate->stableId)
                    rank++;
            if (rank == i) {
                selected = candidate;
                break;
            }
        }
        if (selected == NULL || selected->profileIdentityId == 0
            || selected->semanticRole == 0 || selected->semanticRole > 7)
            return FALSE;
        compositionOut->resolvedNodes[i].nodeId = selected->stableId;
        compositionOut->resolvedNodes[i].profileId =
            selected->profileIdentityId;
        compositionOut->resolvedNodes[i].customRoleId =
            selected->customRoleId;
        compositionOut->resolvedNodes[i].semanticRole =
            selected->semanticRole;
        compositionOut->resolvedNodes[i].flags = selected->flags;
        compositionOut->resolvedNodes[i].bound = TRUE;
        if (!CopyProfileValues(header, selected->profileIdentityId,
                compositionOut->resolvedNodes[i].stateValues)) return FALSE;
        if (selected->flags & OWBD_NODE_FLAG_BASE) {
            if (base != NULL) return FALSE;
            base = &compositionOut->resolvedNodes[i];
        }
    }
    if (base == NULL) return FALSE;
    /* Complete binding phase: all matching BIND/UNBIND actions fold into the
     * copied roster before any role-scoped state scalar action is applied. */
    for (i = 0; i < header->overrideSources.count; i++) {
        const OverworldWildOverrideSourceRecord *source =
            MatchingSourceAtRank(header, sources, staticContext, i);
        if (source == NULL) break;
        for (j = 0; j < source->actionCount; j++) {
            const OverworldWildStaticActionRecord *action =
                SourceActionAtRank(source, actions, j);
            OverworldWildRuntimeResolvedNode *target;
            if (action == NULL) return FALSE;
            if (action->kind != OWBD_STATIC_ACTION_BIND_NODE
                && action->kind != OWBD_STATIC_ACTION_UNBIND_NODE) continue;
            if (action->payload.bindNode.controllerId
                    != controller->stableId) continue;
            target = FindResolvedNode(compositionOut,
                action->payload.bindNode.nodeId);
            if (target == NULL) return FALSE;
            if (action->kind == OWBD_STATIC_ACTION_UNBIND_NODE) {
                if (target == base) return FALSE;
                target->profileId = 0;
                target->bound = FALSE;
                memset(target->stateValues, 0, sizeof(target->stateValues));
            } else {
                target->profileId =
                    action->payload.bindNode.profileIdentityId;
                target->bound = TRUE;
                if (!CopyProfileValues(header, target->profileId,
                        target->stateValues)) return FALSE;
            }
        }
    }
    compositionOut->catalogIdentity = RuntimeCatalogMix(
        header->schemaFingerprint, header->checksum);
    if (compositionOut->catalogIdentity == 0)
        compositionOut->catalogIdentity = 1;
    compositionOut->controllerId = controller->stableId;
    compositionOut->valid = TRUE;
    compositionOut->immutableContextMask = staticContext->groupFlags;
    compositionOut->staticContext = *staticContext;
    compositionOut->baseNodeId = base->nodeId;
    compositionOut->baseProfileId = base->profileId;
    compositionOut->spawnPolicyId = controller->spawnPolicyId;
    compositionOut->populationPolicyId = controller->populationPolicyId;
    hookSetId = controller->hookSetId;
    memset(&compositionOut->spawnConfiguration, 0,
        sizeof(compositionOut->spawnConfiguration));
    if (!CopyPolicyValues(&header->spawnPolicies,
            compositionOut->spawnPolicyId, 6, 6,
            &compositionOut->spawnConfiguration.spawnState)
        || !CopyPolicyValues(&header->populationPolicies,
            compositionOut->populationPolicyId, 8, 2,
            &compositionOut->spawnConfiguration.populationLimit)
        || !CopyPolicyValues(&header->hookSets, hookSetId, 4, 4,
            &compositionOut->spawnConfiguration.helpCallInvocation))
        return FALSE;
    compositionOut->baseSemanticRole = base->semanticRole;
    compositionOut->controllerValues[0] = controller->alertState;
    compositionOut->controllerValues[1] = controller->alertEmote;
    compositionOut->controllerValues[2] = controller->alertTime;
    compositionOut->controllerValues[3] = controller->alertness;
    compositionOut->controllerValues[4] = controller->alertRange;
    compositionOut->controllerValues[5] = controller->alertChance;
    compositionOut->controllerValues[6] = controller->stamina;
    compositionOut->controllerValues[7] = controller->restTime;
    compositionOut->controllerValues[8] = controller->flags;
    /* The validated v40 source priority is the staticPriority.  Sources are
     * already validated unique; select the next complete key explicitly so
     * serialized array position is never a composition tie-break. */
    for (i = 0; i < header->overrideSources.count; i++) {
        const OverworldWildOverrideSourceRecord *source =
            MatchingSourceAtRank(header, sources, staticContext, i);
        if (source == NULL) break;
        for (j = 0; j < source->actionCount; j++) {
            const OverworldWildStaticActionRecord *action =
                SourceActionAtRank(source, actions, j);
            OverworldWildRuntimeStaticModifierContribution scratchRecord;
            if (action == NULL) return FALSE;
            if (action->kind == OWBD_STATIC_ACTION_APPLY_STATE_MODIFIER) {
                u8 nodeIndex;
                if (action->payload.modifier.controllerId != 0
                    && action->payload.modifier.controllerId
                        != controller->stableId) continue;
                for (nodeIndex = 0; nodeIndex < compositionOut->nodeCount;
                        nodeIndex++) {
                    OverworldWildRuntimeResolvedNode *target =
                        &compositionOut->resolvedNodes[nodeIndex];
                    if (!target->bound
                        || !(action->payload.modifier.semanticRoleMask
                            & (1u << (target->semanticRole - 1)))) continue;
                    memset(&scratchRecord, 0, sizeof(scratchRecord));
                    if (!ApplyStaticScalar(4, action, target->stateValues,
                            action->payload.modifier.fieldId,
                            &scratchRecord)) return FALSE;
                    scratchRecord.targetNodeId = target->nodeId;
                    scratchRecord.staticPriority = source->priority;
                    scratchRecord.ruleStableId = source->stableId;
                    scratchRecord.actionStableId = action->stableId;
                    RecordStaticContribution(compositionOut, &scratchRecord);
                }
                continue;
            }
            memset(&scratchRecord, 0, sizeof(scratchRecord));
            if (action->kind
                    == OWBD_STATIC_ACTION_APPLY_CONTROLLER_MODIFIER) {
                if (!ApplyStaticScalar(5, action,
                        compositionOut->controllerValues,
                        action->payload.modifier.fieldId - 1,
                        &scratchRecord)) return FALSE;
                scratchRecord.staticPriority = source->priority;
                scratchRecord.ruleStableId = source->stableId;
                scratchRecord.actionStableId = action->stableId;
                RecordStaticContribution(compositionOut, &scratchRecord);
            } else if (action->kind == OWBD_STATIC_ACTION_BIND_SPAWN_POLICY) {
                compositionOut->spawnPolicyId =
                    action->payload.bindPolicy.policyId;
                if (!CopyPolicyValues(&header->spawnPolicies,
                        compositionOut->spawnPolicyId, 6, 6,
                        &compositionOut->spawnConfiguration.spawnState))
                    return FALSE;
            } else if (action->kind
                    == OWBD_STATIC_ACTION_APPLY_SPAWN_POLICY_PATCH) {
                if (!ApplyStaticScalar(7, action,
                        &compositionOut->spawnConfiguration.spawnState,
                        action->payload.modifier.fieldId - 1, NULL))
                    return FALSE;
            } else if (action->kind
                    == OWBD_STATIC_ACTION_BIND_POPULATION_POLICY) {
                compositionOut->populationPolicyId =
                    action->payload.bindPolicy.policyId;
                if (!CopyPolicyValues(&header->populationPolicies,
                        compositionOut->populationPolicyId, 8, 2,
                        &compositionOut->spawnConfiguration.populationLimit))
                    return FALSE;
            } else if (action->kind
                    == OWBD_STATIC_ACTION_APPLY_POPULATION_POLICY_PATCH) {
                if (!ApplyStaticScalar(9, action,
                        &compositionOut->spawnConfiguration.populationLimit,
                        action->payload.modifier.fieldId - 1, NULL))
                    return FALSE;
            } else if (action->kind == OWBD_STATIC_ACTION_BIND_HOOK_SET) {
                hookSetId = action->payload.bindPolicy.policyId;
                if (!CopyPolicyValues(&header->hookSets,
                        hookSetId, 4, 4,
                        &compositionOut->spawnConfiguration.helpCallInvocation))
                    return FALSE;
            }
        }
    }
    compositionOut->boundNodeCount = 0;
    compositionOut->semanticRoleMask = 0;
    for (i = 0; i < compositionOut->nodeCount; i++) {
        const OverworldWildRuntimeResolvedNode *node =
            &compositionOut->resolvedNodes[i];
        if (!node->bound) continue;
        compositionOut->boundNodeCount++;
        compositionOut->semanticRoleMask |=
            (u8)(1u << (node->semanticRole - 1));
    }
    if (!base->bound || base->profileId == 0) return FALSE;
    memcpy(compositionOut->stateValues, base->stateValues,
        sizeof(compositionOut->stateValues));
    if (input != NULL
        && !CanonicalApplicabilityMatches(compositionOut, input)) return FALSE;
    compositionOut->staticContextIdentity = RuntimeCatalogMix(
        compositionOut->catalogIdentity,
        ((u32)controller->stableId << 16) | base->nodeId);
    compositionOut->staticContextIdentity = RuntimeCatalogMix(
        compositionOut->staticContextIdentity,
        ((u32)base->profileId << 16) | base->semanticRole);
    compositionOut->staticContextIdentity = RuntimeCatalogMix(
        compositionOut->staticContextIdentity, staticContext->groupFlags);
    compositionOut->staticContextIdentity = RuntimeCatalogMix(
        compositionOut->staticContextIdentity,
        ((u32)staticContext->species << 16)
            | ((u32)staticContext->level << 8) | staticContext->terrain);
    compositionOut->staticContextIdentity = RuntimeCatalogMix(
        compositionOut->staticContextIdentity,
        ((u32)staticContext->shiny << 8) | staticContext->behaviorClass);
    compositionOut->staticContextIdentity = RuntimeCatalogHashBytes(
        compositionOut->staticContextIdentity, compositionOut->resolvedNodes,
        sizeof(compositionOut->resolvedNodes));
    compositionOut->staticContextIdentity = RuntimeCatalogHashBytes(
        compositionOut->staticContextIdentity,
        compositionOut->controllerValues,
        sizeof(compositionOut->controllerValues));
    if (compositionOut->staticContextIdentity == 0)
        compositionOut->staticContextIdentity = 1;
    compositionOut->staticSetHash = StaticCompositionSetHash(compositionOut);
    return TRUE;
}

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
BOOL OverworldWildRuntime_CopyInstalledStaticComposition(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    OverworldWildRuntimeStaticComposition *compositionOut)
{
    return CopyInstalledStaticCompositionInternal(
        staticContext, input, compositionOut);
}
#endif

BOOL OverworldWildRuntime_CopyInstalledStaticCache(
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *input,
    u32 staticContextGeneration,
    OverworldWildRuntimeStaticCache *cacheOut)
{
    OverworldWildRuntimeStaticComposition composition;

    if (cacheOut == NULL) return FALSE;
    memset(cacheOut, 0, sizeof(*cacheOut));
    if (!CopyInstalledStaticCompositionInternal(
            staticContext, input, &composition)) return FALSE;
    cacheOut->catalogIdentity = composition.catalogIdentity;
    cacheOut->staticContextIdentity = composition.staticContextIdentity;
    cacheOut->staticSetHash = composition.staticSetHash;
    cacheOut->staticContextGeneration = staticContextGeneration;
    memcpy(&cacheOut->immutableContextMask,
        (void *)&composition.immutableContextMask,
        sizeof(*cacheOut) - offsetof(OverworldWildRuntimeStaticCache,
            immutableContextMask));
    return TRUE;
}

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
BOOL OverworldWildRuntime_ApplicabilityMatchesStaticCache(
    const OverworldWildRuntimeApplicabilityInput *input,
    const OverworldWildRuntimeStaticCache *cache)
{
    u8 nodeIndex;
    u8 inputIndex = 0;
    if (input == NULL || cache == NULL
        || input->immutableContextMask != cache->immutableContextMask
        || input->controllerId != cache->controllerId
        || input->effectiveProfileId != cache->baseProfileId
        || input->effectiveSemanticRole != cache->baseSemanticRole
        || input->boundNodeCount != cache->boundNodeCount
        || input->semanticRoleMask != cache->semanticRoleMask)
        return FALSE;
    for (nodeIndex = 0; nodeIndex < cache->nodeCount; nodeIndex++) {
        const OverworldWildRuntimeResolvedNode *node =
            &cache->resolvedNodes[nodeIndex];
        if (!node->bound) continue;
        if (inputIndex >= input->boundNodeCount
            || input->boundNodeIds[inputIndex++] != node->nodeId)
            return FALSE;
    }
    return inputIndex == input->boundNodeCount;
}
#endif

OverworldWildRuntimeStatus OverworldWildRuntime_ValidateStaticCache(
    const OverworldWildRuntimeStaticCache *cache,
    u32 staticContextGeneration)
{
    u32 identity;
    u32 hash;
    u8 i, boundCount = 0, roleMask = 0;
    BOOL sawBase = FALSE;
    if (cache == NULL
        || !OverworldWildRuntime_CopyInstalledCatalogIdentity(&identity)
        || identity != cache->catalogIdentity)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    hash = RuntimeCatalogMix(0x4F575339u, cache->catalogIdentity);
    hash = RuntimeCatalogMix(hash, cache->staticContextIdentity);
    hash = RuntimeCatalogHashBytes(hash, &cache->immutableContextMask,
        sizeof(*cache) - offsetof(OverworldWildRuntimeStaticCache,
            immutableContextMask));
    if (!cache->valid || cache->reserved > 1
        || cache->staticContextIdentity == 0
        || cache->immutableContextMask != cache->staticContext.groupFlags
        || cache->staticContext.reserved != 0
        || cache->staticContext.shiny > 1
        || cache->nodeCount == 0
        || cache->nodeCount > OW_WILD_RUNTIME_MAX_RESOLVED_NODES
        || cache->boundNodeCount == 0
        || cache->boundNodeCount > cache->nodeCount
        || (cache->semanticRoleMask & ~0x7Fu)
        || cache->controllerId == 0 || cache->baseNodeId == 0
        || cache->baseProfileId == 0 || cache->baseSemanticRole == 0
        || cache->baseSemanticRole > 7
        || cache->spawnPolicyId == 0 || cache->populationPolicyId == 0
        || cache->spawnConfiguration.spawnState > 3
        || cache->spawnConfiguration.destination > 16
        || cache->spawnConfiguration.minimumDistance < 1
        || cache->spawnConfiguration.minimumDistance > 8
        || cache->spawnConfiguration.maximumDistance
            < cache->spawnConfiguration.minimumDistance
        || cache->spawnConfiguration.maximumDistance > 8
        || cache->spawnConfiguration.spawnHopTime > 64
        || cache->spawnConfiguration.spawnFlags != 0
        || cache->spawnConfiguration.populationLimit > 10
        || cache->spawnConfiguration.populationFlags != 0
        || cache->spawnConfiguration.helpCallInvocation > 1
        || cache->spawnConfiguration.pickupThrowEntry > 1
        || cache->spawnConfiguration.pickupThrowActiveLoop
            != cache->spawnConfiguration.pickupThrowEntry
        || (cache->spawnConfiguration.helpCallInvocation
            && cache->spawnConfiguration.pickupThrowEntry)
        || cache->spawnConfiguration.hookFlags != 0
        || cache->staticContextGeneration != staticContextGeneration
        || cache->staticModifierCount
            > OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS
        || cache->staticSetHash != hash)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    for (i = 0; i < sizeof(cache->padding); i++)
        if (cache->padding[i] != 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    for (i = 0; i < cache->nodeCount; i++) {
        const OverworldWildRuntimeResolvedNode *node =
            &cache->resolvedNodes[i];
        u8 valueIndex;
        if (node->nodeId == 0 || node->reserved != 0
            || node->semanticRole == 0 || node->semanticRole > 7
            || (i != 0
                && cache->resolvedNodes[i - 1].nodeId >= node->nodeId))
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        if (!node->bound) {
            if (node->profileId != 0)
                return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
            for (valueIndex = 0; valueIndex < sizeof(node->stateValues);
                    valueIndex++)
                if (node->stateValues[valueIndex] != 0)
                    return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
            continue;
        }
        if (node->profileId == 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        boundCount++;
        roleMask |= (u8)(1u << (node->semanticRole - 1));
        if (node->nodeId == cache->baseNodeId) {
            if (sawBase || node->profileId != cache->baseProfileId
                || node->semanticRole != cache->baseSemanticRole)
                return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
            for (valueIndex = 0; valueIndex < sizeof(node->stateValues);
                    valueIndex++)
                if (node->stateValues[valueIndex]
                        != cache->stateValues[valueIndex])
                    return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
            sawBase = TRUE;
        }
    }
    if (!sawBase || boundCount != cache->boundNodeCount
        || roleMask != cache->semanticRoleMask)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus
OverworldWildRuntime_CopyValidatedSpawnConfiguration(
    const OverworldWildRuntimeStaticCache *staticCache,
    u32 expectedStaticContextGeneration,
    OverworldWildRuntimeSpawnConfiguration *configurationOut)
{
    OverworldWildRuntimeStatus status;
    if (configurationOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(configurationOut, 0, sizeof(*configurationOut));
    status = OverworldWildRuntime_ValidateStaticCache(
        staticCache, expectedStaticContextGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    *configurationOut = staticCache->spawnConfiguration;
    return OW_WILD_RUNTIME_STATUS_OK;
}

#ifndef OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
BOOL OverworldWildRuntime_MatchesPendingTimerExpiry(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    const OverworldWildRuntimeTimer *timer;
    u8 index;
    if (runtime == NULL || expiry == NULL
        || expiry->slotIndex >= OW_WILD_MAX_SPAWNS)
        return FALSE;
    slot = &runtime->slots[expiry->slotIndex];
    timer = slot->timerBank.timers;
    for (index = 0; index < slot->activeLayerCount; index++, timer++) {
        if (timer->entryGeneration == expiry->entryGeneration
            && timer->timerGeneration == expiry->timerGeneration
            && (timer->flags & (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
                == (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
            return TRUE;
    }
    return FALSE;
}
#endif

OverworldWildRuntimeStatus OverworldWildRuntime_ResolveRetainedStaticCache(
    const OverworldWildRuntimeStaticCache *retainedCache,
    u32 staticContextGeneration,
    OverworldWildRuntimeStaticCache *resolvedOut)
{
    if (retainedCache == NULL || resolvedOut == NULL
        || retainedCache == resolvedOut
        || OverworldWildRuntime_ValidateStaticCache(
            retainedCache, staticContextGeneration)
            != OW_WILD_RUNTIME_STATUS_OK)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    *resolvedOut = *retainedCache;
    return OW_WILD_RUNTIME_STATUS_OK;
}

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
BOOL OverworldWildRuntime_CopyInstalledResolvedNode(
    const OverworldWildRuntimeStaticComposition *composition,
    const OverworldWildRuntimeDefinition *definition,
    OverworldWildRuntimeResolvedNode *nodeOut)
{
    const OverworldWildRuntimeResolvedNode *match = NULL;
    u8 i;

    memset(nodeOut, 0, sizeof(*nodeOut));
    if (composition == NULL || definition == NULL
        || definition->kind != OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE)
        return FALSE;
    for (i = 0; i < composition->nodeCount; i++) {
        const OverworldWildRuntimeResolvedNode *node =
            &composition->resolvedNodes[i];
        if (!node->bound) continue;
        if ((definition->selectorKind == OW_WILD_RUNTIME_SELECTOR_EXACT
                && node->nodeId == definition->nodeId)
            || (definition->selectorKind == OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
                && node->semanticRole == definition->semanticRole)) {
            if (match != NULL) return FALSE;
            match = node;
        }
    }
    if (match == NULL) return FALSE;
    *nodeOut = *match;
    return TRUE;
}
#endif

BOOL OverworldWildRuntime_CopyResolvedCachedNode(
    const OverworldWildRuntimeStaticCache *cache,
    const OverworldWildRuntimeDefinition *definition,
    OverworldWildRuntimeResolvedNode *nodeOut)
{
    const OverworldWildRuntimeResolvedNode *match = NULL;
    u8 i;

    memset(nodeOut, 0, sizeof(*nodeOut));
    if (cache == NULL || definition == NULL
        || definition->kind != OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE)
        return FALSE;
    for (i = 0; i < cache->nodeCount; i++) {
        const OverworldWildRuntimeResolvedNode *node =
            &cache->resolvedNodes[i];
        if (!node->bound) continue;
        if ((definition->selectorKind == OW_WILD_RUNTIME_SELECTOR_EXACT
                && node->nodeId == definition->nodeId)
            || (definition->selectorKind
                    == OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
                && node->semanticRole == definition->semanticRole)) {
            if (match != NULL) return FALSE;
            match = node;
        }
    }
    if (match == NULL) return FALSE;
    *nodeOut = *match;
    return TRUE;
}

BOOL OverworldWildRuntime_CopyInstalledModifierOperations(
    u16 definitionId,
    OverworldWildRuntimeModifierOperation *operationsOut,
    u8 capacity,
    u8 *operationCountOut)
{
    OverworldWildRuntimeDefinition definition;
    (void)operationsOut;
    (void)capacity;
    if (operationCountOut == NULL) return FALSE;
    *operationCountOut = 0;
    if (!OverworldWildRuntime_CopyInstalledDefinition(definitionId, &definition))
        return FALSE;
    /* The frozen v40 catalog has no definition-to-modifier payload edge. */
    return definition.kind != OW_WILD_RUNTIME_DEFINITION_MODIFIER;
}

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
u8 OverworldWildRuntime_CountInstalledTiredTranslations(
    u8 tiredOriginKind,
    u16 destinationControllerId,
    BOOL authoredTiredBound,
    u16 *candidateDefinitionIdOut)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildTiredTranslationRecord *translations;
    const u8 *transitions;
    u16 index;
    u8 count = 0;

    if (candidateDefinitionIdOut == NULL) return 0;
    *candidateDefinitionIdOut = 0;
    if (sOverworldWildValidatedV40 == NULL) return 0;
    header = (const void *)sOverworldWildValidatedV40;
    if (tiredOriginKind == 0) {
        transitions = (const void *)(sOverworldWildValidatedV40
            + header->transitions.offset);
        for (index = 0; index < header->transitions.count; index++) {
            const u8 *transition = transitions
                + (u32)index * header->transitions.entrySize;
            /* The frozen v40 trigger ABI assigns stamina exhaustion to 2. */
            if (transition[18] != 2)
                continue;
            if (count++ == 0)
                *candidateDefinitionIdOut = (u16)(transition[2]
                    | ((u16)transition[3] << 8));
        }
        return count;
    }
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
#endif
