.nds
.thumb

/* Main loads resident overlay 161 before SaveData_New and title overlay 36.
 * Overlay 36 is compressed, so use the already-installed ARM9 save hooks:
 * NewGame_InitSaveData calls Save_InitDynamicRegion at 0x020274A8;
 * Continue_LoadSaveData_HandleError calls SaveData_TryLoadOnContinue, whose
 * successful path calls Save_LoadDynamicRegion at 0x02027AD4.
 *
 * scripts/make.py installs each hook as:
 *   ldr r1, [pc, #0]; bx r1; .word <linked root C target>
 * Keep its target word at +4. Redirect the literal load to +8, where this
 * patch stores a nearby wrapper address. The wrappers call the saved target
 * and then the fixed resident API callback at table offset 0x24. */
.open "base/arm9.bin", 0x02000000

.org 0x020274A8
.area 2
    ldr r1, [pc, #4]
.endarea
.org 0x020274B0
    .word PlayerHealthHook_SaveInit | 1
.org 0x020274B4
.area 0x020274D0 - .
PlayerHealthHook_SaveInit:
    push {r4, lr}
    ldr r3, =0x020274AC
    ldr r3, [r3]
    blx r3
    ldr r3, =0x01FFA580
    ldr r3, [r3, #0x24]
    blx r3
    pop {r4, pc}
    .pool
.endarea

.org 0x02027AD4
.area 2
    ldr r1, [pc, #4]
.endarea
.org 0x02027ADC
    .word PlayerHealthHook_SaveLoad | 1
.org 0x02027AE0
.area 0x02027B74 - .
PlayerHealthHook_SaveLoad:
    push {r4, lr}
    ldr r3, =0x02027AD8
    ldr r3, [r3]
    blx r3
    cmp r0, #0
    beq PlayerHealthHook_SaveLoad_Done
    mov r4, r0
    ldr r3, =0x01FFA580
    ldr r3, [r3, #0x24]
    blx r3
    mov r0, r4
PlayerHealthHook_SaveLoad_Done:
    pop {r4, pc}
    .pool
.endarea

.close
