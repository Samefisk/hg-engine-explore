/* Overlay 158 */
OUTPUT_ARCH(arm)
MEMORY {
        rom     : ORIGIN = 0x023B65C0, LENGTH = 0x4540
        ewram   : ORIGIN = 0x023B65C0, LENGTH = 0x4540
        emote_initialize : ORIGIN = 0x02203B28, LENGTH = 0x178
        emote_release : ORIGIN = 0x02203A60, LENGTH = 0x54
        emote_destroy : ORIGIN = 0x02203A20, LENGTH = 0x18
}

/* Public entries and state stay anchored while the private prefix shrinks. */
ACTOR_CORE_ORIGIN = 0x023B6B00;
ASSERT(ACTOR_CORE_ORIGIN - ORIGIN(rom) == 0x540,
    "overworld condition prefix size changed");

OverworldWalk_SkidTiles = 0x023BF4D6 | 1;
OverworldActorHopPlanner_Plan = 0x023BD4F0 | 1;
OverworldActorTeleportPlanner_Plan = 0x023BD4F8 | 1;
/* Private condition helper shares resident ITCM; it does not own HP state. */
OverworldBehaviorConditionAdapter_ClearResolution = 0x01FFBD00 | 1;

SECTIONS {
        /* All compiler helpers have explicit checked resident Thumb imports.
         * Do not link duplicate helper definitions into this fixed overlay. */
        /DISCARD/ : { *thumb_help.o(.text) }

        .overworld_condition_adapter ORIGIN(rom) : {
                FILL (0xABCD)
                KEEP(*(.text.OverworldBehaviorConditionAdapter_EvaluateActor))
                ASSERT(. <= ORIGIN(rom) + 0x370,
                    "condition evaluation overlaps fixed frame reader");
                . = ORIGIN(rom) + 0x370;
                KEEP(*(.text.OverworldBehaviorConditionAdapter_BuildFrame))
                ASSERT(ABSOLUTE(OverworldBehaviorConditionAdapter_BuildFrame) == 0x023B6930,
                    "private condition frame reader moved");
                KEEP(*(.overworld_condition_adapter_zero))
                KEEP(*(.overworld_condition_adapter_constants))
                ASSERT(. <= ORIGIN(rom) + 0x540,
                    "overworld condition adapter exceeds resident prefix");
                . = ORIGIN(rom) + 0x540;
        } >rom = 0xff

        .text ORIGIN(rom) + 0x540 : {
                FILL (0xABCD)
                __text_start = . ;
                KEEP(*(.overworld_actor_system_entry))
                ASSERT(. == ORIGIN(rom) + 0x558,
                    "overworld actor facade entry ABI changed");
                KEEP(*(.overworld_actor_system_compat_entry))
                ASSERT(. == ORIGIN(rom) + 0x578,
                    "overworld actor compatibility entry ABI changed");
                KEEP(*(.overworld_actor_system_debug_layout))
                ASSERT(. == ORIGIN(rom) + 0x5B8,
                    "overworld actor debug layout ABI changed");
                KEEP(*(.overworld_actor_system_resolver_entry))
                ASSERT(. == ORIGIN(rom) + 0x5C8,
                    "overworld actor resolver service slot ABI changed");
                KEEP(*(.overworld_actor_system_motion_entry))
                ASSERT(. == ORIGIN(rom) + 0x5D8,
                    "overworld actor motion service slot ABI changed");
                KEEP(*(.overworld_actor_system_population_entry))
                ASSERT(. == ORIGIN(rom) + 0x5E8,
                    "overworld actor population service slot ABI changed");
                KEEP(*(.overworld_actor_system_movement_policy_entry))
                ASSERT(. == ORIGIN(rom) + 0x5F8,
                    "overworld actor movement policy slot ABI changed");
                KEEP(*(.overworld_actor_locomotion_policy))
                ASSERT(. <= ORIGIN(rom) + 0x60C,
                    "overworld actor locomotion selector exceeds its ABI slot");
                . = ORIGIN(rom) + 0x60C;
                KEEP(*(.overworld_actor_target_policy))
                KEEP(*(.overworld_actor_target_constants))
                ASSERT(. <= ORIGIN(rom) + 0x620,
                    "overworld actor target selector exceeds its ABI slot");
                . = ORIGIN(rom) + 0x620;
                KEEP(*(.overworld_actor_population_adapter))
                KEEP(*(.overworld_actor_mount_policy))
                . = ALIGN(4);
                *(.init)
                *overworld_actor_system_overlay.o(.text)
                *overworld_behavior_condition_adapter.o(.text)
                *overworld_behavior_resolver.o(.text)
                ASSERT(ABSOLUTE(.) <= 0x023B8540,"existing Actor core overlaps emote collect");
                . = ORIGIN(rom) + 0x1F80;
                KEEP(*(.overworld_emote_collect))
                KEEP(*(.overworld_emote_select))
                KEEP(*(.overworld_emote_descriptor))
                KEEP(*(.overworld_emote_continuation))
                ASSERT(ABSOLUTE(.) <= 0x023B8600,
                    "actor facade overlaps private Slam rise height");
                . = ORIGIN(rom) + 0x2040;
                KEEP(*(.overworld_motion_slam_rise_height))
                ASSERT(ABSOLUTE(OverworldMotion_SlamRiseUnitHeightNative) == 0x023B8600,
                    "private Slam rise height moved");
                ASSERT(ABSOLUTE(.) <= 0x023B8628,
                    "private Slam rise height exceeds its reserve");
                . = ORIGIN(rom) + 0x2070;
                KEEP(*(.overworld_mount_front_admission))
                ASSERT(ABSOLUTE(OverworldMount_CanCrossFront) == 0x023B8630,
                    "private mounted front admission moved");
                ASSERT(ABSOLUTE(OverworldMountJump_HopInPlace) == 0x023B86DA,
                    "mounted Jump Hop in place moved");
                ASSERT(ABSOLUTE(.) <= 0x023B8800,
                    "mounted front admission overlaps private Wild Hop acceptance");
                ASSERT(ABSOLUTE(.) <= 0x023B8728,"existing mounted front overlaps emote owner");
                . = ORIGIN(rom) + 0x2168;
                KEEP(*(.overworld_emote_createowner))
                KEEP(*(.overworld_emote_destroyowner))
                KEEP(*(.overworld_emote_retire))
                ASSERT(ABSOLUTE(.) <= 0x023B8800,"emote owner exceeds measured gap");
                . = ORIGIN(rom) + 0x2240;
                KEEP(*(.overworld_actor_slam_jump))
                ASSERT(ABSOLUTE(OverworldActorPrivateSlamJump) == 0x023B8800,
                    "private Wild Hop acceptance moved");
                ASSERT(ABSOLUTE(.) == 0x023B8E50,
                    "private Wild Hop acceptance overlaps Field Rest tint policy");
                KEEP(*(.overworld_appearance_rest_policy))
                ASSERT(ABSOLUTE(OverworldActorPrivateRestTint) == 0x023B8E50,
                    "private Field Rest tint copy moved");
                ASSERT(ABSOLUTE(.) == 0x023B9048,
                    "private Field Rest tint copy extent changed");
                KEEP(*(.overworld_actor_pickup_cancel))
                ASSERT(ABSOLUTE(OverworldActorPrivatePickupCancel) == 0x023B9048,
                    "private Wild pickup cancel copy moved");
                ASSERT(ABSOLUTE(.) == 0x023B9110,
                    "private Wild pickup cancel copy extent changed");
                KEEP(*(.overworld_emote_admit))
                ASSERT(ABSOLUTE(.) <= 0x023B9220,"emote Admit exceeds measured gap");
                /* Player HP has checked imports into the shared Motion model.
                 * Keep its entire compiled text at its original stable base. */
                ASSERT(ABSOLUTE(.) <= 0x023B9220,
                    "actor facade overlaps anchored Motion model");
                . = ORIGIN(rom) + 0x2C60;
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_PathLengthForTiles))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Lerp))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_SymmetricArc))
                KEEP(*overworld_motion_model.o(.text.OverworldActorHopGeometry_Init))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Sample))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_GetPathAdvanceTile))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_SelectPlan))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Reset))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Read))
                ASSERT(ABSOLUTE(.) <= 0x023B97EC, "private Motion front overlaps Begin");
                . = 0x2CEC;
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Begin))
                ASSERT(ABSOLUTE(.) <= 0x023B9880, "Motion Begin overlaps private Hop dispatch");
                . = 0x2D80;
                KEEP(*(.overworld_actor_hop_dispatch))
                ASSERT(ABSOLUTE(.) <= 0x023B98A4, "Hop dispatch overlaps fixed Motion Suspend");
                . = 0x2DA4;
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Suspend))
                ASSERT(ABSOLUTE(.) <= 0x023B98C2, "private Motion admission overlaps commit");
                . = 0x2DC2;
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_AcknowledgeCommit))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Tick))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Resume))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_RebindField))
                KEEP(*overworld_motion_model.o(.text.OverworldMotion_Cancel))
                *(.text)
                *(.text.*)
                *(.ctors)
                *(.dtors)
                *(.data)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                *(COMMON)
                ASSERT(. <= ORIGIN(rom) + 0x3AFC,
                    "overworld actor code overlaps one-frame Walk helper");
                ASSERT(ABSOLUTE(.) <= 0x023BA01C,"existing Actor back overlaps emote preparation");
                . = ORIGIN(rom) + 0x3A5C;
                KEEP(*(.overworld_emote_prepare))
                KEEP(*(.overworld_emote_update))
                ASSERT(ABSOLUTE(.) <= 0x023BA0BC,"emote preparation exceeds measured gap");
                . = ORIGIN(rom) + 0x3AFC;
                KEEP(*(.overworld_mount_one_frame_walk))
                ASSERT(OverworldMount_FinishOneFrameWalk
                        == ORIGIN(rom) + 0x3AFC,
                    "mounted one-frame Walk helper ABI moved");
                ASSERT(. <= ORIGIN(rom) + 0x3B20,
                    "overworld actor code overlaps mount profile command");
                . = ORIGIN(rom) + 0x3B20;
                KEEP(*(.overworld_actor_mount_profile_command))
                ASSERT(. <= ORIGIN(rom) + 0x3B58,
                    "overworld mount profile command exceeds reserve");
                . = ORIGIN(rom) + 0x3B58;
                KEEP(*(.overworld_actor_stomp_sound))
                ASSERT(. <= ORIGIN(rom) + 0x3B78,
                    "overworld actor code exceeds resident code reserve");
                . = ORIGIN(rom) + 0x3B78;
                KEEP(*(.overworld_actor_step_particle))
                KEEP(*(.overworld_actor_tail_constants))
                ASSERT(. <= ORIGIN(rom) + 0x3BB0,
                    "overworld step-particle bridge exceeds resident code reserve");
                . = ORIGIN(rom) + 0x3BB0;
                __text_end = . ;
        } >rom = 0xff

        .overworld_emote_initialize ORIGIN(emote_initialize) : {
                KEEP(*(.overworld_emote_initialize))
                KEEP(*(.overworld_emote_loadmember))
                ASSERT(. <= ORIGIN(emote_initialize)+LENGTH(emote_initialize),"emote initialize exceeds dead stock span");
        } >emote_initialize
        .overworld_emote_release ORIGIN(emote_release) : {
                KEEP(*(.overworld_emote_release))
                ASSERT(. <= ORIGIN(emote_release)+LENGTH(emote_release),"emote release exceeds dead stock span");
        } >emote_release
        .overworld_emote_destroy ORIGIN(emote_destroy) : {
                KEEP(*(.overworld_emote_destroy))
                ASSERT(. <= ORIGIN(emote_destroy)+LENGTH(emote_destroy),"emote destructor exceeds dead stock tail");
        } >emote_destroy
        .bss (NOLOAD) : {
                __bss_start__ = . ;
                ASSERT(__bss_start__ == ORIGIN(rom) + 0x3BB0,
                    "overworld actor state base moved");
                KEEP(*(.overworld_actor_system_state))
                *(.bss)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld actor facade state exceeds resident block");
                _end = __bss_end__ ;
                __end__ = __bss_end__ ;
        } >rom = 0xff
}
/* Check absolute addresses after section placement. Inside .text, ld treats
 * these relocatable symbols as section-relative in the assertion. */
ASSERT(OverworldMotion_Begin == 0x023B97EC,
    "player HP Actor Motion Begin import moved");
ASSERT(OverworldMotion_Tick == 0x023B990A,
    "player HP Actor Motion Tick import moved");
ASSERT(OverworldMotion_AcknowledgeCommit == 0x023B98C2,
    "player HP Actor Motion commit import moved");
ASSERT(OverworldMotion_Cancel == 0x023B9A2E,
    "player HP Actor Motion cancel import moved");

ASSERT(OverworldMotion_Suspend == 0x023B98A4, "player HP Actor Motion Suspend import moved");
