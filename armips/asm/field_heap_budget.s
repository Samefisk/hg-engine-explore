.nds
.thumb

// Field heap budget. Both field heaps are children of HEAP_ID_3, which is
// fully packed at field time (FIELD2, heap 32, FIELD1, heap 8).
//
// HEAP_ID_FIELD2 (11) holds every script context: Task_RunScripts allocates
// the environment, script bank, message banks, a 9-string MessageFormat and
// two 1024-character string buffers there. An item ball needs ~19.3 KB of it
// (its own bank plus the std fanfare bank).
//
// FIELD2 also holds the 69.6 KB Wild Query add-on. It survives battles, unlike
// FIELD1, which the field rebuilds into fragments too small for the add-on.
// The add-on loads only while FIELD2 keeps a 28 KB reserve for scripts. The
// 40 KB behavior catalog lives in FIELD1 with the same 28 KB reserve, sized
// for the lazy Cargo array that follows it (OVERWORLD_FIELD_QUERY_HEAP_RESERVE).
//
// Move 48 KB from FIELD1 to FIELD2. HEAP_ID_3's field-time total is unchanged.
.open "base/arm9.bin", 0x02000000

// FieldSystem_New: Heap_Create(HEAP_ID_3, HEAP_ID_FIELD2, 7 << 14 = 0x1C000)
.org 0x0203DFE2
    mov r2, #10                 // 10 << 14 = 0x28000

// Field mode table (_020FC5CC): FIELD1 heap size per mode. The 0xA0000 mode
// at 0x020FC5F0 already leaves more than 48 KB unused and is unchanged.
.org 0x020FC5D0
    .word 0xB8000
.org 0x020FC5D8
    .word 0xB8000
.org 0x020FC5E0
    .word 0xB8000
.org 0x020FC5E8
    .word 0xB8000
.org 0x020FC5F8
    .word 0xB8000

.close

// FieldDrawMapNameInfo_Create: the map-name popup keeps its lazy location-name
// bank (msg 279) open for the whole field. In FIELD1 it is allocated while map
// loading still holds the heap's top, so on some maps (Route 36) it lands
// mid-heap and later splits a ~99 KB hole into two blocks smaller than the
// behavior catalog. The catalog then fails to load: no Wild and no Follower.
// Keep the handle in FIELD2, which outlives FIELD1 and has room for it.
.open "base/overlay/overlay_0001.bin", 0x021E5900

// NewMsgDataFromNarc(MSGDATA_LOAD_LAZY, NARC_msgdata_msg, 279, HEAP_ID_FIELD1)
.org 0x021EFA0E
    mov r3, #11                 // HEAP_ID_FIELD2

// FieldDrawMapName_SetupWindow: keep its 32x5-tile (5120-byte) pixel buffer
// with the popup's FIELD2 message handle. A cold Route34 field was 1020 bytes
// short of the behavior catalog's FIELD1 admission reserve without this.
// Use the stock three-argument AddWindow and the same window template. Its
// synchronous allocation reads BgConfig.heapId; restore it before returning.
// RemoveWindow frees through the buffer's own heap header.
.org 0x021EF7BC
.area 0x2C, 0
    push {r4, r5, r6, lr}       // keep the native stack aligned
    mov r1, r0
    ldr r4, [r0, #0x1C]        // info->bgConfig
    ldr r5, [r4]               // original BgConfig.heapId
    mov r2, #11
    str r2, [r4]
    add r1, #0x20              // info->window
    mov r0, r4
    ldr r2, =FieldMapNameWindow_Template
    bl 0x0201D4F8              // AddWindow
    str r5, [r4]
    pop {r4, r5, r6, pc}
    .align 4
FieldMapNameWindow_Template:
    .byte 3, 0, 0, 32, 5, 11
    .hword 0x197
    .pool
.endarea

// ReadMModelFromNarcInternal: temporary map-object model/sequence/texture
// files are freed after upload or SpriteChangeWork. Keep FIELD1 first and
// borrow FIELD2 only if that allocation fails; both heaps have normal headers.
// Goldenrod -> Route34 needs a 6760-byte NPC texture when FIELD1's largest
// block is only 2588 bytes. The stock unchecked read then writes to NULL.
// Change only the atStart == FALSE branch; resident assets stay in FIELD1.
.org 0x021F9394
    mov r0, #4
    bl 0x022081A0               // OverworldFieldModel_AllocTemporary

// MapObjectRender_CreateQueue: each raw texture stays allocated until its
// VBlank upload and VWait release. The stock ten-load batch can exhaust both
// field heaps at a map border. Use the existing pending-texture queue to
// spread that work across updates, keeping its normal cancellation/lifetime.
// Both immediate loads and the load task use this shared limit.
.org 0x021FA88C
    mov r0, #1

.close
