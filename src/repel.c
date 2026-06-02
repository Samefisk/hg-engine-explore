#include "../include/repel.h"
#include "../include/item.h"
#include "../include/constants/item.h"
#include "../include/bag.h"
#include "../include/constants/file.h"
#include "../include/config.h"
#include "../include/overworld_wild_spawns.h"


void Repel_SetCurrentType();

#ifdef IMPLEMENT_REUSABLE_REPELS
u16 ALIGN4 CurrentRepelType = 0;

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
static BOOL SoundEffectTest_TryStart(FieldSystem *fieldSystem)
{
    const u16 buttons = PAD_Read();
    const u16 soundTestButtons = PAD_BUTTON_SELECT | PAD_BUTTON_R;

    if ((buttons & soundTestButtons) != soundTestButtons) {
        return FALSE;
    }

    EventSet_Script(fieldSystem, OVERWORLD_WILD_SPAWNS_SOUND_TEST_SCRIPT, NULL);
    return TRUE;
}
#endif

bool32 PlayerStepEvent_RepelCounterDecrement(SaveData *saveData, FieldSystem *fieldSystem) {
#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS
    if (SoundEffectTest_TryStart(fieldSystem)) {
        return TRUE;
    }

    if (OverworldWildSpawns_OnPlayerStep(fieldSystem)) {
        return TRUE;
    }
#endif

    void *roamerSaveData = EncDataSave_GetSaveDataPtr(saveData);
    u8* repel_addr = SaveData_GetRepelPtr(roamerSaveData);

    if (*repel_addr != 0) {
        (*repel_addr)--;

        if (*repel_addr == 0) {
            BAG_DATA *bag = Sav2_Bag_get(saveData);
            u16 currentRepel = Repel_GetMostRecent();
            if (Bag_HasItem(bag, currentRepel, 1, HEAPID_WORLD)) {
                EventSet_Script(fieldSystem, 2072, NULL);
            } else {
                EventSet_Script(fieldSystem, 2022, NULL);
            }

            return TRUE;
        }
    }

    return FALSE;
}

u16 Repel_GetMostRecent() {
    Repel_SetCurrentType();
    return CurrentRepelType;
}

BOOL Repel_Use(u16 item_id, u32 heap_id) {
    SaveData *saveData = SaveBlock2_get();
    void *roamerSaveData = EncDataSave_GetSaveDataPtr(saveData);
    u8* repel_addr = SaveData_GetRepelPtr(roamerSaveData);

    BAG_DATA *bag = Sav2_Bag_get(saveData);

    item_id = Repel_GetMostRecent();

    if (Bag_TakeItem(bag, item_id, 1, heap_id)) {
        *repel_addr = Repel_GetSteps(item_id, heap_id);
        return TRUE;
    }

    return FALSE;
}

u8 Repel_GetSteps(u16 item_id, u32 heap_id) {
    return GetItemData(item_id, ITEM_PARAM_HOLD_EFFECT_PARAM, heap_id);
}
#endif

void Repel_SetCurrentType() {
#ifdef IMPLEMENT_REUSABLE_REPELS
    u16 item_id = 0;
    BAG_DATA *bag = Sav2_Bag_get(SaveBlock2_get());
    if (Bag_HasItem(bag, ITEM_MAX_REPEL, 1, HEAPID_MAIN_HEAP))
        item_id = ITEM_MAX_REPEL;
    else if (Bag_HasItem(bag, ITEM_SUPER_REPEL, 1, HEAPID_MAIN_HEAP))
        item_id = ITEM_SUPER_REPEL;
    else
        item_id = ITEM_REPEL;

    CurrentRepelType = item_id;
#endif
}
