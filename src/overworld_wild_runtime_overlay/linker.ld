/* Overlay 157 */
/* Boot-resident Task-8 runtime layer service. */
OUTPUT_ARCH(arm)
MEMORY {
        /* Heap 3 reserves this audited 0x1A80 boot-resident window directly
         * below frozen overlay 155. */
        rom   : ORIGIN = 0x023BB980, LENGTH = 0x1A80
        ewram : ORIGIN = 0x023BB980, LENGTH = 0x1A80
}
SECTIONS {
        .text : {
                FILL (0xABCD)
                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_runtime_entry))
                ASSERT(OverworldWildBehavior_LoadValidatedBundle == ORIGIN(rom),
                    "runtime bundle-loader entry moved");
                *(.init) *(.text*) *(.ctors) *(.dtors) *(.rodata*) *(.data*) *(.fini)
                . = ALIGN(4);
                __text_end = . ;
                __bss_start__ = . ;
                *(.bss*)
                *(COMMON)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ - __bss_start__ <= 0x140,
                    "runtime mutation overlay BSS exceeds fixed scratch budget");
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom) - 0x80,
                    "runtime mutation overlay consumed 0x80 resident headroom");
                ASSERT(__bss_end__ <= 0x023BD380,
                    "runtime mutation overlay exceeds audited resident window");
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom = 0xff
}
