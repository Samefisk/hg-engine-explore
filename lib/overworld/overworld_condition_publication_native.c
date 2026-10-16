#include "../../include/overworld_condition_publication_native.h"
#if !defined(OVERWORLD_CONDITION_PUBLICATION_RUNTIME_ONLY) && !defined(OVERWORLD_CONDITION_PUBLICATION_CHAIN)
#include "../../include/overworld_behavior_condition_adapter.h"
#endif
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <string.h>
#define PUBLICATION_SECTION(name)
#else
#define PUBLICATION_SECTION(name) __attribute__((section(name)))
#endif

typedef u32 OverworldConditionPublicationTailWord __attribute__((may_alias));
typedef char OverworldConditionPublicationTailWordMustMatchRowLayout[
    OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL == 0
        && OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED == 0
        && __builtin_offsetof(OverworldWildBehaviorOverrideProfile, targetMode) % 4 == 0
        && __builtin_offsetof(OverworldWildBehaviorOverrideProfile, profileKind)
            == __builtin_offsetof(OverworldWildBehaviorOverrideProfile, targetMode) + 1
        && __builtin_offsetof(OverworldWildBehaviorOverrideProfile, conditionCount)
            == __builtin_offsetof(OverworldWildBehaviorOverrideProfile, targetMode) + 3
        ? 1 : -1];

#if !defined(OVERWORLD_CONDITION_PUBLICATION_SELECTOR)
void __attribute__((noinline, optimize("Os"))) PUBLICATION_SECTION(".overworld_condition_publication_init")
OverworldConditionPublication_InitResult(OverworldBehaviorConditionResult *result)
{
    u16 i;
    memset(result, 0, sizeof(*result));
    result->resolvedTargetConditionId =
        OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    result->resolvedTargetSourceApplication =
        OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
    result->winningConditionId = OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    result->winningConditionSourceApplication =
        OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
    result->resolvedTarget.kind =
        OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
    for (i = 0; i < OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS; i++) {
        result->winningConditionIds[i] =
            OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    }
}

void __attribute__((noinline, optimize("Os"))) PUBLICATION_SECTION(".overworld_condition_publication_fold")
OverworldConditionPublication_FoldResult(OverworldBehaviorConditionResult *result)
{
    u16 i;
    for (i = 0; i < OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS; i++) {
        if ((result->activeApplicationMask & (1u << i)) == 0) {
            continue;
        }
        result->winningConditionId = result->winningConditionIds[i];
        result->winningConditionSourceApplication = (u8)i;
        if (result->targets[i].kind
                != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE) {
            result->resolvedTarget = result->targets[i];
            result->resolvedTargetConditionId =
                result->winningConditionIds[i];
            result->resolvedTargetSourceApplication = (u8)i;
        }
    }
}

u8 __attribute__((noinline, optimize("Os"))) PUBLICATION_SECTION(".overworld_condition_publication_blob")
OverworldConditionPublication_BlobValid(
    const OverworldWildBehaviorDataBlob *blob,
    u32 blobSize)
{
    /* Round the member limit to the end of a four-value group. This is
     * the same u16 limit check without an extra Thumb literal-pool word. */
    if (!(blob != NULL
        && blobSize == sizeof(*blob)
        && blob->header.magic == OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        && blob->header.version == OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        && blob->header.headerSize == sizeof(blob->header)
        && blob->header.blobSize == blobSize
        && blob->header.overrideProfileCount <= OWBD_OVERRIDE_PROFILE_COUNT
        && (((u32)blob->header.overrideMemberCount
                + (3u - (OWBD_OVERRIDE_MEMBER_COUNT & 3u))) >> 2)
            <= (OWBD_OVERRIDE_MEMBER_COUNT >> 2)
        && blob->header.conditionEntryCount <= OWBD_CONDITION_ENTRY_COUNT)) {
        return 0;
    }
    return 1;
}

#if defined(OVERWORLD_CONDITION_PUBLICATION_CHAIN)
const u32 __attribute__((section(".overworld_condition_publication_imports")))
gOverworldConditionPublicationImports[9] = {
    0x023DEEA3, 0x023DEEBF, 0x023DEE4D,
    0x01FF9A49, 0x01FF9C95, 0x01FFA39D, 0x023C2F75,
    0x02208201, 0x023C7EA9,
};
#endif
#endif

#if !defined(OVERWORLD_CONDITION_PUBLICATION_CHAIN)
void __attribute__((noinline, optimize("Os"))) PUBLICATION_SECTION(".overworld_condition_publication_capture")
OverworldConditionPublication_CapturePrior(
    const OverworldBehaviorConditionPreparedActor *prepared,
    OverworldBehaviorConditionResult *result,
    void *priorPublication)
{
    OverworldConditionPublication_FoldResult(result);
    u16 priorStateIndex = result->resolvedTarget.actor.slot;
    memset(&result->resolvedTarget.actor, 0, sizeof(result->resolvedTarget.actor));
    if (result->resolvedTarget.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        const OverworldBehaviorConditionEntryState *state = &prepared->states[priorStateIndex];
        result->resolvedTarget.actor = prepared->subject;
        result->resolvedTarget.actor.slot = state->targetSlot;
        result->resolvedTarget.actor.generation = state->targetGeneration;
        result->resolvedTarget.actor.encounterGeneration = state->targetEncounterGeneration;
    }
    memcpy(priorPublication, &result->resolvedTarget, OVERWORLD_CONDITION_PUBLICATION_BYTES);
    OverworldConditionPublication_InitResult(result);
}

#if !defined(OVERWORLD_CONDITION_PUBLICATION_RUNTIME_ONLY)
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
u32 __attribute__((noinline, optimize("Os"))) PUBLICATION_SECTION(".overworld_condition_publication_changed")
OverworldConditionPublication_ChangedMask(
    const OverworldWildBehaviorConditionRuntime *runtime, u8 slot)
{
    return (runtime->result.activeApplicationMask ^ runtime->activeApplicationMasks[slot])
        | (runtime->scratch.entryFlags[0]
            & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED);
}

#else
typedef char OverworldConditionPublicationChangedMaskOffsetsMustRemainFixed[
    __builtin_offsetof(OverworldWildBehaviorConditionRuntime, activeApplicationMasks) == 2332
        && __builtin_offsetof(OverworldWildBehaviorConditionRuntime, result)
            + __builtin_offsetof(OverworldBehaviorConditionResult, activeApplicationMask) == 912
        && __builtin_offsetof(OverworldWildBehaviorConditionRuntime, scratch)
            + __builtin_offsetof(OverworldBehaviorConditionScratch, entryFlags) == 880
        && OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PUBLICATION_CHANGED == 8
        ? 1 : -1];
u32 __attribute__((naked, noinline)) PUBLICATION_SECTION(".overworld_condition_publication_changed")
OverworldConditionPublication_ChangedMask(
    const OverworldWildBehaviorConditionRuntime *runtime __attribute__((unused)),
    u8 slot __attribute__((unused)))
{
    __asm__(
        "ldr r2, 1f\n"
        "lsl r1, r1, #2\n"
        "add r1, r0, r1\n"
        "ldr r1, [r1, r2]\n"
        "ldr r2, 2f\n"
        "ldr r2, [r0, r2]\n"
        "eor r1, r2\n"
        "mov r2, #220\n"
        "lsl r2, r2, #2\n"
        "ldrb r0, [r0, r2]\n"
        "mov r2, #8\n"
        "and r0, r2\n"
        "orr r0, r1\n"
        "bx lr\n"
        "1: .word 2332\n"
        "2: .word 912\n");
}

#endif
#endif
#endif
