.syntax unified
.thumb

.section .overworld_wild_shadow_filter_entry, "ax", %progbits

.global OverworldWildSpawns_FilterNativeShadowImpl
.type OverworldWildSpawns_FilterNativeShadowImpl, %function
.thumb_func
OverworldWildSpawns_FilterNativeShadowImpl:
    push {r4, r5, lr}
    mov r4, r0
    // Stock native-shadow routes always pass a live map object. Object IDs
    // occupy one byte; subtracting the wild range start makes every non-wild
    // ID shift the one-bit value to zero or outside the ten-bit policy mask.
    ldr r5, [r0, #8]
    subs r5, #0xE0
    movs r0, #1
    lsls r0, r0, r5
    ldr r5, =0x023BE3FC
    ldrh r5, [r5]
    tst r5, r0
    beq 1f
    ldrb r0, [r4, #2]
    movs r5, #0x10
    orrs r0, r5
    strb r0, [r4, #2]
    pop {r4, r5, pc}
1:
    mov r0, r4
    // sub_020603F8 is resident Thumb code. Calling the absolute linker symbol
    // directly creates an ARM veneer that reaches the right address in the
    // wrong instruction state, so branch through an explicitly Thumb-tagged
    // function pointer instead.
    ldr r5, =0x020603F9
    blx r5
    pop {r4, r5, pc}
    .pool
.size OverworldWildSpawns_FilterNativeShadowImpl, . - OverworldWildSpawns_FilterNativeShadowImpl

.section .overworld_wild_shadow_visibility_filter_entry, "ax", %progbits

.global OverworldWildSpawns_FilterNativeShadowVisibilityImpl
.type OverworldWildSpawns_FilterNativeShadowVisibilityImpl, %function
.thumb_func
OverworldWildSpawns_FilterNativeShadowVisibilityImpl:
    // The two native-shadow tasks keep the object in r6 and their hidden flag
    // in work->0xC (r4).  Set that flag directly from the resident policy on
    // every draw update; the original stock UNK9/UNK20 test still runs next.
    ldr r2, [r6, #8]
    subs r2, #0xE0
    movs r3, #1
    lsls r3, r3, r2
    ldr r2, =0x023BE3FC
    ldrh r2, [r2]
    tst r2, r3
    beq 1f
    movs r2, #1
    b 2f
1:
    movs r2, #0
2:
    // Keep the encounter token in the high half of this stock work word.
    strh r2, [r4, #0xC]
    bx lr
    .pool
.size OverworldWildSpawns_FilterNativeShadowVisibilityImpl, . - OverworldWildSpawns_FilterNativeShadowVisibilityImpl

.section .overworld_wild_shadow_position_filter_entry, "ax", %progbits

.global OverworldWildSpawns_CopyNativeShadowPositionImpl
.type OverworldWildSpawns_CopyNativeShadowPositionImpl, %function
.thumb_func
OverworldWildSpawns_CopyNativeShadowPositionImpl:
    push {r4, r5, r6, lr}
    // Both stock shadow update tasks keep their work block in r4. Its high
    // half at +0xC retains the encounter token bound on the first update.
    mov r6, r4
    mov r4, r0
    mov r5, r1
    ldr r3, =0x0205F945
    blx r3
    ldr r0, [r4, #8]
    subs r0, #0xE0
    cmp r0, #9
    bhi 2f
    sub sp, #8
    mov r2, sp
    mov r1, r6
    adds r1, #0xC
    mov r0, r4
    bl OverworldWalk_CopyNativeShadowValue
    cmp r0, #0
    beq 1f
    ldr r0, [sp]
    str r0, [r5, #4]
1:
    add sp, #8
2:
    pop {r4, r5, r6, pc}
    .pool
.size OverworldWildSpawns_CopyNativeShadowPositionImpl, . - OverworldWildSpawns_CopyNativeShadowPositionImpl
