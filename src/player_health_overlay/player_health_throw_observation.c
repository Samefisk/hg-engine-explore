#include "../../include/player_health_throw_observation.h"
#include "../../include/overworld_throw_observation_native.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/wild_movement_value.h"
#include "../../include/map_events_internal.h"

#define PLAYER_HEALTH_THROW_RUNTIME(state) \
    ((OverworldWildOverlayRuntimeState *)(state)->movementRuntimeState)
#define PLAYER_HEALTH_THROW_SLOT_MASK(slot) (1u << (slot))
#define PLAYER_HEALTH_THROW_MOTION_WALK 1
#define PLAYER_HEALTH_THROW_TIRED_EMOTE 10

static u16 __attribute__((noinline, section(".player_health_throw_text")))
PlayerHealthThrow_ReservableMask(
    OverworldWildSpawnState *state,
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn)
{
    OverworldWildOverlayRuntimeState *runtime;
    FieldSystem *fieldSystem;
    u16 mask = 0;
    int i;

    if (state == NULL || state->movementRuntimeState == NULL
        || isCurrentSpawn == NULL) {
        return 0;
    }
    runtime = PLAYER_HEALTH_THROW_RUNTIME(state);
    fieldSystem = state->movementFieldSystem;
    if (fieldSystem == NULL) {
        return 0;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (i != OW_WILD_FOLLOWER_SLOT
            && state->spawns[i].active
            && isCurrentSpawn(
                fieldSystem, &state->spawns[i])
            && runtime->movementCustomMotionModes[i]
                == PLAYER_HEALTH_THROW_MOTION_WALK
            && runtime->movementCustomJumpActive[i]
            && !runtime->movementCustomJumpPrepActive[i]
            && runtime->movementEmotePartnerPrepObjects[i] == NULL
            && state->movementCrashShakeTimers[i] == 0
            && state->movementSpawnRunActive[i] == 0
            && state->movementActorControlModes[i]
                != OW_WILD_ACTOR_CONTROL_HELD) {
            mask |= PLAYER_HEALTH_THROW_SLOT_MASK(i);
        }
    }
    return mask;
}

static BOOL __attribute__((noinline, section(".player_health_throw_text")))
PlayerHealthThrow_TryReserve(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot,
    const OverworldWildHelperOverlayEntry *helperEntry,
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL || state->movementRuntimeState == NULL
        || targetSlot < 0 || targetSlot >= OW_WILD_MAX_SPAWNS
        || helperEntry == NULL
        || helperEntry->tryStartPickupThrowAction == NULL) {
        return FALSE;
    }
    runtime = PLAYER_HEALTH_THROW_RUNTIME(state);
    return helperEntry->tryStartPickupThrowAction(
        state,
        &runtime->throwState,
        &runtime->spawnPresentations,
        carrierSlot,
        targetSlot,
        WildMovementValue_GetThrowUnstableMask(
            state, runtime->movementCustomMotionModes),
        PlayerHealthThrow_ReservableMask(state, isCurrentSpawn));
}

static void __attribute__((noinline, section(".player_health_throw_text")))
PlayerHealthThrow_StartRecovery(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives,
    PlayerHealthThrowStartTiredFunc startTired)
{
    OverworldWildBehaviorProfile recovery;
    volatile u8 *destination = (volatile u8 *)&recovery;
    const volatile u8 *source = (const volatile u8 *)profile;
    u32 index;

    /* A struct assignment calls the far Thumb memcpy through an ARM veneer.
     * Keep this small copy local to the resident ITCM service. */
    for (index = 0; index < sizeof(recovery); index++) {
        destination[index] = source[index];
    }

    if (PLAYER_HEALTH_THROW_RUNTIME(state)->conditions != NULL) {
        OverworldWildBehaviorConditionRuntime *conditions =
            PLAYER_HEALTH_THROW_RUNTIME(state)->conditions;
        memset(&conditions->bindings[slot], 0, sizeof(conditions->bindings[slot]));
        conditions->bindings[slot].subject = conditions->actors[slot].subject;
    }
    PLAYER_HEALTH_THROW_RUNTIME(state)->throwState.recoveringMask |=
        PLAYER_HEALTH_THROW_SLOT_MASK(slot);
    if (recovery.tiredState == 0) {
        recovery.tiredState = PLAYER_HEALTH_THROW_TIRED_EMOTE;
    }
    recovery.stamina = 1;
    recovery.restTime = profile->throwRecoveryFrames;
    startTired(state, slot, &recovery, primitives);
}

static BOOL __attribute__((noinline, section(".player_health_throw_text")))
PlayerHealthThrow_IsStableTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot,
    PlayerHealthThrowQueryTargetFunc queryTarget)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL || state->movementRuntimeState == NULL
        || queryTarget == NULL) {
        return FALSE;
    }
    runtime = PLAYER_HEALTH_THROW_RUNTIME(state);
    return queryTarget(state, carrierSlot, targetSlot,
        OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE,
        WildMovementValue_GetThrowUnstableMask(
            state, runtime->movementCustomMotionModes));
}

static u16 __attribute__((noinline, section(".player_health_throw_text")))
PlayerHealthThrow_UnstableMask(OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime = PLAYER_HEALTH_THROW_RUNTIME(state);

    return WildMovementValue_GetThrowUnstableMask(
        state, runtime->movementCustomMotionModes);
}

const PlayerHealthThrowServiceEntry gPlayerHealthThrowServiceEntry
    __attribute__((section(".player_health_throw_api"), used)) = {
    PLAYER_HEALTH_THROW_SERVICE_MAGIC,
    PLAYER_HEALTH_THROW_SERVICE_VERSION,
    sizeof(PlayerHealthThrowServiceEntry),
    OVERWORLD_THROW_OBSERVATION_OBSERVE_ENTRY,
    PlayerHealthThrow_TryReserve,
    PlayerHealthThrow_StartRecovery,
    PlayerHealthThrow_IsStableTarget,
    PlayerHealthThrow_UnstableMask,
    OVERWORLD_THROW_OBSERVATION_BINDING_POSITION_ENTRY,
};
