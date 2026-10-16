#include "../../include/overworld_behavior_resolver.h"
#include "../../include/overworld_behavior_condition_runtime.h"
#include "../../include/overworld_behavior_resolver_private_call.h"

static BehaviorResolveStatus Resolver_Dispatch(
    const void *blob, u32 blobSize, const BehaviorResolveRequest *request,
    void *output, BehaviorResolutionTrace *trace, u8 operation)
{
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
    const OverworldBehaviorConditionServiceEntry *service =
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY;
#else
    const OverworldBehaviorConditionServiceEntry *service =
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE();
#endif
    OverworldBehaviorResolverCall call = {0};

    if (service == NULL
        || service->magic != OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC
        || service->version != OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        || service->size != sizeof(*service) || service->resolverCall == NULL)
        return BEHAVIOR_RESOLVE_INVALID_CONTEXT;
    call.version = OVERWORLD_BEHAVIOR_RESOLVER_CALL_VERSION;
    call.size = sizeof(call);
    call.operation = operation;
    call.blobBytes = blob;
    call.blobSize = blobSize;
    call.request = request;
    call.output.result = output;
    call.trace = trace;
    return service->resolverCall(&call)
        ? call.status : BEHAVIOR_RESOLVE_INVALID_CONTEXT;
}

BehaviorResolveStatus BehaviorResolver_Resolve(
    const void *blob, u32 blobSize, const BehaviorResolveRequest *request,
    BehaviorResolveResult *result, BehaviorResolutionTrace *trace)
{
    if (request == NULL || result == NULL)
        return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;
    /* Match the portable resolver's invalid-context output contract even
     * when the current Field has no loaded Query owner. */
    memset(result, 0, sizeof(*result));
    result->winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    result->resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    result->targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    if (trace != NULL) {
        trace->count = 0;
        trace->dropped = 0;
        trace->reserved = 0;
    }
    return Resolver_Dispatch(blob, blobSize, request, result, trace,
        OVERWORLD_BEHAVIOR_RESOLVER_CALL_RESOLVE);
}

BehaviorResolveStatus BehaviorResolver_InspectClass(
    const void *blob, u32 blobSize, const BehaviorResolveRequest *request,
    BehaviorClassSelection *selection, BehaviorResolutionTrace *trace)
{
    if (request == NULL || selection == NULL)
        return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;
    memset(selection, 0, sizeof(*selection));
    if (trace != NULL) {
        trace->count = 0;
        trace->dropped = 0;
        trace->reserved = 0;
    }
    return Resolver_Dispatch(blob, blobSize, request, selection, trace,
        OVERWORLD_BEHAVIOR_RESOLVER_CALL_INSPECT_CLASS);
}
