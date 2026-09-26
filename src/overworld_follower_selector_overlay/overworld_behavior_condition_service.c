#include "../../include/overworld_behavior_condition_runtime.h"
#include "../../include/overworld_follower_selector.h"

const OverworldBehaviorConditionServiceEntry *
__attribute__((section(".overworld_behavior_condition_service_gate"),
    naked, noinline, used))
OverworldBehaviorConditionService_Get(void)
{
    /* Compact Thumb form of OverworldFollowerSelector_IsDirectLoaded(). */
    __asm__(
        "ldr r0, =0x023C8148\n"
        "ldrb r0, [r0]\n"
        "lsl r0, r0, #25\n"
        "bpl 1f\n"
        "ldr r0, =0x023C22A0\n"
        "ldrh r1, [r0, #4]\n"
        "cmp r1, #8\n"
        "beq 2f\n"
        "1:\n"
        "mov r0, #0\n"
        "2:\n"
        "bx lr\n");
}

const OverworldBehaviorConditionServiceEntry
    gOverworldBehaviorConditionServiceEntry
    __attribute__((section(".overworld_behavior_condition_service_entry"), used)) = {
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC,
        OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION,
        sizeof(OverworldBehaviorConditionServiceEntry),
        OverworldBehaviorCondition_PrepareActor,
        OverworldBehaviorCondition_EvaluatePrepared,
        OverworldBehaviorCondition_ValidateResolveRequest,
        0,
    };
