.syntax unified
.thumb

.section .overworld_wild_shadow_policy_entry, "ax", %progbits

.global OverworldWildSpawns_SetNativeShadowSuppressedImpl
.type OverworldWildSpawns_SetNativeShadowSuppressedImpl, %function
.thumb_func
OverworldWildSpawns_SetNativeShadowSuppressedImpl:
    ldr r2, [r0, #8]
    subs r2, #0xE0
    cmp r2, #9
    bhi 3f
    movs r3, #1
    lsls r3, r3, r2
    ldr r2, =gOverworldWildNativeShadowSuppressedMaskStorage
    ldrh r0, [r2]
    cmp r1, #0
    beq 1f
    orrs r0, r3
    b 2f
1:
    bics r0, r3
2:
    strh r0, [r2]
3:
    bx lr
    .pool
.size OverworldWildSpawns_SetNativeShadowSuppressedImpl, . - OverworldWildSpawns_SetNativeShadowSuppressedImpl

.global gOverworldWildNativeShadowSuppressedMaskStorage
.type gOverworldWildNativeShadowSuppressedMaskStorage, %object
gOverworldWildNativeShadowSuppressedMaskStorage:
    .hword 0
.size gOverworldWildNativeShadowSuppressedMaskStorage, . - gOverworldWildNativeShadowSuppressedMaskStorage
    .align 2
