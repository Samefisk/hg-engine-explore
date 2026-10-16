#include "../../include/overworld_query_code_addon_service.h"

OverworldQueryCodeAddonState gOverworldQueryCodeAddonState
    __attribute__((used, section(".overworld_query_code_addon_state"))) = {0};
static OverworldQueryCodeAddonStatus Service_Load(const OverworldQueryCodeAddonOwner *owner,
    const OverworldQueryCodeAddonOps *ops, u32 member, u32 size)
{ return OverworldQueryCodeAddon_Load(&gOverworldQueryCodeAddonState, owner, ops, member, size); }
static const OverworldQueryCodeAddonEntry *Service_Acquire(const OverworldQueryCodeAddonOwner *owner)
{ return OverworldQueryCodeAddon_Acquire(&gOverworldQueryCodeAddonState, owner); }
static OverworldQueryCodeAddonStatus Service_Unload(const OverworldQueryCodeAddonOps *ops, void *query)
{ return OverworldQueryCodeAddon_Unload(&gOverworldQueryCodeAddonState, ops, query); }
const OverworldQueryCodeAddonServiceEntry gOverworldQueryCodeAddonServiceEntry
    __attribute__((used, section(".overworld_query_code_addon_service"))) = {
    OVERWORLD_QUERY_CODE_ADDON_SERVICE_MAGIC, OVERWORLD_QUERY_CODE_ADDON_SERVICE_VERSION,
    sizeof(OverworldQueryCodeAddonServiceEntry), &gOverworldQueryCodeAddonState,
    Service_Load, Service_Acquire, Service_Unload,
};
