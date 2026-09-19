#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"

typedef struct OverworldWildMotionReceiptPrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} OverworldWildMotionReceiptPrefix;

BOOL OverworldWildRuntime_ApplyMotionBoundary(
    int slot, u8 acknowledgements, u16 appliedThrough,
    OverworldMotionSample *sample, u8 *phase, u16 motionIdentity);

/* Wild's call adapter is hosted beside the shared bridge to fit overlay149.
 * It captures only Wild's accepted receipt, never the mounted slot's token. */
BOOL __attribute__((noinline, optimize("Os"),
    section(".overworld_wild_motion_receipt")))
OverworldWildSpawns_AcknowledgeSharedMotion(
    int slot, u8 acknowledgements, u16 appliedThrough,
    OverworldMotionSample *sample, u8 *phase)
{
    const OverworldWildMotionReceiptPrefix *runtime =
        (const OverworldWildMotionReceiptPrefix *)
            sOverworldWildSpawnState.movementRuntimeState;

    return OverworldWildRuntime_ApplyMotionBoundary(
        slot, acknowledgements, appliedThrough, sample, phase,
        runtime->movementMotionIdentities[slot]);
}
