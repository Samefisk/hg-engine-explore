/* Overlay 160 */
OUTPUT_ARCH(arm)
MEMORY {
        rom   : ORIGIN = 0x01FF8620, LENGTH = 0x11E0
        ewram : ORIGIN = 0x01FF8620, LENGTH = 0x11E0
}

SECTIONS {
        .text : {
                KEEP(*(.overworld_mount_walk_ease))
                ASSERT(OverworldWalk_EaseMountedWalk == ORIGIN(rom),
                    "mounted walk easing entry moved");
                ASSERT(. <= 0x01FF8700,
                    "mounted walk easing overlaps graphics refresh");
                . = 0xE0;
                KEEP(*(.overworld_mount_graphics_refresh))
                KEEP(*(.overworld_mount_graphics_refresh_helper))
                ASSERT(. <= 0x01FF8800,
                    "mounted graphics refresh overlaps action entry");
                . = 0x1E0;
                KEEP(*(.overworld_mount_action_entry))
                *(.init)
                *(.text)
                *(.text.*)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                . = ALIGN(4);
                ASSERT(. <= 0x01FF95D0,
                    "mounted action code overlaps fixed shared helpers");
        } >rom = 0xff

        .overworld_mount_conditional_admission 0x01FF95D0 : {
                KEEP(*(.overworld_mount_conditional_admission))
        } >rom = 0xff
        ASSERT(OverworldMount_ValidateConditionalAdmission == 0x01FF95D0,
                "mounted conditional-admission helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_conditional_admission) <= 0x50,
                "mounted conditional-admission helper overlaps landing helper")

        .overworld_mount_landing_allowed 0x01FF9620 : {
                KEEP(*(.overworld_mount_landing_allowed))
        } >rom = 0xff
        ASSERT(OverworldMount_IsLandingTileAllowed == 0x01FF9620,
                "mounted landing helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_landing_allowed) <= 0x40,
                "mounted landing helper overlaps teleport classifier")

        .overworld_mount_teleport_classify 0x01FF9660 : {
                KEEP(*(.overworld_mount_teleport_classify))
        } >rom = 0xff
        ASSERT(OverworldMount_ClassifyTeleportCandidate == 0x01FF9660,
                "mounted teleport classifier ABI moved")
        ASSERT(SIZEOF(.overworld_mount_teleport_classify) <= 0x60,
                "mounted teleport classifier overlaps walk output")

        .overworld_mount_walk_policy_output 0x01FF96C0 : {
                KEEP(*(.overworld_mount_walk_policy_output))
        } >rom = 0xff
        ASSERT(OverworldMount_ApplyWalkPolicyOutput == 0x01FF96C0,
                "mounted walk-output helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_walk_policy_output) <= 0xC0,
                "mounted walk-output helper exceeds its tail reserve")

        .overworld_mount_ordinary_direction 0x01FF9780 : {
                KEEP(*(.overworld_mount_ordinary_direction))
        } >rom = 0xff
        ASSERT(OverworldMount_GetOrdinaryDirection == 0x01FF9780,
                "mounted ordinary-direction helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_ordinary_direction) <= 0x40,
                "mounted ordinary-direction helper overlaps finalize helper")

        .overworld_mount_finalize_pending 0x01FF97C0 : {
                KEEP(*(.overworld_mount_finalize_pending))
        } >rom = 0xff
        ASSERT(OverworldMount_FinalizeIsPending == 0x01FF97C0,
                "mounted finalize-pending helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_finalize_pending) <= 0x20,
                "mounted finalize-pending helper exceeds its tail reserve")

        .overworld_mount_follower_cooldown 0x01FF97D0 : {
                KEEP(*(.overworld_mount_follower_cooldown))
        } >rom = 0xff
        ASSERT(OverworldMount_ClearFollowerDecisionCooldown == 0x01FF97D0,
                "mounted follower-cooldown helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_follower_cooldown) <= 0x10,
                "mounted follower-cooldown helper overlaps player base")

        .overworld_mount_player_base 0x01FF97E0 : {
                KEEP(*(.overworld_mount_player_base))
        } >rom = 0xff
        ASSERT(OverworldMount_UpdatePlayerBaseHeight == 0x01FF97E0,
                "mounted player-base helper ABI moved")
        ASSERT(SIZEOF(.overworld_mount_player_base) <= 0x20,
                "mounted player-base helper exceeds resident action block")
        .bss (NOLOAD) : {
                *(.bss)
                *(COMMON)
                ASSERT(SIZEOF(.bss) == 0,
                    "mounted action adapter must use shared runtime state");
        } >rom = 0xff
}
