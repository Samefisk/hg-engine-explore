#ifndef OVERWORLD_BEHAVIOR_RESOLVER_PRIVATE_CALL_H
#define OVERWORLD_BEHAVIOR_RESOLVER_PRIVATE_CALL_H

#include "overworld_behavior_resolver.h"
#include "overworld_application_bank.h"

#define OVERWORLD_BEHAVIOR_RESOLVER_CALL_VERSION 1
#define OVERWORLD_BEHAVIOR_RESOLVER_CALL_VALIDATE 1
#define OVERWORLD_BEHAVIOR_RESOLVER_CALL_RESOLVE 2
#define OVERWORLD_BEHAVIOR_RESOLVER_CALL_INSPECT_CLASS 3

/* A borrowed, synchronous request. Query does not keep any pointer. The
 * caller owns every output and the immutable Blob for the full call. */
typedef struct OverworldBehaviorResolverCall {
    u16 version, size;
    u8 operation, reserved[3];
    const void *blobBytes;
    u32 blobSize;
    const BehaviorResolveRequest *request;
    union {
        OverworldApplicationBank *validatedBank;
        BehaviorResolveResult *result;
        BehaviorClassSelection *selection;
    } output;
    BehaviorResolutionTrace *trace;
    BehaviorResolveStatus status;
} OverworldBehaviorResolverCall;

typedef BOOL (*OverworldBehaviorResolverCallFunc)(OverworldBehaviorResolverCall *);
BOOL OverworldBehaviorResolver_QueryCall(OverworldBehaviorResolverCall *);
/* Query-local, exact Blob/request gate. The returned bank is borrowed. */
BehaviorResolveStatus OverworldBehaviorResolver_ValidateRequest(
    const void *, u32, const BehaviorResolveRequest *, OverworldApplicationBank *);

#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
typedef char OverworldBehaviorResolverCallMustRemain32[
    sizeof(OverworldBehaviorResolverCall) == 32 ? 1 : -1];
#endif

#endif
