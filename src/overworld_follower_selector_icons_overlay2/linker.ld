/* Retired vanilla follower-interaction graph in overlay 2. */
OUTPUT_ARCH(arm)
MEMORY {
        rom : ORIGIN = 0x0224EF98, LENGTH = 0x8CC
        ewram : ORIGIN = 0x0224EF98, LENGTH = 0x8CC
}

SECTIONS {
        .text : {
                FILL (0xABCD)
                KEEP(*(.follower_selector_ow_entry))
                ASSERT(FollowerSelectorOverworld_Extract == ORIGIN(rom),
                    "follower selector overworld extractor ABI moved");
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                *(.bss)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + LENGTH(rom),
                    "follower selector overworld extractor exceeds retired graph");
        } >rom = 0xff
}
