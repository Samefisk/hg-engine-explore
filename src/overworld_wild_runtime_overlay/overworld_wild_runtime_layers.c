#include "overworld_wild_runtime_layers_internal.h"

#define OW_WILD_RUNTIME_ROLE_TIRED 3
#define OW_WILD_RUNTIME_ROLE_MASK(role) (1u << ((role) - 1))

typedef struct OverworldWildRuntimeDeltaScratch {
    OverworldWildRuntimeLayer finalLayers[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    OverworldWildRuntimeDefinition definitions[2];
    u8 operationOrder[OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS];
    u8 removalMask;
    u8 additionCount;
    u8 finalCount;
    u8 reserved;
} OverworldWildRuntimeDeltaScratch;

typedef struct OverworldWildRuntimeLayerService {
    OverworldWildBehaviorStackRuntime *boundRuntime;
    u32 privateRuntimeIdentity;
    OverworldWildRuntimeDeltaOperation oneOperation;
    OverworldWildRuntimeApplicabilityInput oneApplicability;
    OverworldWildRuntimeDeltaScratch scratch;
    u32 wrapLayerGenerations[OW_WILD_MAX_SPAWNS];
    u8 wrapLayerCounts[OW_WILD_MAX_SPAWNS];
    u8 wrapReserved[2];
} OverworldWildRuntimeLayerService;

static OverworldWildRuntimeLayerService sOverworldWildRuntimeLayerService;

#ifdef OW_WILD_RUNTIME_HOST_TEST
static BOOL sOverworldWildRuntimeForceZeroMix;
#endif

typedef char OverworldWildRuntimeFixedScratchMustFit140[
    sizeof(sOverworldWildRuntimeLayerService) <= 0x140 ? 1 : -1];

static BOOL BytesAreZero(const void *data, u32 size)
{
    const u8 *bytes = data;
    while (size-- != 0) {
        if (*bytes++ != 0) return FALSE;
    }
    return TRUE;
}

static u32 Mix(u32 value, u32 input)
{
#ifdef OW_WILD_RUNTIME_HOST_TEST
    if (sOverworldWildRuntimeForceZeroMix) return 0;
#endif
    value ^= input + 0x9E3779B9u + (value << 6) + (value >> 2);
    value ^= value >> 16;
    value *= 0x7FEB352Du;
    return value ^ (value >> 15);
}

static void RotatePrivateIdentity(
    OverworldWildBehaviorStackRuntime *runtime)
{
    (void)runtime;
    sOverworldWildRuntimeLayerService.privateRuntimeIdentity =
        OverworldWildRuntime_AdvanceNonzeroGeneration(
            sOverworldWildRuntimeLayerService.privateRuntimeIdentity);
}

static u32 HandleTag(
    const OverworldWildBehaviorStackRuntime *runtime,
    u32 epoch,
    u8 slot,
    u32 slotGeneration,
    u16 owner,
    u16 key,
    u32 entryGeneration)
{
    unsigned long address = (unsigned long)runtime;
    u32 tag = Mix(0x4F574838u,
        sOverworldWildRuntimeLayerService.privateRuntimeIdentity);
    tag = Mix(tag, (u32)address);
    if (sizeof(address) > 4) tag = Mix(tag, (u32)(address >> 16 >> 16));
    tag = Mix(tag, epoch);
    tag = Mix(tag, slotGeneration);
    tag = Mix(tag, ((u32)owner << 16) | key);
    tag = Mix(tag, slot);
    tag = Mix(tag, entryGeneration);
    if (tag != 0) return tag;
    tag = sOverworldWildRuntimeLayerService.privateRuntimeIdentity;
    return (tag << 1) | (tag >> 31);
}

static void ReadLayer(
    const OverworldWildRuntimeSlotSidecar *slot,
    u8 index,
    OverworldWildRuntimeLayer *out)
{
    u8 flags = slot->layerBank.generatedFlags[index];
    out->entryGeneration = slot->layerBank.entryGenerations[index];
    out->definitionId = slot->layerBank.definitionIds[index];
    out->ownerId = slot->layerBank.ownerIds[index];
    out->instanceKey = slot->layerBank.instanceKeys[index];
    out->requiredOwnerId = slot->layerBank.requiredOwnerIds[index];
    out->hasTiredOriginKind =
        (flags & OW_WILD_RUNTIME_GENERATED_FLAG_HAS_TIRED_ORIGIN) != 0;
    out->tiredOriginKind = slot->layerBank.tiredOriginKinds[index];
    out->hasRequiredOwnerId =
        (flags & OW_WILD_RUNTIME_GENERATED_FLAG_HAS_REQUIRED_OWNER) != 0;
    out->reserved = 0;
}

static void WriteLayers(
    OverworldWildRuntimeSlotSidecar *slot,
    const OverworldWildRuntimeLayer *layers,
    u8 count)
{
    u8 i;
    memset(&slot->layerBank, 0, sizeof(slot->layerBank));
    slot->activeLayerCount = count;
    for (i = 0; i < count; i++) {
        u8 flags = 0;
        slot->layerBank.entryGenerations[i] = layers[i].entryGeneration;
        slot->layerBank.definitionIds[i] = layers[i].definitionId;
        slot->layerBank.ownerIds[i] = layers[i].ownerId;
        slot->layerBank.instanceKeys[i] = layers[i].instanceKey;
        slot->layerBank.requiredOwnerIds[i] = layers[i].requiredOwnerId;
        slot->layerBank.tiredOriginKinds[i] = layers[i].tiredOriginKind;
        if (layers[i].hasTiredOriginKind)
            flags |= OW_WILD_RUNTIME_GENERATED_FLAG_HAS_TIRED_ORIGIN;
        if (layers[i].hasRequiredOwnerId)
            flags |= OW_WILD_RUNTIME_GENERATED_FLAG_HAS_REQUIRED_OWNER;
        slot->layerBank.generatedFlags[i] = flags;
    }
}

static int CompareKeys(
    const OverworldWildRuntimeLayer *left,
    const OverworldWildRuntimeLayer *right)
{
    if (left->ownerId != right->ownerId)
        return left->ownerId < right->ownerId ? -1 : 1;
    if (left->instanceKey != right->instanceKey)
        return left->instanceKey < right->instanceKey ? -1 : 1;
    return 0;
}

static void SortLayers(OverworldWildRuntimeLayer *layers, u8 count)
{
    u8 i;
    for (i = 1; i < count; i++) {
        OverworldWildRuntimeLayer value = layers[i];
        u8 cursor = i;
        while (cursor != 0 && CompareKeys(&value, &layers[cursor - 1]) < 0) {
            layers[cursor] = layers[cursor - 1];
            cursor--;
        }
        layers[cursor] = value;
    }
}

static int FindLayer(
    const OverworldWildRuntimeSlotSidecar *slot,
    u16 owner,
    u16 key)
{
    u8 i;
    for (i = 0; i < slot->activeLayerCount; i++) {
        if (slot->layerBank.ownerIds[i] == owner
            && slot->layerBank.instanceKeys[i] == key) return i;
    }
    return -1;
}

static OverworldWildRuntimeStatus CopyDefinition(
    u16 id,
    OverworldWildRuntimeDefinition *out)
{
    BOOL hasOrigin;
    BOOL hasOwner;
    u16 expectedOwner = 0;
    if (!OverworldWildRuntime_CopyInstalledDefinition(id, out)
        || out->stableId != id
        || !(out->flags & OW_WILD_RUNTIME_DEFINITION_FLAG_RUNTIME_ELIGIBLE)
        || (out->kind != 1 && out->kind != 2)) {
        return OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION;
    }
    if (out->kind == 1
        && ((out->selectorKind == 1 && out->nodeId == 0)
            || (out->selectorKind == 2
                && (out->semanticRole == 0 || out->semanticRole > 7))
            || (out->selectorKind != 1 && out->selectorKind != 2)))
        return OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION;
    hasOrigin = (out->flags
        & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN) != 0;
    hasOwner = (out->flags
        & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER) != 0;
    if (hasOrigin) {
        if (out->tiredOriginKind == 1) expectedOwner = 0x8107;
        else if (out->tiredOriginKind == 2) expectedOwner = 0x8106;
        else if (out->tiredOriginKind == 3) expectedOwner = 0x8108;
        else return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
        if (!hasOwner || out->requiredOwnerId != expectedOwner)
            return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
    } else if (out->tiredOriginKind != 0) {
        return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
    }
    if (hasOwner) {
        if (out->requiredOwnerId == 0 || out->kind != 1
            || (out->flags & (OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS
                | OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)))
            return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
        if (!hasOrigin && (out->requiredOwnerId != 0x8105
                || out->selectorKind != 2 || out->semanticRole != 3))
            return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
    } else if (out->requiredOwnerId != 0) {
        return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus ValidateBank(
    const OverworldWildRuntimeSlotSidecar *slot)
{
    OverworldWildRuntimeLayer previous;
    OverworldWildRuntimeLayer layer;
    u8 i, j;
    if (slot->activeLayerCount > OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT
        || slot->slotGeneration == 0 || slot->nextEntryGeneration == 0
        || slot->layerGeneration == 0 || slot->effectiveGeneration == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(&previous, 0, sizeof(previous));
    for (i = 0; i < slot->activeLayerCount; i++) {
        ReadLayer(slot, i, &layer);
        if (layer.entryGeneration == 0 || layer.ownerId == 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        if (layer.entryGeneration >= slot->nextEntryGeneration)
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        for (j = 0; j < i; j++) {
            if (slot->layerBank.entryGenerations[j] == layer.entryGeneration)
                return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        }
        if (i != 0 && CompareKeys(&previous, &layer) >= 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        previous = layer;
    }
    for (; i < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT; i++) {
        if (slot->layerBank.entryGenerations[i] || slot->layerBank.definitionIds[i]
            || slot->layerBank.ownerIds[i] || slot->layerBank.instanceKeys[i]
            || slot->layerBank.requiredOwnerIds[i]
            || slot->layerBank.tiredOriginKinds[i]
            || slot->layerBank.generatedFlags[i])
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus ValidateApplicabilityShape(
    const OverworldWildRuntimeApplicabilityInput *input)
{
    u8 i, j;
    if (input == NULL || input->controllerId == 0
        || input->boundNodeCount > OW_WILD_RUNTIME_MAX_BOUND_NODES
        || input->effectiveProfileId == 0
        || input->effectiveSemanticRole == 0
        || input->effectiveSemanticRole > 7
        || input->reserved != 0 || (input->semanticRoleMask & ~0x7Fu))
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    for (i = 0; i < input->boundNodeCount; i++) {
        if (input->boundNodeIds[i] == 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        for (j = 0; j < i; j++)
            if (input->boundNodeIds[j] == input->boundNodeIds[i])
                return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR;
    }
    for (; i < OW_WILD_RUNTIME_MAX_BOUND_NODES; i++)
        if (input->boundNodeIds[i] != 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus CheckApplicable(
    const OverworldWildRuntimeDefinition *definition,
    const OverworldWildRuntimeApplicabilityInput *input)
{
    u8 i;
    if (definition->immutableContextMask != 0xFFFFFFFFu
        && (input->immutableContextMask & definition->immutableContextMask)
            != definition->immutableContextMask)
        return OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE;
    if (definition->controllerId != 0
        && definition->controllerId != input->controllerId)
        return OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE;
    if (definition->kind != 1) return OW_WILD_RUNTIME_STATUS_OK;
    if (definition->selectorKind == 2)
        return input->semanticRoleMask
                & OW_WILD_RUNTIME_ROLE_MASK(definition->semanticRole)
            ? OW_WILD_RUNTIME_STATUS_OK : OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE;
    if (definition->selectorKind != 1)
        return OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION;
    for (i = 0; i < input->boundNodeCount; i++)
        if (input->boundNodeIds[i] == definition->nodeId)
            return OW_WILD_RUNTIME_STATUS_OK;
    return OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE;
}

static OverworldWildRuntimeStatus CheckGeneratedTranslation(
    const OverworldWildRuntimeDefinition *definition,
    const OverworldWildRuntimeApplicabilityInput *input)
{
    u16 candidateDefinitionId = 0;
    u8 count;
    if (!(definition->flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN))
        return OW_WILD_RUNTIME_STATUS_OK;
    count = OverworldWildRuntime_CountInstalledTiredTranslations(
        definition->tiredOriginKind,
        input->controllerId,
        (input->semanticRoleMask
            & OW_WILD_RUNTIME_ROLE_MASK(OW_WILD_RUNTIME_ROLE_TIRED)) != 0,
        &candidateDefinitionId);
    return count == 1 && candidateDefinitionId == definition->stableId
        ? OW_WILD_RUNTIME_STATUS_OK
        : OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
}

static OverworldWildRuntimeStatus ValidateHandle(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 requestedSlot,
    const OverworldWildRuntimeLayerHandle *handle,
    int *indexOut)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    int index;
    if (handle == NULL || handle->runtimeEpoch == 0
        || handle->slotGeneration == 0 || handle->entryGeneration == 0
        || handle->ownerId == 0 || handle->slotIndex >= OW_WILD_MAX_SPAWNS
        || handle->validityTag == 0 || handle->reserved[0]
        || handle->reserved[1] || handle->reserved[2]
        || handle->validityTag != HandleTag(runtime, handle->runtimeEpoch,
            handle->slotIndex, handle->slotGeneration, handle->ownerId,
            handle->instanceKey, handle->entryGeneration))
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    if (handle->slotIndex != requestedSlot)
        return OW_WILD_RUNTIME_STATUS_WRONG_SLOT;
    slot = &runtime->slots[requestedSlot];
    if (handle->runtimeEpoch != runtime->handleEpoch
        || handle->slotGeneration != slot->slotGeneration) {
        *indexOut = -1;
        return OW_WILD_RUNTIME_STATUS_OK;
    }
    index = FindLayer(slot, handle->ownerId, handle->instanceKey);
    if (index < 0 || slot->layerBank.entryGenerations[index]
            != handle->entryGeneration) index = -1;
    *indexOut = index;
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeLayerHandle MakeHandle(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    const OverworldWildRuntimeLayer *layer)
{
    OverworldWildRuntimeLayerHandle handle;
    memset(&handle, 0, sizeof(handle));
    handle.runtimeEpoch = runtime->handleEpoch;
    handle.slotGeneration = runtime->slots[slotIndex].slotGeneration;
    handle.entryGeneration = layer->entryGeneration;
    handle.ownerId = layer->ownerId;
    handle.instanceKey = layer->instanceKey;
    handle.slotIndex = slotIndex;
    handle.validityTag = HandleTag(runtime, handle.runtimeEpoch, slotIndex,
        handle.slotGeneration, handle.ownerId, handle.instanceKey,
        handle.entryGeneration);
    return handle;
}

static OverworldWildRuntimeStatus ValidateOperation(
    const OverworldWildRuntimeDeltaOperation *operation)
{
    if (operation->operationId == 0 || operation->reserved != 0
        || operation->kind < OW_WILD_RUNTIME_DELTA_APPLY
        || operation->kind > OW_WILD_RUNTIME_DELTA_CLEAR)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    if (operation->kind <= OW_WILD_RUNTIME_DELTA_REPLACE) {
        if (operation->payload.apply.definitionId == 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION;
        if (operation->payload.apply.ownerId == 0
            || !BytesAreZero(operation->payload.apply.reserved, 18))
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    } else if (operation->kind <= OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT) {
        if (BytesAreZero(&operation->payload.handle,
                sizeof(operation->payload.handle)))
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    } else if (operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT) {
        if (operation->payload.owner.ownerId == 0
            || !BytesAreZero(operation->payload.owner.reserved, 22))
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    } else if (operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_POLICY) {
        if (operation->payload.policy.mapLifetime < 1
            || operation->payload.policy.mapLifetime > 3
            || !BytesAreZero(operation->payload.policy.reserved, 23))
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    } else if (!BytesAreZero(operation->payload.raw, 24)) {
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static BOOL OperationAddressesLayer(
    const OverworldWildRuntimeDeltaOperation *operation,
    const OverworldWildRuntimeLayer *layer)
{
    OverworldWildRuntimeDefinition definition;
    if (operation->kind <= OW_WILD_RUNTIME_DELTA_REPLACE)
        return operation->payload.apply.ownerId == layer->ownerId
            && operation->payload.apply.instanceKey == layer->instanceKey;
    if (operation->kind <= OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT)
        return operation->payload.handle.ownerId == layer->ownerId
            && operation->payload.handle.instanceKey == layer->instanceKey;
    if (operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT)
        return operation->payload.owner.ownerId == layer->ownerId;
    if (operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_POLICY) {
        if (CopyDefinition(layer->definitionId, &definition)
                != OW_WILD_RUNTIME_STATUS_OK) return FALSE;
        return operation->payload.policy.mapLifetime == definition.mapLifetime;
    }
    return operation->kind == OW_WILD_RUNTIME_DELTA_CLEAR;
}

static OverworldWildRuntimeStatus RejectAmbiguity(
    const OverworldWildRuntimeDeltaOperation *operations,
    const u8 *order,
    u8 count,
    const OverworldWildRuntimeSlotSidecar *slot)
{
    u8 i, j, layerIndex;
    for (i = 0; i < count; i++) {
        const OverworldWildRuntimeDeltaOperation *left = &operations[order[i]];
        if (i && left->operationId == operations[order[i - 1]].operationId)
            return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
        if (count > 1 && left->kind == OW_WILD_RUNTIME_DELTA_CLEAR)
            return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
        for (j = i + 1; j < count; j++) {
            const OverworldWildRuntimeDeltaOperation *right = &operations[order[j]];
            OverworldWildRuntimeLayer synthetic;
            if (left->kind == OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT
                && right->kind
                    == OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT
                && left->payload.owner.ownerId
                    == right->payload.owner.ownerId)
                return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            if (left->kind == OW_WILD_RUNTIME_DELTA_REMOVE_POLICY
                && right->kind == OW_WILD_RUNTIME_DELTA_REMOVE_POLICY
                && left->payload.policy.mapLifetime
                    == right->payload.policy.mapLifetime)
                return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            memset(&synthetic, 0, sizeof(synthetic));
            if (left->kind <= OW_WILD_RUNTIME_DELTA_REPLACE) {
                synthetic.ownerId = left->payload.apply.ownerId;
                synthetic.instanceKey = left->payload.apply.instanceKey;
                synthetic.definitionId = left->payload.apply.definitionId;
                if (right->kind != OW_WILD_RUNTIME_DELTA_REMOVE_POLICY
                    && OperationAddressesLayer(right, &synthetic))
                    return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            } else if (left->kind <= OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT) {
                synthetic.ownerId = left->payload.handle.ownerId;
                synthetic.instanceKey = left->payload.handle.instanceKey;
                if (right->kind != OW_WILD_RUNTIME_DELTA_REMOVE_POLICY
                    && OperationAddressesLayer(right, &synthetic))
                    return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            }
            memset(&synthetic, 0, sizeof(synthetic));
            if (right->kind <= OW_WILD_RUNTIME_DELTA_REPLACE) {
                synthetic.ownerId = right->payload.apply.ownerId;
                synthetic.instanceKey = right->payload.apply.instanceKey;
                synthetic.definitionId = right->payload.apply.definitionId;
                if (left->kind != OW_WILD_RUNTIME_DELTA_REMOVE_POLICY
                    && OperationAddressesLayer(left, &synthetic))
                    return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            } else if (right->kind <= OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT) {
                synthetic.ownerId = right->payload.handle.ownerId;
                synthetic.instanceKey = right->payload.handle.instanceKey;
                if (left->kind != OW_WILD_RUNTIME_DELTA_REMOVE_POLICY
                    && OperationAddressesLayer(left, &synthetic))
                    return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            }
            for (layerIndex = 0; layerIndex < slot->activeLayerCount; layerIndex++) {
                ReadLayer(slot, layerIndex, &synthetic);
                if (OperationAddressesLayer(left, &synthetic)
                    && OperationAddressesLayer(right, &synthetic))
                    return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            }
        }
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static void InitResult(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    OverworldWildRuntimeStackDeltaResult *result)
{
    memset(result, 0, sizeof(*result));
    if (runtime == NULL) return;
    result->runtimeEpochBefore = result->runtimeEpochAfter = runtime->handleEpoch;
    if (slotIndex < OW_WILD_MAX_SPAWNS) {
        const OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        result->slotGenerationBefore = result->slotGenerationAfter = slot->slotGeneration;
        result->layerGenerationBefore = result->layerGenerationAfter = slot->layerGeneration;
        result->effectiveGenerationBefore = result->effectiveGenerationAfter = slot->effectiveGeneration;
    }
}

static OverworldWildRuntimeStatus Fail(
    OverworldWildRuntimeStackDeltaResult *result,
    OverworldWildRuntimeStatus status)
{
    memset(result->operationResults, 0, sizeof(result->operationResults));
    result->operationResultCount = 0;
    result->status = status;
    result->ok = result->mutated = FALSE;
    return status;
}

static OverworldWildRuntimeStatus ValidateMultiplicity(
    const OverworldWildRuntimeLayer *layers,
    u8 count,
    OverworldWildRuntimeDefinition *definition)
{
    u8 i, j;
    for (i = 0; i < count; i++) {
        OverworldWildRuntimeStatus status =
            CopyDefinition(layers[i].definitionId, definition);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        if (layers[i].requiredOwnerId != definition->requiredOwnerId
            || layers[i].tiredOriginKind != definition->tiredOriginKind
            || layers[i].hasRequiredOwnerId
                != ((definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER) != 0)
            || layers[i].hasTiredOriginKind
                != ((definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN) != 0))
            return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
        if ((definition->flags
                & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
            && layers[i].ownerId != definition->requiredOwnerId)
            return OW_WILD_RUNTIME_STATUS_OWNER_NOT_AUTHORIZED;
        if (!(definition->flags
                & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
            && layers[i].instanceKey != 0)
            return definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER
                ? OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER
                : OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED;
        for (j = i + 1; j < count; j++) {
            if (layers[i].ownerId == layers[j].ownerId
                && layers[i].instanceKey == layers[j].instanceKey)
                return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
            if (layers[i].definitionId == layers[j].definitionId) {
                if (!(definition->flags
                        & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS)
                    && layers[i].ownerId != layers[j].ownerId)
                    return OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED;
                if (!(definition->flags
                        & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
                    && layers[i].ownerId == layers[j].ownerId)
                    return OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED;
            }
        }
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus CheckMultiplicityPair(
    const OverworldWildRuntimeLayer *left,
    const OverworldWildRuntimeLayer *right,
    OverworldWildRuntimeDefinition *definition)
{
    OverworldWildRuntimeStatus status;
    if (left->ownerId == right->ownerId
        && left->instanceKey == right->instanceKey)
        return OW_WILD_RUNTIME_STATUS_AMBIGUOUS_DELTA;
    if (left->definitionId != right->definitionId)
        return OW_WILD_RUNTIME_STATUS_OK;
    status = CopyDefinition(left->definitionId, definition);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    if (!(definition->flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS)
        && left->ownerId != right->ownerId)
        return OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED;
    if (!(definition->flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
        && left->ownerId == right->ownerId)
        return OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED;
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus ValidatePlannedMultiplicity(
    const OverworldWildRuntimeDeltaOperation *operations,
    const u8 *order,
    u8 operationCount,
    const OverworldWildRuntimeDeltaOperationResult *operationResults,
    const OverworldWildRuntimeSlotSidecar *slot,
    u8 removalMask,
    OverworldWildRuntimeDefinition *definition)
{
    OverworldWildRuntimeLayer left, right;
    OverworldWildRuntimeStatus status;
    u8 i, j, layerIndex;
    for (i = 0; i < operationCount; i++) {
        const OverworldWildRuntimeDeltaOperation *leftOperation =
            &operations[order[i]];
        if (leftOperation->kind > OW_WILD_RUNTIME_DELTA_REPLACE
            || operationResults[i].status != OW_WILD_RUNTIME_STATUS_OK)
            continue;
        memset(&left, 0, sizeof(left));
        left.definitionId = leftOperation->payload.apply.definitionId;
        left.ownerId = leftOperation->payload.apply.ownerId;
        left.instanceKey = leftOperation->payload.apply.instanceKey;
        for (j = i + 1; j < operationCount; j++) {
            const OverworldWildRuntimeDeltaOperation *rightOperation =
                &operations[order[j]];
            if (rightOperation->kind > OW_WILD_RUNTIME_DELTA_REPLACE
                || operationResults[j].status != OW_WILD_RUNTIME_STATUS_OK)
                continue;
            memset(&right, 0, sizeof(right));
            right.definitionId = rightOperation->payload.apply.definitionId;
            right.ownerId = rightOperation->payload.apply.ownerId;
            right.instanceKey = rightOperation->payload.apply.instanceKey;
            status = CheckMultiplicityPair(&left, &right, definition);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        }
        for (layerIndex = 0; layerIndex < slot->activeLayerCount;
             layerIndex++) {
            if (removalMask & (1u << layerIndex)) continue;
            ReadLayer(slot, layerIndex, &right);
            status = CheckMultiplicityPair(&left, &right, definition);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        }
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static BOOL StoredLayerMatchesDefinition(
    const OverworldWildRuntimeSlotSidecar *slot,
    u8 index,
    const OverworldWildRuntimeDefinition *definition)
{
    u8 expectedFlags = 0;
    if (definition->flags & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN)
        expectedFlags |= OW_WILD_RUNTIME_GENERATED_FLAG_HAS_TIRED_ORIGIN;
    if (definition->flags & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
        expectedFlags |= OW_WILD_RUNTIME_GENERATED_FLAG_HAS_REQUIRED_OWNER;
    return slot->layerBank.generatedFlags[index] == expectedFlags
        && slot->layerBank.tiredOriginKinds[index]
            == definition->tiredOriginKind
        && slot->layerBank.requiredOwnerIds[index]
            == definition->requiredOwnerId;
}

static OverworldWildRuntimeStatus ValidateStoredSlotSemantics(
    const OverworldWildRuntimeSlotSidecar *slot)
{
    OverworldWildRuntimeDefinition definition;
    u8 i, j;
    for (i = 0; i < slot->activeLayerCount; i++) {
        OverworldWildRuntimeStatus status = CopyDefinition(
            slot->layerBank.definitionIds[i], &definition);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        if (!StoredLayerMatchesDefinition(slot, i, &definition))
            return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
        if ((definition.flags
                & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
            && slot->layerBank.ownerIds[i] != definition.requiredOwnerId)
            return OW_WILD_RUNTIME_STATUS_OWNER_NOT_AUTHORIZED;
        if (!(definition.flags
                & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
            && slot->layerBank.instanceKeys[i] != 0)
            return definition.flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER
                ? OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER
                : OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED;
        for (j = i + 1; j < slot->activeLayerCount; j++) {
            if (slot->layerBank.definitionIds[j] != definition.stableId)
                continue;
            if (!(definition.flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_OWNERS)
                && slot->layerBank.ownerIds[j] != slot->layerBank.ownerIds[i])
                return OW_WILD_RUNTIME_STATUS_DEFINITION_OWNED;
            if (!(definition.flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
                && slot->layerBank.ownerIds[j] == slot->layerBank.ownerIds[i])
                return OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED;
        }
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static void RekeySlot(OverworldWildRuntimeSlotSidecar *slot, u8 count)
{
    u8 i;
    for (i = 0; i < count; i++)
        slot->layerBank.entryGenerations[i] = (u32)i + 1;
    slot->nextEntryGeneration = (u32)count + 1;
}

static void InitializeInvalidatedSlot(
    OverworldWildRuntimeSlotSidecar *slot,
    u32 slotGeneration)
{
    memset(slot, 0, sizeof(*slot));
    slot->slotGeneration = slotGeneration;
    slot->staticContextGeneration = 1;
    slot->nextEntryGeneration = 1;
    slot->nextTimerGeneration = 1;
    slot->layerGeneration = 1;
    slot->effectiveGeneration = 1;
    slot->lifecycleTransitions = 1;
    slot->lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
}

static void RestartRuntime(
    OverworldWildBehaviorStackRuntime *runtime,
    BOOL terminalEpoch)
{
    u8 i;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u32 generation = OverworldWildRuntime_AdvanceNonzeroGeneration(
            runtime->slots[i].slotGeneration);
        InitializeInvalidatedSlot(&runtime->slots[i], generation);
    }
    runtime->handleEpoch = terminalEpoch
        ? 1 : OverworldWildRuntime_AdvanceNonzeroGeneration(runtime->handleEpoch);
    RotatePrivateIdentity(runtime);
}

static BOOL StageSlotsForRekey(OverworldWildBehaviorStackRuntime *runtime)
{
    OverworldWildRuntimeStatus status;
    u8 slotIndex;
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        status = ValidateBank(slot);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return FALSE;
        status = ValidateStoredSlotSemantics(slot);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return FALSE;
        sOverworldWildRuntimeLayerService.wrapLayerCounts[slotIndex] =
            slot->activeLayerCount;
        sOverworldWildRuntimeLayerService.wrapLayerGenerations[slotIndex] =
            slot->activeLayerCount
            ? OverworldWildRuntime_AdvanceNonzeroGeneration(
                slot->layerGeneration)
            : slot->layerGeneration;
    }
    return TRUE;
}

void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlotIndex)
{
    u8 slotIndex;
    if (runtime == NULL || targetSlotIndex < 0
        || targetSlotIndex >= OW_WILD_MAX_SPAWNS) return;
    if (runtime->handleEpoch == 0xFFFFFFFFu) {
        RestartRuntime(runtime, TRUE);
        return;
    }
    if (!StageSlotsForRekey(runtime)) {
        RestartRuntime(runtime, FALSE);
        return;
    }
    runtime->handleEpoch++;
    RotatePrivateIdentity(runtime);
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        if (slotIndex == (u8)targetSlotIndex) {
            InitializeInvalidatedSlot(slot, 1);
        } else {
            RekeySlot(slot,
                sOverworldWildRuntimeLayerService.wrapLayerCounts[slotIndex]);
            slot->layerGeneration =
                sOverworldWildRuntimeLayerService
                    .wrapLayerGenerations[slotIndex];
        }
    }
}

OverworldWildRuntimeStatus OverworldWildRuntime_BindPrivateIdentity(
    OverworldWildBehaviorStackRuntime *runtime)
{
    if (runtime == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    if (sOverworldWildRuntimeLayerService.privateRuntimeIdentity
            == 0xFFFFFFFFu) {
        if (runtime->handleEpoch == 0xFFFFFFFFu)
            RestartRuntime(runtime, TRUE);
        else
            runtime->handleEpoch++;
    }
    RotatePrivateIdentity(runtime);
    sOverworldWildRuntimeLayerService.boundRuntime = runtime;
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus ApplyDeltaCore(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    const OverworldWildRuntimeDeltaOperation *operations,
    u8 operationCount,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeDeltaScratch *scratch =
        &sOverworldWildRuntimeLayerService.scratch;
    OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    u8 i, j, survivors, mutated = FALSE, rekey = FALSE;
    BOOL needsApplicability = FALSE;
    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitResult(runtime, slotIndex, result);
    if (runtime == NULL || operations == NULL || applicability == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || sOverworldWildRuntimeLayerService.privateRuntimeIdentity == 0
        || runtime->handleEpoch == 0
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || runtime->reserved[0] || runtime->reserved[1] || runtime->reserved[2]
        || slotIndex >= OW_WILD_MAX_SPAWNS || expectedSlotGeneration == 0
        || operationCount > OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS)
        return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE);
    slot = &runtime->slots[slotIndex];
    if (slot->lifecycleState != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
        return Fail(result, OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT);
    if (slot->slotGeneration != expectedSlotGeneration)
        return Fail(result, OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH);
    status = ValidateBank(slot);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    status = ValidateStoredSlotSemantics(slot);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    memset(scratch, 0, sizeof(*scratch));
    for (i = 0; i < operationCount; i++) scratch->operationOrder[i] = i;
    for (i = 1; i < operationCount; i++) {
        u8 value = scratch->operationOrder[i], cursor = i;
        while (cursor && operations[scratch->operationOrder[cursor - 1]].operationId
                > operations[value].operationId) {
            scratch->operationOrder[cursor] = scratch->operationOrder[cursor - 1];
            cursor--;
        }
        scratch->operationOrder[cursor] = value;
    }
    status = RejectAmbiguity(operations, scratch->operationOrder,
        operationCount, slot);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    for (i = 0; i < operationCount; i++) {
        const OverworldWildRuntimeDeltaOperation *operation =
            &operations[scratch->operationOrder[i]];
        status = ValidateOperation(operation);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
        if (operation->kind <= OW_WILD_RUNTIME_DELTA_REPLACE)
            needsApplicability = TRUE;
        if (operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED
            || operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT) {
            int ignored;
            status = ValidateHandle(runtime, slotIndex,
                &operation->payload.handle, &ignored);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
        }
    }
    if (needsApplicability) {
        status = ValidateApplicabilityShape(applicability);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    }
    for (i = 0; i < operationCount; i++) {
        const OverworldWildRuntimeDeltaOperation *operation =
            &operations[scratch->operationOrder[i]];
        OverworldWildRuntimeDeltaOperationResult *opResult =
            &result->operationResults[i];
        memset(opResult, 0, sizeof(*opResult));
        opResult->operationId = operation->operationId;
        if (operation->kind <= OW_WILD_RUNTIME_DELTA_REPLACE) {
            OverworldWildRuntimeDefinition *definition = &scratch->definitions[0];
            int existing;
            status = CopyDefinition(operation->payload.apply.definitionId, definition);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
            if ((definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
                && operation->payload.apply.ownerId != definition->requiredOwnerId)
                return Fail(result, OW_WILD_RUNTIME_STATUS_OWNER_NOT_AUTHORIZED);
            if (!(definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
                && operation->payload.apply.instanceKey != 0)
                return Fail(result, definition->flags
                        & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER
                    ? OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER
                    : OW_WILD_RUNTIME_STATUS_INSTANCE_KEY_NOT_ALLOWED);
            status = CheckGeneratedTranslation(definition, applicability);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
            status = CheckApplicable(definition, applicability);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
            existing = FindLayer(slot, operation->payload.apply.ownerId,
                operation->payload.apply.instanceKey);
            if (operation->kind == OW_WILD_RUNTIME_DELTA_APPLY && existing >= 0) {
                if (slot->layerBank.definitionIds[existing]
                        != operation->payload.apply.definitionId)
                    return Fail(result, OW_WILD_RUNTIME_STATUS_OWNER_KEY_OCCUPIED);
                if (!StoredLayerMatchesDefinition(slot, (u8)existing, definition))
                    return Fail(result,
                        OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER);
                opResult->status = OW_WILD_RUNTIME_STATUS_IDEMPOTENT;
                opResult->matched = TRUE;
                opResult->handle.ownerId = operation->payload.apply.ownerId;
                opResult->handle.instanceKey = operation->payload.apply.instanceKey;
                continue;
            }
            if (operation->kind == OW_WILD_RUNTIME_DELTA_REPLACE) {
                OverworldWildRuntimeDefinition *old = &scratch->definitions[1];
                u8 mask = OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN
                    | OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER;
                if (existing < 0) return Fail(result, OW_WILD_RUNTIME_STATUS_NOT_FOUND);
                status = CopyDefinition(slot->layerBank.definitionIds[existing], old);
                if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
                if ((old->flags & mask) != (definition->flags & mask)
                    || old->tiredOriginKind != definition->tiredOriginKind
                    || old->requiredOwnerId != definition->requiredOwnerId)
                    return Fail(result,
                        OW_WILD_RUNTIME_STATUS_GENERATED_WRAPPER_FAMILY_MISMATCH);
                scratch->removalMask |= 1u << existing;
            }
            if (scratch->additionCount
                    < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT) {
                OverworldWildRuntimeLayer *layer =
                    &scratch->finalLayers[scratch->additionCount++];
                memset(layer, 0, sizeof(*layer));
                layer->definitionId = definition->stableId;
                layer->ownerId = operation->payload.apply.ownerId;
                layer->instanceKey = operation->payload.apply.instanceKey;
                layer->requiredOwnerId = definition->requiredOwnerId;
                layer->hasTiredOriginKind = (definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN) != 0;
                layer->tiredOriginKind = definition->tiredOriginKind;
                layer->hasRequiredOwnerId = (definition->flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER) != 0;
                /* Scratch-only marker, cleared before publication. */
                layer->reserved = 1;
            } else {
                scratch->additionCount++;
            }
            opResult->status = OW_WILD_RUNTIME_STATUS_OK;
            opResult->matched = TRUE;
            opResult->handle.ownerId = operation->payload.apply.ownerId;
            opResult->handle.instanceKey = operation->payload.apply.instanceKey;
            mutated = TRUE;
        } else if (operation->kind <= OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT) {
            int existing = -1;
            status = ValidateHandle(runtime, slotIndex,
                &operation->payload.handle, &existing);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
            if (existing < 0) {
                if (operation->kind == OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED)
                    return Fail(result, OW_WILD_RUNTIME_STATUS_STALE_HANDLE);
                opResult->status = OW_WILD_RUNTIME_STATUS_STALE_NOOP;
            } else {
                scratch->removalMask |= 1u << existing;
                opResult->status = OW_WILD_RUNTIME_STATUS_OK;
                opResult->matched = TRUE;
                mutated = TRUE;
            }
        } else {
            for (j = 0; j < slot->activeLayerCount; j++) {
                OverworldWildRuntimeLayer layer;
                ReadLayer(slot, j, &layer);
                if (OperationAddressesLayer(operation, &layer)) {
                    scratch->removalMask |= 1u << j;
                    opResult->matched = TRUE;
                    mutated = TRUE;
                }
            }
            opResult->status = OW_WILD_RUNTIME_STATUS_OK;
        }
    }
    survivors = slot->activeLayerCount;
    for (i = 0; i < slot->activeLayerCount; i++)
        if (scratch->removalMask & (1u << i)) survivors--;
    status = ValidatePlannedMultiplicity(operations, scratch->operationOrder,
        operationCount, result->operationResults, slot, scratch->removalMask,
        &scratch->definitions[0]);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    if ((u8)(survivors + scratch->additionCount)
            > OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT)
        return Fail(result, OW_WILD_RUNTIME_STATUS_CAPACITY_EXCEEDED);
    scratch->finalCount = scratch->additionCount;
    for (i = 0; i < slot->activeLayerCount; i++) {
        if (!(scratch->removalMask & (1u << i)))
            ReadLayer(slot, i, &scratch->finalLayers[scratch->finalCount++]);
    }
    SortLayers(scratch->finalLayers, scratch->finalCount);
    status = ValidateMultiplicity(scratch->finalLayers, scratch->finalCount,
        &scratch->definitions[0]);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    if (scratch->additionCount
        && slot->nextEntryGeneration
            > 0xFFFFFFFFu - scratch->additionCount) {
        if (runtime->handleEpoch != 0xFFFFFFFFu
            && !StageSlotsForRekey(runtime)) {
            RestartRuntime(runtime, FALSE);
            memset(result->operationResults, 0,
                sizeof(result->operationResults));
            result->runtimeEpochAfter = runtime->handleEpoch;
            result->slotGenerationAfter =
                runtime->slots[slotIndex].slotGeneration;
            result->layerGenerationAfter =
                runtime->slots[slotIndex].layerGeneration;
            result->effectiveGenerationAfter =
                runtime->slots[slotIndex].effectiveGeneration;
            result->status =
                OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED;
            result->ok = result->mutated = TRUE;
            return OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED;
        }
        rekey = TRUE;
    }
    if (!mutated) {
        for (i = 0; i < operationCount; i++) {
            if (result->operationResults[i].handle.ownerId) {
                int index = FindLayer(slot, result->operationResults[i].handle.ownerId,
                    result->operationResults[i].handle.instanceKey);
                OverworldWildRuntimeLayer layer;
                ReadLayer(slot, index, &layer);
                result->operationResults[i].handle = MakeHandle(runtime, slotIndex, &layer);
            }
        }
        result->operationResultCount = operationCount;
        result->status = OW_WILD_RUNTIME_STATUS_IDEMPOTENT;
        result->ok = TRUE;
        return OW_WILD_RUNTIME_STATUS_IDEMPOTENT;
    }
    if (rekey && runtime->handleEpoch == 0xFFFFFFFFu) {
        RestartRuntime(runtime, TRUE);
        memset(result->operationResults, 0, sizeof(result->operationResults));
        result->runtimeEpochAfter = runtime->handleEpoch;
        result->slotGenerationAfter = runtime->slots[slotIndex].slotGeneration;
        result->layerGenerationAfter = runtime->slots[slotIndex].layerGeneration;
        result->effectiveGenerationAfter = runtime->slots[slotIndex].effectiveGeneration;
        result->status = OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED;
        result->ok = result->mutated = TRUE;
        return OW_WILD_RUNTIME_STATUS_RUNTIME_EPOCH_RESTARTED;
    }
    if (rekey) {
        runtime->handleEpoch++;
        RotatePrivateIdentity(runtime);
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            if (i == slotIndex) continue;
            RekeySlot(&runtime->slots[i],
                sOverworldWildRuntimeLayerService.wrapLayerCounts[i]);
            runtime->slots[i].layerGeneration =
                sOverworldWildRuntimeLayerService.wrapLayerGenerations[i];
        }
        for (i = 0; i < scratch->finalCount; i++) {
            scratch->finalLayers[i].entryGeneration = (u32)i + 1;
            scratch->finalLayers[i].reserved = 0;
        }
        slot->nextEntryGeneration = (u32)scratch->finalCount + 1;
    } else {
        for (i = 0; i < scratch->finalCount; i++) {
            if (scratch->finalLayers[i].reserved) {
                scratch->finalLayers[i].entryGeneration =
                    slot->nextEntryGeneration++;
                scratch->finalLayers[i].reserved = 0;
            }
        }
    }
    WriteLayers(slot, scratch->finalLayers, scratch->finalCount);
    slot->layerGeneration = OverworldWildRuntime_AdvanceNonzeroGeneration(
        slot->layerGeneration);
    for (i = 0; i < operationCount; i++) {
        if (result->operationResults[i].handle.ownerId) {
            int index = FindLayer(slot, result->operationResults[i].handle.ownerId,
                result->operationResults[i].handle.instanceKey);
            OverworldWildRuntimeLayer layer;
            ReadLayer(slot, index, &layer);
            result->operationResults[i].handle = MakeHandle(runtime, slotIndex, &layer);
        }
    }
    result->runtimeEpochAfter = runtime->handleEpoch;
    result->slotGenerationAfter = slot->slotGeneration;
    result->layerGenerationAfter = slot->layerGeneration;
    result->effectiveGenerationAfter = slot->effectiveGeneration;
    result->operationResultCount = operationCount;
    result->status = OW_WILD_RUNTIME_STATUS_OK;
    result->ok = result->mutated = TRUE;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_ApplyStackDelta(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeStackDeltaRequest *request,
    OverworldWildRuntimeStackDeltaResult *result)
{
    u8 i;
    if (request == NULL) {
        if (result) InitResult(runtime, 0xFF, result);
        return result ? Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE)
                      : OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    }
    if (request->reserved != 0
        || request->operationCount > OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS)
        return result ? (InitResult(runtime, request->slotIndex, result),
            Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE))
            : OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    for (i = request->operationCount;
         i < OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS; i++)
        if (!BytesAreZero(&request->operations[i],
                sizeof(request->operations[i])))
            return result ? (InitResult(runtime, request->slotIndex, result),
                Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE))
                : OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    return ApplyDeltaCore(runtime, request->slotIndex,
        request->expectedSlotGeneration, &request->applicability,
        request->operations, request->operationCount, result);
}

static OverworldWildRuntimeStatus OneOperation(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    const OverworldWildRuntimeDeltaOperation *operation,
    OverworldWildRuntimeStackDeltaResult *result)
{
    sOverworldWildRuntimeLayerService.oneOperation = *operation;
    if (applicability != NULL)
        sOverworldWildRuntimeLayerService.oneApplicability = *applicability;
    else
        memset(&sOverworldWildRuntimeLayerService.oneApplicability, 0,
            sizeof(sOverworldWildRuntimeLayerService.oneApplicability));
    return ApplyDeltaCore(runtime, slotIndex, expectedSlotGeneration,
        &sOverworldWildRuntimeLayerService.oneApplicability,
        &sOverworldWildRuntimeLayerService.oneOperation, 1, result);
}

OverworldWildRuntimeStatus OverworldWildRuntime_Apply(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    u16 definitionId, u16 ownerId, u16 instanceKey,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeDeltaOperation operation;
    memset(&operation, 0, sizeof(operation));
    operation.operationId = 1;
    operation.kind = OW_WILD_RUNTIME_DELTA_APPLY;
    operation.payload.apply.definitionId = definitionId;
    operation.payload.apply.ownerId = ownerId;
    operation.payload.apply.instanceKey = instanceKey;
    return OneOperation(runtime, slotIndex, expectedSlotGeneration,
        applicability, &operation, result);
}

OverworldWildRuntimeStatus OverworldWildRuntime_Replace(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    u16 ownerId, u16 instanceKey, u16 definitionId,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeDeltaOperation operation;
    memset(&operation, 0, sizeof(operation));
    operation.operationId = 1;
    operation.kind = OW_WILD_RUNTIME_DELTA_REPLACE;
    operation.payload.apply.definitionId = definitionId;
    operation.payload.apply.ownerId = ownerId;
    operation.payload.apply.instanceKey = instanceKey;
    return OneOperation(runtime, slotIndex, expectedSlotGeneration,
        applicability, &operation, result);
}

OverworldWildRuntimeStatus OverworldWildRuntime_Remove(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeLayerHandle *handle,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeDeltaOperation operation;
    OverworldWildRuntimeStatus status;
    memset(&operation, 0, sizeof(operation));
    operation.operationId = 1;
    operation.kind = OW_WILD_RUNTIME_DELTA_REMOVE_IF_PRESENT;
    if (handle) operation.payload.handle = *handle;
    status = OneOperation(runtime, slotIndex, expectedSlotGeneration,
        NULL, &operation, result);
    if (status == OW_WILD_RUNTIME_STATUS_IDEMPOTENT
        && result->operationResults[0].status
            == OW_WILD_RUNTIME_STATUS_STALE_NOOP) {
        result->status = OW_WILD_RUNTIME_STATUS_STALE_NOOP;
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    }
    return status;
}

OverworldWildRuntimeStatus OverworldWildRuntime_RemoveOwner(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u16 ownerId,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeDeltaOperation operation;
    memset(&operation, 0, sizeof(operation));
    operation.operationId = 1;
    operation.kind = OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT;
    operation.payload.owner.ownerId = ownerId;
    return OneOperation(runtime, slotIndex, expectedSlotGeneration,
        NULL, &operation, result);
}

OverworldWildRuntimeStatus OverworldWildRuntime_ClearAllForSlot(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeDeltaOperation operation;
    memset(&operation, 0, sizeof(operation));
    operation.operationId = 1;
    operation.kind = OW_WILD_RUNTIME_DELTA_CLEAR;
    return OneOperation(runtime, slotIndex, expectedSlotGeneration,
        NULL, &operation, result);
}

u8 OverworldWildRuntime_GetLayerCount(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration)
{
    if (runtime == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || slotIndex >= OW_WILD_MAX_SPAWNS
        || runtime->slots[slotIndex].lifecycleState
            != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED
        || runtime->slots[slotIndex].slotGeneration != expectedSlotGeneration
        || ValidateBank(&runtime->slots[slotIndex]) != OW_WILD_RUNTIME_STATUS_OK)
        return 0;
    return runtime->slots[slotIndex].activeLayerCount;
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetLayerByIndex(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 layerIndex,
    OverworldWildRuntimeLayer *layerOut)
{
    OverworldWildRuntimeStatus status;
    if (runtime == NULL || layerOut == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || runtime->handleEpoch == 0
        || runtime->reserved[0] || runtime->reserved[1] || runtime->reserved[2]
        || slotIndex >= OW_WILD_MAX_SPAWNS)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    if (runtime->slots[slotIndex].lifecycleState
            != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
        return OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT;
    if (runtime->slots[slotIndex].slotGeneration != expectedSlotGeneration)
        return OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH;
    status = ValidateBank(&runtime->slots[slotIndex]);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    if (layerIndex >= runtime->slots[slotIndex].activeLayerCount)
        return OW_WILD_RUNTIME_STATUS_NOT_FOUND;
    ReadLayer(&runtime->slots[slotIndex], layerIndex, layerOut);
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_FindLayer(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u16 ownerId, u16 instanceKey,
    OverworldWildRuntimeLayer *layerOut,
    OverworldWildRuntimeLayerHandle *handleOut)
{
    OverworldWildRuntimeStatus status;
    int index;
    if (ownerId == 0 || layerOut == NULL || handleOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = OverworldWildRuntime_GetLayerByIndex(runtime, slotIndex,
        expectedSlotGeneration, 0, layerOut);
    if (status != OW_WILD_RUNTIME_STATUS_OK
        && status != OW_WILD_RUNTIME_STATUS_NOT_FOUND) return status;
    index = FindLayer(&runtime->slots[slotIndex], ownerId, instanceKey);
    if (index < 0) {
        memset(layerOut, 0, sizeof(*layerOut));
        memset(handleOut, 0, sizeof(*handleOut));
        return OW_WILD_RUNTIME_STATUS_NOT_FOUND;
    }
    ReadLayer(&runtime->slots[slotIndex], index, layerOut);
    *handleOut = MakeHandle(runtime, slotIndex, layerOut);
    return OW_WILD_RUNTIME_STATUS_OK;
}
