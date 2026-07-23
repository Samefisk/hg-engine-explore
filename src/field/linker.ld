/* Overlay 131 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C8000, LENGTH = 0x5000
        ewram   : ORIGIN = 0x023C8000, LENGTH = 0x5000
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_field_service_entry))
                . = ALIGN(4);
                KEEP(*(.overworld_follower_selector_task_poll))
                ASSERT(OverworldFollowerSelector_TaskPoll
                        == ORIGIN(rom) + 0x10,
                    "overworld follower selector task poll moved");
                ASSERT(. <= ORIGIN(rom) + 0x148,
                    "overworld follower selector task poll exceeds ABI reserve");
                . = ORIGIN(rom) + 0x148;
                KEEP(*(.overworld_follower_selector_state))
                ASSERT(gOverworldFollowerSelectorStateStorage
                        == ORIGIN(rom) + 0x148,
                    "overworld follower selector state moved");
                . = ALIGN(4);
                KEEP(*(.overworld_follower_selector_ow_resolver))
                ASSERT(FollowerSelector_ResolveOverworldTag
                        == ORIGIN(rom) + 0x14C,
                    "overworld follower selector resolver moved");
                ASSERT(. <= ORIGIN(rom) + 0x154,
                    "overworld follower selector resolver exceeds ABI reserve");
                . = ORIGIN(rom) + 0x154;
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
                __bss_end__ = . ;
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
