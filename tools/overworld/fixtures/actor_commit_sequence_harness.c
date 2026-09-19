/* Real layouts, commit/release bodies, policy INSPECT arm, chain readiness,
 * and portable motion model. COMMIT reduction, service transport, world
 * publication and trace endpoints are host stubs, not a DS ABI claim. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_actor_system.h"
#include "overworld_motion_model.h"

typedef int BOOL;
typedef struct OverworldActorPolicyView OverworldActorPolicyView;
typedef struct OverworldActorPolicyProfileBinding OverworldActorPolicyProfileBinding;

/* @DECLARATIONS@ */
/* @CONSTANTS@ */

static unsigned assertions, cases, populations, logicalTraces, terminalTraces;
static u32 traceCommit;
static BOOL reducerAccepted;
static u8 reducerDecision;
static OverworldActorRuntimeSlot *observedSlot;

#define CHECK(condition) do { assertions++; if (!(condition)) { \
    fprintf(stderr, "actor commit invariant failed at line %d: %s\n", __LINE__, #condition); \
    exit(1); } } while (0)

static BOOL ReduceWalk(OverworldActorWalkPolicyCall *call)
{
    if (call->operation == OVERWORLD_ACTOR_WALK_POLICY_INSPECT) {
        OverworldActorStateSnapshot *actor = &observedSlot->snapshot;
        OverworldActorPolicyState *policy = &observedSlot->policy;
        switch (call->operation) {
        case OVERWORLD_ACTOR_WALK_POLICY_INSPECT:
            /* @INSPECT_ARM@ */
        default: return FALSE;
        }
        return TRUE;
    }
    call->decision = reducerDecision;
    return reducerAccepted;
}
static struct HostPolicyEntry { BOOL (*reduceWalk)(OverworldActorWalkPolicyCall *); } policyEntry = { ReduceWalk };
static struct { struct HostPolicyEntry *policy; } gOverworldActorSystemMovementPolicyServiceEntry = { &policyEntry };
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&gOverworldActorSystemMovementPolicyServiceEntry)

/* @RELEASE_TARGET@ */
static void ActorSystem_PublishPopulationCommit(void) { populations++; }
static void ActorSystem_WriteTrace(const OverworldActorHandle *handle,
    u16 event, u16 reason, u32 a, u32 b)
{
    CHECK(handle->slot == 0 && reason == OVERWORLD_ACTOR_REASON_OK);
    (void)b;
    if (event == OVERWORLD_ACTOR_EVENT_LOGICAL_COMMIT) {
        logicalTraces++;
        traceCommit = a;
    }
}
static void ActorSystem_WriteTerminalTrace(OverworldActorStateSnapshot *actor,
    u16 event, u16 reason, u32 a, u32 b)
{
    CHECK(event == OVERWORLD_ACTOR_EVENT_MOTION_FINISHED);
    CHECK(reason == OVERWORLD_ACTOR_REASON_OK && a == actor->commitSequence);
    CHECK(actor->motionPhase == OVERWORLD_MOTION_PHASE_IDLE);
    CHECK(actor->motionKind == OVERWORLD_ACTOR_MOTION_NONE);
    CHECK(actor->streamState == OVERWORLD_ACTOR_STREAM_IDLE);
    CHECK(actor->reservationId == 0);
    (void)b;
    terminalTraces++;
}

/* @ACKNOWLEDGE@ */
/* @INSPECT@ */
/* @CHAIN_READY@ */

static OverworldMotionPlan Plan(u8 kind, u16 pause)
{
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;
    OverworldMotionPlan plan;
    memset(&intent, 0, sizeof(intent));
    memset(&candidate, 0, sizeof(candidate));
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = kind;
    intent.duration = kind == OVERWORLD_MOTION_KIND_TELEPORT ? 0 : 8;
    intent.pauseFrames = pause;
    intent.fieldEpoch = 7;
    intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    candidate.targetX = 1;
    candidate.distance = 1;
    CHECK(OverworldMotion_SelectPlan(&intent, 0, 0, 0, &candidate, 1, &plan, NULL)
        == OVERWORLD_MOTION_DECISION_ACCEPTED);
    return plan;
}

static OverworldActorWalkPolicyCall WalkPolicy(void)
{
    static const u8 laneWitness = 1;
    OverworldActorWalkPolicyCall call;
    memset(&call, 0, sizeof(call));
    call.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call.size = sizeof(call);
    call.operation = OVERWORLD_ACTOR_WALK_POLICY_COMMIT;
    /* The reducer stub only needs a non-null lane; it never dereferences it. */
    call.lane = (const struct OverworldWildBehaviorProfileData *)&laneWitness;
    return call;
}

static void Arrange(OverworldActorRuntimeSlot *slot, u8 role, u32 sequence)
{
    memset(slot, 0, sizeof(*slot));
    slot->snapshot.active = TRUE;
    slot->snapshot.role = role;
    slot->snapshot.commitSequence = sequence;
    observedSlot = slot;
    populations = logicalTraces = terminalTraces = 0;
    reducerAccepted = TRUE;
    reducerDecision = OVERWORLD_ACTOR_WALK_POLICY_CONSUMED;
}

static void ReachTarget(OverworldActorRuntimeSlot *slot, const OverworldMotionPlan *plan)
{
    OverworldMotionSample sample;
    u32 before = slot->snapshot.commitSequence;
    CHECK(OverworldMotion_Begin(&slot->motion, plan) == OVERWORLD_MOTION_DECISION_ACCEPTED);
    CHECK(slot->snapshot.commitSequence == before);
    CHECK(slot->motion.commitSequence == 0 && slot->motion.commitPublished == 0);
    for (unsigned frame = 0; frame < (plan->duration ? plan->duration : 1); frame++) {
        OverworldMotion_Tick(&slot->motion, 7, &sample);
        CHECK(slot->snapshot.commitSequence == before);
    }
    CHECK(slot->motion.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING);
    /* ActorSystem_Frame publishes these before the engine updater supplies
     * the final ACK. Start from that real boundary shape, not an idle zero. */
    slot->snapshot.motionPhase = slot->motion.phase;
    slot->snapshot.motionKind = plan->kind;
    slot->snapshot.motionElapsed = slot->motion.elapsed;
    slot->snapshot.motionDuration = plan->duration;
    slot->snapshot.reservationId = 0x1234;
    slot->snapshot.streamState = OVERWORLD_ACTOR_STREAM_ADVANCED;
    slot->snapshot.reserved1 = OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS;
}

static void Commit(OverworldActorRuntimeSlot *slot)
{
    OverworldActorWalkPolicyCall call = WalkPolicy();
    OverworldActorWalkPolicyCall *walk = slot->motion.plan.kind == OVERWORLD_MOTION_KIND_WALK ? &call : NULL;
    u32 expected = slot->snapshot.commitSequence + 1u;
    unsigned before = logicalTraces;
    CHECK(ActorSystem_TryAcknowledgeMotionCommit(slot, 7, walk) == OVERWORLD_MOTION_DECISION_ACCEPTED);
    CHECK(slot->snapshot.commitSequence == expected);
    CHECK(slot->motion.commitSequence == 1 && slot->motion.commitPublished == 1);
    CHECK(logicalTraces == before + 1 && traceCommit == expected);
    CHECK(populations == logicalTraces && slot->snapshot.reservationId == 0);
    CHECK(slot->snapshot.reserved1 == 0);
    {
        OverworldActorStateSnapshot published = slot->snapshot;
        CHECK(ActorSystem_TryAcknowledgeMotionCommit(slot, 7, walk) == OVERWORLD_MOTION_DECISION_ACCEPTED);
        CHECK(memcmp(&published, &slot->snapshot, sizeof(published)) == 0);
    }
    CHECK(slot->snapshot.commitSequence == expected && logicalTraces == before + 1);
}

static void CheckContinuousMotions(void)
{
    static const u32 seeds[] = { 0, 65534, 0xFFFFFFFEu };
    static const u8 kinds[] = { OVERWORLD_MOTION_KIND_HOP, OVERWORLD_MOTION_KIND_WALK,
        OVERWORLD_MOTION_KIND_WALK, OVERWORLD_MOTION_KIND_REPOSITION,
        OVERWORLD_MOTION_KIND_TELEPORT };
    for (u8 role = OVERWORLD_ACTOR_ROLE_WILD; role <= OVERWORLD_ACTOR_ROLE_MOUNTED; role++) {
        for (unsigned seed = 0; seed < sizeof(seeds) / sizeof(seeds[0]); seed++) {
            OverworldActorRuntimeSlot slot;
            Arrange(&slot, role, seeds[seed]);
            for (unsigned index = 0; index < sizeof(kinds) / sizeof(kinds[0]); index++) {
                OverworldMotionPlan plan = Plan(kinds[index], index == 0 ? 2 : 0);
                if (index == 3) plan.commitPolicy = OVERWORLD_MOTION_COMMIT_NO_CHAIN;
                slot.policy.pendingStep = OVERWORLD_ACTOR_WALK_PENDING_NONE;
                ReachTarget(&slot, &plan);
                Commit(&slot);
                CHECK(slot.snapshot.commitSequence == seeds[seed] + index + 1u);
                CHECK(slot.policy.pendingStep
                    == (role != OVERWORLD_ACTOR_ROLE_MOUNTED && index != 3
                        ? OVERWORLD_ACTOR_WALK_PENDING_CHAIN : OVERWORLD_ACTOR_WALK_PENDING_NONE));
                for (unsigned pause = 0; pause < plan.pauseFrames; pause++) {
                    OverworldMotionState before = slot.motion;
                    OverworldMotionSample sample;
                    CHECK(OverworldMotion_Begin(&slot.motion, &plan) == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE);
                    CHECK(memcmp(&before, &slot.motion, sizeof(before)) == 0);
                    OverworldMotion_Tick(&slot.motion, 7, &sample);
                    CHECK(slot.snapshot.commitSequence == seeds[seed] + index + 1u);
                }
                CHECK(slot.motion.phase == OVERWORLD_MOTION_PHASE_IDLE);
                cases++;
            }
        }
    }
}

static void CheckRejectedBoundaries(void)
{
    for (unsigned kind = 0; kind < 2; kind++) {
        for (unsigned rejection = 0; rejection < 9; rejection++) {
            OverworldActorRuntimeSlot slot;
            OverworldMotionPlan plan = Plan(kind ? OVERWORLD_MOTION_KIND_WALK : OVERWORLD_MOTION_KIND_HOP, 0);
            OverworldActorWalkPolicyCall call = WalkPolicy();
            OverworldActorWalkPolicyCall *walk = kind ? &call : NULL;
            Arrange(&slot, OVERWORLD_ACTOR_ROLE_WILD, 0x12345678);
            ReachTarget(&slot, &plan);
            switch (rejection) {
            case 0: slot.snapshot.reserved1 &= ~OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED; break;
            case 1: slot.snapshot.reserved1 &= ~OVERWORLD_ACTOR_BOUNDARY_STREAM_READY; break;
            case 2: slot.snapshot.reserved1 &= ~OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED; break;
            case 3: slot.snapshot.reserved1 &= ~OVERWORLD_ACTOR_BOUNDARY_ENGINE_END; break;
            case 4: slot.policy.pendingFirstPathAdvance = 1; break;
            case 5: slot.snapshot.active = FALSE; break;
            case 6: walk = kind ? NULL : &call; break;
            case 7:
                if (kind) reducerAccepted = FALSE;
                else slot.motion.phase = OVERWORLD_MOTION_PHASE_MOVING;
                break;
            case 8:
                if (kind) reducerDecision = OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
                else slot.motion.plan.fieldEpoch = 8; /* Real model rejects the acknowledgement. */
                break;
            }
            {
                OverworldActorStateSnapshot before = slot.snapshot;
                ActorSystem_TryAcknowledgeMotionCommit(&slot, 7, walk);
                CHECK(memcmp(&before, &slot.snapshot, sizeof(before)) == 0);
            }
            CHECK(slot.snapshot.commitSequence == 0x12345678);
            CHECK(slot.motion.commitSequence == 0 && slot.motion.commitPublished == 0);
            CHECK(logicalTraces == 0 && populations == 0 && terminalTraces == 0);
            CHECK(slot.snapshot.reservationId == 0x1234);
            cases++;
        }
    }
}

static void CheckCancelAndReset(void)
{
    OverworldActorRuntimeSlot slot;
    OverworldMotionPlan plan = Plan(OVERWORLD_MOTION_KIND_WALK, 0);
    OverworldMotionState zero;
    Arrange(&slot, OVERWORLD_ACTOR_ROLE_WILD, 0);
    ReachTarget(&slot, &plan);
    Commit(&slot);
    ReachTarget(&slot, &plan);
    OverworldMotion_Cancel(&slot.motion, OVERWORLD_MOTION_DECISION_CONTEXT_LOST);
    CHECK(slot.motion.phase == OVERWORLD_MOTION_PHASE_CANCELED);
    ActorSystem_TryAcknowledgeMotionCommit(&slot, 7, NULL);
    CHECK(slot.snapshot.commitSequence == 1 && logicalTraces == 1);
    ReachTarget(&slot, &plan); /* Begin from CANCELED resets only this motion. */
    CHECK(slot.motion.cancelReason == 0);
    Commit(&slot);
    CHECK(slot.snapshot.commitSequence == 2);
    OverworldMotion_Reset(&slot.motion);
    memset(&zero, 0, sizeof(zero));
    CHECK(memcmp(&slot.motion, &zero, sizeof(zero)) == 0);
    CHECK(slot.snapshot.commitSequence == 2);
    ReachTarget(&slot, &plan);
    Commit(&slot);
    CHECK(slot.snapshot.commitSequence == 3);
    cases++;
}

static void CheckTerminalPublication(void)
{
    static const u8 kinds[] = { OVERWORLD_MOTION_KIND_WALK, OVERWORLD_MOTION_KIND_HOP,
        OVERWORLD_MOTION_KIND_REPOSITION, OVERWORLD_MOTION_KIND_TELEPORT };
    static const u16 pauses[] = { 0, 1, 2, 40 };
    for (u8 role = OVERWORLD_ACTOR_ROLE_WILD; role <= OVERWORLD_ACTOR_ROLE_MOUNTED; role++) {
        for (unsigned kind = 0; kind < sizeof(kinds) / sizeof(kinds[0]); kind++) {
            for (unsigned pause = 0; pause < sizeof(pauses) / sizeof(pauses[0]); pause++) {
                OverworldActorRuntimeSlot slot;
                OverworldActorPolicyView view;
                OverworldMotionPlan plan = Plan(kinds[kind], pauses[pause]);
                Arrange(&slot, role, 9);
                slot.snapshot.inputOwnership = role == OVERWORLD_ACTOR_ROLE_MOUNTED ? 1 : 0;
                ReachTarget(&slot, &plan);
                CHECK(OverworldActorPolicy_Inspect(0, &view));
                CHECK(view.motionPhase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING);
                CHECK(!OverworldWildSpawns_IsChainActionReady(0));
                Commit(&slot);
                /* No Frame tick or successor Begin is allowed to repair the
                 * snapshot before the public reader/real chain guard run. */
                CHECK(slot.snapshot.motionPhase == (pauses[pause]
                    ? OVERWORLD_MOTION_PHASE_SETTLING : OVERWORLD_MOTION_PHASE_IDLE));
                CHECK(slot.snapshot.motionKind == (pauses[pause]
                    ? kinds[kind] : OVERWORLD_ACTOR_MOTION_NONE));
                CHECK(slot.snapshot.streamState == (pauses[pause]
                    ? OVERWORLD_ACTOR_STREAM_ADVANCED : OVERWORLD_ACTOR_STREAM_IDLE));
                CHECK(slot.snapshot.inputOwnership == (role == OVERWORLD_ACTOR_ROLE_MOUNTED ? 1 : 0));
                CHECK(slot.snapshot.motionElapsed == plan.duration);
                CHECK(slot.snapshot.motionDuration == plan.duration);
                CHECK(OverworldActorPolicy_Inspect(0, &view));
                CHECK(view.actorActive && view.motionPhase == slot.motion.phase);
                CHECK(OverworldWildSpawns_IsChainActionReady(0) == (pauses[pause] == 0));
                CHECK(!OverworldWildSpawns_IsChainActionReady(-1));
                CHECK(terminalTraces == (pauses[pause] == 0));
                cases++;
            }
        }
    }
}

int main(void)
{
    CheckTerminalPublication();
    CheckContinuousMotions();
    CheckRejectedBoundaries();
    CheckCancelAndReset();
    printf("PASS actor lifetime commit cases: %u cases, %u assertions\n", cases, assertions);
    return 0;
}
