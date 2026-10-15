#include "../../include/overworld_throw_observation_native.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_query_code_addon_service.h"
#include "../../include/overworld_throw_binding_native.h"
#include "../../include/overworld_throw_away_wild.h"

#define PLAYER_HEALTH_THROW_RUNTIME(state) \
    ((OverworldWildOverlayRuntimeState *)(state)->movementRuntimeState)
#define PLAYER_HEALTH_THROW_SLOT_MASK(slot) (1u << (slot))
#define PLAYER_HEALTH_THROW_WINDUP_FLAG 0x40

static inline int PlayerHealthThrow_Abs(int value)
{
    return value < 0 ? -value : value;
}

/* Refresh through the existing frame owner: another actor's preparation may
 * invalidate the shared cache during windup. Never move or recapture Cargo. */
BOOL __attribute__((noinline, section(".overworld_throw_binding_position")))
OverworldThrowObservation_BindingPosition(OverworldWildSpawnState *state, u8 slot,
    u8 name, OverworldTargetBindingPosition *position)
{
    const OverworldBehaviorConditionServiceEntry *gate;
    const OverworldQueryCodeAddonServiceEntry *service;
    const OverworldQueryCodeAddonEntry *entry;
    OverworldWildBehaviorConditionRuntime *conditions;
    OverworldActorHandle saved;
    OverworldBehaviorConditionWorldView *world;
    OverworldTargetBindingStatus result;
    if (state == NULL || state->movementRuntimeState == NULL
        || slot >= OW_WILD_MAX_SPAWNS || position == NULL) return FALSE;
    conditions = PLAYER_HEALTH_THROW_RUNTIME(state)->conditions;
    if (conditions == NULL) return FALSE;
    gate = OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE();
    if (gate == NULL || gate->magic != OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC
        || gate->version != OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        || gate->size != sizeof(*gate)) return FALSE;
    service = (const OverworldQueryCodeAddonServiceEntry *)
        OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR;
    if (service->magic != OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC
        || service->version != OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION
        || service->size != sizeof(*service)
        || service->state != (OverworldQueryCodeAddonState *)OVERWORLD_QUERY_CODE_ADDON_STATE_ADDR
        || service->acquire == NULL) return FALSE;
    world = &conditions->frame.world;
    entry = OVERWORLD_THROW_BINDING_REFRESH_ENTRY(state, conditions, service, slot);
    if (entry == NULL) return FALSE;
    saved = world->subject;
    world->subject = conditions->actors[slot].subject;
    result = entry->bindingResolve(&conditions->bindings[slot], world, name, position);
    world->subject = saved;
    return result == OVERWORLD_TARGET_BINDING_OK;
}

/* The public Condition gate proves Selector lifetime. The private acquire
 * checks this exact prepared owner before calling ordinary heap code. */
u32 __attribute__((noinline, section(".overworld_throw_observe")))
OverworldThrowObservation_Observe(
    OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionRuntime *conditions,
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn,
    PlayerHealthThrowQueryTargetFunc queryTarget)
{
    const OverworldQueryCodeAddonServiceEntry *service;
    const OverworldQueryCodeAddonEntry *entry;
    OverworldQueryCodeAddonOwner owner;
    if (state == NULL || conditions == NULL || (u32)slot >= OW_WILD_MAX_SPAWNS
        || OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE() == NULL) return 0;
    service = (const OverworldQueryCodeAddonServiceEntry *)OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR;
    owner = (OverworldQueryCodeAddonOwner){(u32)(uintptr_t)state->movementFieldSystem,
        conditions->actors[slot].subject.fieldEpoch, conditions->actors[slot].subject.mapGeneration};
    entry = service->acquire(&owner);
    return entry != NULL ? entry->throwObserve(state, slot, profile, blob, conditions,
        isCurrentSpawn, queryTarget, OverworldThrowObservation_BindingPosition) : 0;
}
