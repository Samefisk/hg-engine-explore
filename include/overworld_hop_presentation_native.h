#ifndef OVERWORLD_HOP_PRESENTATION_NATIVE_H
#define OVERWORLD_HOP_PRESENTATION_NATIVE_H

#include "overworld_behavior_conditions.h"

struct LocalMapObject;
struct OverworldWildSpawnState;
struct FieldSystem;
struct OverworldConditionNativeCall;
struct OverworldQueryCodeAddonEntry;
struct OverworldMountRuntimeState;

#define OVERWORLD_HOP_PRESENTATION_WILD_INIT 3
#define OVERWORLD_HOP_PRESENTATION_MOUNT_TICK 4
#define OVERWORLD_HOP_PRESENTATION_MOUNT_FINISH 5
#define OVERWORLD_HOP_PRESENTATION_PREFLIGHT 6

#define OVERWORLD_HOP_PRESENTATION_FRAMES 64
#define OVERWORLD_HOP_PRESENTATION_PREP 0
#define OVERWORLD_HOP_PRESENTATION_HEART 0
#define OVERWORLD_HOP_PRESENTATION_NONE 0xFF

/* Synchronously borrowed native presentation callbacks. The adapters keep
 * all motion and sequence state; this physical code host retains nothing. */
typedef struct OverworldHopPresentationOps {
    union {
        BOOL (*startNext)(struct OverworldWildSpawnState *, int, struct LocalMapObject *);
        struct LocalMapObject *(*follower)(void);
    };
    union {
        void (*ensureFrame)(struct OverworldWildSpawnState *, struct FieldSystem *);
        void (*cry)(u16, u8);
    };
    void (*heart)(struct LocalMapObject *, u8);
    u8 (*choices)(u32);
} OverworldHopPresentationOps;

/* Private boot-resident leaf. The caller is in its loaded parent Field.
 * Acquire checks the current lease only; it cannot load or rebind the image. */
const struct OverworldQueryCodeAddonEntry *OverworldHopPresentation_Acquire(struct FieldSystem *);

OverworldBehaviorConditionStatus OverworldHopPresentation_Run(
    struct OverworldConditionNativeCall *);

#if defined(__arm__)
_Static_assert(sizeof(OverworldHopPresentationOps) == 16,
    "borrowed Hop presentation ops changed");
#endif
#endif
