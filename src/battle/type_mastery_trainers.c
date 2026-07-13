#include "../../include/battle.h"
#include "../../include/type_mastery.h"

#define TRAINER_ID_MISTY_CERULEAN 254
#define TRAINER_ID_MISTY_REMATCH  721

typedef struct TypeMasteryTrainerMetadata {
    u16 trainerId;
    u8 activeType;
    u8 typeLevel;
} TypeMasteryTrainerMetadata;

static const TypeMasteryTrainerMetadata sTypeMasteryTrainerMetadata[] = {
    { TRAINER_ID_MISTY_CERULEAN, TYPE_WATER, 5 },
    { TRAINER_ID_MISTY_REMATCH, TYPE_WATER, 5 },
};

BOOL LONG_CALL TypeMastery_GetTrainerMetadata(
    u32 trainerId,
    u8 *outActiveType,
    u8 *outTypeLevel)
{
    u32 i;

    if (outActiveType != NULL)
    {
        *outActiveType = TYPE_MASTERY_TYPE_NONE;
    }
    if (outTypeLevel != NULL)
    {
        *outTypeLevel = 0;
    }

    if (outActiveType == NULL || outTypeLevel == NULL || trainerId > 0xFFFF)
    {
        return FALSE;
    }

    for (i = 0; i < NELEMS(sTypeMasteryTrainerMetadata); i++)
    {
        const TypeMasteryTrainerMetadata *metadata = &sTypeMasteryTrainerMetadata[i];

        if (metadata->trainerId == trainerId
            && TypeMastery_IsValidType(metadata->activeType)
            && metadata->typeLevel > 0
            && metadata->typeLevel <= TYPE_MASTERY_MAX_TYPE_LEVEL)
        {
            *outActiveType = metadata->activeType;
            *outTypeLevel = metadata->typeLevel;
            return TRUE;
        }
    }

    return FALSE;
}
