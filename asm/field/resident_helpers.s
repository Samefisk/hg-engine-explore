.syntax unified
.thumb

/* Reuse the core's 8-byte Thumb -> ARM -> Thumb bridges. These aliases carry
 * function metadata but allocate no Field code or state. Division preserves
 * both r0 (quotient) and r1 (remainder); memory calls preserve their return ABI.
 * The package gate checks each target, body, and Field call site.
 */
.global __aeabi_idiv
.thumb_func
.thumb_set __aeabi_idiv, 0x023DEE44
.global __aeabi_idivmod
.thumb_func
.thumb_set __aeabi_idivmod, 0x023DEE44
.global __aeabi_uidivmod
.thumb_func
.thumb_set __aeabi_uidivmod, 0x023DEE4C
.global memset
.thumb_func
.thumb_set memset, 0x023DEEA2
.global memcpy
.thumb_func
.thumb_set memcpy, 0x023DEEBE

/* A trainer task suspends the normal field-idle transition retry. Keep this
 * cold driver in the fixed ABI gaps so overlay 131 does not grow. */
.section .overworld_follower_selector_task_poll, "ax", %progbits
.align 1
.global OverworldFieldService_FinishPendingTransition
.thumb_func
OverworldFieldService_FinishPendingTransition:
push {r4, lr}
ldr r4, .LOverworldFieldTransitionAddress
ldrb r2, [r4, #18]
cmp r2, #0
beq .LOverworldFieldTransitionFinished
movs r2, #2
strb r2, [r4, #16]
ldrh r3, [r4, #14]
ldrh r2, [r4, #12]
ldr r1, .LOverworldWildSpawnStateAddress
ldr r0, [r4]
bl OverworldFieldService_OnMapHeaderChangedResident
cmp r0, #0
beq .LOverworldFieldTransitionReturn
.LOverworldFieldTransitionFinished:
movs r0, #1
.LOverworldFieldTransitionReturn:
pop {r4, pc}
.align 2
.LOverworldFieldTransitionAddress:
.word OverworldFieldTransitionRuntimeStorage
.LOverworldWildSpawnStateAddress:
.word sOverworldWildSpawnState
