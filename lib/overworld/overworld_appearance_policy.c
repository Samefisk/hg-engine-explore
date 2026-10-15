#include "../../include/overworld_appearance_policy.h"
#include "../../include/overworld_application_bank.h"

#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
__attribute__((section(".overworld_appearance_damage_policy")))
#endif
u8 OverworldAppearancePolicy_DamageStrength(u16 hp, u16 maxHp, u32 frame)
{
    u32 missing;
    u32 peak;
    u32 shift;
    u32 period;
    u32 triangle;

    if (maxHp == 0 || hp >= maxHp) {
        return 0;
    }
    missing = maxHp - hp;
    peak = 1u + (missing * 5u + maxHp - 1u) / maxHp;
    shift = 7u - ((peak - 2u) >> 1);
    period = 1u << shift;
    /* Keep normal colors for half the cycle, then one soft triangle. */
    triangle = (frame - period / 4u) & (period - 1u);
    if (triangle > period / 2u) {
        return 0;
    }
    if (triangle > period / 4u) {
        triangle = period / 2u - triangle;
    }
    return (u8)((peak * triangle) >> (shift - 2u));
}

/* Keep this private read with the pulse policy in the existing Field slot. */
static u32 __attribute__((noinline))
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
__attribute__((optimize("no-ipa-sra"),
    section(".overworld_appearance_damage_policy.tail")))
#endif
OverworldAppearancePolicy_ApplicableMask(
    const OverworldWildBehaviorConditionOptions *options, u32 roleMask)
{
    /* Only current role bits enter this private helper. Zero means no
     * contribution; the caller uses this mask as a truth value. */
    u32 mask = options->subjectRoleMask;
    if (mask == 0) mask = 0xFF;
    return options->bindOnly ? 0 : mask & roleMask;
}

/* Field owns this pure read. Its linked bytes use existing boot Actor room. */
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
__attribute__((section(".overworld_appearance_rest_policy")))
#endif
BOOL OverworldAppearancePolicy_ShouldRestTint(
    const OverworldBehaviorConditionPreparedActor *prepared,
    const OverworldWildBehaviorDataBlob *blob,
    u32 enabledApplicationMask,
    u32 frame,
    u8 actorRole)
{
    u32 enabled = 0;
    u32 roleMask = (u32)actorRole - OVERWORLD_ACTOR_ROLE_WILD;
    OverworldApplicationBank bank;
    u32 i;

    if (prepared == NULL || blob == NULL || !prepared->valid
        || prepared->count == 0 || prepared->states == NULL
        || prepared->count > prepared->stateCapacity
        || prepared->count > OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES
        || enabledApplicationMask == 0
        || roleMask > OVERWORLD_ACTOR_ROLE_MOUNTED - OVERWORLD_ACTOR_ROLE_WILD
        || !OverworldApplicationBank_Select(blob, prepared->subjectSpecies, &bank)) {
        return FALSE;
    }
    roleMask = 1u << roleMask;
    for (i = 0; i < prepared->count; i++) {
        const OverworldBehaviorConditionEntryState *state =
            &prepared->states[i];
        const OverworldWildBehaviorConditionEntry *entry;
        const OverworldWildBehaviorConditionOptions *options;
        u16 source = prepared->catalogEntryIndexes[i];
        int localApplication;
        u16 globalApplication;

        if (source >= blob->header.conditionEntryCount) {
            return FALSE;
        }
        entry = &blob->conditionEntries[source];
        options = &blob->conditionOptions[source];
        globalApplication = blob->conditionGlobalApplications[source];
        localApplication = OverworldApplicationBank_Local(&bank, globalApplication);
        if (!OverworldAppearancePolicy_ApplicableMask(options, roleMask)) {
            continue;
        }
        if (globalApplication >= blob->header.overrideProfileCount
            || localApplication < 0
            || !blob->applicationRestTint[globalApplication]
            || (state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE) != 0
            || (state->flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED) == 0
            || entry->cooldownFrames == 0
            || (s32)(frame - state->cooldownUntil) >= 0) {
            return FALSE;
        }
        enabled |= enabledApplicationMask & (1u << localApplication);
    }
    return enabled != 0;
}
