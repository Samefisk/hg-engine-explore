#ifndef OVERWORLD_WILD_HELPER_H
#define OVERWORLD_WILD_HELPER_H

#include "types.h"
#include "overworld_wild_behavior_data.h"
#include "overworld_wild_spawns_internal.h"

#define OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR 0x023C4000
#define OVERWORLD_WILD_HELPER_OVERLAY_MAGIC 0x4F574831
#define OVERWORLD_WILD_HELPER_OVERLAY_VERSION 11

#define OW_WILD_HELPER_DIRECTION_NONE 0xFF
#define OW_WILD_HELPER_DIRECTION_UP 0
#define OW_WILD_HELPER_DIRECTION_DOWN 1
#define OW_WILD_HELPER_DIRECTION_LEFT 2
#define OW_WILD_HELPER_DIRECTION_RIGHT 3

#define OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS 8
#define OW_WILD_HELPER_HOP_PLAN_MAX_HOPS 5
#define OW_WILD_HELPER_HOP_PLAN_NODE_COUNT 64

#define OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT 0x01
#define OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED 0x02
#define OW_WILD_HELPER_HOP_RESULT_FLAG_FALLBACK 0x04

typedef struct OverworldWildRolledEncounter {
    u32 personality;
    u16 species;
    u8 form;
    u8 level;
} OverworldWildRolledEncounter;

typedef struct OverworldWildSpawnPosition {
    int startX;
    int startY;
    u8 headbuttTreeType;
} OverworldWildSpawnPosition;

typedef struct OverworldWildSpawnStartup {
    s16 targetX;
    s16 targetY;
    s16 startX;
    s16 startY;
    u8 locomotion;
    u8 hopDirection;
} OverworldWildSpawnStartup;

typedef struct OverworldWildPreparedSpawn {
    OverworldWildSpawnPosition position;
    OverworldWildRolledEncounter encounter;
    OverworldWildSpawnStartup startup;
    OverworldWildBehaviorProfile behaviorProfile;
    int savedShinySlot;
    u8 behaviorClass;
    u8 shiny;
    u8 shinyCounterEligible;
    u8 behaviorLimitKey;
} OverworldWildPreparedSpawn;

typedef struct OverworldWildHelperPlayerState {
    int playerX;
    int playerY;
    int objectX;
    int objectY;
    u8 facing;
    u8 hasObject;
    u8 reserved[2];
} OverworldWildHelperPlayerState;

typedef BOOL (*OverworldWildHelperGetPlayerStateFunc)(
    void *context,
    OverworldWildHelperPlayerState *playerState);
typedef BOOL (*OverworldWildHelperTryGetSpawnTerrainFunc)(
    void *context,
    int x,
    int y,
    OverworldWildSpawnTerrain *terrain);
typedef BOOL (*OverworldWildHelperTilePredicateFunc)(
    void *context,
    int x,
    int y);
typedef BOOL (*OverworldWildHelperNearActiveSpawnFunc)(
    void *context,
    int x,
    int y,
    int radius);
typedef BOOL (*OverworldWildHelperGetMapIdFunc)(
    void *context,
    u16 *mapId);
typedef BOOL (*OverworldWildHelperArchiveLoadFunc)(
    void *context,
    int arcId,
    int datId,
    int offset,
    void *dest,
    int size);
typedef BOOL (*OverworldWildHelperTryGetEncounterDataIdFunc)(
    void *context,
    int *encounterDataId);
typedef int (*OverworldWildHelperFindSavedShinyFunc)(
    void *context,
    OverworldWildSpawnTerrain terrain);
typedef void (*OverworldWildHelperLoadSavedShinyFunc)(
    void *context,
    int savedShinySlot,
    OverworldWildRolledEncounter *encounter);
typedef struct OverworldWildHelperSpawnCallbacks {
    OverworldWildHelperGetPlayerStateFunc getPlayerState;
    OverworldWildHelperTryGetSpawnTerrainFunc tryGetSpawnTerrain;
    OverworldWildHelperTilePredicateFunc isTileOccupied;
    OverworldWildHelperNearActiveSpawnFunc isNearActiveSpawn;
    OverworldWildHelperGetMapIdFunc getMapId;
    OverworldWildHelperArchiveLoadFunc loadArchiveData;
    OverworldWildHelperTryGetEncounterDataIdFunc tryGetEncounterDataId;
    OverworldWildHelperFindSavedShinyFunc findSavedShiny;
    OverworldWildHelperLoadSavedShinyFunc loadSavedShiny;
} OverworldWildHelperSpawnCallbacks;

typedef BOOL (*OverworldWildHelperTryPrepareSpawnFunc)(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    int slot,
    BOOL shinyAlreadySpawned,
    u16 shinyOddsDenominator,
    OverworldWildPreparedSpawn *prepared);

typedef BOOL (*OverworldWildHelperTryPrepareEncounterSpawnFunc)(
    const OverworldWildHelperSpawnCallbacks *callbacks,
    void *context,
    OverworldWildSpawnTerrain terrain,
    int slot,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    BOOL rollPersonality,
    OverworldWildPreparedSpawn *prepared);

typedef struct OverworldWildHelperHopConfig {
    int objectX;
    int objectY;
    int targetX;
    int targetY;
    u8 minDistance;
    u8 maxDistance;
    u8 allowNonCardinal;
    u8 stopOneHopAway;
    u8 directionCount;
    u8 directions[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
} OverworldWildHelperHopConfig;

typedef struct OverworldWildHelperHopResult {
    int landingX;
    int landingY;
    int finalTargetX;
    int finalTargetY;
    u8 direction;
    u8 distance;
    u8 flags;
    u8 reserved;
} OverworldWildHelperHopResult;

typedef BOOL (*OverworldWildHelperHopTileValidator)(
    int landingX,
    int landingY,
    int targetX,
    int targetY,
    void *context);

typedef BOOL (*OverworldWildHelperPickHopFunc)(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result);

typedef LocalMapObject *(*OverworldWildHelperRecreatePresentationFunc)(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    int x,
    int y);
typedef void (*OverworldWildHelperResetSlotFunc)(
    OverworldWildSpawnState *state,
    int slot,
    BOOL deleteAuxiliaryObjects);
typedef BOOL (*OverworldWildHelperReconcilePresentationsFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    OverworldWildHelperRecreatePresentationFunc recreatePresentation);
typedef BOOL (*OverworldWildHelperIsPresentationContextCurrentFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state);
typedef void (*OverworldWildHelperNormalizeThrowPresentationFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot);
typedef void (*OverworldWildHelperSyncCarriedThrowTargetFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    int carrierSlot,
    int targetSlot);
typedef BOOL (*OverworldWildHelperRemoveEncounterFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    u16 expectedGeneration,
    OverworldWildDespawnReason reason,
    u8 distance,
    OverworldWildHelperResetSlotFunc resetSlot);
typedef void (*OverworldWildHelperDespawnFarEncountersFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    u16 movementProtectedMask,
    OverworldWildHelperResetSlotFunc resetSlot);
typedef void (*OverworldWildHelperRecordDespawnEventFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    int slot,
    OverworldWildDespawnReason reason,
    OverworldWildDespawnAction action,
    u8 distance);
typedef u8 (*OverworldWildHelperClassifyBattleResultFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 battleResult);
typedef u8 (*OverworldWildHelperFinishBattleFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildPresentationState *presentation,
    OverworldWildDespawnTelemetry *telemetry,
    u16 battleResult,
    OverworldWildHelperResetSlotFunc resetSlot);
typedef LocalMapObject *(*OverworldWildHelperCreatePresentationObjectFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    int x,
    int y,
    u8 facing,
    u8 movementBehavior,
    u8 range);
typedef BOOL (*OverworldWildHelperValidateDeferredBattleFunc)(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    u16 encounterGeneration);

typedef struct OverworldWildHelperOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildHelperTryPrepareSpawnFunc tryPrepareSpawn;
    OverworldWildHelperTryPrepareEncounterSpawnFunc tryPrepareEncounterSpawn;
    OverworldWildHelperPickHopFunc pickRandomBehaviorHop;
    OverworldWildHelperPickHopFunc planBehaviorHopStep;
    OverworldWildHelperIsPresentationContextCurrentFunc isPresentationContextCurrent;
    OverworldWildHelperNormalizeThrowPresentationFunc normalizeThrowPresentation;
    OverworldWildHelperSyncCarriedThrowTargetFunc syncCarriedThrowTarget;
    OverworldWildHelperReconcilePresentationsFunc reconcilePresentations;
    OverworldWildHelperDespawnFarEncountersFunc despawnFarEncounters;
    OverworldWildHelperFinishBattleFunc finishBattle;
    OverworldWildHelperCreatePresentationObjectFunc createPresentationObject;
    OverworldWildHelperValidateDeferredBattleFunc validateDeferredBattle;
} OverworldWildHelperOverlayEntry;

#define OVERWORLD_WILD_HELPER_OVERLAY_ENTRY \
    ((const OverworldWildHelperOverlayEntry *)OVERWORLD_WILD_HELPER_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_HELPER_H
