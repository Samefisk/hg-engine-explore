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
                KEEP(*(.overworld_wild_helper_flee_fallback_entry))
                ASSERT(gOverworldWildHelperFleeFallbackEntry
                        == ORIGIN(rom) + 0xF8,
                    "overworld wild helper flee fallback ABI moved");
                ASSERT(. <= ORIGIN(rom) + 0x100,
                    "overworld wild helper flee fallback exceeds ABI gap");
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
}
