#include "../include/player_health_model.h"
#include "../include/save.h"

#ifdef OVERWORLD_BEHAVIOR_HOST
#define PLAYER_HEALTH_TAIL_SECTION
#else
#define PLAYER_HEALTH_TAIL_SECTION __attribute__((section(".player_health_tail_end")))
#endif

#define PLAYER_HEALTH_SAVE_MAGIC_0 'P'
#define PLAYER_HEALTH_SAVE_MAGIC_1 'H'
#define PLAYER_HEALTH_SAVE_VERSION 1
#define PLAYER_HEALTH_MOM_SPAWN 1
#define PLAYER_HEALTH_LAST_SPAWN 30
#define PLAYER_HEALTH_LOCAL_FIELD_BLOCK 5
#define PLAYER_HEALTH_BLACKOUT_SPAWN_OFFSET 0x68

static BOOL PlayerHealthSave_IsValidSpawn(u16 spawn)
{
    return spawn >= PLAYER_HEALTH_MOM_SPAWN
        && spawn <= PLAYER_HEALTH_LAST_SPAWN;
}

static u16 PlayerHealthSave_LegacySpawn(SaveData *saveData)
{
    u8 *localFieldData = SaveArray_Get(saveData,
        PLAYER_HEALTH_LOCAL_FIELD_BLOCK);
    u16 spawn;

    if (localFieldData == NULL) {
        return PLAYER_HEALTH_MOM_SPAWN;
    }
    /* LocalFieldData::lastSpawn is at 0x68 in stock save block 5. */
    spawn = *(u16 *)(localFieldData + PLAYER_HEALTH_BLACKOUT_SPAWN_OFFSET);
    return PlayerHealthSave_IsValidSpawn(spawn)
        ? spawn : PLAYER_HEALTH_MOM_SPAWN;
}

static void PlayerHealthSave_InitializeRecord(SaveData *saveData,
    struct SAVE_MISC_DATA *saveMiscData)
{
    u16 spawn = PlayerHealthSave_LegacySpawn(saveData);

    saveMiscData->playerHealthSignature[0] = PLAYER_HEALTH_SAVE_MAGIC_0;
    saveMiscData->playerHealthSignature[1] = PLAYER_HEALTH_SAVE_MAGIC_1;
    saveMiscData->playerHealthSignature[2] = PLAYER_HEALTH_SAVE_VERSION;
    saveMiscData->playerHealthState[0] = PLAYER_HEALTH_MAX_HP;
    saveMiscData->playerHealthState[1] = (u8)spawn;
    saveMiscData->playerHealthState[2] = (u8)(spawn >> 8);
}

static void PlayerHealthSave_EnsureRecord(SaveData *saveData,
    struct SAVE_MISC_DATA *saveMiscData)
{
    u16 spawn;

    if (saveMiscData->playerHealthSignature[0] != PLAYER_HEALTH_SAVE_MAGIC_0
        || saveMiscData->playerHealthSignature[1] != PLAYER_HEALTH_SAVE_MAGIC_1
        || saveMiscData->playerHealthSignature[2] != PLAYER_HEALTH_SAVE_VERSION) {
        /* An older save has no player HP. Give it full HP and a safe return. */
        PlayerHealthSave_InitializeRecord(saveData, saveMiscData);
        return;
    }

    if (saveMiscData->playerHealthState[0] > PLAYER_HEALTH_MAX_HP) {
        saveMiscData->playerHealthState[0] = PLAYER_HEALTH_MAX_HP;
    }
    spawn = saveMiscData->playerHealthState[1]
        | (saveMiscData->playerHealthState[2] << 8);
    if (!PlayerHealthSave_IsValidSpawn(spawn)) {
        saveMiscData->playerHealthState[1] = PLAYER_HEALTH_MOM_SPAWN;
        saveMiscData->playerHealthState[2] = 0;
    }
}

u8 LONG_CALL PLAYER_HEALTH_TAIL_SECTION PlayerHealthSave_GetHP(SaveData *saveData)
{
    struct SAVE_MISC_DATA *saveMiscData;

    if (saveData == NULL) {
        return PLAYER_HEALTH_MAX_HP;
    }
    saveMiscData = Sav2_Misc_get(saveData);
    PlayerHealthSave_EnsureRecord(saveData, saveMiscData);
    return saveMiscData->playerHealthState[0];
}

void LONG_CALL PlayerHealthSave_SetHP(SaveData *saveData, u8 hp)
{
    struct SAVE_MISC_DATA *saveMiscData;

    if (saveData == NULL) {
        return;
    }
    saveMiscData = Sav2_Misc_get(saveData);
    PlayerHealthSave_EnsureRecord(saveData, saveMiscData);
    saveMiscData->playerHealthState[0] = hp > PLAYER_HEALTH_MAX_HP
        ? PLAYER_HEALTH_MAX_HP : hp;
}

u16 LONG_CALL PlayerHealthSave_GetHealingSpawn(SaveData *saveData)
{
    struct SAVE_MISC_DATA *saveMiscData;

    if (saveData == NULL) {
        return PLAYER_HEALTH_MOM_SPAWN;
    }
    saveMiscData = Sav2_Misc_get(saveData);
    PlayerHealthSave_EnsureRecord(saveData, saveMiscData);
    return saveMiscData->playerHealthState[1]
        | (saveMiscData->playerHealthState[2] << 8);
}

void LONG_CALL PlayerHealthSave_SetHealingSpawn(SaveData *saveData, u16 spawn)
{
    struct SAVE_MISC_DATA *saveMiscData;

    if (saveData == NULL || !PlayerHealthSave_IsValidSpawn(spawn)) {
        return;
    }
    saveMiscData = Sav2_Misc_get(saveData);
    PlayerHealthSave_EnsureRecord(saveData, saveMiscData);
    saveMiscData->playerHealthState[1] = (u8)spawn;
    saveMiscData->playerHealthState[2] = (u8)(spawn >> 8);
}
