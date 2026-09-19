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
                FILL(0xABCD)
                KEEP(*(.overworld_walk_decelerate_time))
                ASSERT(OverworldWalk_DecelerateTime == ORIGIN(rom) + 0x1000,
                    "Walk DecelerateTime helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x105C,
                    "Walk DecelerateTime helper exceeds its slot");
                . = ORIGIN(rom) + 0x105C;
                KEEP(*(.overworld_walk_propose_step))
                ASSERT(OverworldWalk_ProposeStep == ORIGIN(rom) + 0x105C,
                    "Walk ProposeStep helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1088,
                    "Walk ProposeStep helper exceeds its slot");
                . = ORIGIN(rom) + 0x1088;
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom = 0xff

        .walk_helpers ORIGIN(rom) + 0x1088 : SUBALIGN(2) {
                FILL(0xABCD)
                KEEP(*(.overworld_walk_clamp_time))
                ASSERT(OverworldWalk_ClampTime == ORIGIN(rom) + 0x1088,
                    "Walk ClampTime helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x109E,
                    "Walk ClampTime helper exceeds its slot");
                . = ORIGIN(rom) + 0x109E;
                KEEP(*(.overworld_walk_accelerate_time))
                ASSERT(OverworldWalk_AccelerateTime == ORIGIN(rom) + 0x109E,
                    "Walk AccelerateTime helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x10D6,
                    "Walk AccelerateTime helper exceeds its slot");
                . = ORIGIN(rom) + 0x10D6;
                KEEP(*(.overworld_walk_skid_tiles))
                ASSERT(OverworldWalk_SkidTiles == ORIGIN(rom) + 0x10D6,
                    "Walk SkidTiles helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x10F0,
                    "Walk SkidTiles helper exceeds its slot");
                . = ORIGIN(rom) + 0x10F0;
                KEEP(*(.overworld_walk_skid_time))
                ASSERT(OverworldWalk_SkidTime == ORIGIN(rom) + 0x10F0,
                    "Walk SkidTime helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1104,
                    "Walk SkidTime helper exceeds its slot");
                . = ORIGIN(rom) + 0x1104;
                KEEP(*(.overworld_walk_stomp_applies))
                ASSERT(OverworldWalk_StompApplies == ORIGIN(rom) + 0x1104,
                    "Walk StompApplies helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1134,
                    "Walk StompApplies helper exceeds its slot");
                . = ORIGIN(rom) + 0x1134;
                KEEP(*(.overworld_walk_direction_from_keys))
                ASSERT(OverworldWalk_DirectionFromKeys
                        == ORIGIN(rom) + 0x1134,
                    "Walk DirectionFromKeys helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1186,
                    "Walk DirectionFromKeys helper exceeds its slot");
                . = ORIGIN(rom) + 0x1186;
                KEEP(*(.overworld_walk_direction_key))
                . = ALIGN(4);
                KEEP(*(.overworld_walk_direction_key_body))
                ASSERT(OverworldWalk_DirectionKey == ORIGIN(rom) + 0x1186,
                    "Walk DirectionKey helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x119C,
                    "Walk DirectionKey helper exceeds its slot");
                . = ORIGIN(rom) + 0x119C;
                KEEP(*(.overworld_walk_delta_x))
                /* GNU ld exposes these exact-fit Thumb symbols as a
                 * section-relative value while evaluating ASSERT. Placement
                 * is fixed by the location counter above; require the Thumb
                 * entry itself to remain defined. */
                ASSERT(DEFINED(OverworldWalk_DeltaX)
                        && (OverworldWalk_DeltaX & 1) == 1,
                    "Walk DeltaX helper is missing or is not Thumb");
                ASSERT(. <= ORIGIN(rom) + 0x11BE,
                    "Walk DeltaX helper exceeds its slot");
                . = ORIGIN(rom) + 0x11BE;
                KEEP(*(.overworld_walk_delta_y))
                ASSERT(DEFINED(OverworldWalk_DeltaY)
                        && (OverworldWalk_DeltaY & 1) == 1,
                    "Walk DeltaY helper is missing or is not Thumb");
                ASSERT(. <= ORIGIN(rom) + 0x11E2,
                    "Walk DeltaY helper exceeds its slot");
                . = ORIGIN(rom) + 0x11E2;
                KEEP(*(.overworld_walk_is_forty_five_degree_turn))
                ASSERT(OverworldWalk_IsFortyFiveDegreeTurn
                        == ORIGIN(rom) + 0x11E2,
                    "Walk IsFortyFiveDegreeTurn helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x128C,
                    "Walk IsFortyFiveDegreeTurn helper exceeds its slot");
                . = ORIGIN(rom) + 0x128C;
                KEEP(*(.overworld_walk_direction_from_delta))
                ASSERT(OverworldWalk_DirectionFromDelta
                        == ORIGIN(rom) + 0x128C,
                    "Walk DirectionFromDelta helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x12CE,
                    "Walk DirectionFromDelta helper exceeds its slot");
                . = ORIGIN(rom) + 0x12CE;
                KEEP(*(.overworld_walk_strict_diagonal_allowed))
                . = ALIGN(4);
                KEEP(*(.overworld_walk_strict_diagonal_allowed_body))
                ASSERT(OverworldWalk_StrictDiagonalAllowed
                        == ORIGIN(rom) + 0x12CE,
                    "Walk StrictDiagonalAllowed helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x134E,
                    "Walk StrictDiagonalAllowed helper exceeds its slot");
                . = ORIGIN(rom) + 0x134E;
                KEEP(*(.overworld_walk_diagonal_facing))
                ASSERT(OverworldWalk_DiagonalFacing
                        == ORIGIN(rom) + 0x134E,
                    "Walk DiagonalFacing helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1380,
                    "Walk DiagonalFacing helper exceeds its slot");
                . = ORIGIN(rom) + 0x1380;
                KEEP(*(.overworld_walk_resolve_mounted_diagonal))
                ASSERT(OverworldWalk_ResolveMountedDiagonal
                        == ORIGIN(rom) + 0x1380,
                    "Walk ResolveMountedDiagonal helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1440,
                    "Walk ResolveMountedDiagonal helper exceeds its slot");
                . = ORIGIN(rom) + 0x1440;
                KEEP(*(.overworld_walk_start_mounted_flat))
                ASSERT(OverworldWalk_StartMountedFlat
                        == ORIGIN(rom) + 0x1440,
                    "Walk StartMountedFlat helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x15A0,
                    "Walk StartMountedFlat helper exceeds its slot");
                . = ORIGIN(rom) + 0x15A0;
                KEEP(*(.overworld_walk_filter_mounted_input))
                ASSERT(OverworldWalk_FilterMountedInput
                        == ORIGIN(rom) + 0x15A0,
                    "Walk FilterMountedInput helper moved");
                ASSERT(. <= ORIGIN(rom) + 0x1760,
                    "Walk FilterMountedInput helper exceeds its slot");
                . = ORIGIN(rom) + 0x1760;
                *(.overworld_walk_module)
                *(.overworld_walk_module_rodata)
                ASSERT(. <= ORIGIN(rom) + 0x1860,
                    "overworld Walk module overlaps Field terrain code host");
                . = ORIGIN(rom) + 0x1860;
                KEEP(*(.overworld_field_terrain_stream_entry))
                ASSERT(OverworldFieldTerrainStream_Apply
                        == ORIGIN(rom) + 0x1860,
                    "Field terrain private entry moved");
                KEEP(*(.overworld_field_terrain_stream_code))
                ASSERT(. <= ORIGIN(rom) + 0x1A50,
                    "Field terrain code overlaps Walk rejection code host");
                . = ORIGIN(rom) + 0x1A50;
                KEEP(*(.overworld_walk_candidate_rejection))
                ASSERT(. <= ORIGIN(rom) + 0x1B14,
                    "Walk rejection code overlaps mount abort helper");
                . = ORIGIN(rom) + 0x1B14;
                KEEP(*(.overworld_walk_stop_skid_plan))
                ASSERT(OverworldWalk_MarkPlannedStopSkid
                        == ORIGIN(rom) + 0x1B14,
                    "Walk stop-skid planner moved");
                KEEP(*(.overworld_walk_decelerate_time_body))
                ASSERT(. <= ORIGIN(rom) + 0x1BEA,
                    "Walk stop-skid planner overlaps mount abort helper");
                . = ORIGIN(rom) + 0x1BEA;
                ASSERT(__bss_end__ + 0x1000 <= ORIGIN(rom) + LENGTH(rom),
                    "move-history overlay exceeds guarded code envelope");
        } >rom = 0xff

        .mount_abort ORIGIN(rom) + 0x1BEA : {
                KEEP(*(.overworld_walk_mount_abort))
                ASSERT(OverworldWalkMount_RebaseMotionTargetImpl
                        == ORIGIN(rom) + 0x1BEA,
                    "mounted motion abort helper moved");
                ASSERT(. == ORIGIN(rom) + 0x1BF6,
                    "mounted motion abort helper changed packaged size");
        } >rom = 0xff

        /* Explicit Wild presentation code host. Existing history, Walk,
         * Field and mount entries above retain their fixed addresses. */
        .spawn_identity 0x023C0000 : {
                KEEP(*(.overworld_spawn_identity))
                ASSERT(ABSOLUTE(OverworldWildSpawnIdentity_PrepareSlot) == 0x023C0000,
                    "Wild spawn identity entry moved");
                /* ld strips the Thumb bit in script expressions. The S2
                 * guard checks ELF FUNC/odd st_value and the caller import. */
                ASSERT(DEFINED(OverworldWildSpawnIdentity_PrepareSlot)
                        && (ABSOLUTE(OverworldWildSpawnIdentity_PrepareSlot) & 1) == 0,
                    "Wild spawn identity code address is not aligned");
                . = ALIGN(4);
                ASSERT(. <= 0x023C0184,
                    "Wild spawn identity overlaps occupancy host");
                . = ORIGIN(rom) + 0x1D84;
                KEEP(*(.overworld_wild_occupancy))
                ASSERT(ABSOLUTE(OverworldWildOccupancy_Query) == 0x023C0184,
                    "Wild occupancy entry moved");
                ASSERT(. <= 0x023C025C,
                    "Wild occupancy overlaps spawn guard host");
                . = ORIGIN(rom) + 0x1E5C;
                KEEP(*(.overworld_spawn_guard_read))
                ASSERT(ABSOLUTE(OverworldWildSpawnGuard_Read) == 0x023C025C,
                    "Wild spawn guard read entry moved");
                ASSERT(. <= 0x023C034C,
                    "Wild spawn guard read exceeds its slot");
                . = ORIGIN(rom) + 0x1F4C;
                KEEP(*(.overworld_spawn_guard_near))
                ASSERT(ABSOLUTE(OverworldWildSpawnGuard_IsNearActiveSpawn) == 0x023C034C,
                    "Wild spawn proximity entry moved");
                ASSERT(. <= 0x023C03D0,
                    "Wild spawn proximity exceeds its slot");
                . = ORIGIN(rom) + 0x1FD0;
                KEEP(*(.overworld_spawn_guard_surf))
                ASSERT(ABSOLUTE(OverworldWildSpawnGuard_IsSurfBehavior) == 0x023C03D0,
                    "Wild surf predicate moved");
                ASSERT(. <= ORIGIN(rom) + LENGTH(rom),
                    "Wild spawn identity exceeds explicit resident tail");
        } >rom = 0xff

}
