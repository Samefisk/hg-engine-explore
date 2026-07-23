/* Overlay 152 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C0400, LENGTH = 0x1EA0
        ewram   : ORIGIN = 0x023C0400, LENGTH = 0x1EA0
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_follower_selector_entry))
                ASSERT(. == ORIGIN(rom) + 0x38,
                    "overworld follower selector entry ABI changed");
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
                    "overworld follower selector overlay exceeds RAM region");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
