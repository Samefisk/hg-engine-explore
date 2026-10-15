"""Production dispatch regression; host landing seams are not game proof."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from tools.overworld.test_blocked_wild_facing import function_bodies


DISPATCH = "OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand"
RANDOM_HOP = "OverworldWildSpawns_TryStartRandomBehaviorHopCommand"
DIRECTED_HOP = "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand"
CHILL = "OverworldWildSpawns_TryStartChillWanderCommand"
SIGNATURES = {
    DISPATCH: "OverworldWildSpawnState *state, int slot, LocalMapObject *object, "
              "const OverworldWildBehaviorProfile *profile, const OverworldWildBehaviorPrimitives *primitives",
    RANDOM_HOP: "OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot, "
                "const OverworldWildBehaviorProfile *profile",
    DIRECTED_HOP: "OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot, "
                  "const OverworldWildBehaviorProfile *profile, int dx, int dy, "
                  "const u8 *directions, int directionCount, u8 planMode",
    CHILL: "OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot, "
           "const OverworldWildBehaviorProfile *profile, const OverworldWildBehaviorPrimitives *primitives",
}


def harness_source():
    bodies = function_bodies()
    prototypes = "\n".join(f"static BOOL {name}({signature});" for name, signature in SIGNATURES.items())
    functions = "\n".join(f"static BOOL {name}({signature})\n{{{bodies[name]}\n}}"
                          for name, signature in SIGNATURES.items())
    return PRELUDE + prototypes + functions + DRIVER


PRELUDE = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 8
#define OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS 8
#define OW_WILD_SPAWNER_UNTANGLE_MAX_DIRECTIONS 8
#define OW_WILD_SPAWNER_SPOT_STATE_CHILL 0
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 1
#define OW_WILD_SPAWN_ENTRY_MOVE 1
#define OW_WILD_BEHAVIOR_TARGET_NONE 0
#define OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER 1
#define OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY 2
#define OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER 3
#define OW_WILD_BEHAVIOR_TARGET_CONDITION_ACTOR 4
#define OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER 5
#define OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER 6
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_THROW_LINE 7
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 3
#define OW_WILD_SPAWNER_THROW_TARGET_NONE 0
#define OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG 0x80
#define OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG 0x40
#define OW_WILD_SPAWNER_THROW_TARGET_DECODE(value) ((value) & 7)
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
#define OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR 1
#define OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR 1
#define OW_WILD_BEHAVIOR_KIND_CHASE 2
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT 2
#define OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP 1
#define OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN 0
#define OW_WILD_HELPER_HOP_PLAN_DIRECT 0
#define OW_WILD_HELPER_HOP_PLAN_FLEE 1
#define OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY 2
#define OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT 4
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER 1
#define OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES 32
#define OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_BEHAVIOR_BOOL_YES 1
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(value) ((value) & 2)
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(value) ((value) & 1)
#define OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(value) ((value) & 2)
#define OW_WILD_BEHAVIOR_WALK_USES_FIXED_FACING(value) ((value) & 1)
#define PLAYER_HEALTH_THROW_LAUNCH 0
#define PLAYER_HEALTH_EVENT_CODE(slot, event) 0

typedef struct LocalMapObject { int x, y; u8 facing; } LocalMapObject;
typedef struct FieldSystem { LocalMapObject *playerAvatar; } FieldSystem;
typedef struct OverworldWildBehaviorProfileData {
    u8 chillAction, hopPause, walkPause, hopMinDistance, hopMaxDistance;
    u8 hopAllowNonCardinal, walkOptions, avoidPreviousTile, wanderStraightChance;
} OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile {
    OverworldWildBehaviorProfileData owner;
    u8 onReachAction, chillState, throwMaxRange, throwWindupFrames;
    u8 chaseBoostDistance, chaseBoostSpeed, chillSpeed;
} OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { u8 chillTarget, chillLocomotion; } OverworldWildBehaviorPrimitives;
typedef struct OverworldWildOverlayRuntimeState {
    struct { u8 targets[8]; u8 carrierMask; } throwState;
    s16 movementCustomJumpTargetX[8], movementCustomJumpTargetY[8];
    struct { s16 lastKnownX[8], lastKnownY[8]; } spawnPresentations;
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    struct { BOOL active; LocalMapObject *object; } spawns[8];
    FieldSystem *movementFieldSystem;
    u8 movementSpotStates[8], movementSpawnRunActive[8], movementCooldowns[8];
    s16 movementSpawnRunTargetX[8], movementSpawnRunTargetY[8];
    u8 movementStagedHopAvoidValid[8];
    s16 movementStagedHopAvoidX[8], movementStagedHopAvoidY[8];
    OverworldWildOverlayRuntimeState runtime;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) (&(state)->runtime)
typedef struct OverworldWildHelperHopConfig {
    int objectX, objectY, targetX, targetY;
    u8 minDistance, maxDistance, allowNonCardinal, planMode, directionCount;
} OverworldWildHelperHopConfig;
typedef struct OverworldWildHelperHopResult { int landingX, landingY, finalTargetX, finalTargetY; } OverworldWildHelperHopResult;
typedef BOOL (*LandingValidator)(OverworldWildSpawnState *, int, FieldSystem *, u16, int, int, int, int);
typedef struct OverworldWildBehaviorHopValidationContext {
    OverworldWildSpawnState *state; FieldSystem *fieldSystem;
    LandingValidator baseValidator; int slot; u16 allowedTile; BOOL rejectPreviousTile;
} OverworldWildBehaviorHopValidationContext;
typedef BOOL (*HelperValidator)(int, int, int, int, void *);
typedef struct OverworldWildHelperOverlayEntry {
    BOOL (*pickRandomBehaviorHop)(const OverworldWildHelperHopConfig *, HelperValidator, void *, OverworldWildHelperHopResult *);
} OverworldWildHelperOverlayEntry;
static int facingWrites, landingAttempts, randomQueries, directedPlans, activeConditions;
static LocalMapObject *sOverworldWildCollisionIgnoredObject;
static void Check(BOOL value, const char *message) { if (!value) { fprintf(stderr, "%s\n", message); exit(1); } }
static int OverworldWildSpawns_Abs(int value) { return abs(value); }
static int OverworldWildSpawns_Max(int a, int b) { return a > b ? a : b; }
static int OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object) { return object->x; }
static int OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object) { return object->y; }
#define GetPlayerXCoord OverworldWildSpawns_ObjectCurrentX
#define GetPlayerYCoord OverworldWildSpawns_ObjectCurrentY
static int OverworldWildSpawns_GetActiveConditionApplications(OverworldWildSpawnState *state, int slot) { return activeConditions; }
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetControllerLane(const OverworldWildBehaviorProfile *profile, u8 spot) { return &profile->owner; }
static u8 OverworldWildSpawns_GetCurrentMovementLocomotion(const OverworldWildBehaviorPrimitives *primitives, u8 spot) { return primitives->chillLocomotion; }
static u8 OverworldWildSpawns_GetBehaviorHopMinDistance(const OverworldWildBehaviorProfile *profile, u8 spot) { return profile->owner.hopMinDistance; }
static u8 OverworldWildSpawns_GetBehaviorHopMaxDistance(const OverworldWildBehaviorProfile *profile, u8 spot) { return profile->owner.hopMaxDistance; }
static u16 OverworldWildSpawns_GetAllowedTileForSpotState(const OverworldWildBehaviorProfile *profile, u8 spot) { return 512; }
static int OverworldWildSpawns_MovementDirectionDeltaX(int d) { return d == 2 ? -1 : d == 3 ? 1 : 0; }
static int OverworldWildSpawns_MovementDirectionDeltaY(int d) { return d == 0 ? -1 : d == 1 ? 1 : 0; }
static int OverworldWildSpawns_BuildRandomDirections(u8 *directions) { for (int i=0; i<4; i++) directions[i]=(3+i)%4; return 4; }
static int OverworldWildSpawns_BuildDirectedDirections(int dx, int dy, u8 *directions) { if (!dx && !dy) return 0; directions[0]=dx ? 2+(dx>0) : (dy>0); return 1; }
static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 facing) { object->facing=facing; facingWrites++; }
static BOOL OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(OverworldWildSpawnState *state, int slot, FieldSystem *field, u16 tile, int x, int y, int tx, int ty) { return FALSE; }
static BOOL OverworldWildSpawns_ValidateBehaviorHopLanding(int x, int y, int tx, int ty, void *context) {
    OverworldWildBehaviorHopValidationContext *v=context;
    return v->baseValidator(v->state,v->slot,v->fieldSystem,v->allowedTile,x,y,tx,ty);
}
static BOOL RejectRandom(const OverworldWildHelperHopConfig *config, HelperValidator validator, void *context, OverworldWildHelperHopResult *result) {
    randomQueries++;
    for (int d=0; d<4; d++) for (int n=config->minDistance; n<=config->maxDistance; n++) {
        int x=config->objectX+OverworldWildSpawns_MovementDirectionDeltaX(d)*n;
        int y=config->objectY+OverworldWildSpawns_MovementDirectionDeltaY(d)*n;
        landingAttempts++;
        Check(!validator(x,y,x,y,context), "fixture admitted a Hop landing");
    }
    return FALSE;
}
static const OverworldWildHelperOverlayEntry helper={RejectRandom};
static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void) { return &helper; }
static void OverworldWildSpawns_BuildHopHelperConfig(const OverworldWildBehaviorProfileData *lane, int x, int y, int tx, int ty, const u8 *directions, int count, u8 mode, OverworldWildHelperHopConfig *config) {
    *config=(OverworldWildHelperHopConfig){ .objectX=x,.objectY=y,.minDistance=lane->hopMinDistance,.maxDistance=lane->hopMaxDistance };
}
static BOOL OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(OverworldWildSpawnState *state, FieldSystem *field, int slot, const OverworldWildBehaviorProfile *profile, u16 tile, int x, int y, int tx, int ty, u8 marker) { landingAttempts++; return FALSE; }
static BOOL OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(OverworldWildSpawnState *state, FieldSystem *field, int slot, const OverworldWildBehaviorProfile *profile, u16 tile, int tx, int ty, const u8 *directions, int count, u8 mode) { directedPlans++; return FALSE; }
/* Native/other locomotion seams are unreachable in this Hop-only fixture. */
#define MapObject_IsSingleMovementActive(...) FALSE
#define MapObject_ClearSingleMovementActive(...) ((void)0)
#define OverworldWildSpawns_TryGetConditionTargetPosition(...) FALSE
#define OverworldWildSpawns_IsCurrentSpawnObject(...) TRUE
#define OverworldWildSpawns_ClearThrowStateForSlot(...) ((void)0)
#define OverworldWildSpawns_IsValidPickupThrowTarget(...) TRUE
#define OverworldWildSpawns_TryGetCirclePlayerMovementTarget(...) FALSE
#define OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(...) FALSE
#define OverworldWildSpawns_StartPreparedCustomJumpCommand(...) FALSE
#define OverworldWildSpawns_PlayerHealthReady(...) FALSE
static const struct { BOOL (*contactEvent)(OverworldWildSpawnState *, int, const OverworldWildBehaviorProfile *, u32); } unusedHealth;
#define PLAYER_HEALTH_OVERLAY_ENTRY (&unusedHealth)
#define OverworldWildSpawns_StartThrowRecovery(...) ((void)0)
#define OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile(...) ((void)0)
#define OverworldWildSpawns_ShowBubble(...) ((void)0)
#define OverworldWildSpawns_IsStablePickupThrowTarget(...) FALSE
#define OverworldWildSpawns_StartCarriedThrowTarget(...) FALSE
#define OverworldWildSpawns_AppendFleeFallbackDirections(...) ((void)0)
#define OverworldWildSpawns_ApplyWalkPursuitDirectionInertia(...) ((void)0)
#define OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(...) ((void)0)
#define OverworldWildSpawns_TryStartTeleportMovementCommand(...) FALSE
#define OverworldWildSpawns_TryStartSpawnerMovementCommand(...) FALSE
#define OverworldWildSpawns_IsPlayerTile(...) FALSE
#define OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(...) FALSE
#define OverworldWildSpawns_TryGetBehaviorHopVector(...) FALSE
static unsigned gf_rand(void) { return 0; }
"""


PRELUDE += r"""
/* Typed read-only Cargo target boundary. The random conditional Hop bypasses
 * this seam; the directed control admits only its ordinary Player target. */
#define OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE 13
#define OW_WILD_BEHAVIOR_TARGET_CARGO 12
#define OVERWORLD_CARGO_READ_TARGET_VALID 1
#define OVERWORLD_CARGO_READ_TARGET_ABORT 2
#define OVERWORLD_PICKUP_ROUTE_PENDING 0
#define OVERWORLD_PICKUP_ROUTE_REACHABLE 1
#define PlayerHealthThrowService_IsReady(...) FALSE
#define PLAYER_HEALTH_THROW_SERVICE_ENTRY NULL
#define OverworldWildSpawns_AbortThrow(...) ((void)0)
#define OverworldWildSpawns_QueryCargoRoute(...) 2
static const int sOverworldWildCargoTargetOps=0;
typedef int OverworldPickupRouteStatus;
typedef struct OverworldCargoQueryResult {
    struct { u8 hasNextStep; struct { int x,y; } nextStep; } route;
} OverworldCargoQueryResult;
typedef struct OverworldCargoReadWildTargetCall {
    OverworldWildSpawnState *state; LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const void *throwService, *ops;
    u8 slot, movementTarget, throwTarget, reserved;
} OverworldCargoReadWildTargetCall;
typedef struct OverworldCargoReadWildTarget {
    LocalMapObject *targetObject;
    int objectX,objectY,playerX,playerY,impactX,impactY,dx,dy;
    u8 targetSlot,throwDistance,direction,reserved;
} OverworldCargoReadWildTarget;
static int targetReads;
static u8 ReadPlayerTarget(const OverworldCargoReadWildTargetCall *call, OverworldCargoReadWildTarget *read) {
    Check(call->state && call->slot==0 && call->object==call->state->spawns[0].object
        && call->movementTarget==OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER
        && call->throwTarget==0 && call->reserved==0,
        "blocked Hop entered an unrelated Cargo target path");
    memset(read,0,sizeof(*read)); targetReads++;
    read->objectX=call->object->x;read->objectY=call->object->y;
    read->playerX=call->state->movementFieldSystem->playerAvatar->x;
    read->playerY=call->state->movementFieldSystem->playerAvatar->y;
    read->dx=read->playerX-read->objectX;read->dy=read->playerY-read->objectY;
    return OVERWORLD_CARGO_READ_TARGET_VALID;
}
typedef struct OverworldQueryCodeAddonEntry {
    u8 (*cargoReadTarget)(const OverworldCargoReadWildTargetCall *,OverworldCargoReadWildTarget *);
} OverworldQueryCodeAddonEntry;
static const OverworldQueryCodeAddonEntry targetEntry={ReadPlayerTarget};
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem *field, const void *transition) {
    Check(field && !transition,"blocked Hop target read changed admission");return &targetEntry;
}
"""


DRIVER = r"""
int main(void) {
    LocalMapObject object={.x=570,.y=404,.facing=2}, player={.x=572,.y=404};
    FieldSystem field={.playerAvatar=&player};
    OverworldWildSpawnState state={.movementFieldSystem=&field};
    OverworldWildBehaviorProfile profile={.owner={.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_HOP,
        .hopPause=10,.hopMinDistance=1,.hopMaxDistance=8,.hopAllowNonCardinal=1}};
    OverworldWildBehaviorPrimitives primitives={.chillTarget=OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY,
        .chillLocomotion=OW_WILD_BEHAVIOR_LOCOMOTION_HOP};
    state.spawns[0].active=TRUE; state.spawns[0].object=&object;
    activeConditions=1; /* Notice remains active after its alert ends. */
    for (int retry=0; retry<3; retry++) {
        state.movementCooldowns[0]=0;
        Check(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&object,&profile,&primitives),
            "blocked random Hop started motion");
        Check(object.facing==2 && facingWrites==0, "blocked conditional random Hop changed facing");
        Check(state.movementCooldowns[0]==10, "blocked conditional Hop lost authored pause");
    }
    Check(randomQueries==3 && landingAttempts==96 && directedPlans==0 && targetReads==0,
        "conditional random Hop did not use the ordinary random landing path");
    primitives.chillTarget=OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER;
    Check(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&object,&profile,&primitives),
        "blocked directed Hop started motion");
    Check(object.facing==3 && facingWrites==1 && directedPlans>0 && randomQueries==3 && targetReads==1,
        "genuine directed Hop lost its directed blocked-facing behavior");
    Check(state.movementCooldowns[0]==10, "directed Hop lost authored pause");
    activeConditions=0; facingWrites=0;
    Check(!OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(&state,0,&object,&profile,&primitives),
        "ordinary idle without a condition was admitted to conditional dispatch");
    Check(facingWrites==0 && randomQueries==3 && targetReads==1, "inactive condition dispatched movement");
    return 0;
}
"""


class BlockedNoticeHopTests(unittest.TestCase):
    def test_actual_directed_hop_vector_precedes_only_impossible_landing_reads(self):
        from tools.overworld.test_chain_action_lifecycle import hop_vector_preflight_source, execute
        result = execute(hop_vector_preflight_source(directed=True), "directed")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_production_conditional_random_hop_reject_preserves_facing_and_profile_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "blocked-notice-hop"
            result = subprocess.run([*shlex.split(os.environ.get("HOST_CC", "cc")),
                                     "-std=gnu11", "-O0", "-x", "c", "-", "-o", str(executable)],
                                    input=harness_source(), text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
