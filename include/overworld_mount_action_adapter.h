#ifndef OVERWORLD_MOUNT_ACTION_ADAPTER_H
#define OVERWORLD_MOUNT_ACTION_ADAPTER_H

#include "overworld_mount_internal.h"
#include "overworld_actor_system_internal.h"
#include "overworld_behavior_condition_adapter.h"

#define OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION 2
#define OVERWORLD_MOUNT_ACTION_OVERLAY_LOAD_ADDR 0x01FF8620
#define OVERWORLD_MOUNT_ACTION_OVERLAY_END_ADDR 0x01FF9800
#define OVERWORLD_MOUNT_ACTION_OVERLAY_ENTRY_ADDR 0x01FF8801
#define OVERWORLD_MOUNT_CONDITIONAL_ADMISSION_ENTRY_ADDR 0x01FF95D1
#define OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER 0x8000
#define OVERWORLD_MOUNT_CONDITIONAL_ADMISSION_INVALID \
    ((const BehaviorResolveRequest *)1)

typedef enum OverworldMountActionOperation {
    OVERWORLD_MOUNT_ACTION_WALK_CORRIDOR = 1,
    OVERWORLD_MOUNT_ACTION_START_CHAIN = 2,
    OVERWORLD_MOUNT_ACTION_TICK_CHAIN = 3,
    OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN = 4,
    OVERWORLD_MOUNT_ACTION_CHAIN_FORWARD_TARGET = 5,
    OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY = 6,
} OverworldMountActionOperation;

typedef enum OverworldMountActionResult {
    OVERWORLD_MOUNT_ACTION_FINAL = 0,
    OVERWORLD_MOUNT_ACTION_STARTED = 1,
    OVERWORLD_MOUNT_ACTION_RETRY = 2,
} OverworldMountActionResult;

typedef struct OverworldMountActionCall {
    u16 version;
    u16 size;
    u8 operation;
    u8 action;
    u8 direction;
    u8 result;
    OverworldMountRuntimeState *state;
    FIELD_PLAYER_AVATAR *avatar;
    const OverworldActorPolicyView *policy;
    u32 *trajectory;
} OverworldMountActionCall;

typedef u8 (*OverworldMountActionAdapterDispatchFunc)(
    OverworldMountActionCall *call);
typedef const BehaviorResolveRequest *
(*OverworldMountConditionalAdmissionFunc)(
    const OverworldWildBehaviorConditionRuntime *conditions,
    const OverworldWildBehaviorContext *context);

#define OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH \
    ((OverworldMountActionAdapterDispatchFunc) \
        OVERWORLD_MOUNT_ACTION_OVERLAY_ENTRY_ADDR)
#define OVERWORLD_MOUNT_CONDITIONAL_ADMISSION \
    ((OverworldMountConditionalAdmissionFunc) \
        OVERWORLD_MOUNT_CONDITIONAL_ADMISSION_ENTRY_ADDR)

#endif // OVERWORLD_MOUNT_ACTION_ADAPTER_H
