"""S1 regression for chain pause actions and look-around frame timing.

Bird profiles use a passive Pause: the chain has a move count and pause time,
but no visual action. This harness extracts the production reducer and Wild
adapter so None cannot silently become Pause again, or vice versa.
"""

from pathlib import Path
import importlib.util
import json
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def harness_source() -> str:
    extract = load_module(
        "passive_chain_extract",
        ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py",
    )
    runtime_body = extract.production_function(
        RUNTIME.read_text(), "OverworldActorWalkPolicy_ReduceChain", "void"
    )
    wild_body = extract.production_function(
        WILD.read_text(), "OverworldWildSpawns_ApplyUniversalChainMovementPause", "void"
    )
    look_body = extract.production_function(
        WILD.read_text(), "OverworldWildSpawns_GetLookAroundFrames", "u8"
    )
    return SUPPORT + runtime_body + "\n" + wild_body + "\n" + look_body + DRIVER


SUPPORT = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0

#define OVERWORLD_ACTOR_WALK_PENDING_NONE 0
#define OVERWORLD_ACTOR_WALK_PENDING_CHAIN 3
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT 4
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING 9
#define OVERWORLD_ACTOR_WALK_POLICY_IGNORED 0
#define OVERWORLD_ACTOR_WALK_POLICY_CONSUMED 1
#define OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED 0x08
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND 2
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS 3
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS 4
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE 6
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD 7
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 6
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_SPAWNER_SPOT_STATE_ACTIVE 2
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 3
#define OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(options) (((options) & 1) != 0)

typedef struct OverworldWildBehaviorProfileData {
    u8 chainPauseAction;
    u8 walkOptions;
    u8 ramAccelerationSteps;
    u8 chainMovementVariance;
    u8 chainPauseActionChance;
    u8 chainRepositionSpeed;
    u8 ramMaxSpeed;
    u8 chainPauseVariance;
    u8 chainRepositionJumpCount;
    u8 tilesBeforeTurnSkid;
} OverworldWildBehaviorProfileData;

typedef struct OverworldWildBehaviorProfile {
    OverworldWildBehaviorProfileData lane;
    OverworldWildBehaviorProfileData active;
    OverworldWildBehaviorProfileData tired;
} OverworldWildBehaviorProfile;

typedef struct OverworldWildBehaviorPrimitives {
    u8 chillLocomotion;
    u8 attentiveLocomotion;
    u8 tiredLocomotion;
} OverworldWildBehaviorPrimitives;

typedef struct OverworldWildWalkMomentumState { u8 turnDirection; } OverworldWildWalkMomentumState;
typedef struct OverworldActorPolicyState {
    OverworldWildWalkMomentumState walkMomentum;
    u8 chainStepsRemaining;
    u8 deferredChainPauseTicks;
    u8 deferredChainPauseAction;
    u8 variancePhase;
    u8 pendingStep;
} OverworldActorPolicyState;
typedef struct OverworldActorStateSnapshot { u32 commitSequence; } OverworldActorStateSnapshot;
typedef struct OverworldActorWalkPolicyCall {
    const OverworldWildBehaviorProfileData *lane;
    u8 actorSlot;
    u8 operation;
    u8 locomotion;
    u8 laneState;
    u8 flags;
    u8 decision;
    u8 chainAction;
    u8 chainTicks;
} OverworldActorWalkPolicyCall;
typedef struct OverworldWildSpawnState {
    u8 movementSpotStates[10];
    u8 movementCooldowns[10];
} OverworldWildSpawnState;

static OverworldActorPolicyState policy;
static OverworldActorStateSnapshot actor;
static OverworldActorWalkPolicyCall lastCall;
static unsigned deferredCalls;
static unsigned publishCalls;
static u32 gf_rand(void) { return 0; }
static BOOL OverworldActorWalkPolicy_PublishEffect(
    OverworldActorStateSnapshot *unusedActor, u32 unusedEffect, u32 unusedSequence)
{ (void)unusedActor; (void)unusedEffect; (void)unusedSequence; publishCalls++; return TRUE; }
static void OverworldActorWalkPolicy_ReduceChain(
    OverworldActorPolicyState *, OverworldActorStateSnapshot *,
    OverworldActorWalkPolicyCall *);
static BOOL ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING) {
        if ((policy.deferredChainPauseAction & 0x80) != 0) {
            call->chainAction = policy.deferredChainPauseAction & 0x7F;
            call->chainTicks = policy.deferredChainPauseTicks;
            policy.deferredChainPauseAction = 0;
            call->decision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
        }
        return TRUE;
    }
    OverworldActorWalkPolicy_ReduceChain(&policy, &actor, call);
    lastCall = *call;
    return TRUE;
}
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{ return ReduceWalk(call); }
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetBehaviorStateLane(
    const OverworldWildBehaviorProfile *profile, u8 spotState)
{
    return spotState == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE ? &profile->active
        : spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED ? &profile->tired
        : &profile->lane;
}
static u8 OverworldWildSpawns_GetCurrentMovementLocomotion(
    const OverworldWildBehaviorPrimitives *primitives, u8 spotState)
{
    return spotState == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE
        ? primitives->attentiveLocomotion
        : spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? primitives->tiredLocomotion : primitives->chillLocomotion;
}
static void OverworldWildSpawns_InitPolicyCall(
    OverworldActorWalkPolicyCall *call, int slot, int operation)
{
    memset(call, 0, sizeof(*call));
    call->actorSlot = (u8)slot;
    call->operation = (u8)operation;
}
static void OverworldWildSpawns_CommitDeferredChainMovementPause(
    OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile)
{ (void)state; (void)slot; (void)profile; deferredCalls++; }
static u8 OverworldWildSpawns_GetLookAroundFrames(u8 pauseTicks);
"""


DRIVER = r"""
static void Reset(void)
{
    memset(&policy, 0, sizeof(policy));
    memset(&actor, 0, sizeof(actor));
    memset(&lastCall, 0, sizeof(lastCall));
    deferredCalls = 0;
    publishCalls = 0;
    policy.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_CHAIN;
}

int main(void)
{
    OverworldWildSpawnState state = {0};
    OverworldWildBehaviorProfile profile = {0};
    OverworldWildBehaviorPrimitives primitives = {0};
    primitives.chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_HOP;

    Reset();
    profile.lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE;
    profile.lane.ramAccelerationSteps = 1;
    profile.lane.ramMaxSpeed = 30;
    profile.lane.chainMovementVariance = 2;
    profile.lane.chainPauseVariance = 20;
    profile.lane.chainPauseActionChance = 100;
    OverworldWildSpawns_ApplyUniversalChainMovementPause(
        &state, 0, &profile, &primitives);
    if (lastCall.decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED
        || lastCall.chainTicks != 0
        || state.movementCooldowns[0] != 0
        || policy.chainStepsRemaining != 0
        || policy.deferredChainPauseAction != 0
        || deferredCalls != 0
        || publishCalls != 0) {
        fprintf(stderr,
            "None did not skip the pause: decision=%u action=%u ticks=%u cooldown=%u remaining=%u deferred=%u calls=%u\n",
            lastCall.decision, lastCall.chainAction, lastCall.chainTicks,
            state.movementCooldowns[0], policy.chainStepsRemaining,
            policy.deferredChainPauseAction, deferredCalls);
        return 1;
    }

    Reset();
    memset(&state, 0, sizeof(state));
    memset(&profile, 0, sizeof(profile));
    profile.lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE;
    profile.lane.ramAccelerationSteps = 1;
    profile.lane.ramMaxSpeed = 30;
    profile.lane.chainMovementVariance = 2;
    profile.lane.chainPauseVariance = 20;
    profile.lane.chainPauseActionChance = 1;
    OverworldWildSpawns_ApplyUniversalChainMovementPause(
        &state, 0, &profile, &primitives);
    if (lastCall.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
        || lastCall.chainAction != OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE
        || lastCall.chainTicks != 24
        || state.movementCooldowns[0] != 24
        || policy.chainStepsRemaining != 0
        || policy.deferredChainPauseAction != 0
        || deferredCalls != 0
        || publishCalls != 1) {
        fprintf(stderr,
            "passive Pause was lost: decision=%u action=%u ticks=%u cooldown=%u remaining=%u deferred=%u calls=%u\n",
            lastCall.decision, lastCall.chainAction, lastCall.chainTicks,
            state.movementCooldowns[0], policy.chainStepsRemaining,
            policy.deferredChainPauseAction, deferredCalls);
        return 2;
    }

    Reset();
    memset(&state, 0, sizeof(state));
    memset(&profile, 0, sizeof(profile));
    primitives.chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    profile.lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE;
    profile.lane.walkOptions = 1;
    profile.lane.ramAccelerationSteps = 1;
    profile.lane.ramMaxSpeed = 8;
    profile.lane.chainPauseActionChance = 100;
    profile.lane.tilesBeforeTurnSkid = 0x80;
    OverworldWildSpawns_ApplyUniversalChainMovementPause(
        &state, 0, &profile, &primitives);
    if (lastCall.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
        || lastCall.chainAction != OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE
        || lastCall.chainTicks != 4
        || state.movementCooldowns[0] != 4
        || policy.deferredChainPauseAction != 0
        || policy.deferredChainPauseTicks != 4
        || deferredCalls != 0
        || publishCalls != 1) {
        fprintf(stderr,
            "walk chain Pause did not stay a plain pause: action=%u ticks=%u cooldown=%u pending=%u pendingTicks=%u\n",
            lastCall.chainAction, lastCall.chainTicks,
            state.movementCooldowns[0], policy.deferredChainPauseAction,
            policy.deferredChainPauseTicks);
        return 3;
    }

    Reset();
    memset(&state, 0, sizeof(state));
    memset(&profile, 0, sizeof(profile));
    primitives.chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
    profile.lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND;
    profile.lane.ramAccelerationSteps = 1;
    profile.lane.ramMaxSpeed = 30;
    profile.lane.chainPauseActionChance = 100;
    OverworldWildSpawns_ApplyUniversalChainMovementPause(
        &state, 0, &profile, &primitives);
    if (lastCall.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
        || lastCall.chainAction != OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND
        || lastCall.chainTicks != 15
        || policy.deferredChainPauseAction != 0x82
        || deferredCalls != 1
        || publishCalls != 1) {
        fprintf(stderr, "visual chain control failed\n");
        return 4;
    }
    if (OverworldWildSpawns_GetLookAroundFrames(0) != 3
        || OverworldWildSpawns_GetLookAroundFrames(1) != 3
        || OverworldWildSpawns_GetLookAroundFrames(15) != 30
        || OverworldWildSpawns_GetLookAroundFrames(30) != 60
        || OverworldWildSpawns_GetLookAroundFrames(128) != 255) {
        fprintf(stderr, "look-around chain ticks were not converted to field frames\n");
        return 5;
    }

    Reset();
    memset(&state, 0, sizeof(state));
    memset(&profile, 0, sizeof(profile));
    primitives.chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
    profile.lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD;
    profile.lane.walkOptions = 1;
    profile.lane.ramAccelerationSteps = 1;
    profile.lane.ramMaxSpeed = 30;
    profile.lane.chainPauseVariance = 20;
    profile.lane.chainPauseActionChance = 100;
    OverworldWildSpawns_ApplyUniversalChainMovementPause(
        &state, 0, &profile, &primitives);
    if (lastCall.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
        || lastCall.chainAction != OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD
        || lastCall.chainTicks != 0
        || state.movementCooldowns[0] != 0
        || policy.deferredChainPauseAction != 0x87
        || policy.deferredChainPauseTicks != 0
        || deferredCalls != 1
        || publishCalls != 1) {
        fprintf(stderr,
            "forward Hop boundary changed: decision=%u action=%u ticks=%u cooldown=%u pending=%u pendingTicks=%u calls=%u\n",
            lastCall.decision, lastCall.chainAction, lastCall.chainTicks,
            state.movementCooldowns[0], policy.deferredChainPauseAction,
            policy.deferredChainPauseTicks, deferredCalls);
        return 6;
    }
    puts("None, passive Pause, look-around, and forward-Hop boundary cases passed");
    return 0;
}
"""


class PassiveChainPauseTests(unittest.TestCase):
    def test_passive_profiles_select_pause_explicitly(self):
        header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        self.assertIn(
            "#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5",
            header,
        )
        self.assertIn(
            "#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE 6",
            header,
        )
        self.assertIn(
            "#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD 7",
            header,
        )
        catalog = json.loads(
            (ROOT / "data/overworld_behavior_profiles.json").read_text()
        )
        profiles = {
            profile["id"]: profile["fields"]
            for profile in catalog["profiles"]
        }
        classes = {
            binding["symbol"]: profiles[binding["profile"]]
            for binding in catalog["runtimeBindings"]["classOrder"]
        }
        overrides = {
            profile["name"]: profile["fields"]
            for profile in catalog["profiles"]
        }
        self.assertEqual(
            classes["OW_WILD_BEHAVIOR_CLASS_DEFAULT"]["chainPauseAction"]["value"],
            "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE",
        )
        for symbol in (
            "OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE",
            "OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM",
        ):
            self.assertEqual(
                classes[symbol]["chainPauseAction"]["value"],
                "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE",
            )
        for name in ("Bird",):
            self.assertEqual(
                overrides[name]["chainPauseAction"]["value"],
                "OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE",
            )

    def test_none_and_pause_have_distinct_semantics(self):
        with tempfile.TemporaryDirectory(prefix="ow-passive-chain-") as directory:
            source = Path(directory) / "passive_chain.c"
            binary = Path(directory) / "passive_chain"
            source.write_text(harness_source())
            compile_result = subprocess.run(
                ["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run(
                [str(binary)], cwd=ROOT, text=True, capture_output=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
