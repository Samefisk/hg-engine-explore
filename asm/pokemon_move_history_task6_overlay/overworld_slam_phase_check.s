    .syntax unified
    .thumb
    .section .overworld_motion_slam_phase_check,"ax",%progbits
    .global OverworldSlam_PhaseCheckNative
    .type OverworldSlam_PhaseCheckNative, %function
    .thumb_func
OverworldSlam_PhaseCheckNative:
    cmp r0, #2
    bne 1f
    cmp r1, #0
    beq 1f
    cmp r2, #0
    beq 1f
    cmp r2, r3
    blt 2f
1:  movs r0, #0
    bx lr
2:  movs r0, #1
    bx lr
    .size OverworldSlam_PhaseCheckNative, .-OverworldSlam_PhaseCheckNative
