/* Overlay 157 */
OUTPUT_ARCH(arm)
MEMORY {
        /*
         * Boot-resident mount control occupies a dedicated block immediately
         * below resident overworld runtime overlay 156. Heap 3 reserves this
         * complete range; never borrow incidental padding from another overlay.
         */
        rom     : ORIGIN = 0x023BAB00, LENGTH = 0x1D00
        ewram   : ORIGIN = 0x023BAB00, LENGTH = 0x1D00
}

OverworldWalk_DeltaX = 0x023BF59C | 1;
OverworldWalk_DeltaY = 0x023BF5BE | 1;
OverworldWalk_DirectionFromDelta = 0x023BF68C | 1;
OverworldWalk_DirectionFromKeys = 0x023BF534 | 1;
OverworldWalk_StrictDiagonalAllowed = 0x023BF6CE | 1;
OverworldWalk_DiagonalFacing = 0x023BF74E | 1;
OverworldWalk_ResolveMountedDiagonal = 0x023BF780 | 1;
OverworldWalk_StartMountedFlat = 0x023BF840 | 1;
OverworldWalk_FilterMountedInput = 0x023BF9A0 | 1;
OverworldWildSpawns_ResolveWalkPause = 0x023DFFCC | 1;
OverworldMount_UpdatePlayerBaseHeight = 0x01FF97E0 | 1;
OverworldMount_ClearFollowerDecisionCooldown = 0x01FF97D0 | 1;
OverworldMount_GetOrdinaryDirection = 0x01FF9780 | 1;
OverworldMount_FinalizeIsPending = 0x01FF97C0 | 1;
OverworldMount_IsLandingTileAllowed = 0x01FF9620 | 1;
OverworldMount_ClassifyTeleportCandidate = 0x01FF9660 | 1;
OverworldMount_ApplyWalkPolicyOutput = 0x01FF96C0 | 1;
OverworldActor_PlayStompSound = 0x023BA118 | 1;
OverworldActorPolicy_MountCommand = 0x023BA0E0 | 1;
OverworldMount_ChainControl = 0x01FF9800 | 1;
OverworldMount_ResetMomentum = 0x01FF9AB0 | 1;
OverworldMount_BufferedDirection = 0x01FF9AD4 | 1;

SECTIONS {
        .text : {
                FILL (0xABCD)
                KEEP(*(.overworld_mount_precode))
                KEEP(*(.overworld_mount_hop_search))
                KEEP(*(.overworld_mount_streaming))
                /* Private forwarding code stays inside this overlay. Its
                 * body and the fixed public entries below do not change. */
                KEEP(*(.overworld_mount_boundary_thunk))
                ASSERT(. <= ORIGIN(rom) + 0x314,
                    "overworld mount precode exceeds reserve");
                . = ORIGIN(rom) + 0x314;
                __text_start = . ;
                KEEP(*(.overworld_mount_motion))
                ASSERT(. <= ORIGIN(rom) + 0xB00,
                    "overworld mount motion overlaps fixed entry");
                . = ORIGIN(rom) + 0xB00;
                KEEP(*(.overworld_mount_entry))
                ASSERT(. <= ORIGIN(rom) + 0xB20,
                    "overworld mount entry exceeds ABI reserve");
                . = ORIGIN(rom) + 0xB20;
                KEEP(*(.overworld_mount_control))
                KEEP(*(.overworld_mount_control_tail_crash))
                KEEP(*(.overworld_mount_control_tail))
                KEEP(*(.overworld_mount_control_gap))
                ASSERT(. <= ORIGIN(rom) + 0xBA0,
                    "overworld mount player-control wrapper exceeded reserve");
                . = ORIGIN(rom) + 0xBA0;
                KEEP(*(.overworld_mount_step))
                KEEP(*(.overworld_mount_step_extra))
                ASSERT(. <= ORIGIN(rom) + 0xBE0,
                    "overworld mount player-step wrapper exceeded reserve");
                . = ORIGIN(rom) + 0xBE0;
                KEEP(*(.overworld_mount_field_input))
                KEEP(*(.overworld_mount_field_input_extra))
                ASSERT(. <= ORIGIN(rom) + 0xC40,
                    "overworld mount field-input wrapper exceeded reserve");
                . = ORIGIN(rom) + 0xC40;
                KEEP(*(.overworld_mount_crash))
                KEEP(*(.overworld_mount_crash_extra))
                ASSERT(. <= ORIGIN(rom) + 0xC78,
                    "overworld mount crash-sound wrapper exceeded reserve");
                . = ORIGIN(rom) + 0xC78;
                KEEP(*(.overworld_mount_toggle_latch))
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0x1C40,
                    "overworld mount code exceeds stable packaged size");
                __mount_used_end = .;
                /* Overlay 157 is boot-resident. Keep its file size stable so
                 * the Y9/FAT metadata sealed into the ROM cannot drift when
                 * a compiler change makes the code smaller. */
                . = ORIGIN(rom) + 0x1C40;
                __text_end = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                /* Retain the historic four-byte prefix so the runtime state
                 * and its resident Select latch keep their fixed addresses. */
                . = . + 4;
                __mount_state_start = ABSOLUTE(.);
                KEEP(*(.overworld_mount_state))
                *(.bss)
                *(COMMON)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__mount_state_start + 0x96 == 0x023BC7DA,
                    "resident mount toggle latch address drifted");
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld mount overlay exceeds reserved RAM");
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom = 0xff
}
