/* Overlay 158 */
OUTPUT_ARCH(arm)
MEMORY {
        /* CP4's temporary shadow bridge precedes the fixed actor ABI. */
        rom     : ORIGIN = 0x023B6500, LENGTH = 0x4600
        ewram   : ORIGIN = 0x023B6500, LENGTH = 0x4600
}

ACTOR_CORE_ORIGIN = 0x023B6B00;

OverworldWalk_SkidTiles = 0x023BF4D6 | 1;
OverworldActorHopPlanner_Plan = 0x023BD4F0 | 1;
OverworldActorTeleportPlanner_Plan = 0x023BD4F8 | 1;

SECTIONS {
        .overworld_condition_shadow ORIGIN(rom) : {
                FILL (0xABCD)
                KEEP(*(.overworld_condition_shadow_entry))
                ASSERT(gOverworldBehaviorConditionShadowEntry == ORIGIN(rom),
                    "condition shadow bridge entry moved");
                *(.text.OverworldBehaviorConditionShadow_*)
                *(.rodata.OverworldBehaviorConditionShadow_*)
                ASSERT(. <= ORIGIN(rom) + 0x600,
                    "condition shadow bridge exceeds temporary reserve");
                . = ORIGIN(rom) + 0x600;
        } >rom = 0xff

        .text ORIGIN(rom) + 0x600 : {
                FILL (0xABCD)
                __text_start = . ;
                KEEP(*(.overworld_actor_system_entry))
                ASSERT(. == ORIGIN(rom) + 0x618,
                    "overworld actor facade entry ABI changed");
                KEEP(*(.overworld_actor_system_compat_entry))
                ASSERT(. == ORIGIN(rom) + 0x638,
                    "overworld actor compatibility entry ABI changed");
                KEEP(*(.overworld_actor_system_debug_layout))
                ASSERT(. == ORIGIN(rom) + 0x678,
                    "overworld actor debug layout ABI changed");
                KEEP(*(.overworld_actor_system_resolver_entry))
                ASSERT(. == ORIGIN(rom) + 0x688,
                    "overworld actor resolver service slot ABI changed");
                KEEP(*(.overworld_actor_system_motion_entry))
                ASSERT(. == ORIGIN(rom) + 0x698,
                    "overworld actor motion service slot ABI changed");
                KEEP(*(.overworld_actor_system_population_entry))
                ASSERT(. == ORIGIN(rom) + 0x6A8,
                    "overworld actor population service slot ABI changed");
                KEEP(*(.overworld_actor_system_movement_policy_entry))
                ASSERT(. == ORIGIN(rom) + 0x6B8,
                    "overworld actor movement policy slot ABI changed");
                KEEP(*(.overworld_actor_lane_policy))
                ASSERT(. == ORIGIN(rom) + 0x6E0,
                    "overworld actor lane selector ABI changed");
                KEEP(*(.overworld_actor_population_adapter))
                KEEP(*(.overworld_actor_mount_policy))
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.text.*)
                *(.ctors)
                *(.dtors)
                *(.data)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                *(COMMON)
                ASSERT(. <= ORIGIN(rom) + 0x3C30,
                    "overworld actor code exceeds resident code reserve");
                . = ORIGIN(rom) + 0x3C30;
                KEEP(*(.overworld_actor_step_particle))
                ASSERT(. <= ORIGIN(rom) + 0x3C70,
                    "overworld step-particle bridge exceeds resident code reserve");
                . = ORIGIN(rom) + 0x3C70;
                __text_end = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                ASSERT(__bss_start__ == ORIGIN(rom) + 0x3C70,
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
