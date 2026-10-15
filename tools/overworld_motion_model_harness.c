#include "overworld_motion_model.h"

#include <stdio.h>
#include <string.h>

static int sFailures;

#define CHECK(condition, label) \
    do { \
        if (!(condition)) { \
            fprintf(stderr, "FAIL: %s\n", label); \
            sFailures++; \
        } \
    } while (0)

static OverworldMotionIntent MakeIntent(u8 kind, u16 duration)
{
    OverworldMotionIntent intent;

    memset(&intent, 0, sizeof(intent));
    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = kind;
    intent.duration = duration;
    intent.fieldEpoch = 7;
    intent.facing = 3;
    intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NORMAL;
    return intent;
}

static OverworldMotionCandidate MakeCandidate(s16 x, s16 y, u16 flags)
{
    OverworldMotionCandidate candidate;

    memset(&candidate, 0, sizeof(candidate));
    candidate.targetX = x;
    candidate.targetY = y;
    candidate.targetBaseY = 0x1000;
    candidate.rejectionFlags = flags;
    candidate.distance = 1;
    return candidate;
}

static int CountPublishedAdvances(
    u16 flags,
    const OverworldMotionSample *sample)
{
    if ((flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) == 0) {
        return 0;
    }
    return sample->lastPathAdvance - sample->firstPathAdvance + 1;
}

static void CheckCandidateOrder(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_WALK, 8);
    OverworldMotionCandidate candidates[3];
    OverworldMotionPlan plan;
    u8 selected = 0xFF;

    candidates[0] = MakeCandidate(1, 0, OVERWORLD_MOTION_CANDIDATE_BLOCKED);
    candidates[1] = MakeCandidate(1, 1, 0);
    candidates[2] = MakeCandidate(0, 1, 0);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, candidates, 3, &plan, &selected)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "first valid candidate is accepted");
    CHECK(selected == 1 && plan.targetX == 1 && plan.targetY == 1,
        "candidate order is stable");

    candidates[0].rejectionFlags = OVERWORLD_MOTION_CANDIDATE_WORLD_BUSY;
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, candidates, 3, &plan, &selected)
            == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY,
        "world busy does not fall through to a different target");
}

static void CheckExactWalk(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_WALK, 8);
    OverworldMotionCandidate candidate = MakeCandidate(1, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    u16 flags;
    int frame;
    int advances = 0;

    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Walk plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Walk begins");
    for (frame = 1; frame <= 8; frame++) {
        flags = OverworldMotion_Tick(&state, 7, &sample);
        CHECK(sample.elapsed == frame, "Walk elapsed is exact");
        advances += CountPublishedAdvances(flags, &sample);
        if (frame < 8) {
            CHECK((flags & OVERWORLD_MOTION_TICK_COMMIT_READY) == 0,
                "Walk cannot commit early");
        }
    }
    CHECK(sample.renderX == 0x18000 && sample.renderZ == 0x8000,
        "Walk reaches the exact target");
    CHECK(advances == 1, "one-tile Walk publishes one path advance");
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING,
        "Walk waits for engine commit acknowledgement");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Walk commit is acknowledged");
    CHECK(state.commitSequence == 1
            && state.phase == OVERWORLD_MOTION_PHASE_IDLE,
        "Walk publishes exactly one terminal commit");
}

static void CheckDurationBoundaries(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_WALK, 1);
    OverworldMotionCandidate candidate = MakeCandidate(1, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    u16 flags;
    int frame;
    int advances = 0;

    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "one-frame Walk plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "one-frame Walk begins");
    flags = OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.elapsed == 1 && sample.renderX == 0x18000,
        "duration 1 reaches the exact target on its first tick");
    CHECK((flags & (OVERWORLD_MOTION_TICK_REACHED_TARGET
                    | OVERWORLD_MOTION_TICK_COMMIT_READY))
            == (OVERWORLD_MOTION_TICK_REACHED_TARGET
                | OVERWORLD_MOTION_TICK_COMMIT_READY),
        "duration 1 reaches commit pending on its first tick");
    CHECK(CountPublishedAdvances(flags, &sample) == 1,
        "duration 1 publishes one path advance");
    flags = OverworldMotion_Tick(&state, 7, &sample);
    CHECK(flags == OVERWORLD_MOTION_TICK_COMMIT_READY
            && state.commitSequence == 0,
        "waiting for acknowledgement does not publish a commit");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "duration 1 commit is acknowledged");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE
            && state.commitSequence == 1,
        "a terminal commit cannot be acknowledged twice");

    intent = MakeIntent(OVERWORLD_MOTION_KIND_WALK, 32);
    candidate = MakeCandidate(-1, 3, 0);
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, -2, 3, -0x2000, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "32-frame Walk plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "32-frame Walk begins");
    for (frame = 1; frame <= 32; frame++) {
        flags = OverworldMotion_Tick(&state, 7, &sample);
        advances += CountPublishedAdvances(flags, &sample);
        CHECK(sample.elapsed == frame, "duration 32 elapsed is exact");
        if (frame < 32) {
            CHECK((flags & OVERWORLD_MOTION_TICK_COMMIT_READY) == 0,
                "duration 32 cannot commit early");
        }
    }
    CHECK(sample.renderX == -0x8000 && sample.renderZ == 0x38000,
        "duration 32 reaches a negative-coordinate target exactly");
    CHECK(advances == 1,
        "duration 32 publishes one and only one path advance");
}

static void CheckDiagonalMultiTilePath(void)
{
    static const s16 expectedX[] = { 0, 1, 2, 2, 3, 4 };
    static const s16 expectedY[] = { 0, 0, 0, 1, 1, 1 };
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_HOP, 8);
    OverworldMotionCandidate candidate = MakeCandidate(4, 1, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    u16 flags;
    u16 published = 0;
    s16 tileX;
    s16 tileY;
    int frame;
    int advance;

    candidate.distance = 4;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "diagonal multi-tile plan resolves");
    for (advance = 0; advance <= 5; advance++) {
        CHECK(OverworldMotion_GetPathAdvanceTile(
                  &plan, (u16)advance, &tileX, &tileY),
            "diagonal path tile is available");
        CHECK(tileX == expectedX[advance] && tileY == expectedY[advance],
            "diagonal path order follows boundary crossings");
    }
    CHECK(!OverworldMotion_GetPathAdvanceTile(&plan, 6, &tileX, &tileY),
        "diagonal path rejects an advance beyond its target");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "diagonal multi-tile motion begins");
    for (frame = 1; frame <= 8; frame++) {
        flags = OverworldMotion_Tick(&state, 7, &sample);
        if (flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) {
            CHECK(sample.firstPathAdvance == published + 1,
                "path advance ranges do not skip or repeat events");
            published = sample.lastPathAdvance;
        }
    }
    CHECK(published == 5,
        "four-by-one diagonal travel emits five ordered boundary crossings");
    CHECK(sample.renderX == 0x48000 && sample.renderZ == 0x18000,
        "diagonal multi-tile motion reaches its exact target");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ACCEPTED
            && state.commitSequence == 1,
        "diagonal multi-tile motion still produces one terminal commit");
}

static void CheckPresentationMath(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_HOP, 8);
    OverworldMotionCandidate candidate = MakeCandidate(4, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;

    intent.arcHeightQ4 = 32;
    intent.swayWidth = 2;
    intent.spinSpeed = 2;
    candidate.distance = 4;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "presentation-math plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "presentation-math motion begins");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.heightOffset == 49152 && sample.swayOffset == 6144,
        "arc and first sway lobe keep deployed integer truncation");
    CHECK(sample.facing == 3,
        "spin waits for its authored frame interval");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.heightOffset == 98304 && sample.swayOffset == 8192,
        "arc and sway peak use exact integer math");
    CHECK(sample.facing == 1,
        "spin advances in engine N/E/S/W order");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    (void)OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.heightOffset == 131072 && sample.swayOffset == 0,
        "arc midpoint and sway crossover are exact");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.swayOffset == -6144,
        "second sway lobe mirrors with a negative sign");
}

static void CheckHopAndTransition(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_HOP, 8);
    OverworldMotionCandidate candidate = MakeCandidate(4, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    u16 flags;
    int advances = 0;
    int frame;
    s32 heldX;
    s32 heldY;
    s32 heldZ;

    intent.arcHeightQ4 = 32;
    intent.pauseFrames = 2;
    candidate.distance = 4;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Hop plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Hop begins");
    for (frame = 1; frame <= 4; frame++) {
        flags = OverworldMotion_Tick(&state, 7, &sample);
        advances += CountPublishedAdvances(flags, &sample);
    }
    CHECK(sample.heightOffset == 131072,
        "Hop has the deployed midpoint arc");
    heldX = sample.renderX;
    heldY = sample.renderY;
    heldZ = sample.renderZ;
    CHECK(OverworldMotion_Tick(&state, 8, &sample) == 0,
        "field epoch mismatch suspends Hop");
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_SUSPENDED
            && state.elapsed == 4
            && sample.renderX == heldX
            && sample.renderY == heldY
            && sample.renderZ == heldZ,
        "suspension holds the complete render sample");
    CHECK(OverworldMotion_Tick(&state, 8, &sample) == 0
            && state.elapsed == 4,
        "repeated suspended ticks cannot advance time");
    CHECK(OverworldMotion_RebindField(&state, 6, 8)
            == OVERWORLD_MOTION_DECISION_STALE_FIELD,
        "transition rebind rejects the wrong previous epoch");
    CHECK(OverworldMotion_RebindField(&state, 7, 8)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "transition coordinator can rebind and resume Hop");
    for (frame = 5; frame <= 8; frame++) {
        flags = OverworldMotion_Tick(&state, 8, &sample);
        advances += CountPublishedAdvances(flags, &sample);
    }
    CHECK(advances == 4, "four-tile Hop publishes four path advances");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 8)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Hop commits after transition rebind");
    CHECK(state.commitSequence == 1
            && state.phase == OVERWORLD_MOTION_PHASE_SETTLING,
        "Hop has one commit and enters its authored pause");
    (void)OverworldMotion_Tick(&state, 8, &sample);
    flags = OverworldMotion_Tick(&state, 8, &sample);
    CHECK((flags & OVERWORLD_MOTION_TICK_FINISHED) != 0
            && state.phase == OVERWORLD_MOTION_PHASE_IDLE,
        "Hop pause ends on the exact frame");
}

static void CheckCancelIsTerminal(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_HOP, 8);
    OverworldMotionCandidate candidate = MakeCandidate(2, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;

    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "cancel plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "cancel motion begins");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    OverworldMotion_Cancel(&state, 4);
    OverworldMotion_Cancel(&state, 9);
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_CANCELED
            && state.cancelReason == 4,
        "cancel is terminal and preserves the first reason");
    CHECK(OverworldMotion_Tick(&state, 7, &sample) == 0
            && state.commitSequence == 0,
        "canceled motion cannot tick or commit");
}

static void CheckTeleportVisibility(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_TELEPORT, 4);
    OverworldMotionCandidate candidate = MakeCandidate(2, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;

    intent.visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_FLICKER;
    candidate.distance = 2;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Teleport plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Teleport begins");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.visible != 0, "Teleport visibility starts on");
    (void)OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.visible == 0, "Teleport flicker is deterministic");
}

static void CheckZeroDurationTeleport(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_TELEPORT, 0);
    OverworldMotionCandidate candidate = MakeCandidate(3, -2, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    u16 flags;

    intent.visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_HIDDEN;
    candidate.distance = 3;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0x1000, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "zero-duration Teleport plan resolves");
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "zero-duration Teleport uses the normal begin seam");
    flags = OverworldMotion_Tick(&state, 7, &sample);
    CHECK(sample.elapsed == 0
            && sample.renderX == 0x38000
            && sample.renderZ == -0x18000,
        "zero-duration Teleport samples its target in the start frame");
    CHECK((flags & (OVERWORLD_MOTION_TICK_PATH_ADVANCED
                    | OVERWORLD_MOTION_TICK_REACHED_TARGET
                    | OVERWORLD_MOTION_TICK_COMMIT_READY))
            == (OVERWORLD_MOTION_TICK_PATH_ADVANCED
                | OVERWORLD_MOTION_TICK_REACHED_TARGET
                | OVERWORLD_MOTION_TICK_COMMIT_READY),
        "zero-duration Teleport publishes path and commit readiness at once");
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING,
        "zero-duration Teleport waits for the normal commit acknowledgement");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "zero-duration Teleport completes through the normal acknowledgement");

    intent = MakeIntent(OVERWORLD_MOTION_KIND_WALK, 0);
    CHECK(OverworldMotion_SelectPlan(
              &intent, 0, 0, 0, &candidate, 1, &plan, NULL)
            == OVERWORLD_MOTION_DECISION_PROFILE,
        "zero-duration Walk remains invalid");
    memset(&plan, 0, sizeof(plan));
    plan.version = OVERWORLD_MOTION_MODEL_VERSION;
    plan.kind = OVERWORLD_MOTION_KIND_HOP;
    CHECK(OverworldMotion_Begin(&state, &plan)
            == OVERWORLD_MOTION_DECISION_PROFILE,
        "zero-duration Hop remains invalid");
}

static void CheckWorldGateOwnership(void)
{
    CHECK(!OverworldMotion_BlocksWorldGate(
            FALSE, TRUE, OVERWORLD_MOTION_PHASE_MOVING, 9),
        "inactive actor cannot block a world gate");
    CHECK(!OverworldMotion_BlocksWorldGate(
            TRUE, FALSE, OVERWORLD_MOTION_PHASE_MOVING, 9),
        "non-player actor cannot block a world gate");
    CHECK(!OverworldMotion_BlocksWorldGate(
            TRUE, TRUE, OVERWORLD_MOTION_PHASE_IDLE, 0),
        "idle player actor leaves world gates open");
    CHECK(OverworldMotion_BlocksWorldGate(
            TRUE, TRUE, OVERWORLD_MOTION_PHASE_MOVING, 9),
        "moving player actor blocks world gates");
    CHECK(OverworldMotion_BlocksWorldGate(
            TRUE, TRUE, OVERWORLD_MOTION_PHASE_SETTLING, 0),
        "settling player actor blocks world gates");
    CHECK(OverworldMotion_BlocksWorldGate(
            TRUE, TRUE, OVERWORLD_MOTION_PHASE_IDLE, 9),
        "player reservation blocks world gates before phase publication");
    CHECK(!OverworldMotion_BlocksWorldGate(
            TRUE, TRUE, OVERWORLD_MOTION_PHASE_CANCELED, 0),
        "terminal cancel reopens world gates");
}


static void CheckCurvedSlamRise(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_HOP, 16);
    OverworldMotionCandidate candidate = MakeCandidate(6, 0, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    /* Independent Q4 heights: fast initial rise, then a level apex. */
    static const u8 heights[] = {15, 28, 39, 48, 55, 60, 63, 64,
        64, 64, 64, 64, 48, 32, 16, 0};
    unsigned frame;
    intent.flags = OVERWORLD_MOTION_FLAG_SLAM;
    intent.arcHeightQ4 = 64;
    intent.arcRiseFrames = 8;
    intent.arcHangFrames = 4;
    intent.pauseFrames = 0;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(&intent, 0, 0, 0, &candidate, 1,
              &plan, NULL) == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "six-tile curved Slam resolves through shared Motion");
    CHECK(OverworldMotion_Begin(&state, &plan) == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "curved Slam begins through the ordinary owner");
    for (frame = 1; frame <= sizeof(heights); frame++) {
        OverworldMotion_Tick(&state, 7, &sample);
        CHECK(sample.heightOffset == (s32)heights[frame - 1] * 4096,
            "Slam curves upward, holds at four tiles and drops straight down");
        if (frame >= 8) {
            CHECK(sample.renderX == 0x68000 && sample.renderZ == 0x8000,
                "curved Slam keeps its exact frozen landing through hang and drop");
        }
    }
}

static void CheckSlam(void)
{
    OverworldMotionIntent intent = MakeIntent(OVERWORLD_MOTION_KIND_HOP, 20);
    OverworldMotionCandidate candidate = MakeCandidate(-1, 5, 0);
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample sample;
    u16 flags;
    int frame;
    int advances = 0;
    static const s32 lateHeights[] = {0x18000, 0x18000, 0x18000,
        0x18000, 0x18000, 0x12000, 0xC000, 0x6000, 0};

    CHECK(sizeof(OverworldMotionIntent) == 18 && sizeof(OverworldMotionPlan) == 40,
        "Slam retains the fixed Motion intent and plan sizes");
    CHECK(offsetof(OverworldMotionIntent, arcRiseFrames)
            == offsetof(OverworldMotionIntent, spinSpeed)
            && offsetof(OverworldMotionPlan, arcHangFrames)
                == offsetof(OverworldMotionPlan, swayWidth),
        "Slam phase aliases retain the old byte offsets");
    intent.flags = OVERWORLD_MOTION_FLAG_SLAM;
    intent.arcHeightQ4 = 24;
    intent.arcRiseFrames = 12;
    intent.arcHangFrames = 4;
    intent.pauseFrames = 2;
    candidate.targetBaseY = 0x9000;
    OverworldMotion_Reset(&state);
    CHECK(OverworldMotion_SelectPlan(&intent, -4, 3, -0x3000,
              &candidate, 1, &plan, NULL) == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Slam resolves without changing its authored phases");
    CHECK(plan.arcRiseFrames == 12 && plan.arcHangFrames == 4
            && plan.arcHeightQ4 == 24 && plan.duration == 20,
        "Slam plan keeps rise, hang, total and peak");
    CHECK(OverworldMotion_Begin(&state, &plan) == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Slam begins in shared Motion");
    for (frame = 1; frame <= 20; frame++) {
        flags = OverworldMotion_Tick(&state, 7, &sample);
        advances += CountPublishedAdvances(flags, &sample);
        CHECK(sample.elapsed == frame && sample.duration == 20,
            "Slam uses one shared total clock");
        CHECK(sample.facing == 3 && sample.swayOffset == 0,
            "Slam phase bytes never turn into spin or sway");
        if (frame == 6) {
            CHECK(sample.renderX == -0x20000 && sample.renderZ == 0x48000
                    && sample.baseY == 0x3000 && sample.heightOffset == 0x12000,
                "Slam has a curved three-quarter height at half-rise");
        }
        if (frame >= 12) {
            CHECK(sample.renderX == -0x8000 && sample.renderZ == 0x58000
                    && sample.baseY == 0x9000,
                "Slam hangs and drops straight over its frozen landing");
            CHECK(sample.heightOffset == lateHeights[frame - 12],
                "Slam peak, hang and fast drop have exact frame heights");
            CHECK(advances == 5, "Slam logical path completes at rise, not drop");
            if (frame > 12) {
                CHECK((flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) == 0,
                    "Slam hang/drop never publishes a second path advance");
            }
        }
        if (frame < 20) {
            CHECK((flags & (OVERWORLD_MOTION_TICK_COMMIT_READY
                        | OVERWORLD_MOTION_TICK_REACHED_TARGET)) == 0,
                "Slam cannot finish while airborne or hanging");
        }
    }
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING
            && sample.heightOffset == 0
            && (flags & OVERWORLD_MOTION_TICK_COMMIT_READY),
        "Slam reaches one ordinary terminal at drop end");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ACCEPTED
            && state.commitSequence == 1 && state.settleRemaining == 2,
        "Slam pause begins only after terminal acknowledgement");
    CHECK(OverworldMotion_AcknowledgeCommit(&state, 7)
            == OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE,
        "Slam terminal cannot be acknowledged twice");
    OverworldMotion_Tick(&state, 7, &sample);
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_SETTLING,
        "Slam keeps its first authored settling frame");
    flags = OverworldMotion_Tick(&state, 7, &sample);
    CHECK(state.phase == OVERWORLD_MOTION_PHASE_IDLE
            && (flags & OVERWORLD_MOTION_TICK_FINISHED),
        "Slam returns control through the ordinary pause lifecycle");

    /* These boundary inputs exercise phase validity and division edges. */
    {
        static const u8 phases[][3] = {{1, 0, 1}, {3, 0, 7}, {4, 1, 1}, {255, 255, 255}};
        unsigned i;
        for (i = 0; i < sizeof(phases) / sizeof(phases[0]); i++) {
            u16 total = (u16)phases[i][0] + phases[i][1] + phases[i][2];
            intent.arcRiseFrames = phases[i][0];
            intent.arcHangFrames = phases[i][1];
            intent.duration = total;
            intent.pauseFrames = 0;
            OverworldMotion_Reset(&state);
            CHECK(OverworldMotion_SelectPlan(&intent, -4, 3, -0x3000,
                      &candidate, 1, &plan, NULL) == OVERWORLD_MOTION_DECISION_ACCEPTED,
                "Slam accepts positive rise/drop and zero or maximum hang");
            CHECK(OverworldMotion_Begin(&state, &plan)
                    == OVERWORLD_MOTION_DECISION_ACCEPTED,
                "Slam phase boundary begins");
            for (frame = 1; frame <= total; frame++) {
                OverworldMotion_Tick(&state, 7, &sample);
                if (frame >= intent.arcRiseFrames) {
                    CHECK(sample.renderX == -0x8000 && sample.renderZ == 0x58000,
                        "every Slam phase boundary holds its landing after rise");
                }
                CHECK(sample.heightOffset >= 0 && sample.heightOffset <= 0x18000,
                    "every Slam phase boundary stays within its configured peak");
            }
            CHECK(sample.heightOffset == 0
                    && state.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING,
                "every Slam phase boundary completes only at its total duration");
        }
    }
    intent.arcRiseFrames = 12;
    intent.arcHangFrames = 4;
    intent.duration = 20;
    intent.arcHeightQ4 = 24;
    for (frame = 0; frame < 5; frame++) {
        OverworldMotionIntent invalid = intent;
        switch (frame) {
        case 0: invalid.arcRiseFrames = 0; break;
        case 1: invalid.arcHeightQ4 = 0; break;
        case 2: invalid.duration = 16; break;
        case 3: invalid.duration = 15; break;
        default: invalid.kind = OVERWORLD_MOTION_KIND_WALK; break;
        }
        CHECK(OverworldMotion_SelectPlan(&invalid, -4, 3, -0x3000,
                  &candidate, 1, &plan, NULL) == OVERWORLD_MOTION_DECISION_PROFILE,
            "malformed Slam cannot enter candidate selection");
        memset(&plan, 0, sizeof(plan));
        plan.version = invalid.version;
        plan.kind = invalid.kind;
        plan.duration = invalid.duration;
        plan.flags = invalid.flags;
        plan.arcHeightQ4 = invalid.arcHeightQ4;
        plan.arcRiseFrames = invalid.arcRiseFrames;
        plan.arcHangFrames = invalid.arcHangFrames;
        OverworldMotion_Reset(&state);
        CHECK(OverworldMotion_Begin(&state, &plan) == OVERWORLD_MOTION_DECISION_PROFILE,
            "malformed direct Slam plan cannot begin");
    }
    candidate.rejectionFlags = OVERWORLD_MOTION_CANDIDATE_OCCUPIED;
    CHECK(OverworldMotion_SelectPlan(&intent, -4, 3, -0x3000,
              &candidate, 1, &plan, NULL) == OVERWORLD_MOTION_DECISION_OCCUPIED,
        "Slam never grants occupied landing permission");
}

int main(void)
{
    CheckCandidateOrder();
    CheckExactWalk();
    CheckDurationBoundaries();
    CheckDiagonalMultiTilePath();
    CheckPresentationMath();
    CheckHopAndTransition();
    CheckCancelIsTerminal();
    CheckTeleportVisibility();
    CheckZeroDurationTeleport();
    CheckWorldGateOwnership();
    CheckSlam();
    CheckCurvedSlamRise();
    if (sFailures != 0) {
        return 1;
    }
    puts("overworld motion model contracts verified");
    return 0;
}
