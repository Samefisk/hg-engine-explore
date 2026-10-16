#include "../../include/overworld_target_bindings.h"
#if defined(OVERWORLD_BEHAVIOR_HOST) || defined(OVERWORLD_ACTOR_SYSTEM_HOST)
#include <string.h>
#endif

static u8 Binding_HandleValid(const OverworldActorHandle *actor)
{
    return actor != NULL
        && actor->slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        && actor->generation != 0
        && actor->fieldEpoch != 0
        && actor->mapGeneration != 0
        && actor->encounterGeneration != 0;
}

static u8 Binding_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    return left->slot == right->slot
        && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

static OverworldTargetBindingStatus Binding_CurrentSubject(
    const OverworldTargetBindingsState *state,
    const OverworldBehaviorConditionWorldView *world)
{
    if (state == NULL || world == NULL
        || world->actorCount > OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS) {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    if (!Binding_HandleValid(&state->subject)
        || !Binding_HandleValid(&world->subject)
        || !Binding_HandleEquals(&state->subject, &world->subject)) {
        return OVERWORLD_TARGET_BINDING_STALE_SUBJECT;
    }
    return OVERWORLD_TARGET_BINDING_OK;
}

static OverworldTargetBindingStatus Binding_Position(
    const OverworldBehaviorConditionWorldView *world,
    const OverworldBehaviorConditionTargetReference *target,
    OverworldTargetBindingPosition *position)
{
    u8 i;
    u8 matches = 0;

    if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER) {
        if (!world->playerValid) {
            return OVERWORLD_TARGET_BINDING_STALE_TARGET;
        }
        position->x = world->playerX;
        position->y = world->playerY;
    } else if (target->kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR) {
        if (!Binding_HandleValid(&target->actor)
            || target->actor.fieldEpoch != world->subject.fieldEpoch
            || target->actor.mapGeneration != world->subject.mapGeneration) {
            return OVERWORLD_TARGET_BINDING_STALE_TARGET;
        }
        for (i = 0; i < world->actorCount; i++) {
            const OverworldBehaviorConditionActorObservation *actor =
                &world->actors[i];

            if (actor->valid
                && Binding_HandleEquals(&actor->actor, &target->actor)) {
                matches++;
                position->x = actor->x;
                position->y = actor->y;
            }
        }
        if (matches != 1) {
            return OVERWORLD_TARGET_BINDING_STALE_TARGET;
        }
    } else {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    position->target = *target;
    return OVERWORLD_TARGET_BINDING_OK;
}

OverworldTargetBindingStatus OverworldTargetBindings_Init(
    OverworldTargetBindingsState *state,
    const OverworldActorHandle *subject)
{
    OverworldActorHandle owner;
    u8 name;

    if (state == NULL || !Binding_HandleValid(subject)) {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    owner = *subject;
    memset(state, 0, sizeof(*state));
    state->subject = owner;
    for (name = 0; name < OVERWORLD_TARGET_BINDING_COUNT; name++) {
        state->bindings[name].sourceConditionId =
            OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
        state->bindings[name].sourceApplication =
            OVERWORLD_BEHAVIOR_CONDITION_NO_APPLICATION;
        state->bindings[name].reason = OVERWORLD_TARGET_BINDING_EMPTY;
    }
    return OVERWORLD_TARGET_BINDING_OK;
}

OverworldTargetBindingStatus OverworldTargetBindings_CaptureEntry(
    OverworldTargetBindingsState *state,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldActorHandle *admittedSubject,
    const OverworldBehaviorConditionEntryResult *entry,
    u8 name,
    u8 lifetime,
    u16 durationFrames)
{
    OverworldTargetBindingStatus status;
    OverworldTargetBinding *binding;
    OverworldTargetBindingPosition position;

    if (entry == NULL || name >= OVERWORLD_TARGET_BINDING_COUNT
        || lifetime > OVERWORLD_TARGET_BINDING_FRAMES
        || (lifetime == OVERWORLD_TARGET_BINDING_FRAMES
            ? durationFrames == 0 : durationFrames != 0)) {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    status = Binding_CurrentSubject(state, world);
    if (status != OVERWORLD_TARGET_BINDING_OK) {
        return status;
    }
    if (!Binding_HandleValid(admittedSubject)
        || !Binding_HandleEquals(admittedSubject, &world->subject)) {
        return OVERWORLD_TARGET_BINDING_STALE_SUBJECT;
    }
    if (entry->active != 1 || entry->triggered != 1
        || entry->conditionTrue != 1) {
        return OVERWORLD_TARGET_BINDING_NOT_ADMITTED;
    }
    if (entry->conditionId == OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY
        || entry->applicationIndex >= OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS
        || entry->target.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE
        || (name == OVERWORLD_TARGET_BINDING_CARGO
            && entry->target.kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR)) {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    binding = &state->bindings[name];
    if ((binding->flags & OVERWORLD_TARGET_BINDING_BOUND) != 0
        && !(binding->lifetime == OVERWORLD_TARGET_BINDING_FRAMES
            && (s32)(world->frame - binding->expiresAt) >= 0)) {
        return OVERWORLD_TARGET_BINDING_ALREADY_BOUND;
    }
    /* The two value bindings may name the same actor. The authored selector
     * chooses this explicitly; storing Cargo does not take actor control. */
    if (entry->target.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
        && Binding_HandleEquals(&entry->target.actor, &state->subject)) {
        return OVERWORLD_TARGET_BINDING_CONFLICT;
    }
    status = Binding_Position(world, &entry->target, &position);
    if (status != OVERWORLD_TARGET_BINDING_OK) {
        return status;
    }
    binding->target = entry->target;
    binding->sourceConditionId = entry->conditionId;
    binding->sourceApplication = entry->applicationIndex;
    binding->expiresAt = lifetime == OVERWORLD_TARGET_BINDING_FRAMES
        ? world->frame + durationFrames : 0;
    binding->lifetime = lifetime;
    binding->flags = OVERWORLD_TARGET_BINDING_BOUND;
    binding->reason = OVERWORLD_TARGET_BINDING_OK;
    return OVERWORLD_TARGET_BINDING_OK;
}

OverworldTargetBindingStatus OverworldTargetBindings_Resolve(
    OverworldTargetBindingsState *state,
    const OverworldBehaviorConditionWorldView *world,
    u8 name,
    OverworldTargetBindingPosition *position)
{
    OverworldTargetBindingStatus status;
    OverworldTargetBinding *binding;
    OverworldTargetBindingPosition current;

    if (position == NULL || name >= OVERWORLD_TARGET_BINDING_COUNT) {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    memset(position, 0, sizeof(*position));
    status = Binding_CurrentSubject(state, world);
    if (status != OVERWORLD_TARGET_BINDING_OK) {
        if (state != NULL) {
            state->bindings[name].reason = status;
        }
        return status;
    }
    binding = &state->bindings[name];
    if ((binding->flags & OVERWORLD_TARGET_BINDING_BOUND) == 0) {
        return OVERWORLD_TARGET_BINDING_EMPTY;
    }
    if (binding->lifetime == OVERWORLD_TARGET_BINDING_FRAMES
        && (s32)(world->frame - binding->expiresAt) >= 0) {
        status = OVERWORLD_TARGET_BINDING_EXPIRED;
    } else {
        status = Binding_Position(world, &binding->target, &current);
    }
    binding->reason = status;
    if (status == OVERWORLD_TARGET_BINDING_OK) {
        *position = current;
    }
    return status;
}

OverworldTargetBindingStatus OverworldTargetBindings_Clear(
    OverworldTargetBindingsState *state,
    const OverworldActorHandle *subject,
    u8 name,
    u8 reason)
{
    OverworldTargetBinding *binding;

    if (state == NULL || !Binding_HandleValid(subject)
        || name >= OVERWORLD_TARGET_BINDING_COUNT
        || reason < OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT
        || reason > OVERWORLD_TARGET_BINDING_CLEAR_BATTLE) {
        return OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT;
    }
    if (!Binding_HandleEquals(&state->subject, subject)) {
        return OVERWORLD_TARGET_BINDING_STALE_SUBJECT;
    }
    binding = &state->bindings[name];
    memset(&binding->target, 0, sizeof(binding->target));
    binding->flags = 0;
    binding->expiresAt = 0;
    binding->reason = reason;
    return OVERWORLD_TARGET_BINDING_OK;
}

OverworldTargetBindingStatus OverworldTargetBindings_ClearAll(
    OverworldTargetBindingsState *state,
    const OverworldActorHandle *subject,
    u8 reason)
{
    OverworldTargetBindingStatus status = OverworldTargetBindings_Clear(
        state, subject, OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST, reason);

    if (status != OVERWORLD_TARGET_BINDING_OK) {
        return status;
    }
    return OverworldTargetBindings_Clear(
        state, subject, OVERWORLD_TARGET_BINDING_CARGO, reason);
}
