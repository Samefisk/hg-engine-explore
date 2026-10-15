/* Overlay 149 */
OUTPUT_ARCH(arm)
MEMORY {

        slamJump : ORIGIN = 0x023B8800, LENGTH = 0x650
        pickupCancel : ORIGIN = 0x023B9048, LENGTH = 0x1D8
        rom     : ORIGIN = 0x023CCFD8, LENGTH = 0xB028
        ewram   : ORIGIN = 0x023CCFD8, LENGTH = 0xB028
        combat  : ORIGIN = 0x01FFF580, LENGTH = 0x180
        carrier : ORIGIN = 0x01FFF800, LENGTH = 0x180
        hit     : ORIGIN = 0x01FFFB80, LENGTH = 0x3A0
        field   : ORIGIN = 0x02208400, LENGTH = 0x100
        policy  : ORIGIN = 0x022085D0, LENGTH = 0x30
        cargo   : ORIGIN = 0x023CCDC8, LENGTH = 0xD0
        throwY  : ORIGIN = 0x023C7D34, LENGTH = 0xC4
        teleY   : ORIGIN = 0x01FFEF54, LENGTH = 0xAC
        notice  : ORIGIN = 0x023C2C1C, LENGTH = 0x164
        route   : ORIGIN = 0x022081E0, LENGTH = 0x20
        hopSupport : ORIGIN = 0x0220833C, LENGTH = 0x24
        cleanupTask : ORIGIN = 0x01FFC124, LENGTH = 0x3C
        cleanupHop : ORIGIN = 0x01FFEEFC, LENGTH = 0x58
        cleanupProgress : ORIGIN = 0x01FFF318, LENGTH = 0x28
        cleanupSpawn : ORIGIN = 0x01FFF3D4, LENGTH = 0x2C
        cleanupPresentation : ORIGIN = 0x01FFF432, LENGTH = 0x4E
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
        .overworld_actor_slam_jump ORIGIN(slamJump) : {
                KEEP(*(.overworld_actor_slam_jump))
                ASSERT(ABSOLUTE(ADDR(.overworld_actor_slam_jump)) == 0x023B8800,
                    "private shared Slam jump moved");
                ASSERT(SIZEOF(.overworld_actor_slam_jump) == LENGTH(slamJump),
                    "private shared Slam jump overlaps Field Rest tint policy");
        } >slamJump

        /* Wild owns this unchanged handoff leaf. The wrapper copies the fully
         * linked bytes into the boot-resident Actor image after Field Rest. */
        .overworld_actor_pickup_cancel ORIGIN(pickupCancel) : {
                KEEP(*(.overworld_actor_pickup_cancel))
                ASSERT(ABSOLUTE(ADDR(.overworld_actor_pickup_cancel)) == 0x023B9048,
                    "private pickup cancel moved");
                ASSERT(SIZEOF(.overworld_actor_pickup_cancel) == 0xC8,
                    "private pickup cancel body extent changed");
                ASSERT(SIZEOF(.overworld_actor_pickup_cancel) <= LENGTH(pickupCancel),
                    "private pickup cancel overlaps anchored Motion");
        } >pickupCancel

        .overworld_field_wild_hop_support ORIGIN(hopSupport) : {
                KEEP(*(.overworld_field_wild_hop_ops))
                ASSERT(ABSOLUTE(.) == 0x0220834C,
                    "private Hop presentation ops changed size");
                KEEP(*(.overworld_field_wild_hop_look))
                ASSERT(SIZEOF(.overworld_field_wild_hop_support) == LENGTH(hopSupport),
                    "private Hop support exceeds Field equality filler");
        } >hopSupport
        /* Fully linked unchanged leaves use existing boot-HP filler. The
         * wrapper copies these bytes after Wild links; no reciprocal link. */
        .overworld_wild_cleanup_task ORIGIN(cleanupTask) : {
                KEEP(*(.overworld_wild_cleanup_task))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_cleanup_task)) == 0x01FFC124,
                    "private movement-list cleanup moved");
                ASSERT(SIZEOF(.overworld_wild_cleanup_task) <= LENGTH(cleanupTask),
                    "private movement-list cleanup exceeds HP filler");
        } >cleanupTask
        .overworld_wild_cleanup_hop_request ORIGIN(cleanupHop) : {
                KEEP(*(.overworld_wild_cleanup_hop_request))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_cleanup_hop_request)) == 0x01FFEEFC,
                    "private Hop request moved");
                ASSERT(SIZEOF(.overworld_wild_cleanup_hop_request) <= LENGTH(cleanupHop),
                    "private Hop request exceeds HP filler");
        } >cleanupHop
        .overworld_wild_cleanup_progress ORIGIN(cleanupProgress) : {
                KEEP(*(.overworld_wild_cleanup_progress))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_cleanup_progress)) == 0x01FFF318,
                    "private progress cleanup moved");
                ASSERT(SIZEOF(.overworld_wild_cleanup_progress) <= LENGTH(cleanupProgress),
                    "private progress cleanup exceeds HP filler");
        } >cleanupProgress
        .overworld_wild_cleanup_spawn ORIGIN(cleanupSpawn) : {
                KEEP(*(.overworld_wild_cleanup_spawn))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_cleanup_spawn)) == 0x01FFF3D4,
                    "private spawn cleanup moved");
                ASSERT(SIZEOF(.overworld_wild_cleanup_spawn) <= LENGTH(cleanupSpawn),
                    "private spawn cleanup exceeds HP filler");
        } >cleanupSpawn
        .overworld_wild_cleanup_presentation ORIGIN(cleanupPresentation) : {
                KEEP(*(.overworld_wild_cleanup_presentation))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_cleanup_presentation)) == 0x01FFF432,
                    "private presentation cleanup moved");
                ASSERT(SIZEOF(.overworld_wild_cleanup_presentation) <= LENGTH(cleanupPresentation),
                    "private presentation cleanup exceeds HP filler");
        } >cleanupPresentation
        .overworld_wild_notice_callers : {
                KEEP(*(.overworld_wild_notice_callers))
                KEEP(*(.overworld_wild_notice_callers.tail))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_notice_callers)) == 0x023C2C1C,
                    "private notice callers moved");
                ASSERT(SIZEOF(.overworld_wild_notice_callers) <= LENGTH(notice),
                    "private notice callers exceed Selector152 filler");
        } >notice

        .overworld_wild_throw_height : {
                KEEP(*(.overworld_wild_throw_height))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_throw_height)) == 0x023C7D34,
                    "private Throw height getter moved");
                ASSERT(SIZEOF(.overworld_wild_throw_height) <= LENGTH(throwY),
                    "private Throw height getter exceeds Helper151 filler");
        } >throwY
        .overworld_wild_teleport_read : {
                KEEP(*(.overworld_wild_teleport_read))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_teleport_read)) == 0x01FFEF54,
                    "private Teleport read callback moved");
                ASSERT(SIZEOF(.overworld_wild_teleport_read) <= LENGTH(teleY),
                    "private Teleport read callback exceeds HP filler");
        } >teleY
        .overworld_field_wild_cargo_observation : {
                KEEP(*(.overworld_field_wild_cargo_observation))
                ASSERT(ABSOLUTE(.) <= 0x023CCE88,
                    "private Wild Cargo observer exceeds its fixed body home");
                . = 0xC0;
                ASSERT(ABSOLUTE(.) == 0x023CCE88,
                    "private Wild bubble helper home moved");
                KEEP(*(.overworld_field_wild_cargo_observation.tail))
                ASSERT(ABSOLUTE(.) == 0x023CCE98,
                    "private Wild bubble helper extent differs");
                ASSERT(SIZEOF(.overworld_field_wild_cargo_observation) <= LENGTH(cargo),
                    "private Wild Cargo observation exceeds Field131 reserve");
        } >cargo
        .overworld_field_wild_route_base_y : {
                KEEP(*(.overworld_field_wild_route_base_y))
                ASSERT(ABSOLUTE(ADDR(.overworld_field_wild_route_base_y)) == 0x022081E0,
                    "private Wild route height wrapper moved");
                ASSERT(SIZEOF(.overworld_field_wild_route_base_y) <= LENGTH(route),
                    "private Wild route height wrapper exceeds Field reserve");
        } >route
        .overworld_field_wild_policy_init : {
                KEEP(*(.overworld_field_wild_policy_init))
                KEEP(*(.overworld_field_wild_policy_init.tail))
                ASSERT(ABSOLUTE(ADDR(.overworld_field_wild_policy_init)) == 0x022085D0,
                    "private Wild policy initializer moved");
                ASSERT(SIZEOF(.overworld_field_wild_policy_init) <= LENGTH(policy),
                    "private Wild policy initializer exceeds Field reserve");
        } >policy
        .overworld_field_wild_walk_output : {
                KEEP(*(.overworld_field_wild_walk_output))
                KEEP(*(.overworld_field_wild_walk_output.tail))
                ASSERT(SIZEOF(.overworld_field_wild_walk_output) <= LENGTH(field),
                    "wild walk output exceeds stock Field capsule");
        } >field
        .overworld_wild_carrier_hit : {
                KEEP(*(.overworld_wild_carrier_hit))
                KEEP(*(.overworld_wild_carrier_hit.tail))
                KEEP(*(.overworld_wild_carrier_hit.reserve))
                ASSERT(ABSOLUTE(ADDR(.overworld_wild_carrier_hit)) == 0x01FFF800,
                    "private carrier hit leaf moved");
                ASSERT(SIZEOF(.overworld_wild_carrier_hit) <= LENGTH(carrier),
                    "private carrier hit leaf exceeds empty combat capsule");
        } >carrier
        .overworld_wild_combat_tail : {
                KEEP(*(.overworld_wild_combat_tail))
                ASSERT(SIZEOF(.overworld_wild_combat_tail) <= LENGTH(hit),
                    "wild hit adapter exceeds resident slot");
        } >hit
        .overworld_wild_combat : {
                KEEP(*(.overworld_wild_combat))
                ASSERT(SIZEOF(.overworld_wild_combat) <= LENGTH(combat),
                    "wild combat capsule exceeds resident slot");
        } >combat
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
