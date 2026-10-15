#!/usr/bin/env python3
"""Check the production hit Crash transition with native-owner host stubs.

The shared Motion model is linked unchanged. This does not prove role rendering.
"""

from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def heavy_ownership_source() -> str:
    """Extract only the actual loop admission prefix and role-owned mask."""
    source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    marker = 'static BOOL __attribute__((optimize("Os", "inline-small-functions"))) OverworldWildSpawns_TickHeavyMovementSlots('
    start = source.index(marker)
    end = source.index("        OW_WILD_PERF_INC(", start)
    prefix = source[start:end].replace('__attribute__((optimize("Os", "inline-small-functions"))) ', '', 1)
    # The omitted body owns ordinary movement. This check ends at its admission
    # boundary and never copies the movement or Crash reducer.
    prefix += "    }\n    return movementFinishedThisFrame;\n}\n"
    start = source.index("    roleOwnedMask = OverworldWildSpawns_MountIsActive()")
    end = source.index("    frameWorkMask =", start)
    mask = ("static u16 TestHeavyMask(u32 frameWork) {\n"
            "    u16 roleOwnedMask, heavyWorkMask;\n" + source[start:end]
            + "    return heavyWorkMask;\n}\n")
    return prefix + mask


HEAVY_STUBS = r"""
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
#define OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT 16
typedef struct FieldSystem { u8 unused; } FieldSystem;
typedef struct OverworldWildSpawnState {
    u16 captureTargetMask, participantMask, crashMask;
} OverworldWildSpawnState;
static BOOL mounted;
static unsigned crashProbes[OW_WILD_MAX_SPAWNS], wildSettles[OW_WILD_MAX_SPAWNS];
static BOOL OverworldWildSpawns_MountIsActive(void) { return mounted; }
static u16 OverworldWildSpawns_GetThrowParticipantMask(OverworldWildSpawnState *state) {
    return state->participantMask;
}
static void OverworldWildSpawns_ClearThrowStateForSlot(OverworldWildSpawnState *state, int slot) {
    state->participantMask &= ~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
}
static BOOL OverworldWildSpawns_HasHitCrash(OverworldWildSpawnState *state, int slot) {
    ++crashProbes[slot];
    return (state->crashMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
}
static BOOL OverworldWildSpawns_ApplyQueuedCombat(
    OverworldWildSpawnState *state, FieldSystem *field, int slot) {
    assert(state != NULL && field != NULL);
    ++wildSettles[slot];
    return TRUE;
}
static void OverworldWildSpawns_ResetSlotMovementCommand(
    OverworldWildSpawnState *state, int slot, BOOL unused) {
    (void)unused;
    assert(state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS);
}
#define OverworldWildSpawns_ClearStagedHopTarget(state, slot) \
    OverworldWildSpawns_ResetSlotMovementCommand(state, slot, FALSE)
#define OverworldWildSpawns_ClearSpawnRunState(state, slot) \
    OverworldWildSpawns_ResetSlotMovementCommand(state, slot, FALSE)
"""


HEAVY_CASES = r"""
int main(void) {
    const u16 wildBit = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(0);
    const u16 followerBit = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(OW_WILD_FOLLOWER_SLOT);
    const u16 present = wildBit | followerBit;
    OverworldWildSpawnState state = {.crashMask = present};
    FieldSystem field = {0};
    u32 work = (u32)present << OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT;
    mounted = TRUE;
    assert(TestHeavyMask(work) == wildBit);
    assert(!OverworldWildSpawns_TickHeavyMovementSlots(
        &state, &field, present, 0, TestHeavyMask(work)));
    assert(crashProbes[0] == 1 && wildSettles[0] == 1); /* Normal Wild still runs. */
    assert(crashProbes[OW_WILD_FOLLOWER_SLOT] == 0);
    assert(wildSettles[OW_WILD_FOLLOWER_SLOT] == 0); /* Mount owns its SETTLE. */
    memset(crashProbes, 0, sizeof(crashProbes));
    memset(wildSettles, 0, sizeof(wildSettles));
    mounted = FALSE;
    assert(TestHeavyMask(work) == present);
    assert(!OverworldWildSpawns_TickHeavyMovementSlots(
        &state, &field, present, 0, TestHeavyMask(work)));
    assert(crashProbes[0] == 1 && wildSettles[0] == 1);
    assert(crashProbes[OW_WILD_FOLLOWER_SLOT] == 1);
    assert(wildSettles[OW_WILD_FOLLOWER_SLOT] == 1); /* Unmounted follower stays admitted. */
    puts("Wild Crash admission respects the production mounted ownership gate.");
    return 0;
}
"""


def block(source: str, marker: str, suffix: str = "") -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + suffix


def production_source() -> str:
    actor = (ROOT / "include/overworld_actor_system.h").read_text()
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    movement = (ROOT / "include/overworld_wild_movement.h").read_text()
    helper = (ROOT / "src/player_health_overlay/overworld_actor_hit_crash.c").read_text()
    policy = (ROOT / "src/player_health_overlay/overworld_walk_input_policy.c").read_text()
    runtime = (ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
    constants = "".join(re.findall(
        r"^#define (?:OW_WILD_WALK_DIRECTION_NONE|OVERWORLD_ACTOR_WALK_(?:POLICY_VERSION|HIT_CRASH_\w+|PENDING_\w+|STEP_SKID|STEP_CLEAR_PRESENTATION))[^\n]*\n",
        movement, re.MULTILINE))
    declarations = "\n".join([
        block(actor, "typedef enum OverworldActorMotionKind", " OverworldActorMotionKind;"),
        block(actor, "typedef enum OverworldActorStreamState", " OverworldActorStreamState;"),
        block(actor, "typedef enum OverworldActorWorldEffect", " OverworldActorWorldEffect;"),
        block(actor, "typedef struct OverworldActorHandle", " OverworldActorHandle;"),
        block(actor, "typedef struct OverworldActorStateSnapshot", " OverworldActorStateSnapshot;"),
        block(movement, "typedef struct OverworldWildWalkMomentumState", " OverworldWildWalkMomentumState;"),
        block(movement, "typedef enum OverworldActorWalkPolicyOperation", " OverworldActorWalkPolicyOperation;"),
        block(movement, "typedef enum OverworldActorWalkPolicyDecision", " OverworldActorWalkPolicyDecision;"),
        block(internal, "struct OverworldActorPolicyState {", ";"),
        "typedef struct OverworldActorPolicyState OverworldActorPolicyState;",
        block(internal, "typedef struct OverworldActorRuntimeSlot", " OverworldActorRuntimeSlot;"),
    ])
    call = block(movement, "typedef struct OverworldActorWalkPolicyCall", " OverworldActorWalkPolicyCall;")
    # The lane is unused here. Keep its ARM9 32-bit ABI on a 64-bit host.
    call = re.sub(r"    union \{.*?    \};", "    u32 lane;", call, flags=re.DOTALL)
    outcome = "\n".join([
        "void " + block(policy, "OverworldActorWalkPolicy_ResetState("),
        "void " + block(policy, "OverworldActorWalkPolicy_Crash("),
    ])
    start = runtime.index("    case OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH:")
    end = runtime.index("    case OVERWORLD_ACTOR_WALK_POLICY_INSPECT:", start)
    case = runtime[start:end]
    reducer = ("static BOOL TestReduce(OverworldActorPolicyState *policy, "
               "OverworldActorStateSnapshot *actor, OverworldActorWalkPolicyCall *call) {\n"
               "switch (call->operation) {\n" + case + "default: return FALSE;\n}}\n")
    function = "BOOL " + block(helper, "OverworldActorHitCrash_Apply(")
    assert not any(name in function for name in (
        "OverworldMotion_Cancel(", "OverworldMotion_AcknowledgeCommit(",
        "EngineBoundary(", "ServiceEngineBoundary("))
    return (constants + declarations + "\n" + call
            + "\n"
            + outcome + TRACE + reducer + OWNER + function)


TRACE = r"""
static OverworldActorRuntimeSlot *watched;
static unsigned crashTraces;
static BOOL OverworldActorWalkPolicy_PublishEffect(
    OverworldActorStateSnapshot *actor, u32 effect, u32 sequence) {
    assert(actor == &watched->snapshot);
    assert(effect == OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    assert(sequence == 51);
    assert(watched->motion.phase != OVERWORLD_MOTION_PHASE_SUSPENDED);
    ++crashTraces;
    return TRUE;
}
"""

OWNER = r"""
static struct {
    BOOL (*reduceWalk)(OverworldActorPolicyState *,
                      OverworldActorStateSnapshot *,
                      OverworldActorWalkPolicyCall *);
} owner = { TestReduce };
#define OVERWORLD_ACTOR_WALK_POLICY_OWNER_ENTRY (&owner)
"""

CASES = r"""
static OverworldActorRuntimeSlot slot;
static OverworldActorWalkPolicyCall call;
static void receipt(u16 id, u16 epoch) {
    memcpy(call.reserved, &id, 2);
    memcpy(call.reserved + 2, &epoch, 2);
}
static u16 saved_id(void) {
    u16 id;
    memcpy(&id, call.reserved, 2);
    return id;
}
static void reset_fixture(void) {
    memset(&slot, 0, sizeof(slot));
    memset(&call, 0, sizeof(call));
    watched = &slot;
    crashTraces = 0;
    slot.snapshot.active = 1;
    slot.snapshot.handle.slot = 7;
    slot.snapshot.handle.fieldEpoch = 3;
    slot.snapshot.commitSequence = 51;
    slot.snapshot.inputOwnership = 2;
    slot.snapshot.lastCancelReason = 9;
    slot.snapshot.originX = -5;
    slot.snapshot.originY = 6;
    slot.snapshot.logicalX = -5;
    slot.snapshot.logicalY = 6;
    slot.snapshot.renderX = -4;
    slot.snapshot.renderY = 6;
    slot.snapshot.targetX = -3;
    slot.snapshot.targetY = 6;
    slot.policy.walkMomentum.baseSpeed = 20;
    slot.policy.walkMomentum.spotState = 1;
    slot.policy.walkMomentum.speed = 2;
    slot.policy.bufferedDirection = 2;
    call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call.size = sizeof(call);
    call.actorSlot = 7;
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_HIT_CRASH;
    receipt(0, 3);
}
static void active_skid(void) {
    reset_fixture();
    slot.motion.phase = OVERWORLD_MOTION_PHASE_MOVING;
    slot.motion.plan.kind = OVERWORLD_MOTION_KIND_SKID;
    slot.motion.plan.reservationId = 11;
    slot.motion.plan.fieldEpoch = 3;
    slot.motion.elapsed = 4;
    slot.motion.plan.duration = 12;
    slot.snapshot.motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
    slot.snapshot.reservationId = 11;
    slot.snapshot.motionKind = OVERWORLD_ACTOR_MOTION_SKID;
    slot.policy.pendingFirstPathAdvance = 1;
    slot.policy.pendingLastPathAdvance = 2;
    slot.snapshot.reserved1 = 255;
}
#define REJECT_ACTIVE(change) do { \
    active_skid(); change; \
    assert(!OverworldActorHitCrash_Apply(&slot, &call, 3)); \
    assert(crashTraces == 0); \
} while (0)
static void check_crash(void) {
    assert(call.decision == OVERWORLD_ACTOR_WALK_POLICY_CONSUMED);
    assert(call.effect == OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    assert(call.stepFlags & OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION);
    assert(crashTraces == 1);
    assert(slot.policy.walkMomentum.baseSpeed == 20);
    assert(slot.policy.walkMomentum.speed == 20);
    assert(slot.policy.walkMomentum.spotState == 1);
    assert(!slot.policy.pendingSkid && !slot.policy.stopPending);
    assert(!slot.policy.walkMomentum.skidRemaining);
    assert(slot.snapshot.commitSequence == 51);
    assert(slot.snapshot.inputOwnership == 2);
    assert(slot.snapshot.lastCancelReason == 9);
}
int main(void) {
    _Static_assert(sizeof(OverworldActorWalkPolicyCall) == 28, "call ABI");
    _Static_assert(sizeof(OverworldActorRuntimeSlot) == 176, "slot ABI");
    _Static_assert(sizeof(OverworldActorPolicyState) == 36, "policy ABI");
    REJECT_ACTIVE(call.version++);
    REJECT_ACTIVE(call.size--);
    REJECT_ACTIVE(call.actorSlot = 6);
    REJECT_ACTIVE(call.operation = OVERWORLD_ACTOR_WALK_POLICY_INPUT);
    REJECT_ACTIVE(slot.snapshot.active = 0);
    REJECT_ACTIVE(receipt(0, 4));
    REJECT_ACTIVE(slot.snapshot.handle.fieldEpoch = 4);
    REJECT_ACTIVE(slot.snapshot.reservationId = 0);
    REJECT_ACTIVE(slot.motion.plan.reservationId = 12);
    REJECT_ACTIVE(slot.motion.plan.fieldEpoch = 4);
    REJECT_ACTIVE(slot.motion.commitPublished = 1);
    REJECT_ACTIVE(slot.motion.plan.kind = OVERWORLD_MOTION_KIND_HOP);
    REJECT_ACTIVE(call.flags = 1);

    active_skid();
    assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
    check_crash();
    assert(saved_id() == 11);
    assert(slot.motion.phase == OVERWORLD_MOTION_PHASE_SUSPENDED);
    assert(slot.snapshot.motionPhase == OVERWORLD_MOTION_PHASE_SUSPENDED);
    assert(slot.motion.phaseBeforeSuspend == OVERWORLD_MOTION_PHASE_MOVING);
    OverworldMotionSample sample;
    assert(OverworldMotion_Tick(&slot.motion, 3, &sample) == 0);
    assert(slot.motion.elapsed == 4);
    assert(OverworldMotion_AcknowledgeCommit(&slot.motion, 3)
        == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE);

    call.flags = OVERWORLD_ACTOR_WALK_HIT_CRASH_SETTLE;
    receipt(12, 3);
    assert(!OverworldActorHitCrash_Apply(&slot, &call, 3));
    receipt(11, 4);
    assert(!OverworldActorHitCrash_Apply(&slot, &call, 3));
    receipt(11, 3);
    assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
    assert(crashTraces == 1);
    assert(slot.motion.phase == OVERWORLD_MOTION_PHASE_IDLE);
    assert(slot.snapshot.motionPhase == OVERWORLD_MOTION_PHASE_IDLE);
    assert(slot.snapshot.logicalX == -5 && slot.snapshot.logicalY == 6);
    assert(slot.snapshot.renderX == -5 && slot.snapshot.renderY == 6);
    assert(slot.snapshot.targetX == -5 && slot.snapshot.targetY == 6);
    assert(!slot.snapshot.reservationId && !slot.snapshot.reserved1);
    assert(!slot.policy.pendingFirstPathAdvance && !slot.policy.pendingLastPathAdvance);
    assert(slot.snapshot.commitSequence == 51);
    assert(slot.snapshot.inputOwnership == 2);
    assert(slot.snapshot.lastCancelReason == 9);
    assert(!OverworldActorHitCrash_Apply(&slot, &call, 3));

    /* Due skids crash synchronously at idle; they get no fake suspension. */
    for (unsigned due = 0; due < 4; ++due) {
        reset_fixture();
        if (due == 0) slot.policy.pendingSkid = 1;
        if (due == 1) slot.policy.walkMomentum.skidRemaining = 2;
        if (due == 2) slot.policy.stopPending = 1;
        if (due == 3) {
            slot.policy.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL;
            call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_SKID;
        }
        assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
        check_crash();
        assert(saved_id() == 0 && slot.motion.phase == OVERWORLD_MOTION_PHASE_IDLE);
        call.flags = OVERWORLD_ACTOR_WALK_HIT_CRASH_SETTLE;
        assert(!OverworldActorHitCrash_Apply(&slot, &call, 3));
    }
    /* A fast Walk and turn buffer alone must not turn into a hit Crash. */
    reset_fixture();
    assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
    assert(crashTraces == 0 && call.effect == OVERWORLD_ACTOR_WORLD_EFFECT_NONE);
    active_skid();
    slot.motion.plan.kind = OVERWORLD_MOTION_KIND_WALK;
    assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
    assert(crashTraces == 0 && slot.motion.phase == OVERWORLD_MOTION_PHASE_MOVING);
    slot.policy.stopPending = 1;
    assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
    check_crash();
    /* A due skid in the previous tile's authored pause crashes at that
     * committed tile. The old pause ends without a second commit or END. */
    reset_fixture();
    slot.motion.phase = OVERWORLD_MOTION_PHASE_SETTLING;
    slot.motion.commitPublished = 1;
    slot.motion.plan.kind = OVERWORLD_MOTION_KIND_WALK;
    slot.motion.plan.fieldEpoch = 3;
    slot.motion.plan.targetX = -5;
    slot.motion.plan.targetY = 6;
    slot.motion.settleRemaining = 7;
    slot.policy.walkMomentum.skidRemaining = 2;
    assert(OverworldActorHitCrash_Apply(&slot, &call, 3));
    check_crash();
    assert(saved_id() == 0);
    assert(slot.motion.phase == OVERWORLD_MOTION_PHASE_IDLE);
    assert(slot.motion.settleRemaining == 0);
    assert(slot.snapshot.logicalX == -5 && slot.snapshot.logicalY == 6);
    assert(slot.snapshot.renderX == -5 && slot.snapshot.renderY == 6);
    assert(OverworldMotion_Tick(&slot.motion, 3, &sample) == 0);
    assert(OverworldMotion_AcknowledgeCommit(&slot.motion, 3)
        == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE);
    call.flags = OVERWORLD_ACTOR_WALK_HIT_CRASH_SETTLE;
    assert(!OverworldActorHitCrash_Apply(&slot, &call, 3));
    /* Uncommitted settling state, a canceled move, or an idle reservation
     * cannot use the synchronous no-motion path. */
    REJECT_ACTIVE(slot.motion.phase = OVERWORLD_MOTION_PHASE_SETTLING);
    REJECT_ACTIVE(slot.motion.phase = OVERWORLD_MOTION_PHASE_CANCELED);
    reset_fixture();
    slot.snapshot.reservationId = 11;
    slot.policy.stopPending = 1;
    assert(!OverworldActorHitCrash_Apply(&slot, &call, 3));
    puts("Hit Crash is immediate, releases the old move once, and rejects stale receipts.");
    return 0;
}
"""


def queued_combat_source() -> str:
    source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    files = [source, (ROOT / "include/overworld_combat.h").read_text(),
             (ROOT / "include/overworld_wild_helper.h").read_text(),
             (ROOT / "include/overworld_wild_runtime.h").read_text(),
             (ROOT / "include/overworld_wild_behavior_data.h").read_text()]
    names = ("OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG", "OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG",
             "OW_WILD_HELPER_THROW_TARGET_DECODE", "OW_WILD_HELPER_THROW_TARGET_SLOT_MASK",
             "OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND", "OW_WILD_SPAWNER_FX32_ONE",
             "OW_WILD_SPAWNER_TILE_FX32", "OW_WILD_SPAWNER_TILE_CENTER_FX32",
             "OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32", "OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FRAMES",
             "OW_WILD_SURFACE_ID_NATIVE_GROUND", "OW_WILD_RUNTIME_MOTION_REQUEST_FORCED",
             "OVERWORLD_COMBAT_NONE", "OVERWORLD_COMBAT_KNOCKBACK", "OVERWORLD_COMBAT_FAINTED",
             "OVERWORLD_COMBAT_CRASH_SETTLE", "OVERWORLD_COMBAT_CRASH_PLAYING")
    constants = ""
    for name in names:
        for text in files:
            lines = text.splitlines(keepends=True)
            index = next((i for i, line in enumerate(lines)
                          if re.match(r"^#define " + name + r"(?:\s|\()", line)), None)
            if index is not None:
                while True:
                    line = lines[index]
                    constants += line
                    if not line.rstrip().endswith("\\"):
                        break
                    index += 1
                break
        else:
            raise AssertionError(name)
    controls = (ROOT / "include/overworld_wild_spawns_internal.h").read_text()
    bindings = (ROOT / "include/overworld_target_bindings.h").read_text()
    declarations = block(controls, "typedef enum OverworldWildActorControlMode", " OverworldWildActorControlMode;")
    declarations += block(bindings, "typedef enum OverworldTargetBindingName", " OverworldTargetBindingName;")
    function = "static void " + block(source, "OverworldWildSpawns_PrepareCarrierHit(\n    OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot)\n{")
    function += "\nstatic BOOL " + block(source, "OverworldWildSpawns_ApplyQueuedCombat(\n    OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot)\n{")
    return constants + declarations + QUEUED_STUBS + function + QUEUED_CASES


QUEUED_STUBS = r"""
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
typedef struct FieldSystem { int unused; } FieldSystem;
typedef struct LocalMapObject { int xCurr, yCurr, curFacing; u32 posVec[3]; BOOL single; } LocalMapObject;
typedef struct VecFx32 { s32 x, y, z; } VecFx32;
typedef struct OverworldActorPolicyView { u8 motionPhase; } OverworldActorPolicyView;
typedef struct OverworldWildBehaviorProfile { u8 unused; } OverworldWildBehaviorProfile;
typedef struct OverworldWildSurfaceHit { u16 surfaceId; } OverworldWildSurfaceHit;
typedef struct OverworldWildSpawn { LocalMapObject *object; BOOL current; } OverworldWildSpawn;
typedef struct OverworldWildOverlayRuntimeState {
    struct { u8 targets[10]; u16 targetMask, carrierMask; } throwState;
    u32 interest[10], cargo[10];
    int movementMotionIdentities[10]; u16 movementNativeHeldMask;
    int movementCustomJumpStartX[10], movementCustomJumpStartY[10], movementCustomJumpStartBaseY[10];
    int movementCustomJumpTargetX[10], movementCustomJumpTargetY[10], movementCustomJumpTargetBaseY[10];
    int movementCustomJumpArcHeightsQ4[10], movementCustomJumpPrepActive[10];
} OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[10]; OverworldWildOverlayRuntimeState *runtime;
    int movementActorControlModes[10], movementCrashShakeTimers[10], movementSpotStates[10];
    int movementCooldowns[10], movementPendingDirections[10], movementPendingDistances[10], movementStagedHopDistances[10];
    u16 movementInProgressMask;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) ((state)->runtime)
static OverworldWildSpawnState state;
static OverworldWildOverlayRuntimeState runtime;
static LocalMapObject objects[10]; static FieldSystem field;
static OverworldMotionPlan prepared;
static BOOL ready, inspectOK, bindingCurrent;
static int phase, queuedWork, nextWork, requestDecision;
static unsigned preparedCalls, acknowledgements, clears, releases, removals, requests, jumps, commands;
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f, OverworldWildSpawn *s) {
    assert(f == &field); return s->current;
}
static u8 Prepare(const OverworldWildSpawnState *s, u8 slot, OverworldMotionPlan *p) {
    assert(s == &state && slot == 0); *p = prepared;
    return ++preparedCalls == 1 ? queuedWork : nextWork;
}
static void Acknowledge(const OverworldWildSpawnState *s, u8 slot) {
    assert(s == &state && slot == 0); ++acknowledgements; queuedWork = OVERWORLD_COMBAT_NONE;
}
static struct { u8 (*prepare)(const OverworldWildSpawnState *,u8,OverworldMotionPlan *);
    void (*acknowledge)(const OverworldWildSpawnState *,u8); } combat = {Prepare,Acknowledge};
#define OVERWORLD_COMBAT_ENTRY (&combat)
typedef struct OverworldReturnMoveWildContext {
    OverworldWildSpawnState *state; FieldSystem *field; const void *ops; int slot;
} OverworldReturnMoveWildContext;
static int sOverworldWildReturnOps;
typedef struct OverworldQueryCodeAddonEntry {
    u8 (*returnCombatWork)(const OverworldReturnMoveWildContext *, OverworldMotionPlan *);
} OverworldQueryCodeAddonEntry;
static u8 ReturnCombatWork(const OverworldReturnMoveWildContext *context, OverworldMotionPlan *plan) {
    assert(context->state == &state && context->field == &field
        && context->ops == &sOverworldWildReturnOps && context->slot == 0);
    if (!ready || !state.spawns[0].current) return OVERWORLD_COMBAT_NONE;
    return OVERWORLD_COMBAT_ENTRY->prepare(context->state, (u8)context->slot, plan);
}
static const OverworldQueryCodeAddonEntry queryAddon = {ReturnCombatWork};
static const OverworldQueryCodeAddonEntry *OverworldWildSpawns_QueryAddon(FieldSystem *f, void *unused) {
    assert(f == &field && unused == NULL); return &queryAddon;
}
static void OverworldWildSpawns_ClearPendingNotices(OverworldWildSpawnState *s,int slot) {
    assert(s == &state && slot == 0);
}
static void OverworldWildSpawns_ClearThrowStateForSlot(OverworldWildSpawnState *s, int slot) {
    assert(s == &state && slot == 0); ++clears;
    runtime.throwState.targets[0] = 0; runtime.throwState.targetMask = runtime.throwState.carrierMask = 0;
    runtime.interest[0] = runtime.cargo[0] = 0;
}
static void OverworldWildSpawns_RemoveEncounter(OverworldWildSpawnState *s, FieldSystem *f, int slot) {
    assert(f == &field); ++removals; OverworldWildSpawns_ClearThrowStateForSlot(s,slot); s->spawns[slot].current = FALSE;
}
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *p) {
    assert(slot == 0); p->motionPhase = phase; return inspectOK;
}
static const LocalMapObject * __attribute__((unused)) OverworldWildSpawns_GetThrowBindingBody(
    OverworldWildSpawnState *s, int slot, u8 name, int x, int y) {
    assert(s == &state && slot == 0 && name == OVERWORLD_TARGET_BINDING_CARGO);
    assert(x == objects[1].xCurr && y == objects[1].yCurr);
    return bindingCurrent ? &objects[1] : &objects[2];
}
static void CheckState(OverworldWildSpawnState *s, int slot) { assert(s == &state && slot == 0); }
static void OverworldWildSpawns_ReleaseHeldActorControl(OverworldWildSpawnState *s, int slot) {
    CheckState(s,slot); ++releases; s->movementActorControlModes[slot] = OW_WILD_ACTOR_CONTROL_AUTONOMOUS;
}
static void OverworldWildSpawns_ClearStagedHopTargetLocal(OverworldWildSpawnState *s,int slot) { CheckState(s,slot); }
static void OverworldWildSpawns_ClearSpawnRunState(OverworldWildSpawnState *s,int slot) { CheckState(s,slot); }
static void OverworldWildSpawns_ClearWalkMovementState(OverworldWildSpawnState *s,int slot,LocalMapObject *o) {
    CheckState(s,slot); assert(o == &objects[0]);
    /* Clear aim WINDUP before these saved endpoint fields are replaced. */
    assert(!(runtime.throwState.targets[0] & OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG));
    assert(runtime.movementCustomJumpTargetX[0] == 90);
}
static void OverworldWildSpawns_FinishPresentationCommand(LocalMapObject *o) { assert(o == &objects[0]); }
static void OverworldWildSpawns_SetObjectLandingTile(FieldSystem *f,LocalMapObject *o,int x,int y) {
    assert(f == &field && o == &objects[0]); o->xCurr=x; o->yCurr=y;
}
static void MapObject_SetPositionFromVectorAndDirection(LocalMapObject *o,VecFx32 *p,int d) { assert(o && p && d >= 0); }
static void MapObject_ClearHeldMovement(LocalMapObject *o) { assert(o); }
static void MapObject_ClearSingleMovementActive(LocalMapObject *o) { o->single = FALSE; }
static void OverworldWildSpawns_ClearMovementSlotInProgress(OverworldWildSpawnState *s,int slot) { s->movementInProgressMask &= ~(1u<<slot); }
static void OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(OverworldWildSpawnState *s,int slot,OverworldWildBehaviorProfile *p,void *unused) { CheckState(s,slot); assert(p && !unused); }
static void OverworldWildSpawns_PlayMovementCrashFeedback(OverworldWildBehaviorProfile *p,int spot) { assert(p); (void)spot; }
static void OverworldWildSpawns_StartMovementCrashShake(OverworldWildSpawnState *s,int slot,LocalMapObject *o,int frames) { CheckState(s,slot); assert(o && frames > 0); }
static BOOL OverworldWildSpawns_IsMovementSlotInProgress(OverworldWildSpawnState *s,int slot) { return !!(s->movementInProgressMask & (1u<<slot)); }
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *o) { return o->single; }
static BOOL OverworldWildSpawns_QuerySurface(FieldSystem *f,int x,int y,OverworldWildSurfaceHit *surface) {
    assert(f == &field && x == prepared.targetX && y == prepared.targetY); surface->surfaceId=9; return TRUE;
}
static int Request(OverworldWildSpawnState *s,int slot,void *lane,int kind,int visibility,int arc,int facing,int duration,int pause,int flags,int surface) {
    CheckState(s,slot); ++requests;
    assert(!lane && kind == (OVERWORLD_MOTION_KIND_HOP | OW_WILD_RUNTIME_MOTION_REQUEST_FORCED));
    assert(visibility == OVERWORLD_MOTION_VISIBILITY_VISIBLE && arc == prepared.arcHeightQ4);
    assert(facing == objects[0].curFacing && duration == prepared.duration && !pause && !flags && surface == 9);
    return requestDecision;
}
static struct { int (*requestMotion)(OverworldWildSpawnState *,int,void *,int,int,int,int,int,int,int,int); } motion = {Request};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&motion)
static void OverworldWildSpawns_StartCustomJump(OverworldWildSpawnState *s,int slot,int x,int y,int tx,int ty,int base,int targetBase) {
    CheckState(s,slot); ++jumps; assert(x==2 && y==3 && tx==prepared.targetX && ty==prepared.targetY && base==65536 && targetBase==prepared.targetBaseY);
}
static void OverworldWildSpawns_SetPreviousTile(OverworldWildSpawnState *s,int slot,int x,int y) { CheckState(s,slot); assert(x==2 && y==3); }
static void MapObject_StartMovementCommand(LocalMapObject *o,int cmd) { assert(o==&objects[0] && cmd==OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND); ++commands; }
static void MapObject_SetSingleMovementActive(LocalMapObject *o) { o->single=TRUE; }
static void OverworldWildSpawns_SetMovementSlotInProgress(OverworldWildSpawnState *s,int slot) { s->movementInProgressMask |= 1u<<slot; }
"""


QUEUED_CASES = r"""
static void Reset(void) {
    memset(&state,0,sizeof(state)); memset(&runtime,0,sizeof(runtime)); memset(objects,0,sizeof(objects));
    state.runtime=&runtime; for (int i=0;i<10;i++) state.spawns[i]=(OverworldWildSpawn){&objects[i],TRUE};
    objects[0].xCurr=2; objects[0].yCurr=3; objects[0].posVec[1]=65536; objects[0].curFacing=1;
    objects[1].xCurr=2; objects[1].yCurr=4; state.movementActorControlModes[1]=OW_WILD_ACTOR_CONTROL_HELD;
    runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG|2;
    runtime.throwState.carrierMask=1; runtime.throwState.targetMask=2;
    runtime.interest[0]=123; runtime.cargo[0]=456; runtime.movementCustomJumpTargetX[0]=90;
    prepared=(OverworldMotionPlan){.version=OVERWORLD_MOTION_MODEL_VERSION,.kind=OVERWORLD_MOTION_KIND_HOP,
        .duration=8,.targetX=2,.targetY=6,.targetBaseY=65536,.direction=1,.distance=3,.arcHeightQ4=48};
    ready=inspectOK=bindingCurrent=TRUE; phase=OVERWORLD_MOTION_PHASE_IDLE;
    queuedWork=nextWork=OVERWORLD_COMBAT_KNOCKBACK; requestDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;
    preparedCalls=acknowledgements=clears=releases=removals=requests=jumps=commands=0;
}
static void Retained(void) {
    assert(!clears && !releases && !removals && runtime.interest[0]==123 && runtime.cargo[0]==456);
    assert(runtime.throwState.targets[0]==(OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG|2));
    assert(runtime.throwState.carrierMask==1 && runtime.throwState.targetMask==2);
}
int main(void) {
    for (int windup=0;windup<2;windup++) {
        Reset(); if(windup) runtime.throwState.targets[0] |= OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG;
        assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0)); Retained();
        assert(requests==1 && jumps==1 && commands==1 && acknowledgements==1);
        assert(objects[0].single && state.movementInProgressMask==1 && queuedWork==OVERWORLD_COMBAT_NONE);
    }
    for (int invalid=0;invalid<7;invalid++) {
        Reset();
        if(invalid==0) runtime.throwState.targets[0]=2;
        if(invalid==1) runtime.throwState.carrierMask=0;
        if(invalid==2) runtime.throwState.targets[0]=OW_WILD_HELPER_THROW_TARGET_CARRIED_FLAG;
        if(invalid==3) runtime.throwState.targetMask=0;
        if(invalid==4) state.movementActorControlModes[1]=OW_WILD_ACTOR_CONTROL_AUTONOMOUS;
        if(invalid==5) state.spawns[1].current=FALSE;
        if(invalid==6) bindingCurrent=FALSE;
        assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0));
        assert(clears==1 && !runtime.cargo[0] && !runtime.interest[0] && !runtime.throwState.carrierMask);
        assert(requests==1 && jumps==1 && acknowledgements==1);
    }
    Reset(); state.movementActorControlModes[0]=OW_WILD_ACTOR_CONTROL_HELD;
    assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0));
    assert(clears==2 && releases==1 && preparedCalls==2 && jumps==1 && acknowledgements==1);
    Reset(); state.movementActorControlModes[0]=OW_WILD_ACTOR_CONTROL_HELD; nextWork=OVERWORLD_COMBAT_NONE;
    assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0));
    assert(clears==1 && releases==1 && preparedCalls==2 && !requests && !acknowledgements);
    Reset(); queuedWork=OVERWORLD_COMBAT_FAINTED;
    assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0));
    assert(removals==1 && clears==1 && !requests && !acknowledgements);
    for(int busy=0;busy<4;busy++) {
        Reset(); if(busy==0) inspectOK=FALSE;
        if(busy==1) phase=OVERWORLD_MOTION_PHASE_MOVING;
        if(busy==2) state.movementInProgressMask=1;
        if(busy==3) objects[0].single=TRUE;
        assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0)); Retained();
        assert(!requests && !acknowledgements && queuedWork==OVERWORLD_COMBAT_KNOCKBACK);
    }
    Reset(); runtime.throwState.targets[0] |= OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG;
    requestDecision=OVERWORLD_MOTION_DECISION_BLOCKED;
    assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0)); Retained();
    assert(requests==1 && !jumps && !commands && !acknowledgements && queuedWork==OVERWORLD_COMBAT_KNOCKBACK);
    runtime.movementCustomJumpTargetX[0]=90; requestDecision=OVERWORLD_MOTION_DECISION_ACCEPTED;
    assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0)); Retained();
    assert(requests==2 && jumps==1 && acknowledgements==1);
    /* A blocked hit has no legal Hop, but must still retire Trigger-only Throw. */
    Reset(); runtime.throwState.targets[0]=0; runtime.throwState.carrierMask=0;
    runtime.throwState.targetMask=0; runtime.cargo[0]=0; prepared.version=0;
    assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0));
    assert(clears==1 && runtime.interest[0]==0 && !requests && !jumps
        && acknowledgements==1 && queuedWork==OVERWORLD_COMBAT_NONE);
    for(int idle=0;idle<3;idle++) {
        Reset(); if(idle==0) ready=FALSE; if(idle==1) state.spawns[0].current=FALSE;
        if(idle==2) queuedWork=OVERWORLD_COMBAT_NONE;
        assert(!OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0)); Retained(); assert(!requests && !acknowledgements);
    }
    puts("Queued combat keeps valid carried Cargo, clears stale/held/faint relations, and preserves busy/rejected work.");
    return 0;
}
"""


def queued_walk_completion_source() -> str:
    """Real completion admission and current FinishReturnMove call seam."""
    wild = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    finished = block(wild, "OverworldWildSpawns_HandleFinishedMovementCommand(OverworldWildSpawnState *state, int slot)\n{")
    terminal = finished.index("    if (OverworldWildSpawns_FinishReturnMove(state, slot, &profile, &primitives,\n            OVERWORLD_RETURN_MOVE_WALK_TERMINAL")
    stop = finished.index("    if (combatOwnsCompletion) {\n        return;\n    }", terminal)
    end = finished.index("    if (pendingDistanceDespawn) {", stop)
    # Keep all production gates through terminal Walk and combat's return.
    # The rest is new ordinary intent, which must remain unreachable here.
    finished = "static void " + finished[:end] + "\n    (void)lane; ordinaryIntents++;\nrequest_distance_despawn:\n    ordinaryIntents++;\n}\n"
    finish_return = "static BOOL " + block(wild,
        "OverworldWildSpawns_FinishReturnMove(OverworldWildSpawnState *state, int slot,\n    OverworldWildBehaviorProfile *profile, OverworldWildBehaviorPrimitives *primitives,\n    u8 flags)\n{")
    queued = queued_combat_source().split(QUEUED_CASES, 1)[0]
    queued = queued.replace("typedef struct OverworldActorPolicyView { u8 motionPhase; }",
        "typedef struct OverworldActorPolicyView { u8 motionPhase, chainStepsRemaining, chainPauseTicks; }")
    queued = queued.replace("LocalMapObject *object; BOOL current;", "LocalMapObject *object; BOOL current, active;")
    queued = queued.replace("int movementMotionIdentities[10];", "int movementCustomMotionModes[10], movementCustomJumpActive[10]; struct { u16 distanceDespawnPendingMask; } spawnPresentations; struct { u8 phase; } returnMoves[10]; int movementMotionIdentities[10];")
    queued = queued.replace("OverworldWildSpawn spawns[10];", "FieldSystem *movementFieldSystem; OverworldWildSpawn spawns[10];")
    queued = queued.replace("static u8 Prepare(", "static unsigned terminalCommits, ordinaryIntents; static u8 completionChain; static BOOL swapObject;\nstatic u8 Prepare(")
    queued = queued.replace("u8 (*returnCombatWork)(const OverworldReturnMoveWildContext *, OverworldMotionPlan *);",
        "u8 (*returnCombatWork)(const OverworldReturnMoveWildContext *, OverworldMotionPlan *);\n    BOOL (*returnFinish)(const OverworldReturnMoveWildContext *, void *, void *, u8);")
    queued = queued.replace("static const OverworldQueryCodeAddonEntry queryAddon = {ReturnCombatWork};",
        "static BOOL ReturnFinish(const OverworldReturnMoveWildContext *, void *, void *, u8);\nstatic const OverworldQueryCodeAddonEntry queryAddon = {ReturnCombatWork,ReturnFinish};")
    queued = queued.replace("*p = prepared;", "*p = prepared; if (swapObject) ((OverworldWildSpawnState *)s)->spawns[slot].object=&objects[2];")
    queued = queued.replace("s->spawns[slot].current = FALSE;", "s->spawns[slot].current = FALSE; s->spawns[slot].active=FALSE;")
    queued = queued.replace("p->motionPhase = phase;", "p->motionPhase = phase; p->chainStepsRemaining=completionChain; p->chainPauseTicks=0;")
    queued = queued.replace("assert(p && !unused);", "assert(p); (void)unused;")
    queued = queued.replace("++requests;", "++requests; assert(terminalCommits==1 && phase==OVERWORLD_MOTION_PHASE_IDLE);")
    reset = QUEUED_CASES[:QUEUED_CASES.index("static void Retained(void)")]
    reset = reset.replace("{&objects[i],TRUE}", "{&objects[i],TRUE,TRUE}")
    return queued + COMPLETION_STUBS + finish_return + "\n" + finished + reset + COMPLETION_CASES


COMPLETION_STUBS = r"""
#define OW_WILD_CUSTOM_MOTION_WALK 1
#define OW_WILD_RETURN_NONE 0
#define OVERWORLD_RETURN_MOVE_BEFORE_WALK 1
#define OVERWORLD_RETURN_MOVE_AFTER_WALK 2
#define OVERWORLD_RETURN_MOVE_COMBAT_OWNED 4
#define OVERWORLD_RETURN_MOVE_DESPAWN 8
#define OVERWORLD_RETURN_MOVE_WALK_TERMINAL 16
#define OVERWORLD_RETURN_MOVE_STOP_AFTER_COMMIT 32
#define OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING 0x80
#define OW_WILD_CHAIN_COMPLETE 2
#define OW_WILD_CHAIN_ABORT 3
#define OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT 14
#define OVERWORLD_ACTOR_WORLD_EFFECT_CRASH 3
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND 0x4A
#define PLAYER_HEALTH_MOTION_LAND 0
#define PLAYER_HEALTH_EVENT_CODE(slot,event) 0
#define BIT_VANISH 0
#define MAPOBJECTFLAG_UNK18 0
typedef struct { u8 unused; } OverworldWildBehaviorProfileData;
typedef struct { u8 unused; } OverworldWildBehaviorPrimitives;
typedef struct { u8 effect; } OverworldActorWalkPolicyCall;
typedef struct { u8 outcome, encodedRemaining; } OverworldWildChainRepositionResult;
static const struct { void (*contactEvent)(OverworldWildSpawnState *,int,void *,int); } health;
#define PLAYER_HEALTH_OVERLAY_ENTRY (&health)
#define OverworldWildSpawns_PlayerHealthReady() FALSE
#define OverworldWildSpawns_RecordFinishedMovementHistory(state,slot) ((void)0)
#define OverworldWildSpawns_RunImmediateCanopyMovementCommand(object,command) ((void)0)
#define OverworldWildSpawns_ObjectCurrentX(object) ((object)->xCurr)
#define OverworldWildSpawns_ObjectCurrentY(object) ((object)->yCurr)
#define OverworldWildSpawns_ClearObjectFlags(object,flags) ((void)0)
#define OverworldWildSpawns_ClearCustomJumpLocal(state,slot) ((void)0)
#define OverworldWildSpawns_IsChainActionReady(slot) FALSE
#define OverworldWildSpawns_ApplyChainRepositionResult(slot,result) TRUE
#define OverworldWildSpawns_InitPolicyCall(call,slot,operation) ((void)0)
#define OverworldWildSpawns_ReduceWalk(call) TRUE
#define OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(state,slot,profile) FALSE
#define OverworldWildSpawns_RunChainReposition(state,slot,profile,remaining,result) ((void)0)
static BOOL ReturnFinish(const OverworldReturnMoveWildContext *context,
    void *profile, void *primitives, u8 flags) {
    assert(context->state==&state && context->field==&field
        && context->ops==&sOverworldWildReturnOps && context->slot==0);
    assert(profile && primitives && !requests && !jumps && !acknowledgements);
    if (flags & OVERWORLD_RETURN_MOVE_WALK_TERMINAL) {
        assert(flags & OVERWORLD_RETURN_MOVE_STOP_AFTER_COMMIT);
        assert(phase==OVERWORLD_MOTION_PHASE_COMMIT_PENDING);
        assert(runtime.movementCustomMotionModes[0]==OW_WILD_CUSTOM_MOTION_WALK);
        ++terminalCommits; phase=OVERWORLD_MOTION_PHASE_IDLE;
        runtime.movementCustomMotionModes[0]=0;
        return FALSE;
    }
    assert(flags & OVERWORLD_RETURN_MOVE_BEFORE_WALK);
    assert(flags & OVERWORLD_RETURN_MOVE_COMBAT_OWNED);
    return FALSE;
}
"""


COMPLETION_CASES = r"""
static void ReadyCompletion(void) {
    Reset(); state.movementFieldSystem=&field;
    runtime.throwState.targets[0]=0; runtime.throwState.targetMask=runtime.throwState.carrierMask=0;
    runtime.movementCustomMotionModes[0]=OW_WILD_CUSTOM_MOTION_WALK;
    phase=OVERWORLD_MOTION_PHASE_COMMIT_PENDING;
    terminalCommits=ordinaryIntents=0; completionChain=0; swapObject=FALSE;
}
int main(void) {
    for (int chain=0;chain<2;chain++) {
        ReadyCompletion(); completionChain=chain?OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING:0;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state,0);
        assert(terminalCommits==1 && !ordinaryIntents && phase==OVERWORLD_MOTION_PHASE_IDLE);
        assert(!requests && !jumps && !acknowledgements && queuedWork==OVERWORLD_COMBAT_KNOCKBACK);
        assert(OverworldWildSpawns_ApplyQueuedCombat(&state,&field,0));
        assert(terminalCommits==1 && requests==1 && jumps==1 && acknowledgements==1);
        assert(queuedWork==OVERWORLD_COMBAT_NONE && objects[0].single && state.movementInProgressMask==1);
    }
    for (int rejected=0;rejected<4;rejected++) {
        ReadyCompletion();
        if(rejected==0) phase=OVERWORLD_MOTION_PHASE_MOVING;
        if(rejected==1) runtime.movementCustomMotionModes[0]=0;
        if(rejected==2) swapObject=TRUE;
        if(rejected==3) queuedWork=OVERWORLD_COMBAT_FAINTED;
        OverworldWildSpawns_HandleFinishedMovementCommand(&state,0);
        assert(!terminalCommits && !ordinaryIntents && !requests && !jumps);
        if(rejected==3) assert(removals==1 && !state.spawns[0].active);
        else assert(queuedWork==OVERWORLD_COMBAT_KNOCKBACK && !acknowledgements);
    }
    puts("Queued knockback closes one accepted Walk before START, skips chain/skid intent, and rejects stale completion.");
    return 0;
}
"""


def main() -> None:
    prefix = ("#include <assert.h>\n#include <stdio.h>\n#include <string.h>\n"
              '#include "overworld_motion_model.h"\n'
              "typedef int BOOL;\n")
    with tempfile.TemporaryDirectory(prefix="overworld-hit-crash-") as temporary:
        source = Path(temporary) / "hit_crash.c"
        executable = Path(temporary) / "hit_crash"
        source.write_text(prefix + production_source() + CASES)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                        str(source), str(ROOT / "lib/overworld/overworld_motion_model.c"),
                        "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
        source = Path(temporary) / "queued_combat.c"
        executable = Path(temporary) / "queued_combat"
        source.write_text(prefix + queued_combat_source())
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                        str(source), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
        source = Path(temporary) / "queued_walk_completion.c"
        executable = Path(temporary) / "queued_walk_completion"
        source.write_text(prefix + queued_walk_completion_source())
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                        str(source), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
        control = source.read_text().replace("    if (combatOwnsCompletion\n",
            "    if (combatOwnsCompletion) return;\n    if (combatOwnsCompletion\n", 1)
        if control == source.read_text():
            raise SystemExit("queued Walk completion negative control was not applied")
        source.write_text(control)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                        str(source), "-o", str(executable)], check=True)
        rejected = subprocess.run([str(executable)], capture_output=True, text=True)
        if rejected.returncode == 0 or "terminalCommits==1" not in rejected.stderr:
            raise SystemExit("queued Walk completion negative control did not reject the old deadlock")
        print("Queued Walk completion negative control rejects the old combat early return.")
        source = Path(temporary) / "heavy_ownership.c"
        executable = Path(temporary) / "heavy_ownership"
        source.write_text(prefix + HEAVY_STUBS + heavy_ownership_source() + HEAVY_CASES)
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"),
                        str(source), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
