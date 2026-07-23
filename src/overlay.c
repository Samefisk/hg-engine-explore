#include "../include/types.h"
#include "../include/debug.h"
#include "../include/map_teleport.h"
#include "../include/overlay.h"
#include "../include/overworld_follower_selector.h"
#include "../include/overworld_wild_behavior_data.h"
#include "../include/overworld_wild_spawns_internal.h"
#include "../include/save.h"
#include "../include/constants/file.h"


struct LinkedOverlayList gLinkedOverlayList[] =
{
    {OVERLAY_BATTLE, OVERLAY_BATTLE_EXTENSION},
    {OVERLAY_FIELD, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION,
        OVERLAY_OVERWORLD_FOLLOWER_SELECTOR},
    {OVERLAY_HALL_OF_FAME, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_HALL_OF_FAME_PC, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_POKEATHLON, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_POKEWALKER, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_POKEDEX, OVERLAY_POKEDEX_EXTENSION},
};

/*
 * Tail-call overlay 131's poll(NULL) teardown callback.  The naked form keeps
 * the failure contract inside overlay 129's extremely small remaining budget:
 * the callback returns directly to this function's caller in r0.
 */
BOOL __attribute__((naked))
OverworldFieldService_ShutdownTransientServices(void)
{
    __asm__(
        "ldr r3, =0x023C8000\n"
        "ldr r2, [r3]\n"
        "ldr r1, =0x3146574F\n"
        "cmp r2, r1\n"
        "bne 1f\n"
        "ldr r3, [r3, #8]\n"
        "cmp r3, #0\n"
        "beq 1f\n"
        "mov r0, #0\n"
        "bx r3\n"
        "1:\n"
        "mov r0, #1\n"
        "bx lr\n");
}

static BOOL IsOverworldFieldOverlay(u32 ovyId)
{
    return ovyId == OVERLAY_GETMONEVOLUTION_SPECIFIC
        || ovyId >= OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION;
}

static BOOL ResetOverworldFieldServiceState(void)
{
    if (!OverworldFieldService_ShutdownTransientServices()) {
        return FALSE;
    }
    *(u32 *)OVERWORLD_FIELD_SERVICE_ENTRY_ADDR = 0;
    return TRUE;
}

u32 LONG_CALL UnloadOverworldWildBehaviorOverlay(void)
{
    const OverworldWildBehaviorOverlayEntry *entry =
        OVERWORLD_WILD_BEHAVIOR_OVERLAY_ENTRY;
    u32 result;

    if (entry->magic != OVERWORLD_WILD_BEHAVIOR_OVERLAY_MAGIC
        || !OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE()) {
        return FALSE;
    }
    OVERWORLD_WILD_BEHAVIOR_OVERLAY_CLEANUP();
    result = FS_UnloadOverlay(0, OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA);
    if (result) {
        *(u32 *)OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR = 0;
    }
    return result;
}

BOOL LONG_CALL UnloadOverworldWildOverlays(void)
{
    /*
     * Overlay 152 is untracked by the SDK table, so tear it down through the
     * field-service callback before releasing its tracked overlay 149 owner.
     * A later 149 load links 152 back in for the resumed field session.
     */
    UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
    /* A successful 149 cleanup owns and unloads 150/151 atomically. */
    return !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
}

static BOOL UnloadColdOverworldWildOverlaysFor(u32 ovyId)
{
    if (IsOverworldFieldOverlay(ovyId)) {
        return TRUE;
    }

    return UnloadOverworldWildOverlays();
}

#ifdef DEBUG_PRINT_OVERLAY_LOADS
inline static void PrintLoadedOverlays(u32 ovyId)
{
    u32 overlayRegion;
    PMiLoadedOverlay *loadedOverlays;
    overlayRegion = GetOverlayLoadDestination(ovyId);
    loadedOverlays = GetLoadedOverlaysInRegion(overlayRegion);
    debug_printf("    Loaded overlays: ");
    for (int i = 0; i < MAX_ACTIVE_OVERLAYS; i++)
    {
        if (loadedOverlays[i].active == TRUE)
        {
            debug_printf(i == 0 ? "%04d" : ", %04d", loadedOverlays[i].id);
        }
    }
    debug_printf("\n\0");
}
#endif


void LONG_CALL UnloadOverlayByID(u32 ovyId) {
    u32 i;
    PMiLoadedOverlay *table;

unloadSecond:
    table = GetLoadedOverlaysInRegion(GetOverlayLoadDestination(ovyId));
    for (i = 0; i < MAX_ACTIVE_OVERLAYS; i++) {
        if (table[i].active == TRUE && table[i].id == ovyId) {
            if (ovyId == OVERLAY_FIELD_EXTENSION) {
                if (!ResetOverworldFieldServiceState()) {
                    return;
                }
            }
            if (ovyId == OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION) {
                if (!OverworldFieldService_ShutdownTransientServices()
                    || !OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->cleanupResidentData()) {
                    /* Teardown still owns 149/150/151; retry before overlap. */
                    return;
                }
            }
            FreeOverlayAllocation(&table[i]);
            break;
        }
    }

#ifdef DEBUG_PRINT_OVERLAY_LOADS
    debug_printf("Freed overlay %d.\n", ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS

    for (i = 0; i < NELEMS(gLinkedOverlayList); i++)
    {
        if (gLinkedOverlayList[i].first_id == ovyId)
        {
            ovyId = gLinkedOverlayList[i].ext_id;
            goto unloadSecond;
        }
    }

    if (ovyId == OVERLAY_BATTLE_EXTENSION) {
#ifdef DEBUG_PRINT_OVERLAY_LOADS
        debug_printf("Cleaning up overlays linked to overlay %d... ", ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS
        UnloadOverlayByID(OVERLAY_BATTLECONTROLLER_BEFOREMOVE);
        UnloadOverlayByID(OVERLAY_SERVERBEFOREACT);
        UnloadOverlayByID(OVERLAY_BATTLECONTROLLER_MOVEEND);
    }
}


u32 LONG_CALL HandleLoadOverlay(u32 ovyId, u32 loadType) {
    u32 result;
    u32 dmaBak = FS_DMA_NOT_USE;
    u32 overlayRegion;
    PMiLoadedOverlay *loadedOverlays;
    u32 i;
#ifdef DEBUG_PRINT_OVERLAY_LOADS
    u32 countActive = 0;
#endif // DEBUG_PRINT_OVERLAY_LOADS

loadExtension:
    if (!UnloadColdOverworldWildOverlaysFor(ovyId)) {
        return FALSE;
    }

    if (ovyId == OVERLAY_BATTLE_EXTENSION) {
#ifdef DEBUG_PRINT_OVERLAY_LOADS
        debug_printf("Overlay %d has priority over field overlays--unloading them...\n", ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS
        UnloadOverlayByID(OVERLAY_FIELD_EXTENSION);
    }

    if (!CanOverlayBeLoaded(ovyId)) {
        if (IsOverlayLoaded(ovyId)) {
            result = FALSE;
            goto loadLinkedExtension;
        }
#ifdef DEBUG_PRINT_OVERLAY_LOADS
        debug_printf("ERROR: Can't load in overlay_%04d.bin.\n", ovyId);
        PrintLoadedOverlays(ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS
        return FALSE;
    }

    /*
     * The field session already occupies every SDK bookkeeping slot.  Keep
     * the selector tied to overlay 149's linked lifetime, but load it
     * directly so it does not displace the wild-spawn helper overlay.  The
     * overlap check above remains mandatory: later overlapping loads cannot
     * see this untracked overlay, so every cold-overlay transition first
     * invokes the field-service shutdown above and directly unloads it.
     */
    if (ovyId == OVERLAY_OVERWORLD_FOLLOWER_SELECTOR) {
        result = LoadOverlayNoInitAsync(0, ovyId);
        if (result) {
            OverworldFollowerSelector_SetDirectLoaded();
        }
        return result;
    }

    overlayRegion = GetOverlayLoadDestination(ovyId);
    loadedOverlays = GetLoadedOverlaysInRegion(overlayRegion);

    for (i = 0; i < MAX_ACTIVE_OVERLAYS; i++) {
        if (loadedOverlays[i].active == FALSE) {
            PMiLoadedOverlay *ovy = &loadedOverlays[i];
            ovy->active = TRUE;
            ovy->id = ovyId;
            break;
        }
    }

#ifdef DEBUG_PRINT_OVERLAY_LOADS
    {
        for (int j = 0; j < MAX_ACTIVE_OVERLAYS; j++)
        {
            countActive += loadedOverlays[j].active == TRUE;
        }
    }
#endif // DEBUG_PRINT_OVERLAY_LOADS

    if (i >= MAX_ACTIVE_OVERLAYS) {
#ifdef DEBUG_PRINT_OVERLAY_LOADS
        debug_printf("ERROR: Too many overlays!  Active count: %d\n", countActive);
        PrintLoadedOverlays(ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS
        GF_ASSERT(0);
        return FALSE;
    }

    if (overlayRegion == 1 || overlayRegion == 2) {
        dmaBak = FS_SetDefaultDMA(FS_DMA_NOT_USE);
    }

    switch (loadType) {
    case 0:
        result = LoadOverlayNormal(0, ovyId);
        break;
    case 1:
        result = LoadOverlayNoInit(0, ovyId);
        break;
    case 2:
        result = LoadOverlayNoInitAsync(0, ovyId);
        break;
    default:
        GF_ASSERT(0);
        result = FALSE;
        break;
    }

    if (overlayRegion == 1 || overlayRegion == 2) {
        FS_SetDefaultDMA(dmaBak);
    }

    if (result == FALSE) {
        /* The slot reservation owns nothing when the SDK load fails. */
        loadedOverlays[i].active = FALSE;
        loadedOverlays[i].id = 0;
#ifdef DEBUG_PRINT_OVERLAY_LOADS
        debug_printf("Failed to load overlay_%04d.bin.\n", ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS
        GF_ASSERT(0);
        return FALSE;
    }

loadLinkedExtension:
    for (i = 0; i < NELEMS(gLinkedOverlayList); i++)
    {
        if (gLinkedOverlayList[i].first_id == ovyId)
        {
            if (result == FALSE
                && (gLinkedOverlayList[i].ext_id
                        == OVERLAY_OVERWORLD_FOLLOWER_SELECTOR
                    ? OverworldFollowerSelector_IsDirectLoaded()
                    : (BOOL)IsOverlayLoaded(gLinkedOverlayList[i].ext_id))) {
                    return FALSE;
            }
            ovyId = gLinkedOverlayList[i].ext_id;
            loadType = 2;
#ifdef DEBUG_PRINT_OVERLAY_LOADS
            debug_printf("Trying to load linked overlay_%04d.bin.\n", ovyId);
#endif // DEBUG_PRINT_OVERLAY_LOADS
            goto loadExtension;
        }
    }

    return result;
}


u32 LONG_CALL IsOverlayLoaded(u32 ovyId)
{
    PMiLoadedOverlay *table = GetLoadedOverlaysInRegion(GetOverlayLoadDestination(ovyId));
    PMiLoadedOverlay *end = table + MAX_ACTIVE_OVERLAYS;

    do {
        if (table->id == ovyId && table->active == TRUE) {
            return 1;
        }
        table++;
    } while (table < end);

    return 0;
}
