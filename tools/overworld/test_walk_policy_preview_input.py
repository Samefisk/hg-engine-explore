#!/usr/bin/env python3
"""Host check that Walk preview returns a skid without changing live state."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
ACTOR_SYSTEM = ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"


def preview_branch() -> str:
    source = RUNTIME.read_text()
    start = source.index(
        "if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT)")
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("preview branch is incomplete")


def actor_reduce_walk() -> str:
    source = ACTOR_SYSTEM.read_text()
    start = source.index("static BOOL ActorSystem_ReduceWalk(")
    end = source.index("\nBOOL __attribute__", start)
    return source[start:end]


def harness() -> str:
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT 16
#define OVERWORLD_ACTOR_WALK_POLICY_INPUT 1
#define OVERWORLD_ACTOR_WALK_POLICY_IGNORED 0
#define OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP 2
#define OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL 1
#define OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED 2
#define OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX 3
#define OVERWORLD_ACTOR_WORLD_EFFECT_NONE 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE 0
#define OVERWORLD_ACTOR_WALK_STEP_SKID 2
typedef struct OverworldActorPolicyState {
    u8 momentum[32];
    u8 pendingStep;
    u8 bufferedDirection;
} OverworldActorPolicyState;
typedef struct OverworldActorWalkPolicyCall {
    u8 operation, decision, effect, chainAction, stepFlags, actorSlot;
    u8 reserved[4];
    const void *lane;
} OverworldActorWalkPolicyCall;
typedef struct OverworldActorStateSnapshot { u8 active, sentinel; }
    OverworldActorStateSnapshot;
static unsigned reduceCalls;
static const OverworldActorPolicyState *livePolicy;
static unsigned displayedTimeCalls, randomCalls;
static void OverworldActorWalkPolicy_ReduceInput(
    OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call) {
    ++reduceCalls;
    if (policy == livePolicy) reduceCalls += 100;
    memset(policy->momentum, 0xA5, sizeof(policy->momentum));
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL;
    call->decision = OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP;
    call->stepFlags |= OVERWORLD_ACTOR_WALK_STEP_SKID;
}
static BOOL OverworldActorWalkPolicy_Reduce(
    OverworldActorPolicyState *policy, OverworldActorStateSnapshot *actor,
    OverworldActorWalkPolicyCall *call) {
''' + preview_branch() + r'''
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_INPUT) {
        call->decision = OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
        call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_NONE;
        call->chainAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE;
        OverworldActorWalkPolicy_ReduceInput(policy, call);
        return TRUE;
    }
    (void)actor;
    return FALSE;
}
typedef struct OverworldActorRuntimeSlot {
    OverworldActorPolicyState policy;
    OverworldActorStateSnapshot snapshot;
} OverworldActorRuntimeSlot;
#define OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS 1
static struct { OverworldActorRuntimeSlot slots[1]; }
    gOverworldActorSystemState;
static struct {
    BOOL (*reduceWalk)(OverworldActorPolicyState *,
        OverworldActorStateSnapshot *, OverworldActorWalkPolicyCall *);
} walkOwner = { OverworldActorWalkPolicy_Reduce };
#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY (&walkOwner)
#define OVERWORLD_WALK_SELECT_DISPLAYED_TIME(call, actor, policy) do { \
    ++displayedTimeCalls; ++randomCalls; \
    (void)(call); (void)(actor); (void)(policy); \
} while (0)
''' + actor_reduce_walk() + r'''
int main(void) {
    OverworldActorRuntimeSlot *slot = &gOverworldActorSystemState.slots[0];
    OverworldActorPolicyState *policy = &slot->policy, prior;
    OverworldActorStateSnapshot *actor = &slot->snapshot, priorActor;
    OverworldActorWalkPolicyCall call;
    int lane = 1;
    memset(policy, 0x5A, sizeof(*policy));
    actor->active = 1;
    actor->sentinel = 0xA5;
    policy->pendingStep = 0;
    prior = *policy;
    priorActor = *actor;
    livePolicy = policy;
    memset(&call, 0, sizeof(call));
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT;
    call.lane = &lane;
    if (!ActorSystem_ReduceWalk(&call)
        || memcmp(policy, &prior, sizeof(*policy)) != 0
        || memcmp(actor, &priorActor, sizeof(*actor)) != 0
        || reduceCalls != 1
        || displayedTimeCalls != 0 || randomCalls != 0
        || call.operation != OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT
        || call.decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
        || !(call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID)
        || call.reserved[OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX] != 0)
        return 1;
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL;
    prior = *policy;
    memset(&call, 0, sizeof(call));
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT;
    call.lane = &lane;
    if (!ActorSystem_ReduceWalk(&call)
        || memcmp(policy, &prior, sizeof(*policy)) != 0
        || memcmp(actor, &priorActor, sizeof(*actor)) != 0
        || reduceCalls != 1
        || displayedTimeCalls != 0 || randomCalls != 0
        || call.operation != OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT
        || call.decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED
        || call.reserved[OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX]
            != OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL)
        return 2;
    policy->pendingStep = OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED;
    prior = *policy;
    memset(&call, 0, sizeof(call));
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT;
    call.lane = &lane;
    if (!ActorSystem_ReduceWalk(&call)
        || memcmp(policy, &prior, sizeof(*policy)) != 0
        || memcmp(actor, &priorActor, sizeof(*actor)) != 0
        || reduceCalls != 1
        || displayedTimeCalls != 0 || randomCalls != 0
        || call.operation != OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_INPUT
        || call.reserved[OVERWORLD_ACTOR_WALK_POLICY_PREVIEW_PENDING_INDEX]
            != OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED)
        return 3;
    puts("preview skid and pending state unchanged");
    return 0;
}
'''


class WalkPolicyPreview(unittest.TestCase):
    def test_skid_preview_does_not_commit_or_replace_pending_step(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "preview.c"
            binary = Path(temp) / "preview"
            source.write_text(harness())
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            run = subprocess.run([str(binary)], check=True,
                                 capture_output=True, text=True)
            self.assertEqual(run.stdout.strip(),
                             "preview skid and pending state unchanged")


if __name__ == "__main__":
    unittest.main()
