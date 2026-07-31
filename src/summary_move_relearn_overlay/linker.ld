/* Overlay 154 */
OUTPUT_ARCH(arm)
MEMORY {
        /*
         * This cold application overlay ends before stock overlay 133 at
         * 0x023C22A0. OverlayManager owns its Summary-wide lifetime.
         */
        rom   : ORIGIN = 0x023C0400, LENGTH = 0x1EA0
        ewram : ORIGIN = 0x023C0400, LENGTH = 0x1EA0
}

SECTIONS {
        .text : {
                FILL (0xABCD)
                __text_start = . ;
                KEEP(*(.summary_move_relearn_api))
                ASSERT(SummaryMoveRelearn_Entry == ORIGIN(rom) + 0x08,
                    "Summary relearn fixed entry moved");
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                __text_end = . ;
        } >rom = 0xff

        .data : {
                *(.data)
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                *(.bss)
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(ewram) + LENGTH(ewram),
                    "Summary relearn overlay overlaps stock overlay 133");
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >ewram
}
