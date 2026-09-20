#include "overworld_motion_model.h"

#include <stdio.h>
#include <string.h>

/*
 * Independent host oracle for the fixed-size Thumb planner. It proves the
 * public candidate-order and rejection contracts without adding a second
 * runtime policy owner to a field adapter.
 */

#define TARGET_ADJACENT 0
#define TARGET_DIRECTIONAL 1
#define TARGET_CHILL 2
#define RESERVED_STOPS_SEARCH (1u << 0)

typedef struct HostLane {
    u8 bytes[72];
} HostLane;

typedef struct HostCandidate {
    s16 targetX;
    s16 targetY;
    s32 targetBaseY;
    u16 rejectionFlags;
    u8 direction;
    u8 distance;
    u8 targetFacing;
    u8 reserved;
} HostCandidate;

typedef void (*HostClassify)(void *world, HostCandidate *candidate);

typedef struct HostCall {
    const HostLane *lane;
    const u8 *directions;
    HostClassify classify;
    void *world;
    u32 directionRandom;
    u32 distanceRandom;
    s16 desiredX;
    s16 desiredY;
    u8 targetMode;
    u8 directionCount;
    u8 pathAdvancePolicy;
    u8 flags;
} HostCall;

typedef struct HostRequest {
    u8 candidateCount;
    u8 reservedReason;
    u8 selectedIndex;
    u16 fieldEpoch;
    s16 startX;
    s16 startY;
    s32 startBaseY;
    OverworldMotionPlan *plan;
    HostCall *teleportPlan;
} HostRequest;

typedef struct HostWorld {
    HostCandidate candidates[20];
    u8 count;
    u8 rejectReservedAt;
    u8 rejectBusyAt;
    u8 acceptAt;
} HostWorld;

static int sFailures;

#define CHECK(condition, label) \
    do { \
        if (!(condition)) { \
            fprintf(stderr, "FAIL: %s\n", label); \
            sFailures++; \
        } \
    } while (0)

static s16 MinMagnitude(s16 delta, u8 distance)
{
    s16 magnitude = delta < 0 ? (s16)-delta : delta;

    if (magnitude > distance) {
        magnitude = distance;
    }
    return delta < 0 ? (s16)-magnitude : magnitude;
}

static s16 DeltaX(u8 direction)
{
    static const signed char deltas[] = { 0, 0, -1, 1, -1, 1, -1, 1 };

    return direction < sizeof(deltas) ? deltas[direction] : 0;
}

static s16 DeltaY(u8 direction)
{
    static const signed char deltas[] = { -1, 1, 0, 0, -1, -1, 1, 1 };

    return direction < sizeof(deltas) ? deltas[direction] : 0;
}

static u8 DirectionFromDelta(s16 deltaX, s16 deltaY)
{
    if (deltaX < 0) {
        return deltaY < 0 ? 4 : deltaY > 0 ? 6 : 2;
    }
    if (deltaX > 0) {
        return deltaY < 0 ? 5 : deltaY > 0 ? 7 : 3;
    }
    return deltaY > 0 ? 1 : 0;
}

static OverworldMotionDecision CandidateDecision(u16 flags, u8 callFlags)
{
    if (flags == 0) {
        return OVERWORLD_MOTION_DECISION_ACCEPTED;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_WORLD_BUSY) {
        return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_BAD_DIRECTION) {
        return OVERWORLD_MOTION_DECISION_DIRECTION;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_SIDE_BLOCKED) {
        return OVERWORLD_MOTION_DECISION_SIDE_TILE;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN) {
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_OCCUPIED) {
        return OVERWORLD_MOTION_DECISION_OCCUPIED;
    }
    if (flags & OVERWORLD_MOTION_CANDIDATE_RESERVED) {
        return OVERWORLD_MOTION_DECISION_RESERVED;
    }
    (void)callFlags;
    return OVERWORLD_MOTION_DECISION_BLOCKED;
}

static OverworldMotionDecision HostPlan(HostRequest *request)
{
    static const u8 chillDirections[] = { 0, 3, 1, 2 };
    HostCall *call;
    HostCandidate candidate;
    OverworldMotionDecision decision = OVERWORLD_MOTION_DECISION_NO_CANDIDATE;
    s16 desiredDeltaX;
    s16 desiredDeltaY;
    u8 maxStep = 0;
    u8 adjacentDirection = 0;
    u8 index;
    u8 limit;

    if (request == NULL || request->teleportPlan == NULL
        || request->plan == NULL) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    call = request->teleportPlan;
    if (call->lane == NULL || call->classify == NULL
        || call->targetMode > TARGET_CHILL
        || (call->targetMode == TARGET_DIRECTIONAL
            && (call->directions == NULL
                || call->directionCount == 0
                || call->directionCount > 8))) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    request->candidateCount = 0;
    request->selectedIndex = 0xFF;
    request->reservedReason = OVERWORLD_MOTION_DECISION_NO_CANDIDATE;
    desiredDeltaX = (s16)(call->desiredX - request->startX);
    desiredDeltaY = (s16)(call->desiredY - request->startY);
    if (call->targetMode == TARGET_ADJACENT) {
        s16 absX = desiredDeltaX < 0 ? (s16)-desiredDeltaX : desiredDeltaX;
        s16 absY = desiredDeltaY < 0 ? (s16)-desiredDeltaY : desiredDeltaY;

        maxStep = absX > absY ? (u8)absX : (u8)absY;
        if (maxStep > 6) {
            maxStep = 6;
        }
        if (maxStep == 0) {
            return decision;
        }
        adjacentDirection = DirectionFromDelta(desiredDeltaX, desiredDeltaY);
        limit = maxStep;
    } else if (call->targetMode == TARGET_DIRECTIONAL) {
        limit = (u8)(call->directionCount * 6);
    } else {
        limit = 16;
    }
    for (index = 0; index < limit; index++) {
        u8 direction;
        u8 distance;

        memset(&candidate, 0, sizeof(candidate));
        candidate.targetBaseY = request->startBaseY;
        if (call->targetMode == TARGET_ADJACENT) {
            distance = (u8)(maxStep - index);
            direction = adjacentDirection;
            candidate.targetX = (s16)(request->startX
                + MinMagnitude(desiredDeltaX, distance));
            candidate.targetY = (s16)(request->startY
                + MinMagnitude(desiredDeltaY, distance));
        } else if (call->targetMode == TARGET_DIRECTIONAL) {
            direction = call->directions[index / 6];
            distance = (u8)(6 - index % 6);
            candidate.targetX = (s16)(request->startX
                + DeltaX(direction) * distance);
            candidate.targetY = (s16)(request->startY
                + DeltaY(direction) * distance);
        } else {
            distance = (u8)(3 + ((index / 4 + call->distanceRandom) & 3));
            direction = chillDirections[
                (index % 4 + call->directionRandom) & 3];
            candidate.targetX = (s16)(request->startX
                + DeltaX(direction) * distance);
            candidate.targetY = (s16)(request->startY
                + DeltaY(direction) * distance);
        }
        candidate.direction = direction;
        candidate.distance = distance;
        candidate.targetFacing = direction;
        call->classify(call->world, &candidate);
        request->candidateCount++;
        decision = CandidateDecision(candidate.rejectionFlags, call->flags);
        if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
            u8 locomotion = call->lane->bytes[12];
            u16 duration = call->lane->bytes[23];

            if (locomotion >= 10) {
                duration = (u16)(duration * distance);
            }
            memset(request->plan, 0, sizeof(*request->plan));
            request->plan->version = OVERWORLD_MOTION_MODEL_VERSION;
            request->plan->kind = OVERWORLD_MOTION_KIND_TELEPORT;
            request->plan->facing = candidate.targetFacing;
            request->plan->fieldEpoch = request->fieldEpoch;
            request->plan->startX = request->startX;
            request->plan->startY = request->startY;
            request->plan->targetX = candidate.targetX;
            request->plan->targetY = candidate.targetY;
            request->plan->startBaseY = request->startBaseY;
            request->plan->targetBaseY = candidate.targetBaseY;
            request->plan->duration = duration;
            request->plan->direction = direction;
            request->plan->distance = distance;
            request->plan->visibilityPolicy = (u8)(2 - (locomotion & 1));
            request->plan->pauseFrames = call->lane->bytes[24];
            request->plan->pathAdvancePolicy = call->pathAdvancePolicy;
            request->selectedIndex = index;
            return decision;
        }
        request->reservedReason = (u8)decision;
        if (decision == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
            || (decision == OVERWORLD_MOTION_DECISION_RESERVED
                && (call->flags & RESERVED_STOPS_SEARCH) != 0)) {
            return decision;
        }
    }
    return decision;
}

static void Classify(void *rawWorld, HostCandidate *candidate)
{
    HostWorld *world = rawWorld;
    u8 index = world->count;

    world->candidates[index] = *candidate;
    world->count++;
    if (world->rejectBusyAt != 0 && world->rejectBusyAt == world->count) {
        candidate->rejectionFlags = OVERWORLD_MOTION_CANDIDATE_WORLD_BUSY;
    } else if (world->rejectReservedAt != 0
        && world->rejectReservedAt == world->count) {
        candidate->rejectionFlags = OVERWORLD_MOTION_CANDIDATE_RESERVED;
    } else if (world->acceptAt == 0 || world->acceptAt != world->count) {
        candidate->rejectionFlags = OVERWORLD_MOTION_CANDIDATE_BLOCKED;
    }
}

static HostRequest MakeRequest(
    HostLane *lane,
    HostCall *call,
    HostWorld *world,
    OverworldMotionPlan *plan)
{
    HostRequest request;

    memset(&request, 0, sizeof(request));
    memset(lane, 0, sizeof(*lane));
    memset(call, 0, sizeof(*call));
    memset(world, 0, sizeof(*world));
    memset(plan, 0, sizeof(*plan));
    lane->bytes[12] = 6;
    lane->bytes[23] = 4;
    lane->bytes[24] = 9;
    call->lane = lane;
    call->classify = Classify;
    call->world = world;
    request.fieldEpoch = 7;
    request.startX = 10;
    request.startY = 10;
    request.startBaseY = 0x1000;
    request.plan = plan;
    request.teleportPlan = call;
    return request;
}

static void CheckAdjacentOrder(void)
{
    HostLane lane;
    HostCall call;
    HostWorld world;
    HostRequest request;
    OverworldMotionPlan plan;
    static const s16 expectedX[] = { 15, 14, 13, 12, 11 };
    static const s16 expectedY[] = { 12, 12, 12, 12, 11 };
    u8 index;

    request = MakeRequest(&lane, &call, &world, &plan);
    call.targetMode = TARGET_ADJACENT;
    call.desiredX = 15;
    call.desiredY = 12;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_BLOCKED,
        "fully blocked adjacent search returns its last reason");
    CHECK(world.count == 5 && request.candidateCount == 5,
        "adjacent search evaluates each distance exactly once");
    for (index = 0; index < 5; index++) {
        CHECK(world.candidates[index].distance == 5 - index
                && world.candidates[index].targetX == expectedX[index]
                && world.candidates[index].targetY == expectedY[index],
            "adjacent fallback order is maxStep through one");
    }
}

static void CheckReservationPolicies(void)
{
    static const u8 east[] = { 3 };
    HostLane lane;
    HostCall call;
    HostWorld world;
    HostRequest request;
    OverworldMotionPlan plan;

    request = MakeRequest(&lane, &call, &world, &plan);
    call.targetMode = TARGET_DIRECTIONAL;
    call.directions = east;
    call.directionCount = 1;
    call.flags = RESERVED_STOPS_SEARCH;
    world.rejectReservedAt = 1;
    world.acceptAt = 2;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_RESERVED
            && world.count == 1,
        "wild reservation rejection stops candidate search");

    request = MakeRequest(&lane, &call, &world, &plan);
    call.targetMode = TARGET_DIRECTIONAL;
    call.directions = east;
    call.directionCount = 1;
    world.rejectReservedAt = 1;
    world.acceptAt = 2;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_ACCEPTED
            && world.count == 2
            && request.selectedIndex == 1
            && plan.distance == 5,
        "mounted reservation rejection continues to the next candidate");

    request = MakeRequest(&lane, &call, &world, &plan);
    call.targetMode = TARGET_DIRECTIONAL;
    call.directions = east;
    call.directionCount = 1;
    world.rejectBusyAt = 1;
    world.acceptAt = 2;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY
            && world.count == 1,
        "world-busy rejection always stops candidate search");
}

static void CheckTimingAndFailClosed(void)
{
    static const u8 east[] = { 3 };
    HostLane lane;
    HostCall call;
    HostWorld world;
    HostRequest request;
    OverworldMotionPlan plan;

    request = MakeRequest(&lane, &call, &world, &plan);
    lane.bytes[12] = 10;
    lane.bytes[23] = 4;
    call.targetMode = TARGET_DIRECTIONAL;
    call.directions = east;
    call.directionCount = 1;
    call.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;
    world.acceptAt = 1;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_ACCEPTED
            && plan.duration == 24
            && plan.visibilityPolicy == OVERWORLD_MOTION_VISIBILITY_FLICKER
            && plan.pauseFrames == 9
            && plan.pathAdvancePolicy == OVERWORLD_MOTION_PATH_ADVANCE_PLAYER,
        "planner owns per-tile timing, flicker, pause, and path policy");

    lane.bytes[12] = 9;
    lane.bytes[23] = 0;
    memset(&world, 0, sizeof(world));
    world.acceptAt = 1;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_ACCEPTED
            && plan.duration == 0
            && plan.visibilityPolicy == OVERWORLD_MOTION_VISIBILITY_HIDDEN,
        "fixed zero-time hidden Teleport remains an immediate plan");

    call.lane = NULL;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_PROFILE,
        "missing lane fails closed");
    call.lane = &lane;
    call.classify = NULL;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_PROFILE,
        "missing classifier fails closed");
    call.classify = Classify;
    call.targetMode = TARGET_DIRECTIONAL;
    call.directionCount = 0;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_PROFILE,
        "empty directional set fails closed");
    request.teleportPlan = NULL;
    CHECK(HostPlan(&request) == OVERWORLD_MOTION_DECISION_PROFILE,
        "missing planner call fails closed");
}

int main(void)
{
    CheckAdjacentOrder();
    CheckReservationPolicies();
    CheckTimingAndFailClosed();
    if (sFailures != 0) {
        return 1;
    }
    puts("overworld Teleport planner contracts verified");
    return 0;
}
