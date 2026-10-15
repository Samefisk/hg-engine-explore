#include "../include/player_health_recovery.h"

#include "../include/player_health.h"
#include "../include/pokemon.h"
#include "../include/save.h"
#include "../include/script.h"
#include "../include/task.h"

/* 0x401F is unused by the stock and project map scripts. The script writes it
 * only after HealParty succeeds, so the field service cannot heal early. */
#define PLAYER_HEALTH_HEAL_EVENT_VAR 0x401F
#define PLAYER_HEALTH_HEAL_EVENT_CENTER 1
#define PLAYER_HEALTH_HEAL_EVENT_HOME 2
#define PLAYER_HEALTH_MOM_SPAWN 1

/* SAVE_LOCAL_FIELD_DATA is block 5. In the matching HeartGold source,
 * LocalFieldData::lastSpawn follows five 20-byte Locations and two u16s.
 * The stock blackout task reads that halfword during its init and later uses
 * it again to choose the Mom or Center arrival script. */
#define PLAYER_HEALTH_LOCAL_FIELD_BLOCK 5
#define PLAYER_HEALTH_BLACKOUT_SPAWN_OFFSET 0x68

/* Verified against build/arm9.bin: ScrCmd_OverworldWhiteOut (script opcode
 * 279) calls CallTask_Blackout at 0x0205297C. Its literal task argument is
 * 0x02052859 (Thumb Task_Blackout), matching reference src/blackout.c. */
#define PLAYER_HEALTH_STOCK_BLACKOUT_TASK ((TaskFunc)0x02052859)
/* Stock overlay 1 FieldDrawMapName_Reset. The ordinary field input path calls
 * it before starting a transition; this direct HP task has no input event. */
#define PLAYER_HEALTH_STOCK_MAP_NAME_RESET \
    ((void (*)(void *))0x021EFACD)

static FieldSystem *sBlackoutFieldSystem
    __attribute__((section(".player_health_state"))) = NULL;
static u8 sBlackoutFailed
    __attribute__((section(".player_health_state"))) = 0;
/* FieldSystem_CreateTask is the stock root-task entry point in rom.ld. */
extern TaskManager *LONG_CALL FieldSystem_CreateTask(
    FieldSystem *fieldSystem, TaskFunc taskFunc, void *env);
extern void LONG_CALL CallTask_LeaveOverworld(TaskManager *taskman);

static u16 *PlayerHealthRecovery_StockSpawn(FieldSystem *fieldSystem)
{
    u8 *localFieldData;

    localFieldData = SaveArray_Get(fieldSystem->savedata,
        PLAYER_HEALTH_LOCAL_FIELD_BLOCK);
    if (localFieldData == NULL) {
        return NULL;
    }
    return (u16 *)(localFieldData + PLAYER_HEALTH_BLACKOUT_SPAWN_OFFSET);
}

void PlayerHealthRecovery_ServiceHealing(FieldSystem *fieldSystem)
{
    u16 event;
    u16 *stockSpawn;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL
        || fieldSystem == sBlackoutFieldSystem) {
        return;
    }

    event = VarGet(fieldSystem, PLAYER_HEALTH_HEAL_EVENT_VAR);
    if (event != PLAYER_HEALTH_HEAL_EVENT_CENTER
        && event != PLAYER_HEALTH_HEAL_EVENT_HOME) {
        return;
    }
    VarSet(fieldSystem, PLAYER_HEALTH_HEAL_EVENT_VAR, 0);

    if (event == PLAYER_HEALTH_HEAL_EVENT_HOME) {
        PlayerHealthSave_SetHealingSpawn(fieldSystem->savedata,
            PLAYER_HEALTH_MOM_SPAWN);
    } else {
        stockSpawn = PlayerHealthRecovery_StockSpawn(fieldSystem);
        if (stockSpawn != NULL) {
            PlayerHealthSave_SetHealingSpawn(fieldSystem->savedata, *stockSpawn);
        }
    }
    PlayerHealthField_Restore(fieldSystem);
}

static BOOL PlayerHealthRecovery_StockBlackoutTask(TaskManager *taskman)
{
    FieldSystem *fieldSystem = taskman->fieldSystem;
    u16 *stockSpawn;
    u16 previousSpawn;
    BOOL complete;

    if (fieldSystem == NULL || fieldSystem != sBlackoutFieldSystem
        || fieldSystem->savedata == NULL) {
        sBlackoutFailed = TRUE;
        return TRUE;
    }
    stockSpawn = PlayerHealthRecovery_StockSpawn(fieldSystem);
    if (stockSpawn == NULL) {
        sBlackoutFailed = TRUE;
        return TRUE;
    }

    /* Both stock destination reads happen inside Task_Blackout calls. Keep
     * its normal saved checkpoint intact across every wait and child task. */
    previousSpawn = *stockSpawn;
    *stockSpawn = PlayerHealthSave_GetHealingSpawn(fieldSystem->savedata);
    complete = PLAYER_HEALTH_STOCK_BLACKOUT_TASK(taskman);
    *stockSpawn = previousSpawn;
    return complete;
}

static BOOL PlayerHealthRecovery_BlackoutTask(TaskManager *taskman)
{
    FieldSystem *fieldSystem = taskman->fieldSystem;

    if (taskman->state == 0) {
        void *fieldWork = *(void **)((u8 *)fieldSystem + 4);

        if (fieldWork != NULL) {
            void *mapName = *(void **)((u8 *)fieldWork + 8);

            if (mapName != NULL) {
                PLAYER_HEALTH_STOCK_MAP_NAME_RESET(mapName);
            }
        }
        taskman->state = 1;
        /* Stock Task_Blackout queues its warp only after field teardown.
         * Vanilla's white-out script leaves the field before calling it. */
        CallTask_LeaveOverworld(taskman);
        return FALSE;
    }
    if (taskman->state == 1) {
        taskman->state = 2;
        TaskManager_Call(taskman,
            PlayerHealthRecovery_StockBlackoutTask, NULL);
        return FALSE;
    }

    /* Stock blackout and its arrival script have finished. */
    if (!sBlackoutFailed && fieldSystem == sBlackoutFieldSystem) {
        PlayerHealthField_Restore(fieldSystem);
    }
    sBlackoutFieldSystem = NULL;
    return TRUE;
}

void PlayerHealthRecovery_SessionReset(void)
{
    sBlackoutFieldSystem = NULL;
    sBlackoutFailed = FALSE;
}

BOOL PlayerHealthRecovery_BeginBlackout(FieldSystem *fieldSystem)
{
    u16 *stockSpawn;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL
        || fieldSystem->taskman != NULL || sBlackoutFieldSystem != NULL
        || !PlayerHealthField_RecoveryPending(fieldSystem)) {
        return FALSE;
    }

    stockSpawn = PlayerHealthRecovery_StockSpawn(fieldSystem);
    if (stockSpawn == NULL) {
        return FALSE;
    }
    sBlackoutFailed = FALSE;
    sBlackoutFieldSystem = fieldSystem;
    if (FieldSystem_CreateTask(fieldSystem,
            PlayerHealthRecovery_BlackoutTask, NULL) == NULL) {
        sBlackoutFieldSystem = NULL;
        return FALSE;
    }
    return TRUE;
}
