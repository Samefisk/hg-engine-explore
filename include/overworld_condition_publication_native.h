#ifndef OVERWORLD_CONDITION_PUBLICATION_NATIVE_H
#define OVERWORLD_CONDITION_PUBLICATION_NATIVE_H
#include "overworld_behavior_condition_runtime.h"
/* Private pure-code leaves fill existing boot-reserved Chain and loaded
 * Selector padding. The Condition service remains the sole evaluation owner. */
#define OVERWORLD_CONDITION_PUBLICATION_BYTES 20
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST) \
    || defined(OVERWORLD_CONDITION_PUBLICATION_SELECTOR)
#define CONDITION_PUBLICATION_CALL
#else
#define CONDITION_PUBLICATION_CALL __attribute__((long_call))
#endif
u8 CONDITION_PUBLICATION_CALL OverworldConditionPublication_BlobValid(
    const OverworldWildBehaviorDataBlob *, u32);
void CONDITION_PUBLICATION_CALL OverworldConditionPublication_InitResult(
    OverworldBehaviorConditionResult *);
void CONDITION_PUBLICATION_CALL OverworldConditionPublication_FoldResult(
    OverworldBehaviorConditionResult *);
void CONDITION_PUBLICATION_CALL OverworldConditionPublication_CapturePrior(
    const OverworldBehaviorConditionPreparedActor *, OverworldBehaviorConditionResult *, void *);
struct OverworldWildBehaviorConditionRuntime;
u32 OverworldConditionPublication_ChangedMask(
    const struct OverworldWildBehaviorConditionRuntime *, u8);
/* No padding in the 20-byte current target/provenance value. */
typedef char OverworldConditionPublicationSpanMustStay20[
    __builtin_offsetof(OverworldBehaviorConditionResult, winningConditionIds)
        - __builtin_offsetof(OverworldBehaviorConditionResult, resolvedTarget)
        == OVERWORLD_CONDITION_PUBLICATION_BYTES ? 1 : -1];
#endif
