#ifndef OVERWORLD_MOUNT_H
#define OVERWORLD_MOUNT_H

#include "overworld_wild_behavior_data.h"
#include "pokemon.h"
#include "types.h"

#define OVERWORLD_MOUNT_OVERLAY_LOAD_ADDR 0x023BAB00
#define OVERWORLD_MOUNT_OVERLAY_ENTRY_ADDR 0x023BB600
#define OVERWORLD_MOUNT_OVERLAY_END_ADDR 0x023BC800
#define OVERWORLD_MOUNT_OVERLAY_MAGIC 0x544E554D /* MUNT */
#define OVERWORLD_MOUNT_OVERLAY_VERSION 8

typedef enum OverworldMountPhase {
    OVERWORLD_MOUNT_PHASE_NONE = 0,
    OVERWORLD_MOUNT_PHASE_BOUND,
    OVERWORLD_MOUNT_PHASE_RIDING,
} OverworldMountPhase;

typedef enum OverworldMountMotionMode {
    OVERWORLD_MOUNT_MOTION_NONE = 0,
    OVERWORLD_MOUNT_MOTION_HOP,
    OVERWORLD_MOUNT_MOTION_TELEPORT,
    OVERWORLD_MOUNT_MOTION_CRASH,
} OverworldMountMotionMode;

typedef enum OverworldMountCancelReason {
    OVERWORLD_MOUNT_CANCEL_NONE = 0,
    OVERWORLD_MOUNT_CANCEL_EXPLICIT,
    OVERWORLD_MOUNT_CANCEL_FIELD_BUSY,
    OVERWORLD_MOUNT_CANCEL_MAP_CHANGE,
    OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST,
    OVERWORLD_MOUNT_CANCEL_IDENTITY_CHANGED,
    OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP,
} OverworldMountCancelReason;

typedef struct OverworldMountBinding {
    u32 personality;
    u16 species;
    u16 mapId;
    u16 mapGeneration;
    u16 encounterGeneration;
    u8 form;
    u8 level;
    u8 partySlot;
    u8 behaviorClass;
} OverworldMountBinding;

typedef struct OverworldMountSnapshot {
    /* The fully composed owner lane used for mounted control. Active/Tired
     * remain wild-AI concepts and are intentionally not retained here. */
    OverworldWildBehaviorProfileData profile;
    OverworldMountBinding binding;
    u32 sessionGeneration;
    u8 phase;
    u8 lastCancelReason;
    u8 motionMode;
    u8 reserved;
} OverworldMountSnapshot;

typedef struct OverworldMountOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    BOOL (*begin)(
        FieldSystem *fieldSystem,
        const OverworldMountBinding *binding,
        const OverworldWildBehaviorProfile *profile,
        const OverworldWildBehaviorPrimitives *primitives,
        const OverworldWildSurfaceCatalog *surfaceCatalog);
    void (*cancel)(u8 reason);
    void (*prepareMapTransition)(u8 mode);
    void (*onPlayerStep)(void);
    BOOL (*isActive)(void);
    BOOL (*tick)(
        FieldSystem *fieldSystem,
        struct OverworldWildSpawnState *state,
        u16 physicalKeys);
} OverworldMountOverlayEntry;

typedef char OverworldMountOverlayEntrySizeMustRemain32Bytes[
    sizeof(OverworldMountOverlayEntry) == 32 ? 1 : -1];

#define OVERWORLD_MOUNT_OVERLAY_ENTRY \
    ((const OverworldMountOverlayEntry *)OVERWORLD_MOUNT_OVERLAY_ENTRY_ADDR)

/* Fixed bridge used by the stock once-per-player-step callback. */
BOOL OverworldMount_PlayerStepBridgeEntry(FieldSystem *fieldSystem);

#endif // OVERWORLD_MOUNT_H
