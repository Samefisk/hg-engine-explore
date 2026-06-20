#include "../../include/types.h"

#define HEADBUTT_MAX_COORDS_PER_TREE 6
#define HEADBUTT_NO_MATCH -1
#define HEADBUTT_SPECIAL_TREE_RESULT 2

typedef struct {
    s16 x;
    s16 y;
} HeadbuttCoord;

typedef struct {
    u8 coordCount;
    u8 reserved;
} CompactHeadbuttTreeHeader;

extern s32 HeadbuttNormalTreeResult(u16 treeIndex, u16 normalTreeCount, u32 selector);

static const u8 *HeadbuttSkipCompactTree(const u8 *cursor, u8 coordCount)
{
    return cursor + sizeof(CompactHeadbuttTreeHeader) + coordCount * sizeof(HeadbuttCoord);
}

static BOOL HeadbuttCompactTreeMatches(const u8 *cursor, s32 playerX, s32 playerY)
{
    const CompactHeadbuttTreeHeader *header = (const CompactHeadbuttTreeHeader *)cursor;
    const HeadbuttCoord *coords =
        (const HeadbuttCoord *)(cursor + sizeof(CompactHeadbuttTreeHeader));
    u8 i;

    if (header->coordCount == 0 || header->coordCount > HEADBUTT_MAX_COORDS_PER_TREE) {
        return FALSE;
    }

    for (i = 0; i < header->coordCount; i++) {
        if (coords[i].x == playerX && coords[i].y == playerY) {
            return TRUE;
        }
    }

    return FALSE;
}

s32 HeadbuttCompactTreeMatcher(
    u16 normalTreeCount,
    u16 specialTreeCount,
    u32 selector,
    s32 playerX,
    s32 playerY,
    const u8 *treeData)
{
    const u8 *cursor = treeData;
    u16 treeIndex;

    for (treeIndex = 0; treeIndex < normalTreeCount; treeIndex++) {
        const CompactHeadbuttTreeHeader *header = (const CompactHeadbuttTreeHeader *)cursor;

        if (header->coordCount == 0 || header->coordCount > HEADBUTT_MAX_COORDS_PER_TREE) {
            return HEADBUTT_NO_MATCH;
        }

        if (HeadbuttCompactTreeMatches(cursor, playerX, playerY)) {
            return HeadbuttNormalTreeResult(treeIndex, normalTreeCount, selector);
        }

        cursor = HeadbuttSkipCompactTree(cursor, header->coordCount);
    }

    for (treeIndex = 0; treeIndex < specialTreeCount; treeIndex++) {
        const CompactHeadbuttTreeHeader *header = (const CompactHeadbuttTreeHeader *)cursor;

        if (header->coordCount == 0 || header->coordCount > HEADBUTT_MAX_COORDS_PER_TREE) {
            return HEADBUTT_NO_MATCH;
        }

        if (HeadbuttCompactTreeMatches(cursor, playerX, playerY)) {
            return HEADBUTT_SPECIAL_TREE_RESULT;
        }

        cursor = HeadbuttSkipCompactTree(cursor, header->coordCount);
    }

    return HEADBUTT_NO_MATCH;
}
