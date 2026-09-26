#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_wild_runtime.h"

/* Overlay 159 remains loaded beside Mount. Surface queries use Mount's one
 * runtime state and do not retain a second field or actor owner. */
u16 __attribute__((noinline, used,
    section(".overworld_mount_surface_id")))
OverworldMount_GetSurfaceId(int targetX, int targetY)
{
    const OverworldMountRuntimeState *state =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    OverworldWildSurfaceHit surface;

    if (OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->querySurface(
            state->fieldSystem,
            state->surfaceCatalog,
            targetX,
            targetY,
            &surface)) {
        return surface.surfaceId;
    }
    return OW_WILD_SURFACE_ID_NATIVE_GROUND;
}
