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
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
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
        == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(!entry.active);
    world.actors[0].actor = Handle(1, 2);

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
    assert(!states[0].active && !states[0].hasTriggered);

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
    OverworldBehaviorConditionPreparedActor prepared;
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    OverworldBehaviorConditionWorldView world = {0};
    OverworldBehaviorConditionCandidate candidates[2] = {0};
    OverworldWildBehaviorContext subjectContext = {0};
    OverworldWildBehaviorConditionEntry *entry;

    assert(blob != NULL);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    assert(blob->header.overrideProfileCount > 2);
    blob->header.conditionEntryCount = 2;

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
    assert(scratch.entryResults[0].conditionTrue);
    assert(scratch.entryResults[1].conditionTrue);

    /* A reused candidate slot invalidates the captured complete actor handle. */
    world.actors[0].actor = Handle(1, 9);
    assert(OverworldBehaviorCondition_EvaluatePrepared(
        blob, sizeof(*blob), &prepared, &world, candidates, 2, world.frame + 1,
        &scratch, &result) == OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(result.targets[1].kind == OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE);
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
