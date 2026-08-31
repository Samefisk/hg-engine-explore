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

SECTIONS {
        .text : {
                FILL (0xABCD)
                KEEP(*(.overworld_mount_precode))
                KEEP(*(.overworld_mount_hop_search))
                KEEP(*(.overworld_mount_streaming))
                ASSERT(. <= ORIGIN(rom) + 0x304,
                    "overworld mount precode exceeds expanded reserve");
                . = ORIGIN(rom) + 0x304;
                __text_start = . ;
                KEEP(*(.overworld_mount_motion))
                build/thumb_help.o(.text)
                ASSERT(. <= ORIGIN(rom) + 0xAE0,
                    "overworld mount motion exceeds audited archive gap");
                . = ORIGIN(rom) + 0xAE0;
                KEEP(*(.overworld_wild_movement_policy_entry))
                ASSERT(. <= ORIGIN(rom) + 0xAF0,
                    "overworld wild movement policy entry exceeds ABI reserve");
                . = ORIGIN(rom) + 0xB00;
                KEEP(*(.overworld_mount_entry))
                ASSERT(. <= ORIGIN(rom) + 0xB20,
                    "overworld mount entry exceeds ABI reserve");
                . = ORIGIN(rom) + 0xB20;
                KEEP(*(.overworld_mount_control))
                KEEP(*(.overworld_mount_control_tail))
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
                /* Overlay 157 is boot-resident. Keep its file size stable so
                 * the Y9/FAT metadata sealed into the ROM cannot drift when
                 * a compiler change makes the code smaller. */
                . = ORIGIN(rom) + 0x1C40;
                __text_end = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                KEEP(*(.overworld_mount_generation))
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
