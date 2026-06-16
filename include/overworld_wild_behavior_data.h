#ifndef OVERWORLD_WILD_BEHAVIOR_DATA_H
#define OVERWORLD_WILD_BEHAVIOR_DATA_H

#include "types.h"

#define OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR 0x023C3000
#define OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC 0x4F574244
#define OVERWORLD_WILD_BEHAVIOR_DATA_VERSION 1

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
} OverworldWildSpawnDestination;

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
    u8 normalSpeed;
    u8 maxSpeed;
    u8 range;
    u8 jumpLevel;
    u8 profileId;
    u8 spawnState;
    u8 chillAction;
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
    u16 species;
    u32 groupMask;
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

typedef struct OverworldWildBehaviorOverride {
    OverworldWildBehaviorMatch match;
    u32 mask;
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
#define OW_WILD_BEHAVIOR_OVERRIDE_NORMAL_SPEED (1u << 8)
#define OW_WILD_BEHAVIOR_OVERRIDE_MAX_SPEED (1u << 9)
#define OW_WILD_BEHAVIOR_OVERRIDE_RANGE (1u << 10)
#define OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL (1u << 11)
#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_ID (1u << 12)
#define OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_STATE (1u << 13)
#define OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION (1u << 14)
#define OW_WILD_BEHAVIOR_OVERRIDE_ALERT_RANGE (1u << 15)
#define OW_WILD_BEHAVIOR_OVERRIDE_ATTENTIVE_ACTION (1u << 16)
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

typedef struct OverworldWildBehaviorDataOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    const OverworldWildBehaviorProfile *classProfiles;
    u16 classProfileCount;
    const OverworldWildBehaviorClassRule *classRules;
    u16 classRuleCount;
    const OverworldWildBehaviorOverride *overrides;
    u16 overrideCount;
} OverworldWildBehaviorDataOverlayEntry;

#define OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY \
    ((const OverworldWildBehaviorDataOverlayEntry *)OVERWORLD_WILD_BEHAVIOR_DATA_OVERLAY_ENTRY_ADDR)

#endif // OVERWORLD_WILD_BEHAVIOR_DATA_H
