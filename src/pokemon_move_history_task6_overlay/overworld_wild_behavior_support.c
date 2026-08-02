#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/constants/file.h"

/* Overlay 155 is boot-resident, so overlay 149 imports these private helpers. */
#define OVERWORLD_WILD_RUNTIME_SIDECARS_IMPLEMENTATION
#include "../overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"

/* Keep resident lifecycle memset calls direct; a linker-generated Thumb
 * interworking veneer would consume the sealed private-support tail. */
void __attribute__((naked, noinline, used, aligned(4),
    section(".ow_wild_runtime_sidecar_wrapper")))
__wrap_memset(void)
{
    asm volatile(
        ".arch armv5t\n"
        "push {lr}\n"
        "blx 0x020E5B44\n"
        "pop {pc}\n"
        ".arch armv4t\n");
}

/* Overlay 155 is boot-resident.  Production validation imports these helpers
 * by symbol from its fixed private window; host validators keep local copies. */
#define OWBD_VALIDATION_DEFINE_RESIDENT_HELPERS
#define OWBD_VALIDATION_NO_PROJECTION_BUILDER
#include "../../scripts/overworld_wild_behavior_v40_validation_shared.h"

OverworldWildBehaviorLoadResult
    __attribute__((section(".owbd_resident_loader"), noinline, used))
OverworldWildBehavior_LoadValidatedProjection(
    OverworldWildBehaviorSemanticValidator validator,
    void **projectionOut)
{
    void *narc, *workspace, *projection;
    u32 size;
    *projectionOut = NULL;
    narc = NARC_ctor(ARC_CODE_ADDONS, HEAPID_WORLD);
    if (narc == NULL) return OWBD_LOAD_TRANSIENT_FAILURE;
    if (NARC_GetFileCount(narc) <= CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_PROJECTION) {
        NARC_dtor(narc); return OWBD_LOAD_PERMANENT_INVALID;
    }
    size = NARC_GetMemberSize(narc, CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA);
    if (size != OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE) {
        NARC_dtor(narc); return OWBD_LOAD_PERMANENT_INVALID;
    }
    workspace = sys_AllocMemory(HEAPID_WORLD, OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE);
    if (workspace == NULL) { NARC_dtor(narc); return OWBD_LOAD_TRANSIENT_FAILURE; }
    if (!validator(narc, size, workspace, OVERWORLD_WILD_BEHAVIOR_VALIDATOR_WORKSPACE_SIZE)) {
        sys_FreeMemoryEz(workspace); NARC_dtor(narc); return OWBD_LOAD_PERMANENT_INVALID;
    }
    sys_FreeMemoryEz(workspace);
    size = NARC_GetMemberSize(narc, CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_PROJECTION);
    if (size != OVERWORLD_WILD_BEHAVIOR_RUNTIME_PROJECTION_SIZE) {
        NARC_dtor(narc); return OWBD_LOAD_PERMANENT_INVALID;
    }
    projection = sys_AllocMemory(HEAPID_WORLD, size);
    if (projection == NULL) { NARC_dtor(narc); return OWBD_LOAD_TRANSIENT_FAILURE; }
    NARC_ReadWholeMember(narc, CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_PROJECTION, projection);
    NARC_dtor(narc);
    if (!validator(NULL, size, projection, 0)) {
        sys_FreeMemoryEz(projection); return OWBD_LOAD_PERMANENT_INVALID;
    }
    *projectionOut = projection;
    return OWBD_LOAD_SUCCESS;
}
