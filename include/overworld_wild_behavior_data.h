#ifndef OVERWORLD_WILD_BEHAVIOR_DATA_H
#define OVERWORLD_WILD_BEHAVIOR_DATA_H

#include "types.h"
#include "constants/generated/overworld_wild_roof_catalog_counts.h"

typedef struct FieldSystem FieldSystem;
struct LocalMapObject;
struct OverworldWildSpawnState;
struct OverworldWildThrowState;
struct OverworldWildBehaviorPrimitives;

#define OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR 0x023C3000
#define OVERWORLD_WILD_LEGACY_ENCOUNTER_LOOKUP_ENTRY_ADDR 0x023C3000
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE_ADDR 0x023C3059
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_CLEANUP_ADDR 0x023C3101
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_MAGIC 0x4F57424F
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION 8
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC 0x4F574244
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 65
#define OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_MAGIC 0x4F574544
#define OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_VERSION 2
#define OVERWORLD_WILD_SPAWN_METADATA_MAGIC 0x4F57534D
#define OVERWORLD_WILD_SPAWN_METADATA_VERSION 2
#define OVERWORLD_WILD_SPAWN_METADATA_OVERLAY_MAGIC 0x4F57534F
#define OVERWORLD_WILD_SPAWN_METADATA_OVERLAY_VERSION 2
#define OVERWORLD_WILD_LEARNSET_CACHE_OVERLAY_MAGIC 0x4F574C43
#define OVERWORLD_WILD_LEARNSET_CACHE_OVERLAY_VERSION 1
#define OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_MAGIC 0x4F575043
#define OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_VERSION 1
#define OVERWORLD_WILD_LEVELUP_LEARNSET_DISPATCH_SLOT_ADDR 0x02071FD8
#define OVERWORLD_WILD_PERSONAL_PARAM_DISPATCH_SLOT_ADDR 0x0206FBEC
#define OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR 0x023C30E0
#define OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY_ADDR 0x023C30EC
#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY_ADDR 0x023C30F0
#define OVERWORLD_WILD_STAGED_HOP_TASKS_ADDR 0x023C3F18
#define OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM 31
#define OW_WILD_BEHAVIOR_CLASS_DEFAULT 0
#define OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE 1
#define OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM 2
#define OW_WILD_BEHAVIOR_CLASS_PICKED_UP 3
#define OWBD_CLASS_PROFILE_COUNT 4
#define OWBD_CLASS_RULE_COUNT 2
#define OWBD_SPECIES_CLASS_RULE_COUNT 113
#define OWBD_OVERRIDE_PROFILE_COUNT 17
#define OWBD_CONDITIONAL_STATE_COUNT 1
#define OWBD_CONDITIONAL_STATE_STORAGE_COUNT \
    ((OWBD_CONDITIONAL_STATE_COUNT) ? OWBD_CONDITIONAL_STATE_COUNT : 1)
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_BIRD 5
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON 13
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_ACTIVE 15
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_TIRED 16
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_BIRD_ROOFTOP 11
typedef char OverworldWildBehaviorOverrideProfileCountMustFitApplicabilityMask[
    OWBD_OVERRIDE_PROFILE_COUNT <= 32 ? 1 : -1];
#define OWBD_OVERRIDE_MEMBER_COUNT 195
#define OWBD_SURFACE_MODEL_COUNT OWBD_GENERATED_SURFACE_MODEL_COUNT
#define OWBD_SURFACE_INSTANCE_COUNT OWBD_GENERATED_SURFACE_INSTANCE_COUNT
#define OWBD_SURFACE_TEMPLATE_COUNT OWBD_GENERATED_SURFACE_TEMPLATE_COUNT
#define OWBD_SURFACE_CATALOG_RAW_SIZE \
    (OWBD_SURFACE_MODEL_COUNT * 6 + OWBD_SURFACE_INSTANCE_COUNT * 10 \
        + OWBD_SURFACE_TEMPLATE_COUNT * 2)
/* surfaceModels begins two bytes past a four-byte boundary in blob v57. */
#define OWBD_SURFACE_CATALOG_PADDING_SIZE \
    ((4 - ((OWBD_SURFACE_CATALOG_RAW_SIZE + 2) & 3)) & 3)
#define OW_WILD_ROOF_HEIGHT_QUANTUM_SHIFT 4
#define OW_WILD_MAP_BLOCK_SHIFT 5
#define OW_WILD_MAP_BLOCK_MASK 31
#define OW_WILD_MAP_MATRIX_ALTITUDES_OFFSET 0x644
#define OW_WILD_MAP_MATRIX_MODELS_OFFSET 0x964
#define OW_WILD_MAP_ALTITUDE_HEIGHT_SHIFT 15
#define OW_WILD_SURFACE_ID_BLOCK_SHIFT 4
#define OWBD_OVERRIDE_COUNT OWBD_OVERRIDE_PROFILE_COUNT
#define OWED_ENCOUNTER_AREA_COUNT 150
#define OWED_ENCOUNTER_LOOKUP_DIRECTORY_ENTRY_SIZE 12

#define OWED_SECTION_LAND_LEVELS (1u << 0)
#define OWED_SECTION_LAND_MORNING (1u << 1)
#define OWED_SECTION_LAND_DAY (1u << 2)
#define OWED_SECTION_LAND_NIGHT (1u << 3)
#define OWED_SECTION_SURF (1u << 4)
#define OWED_SECTION_OLD_ROD (1u << 5)
#define OWED_SECTION_GOOD_ROD (1u << 6)
#define OWED_SECTION_SUPER_ROD (1u << 7)

typedef enum OverworldWildSpawnTerrain {
    OW_WILD_SPAWN_TERRAIN_LAND,
    OW_WILD_SPAWN_TERRAIN_SURF,
    OW_WILD_SPAWN_TERRAIN_HEADBUTT,
    OW_WILD_SPAWN_TERRAIN_FISHING,
} OverworldWildSpawnTerrain;

typedef enum OverworldWildSpawnDestination {
    OW_WILD_SPAWN_DESTINATION_POOL,
    OW_WILD_SPAWN_DESTINATION_CANOPY,
    OW_WILD_SPAWN_DESTINATION_LAND,
    OW_WILD_SPAWN_DESTINATION_GRASS,
    OW_WILD_SPAWN_DESTINATION_SHORE,
    OW_WILD_SPAWN_DESTINATION_WATER,
    OW_WILD_SPAWN_DESTINATION_FIVE_TILES_BEHIND_PLAYER,
    OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER,
    OW_WILD_SPAWN_DESTINATION_TWO_TILES_FRONT_OF_PLAYER,
    OW_WILD_SPAWN_DESTINATION_THREE_TILES_FRONT_OF_PLAYER,
    OW_WILD_SPAWN_DESTINATION_FOUR_TILES_FRONT_OF_PLAYER,
    OW_WILD_SPAWN_DESTINATION_FIVE_TILES_FRONT_OF_PLAYER,
    OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER,
    OW_WILD_SPAWN_DESTINATION_TWO_TILES_BEHIND_PLAYER,
    OW_WILD_SPAWN_DESTINATION_THREE_TILES_BEHIND_PLAYER,
    OW_WILD_SPAWN_DESTINATION_FOUR_TILES_BEHIND_PLAYER,
    OW_WILD_SPAWN_DESTINATION_NEXT_TO_PLAYER,
    OW_WILD_SPAWN_DESTINATION_ROOFTOP,
    OW_WILD_SPAWN_DESTINATION_SIGNPOST,
    OW_WILD_SPAWN_DESTINATION_MAILBOX,
    OW_WILD_SPAWN_DESTINATION_FLOWERBED,
} OverworldWildSpawnDestination;

#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND         (1u << 0)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER        (1u << 1)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY       (1u << 2)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS        (1u << 3)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER       (1u << 4)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT (1u << 5)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP      (1u << 6)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST     (1u << 7)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX      (1u << 8)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_FLOWERBED    (1u << 9)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_FIRST \
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL \
    (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_FLOWERBED)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL          0x03FF
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT      OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND

#define OW_WILD_SURFACE_TYPE_ROOFTOP 0
#define OW_WILD_SURFACE_TYPE_SIGNPOST 1
#define OW_WILD_SURFACE_TYPE_MAILBOX 2
#define OW_WILD_SURFACE_TYPE_FLOWERBED 3
#define OW_WILD_SURFACE_TYPE_COUNT 4
#define OW_WILD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND 0xFF
#define OW_WILD_SURFACE_ID_NATIVE_GROUND 0xFFFF
#define OW_WILD_SURFACE_TYPE_TERRAIN_MASK(surfaceType) \
    (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_FIRST << (surfaceType))

#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_FRONT  (1u << 0)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_BEHIND (1u << 1)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_LEFT   (1u << 2)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_RIGHT  (1u << 3)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL   0xFu
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL

#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND 2
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS 3
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS 4
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMPS_DEFAULT 3
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMPS_MAX 8
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_SPEED_DEFAULT 1
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_SPEED_MAX 4
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DISTANCE_DEFAULT 1
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DISTANCE_MAX 5
#define OW_WILD_BEHAVIOR_TILES_TO_ACCELERATE_DEFAULT 3
#define OW_WILD_BEHAVIOR_MAX_WALK_SPEED_DEFAULT 4
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 6
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_NO_FLICKER 9
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE 10
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER 11
/* Source compatibility for profiles authored before Teleport was generalized. */
#define OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT
#define OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(locomotion) \
    ((locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_NO_FLICKER \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER)
#define OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER(locomotion) \
    ((locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE)
#define OW_WILD_BEHAVIOR_TELEPORT_USES_PER_TILE_TIME(locomotion) \
    ((locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE \
        || (locomotion) == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER)
#define OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION (1u << 0)
#define OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_SHIFT 1
#define OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_MASK (7u << OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT 4
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK (7u << OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_OPTIONS_RESERVED_MASK (1u << 7)
#define OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) == 0)
#define OW_WILD_BEHAVIOR_WALK_STOMP_SPEED(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_MASK) \
        >> OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK) \
        >> OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_OPTIONS(lockDirection, stompSpeed, crashSound) \
    (((lockDirection) ? OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION : 0) \
        | (((stompSpeed) << OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_STOMP_SPEED_MASK) \
        | (((crashSound) << OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK))
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_NONE 0
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT 1
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MAX \
    OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT
#define OW_WILD_BEHAVIOR_HOP_SWAY_WIDTH_MAX 8
#define OW_WILD_BEHAVIOR_JUMP_ARC_HEIGHT_MIN_Q4 16

/* Compact blob representation. Active and tired runtime lanes are composed
 * from the Chill lane of the referenced override profiles. */
typedef struct OverworldWildBehaviorProfileData {
    u8 chillState;
    u8 alertState;
    u8 alertEmote;
    u8 alertTime;
    u8 alertness;
    u8 stamina;
    u8 restTime;
    u8 chillSpeed;
    u8 range;
    u8 jumpLevel;
    u8 profileId;
    u8 spawnState;
    u8 chillAction;
    u8 chillTarget;
    u8 alertRange;
    u8 playerAdjacentDirectionMasks;
    u8 alertChance;
    u8 spawnDestination;
    u8 battleTrigger;
    u8 hopAllowNonCardinal;
    u8 hopMinDistance;
    u8 hopMaxDistance;
    u8 hopPause;
    u8 teleportTime;
    u8 teleportPause;
    u8 alertSpecialAction;
    u8 overworldLimit;
    u8 spawnDestinationMinDistance;
    u8 spawnDestinationMaxDistance;
    u8 ramAccelerationSteps;
    u8 ramMaxSpeed;
    u8 chainPauseAction;
    /* One value bit and one explicit/inherit bit per terrain. */
    u16 chillAllowedTerrainMask;
    u16 chillAllowedTerrainOverrideMask;
    u8 hopTime;
    u8 chaseBoostDistance;
    u8 chaseBoostSpeed;
    u8 hopSpinSpeed;
    u8 spawnHopTime;
    u8 circleRadius;
    u8 continueWhenArrived;
    u8 avoidPreviousTile;
    u8 chainMovementVariance;
    u8 chainPauseVariance;
    u8 activeProfile;
    u8 tiredProfile;
    u8 hopElevationTimeScale;
    u8 hopElevationArcScale;
    u8 tilesToAccelerate;
    u8 maxWalkSpeed;
    /* Spawn placement uses the same option bits as allowed terrain, but its
     * value/inheritance policy is stored and resolved independently. */
    u16 spawnDestinationMask;
    u16 spawnDestinationOverrideMask;
    u8 hopAllowVerticalObstacles;
    u8 chainRepositionJumpCount;
    u8 hopSwayWidth;
    u8 spawnHopSwayWidth;
    u8 chainRepositionSpeed;
    u8 chainRepositionDistance;
    u8 chainRepositionDust;
    u8 chainRepositionAllowCardinal;
    u8 chainRepositionAllowDiagonal;
    /* Zero preserves the legacy Walk behavior: turning allowed, no effects. */
    u8 walkOptions;
} OverworldWildBehaviorProfileData;

typedef char OverworldWildBehaviorProfileDataSizeMustRemain66Bytes[
    sizeof(OverworldWildBehaviorProfileData) == 66 ? 1 : -1];

/* Runtime composite. Its prefix intentionally matches the compact blob so the
 * owner Chill lane can be copied directly before linked state lanes are added. */
typedef struct OverworldWildBehaviorProfile {
    union {
        OverworldWildBehaviorProfileData owner;
        struct {
            u8 chillState;
            u8 alertState;
            u8 alertEmote;
            u8 alertTime;
            u8 alertness;
            u8 stamina;
            u8 restTime;
            u8 chillSpeed;
            u8 range;
            u8 jumpLevel;
            u8 profileId;
            u8 spawnState;
            u8 chillAction;
            u8 chillTarget;
            u8 alertRange;
            u8 playerAdjacentDirectionMasks;
            u8 alertChance;
            u8 spawnDestination;
            u8 battleTrigger;
            u8 hopAllowNonCardinal;
            u8 hopMinDistance;
            u8 hopMaxDistance;
            u8 hopPause;
            u8 teleportTime;
            u8 teleportPause;
            u8 alertSpecialAction;
            u8 overworldLimit;
            u8 spawnDestinationMinDistance;
            u8 spawnDestinationMaxDistance;
            u8 ramAccelerationSteps;
            u8 ramMaxSpeed;
            u8 chainPauseAction;
            u16 chillAllowedTerrainMask;
            u16 chillAllowedTerrainOverrideMask;
            u8 hopTime;
            u8 chaseBoostDistance;
            u8 chaseBoostSpeed;
            u8 hopSpinSpeed;
            u8 spawnHopTime;
            u8 circleRadius;
            u8 continueWhenArrived;
            u8 avoidPreviousTile;
            u8 chainMovementVariance;
            u8 chainPauseVariance;
            u8 activeProfile;
            u8 tiredProfile;
            u8 hopElevationTimeScale;
            u8 hopElevationArcScale;
            u8 tilesToAccelerate;
            u8 maxWalkSpeed;
            u16 spawnDestinationMask;
            u16 spawnDestinationOverrideMask;
            u8 hopAllowVerticalObstacles;
            u8 chainRepositionJumpCount;
            u8 hopSwayWidth;
            u8 spawnHopSwayWidth;
            u8 chainRepositionSpeed;
            u8 chainRepositionDistance;
            u8 chainRepositionDust;
            u8 chainRepositionAllowCardinal;
            u8 chainRepositionAllowDiagonal;
            u8 walkOptions;
        };
    };
    union {
        OverworldWildBehaviorProfileData active;
        struct {
            u8 attentiveState;
            u8 _activePad01[5];
            u8 _activePad06;
            u8 attentiveSpeed;
            u8 _activePad08[4];
            u8 movementStyle;
            u8 targetSelector;
            u8 _activePad14;
            u8 attentivePlayerAdjacentDirectionMasks;
            u8 _activePad16[2];
            u8 attentiveBattle;
            u8 attentiveHopAllowNonCardinal;
            u8 attentiveHopMinDistance;
            u8 attentiveHopMaxDistance;
            u8 attentiveHopPause;
            u8 attentiveTeleportTime;
            u8 attentiveTeleportPause;
            u8 _activePad25[4];
            u8 attentiveRamAccelerationSteps;
            u8 attentiveRamMaxSpeed;
            u8 attentiveChainPauseAction;
            u16 attentiveAllowedTerrainMask;
            u16 attentiveAllowedTerrainOverrideMask;
            u8 attentiveHopTime;
            u8 attentiveChaseBoostDistance;
            u8 attentiveChaseBoostSpeed;
            u8 attentiveHopSpinSpeed;
            u8 _activePad40;
            u8 attentiveCircleRadius;
            u8 attentiveContinueWhenArrived;
            u8 attentiveAvoidPreviousTile;
            u8 attentiveChainMovementVariance;
            u8 attentiveChainPauseVariance;
            u8 _activePad46[2];
            u8 attentiveHopElevationTimeScale;
            u8 attentiveHopElevationArcScale;
            u8 attentiveTilesToAccelerate;
            u8 attentiveMaxWalkSpeed;
            u16 attentiveSpawnDestinationMask;
            u16 attentiveSpawnDestinationOverrideMask;
            u8 attentiveHopAllowVerticalObstacles;
            u8 attentiveChainRepositionJumpCount;
            u8 attentiveHopSwayWidth;
            u8 attentiveSpawnHopSwayWidth;
            u8 attentiveChainRepositionSpeed;
            u8 attentiveChainRepositionDistance;
            u8 attentiveChainRepositionDust;
            u8 attentiveChainRepositionAllowCardinal;
            u8 attentiveChainRepositionAllowDiagonal;
            u8 attentiveWalkOptions;
        };
    };
    union {
        OverworldWildBehaviorProfileData tired;
        struct {
            u8 tiredState;
            u8 _tiredPad01[6];
            u8 tiredSpeed;
            u8 _tiredPad08[7];
            u8 tiredPlayerAdjacentDirectionMasks;
            u8 _tiredPad16[3];
            u8 tiredHopAllowNonCardinal;
            u8 tiredHopMinDistance;
            u8 tiredHopMaxDistance;
            u8 tiredHopPause;
            u8 tiredTeleportTime;
            u8 tiredTeleportPause;
            u8 _tiredPad25[4];
            u8 tiredRamAccelerationSteps;
            u8 tiredRamMaxSpeed;
            u8 tiredChainPauseAction;
            u16 tiredAllowedTerrainMask;
            u16 tiredAllowedTerrainOverrideMask;
            u8 tiredHopTime;
            u8 _tiredPad37[2];
            u8 tiredHopSpinSpeed;
            u8 _tiredPad40;
            u8 tiredCircleRadius;
            u8 tiredContinueWhenArrived;
            u8 tiredAvoidPreviousTile;
            u8 tiredChainMovementVariance;
            u8 tiredChainPauseVariance;
            u8 _tiredPad46[2];
            u8 tiredHopElevationTimeScale;
            u8 tiredHopElevationArcScale;
            u8 tiredTilesToAccelerate;
            u8 tiredMaxWalkSpeed;
            u16 tiredSpawnDestinationMask;
            u16 tiredSpawnDestinationOverrideMask;
            u8 tiredHopAllowVerticalObstacles;
            u8 tiredChainRepositionJumpCount;
            u8 tiredHopSwayWidth;
            u8 tiredSpawnHopSwayWidth;
            u8 tiredChainRepositionSpeed;
            u8 tiredChainRepositionDistance;
            u8 tiredChainRepositionDust;
            u8 tiredChainRepositionAllowCardinal;
            u8 tiredChainRepositionAllowDiagonal;
            u8 tiredWalkOptions;
        };
    };
} OverworldWildBehaviorProfile;

typedef char OverworldWildBehaviorProfileSizeMustRemain198Bytes[
    sizeof(OverworldWildBehaviorProfile) == 198 ? 1 : -1];

typedef struct OverworldWildBehaviorContext {
    u16 species;
    u16 conditionTerrainMask;
    u32 groupFlags;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 behaviorClass;
} OverworldWildBehaviorContext;

typedef struct OverworldWildBehaviorMatch {
    u32 groupMask;
    u16 species;
    u8 terrain;
    u8 minLevel;
    u8 maxLevel;
    u8 shiny;
    u8 behaviorClass;
} OverworldWildBehaviorMatch;

typedef struct OverworldWildBehaviorClassRule {
    OverworldWildBehaviorMatch match;
    u8 behaviorClass;
} OverworldWildBehaviorClassRule;

typedef struct OverworldWildBehaviorSpeciesClassRule {
    u16 species;
    u8 behaviorClass;
} OverworldWildBehaviorSpeciesClassRule;

typedef struct OverworldWildBehaviorOverrideProfile {
    OverworldWildBehaviorMatch match;
    u16 memberStart;
    u16 memberCount;
    u8 targetMode;
    u32 mask;
    u16 mask2;
    u32 mask3;
    OverworldWildBehaviorProfileData profile;
    u32 relativeMask;
    u16 relativeMask2;
    u32 relativeMask3;
    u32 atLeastMask;
    u16 atLeastMask2;
    u32 atLeastMask3;
    u32 atMostMask;
    u16 atMostMask2;
    u32 atMostMask3;
    /* Used only when a relative adjustment is followed by a bound. */
    OverworldWildBehaviorProfileData compoundBoundProfile;
} OverworldWildBehaviorOverrideProfile;

typedef char OverworldWildBehaviorOverrideProfileSizeMustRemain204Bytes[
    sizeof(OverworldWildBehaviorOverrideProfile) == 204 ? 1 : -1];

typedef struct OverworldWildBehaviorConditionalState {
    u8 parentProfile;
    u8 overrideProfile;
    u16 terrainMask;
    u16 terrainOverrideMask;
    u8 minMovementSpeed;
    u8 maxMovementSpeed;
} OverworldWildBehaviorConditionalState;

typedef char OverworldWildBehaviorConditionalStateSizeMustRemain8Bytes[
    sizeof(OverworldWildBehaviorConditionalState) == 8 ? 1 : -1];

#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED 0
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS 1
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL 2
#define OW_WILD_BEHAVIOR_CONDITIONAL_PROFILE_NONE 0xFF
#define OW_WILD_BEHAVIOR_RELATIVE(value) ((u8)(s8)(value))
#define OW_WILD_BEHAVIOR_AT_LEAST(value) ((u8)(value))
#define OW_WILD_BEHAVIOR_AT_MOST(value) ((u8)(value))

#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_STATE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_EMOTE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_TIME (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERTNESS (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE_STAMINA (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE_RANGE (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_ID (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_TARGET (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_RANGE (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE_PLAYER_ADJACENT_DIRECTION_MASKS (1u << 15)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_CHANCE (1u << 16)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION (1u << 17)
#define OW_WILD_BEHAVIOR_OVERRIDE_BATTLE_TRIGGER (1u << 18)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_ALLOW_NON_CARDINAL (1u << 19)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_MIN_DISTANCE (1u << 20)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_MAX_DISTANCE (1u << 21)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_PAUSE (1u << 22)
#define OW_WILD_BEHAVIOR_OVERRIDE_TELEPORT_TIME (1u << 23)
#define OW_WILD_BEHAVIOR_OVERRIDE_TELEPORT_PAUSE (1u << 24)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_SPECIAL_ACTION (1u << 25)
#define OW_WILD_BEHAVIOR_OVERRIDE_OVERWORLD_LIMIT (1u << 26)

#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MIN_DISTANCE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MAX_DISTANCE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RAM_ACCELERATION_STEPS (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RAM_MAX_SPEED (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_PAUSE_ACTION (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_MASK (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE2_HOP_TIME (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHASE_BOOST_DISTANCE (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHASE_BOOST_SPEED (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE2_HOP_SPIN_SPEED (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_HOP_TIME (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CIRCLE_RADIUS (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CONTINUE_WHEN_ARRIVED (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE2_AVOID_PREVIOUS_TILE (1u << 14)

#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_MOVEMENT_VARIANCE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_VARIANCE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ACTIVE_PROFILE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_PROFILE (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE3_HOP_ELEVATION_TIME_SCALE (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE3_HOP_ELEVATION_ARC_SCALE (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TILES_TO_ACCELERATE (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE3_MAX_WALK_SPEED (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_MASK (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_OVERRIDE_MASK (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE3_HOP_ALLOW_VERTICAL_OBSTACLES (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_JUMP_COUNT (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE3_HOP_SWAY_WIDTH (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_HOP_SWAY_WIDTH (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_SPEED (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_DISTANCE (1u << 15)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_DUST (1u << 16)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_ALLOW_CARDINAL (1u << 17)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_ALLOW_DIAGONAL (1u << 18)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_OPTIONS (1u << 19)

#define OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP 0xFD

#define OW_WILD_BEHAVIOR_OVERRIDE_NORMAL_SPEED OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED

typedef struct OverworldWildBehaviorDataOverlayEntry {
    const OverworldWildBehaviorProfileData *classProfiles;
    u16 classProfileCount;
    const OverworldWildBehaviorClassRule *classRules;
    u16 classRuleCount;
    const OverworldWildBehaviorSpeciesClassRule *speciesClassRules;
    u16 speciesClassRuleCount;
    const OverworldWildBehaviorOverrideProfile *overrideProfiles;
    u16 overrideProfileCount;
    const u16 *overrideMembers;
    u16 overrideMemberCount;
} OverworldWildBehaviorDataOverlayEntry;

typedef struct OverworldWildBehaviorDataBlobHeader {
    u32 magic;
    u16 version;
    u16 headerSize;
    u32 blobSize;
    u32 classProfilesOffset;
    u16 classProfileCount;
    u16 classProfileSize;
    u32 classRulesOffset;
    u16 classRuleCount;
    u16 classRuleSize;
    u32 speciesClassRulesOffset;
    u16 speciesClassRuleCount;
    u16 speciesClassRuleSize;
    u32 overrideProfilesOffset;
    u16 overrideProfileCount;
    u16 overrideProfileSize;
    u32 overrideMembersOffset;
    u16 overrideMemberCount;
    u16 overrideMemberSize;
    u32 conditionalStatesOffset;
    u16 conditionalStateCount;
    u16 conditionalStateSize;
    u32 surfaceModelsOffset;
    u16 surfaceModelCount;
    u16 surfaceModelSize;
    u32 surfaceInstancesOffset;
    u16 surfaceInstanceCount;
    u16 surfaceInstanceSize;
    u32 surfaceTemplatesOffset;
    u16 surfaceTemplateCount;
    u16 surfaceTemplateSize;
} OverworldWildBehaviorDataBlobHeader;

typedef char OverworldWildBehaviorDataBlobHeaderSizeMustRemain84Bytes[
    sizeof(OverworldWildBehaviorDataBlobHeader) == 84 ? 1 : -1];

typedef struct OverworldWildSurfaceModelDirectoryEntry {
    u16 landDataId;
    u16 firstInstance;
    u8 instanceCount;
    u8 reserved;
} OverworldWildSurfaceModelDirectoryEntry;

typedef struct OverworldWildSurfaceInstance {
    u8 minX;
    u8 minY;
    u8 templateId;
    u8 localSurfaceId;
    u16 heightQ4;
    u8 heightPage;
    u8 surfaceType;
    s8 anchorBlockDx;
    s8 anchorBlockDy;
} OverworldWildSurfaceInstance;

typedef struct OverworldWildSurfaceTemplate {
    u8 width;
    u8 height;
} OverworldWildSurfaceTemplate;

typedef struct OverworldWildSurfaceCatalog {
    OverworldWildSurfaceModelDirectoryEntry models[OWBD_SURFACE_MODEL_COUNT];
    OverworldWildSurfaceInstance instances[OWBD_SURFACE_INSTANCE_COUNT];
    OverworldWildSurfaceTemplate templates[OWBD_SURFACE_TEMPLATE_COUNT];
} OverworldWildSurfaceCatalog;

typedef struct OverworldWildSurfaceHit {
    s32 height;
    u16 surfaceId;
    u8 surfaceType;
    u8 nodeId;
} OverworldWildSurfaceHit;

typedef struct OverworldWildSurfaceBlockCache {
    const OverworldWildSurfaceCatalog *catalog;
    u16 blockIndex;
    u8 matrixId;
    u8 modelIndex;
} OverworldWildSurfaceBlockCache;

typedef char OverworldWildSurfaceModelCountMustFitCacheIndex[
    OWBD_SURFACE_MODEL_COUNT < 0xFF ? 1 : -1];

typedef char OverworldWildSurfaceModelDirectoryEntrySizeMustRemain6Bytes[
    sizeof(OverworldWildSurfaceModelDirectoryEntry) == 6 ? 1 : -1];
typedef char OverworldWildSurfaceInstanceSizeMustRemain10Bytes[
    sizeof(OverworldWildSurfaceInstance) == 10 ? 1 : -1];
typedef char OverworldWildSurfaceTemplateSizeMustRemain2Bytes[
    sizeof(OverworldWildSurfaceTemplate) == 2 ? 1 : -1];
typedef char OverworldWildSurfaceCatalogMustRemainPacked[
    sizeof(OverworldWildSurfaceCatalog)
            == OWBD_SURFACE_MODEL_COUNT * sizeof(OverworldWildSurfaceModelDirectoryEntry)
                + OWBD_SURFACE_INSTANCE_COUNT * sizeof(OverworldWildSurfaceInstance)
                + OWBD_SURFACE_TEMPLATE_COUNT * sizeof(OverworldWildSurfaceTemplate)
        ? 1
        : -1];
typedef char OverworldWildSurfaceCatalogInstancesOffsetMustRemainPacked[
    offsetof(OverworldWildSurfaceCatalog, instances)
            == OWBD_SURFACE_MODEL_COUNT * sizeof(OverworldWildSurfaceModelDirectoryEntry)
        ? 1
        : -1];
typedef char OverworldWildSurfaceCatalogTemplatesOffsetMustRemainPacked[
    offsetof(OverworldWildSurfaceCatalog, templates)
            == OWBD_SURFACE_MODEL_COUNT * sizeof(OverworldWildSurfaceModelDirectoryEntry)
                + OWBD_SURFACE_INSTANCE_COUNT * sizeof(OverworldWildSurfaceInstance)
        ? 1
        : -1];
typedef char OverworldWildSurfaceTemplateCountMustFitByteIndex[
    OWBD_SURFACE_TEMPLATE_COUNT <= 256 ? 1 : -1];
typedef char OverworldWildSurfaceHitSizeMustRemain8Bytes[
    sizeof(OverworldWildSurfaceHit) == 8 ? 1 : -1];
typedef char OverworldWildSurfaceBlockCacheSizeMustRemain8Bytes[
    sizeof(OverworldWildSurfaceBlockCache) == 8 ? 1 : -1];

typedef struct OverworldWildBehaviorDataBlob {
    OverworldWildBehaviorDataBlobHeader header;
    OverworldWildBehaviorProfileData classProfiles[OWBD_CLASS_PROFILE_COUNT];
    OverworldWildBehaviorClassRule classRules[OWBD_CLASS_RULE_COUNT];
    OverworldWildBehaviorSpeciesClassRule speciesClassRules[OWBD_SPECIES_CLASS_RULE_COUNT];
    OverworldWildBehaviorOverrideProfile overrideProfiles[OWBD_OVERRIDE_PROFILE_COUNT];
    u16 overrideMembers[OWBD_OVERRIDE_MEMBER_COUNT];
    OverworldWildBehaviorConditionalState
        conditionalStates[OWBD_CONDITIONAL_STATE_STORAGE_COUNT];
    OverworldWildSurfaceModelDirectoryEntry surfaceModels[OWBD_SURFACE_MODEL_COUNT];
    OverworldWildSurfaceInstance surfaceInstances[OWBD_SURFACE_INSTANCE_COUNT];
    OverworldWildSurfaceTemplate surfaceTemplates[OWBD_SURFACE_TEMPLATE_COUNT];
#if OWBD_SURFACE_CATALOG_PADDING_SIZE != 0
    u8 surfacePadding[OWBD_SURFACE_CATALOG_PADDING_SIZE];
#endif
} OverworldWildBehaviorDataBlob;

typedef struct OverworldWildEncounterLookupDataBlobHeader {
    u32 magic;
    u16 version;
    u16 headerSize;
    u16 recordCount;
    u16 directoryEntrySize;
    u32 directoryOffset;
    u32 payloadOffset;
    u32 totalSize;
    u32 checksum;
    u32 flags;
} OverworldWildEncounterLookupDataBlobHeader;

typedef struct OverworldWildEncounterLookupDirectoryEntry {
    u16 mapId;
    u16 dataId;
    u32 offset;
    u16 size;
    u16 flags;
} OverworldWildEncounterLookupDirectoryEntry;

typedef struct OverworldWildEncounterLookupDataEntry {
    const u16 *mapIds;
    const u8 *dataIds;
    u16 count;
} OverworldWildEncounterLookupDataEntry;

typedef BOOL (*OverworldWildValidateBehaviorOverlayFunc)(void);
typedef void (*OverworldWildCleanupBehaviorOverlayFunc)(void);

typedef struct OverworldWildBehaviorOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
} OverworldWildBehaviorOverlayEntry;

typedef const OverworldWildSurfaceInstance *(*OverworldWildQuerySurfaceFunc)(
    const OverworldWildSurfaceInstance *instances,
    const OverworldWildSurfaceTemplate *templates,
    u32 instanceCount,
    u32 packedLocalCoordinates);
typedef u32 (*OverworldWildCalculateJumpTrajectoryFunc)(
    u8 framesPerTile,
    u8 distance,
    s32 elevationDelta,
    u16 packedElevationScales);
typedef s32 (*OverworldWildCalculateJumpArcFunc)(
    u16 elapsedFrames,
    u16 totalFrames,
    u8 arcHeightQ4);
typedef struct OverworldWildSurfaceServiceEntry {
    OverworldWildQuerySurfaceFunc query;
    OverworldWildCalculateJumpTrajectoryFunc calculateJumpTrajectory;
    OverworldWildCalculateJumpArcFunc calculateJumpArc;
} OverworldWildSurfaceServiceEntry;

typedef void *(*OverworldWildCreateCustomJumpShadowEffectFunc)(
    void *effectContext,
    void *object);
typedef void (*OverworldWildClearCustomJumpShadowEffectFunc)(void);

typedef struct OverworldWildCustomJumpShadowEntry {
    OverworldWildCreateCustomJumpShadowEffectFunc create;
    OverworldWildClearCustomJumpShadowEffectFunc clear;
} OverworldWildCustomJumpShadowEntry;

typedef u8 (*OverworldWildGetPlayerBallCatchValueFunc)(u8 catchRate);
typedef u8 (*OverworldWildCalculatePlayerBallShakesFunc)(u8 catchValue);
typedef u32 (*OverworldWildFinalizeSpawnPersonalityFunc)(
    u32 personality,
    u32 trainerId,
    BOOL shiny);
typedef int (*OverworldWildFindCapturedPokemonDestinationFunc)(
    FieldSystem *fieldSystem);
typedef int (*OverworldWildFindBattleTalkSlotFunc)(
    FieldSystem *fieldSystem,
    struct OverworldWildSpawnState *state,
    struct LocalMapObject *talkedObject,
    u16 excludedMask);

typedef struct OverworldWildCaptureUtilitiesEntry {
    OverworldWildGetPlayerBallCatchValueFunc getCatchValue;
    OverworldWildCalculatePlayerBallShakesFunc calculateShakes;
    OverworldWildFinalizeSpawnPersonalityFunc finalizePersonality;
    OverworldWildFindCapturedPokemonDestinationFunc findDestination;
    OverworldWildFindBattleTalkSlotFunc findBattleTalkSlot;
} OverworldWildCaptureUtilitiesEntry;

typedef struct OverworldWildSpawnMetadata {
    u16 spriteId;
    u16 followerParam;
    u8 type1;
    u8 type2;
    u8 catchValue;
    u8 renderModePlusOne;
} OverworldWildSpawnMetadata;

typedef struct OverworldWildSpawnMetadataException {
    u16 species;
    u8 form;
    u8 reserved;
    OverworldWildSpawnMetadata metadata;
} OverworldWildSpawnMetadataException;

typedef struct OverworldWildSpawnMetadataBlobHeader {
    u32 magic;
    u16 version;
    u16 headerSize;
    u32 totalSize;
    u32 baseOffset;
    u16 baseCount;
    u16 baseRecordSize;
    u32 exceptionsOffset;
    u16 exceptionCount;
    u16 exceptionRecordSize;
    u16 formSpeciesBaseCount;
    u16 flags;
    u32 checksum;
} OverworldWildSpawnMetadataBlobHeader;

typedef BOOL (*OverworldWildTryGetSpawnMetadataFunc)(
    u16 species,
    u8 form,
    OverworldWildSpawnMetadata *metadata);
typedef void (*OverworldWildCleanupSpawnMetadataFunc)(void);
typedef u32 (*OverworldWildGetSpawnSpriteIdFunc)(u16 species, u8 form);
typedef void (*OverworldWildApplySpawnRenderParamsFunc)(
    struct LocalMapObject *object,
    u16 species,
    u8 form,
    u32 spriteId,
    BOOL shiny);
typedef struct OverworldWildSpawnMetadataOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildTryGetSpawnMetadataFunc tryGet;
    OverworldWildCleanupSpawnMetadataFunc cleanup;
    OverworldWildGetSpawnSpriteIdFunc getSpriteId;
    OverworldWildApplySpawnRenderParamsFunc applyRenderParams;
} OverworldWildSpawnMetadataOverlayEntry;

typedef void (*OverworldWildLoadLevelUpLearnsetFunc)(
    int species,
    int form,
    u32 *levelUpLearnset);
typedef BOOL (*OverworldWildWarmLevelUpLearnsetCacheFunc)(void);
typedef struct OverworldWildLearnsetCacheOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildLoadLevelUpLearnsetFunc load;
    OverworldWildWarmLevelUpLearnsetCacheFunc warm;
} OverworldWildLearnsetCacheOverlayEntry;

typedef BOOL (*OverworldWildQueryPickupThrowTargetFunc)(
    struct OverworldWildSpawnState *state,
    struct OverworldWildThrowState *throwState,
    int carrierSlot,
    int targetSlot,
    u8 query,
    u16 unstableMask);
typedef BOOL (*OverworldWildStartSpawnerMovementFunc)(
    struct OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const u8 *directions,
    int directionCount,
    const OverworldWildBehaviorProfile *profile,
    const struct OverworldWildBehaviorPrimitives *primitives);
typedef BOOL (*OverworldWildTryResolveOverlapFunc)(
    struct OverworldWildSpawnState *state,
    struct OverworldWildThrowState *throwState,
    u16 unstableMask,
    OverworldWildQueryPickupThrowTargetFunc queryTarget,
    OverworldWildStartSpawnerMovementFunc startMovement);
typedef struct OverworldWildOverlapResolverEntry {
    OverworldWildTryResolveOverlapFunc tryResolve;
} OverworldWildOverlapResolverEntry;

typedef u32 (*OverworldWildGetPersonalParamFunc)(int species, int parameter);
typedef struct OverworldWildPersonalCacheOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildGetPersonalParamFunc getParam;
} OverworldWildPersonalCacheOverlayEntry;

#define gOverworldWildLevelUpLearnsetLoader \
    (*(volatile OverworldWildLoadLevelUpLearnsetFunc *) \
        OVERWORLD_WILD_LEVELUP_LEARNSET_DISPATCH_SLOT_ADDR)
#define gOverworldWildPersonalParamLoader \
    (*(volatile OverworldWildGetPersonalParamFunc *) \
        OVERWORLD_WILD_PERSONAL_PARAM_DISPATCH_SLOT_ADDR)

#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_ENTRY \
    ((const OverworldWildBehaviorOverlayEntry *)OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR)
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE \
    ((OverworldWildValidateBehaviorOverlayFunc)OVERWORLD_WILD_BEHAVIOR_OVERLAY_VALIDATE_ADDR)
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_CLEANUP \
    ((OverworldWildCleanupBehaviorOverlayFunc)OVERWORLD_WILD_BEHAVIOR_OVERLAY_CLEANUP_ADDR)
#define OVERWORLD_WILD_LEGACY_ENCOUNTER_LOOKUP_ENTRY \
    ((const OverworldWildEncounterLookupDataEntry *)(OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR \
        + sizeof(OverworldWildBehaviorOverlayEntry)))
#define OVERWORLD_WILD_CUSTOM_JUMP_SHADOW_ENTRY \
    ((const OverworldWildCustomJumpShadowEntry *)(OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR \
        + sizeof(OverworldWildBehaviorOverlayEntry) \
        + sizeof(OverworldWildEncounterLookupDataEntry)))
#define OVERWORLD_WILD_CAPTURE_UTILITIES_ENTRY \
    ((const OverworldWildCaptureUtilitiesEntry *)(OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR \
        + sizeof(OverworldWildBehaviorOverlayEntry) \
        + sizeof(OverworldWildEncounterLookupDataEntry) \
        + sizeof(OverworldWildCustomJumpShadowEntry)))
#define OVERWORLD_WILD_SPAWN_METADATA_ENTRY \
    ((const OverworldWildSpawnMetadataOverlayEntry *)(OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR \
        + sizeof(OverworldWildBehaviorOverlayEntry) \
        + sizeof(OverworldWildEncounterLookupDataEntry) \
        + sizeof(OverworldWildCustomJumpShadowEntry) \
        + sizeof(OverworldWildCaptureUtilitiesEntry)))
#define OVERWORLD_WILD_LEARNSET_CACHE_ENTRY \
    ((const OverworldWildLearnsetCacheOverlayEntry *)(OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR \
        + sizeof(OverworldWildBehaviorOverlayEntry) \
        + sizeof(OverworldWildEncounterLookupDataEntry) \
        + sizeof(OverworldWildCustomJumpShadowEntry) \
        + sizeof(OverworldWildCaptureUtilitiesEntry) \
        + sizeof(OverworldWildSpawnMetadataOverlayEntry)))
#define OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY \
    ((const OverworldWildOverlapResolverEntry *) \
        OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY_ADDR)
#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY \
    ((const OverworldWildSurfaceServiceEntry *) \
        OVERWORLD_WILD_SURFACE_SERVICE_ENTRY_ADDR)
#define OVERWORLD_WILD_PERSONAL_CACHE_ENTRY \
    ((const OverworldWildPersonalCacheOverlayEntry *) \
        OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR)

#endif // OVERWORLD_WILD_BEHAVIOR_DATA_H
