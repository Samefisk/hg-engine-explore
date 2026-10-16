"""Actual-C Throw cleanup and claimant selection.

Engine reads and START are host seams. Native ABI and game motion need the
registered game proof. These cases join existing production owners.
"""
from pathlib import Path
import os
import shlex
import subprocess
import unittest
import re

from tools.overworld.test_picked_up_actor_control import extract_function

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "build/tickets/tkt11-abort-composition-host"
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
HELPER = ROOT / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c"
READ = ROOT / "lib/overworld/overworld_cargo_read_wild.c"
OBSERVE = ROOT / "lib/overworld/overworld_throw_observation_native.c"
QUERY_OBSERVE = ROOT / "lib/overworld/overworld_throw_observation_query.c"
HELD = ROOT / "lib/overworld/overworld_throw_held_wild.c"


def functions(path, specs):
    source = path.read_text()
    return "\n".join(extract_function(source, name, returns) for name, returns in specs)


def fixture():
    chunks = [
        PRELUDE,
        functions(HELPER, [("OverworldWildHelper_ClearPickupThrowState", "u16")]),
        functions(WILD, [("OverworldWildSpawns_ClearPendingNotices", "void")]),
        functions(WILD, [("OverworldWildSpawns_ReleaseHeldActorControl", "void")]),
        functions(READ, [("OverworldCargoReadWild_Options", "const OverworldWildBehaviorConditionOptions *")]),
        functions(WILD, [("OverworldWildSpawns_PickupOptions", "const OverworldWildBehaviorConditionOptions *"),
                         ("OverworldWildSpawns_RetireClearedThrowBindings", "void"),
                         ("OverworldWildSpawns_ClearThrowRelations", "void"),
                         ("OverworldWildSpawns_ClearThrowStateForSlot", "void"),
                         ("OverworldWildSpawns_AbortThrow", "void"),
                         ("OverworldWildSpawns_PrepareCarrierHit", "void")]),
        functions(QUERY_OBSERVE, [("PlayerHealthThrow_Line", "BOOL"), ("OverworldThrowObservationQuery_Observe", "u32")]),
        functions(OBSERVE, [("OverworldThrowObservation_Observe", "u32")]),
        functions(HELD, [("OverworldThrowHeldWild_ReleaseCargo", "BOOL")]).replace(
            "static BOOL OverworldThrowHeldWild_ReleaseCargo(",
            "BOOL OverworldThrowHeldWild_ReleaseCargo("),
        functions(READ, [("OverworldCargoReadWild_Observe", "u32"),
                        ("OverworldCargoReadWild_Target", "u8")]),
        functions(HELD, [("OverworldThrowHeldWild_Run", "BOOL")]).replace("static BOOL OverworldThrowHeldWild_Run(", "BOOL OverworldThrowHeldWild_Run("),
        functions(WILD, [("OverworldWildSpawns_IsMovementSlotInProgress", "BOOL"),
                         ("OverworldWildSpawns_GetInteractionObservation", "u32"),
                         ("OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand", "BOOL")]),
        DRIVER,
    ]
    return "\n".join(chunks)


def run(source, stem, runtime_path=None):
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "host_types.h").write_text(HOST_TYPES)
    unit, binary = HERE / (stem + ".c"), HERE / stem
    geometry = functions(
        ROOT / "src/pokemon_move_history_overlay/overworld_hop_geometry.c",
        [("OverworldActorHopGeometry_NextCell", "void")],
    ).replace("static void ", "void ", 1)
    source = ('#include "overworld_motion_model.h"\n'
              '#include "overworld_actor_hop_geometry.h"\n' + geometry + "\n" + source)
    unit.write_text(source)
    command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=gnu11", "-O2",
               "-Wall", "-Wextra", "-Werror", "-Wno-unused-function", "-Wno-pointer-to-int-cast",
               "-DOVERWORLD_BEHAVIOR_HOST", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
               "-DOVERWORLD_MOTION_HOST",
               "-include", str(HERE / "host_types.h"), "-I", str(ROOT / "include"),
               "-I", str(ROOT / "src/pokemon_move_history_task6_overlay"),
               "-iquote", str(ROOT / "lib/overworld"), str(unit),
               str(ROOT / "lib/overworld/overworld_behavior_conditions.c"),
               str(ROOT / "lib/overworld/overworld_vision.c"),
               str(runtime_path or ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"),
               str(ROOT / "lib/overworld/overworld_target_bindings.c"),
               str(ROOT / "lib/overworld/overworld_pickup_route.c"),
               str(ROOT / "lib/overworld/overworld_motion_model.c"),
               str(ROOT / "data/OverworldWildBehaviorData.c"), "-o", str(binary)]
    compiled = subprocess.run(command, text=True, capture_output=True)
    (HERE / (stem + "-compile.log")).write_text(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise AssertionError(compiled.stderr)
    result = subprocess.run([str(binary)], text=True, capture_output=True)
    (HERE / (stem + "-run.log")).write_text(result.stdout + result.stderr)
    return result


class ThrowFailureCompositionTests(unittest.TestCase):
    def test_abort_retires_bound_notice_and_allows_one_fresh_capture(self):
        source = fixture().split("int main(void) {", 1)[0] + NOTICE_ABORT_DRIVER
        result = run(source, "throw-notice-abort")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_notice_retirement_keeps_the_reproduced_failure(self):
        source = fixture().split("int main(void) {", 1)[0] + NOTICE_ABORT_DRIVER
        seam = "OverworldWildSpawns_RetireClearedThrowBindings(runtime->conditions, i);"
        self.assertEqual(source.count(seam), 1)
        result = run(source.replace(seam, "/* regression: stale active notice */"),
                     "throw-notice-abort-without-retirement")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE", result.stderr)

    def test_actual_loss_expiry_failed_start_cleanup_retry_and_new_cargo(self):
        result = run(fixture(), "throw-composition")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_held_search_has_no_time_expiry_and_keeps_identity_cleanup(self):
        result = run(held_lifetime_fixture(), "held-search-lifetime")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_finite_held_search_definition_is_rejected(self):
        source = held_lifetime_fixture()
        seam = "assert(held->activationMode==OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE && held->durationFrames==0 && held->cooldownFrames==0);"
        self.assertEqual(source.count(seam), 1)
        source = source.replace(seam, "blob->conditionEntries[heldIndex].activationMode=OVERWORLD_BEHAVIOR_CONDITION_TIMED;blob->conditionEntries[heldIndex].durationFrames=60;blob->conditionEntries[heldIndex].cooldownFrames=120;")
        result = run(source, "held-search-finite-expiry-fault")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OverworldBehaviorCondition_EvaluatePrepared", result.stderr)

    def test_missing_composed_cleanup_is_rejected(self):
        source = fixture()
        seam = "OverworldWildSpawns_ClearThrowRelations(state,slot,FALSE);"
        self.assertEqual(source.count(seam), 1)
        result = run(source.replace(seam, "/* fault: dropped owner cleanup */"), "throw-composition-fault")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("runtime.throwState.targets[0]==0", result.stderr)

    def test_actual_claimant_beats_nearer_non_claimant(self):
        source = fixture().split("static OverworldWildSpawnState state;", 1)[0]
        source += PURSUER_DRIVER
        result = run(source, "throw-pursuer")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_claimant_filter_is_rejected(self):
        source = fixture().split("static OverworldWildSpawnState state;", 1)[0]
        source += PURSUER_DRIVER
        runtime = ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"
        current = runtime.read_text()
        seam = """|| ((definition.terrainMask
                            & OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP)"""
        self.assertEqual(current.count(seam), 1)
        HERE.mkdir(parents=True, exist_ok=True)
        mutant = HERE / "condition-runtime-no-claim-filter.c"
        mutant.write_text(current.replace(seam, "|| ((0 & OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP)"))
        # The production file uses relative includes. Preserve its include
        # home through the existing -iquote search rather than changing C.
        result = run(source, "throw-pursuer-fault", mutant)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("result.resolvedTarget.actor.slot==7", result.stderr)




HOST_TYPES = r"""
#include <string.h>
/* The stock types.h declares ARM-only long_call imports. This host boundary
 * supplies the same scalar widths, not engine imports or guest layouts. */
#include <stdint.h>
#include <stddef.h>
#ifdef __clang__
#pragma clang diagnostic ignored "-Wunknown-attributes"
#endif
#define TYPES_H
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint64_t u64;
typedef int8_t s8;typedef int16_t s16;typedef int32_t s32;typedef int64_t s64;
typedef int BOOL;typedef s32 fx32;
typedef struct { fx32 x,y,z; } VecFx32;
#define TRUE 1
#define FALSE 0
#define ALIGN4 __attribute__((aligned(4)))
#define PACKED __attribute__((packed))
#define LONG_CALL
#define NELEMS(a) (sizeof(a)/sizeof((a)[0]))
"""


HOST_ACTOR_ROLE_STATE = r"""
/* Public snapshots are real types. Acquisition and the enclosing native
 * container are host seams; no ARM pointer layout is claimed. */
typedef struct OverworldActorSystemState {
    struct { OverworldActorStateSnapshot snapshot; } slots[10];
} OverworldActorSystemState;
static OverworldActorSystemState roleState;
static BOOL roleStateReady=TRUE;
static const OverworldActorSystemState *ActorState(void) { return roleStateReady?&roleState:NULL; }
static const OverworldPickupRouteWildOps roleOps={.actorState=ActorState};

"""


PRELUDE = r"""
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "overworld_behavior_condition_runtime.h"
#include "overworld_target_bindings.h"
#include "overworld_cargo_query.h"
#include "overworld_cargo_query_wild.h"
#include "overworld_throw_away_wild.h"

/* Host-width engine structs expose only named fields used by the extracted
 * functions. No ARM layout claim is made here. Portable value types and all
 * binding/condition reducers are the real production headers and C. */
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_ACTOR_CONTROL_AUTONOMOUS 0
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_HELPER_THROW_TARGET_NONE 0
#define OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG 0x80
#define OW_WILD_HELPER_THROW_TARGET_SLOT_MASK 0x3F
#define OW_WILD_HELPER_THROW_TARGET_ENCODE(slot) ((u8)((slot)+1))
#define OW_WILD_HELPER_THROW_TARGET_DECODE(value) ((u8)(((value)&0x3F)-1))
#define OW_WILD_SPAWNER_THROW_TARGET_NONE OW_WILD_HELPER_THROW_TARGET_NONE
#define OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG 0x80
#define OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG 0x40
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
#define OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS 4
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_SPAWN_ENTRY_MOVE 1
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_ELIGIBLE 3
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID 0
#define OW_WILD_HELPER_HOP_PLAN_FLEE 2
#define OW_WILD_HELPER_HOP_PLAN_DIRECT 0
#define OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY 1
#define OW_WILD_HELPER_DIRECTION_LEFT 2
#define OW_WILD_HELPER_PRESENTATION_NORMALIZE_SLOT 0
#define PLAYER_HEALTH_THROW_SLOT_MASK(slot) (1u << (slot))
#define PLAYER_HEALTH_THROW_RUNTIME(state) ((state)->movementRuntimeState)
#define PLAYER_HEALTH_THROW_WINDUP_FLAG 0x40
#define PLAYER_HEALTH_MOTION_CANCEL 4
#define PLAYER_HEALTH_THROW_LAUNCH 1
#define PLAYER_HEALTH_EVENT_CODE(slot,event) (((slot)<<8)|(event))
#define OW_WILD_BEHAVIOR_TARGET_NONE 0
#define OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY 1
#define OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER 2
#define OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER 3
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_KIND_CHASE 3

typedef struct LocalMapObject { int xCurr,yCurr; u32 posVec[3]; } LocalMapObject;
typedef struct OverworldWildSpawn { LocalMapObject *object; u8 active; u16 encounterGeneration; } OverworldWildSpawn;
typedef struct OverworldWildThrowState { u8 targets[10]; u16 targetMask,carrierMask,recoveringMask; } OverworldWildThrowState;
typedef struct OverworldWildPresentationState { u8 farSamples[10]; s16 lastKnownX[10],lastKnownY[10]; } OverworldWildPresentationState;
typedef struct OverworldWildBehaviorConditionRuntime {
    struct { OverworldBehaviorConditionWorldView world;
        OverworldBehaviorConditionCandidate candidates[10]; u8 valid; } frame;
    OverworldBehaviorConditionPreparedActor actors[10];
    OverworldTargetBindingsState bindings[10];
    u16 targetValidMask; s16 targetX[10],targetY[10];
} OverworldWildBehaviorConditionRuntime;
typedef struct OverworldWildOverlayRuntimeState {
    OverworldWildThrowState throwState;
    OverworldWildPresentationState spawnPresentations;
    OverworldWildBehaviorConditionRuntime *conditions;
    s16 movementCustomJumpTargetX[10],movementCustomJumpTargetY[10];
    s32 movementCustomJumpTargetBaseY[10];
} OverworldWildOverlayRuntimeState;
struct FieldSystem { LocalMapObject *playerAvatar; };
typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[10]; FieldSystem *movementFieldSystem;
    OverworldWildOverlayRuntimeState *movementRuntimeState;
    u8 movementActorControlModes[10],movementCooldowns[10],movementSpotStates[10];
    u8 movementSpawnRunActive[10]; s16 movementSpawnRunTargetX[10],movementSpawnRunTargetY[10];
    u16 captureTargetMask,movementInProgressMask;
} OverworldWildSpawnState;
/* HOST_NATIVE_CONDITION_TYPES */
#define OW_WILD_RUNTIME(state) ((state)->movementRuntimeState)
typedef struct OverworldWildHelperOverlayEntry {
    u16 (*clearPickupThrowState)(OverworldWildSpawnState *,OverworldWildThrowState *,OverworldWildPresentationState *,int,BOOL);
} OverworldWildHelperOverlayEntry;
typedef BOOL (*PlayerHealthThrowIsCurrentSpawnFunc)(FieldSystem *,const OverworldWildSpawn *);
typedef BOOL (*PlayerHealthThrowQueryTargetFunc)(OverworldWildSpawnState *,int,int,u8,u32);
typedef BOOL (*OverworldThrowObservationBindingPositionFunc)(OverworldWildSpawnState *,u8,u8,OverworldTargetBindingPosition *);
typedef struct PlayerHealthThrowServiceEntry {
    u32 (*observe)(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,const OverworldWildBehaviorDataBlob *,const OverworldWildBehaviorConditionRuntime *,PlayerHealthThrowIsCurrentSpawnFunc,PlayerHealthThrowQueryTargetFunc);
    BOOL (*bindingPosition)(OverworldWildSpawnState *,u8,u8,OverworldTargetBindingPosition *);
} PlayerHealthThrowServiceEntry;
typedef struct OverworldCargoReadWildObservationCall {
    OverworldCargoQueryWildCall cargo; OverworldWildBehaviorConditionRuntime *conditions;
    const PlayerHealthThrowServiceEntry *throwService;
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn; PlayerHealthThrowQueryTargetFunc queryTarget;
} OverworldCargoReadWildObservationCall;
typedef struct OverworldCargoReadWildTargetOps {
    int (*playerX)(LocalMapObject *); int (*playerY)(LocalMapObject *);
    PlayerHealthThrowIsCurrentSpawnFunc isCurrentSpawn; PlayerHealthThrowQueryTargetFunc queryTarget;
    BOOL (*circleTarget)(OverworldWildSpawnState *,FieldSystem *,int,const OverworldWildBehaviorProfile *,u8,int,int,int,int,int *,int *);
    BOOL (*adjacentTarget)(OverworldWildSpawnState *,FieldSystem *,int,const OverworldWildBehaviorProfile *,int *,int *);
} OverworldCargoReadWildTargetOps;
typedef struct OverworldCargoReadWildTargetCall {
    OverworldWildSpawnState *state; LocalMapObject *object; const OverworldWildBehaviorProfile *profile;
    const PlayerHealthThrowServiceEntry *throwService; const OverworldCargoReadWildTargetOps *ops;
    u8 slot,movementTarget,throwTarget,reserved;
} OverworldCargoReadWildTargetCall;
typedef struct OverworldCargoReadWildTarget {
    LocalMapObject *targetObject; int objectX,objectY,playerX,playerY,impactX,impactY,dx,dy;
    u8 targetSlot,throwDistance,direction,reserved;
} OverworldCargoReadWildTarget;
#define OVERWORLD_CARGO_READ_TARGET_VALID 1
#define OVERWORLD_CARGO_READ_TARGET_ABORT 2
#define OVERWORLD_CARGO_READ_TARGET_NONE 0
#define OVERWORLD_CARGO_READ_TARGET_CIRCLE 9
#define OVERWORLD_CARGO_READ_TARGET_ADJACENT 6
/* Cargo native read fields above are the existing host boundary. Reuse the
 * real held Call/Ops declarations without importing guest-width layouts. */
#define OVERWORLD_CARGO_READ_WILD_H
#include "overworld_throw_held_wild.h"


static u16 OverworldWildHelper_ClearPickupThrowState(OverworldWildSpawnState *,OverworldWildThrowState *,OverworldWildPresentationState *,int,BOOL);
/* Linked from the real pickup-route C unit by run(), not a fixture comparator. */
u8 OverworldPickupRoute_EqualValues(const void *,const void *,u8);
/* HOST_ACTOR_ROLE_STATE */
static const OverworldWildBehaviorConditionOptions *OverworldCargoReadWild_Options(const OverworldPickupRouteWildWorld *);
static u32 OverworldCargoReadWild_Observe(const OverworldCargoReadWildObservationCall *,BOOL *);
static u8 OverworldCargoReadWild_Target(const OverworldCargoReadWildTargetCall *,OverworldCargoReadWildTarget *);
static u32 OverworldThrowObservation_Observe(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,const OverworldWildBehaviorDataBlob *,const OverworldWildBehaviorConditionRuntime *,PlayerHealthThrowIsCurrentSpawnFunc,PlayerHealthThrowQueryTargetFunc);
static u32 OverworldThrowObservationQuery_Observe(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,const OverworldWildBehaviorDataBlob *,const OverworldWildBehaviorConditionRuntime *,PlayerHealthThrowIsCurrentSpawnFunc,PlayerHealthThrowQueryTargetFunc,OverworldThrowObservationBindingPositionFunc);
static const OverworldWildHelperOverlayEntry helper={OverworldWildHelper_ClearPickupThrowState};
static unsigned releaseCalls,normalizes,shadows,contactCancels,startCalls;
static OverworldPickupRouteStatus routeStatus=OVERWORLD_PICKUP_ROUTE_REACHABLE;
static BOOL startAccepted=FALSE;
static u16 eligibleMask;
static OverworldWildBehaviorDataBlob *blob;
extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static BOOL OverworldThrowObservation_BindingPosition(OverworldWildSpawnState *s,u8 slot,u8 name,OverworldTargetBindingPosition *out) {
    OverworldBehaviorConditionWorldView world=s->movementRuntimeState->conditions->frame.world;
    world.subject=s->movementRuntimeState->conditions->actors[slot].subject;
    return OverworldTargetBindings_Resolve(&s->movementRuntimeState->conditions->bindings[slot],&world,name,out)==OVERWORLD_TARGET_BINDING_OK;
}
static const PlayerHealthThrowServiceEntry throwService={OverworldThrowObservation_Observe,OverworldThrowObservation_BindingPosition};
#define PLAYER_HEALTH_THROW_SERVICE_ENTRY (&throwService)
static BOOL PlayerHealthThrowService_IsReady(void) { return TRUE; }
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f,const OverworldWildSpawn *s) { return f!=NULL && s->active && s->object!=NULL; }
static BOOL OverworldWildSpawns_QueryPickupThrowTarget(OverworldWildSpawnState *s,int slot,int target,u8 query,u32 masks) { (void)s;(void)slot;(void)query;(void)masks;return (eligibleMask&(1u<<target))!=0; }
static void OverworldWildSpawns_ClearWalkMovementState(OverworldWildSpawnState *s,int slot,LocalMapObject *o) { (void)o;assert(s->movementActorControlModes[slot]==0);releaseCalls++; }
static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void) { return &helper; }
static OverworldWildBehaviorConditionRuntime *OverworldWildSpawns_GetConditionRuntime(OverworldWildSpawnState *s) { return s->movementRuntimeState->conditions; }
static BOOL OverworldWildSpawns_ApplyPresentationCommand(FieldSystem *f,OverworldWildSpawnState *s,int cmd,u8 slot) { (void)f;(void)s;(void)cmd;(void)slot;normalizes++;return TRUE; }
static void OverworldWildSpawns_ReconcileNativeShadow(FieldSystem *f,LocalMapObject *o) { (void)f;(void)o;shadows++; }
static BOOL OverworldWildSpawns_PlayerHealthReady(void) { return TRUE; }
static BOOL Contact(OverworldWildSpawnState *s,int code,const OverworldWildBehaviorProfile *p,u32 detail) { (void)s;(void)p;(void)detail;if((code&255)==PLAYER_HEALTH_MOTION_CANCEL)contactCancels++;else assert((code&255)==PLAYER_HEALTH_THROW_LAUNCH);return TRUE; }
static const struct { BOOL (*contactEvent)(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,u32); } health={Contact};
#define PLAYER_HEALTH_OVERLAY_ENTRY (&health)
static int PlayerHealthThrow_Abs(int x) { return abs(x); }
static OverworldPickupRouteStatus OverworldCargoReadWild_Route(const OverworldCargoQueryWildCall *call,OverworldCargoQueryResult *out) { (void)call;memset(out,0,sizeof(*out));out->status=routeStatus;out->eligibleActorMask=eligibleMask;return routeStatus; }
/* Target access is the T44 engine read seam, invoked through the actual
 * CargoReadObserve body. Its typed borrowed packet and call order stay real. */
static OverworldBehaviorConditionStatus FixtureConditionNative(OverworldConditionNativeCall *call) {
    assert(call!=NULL && call->version==OVERWORLD_CONDITION_NATIVE_CALL_VERSION
        && call->size==sizeof(*call) && call->operation==OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS);
    OverworldPickupRouteWildWorld *world=call->targetAccessWorld;
    assert(world!=NULL && world->state==call->state && world->field==call->field
        && world->behaviorData==call->blob && call->blobSize==sizeof(*call->blob)
        && world->slot==call->slot && call->runtime==world->state->movementRuntimeState->conditions);
    for(u8 i=0;i<call->runtime->frame.world.actorCount;i++) {
        OverworldBehaviorConditionCandidate *candidate=&call->runtime->frame.candidates[i];
        assert(candidate->reserved[0]&OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE);
        if(eligibleMask&(1u<<call->runtime->frame.world.actors[i].actor.slot))
            candidate->reserved[0]&=~OVERWORLD_BEHAVIOR_CONDITION_CANDIDATE_INACCESSIBLE;
    }
    return OVERWORLD_BEHAVIOR_CONDITION_OK;
}
typedef struct OverworldQueryCodeAddonEntry {
    const OverworldWildBehaviorConditionOptions *(*cargoReadOptions)(const OverworldPickupRouteWildWorld *);
    u32 (*cargoReadObserve)(const OverworldCargoReadWildObservationCall *,BOOL *);
    u8 (*cargoReadTarget)(const OverworldCargoReadWildTargetCall *,OverworldCargoReadWildTarget *);
    u32 (*throwObserve)(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,const OverworldWildBehaviorDataBlob *,const OverworldWildBehaviorConditionRuntime *,PlayerHealthThrowIsCurrentSpawnFunc,PlayerHealthThrowQueryTargetFunc,OverworldThrowObservationBindingPositionFunc);
    BOOL (*throwHeld)(const OverworldThrowHeldWildCall *);
    OverworldBehaviorConditionStatus (*conditionNative)(OverworldConditionNativeCall *);
} OverworldQueryCodeAddonEntry;
static const OverworldQueryCodeAddonEntry entry={OverworldCargoReadWild_Options,OverworldCargoReadWild_Observe,OverworldCargoReadWild_Target,OverworldThrowObservationQuery_Observe,OverworldThrowHeldWild_Run,FixtureConditionNative};
/* Private package acquisition is a native seam. Both the fixed native
 * wrapper and the moved observation/line bodies are actual production C. */
typedef struct OverworldQueryCodeAddonOwner { u32 fieldIdentity; u16 fieldEpoch,mapGeneration; } OverworldQueryCodeAddonOwner;
typedef struct OverworldQueryCodeAddonServiceEntry {
    const OverworldQueryCodeAddonEntry *(*acquire)(const OverworldQueryCodeAddonOwner *);
} OverworldQueryCodeAddonServiceEntry;
static const OverworldQueryCodeAddonEntry *ObserveAcquire(const OverworldQueryCodeAddonOwner *owner) {
    assert(owner->fieldEpoch==3 && owner->mapGeneration==4);return &entry;
}
static const OverworldQueryCodeAddonServiceEntry observeService={ObserveAcquire};
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR ((uintptr_t)&observeService)
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE() (&entry)
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem *f,void *unused) { (void)unused;return f!=NULL?&entry:NULL; }
static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void) { return blob; }
/* This fixture owns idle failure/expiry/retry. A moving-frame refresh must
 * not get an invented world from this host native-read seam. */
static void OverworldWildSpawns_BuildBehaviorContext(OverworldWildBehaviorContext *c,const OverworldWildSpawn *s,u16 species,u8 level,u8 terrain,u8 shiny) { (void)c;(void)s;(void)species;(void)level;(void)terrain;(void)shiny;assert(!"idle fixture requested native context"); }
static BOOL OverworldBehaviorConditionAdapter_BuildFrame(OverworldWildSpawnState *s,FieldSystem *f,OverworldWildBehaviorConditionRuntime *r,void (*context)(OverworldWildBehaviorContext *,const OverworldWildSpawn *,u16,u8,u8,u8),BOOL (*current)(FieldSystem *,const OverworldWildSpawn *)) { (void)s;(void)f;(void)r;(void)context;(void)current;assert(!"idle fixture requested native frame");return FALSE; }
static void OverworldWildSpawns_InitRouteWorld(OverworldWildSpawnState *s,int slot,OverworldPickupRouteWildWorld *world) {
    memset(world,0,sizeof(*world));world->state=s;world->slot=slot;
    world->field=s->movementFieldSystem;world->ops=&roleOps;world->behaviorData=blob;
}
static void OverworldWildSpawns_InitCargoReadCall(OverworldWildSpawnState *s,u8 slot,const OverworldWildBehaviorProfile *p,OverworldPickupRouteWildWorld *world,OverworldCargoQueryWildCall *call) { memset(world,0,sizeof(*world));world->state=s;world->slot=slot;world->field=s->movementFieldSystem;world->behaviorData=blob;world->ops=&roleOps;memset(call,0,sizeof(*call));call->world=world;call->profile=p;call->allowedTerrainMask=p->owner.chillAllowedTerrainMask;call->locomotion=p->owner.chillAction; }
/* T44 separately proves the native reachability leaf. This fixture owns
 * cleanup and binding transitions, so the engine query remains a host seam. */
static void OverworldWildSpawns_PopulateTargetAccess(OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorDataBlob *b,OverworldWildBehaviorConditionRuntime *c,const OverworldQueryCodeAddonEntry *e,OverworldPickupRouteWildWorld *w,u16 terrain) { (void)s;(void)slot;(void)b;(void)c;(void)e;(void)w;(void)terrain; }
static int X(LocalMapObject *o) { return o->xCurr; } static int Y(LocalMapObject *o) { return o->yCurr; }
static BOOL Circle(OverworldWildSpawnState *s,FieldSystem *f,int slot,const OverworldWildBehaviorProfile *p,u8 spot,int x,int y,int px,int py,int *outx,int *outy) { (void)s;(void)f;(void)slot;(void)p;(void)spot;(void)x;(void)y;(void)px;(void)py;(void)outx;(void)outy;return FALSE; }
static BOOL Adjacent(OverworldWildSpawnState *s,FieldSystem *f,int slot,const OverworldWildBehaviorProfile *p,int *x,int *y) { (void)s;(void)f;(void)slot;(void)p;(void)x;(void)y;return FALSE; }
static const OverworldCargoReadWildTargetOps sOverworldWildCargoTargetOps={X,Y,OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget,Circle,Adjacent};
static u32 OverworldWildSpawns_GetActiveConditionApplications(OverworldWildSpawnState *s,int slot) { (void)s;(void)slot;return 1; }
static int OverworldWildSpawns_BuildDirectedDirections(int dx,int dy,u8 *d) { d[0]=dx?2+(dx>0):(dy>0);return dx||dy; }
static int OverworldWildSpawns_BuildRandomDirections(u8 *d) { d[0]=0;return 1; }
static int OverworldWildSpawns_Abs(int x) { return abs(x); }
static int OverworldWildSpawns_Max(int a,int b) { return a>b?a:b; }
static u16 OverworldWildSpawns_GetAllowedTileForSpotState(const OverworldWildBehaviorProfile *p,u8 spot) { (void)spot;return p->owner.chillAllowedTerrainMask; }
static OverworldPickupRouteStatus OverworldWildSpawns_QueryCargoRoute(OverworldWildSpawnState *s,u8 slot,const OverworldWildBehaviorProfile *p,u16 mask,OverworldCargoQueryResult *out) { (void)s;(void)slot;(void)p;(void)mask;memset(out,0,sizeof(*out));out->status=routeStatus;out->route.hasNextStep=1;out->route.nextStep.x=11;out->route.nextStep.y=10;return routeStatus; }
static BOOL OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(OverworldWildSpawnState *s,FieldSystem *f,int slot,const OverworldWildBehaviorProfile *p,u16 allowed,int x,int y,int tx,int ty,u8 marker) { (void)s;(void)f;(void)slot;(void)p;(void)allowed;(void)x;(void)y;(void)tx;(void)ty;(void)marker;startCalls++;return startAccepted; }
static LocalMapObject *sOverworldWildCollisionIgnoredObject;
/* Unused motion/presentation seams in these loss and route-START cases. */
#define MapObject_ClearSingleMovementActive(...) ((void)0)
#define OverworldWildSpawns_TryStartChillWanderCommand(...) FALSE
#define OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile(...) ((void)0)
#define OverworldWildSpawns_SetObjectFacing(...) ((void)0)
#define OverworldWildSpawns_ShowBubble(...) ((void)0)
#define OverworldWildSpawns_GetAlertBubbleIdForProfile(...) 0
#define OverworldWildSpawns_StartCarriedThrowTarget(...) FALSE
#define OverworldWildSpawns_AppendFleeFallbackDirections(...) ((void)0)
#define OverworldWildSpawns_ApplyWalkPursuitDirectionInertia(...) ((void)0)
#define OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(...) ((void)0)
#define OverworldWildSpawns_TryStartRandomBehaviorHopCommand(...) FALSE
#define OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(...) FALSE
#define OverworldWildSpawns_TryStartTeleportMovementCommand(...) FALSE
#define OverworldWildSpawns_TryStartSpawnerMovementCommand(...) FALSE
#define OW_WILD_SPAWNER_CUSTOM_MOTION_THROW_FLAG 3

/* Existing dispatcher reads and native START remain host seams. The saved
 * plan and mandatory launch recheck are extracted production control flow. */
static int nativeAwayValid=1,selectCalls,validateCalls,flightCalls,recoveryCalls;
static s32 flightHeight;
static void OverworldWildSpawns_AbortThrow(OverworldWildSpawnState *,int);
static void OverworldWildSpawns_ClearThrowStateForSlot(OverworldWildSpawnState *,int);
static BOOL OverworldWildSpawns_ReadAwayThrow(OverworldWildSpawnState *s,int carrier,int cargo,u32 settings,const OverworldThrowAwayAim *required,OverworldThrowAwayAim *out) {
 (void)s;assert(carrier==0&&cargo==1&&settings==(3|(1u<<8)));
 if(required){++validateCalls;assert(required->x==13&&required->z==10&&required->baseY==24576&&required->distance==3&&required->direction==3);}
 else ++selectCalls;
 if(!nativeAwayValid)return FALSE;
 if(out)*out=required?*required:(OverworldThrowAwayAim){13,10,24576,3,3};
 return TRUE;
}
static const LocalMapObject *OverworldWildSpawns_GetThrowBindingBody(OverworldWildSpawnState *s,int slot,u8 name,int x,int y) {
 OverworldTargetBindingPosition b;if(!throwService.bindingPosition(s,slot,name,&b))return NULL;
 if(b.x!=x||b.y!=y||b.target.kind!=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR)return NULL;
 return s->spawns[b.target.actor.slot].object;
}
static BOOL Flight(OverworldWildSpawnState *s,FieldSystem *f,int slot,LocalMapObject *o,u8 direction,u8 distance,int x,int z,const OverworldWildBehaviorProfile *p,int flag) {
 (void)f;(void)o;(void)p;assert(slot==1&&direction==3&&distance==3&&x==13&&z==10&&flag==3);
 ++flightCalls;flightHeight=s->movementRuntimeState->movementCustomJumpTargetBaseY[slot];return TRUE;
}
#define OverworldWildSpawns_StartPreparedCustomJumpCommand Flight
#define OverworldWildSpawns_StartThrowRecovery(...) (++recoveryCalls)
static void HeldClearMovement(LocalMapObject *o) { (void)o; }
static void HeldRecovery(OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorProfile *p,const OverworldWildBehaviorPrimitives *v) { (void)s;(void)slot;(void)p;(void)v;++recoveryCalls; }
static void HeldRelease(OverworldWildSpawnState *s,int carrier,int cargo,LocalMapObject *o) { (void)cargo;(void)o;OverworldWildSpawns_ClearThrowStateForSlot(s,carrier); }
static void HeldFacing(LocalMapObject *o,u8 direction) { (void)o;(void)direction; }
static void HeldBubble(LocalMapObject *o,u8 bubble) { (void)o;(void)bubble; }
static u8 HeldBubbleId(const OverworldWildBehaviorProfile *p) { (void)p;return 0; }
static const OverworldThrowHeldWildOps sOverworldWildThrowHeldOps={
    OverworldWildSpawns_GetThrowBindingBody,HeldClearMovement,Flight,HeldRecovery,
    HeldRelease,HeldFacing,HeldBubble,HeldBubbleId,OverworldWildSpawns_AbortThrow
};
BOOL OverworldThrowAwayWild_Read(const OverworldThrowAwayWildCall *call) {
    return OverworldWildSpawns_ReadAwayThrow(call->world->state,call->world->slot,
        call->targetSlot,call->settings,call->required,call->result);
}
#define PlayerHealthOverlay_IsReady OverworldWildSpawns_PlayerHealthReady

"""

# Keep the actual typed native packet. Only its enclosing runtime/engine
# container is host-width, so skip that container's ARM-only header layout.
_native_adapter = (ROOT / "include/overworld_behavior_condition_adapter.h").read_text()
_native_callbacks = "\n".join(re.search(
    r"typedef (?:void|u16|u32) \(\*" + name + r"\)\([\s\S]*?\);", _native_adapter).group(0)
    for name in ("OverworldBehaviorConditionBuildContextFunc",
                 "OverworldBehaviorConditionTerrainFunc", "OverworldBehaviorConditionObserveFunc"))
PRELUDE = PRELUDE.replace("/* HOST_NATIVE_CONDITION_TYPES */",
    "#define OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_H\n" + _native_callbacks
    + '\n#include "overworld_condition_moving_notice_native.h"')
PRELUDE = PRELUDE.replace("/* HOST_ACTOR_ROLE_STATE */", HOST_ACTOR_ROLE_STATE)


DRIVER = r"""
static OverworldActorHandle Handle(unsigned slot,unsigned generation) {
    OverworldActorHandle h={0};h.slot=slot;h.generation=generation;
    h.fieldEpoch=3;h.mapGeneration=4;h.encounterGeneration=generation+10;return h;
}
static OverworldWildSpawnState state;
static unsigned selectionCalls;
static OverworldWildOverlayRuntimeState runtime;
static OverworldWildBehaviorConditionRuntime conditions;
static LocalMapObject objects[10],player={.xCurr=80,.yCurr=80};
static FieldSystem field={&player};
static OverworldWildBehaviorProfile profile;
static OverworldWildBehaviorPrimitives primitives;
static unsigned cargoIndex;
static void Bind(unsigned name,unsigned actor,u8 lifetime,u16 duration) {
    OverworldBehaviorConditionEntryResult admitted={0};
    admitted.active=admitted.triggered=admitted.conditionTrue=1;
    admitted.conditionId=blob->conditionEntries[cargoIndex].conditionId;
    admitted.applicationIndex=blob->conditionEntries[cargoIndex].applicationIndex;
    admitted.target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    for(unsigned i=0;i<conditions.frame.world.actorCount;i++)
        if(conditions.frame.world.actors[i].actor.slot==actor)
            admitted.target.actor=conditions.frame.world.actors[i].actor;
    assert(OverworldTargetBindings_CaptureEntry(&conditions.bindings[0],
        &conditions.frame.world,&conditions.actors[0].subject,&admitted,name,lifetime,duration)
        ==OVERWORLD_TARGET_BINDING_OK);
}
static void InitCase(BOOL held) {
    memset(&state,0,sizeof(state));memset(&runtime,0,sizeof(runtime));memset(&conditions,0,sizeof(conditions));
    memset(&profile,0,sizeof(profile));memset(&primitives,0,sizeof(primitives));
    releaseCalls=normalizes=shadows=contactCancels=startCalls=selectionCalls=0;
    routeStatus=OVERWORLD_PICKUP_ROUTE_REACHABLE;eligibleMask=1u<<1;startAccepted=FALSE;
    memset(&roleState,0,sizeof(roleState));roleStateReady=TRUE;
    roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
    state.movementFieldSystem=&field;state.movementRuntimeState=&runtime;runtime.conditions=&conditions;
    blob=malloc(sizeof(*blob));assert(blob);memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
    for(cargoIndex=0;cargoIndex<blob->header.conditionEntryCount;cargoIndex++)
        if(blob->conditionOptions[cargoIndex].captureBinding==2 && blob->conditionOptions[cargoIndex].mustBeReachableForPickup
            && OverworldBehaviorCondition_RoleApplies(blob->conditionOptions[cargoIndex].subjectRoleMask,OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD))break;
    assert(cargoIndex<blob->header.conditionEntryCount);
    assert(blob->conditionOptions[cargoIndex].failureResponse==1 && blob->conditionOptions[cargoIndex].retryFrames==32);
    for(unsigned i=0;i<10;i++){objects[i]=(LocalMapObject){.xCurr=10+(int)i,.yCurr=10};state.spawns[i].object=&objects[i];state.spawns[i].active=1;conditions.actors[i].subject=Handle(i,i+1);}
    conditions.actors[0].count=1;conditions.actors[0].catalogEntryIndexes[0]=cargoIndex;
    conditions.frame.valid=1;conditions.frame.world.subject=Handle(0,1);conditions.frame.world.subjectRoleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
    conditions.frame.world.bindings=&conditions.bindings[0];
    conditions.frame.world.frame=100;conditions.frame.world.actorCount=3;
    for(unsigned n=0;n<3;n++){conditions.frame.world.actors[n].actor=Handle(n+1,n+2);conditions.frame.world.actors[n].x=11+n;conditions.frame.world.actors[n].y=10;conditions.frame.world.actors[n].valid=1;}
    assert(OverworldTargetBindings_Init(&conditions.bindings[0],&conditions.actors[0].subject)==OVERWORLD_TARGET_BINDING_OK);
    Bind(OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST,3,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0);
    Bind(OVERWORLD_TARGET_BINDING_CARGO,1,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0);
    runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_ENCODE(1)|(held?0x80:0);
    runtime.throwState.carrierMask=1;runtime.throwState.targetMask=2;
    state.movementActorControlModes[1]=held?1:0;
    profile.owner.chillAllowedTerrainMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;
    profile.owner.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
    profile.onReachAction=OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR;
    primitives.chillTarget=OW_WILD_BEHAVIOR_TARGET_CARGO;primitives.chillLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
}
static void Cleaned(BOOL held) {
    assert(runtime.throwState.targets[0]==0 && runtime.throwState.targetMask==0 && runtime.throwState.carrierMask==0 && runtime.throwState.recoveringMask==0);
    assert(conditions.bindings[0].bindings[0].flags==0 && conditions.bindings[0].bindings[1].flags==0);
    assert(!memcmp(&conditions.bindings[0].subject,&conditions.actors[0].subject,sizeof(OverworldActorHandle)));
    assert(state.movementActorControlModes[1]==0);
    assert(state.movementCooldowns[0]==32);
    assert(releaseCalls==(unsigned)held && normalizes==(unsigned)held && shadows==(unsigned)held && contactCancels==(unsigned)held);
}
static void SelectNewCargo(void) {
    OverworldBehaviorConditionEntryState value={0};
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    OverworldBehaviorConditionCandidate candidates[3]={0};
    OverworldBehaviorConditionPreparedActor *prepared=&conditions.actors[0];
    assert(state.movementCooldowns[0]==32); /* Native wait length, not host elapsed frames. */
    Bind(OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST,3,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0);
    eligibleMask=1u<<2;
    u32 observation=OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions);
    assert(((observation>>8)&1023)==(1u<<2));
    conditions.frame.world.reserved[0]=observation&255;
    conditions.frame.world.reserved[1]=(observation>>8)&255;
    conditions.frame.world.reserved[2]=(observation>>16)&3;
    conditions.frame.world.incomingClaimMask=(observation>>18)&1023;
    prepared->states=&value;prepared->stateCapacity=1;prepared->valid=1;
    for(unsigned n=0;n<3;n++){candidates[n].context.species=43;candidates[n].context.level=5;candidates[n].roleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;}
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),prepared,
        &conditions.frame.world,candidates,3,1,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(conditions.bindings[0].bindings[1].flags==OVERWORLD_TARGET_BINDING_BOUND);
    assert(conditions.bindings[0].bindings[1].target.actor.slot==2);
    selectionCalls++;
}
int main(void) {
    /* Lost Trigger must clear a held Cargo, its claim and both bindings. */
    InitCase(TRUE);conditions.frame.world.actors[2].actor.generation++;
    assert(OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions)==0);
    Cleaned(TRUE);SelectNewCargo();assert(selectionCalls==1);free(blob);
    /* Lost Cargo follows the same composed owner cleanup, not a player fallback. */
    InitCase(TRUE);conditions.frame.world.actors[0].actor.encounterGeneration++;
    assert(OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions)==0);
    Cleaned(TRUE);free(blob);
    /* Timed binding stays live before the exact expiry and aborts at expiry. */
    InitCase(TRUE);assert(OverworldTargetBindings_Clear(&conditions.bindings[0],&conditions.actors[0].subject,0,OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)==0);
    Bind(0,3,OVERWORLD_TARGET_BINDING_FRAMES,5);conditions.frame.world.frame=104;
    assert(OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions)&OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID);
    assert(runtime.throwState.targets[0]!=0);conditions.frame.world.frame=105;
    assert(OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions)==0);
    Cleaned(TRUE);free(blob);
    /* Actual frame dispatcher owns failure of a reachable route's native START. */
    InitCase(FALSE);
    assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    assert(startCalls==1);Cleaned(FALSE);SelectNewCargo();free(blob);
    /* The matching accepted START preserves the relation and does not apply retry. */
    InitCase(FALSE);startAccepted=TRUE;
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    assert(startCalls==1 && runtime.throwState.targets[0]!=0 && state.movementCooldowns[0]==0);free(blob);
    puts("Throw owner composition: loss, expiry, START failure, cleanup and authored retry/new Cargo pass");return 0;
}
"""


NOTICE_ABORT_DRIVER = r"""
int main(void) {
    OverworldBehaviorConditionEntryState entryStates[3]={{0}};
    OverworldBehaviorConditionScratch scratch={0};
    OverworldBehaviorConditionResult result={0};
    OverworldBehaviorConditionCandidate candidates[3]={{0}};
    unsigned noticeIndex,dependentIndex;

    InitCase(FALSE);
    for(noticeIndex=0;noticeIndex<blob->header.conditionEntryCount;noticeIndex++)
        if(blob->conditionOptions[noticeIndex].captureBinding==OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST+1
            && blob->conditionEntries[noticeIndex].targetKind==OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER
            && OverworldBehaviorCondition_RoleApplies(blob->conditionOptions[noticeIndex].subjectRoleMask,
                OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD))break;
    assert(noticeIndex<blob->header.conditionEntryCount);
    for(dependentIndex=0;dependentIndex<blob->header.conditionEntryCount;dependentIndex++)
        if(blob->conditionOptions[dependentIndex].captureBinding==0
            && blob->conditionOptions[dependentIndex].usesBinding==OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST+1
            && OverworldBehaviorCondition_RoleApplies(blob->conditionOptions[dependentIndex].subjectRoleMask,
                OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD))break;
    assert(dependentIndex<blob->header.conditionEntryCount);
    conditions.actors[0].count=3;
    conditions.actors[0].catalogEntryIndexes[0]=noticeIndex;
    conditions.actors[0].catalogEntryIndexes[1]=cargoIndex;
    conditions.actors[0].catalogEntryIndexes[2]=dependentIndex;
    conditions.actors[0].states=entryStates;
    conditions.actors[0].stateCapacity=3;
    conditions.actors[0].valid=1;
    entryStates[0].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE
        |OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED
        |OVERWORLD_BEHAVIOR_CONDITION_STATE_PRESENTATION_PENDING;
    entryStates[0].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
    entryStates[0].cooldownUntil=777;
    entryStates[1].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    entryStates[1].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    entryStates[1].targetSlot=1;
    entryStates[1].targetGeneration=2;
    entryStates[2].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
        ==OVERWORLD_TARGET_BINDING_BOUND);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
        ==OVERWORLD_TARGET_BINDING_BOUND);
    /* Pre-pickup hit takes the real combat cleanup branch. */
    OverworldWildSpawns_PrepareCarrierHit(&state,&field,0);
    assert(runtime.throwState.targets[0]==0 && runtime.throwState.carrierMask==0
        && runtime.throwState.targetMask==0);
    assert(conditions.frame.valid==1);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags==0);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags==0);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)==0);
    assert((entryStates[1].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)==0);
    assert((entryStates[2].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)==0);
    assert(entryStates[0].targetKind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE);
    assert(entryStates[0].cooldownUntil==777);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_PRESENTATION_PENDING)!=0);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED)!=0);

    player.xCurr=11;player.yCurr=10;
    conditions.frame.world.subjectX=10;conditions.frame.world.subjectY=10;
    conditions.frame.world.subjectFacing=3;
    conditions.frame.world.playerX=11;conditions.frame.world.playerY=10;
    conditions.frame.world.playerValid=1;
    conditions.actors[0].count=1;
    for(unsigned n=0;n<3;n++){
        candidates[n].context.species=43;candidates[n].context.level=5;
        candidates[n].roleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
    }
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),&conditions.actors[0],
        &conditions.frame.world,candidates,3,1,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)!=0);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
        ==OVERWORLD_TARGET_BINDING_BOUND);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.kind
        ==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
    assert(result.triggeredApplicationMask!=0);
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),&conditions.actors[0],
        &conditions.frame.world,candidates,3,1,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(result.triggeredApplicationMask==0);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
        ==OVERWORLD_TARGET_BINDING_BOUND);
    /* The live Trigger can now admit a fresh Cargo, with no old claim left. */
    conditions.actors[0].count=2;
    eligibleMask=1u<<2;
    u32 observation=OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions);
    assert(((observation>>8)&1023)==(1u<<2));
    conditions.frame.world.reserved[0]=observation&255;
    conditions.frame.world.reserved[1]=(observation>>8)&255;
    conditions.frame.world.reserved[2]=(observation>>16)&3;
    conditions.frame.world.incomingClaimMask=(observation>>18)&1023;
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),&conditions.actors[0],
        &conditions.frame.world,candidates,3,1,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags
        ==OVERWORLD_TARGET_BINDING_BOUND);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor.slot==2);
    assert(runtime.throwState.targets[0]==0 && runtime.throwState.targetMask==0);
    free(blob);

    /* A blocked or invalid Cargo query uses the same abort path. */
    InitCase(FALSE);
    memset(entryStates,0,sizeof(entryStates));
    conditions.actors[0].count=1;
    conditions.actors[0].catalogEntryIndexes[0]=noticeIndex;
    conditions.actors[0].states=entryStates;
    conditions.actors[0].stateCapacity=1;
    conditions.actors[0].valid=1;
    entryStates[0].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    entryStates[0].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
    OverworldWildSpawns_AbortThrow(&state,0);
    assert(runtime.throwState.targets[0]==0 && runtime.throwState.carrierMask==0);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags==0);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)==0);
    assert(conditions.frame.valid==1);
    free(blob);

    /* The follower's actor notice must retire by the same bound-name rule. */
    InitCase(FALSE);
    for(noticeIndex=0;noticeIndex<blob->header.conditionEntryCount;noticeIndex++)
        if(blob->conditionOptions[noticeIndex].captureBinding==OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST+1
            && blob->conditionEntries[noticeIndex].targetKind==OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR
            && OverworldBehaviorCondition_RoleApplies(blob->conditionOptions[noticeIndex].subjectRoleMask,
                OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER))break;
    assert(noticeIndex<blob->header.conditionEntryCount);
    memset(entryStates,0,sizeof(entryStates));
    conditions.actors[0].count=1;
    conditions.actors[0].catalogEntryIndexes[0]=noticeIndex;
    conditions.actors[0].states=entryStates;
    conditions.actors[0].stateCapacity=1;
    conditions.actors[0].valid=1;
    conditions.frame.world.subjectRoleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER;
    conditions.frame.world.subjectX=10;conditions.frame.world.subjectY=10;
    conditions.frame.world.subjectFacing=3;
    entryStates[0].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    entryStates[0].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    entryStates[0].targetSlot=3;
    entryStates[0].targetGeneration=4;
    OverworldWildSpawns_PrepareCarrierHit(&state,&field,0);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)==0);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags==0);
    assert(conditions.frame.valid==1);
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),&conditions.actors[0],
        &conditions.frame.world,candidates,3,1,&scratch,&result)==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert((entryStates[0].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)!=0);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
        ==OVERWORLD_TARGET_BINDING_BOUND);
    assert(conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].target.kind
        ==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR);
    free(blob);
    return 0;
}
"""

PURSUER_DRIVER = r"""
int main(void) {
    OverworldWildSpawnState state={0};OverworldWildOverlayRuntimeState runtime={0};
    OverworldWildBehaviorConditionRuntime conditions={0};LocalMapObject objects[10]={0};
    LocalMapObject player={.xCurr=100,.yCurr=100};FieldSystem field={&player};
    OverworldWildBehaviorProfile profile={0};
    OverworldBehaviorConditionEntryState entryState={0};
    OverworldBehaviorConditionScratch scratch;OverworldBehaviorConditionResult result;
    OverworldBehaviorConditionCandidate candidates[2]={0};
    blob=malloc(sizeof(*blob));assert(blob);memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
    unsigned index;
    for(index=0;index<blob->header.conditionEntryCount;index++)
        if(blob->conditionEntries[index].kind==OW_WILD_BEHAVIOR_CONDITION_ACTOR_FACTS
            && blob->conditionEntries[index].terrainMask==OVERWORLD_BEHAVIOR_ACTOR_FACT_TARGETED_FOR_PICKUP
            && blob->conditionEntries[index].targetKind==OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR)break;
    assert(index<blob->header.conditionEntryCount);
    state.movementFieldSystem=&field;state.movementRuntimeState=&runtime;runtime.conditions=&conditions;
    for(unsigned i=0;i<10;i++){state.spawns[i].object=&objects[i];state.spawns[i].active=1;conditions.actors[i].subject=Handle(i,i+1);}
    OverworldBehaviorConditionWorldView *world=&conditions.frame.world;
    world->subject=Handle(3,4);world->subjectRoleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
    world->subjectX=10;world->subjectY=10;world->frame=100;world->actorCount=2;
    world->actors[0].actor=Handle(0,1);world->actors[0].x=11;world->actors[0].y=10;world->actors[0].valid=1;
    world->actors[1].actor=Handle(7,8);world->actors[1].x=14;world->actors[1].y=10;world->actors[1].valid=1;
    candidates[0].context.species=56;candidates[0].roleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;
    candidates[1].context.species=74;candidates[1].roleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER;
    OverworldBehaviorConditionPreparedActor *prepared=&conditions.actors[3];
    prepared->valid=1;prepared->states=&entryState;prepared->stateCapacity=1;prepared->count=1;prepared->catalogEntryIndexes[0]=index;
    runtime.throwState.targets[7]=OW_WILD_HELPER_THROW_TARGET_ENCODE(3);
    u32 observation=OverworldThrowObservation_Observe(&state,3,&profile,blob,&conditions,OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget);
    assert((observation>>18)==(1u<<7));
    world->incomingClaimMask=observation>>18;world->reserved[0]=observation&255;
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),prepared,world,candidates,2,1,&scratch,&result)==0);
    assert(result.resolvedTarget.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR && result.resolvedTarget.actor.slot==7);
    /* Compact observation index does not substitute for the native slot bit. */
    OverworldBehaviorConditionActorObservation actor=world->actors[0];world->actors[0]=world->actors[1];world->actors[1]=actor;
    OverworldBehaviorConditionCandidate candidate=candidates[0];candidates[0]=candidates[1];candidates[1]=candidate;
    memset(&entryState,0,sizeof(entryState));world->frame++;
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),prepared,world,candidates,2,1,&scratch,&result)==0);
    assert(result.resolvedTarget.actor.slot==7);
    /* A disappeared pursuer contributes no incoming claim and no flee target. */
    state.spawns[7].active=0;
    observation=OverworldThrowObservation_Observe(&state,3,&profile,blob,&conditions,OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget);
    assert(!(observation>>18));world->incomingClaimMask=0;world->reserved[0]=observation&255;
    memset(&entryState,0,sizeof(entryState));world->frame++;
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),prepared,world,candidates,2,1,&scratch,&result)==0);
    assert(!result.activeApplicationMask && result.resolvedTarget.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_NONE);
    free(blob);puts("Actual native claimant wins over nearer non-claimant; compact order and loss pass");return 0;
}
"""



# Position reads use the production frame owner and binding reader. Engine
# pointer/SDK reads below are named host seams; ARM layout is proved by the
# separate exact native link and packed-byte check.
ADAPTER = ROOT / 'lib/overworld/overworld_behavior_condition_adapter.c'
BINDING_NATIVE = ROOT / 'lib/overworld/overworld_throw_binding_native.c'


def binding_fixture(observation_source=None):
    adapter = ADAPTER.read_text()
    clear_start = adapter.index('static void OverworldBehaviorConditionAdapter_ClearActor(')
    host_clear = adapter[clear_start:adapter.index('\n#else', clear_start)]
    body = '\n'.join([
        extract_function(adapter, 'OverworldBehaviorConditionAdapter_ClearResolution', 'void'),
        extract_function(host_clear, 'OverworldBehaviorConditionAdapter_ClearActor', 'void'),
        extract_function(adapter, 'OverworldBehaviorConditionAdapter_BuildFrame', 'BOOL'),
        functions(WILD, [('OverworldWildSpawns_ClearConditionActorRecord', 'void')]),
    ])
    refresh = BINDING_NATIVE.read_text()
    current = extract_function(refresh, 'OverworldThrowBinding_CurrentSpawn', 'BOOL')
    name = 'OverworldThrowBinding_Refresh'
    start = refresh.index(name + '(')
    brace = refresh.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (refresh[end] == '{') - (refresh[end] == '}')
        end += 1
    refresh_body = 'static const OverworldQueryCodeAddonEntry *' + refresh[start:end]
    binding = extract_function(observation_source or OBSERVE.read_text(),
                               'OverworldThrowObservation_BindingPosition', 'BOOL')
    return '\n'.join([BINDING_PRELUDE, body, current, refresh_body,
                      '#define OVERWORLD_THROW_BINDING_REFRESH_ENTRY OverworldThrowBinding_Refresh',
                      binding, BINDING_DRIVER])


BINDING_PRELUDE = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "overworld_behavior_condition_runtime.h"
#include "overworld_target_bindings.h"
#include "overworld_query_code_addon_service.h"
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_SPAWN_TERRAIN_LAND 0
#define OVERWORLD_BEHAVIOR_CONDITION_TARGET_ROLE_MOUNTED 4
#define MAPOBJECTFLAG_ACTIVE 1
#define OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT 1300
#define PLAYER_HEALTH_THROW_RUNTIME(s) ((s)->movementRuntimeState)
typedef struct LocalMapObject { int xCurr,yCurr; u32 flags; u16 id,scriptId; u8 curFacing,owned; } LocalMapObject;
typedef LocalMapObject FIELD_PLAYER_AVATAR;
typedef struct OverworldWildSpawn { LocalMapObject *object; u8 active; u16 mapId,objectId,encounterGeneration; } OverworldWildSpawn;
typedef struct OverworldWildBehaviorConditionFrame { OverworldBehaviorConditionWorldView world; OverworldBehaviorConditionCandidate candidates[10]; u16 actorSlotMask; u8 traceArmed,valid; } OverworldWildBehaviorConditionFrame;
typedef struct OverworldWildBehaviorConditionRuntime {
    OverworldBehaviorConditionPreparedActor actors[10];
    OverworldWildBehaviorConditionFrame frame;
    OverworldVisionSpec currentVisions[10]; OverworldActorSnapshot actorSnapshot;
    u32 activeApplicationMasks[10],timedWinningApplicationMasks[10];
    u16 targetValidMask; OverworldTargetBindingsState bindings[10];
} OverworldWildBehaviorConditionRuntime;
typedef struct OverworldWildOverlayRuntimeState { OverworldWildBehaviorConditionRuntime *conditions; } OverworldWildOverlayRuntimeState;
struct FieldSystem { struct { u16 mapId; } *location; FIELD_PLAYER_AVATAR *playerAvatar; };
typedef struct OverworldWildSpawnState { OverworldWildSpawn spawns[10]; FieldSystem *movementFieldSystem; OverworldWildOverlayRuntimeState *movementRuntimeState; u8 movementBehaviorClasses[10]; u16 mapGeneration; } OverworldWildSpawnState;
typedef void (*OverworldBehaviorConditionBuildContextFunc)(OverworldWildBehaviorContext *,const OverworldWildSpawn *,u16,u8,u8,u8);
typedef BOOL (*OverworldBehaviorConditionIsCurrentSpawnFunc)(FieldSystem *,const OverworldWildSpawn *);
static FieldSystem *gFieldSysPtr;
static u32 currentFrame;
static unsigned contextWrites,inspectCalls,acquireCalls;
static BOOL inspectorReady=TRUE,gateReady=TRUE;
static OverworldActorHandle nativeHandles[10];
static OverworldActorResult Inspect(const OverworldActorQuery *q,OverworldActorSnapshot *s) {
    inspectCalls++; if(!inspectorReady)return OVERWORLD_ACTOR_RESULT_ERROR;
    memset(s,0,sizeof(*s));s->frame=currentFrame;
    if(q->kind==OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX){s->hasActor=1;s->actor.handle=nativeHandles[q->index];s->actor.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;}
    return OVERWORLD_ACTOR_RESULT_OK;
}
static const OverworldActorSystemEntry actorEntry={.inspect=Inspect};
#undef OVERWORLD_ACTOR_SYSTEM_ENTRY
#define OVERWORLD_ACTOR_SYSTEM_ENTRY (&actorEntry)
#define OverworldBehaviorConditionAdapter_Free free
#define sys_FreeMemoryEz free
static BOOL OverworldBehaviorConditionAdapter_HandleEquals(const OverworldActorHandle *a,const OverworldActorHandle *b) {return a->slot==b->slot && a->generation==b->generation && a->fieldEpoch==b->fieldEpoch && a->mapGeneration==b->mapGeneration && a->encounterGeneration==b->encounterGeneration;}
static BOOL OverworldSpawnSpatial_IsCurrentMapObject(FieldSystem *f,LocalMapObject *o) {return f!=NULL && o!=NULL && o->owned;}
static int OverworldThrowBinding_PlayerX(FIELD_PLAYER_AVATAR *p) {return p->xCurr;}
static int OverworldThrowBinding_PlayerY(FIELD_PLAYER_AVATAR *p) {return p->yCurr;}
static const OverworldQueryCodeAddonEntry addon={.magic=OVERWORLD_QUERY_CODE_ADDON_MAGIC,.version=OVERWORLD_QUERY_CODE_ADDON_VERSION,.size=sizeof(OverworldQueryCodeAddonEntry),.bindingResolve=OverworldTargetBindings_Resolve};
static OverworldQueryCodeAddonState addonState;
static const OverworldQueryCodeAddonEntry *Acquire(const OverworldQueryCodeAddonOwner *o) {
    acquireCalls++;return o->fieldIdentity==(u32)(uintptr_t)gFieldSysPtr && o->fieldEpoch==3 && o->mapGeneration==4 ? &addon:NULL;
}
static OverworldQueryCodeAddonServiceEntry addonService;
static const OverworldBehaviorConditionServiceEntry gateService={.magic=OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,.version=OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION,.size=sizeof(OverworldBehaviorConditionServiceEntry)};
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE() (gateReady?&gateService:NULL)
#undef OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR ((uintptr_t)&addonService)
#undef OVERWORLD_QUERY_CODE_ADDON_STATE_ADDR
#define OVERWORLD_QUERY_CODE_ADDON_STATE_ADDR ((uintptr_t)&addonState)
static void Context(OverworldWildBehaviorContext *c,const OverworldWildSpawn *s,u16 species,u8 level,u8 terrain,u8 shiny) {(void)s;(void)species;(void)level;(void)terrain;(void)shiny;memset(c,0,sizeof(*c));contextWrites++;}
'''

BINDING_DRIVER = r'''
static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime;
static OverworldWildBehaviorConditionRuntime conditions;
static LocalMapObject objects[10],player;
static struct {u16 mapId;} location;
static FieldSystem field;
static OverworldActorHandle Handle(u16 slot) {OverworldActorHandle h={slot,(u16)(slot+1),3,4,(u16)(slot+11),0};return h;}
static void Capture(u8 name,u8 kind,u8 slot,u8 lifetime,u16 duration) {
    OverworldBehaviorConditionEntryResult e={0};e.active=e.triggered=e.conditionTrue=1;e.conditionId=20;e.applicationIndex=20;e.target.kind=kind;
    if(kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR)e.target.actor=conditions.actors[slot].subject;
    conditions.frame.world.subject=conditions.actors[7].subject;
    assert(OverworldTargetBindings_CaptureEntry(&conditions.bindings[7],&conditions.frame.world,&conditions.actors[7].subject,&e,name,lifetime,duration)==0);
}
static void Init(void) {
    memset(&state,0,sizeof(state));memset(&conditions,0,sizeof(conditions));memset(&runtime,0,sizeof(runtime));
    currentFrame=100;contextWrites=inspectCalls=acquireCalls=0;inspectorReady=gateReady=TRUE;
    addonService=(OverworldQueryCodeAddonServiceEntry){.magic=OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC,.version=OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION,.size=sizeof(OverworldQueryCodeAddonServiceEntry),.state=&addonState,.acquire=Acquire};
    location.mapId=33;field.location=(void *)&location;field.playerAvatar=&player;player.xCurr=80;player.yCurr=81;gFieldSysPtr=&field;
    state.mapGeneration=4;state.movementFieldSystem=&field;state.movementRuntimeState=&runtime;runtime.conditions=&conditions;
    for(u16 i=0;i<10;i++){objects[i]=(LocalMapObject){10+i,20+i,MAPOBJECTFLAG_ACTIVE,i,1300,1,1};state.spawns[i]=(OverworldWildSpawn){&objects[i],1,33,i,(u16)(i+11)};conditions.actors[i].subject=nativeHandles[i]=Handle(i);conditions.actors[i].valid=1;}
    assert(OverworldBehaviorConditionAdapter_BuildFrame(&state,&field,&conditions,Context,OverworldThrowBinding_CurrentSpawn));
    conditions.frame.world.playerValid=TRUE;conditions.frame.world.playerX=80;conditions.frame.world.playerY=81;
    assert(OverworldTargetBindings_Init(&conditions.bindings[7],&conditions.actors[7].subject)==0);
    Capture(0,OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,0,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0);
    Capture(1,OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,1,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0);
}
int main(void) {
    OverworldTargetBindingPosition out;OverworldTargetBindingsState before;OverworldActorHandle saved;unsigned writes;
    /* The resident table and loaded package have separate version owners.
     * Run the real reader with service2 and the current package4 entry. */
    Init();assert(addonService.version==2 && addon.version==5);
    assert(addonService.version!=addon.version);
    assert(OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    assert(out.x==10 && out.y==20 && acquireCalls==1);
    Init();addonService.magic++;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(acquireCalls==0);
    Init();addonService.version=OVERWORLD_QUERY_CODE_ADDON_VERSION;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(acquireCalls==0);
    Init();addonService.size++;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(acquireCalls==0);
    Init();addonService.state=NULL;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(acquireCalls==0);
    Init();addonService.acquire=NULL;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(acquireCalls==0);
    Init();before=conditions.bindings[7];saved=conditions.frame.world.subject;writes=contextWrites;
    /* This is the actual ClearActor prefix of unrelated PrepareActor during
     * the20-frame windup. It invalidates the GLOBAL frame, not our bindings. */
    OverworldBehaviorConditionAdapter_ClearActor(&conditions,2);assert(!conditions.frame.valid);
    objects[0].xCurr=43;currentFrame=120;
    assert(OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    assert(out.x==43 && out.y==20 && conditions.frame.world.frame==120);
    assert(!conditions.frame.valid && contextWrites==writes);
    assert(!memcmp(&before,&conditions.bindings[7],sizeof(before)));
    assert(!memcmp(&saved,&conditions.frame.world.subject,sizeof(saved)));
    assert(OverworldThrowObservation_BindingPosition(&state,7,1,&out) && out.x==11);
    /* Full Evaluate must still rebuild all candidate contexts afterwards. */
    assert(OverworldBehaviorConditionAdapter_BuildFrame(&state,&field,&conditions,Context,OverworldThrowBinding_CurrentSpawn));
    assert(conditions.frame.valid && contextWrites>writes);
    /* Complete same-frame evaluation data keeps its native visibility bits. */
    Init();conditions.frame.world.actors[0].facingAndOcclusion=13;writes=contextWrites;
    assert(OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    assert(conditions.frame.valid && conditions.frame.world.actors[0].facingAndOcclusion==13 && contextWrites==writes);
    /* SAME-FRAME cached rows cannot grant a removed or invalid prepared actor. */
    Init();state.spawns[0].active=FALSE;OverworldWildSpawns_ClearConditionActorRecord(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();OverworldWildSpawns_ClearConditionActorRecord(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();objects[0].owned=FALSE;OverworldBehaviorConditionAdapter_ClearResolution(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();conditions.actors[0].subject.generation++;OverworldBehaviorConditionAdapter_ClearResolution(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();conditions.actors[0].subject.fieldEpoch++;OverworldBehaviorConditionAdapter_ClearResolution(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();state.spawns[0].encounterGeneration++;OverworldBehaviorConditionAdapter_ClearResolution(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();nativeHandles[7].generation++;OverworldBehaviorConditionAdapter_ClearResolution(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();conditions.actors[7].valid=FALSE;OverworldBehaviorConditionAdapter_ClearResolution(&conditions,0);assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();conditions.actors[7].subject.fieldEpoch++;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();state.mapGeneration++;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();gFieldSysPtr=NULL;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    /* Binding lifetime uses the ACTUAL current Actor clock after rebuild. */
    Init();assert(OverworldTargetBindings_Clear(&conditions.bindings[7],&conditions.actors[7].subject,0,OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)==0);
    Capture(0,OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR,0,OVERWORLD_TARGET_BINDING_FRAMES,20);
    currentFrame=119;assert(OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    currentFrame=120;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    /* PLAYER bindings read the current stock owner too, not old visibility. */
    Init();assert(OverworldTargetBindings_Clear(&conditions.bindings[7],&conditions.actors[7].subject,0,OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)==0);
    Capture(0,OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER,0,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0);
    player.xCurr=92;player.yCurr=93;assert(OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(out.x==92 && out.y==93);
    field.playerAvatar=NULL;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    Init();gateReady=FALSE;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));assert(acquireCalls==0);
    Init();inspectorReady=FALSE;assert(!OverworldThrowObservation_BindingPosition(&state,7,0,&out));
    puts("Actual binding reader: service2/package4, table guards, unrelated prepare, current identity, same-frame loss, expiry and Player freshness pass");return 0;
}
'''


class ThrowBindingFreshnessTests(unittest.TestCase):
    def test_actual_reader_refreshes_after_unrelated_prepare(self):
        result = run(binding_fixture(), 'throw-binding-freshness')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_invalid_cache_abort_is_rejected(self):
        current = OBSERVE.read_text()
        old_gate = 'if (conditions == NULL) return FALSE;'
        self.assertEqual(current.count(old_gate), 1)
        mutant = current.replace(old_gate,
            'if (conditions == NULL || !conditions->frame.valid) return FALSE;')
        result = run(binding_fixture(mutant), 'throw-binding-old-cache-abort')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('OverworldThrowObservation_BindingPosition(&state,7,0,&out)', result.stderr)

    def test_package_version_used_for_resident_service_is_rejected(self):
        current = OBSERVE.read_text()
        guard = 'service->version != OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION'
        self.assertEqual(current.count(guard), 1)
        mutant = current.replace(guard,
            'service->version != OVERWORLD_QUERY_CODE_ADDON_VERSION')
        result = run(binding_fixture(mutant), 'throw-binding-package-version-fault')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('OverworldThrowObservation_BindingPosition(&state,7,0,&out)', result.stderr)




HELD_LIFETIME_DRIVER = r"""
int main(void) {
    InitCase(TRUE);
    unsigned heldIndex, releaseIndex;
    for(heldIndex=0;heldIndex<blob->header.conditionEntryCount;heldIndex++) {
        const OverworldWildBehaviorConditionEntry *e=&blob->conditionEntries[heldIndex];
        if(e->kind==OW_WILD_BEHAVIOR_CONDITION_ACTOR_FACTS
            && e->terrainMask==(OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD|OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID)
            && e->terrainOverrideMask==OVERWORLD_BEHAVIOR_ACTOR_FACT_RECOVERING)break;
    }
    assert(heldIndex<blob->header.conditionEntryCount);
    const OverworldWildBehaviorConditionEntry *held=&blob->conditionEntries[heldIndex];
    assert(held->activationMode==OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE && held->durationFrames==0 && held->cooldownFrames==0);
    for(releaseIndex=0;releaseIndex<blob->header.conditionEntryCount;releaseIndex++) {
        const OverworldWildBehaviorConditionEntry *e=&blob->conditionEntries[releaseIndex];
        if(e->kind==OW_WILD_BEHAVIOR_CONDITION_ACTOR_FACTS
            && e->terrainMask==(OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD|OVERWORLD_BEHAVIOR_ACTOR_FACT_THROW_LINE|OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID))break;
    }
    assert(releaseIndex<blob->header.conditionEntryCount);
    assert(blob->conditionEntries[releaseIndex].activationMode==OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE);
    OverworldBehaviorConditionEntryState entryState={0};
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    OverworldBehaviorConditionCandidate candidates[3]={0};
    OverworldBehaviorConditionPreparedActor *prepared=&conditions.actors[0];
    prepared->catalogEntryIndexes[0]=heldIndex;prepared->states=&entryState;
    prepared->valid=1;prepared->stateCapacity=1;
    conditions.frame.world.subjectX=10;conditions.frame.world.subjectY=10;
    conditions.frame.world.actors[2].x=16;conditions.frame.world.actors[2].y=14;
    objects[3]=(LocalMapObject){.xCurr=16,.yCurr=14};
    profile.chillState=OW_WILD_BEHAVIOR_KIND_CHASE;
    profile.throwMaxRange=8;
    primitives.chillTarget=OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;
    for(unsigned n=0;n<3;n++){candidates[n].context.species=43;candidates[n].context.level=5;candidates[n].roleMask=OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD;}
    for(unsigned frame=100;frame<=2100;frame++) {
        conditions.frame.world.frame=frame;
        u32 facts=OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions);
        assert((facts&(OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD|OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID))==(OVERWORLD_BEHAVIOR_ACTOR_FACT_HELD|OVERWORLD_BEHAVIOR_ACTOR_FACT_TRIGGER_VALID));
        assert(!(facts&(OVERWORLD_BEHAVIOR_ACTOR_FACT_THROW_LINE|OVERWORLD_BEHAVIOR_ACTOR_FACT_RECOVERING)));
        conditions.frame.world.reserved[0]=facts&255;
        assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),prepared,&conditions.frame.world,candidates,3,1,&scratch,&result)==0);
        assert(result.activeApplicationMask==(1u<<held->applicationIndex));
        assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
        assert(runtime.throwState.targets[0]==(OW_WILD_HELPER_THROW_TARGET_ENCODE(1)|0x80));
        assert(runtime.throwState.carrierMask==1 && runtime.throwState.targetMask==2 && runtime.throwState.recoveringMask==0);
        assert(conditions.bindings[0].bindings[0].flags==OVERWORLD_TARGET_BINDING_BOUND && conditions.bindings[0].bindings[1].flags==OVERWORLD_TARGET_BINDING_BOUND);
        assert(releaseCalls==0 && normalizes==0 && state.movementCooldowns[0]==0);
    }
    /* An angled target newly within the existing L1 range admits release. */
    conditions.frame.world.frame++;
    conditions.frame.world.actors[2].x=14;conditions.frame.world.actors[2].y=12;
    objects[3]=(LocalMapObject){.xCurr=14,.yCurr=12};
    u32 facts=OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions);
    assert(facts&OVERWORLD_BEHAVIOR_ACTOR_FACT_THROW_LINE);
    prepared->catalogEntryIndexes[0]=releaseIndex;memset(&entryState,0,sizeof(entryState));
    conditions.frame.world.reserved[0]=facts&255;
    assert(OverworldBehaviorCondition_EvaluatePrepared(blob,sizeof(*blob),prepared,&conditions.frame.world,candidates,3,1,&scratch,&result)==0);
    assert(result.activeApplicationMask==(1u<<blob->conditionEntries[releaseIndex].applicationIndex));
    profile.chillState=OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR;profile.throwWindupFrames=20;profile.throwRecoveryFrames=60;
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    assert(state.movementCooldowns[0]==20 && (runtime.throwState.targets[0]&0x40));
    assert(runtime.throwState.recoveringMask==0);free(blob);
    /* Identity loss still runs the same real composed cleanup. */
    InitCase(TRUE);conditions.frame.world.actors[2].actor.generation++;
    assert(OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions)==0);Cleaned(TRUE);free(blob);
    InitCase(TRUE);conditions.frame.world.actors[0].actor.encounterGeneration++;
    assert(OverworldWildSpawns_GetInteractionObservation(&state,0,&profile,blob,&conditions)==0);Cleaned(TRUE);free(blob);
    puts("held search: 2001 valid frames, then line/windup; lost Trigger/Cargo cleanup pass");return 0;
}
"""

def held_lifetime_fixture():
    source = fixture()
    return source[:source.index('int main(void)', source.index('static OverworldActorHandle Handle'))] + HELD_LIFETIME_DRIVER




def replace(source, old, new):
    assert source.count(old) == 1, old
    return source.replace(old, new)

def atomic_handoff_fixture(source=None):
    if source is None:
        source = WILD.read_text()
    # Reuse the existing composed Throw scaffold and real binding reducer.
    pre = PRELUDE.replace(HOST_ACTOR_ROLE_STATE,
        'static const struct OverworldActorSystemState *ActorState(void);\n'
        'static const OverworldPickupRouteWildOps roleOps={.actorState=ActorState};')
    # This fixture supplies its own native route initializer and actor reader.
    start = pre.index("static void OverworldWildSpawns_InitRouteWorld(")
    end = pre.index("static void OverworldWildSpawns_InitCargoReadCall(", start)
    pre = pre[:start] + pre[end:]
    pre = replace(pre, 'typedef struct LocalMapObject { int xCurr,yCurr; u32 posVec[3]; }',
        'typedef struct LocalMapObject { int xCurr,yCurr; u32 flags, posVec[3]; }')
    pre = replace(pre, 'u8 active; u16 encounterGeneration; } OverworldWildSpawn;',
        'u8 active; u16 encounterGeneration; u32 personality; } OverworldWildSpawn;')
    pre = replace(pre, 's16 lastKnownX[10],lastKnownY[10];',
        's16 lastKnownX[10],lastKnownY[10]; u16 distanceDespawnPendingMask;')
    pre = replace(pre, 's16 movementCustomJumpTargetX[10],movementCustomJumpTargetY[10];',
        's16 movementCustomJumpTargetX[10],movementCustomJumpTargetY[10]; u8 movementEmotePlayHopSound[10];')
    pre = replace(pre, 's32 movementCustomJumpTargetBaseY[10];',
        's32 movementCustomJumpTargetBaseY[10]; u16 movementMotionIdentities[10]; u8 movementCustomJumpPrepActive[10],movementCustomJumpActive[10],movementCustomMotionModes[10]; struct {u8 phase;} returnMoves[10];')
    pre = replace(pre, 'u16 captureTargetMask,movementInProgressMask;',
        'u16 captureTargetMask,movementInProgressMask; u8 movementEmoteTimers[10],movementStagedHopPending[10],movementCrashShakeTimers[10],movementTeleportVisiblePause[10],movementTeleportHidden[10],movementTeleportFlickerTimers[10]; LocalMapObject *movementTeleportFlickerObjects[10]; s16 movementStagedHopTargetX[10],movementStagedHopTargetY[10]; int movementQueuedBattleSlot,pendingSlot;')
    pre = replace(pre, 'u16 (*clearPickupThrowState)',
        'BOOL (*startCarriedThrowTarget)(OverworldWildSpawnState *,OverworldWildThrowState *,OverworldWildPresentationState *,int,int);\n    u16 (*clearPickupThrowState)')
    pre = replace(pre, 'static const OverworldWildHelperOverlayEntry helper={OverworldWildHelper_ClearPickupThrowState};',
        'static BOOL OverworldWildHelper_StartCarriedThrowTarget(OverworldWildSpawnState *,OverworldWildThrowState *,OverworldWildPresentationState *,int,int);\nstatic const OverworldWildHelperOverlayEntry helper={OverworldWildHelper_StartCarriedThrowTarget,OverworldWildHelper_ClearPickupThrowState};')
    pre = replace(pre, 'u8 (*cargoReadTarget)(const OverworldCargoReadWildTargetCall *,OverworldCargoReadWildTarget *);',
        'u8 (*cargoReadTarget)(const OverworldCargoReadWildTargetCall *,OverworldCargoReadWildTarget *);\n    OverworldPickupRouteEdgeResult (*atomicPickup)(void *,const OverworldActorHandle *,const OverworldActorHandle *);')
    pre = replace(pre, 'static const OverworldQueryCodeAddonEntry entry={OverworldCargoReadWild_Options,OverworldCargoReadWild_Observe,OverworldCargoReadWild_Target,OverworldThrowObservationQuery_Observe,OverworldThrowHeldWild_Run,FixtureConditionNative};',
        'OverworldPickupRouteEdgeResult OverworldPickupRouteWild_AtomicPickup(void *,const OverworldActorHandle *,const OverworldActorHandle *);\nstatic const OverworldQueryCodeAddonEntry entry={OverworldCargoReadWild_Options,OverworldCargoReadWild_Observe,OverworldCargoReadWild_Target,OverworldPickupRouteWild_AtomicPickup,OverworldThrowObservationQuery_Observe,OverworldThrowHeldWild_Run,FixtureConditionNative};')
    pre = replace(pre, 'assert(s->movementActorControlModes[slot]==0);releaseCalls++;',
        'assert(s->movementActorControlModes[slot]<=1);releaseCalls++;')
    pre = replace(pre, 'static u32 OverworldWildSpawns_GetActiveConditionApplications(OverworldWildSpawnState *s,int slot) { (void)s;(void)slot;return 1; }',
        'static u32 OverworldWildSpawns_GetActiveConditionApplications(OverworldWildSpawnState *s,int slot) { (void)s;(void)slot;return 1; }')
    # Execute the actual Route union handoff. Tick remains a bounded engine
    # query seam and must receive options, never the Observe callback alias.
    route_stub = 'static OverworldPickupRouteStatus OverworldCargoReadWild_Route(const OverworldCargoQueryWildCall *call,OverworldCargoQueryResult *out) { (void)call;memset(out,0,sizeof(*out));out->status=routeStatus;out->eligibleActorMask=eligibleMask;return routeStatus; }'
    tick_seam = 'static OverworldPickupRouteStatus OverworldCargoReadWild_Route(const OverworldCargoQueryWildCall *,OverworldCargoQueryResult *);\nOverworldPickupRouteStatus OverworldCargoQueryWild_Tick(const OverworldCargoQueryWildCall *call,OverworldCargoQueryResult *out) { assert(call->options==OverworldCargoReadWild_Options(call->world));memset(out,0,sizeof(*out));out->status=routeStatus;out->eligibleActorMask=eligibleMask;return routeStatus; }'
    pre = replace(pre, route_stub, tick_seam)
    pre = replace(pre, 'out->route.hasNextStep=1;', 'out->route.hasNextStep=0;')
    pre = replace(pre, '#define OverworldWildSpawns_StartCarriedThrowTarget(...) FALSE', '')
    pre = replace(pre, '#define OverworldWildSpawns_TryStartSpawnerMovementCommand(...) FALSE',
        '#define OverworldWildSpawns_TryStartSpawnerMovementCommand(s,f,slot,...) FixtureStart(slot)')
    pre = replace(pre, '#define OverworldWildSpawns_TryStartChillWanderCommand(...) FALSE',
        '#define OverworldWildSpawns_TryStartChillWanderCommand(s,f,slot,...) FixtureStart(slot)')
    policy = (ROOT/'include/overworld_wild_movement.h').read_text()
    values = '\n'.join(re.search(r'typedef struct '+name+r'\s*\{[\s\S]*?\}\s*'+name+r';',policy).group(0) for name in ('OverworldWildWalkMomentumState','OverworldActorPolicyView'))
    pre = '#include "overworld_motion_model.h"\n#include "overworld_pickup_reach.h"\n'+values+'\n' + pre
    # Preserve the complete per-actor production scheduler, excluding only
    # its preceding global battle/overlap block (tested by existing owners).
    tick = extract_function(source, 'OverworldWildSpawns_TickMovementParams', 'void')
    prefix = tick[:tick.index('    state->movementFieldSystem = fieldSystem;')]
    loop_start = tick.index('    for (i = 0;')
    for token in ('    for (int pass =', 'visitGroup:', '    do {'):
        if token in tick:
            loop_start = min(loop_start, tick.index(token))
    tick = prefix + tick[loop_start:]
    defs = []
    for path in (WILD, ROOT/'include/overworld_wild_spawns_internal.h',
                 ROOT/'include/overworld_wild_movement.h',
                 ROOT/'include/overworld_behavior_condition_adapter.h'):
        for line in path.read_text().replace('\\\n', ' ').splitlines():
            if any(line.startswith('#define '+name+' ') or line.startswith('#define '+name+'(') for name in HANDOFF_NAMES):
                defs.append(line)
    bodies = [
        functions(ROOT/'src/overworld_actor_system_overlay/overworld_actor_system_overlay.c', [('ActorSystem_ReleaseTarget','void'),('ActorSystem_CancelActor','void')]),
        functions(HELPER, [('OverworldWildHelper_ClearPickupThrowState','u16')]),
        functions(WILD, [('OverworldWildSpawns_ReleaseHeldActorControl','void')]),
        functions(READ, [('OverworldCargoReadWild_Options','const OverworldWildBehaviorConditionOptions *')]),
        functions(WILD, [('OverworldWildSpawns_PickupOptions','const OverworldWildBehaviorConditionOptions *'),('OverworldWildSpawns_RetireClearedThrowBindings','void'),('OverworldWildSpawns_ClearThrowRelations','void'),('OverworldWildSpawns_ClearThrowStateForSlot','void'),('OverworldWildSpawns_AbortThrow','void')]),
        functions(QUERY_OBSERVE, [('PlayerHealthThrow_Line','BOOL'),('OverworldThrowObservationQuery_Observe','u32')]),
        functions(OBSERVE, [('OverworldThrowObservation_Observe','u32')]),
        functions(HELD, [('OverworldThrowHeldWild_ReleaseCargo','BOOL')]).replace(
            'static BOOL OverworldThrowHeldWild_ReleaseCargo(',
            'BOOL OverworldThrowHeldWild_ReleaseCargo('),
        functions(READ, [('OverworldCargoReadWild_Route','OverworldPickupRouteStatus'),('OverworldCargoReadWild_Observe','u32'),('OverworldCargoReadWild_Target','u8')]),
        functions(ROOT / "lib/overworld/overworld_pickup_route_wild.c", [('HandleMatches','BOOL'),('Bound','BOOL'),('PickupDelta','u32'),('PickupOrdinaryMotion','BOOL'),('OverworldPickupRouteWild_AtomicPickup','Result')]),
        functions(HELPER, [('OverworldWildHelper_StartCarriedThrowTarget','BOOL')]),
        functions(WILD, [('OverworldWildSpawns_ClearMovementSlotInProgress','void'),('OverworldWildSpawns_CancelCargoMotionForPickup','BOOL'),('OverworldWildSpawns_StartCarriedThrowTarget','BOOL')]),
        functions(HELD, [('OverworldThrowHeldWild_Run','BOOL')]).replace('static BOOL OverworldThrowHeldWild_Run(', 'BOOL OverworldThrowHeldWild_Run('),
        functions(WILD, [('OverworldWildSpawns_IsMovementSlotInProgress','BOOL'),('OverworldWildSpawns_GetInteractionObservation','u32'),('OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand','BOOL')]),
        functions(WILD, [('OverworldWildSpawns_GetControllerLane','const OverworldWildBehaviorProfileData *')]),
        functions(ROOT/'src/overworld_actor_system_overlay/overworld_actor_system_overlay.c',
                  [('OverworldActorSystem_SelectMovementLocomotion','u8')]),
        extract_function(source, 'OverworldWildSpawns_ResolveConditionsAtIntentBoundary','BOOL'),
        functions(WILD, [('OverworldWildSpawns_IssueIdleIntent','BOOL')]),
        tick,
    ]
    return '\n'.join([pre, '\n'.join(defs), HANDOFF_SUPPORT, *bodies, HANDOFF_DRIVER]).replace('static Result OverworldPickupRouteWild_AtomicPickup(', 'Result OverworldPickupRouteWild_AtomicPickup(')

HANDOFF_NAMES = ['OW_WILD_CONDITION_RESULT_TRIGGERED','OW_WILD_CONDITION_RESULT_TIMED_ENDED','OW_WILD_CONDITION_RESULT_PROFILE_CHANGED','OW_WILD_CONDITION_RESULT_FAIL_CLOSED','OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING','OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN','OW_WILD_SPAWN_AGGRO_PENDING_FLAG','OW_WILD_SPAWNER_SPOT_STATE_TIRED','OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TARGET_ENTERED','OVERWORLD_BEHAVIOR_CONDITION_WARM_CARGO']

HANDOFF_SUPPORT = r'''
/* These handoff cases use Throw, Walk and Hop. A Slam dispatch would make
 * their fixture invalid; never substitute a successful Slam admission. */
static BOOL OverworldWildSpawns_TryStartSlamHopCommand(
    OverworldWildSpawnState *state, int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldQueryCodeAddonEntry *entry, BOOL *handled)
{
    (void)state; (void)slot; (void)profile; (void)entry; (void)handled;
    assert(!"unexpected Slam dispatch in pickup handoff fixture");
    return FALSE;
}
#define OW_WILD_BEHAVIOR_REACTION_NONE 0
#define OW_WILD_RETURN_NONE 0
#define OverworldWildSpawns_SampleMovingNoticeForSlot(...) ((void)0)
#define OverworldWildSpawns_ClearPendingNotices(s,slot) ((void)(s),pendingClears[slot]++)
#define OverworldWildSpawns_GetCurrentMovementLocomotion OverworldActorSystem_SelectMovementLocomotion
#define MAPOBJECTFLAG_ACTIVE 1
#define MAPOBJECTFLAG_SINGLE_MOVEMENT 2
#define MAPOBJECTFLAG_UNK18 4
#define BIT_VANISH 8
#define OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(slot) ((u8)(((slot)+1)|0x80))
#define OW_WILD_SPAWNER_THROW_TARGET_DECODE(value) ((u8)(((value)&0x3F)-1))
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ 0
typedef OverworldPickupRouteEdgeResult Result;
#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL
#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED
#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID
#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED
typedef struct OverworldActorPolicyState { u16 pendingFirstPathAdvance,pendingLastPathAdvance; } OverworldActorPolicyState;
typedef struct OverworldActorRuntimeSlot { OverworldActorStateSnapshot snapshot; OverworldMotionState motion; OverworldActorPolicyState policy; } OverworldActorRuntimeSlot;
typedef struct OverworldActorSystemState { u16 fieldEpoch,mapGeneration; OverworldActorRuntimeSlot slots[10]; } OverworldActorSystemState;
static OverworldActorSystemState actors;
static OverworldWildBehaviorProfile profiles[10];
static OverworldWildBehaviorPrimitives primitiveValues[10];
static struct { u16 intentConditionsCheckedMask; } sOverworldWildFlags;
static unsigned visits[10], intentCalls[10], starts[10], pickups, carrier, cargoSlot, cancels,controls,pendingClears[10],shellFinishes,restores;
static BOOL cancelAccepted=TRUE,combatReady=TRUE,helperReady=TRUE;static u8 combatWork;
#define OverworldWildSpawns_GetHelperOverlayEntry() (helperReady?&helper:NULL)
static unsigned terminalOrder;
static BOOL supportReady=TRUE, serviceReady=TRUE, ownerCurrent=TRUE;
static u16 boundaryReceipt;
#define gOverworldActorSystemState actors
#define OVERWORLD_ACTOR_BOUNDARY_CANCEL (1u<<6)
#define OVERWORLD_COMBAT_NONE 0
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND 0x4A
static BOOL OverworldCombat_IsReady(void) {return combatReady;}
static u8 PrepareCombat(const OverworldWildSpawnState *s,u8 slot,OverworldMotionPlan *p) {(void)s;(void)p;assert(slot==cargoSlot);return combatWork;}
static const struct {u8 (*prepare)(const OverworldWildSpawnState *,u8,OverworldMotionPlan *);} combat={PrepareCombat};
#define OVERWORLD_COMBAT_ENTRY (&combat)
static BOOL OverworldWildSpawns_IsMovementFieldContextCurrent(OverworldWildSpawnState *s,FieldSystem *f) {return ownerCurrent && s->movementFieldSystem==f && f!=NULL;}
static void ActorSystem_WriteTerminalTrace(OverworldActorStateSnapshot *a,u16 event,u16 reason,u32 x,u32 y) {
    (void)reason;(void)x;(void)y;assert(a->handle.slot==cargoSlot);assert(event==OVERWORLD_ACTOR_EVENT_MOTION_CANCELED);
    assert(!terminalOrder);terminalOrder=1;cancels++;controls++;
}
static void ActorSystem_ReleaseTarget(OverworldActorStateSnapshot *);
static void ActorSystem_CancelActor(OverworldActorStateSnapshot *,u16);
static BOOL OverworldWildSpawns_AcknowledgeSharedMotion(int slot,u8 flags,u16 reason,OverworldMotionSample *sample,u8 *phase) {
    assert(slot==(int)cargoSlot && flags==OVERWORLD_ACTOR_BOUNDARY_CANCEL && sample==NULL);
    if(!cancelAccepted || !actors.slots[slot].snapshot.reservationId
        || actors.slots[slot].snapshot.reservationId!=boundaryReceipt) return FALSE;
    ActorSystem_CancelActor(&actors.slots[slot].snapshot,reason);*phase=actors.slots[slot].motion.phase;return TRUE;
}
static void OverworldWildSpawns_FinishPresentationCommand(LocalMapObject *o) {assert(terminalOrder==1);o->flags&=~MAPOBJECTFLAG_SINGLE_MOVEMENT;shellFinishes++;}
static BOOL OverworldWildSpawns_RunImmediateCanopyMovementCommand(LocalMapObject *o,u32 command) {(void)o;assert(command==0x4A && terminalOrder==1);restores++;return TRUE;}
static void OverworldWildSpawns_ClearStagedHopTargetLocal(OverworldWildSpawnState *s,int slot) {
    assert(slot==(int)cargoSlot && terminalOrder==1);s->movementStagedHopPending[slot]=0;s->movementStagedHopTargetX[slot]=s->movementStagedHopTargetY[slot]=0;
    s->movementRuntimeState->movementCustomJumpPrepActive[slot]=0;s->movementRuntimeState->movementCustomJumpActive[slot]=0;s->movementRuntimeState->movementCustomMotionModes[slot]=0;
}
static BOOL FixtureStart(int slot) {
    starts[slot]++; actors.slots[slot].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
    actors.slots[slot].snapshot.reservationId=30+slot; return TRUE;
}
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(OverworldWildSpawnState *s,int slot,OverworldWildBehaviorProfile *p,OverworldWildBehaviorPrimitives *pr) {
    (void)s;visits[slot]++;*p=profiles[slot];*pr=primitiveValues[slot];
}
static BOOL OverworldActorPolicy_Inspect(u8 slot,OverworldActorPolicyView *p) {
    memset(p,0,sizeof(*p));p->actorActive=1;p->motionPhase=actors.slots[slot].snapshot.motionPhase;return TRUE;
}
static u32 OverworldWildSpawns_GetInteractionObservation(OverworldWildSpawnState *,int,const OverworldWildBehaviorProfile *,const OverworldWildBehaviorDataBlob *,OverworldWildBehaviorConditionRuntime *);
static u16 OverworldWildSpawns_EvaluateConditionsForSlot(OverworldWildSpawnState *s,FieldSystem *f,int slot,OverworldWildBehaviorProfile *p,OverworldWildBehaviorPrimitives *pr,int operation) {
    (void)f;(void)operation;intentCalls[slot]++;*p=profiles[slot];if(pr)*pr=primitiveValues[slot];if((unsigned)slot==carrier)(void)OverworldWildSpawns_GetInteractionObservation(s,slot,p,blob,s->movementRuntimeState->conditions);return 0;
}
static const OverworldActorSystemState *ActorState(void) {return &actors;}
static BOOL CurrentObject(FieldSystem *f,LocalMapObject *o) {(void)f;return ownerCurrent && o!=NULL;}
static BOOL QuerySurface(FieldSystem *f,const OverworldWildSurfaceCatalog *catalog,int x,int y,OverworldWildSurfaceHit *hit) {(void)f;(void)catalog;(void)x;(void)y;(void)hit;return FALSE;}
static BOOL ResolveBase(FieldSystem *f,const OverworldWildSurfaceHit *hit,s32 origin,u32 flags,int x,int y,s32 *out) {(void)f;(void)hit;(void)flags;(void)x;(void)y;*out=origin;return supportReady;}
static OverworldPickupRouteEdgeResult Reach(void *raw,const OverworldPickupRoutePosition *a,const OverworldPickupRoutePosition *b) {(void)raw;return OverworldPickupReach_Check(a,b,1,2);}
static const OverworldPickupRouteWildOps ops={.version=OVERWORLD_PICKUP_ROUTE_WILD_VERSION,.size=sizeof(ops),.actorState=ActorState,.currentObject=CurrentObject,.querySurface=QuerySurface,.resolveBaseYAt=ResolveBase,.pickupReach=Reach};
const OverworldPickupRouteNativeSeams *OverworldPickupRouteWild_GetSeams(void *raw) {
    static const OverworldPickupRouteNativeSeams value={0};
    const OverworldPickupRouteWildWorld *w=raw;
    return serviceReady && w && w->field && w->ops==&ops?&value:NULL;
}
static void OverworldWildSpawns_InitRouteWorld(OverworldWildSpawnState *s,int slot,OverworldPickupRouteWildWorld *w) {memset(w,0,sizeof(*w));w->field=s->movementFieldSystem;w->state=s;w->slot=slot;w->ops=&ops;w->behaviorData=blob;}
static BOOL OverworldWildHelper_IsPickupThrowMovementContextCurrent(OverworldWildSpawnState *s) {return ownerCurrent && s->movementFieldSystem!=NULL;}
static BOOL OverworldWildHelper_IsExactObject(FieldSystem *f,OverworldWildSpawnState *s,int slot) {return CurrentObject(f,s->spawns[slot].object) && s->spawns[slot].active;}
static void OverworldWildHelper_SyncCarriedThrowTarget(FieldSystem *f,OverworldWildSpawnState *s,OverworldWildPresentationState *p,int c,int target) {(void)f;(void)p;assert(c==(int)carrier && target==(int)cargoSlot);assert(s->movementActorControlModes[target]==OW_WILD_ACTOR_CONTROL_HELD);assert(!actors.slots[target].snapshot.reservationId);if(cancels){assert(terminalOrder==1);terminalOrder=2;}pickups++;}
#define MapObject_SetBits(object,bits) ((object)->flags|=(bits))
#define MapObject_ClearBits(object,bits) ((object)->flags&=~(bits))
#define MapObject_IsSingleMovementActive(object) (((object)->flags&MAPOBJECTFLAG_SINGLE_MOVEMENT)!=0)
#define OverworldWildSpawns_HasPendingBattle(...) FALSE
#define OverworldWildSpawns_GetConditionRuntime(s) ((s)->movementRuntimeState->conditions)
#define OverworldWildSpawns_TryReservePickupTarget(...) FALSE
#define OverworldWildSpawns_GetThrowBindingBody(...) ((const LocalMapObject *)NULL)
#define OverworldWildSpawns_ApplyFacePlayerFacing(...) ((void)0)
#define OverworldWildSpawns_SyncCarriedThrowTarget(s,c,t) ((void)(s),(void)(c),(void)(t))
#define OverworldWildSpawns_EnsureFrameMovementTask(...) ((void)0)
#define OverworldWildSpawns_EnterAggroState(...) ((void)0)
#define OverworldWildSpawns_ApplyHelpChildSpawnState(...) ((void)0)
#define OverworldWildSpawns_ApplyQueuedCombat(...) FALSE
#define OverworldWildSpawns_TickCustomJumpRenderSettle(...) FALSE
#define OverworldWildSpawns_ContinuePendingStagedHop(...) ((void)0)
#define OverworldWildSpawns_CommitDeferredChainMovementPause(...) ((void)0)
#define OverworldWildSpawns_TickSpotEmote(...) FALSE
#define OverworldWildSpawns_TickTiredEmote(...) FALSE
#define OverworldWildSpawns_UpdateSpawnMoveTargetState(...) FALSE
#define OverworldWildSpawns_StartTiredEmoteWithProfile(...) ((void)0)
#define OverworldWildSpawns_TryStartSpotEmote(s,slot,object,...) ((void)(s),(void)(slot),(void)(object),FALSE)
'''

HANDOFF_DRIVER = r'''
static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime;
static OverworldWildBehaviorConditionRuntime conditions;
static LocalMapObject objects[10], player;
static FieldSystem field={&player};
static OverworldActorHandle Handle(unsigned slot) {return (OverworldActorHandle){slot,1,3,4,11+slot,0};}
static void Bind(unsigned name,BOOL isPlayer) {
    OverworldBehaviorConditionEntryResult e={0};e.active=e.triggered=e.conditionTrue=1;e.conditionId=200+name;e.applicationIndex=20;
    e.target.kind=isPlayer?OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER:OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    if(!isPlayer)e.target.actor=Handle(cargoSlot);
    assert(OverworldTargetBindings_CaptureEntry(&conditions.bindings[carrier],&conditions.frame.world,&conditions.actors[carrier].subject,&e,name,OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_OK);
}
static void Reset(unsigned carrierSlot,unsigned target) {
    carrier=carrierSlot;cargoSlot=target;
    memset(&state,0,sizeof(state));memset(&runtime,0,sizeof(runtime));memset(&conditions,0,sizeof(conditions));memset(&actors,0,sizeof(actors));memset(objects,0,sizeof(objects));
    memset(profiles,0,sizeof(profiles));memset(primitiveValues,0,sizeof(primitiveValues));memset(&sOverworldWildFlags,0,sizeof(sOverworldWildFlags));
    memset(visits,0,sizeof(visits));memset(starts,0,sizeof(starts));memset(intentCalls,0,sizeof(intentCalls));pickups=releaseCalls=cancels=controls=shellFinishes=restores=terminalOrder=0;memset(pendingClears,0,sizeof(pendingClears));
    cancelAccepted=combatReady=helperReady=TRUE;combatWork=0;boundaryReceipt=0;
    supportReady=serviceReady=ownerCurrent=TRUE;routeStatus=OVERWORLD_PICKUP_ROUTE_REACHABLE;eligibleMask=1u<<target;
    state.movementFieldSystem=&field;state.movementRuntimeState=&runtime;state.movementQueuedBattleSlot=state.pendingSlot=-1;runtime.conditions=&conditions;actors.fieldEpoch=3;actors.mapGeneration=4;
    blob=malloc(sizeof(*blob));assert(blob);memcpy(blob,&gOverworldWildBehaviorDataBlob,sizeof(*blob));
    conditions.frame.valid=1;conditions.frame.world.frame=100;conditions.frame.world.subject=Handle(carrier);conditions.frame.world.playerValid=1;conditions.frame.world.playerX=7;conditions.frame.world.playerY=10;conditions.frame.world.actorCount=2;
    for(unsigned n=0;n<2;n++) {
        unsigned slot=n?target:carrierSlot;objects[slot].xCurr=10+n;objects[slot].yCurr=10;objects[slot].flags=MAPOBJECTFLAG_ACTIVE;objects[slot].posVec[1]=65536;objects[slot].posVec[0]=(10+n)*0x10000+0x8000;objects[slot].posVec[2]=10*0x10000+0x8000;
        state.spawns[slot]=(OverworldWildSpawn){&objects[slot],1,11+slot,100+slot};conditions.actors[slot].subject=Handle(slot);
        actors.slots[slot].snapshot=(OverworldActorStateSnapshot){.active=1,.handle=Handle(slot),.subjectIdentity=100+slot,.role=OVERWORLD_ACTOR_ROLE_WILD,.motionPhase=OVERWORLD_ACTOR_PHASE_IDLE};
        conditions.frame.world.actors[n].actor=Handle(slot);conditions.frame.world.actors[n].valid=1;conditions.frame.world.actors[n].x=10+n;conditions.frame.world.actors[n].y=10;
        profiles[slot].owner.chillAllowedTerrainMask=OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;profiles[slot].owner.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
        primitiveValues[slot].chillLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;primitiveValues[slot].chillTarget=OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY;
    }
    conditions.actors[carrier].count=1;
    unsigned idx=0;for(;idx<blob->header.conditionEntryCount;idx++)if(blob->conditionOptions[idx].captureBinding==2&&blob->conditionOptions[idx].mustBeReachableForPickup&&(blob->conditionOptions[idx].subjectRoleMask&(carrierSlot==OW_WILD_FOLLOWER_SLOT?2:1)))break;
    assert(idx<blob->header.conditionEntryCount);conditions.actors[carrier].catalogEntryIndexes[0]=idx;blob->conditionOptions[idx].pickupHeight=2;
    assert(OverworldTargetBindings_Init(&conditions.bindings[carrier],&conditions.actors[carrier].subject)==OVERWORLD_TARGET_BINDING_OK);
    Bind(OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST,TRUE);Bind(OVERWORLD_TARGET_BINDING_CARGO,FALSE);
    conditions.bindings[carrier].bindings[OVERWORLD_TARGET_BINDING_CARGO].sourceConditionId=blob->conditionEntries[idx].conditionId;
    if(carrierSlot==OW_WILD_FOLLOWER_SLOT)actors.slots[carrier].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
    runtime.throwState.targets[carrier]=OW_WILD_HELPER_THROW_TARGET_ENCODE(target);runtime.throwState.carrierMask=1u<<carrier;runtime.throwState.targetMask=1u<<target;
    profiles[carrier].onReachAction=OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR;
    primitiveValues[carrier].chillLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;primitiveValues[carrier].chillTarget=OW_WILD_BEHAVIOR_TARGET_CARGO;
}
static void MovingCargo(u8 kind) {
    OverworldActorRuntimeSlot *slot=&actors.slots[cargoSlot];
    slot->snapshot.motionKind=kind;slot->snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
    slot->snapshot.reservationId=28;slot->snapshot.inputOwnership=1;
    slot->motion.phase=OVERWORLD_MOTION_PHASE_MOVING;
    slot->motion.plan=(OverworldMotionPlan){.version=OVERWORLD_MOTION_MODEL_VERSION,
        .kind=kind,.fieldEpoch=Handle(cargoSlot).fieldEpoch,.startX=11,.startY=10,
        .targetX=12,.targetY=10,.startBaseY=65536,.targetBaseY=65536,
        .duration=16,.reservationId=28};
    runtime.movementMotionIdentities[cargoSlot]=boundaryReceipt=28;
    runtime.movementCustomJumpActive[cargoSlot]=1;runtime.movementCustomMotionModes[cargoSlot]=kind;
    runtime.movementCustomJumpPrepActive[cargoSlot]=kind==OVERWORLD_MOTION_KIND_HOP;runtime.returnMoves[cargoSlot].phase=1;
    state.movementInProgressMask=1u<<cargoSlot;
    objects[cargoSlot].flags|=MAPOBJECTFLAG_SINGLE_MOVEMENT;
}
static void Tick(u16 mask) {OverworldWildSpawns_TickMovementParams(&state,&field,TRUE,mask);}
static void Done(void) {for(unsigned n=0;n<10;n++)assert(visits[n]<=1);free(blob);}
int main(void) {
    for(unsigned reverse=0;reverse<2;reverse++) {
        Reset(reverse?0:1,reverse?1:0);Tick(3);
        assert(pickups==1 && state.movementActorControlModes[cargoSlot]==OW_WILD_ACTOR_CONTROL_HELD);
        assert(runtime.throwState.targets[carrier]==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(cargoSlot));
        assert(starts[cargoSlot]==0 && actors.slots[cargoSlot].snapshot.motionPhase==OVERWORLD_ACTOR_PHASE_IDLE);Done();
        /* Support unavailable => Atomic DEFERRED,
         * but the same normal Cargo START still runs. No forced idle dwell. */
        Reset(reverse?0:1,reverse?1:0);supportReady=FALSE;Tick(3);
        assert(pickups==0 && starts[cargoSlot]==1 && state.movementActorControlModes[cargoSlot]==0);Done();
        /* A bound Cargo's accepted step has completed. The route may still
         * be PENDING after its occupancy/reservation revision changes. The
         * current physical Atomic gate must win before Cargo starts again. */
        for(unsigned walk=0;walk<2;walk++) {
            Reset(reverse?0:1,reverse?1:0);routeStatus=OVERWORLD_PICKUP_ROUTE_PENDING;
            if(walk)primitiveValues[carrier].chillLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_WALK;
            actors.slots[cargoSlot].snapshot.commitSequence=14;
            Tick(3);
            assert(pickups==1 && starts[cargoSlot]==0);
            assert(state.movementActorControlModes[cargoSlot]==OW_WILD_ACTOR_CONTROL_HELD);
            assert(actors.slots[cargoSlot].snapshot.commitSequence==14);Done();
        }
        Reset(reverse?0:1,reverse?1:0);routeStatus=OVERWORLD_PICKUP_ROUTE_PENDING;
        objects[cargoSlot].xCurr=15;conditions.frame.world.actors[1].x=15;Tick(3);
        assert(pickups==0 && starts[cargoSlot]==1);Done();
        Reset(reverse?0:1,reverse?1:0);routeStatus=OVERWORLD_PICKUP_ROUTE_PENDING;
        supportReady=FALSE;Tick(3);assert(pickups==0 && starts[cargoSlot]==1);Done();
        Reset(reverse?0:1,reverse?1:0);routeStatus=OVERWORLD_PICKUP_ROUTE_PENDING;
        objects[cargoSlot].posVec[1]+=3u<<12;Tick(3);
        assert(pickups==0 && starts[cargoSlot]==1);Done();
        /* A physical neighbor cannot bypass a failed route/query contract. */
        for(unsigned failure=OVERWORLD_PICKUP_ROUTE_UNREACHABLE;
            failure<=OVERWORLD_PICKUP_ROUTE_RESOURCE_LIMIT;failure++) {
            Reset(reverse?0:1,reverse?1:0);routeStatus=(OverworldPickupRouteStatus)failure;Tick(3);
            assert(pickups==0 && starts[cargoSlot]==1 && runtime.throwState.targets[carrier]==0);Done();
        }
        /* None of the accepted-motion gates can be skipped by this handoff.
         * Keep each blocked Cargo's current command and reservation intact. */
        for(unsigned guard=0;guard<4;guard++) {
            Reset(reverse?0:1,reverse?1:0);routeStatus=OVERWORLD_PICKUP_ROUTE_PENDING;
            state.movementInProgressMask=1u<<cargoSlot;
            if(guard==0)actors.slots[cargoSlot].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
            if(guard==1)actors.slots[cargoSlot].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_COMMIT_PENDING;
            if(guard==2)actors.slots[cargoSlot].snapshot.reservationId=28;
            if(guard==3)objects[cargoSlot].flags|=MAPOBJECTFLAG_SINGLE_MOVEMENT;
            OverworldActorStateSnapshot before=actors.slots[cargoSlot].snapshot;
            u32 flags=objects[cargoSlot].flags;Tick(3);
            assert(pickups==0 && starts[cargoSlot]==0 && state.movementActorControlModes[cargoSlot]==0);
            assert(memcmp(&before,&actors.slots[cargoSlot].snapshot,sizeof(before))==0 && objects[cargoSlot].flags==flags);
            assert(state.movementInProgressMask==(1u<<cargoSlot));Done();
        }
        Reset(reverse?0:1,reverse?1:0);state.movementCooldowns[carrier]=2;Tick(3);
        assert(pickups==0 && starts[cargoSlot]==1 && state.movementCooldowns[carrier]==1);Done();
        Reset(reverse?0:1,reverse?1:0);sOverworldWildFlags.intentConditionsCheckedMask=1u<<carrier;Tick(3);
        assert(pickups==0 && starts[cargoSlot]==1);Done();
        Reset(reverse?0:1,reverse?1:0);Tick(1u<<cargoSlot);
        assert(pickups==0 && starts[cargoSlot]==1 && visits[carrier]==0);Done();
        Reset(reverse?0:1,reverse?1:0);actors.slots[carrier].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;Tick(3);
        assert(pickups==0 && starts[cargoSlot]==1);Done();
        for(unsigned fault=0;fault<6;fault++) {
            Reset(reverse?0:1,reverse?1:0);
            if(fault==0)conditions.frame.world.playerValid=0;
            if(fault==1)conditions.frame.world.actors[1].actor.generation++;
            if(fault==2)actors.slots[cargoSlot].snapshot.handle.generation++;
            if(fault==3)runtime.throwState.targetMask=0;
            if(fault==4)ownerCurrent=FALSE;
            if(fault==5)runtime.throwState.targets[carrier]=OW_WILD_HELPER_THROW_TARGET_ENCODE(2);
            Tick(3);assert(pickups==0 && starts[cargoSlot]==1);Done();
        }
    }
    Reset(OW_WILD_FOLLOWER_SLOT,0);routeStatus=OVERWORLD_PICKUP_ROUTE_PENDING;
    actors.slots[carrier].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
    Tick((1u<<carrier)|(1u<<cargoSlot));
    assert(pickups==1 && starts[cargoSlot]==0 && state.movementActorControlModes[cargoSlot]==OW_WILD_ACTOR_CONTROL_HELD);Done();
    puts("actual Tick/idle/dispatch/bind/Atomic/HELD: both slot orders, current query, deferred Cargo START, full owner/claim/gates passed");
    return 0;
}
'''


class AtomicHandoffTests(unittest.TestCase):
    def test_reached_moving_cargo_hands_off_without_waiting_for_motion_end(self):
        driver = HANDOFF_DRIVER[:HANDOFF_DRIVER.index('int main(void)')] + r"""
static void UnchangedAttempt(void) {
    OverworldWildSpawnState beforeState=state;
    OverworldWildOverlayRuntimeState beforeRuntime=runtime;
    OverworldActorSystemState beforeActors=actors;
    LocalMapObject beforeObjects[10];memcpy(beforeObjects,objects,sizeof(objects));
    (void)OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,cargoSlot);
    assert(!pickups && !cancels && !controls && !shellFinishes && !restores);
    assert(memcmp(&beforeState,&state,sizeof(state))==0);
    assert(memcmp(&beforeRuntime,&runtime,sizeof(runtime))==0);
    assert(memcmp(&beforeActors,&actors,sizeof(actors))==0);
    assert(memcmp(beforeObjects,objects,sizeof(objects))==0);
}
static void PickedUp(u8 kind) {
    assert(pickups==1 && state.movementActorControlModes[cargoSlot]==OW_WILD_ACTOR_CONTROL_HELD);
    assert(runtime.throwState.targets[carrier]==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(cargoSlot));
    assert(actors.slots[cargoSlot].snapshot.reservationId==0 && cancels==1 && controls==1);
    assert(actors.slots[cargoSlot].snapshot.inputOwnership==0 && actors.slots[cargoSlot].motion.phase==OVERWORLD_MOTION_PHASE_CANCELED);
    assert(shellFinishes==1 && pendingClears[cargoSlot]==1 && runtime.returnMoves[cargoSlot].phase==0);
    assert(runtime.movementMotionIdentities[cargoSlot]==0 && state.movementInProgressMask==0);
    assert(!runtime.movementCustomJumpActive[cargoSlot] && !runtime.movementCustomJumpPrepActive[cargoSlot]);
    assert(!(objects[cargoSlot].flags&MAPOBJECTFLAG_SINGLE_MOVEMENT));
    assert(restores==(unsigned)(kind==OVERWORLD_MOTION_KIND_HOP) && terminalOrder==2);
}
static void DeferredDispatch(void) {
    OverworldWildSpawnState beforeState=state;
    OverworldWildOverlayRuntimeState beforeRuntime=runtime;
    OverworldActorSystemState beforeActors=actors;
    OverworldWildBehaviorConditionRuntime beforeConditions=conditions;
    LocalMapObject beforeObjects[10];memcpy(beforeObjects,objects,sizeof(objects));
    /* Real accepted-motion/physical gate must report waiting to its caller.
     * REACHABLE with no next edge must not turn that wait into AbortThrow. */
    assert(OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,cargoSlot));
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(
        &state,carrier,&objects[carrier],&profiles[carrier],&primitiveValues[carrier]));
    assert(!pickups && !cancels && !controls && !shellFinishes && !restores);
    assert(state.movementCooldowns[carrier]==1);
    state.movementCooldowns[carrier]=beforeState.movementCooldowns[carrier];
    assert(memcmp(&beforeState,&state,sizeof(state))==0);
    assert(memcmp(&beforeRuntime,&runtime,sizeof(runtime))==0);
    assert(memcmp(&beforeActors,&actors,sizeof(actors))==0);
    assert(memcmp(&beforeConditions,&conditions,sizeof(conditions))==0);
    assert(memcmp(beforeObjects,objects,sizeof(objects))==0);
}
static void PickupAfterWait(u8 kind) {
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(
        &state,carrier,&objects[carrier],&profiles[carrier],&primitiveValues[carrier]));
    PickedUp(kind);
}
int main(void) {
    for(unsigned kind=OVERWORLD_MOTION_KIND_WALK;kind<=OVERWORLD_MOTION_KIND_HOP;kind++) {
        for(unsigned reverse=0;reverse<2;reverse++) {
            for(unsigned phase=OVERWORLD_ACTOR_PHASE_MOVING;phase<=OVERWORLD_ACTOR_PHASE_SETTLING;phase++) {
                Reset(reverse?1:0,reverse?0:1);MovingCargo(kind);
                actors.slots[cargoSlot].snapshot.motionPhase=actors.slots[cargoSlot].motion.phase=phase;
                /* A full staged ordinary leg is valid; an intermediate leg is not. */
                state.movementStagedHopPending[cargoSlot]=kind==OVERWORLD_MOTION_KIND_WALK?3:1;
                state.movementStagedHopTargetX[cargoSlot]=12;state.movementStagedHopTargetY[cargoSlot]=10;
                OverworldActorRuntimeSlot carrierBefore=actors.slots[carrier];
                Tick(3);PickedUp(kind);
                assert(memcmp(&carrierBefore,&actors.slots[carrier],sizeof(carrierBefore))==0);Done();
            }
        }
        /* Logical tile reach is insufficient while the real moving body is
         * outside horizontal reach. No command, token or claim is touched. */
        Reset(0,1);MovingCargo(kind);objects[cargoSlot].posVec[0]+=1;
        UnchangedAttempt();DeferredDispatch();objects[cargoSlot].posVec[0]-=1;
        PickupAfterWait(kind);Done();
        Reset(0,1);MovingCargo(kind);objects[cargoSlot].posVec[2]+=0x10001;
        UnchangedAttempt();DeferredDispatch();objects[cargoSlot].posVec[2]-=0x10001;
        PickupAfterWait(kind);Done();
        /* A Hop's real arc counts in authored height. Grounded tile support
         * does not make a body above the limit pickable. */
        Reset(0,1);MovingCargo(kind);objects[cargoSlot].posVec[1]+=(2u<<12)+1;
        UnchangedAttempt();
        /* This host support receipt includes the height, so the earlier
         * authored support/reach guard still rejects it. */
        assert(!OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,cargoSlot));
        objects[cargoSlot].posVec[1]-=1;
        PickupAfterWait(kind);Done();
        for(unsigned guard=0;guard<34;guard++) {
            Reset(0,1);MovingCargo(kind);
            OverworldActorRuntimeSlot *target=&actors.slots[cargoSlot];
            switch(guard) {
            case 0: target->motion.plan.flags=OVERWORLD_MOTION_FLAG_FORCED;break;
            case 1: target->motion.plan.kind=target->snapshot.motionKind=OVERWORLD_MOTION_KIND_FLY_IN;break;
            case 2: target->motion.plan.kind=target->snapshot.motionKind=OVERWORLD_MOTION_KIND_REPOSITION;break;
            case 3: target->motion.plan.kind=target->snapshot.motionKind=OVERWORLD_MOTION_KIND_TELEPORT;break;
            case 4: target->motion.plan.kind=target->snapshot.motionKind=OVERWORLD_MOTION_KIND_SKID;break;
            case 5: target->motion.plan.reservationId++;break;
            case 6: runtime.movementMotionIdentities[cargoSlot]++;break;
            case 7: target->snapshot.reservationId=0;break;
            case 8: target->motion.plan.fieldEpoch++;break;
            case 9: target->motion.plan.version++;break;
            case 10: target->motion.phase=OVERWORLD_MOTION_PHASE_SUSPENDED;break;
            case 11: target->motion.plan.visibilityPolicy=OVERWORLD_MOTION_VISIBILITY_HIDDEN;break;
            case 12: state.movementSpawnRunActive[cargoSlot]=3;break;
            case 13: state.movementCrashShakeTimers[cargoSlot]=1;break;
            case 14: state.movementTeleportHidden[cargoSlot]=1;break;
            case 15: state.movementTeleportFlickerTimers[cargoSlot]=1;break;
            case 16: state.movementTeleportFlickerObjects[cargoSlot]=&player;break;
            case 17: state.movementQueuedBattleSlot=cargoSlot;break;
            case 18: state.pendingSlot=cargoSlot;break;
            case 19: target->snapshot.handle.generation++;break;
            case 20: target->snapshot.subjectIdentity++;break;
            case 21: state.spawns[cargoSlot].encounterGeneration++;break;
            case 22: runtime.throwState.targets[cargoSlot]=OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(2);break;
            case 23: runtime.throwState.targetMask=0;break;
            case 24: runtime.throwState.carrierMask=0;break;
            case 25: state.movementActorControlModes[cargoSlot]=OW_WILD_ACTOR_CONTROL_HELD;break;
            case 26: state.movementStagedHopPending[cargoSlot]=2;break;
            case 27: state.movementStagedHopPending[cargoSlot]=kind==OVERWORLD_MOTION_KIND_WALK?3:1;state.movementStagedHopTargetX[cargoSlot]=13;break;
            case 28: supportReady=FALSE;break;
            case 29: cancelAccepted=FALSE;break;
            case 30: helperReady=FALSE;break;
            case 31: combatReady=FALSE;break;
            case 32: runtime.throwState.targets[2]=OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(cargoSlot);break;
            case 33: state.captureTargetMask=1u<<cargoSlot;break;
            }
            UnchangedAttempt();Done();
        }
        for(unsigned work=1;work<=4;work++) {
            Reset(0,1);MovingCargo(kind);combatWork=work;UnchangedAttempt();Done();
        }
        /* Idle physical failure remains terminal, with the same normal
         * caller cleanup. It cannot gain moving-Cargo wait credit. */
        Reset(0,1);objects[cargoSlot].posVec[0]+=1;
        assert(!OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,cargoSlot));
        assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(
            &state,carrier,&objects[carrier],&profiles[carrier],&primitiveValues[carrier]));
        assert(!pickups && !cancels && !controls);
        assert(runtime.throwState.targets[carrier]==OW_WILD_HELPER_THROW_TARGET_NONE);
        assert(!conditions.bindings[carrier].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags);
        assert(!conditions.bindings[carrier].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags);
        Done();
        /* A carrier's accepted move keeps its token and input. */
        Reset(0,1);MovingCargo(kind);
        actors.slots[carrier].snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
        actors.slots[carrier].snapshot.reservationId=99;
        UnchangedAttempt();Done();
        Reset(OW_WILD_FOLLOWER_SLOT,0);MovingCargo(kind);
        Tick((1u<<carrier)|(1u<<cargoSlot));PickedUp(kind);Done();
    }
    puts("real Actor cancel before HELD: moving Walk/Hop, physical reach/arc, full tokens, failed handoff unchanged");return 0;
}
"""
        source = atomic_handoff_fixture().replace(HANDOFF_DRIVER, driver)
        result = run(source, "throw-moving-handoff")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_terminal_cargo_and_carrier_share_the_original_atomic_pickup(self):
        result = run(atomic_handoff_fixture(), "throw-terminal-handoff")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)




CARGO_SEARCH_TARGET_DRIVER = r"""
static unsigned bindingReads;
static int PlayerX(LocalMapObject *o) { return o->xCurr; }
static int PlayerY(LocalMapObject *o) { return o->yCurr; }
static BOOL CurrentSpawn(FieldSystem *f,const OverworldWildSpawn *s) {
    return f!=NULL && s->active && s->object!=NULL;
}
static BOOL QueryTarget(OverworldWildSpawnState *s,int a,int b,u8 q,u32 mask) {
    (void)s;(void)a;(void)b;(void)q;(void)mask;assert(!"unexpected target query");return FALSE;
}
static BOOL BindingPosition(OverworldWildSpawnState *s,u8 slot,u8 name,
    OverworldTargetBindingPosition *out) {
    bindingReads++;
    OverworldWildBehaviorConditionRuntime *c=s->movementRuntimeState->conditions;
    if(c==NULL)return FALSE;
    OverworldBehaviorConditionWorldView world=c->frame.world;
    world.subject=c->actors[slot].subject;
    return OverworldTargetBindings_Resolve(&c->bindings[slot],&world,name,out)==OVERWORLD_TARGET_BINDING_OK;
}
static OverworldActorHandle Handle(u8 slot) {
    return (OverworldActorHandle){slot,2,3,4,5,0};
}
int main(void) {
    OverworldWildSpawnState state={0};OverworldWildOverlayRuntimeState runtime={0};
    OverworldWildBehaviorConditionRuntime conditions={0};
    LocalMapObject owner={.xCurr=10,.yCurr=10},cargo={.xCurr=12,.yCurr=10},player={.xCurr=20,.yCurr=20};
    FieldSystem field={&player};OverworldWildBehaviorProfile profile={0};
    const PlayerHealthThrowServiceEntry service={NULL,BindingPosition};
    const OverworldCargoReadWildTargetOps ops={PlayerX,PlayerY,CurrentSpawn,QueryTarget,NULL,NULL};
    OverworldCargoReadWildTargetCall call={&state,&owner,&profile,&service,&ops,
        0,OW_WILD_BEHAVIOR_TARGET_CARGO,OW_WILD_HELPER_THROW_TARGET_NONE,0};
    OverworldCargoReadWildTarget out={0};
    state.movementFieldSystem=&field;state.movementRuntimeState=&runtime;runtime.conditions=&conditions;
    state.spawns[0]=(OverworldWildSpawn){&owner,1,5};state.spawns[1]=(OverworldWildSpawn){&cargo,1,5};
    conditions.actors[0].subject=Handle(0);conditions.frame.world.subject=Handle(0);
    conditions.frame.world.frame=100;conditions.frame.world.actorCount=1;
    conditions.frame.world.actors[0].valid=1;conditions.frame.world.actors[0].actor=Handle(1);
    conditions.frame.world.actors[0].x=cargo.xCurr;conditions.frame.world.actors[0].y=cargo.yCurr;
    assert(OverworldTargetBindings_Init(&conditions.bindings[0],&conditions.actors[0].subject)==OVERWORLD_TARGET_BINDING_OK);
    OverworldTargetBinding *binding=&conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO];
    /* Empty unclaimed search returns NONE before any resolver call. The
     * production dispatcher aborts only ABORT; no pose/claim is changed here. */
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_NONE);
    assert(bindingReads==0 && runtime.throwState.targets[0]==0 && runtime.throwState.carrierMask==0);
    assert(owner.xCurr==10 && owner.yCurr==10 && cargo.xCurr==12 && cargo.yCurr==10);
    for(unsigned held=0;held<2;held++) {
        call.throwTarget=OW_WILD_HELPER_THROW_TARGET_ENCODE(1)|(held?OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG:0);
        bindingReads=0;
        assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
        assert(bindingReads==1); /* Missing binding cannot hide a claim or HELD. */
    }
    call.throwTarget=OW_WILD_HELPER_THROW_TARGET_NONE;
    binding->flags=0x80;bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
    assert(bindingReads==1);binding->flags=0;
    call.throwService=NULL;bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
    assert(bindingReads==0);call.throwService=&service;
    runtime.conditions=NULL;bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
    assert(bindingReads==1);runtime.conditions=&conditions;
    call.movementTarget=OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
    assert(bindingReads==1);call.movementTarget=OW_WILD_BEHAVIOR_TARGET_CARGO;
    OverworldBehaviorConditionEntryResult admitted={0};
    admitted.active=admitted.conditionTrue=admitted.triggered=1;admitted.conditionId=1;admitted.applicationIndex=1;
    admitted.target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;admitted.target.actor=Handle(1);
    assert(OverworldTargetBindings_CaptureEntry(&conditions.bindings[0],&conditions.frame.world,
        &conditions.actors[0].subject,&admitted,OVERWORLD_TARGET_BINDING_CARGO,
        OVERWORLD_TARGET_BINDING_UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_OK);
    bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_VALID);
    assert(bindingReads==1 && out.playerX==12 && out.playerY==10 && out.dx==2 && out.dy==0);
    conditions.frame.world.actors[0].actor.generation++;bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
    assert(bindingReads==1); /* The real binding reducer rejects a stale full target. */
    conditions.frame.world.actors[0].actor=Handle(1);conditions.actors[0].subject.generation++;bindingReads=0;
    assert(OverworldCargoReadWild_Target(&call,&out)==OVERWORLD_CARGO_READ_TARGET_ABORT);
    assert(bindingReads==1); /* The real binding reducer also checks the current owner. */
    puts("Cargo target search: exact empty NONE; claimed/held/stale/unknown/unavailable cases ABORT; valid full binding unchanged");
    return 0;
}
"""


def cargo_search_target_fixture():
    # Reuse only the existing named engine-read seams. Target is the actual
    # production body; current subject/target resolution is the real reducer.
    prelude = PRELUDE.split("static u16 OverworldWildHelper_ClearPickupThrowState", 1)[0]
    return "\n".join((prelude, functions(READ, [("OverworldCargoReadWild_Target", "u8")]), CARGO_SEARCH_TARGET_DRIVER))


class CargoSearchTargetTests(unittest.TestCase):
    def test_empty_search_preserves_claim_and_current_binding_guards(self):
        result = run(cargo_search_target_fixture(), "cargo-search-target")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_or_broad_empty_search_guard_is_rejected(self):
        source = cargo_search_target_fixture()
        guard = """if(target==OW_WILD_BEHAVIOR_TARGET_CARGO
            && relation==OW_WILD_HELPER_THROW_TARGET_NONE
            && call->throwService!=NULL
            && runtime->conditions!=NULL
            && runtime->conditions->bindings[slot].bindings[name].flags==0)
            return OVERWORLD_CARGO_READ_TARGET_NONE;"""
        self.assertEqual(source.count(guard), 1)
        faults = (
            ("old-abort", source.replace(guard, "/* old path always resolves */")),
            ("claimed-empty", source.replace("&& relation==OW_WILD_HELPER_THROW_TARGET_NONE\n", "\n")),
            ("unknown-flags", source.replace("runtime->conditions->bindings[slot].bindings[name].flags==0)", "(runtime->conditions->bindings[slot].bindings[name].flags&OVERWORLD_TARGET_BINDING_BOUND)==0)")),
            ("missing-service", source.replace("&& call->throwService!=NULL\n", "\n")),
        )
        for name, mutant in faults:
            with self.subTest(name=name):
                self.assertNotEqual(mutant, source)
                result = run(mutant, "cargo-search-target-" + name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("OverworldCargoReadWild_Target", result.stderr)


def away_launch_fixture():
    source = fixture()
    prefix = source.split("int main(void) {", 1)[0]
    return prefix + "int main(void) {\n" + AWAY_LAUNCH_DRIVER + "return 0;\n}\n"


def role_options_fixture():
    source = fixture().split("static OverworldActorHandle Handle", 1)[0]
    return source + ROLE_OPTIONS_DRIVER


AWAY_LAUNCH_DRIVER = r"""
    InitCase(TRUE);profile.chillState=OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR;
    profile.chillTarget=OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE;profile.throwMaxRange=3;
    primitives.chillTarget=profile.chillTarget;primitives.chillLocomotion=0;
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    assert(selectCalls==1&&validateCalls==0&&flightCalls==0);
    assert(runtime.movementCustomJumpTargetX[0]==13&&runtime.movementCustomJumpTargetY[0]==10&&runtime.movementCustomJumpTargetBaseY[0]==24576);
    assert(runtime.throwState.targets[0]&0x40);
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    assert(selectCalls==1&&validateCalls==1&&flightCalls==1&&flightHeight==24576&&recoveryCalls==1);
    assert(runtime.throwState.targets[0]==0);free(blob);
    InitCase(TRUE);profile.chillState=OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR;
    profile.chillTarget=OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE;profile.throwMaxRange=3;
    primitives.chillTarget=profile.chillTarget;primitives.chillLocomotion=0;
    assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    nativeAwayValid=0;
    assert(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
    assert(flightCalls==1&&runtime.throwState.targets[0]==0&&state.movementActorControlModes[1]==0);free(blob);
    nativeAwayValid=1;
    puts("Actual away dispatcher: saved aim, exact height, launch recheck and drop on invalid landing pass");

"""

ROLE_OPTIONS_DRIVER = r"""
int main(void) {
 OverworldWildOverlayRuntimeState runtime={0};OverworldWildSpawnState state={0};
 OverworldWildBehaviorConditionRuntime conditions={0};runtime.conditions=&conditions;state.movementRuntimeState=&runtime;
 OverworldWildBehaviorDataBlob *blob=calloc(1,sizeof(*blob));assert(blob);blob->header.conditionEntryCount=2;
 blob->conditionOptions[0]=(OverworldWildBehaviorConditionOptions){.subjectRoleMask=1,.captureBinding=2,.mustBeReachableForPickup=1,.usesBinding=1};
 blob->conditionOptions[1]=(OverworldWildBehaviorConditionOptions){.subjectRoleMask=2,.captureBinding=2,.mustBeReachableForPickup=1,.usesBinding=3};
 blob->conditionEntries[0].conditionId=11;blob->conditionEntries[1].conditionId=12;
 conditions.actors[0].count=2;conditions.actors[0].catalogEntryIndexes[0]=0;conditions.actors[0].catalogEntryIndexes[1]=1;
 OverworldPickupRouteWildWorld world={.state=&state,.slot=0,.behaviorData=blob,.ops=&roleOps};
 roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
 assert(OverworldCargoReadWild_Options(&world)==&blob->conditionOptions[0]);
 roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
 assert(OverworldCargoReadWild_Options(&world)==&blob->conditionOptions[1]);
 roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_MOUNTED;
 assert(OverworldCargoReadWild_Options(&world)==NULL);
 roleStateReady=FALSE;assert(OverworldCargoReadWild_Options(&world)==NULL);roleStateReady=TRUE;
 world.ops=NULL;assert(OverworldCargoReadWild_Options(&world)==NULL);world.ops=&roleOps;
 OverworldPickupRouteWildOps noReader=roleOps;noReader.actorState=NULL;world.ops=&noReader;
 assert(OverworldCargoReadWild_Options(&world)==NULL);world.ops=&roleOps;
 conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags=OVERWORLD_TARGET_BINDING_BOUND;
 conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].sourceConditionId=12;
 roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
 assert(OverworldCargoReadWild_Options(&world)==&blob->conditionOptions[1]);
 roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_WILD;
 assert(OverworldCargoReadWild_Options(&world)==NULL);
 conditions.bindings[0].bindings[OVERWORLD_TARGET_BINDING_CARGO].sourceConditionId=11;
 assert(OverworldCargoReadWild_Options(&world)==&blob->conditionOptions[0]);
 roleState.slots[0].snapshot.role=OVERWORLD_ACTOR_ROLE_FOLLOWER;
 assert(OverworldCargoReadWild_Options(&world)==NULL);
 free(blob);puts("current Options: Wild1, Follower3, MountedNone, missing owner/readers and bound source-condition role controls pass");
}
"""


class ThrowAwayAndRoleTests(unittest.TestCase):
    def test_actual_away_windup_rechecks_saved_plan_before_launch_or_drop(self):
        result = run(away_launch_fixture(), "throw-away-launch-drop")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_cargo_options_match_role_and_bound_source(self):
        result = run(role_options_fixture(), "throw-cargo-role-options")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_angled_held_read_windup_and_saved_launch(self):
        result = run(angled_launch_fixture(), "throw-angled-launch")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_cardinal_windup_gate_rejects_angled_launch(self):
        source = angled_launch_fixture()
        gate = "&& read->throwDistance <= profile->throwMaxRange) {"
        self.assertEqual(source.count(gate), 1)
        result = run(source.replace(gate,
            "&& (read->dx == 0 || read->dy == 0)\n            " + gate),
            "throw-angled-old-cardinal-gate")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand", result.stderr)


def angled_launch_fixture():
    source = fixture().split("int main(void) {", 1)[0]
    source = source.replace("static s32 flightHeight;",
        "static s32 flightHeight;\nstatic int expectedX,expectedZ;static u8 expectedDistance,expectedDirection;")
    source = source.replace("settings==(3|(1u<<8))", "settings==(expectedDistance|(1u<<8))")
    source = source.replace("required->x==13&&required->z==10&&required->baseY==24576&&required->distance==3&&required->direction==3",
        "required->x==expectedX&&required->z==expectedZ&&required->baseY==24576&&required->distance==expectedDistance&&required->direction==expectedDirection")
    source = source.replace("(OverworldThrowAwayAim){13,10,24576,3,3}",
        "(OverworldThrowAwayAim){expectedX,expectedZ,24576,expectedDirection,expectedDistance}")
    source = source.replace("slot==1&&direction==3&&distance==3&&x==13&&z==10&&flag==3",
        "slot==1&&direction==expectedDirection&&distance==expectedDistance&&x==expectedX&&z==expectedZ&&flag==3")
    return source + ANGLED_LAUNCH_DRIVER


ANGLED_LAUNCH_DRIVER = r"""
int main(void) {
    static const signed char offsets[][2]={{4,2},{2,4},{-4,2},{4,-2},{-2,-4},{0,4},{4,0}};
    for(unsigned away=0;away<2;away++) for(unsigned n=0;n<sizeof(offsets)/sizeof(offsets[0]);n++) {
        InitCase(TRUE);selectCalls=validateCalls=flightCalls=recoveryCalls=0;
        int dx=offsets[n][0],dz=offsets[n][1],ax=abs(dx),az=abs(dz);
        expectedX=10+dx;expectedZ=10+dz;
        expectedDistance=away?(ax>az?ax:az):ax+az;
        expectedDirection=ax>=az?2+(dx>0):(dz>0);
        conditions.frame.world.actors[2].x=expectedX;conditions.frame.world.actors[2].y=expectedZ;
        objects[3]=(LocalMapObject){.xCurr=expectedX,.yCurr=expectedZ,.posVec={0,24576,0}};
        profile.chillState=OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR;
        profile.chillTarget=away?OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE:OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;
        profile.throwMaxRange=away?expectedDistance:8;profile.throwWindupFrames=20;
        primitives.chillTarget=profile.chillTarget;primitives.chillLocomotion=0;
        if(!away) {
            OverworldTargetBindingPosition interest;
            assert(OverworldThrowObservation_BindingPosition(&state,0,0,&interest));
            assert(PlayerHealthThrow_Line(&state,0,runtime.throwState.targets[0],&profile,&interest,OverworldWildSpawns_QueryPickupThrowTarget));
            OverworldCargoReadWildTarget read;
            const OverworldCargoReadWildTargetCall call={&state,&objects[0],&profile,&throwService,&sOverworldWildCargoTargetOps,0,profile.chillTarget,runtime.throwState.targets[0],0};
            assert(OverworldCargoReadWild_Target(&call,&read)==OVERWORLD_CARGO_READ_TARGET_VALID);
            assert(read.impactX==expectedX&&read.impactY==expectedZ&&read.playerX==expectedX&&read.playerY==expectedZ);
        }
        assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
        assert(runtime.throwState.targets[0]&0x40);
        assert(runtime.movementCustomJumpTargetX[0]==expectedX&&runtime.movementCustomJumpTargetY[0]==expectedZ);
        assert(state.movementCooldowns[0]==20&&flightCalls==0);
        assert(OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&objects[0],&profile,&primitives));
        assert(flightCalls==1&&flightHeight==24576&&recoveryCalls==1&&runtime.throwState.targets[0]==0);
        assert(selectCalls==(int)away&&validateCalls==(int)away);
        free(blob);
    }
    puts("angled/cardinal Wild L1 and Away radius: unchanged endpoint, windup, saved height and launch pass");return 0;
}
"""




AWAY_AIM_DRIVER = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "overworld_throw_away_aim.h"
typedef struct World {
    OverworldMotionDecision decisions[5];
    unsigned count;
    int x[5],z[5];
    s32 height;
} World;
static OverworldMotionDecision Landing(void *raw,int x,int z,s32 *height) {
    World *w=raw;unsigned i=w->count++;
    assert(i<5 && x>=0 && x<=32767 && z>=0 && z<=32767);
    w->x[i]=x;w->z[i]=z;
    if(w->decisions[i]==OVERWORLD_MOTION_DECISION_ACCEPTED) *height=w->height;
    return w->decisions[i];
}
static OverworldThrowAwayAimCall Call(World *w,int dx,int dz,unsigned distance) {
    return (OverworldThrowAwayAimCall){100,100,100-dx,100-dz,distance,w,Landing};
}
static void Invalid(OverworldThrowAwayAimCall *c,World *w) {
    OverworldThrowAwayAim out,before;
    memset(&out,0xA5,sizeof(out));before=out;w->count=0;
    assert(!OverworldThrowAwayAim_Select(c,&out));
    assert(w->count==0 && !memcmp(&out,&before,sizeof(out)));
}
int main(void) {
    World w={0};w.height=24576;
    OverworldThrowAwayAimCall c;OverworldThrowAwayAim out,saved,before;
    for(int sx=-1;sx<=1;sx+=2) for(int sz=-1;sz<=1;sz+=2) {
        c=Call(&w,3*sx,2*sz,8);w.count=0;
        assert(OverworldThrowAwayAim_Select(&c,&out));
        assert(out.x==100+8*sx && out.z==100+5*sz && out.direction==2+(sx>0));
        assert(out.distance==8 && out.baseY==24576 && w.count==1);
        before=out;w.count=0;assert(OverworldThrowAwayAim_Validate(&c,&out));
        assert(w.count==1 && !memcmp(&out,&before,sizeof(out)));
        for(unsigned d=1;d<=8;d++) {
            c=Call(&w,sx,sz,d);w.count=0;
            assert(OverworldThrowAwayAim_Select(&c,&out));
            assert(out.x==100+(int)d*sx && out.z==100+(int)d*sz && out.distance==d);
            assert(w.count==1 && OverworldThrowAwayAim_Validate(&c,&out));
        }
    }
    c=Call(&w,2,3,8);w.count=0;
    assert(OverworldThrowAwayAim_Select(&c,&out));
    assert(out.x==105 && out.z==108 && out.direction==1 && w.count==1);
    /* Round to the nearest tile without exceeding the exact authored radius. */
    c=Call(&w,5,1,8);w.count=0;assert(OverworldThrowAwayAim_Select(&c,&out));
    assert(out.x==108 && out.z==102);
    c=Call(&w,7,1,1);w.count=0;assert(OverworldThrowAwayAim_Select(&c,&out));
    assert(out.x==101 && out.z==100 && w.count==1); /* Cardinal duplicate skipped. */
    static const int dx[4]={0,0,-3,3},dz[4]={-3,3,0,0};
    for(unsigned i=0;i<4;i++) {
        c=Call(&w,dx[i],dz[i],8);w.count=0;
        assert(OverworldThrowAwayAim_Select(&c,&out));
        assert(out.direction==i && out.x==100+(dx[i]?8*(dx[i]>0?1:-1):0));
        assert(out.z==100+(dz[i]?8*(dz[i]>0?1:-1):0) && w.count==1);
    }
    c=Call(&w,0,0,8);w.count=0;assert(OverworldThrowAwayAim_Select(&c,&out));
    assert(out.x==92 && out.z==100 && out.direction==2 && w.count==1);
    /* New projected aim fails: retain the old outward/cardinal order. */
    c=Call(&w,3,2,8);w.count=0;w.decisions[0]=OVERWORLD_MOTION_DECISION_BLOCKED;
    assert(OverworldThrowAwayAim_Select(&c,&out));
    assert(w.count==2 && w.x[0]==108 && w.z[0]==105 && out.x==108 && out.z==100);
    for(unsigned i=0;i<5;i++) w.decisions[i]=OVERWORLD_MOTION_DECISION_BLOCKED;
    memset(&out,0xA5,sizeof(out));before=out;w.count=0;
    assert(!OverworldThrowAwayAim_Select(&c,&out));
    assert(w.count==5 && !memcmp(&out,&before,sizeof(out)));
    c=Call(&w,3,0,8);w.count=0;assert(!OverworldThrowAwayAim_Select(&c,&out));
    assert(w.count==4 && !memcmp(&out,&before,sizeof(out)));
    memset(w.decisions,0,sizeof(w.decisions));c=Call(&w,3,2,8);
    static const OverworldMotionDecision failures[]={OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY,
        OVERWORLD_MOTION_DECISION_PROFILE,OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE};
    for(unsigned i=0;i<sizeof(failures)/sizeof(*failures);i++) {
        w.count=0;w.decisions[0]=failures[i];
        assert(!OverworldThrowAwayAim_Select(&c,&out));
        assert(w.count==1 && !memcmp(&out,&before,sizeof(out)));
    }
    memset(w.decisions,0,sizeof(w.decisions));
    Invalid(NULL,&w);c=Call(&w,3,2,8);
    assert(!OverworldThrowAwayAim_Select(&c,NULL) && w.count==0);
    c.landing=NULL;Invalid(&c,&w);
    c=Call(&w,3,2,0);Invalid(&c,&w);c.distance=9;Invalid(&c,&w);c.distance=255;Invalid(&c,&w);
    c=Call(&w,3,2,8);c.originX=-1;Invalid(&c,&w);c.originX=32768;Invalid(&c,&w);
    c=Call(&w,3,2,8);c.originZ=-1;Invalid(&c,&w);c.originZ=32768;Invalid(&c,&w);
    c=Call(&w,3,2,8);c.playerX=-1;Invalid(&c,&w);c.playerX=32768;Invalid(&c,&w);
    c=Call(&w,3,2,8);c.playerZ=-1;Invalid(&c,&w);c.playerZ=32768;Invalid(&c,&w);
    c=Call(&w,3,2,8);w.count=0;assert(OverworldThrowAwayAim_Select(&c,&saved));
    assert(!OverworldThrowAwayAim_Validate(NULL,&saved));
    assert(!OverworldThrowAwayAim_Validate(&c,NULL));
    before=saved;w.count=0;
    c.playerX=111;c.playerZ=107;assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==0);
    c.playerX=96;c.playerZ=98;assert(OverworldThrowAwayAim_Validate(&c,&saved) && w.count==1);
    assert(!memcmp(&saved,&before,sizeof(saved))); /* Current Player does not retarget saved aim. */
    w.height++;assert(!OverworldThrowAwayAim_Validate(&c,&saved));w.height--;
    w.count=0;w.decisions[0]=OVERWORLD_MOTION_DECISION_OCCUPIED;
    assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==1);
    memset(w.decisions,0,sizeof(w.decisions));w.count=0;
    saved.distance=7;assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==0);saved=before;
    saved.x--;assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==0);saved=before;
    saved.x=32768;assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==0);saved=before;
    saved.z=-1;assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==0);saved=before;
    saved.direction=4;assert(!OverworldThrowAwayAim_Validate(&c,&saved) && w.count==0);
    puts("Actual Away aim: arbitrary angles, exact radius, old cardinal order, bounded fallback and saved endpoint/height/current Player guards pass");
    return 0;
}
"""


class ThrowAwayAimTests(unittest.TestCase):
    def test_actual_aim_angles_radius_fallback_and_saved_landing(self):
        HERE.mkdir(parents=True, exist_ok=True)
        unit, binary = HERE / "away-aim.c", HERE / "away-aim"
        unit.write_text(AWAY_AIM_DRIVER)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                   "-Wall", "-Wextra", "-Werror", "-DOVERWORLD_MOTION_HOST",
                   "-I", str(ROOT / "include"), str(unit),
                   str(ROOT / "lib/overworld/overworld_throw_away_aim.c"), "-o", str(binary)]
        compiled = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        result = subprocess.run([str(binary)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
