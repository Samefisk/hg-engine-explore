/* Preserve the fixed overlay-2 ABI slots used by follower release. The
 * retired follower-interaction functions before them (0x0224F8FC up to the
 * release slot) host the Wild water sink. */
OUTPUT_ARCH(arm)
MEMORY {
        rom : ORIGIN = 0x0224F8FC, LENGTH = 0xE84
        ewram : ORIGIN = 0x0224F8FC, LENGTH = 0xE84
}

SECTIONS {
        .text : {
                FILL (0xABCD)
                ASSERT(ABSOLUTE(.) == 0x0224F8FC, "water sink entry moved");
                KEEP(*(.overworld_water_sink_entry))
                KEEP(*(.overworld_water_sink))
                KEEP(*(.overworld_water_sink_rodata))
                . = ALIGN(4);
                KEEP(*(.overworld_water_sink_data))
                ASSERT(ABSOLUTE(.) <= 0x0224FFF0,
                    "water sink overlaps its splash placer");
                . = ORIGIN(rom) + 0x6F4; /* 0x0224FFF0 */
                ASSERT(ABSOLUTE(.) == 0x0224FFF0, "water sink splash placer moved");
                KEEP(*(.overworld_water_sink_splash))
                . = ORIGIN(rom) + 0x6F4 + 0x4; /* 0x0224FFF4 */
                ASSERT(ABSOLUTE(.) == 0x0224FFF4, "skid aim entry moved");
                KEEP(*(.overworld_skid_aim_entry))
                . = ORIGIN(rom) + 0x6F4 + 0x8; /* 0x0224FFF8 */
                ASSERT(ABSOLUTE(.) == 0x0224FFF8, "water sink mirror placer moved");
                KEEP(*(.overworld_water_sink_mirror))
                ASSERT(ABSOLUTE(.) <= 0x02250000,
                    "water sink overlaps its per-frame pass");
                . = ORIGIN(rom) + 0x704; /* 0x02250000 */
                KEEP(*(.overworld_water_sink_frame))
                ASSERT(ABSOLUTE(.) <= 0x022500B0,
                    "water sink frame pass overlaps the grass gate");
                . = ORIGIN(rom) + 0x704 + 0xB0; /* 0x022500B0 */
                ASSERT(ABSOLUTE(.) == 0x022500B0, "water sink grass gate moved");
                KEEP(*(.overworld_water_sink_grass))
                KEEP(*(.overworld_water_sink_grass_data))
                ASSERT(ABSOLUTE(.) <= 0x02250110,
                    "water sink exceeds the retired follower-interaction graph");
                . = ORIGIN(rom) + 0x818; /* 0x02250114 */
                KEEP(*(.follower_release_tick))
                ASSERT(. <= ORIGIN(rom) + 0x818 + 0x180,
                    "follower release tick exceeds fixed ABI slot");
                . = ORIGIN(rom) + 0x818 + 0x180;
                KEEP(*(.follower_release_render))
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                *(.bss)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0x818 + 0x358,
                    "follower release render exceeds fixed ABI slot");
                . = ORIGIN(rom) + 0x818 + 0x358;
                KEEP(*(.follower_release_aggro))
                ASSERT(. <= ORIGIN(rom) + 0xBA4, /* 0x022504A0 */
                    "follower release aggro helper exceeds its slot");
                /* FollowMon_PlaceholdersSet up to the live allocator at
                 * 0x02250780 is reached only from the retired graph above. */
                . = ORIGIN(rom) + 0xBA4;
                ASSERT(ABSOLUTE(.) == 0x022504A0, "water sink player collision moved");
                KEEP(*(.overworld_water_sink_mount))
                . = ALIGN(4);
                KEEP(*(.overworld_water_sink_tail))
                ASSERT(. <= ORIGIN(rom) + LENGTH(rom),
                    "water sink tail reaches the live field allocator");
        } >rom = 0xff
}
