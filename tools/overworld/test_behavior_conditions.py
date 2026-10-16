"""Host proof for conditional-profile activation, timers, and targets."""

from pathlib import Path
import importlib.util
import re
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
    /* Damage is an accepted-source event, independent of Vision or distance.
     * Mere proximity and an unmarked nearer actor cannot select its target. */
    memset(states, 0, sizeof(states));
    definitions[0] = PokemonWhile(0);
    definitions[0].kind = OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED;
    definitions[0].rangeKind = 0;
    definitions[0].distance = 0;
    inputs[0].eligibleActorMask = 3;
    world.actors[0].x = -100;
    world.actors[0].y = 100;
    world.actors[0].facingAndOcclusion = 0;
    world.actors[1].facingAndOcclusion = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK && !entry.active);
    world.actors[0].facingAndOcclusion =
        OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK && entry.active && entry.triggered);
    assert(entry.target.actor.slot == world.actors[0].actor.slot);
    world.actors[0].facingAndOcclusion = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(
        &definitions[0], &inputs[0], &world, &states[0], &entry)
        == OVERWORLD_BEHAVIOR_CONDITION_OK && !entry.active);
    /* A brief moving sighting activates immediately. Geometry is read-only;
     * only presentation waits until the ordinary motion ends. */
    memset(states, 0, sizeof(states));
    definitions[0] = PlayerTimed(0);
    definitions[0].activationMode = OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH;
    definitions[0].durationFrames = 0;
    definitions[0].rangeKind = OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;
    definitions[0].distance = 32;
    definitions[0].reserved = OVERWORLD_VISION_CONE_CARDINAL_LINES;
    world.subjectX = 601; world.subjectY = 402;
    world.playerValid = 1; world.playerX = 606; world.playerY = 403;
    world.playerFacingAndOcclusion = world.reserved[0] = 0;
    world.frame = 300;
    inputs[0].chanceRoll = 0;
    inputs[0].reserved = OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !entry.active && !entry.triggered
        && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    world.playerY = 402;
    OverworldBehaviorConditionEntryState before = states[0];
    inputs[0].reserved = OVERWORLD_BEHAVIOR_CONDITION_INPUT_NOTICE_GEOMETRY;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && entry.conditionTrue && !entry.active && !entry.triggered
        && !memcmp(&before, &states[0], sizeof(before)));
    inputs[0].reserved = OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && entry.active && entry.triggered
        && (states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING)
        && states[0].targetKind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER
        && states[0].activeUntil == 0 && states[0].cooldownUntil == 0);
    before = states[0]; world.frame++; world.playerY = 403;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !memcmp(&before, &states[0], sizeof(before)));
    inputs[0].reserved = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && entry.active && entry.triggered
        && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && entry.active && !entry.triggered);
    /* Crash/cooldown still require a fresh false-to-true rearm. */
    states[0].flags |= OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !entry.active);
    world.frame = states[0].cooldownUntil; world.playerY = 402;
    inputs[0].reserved = OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    world.playerY = 403;
    inputs[0].reserved = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_REARM));
    inputs[0].reserved = OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE;
    world.playerY = 402; definitions[0].chance = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    definitions[0].chance = 100; world.playerFacingAndOcclusion = 4;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    world.playerFacingAndOcclusion = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && (states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    world.playerValid = 0; inputs[0].reserved = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET
        && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    /* A recycled Pokémon cannot substitute for the pending full target. */
    memset(states, 0, sizeof(states)); definitions[0] = PokemonWhile(0);
    definitions[0].activationMode = OVERWORLD_BEHAVIOR_CONDITION_UNTIL_CRASH;
    world.actorCount = 1; world.actors[0].actor = Handle(1, 8);
    world.actors[0].x = 602; world.actors[0].y = 402; world.actors[0].valid = 1;
    world.actors[0].facingAndOcclusion = 0; inputs[0].eligibleActorMask = 1;
    inputs[0].reserved = OVERWORLD_BEHAVIOR_CONDITION_INPUT_MOVING_NOTICE;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == 0 && (states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
    world.actors[0].actor.generation++; inputs[0].reserved = 0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&definitions[0], &inputs[0], &world,
        &states[0], &entry) == OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET
        && !(states[0].flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_NOTICE_PENDING));
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
    OverworldWildBehaviorOverrideProfile savedApplication;
    OverworldWildBehaviorConditionEntry savedEntry;
    const u8 tail = OWBD_MASKABLE_APPLICATION_COUNT;
    const u8 last = OWBD_MASKABLE_APPLICATION_COUNT - 1;

    assert(sizeof(preparedStates) == 32);

    assert(blob != NULL);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    assert(blob->header.overrideProfileCount > 2);
    assert(blob->header.overrideProfileCount > tail);
    assert(OVERWORLD_BEHAVIOR_CONDITION_MAX_APPLICATIONS == 32);
    assert(OWBD_MASKABLE_APPLICATION_COUNT == 32);
    assert(sizeof(result.targets) / sizeof(result.targets[0]) == 32);
    blob->header.conditionEntryCount = 2;
    memset(blob->conditionOptions, 0, 2 * sizeof(blob->conditionOptions[0]));

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

    /* The external resolver validator keeps bit31 and rejects a byte-index
     * Tired tail as a conditional target before any mask shift. */
    savedApplication = blob->overrideProfiles[last];
    savedEntry = blob->conditionEntries[0];
    blob->overrideProfiles[last].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL;
    request.forcedOverrideMask = 1u << last;
    assert(OverworldBehaviorCondition_ValidateResolveRequest(blob, &request));
    request.forcedOverrideMask = 0;
    blob->overrideProfiles[last].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[last].conditionStart = 0;
    blob->overrideProfiles[last].conditionCount = 1;
    blob->conditionEntries[0].conditionId = 1337;
    blob->conditionEntries[0].targetKind = OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    request.activeConditionalMask = 1u << last;
    request.winningConditionId = request.resolvedTargetConditionId = 1337;
    request.resolvedTarget.kind = BEHAVIOR_RESOLVE_TARGET_PLAYER;
    request.targetSourceApplication = last;
    assert(OverworldBehaviorCondition_ValidateResolveRequest(blob, &request));
    request.targetSourceApplication = tail;
    assert(!OverworldBehaviorCondition_ValidateResolveRequest(blob, &request));
    blob->overrideProfiles[last] = savedApplication;
    blob->conditionEntries[0] = savedEntry;
    request.activeConditionalMask = 0;
    request.winningConditionId = request.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.resolvedTarget.kind = BEHAVIOR_RESOLVE_TARGET_NONE;
    request.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;

    /* The shared condition blob gate accepts only disabled, nonconditional
     * tail rows with no condition entries. It still has 32 result slots. */
    savedApplication = blob->overrideProfiles[tail];
    blob->overrideProfiles[tail].targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    assert(OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    blob->overrideProfiles[tail] = savedApplication;
    blob->overrideProfiles[tail].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    assert(OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    blob->overrideProfiles[tail] = savedApplication;
    blob->overrideProfiles[tail].conditionCount = 1;
    assert(OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    blob->overrideProfiles[tail] = savedApplication;
    blob->overrideProfiles[tail].conditionStart = 255; /* unused with count0 */
    assert(OverworldBehaviorCondition_PrepareActor(
        blob, sizeof(*blob), &subjectContext, &world.subject, &prepared)
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    blob->overrideProfiles[tail] = savedApplication;

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
    blob->conditionEntries[1].applicationIndex = tail;
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame,
        &scratch, &result)
        == OVERWORLD_BEHAVIOR_CONDITION_INVALID_DEFINITION);
    assert(prepared.states[0].flags == 0);
    blob->conditionEntries[1].applicationIndex = 2;
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



def idle_boundary_harness(source=None):
    """Exact per-actor scheduling/boundary C; native gates and adapter inputs stubbed."""
    if source is None:
        source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    spec = importlib.util.spec_from_file_location(
        "condition_idle_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py"
    )
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    tick = extract.production_function(source, "OverworldWildSpawns_TickMovementParams", "void")
    # Global battle/overlap work precedes this per-actor block and is outside
    # this bounded fixture. Every actor gate/pause/intent branch is retained.
    tick_prefix = tick[:tick.index("    state->movementFieldSystem = fieldSystem;")]
    loop_start = tick.index("    for (i = 0;")
    if "    for (int pass =" in tick:
        loop_start = tick.index("    for (int pass =")
    tick_loop = tick[loop_start:tick.rfind("\n}")]
    result_type = "u8" if re.search(
        r"static\s+u8\b[^;{}]*OverworldWildSpawns_ResolveConditionsAtIntentBoundary\(", source
    ) else "BOOL"
    boundary = extract.production_function(
        source, "OverworldWildSpawns_ResolveConditionsAtIntentBoundary", result_type
    )
    chain = extract.production_function(
        source, "OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary", "BOOL"
    )
    moving_notice = extract.production_function(
        source, "OverworldWildSpawns_SampleMovingNoticeForSlot", "void"
    )
    evaluation = extract.production_function(source, "OverworldWildSpawns_EvaluateConditionsForSlot", "u16")
    # Execute the actual native outcome mapping, including its private failure
    # bit allocation; this is not a copied profile-change result.
    mapping = evaluation[evaluation.rfind("    return"):evaluation.rfind("\n}")]
    definitions = {}
    for text in (source, (ROOT / "include/overworld_wild_spawns_internal.h").read_text(),
                 (ROOT / "include/overworld_behavior_condition_adapter.h").read_text(),
                 (ROOT / "include/overworld_wild_movement.h").read_text()):
        for line in text.replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)", line)
            if match:
                definitions[match[1]] = line
    names = [
        "OW_WILD_CONDITION_RESULT_TRIGGERED", "OW_WILD_CONDITION_RESULT_TIMED_ENDED",
        "OW_WILD_CONDITION_RESULT_FAIL_CLOSED", "OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK",
        "OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING", "OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND",
        "OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK", "OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN",
        "OW_WILD_SPAWNER_THROW_TARGET_NONE", "OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG",
        "OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG", "OW_WILD_SPAWNER_THROW_TARGET_DECODE",
        "OW_WILD_SPAWNER_THROW_TARGET_SLOT_MASK", "OW_WILD_SPAWN_AGGRO_PENDING_FLAG",
        "OW_WILD_SPAWNER_SPOT_STATE_CHILL", "OW_WILD_SPAWNER_SPOT_STATE_EMOTING", "OW_WILD_SPAWNER_SPOT_STATE_TIRED",
        "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED", "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED",
        "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
        "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED",
        "OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_DURING_MOVEMENT",
        "OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE", "OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO",
    ]
    constants = "\n".join(definitions[name] for name in names if name in definitions)
    for name in ("OW_WILD_CONDITION_RESULT_PROFILE_CHANGED", "OW_WILD_CONDITION_BOUNDARY_READY"):
        if name in definitions:
            constants += "\n" + definitions[name]
    if "sOverworldWildMovementFrameTaskExecuting" in definitions:
        constants += "\n" + definitions["sOverworldWildMovementFrameTaskExecuting"]
    else:
        constants += "\n#define sOverworldWildMovementFrameTaskExecuting sOverworldWildFlags.movementFrameTaskExecuting"
    reset = re.search(r"sOverworldWildFlags\.intentConditionsCheckedMask\s*=\s*0;", source)
    frame_reset = reset.group(0) if reset else "/* Pre-fix code has no per-frame marker reset. */"
    marker = re.search(r"\b(u8|u16)\s+intentConditionsCheckedMask;", source)
    marker_type = marker.group(1) if marker else "u8"
    policy_header = (ROOT / "include/overworld_wild_movement.h").read_text()
    policy_values = "\n".join(re.search(
        r"typedef struct " + name + r"\s*\{[\s\S]*?\}\s*" + name + r";", policy_header
    ).group(0) for name in ("OverworldWildWalkMomentumState", "OverworldActorPolicyView"))
    return (
        IDLE_SUPPORT_PREFIX.replace("/* @POLICY_VALUES@ */", policy_values) + constants
        + IDLE_SUPPORT.replace("/* @MARKER_TYPE@ */", marker_type)
        + "\nstatic u16 MapOutcome(u8 flags, u8 direction) {\n"
        + "    struct { u8 flags; } outcome = {flags};\n" + mapping + "\n}\n"
        + boundary + "\n" + chain + "\n" + moving_notice + "\n" + IDLE_INTENT_STUB
        + tick_prefix + "    (void)fieldSystem;\n" + tick_loop + "\n}\n"
        + "static void BeginFrame(void) { " + frame_reset
        + " sOverworldWildMovementFrameTaskExecuting = TRUE; }\n" + IDLE_DRIVER
    )


IDLE_SUPPORT_PREFIX = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
/* Native engine objects are boundary stubs; keep the real policy/motion
 * values while avoiding declarations of ARM-only engine functions on host. */
#define TYPES_H
#define TRUE 1
#define FALSE 0
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64;
typedef int8_t s8; typedef int16_t s16; typedef int32_t s32; typedef int64_t s64;
typedef int BOOL;
#include "overworld_motion_model.h"
/* @POLICY_VALUES@ */
"""

IDLE_SUPPORT = r"""
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
#define OW_WILD_RETURN_NONE 0
#define OW_WILD_BEHAVIOR_REACTION_NONE 0
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 16
#define OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(value) ((value) & 1)
typedef struct LocalMapObject { u8 unused; } LocalMapObject;
typedef struct FieldSystem { u8 unused; } FieldSystem;
typedef struct OverworldWildBehaviorProfile { struct { u8 walkOptions; } owner; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { u8 tiredReaction; } OverworldWildBehaviorPrimitives;
typedef struct OverworldWildOverlayRuntimeState {
    struct { u8 targets[10]; u16 recoveringMask,carrierMask,targetMask; } throwState;
    struct { u8 phase; } returnMoves[10];
    struct { u16 distanceDespawnPendingMask; } spawnPresentations;
    u8 movementEmotePlayHopSound[10];
    struct { struct { struct { u8 flags; } bindings[2]; } bindings[10]; } *conditions;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    struct { u8 active; LocalMapObject *object; } spawns[10];
    u16 captureTargetMask;
    u8 movementCooldowns[10], movementStagedHopPending[10], movementActorControlModes[10];
    u8 movementCrashShakeTimers[10], movementTeleportVisiblePause[10], movementSpotStates[10];
    u8 movementSpawnRunActive[10];
    int movementQueuedBattleSlot;
    FieldSystem *movementFieldSystem;
    OverworldWildOverlayRuntimeState runtime;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) (&(state)->runtime)
static struct { u8 movementFrameTaskExecuting; /* @MARKER_TYPE@ */ intentConditionsCheckedMask; } sOverworldWildFlags;
static OverworldWildSpawnState state;
static LocalMapObject object;
static FieldSystem field;
static OverworldActorPolicyView nativePolicy;
static unsigned conditionCalls, idleCalls, tiredCalls, alertCalls, clearThrowCalls;
static unsigned fixtureActiveApplications, outcomeFlags, failClosed, nativeSingle, gate;
static int refreshedPause;
static u8 tiredReaction;
static u16 MapOutcome(u8,u8);
static u16 OverworldWildSpawns_EvaluateConditionsForSlot(
    OverworldWildSpawnState *s, FieldSystem *f, int slot,
    OverworldWildBehaviorProfile *profile, OverworldWildBehaviorPrimitives *primitives,int operation)
{
    (void)f; (void)profile;
    if(operation==OVERWORLD_BEHAVIOR_CONDITION_SAMPLE_MOVING_NOTICE||operation==OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO)return 0;
    conditionCalls++;
    primitives->tiredReaction = tiredReaction;
    if (refreshedPause >= 0) s->movementCooldowns[slot] = (u8)refreshedPause;
    return failClosed ? OW_WILD_CONDITION_RESULT_FAIL_CLOSED : MapOutcome((u8)outcomeFlags,0);
}
#define OverworldWildSpawns_GetActiveConditionApplications(...) fixtureActiveApplications
#define OverworldWildSpawns_ClearThrowStateForSlot(...) (++clearThrowCalls)
#define OverworldWildSpawns_StartTiredEmoteWithProfile(...) (++tiredCalls)
#define OverworldWildSpawns_TryStartSpotEmote(...) (++alertCalls, gate == 18)
#define OverworldWildSpawns_IsCurrentSpawnObject(...) TRUE
#define OverworldWildSpawns_EnterAggroState(...) ((void)0)
#define OverworldWildSpawns_GetControllerLane(p,...) (&(p)->owner)
#define OverworldWildSpawns_GetCurrentMovementLocomotion(...) 0
#define OverworldWildSpawns_ClearWalkMovementState(...) ((void)0)
#define OverworldWildSpawns_ApplyHelpChildSpawnState(...) ((void)0)
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
    OverworldWildSpawnState *s,int slot,OverworldWildBehaviorProfile *p,OverworldWildBehaviorPrimitives *pr)
{ (void)s;(void)slot;memset(p,0,sizeof(*p));memset(pr,0,sizeof(*pr));pr->tiredReaction=tiredReaction; }
static BOOL OverworldActorPolicy_Inspect(u8 slot,OverworldActorPolicyView *p)
{ (void)slot;*p=nativePolicy;return TRUE; }
#define OverworldWildSpawns_ApplyFacePlayerFacing(...) ((void)0)
#define OverworldWildSpawns_SyncCarriedThrowTarget(...) ((void)0)
#define OverworldWildSpawns_IsMovementSlotInProgress(...) (gate == 3)
#define OverworldWildSpawns_EnsureFrameMovementTask(...) ((void)0)
#define OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST 0
#define OVERWORLD_TARGET_BINDING_BOUND 1
#define OverworldWildSpawns_GetInteractionObservation(...) 0
#define OverworldWildSpawns_GetBehaviorDataBlob(...) 0
#define OverworldWildSpawns_ApplyQueuedCombat(...) (gate == 4)
#define OverworldWildSpawns_TickCustomJumpRenderSettle(...) (gate == 5)
#define OverworldWildSpawns_ContinuePendingStagedHop(...) ((void)0)
#define OverworldWildSpawns_CommitDeferredChainMovementPause(...) ((void)0)
#define OverworldWildSpawns_TickSpotEmote(...) (gate == 9)
#define OverworldWildSpawns_TickTiredEmote(...) (gate == 10)
#define OverworldWildSpawns_UpdateSpawnMoveTargetState(...) (gate == 11)
#define OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(...) FALSE
#define MapObject_IsSingleMovementActive(...) nativeSingle
"""

IDLE_INTENT_STUB = r"""
static BOOL OverworldWildSpawns_IssueIdleIntent(
    OverworldWildSpawnState *s,FieldSystem *f,int slot,LocalMapObject *o,
    OverworldWildBehaviorProfile *p,OverworldWildBehaviorPrimitives *pr)
{ (void)s;(void)f;(void)slot;(void)o;(void)p;(void)pr;idleCalls++;return FALSE; }
"""

IDLE_DRIVER = r"""
static void Reset(void)
{
    memset(&state,0,sizeof(state));memset(&nativePolicy,0,sizeof(nativePolicy));
    memset(&sOverworldWildFlags,0,sizeof(sOverworldWildFlags));
    state.spawns[0].active=1;state.spawns[0].object=&object;
    state.movementFieldSystem=&field;state.movementQueuedBattleSlot=-1;
    state.movementCooldowns[0]=12;state.movementTeleportVisiblePause[0]=TRUE;
    conditionCalls=idleCalls=tiredCalls=alertCalls=clearThrowCalls=0;
    fixtureActiveApplications=outcomeFlags=failClosed=nativeSingle=gate=0;
    refreshedPause=-1;tiredReaction=0;BeginFrame();
}
static void Tick(void) { OverworldWildSpawns_TickMovementParams(&state,&field,TRUE,1); }
#define CHECK(value) do { if (!(value)) { fprintf(stderr,"idle boundary line%d: %s\n",__LINE__,#value);return 1; } } while(0)
int main(void)
{
    /* An ordinary Routine pause is not a condition evaluation barrier. */
    Reset();fixtureActiveApplications=1;outcomeFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED;
    Tick();CHECK(conditionCalls==1 && idleCalls==1 && state.movementCooldowns[0]==OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN);
    CHECK(!state.movementTeleportVisiblePause[0]);
    /* Stable active/ordinary profiles preserve the remaining Routine pause. */
    Reset();fixtureActiveApplications=1;Tick();CHECK(conditionCalls==1 && idleCalls==0 && state.movementCooldowns[0]==11);
    Reset();Tick();CHECK(conditionCalls==1 && idleCalls==0 && state.movementCooldowns[0]==11);
    /* Expiry resolves the new Routine but does not clear its pause. The fresh
     * pause must be read after resolution instead of using the prior copy. */
    Reset();outcomeFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED|OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED;
    refreshedPause=17;Tick();CHECK(conditionCalls==1 && idleCalls==0 && state.movementCooldowns[0]==16);
    /* Fail-closed, Tired, held relation release and alert retain ownership. */
    Reset();failClosed=1;Tick();CHECK(conditionCalls==1 && idleCalls==0 && state.movementCooldowns[0]==12);
    Reset();outcomeFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED;tiredReaction=1;
    Tick();CHECK(tiredCalls==1 && idleCalls==0 && state.movementCooldowns[0]==12);
    Reset();state.runtime.throwState.targets[0]=2;Tick();CHECK(clearThrowCalls==1 && idleCalls==0 && state.movementCooldowns[0]==12);
    Reset();fixtureActiveApplications=1;outcomeFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED|OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED;gate=18;
    Tick();CHECK(alertCalls==1 && idleCalls==0 && state.movementCooldowns[0]==12);
    /* Every preceding per-actor owner/gate remains before evaluation. */
    for (unsigned current=1;current<=16;current++) {
        Reset();gate=current;
        if(current==1)state.captureTargetMask=1;
        if(current==2)state.runtime.spawnPresentations.distanceDespawnPendingMask=1;
        if(current==6)state.movementStagedHopPending[0]=1;
        if(current==7)nativePolicy.chainPauseAction=OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING;
        if(current==8)state.movementActorControlModes[0]=OW_WILD_ACTOR_CONTROL_HELD;
        if(current==12)state.movementCrashShakeTimers[0]=1;
        if(current==13)state.movementQueuedBattleSlot=0;
        if(current==14)state.runtime.throwState.targets[0]=OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG;
        if(current==15)nativePolicy.motionPhase=OVERWORLD_MOTION_PHASE_MOVING;
        if(current==16)nativeSingle=1;
        if(current==5)OverworldWildSpawns_TickMovementParams(&state,&field,FALSE,0);
        else Tick();
        CHECK(conditionCalls==0 && idleCalls==0);
    }
    /* A terminal chain/render-settle can resolve without an old in-progress
     * bit. Its real chain boundary marks this frame and the next idle pass
     * must not evaluate or decrement pause again. Normal Walk stays unmarked. */
    for (unsigned slot=0;slot<OW_WILD_MAX_SPAWNS;slot++) {
        Reset();OverworldWildBehaviorProfile p={0};
        state.spawns[0].active=FALSE;state.spawns[slot].active=TRUE;state.spawns[slot].object=&object;
        state.movementCooldowns[slot]=12;state.movementTeleportVisiblePause[slot]=TRUE;
        CHECK(OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(&state,slot,&p));
        CHECK(conditionCalls==1);nativePolicy.chainPauseAction=0;
        OverworldWildSpawns_TickMovementParams(&state,&field,TRUE,(u16)(1u<<slot));
        CHECK(conditionCalls==1 && idleCalls==0 && state.movementCooldowns[slot]==12);
        BeginFrame();fixtureActiveApplications=1;outcomeFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED;
        OverworldWildSpawns_TickMovementParams(&state,&field,TRUE,(u16)(1u<<slot));
        CHECK(conditionCalls==2 && idleCalls==1 && state.movementCooldowns[slot]==OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN);
    }
    Reset();state.movementCooldowns[0]=0;Tick();CHECK(conditionCalls==1 && idleCalls==1);
    CHECK(MapOutcome(OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED,0)!=OW_WILD_CONDITION_RESULT_FAIL_CLOSED);
    printf("actual idle condition boundary: paused trigger/stable pause/expiry/16 gates/10-slot terminal dedup+reset/normal Walk passed\n");
    return 0;
}
"""


ALERT_PUBLICATION_PRELUDE = r"""
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "host-adapter.h"
struct FieldSystem { u8 unused; };
struct OverworldWildSpawnState { u8 unused; };
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_CONDITION_RESULT_FAIL_CLOSED (1u << 3)
#define OVERWORLD_CONDITION_VISIBILITY_POPULATE_ENTRY Visibility
static OverworldWildBehaviorConditionRuntime runtime;
static OverworldWildBehaviorDataBlob blob;
static OverworldWildSpawnState state;
static FieldSystem field;
static unsigned evaluateCalls,applyCalls,healthCalls,failedCalls;
static u8 nextFlags,mounted,missing;
static u32 nextMask;
static OverworldTargetBinding nextInterest;
static int status;
static void Context(OverworldWildBehaviorContext *c,const OverworldWildSpawn *s,u16 species,u8 level,u8 terrain,u8 shiny)
{ (void)c;(void)s;(void)species;(void)level;(void)terrain;(void)shiny; }
static BOOL Current(FieldSystem *f,const OverworldWildSpawn *s)
{ (void)f;(void)s;return TRUE; }
static u16 Terrain(FieldSystem *f,int x,int y)
{ (void)f;(void)x;(void)y;return 1; }
static void Visibility(FieldSystem *f,OverworldBehaviorConditionWorldView *w)
{ (void)f;(void)w; }
static u32 OverworldWildSpawns_GetInteractionObservation(OverworldWildSpawnState*s,int slot,const OverworldWildBehaviorProfile*p,const OverworldWildBehaviorDataBlob*b,OverworldWildBehaviorConditionRuntime*r)
{ (void)s;(void)slot;(void)p;(void)b;(void)r;return 0; }
#define OverworldWildSpawns_ReadNoticeFacts OverworldWildSpawns_GetInteractionObservation
static OverworldBehaviorConditionStatus Evaluate(OverworldWildBehaviorConditionRuntime*r,OverworldWildSpawnState*s,FieldSystem*f,const void*b,u32 z,u8 slot,u8 speed,const OverworldWildBehaviorProfile*p,OverworldBehaviorConditionObserveFunc observe,int mode,OverworldBehaviorConditionBuildContextFunc context,OverworldBehaviorConditionIsCurrentSpawnFunc current,OverworldBehaviorConditionTerrainFunc terrain,OverworldBehaviorConditionPopulateVisibilityFunc visibility,OverworldBehaviorConditionAdapterOutcome*out)
{
 (void)s;(void)f;(void)b;(void)z;(void)speed;(void)p;(void)observe;(void)context;(void)current;(void)terrain;(void)visibility;
 evaluateCalls++;memset(out,0,sizeof(*out));
 if(status)return (OverworldBehaviorConditionStatus)status;
 if(mode==OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO)return OVERWORLD_BEHAVIOR_CONDITION_OK;
 out->flags=nextFlags;out->targetDx=1;r->activeApplicationMasks[slot]=nextMask;
 r->bindings[slot].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST]=nextInterest;
 return OVERWORLD_BEHAVIOR_CONDITION_OK;
}
static const OverworldBehaviorConditionAdapterEntry adapter={.evaluateActor=Evaluate};
static BOOL OverworldWildSpawns_MountIsActive(void){return mounted;}
static const OverworldBehaviorConditionAdapterEntry *OverworldWildSpawns_GetConditionAdapter(void){return missing==1?NULL:&adapter;}
static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void){return missing==2?NULL:&blob;}
static OverworldWildBehaviorConditionRuntime *OverworldWildSpawns_GetConditionRuntime(OverworldWildSpawnState*s){(void)s;return missing==3?NULL:&runtime;}
#define OverworldWildSpawns_BuildBehaviorContext Context
#define OverworldWildSpawns_IsCurrentSpawnObject Current
#define OverworldWildSpawns_GetConditionTerrainBit Terrain
static u16 OverworldWildSpawns_FailClosedConditionResolution(OverworldWildSpawnState*s,int slot,const OverworldBehaviorConditionAdapterEntry*a,OverworldWildBehaviorConditionRuntime*r)
{ (void)s;(void)slot;(void)a;(void)r;failedCalls++;return OW_WILD_CONDITION_RESULT_FAIL_CLOSED; }
static void OverworldWildSpawns_ApplyBehaviorResolution(OverworldWildSpawnState*s,int slot,const BehaviorResolveResult*r)
{ (void)s;(void)slot;assert(r==&runtime.resolution);applyCalls++; }
static void OverworldWildSpawns_PublishHealthProfile(OverworldWildSpawnState*s,int slot,const OverworldWildBehaviorProfile*p)
{ (void)s;(void)slot;assert(memcmp(p,&runtime.resolution.profile,sizeof(*p))==0);healthCalls++; }
static u8 OverworldWalk_DirectionFromDelta(int x,int y){assert(x==1&&y==0);return 3;}
"""

ALERT_PUBLICATION_DRIVER = r"""
static OverworldWildBehaviorProfile prior;
static OverworldWildBehaviorPrimitives primitives;
static void Reset(void){
 memset(&runtime,0,sizeof(runtime));memset(&prior,0x5a,sizeof(prior));
 runtime.resolution.profile=prior;memset(&runtime.resolution.primitives,0xa5,sizeof(primitives));
 runtime.frame.world.subjectFacing=2;
 OverworldTargetBinding *interest=&runtime.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
 interest->flags=OVERWORLD_TARGET_BINDING_BOUND;interest->target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
 interest->target.actor=(OverworldActorHandle){0,1,3,3,1,0};
 interest->sourceConditionId=12365;interest->sourceApplication=19;nextInterest=*interest;
 runtime.activeApplicationMasks[7]=1u<<19;nextMask=1u<<19;
 nextFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED|OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED;
 evaluateCalls=applyCalls=healthCalls=failedCalls=status=mounted=missing=0;
}
static u16 Run(void){return OverworldWildSpawns_EvaluateConditionsForSlot(&state,&field,7,&prior,&primitives,-1);}
int main(void){
 _Static_assert(sizeof(prior)==160,"whole published profile");
 Reset();u16 result=Run();
 /* Same authored profile + same application episode: target/provenance must
  * still publish, but cannot start another identical alert/pause. */
 assert(!(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED);
 assert(evaluateCalls==1&&applyCalls==1&&healthCalls==1);
 assert(memcmp(&primitives,&runtime.resolution.primitives,sizeof(primitives))==0);
 assert((result>>8)==2);
 /* First entry/re-entry is a real authored reaction, even when composition
  * happens to yield the same bytes as the old numeric profile. */
 for(unsigned oldMask=0;oldMask<2;oldMask++){
  Reset();runtime.activeApplicationMasks[7]=oldMask;result=Run();
  assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);assert((result>>8)==3);
 }
 /* Clearing a claim does not necessarily clear active masks or the profile.
  * A new/unbound/replaced Interest must still get its authored first alert. */
 Reset();runtime.bindings[7].bindings[0].flags=0;result=Run();
 assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
 Reset();nextInterest.flags=0;result=Run();
 assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
 for(unsigned byte=0;byte<sizeof(nextInterest.target.actor);byte++){
  Reset();((u8 *)&nextInterest.target.actor)[byte]^=1;result=Run();
  assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
 }
 Reset();nextInterest.target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;result=Run();
 assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
 Reset();runtime.bindings[7].bindings[0].target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE;
 nextInterest=runtime.bindings[7].bindings[0];result=Run();
 assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
 Reset();runtime.bindings[7].bindings[0].target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
 nextInterest=runtime.bindings[7].bindings[0];result=Run();
 assert(!(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED));
 /* Every logical byte in either80-byte lane can carry a distinct authored
  * profile. Do not gate only the winning app, fingerprint or alert ID. */
 for(unsigned byte=0;byte<sizeof(prior);byte++){
  Reset();((u8 *)&runtime.resolution.profile)[byte]^=1;result=Run();
  assert(result&OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED);
  assert(memcmp(&prior,&runtime.resolution.profile,sizeof(prior))==0);
 }
 Reset();nextFlags=OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED|OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED;
 result=Run();assert((result&7)==nextFlags&&applyCalls==1&&healthCalls==1);
 Reset();nextFlags=0;result=Run();assert(!(result&7)&&applyCalls==0&&healthCalls==0);
 /* Warm reads cannot publish or own presentation. */
 Reset();result=OverworldWildSpawns_EvaluateConditionsForSlot(&state,&field,7,&prior,NULL,OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO);
 assert(!(result&7)&&applyCalls==0&&healthCalls==0&&evaluateCalls==1);
 Reset();mounted=1;assert(Run()==0&&evaluateCalls==0);
 for(unsigned absent=1;absent<=3;absent++){
  Reset();missing=absent;assert(Run()==OW_WILD_CONDITION_RESULT_FAIL_CLOSED);
  assert(evaluateCalls==0&&failedCalls==1&&applyCalls==0&&healthCalls==0);
 }
 Reset();status=OVERWORLD_BEHAVIOR_CONDITION_STALE_TARGET;
 assert(Run()==OW_WILD_CONDITION_RESULT_FAIL_CLOSED&&failedCalls==1&&applyCalls==0&&healthCalls==0);
 puts("exact Wild wrapper: identical profile target refresh without repeated alert; all160 distinct bytes/new episode/timed/warm/stale guards GREEN");
 return 0;
}
"""


def alert_publication_harness(source):
    spec = importlib.util.spec_from_file_location(
        "condition_alert_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py"
    )
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    return ALERT_PUBLICATION_PRELUDE + extract.production_function(
        source, "OverworldWildSpawns_EvaluateConditionsForSlot", "u16"
    ) + ALERT_PUBLICATION_DRIVER


def run_alert_publication_harness(source, output):
    from tools.overworld.test_throw_failure_composition import HOST_TYPES
    header = (ROOT / "include/overworld_behavior_condition_adapter.h").read_text()
    header = header[:header.index("typedef char OverworldBehaviorConditionAdapterEntrySizeMustRemain28Bytes[")]
    (output / "host-adapter.h").write_text(header + "\n#endif\n")
    (output / "host-types.h").write_text(HOST_TYPES + '\n#include <string.h>\n')
    unit, binary = output / "alert.c", output / "alert"
    unit.write_text(alert_publication_harness(source))
    command = [*shlex.split(os.environ.get("HOST_CC", "cc")),
        "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
        "-DOVERWORLD_BEHAVIOR_HOST", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
        "-include", str(output / "host-types.h"), "-I", str(output),
        "-I", str(ROOT / "include"), str(unit), "-o", str(binary)]
    compiled = subprocess.run(command, capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    return subprocess.run([str(binary)], capture_output=True, text=True)


class BehaviorConditionTests(unittest.TestCase):
    def test_target_publication_does_not_restart_an_identical_alert(self):
        source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        with tempfile.TemporaryDirectory(prefix="condition-alert-publication-") as directory:
            result = run_alert_publication_harness(source, Path(directory))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wild_controller_uses_the_idle_intent_boundary(self):
        source = (
            ROOT
            / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        boundary = source.index("            if (actorMotionOwnsFacing) {")
        cooldown = source.index("            if (cooldown > 1)", boundary)
        no_intent = source.index("            if (cooldown && !frameTick) continue;", cooldown)
        evaluation = source.index(
            "            if (OverworldWildSpawns_IssueIdleIntent(", no_intent
        )
        single = source.index("            if (MapObject_IsSingleMovementActive(object)) {", boundary)
        condition = source.index("OverworldWildSpawns_ResolveConditionsAtIntentBoundary(", single)
        marker = source.index("if (frameTick && (sOverworldWildFlags.intentConditionsCheckedMask", single)
        self.assertLess(single, marker)
        self.assertLess(marker, condition)
        self.assertLess(condition, cooldown)
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
            "sizeof(OverworldWildBehaviorConditionRuntime) == 2740",
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
        finished_start = re.search(
            r"static void __attribute__\(\(optimize\([^\n]+\)\)\) OverworldWildSpawns_HandleFinishedMovementCommand\(",
            source).start()
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
            / "lib/overworld/overworld_condition_moving_notice_native.c"
        ).read_text()
        evaluation_start = source.index(
            "OverworldBehaviorConditionAdapter_CollectWinningEntries("
        )
        evaluation_end = source.index(
            "OverworldBehaviorConditionStatus OverworldConditionNative_Run",
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
        for flag in ("OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED",
                     "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED",
                     "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED"):
            self.assertIn(flag, evaluation)
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
        self.assertIn("activeApplications = OverworldWildSpawns_GetActiveConditionApplications(state, slot);", boundary)
        self.assertIn("activeApplications == 0", boundary)

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
        reset = resume.index("OverworldWildSpawns_ClearWalkMovementState(")
        self.assertLess(evaluation, teleport)
        self.assertLess(evaluation, reset)

        # Pickup now starts from the resolved on-reach profile at the next
        # idle intent, after its own condition boundary has been checked.
        idle_start = source.index("OverworldWildSpawns_IssueIdleIntent(")
        idle_end = source.index("OverworldWildSpawns_TickMovementParams(", idle_start)
        idle = source[idle_start:idle_end]
        self.assertIn("OVERWORLD_TARGET_BINDING_CARGO, &cargo", idle)
        self.assertNotIn("conditions->result.resolvedTarget", idle)
        self.assertIn("target->kind != OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR", idle)
        self.assertNotIn("OverworldWildSpawns_ResolveConditionsAtIntentBoundary(", idle)
        tick_start = source.index("static void __attribute__((optimize(\"Os\", \"tree-forwprop\"))) OverworldWildSpawns_TickMovementParams(")
        tick_end = source.index("OverworldWildSpawns_UpdateSpawnerMovementCommand(LocalMapObject", tick_start)
        tick = source[tick_start:tick_end]
        self.assertLess(tick.index("OverworldWildSpawns_ResolveConditionsAtIntentBoundary("),
                        tick.index("OverworldWildSpawns_IssueIdleIntent("))

    def test_idle_pause_condition_boundary_semantics(self):
        with tempfile.TemporaryDirectory(prefix="condition-idle-boundary-") as directory:
            unit = Path(directory) / "idle.c"
            binary = Path(directory) / "idle"
            wild_source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
            unit.write_text(idle_boundary_harness(wild_source))
            command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                       "-Wall", "-Wextra", "-Werror", "-Wno-unused-variable",
                       "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include"),
                       str(unit), "-o", str(binary)]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            completed = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            mutants = {
                "missing terminal marker": ("sOverworldWildFlags.intentConditionsCheckedMask |= 1u << slot;", ""),
                "missing frame reset": ("sOverworldWildFlags.intentConditionsCheckedMask = 0;", ""),
                "eight-bit marker loses Fishing slots": ("u16 intentConditionsCheckedMask;", "u8 intentConditionsCheckedMask;"),
                "lost native SingleMovement guard": (
                    "if (MapObject_IsSingleMovementActive(object)) {\n                continue;\n            }\n            if (frameTick && (sOverworldWildFlags.intentConditionsCheckedMask",
                    "if (FALSE) {\n                continue;\n            }\n            if (frameTick && (sOverworldWildFlags.intentConditionsCheckedMask"),
                "expiry clears Routine pause": ("&& activeApplications != 0) {", ") {"),
            }
            for name, (old, new) in mutants.items():
                self.assertEqual(wild_source.count(old), 1, "mutation seam differs: " + name)
                unit.write_text(idle_boundary_harness(wild_source.replace(old, new)))
                compiled = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(compiled.returncode, 0, name + compiled.stdout + compiled.stderr)
                completed = subprocess.run([str(binary)], capture_output=True, text=True)
                self.assertNotEqual(completed.returncode, 0, "failed to reject: " + name)

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
                str(ROOT / "lib/overworld/overworld_target_bindings.c"),
                str(ROOT / "lib/overworld/overworld_pickup_route.c"),
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
