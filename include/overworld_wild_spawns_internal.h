#ifndef OVERWORLD_WILD_SPAWNS_INTERNAL_H
#define OVERWORLD_WILD_SPAWNS_INTERNAL_H

#include "overworld_wild_spawns.h"
#include "overworld_wild_behavior_data.h"
#include "constants/maps.h"

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR 0x023CD000
#define OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY_ADDR 0x023BD4D8
#define OVERWORLD_WILD_NATIVE_SHADOW_POLICY_ENTRY_ADDR 0x023BE3D8
#define OVERWORLD_WILD_NATIVE_SHADOW_POLICY_MASK_ADDR 0x023BE3FC
#define OW_WILD_LAND_SURF_MAX_SPAWNS 6
#define OW_WILD_HEADBUTT_MAX_SPAWNS 2
#define OW_WILD_FISH_MAX_SPAWNS 2
#define OW_WILD_HEADBUTT_SLOT_START OW_WILD_LAND_SURF_MAX_SPAWNS
#define OW_WILD_FISH_SLOT_START (OW_WILD_HEADBUTT_SLOT_START + OW_WILD_HEADBUTT_MAX_SPAWNS)
#define OW_WILD_FOLLOWER_SLOT (OW_WILD_FISH_SLOT_START - 1)
#define OW_WILD_MAX_SPAWNS (OW_WILD_LAND_SURF_MAX_SPAWNS + OW_WILD_HEADBUTT_MAX_SPAWNS + OW_WILD_FISH_MAX_SPAWNS)
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
#define OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING 0x04
#define OW_WILD_SPAWN_AGGRO_FLAG 0x02
#define OW_WILD_SPAWN_AGGRO_PENDING_FLAG 0x04
#define OW_WILD_SPOT_STATE_ACTIVE 2
#define OW_WILD_SPOT_STATE_TIRED 3

#define OW_WILD_FOLLOWER_RELEASE_NONE 0
#define OW_WILD_FOLLOWER_RELEASE_REQUESTED 1
#define OW_WILD_FOLLOWER_RELEASE_FLYING 2
#define OW_WILD_FOLLOWER_RELEASE_READY 3
#define OW_WILD_FOLLOWER_RELEASE_SPAWNED 4
#define OW_WILD_FOLLOWER_RELEASE_BOUNCING 5
#define OW_WILD_FOLLOWER_RELEASE_FAILED 6
#define OW_WILD_FOLLOWER_RELEASE_STATE_MASK 0x7F
#define OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG 0x80

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
    union {
        u8 movementCrashShakeTimers[OW_WILD_MAX_SPAWNS];
        u8 movementRamCrashShakeTimers[OW_WILD_MAX_SPAWNS];
    };
    union {
        u32 movementCrashShakeBaseX[OW_WILD_MAX_SPAWNS];
        u32 movementRamCrashShakeBaseX[OW_WILD_MAX_SPAWNS];
    };
    union {
        u32 movementCrashShakeBaseZ[OW_WILD_MAX_SPAWNS];
        u32 movementRamCrashShakeBaseZ[OW_WILD_MAX_SPAWNS];
    };
    u8 movementTeleportHidden[OW_WILD_MAX_SPAWNS];
    u8 movementTeleportHiddenSteps[OW_WILD_MAX_SPAWNS];
    u8 movementTeleportFlickerTimers[OW_WILD_MAX_SPAWNS];
    u8 movementTeleportVisiblePause[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementMankeyTreeTopProxyObjects[OW_WILD_MAX_SPAWNS];
    LocalMapObject *movementTeleportFlickerObjects[OW_WILD_MAX_SPAWNS];
    u8 movementAButtonDown;
    u16 mapGeneration;
    u16 pendingMapGeneration;
    u16 pendingEncounterGeneration;
    u8 presentationRestorePending;
    u8 activeFollowerPartySlot;
    u16 captureTargetMask;
    s16 followerReleaseX;
    s16 followerReleaseY;
    u8 followerReleaseState;
} OverworldWildSpawnState;

typedef void (*OverworldWildFollowerReleaseDispatchCallback)(
    FieldSystem *fieldSystem,
    u8 action);
typedef void (*OverworldWildFollowerReleaseRotationCallback)(s16 rotation);
BOOL OverworldWildSpawns_TickFollowerReleasePresentation(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    void *projectile,
    OverworldWildFollowerReleaseDispatchCallback dispatch,
    OverworldWildFollowerReleaseRotationCallback rotate);
void OverworldWildSpawns_RenderPlayerBallProjectile(
    void *projectile,
    OverworldWildFollowerReleaseRotationCallback rotate);

typedef struct OverworldWildResidentData {
    u8 pendingFlags;
    u8 battleFlags;
    u16 savedHp[OW_WILD_MAX_SPAWNS];
} OverworldWildResidentData;

extern OverworldWildResidentData gOverworldWildResidentData;
#define gOverworldWildNativeShadowSuppressedMask \
    (*(volatile u16 *)OVERWORLD_WILD_NATIVE_SHADOW_POLICY_MASK_ADDR)
/* Exact byte alias exported by overlay 129 for cross-overlay relocations. */
extern u8 gOverworldWildFieldIdleRearmPending;

typedef enum OverworldWildMapHeaderChangeMode {
    OW_WILD_MAP_HEADER_CHANGE_PRESERVE = 0,
    OW_WILD_MAP_HEADER_CHANGE_DISCARD,
    OW_WILD_MAP_HEADER_CHANGE_CANONICALIZE,
} OverworldWildMapHeaderChangeMode;

typedef BOOL (*OverworldWildHopLandingBaseValidatorFunc)(
    OverworldWildSpawnState *state,
    int slot,
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int landingX,
    int landingY,
    int targetX,
    int targetY);
typedef BOOL (*OverworldWildStartPreparedCustomJumpFunc)(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    u8 distance,
    int targetX,
    int targetY,
    const OverworldWildBehaviorProfile *profile,
    BOOL suppressHopStartSound);

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
    OverworldWildHopLandingBaseValidatorFunc validateHopLanding;
    OverworldWildStartPreparedCustomJumpFunc startPreparedCustomJump;
} OverworldWildSpawnsOverlayEntry;

typedef char OverworldWildSpawnsOverlayEntrySizeMustRemain36Bytes[
    sizeof(OverworldWildSpawnsOverlayEntry) == 36 ? 1 : -1];

extern OverworldWildSpawnState sOverworldWildSpawnState;

/*
 * Stock terrain transitions can request a native shadow after the overworld
 * overlay has classified an authored surface.  Keep the decision in resident
 * code so every stock request can be filtered even while the overlay is
 * between movement callbacks.
 */
typedef void (*OverworldWildSetNativeShadowSuppressedFunc)(
    LocalMapObject *object,
    BOOL suppressed);
#define OverworldWildSpawns_SetNativeShadowSuppressed \
    ((OverworldWildSetNativeShadowSuppressedFunc) \
        (OVERWORLD_WILD_NATIVE_SHADOW_POLICY_ENTRY_ADDR | 1))

typedef BOOL (*OverworldWildResolveHopTrajectoryFunc)(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *surfaceCatalog,
    const OverworldWildBehaviorProfileData *lane,
    LocalMapObject *object,
    s32 startBaseY,
    s32 targetBaseY,
    int startX,
    int startY,
    int targetX,
    int targetY,
    u8 distance,
    u32 *trajectoryOut);

typedef BOOL (*OverworldWildTryGetBehaviorHopVectorFunc)(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance);
typedef BOOL (*OverworldWildHopTileValidatorFunc)(
    int landingX,
    int landingY,
    int targetX,
    int targetY,
    void *context);
typedef void (*OverworldWildBuildHopHelperConfigFunc)(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int objectX,
    int objectY,
    int targetX,
    int targetY,
    const u8 *directions,
    int directionCount,
    BOOL stopOneHopAway,
    void *config);
typedef BOOL (*OverworldWildRunChainRepositionFunc)(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 *jumpsRemaining);

#define OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS \
    u8 movementCustomJumpPrepActive[OW_WILD_MAX_SPAWNS]; \
    u8 movementCustomJumpActive[OW_WILD_MAX_SPAWNS]; \
    LocalMapObject *movementEmotePartnerPrepObjects[OW_WILD_MAX_SPAWNS]; \
    s16 movementCustomJumpStartX[OW_WILD_MAX_SPAWNS]; \
    s16 movementCustomJumpStartY[OW_WILD_MAX_SPAWNS]; \
    s16 movementCustomJumpTargetX[OW_WILD_MAX_SPAWNS]; \
    s16 movementCustomJumpTargetY[OW_WILD_MAX_SPAWNS]; \
    s32 movementCustomJumpStartBaseY[OW_WILD_MAX_SPAWNS]; \
    s32 movementCustomJumpTargetBaseY[OW_WILD_MAX_SPAWNS]; \
    u16 movementCustomJumpFrameCounts[OW_WILD_MAX_SPAWNS]; \
    u16 movementCustomJumpElapsedFrames[OW_WILD_MAX_SPAWNS]; \
    u16 movementCustomJumpSpinElapsedFrames[OW_WILD_MAX_SPAWNS]; \
    u8 movementCustomJumpSpinSpeeds[OW_WILD_MAX_SPAWNS]; \
    u8 movementCustomJumpSpinTimers[OW_WILD_MAX_SPAWNS]; \
    u8 movementCustomJumpSpinSteps[OW_WILD_MAX_SPAWNS]; \
    s32 movementCustomJumpShadowBaseY[OW_WILD_MAX_SPAWNS]

typedef u8 (*OverworldWildApplyJumpRenderMotionFunc)(
    const void *runtimeState,
    int slot,
    LocalMapObject *object,
    u32 elapsed,
    u8 arcHeightQ4);

typedef struct OverworldWildBehaviorHopValidationContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildSurfaceCatalog *surfaceCatalog;
    OverworldWildHopLandingBaseValidatorFunc baseValidator;
    int slot;
    u16 allowedTile;
} OverworldWildBehaviorHopValidationContext;

typedef struct OverworldWildHopTrajectoryEntry {
    OverworldWildResolveHopTrajectoryFunc resolve;
    OverworldWildTryGetBehaviorHopVectorFunc tryGetVector;
    OverworldWildHopTileValidatorFunc validateHopLanding;
    OverworldWildBuildHopHelperConfigFunc buildHelperConfig;
    OverworldWildRunChainRepositionFunc runChainReposition;
    OverworldWildApplyJumpRenderMotionFunc applyJumpRenderMotion;
} OverworldWildHopTrajectoryEntry;

#define OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY \
    ((const OverworldWildHopTrajectoryEntry *) \
        OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY_ADDR)

#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY ((const OverworldWildSpawnsOverlayEntry *)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_SPAWNS_INTERNAL_H
