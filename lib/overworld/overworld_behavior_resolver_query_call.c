#include "../../include/overworld_behavior_resolver_private_call.h"
#include "../../include/overworld_behavior_condition_runtime.h"

BOOL OverworldBehaviorResolver_QueryCall(OverworldBehaviorResolverCall *call)
{
    if (call == NULL || call->version != OVERWORLD_BEHAVIOR_RESOLVER_CALL_VERSION
        || call->size != sizeof(*call) || call->reserved[0] != 0
        || call->reserved[1] != 0 || call->reserved[2] != 0)
        return FALSE;

    switch (call->operation) {
    case OVERWORLD_BEHAVIOR_RESOLVER_CALL_VALIDATE: {
        if (call->output.validatedBank == NULL || call->trace != NULL)
            return FALSE;
        call->status = OverworldBehaviorResolver_ValidateRequest(
            call->blobBytes, call->blobSize, call->request,
            call->output.validatedBank);
        return TRUE;
    }
    case OVERWORLD_BEHAVIOR_RESOLVER_CALL_RESOLVE:
        call->status = BehaviorResolver_Resolve(
            call->blobBytes, call->blobSize, call->request,
            call->output.result, call->trace);
        return TRUE;
    case OVERWORLD_BEHAVIOR_RESOLVER_CALL_INSPECT_CLASS:
        call->status = BehaviorResolver_InspectClass(
            call->blobBytes, call->blobSize, call->request,
            call->output.selection, call->trace);
        return TRUE;
    default:
        return FALSE;
    }
}
