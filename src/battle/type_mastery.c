#include "../../include/battle.h"
#include "../../include/pokemon.h"
#include "../../include/type_mastery.h"
#include "../../include/constants/species.h"

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

void LONG_CALL TypeMastery_ClearBattleState(TypeMasteryBattleState *state)
{
    if (state == NULL)
    {
        return;
    }

    memset(state, 0, sizeof(*state));
    state->activeType = TYPE_MASTERY_TYPE_NONE;
}

void LONG_CALL TypeMastery_BuildBattleState(
    TypeMasteryBattleState *state,
    u32 activeType,
    u32 typeLevel,
    struct Party *party)
{
    if (state == NULL)
    {
        return;
    }

    TypeMastery_ClearBattleState(state);
    if (!TypeMastery_IsValidType(activeType))
    {
        return;
    }

    if (typeLevel > TYPE_MASTERY_MAX_TYPE_LEVEL)
    {
        typeLevel = TYPE_MASTERY_MAX_TYPE_LEVEL;
    }

    state->activeType = activeType;
    state->typeLevel = typeLevel;
    state->matchingCount = TypeMastery_CountMatchingPartyMembers(party, activeType);
    state->commitmentMultiplier = TypeMastery_GetCommitmentMultiplier(state->matchingCount);
    state->boonLevel = TypeMastery_CalculateBoonLevel(typeLevel, state->matchingCount);
}

BOOL LONG_CALL TypeMastery_CacheBattleStateForBattler(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx,
    u32 battler,
    u32 activeType,
    u32 typeLevel)
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
        activeType,
        typeLevel,
        BattleWorkPokePartyGet(bsys, battler));
    return TRUE;
}

void LONG_CALL TypeMastery_InitializeBattleStates(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx)
{
    TypeMasterySaveData *mastery;
    struct Party *playerParty;
    u32 activeType;
    u32 typeLevel;
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
        activeType = TypeMastery_GetActiveType(mastery);
        typeLevel = TypeMastery_GetTypeLevel(mastery, activeType);

        for (battler = 0; battler < maxBattlers; battler++)
        {
            if (BATTLER_IS_PLAYERS(battler)
                && BattleWorkPokePartyGet(bsys, battler) == playerParty)
            {
                TypeMastery_CacheBattleStateForBattler(
                    bsys,
                    ctx,
                    battler,
                    activeType,
                    typeLevel);
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
        u8 trainerType;
        u8 trainerLevel;

        if (playerParty != NULL
            && BATTLER_IS_PLAYERS(battler)
            && BattleWorkPokePartyGet(bsys, battler) == playerParty)
        {
            continue;
        }

        if (TypeMastery_GetTrainerMetadata(
                BattleWork_GetTrainerIndex(bsys, battler),
                &trainerType,
                &trainerLevel))
        {
            TypeMastery_CacheBattleStateForBattler(
                bsys,
                ctx,
                battler,
                trainerType,
                trainerLevel);
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

u8 LONG_CALL TypeMastery_GetWaterDamageBonusPercent(
    struct BattleStruct *ctx,
    u32 battler,
    u32 moveType)
{
    const TypeMasteryBattleState *state;
    u8 boonLevel;
    u32 hp;
    u32 maxHp;

    state = TypeMastery_GetBattleStateForBattler(ctx, battler);
    if (state == NULL
        || state->activeType != TYPE_WATER
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
