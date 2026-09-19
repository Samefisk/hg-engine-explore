.section .overworld_grass_effect_guard, "ax", %progbits
.align 2
.thumb

/* ov01_021FF174: effect allocation can fail when the stock pool is full.
 * Enter after ov01_021F1740, before the handle is stored/dereferenced.
 * FALSE makes sub_02068A08 destroy the SysTask and reset its slot; the
 * effect destructor must not run for an init which never owned a handle.
 */
.global OverworldGrassEffect_InitAllocationGuard
.type OverworldGrassEffect_InitAllocationGuard, %function
.thumb_func
OverworldGrassEffect_InitAllocationGuard:
    cmp r0, #0
    beq .LGrassEffectReject
    /* Exact four instructions displaced at 0x021FF1F0. */
    str r0, [r4, #0x3C]
    mov r1, #2
    ldr r0, [r4, #0x30]
    lsl r1, r1, #8
    /* Preserve r2, r3 and LR while returning to the stock continuation. */
    push {r2, r3}
    ldr r2, .LGrassEffectContinue
    str r2, [sp, #4]
    pop {r2, pc}
.LGrassEffectReject:
    add sp, #0xC
    pop {r3, r4, r5, r6, pc}
.align 2
.LGrassEffectContinue:
    .word 0x021FF1F9
.size OverworldGrassEffect_InitAllocationGuard, .-OverworldGrassEffect_InitAllocationGuard
