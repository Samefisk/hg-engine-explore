/* Overlay 153 */
OUTPUT_ARCH(arm)
MEMORY {

        /*
         * Boot-resident move-history code occupies the otherwise unused gap
         * after every stock overlay and before custom overlay 152.
         */
        rom     : ORIGIN = 0x023BE400, LENGTH = 0x2000
        ewram   : ORIGIN = 0x023BE400, LENGTH = 0x2000
}

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                KEEP(*(.pokemon_move_history_api))
                /*
                 * These entries must preserve r3 (and, for candidates, the
                 * stacked fifth argument), so keep their implementations
                 * within range of the fixed-width Thumb-1 branches.
                 */
                KEEP(*(.pokemon_move_history_short_branch_targets))
                ASSERT(MoveHistoryEntry_Init == ORIGIN(rom) + 0x00,
                    "move-history Init ABI moved");
                ASSERT(MoveHistoryEntry_Load == ORIGIN(rom) + 0x08,
                    "move-history Load ABI moved");
                ASSERT(MoveHistoryEntry_Reset == ORIGIN(rom) + 0x10,
                    "move-history Reset ABI moved");
                ASSERT(MoveHistoryEntry_CaptureSnapshot == ORIGIN(rom) + 0x18,
                    "move-history CaptureSnapshot ABI moved");
                ASSERT(MoveHistoryEntry_Seed == ORIGIN(rom) + 0x20,
                    "move-history Seed ABI moved");
                ASSERT(MoveHistoryEntry_RecordMove == ORIGIN(rom) + 0x28,
                    "move-history RecordMove ABI moved");
                ASSERT(MoveHistoryEntry_RecordSnapshot == ORIGIN(rom) + 0x30,
                    "move-history RecordSnapshot ABI moved");
                ASSERT(MoveHistoryEntry_Query == ORIGIN(rom) + 0x38,
                    "move-history Query ABI moved");
                ASSERT(MoveHistoryEntry_CommitIfDirty == ORIGIN(rom) + 0x40,
                    "move-history CommitIfDirty ABI moved");
                ASSERT(MoveHistoryEntry_LoadAndSeedParty == ORIGIN(rom) + 0x48,
                    "move-history LoadAndSeedParty ABI moved");
                ASSERT(MoveHistoryEntry_PrepareSave == ORIGIN(rom) + 0x50,
                    "move-history PrepareSave ABI moved");
                ASSERT(MoveHistoryEntry_FinishSave == ORIGIN(rom) + 0x58,
                    "move-history FinishSave ABI moved");
                ASSERT(MoveHistoryEntry_CancelSave == ORIGIN(rom) + 0x60,
                    "move-history CancelSave ABI moved");
                ASSERT(MoveHistoryEntry_WriteSaveNow == ORIGIN(rom) + 0x68,
                    "move-history WriteSaveNow ABI moved");
                ASSERT(MoveHistoryEntry_SaveGameNormal == ORIGIN(rom) + 0x70,
                    "move-history SaveGameNormal ABI moved");
                ASSERT(MoveHistoryEntry_BuildRelearnCandidates
                        == ORIGIN(rom) + 0x78,
                    "move-relearn candidate ABI moved");
                ASSERT(MoveHistoryEntry_ReplaceMove
                        == ORIGIN(rom) + 0x80,
                    "move-history ReplaceMove ABI moved");
                ASSERT(MoveHistoryEntry_DeleteMoveSlot
                        == ORIGIN(rom) + 0x88,
                    "move-history DeleteMoveSlot ABI moved");
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
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + 0xF6C,
                    "move-history code overlaps native-shadow filter entry");
                . = ORIGIN(rom) + 0xF6C;
                KEEP(*(.overworld_wild_shadow_filter_entry))
                ASSERT(OverworldWildSpawns_FilterNativeShadowImpl
                        == ORIGIN(rom) + 0xF6C,
                    "native-shadow filter entry moved");
                . = ORIGIN(rom) + 0xF9C;
                KEEP(*(.overworld_wild_shadow_visibility_filter_entry))
                ASSERT(OverworldWildSpawns_FilterNativeShadowVisibilityImpl
                        == ORIGIN(rom) + 0xF9C,
                    "native-shadow visibility filter entry moved");
                . = ORIGIN(rom) + 0xFBC;
                KEEP(*(.overworld_wild_shadow_position_filter_entry))
                ASSERT(OverworldWildSpawns_CopyNativeShadowPositionImpl
                        == ORIGIN(rom) + 0xFBC,
                    "native-shadow position filter entry moved");
                ASSERT(. <= ORIGIN(rom) + 0x1000,
                    "native-shadow position filter exceeds resident page");
                . = ORIGIN(rom) + 0x1000;
                KEEP(*(.overworld_walk_module_entry))
                ASSERT(gOverworldWalkModuleEntry == ORIGIN(rom) + 0x1000,
                    "overworld Walk module entry moved");
                KEEP(*(.overworld_walk_profile_module_entry))
                ASSERT(gOverworldWalkProfileModuleEntry
                        == ORIGIN(rom) + 0x1040,
                    "overworld Walk profile module entry moved");
                KEEP(*(.overworld_walk_mount_module_entry))
                ASSERT(gOverworldWalkMountModuleEntry
                        == ORIGIN(rom) + 0x1058,
                    "overworld mounted Walk module entry moved");
                KEEP(*(.overworld_walk_face_module_entry))
                ASSERT(gOverworldWalkFaceModuleEntry
                        == ORIGIN(rom) + 0x1068,
                    "overworld face-player module entry moved");
                KEEP(*(.overworld_walk_wild_policy_module_entry))
                ASSERT(gOverworldWalkWildPolicyModuleEntry
                        == ORIGIN(rom) + 0x1074,
                    "overworld wild policy module entry moved");
                *(.overworld_walk_module)
                *(.overworld_walk_module_rodata)
                ASSERT(. <= ORIGIN(rom) + 0x1C00,
                    "overworld Walk module exceeds guarded resident page");
                ASSERT(__bss_end__ + 0x1000 <= ORIGIN(rom) + LENGTH(rom),
                    "move-history overlay exceeds guarded code envelope");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
