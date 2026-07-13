#ifndef TYPE_MASTERY_H
#define TYPE_MASTERY_H

#include "types.h"

#define TYPE_MASTERY_TYPE_COUNT 18
#define TYPE_MASTERY_TYPE_NONE  0xFF

#define TYPE_MASTERY_MAX_TYPE_LEVEL 5
#define TYPE_MASTERY_MAX_BOON_LEVEL 15

#define TYPE_MASTERY_SPECIALIST_BOON_LEVEL 6
#define TYPE_MASTERY_MASTER_BOON_LEVEL     11

#define TYPE_MASTERY_SAVE_MAGIC 0x544D5931 // "TMY1"

#define TYPE_MASTERY_LEVEL_1_EXP  100
#define TYPE_MASTERY_LEVEL_2_EXP  300
#define TYPE_MASTERY_LEVEL_3_EXP  700
#define TYPE_MASTERY_LEVEL_4_EXP 1500
#define TYPE_MASTERY_LEVEL_5_EXP 3000

typedef struct TypeMasterySaveData {
    u32 magic;
    u32 typeExp[TYPE_MASTERY_TYPE_COUNT];
    u8 activeType;
    u8 reserved[3];
} TypeMasterySaveData;

typedef struct TypeMasteryBattleState {
    u8 activeType;
    u8 typeLevel;
    u8 matchingCount;
    u8 commitmentMultiplier;
    u8 boonLevel;
    u8 reserved[3];
} TypeMasteryBattleState;

struct Party;
struct BattleStruct;
struct BattleSystem;

static inline BOOL TypeMastery_IsValidType(u32 type)
{
    return type < TYPE_MASTERY_TYPE_COUNT;
}

static inline void TypeMastery_InitSaveData(TypeMasterySaveData *mastery)
{
    if (mastery == NULL)
    {
        return;
    }

    MI_CpuClearFast(mastery, sizeof(*mastery));
    mastery->magic = TYPE_MASTERY_SAVE_MAGIC;
    mastery->activeType = TYPE_MASTERY_TYPE_NONE;
}

static inline void TypeMastery_EnsureSaveData(TypeMasterySaveData *mastery)
{
    if (mastery != NULL && mastery->magic != TYPE_MASTERY_SAVE_MAGIC)
    {
        TypeMastery_InitSaveData(mastery);
    }
}

static inline u32 TypeMastery_GetExp(const TypeMasterySaveData *mastery, u32 type)
{
    if (mastery == NULL || mastery->magic != TYPE_MASTERY_SAVE_MAGIC || !TypeMastery_IsValidType(type))
    {
        return 0;
    }

    return mastery->typeExp[type];
}

static inline void TypeMastery_SetExp(TypeMasterySaveData *mastery, u32 type, u32 exp)
{
    if (mastery == NULL || !TypeMastery_IsValidType(type))
    {
        return;
    }

    TypeMastery_EnsureSaveData(mastery);
    mastery->typeExp[type] = exp;
}

static inline u32 TypeMastery_AddExp(TypeMasterySaveData *mastery, u32 type, u32 amount)
{
    u32 currentExp;

    if (mastery == NULL || !TypeMastery_IsValidType(type))
    {
        return 0;
    }

    TypeMastery_EnsureSaveData(mastery);
    currentExp = mastery->typeExp[type];
    if (0xFFFFFFFF - currentExp < amount)
    {
        currentExp = 0xFFFFFFFF;
    }
    else
    {
        currentExp += amount;
    }
    mastery->typeExp[type] = currentExp;

    return currentExp;
}

static inline u8 TypeMastery_GetLevelFromExp(u32 exp)
{
    if (exp >= TYPE_MASTERY_LEVEL_5_EXP)
    {
        return 5;
    }
    if (exp >= TYPE_MASTERY_LEVEL_4_EXP)
    {
        return 4;
    }
    if (exp >= TYPE_MASTERY_LEVEL_3_EXP)
    {
        return 3;
    }
    if (exp >= TYPE_MASTERY_LEVEL_2_EXP)
    {
        return 2;
    }
    if (exp >= TYPE_MASTERY_LEVEL_1_EXP)
    {
        return 1;
    }
    return 0;
}

static inline u8 TypeMastery_GetTypeLevel(const TypeMasterySaveData *mastery, u32 type)
{
    return TypeMastery_GetLevelFromExp(TypeMastery_GetExp(mastery, type));
}

static inline u8 TypeMastery_GetActiveType(const TypeMasterySaveData *mastery)
{
    if (mastery == NULL
        || mastery->magic != TYPE_MASTERY_SAVE_MAGIC
        || !TypeMastery_IsValidType(mastery->activeType))
    {
        return TYPE_MASTERY_TYPE_NONE;
    }

    return mastery->activeType;
}

static inline BOOL TypeMastery_SetActiveType(TypeMasterySaveData *mastery, u32 type)
{
    if (mastery == NULL || !TypeMastery_IsValidType(type))
    {
        return FALSE;
    }

    TypeMastery_EnsureSaveData(mastery);
    mastery->activeType = type;
    return TRUE;
}

static inline void TypeMastery_ClearActiveType(TypeMasterySaveData *mastery)
{
    if (mastery == NULL)
    {
        return;
    }

    TypeMastery_EnsureSaveData(mastery);
    mastery->activeType = TYPE_MASTERY_TYPE_NONE;
}

static inline u8 TypeMastery_GetCommitmentMultiplier(u32 matchingCount)
{
    if (matchingCount == 0)
    {
        return 0;
    }
    if (matchingCount <= 2)
    {
        return 1;
    }
    if (matchingCount <= 4)
    {
        return 2;
    }
    return 3;
}

static inline u8 TypeMastery_CalculateBoonLevel(u32 typeLevel, u32 matchingCount)
{
    u32 boonLevel;

    if (typeLevel > TYPE_MASTERY_MAX_TYPE_LEVEL)
    {
        typeLevel = TYPE_MASTERY_MAX_TYPE_LEVEL;
    }

    boonLevel = typeLevel * TypeMastery_GetCommitmentMultiplier(matchingCount);
    if (boonLevel > TYPE_MASTERY_MAX_BOON_LEVEL)
    {
        boonLevel = TYPE_MASTERY_MAX_BOON_LEVEL;
    }

    return boonLevel;
}

u8 LONG_CALL TypeMastery_CountMatchingPartyMembers(struct Party *party, u32 type);
void LONG_CALL TypeMastery_ClearBattleState(TypeMasteryBattleState *state);
void LONG_CALL TypeMastery_BuildBattleState(
    TypeMasteryBattleState *state,
    u32 activeType,
    u32 typeLevel,
    struct Party *party);
BOOL LONG_CALL TypeMastery_CacheBattleStateForBattler(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx,
    u32 battler,
    u32 activeType,
    u32 typeLevel);
BOOL LONG_CALL TypeMastery_GetTrainerMetadata(
    u32 trainerId,
    u8 *outActiveType,
    u8 *outTypeLevel);
void LONG_CALL TypeMastery_InitializeBattleStates(
    struct BattleSystem *bsys,
    struct BattleStruct *ctx);
const TypeMasteryBattleState *LONG_CALL TypeMastery_GetBattleStateForBattler(
    const struct BattleStruct *ctx,
    u32 battler);
u8 LONG_CALL TypeMastery_GetWaterDamageBonusPercent(
    struct BattleStruct *ctx,
    u32 battler,
    u32 moveType);

#endif // TYPE_MASTERY_H
