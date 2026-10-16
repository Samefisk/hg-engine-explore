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
// The add-on loads only while FIELD2 keeps a 32 KB reserve for scripts. The
// 53.3 KB behavior catalog lives in FIELD1.
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
