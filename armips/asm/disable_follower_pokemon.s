.nds
.thumb

// Disable only the vanilla walking-Pokemon presentation and gameplay hooks.
// Keep its compatibility map object, save layout, and sprite/model/render
// helpers intact: stock event scripts can dereference object 253 without an
// active/null guard, and overworld wild Pokemon reuse the rendering helpers.
// This is separate from the partner-trainer flags used for double battles.

.open "base/arm9.bin", 0x02000000

.if DISABLE_FOLLOWER_POKEMON == 1

// sub_02069DC8
// This shared helper is also used by overworld wild Pokemon. Preserve its
// original behavior for every object except the vanilla follower (ID 253).
// For that object, set the stock hidden flag and clear its render-enable bit.
.org 0x02069DC8
.area 0x24, 0x00
    push {r3, r4, r5, lr}
    mov r4, r0
    mov r5, r1
    ldr r2, [r0, #8] // LocalMapObject::id
    cmp r2, #253 // obj_partner_poke
    bne @@applyVisibility
    mov r5, #0 // clear the follower render-enable bit
    mov r1, #1 // set the stock hidden flag

@@applyVisibility:
    bl 0x0206A040 // visibility/flag-19 setter
    mov r0, r4
    mov r1, r5
    bl 0x02069DEC // follower render-enable parameter setter
    pop {r3, r4, r5, pc}
.endarea

// FollowMon_IsActive
// Normal movement, interaction, field-move, and transition callers take their
// established inactive/no-op paths. The hidden compatibility object remains
// available to the handful of stock scripts that dereference it directly.
.org 0x02069F88
.area 0x04, 0x00
    mov r0, #0
    bx lr
.endarea

.endif

.close
