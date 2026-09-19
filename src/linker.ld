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

        /* Keep the Walk pause resolver out of the fixed-address core ABI. */
        .overworld_walk_pause_variance 0x023DFFCC : {
                KEEP(*(.overworld_walk_pause_variance))
        } >rom = 0xff
        ASSERT(SIZEOF(.overworld_walk_pause_variance) <= 52,
                "Walk pause variance resolver exceeds its 52-byte tail budget")
}
