#include "../../include/overworld_wild_behavior_data.h"
#include "../overworld_wild_runtime_overlay/overworld_wild_runtime_layers_internal.h"

static u8 CountTimers(const OverworldWildRuntimeSlotSidecar *slot, BOOL pending)
{
    u8 i, count = 0;
    u8 mask = OW_WILD_RUNTIME_TIMER_VALID
        | (pending ? OW_WILD_RUNTIME_TIMER_ZERO_PENDING : 0);
    for (i = 0; i < slot->activeLayerCount; i++)
        if ((slot->timerBank.timers[i].flags & mask) == mask) count++;
    return count;
}

static void InitTick(const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex, OverworldWildRuntimeTimerTickResult *result)
{
    memset(result, 0, sizeof(*result));
    if (runtime == NULL || slotIndex >= OW_WILD_MAX_SPAWNS) return;
    result->runtimeEpoch = runtime->handleEpoch;
    result->slotGeneration = runtime->slots[slotIndex].slotGeneration;
    result->layerGenerationBefore = result->layerGenerationAfter =
        runtime->slots[slotIndex].layerGeneration;
    result->effectiveGenerationBefore = result->effectiveGenerationAfter =
        runtime->slots[slotIndex].effectiveGeneration;
}

static BOOL ExpireHidden(OverworldWildRuntimeTimer *timer,
    const OverworldWildRuntimeProvenance *provenance)
{
    if (!(timer->flags & OW_WILD_RUNTIME_TIMER_VALID)
        || timer->hiddenPolicy != OW_WILD_RUNTIME_HIDDEN_TIMER_EXPIRE_ON_HIDE
        || (provenance->winningOwnerId == timer->ownerId
            && provenance->winningInstanceKey == timer->instanceKey)
        || (timer->flags & OW_WILD_RUNTIME_TIMER_ZERO_PENDING)) return FALSE;
    timer->remainingTicks = 0;
    timer->flags |= OW_WILD_RUNTIME_TIMER_ZERO_PENDING;
    return TRUE;
}

u8 OverworldWildRuntime_GetTimerCount(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration)
{
    if (OverworldWildRuntime_ValidateTimerQueryInternal(runtime, slotIndex,
            expectedSlotGeneration) != OW_WILD_RUNTIME_STATUS_OK) return 0;
    return CountTimers(&runtime->slots[slotIndex], FALSE);
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetTimerByIndex(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 timerIndex,
    OverworldWildRuntimeTimer *timerOut)
{
    OverworldWildRuntimeStatus status;
    const OverworldWildRuntimeSlotSidecar *slot;
    u8 i, count = 0;
    if (timerOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(timerOut, 0, sizeof(*timerOut));
    status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
        slotIndex, expectedSlotGeneration);
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

OverworldWildRuntimeStatus OverworldWildRuntime_SetTimerPresentationGate(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, BOOL active)
{
    OverworldWildRuntimeStatus status;
    OverworldWildRuntimeSlotSidecar *slot;
    u8 i;
    if (active != FALSE && active != TRUE)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
        slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    slot = &runtime->slots[slotIndex];
    if (slot->presentationGate == (u8)active)
        return OW_WILD_RUNTIME_STATUS_IDEMPOTENT;
    slot->presentationGate = (u8)active;
    if (!active)
        for (i = 0; i < slot->activeLayerCount; i++)
            ExpireHidden(&slot->timerBank.timers[i], &slot->provenance);
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_TickCandidateTimers(
    OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 clock, u8 ticks,
    BOOL presentationGate, OverworldWildRuntimeTimerTickResult *result)
{
    OverworldWildRuntimeStatus status;
    OverworldWildRuntimeSlotSidecar *slot;
    u8 i;
    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitTick(runtime, slotIndex, result);
    if ((clock != OW_WILD_RUNTIME_TIMER_CLOCK_FRAME
            && clock != OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT)
        || (presentationGate != FALSE && presentationGate != TRUE))
        return result->status = OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
        slotIndex, expectedSlotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return result->status = status;
    slot = &runtime->slots[slotIndex];
    if (slot->presentationGate != (u8)presentationGate)
        return result->status = OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
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
            if (ExpireHidden(timer, &slot->provenance)) {
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
    result->pendingExpiryCount = CountTimers(slot, TRUE);
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
        expectedSlotGeneration, OW_WILD_RUNTIME_TIMER_CLOCK_COMPLETED_MOVEMENT,
        1, presentationGate, result);
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
        InitTick(runtime, i, &results[i]);
        if (slot->lifecycleState != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED) {
            results[i].status = OW_WILD_RUNTIME_STATUS_INACTIVE_SLOT;
            continue;
        }
        status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime, i,
            slot->slotGeneration);
        if (status != OW_WILD_RUNTIME_STATUS_OK) {
            results[i].status = status;
            return status;
        }
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        BOOL gate = (presentationGateMask & (1u << i)) != 0;
        OverworldWildRuntimeSlotSidecar *slot = &runtime->slots[i];
        if (slot->lifecycleState != OW_WILD_RUNTIME_SLOT_LIFECYCLE_ASSIGNED)
            continue;
        status = OverworldWildRuntime_SetTimerPresentationGate(runtime, i,
            slot->slotGeneration, gate);
        if (status != OW_WILD_RUNTIME_STATUS_OK
            && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT) return status;
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
    if (OverworldWildRuntime_ValidateTimerQueryInternal(runtime, slotIndex,
            expectedSlotGeneration) != OW_WILD_RUNTIME_STATUS_OK) return 0;
    return CountTimers(&runtime->slots[slotIndex], TRUE);
}

OverworldWildRuntimeStatus OverworldWildRuntime_GetPendingTimerExpiryByIndex(
    const OverworldWildBehaviorStackRuntime *runtime, u8 slotIndex,
    u32 expectedSlotGeneration, u8 pendingIndex,
    OverworldWildRuntimeTimerExpiry *expiryOut)
{
    OverworldWildRuntimeStatus status;
    const OverworldWildRuntimeSlotSidecar *slot;
    u8 i, count = 0;
    if (expiryOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(expiryOut, 0, sizeof(*expiryOut));
    status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
        slotIndex, expectedSlotGeneration);
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

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
static void InitDelta(const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex, OverworldWildRuntimeStackDeltaResult *result)
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

static OverworldWildRuntimeStatus FinishDelta(
    OverworldWildRuntimeStackDeltaResult *result,
    OverworldWildRuntimeStatus status, BOOL ok)
{
    result->status = status;
    result->ok = ok;
    return status;
}

OverworldWildRuntimeStatus OverworldWildRuntime_CommitTimerExpiry(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeStackDeltaResult *result)
{
    OverworldWildRuntimeSlotSidecar *slot;
    const OverworldWildRuntimeTimer *timer;
    OverworldWildRuntimeLayerHandle handle;
    OverworldWildRuntimeStatus status;
    int index = -1;
    u8 i;
    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitDelta(runtime, expiry != NULL ? expiry->slotIndex : 0xFF, result);
    status = OverworldWildRuntime_PreflightTimerExpiryInternal(runtime, expiry);
    if (status == OW_WILD_RUNTIME_STATUS_STALE_NOOP)
        return FinishDelta(result, status, TRUE);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishDelta(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
            FALSE);
    slot = &runtime->slots[expiry->slotIndex];
    status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
        expiry->slotIndex, expiry->slotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishDelta(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
            FALSE);
    for (i = 0; i < slot->activeLayerCount; i++)
        if (slot->layerBank.ownerIds[i] == expiry->ownerId
            && slot->layerBank.instanceKeys[i] == expiry->instanceKey) {
            index = i;
            break;
        }
    if (index < 0)
        return FinishDelta(result, OW_WILD_RUNTIME_STATUS_STALE_NOOP, TRUE);
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
        return FinishDelta(result, OW_WILD_RUNTIME_STATUS_STALE_NOOP, TRUE);
    status = OverworldWildRuntime_MakeTimerRemovalHandleInternal(runtime,
        expiry->slotIndex, (u8)index, &handle);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishDelta(result, status, FALSE);
    return OverworldWildRuntime_Remove(runtime, expiry->slotIndex,
        slot->slotGeneration, &handle, result);
}
#endif

#ifdef OW_WILD_RUNTIME_HOST_TEST
static BOOL CopyCatalogHeader(OverworldWildBehaviorDataBlobHeader *headerOut)
{
    if (headerOut == NULL
#ifdef OW_WILD_RUNTIME_HOST_TEST
        || OverworldWildRuntime_CopyInstalledCatalogBytes == NULL
#endif
        || !OverworldWildRuntime_CopyInstalledCatalogBytes(
            0, headerOut, sizeof(*headerOut))
        || headerOut->magic != OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        || headerOut->version != OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        || headerOut->headerSize != sizeof(*headerOut)
        || headerOut->blobSize != OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE)
        return FALSE;
    return TRUE;
}

static BOOL CopyCatalogRecord(
    const OverworldWildBehaviorDataBlobHeader *header,
    const OverworldWildBlobSection *section,
    u16 index,
    void *recordOut,
    u16 expectedSize)
{
    u32 relativeOffset;
    if (header == NULL || section == NULL || recordOut == NULL
        || expectedSize == 0 || section->entrySize != expectedSize
        || index >= section->count)
        return FALSE;
    relativeOffset = (u32)index * expectedSize;
    if (section->offset > header->blobSize
        || relativeOffset > header->blobSize - section->offset
        || expectedSize > header->blobSize - section->offset - relativeOffset)
        return FALSE;
    return OverworldWildRuntime_CopyInstalledCatalogBytes(
        section->offset + relativeOffset, recordOut, expectedSize);
}
#endif

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
static BOOL CopyCanonicalApplicability(
    const OverworldWildRuntimeStaticComposition *composition,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut)
{
    u8 nodeIndex;
    u8 boundIndex = 0;
    u8 boundRoleMask = 0;
    OverworldWildRuntimeApplicabilityInput *applicability =
        &resolvedOut->applicability;
    applicability->immutableContextMask = composition->immutableContextMask;
    applicability->controllerId = composition->controllerId;
    applicability->effectiveProfileId = composition->baseProfileId;
    applicability->effectiveSemanticRole = composition->baseSemanticRole;
    applicability->semanticRoleMask = composition->semanticRoleMask;
    for (nodeIndex = 0; nodeIndex < composition->nodeCount; nodeIndex++) {
        const OverworldWildRuntimeResolvedNode *node =
            &composition->resolvedNodes[nodeIndex];
        if (!node->bound) continue;
        if (boundIndex >= OW_WILD_RUNTIME_MAX_BOUND_NODES
            || node->nodeId == 0 || node->profileId == 0
            || node->semanticRole == 0 || node->semanticRole > OWBD_ROLE_CUSTOM)
            return FALSE;
        applicability->boundNodeIds[boundIndex++] = node->nodeId;
        boundRoleMask |= OWBD_ROLE_MASK(node->semanticRole);
        if (node->semanticRole == OWBD_ROLE_TIRED) {
            if (resolvedOut->authoredTiredBound) return FALSE;
            resolvedOut->authoredTiredBound = TRUE;
            resolvedOut->tiredNodeId = node->nodeId;
            resolvedOut->tiredProfileId = node->profileId;
        }
    }
    applicability->boundNodeCount = boundIndex;
    return boundIndex == composition->boundNodeCount
        && boundRoleMask == composition->semanticRoleMask
        && (boundRoleMask & OWBD_ROLE_MASK(composition->baseSemanticRole));
}

static OverworldWildRuntimeStatus ResolveCanonicalStaticContextInternal(
    const OverworldWildRuntimeStaticContext *staticContext,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut,
    OverworldWildRuntimeStaticComposition *compositionOut)
{
    OverworldWildRuntimeStaticComposition composition;
    if (resolvedOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    memset(resolvedOut, 0, sizeof(*resolvedOut));
    if (staticContext == NULL
        || !OverworldWildRuntime_CopyInstalledStaticComposition(
            staticContext, NULL, &composition)
        || !composition.valid
        || composition.controllerId == 0 || composition.baseNodeId == 0
        || composition.baseProfileId == 0
        || composition.baseSemanticRole == 0
        || composition.baseSemanticRole > OWBD_ROLE_CUSTOM
        || composition.boundNodeCount > OW_WILD_RUNTIME_MAX_BOUND_NODES
        || composition.nodeCount > OW_WILD_RUNTIME_MAX_RESOLVED_NODES)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    resolvedOut->catalogIdentity = composition.catalogIdentity;
    resolvedOut->staticContextIdentity = composition.staticContextIdentity;
    resolvedOut->staticSetHash = composition.staticSetHash;
    resolvedOut->controllerId = composition.controllerId;
    resolvedOut->baseNodeId = composition.baseNodeId;
    resolvedOut->baseProfileId = composition.baseProfileId;
    resolvedOut->spawnPolicyId = composition.spawnPolicyId;
    resolvedOut->populationPolicyId = composition.populationPolicyId;
    resolvedOut->baseSemanticRole = composition.baseSemanticRole;
    resolvedOut->stamina = composition.controllerValues[6];
    resolvedOut->restTime = composition.controllerValues[7];
    if (!CopyCanonicalApplicability(&composition, resolvedOut)) {
        memset(resolvedOut, 0, sizeof(*resolvedOut));
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    }
    if (compositionOut != NULL) *compositionOut = composition;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_ResolveCanonicalStaticContext(
    const OverworldWildRuntimeStaticContext *staticContext,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut)
{
    return ResolveCanonicalStaticContextInternal(
        staticContext, resolvedOut, NULL);
}

OverworldWildRuntimeStatus OverworldWildRuntime_PrimeCanonicalEffectiveCache(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeStaticContext *staticContext,
    OverworldWildRuntimeResolvedStaticContext *resolvedOut)
{
    OverworldWildRuntimeResolvedStaticContext resolved;
    OverworldWildRuntimeStatus status =
        OverworldWildRuntime_ResolveCanonicalStaticContext(
            staticContext, &resolved);
    if (resolvedOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    memset(resolvedOut, 0, sizeof(*resolvedOut));
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    status = OverworldWildRuntime_PrimeEffectiveCache(runtime, slotIndex,
        expectedSlotGeneration, staticContext, &resolved.applicability);
    if (status != OW_WILD_RUNTIME_STATUS_OK
        && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT)
        return status;
    *resolvedOut = resolved;
    return status;
}
#endif

#ifdef OW_WILD_RUNTIME_HOST_TEST
static BOOL CopyTransitionForTrigger(
    const OverworldWildBehaviorDataBlobHeader *header,
    u8 trigger,
    OverworldWildTransitionRecord *transitionOut)
{
    OverworldWildTransitionRecord candidate;
    u16 index;
    BOOL found = FALSE;
    for (index = 0; index < header->transitions.count; index++) {
        if (!CopyCatalogRecord(header, &header->transitions, index,
                &candidate, sizeof(candidate))) return FALSE;
        if (candidate.trigger != trigger) continue;
        if (found) return FALSE;
        *transitionOut = candidate;
        found = TRUE;
    }
    return found;
}

static BOOL SerializedNodeBacklinkMatches(
    const OverworldWildBehaviorDataBlobHeader *header,
    u16 nodeId,
    u16 controllerId,
    u16 profileId,
    u8 semanticRole)
{
    OverworldWildControllerNodeRecord node;
    u16 index;
    u8 matchCount = 0;
    for (index = 0; index < header->controllerNodes.count; index++) {
        if (!CopyCatalogRecord(header, &header->controllerNodes, index,
                &node, sizeof(node))) return FALSE;
        if (node.stableId != nodeId) continue;
        matchCount++;
        if (node.controllerId != controllerId
            || node.profileIdentityId != profileId
            || node.semanticRole != semanticRole || node.reserved != 0)
            return FALSE;
    }
    return matchCount == 1;
}
#endif

#ifdef OW_WILD_RUNTIME_HOST_TEST
static BOOL CopyBoundResolvedNode(
    const OverworldWildRuntimeStaticComposition *composition,
    u16 nodeId,
    u8 semanticRole,
    OverworldWildRuntimeResolvedNode *nodeOut)
{
    u8 index;
    u8 matchCount = 0;
    for (index = 0; index < composition->nodeCount; index++) {
        const OverworldWildRuntimeResolvedNode *node =
            &composition->resolvedNodes[index];
        if (node->nodeId != nodeId) continue;
        matchCount++;
        if (!node->bound || node->profileId == 0
            || node->semanticRole != semanticRole)
            return FALSE;
        *nodeOut = *node;
    }
    return matchCount == 1;
}
#endif

#ifdef OW_WILD_RUNTIME_HOST_TEST
static OverworldWildRuntimeStatus ResolveRecoveryCandidateCatalogOracle(
    const OverworldWildRuntimeStaticContext *staticContext,
    u8 origin,
    OverworldWildRuntimeRecoveryCandidate *candidateOut)
{
    OverworldWildBehaviorDataBlobHeader header;
    OverworldWildRuntimeResolvedStaticContext resolved;
    OverworldWildRuntimeStaticComposition composition;
    OverworldWildRuntimeResolvedNode resolvedNode;
    OverworldWildRuntimeDefinition definition;
    OverworldWildOverrideDefinitionRecord definitionRecord = {0};
    OverworldWildOverrideDefinitionRecord definitionCandidate;
    OverworldWildTiredTranslationRecord translation = {0};
    OverworldWildTiredTranslationRecord translationCandidate;
    OverworldWildTransitionRecord transition = {0};
    OverworldWildRuntimeStatus status;
    u32 catalogIdentity;
    u16 definitionId = 0;
    u16 ownerId = 0;
    u16 recoveryTransitionId = 0;
    u16 nodeId = 0;
    u16 profileId = 0;
    u16 index;
    u8 translatedOrigin = 0;
    u8 matchCount = 0;
    u8 definitionMatchCount = 0;
    u8 selection;
    if (candidateOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
    memset(candidateOut, 0, sizeof(*candidateOut));
    status = ResolveCanonicalStaticContextInternal(
        staticContext, &resolved, &composition);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    if (!OverworldWildRuntime_CopyInstalledCatalogIdentity(&catalogIdentity)
        || catalogIdentity != resolved.catalogIdentity
        || !CopyCatalogHeader(&header))
        return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
    if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA) {
        if (!resolved.authoredTiredBound)
            return OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE;
        if (!CopyTransitionForTrigger(&header,
                OWBD_TRIGGER_STAMINA_EXHAUSTED, &transition))
            return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
        definitionId = transition.candidateDefinitionId;
        ownerId = transition.ownerId;
        nodeId = resolved.tiredNodeId;
        profileId = resolved.tiredProfileId;
        selection = OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC;
    } else {
        if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH)
            translatedOrigin = OWBD_TIRED_ORIGIN_RAM_CRASH;
        else if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY)
            translatedOrigin = OWBD_TIRED_ORIGIN_THROW_RECOVERY;
        else if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED)
            translatedOrigin = OWBD_TIRED_ORIGIN_FLED;
        else
            return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
        for (index = 0; index < header.tiredTranslations.count; index++) {
            if (!CopyCatalogRecord(&header, &header.tiredTranslations, index,
                    &translationCandidate, sizeof(translationCandidate)))
                return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
            if (translationCandidate.tiredOriginKind != translatedOrigin
                || translationCandidate.destinationControllerId
                    != resolved.controllerId
                || translationCandidate.authoredTiredBound
                    != resolved.authoredTiredBound)
                continue;
            if (matchCount++ != 0) continue;
            translation = translationCandidate;
            if (translation.authoredProfileId == 0
                || translation.timerOperator != OWBD_CANDIDATE_TIMER_SET
                || translation.timerSource != OWBD_TIMER_SOURCE_FIXED
                || translation.mapLifetime != OWBD_LIFETIME_PRESERVE_LOGICAL
                || translation.battleLifetime != OWBD_LIFETIME_CLEAR
                || translation.flags != 0 || translation.reserved != 0
                || (resolved.authoredTiredBound
                    && (translation.exactFallbackControllerId != 0
                        || translation.exactFallbackNodeId != 0))
                || (!resolved.authoredTiredBound
                    && (translation.exactFallbackControllerId
                            != resolved.controllerId
                        || translation.exactFallbackNodeId == 0)))
                return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
            definitionId = translation.candidateDefinitionId;
            recoveryTransitionId = translation.recoveryTransitionId;
        }
        if (matchCount != 1)
            return matchCount == 0
                ? OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
                : OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR;
        if (resolved.authoredTiredBound) {
            nodeId = resolved.tiredNodeId;
            profileId = resolved.tiredProfileId;
            selection = OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC;
            if (!SerializedNodeBacklinkMatches(&header, nodeId,
                    resolved.controllerId, translation.authoredProfileId,
                    OWBD_ROLE_TIRED))
                return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
        } else {
            if (!CopyBoundResolvedNode(&composition,
                    translation.exactFallbackNodeId, OWBD_ROLE_CUSTOM,
                    &resolvedNode)
                || !SerializedNodeBacklinkMatches(&header,
                    translation.exactFallbackNodeId, resolved.controllerId,
                    translation.authoredProfileId, OWBD_ROLE_CUSTOM))
                return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
            nodeId = resolvedNode.nodeId;
            profileId = resolvedNode.profileId;
            selection = OW_WILD_RUNTIME_RECOVERY_SELECTION_GENERATED_EXACT;
        }
    }
    for (index = 0; index < header.overrideDefinitions.count; index++) {
        if (!CopyCatalogRecord(&header, &header.overrideDefinitions, index,
                &definitionCandidate, sizeof(definitionCandidate)))
            return OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA;
        if (definitionCandidate.stableId != definitionId) continue;
        if (definitionMatchCount++ == 0)
            definitionRecord = definitionCandidate;
    }
    if (!OverworldWildRuntime_CopyInstalledDefinition(
            definitionId, &definition)
        || definitionMatchCount != 1
        || definition.kind != OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE
        || definitionRecord.kind != definition.kind
        || definitionRecord.selectorKind != definition.selectorKind
        || definitionRecord.semanticRole != definition.semanticRole
        || definitionRecord.nodeId != definition.nodeId
        || definitionRecord.requiredOwnerId != definition.requiredOwnerId
        || !(definition.flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
        || definition.requiredOwnerId == 0
        || (ownerId != 0 && ownerId != definition.requiredOwnerId)
        || (definition.controllerId != 0
            && definition.controllerId != resolved.controllerId)
        || definitionRecord.recoveryTransitionId == 0
        || (recoveryTransitionId != 0
            && recoveryTransitionId != definitionRecord.recoveryTransitionId)
        || (selection == OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC
            && (definition.selectorKind
                    != OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
                || definition.semanticRole != OWBD_ROLE_TIRED))
        || (selection == OW_WILD_RUNTIME_RECOVERY_SELECTION_GENERATED_EXACT
            && (definition.selectorKind != OW_WILD_RUNTIME_SELECTOR_EXACT
                || definition.nodeId != nodeId))
        || nodeId == 0 || profileId == 0
        || (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA
            && (definition.flags
                & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN))
        || (origin != OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA
            && (!(definition.flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN)
                || definition.tiredOriginKind != translatedOrigin)))
        return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
    ownerId = definition.requiredOwnerId;
    candidateOut->definitionId = definition.stableId;
    candidateOut->ownerId = ownerId;
    candidateOut->recoveryTransitionId =
        definitionRecord.recoveryTransitionId;
    candidateOut->controllerId = resolved.controllerId;
    candidateOut->nodeId = nodeId;
    candidateOut->profileId = profileId;
    candidateOut->origin = origin;
    candidateOut->selection = selection;
    candidateOut->selectorKind = definition.selectorKind;
    candidateOut->semanticRole = definition.semanticRole;
    return OW_WILD_RUNTIME_STATUS_OK;
}
#endif

/* The installed bytes are immutable after OwbdValidateStream accepts the
 * complete v40 closure. Runtime selection therefore consumes the resident
 * catalog's value-copy projections and rechecks only caller-dependent
 * identity/applicability. The host catalog oracle above retains exhaustive
 * relationship coverage without shipping a second validator in overlay159. */
#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
OverworldWildRuntimeStatus OverworldWildRuntime_ResolveRecoveryCandidate(
    const OverworldWildRuntimeStaticContext *staticContext,
    u8 origin,
    OverworldWildRuntimeRecoveryCandidate *candidateOut)
{
    OverworldWildRuntimeResolvedStaticContext resolved;
    OverworldWildRuntimeStaticComposition composition;
    OverworldWildRuntimeResolvedNode resolvedNode;
    OverworldWildRuntimeDefinition definition;
    OverworldWildRuntimeTimerDefinition timerDefinition;
    OverworldWildRuntimeStatus status;
    u16 definitionId = 0;
    u8 translatedOrigin = 0;
    u8 selection;
    u8 matches;

    if (candidateOut == NULL)
        return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
    memset(candidateOut, 0, sizeof(*candidateOut));
    status = ResolveCanonicalStaticContextInternal(
        staticContext, &resolved, &composition);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;

    if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA) {
        if (!resolved.authoredTiredBound)
            return OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE;
        selection = OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC;
    } else {
        if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED)
            translatedOrigin = OWBD_TIRED_ORIGIN_FLED;
        else if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_RAM_CRASH)
            translatedOrigin = OWBD_TIRED_ORIGIN_RAM_CRASH;
        else if (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_THROW_RECOVERY)
            translatedOrigin = OWBD_TIRED_ORIGIN_THROW_RECOVERY;
        else
            return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
        selection = resolved.authoredTiredBound
            ? OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC
            : OW_WILD_RUNTIME_RECOVERY_SELECTION_GENERATED_EXACT;
    }
    matches = OverworldWildRuntime_CountInstalledTiredTranslations(
        translatedOrigin, resolved.controllerId,
        resolved.authoredTiredBound, &definitionId);
    if (matches != 1)
        return matches == 0
            ? OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE
            : OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR;
    if (!OverworldWildRuntime_CopyInstalledDefinition(
            definitionId, &definition)
        || !OverworldWildRuntime_ResolveInstalledTimerDefinition(
            definitionId, NULL, &timerDefinition)
        || definition.kind != OW_WILD_RUNTIME_DEFINITION_STATE_CANDIDATE
        || !(definition.flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
        || definition.requiredOwnerId == 0
        || (definition.controllerId != 0
            && definition.controllerId != resolved.controllerId)
        || (origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA
            && (definition.flags
                & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN))
        || (origin != OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA
            && (!(definition.flags
                    & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN)
                || definition.tiredOriginKind != translatedOrigin)))
        return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;

    if (selection == OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC) {
        if (definition.selectorKind
                != OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
            || definition.semanticRole != OWBD_ROLE_TIRED
            || !OverworldWildRuntime_CopyInstalledResolvedNode(
                &composition, &definition, &resolvedNode)
            || resolvedNode.nodeId != resolved.tiredNodeId)
            return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
    } else if (definition.selectorKind != OW_WILD_RUNTIME_SELECTOR_EXACT
        || !OverworldWildRuntime_CopyInstalledResolvedNode(
            &composition, &definition, &resolvedNode)
        || resolvedNode.semanticRole != OWBD_ROLE_CUSTOM) {
        return OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION;
    }

    candidateOut->definitionId = definition.stableId;
    candidateOut->ownerId = definition.requiredOwnerId;
    candidateOut->recoveryTransitionId =
        timerDefinition.recoveryTransitionId;
    candidateOut->controllerId = resolved.controllerId;
    candidateOut->nodeId = resolvedNode.nodeId;
    candidateOut->profileId = resolvedNode.profileId;
    candidateOut->origin = origin;
    candidateOut->selection = selection;
    candidateOut->selectorKind = definition.selectorKind;
    candidateOut->semanticRole = definition.semanticRole;
    return OW_WILD_RUNTIME_STATUS_OK;
}
#endif

static OverworldWildRuntimeStatus FinishTransition(
    OverworldWildRuntimeTransitionResult *result,
    OverworldWildRuntimeStatus status,
    BOOL ok)
{
    result->status = status;
    result->ok = ok;
    return status;
}

static int FindTransitionLayer(
    const OverworldWildRuntimeSlotSidecar *slot,
    u16 definitionId,
    u16 ownerId,
    u16 instanceKey)
{
    u8 index;
    for (index = 0; index < slot->activeLayerCount; index++) {
        if (slot->layerBank.ownerIds[index] == ownerId
            && slot->layerBank.instanceKeys[index] == instanceKey
            && (definitionId == 0
                || slot->layerBank.definitionIds[index] == definitionId))
            return index;
    }
    return -1;
}

static BOOL TransitionExpiryIsZero(
    const OverworldWildRuntimeTimerExpiry *expiry)
{
    const u8 *bytes = (const u8 *)expiry;
    u8 index;
    for (index = 0; index < sizeof(*expiry); index++)
        if (bytes[index] != 0) return FALSE;
    return TRUE;
}

static OverworldWildRuntimeStatus PreflightTransitionReplay(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeTransitionEvent *event)
{
    const OverworldWildRuntimeTimerExpiry *expiry = &event->replayExpiry;
    OverworldWildRuntimeStatus status;
    if (!(event->flags & OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY))
        return TransitionExpiryIsZero(expiry)
            ? OW_WILD_RUNTIME_STATUS_OK
            : OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    status = OverworldWildRuntime_PreflightTimerExpiryInternal(
        runtime, expiry);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    if (expiry->slotIndex != slotIndex
        || expiry->slotGeneration != expectedSlotGeneration)
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    return OverworldWildRuntime_MatchesPendingTimerExpiry(runtime, expiry)
        ? OW_WILD_RUNTIME_STATUS_OK : OW_WILD_RUNTIME_STATUS_STALE_NOOP;
}

#if defined(__GNUC__) && !defined(__clang__)
#define OW_WILD_RUNTIME_GUARD_DISPATCH_ATTRIBUTES \
    __attribute__((noinline, optimize("no-jump-tables")))
#else
#define OW_WILD_RUNTIME_GUARD_DISPATCH_ATTRIBUTES __attribute__((noinline))
#endif

static BOOL OW_WILD_RUNTIME_GUARD_DISPATCH_ATTRIBUTES TransitionGuardMatches(
    const OverworldWildRuntimeTransitionEvent *event,
    const OverworldWildRuntimeEffectiveCache *effective,
    const OverworldWildRuntimeSlotSidecar *slot,
    const OverworldWildTransitionGuardRecord *guard)
{
    BOOL match;
    if (guard->kind == OWBD_GUARD_ALWAYS) {
        match = TRUE;
    } else if (guard->kind == OWBD_GUARD_EFFECTIVE_ROLE) {
        match = effective->semanticRole == guard->payload;
    } else if (guard->kind == OWBD_GUARD_EFFECTIVE_NODE) {
        match = effective->nodeId == guard->referenceId;
    } else if (guard->kind == OWBD_GUARD_OWNER_PRESENT
            || guard->kind == OWBD_GUARD_OWNER_ABSENT) {
        u8 index;
        match = FALSE;
        for (index = 0; index < slot->activeLayerCount; index++) {
            if (slot->layerBank.ownerIds[index] == guard->referenceId) {
                match = TRUE;
                break;
            }
        }
        if (guard->kind == OWBD_GUARD_OWNER_ABSENT) match = !match;
    } else if (guard->kind == OWBD_GUARD_CANDIDATE_TIMER_EXPIRED) {
        match = (event->flags & OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY)
            && event->replayExpiry.recoveryTransitionId != 0
            && event->replayExpiry.definitionId != 0
            && event->replayExpiry.ownerId != 0
            && event->trigger == guard->payload;
    } else if (guard->kind == OWBD_GUARD_ALERT_CHANCE_ROLL) {
        match = event->chanceRoll < guard->payload;
    } else if (guard->kind == OWBD_GUARD_SYSTEM_ROUTE) {
        match = event->systemRoute == guard->payload;
    } else {
        return FALSE;
    }
    return guard->negate ? !match : match;
}

#undef OW_WILD_RUNTIME_GUARD_DISPATCH_ATTRIBUTES

static BOOL CopyTransitionApplicability(
    const OverworldWildRuntimeSlotSidecar *slot,
    OverworldWildRuntimeApplicabilityInput *applicabilityOut)
{
    const OverworldWildRuntimeStaticCache *cache = &slot->staticCache;
    u8 index;
    memset(applicabilityOut, 0, sizeof(*applicabilityOut));
    if (!cache->valid || cache->boundNodeCount > OW_WILD_RUNTIME_MAX_BOUND_NODES)
        return FALSE;
    applicabilityOut->immutableContextMask = cache->immutableContextMask;
    applicabilityOut->controllerId = cache->controllerId;
    applicabilityOut->semanticRoleMask = cache->semanticRoleMask;
    applicabilityOut->effectiveProfileId = cache->baseProfileId;
    applicabilityOut->effectiveSemanticRole = cache->baseSemanticRole;
    for (index = 0; index < cache->nodeCount; index++) {
        if (!cache->resolvedNodes[index].bound) continue;
        applicabilityOut->boundNodeIds[applicabilityOut->boundNodeCount++] =
            cache->resolvedNodes[index].nodeId;
    }
    return applicabilityOut->boundNodeCount == cache->boundNodeCount;
}

OverworldWildRuntimeStatus OverworldWildRuntime_DispatchTransition(
    OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeTransitionEvent *event,
    OverworldWildRuntimeTransitionResult *result)
{
    const OverworldWildBehaviorDataBlobHeader *catalog;
    const OverworldWildTransitionRecord *transitions;
    const OverworldWildTransitionGuardRecord *guards;
    const OverworldWildTransitionOperationRecord *operations;
    const OverworldWildTransitionActionRecord *actions;
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeEffectiveCache effective;
    const OverworldWildTransitionRecord *transition = NULL;
    OverworldWildRuntimeStatus status;
    u16 index;
    u32 actionFlags = 0;
    BOOL ambiguous = FALSE;
    BOOL mutated;

    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(result, 0, sizeof(*result));
    if (event == NULL || event->trigger < OWBD_TRIGGER_ALERT_COMPLETE
        || event->trigger > OWBD_TRIGGER_FOLLOWER_REMOVE
        || event->flags & ~OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY
        || event->chanceRoll > 99)
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_INVALID_HANDLE, FALSE);
    status = PreflightTransitionReplay(runtime, slotIndex,
        expectedSlotGeneration, event);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishTransition(result, status,
            status == OW_WILD_RUNTIME_STATUS_STALE_NOOP);
    status = OverworldWildRuntime_GetEffectiveCache(runtime, slotIndex,
        expectedSlotGeneration, &effective);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishTransition(result, status, FALSE);
    catalog = OverworldWildRuntime_AcquireInstalledTransitionCatalog();
    if (catalog == NULL)
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA, FALSE);
    transitions = (const void *)((const u8 *)catalog
        + catalog->transitions.offset);
    guards = (const void *)((const u8 *)catalog
        + catalog->transitionGuards.offset);
    operations = (const void *)((const u8 *)catalog
        + catalog->transitionOperations.offset);
    actions = (const void *)((const u8 *)catalog
        + catalog->transitionActions.offset);

    for (index = 0; index < catalog->transitions.count; index++) {
        const OverworldWildTransitionRecord *candidate =
            &transitions[index];
        if (candidate->trigger != event->trigger
            || !(candidate->fromRoleMask
                & OWBD_ROLE_MASK(effective.semanticRole))
            || ((event->flags & OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY)
                && candidate->stableId
                    != event->replayExpiry.recoveryTransitionId))
            continue;
        if (transition == NULL
            || candidate->dispatchPriority > transition->dispatchPriority) {
            transition = candidate;
            ambiguous = FALSE;
        } else if (candidate->dispatchPriority
                == transition->dispatchPriority) {
            ambiguous = TRUE;
        }
    }
    if (ambiguous)
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_AMBIGUOUS_SELECTOR, FALSE);
    if (transition == NULL)
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE, FALSE);
    if ((event->flags & OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY)
        && (transition->candidateDefinitionId
                != event->replayExpiry.definitionId
            || transition->ownerId != event->replayExpiry.ownerId))
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_STALE_NOOP, TRUE);
    if (transition->operationCount
            > OW_WILD_RUNTIME_MAX_DELTA_OPERATIONS)
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA, FALSE);
    for (index = 0; index < transition->guardCount; index++) {
        const OverworldWildTransitionGuardRecord *guard =
            &guards[transition->guardStart + index];
        if (!TransitionGuardMatches(event, &effective,
                &runtime->slots[slotIndex], guard))
            return FinishTransition(result,
                OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE, FALSE);
    }

    memset(&request, 0, sizeof(request));
    request.expectedSlotGeneration = expectedSlotGeneration;
    request.slotIndex = slotIndex;
    if (!CopyTransitionApplicability(&runtime->slots[slotIndex],
            &request.applicability))
        return FinishTransition(result,
            OW_WILD_RUNTIME_STATUS_NOT_APPLICABLE, FALSE);
    for (index = 0; index < transition->operationCount; index++) {
        const OverworldWildTransitionOperationRecord *source =
            &operations[transition->operationStart + index];
        OverworldWildRuntimeDeltaOperation *operation =
            &request.operations[request.operationCount];
        u16 instanceKey;
        int layerIndex;
        BOOL replayTarget;
        if (source->busyPolicy != OWBD_BUSY_REJECT)
            return FinishTransition(result,
                source->busyPolicy == OWBD_BUSY_QUEUE_EXACT
                    ? OW_WILD_RUNTIME_STATUS_DATA_BUSY
                    : OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA,
                FALSE);
        replayTarget = source->definitionId
                == transition->candidateDefinitionId
            && source->ownerId == transition->ownerId;
        instanceKey = replayTarget
                && (event->flags & OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY)
            ? event->replayExpiry.instanceKey
            : event->trigger == OWBD_TRIGGER_FORCED_SLEEP_APPLY
                ? source->instanceKey : 0;
        memset(operation, 0, sizeof(*operation));
        operation->operationId = source->stableId;
        operation->kind = source->kind;
        if (source->kind == OWBD_TRANSITION_APPLY
            || source->kind == OWBD_TRANSITION_REPLACE) {
            operation->payload.apply.definitionId =
                source->kind == OWBD_TRANSITION_REPLACE
                    ? source->replacementDefinitionId
                    : source->definitionId;
            operation->payload.apply.ownerId = source->ownerId;
            operation->payload.apply.instanceKey = instanceKey;
        } else if (source->kind == OWBD_TRANSITION_REMOVE_REQUIRED
                || source->kind == OWBD_TRANSITION_REMOVE_IF_PRESENT) {
            layerIndex = FindTransitionLayer(&runtime->slots[slotIndex],
                source->definitionId, source->ownerId, instanceKey);
            if (layerIndex < 0) {
                if (source->kind == OWBD_TRANSITION_REMOVE_REQUIRED)
                    return FinishTransition(result,
                        OW_WILD_RUNTIME_STATUS_NOT_FOUND, FALSE);
                continue;
            }
            status = OverworldWildRuntime_MakeTimerRemovalHandleInternal(
                runtime, slotIndex, (u8)layerIndex,
                &operation->payload.handle);
            if (status != OW_WILD_RUNTIME_STATUS_OK)
                return FinishTransition(result, status, FALSE);
        } else if (source->kind
                == OWBD_TRANSITION_REMOVE_OWNER_IF_PRESENT) {
            operation->payload.owner.ownerId = source->ownerId;
        } else if (source->kind == OWBD_TRANSITION_APPLY_POLICY
                && source->policyId >= 1 && source->policyId <= 3) {
            operation->payload.policy.mapLifetime = (u8)source->policyId;
        } else {
            return FinishTransition(result,
                OW_WILD_RUNTIME_STATUS_INVALID_STATIC_DATA, FALSE);
        }
        request.operationCount++;
    }
    status = OverworldWildRuntime_ApplyStackDeltaCompact(
        runtime, &request, &mutated);
    if (status != OW_WILD_RUNTIME_STATUS_OK
        && status != OW_WILD_RUNTIME_STATUS_IDEMPOTENT)
        return FinishTransition(result, status, FALSE);
    result->effectiveAfter = runtime->slots[slotIndex].effectiveCache;
    result->transitionId = transition->stableId;
    result->definitionId = transition->candidateDefinitionId;
    result->ownerId = transition->ownerId;
    result->instanceKey = event->flags
            & OW_WILD_RUNTIME_TRANSITION_EVENT_REPLAY
        ? event->replayExpiry.instanceKey
        : event->trigger == OWBD_TRIGGER_FORCED_SLEEP_APPLY
            ? transition->candidateDefinitionId : 0;
    result->mutated = mutated;
    result->operationCount = request.operationCount;
    if (mutated) {
        for (index = 0; index < transition->actionCount; index++)
            actionFlags |= OW_WILD_RUNTIME_TRANSITION_ACTION(
                actions[transition->actionStart + index].kind);
        result->actionFlags = actionFlags;
    }
    return FinishTransition(result, status, TRUE);
}

typedef struct OverworldWildRuntimeRecoveryPlan {
    u16 transitionId;
    u16 candidateDefinitionId;
    u16 ownerId;
    u16 calmResetOwnerIds[OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS];
    u8 calmResetOwnerCount;
    u8 route;
    u8 actionFlags;
    u8 reserved;
} OverworldWildRuntimeRecoveryPlan;

#ifdef OW_WILD_RUNTIME_HOST_TEST
static BOOL AddRecoveryStableId(u16 *stableIds, u8 *count, u16 stableId)
{
    u8 index;
    if (stableId == 0) return FALSE;
    for (index = 0; index < *count; index++)
        if (stableIds[index] == stableId) return FALSE;
    stableIds[(*count)++] = stableId;
    return TRUE;
}

static BOOL CopyInstalledControllerIds(
    const OverworldWildBehaviorDataBlobHeader *header,
    u16 controllerIds[OWBD_CONTROLLER_COUNT])
{
    OverworldWildControllerRecord controller;
    u16 index;
    if (header == NULL || header->controllers.count != OWBD_CONTROLLER_COUNT)
        return FALSE;
    memset(controllerIds, 0,
        sizeof(u16) * OWBD_CONTROLLER_COUNT);
    for (index = 0; index < header->controllers.count; index++) {
        u16 priorIndex;
        if (!CopyCatalogRecord(header, &header->controllers, index,
                &controller, sizeof(controller))
            || controller.stableId == 0 || controller.reserved != 0)
            return FALSE;
        for (priorIndex = 0; priorIndex < index; priorIndex++)
            if (controllerIds[priorIndex] == controller.stableId)
                return FALSE;
        controllerIds[index] = controller.stableId;
    }
    return TRUE;
}

static BOOL InstalledControllerIndex(
    const u16 controllerIds[OWBD_CONTROLLER_COUNT],
    u16 controllerId,
    u8 *indexOut)
{
    u8 index;
    for (index = 0; index < OWBD_CONTROLLER_COUNT; index++) {
        if (controllerIds[index] != controllerId) continue;
        if (indexOut != NULL) *indexOut = index;
        return TRUE;
    }
    return FALSE;
}

static BOOL SerializedControllerProfileNodeMatches(
    const OverworldWildBehaviorDataBlobHeader *header,
    u16 controllerId,
    u16 profileId,
    u8 semanticRole)
{
    OverworldWildControllerNodeRecord node;
    u16 index;
    u8 matchCount = 0;
    for (index = 0; index < header->controllerNodes.count; index++) {
        if (!CopyCatalogRecord(header, &header->controllerNodes, index,
                &node, sizeof(node)))
            return FALSE;
        if (node.controllerId != controllerId
            || node.profileIdentityId != profileId
            || node.semanticRole != semanticRole)
            continue;
        if (node.stableId == 0 || node.reserved != 0) return FALSE;
        matchCount++;
    }
    return matchCount == 1;
}

static BOOL CopyForcedAsleepSemanticSource(
    const OverworldWildBehaviorDataBlobHeader *header,
    OverworldWildOverrideSourceRecord *sourceOut)
{
    OverworldWildOverrideSourceRecord source;
    u16 index;
    u8 matchCount = 0;
    memset(sourceOut, 0, sizeof(*sourceOut));
    for (index = 0; index < header->overrideSources.count; index++) {
        if (!CopyCatalogRecord(header, &header->overrideSources, index,
                &source, sizeof(source)))
            return FALSE;
        if (source.match.behaviorClass
                != OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP)
            continue;
        if (source.stableId == 0 || source.actionCount == 0)
            return FALSE;
        if (matchCount++ == 0) *sourceOut = source;
    }
    return matchCount == 1;
}

static BOOL TiredTranslationBacklinkMatches(
    const OverworldWildBehaviorDataBlobHeader *header,
    const OverworldWildOverrideDefinitionRecord *definition,
    const OverworldWildTransitionRecord *transition)
{
    OverworldWildTiredTranslationRecord translation;
    u16 installedControllers[OWBD_CONTROLLER_COUNT];
    u8 coveredControllers[OWBD_CONTROLLER_COUNT];
    u16 index;
    u8 controllerCount = 0;
    BOOL exact = definition->selectorKind == OWBD_SELECTOR_EXACT;
    if (!CopyInstalledControllerIds(header, installedControllers))
        return FALSE;
    memset(coveredControllers, 0, sizeof(coveredControllers));
    for (index = 0; index < header->tiredTranslations.count; index++) {
        u8 controllerIndex;
        if (!CopyCatalogRecord(header, &header->tiredTranslations, index,
                &translation, sizeof(translation)))
            return FALSE;
        if (translation.candidateDefinitionId != definition->stableId
            && translation.recoveryTransitionId != transition->stableId)
            continue;
        if (translation.candidateDefinitionId != definition->stableId
            || translation.recoveryTransitionId != transition->stableId
            || translation.stableId == 0
            || translation.tiredOriginKind
                != definition->tiredOriginKind
            || translation.destinationControllerId == 0
            || translation.authoredProfileId == 0
            || translation.timerOperator != OWBD_CANDIDATE_TIMER_SET
            || translation.timerSource != OWBD_TIMER_SOURCE_FIXED
            || translation.mapLifetime != OWBD_LIFETIME_PRESERVE_LOGICAL
            || translation.battleLifetime != OWBD_LIFETIME_CLEAR
            || translation.flags != 0 || translation.reserved != 0
            || controllerCount >= OWBD_CONTROLLER_COUNT
            || !InstalledControllerIndex(installedControllers,
                translation.destinationControllerId, &controllerIndex)
            || coveredControllers[controllerIndex])
            return FALSE;
        coveredControllers[controllerIndex] = TRUE;
        controllerCount++;
        if (exact) {
            if (translation.authoredTiredBound
                || translation.destinationControllerId
                    != definition->controllerId
                || translation.exactFallbackControllerId
                    != definition->controllerId
                || translation.exactFallbackNodeId != definition->nodeId
                || !SerializedNodeBacklinkMatches(header,
                    definition->nodeId, definition->controllerId,
                    translation.authoredProfileId, OWBD_ROLE_CUSTOM))
                return FALSE;
        } else if (!translation.authoredTiredBound
            || translation.exactFallbackControllerId != 0
            || translation.exactFallbackNodeId != 0
            || !SerializedControllerProfileNodeMatches(header,
                translation.destinationControllerId,
                translation.authoredProfileId, OWBD_ROLE_TIRED)) {
            return FALSE;
        }
    }
    return controllerCount == (exact ? 1 : OWBD_CONTROLLER_COUNT);
}

static BOOL ForcedSleepBacklinkMatches(
    const OverworldWildBehaviorDataBlobHeader *header,
    const OverworldWildOverrideDefinitionRecord *definition,
    const OverworldWildTransitionRecord *transition)
{
    OverworldWildImportRecipeRecord recipe;
    OverworldWildOverrideDefinitionRecord candidate;
    OverworldWildOverrideSourceRecord semanticSource;
    u16 installedControllers[OWBD_CONTROLLER_COUNT];
    u8 coveredControllers[OWBD_CONTROLLER_COUNT];
    u16 index;
    u8 controllerCount = 0;
    u8 definitionCount = 0;
    if (!CopyInstalledControllerIds(header, installedControllers)
        || !CopyForcedAsleepSemanticSource(header, &semanticSource))
        return FALSE;
    memset(coveredControllers, 0, sizeof(coveredControllers));
    for (index = 0; index < header->overrideDefinitions.count; index++) {
        if (!CopyCatalogRecord(header, &header->overrideDefinitions, index,
                &candidate, sizeof(candidate)))
            return FALSE;
        if (candidate.recoveryTransitionId != transition->stableId) continue;
        if (candidate.stableId != definition->stableId) return FALSE;
        definitionCount++;
    }
    if (definitionCount != 1) return FALSE;
    for (index = 0; index < header->importRecipes.count; index++) {
        u8 controllerIndex;
        if (!CopyCatalogRecord(header, &header->importRecipes, index,
                &recipe, sizeof(recipe)))
            return FALSE;
        if (recipe.recoveryTransitionId != transition->stableId
            && !(recipe.ownerId == 0x810A
                && recipe.semanticRole == OWBD_ROLE_ASLEEP))
            continue;
        if (recipe.recoveryTransitionId != transition->stableId
            || recipe.ownerId != 0x810A
            || recipe.semanticRole != OWBD_ROLE_ASLEEP
            || recipe.controllerId == 0 || recipe.nodeId == 0
            || recipe.profileIdentityId == 0
            || recipe.semanticSourceId != semanticSource.stableId
            || recipe.actionStart != semanticSource.actionStart
            || recipe.actionCount != semanticSource.actionCount
            || recipe.truthVector != 0xFFFF
            || recipe.lifetime != OWBD_LIFETIME_PRESERVE_LOGICAL
            || recipe.flags != 0 || recipe.reserved != 0
            || controllerCount >= OWBD_CONTROLLER_COUNT
            || !InstalledControllerIndex(installedControllers,
                recipe.controllerId, &controllerIndex)
            || coveredControllers[controllerIndex]
            || !SerializedNodeBacklinkMatches(header, recipe.nodeId,
                recipe.controllerId, recipe.profileIdentityId,
                OWBD_ROLE_ASLEEP))
            return FALSE;
        coveredControllers[controllerIndex] = TRUE;
        controllerCount++;
    }
    return controllerCount == OWBD_CONTROLLER_COUNT;
}

static BOOL ValidateRecoveryCatalogClosure(
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeRecoveryPlan *planOut)
{
    OverworldWildBehaviorDataBlobHeader header;
    OverworldWildTransitionRecord transition = {0};
    OverworldWildTransitionRecord candidate;
    OverworldWildTransitionGuardRecord guard;
    OverworldWildTransitionOperationRecord operation;
    OverworldWildTransitionActionRecord action;
    OverworldWildTransitionRecord staminaTransition;
    OverworldWildRecoveryActionRecord recovery;
    OverworldWildOverrideDefinitionRecord definition = {0};
    OverworldWildOverrideDefinitionRecord definitionCandidate;
    u16 stableIds[12];
    u16 index;
    u8 stableIdCount = 0;
    u8 definitionMatchCount = 0;
    u8 expectedActionCount;
    u8 expectedFromRoleMask;
    u8 expectedRoute;
    BOOL found = FALSE;
    memset(planOut, 0, sizeof(*planOut));
    if (!CopyCatalogHeader(&header)) return FALSE;
    for (index = 0; index < header.transitions.count; index++) {
        if (!CopyCatalogRecord(&header, &header.transitions, index,
                &candidate, sizeof(candidate))) return FALSE;
        if (candidate.stableId != expiry->recoveryTransitionId) continue;
        if (found) return FALSE;
        transition = candidate;
        found = TRUE;
    }
    for (index = 0; index < header.overrideDefinitions.count; index++) {
        if (!CopyCatalogRecord(&header, &header.overrideDefinitions, index,
                &definitionCandidate, sizeof(definitionCandidate)))
            return FALSE;
        if (definitionCandidate.stableId != expiry->definitionId) continue;
        if (definitionMatchCount++ == 0) definition = definitionCandidate;
    }
    if (!found || definitionMatchCount != 1)
        return FALSE;
    if (!AddRecoveryStableId(stableIds, &stableIdCount,
            transition.stableId)
        || !AddRecoveryStableId(stableIds, &stableIdCount,
            definition.stableId)
        || transition.trigger != OWBD_TRIGGER_TIRED_EXPIRED
        || transition.candidateDefinitionId != expiry->definitionId
        || transition.ownerId != expiry->ownerId
        || transition.guardCount != 1
        || (transition.operationCount != 1
            && transition.operationCount
                != OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS + 1)
        || transition.recoveryCount != 1 || transition.dispatchPriority == 0
        || definition.stableId != expiry->definitionId
        || definition.recoveryTransitionId != transition.stableId
        || definition.kind != OWBD_OVERRIDE_KIND_STATE_CANDIDATE
        || definition.timerClock == OWBD_TIMER_CLOCK_NONE
        || definition.recoveryPolicy != OWBD_RECOVERY_ROUTE_TRANSITION
        || definition.hasTiredOriginKind > 1
        || definition.hasRequiredOwnerId > 1
        || definition.allowMultipleOwners > 1
        || definition.allowMultipleInstancesPerOwner > 1
        || (!definition.hasTiredOriginKind
            && definition.tiredOriginKind != 0)
        || definition.flags
            != (definition.selectorKind == OWBD_SELECTOR_EXACT ? 1 : 0)
        || definition.reserved0 != 0
        || definition.reserved1 != 0
        || (definition.hasRequiredOwnerId
            && definition.requiredOwnerId != expiry->ownerId))
        return FALSE;
    if (definition.hasTiredOriginKind
        || definition.semanticRole == OWBD_ROLE_TIRED) {
        if (!definition.hasRequiredOwnerId
            || definition.requiredOwnerId != expiry->ownerId
            || definition.allowMultipleOwners
            || definition.allowMultipleInstancesPerOwner)
            return FALSE;
        if (definition.selectorKind == OWBD_SELECTOR_EXACT) {
            if (definition.controllerId == 0 || definition.nodeId == 0
                || definition.semanticRole != 0
                || definition.authoredTiredBound != 0
                || definition.flags != 1)
                return FALSE;
        } else if (definition.selectorKind
                != OWBD_SELECTOR_SEMANTIC_ROLE
            || definition.controllerId != 0 || definition.nodeId != 0
            || definition.semanticRole != OWBD_ROLE_TIRED
            || definition.authoredTiredBound != 0
            || definition.flags != 0) {
            return FALSE;
        }
        if (!definition.hasTiredOriginKind) {
            if (definition.selectorKind
                    != OWBD_SELECTOR_SEMANTIC_ROLE
                || definition.semanticRole != OWBD_ROLE_TIRED
                || expiry->ownerId != 0x8105
                || !CopyTransitionForTrigger(&header,
                    OWBD_TRIGGER_STAMINA_EXHAUSTED,
                    &staminaTransition)
                || staminaTransition.candidateDefinitionId
                    != definition.stableId
                || staminaTransition.ownerId != expiry->ownerId)
                return FALSE;
            expectedRoute = OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM;
        } else if (definition.tiredOriginKind == OWBD_TIRED_ORIGIN_FLED) {
            if (expiry->ownerId != 0x8107) return FALSE;
            expectedRoute = OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF;
        } else if (definition.tiredOriginKind
                == OWBD_TIRED_ORIGIN_RAM_CRASH) {
            if (expiry->ownerId != 0x8106) return FALSE;
            expectedRoute = OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM;
        } else if (definition.tiredOriginKind
                == OWBD_TIRED_ORIGIN_THROW_RECOVERY) {
            if (expiry->ownerId != 0x8108) return FALSE;
            expectedRoute = OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM;
        } else {
            return FALSE;
        }
        if (definition.hasTiredOriginKind
            && !TiredTranslationBacklinkMatches(
                &header, &definition, &transition))
            return FALSE;
        expectedActionCount = 2;
        expectedFromRoleMask = definition.selectorKind == OWBD_SELECTOR_EXACT
            ? OWBD_ROLE_MASK(OWBD_ROLE_CUSTOM) : 0x7F;
    } else if (definition.semanticRole == OWBD_ROLE_ASLEEP
        && definition.selectorKind == OWBD_SELECTOR_SEMANTIC_ROLE
        && definition.requiredOwnerId == 0
        && !definition.hasRequiredOwnerId
        && !definition.allowMultipleOwners
        && definition.allowMultipleInstancesPerOwner
        && definition.controllerId == 0 && definition.nodeId == 0
        && definition.authoredTiredBound == 0
        && definition.flags == 0
        && definition.hiddenTimerPolicy
            == OWBD_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN) {
        if (expiry->ownerId != 0x810A
            || !ForcedSleepBacklinkMatches(
                &header, &definition, &transition))
            return FALSE;
        expectedRoute = OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF;
        expectedActionCount = 1;
        expectedFromRoleMask = 0x7F;
    } else {
        return FALSE;
    }
    if (transition.fromRoleMask != expectedFromRoleMask
        || transition.operationCount
            != (expectedRoute == OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF
                ? 1 : OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS + 1)
        || transition.actionCount != expectedActionCount
        || !CopyCatalogRecord(&header, &header.transitionGuards,
            transition.guardStart, &guard, sizeof(guard))
        || !AddRecoveryStableId(stableIds, &stableIdCount, guard.stableId)
        || guard.transitionId != transition.stableId
        || guard.kind != OWBD_GUARD_CANDIDATE_TIMER_EXPIRED
        || guard.negate || guard.payload != OWBD_TRIGGER_TIRED_EXPIRED
        || guard.reserved0 || guard.referenceId || guard.reserved)
        return FALSE;
    planOut->transitionId = transition.stableId;
    planOut->candidateDefinitionId = transition.candidateDefinitionId;
    planOut->ownerId = transition.ownerId;
    for (index = 0; index < transition.operationCount; index++) {
        if (!CopyCatalogRecord(&header, &header.transitionOperations,
                (u16)(transition.operationStart + index), &operation,
                sizeof(operation))
            || operation.transitionId != transition.stableId)
            return FALSE;
        if (!AddRecoveryStableId(stableIds, &stableIdCount,
                operation.stableId)
            || operation.busyPolicy != OWBD_BUSY_REJECT
            || operation.reserved)
            return FALSE;
        if (index == 0) {
            if (operation.kind != OWBD_TRANSITION_REMOVE_REQUIRED
                || !operation.required
                || operation.definitionId != expiry->definitionId
                || operation.ownerId != expiry->ownerId
                || operation.replacementDefinitionId != 0
                || operation.policyId != 0
                || operation.instanceKey != 0)
                return FALSE;
            continue;
        }
        if (operation.kind != OWBD_TRANSITION_REMOVE_OWNER_IF_PRESENT
            || operation.required
            || operation.ownerId == 0
            || operation.ownerId != (u16)(0x8101 + index)
            || operation.definitionId != 0
            || operation.replacementDefinitionId != 0
            || operation.policyId != 0 || operation.instanceKey != 0)
            return FALSE;
        {
            u8 priorIndex;
            for (priorIndex = 0;
                    priorIndex < planOut->calmResetOwnerCount; priorIndex++)
                if (planOut->calmResetOwnerIds[priorIndex]
                        == operation.ownerId)
                    return FALSE;
        }
        planOut->calmResetOwnerIds[planOut->calmResetOwnerCount++] =
            operation.ownerId;
    }
    for (index = 0; index < transition.actionCount; index++) {
        u8 flag;
        if (!CopyCatalogRecord(&header, &header.transitionActions,
                (u16)(transition.actionStart + index), &action,
                sizeof(action))
            || action.transitionId != transition.stableId
            || !AddRecoveryStableId(stableIds, &stableIdCount,
                action.stableId)
            || action.phase != OWBD_ACTION_PHASE_EXIT
            || action.referenceId != 0 || action.payload != 0)
            return FALSE;
        if (index == 0 && action.kind == OWBD_ACTION_RESET_TIRED_COUNTER)
            flag = OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER;
        else if (index == 1
            && action.kind == OWBD_ACTION_START_POST_TIRED_COOLDOWN)
            flag = OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN;
        else
            return FALSE;
        planOut->actionFlags |= flag;
    }
    if (!CopyCatalogRecord(&header, &header.recoveryActions,
            transition.recoveryStart, &recovery, sizeof(recovery))
        || !AddRecoveryStableId(stableIds, &stableIdCount,
            recovery.stableId)
        || recovery.transitionId != transition.stableId
        || recovery.ownerId != expiry->ownerId || !recovery.required)
        return FALSE;
    if (expectedRoute == OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF
        && recovery.kind == OWBD_RECOVERY_ACTION_REMOVE_SELF
        && planOut->calmResetOwnerCount == 0)
        planOut->route = OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF;
    else if (expectedRoute
            == OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM
        && recovery.kind == OWBD_RECOVERY_ACTION_REMOVE_OWNER_IF_PRESENT
        && planOut->calmResetOwnerCount
            == OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS)
        planOut->route = OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM;
    else
        return FALSE;
    return TRUE;
}
#endif

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
static BOOL CopyRecoveryPlan(
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeRecoveryPlan *planOut)
{
    OverworldWildRuntimeDefinition definition;
    u8 index;
    BOOL hasOrigin;

    memset(planOut, 0, sizeof(*planOut));
    if (expiry->recoveryPolicy != OWBD_RECOVERY_ROUTE_TRANSITION
        || !OverworldWildRuntime_CopyInstalledDefinition(
            expiry->definitionId, &definition))
        return FALSE;
    /* RecoverExpiredTimer authenticated the complete expiry tuple against
     * the live timer immediately before this call. That timer metadata came
     * from the immutable installed definition, so repeating its transition
     * lookup here cannot strengthen the identity check. */
    hasOrigin = (definition.flags
        & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_TIRED_ORIGIN) != 0;
    if ((hasOrigin || definition.semanticRole == OWBD_ROLE_TIRED)
        && (definition.flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
        && definition.requiredOwnerId == expiry->ownerId
        && (!hasOrigin || (definition.tiredOriginKind >= OWBD_TIRED_ORIGIN_FLED
            && definition.tiredOriginKind
                <= OWBD_TIRED_ORIGIN_THROW_RECOVERY))) {
        planOut->actionFlags =
            OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER
                | OW_WILD_RUNTIME_RECOVERY_ACTION_START_POST_TIRED_COOLDOWN;
        if (hasOrigin
            && definition.tiredOriginKind == OWBD_TIRED_ORIGIN_FLED) {
            planOut->route = OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF;
            return TRUE;
        }
        /* OwbdValidateStream fixes the legacy calm-reset owner closure to
         * owner records 0x8102..0x8104 in canonical operation order. */
        for (index = 0; index < OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS; index++)
            planOut->calmResetOwnerIds[index] = (u16)(0x8102 + index);
        planOut->calmResetOwnerCount = OW_WILD_RUNTIME_MAX_CALM_RESET_OWNERS;
        planOut->route =
            OW_WILD_RUNTIME_TIMER_RECOVERY_LEGACY_RETURN_CALM;
        return TRUE;
    }
    /* The same validator pins the sole non-owner-bound asleep recovery to
     * the forced-asleep import owner (0x810A) and a remove-self route. */
    if (!hasOrigin && definition.selectorKind
            == OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
        && definition.semanticRole == OWBD_ROLE_ASLEEP
        && !(definition.flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_HAS_REQUIRED_OWNER)
        && (definition.flags
            & OW_WILD_RUNTIME_DEFINITION_FLAG_MULTIPLE_INSTANCES)
        && expiry->ownerId == 0x810A) {
        planOut->actionFlags =
            OW_WILD_RUNTIME_RECOVERY_ACTION_RESET_TIRED_COUNTER;
        planOut->route = OW_WILD_RUNTIME_TIMER_RECOVERY_REMOVE_SELF;
        return TRUE;
    }
    return FALSE;
}
#endif

#if defined(OW_WILD_RUNTIME_HOST_TEST) \
    || defined(OW_WILD_RUNTIME_ACCESSOR_HOST_TEST)
static void InitRecoveryResult(
    const OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeTimerRecoveryResult *result)
{
    memset(result, 0, sizeof(*result));
    if (runtime == NULL || expiry == NULL
        || expiry->slotIndex >= OW_WILD_MAX_SPAWNS) return;
    result->runtimeEpochBefore = result->runtimeEpochAfter =
        runtime->handleEpoch;
    result->slotGeneration = runtime->slots[expiry->slotIndex].slotGeneration;
    result->layerGenerationBefore = result->layerGenerationAfter =
        runtime->slots[expiry->slotIndex].layerGeneration;
    result->effectiveGenerationBefore = result->effectiveGenerationAfter =
        runtime->slots[expiry->slotIndex].effectiveGeneration;
    result->slotIndex = expiry->slotIndex;
    result->recoveryTransitionId = expiry->recoveryTransitionId;
}

static OverworldWildRuntimeStatus FinishRecovery(
    OverworldWildRuntimeTimerRecoveryResult *result,
    OverworldWildRuntimeStatus status,
    BOOL ok)
{
    result->status = status;
    result->ok = ok;
    return status;
}

OverworldWildRuntimeStatus OverworldWildRuntime_RecoverExpiredTimer(
    OverworldWildBehaviorStackRuntime *runtime,
    const OverworldWildRuntimeTimerExpiry *expiry,
    OverworldWildRuntimeTimerRecoveryResult *result)
{
    OverworldWildRuntimeStackDeltaRequest request;
    OverworldWildRuntimeStackDeltaResult deltaResult;
    OverworldWildRuntimeRecoveryPlan plan;
    OverworldWildRuntimeLayerHandle handle;
    OverworldWildRuntimeSlotSidecar *slot;
    OverworldWildRuntimeStatus status;
    u8 layerIndex;
    if (result == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    InitRecoveryResult(runtime, expiry, result);
    status = OverworldWildRuntime_PreflightTimerExpiryInternal(runtime, expiry);
    if (status == OW_WILD_RUNTIME_STATUS_STALE_NOOP)
        return FinishRecovery(result, status, TRUE);
    if (status != OW_WILD_RUNTIME_STATUS_OK || expiry == NULL)
        return FinishRecovery(result, OW_WILD_RUNTIME_STATUS_INVALID_HANDLE,
            FALSE);
    status = OverworldWildRuntime_ValidateTimerQueryInternal(runtime,
        expiry->slotIndex, expiry->slotGeneration);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishRecovery(result, status, FALSE);
    slot = &runtime->slots[expiry->slotIndex];
    for (layerIndex = 0; layerIndex < slot->activeLayerCount; layerIndex++) {
        const OverworldWildRuntimeTimer *timer =
            &slot->timerBank.timers[layerIndex];
        if (slot->layerBank.ownerIds[layerIndex] != expiry->ownerId
            || slot->layerBank.instanceKeys[layerIndex] != expiry->instanceKey)
            continue;
        if ((timer->flags & (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING))
                != (OW_WILD_RUNTIME_TIMER_VALID
                    | OW_WILD_RUNTIME_TIMER_ZERO_PENDING)
            || timer->entryGeneration != expiry->entryGeneration
            || timer->timerGeneration != expiry->timerGeneration
            || timer->definitionId != expiry->definitionId
            || timer->recoveryTransitionId != expiry->recoveryTransitionId
            || timer->recoveryPolicy != expiry->recoveryPolicy)
            return FinishRecovery(result,
                OW_WILD_RUNTIME_STATUS_STALE_NOOP, TRUE);
        break;
    }
    if (layerIndex == slot->activeLayerCount)
        return FinishRecovery(result, OW_WILD_RUNTIME_STATUS_STALE_NOOP, TRUE);
    if (!CopyRecoveryPlan(expiry, &plan))
        return FinishRecovery(result,
            OW_WILD_RUNTIME_STATUS_INVALID_TRANSLATION, FALSE);
    status = OverworldWildRuntime_MakeTimerRemovalHandleInternal(runtime,
        expiry->slotIndex, layerIndex, &handle);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishRecovery(result, status, FALSE);
    memset(&request, 0, sizeof(request));
    request.expectedSlotGeneration = expiry->slotGeneration;
    request.slotIndex = expiry->slotIndex;
    request.operationCount = (u8)(plan.calmResetOwnerCount + 1);
    request.operations[0].operationId = 1;
    request.operations[0].kind = OW_WILD_RUNTIME_DELTA_REMOVE_REQUIRED;
    request.operations[0].payload.handle = handle;
    for (layerIndex = 0; layerIndex < plan.calmResetOwnerCount; layerIndex++) {
        OverworldWildRuntimeDeltaOperation *operation =
            &request.operations[layerIndex + 1];
        operation->operationId = (u16)(layerIndex + 2);
        operation->kind = OW_WILD_RUNTIME_DELTA_REMOVE_OWNER_IF_PRESENT;
        operation->payload.owner.ownerId = plan.calmResetOwnerIds[layerIndex];
    }
    status = OverworldWildRuntime_ApplyStackDelta(
        runtime, &request, &deltaResult);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return FinishRecovery(result, status, FALSE);
    result->runtimeEpochAfter = deltaResult.runtimeEpochAfter;
    result->slotGeneration = deltaResult.slotGenerationAfter;
    result->layerGenerationAfter = deltaResult.layerGenerationAfter;
    result->effectiveGenerationAfter = deltaResult.effectiveGenerationAfter;
    result->mutated = deltaResult.mutated;
    result->route = plan.route;
    result->actionFlags = plan.actionFlags;
    result->calmResetOwnerCount = plan.calmResetOwnerCount;
    result->calmResetOwnerIds[0] = plan.calmResetOwnerIds[0];
    result->calmResetOwnerIds[1] = plan.calmResetOwnerIds[1];
    result->calmResetOwnerIds[2] = plan.calmResetOwnerIds[2];
    return FinishRecovery(result, OW_WILD_RUNTIME_STATUS_OK, TRUE);
}
#endif

static OverworldWildRuntimeStatus CopyCommandOrigin(
    const OverworldWildBehaviorStackRuntime *runtime,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeCommandIdentity *identity,
    OverworldWildRuntimeCommandOrigin *originOut)
{
    OverworldWildRuntimeEffectiveCache effective;
    OverworldWildRuntimeProvenance provenance;
    OverworldWildRuntimeStatus status;
    const OverworldWildRuntimeSlotSidecar *slot;
    u8 layerIndex;
    status = OverworldWildRuntime_GetEffectiveCache(runtime, slotIndex,
        expectedSlotGeneration, &effective);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    status = OverworldWildRuntime_GetProvenance(runtime, slotIndex,
        expectedSlotGeneration, &provenance);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    slot = &runtime->slots[slotIndex];
    memset(originOut, 0, sizeof(*originOut));
    originOut->runtimeEpoch = runtime->handleEpoch;
    originOut->slotGeneration = expectedSlotGeneration;
    originOut->commandGeneration = identity->commandGeneration;
    originOut->commandSerial = identity->commandSerial;
    originOut->effectiveGeneration = effective.effectiveGeneration;
    originOut->objectGeneration = identity->objectGeneration;
    originOut->staminaPolicyGeneration = identity->staminaPolicyGeneration;
    originOut->staminaPolicyId = identity->staminaPolicyId;
    originOut->controllerId = effective.controllerId;
    originOut->nodeId = effective.nodeId;
    originOut->stateProfileId = effective.profileId;
    originOut->winningDefinitionId = provenance.winningDefinitionId;
    originOut->winningOwnerId = provenance.winningOwnerId;
    originOut->winningInstanceKey = provenance.winningInstanceKey;
    originOut->slotIndex = slotIndex;
    originOut->flags = OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID;
    if (originOut->controllerId == 0 || originOut->nodeId == 0
        || originOut->stateProfileId == 0
        || originOut->effectiveGeneration == 0)
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    if (originOut->winningDefinitionId == 0
        && originOut->winningOwnerId == 0
        && originOut->winningInstanceKey == 0) {
        originOut->winnerKind = OW_WILD_RUNTIME_COMMAND_WINNER_BASE;
    } else if (originOut->winningDefinitionId != 0
        && originOut->winningOwnerId != 0) {
        originOut->winnerKind = OW_WILD_RUNTIME_COMMAND_WINNER_LAYER;
        for (layerIndex = 0; layerIndex < slot->activeLayerCount; layerIndex++)
            if (slot->layerBank.ownerIds[layerIndex]
                    == originOut->winningOwnerId
                && slot->layerBank.instanceKeys[layerIndex]
                    == originOut->winningInstanceKey
                && slot->layerBank.definitionIds[layerIndex]
                    == originOut->winningDefinitionId) {
                originOut->winningEntryGeneration =
                    slot->layerBank.entryGenerations[layerIndex];
                break;
            }
        if (layerIndex == slot->activeLayerCount)
            return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    } else {
        return OW_WILD_RUNTIME_STATUS_INVALID_COMPOSITION;
    }
    return OW_WILD_RUNTIME_STATUS_OK;
}

static BOOL CommandIdentityValid(
    const OverworldWildRuntimeCommandIdentity *identity)
{
    return identity != NULL && identity->commandGeneration != 0
        && identity->commandSerial != 0 && identity->objectGeneration != 0
        && identity->staminaPolicyId != 0
        && identity->staminaPolicyGeneration != 0
        && identity->reserved[0] == 0 && identity->reserved[1] == 0;
}

static BOOL CommandOriginsEqual(
    const OverworldWildRuntimeCommandOrigin *left,
    const OverworldWildRuntimeCommandOrigin *right)
{
    const u8 *leftBytes = (const u8 *)left;
    const u8 *rightBytes = (const u8 *)right;
    u32 remaining = sizeof(*left);
    while (remaining-- != 0)
        if (*leftBytes++ != *rightBytes++) return FALSE;
    return TRUE;
}

OverworldWildRuntimeStatus OverworldWildRuntime_CaptureCommandOrigin(
    const OverworldWildBehaviorStackRuntime *runtime,
    OverworldWildRuntimeCommandOriginBank *bank,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeCommandIdentity *identity)
{
    OverworldWildRuntimeCommandOrigin origin;
    OverworldWildRuntimeStatus status;
    if (bank == NULL || !CommandIdentityValid(identity)
        || slotIndex >= OW_WILD_MAX_SPAWNS)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    if (bank->records[slotIndex].flags & OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID)
        return OW_WILD_RUNTIME_STATUS_DATA_BUSY;
    status = CopyCommandOrigin(runtime, slotIndex,
        expectedSlotGeneration, identity, &origin);
    if (status != OW_WILD_RUNTIME_STATUS_OK) return status;
    bank->records[slotIndex] = origin;
    return OW_WILD_RUNTIME_STATUS_OK;
}

OverworldWildRuntimeStatus OverworldWildRuntime_ConsumeCommandOrigin(
    const OverworldWildBehaviorStackRuntime *runtime,
    OverworldWildRuntimeCommandOriginBank *bank,
    u8 slotIndex,
    u32 expectedSlotGeneration,
    const OverworldWildRuntimeCommandIdentity *identity,
    OverworldWildRuntimeCommandOrigin *originOut)
{
    OverworldWildRuntimeCommandOrigin current;
    OverworldWildRuntimeCommandOrigin *captured;
    OverworldWildRuntimeStatus status;
    if (originOut == NULL) return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    memset(originOut, 0, sizeof(*originOut));
    if (bank == NULL || !CommandIdentityValid(identity)
        || slotIndex >= OW_WILD_MAX_SPAWNS)
        return OW_WILD_RUNTIME_STATUS_INVALID_HANDLE;
    captured = &bank->records[slotIndex];
    if (!(captured->flags & OW_WILD_RUNTIME_COMMAND_ORIGIN_VALID)
        || captured->slotIndex != slotIndex
        || captured->slotGeneration != expectedSlotGeneration
        || captured->commandGeneration != identity->commandGeneration
        || captured->commandSerial != identity->commandSerial
        || captured->objectGeneration != identity->objectGeneration
        || captured->staminaPolicyId != identity->staminaPolicyId
        || captured->staminaPolicyGeneration
            != identity->staminaPolicyGeneration)
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    status = CopyCommandOrigin(runtime, slotIndex,
        expectedSlotGeneration, identity, &current);
    if (status != OW_WILD_RUNTIME_STATUS_OK)
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    if (!CommandOriginsEqual(captured, &current))
        return OW_WILD_RUNTIME_STATUS_STALE_NOOP;
    *originOut = *captured;
    memset(captured, 0, sizeof(*captured));
    return OW_WILD_RUNTIME_STATUS_OK;
}

void OverworldWildRuntime_InvalidateCommandOrigin(
    OverworldWildRuntimeCommandOriginBank *bank,
    u8 slotIndex)
{
    if (bank != NULL && slotIndex < OW_WILD_MAX_SPAWNS)
        memset(&bank->records[slotIndex], 0,
            sizeof(bank->records[slotIndex]));
}

void OverworldWildRuntime_InvalidateAllCommandOrigins(
    OverworldWildRuntimeCommandOriginBank *bank)
{
    if (bank != NULL) memset(bank, 0, sizeof(*bank));
}
