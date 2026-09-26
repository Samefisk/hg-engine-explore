.section .overworld_effect_pool_capacity, "ax", %progbits
.align 2
.thumb

/* Displace the eight bytes at ov01_021E64D0. The stock r2=32 has already
 * sized its other budgets; only the model/field-effect slot count grows to 48.
 * r3 keeps the original 32 argument. Resume after the displaced BL.
 */
.global OverworldEffectPool_ExpandModelSlots
.type OverworldEffectPool_ExpandModelSlots, %function
.thumb_func
OverworldEffectPool_ExpandModelSlots:
    mov r1, #4
    add r3, r2, #0
    mov r2, #48
    bl 0x021F1390
    ldr r3, .LEffectPoolContinue
    bx r3
.align 2
.LEffectPoolContinue:
    .word 0x021E64D9
.size OverworldEffectPool_ExpandModelSlots, .-OverworldEffectPool_ExpandModelSlots
