#include "../include/types.h"
#include "../include/debug.h"
#include "../include/map_teleport.h"
#include "../include/overlay.h"
#include "../include/overworld_wild_behavior_data.h"
#include "../include/overworld_wild_spawns_internal.h"
#include "../include/save.h"
#include "../include/constants/file.h"


struct LinkedOverlayList gLinkedOverlayList[] =
{
    {OVERLAY_BATTLE, OVERLAY_BATTLE_EXTENSION},
    {OVERLAY_FIELD, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_HALL_OF_FAME, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_HALL_OF_FAME_PC, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_POKEATHLON, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_POKEWALKER, OVERLAY_FIELD_EXTENSION},
    {OVERLAY_POKEDEX, OVERLAY_POKEDEX_EXTENSION},
};

// entirely clean up overlays if the first one is being unloaded
u8 gCleanupOverlayList[][4] =
{
    {OVERLAY_BATTLE_EXTENSION, OVERLAY_BATTLECONTROLLER_BEFOREMOVE, OVERLAY_SERVERBEFOREACT, OVERLAY_BATTLECONTROLLER_MOVEEND},
};

static BOOL IsOverworldWildOverlay(u32 ovyId)
{
    return ovyId == OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION
        || ovyId == OVERLAY_OVERWORLD_WILD_HELPER;
}

static void ResetMapTeleportOverlayState(void)
{
    *(u32 *)MAP_TELEPORT_OVERLAY_ENTRY_ADDR = 0;
    gMapTeleportTransitionState.state = 0;
    gMapTeleportTransitionState.frame = 0;
}

u32 LONG_CALL UnloadOverworldWildBehaviorOverlay(void)
{
    const OverworldWildBehaviorOverlayEntry *entry =
        OVERWORLD_WILD_BEHAVIOR_OVERLAY_ENTRY;
    u32 result;

    if (entry->magic != OVERWORLD_WILD_BEHAVIOR_OVERLAY_MAGIC
        || entry->version != OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION
        || entry->size != sizeof(*entry)
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

void LONG_CALL UnloadOverworldWildOverlays(void)
{
    UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION);
}

static void UnloadColdOverworldWildOverlaysFor(u32 ovyId)
{
    if (IsOverworldWildOverlay(ovyId)) {
        return;
    }

    UnloadOverworldWildOverlays();
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
    u32 i, j = 0, k = 1;
    BOOL cleanupMode = FALSE;
    PMiLoadedOverlay *table;

unloadSecond:
    table = GetLoadedOverlaysInRegion(GetOverlayLoadDestination(ovyId));
    for (i = 0; i < MAX_ACTIVE_OVERLAYS; i++) {
        if (table[i].active == TRUE && table[i].id == ovyId) {
            if (ovyId == OVERLAY_FIELD_EXTENSION) {
                ResetMapTeleportOverlayState();
            }
            if (ovyId == OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION
                && OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->cleanupResidentData != NULL) {
                if (!OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->cleanupResidentData()) {
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

    // alright we want to clear overlays
    for (; j < NELEMS(gCleanupOverlayList); j++) {
        if (k >= NELEMS(gCleanupOverlayList[0])) {
            cleanupMode = FALSE;
            k = 1;
            continue; // increases j
        }
        if ((gCleanupOverlayList[j][0] == ovyId) || cleanupMode) {
            if (gCleanupOverlayList[j][k]) {
                ovyId = gCleanupOverlayList[j][k++];
                cleanupMode = TRUE;
#ifdef DEBUG_PRINT_OVERLAY_LOADS
                debug_printf("Cleaning up overlay %d linked to overlay %d... ", ovyId, gCleanupOverlayList[j][0]);
#endif // DEBUG_PRINT_OVERLAY_LOADS
                goto unloadSecond;
            } else {
                k = 1;
                continue; // increases j
            }
        }
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
    UnloadColdOverworldWildOverlaysFor(ovyId);

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
                && IsOverlayLoaded(gLinkedOverlayList[i].ext_id)) {
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

    for (int i = 0; i < MAX_ACTIVE_OVERLAYS; i++) {
        if (table[i].active == TRUE && table[i].id == ovyId) {
            return 1;
        }
    }

    return 0;
}
