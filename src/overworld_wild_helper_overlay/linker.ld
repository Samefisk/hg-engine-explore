/* Overlay 151 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C4000, LENGTH = 0x4000
        ewram   : ORIGIN = 0x023C4000, LENGTH = 0x4000
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_helper_entry))
                . = ALIGN(4);
                KEEP(*(.overworld_wild_helper_validate))
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0xF8,
                    "overworld wild helper validator overlaps flee fallback ABI");
                . = ORIGIN(rom) + 0xF8;
                LONG(0)
                LONG(0)
                . = ORIGIN(rom) + 0x100;
                KEEP(*(.overworld_wild_helper_lifecycle))
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                __text_end  = . ;

                __bss_start__ = . ;
                *(.bss)
                __bss_end__ = . ;
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff

        /* Keep the existing four-byte data host before the fixed spatial
         * tail. The helper's bss is part of the historical .text envelope. */
        .data : {
                *(.data)
        } >rom = 0xff

        ASSERT(ADDR(.data) + SIZEOF(.data) <= ORIGIN(rom) + 0x3DF8,
            "wild helper core overlaps condition visibility population")

        .overworld_condition_visibility_populate ORIGIN(rom) + 0x3DF8 : {
                KEEP(*(.overworld_condition_visibility_populate))
                ASSERT(OverworldConditionVisibility_PopulateWorld
                        == ORIGIN(rom) + 0x3DF8,
                    "condition visibility population moved");
                ASSERT(. <= ORIGIN(rom) + 0x3EA8,
                    "condition visibility population exceeds helper slot");
                . = ORIGIN(rom) + 0x3EA8;
        } >rom = 0xff

        .overworld_condition_visibility_trace ORIGIN(rom) + 0x3EA8 : {
                KEEP(*(.overworld_condition_visibility_trace))
                ASSERT(OverworldConditionVisibility_TraceBlocked
                        == ORIGIN(rom) + 0x3EA8,
                    "condition visibility trace moved");
                ASSERT(. <= ORIGIN(rom) + 0x3F60,
                    "condition visibility trace exceeds helper tail");
                . = ORIGIN(rom) + 0x3F60;
        } >rom = 0xff

        .overworld_spawn_spatial ORIGIN(rom) + 0x3F60 : {
                KEEP(*(.overworld_spawn_spatial_player_tile))
                ASSERT(OverworldSpawnSpatial_IsPlayerTile
                        == ORIGIN(rom) + 0x3F60,
                    "spawn spatial player-tile helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x3F98,
                    "spawn spatial player-tile helper exceeds its slot");
                . = ORIGIN(rom) + 0x3F98;
                KEEP(*(.overworld_spawn_spatial_player_front_tile))
                ASSERT(OverworldSpawnSpatial_IsPlayerFrontTile
                        == ORIGIN(rom) + 0x3F98,
                    "spawn spatial player-front helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x4000,
                    "spawn spatial helper tail exceeds resident slot");
                . = ORIGIN(rom) + 0x4000;
        } >rom = 0xff
}
