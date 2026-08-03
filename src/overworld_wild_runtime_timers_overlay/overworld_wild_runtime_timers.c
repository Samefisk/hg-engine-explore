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
