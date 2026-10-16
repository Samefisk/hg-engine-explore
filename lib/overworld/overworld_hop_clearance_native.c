#include "../../include/overworld_hop_clearance_native.h"
#include "../../include/overworld_query_code_addon.h"
#include "../../include/overworld_wild_occupancy.h"
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
#include "../../include/map_events_internal.h"
#endif
#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
#include <string.h>
#endif
extern const OverworldQueryCodeAddonEntry gOverworldQueryCodeAddonEntry;
#define OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32 (1 << FX32_SHIFT)
#define HOP_CLEARANCE_CODE __attribute__((noinline, optimize("Os")))
#pragma GCC optimize("no-if-conversion", "no-tree-loop-optimize", "no-tree-ter")

static inline s32 OverworldActorHopPlanner_CallArc(
    s32 (*function)(u16, u16, u8), u32 numerator, u32 denominator)
{
#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
    return function(numerator, denominator, 1);
#else
    register u32 input0 __asm__("r0") = numerator;
    register u32 input1 __asm__("r1") = denominator;
    register u32 input2 __asm__("r2") = 1;
    register s32 (*input3)(u16, u16, u8) __asm__("r3") = function;
    /* Every argument is already in its declared range. Invoke the exact
     * native u16/u16/u8 register ABI without duplicate zero extension. */
    __asm__ volatile("blx r3" : "+r"(input0), "+r"(input1), "+r"(input2), "+r"(input3)
        : : "r12", "lr", "cc", "memory");
    return input0;
#endif
}


static BOOL HOP_CLEARANCE_CODE
OverworldActorHopPlanner_IsJump(const OverworldActorHopPlanCall *call)
{
    return call->operation == OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY
        && (call->spotState & (OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM
            | OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY)) == 0
        && OW_WILD_BEHAVIOR_SKID_BOOLEAN(call->lane->hopAllowVerticalObstacles)
        && call->lane->hopMinDistance == call->lane->hopMaxDistance;
}

/* Height of one crossed native cell for a Jump, or zero when it is open. */
static u32 HOP_CLEARANCE_CODE
OverworldActorHopPlanner_JumpObstacleHeight(const OverworldActorHopPlanCall *call,
    const OverworldHopClearanceNativeOps *ops, int x, int y)
{
    FieldSystem *fieldSystem = call->fieldSystem;
    u32 ledge;
    s32 groundY;

    if ((x | y) < 0) {
        return OVERWORLD_JUMP_WALL_HEIGHT;
    }
    /* A ledge tile also carries stock collision, so its rule comes first.
     * Ledges 56..59 face east, west, north and south. Below Both, only a
     * cardinal Jump passes, and only downhill. */
    ledge = ops->tileBehavior(fieldSystem, x, y) - 56;
    if (ledge <= 3) {
        int dx = call->targetX - call->startX;
        int dy = call->targetY - call->startY;

        if (call->lane->jumpLevel < 2
            && ledge != (dy == 0 ? (u32)(dx < 0)
                : dx != 0 ? 4u : 2u + (dy > 0))) {
            return OVERWORLD_JUMP_WALL_HEIGHT;
        }
    } else if (ops->blocked(fieldSystem, x, y)) {
        /* A cliff face has no native ground. A downhill Jump falls past it,
         * so it is open; a grounded tree or wall stays a wall. */
        return call->targetBaseY < call->startBaseY
                && !ops->resolveBaseYAt(fieldSystem, NULL,
                    call->startBaseY, 0, x, y, &groundY)
            ? 0 : OVERWORLD_JUMP_WALL_HEIGHT;
    }
    return ops->occupied(fieldSystem, call->object, NULL,
            x, y, 0, OVERWORLD_WILD_OCCUPANCY_OBJECTS)
        ? OVERWORLD_JUMP_OBJECT_HEIGHT : 0;
}

static OverworldMotionDecision HOP_CLEARANCE_CODE
OverworldActorHopPlanner_ClearanceFinish(
    OverworldActorHopClearanceCursor *cursor,
    OverworldMotionDecision decision)
{
    cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_DONE;
    cursor->decision = decision;
    return decision;
}

static OverworldMotionDecision HOP_CLEARANCE_CODE
    __attribute__((used))
OverworldActorHopPlanner_ClearanceBegin(OverworldActorHopPlanCall *request,
    const OverworldHopClearanceNativeOps *ops)
{
    OverworldActorHopClearanceCursor *cursor = request->clearanceCursor;
    const OverworldActorHopPlanCall *call;
    const OverworldWildBehaviorProfileData *lane;
    u32 trajectory;
    u32 totalFrames;
    u32 arcHeightQ4;
    BOOL slam;
    BOOL spawnEntry;

    if (cursor == NULL || cursor->version != OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION
        || cursor->size != sizeof(*cursor) || cursor->input == NULL
        || cursor->reserved != 0
        || ((cursor->playable == NULL) != (cursor->behavior == NULL))) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    call = cursor->input;
    lane = call->lane;
    cursor->readsUsed = 0;
    cursor->hasSurface = 0;
    cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_DONE;
    cursor->decision = OVERWORLD_MOTION_DECISION_PROFILE;
    if (call->operation != OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY
        && call->operation != OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (lane == NULL || call->fieldSystem == NULL || call->distance == 0) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    ops->geometryInit(&cursor->geometry, &call->startX);
    if ((cursor->geometry.absDx | cursor->geometry.absDy) == 0
        || cursor->geometry.absDx > call->distance
        || cursor->geometry.absDy > call->distance) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    slam = (call->spotState & OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM) != 0;
    spawnEntry = (call->spotState & OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY) != 0;
    if (slam) {
        u32 rise = call->arcRiseFrames;
        u32 hang = call->arcHangFrames;
        trajectory = call->trajectory;
        arcHeightQ4 = trajectory >> 16;
        if (call->operation != OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY
            || arcHeightQ4 > 255
            || !ops->slamPhaseCheck(OVERWORLD_MOTION_KIND_HOP,
                arcHeightQ4, rise, (s32)(trajectory & 0xFFFF) - hang)) {
            return OVERWORLD_MOTION_DECISION_PROFILE;
        }
        totalFrames = rise;
    } else if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY) {
        trajectory = call->trajectory;
        totalFrames = 2 * call->distance;
        arcHeightQ4 = 0;
    } else {
        trajectory = ops->calculateTrajectory(
            spawnEntry ? lane->spawnHopTime : lane->hopTime,
            call->distance, call->targetBaseY - call->startBaseY,
            lane->hopElevationTimeScale
                | ((u16)lane->hopElevationArcScale << 8));
        totalFrames = trajectory & 0xFFFF;
        arcHeightQ4 = trajectory >> 16;
    }
    cursor->trajectory = (arcHeightQ4 << 16) | (trajectory & 0xFFFF);
    cursor->totalFrames = totalFrames;
    if (!slam && totalFrames < 2) {
        request->trajectory = cursor->trajectory;
        return OverworldActorHopPlanner_ClearanceFinish(cursor,
            OVERWORLD_MOTION_DECISION_ACCEPTED);
    }
    cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_NEXT;
    cursor->decision = OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
}

static OverworldMotionDecision HOP_CLEARANCE_CODE
    __attribute__((used, optimize("no-ivopts")))
OverworldActorHopPlanner_ClearanceStep(OverworldActorHopPlanCall *request,
    const OverworldHopClearanceNativeOps *ops)
{
    OverworldActorHopClearanceCursor *cursor = request->clearanceCursor;
    const OverworldActorHopPlanCall *call;
    const OverworldWildBehaviorProfileData *lane;
    OverworldActorHopGeometry *geometry;
    BOOL slam;
    BOOL spawnEntry;
    u32 totalFrames;
    u32 arcHeightQ4;
    s32 obstacleBaseY;
    u32 edge;
    typedef s32 (*OverworldUnitArcFunc)(u16, u16, u8);
    OverworldUnitArcFunc unitArcFn;

    if (cursor == NULL || cursor->version != OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION
        || cursor->size != sizeof(*cursor) || cursor->input == NULL
        || cursor->reserved != 0 || cursor->hasSurface > 1
        || cursor->readBudget > OVERWORLD_ACTOR_HOP_CLEARANCE_MAX_READS
        || cursor->phase < OVERWORLD_ACTOR_HOP_CLEARANCE_NEXT
        || cursor->phase > OVERWORLD_ACTOR_HOP_CLEARANCE_DONE) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    cursor->readsUsed = 0;
    call = cursor->input;
    lane = call->lane;
    geometry = &cursor->geometry;
    slam = (call->spotState & OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM) != 0;
    spawnEntry = (call->spotState & OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY) != 0;
    totalFrames = cursor->totalFrames;
    arcHeightQ4 = cursor->trajectory >> 16;
    unitArcFn = slam ? ops->slamArc
        : ops->calculateArc;

    for (;;) {
        if (cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_DONE) {
            if (cursor->decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
                request->trajectory = cursor->trajectory;
            }
            return cursor->decision;
        }
        if (cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_NEXT) {
            ops->nextCell(geometry);
            /* The destination support stays with the landing owner. */
            if (geometry->tileX == call->targetX && geometry->tileY == call->targetY) {
                cursor->trajectory = (arcHeightQ4 << 16) | (cursor->trajectory & 0xFFFF);
                OverworldActorHopPlanner_ClearanceFinish(cursor,
                    OVERWORLD_MOTION_DECISION_ACCEPTED);
                continue;
            }
            cursor->phase = cursor->playable != NULL
                ? OVERWORLD_ACTOR_HOP_CLEARANCE_PLAYABLE
                : OVERWORLD_ACTOR_HOP_CLEARANCE_SURFACE;
        }
        /* Reduce uses only saved scalar values. Every phase which reads the
         * world reserves its complete read cost before its callback, and saves the next phase
         * before a yield. No completed query is repeated on the next STEP. */
        if (cursor->phase != OVERWORLD_ACTOR_HOP_CLEARANCE_REDUCE) {
            u8 cost = cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT
                ? OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT_READS : 1;
            if (cursor->readBudget < cost) {
                return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
            }
            cursor->readBudget -= cost;
            cursor->readsUsed += cost;
        }
        if (cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_PLAYABLE) {
            if (!cursor->playable(call->fieldSystem, geometry->tileX, geometry->tileY)) {
                return OverworldActorHopPlanner_ClearanceFinish(cursor,
                    OVERWORLD_MOTION_DECISION_BLOCKED);
            }
            cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_BEHAVIOR;
            continue;
        }
        if (cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_BEHAVIOR) {
            if (cursor->behavior(call->fieldSystem, geometry->tileX, geometry->tileY) == 0xFF) {
                return OverworldActorHopPlanner_ClearanceFinish(cursor,
                    OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY);
            }
            cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_SURFACE;
            continue;
        }
        if (cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_SURFACE) {
            cursor->hasSurface = ops->querySurface(
                call->fieldSystem, call->surfaceCatalog,
                geometry->tileX, geometry->tileY, &cursor->hit) != 0;
            if (!spawnEntry && (!cursor->hasSurface
                    || cursor->hit.surfaceId == OW_WILD_SURFACE_ID_NATIVE_GROUND)) {
                u32 height = OverworldActorHopPlanner_IsJump(call)
                    ? OverworldActorHopPlanner_JumpObstacleHeight(
                        call, ops, geometry->tileX, geometry->tileY)
                    : 0;

                cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_NEXT;
                if (height != 0) {
                    /* A native obstacle stands in its cell centre, so the
                     * arc is sampled there: timing decides the clearance.
                     * Jump lines are cardinal or 45 degrees, so the cell's
                     * entry and exit fractions share one denominator. */
                    u32 sample = ops->unsignedDivide(totalFrames
                        * ((geometry->entryNumerator + (geometry->error <= 0
                            ? geometry->xBoundary : geometry->yBoundary)) >> 1),
                        geometry->entryDenominator);
                    s32 unitArc;
                    s32 obstructionDelta;
                    u32 required;

                    if (sample == 0) {
                        sample = 1;
                    } else if (sample >= totalFrames) {
                        sample = totalFrames - 1;
                    }
                    obstructionDelta = call->startBaseY
                        + (s32)(height << FX32_SHIFT)
                        - ops->lerp(call->startBaseY, call->targetBaseY,
                            sample, totalFrames)
                        + OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32;
                    unitArc = OverworldActorHopPlanner_CallArc(
                        unitArcFn, sample, totalFrames);
                    if (unitArc * (s32)arcHeightQ4 < obstructionDelta) {
                        required = unitArc <= 0 ? 0x100
                            : (u32)ops->signedDivide(obstructionDelta, unitArc) + 1;
                        if (required > OVERWORLD_JUMP_ARC_CAP(call->distance)) {
                            return OverworldActorHopPlanner_ClearanceFinish(cursor,
                                OVERWORLD_MOTION_DECISION_BLOCKED);
                        }
                        arcHeightQ4 = required;
                        cursor->trajectory = (arcHeightQ4 << 16)
                            | (cursor->trajectory & 0xFFFF);
                    }
                }
                continue;
            }
            cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT;
            continue;
        }
        if (cursor->phase == OVERWORLD_ACTOR_HOP_CLEARANCE_HEIGHT) {
            cursor->obstacleBaseY = cursor->fallbackBaseY;
            if (!ops->resolveBaseYAt(
                    call->fieldSystem, cursor->hasSurface ? &cursor->hit : NULL,
                    call->startBaseY, cursor->objectFlags,
                    geometry->tileX, geometry->tileY, &cursor->obstacleBaseY)
                && (call->spotState & OVERWORLD_ACTOR_HOP_PLAN_FLAG_STRICT_HEIGHT) != 0) {
                return OverworldActorHopPlanner_ClearanceFinish(cursor,
                    OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY);
            }
            cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_REDUCE;
            continue;
        }
        obstacleBaseY = cursor->obstacleBaseY;
        for (edge = 0; edge < 2; edge++) {
            /* Entry uses floor; exit adds denominator - 1 for ceiling. */
            u32 numerator;
            u32 denominator;
            if (edge == 0) {
                numerator = geometry->entryNumerator;
                denominator = geometry->entryDenominator;
            } else {
                numerator = geometry->error <= 0
                    ? geometry->xBoundary : geometry->yBoundary;
                denominator = 2 * (geometry->error <= 0
                    ? geometry->absDx : geometry->absDy);
            }
            s32 baseY;
            s32 unitArc;
            s32 obstructionDelta;
            u32 required;

            u32 sampleNumerator = numerator;
            u32 sampleDenominator = denominator;
            if (!slam) {
                sampleNumerator = ops->unsignedDivide(totalFrames * numerator
                    + edge * (denominator - 1), denominator);
                if (sampleNumerator == 0) {
                    sampleNumerator = 1;
                } else if (sampleNumerator >= totalFrames) {
                    sampleNumerator = totalFrames - 1;
                }
                sampleDenominator = totalFrames;
            }
            baseY = ops->lerp(call->startBaseY,
                call->targetBaseY, sampleNumerator, sampleDenominator);
            if (obstacleBaseY <= baseY) {
                continue;
            }
            unitArc = OverworldActorHopPlanner_CallArc(unitArcFn, sampleNumerator, sampleDenominator);
            if (unitArc <= 0) {
                return OverworldActorHopPlanner_ClearanceFinish(cursor, OVERWORLD_MOTION_DECISION_BLOCKED);
            }
            obstructionDelta = obstacleBaseY - baseY
                + OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32;
            if (unitArc * arcHeightQ4 >= obstructionDelta) {
                continue;
            }
            if (slam || call->operation == OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY
                || (!spawnEntry && !OW_WILD_BEHAVIOR_SKID_BOOLEAN(lane->hopAllowVerticalObstacles))) {
                return OverworldActorHopPlanner_ClearanceFinish(cursor, OVERWORLD_MOTION_DECISION_BLOCKED);
            }
            required = (u32)ops->signedDivide(obstructionDelta, unitArc) + 1;
            if (required > 0xFF
                || (OverworldActorHopPlanner_IsJump(call)
                    && required > OVERWORLD_JUMP_ARC_CAP(call->distance))) {
                return OverworldActorHopPlanner_ClearanceFinish(cursor, OVERWORLD_MOTION_DECISION_BLOCKED);
            }
            arcHeightQ4 = required;
        }
        cursor->trajectory = (arcHeightQ4 << 16) | (cursor->trajectory & 0xFFFF);
        cursor->phase = OVERWORLD_ACTOR_HOP_CLEARANCE_NEXT;
    }
}

static OverworldMotionDecision HOP_CLEARANCE_CODE
    __attribute__((used))
OverworldActorHopPlanner_PlanTrajectory(OverworldActorHopPlanCall *call,
    const OverworldHopClearanceNativeOps *ops)
{
    /* The fixed native dispatch keeps its two owners. Operations3/4 enter
     * this owner before the object word can be read as a MapObject. */
    if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN) {
        return OverworldActorHopPlanner_ClearanceBegin(call, ops);
    }
    if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP) {
        return OverworldActorHopPlanner_ClearanceStep(call, ops);
    }
    OverworldActorHopClearanceCursor cursor = {0};
    OverworldActorHopPlanCall request = {0};
    OverworldMotionDecision decision;

    if (call->object == NULL) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    cursor.version = OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION;
    cursor.size = sizeof(cursor);
    cursor.input = call;
    cursor.objectFlags = call->object->flags;
    cursor.fallbackBaseY = (s32)call->object->posVec[1];
    request.clearanceCursor = &cursor;
    decision = OverworldActorHopPlanner_ClearanceBegin(&request, ops);
    while (cursor.phase != OVERWORLD_ACTOR_HOP_CLEARANCE_DONE) {
        cursor.readBudget = OVERWORLD_ACTOR_HOP_CLEARANCE_MAX_READS;
        decision = OverworldActorHopPlanner_ClearanceStep(&request, ops);
    }
    if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        call->trajectory = cursor.trajectory;
    }
    return decision;
}


OverworldMotionDecision OverworldHopClearance_Run(OverworldActorHopPlanCall *call,
    const OverworldHopClearanceNativeOps *ops)
{
    const OverworldActorHopPlanCall *input=call;
    const void *const *callback;
    if (call==NULL || call->operation<OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY
        || call->operation>OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP
        || ops==NULL || ops->magic!=OVERWORLD_HOP_CLEARANCE_NATIVE_MAGIC
        || ops->version!=OVERWORLD_HOP_CLEARANCE_NATIVE_VERSION
        || ops->size!=sizeof(*ops) || ops->leaseEntry!=&gOverworldQueryCodeAddonEntry)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    /* Every word from current to the end of the table is a callback. */
    for (callback=(const void *const *)&ops->current;
            callback<(const void *const *)(ops+1); callback++)
        if (*callback==NULL) return OVERWORLD_MOTION_DECISION_PROFILE;
    if (call->operation>=OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN) {
        const OverworldActorHopClearanceCursor *cursor=call->clearanceCursor;
        if (cursor==NULL || cursor->version!=OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION
            || cursor->size!=sizeof(*cursor)) return OVERWORLD_MOTION_DECISION_PROFILE;
        input=cursor->input;
    }
    if (input==NULL || input->fieldSystem==NULL
        || !ops->current(input->fieldSystem,ops->leaseEntry))
        return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    return OverworldActorHopPlanner_PlanTrajectory(call,ops);
}
