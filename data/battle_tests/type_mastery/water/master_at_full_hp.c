// Test: Type Mastery Water - master boon stays active at full HP
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
        .playerTypeMastery = { .enabled = TRUE, .activeType = TYPE_WATER, .typeLevel = 5 },
        .playerParty = TM_WATER_PARTY_MASTER_LOW_DAMAGE,
        .enemyParty = TM_LOW_DAMAGE_TARGET_PARTY,
        .playerScript = TM_PLAYER_ATTACK_SCRIPT,
        .enemyScript = TM_ENEMY_IDLE_SCRIPT,
        .expectations = {
            TM_STATE_EXPECTATION(BATTLER_PLAYER_FIRST, 5, 6, 3, 15),
            TM_BONUS_EXPECTATION(BATTLER_PLAYER_FIRST, 15),
            TM_HP_DAMAGE_EXPECTATION(
                BATTLER_ENEMY_FIRST,
                14, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9),
            TM_REMAINING_HP_EXPECTATION(BATTLER_ENEMY_FIRST, 81, 86),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
