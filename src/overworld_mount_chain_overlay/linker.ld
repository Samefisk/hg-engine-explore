/* Overlay 159 */
OUTPUT_ARCH(arm)
MEMORY {
        rom   : ORIGIN = 0x01FF9800, LENGTH = 0xD80
        ewram : ORIGIN = 0x01FF9800, LENGTH = 0xD80
}

OverworldMount_ProcessPlayerControl = 0x023BC2AC | 1;
OverworldMount_TryStartCustomMotion = 0x023BB20C | 1;
OverworldMount_GetInputDirection = 0x023BB67C | 1;
OverworldActorPolicy_MountCommand = 0x023BA0E0 | 1;
OverworldWildOccupancy_Query = 0x023C0184 | 1;
OverworldMount_CanCrossFront = 0x023B8630 | 1;

SECTIONS {
        /DISCARD/ : { *(.overworld_mount_private_terrain_idle) }
        .text : {
                KEEP(*(.overworld_mount_chain_entry))
                ASSERT(OverworldMount_ChainControl == ORIGIN(rom),
                    "mounted chain entry moved");
                *(.text)
                *(.rodata)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0x230, "chain core overlaps skid dust filter");
                . = ORIGIN(rom) + 0x230;
                /* Wild runtime skid/landing dust entry; fixed for its stub. */
                KEEP(*(.overworld_skid_dust))
                ASSERT(ABSOLUTE(OverworldSkidDust_Play) == ORIGIN(rom) + 0x230,
                    "skid dust filter entry moved");
                ASSERT(. <= 0x01FF9A48, "chain core overlaps private result init");
                . = ORIGIN(rom) + 0x248;
                KEEP(*(.overworld_condition_publication_init))
                ASSERT((ABSOLUTE(OverworldConditionPublication_InitResult) & ~1) == 0x01FF9A48, "private result init moved");
                ASSERT(. <= ORIGIN(rom) + 0x270,
                    "mounted chain logic overlaps surface query");
                . = ORIGIN(rom) + 0x270;
                KEEP(*(.overworld_mount_surface_id))
                ASSERT(OverworldMount_GetSurfaceId == ORIGIN(rom) + 0x270,
                    "mounted surface-query ABI moved");
                ASSERT(. <= ORIGIN(rom) + 0x2B0,
                    "mounted surface query overlaps reset entry");
                . = ORIGIN(rom) + 0x2B0;
                KEEP(*(.overworld_mount_reset_momentum))
                ASSERT(. <= ORIGIN(rom) + 0x2D4,
                    "mounted reset overlaps buffered direction entry");
                . = ORIGIN(rom) + 0x2D4;
                KEEP(*(.overworld_mount_buffer_direction))
                ASSERT(. <= ORIGIN(rom) + 0x300,
                    "mounted buffered direction exceeds stable entry page");
                . = ORIGIN(rom) + 0x300;
                KEEP(*(.overworld_mount_forward_hop))
                ASSERT(. <= ORIGIN(rom) + 0x48C,
                    "mounted forward Hop overlaps shared Walk pacing");
                . = ORIGIN(rom) + 0x48C;
                KEEP(*(.overworld_walk_displayed_time))
                ASSERT(OverworldWalk_SelectDisplayedTime == ORIGIN(rom) + 0x48C,
                    "shared Walk pacing entry moved");
                ASSERT(. <= 0x01FF9C94, "Walk pacing overlaps private result fold");
                . = ORIGIN(rom) + 0x494;
                KEEP(*(.overworld_condition_publication_fold))
                ASSERT((ABSOLUTE(OverworldConditionPublication_FoldResult) & ~1) == 0x01FF9C94, "private result fold moved");
                ASSERT(. <= 0x01FF9CDC, "result fold overlaps fixed import whitelist");
                . = ORIGIN(rom) + 0x4DC;
                KEEP(*(.overworld_condition_publication_imports))
                ASSERT(ABSOLUTE(gOverworldConditionPublicationImports) == 0x01FF9CDC, "private import whitelist moved");
                ASSERT(. <= ORIGIN(rom) + 0x500,
                    "shared Walk pacing exceeds resident chain block");
        } >rom = 0xff

        /* Append the mounted presentation model without moving chain or
         * Walk entries. Boot reserves this whole range from the ITCM arena. */
        .overworld_mount_gait 0x01FF9D00 : {
                KEEP(*(.overworld_mount_gait_entry))
                ASSERT((ABSOLUTE(OverworldMountGait_Apply) & ~1) == 0x01FF9D00,
                    "mounted gait entry moved");
                KEEP(*(.overworld_mount_gait_code))
                . = ALIGN(4);
                ASSERT(. <= 0x01FFA000,
                    "mounted gait code overlaps diagonal resolver");
                . = 0x300;
                KEEP(*(.overworld_mount_diagonal_resolver))
                ASSERT((ABSOLUTE(OverworldMount_ResolveMountedDiagonalBody) & ~1)
                        == 0x01FFA000,
                    "mounted diagonal resolver body moved");
                ASSERT(. <= 0x01FFA0F0,
                    "mounted diagonal resolver overlaps strict check");
                . = 0x3F0;
                KEEP(*(.overworld_mount_strict_diagonal_allowed_body))
                ASSERT((ABSOLUTE(OverworldMount_StrictDiagonalAllowedBody) & ~1)
                        == 0x01FFA0F0,
                    "mounted strict diagonal body moved");
                ASSERT(. <= 0x01FFA100,
                    "mounted gait code overlaps presentation");
        } >rom = 0xff

        .overworld_mount_presentation 0x01FFA100 : {
                KEEP(*(.overworld_mount_presentation_entry))
                ASSERT((ABSOLUTE(OverworldFieldService_SyncMountedPresentation) & ~1)
                        == 0x01FFA100, "mounted presentation entry moved");
                KEEP(*(.overworld_walk_displayed_time_code))
                . = ALIGN(4);
                ASSERT(. <= 0x01FFA39C, "presentation overlaps private blob validation");
                . = 0x29C;
                KEEP(*(.overworld_condition_publication_blob))
                ASSERT((ABSOLUTE(OverworldConditionPublication_BlobValid) & ~1) == 0x01FFA39C, "private blob validation moved");
                ASSERT(. <= 0x01FFA400,
                    "mounted presentation overlaps player contact entry");
                . = 0x300;
                KEEP(*(.overworld_mount_player_contact))
                ASSERT((ABSOLUTE(OverworldMount_ReportBlockedPlayerStep) & ~1)
                        == 0x01FFA400,
                    "mounted player contact entry moved");
                ASSERT(. <= 0x01FFA4E0,
                    "mounted presentation overlaps gait state");
                . = 0x3E0;
                KEEP(*(.overworld_mount_private_inspect))
                ASSERT(ABSOLUTE(.) == 0x01FFA4EC,
                    "private policy inspect changed its Chain filler");
                KEEP(*(.overworld_motion_slam_unit_height))
                ASSERT((ABSOLUTE(OverworldSlam_UnitHeightNative) & ~1)
                    == 0x01FFA4EC, "private Slam unit height moved");
                ASSERT(ABSOLUTE(.) == 0x01FFA500,
                    "private Slam unit height must fill exactly20 existing bytes");
        } >rom = 0xff

        /* Explicit loaded data: overlay 159 retains zero SDK BSS bytes.
         * The gait owner resets this capsule at mount lifecycle boundaries. */
        .overworld_mount_gait_state 0x01FFA500 : {
                __mount_gait_state_start = ABSOLUTE(.);
                KEEP(*(.overworld_mount_gait_state))
                . = ALIGN(4);
                __mount_gait_state_end = ABSOLUTE(.);
                ASSERT(. <= 0x01FFA580,
                    "mounted gait state exceeds its 128-byte reserve");
        } >rom = 0x00

        .bss (NOLOAD) : {
                *(.bss)
                *(.bss.*)
                *(COMMON)
                ASSERT(SIZEOF(.bss) == 0,
                    "mounted chain state must use its explicit loaded capsule");
        } >rom = 0xff
}
