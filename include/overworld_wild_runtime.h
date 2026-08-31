#ifndef OVERWORLD_WILD_RUNTIME_H
#define OVERWORLD_WILD_RUNTIME_H

#include "types.h"
#include "overworld_wild_behavior_data.h"
#include "overworld_wild_movement.h"

typedef struct LocalMapObject LocalMapObject;

#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY_ADDR 0x023BC800
#define OVERWORLD_WILD_RUNTIME_OVERLAY_END_ADDR 0x023BD400
#define OVERWORLD_WILD_RUNTIME_MAGIC 0x3152574F /* "OWR1" */
#define OVERWORLD_WILD_RUNTIME_VERSION 10

typedef BOOL (*OverworldWildRuntimeValidateFunc)(void);
typedef BOOL (*OverworldWildRuntimeQuerySurfaceFunc)(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *catalog,
    int x,
    int y,
    OverworldWildSurfaceHit *hit);
typedef s32 (*OverworldWildRuntimeGetGroundBaseYFunc)(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *catalog,
    LocalMapObject *object,
    int x,
    int y);
typedef void (*OverworldWildRuntimeWalkMomentumResetFunc)(
    OverworldWildWalkMomentumState *state);
typedef BOOL (*OverworldWildRuntimeWalkMomentumStartFunc)(
    OverworldWildWalkMomentumState *state,
    u8 requestedDirection,
    u8 baseSpeed,
    u8 spotState,
    OverworldWildWalkStartStepCallback startStep,
    OverworldWildWalkEffectCallback effect,
    void *context);
typedef BOOL (*OverworldWildRuntimeWalkMomentumFinishFunc)(
    OverworldWildWalkMomentumState *state,
    u8 baseSpeed,
    u8 spotState,
    u8 fastestTravelTime,
    u8 tilesToAccelerate,
    u8 completedDirection,
    u8 completedDistance,
    BOOL walkStillActive,
    OverworldWildWalkStartStepCallback startStep,
    OverworldWildWalkEffectCallback effect,
    void *context);
typedef void (*OverworldWildRuntimePlayStepDirtParticleFunc)(
    LocalMapObject *object);
typedef void (*OverworldWildRuntimePlayLandingHopParticleFunc)(
    LocalMapObject *object);

typedef struct OverworldWildRuntimeOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldWildRuntimeValidateFunc validate;
    OverworldWildRuntimeQuerySurfaceFunc querySurface;
    OverworldWildRuntimeGetGroundBaseYFunc getGroundBaseY;
    OverworldWildRuntimeWalkMomentumResetFunc walkMomentumReset;
    OverworldWildRuntimeWalkMomentumStartFunc walkMomentumStart;
    OverworldWildRuntimeWalkMomentumFinishFunc walkMomentumFinish;
    /* ABI padding retained until overlay 156 can move. Resolver mechanics
     * are private to the actor-system resolver service. */
    u32 reservedResolverCallbacks[6];
    OverworldWildRuntimePlayStepDirtParticleFunc playStepDirtParticle;
    OverworldWildRuntimePlayLandingHopParticleFunc playLandingHopParticle;
} OverworldWildRuntimeOverlayEntry;

typedef char OverworldWildRuntimeOverlayEntrySizeMustRemain64Bytes[
    sizeof(OverworldWildRuntimeOverlayEntry) == 64 ? 1 : -1];

#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY \
    ((const OverworldWildRuntimeOverlayEntry *) \
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY_ADDR)

static inline BOOL OverworldWildRuntime_Validate(void)
{
    const OverworldWildRuntimeOverlayEntry *entry =
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY;
    u32 rawValidateAddress = (u32)entry->validate;
    u32 validateAddress = rawValidateAddress & ~1u;

    return entry->magic == OVERWORLD_WILD_RUNTIME_MAGIC
        && entry->version == OVERWORLD_WILD_RUNTIME_VERSION
        && entry->size == sizeof(*entry)
        && (rawValidateAddress & 1u) != 0
        && validateAddress >= OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY_ADDR
        && validateAddress < OVERWORLD_WILD_RUNTIME_OVERLAY_END_ADDR
        && entry->validate();
}

#endif // OVERWORLD_WILD_RUNTIME_H
