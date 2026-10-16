#ifndef OVERWORLD_WILD_RUNTIME_H
#define OVERWORLD_WILD_RUNTIME_H

#include "types.h"
#include "overworld_motion_model.h"
#include "overworld_actor_system.h"
#include "overworld_role_controller.h"
#include "overworld_wild_behavior_data.h"
#include "overworld_wild_movement.h"

typedef struct LocalMapObject LocalMapObject;
struct OverworldWildSpawnState;

#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY_ADDR 0x023BC800
#define OVERWORLD_WILD_RUNTIME_OVERLAY_END_ADDR 0x023BD400
#define OVERWORLD_WILD_RUNTIME_MAGIC 0x3152574F /* "OWR1" */
#define OVERWORLD_WILD_RUNTIME_VERSION 18

/* The request adapter removes this bit before Actor Motion sees the kind.
 * Forced motion has no lane: it uses zero pause, no chain and FORCED. */
#define OW_WILD_RUNTIME_MOTION_REQUEST_FORCED 0x80

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
/* knownSurface==NULL means a completed query found no catalog support.
 * FALSE means native support is not ready; output remains unchanged. */
typedef BOOL (*OverworldWildRuntimeResolveBaseYAtFunc)(
    FieldSystem *, const OverworldWildSurfaceHit *knownSurface,
    s32 originBaseY, u32 objectFlags, int x, int y, s32 *output);
typedef void (*OverworldWildRuntimeFillActorViewFunc)(
    FieldSystem *fieldSystem,
    struct OverworldWildSpawnState *state,
    int slot,
    OverworldActorStateSnapshot *view);
typedef BOOL (*OverworldWildRuntimeBindActorFunc)(
    FieldSystem *fieldSystem,
    struct OverworldWildSpawnState *state,
    int slot,
    OverworldActorHandle *handle);
typedef OverworldMotionDecision (*OverworldWildRuntimeRequestMotionFunc)(
    struct OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfileData *lane,
    u8 kind,
    u8 visibilityPolicy,
    u8 arcHeightQ4,
    u8 facing,
    u16 duration,
    u8 spinSpeed,
    u8 swayWidth,
    u16 targetSurfaceId);
typedef void (*OverworldWildRuntimeReduceRoleFunc)(
    const OverworldRoleControllerInput *input,
    OverworldRoleControllerOutput *output);
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
    OverworldWildRuntimeFillActorViewFunc fillActorView;
    OverworldWildRuntimeResolveBaseYAtFunc resolveBaseYAt;
    OverworldWildRuntimeRequestMotionFunc requestMotion;
    OverworldWildRuntimeReduceRoleFunc reduceRole;
    u32 reservedAcknowledgeMotion;
    OverworldWildRuntimeBindActorFunc bindActor;
    OverworldWildRuntimePlayStepDirtParticleFunc playStepDirtParticle;
    OverworldWildRuntimePlayLandingHopParticleFunc playLandingHopParticle;
} OverworldWildRuntimeOverlayEntry;

typedef char OverworldWildRuntimeOverlayEntrySizeMustRemain52Bytes[
    sizeof(OverworldWildRuntimeOverlayEntry) == 52 ? 1 : -1];

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
