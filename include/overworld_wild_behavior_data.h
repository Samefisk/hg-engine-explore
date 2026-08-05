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
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 41
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
#define OWBD_OVERRIDE_PROFILE_COUNT 14
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER_POKEMON 10
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_ACTIVE 12
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_TIRED 13
#define OWBD_OVERRIDE_MEMBER_COUNT 164
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
} OverworldWildSpawnDestination;

#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND         (1u << 0)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER        (1u << 1)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY       (1u << 2)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS        (1u << 3)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER       (1u << 4)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT (1u << 5)
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL          0x3F
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT      OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND

#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_FRONT  (1u << 0)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_BEHIND (1u << 1)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_LEFT   (1u << 2)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_RIGHT  (1u << 3)
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL   0xFu
#define OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL

#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE 0
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND 2

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
    u8 chillAllowedTerrainMask;
    u8 chillAllowedTerrainOverrideMask;
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
} OverworldWildBehaviorProfileData;

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
    u8 chillAllowedTerrainMask;
    u8 chillAllowedTerrainOverrideMask;
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
            u8 attentiveAllowedTerrainMask;
            u8 attentiveAllowedTerrainOverrideMask;
            u8 attentiveHopTime;
            u8 attentiveChaseBoostDistance;
            u8 attentiveChaseBoostSpeed;
            u8 attentiveHopSpinSpeed;
            u8 _activePad38;
            u8 attentiveCircleRadius;
            u8 attentiveContinueWhenArrived;
            u8 attentiveAvoidPreviousTile;
            u8 attentiveChainMovementVariance;
            u8 attentiveChainPauseVariance;
            u8 _activePad44[2];
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
            u8 tiredAllowedTerrainMask;
            u8 tiredAllowedTerrainOverrideMask;
            u8 tiredHopTime;
            u8 _tiredPad35[2];
            u8 tiredHopSpinSpeed;
            u8 _tiredPad38;
            u8 tiredCircleRadius;
            u8 tiredContinueWhenArrived;
            u8 tiredAvoidPreviousTile;
            u8 tiredChainMovementVariance;
            u8 tiredChainPauseVariance;
            u8 _tiredPad44[2];
        };
    };
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

#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED 0
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS 1
#define OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL 2
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
} OverworldWildBehaviorDataBlobHeader;

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
#define OVERWORLD_WILD_PERSONAL_CACHE_ENTRY \
    ((const OverworldWildPersonalCacheOverlayEntry *) \
        OVERWORLD_WILD_PERSONAL_CACHE_ENTRY_ADDR)

#endif // OVERWORLD_WILD_BEHAVIOR_DATA_H
