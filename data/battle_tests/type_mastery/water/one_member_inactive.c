// Test: Type Mastery requires at least two matching party members
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
        .playerTypeMastery = { .enabled = TRUE, .typeLevels = { [TYPE_WATER] = 5 } },
        .playerParty = {
            TM_TEST_MON(SPECIES_BLASTOISE, ABILITY_DAMP, MOVE_WATER_PULSE, 51),
            TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON, TM_EMPTY_MON,
        },
        .enemyParty = TM_TARGET_PARTY,
        .playerScript = TM_PLAYER_ATTACK_SCRIPT,
        .enemyScript = TM_ENEMY_IDLE_SCRIPT,
        .expectations = {
            TM_STATE_EXPECTATION(BATTLER_PLAYER_FIRST, 5, 1, 0, 0),
            TM_BONUS_EXPECTATION(BATTLER_PLAYER_FIRST, 0),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
