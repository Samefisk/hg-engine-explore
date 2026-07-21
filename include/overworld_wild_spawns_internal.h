#ifndef OVERWORLD_WILD_SPAWNS_INTERNAL_H
#define OVERWORLD_WILD_SPAWNS_INTERNAL_H

#include "overworld_wild_spawns.h"
#include "constants/maps.h"

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR 0x023CD000

#define OW_WILD_GRASS_MAX_SPAWNS 3
#define OW_WILD_SURF_MAX_SPAWNS 3
#define OW_WILD_HEADBUTT_MAX_SPAWNS 2
#define OW_WILD_FISH_MAX_SPAWNS 2
#define OW_WILD_HEADBUTT_SLOT_START (OW_WILD_GRASS_MAX_SPAWNS + OW_WILD_SURF_MAX_SPAWNS)
#define OW_WILD_FISH_SLOT_START (OW_WILD_HEADBUTT_SLOT_START + OW_WILD_HEADBUTT_MAX_SPAWNS)
#define OW_WILD_FOLLOWER_SLOT (OW_WILD_FISH_SLOT_START - 1)
#define OW_WILD_MAX_SPAWNS (OW_WILD_GRASS_MAX_SPAWNS + OW_WILD_SURF_MAX_SPAWNS + OW_WILD_HEADBUTT_MAX_SPAWNS + OW_WILD_FISH_MAX_SPAWNS)
#define OW_WILD_MAX_SAVED_SHINIES 2
#define OW_WILD_PREVIOUS_TILE_UNLOCKED 0
#define OW_WILD_PREVIOUS_TILE_LOCKED 1
#define OW_WILD_SAVED_SHINY_ACTIVE 0x80
#define OW_WILD_SAVED_SHINY_TERRAIN_MASK 0x7F
#define OW_WILD_SPECIES_MASK 0x7FF
#define OW_WILD_FORM_SHIFT 11
#define OW_WILD_OBJECT_ID_START 0xE0
#define OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID 0xF0
#define OW_WILD_DISTANCE_DESPAWN_SAMPLES 2
#define OW_WILD_DISTANCE_DESPAWN_TILES 16
#define OW_WILD_STAGED_HOP_MOVEMENT_LIST_WORDS 72
#define OW_WILD_FIELD_READY_DELAY_FRAMES 90
#define OW_WILD_FIELD_IDLE_REARM_PENDING 0x01
#define OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING 0x02
/* Reconciliation may identify one logical slot that is safe to quarantine. */
#define OW_WILD_RECONCILE_RETRY 0
#define OW_WILD_RECONCILE_COMPLETE 1
#define OW_WILD_RECONCILE_POISONED_SLOT_BASE 2

typedef enum OverworldWildDespawnReason {
    OW_WILD_DESPAWN_REASON_NONE = 0,
    OW_WILD_DESPAWN_REASON_BATTLE_DEFEATED,
    OW_WILD_DESPAWN_REASON_BATTLE_CAUGHT,
    OW_WILD_DESPAWN_REASON_DISTANCE,
} OverworldWildDespawnReason;

typedef enum OverworldWildDespawnAction {
    OW_WILD_DESPAWN_ACTION_NONE = 0,
    OW_WILD_DESPAWN_ACTION_DELETE_OBJECT,
    OW_WILD_DESPAWN_ACTION_CLEAR_LOGICAL_ONLY,
    OW_WILD_DESPAWN_ACTION_REBIND_OBJECT,
    OW_WILD_DESPAWN_ACTION_PRESENTATION_MISSING,
    OW_WILD_DESPAWN_ACTION_RECREATE_OBJECT,
    OW_WILD_DESPAWN_ACTION_DELETE_SUPPRESSED,
    OW_WILD_DESPAWN_ACTION_IDENTITY_CONFLICT,
} OverworldWildDespawnAction;

typedef enum OverworldWildBattleDisposition {
    OW_WILD_BATTLE_DISPOSITION_RETAIN = 0,
    OW_WILD_BATTLE_DISPOSITION_FLED,
    OW_WILD_BATTLE_DISPOSITION_DEFEATED,
    OW_WILD_BATTLE_DISPOSITION_CAUGHT,
} OverworldWildBattleDisposition;

typedef enum OverworldWildDespawnAuthorization {
    OW_WILD_DESPAWN_DENIED = 0,
    OW_WILD_DESPAWN_CLEAR_LOGICAL_ONLY,
    OW_WILD_DESPAWN_DELETE_VERIFIED_OBJECT,
} OverworldWildDespawnAuthorization;

typedef struct OverworldWildSpawn {
    LocalMapObject *object;
    u32 personality;
    u16 mapId;
    u16 species;
    u8 form;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 active;
    u8 objectId;
    u16 encounterGeneration;
} OverworldWildSpawn;

typedef char OverworldWildSpawnSizeMustRemain20Bytes[
    sizeof(OverworldWildSpawn) == 20 ? 1 : -1];

typedef struct OverworldWildDespawnRecord {
    u32 objectPtr;
    u32 objectFlags;
    u32 personality;
    u16 sequence;
    u16 mapId;
    u16 spawnMapId;
    u16 mapGeneration;
    u16 encounterGeneration;
    s16 objectX;
    s16 objectY;
    s16 playerX;
    s16 playerY;
    s16 objectId;
    u8 reason;
    u8 action;
    u8 slot;
    u8 distance;
    u8 contextFlags;
    u8 expectedObjectId;
} OverworldWildDespawnRecord;

#define OW_WILD_DESPAWN_RECORD_COUNT 8

typedef struct OverworldWildDespawnTelemetry {
    u32 magic;
    u16 sequence;
    u8 writeIndex;
    u8 unexpectedCount;
    u16 reasonCounts[4];
    OverworldWildDespawnRecord records[OW_WILD_DESPAWN_RECORD_COUNT];
} OverworldWildDespawnTelemetry;

typedef struct OverworldWildPresentationState {
    s16 lastKnownX[OW_WILD_MAX_SPAWNS];
    s16 lastKnownY[OW_WILD_MAX_SPAWNS];
    u8 farSamples[OW_WILD_MAX_SPAWNS];
    u16 managerRestoreMask;
} OverworldWildPresentationState;

typedef struct OverworldWildThrowState {
    u8 targets[OW_WILD_MAX_SPAWNS];
    u16 targetMask;
    u16 carrierMask;
} OverworldWildThrowState;

typedef struct OverworldWildSavedShiny {
    u16 mapId;
    u16 speciesAndForm;
    u8 level;
    u8 terrainAndActive;
} OverworldWildSavedShiny;

typedef struct OverworldWildSpawnState {
    OverworldWildSpawn spawns[OW_WILD_MAX_SPAWNS];
    OverworldWildSavedShiny savedShinies[OW_WILD_MAX_SAVED_SHINIES];
    int mapId;
    void *mapObjectMan;
    void *mapObjects;
    FieldSystem *movementFieldSystem;
    void *movementRuntimeState;
    u8 justSpawned;
    u8 spawnCooldown;
    u8 headbuttSpawnCooldown;
    u8 fishingSpawnCooldown;
    u8 ambientCryCooldown;
    u8 battleGraceSteps;
    u8 movementCooldowns[OW_WILD_MAX_SPAWNS];
    u16 movementInProgressMask;
    u8 movementBattleSettleFrames;
    u32 pendingPersonality;
    u16 pendingSpecies;
    u8 pendingLevel;
    u8 pendingShiny;
    u8 shinySpawned;
    u8 savedShiniesLoaded;
    s8 pendingSlot;
    s8 movementQueuedBattleSlot;
    u8 movementSpotStates[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteTimers[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteSteps[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteDirections[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteJumpsRemaining[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteEndStates[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteBubbleIds[OW_WILD_MAX_SPAWNS];
    u8 movementEmoteShowBubbleEachJump[OW_WILD_MAX_SPAWNS];
    u8 movementEmotePlayCryOnHop[OW_WILD_MAX_SPAWNS];
    u8 movementActiveSteps[OW_WILD_MAX_SPAWNS];
    u8 movementSpotCooldowns[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorClasses[OW_WILD_MAX_SPAWNS];
    s16 movementPreviousTileX[OW_WILD_MAX_SPAWNS];
    s16 movementPreviousTileY[OW_WILD_MAX_SPAWNS];
    u8 movementPreviousTileLocked[OW_WILD_MAX_SPAWNS];
    u8 movementPendingDirections[OW_WILD_MAX_SPAWNS];
    u8 movementPendingDistances[OW_WILD_MAX_SPAWNS];
    u8 movementLastDirections[OW_WILD_MAX_SPAWNS];
    u8 movementLastDistances[OW_WILD_MAX_SPAWNS];
    s16 movementSpawnRunTargetX[OW_WILD_MAX_SPAWNS];
    s16 movementSpawnRunTargetY[OW_WILD_MAX_SPAWNS];
    u8 movementSpawnRunActive[OW_WILD_MAX_SPAWNS];
    s16 movementStagedHopOriginX[OW_WILD_MAX_SPAWNS];
    s16 movementStagedHopOriginY[OW_WILD_MAX_SPAWNS];
    s16 movementStagedHopTargetX[OW_WILD_MAX_SPAWNS];
    s16 movementStagedHopTargetY[OW_WILD_MAX_SPAWNS];
    s16 movementStagedHopAvoidX[OW_WILD_MAX_SPAWNS];
    s16 movementStagedHopAvoidY[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyPathFailureX[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyPathFailureY[OW_WILD_MAX_SPAWNS];
    u8 movementStagedHopDistances[OW_WILD_MAX_SPAWNS];
    u8 movementStagedHopFinishWithTired[OW_WILD_MAX_SPAWNS];
    u8 movementStagedHopPending[OW_WILD_MAX_SPAWNS];
    u8 movementStagedHopAvoidValid[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyPathFailureCounts[OW_WILD_MAX_SPAWNS];
    u8 movementRamDirections[OW_WILD_MAX_SPAWNS];
    u8 movementRamStepCounters[OW_WILD_MAX_SPAWNS];
    u8 movementRamSpeeds[OW_WILD_MAX_SPAWNS];
    u8 movementRamCrashShakeTimers[OW_WILD_MAX_SPAWNS];
    u32 movementRamCrashShakeBaseX[OW_WILD_MAX_SPAWNS];
    u32 movementRamCrashShakeBaseZ[OW_WILD_MAX_SPAWNS];
    u8 movementPhantomHidden[OW_WILD_MAX_SPAWNS];
    u8 movementPhantomHiddenSteps[OW_WILD_MAX_SPAWNS];
    u8 movementPhantomFlickerTimers[OW_WILD_MAX_SPAWNS];
    u8 movementPhantomVisiblePause[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementMankeyTreeTopProxyObjects[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementPhantomFlickerObjects[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementPhantomTeleportFlickerObjects[OW_WILD_MAX_SPAWNS];
    s16 movementPhantomTeleportOriginX[OW_WILD_MAX_SPAWNS];
    s16 movementPhantomTeleportOriginY[OW_WILD_MAX_SPAWNS];
    s16 movementPhantomTeleportTargetX[OW_WILD_MAX_SPAWNS];
    s16 movementPhantomTeleportTargetY[OW_WILD_MAX_SPAWNS];
    u8 movementPhantomTeleportHasTarget[OW_WILD_MAX_SPAWNS];
    u8 movementAButtonDown;
    u16 mapGeneration;
    u16 pendingMapGeneration;
    u16 pendingEncounterGeneration;
    u8 presentationRestorePending;
    u16 captureTargetMask;
} OverworldWildSpawnState;

typedef struct OverworldWildResidentData {
    u8 pendingFlags;
    u8 battleFlags;
    u16 savedHp[OW_WILD_MAX_SPAWNS];
} OverworldWildResidentData;

extern OverworldWildResidentData gOverworldWildResidentData;

typedef enum OverworldWildMapHeaderChangeMode {
    OW_WILD_MAP_HEADER_CHANGE_PRESERVE = 0,
    OW_WILD_MAP_HEADER_CHANGE_DISCARD,
    OW_WILD_MAP_HEADER_CHANGE_CANONICALIZE,
} OverworldWildMapHeaderChangeMode;

typedef struct OverworldWildSpawnsOverlayEntry {
    BOOL (*onPlayerStep)(
        FieldSystem *fieldSystem,
        OverworldWildSpawnState *state,
        OverworldWildResidentData *residentData);
    BOOL (*tryPrimeBattleFromTalk)(
        FieldSystem *fieldSystem,
        OverworldWildSpawnState *state,
        LocalMapObject *talkedObject);
    u8 (*cleanupPendingBattle)(FieldSystem *fieldSystem, OverworldWildSpawnState *state, u16 battleResult);
    BOOL (*cleanupResidentData)(void);
    BOOL (*onPlayerFrame)(FieldSystem *fieldSystem, OverworldWildSpawnState *state);
    void (*onFieldBusy)(
        FieldSystem *fieldSystem,
        OverworldWildSpawnState *state,
        OverworldWildResidentData *residentData);
    void (*prepareMapHeaderChange)(
        OverworldWildSpawnState *state,
        OverworldWildMapHeaderChangeMode mode);
} OverworldWildSpawnsOverlayEntry;

typedef char OverworldWildSpawnsOverlayEntrySizeMustRemain28Bytes[
    sizeof(OverworldWildSpawnsOverlayEntry) == 28 ? 1 : -1];

extern OverworldWildSpawnState sOverworldWildSpawnState;

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY ((const OverworldWildSpawnsOverlayEntry *)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_SPAWNS_INTERNAL_H
