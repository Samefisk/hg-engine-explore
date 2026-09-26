"""S1 chain handoff: real action/start bodies, engine-boundary host stubs.

The accepted normal Ledyba scenario is the separate live witness. This test
does not claim collision, rendered motion, ARM ABI, or normal chain timing.
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
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError("chain fixture seam differs: " + old[:100])
    return source.replace(old, new)


def harness_source():
    start = module("chain_start", ROOT / "scripts/verify_overworld_motion_start_transaction.py")
    extract = module("chain_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    audit = module("chain_bodies", ROOT / "scripts/verify_overworld_role_controller.py")
    wild, runtime = WILD.read_text(), RUNTIME.read_text()
    body = audit.function_bodies(wild)
    source = start.harness_source().split("static void RunCase(", 1)[0]
    source = replace_once(source, '#include "overworld_motion_model.h"',
                          '#include "overworld_motion_model.h"\n#include "overworld_role_controller.h"')
    source = replace_once(source, "u8 walkOptions, walkSwayWidth, hopSwayWidth, spawnHopSwayWidth, spawnHopTime;",
                          "u8 walkOptions, walkSwayWidth, hopSwayWidth, spawnHopSwayWidth, spawnHopTime, hopTime, hopPause, chainRepositionJumpCount, chainRepositionDistance, "
                          "chainRepositionAllowCardinal, chainRepositionAllowDiagonal, chainRepositionDust; u16 chillAllowedTerrainMask;")
    source = replace_once(
        source,
        "typedef struct OverworldWildBehaviorProfile { OverworldWildBehaviorProfileData lane; } OverworldWildBehaviorProfile;",
        "typedef struct OverworldWildBehaviorProfile { union { OverworldWildBehaviorProfileData lane; OverworldWildBehaviorProfileData owner; }; "
        "OverworldWildBehaviorProfileData tired; u8 jumpLevel, stamina, tiredState; } OverworldWildBehaviorProfile;",
    )
    source = replace_once(
        source,
        "typedef struct OverworldWildWalkMomentumState { u8 speed; } OverworldWildWalkMomentumState;",
        "typedef struct OverworldWildWalkMomentumState { "
        "u8 direction, tileCounter, speed, baseSpeed, spotState, skidRemaining, turnDirection, resumeSpeed; "
        "} OverworldWildWalkMomentumState;",
    )
    source = replace_once(source, "u8 movementCustomJumpPrepActive[10], movementCustomJumpActive[10];",
                          "u8 movementCustomJumpPrepActive[10], movementCustomJumpActive[10], movementEmotePlayHopSound[10], "
                          "movementMankeyTreeTopLandingExpected[10], movementMankeyTreeTopSettled[10]; "
                          "s16 movementMankeyTreeTopSettledX[10], movementMankeyTreeTopSettledY[10];")
    source = replace_once(
        source,
        "typedef struct FieldSystem { int unused; } FieldSystem;",
        "typedef struct FIELD_PLAYER_AVATAR { LocalMapObject *mapObject; } FIELD_PLAYER_AVATAR; "
        "typedef struct FieldSystem { int unused; FIELD_PLAYER_AVATAR *playerAvatar; void *map_matrix; } FieldSystem;",
    )
    source = "#define MAP_EVERYWHERE 0\n" + source
    source = replace_once(source, "u16 movementInProgressMask;", """
    u16 movementInProgressMask;
    struct { LocalMapObject *object; u8 active; } spawns[10];
    u8 movementCooldowns[10];
    u8 movementEmoteJumpsRemaining[10], movementEmoteTimers[10], movementEmoteSteps[10];
    u8 movementEmoteDirections[10], movementEmoteEndStates[10], movementEmoteBubbleIds[10];
    u8 movementEmoteShowBubbleEachJump[10], movementEmotePlayCryOnHop[10];
    s16 movementStagedHopOriginX[10], movementStagedHopOriginY[10];
    s16 movementStagedHopTargetX[10], movementStagedHopTargetY[10];
    s16 movementStagedHopAvoidX[10], movementStagedHopAvoidY[10];
    s16 movementPreviousTileX[10], movementPreviousTileY[10];
    u8 movementStagedHopFinishWithTired[10], movementStagedHopAvoidValid[10];
    """)
    # Keep the real portable admission model; the engine bridge supplies its
    # kind/arc/pause contract, with distinct ordinary-Hop timing as a control.
    source = replace_once(source, ".duration = duration, .startX =", ".duration = duration, "
                          ".arcHeightQ4 = state->runtime.movementCustomJumpArcHeightsQ4[slot], "
                          ".pauseFrames = reposition || state->movementStagedHopPending[slot] "
                          "== OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING ? 0 : walk ? 0 : lane->hopPause, "
                          ".commitPolicy = reposition ? OVERWORLD_MOTION_COMMIT_NO_CHAIN : OVERWORLD_MOTION_COMMIT_NORMAL, .startX =")
    source = replace_once(source, "*trajectory = 8 | (24u << 16);",
                          "*trajectory = (lane->hopTime ? lane->hopTime : 7) | (24u << 16);")
    source = replace_once(source, "static OverworldMotionDecision OverworldWildSpawns_ResolveHopTrajectory(",
                          "static unsigned plannerRejects, plannerCalls;\nstatic OverworldMotionDecision OverworldWildSpawns_ResolveHopTrajectory(")
    source = replace_once(source, "return trajectoryOkay ? OVERWORLD_MOTION_DECISION_ACCEPTED : OVERWORLD_MOTION_DECISION_BLOCKED;",
                          "plannerCalls++; if (plannerRejects) { plannerRejects--; return OVERWORLD_MOTION_DECISION_BLOCKED; } "
                          "return trajectoryOkay ? OVERWORLD_MOTION_DECISION_ACCEPTED : OVERWORLD_MOTION_DECISION_BLOCKED;")
    definitions = {}
    for path in (WILD, ROOT / "include/overworld_wild_behavior_data.h", ROOT / "include/overworld_wild_movement.h",
                 ROOT / "include/overworld_wild_spawns_internal.h"):
        for line in path.read_text().replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match:
                definitions[match[1]] = line
    functions = [
        ("OverworldWildSpawns_IsPlayableMapMatrixTile", "BOOL"),
        ("OverworldWildSpawns_TryGetLoadedMetatileBehavior", "BOOL"),
        ("OverworldWildSpawns_ClassifyBehaviorHopLandingTile", "OverworldMotionDecision"),
        ("OverworldWildSpawns_IsBehaviorAllowedHopLandingTile", "BOOL"),
        ("OverworldWildSpawns_GetAllowedTileForSpotState", "u16"),
        ("OverworldWildSpawns_ClearStagedHopTargetLocal", "void"),
        ("OverworldWildSpawns_IsChainActionReady", "BOOL"),
        ("OverworldWildSpawns_ApplyChainRepositionResult", "BOOL"),
        ("OverworldWildSpawns_RunChainReposition", "BOOL"),
        ("OverworldWildSpawns_GetLookAroundFrames", "u8"),
        ("OverworldWildSpawns_ResetEmotePresentationStyle", "void"),
        ("OverworldWildSpawns_TryStartChainForwardHop", "u8"),
        ("OverworldWildSpawns_TryStartChainPauseAction", "u8"),
        ("OverworldWildSpawns_CommitDeferredChainMovementPause", "void"),
        ("OverworldWildSpawns_FinishPendingStagedHop", "void"),
    ]
    actual = "\n".join(extract.production_function(wild, name, result) for name, result in functions)
    # Exercise the exact production continuation branch, not a copied version
    # of its ready check/counter update. Earlier unrelated carrier/history and
    # later normal movement branches are outside this bounded host fixture.
    finished = body["OverworldWildSpawns_HandleFinishedMovementCommand"]
    left = finished.index("    if ((policy.chainStepsRemaining", finished.index("GetBehaviorProfileAndPrimitivesForSlot"))
    right = finished.index("    if (OverworldWildSpawns_HandleFinishedWalkMovement", left)
    continuation = finished[left:right]
    continuation = replace_once(
        continuation,
        "        if (pendingDistanceDespawn) {\n            goto request_distance_despawn;\n        }\n",
        "",
    )
    command_body = audit.function_bodies(runtime)["OverworldActorWalkPolicy_ApplyCommand"]
    planned_hop_body = body["OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand"]
    landing_decision_assignment = re.search(
        r"    state->movementStagedHopFinishWithTired\[slot\] = .*?;",
        planned_hop_body,
        re.S,
    ).group(0)
    cases = []
    for name in ("CHAIN_TAKE_PENDING", "CHAIN_PUT_PENDING", "CHAIN_REPOSITION_BEGIN",
                 "CHAIN_REPOSITION_ADVANCE", "CHAIN_REPOSITION_FINISH"):
        match = re.search(r"    case OVERWORLD_ACTOR_WALK_POLICY_" + name + r":.*?(?=    case |    default:)", command_body, re.S)
        if not match:
            raise ValueError("missing production chain policy case: " + name)
        cases.append(match.group(0))
    policy_header = (ROOT / "include/overworld_wild_movement.h").read_text()
    enums = "\n".join(re.search(r"typedef enum " + name + r" \{.*?\} " + name + ";", policy_header, re.S).group(0)
                      for name in ("OverworldActorWalkPolicyOperation", "OverworldActorWalkPolicyDecision"))
    wanted = set(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b", actual + continuation + SUPPORT + source))
    present = set(re.findall(r"^#define\s+(\w+)", source, re.M))
    macros = []
    while wanted:
        name = wanted.pop()
        if name in present:
            continue
        if name not in definitions:
            raise ValueError("missing source constant: " + name)
        line = definitions[name]
        macros.append(line)
        present.add(name)
        wanted.update(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b", line.split(name, 1)[1]))
    # Definitions precede all real bodies. The fixture uses compact host
    # structs, not the DS layout; runtime policy cases are inserted unchanged.
    source = "\n".join(macros) + "\n" + source
    result_struct = re.search(r"typedef struct OverworldWildChainRepositionResult \{.*?\} OverworldWildChainRepositionResult;", wild, re.S).group(0)
    support = (SUPPORT.replace("/* @ENUMS@ */", enums)
               .replace("/* @CASES@ */", "\n".join(cases))
               .replace("/* @RESULT@ */", result_struct)
               .replace("/* @LANDING_DECISION@ */", landing_decision_assignment))
    source += support + actual
    source += """
static void OverworldWildSpawns_HandleFinishedMovementCommand(OverworldWildSpawnState *state, int slot)
{
    OverworldActorPolicyView policy;
    OverworldWildChainRepositionResult repositionResult;
    OverworldWildBehaviorProfile profile = testProfile;
    if (!OverworldActorPolicy_Inspect(slot, &policy)) return;
    completionCalls++;
""" + continuation + "}\n" + DRIVER
    return source


SUPPORT = r"""
/* @ENUMS@ */
typedef int8_t s8;
typedef struct OverworldActorWalkPolicyCall {
    u8 actorSlot, operation, direction, distance, chainAction, chainTicks, decision;
} OverworldActorWalkPolicyCall;
/* @RESULT@ */
_Static_assert(sizeof(OverworldWildChainRepositionResult) == 4, "native result remains four bytes");
static OverworldWildBehaviorProfile testProfile;
static unsigned roleCalls, completionCalls;
static BOOL allowCandidate;
static OverworldMotionDecision candidateDecision;
typedef struct OverworldWildSurfaceHit { u16 surfaceId; u8 surfaceType; s32 height; } OverworldWildSurfaceHit;
static BOOL surfaceEnabled;
static u16 sourceSurfaceId, targetSurfaceId;
static void OverworldWildSpawns_InitPolicyCall(OverworldActorWalkPolicyCall *call, int slot, int op)
{ memset(call, 0, sizeof(*call)); call->actorSlot = slot; call->operation = op; }
static BOOL ReduceChainPolicy(OverworldActorWalkPolicyCall *call)
{
    OverworldActorPolicyView *policy = &selectedPolicy;
#define deferredChainPauseAction chainPauseAction
#define deferredChainPauseTicks chainPauseTicks
    switch (call->operation) {
/* @CASES@ */
    default: return FALSE;
    }
#undef deferredChainPauseAction
#undef deferredChainPauseTicks
    return TRUE;
}
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    return ReduceChainPolicy(call);
}
static u8 BuildLookPlan(u8 direction) { return direction; }
static struct { BOOL (*reduceWalk)(OverworldActorWalkPolicyCall *); u8 (*buildLookPlan)(u8); }
    policyEntry = {ReduceChainPolicy, BuildLookPlan};
static struct { void *unused; typeof(policyEntry) *policy; } movementEntry = {0, &policyEntry};
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&movementEntry)
#define OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS 10
static u32 OverworldWildSpawns_ReduceRole(int slot, u32 request, u32 details)
{
    (void)slot;
    OverworldRoleControllerInput input = {.version = OVERWORLD_ROLE_CONTROLLER_VERSION,
        .size = sizeof(input), .role = OVERWORLD_ROLE_CONTROLLER_ROLE_WILD,
        .event = request, .flags = details, .chainAction = details >> 8, .chainTicks = details >> 16};
    OverworldRoleControllerOutput output;
    roleCalls++;
    OverworldRoleController_Reduce(&input, &output);
    return output.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL
        ? OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED | output.terminalKind
            | (u32)output.terminalAction << 8 | (u32)output.terminalTicks << 16 : 0;
}
static u32 gf_rand(void) { return 0; }
static u32 OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object) { return (u32)object->xCurr; }
static u32 OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object) { return (u32)object->yCurr; }
static BOOL OverworldWildSpawns_IsCanopyHopperTreeTopSlot(OverworldWildSpawnState *state, int slot)
{ (void)state; (void)slot; return FALSE; }
static BOOL OverworldWildSpawns_IsMountedPlayerScriptedLandingTile(FieldSystem *field, int x, int y)
{ (void)field; (void)x; (void)y; return FALSE; }
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *field, int x, int y, OverworldWildSurfaceHit *hit)
{ (void)field; hit->surfaceType = 0; hit->surfaceId = x == 550 && y == 380 ? sourceSurfaceId : targetSurfaceId;
  hit->height = 65536; return surfaceEnabled; }
static u8 GetMetatileBehaviorAt(FieldSystem *field, int x, int y)
{ (void)field; (void)x; (void)y; return 0; }
static BOOL OverworldWildSpawns_DoesAllowedTileMatch(FieldSystem *field, u16 allowed, u8 behavior, int x, int y)
{ (void)field; (void)allowed; (void)behavior;
  return x >= 548 && x <= 552 && y >= 378 && y <= 382
      && (allowCandidate || candidateDecision != OVERWORLD_MOTION_DECISION_TERRAIN); }
static BOOL OverworldWildSpawns_IsPlayerTile(FieldSystem *field, int x, int y)
{ (void)field; (void)x; (void)y; return FALSE; }
static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *field, int x, int y)
{ (void)field; (void)x; (void)y; return !allowCandidate && candidateDecision == OVERWORLD_MOTION_DECISION_OCCUPIED; }
static BOOL OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(FieldSystem *field, LocalMapObject *object, int x, int y)
{ (void)object; return OverworldWildSpawns_IsTileOccupiedByObject(field, x, y); }
static BOOL OverworldWildSpawns_IsTileOccupiedOnSurface(FieldSystem *field, LocalMapObject *object, BOOL player, int x, int y, s32 height)
{ (void)object; (void)player; (void)height; return OverworldWildSpawns_IsTileOccupiedByObject(field, x, y); }
static OverworldMotionDecision OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
    OverworldWildSpawnState *, int, FieldSystem *, u16, int, int, int, int);
static void OverworldWildSpawns_ClearStagedHopTargetLocal(
    OverworldWildSpawnState *, int);
/* The full planned-Hop helper has many callers outside this bounded chain
 * fixture. Keep its landing classification, staged state, and shared-motion
 * start contract here while extracting the forward-chain caller unchanged. */
static BOOL OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
    OverworldWildSpawnState *state, FieldSystem *field, int slot,
    const OverworldWildBehaviorProfile *profile, u16 allowed,
    int landingX, int landingY, int finalX, int finalY, u8 marker)
{
    LocalMapObject *object = state->spawns[slot].object;
    u8 distance = landingX != object->xCurr
        ? (u8)(landingX > object->xCurr
            ? landingX - object->xCurr : object->xCurr - landingX)
        : (u8)(landingY > object->yCurr
            ? landingY - object->yCurr : object->yCurr - landingY);
    OverworldMotionDecision landingDecision = OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
        state, slot, field, allowed, landingX, landingY, finalX, finalY);
/* @LANDING_DECISION@ */
    if (landingDecision != OVERWORLD_MOTION_DECISION_ACCEPTED) return FALSE;
    state->movementStagedHopOriginX[slot] = object->xCurr;
    state->movementStagedHopOriginY[slot] = object->yCurr;
    state->movementStagedHopTargetX[slot] = finalX;
    state->movementStagedHopTargetY[slot] = finalY;
    state->movementStagedHopDistances[slot] = distance;
    state->movementStagedHopPending[slot] = marker;
    if (OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
            state, field, slot, object, selectedPolicy.walkMomentum.direction,
            distance, landingX, landingY, profile, TRUE, 0)
        == OVERWORLD_MOTION_DECISION_ACCEPTED) return TRUE;
    OverworldWildSpawns_ClearStagedHopTargetLocal(state, slot);
    return FALSE;
}
static BOOL OverworldWildSpawns_StartPreparedCustomJumpCommand(OverworldWildSpawnState *state,
    FieldSystem *field, int slot, LocalMapObject *object, u8 dir, u8 distance,
    int x, int y, const OverworldWildBehaviorProfile *profile, BOOL suppress)
{ return OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(state, field, slot, object,
    dir, distance, x, y, profile, suppress, 0) == OVERWORLD_MOTION_DECISION_ACCEPTED; }
static BOOL OverworldWildSpawns_TryStartManualHopEmote(OverworldWildSpawnState *state, int slot,
    LocalMapObject *object, u8 required, u8 end, u8 direction, u8 count, u8 frames,
    u8 bubble, BOOL each, BOOL sound)
{ (void)state; (void)slot; (void)object; (void)required; (void)end; (void)direction;
  (void)count; (void)frames; (void)bubble; (void)each; (void)sound; return FALSE; }
static void OverworldWildSpawns_StartNextSpotEmoteStep(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{ (void)state; (void)slot; (void)object; }
static BOOL OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(
    OverworldWildSpawnState *state, int slot, OverworldWildBehaviorProfile *profile)
{ (void)state; (void)slot; (void)profile; return TRUE; }
static void OverworldWildSpawns_HandleFinishedMovementCommand(OverworldWildSpawnState *, int);
"""


DRIVER = r"""
static void Reset(OverworldWildSpawnState *state, FieldSystem *field, LocalMapObject *object)
{
    memset(state, 0, sizeof(*state)); memset(&selectedPolicy, 0, sizeof(selectedPolicy));
    memset(&motion, 0, sizeof(motion));
    *object = (LocalMapObject){.xCurr = 550, .yCurr = 380, .posVec = {0,65536,0}, .flags=1, .movementCommand=255};
    state->spawns[0].object = object; state->movementFieldSystem = field;
    state->spawns[0].active = TRUE;
    inspectOkay = trajectoryOkay = prepOkay = requestOkay = allowCandidate = TRUE;
    candidateDecision = OVERWORLD_MOTION_DECISION_TERRAIN;
    selectedPolicy.actorActive = TRUE; selectedPolicy.chainPauseAction = 0x85; selectedPolicy.chainPauseTicks = 8;
    testProfile = (OverworldWildBehaviorProfile){.lane = {.hopPause=40, .chainRepositionJumpCount=4,
        .chainRepositionDistance=2, .chainRepositionAllowDiagonal=1}};
    shellStarts = beginCalls = roleCalls = completionCalls = 0;
    plannerRejects = plannerCalls = 0;
    surfaceEnabled = FALSE; sourceSurfaceId = targetSurfaceId = OW_WILD_SURFACE_ID_NATIVE_GROUND;
}
static void FinishLeg(OverworldWildSpawnState *state, LocalMapObject *object)
{
    object->xCurr = motion.plan.targetX; object->yCurr = motion.plan.targetY;
    object->flags &= ~2u; object->movementCommand = 255;
    state->movementInProgressMask = 0;
    if (state->movementStagedHopPending[0]
        != OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING) {
        state->movementStagedHopPending[0] = FALSE;
    }
    OverworldWildSpawns_ClearCustomJumpLocal(state, 0);
    motion.phase = OVERWORLD_MOTION_PHASE_IDLE;
}
int main(int argc, char **argv)
{
    (void)argc; OverworldWildSpawnState state; FieldSystem field = {0}; LocalMapObject object;
    u8 mapMatrix[1604] = {47, 17};
    for (unsigned i = 0; i < 47 * 17; i++) mapMatrix[6 + i * 2] = 33;
    field.map_matrix = mapMatrix;
    caseName = argv[1]; Reset(&state, &field, &object);
    if (!strcmp(caseName, "first")) {
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        printf("first admission: starts=%u kind=%u duration=%u pause=%u arc=%u\n",
            beginCalls, motion.plan.kind, motion.plan.duration, motion.plan.pauseFrames,
            state.runtime.movementCustomJumpArcHeightsQ4[0]);
        CHECK(beginCalls == 1 && motion.plan.kind == OVERWORLD_MOTION_KIND_REPOSITION);
        CHECK(motion.plan.duration == 8 && state.runtime.movementCustomJumpArcHeightsQ4[0] == 0);
        CHECK(motion.plan.pauseFrames == 0 && motion.plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NO_CHAIN);
        CHECK((selectedPolicy.chainStepsRemaining & 0xAF) == 0xA4);
    } else if (!strcmp(caseName, "resume")) {
        /* Exact late state from the prior bad Hop: valid grid, four authored
         * repositions, cleared native presentation, actor still settling. */
        selectedPolicy.chainStepsRemaining = 0xA4; selectedPolicy.chainPauseAction = 0x9A;
        object.xCurr = 552; object.yCurr = 382;
        motion.phase = OVERWORLD_MOTION_PHASE_SETTLING;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        printf("settling continuation: roleCalls=%u starts=%u remaining=%u\n", roleCalls, beginCalls,
            selectedPolicy.chainStepsRemaining);
        CHECK(roleCalls == 0 && beginCalls == 0 && selectedPolicy.chainStepsRemaining == 0xA4);
        motion.phase = OVERWORLD_MOTION_PHASE_IDLE;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 1 && motion.plan.kind == OVERWORLD_MOTION_KIND_REPOSITION);
        CHECK(selectedPolicy.chainStepsRemaining == 0xA3 && roleCalls == 0);
    } else if (!strcmp(caseName, "complete")) {
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        for (unsigned index=0; index<4; index++) {
            CHECK(beginCalls == index+1 && motion.plan.kind == OVERWORLD_MOTION_KIND_REPOSITION);
            CHECK(motion.plan.duration == 8 && motion.plan.pauseFrames == 0);
            CHECK((selectedPolicy.chainStepsRemaining & 15) == 4-index);
            FinishLeg(&state, &object);
            OverworldWildSpawns_HandleFinishedMovementCommand(&state, 0);
        }
        CHECK(beginCalls == 4 && selectedPolicy.chainStepsRemaining == 0 && selectedPolicy.chainPauseAction == 0);
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 4 && !MapObject_IsSingleMovementActive(&object));
    } else if (!strcmp(caseName, "steps") || !strcmp(caseName, "jumps")) {
        BOOL jumps = !strcmp(caseName, "jumps");
        selectedPolicy.chainPauseAction = jumps ? 0x83 : 0x84;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 1 && motion.plan.kind == OVERWORLD_MOTION_KIND_REPOSITION);
        CHECK(motion.plan.duration == (jumps ? 7 : 8));
        CHECK(state.runtime.movementCustomJumpArcHeightsQ4[0] == (jumps ? 24 : 0));
        CHECK(motion.plan.pauseFrames == 0 && motion.plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NO_CHAIN);
    } else if (!strcmp(caseName, "ordinary")) {
        CHECK(OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(&state, &field, 0,
            &object, 4, 1, 551, 381, &testProfile, TRUE, 0) == OVERWORLD_MOTION_DECISION_ACCEPTED);
        CHECK(motion.plan.kind == OVERWORLD_MOTION_KIND_HOP && motion.plan.pauseFrames == 40);
        CHECK(motion.plan.duration == 7 && motion.plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NORMAL);
    } else if (!strcmp(caseName, "forward")) {
        selectedPolicy.chainPauseAction = 0x87;
        selectedPolicy.chainPauseTicks = 0;
        selectedPolicy.walkMomentum.direction = 3;
        selectedPolicy.walkMomentum.speed = 4;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 1 && motion.plan.kind == OVERWORLD_MOTION_KIND_HOP);
        CHECK(motion.plan.startX == 550 && motion.plan.startY == 380);
        CHECK(motion.plan.targetX == 552 && motion.plan.targetY == 380);
        CHECK(motion.plan.duration == 8 && motion.plan.pauseFrames == 0);
        CHECK(motion.plan.commitPolicy == OVERWORLD_MOTION_COMMIT_NORMAL);
        CHECK(state.runtime.movementCustomJumpArcHeightsQ4[0] == 24);
        CHECK(state.movementStagedHopDistances[0] == 2
            && state.movementStagedHopPending[0]
                == OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING);
        CHECK(selectedPolicy.chainPauseAction == 0
            && selectedPolicy.chainPauseTicks == 0
            && selectedPolicy.walkMomentum.direction == 3
            && selectedPolicy.walkMomentum.speed == 4);
        FinishLeg(&state, &object);
        OverworldWildSpawns_FinishPendingStagedHop(
            &state, 0, &object);
        CHECK(state.movementStagedHopPending[0] == 0
            && state.movementCooldowns[0] == 0
            && completionCalls == 0);
        CHECK(selectedPolicy.walkMomentum.direction == 3
            && selectedPolicy.walkMomentum.speed == 4);
        CHECK(OverworldWildSpawns_IsChainActionReady(0));
    } else if (!strcmp(caseName, "forward-terrain")) {
        selectedPolicy.chainPauseAction = 0x87;
        selectedPolicy.chainPauseTicks = 0;
        selectedPolicy.walkMomentum.direction = 3;
        selectedPolicy.walkMomentum.speed = 4;
        allowCandidate = FALSE;
        candidateDecision = OVERWORLD_MOTION_DECISION_TERRAIN;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 0 && selectedPolicy.chainPauseAction == 0);
        CHECK(state.movementCooldowns[0] == 0
            && state.movementStagedHopPending[0] == 0);
    } else if (!strcmp(caseName, "forward-occupied")) {
        selectedPolicy.chainPauseAction = 0x87;
        selectedPolicy.chainPauseTicks = 0;
        selectedPolicy.walkMomentum.direction = 3;
        selectedPolicy.walkMomentum.speed = 4;
        allowCandidate = FALSE;
        candidateDecision = OVERWORLD_MOTION_DECISION_OCCUPIED;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 0 && selectedPolicy.chainPauseAction == 0);
        CHECK(state.movementCooldowns[0] == 0
            && state.movementStagedHopPending[0] == 0);
    } else if (!strcmp(caseName, "forward-busy")) {
        selectedPolicy.chainPauseAction = 0x87;
        selectedPolicy.chainPauseTicks = 0;
        selectedPolicy.walkMomentum.direction = 3;
        selectedPolicy.walkMomentum.speed = 4;
        requestOkay = FALSE;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 1 && selectedPolicy.chainPauseAction == 0x87);
        CHECK(state.movementCooldowns[0] == 1
            && state.movementStagedHopPending[0] == 0
            && !MapObject_IsSingleMovementActive(&object));
    } else if (!strcmp(caseName, "blocked")) {
        allowCandidate = FALSE;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 0 && selectedPolicy.chainStepsRemaining == 0);
        CHECK(selectedPolicy.chainPauseAction == 0 && state.movementCooldowns[0] == 8);
    } else if (!strcmp(caseName, "blocked-later")) {
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        FinishLeg(&state, &object); allowCandidate = FALSE;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state, 0);
        CHECK(beginCalls == 1 && selectedPolicy.chainStepsRemaining == 0 && selectedPolicy.chainPauseAction == 0);
        CHECK(!MapObject_IsSingleMovementActive(&object));
        CHECK(state.movementCooldowns[0] == 8);
    } else if (!strcmp(caseName, "temporary-blocked-later")) {
        /* Engine-boundary model of a moving blocker: no candidate this tick,
         * the same landing is available next tick. The native landing and
         * occupancy readers are separate from this policy host witness. */
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        FinishLeg(&state, &object);
        u8 remaining = selectedPolicy.chainStepsRemaining;
        u8 grid = selectedPolicy.chainPauseAction;
        allowCandidate = FALSE;
        candidateDecision = OVERWORLD_MOTION_DECISION_OCCUPIED;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state, 0);
        CHECK(beginCalls == 1 && selectedPolicy.chainStepsRemaining == remaining);
        CHECK(selectedPolicy.chainPauseAction == grid && !MapObject_IsSingleMovementActive(&object));
        allowCandidate = TRUE;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state, 0);
        CHECK(beginCalls == 2 && selectedPolicy.chainStepsRemaining == 0xA3);
    } else if (!strcmp(caseName, "admission")) {
        requestOkay = FALSE;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(beginCalls == 1 && shellStarts == 0 && !MapObject_IsSingleMovementActive(&object));
        CHECK(selectedPolicy.chainStepsRemaining == 0 && selectedPolicy.chainPauseAction == 0x85);
        CHECK(!state.runtime.movementCustomJumpActive[0] && !state.runtime.movementCustomJumpPrepActive[0]);
    } else if (!strcmp(caseName, "retry-later") || !strcmp(caseName, "prep-later")) {
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        FinishLeg(&state, &object);
        u8 remaining = selectedPolicy.chainStepsRemaining, grid = selectedPolicy.chainPauseAction;
        u8 direction = state.movementPendingDirections[0], distance = state.movementPendingDistances[0];
        u8 staged = state.movementStagedHopDistances[0], facing = object.curFacing;
        if (!strcmp(caseName, "retry-later")) requestOkay = FALSE; else prepOkay = FALSE;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state, 0);
        CHECK(selectedPolicy.chainStepsRemaining == remaining && selectedPolicy.chainPauseAction == grid);
        CHECK(state.movementPendingDirections[0] == direction && state.movementPendingDistances[0] == distance);
        CHECK(state.movementStagedHopDistances[0] == staged && object.curFacing == facing);
        CHECK(!MapObject_IsSingleMovementActive(&object));
        requestOkay = prepOkay = TRUE;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state, 0);
        CHECK(selectedPolicy.chainStepsRemaining == 0xA3 && motion.phase == OVERWORLD_MOTION_PHASE_MOVING);
    } else if (!strcmp(caseName, "planner-next")) {
        plannerRejects = 1;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(plannerCalls == 2 && beginCalls == 1);
        CHECK(selectedPolicy.chainStepsRemaining == 0xA4 && shellStarts == 1);
    } else if (!strcmp(caseName, "planner-exhausted")) {
        trajectoryOkay = FALSE;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(plannerCalls == 4 && beginCalls == 0);
        CHECK(selectedPolicy.chainStepsRemaining == 0 && selectedPolicy.chainPauseAction == 0);
        CHECK(state.movementCooldowns[0] == 8 && !MapObject_IsSingleMovementActive(&object));
    } else if (!strcmp(caseName, "temporary-first")) {
        allowCandidate = FALSE; candidateDecision = OVERWORLD_MOTION_DECISION_OCCUPIED;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(selectedPolicy.chainPauseAction == 0x85 && selectedPolicy.chainStepsRemaining == 0);
        CHECK(state.movementCooldowns[0] == 1 && beginCalls == 0);
        allowCandidate = TRUE;
        OverworldWildSpawns_CommitDeferredChainMovementPause(&state, 0, &testProfile);
        CHECK(selectedPolicy.chainStepsRemaining == 0xA4 && beginCalls == 1);
    } else if (!strcmp(caseName, "typed-results")) {
        OverworldWildChainRepositionResult result;
        selectedPolicy.chainPauseAction = 0x95; selectedPolicy.chainStepsRemaining = 0x20;
        allowCandidate = FALSE;
        CHECK(!OverworldWildSpawns_RunChainReposition(&state, 0, &testProfile, 0x20, &result));
        CHECK(result.outcome == OW_WILD_CHAIN_ABORT && result.reason == OVERWORLD_MOTION_DECISION_NO_CANDIDATE);
        CHECK(result.encodedRemaining == 0x20 && result.gridDelta == 0);
        candidateDecision = OVERWORLD_MOTION_DECISION_OCCUPIED;
        CHECK(!OverworldWildSpawns_RunChainReposition(&state, 0, &testProfile, 0xA4, &result));
        CHECK(result.outcome == OW_WILD_CHAIN_RETRY && result.reason == OVERWORLD_MOTION_DECISION_OCCUPIED);
        CHECK(result.encodedRemaining == 0xA4 && result.gridDelta == 0);
        CHECK(!OverworldWildSpawns_RunChainReposition(&state, 0, &testProfile, 0xA1, &result));
        CHECK(result.outcome == OW_WILD_CHAIN_COMPLETE && result.reason == OVERWORLD_MOTION_DECISION_ACCEPTED);
    } else if (!strcmp(caseName, "landing-classifier")) {
#define LAND(field, x, y) OverworldWildSpawns_ClassifyBehaviorHopLandingTile(&state, 0, field, 0x3FF, x, y, x, y)
        CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_ACCEPTED);
        CHECK(OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(&state, 0, &field, 0x3FF, 551, 381, 551, 381));
        CHECK(LAND(NULL, 551, 381) == OVERWORLD_MOTION_DECISION_PROFILE);
        CHECK(LAND(&field, -1, 381) == OVERWORLD_MOTION_DECISION_BLOCKED);
        inspectOkay = FALSE; CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_PROFILE); inspectOkay = TRUE;
        allowCandidate = FALSE; candidateDecision = OVERWORLD_MOTION_DECISION_TERRAIN;
        CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_TERRAIN);
        candidateDecision = OVERWORLD_MOTION_DECISION_OCCUPIED;
        CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_OCCUPIED);
        CHECK(!OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(&state, 0, &field, 0x3FF, 551, 381, 551, 381));
        allowCandidate = TRUE;
        selectedPolicy.chainPauseAction = 0x9A; selectedPolicy.chainStepsRemaining = 0xA4;
        CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_BLOCKED);
        selectedPolicy.chainPauseAction = 0;
        surfaceEnabled = TRUE; sourceSurfaceId = 1; targetSurfaceId = 2;
        CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_TERRAIN);
        targetSurfaceId = 1;
        CHECK(LAND(&field, 551, 381) == OVERWORLD_MOTION_DECISION_ACCEPTED);
#undef LAND
    } else if (!strcmp(caseName, "ready-parity")) {
        const int slots[] = {-1, 0, 9, 10, 256};
        for (unsigned i = 0; i < sizeof(slots) / sizeof(slots[0]); i++) {
            for (unsigned phase = 0; phase <= OVERWORLD_MOTION_PHASE_CANCELED; phase++) {
                for (unsigned active = 0; active < 2; active++) {
                    for (unsigned readable = 0; readable < 2; readable++) {
                        selectedPolicy.actorActive = active; inspectOkay = readable; motion.phase = phase;
                        BOOL expected = slots[i] >= 0 && slots[i] < 10 && active && readable
                            && (phase == OVERWORLD_MOTION_PHASE_IDLE || phase == OVERWORLD_MOTION_PHASE_CANCELED);
                        CHECK(OverworldWildSpawns_IsChainActionReady(slots[i]) == expected);
                    }
                }
            }
        }
    } else return 2;
    printf("PASS chain lifecycle %s: %u assertions\n", caseName, assertions);
    return 0;
}
"""


def execute(source, case):
    with tempfile.TemporaryDirectory(prefix="chain-lifecycle-") as directory:
        unit, binary = Path(directory) / "chain.c", Path(directory) / "chain"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-function", "-Wno-unused-variable", "-DOVERWORLD_MOTION_HOST", "-DOVERWORLD_ROLE_CONTROLLER_HOST", "-I", str(ROOT / "include"),
                   str(unit), str(ROOT / "lib/overworld/overworld_motion_model.c"),
                   str(ROOT / "lib/overworld/overworld_role_controller.c"), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr)
        return subprocess.run([str(binary), case], capture_output=True, text=True)


class ChainActionLifecycleTests(unittest.TestCase):
    def test_temporary_blocker_preserves_selected_continuation(self):
        result = execute(harness_source(), "temporary-blocked-later")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_chain_action_handoff(self):
        source = harness_source()
        for case in ("first", "resume", "complete", "steps", "jumps", "ordinary",
                     "forward", "forward-terrain", "forward-occupied", "forward-busy",
                     "blocked", "blocked-later", "admission",
                     "retry-later", "prep-later", "planner-next", "planner-exhausted", "temporary-first", "typed-results", "landing-classifier", "ready-parity"):
            with self.subTest(case=case):
                result = execute(source, case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_known_bad_actual_body_changes_are_rejected(self):
        source = harness_source()
        extract = module("chain_mutation_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
        mutations = (
            ("late first classification", "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed", "OverworldMotionDecision",
             "chainReposition = (policy.chainPauseAction\n        & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)\n        == OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER;",
             "chainReposition = (policy.chainStepsRemaining & 0x80) != 0;", "first"),
            ("lost continuation", "OverworldWildSpawns_CommitDeferredChainMovementPause", "void",
             "OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);", "(void)state;", "resume"),
            ("grid decoded as deferred action", "OverworldWildSpawns_CommitDeferredChainMovementPause", "void",
             "if ((encodedAction & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)",
             "if (0 && (encodedAction & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)", "resume"),
            ("remaining count not advanced", "OverworldWildSpawns_RunChainReposition", "BOOL",
             "remaining = (encodedRemaining - 1) & 0x0F;", "remaining = encodedRemaining & 0x0F;", "complete"),
            ("temporary rejection finishes chain", "OverworldWildSpawns_ApplyChainRepositionResult", "BOOL",
             "if (result->outcome == OW_WILD_CHAIN_RETRY", "if (0 && result->outcome == OW_WILD_CHAIN_RETRY", "temporary-blocked-later"),
            ("structural exhaustion stays pending", "OverworldWildSpawns_RunChainReposition", "BOOL",
             "result->outcome = OW_WILD_CHAIN_ABORT;", "result->outcome = OW_WILD_CHAIN_RETRY;", "blocked"),
            ("planner stops searching", "OverworldWildSpawns_RunChainReposition", "BOOL",
             "if (decision != OVERWORLD_MOTION_DECISION_BLOCKED\n            && decision != OVERWORLD_MOTION_DECISION_TERRAIN)",
             "if (1)", "planner-next"),
            ("occupancy mislabeled structural", "OverworldWildSpawns_ClassifyBehaviorHopLandingTile", "OverworldMotionDecision",
             ": OVERWORLD_MOTION_DECISION_OCCUPIED;", ": OVERWORLD_MOTION_DECISION_TERRAIN;", "temporary-blocked-later"),
            ("forward occupancy stays pending", "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand", "BOOL",
             "state->movementStagedHopFinishWithTired[slot] = landingDecision;",
             "state->movementStagedHopFinishWithTired[slot] = landingDecision == OVERWORLD_MOTION_DECISION_OCCUPIED "
             "? OVERWORLD_MOTION_DECISION_ACCEPTED : landingDecision;", "forward-occupied"),
        )
        for label, name, result_type, old, new, case in mutations:
            with self.subTest(mutation=label):
                function = extract.production_function(source, name, result_type)
                changed = replace_once(function, old, new)
                result = execute(replace_once(source, function, changed), case)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("motion start invariant failed", result.stderr)


if __name__ == "__main__":
    unittest.main()
