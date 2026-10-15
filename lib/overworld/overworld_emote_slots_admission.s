.section .overworld_emote_continuation,"ax",%progbits
.syntax unified
.thumb
/* A second hook at02203A58, after the existing unchanged model guard's
 * GetContext and capacity check at02203A50. The native frame is still live. */
.global OverworldEmoteSlots_AfterModelAdmission
.type OverworldEmoteSlots_AfterModelAdmission, %function
.thumb_func
OverworldEmoteSlots_AfterModelAdmission:
    mov r0, r6
    mov r1, r5
    mov r2, r4
    bl OverworldEmoteSlots_Admit
    add sp, #0x2C
    pop {r3, r4, r5, r6, pc}
.size OverworldEmoteSlots_AfterModelAdmission, .-OverworldEmoteSlots_AfterModelAdmission
