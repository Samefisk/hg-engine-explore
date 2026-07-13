#include "../../include/battle.h"
#include "../../include/type_mastery.h"

#define TRAINER_ID_MISTY_CERULEAN 254
#define TRAINER_ID_MISTY_REMATCH  721

typedef struct TypeMasteryTrainerMetadata {
    u16 trainerId;
    u8 type;
    u8 typeLevel;
} TypeMasteryTrainerMetadata;

static const TypeMasteryTrainerMetadata sTypeMasteryTrainerMetadata[] = {
    { TRAINER_ID_MISTY_CERULEAN, TYPE_WATER, 5 },
    { TRAINER_ID_MISTY_REMATCH, TYPE_WATER, 5 },
};

BOOL LONG_CALL TypeMastery_GetTrainerTypeLevels(
    u32 trainerId,
    u8 outTypeLevels[TYPE_MASTERY_TYPE_COUNT])
{
    u32 i;
    BOOL found = FALSE;

    if (outTypeLevels == NULL || trainerId > 0xFFFF)
    {
        return FALSE;
    }

    memset(outTypeLevels, 0, TYPE_MASTERY_TYPE_COUNT);

    for (i = 0; i < NELEMS(sTypeMasteryTrainerMetadata); i++)
    {
        const TypeMasteryTrainerMetadata *metadata = &sTypeMasteryTrainerMetadata[i];

        if (metadata->trainerId == trainerId
            && TypeMastery_IsValidType(metadata->type)
            && metadata->typeLevel > 0
            && metadata->typeLevel <= TYPE_MASTERY_MAX_TYPE_LEVEL)
        {
            outTypeLevels[metadata->type] = metadata->typeLevel;
            found = TRUE;
        }
    }

    return found;
}
