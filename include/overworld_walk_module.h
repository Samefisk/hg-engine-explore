#ifndef OVERWORLD_WALK_MODULE_H
#define OVERWORLD_WALK_MODULE_H

#include "types.h"

struct FIELD_PLAYER_AVATAR;
struct LocalMapObject;
struct OverworldMountRuntimeState;
struct OverworldWildBehaviorProfileData;
struct OverworldWildBehaviorProfile;
struct OverworldWildBehaviorOverrideProfile;
struct OverworldWildBehaviorContext;
struct OverworldWildBehaviorDataBlob;
struct OverworldWildBehaviorPrimitives;
struct OverworldWildSpawnState;

#define OVERWORLD_WALK_MODULE_ENTRY_ADDR 0x023BF400
#define OVERWORLD_WALK_MODULE_MAGIC 0x4B4C4157 /* WALK */
#define OVERWORLD_WALK_MODULE_VERSION 1
#define OVERWORLD_WALK_PROFILE_MODULE_ENTRY_ADDR 0x023BF440
#define OVERWORLD_WALK_PROFILE_MODULE_MAGIC 0x46525057 /* WPRF */
#define OVERWORLD_WALK_MOUNT_MODULE_ENTRY_ADDR 0x023BF458
#define OVERWORLD_WALK_MOUNT_MODULE_MAGIC 0x544E4D57 /* WMNT */
#define OVERWORLD_WALK_FACE_MODULE_ENTRY_ADDR 0x023BF468
#define OVERWORLD_WALK_FACE_MODULE_MAGIC 0x45434146 /* FACE */
#define OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY_ADDR 0x023BF474
#define OVERWORLD_WALK_WILD_POLICY_MODULE_MAGIC 0x4C4F5057 /* WPOL */

typedef struct OverworldWalkModuleEntry {
    u32 magic;
    u16 version;
    u16 size;
    u8 (*clampTime)(u8 time);
    u8 (*accelerateTime)(u8 time, u8 fastestTime);
    u8 (*skidTiles)(u8 time);
    u8 (*skidTime)(u8 time);
    BOOL (*stompApplies)(u8 time, u8 threshold);
    u8 (*directionFromKeys)(u32 keys);
    u32 (*directionKey)(u8 direction);
    int (*deltaX)(u8 direction);
    int (*deltaY)(u8 direction);
    BOOL (*isFortyFiveDegreeTurn)(u8 fromDirection, u8 toDirection);
    void (*resolveMountedDiagonal)(
        struct OverworldMountRuntimeState *state,
        struct FIELD_PLAYER_AVATAR *avatar,
        u32 *newKeys,
        u32 *heldKeys);
    BOOL (*strictDiagonalAllowed)(
        struct OverworldMountRuntimeState *state,
        struct FIELD_PLAYER_AVATAR *avatar,
        u8 direction);
    u8 (*diagonalFacing)(
        struct LocalMapObject *player,
        u8 direction,
        u32 newKeys);
    u8 (*directionFromDelta)(int dx, int dy);
} OverworldWalkModuleEntry;

typedef char OverworldWalkModuleEntrySizeMustRemain64Bytes[
    sizeof(OverworldWalkModuleEntry) == 64 ? 1 : -1];

#define OVERWORLD_WALK_MODULE_ENTRY \
    ((const OverworldWalkModuleEntry *)OVERWORLD_WALK_MODULE_ENTRY_ADDR)

typedef struct OverworldWalkProfileModuleEntry {
    u32 magic;
    u16 version;
    u16 size;
    BOOL (*validateProfileData)(
        const struct OverworldWildBehaviorProfileData *profile);
    BOOL (*validateExactOverrideValue)(u8 fieldIndex, u8 value);
    void (*normalizeProfileData)(
        struct OverworldWildBehaviorProfileData *profile);
    BOOL (*validateExactOverrideProfile)(
        const struct OverworldWildBehaviorOverrideProfile *profile);
} OverworldWalkProfileModuleEntry;

typedef char OverworldWalkProfileModuleEntrySizeMustRemain24Bytes[
    sizeof(OverworldWalkProfileModuleEntry) == 24 ? 1 : -1];

#define OVERWORLD_WALK_PROFILE_MODULE_ENTRY \
    ((const OverworldWalkProfileModuleEntry *) \
        OVERWORLD_WALK_PROFILE_MODULE_ENTRY_ADDR)

typedef struct OverworldWalkMountModuleEntry {
    u32 magic;
    u16 version;
    u16 size;
    void (*filterInput)(
        struct OverworldMountRuntimeState *state,
        struct FIELD_PLAYER_AVATAR *avatar,
        u32 *newKeys,
        u32 *heldKeys);
    BOOL (*startFlatMotion)(
        struct OverworldMountRuntimeState *state,
        struct FIELD_PLAYER_AVATAR *avatar,
        struct LocalMapObject *follower,
        void *landDataManager,
        u8 direction,
        u8 facingDirection);
} OverworldWalkMountModuleEntry;

typedef char OverworldWalkMountModuleEntrySizeMustRemain16Bytes[
    sizeof(OverworldWalkMountModuleEntry) == 16 ? 1 : -1];

#define OVERWORLD_WALK_MOUNT_MODULE_ENTRY \
    ((const OverworldWalkMountModuleEntry *) \
        OVERWORLD_WALK_MOUNT_MODULE_ENTRY_ADDR)

typedef struct OverworldWalkFaceModuleEntry {
    u32 magic;
    u16 version;
    u16 size;
    void (*apply)(
        struct OverworldWildSpawnState *state,
        int slot,
        u8 enabled);
} OverworldWalkFaceModuleEntry;

typedef char OverworldWalkFaceModuleEntrySizeMustRemain12Bytes[
    sizeof(OverworldWalkFaceModuleEntry) == 12 ? 1 : -1];

#define OVERWORLD_WALK_FACE_MODULE_ENTRY \
    ((const OverworldWalkFaceModuleEntry *) \
        OVERWORLD_WALK_FACE_MODULE_ENTRY_ADDR)

typedef struct OverworldWalkWildPolicyModuleEntry {
    u32 magic;
    u16 version;
    u16 size;
    void (*resolvePrimitives)(
        const struct OverworldWildBehaviorProfile *profile,
        struct OverworldWildBehaviorPrimitives *primitives);
    u32 (*groupFlagsForTypes)(u16 species, u8 type1, u8 type2);
    u32 (*selectConditionalOverrideMask)(
        const struct OverworldWildBehaviorDataBlob *behaviorData,
        const struct OverworldWildBehaviorContext *context,
        u32 normalOverrideMask,
        u8 movementSpeed);
} OverworldWalkWildPolicyModuleEntry;

typedef char OverworldWalkWildPolicyModuleEntrySizeMustRemain20Bytes[
    sizeof(OverworldWalkWildPolicyModuleEntry) == 20 ? 1 : -1];

#define OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY \
    ((const OverworldWalkWildPolicyModuleEntry *) \
        OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY_ADDR)

#endif
