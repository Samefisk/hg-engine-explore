#ifndef OVERWORLD_WILD_BEHAVIOR_DATA_H
#define OVERWORLD_WILD_BEHAVIOR_DATA_H

#include "types.h"

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
#define OVERWORLD_WILD_BEHAVIOR_OVERLAY_VERSION 2
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC 0x4F574244
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 40
#define OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE 11636u
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAX_SIZE 0x3000u
#define OVERWORLD_WILD_BEHAVIOR_DATA_CHECKSUM 0x191F4869u
#define OVERWORLD_WILD_BEHAVIOR_DATA_SCHEMA_FINGERPRINT 0xE9C872AAu
#define OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE 3416u
#define OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_MAX_SIZE 0x0D8Cu
#define OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_CHECKSUM 0xE0B4A194u
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE 0x1600u
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_ENTRY_ADDR 0x023C0400u
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_END_ADDR 0x023C2160u
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_MAGIC 0x5642574Fu
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_VERSION 1u
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
#define OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM 31
#define OW_WILD_BEHAVIOR_CLASS_DEFAULT 0
#define OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE 1
#define OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM 2
#define OW_WILD_BEHAVIOR_CLASS_PICKED_UP 3
#define OWBD_CLASS_PROFILE_COUNT 4
#define OWBD_CLASS_RULE_COUNT 2
#define OWBD_SPECIES_CLASS_RULE_COUNT 113
#define OWBD_OVERRIDE_PROFILE_COUNT 11
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON 10
#define OWBD_OVERRIDE_MEMBER_COUNT 155
#define OWBD_OVERRIDE_COUNT OWBD_OVERRIDE_PROFILE_COUNT
#define OWBD_STATE_BODY_COUNT 58
#define OWBD_PROFILE_IDENTITY_COUNT 58
#define OWBD_CONTROLLER_COUNT 3
#define OWBD_CONTROLLER_NODE_COUNT 21
#define OWBD_TRANSITION_COUNT 26
#define OWBD_SPAWN_POLICY_COUNT 3
#define OWBD_POPULATION_POLICY_COUNT 6
#define OWBD_HOOK_SET_COUNT 3
#define OWBD_OVERRIDE_DEFINITION_COUNT 19
#define OWBD_OVERRIDE_SOURCE_COUNT 11
#define OWBD_OVERRIDE_ACTION_COUNT 207
#define OWBD_OWNER_COUNT 10
#define OWBD_RECOVERY_ACTION_COUNT 15
#define OWBD_TRANSITION_GUARD_COUNT 26
#define OWBD_TRANSITION_OPERATION_COUNT 53
#define OWBD_TRANSITION_ACTION_COUNT 41
#define OWBD_IMPORT_RECIPE_COUNT 12
#define OWBD_APPLICABILITY_COUNT 19
#define OWBD_TIRED_TRANSLATION_COUNT 18
#define OWBD_SEMANTIC_ID_COUNT 16
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
} OverworldWildSpawnDestination;

#define OW_WILD_BEHAVIOR_ALLOWED_TILE_LAND 0
#define OW_WILD_BEHAVIOR_ALLOWED_TILE_WATER 1
#define OW_WILD_BEHAVIOR_ALLOWED_TILE_CANOPY 2
#define OW_WILD_BEHAVIOR_ALLOWED_TILE_GRASS 3
#define OW_WILD_BEHAVIOR_ALLOWED_TILE_PLAYER 4
#define OW_WILD_BEHAVIOR_ALLOWED_TILE_PLAYER_FRONT 5
#define OW_WILD_BEHAVIOR_ALLOWED_TILE_NONE 0xF

#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_FRONT  (1u << 0)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_BEHIND (1u << 1)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_LEFT   (1u << 2)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_RIGHT  (1u << 3)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL   0xFu
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL

#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND 2

typedef struct OverworldWildBehaviorProfile {
    u8 chillState;
    u8 alertState;
    u8 alertEmote;
    u8 alertTime;
    u8 alertness;
    u8 attentiveState;
    u8 stamina;
    u8 tiredState;
    u8 restTime;
    u8 chillSpeed;
    u8 attentiveSpeed;
    u8 tiredSpeed;
    u8 range;
    u8 jumpLevel;
    u8 profileId;
    u8 spawnState;
    u8 chillAction;
    u8 chillTarget;
    u8 alertRange;
    u8 playerAdjacentDirectionMasks; // Shared nonzero player-relative F/B/L/R mask for Next to player.
    u8 targetSelector;
    u8 movementStyle;
    u8 alertChance;
    u8 spawnDestination;
    u8 attentiveBattle;
    u8 specialAction;
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
    u8 chillAllowedTile;
    u8 attentiveAllowedTile;
    u8 tiredAllowedTile;
    u8 chillAllowedTile2;
    u8 attentiveAllowedTile2;
    u8 tiredAllowedTile2;
    u8 attentiveHopAllowNonCardinal;
    u8 attentiveHopMinDistance;
    u8 attentiveHopMaxDistance;
    u8 attentiveHopPause;
    u8 attentiveTeleportTime;
    u8 attentiveTeleportPause;
    u8 attentiveRamAccelerationSteps;
    u8 attentiveRamMaxSpeed;
    u8 tiredHopAllowNonCardinal;
    u8 tiredHopMinDistance;
    u8 tiredHopMaxDistance;
    u8 tiredHopPause;
    u8 tiredTeleportTime;
    u8 tiredTeleportPause;
    u8 tiredRamAccelerationSteps;
    u8 tiredRamMaxSpeed;
    u8 hopTime;
    u8 attentiveChaseBoostDistance;
    u8 attentiveChaseBoostSpeed;
    u8 hopSpinSpeed;
    u8 spawnHopTime;
    u8 attentiveHopSpinSpeed;
    u8 attentiveCircleRadius;
    u8 attentiveContinueWhenArrived;
    u8 attentiveAvoidPreviousTile;
    u8 chainMovementVariance;
    u8 chainPauseVariance;
} OverworldWildBehaviorProfile;

typedef struct OverworldWildBehaviorContext {
    u16 species;
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
    OverworldWildBehaviorProfile profile;
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
    OverworldWildBehaviorProfile compoundBoundProfile;
} OverworldWildBehaviorOverrideProfile;

#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED 0
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS 1
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL 2
#define OW_WILD_BEHAVIOR_RELATIVE(value) ((u8)(s8)(value))
#define OW_WILD_BEHAVIOR_AT_LEAST(value) ((u8)(value))
#define OW_WILD_BEHAVIOR_AT_MOST(value) ((u8)(value))

#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_STATE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_EMOTE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERTNESS (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_STATE (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE_STAMINA (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE_TIRED_STATE (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_SPEED (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE_RANGE (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_ID (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_RANGE (1u << 15)
#define OW_WILD_BEHAVIOR_OVERRIDE_TIRED_SPEED (1u << 16)
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_SELECTOR (1u << 17)
#define OW_WILD_BEHAVIOR_OVERRIDE_MOVEMENT_STYLE (1u << 18)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_CHANCE (1u << 19)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_TIME (1u << 20)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION (1u << 21)
#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_BATTLE (1u << 22)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPECIAL_ACTION (1u << 23)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_ALLOW_NON_CARDINAL (1u << 24)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_MIN_DISTANCE (1u << 25)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_MAX_DISTANCE (1u << 26)

#define OW_WILD_BEHAVIOR_OVERRIDE2_HOP_PAUSE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_TIME (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_PAUSE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_SPECIAL_ACTION (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MIN_DISTANCE (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MAX_DISTANCE (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RAM_ACCELERATION_STEPS (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RAM_MAX_SPEED (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE_2 (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE_2 (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE_2 (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_TARGET (1u << 14)

#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_ALLOW_NON_CARDINAL (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_MIN_DISTANCE (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_MAX_DISTANCE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_PAUSE (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_TELEPORT_TIME (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_TELEPORT_PAUSE (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_RAM_ACCELERATION_STEPS (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_RAM_MAX_SPEED (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_ALLOW_NON_CARDINAL (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_MIN_DISTANCE (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_MAX_DISTANCE (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_HOP_PAUSE (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_TELEPORT_TIME (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_TELEPORT_PAUSE (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_RAM_ACCELERATION_STEPS (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_RAM_MAX_SPEED (1u << 15)
#define OW_WILD_BEHAVIOR_OVERRIDE3_OVERWORLD_LIMIT (1u << 16)
#define OW_WILD_BEHAVIOR_OVERRIDE3_HOP_TIME (1u << 17)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CHASE_BOOST_DISTANCE (1u << 18)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CHASE_BOOST_SPEED (1u << 19)
#define OW_WILD_BEHAVIOR_OVERRIDE3_HOP_SPIN_SPEED (1u << 20)
#define OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_HOP_TIME (1u << 21)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_HOP_SPIN_SPEED (1u << 22)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CIRCLE_RADIUS (1u << 23)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_CONTINUE_WHEN_ARRIVED (1u << 24)
#define OW_WILD_BEHAVIOR_OVERRIDE3_ATTENTIVE_AVOID_PREVIOUS_TILE (1u << 25)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_ACTION (1u << 26)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_MOVEMENT_VARIANCE (1u << 27)
#define OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_PAUSE_VARIANCE (1u << 28)
#define OW_WILD_BEHAVIOR_OVERRIDE3_PLAYER_ADJACENT_DIRECTION_MASKS (1u << 29)

#define OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP 0xFD

#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_ACTION 0u

#define OW_WILD_BEHAVIOR_OVERRIDE_NORMAL_SPEED OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED
#define OW_WILD_BEHAVIOR_OVERRIDE_MAX_SPEED OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_SPEED

/*
 * Version-40 serialized model.  These are wire records, not live runtime
 * objects: every relationship is a stable nonzero u16 ID and no record owns a
 * pointer.  The old three-state records above are only the explicitly bounded
 * runtime compatibility projection API; they are not an authoritative v40
 * serialized section.
 */
#if defined(__GNUC__)
#define OWBD_PACKED __attribute__((packed))
#else
#define OWBD_PACKED
#endif

#define OWBD_BLOB_FLAG_LEGACY_PROJECTION  (1u << 0)
#define OWBD_BLOB_FLAG_NAMES_ARE_HASHES   (1u << 1)
#define OWBD_BLOB_FLAG_AUTHORED_SOURCE     (1u << 2)
#define OWBD_BLOB_KNOWN_FLAGS \
    (OWBD_BLOB_FLAG_LEGACY_PROJECTION | OWBD_BLOB_FLAG_NAMES_ARE_HASHES \
        | OWBD_BLOB_FLAG_AUTHORED_SOURCE)
#define OWBD_NO_ID 0
#define OWBD_ANY_ID 0
#define OWBD_STATIC_PRIORITY_CLASS_BASE 0x0000
#define OWBD_STATIC_PRIORITY_OVERRIDE_BASE 0x4000
#define OWBD_GENERATED_PRIORITY_MATERIALIZED 0x8000

typedef enum OverworldWildSemanticRole {
    OWBD_ROLE_CALM = 1,
    OWBD_ROLE_ATTENTIVE,
    OWBD_ROLE_TIRED,
    OWBD_ROLE_ASLEEP,
    OWBD_ROLE_CARRIED,
    OWBD_ROLE_FOLLOWER,
    OWBD_ROLE_CUSTOM,
} OverworldWildSemanticRole;

#define OWBD_ROLE_MASK(role) (1u << ((role) - 1))
#define OWBD_ROLE_MASK_ORDINARY \
    (OWBD_ROLE_MASK(OWBD_ROLE_CALM) \
        | OWBD_ROLE_MASK(OWBD_ROLE_ATTENTIVE) \
        | OWBD_ROLE_MASK(OWBD_ROLE_TIRED))

typedef enum OverworldWildSelectorKind {
    OWBD_SELECTOR_EXACT = 1,
    OWBD_SELECTOR_SEMANTIC_ROLE,
} OverworldWildSelectorKind;

typedef enum OverworldWildOverrideKind {
    OWBD_OVERRIDE_KIND_STATE_CANDIDATE = 1,
    OWBD_OVERRIDE_KIND_MODIFIER,
} OverworldWildOverrideKind;

typedef enum OverworldWildOverrideChannel {
    OWBD_CHANNEL_STATIC_CONTEXT = 0,
    OWBD_CHANNEL_CONTROLLER_STATE = 1,
    OWBD_CHANNEL_TEMPORARY_EFFECT = 2,
    OWBD_CHANNEL_SCRIPTED_FORCE = 3,
    OWBD_CHANNEL_POSSESSION = 4,
    OWBD_CHANNEL_SYSTEM_SAFETY = 5,
} OverworldWildOverrideChannel;

/* The serialized numeric value is also the fixed composition rank. */
#define OWBD_CHANNEL_RANK_STATIC_CONTEXT    OWBD_CHANNEL_STATIC_CONTEXT
#define OWBD_CHANNEL_RANK_CONTROLLER_STATE  OWBD_CHANNEL_CONTROLLER_STATE
#define OWBD_CHANNEL_RANK_TEMPORARY_EFFECT  OWBD_CHANNEL_TEMPORARY_EFFECT
#define OWBD_CHANNEL_RANK_SCRIPTED_FORCE    OWBD_CHANNEL_SCRIPTED_FORCE
#define OWBD_CHANNEL_RANK_POSSESSION        OWBD_CHANNEL_POSSESSION
#define OWBD_CHANNEL_RANK_SYSTEM_SAFETY     OWBD_CHANNEL_SYSTEM_SAFETY

typedef enum OverworldWildModifierTargetKind {
    OWBD_MODIFIER_TARGET_STATE = 1,
    OWBD_MODIFIER_TARGET_CONTROLLER,
    OWBD_MODIFIER_TARGET_SPAWN_POLICY,
    OWBD_MODIFIER_TARGET_POPULATION_POLICY,
    OWBD_MODIFIER_TARGET_NODE_BINDING,
    OWBD_MODIFIER_TARGET_HOOK_SET,
    OWBD_MODIFIER_TARGET_CANDIDATE_TIMER,
} OverworldWildModifierTargetKind;

typedef enum OverworldWildModifierOperator {
    OWBD_OPERATOR_SET = 1,
    OWBD_OPERATOR_ADD,
    OWBD_OPERATOR_AT_LEAST,
    OWBD_OPERATOR_AT_MOST,
    OWBD_OPERATOR_ADD_AT_LEAST,
    OWBD_OPERATOR_ADD_AT_MOST,
} OverworldWildModifierOperator;

typedef enum OverworldWildStateField {
    OWBD_STATE_FIELD_LOCOMOTION = 1,
    OWBD_STATE_FIELD_TARGET,
    OWBD_STATE_FIELD_SPEED,
    OWBD_STATE_FIELD_RANGE,
    OWBD_STATE_FIELD_JUMP_LEVEL,
    OWBD_STATE_FIELD_ALLOWED_TILE,
    OWBD_STATE_FIELD_ALLOWED_TILE_2,
    OWBD_STATE_FIELD_HOP_ALLOW_NON_CARDINAL,
    OWBD_STATE_FIELD_HOP_MIN_DISTANCE,
    OWBD_STATE_FIELD_HOP_MAX_DISTANCE,
    OWBD_STATE_FIELD_HOP_PAUSE,
    OWBD_STATE_FIELD_HOP_TIME,
    OWBD_STATE_FIELD_HOP_SPIN_SPEED,
    OWBD_STATE_FIELD_TELEPORT_TIME,
    OWBD_STATE_FIELD_TELEPORT_PAUSE,
    OWBD_STATE_FIELD_RAM_ACCELERATION_STEPS,
    OWBD_STATE_FIELD_RAM_MAX_SPEED,
    OWBD_STATE_FIELD_CHASE_BOOST_DISTANCE,
    OWBD_STATE_FIELD_CHASE_BOOST_SPEED,
    OWBD_STATE_FIELD_CIRCLE_RADIUS,
    OWBD_STATE_FIELD_CONTINUE_WHEN_ARRIVED,
    OWBD_STATE_FIELD_AVOID_PREVIOUS_TILE,
    OWBD_STATE_FIELD_CHAIN_PAUSE_ACTION,
    OWBD_STATE_FIELD_CHAIN_MOVEMENT_VARIANCE,
    OWBD_STATE_FIELD_CHAIN_PAUSE_VARIANCE,
    OWBD_STATE_FIELD_BATTLE_TRIGGER,
    OWBD_STATE_FIELD_PLAYER_ADJACENT_MASK,
    OWBD_STATE_FIELD_BEHAVIOR_KIND,
} OverworldWildStateField;

typedef enum OverworldWildControllerField {
    OWBD_CONTROLLER_FIELD_ALERT_STATE = 1,
    OWBD_CONTROLLER_FIELD_ALERT_EMOTE,
    OWBD_CONTROLLER_FIELD_ALERT_TIME,
    OWBD_CONTROLLER_FIELD_ALERTNESS,
    OWBD_CONTROLLER_FIELD_ALERT_RANGE,
    OWBD_CONTROLLER_FIELD_ALERT_CHANCE,
    OWBD_CONTROLLER_FIELD_STAMINA,
    OWBD_CONTROLLER_FIELD_ALERT_SPECIAL_ACTION,
    OWBD_CONTROLLER_FIELD_SOURCE_PROFILE_ID,
} OverworldWildControllerField;

typedef enum OverworldWildSpawnPolicyField {
    OWBD_SPAWN_FIELD_STATE = 1,
    OWBD_SPAWN_FIELD_DESTINATION,
    OWBD_SPAWN_FIELD_MIN_DISTANCE,
    OWBD_SPAWN_FIELD_MAX_DISTANCE,
    OWBD_SPAWN_FIELD_HOP_TIME,
} OverworldWildSpawnPolicyField;

typedef enum OverworldWildPopulationPolicyField {
    OWBD_POPULATION_FIELD_LIMIT = 1,
} OverworldWildPopulationPolicyField;

typedef enum OverworldWildNodeBindingField {
    OWBD_NODE_BINDING_FIELD_STATE_KIND = 1,
} OverworldWildNodeBindingField;

typedef enum OverworldWildHookField {
    OWBD_HOOK_FIELD_HELP_CALL_INVOCATION = 1,
    OWBD_HOOK_FIELD_PICKUP_THROW_ENTRY,
    OWBD_HOOK_FIELD_PICKUP_THROW_ACTIVE_LOOP,
} OverworldWildHookField;

typedef enum OverworldWildCandidateTimerField {
    OWBD_CANDIDATE_TIMER_FIELD_REST_TIME = 1,
} OverworldWildCandidateTimerField;

typedef enum OverworldWildLifetimePolicy {
    OWBD_LIFETIME_CLEAR = 1,
    OWBD_LIFETIME_PRESERVE_LOGICAL = 2,
    OWBD_LIFETIME_SYSTEM = 3,
} OverworldWildLifetimePolicy;

#define OWBD_MAP_LIFETIME_CLEAR OWBD_LIFETIME_CLEAR
#define OWBD_MAP_LIFETIME_PRESERVE_LOGICAL OWBD_LIFETIME_PRESERVE_LOGICAL
#define OWBD_MAP_LIFETIME_SYSTEM OWBD_LIFETIME_SYSTEM
#define OWBD_BATTLE_LIFETIME_CLEAR OWBD_LIFETIME_CLEAR
#define OWBD_BATTLE_LIFETIME_PRESERVE_LOGICAL OWBD_LIFETIME_PRESERVE_LOGICAL
#define OWBD_BATTLE_LIFETIME_SYSTEM OWBD_LIFETIME_SYSTEM

typedef enum OverworldWildTimerClock {
    OWBD_TIMER_CLOCK_NONE = 0,
    OWBD_TIMER_CLOCK_FRAME,
    OWBD_TIMER_CLOCK_COMPLETED_MOVEMENT,
} OverworldWildTimerClock;

#define OWBD_TIMER_CLOCK_FIELD_FRAME OWBD_TIMER_CLOCK_FRAME
#define OWBD_TIMER_CLOCK_MOVEMENT_STEP OWBD_TIMER_CLOCK_COMPLETED_MOVEMENT

typedef enum OverworldWildTimerSource {
    OWBD_TIMER_SOURCE_NONE = 0,
    OWBD_TIMER_SOURCE_FIXED,
    OWBD_TIMER_SOURCE_CONTROLLER_STAMINA,
    OWBD_TIMER_SOURCE_CANDIDATE_FOLD,
} OverworldWildTimerSource;

typedef enum OverworldWildHiddenTimerPolicy {
    OWBD_HIDDEN_TIMER_NONE = 0,
    OWBD_HIDDEN_TIMER_PAUSE_WHILE_HIDDEN,
    OWBD_HIDDEN_TIMER_CONTINUE_WHILE_HIDDEN,
    OWBD_HIDDEN_TIMER_EXPIRE_ON_HIDE,
} OverworldWildHiddenTimerPolicy;

typedef enum OverworldWildRecoveryPolicy {
    OWBD_RECOVERY_NONE = 0,
    OWBD_RECOVERY_ROUTE_TRANSITION,
} OverworldWildRecoveryPolicy;

typedef enum OverworldWildTiredOriginKind {
    OWBD_TIRED_ORIGIN_FLED = 1,
    OWBD_TIRED_ORIGIN_RAM_CRASH,
    OWBD_TIRED_ORIGIN_THROW_RECOVERY,
} OverworldWildTiredOriginKind;

typedef enum OverworldWildStaticActionKind {
    OWBD_STATIC_ACTION_ASSIGN_CONTROLLER = 1,
    OWBD_STATIC_ACTION_BIND_NODE,
    OWBD_STATIC_ACTION_UNBIND_NODE,
    OWBD_STATIC_ACTION_APPLY_STATE_MODIFIER,
    OWBD_STATIC_ACTION_APPLY_CONTROLLER_MODIFIER,
    OWBD_STATIC_ACTION_BIND_SPAWN_POLICY,
    OWBD_STATIC_ACTION_APPLY_SPAWN_POLICY_PATCH,
    OWBD_STATIC_ACTION_BIND_POPULATION_POLICY,
    OWBD_STATIC_ACTION_APPLY_POPULATION_POLICY_PATCH,
    OWBD_STATIC_ACTION_BIND_HOOK_SET,
    OWBD_STATIC_ACTION_APPLY_CANDIDATE_TIMER_OPERATOR,
} OverworldWildStaticActionKind;

typedef enum OverworldWildTransitionTrigger {
    OWBD_TRIGGER_ALERT_COMPLETE = 1,
    OWBD_TRIGGER_STAMINA_EXHAUSTED,
    OWBD_TRIGGER_TIRED_EXPIRED,
    OWBD_TRIGGER_POSSESSION_APPLY,
    OWBD_TRIGGER_POSSESSION_REMOVE,
    OWBD_TRIGGER_FLED,
    OWBD_TRIGGER_RAM_CRASH,
    OWBD_TRIGGER_THROW_RECOVERY,
    OWBD_TRIGGER_AGGRO_APPLY,
    OWBD_TRIGGER_HELP_CALL_APPLY,
    OWBD_TRIGGER_FORCED_SLEEP_APPLY,
    OWBD_TRIGGER_FOLLOWER_APPLY,
    OWBD_TRIGGER_FOLLOWER_REMOVE,
} OverworldWildTransitionTrigger;

typedef enum OverworldWildTransitionGuardKind {
    OWBD_GUARD_ALWAYS = 1,
    OWBD_GUARD_EFFECTIVE_ROLE,
    OWBD_GUARD_EFFECTIVE_NODE,
    OWBD_GUARD_OWNER_PRESENT,
    OWBD_GUARD_OWNER_ABSENT,
    OWBD_GUARD_CANDIDATE_TIMER_EXPIRED,
    OWBD_GUARD_ALERT_CHANCE_ROLL,
    OWBD_GUARD_SYSTEM_ROUTE,
} OverworldWildTransitionGuardKind;

typedef enum OverworldWildTransitionOperationKind {
    OWBD_TRANSITION_APPLY = 1,
    OWBD_TRANSITION_REPLACE,
    OWBD_TRANSITION_REMOVE_REQUIRED,
    OWBD_TRANSITION_REMOVE_IF_PRESENT,
    OWBD_TRANSITION_REMOVE_OWNER_IF_PRESENT,
    OWBD_TRANSITION_APPLY_POLICY,
} OverworldWildTransitionOperationKind;

typedef enum OverworldWildTransitionBusyPolicy {
    OWBD_BUSY_REJECT = 1,
    OWBD_BUSY_QUEUE_EXACT,
} OverworldWildTransitionBusyPolicy;

typedef enum OverworldWildTypedActionPhase {
    OWBD_ACTION_PHASE_ENTRY = 1,
    OWBD_ACTION_PHASE_EXIT,
    OWBD_ACTION_PHASE_PRESENTATION,
    OWBD_ACTION_PHASE_INVOCATION,
} OverworldWildTypedActionPhase;

typedef enum OverworldWildTypedActionKind {
    OWBD_ACTION_NONE = 0,
    OWBD_ACTION_RESET_ACTIVE_STEPS = 1,
    OWBD_ACTION_RESET_TIRED_COUNTER,
    OWBD_ACTION_CLEAR_MOVEMENT_CHAIN,
    OWBD_ACTION_START_POST_TIRED_COOLDOWN,
    OWBD_ACTION_START_ALERT_PRESENTATION,
    OWBD_ACTION_ACTIVE_ENTRY_TRY_PICKUP_THROW,
    OWBD_ACTION_ALERT_COMPLETE,
    OWBD_ACTION_CANOPY_PICKUP_THROW_HOOK,
} OverworldWildTypedActionKind;

typedef enum OverworldWildApplicabilityFlags {
    OWBD_APPLICABILITY_IMMUTABLE_CONTEXT = 1u << 0,
    OWBD_APPLICABILITY_CONTROLLER = 1u << 1,
    OWBD_APPLICABILITY_EFFECTIVE_PROFILE = 1u << 2,
    OWBD_APPLICABILITY_SEMANTIC_ROLE = 1u << 3,
} OverworldWildApplicabilityFlags;

typedef enum OverworldWildRecoveryActionKind {
    OWBD_RECOVERY_ACTION_REMOVE_SELF = 1,
    OWBD_RECOVERY_ACTION_REMOVE_OWNER_IF_PRESENT,
    OWBD_RECOVERY_ACTION_RESET_TIRED_COUNTER,
    OWBD_RECOVERY_ACTION_START_FLEE_COOLDOWN,
} OverworldWildRecoveryActionKind;

typedef enum OverworldWildCandidateTimerOperator {
    OWBD_CANDIDATE_TIMER_SET = OWBD_OPERATOR_SET,
    OWBD_CANDIDATE_TIMER_ADD = OWBD_OPERATOR_ADD,
} OverworldWildCandidateTimerOperator;

#define OWBD_CANDIDATE_TIMER_SET_MAX 255
#define OWBD_CANDIDATE_TIMER_ADD_MIN (-32)
#define OWBD_CANDIDATE_TIMER_ADD_MAX 32
#define OWBD_CANDIDATE_TIMER_ADD_CLAMP_MAX 64

typedef struct OWBD_PACKED OverworldWildBlobSection {
    u32 offset;
    u16 count;
    u16 entrySize;
} OverworldWildBlobSection;

/* Compact authored-source v40 records. Small indices are limited to interned
 * bodies; every semantic relationship uses a registry-owned nonzero u16 ID. */
typedef struct OWBD_PACKED OverworldWildStateBodyRecord {
    u16 stableId;
    u8 provenanceKind;
    u8 valueCount;
    u8 values[28];
} OverworldWildStateBodyRecord;

typedef struct OWBD_PACKED OverworldWildProfileIdentityRecord {
    u16 stableId;
    u16 bodyId;
    u16 provenanceRecipeId;
    u8 tagA;
    u8 tagB;
} OverworldWildProfileIdentityRecord;

typedef struct OWBD_PACKED OverworldWildControllerRecord {
    u16 stableId;
    u16 nameId;
    u16 nodeStart;
    u16 nodeCount;
    u16 spawnPolicyId;
    u16 populationPolicyId;
    u16 hookSetId;
    u8 alertState;
    u8 alertEmote;
    u8 alertTime;
    u8 alertness;
    u8 alertRange;
    u8 alertChance;
    u8 stamina;
    u8 restTime;
    u8 flags;
    u8 reserved;
} OverworldWildControllerRecord;

typedef struct OWBD_PACKED OverworldWildControllerNodeRecord {
    u16 stableId;
    u16 controllerId;
    u16 profileIdentityId;
    u16 customRoleId;
    u8 semanticRole;
    u8 flags;
    u16 reserved;
} OverworldWildControllerNodeRecord;

#define OWBD_NODE_FLAG_BASE     (1u << 0)
#define OWBD_NODE_FLAG_OPTIONAL (1u << 1)
#define OWBD_NODE_FLAG_HIDDEN   (1u << 2)
#define OWBD_NODE_KNOWN_FLAGS \
    (OWBD_NODE_FLAG_BASE | OWBD_NODE_FLAG_OPTIONAL | OWBD_NODE_FLAG_HIDDEN)

typedef struct OWBD_PACKED OverworldWildOverrideSourceRecord {
    u16 stableId;
    u16 nameId;
    OverworldWildBehaviorMatch match;
    u16 memberStart;
    u16 memberCount;
    u16 actionStart;
    u16 actionCount;
    u8 targetMode;
    u8 order;
    u16 priority;
} OverworldWildOverrideSourceRecord;

typedef struct OWBD_PACKED OverworldWildGenericAssignmentRecord {
    u16 stableId;
    OverworldWildBehaviorMatch match;
    u16 assignmentActionIndex;
    u16 priority;
    u16 reserved;
} OverworldWildGenericAssignmentRecord;

typedef struct OWBD_PACKED OverworldWildSpeciesAssignmentRecord {
    u16 stableId;
    u16 species;
    u16 assignmentActionIndex;
    u16 priority;
} OverworldWildSpeciesAssignmentRecord;

typedef union OWBD_PACKED OverworldWildStaticActionPayload {
    struct OWBD_PACKED { u16 controllerId; u16 reserved0; u16 reserved1; u16 reserved2; } assignController;
    struct OWBD_PACKED { u16 controllerId; u16 nodeId; u16 profileIdentityId; u16 reserved; } bindNode;
    struct OWBD_PACKED { u16 controllerId; u16 nodeId; u16 reserved0; u16 reserved1; } unbindNode;
    /* ADD_AT_* applies delta first, then clamps to bound.  Other operators require bound == 0. */
    struct OWBD_PACKED {
        u8 fieldId;
        u8 operatorKind;
        s8 delta;
        u8 bound;
        u8 semanticRoleMask;
        u8 reserved;
        u16 controllerId;
    } modifier;
    struct OWBD_PACKED { u16 policyId; u16 reserved0; u16 reserved1; u16 reserved2; } bindPolicy;
    /* SET decodes operand as u8 (0..255). ADD decodes it as s8
     * (-32..32) and clamps each intermediate result to 0..64. */
    struct OWBD_PACKED { u16 controllerId; u16 nodeId; u8 operatorKind; u8 operand; u16 reserved; } timer;
    u8 raw[8];
} OverworldWildStaticActionPayload;

typedef struct OWBD_PACKED OverworldWildStaticActionRecord {
    u16 stableId;
    u8 kind;
    u8 flags;
    OverworldWildStaticActionPayload payload;
} OverworldWildStaticActionRecord;

typedef OverworldWildStaticActionRecord OverworldWildOverrideActionRecord;

#define OWBD_OVERRIDE_ACTION_FLAG_DIAGNOSTIC_ONLY (1u << 0)

typedef struct OWBD_PACKED OverworldWildTransitionRecord {
    u16 stableId;
    u16 candidateDefinitionId;
    u16 ownerId;
    u16 guardStart;
    u16 guardCount;
    u16 operationStart;
    u16 operationCount;
    u16 actionStart;
    u16 actionCount;
    u8 trigger;
    u8 fromRoleMask;
    u8 recoveryStart;
    u8 recoveryCount;
    u16 dispatchPriority;
} OverworldWildTransitionRecord;

typedef struct OWBD_PACKED OverworldWildTransitionGuardRecord {
    u16 stableId;
    u16 transitionId;
    u8 kind;
    u8 negate;
    u8 payload;
    u8 reserved0;
    u16 referenceId;
    u16 reserved;
} OverworldWildTransitionGuardRecord;

typedef struct OWBD_PACKED OverworldWildTransitionOperationRecord {
    u16 stableId;
    u16 transitionId;
    u16 definitionId;
    u16 ownerId;
    u16 replacementDefinitionId;
    u16 policyId;
    u16 instanceKey;
    u8 kind;
    u8 busyPolicy;
    u8 required;
    u8 reserved;
} OverworldWildTransitionOperationRecord;

typedef struct OWBD_PACKED OverworldWildTransitionActionRecord {
    u16 stableId;
    u16 transitionId;
    u8 phase;
    u8 kind;
    u16 referenceId;
    u16 payload;
} OverworldWildTransitionActionRecord;

typedef struct OWBD_PACKED OverworldWildSpawnPolicyRecord {
    u16 stableId;
    u16 nameId;
    u16 provenanceId;
    u8 spawnState;
    u8 destination;
    u8 minimumDistance;
    u8 maximumDistance;
    u8 spawnHopTime;
    u8 flags;
} OverworldWildSpawnPolicyRecord;

typedef struct OWBD_PACKED OverworldWildPopulationPolicyRecord {
    u16 stableId;
    u16 nameId;
    u16 populationGroupId;
    u16 provenanceId;
    u8 limit;
    u8 flags;
} OverworldWildPopulationPolicyRecord;

typedef struct OWBD_PACKED OverworldWildHookSetRecord {
    u16 stableId;
    u16 nameId;
    u8 helpCallInvocation;
    u8 pickupThrowEntry;
    u8 pickupThrowActiveLoop;
    u8 flags;
} OverworldWildHookSetRecord;

typedef struct OWBD_PACKED OverworldWildOverrideDefinitionRecord {
    u16 stableId;
    u16 nameId;
    u16 controllerId;
    u16 nodeId;
    u16 requiredOwnerId;
    u16 recoveryTransitionId;
    u16 applicabilityId;
    u16 priority;
    u8 kind;
    u8 channel;
    u8 selectorKind;
    u8 semanticRole;
    u8 mapLifetime;
    u8 battleLifetime;
    u8 timerClock;
    u8 timerSource;
    u8 hiddenTimerPolicy;
    u8 recoveryPolicy;
    u8 timerValue;
    u8 hasTiredOriginKind;
    u8 tiredOriginKind;
    u8 hasRequiredOwnerId;
    u8 allowMultipleOwners;
    u8 allowMultipleInstancesPerOwner;
    u8 authoredTiredBound;
    u8 flags;
    u8 reserved0;
    u8 reserved1;
} OverworldWildOverrideDefinitionRecord;

typedef struct OWBD_PACKED OverworldWildOwnerRecord {
    u16 stableId;
    u16 nameId;
    u8 systemOwned;
    u8 flags;
} OverworldWildOwnerRecord;

typedef struct OWBD_PACKED OverworldWildRecoveryActionRecord {
    u16 stableId;
    u16 transitionId;
    u16 ownerId;
    u8 kind;
    u8 required;
} OverworldWildRecoveryActionRecord;

typedef struct OWBD_PACKED OverworldWildImportRecipeRecord {
    u16 stableId;
    u16 ownerId;
    u16 controllerId;
    u16 nodeId;
    u16 profileIdentityId;
    u16 recoveryTransitionId;
    u16 semanticSourceId;
    u16 actionStart;
    u16 actionCount;
    /* 0xFFFF means replay the complete ordered matcher truth vector. */
    u16 truthVector;
    u8 semanticRole;
    u8 lifetime;
    u8 flags;
    u8 reserved;
} OverworldWildImportRecipeRecord;

typedef struct OWBD_PACKED OverworldWildApplicabilityRecord {
    u16 stableId;
    u16 flags;
    u32 immutableContextMask;
    u16 controllerId;
    u16 effectiveProfileId;
    u8 semanticRole;
    u8 reserved0;
    u16 reserved;
} OverworldWildApplicabilityRecord;

typedef struct OWBD_PACKED OverworldWildTiredTranslationRecord {
    u16 stableId;
    u8 tiredOriginKind;
    u8 authoredTiredBound;
    u16 destinationControllerId;
    u16 authoredProfileId;
    u16 candidateDefinitionId;
    u16 recoveryTransitionId;
    u16 exactFallbackControllerId;
    u16 exactFallbackNodeId;
    u8 timerOperator;
    u8 timerSource;
    u8 mapLifetime;
    u8 battleLifetime;
    u16 flags;
    u16 reserved;
} OverworldWildTiredTranslationRecord;

typedef enum OverworldWildSemanticIdKind {
    OWBD_SEMANTIC_ID_PROVENANCE = 1,
    OWBD_SEMANTIC_ID_CUSTOM_ROLE,
    OWBD_SEMANTIC_ID_POPULATION_GROUP,
} OverworldWildSemanticIdKind;

typedef struct OWBD_PACKED OverworldWildSemanticIdRecord {
    u16 stableId;
    u8 kind;
    u8 ordinal;
    u16 reserved;
    u16 reserved2;
} OverworldWildSemanticIdRecord;

typedef struct OverworldWildBehaviorDataOverlayEntry {
    const OverworldWildBehaviorProfile *classProfiles;
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

typedef enum OverworldWildBehaviorLoadResult {
    OWBD_LOAD_PERMANENT_INVALID = 0,
    OWBD_LOAD_SUCCESS = 1,
    OWBD_LOAD_TRANSIENT_FAILURE = 2,
} OverworldWildBehaviorLoadResult;

typedef BOOL (*OverworldWildBehaviorSemanticValidator)(
    void *narc, u32 memberSize, void *workspace, u32 workspaceSize);
OverworldWildBehaviorLoadResult OverworldWildBehavior_LoadValidatedProjection(
    OverworldWildBehaviorSemanticValidator validator,
    void **projectionOut);
OverworldWildBehaviorLoadResult OverworldWildBehavior_LoadValidatedBundle(
    OverworldWildBehaviorSemanticValidator validator,
    void **projectionOut);
void OverworldWildBehavior_ReleaseValidatedBundle(void *projection);
void OverworldWildBehavior_FreeValidatedBundle(void *projection);

typedef OverworldWildBehaviorLoadResult (*OverworldWildLoadValidatedProjectionFunc)(
    void **projection);

typedef struct OverworldWildBehaviorValidatorOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildLoadValidatedProjectionFunc loadValidatedProjection;
} OverworldWildBehaviorValidatorOverlayEntry;

typedef char OverworldWildBehaviorValidatorOverlayEntrySizeMustRemain12Bytes[
    sizeof(OverworldWildBehaviorValidatorOverlayEntry) == 8 + sizeof(void *) ? 1 : -1];

typedef struct OWBD_PACKED OverworldWildBehaviorDataBlobHeader {
    u32 magic;
    u16 version;
    u16 headerSize;
    u32 blobSize;
    u32 flags;
    u32 checksum;
    u32 schemaFingerprint;
    OverworldWildBlobSection stateBodies;
    OverworldWildBlobSection profileIdentities;
    OverworldWildBlobSection controllers;
    OverworldWildBlobSection controllerNodes;
    OverworldWildBlobSection sourceClassProfiles;
    OverworldWildBlobSection genericAssignments;
    OverworldWildBlobSection speciesAssignments;
    OverworldWildBlobSection overrideSources;
    OverworldWildBlobSection overrideMembers;
    OverworldWildBlobSection overrideActions;
    OverworldWildBlobSection spawnPolicies;
    OverworldWildBlobSection populationPolicies;
    OverworldWildBlobSection hookSets;
    OverworldWildBlobSection owners;
    OverworldWildBlobSection overrideDefinitions;
    OverworldWildBlobSection transitions;
    OverworldWildBlobSection transitionGuards;
    OverworldWildBlobSection transitionOperations;
    OverworldWildBlobSection transitionActions;
    OverworldWildBlobSection recoveryActions;
    OverworldWildBlobSection importRecipes;
    OverworldWildBlobSection applicability;
    OverworldWildBlobSection tiredTranslations;
    OverworldWildBlobSection semanticIds;
} OverworldWildBehaviorDataBlobHeader;

typedef char OverworldWildBlobSectionSizeMustRemain8Bytes[
    sizeof(OverworldWildBlobSection) == 8 ? 1 : -1];
typedef char OverworldWildStateBodyRecordSizeMustRemain32Bytes[
    sizeof(OverworldWildStateBodyRecord) == 32 ? 1 : -1];
typedef char OverworldWildProfileIdentityRecordSizeMustRemain8Bytes[
    sizeof(OverworldWildProfileIdentityRecord) == 8 ? 1 : -1];
typedef char OverworldWildControllerRecordSizeMustRemain24Bytes[
    sizeof(OverworldWildControllerRecord) == 24 ? 1 : -1];
typedef char OverworldWildControllerNodeRecordSizeMustRemain12Bytes[
    sizeof(OverworldWildControllerNodeRecord) == 12 ? 1 : -1];
typedef char OverworldWildOverrideSourceRecordSizeMustRemain28Bytes[
    sizeof(OverworldWildOverrideSourceRecord) == 28 ? 1 : -1];
typedef char OverworldWildGenericAssignmentRecordSizeMustRemain20Bytes[
    sizeof(OverworldWildGenericAssignmentRecord) == 20 ? 1 : -1];
typedef char OverworldWildSpeciesAssignmentRecordSizeMustRemain8Bytes[
    sizeof(OverworldWildSpeciesAssignmentRecord) == 8 ? 1 : -1];
typedef char OverworldWildOverrideActionRecordSizeMustRemain12Bytes[
    sizeof(OverworldWildOverrideActionRecord) == 12 ? 1 : -1];
typedef char OverworldWildStaticActionPayloadSizeMustRemain8Bytes[
    sizeof(OverworldWildStaticActionPayload) == 8 ? 1 : -1];
typedef char OverworldWildSpawnPolicyRecordSizeMustRemain12Bytes[
    sizeof(OverworldWildSpawnPolicyRecord) == 12 ? 1 : -1];
typedef char OverworldWildPopulationPolicyRecordSizeMustRemain10Bytes[
    sizeof(OverworldWildPopulationPolicyRecord) == 10 ? 1 : -1];
typedef char OverworldWildHookSetRecordSizeMustRemain8Bytes[
    sizeof(OverworldWildHookSetRecord) == 8 ? 1 : -1];
typedef char OverworldWildOverrideDefinitionRecordSizeMustRemain36Bytes[
    sizeof(OverworldWildOverrideDefinitionRecord) == 36 ? 1 : -1];
typedef char OverworldWildTransitionRecordSizeMustRemain24Bytes[
    sizeof(OverworldWildTransitionRecord) == 24 ? 1 : -1];
typedef char OverworldWildTransitionGuardRecordSizeMustRemain12Bytes[
    sizeof(OverworldWildTransitionGuardRecord) == 12 ? 1 : -1];
typedef char OverworldWildTransitionOperationRecordSizeMustRemain18Bytes[
    sizeof(OverworldWildTransitionOperationRecord) == 18 ? 1 : -1];
typedef char OverworldWildTransitionActionRecordSizeMustRemain10Bytes[
    sizeof(OverworldWildTransitionActionRecord) == 10 ? 1 : -1];
typedef char OverworldWildOwnerRecordSizeMustRemain6Bytes[
    sizeof(OverworldWildOwnerRecord) == 6 ? 1 : -1];
typedef char OverworldWildRecoveryActionRecordSizeMustRemain8Bytes[
    sizeof(OverworldWildRecoveryActionRecord) == 8 ? 1 : -1];
typedef char OverworldWildImportRecipeRecordSizeMustRemain24Bytes[
    sizeof(OverworldWildImportRecipeRecord) == 24 ? 1 : -1];
typedef char OverworldWildApplicabilityRecordSizeMustRemain16Bytes[
    sizeof(OverworldWildApplicabilityRecord) == 16 ? 1 : -1];
typedef char OverworldWildTiredTranslationRecordSizeMustRemain24Bytes[
    sizeof(OverworldWildTiredTranslationRecord) == 24 ? 1 : -1];
typedef char OverworldWildSemanticIdRecordSizeMustRemain8Bytes[
    sizeof(OverworldWildSemanticIdRecord) == 8 ? 1 : -1];
typedef char OverworldWildBehaviorDataBlobHeaderSizeMustRemain216Bytes[
    sizeof(OverworldWildBehaviorDataBlobHeader) == 216 ? 1 : -1];
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
    int directionCount);
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
#define OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_ENTRY \
    ((const OverworldWildBehaviorValidatorOverlayEntry *) \
        OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_ENTRY_ADDR)
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
#define OVERWORLD_WILD_PERSONAL_CACHE_ENTRY \
    ((const OverworldWildPersonalCacheOverlayEntry *) \
        OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR)

#endif // OVERWORLD_WILD_BEHAVIOR_DATA_H
