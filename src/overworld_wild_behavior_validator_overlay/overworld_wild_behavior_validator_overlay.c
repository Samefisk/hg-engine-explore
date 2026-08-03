#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/constants/file.h"

#define OWBD_VALIDATION_NO_PROJECTION_BUILDER
#define OWBD_VALIDATION_USE_RESIDENT_HELPERS
#include "../../scripts/overworld_wild_behavior_v40_validation_shared.h"

typedef struct OwbdNarcReader {
    void *narc;
    u32 member;
    u32 size;
} OwbdNarcReader;

static BOOL OwbdNarcRead(void *context, u32 offset, u32 size, void *dest)
{
    OwbdNarcReader *reader = context;
    if (reader == NULL || dest == NULL || offset > reader->size
        || size > reader->size - offset) {
        return FALSE;
    }
    NARC_ReadFromMember(reader->narc, reader->member, offset, size, dest);
    return TRUE;
}

static BOOL OwbdValidateNarcMember(void *narc, u32 size, void *workspace, u32 workspaceSize)
{
    OwbdNarcReader reader;
    if (narc == NULL) return FALSE;
    reader.narc = narc;
    reader.member = CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA;
    reader.size = size;
    return OwbdValidateStream(OwbdNarcRead, &reader, size, workspace, workspaceSize);
}

OverworldWildBehaviorLoadResult OverworldWildBehaviorValidator_LoadCatalog(
    void **catalogOut)
{
    return OverworldWildBehavior_LoadValidatedBundle(
        OwbdValidateNarcMember, catalogOut);
}

const OverworldWildBehaviorValidatorOverlayEntry gOverworldWildBehaviorValidatorOverlayEntry
    __attribute__((section(".overworld_wild_behavior_validator_entry"), used)) = {
        OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_MAGIC,
        OVERWORLD_WILD_BEHAVIOR_VALIDATOR_OVERLAY_VERSION,
        sizeof(OverworldWildBehaviorValidatorOverlayEntry),
        OverworldWildBehaviorValidator_LoadCatalog,
    };
