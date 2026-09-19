#include "overworld_motion_world_fixture.h"

#include <string.h>

static u8 OverworldMotionHost_InBounds(
    const OverworldMotionHostWorld *world,
    s16 x,
    s16 y)
{
    return world != NULL
        && x >= 0
        && y >= 0
        && x < world->width
        && y < world->height;
}

static OverworldMotionHostTile *OverworldMotionHost_Tile(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y)
{
    if (!OverworldMotionHost_InBounds(world, x, y)) {
        return NULL;
    }
    return &world->tiles[y * world->width + x];
}

static const OverworldMotionHostTile *OverworldMotionHost_ConstTile(
    const OverworldMotionHostWorld *world,
    s16 x,
    s16 y)
{
    if (!OverworldMotionHost_InBounds(world, x, y)) {
        return NULL;
    }
    return &world->tiles[y * world->width + x];
}

void OverworldMotionHostWorld_Init(
    OverworldMotionHostWorld *world,
    u8 width,
    u8 height,
    u16 terrainMask)
{
    u16 x;
    u16 y;

    if (world == NULL) {
        return;
    }
    memset(world, 0, sizeof(*world));
    if (width > OVERWORLD_MOTION_HOST_WORLD_MAX_WIDTH) {
        width = OVERWORLD_MOTION_HOST_WORLD_MAX_WIDTH;
    }
    if (height > OVERWORLD_MOTION_HOST_WORLD_MAX_HEIGHT) {
        height = OVERWORLD_MOTION_HOST_WORLD_MAX_HEIGHT;
    }
    world->width = width;
    world->height = height;
    world->nextReservationId = 1;
    for (y = 0; y < height; y++) {
        for (x = 0; x < width; x++) {
            OverworldMotionHostTile *tile =
                &world->tiles[y * width + x];

            tile->terrainMask = terrainMask;
            tile->occupant = OVERWORLD_MOTION_HOST_ACTOR_NONE;
            tile->reservationOwner = OVERWORLD_MOTION_HOST_ACTOR_NONE;
        }
    }
}

u8 OverworldMotionHostWorld_SetTile(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u16 terrainMask,
    s32 baseY,
    u8 blocked)
{
    OverworldMotionHostTile *tile = OverworldMotionHost_Tile(world, x, y);

    if (tile == NULL) {
        return FALSE;
    }
    tile->terrainMask = terrainMask;
    tile->baseY = baseY;
    tile->blocked = blocked != 0;
    return TRUE;
}

u8 OverworldMotionHostWorld_SetOccupant(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 actorId)
{
    return OverworldMotionHostWorld_SetSurfaceOccupant(
        world, x, y, 0, actorId);
}

u8 OverworldMotionHostWorld_SetSurfaceOccupant(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 surfaceId,
    u8 actorId)
{
    OverworldMotionHostTile *tile = OverworldMotionHost_Tile(world, x, y);

    if (tile == NULL) {
        return FALSE;
    }
    tile->occupant = actorId;
    tile->occupantSurface = surfaceId;
    return TRUE;
}

u8 OverworldMotionHostWorld_SetReservation(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 actorId,
    u16 reservationId)
{
    return OverworldMotionHostWorld_SetSurfaceReservation(
        world, x, y, 0, actorId, reservationId);
}

u8 OverworldMotionHostWorld_SetSurfaceReservation(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 surfaceId,
    u8 actorId,
    u16 reservationId)
{
    OverworldMotionHostTile *tile = OverworldMotionHost_Tile(world, x, y);

    if (tile == NULL) {
        return FALSE;
    }
    tile->reserved = reservationId != 0;
    tile->reservationOwner = tile->reserved
        ? actorId
        : OVERWORLD_MOTION_HOST_ACTOR_NONE;
    tile->reservationSurface = surfaceId;
    tile->reservationId = reservationId;
    return TRUE;
}

static void OverworldMotionHost_Trace(
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
    OverworldMotionHostTraceEvent *event;

    if (trace->count >= OVERWORLD_MOTION_HOST_TRACE_CAPACITY) {
        trace->dropped++;
        return;
    }
    event = &trace->events[trace->count++];
    event->kind = kind;
    event->motionKind = motionKind;
    event->decision = decision;
    event->candidateIndex = candidateIndex;
    event->frame = frame;
    event->sequence = sequence;
    event->x = x;
    event->y = y;
}

static u16 OverworldMotionHost_TileRejection(
    const OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    s16 x,
    s16 y)
{
    const OverworldMotionHostTile *tile =
        OverworldMotionHost_ConstTile(world, x, y);
    u16 flags = 0;

    if (tile == NULL || tile->blocked) {
        return OVERWORLD_MOTION_CANDIDATE_BLOCKED;
    }
    if ((tile->terrainMask & request->allowedTerrainMask) == 0) {
        flags |= OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN;
    }
    if (tile->occupant != OVERWORLD_MOTION_HOST_ACTOR_NONE
        && tile->occupant != request->actorId
        && tile->occupantSurface == request->surfaceId) {
        flags |= OVERWORLD_MOTION_CANDIDATE_OCCUPIED;
    }
    if (tile->reserved
        && tile->reservationOwner != request->actorId
        && tile->reservationSurface == request->surfaceId) {
        flags |= OVERWORLD_MOTION_CANDIDATE_RESERVED;
    }
    return flags;
}

static u8 OverworldMotionHost_IsDiagonal(
    const OverworldMotionHostRequest *request,
    const OverworldMotionHostTarget *target)
{
    return target->x != request->startX
        && target->y != request->startY;
}

static u16 OverworldMotionHost_PathRejection(
    const OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    const OverworldMotionHostTarget *target)
{
    OverworldMotionPlan path;
    s16 x;
    s16 y;
    u16 index;
    u16 flags = 0;
    u16 limit = (u16)world->width + world->height;

    memset(&path, 0, sizeof(path));
    path.startX = request->startX;
    path.startY = request->startY;
    path.targetX = target->x;
    path.targetY = target->y;
    for (index = 1; index <= limit; index++) {
        if (!OverworldMotion_GetPathAdvanceTile(&path, index, &x, &y)) {
            break;
        }
        flags |= OverworldMotionHost_TileRejection(
            world, request, x, y);
    }
    return flags;
}

static u16 OverworldMotionHost_CandidateFlags(
    const OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    const OverworldMotionHostTarget *target)
{
    u16 flags;
    s16 xStep;
    s16 yStep;

    if (world->busy) {
        return OVERWORLD_MOTION_CANDIDATE_WORLD_BUSY;
    }
    flags = request->intent.kind == OVERWORLD_MOTION_KIND_WALK
        ? OverworldMotionHost_PathRejection(world, request, target)
        : OverworldMotionHost_TileRejection(
            world, request, target->x, target->y);
    if (target->direction >= 8
        || (request->allowedDirectionMask != 0
            && (request->allowedDirectionMask
                    & (1u << target->direction)) == 0)) {
        flags |= OVERWORLD_MOTION_CANDIDATE_BAD_DIRECTION;
    }
    if (request->strictDiagonal
        && OverworldMotionHost_IsDiagonal(request, target)) {
        xStep = target->x > request->startX ? 1 : -1;
        yStep = target->y > request->startY ? 1 : -1;
        if (OverworldMotionHost_TileRejection(
                world,
                request,
                request->startX + xStep,
                request->startY) != 0
            || OverworldMotionHost_TileRejection(
                world,
                request,
                request->startX,
                request->startY + yStep) != 0) {
            flags |= OVERWORLD_MOTION_CANDIDATE_SIDE_BLOCKED;
        }
    }
    return flags;
}

static u8 OverworldMotionHost_Distance(
    const OverworldMotionHostRequest *request,
    const OverworldMotionHostTarget *target)
{
    s16 xDistance = target->x - request->startX;
    s16 yDistance = target->y - request->startY;

    if (xDistance < 0) {
        xDistance = -xDistance;
    }
    if (yDistance < 0) {
        yDistance = -yDistance;
    }
    return (u8)(xDistance > yDistance ? xDistance : yDistance);
}

static OverworldMotionDecision OverworldMotionHost_CandidateDecision(u16 flags)
{
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
    if (flags & OVERWORLD_MOTION_CANDIDATE_BLOCKED) {
        return OVERWORLD_MOTION_DECISION_BLOCKED;
    }
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static void OverworldMotionHost_BuildCandidates(
    const OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution)
{
    u8 index;

    execution->candidateCount = request->candidateCount;
    for (index = 0; index < request->candidateCount; index++) {
        const OverworldMotionHostTarget *target = &request->targets[index];
        const OverworldMotionHostTile *tile =
            OverworldMotionHost_ConstTile(world, target->x, target->y);
        OverworldMotionCandidate *candidate = &execution->candidates[index];

        memset(candidate, 0, sizeof(*candidate));
        candidate->targetX = target->x;
        candidate->targetY = target->y;
        candidate->targetBaseY = tile != NULL ? tile->baseY : 0;
        candidate->rejectionFlags = OverworldMotionHost_CandidateFlags(
            world, request, target);
        candidate->direction = target->direction;
        candidate->distance = target->distance != 0
            ? target->distance
            : OverworldMotionHost_Distance(request, target);
        if (tile != NULL
            && tile->reserved
            && tile->reservationOwner == request->actorId) {
            candidate->reservationId = tile->reservationId;
        }
    }
}

static void OverworldMotionHost_TracePlan(
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution)
{
    u8 index;
    u8 intentDecision = execution->decision == OVERWORLD_MOTION_DECISION_PROFILE
        ? OVERWORLD_MOTION_DECISION_PROFILE
        : OVERWORLD_MOTION_DECISION_ACCEPTED;

    OverworldMotionHost_Trace(
        &execution->trace,
        OVERWORLD_MOTION_HOST_TRACE_INTENT_CREATED,
        request->intent.kind,
        intentDecision,
        0xFF,
        0,
        0,
        request->startX,
        request->startY);
    if (execution->decision == OVERWORLD_MOTION_DECISION_PROFILE) {
        return;
    }
    for (index = 0; index < request->candidateCount; index++) {
        OverworldMotionDecision decision = OverworldMotionHost_CandidateDecision(
            execution->candidates[index].rejectionFlags);

        if (index == execution->selectedIndex) {
            break;
        }
        OverworldMotionHost_Trace(
            &execution->trace,
            OVERWORLD_MOTION_HOST_TRACE_CANDIDATE_REJECTED,
            request->intent.kind,
            decision,
            index,
            0,
            0,
            request->targets[index].x,
            request->targets[index].y);
        if (decision == OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY) {
            break;
        }
    }
    if (execution->decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        OverworldMotionHost_Trace(
            &execution->trace,
            OVERWORLD_MOTION_HOST_TRACE_PLAN_SELECTED,
            request->intent.kind,
            execution->decision,
            execution->selectedIndex,
            0,
            0,
            execution->plan.targetX,
            execution->plan.targetY);
    }
}

OverworldMotionDecision OverworldMotionHost_Plan(
    const OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution)
{
    if (world == NULL
        || request == NULL
        || execution == NULL
        || request->candidateCount == 0
        || request->candidateCount > OVERWORLD_MOTION_MAX_CANDIDATES
        || !OverworldMotionHost_InBounds(
            world, request->startX, request->startY)) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    memset(execution, 0, sizeof(*execution));
    execution->selectedIndex = 0xFF;
    execution->logicalX = request->startX;
    execution->logicalY = request->startY;
    OverworldMotionHost_BuildCandidates(world, request, execution);
    execution->decision = OverworldMotion_SelectPlan(
        &request->intent,
        request->startX,
        request->startY,
        request->startBaseY,
        execution->candidates,
        request->candidateCount,
        &execution->plan,
        &execution->selectedIndex);
    OverworldMotionHost_TracePlan(request, execution);
    return (OverworldMotionDecision)execution->decision;
}

static u16 OverworldMotionHost_ReserveTarget(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionPlan *plan)
{
    OverworldMotionHostTile *tile = OverworldMotionHost_Tile(
        world, plan->targetX, plan->targetY);

    if (tile == NULL) {
        return 0;
    }
    if (plan->reservationId == 0) {
        plan->reservationId = world->nextReservationId++;
        if (world->nextReservationId == 0) {
            world->nextReservationId++;
        }
    }
    tile->reserved = TRUE;
    tile->reservationOwner = request->actorId;
    tile->reservationSurface = request->surfaceId;
    tile->reservationId = plan->reservationId;
    return plan->reservationId;
}

static void OverworldMotionHost_ReleaseTarget(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    const OverworldMotionPlan *plan)
{
    OverworldMotionHostTile *tile = OverworldMotionHost_Tile(
        world, plan->targetX, plan->targetY);

    if (tile != NULL
        && tile->reserved
        && tile->reservationOwner == request->actorId
        && tile->reservationSurface == request->surfaceId
        && tile->reservationId == plan->reservationId) {
        tile->reserved = FALSE;
        tile->reservationOwner = OVERWORLD_MOTION_HOST_ACTOR_NONE;
        tile->reservationSurface = 0;
        tile->reservationId = 0;
    }
}

static void OverworldMotionHost_MoveOccupant(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    s16 fromX,
    s16 fromY,
    s16 toX,
    s16 toY)
{
    OverworldMotionHostTile *from = OverworldMotionHost_Tile(
        world, fromX, fromY);
    OverworldMotionHostTile *to = OverworldMotionHost_Tile(
        world, toX, toY);

    if (from != NULL && from->occupant == request->actorId) {
        from->occupant = OVERWORLD_MOTION_HOST_ACTOR_NONE;
    }
    if (to != NULL) {
        to->occupant = request->actorId;
        to->occupantSurface = request->surfaceId;
    }
}

static void OverworldMotionHost_ApplyPathAdvances(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution,
    const OverworldMotionSample *sample)
{
    u16 advance;

    if ((sample->flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) == 0) {
        return;
    }
    for (advance = sample->firstPathAdvance;
         advance <= sample->lastPathAdvance;
         advance++) {
        s16 x;
        s16 y;

        if (!OverworldMotion_GetPathAdvanceTile(
                &execution->plan, advance, &x, &y)) {
            continue;
        }
        if (request->intent.kind == OVERWORLD_MOTION_KIND_WALK) {
            OverworldMotionHost_MoveOccupant(
                world,
                request,
                execution->logicalX,
                execution->logicalY,
                x,
                y);
        }
        execution->logicalX = x;
        execution->logicalY = y;
        OverworldMotionHost_Trace(
            &execution->trace,
            OVERWORLD_MOTION_HOST_TRACE_PATH_ADVANCED,
            request->intent.kind,
            OVERWORLD_MOTION_DECISION_ACCEPTED,
            execution->selectedIndex,
            execution->totalFrames,
            advance,
            x,
            y);
    }
}

OverworldMotionDecision OverworldMotionHost_Begin(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution)
{
    OverworldMotionDecision decision = OverworldMotionHost_Plan(
        world, request, execution);

    if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return decision;
    }
    if (OverworldMotionHost_ReserveTarget(world, request, &execution->plan)
        == 0) {
        execution->decision = OVERWORLD_MOTION_DECISION_RESERVED;
        return OVERWORLD_MOTION_DECISION_RESERVED;
    }
    decision = OverworldMotion_Begin(&execution->state, &execution->plan);
    if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        OverworldMotionHost_ReleaseTarget(world, request, &execution->plan);
        execution->decision = decision;
        return decision;
    }
    execution->decision = decision;
    return decision;
}

void OverworldMotionHost_Cancel(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution,
    u8 reason)
{
    if (world == NULL || request == NULL || execution == NULL) {
        return;
    }
    OverworldMotion_Cancel(&execution->state, reason);
    OverworldMotionHost_ReleaseTarget(world, request, &execution->plan);
}

OverworldMotionDecision OverworldMotionHost_Execute(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution)
{
    OverworldMotionDecision decision = OverworldMotionHost_Begin(
        world, request, execution);
    u32 guard = 0;

    if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return decision;
    }
    while (execution->state.phase != OVERWORLD_MOTION_PHASE_IDLE
        && execution->state.phase != OVERWORLD_MOTION_PHASE_CANCELED
        && guard++ < 0x20000u) {
        u16 flags;

        execution->totalFrames++;
        flags = OverworldMotion_Tick(
            &execution->state,
            request->intent.fieldEpoch,
            &execution->lastSample);
        if ((flags & OVERWORLD_MOTION_TICK_MOVED) != 0) {
            execution->movementFrames++;
            if (execution->lastSample.heightOffset
                > execution->peakHeightOffset) {
                execution->peakHeightOffset =
                    execution->lastSample.heightOffset;
            }
            if (execution->lastSample.visible) {
                execution->visibleFrames++;
            } else {
                execution->hiddenFrames++;
            }
        }
        OverworldMotionHost_ApplyPathAdvances(
            world, request, execution, &execution->lastSample);
        if (execution->state.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
            decision = OverworldMotion_AcknowledgeCommit(
                &execution->state, request->intent.fieldEpoch);
            if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
                OverworldMotionHost_ReleaseTarget(
                    world, request, &execution->plan);
                break;
            }
            if (request->intent.kind != OVERWORLD_MOTION_KIND_WALK) {
                OverworldMotionHost_MoveOccupant(
                    world,
                    request,
                    request->startX,
                    request->startY,
                    execution->plan.targetX,
                    execution->plan.targetY);
            }
            execution->logicalX = execution->plan.targetX;
            execution->logicalY = execution->plan.targetY;
            OverworldMotionHost_ReleaseTarget(
                world, request, &execution->plan);
            OverworldMotionHost_Trace(
                &execution->trace,
                OVERWORLD_MOTION_HOST_TRACE_TERMINAL_COMMIT,
                request->intent.kind,
                decision,
                execution->selectedIndex,
                execution->totalFrames,
                execution->state.commitSequence,
                execution->logicalX,
                execution->logicalY);
            if (execution->state.phase == OVERWORLD_MOTION_PHASE_IDLE) {
                OverworldMotionHost_Trace(
                    &execution->trace,
                    OVERWORLD_MOTION_HOST_TRACE_MOTION_FINISHED,
                    request->intent.kind,
                    decision,
                    execution->selectedIndex,
                    execution->totalFrames,
                    execution->state.commitSequence,
                    execution->logicalX,
                    execution->logicalY);
            }
        } else if ((flags & OVERWORLD_MOTION_TICK_FINISHED) != 0) {
            OverworldMotionHost_Trace(
                &execution->trace,
                OVERWORLD_MOTION_HOST_TRACE_MOTION_FINISHED,
                request->intent.kind,
                OVERWORLD_MOTION_DECISION_ACCEPTED,
                execution->selectedIndex,
                execution->totalFrames,
                execution->state.commitSequence,
                execution->logicalX,
                execution->logicalY);
        }
    }
    if (execution->state.phase != OVERWORLD_MOTION_PHASE_IDLE
        && execution->state.phase != OVERWORLD_MOTION_PHASE_CANCELED
        && decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        OverworldMotionHost_Cancel(world, request, execution, 1);
        execution->decision = OVERWORLD_MOTION_DECISION_CONTEXT_LOST;
        return OVERWORLD_MOTION_DECISION_CONTEXT_LOST;
    }
    execution->decision = decision;
    return decision;
}

u8 OverworldMotionHost_TraceEqual(
    const OverworldMotionHostTrace *expected,
    const OverworldMotionHostTrace *actual,
    u16 *mismatchIndex)
{
    u16 index;
    u16 count;

    if (expected == NULL || actual == NULL) {
        return FALSE;
    }
    count = expected->count < actual->count
        ? expected->count
        : actual->count;
    for (index = 0; index < count; index++) {
        if (memcmp(
                &expected->events[index],
                &actual->events[index],
                sizeof(expected->events[index])) != 0) {
            if (mismatchIndex != NULL) {
                *mismatchIndex = index;
            }
            return FALSE;
        }
    }
    if (expected->count != actual->count
        || expected->dropped != actual->dropped) {
        if (mismatchIndex != NULL) {
            *mismatchIndex = count;
        }
        return FALSE;
    }
    if (mismatchIndex != NULL) {
        *mismatchIndex = 0xFFFF;
    }
    return TRUE;
}
