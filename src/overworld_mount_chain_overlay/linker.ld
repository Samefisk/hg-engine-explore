/* Overlay 159 */
OUTPUT_ARCH(arm)
MEMORY {
        rom   : ORIGIN = 0x01FF9800, LENGTH = 0xD80
        ewram : ORIGIN = 0x01FF9800, LENGTH = 0xD80
}

OverworldMount_ProcessPlayerControl = 0x023BC330 | 1;
OverworldMount_TryStartCustomMotion = 0x023BB218 | 1;
OverworldMount_GetInputDirection = 0x023BB67C | 1;
OverworldActorPolicy_MountCommand = 0x023BA0E0 | 1;
OverworldWildOccupancy_Query = 0x023C0184 | 1;

SECTIONS {
        .text : {
                KEEP(*(.overworld_mount_chain_entry))
                ASSERT(OverworldMount_ChainControl == ORIGIN(rom),
                    "mounted chain entry moved");
                *(.text)
                *(.rodata)
                . = ALIGN(4);
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
                ASSERT(. <= 0x01FFA100,
                    "mounted gait code overlaps presentation");
        } >rom = 0xff

        .overworld_mount_presentation 0x01FFA100 : {
                KEEP(*(.overworld_mount_presentation_entry))
                ASSERT((ABSOLUTE(OverworldFieldService_SyncMountedPresentation) & ~1)
                        == 0x01FFA100, "mounted presentation entry moved");
                KEEP(*(.overworld_walk_displayed_time_code))
                . = ALIGN(4);
                ASSERT(. <= 0x01FFA500,
                    "mounted presentation overlaps gait state");
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
