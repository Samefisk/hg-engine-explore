#ifndef TYPE_MASTERY_WATER_TEST_FIXTURE_H
#define TYPE_MASTERY_WATER_TEST_FIXTURE_H

#define TM_TEST_MON(speciesValue, abilityValue, moveValue, hpValue) \
    { \
        .species = (speciesValue), \
        .level = 50, \
        .form = 0, \
        .ability = (abilityValue), \
        .item = ITEM_NONE, \
        .moves = { (moveValue), MOVE_NONE, MOVE_NONE, MOVE_NONE }, \
        .hp = (hpValue), \
        .status = 0, \
        .condition2 = 0, \
        .moveEffectFlags = 0, \
    }

#define TM_EMPTY_MON { .species = SPECIES_NONE }

#define TM_TARGET_PARTY \
    { \
        TM_TEST_MON(SPECIES_SNORLAX, ABILITY_IMMUNITY, MOVE_SPLASH, FULL_HP), \
        TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, \
    }

#define TM_LOW_DAMAGE_TARGET_PARTY \
    { \
        TM_TEST_MON(SPECIES_SHUCKLE, ABILITY_GLUTTONY, MOVE_SPLASH, FULL_HP), \
        TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, \
    }

#define TM_WATER_PARTY_CORE(hpValue, moveValue) \
    { \
        TM_TEST_MON(SPECIES_BLASTOISE, ABILITY_DAMP, moveValue, hpValue), \
        TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, \
    }

#define TM_WATER_PARTY_SPECIALIST(hpValue, moveValue) \
    { \
        TM_TEST_MON(SPECIES_BLASTOISE, ABILITY_DAMP, moveValue, hpValue), \
        TM_TEST_MON(SPECIES_WARTORTLE, ABILITY_DAMP, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_VAPOREON, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, \
    }

#define TM_WATER_PARTY_MASTER(hpValue, moveValue) \
    { \
        TM_TEST_MON(SPECIES_BLASTOISE, ABILITY_DAMP, moveValue, hpValue), \
        TM_TEST_MON(SPECIES_WARTORTLE, ABILITY_DAMP, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_VAPOREON, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_LAPRAS, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_GYARADOS, ABILITY_INTIMIDATE, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_STARMIE, ABILITY_NATURAL_CURE, MOVE_SPLASH, FULL_HP), \
    }

#define TM_WATER_PARTY_MASTER_LOW_DAMAGE \
    { \
        TM_TEST_MON(SPECIES_MAGIKARP, ABILITY_SWIFT_SWIM, MOVE_WATER_GUN, FULL_HP), \
        TM_TEST_MON(SPECIES_WARTORTLE, ABILITY_DAMP, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_VAPOREON, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_LAPRAS, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_GYARADOS, ABILITY_INTIMIDATE, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_STARMIE, ABILITY_NATURAL_CURE, MOVE_SPLASH, FULL_HP), \
    }

#define TM_WATER_PARTY_FOUR(hpValue, moveValue) \
    { \
        TM_TEST_MON(SPECIES_BLASTOISE, ABILITY_DAMP, moveValue, hpValue), \
        TM_TEST_MON(SPECIES_WARTORTLE, ABILITY_DAMP, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_VAPOREON, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_LAPRAS, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_EMPTY_MON, TM_EMPTY_MON, \
    }

#define TM_NON_WATER_LEAD_MASTER_PARTY(moveValue) \
    { \
        TM_TEST_MON(SPECIES_MEW, ABILITY_SYNCHRONIZE, moveValue, FULL_HP), \
        TM_TEST_MON(SPECIES_BLASTOISE, ABILITY_DAMP, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_WARTORTLE, ABILITY_DAMP, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_VAPOREON, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_LAPRAS, ABILITY_WATER_ABSORB, MOVE_SPLASH, FULL_HP), \
        TM_TEST_MON(SPECIES_GYARADOS, ABILITY_INTIMIDATE, MOVE_SPLASH, FULL_HP), \
    }

#define TM_IDLE_SCRIPT \
    { \
        { ACTION_MOVE_SLOT_1, BATTLER_PLAYER_FIRST }, \
        { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
        { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
        { ACTION_NONE, 0 }, \
    }

#define TM_PLAYER_ATTACK_SCRIPT \
    { \
        { \
            { ACTION_MOVE_SLOT_1, BATTLER_ENEMY_FIRST }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, \
        }, \
        { \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
        }, \
    }

#define TM_ENEMY_IDLE_SCRIPT \
    { \
        TM_IDLE_SCRIPT, \
        { \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
        }, \
    }

#define TM_PLAYER_IDLE_SCRIPT \
    { \
        { \
            { ACTION_MOVE_SLOT_1, BATTLER_ENEMY_FIRST }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, \
        }, \
        { \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
        }, \
    }

#define TM_ENEMY_ATTACK_SCRIPT \
    { \
        { \
            { ACTION_MOVE_SLOT_1, BATTLER_PLAYER_FIRST }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, \
        }, \
        { \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
            { ACTION_NONE, 0 }, { ACTION_NONE, 0 }, \
        }, \
    }

#define TM_STATE_EXPECTATION(battlerValue, levelValue, countValue, multiplierValue, boonValue) \
    { \
        .expectationType = EXPECTATION_TYPE_TYPE_MASTERY_STATE, \
        .battlerIDOrPartySlot = (battlerValue), \
        .expectationValue.typeMasteryState = { \
            .activeType = TYPE_WATER, \
            .typeLevel = (levelValue), \
            .matchingCount = (countValue), \
            .commitmentMultiplier = (multiplierValue), \
            .boonLevel = (boonValue), \
        }, \
    }

#define TM_BONUS_EXPECTATION(battlerValue, bonusValue) \
    { \
        .expectationType = EXPECTATION_TYPE_TYPE_MASTERY_DAMAGE_BONUS, \
        .battlerIDOrPartySlot = (battlerValue), \
        .expectationValue.typeMasteryDamageBonus = (bonusValue), \
    }

#define TM_HP_DAMAGE_EXPECTATION(battlerValue, ...) \
    { \
        .expectationType = EXPECTATION_TYPE_HP_BAR, \
        .battlerIDOrPartySlot = (battlerValue), \
        .expectationValue.hpTaken = { __VA_ARGS__ }, \
    }

#define TM_REMAINING_HP_EXPECTATION(battlerValue, ...) \
    { \
        .expectationType = EXPECTATION_TYPE_BATTLER_HP, \
        .battlerIDOrPartySlot = (battlerValue), \
        .expectationValue.hpRemaining = { __VA_ARGS__ }, \
    }

#endif // TYPE_MASTERY_WATER_TEST_FIXTURE_H
