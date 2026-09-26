/* Overlay 149 */
OUTPUT_ARCH(arm)
MEMORY {

        rom     : ORIGIN = 0x023CCFD8, LENGTH = 0xB028
        ewram   : ORIGIN = 0x023CCFD8, LENGTH = 0xB028
}

OverworldWalk_ClampTime = 0x023BF488 | 1;
OverworldWalk_DirectionKey = 0x023BF586 | 1;
OverworldWalk_DeltaX = 0x023BF59C | 1;
OverworldWalk_DeltaY = 0x023BF5BE | 1;
OverworldWalk_DirectionFromDelta = 0x023BF68C | 1;
OverworldWalk_DiagonalFacing = 0x023BF74E | 1;
OverworldWildSpawns_SelectMovementLocomotion = 0x023B6BB8 | 1;
OverworldWildSpawns_SelectMovementTarget = 0x023B6BCC | 1;
OverworldWildSpawns_AcknowledgeSharedMotion = 0x023BD3C4 | 1;
OverworldWildSpawns_MovementDirectionDeltaX = 0x023BF59C | 1;
OverworldWildSpawns_MovementDirectionDeltaY = 0x023BF5BE | 1;
OverworldWildOccupancy_Query = 0x023C0184 | 1;
OverworldWildSpawnGuard_Read = 0x023C025C | 1;
OverworldWildSpawnGuard_IsNearActiveSpawn = 0x023C034C | 1;
OverworldWildSpawnGuard_IsSurfBehavior = 0x023C03D0 | 1;
OverworldActor_PlayStompSound = 0x023BA118 | 1;

SECTIONS {
        .text : {

                FILL (0xABCD)

                __text_start = . ;
                . = ALIGN(4);
                KEEP(*(.overworld_wild_spawns_prefix_bss))
                ASSERT(. <= 0x28,
                    "overworld wild spawns prefix exceeds field-overlay gap");
                . = 0x28;
                KEEP(*(.overworld_wild_spawns_entry))
                __native_shadow_value_start = .;
                KEEP(*(.overworld_wild_native_shadow_value))
                ASSERT(ABSOLUTE(__native_shadow_value_start) == 0x023CD028,
                    "native-shadow value callback moved");
                . = ALIGN(4);
                *(.init)
                *(.text)
                *(.ctors)
                *(.dtors)
                *(.rodata)
                *(.rodata.*)
                *(.fini)
                . = ALIGN(4);
                ASSERT(. <= ORIGIN(rom) + 0xB000,
                    "overworld wild spawns overlay exceeds stable file slot");
                /* Keep later overlay FAT offsets stable when code shrinks. */
                . = ORIGIN(rom) + 0xB000;
                __text_end  = . ;
        } >rom = 0xff

        .bss (NOLOAD) : {
                __bss_start__ = . ;
                *(.bss)
                *(COMMON)
                . = ALIGN(4);
                __bss_end__ = . ;
                ASSERT(__text_end <= ORIGIN(rom) + 0xB000,
                    "overworld wild spawns overlay exceeds packaged FAT slot");
                ASSERT(__bss_end__ <= ORIGIN(rom) + LENGTH(rom),
                    "overworld wild spawns overlay exceeds reserved RAM");
        _end = __bss_end__ ;
        __end__ = __bss_end__ ;
        } >rom = 0xff
}
