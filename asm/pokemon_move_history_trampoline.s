.syntax unified
.thumb

.global SaveGameNormal
.type SaveGameNormal, %function
SaveGameNormal:
    ldr r3, 1f
    bx r3
    .align 2
1:  .word 0x023BE471
