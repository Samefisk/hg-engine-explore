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
        combat  : ORIGIN = 0x01FFF980, LENGTH = 0x200
        hit     : ORIGIN = 0x01FFF700, LENGTH = 0x100
        hopTick : ORIGIN = 0x022083B8, LENGTH = 0x48
        terrainIdle : ORIGIN = 0x01FF9770, LENGTH = 0x10
        inspect : ORIGIN = 0x01FFA4E0, LENGTH = 0xC
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
        .overworld_mount_private_terrain_idle ORIGIN(terrainIdle) : {
                KEEP(*(.overworld_mount_private_terrain_idle))
                ASSERT(ABSOLUTE(ADDR(.overworld_mount_private_terrain_idle)) == 0x01FF9770,
                    "private Mount terrain-idle leaf moved");
                ASSERT(SIZEOF(.overworld_mount_private_terrain_idle) == LENGTH(terrainIdle),
                    "private Mount terrain-idle leaf changed size");
        } >terrainIdle
        .overworld_mount_private_inspect ORIGIN(inspect) : {
                KEEP(*(.overworld_mount_private_inspect))
                ASSERT(ABSOLUTE(ADDR(.overworld_mount_private_inspect)) == 0x01FFA4E0,
                    "private Mount policy inspect moved");
                ASSERT(SIZEOF(.overworld_mount_private_inspect) == LENGTH(inspect),
                    "private Mount policy inspect changed size");
        } >inspect
        .overworld_field_mount_hop_tick ORIGIN(hopTick) : {
                KEEP(*(.overworld_field_mount_hop_tick))
                ASSERT(ABSOLUTE(ADDR(.overworld_field_mount_hop_tick)) == 0x022083B8,
                    "private Mount Hop bridge moved");
                ASSERT(ABSOLUTE(.) <= ORIGIN(hopTick) + LENGTH(hopTick),
                    "private Mount Hop bridge exceeds Field filler");
                . = LENGTH(hopTick);
                ASSERT(SIZEOF(.overworld_field_mount_hop_tick) == LENGTH(hopTick),
                    "private Mount Hop bridge changed Field filler size");
        } >hopTick
        .overworld_mount_combat_tail : {
                KEEP(*(.overworld_mount_combat_tail))
                ASSERT(ABSOLUTE(.) == 0x01FFF7EC,
                    "Mount hit body changed private Hop-ops filler");
                KEEP(*(.overworld_mount_private_hop_ops))
                ASSERT(ABSOLUTE(.) == 0x01FFF7FC,
                    "private Mount Hop ops changed size");
                ASSERT(SIZEOF(.overworld_mount_combat_tail) <= LENGTH(hit),
                    "mount hit adapter exceeds resident slot");
        } >hit
        .overworld_mount_combat : {
                KEEP(*(.overworld_mount_combat))
                /* Append the Walk preview after the fixed HP entry. */
                KEEP(*(.overworld_mount_preview))
                ASSERT(ABSOLUTE(.) <= 0x01FFFB58,
                    "Mount preview overlaps private player check");
                . = ORIGIN(combat) + 0x1D8;
                KEEP(*(.overworld_mount_private_player))
                ASSERT(ABSOLUTE(.) == 0x01FFFB80,
                    "private Mount player check changed size");
                ASSERT(SIZEOF(.overworld_mount_combat) <= LENGTH(combat),
                    "mount combat capsule exceeds resident slot");
        } >combat
        .text : {
                FILL (0xABCD)
                KEEP(*(.overworld_mount_precode))
                KEEP(*(.overworld_mount_hop_search))
                KEEP(*(.overworld_mount_streaming))
                /* Private forwarding code stays inside this overlay. Its
                 * body and the fixed public entries below do not change. */
                KEEP(*(.overworld_mount_boundary_thunk))
                /* Appended in the freed Hop-search reserve; earlier fixed
                 * private leaves keep their addresses. */
                KEEP(*(.overworld_mount_jump_landed))
                ASSERT(. <= ORIGIN(rom) + 0x314,
                    "overworld mount precode exceeds reserve");
                . = ORIGIN(rom) + 0x314;
                __text_start = . ;
                KEEP(*(.overworld_mount_motion))
                ASSERT(. <= ORIGIN(rom) + 0xAAC,
                    "overworld mount motion overlaps release grace");
                . = ORIGIN(rom) + 0xAAC;
                /* Mounted release grace, called by overlay-159 chain control. */
                KEEP(*(.overworld_mount_release_grace))
                ASSERT(ABSOLUTE(OverworldWalk_ApplyReleaseGrace) == ORIGIN(rom) + 0xAAC,
                    "mounted release grace entry moved");
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
                /* The four-byte prefix stores the last rendered player unk88
                 * value; the state and Select latch keep their fixed addresses. */
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
