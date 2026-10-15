#!/usr/bin/env python3
"""Actual Wild read callback/scheduling and bounded Cargo reducer controls.

Native frame/admission callbacks are stand-ins. The cadence control uses the
unchanged production Cargo/Route/Native reducers and the exact moving branch.
This is host evidence; the same-ROM Wild Throw game case remains required.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


extract = module("warm_extract", "scripts/verify_overworld_spawn_profile_lifecycle.py")
cargo = module("warm_cargo", "scripts/verify_overworld_cargo_query.py")


def moving_branch(source):
    tick = extract.production_function(source, "OverworldWildSpawns_TickMovementParams", "void")
    if "landing pause. Accepted motion" in tick:
        start = tick.index("if (frameTick", tick.index("landing pause. Accepted motion"))
    else:
        start = tick.index("if (frameTick) {", tick.index("if (OverworldWildSpawns_IsMovementSlotInProgress"))
    depth, end = 1, tick.index("{", start) + 1
    while depth:
        depth += (tick[end] == "{") - (tick[end] == "}")
        end += 1
    return tick[start:end]


PREFIX = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOTION_PHASE_SETTLING 4
#define OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO 1u
typedef struct { u8 motionPhase; } OverworldActorPolicyView;
#define OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST 0
#define OVERWORLD_TARGET_BINDING_BOUND 1
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG 128
#define OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG 64
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildBehaviorProfile { int unused; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { int unused; } OverworldWildBehaviorPrimitives;
typedef struct OverworldWildBehaviorDataBlob { int unused; } OverworldWildBehaviorDataBlob;
typedef struct OverworldWildBehaviorConditionRuntime {
 struct { struct { u8 flags; } bindings[2]; } bindings[10];
 struct { struct { u32 frame;u8 reservedBinding; } world;unsigned valid; } frame;
} OverworldWildBehaviorConditionRuntime;
typedef struct OverworldWildOverlayRuntimeState {
 OverworldWildBehaviorConditionRuntime *conditions;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
 FieldSystem *movementFieldSystem; u16 movementInProgressMask;
 u8 movementActorControlModes[10], movementSpawnRunActive[10];
 OverworldWildOverlayRuntimeState runtime;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(s) (&(s)->runtime)
typedef struct OverworldPickupRouteWildWorld {
 OverworldWildSpawnState *state; u8 slot; const OverworldWildBehaviorDataBlob *behaviorData;
} OverworldPickupRouteWildWorld;
typedef struct OverworldCargoReadWildObservationCall {
 struct { OverworldPickupRouteWildWorld *world; const OverworldWildBehaviorProfile *profile; } cargo;
 const OverworldWildBehaviorConditionRuntime *conditions;
 const void *throwService;
 BOOL (*isCurrentSpawn)(FieldSystem *,const void *);
 BOOL (*queryTarget)(void);
} OverworldCargoReadWildObservationCall;
typedef struct OverworldQueryCodeAddonEntry {
 const void *(*cargoReadOptions)(const OverworldPickupRouteWildWorld *);
 u32 (*cargoReadObserve)(const OverworldCargoReadWildObservationCall *,BOOL *);
} OverworldQueryCodeAddonEntry;
static unsigned ready, admitted, reachableOptions, subjectCurrent, lost, frame, completedFrame;
static u8 warmPhase,warmKnown=1;
static unsigned builds, observations, nativeUnits, aborts, lastNativeFrame;
static OverworldWildBehaviorConditionRuntime conditions;
static OverworldWildSpawnState actor;
static FieldSystem field;
static OverworldWildBehaviorProfile profile;
static OverworldWildBehaviorDataBlob blob;
static int service;
#define PLAYER_HEALTH_THROW_SERVICE_ENTRY (&service)
static BOOL PlayerHealthThrowService_IsReady(void) { return ready; }
static BOOL OverworldWildSpawns_IsMovementSlotInProgress(OverworldWildSpawnState *s,int slot)
 { return (s->movementInProgressMask & (1u<<slot))!=0; }
static BOOL OverworldActorPolicy_Inspect(u8 slot,OverworldActorPolicyView *view)
 { assert(slot==0);view->motionPhase=warmPhase;return warmKnown; }
static void OverworldWildSpawns_BuildBehaviorContext(void) {}
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f,const void *s)
 { (void)f;(void)s;return subjectCurrent; }
static BOOL OverworldWildSpawns_QueryPickupThrowTarget(void) { return TRUE; }
static BOOL OverworldBehaviorConditionAdapter_BuildFrame(OverworldWildSpawnState *s,FieldSystem *f,
 OverworldWildBehaviorConditionRuntime *c,void (*builder)(void),BOOL (*current)(FieldSystem *,const void *))
 { assert(s==&actor && f==&field && c==actor.runtime.conditions);
   assert(builder==OverworldWildSpawns_BuildBehaviorContext && current==OverworldWildSpawns_IsCurrentSpawnObject);
   ++builds;c->frame.world.frame=completedFrame;
   c->frame.world.reservedBinding=0;c->frame.valid=subjectCurrent;return subjectCurrent; }
static void OverworldWildSpawns_InitCargoReadCall(OverworldWildSpawnState *s,u8 slot,
 const OverworldWildBehaviorProfile *p,OverworldPickupRouteWildWorld *w,void *raw)
 { OverworldCargoReadWildObservationCall *c=raw;memset(c,0,sizeof(c->cargo));
   w->state=s;w->slot=slot;c->cargo.world=w;c->cargo.profile=p; }
static const void *Options(const OverworldPickupRouteWildWorld *w)
 { assert(w->state==&actor && w->behaviorData==&blob);return reachableOptions?&service:NULL; }
static u32 Observe(const OverworldCargoReadWildObservationCall *c,BOOL *needAbort)
 { assert(c->conditions==&conditions && c->throwService==&service);++observations;
   *needAbort=lost;
   if(!lost && lastNativeFrame!=frame) { ++nativeUnits;lastNativeFrame=frame; }
   return lost?0:1; }
static const OverworldQueryCodeAddonEntry entry={Options,Observe};
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem *f,const void *t)
 { assert(f==&field && t==NULL);return admitted?&entry:NULL; }
static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void) { return &blob; }
static void OverworldWildSpawns_AbortThrow(OverworldWildSpawnState *s,int slot)
 { (void)slot;++aborts;s->movementInProgressMask=0; }
static void Reset(void)
 { memset(&actor,0,sizeof(actor));memset(&conditions,0,sizeof(conditions));
   actor.movementFieldSystem=&field;actor.runtime.conditions=&conditions;actor.movementInProgressMask=1;
   conditions.bindings[0].bindings[0].flags=1;
   ready=admitted=reachableOptions=subjectCurrent=1;lost=frame=builds=observations=nativeUnits=aborts=0;
   lastNativeFrame=~0u;warmPhase=0;warmKnown=1; }
'''

# The adapter's actual warm admission is checked by test_behavior_condition_adapter.
# This stand-in keeps the exact Tick branch and production observation callback.
WARM_EVALUATION = r'''
static u16 OverworldWildSpawns_EvaluateConditionsForSlot(
 OverworldWildSpawnState *state,FieldSystem *fieldSystem,int slot,
 OverworldWildBehaviorProfile *profileOut,OverworldWildBehaviorPrimitives *primitivesOut)
 { assert(state==&actor && fieldSystem==&field && slot==0 && profileOut==&profile);
   assert(primitivesOut==NULL);
   /* Model the upstream adapter frame SDK seam, then its exact synchronous
    * mode. A stale SDK sample also exercises the callback's current guard. */
   OverworldWildBehaviorConditionRuntime *current=state->runtime.conditions;
   (void)OverworldBehaviorConditionAdapter_BuildFrame(state,fieldSystem,current,
       OverworldWildSpawns_BuildBehaviorContext,OverworldWildSpawns_IsCurrentSpawnObject);
   current->frame.world.reservedBinding=OVERWORLD_BEHAVIOR_CONDITION_EVALUATE_WARM_CARGO;
   u16 result=(u16)OverworldWildSpawns_GetInteractionObservation(
    state,slot,profileOut,&blob,current);
   current->frame.world.reservedBinding=0;
   return result; }
'''


DRIVER = r'''
static void TickAccepted(u8 throwTarget)
 { OverworldWildSpawnState *state=&actor;OverworldWildOverlayRuntimeState *runtime=&actor.runtime;
   int i=0;BOOL frameTick=TRUE;FieldSystem *fieldSystem=&field;
   OverworldActorPolicyView policy;BOOL actorPolicyKnown=OverworldActorPolicy_Inspect(0,&policy);
   BOOL movementInProgress=OverworldWildSpawns_IsMovementSlotInProgress(state,i);
   BOOL actorMotionOwnsFacing=actorPolicyKnown && policy.motionPhase>0 && policy.motionPhase<5;
   completedFrame=frame;
   do { /* @BRANCH@ */ } while(0);
   assert(conditions.frame.world.reservedBinding==0); }
int main(void)
 {
  Reset();for(frame=0;frame<80;frame++)TickAccepted(0);
  assert(builds==80 && observations==80 && nativeUnits==80 && !aborts && actor.movementInProgressMask==1);
  /* A second read on this exact frame cannot spend a second native unit. */
  frame--;TickAccepted(0);assert(nativeUnits==80);
  /* All five authored settle frames may advance the same bounded query.
   * A lost binding still cannot clear accepted motion before idle. */
  Reset();actor.movementInProgressMask=0;warmPhase=OVERWORLD_MOTION_PHASE_SETTLING;
  for(frame=0;frame<5;frame++)TickAccepted(0);
  assert(builds==5 && observations==5 && nativeUnits==5 && !aborts);
  lost=1;TickAccepted(0);assert(!aborts);
  warmPhase=0;TickAccepted(0);assert(!aborts); /* idle scheduling does no warm read */
  (void)OverworldWildSpawns_GetInteractionObservation(&actor,0,&profile,&blob,&conditions);assert(aborts==1);
  Reset();lost=1;TickAccepted(0);assert(observations==1 && !aborts && actor.movementInProgressMask==1);
  actor.movementInProgressMask=0;
  (void)OverworldWildSpawns_GetInteractionObservation(&actor,0,&profile,&blob,&conditions);
  assert(aborts==1);
  for(unsigned gate=0;gate<9;gate++) {
   Reset();
   if(gate==0)actor.runtime.conditions=NULL;
   if(gate==1)conditions.bindings[0].bindings[0].flags=0;
   if(gate==2)actor.movementActorControlModes[0]=OW_WILD_ACTOR_CONTROL_HELD;
   if(gate==3)actor.movementSpawnRunActive[0]=1;
   if(gate==4)ready=0;
   if(gate==5)admitted=0;
   if(gate==6)reachableOptions=0;
   if(gate==7)subjectCurrent=0;
   TickAccepted(gate==8?OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG:0);
   assert(!observations && !nativeUnits && !aborts && actor.movementInProgressMask==1);
   if(gate<4 || gate==8)assert(!builds);else assert(builds==1);
  }
  Reset();TickAccepted(OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG);assert(!builds && !observations);
  puts("PASS accepted-frame service, authored options, current frame, held/startup/loss/admission guards");
  return 0;
 }
'''


CADENCE = r'''
#include <assert.h>
#include "overworld_target_bindings.h"
#define TRUE 1
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG 128
#define OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG 64
typedef int BOOL;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildBehaviorProfile { int unused; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { int unused; } OverworldWildBehaviorPrimitives;
static FieldSystem cadenceField;
static OverworldWildBehaviorProfile profile;
struct WarmConditions { OverworldTargetBindingsState bindings[10]; } warmConditions;
struct WarmRuntime { struct WarmConditions *conditions; } warmRuntime;
struct WarmActor { u8 movementActorControlModes[10], movementSpawnRunActive[10]; } warmActor;
static unsigned cadenceCalls;
#define OVERWORLD_MOTION_PHASE_SETTLING 4
static BOOL OverworldWildSpawns_IsMovementSlotInProgress(struct WarmActor *s,int slot)
 { (void)s;(void)slot;return TRUE; }
static u32 WarmQuery(void) { ++cadenceCalls;assert(!Tick());return 0; }
#define OverworldWildSpawns_GetInteractionObservation(...) WarmQuery()
static u16 OverworldWildSpawns_EvaluateConditionsForSlot(
 struct WarmActor *state,FieldSystem *fieldSystem,int slot,
 OverworldWildBehaviorProfile *profileOut,OverworldWildBehaviorPrimitives *primitivesOut)
 { assert(state==&warmActor && fieldSystem==&cadenceField && slot==0 && profileOut==&profile);
   assert(primitivesOut==NULL);
   return (u16)OverworldWildSpawns_GetInteractionObservation(
    state,slot,profileOut,NULL,warmRuntime.conditions); }
static int Cadence(void) {
 Setup(24,3,23,1);warmRuntime.conditions=&warmConditions;
 warmConditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags=OVERWORLD_TARGET_BINDING_BOUND;
 struct WarmActor *state=&warmActor;struct WarmRuntime *runtime=&warmRuntime;
 int i=0;BOOL frameTick=TRUE;u8 throwTarget=0;unsigned gameFrame;
 BOOL actorPolicyKnown=TRUE;struct { u8 motionPhase; } policy={2};
 BOOL movementInProgress=OverworldWildSpawns_IsMovementSlotInProgress(state,i);
 BOOL actorMotionOwnsFacing=TRUE;
 FieldSystem *fieldSystem=&cadenceField;
 for(gameFrame=0;gameFrame<500;gameFrame++) {
  bindingsWorld.frame=gameFrame;
  if(gameFrame%16==0) {
   changes[0]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[0].x,1};
   world.body[1][bindingsWorld.actors[0].x]=0;
   bindingsWorld.actors[0].x=(s16)(22+((gameFrame/16)&1));world.body[1][bindingsWorld.actors[0].x]=1;
   changes[1]=(OverworldCargoQueryChangedTile){bindingsWorld.actors[0].x,1};input.changedTileCount=2;
   query.origin.x=(s16)((gameFrame/16)&1);bindingsWorld.subjectX=query.origin.x;++query.dynamicRevision;
   ++cadenceCalls;assert(!Tick());
  } else { do { /* @BRANCH@ */ }while(0); }
  if(output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE)break;
  assert(output.status==OVERWORLD_PICKUP_ROUTE_PENDING);
 }
 printf("actual Cargo cadence: completed gameFrame%u queryCalls%u nodes%u status%u\n",
  gameFrame,cadenceCalls,scheduler.route.nodeCount,output.status);
 assert(gameFrame<500 && output.status==OVERWORLD_PICKUP_ROUTE_REACHABLE);
 assert(output.route.hasNextStep && (output.route.nextStep.x!=query.origin.x || output.route.nextStep.y!=query.origin.y));
 assert(output.route.origin.x==query.origin.x && output.route.cargoPosition.x==bindingsWorld.actors[0].x);
 return 0;
}
int main(void) { return Cadence(); }
'''


def compile_run(directory, name, unit, sources=()):
    source, binary = directory / (name + ".c"), directory / name
    source.write_text(unit)
    command = ["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-Wno-unused-variable", "-Wno-unused-function", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
               "-I", str(ROOT / "include"), *map(str, sources), str(source), "-o", str(binary)]
    subprocess.run(command, check=True)
    return subprocess.run([str(binary)], capture_output=True, text=True)


def cadence_unit(source):
    prelude = cargo.PRELUDE.replace("q->cargo.encounterGeneration!=7", "(q->cargo.encounterGeneration!=7 && q->cargo.encounterGeneration!=8)")
    prelude = prelude.replace("unsigned calls,supportCalls,hopSamples", "int oneWay;unsigned calls,supportCalls,hopSamples")
    prelude = prelude[:prelude.index("static Result Classify(")].replace("static unsigned callsBefore;\n", "")
    return prelude + cargo.HARNESS[:cargo.HARNESS.index("static int Finish(")] + CADENCE.replace("/* @BRANCH@ */", moving_branch(source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, help="retain old accepted-motion cadence RED")
    args = parser.parse_args()
    source = SOURCE.read_text()
    observation = extract.production_function(source, "OverworldWildSpawns_GetInteractionObservation", "u32")
    query_sources = [ROOT / ("lib/overworld/" + file) for file in (
        "overworld_cargo_query.c", "overworld_pickup_route_native.c", "overworld_pickup_route.c")]
    with tempfile.TemporaryDirectory(prefix="wild-cargo-warm-") as temporary:
        directory = Path(temporary)
        current = compile_run(directory, "warm", PREFIX + observation + WARM_EVALUATION + DRIVER.replace("/* @BRANCH@ */", moving_branch(source)))
        if current.returncode:
            raise SystemExit(current.stdout + current.stderr)
        print(current.stdout.strip())
        current = compile_run(directory, "cadence", cadence_unit(source), query_sources)
        print(current.stdout.strip())
        if current.returncode:
            raise SystemExit(current.stderr)
        if args.before:
            before = compile_run(directory, "before", cadence_unit(args.before.read_text()), query_sources)
            if not before.returncode:
                raise SystemExit("old sparse accepted-motion cadence unexpectedly passed")
            print("RED old cadence rejected:", before.stderr.strip())
        for name, old, new in (
            ("moving abort", "if(needAbort && !moving)", "if(needAbort)"),
            ("authored Cargo option", "entry->cargoReadOptions(&world)==NULL", "FALSE"),
            ("current frame", "!conditions->frame.valid", "FALSE"),
        ):
            assert source.count(old) == 1, name
            changed = source.replace(old, new, 1)
            unit = PREFIX + extract.production_function(changed, "OverworldWildSpawns_GetInteractionObservation", "u32") + WARM_EVALUATION + DRIVER.replace("/* @BRANCH@ */", moving_branch(changed))
            mutant = compile_run(directory, name.replace(" ", "-"), unit)
            if not mutant.returncode:
                raise SystemExit("missing guard accepted: " + name)
            print("rejected missing guard:", name)


if __name__ == "__main__":
    main()
