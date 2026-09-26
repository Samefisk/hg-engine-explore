.nds
.thumb

// big thanks to mikelan98 and nomura for this.  really cool stuff

.open "base/arm9.bin", 0x02000000

.org 0x02000CD0 // branch from Main(), run once

    bl load_arm9_expansion


.org 0x02110334
.area 0x40, 0x00

load_arm9_expansion: // load the narc subfile with arm9 expansion data
    push {r2, r4, r5, lr}

// load overlay 129 as arm9 expansion
    mov r0, #129
    mov r1, #2
    bl HandleLoadOverlay129 // HandleLoadOverlay(129, 2) // noinit load

// Load all resident homes without extending into the data at 0x02110374.
// The order keeps actor, mount, and their adapters in place before runtime use.
    ldr r4, =ResidentOverlayIds
    mov r5, #7
ResidentOverlayLoop:
    mov r0, #0
    ldrb r1, [r4]
    add r4, #1
    bl LoadResidentOverlay
    sub r5, #1
    bne ResidentOverlayLoop

    mov r0, #0
    mov r1, #3
    pop {r2, r4, r5, pc}

    .align 2
ResidentOverlayIds:
    .byte 158, 157, 159, 160, 155, 153, 156

.pool
.endarea

.org 0x21102C4

HandleLoadOverlay129:
	push {r3-r7, lr}
	mov r4, r1
	mov r1, #0
	mvn r1, r1
	ldr r2, =0x02007000|1 // HandleLoadOverlay+8, need normal loading for the first one
	bx r2

.pool

LoadResidentOverlay:
    // ITCM overlays need HandleLoadOverlay's no-DMA FS load path.
    cmp r1, #159
    beq LoadResidentItcmOverlay
    cmp r1, #160
    beq LoadResidentItcmOverlay
    ldr r2, =0x02007188|1 // LoadOverlayNoInit(region 0, r1)
    bx r2

LoadResidentItcmOverlay:
    mov r0, r1
    mov r1, #1 // HandleLoadOverlay(id, OVY_LOAD_NOINIT)
    ldr r2, =0x02006FF8|1
    bx r2

.pool

// OS_InitArena reads this OS_GetInitArenaLo(ITCM) literal. Reserve both
// boot-resident mount adapters and gait capsule above the stock ITCM image.
.org 0x020D2C68
    .word 0x01FFA580

.close
