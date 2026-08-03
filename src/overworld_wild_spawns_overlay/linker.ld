/* Overlay 149 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023CD000, LENGTH = 0xB000
        ewram   : ORIGIN = 0x023CD000, LENGTH = 0xB000
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_spawns_entry))
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.rodata.*)
                *(.data)
                *(.fini)
                *(COMMON)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0xAEC4,
                    "overworld wild spawns overlay exceeds sealed text boundary");
                . = ORIGIN(rom) + 0xAEC4;
                __text_end  = . ;

                __bss_start__ = . ;
                *(.bss)
                . = ALIGN(4);
                __bss_end__ = . ;
        ASSERT(__bss_end__ <= ORIGIN(rom) + 0xAF80,
            "overworld wild spawns overlay consumed 0x80 reserve");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
