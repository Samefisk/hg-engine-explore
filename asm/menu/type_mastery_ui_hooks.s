.text
.align 2
.thumb

.global TypeMastery_PartyMenuInput_Hook
TypeMastery_PartyMenuInput_Hook:
    bl TypeMastery_PartyMenuHandleInput
    cmp r0, #4
    bhi .Lparty_high
    ldr r1, =0x02079314 | 1
    bx r1
.Lparty_high:
    ldr r1, =0x020793B6 | 1
    bx r1

.global TypeMastery_TrainerCardInput_Hook
TypeMastery_TrainerCardInput_Hook:
    bl TypeMastery_TrainerCardHandleInput
    cmp r0, #3
    bne .Ltrainer_not_exit
    ldr r1, =0x021E5DD0 | 1
    bx r1
.Ltrainer_not_exit:
    ldr r1, =0x021E5DDC | 1
    bx r1

.pool
