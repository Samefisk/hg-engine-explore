    .syntax unified
    .thumb
    .global OverworldMotion_SlamUDiv
    .type OverworldMotion_SlamUDiv, %function
    .thumb_func
    .thumb_set OverworldMotion_SlamUDiv, 0x023DEE4C
    .section .overworld_motion_slam_unit_height,"ax",%progbits
    .global OverworldSlam_UnitHeightNative
    .type OverworldSlam_UnitHeightNative, %function
    .thumb_func
OverworldSlam_UnitHeightNative:
    cmp r0, r1
    bcc 1f
    movs r0, #0x80
    lsls r0, r0, #5
    bx lr
1:  lsls r0, r0, #12
    push {r4, lr}
    bl OverworldMotion_SlamUDiv
    pop {r4, pc}
    .size OverworldSlam_UnitHeightNative, .-OverworldSlam_UnitHeightNative
