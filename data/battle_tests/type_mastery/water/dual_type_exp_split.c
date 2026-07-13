// Test: a dual-type Pokémon splits its actual awarded EXP evenly between both types
#include "fixture.h"

#ifndef GET_TEST_CASE_ONLY
#include "../../../../include/battle.h"
#include "../../../../include/constants/ability.h"
#include "../../../../include/constants/item.h"
#include "../../../../include/constants/moves.h"
#include "../../../../include/constants/species.h"
#include "../../../../include/test_battle.h"
const struct TestBattleScenario BattleTests[] = {
#endif

    {
        .battleType = BATTLE_TYPE_SINGLE,
        .terrain = TERRAIN_NONE,
        .playerParty = {
            TM_TEST_MON(SPECIES_LAPRAS, ABILITY_WATER_ABSORB, MOVE_WATER_PULSE, FULL_HP),
            TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON,
        },
        .enemyParty = {
            TM_TEST_MON(SPECIES_RATTATA, ABILITY_RUN_AWAY, MOVE_SPLASH, 1),
            TM_TEST_MON(SPECIES_SNORLAX, ABILITY_IMMUNITY, MOVE_SPLASH, FULL_HP),
            TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON,
        },
        .playerScript = TM_PLAYER_ATTACK_SCRIPT,
        .enemyScript = TM_ENEMY_IDLE_SCRIPT,
        .expectations = {
            TM_BONUS_EXPECTATION(BATTLER_PLAYER_FIRST, 0),
            TM_EXP_EXPECTATION(TYPE_WATER, 2),
            TM_EXP_EXPECTATION(TYPE_ICE, 2),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
