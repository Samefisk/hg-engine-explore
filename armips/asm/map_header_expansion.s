.nds
.thumb

// Map header expansion: map IDs 540..MAP_HEADER_COUNT-1.
// Design, addresses and limits: documentation/map-system/header-expansion.md.
// Static check after a build:
//   python3 -B -m tools.maps.header_table verify --arm9 base/arm9.bin --root base/root
//
// The vanilla 540-entry table at 0x020F6BE0 stays in place, and so do all 27
// MapHeader_* getters. Every getter calls the static bounds check at 0x0203B268,
// then reads (0x020F6BE0 + field) + returned_id * 24. The check now returns
// either the vanilla ID or a "storage index" whose row lands in an extension
// slot outside the table. Resident RAM is full, so the slots live in two dead
// vanilla ARM9 data blocks:
//   B: 0x020FFC10..0x020FFE2B  stock icon-palette table (readers replaced by
//      the PokeIconCgxPatternGet, IconPalGet and GetMonIconPalette hooks)
//   A: 0x020FF134..0x020FF462  tail of the retired gSpeciesToOWNum table
//      (pokedex.s code owns 0x020FF088..0x020FF134)
// Both slot bases are 24-byte aligned relative to the table base, so each
// storage index is an exact row number.

MAP_HEADER_COUNT equ 600 // logical map ID count; multiple of 4, 544..792

MAP_HEADER_TABLE equ 0x020F6BE0
MAP_HEADER_VANILLA_COUNT equ 540
MAP_HEADER_SIZE equ 24
MAP_HEADER_EXT_FILE equ "base/map_header_ext.bin" // written by tools.maps before armips

MAP_HEADER_EXT_B_BASE equ 0x020FFC10
MAP_HEADER_EXT_B_SLOTS equ 20
MAP_HEADER_EXT_B_LIMIT equ 0x020FFE2B // 0x020FFE2B and later bytes are live data
MAP_HEADER_EXT_A_TOP equ 0x020FF460 // last 24-byte row end below 0x020FF462
MAP_HEADER_EXT_A_MAX_SLOTS equ 32
MAP_HEADER_EXT_A_FLOOR equ 0x020FF134 // end of the pokedex.s code in the same block

GF_AssertFail_Address equ 0x0202551C

.if (MAP_HEADER_COUNT % 4) != 0 || MAP_HEADER_COUNT <= MAP_HEADER_VANILLA_COUNT || MAP_HEADER_COUNT > MAP_HEADER_VANILLA_COUNT + 252
    .error "MAP_HEADER_COUNT must be a multiple of 4 in 544..792"
.endif
.if ((MAP_HEADER_EXT_B_BASE - MAP_HEADER_TABLE) % MAP_HEADER_SIZE) != 0 || ((MAP_HEADER_EXT_A_TOP - MAP_HEADER_TABLE) % MAP_HEADER_SIZE) != 0
    .error "map header extension slots are not row-aligned with the vanilla table"
.endif

// armips opens every .incbin file while parsing, even in a false .if, so a
// missing extension file falls back to this source with zero bytes taken.
// equ is textual substitution: every composite value below is parenthesized.
MAP_HEADER_EXT_SOURCE equ (fileexists(MAP_HEADER_EXT_FILE) ? MAP_HEADER_EXT_FILE : "armips/asm/map_header_expansion.s")
.if fileexists(MAP_HEADER_EXT_FILE)
    MAP_HEADER_EXT_FILE_SIZE equ (filesize(MAP_HEADER_EXT_FILE))
.else
    MAP_HEADER_EXT_FILE_SIZE equ 0
.endif
.if (MAP_HEADER_EXT_FILE_SIZE % MAP_HEADER_SIZE) != 0
    .error "base/map_header_ext.bin is not a whole number of 24-byte map headers"
.endif

MAP_HEADER_EXT_DEFINED equ (MAP_HEADER_EXT_FILE_SIZE / MAP_HEADER_SIZE)
.if MAP_HEADER_EXT_DEFINED > MAP_HEADER_COUNT - MAP_HEADER_VANILLA_COUNT
    .error "more extension map headers than MAP_HEADER_COUNT allows"
.endif
.if MAP_HEADER_EXT_DEFINED > MAP_HEADER_EXT_B_SLOTS + MAP_HEADER_EXT_A_MAX_SLOTS
    .error "more extension map headers than the resident slots hold (52)"
.endif

.if MAP_HEADER_EXT_DEFINED > MAP_HEADER_EXT_B_SLOTS
    MAP_HEADER_EXT_B_DEFINED equ MAP_HEADER_EXT_B_SLOTS
.else
    MAP_HEADER_EXT_B_DEFINED equ MAP_HEADER_EXT_DEFINED
.endif
MAP_HEADER_EXT_A_DEFINED equ (MAP_HEADER_EXT_DEFINED - MAP_HEADER_EXT_B_DEFINED)
MAP_HEADER_EXT_A_BASE equ (MAP_HEADER_EXT_A_TOP - MAP_HEADER_EXT_A_DEFINED * MAP_HEADER_SIZE)

// Row numbers relative to MAP_HEADER_TABLE. idx = mapId - 540.
// B rows: B_ROW + idx; A rows: A_ROW + idx (idx >= B_DEFINED).
MAP_HEADER_EXT_B_ROW equ ((MAP_HEADER_EXT_B_BASE - MAP_HEADER_TABLE) / MAP_HEADER_SIZE)
MAP_HEADER_EXT_A_ROW equ ((MAP_HEADER_EXT_A_BASE - MAP_HEADER_TABLE) / MAP_HEADER_SIZE - MAP_HEADER_EXT_B_DEFINED)

.open "base/arm9.bin", 0x02000000

.if readu16("base/arm9.bin", 0x0203B268 - 0x02000000) != 0xB508 && readu16("base/arm9.bin", 0x0203B268 - 0x02000000) != 0x4900
    .error "MapNumberBoundsCheck at 0x0203B268 is not the expected code"
.endif
.if readu32("base/arm9.bin", 0x0203B28C - 0x02000000) != MAP_HEADER_TABLE + 1
    .error "MapHeader_GetAreaDataBank no longer reads the vanilla header table"
.endif

// static u32 MapNumberBoundsCheck(u32 mapId), 20 bytes up to the first getter.
// r1 is already clobbered by the stock body; r2/r3 are caller-saved and every
// getter preserves its own inputs before the call.
.org 0x0203B268
.area 0x0203B27C - 0x0203B268, 0x00
    ldr r1, =MapHeaderExt_BoundsCheck | 1
    bx r1
.pool
.endarea

// Slot block B: B slots, then the bounds check.
.org MAP_HEADER_EXT_B_BASE
.area MAP_HEADER_EXT_B_LIMIT - MAP_HEADER_EXT_B_BASE
MapHeaderExt_SlotsB:
.area MAP_HEADER_EXT_B_SLOTS * MAP_HEADER_SIZE, 0x00
.if MAP_HEADER_EXT_B_DEFINED > 0
    .incbin MAP_HEADER_EXT_SOURCE, 0, MAP_HEADER_EXT_B_DEFINED * MAP_HEADER_SIZE
.endif
.endarea

.align 4
// r0 = map ID; returns the row to read from MAP_HEADER_TABLE.
MapHeaderExt_BoundsCheck:
    mov r1, #(MAP_HEADER_VANILLA_COUNT >> 2)
    lsl r1, r1, #2
    sub r2, r0, r1
    bcc @@vanilla
    cmp r2, #MAP_HEADER_EXT_B_DEFINED
    blo @@slotB
    cmp r2, #MAP_HEADER_EXT_DEFINED
    blo @@slotA
    cmp r2, #(MAP_HEADER_COUNT - MAP_HEADER_VANILLA_COUNT)
    bhs @@invalid
    mov r0, #1 // defined-less extension ID: use the MAP_NOTHING header
@@vanilla:
    bx lr
@@slotB:
    ldr r0, =MAP_HEADER_EXT_B_ROW
    add r0, r0, r2
    bx lr
@@slotA:
    ldr r0, =MAP_HEADER_EXT_A_ROW
    add r0, r0, r2
    bx lr
@@invalid:
    push {r3, lr}
    bl GF_AssertFail_Address
    mov r0, #1 // MAP_NOTHING, as in the stock check
    pop {r3, pc}
.pool
MapHeaderExt_BoundsCheckEnd:
.endarea

// Slot block A: top-aligned so the gap after the pokedex.s code stays free.
.if MAP_HEADER_EXT_A_DEFINED > 0
    .if MAP_HEADER_EXT_A_BASE < MAP_HEADER_EXT_A_FLOOR
        .error "map header slot block A overlaps the pokedex.s code"
    .endif
    .if defined(get_dex_num_patch)
        .if MAP_HEADER_EXT_A_BASE < get_dex_num_patch + 0x20
            .error "map header slot block A overlaps the pokedex.s code"
        .endif
    .endif
    .org MAP_HEADER_EXT_A_BASE
MapHeaderExt_SlotsA:
    .area MAP_HEADER_EXT_A_DEFINED * MAP_HEADER_SIZE
        .incbin MAP_HEADER_EXT_SOURCE, MAP_HEADER_EXT_B_DEFINED * MAP_HEADER_SIZE, MAP_HEADER_EXT_A_DEFINED * MAP_HEADER_SIZE
    .endarea
.endif

// MapMarkingsSave_MapIDisValid: mapID >= MAP_ID_MAX is an empty marking.
.if readu16("base/arm9.bin", 0x0202F376 - 0x02000000) != 0x2087 && readu16("base/arm9.bin", 0x0202F376 - 0x02000000) != (0x2000 | (MAP_HEADER_COUNT >> 2))
    .error "map-marking MAP_ID_MAX compare at 0x0202F376 is not the expected code"
.endif
.org 0x0202F376
    mov r0, #(MAP_HEADER_COUNT >> 2)

.close

// Pokegear radio "Pokemon Talk" landmark loop: for (i = 0; i < MAP_ID_MAX; i++).
// Overlay 101 is compressed in the stock ROM; patch it only once the build
// decompresses it (bit 24 of its y9 flags is clear). Unpatched, new maps are
// never sampled by the show; nothing reads out of bounds.
.if (readu32("base/overarm9.bin", 101 * 0x20 + 0x1C) & 0x01000000) == 0
    .open "base/overlay/overlay_0101.bin", 0x021E7740
    .if readu16("base/overlay/overlay_0101.bin", 0x021F707C - 0x021E7740) != 0x2087 && readu16("base/overlay/overlay_0101.bin", 0x021F707C - 0x021E7740) != (0x2000 | (MAP_HEADER_COUNT >> 2))
        .error "Pokemon Talk MAP_ID_MAX loop at 0x021F707C is not the expected code"
    .endif
    .org 0x021F707C
        mov r0, #(MAP_HEADER_COUNT >> 2)
    .close
.else
    .warning "overlay 101 is compressed: Pokemon Talk still samples map IDs below 540 only"
.endif
