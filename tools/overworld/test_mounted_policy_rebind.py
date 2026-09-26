"""Host control for the Wild policy bind used during mounted map rebind."""

from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def source_function(source: str, name: str) -> str:
    match = re.search(
        r"\b" + re.escape(name) + r"\s*\([^;{}]*\)\s*\{",
        source,
    )
    if match is None:
        raise ValueError(name + " definition is missing")
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return "static void " + source[match.start() : end + 1]
    raise ValueError(name + " definition is incomplete")


def bind_function(source: str) -> str:
    return source_function(source, "OverworldWildSpawns_BindActorPolicyProfile")


PRELUDE = r"""
#include <stdint.h>

typedef uint32_t u32;
typedef int BOOL;
#define OW_WILD_FOLLOWER_SLOT 7
#define OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE 1

typedef struct OverworldActorPolicyProfileBinding {
    u32 behaviorFingerprint;
    u32 matchedLayerMask;
} OverworldActorPolicyProfileBinding;

typedef struct OverworldActorWalkPolicyCall {
    int actorSlot;
    int operation;
    OverworldActorPolicyProfileBinding *profileBinding;
} OverworldActorWalkPolicyCall;

static int mount_active;
static int bind_count;
static int bound_slot;
static OverworldActorPolicyProfileBinding bound;

static BOOL OverworldWildSpawns_MountIsActive(void)
{
    return mount_active;
}

static void OverworldWildSpawns_InitPolicyCall(
    OverworldActorWalkPolicyCall *call, int slot, int operation)
{
    call->actorSlot = slot;
    call->operation = operation;
    call->profileBinding = 0;
}

static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    if (call->operation != OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE
        || call->profileBinding == 0) {
        return 0;
    }
    bind_count++;
    bound_slot = call->actorSlot;
    bound = *call->profileBinding;
    return 1;
}
"""


DRIVER = r"""
int main(void)
{
    mount_active = 1;
    bound.behaviorFingerprint = 0x11111111;
    bound.matchedLayerMask = 1u << 28;

    /* Wild REBIND may prepare a Follower cache but cannot replace Mounted. */
    OverworldWildSpawns_BindActorPolicyProfile(
        OW_WILD_FOLLOWER_SLOT, 0x22222222, 1u << 27);
    if (bind_count != 0 || bound.behaviorFingerprint != 0x11111111
        || bound.matchedLayerMask != (1u << 28)) return 1;

    /* The guard must not suppress ordinary Wild policy binds. */
    OverworldWildSpawns_BindActorPolicyProfile(0, 0x33333333, 3);
    if (bind_count != 1 || bound_slot != 0
        || bound.behaviorFingerprint != 0x33333333
        || bound.matchedLayerMask != 3) return 2;

    /* After dismount, normal Follower rebind is allowed again. */
    mount_active = 0;
    OverworldWildSpawns_BindActorPolicyProfile(
        OW_WILD_FOLLOWER_SLOT, 0x22222222, 1u << 27);
    if (bind_count != 2 || bound_slot != OW_WILD_FOLLOWER_SLOT
        || bound.behaviorFingerprint != 0x22222222
        || bound.matchedLayerMask != (1u << 27)) return 3;
    return 0;
}
"""


def run_control(function: str) -> int:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        source_path = path / "policy_rebind.c"
        program_path = path / "policy_rebind"
        source_path.write_text(PRELUDE + function + DRIVER)
        subprocess.run(
            ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
             "-o", str(program_path), str(source_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return subprocess.run([str(program_path)], check=False).returncode


class MountedPolicyRebindTests(unittest.TestCase):
    def test_mounted_cache_cannot_hide_later_follower_rebind(self) -> None:
        source = SOURCE.read_text()
        start = source.index("OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(")
        end = source.index("OverworldWildSpawns_BeginMountSelectedFollower(", start)
        getter = source[start:end]
        self.assertRegex(
            getter,
            r"if \(cache != NULL\s*"
            r"&& \(slot != OW_WILD_FOLLOWER_SLOT\s*"
            r"\|\| !OverworldWildSpawns_MountIsActive\(\)\)\)\s*\{\s*"
            r"OverworldWildSpawns_StoreBehaviorSlotCache\(",
        )
        # A mounted cache entry would skip the post-dismount policy bind.
        self.assertEqual(getter.count("OverworldWildSpawns_StoreBehaviorSlotCache("), 1)

    def test_mounted_guard_and_follower_control(self) -> None:
        function = bind_function(SOURCE.read_text())
        self.assertEqual(run_control(function), 0)

    def test_negative_control_rejects_follower_bind_during_mount(self) -> None:
        function = bind_function(SOURCE.read_text())
        unguarded, count = re.subn(
            r"if\s*\(slot\s*==\s*OW_WILD_FOLLOWER_SLOT\s*"
            r"&&\s*OverworldWildSpawns_MountIsActive\(\)\)\s*\{\s*return;\s*\}",
            "",
            function,
            count=1,
        )
        self.assertEqual(count, 1)
        self.assertEqual(run_control(unguarded), 1)


if __name__ == "__main__":
    unittest.main()
