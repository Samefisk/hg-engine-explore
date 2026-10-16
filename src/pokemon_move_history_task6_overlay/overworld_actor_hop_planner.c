#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_actor_hop_clearance.h"
#include "../../include/overworld_hop_clearance_native.h"
#include "../../include/overworld_query_code_addon.h"
#include "../../include/overworld_hop_presentation_native.h"
#include "../../include/overworld_wild_occupancy.h"
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
__asm__(".global OverworldWildOccupancy_Query\n.type OverworldWildOccupancy_Query, %function\n.thumb\n.thumb_func\n.thumb_set OverworldWildOccupancy_Query, 0x023C0185\n");
__asm__(".global OverworldHopPresentation_Acquire\n.type OverworldHopPresentation_Acquire, %function\n.thumb\n.thumb_func\n.thumb_set OverworldHopPresentation_Acquire, 0x023DEDF1\n");
#endif

#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
static s32 OverworldMotion_SlamUnitArc(u16 numerator, u16 denominator, u8 peak)
{
    (void)peak;
    return OverworldMotion_SlamRiseUnitHeight(numerator, denominator);
}
#else
extern s32 OverworldMotion_SlamUnitArc(u16, u16, u8);
__asm__(".global OverworldMotion_SlamUnitArc\n.type OverworldMotion_SlamUnitArc, %function\n.thumb\n.thumb_func\n.thumb_set OverworldMotion_SlamUnitArc, 0x023B8601\n");
#endif

extern void OverworldActorHopGeometry_Init(OverworldActorHopGeometry *, const void *);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
__asm__(".global OverworldActorHopGeometry_Init\n.type OverworldActorHopGeometry_Init, %function\n.thumb\n.thumb_func\n.thumb_set OverworldActorHopGeometry_Init, 0x023B92D1\n");
#endif



#pragma GCC optimize("no-if-conversion", "no-tree-loop-optimize", "no-tree-ter")


#define OVERWORLD_HOP_OBSTACLE_CLEARANCE_FX32 (1 << FX32_SHIFT)
#define OVERWORLD_HOP_PLANNER_CODE \
    __attribute__((section(".overworld_actor_hop_planner_code"), noinline, \
        optimize("Os")))

/* Boot-resident shared interpolation, in the existing Walk helper page. */
extern s32 OverworldActorHopPlanner_LerpFx32(s32, s32, u32, u32);
__asm__(".global OverworldActorHopPlanner_LerpFx32\n.type OverworldActorHopPlanner_LerpFx32, %function\n.thumb\n.thumb_func\n.thumb_set OverworldActorHopPlanner_LerpFx32, 0x023BF811\n");
__asm__(".global OverworldActorHopGeometry_NextCell\n.type OverworldActorHopGeometry_NextCell, %function\n.thumb\n.thumb_func\n.thumb_set OverworldActorHopGeometry_NextCell, 0x023BFFA3\n");

static inline const OverworldWildBehaviorProfileData *
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
    __attribute__((used))
OverworldActorHopPlanner_PlanVector(
    OverworldActorHopPlanCall *call)
{
    const OverworldWildBehaviorProfileData *lane;
    int dx = call->deltaX;
    int dy = call->deltaY;
    u32 absDx = dx < 0 ? 0u - (u32)dx : (u32)dx;
    u32 absDy = dy < 0 ? 0u - (u32)dy : (u32)dy;
    u32 distance = absDx > absDy ? absDx : absDy;
    u32 direction = absDx >= absDy ? 3 + (dx >> 31) : 1 + (dy >> 31);

    if (call->profile == NULL || distance == 0) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (absDx + absDy != distance && absDx != absDy
        && !(call->spotState & OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM)) {
        return OVERWORLD_MOTION_DECISION_DIRECTION;
    }
    lane = OverworldActorHopPlanner_GetLane(call->profile,
            call->spotState & ~OVERWORLD_ACTOR_HOP_PLAN_FLAG_SLAM);
    if (absDx + absDy == distance) {
        if (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                lane->hopAllowNonCardinal)) {
            return OVERWORLD_MOTION_DECISION_DIRECTION;
        }
    } else if (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                   lane->hopAllowNonCardinal)) {
        return OVERWORLD_MOTION_DECISION_DIRECTION;
    }
    if (distance < lane->hopMinDistance
        || distance > lane->hopMaxDistance) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    call->direction = direction;
    call->distance = (u8)distance;
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
}

extern u32 __aeabi_uidiv(u32, u32);
extern s32 __aeabi_idiv(s32, s32);

static BOOL OverworldActorHopPlanner_CurrentQuery(FieldSystem *field,const void *entry)
{
    return OverworldHopPresentation_Acquire(field)==entry;
}

static OverworldMotionDecision OVERWORLD_HOP_PLANNER_CODE
    __attribute__((used))
OverworldActorHopPlanner_PlanTrajectory(OverworldActorHopPlanCall *call)
{
    const OverworldActorHopPlanCall *input=call;
    const OverworldQueryCodeAddonEntry *entry;
    OverworldHopClearanceNativeOps ops;
    if (call->operation>=OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN) {
        const OverworldActorHopClearanceCursor *cursor=call->clearanceCursor;
        if (cursor==NULL || cursor->version!=OVERWORLD_ACTOR_HOP_CLEARANCE_VERSION
            || cursor->size!=sizeof(*cursor)) return OVERWORLD_MOTION_DECISION_PROFILE;
        input=cursor->input;
    }
    if (input==NULL || input->fieldSystem==NULL)
        return OVERWORLD_MOTION_DECISION_PROFILE;
    entry=OverworldHopPresentation_Acquire(input->fieldSystem);
    if (entry==NULL) return OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;
    if (entry->magic!=OVERWORLD_QUERY_CODE_ADDON_MAGIC
        || entry->version!=OVERWORLD_QUERY_CODE_ADDON_VERSION
        || entry->size!=sizeof(*entry) || entry->hopTrajectory==NULL
        || !OverworldWildRuntime_Validate()) return OVERWORLD_MOTION_DECISION_PROFILE;
    ops=(OverworldHopClearanceNativeOps){
        OVERWORLD_HOP_CLEARANCE_NATIVE_MAGIC,OVERWORLD_HOP_CLEARANCE_NATIVE_VERSION,
        sizeof(ops),entry,OverworldActorHopPlanner_CurrentQuery,
        OverworldActorHopGeometry_Init,OverworldActorHopGeometry_NextCell,
        OverworldActorHopPlanner_LerpFx32,OverworldMotion_SlamUnitArc,
        OverworldMotion_SlamPhaseCheck,
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->querySurface,
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->resolveBaseYAt,
        OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpTrajectory,
        OVERWORLD_WILD_SURFACE_SERVICE_ENTRY->calculateJumpArc,
        __aeabi_uidiv,__aeabi_idiv,IsMetatileBlockedAt,GetMetatileBehaviorAt,
        OverworldWildOccupancy_Query};
    return entry->hopTrajectory(call,&ops);
}

#ifdef OVERWORLD_ACTOR_SYSTEM_HOST
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
    /* Match the fixed native dispatch's two owners and operation guard. */
    if (call->operation <= OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP) {
        return OverworldActorHopPlanner_PlanTrajectory(call);
    }
    return OVERWORLD_MOTION_DECISION_PROFILE;
}

#else
extern OverworldMotionDecision OverworldActorHopPlanner_PlanImpl(OverworldActorHopPlanCall *);
__asm__(".global OverworldActorHopPlanner_PlanImpl\n.type OverworldActorHopPlanner_PlanImpl, %function\n.thumb\n.thumb_func\n.thumb_set OverworldActorHopPlanner_PlanImpl, 0x023B9881\n");

#endif

OverworldMotionDecision __attribute__((naked,
    section(".overworld_actor_hop_planner"), used))
OverworldActorHopPlanner_Plan(OverworldActorHopPlanCall *call)
{
    (void)call;
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word OverworldActorHopPlanner_PlanImpl\n");
}
