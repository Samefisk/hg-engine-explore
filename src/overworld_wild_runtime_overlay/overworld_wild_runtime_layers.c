#include "overworld_wild_runtime_layers_internal.h"

#define OW_WILD_RUNTIME_ROLE_TIRED 3
#define OW_WILD_RUNTIME_ROLE_MASK(role) (1u << ((role) - 1))
#ifdef OW_WILD_RUNTIME_HOST_TEST
#define OW_WILD_RUNTIME_COMPOSITION_CODE
#else
#define OW_WILD_RUNTIME_COMPOSITION_CODE \
    __attribute__((section(".ow_wild_runtime_composition")))
#endif

typedef struct OverworldWildRuntimeDeltaScratch {
    OverworldWildRuntimeLayer finalLayers[OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    OverworldWildRuntimeDefinition definitions[2];
    u8 operationOrder[OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS];
    u8 removalMask;
    u8 additionCount;
    u8 finalCount;
    u8 reserved;
} OverworldWildRuntimeDeltaScratch;

typedef struct OverworldWildRuntimeModifierWork {
    OverworldWildRuntimeDefinition definition;
    u16 ownerId;
    u16 instanceKey;
} OverworldWildRuntimeModifierWork;

typedef struct OverworldWildRuntimeRekeyStage {
    u32 layerGenerations[OW_WILD_MAX_SPAWNS];
    u8 layerCounts[OW_WILD_MAX_SPAWNS];
    u8 reserved[2];
} OverworldWildRuntimeRekeyStage;

typedef struct __attribute__((may_alias)) OverworldWildRuntimeCompositionWorkspace {
    u32 busy;
    OverworldWildRuntimeDeltaScratch delta;
    OverworldWildRuntimeStaticCache prospectiveStatic;
    OverworldWildRuntimeEffectiveCache prospectiveEffective;
    OverworldWildRuntimeProvenance prospectiveProvenance;
    OverworldWildRuntimeRekeyStage rekey;
    OverworldWildRuntimeModifierWork modifiers[
        OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT
            + OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS];
} OverworldWildRuntimeCompositionWorkspace;

typedef char OverworldWildRuntimeCompositionWorkspaceMustExactlyFit[
    sizeof(OverworldWildRuntimeCompositionWorkspace)
            == OW_WILD_RUNTIME_COMPOSITION_WORKSPACE_SIZE
        ? 1 : -1];

typedef struct OverworldWildRuntimeLayerService {
    OverworldWildBehaviorStackRuntime *boundRuntime;
    u32 privateRuntimeIdentity;
} OverworldWildRuntimeLayerService;

static OverworldWildRuntimeLayerService sOverworldWildRuntimeLayerService;

static BOOL CompositionWorkspaceIsBusy(
    const OverworldWildBehaviorStackRuntime *runtime)
{
    return runtime != NULL && runtime->compositionWorkspace.alignment != 0;
}

static OverworldWildRuntimeCompositionWorkspace *AcquireCompositionWorkspace(
    OverworldWildBehaviorStackRuntime *runtime)
{
    OverworldWildRuntimeCompositionWorkspace *workspace;
    if (CompositionWorkspaceIsBusy(runtime)) return NULL;
    workspace = (OverworldWildRuntimeCompositionWorkspace *)
        runtime->compositionWorkspace.bytes;
    /* ReleaseCompositionWorkspace leaves all scratch zeroed. */
    workspace->busy = TRUE;
    return workspace;
}

static __attribute__((noinline)) void ReleaseCompositionWorkspace(
    OverworldWildBehaviorStackRuntime *runtime)
{
    memset(&runtime->compositionWorkspace, 0,
        sizeof(runtime->compositionWorkspace));
}

static void ExpireHiddenTimers(
    OverworldWildRuntimeTimer *timers,
    u8 count,
    u16 winningOwnerId,
    u16 winningInstanceKey);

void OverworldWildRuntime_ClearSlotStorage(
    OverworldWildRuntimeSlotSidecar *slot)
{
    memset(slot, 0, sizeof(*slot));
}

void OverworldWildRuntime_InitializeStorage(
    OverworldWildBehaviorStackRuntime *runtime)
{
    int slotIndex;

    memset(runtime, 0, sizeof(*runtime));
    runtime->handleEpoch = 1;
    runtime->dataIncarnation = 1;
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_ACTIVE;
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        slot->slotGeneration = 1;
        slot->staticContextGeneration = 1;
        slot->nextEntryGeneration = 1;
        slot->nextTimerGeneration = 1;
        slot->layerGeneration = 1;
        slot->effectiveGeneration = 1;
        slot->cacheIncarnation = 1;
        slot->lifecycleState = OW_WILD_RUNTIME_SLOT_LIFECYCLE_VIRGIN;
    }
}

#ifdef OW_WILD_RUNTIME_HOST_TEST
void OverworldWildRuntime_MarkResidentCold(
    OverworldWildBehaviorStackRuntime *runtime)
{
    int slot;
    runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        runtime->dataIncarnation);
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        OverworldWildRuntimeStaticContext staticContext =
            runtime->slots[slot].staticCache.staticContext;
        runtime->slots[slot].cacheIncarnation =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->slots[slot].cacheIncarnation);
        memset((u8 *)&runtime->slots[slot]
                + offsetof(OverworldWildRuntimeSlotSidecar, staticCache), 0,
            offsetof(OverworldWildRuntimeSlotSidecar, provenance)
                + sizeof(runtime->slots[slot].provenance)
                - offsetof(OverworldWildRuntimeSlotSidecar, staticCache));
        runtime->slots[slot].staticCache.staticContext = staticContext;
    }
    runtime->lifetimeState = OW_WILD_RUNTIME_LIFETIME_RESIDENT_COLD;
}

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

static BOOL BytesEqual(const void *left, const void *right, u32 size)
{
    const u8 *leftBytes = left;
    const u8 *rightBytes = right;
    while (size-- != 0) {
        if (*leftBytes++ != *rightBytes++) return FALSE;
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

static u32 HashBytes(u32 hash, const void *data, u32 size)
{
    const u8 *bytes = data;
    while (size-- != 0) hash = Mix(hash, *bytes++);
    return hash != 0 ? hash : 1;
}

static u32 EffectiveHash(const OverworldWildRuntimeEffectiveCache *cache)
{
    return HashBytes(0x4F574539u, &cache->capabilityMask,
        sizeof(*cache) - offsetof(OverworldWildRuntimeEffectiveCache,
            capabilityMask));
}

static u32 ResidentProvenanceHash(
    const OverworldWildRuntimeResidentProvenance *provenance)
{
    return HashBytes(0x4F575039u, &provenance->winningDefinitionId,
        sizeof(*provenance) - offsetof(
            OverworldWildRuntimeResidentProvenance, winningDefinitionId));
}

static void StoreResidentProvenance(
    OverworldWildRuntimeResidentProvenance *resident,
    const OverworldWildRuntimeProvenance *provenance)
{
    memcpy(resident, (void *)provenance, sizeof(*resident));
}

static u32 CacheIdentity(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeSlotSidecar *slot,
    const OverworldWildRuntimeEffectiveCache *effective,
    u32 provenanceFreshnessGeneration,
    u32 privateRuntimeIdentity)
{
    u32 identity = Mix(0x4F574339u,
        privateRuntimeIdentity);
    (void)runtime;
    identity = Mix(identity, effective->dataIncarnation);
    identity = Mix(identity, effective->cacheIncarnation);
    identity = Mix(identity, effective->catalogIdentity);
    identity = Mix(identity, effective->staticContextIdentity);
    identity = Mix(identity, effective->staticSetHash);
    identity = Mix(identity, effective->staticContextGeneration);
    identity = Mix(identity, slot->slotGeneration);
    identity = Mix(identity, effective->layerGeneration);
    identity = Mix(identity, effective->effectiveGeneration);
    identity = Mix(identity, effective->effectiveHash);
    identity = Mix(identity, effective->provenanceHash);
    identity = Mix(identity, provenanceFreshnessGeneration);
    return identity != 0 ? identity : 1;
}

static OverworldWildRuntimeStatus ValidateCacheKey(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeSlotSidecar *slot)
{
    const OverworldWildRuntimeStaticCache *staticCache = &slot->staticCache;
    const OverworldWildRuntimeEffectiveCache *effective =
        &slot->effectiveCache;
    const OverworldWildRuntimeResidentProvenance *provenance =
        &slot->provenance;
    if (runtime == NULL || runtime->dataIncarnation == 0
        || slot->cacheIncarnation == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    {
        OverworldWildRuntimeStatus status =
            OverworldWildRuntime_ValidateStaticCache(staticCache,
                slot->staticContextGeneration);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    if (!(effective->flags & OW_WILD_RUNTIME_CACHE_VALID)
        || !(provenance->flags & OW_WILD_RUNTIME_PROVENANCE_VALID)
        || effective->dataIncarnation != runtime->dataIncarnation
        || effective->cacheIncarnation != slot->cacheIncarnation
        || effective->catalogIdentity != staticCache->catalogIdentity
        || effective->staticContextIdentity
            != staticCache->staticContextIdentity
        || effective->staticSetHash != staticCache->staticSetHash
        || effective->staticContextGeneration
            != slot->staticContextGeneration
        || effective->layerGeneration != slot->layerGeneration
        || effective->effectiveGeneration != slot->effectiveGeneration
        || effective->effectiveHash != EffectiveHash(effective)
        || provenance->dataIncarnation != effective->dataIncarnation
        || provenance->cacheIncarnation != effective->cacheIncarnation
        || provenance->catalogIdentity != effective->catalogIdentity
        || provenance->staticContextIdentity
            != effective->staticContextIdentity
        || provenance->staticSetHash != effective->staticSetHash
        || provenance->staticContextGeneration
            != effective->staticContextGeneration
        || provenance->layerGeneration != effective->layerGeneration
        || provenance->effectiveGeneration != effective->effectiveGeneration
        || provenance->effectiveHash != effective->effectiveHash
        || provenance->freshnessGeneration == 0
        || provenance->candidateCount
            > OW_WILD_RUNTIME_MAX_PROVENANCE_CANDIDATES
        || provenance->provenanceHash != ResidentProvenanceHash(provenance)
        || effective->provenanceHash != provenance->provenanceHash
        || effective->cacheIdentity != provenance->cacheIdentity
        || effective->cacheIdentity
            != CacheIdentity(runtime, slot, effective,
                provenance->freshnessGeneration,
                sOverworldWildRuntimeLayerService.privateRuntimeIdentity))
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    return OW_WILD_RUNTIME_STATUS_OK;
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

u32 OverworldWildRuntime_TimerExpiryTagInternal(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry)
{
    u32 tag = HandleTag(runtime, expiry->runtimeEpoch, expiry->slotIndex,
        expiry->slotGeneration, expiry->ownerId, expiry->instanceKey,
        expiry->entryGeneration);
    tag = Mix(tag, expiry->timerGeneration);
    tag = Mix(tag, ((u32)expiry->definitionId << 16)
        | expiry->recoveryTransitionId);
    tag = Mix(tag, expiry->recoveryPolicy);
    return tag != 0 ? tag : 0x4F575458u;
}

OverworldWildRuntimeStatus OverworldWildRuntime_PreflightTimerExpiryInternal(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    if (runtime == NULL || expiry == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || runtime->handleEpoch == 0
        || sOverworldWildRuntimeLayerService.privateRuntimeIdentity == 0
        || runtime->reserved[0] || runtime->reserved[1]
        || runtime->reserved[2]
        || expiry->runtimeEpoch == 0 || expiry->slotGeneration == 0
        || expiry->entryGeneration == 0 || expiry->timerGeneration == 0
        || expiry->ownerId == 0 || expiry->definitionId == 0
        || expiry->recoveryPolicy == 0
        || expiry->slotIndex >= OW_WILD_MAX_SPAWNS
        || expiry->validityTag == 0 || expiry->reserved[0]
        || expiry->reserved[1])
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    slot = &runtime->slots[expiry->slotIndex];
    if (expiry->runtimeEpoch != runtime->handleEpoch
        || expiry->slotGeneration != slot->slotGeneration)
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    if (expiry->validityTag
            != OverworldWildRuntime_TimerExpiryTagInternal(runtime, expiry))
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    return OW_WILD_RUNTIME_STATUS_OK;
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

static void WriteTimers(
    OverworldWildRuntimeSlotSidecar *slot,
    const OverworldWildRuntimeTimer *timers,
    u8 count)
{
    memset(&slot->timerBank, 0, sizeof(slot->timerBank));
    if (count != 0)
        memcpy(slot->timerBank.timers, (void *)timers,
            count * sizeof(slot->timerBank.timers[0]));
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
        || slot->nextTimerGeneration == 0
        || slot->presentationGate > 1
        || slot->timerStateReserved[0] || slot->timerStateReserved[1]
        || slot->timerStateReserved[2]
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
        {
            const OverworldWildRuntimeTimer *timer =
                &slot->timerBank.timers[i];
            if (timer->flags & OW_WILD_RUNTIME_TIMER_VALID) {
                if ((timer->flags & ~(OW_WILD_RUNTIME_TIMER_VALID
                            | OW_WILD_RUNTIME_TIMER_ZERO_PENDING)) != 0
                    || timer->entryGeneration != layer.entryGeneration
                    || timer->ownerId != layer.ownerId
                    || timer->instanceKey != layer.instanceKey
                    || timer->definitionId != layer.definitionId
                    || timer->timerGeneration == 0
                    || timer->timerGeneration >= slot->nextTimerGeneration
                    || timer->clock < OW_WILD_RUNTIME_TIMER_CLOCK_FRAME
                    || timer->clock
                        > OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT
                    || timer->hiddenPolicy
                        < OW_WILD_RUNTIME_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN
                    || timer->hiddenPolicy
                        > OW_WILD_RUNTIME_HIDDEN_TIMER_EXPIRE_ON_HIDE
                    || timer->recoveryPolicy == 0
                    || timer->reserved[0] || timer->reserved[1]
                    || ((timer->flags & OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
                        != (timer->remainingTicks == 0
                            ? OW_WILD_RUNTIME_TIMER_ZERO_PENDING : 0)))
                    return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
                for (j = 0; j < i; j++)
                    if ((slot->timerBank.timers[j].flags
                            & OW_WILD_RUNTIME_TIMER_VALID)
                        && slot->timerBank.timers[j].timerGeneration
                            == timer->timerGeneration)
                        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
            } else if (!BytesAreZero(timer, sizeof(*timer))) {
                return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
            }
        }
        previous = layer;
    }
    for (; i < OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT; i++) {
        if (slot->layerBank.entryGenerations[i] || slot->layerBank.definitionIds[i]
            || slot->layerBank.ownerIds[i] || slot->layerBank.instanceKeys[i]
            || slot->layerBank.requiredOwnerIds[i]
            || slot->layerBank.tiredOriginKinds[i]
            || slot->layerBank.generatedFlags[i]
            || !BytesAreZero(&slot->timerBank.timers[i],
                sizeof(slot->timerBank.timers[i])))
            return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    }
    if (slot->effectiveCache.flags & OW_WILD_RUNTIME_CACHE_VALID) {
        OverworldWildRuntimeStatus status = ValidateCacheKey(
            sOverworldWildRuntimeLayerService.boundRuntime, slot);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    } else if (!BytesAreZero(&slot->effectiveCache,
            sizeof(slot->effectiveCache))
        || !BytesAreZero(&slot->provenance, sizeof(slot->provenance))) {
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
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

#ifdef OW_WILD_RUNTIME_HOST_TEST
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
#endif

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

OverworldWildRuntimeStatus
OverworldWildRuntime_MakeTimerRemovalHandleInternal(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u8 layerIndex,
    OverworldWildRuntimeLayerHandle *handleOut)
{
    OverworldWildRuntimeLayer layer;
    if (runtime == NULL || handleOut == NULL
        || slotIndex >= OW_WILD_MAX_SPAWNS
        || layerIndex >= runtime->slots[slotIndex].activeLayerCount)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    ReadLayer(&runtime->slots[slotIndex], layerIndex, &layer);
    *handleOut = MakeHandle(runtime, slotIndex, &layer);
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus ValidateOperation(
    const OverworldWildRuntimeDeltaOperation *operation,
    BOOL internalBoundaryPolicy)
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
        if (operation->payload.policy.mapLifetime > 3
            || (operation->payload.policy.mapLifetime == 0
                && !internalBoundaryPolicy)
            || operation->payload.policy.boundary
                > OW_WILD_RUNTIME_POLICY_BOUNDARY_BATTLE
            || !BytesAreZero(operation->payload.policy.reserved, 22))
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
        u8 lifetime;
        if (CopyDefinition(layer->definitionId, &definition)
                != OW_WILD_RUNTIME_STATUS_OK) return FALSE;
        lifetime = operation->payload.policy.boundary
                == OW_WILD_RUNTIME_POLICY_BOUNDARY_BATTLE
            ? definition.battleLifetime : definition.mapLifetime;
        return operation->payload.policy.mapLifetime == lifetime
            || (operation->payload.policy.mapLifetime == 0
                && (lifetime & 1));
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
                    == right->payload.policy.mapLifetime
                && left->payload.policy.boundary
                    == right->payload.policy.boundary)
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
    OverworldWildRuntimeTimerDefinition timerDefinition;
    u8 i, j;
    for (i = 0; i < slot->activeLayerCount; i++) {
        OverworldWildRuntimeStatus status = CopyDefinition(
            slot->layerBank.definitionIds[i], &definition);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        if (!StoredLayerMatchesDefinition(slot, i, &definition))
            return OW_WILD_RUNTIME_STATUS_INVALID_GENERATED_WRAPPER;
        if (!OverworldWildRuntime_ResolveInstalledTimerDefinition(
                definition.stableId, &slot->staticCache, &timerDefinition))
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        if (timerDefinition.clock == OW_WILD_RUNTIME_TIMER_CLOCK_NONE) {
            if (!BytesAreZero(&slot->timerBank.timers[i],
                    sizeof(slot->timerBank.timers[i])))
                return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        } else {
            const OverworldWildRuntimeTimer *timer =
                &slot->timerBank.timers[i];
            if (!(timer->flags & OW_WILD_RUNTIME_TIMER_VALID)
                || timer->recoveryTransitionId
                    != timerDefinition.recoveryTransitionId
                || timer->armedDuration != timerDefinition.duration
                || (timer->armedDuration == 255
                    ? timer->remainingTicks != 255
                    : timer->remainingTicks > timer->armedDuration)
                || timer->clock != timerDefinition.clock
                || timer->hiddenPolicy != timerDefinition.hiddenPolicy
                || timer->recoveryPolicy != timerDefinition.recoveryPolicy)
                return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        }
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
    u32 nextTimer = 1;
    u8 i;
    for (i = 0; i < count; i++) {
        slot->layerBank.entryGenerations[i] = (u32)i + 1;
        if (slot->timerBank.timers[i].flags
                & OW_WILD_RUNTIME_TIMER_VALID) {
            slot->timerBank.timers[i].entryGeneration = (u32)i + 1;
            slot->timerBank.timers[i].timerGeneration = nextTimer++;
        }
    }
    slot->nextEntryGeneration = (u32)count + 1;
    slot->nextTimerGeneration = nextTimer;
}

static void __attribute__((noinline)) InitializeInvalidatedSlot(
    OverworldWildRuntimeSlotSidecar *slot,
    u32 slotGeneration,
    u32 cacheIncarnation)
{
    OverworldWildRuntime_ClearSlotStorage(slot);
    slot->slotGeneration = slotGeneration;
    slot->staticContextGeneration = 1;
    slot->nextEntryGeneration = 1;
    slot->nextTimerGeneration = 1;
    slot->layerGeneration = 1;
    slot->effectiveGeneration = 1;
    slot->cacheIncarnation = cacheIncarnation;
    slot->lifecycleTransitions = 1;
    slot->lifecycleState =
        OW_WILD_RUNTIME_SLOT_LIFECYCLE_DESTRUCTIVELY_INVALIDATED;
}

static void RestartRuntime(
    OverworldWildBehaviorStackRuntime *runtime,
    BOOL terminalEpoch)
{
    u8 i;
    runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        runtime->dataIncarnation);
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u32 generation = OverworldWildRuntime_AdvanceNonzeroGeneration(
            runtime->slots[i].slotGeneration);
        u32 incarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
            runtime->slots[i].cacheIncarnation);
        InitializeInvalidatedSlot(&runtime->slots[i], generation, incarnation);
    }
    runtime->handleEpoch = terminalEpoch
        ? 1 : OverworldWildRuntime_AdvanceNonzeroGeneration(runtime->handleEpoch);
    RotatePrivateIdentity(runtime);
}

static BOOL StageSlotsForRekey(
    OverworldWildBehaviorStackRuntime *runtime,
    OverworldWildRuntimeRekeyStage *stage)
{
    OverworldWildRuntimeStatus status;
    u8 slotIndex;
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        status = ValidateBank(slot);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return FALSE;
        status = ValidateStoredSlotSemantics(slot);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return FALSE;
        stage->layerCounts[slotIndex] = slot->activeLayerCount;
        stage->layerGenerations[slotIndex] =
            slot->activeLayerCount
            ? OverworldWildRuntime_AdvanceNonzeroGeneration(
                slot->layerGeneration)
            : slot->layerGeneration;
    }
    return TRUE;
}

enum {
    OW_WILD_RUNTIME_SKIP_NONE = 0,
    OW_WILD_RUNTIME_SKIP_NOT_APPLICABLE = 1,
    OW_WILD_RUNTIME_SKIP_FILTER = 2,
    OW_WILD_RUNTIME_NORMALIZE_HOP_MAX = 1,
    OW_WILD_RUNTIME_NORMALIZE_SECONDARY_TILE = 2,
    OW_WILD_RUNTIME_NORMALIZE_STAMINA = 3,
};

static int OW_WILD_RUNTIME_COMPOSITION_CODE CompareDefinitionKey(
    const OverworldWildRuntimeDefinition *left,
    u16 leftOwner,
    u16 leftKey,
    const OverworldWildRuntimeDefinition *right,
    u16 rightOwner,
    u16 rightKey)
{
    if (left->channel != right->channel)
        return left->channel < right->channel ? -1 : 1;
    if (left->priority != right->priority)
        return left->priority < right->priority ? -1 : 1;
    if (left->stableId != right->stableId)
        return left->stableId < right->stableId ? -1 : 1;
    if (leftOwner != rightOwner) return leftOwner < rightOwner ? -1 : 1;
    if (leftKey != rightKey) return leftKey < rightKey ? -1 : 1;
    return 0;
}

static void OW_WILD_RUNTIME_COMPOSITION_CODE RecordNormalization(
    OverworldWildRuntimeProvenance *provenance,
    u8 fieldNamespace,
    u8 fieldId,
    u8 rule,
    u8 before,
    u8 after)
{
    OverworldWildRuntimeNormalizationProvenance *record;
    if (provenance->normalizationCount
            >= OW_WILD_RUNTIME_MAX_PROVENANCE_NORMALIZATIONS) {
        provenance->flags |=
            OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_NORMALIZATIONS;
        return;
    }
    record = &provenance->normalizations[provenance->normalizationCount++];
    record->fieldNamespace = fieldNamespace;
    record->fieldId = fieldId;
    record->rule = rule;
    record->before = before;
    record->after = after;
}

static BOOL OW_WILD_RUNTIME_COMPOSITION_CODE FieldDomain(
    u8 fieldNamespace,
    u8 fieldId,
    u8 *minimumOut,
    u8 *maximumOut,
    BOOL *numericOut)
{
    u8 kind;
    u8 maximum = 0xFF;
    int maskIndex;
    if (fieldNamespace == OW_WILD_RUNTIME_FIELD_STATE) {
        if (fieldId == 0 || fieldId > 27) return FALSE;
        kind = 4;
        maskIndex = 0;
    } else if (fieldNamespace == OW_WILD_RUNTIME_FIELD_CONTROLLER) {
        if (fieldId == 0 || fieldId > 7) return FALSE;
        kind = 5;
        maskIndex = 1;
    } else return FALSE;
    /* The shared resident Task-5 table/helper supplies maxima and exact enum
     * gaps; Task 6 supplies the nonzero movement-speed lower bound. */
    *minimumOut = fieldNamespace == OW_WILD_RUNTIME_FIELD_STATE
        && fieldId == 3 ? 1 : 0;
    *numericOut = (sOwbdNumericFieldMasks[maskIndex]
        & (1u << fieldId)) != 0;
    while (maximum != 0 && !OwbdStaticValueValid(kind, fieldId, maximum))
        maximum--;
    if (!OwbdStaticValueValid(kind, fieldId, maximum)) return FALSE;
    *maximumOut = maximum;
    return TRUE;
}

static OverworldWildRuntimeStatus OW_WILD_RUNTIME_COMPOSITION_CODE
ApplyModifierOperation(
    OverworldWildRuntimeEffectiveCache *cache,
    OverworldWildRuntimeProvenance *provenance,
    const OverworldWildRuntimeModifierWork *work,
    const OverworldWildRuntimeModifierOperation *operation)
{
    OverworldWildRuntimeFieldContribution *record = NULL;
    u8 minimum = 0, maximum = 0, before, after;
    BOOL numeric;
    signed long result;
    u8 *target;
    u8 fieldIndex;

    if (!FieldDomain(operation->fieldNamespace, operation->fieldId,
            &minimum, &maximum, &numeric))
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    if (operation->fieldNamespace == OW_WILD_RUNTIME_FIELD_STATE) {
        target = cache->stateValues;
        fieldIndex = operation->fieldId;
    } else {
        target = cache->controllerValues;
        fieldIndex = operation->fieldId - 1;
    }
    before = target[fieldIndex];
    if (operation->operatorKind < OW_WILD_RUNTIME_OPERATOR_SET
        || operation->operatorKind > OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST)
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    if (operation->operatorKind != OW_WILD_RUNTIME_OPERATOR_ADD
        && operation->operatorKind != OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST
        && operation->operatorKind != OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST
        && (operation->operand < 0 || operation->operand > 255)) {
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    }
    if (!numeric && operation->operatorKind != OW_WILD_RUNTIME_OPERATOR_SET)
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    /* Runtime relative operands are the frozen s16 ABI.  The shared Task-5
     * helper still owns field/operator/bound applicability, but receives a
     * neutral wire delta so its serialized s8/-32..32 limit cannot narrow a
     * runtime operation. */
    if (!OwbdModifierPayloadValid(
            operation->fieldNamespace == OW_WILD_RUNTIME_FIELD_STATE ? 4 : 5,
            operation->fieldId, operation->operatorKind,
            operation->operatorKind == OW_WILD_RUNTIME_OPERATOR_ADD
                    || operation->operatorKind
                        >= OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST
                ? 0 : (signed char)operation->operand,
            operation->bound))
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    /* The shared helper validates every maximum and enum gap.  Speed is the
     * sole supported field whose Task-6 minimum is nonzero. */
    if (operation->fieldNamespace == OW_WILD_RUNTIME_FIELD_STATE
        && operation->fieldId == 3
        && ((operation->operatorKind != OW_WILD_RUNTIME_OPERATOR_ADD
                && operation->operatorKind
                    < OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST
                && operation->operand == 0)
            || (operation->operatorKind
                    >= OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST
                && operation->bound == 0)))
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    switch (operation->operatorKind) {
    case OW_WILD_RUNTIME_OPERATOR_SET: result = operation->operand; break;
    case OW_WILD_RUNTIME_OPERATOR_ADD:
        result = (signed long)before + operation->operand; break;
    case OW_WILD_RUNTIME_OPERATOR_AT_LEAST:
        result = before > operation->operand ? before : operation->operand;
        break;
    case OW_WILD_RUNTIME_OPERATOR_AT_MOST:
        result = before < operation->operand ? before : operation->operand;
        break;
    case OW_WILD_RUNTIME_OPERATOR_ADD_AT_LEAST:
        result = (signed long)before + operation->operand;
        if (result < minimum) result = minimum;
        if (result > maximum) result = maximum;
        if (result < operation->bound) result = operation->bound;
        break;
    case OW_WILD_RUNTIME_OPERATOR_ADD_AT_MOST:
        result = (signed long)before + operation->operand;
        if (result < minimum) result = minimum;
        if (result > maximum) result = maximum;
        if (result > operation->bound) result = operation->bound;
        break;
    default: return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    }
    if (result < minimum) result = minimum;
    if (result > maximum) result = maximum;
    after = (u8)result;
    target[fieldIndex] = after;
    if (provenance->contributionCount
            < OW_WILD_RUNTIME_MAX_PROVENANCE_CONTRIBUTIONS) {
        record = &provenance->contributions[provenance->contributionCount++];
        record->definitionId = work->definition.stableId;
        record->ownerId = work->ownerId;
        record->instanceKey = work->instanceKey;
        record->operand = operation->operand;
        record->fieldNamespace = operation->fieldNamespace;
        record->fieldId = operation->fieldId;
        record->operatorKind = operation->operatorKind;
        record->bound = operation->bound;
        record->before = before;
        record->after = after;
    } else {
        provenance->flags |=
            OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_CONTRIBUTIONS;
    }
    if (operation->operatorKind == OW_WILD_RUNTIME_OPERATOR_SET) {
        u8 writerIndex = operation->fieldNamespace
                == OW_WILD_RUNTIME_FIELD_STATE
            ? operation->fieldId
            : (u8)(28 + operation->fieldId - 1);
        if (writerIndex < OW_WILD_RUNTIME_PROVENANCE_FIELD_COUNT)
            provenance->lastWriterDefinitionIds[writerIndex] =
                work->definition.stableId;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static BOOL OW_WILD_RUNTIME_COMPOSITION_CODE ModifierApplies(
    const OverworldWildRuntimeDefinition *definition,
    const OverworldWildRuntimeStaticCache *staticCache,
    const OverworldWildRuntimeEffectiveCache *effective);

static OverworldWildRuntimeStatus OW_WILD_RUNTIME_COMPOSITION_CODE
ApplyModifierWork(
    OverworldWildRuntimeEffectiveCache *effective,
    OverworldWildRuntimeProvenance *provenance,
    const OverworldWildRuntimeStaticCache *staticCache,
    const OverworldWildRuntimeModifierWork *work,
    const OverworldWildRuntimeStaticModifierContribution *staticContribution)
{
    const OverworldWildBehaviorDataBlobHeader *header;
    const OverworldWildModifierOperationRecord *records;
    OverworldWildBlobSection section;
    OverworldWildRuntimeModifierOperation operation;
    u16 recordIndex;
    u8 operationCount = 0;
    u8 operationIndex;
    BOOL applies = ModifierApplies(&work->definition, staticCache, effective);

    if (provenance->modifierCount < OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS) {
        OverworldWildRuntimeModifierProvenance *record =
            &provenance->modifiers[provenance->modifierCount++];
        record->definitionId = work->definition.stableId;
        record->ownerId = work->ownerId;
        record->instanceKey = work->instanceKey;
        record->channel = work->definition.channel;
        record->priority = work->definition.priority;
        record->applied = applies;
        record->skipReason = applies ? OW_WILD_RUNTIME_SKIP_NONE
                                     : OW_WILD_RUNTIME_SKIP_FILTER;
        if (staticContribution != NULL) {
            record->staticPriority = staticContribution->staticPriority;
            record->ruleStableId = staticContribution->ruleStableId;
            record->actionStableId = staticContribution->actionStableId;
            record->channel = 0;
        }
    } else {
        provenance->flags |= OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_MODIFIERS;
    }
    header = OverworldWildRuntime_AcquireInstalledTransitionCatalog();
    if (header == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    memcpy(&section, (void *)&header->modifierOperations, sizeof(section));
    records = (const void *)((const u8 *)header + section.offset);
    for (recordIndex = 0; recordIndex < section.count; recordIndex++) {
        if (records[recordIndex].definitionId == work->definition.stableId)
            operationCount++;
    }
    if (operationCount == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
    if (!applies) return OW_WILD_RUNTIME_STATUS_OK;
    for (operationIndex = 0; operationIndex < operationCount;
            operationIndex++) {
        const OverworldWildModifierOperationRecord *record = NULL;
        OverworldWildRuntimeStatus status;
        for (recordIndex = 0; recordIndex < section.count; recordIndex++) {
            if (records[recordIndex].definitionId
                        == work->definition.stableId
                    && records[recordIndex].order == operationIndex) {
                record = &records[recordIndex];
                break;
            }
        }
        if (record == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_MODIFIER;
        memcpy(&operation, (void *)&record->operand, sizeof(operation));
        status = ApplyModifierOperation(
            effective, provenance, work, &operation);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static OverworldWildRuntimeStatus OW_WILD_RUNTIME_COMPOSITION_CODE
ValidateEffectiveScalarDomains(
    const OverworldWildRuntimeEffectiveCache *cache)
{
    u8 fieldId;
    if (cache->controllerId == 0 || cache->nodeId == 0
        || cache->profileId == 0 || cache->semanticRole == 0
        || cache->semanticRole > 7 || cache->stateValues[0] > 11
        || cache->stateValues[0] == 9
        || cache->stateValues[9] > cache->stateValues[10]
        || cache->controllerValues[8] != 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    for (fieldId = 1; fieldId <= 27; fieldId++) {
        if (!OwbdStaticValueValid(4, fieldId, cache->stateValues[fieldId]))
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    }
    for (fieldId = 1; fieldId <= 7; fieldId++) {
        if (!OwbdStaticValueValid(5, fieldId,
                cache->controllerValues[fieldId - 1]))
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static BOOL OW_WILD_RUNTIME_COMPOSITION_CODE ModifierApplies(
    const OverworldWildRuntimeDefinition *definition,
    const OverworldWildRuntimeStaticCache *staticCache,
    const OverworldWildRuntimeEffectiveCache *effective)
{
    if (definition->immutableContextMask != 0xFFFFFFFFu
        && (staticCache->immutableContextMask & definition->immutableContextMask)
            != definition->immutableContextMask) return FALSE;
    if (definition->controllerId != 0
        && definition->controllerId != effective->controllerId) return FALSE;
    if (definition->effectiveProfileId != 0
        && definition->effectiveProfileId != effective->profileId) return FALSE;
    if (definition->applicabilitySemanticRole != 0
        && definition->applicabilitySemanticRole != effective->semanticRole)
        return FALSE;
    return TRUE;
}

static void OW_WILD_RUNTIME_COMPOSITION_CODE AddCandidateProvenance(
    OverworldWildRuntimeProvenance *provenance,
    const OverworldWildRuntimeCandidateProvenance *candidate)
{
    if (provenance->candidateCount
            < OW_WILD_RUNTIME_MAX_PROVENANCE_CANDIDATES) {
        provenance->candidates[provenance->candidateCount++] = *candidate;
    } else {
        provenance->flags |=
            OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_CANDIDATES;
    }
}

static int OW_WILD_RUNTIME_COMPOSITION_CODE CompareCandidateProvenance(
    const OverworldWildRuntimeCandidateProvenance *left,
    const OverworldWildRuntimeCandidateProvenance *right)
{
    if (left->channel != right->channel)
        return left->channel < right->channel ? -1 : 1;
    if (left->priority != right->priority)
        return left->priority < right->priority ? -1 : 1;
    if (left->definitionId != right->definitionId)
        return left->definitionId < right->definitionId ? -1 : 1;
    if (left->ownerId != right->ownerId)
        return left->ownerId < right->ownerId ? -1 : 1;
    if (left->instanceKey != right->instanceKey)
        return left->instanceKey < right->instanceKey ? -1 : 1;
    return 0;
}

static OverworldWildRuntimeStatus OW_WILD_RUNTIME_COMPOSITION_CODE
ComposeProspective(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeSlotSidecar *slot,
    const OverworldWildRuntimeStaticCache *resolvedStatic,
    const OverworldWildRuntimeLayer *layers,
    u8 layerCount,
    u32 prospectiveLayerGeneration,
    u32 prospectiveDataIncarnation,
    u32 prospectiveCacheIncarnation,
    OverworldWildRuntimeStaticCache *staticOut,
    OverworldWildRuntimeEffectiveCache *effectiveOut,
    OverworldWildRuntimeProvenance *provenanceOut,
    BOOL *effectiveChangedOut,
    OverworldWildRuntimeCompositionWorkspace *workspace)
{
    OverworldWildRuntimeDefinition winnerDefinition;
    OverworldWildRuntimeResolvedNode winnerNode;
    OverworldWildRuntimeResidentProvenance residentProvenance;
    OverworldWildRuntimeModifierWork *modifiers = workspace->modifiers;
    u8 modifierCount = 0;
    u8 i, j;
    BOOL hasWinner = FALSE;

    memset(effectiveOut, 0, sizeof(*effectiveOut));
    memset(provenanceOut, 0, sizeof(*provenanceOut));
    if (resolvedStatic != NULL) {
        OverworldWildRuntimeStatus staticStatus =
            OverworldWildRuntime_ValidateStaticCache(resolvedStatic,
                slot->staticContextGeneration);
        if (staticStatus != OW_WILD_RUNTIME_STATUS_OK) return staticStatus;
        if (slot->staticCache.valid
            && !BytesEqual(&slot->staticCache, resolvedStatic,
                sizeof(*resolvedStatic)))
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        if (staticOut != resolvedStatic) *staticOut = *resolvedStatic;
    } else {
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    }
    effectiveOut->controllerId = staticOut->controllerId;
    effectiveOut->nodeId = staticOut->baseNodeId;
    effectiveOut->profileId = staticOut->baseProfileId;
    effectiveOut->spawnPolicyId = staticOut->spawnPolicyId;
    effectiveOut->populationPolicyId = staticOut->populationPolicyId;
    effectiveOut->semanticRole = staticOut->baseSemanticRole;
    effectiveOut->dataIncarnation = prospectiveDataIncarnation;
    effectiveOut->cacheIncarnation = prospectiveCacheIncarnation;
    effectiveOut->catalogIdentity = staticOut->catalogIdentity;
    effectiveOut->staticContextIdentity = staticOut->staticContextIdentity;
    effectiveOut->staticSetHash = staticOut->staticSetHash;
    effectiveOut->staticContextGeneration =
        staticOut->staticContextGeneration;
    memcpy(effectiveOut->stateValues, staticOut->stateValues,
        sizeof(effectiveOut->stateValues));
    memcpy(effectiveOut->controllerValues, staticOut->controllerValues,
        sizeof(effectiveOut->controllerValues));
    {
        OverworldWildRuntimeCandidateProvenance base;
        memset(&base, 0, sizeof(base));
        base.nodeId = staticOut->baseNodeId;
        base.profileId = staticOut->baseProfileId;
        base.semanticRole = staticOut->baseSemanticRole;
        base.applicable = TRUE;
        base.isWinner = TRUE;
        AddCandidateProvenance(provenanceOut, &base);
    }
    memset(&winnerDefinition, 0, sizeof(winnerDefinition));
    memset(&winnerNode, 0, sizeof(winnerNode));
    for (i = 0; i < layerCount; i++) {
        OverworldWildRuntimeDefinition definition;
        OverworldWildRuntimeStatus status = CopyDefinition(
            layers[i].definitionId, &definition);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        if (definition.kind == OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE) {
            OverworldWildRuntimeResolvedNode node;
            OverworldWildRuntimeCandidateProvenance candidate;
            BOOL applicable = definition.immutableContextMask == 0xFFFFFFFFu
                || (staticOut->immutableContextMask
                        & definition.immutableContextMask)
                    == definition.immutableContextMask;
            memset(&candidate, 0, sizeof(candidate));
            candidate.entryGeneration = layers[i].entryGeneration;
            candidate.definitionId = definition.stableId;
            candidate.ownerId = layers[i].ownerId;
            candidate.instanceKey = layers[i].instanceKey;
            candidate.channel = definition.channel;
            candidate.priority = definition.priority;
            if (definition.controllerId != 0
                && definition.controllerId != staticOut->controllerId)
                applicable = FALSE;
            if (applicable)
                applicable = OverworldWildRuntime_CopyResolvedCachedNode(
                    staticOut, &definition, &node);
            candidate.applicable = applicable;
            candidate.skipReason = applicable
                ? OW_WILD_RUNTIME_SKIP_NONE
                : OW_WILD_RUNTIME_SKIP_NOT_APPLICABLE;
            if (applicable) {
                candidate.nodeId = node.nodeId;
                candidate.profileId = node.profileId;
                candidate.semanticRole = node.semanticRole;
                if (!hasWinner || CompareDefinitionKey(&winnerDefinition,
                        provenanceOut->winningOwnerId,
                        provenanceOut->winningInstanceKey,
                        &definition, layers[i].ownerId,
                        layers[i].instanceKey) < 0) {
                    for (j = 0; j < provenanceOut->candidateCount; j++)
                        provenanceOut->candidates[j].isWinner = FALSE;
                    candidate.isWinner = TRUE;
                    winnerDefinition = definition;
                    winnerNode = node;
                    provenanceOut->winningDefinitionId = definition.stableId;
                    provenanceOut->winningOwnerId = layers[i].ownerId;
                    provenanceOut->winningInstanceKey = layers[i].instanceKey;
                    hasWinner = TRUE;
                }
            }
            AddCandidateProvenance(provenanceOut, &candidate);
        } else if (definition.kind == OW_WILD_RUNTIME_DEFINITION_MODIFIER) {
            if (modifierCount >= OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT
                    + OW_WILD_RUNTIME_MAX_PROVENANCE_MODIFIERS)
                return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
            modifiers[modifierCount].definition = definition;
            modifiers[modifierCount].ownerId = layers[i].ownerId;
            modifiers[modifierCount].instanceKey = layers[i].instanceKey;
            modifierCount++;
        } else {
            return OW_WILD_RUNTIME_STATUS_INVALID_DEFINITION;
        }
    }
    if (hasWinner) {
        effectiveOut->nodeId = winnerNode.nodeId;
        effectiveOut->profileId = winnerNode.profileId;
        effectiveOut->semanticRole = winnerNode.semanticRole;
        memcpy(effectiveOut->stateValues, winnerNode.stateValues,
            sizeof(effectiveOut->stateValues));
    }
    {
        OverworldWildRuntimeStatus status =
            ValidateEffectiveScalarDomains(effectiveOut);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    for (i = 0; i < provenanceOut->candidateCount; i++) {
        if (provenanceOut->candidates[i].isWinner) {
            if (i != 0) {
                OverworldWildRuntimeCandidateProvenance value =
                    provenanceOut->candidates[0];
                provenanceOut->candidates[0] =
                    provenanceOut->candidates[i];
                provenanceOut->candidates[i] = value;
            }
            break;
        }
    }
    if (i == provenanceOut->candidateCount)
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    for (i = 0; i < provenanceOut->candidateCount; i++)
        provenanceOut->candidates[i].isWinner = i == 0;
    for (i = 2; i < provenanceOut->candidateCount; i++) {
        OverworldWildRuntimeCandidateProvenance value =
            provenanceOut->candidates[i];
        u8 cursor = i;
        while (cursor > 1 && CompareCandidateProvenance(&value,
                &provenanceOut->candidates[cursor - 1]) < 0) {
            provenanceOut->candidates[cursor] =
                provenanceOut->candidates[cursor - 1];
            cursor--;
        }
        provenanceOut->candidates[cursor] = value;
    }
    for (i = 0; i < staticOut->staticModifierCount; i++) {
        const OverworldWildRuntimeStaticModifierContribution *contribution =
            &staticOut->staticModifiers[i];
        OverworldWildRuntimeDefinition definition;
        OverworldWildRuntimeModifierWork work;
        OverworldWildRuntimeStatus status;
        if (contribution->ruleStableId == 0
            || contribution->actionStableId == 0)
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        if (i != 0) {
            const OverworldWildRuntimeStaticModifierContribution *previous =
                &staticOut->staticModifiers[i - 1];
            if (contribution->staticPriority < previous->staticPriority
                || (contribution->staticPriority == previous->staticPriority
                    && (contribution->ruleStableId < previous->ruleStableId
                        || (contribution->ruleStableId == previous->ruleStableId
                            && (contribution->actionStableId
                                    < previous->actionStableId
                                || (contribution->actionStableId
                                        == previous->actionStableId
                                    && contribution->targetNodeId
                                        <= previous->targetNodeId))))))
                return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        }
        if (contribution->targetNodeId != 0
            && contribution->targetNodeId != effectiveOut->nodeId)
            continue;
        if (contribution->modifierDefinitionId == 0) {
            OverworldWildRuntimeModifierProvenance *modifier;
            OverworldWildRuntimeFieldContribution *field;
            u8 writerIndex;
            modifier = &provenanceOut->modifiers[
                provenanceOut->modifierCount++];
            memcpy(&modifier->staticPriority,
                (void *)&contribution->staticPriority,
                sizeof(contribution->staticPriority)
                    + sizeof(contribution->ruleStableId)
                    + sizeof(contribution->actionStableId));
            modifier->applied = TRUE;
            field = &provenanceOut->contributions[
                provenanceOut->contributionCount++];
            field->definitionId = contribution->actionStableId;
            memcpy(&field->operand, (void *)&contribution->operand,
                sizeof(contribution->operand)
                    + sizeof(contribution->fieldNamespace)
                    + sizeof(contribution->fieldId)
                    + sizeof(contribution->operatorKind)
                    + sizeof(contribution->bound)
                    + sizeof(contribution->before)
                    + sizeof(contribution->after));
            if (contribution->operatorKind == OW_WILD_RUNTIME_OPERATOR_SET) {
                writerIndex = (u8)(contribution->fieldId
                    + 27 * (contribution->fieldNamespace - 1));
                provenanceOut->lastWriterDefinitionIds[writerIndex] =
                    contribution->actionStableId;
            }
            continue;
        }
        status = CopyDefinition(
            contribution->modifierDefinitionId, &definition);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
        if (definition.kind != OW_WILD_RUNTIME_DEFINITION_MODIFIER)
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        work.definition = definition;
        work.ownerId = 0;
        work.instanceKey = 0;
        status = ApplyModifierWork(effectiveOut, provenanceOut, staticOut,
            &work, contribution);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    if (staticOut->reserved)
        provenanceOut->flags |= OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_MODIFIERS
            | OW_WILD_RUNTIME_PROVENANCE_TRUNCATED_CONTRIBUTIONS;
    for (i = 1; i < modifierCount; i++) {
        OverworldWildRuntimeModifierWork value = modifiers[i];
        u8 cursor = i;
        while (cursor != 0 && CompareDefinitionKey(&value.definition,
                value.ownerId, value.instanceKey,
                &modifiers[cursor - 1].definition,
                modifiers[cursor - 1].ownerId,
                modifiers[cursor - 1].instanceKey) < 0) {
            modifiers[cursor] = modifiers[cursor - 1];
            cursor--;
        }
        modifiers[cursor] = value;
    }
    for (i = 0; i < modifierCount; i++) {
        OverworldWildRuntimeStatus status = ApplyModifierWork(
            effectiveOut, provenanceOut, staticOut, &modifiers[i], NULL);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    if (effectiveOut->stateValues[10] < effectiveOut->stateValues[9]) {
        u8 before = effectiveOut->stateValues[10];
        effectiveOut->stateValues[10] = effectiveOut->stateValues[9];
        RecordNormalization(provenanceOut, OW_WILD_RUNTIME_FIELD_STATE, 10,
            OW_WILD_RUNTIME_NORMALIZE_HOP_MAX, before,
            effectiveOut->stateValues[10]);
    }
    if (effectiveOut->stateValues[7] == effectiveOut->stateValues[6]
        && effectiveOut->stateValues[7] != 15) {
        u8 before = effectiveOut->stateValues[7];
        effectiveOut->stateValues[7] = 15;
        RecordNormalization(provenanceOut, OW_WILD_RUNTIME_FIELD_STATE, 7,
            OW_WILD_RUNTIME_NORMALIZE_SECONDARY_TILE, before, 15);
    }
    if ((effectiveOut->controllerValues[8] & 1)
        && effectiveOut->controllerValues[6] == 0) {
        effectiveOut->controllerValues[6] = 1;
        RecordNormalization(provenanceOut,
            OW_WILD_RUNTIME_FIELD_CONTROLLER, 7,
            OW_WILD_RUNTIME_NORMALIZE_STAMINA, 0, 1);
    }
    if (effectiveOut->semanticRole == OW_WILD_RUNTIME_ROLE_TIRED
        && effectiveOut->controllerValues[7] == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    if ((effectiveOut->stateValues[1] == 2
            && effectiveOut->stateValues[12] == 0)
        || (effectiveOut->stateValues[1] == 5
            && (effectiveOut->stateValues[16] == 0
                || effectiveOut->stateValues[17] == 0))
        || (effectiveOut->stateValues[1] == 6
            && effectiveOut->stateValues[14] == 0))
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    effectiveOut->primitives[0] = effectiveOut->stateValues[1];
    effectiveOut->primitives[1] = effectiveOut->stateValues[2];
    effectiveOut->primitives[2] = effectiveOut->semanticRole == 4
        ? 2 : (effectiveOut->semanticRole == OW_WILD_RUNTIME_ROLE_TIRED
            ? 1 : 0);
    effectiveOut->primitives[3] = effectiveOut->stateValues[3];
    effectiveOut->primitives[4] = effectiveOut->stateValues[4];
    if (effectiveOut->stateValues[1] != 0
        && effectiveOut->stateValues[0] != 9)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_CAN_MOVE;
    if (effectiveOut->stateValues[26] != 0)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_BATTLE_ON_CONTACT;
    if (effectiveOut->stateValues[12] != 0)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_HOP;
    if (effectiveOut->stateValues[14] != 0)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_TELEPORT;
    if (effectiveOut->stateValues[17] != 0)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_RAM;
    if (effectiveOut->stateValues[5] != 0)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_JUMP_LEDGES;
    if (effectiveOut->stateValues[1] != 0)
        effectiveOut->capabilityMask |= OW_WILD_RUNTIME_CAP_FRAME_WORK;
    effectiveOut->flags = OW_WILD_RUNTIME_CACHE_VALID;
    effectiveOut->effectiveHash = EffectiveHash(effectiveOut);
    *effectiveChangedOut = !(slot->effectiveCache.flags
            & OW_WILD_RUNTIME_CACHE_VALID)
        || slot->effectiveCache.effectiveHash != effectiveOut->effectiveHash
        || slot->effectiveCache.capabilityMask != effectiveOut->capabilityMask
        || !BytesEqual(&slot->effectiveCache.controllerId,
            &effectiveOut->controllerId,
            sizeof(*effectiveOut)
                - offsetof(OverworldWildRuntimeEffectiveCache, controllerId));
    effectiveOut->layerGeneration = prospectiveLayerGeneration;
    effectiveOut->effectiveGeneration = *effectiveChangedOut
        && (slot->effectiveCache.flags & OW_WILD_RUNTIME_CACHE_VALID)
        ? OverworldWildRuntime_AdvanceNonzeroGeneration(
            slot->effectiveGeneration)
        : slot->effectiveGeneration;
    if ((*effectiveChangedOut && slot->effectiveGeneration == 0xFFFFFFFFu)
        || slot->provenance.freshnessGeneration == 0xFFFFFFFFu)
        effectiveOut->cacheIncarnation =
            OverworldWildRuntime_AdvanceNonzeroGeneration(
                effectiveOut->cacheIncarnation);
    provenanceOut->freshnessGeneration =
        OverworldWildRuntime_AdvanceNonzeroGeneration(
            slot->provenance.freshnessGeneration);
    provenanceOut->dataIncarnation = effectiveOut->dataIncarnation;
    provenanceOut->cacheIncarnation = effectiveOut->cacheIncarnation;
    provenanceOut->catalogIdentity = effectiveOut->catalogIdentity;
    provenanceOut->staticContextIdentity =
        effectiveOut->staticContextIdentity;
    provenanceOut->staticSetHash = effectiveOut->staticSetHash;
    provenanceOut->staticContextGeneration =
        effectiveOut->staticContextGeneration;
    provenanceOut->layerGeneration = prospectiveLayerGeneration;
    provenanceOut->effectiveGeneration = effectiveOut->effectiveGeneration;
    provenanceOut->effectiveHash = effectiveOut->effectiveHash;
    provenanceOut->flags |= OW_WILD_RUNTIME_PROVENANCE_VALID;
    StoreResidentProvenance(&residentProvenance, provenanceOut);
    residentProvenance.provenanceHash =
        ResidentProvenanceHash(&residentProvenance);
    provenanceOut->provenanceHash = residentProvenance.provenanceHash;
    effectiveOut->provenanceHash = residentProvenance.provenanceHash;
    effectiveOut->cacheIdentity = CacheIdentity(
        runtime, slot, effectiveOut, provenanceOut->freshnessGeneration,
        prospectiveDataIncarnation != runtime->dataIncarnation
            ? OverworldWildRuntime_AdvanceNonzeroGeneration(
                sOverworldWildRuntimeLayerService.privateRuntimeIdentity)
            : sOverworldWildRuntimeLayerService.privateRuntimeIdentity);
    provenanceOut->cacheIdentity = effectiveOut->cacheIdentity;
    return OW_WILD_RUNTIME_STATUS_OK;
}

void OverworldWildRuntime_HandleSlotGenerationWrap(
    OverworldWildBehaviorStackRuntime *runtime,
    int targetSlotIndex)
{
    OverworldWildRuntimeRekeyStage stage;
    OverworldWildRuntimeSlotSidecar *targetSlot;
    u32 slotGeneration;
    u32 cacheIncarnation;
    u8 slotIndex;
    if (runtime == NULL || targetSlotIndex < 0
        || targetSlotIndex >= OW_WILD_MAX_SPAWNS) return;
    targetSlot = &runtime->slots[targetSlotIndex];
    slotGeneration = targetSlot->slotGeneration + 1;
    cacheIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        targetSlot->cacheIncarnation);
    if (slotGeneration != 0) {
        InitializeInvalidatedSlot(
            targetSlot, slotGeneration, cacheIncarnation);
        return;
    }
    if (runtime->handleEpoch == 0xFFFFFFFFu) {
        RestartRuntime(runtime, TRUE);
        return;
    }
    if (!StageSlotsForRekey(runtime, &stage)) {
        RestartRuntime(runtime, FALSE);
        return;
    }
    runtime->handleEpoch++;
    runtime->dataIncarnation = OverworldWildRuntime_AdvanceNonzeroGeneration(
        runtime->dataIncarnation);
    RotatePrivateIdentity(runtime);
    for (slotIndex = 0; slotIndex < OW_WILD_MAX_SPAWNS; slotIndex++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[slotIndex];
        if (slotIndex == (u8)targetSlotIndex) {
            InitializeInvalidatedSlot(slot, 1,
                OverworldWildRuntime_AdvanceNonzeroGeneration(
                    slot->cacheIncarnation));
        } else {
            slot->cacheIncarnation =
                OverworldWildRuntime_AdvanceNonzeroGeneration(
                    slot->cacheIncarnation);
            RekeySlot(slot, stage.layerCounts[slotIndex]);
            slot->layerGeneration = stage.layerGenerations[slotIndex];
            memset(&slot->effectiveCache, 0, sizeof(slot->effectiveCache));
            memset(&slot->provenance, 0, sizeof(slot->provenance));
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

static OverworldWildRuntimeStatus ApplyDeltaCoreWithWorkspace(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    const OverworldWildRuntimeDeltaOperation *operations,
    u8 operationCount,
    OverworldWildRuntimeStackDeltaResult *result,
    BOOL preflightOnly,
    BOOL internalBoundaryPolicy,
    OverworldWildRuntimeCompositionWorkspace *workspace)
{
    OverworldWildRuntimeDeltaScratch *scratch = &workspace->delta;
    OverworldWildRuntimeTimer prospectiveTimers[
        OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT];
    OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    u32 nextEntryGenerationAfter;
    u32 nextTimerGenerationAfter;
    u8 i, j, survivors, mutated = FALSE, rekey = FALSE;
    u8 newLayerMask = 0;
    u8 timedAdditionCount = 0;
    BOOL effectiveChanged = FALSE;
    BOOL needsApplicability = FALSE;
#define prospectiveStatic workspace->prospectiveStatic
#define prospectiveEffective workspace->prospectiveEffective
#define prospectiveProvenance workspace->prospectiveProvenance
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
        status = ValidateOperation(operation, internalBoundaryPolicy);
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
    status = OverworldWildRuntime_ResolveRetainedStaticCache(
        &slot->staticCache, slot->staticContextGeneration,
        &prospectiveStatic);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
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
#ifdef OW_WILD_RUNTIME_HOST_TEST
            status = CheckGeneratedTranslation(definition, applicability);
            if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
#endif
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
    for (i = 0; i < scratch->finalCount; i++) {
        OverworldWildRuntimeTimerDefinition timerDefinition;
        if (!scratch->finalLayers[i].reserved) continue;
        newLayerMask |= (u8)(1u << i);
        if (!OverworldWildRuntime_ResolveInstalledTimerDefinition(
                scratch->finalLayers[i].definitionId, &prospectiveStatic,
                &timerDefinition))
            return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA);
        if (timerDefinition.clock != OW_WILD_RUNTIME_TIMER_CLOCK_NONE)
            timedAdditionCount++;
    }
    if ((scratch->additionCount
            && slot->nextEntryGeneration
                > 0xFFFFFFFFu - scratch->additionCount)
        || (timedAdditionCount
            && slot->nextTimerGeneration
                > 0xFFFFFFFFu - timedAdditionCount)) {
        if (runtime->handleEpoch != 0xFFFFFFFFu
            && !StageSlotsForRekey(runtime, &workspace->rekey)) {
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
    nextEntryGenerationAfter = slot->nextEntryGeneration;
    nextTimerGenerationAfter = slot->nextTimerGeneration;
    memset(prospectiveTimers, 0, sizeof(prospectiveTimers));
    if (rekey) {
        for (i = 0; i < scratch->finalCount; i++) {
            scratch->finalLayers[i].entryGeneration = (u32)i + 1;
            scratch->finalLayers[i].reserved = 0;
        }
        nextEntryGenerationAfter = (u32)scratch->finalCount + 1;
    } else {
        for (i = 0; i < scratch->finalCount; i++) {
            if (scratch->finalLayers[i].reserved) {
                scratch->finalLayers[i].entryGeneration =
                    nextEntryGenerationAfter++;
                scratch->finalLayers[i].reserved = 0;
            }
        }
    }
    for (i = 0; i < scratch->finalCount; i++) {
        OverworldWildRuntimeLayer *layer = &scratch->finalLayers[i];
        OverworldWildRuntimeTimer *timer = &prospectiveTimers[i];
        if (newLayerMask & (1u << i)) {
            OverworldWildRuntimeTimerDefinition timerDefinition;
            if (!OverworldWildRuntime_ResolveInstalledTimerDefinition(
                    layer->definitionId, &prospectiveStatic,
                    &timerDefinition))
                return Fail(result,
                    OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA);
            if (timerDefinition.clock
                    != OW_WILD_RUNTIME_TIMER_CLOCK_NONE) {
                timer->entryGeneration = layer->entryGeneration;
                timer->timerGeneration = rekey
                    ? 1 : nextTimerGenerationAfter++;
                timer->ownerId = layer->ownerId;
                timer->instanceKey = layer->instanceKey;
                timer->definitionId = layer->definitionId;
                timer->recoveryTransitionId =
                    timerDefinition.recoveryTransitionId;
                timer->remainingTicks = timerDefinition.duration;
                timer->armedDuration = timerDefinition.duration;
                timer->clock = timerDefinition.clock;
                timer->hiddenPolicy = timerDefinition.hiddenPolicy;
                timer->recoveryPolicy = timerDefinition.recoveryPolicy;
                timer->flags = OW_WILD_RUNTIME_TIMER_VALID;
                if (timer->remainingTicks == 0)
                    timer->flags |= OW_WILD_RUNTIME_TIMER_ZERO_PENDING;
            }
        } else {
            int oldIndex = FindLayer(slot, layer->ownerId,
                layer->instanceKey);
            if (oldIndex < 0)
                return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE);
            *timer = slot->timerBank.timers[oldIndex];
        }
    }
    if (rekey) {
        nextTimerGenerationAfter = 1;
        for (i = 0; i < scratch->finalCount; i++) {
            OverworldWildRuntimeTimer *timer = &prospectiveTimers[i];
            if (!(timer->flags & OW_WILD_RUNTIME_TIMER_VALID)) continue;
            timer->entryGeneration = scratch->finalLayers[i].entryGeneration;
            timer->timerGeneration = nextTimerGenerationAfter++;
        }
    }
#ifdef OW_WILD_RUNTIME_HOST_TEST
    if (needsApplicability
        && !OverworldWildRuntime_ApplicabilityMatchesStaticCache(
            applicability, &prospectiveStatic))
        return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA);
#endif
    status = ComposeProspective(
        runtime, slot, &prospectiveStatic,
        scratch->finalLayers,
        scratch->finalCount,
        OverworldWildRuntime_AdvanceNonzeroGeneration(slot->layerGeneration),
        rekey
            ? OverworldWildRuntime_AdvanceNonzeroGeneration(
                runtime->dataIncarnation)
            : runtime->dataIncarnation,
        (rekey || slot->layerGeneration == 0xFFFFFFFFu)
            ? OverworldWildRuntime_AdvanceNonzeroGeneration(
                slot->cacheIncarnation)
            : slot->cacheIncarnation,
        &prospectiveStatic, &prospectiveEffective, &prospectiveProvenance,
        &effectiveChanged, workspace);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return Fail(result, status);
    if (!slot->presentationGate)
        ExpireHiddenTimers(prospectiveTimers, scratch->finalCount,
            prospectiveProvenance.winningOwnerId,
            prospectiveProvenance.winningInstanceKey);
    if (preflightOnly)
        return OW_WILD_RUNTIME_STATUS_OK;
    if (rekey) {
        runtime->handleEpoch++;
        runtime->dataIncarnation = prospectiveEffective.dataIncarnation;
        RotatePrivateIdentity(runtime);
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            if (i == slotIndex) continue;
            runtime->slots[i].cacheIncarnation =
                OverworldWildRuntime_AdvanceNonzeroGeneration(
                    runtime->slots[i].cacheIncarnation);
            RekeySlot(&runtime->slots[i], workspace->rekey.layerCounts[i]);
            runtime->slots[i].layerGeneration =
                workspace->rekey.layerGenerations[i];
            memset(&runtime->slots[i].effectiveCache, 0,
                sizeof(runtime->slots[i].effectiveCache));
            memset(&runtime->slots[i].provenance, 0,
                sizeof(runtime->slots[i].provenance));
        }
    }
    slot->nextEntryGeneration = nextEntryGenerationAfter;
    slot->nextTimerGeneration = nextTimerGenerationAfter;
    WriteLayers(slot, scratch->finalLayers, scratch->finalCount);
    WriteTimers(slot, prospectiveTimers, scratch->finalCount);
    slot->layerGeneration = OverworldWildRuntime_AdvanceNonzeroGeneration(
        slot->layerGeneration);
    slot->staticCache = prospectiveStatic;
    slot->cacheIncarnation = prospectiveEffective.cacheIncarnation;
    slot->effectiveCache = prospectiveEffective;
    StoreResidentProvenance(&slot->provenance, &prospectiveProvenance);
    if (effectiveChanged)
        slot->effectiveGeneration = prospectiveEffective.effectiveGeneration;
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
#undef prospectiveProvenance
#undef prospectiveEffective
#undef prospectiveStatic
}

static OverworldWildRuntimeStatus ApplyDeltaCore(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    const OverworldWildRuntimeDeltaOperation *operations,
    u8 operationCount,
    OverworldWildRuntimeStackDeltaResult *result,
    BOOL preflightOnly,
    BOOL internalBoundaryPolicy)
{
    OverworldWildRuntimeCompositionWorkspace *workspace;
    OverworldWildRuntimeStatus status;

    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitResult(runtime, slotIndex, result);
    if (runtime == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || sOverworldWildRuntimeLayerService.privateRuntimeIdentity == 0
        || runtime->handleEpoch == 0
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || runtime->reserved[0] || runtime->reserved[1] || runtime->reserved[2]
        || operations == NULL || applicability == NULL
        || slotIndex >= OW_WILD_MAX_SPAWNS || expectedSlotGeneration == 0
        || operationCount > OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS)
        return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE);
    workspace = AcquireCompositionWorkspace(runtime);
    if (workspace == NULL)
        return Fail(result, OW_WILD_RUNTIME_STATUS_DATA_BUSY);
    status = ApplyDeltaCoreWithWorkspace(runtime, slotIndex,
        expectedSlotGeneration, applicability, operations, operationCount,
        result, preflightOnly, internalBoundaryPolicy, workspace);
    ReleaseCompositionWorkspace(runtime);
    return status;
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
        request->operations, request->operationCount, result, FALSE, FALSE);
}

OverworldWildRuntimeStatus OverworldWildRuntime_ApplyStackDeltaCompact(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeStackDeltaRequest *request,
    BOOL *mutatedOut)
{
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeStatus status;
    if (mutatedOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    *mutatedOut = FALSE;
    status = OverworldWildRuntime_ApplyStackDelta(runtime, request, &result);
    *mutatedOut = result.mutated;
    return status;
}

static OverworldWildRuntimeStatus OneOperation(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeApplicabilityInput *applicability,
    const OverworldWildRuntimeDeltaOperation *operation,
    OverworldWildRuntimeStackDeltaResult *result,
    BOOL preflightOnly,
    BOOL internalBoundaryPolicy)
{
    OverworldWildRuntimeApplicabilityInput copiedApplicability;
    if (applicability != NULL)
        copiedApplicability = *applicability;
    else
        memset(&copiedApplicability, 0, sizeof(copiedApplicability));
    return ApplyDeltaCore(runtime, slotIndex, expectedSlotGeneration,
        &copiedApplicability, operation, 1, result,
        preflightOnly, internalBoundaryPolicy);
}

OverworldWildRuntimeStatus OverworldWildRuntime_RemoveBoundaryPolicySlotPhase(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u8 boundary,
    BOOL preflightOnly)
{
    OverworldWildRuntimeDeltaOperation operation;
    OverworldWildRuntimeStackDeltaResult result;
    OverworldWildRuntimeStatus status;

    memset(&operation, 0, sizeof(operation));
    operation.operationId = 1;
    operation.kind = OW_WILD_RUNTIME_DELTA_REMOVE_POLICY;
    operation.payload.policy.boundary = boundary;
    status = OneOperation(runtime, slotIndex, expectedSlotGeneration,
        NULL, &operation, &result, preflightOnly, TRUE);
    return status;
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
        applicability, &operation, result, FALSE, FALSE);
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
        applicability, &operation, result, FALSE, FALSE);
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
        NULL, &operation, result, FALSE, FALSE);
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
        NULL, &operation, result, FALSE, FALSE);
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
        NULL, &operation, result, FALSE, FALSE);
}

OverworldWildRuntimeStatus OverworldWildRuntime_PrimeEffectiveCache(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeStaticContext *staticContext,
    const OverworldWildRuntimeApplicabilityInput *applicability)
{
    OverworldWildRuntimeCompositionWorkspace *workspace;
    OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    BOOL changed;
    u8 i;

    if (runtime == NULL || staticContext == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || sOverworldWildRuntimeLayerService.privateRuntimeIdentity == 0
        || runtime->handleEpoch == 0
        || runtime->reserved[0] || runtime->reserved[1] || runtime->reserved[2]
        || slotIndex >= OW_WILD_MAX_SPAWNS || expectedSlotGeneration == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    slot = &runtime->slots[slotIndex];
    if (slot->lifecycleState != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
        return OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT;
    if (slot->slotGeneration != expectedSlotGeneration)
        return OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH;
    status = ValidateBank(slot);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    if (applicability != NULL) {
        status = ValidateApplicabilityShape(applicability);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    workspace = AcquireCompositionWorkspace(runtime);
    if (workspace == NULL) return OW_WILD_RUNTIME_STATUS_DATA_BUSY;
    if (!OverworldWildRuntime_CopyInstalledStaticCache(
            staticContext, applicability, slot->staticContextGeneration,
            &workspace->prospectiveStatic)) {
        status = OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        goto release_workspace;
    }
    if (slot->effectiveCache.flags & OW_WILD_RUNTIME_CACHE_VALID) {
        status = ValidateCacheKey(runtime, slot);
        if (status != OW_WILD_RUNTIME_STATUS_OK) goto release_workspace;
        status = BytesEqual(&slot->staticCache,
                &workspace->prospectiveStatic,
                sizeof(workspace->prospectiveStatic))
            ? OW_WILD_RUNTIME_STATUS_IDEMPOTENT
            : OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        goto release_workspace;
    }
    for (i = 0; i < slot->activeLayerCount; i++)
        ReadLayer(slot, i, &workspace->delta.finalLayers[i]);
    status = ComposeProspective(
        runtime, slot, &workspace->prospectiveStatic,
        workspace->delta.finalLayers,
        slot->activeLayerCount, slot->layerGeneration,
        runtime->dataIncarnation, slot->cacheIncarnation,
        &workspace->prospectiveStatic, &workspace->prospectiveEffective,
        &workspace->prospectiveProvenance, &changed, workspace);
    if (status == OW_WILD_RUNTIME_STATUS_OK) {
        slot->staticCache = workspace->prospectiveStatic;
        slot->effectiveCache = workspace->prospectiveEffective;
        StoreResidentProvenance(&slot->provenance,
            &workspace->prospectiveProvenance);
    }
release_workspace:
    ReleaseCompositionWorkspace(runtime);
    return status;
}


static OverworldWildRuntimeStatus ValidateCacheQuery(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    if (runtime == NULL
        || runtime != sOverworldWildRuntimeLayerService.boundRuntime
        || runtime->lifetimeState != OW_WILD_RUNTIME_LIFETIME_ACTIVE
        || sOverworldWildRuntimeLayerService.privateRuntimeIdentity == 0
        || slotIndex >= OW_WILD_MAX_SPAWNS || expectedSlotGeneration == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    slot = &runtime->slots[slotIndex];
    if (slot->lifecycleState != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
        return OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT;
    if (slot->slotGeneration != expectedSlotGeneration)
        return OW_WILD_RUNTIME_STATUS_SLOT_GENERATION_MISMATCH;
    if (!(slot->effectiveCache.flags & OW_WILD_RUNTIME_CACHE_VALID))
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    return ValidateCacheKey(runtime, slot);
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetEffectiveCache(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeEffectiveCache *cacheOut)
{
    OverworldWildRuntimeStatus status;
    if (cacheOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = ValidateCacheQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) {
        memset(cacheOut, 0, sizeof(*cacheOut));
        return status;
    }
    *cacheOut = runtime->slots[slotIndex].effectiveCache;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetCapabilityMask(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    u32 *capabilityMaskOut)
{
    OverworldWildRuntimeStatus status;
    if (capabilityMaskOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = ValidateCacheQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) {
        *capabilityMaskOut = 0;
        return status;
    }
    *capabilityMaskOut =
        runtime->slots[slotIndex].effectiveCache.capabilityMask;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetProvenance(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    OverworldWildRuntimeProvenance *provenanceOut)
{
    OverworldWildBehaviorStackRuntime *mutableRuntime;
    OverworldWildRuntimeCompositionWorkspace *workspace;
    const OverworldWildRuntimeSlotSidecar *slot;
    const OverworldWildRuntimeResidentProvenance *resident;
    OverworldWildRuntimeStatus status;
    BOOL changed;
    u8 count;
    u8 index;
    if (provenanceOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = ValidateCacheQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) {
        memset(provenanceOut, 0, sizeof(*provenanceOut));
        return status;
    }
    slot = &runtime->slots[slotIndex];
    count = slot->activeLayerCount;
    if (count > OW_WILD_MAX_RUNTIME_LAYERS_PER_SLOT) {
        memset(provenanceOut, 0, sizeof(*provenanceOut));
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    }
    /* Scratch does not form part of the logical query state and is cleared
     * before returning; the guard makes nested queries fail deterministically. */
    mutableRuntime = (OverworldWildBehaviorStackRuntime *)runtime;
    workspace = AcquireCompositionWorkspace(mutableRuntime);
    if (workspace == NULL) {
        memset(provenanceOut, 0, sizeof(*provenanceOut));
        return OW_WILD_RUNTIME_STATUS_DATA_BUSY;
    }
    for (index = 0; index < count; index++)
        ReadLayer(slot, index, &workspace->delta.finalLayers[index]);
    status = ComposeProspective(runtime, slot, &slot->staticCache,
        workspace->delta.finalLayers,
        count, slot->layerGeneration,
        runtime->dataIncarnation, slot->cacheIncarnation,
        &workspace->prospectiveStatic, &workspace->prospectiveEffective,
        provenanceOut, &changed, workspace);
    if (status != OW_WILD_RUNTIME_STATUS_OK) {
        memset(provenanceOut, 0, sizeof(*provenanceOut));
        goto release_workspace;
    }
    resident = &slot->provenance;
    if (changed
        || !BytesEqual(&provenanceOut->dataIncarnation,
            &resident->dataIncarnation,
            offsetof(OverworldWildRuntimeProvenance, candidateCount)
                - offsetof(OverworldWildRuntimeProvenance,
                    dataIncarnation))
        || provenanceOut->candidateCount != resident->candidateCount) {
        memset(provenanceOut, 0, sizeof(*provenanceOut));
        status = OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
        goto release_workspace;
    }
    memcpy(provenanceOut, (void *)resident,
        offsetof(OverworldWildRuntimeProvenance, candidateCount));
    status = OW_WILD_RUNTIME_STATUS_OK;
release_workspace:
    ReleaseCompositionWorkspace(mutableRuntime);
    return status;
}

OverworldWildRuntimeStatus OverworldWildRuntime_ValidateTimerQueryInternal(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration);
#define ValidateTimerQuery OverworldWildRuntime_ValidateTimerQueryInternal

#ifndef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
u8 OverworldWildRuntime_GetTimerCount(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    u8 i, count = 0;
    if (ValidateTimerQuery(runtime, slotIndex, expectedSlotGeneration)
            != OW_WILD_RUNTIME_STATUS_OK) return 0;
    slot = &runtime->slots[slotIndex];
    for (i = 0; i < slot->activeLayerCount; i++)
        if (slot->timerBank.timers[i].flags & OW_WILD_RUNTIME_TIMER_VALID)
            count++;
    return count;
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetTimerByIndex(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 timerIndex,
    OverworldWildRuntimeTimer *timerOut)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    u8 i, count = 0;
    if (timerOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(timerOut, 0, sizeof(*timerOut));
    status = ValidateTimerQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    slot = &runtime->slots[slotIndex];
    for (i = 0; i < slot->activeLayerCount; i++) {
        if (!(slot->timerBank.timers[i].flags
                & OW_WILD_RUNTIME_TIMER_VALID)) continue;
        if (count++ == timerIndex) {
            *timerOut = slot->timerBank.timers[i];
            return OW_WILD_RUNTIME_STATUS_OK;
        }
    }
    return OW_WILD_RUNTIME_STATUS_NOT_FOUND;
}
#endif

#ifndef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static u8 CountPendingTimerExpiries(
    const OverworldWildRuntimeSlotSidecar *slot)
{
    u8 i, count = 0;
    for (i = 0; i < slot->activeLayerCount; i++)
        if ((slot->timerBank.timers[i].flags
                & (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
            == (OW_WILD_RUNTIME_TIMER_VALID
                | OW_WILD_RUNTIME_TIMER_ZERO_PENDING)) count++;
    return count;
}
#endif

OverworldWildRuntimeStatus OverworldWildRuntime_ValidateTimerQueryInternal(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration)
{
    OverworldWildRuntimeStatus status = ValidateCacheQuery(runtime,
        slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    status = ValidateBank(&runtime->slots[slotIndex]);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    return ValidateStoredSlotSemantics(&runtime->slots[slotIndex]);
}

static BOOL ExpireHiddenTimer(
    OverworldWildRuntimeTimer *timer,
    u16 winningOwnerId,
    u16 winningInstanceKey)
{
    if (!(timer->flags & OW_WILD_RUNTIME_TIMER_VALID)
        || timer->hiddenPolicy
            != OW_WILD_RUNTIME_HIDDEN_TIMER_EXPIRE_ON_HIDE
        || (winningOwnerId == timer->ownerId
            && winningInstanceKey == timer->instanceKey)
        || (timer->flags & OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
        return FALSE;
    timer->remainingTicks = 0;
    timer->flags |= OW_WILD_RUNTIME_TIMER_ZERO_PENDING;
    return TRUE;
}

static void ExpireHiddenTimers(
    OverworldWildRuntimeTimer *timers,
    u8 count,
    u16 winningOwnerId,
    u16 winningInstanceKey)
{
    u8 i;
    for (i = 0; i < count; i++)
        ExpireHiddenTimer(&timers[i], winningOwnerId, winningInstanceKey);
}

#ifndef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
static void InitTimerTickResult(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    OverworldWildRuntimeTimerTickResult *result)
{
    memset(result, 0, sizeof(*result));
    if (runtime == NULL || slotIndex >= OW_WILD_MAX_SPAWNS) return;
    result->runtimeEpoch = runtime->handleEpoch;
    result->slotGeneration = runtime->slots[slotIndex].slotGeneration;
    result->layerGenerationBefore = runtime->slots[slotIndex].layerGeneration;
    result->layerGenerationAfter = runtime->slots[slotIndex].layerGeneration;
    result->effectiveGenerationBefore =
        runtime->slots[slotIndex].effectiveGeneration;
    result->effectiveGenerationAfter =
        runtime->slots[slotIndex].effectiveGeneration;
}
#endif

#ifndef OW_WILD_RUNTIME_TIMER_EXTERNAL_SHARD
OverworldWildRuntimeStatus OverworldWildRuntime_SetTimerPresentationGate(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, BOOL active)
{
    OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    if (active != FALSE && active != TRUE)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = ValidateTimerQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    slot = &runtime->slots[slotIndex];
    if (slot->presentationGate == (u8)active)
        return OW_WILD_RUNTIME_STATUS_IDEMPOTENT;
    slot->presentationGate = (u8)active;
    if (active) return OW_WILD_RUNTIME_STATUS_OK;
    ExpireHiddenTimers(slot->timerBank.timers, slot->activeLayerCount,
        slot->provenance.winningOwnerId,
        slot->provenance.winningInstanceKey);
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_TickCandidateTimers(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 clock, u8 ticks,
    BOOL presentationGate, OverworldWildRuntimeTimerTickResult *result)
{
    OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    u8 i;
    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitTimerTickResult(runtime, slotIndex, result);
    if ((clock != OW_WILD_RUNTIME_TIMER_CLOCK_FRAME
            && clock != OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT)
        || (presentationGate != FALSE && presentationGate != TRUE)) {
        result->status = OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    }
    status = ValidateTimerQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) {
        result->status = status;
        return status;
    }
    slot = &runtime->slots[slotIndex];
    if (slot->presentationGate != (u8)presentationGate) {
        result->status = OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
        return result->status;
    }
    if (!slot->presentationGate) {
        for (i = 0; i < slot->activeLayerCount; i++) {
            OverworldWildRuntimeTimer *timer = &slot->timerBank.timers[i];
            BOOL winner = slot->provenance.winningOwnerId == timer->ownerId
                && slot->provenance.winningInstanceKey == timer->instanceKey;
            int remaining;
            if (!(timer->flags & OW_WILD_RUNTIME_TIMER_VALID)
                || timer->clock != clock
                || (timer->flags & OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
                || timer->remainingTicks == 255) continue;
            if (ExpireHiddenTimer(timer,
                    slot->provenance.winningOwnerId,
                    slot->provenance.winningInstanceKey)) {
                result->changedTimerCount++;
                continue;
            }
            if (!winner && timer->hiddenPolicy
                    != OW_WILD_RUNTIME_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN)
                continue;
            remaining = timer->remainingTicks - ticks;
            if (remaining < 0) remaining = 0;
            if ((u8)remaining != timer->remainingTicks) {
                timer->remainingTicks = (u8)remaining;
                result->changedTimerCount++;
                if (remaining == 0)
                    timer->flags |= OW_WILD_RUNTIME_TIMER_ZERO_PENDING;
            }
        }
    }
    result->pendingExpiryCount = CountPendingTimerExpiries(slot);
    result->status = OW_WILD_RUNTIME_STATUS_OK;
    result->ok = TRUE;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_TickCompletedMovementTimers(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, BOOL presentationGate,
    OverworldWildRuntimeTimerTickResult *result)
{
    return OverworldWildRuntime_TickCandidateTimers(runtime, slotIndex,
        expectedSlotGeneration,
        OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT, 1,
        presentationGate, result);
}

OverworldWildRuntimeStatus OverworldWildRuntime_TickFrameTimers(
    OverworldWildBehaviorStackRuntime *runtime, u16 presentationGateMask,
    OverworldWildRuntimeTimerTickResult results[OW_WILD_MAX_SPAWNS])
{
    OverworldWildRuntimeStatus status;
    u8 i;
    if (runtime == NULL || results == NULL
        || (presentationGateMask & ~((1u << OW_WILD_MAX_SPAWNS) - 1u)))
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[i];
        InitTimerTickResult(runtime, i, &results[i]);
        if (slot->lifecycleState
                != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED) {
            results[i].status = OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT;
            continue;
        }
        status = ValidateTimerQuery(runtime, i, slot->slotGeneration);
        if (status != OW_WILD_RUNTIME_STATUS_OK) {
            results[i].status = status;
            return status;
        }
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        BOOL gate = (presentationGateMask & (1u << i)) != 0;
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[i];
        if (slot->lifecycleState
                != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
            continue;
        status = OverworldWildRuntime_SetTimerPresentationGate(runtime, i,
            slot->slotGeneration, gate);
        if (status != OW_WILD_RUNTIME_STATUS_OK
            && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT)
            return status;
        status = OverworldWildRuntime_TickCandidateTimers(runtime, i,
            slot->slotGeneration, OW_WILD_RUNTIME_TIMER_CLOCK_FRAME, 1,
            gate, &results[i]);
        if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

u8 OverworldWildRuntime_GetPendingTimerExpiryCount(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    if (ValidateTimerQuery(runtime, slotIndex, expectedSlotGeneration)
            != OW_WILD_RUNTIME_STATUS_OK)
        return 0;
    slot = &runtime->slots[slotIndex];
    return CountPendingTimerExpiries(slot);
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetPendingTimerExpiryByIndex(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 pendingIndex,
    OverworldWildRuntimeTimerExpiry *expiryOut)
{
    const OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    u8 i, count = 0;
    if (expiryOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(expiryOut, 0, sizeof(*expiryOut));
    status = ValidateTimerQuery(runtime, slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    slot = &runtime->slots[slotIndex];
    for (i = 0; i < slot->activeLayerCount; i++) {
        const OverworldWildRuntimeTimer *timer = &slot->timerBank.timers[i];
        if ((timer->flags & (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
                != (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING)) continue;
        if (count++ != pendingIndex) continue;
        expiryOut->runtimeEpoch = runtime->handleEpoch;
        expiryOut->slotGeneration = slot->slotGeneration;
        expiryOut->entryGeneration = timer->entryGeneration;
        expiryOut->timerGeneration = timer->timerGeneration;
        expiryOut->ownerId = timer->ownerId;
        expiryOut->instanceKey = timer->instanceKey;
        expiryOut->definitionId = timer->definitionId;
        expiryOut->recoveryTransitionId = timer->recoveryTransitionId;
        expiryOut->slotIndex = slotIndex;
        expiryOut->recoveryPolicy = timer->recoveryPolicy;
        expiryOut->validityTag =
            OverworldWildRuntime_TimerExpiryTagInternal(runtime, expiryOut);
        return OW_WILD_RUNTIME_STATUS_OK;
    }
    return OW_WILD_RUNTIME_STATUS_NOT_FOUND;
}

static OverworldWildRuntimeStatus StaleTimerExpiryResult(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    OverworldWildRuntimeStackDeltaResult *result)
{
    InitResult(runtime, slotIndex, result);
    result->status = OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    result->ok = TRUE;
    return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
}

OverworldWildRuntimeStatus OverworldWildRuntime_CommitTimerExpiry(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeSlotSidecar *slot;
    const OverworldWildRuntimeTimer *timer;
    OverworldWildRuntimeLayer layer;
    OverworldWildRuntimeLayerHandle handle;
    OverworldWildRuntimeStatus status;
    int index;
    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitResult(runtime, expiry != NULL ? expiry->slotIndex : 0xFF, result);
    status = OverworldWildRuntime_PreflightTimerExpiryInternal(runtime, expiry);
    if (status == OW_WILD_RUNTIME_STATUS_STALE_NOOP)
        return StaleTimerExpiryResult(runtime, expiry->slotIndex, result);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE);
    slot = &runtime->slots[expiry->slotIndex];
    if (OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
            expiry->slotIndex, expiry->slotGeneration)
            != OW_WILD_RUNTIME_STATUS_OK)
        return Fail(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE);
    index = FindLayer(slot, expiry->ownerId, expiry->instanceKey);
    if (index < 0)
        return StaleTimerExpiryResult(runtime, expiry->slotIndex, result);
    timer = &slot->timerBank.timers[index];
    if ((timer->flags & (OW_WILD_RUNTIME_TIMER_VALID
                | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
            != (OW_WILD_RUNTIME_TIMER_VALID
                | OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
        || timer->entryGeneration != expiry->entryGeneration
        || timer->timerGeneration != expiry->timerGeneration
        || timer->definitionId != expiry->definitionId
        || timer->recoveryTransitionId != expiry->recoveryTransitionId
        || timer->recoveryPolicy != expiry->recoveryPolicy)
        return StaleTimerExpiryResult(runtime, expiry->slotIndex, result);
    ReadLayer(slot, (u8)index, &layer);
    handle = MakeHandle(runtime, expiry->slotIndex, &layer);
    return OverworldWildRuntime_Remove(runtime, expiry->slotIndex,
        slot->slotGeneration, &handle, result);
}
#endif

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
