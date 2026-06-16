.nds
.thumb

.open "base/overlay/overlay_0001.bin", 0x021E5900

//.org 0x021F73C4
//
//.halfword NUM_OF_MON_OVERWORLDS + 0x1E4 // update the limiter
//// 0x1E4 is the start of the follower mon tags

.org 0x021F7394
nop

.equ OW_WILD_OBJECT_ID_START, 0xE0
.equ OW_WILD_MAX_SPAWNS, 10

// Overlay 1 only reads the follower shiny palette bit for hardcoded follower
// object IDs. Let overworld wild spawn IDs use the same param 2 bit without
// changing their object type or stealing the real follower object path.
.org 0x0220553C
.area 0x08, 0x00
    ldr r3, =OverworldWildSpawns_CheckShinyPaletteObject|1
    bx r3
    .pool
.endarea

.org 0x02205544
.area 0x20, 0x00
OverworldWildSpawns_IsPokemonPaletteObjectId:
    ldr r0, [r0, #8]
    cmp r0, #253
    beq @@isPokemonPaletteObject
    cmp r0, #250
    beq @@isPokemonPaletteObject
    cmp r0, #251
    beq @@isPokemonPaletteObject

    sub r0, #OW_WILD_OBJECT_ID_START
    cmp r0, #OW_WILD_MAX_SPAWNS
    bcc @@isPokemonPaletteObject

    mov r0, #0
    bx lr

@@isPokemonPaletteObject:
    mov r0, #1
    bx lr
.endarea

// The shiny palette loader repeats the follower object-ID gate after the
// shiny check. Admit wild object IDs there too, otherwise shiny wild objects
// pass the first check but still keep the normal palette.
.org 0x0220582C
.area 0x10, 0x00
    mov r0, r5
    bl OverworldWildSpawns_IsPokemonPaletteObjectId
    cmp r0, #0
    beq 0x0220586A
    b 0x0220583C
.endarea

// Battle/field transitions dispatch through a callback table with BLX. If a
// Thumb callback ever arrives with bit 0 cleared, the ARM9 enters valid Thumb
// bytes as ARM and halts. Keep the target Thumb-tagged at the dispatch point.
.org 0x021EFB42
.area 0x04, 0x00
    bl OverworldWildSpawns_TransitionDispatchThumbThunk
.endarea

.org 0x02209B18
.area 0x40, 0xFF
OverworldWildSpawns_CheckShinyPaletteObject:
    push {r4, lr}
    mov r4, r0

    bl OverworldWildSpawns_IsPokemonPaletteObjectId
    cmp r0, #0
    bne @@readShinyParam

    mov r0, #0
    pop {r4, pc}

@@readShinyParam:
    mov r0, r4
    mov r1, #2
    bl 0x0205F2F4 // MapObject_GetParam
    mov r1, #1
    and r0, r1
    pop {r4, pc}

OverworldWildSpawns_TransitionDispatchThumbThunk:
    push {r0, r3, r4, lr}
    ldr r2, [r2, r3]
    mov r0, #1
    orr r2, r0
    pop {r0, r3}
    blx r2
    pop {r4, pc}

    .pool
.endarea

.close


// limiter for hall of fame overworlds

.open "base/overlay/overlay_0063.bin", 0x0221BE20

.org 0x0221E448

.word NUM_OF_MONS

.close


// limiter for pokeathlon overworlds

.open "base/overlay/overlay_0096.bin", 0x021E5900

.org 0x021E91FC

.word NUM_OF_MONS

.close


.open "base/arm9.bin", 0x02000000

.org 0x0206A330
.word NUM_OF_MONS

.org 0x0206A338


.area 0x28

// rewrite this to use a byte per mon instead of a whole hword
// might rewrite to use a nybble eventually
// pokemon above brute bonnet can not have gender differences atm

// r0 is species
does_species_have_dimorphism:
    push {r3, lr}
    cmp r0, #0
    ble @@_invalidMon
    ldr r1, =(SPECIES_ARCEUS * 2)
    cmp r0, r1
    ble @@_validMon

@@_invalidMon:
    mov r0, #0
    b @@_getDimorphism

@@_validMon:
    sub r0, r0, #1

@@_getDimorphism:
    ldr r1, =0x020FECAE
    ldrb r0, [r1, r0]
    pop {r3, pc}

.pool

.endarea

.close
