.nds
.thumb

// big thanks to mikelan98 and nomura for this.  really cool stuff

.open "base/arm9.bin", 0x02000000

.org 0x02000CD0 // branch from Main(), run once

    bl load_arm9_expansion


.org 0x02110334

load_arm9_expansion: // load the narc subfile with arm9 expansion data
    push {r2, lr}

// load overlay 129 as arm9 expansion
    mov r0, #129
    mov r1, #2
    bl HandleLoadOverlay129 // HandleLoadOverlay(129, 2) // noinit load

// load overlay 155's task-6 bridge before any resident history caller
    mov r1, #155
    bl LoadResidentOverlay

// load overlay 157's runtime-layer service into the third reserved window
    mov r1, #157
    bl LoadResidentOverlay

// load overlays 158 and 153 through the bounded padding helper
    bl LoadRuntimeLayersAndHistory
    nop

    mov r0, #0
    mov r1, #3
    pop {r2, pc}


.pool

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
    mov r0, #0
    ldr r2, =0x02007188|1 // LoadOverlayNoInit(region 0, r1)
    bx r2

.pool

// Stock 0x021102E0..0x021102F7 is all 0xFF padding.  Keep this helper in the
// bounded 0x021102E0..0x021102F3 area so the adjacent word at 0x021102F8
// cannot be overwritten.
.org 0x021102E0
.area 0x14, 0xFF
LoadRuntimeLayersAndHistory:
    push {r3, lr}
    mov r1, #158
    bl LoadResidentOverlay
    mov r1, #153
    bl LoadResidentOverlay
    pop {r3, pc}
.endarea

.close
