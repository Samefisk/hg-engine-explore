/* Overlay 129 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023D8000 + 0x600, LENGTH = 0x8000-0x600
        ewram   : ORIGIN = 0x023D8000 + 0x600, LENGTH = 0x8000-0x600
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                *(.init)
                *(EXCLUDE_FILE (build/thumb_help.o) .text)
                /* Use existing filler without moving generic core exports. */
                __item_data_start = .;
                KEEP(*(.item_data_none))
                __item_data_end = .;
                ASSERT(__item_data_end - __item_data_start <= 64,
                    "private no-item data loader exceeds its budget");
                ASSERT(. <= 0x023DEDF0,
                    "core code overlaps private Hop lease leaf");
                . = ORIGIN(rom) + 0x67F0;
                KEEP(*(.overworld_hop_lease))
                ASSERT(ABSOLUTE(OverworldHopPresentation_Acquire) == 0x023DEDF0,
                    "private Hop lease leaf moved");
                ASSERT(. <= 0x023DEE44,
                    "private Hop lease leaf exceeds existing 84-byte gap");
                . = ORIGIN(rom) + 0x6844;
                build/thumb_help.o(.text)
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

        .data : {
                *(.data)
                *(.data.*)
        } >rom = 0xff

        .overworld_wild_turn_skid : {
                KEEP(*(.overworld_wild_turn_skid))
        } >rom = 0xff

        /* Append only: existing core exports and their callers stay fixed. */
        .overworld_grass_effect_guard : {
                KEEP(*(.overworld_grass_effect_guard))
        } >rom = 0xff
        ASSERT(SIZEOF(.overworld_grass_effect_guard) <= 32,
                "grass-effect allocation guard exceeds its 32-byte budget")

        .overworld_dust_effect_guard : {
                KEEP(*(.overworld_dust_effect_guard))
        } >rom = 0xff
        ASSERT(SIZEOF(.overworld_dust_effect_guard) <= 32,
                "dust-effect allocation guard exceeds its 32-byte budget")

        .overworld_effect_pool_capacity : {
                KEEP(*(.overworld_effect_pool_capacity))
        } >rom = 0xff
        ASSERT(SIZEOF(.overworld_effect_pool_capacity) <= 20,
                "effect-pool capacity hook exceeds its 20-byte tail budget")
        ASSERT(ADDR(.overworld_effect_pool_capacity)
                    + SIZEOF(.overworld_effect_pool_capacity) <= 0x023DFFCC,
                "effect guards overlap the Walk pause resolver")

        .overworld_bubble_effect_guard : {
                KEEP(*(.overworld_bubble_effect_guard))
        } >rom = 0xff
        ASSERT(SIZEOF(.overworld_bubble_effect_guard) <= 48,
                "bubble model admission exceeds its 48-byte tail budget")
        ASSERT(ADDR(.overworld_bubble_effect_guard)
                    + SIZEOF(.overworld_bubble_effect_guard) <= 0x023DFFCC,
                "bubble model admission overlaps the Walk pause resolver")

        /* Keep the Walk pause resolver out of the fixed-address core ABI. */
        .overworld_walk_pause_variance 0x023DFFCC : {
                KEEP(*(.overworld_walk_pause_variance))
        } >rom = 0xff
        ASSERT(SIZEOF(.overworld_walk_pause_variance) <= 52,
                "Walk pause variance resolver exceeds its 52-byte tail budget")
}
