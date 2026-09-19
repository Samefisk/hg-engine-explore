.nds
.thumb

// FieldInput_Process asks for Waterfall on every field update. The stock
// GetIdxOfFirstPartyMonWithMove decodes and encodes the whole Pokemon five
// times per party member. Keep its exact first-match/egg rules, but group the
// four move reads under the native lock. No cache, timer, RNG or overlay state.
// The first native egg read MUST precede AcquireMonLock: it checks the saved
// checksum and marks Bad Eggs. AcquireMonLock alone does not validate it.
.open "base/arm9.bin", 0x02000000
.org 0x020542E8
.area 0x70, 0x00
FieldPartyMoveQuery:
    push {r3-r7, lr}
    sub sp, #8
    str r0, [sp, #0] // Party; original pushed r3 at sp+8 is lock-token scratch.
    mov r5, r1       // Requested move.
    bl 0x02074640   // Party_GetCount.
    str r0, [sp, #4]
    mov r6, #0      // Party index.
    b @@testParty

@@partyMember:
    ldr r0, [sp, #0]
    mov r1, r6
    bl 0x02074644   // Party_GetMonByIndex.
    mov r4, r0
    mov r1, #76     // MON_DATA_IS_EGG; native checksum check stays first.
    mov r2, #0
    bl 0x0206E540   // GetMonData.
    cmp r0, #0
    bne @@nextMember
    mov r0, r4
    bl 0x0206DD40   // AcquireMonLock; preserve an outer owner's lock.
    str r0, [sp, #8]
    mov r7, #54     // MON_DATA_MOVE1.

@@move:
    mov r0, r4
    mov r1, r7
    mov r2, #0
    bl 0x0206E540
    cmp r0, r5
    beq @@release
    add r7, #1
    cmp r7, #58     // One past MON_DATA_MOVE4.
    bne @@move

@@release:
    mov r0, r4
    ldr r1, [sp, #8]
    bl 0x0206DD8C   // ReleaseMonLock on BOTH match and no-match paths.
    cmp r7, #58
    bne @@found

@@nextMember:
    add r6, #1
@@testParty:
    ldr r0, [sp, #4]
    cmp r6, r0
    blt @@partyMember
    mov r0, #0xFF
    b @@return
@@found:
    mov r0, r6
@@return:
    add sp, #8
    pop {r3-r7, pc}
.endarea
.close
