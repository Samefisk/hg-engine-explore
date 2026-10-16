#include "../../include/overworld_behavior_condition_adapter.h"
#include "../../include/overworld_combat.h"
#include "../../include/overworld_application_bank.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_runtime_state_internal.h"

static BOOL OverworldBehaviorConditionAdapter_HandleEquals(const OverworldActorHandle *a, const OverworldActorHandle *b)
{
    return a->slot == b->slot && a->generation == b->generation
        && a->fieldEpoch == b->fieldEpoch && a->mapGeneration == b->mapGeneration
        && a->encounterGeneration == b->encounterGeneration;
}

/* This mark belongs only to the subject being evaluated. A cached world can
 * be reused by another subject in the same Actor frame, so clear all marks. */
static void OverworldBehaviorConditionAdapter_PlayerDamage(
    OverworldWildBehaviorConditionRuntime *runtime,
    OverworldWildSpawnState *state, FieldSystem *fieldSystem, u8 slot)
{
    OverworldPlayerDamageSource *event = &runtime->playerDamage;
    const OverworldActorHandle *subject = &runtime->actors[slot].subject;
    u16 hp, maximum;
    u32 index;

    runtime->frame.world.playerFacingAndOcclusion =
        (runtime->frame.world.playerFacingAndOcclusion
            & ~OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED)
        | (runtime->actors[slot].subjectDamagePending
            ? OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_SUBJECT_DAMAGED : 0);
    for (index = 0; index < runtime->frame.world.actorCount; index++)
        runtime->frame.world.actors[index].facingAndOcclusion &= ~OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE;
    if (event->fieldSystem != fieldSystem
        || subject->fieldEpoch != event->source.fieldEpoch
        || subject->mapGeneration != event->source.mapGeneration) {
        event->pendingMask = 0;
        return;
    }
    if (!(event->pendingMask & (1u << slot))) return;
    if (event->recipientGenerations[slot] != subject->generation) {
        event->pendingMask &= ~(1u << slot);
        return;
    }
    for (index = 0; index < runtime->frame.world.actorCount; index++) {
        OverworldBehaviorConditionActorObservation *candidate =
            &runtime->frame.world.actors[index];
        if (candidate->valid && OverworldBehaviorConditionAdapter_HandleEquals(
                &candidate->actor, &event->source)) {
            if (!OverworldCombat_IsReady()
                || !OVERWORLD_COMBAT_ENTRY->readHp(state,
                    (u8)event->source.slot, &hp, &maximum) || hp == 0) break;
            candidate->facingAndOcclusion |= OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE;
            return;
        }
    }
    /* Full native source/context loss or faint is a terminal event failure. */
    event->pendingMask = 0;
}

static void OverworldBehaviorConditionAdapter_ConsumePlayerDamage(
    OverworldWildBehaviorConditionRuntime *runtime, u8 slot,
    const OverworldWildBehaviorConditionEntry *entry, u8 entryFlags)
{
        if (entry->kind == OVERWORLD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED
            && (entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED)
            && !(entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_PRESENTATION_ENTERED)) {
            runtime->actors[slot].subjectDamagePending = 0;
        }
        if (entry->kind == OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED
            && (entryFlags & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED)
            && runtime->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].sourceConditionId
                == entry->conditionId
            && (runtime->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
                & OVERWORLD_TARGET_BINDING_BOUND)
            && runtime->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.kind
                == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR
            && OverworldBehaviorConditionAdapter_HandleEquals(
                &runtime->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.actor,
                &runtime->playerDamage.source)) {
            runtime->playerDamage.pendingMask &= ~(1u << slot);
        }
}

/* One shared read/consume leaf. Mutable event storage stays with the Field. */
void OverworldPlayerDamageCondition_Read(
    OverworldWildBehaviorConditionRuntime *runtime, OverworldWildSpawnState *state,
    FieldSystem *fieldSystem, u8 slot, const OverworldWildBehaviorDataBlob *blob)
{
    u8 index;
    if (blob == NULL) {
        OverworldBehaviorConditionAdapter_PlayerDamage(runtime, state, fieldSystem, slot);
        return;
    }
    for (index = 0; index < runtime->actors[slot].count; index++) {
        const OverworldWildBehaviorConditionEntry *entry =
            &blob->conditionEntries[runtime->actors[slot].catalogEntryIndexes[index]];
        OverworldBehaviorConditionAdapter_ConsumePlayerDamage(runtime, slot, entry,
            runtime->scratch.entryFlags[index]);
    }
}

BOOL OverworldBehaviorCondition_BuildRequest(
    OverworldWildBehaviorConditionRuntime *runtime, int forcedGlobalApplication,
    const OverworldWildBehaviorDataBlob *blob)
{
    OverworldApplicationBank bank;
    int local = -1;
    if (forcedGlobalApplication >= 0) {
        if ((unsigned)forcedGlobalApplication >= OVERWORLD_APPLICATION_BANK_NONE
            || !OverworldApplicationBank_Select(blob, runtime->context.species, &bank)
            || (local = OverworldApplicationBank_Local(&bank,
                (u16)forcedGlobalApplication)) < 0)
            return FALSE;
    }
    /* The request is shared scratch. Refresh it for this actor even when its
     * active mask is unchanged, so a caller can use its resolved target now. */
    runtime->request.context = runtime->context;
    runtime->request.forcedOverrideMask =
        local >= 0 ? 1u << local : 0;
    runtime->request.behaviorClass = runtime->context.behaviorClass;
    runtime->request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    runtime->request.activeConditionalMask =
        runtime->result.activeApplicationMask;
    runtime->request.winningConditionId = runtime->result.winningConditionId;
    runtime->request.targetSourceApplication =
        runtime->result.resolvedTargetSourceApplication;
    runtime->request.resolvedTargetConditionId =
        runtime->result.resolvedTargetConditionId;
    /* Reserved bytes stay zero from runtime initialization. */
    memcpy(
        &runtime->request.resolvedTarget,
        &runtime->result.resolvedTarget,
        sizeof(runtime->request.resolvedTarget));
    return TRUE;
}


/* Damage acceptance is the only publisher. The physical contact slot owns
 * the source, including a thrown Cargo whose attack lane came from a carrier. */
void OverworldPlayerDamageCondition_Publish(
    const OverworldWildSpawnState *wild, u8 source, BOOL (*current)(const OverworldWildSpawnState *, u8))
{
    const OverworldActorSystemState *actors =
        (const OverworldActorSystemState *)OVERWORLD_ACTOR_SYSTEM_STATE_ADDR;
    OverworldWildOverlayRuntimeState *runtime = wild->movementRuntimeState;
    OverworldWildBehaviorConditionRuntime *conditions;
    const OverworldBehaviorConditionPreparedActor *prepared;
    const OverworldActorStateSnapshot *actor;
    OverworldPlayerDamageSource *event;
    u32 slot;
    u8 subjectDamage = source
        & OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE;

    source &= ~OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE;
    if (source >= OW_WILD_MAX_SPAWNS
        || runtime == NULL || runtime->conditions == NULL
        || !current(wild, source)) return;
    conditions = runtime->conditions;
    prepared = &conditions->actors[source];
    actor = &actors->slots[source].snapshot;
    if (!prepared->valid || !actor->active
        || prepared->subject.slot != source
        || actor->handle.slot != source
        || actor->handle.generation != prepared->subject.generation
        || actor->handle.fieldEpoch != actors->fieldEpoch
        || actor->handle.fieldEpoch != prepared->subject.fieldEpoch
        || actor->handle.mapGeneration != wild->mapGeneration
        || actor->handle.mapGeneration != prepared->subject.mapGeneration
        || actor->handle.encounterGeneration != wild->spawns[source].encounterGeneration
        || actor->handle.encounterGeneration != prepared->subject.encounterGeneration
        || actor->handle.reserved != prepared->subject.reserved
        || actor->subjectIdentity != wild->spawns[source].personality
        || actor->species != wild->spawns[source].species) return;
    if (subjectDamage) {
        conditions->actors[source].subjectDamagePending = 1;
        conditions->frame.valid = FALSE;
        return;
    }
    event = &conditions->playerDamage;
    event->fieldSystem = wild->movementFieldSystem;
    event->frame = actors->frame;
    event->source = actor->handle;
    event->pendingMask = 0;
    conditions->frame.valid = FALSE;
    for (slot = 0; slot < OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS; slot++) {
        prepared = &conditions->actors[slot];
        if (prepared->valid && prepared->subject.slot == slot
            && prepared->subject.fieldEpoch == actor->handle.fieldEpoch
            && prepared->subject.mapGeneration == actor->handle.mapGeneration) {
            event->recipientGenerations[slot] = prepared->subject.generation;
            event->pendingMask |= 1u << slot;
        }
    }
}
