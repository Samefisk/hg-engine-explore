/* Overlay 156 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023BC800, LENGTH = 0xC00
        ewram   : ORIGIN = 0x023BC800, LENGTH = 0xC00
}

SECTIONS {
        /* This resident overlay has no compiler-helper relocations. Keep the
         * generic overlay dependency from consuming its fixed reservation. */
        /DISCARD/ : { *thumb_help.o(.text) }

        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_runtime_entry))
                ASSERT(. == ORIGIN(rom) + 0x40,
                    "overworld wild runtime entry ABI changed");
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
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld wild runtime overlay exceeds resident reservation");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
