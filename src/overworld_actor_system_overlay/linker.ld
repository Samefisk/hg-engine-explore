/* Overlay 158 */
OUTPUT_ARCH(arm)
MEMORY {
        /* Boot-resident actor facade immediately below overlay 157. */
        rom     : ORIGIN = 0x023B6B00, LENGTH = 0x4000
        ewram   : ORIGIN = 0x023B6B00, LENGTH = 0x4000
}

SECTIONS {
        .text : {
                FILL (0xABCD)
                __text_start = . ;
                KEEP(*(.overworld_actor_system_entry))
                ASSERT(. == ORIGIN(rom) + 0x18,
                    "overworld actor facade entry ABI changed");
                KEEP(*(.overworld_actor_system_compat_entry))
                ASSERT(. == ORIGIN(rom) + 0x38,
                    "overworld actor compatibility entry ABI changed");
                KEEP(*(.overworld_actor_system_debug_layout))
                ASSERT(. == ORIGIN(rom) + 0x78,
                    "overworld actor debug layout ABI changed");
                KEEP(*(.overworld_actor_system_resolver_entry))
                ASSERT(. == ORIGIN(rom) + 0x88,
                    "overworld actor resolver service slot ABI changed");
                KEEP(*(.overworld_actor_system_motion_entry))
                ASSERT(. == ORIGIN(rom) + 0x98,
                    "overworld actor motion service slot ABI changed");
                KEEP(*(.overworld_actor_system_population_entry))
                ASSERT(. == ORIGIN(rom) + 0xA8,
                    "overworld actor population service slot ABI changed");
                KEEP(*(.overworld_actor_system_movement_policy_entry))
                ASSERT(. == ORIGIN(rom) + 0xB8,
                    "overworld actor movement policy slot ABI changed");
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
                ASSERT(. <= ORIGIN(rom) + 0x3000,
                    "overworld actor code exceeds resident code reserve");
                /*
                 * Portable modules and later implementations link before this
                 * boundary. Only the last 0x1000 is the fixed state reserve.
                 */
                . = ORIGIN(rom) + 0x3000;
                __text_end = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                ASSERT(__bss_start__ == ORIGIN(rom) + 0x3000,
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
