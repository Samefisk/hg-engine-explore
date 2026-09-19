#include "overworld_motion_world_fixture.h"

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

static OverworldMotionHostRequest MakeRequest(
    u8 kind,
    u16 duration,
    s16 startX,
    s16 startY,
    u8 actorId)
{
    OverworldMotionHostRequest request;

    memset(&request, 0, sizeof(request));
    request.intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    request.intent.kind = kind;
    request.intent.duration = duration;
    request.intent.fieldEpoch = 7;
    request.intent.facing = 3;
    request.intent.pathAdvancePolicy =
        OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    request.intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NORMAL;
    request.startX = startX;
    request.startY = startY;
    request.allowedTerrainMask = OVERWORLD_MOTION_HOST_TERRAIN_LAND;
    request.allowedDirectionMask = 0xFF;
    request.actorId = actorId;
    return request;
}

static void AddTarget(
    OverworldMotionHostRequest *request,
    s16 x,
    s16 y,
    u8 direction,
    u8 distance)
{
    OverworldMotionHostTarget *target =
        &request->targets[request->candidateCount++];

    target->x = x;
    target->y = y;
    target->direction = direction;
    target->distance = distance;
}

static void AddTrace(
    OverworldMotionHostTrace *trace,
    u8 kind,
    u8 motionKind,
    u8 decision,
    u8 candidateIndex,
    u16 frame,
    u16 sequence,
    s16 x,
    s16 y)
{
    OverworldMotionHostTraceEvent *event = &trace->events[trace->count++];

    event->kind = kind;
    event->motionKind = motionKind;
    event->decision = decision;
    event->candidateIndex = candidateIndex;
    event->frame = frame;
    event->sequence = sequence;
    event->x = x;
    event->y = y;
}

static void CheckWorldRejectionsAndCandidateOrder(void)
{
    OverworldMotionHostWorld world;
    OverworldMotionHostRequest request = MakeRequest(
        OVERWORLD_MOTION_KIND_HOP, 4, 3, 3, 1);
    OverworldMotionHostExecution execution;

    OverworldMotionHostWorld_Init(
        &world, 7, 7, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    CHECK(OverworldMotionHostWorld_SetTile(
              &world,
              4,
              3,
              OVERWORLD_MOTION_HOST_TERRAIN_LAND,
              0,
              TRUE),
        "fixture sets a blocked tile");
    CHECK(OverworldMotionHostWorld_SetTile(
              &world,
              3,
              4,
              OVERWORLD_MOTION_HOST_TERRAIN_WATER,
              0,
              FALSE),
        "fixture sets a terrain tile");
    CHECK(OverworldMotionHostWorld_SetOccupant(&world, 2, 3, 2),
        "fixture sets an occupied tile");
    CHECK(OverworldMotionHostWorld_SetReservation(&world, 3, 2, 2, 77),
        "fixture sets a reserved tile");
    request.strictDiagonal = TRUE;
    AddTarget(&request, 4, 3, 3, 1);
    AddTarget(&request, 4, 4, 7, 1);
    AddTarget(&request, 3, 4, 1, 1);
    AddTarget(&request, 2, 3, 2, 1);
    AddTarget(&request, 3, 2, 0, 1);
    AddTarget(&request, 1, 3, 2, 2);

    CHECK(OverworldMotionHost_Plan(&world, &request, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "ordered world candidates produce a plan");
    CHECK(execution.selectedIndex == 5
            && execution.plan.targetX == 1
            && execution.plan.targetY == 3,
        "planner selects the first valid ordered candidate");
    CHECK(execution.candidates[0].rejectionFlags
            == OVERWORLD_MOTION_CANDIDATE_BLOCKED,
        "blocked collision has a typed rejection");
    CHECK((execution.candidates[1].rejectionFlags
                & OVERWORLD_MOTION_CANDIDATE_SIDE_BLOCKED) != 0,
        "strict diagonal checks both cardinal side tiles");
    CHECK(execution.candidates[2].rejectionFlags
            == OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN,
        "terrain mismatch has a typed rejection");
    CHECK(execution.candidates[3].rejectionFlags
            == OVERWORLD_MOTION_CANDIDATE_OCCUPIED,
        "occupancy has a typed rejection");
    CHECK(execution.candidates[4].rejectionFlags
            == OVERWORLD_MOTION_CANDIDATE_RESERVED,
        "reservation has a typed rejection");
    CHECK(execution.trace.count == 7
            && execution.trace.events[1].decision
                == OVERWORLD_MOTION_DECISION_BLOCKED
            && execution.trace.events[2].decision
                == OVERWORLD_MOTION_DECISION_SIDE_TILE
            && execution.trace.events[3].decision
                == OVERWORLD_MOTION_DECISION_TERRAIN
            && execution.trace.events[4].decision
                == OVERWORLD_MOTION_DECISION_OCCUPIED
            && execution.trace.events[5].decision
                == OVERWORLD_MOTION_DECISION_RESERVED,
        "semantic trace keeps candidate order and rejection reasons");

    world.busy = TRUE;
    CHECK(OverworldMotionHost_Plan(&world, &request, &execution)
            == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY,
        "world busy stops planning");
    CHECK(execution.trace.count == 2
            && execution.trace.events[1].candidateIndex == 0,
        "world busy does not fall through to another candidate");
}

static void CheckWalkPathCollision(void)
{
    OverworldMotionHostWorld world;
    OverworldMotionHostRequest walk = MakeRequest(
        OVERWORLD_MOTION_KIND_WALK, 4, 1, 1, 1);
    OverworldMotionHostRequest hop;
    OverworldMotionHostExecution execution;

    OverworldMotionHostWorld_Init(
        &world, 6, 3, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    (void)OverworldMotionHostWorld_SetTile(
        &world,
        2,
        1,
        OVERWORLD_MOTION_HOST_TERRAIN_LAND,
        0,
        TRUE);
    AddTarget(&walk, 3, 1, 3, 2);
    CHECK(OverworldMotionHost_Plan(&world, &walk, &execution)
            == OVERWORLD_MOTION_DECISION_BLOCKED,
        "Walk validates every crossed tile");

    hop = walk;
    hop.intent.kind = OVERWORLD_MOTION_KIND_HOP;
    CHECK(OverworldMotionHost_Plan(&world, &hop, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Hop collision validates its landing instead of jumped tiles");
}

static void CheckSurfaceOccupancyAndReservationLifecycle(void)
{
    OverworldMotionHostWorld world;
    OverworldMotionHostRequest owner = MakeRequest(
        OVERWORLD_MOTION_KIND_HOP, 4, 1, 1, 1);
    OverworldMotionHostRequest contender = MakeRequest(
        OVERWORLD_MOTION_KIND_HOP, 4, 1, 1, 2);
    OverworldMotionHostRequest otherSurface;
    OverworldMotionHostExecution ownerExecution;
    OverworldMotionHostExecution execution;

    OverworldMotionHostWorld_Init(
        &world, 5, 4, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    AddTarget(&contender, 3, 1, 3, 2);

    CHECK(OverworldMotionHostWorld_SetSurfaceOccupant(
              &world, 3, 1, 4, 1),
        "fixture sets a typed surface occupant");
    contender.surfaceId = 4;
    CHECK(OverworldMotionHost_Plan(&world, &contender, &execution)
            == OVERWORLD_MOTION_DECISION_OCCUPIED,
        "same X/Y on the same surface is occupied");
    contender.surfaceId = 5;
    CHECK(OverworldMotionHost_Plan(&world, &contender, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "same X/Y on a different surface remains available");

    (void)OverworldMotionHostWorld_SetSurfaceOccupant(
        &world, 3, 1, 0, OVERWORLD_MOTION_HOST_ACTOR_NONE);
    contender.surfaceId = 4;
    CHECK(OverworldMotionHostWorld_SetSurfaceReservation(
              &world, 3, 1, 4, 1, 91),
        "first actor reserves the shared target");
    CHECK(OverworldMotionHost_Plan(&world, &contender, &execution)
            == OVERWORLD_MOTION_DECISION_RESERVED,
        "second actor cannot accept the same reserved target");
    CHECK(OverworldMotionHostWorld_SetSurfaceReservation(
              &world,
              3,
              1,
              4,
              OVERWORLD_MOTION_HOST_ACTOR_NONE,
              0),
        "owner release clears the shared target reservation");
    CHECK(OverworldMotionHost_Plan(&world, &contender, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "second actor can retry after reservation release");

    OverworldMotionHostWorld_Init(
        &world, 5, 4, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    owner.surfaceId = 4;
    contender.surfaceId = 4;
    otherSurface = contender;
    otherSurface.actorId = 3;
    otherSurface.surfaceId = 5;
    AddTarget(&owner, 3, 1, 3, 2);
    CHECK(OverworldMotionHost_Begin(&world, &owner, &ownerExecution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "accepted motion owns its target reservation before ticking");
    CHECK(OverworldMotionHost_Plan(&world, &contender, &execution)
            == OVERWORLD_MOTION_DECISION_RESERVED,
        "same-surface contender is serialized while the owner is active");
    CHECK(OverworldMotionHost_Plan(&world, &otherSurface, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "different-surface contender is not serialized at the same X/Y");
    OverworldMotionHost_Cancel(&world, &owner, &ownerExecution, 1);
    CHECK(ownerExecution.state.phase == OVERWORLD_MOTION_PHASE_CANCELED,
        "cancel reaches the terminal canceled phase");
    CHECK(OverworldMotionHost_Plan(&world, &contender, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "cancel releases the target for the next same-surface actor");
}

static void CheckExactWalkAndSemanticTrace(void)
{
    OverworldMotionHostWorld wildWorld;
    OverworldMotionHostWorld mountedWorld;
    OverworldMotionHostRequest wild = MakeRequest(
        OVERWORLD_MOTION_KIND_WALK, 5, 1, 1, 4);
    OverworldMotionHostRequest mounted;
    OverworldMotionHostExecution wildExecution;
    OverworldMotionHostExecution mountedExecution;
    OverworldMotionHostTrace expected;
    OverworldMotionHostTrace changed;
    const OverworldMotionHostTile *target;
    u16 mismatch = 0;

    memset(&expected, 0, sizeof(expected));
    OverworldMotionHostWorld_Init(
        &wildWorld, 5, 4, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    OverworldMotionHostWorld_Init(
        &mountedWorld, 5, 4, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    (void)OverworldMotionHostWorld_SetOccupant(&wildWorld, 1, 1, 4);
    (void)OverworldMotionHostWorld_SetOccupant(&mountedWorld, 1, 1, 4);
    AddTarget(&wild, 2, 1, 3, 1);
    mounted = wild;
    mounted.intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NO_CHAIN;

    CHECK(OverworldMotionHost_Execute(&wildWorld, &wild, &wildExecution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "exact Walk executes");
    CHECK(wildExecution.movementFrames == 5
            && wildExecution.totalFrames == 5,
        "Walk uses its exact authored frame count");
    CHECK(wildExecution.lastSample.renderX == 0x28000
            && wildExecution.lastSample.renderZ == 0x18000,
        "Walk reaches the exact render target");
    CHECK(wildExecution.state.commitSequence == 1
            && wildExecution.logicalX == 2
            && wildExecution.logicalY == 1,
        "Walk has one semantic commit at its target");
    target = &wildWorld.tiles[1 * wildWorld.width + 2];
    CHECK(target->occupant == 4
            && !target->reserved
            && wildWorld.tiles[1 * wildWorld.width + 1].occupant
                == OVERWORLD_MOTION_HOST_ACTOR_NONE,
        "Walk moves occupancy and releases its reservation");

    AddTrace(&expected,
        OVERWORLD_MOTION_HOST_TRACE_INTENT_CREATED,
        OVERWORLD_MOTION_KIND_WALK,
        OVERWORLD_MOTION_DECISION_ACCEPTED,
        0xFF, 0, 0, 1, 1);
    AddTrace(&expected,
        OVERWORLD_MOTION_HOST_TRACE_PLAN_SELECTED,
        OVERWORLD_MOTION_KIND_WALK,
        OVERWORLD_MOTION_DECISION_ACCEPTED,
        0, 0, 0, 2, 1);
    AddTrace(&expected,
        OVERWORLD_MOTION_HOST_TRACE_PATH_ADVANCED,
        OVERWORLD_MOTION_KIND_WALK,
        OVERWORLD_MOTION_DECISION_ACCEPTED,
        0, 3, 1, 2, 1);
    AddTrace(&expected,
        OVERWORLD_MOTION_HOST_TRACE_TERMINAL_COMMIT,
        OVERWORLD_MOTION_KIND_WALK,
        OVERWORLD_MOTION_DECISION_ACCEPTED,
        0, 5, 1, 2, 1);
    AddTrace(&expected,
        OVERWORLD_MOTION_HOST_TRACE_MOTION_FINISHED,
        OVERWORLD_MOTION_KIND_WALK,
        OVERWORLD_MOTION_DECISION_ACCEPTED,
        0, 5, 1, 2, 1);
    CHECK(OverworldMotionHost_TraceEqual(
              &expected, &wildExecution.trace, &mismatch),
        "Walk trace matches its independent semantic contract");

    CHECK(OverworldMotionHost_Execute(
              &mountedWorld, &mounted, &mountedExecution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "mounted-role Walk fixture executes");
    CHECK(OverworldMotionHost_TraceEqual(
              &wildExecution.trace, &mountedExecution.trace, &mismatch),
        "wild and mounted Walk have identical semantic traces");

    changed = wildExecution.trace;
    changed.events[2].x++;
    CHECK(!OverworldMotionHost_TraceEqual(
              &wildExecution.trace, &changed, &mismatch)
            && mismatch == 2,
        "trace comparison reports the first semantic difference");
}

static void CheckExactHop(void)
{
    OverworldMotionHostWorld world;
    OverworldMotionHostRequest request = MakeRequest(
        OVERWORLD_MOTION_KIND_HOP, 8, 1, 1, 5);
    OverworldMotionHostExecution execution;
    int x;

    OverworldMotionHostWorld_Init(
        &world, 8, 3, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    (void)OverworldMotionHostWorld_SetOccupant(&world, 1, 1, 5);
    for (x = 2; x <= 4; x++) {
        (void)OverworldMotionHostWorld_SetTile(
            &world,
            (s16)x,
            1,
            OVERWORLD_MOTION_HOST_TERRAIN_LAND,
            0,
            TRUE);
    }
    request.intent.arcHeightQ4 = 32;
    request.intent.pauseFrames = 2;
    AddTarget(&request, 5, 1, 3, 4);

    CHECK(OverworldMotionHost_Execute(&world, &request, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Hop executes over blocked intermediate tiles");
    CHECK(execution.movementFrames == 8
            && execution.totalFrames == 10,
        "Hop travel and landing pause use exact frames");
    CHECK(execution.peakHeightOffset == 0x20000,
        "Hop uses the exact shared arc");
    CHECK(execution.state.commitSequence == 1
            && execution.logicalX == 5
            && execution.logicalY == 1,
        "Hop has one terminal commit");
    CHECK(execution.trace.count == 8
            && execution.trace.events[2].frame == 1
            && execution.trace.events[3].frame == 3
            && execution.trace.events[4].frame == 5
            && execution.trace.events[5].frame == 7,
        "Hop publishes every ordered path boundary once");
    CHECK(world.tiles[1 * world.width + 5].occupant == 5
            && !world.tiles[1 * world.width + 5].reserved,
        "Hop commits occupancy and releases its landing reservation");
    for (x = 2; x <= 4; x++) {
        CHECK(world.tiles[1 * world.width + x].blocked,
            "Hop does not alter jumped collision tiles");
    }
}

static void CheckExactTeleportAndReservationReuse(void)
{
    OverworldMotionHostWorld world;
    OverworldMotionHostRequest request = MakeRequest(
        OVERWORLD_MOTION_KIND_TELEPORT, 6, 1, 1, 7);
    OverworldMotionHostExecution execution;

    OverworldMotionHostWorld_Init(
        &world, 8, 3, OVERWORLD_MOTION_HOST_TERRAIN_LAND);
    (void)OverworldMotionHostWorld_SetOccupant(&world, 1, 1, 7);
    (void)OverworldMotionHostWorld_SetTile(
        &world,
        6,
        1,
        OVERWORLD_MOTION_HOST_TERRAIN_WATER,
        0x4000,
        FALSE);
    (void)OverworldMotionHostWorld_SetReservation(&world, 6, 1, 7, 42);
    request.allowedTerrainMask = OVERWORLD_MOTION_HOST_TERRAIN_WATER;
    request.intent.visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_HIDDEN;
    request.intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;
    AddTarget(&request, 6, 1, 3, 5);

    CHECK(OverworldMotionHost_Execute(&world, &request, &execution)
            == OVERWORLD_MOTION_DECISION_ACCEPTED,
        "Teleport accepts its actor's existing reservation");
    CHECK(execution.plan.reservationId == 42,
        "Teleport preserves the reservation identity");
    CHECK(execution.movementFrames == 6
            && execution.totalFrames == 6
            && execution.hiddenFrames == 6
            && execution.visibleFrames == 0,
        "Teleport time and hidden visibility are exact");
    CHECK(execution.lastSample.baseY == 0x4000
            && execution.lastSample.renderX == 0x68000,
        "Teleport reaches the target surface and render position");
    CHECK(execution.state.commitSequence == 1
            && world.tiles[1 * world.width + 6].occupant == 7
            && !world.tiles[1 * world.width + 6].reserved,
        "Teleport commits once and releases its reservation");

    OverworldMotionHostWorld_Init(
        &world, 8, 3, OVERWORLD_MOTION_HOST_TERRAIN_WATER);
    (void)OverworldMotionHostWorld_SetReservation(&world, 6, 1, 9, 43);
    CHECK(OverworldMotionHost_Plan(&world, &request, &execution)
            == OVERWORLD_MOTION_DECISION_RESERVED,
        "another actor's reservation rejects Teleport");
}

int main(void)
{
    CheckWorldRejectionsAndCandidateOrder();
    CheckWalkPathCollision();
    CheckSurfaceOccupancyAndReservationLifecycle();
    CheckExactWalkAndSemanticTrace();
    CheckExactHop();
    CheckExactTeleportAndReservationReuse();
    if (sFailures != 0) {
        return 1;
    }
    puts("overworld motion host world contracts verified");
    return 0;
}
