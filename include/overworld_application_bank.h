#ifndef OVERWORLD_APPLICATION_BANK_H
#define OVERWORLD_APPLICATION_BANK_H

#include "overworld_wild_behavior_data.h"

#define OVERWORLD_APPLICATION_BANK_NONE 0xFFFFu

typedef struct OverworldApplicationBank {
    const u16 *globalIds;
    u8 count;
} OverworldApplicationBank;

/* All pointers are borrowed from the current Field-owned immutable blob.
 * Never retain a bank after Field unload or with a different subject. */
static inline BOOL OverworldApplicationBank_Select(
    const OverworldWildBehaviorDataBlob *blob, u16 species,
    OverworldApplicationBank *result)
{
    u16 left = 0;
    u16 right = OWBD_APPLICATION_BANK_DIRECTORY_COUNT - 1;
    const OverworldApplicationBankDirectoryEntry *row;
    if (blob == NULL || result == NULL)
        return FALSE;
    result->globalIds = NULL;
    result->count = 0;
    /* The last row is the wildcard fallback. Named rows are numeric. */
    while (left < right) {
        u16 middle = left + (right - left) / 2;
        row = &blob->applicationBankDirectory[middle];
        if (row->species < species)
            left = middle + 1;
        else
            right = middle;
    }
    row = &blob->applicationBankDirectory[left];
    if (row->species != species)
        row = &blob->applicationBankDirectory[
            OWBD_APPLICATION_BANK_DIRECTORY_COUNT - 1];
    if (row->count > OWBD_MASKABLE_APPLICATION_COUNT
        || (u32)row->first + row->count > OWBD_APPLICATION_BANK_INDEX_COUNT)
        return FALSE;
    result->globalIds = blob->applicationBankIndexes + row->first;
    result->count = row->count;
    for (u8 i = 0; i < result->count; ++i)
        if (result->globalIds[i] >= blob->header.overrideProfileCount
            || (i && result->globalIds[i] <= result->globalIds[i - 1]))
            return FALSE;
    return TRUE;
}

static inline u16 OverworldApplicationBank_Global(
    const OverworldApplicationBank *bank, u8 localSlot)
{
    return bank != NULL && localSlot < bank->count
        ? bank->globalIds[localSlot]
        : OVERWORLD_APPLICATION_BANK_NONE;
}

static inline int OverworldApplicationBank_Local(
    const OverworldApplicationBank *bank, u16 globalId)
{
    u8 i;
    if (bank == NULL || bank->count > OWBD_MASKABLE_APPLICATION_COUNT)
        return -1;
    for (i = 0; i < bank->count; ++i)
        if (bank->globalIds[i] == globalId)
            return i;
    return -1;
}

static inline const OverworldWildBehaviorOverrideProfile *
OverworldApplicationBank_Profile(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldApplicationBank *bank, u8 localSlot)
{
    return &blob->overrideProfiles[bank->globalIds[localSlot]];
}

#endif
