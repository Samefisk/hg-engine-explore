    .syntax unified
    .thumb
    .global OverworldActorHopPlanner_VectorOwner
    .type OverworldActorHopPlanner_VectorOwner, %function
    .thumb_func
    .thumb_set OverworldActorHopPlanner_VectorOwner, 0x023BDCA1
    .global OverworldActorHopPlanner_TrajectoryOwner
    .type OverworldActorHopPlanner_TrajectoryOwner, %function
    .thumb_func
    .thumb_set OverworldActorHopPlanner_TrajectoryOwner, 0x023BDD25
    .section .overworld_actor_hop_dispatch,"ax",%progbits
    .global OverworldActorHopPlanner_DispatchNative
    .type OverworldActorHopPlanner_DispatchNative,%function
    .thumb_func
OverworldActorHopPlanner_DispatchNative:
    cmp r0, #0
    beq 2f
    movs r1, #44
    ldrb r1, [r0,r1]
    cmp r1, #0
    beq 1f
    cmp r1, #4
    bhi 2f
    ldr r3, 4f
    bx r3
1:  ldr r3, 3f
    bx r3
2:  movs r0, #8
    bx lr
    .align 2
3:  .word OverworldActorHopPlanner_VectorOwner
4:  .word OverworldActorHopPlanner_TrajectoryOwner
    .size OverworldActorHopPlanner_DispatchNative, .-OverworldActorHopPlanner_DispatchNative
