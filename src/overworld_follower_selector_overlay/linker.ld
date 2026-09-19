/* Overlay 152 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C0400, LENGTH = 0x2C00
        ewram   : ORIGIN = 0x023C0400, LENGTH = 0x2C00
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_follower_selector_entry))
                ASSERT(. == ORIGIN(rom) + 0x3C,
                    "overworld follower selector entry ABI changed");
                . = ALIGN(4);
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
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + 0x1E00,
                    "overworld follower selector core overlaps spatial tail");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff

        .overworld_spawn_spatial ORIGIN(rom) + 0x1E00 : {
                KEEP(*(.overworld_spawn_spatial_current_map_object))
                ASSERT(OverworldSpawnSpatial_IsCurrentMapObject
                        == ORIGIN(rom) + 0x1E00,
                    "spawn spatial current-object helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1E30,
                    "spawn spatial current-object helper exceeds its slot");
                . = ORIGIN(rom) + 0x1E30;
                KEEP(*(.overworld_spawn_spatial_distance_from_player))
                ASSERT(OverworldSpawnSpatial_DistanceFromPlayer
                        == ORIGIN(rom) + 0x1E30,
                    "spawn spatial distance helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1E64,
                    "spawn spatial distance helper exceeds its slot");
                . = ORIGIN(rom) + 0x1E64;
                KEEP(*(.overworld_spawn_spatial_object_on_player_tile))
                ASSERT(OverworldSpawnSpatial_IsObjectOnPlayerTile
                        == ORIGIN(rom) + 0x1E64,
                    "spawn spatial object-tile helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1EA0,
                    "spawn spatial selector tail exceeds resident slot");
                . = ORIGIN(rom) + 0x1EA0;
        } >rom = 0xff

        .overworld_behavior_conditions ORIGIN(rom) + 0x1EA0 : {
                KEEP(*(.overworld_behavior_condition_service_entry))
                ASSERT(gOverworldBehaviorConditionServiceEntry
                        == ORIGIN(rom) + 0x1EA0,
                    "condition service entry moved");
                ASSERT(. == ORIGIN(rom) + 0x1EB4,
                    "condition service entry size changed");
                *(.text.OverworldBehaviorCondition_*)
                ASSERT(. <= ORIGIN(rom) + LENGTH(rom),
                    "condition service exceeds field-linked overlay tail");
                . = ORIGIN(rom) + LENGTH(rom);
        } >rom = 0xff
}
