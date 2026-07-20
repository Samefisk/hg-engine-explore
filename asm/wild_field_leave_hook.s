.text
.align 2
.thumb

.global FieldSystem_LeaveFieldHook
FieldSystem_LeaveFieldHook:
push {r4, lr}
mov r4, r0
bl UnloadOverworldWildOverlays
cmp r0, #0
beq .LFieldSystemLeaveFieldReturn
mov r0, r4
mov r1, #0
str r1, [r0, #0x6C]
.LFieldSystemLeaveFieldReturn:
mov r0, r4
pop {r4, pc}
