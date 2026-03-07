#include "../include/visible_item_balls.h"

#include "../include/constants/item.h"
#include "../include/map_events_internal.h"
#include "../include/save.h"
#include "../include/script.h"

#define DIR_NORTH                      0
#define DIR_SOUTH                      1
#define DIR_WEST                       2
#define DIR_EAST                       3

enum VisibleItemPoolId {
    VISIBLE_ITEM_POOL_COMMON,
    VISIBLE_ITEM_POOL_GOOD,
    VISIBLE_ITEM_POOL_RARE,
    VISIBLE_ITEM_POOL_COUNT,
};

typedef struct VisibleItemPool {
    const u16 *items;
    u16 count;
} VisibleItemPool;

static const u16 sVisibleItemPoolCommon[] = {
    ITEM_POTION,
    ITEM_SUPER_POTION,
    ITEM_ANTIDOTE,
    ITEM_PARALYZE_HEAL,
    ITEM_AWAKENING,
    ITEM_BURN_HEAL,
    ITEM_ICE_HEAL,
    ITEM_FULL_HEAL,
    ITEM_ESCAPE_ROPE,
    ITEM_REPEL,
    ITEM_GREAT_BALL,
};

static const u16 sVisibleItemPoolGood[] = {
    ITEM_HYPER_POTION,
    ITEM_MAX_POTION,
    ITEM_REVIVE,
    ITEM_ETHER,
    ITEM_MAX_ETHER,
    ITEM_ELIXIR,
    ITEM_ULTRA_BALL,
    ITEM_SUPER_REPEL,
    ITEM_MAX_REPEL,
    ITEM_PP_UP,
};

static const u16 sVisibleItemPoolRare[] = {
    ITEM_FULL_RESTORE,
    ITEM_MAX_REVIVE,
    ITEM_RARE_CANDY,
    ITEM_NUGGET,
    ITEM_BIG_PEARL,
    ITEM_STAR_PIECE,
    ITEM_PROTEIN,
    ITEM_IRON,
    ITEM_CALCIUM,
    ITEM_CARBOS,
};

static const VisibleItemPool sVisibleItemPools[VISIBLE_ITEM_POOL_COUNT] = {
    [VISIBLE_ITEM_POOL_COMMON] = { sVisibleItemPoolCommon, NELEMS(sVisibleItemPoolCommon) },
    [VISIBLE_ITEM_POOL_GOOD] = { sVisibleItemPoolGood, NELEMS(sVisibleItemPoolGood) },
    [VISIBLE_ITEM_POOL_RARE] = { sVisibleItemPoolRare, NELEMS(sVisibleItemPoolRare) },
};

static u32 HashVisibleItemBallSeed(u32 seed)
{
    seed ^= seed >> 16;
    seed *= 0x7FEB352D;
    seed ^= seed >> 15;
    seed *= 0x846CA68B;
    seed ^= seed >> 16;
    return seed;
}

static u32 GetVisibleItemBallSpotSeed(FieldSystem *fsys)
{
    u16 *facingPtr;
    u32 mapId;
    int x;
    int y;
    int facing;

    if (fsys == NULL || fsys->playerAvatar == NULL || fsys->location == NULL) {
        return 0;
    }

    mapId = fsys->location->mapId;
    x = GetPlayerXCoord(fsys->playerAvatar);
    y = GetPlayerYCoord(fsys->playerAvatar);

    facingPtr = GetEvScriptWorkMemberAdrs(fsys, SCRIPTENV_FACING_DIRECTION);
    facing = facingPtr != NULL ? *facingPtr : DIR_NORTH;

    switch (facing) {
        case DIR_NORTH:
            y -= 1;
            break;

        case DIR_SOUTH:
            y += 1;
            break;

        case DIR_WEST:
            x -= 1;
            break;

        case DIR_EAST:
            x += 1;
            break;
    }

    return mapId ^ ((u32)(x & 0xFFFF) << 16) ^ (u32)(y & 0xFFFF);
}

static int GetVisibleItemPoolId(u16 originalItem)
{
    switch (originalItem) {
        case ITEM_POTION:
        case ITEM_SUPER_POTION:
        case ITEM_ANTIDOTE:
        case ITEM_PARALYZE_HEAL:
        case ITEM_AWAKENING:
        case ITEM_BURN_HEAL:
        case ITEM_ICE_HEAL:
        case ITEM_FULL_HEAL:
        case ITEM_ESCAPE_ROPE:
        case ITEM_REPEL:
        case ITEM_GREAT_BALL:
            return VISIBLE_ITEM_POOL_COMMON;

        case ITEM_HYPER_POTION:
        case ITEM_MAX_POTION:
        case ITEM_REVIVE:
        case ITEM_ETHER:
        case ITEM_MAX_ETHER:
        case ITEM_ELIXIR:
        case ITEM_ULTRA_BALL:
        case ITEM_SUPER_REPEL:
        case ITEM_MAX_REPEL:
        case ITEM_PP_UP:
            return VISIBLE_ITEM_POOL_GOOD;

        case ITEM_FULL_RESTORE:
        case ITEM_MAX_REVIVE:
        case ITEM_RARE_CANDY:
        case ITEM_NUGGET:
        case ITEM_BIG_PEARL:
        case ITEM_STAR_PIECE:
        case ITEM_PROTEIN:
        case ITEM_IRON:
        case ITEM_CALCIUM:
        case ITEM_CARBOS:
            return VISIBLE_ITEM_POOL_RARE;
    }

    return -1;
}

u16 ResolveVisibleItemBallItem(FieldSystem *fsys, u16 originalItem)
{
    struct PlayerProfile *profile;
    const VisibleItemPool *pool;
    int poolId;
    u32 spotSeed;
    u32 poolIndex;
    u32 seed;

    spotSeed = GetVisibleItemBallSpotSeed(fsys);
    if (spotSeed == 0) {
        return originalItem;
    }

    poolId = GetVisibleItemPoolId(originalItem);
    if (poolId < 0) {
        return originalItem;
    }

    pool = &sVisibleItemPools[poolId];
    if (pool->count == 0) {
        return ITEM_POKE_BALL;
    }

    profile = Sav2_PlayerData_GetProfileAddr(fsys->savedata);
    seed = profile->id;
    seed ^= spotSeed * 0x9E3779B9;
    seed ^= (u32)(poolId + 1) * 0x85EBCA6B;
    seed ^= (u32)originalItem * 0xC2B2AE35;
    seed = HashVisibleItemBallSeed(seed);

    poolIndex = seed % pool->count;
    if (pool->count > 1 && pool->items[poolIndex] == originalItem) {
        poolIndex = (poolIndex + 1) % pool->count;
    }

    return pool->items[poolIndex];
}
