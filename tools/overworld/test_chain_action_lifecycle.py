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
                          "chainRepositionAllowCardinal, chainRepositionAllowDiagonal, chainRepositionDust, onReachAction; u16 chillAllowedTerrainMask;")
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
    LocalMapObject *object, u8 required, u8 direction, u8 count, BOOL sound)
{ (void)state; (void)slot; (void)object; (void)required; (void)direction;
  (void)count; (void)sound; return FALSE; }
static BOOL OverworldActorWalkPolicy_SampleChainChance(u32 chance)
{ (void)chance; return FALSE; }
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


def hop_vector_preflight_source(wild=None, *, directed=False):
    """Extract the actual admission bodies; only engine boundaries count calls."""
    extract = module("hop_preflight_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    wild = WILD.read_text() if wild is None else wild
    planner = (ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c").read_text()
    # Use the real pure vector predicate, not a second host choice algorithm.
    lane = extract.production_function(planner, "OverworldActorHopPlanner_GetLane",
                                       "inline const OverworldWildBehaviorProfileData *")
    vector = extract.production_function(planner, "OverworldActorHopPlanner_PlanVector", "OverworldMotionDecision")
    planned = extract.production_function(wild, "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand", "BOOL")
    chain = extract.production_function(wild, "OverworldWildSpawns_TryStartChainForwardHop", "u8")
    actual = lane + vector + HOP_PREFLIGHT_VECTOR_BRIDGE + planned + chain
    if directed:
        actual += extract.production_function(wild, "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand", "BOOL")
    definitions = {}
    for source in (wild, *((ROOT / "include" / name).read_text() for name in
            ("overworld_wild_behavior_data.h", "overworld_wild_spawns_internal.h",
             "overworld_wild_helper.h", "overworld_wild_movement.h"))):
        for line in source.replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)", line)
            if match:
                definitions[match[1]] = line
    wanted = set(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b", actual + HOP_PREFLIGHT_SUPPORT
                           + HOP_PREFLIGHT_DRIVER + HOP_PREFLIGHT_DIRECTED_DRIVER))
    macros = []
    while wanted:
        name = wanted.pop()
        if name in {re.match(r"#define\s+(\w+)", line)[1] for line in macros}:
            continue
        line = definitions[name]
        macros.append(line)
        wanted.update(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b", line.split(name, 1)[1]))
    driver = HOP_PREFLIGHT_DIRECTED_DRIVER if directed else HOP_PREFLIGHT_DRIVER
    return "\n".join(macros) + "\n" + HOP_PREFLIGHT_SUPPORT + actual + driver


HOP_PREFLIGHT_SUPPORT = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_motion_model.h"
#include "overworld_role_controller.h"
typedef int BOOL;
typedef struct OverworldWildBehaviorProfileData {
    u8 chillAction, hopMinDistance, hopMaxDistance, hopAllowNonCardinal, hopPause, walkOptions;
} OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile { OverworldWildBehaviorProfileData owner, tired; u8 jumpLevel; } OverworldWildBehaviorProfile;
typedef struct OverworldWildBehaviorPrimitives { u8 unused; } OverworldWildBehaviorPrimitives;
typedef struct LocalMapObject { int xCurr, yCurr; u8 facing; } LocalMapObject;
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildSpawnState {
    struct { LocalMapObject *object; u8 active; } spawns[10];
    FieldSystem *movementFieldSystem;
    u8 movementSpotStates[10], movementStagedHopFinishWithTired[10], movementStagedHopDistances[10], movementStagedHopPending[10], movementCooldowns[10];
    s16 movementStagedHopOriginX[10], movementStagedHopOriginY[10], movementStagedHopTargetX[10], movementStagedHopTargetY[10];
} OverworldWildSpawnState;
typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state; FieldSystem *fieldSystem; LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile; const OverworldWildBehaviorPrimitives *primitives;
    u8 slot; u16 allowedTile; u8 jumpLevel, avoidPreviousTile;
} OverworldWildDirectionStepContext;
typedef struct OverworldActorHopPlanCall {
    const OverworldWildBehaviorProfile *profile; s16 deltaX, deltaY; u8 spotState, direction, distance;
} OverworldActorHopPlanCall;
static unsigned worldQueries, invalidTargetQueries, vectorCalls, roleRequests, hopStarts, walkStarts, planCalls, facingWrites;
static OverworldMotionDecision landingResult;
static u16 lastAllowed;
static void Check(BOOL good, const char *message) { if (!good) { fprintf(stderr, "%s\n", message); exit(1); } }
static int OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object) { return object->xCurr; }
static int OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object) { return object->yCurr; }
static int OverworldWildSpawns_Abs(int value) { return abs(value); }
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetControllerLane(const OverworldWildBehaviorProfile *profile, u8 spot) {
    return spot == OW_WILD_SPAWNER_SPOT_STATE_TIRED ? &profile->tired : &profile->owner;
}
static OverworldMotionDecision OverworldWildSpawns_ClassifyBehaviorHopLandingTile(OverworldWildSpawnState *state, int slot, FieldSystem *field, u16 allowed, int x, int y, int tx, int ty) {
    (void)state; (void)slot; (void)field; (void)tx; (void)ty;
    worldQueries++; lastAllowed = allowed;
    if (x == 584 && y == 397) invalidTargetQueries++;
    return landingResult;
}
static u32 OverworldWildSpawns_ReduceRole(int slot, u32 request, u32 flags) {
    (void)slot; (void)flags; roleRequests++;
    return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED | (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT);
}
static u8 OverworldWalk_DirectionFromDelta(int dx, int dy) { return dx != 0 ? 2 + (dx > 0) : dy > 0; }
static BOOL OverworldWildSpawns_TryStartAcceleratedWalkStep(const OverworldWildDirectionStepContext *context, const void *policy, u8 direction, BOOL preview) {
    (void)context; (void)policy; (void)direction; (void)preview; walkStarts++; return TRUE;
}
static OverworldMotionDecision OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(OverworldWildSpawnState *state, FieldSystem *field, int slot, LocalMapObject *object, u8 direction, u8 distance, int x, int y, const OverworldWildBehaviorProfile *profile, BOOL suppress, u8 time) {
    (void)state; (void)field; (void)slot; (void)object; (void)direction; (void)distance; (void)x; (void)y; (void)profile; (void)suppress; (void)time;
    hopStarts++; return OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static void OverworldWildSpawns_ClearStagedHopTargetLocal(OverworldWildSpawnState *state, int slot) { state->movementStagedHopPending[slot] = 0; }
static u16 OverworldWildSpawns_GetAllowedTileForSpotState(const OverworldWildBehaviorProfile *profile, u8 spot) { (void)profile; (void)spot; return 512; }
static u8 OverworldWildSpawns_GetBehaviorHopMinDistance(const OverworldWildBehaviorProfile *profile, u8 spot) { return OverworldWildSpawns_GetControllerLane(profile, spot)->hopMinDistance; }
static u8 OverworldWildSpawns_GetBehaviorHopMaxDistance(const OverworldWildBehaviorProfile *profile, u8 spot) { return OverworldWildSpawns_GetControllerLane(profile, spot)->hopMaxDistance; }
static int OverworldWildSpawns_MovementDirectionDeltaX(int direction) { return direction == 2 ? -1 : direction == 3 ? 1 : 0; }
static int OverworldWildSpawns_MovementDirectionDeltaY(int direction) { return direction == 0 ? -1 : direction == 1 ? 1 : 0; }
static BOOL OverworldWildSpawns_IsPlayerTile(FieldSystem *field, int x, int y) { (void)field; (void)x; (void)y; return FALSE; }
static BOOL OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(FieldSystem *field, LocalMapObject *object, int x, int y) { (void)field; (void)object; (void)x; (void)y; return FALSE; }
static BOOL OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(OverworldWildSpawnState *state, int slot, FieldSystem *field, u16 allowed, int x, int y, int tx, int ty) {
    return OverworldWildSpawns_ClassifyBehaviorHopLandingTile(state,slot,field,allowed,x,y,tx,ty) == OVERWORLD_MOTION_DECISION_ACCEPTED;
}
static BOOL OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(OverworldWildSpawnState *state, FieldSystem *field, int slot, const OverworldWildBehaviorProfile *profile, u16 allowed, int x, int y, const u8 *directions, int count, u8 mode) {
    (void)state; (void)field; (void)slot; (void)profile; (void)allowed; (void)x; (void)y; (void)directions; (void)count; (void)mode; planCalls++; return FALSE;
}
static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 facing) { object->facing = facing; facingWrites++; }
static void ResetCounts(void) { worldQueries = invalidTargetQueries = vectorCalls = roleRequests = hopStarts = walkStarts = planCalls = facingWrites = 0; }
"""

HOP_PREFLIGHT_VECTOR_BRIDGE = r"""
static BOOL OverworldWildSpawns_TryGetBehaviorHopVector(const OverworldWildBehaviorProfile *profile, u8 spotState, int dx, int dy, u8 *direction, u8 *distance) {
    OverworldActorHopPlanCall call = {.profile=profile, .spotState=spotState, .deltaX=(s16)dx, .deltaY=(s16)dy};
    vectorCalls++;
    if (OverworldActorHopPlanner_PlanVector(&call) != OVERWORLD_MOTION_DECISION_ACCEPTED) return FALSE;
    if (direction != NULL) { *direction=call.direction; *distance=call.distance; }
    return TRUE;
}
"""

HOP_PREFLIGHT_DRIVER = r"""
int main(int argc, char **argv) {
    LocalMapObject object={.xCurr=589, .yCurr=399}; FieldSystem field={0};
    OverworldWildSpawnState state={.movementFieldSystem=&field};
    OverworldWildBehaviorProfile profile={.owner={.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_HOP, .hopMinDistance=1, .hopMaxDistance=6, .hopAllowNonCardinal=1}};
    state.spawns[7].object=&object; state.spawns[7].active=TRUE;
    landingResult=OVERWORLD_MOTION_DECISION_ACCEPTED;
    if (argc == 2 && !strcmp(argv[1], "ordinary-invalid")) {
        const int deltas[][2]={{-14,-1},{0,0},{0,7}};
        for (unsigned i=0;i<3;i++) {
            ResetCounts(); state.movementStagedHopFinishWithTired[7]=77;
            OverworldWildSpawnState before=state;
            Check(!OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(&state,&field,7,&profile,512,589+deltas[i][0],399+deltas[i][1],589+deltas[i][0],399+deltas[i][1],0), "invalid ordinary Hop started");
            Check(worldQueries==0, "invalid ordinary Hop queried world before vector rejection");
            Check(roleRequests==0 && hopStarts==0 && walkStarts==0 && !memcmp(&state,&before,sizeof(state)), "invalid ordinary Hop changed motion or staged state");
        }
    } else {
        Check(OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(&state,&field,7,&profile,512,583,393,583,393,0), "valid diagonal Hop rejected");
        Check(worldQueries==1 && vectorCalls==1 && roleRequests==1 && hopStarts==1 && walkStarts==0 && state.movementStagedHopDistances[7]==6, "valid Hop lost landing role or START");
        ResetCounts(); landingResult=OVERWORLD_MOTION_DECISION_TERRAIN;
        Check(!OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(&state,&field,7,&profile,512,583,393,583,393,0), "terrain-blocked valid Hop started");
        Check(worldQueries==1 && roleRequests==0 && hopStarts==0, "valid blocked Hop bypassed landing");
        ResetCounts(); landingResult=OVERWORLD_MOTION_DECISION_ACCEPTED; profile.owner.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
        Check(OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(&state,&field,7,&profile,512,588,399,588,399,0), "flat Walk rejected");
        Check(worldQueries==1 && (lastAllowed&OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER) && vectorCalls==0 && roleRequests==0 && walkStarts==1 && hopStarts==0, "flat Walk lost strict landing or Walk START");
        profile.owner.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_HOP;
        profile.owner.hopMinDistance=OW_WILD_SPAWNER_CHAIN_HOP_FORWARD_DISTANCE+1;
        const OverworldMotionDecision decisions[]={OVERWORLD_MOTION_DECISION_ACCEPTED, OVERWORLD_MOTION_DECISION_TERRAIN, OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY, OVERWORLD_MOTION_DECISION_OCCUPIED};
        for (unsigned i=0;i<4;i++) {
            ResetCounts(); landingResult=decisions[i]; state.movementStagedHopFinishWithTired[7]=77;
            u8 result=OverworldWildSpawns_TryStartChainForwardHop(&state,7,&profile,2);
            Check(worldQueries==1 && state.movementStagedHopFinishWithTired[7]==decisions[i], "invalid chain Hop lost original landing receipt");
            Check(result==(decisions[i]==OVERWORLD_MOTION_DECISION_ACCEPTED ? 0 : OW_WILD_CHAIN_ABORT), "invalid chain Hop changed abort or retry");
            Check(roleRequests==0 && hopStarts==0 && walkStarts==0, "invalid chain Hop reached START");
        }
    }
    puts("PASS actual Hop preflight"); return 0;
}
"""

HOP_PREFLIGHT_DIRECTED_DRIVER = r"""
int main(int argc, char **argv) {
    (void)argc; (void)argv;
    LocalMapObject object={.xCurr=570, .yCurr=396}; FieldSystem field={0};
    OverworldWildSpawnState state={.movementFieldSystem=&field};
    OverworldWildBehaviorProfile profile={.owner={.chillAction=OW_WILD_BEHAVIOR_LOCOMOTION_HOP, .hopMinDistance=1, .hopMaxDistance=2, .hopAllowNonCardinal=0, .hopPause=9}};
    const u8 directions[]={3}; state.spawns[0].object=&object; state.spawns[0].active=TRUE;
    landingResult=OVERWORLD_MOTION_DECISION_TERRAIN;
    Check(!OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(&state,&field,0,&profile,2,0,directions,1,OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY), "valid blocked directed Hop started");
    Check(worldQueries==2 && planCalls==0 && state.movementCooldowns[0]==9, "valid blocked vector lost blocked branch");
    ResetCounts();
    Check(!OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(&state,&field,0,&profile,14,1,directions,1,OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY), "invalid directed Hop started");
    Check(invalidTargetQueries==0, "invalid directed vector queried impossible target");
    Check(planCalls==2 && worldQueries==2 && state.movementCooldowns[0]==9, "invalid vector did not continue to valid fallback checks");
    puts("PASS actual directed vector order"); return 0;
}
"""


def hop_effects_source():
    """Use actual adapter packets and borrowed body; mock only lease/engine/RNG."""
    extract = module("hop_effect_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    wild = WILD.read_text()
    mount = (ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    native = (ROOT / "lib/overworld/overworld_condition_moving_notice_native.c").read_text().replace("\nOverworldBehaviorConditionStatus Overworld", "\nstatic OverworldBehaviorConditionStatus Overworld")
    chooser = extract.production_function(
        (ROOT / "include/overworld_hop_effects_internal.h").read_text(),
        "OverworldActorWalkPolicy_SampleHopEffectsInline", "inline u8")
    actual = chooser.replace("SampleHopEffectsInline", "SampleHopEffects")
    actual += "\n".join(extract.production_function(wild, name, result) for name, result in (
        ("OverworldWildSpawns_ShowBubble", "void"),
        ("OverworldWildSpawns_StartNextSpotEmoteStep", "BOOL"),
    ))
    actual += extract.production_function(native, "OverworldHopPresentation_Run", "OverworldBehaviorConditionStatus")
    dispatcher = extract.production_function(native, "OverworldConditionNative_Run", "OverworldBehaviorConditionStatus")
    # Keep the exact common packet gate and private operation dispatch. Normal
    # condition reduction has its own existing compiled-source fixtures.
    gate = dispatcher[dispatcher.index("    if(call==NULL"):dispatcher.index("    if (call->operation>OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS")]
    gate = gate.replace("#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)", "").replace("#endif", "")
    actual += "\nstatic OverworldBehaviorConditionStatus DispatchHop(OverworldConditionNativeCall *call)\n{\n" + gate + "    return OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT;\n}\n"
    lease = (ROOT / "src/overworld_hop_lease.c").read_text()
    left = lease.index("{", lease.index("OverworldHopPresentation_Acquire("))
    actual += HOP_LEASE_STUB.replace("LEASE_BODY", lease[left:].replace("(u32)field", "(u32)(uintptr_t)field"))
    for owner, table in ((wild, "sOverworldWildHopOps"), (mount, "sOverworldMountHopOps")):
        left = owner.index("static const OverworldHopPresentationOps " + table)
        right = owner.index("};", left) + 2
        actual += re.sub(r'__attribute__\(\(section\("[^"]+"\)\)\)', '', owner[left:right]) + "\n"
    actual += "\n".join(extract.production_function(wild, name, result) for name, result in (
        ("OverworldWildSpawns_TryStartManualHopEmote", "u8"),
        ("OverworldWildSpawns_TryStartChainPauseAction", "u8"),
    ))
    actual += extract.production_function(mount, "OverworldMount_TickChainHopEffects", "void")
    begin = extract.production_function(mount, "OverworldMount_BeginSharedMotion", "BOOL")
    left = begin.index("        if (sOverworldMountState.walkEndState == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP)", begin.index("sOverworldMountState.motionIdentity = call.motionIdentity;"))
    right = begin.index("        if (intent.kind == OVERWORLD_MOTION_KIND_WALK)", left)
    actual += "\nstatic void AcceptHopLatch(void)\n{\n" + begin[left:right] + "}\n"
    definitions = {}
    for path in (WILD, ROOT / "include/overworld_wild_behavior_data.h", ROOT / "include/overworld_wild_movement.h",
                 ROOT / "include/overworld_wild_spawns_internal.h", ROOT / "include/overworld_hop_presentation_native.h"):
        for line in path.read_text().replace("\\\n", " ").splitlines():
            match = re.match(r"#define\s+(\w+)\b", line)
            if match:
                definitions[match[1]] = line
    present = set(re.findall(r"^#define\s+(\w+)", HOP_EFFECT_STUBS, re.M))
    wanted = set(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b|\bOVERWORLD_HOP_PRESENTATION_[A-Z_0-9]+\b", actual + HOP_EFFECT_DRIVER))
    macros = []
    while wanted:
        name = wanted.pop()
        if name in present:
            continue
        line = definitions[name]
        macros.append(line)
        present.add(name)
        wanted.update(re.findall(r"\bOW_WILD_[A-Z_0-9]+\b|\bOVERWORLD_HOP_PRESENTATION_[A-Z_0-9]+\b", line.split(name, 1)[1]))
    return "\n".join(macros) + HOP_EFFECT_STUBS + actual + HOP_EFFECT_DRIVER


HOP_EFFECT_STUBS = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "constants/sndseq.h"
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OW_WILD_RUNTIME(state) (&(state)->runtime)
#define OW_WILD_MAX_SPAWNS 10
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_BEGIN 1
#define OVERWORLD_MOUNT_MOTION_NONE 0
#define OVERWORLD_MOUNT_MOTION_HOP 1
#define OVERWORLD_MOUNT_WALK_END_CHAIN_HOP 4
typedef struct LocalMapObject { u8 curFacing; union { u32 flags; u8 active; }; } LocalMapObject;
#define MAPOBJECTFLAG_SINGLE_MOVEMENT 1
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct OverworldWildBehaviorProfileData { u8 chainRepositionJumpCount, onReachAction; } OverworldWildBehaviorProfileData;
typedef struct OverworldWildBehaviorProfile { OverworldWildBehaviorProfileData owner, tired; } OverworldWildBehaviorProfile;
typedef struct OverworldActorWalkPolicyCall { u8 direction, distance; } OverworldActorWalkPolicyCall;
typedef struct OverworldWildChainRepositionResult { u8 outcome; } OverworldWildChainRepositionResult;
typedef struct OverworldWildSpawnState {
    struct { LocalMapObject *object; u16 species; u8 form, active; } spawns[10];
    u8 movementSpotStates[10], movementEmoteJumpsRemaining[10], movementEmoteTimers[10];
    u8 movementEmoteSteps[10], movementEmoteDirections[10], movementEmoteEndStates[10];
    u8 movementEmoteBubbleIds[10], movementEmoteShowBubbleEachJump[10], movementEmotePlayCryOnHop[10];
    u8 movementBattleSettleFrames; FieldSystem *movementFieldSystem;
    struct { LocalMapObject *movementEmotePartnerPrepObjects[10]; u8 movementEmotePlayHopSound[10]; } runtime;
} OverworldWildSpawnState;
typedef struct OverworldMountRuntimeState {
    FieldSystem *fieldSystem;
    struct { u8 motionMode; OverworldWildBehaviorProfileData profile; struct { u16 species; u8 form; } binding; } snapshot;
    u8 walkEndState; u32 reservedPriorFollowerPolicy;
} OverworldMountRuntimeState;
typedef int OverworldBehaviorConditionStatus;
#define OVERWORLD_BEHAVIOR_CONDITION_OK 0
#define OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT 1
#define OVERWORLD_CONDITION_NATIVE_CALL_VERSION 2
#define OVERWORLD_CONDITION_NATIVE_TARGET_ACCESS 2
typedef struct OverworldHopPresentationOps {
    union { BOOL (*startNext)(OverworldWildSpawnState *, int, LocalMapObject *); LocalMapObject *(*follower)(void); };
    union { void (*ensureFrame)(OverworldWildSpawnState *, FieldSystem *); void (*cry)(u16,u8); };
    void (*heart)(LocalMapObject *,u8);
    u8 (*choices)(u32);
} OverworldHopPresentationOps;
typedef struct OverworldConditionNativeCall {
    union { void *runtime; OverworldMountRuntimeState *hopMount; };
    OverworldWildSpawnState *state;
    FieldSystem *field;
    LocalMapObject *hopObject;
    union { u32 blobSize; struct { u8 hopRequiredState,hopDirection,hopCount,hopOptions; }; };
    const OverworldHopPresentationOps *hopOps;
    u16 version,size; u8 slot,subjectMovementSpeed,operation,reserved;
} OverworldConditionNativeCall;
typedef struct OverworldQueryCodeAddonEntry { OverworldBehaviorConditionStatus (*conditionNative)(OverworldConditionNativeCall *); } OverworldQueryCodeAddonEntry;
static OverworldMountRuntimeState sOverworldMountState;
static LocalMapObject mountedObject;
static BOOL followerCurrent = TRUE;
static unsigned rngCalls, cries, hearts, commands, sounds;
static u32 draws[2], chances[2];
static BOOL OverworldActorWalkPolicy_SampleChainChance(u32 chance) {
    chances[rngCalls % 2] = chance;
    return draws[rngCalls++ % 2] < chance;
}
static void PlayCry(u16 species, u8 form) { if (species != 74 || form != 2) cries += 100; cries++; }
static void OverworldWildBubble_ShowQuiet(LocalMapObject *object, u8 id) { if (object == NULL || id != 0) hearts += 100; hearts++; }
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *object) { return object->active; }
static u32 MapObject_MovementCommandFromDirection(u8 direction, u32 command) { return command + direction; }
static void OverworldWildSpawns_StartSpotEmoteCommand(LocalMapObject *object, u32 command) { (void)command; object->active = TRUE; commands++; }
static void PlaySE(u32 sound) { (void)sound; sounds++; }
static void OverworldWildSpawns_StartHopStartSoundSuppression(OverworldWildSpawnState *state, int slot) { (void)state; (void)slot; }
static void OverworldWildSpawns_EnsureFrameMovementTask(OverworldWildSpawnState *state, FieldSystem *field) { (void)state; (void)field; }
static u8 BuildLookPlan(u8 direction) { return direction; }
static int ResolveLook(u8 plan, u8 step, u8 count, u8 timer) { (void)step; (void)count; (void)timer; return plan; }
static struct { u8 (*buildLookPlan)(u8); int (*resolveLook)(u8,u8,u8,u8); } policy = {BuildLookPlan, ResolveLook};
static struct { typeof(policy) *policy; } policyEntry = {&policy};
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&policyEntry)
static const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetControllerLane(const OverworldWildBehaviorProfile *p, u8 spot) { return spot == 3 ? &p->tired : &p->owner; }
static u8 OverworldWildSpawns_TryStartChainForwardHop(OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorProfile *p,u8 d) { (void)s; (void)slot; (void)p; (void)d; return FALSE; }
static BOOL OverworldWildSpawns_IsChainActionReady(int slot) { (void)slot; return FALSE; }
static void OverworldWildSpawns_InitPolicyCall(OverworldActorWalkPolicyCall *c,int slot,u8 op) { (void)c; (void)slot; (void)op; }
static BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *c) { (void)c; return FALSE; }
static BOOL OverworldWildSpawns_RunChainReposition(OverworldWildSpawnState *s,int slot,const OverworldWildBehaviorProfile *p,u8 d,OverworldWildChainRepositionResult *r) { (void)s; (void)slot; (void)p; (void)d; (void)r; return FALSE; }
static BOOL OverworldWildSpawns_ApplyChainRepositionResult(int slot,const OverworldWildChainRepositionResult *r) { (void)slot; (void)r; return FALSE; }
static u8 OverworldWildSpawns_GetLookAroundFrames(u8 ticks) { return ticks; }
static void OverworldWildSpawns_ResetEmotePresentationStyle(OverworldWildSpawnState *s,int slot,u8 id) { s->movementEmoteBubbleIds[slot]=id; }
static LocalMapObject *OverworldMount_GetFollowerObject(void) { return followerCurrent ? &mountedObject : NULL; }
'''

HOP_LEASE_STUB = r'''
static BOOL leaseCurrent = TRUE;
static const OverworldQueryCodeAddonEntry hostHopEntry = { DispatchHop };
typedef struct OverworldQueryCodeAddonOwner { u32 fieldIdentity; u16 fieldEpoch,mapGeneration; } OverworldQueryCodeAddonOwner;
typedef struct OverworldQueryCodeAddonServiceEntry { u32 magic; u16 version,size; void *state; void *load; const OverworldQueryCodeAddonEntry *(*acquire)(const OverworldQueryCodeAddonOwner *); void *unload; } OverworldQueryCodeAddonServiceEntry;
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC 0x53444F57u
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION 2
static u32 hostContext = 0x00340012u;
static BOOL hostGate = TRUE;
static FieldSystem *hostCurrentField;
static u32 ReadContext(void) { return hostContext; }
static struct { u32 (*getContext)(void); } hostCompat = { ReadContext };
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&hostCompat)
static void *ReadConditionGate(void) { return hostGate ? &hostCompat : NULL; }
#define OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE ReadConditionGate
static const OverworldQueryCodeAddonEntry *ReadLease(const OverworldQueryCodeAddonOwner *owner) {
    return leaseCurrent && owner->fieldIdentity==(u32)(uintptr_t)hostCurrentField
        && owner->fieldEpoch==0x12 && owner->mapGeneration==0x34 ? &hostHopEntry : NULL;
}
static OverworldQueryCodeAddonServiceEntry hostService = {
    OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC, 2, sizeof(OverworldQueryCodeAddonServiceEntry), NULL,NULL, ReadLease,NULL
};
#define OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR ((uintptr_t)&hostService)
static const OverworldQueryCodeAddonEntry *OverworldHopPresentation_Acquire(FieldSystem *field) LEASE_BODY
'''


HOP_EFFECT_DRIVER = r'''
#define CHECK(test) do { if (!(test)) { fprintf(stderr,"Hop effect invariant failed line%d\n",__LINE__); return 1; } } while(0)
int main(int argc, char **argv) {
    (void)argc; OverworldWildSpawnState state = {0}; LocalMapObject object = {0};
    OverworldWildBehaviorProfile profile = {0};
    FieldSystem field = {0}; hostCurrentField=&field; state.movementFieldSystem=&field; sOverworldMountState.fieldSystem=&field;
    state.spawns[0].object=&object; state.spawns[0].active=TRUE; state.spawns[0].species=74; state.spawns[0].form=2;
    if (!strcmp(argv[1],"chooser")) {
        const u32 chance[] = {0,25,50,100};
        for (u32 code=0; code<16; code++) {
            for (u32 first=0; first<100; first++) {
                for (u32 second=0; second<100; second++) {
                    u32 heart=code&3u, cry=(code>>2)&3u;
                    rngCalls=0; draws[0]=first; draws[1]=second;
                    u8 actual=OverworldActorWalkPolicy_SampleHopEffects(code);
                    u8 expected=(heart && first<chance[heart])
                        | ((cry && (heart ? second:first)<chance[cry])<<1);
                    CHECK(actual==expected);
                    CHECK(rngCalls==(unsigned)(heart!=0)+(unsigned)(cry!=0));
                }
            }
        }
    } else if (!strcmp(argv[1],"wild")) {
        for (u8 code=0; code<4; code++) {
            state.movementSpotStates[0]=0; object.active=FALSE; rngCalls=cries=hearts=commands=0;
            profile.owner.chainRepositionJumpCount=code<<6; profile.owner.onReachAction=code<<6;
            draws[0]=0; draws[1]=99;
            CHECK(OverworldWildSpawns_TryStartChainPauseAction(&state,0,&profile,OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE,2,0));
            CHECK(commands==1 && cries==0 && hearts==0 && rngCalls==(code ? 2u:0u));
            CHECK(state.movementEmoteJumpsRemaining[0]==2 && state.movementEmoteShowBubbleEachJump[0]);
            if (code) CHECK(chances[0]==(25u<<(code-1)) && chances[1]==chances[0]);
            profile.owner=(OverworldWildBehaviorProfileData){0};
            object.active=FALSE; CHECK(OverworldWildSpawns_StartNextSpotEmoteStep(&state,0,&object));
            CHECK(hearts==(code ? 1u:0u) && cries==(code==3 ? 1u:0u));
            CHECK(!OverworldWildSpawns_StartNextSpotEmoteStep(&state,0,&object));
            CHECK(rngCalls==(code ? 2u:0u));
            object.active=FALSE; state.movementEmoteSteps[0]=OW_WILD_SPAWNER_SPOT_EMOTE_STEP_JUMP;
            CHECK(OverworldWildSpawns_StartNextSpotEmoteStep(&state,0,&object));
            CHECK(hearts==(code ? 2u:0u) && cries==(code==3 ? 2u:0u) && rngCalls==(code ? 2u:0u));
        }
    } else if (!strcmp(argv[1],"independent")) {
        profile.owner.chainRepositionJumpCount=profile.owner.onReachAction=2u<<6;
        draws[0]=99; draws[1]=0;
        CHECK(OverworldWildSpawns_TryStartChainPauseAction(&state,0,&profile,OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE,1,0));
        object.active=FALSE; CHECK(OverworldWildSpawns_StartNextSpotEmoteStep(&state,0,&object));
        CHECK(rngCalls==2 && cries==1 && hearts==0);
    } else if (!strcmp(argv[1],"guards")) {
        profile.owner.chainRepositionJumpCount=profile.owner.onReachAction=3u<<6;
        object.active=TRUE;
        CHECK(!OverworldWildSpawns_TryStartChainPauseAction(&state,0,&profile,OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE,2,0));
        CHECK(rngCalls==0 && cries==0 && hearts==0 && commands==0);
        object.active=FALSE;
        CHECK(OverworldWildSpawns_TryStartManualHopEmote(&state,0,&object,OW_WILD_HOP_PARAMETERS(0,0,1,FALSE)));
        object.active=FALSE; CHECK(OverworldWildSpawns_StartNextSpotEmoteStep(&state,0,&object));
        CHECK(rngCalls==0 && cries==0 && hearts==0 && !state.movementEmoteShowBubbleEachJump[0]);
    } else if (!strcmp(argv[1],"tired")) {
        state.movementSpotStates[0]=3; profile.tired.chainRepositionJumpCount=profile.tired.onReachAction=2u<<6;
        draws[0]=0; draws[1]=99;
        CHECK(OverworldWildSpawns_TryStartChainPauseAction(&state,0,&profile,OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE,1,0));
        CHECK(rngCalls==2 && chances[0]==50 && chances[1]==50 && state.movementEmoteEndStates[0]==3);
    } else if (!strcmp(argv[1],"mounted")) {
        u8 *action=(u8 *)(void *)&sOverworldMountState.reservedPriorFollowerPolicy;
        sOverworldMountState.snapshot.motionMode=OVERWORLD_MOUNT_MOTION_HOP;
        sOverworldMountState.walkEndState=OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;
        sOverworldMountState.snapshot.binding.species=74; sOverworldMountState.snapshot.binding.form=2;
        for (u8 code=0; code<4; code++) {
            sOverworldMountState.reservedPriorFollowerPolicy=OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE;
            sOverworldMountState.snapshot.profile.chainRepositionJumpCount=code<<6; sOverworldMountState.snapshot.profile.onReachAction=code<<6;
            draws[0]=0; draws[1]=99; rngCalls=cries=hearts=0;
            OverworldMount_TickChainHopEffects(); OverworldMount_TickChainHopEffects();
            CHECK(rngCalls==(code ? 2u:0u) && hearts==(code ? 1u:0u) && cries==(code==3 ? 1u:0u));
            CHECK((action[3]&12u)==12u);
            sOverworldMountState.snapshot.profile=(OverworldWildBehaviorProfileData){0};
            AcceptHopLatch(); CHECK((action[3]&12u)==4u);
            OverworldMount_TickChainHopEffects();
            CHECK(rngCalls==(code ? 2u:0u) && hearts==(code ? 2u:0u) && cries==(code==3 ? 2u:0u));
        }
    } else if (!strcmp(argv[1],"borrowed-guards")) {
        OverworldConditionNativeCall call = {.state=&state,.field=&field,.hopObject=&object,
            .hopCount=1,.hopOptions=0x3F,.hopOps=&sOverworldWildHopOps,
            .version=2,.size=sizeof(call),.operation=OVERWORLD_HOP_PRESENTATION_WILD_INIT};
        OverworldConditionNativeCall good=call; OverworldWildSpawnState before=state;
        for(unsigned bad=0; bad<12; bad++) {
            call=good; state=before; object.flags=0; OverworldHopPresentationOps ops=sOverworldWildHopOps;
            switch(bad) {
            case 0:call.version=1;break; case 1:call.size--;break;case 2:call.reserved=1;break;
            case 3:call.operation=OVERWORLD_HOP_PRESENTATION_PREFLIGHT;break;
            case 4:call.operation=7;break; case 5:call.slot=10;break;
            case 6:state.spawns[0].active=FALSE;break;
            case 7:state.spawns[0].object=&mountedObject;break;
            case 8:call.hopObject=NULL;break;case 9:call.hopCount=0;break;
            case 10:ops.choices=NULL;call.hopOps=&ops;break;
            case 11:state.movementSpotStates[0]=3;break;
            }
            OverworldWildSpawnState retained=state;
            CHECK(DispatchHop(&call)==OVERWORLD_BEHAVIOR_CONDITION_INVALID_ARGUMENT);
            CHECK(!memcmp(&state,&retained,sizeof(state)) && rngCalls==0 && commands==0);
        }
        state=before; object.flags=0; leaseCurrent=FALSE;
        CHECK(!OverworldWildSpawns_TryStartManualHopEmote(&state,0,&object,OW_WILD_HOP_PARAMETERS(0,0,1,0x3F)));
        CHECK(!memcmp(&state,&before,sizeof(state)) && rngCalls==0 && commands==0);
        CHECK(OverworldHopPresentation_Acquire(sOverworldMountState.fieldSystem)==NULL);
        leaseCurrent=TRUE;
        CHECK(OverworldHopPresentation_Acquire(&field)==&hostHopEntry);
        for(unsigned bad=0; bad<7; bad++) {
            u32 context=hostContext,magic=hostService.magic;u16 version=hostService.version,size=hostService.size;
            typeof(hostService.acquire) acquire=hostService.acquire;
            switch(bad) {case 0:hostGate=FALSE;break;case 1:hostService.magic^=1;break;
            case 2:hostService.version++;break;case 3:hostService.size--;break;
            case 4:hostService.acquire=NULL;break;case 5:hostContext^=1;break;
            case 6:hostContext^=1u<<16;break;}
            CHECK(OverworldHopPresentation_Acquire(&field)==NULL);
            hostGate=TRUE;hostService.magic=magic;hostService.version=version;hostService.size=size;
            hostService.acquire=acquire;hostContext=context;
        }
        CHECK(OverworldHopPresentation_Acquire(NULL)==NULL);
        CHECK(OverworldHopPresentation_Acquire((FieldSystem *)&object)==NULL);
    } else if (!strcmp(argv[1],"mounted-guards")) {
        sOverworldMountState.snapshot.profile.chainRepositionJumpCount=sOverworldMountState.snapshot.profile.onReachAction=3u<<6;
        OverworldMount_TickChainHopEffects(); CHECK(rngCalls==0);
        sOverworldMountState.snapshot.motionMode=OVERWORLD_MOUNT_MOTION_HOP;
        sOverworldMountState.walkEndState=OVERWORLD_MOUNT_WALK_END_CHAIN_HOP;
        OverworldMount_TickChainHopEffects(); CHECK(rngCalls==0);
        sOverworldMountState.reservedPriorFollowerPolicy=OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE;
        followerCurrent=FALSE; OverworldMount_TickChainHopEffects(); CHECK(rngCalls==0 && cries==0 && hearts==0);
    }
    return 0;
}
'''


class HopEffectsLifecycleTests(unittest.TestCase):
    def test_accepted_sequence_and_each_real_jump(self):
        source = hop_effects_source()
        for case in ("chooser", "wild", "independent", "guards", "tired", "mounted", "mounted-guards", "borrowed-guards"):
            with self.subTest(case=case):
                result = execute(source, case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_output_boundaries_remain_guarded(self):
        audit = module("hop_effect_boundaries", ROOT / "scripts/verify_overworld_role_controller.py")
        wild = audit.function_bodies(WILD.read_text())
        self.assertIn("&& !state->movementEmoteShowBubbleEachJump[slot]", wild["OverworldWildSpawns_TickSpotEmote"])
        mount = audit.function_bodies((ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text())
        update = mount["OverworldMount_UpdateCustomMotion"]
        self.assertLess(update.index("if (!OverworldMount_AcknowledgeSharedMotion("), update.index("OverworldMount_TickChainHopEffects()"))
        self.assertIn("OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);", update)
        begin = mount["OverworldMount_BeginSharedMotion"]
        self.assertLess(begin.index("OverworldHopPresentation_Acquire(sOverworldMountState.fieldSystem)"), begin.index("intent.version"))
        self.assertLess(begin.index("OVERWORLD_MOTION_DECISION_ACCEPTED"), begin.index("[3] &= ~8u"))
        self.assertLess(begin.index("motionIdentity = call.motionIdentity"), begin.index("[3] &= ~8u"))
        self.assertNotIn("HopPresentation(OVERWORLD_HOP_PRESENTATION_MOUNT_FINISH)", mount["OverworldMount_FinishCustomMotion"])


class ChainActionLifecycleTests(unittest.TestCase):
    def test_actual_hop_vector_preflight_preserves_walk_and_chain_receipts(self):
        source = hop_vector_preflight_source()
        for case in ("ordinary-invalid", "semantics"):
            with self.subTest(case=case):
                result = execute(source, case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
