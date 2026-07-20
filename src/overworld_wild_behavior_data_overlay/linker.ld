/* Overlay 150 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C3000, LENGTH = 0x1000
        ewram   : ORIGIN = 0x023C3000, LENGTH = 0x1000
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_behavior_data_entry))
                . = ALIGN(4);
                ASSERT(. == ORIGIN(rom) + 0x58,
                    "overworld wild behavior validator ABI moved");
                KEEP(*(.overworld_wild_behavior_data_validate))
                ASSERT(OverworldWildBehavior_ValidateOverlay
                        == ORIGIN(rom) + 0x58,
                    "overworld wild behavior validator symbol mismatch");
                KEEP(*(.overworld_wild_personal_cache_dispatch))
                ASSERT(. <= ORIGIN(rom) + 0xE0,
                    "overworld wild behavior validator overlaps personal-cache ABI");
                . = ORIGIN(rom) + 0xE0;
                KEEP(*(.overworld_wild_personal_cache_entry))
                ASSERT(gOverworldWildPersonalCacheOverlayEntry
                        == ORIGIN(rom) + 0xE0,
                    "overworld wild personal-cache ABI moved");
                ASSERT(. == ORIGIN(rom) + 0xEC,
                    "overworld wild personal-cache ABI size changed");
                KEEP(*(.overworld_wild_overlap_resolver_entry))
                ASSERT(gOverworldWildOverlapResolverEntry
                        == ORIGIN(rom) + 0xEC,
                    "overworld wild overlap-resolver ABI moved");
                ASSERT(. == ORIGIN(rom) + 0xF0,
                    "overworld wild overlap-resolver ABI size changed");
                . = ORIGIN(rom) + 0x100;
                KEEP(*(.overworld_wild_behavior_data_cleanup))
                ASSERT(OverworldWildBehavior_CleanupOverlay
                        == ORIGIN(rom) + 0x100,
                    "overworld wild behavior cleanup symbol mismatch");
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                *(COMMON)
                __text_end  = . ;
                ASSERT(__text_end <= ORIGIN(rom) + LENGTH(rom),
                    "overworld wild behavior overlay exceeds 4 KiB");

                __bss_start__ = . ;
                *(.bss)
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld wild behavior overlay BSS exceeds 4 KiB");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
