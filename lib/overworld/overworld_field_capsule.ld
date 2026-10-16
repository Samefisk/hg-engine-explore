/* Retired stock overlay 1 graphics table. Both stock readers are repointed
 * to gOWTagToFileNum. The live graphics callback list begins at 0x022089CC. */
OUTPUT_ARCH(arm)
MEMORY {
    rom : ORIGIN = 0x022074A8, LENGTH = 0x1524
    release : ORIGIN = 0x01FFD250, LENGTH = 0x7C
    rest_policy : ORIGIN = 0x023B8E50, LENGTH = 0x3D0
}
SECTIONS {
    /* Same pure Field policy; copied once into existing boot Actor filler. */
    .overworld_appearance_rest_policy ORIGIN(rest_policy) : {
        KEEP(*(.overworld_appearance_rest_policy))
        ASSERT(ABSOLUTE(OverworldAppearancePolicy_ShouldRestTint) == 0x023B8E50,
            "private Field Rest tint policy moved");
        ASSERT(SIZEOF(.overworld_appearance_rest_policy) == 0x1F4,
            "private Field Rest tint policy extent changed");
        ASSERT(ABSOLUTE(.) <= ORIGIN(rest_policy) + LENGTH(rest_policy),
            "private Field Rest tint policy overlaps anchored Motion");
    } > rest_policy

    /* Same Field owner; bytes are copied into the existing HP padding. */
    .overworld_appearance_release ORIGIN(release) : {
        ASSERT(ABSOLUTE(.) == 0x01FFD250,
            "private appearance release entry moved");
        KEEP(*(.overworld_appearance_release))
        ASSERT(SIZEOF(.overworld_appearance_release) <= LENGTH(release),
            "private appearance release exceeds existing HP gap");
    } > release

    .text : {
        KEEP(*(.overworld_actor_appearance_entry))
        ASSERT(ABSOLUTE(gOverworldActorAppearanceEntry) == 0x022074A8,
            "field appearance entry moved");
        ASSERT(ABSOLUTE(.) == 0x022074C4,
            "field appearance entry size changed");
        *(.text*)
        *(.rodata*)
        *(.data*)
        . = ALIGN(4);
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        __appearance_end = ABSOLUTE(.);
        ASSERT(ABSOLUTE(.) <= 0x022081E0,
            "field appearance overlaps Wild route support");
        . = ABSOLUTE(0x022081E0);
        KEEP(*(.overworld_field_wild_route_base_y))
        ASSERT(ABSOLUTE(.) == 0x02208200,
            "private Wild route support reserve changed");
        . = ABSOLUTE(0x02208200);
        KEEP(*(.overworld_condition_subject))
        ASSERT(ABSOLUTE(OverworldConditionSubject_Populate) == 0x02208200,
            "condition subject entry moved");
        ASSERT(ABSOLUTE(.) <= 0x022082C0,
            "condition subject exceeds its reserve");
        . = ABSOLUTE(0x022082C0);
        KEEP(*(.overworld_condition_subject_clear))
        ASSERT(ABSOLUTE(OverworldConditionSubject_ClearActor) == 0x022082C0,
            "condition clear entry moved");
        ASSERT(ABSOLUTE(.) <= 0x02208320,
            "condition clear exceeds its reserve");
        . = ABSOLUTE(0x02208320);
        KEEP(*(.overworld_condition_subject_equal))
        ASSERT(ABSOLUTE(OverworldConditionSubject_HandleEquals) == 0x02208320,
            "condition equality entry moved");
        ASSERT(ABSOLUTE(.) <= 0x0220833A,
            "condition equality exceeds its reserve");
        . = ABSOLUTE(0x0220833C);
        KEEP(*(.overworld_field_wild_hop_support))
        ASSERT(ABSOLUTE(.) == 0x02208360,
            "private Hop support changed its Field filler");
        . = ABSOLUTE(0x02208360);
        KEEP(*(.overworld_field_spawn_orphans))
        ASSERT(ABSOLUTE(.) == 0x022083B8,
            "spawn orphan cleanup changed its existing extent");
        KEEP(*(.overworld_field_mount_hop_tick))
        ASSERT(ABSOLUTE(.) == 0x02208400,
            "private Mount Hop bridge changed Field filler size");
        ASSERT(ABSOLUTE(.) <= 0x02208400,
            "spawn orphan cleanup exceeds its reserve");
        . = ABSOLUTE(0x02208400);
        KEEP(*(.overworld_field_wild_walk_output))
        __wild_walk_output_end = ABSOLUTE(.);
        ASSERT(ABSOLUTE(.) <= 0x02208500,
            "private Wild walk output exceeds its reserve");
        . = ABSOLUTE(0x02208500);
        KEEP(*(.overworld_field_walk_input_tuning))
        __walk_input_tuning_end = ABSOLUTE(.);
        ASSERT(ABSOLUTE(.) <= 0x02208700,
            "private Walk tuning exceeds its reserve");
        . = ABSOLUTE(0x02208700);
        KEEP(*(.overworld_field_appearance_exit))
        ASSERT(ABSOLUTE(OverworldActorAppearance_FieldExit) == 0x02208700,
            "appearance Field Exit entry moved");
        KEEP(*(.overworld_field_appearance_refresh))
        ASSERT(ABSOLUTE(.) <= 0x022088A0,
            "appearance field hooks overlap damage policy");
        . = ABSOLUTE(0x022088A0);
        __damage_policy_start = ABSOLUTE(.);
        KEEP(*(.overworld_appearance_damage_policy))
        ASSERT(ABSOLUTE(OverworldAppearancePolicy_DamageStrength) == 0x022088A0,
            "appearance damage policy entry moved");
        KEEP(*(.overworld_appearance_damage_policy.tail))
        __damage_policy_end = ABSOLUTE(.);
        ASSERT(ABSOLUTE(.) <= 0x02208900,
            "appearance damage policy overlaps world-effect delivery");
        . = ABSOLUTE(0x02208900);
        KEEP(*(.overworld_field_world_effect))
        ASSERT(ABSOLUTE(OverworldWildConditions_NotifyWorldEffect) == 0x02208900,
            "world-effect delivery entry moved");
        __world_effect_end = ABSOLUTE(.);
        KEEP(*(.overworld_field_appearance_cleanup))
        ASSERT(ABSOLUTE(.) <= 0x022089CC,
            "world-effect delivery overlaps stock graphics callback list");
        . = ABSOLUTE(ORIGIN(rom) + LENGTH(rom));
    } > rom = 0
}
