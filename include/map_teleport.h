#ifndef MAP_TELEPORT_H
#define MAP_TELEPORT_H

#include "types.h"

typedef struct FieldSystem FieldSystem;
typedef struct OverworldWildSpawnState OverworldWildSpawnState;

/*
 * Overlay 131 used to expose the custom debug map-teleport service here.
 * Keep the fixed address so resident code can reach field services without
 * adding a direct overlay relocation. This service does not replace or alter
 * the game's normal map-warp implementation.
 */
#define OVERWORLD_FIELD_SERVICE_ENTRY_ADDR 0x023C8000
/* The version is encoded in the magic so resident validation is one compare. */
#define OVERWORLD_FIELD_SERVICE_MAGIC 0x3146574F /* "OWF1" */

typedef enum OverworldFieldMapHeaderChangeResult {
    OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE = 0,
    OVERWORLD_FIELD_MAP_HEADER_CHANGE_PRESERVED,
    OVERWORLD_FIELD_MAP_HEADER_CHANGE_CLEARED,
} OverworldFieldMapHeaderChangeResult;

typedef OverworldFieldMapHeaderChangeResult (*OverworldFieldMapHeaderChangedFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 previousMapId,
    u16 currentMapId);
typedef BOOL (*OverworldFieldPollFrameFunc)(FieldSystem *fieldSystem);
typedef BOOL (*OverworldFieldTryGetEncounterDataIdForMapFunc)(
    u16 mapId,
    int *encounterDataId);

typedef struct OverworldFieldServiceEntry {
    u32 magic;
    OverworldFieldMapHeaderChangedFunc onMapHeaderChanged;
    OverworldFieldPollFrameFunc pollFrame;
    OverworldFieldTryGetEncounterDataIdForMapFunc tryGetEncounterDataIdForMap;
} OverworldFieldServiceEntry;

typedef char OverworldFieldServiceEntrySizeMustRemain16Bytes[
    sizeof(OverworldFieldServiceEntry) == 16 ? 1 : -1];

#define OVERWORLD_FIELD_SERVICE_ENTRY \
    ((const OverworldFieldServiceEntry *)OVERWORLD_FIELD_SERVICE_ENTRY_ADDR)

static inline const OverworldFieldServiceEntry *OverworldFieldService_GetEntry(void)
{
    const OverworldFieldServiceEntry *entry = OVERWORLD_FIELD_SERVICE_ENTRY;

    if (entry->magic != OVERWORLD_FIELD_SERVICE_MAGIC) {
        return NULL;
    }

    return entry;
}

static inline OverworldFieldMapHeaderChangeResult OverworldFieldService_OnMapHeaderChanged(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 previousMapId,
    u16 currentMapId)
{
    const OverworldFieldServiceEntry *entry = OverworldFieldService_GetEntry();

    if (entry == NULL || entry->onMapHeaderChanged == NULL) {
        return OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE;
    }

    return entry->onMapHeaderChanged(
        fieldSystem,
        state,
        previousMapId,
        currentMapId);
}

static inline void OverworldFieldService_PollFrame(FieldSystem *fieldSystem)
{
    const OverworldFieldServiceEntry *entry = OverworldFieldService_GetEntry();

    if (entry == NULL || entry->pollFrame == NULL) {
        return;
    }

    (void)entry->pollFrame(fieldSystem);
}

/* A NULL frame is reserved for transient field-service teardown. */
BOOL OverworldFieldService_ShutdownTransientServices(void);

static inline BOOL OverworldFieldService_TryGetEncounterDataIdForMap(
    u16 mapId,
    int *encounterDataId)
{
    const OverworldFieldServiceEntry *entry = OverworldFieldService_GetEntry();

    if (entry == NULL || entry->tryGetEncounterDataIdForMap == NULL) {
        return FALSE;
    }

    return entry->tryGetEncounterDataIdForMap(mapId, encounterDataId);
}

#endif // MAP_TELEPORT_H
