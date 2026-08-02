/* Overlay 156 */
OUTPUT_ARCH(arm)
MEMORY {
        rom   : ORIGIN = 0x023C0400, LENGTH = 0x1E00
        ewram : ORIGIN = 0x023C0400, LENGTH = 0x1E00
}
SECTIONS {
        .text : {
                FILL (0xABCD)
                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_behavior_validator_entry))
                ASSERT(. == ORIGIN(rom) + 0xC,
                    "behavior validator entry ABI changed");
                . = ALIGN(4);
                *(.init) *(.text) *(.ctors) *(.dtors) *(.rodata*) *(.fini) *(COMMON)
                __text_end = . ;
                __bss_start__ = . ;
                *(.bss)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + 0x1D00,
                    "behavior validator consumed private 0x60 reserve");
                ASSERT(__bss_end__ <= ORIGIN(rom) + 0x1D60,
                    "behavior validator exceeds guarded overlay-152 window");
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom = 0xff
}
