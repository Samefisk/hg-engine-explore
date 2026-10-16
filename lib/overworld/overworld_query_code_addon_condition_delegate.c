#include "../../include/overworld_query_code_addon_service.h"
#include "../../include/constants/file.h"

static const OverworldQueryCodeAddonEntry *Condition_Current(const OverworldActorHandle *subject)
{
    OverworldQueryCodeAddonOwner owner = gOverworldQueryCodeAddonState.owner;
    if (subject) {
        owner.fieldEpoch = subject->fieldEpoch;
        owner.mapGeneration = subject->mapGeneration;
    }
    return OverworldQueryCodeAddon_Acquire(&gOverworldQueryCodeAddonState, &owner);
}
OverworldBehaviorConditionStatus OverworldQueryCodeAddon_ConditionPrepare(
    const void *blob, u32 size, const OverworldWildBehaviorContext *context,
    const OverworldActorHandle *subject, OverworldBehaviorConditionPreparedActor *prepared)
{
    const OverworldQueryCodeAddonEntry *entry = Condition_Current(subject);
    OverworldBehaviorConditionStatus status;
    if (!entry) return OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
    status = entry->conditionPrepare(blob, size, context, subject, prepared);
    /* The addon only sizes/prepares values. Native World-heap ownership stays
     * here, matching the previous service's allocate-only-when-missing rule. */
    if (status == OVERWORLD_BEHAVIOR_CONDITION_STORAGE_REQUIRED
        && prepared && !prepared->states && prepared->count) {
        prepared->states = sys_AllocMemory(HEAPID_WORLD,
            prepared->count * sizeof(*prepared->states));
        if (prepared->states) {
            prepared->stateCapacity = prepared->count;
            status = entry->conditionPrepare(blob, size, context, subject, prepared);
        }
    }
    return status;
}
OverworldBehaviorConditionStatus OverworldQueryCodeAddon_ConditionEvaluate(
    const void *blob, u32 size, OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldBehaviorConditionWorldView *world, const OverworldBehaviorConditionCandidate *candidates,
    u8 count, u32 seed, OverworldBehaviorConditionScratch *scratch, OverworldBehaviorConditionResult *result)
{
    const OverworldQueryCodeAddonEntry *entry = Condition_Current(world ? &world->subject : NULL);
    return entry ? entry->conditionEvaluate(blob, size, prepared, world, candidates, count, seed, scratch, result)
        : OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION;
}
BOOL OverworldQueryCodeAddon_ResolverCall(OverworldBehaviorResolverCall *call)
{
    const OverworldQueryCodeAddonEntry *entry = Condition_Current(NULL);
    return entry ? entry->resolverCall(call) : FALSE;
}
void OverworldQueryCodeAddon_ConditionNotify(OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldActorHandle *subject, u32 effect)
{
    const OverworldQueryCodeAddonEntry *entry = Condition_Current(subject);
    if (entry) entry->conditionNotify(prepared, subject, effect);
}
