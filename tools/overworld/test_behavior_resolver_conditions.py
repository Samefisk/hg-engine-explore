"""Host proof for explicit conditional-profile resolver composition."""

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
#include <stdlib.h>
#include <string.h>

#include "overworld_behavior_resolver.h"

extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static void ClearApplication(OverworldWildBehaviorOverrideProfile *profile)
{
    memset(profile, 0, sizeof(*profile));
    profile->targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED;
    profile->profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL;
}

static void SetSpeed(
    OverworldWildBehaviorOverrideProfile *profile,
    u8 speed)
{
    profile->mask = OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED;
    profile->profile.chillSpeed = speed;
}

static BehaviorResolveRequest ExplicitRequest(u32 activeMask)
{
    BehaviorResolveRequest request;

    memset(&request, 0, sizeof(request));
    request.context.level = 5;
    request.context.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    request.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    request.activeConditionalMask = activeMask;
    request.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    request.conditionInputMode = BEHAVIOR_RESOLVE_CONDITIONS_EXPLICIT;
    return request;
}

static void SetPlayerTarget(
    BehaviorResolveRequest *request,
    u8 application,
    u16 conditionId)
{
    request->resolvedTarget.kind = BEHAVIOR_RESOLVE_TARGET_PLAYER;
    request->targetSourceApplication = application;
    request->resolvedTargetConditionId = conditionId;
}

static void SetActorTarget(
    BehaviorResolveRequest *request,
    u8 application,
    u16 conditionId)
{
    request->resolvedTarget.kind = BEHAVIOR_RESOLVE_TARGET_ACTOR;
    request->resolvedTarget.actorSlot = 4;
    request->resolvedTarget.actorGeneration = 8;
    request->resolvedTarget.fieldEpoch = 12;
    request->resolvedTarget.mapGeneration = 16;
    request->resolvedTarget.encounterGeneration = 20;
    request->targetSourceApplication = application;
    request->resolvedTargetConditionId = conditionId;
}

static void Resolve(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request,
    BehaviorResolveResult *result,
    BehaviorResolutionTrace *trace)
{
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), request, result, trace) == BEHAVIOR_RESOLVE_OK);
}

int main(void)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    BehaviorResolutionStep steps[96];
    BehaviorResolutionTrace trace = {steps, 96, 0, 0, 0};
    BehaviorResolveRequest request;
    BehaviorResolveResult first;
    BehaviorResolveResult second;
    u16 i;

    assert(blob != NULL);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    assert(blob->header.overrideProfileCount >= 4);
    assert(blob->header.conditionEntryCount >= 2);
    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        ClearApplication(&blob->overrideProfiles[i]);
    }

    /* normal, conditional, conditional, normal */
    blob->overrideProfiles[0].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    SetSpeed(&blob->overrideProfiles[0], 10);

    blob->overrideProfiles[1].profileKind =
        OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[1].conditionStart = 0;
    blob->overrideProfiles[1].conditionCount = 1;
    SetSpeed(&blob->overrideProfiles[1], 20);
    blob->overrideProfiles[1].mask |= OW_WILD_BEHAVIOR_OVERRIDE_STAMINA;
    blob->overrideProfiles[1].profile.stamina = 41;

    blob->overrideProfiles[2].profileKind =
        OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[2].conditionStart = 1;
    blob->overrideProfiles[2].conditionCount = 1;
    SetSpeed(&blob->overrideProfiles[2], 25);
    blob->overrideProfiles[2].mask |= OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME;
    blob->overrideProfiles[2].profile.restTime = 42;

    blob->overrideProfiles[3].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    SetSpeed(&blob->overrideProfiles[3], 30);

    blob->conditionEntries[0].applicationIndex = 1;
    blob->conditionEntries[0].conditionId = 101;
    blob->conditionEntries[0].targetKind =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    blob->conditionEntries[1].applicationIndex = 2;
    blob->conditionEntries[1].conditionId = 102;
    blob->conditionEntries[1].targetKind =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR;

    request = ExplicitRequest(0);
    Resolve(blob, &request, &first, NULL);
    assert(first.profile.owner.chillSpeed == 30);
    assert(first.profile.owner.stamina != 41);
    assert(first.conditionalOverrideMask == 0);

    request = ExplicitRequest(1u << 1);
    request.winningConditionId = 101;
    Resolve(blob, &request, &first, &trace);
    /* This is 30 only when application 3 runs after conditional app 1. */
    assert(first.profile.owner.chillSpeed == 30);
    assert(first.profile.owner.stamina == 41);
    assert(first.conditionalOverrideMask == (1u << 1));
    assert(trace.steps[1].sourceIndex == 0);
    assert(trace.steps[2].sourceIndex == 1);
    assert(trace.steps[3].sourceIndex == 3);

    /* Without the trailing normal write, later conditional app 2 wins. */
    blob->overrideProfiles[3].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED;
    request = ExplicitRequest((1u << 1) | (1u << 2));
    request.winningConditionId = 102;
    SetActorTarget(&request, 2, 102);
    Resolve(blob, &request, &first, NULL);
    Resolve(blob, &request, &second, NULL);
    assert(first.profile.owner.chillSpeed == 25);
    assert(first.profile.owner.stamina == 41);
    assert(first.profile.owner.restTime == 42);
    assert(first.resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_ACTOR);
    assert(first.resolvedTarget.actorSlot == 4);
    assert(first.targetSourceApplication == 2);
    assert(first.winningConditionId == 102);
    assert(first.resolvedTargetConditionId == 102);
    assert(first.fingerprint == second.fingerprint);

    /* A later targetless condition changes fields but preserves app 1 target. */
    blob->conditionEntries[1].targetKind =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_NONE;
    request = ExplicitRequest((1u << 1) | (1u << 2));
    request.winningConditionId = 102;
    SetPlayerTarget(&request, 1, 101);
    Resolve(blob, &request, &second, NULL);
    assert(second.profile.owner.chillSpeed == 25);
    assert(second.resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_PLAYER);
    assert(second.targetSourceApplication == 1);
    assert(second.winningConditionId == 102);
    assert(second.resolvedTargetConditionId == 101);
    assert(first.fingerprint != second.fingerprint);

    /* Active bits cannot name normal applications or mismatched targets. */
    request = ExplicitRequest(1u << 0);
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);
    request = ExplicitRequest(1u << 1);
    request.winningConditionId = 101;
    SetActorTarget(&request, 1, 101);
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);

    free(blob);
    return 0;
}
"""


class BehaviorResolverConditionTests(unittest.TestCase):
    def test_explicit_condition_order_targets_and_fingerprint(self) -> None:
        compiler_setting = os.environ.get("CC")
        compiler = shlex.split(compiler_setting) if compiler_setting else []
        if not compiler:
            default_compiler = shutil.which("cc")
            compiler = [default_compiler] if default_compiler else []
        self.assertTrue(compiler, "a host C compiler is required")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "resolver_conditions.c"
            executable = Path(directory) / "resolver_conditions"
            source.write_text(HARNESS, encoding="utf-8")
            command = compiler + [
                "-std=c99",
                "-O2",
                "-Wall",
                "-Wextra",
                "-DOVERWORLD_BEHAVIOR_HOST",
                "-I",
                str(ROOT / "include"),
                "-I",
                str(ROOT / "data"),
                str(ROOT / "lib/overworld/overworld_behavior_resolver.c"),
                str(ROOT / "data/OverworldWildBehaviorData.c"),
                str(source),
                "-o",
                str(executable),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )
            completed = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )


if __name__ == "__main__":
    unittest.main()
