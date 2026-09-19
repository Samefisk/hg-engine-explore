#ifndef OVERWORLD_MOTION_WORLD_FIXTURE_H
#define OVERWORLD_MOTION_WORLD_FIXTURE_H

#include "overworld_motion_model.h"

#define OVERWORLD_MOTION_HOST_WORLD_MAX_WIDTH 16
#define OVERWORLD_MOTION_HOST_WORLD_MAX_HEIGHT 16
#define OVERWORLD_MOTION_HOST_ACTOR_NONE 0xFF

#define OVERWORLD_MOTION_HOST_TERRAIN_LAND  (1u << 0)
#define OVERWORLD_MOTION_HOST_TERRAIN_WATER (1u << 1)
#define OVERWORLD_MOTION_HOST_TERRAIN_LEDGE (1u << 2)

typedef struct OverworldMotionHostTile {
    s32 baseY;
    u16 terrainMask;
    u16 reservationId;
    u8 blocked;
    u8 occupant;
    u8 occupantSurface;
    u8 reservationOwner;
    u8 reservationSurface;
    u8 reserved;
} OverworldMotionHostTile;

typedef struct OverworldMotionHostWorld {
    OverworldMotionHostTile tiles[
        OVERWORLD_MOTION_HOST_WORLD_MAX_WIDTH
        * OVERWORLD_MOTION_HOST_WORLD_MAX_HEIGHT];
    u16 nextReservationId;
    u8 width;
    u8 height;
    u8 busy;
    u8 reserved;
} OverworldMotionHostWorld;

typedef struct OverworldMotionHostTarget {
    s16 x;
    s16 y;
    u8 direction;
    u8 distance;
} OverworldMotionHostTarget;

typedef struct OverworldMotionHostRequest {
    OverworldMotionIntent intent;
    OverworldMotionHostTarget targets[OVERWORLD_MOTION_MAX_CANDIDATES];
    s16 startX;
    s16 startY;
    s32 startBaseY;
    u16 allowedTerrainMask;
    u16 allowedDirectionMask;
    u8 candidateCount;
    u8 actorId;
    u8 surfaceId;
    u8 strictDiagonal;
    u8 reserved;
} OverworldMotionHostRequest;

typedef enum OverworldMotionHostTraceEventKind {
    OVERWORLD_MOTION_HOST_TRACE_INTENT_CREATED = 1,
    OVERWORLD_MOTION_HOST_TRACE_CANDIDATE_REJECTED,
    OVERWORLD_MOTION_HOST_TRACE_PLAN_SELECTED,
    OVERWORLD_MOTION_HOST_TRACE_PATH_ADVANCED,
    OVERWORLD_MOTION_HOST_TRACE_TERMINAL_COMMIT,
    OVERWORLD_MOTION_HOST_TRACE_MOTION_FINISHED,
} OverworldMotionHostTraceEventKind;

typedef struct OverworldMotionHostTraceEvent {
    u8 kind;
    u8 motionKind;
    u8 decision;
    u8 candidateIndex;
    u16 frame;
    u16 sequence;
    s16 x;
    s16 y;
} OverworldMotionHostTraceEvent;

#define OVERWORLD_MOTION_HOST_TRACE_CAPACITY 96

typedef struct OverworldMotionHostTrace {
    OverworldMotionHostTraceEvent events[OVERWORLD_MOTION_HOST_TRACE_CAPACITY];
    u16 count;
    u16 dropped;
} OverworldMotionHostTrace;

typedef struct OverworldMotionHostExecution {
    OverworldMotionCandidate candidates[OVERWORLD_MOTION_MAX_CANDIDATES];
    OverworldMotionPlan plan;
    OverworldMotionState state;
    OverworldMotionSample lastSample;
    OverworldMotionHostTrace trace;
    s32 peakHeightOffset;
    s16 logicalX;
    s16 logicalY;
    u16 movementFrames;
    u16 totalFrames;
    u16 visibleFrames;
    u16 hiddenFrames;
    u8 decision;
    u8 selectedIndex;
    u8 candidateCount;
    u8 reserved;
} OverworldMotionHostExecution;

void OverworldMotionHostWorld_Init(
    OverworldMotionHostWorld *world,
    u8 width,
    u8 height,
    u16 terrainMask);
u8 OverworldMotionHostWorld_SetTile(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u16 terrainMask,
    s32 baseY,
    u8 blocked);
u8 OverworldMotionHostWorld_SetOccupant(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 actorId);
u8 OverworldMotionHostWorld_SetSurfaceOccupant(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 surfaceId,
    u8 actorId);
u8 OverworldMotionHostWorld_SetReservation(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 actorId,
    u16 reservationId);
u8 OverworldMotionHostWorld_SetSurfaceReservation(
    OverworldMotionHostWorld *world,
    s16 x,
    s16 y,
    u8 surfaceId,
    u8 actorId,
    u16 reservationId);

OverworldMotionDecision OverworldMotionHost_Plan(
    const OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution);
OverworldMotionDecision OverworldMotionHost_Begin(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution);
void OverworldMotionHost_Cancel(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution,
    u8 reason);
OverworldMotionDecision OverworldMotionHost_Execute(
    OverworldMotionHostWorld *world,
    const OverworldMotionHostRequest *request,
    OverworldMotionHostExecution *execution);
u8 OverworldMotionHost_TraceEqual(
    const OverworldMotionHostTrace *expected,
    const OverworldMotionHostTrace *actual,
    u16 *mismatchIndex);

#endif // OVERWORLD_MOTION_WORLD_FIXTURE_H
