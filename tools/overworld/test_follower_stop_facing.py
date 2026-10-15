"""TKT-0008: an empty follower stop reply must not request North.

Compile the current Wild call initializer, INPUT reducer and output adapter.
Lane/policy/call declarations and timing/proposal helpers come from production.
Only engine storage and unused reducer operations are host boundaries. This
proves the source seam; the same normal game stop remains live acceptance.
"""

from pathlib import Path
import importlib.util
import os
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def harness_source():
    spec = importlib.util.spec_from_file_location(
        "follower_stop_bodies", ROOT / "scripts/verify_overworld_role_controller.py"
    )
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    wild = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    runtime = (ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
    policy = (ROOT / "src/player_health_overlay/overworld_walk_input_policy.c").read_text()
    walk = (ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c").read_text()
    movement = (ROOT / "include/overworld_wild_movement.h").read_text()
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    behavior = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    timing = (ROOT / "include/overworld_walk_timing_policy.h").read_text()
    actor_header = (ROOT / "include/overworld_actor_system.h").read_text()

    def declaration(source, prefix):
        if source.count(prefix) != 1:
            raise ValueError("unique production declaration missing: " + prefix)
        first = source.index(prefix)
        start = source.index("{", first)
        end = extract.matching_delimiter(extract.strip_c_noncode(source), start, "{", "}")
        return source[first:source.index(";", end) + 1]

    declarations = [declaration(movement, "typedef struct " + name + " {") for name in (
        "OverworldWildWalkMomentumState", "OverworldActorPolicyView",
        "OverworldActorPolicyProfileBinding", "OverworldActorPolicyProfileTransaction",
        "OverworldActorWalkPolicyCall")]
    declarations += [declaration(movement, "typedef enum " + name + " {") for name in (
        "OverworldActorWalkPolicyOperation", "OverworldActorWalkPolicyDecision",
        "OverworldActorWalkPolicyStartResult")]
    declarations += [declaration(behavior, "typedef struct OverworldWildBehaviorProfileData {"),
                     "typedef struct OverworldActorPolicyState OverworldActorPolicyState;",
                     declaration(internal, "struct OverworldActorPolicyState {"),
                     declaration(actor_header, "typedef enum OverworldActorWorldEffect {")]
    functions = []
    for source, signature in (
        (timing, "static u8 OverworldWalkTimingPolicy_Clamp(u8 travelTime)"),
        (timing, "static u16 OverworldWalkTimingPolicy_LinearTimeQ8(u8 baseTime, u8 fastestTime, u8 rampFrames, u8 movingFrames)"),
        (timing, "static u8 OverworldWalkTimingPolicy_LinearElapsedForTime(u8 baseTime, u8 fastestTime, u8 rampFrames, u8 visibleTime)"),
        (timing, "static u8 OverworldWalkTimingPolicy_LinearDuration(u16 timeQ8, u8 carry, u8 *nextCarry)"),
        (timing, "static u8 OverworldWalkTimingPolicy_Decelerate(u8 currentTravelTime, u8 baseTravelTime, u8 accelerationStep)"),
        (timing, "static u8 OverworldWalkTimingPolicy_SkidTiles(u8 travelTime)"),
        (timing, "static u8 OverworldWalkTimingPolicy_SkidTime(u8 travelTime)"),
        (policy, "static void OverworldActorWalkPolicy_ResetState(OverworldActorPolicyState *policy, BOOL initialize, u8 baseSpeed, u8 laneState)"),
        (walk, "void OverworldWalk_MarkPlannedStopSkid(const OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call)"),
        (walk, "void OverworldWalk_ProposeStep(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call, u8 direction, u8 facing, u8 time, u8 stepFlags, u8 skidTiles)"),
        (policy, "static void OverworldWalkInput_RefreshTuning(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call, u8 baseSpeed, BOOL linear)"),
        (policy, "static void OverworldActorWalkPolicy_ReduceInput(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call)"),
        (runtime, "static BOOL OverworldActorWalkPolicy_Reduce(OverworldActorPolicyState *policy, OverworldActorStateSnapshot *actor, OverworldActorWalkPolicyCall *call)"),
        (wild, "static void OverworldWildSpawns_InitPolicyCall(OverworldActorWalkPolicyCall *call, int slot, u8 operation)"),
        (wild, "static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 direction)"),
        (wild, "static void OverworldWildSpawns_ApplyWalkPolicyOutput(OverworldWildDirectionStepContext *stepContext, OverworldActorWalkPolicyCall *call)"),
    ):
        name = signature.split("(", 1)[0].split()[-1]
        functions.append(signature + " {" + extract.function_bodies(source)[name] + "}\n")
    definitions = {}
    for source in (movement, internal, behavior, timing, wild, actor_header):
        for line in source.replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match:
                definitions[match[1]] = line
    text = "\n".join(declarations + functions) + SUPPORT + DRIVER
    wanted = set(re.findall(r"\b(?:OW_WILD|OVERWORLD_ACTOR|OVERWORLD_WALK)_[A-Z_0-9]+\b", text))
    included, macros = set(), []
    while wanted:
        name = wanted.pop()
        if name in included or name not in definitions:
            continue
        line = definitions[name]
        included.add(name)
        macros.append(line)
        wanted.update(re.findall(r"\b[A-Z][A-Z_0-9]+\b", line.split(name, 1)[1]))
    return PRELUDE + "\n".join(macros + declarations) + SUPPORT + "\n".join(functions) + DRIVER


PRELUDE = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define MAPOBJECTFLAG_UNK7 0x80
"""

SUPPORT = r"""
#define OverworldWalk_ClampTime OverworldWalkTimingPolicy_Clamp
#define OverworldWalk_DecelerateTime OverworldWalkTimingPolicy_Decelerate
#define OverworldWalk_SkidTiles OverworldWalkTimingPolicy_SkidTiles
#define OverworldWalk_SkidTime OverworldWalkTimingPolicy_SkidTime
typedef struct OverworldActorStateSnapshot { u8 unused; } OverworldActorStateSnapshot;
typedef struct LocalMapObject {
    u32 flags;
    u8 facingInit, curFacing, nextFacing, curFacingBak, nextFacingBak;
} LocalMapObject;
typedef struct OverworldWildSpawnState {
    u8 movementPreviousTileLocked[10], movementLastDistances[10];
    u8 movementCooldowns[10], movementSpotStates[10];
} OverworldWildSpawnState;
typedef struct OverworldWildBehaviorProfile { u8 unused; } OverworldWildBehaviorProfile;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    u8 slot;
} OverworldWildDirectionStepContext;
/* Stop cases never enter these operations or presentation effects. */
static BOOL OverworldActorWalkPolicy_ApplyCommand(OverworldActorPolicyState *p,
    OverworldActorStateSnapshot *a, OverworldActorWalkPolicyCall *c)
{ (void)p; (void)a; (void)c; abort(); }
static void OverworldActorWalkPolicy_ReduceStartResult(OverworldActorPolicyState *p,
    OverworldActorWalkPolicyCall *c) { (void)p; (void)c; abort(); }
static void OverworldActorWalkPolicy_ReduceCommit(OverworldActorPolicyState *p,
    OverworldActorWalkPolicyCall *c) { (void)p; (void)c; abort(); }
static void OverworldActorWalkPolicy_ReduceChain(OverworldActorPolicyState *p,
    OverworldActorStateSnapshot *a, OverworldActorWalkPolicyCall *c)
{ (void)p; (void)a; (void)c; abort(); }
static BOOL OverworldWalk_IsFortyFiveDegreeTurn(u8 from, u8 to)
{ (void)from; (void)to; abort(); }
static void Particle(LocalMapObject *object) { (void)object; abort(); }
static const struct { void (*playLandingHopParticle)(LocalMapObject *); }
    runtimeEntry = { Particle };
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
static void OverworldActor_PlayStompSound(u8 options) { (void)options; abort(); }
static void OverworldWildSpawns_PublishWalkCrash(OverworldWildSpawnState *state, u8 slot)
{ (void)state; (void)slot; abort(); }
static void OverworldWildSpawns_PlayMovementCrashFeedback(
    const OverworldWildBehaviorProfile *profile, u8 spot)
{ (void)profile; (void)spot; abort(); }
static void OverworldWildSpawns_StartMovementCrashShake(
    OverworldWildSpawnState *state, int slot, LocalMapObject *object, int frames)
{ (void)state; (void)slot; (void)object; (void)frames; abort(); }
_Static_assert(sizeof(OverworldActorPolicyState) == 36, "current native policy");
_Static_assert(sizeof(OverworldWildBehaviorProfileData) == 80, "current native lane");
static void check(int condition, const char *label)
{ if (!condition) { fprintf(stderr, "%s\n", label); exit(1); } }
"""

DRIVER = r"""
int main(void)
{
    /* Exact Stantler lane from measured ROM3482 INPUT receipt, frame 903. */
    const u8 laneBytes[80] = {
        3,3,8,10,1,20,10,8,32,2,0,3,1,6,1,15,90,12,0,0,2,2,0,9,
        30,0,0,1,5,0,0,0,1,0,255,3,4,0,0,0,4,1,0,1,0,0,0,10,
        100,100,120,4,16,0,255,3,1,1,0,0,4,5,1,1,5,2,80,100,
        0,193,0,34,0,0,0,0,8,20,60,4
    };
    OverworldWildBehaviorProfileData lane;
    memcpy(&lane, laneBytes, sizeof(lane));
    OverworldActorStateSnapshot actor = {0};
    /* Both the measured already-reset idle state and a just-finished slow
     * Walk must preserve each non-North direction when no skid is proposed. */
    for (u8 facing = 1; facing <= 3; ++facing) {
        for (u8 stopped = 0; stopped <= 1; ++stopped) {
            OverworldActorPolicyState policy = {0};
            OverworldActorWalkPolicy_ResetState(&policy, TRUE, 8, 0);
            if (!stopped) policy.walkMomentum.direction = facing;
            LocalMapObject object = { MAPOBJECTFLAG_UNK7, facing, facing,
                facing, facing, facing };
            OverworldWildSpawnState state = {0};
            state.movementPreviousTileLocked[7] = TRUE;
            state.movementLastDistances[7] = 1;
            OverworldWildDirectionStepContext context = { &state, &object, NULL, 7 };
            OverworldActorWalkPolicyCall call;
            OverworldWildSpawns_InitPolicyCall(&call, 7, OVERWORLD_ACTOR_WALK_POLICY_INPUT);
            call.lane = &lane;
            call.direction = OW_WILD_WALK_DIRECTION_NONE;
            check(OverworldActorWalkPolicy_Reduce(&policy, &actor, &call), "INPUT rejected");
            check(call.decision == OVERWORLD_ACTOR_WALK_POLICY_IGNORED
                && call.effect == OVERWORLD_ACTOR_WORLD_EFFECT_NONE
                && call.stepFlags == OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION,
                "stop reply differs from measured no-motion receipt");
            OverworldWildSpawns_ApplyWalkPolicyOutput(&context, &call);
            check(object.facingInit == facing && object.curFacing == facing
                && object.nextFacing == facing && object.curFacingBak == facing
                && object.nextFacingBak == facing,
                "empty follower stop reply changed facing to North");
            check(!(object.flags & MAPOBJECTFLAG_UNK7)
                && !state.movementPreviousTileLocked[7]
                && !state.movementLastDistances[7] && !call.stepFlags,
                "stop presentation cleanup did not run");
            check(call.stepDirection == OW_WILD_WALK_DIRECTION_NONE,
                "empty follower stop reply proposed a step direction");
            /* An explicit face request still uses the real adapter/setter. */
            call.facingDirection = 0;
            call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
            OverworldWildSpawns_ApplyWalkPolicyOutput(&context, &call);
            check(object.curFacing == 0 && object.nextFacing == 0,
                "explicit facing request was suppressed");
        }
    }
    puts("follower stop facing: production init/reducer/apply passed");
    return 0;
}
"""


class FollowerStopFacingTests(unittest.TestCase):
    def test_empty_stop_preserves_facing_through_production_pipeline(self):
        with tempfile.TemporaryDirectory(prefix="follower-stop-") as directory:
            executable = Path(directory) / "follower-stop"
            compiled = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")),
                 "-std=gnu11", "-O0", "-x", "c", "-", "-o", executable],
                input=harness_source(), text=True, capture_output=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            run = subprocess.run([executable], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == "__main__":
    unittest.main()
