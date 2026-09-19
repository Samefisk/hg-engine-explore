"""S1: rejected candidates are not a genuine no-input/stop command.

Compile current policy bodies, header declarations, Wild adapter bodies and
the real portable role controller. Native inspection/engine admission are
host stubs; this does not prove game scheduling, collision or rendered motion.
The normal S4 Ledyba failure remains the separate product witness.
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
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
ACTOR = ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"


def harness_source():
    spec = importlib.util.spec_from_file_location("candidate_bodies", ROOT / "scripts/verify_overworld_role_controller.py")
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    runtime, wild, actor = RUNTIME.read_text(), WILD.read_text(), ACTOR.read_text()
    walk_module = (
        ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c"
    ).read_text()
    movement = (ROOT / "include/overworld_wild_movement.h").read_text()
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    behavior = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    timing = (ROOT / "include/overworld_walk_timing_policy.h").read_text()

    def declaration(source, prefix):
        if source.count(prefix) != 1:
            raise ValueError("unique declaration missing: " + prefix)
        first = source.index(prefix)
        start = source.index("{", first)
        end = extract.matching_delimiter(extract.strip_c_noncode(source), start, "{", "}")
        if end < 0: raise ValueError("incomplete declaration: " + prefix)
        return source[first:source.index(";", end) + 1]

    declarations = [declaration(movement, "typedef struct " + name + " {") for name in (
        "OverworldWildWalkMomentumState", "OverworldActorPolicyView", "OverworldActorPolicyProfileBinding",
        "OverworldActorWalkPolicyCall")]
    declarations += [declaration(movement, "typedef enum " + name + " {") for name in (
        "OverworldActorWalkPolicyOperation", "OverworldActorWalkPolicyDecision",
        "OverworldActorWalkPolicyStartResult")]
    declarations += [declaration(behavior, "typedef struct OverworldWildBehaviorProfileData {"),
                     "typedef struct OverworldActorPolicyState OverworldActorPolicyState;",
                     declaration(internal, "struct OverworldActorPolicyState {")]
    functions = []
    for source, signature in (
        (timing, "static u8 OverworldWalkTimingPolicy_Clamp(u8 travelTime)"),
        (timing, "static u8 OverworldWalkTimingPolicy_Accelerate(u8 currentTravelTime, u8 fastestTravelTime, u8 accelerationStep)"),
        (timing, "static u8 OverworldWalkTimingPolicy_Decelerate(u8 currentTravelTime, u8 baseTravelTime, u8 accelerationStep)"),
        (timing, "static u8 OverworldWalkTimingPolicy_SkidTiles(u8 travelTime)"),
        (timing, "static u8 OverworldWalkTimingPolicy_SkidTime(u8 travelTime)"),
        (timing, "static BOOL OverworldWalkTimingPolicy_StompApplies(u8 travelTime, u8 stompAtTravelTime)"),
        (runtime, "static void OverworldActorWalkPolicy_ResetState(OverworldActorPolicyState *policy, BOOL initialize, u8 baseSpeed, u8 laneState)"),
        (walk_module, "void OverworldWalk_MarkPlannedStopSkid(const OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call)"),
        (walk_module, "void OverworldWalk_ProposeStep(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call, u8 direction, u8 facing, u8 time, u8 stepFlags, u8 skidTiles)"),
        (runtime, "static void OverworldActorWalkPolicy_ReduceInput(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call)"),
        (runtime, "static void OverworldActorWalkPolicy_ReduceStartResult(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call)"),
        (runtime, "static void OverworldActorWalkPolicy_ReduceCommit(OverworldActorPolicyState *policy, OverworldActorWalkPolicyCall *call)"),
    ):
        name = signature.split("(", 1)[0].split()[-1]
        functions.append(signature + " {" + extract.function_bodies(source)[name] + "}\n")
    adapter = "static u32 OverworldWildSpawns_ReduceRole(int slot, u32 request, u32 details) {" \
        + extract.function_bodies(wild)["OverworldWildSpawns_ReduceRole"] + "}\n"
    adapter += "static BOOL OverworldWildSpawns_TryStartAcceleratedWalkStep(const OverworldWildDirectionStepContext *stepContext, u8 direction) {" \
        + extract.function_bodies(wild)["OverworldWildSpawns_TryStartAcceleratedWalkStep"] + "}\n"
    definitions = {}
    for source in (movement, behavior, timing, wild, (ROOT / "include/overworld_wild_spawns_internal.h").read_text()):
        for line in source.replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match: definitions[match[1]] = line
    actor_wrapper = "static BOOL ActorSystem_ReduceWalk(OverworldActorWalkPolicyCall *call) {" \
        + extract.function_bodies(actor)["ActorSystem_ReduceWalk"] + "}\n"
    text = "\n".join(declarations + functions) + SUPPORT + actor_wrapper + adapter + DRIVER
    wanted = set(re.findall(r"\b(?:OW_WILD|OVERWORLD_ACTOR_WALK|OVERWORLD_WALK)_[A-Z_0-9]+\b", text))
    included, macros = set(), []
    while wanted:
        name = wanted.pop()
        if name in included or name not in definitions: continue  # enums are compiled above
        line = definitions[name]
        included.add(name); macros.append(line)
        wanted.update(re.findall(r"\b[A-Z][A-Z_0-9]+\b", line.split(name, 1)[1]))
    # Only field/transport stubs use host-sized structures. Policy structures
    # and role enums/packing are the current source declarations, not replicas.
    return PRELUDE + "\n".join(macros + declarations) + HELPERS + "\n".join(functions) \
        + SUPPORT + actor_wrapper + adapter + DRIVER


PRELUDE = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_role_controller.h"
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
"""

HELPERS = r"""
#define OverworldWalk_ClampTime OverworldWalkTimingPolicy_Clamp
#define OverworldWalk_AccelerateTime OverworldWalkTimingPolicy_Accelerate
#define OverworldWalk_DecelerateTime OverworldWalkTimingPolicy_Decelerate
#define ActorSystem_ClampWalkTimeWide(time) OverworldWalkTimingPolicy_Clamp((u8)(time))
#define OverworldWalk_SkidTiles OverworldWalkTimingPolicy_SkidTiles
#define OverworldWalk_SkidTime OverworldWalkTimingPolicy_SkidTime
#define OverworldWalk_StompApplies OverworldWalkTimingPolicy_StompApplies
void OverworldWalk_MarkPlannedStopSkid(
    const OverworldActorPolicyState *policy,
    OverworldActorWalkPolicyCall *call);
static BOOL OverworldWalk_IsFortyFiveDegreeTurn(u8 from, u8 to)
{ (void)from; (void)to; return FALSE; }
static u8 OverworldWalkDirectionPolicy_ApplyStartResult(u8 committed, u8 proposed, BOOL accepted)
{ return accepted ? proposed : committed; }
#define OVERWORLD_ACTOR_WORLD_EFFECT_CRASH 3
#define OVERWORLD_ACTOR_WORLD_EFFECT_STOMP 2
#define OVERWORLD_ACTOR_WORLD_EFFECT_SKID_DUST 1
#define OVERWORLD_ACTOR_WORLD_EFFECT_NONE 0
_Static_assert(sizeof(OverworldActorPolicyState) == 32, "actual policy state layout");
_Static_assert(sizeof(OverworldWildBehaviorProfileData) == 72, "actual lane layout");
_Static_assert(offsetof(OverworldActorWalkPolicyCall, decision)
    - offsetof(OverworldActorWalkPolicyCall, actorSlot) == 8
    && OVERWORLD_ACTOR_WALK_POLICY_IGNORED == 0, "observer ignored-input public ABI");
static unsigned checks, reductions, executions;
static u8 lastStepFlags;
static OverworldWildBehaviorProfileData lane;
typedef struct OverworldActorStateSnapshot { u32 commitSequence; } OverworldActorStateSnapshot;
typedef struct OverworldActorRuntimeSlot {
    OverworldActorStateSnapshot snapshot;
    OverworldActorPolicyState policy;
} OverworldActorRuntimeSlot;
static struct {
    OverworldActorRuntimeSlot slots[10];
} gOverworldActorSystemState;
#define selected gOverworldActorSystemState.slots[0].policy
"""

SUPPORT = r"""
typedef struct OverworldWildSpawnState {
    u8 movementSpawnRunActive[10], movementSpotStates[10];
} OverworldWildSpawnState;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    const OverworldWildBehaviorProfileData *profile;
    u8 slot;
} OverworldWildDirectionStepContext;
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetBehaviorStateLane(
    const OverworldWildBehaviorProfileData *profile, u8 spotState)
{ (void)spotState; return profile; }
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *view)
{ if (slot != 0) abort(); memset(view, 0, sizeof(*view)); view->walkMomentum = selected.walkMomentum; return TRUE; }
static void OverworldWildSpawns_InitPolicyCall(OverworldActorWalkPolicyCall *call, u8 slot, u8 operation)
{ memset(call, 0, sizeof(*call)); call->version=OVERWORLD_ACTOR_WALK_POLICY_VERSION;
  call->size=sizeof(*call); call->actorSlot=slot; call->operation=operation; }
static BOOL ActorSystem_ReduceWalk(OverworldActorWalkPolicyCall *call);
static BOOL RuntimeReduceWalk(OverworldActorPolicyState *policy,
    OverworldActorStateSnapshot *actor, OverworldActorWalkPolicyCall *call)
{ (void)actor;
  if (call->operation==OVERWORLD_ACTOR_WALK_POLICY_INPUT)
      OverworldActorWalkPolicy_ReduceInput(policy,call);
  else if (call->operation==OVERWORLD_ACTOR_WALK_POLICY_START_RESULT)
      OverworldActorWalkPolicy_ReduceStartResult(policy,call);
  else if (call->operation==OVERWORLD_ACTOR_WALK_POLICY_COMMIT)
      OverworldActorWalkPolicy_ReduceCommit(policy,call);
  return TRUE; }
static const struct {
    BOOL (*reduceWalk)(OverworldActorPolicyState *, OverworldActorStateSnapshot *,
        OverworldActorWalkPolicyCall *);
} testPolicyOwner={RuntimeReduceWalk};
#undef OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY
#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY (&testPolicyOwner)
#ifndef OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
#define OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS 10
#endif
static BOOL ReduceWalk(OverworldActorWalkPolicyCall *call)
{ reductions++; return ActorSystem_ReduceWalk(call); }
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{ return ReduceWalk(call); }
static BOOL OverworldWildSpawns_ExecuteWalkPolicy(OverworldWildDirectionStepContext *context,
    OverworldActorWalkPolicyCall *call)
{ (void)context; executions++; lastStepFlags=call->stepFlags;
  return call->decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED; }
static const struct { void (*reduceRole)(const OverworldRoleControllerInput *, OverworldRoleControllerOutput *); }
    runtimeEntry = {OverworldRoleController_Reduce};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&runtimeEntry)
static void Check(BOOL condition, const char *message)
{ checks++; if (!condition) { fprintf(stderr, "%s\n", message); exit(1); } }
static void Seed(void)
{
    gOverworldActorSystemState.slots[0].snapshot.commitSequence = 0;
    memset(&selected, 0xA5, sizeof(selected));
    selected.walkMomentum = (OverworldWildWalkMomentumState){4, 2, 8, 8, 0, 0, 3, 6};
    selected.chainStepsRemaining = 10;
    selected.deferredChainPauseTicks = 37;
    selected.deferredChainPauseAction = OVERWORLD_ROLE_CONTROLLER_CHAIN_REPOSITION_SKIDS;
    selected.variancePhase = 0;
    selected.bufferedDirection = OW_WILD_WALK_DIRECTION_NONE;
    selected.stopPending = FALSE;
    selected.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
    selected.pendingSkid = FALSE;
    memset(&lane, 0, sizeof(lane)); lane.chillSpeed = 8;
}
static OverworldActorWalkPolicyCall Input(u8 direction)
{
    OverworldActorWalkPolicyCall call;
    OverworldWildSpawns_InitPolicyCall(&call, 0, OVERWORLD_ACTOR_WALK_POLICY_INPUT);
    call.lane=&lane; call.direction=direction; call.laneState=0;
    call.flags=OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    return call;
}
"""

DRIVER = r"""
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "rejected")) {
        for (unsigned mode=0; mode<2; mode++) for (u8 index=0; index<4; index++)
            for (unsigned variant=0; variant<16; variant++) {
                Seed(); lane.hopAllowNonCardinal = mode
                    ? OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY
                    : OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY;
                if (variant&1) selected.walkMomentum.speed=0;
                if (variant&2) selected.walkMomentum.baseSpeed=7;
                if (variant&4) selected.walkMomentum.spotState=2;
                if (variant&8) {
                    selected.bufferedDirection=5; selected.stopPending=TRUE;
                    selected.pendingStep=OVERWORLD_ACTOR_WALK_PENDING_ACTIVE;
                    selected.pendingSkid=TRUE; selected.walkMomentum.skidRemaining=2;
                }
                u8 direction = index + (mode ? 4 : 0);
                OverworldActorPolicyState before = selected;
                OverworldActorWalkPolicyCall call=Input(direction), callBefore=call;
                OverworldActorWalkPolicy_ReduceInput(&selected, &call);
                if (memcmp(&before, &selected, sizeof(before)) || memcmp(&call, &callBefore, sizeof(call))) {
                    fprintf(stderr, "forbidden candidate changed policy: direction=%u mode=%u variant=%u chain=%u->%u flags=%u decision=%u\n",
                        direction, lane.hopAllowNonCardinal, variant, before.chainStepsRemaining,
                        selected.chainStepsRemaining, call.stepFlags, call.decision); return 1;
                }
                checks++;
            }
    } else if (!strcmp(argv[1], "legal")) {
        for (u8 direction=0; direction<8; direction++) {
            Seed(); lane.hopAllowNonCardinal=direction<4
                ? OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY
                : OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY;
            selected.walkMomentum.direction=OW_WILD_WALK_DIRECTION_NONE;
            OverworldActorWalkPolicyCall call=Input(direction);
            OverworldActorWalkPolicy_ReduceInput(&selected, &call);
            Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP && call.stepDirection==direction
                && call.travelTime==8 && selected.chainStepsRemaining==10, "legal direction did not propose unchanged Walk");
        }
        /* An accepted lane change still initializes new momentum and clears
         * the prior lane's chain. Only rejected candidates bypass that work. */
        Seed(); lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY;
        lane.chillSpeed=12;
        OverworldActorWalkPolicyCall call=Input(5);
        call.laneState=OW_WILD_SPAWNER_SPOT_STATE_ACTIVE;
        OverworldActorWalkPolicy_ReduceInput(&selected, &call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP && call.stepDirection==5
            && call.travelTime==12 && call.stepFlags==OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION
            && selected.walkMomentum.speed==12 && selected.walkMomentum.baseSpeed==12
            && selected.walkMomentum.spotState==OW_WILD_SPAWNER_SPOT_STATE_ACTIVE
            && selected.chainStepsRemaining==0 && selected.deferredChainPauseTicks==0
            && selected.deferredChainPauseAction==0, "allowed lane change no longer initializes policy");
    } else if (!strcmp(argv[1], "none")) {
        Seed(); lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY;
        OverworldActorWalkPolicyCall call=Input(OW_WILD_WALK_DIRECTION_NONE);
        OverworldActorWalkPolicy_ReduceInput(&selected, &call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_IGNORED
            && call.stepFlags==OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION
            && selected.chainStepsRemaining==0 && selected.deferredChainPauseTicks==0
            && selected.deferredChainPauseAction==0 && selected.walkMomentum.speed==8
            && selected.walkMomentum.direction==OW_WILD_WALK_DIRECTION_NONE, "genuine NONE reset changed");
        Seed(); selected.walkMomentum.speed=2;
        call=Input(OW_WILD_WALK_DIRECTION_NONE);
        call.flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_DEFER_STOP;
        OverworldActorWalkPolicy_ReduceInput(&selected, &call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_CONSUMED && selected.stopPending,
              "genuine NONE defer changed");
        call=Input(OW_WILD_WALK_DIRECTION_NONE);
        OverworldActorWalkPolicy_ReduceInput(&selected, &call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP && call.distance==2 && call.travelTime==4
            && call.stepDirection==4 && call.facingDirection==4
            && call.stepFlags==(OVERWORLD_ACTOR_WALK_STEP_VALIDATE | OVERWORLD_ACTOR_WALK_STEP_SKID
                | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID) && selected.chainStepsRemaining==10,
            "genuine NONE stop skid changed");
    } else if (!strcmp(argv[1], "batch")) {
        Seed(); lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY;
        OverworldWildSpawnState state={0};
        OverworldWildDirectionStepContext context={&state,&lane,0};
        OverworldActorPolicyState before=selected;
        /* Exact rejected INPUT order in S4 test-00230788..., frame1880. */
        u8 directions[]={0,3,2};
        for (unsigned i=0; i<sizeof(directions); i++)
            Check(!OverworldWildSpawns_TryStartAcceleratedWalkStep(&context, directions[i]),
                  "forbidden candidate accepted by Wild adapter");
        Check(!memcmp(&before,&selected,sizeof(before)), "complete rejected Wild candidate batch erased state");
        unsigned calls=reductions, applied=executions;
        Check(!OverworldWildSpawns_TryStartAcceleratedWalkStep(&context, OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE),
              "Wild NONE was accepted");
        Check(reductions==calls && executions==applied && !memcmp(&before,&selected,sizeof(before)),
              "Wild NONE reached Walk reducer or engine");
    } else if (!strcmp(argv[1], "turn")) {
        OverworldActorWalkPolicyCall call;

        /* The old /2 rule walks the base-derived levels backwards exactly,
         * including its odd ceil-half level. */
        Seed(); lane.chillSpeed=20; lane.walkAccelerationStep=33;
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,3,20,0,0,3,0};
        call=Input(1); call.flags|=OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID;
        OverworldActorWalkPolicy_ReduceInput(&selected,&call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP && call.travelTime==5
            && call.reserved[0]==5 && selected.walkMomentum.speed==3,
            "ordinary /2 turn did not propose one slower level without early mutation");
        call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
        OverworldActorWalkPolicy_ReduceStartResult(&selected,&call);
        Check(selected.walkMomentum.speed==5 && selected.walkMomentum.tileCounter==0
            && selected.walkMomentum.direction==1,
            "accepted ordinary /2 turn did not lose one acceleration level");

        Seed(); lane.chillSpeed=20; lane.walkAccelerationStep=3;
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,8,20,0,0,3,0};
        call=Input(1); call.flags|=OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID;
        OverworldActorWalkPolicy_ReduceInput(&selected,&call);
        Check(call.travelTime==11 && call.reserved[0]==11,
            "fixed-step turn did not add back one configured frame step");

        Seed(); lane.chillSpeed=20; lane.walkAccelerationStep=0;
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,5,20,0,0,3,0};
        call=Input(1); call.flags|=OVERWORLD_ACTOR_WALK_POLICY_FLAG_SUPPRESS_TURN_SKID;
        OverworldActorWalkPolicy_ReduceInput(&selected,&call);
        Check(call.travelTime==5 && call.reserved[0]==5,
            "disabled acceleration changed speed on turn");
        call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
        OverworldActorWalkPolicy_ReduceStartResult(&selected,&call);
        Check(selected.walkMomentum.speed==5 && selected.walkMomentum.tileCounter==2,
            "blocked turn changed acceleration state");

        Seed(); lane.walkAccelerationStep=33; lane.tilesBeforeTurnSkid=1;
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,2,8,0,0,3,0};
        call=Input(1);
        OverworldActorWalkPolicy_ReduceInput(&selected,&call);
        Check(call.travelTime==4 && call.reserved[0]==4
            && (call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_SKID)!=0,
            "turn skid did not carry its one-level-slower recovery");
        call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
        OverworldActorWalkPolicy_ReduceStartResult(&selected,&call);
        Check(selected.walkMomentum.resumeSpeed==4,
            "turn skid did not prepare recovery one acceleration level slower");

        for (u8 speed=5; speed<=7; speed++) {
            Seed(); lane.walkAccelerationStep=0; lane.tilesBeforeTurnSkid=1;
            lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
            selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,speed,8,0,0,3,0};
            call=Input(1);
            OverworldActorWalkPolicy_ReduceInput(&selected,&call);
            if (speed<=6) {
                Check(call.distance==1 && call.travelTime==speed*2
                    && (call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_SKID)!=0,
                    "5-6 frame turn did not propose a one-tile skid");
            } else {
                Check(call.distance==0 && call.travelTime==7
                    && (call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_SKID)==0,
                    "7-frame turn unexpectedly proposed a skid");
            }
        }

        Seed(); lane.walkAccelerationStep=33;
        lane.tilesBeforeTurnSkid=OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(1, 0, 0);
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,2,8,0,0,3,0};
        call=Input(1);
        OverworldActorWalkPolicy_ReduceInput(&selected,&call);
        Check((call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_SKID)!=0
            && (call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH)==0,
            "default-off turn skid unexpectedly planned its future path");

        Seed(); lane.walkAccelerationStep=33;
        lane.tilesBeforeTurnSkid=OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(1, 1, 0);
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum=(OverworldWildWalkMomentumState){0,2,2,8,0,0,3,0};
        call=Input(1);
        OverworldActorWalkPolicy_ReduceInput(&selected,&call);
        Check((call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH)!=0
            && call.reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX]==call.distance,
            "opted-in turn skid did not reserve its exact skid path");
        OverworldWildWalkMomentumState momentumBefore=selected.walkMomentum;
        u8 chainBefore=selected.chainStepsRemaining;
        call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
        OverworldActorWalkPolicy_ReduceStartResult(&selected,&call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_IGNORED
            && call.effect==OVERWORLD_ACTOR_WORLD_EFFECT_NONE
            && selected.pendingStep==OVERWORLD_ACTOR_WALK_PENDING_NONE
            && !memcmp(&momentumBefore,&selected.walkMomentum,sizeof(momentumBefore))
            && selected.chainStepsRemaining==chainBefore,
            "blocked planned turn skid changed momentum, chain state, or crash output");
    } else if (!strcmp(argv[1], "surface-validation")) {
        Seed();
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum.direction=OW_WILD_WALK_DIRECTION_NONE;
        OverworldWildSpawnState state={0};
        OverworldWildDirectionStepContext context={&state,&lane,0};
        Check(OverworldWildSpawns_TryStartAcceleratedWalkStep(&context, 0)
            && (lastStepFlags&OVERWORLD_ACTOR_WALK_STEP_VALIDATE)!=0,
            "initial Wild Walk skipped surface validation");

        Seed();
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum.direction=0;
        selected.walkMomentum.speed=8;
        Check(OverworldWildSpawns_TryStartAcceleratedWalkStep(&context, 1)
            && (lastStepFlags&OVERWORLD_ACTOR_WALK_STEP_VALIDATE)!=0
            && (lastStepFlags&OVERWORLD_ACTOR_WALK_STEP_RESET_ACCELERATION)!=0,
            "turning Wild Walk skipped surface validation");
    } else if (!strcmp(argv[1], "variance")) {
        Seed();
        lane.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        lane.chainRepositionAllowDiagonal =
            OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS(0, 31);
        selected.walkMomentum.direction = OW_WILD_WALK_DIRECTION_NONE;
        OverworldActorWalkPolicyCall call=Input(0);
        ReduceWalk(&call);
        Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call.travelTime==8 && call.reserved[0]==8
            && selected.variancePhase==0,
            "first varied Walk proposal or nominal speed differs");
        call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
        call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        ReduceWalk(&call);
        Check(selected.variancePhase==0 && selected.walkMomentum.speed==8,
            "blocked Walk consumed variance or changed momentum");
        call=Input(0);
        ReduceWalk(&call);
        Check(call.travelTime==8, "blocked Walk rerolled its candidate");
        call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
        call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        ReduceWalk(&call);
        Check(selected.variancePhase==0 && selected.walkMomentum.speed==8,
            "accepted varied Walk changed chain variance or nominal momentum");
        gOverworldActorSystemState.slots[0].snapshot.commitSequence++;
        call=Input(0);
        ReduceWalk(&call);
        Check(call.travelTime==17 && selected.walkMomentum.speed==8,
            "next varied Walk did not use the next capped duration");
        Seed(); lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        lane.chainRepositionAllowDiagonal=
            OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS(0, 0);
        selected.walkMomentum.direction=OW_WILD_WALK_DIRECTION_NONE;
        call=Input(0); ReduceWalk(&call);
        Check(call.travelTime==8 && selected.variancePhase==0,
            "zero variance changed the existing Walk time");
        Seed(); lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        lane.chainRepositionAllowDiagonal=
            OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS(0, 31);
        selected.walkMomentum.speed=2; selected.walkMomentum.direction=0;
        call=Input(OW_WILD_WALK_DIRECTION_NONE);
        ReduceWalk(&call);
        Check(call.travelTime==4 && (call.stepFlags&OVERWORLD_ACTOR_WALK_STEP_SKID)!=0,
            "Walk variance changed stop-skid timing");
        Seed(); lane.chillSpeed=3;
        lane.hopAllowNonCardinal=OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        lane.chainRepositionAllowDiagonal=
            OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS(0, 5);
        selected.walkMomentum.direction=OW_WILD_WALK_DIRECTION_NONE;
        for (u8 sequence=0; sequence<6; sequence++) {
            gOverworldActorSystemState.slots[0].snapshot.commitSequence=sequence;
            call=Input(0); ReduceWalk(&call);
            Check(call.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
                && call.travelTime==3+sequence,
                "3-frame Walk variance did not preserve the full 3..8 range");
            call.startResult=OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
            call.operation=OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
            ReduceWalk(&call);
        }
    } else if (!strcmp(argv[1], "chain-does-not-stop-skid")) {
        Seed();
        lane.chillSpeed = 12;
        lane.maxWalkSpeed = 4;
        lane.tilesToAccelerate = 2;
        lane.walkAccelerationStep = 33;
        lane.ramAccelerationSteps = 6;
        lane.chainMovementVariance = 0;
        lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE;
        lane.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(3, 0, 1);
        lane.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum = (OverworldWildWalkMomentumState){0, 1, 4, 12, 0, 0, 5, 0};
        selected.chainStepsRemaining = 1;
        selected.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
        OverworldActorWalkPolicyCall call = Input(0);
        ReduceWalk(&call);
        Check(call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call.stepDirection == 0 && call.travelTime == 4
            && (call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_PLANNED_STOP_SKID) == 0
            && call.reserved[OVERWORLD_ACTOR_WALK_POLICY_STOP_SKID_TILES_INDEX] == 0,
            "PAUSE chain incorrectly started lifecycle stop-skid planning");

        lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD;
        selected.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
        call = Input(0); ReduceWalk(&call);
        Check((call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_PLANNED_STOP_SKID) == 0
            && call.reserved[OVERWORLD_ACTOR_WALK_POLICY_STOP_SKID_TILES_INDEX] == 0,
            "HOP_FORWARD chain incorrectly started lifecycle stop-skid planning");
    } else if (!strcmp(argv[1], "runner-turn-runway")) {
        Seed();
        lane.chillSpeed = 8;
        lane.maxWalkSpeed = 4;
        lane.tilesToAccelerate = 1;
        lane.walkAccelerationStep = 1;
        lane.ramAccelerationSteps = 6;
        lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD;
        lane.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(1, 1, 1);
        lane.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum = (OverworldWildWalkMomentumState){3, 0, 8, 8, 0, 0, 0, 0};
        selected.chainStepsRemaining = 6;
        OverworldActorWalkPolicyCall call = Input(3);
        ReduceWalk(&call);
        Check(call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call.stepDirection == 3
            && (call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH) != 0
            && call.reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX]
                == OverworldWalk_SkidTiles(lane.maxWalkSpeed),
            "Runner normal step did not reserve its future turn-skid runway");
        OverworldWildWalkMomentumState momentumBefore = selected.walkMomentum;
        u8 chainBefore = selected.chainStepsRemaining;
        call.operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult = OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
        ReduceWalk(&call);
        Check(call.decision == OVERWORLD_ACTOR_WALK_POLICY_IGNORED
            && selected.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_NONE
            && !memcmp(&momentumBefore, &selected.walkMomentum, sizeof(momentumBefore))
            && selected.chainStepsRemaining == chainBefore,
            "blocked Runner runway did not reject the candidate without changing momentum");

        Seed();
        lane.chillSpeed = 8; lane.maxWalkSpeed = 4;
        lane.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(1, 1, 1);
        lane.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum = (OverworldWildWalkMomentumState){3, 0, 8, 8, 0, 0, 0, 0};
        call = Input(3);
        call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED;
        ReduceWalk(&call);
        Check((call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH) == 0,
            "mounted Runner proposal incorrectly reserved Wild-only runway");

        Seed();
        lane.chillSpeed = 8; lane.maxWalkSpeed = 4;
        lane.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(0, 1, 1);
        lane.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum = (OverworldWildWalkMomentumState){3, 0, 8, 8, 0, 0, 0, 0};
        call = Input(3);
        ReduceWalk(&call);
        Check((call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH) == 0,
            "zero turn-skid threshold incorrectly reserved future runway");
    } else if (!strcmp(argv[1], "runner-turn-complete")) {
        Seed();
        lane.chillSpeed = 8;
        lane.maxWalkSpeed = 4;
        lane.tilesToAccelerate = 1;
        lane.walkAccelerationStep = 1;
        lane.ramAccelerationSteps = 6;
        lane.chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD;
        lane.tilesBeforeTurnSkid = OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(1, 1, 1);
        lane.hopAllowNonCardinal = OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
        selected.walkMomentum = (OverworldWildWalkMomentumState){3, 0, 4, 8, 0, 0, 3, 0};
        selected.chainStepsRemaining = 4;

        OverworldActorWalkPolicyCall call = Input(0);
        ReduceWalk(&call);
        Check(call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call.stepDirection == 3 && call.facingDirection == 0
            && (call.stepFlags & (OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH))
                == (OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH),
            "Runner did not propose its planned turn skid");
        call.operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult = OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
        ReduceWalk(&call);

        OverworldWildSpawns_InitPolicyCall(
            &call, 0, OVERWORLD_ACTOR_WALK_POLICY_COMMIT);
        call.lane = &lane;
        call.direction = 3;
        call.distance = 1;
        call.laneState = 0;
        call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACTIVE
            | OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
        ReduceWalk(&call);
        Check(call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call.stepDirection == 0 && call.facingDirection == 0
            && (call.stepFlags & (OVERWORLD_ACTOR_WALK_STEP_POST_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                    | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH))
                == (OVERWORLD_ACTOR_WALK_STEP_POST_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_VALIDATE
                    | OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH)
            && call.reserved[OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX]
                == OverworldWalk_SkidTiles(lane.maxWalkSpeed)
            && selected.walkMomentum.direction == 0,
            "Runner turn skid recovery did not reserve the next turn runway");
        call.operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
        call.startResult = OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
        ReduceWalk(&call);
        Check(selected.walkMomentum.direction == 0 && !selected.pendingSkid
                && selected.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_ACTIVE,
            "Runner post-skid step did not commit the requested direction");
    } else return 2;
    printf("candidate rejection: %s %u checks passed\n", argv[1], checks);
    return 0;
}
"""


def execute(source, case):
    with tempfile.TemporaryDirectory(prefix="walk-candidate-") as directory:
        unit, binary = Path(directory) / "fixture.c", Path(directory) / "fixture"
        unit.write_text(source)
        command = shlex.split(os.environ.get("CC", "cc")) + ["-std=gnu11", "-O2", "-fno-strict-aliasing",
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
            "-DOVERWORLD_ROLE_CONTROLLER_HOST", "-I", str(ROOT / "include"),
            str(unit), str(ROOT / "lib/overworld/overworld_role_controller.c"), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode: raise RuntimeError(compiled.stderr)
        return subprocess.run([str(binary), case], capture_output=True, text=True)


class WalkPolicyCandidateRejectionTests(unittest.TestCase):
    def test_forbidden_candidates_preserve_complete_policy(self):
        result = execute(harness_source(), "rejected")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_wild_rejected_batch_does_not_turn_into_stop(self):
        result = execute(harness_source(), "batch")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legal_candidates_and_genuine_none_keep_original_semantics(self):
        source = harness_source()
        for case in ("legal", "none"):
            with self.subTest(case=case):
                result = execute(source, case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_walk_time_variance_is_per_accepted_normal_tile(self):
        result = execute(harness_source(), "variance")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_movement_chain_never_starts_stop_skid(self):
        result = execute(harness_source(), "chain-does-not-stop-skid")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_runner_normal_step_reserves_future_turn_skid_runway(self):
        result = execute(harness_source(), "runner-turn-runway")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_runner_turn_skid_commits_requested_direction(self):
        result = execute(harness_source(), "runner-turn-complete")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accepted_turn_loses_one_acceleration_level(self):
        result = execute(harness_source(), "turn")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_ordinary_wild_walks_request_surface_validation(self):
        result = execute(harness_source(), "surface-validation")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_conversion_and_other_boundary_mutations_are_rejected(self):
        source = harness_source()
        start = source.index("if ((requestedDirection < 4")
        end = source.index("    if (state->speed == 0", start)
        branch = source[start:end]
        self.assertEqual(len(re.findall(r"\breturn\s*;", branch)), 1)
        old = re.sub(r"\breturn\s*;", "requestedDirection = OW_WILD_WALK_DIRECTION_NONE;", branch)
        dirty = re.sub(r"\breturn\s*;", "policy->chainStepsRemaining = 0; return;", branch)
        role_guard = """if ((roleDecision & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0) {
        return FALSE;
    }"""
        self.assertEqual(source.count(role_guard), 1)
        none_branch = "if (requestedDirection == OW_WILD_WALK_DIRECTION_NONE) {"
        self.assertEqual(source.count(none_branch), 1)
        mutants = (
            (source[:start] + old + source[end:], "rejected", "old NONE conversion"),
            (source[:start] + dirty + source[end:], "rejected", "mutate before rejection"),
            (source.replace(role_guard, "/* removed role rejection */"), "batch", "Wild NONE policy admission"),
            (source.replace(none_branch, none_branch + " return;"), "none", "swallowed genuine NONE"),
        )
        for changed, case, name in mutants:
            with self.subTest(mutation=name):
                result = execute(changed, case)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
