#include "../include/types.h"
#include "../include/constants/file.h"

#define OW_SHINY_GFX_START 3000
#define OW_SHINY_GFX_COUNT 2048
#define OW_OVERWORLD_RESOURCE_HEAP_ID 4

void *LONG_CALL FieldOverworldResourceManager_GetPokemonOwNarc(void *resourceManager);

static void *LoadOverworldModelMember(void *narc, u32 memberNo, BOOL allocHigh)
{
    u32 size = NARC_GetMemberSize(narc, memberNo);
    void *data;

    if (allocHigh) {
        data = sys_AllocMemory(OW_OVERWORLD_RESOURCE_HEAP_ID, size);
    } else {
        data = sys_AllocMemoryLo(OW_OVERWORLD_RESOURCE_HEAP_ID, size);
    }

    if (data == NULL) {
        return NULL;
    }

    NARC_ReadWholeMember(narc, memberNo, data);
    return data;
}

void *OverworldWildSpawns_LoadOverworldModelResource(void *resourceManager, u32 memberNo, BOOL allocHigh)
{
    void *narc;
    void *data;

    if (memberNo >= OW_SHINY_GFX_START && memberNo < OW_SHINY_GFX_START + OW_SHINY_GFX_COUNT) {
        narc = NARC_ctor(ARC_CODE_ADDONS, OW_OVERWORLD_RESOURCE_HEAP_ID);
        if (narc == NULL) {
            return NULL;
        }

        data = LoadOverworldModelMember(
            narc,
            CODE_ADDON_SHINY_OVERWORLD_BTX_START + memberNo - OW_SHINY_GFX_START,
            allocHigh);
        NARC_dtor(narc);
        return data;
    }

    narc = FieldOverworldResourceManager_GetPokemonOwNarc(resourceManager);
    return LoadOverworldModelMember(narc, memberNo, allocHigh);
}
