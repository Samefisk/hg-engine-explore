"""Host proof for conditional-profile activation, timers, and targets."""

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


HARNESS = r"""
#include <assert.h>
#include <string.h>
#include "overworld_behavior_conditions.h"

static OverworldActorHandle Handle(unsigned slot, unsigned generation)
{
    OverworldActorHandle handle = {0};
    handle.slot = (u16)slot;
    handle.generation = (u16)generation;
    handle.fieldEpoch = 3;
    handle.mapGeneration = 4;
    handle.encounterGeneration = (u16)(generation + 10);
    return handle;
}

static OverworldBehaviorConditionDefinition PlayerTimed(unsigned app)
{
    OverworldBehaviorConditionDefinition value = {0};
    value.conditionId = 100 + app;
    value.applicationIndex = (u8)app;
    value.kind = OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED;
    value.activationMode = OVERWORLD_BEHAVIOR_CONDITION_TIMED;
    value.targetKind = OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    value.rangeKind = OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS;
    value.distance = 4;
    value.chance = 100;
    value.durationFrames = 10;
    value.cooldownFrames = 20;
    return value;
}

static OverworldBehaviorConditionDefinition PokemonWhile(unsigned app)
{
    OverworldBehaviorConditionDefinition value = {0};
    value.conditionId = 200 + app;
    value.applicationIndex = (u8)app;
    value.kind = OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED;
    value.activationMode = OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
    value.targetKind = OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR;
    value.rangeKind = OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS;
    value.distance = 5;
    value.chance = 100;
    return value;
}

static OverworldBehaviorConditionDefinition PokemonTimed(unsigned app)
{
    OverworldBehaviorConditionDefinition value = PokemonWhile(app);
    value.activationMode = OVERWORLD_BEHAVIOR_CONDITION_TIMED;
    value.durationFrames = 10;
    value.cooldownFrames = 5;
    return value;
}

int main(void)
{
    OverworldBehaviorConditionWorldView world = {0};
    OverworldBehaviorConditionDefinition definitions[3];
    OverworldBehaviorConditionEntryInput inputs[3] = {0};
    OverworldBehaviorConditionEntryState states[3] = {0};
    OverworldBehaviorConditionEntryResult entry;
    OverworldBehaviorConditionResult result;

    assert(sizeof(OverworldBehaviorConditionEntryState) == 16);

    world.subject = Handle(0, 1);
    world.subjectX = 10;
    world.subjectY = 10;
    world.playerValid = 1;
    world.playerX = 12;
    world.playerY = 10;
    world.actorCount = 2;
    world.actors[0].actor = Handle(1, 2);
    world.actors[0].x = 14;
    world.actors[0].y = 10;
    world.actors[0].valid = 1;
    world.actors[1].actor = Handle(2, 3);
    world.actors[1].x = 11;
    world.actors[1].y = 10;
    world.actors[1].valid = 1;

    definitions[0] = PlayerTimed(3);
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.triggered);
    assert(entry.target.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);

    world.frame = 5;
    world.playerX = 30;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && !entry.conditionTrue && !entry.triggered);

    world.frame = 10;
    world.playerX = 12;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active && !entry.triggered);

    world.frame = 20;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.triggered);
    assert(states[0].activeUntil == 30 && states[0].cooldownUntil == 40);

    definitions[1] = PokemonWhile(4);
    inputs[1].eligibleActorMask = 3;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[1], &inputs[1], &world, &states[1], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.triggered);
    assert(entry.target.actor.slot == 2);

    /* A Pokemon condition can observe actors without exporting one as the
     * profile target. */
    definitions[2] = PokemonWhile(4);
    definitions[2].targetKind = OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;
    inputs[2].eligibleActorMask = 3;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[2], &inputs[2], &world, &states[2], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active);
    assert(entry.target.kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE);

    world.actors[1].x = 30;
    world.actors[1].y = 30;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[1], &inputs[1], &world, &states[1], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[1], &inputs[1], &world, &states[1], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.triggered);
    assert(entry.target.actor.slot == 1);

    world.actors[0].valid = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[1], &inputs[1], &world, &states[1], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);
    assert(!entry.active);

    memset(states, 0, sizeof(states));
    world.actors[0].valid = 1;
    world.actors[0].x = 14;
    world.actors[0].y = 10;
    world.actors[1].x = 11;
    world.actors[1].y = 10;
    definitions[0] = PokemonWhile(5);
    definitions[0].conditionId = 300;
    definitions[1] = PokemonWhile(5);
    definitions[1].conditionId = 301;
    definitions[2] = PlayerTimed(6);
    inputs[0].eligibleActorMask = 1;
    inputs[1].eligibleActorMask = 2;
    assert(OverworldBehaviorCondition_Evaluate(
        definitions, inputs, states, 3, &world, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(result.activeApplicationMask == ((1u << 5) | (1u << 6)));
    assert(result.winningConditionIds[5] == 301);
    assert(result.targets[5].actor.slot == 2);
    assert(result.resolvedTarget.kind
        == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
    assert(result.resolvedTargetSourceApplication == 6);
    assert(result.resolvedTargetConditionId == 106);
    assert(result.winningConditionSourceApplication == 6);
    assert(result.winningConditionId == 106);

    /* The winning entry alone supplies the application trigger result. */
    definitions[0].activationMode = OVERWORLD_BEHAVIOR_CONDITION_TIMED;
    definitions[0].durationFrames = 10;
    definitions[0].cooldownFrames = 0;
    assert(OverworldBehaviorCondition_Evaluate(
        definitions, inputs, states, 2, &world, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert((result.triggeredApplicationMask & (1u << 5)) == 0);

    /* A timed refresh selects a fresh actor after cooldown. */
    memset(&states[0], 0, sizeof(states[0]));
    definitions[0] = PokemonTimed(7);
    inputs[0].eligibleActorMask = 3;
    world.frame = 100;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.target.actor.slot == 2);
    world.actors[1].x = 30;
    world.actors[1].y = 30;
    world.frame = 105;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.triggered && entry.target.actor.slot == 1);

    /* Reusing an actor slot with a new generation ends the held activation. */
    world.actors[0].actor = Handle(1, 9);
    world.frame = 106;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);
    assert(!entry.active);
    world.actors[0].actor = Handle(1, 2);

    /* The compact target still rejects an actor from another field epoch. */
    memset(&states[0], 0, sizeof(states[0]));
    world.frame = 200;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.target.actor.slot == 1);
    world.actors[0].actor.fieldEpoch = 9;
    world.frame = 201;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);
    assert(!entry.active);
    world.actors[0].actor.fieldEpoch = 3;

    memset(&states[0], 0, sizeof(states[0]));
    definitions[0] = PlayerTimed(7);
    definitions[0].durationFrames = 8;
    definitions[0].cooldownFrames = 20;
    world.frame = 0xFFFFFFFEu;
    world.playerX = 12;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.triggered);
    world.playerX = 30;
    world.frame = 5;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && !entry.triggered);
    world.frame = 6;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);
    world.frame = 7;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);

    definitions[0].kind = OVERWORLD_BEHAVIOR_CONDITION_TERRAIN_SPEED;
    definitions[0].activationMode = OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
    definitions[0].targetKind = OVERWORLD_BEHAVIOR_CONDITION_TARGET_NONE;
    definitions[0].durationFrames = 0;
    definitions[0].cooldownFrames = 0;
    definitions[0].terrainMask = 4;
    definitions[0].terrainOverrideMask = 4;
    definitions[0].minMovementSpeed = 5;
    definitions[0].maxMovementSpeed = 10;
    world.subjectTerrainMask = 4;
    world.subjectMovementSpeed = 7;
    memset(&states[0], 0, sizeof(states[0]));
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active);
    world.subjectTerrainMask = 1;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);

    /* Shared current Vision, custom Vision, occlusion, and inverse Vision
     * use the same bounded geometry for the player and actor targets. */
    memset(states, 0, sizeof(states));
    world.subjectX = 10;
    world.subjectY = 10;
    world.subjectFacing = OVERWORLD_VISION_FACING_NORTH;
    world.subjectVisionRange = OVERWORLD_VISION_DEFAULT_RANGE;
    world.subjectVisionOptions = OVERWORLD_VISION_DEFAULT_OPTIONS;
    world.playerValid = 1;
    world.playerX = 10;
    world.playerY = 7;
    world.playerFacingAndOcclusion = OVERWORLD_VISION_FACING_NORTH;
    world.playerVisionRange = OVERWORLD_VISION_DEFAULT_RANGE;
    world.playerVisionOptions = OVERWORLD_VISION_DEFAULT_OPTIONS;
    definitions[0] = PlayerTimed(8);
    definitions[0].activationMode = OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
    definitions[0].durationFrames = 0;
    definitions[0].cooldownFrames = 0;
    definitions[0].rangeKind =
        OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT;
    definitions[0].distance = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.conditionTrue);

    world.playerFacingAndOcclusion =
        OVERWORLD_VISION_FACING_NORTH
        | OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active && !entry.conditionTrue);

    memset(&states[0], 0, sizeof(states[0]));
    world.playerFacingAndOcclusion = OVERWORLD_VISION_FACING_NORTH;
    definitions[0].rangeKind =
        OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;
    definitions[0].distance = 2;
    definitions[0].reserved = OVERWORLD_VISION_DEFAULT_OPTIONS;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);
    definitions[0].distance = 3;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active);

    memset(&states[0], 0, sizeof(states[0]));
    definitions[0].kind =
        OVERWORLD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT;
    definitions[0].rangeKind =
        OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT;
    definitions[0].distance = 0;
    definitions[0].reserved = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.target.kind
        == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
    world.playerFacingAndOcclusion = OVERWORLD_VISION_FACING_SOUTH;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);

    memset(&states[0], 0, sizeof(states[0]));
    definitions[0].targetKind =
        OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR;
    inputs[0].eligibleActorMask = 1;
    world.actors[0].x = 10;
    world.actors[0].y = 7;
    world.actors[0].valid = 1;
    world.actors[0].facingAndOcclusion = OVERWORLD_VISION_FACING_NORTH;
    world.actors[0].visionRange = OVERWORLD_VISION_DEFAULT_RANGE;
    world.actors[0].visionOptions = OVERWORLD_VISION_DEFAULT_OPTIONS;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(entry.active && entry.target.kind
        == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);
    world.actors[0].facingAndOcclusion = OVERWORLD_VISION_FACING_SOUTH;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);

    /* Reject the full batch before an invalid later entry can mutate state. */
    memset(states, 0, sizeof(states));
    definitions[0] = PlayerTimed(1);
    definitions[1] = PlayerTimed(2);
    definitions[1].conditionId = OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    world.playerX = 12;
    world.frame = 200;
    assert(OverworldBehaviorCondition_Evaluate(
        definitions, inputs, states, 2, &world, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    assert((states[0].flags
        & (OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE
            | OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED)) == 0);

    assert(OverworldBehaviorCondition_Evaluate(
        definitions, inputs, states,
        OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES + 1,
        &world, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    return 0;
}
"""


RUNTIME_HARNESS = r"""
#include <assert.h>
#include <stdlib.h>
#include <string.h>

#include "overworld_behavior_condition_runtime.h"

extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static OverworldActorHandle Handle(unsigned slot, unsigned generation)
{
    OverworldActorHandle handle = {0};
    handle.slot = (u16)slot;
    handle.generation = (u16)generation;
    handle.fieldEpoch = 3;
    handle.mapGeneration = 4;
    handle.encounterGeneration = (u16)(generation + 10);
    return handle;
}

static void SetAllSubject(
    OverworldWildBehaviorDataBlob *blob,
    OverworldWildBehaviorConditionEntry *entry,
    unsigned application)
{
    OverworldWildBehaviorOverrideProfile *subject =
        &blob->overrideProfiles[0];
    memset(subject, 0, sizeof(*subject));
    subject->targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    subject->profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL;
    subject->match.terrain = 0xFF;
    subject->match.shiny = 0xFF;
    subject->match.behaviorClass = 0xFF;
    memset(entry, 0, sizeof(*entry));
    entry->conditionId = (u16)(500 + application);
    entry->applicationIndex = (u8)application;
    entry->subjectApplicationIndex = 0;
    entry->subjectMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    entry->chancePercent = 100;
}

int main(void)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    OverworldBehaviorConditionPreparedActor prepared = {0};
    OverworldBehaviorConditionEntryState preparedStates[2];
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    OverworldBehaviorConditionWorldView world = {0};
    OverworldBehaviorConditionCandidate candidates[2] = {0};
    OverworldWildBehaviorContext subjectContext = {0};
    BehaviorResolveRequest request = {0};
    OverworldWildBehaviorConditionEntry *entry;

    assert(sizeof(preparedStates) == 32);

    assert(blob != NULL);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    assert(blob->header.overrideProfileCount > 2);
    blob->header.conditionEntryCount = 2;

    request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    request.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    assert(OverworldBehaviorCondition_ValidateResolveRequest(blob, &request));
    request.requestVersion = 1;
    assert(!OverworldBehaviorCondition_ValidateResolveRequest(blob, &request));
    request.requestVersion = 0;
    assert(!OverworldBehaviorCondition_ValidateResolveRequest(blob, &request));
    request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;

    entry = &blob->conditionEntries[0];
    SetAllSubject(blob, entry, 1);
    entry->kind = OW_WILD_BEHAVIOR_CONDITION_POKEMON_NOTICED;
    entry->activationMode = OW_WILD_BEHAVIOR_CONDITION_WHILE_TRUE;
    entry->targetKind = OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR;
    entry->targetRoleMask = OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
    entry->targetSelection =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_SELECTION_NEAREST;
    entry->rangeKind = OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS;
    entry->rangeLength = 4;
    entry->targetMemberStart = 0;
    entry->targetMemberCount = 1;
    blob->overrideMembers[0] = 25;

    entry = &blob->conditionEntries[1];
    SetAllSubject(blob, entry, 2);
    entry->kind = OW_WILD_BEHAVIOR_CONDITION_TERRAIN_SPEED;
    entry->activationMode = OW_WILD_BEHAVIOR_CONDITION_WHILE_TRUE;
    entry->targetKind = OW_WILD_BEHAVIOR_CONDITION_TARGET_NONE;
    entry->terrainMask = 4;
    entry->terrainOverrideMask = 4;

    subjectContext.species = 16;
    subjectContext.level = 5;
    subjectContext.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    subjectContext.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    world.subject = Handle(0, 1);
    assert(OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared)
        == OVERWORLD_BEHAVIOR_CONDITION_STORAGE_REQUIRED);
    assert(!prepared.valid && prepared.count == 2);
    prepared.states = preparedStates;
    prepared.stateCapacity = 2;
    assert(OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(prepared.valid && prepared.count == 2);

    world.frame = 10;
    world.subjectX = 10;
    world.subjectY = 10;
    world.subjectTerrainMask = 4;
    world.subjectMovementSpeed = 8;
    world.actorCount = 2;
    world.actors[0].actor = Handle(1, 2);
    world.actors[0].x = 11;
    world.actors[0].y = 10;
    world.actors[0].valid = 1;
    candidates[0].context.species = 25;
    candidates[0].roleMask =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
    world.actors[1].actor = Handle(2, 3);
    world.actors[1].x = 12;
    world.actors[1].y = 10;
    world.actors[1].valid = 1;
    candidates[1].context.species = 25;
    candidates[1].roleMask =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER;

    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame,
        &scratch, &result) == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(result.activeApplicationMask == ((1u << 1) | (1u << 2)));
    assert(result.targets[1].kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);
    assert(result.targets[1].actor.slot == 1);
    assert(scratch.entryFlags[0]
        & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE);
    assert(scratch.entryFlags[1]
        & OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE);

    /* Reject the prepared batch before an invalid later entry mutates the
     * first condition's state. */
    memset(prepared.states, 0, sizeof(preparedStates));
    blob->conditionEntries[1].conditionId =
        OVERWORLD_BEHAVIOR_CONDITION_NO_ENTRY;
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame,
        &scratch, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    assert(prepared.states[0].flags == 0);
    blob->conditionEntries[1].conditionId = 502;
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame,
        &scratch, &result) == OVERWORLD_BEHAVIOR_CONDITION_OK);

    /* A reused candidate slot invalidates the captured complete actor handle. */
    world.actors[0].actor = Handle(1, 9);
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame + 1,
        &scratch, &result) == OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET);
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame + 2,
        &scratch, &result) == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(result.targets[1].actor.generation == 9);

    world.subject = Handle(0, 7);
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame + 3,
        &scratch, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    free(blob);
    return 0;
}
"""


class BehaviorConditionTests(unittest.TestCase):
    def test_wild_controller_uses_the_idle_intent_boundary(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        boundary = source.index("            if (actorMotionOwnsFacing) {")
        cooldown = source.index("            if (cooldown > 0) {", boundary)
        no_intent = source.index(
            "            if (!shouldIssueLookCommand) {", cooldown
        )
        evaluation = source.index(
            "            if (OverworldWildSpawns_IssueIdleIntent(", no_intent
        )
        self.assertLess(cooldown, no_intent)
        self.assertLess(no_intent, evaluation)

    def test_wild_controller_validates_the_condition_adapter(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        helper_start = source.index("OverworldWildSpawns_GetConditionAdapter(void)")
        helper_end = source.index(
            "OverworldWildSpawns_ClearConditionSlot(", helper_start
        )
        helper = source[helper_start:helper_end]
        for required in (
            "OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC",
            "OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION",
            "service->size != sizeof(*service)",
            "service->conditionAdapter == NULL",
            "OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_MAGIC",
            "OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION",
        ):
            self.assertIn(required, helper)
        actor = (
            ROOT
            / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
        ).read_text()
        for required in (
            "gOverworldBehaviorConditionAdapterEntry.prepareActor == NULL",
            "gOverworldBehaviorConditionAdapterEntry.clearActor == NULL",
            "gOverworldBehaviorConditionAdapterEntry.clearAll == NULL",
            "gOverworldBehaviorConditionAdapterEntry.clearResolution == NULL",
            "gOverworldBehaviorConditionAdapterEntry.evaluateActor == NULL",
            "gOverworldActorSystemMovementPolicyServiceEntry.conditionAdapter",
        ):
            self.assertIn(required, actor)

    def test_wild_condition_state_is_allocated_lazily(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        self.assertIn(
            "OverworldWildBehaviorConditionRuntime *conditions;",
            source,
        )
        ensure_start = source.index(
            "OverworldWildSpawns_EnsureConditionRuntime("
        )
        ensure_end = source.index(
            "#define OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT",
            ensure_start,
        )
        ensure = source[ensure_start:ensure_end]
        self.assertIn(
            "sys_AllocMemory(\n            HEAPID_WORLD,",
            ensure,
        )
        self.assertIn("sizeof(*runtime->conditions)", ensure)
        self.assertIn(
            "sizeof(OverworldWildBehaviorConditionRuntime) == 2072",
            (ROOT / "include/overworld_behavior_condition_adapter.h")
            .read_text(),
        )
        prepare_start = source.index(
            "OverworldWildSpawns_PrepareConditionsForSlot("
        )
        prepare_end = source.index(
            "#define OW_WILD_CONDITION_RESULT_TRIGGERED",
            prepare_start,
        )
        self.assertIn(
            "OverworldWildSpawns_EnsureConditionRuntime(state)",
            source[prepare_start:prepare_end],
        )
        self.assertIn("sys_FreeMemoryEz(runtime->conditions);", source)

    def test_every_chain_intent_boundary_rechecks_conditions(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        deferred_start = source.index(
            "static void __attribute__((noinline, optimize(\"Os\"))) OverworldWildSpawns_CommitDeferredChainMovementPause("
        )
        deferred_end = source.index(
            "OverworldWildSpawns_TryStartWalkStopSkid(", deferred_start
        )
        deferred = source[deferred_start:deferred_end]
        self.assertIn(
            "OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(",
            deferred,
        )
        self.assertLess(
            deferred.index("OverworldWildSpawns_IsChainActionReady(slot)"),
            deferred.index(
                "OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary("
            ),
        )
        finished_start = source.index(
            "static void __attribute__((optimize(\"Os\"))) OverworldWildSpawns_HandleFinishedMovementCommand("
        )
        finished_end = source.index(
            "OverworldWildSpawns_CompleteTeleportMovement(", finished_start
        )
        chain_start = source.index(
            "if ((policy.chainStepsRemaining", finished_start, finished_end
        )
        reposition_start = source.index(
            "OverworldWildSpawns_RunChainReposition(", chain_start, finished_end
        )
        self.assertIn(
            "OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(",
            source[chain_start:reposition_start],
        )

    def test_condition_allocation_failure_rejects_bind(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        startup_start = source.index("OverworldWildSpawns_StartSpawnStartup(")
        startup_end = source.index(
            "OverworldWildSpawns_CountActiveBehaviorLimitKey(", startup_start
        )
        startup = source[startup_start:startup_end]
        self.assertIn(
            "if (!OverworldWildSpawns_PrepareConditionsForSlot(", startup
        )
        self.assertIn("->unbind(", startup)

        transition_start = source.index(
            "static BOOL __attribute__((optimize(\"Os\"))) OverworldWildSpawns_ApplyTransitionWork("
        )
        transition_end = source.index(
            "OverworldWildSpawns_StartTiredEmoteWithProfile(", transition_start
        )
        transition = source[transition_start:transition_end]
        self.assertIn(
            "if (!OverworldWildSpawns_PrepareConditionsForSlot(", transition
        )

    def test_wild_timed_completion_tracks_only_winning_conditions(self):
        source = (
            ROOT
            / "lib/overworld/overworld_behavior_condition_adapter.c"
        ).read_text()
        evaluation_start = source.index(
            "OverworldBehaviorConditionAdapter_EvaluateActor("
        )
        evaluation_end = source.index(
            "const OverworldBehaviorConditionAdapterEntry",
            evaluation_start,
        )
        evaluation = source[evaluation_start:evaluation_end]
        self.assertIn(
            "runtime->result.winningConditionIds[", evaluation
        )
        self.assertIn("== entry->conditionId", evaluation)

    def test_wild_uses_tired_only_after_the_last_timed_profile_ends(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        evaluation_start = source.index(
            "OverworldWildSpawns_EvaluateConditionsForSlot("
        )
        evaluation_end = source.index(
            "OverworldWildSpawns_BehaviorSlotCacheMatches(", evaluation_start
        )
        evaluation = source[evaluation_start:evaluation_end]
        self.assertIn(
            "& (OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED\n"
            "                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED)",
            evaluation,
        )
        self.assertNotIn("return outcome.flags |", evaluation)
        self.assertNotIn("endingRequest", evaluation)
        self.assertNotIn("endedTimedApplicationMask", evaluation)
        boundary_start = source.index(
            'static BOOL __attribute__((noinline, optimize("Os")))\n'
            "OverworldWildSpawns_ResolveConditionsAtIntentBoundary("
        )
        boundary_end = source.index(
            "OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(",
            boundary_start,
        )
        boundary = source[boundary_start:boundary_end]
        self.assertIn(
            "OverworldWildSpawns_GetActiveConditionApplications(state, slot) == 0",
            boundary,
        )

    def test_alert_completion_rechecks_conditions_before_owner_work(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        resume_start = source.index("OverworldWildSpawns_ResumeOwnerAfterAlert(")
        resume_end = source.index("OverworldWildSpawns_TickSpotEmote(", resume_start)
        resume = source[resume_start:resume_end]
        evaluation = resume.index(
            "OverworldWildSpawns_ResolveConditionsAtIntentBoundary("
        )
        teleport = resume.index(
            "OverworldWildSpawns_PrepareConditionalTeleport("
        )
        pickup = resume.index("OverworldWildSpawns_TryStartPickupThrowAction(")
        self.assertLess(evaluation, teleport)
        self.assertLess(evaluation, pickup)

    def test_portable_evaluator(self):
        with tempfile.TemporaryDirectory(prefix="behavior-conditions-") as directory:
            source = Path(directory) / "conditions.c"
            binary = Path(directory) / "conditions"
            source.write_text(HARNESS)
            command = [
                *shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                "-I",
                str(ROOT / "include"),
                str(source),
                str(ROOT / "lib/overworld/overworld_behavior_conditions.c"),
                str(ROOT / "lib/overworld/overworld_vision.c"),
                "-o",
                str(binary),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )
            completed = subprocess.run(
                [str(binary)], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )

    def test_prepared_runtime_adapter(self):
        with tempfile.TemporaryDirectory(prefix="behavior-condition-runtime-") as directory:
            source = Path(directory) / "condition_runtime.c"
            binary = Path(directory) / "condition_runtime"
            source.write_text(RUNTIME_HARNESS)
            command = [
                *shlex.split(os.environ.get("HOST_CC", "cc")),
                "-std=c11",
                "-O2",
                "-Wall",
                "-Wextra",
                "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                "-I",
                str(ROOT / "include"),
                str(source),
                str(ROOT / "lib/overworld/overworld_behavior_conditions.c"),
                str(ROOT / "lib/overworld/overworld_vision.c"),
                str(ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"),
                str(ROOT / "data/OverworldWildBehaviorData.c"),
                "-o",
                str(binary),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )
            completed = subprocess.run(
                [str(binary)], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )

    def test_arm_compile(self):
        compiler = shutil.which("arm-none-eabi-gcc")
        if compiler is None:
            compiler = "/opt/homebrew/bin/arm-none-eabi-gcc"
        self.assertTrue(Path(compiler).is_file(), "arm-none-eabi-gcc is required")
        with tempfile.TemporaryDirectory(prefix="behavior-conditions-arm-") as directory:
            output = Path(directory) / "conditions.o"
            completed = subprocess.run(
                [
                    compiler,
                    "-std=c11",
                    "-mthumb",
                    "-mcpu=arm7tdmi",
                    "-fno-builtin",
                    "-w",
                    "-Werror=incompatible-pointer-types",
                    "-I",
                    str(ROOT / "include"),
                    "-c",
                    str(ROOT / "lib/overworld/overworld_behavior_conditions.c"),
                    "-o",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )

        with tempfile.TemporaryDirectory(prefix="behavior-condition-runtime-arm-") as directory:
            output = Path(directory) / "condition_runtime.o"
            completed = subprocess.run(
                [
                    compiler,
                    "-std=c11",
                    "-mthumb",
                    "-mcpu=arm7tdmi",
                    "-fno-builtin",
                    "-w",
                    "-Werror=incompatible-pointer-types",
                    "-I",
                    str(ROOT / "include"),
                    "-c",
                    str(ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"),
                    "-o",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )


if __name__ == "__main__":
    unittest.main()
