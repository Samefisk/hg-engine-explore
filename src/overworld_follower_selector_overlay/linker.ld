/* Overlay 152 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023C0400, LENGTH = 0x2C00
        ewram   : ORIGIN = 0x023C0400, LENGTH = 0x2C00
        binding : ORIGIN = 0x02208600, LENGTH = 0x100
}

SECTIONS {
        .overworld_throw_binding_refresh ORIGIN(binding) : {
                KEEP(*(.overworld_throw_binding_refresh))
                ASSERT(ABSOLUTE(OverworldThrowBinding_Refresh) == 0x02208600,
                    "private Throw binding refresh moved");
                KEEP(*(.overworld_throw_binding_refresh.tail))
                ASSERT(ABSOLUTE(.) <= ORIGIN(binding) + LENGTH(binding),
                    "Throw binding refresh exceeds the existing Field reserve");
        } > binding = 0

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
                *(.text.OverworldVision_IsValidSpec)
                ASSERT(. <= ORIGIN(rom) + 0x1EA0,
                    "spawn spatial selector tail exceeds resident slot");
                . = ORIGIN(rom) + 0x1EA0;
        } >rom = 0xff

        /* The static spatial entry keeps IsValidSpec; all other Vision code
         * is addon-local with the pure Condition engine. */
        /DISCARD/ : { *(.text.OverworldVision_*) }

        .overworld_behavior_conditions ORIGIN(rom) + 0x1EA0 : {
                KEEP(*(.overworld_behavior_condition_service_entry))
                ASSERT(gOverworldBehaviorConditionServiceEntry
                        == ORIGIN(rom) + 0x1EA0,
                    "condition service entry moved");
                ASSERT(. == ORIGIN(rom) + 0x1EB8,
                    "condition service entry size changed");
                KEEP(*(.overworld_behavior_condition_service_gate))
                ASSERT(OverworldBehaviorConditionService_Get
                        == ORIGIN(rom) + 0x1EB8,
                    "condition service gate moved");
                ASSERT(ABSOLUTE(.) <= 0x023C22F0,
                    "condition lifetime gate overlaps private query service");
                . = ORIGIN(rom) + 0x1EF0;
                KEEP(*(.overworld_query_code_addon_service))
                ASSERT(ABSOLUTE(gOverworldQueryCodeAddonServiceEntry) == 0x023C22F0,
                    "private query addon service moved");
                ASSERT(ABSOLUTE(.) == 0x023C2308, "private query service size differs");
                KEEP(*(.overworld_query_code_addon_state))
                ASSERT(ABSOLUTE(gOverworldQueryCodeAddonState) == 0x023C2308,
                    "private query state moved");
                ASSERT(ABSOLUTE(.) == 0x023C2324, "private query state size differs");
                *(.text.Addon_*)
                *(.text.OverworldQueryCodeAddon_*)
                *(.text.Service_*)
                *(.text.Condition_Current)
                *(.text.Field_Service)
                *(.rodata*)
                ASSERT(ABSOLUTE(.) <= 0x023C2A80,
                    "query bootstrap overlaps current-context acquire");
                . = ORIGIN(rom) + 0x2680;
                KEEP(*(.overworld_query_code_addon_field_acquire_current))
                ASSERT(ABSOLUTE(OverworldQueryCodeAddonField_AcquireCurrent) == 0x023C2A80,
                    "private current-context acquire moved");
                KEEP(*(.overworld_query_code_addon_field_acquire_current.tail))
                ASSERT(ABSOLUTE(.) <= 0x023C2B00,
                    "current-context acquire overlaps fixed Field acquire");
                . = ORIGIN(rom) + 0x2700;
                KEEP(*(.overworld_query_code_addon_field_acquire))
                ASSERT(ABSOLUTE(OverworldQueryCodeAddonField_Acquire) == 0x023C2B00,
                    "Field query acquire moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2B70, "Field query acquire exceeds its slot");
                . = ORIGIN(rom) + 0x2770;
                KEEP(*(.overworld_query_code_addon_field_unload))
                ASSERT(ABSOLUTE(OverworldQueryCodeAddonField_Unload) == 0x023C2B70,
                    "Field query unload moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2BA0, "Field query unload exceeds its slot");
                . = ORIGIN(rom) + 0x27A0;
                KEEP(*(.overworld_throw_observe))
                ASSERT(ABSOLUTE(OverworldThrowObservation_Observe) == 0x023C2BA0,
                    "private Throw observation moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2C1C, "Throw observation overlaps private notice callers");
                . = ORIGIN(rom) + 0x281C;
                KEEP(*(.overworld_wild_notice_callers))
                ASSERT(ABSOLUTE(.) == 0x023C2D80, "private notice caller reservation differs");
                __query_stock_import_begin = ABSOLUTE(.);
                KEEP(*(.overworld_query_stock_coordinate_import))
                ASSERT(__query_stock_import_begin == 0x023C2D80,
                    "private stock import check moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2DA0,
                    "private stock import check overlaps fixed BindingPosition");
                . = ORIGIN(rom) + 0x29A0;
                KEEP(*(.overworld_throw_binding_position))
                ASSERT(ABSOLUTE(OverworldThrowObservation_BindingPosition) == 0x023C2DA0,
                    "private Throw binding read moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2EB0,
                    "Throw binding read overlaps private Query rebind");
                . = ORIGIN(rom) + 0x2AB0;
                KEEP(*(.overworld_query_code_addon_rebind))
                ASSERT(ABSOLUTE(OverworldQueryCodeAddon_Rebind) == 0x023C2EB0,
                    "private Query rebind moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2F74, "private rebind overlaps publication capture");
                . = ORIGIN(rom) + 0x2B74;
                KEEP(*(.overworld_condition_publication_capture))
                ASSERT((ABSOLUTE(OverworldConditionPublication_CapturePrior) & ~1) == 0x023C2F74, "private publication capture moved");
                ASSERT(ABSOLUTE(.) <= 0x023C2FCC, "publication capture overlaps changed mask");
                . = ORIGIN(rom) + 0x2BCC;
                KEEP(*(.overworld_condition_publication_changed))
                ASSERT((ABSOLUTE(OverworldConditionPublication_ChangedMask) & ~1) == 0x023C2FCC, "private publication changed mask moved");
                __query_addon_bootstrap_end = ABSOLUTE(.);
                ASSERT(. <= ORIGIN(rom) + LENGTH(rom) - 0x10,
                    "condition service leaves less than 16 bytes headroom");
                . = ORIGIN(rom) + LENGTH(rom);
        } >rom = 0xff
}
