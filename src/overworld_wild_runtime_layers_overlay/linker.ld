/* Overlay 158 */
/* Boot-resident Task-9 mutation, composition, cache, and provenance service. */
OUTPUT_ARCH(arm)
MEMORY {
        rom   : ORIGIN = 0x023B8400, LENGTH = 0x3580
        ewram : ORIGIN = 0x023B8400, LENGTH = 0x3580
}
SECTIONS {
        .text : {
                FILL (0xABCD)
                __text_start = . ;
                *overworld_wild_runtime_layers.o(.text*)
                *overworld_wild_runtime_layers.o(
                    .ow_wild_runtime_composition)
                *overworld_wild_runtime_layers.o(.rodata*)
                *overworld_wild_runtime_layers.o(.data*)
                . = ALIGN(4);
                __text_end = . ;
                __bss_start__ = . ;
                *overworld_wild_runtime_layers.o(.bss*)
                *(COMMON)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ - __bss_start__ <= 0x140,
                    "runtime layers overlay BSS exceeds fixed scratch budget");
                ASSERT(__bss_end__ <= 0x023BB900,
                    "runtime layers overlay consumed 0x80 headroom");
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom = 0xff
}
