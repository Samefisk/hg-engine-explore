#ifndef OVERWORLD_BEHAVIOR_CONDITION_SHADOW_H
#define OVERWORLD_BEHAVIOR_CONDITION_SHADOW_H

#include "overworld_behavior_condition_runtime.h"
#include "overworld_wild_spawns_internal.h"

#define OVERWORLD_BEHAVIOR_CONDITION_SHADOW_MAGIC 0x5343574F /* OWCS */
#define OVERWORLD_BEHAVIOR_CONDITION_SHADOW_VERSION 2
#define OVERWORLD_BEHAVIOR_CONDITION_SHADOW_ENTRY_ADDR 0x023B6500

typedef struct OverworldBehaviorConditionShadowFrame {
    OverworldBehaviorConditionWorldView world;
    OverworldBehaviorConditionCandidate
        candidates[OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS];
    u8 traceArmed;
    u8 valid;
} OverworldBehaviorConditionShadowFrame;

typedef struct OverworldBehaviorConditionShadowRuntime {
    OverworldBehaviorConditionPreparedActor actors[OW_WILD_MAX_SPAWNS];
    OverworldBehaviorConditionScratch scratch;
    OverworldBehaviorConditionResult result;
    BehaviorResolveResult resolution;
    OverworldBehaviorConditionShadowFrame frame;
    u8 maxPreparedCount;
    u8 reserved[3];
} OverworldBehaviorConditionShadowRuntime;

typedef OverworldWildBehaviorContext
(*OverworldBehaviorConditionBuildContextFunc)(
    const OverworldWildSpawn *spawn,
    u16 species,
    u8 level,
    u8 terrain,
    u8 shiny);

typedef BOOL (*OverworldBehaviorConditionCurrentSpawnFunc)(
    FieldSystem *fieldSystem,
    const OverworldWildSpawn *spawn);

typedef struct OverworldBehaviorConditionShadowCall {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    const OverworldWildBehaviorDataBlob *behaviorData;
    OverworldBehaviorConditionShadowRuntime *runtime;
    OverworldBehaviorConditionBuildContextFunc buildContext;
    OverworldBehaviorConditionCurrentSpawnFunc isCurrentSpawn;
    u16 subjectTerrainMask;
    u8 subjectMovementSpeed;
    s8 forcedOverrideProfileIndex;
    u8 slot;
    u8 reserved[3];
} OverworldBehaviorConditionShadowCall;

typedef BOOL (*OverworldBehaviorConditionShadowPrepareFunc)(
    OverworldWildSpawnState *state,
    const OverworldWildBehaviorDataBlob *behaviorData,
    OverworldBehaviorConditionShadowRuntime *runtime,
    OverworldBehaviorConditionBuildContextFunc buildContext,
    const OverworldActorHandle *handle,
    u8 slot);

typedef void (*OverworldBehaviorConditionShadowClearSlotFunc)(
    OverworldBehaviorConditionShadowRuntime *runtime,
    u8 slot);

typedef void (*OverworldBehaviorConditionShadowClearAllFunc)(
    OverworldBehaviorConditionShadowRuntime *runtime);

typedef void (*OverworldBehaviorConditionShadowRunFunc)(
    const OverworldBehaviorConditionShadowCall *call);

typedef struct OverworldBehaviorConditionShadowEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldBehaviorConditionShadowPrepareFunc prepare;
    OverworldBehaviorConditionShadowClearSlotFunc clearSlot;
    OverworldBehaviorConditionShadowClearAllFunc clearAll;
    OverworldBehaviorConditionShadowRunFunc run;
} OverworldBehaviorConditionShadowEntry;

#define OVERWORLD_BEHAVIOR_CONDITION_SHADOW_ENTRY \
    ((const OverworldBehaviorConditionShadowEntry *) \
        OVERWORLD_BEHAVIOR_CONDITION_SHADOW_ENTRY_ADDR)

typedef char OverworldBehaviorConditionShadowEntrySizeMustRemain24Bytes[
    sizeof(OverworldBehaviorConditionShadowEntry) == 24 ? 1 : -1];

#endif // OVERWORLD_BEHAVIOR_CONDITION_SHADOW_H
