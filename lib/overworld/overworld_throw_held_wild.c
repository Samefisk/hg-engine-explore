#include "../../include/overworld_throw_held_wild.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/player_health.h"

BOOL OverworldThrowHeldWild_ReleaseCargo(const OverworldPickupRouteWildWorld *world)
{
    OverworldWildOverlayRuntimeState *runtime=world->state->movementRuntimeState;
    OverworldWildBehaviorConditionRuntime *conditions=runtime->conditions;
    u8 slot=world->slot, relation=runtime->throwState.targets[slot];
    if(relation&OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG) return FALSE;
    if(OverworldTargetBindings_Clear(&conditions->bindings[slot],
            &conditions->actors[slot].subject,OVERWORLD_TARGET_BINDING_CARGO,
            OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)!=OVERWORLD_TARGET_BINDING_OK) return FALSE;
    runtime->throwState.targets[slot]=OW_WILD_HELPER_THROW_TARGET_NONE;
    runtime->throwState.carrierMask&=~(1u<<slot);
    if(relation!=OW_WILD_HELPER_THROW_TARGET_NONE) {
        u8 old=OW_WILD_HELPER_THROW_TARGET_DECODE(relation);
        u16 surviving=0;
        for(u8 n=0;n<OW_WILD_MAX_SPAWNS;n++)
            if(runtime->throwState.targets[n]!=OW_WILD_HELPER_THROW_TARGET_NONE)
                surviving|=1u<<OW_WILD_HELPER_THROW_TARGET_DECODE(runtime->throwState.targets[n]);
        if(old<OW_WILD_MAX_SPAWNS && !(surviving&(1u<<old)))
            runtime->throwState.targetMask&=~(1u<<old);
    }
    OverworldBehaviorConditionPreparedActor *prepared=&conditions->actors[slot];
    for(u8 n=0;n<prepared->count;n++) {
        u16 index=prepared->catalogEntryIndexes[n];
        if(index>=world->behaviorData->header.conditionEntryCount) continue;
        const OverworldWildBehaviorConditionOptions *options=&world->behaviorData->conditionOptions[index];
        if(options->captureBinding==2 || options->usesBinding==2) {
            prepared->states[n].flags&=~OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
            prepared->states[n].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
        }
    }
    return TRUE;
}

/* The shared held intent calls the existing movement, recovery and drop owner.
 * It stores no controller state and owns no movement engine. */
BOOL OverworldThrowHeldWild_Run(const OverworldThrowHeldWildCall *input)
{
    OverworldPickupRouteWildWorld *world = input->world;
    OverworldWildSpawnState *state = world->state;
    FieldSystem *fieldSystem = world->field;
    int slot = world->slot;
    LocalMapObject *object = state->spawns[slot].object;
    OverworldWildOverlayRuntimeState *runtime = state->movementRuntimeState;
    const OverworldWildBehaviorProfile *profile = input->profile;
    const OverworldWildBehaviorPrimitives *primitives = input->primitives;
    OverworldCargoReadWildTarget *read = input->read;
    const OverworldThrowHeldWildOps *ops = input->ops;
    u8 movementTarget = input->movementTarget, throwTarget = input->throwTarget;
        if(movementTarget==OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE
            && profile->chillState==OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR) {
            OverworldThrowAwayAim away,saved;
            const OverworldThrowAwayAim *required=NULL;
            if(throwTarget&0x40) {
                saved=(OverworldThrowAwayAim){read->impactX,read->impactY,
                    runtime->movementCustomJumpTargetBaseY[slot],read->direction,read->throwDistance};
                required=&saved;
            }
            OverworldThrowAwayWildCall awayCall = {input->world, input->throwService, required, &away,
                OVERWORLD_THROW_AWAY_SETTINGS(profile->throwMaxRange, profile->chillAllowedTerrainMask), read->targetSlot, {0}};
            if(!OverworldThrowAwayWild_Read(&awayCall)) {
                ops->abort(state,slot);
                return FALSE;
            }
            read->impactX=away.x;read->impactY=away.z;read->direction=away.direction;
            read->throwDistance=away.distance;read->dx=away.x-read->objectX;read->dy=away.z-read->objectY;
            /* Windup reads its saved height; a current plan writes it once. */
            if(!(throwTarget&0x40))
                runtime->movementCustomJumpTargetBaseY[slot]=away.baseY;
        }

        if (profile->chillState == OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR
            && (throwTarget & 0x40)) {
            if (ops->bindingBody(state, slot,
                    OVERWORLD_TARGET_BINDING_CARGO, read->targetObject->xCurr,
                    read->targetObject->yCurr) != read->targetObject) {
                ops->abort(state, slot);
                return FALSE;
            }
            runtime->movementCustomJumpTargetBaseY[read->targetSlot] =
                runtime->movementCustomJumpTargetBaseY[slot];
            ops->clearMovement(read->targetObject);
            if (read->throwDistance != 0
                && ops->startJump(
                    state,
                    fieldSystem,
                    read->targetSlot,
                    read->targetObject,
                    read->direction,
                    read->throwDistance,
                    read->impactX,
                    read->impactY,
                    profile,
                    3)) {
                /* A Throw carries the thrower's profile onto the target's
                 * flight. An ordinary wild Hop uses its own resolved profile. */
                if (PlayerHealthOverlay_IsReady()) {
                    (void)PLAYER_HEALTH_OVERLAY_ENTRY->contactEvent(
                        state, PLAYER_HEALTH_EVENT_CODE(
                            read->targetSlot, PLAYER_HEALTH_THROW_LAUNCH),
                        profile, state->movementSpotStates[slot]
                            | ((u32)slot << 8));
                }
                runtime->spawnPresentations.lastKnownX[read->targetSlot] = (s16)read->impactX;
                runtime->spawnPresentations.lastKnownY[read->targetSlot] = (s16)read->impactY;
                runtime->throwState.targets[slot] = 0;
                runtime->throwState.carrierMask &= ~(1u << slot);
                ops->recovery(
                    state, slot, profile, primitives);
            } else {
                ops->release(
                    state,
                    slot,
                    read->targetSlot,
                    read->targetObject);
                ops->recovery(
                    state, slot, profile, primitives);
            }
            return TRUE;
        }
        if (profile->chillState == OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR
            && read->throwDistance != 0
            && read->throwDistance <= profile->throwMaxRange) {
            const LocalMapObject *aim = movementTarget==OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE
                ? read->targetObject : ops->bindingBody(
                    state, slot, OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST, read->impactX, read->impactY);
            if (aim == NULL) {
                ops->abort(state, slot);
                return FALSE;
            }
            runtime->movementCustomJumpTargetX[slot] = (s16)read->impactX;
            runtime->movementCustomJumpTargetY[slot] = (s16)read->impactY;
            if(movementTarget!=OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE)
                runtime->movementCustomJumpTargetBaseY[slot] = (s32)aim->posVec[1];
            runtime->throwState.targets[slot] =
                throwTarget | 0x40;
            ops->facing(object, read->direction);
            ops->bubble(
                object, ops->bubbleId(profile));
            state->movementCooldowns[slot] = profile->throwWindupFrames;
            return TRUE;
        }
        if (profile->chillState == OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR) {
            /* A line can become invalid between observation and this intent.
             * Leave the held actor owned and let the next profile resolve
             * choose the positioning stage again. */
            return FALSE;
        }
    return FALSE;
}
