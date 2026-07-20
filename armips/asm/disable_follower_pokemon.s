.nds
.thumb

// Disable only the vanilla walking-Pokemon presentation and gameplay hooks.
// Keep its compatibility map object, save layout, and sprite/model/render
// helpers intact: stock event scripts can dereference object 253 without an
// active/null guard, and overworld wild Pokemon reuse the rendering helpers.
// This is separate from the partner-trainer flags used for double battles.

.open "base/arm9.bin", 0x02000000

.if DISABLE_FOLLOWER_POKEMON == 1

// FollowMon_ChangeMon can reattach object 253 from the saved map-object array
// without passing it through sub_02069DC8. Route both of its lookups through
// the wrapper below so existing saves receive the same hidden state as newly
// created followers.
.org 0x02069BDC
.area 0x04, 0x00
    bl FollowMon_GetAndHideCompatibilityObject
.endarea

.org 0x02069CF4
.area 0x04, 0x00
    bl FollowMon_GetAndHideCompatibilityObject
.endarea

// sub_02069DC8
// This shared helper is also used by overworld wild Pokemon. Preserve its
// original behavior except for objects using the vanilla follower movement
// type (0x30). Photo objects and overworld wild Pokemon use other movements.
// For the follower, set the stock vanish flag and clear its render-enable bit.
.org 0x02069DC8
.area 0x24, 0x00
    push {r3, r4, r5, lr}
    mov r4, r0
    mov r5, r1
    ldr r2, [r0, #0x14] // LocalMapObject::movement
    cmp r2, #0x30 // vanilla walking-follower movement
    bne @@applyVisibility
    mov r5, #0 // clear the follower render-enable bit
    mov r1, #1 // set MAPOBJECTFLAG_VISIBLE (the stock vanish flag)

@@applyVisibility:
    bl 0x0206A040 // visibility/flag-19 setter
    mov r0, r4
    mov r1, r5
    bl 0x02069DEC // follower render-enable parameter setter
    pop {r3, r4, r5, pc}
.endarea

// FollowMon_IsActive and saved-object compatibility wrapper.
// Normal movement, interaction, field-move, and transition callers take their
// established inactive/no-op paths. The remainder of the original function is
// unreachable after this return, so use it to hide restored object 253 before
// FollowMon_ChangeMon reattaches it to the FieldSystem.
.org 0x02069F88
.area 0x28, 0x00
    mov r0, #0
    bx lr

FollowMon_GetAndHideCompatibilityObject:
    push {r4, lr}
    bl 0x0205EE60 // MapObjectManager_GetFirstActiveObjectByID
    mov r4, r0
    cmp r0, #0
    beq @@returnObject
    mov r1, #1
    bl 0x02069DC8 // apply the follower-specific hidden state

@@returnObject:
    mov r0, r4
    pop {r4, pc}
.endarea

.endif

.close
