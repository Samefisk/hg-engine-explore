#include "../../include/types.h"
#include "../../include/debug.h"

#ifdef DEBUG_BATTLE_SCENARIOS

#include "../../include/battle.h"
#include "../../include/pokemon.h"
#include "../../include/test_battle.h"
#include "../../include/type_mastery.h"
#include "../../include/constants/file.h"
#include "../../include/constants/generated/test_battle.h"
#include "../../include/constants/item.h"
#include "../../include/constants/moves.h"
#include "../../include/constants/species.h"

typedef char TestBattleTestIndexCapacityCheck[
    (TEST_BATTLE_TOTAL_TESTS <= STATE_TEST_INDEX_MASK + 1) ? 1 : -1];

static int *sEmulatorCommunicationSendHole = (int *)0x02FFF81C;
static BOOL sPartiesPrepared;
static BOOL sBattleStateApplied;

static void TestBattle_AllocAndLoadScenario(void)
{
    int testIndex;

    if (gTestBattleScenario == NULL) {
        gTestBattleScenario =
            sys_AllocMemory(HEAPID_DEFAULT, sizeof(struct TestBattleScenario));
    }
    if (gTestBattleScenario == NULL) {
        return;
    }

    testIndex = TestBattle_StateGetCurrentTestIndex();
    ArchiveDataLoadOfs(
        gTestBattleScenario,
        ARC_CODE_ADDONS,
        CODE_ADDON_BATTLE_TESTS,
        testIndex * sizeof(struct TestBattleScenario),
        sizeof(struct TestBattleScenario));
}

static void TestBattle_OverridePokemon(
    struct PartyPokemon *mon,
    const struct TestBattlePokemon *testMon)
{
    int i;
    u8 friendship = 255;

    PokeParaSet(mon, testMon->species, testMon->level, 31, FALSE, 0, 0, 0);
    SetMonData(mon, MON_DATA_FORM, (void *)&testMon->form);
    SetMonData(mon, MON_DATA_ABILITY, (void *)&testMon->ability);
    SetMonData(mon, MON_DATA_HELD_ITEM, (void *)&testMon->item);
    SET_MON_NATURE_OVERRIDE(mon, NATURE_HARDY);

    for (i = 0; i < 4; i++) {
        if (testMon->moves[i] != MOVE_NONE) {
            u32 pp = 40;
            SetMonData(mon, MON_DATA_MOVE1 + i, (void *)&testMon->moves[i]);
            SetMonData(mon, MON_DATA_MOVE1MAXPP + i, &pp);
            SetMonData(mon, MON_DATA_MOVE1PP + i, &pp);
        }
    }

    if (testMon->hp == FULL_HP) {
        u16 maxHP = (u16)GetMonData(mon, MON_DATA_MAXHP, NULL);
        SetMonData(mon, MON_DATA_HP, &maxHP);
    } else {
        SetMonData(mon, MON_DATA_HP, (void *)&testMon->hp);
    }
    SetMonData(mon, MON_DATA_STATUS, (void *)&testMon->status);
    SetMonData(mon, MON_DATA_FRIENDSHIP, &friendship);
    RecalcPartyPokemonStats(mon);
    ChangeToBattleForm(mon);
    RecalcPartyPokemonStats(mon);
}

static void TestBattle_OverridePartySlot(
    struct Party *party,
    int slot,
    const struct TestBattlePokemon *testMon)
{
    struct PartyPokemon *mon;

    if (party == NULL) {
        return;
    }
    mon = Party_GetMonByIndex(party, slot);
    if (mon != NULL) {
        TestBattle_OverridePokemon(mon, testMon);
    }
}

void LONG_CALL TestBattle_OverrideParties(struct BattleSystem *bsys)
{
    const struct TestBattleScenario *scenario;
    struct Party *playerParty;
    struct Party *enemyParty;
    int enemyCount = 0;
    int playerCount = 0;
    int slot;
    int testIndex;

    if (sPartiesPrepared) {
        return;
    }

    playerParty = BattleWorkPokePartyGet(bsys, BATTLER_PLAYER_FIRST);
    enemyParty = BattleWorkPokePartyGet(bsys, BATTLER_ENEMY_FIRST);
    if (playerParty == NULL || enemyParty == NULL) {
        return;
    }

    if (TestBattle_StateIsComplete()) {
        TestBattle_StateSetCurrentTestIndex(TestBattle_StateGetCurrentTestIndex() + 1);
    }
    TestBattle_StateSetComplete(FALSE);
    testIndex = TestBattle_StateGetCurrentTestIndex();
    TestBattle_StateSetHasMoreTests((testIndex + 1) < TEST_BATTLE_TOTAL_TESTS);
    TestBattle_StateResetScriptIndices();
    TestBattle_AllocAndLoadScenario();
    if (gTestBattleScenario == NULL) {
        return;
    }

    scenario = gTestBattleScenario;
    if (scenario->enemyTrainerId != 0) {
        bsys->battleType |= BATTLE_TYPE_TRAINER;
        bsys->trainerId[BATTLER_ENEMY_FIRST] = scenario->enemyTrainerId;
    }
    for (slot = 0; slot < 6 && scenario->enemyParty[slot].species != SPECIES_NONE; slot++) {
        enemyCount++;
    }
    for (slot = 0; slot < 6 && scenario->playerParty[slot].species != SPECIES_NONE; slot++) {
        playerCount++;
    }
    if (scenario->battleType & BATTLE_TYPE_DOUBLE) {
        bsys->battleType = BATTLE_TYPE_TRAINER | scenario->battleType;
    }
    if (playerParty != NULL) {
        playerParty->count = playerCount;
        for (slot = 0; slot < playerCount; slot++) {
            TestBattle_OverridePartySlot(playerParty, slot, &scenario->playerParty[slot]);
        }
    }
    if (enemyParty != NULL) {
        for (slot = enemyParty->count; slot < enemyCount; slot++) {
            struct PartyPokemon tempMon;
            PokeParaSet(&tempMon, SPECIES_BULBASAUR, 5, 0, FALSE, 0, 0, 0);
            PokeParty_Add(enemyParty, &tempMon);
        }
        enemyParty->count = enemyCount;
        for (slot = 0; slot < enemyCount; slot++) {
            TestBattle_OverridePartySlot(enemyParty, slot, &scenario->enemyParty[slot]);
        }
    }
    bsys->trainers[1].poke_count = enemyCount;
    sPartiesPrepared = TRUE;
}

void LONG_CALL SendValueThroughCommunicationSendHole(int value)
{
    *sEmulatorCommunicationSendHole = value;
}

struct TestBattleScenario *LONG_CALL TestBattle_GetCurrentScenario(void)
{
    return gTestBattleScenario;
}

BOOL LONG_CALL TestBattle_HasMoreExpectations(void)
{
    if (gTestBattleScenario == NULL) {
        return FALSE;
    }

    return gTestBattleScenario->expectationPassCount != MAX_EXPECTATIONS
        && gTestBattleScenario
                ->expectations[gTestBattleScenario->expectationPassCount]
                .expectationType
            != 0;
}

static void TestBattle_ApplyTypeMasterySettings(
    struct BattleSystem *bsys,
    struct BattleStruct *sp)
{
    u32 battler;
    u32 maxBattlers;

    if (!gTestBattleScenario->useProductionTypeMastery) {
        for (battler = 0; battler < CLIENT_MAX; battler++) {
            TypeMastery_ClearBattleState(&sp->typeMastery[battler]);
        }
    }

    maxBattlers = BattleWorkClientSetMaxGet(bsys);
    if (maxBattlers == 0 || maxBattlers > CLIENT_MAX) {
        maxBattlers = CLIENT_MAX;
    }

    for (battler = 0; battler < maxBattlers; battler++) {
        const struct TestTypeMasterySettings *settings = BATTLER_IS_PLAYERS(battler)
            ? &gTestBattleScenario->playerTypeMastery
            : &gTestBattleScenario->enemyTypeMastery;

        if (settings->enabled) {
            TypeMastery_BuildBattleState(
                &sp->typeMastery[battler],
                settings->typeLevels,
                BattleWorkPokePartyGet(bsys, battler));
        }
    }
}

static void TestBattle_CheckTypeMasteryStateExpectations(struct BattleStruct *sp)
{
    while (TestBattle_HasMoreExpectations()) {
        const struct Expectations *expectation =
            &gTestBattleScenario->expectations[gTestBattleScenario->expectationPassCount];
        const struct TestTypeMasteryStateExpectation *expected;
        const TypeMasteryTypeBattleState *actual;

        if (expectation->expectationType != EXPECTATION_TYPE_TYPE_MASTERY_STATE) {
            break;
        }

        expected = &expectation->expectationValue.typeMasteryState;
        actual = TypeMastery_GetTypeBattleStateForBattler(
            sp,
            expectation->battlerIDOrPartySlot,
            expected->type);
        if (actual == NULL
            || actual->typeLevel != expected->typeLevel
            || actual->matchingCount != expected->matchingCount
            || actual->commitmentMultiplier != expected->commitmentMultiplier
            || actual->boonLevel != expected->boonLevel) {
            if (actual != NULL) {
                debug_printf(
                    "TM type %d state got %d/%d/%d/%d expected %d/%d/%d/%d\n",
                    expected->type,
                    actual->typeLevel,
                    actual->matchingCount,
                    actual->commitmentMultiplier,
                    actual->boonLevel,
                    expected->typeLevel,
                    expected->matchingCount,
                    expected->commitmentMultiplier,
                    expected->boonLevel);
            }
            break;
        }

        gTestBattleScenario->expectationPassCount++;
    }
}

void LONG_CALL TestBattle_ApplyBattleState(
    struct BattleSystem *bsys,
    struct BattleStruct *sp)
{
    int slot;

    if (sBattleStateApplied
        || !sPartiesPrepared
        || gTestBattleScenario == NULL
        || sp->server_seq_no == CONTROLLER_COMMAND_GET_BATTLE_MON) {
        return;
    }

    if (gTestBattleScenario->battleType & BATTLE_TYPE_DOUBLE) {
        sp->sel_mons_no[BATTLER_PLAYER_FIRST] = 0;
        if (gTestBattleScenario->playerParty[1].species != 0) {
            sp->sel_mons_no[BATTLER_PLAYER_SECOND] = 1;
        }
        sp->sel_mons_no[BATTLER_ENEMY_FIRST] = 0;
        if (gTestBattleScenario->enemyParty[1].species != 0) {
            sp->sel_mons_no[BATTLER_ENEMY_SECOND] = 1;
        }
    }

    for (slot = 0; slot < 2; slot++) {
        const struct TestBattlePokemon *mon = &gTestBattleScenario->playerParty[slot];
        int battler = slot == 0 ? BATTLER_PLAYER_FIRST : BATTLER_PLAYER_SECOND;

        if (mon->species == 0) {
            continue;
        }
        if (mon->status) {
            sp->battlemon[battler].condition |= mon->status;
        }
        if (mon->condition2) {
            sp->battlemon[battler].condition2 |= mon->condition2;
            if (mon->condition2 & STATUS2_RECHARGE) {
                sp->battlemon[battler].moveeffect.rechargeCount = 2;
                if (mon->item == ITEM_CHOICE_BAND
                    || mon->item == ITEM_CHOICE_SPECS
                    || mon->item == ITEM_CHOICE_SCARF) {
                    sp->battlemon[battler].moveeffect.moveNoChoice = mon->moves[0];
                }
            }
        }
        if (mon->moveEffectFlags) {
            sp->battlemon[battler].effect_of_moves |= mon->moveEffectFlags;
        }
    }

    for (slot = 0; slot < 2; slot++) {
        const struct TestBattlePokemon *mon = &gTestBattleScenario->enemyParty[slot];
        int battler = slot == 0 ? BATTLER_ENEMY_FIRST : BATTLER_ENEMY_SECOND;

        if (mon->species == 0) {
            continue;
        }
        if (mon->status) {
            sp->battlemon[battler].condition |= mon->status;
        }
        if (mon->condition2) {
            sp->battlemon[battler].condition2 |= mon->condition2;
            if (mon->condition2 & STATUS2_RECHARGE) {
                sp->battlemon[battler].moveeffect.rechargeCount = 2;
                if (mon->item == ITEM_CHOICE_BAND
                    || mon->item == ITEM_CHOICE_SPECS
                    || mon->item == ITEM_CHOICE_SCARF) {
                    sp->battlemon[battler].moveeffect.moveNoChoice = mon->moves[0];
                }
            }
        }
        if (mon->moveEffectFlags) {
            sp->battlemon[battler].effect_of_moves |= mon->moveEffectFlags;
        }
    }

    sp->field_condition |= gTestBattleScenario->weather;
    sp->field_condition |= gTestBattleScenario->fieldCondition;
    sp->terrainOverlay.type = gTestBattleScenario->terrain;
    sp->terrainOverlay.numberOfTurnsLeft =
        gTestBattleScenario->terrain == TERRAIN_NONE ? 0 : 255;

    TestBattle_ApplyTypeMasterySettings(bsys, sp);
    TestBattle_CheckTypeMasteryStateExpectations(sp);
    sBattleStateApplied = TRUE;
}

void LONG_CALL TestBattle_RecordTypeMasteryDamageBonus(u32 battler, u32 bonusPercent)
{
    const struct Expectations *expectation;

    if (!TestBattle_HasMoreExpectations()) {
        return;
    }

    expectation =
        &gTestBattleScenario->expectations[gTestBattleScenario->expectationPassCount];
    if (expectation->expectationType == EXPECTATION_TYPE_TYPE_MASTERY_DAMAGE_BONUS
        && expectation->battlerIDOrPartySlot == battler
        && expectation->expectationValue.typeMasteryDamageBonus == bonusPercent) {
        gTestBattleScenario->expectationPassCount++;
    } else if (expectation->expectationType
        == EXPECTATION_TYPE_TYPE_MASTERY_DAMAGE_BONUS) {
        debug_printf(
            "TM bonus battler %d got %d expected battler %d bonus %d\n",
            battler,
            bonusPercent,
            expectation->battlerIDOrPartySlot,
            expectation->expectationValue.typeMasteryDamageBonus);
    }
}

void LONG_CALL TestBattle_RecordTypeMasteryExp(
    u32 type,
    u32 typeExp,
    u32 pokemonExp)
{
    const struct Expectations *expectation;
    const struct TestTypeMasteryExpExpectation *expected;

    if (!TestBattle_HasMoreExpectations()) {
        return;
    }

    expectation =
        &gTestBattleScenario->expectations[gTestBattleScenario->expectationPassCount];
    if (expectation->expectationType != EXPECTATION_TYPE_TYPE_MASTERY_EXP) {
        return;
    }

    expected = &expectation->expectationValue.typeMasteryExp;
    if (pokemonExp > 0
        && expected->divisor > 0
        && type == expected->type
        && typeExp == pokemonExp / expected->divisor) {
        gTestBattleScenario->expectationPassCount++;
    } else {
        debug_printf(
            "TM EXP type %d got %d/%d expected type %d divisor %d\n",
            type,
            typeExp,
            pokemonExp,
            expected->type,
            expected->divisor);
    }
}

static BOOL TestBattle_AreScriptsComplete(void)
{
    int battler;
    int maxBattlers;

    if (gTestBattleScenario == NULL) {
        return FALSE;
    }

    maxBattlers = (gTestBattleScenario->battleType & BATTLE_TYPE_DOUBLE) ? 4 : 2;
    for (battler = 0; battler < maxBattlers; battler++) {
        const struct BattleAction *script;
        int scriptSlot = (battler == BATTLER_PLAYER_FIRST
                             || battler == BATTLER_ENEMY_FIRST)
            ? 0
            : 1;
        int scriptIndex = TestBattle_StateGetScriptIndex(battler);

        if (battler == BATTLER_PLAYER_FIRST || battler == BATTLER_PLAYER_SECOND) {
            script = gTestBattleScenario->playerScript[scriptSlot];
        } else {
            script = gTestBattleScenario->enemyScript[scriptSlot];
        }

        if (scriptIndex < AI_SCRIPT_MAX_MOVES
            && script[scriptIndex].action != ACTION_NONE) {
            return FALSE;
        }
    }

    return TRUE;
}

static void TestBattle_CheckBattlerHpExpectation(struct BattleStruct *sp)
{
    const struct Expectations *expectation;
    u32 hp;
    int i;

    if (!TestBattle_HasMoreExpectations()) {
        return;
    }

    expectation =
        &gTestBattleScenario->expectations[gTestBattleScenario->expectationPassCount];
    if (expectation->expectationType != EXPECTATION_TYPE_BATTLER_HP
        || expectation->battlerIDOrPartySlot >= CLIENT_MAX) {
        return;
    }

    hp = sp->battlemon[expectation->battlerIDOrPartySlot].hp;
    for (i = 0; i < 16; i++) {
        if (hp == expectation->expectationValue.hpRemaining[i]) {
            gTestBattleScenario->expectationPassCount++;
            return;
        }
    }

    debug_printf(
        "Battler %d HP got %d; no allowed value matched\n",
        expectation->battlerIDOrPartySlot,
        hp);
}

static void TestBattle_CheckScriptCompletion(struct BattleStruct *sp)
{
    if (!TestBattle_StateIsComplete() && TestBattle_AreScriptsComplete()) {
        TestBattle_CheckBattlerHpExpectation(sp);
        TestBattle_StateSetComplete(TRUE);
        gTestBattleState &= ~STATE_QUEUED_BIT;
    }
}

BOOL LONG_CALL TestBattle_IsComplete(void)
{
    return TestBattle_StateIsComplete();
}

void LONG_CALL TestBattle_GetAIScriptedMove(int battler, u8 *moveSlot, u8 *target)
{
    const struct BattleAction *script;
    struct BattleAction action;
    int scriptSlot;
    int scriptIndex;

    *moveSlot = 0;
    *target = 0;
    if (gTestBattleScenario == NULL || battler < 0 || battler >= CLIENT_MAX) {
        return;
    }

    scriptSlot = (battler == BATTLER_PLAYER_FIRST || battler == BATTLER_ENEMY_FIRST)
        ? 0
        : 1;
    script = (battler == BATTLER_PLAYER_FIRST || battler == BATTLER_PLAYER_SECOND)
        ? gTestBattleScenario->playerScript[scriptSlot]
        : gTestBattleScenario->enemyScript[scriptSlot];
    scriptIndex = TestBattle_StateGetScriptIndex(battler);
    if (scriptIndex >= AI_SCRIPT_MAX_MOVES) {
        return;
    }

    action = script[scriptIndex];
    if (action.action == ACTION_NONE) {
        return;
    }
    if (action.action <= ACTION_MOVE_SLOT_4) {
        *moveSlot = action.action;
        *target = action.target;
    }
    TestBattle_StateIncrementScriptIndex(battler);
}

u8 LONG_CALL TestBattle_AISelectMove(struct BattleSystem *bsys, int battler)
{
    u8 moveSlot;
    u8 target;

    TestBattle_GetAIScriptedMove(battler, &moveSlot, &target);
    bsys->sp->waza_no_pos[battler] = moveSlot;
    bsys->sp->aiWorkTable.ai_dir_select_client[battler] = target;
    return moveSlot;
}

int LONG_CALL TestBattle_AIPickCommand(struct BattleSystem *bsys, int battler)
{
    const struct BattleAction *script;
    struct BattleAction action;
    int scriptSlot;
    int scriptIndex;

    if (battler == BATTLER_PLAYER_FIRST || battler == BATTLER_PLAYER_SECOND
        || gTestBattleScenario == NULL || bsys == NULL || bsys->sp == NULL) {
        return 1;
    }

    scriptSlot = battler == BATTLER_ENEMY_FIRST ? 0 : 1;
    script = gTestBattleScenario->enemyScript[scriptSlot];
    TestBattle_CheckScriptCompletion(bsys->sp);
    if (TestBattle_StateIsComplete()) {
        return 1;
    }

    scriptIndex = TestBattle_StateGetScriptIndex(battler);
    if (scriptIndex >= AI_SCRIPT_MAX_MOVES) {
        return 1;
    }

    action = script[scriptIndex];
    if (action.action >= ACTION_SWITCH_SLOT_0
        && action.action <= ACTION_SWITCH_SLOT_5) {
        bsys->sp->ai_reshuffle_sel_mons_no[battler] =
            action.action - ACTION_SWITCH_SLOT_0;
        TestBattle_StateIncrementScriptIndex(battler);
        return 3;
    }

    return 1;
}

static void TestBattle_SelectPlayerAction(
    struct BattleStruct *ctx,
    int battler,
    const struct BattleAction *script)
{
    int scriptIndex = TestBattle_StateGetScriptIndex(battler);
    struct BattleAction action;

    if (scriptIndex >= AI_SCRIPT_MAX_MOVES) {
        return;
    }

    action = script[scriptIndex];
    if (action.action == ACTION_NONE) {
        return;
    }

    if (action.action >= ACTION_SWITCH_SLOT_0
        && action.action <= ACTION_SWITCH_SLOT_5) {
        u8 partySlot = action.action - ACTION_SWITCH_SLOT_0;
        ctx->playerActions[battler][0] = CONTROLLER_COMMAND_POKEMON_INPUT;
        ctx->playerActions[battler][1] = partySlot;
        ctx->playerActions[battler][2] = 0;
        ctx->playerActions[battler][3] = SELECT_POKEMON_COMMAND;
        ctx->reshuffle_sel_mons_no[battler] = partySlot;
    } else {
        u8 moveSlot = action.action;
        ctx->playerActions[battler][0] = CONTROLLER_COMMAND_FIGHT_INPUT;
        ctx->playerActions[battler][1] = action.target;
        ctx->playerActions[battler][2] = moveSlot + 1;
        ctx->playerActions[battler][3] = SELECT_FIGHT_COMMAND;
        ctx->waza_no_pos[battler] = moveSlot;
        ctx->waza_no_select[battler] = ctx->battlemon[battler].move[moveSlot];
    }

    ctx->com_seq_no[battler] = SSI_STATE_END;
    ctx->ret_seq_no[battler] = SSI_STATE_13;
    TestBattle_StateIncrementScriptIndex(battler);
}

void LONG_CALL TestBattle_autoSelectPlayerMoves(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx)
{
    if (ctx->server_seq_no != CONTROLLER_COMMAND_SELECTION_SCREEN_INPUT
        || ctx->com_seq_no[BATTLER_PLAYER_FIRST] != SSI_STATE_SELECT_COMMAND_INIT
        || gTestBattleScenario == NULL) {
        return;
    }

    TestBattle_CheckScriptCompletion(ctx);
    TestBattle_SelectPlayerAction(
        ctx,
        BATTLER_PLAYER_FIRST,
        gTestBattleScenario->playerScript[0]);

    if (BattleTypeGet(bsys) & BATTLE_TYPE_DOUBLE) {
        TestBattle_SelectPlayerAction(
            ctx,
            BATTLER_PLAYER_SECOND,
            gTestBattleScenario->playerScript[1]);
    }
}

#endif // DEBUG_BATTLE_SCENARIOS
