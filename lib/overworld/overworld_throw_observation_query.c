#include "../../include/overworld_throw_observation_native.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_throw_away_wild.h"
#define PLAYER_HEALTH_THROW_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)(state)->movementRuntimeState)
#define PLAYER_HEALTH_THROW_SLOT_MASK(slot) (1u << (slot))
#define PLAYER_HEALTH_THROW_WINDUP_FLAG 0x40
static inline int PlayerHealthThrow_Abs(int value) { return value < 0 ? -value : value; }

/* Shared line fact: the away endpoint uses the same legality query as launch. */
static BOOL __attribute__((noinline)) PlayerHealthThrow_Line(
    OverworldWildSpawnState *state, int slot, u8 relation,
    const OverworldWildBehaviorProfile *profile,
    const OverworldTargetBindingPosition *interest,
    PlayerHealthThrowQueryTargetFunc queryTarget)
{
    LocalMapObject *object;
    int dx, dy, distance;
    if (relation & PLAYER_HEALTH_THROW_WINDUP_FLAG) return TRUE;
    if (profile->chillTarget == OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE)
        return queryTarget(state, slot, OW_WILD_HELPER_THROW_TARGET_DECODE(relation),
            OW_WILD_HELPER_PICKUP_THROW_QUERY_AWAY_LINE,
            OVERWORLD_THROW_AWAY_SETTINGS(profile->throwMaxRange, profile->chillAllowedTerrainMask));
    object = state->spawns[slot].object;
    dx = interest->x - object->xCurr; dy = interest->y - object->yCurr;
    distance = PlayerHealthThrow_Abs(dx) + PlayerHealthThrow_Abs(dy);
    return distance != 0 && distance <= profile->throwMaxRange;
}

u32 OverworldThrowObservationQuery_Observe(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorConditionRuntime *conditions,
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn,
    PlayerHealthThrowQueryTargetFunc queryTarget,
    OverworldThrowObservationBindingPositionFunc bindingPosition)
{
    OverworldWildOverlayRuntimeState *runtime = PLAYER_HEALTH_THROW_RUNTIME(state);
    const OverworldBehaviorConditionPreparedActor *prepared =
        &conditions->actors[slot];
    u16 slotMask = PLAYER_HEALTH_THROW_SLOT_MASK(slot);
    u8 relation = runtime->throwState.targets[slot];
    u8 facts = 0;
    u16 cargoMask = 0;
    u16 incomingClaimMask = 0;
    OverworldTargetBindingPosition objectOfInterest;
    BOOL needsCargo = FALSE;
    int i;

    if (relation != OW_WILD_HELPER_THROW_TARGET_NONE) {
        facts |= (relation & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
            ? OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD
            : OVERWORLD_BEHAVIOR_ACTOR_FACT_RESERVED;
    }
    if ((runtime->throwState.recoveringMask & slotMask) != 0) {
        facts |= OVERWORLD_BEHAVIOR_ACTOR_FACT_RECOVERING;
    }
    if (bindingPosition(state, slot,
            OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST, &objectOfInterest)) {
        facts |= OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID;
        if ((facts & OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD) != 0) {
            if (PlayerHealthThrow_Line(state, slot, relation, profile,
                    &objectOfInterest, queryTarget)) {
                facts |= OVERWORLD_BEHAVIOR_ACTOR_FACT_THROW_LINE;
            }
        }
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u8 other = runtime->throwState.targets[i];
        if (other != OW_WILD_HELPER_THROW_TARGET_NONE
            && !(other & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG)
            && OW_WILD_HELPER_THROW_TARGET_DECODE(other) == slot
            && state->spawns[i].active
            && isCurrentSpawn(state->movementFieldSystem, &state->spawns[i])) {
            facts |= OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP;
            incomingClaimMask |= 1u << i;
        }
    }
    for (i = 0; i < prepared->count; i++) {
        u16 index = prepared->catalogEntryIndexes[i];
        const OverworldWildBehaviorConditionEntry *entry;

        if (index >= blob->header.conditionEntryCount) {
            continue;
        }
        entry = &blob->conditionEntries[index];
        if (entry->targetKind == OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR
            && blob->conditionOptions[index].captureBinding == 2) {
            needsCargo = TRUE;
            break;
        }
    }
    if (!needsCargo || (facts & (OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD
            | OVERWORLD_BEHAVIOR_ACTOR_FACT_RECOVERING)) != 0) {
        return facts | ((u32)incomingClaimMask << 18);
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        u16 candidateMask = PLAYER_HEALTH_THROW_SLOT_MASK(i);
        u8 reservedRelation = OW_WILD_HELPER_THROW_TARGET_DECODE(relation);

        if (i == slot
            || ((slot == OW_WILD_FOLLOWER_SLOT
                    || (relation & OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) != 0)
                && relation != OW_WILD_HELPER_THROW_TARGET_NONE
                && i != reservedRelation)) {
            continue;
        }
        if (queryTarget(
                state,
                slot,
                i,
                OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE,
                0)) {
            cargoMask |= candidateMask;
        }
    }
    return facts | ((u32)cargoMask << 8) | ((u32)incomingClaimMask << 18);
}
