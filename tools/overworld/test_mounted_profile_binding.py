"""Host checks for one coherent Mounted profile-binding transaction."""

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPAWNS_SOURCE = (
    ROOT
    / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)
MOUNT_SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


HARNESS = r"""
#include <assert.h>
#include <string.h>

#include "constants/species.h"
#include "overworld_behavior_resolver.h"

extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static BehaviorResolveRequest SprintRequest(void)
{
    BehaviorResolveRequest request;

    memset(&request, 0, sizeof(request));
    request.context.species = SPECIES_STANTLER;
    request.context.level = 20;
    request.context.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    request.context.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    request.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    request.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    request.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    return request;
}

static void Resolve(
    const BehaviorResolveRequest *request,
    BehaviorResolveResult *result)
{
    assert(BehaviorResolver_Resolve(
        &gOverworldWildBehaviorDataBlob,
        sizeof(gOverworldWildBehaviorDataBlob),
        request,
        result,
        NULL) == BEHAVIOR_RESOLVE_OK);
    assert(result->fingerprint != 0);
}

int main(void)
{
    const OverworldWildBehaviorDataBlob *blob =
        &gOverworldWildBehaviorDataBlob;
    const u32 followerBit =
        1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER;
    const u32 mountedBit =
        1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED;
    const OverworldWildBehaviorOverrideProfile *followerProfile =
        &blob->overrideProfiles[OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER];
    const OverworldWildBehaviorOverrideProfile *mountedProfile =
        &blob->overrideProfiles[OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED];
    BehaviorResolveRequest request = SprintRequest();
    BehaviorResolveRequest conditionalRequest;
    BehaviorResolveResult normal;
    BehaviorResolveResult mounted;
    BehaviorResolveResult followerMounted;
    BehaviorResolveResult conditional;
    BehaviorResolveResult conditionalMounted;
    u8 conditionalApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    u16 i;

    Resolve(&request, &normal);
    request.forcedOverrideMask = mountedBit;
    Resolve(&request, &mounted);
    request.forcedOverrideMask = followerBit | mountedBit;
    Resolve(&request, &followerMounted);

    /* Mounted is its own receipt, but its empty body keeps the selected
     * Pokemon's complete normal profile and primitives. */
    assert(memcmp(&mounted.profile, &normal.profile, sizeof(normal.profile)) == 0);
    assert(memcmp(
        &mounted.primitives,
        &normal.primitives,
        sizeof(normal.primitives)) == 0);
    assert(mounted.fingerprint != normal.fingerprint);
    assert(mounted.forcedOverrideMask == mountedBit);
    assert((mounted.appliedOverrideMask & mountedBit) != 0);
    assert((mounted.appliedOverrideMask & followerBit) == 0);

    /* These are the eight Follower-owned fields. Even when Sprint happens
     * to share a numeric value, Mounted must not claim Follower provenance. */
    assert(mounted.profile.owner.chillState == normal.profile.owner.chillState);
    assert(mounted.profile.owner.chillSpeed == normal.profile.owner.chillSpeed);
    assert(mounted.profile.owner.spawnState == normal.profile.owner.spawnState);
    assert(mounted.profile.owner.chillTarget == normal.profile.owner.chillTarget);
    assert(mounted.profile.owner.spawnDestination
        == normal.profile.owner.spawnDestination);
    assert(mounted.profile.owner.chillAllowedTerrainMask
        == normal.profile.owner.chillAllowedTerrainMask);
    assert(mounted.profile.owner.chillAllowedTerrainOverrideMask
        == normal.profile.owner.chillAllowedTerrainOverrideMask);
    assert(mounted.profile.owner.walkPause == normal.profile.owner.walkPause);
    assert(followerProfile->mask ==
        (OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE
            | OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED
            | OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE
            | OW_WILD_BEHAVIOR_OVERRIDE_CHILL_TARGET
            | OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION));
    assert(followerProfile->mask2 ==
        (OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK));
    assert(followerProfile->mask3 ==
        OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE);
    assert(mountedProfile->mask == 0
        && mountedProfile->mask2 == 0
        && mountedProfile->mask3 == 0);
    assert((followerMounted.appliedOverrideMask & followerBit) != 0);
    assert(memcmp(
        &followerMounted.profile,
        &normal.profile,
        sizeof(normal.profile)) != 0);
    assert(followerMounted.profile.owner.chillState
        != normal.profile.owner.chillState);
    assert(followerMounted.profile.owner.chillTarget
        != normal.profile.owner.chillTarget);
    assert(followerMounted.profile.owner.spawnDestination
        != normal.profile.owner.spawnDestination);

    /* A live conditional admission composes with the same normal Owner plus
     * Mounted request. Mounted changes only receipt provenance. */
    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        if (blob->overrideProfiles[i].profileKind
                == OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL
            && blob->overrideProfiles[i].conditionCount != 0) {
            conditionalApplication = (u8)i;
            break;
        }
    }
    assert(conditionalApplication != BEHAVIOR_RESOLVER_NO_APPLICATION);
    conditionalRequest = SprintRequest();
    conditionalRequest.activeConditionalMask =
        1u << conditionalApplication;
    conditionalRequest.winningConditionId =
        blob->conditionEntries[
            blob->overrideProfiles[conditionalApplication].conditionStart]
            .conditionId;
    Resolve(&conditionalRequest, &conditional);
    conditionalRequest.forcedOverrideMask = mountedBit;
    Resolve(&conditionalRequest, &conditionalMounted);
    assert(memcmp(
        &conditionalMounted.profile,
        &conditional.profile,
        sizeof(conditional.profile)) == 0);
    assert(memcmp(
        &conditionalMounted.primitives,
        &conditional.primitives,
        sizeof(conditional.primitives)) == 0);
    assert(conditionalMounted.conditionalOverrideMask
        == conditionalRequest.activeConditionalMask);
    assert(conditionalMounted.winningConditionId
        == conditionalRequest.winningConditionId);
    assert(conditionalMounted.fingerprint != conditional.fingerprint);
    return 0;
}
"""


def function_body(source: str, name: str) -> str:
    marker = -1
    opening = -1
    while True:
        marker = source.index(name + "(", marker + 1)
        candidate_opening = source.index("{", marker)
        candidate_semicolon = source.find(";", marker, candidate_opening)
        if candidate_semicolon == -1:
            opening = candidate_opening
            break
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise AssertionError(f"unterminated function: {name}")


class MountedProfileBindingTests(unittest.TestCase):
    def test_normal_sprint_and_live_condition_inheritance(self) -> None:
        compiler_setting = os.environ.get("CC")
        compiler = shlex.split(compiler_setting) if compiler_setting else []
        if not compiler:
            default_compiler = shutil.which("cc")
            compiler = [default_compiler] if default_compiler else []
        self.assertTrue(compiler, "a host C compiler is required")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mounted_profile_binding.c"
            executable = Path(directory) / "mounted_profile_binding"
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

    def test_bridge_uses_one_truthful_result_and_commits_last(self) -> None:
        source = SPAWNS_SOURCE.read_text(encoding="utf-8")
        resolver = function_body(
            source, "OverworldWildSpawns_ResolveBehaviorProfileForContext"
        )
        begin = function_body(
            source, "OverworldWildSpawns_BeginMountSelectedFollower"
        )

        self.assertEqual(
            begin.count("OverworldWildSpawns_ResolveBehaviorProfileForContext("),
            1,
        )
        resolve_call_start = begin.index(
            "OverworldWildSpawns_ResolveBehaviorProfileForContext("
        )
        resolve_call_end = begin.index("&resolution);", resolve_call_start)
        resolve_call = begin[resolve_call_start:resolve_call_end]
        self.assertIn(
            "1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED", resolve_call
        )
        self.assertNotIn(
            "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER", resolve_call
        )
        self.assertNotIn(
            "OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(",
            begin,
        )
        self.assertIn(
            "behaviorData == NULL || resolution.fingerprint == 0", begin
        )
        self.assertIn(
            "role.policyTransaction.next.behaviorFingerprint = "
            "resolution.fingerprint",
            begin,
        )
        self.assertIn(
            "resolution.matchedClassRuleMask\n        "
            "| resolution.appliedOverrideMask",
            begin,
        )
        self.assertIn("&resolution.profile", begin)

        resolve_at = resolve_call_start
        mount_begin_at = begin.index("OVERWORLD_MOUNT_OVERLAY_ENTRY->begin(")
        reset_at = begin.index("OverworldWildSpawns_ResetSlotMovementCommand(")
        self.assertLess(resolve_at, mount_begin_at)
        self.assertLess(mount_begin_at, reset_at)
        failed_begin = begin[mount_begin_at:reset_at]
        self.assertIn("return FALSE;", failed_begin)

        self.assertIn(
            "conditions->request.activeConditionalMask", begin
        )
        self.assertIn(
            "conditions->request.forcedOverrideMask", begin
        )
        self.assertIn("&conditions->request.context", begin)
        self.assertIn("conditionalAdmission = &conditions->request", begin)
        for field in (
            "activeConditionalMask",
            "resolvedTarget",
            "winningConditionId",
            "targetSourceApplication",
            "resolvedTargetConditionId",
        ):
            self.assertIn(
                f"conditionalAdmission->{field}", resolver
            )
        self.assertNotIn(
            "request.forcedOverrideMask = "
            "conditionalAdmission->forcedOverrideMask",
            resolver,
        )

    def test_swap_failure_and_detach_keep_follower_policy_safe(self) -> None:
        source = MOUNT_SOURCE.read_text(encoding="utf-8")
        begin = function_body(source, "OverworldMount_Begin")
        cancel = function_body(source, "OverworldMount_Cancel")

        swap_at = begin.index("OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE")
        failure_at = begin.index("return FALSE;", swap_at)
        publish_at = begin.index("memset(&sOverworldMountState", swap_at)
        self.assertLess(swap_at, failure_at)
        self.assertLess(failure_at, publish_at)
        self.assertIn(
            "policyTransaction->prior.behaviorFingerprint", begin
        )
        self.assertIn(
            "policyTransaction->prior.matchedLayerMask", begin
        )
        self.assertIn("OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE", cancel)
        self.assertIn(
            "&sOverworldMountState.priorFollowerBehaviorFingerprint", cancel
        )


if __name__ == "__main__":
    unittest.main()
