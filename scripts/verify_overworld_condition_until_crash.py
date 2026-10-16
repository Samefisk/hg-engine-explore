#!/usr/bin/env python3
"""Compile production condition and Walk entry paths for Until Crash."""
from pathlib import Path
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONDITION_FIXTURE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "overworld_behavior_condition_runtime.h"

static void check_until_crash(void)
{
    OverworldBehaviorConditionDefinition d = {0};
    OverworldBehaviorConditionEntryInput in = {0};
    OverworldBehaviorConditionWorldView w = {0};
    OverworldBehaviorConditionEntryState s = {0};
    OverworldBehaviorConditionEntryResult r;
    d.conditionId = 1;
    d.kind = OVERWORLD_BEHAVIOR_CONDITION_PLAYER_NOTICED;
    d.activationMode = 2;
    d.targetKind = OVERWORLD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    d.rangeKind = OVERWORLD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM;
    d.distance = 32;
    d.reserved = OVERWORLD_VISION_CONE_CARDINAL_LINES;
    d.chance = 100;
    d.cooldownFrames = 100;
    w.subject = (OverworldActorHandle){.slot=0,.generation=1,
        .fieldEpoch=1,.mapGeneration=1,.encounterGeneration=1};
    w.subjectFacing = OVERWORLD_VISION_FACING_EAST;
    w.playerValid = 1;
    w.playerX = 32;
    w.frame = 1;
    assert(OverworldBehaviorCondition_DefinitionValid(&d));
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(r.active && r.triggered);
    w.playerX = 0;
    w.playerY = 10;
    w.frame = 1000;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(r.active && !r.triggered);
#if defined(OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING)
    OverworldBehaviorConditionPreparedActor prepared = {.subject=w.subject,
        .states=&s,.count=1,.valid=1,.stateCapacity=1};
    OverworldActorHandle stale = w.subject;
    stale.generation++;
    OverworldBehaviorCondition_NotifyWorldEffect(&prepared,&stale,
        OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    assert(!(s.flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING));
    for (unsigned field=0;field<5;field++) {
        stale=w.subject;
        switch(field) {
        case 0: stale.slot++;break;
        case 1: stale.generation++;break;
        case 2: stale.fieldEpoch++;break;
        case 3: stale.mapGeneration++;break;
        case 4: stale.encounterGeneration++;break;
        }
        OverworldBehaviorCondition_NotifyWorldEffect(&prepared,&stale,
            OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
        assert(!(s.flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING));
    }
    prepared.valid=0;
    OverworldBehaviorCondition_NotifyWorldEffect(&prepared,&w.subject,
        OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    assert(!(s.flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING));
    prepared.valid=1;
    OverworldBehaviorCondition_NotifyWorldEffect(&prepared,&w.subject,
        OVERWORLD_ACTOR_WORLD_EFFECT_STOMP);
    assert(!(s.flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING));
    OverworldBehaviorCondition_NotifyWorldEffect(&prepared,&w.subject,
        OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    assert(s.flags & OVERWORLD_BEHAVIOR_CONDITION_STATE_CRASH_PENDING);
    w.playerX=32; w.playerY=0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(!r.active && !r.triggered);
    w.frame=1001; w.playerY=1;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(!r.active);
    w.frame=1002; w.playerY=0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(!r.active);
    w.frame=1200;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(!r.active);
    w.playerY=1;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(!r.active);
    w.playerY=0;
    assert(OverworldBehaviorCondition_EvaluateEntry(&d,&in,&w,&s,&r)==0);
    assert(r.active && r.triggered);
#endif
}

int main(void)
{
    OverworldVisionSpec line = {32,OVERWORLD_VISION_CONE_CARDINAL_LINES};
    check_until_crash();
    assert(OverworldVision_CanSee(&line,0,0,3,32,0,0));
    assert(!OverworldVision_CanSee(&line,0,0,3,32,1,0));
    assert(!OverworldVision_CanSee(&line,0,0,3,33,0,0));
    assert(OverworldVision_CanSee(&line,0,0,3,-1,0,0));
    assert(OverworldVision_CanSee(&line,0,0,3,0,32,0));
    assert(OverworldVision_CanSee(&line,0,0,3,-32,0,0));
    assert(!OverworldVision_CanSee(&line,0,0,3,0,33,0));
    assert(!OverworldVision_CanSee(&line,0,0,3,32,0,1));
    puts("until-crash + rearm + generation + 32-tile cardinal sight: PASS");
}
'''


def body(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def walk_fixture():
    movement = (ROOT / "include/overworld_wild_movement.h").read_text()
    declarations = movement[movement.index("typedef struct OverworldWildWalkMomentumState"):
        movement.index("typedef char OverworldActorWalkPolicyCallSizeMustRemain28Bytes")]
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    policy = body(internal, "struct OverworldActorPolicyState {") + ";"
    source = (ROOT / "src/player_health_overlay/overworld_walk_input_policy.c").read_text()
    profile_skid = "static u8 " + body(source, "OverworldWalk_ProfileSkidTiles(")
    reset = "void " + body(source, "OverworldActorWalkPolicy_ResetState(")
    tuning = "static void " + body(source, "OverworldWalkInput_RefreshTuning(")
    crash = "void " + body(source, "OverworldActorWalkPolicy_Crash(")
    reduce = "void " + body(source, "OverworldActorWalkPolicy_ReduceInput(")
    wild = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    no_alert = body(wild, "if (profile->alertTime == 0")
    return r'''
#include "overworld_wild_behavior_data.h"
#include "overworld_walk_timing_policy.h"
#include <assert.h>
#include <stdio.h>
#define OVERWORLD_ACTOR_WORLD_EFFECT_CRASH 3
#define OW_WILD_SPAWNER_BUBBLE_ID_NONE 0
#define OW_WILD_WALK_DIRECTION_NONE 0xff
''' + declarations + "\ntypedef struct OverworldActorPolicyState OverworldActorPolicyState;\n" + policy + r'''
_Static_assert(sizeof(OverworldActorPolicyState)==36,"Policy ABI changed");
static u8 OverworldWalk_ClampTime(u8 t) { return OverworldWalkTimingPolicy_Clamp(t); }
static u8 OverworldWalk_SkidTiles(u8 t) { return OverworldWalkTimingPolicy_SkidTiles(t); }
static u8 OverworldWalk_SkidTime(u8 t) { return OverworldWalkTimingPolicy_SkidTime(t); }
static u8 OverworldWalk_DecelerateTime(u8 t,u8 b,u8 a) { return OverworldWalkTimingPolicy_Decelerate(t,b,a); }
static BOOL OverworldWalk_IsFortyFiveDegreeTurn(u8 a,u8 b) { return (a<4)!=(b<4); }
static void OverworldWalk_ProposeStep(OverworldActorPolicyState *p,
    OverworldActorWalkPolicyCall *c,u8 d,u8 f,u8 t,u8 flags,u8 skid)
{ p->pendingStep=OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL; c->decision=OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP;
  c->stepDirection=d;c->facingDirection=f;c->travelTime=t;c->stepFlags|=flags;(void)skid; }
''' + profile_skid + "\n" + reset + "\n" + tuning + "\n" + crash + "\n" + reduce + r'''
static BOOL no_alert_intent(const OverworldWildBehaviorProfileData *profile)
{ u8 bubbleId=OW_WILD_SPAWNER_BUBBLE_ID_NONE;
''' + no_alert + r'''
return TRUE; }
int main(void)
{
    OverworldWildBehaviorProfileData lane={0};
    OverworldActorPolicyState p={0}, before;
    OverworldActorWalkPolicyCall c={0};
    lane.chillSpeed=32; lane.maxWalkSpeed=2; lane.tilesToAccelerate=180;
    lane.walkAccelerationStep=34;
    p.walkMomentum.direction=3; p.walkMomentum.speed=8;
    p.walkMomentum.baseSpeed=16; p.walkMomentum.turnDirection=7;
    p.bufferedDirection=0xff;p.lastWalkTime=8;p.chainStepsRemaining=5;
    c.lane=&lane;c.direction=3;
    OverworldActorWalkPolicy_ReduceInput(&p,&c);
    assert(c.decision==OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP && c.travelTime<=8);
    assert(p.walkMomentum.direction==3 && p.walkMomentum.turnDirection==7);
    assert(p.chainStepsRemaining==5 && !(c.stepFlags&OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION));
    p.linearElapsed=37;p.linearCarry=55;p.lastWalkTime=8;
    before=p;c=(OverworldActorWalkPolicyCall){.lane=&lane,.direction=3};
    OverworldActorWalkPolicy_ReduceInput(&p,&c);
    assert(p.linearElapsed==before.linearElapsed && p.linearCarry==before.linearCarry);
    p=before;p.walkMomentum.baseSpeed=16;p.linearMode=0;
    p.pendingSkid=1;p.walkMomentum.skidRemaining=2;p.stopPending=1;p.bufferedDirection=0;
    c=(OverworldActorWalkPolicyCall){.lane=&lane,.direction=3};
    OverworldActorWalkPolicy_ReduceInput(&p,&c);
    assert(c.decision==OVERWORLD_ACTOR_WALK_POLICY_CONSUMED);
    assert(p.pendingSkid==1 && p.walkMomentum.skidRemaining==2 && p.stopPending==1 && p.bufferedDirection==0);
    OverworldActorWalkPolicy_Crash(&p,&c,32,0);
    assert(c.effect==OVERWORLD_ACTOR_WORLD_EFFECT_CRASH
        && c.decision==OVERWORLD_ACTOR_WALK_POLICY_CONSUMED
        && (c.stepFlags&OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION));
    assert(p.walkMomentum.direction==OW_WILD_WALK_DIRECTION_NONE
        && p.walkMomentum.speed==32 && p.walkMomentum.baseSpeed==32
        && !p.walkMomentum.skidRemaining && !p.pendingSkid && !p.stopPending
        && !p.linearElapsed && !p.linearCarry && !p.chainStepsRemaining
        && p.bufferedDirection==OW_WILD_WALK_DIRECTION_NONE);
    lane.alertTime=0;assert(!no_alert_intent(&lane));
    puts("same-lane profile momentum + due skid + production Crash reset + zero-alert same-intent: PASS");
}
'''



def heading_fixture():
    from tools.overworld.test_blocked_notice_hop import PRELUDE, SIGNATURES
    from tools.overworld.test_blocked_wild_facing import function_bodies
    bodies = function_bodies()
    signatures = dict(SIGNATURES)
    name = "OverworldWildSpawns_TryStartSpawnerMovementCommand"
    signatures[name] = ("OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot, "
        "const u8 *directions, int directionCount, const OverworldWildBehaviorProfile *profile, "
        "const OverworldWildBehaviorPrimitives *primitives")
    prelude = PRELUDE.replace("#define OverworldWildSpawns_TryStartSpawnerMovementCommand(...) FALSE", "")
    prelude = prelude.replace("#define OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(...) ((void)0)", "")
    prelude = prelude.replace("u8 onReachAction, chillState, throwMaxRange, throwWindupFrames;",
        "u8 onReachAction, chillState, throwMaxRange, throwWindupFrames, chillTarget;")
    prelude = prelude.replace("u8 chaseBoostDistance, chaseBoostSpeed, chillSpeed;",
        "u8 chaseBoostDistance, chaseBoostSpeed, chillSpeed, jumpLevel;")
    prelude = prelude.replace("u8 hopAllowNonCardinal, walkOptions, avoidPreviousTile, wanderStraightChance;",
        "u8 hopAllowNonCardinal, walkOptions, avoidPreviousTile, wanderStraightChance, ramMaxSpeed;")
    prelude = prelude.replace("u8 movementSpotStates[8], movementSpawnRunActive[8], movementCooldowns[8];",
        "u8 movementSpotStates[8], movementSpawnRunActive[8], movementCooldowns[8], movementLastDistances[8], movementLastDirections[8], movementPreviousTileLocked[8]; s16 movementPreviousTileX[8], movementPreviousTileY[8];")
    prelude = prelude.replace("typedef int16_t s16; typedef int BOOL;",
        "typedef int16_t s16; typedef int32_t s32; typedef int BOOL;")
    prelude = prelude.replace("int x, y; u8 facing;",
        "int x, y, xCurr, yCurr; s32 posVec[3]; u8 facing;")
    prelude = prelude.replace("s16 movementCustomJumpTargetX[8], movementCustomJumpTargetY[8];",
        "s16 movementCustomJumpTargetX[8], movementCustomJumpTargetY[8]; s32 movementCustomJumpTargetBaseY[8];")
    prelude = prelude.replace("call->movementTarget==OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER",
        "(call->movementTarget==OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER || call->movementTarget==8)")
    prelude = prelude.replace("call->slot==0", "call->slot<OW_WILD_MAX_SPAWNS")
    prelude = prelude.replace("call->state->spawns[0].object", "call->state->spawns[call->slot].object")
    prelude = prelude.replace("typedef struct OverworldQueryCodeAddonEntry {",
        "typedef struct OverworldThrowHeldWildCall OverworldThrowHeldWildCall;\n"
        "typedef struct OverworldQueryCodeAddonEntry {\n"
        "    BOOL (*throwHeld)(const OverworldThrowHeldWildCall *);")
    prelude = prelude.replace("static const OverworldQueryCodeAddonEntry targetEntry={ReadPlayerTarget};",
        "static BOOL UnexpectedHeld(const OverworldThrowHeldWildCall *call) "
        "{ Check(FALSE, \"Walk fixture entered held Throw\"); return FALSE; }\n"
        "static const OverworldQueryCodeAddonEntry targetEntry={UnexpectedHeld,ReadPlayerTarget};")
    # Throw routes are outside this Walk-only fixture; keep their ABI seams typed.
    prelude += r"""
#define OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST 0
#define OVERWORLD_TARGET_BINDING_CARGO 1
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE 14
typedef struct { int unused; } OverworldPickupRouteWildWorld;
struct OverworldThrowHeldWildCall {
    OverworldPickupRouteWildWorld *world;
    const void *throwService;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    OverworldCargoReadWildTarget *read;
    const void *ops;
    u8 throwTarget,movementTarget,reserved[2];
};
static const int sOverworldWildThrowHeldOps=0;
static void OverworldWildSpawns_InitRouteWorld(
    OverworldWildSpawnState *state,int slot,OverworldPickupRouteWildWorld *world)
{ Check(FALSE,"Walk fixture entered a Throw route"); }
static LocalMapObject *OverworldWildSpawns_GetThrowBindingBody(
    OverworldWildSpawnState *state, int slot, u8 binding, int x, int y)
{ (void)state; (void)slot; (void)binding; (void)x; (void)y; return NULL; }
"""
    native = r"""
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND 4
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION 1
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP 0
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN 1
#define OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE 255
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE 8
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_MOTION_PHASE_CANCELED 7
#define OW_WILD_DIRECTION_STEP_BUSY 0
#define OW_WILD_DIRECTION_STEP_BLOCKED 1
#define OW_WILD_DIRECTION_STEP_STARTED 2
typedef int OverworldWildDirectionStepResult;
typedef struct { u8 direction,speed,skidRemaining; } Momentum;
typedef struct { u8 motionPhase; Momentum walkMomentum; } OverworldActorPolicyView;
typedef struct { OverworldWildSpawnState *state; FieldSystem *fieldSystem; LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile; const OverworldWildBehaviorPrimitives *primitives;
    u8 slot,jumpLevel,avoidPreviousTile;u16 allowedTile; } OverworldWildDirectionStepContext;
static u8 heading=3,expectedHeading=3,speed=4;
static int starts,crashes,block;
static BOOL OverworldActorPolicy_Inspect(u8 slot,OverworldActorPolicyView *p)
{*p=(OverworldActorPolicyView){.walkMomentum={.direction=heading,.speed=speed}};return TRUE;}
static u8 OverworldWildSpawns_GetCurrentMovementTarget(const OverworldWildBehaviorPrimitives *p,u8 spot) { return p->chillTarget; }
#define OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(...) ((void)0)
#define OverworldWildSpawns_TryApplyPlayerCollisionAttack(...) ((void)0)
#define OverworldWildSpawns_TryStartBlockedWalkStopSkid(...) FALSE
static int Choose(const u8 *d,int n,u8 last,u8 chance){return 0;}
static const struct {int(*chooseWanderDirection)(const u8 *,int,u8,u8);} inner={Choose};
static const struct {const void *unused;} unused;
static const struct {const typeof(inner)*policy;} movementEntry={&inner};
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&movementEntry)
static int OverworldWildSpawns_TryStartSingleDirectionMovementStep(OverworldWildDirectionStepContext *c,const OverworldActorPolicyView *p,u8 direction,BOOL continuation)
{Check(direction==expectedHeading,"charge or backtrack control chose wrong heading");starts++;return block?OW_WILD_DIRECTION_STEP_BLOCKED:OW_WILD_DIRECTION_STEP_STARTED;}
static BOOL OverworldWildSpawns_HandleLockedWalkCrash(const OverworldWildDirectionStepContext *c,u8 direction)
{Check(direction==expectedHeading,"blocked charge crashed in wrong direction");crashes++;return TRUE;}
"""
    native += "static u8 OverworldWildSpawns_GetCommittedWalkDirection(const OverworldActorPolicyView *policy) {\n" + bodies["OverworldWildSpawns_GetCommittedWalkDirection"] + "\n}\n"
    for name, result, signature in (
        ("OverworldWildSpawns_ShouldAvoidPreviousTileForResolvedProfile", "BOOL",
            "OverworldWildSpawnState *state, int slot, const OverworldWildBehaviorProfile *profile"),
        ("OverworldWildSpawns_IsPreviousTileLockedAt", "BOOL",
            "OverworldWildSpawnState *state, int slot, int x, int y"),
        ("OverworldWildSpawns_IsAvoidedBacktrackStep", "BOOL",
            "OverworldWildSpawnState *state, int slot, LocalMapObject *object, u8 direction, int distance, BOOL avoidPreviousTile"),
        ("OverworldWildSpawns_AddChaseFallbackDirection", "void",
            "u8 *directions, int *directionCount, u8 direction"),
        ("OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections", "void",
            "u8 *directions, int *directionCount"),
    ):
        native += f"static {result} {name}({signature}) {{\n{bodies[name]}\n}}\n"
    prototypes = "\n".join(f"static BOOL {name}({signature});" for name, signature in signatures.items())
    functions = "\n".join(f"static BOOL {name}({signature})\n{{{bodies[name]}\n}}"
        for name, signature in signatures.items())
    driver = r"""
int main(void) {
    LocalMapObject object={.x=584,.y=398},player={.x=580,.y=398};
    FieldSystem field={.playerAvatar=&player};
    OverworldWildSpawnState state={.movementFieldSystem=&field};
    OverworldWildBehaviorProfile profile={.owner={.walkOptions=1,.hopAllowNonCardinal=1}};
    OverworldWildBehaviorPrimitives primitives={.chillTarget=OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE,
        .chillLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_WANDER};
    activeConditions=1;state.spawns[0].active=TRUE;state.spawns[0].object=&object;
    const int positions[3][2]={{580,398},{584,405},{584,398}};
    for(int i=0;i<3;i++) {
        player.x=positions[i][0];player.y=positions[i][1];
        Check(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&object,&profile,&primitives),
            "locked active charge stopped when player moved behind/off-axis/on tile");
    }
    Check(starts==3 && crashes==0,"continuation did not reach exactly one native step per intent");
    block=1;
    Check(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&object,&profile,&primitives),
        "blocked charge missed normal Crash seam");
    Check(starts==4 && crashes==1,"blocked heading did not reach exactly one Crash adoption");
    /* Measured follower start: its target is North through its previous tile.
     * No accepted Ram step has committed a heading yet. Ordinary pursuit must
     * keep its backtrack policy; a locked charge must try North immediately. */
    object.x=594;object.y=398;player.x=594;player.y=394;
    state.spawns[7].active=TRUE;state.spawns[7].object=&object;
    state.movementPreviousTileLocked[7]=1;
    state.movementPreviousTileX[7]=594;state.movementPreviousTileY[7]=397;
    profile.chillState=OW_WILD_BEHAVIOR_KIND_CHASE;
    profile.chillTarget=OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE;
    heading=OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE;speed=0;expectedHeading=0;block=0;
    Check(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,7,&object,&profile,&primitives),
        "first locked follower step through previous tile stopped");
    Check(starts==5 && crashes==1,"first locked follower step selected a fallback");
    block=1;
    Check(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,7,&object,&profile,&primitives),
        "first blocked locked follower step missed Crash");
    Check(starts==6 && crashes==2,"first blocked locked follower step did not adopt one Crash");
    profile.owner.walkOptions=0;expectedHeading=2;block=0;
    Check(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,7,&object,&profile,&primitives),
        "unlocked pursuit stopped instead of avoiding previous tile");
    Check(starts==7 && crashes==2,"unlocked pursuit lost its previous-tile fallback");
    puts("production dispatch: committed heading + first previous-tile charge + blocked Crash + unlocked backtrack control: PASS");
    return 0;
}
"""
    return prelude + native + prototypes + functions + driver

def main():
    flags = ["clang", "-Wno-unknown-attributes", "-Wno-macro-redefined",
        "-Wno-pointer-to-int-cast", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
        "-DOVERWORLD_BEHAVIOR_HOST", "-I", str(ROOT / "include")]
    with tempfile.TemporaryDirectory(prefix="ow-until-crash-") as directory:
        temporary = Path(directory)
        for name, source, libraries in (
            ("condition", CONDITION_FIXTURE, ["overworld_behavior_conditions.c",
                "overworld_behavior_condition_runtime.c", "overworld_target_bindings.c",
                "overworld_pickup_route.c", "overworld_vision.c"]),
            ("walk", walk_fixture(), []),
            ("heading", heading_fixture(), []),
        ):
            fixture = temporary / f"{name}.c"
            binary = temporary / name
            fixture.write_text(source)
            subprocess.run(flags + [str(fixture)] +
                [str(ROOT / "lib/overworld" / library) for library in libraries] +
                ["-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
            if name == "heading":
                control = source.replace("avoidPreviousTile = !lockDirection\n        &&",
                    "avoidPreviousTile =", 1)
                if control == source:
                    raise SystemExit("first-charge prior-tile negative control was not applied")
                fixture.write_text(control)
                subprocess.run(flags + [str(fixture), "-o", str(binary)], check=True)
                result = subprocess.run([str(binary)], capture_output=True, text=True)
                if result.returncode != 1 or result.stderr.strip() != "charge or backtrack control chose wrong heading":
                    raise SystemExit("first-charge prior-tile negative control did not reject the old heading")
                print("first-charge prior-tile negative control rejects old fallback heading: PASS")


if __name__ == "__main__":
    main()
