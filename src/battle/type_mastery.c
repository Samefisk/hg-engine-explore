#include "../../include/battle.h"
#include "../../include/pokemon.h"
#include "../../include/type_mastery.h"
#include "../../include/constants/species.h"

#ifdef DEBUG_BATTLE_SCENARIOS
#include "../../include/test_battle.h"
#endif

typedef char TypeMasterySaveDataSizeCheck[(sizeof(TypeMasterySaveData) == 0x50) ? 1 : -1];
typedef char TypeMasteryTypeCountCheck[(TYPE_MASTERY_TYPE_COUNT == TYPE_DARK + 1) ? 1 : -1];

u8 LONG_CALL TypeMastery_CountMatchingPartyMembers(struct Party *party, u32 type)
{
    int partyCount;
    int i;
    u8 matchingCount = 0;

    if (party == NULL || !TypeMastery_IsValidType(type))
    {
        return 0;
    }

    partyCount = party->count;
    if (partyCount < 0)
    {
        partyCount = 0;
    }
    else if (partyCount > 6)
    {
        partyCount = 6;
    }

    for (i = 0; i < partyCount; i++)
    {
        struct PartyPokemon *mon = Party_GetMonByIndex(party, i);
        u32 type1;
        u32 type2;

        if (mon == NULL
            || GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_NONE
            || GetMonData(mon, MON_DATA_IS_EGG, NULL))
        {
            continue;
        }

        type1 = GetMonData(mon, MON_DATA_TYPE_1, NULL);
        type2 = GetMonData(mon, MON_DATA_TYPE_2, NULL);
        if (type1 == type || type2 == type)
        {
            matchingCount++;
        }
    }

    return matchingCount;
}

static void TypeMastery_AwardTypeExp(
    TypeMasterySaveData *mastery,
    u32 type,
    u32 typeExp,
    u32 pokemonExp)
{
    if (!TypeMastery_IsValidType(type) || typeExp == 0)
    {
        return;
    }

    TypeMastery_AddExp(mastery, type, typeExp);
#ifdef DEBUG_BATTLE_SCENARIOS
    TestBattle_RecordTypeMasteryExp(type, typeExp, pokemonExp);
#else
    (void)pokemonExp;
#endif
}

void LONG_CALL TypeMastery_AwardPokemonExp(
    TypeMasterySaveData *mastery,
    struct PartyPokemon *mon,
    u32 pokemonExp)
{
    u32 type1;
    u32 type2;
    u32 splitExp;

    if (mon == NULL || pokemonExp == 0)
    {
        return;
    }

    type1 = GetMonData(mon, MON_DATA_TYPE_1, NULL);
    type2 = GetMonData(mon, MON_DATA_TYPE_2, NULL);
    if (!TypeMastery_IsValidType(type1) || !TypeMastery_IsValidType(type2))
    {
        return;
    }

    if (type1 == type2)
    {
        TypeMastery_AwardTypeExp(mastery, type1, pokemonExp, pokemonExp);
        return;
    }

    splitExp = pokemonExp / 2;
    TypeMastery_AwardTypeExp(mastery, type1, splitExp, pokemonExp);
    TypeMastery_AwardTypeExp(mastery, type2, splitExp, pokemonExp);
}

void LONG_CALL TypeMastery_ClearBattleState(TypeMasteryBattleState *state)
{
    if (state == NULL)
    {
        return;
    }

    memset(state, 0, sizeof(*state));
}

void LONG_CALL TypeMastery_BuildBattleState(
    TypeMasteryBattleState *state,
    const u8 typeLevels[TYPE_MASTERY_TYPE_COUNT],
    struct Party *party)
{
    u32 type;

    if (state == NULL)
    {
        return;
    }

    TypeMastery_ClearBattleState(state);
    if (typeLevels == NULL)
    {
        return;
    }

    for (type = 0; type < TYPE_MASTERY_TYPE_COUNT; type++)
    {
        TypeMasteryTypeBattleState *typeState = &state->types[type];
        u32 typeLevel = typeLevels[type];

        if (typeLevel > TYPE_MASTERY_MAX_TYPE_LEVEL)
        {
            typeLevel = TYPE_MASTERY_MAX_TYPE_LEVEL;
        }

        typeState->typeLevel = typeLevel;
        typeState->matchingCount = TypeMastery_CountMatchingPartyMembers(party, type);
        typeState->commitmentMultiplier = TypeMastery_GetCommitmentMultiplier(typeState->matchingCount);
        typeState->boonLevel = TypeMastery_CalculateBoonLevel(typeLevel, typeState->matchingCount);
    }
}

BOOL LONG_CALL TypeMastery_CacheBattleStateForBattler(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx,
    u32 battler,
    const u8 typeLevels[TYPE_MASTERY_TYPE_COUNT])
{
    u32 maxBattlers;

    if (bsys == NULL || ctx == NULL || battler >= CLIENT_MAX)
    {
        return FALSE;
    }

    maxBattlers = BattleWorkClientSetMaxGet(bsys);
    if (battler >= maxBattlers)
    {
        return FALSE;
    }

    TypeMastery_BuildBattleState(
        &ctx->typeMastery[battler],
        typeLevels,
        BattleWorkPokePartyGet(bsys, battler));
    return TRUE;
}

void LONG_CALL TypeMastery_InitializeBattleStates(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx)
{
    TypeMasterySaveData *mastery;
    struct Party *playerParty;
    u8 typeLevels[TYPE_MASTERY_TYPE_COUNT];
    u32 battleType;
    u32 maxBattlers;
    u32 battler;

    if (ctx == NULL)
    {
        return;
    }

    for (battler = 0; battler < CLIENT_MAX; battler++)
    {
        TypeMastery_ClearBattleState(&ctx->typeMastery[battler]);
    }

    if (bsys == NULL)
    {
        return;
    }

    playerParty = BattleWorkPokePartyGet(bsys, BATTLER_PLAYER);
    maxBattlers = BattleWorkClientSetMaxGet(bsys);
    if (maxBattlers > CLIENT_MAX)
    {
        maxBattlers = CLIENT_MAX;
    }

    mastery = TypeMastery_GetSaveData(SaveBlock2_get());
    if (mastery != NULL && playerParty != NULL)
    {
        for (u32 type = 0; type < TYPE_MASTERY_TYPE_COUNT; type++)
        {
            typeLevels[type] = TypeMastery_GetTypeLevel(mastery, type);
        }

        for (battler = 0; battler < maxBattlers; battler++)
        {
            if (BATTLER_IS_PLAYERS(battler)
                && BattleWorkPokePartyGet(bsys, battler) == playerParty)
            {
                TypeMastery_CacheBattleStateForBattler(
                    bsys,
                    ctx,
                    battler,
                    typeLevels);
            }
        }
    }

    battleType = BattleTypeGet(bsys);
    if (!(battleType & BATTLE_TYPE_TRAINER)
        || (battleType & (BATTLE_TYPE_WIRELESS | BATTLE_TYPE_BATTLE_TOWER)))
    {
        return;
    }

    for (battler = 0; battler < maxBattlers; battler++)
    {
        if (playerParty != NULL
            && BATTLER_IS_PLAYERS(battler)
            && BattleWorkPokePartyGet(bsys, battler) == playerParty)
        {
            continue;
        }

        if (TypeMastery_GetTrainerTypeLevels(
                BattleWork_GetTrainerIndex(bsys, battler),
                typeLevels))
        {
            TypeMastery_CacheBattleStateForBattler(
                bsys,
                ctx,
                battler,
                typeLevels);
        }
    }
}

const TypeMasteryBattleState *LONG_CALL TypeMastery_GetBattleStateForBattler(
    const struct BattleStruct *ctx,
    u32 battler)
{
    if (ctx == NULL || battler >= CLIENT_MAX)
    {
        return NULL;
    }

    return &ctx->typeMastery[battler];
}

const TypeMasteryTypeBattleState *LONG_CALL TypeMastery_GetTypeBattleStateForBattler(
    const struct BattleStruct *ctx,
    u32 battler,
    u32 type)
{
    const TypeMasteryBattleState *state;

    if (!TypeMastery_IsValidType(type))
    {
        return NULL;
    }

    state = TypeMastery_GetBattleStateForBattler(ctx, battler);
    if (state == NULL)
    {
        return NULL;
    }

    return &state->types[type];
}

u8 LONG_CALL TypeMastery_GetWaterDamageBonusPercent(
    struct BattleStruct *ctx,
    u32 battler,
    u32 moveType)
{
    const TypeMasteryTypeBattleState *state;
    u8 boonLevel;
    u32 hp;
    u32 maxHp;

    state = TypeMastery_GetTypeBattleStateForBattler(ctx, battler, TYPE_WATER);
    if (state == NULL
        || state->boonLevel == 0
        || moveType != TYPE_WATER
        || !HasType(ctx, battler, TYPE_WATER))
    {
        return 0;
    }

    boonLevel = state->boonLevel;
    if (boonLevel > TYPE_MASTERY_MAX_BOON_LEVEL)
    {
        boonLevel = TYPE_MASTERY_MAX_BOON_LEVEL;
    }

    hp = ctx->battlemon[battler].hp;
    maxHp = ctx->battlemon[battler].maxhp;
    if (hp == 0 || maxHp == 0)
    {
        return 0;
    }

    if (boonLevel < TYPE_MASTERY_SPECIALIST_BOON_LEVEL
        && hp * 3 > maxHp)
    {
        return 0;
    }
    if (boonLevel < TYPE_MASTERY_MASTER_BOON_LEVEL
        && hp * 2 > maxHp)
    {
        return 0;
    }

    return boonLevel;
}
