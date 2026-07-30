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
                ASSERT(. <= ORIGIN(rom) + 0x300,
                    "follower selector overworld extractor exceeds ABI slot");
                . = ORIGIN(rom) + 0x300;
                KEEP(*(.follower_release_bounce_entry))
                ASSERT(OverworldWildSpawns_StartFollowerReleaseBounce
                        == ORIGIN(rom) + 0x300,
                    "follower release bounce entry ABI moved");
                ASSERT(. <= ORIGIN(rom) + 0x600,
                    "follower release bounce entry exceeds ABI slot");
                . = ORIGIN(rom) + 0x600;
                KEEP(*(.follower_release_bounce_render))
                ASSERT(OverworldWildSpawns_RenderFollowerReleaseBounce
                        == ORIGIN(rom) + 0x600,
                    "follower release bounce render ABI moved");
                . = ORIGIN(rom) + 0x714;
                KEEP(*(.follower_release_return))
                ASSERT(OverworldWildSpawns_ReturnFollowerReleaseBall
                        == ORIGIN(rom) + 0x714,
                    "follower release return ABI moved");
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
