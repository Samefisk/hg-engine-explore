.section .overworld_dust_effect_guard, "ax", %progbits
.align 2
.thumb

/* The stock dry-ground dust effect can fail to allocate a 3D model when
 * many Pokémon walk at once. Reject only that optional effect before its
 * update dereferences the missing model. The failed init owns no handle, so
 * the field-effect manager destroys its task without calling its destructor.
 */
.global OverworldDustEffect_InitAllocationGuard
.type OverworldDustEffect_InitAllocationGuard, %function
.thumb_func
OverworldDustEffect_InitAllocationGuard:
    cmp r0, #0
    beq .LDustEffectReject
    str r0, [r4, #0x20]
    mov r0, #1
    b .LDustEffectReturn
.LDustEffectReject:
    mov r0, #0
.LDustEffectReturn:
    add sp, #0xC
    pop {r4, r5, pc}
.size OverworldDustEffect_InitAllocationGuard, .-OverworldDustEffect_InitAllocationGuard
