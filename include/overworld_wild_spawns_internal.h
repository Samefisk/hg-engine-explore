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
#define OW_WILD_MAX_SPAWNS (OW_WILD_GRASS_MAX_SPAWNS + OW_WILD_SURF_MAX_SPAWNS + OW_WILD_HEADBUTT_MAX_SPAWNS + OW_WILD_FISH_MAX_SPAWNS)
#define OW_WILD_MAX_SAVED_SHINIES 2
#define OW_WILD_SAVED_SHINY_ACTIVE 0x80
#define OW_WILD_SAVED_SHINY_TERRAIN_MASK 0x7F
#define OW_WILD_SPECIES_MASK 0x7FF
#define OW_WILD_FORM_SHIFT 11
#define OW_WILD_CANOPY_HOP_MOVEMENT_LIST_WORDS 72

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
} OverworldWildSpawn;

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
    u8 movementPlayfulNeighborSteps[OW_WILD_MAX_SPAWNS];
    u8 movementSpotCooldowns[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorClasses[OW_WILD_MAX_SPAWNS];
    u16 movementForcedAsleepMask;
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
    s16 movementCanopyHopOriginX[OW_WILD_MAX_SPAWNS];
    s16 movementCanopyHopOriginY[OW_WILD_MAX_SPAWNS];
    s16 movementCanopyHopTargetX[OW_WILD_MAX_SPAWNS];
    s16 movementCanopyHopTargetY[OW_WILD_MAX_SPAWNS];
    s16 movementCanopyHopAvoidX[OW_WILD_MAX_SPAWNS];
    s16 movementCanopyHopAvoidY[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyPathFailureX[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyPathFailureY[OW_WILD_MAX_SPAWNS];
    u8 movementCanopyHopDirections[OW_WILD_MAX_SPAWNS];
    u8 movementCanopyHopDistances[OW_WILD_MAX_SPAWNS];
    u8 movementCanopyHopFinishWithTired[OW_WILD_MAX_SPAWNS];
    u8 movementCanopyHopPending[OW_WILD_MAX_SPAWNS];
    u8 movementCanopyHopAvoidValid[OW_WILD_MAX_SPAWNS];
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
} OverworldWildSpawnState;

typedef struct OverworldWildSpawnsOverlayEntry {
    BOOL (*onPlayerStep)(FieldSystem *fieldSystem, OverworldWildSpawnState *state);
    void (*cleanupPendingBattle)(FieldSystem *fieldSystem, OverworldWildSpawnState *state, u16 battleResult);
    void (*visualTesterCommand)(FieldSystem *fieldSystem, u16 command);
    void (*cleanupResidentData)(void);
} OverworldWildSpawnsOverlayEntry;

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY ((const OverworldWildSpawnsOverlayEntry *)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_SPAWNS_INTERNAL_H
