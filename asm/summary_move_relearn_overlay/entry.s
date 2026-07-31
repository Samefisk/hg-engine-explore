.syntax unified
.thumb

.section .summary_move_relearn_api, "ax", %progbits

/* "SRM4", followed by the task ABI version. */
.word 0x344D5253
.word 4

.global SummaryMoveRelearn_Entry
.type SummaryMoveRelearn_Entry, %function
SummaryMoveRelearn_Entry:
    ldr r3, 1f
    bx r3
    .align 2
1:  .word SummaryMoveRelearn_MainState + 1
.size SummaryMoveRelearn_Entry, . - SummaryMoveRelearn_Entry
