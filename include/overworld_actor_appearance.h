#ifndef OVERWORLD_ACTOR_APPEARANCE_H
#define OVERWORLD_ACTOR_APPEARANCE_H

#include "types.h"
#include "overworld_actor_system.h"
#include "overlay.h"

struct MapObjectMan;
struct LocalMapObject;
struct FieldSystem;
struct OverworldWildSpawnState;
struct OverworldBehaviorConditionPreparedActor;
struct OverworldWildBehaviorDataBlob;

#define OVERWORLD_ACTOR_APPEARANCE_MAX_STRENGTH 16
#define OVERWORLD_ACTOR_APPEARANCE_BLUE_STRENGTH 2

typedef enum OverworldActorAppearanceResult {
    OVERWORLD_ACTOR_APPEARANCE_CLEAR = 0,
    OVERWORLD_ACTOR_APPEARANCE_TINTED,
    OVERWORLD_ACTOR_APPEARANCE_YIELDED,
    OVERWORLD_ACTOR_APPEARANCE_UNSUPPORTED,
    OVERWORLD_ACTOR_APPEARANCE_INVALID,
    OVERWORLD_ACTOR_APPEARANCE_NO_MEMORY,
} OverworldActorAppearanceResult;

typedef enum OverworldActorAppearanceMode {
    OVERWORLD_ACTOR_APPEARANCE_NONE = 0,
    OVERWORLD_ACTOR_APPEARANCE_RED,
    OVERWORLD_ACTOR_APPEARANCE_BLUE,
} OverworldActorAppearanceMode;

typedef struct OverworldActorAppearanceInput {
    /* Must point at the current resident Actor snapshot, not a stack copy.
     * Mounted supplies the Pokemon MapObject, never the rider anchor. */
    const OverworldActorStateSnapshot *actor;
    struct LocalMapObject *pokemon;
    u8 redStrength;
    /* The condition owner supplies eligibility. Zero is the default.
     * The renderer neither evaluates conditions nor reads their timers. */
    u8 restTint;
    /* Uses the existing ARM input padding. Injury keeps the red palette owner
     * through zero-strength OFF frames; full HP permits rest tint or clear. */
    u8 damageActive;
} OverworldActorAppearanceInput;

typedef struct OverworldActorAppearanceNativeInput {
    const OverworldActorStateSnapshot *actor;
    const struct OverworldWildSpawnState *spawns;
    const struct OverworldBehaviorConditionPreparedActor *conditions;
    const struct OverworldWildBehaviorDataBlob *behavior;
    /* Prepared catalog application bits with rest tint enabled. Zero is off.
     * The condition owner supplies these from the current catalog. */
    u32 restEnabledApplications;
    u32 frame;
} OverworldActorAppearanceNativeInput;

/* Cached native facts for inspection. appliedMaterials counts real MAT
 * callbacks; it is not a substitute for proving the palette upload. */
typedef struct OverworldActorAppearanceSnapshot {
    OverworldActorHandle handle;
    u32 subjectIdentity;
    u32 authorityGeneration;
    u32 engineAnchorGeneration;
    u32 presentationGeneration;
    u32 actorPointer;
    u32 objectPointer;
    u32 drawPointer;
    u32 modelPointer;
    u32 texturePointer;
    u32 originalPalettePointer;
    u32 tintedPalettePointer;
    u32 originalPaletteKey;
    u32 privatePaletteKey;
    u32 appliedMaterials;
    u32 lastOriginalBase;
    u32 lastTintedBase;
    u16 paletteBytes;
    u16 species;
    u8 form;
    u8 level;
    u8 role;
    u8 mode;
    u8 strength;
    u8 yielded;
    u8 reserved[2];
} OverworldActorAppearanceSnapshot;

/* Call once per current actor at the presentation boundary. Graphics reloads
 * are detected here. Unknown/foreign callbacks keep control, including recall.
 * The module supports PLTT16 resources only and fails other formats closed. */
OverworldActorAppearanceResult OverworldActorAppearance_Update(
    struct MapObjectMan *manager,
    const OverworldActorAppearanceInput *input);

/* Remove a slot before its object/Actor storage is destroyed. A current
 * manager allows callback restoration; NULL means the old draws are already
 * destroyed. Finish/cancel recall before unloading this callback's code. */
void OverworldActorAppearance_Forget(struct MapObjectMan *manager, u16 slot);
void OverworldActorAppearance_Reset(struct MapObjectMan *manager);
const OverworldActorAppearanceSnapshot *OverworldActorAppearance_Inspect(u16 slot);

/* Field-update glue. Uses native HP and the condition owner's prepared state;
 * neither is read during drawing. All roles pass the same current actor. */
OverworldActorAppearanceResult OverworldActorAppearance_RefreshNative(
    const OverworldActorAppearanceNativeInput *input);

/* Call while the current object pool and Selector are still owned, BEFORE
 * stock Field overlay 1 releases its graphics or unloads. Cancel recall first,
 * then restore every tint callback and free private palettes. FALSE means
 * keep overlay 1 and its objects loaded and retry; do not force an unload.
 * NULL/NULL is allowed only after both draws and Selector are destroyed. */
BOOL OverworldActorAppearance_BeforeParentUnload(
    struct FieldSystem *fieldSystem, struct MapObjectMan *currentManager);

/* The current field owns this update. It uses the resident Actor slots and
 * the already loaded catalog; it never prepares a spawn or resolves a profile. */
void OverworldActorAppearance_RefreshAll(
    const struct OverworldWildSpawnState *spawns,
    const struct OverworldWildBehaviorDataBlob *behavior);
BOOL OverworldActorAppearance_FieldExit(void *manager, int *exitState);

/* Physical home is the retired stock graphics table, inside overlay 1.
 * Draw callbacks are drained before the stock Field parent releases graphics. */
#define OVERWORLD_ACTOR_APPEARANCE_CAPSULE_BASE 0x022074A8
#define OVERWORLD_ACTOR_APPEARANCE_CAPSULE_END 0x022089CC
#define OVERWORLD_ACTOR_APPEARANCE_MAGIC 0x5041574F /* OWAP */
#define OVERWORLD_ACTOR_APPEARANCE_VERSION 2
typedef struct OverworldActorAppearanceEntry {
    u32 magic;
    u16 version, size;
    OverworldActorAppearanceResult (*refresh)(const OverworldActorAppearanceNativeInput *);
    void (*forget)(struct MapObjectMan *, u16);
    BOOL (*beforeParentUnload)(struct FieldSystem *, struct MapObjectMan *);
    const OverworldActorAppearanceSnapshot *(*inspect)(u16);
    void (*refreshAll)(const struct OverworldWildSpawnState *,
        const struct OverworldWildBehaviorDataBlob *);
} OverworldActorAppearanceEntry;
#define OVERWORLD_ACTOR_APPEARANCE_ENTRY \
    ((const OverworldActorAppearanceEntry *)OVERWORLD_ACTOR_APPEARANCE_CAPSULE_BASE)

/* Resident spawn cleanup also runs before the stock Field parent exists.
 * Never enter this parent's code when it is absent from the SDK load list. */
static inline void __attribute__((unused)) OverworldActorAppearance_ForgetLoaded(
    struct MapObjectMan *manager, u16 slot)
{
    if (IsOverlayLoaded(1)) {
        OVERWORLD_ACTOR_APPEARANCE_ENTRY->forget(manager, slot);
    }
}

#endif
