/* Overlay 158 */
OUTPUT_ARCH(arm)
MEMORY {
        rom     : ORIGIN = 0x023B65A0, LENGTH = 0x4560
        ewram   : ORIGIN = 0x023B65A0, LENGTH = 0x4560
}

ACTOR_CORE_ORIGIN = 0x023B6B00;

OverworldWalk_SkidTiles = 0x023BF4D6 | 1;
OverworldActorHopPlanner_Plan = 0x023BD4F0 | 1;
OverworldActorTeleportPlanner_Plan = 0x023BD4F8 | 1;

SECTIONS {
        .overworld_condition_adapter ORIGIN(rom) : {
                FILL (0xABCD)
                KEEP(*(.text.OverworldBehaviorConditionAdapter_EvaluateActor))
                KEEP(*(.text.OverworldBehaviorConditionAdapter_BuildFrame))
                KEEP(*(.overworld_condition_adapter_zero))
                KEEP(*(.overworld_condition_adapter_constants))
                ASSERT(. <= ORIGIN(rom) + 0x560,
                    "overworld condition adapter exceeds resident prefix");
                . = ORIGIN(rom) + 0x560;
        } >rom = 0xff

        .text ORIGIN(rom) + 0x560 : {
                FILL (0xABCD)
                __text_start = . ;
                KEEP(*(.overworld_actor_system_entry))
                ASSERT(. == ORIGIN(rom) + 0x578,
                    "overworld actor facade entry ABI changed");
                KEEP(*(.overworld_actor_system_compat_entry))
                ASSERT(. == ORIGIN(rom) + 0x598,
                    "overworld actor compatibility entry ABI changed");
                KEEP(*(.overworld_actor_system_debug_layout))
                ASSERT(. == ORIGIN(rom) + 0x5D8,
                    "overworld actor debug layout ABI changed");
                KEEP(*(.overworld_actor_system_resolver_entry))
                ASSERT(. == ORIGIN(rom) + 0x5E8,
                    "overworld actor resolver service slot ABI changed");
                KEEP(*(.overworld_actor_system_motion_entry))
                ASSERT(. == ORIGIN(rom) + 0x5F8,
                    "overworld actor motion service slot ABI changed");
                KEEP(*(.overworld_actor_system_population_entry))
                ASSERT(. == ORIGIN(rom) + 0x608,
                    "overworld actor population service slot ABI changed");
                KEEP(*(.overworld_actor_system_movement_policy_entry))
                ASSERT(. == ORIGIN(rom) + 0x618,
                    "overworld actor movement policy slot ABI changed");
                KEEP(*(.overworld_actor_locomotion_policy))
                ASSERT(. <= ORIGIN(rom) + 0x62C,
                    "overworld actor locomotion selector exceeds its ABI slot");
                . = ORIGIN(rom) + 0x62C;
                KEEP(*(.overworld_actor_target_policy))
                ASSERT(. <= ORIGIN(rom) + 0x640,
                    "overworld actor target selector exceeds its ABI slot");
                . = ORIGIN(rom) + 0x640;
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
                ASSERT(. <= ORIGIN(rom) + 0x3B90,
                    "overworld actor code exceeds resident code reserve");
                . = ORIGIN(rom) + 0x3B90;
                KEEP(*(.overworld_actor_step_particle))
                KEEP(*(.overworld_actor_tail_constants))
                ASSERT(. <= ORIGIN(rom) + 0x3BD0,
                    "overworld step-particle bridge exceeds resident code reserve");
                . = ORIGIN(rom) + 0x3BD0;
                __text_end = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                ASSERT(__bss_start__ == ORIGIN(rom) + 0x3BD0,
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
