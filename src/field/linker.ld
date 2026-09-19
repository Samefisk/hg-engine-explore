/* Overlay 131 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C8000, LENGTH = 0x5000
        ewram   : ORIGIN = 0x023C8000, LENGTH = 0x5000
}

OverworldFieldTerrainStream_Apply = 0x023BFC60 | 1;

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
                ASSERT(. <= ORIGIN(rom) + 0xD0,
                    "overworld follower selector task poll exceeds ABI reserve");
                . = ORIGIN(rom) + 0xD0;
                KEEP(*(.overworld_follower_transition_queue_append))
                ASSERT(OverworldFollowerTransitionQueue_AppendResident
                        == ORIGIN(rom) + 0xD0,
                    "follower transition queue append moved");
                ASSERT(. <= ORIGIN(rom) + 0x108,
                    "follower transition queue append exceeds ABI reserve");
                . = ORIGIN(rom) + 0x108;
                KEEP(*(.overworld_follower_transition_queue_pop))
                ASSERT(OverworldFollowerTransitionQueue_PopResident
                        == ORIGIN(rom) + 0x108,
                    "follower transition queue pop moved");
                ASSERT(. <= ORIGIN(rom) + 0x130,
                    "follower transition queue pop exceeds ABI reserve");
                . = ORIGIN(rom) + 0x130;
                KEEP(*(.overworld_follower_transition_queue))
                ASSERT(gOverworldFollowerTransitionQueueStorage
                        == ORIGIN(rom) + 0x130,
                    "follower transition queue storage moved");
                ASSERT(. <= ORIGIN(rom) + 0x138,
                    "follower transition queue storage exceeds ABI reserve");
                . = ORIGIN(rom) + 0x138;
                KEEP(*(.overworld_field_terrain_stream))
                ASSERT(OverworldFieldService_TerrainStream
                        == ORIGIN(rom) + 0x138,
                    "field terrain stream moved");
                ASSERT(. <= ORIGIN(rom) + 0x148,
                    "field terrain stream exceeds ABI reserve");
                . = ORIGIN(rom) + 0x148;
                KEEP(*(.overworld_follower_selector_state))
                ASSERT(gOverworldFollowerSelectorStateStorage
                        == ORIGIN(rom) + 0x148,
                    "overworld follower selector state moved");
                KEEP(*(.overworld_field_private_flags))
                ASSERT(. <= ORIGIN(rom) + 0x14C,
                    "overworld field private flags exceed ABI padding");
                . = ALIGN(4);
                KEEP(*(.overworld_follower_selector_ow_resolver))
                ASSERT(FollowerSelector_ResolveOverworldTag
                        == ORIGIN(rom) + 0x14C,
                    "overworld follower selector resolver moved");
                ASSERT(. <= ORIGIN(rom) + 0x154,
                    "overworld follower selector resolver exceeds ABI reserve");
                . = ORIGIN(rom) + 0x154;
                KEEP(*(.overworld_field_mount_presentation_entry))
                ASSERT(gOverworldFieldMountPresentationEntry
                        == ORIGIN(rom) + 0x154,
                    "overworld field mount presentation entry moved");
                ASSERT(. == ORIGIN(rom) + 0x164,
                    "overworld field mount presentation entry ABI changed");
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.fini)
                __text_end  = . ;
        } >rom = 0xff

        .data : {
                *(.data)
        } >rom = 0xff

        .overworld_mount_field_input_host ORIGIN(rom) + 0x4E98 : {
                KEEP(*(.overworld_mount_field_input_host))
                . = ALIGN(4);
        } >rom = 0xff
        ASSERT(ADDR(.data) + SIZEOF(.data) <= ORIGIN(rom) + 0x4E98,
            "field data overlaps mount field-input host")
        ASSERT(OverworldMount_ProcessFieldInput == ORIGIN(rom) + 0x4E98,
            "mount field-input host moved")
        ASSERT(SIZEOF(.overworld_mount_field_input_host) <= 0x100,
            "mount field-input host exceeds private reserve")

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                *(.bss)
                *(COMMON)
                __bss_end__ = . ;
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom

        .walking_friendship 0x023CCF90 : {
                KEEP(*(.walking_friendship))
        } >rom = 0xff
        ASSERT(ADDR(.bss) + SIZEOF(.bss) <= 0x023CCF90,
            "field state overlaps walking friendship wrapper")
        ASSERT(OverworldField_ApplyWalkingFriendship == 0x023CCF90,
            "walking friendship wrapper moved")
        ASSERT(ADDR(.walking_friendship) + SIZEOF(.walking_friendship) <= 0x023CCFD8,
            "walking friendship wrapper exceeds field tail")

        /* asm/field/resident_helpers.s supplies typed imports to the existing
         * resident Thumb bridges. Raw stock ARM aliases produce a Thumb BL
         * without changing instruction mode and lock field initialization. */
        ASSERT(ADDR(.bss) + SIZEOF(.bss) <= 0x023CCFD8,
            "field overlay overlaps overworld wild overlay prefix")
}
