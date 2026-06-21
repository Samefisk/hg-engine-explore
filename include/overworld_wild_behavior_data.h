#ifndef OVERWORLD_WILD_BEHAVIOR_DATA_H
#define OVERWORLD_WILD_BEHAVIOR_DATA_H

#include "types.h"

#define OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR 0x023C3000
#define OVERWORLD_WILD_LEGACY_ENCOUNTER_LOOKUP_ENTRY_ADDR 0x023C3000
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC 0x4F574244
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 18
#define OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_MAGIC 0x4F574544
#define OVERWORLD_WILD_ENCOUNTER_LOOKUP_DATA_VERSION 2
#define OWBD_CLASS_PROFILE_COUNT 8
#define OWBD_CLASS_RULE_COUNT 2
#define OWBD_SPECIES_CLASS_RULE_COUNT 110
#define OWBD_OVERRIDE_COUNT 2
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
    u8 attentiveAction;
    u8 targetSelector;
    u8 movementStyle;
    u8 chillCooldown;
    u8 attentiveCooldown;
    u8 alertChance;
    u8 spawnDestination;
    u8 chillBattle;
    u8 alertBattle;
    u8 attentiveBattle;
    u8 tiredBattle;
    u8 specialAction;
    u8 hopAllowNonCardinal;
    u8 hopMinDistance;
    u8 hopMaxDistance;
    u8 hopPause;
    u8 teleportTime;
    u8 teleportPause;
    u8 alertSpecialAction;
    u8 alertCallSpawnAmount;
    u8 alertCallSpawnState;
    u8 spawnDestinationMinDistance;
    u8 spawnDestinationMaxDistance;
    u8 ramAccelerationSteps;
    u8 ramMaxSpeed;
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

typedef struct OverworldWildBehaviorOverride {
    OverworldWildBehaviorMatch match;
    u32 mask;
    u16 mask2;
    u32 mask3;
    OverworldWildBehaviorProfile profile;
} OverworldWildBehaviorOverride;

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
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_COOLDOWN (1u << 19)
#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_COOLDOWN (1u << 20)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_CHANCE (1u << 21)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_TIME (1u << 22)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION (1u << 23)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_BATTLE (1u << 24)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_BATTLE (1u << 25)
#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_BATTLE (1u << 26)
#define OW_WILD_BEHAVIOR_OVERRIDE_TIRED_BATTLE (1u << 27)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPECIAL_ACTION (1u << 28)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_ALLOW_NON_CARDINAL (1u << 29)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_MIN_DISTANCE (1u << 30)
#define OW_WILD_BEHAVIOR_OVERRIDE_HOP_MAX_DISTANCE (1u << 31)

#define OW_WILD_BEHAVIOR_OVERRIDE2_HOP_PAUSE (1u << 0)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_TIME (1u << 1)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TELEPORT_PAUSE (1u << 2)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_SPECIAL_ACTION (1u << 3)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ALERT_CALL_SPAWN_AMOUNT (1u << 4)
#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MIN_DISTANCE (1u << 5)
#define OW_WILD_BEHAVIOR_OVERRIDE2_SPAWN_DESTINATION_MAX_DISTANCE (1u << 6)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RAM_ACCELERATION_STEPS (1u << 7)
#define OW_WILD_BEHAVIOR_OVERRIDE2_RAM_MAX_SPEED (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TILE_2 (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE2_ATTENTIVE_ALLOWED_TILE_2 (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE2_TIRED_ALLOWED_TILE_2 (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_TARGET (1u << 15)

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
#define OW_WILD_BEHAVIOR_OVERRIDE3_ALERT_CALL_SPAWN_STATE (1u << 16)

#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_ACTION 0u

#define OW_WILD_BEHAVIOR_OVERRIDE_NORMAL_SPEED OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED
#define OW_WILD_BEHAVIOR_OVERRIDE_MAX_SPEED OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_SPEED

typedef struct OverworldWildBehaviorDataOverlayEntry {
    const OverworldWildBehaviorProfile *classProfiles;
    u16 classProfileCount;
    const OverworldWildBehaviorClassRule *classRules;
    u16 classRuleCount;
    const OverworldWildBehaviorSpeciesClassRule *speciesClassRules;
    u16 speciesClassRuleCount;
    const OverworldWildBehaviorOverride *overrides;
    u16 overrideCount;
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
    u32 overridesOffset;
    u16 overrideCount;
    u16 overrideSize;
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

#define OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY \
    ((const OverworldWildBehaviorDataOverlayEntry *)OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR)
#define OVERWORLD_WILD_LEGACY_ENCOUNTER_LOOKUP_ENTRY \
    ((const OverworldWildEncounterLookupDataEntry *)OVERWORLD_WILD_LEGACY_ENCOUNTER_LOOKUP_ENTRY_ADDR)

#endif // OVERWORLD_WILD_BEHAVIOR_DATA_H
