/* Overlay 161 */
OUTPUT_ARCH(arm)

/* Stock ARM9 graphics services. Addresses are from the matching vanilla
 * HeartGold source and ARM9 binary. Thumb entries carry the low bit. */
sub_02021AC8 = 0x02021AC9;
sub_02021B5C = 0x02021B5D;
ObjPlttTransfer_CreateTaskAndDoTransferFromTemplate_ExtPlttBanned = 0x020226A5;
ObjPlttTransfer_FreeTaskByID = 0x02022745;
ObjPlttTransfer_GetPlttProxyByID = 0x020227AD;
ObjPlttTransfer_GetPaletteVramOffset = 0x02022809;
NNS_G2dEntryOamManagerOamWithAffineIdx = 0x020B7B10;
GX_LoadOBJ = 0x020CFE74;
GX_LoadOBJPltt = 0x020CFD18;
DC_FlushRange = 0x020D2894;
MEMORY {
        /* Boot-resident ITCM directly after the mounted gait capsule. */
        rom   : ORIGIN = 0x01FFA580, LENGTH = 0x5A80
        ewram : ORIGIN = 0x01FFA580, LENGTH = 0x5A80
        field : ORIGIN = 0x02208500, LENGTH = 0xD0
}

SECTIONS {
        .overworld_field_walk_input_tuning : {
                KEEP(*(.overworld_field_walk_input_tuning))
                ASSERT(ABSOLUTE(ADDR(.overworld_field_walk_input_tuning)) == 0x02208500,
                    "private Walk tuning entry moved");
                ASSERT(SIZEOF(.overworld_field_walk_input_tuning) <= LENGTH(field),
                    "private Walk tuning exceeds parent Field reserve");
        } >field
        .text : {
                __text_start = .;
                KEEP(*(.player_health_api))
                ASSERT(gPlayerHealthOverlayEntry == ORIGIN(rom),
                    "player health entry table moved");
                ASSERT(. == ORIGIN(rom) + 0x34,
                    "player health entry table size changed");
                *(.init)
                *(.text)
                *(.text.*)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                *(.data)
                *(.data.*)
                KEEP(*(.player_health_state))
                . = ALIGN(4);
                KEEP(*(.overworld_combat_prepare))
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0x1780,
                    "player health code overlaps condition clear slot");
                . = ORIGIN(rom) + 0x1780;
                KEEP(*(.actor_condition_clear))
                ASSERT(OverworldBehaviorConditionAdapter_ClearResolution
                        == ORIGIN(rom) + 0x1780,
                    "condition clear Thumb entry moved");
                KEEP(*(.player_health_tail))
                . = ALIGN(4);
                ASSERT(ABSOLUTE(.) <= 0x01FFC124,
                    "player health tail overlaps private movement-list cleanup");
                . = ORIGIN(rom) + 0x1BA4;
                KEEP(*(.overworld_wild_cleanup_task))
                ASSERT(ABSOLUTE(.) == 0x01FFC160,
                    "private movement-list cleanup reservation differs");
                ASSERT(. <= ORIGIN(rom) + 0x1BE0,
                    "player health code overlaps blocked-step entries");
                . = ORIGIN(rom) + 0x1BE0;
                KEEP(*(.player_health_stock_collision_entry))
                ASSERT(PlayerHealthContact_StockCollisionEntry
                        == ORIGIN(rom) + 0x1BE0,
                    "stock collision entry moved");
                ASSERT(. <= ORIGIN(rom) + 0x1BE8,
                    "stock collision entry exceeds slot");
                . = ORIGIN(rom) + 0x1BE8;
                KEEP(*(.player_health_blocked_step_entry))
                ASSERT(PlayerHealthContact_BlockedStepEntry
                        == ORIGIN(rom) + 0x1BE8,
                    "blocked-step entry moved");
                ASSERT(. <= ORIGIN(rom) + 0x1C00,
                    "blocked-step entry exceeds its fixed slot");
                . = ORIGIN(rom) + 0x1BF0;
                KEEP(*(.player_health_knockback_entry))
                ASSERT(PlayerHealthField_OverrideControlEntryImpl
                        == ORIGIN(rom) + 0x1BF0,
                    "knockback control entry moved");
                ASSERT(. <= ORIGIN(rom) + 0x1C00,
                    "knockback control entry exceeds its fixed slot");
                . = ORIGIN(rom) + 0x1C00;
                KEEP(*(.player_health_throw_api))
                ASSERT(gPlayerHealthThrowServiceEntry
                        == ORIGIN(rom) + 0x1C00,
                    "Throw observation entry moved");
                ASSERT(. == ORIGIN(rom) + 0x1C20,
                    "Throw observation entry size changed");
                KEEP(*(.player_health_throw_text))
                KEEP(*(.player_health_palette_copy))
                KEEP(*(.player_health_extended_state))
                KEEP(*(.player_health_extended_text))
                ASSERT(ABSOLUTE(.) <= 0x01FFD250,
                    "player health overlaps private appearance release gap");
                /* The Field release leaf ends at D2CC. These private owners
                 * reuse only the following measured resident filler. */
                . = ORIGIN(rom) + 0x2D4C;
                KEEP(*(.overworld_behavior_packed_options))
                ASSERT(ABSOLUTE(OverworldBehaviorPackedOptions_Apply) == 0x01FFD2CC,
                    "private packed profile helper moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFD336,
                    "private packed profile helper exceeds filler");
                . = ORIGIN(rom) + 0x2DB6;
                KEEP(*(.overworld_walk_profile_skid))
                ASSERT(ABSOLUTE(OverworldWalk_ProfileSkidTiles) == 0x01FFD336,
                    "private profile skid picker moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFD380,
                    "private skid picker overlaps HitCrash");
                . = ORIGIN(rom) + 0x2E00;
                KEEP(*(.overworld_actor_hit_crash))
                ASSERT(ABSOLUTE(OverworldActorHitCrash_Apply) == 0x01FFD380,
                    "hit Crash owner entry moved");
                ASSERT(. <= 0x01FFD510,
                    "hit Crash owner overlaps Field empty-axis check");
                . = ORIGIN(rom) + 0x2F90;
                KEEP(*(.overworld_field_empty_axis))
                ASSERT(ABSOLUTE(OverworldFieldTerrainStream_RetireEmptyAxis)
                        == 0x01FFD510,
                    "Field empty-axis check entry moved");
                ASSERT(. <= 0x01FFD580,
                    "Field empty-axis check overlaps combat service");
                . = ORIGIN(rom) + 0x3000;
                KEEP(*(.overworld_combat_api))
                ASSERT(ABSOLUTE(gOverworldCombatEntry) == 0x01FFD580,
                    "combat entry table moved");
                KEEP(*(.overworld_combat_text))
                KEEP(*(.overworld_combat_state))
                ASSERT(. <= ORIGIN(rom) + 0x5000,
                    "combat service overlaps actor capsules");
                /* Shared Walk policy uses the measured free code gap before
                 * the fixed combat capsules. Its state stays Actor-owned. */
                ASSERT(ABSOLUTE(.) <= 0x01FFEEFC,
                    "combat service overlaps private Hop request filler");
                . = ORIGIN(rom) + 0x497C;
                KEEP(*(.overworld_wild_cleanup_hop_request))
                ASSERT(ABSOLUTE(.) == 0x01FFEF54,
                    "private Hop request reservation differs");
                . = ORIGIN(rom) + 0x49D4;
                KEEP(*(.overworld_wild_teleport_read))
                ASSERT(ABSOLUTE(.) == 0x01FFF000,
                    "private Teleport read wrapper changed its172-byte reserve");
                ASSERT(ABSOLUTE(.) <= 0x01FFF000,
                    "combat service overlaps shared Walk policy code host");
                . = ORIGIN(rom) + 0x4A80;
                KEEP(*(.overworld_walk_policy_reset))
                ASSERT(ABSOLUTE(OverworldActorWalkPolicy_ResetState) == 0x01FFF000,
                    "shared Walk reset entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF028,
                    "shared Walk reset overlaps private variance helper");
                . = ORIGIN(rom) + 0x4AA8;
                KEEP(*(.overworld_walk_policy_variance))
                ASSERT(ABSOLUTE(OverworldActorWalkPolicy_SampleVariance) == 0x01FFF028,
                    "private Walk variance helper moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF040,
                    "private Walk variance helper overlaps input policy entry");
                . = ORIGIN(rom) + 0x4AC0;
                KEEP(*(.overworld_walk_input_policy))
                ASSERT(ABSOLUTE(OverworldActorWalkPolicy_ReduceInput) == 0x01FFF040,
                    "shared Walk input policy entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF380,
                    "shared Walk input policy overlaps actor replies");
                ASSERT(ABSOLUTE(.) <= 0x01FFF318,
                    "shared Walk input policy overlaps private progress cleanup");
                . = ORIGIN(rom) + 0x4D98;
                KEEP(*(.overworld_wild_cleanup_progress))
                ASSERT(ABSOLUTE(.) == 0x01FFF340,
                    "private progress cleanup reservation differs");
                . = ORIGIN(rom) + 0x4DC0;
                KEEP(*(.overworld_walk_policy_crash))
                ASSERT(ABSOLUTE(OverworldActorWalkPolicy_Crash) == 0x01FFF340,
                    "shared Walk Crash outcome entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF35C,
                    "shared Walk Crash outcome overlaps private chain chance");
                . = ORIGIN(rom) + 0x4DDC;
                KEEP(*(.overworld_walk_policy_chain_chance))
                ASSERT(ABSOLUTE(OverworldActorWalkPolicy_SampleChainChance) == 0x01FFF35C,
                    "private chain chance helper moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF380,
                    "private chain chance helper overlaps actor replies");
                . = ORIGIN(rom) + 0x4E00;
                KEEP(*(.overworld_actor_acknowledgements))
                ASSERT(ABSOLUTE(gOverworldActorAcknowledgements) == 0x01FFF380,
                    "actor acknowledgement capsule moved");
                ASSERT(ABSOLUTE(.) == 0x01FFF3B0,
                    "actor acknowledgement capsule size changed");
                KEEP(*(.overworld_wild_quiet_bubble))
                ASSERT(ABSOLUTE(OverworldWildBubble_ShowQuiet) == 0x01FFF3B0,
                    "private quiet bubble entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF3D4,
                    "private quiet bubble overlaps spawn cleanup");
                . = ORIGIN(rom) + 0x4E54;
                KEEP(*(.overworld_wild_cleanup_spawn))
                ASSERT(ABSOLUTE(.) == 0x01FFF400,
                    "private spawn cleanup reservation differs");
                . = ORIGIN(rom) + 0x4E80;
                KEEP(*(.overworld_walk_mount_save_proposal))
                ASSERT(ABSOLUTE(Walk_MountSaveProposal) == 0x01FFF400,
                    "mounted Walk save entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF432,
                    "mounted Walk save overlaps private presentation cleanup");
                . = ORIGIN(rom) + 0x4EB2;
                KEEP(*(.overworld_wild_cleanup_presentation))
                ASSERT(ABSOLUTE(.) == 0x01FFF480,
                    "private presentation cleanup reservation differs");
                . = ORIGIN(rom) + 0x4F00;
                KEEP(*(.overworld_walk_proposal_save_reserved))
                ASSERT(ABSOLUTE(OverworldMountWalkProposal_SaveReserved) == 0x01FFF480,
                    "mounted Walk reserved-byte save entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF4A0,
                    "mounted Walk reserved-byte save exceeds slot");
                . = ORIGIN(rom) + 0x4F20;
                KEEP(*(.overworld_walk_proposal_restore_reserved))
                ASSERT(ABSOLUTE(OverworldMountWalkProposal_RestoreReserved) == 0x01FFF4A0,
                    "mounted Walk reserved-byte restore entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF4C0,
                    "mounted Walk reserved-byte restore exceeds slot");
                . = ORIGIN(rom) + 0x4F40;
                KEEP(*(.overworld_walk_mount_finish))
                ASSERT(ABSOLUTE(OverworldMountWalkProposal_Finish) == 0x01FFF4C0,
                    "mounted Walk finish entry moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF550,
                    "mounted Walk finish overlaps private Hop effect choice");
                . = ORIGIN(rom) + 0x4FD0;
                KEEP(*(.overworld_hop_effect_choice))
                ASSERT(ABSOLUTE(OverworldActorWalkPolicy_SampleHopEffects) == 0x01FFF550,
                    "private Hop effect choice moved");
                ASSERT(ABSOLUTE(.) <= 0x01FFF57C,
                    "private Hop effect choice overlaps proposal capsule");
                . = ORIGIN(rom) + 0x4FFC;
                KEEP(*(.overworld_mount_walk_proposal_reserved))
                ASSERT(ABSOLUTE(gOverworldMountWalkProposalReserved) == 0x01FFF57C,
                    "mounted Walk proposal capsule moved");
                ASSERT(ABSOLUTE(.) == ORIGIN(rom) + 0x5000,
                    "mounted Walk proposal capsule size changed");
                . = ORIGIN(rom) + 0x5000;
                KEEP(*(.overworld_combat_capsules))
                ASSERT(ABSOLUTE(.) == 0x01FFFB80,
                    "existing combat capsule size changed");
                KEEP(*(.overworld_wild_combat_tail))
                ASSERT(ABSOLUTE(.) == 0x01FFFF20,
                    "wild hit adapter capsule size changed");
                KEEP(*(.player_health_tail_end))
                . = ALIGN(4);
                ASSERT(ABSOLUTE(.) <= 0x01FFFF80,
                    "health tail exceeds resident reservation");
                /* The stock ITCM arena is empty; syntheticoverlay.s moves its
                 * low bound to the ITCM end so this tail hosts the Walk
                 * policy transition reset. */
                . = ORIGIN(rom) + 0x5A00;
                KEEP(*(.overworld_walk_policy_transition_reset))
                ASSERT(ABSOLUTE(.) <= 0x02000000,
                    "Walk policy transition reset exceeds the ITCM end");
                . = ORIGIN(rom) + 0x5A80;
                __text_end = .;
                ASSERT(. <= ORIGIN(rom) + LENGTH(rom),
                    "player health exceeds its resident ITCM reservation");
        } >rom = 0xff

        .bss (NOLOAD) : {
                *(.bss)
                *(.bss.*)
                *(COMMON)
                ASSERT(SIZEOF(.bss) == 0,
                    "player health state must have a loaded reset capsule");
        } >rom = 0xff
}
