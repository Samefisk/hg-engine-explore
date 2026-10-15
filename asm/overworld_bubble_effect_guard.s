.section .overworld_bubble_effect_guard, "ax", %progbits
.align 2
.thumb

/* ov01_02203A48 already owns its 64-byte frame at this entry point.
 * Reject before the stock bubble busy flag, resources, or VRAM work are set.
 * The model pool count uses the same signed comparison as sub_02024280.
 */
.global OverworldBubbleEffect_ModelAdmissionGuard
.type OverworldBubbleEffect_ModelAdmissionGuard, %function
.thumb_func
OverworldBubbleEffect_ModelAdmissionGuard:
    ldr r6, .LBubbleEffectGetContext
    blx r6
    ldr r1, [r0, #0x20]
    cmp r1, #0
    beq .LBubbleEffectReject
    ldr r1, [r1, #0x0C]
    cmp r1, #0
    beq .LBubbleEffectReject
    ldr r2, [r1, #8]
    add r1, #0xD4
    ldr r1, [r1]
    cmp r1, r2
    bge .LBubbleEffectReject
    /* Complete the displaced GetContext/r6/type setup at 0x02203A50. */
    mov r6, r0
    mov r1, #0x12
    ldr r2, .LBubbleEffectContinue
    bx r2
.LBubbleEffectReject:
    mov r0, #0
    add sp, #0x2C
    pop {r3, r4, r5, r6, pc}
.align 2
.LBubbleEffectGetContext:
    .word 0x021F146D
.LBubbleEffectContinue:
    .word 0x02203A59
.size OverworldBubbleEffect_ModelAdmissionGuard, .-OverworldBubbleEffect_ModelAdmissionGuard
