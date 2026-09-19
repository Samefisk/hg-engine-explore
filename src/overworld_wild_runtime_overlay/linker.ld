/* Overlay 156 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023BC800, LENGTH = 0xC00
        ewram   : ORIGIN = 0x023BC800, LENGTH = 0xC00
}

/* Overlay 158 owns this resident ABI address. Import it explicitly because
 * custom overlay symbols are not part of the vanilla rom_gen.ld export set. */
OverworldRoleController_Reduce = 0x023BE240 | 1;
OverworldWalk_DecelerateTime = 0x023BF400 | 1;
OverworldWalk_ProposeStep = 0x023BF45C | 1;
OverworldWalk_ClampTime = 0x023BF488 | 1;
OverworldWalk_AccelerateTime = 0x023BF49E | 1;
OverworldWalk_SkidTiles = 0x023BF4D6 | 1;
OverworldWalk_SkidTime = 0x023BF4F0 | 1;
OverworldWalk_StompApplies = 0x023BF504 | 1;
OverworldWalk_IsFortyFiveDegreeTurn = 0x023BF5E2 | 1;
OverworldWildRuntime_PlayStepDirtParticle = 0x023BA130 | 1;

SECTIONS {
        /* This resident overlay has no compiler-helper relocations. Keep the
         * generic overlay dependency from consuming its fixed reservation. */
        /DISCARD/ : { *thumb_help.o(.text) }

        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_runtime_entry))
                ASSERT(. == ORIGIN(rom) + 0x34,
                    "overworld wild runtime entry ABI changed");
                KEEP(*(.overworld_actor_walk_policy_owner))
                ASSERT(. == ORIGIN(rom) + 0x40,
                    "actor Walk policy owner entry ABI changed");
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.data)
                *(.rodata)
                *(.fini)
                *(COMMON)
                ASSERT(. <= ORIGIN(rom) + 0xB50,
                    "overworld wild runtime core exceeds stable reserve");
                . = ORIGIN(rom) + 0xB50;
                KEEP(*(.overworld_wild_runtime_acknowledge))
                KEEP(*(.overworld_wild_runtime_landing_particle))
                ASSERT(. <= ORIGIN(rom) + 0xBC4,
                    "explicit Actor Motion boundary exceeds receipt reserve");
                . = ORIGIN(rom) + 0xBC4;
                KEEP(*(.overworld_wild_motion_receipt))
                ASSERT(. <= ORIGIN(rom) + 0xBEC,
                    "Wild receipt adapter exceeds stable reserve");
                . = ORIGIN(rom) + 0xBEC;
                KEEP(*(.overworld_wild_runtime_mount_facing))
                KEEP(*(.overworld_wild_runtime_tail_data))
                ASSERT(. <= ORIGIN(rom) + 0xC00,
                    "mounted facing wrapper exceeds resident reserve");
                . = ORIGIN(rom) + 0xC00;
                __text_end  = . ;

                __bss_start__ = . ;
                *(.bss)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld wild runtime overlay exceeds resident reservation");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
