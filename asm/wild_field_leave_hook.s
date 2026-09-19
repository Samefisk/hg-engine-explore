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

.global FieldSystem_WaitLeaveFieldHook
FieldSystem_WaitLeaveFieldHook:
/*
 * The stock leave caller invokes FieldSystem_LeaveFieldHook once, then waits
 * here for the field overlay manager to exit. Cleanup is retryable, so retry
 * it once per wait frame before checking the stock completion condition.
 */
push {r3, lr}
ldr r0, [r0, #0x18]
bl FieldSystem_LeaveFieldHook
ldr r0, [r0]
ldr r0, [r0]
cmp r0, #0
bne .LFieldSystemWaitLeavePending
mov r0, #1
pop {r3, pc}
.LFieldSystemWaitLeavePending:
mov r0, #0
pop {r3, pc}
