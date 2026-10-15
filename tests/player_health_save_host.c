#include <string.h>

#include "../include/player_health_model.h"
#include "../include/save.h"

static u8 sLocalFieldData[0x80];

struct SAVE_MISC_DATA *Sav2_Misc_get(void *saveData)
{
    return saveData;
}

void *SaveArray_Get(SaveData *saveData, int id)
{
    (void)saveData;
    return id == 5 ? sLocalFieldData : NULL;
}

static int sFailures;

#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "line %d: %s\n", __LINE__, #value); sFailures++; \
} } while (0)

static void FillRecord(struct SAVE_MISC_DATA *record, u8 hp, u16 spawn)
{
    memset(record, 0xA5, sizeof(*record));
    record->playerHealthSignature[0] = 'P';
    record->playerHealthSignature[1] = 'H';
    record->playerHealthSignature[2] = 1;
    record->playerHealthState[0] = hp;
    record->playerHealthState[1] = (u8)spawn;
    record->playerHealthState[2] = (u8)(spawn >> 8);
}

static void CheckUnrelatedBytes(const struct SAVE_MISC_DATA *before,
    const struct SAVE_MISC_DATA *after)
{
    const u8 *left = (const u8 *)before;
    const u8 *right = (const u8 *)after;
    unsigned int i;
    for (i = 0; i < sizeof(*before); i++) {
        if ((i >= 0x2D5 && i < 0x2D8) || (i >= 0x2DD && i < 0x2E0)) {
            continue;
        }
        CHECK(left[i] == right[i]);
    }
}

int main(void)
{
    struct SAVE_MISC_DATA record, before, loaded;
    SaveData *saveData = (SaveData *)&record;
    PlayerHealthState health;
    unsigned int hp, marker;
    const u16 badSpawns[] = {0, 31, 255, 256, 0xFFFF};
    unsigned int i;

    CHECK(__builtin_offsetof(struct SAVE_MISC_DATA, playerHealthSignature) == 0x2D5);
    CHECK(__builtin_offsetof(struct SAVE_MISC_DATA, playerHealthState) == 0x2DD);
    memset(sLocalFieldData, 0, sizeof(sLocalFieldData));
    sLocalFieldData[0x68] = 23;

    /* Every possible serialized HP byte: valid zero is never legacy/full HP. */
    for (hp = 0; hp <= 255; hp++) {
        FillRecord(&record, (u8)hp, 23);
        before = record;
        CHECK(PlayerHealthSave_GetHP(saveData) == (hp <= 100 ? hp : 100));
        CHECK(PlayerHealthSave_GetHealingSpawn(saveData) == 23);
        CheckUnrelatedBytes(&before, &record);
        loaded = record;
        PlayerHealth_Init(&health, PlayerHealthSave_GetHP((SaveData *)&loaded));
        CHECK(health.hp == (hp <= 100 ? hp : 100));
        CHECK(health.recoveryPending == (hp == 0));
        CHECK(PlayerHealth_BeginFrame(&health, 1, TRUE)
            == (hp == 0 ? PLAYER_HEALTH_RECOVERING : PLAYER_HEALTH_OK));
        if (hp == 0) {
            CHECK(!health.frameActive);
            CHECK(PlayerHealth_TryHit(&health, 33)
                == PLAYER_HEALTH_RECOVERING);
            CHECK(PlayerHealth_EndFrame(&health, FALSE) != PLAYER_HEALTH_OK);
            CHECK(health.hp == 0 && health.restFrames == 0);
            CHECK(PlayerHealthSave_GetHP((SaveData *)&loaded) == 0);
        }
    }

    /* Corrupt each marker independently; do not accept a partial signature. */
    for (marker = 0; marker < 3; marker++) {
        FillRecord(&record, 0, 3);
        record.playerHealthSignature[marker] = 0;
        before = record;
        CHECK(PlayerHealthSave_GetHP(saveData) == 100);
        CHECK(PlayerHealthSave_GetHealingSpawn(saveData) == 23);
        CheckUnrelatedBytes(&before, &record);
    }
    FillRecord(&record, 0, 3);
    memset(record.playerHealthSignature, 0, 3);
    before = record;
    CHECK(PlayerHealthSave_GetHP(saveData) == 100);
    CHECK(PlayerHealthSave_GetHealingSpawn(saveData) == 23);
    CheckUnrelatedBytes(&before, &record);

    for (i = 0; i < sizeof(badSpawns) / sizeof(badSpawns[0]); i++) {
        /* Bad checkpoint repairs must not turn a zero-HP load into healing. */
        FillRecord(&record, 0, badSpawns[i]);
        before = record;
        CHECK(PlayerHealthSave_GetHealingSpawn(saveData) == 1);
        CHECK(PlayerHealthSave_GetHP(saveData) == 0);
        CheckUnrelatedBytes(&before, &record);
        /* Migration with an invalid stock checkpoint uses home. */
        record.playerHealthSignature[2] = 0;
        sLocalFieldData[0x68] = (u8)badSpawns[i];
        sLocalFieldData[0x69] = (u8)(badSpawns[i] >> 8);
        CHECK(PlayerHealthSave_GetHP(saveData) == 100);
        CHECK(PlayerHealthSave_GetHealingSpawn(saveData) == 1);
    }

    FillRecord(&record, 67, 30);
    before = record;
    PlayerHealthSave_SetHealingSpawn(saveData, 0);
    PlayerHealthSave_SetHealingSpawn(saveData, 31);
    CHECK(memcmp(&before, &record, sizeof(record)) == 0);
    PlayerHealthSave_SetHP(saveData, 0);
    CHECK(PlayerHealthSave_GetHP(saveData) == 0);
    CHECK(PlayerHealthSave_GetHealingSpawn(saveData) == 30);
    PlayerHealthSave_SetHP(saveData, 255);
    CHECK(PlayerHealthSave_GetHP(saveData) == 100);
    CheckUnrelatedBytes(&before, &record);
    CHECK(PlayerHealthSave_GetHP(NULL) == 100);
    CHECK(PlayerHealthSave_GetHealingSpawn(NULL) == 1);
    PlayerHealthSave_SetHP(NULL, 0);
    PlayerHealthSave_SetHealingSpawn(NULL, 3);
    return sFailures != 0;
}
