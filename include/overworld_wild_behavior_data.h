#ifndef OVERWORLD_WILD_BEHAVIOR_DATA_H
#define OVERWORLD_WILD_BEHAVIOR_DATA_H

#include "types.h"
#include "overworld_vision.h"
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
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION 13
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC 0x4F574244
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 95
#define OVERWORLD_WILD_BEHAVIOR_SEMANTIC_VERSION 95
#define OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_MAGIC 0x4F574544
#define OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_VERSION 2
#define OVERWORLD_WILD_SPAWN_METADATA_MAGIC 0x4F57534D
#define OVERWORLD_WILD_SPAWN_METADATA_VERSION 3
/* Shared runtime/build allocation bound; v3 records exceed the old16KiB cap. */
#define OVERWORLD_WILD_SPAWN_METADATA_MAX_BLOB_SIZE 0x8000
/* The behavior catalog uses FIELD1 (heap 4), and the larger Query add-on uses
 * HEAPID_WORLD. A field rebuilt after a battle leaves FIELD1 fragmented below
 * the add-on's size, while HEAPID_WORLD survives battles intact. The smaller
 * metadata cache stays on the default heap. */
#define OVERWORLD_WILD_BEHAVIOR_DATA_HEAP_ID 4
#define OVERWORLD_WILD_SPAWN_METADATA_HEAP_ID HEAPID_DEFAULT
#define OVERWORLD_WILD_SPAWN_METADATA_OVERLAY_MAGIC 0x4F57534F
#define OVERWORLD_WILD_SPAWN_METADATA_OVERLAY_VERSION 3
#define OVERWORLD_WILD_LEARNSET_CACHE_OVERLAY_MAGIC 0x4F574C43
#define OVERWORLD_WILD_LEARNSET_CACHE_OVERLAY_VERSION 1
#define OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_MAGIC 0x4F575043
#define OVERWORLD_WILD_PERSONAL_CACHE_OVERLAY_VERSION 1
#define OVERWORLD_WILD_LEVELUP_LEARNSET_DISPATCH_SLOT_ADDR 0x02071FD8
#define OVERWORLD_WILD_PERSONAL_PARAM_DISPATCH_SLOT_ADDR 0x0206FBEC
#define OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR 0x023C30E0
#define OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY_ADDR 0x023C30EC
#define OVERWORLD_WILD_SURFACE_SERVICE_ENTRY_ADDR 0x023C30F0
#define OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM 31
#define OW_WILD_BEHAVIOR_CLASS_DEFAULT 0
#define OW_WILD_BEHAVIOR_CLASS_ROOFTOP_ACCESS 1
#define OWBD_CLASS_PROFILE_COUNT 2
#define OWBD_CLASS_RULE_COUNT 2
#define OWBD_SPECIES_CLASS_RULE_COUNT 115
#define OWBD_OVERRIDE_PROFILE_COUNT 38
#define OWBD_MASKABLE_APPLICATION_COUNT 32
#define OWBD_APPLICATION_BANK_DIRECTORY_COUNT 333
#define OWBD_APPLICATION_BANK_INDEX_COUNT 1612
#define OWBD_CONDITION_ENTRY_COUNT 26
#define OWBD_CONDITION_ENTRY_STORAGE_COUNT \
    ((OWBD_CONDITION_ENTRY_COUNT) ? OWBD_CONDITION_ENTRY_COUNT : 1)
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_REST 11
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER 17
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED 36
/* Global IDs are separate from each subject's32 local mask slots. */
typedef char OverworldWildBehaviorOverrideProfileCountMustFitLinkedTable[
    OWBD_OVERRIDE_PROFILE_COUNT <= 65534 ? 1 : -1];
typedef char OverworldWildBehaviorConditionEntryCountMustFitRuntimeState[
    OWBD_CONDITION_ENTRY_COUNT <= 65535 ? 1 : -1];
#define OWBD_OVERRIDE_MEMBER_COUNT 745
#define OWBD_SURFACE_MODEL_COUNT OWBD_GENERATED_SURFACE_MODEL_COUNT
#define OWBD_SURFACE_INSTANCE_COUNT OWBD_GENERATED_SURFACE_INSTANCE_COUNT
#define OWBD_SURFACE_TEMPLATE_COUNT OWBD_GENERATED_SURFACE_TEMPLATE_COUNT
#define OWBD_SURFACE_CATALOG_RAW_SIZE \
    (OWBD_SURFACE_MODEL_COUNT * 6 + OWBD_SURFACE_INSTANCE_COUNT * 8 \
        + OWBD_SURFACE_TEMPLATE_COUNT * 2)
/* Condition entries restore four-byte alignment after the u16 member table.
 * Only the packed surface catalog size can require trailing blob padding. */
#define OWBD_SURFACE_CATALOG_PADDING_SIZE \
    ((4 - (OWBD_SURFACE_CATALOG_RAW_SIZE & 3)) & 3)
#define OW_WILD_ROOF_HEIGHT_QUANTUM_SHIFT 4
#define OW_WILD_MAP_BLOCK_SHIFT 5
#define OW_WILD_MAP_BLOCK_MASK 31
#define OW_WILD_MAP_MATRIX_HEADERS_OFFSET 0x6
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
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST (1u << 4)
/* Decode existing authoring data without changing its serialized bit. */
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER \
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_OBJECT_OF_INTEREST
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT (1u << 5)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP      (1u << 6)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST     (1u << 7)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX      (1u << 8)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_FLOWERBED    (1u << 9)
/* Presentation only: the body stays on top of deep water instead of sinking
 * into it. WATER still grants access; tile matching ignores this bit. */
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER_SURFACE (1u << 10)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_FIRST \
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL \
    (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ROOFTOP \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SIGNPOST \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_MAILBOX \
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_FLOWERBED)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL          0x03FF
/* Every stored Allowed-terrain policy bit, including presentation-only
 * Water surface. Tile matching and destinations use ALL. */
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_POLICY_ALL   0x07FF
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT      OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND

#define OW_WILD_SURFACE_TYPE_ROOFTOP 0
#define OW_WILD_SURFACE_TYPE_SIGNPOST 1
#define OW_WILD_SURFACE_TYPE_MAILBOX 2
#define OW_WILD_SURFACE_TYPE_FLOWERBED 3
#define OW_WILD_SURFACE_TYPE_CANOPY 4
#define OW_WILD_SURFACE_TYPE_COUNT 5
#define OW_WILD_SURFACE_HEIGHT_PAGE_NATIVE_GROUND 0x1F
#define OW_WILD_SURFACE_ID_NATIVE_CANOPY 0xFFFE
#define OW_WILD_SURFACE_ID_NATIVE_GROUND 0xFFFF
#define OW_WILD_SURFACE_TYPE_TERRAIN_MASK(surfaceType) \
    ((surfaceType) == OW_WILD_SURFACE_TYPE_CANOPY \
        ? OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY \
        : OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_FIRST << (surfaceType))

#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_FRONT  (1u << 0)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_BEHIND (1u << 1)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_LEFT   (1u << 2)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_RIGHT  (1u << 3)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL   0xFu
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL

#define OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN 4

#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND 2
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS 3
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS 4
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE 6
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD 7
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE (1u << 7)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE(action) \
    (1u << ((action) - 1u))
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_HOP_IN_PLACE (1u << 0)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_LOOK_AROUND (1u << 1)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_REPOSITION_JUMPS (1u << 2)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_REPOSITION_STEPS (1u << 3)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_REPOSITION_SKIDS (1u << 4)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE (1u << 5)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_HOP_FORWARD (1u << 6)
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_MASK \
    (OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_HOP_IN_PLACE \
        | OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_LOOK_AROUND \
        | OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_REPOSITION_JUMPS \
        | OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_REPOSITION_STEPS \
        | OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_REPOSITION_SKIDS \
        | OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_PAUSE \
        | OW_WILD_BEHAVIOR_CHAIN_PAUSE_CHOICE_HOP_FORWARD)
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMPS_DEFAULT 3
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMPS_MAX 8
#define OW_WILD_BEHAVIOR_WALK_TIME_MIN 1
#define OW_WILD_BEHAVIOR_WALK_TIME_MAX 32
#define OW_WILD_BEHAVIOR_WALK_TIME_DEFAULT 16
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_SPEED_DEFAULT 16
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_SPEED_MAX 32
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DISTANCE_DEFAULT 1
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DISTANCE_MAX 5
#define OW_WILD_BEHAVIOR_TILES_TO_ACCELERATE_DEFAULT 3
#define OW_WILD_BEHAVIOR_MAX_WALK_SPEED_DEFAULT 2
#define OW_WILD_BEHAVIOR_WALK_ACCELERATION_NONE 0
#define OW_WILD_BEHAVIOR_WALK_ACCELERATION_DIVIDE_BY_2 33
#define OW_WILD_BEHAVIOR_WALK_ACCELERATION_STEP_DEFAULT 1
#define OW_WILD_BEHAVIOR_WALK_PAUSE_DEFAULT 32
#define OW_WILD_BEHAVIOR_TURN_SKID_BUILDUP_DEFAULT 1
#define OW_WILD_BEHAVIOR_TURN_SKIDS_DISABLED 0
#define OW_WILD_BEHAVIOR_LOCOMOTION_WALK 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT 6
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_NO_FLICKER 9
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE 10
#define OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT_PER_TILE_NO_FLICKER 11
#define OW_WILD_BEHAVIOR_LOCOMOTION_FLUTTER OW_WILD_BEHAVIOR_LOCOMOTION_HOP
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
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT 4
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK (1u << OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_OPTION_DISABLE_ACCELERATION (1u << 5)
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY 0
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_AND_DIAGONAL 1
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY 2
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_MAX \
    OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY
#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTION_MASK 0x03
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK 0x01
#define OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_SHIFT 1
#define OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MASK 0xFE
#define OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MAX 32
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_CARDINAL_OPTIONS(allowCardinal, walkPauseVariance) \
    (((allowCardinal) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK) \
        | (((walkPauseVariance) << OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MASK))
#define OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MASK) \
        >> OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_SHIFT)
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOWS_CARDINAL(options) \
    ((options) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK)
#define OW_WILD_BEHAVIOR_SET_CHAIN_REPOSITION_ALLOW_CARDINAL(options, allowCardinal) \
    ((options) = ((options) & OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MASK) \
        | ((allowCardinal) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK))
#define OW_WILD_BEHAVIOR_SET_WALK_PAUSE_VARIANCE(options, walkPauseVariance) \
    ((options) = ((options) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK) \
        | (((walkPauseVariance) << OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MASK))
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_DIAGONAL_MASK 0x01
#define OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_SHIFT 1
#define OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MASK 0xFE
#define OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MAX 32
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_DIAGONAL_OPTIONS(allowDiagonal, walkTimeVariance) \
    (((allowDiagonal) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_DIAGONAL_MASK) \
        | (((walkTimeVariance) << OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MASK))
#define OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MASK) \
        >> OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_SHIFT)
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOWS_DIAGONAL(options) \
    ((options) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_DIAGONAL_MASK)
#define OW_WILD_BEHAVIOR_SET_CHAIN_REPOSITION_ALLOW_DIAGONAL(options, allowDiagonal) \
    ((options) = ((options) & OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MASK) \
        | ((allowDiagonal) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_DIAGONAL_MASK))
#define OW_WILD_BEHAVIOR_SET_WALK_TIME_VARIANCE(options, walkTimeVariance) \
    ((options) = ((options) & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_DIAGONAL_MASK) \
        | (((walkTimeVariance) << OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MASK))
#define OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID_MASK 0x3F
#define OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_SHIFT 6
#define OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_MASK \
    (1u << OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_SHIFT)
#define OW_WILD_BEHAVIOR_STOP_SKID_SHIFT 7
#define OW_WILD_BEHAVIOR_STOP_SKID_MASK \
    (1u << OW_WILD_BEHAVIOR_STOP_SKID_SHIFT)
#define OW_WILD_BEHAVIOR_TURN_SKID_OPTIONS(tilesBeforeTurnSkid, planTurnSkidPath, stopSkid) \
    (((tilesBeforeTurnSkid) & OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID_MASK) \
        | (((planTurnSkidPath) << OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_SHIFT) \
            & OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_MASK) \
        | (((stopSkid) << OW_WILD_BEHAVIOR_STOP_SKID_SHIFT) \
            & OW_WILD_BEHAVIOR_STOP_SKID_MASK))
#define OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(options) \
    ((options) & OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID_MASK)
#define OW_WILD_BEHAVIOR_PLANS_TURN_SKID_PATH(options) \
    (((options) & OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_MASK) != 0)
#define OW_WILD_BEHAVIOR_STOPS_WITH_SKID(options) \
    (((options) & OW_WILD_BEHAVIOR_STOP_SKID_MASK) != 0)
#define OW_WILD_BEHAVIOR_SET_TILES_BEFORE_TURN_SKID(options, tilesBeforeTurnSkid) \
    ((options) = ((options) & (OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_MASK \
            | OW_WILD_BEHAVIOR_STOP_SKID_MASK)) \
        | ((tilesBeforeTurnSkid) & OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID_MASK))
#define OW_WILD_BEHAVIOR_SET_PLAN_TURN_SKID_PATH(options, planTurnSkidPath) \
    ((options) = ((options) & (OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID_MASK \
            | OW_WILD_BEHAVIOR_STOP_SKID_MASK)) \
        | (((planTurnSkidPath) << OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_SHIFT) \
            & OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_MASK))
#define OW_WILD_BEHAVIOR_SET_STOP_SKID(options, stopSkid) \
    ((options) = ((options) & (OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID_MASK \
            | OW_WILD_BEHAVIOR_PLAN_TURN_SKID_PATH_MASK)) \
        | (((stopSkid) << OW_WILD_BEHAVIOR_STOP_SKID_SHIFT) \
            & OW_WILD_BEHAVIOR_STOP_SKID_MASK))
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(mode) \
    ((mode) < OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_DIAGONAL_ONLY)
#define OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode) \
    ((mode) != OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY)
#define OW_WILD_BEHAVIOR_WALK_OPTION_FACE_PLAYER (1u << 6)
#define OW_WILD_BEHAVIOR_WALK_OPTION_FIXED_FACING (1u << 7)
#define OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_SHIFT 1
#define OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_MASK \
    (7u << OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_MAX 7
#define OW_WILD_BEHAVIOR_WALK_OPTIONS_RESERVED_MASK 0x00
#define OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) == 0)
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK) \
        >> OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_DISABLES_ACCELERATION(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_OPTION_DISABLE_ACCELERATION) != 0)
#define OW_WILD_BEHAVIOR_WALK_USES_FIXED_FACING(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_OPTION_FIXED_FACING) != 0)
#define OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_OPTION_FACE_PLAYER) != 0)
#define OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH(options) \
    (((options) & OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_MASK) \
        >> OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH_SHIFT)
#define OW_WILD_BEHAVIOR_WALK_PRESERVES_FACING(options) \
    (((options) & (OW_WILD_BEHAVIOR_WALK_OPTION_FACE_PLAYER \
        | OW_WILD_BEHAVIOR_WALK_OPTION_FIXED_FACING)) != 0)
#define OW_WILD_BEHAVIOR_WALK_OPTIONS(lockDirection, crashSound) \
    (((lockDirection) ? OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION : 0) \
        | (((crashSound) << OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_SHIFT) \
            & OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MASK))
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_NONE 0
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT 1
#define OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_MAX \
    OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT
#define OW_WILD_BEHAVIOR_HOP_SWAY_WIDTH_MAX 8
#define OW_WILD_BEHAVIOR_JUMP_ARC_HEIGHT_MIN_Q4 16

/* Byte 42 packs autonomous movement and pre-pickup Cargo target selection. */
#define OW_WILD_BEHAVIOR_CONTROLLER_OPTIONS(continueWhenArrived, returnAfterMove) \
    (((continueWhenArrived) & 1u) | (((returnAfterMove) & 1u) << 1))
#define OW_WILD_BEHAVIOR_CONTINUES_WHEN_ARRIVED(options) ((options) & 1u)
#define OW_WILD_BEHAVIOR_RETURNS_AFTER_MOVE(options) (((options) >> 1) & 1u)
#define OW_WILD_BEHAVIOR_CARGO_TARGET_CHECK_INTERVAL(options) (((options) >> 2) & 15u)
#define OW_WILD_BEHAVIOR_CARGO_TARGET_SWITCH_ADVANTAGE(options) ((options) >> 6)
#define OW_WILD_BEHAVIOR_CONTROLLER_CARGO_OPTIONS(continueWhenArrived, returnAfterMove, interval, advantage) \
    (OW_WILD_BEHAVIOR_CONTROLLER_OPTIONS(continueWhenArrived, returnAfterMove) \
        | (((interval) & 15u) << 2) | (((advantage) & 3u) << 6))

/* Byte 43 retains previous-tile permission in bit 0. Byte 57 retains
 * the Reposition count in bits 0..3. Extra Hop in place rolls are separate
 * from the pause-action admission roll and use only the high slices. */
#define OW_WILD_BEHAVIOR_AVOIDS_PREVIOUS_TILE(options) ((options) & 1u)
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMP_COUNT(options) ((options) & 15u)
#define OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_EXTRA_HOPS(options) (((options) >> 4) & 3u)
#define OW_WILD_BEHAVIOR_HOP_EFFECT_CHANCE_OFF 0
#define OW_WILD_BEHAVIOR_HOP_EFFECT_CHANCE_25 1
#define OW_WILD_BEHAVIOR_HOP_EFFECT_CHANCE_50 2
#define OW_WILD_BEHAVIOR_HOP_EFFECT_CHANCE_100 3
#define OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_HEART_CHANCE(options) ((options) >> 6)
#define OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_CRY_CHANCE(options) ((options) >> 6)
#define OW_WILD_BEHAVIOR_ON_REACH_ACTION(options) ((options) & 1u)
#define OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_EXTRA_CHANCE(options) ((options) >> 1)
#define OW_WILD_BEHAVIOR_PREVIOUS_TILE_HOP_OPTIONS(avoidPreviousTile, chance) \
    (((avoidPreviousTile) & 1u) | (((chance) & 127u) << 1))
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_OPTIONS(repositionCount, extraHops) \
    (((repositionCount) & 15u) | (((extraHops) & 3u) << 4))
#define OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_EFFECT_OPTIONS(repositionCount, extraHops, heartChance) \
    (OW_WILD_BEHAVIOR_CHAIN_REPOSITION_HOP_OPTIONS(repositionCount, extraHops) \
        | (((heartChance) & 3u) << 6))
#define OW_WILD_BEHAVIOR_ON_REACH_HOP_OPTIONS(onReachAction, cryChance) \
    (((onReachAction) & 1u) | (((cryChance) & 3u) << 6))
#define OW_WILD_BEHAVIOR_SET_CHAIN_REPOSITION_JUMP_COUNT(options, count) \
    ((options) = ((options) & 0xF0u) | ((count) & 15u))
#define OW_WILD_BEHAVIOR_SET_CHAIN_HOP_IN_PLACE_EXTRA_HOPS(options, count) \
    ((options) = ((options) & ~0x30u) | (((count) & 3u) << 4))
#define OW_WILD_BEHAVIOR_SET_CHAIN_HOP_IN_PLACE_EXTRA_CHANCE(options, chance) \
    ((options) = ((options) & 1u) | (((chance) & 127u) << 1))

/* Mounted Walk presentation only. Each control inherits independently.
 * Stride codes 0..3 mean 16, 32, 48, or 64 pixels travelled per cycle. */
#define OW_WILD_BEHAVIOR_MOUNT_GAIT_OPTIONS(bounce, stride, settle, lean) \
    (((bounce) & 3u) | (((stride) & 3u) << 2) \
        | (((settle) & 3u) << 4) | (((lean) & 3u) << 6))
#define OW_WILD_BEHAVIOR_MOUNT_BOUNCE(options) ((options) & 3u)
#define OW_WILD_BEHAVIOR_MOUNT_STRIDE(options) (((options) >> 2) & 3u)
#define OW_WILD_BEHAVIOR_MOUNT_SETTLE(options) (((options) >> 4) & 3u)
#define OW_WILD_BEHAVIOR_MOUNT_LEAN(options) (((options) >> 6) & 3u)

/* Skid thresholds use displayed frames per tile: zero is Off, 1..127 is
 * the slowest admitted time. Packed booleans retain their independent low bit. */
#define OW_WILD_BEHAVIOR_SKID_BOOLEAN(options) ((options) & 1u)
#define OW_WILD_BEHAVIOR_SKID_THRESHOLD(options) ((options) >> 1)
#define OW_WILD_BEHAVIOR_SKID_OPTIONS(enabled, threshold) \
    (((enabled) & 1u) | (((threshold) & 127u) << 1))
#define OW_WILD_BEHAVIOR_TURN_SKID_ONE_TIME(profile) ((profile)->range)
#define OW_WILD_BEHAVIOR_TURN_SKID_TWO_TIME(profile) \
    OW_WILD_BEHAVIOR_SKID_THRESHOLD((profile)->hopAllowVerticalObstacles)
#define OW_WILD_BEHAVIOR_STOP_SKID_TIME(profile) \
    OW_WILD_BEHAVIOR_SKID_THRESHOLD((profile)->chainRepositionDust)

/* Compact blob representation. The Tired runtime lane is composed from the
 * Owner lane of the referenced override profile. Mounted gait reuses byte 16
 * so existing movement fields keep their 72-byte storage layout and offsets. */
typedef struct OverworldWildBehaviorProfileData {
    u8 chillState;
    u8 visionRange;
    u8 alertEmote;
    u8 alertTime;
    u8 visionCone;
    u8 stamina;
    u8 restTime;
    u8 chillSpeed;
    u8 range; /* turnSkidOneTime storage; native movement axes stay signed -1. */
    u8 jumpLevel;
    u8 profileId;
    u8 spawnState;
    u8 chillAction;
    u8 chillTarget;
    u8 visionAdjacentAwareness;
    u8 playerAdjacentDirectionMasks;
    u8 mountBounce; /* Packed mounted gait controls; use the getters above. */
    u8 spawnDestination;
    u8 battleTrigger;
    /* Low two bits select cardinal/diagonal movement. High six bits store
     * the independent 0..32 Walk travel-time variance. */
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
    /* One action ID, or RANDOM_CHOICE plus a bit set of eligible actions. */
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
    u8 continueWhenArrived; /* Packed movement/Cargo controls; use the getters above. */
    u8 avoidPreviousTile; /* Packed previous-tile/Hop controls; use getters. */
    u8 chainMovementVariance;
    u8 chainPauseVariance;
    u8 walkSwayWidth;
    u8 tiredProfile;
    u8 hopElevationTimeScale;
    u8 hopElevationArcScale;
    /* Legacy tiles per event, or moving frames to full speed in Linear mode. */
    u8 tilesToAccelerate;
    u8 maxWalkSpeed;
    /* Spawn placement uses the same option bits as allowed terrain, but its
     * value/inheritance policy is stored and resolved independently. */
    u16 spawnDestinationMask;
    u16 spawnDestinationOverrideMask;
    u8 hopAllowVerticalObstacles;
    u8 chainRepositionJumpCount; /* Packed Reposition/Hop counts; use getters. */
    u8 hopSwayWidth;
    u8 spawnHopSwayWidth;
    u8 chainRepositionSpeed;
    u8 chainRepositionDistance;
    u8 chainRepositionDust;
    /* Cardinal permission plus Walk pause variance in the high seven bits. */
    u8 chainRepositionAllowCardinal;
    u8 chainRepositionAllowDiagonal;
    /* Turning, effects, and presentation options for Walk movement. */
    u8 walkOptions;
    /* Exact percent chance to continue the previous random Wander direction. */
    u8 wanderStraightChance;
    /* Overall chance to admit one configured action. Zero preserves legacy
     * data and means that an action always runs. */
    u8 chainPauseActionChance;
    /* Frames to pause after each completed normal Walk step. */
    u8 walkPause;
    /* Low six bits: required Walk steps before a turn skid. Bit 6 is legacy
     * path metadata; it cannot veto a skid. High bit selects lifecycle stop
     * skids. Every skid travels clear tiles, then crashes at its first blocker. */
    u8 tilesBeforeTurnSkid;
    /* Zero disables stomp; otherwise stomp at this travel time or faster. */
    u8 walkStompTime;
    /* 0 disables; 1..32 remove frames; 33 halves time; 34 is Linear speed. */
    u8 walkAccelerationStep;
    /* A resolved attacking profile permits player-contact damage when the
     * moving body meets minImpactSpeed / 256 tiles per field frame. */
    u8 attacking;
    u8 minImpactSpeed;
    u8 collisionDamage;
    u8 onReachAction;
    u8 throwMaxRange;
    u8 throwWindupFrames;
    u8 throwRecoveryFrames;
    /* Low two bits select None, Slide, or Jump. High six bits hold tiles. */
    u8 knockbackOptions;
} OverworldWildBehaviorProfileData;

typedef char OverworldWildBehaviorProfileDataSizeMustRemain80Bytes[
    sizeof(OverworldWildBehaviorProfileData) == 80 ? 1 : -1];

/* Runtime composite. Its prefix intentionally matches the compact blob so the
 * owner Chill lane can be copied directly before linked state lanes are added. */
typedef struct OverworldWildBehaviorProfile {
    union {
        OverworldWildBehaviorProfileData owner;
        struct {
            u8 chillState;
            u8 visionRange;
            u8 alertEmote;
            u8 alertTime;
            u8 visionCone;
            u8 stamina;
            u8 restTime;
            u8 chillSpeed;
            u8 range; /* Reserved zero; native movement axes use signed -1. */
            u8 jumpLevel;
            u8 profileId;
            u8 spawnState;
            u8 chillAction;
            u8 chillTarget;
            u8 visionAdjacentAwareness;
            u8 playerAdjacentDirectionMasks;
            u8 mountBounce;
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
            u8 avoidPreviousTile; /* Packed previous-tile/Hop controls; use getters. */
            u8 chainMovementVariance;
            u8 chainPauseVariance;
            u8 walkSwayWidth;
            u8 tiredProfile;
            u8 hopElevationTimeScale;
            u8 hopElevationArcScale;
            u8 tilesToAccelerate;
            u8 maxWalkSpeed;
            u16 spawnDestinationMask;
            u16 spawnDestinationOverrideMask;
            u8 hopAllowVerticalObstacles;
            u8 chainRepositionJumpCount; /* Packed Reposition/Hop counts; use getters. */
            u8 hopSwayWidth;
            u8 spawnHopSwayWidth;
            u8 chainRepositionSpeed;
            u8 chainRepositionDistance;
            u8 chainRepositionDust;
            u8 chainRepositionAllowCardinal;
            u8 chainRepositionAllowDiagonal;
            u8 walkOptions;
            u8 wanderStraightChance;
            u8 chainPauseActionChance;
            u8 walkPause;
            u8 tilesBeforeTurnSkid;
            u8 walkStompTime;
            u8 walkAccelerationStep;
            u8 attacking;
            u8 minImpactSpeed;
            u8 collisionDamage;
            u8 onReachAction;
            u8 throwMaxRange;
            u8 throwWindupFrames;
            u8 throwRecoveryFrames;
            u8 knockbackOptions;
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
            u8 tiredWalkSwayWidth;
            u8 _tiredPad47;
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
            u8 tiredWanderStraightChance;
            u8 tiredChainPauseActionChance;
            u8 tiredWalkPause;
            u8 tiredTilesBeforeTurnSkid;
            u8 tiredWalkStompTime;
            u8 tiredWalkAccelerationStep;
            u8 tiredAttacking;
            u8 tiredMinImpactSpeed;
            u8 tiredCollisionDamage;
            u8 tiredOnReachAction;
            u8 tiredThrowMaxRange;
            u8 tiredThrowWindupFrames;
            u8 tiredThrowRecoveryFrames;
            u8 tiredKnockback;
        };
    };
} OverworldWildBehaviorProfile;

/* Mechanical actions resolved from the Owner and Tired behavior lanes. AI policy stays
 * in the profile; actor controllers may safely snapshot these primitives. */
typedef struct OverworldWildBehaviorPrimitives {
    u8 spawnLocomotion;
    u8 chillLocomotion;
    u8 chillTarget;
    u8 alertLogic;
    u8 alertReaction;
    u8 tiredLocomotion;
    u8 tiredTarget;
    u8 tiredReaction;
} OverworldWildBehaviorPrimitives;

typedef char OverworldWildBehaviorProfileSizeMustRemain160Bytes[
    sizeof(OverworldWildBehaviorProfile) == 160 ? 1 : -1];
typedef char OverworldWildBehaviorPrimitivesSizeMustRemain8Bytes[
    sizeof(OverworldWildBehaviorPrimitives) == 8 ? 1 : -1];

typedef struct OverworldWildBehaviorContext {
    u16 species;
    u16 reserved;
    u32 groupFlags;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 behaviorClass;
} OverworldWildBehaviorContext;

typedef char OverworldWildBehaviorContextSizeMustRemain12Bytes[
    sizeof(OverworldWildBehaviorContext) == 12 ? 1 : -1];

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
    u8 profileKind;
    u8 conditionStart;
    u8 conditionCount;
    u32 mask;
    u32 mask2;
    u32 mask3;
    OverworldWildBehaviorProfileData profile;
    u32 relativeMask;
    u32 relativeMask2;
    u32 relativeMask3;
    u32 atLeastMask;
    u32 atLeastMask2;
    u32 atLeastMask3;
    u32 atMostMask;
    u32 atMostMask2;
    u32 atMostMask3;
    /* Used only when a relative adjustment is followed by a bound. */
    OverworldWildBehaviorProfileData compoundBoundProfile;
} OverworldWildBehaviorOverrideProfile;

typedef char OverworldWildBehaviorOverrideProfileSizeMustRemain228Bytes[
    sizeof(OverworldWildBehaviorOverrideProfile) == 228 ? 1 : -1];

typedef struct OverworldWildBehaviorConditionEntry {
    OverworldWildBehaviorMatch subjectMatch;
    u32 targetGroupMask;
    u16 terrainMask;
    u16 terrainOverrideMask;
    u16 durationFrames;
    u16 cooldownFrames;
    u16 subjectMemberStart;
    u16 subjectMemberCount;
    u16 targetMemberStart;
    u16 targetMemberCount;
    u16 conditionId;
    u8 applicationIndex;
    u8 subjectMode;
    u8 subjectApplicationIndex;
    u8 kind;
    u8 activationMode;
    u8 targetKind;
    u8 targetRoleMask;
    u8 targetSelection;
    u8 rangeKind;
    u8 rangeLength;
    u8 chancePercent;
    u8 minMovementSpeed;
    u8 maxMovementSpeed;
} OverworldWildBehaviorConditionEntry;

typedef char OverworldWildBehaviorConditionEntrySizeMustRemain48Bytes[
    sizeof(OverworldWildBehaviorConditionEntry) == 48 ? 1 : -1];

/* Append-only condition options preserve every existing catalog section.
 * Capture values are0:none,1:Object of interest,2:Cargo. Uses values add3:Object of interest itself.
 * Roles use the ordinary role mask.
 * Pickup height is in native world units (one tile is16 world units). */
typedef struct OverworldWildBehaviorConditionOptions {
    u8 subjectRoleMask;
    u8 captureBinding;
    u8 bindingLifetime;
    u8 bindOnly;
    u16 bindingDurationFrames;
    u8 usesBinding;
    u8 mustBeReachableForPickup;
    u8 pickupDistance;
    u8 pickupHeight;
    u8 failureResponse;
    u8 retryFrames;
    /* Zero means no dependency; otherwise global application ID plus one.
     * The dependency must precede this condition's application. */
    u16 requiredApplication;
    u8 minTargetDistance;
    u8 maxTargetDistance;
    u8 boundTargetDistance;
    u8 reservedDependency;
} OverworldWildBehaviorConditionOptions;
typedef char OverworldWildBehaviorConditionOptionsMustRemain18[
    sizeof(OverworldWildBehaviorConditionOptions) == 18 ? 1 : -1];

#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED 0
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS 1
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL 2
#define OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL 0
#define OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL 1
#define OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR 12
#define OW_WILD_BEHAVIOR_TARGET_CONDITION_ACTOR 10
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_THROW_LINE 11
#define OW_WILD_BEHAVIOR_TARGET_CARGO 12
#define OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE 13
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE 14
#define OW_WILD_BEHAVIOR_ON_REACH_NONE 0
#define OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR 1
#define OW_WILD_BEHAVIOR_KNOCKBACK_NONE 0
#define OW_WILD_BEHAVIOR_KNOCKBACK_SLIDE 1
#define OW_WILD_BEHAVIOR_KNOCKBACK_JUMP 2
#define OW_WILD_BEHAVIOR_KNOCKBACK_TYPE_MASK 0x03
#define OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_SHIFT 2
#define OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_MASK 0x1C
#define OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(type, distance) \
    (((type) & OW_WILD_BEHAVIOR_KNOCKBACK_TYPE_MASK) \
        | (((distance) << OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_SHIFT) \
            & OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_MASK))
#define OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(options) \
    ((options) & OW_WILD_BEHAVIOR_KNOCKBACK_TYPE_MASK)
#define OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(options) \
    (((options) & OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_MASK) \
        >> OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_SHIFT)
#define OW_WILD_BEHAVIOR_SET_KNOCKBACK_TYPE(options, type) \
    ((options) = ((options) & ~OW_WILD_BEHAVIOR_KNOCKBACK_TYPE_MASK) \
        | ((type) & OW_WILD_BEHAVIOR_KNOCKBACK_TYPE_MASK))
#define OW_WILD_BEHAVIOR_SET_KNOCKBACK_DISTANCE(options, distance) \
    ((options) = ((options) & ~OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_MASK) \
        | (((distance) << OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_SHIFT) \
            & OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE_MASK))
/* Zero keeps the legacy all-recipient behavior. Roles are independent of
 * attack kind. Flight copies these options and restores its ground profile. */
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALL 0
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_PLAYER 1
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_WILD 2
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_PLAYER_AND_WILD 3
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALLIED 4
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_PLAYER_AND_ALLIED 5
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_POKEMON 6
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALL_EXPLICIT 7
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_MASK 0xE0
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(options) ((options) >> 5)
#define OW_WILD_BEHAVIOR_COLLISION_OPTIONS(type, distance, recipients) \
    (OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(type, distance) | (((recipients) & 7) << 5))
#define OW_WILD_BEHAVIOR_SET_DAMAGE_RECIPIENTS(options, recipients) \
    ((options) = ((options) & ~OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_MASK) \
        | (((recipients) & 7) << 5))
#define OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALLOWED(options, role) \
    (OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(options) == 0 \
        || (OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(options) & (role)) != 0)
#define OW_WILD_BEHAVIOR_CONDITION_SUBJECT_APPLICATION_NONE 0xFF
#define OW_WILD_BEHAVIOR_CONDITION_PLAYER_NOTICED 0
#define OW_WILD_BEHAVIOR_CONDITION_POKEMON_NOTICED 1
#define OW_WILD_BEHAVIOR_CONDITION_TERRAIN_SPEED 2
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_CANNOT_SEE_SUBJECT 3
#define OW_WILD_BEHAVIOR_CONDITION_ACTOR_FACTS 4
#define OW_WILD_BEHAVIOR_CONDITION_PLAYER_DAMAGED 5
#define OW_WILD_BEHAVIOR_CONDITION_SUBJECT_DAMAGED 6
#define OW_WILD_BEHAVIOR_ACTOR_FACT_RESERVED (1u << 0)
#define OW_WILD_BEHAVIOR_ACTOR_FACT_HELD (1u << 1)
#define OW_WILD_BEHAVIOR_ACTOR_FACT_THROW_LINE (1u << 2)
#define OW_WILD_BEHAVIOR_ACTOR_FACT_RECOVERING (1u << 3)
#define OW_WILD_BEHAVIOR_CONDITION_WHILE_TRUE 0
#define OW_WILD_BEHAVIOR_CONDITION_TIMED 1
#define OW_WILD_BEHAVIOR_CONDITION_UNTIL_CRASH 2
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_NONE 0
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER 1
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR 2
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_WILD (1u << 0)
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_ROLE_FOLLOWER (1u << 1)
#define OW_WILD_BEHAVIOR_CONDITION_TARGET_SELECTION_NEAREST 0
#define OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CURRENT 5
#define OW_WILD_BEHAVIOR_CONDITION_RANGE_VISION_CUSTOM 6
#define OW_WILD_BEHAVIOR_CONDITIONAL_PROFILE_NONE 0xFF
#define OW_WILD_BEHAVIOR_RELATIVE(value) ((u8)(s8)(value))
#define OW_WILD_BEHAVIOR_AT_LEAST(value) ((u8)(value))
#define OW_WILD_BEHAVIOR_AT_MOST(value) ((u8)(value))
#define OW_WILD_BEHAVIOR_NO_SLOWER_THAN(value) OW_WILD_BEHAVIOR_AT_MOST(value)
#define OW_WILD_BEHAVIOR_NO_FASTER_THAN(value) OW_WILD_BEHAVIOR_AT_LEAST(value)

#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE_MOUNT_BOUNCE (1u << 16)
#define OW_WILD_BEHAVIOR_OVERRIDE_MOUNT_STRIDE (1u << 27)
#define OW_WILD_BEHAVIOR_OVERRIDE_MOUNT_SETTLE (1u << 28)
#define OW_WILD_BEHAVIOR_OVERRIDE_MOUNT_LEAN (1u << 29)
#define OW_WILD_BEHAVIOR_OVERRIDE_VISION_RANGE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_EMOTE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_TIME (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE_VISION_CONE (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE_TURN_SKID_ONE_TIME (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE_STAMINA (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED (1u << 7)
/* Override bit 8 is reserved with the retired movement-range byte. */
#define OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_ID (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_TARGET (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE_VISION_ADJACENT_AWARENESS (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE_PLAYER_ADJACENT_DIRECTION_MASKS (1u << 15)
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
#define OW_WILD_BEHAVIOR_OVERRIDE2_ATTACKING (1u << 15)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ON_REACH_ACTION (1u << 16)
#define OW_WILD_BEHAVIOR_OVERRIDE2_THROW_MAX_RANGE (1u << 17)
#define OW_WILD_BEHAVIOR_OVERRIDE2_THROW_WINDUP_FRAMES (1u << 18)
#define OW_WILD_BEHAVIOR_OVERRIDE2_THROW_RECOVERY_FRAMES (1u << 19)
#define OW_WILD_BEHAVIOR_OVERRIDE2_KNOCKBACK_TYPE (1u << 20)
#define OW_WILD_BEHAVIOR_OVERRIDE2_KNOCKBACK_DISTANCE (1u << 21)
#define OW_WILD_BEHAVIOR_OVERRIDE2_DAMAGE_RECIPIENTS (1u << 22)

#define OW_WILD_BEHAVIOR_OVERRIDE2_TURN_SKID_TWO_TIME (1u << 23)
#define OW_WILD_BEHAVIOR_OVERRIDE2_STOP_SKID_TIME (1u << 24)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RETURN_AFTER_MOVE (1u << 25)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CARGO_TARGET_CHECK_INTERVAL (1u << 26)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CARGO_TARGET_SWITCH_ADVANTAGE (1u << 27)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_EXTRA_HOPS (1u << 28)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_EXTRA_CHANCE (1u << 29)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_HEART_CHANCE (1u << 30)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_CRY_CHANCE (1u << 31)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_MOVEMENT_VARIANCE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_VARIANCE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_SWAY_WIDTH (1u << 2)
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
#define OW_WILD_BEHAVIOR_OVERRIDE3_WANDER_STRAIGHT_CHANCE (1u << 20)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_ACTION_CHANCE (1u << 21)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE (1u << 22)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TILES_BEFORE_TURN_SKID (1u << 23)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_STOMP_TIME (1u << 24)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_ACCELERATION_STEP (1u << 25)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_TIME_VARIANCE (1u << 26)
#define OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE_VARIANCE (1u << 27)
#define OW_WILD_BEHAVIOR_OVERRIDE3_STOP_SKID (1u << 28)
#define OW_WILD_BEHAVIOR_OVERRIDE3_PLAN_TURN_SKID_PATH (1u << 29)
#define OW_WILD_BEHAVIOR_OVERRIDE3_MIN_IMPACT_SPEED (1u << 30)
#define OW_WILD_BEHAVIOR_OVERRIDE3_COLLISION_DAMAGE (1u << 31)

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
    u32 conditionEntriesOffset;
    u16 conditionEntryCount;
    u16 conditionEntrySize;
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
    u8 heightPageAndSurfaceType;
    u8 anchorBlockOffsets;
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
typedef char OverworldWildSurfaceInstanceSizeMustRemain8Bytes[
    sizeof(OverworldWildSurfaceInstance) == 8 ? 1 : -1];
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
#ifndef OVERWORLD_BEHAVIOR_HOST
typedef char OverworldWildSurfaceBlockCacheSizeMustRemain8Bytes[
    sizeof(OverworldWildSurfaceBlockCache) == 8 ? 1 : -1];
#endif

/* Sparse conditional-only group. Record existence means authored/inherited
 * replacement; four zero Arc bytes mean explicit none. IDs refer to global
 * application rows, never species-local u32 mask bits. */
#define OWBD_HOP_ARC_RECORD_COUNT 1
#define OWBD_HOP_ARC_RECORD_STORAGE_COUNT 1
typedef struct OverworldWildHopArcRecord {
    u16 globalApplicationId;
    u8 riseFrames, hangFrames, dropFrames, peakQ4;
} OverworldWildHopArcRecord;
typedef char OverworldWildHopArcRecordSizeMustRemain6[
    sizeof(OverworldWildHopArcRecord) == 6 ? 1 : -1];

/* Subject-local application bank, sorted by numeric species. */
typedef struct OverworldApplicationBankDirectoryEntry {
    u16 species;
    u16 first;
    u8 count;
    u8 reserved;
} OverworldApplicationBankDirectoryEntry;
typedef char OverworldApplicationBankDirectoryEntrySizeMustRemain6[
    sizeof(OverworldApplicationBankDirectoryEntry) == 6 ? 1 : -1];

typedef struct OverworldWildBehaviorDataBlob {
    OverworldWildBehaviorDataBlobHeader header;
    OverworldWildBehaviorProfileData classProfiles[OWBD_CLASS_PROFILE_COUNT];
    OverworldWildBehaviorClassRule classRules[OWBD_CLASS_RULE_COUNT];
    OverworldWildBehaviorSpeciesClassRule speciesClassRules[OWBD_SPECIES_CLASS_RULE_COUNT];
    OverworldWildBehaviorOverrideProfile overrideProfiles[OWBD_OVERRIDE_PROFILE_COUNT];
    u16 overrideMembers[OWBD_OVERRIDE_MEMBER_COUNT];
    OverworldWildBehaviorConditionEntry
        conditionEntries[OWBD_CONDITION_ENTRY_STORAGE_COUNT];
    OverworldWildSurfaceModelDirectoryEntry surfaceModels[OWBD_SURFACE_MODEL_COUNT];
    OverworldWildSurfaceInstance surfaceInstances[OWBD_SURFACE_INSTANCE_COUNT];
    OverworldWildSurfaceTemplate surfaceTemplates[OWBD_SURFACE_TEMPLATE_COUNT];
#if OWBD_SURFACE_CATALOG_PADDING_SIZE != 0
    u8 surfacePadding[OWBD_SURFACE_CATALOG_PADDING_SIZE];
#endif
    /* Legacy 32-bit prefix retained for Blob layout compatibility. Runtime
     * cooldown tint uses applicationRestTint through each subject bank. */
    u32 restEnabledApplications;
    OverworldWildBehaviorConditionOptions
        conditionOptions[OWBD_CONDITION_ENTRY_STORAGE_COUNT];
    OverworldWildHopArcRecord hopArcs[OWBD_HOP_ARC_RECORD_STORAGE_COUNT];
    OverworldApplicationBankDirectoryEntry
        applicationBankDirectory[OWBD_APPLICATION_BANK_DIRECTORY_COUNT];
    u16 applicationBankIndexes[OWBD_APPLICATION_BANK_INDEX_COUNT];
    u16 conditionGlobalApplications[OWBD_CONDITION_ENTRY_STORAGE_COUNT];
    u16 conditionGlobalSubjectApplications[OWBD_CONDITION_ENTRY_STORAGE_COUNT];
    u8 applicationLimitKeys[OWBD_OVERRIDE_PROFILE_COUNT];
    u8 applicationRestTint[OWBD_OVERRIDE_PROFILE_COUNT];
    u16 tiredClassGlobalIds[OWBD_CLASS_PROFILE_COUNT];
    u16 tiredOverrideGlobalIds[OWBD_OVERRIDE_PROFILE_COUNT];
} OverworldWildBehaviorDataBlob;

typedef char OverworldWildBehaviorRestTintMustFollowPaddedSurfaceCatalog[
    __builtin_offsetof(OverworldWildBehaviorDataBlob, restEnabledApplications)
        == __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceTemplates)
            + sizeof(((OverworldWildBehaviorDataBlob *)0)->surfaceTemplates)
            + OWBD_SURFACE_CATALOG_PADDING_SIZE ? 1 : -1];

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
    u32 groupFlags;
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
    u32 motionMasks);
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
