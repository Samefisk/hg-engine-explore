// Test: Type Mastery caches and applies multiple qualified types at once
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
        .playerTypeMastery = {
            .enabled = TRUE,
            .typeLevels = {
                [TYPE_WATER] = 5,
                [TYPE_ICE] = 4,
                [TYPE_FIRE] = 3,
            },
        },
        .playerParty = TM_WATER_ICE_PARTY(68, MOVE_WATER_PULSE),
        .enemyParty = TM_TARGET_PARTY,
        .playerScript = TM_PLAYER_ATTACK_SCRIPT,
        .enemyScript = TM_ENEMY_IDLE_SCRIPT,
        .expectations = {
            TM_TYPE_STATE_EXPECTATION(BATTLER_PLAYER_FIRST, TYPE_WATER, 5, 2, 1, 5),
            TM_TYPE_STATE_EXPECTATION(BATTLER_PLAYER_FIRST, TYPE_ICE, 4, 2, 1, 4),
            TM_TYPE_STATE_EXPECTATION(BATTLER_PLAYER_FIRST, TYPE_FIRE, 3, 0, 0, 0),
            TM_BONUS_EXPECTATION(BATTLER_PLAYER_FIRST, 5),
        },
    },

#ifndef GET_TEST_CASE_ONLY
};
#endif
