.section .overworld_mount_boundary_thunk, "ax", %progbits
.align 2
.force_thumb
.syntax unified

// The resident Actor Motion boundary bridge is Thumb. Tail-call its odd
// address directly so the linker cannot insert an ARM-mode veneer. Preserve
// r3 because it carries the fourth ARM EABI argument.
.global OverworldMount_CallActorMotionBoundary
.thumb_func
.type OverworldMount_CallActorMotionBoundary, function
OverworldMount_CallActorMotionBoundary:
    push {r3}
    .hword 0x4B02
    mov r12, r3
    pop {r3}
    bx r12
    nop
1:  .word 0x023BD351
.size OverworldMount_CallActorMotionBoundary, . - OverworldMount_CallActorMotionBoundary
