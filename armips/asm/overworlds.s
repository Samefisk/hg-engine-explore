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

.org 0x021F7908
.area 0x04, 0x00
    bl 0x021FA3E8
.endarea

.org 0x021F8E68
.area 0x04, 0x00
    // Mounted followers use the controller's shared facing vector. Every
    // other object still tail-calls the retail MapObject_SetFacingVector.
    bl 0x023BD3EC
.endarea

// ov01_021F8E70 resolves a sprite's render-offset mode with a linear scan on
// every draw. Wild objects cache the authenticated mode plus one in the first
// byte past the stock renderer's 0x18-byte private state (object + 0x120).
// Keep the stock lookup for an empty cache and for every object outside the
// three reserved wild-object ID ranges.
.org 0x021F8E70
.area 0x98, 0x00
OverworldWildSpawns_ApplyCachedRenderOffset:
    push {r3, r4, r5, r6, lr}
    sub sp, #0xC
    add r5, r1, #0
    add r6, r0, #0
    add r1, sp, #0
    add r4, r2, #0
    bl 0x0205F96C // MapObject_CopyFacingVector

    // Only C0-C9, D0-D9, and E0-E9 are custom wild presentation objects.
    ldr r0, [r6, #8]
    sub r0, #0xC0
    cmp r0, #0x29
    bhi @@stockLookup
    mov r1, #0xF
    and r0, r1
    cmp r0, #9
    bhi @@stockLookup

    add r0, r6, #0
    add r0, #0xF8
    add r0, #0x28
    ldrb r0, [r0]
    cmp r0, #0
    beq @@stockLookup
    cmp r0, #0x40
    bhi @@stockLookup
    sub r0, #1
    b @@applyMode

@@stockLookup:
    add r0, r6, #0
    bl 0x0205F25C // MapObject_GetSpriteID
    bl 0x021FA298 // exact stock render-offset mode lookup

@@applyMode:
    cmp r0, #0xA
    bne @@normalMode

    // Mode 10: up/down move Z by one unit; left/right move X by ten.
    cmp r5, #3
    bhi @@done
    mov r0, #1
    cmp r5, #1
    bls @@applyDelta
    mov r0, #0xA
    b @@applyDelta

@@normalMode:
    // Every other mode only offsets X for left/right by two units.
    cmp r5, #2
    bcc @@done
    cmp r5, #3
    bhi @@done
    mov r0, #2

@@applyDelta:
    lsl r0, #0xC
    mov r1, #1
    tst r5, r1
    beq @@positiveDelta
    neg r0, r0

@@positiveDelta:
    cmp r5, #1
    bls @@applyZ
    ldr r1, [r4]
    add r0, r1
    str r0, [r4]
    b @@done

@@applyZ:
    ldr r1, [r4, #8]
    add r0, r1
    str r0, [r4, #8]

@@done:
    add sp, #0xC
    pop {r3, r4, r5, r6, pc}
.endarea

.org 0x022061BA
.area 0x04, 0x00
    bl 0x021F771C
.endarea

.org 0x02206220
.area 0x04, 0x00
    bl 0x021F771C
.endarea

.org 0x022061E0
.area 0x04, 0x00
    bl 0x020205D8
.endarea

.org 0x02206246
.area 0x04, 0x00
    bl 0x020205D8
.endarea

.org 0x02209B18
.area 0x02209B44-., 0xFF
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

// Keep the exact personal-parameter hot path resident while overlay 150 owns
// the archive cache. Its stock envelope starts with an 8-byte Thumb dispatcher
// and mutable inline target initialized to an exact resident fallback thunk.
.org 0x0206FBE8
.area 0x08, 0x00
    ldr r3, =pokepersonalparaget_fallback | 1
    bx r3
    .pool
.endarea

.org 0x0206FBF0
.area 0x18, 0x00
pokepersonalparaget_fallback:
    mov r2, r1
    mov r1, #0
    b 0x0206FBC4 // PokeFormNoPersonalParaGet; form zero is exact identity
.endarea

// Dispatch the expanded level-up learnset loader through a resident pointer.
// The original function owns 0x02071FC8..0x02071FDB. Its final word is now a
// data-only slot, initialized to the exact C fallback and published to overlay
// 150 only after that overlay has authenticated and opened the validated NARC.
.org 0x02071FC8
.area 0x10, 0x00
    ldr r3, =0x02071FD8
    ldr r3, [r3]
    bx r3
    .pool
.endarea

.org 0x02071FD8
.area 0x04, 0x00
    .word loadleveluplearnset_handlealternateform_fallback | 1
.endarea

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
