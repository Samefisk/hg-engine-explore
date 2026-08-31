/* Overlay 149 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023CCFD8, LENGTH = 0xB028
        ewram   : ORIGIN = 0x023CCFD8, LENGTH = 0xB028
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_spawns_prefix_bss))
                ASSERT(. <= 0x28,
                    "overworld wild spawns prefix exceeds field-overlay gap");
                . = 0x28;
                KEEP(*(.overworld_wild_spawns_entry))
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0xB000,
                    "overworld wild spawns overlay exceeds stable file slot");
                /* Keep later overlay FAT offsets stable when code shrinks. */
                . = ORIGIN(rom) + 0xB000;
                __text_end  = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                *(.bss)
                *(COMMON)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__text_end <= ORIGIN(rom) + 0xB000,
                    "overworld wild spawns overlay exceeds packaged FAT slot");
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld wild spawns overlay exceeds reserved RAM");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
