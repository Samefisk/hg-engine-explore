#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/map_events_internal.h"

#pragma GCC optimize("no-if-conversion", "no-tree-loop-optimize", "no-tree-ter")

#define OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32 (1 << FX32_SHIFT)
#define OVERWORLD_HOP_OFFSCREEN_DISTANCE 16
#define OVERWORLD_HOP_PLANNER_CODE \
    __attribute__((section(".overworld_actor_hop_planner_code"), noinline, \
        optimize("Os")))

static s32 OVERWORLD_HOP_PLANNER_CODE OverworldActorHopPlanner_LerpFx32(
    s32 start,
    s32 target,
    u32 elapsed,
    u32 total)
{
    s32 delta;
    s32 quotient;
    s32 remainder;

    if (elapsed >= total) {
        return target;
    }
    delta = target - start;
    quotient = delta / (s32)total;
    remainder = delta - quotient * (s32)total;
    return start + quotient * (s32)elapsed
        + remainder * (s32)elapsed / (s32)total;
}

static const OverworldWildBehaviorProfileData *OVERWORLD_HOP_PLANNER_CODE
OverworldActorHopPlanner_GetLane(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        return &profile->tired;
    }
    return &profile->owner;
}

static OverworldMotionDecision OVERWORLD_HOP_PLANNER_CODE
OverworldActorHopPlanner_PlanVector(
    OverworldActorHopPlanCall *call)
{
    const OverworldWildBehaviorProfileData *lane;
    int dx = call->deltaX;
    int dy = call->deltaY;
    int absDx = dx < 0 ? -dx : dx;
    int absDy = dy < 0 ? -dy : dy;
    int distance = absDx > absDy ? absDx : absDy;

    if (call->profile == NULL || distance == 0) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    lane = OverworldActorHopPlanner_GetLane(call->profile, call->spotState);
    if (((absDx == 0 || absDy == 0)
            && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                lane->hopAllowNonCardinal))
        || (absDx != 0 && absDy != 0
            && (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                    lane->hopAllowNonCardinal)
                || absDx != absDy))) {
        return OVERWORLD_MOTION_DECISION_DIRECTION;
    }
    if (distance < lane->hopMinDistance
        || distance > lane->hopMaxDistance) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    call->direction = absDx >= absDy ? 2 + (dx > 0) : (dy > 0);
    call->distance = (u8)distance;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static OverworldMotionDecision OVERWORLD_HOP_PLANNER_CODE
    /* GCC 10's induction-variable rewrite spills extra loop state here. Keep
     * the compact edge arithmetic inside the fixed resident reservation. */
    __attribute__((optimize("no-ivopts")))
OverworldActorHopPlanner_PlanTrajectory(
    OverworldActorHopPlanCall *call)
{
    const OverworldWildBehaviorProfileData *lane = call->lane;
    u32 trajectory;
    u32 totalFrames;
    u32 arcHeightQ4;
    u32 tileIndex;

    if (lane == NULL || call->fieldSystem == NULL
        || call->surfaceCatalog == NULL || call->object == NULL
        || call->distance == 0) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY) {
        trajectory = call->trajectory;
        /* Flat motion samples exact entry/exit fractions of each crossed tile.
         * Keep that geometric clock separate from its authored output duration,
         * including a one-frame duration or a profile whose Hop time is zero. */
        totalFrames = 2 * call->distance;
        arcHeightQ4 = 0;
    } else {
        trajectory = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpTrajectory(
            lane->hopTime,
            call->distance,
            call->targetBaseY - call->startBaseY,
            lane->hopElevationTimeScale
                | ((u16)lane->hopElevationArcScale << 8));
        totalFrames = trajectory & 0xFFFF;
        arcHeightQ4 = trajectory >> 16;
    }
    if (totalFrames < 2) {
        call->trajectory = trajectory;
        return OVERWORLD_MOTION_DECISION_ACCEPTED;
    }

    for (tileIndex = 1; tileIndex < call->distance; tileIndex++) {
        u32 denominator = 2 * call->distance;
        OverworldWildSurfaceHit hit;
        s32 obstacleBaseY;
        int tileX;
        int tileY;
        u32 edge;

        tileX = OverworldActorHopPlanner_LerpFx32(
            (call->startX << 16) + 0x8000,
            (call->targetX << 16) + 0x8000,
            tileIndex,
            call->distance) >> 16;
        tileY = OverworldActorHopPlanner_LerpFx32(
            (call->startY << 16) + 0x8000,
            (call->targetY << 16) + 0x8000,
            tileIndex,
            call->distance) >> 16;
        if (call->distance != OVERWORLD_HOP_OFFSCREEN_DISTANCE) {
            if (!OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->querySurface(
                    call->fieldSystem,
                    call->surfaceCatalog,
                    tileX,
                    tileY,
                    &hit)
                || hit.surfaceId == OW_WILD_SURFACE_ID_NATIVE_GROUND) {
                continue;
            }
            obstacleBaseY = hit.height;
            if (hit.surfaceId == OW_WILD_SURFACE_ID_NATIVE_CANOPY
                || obstacleBaseY == 0) {
                obstacleBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
                    call->fieldSystem,
                    call->surfaceCatalog,
                    call->object,
                    tileX,
                    tileY);
            }
        } else {
            obstacleBaseY = OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
                call->fieldSystem,
                call->surfaceCatalog,
                call->object,
                tileX,
                tileY);
        }

        for (edge = 0; edge < 2; edge++) {
            /* Entry uses floor; exit adds denominator - 1 for ceiling. */
            u32 numerator = totalFrames * (2 * tileIndex - 1 + 2 * edge)
                + edge * (denominator - 1);
            u32 elapsed = numerator / denominator;
            s32 baseY;
            s32 unitArc;
            s32 obstructionDelta;
            u32 required;

            if (elapsed == 0) {
                elapsed = 1;
            } else if (elapsed >= totalFrames) {
                elapsed = totalFrames - 1;
            }
            baseY = OverworldActorHopPlanner_LerpFx32(
                call->startBaseY,
                call->targetBaseY,
                elapsed,
                totalFrames);
            if (obstacleBaseY <= baseY) {
                continue;
            }
            unitArc = OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc(
                elapsed,
                totalFrames,
                1);
            if (unitArc <= 0) {
                return OVERWORLD_MOTION_DECISION_BLOCKED;
            }
            obstructionDelta = obstacleBaseY - baseY
                + OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32;
            if (unitArc * arcHeightQ4 >= obstructionDelta) {
                continue;
            }
            if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY
                || lane->hopAllowVerticalObstacles != 1) {
                return OVERWORLD_MOTION_DECISION_BLOCKED;
            }
            required = (u32)(obstructionDelta / unitArc) + 1;
            if (required > 0xFF) {
                return OVERWORLD_MOTION_DECISION_BLOCKED;
            }
            arcHeightQ4 = required;
        }
    }

    call->trajectory = ((u32)arcHeightQ4 << 16) | (trajectory & 0xFFFF);
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static OverworldMotionDecision OVERWORLD_HOP_PLANNER_CODE
    __attribute__((used))
OverworldActorHopPlanner_PlanImpl(OverworldActorHopPlanCall *call)
{
    if (call == NULL) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (call->operation == OVERWORLD_ACTOR_HOP_PLAN_VECTOR) {
        return OverworldActorHopPlanner_PlanVector(call);
    }
    /* VECTOR already returned; the remaining valid operations are 1 and 2. */
    if (call->operation <= OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY) {
        return OverworldActorHopPlanner_PlanTrajectory(call);
    }
    return OVERWORLD_MOTION_DECISION_PROFILE;
}

OverworldMotionDecision __attribute__((naked,
    section(".overworld_actor_hop_planner"), used))
OverworldActorHopPlanner_Plan(OverworldActorHopPlanCall *call)
{
    (void)call;
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word OverworldActorHopPlanner_PlanImpl + 1\n");
}
