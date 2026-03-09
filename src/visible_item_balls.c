#include "../include/visible_item_balls.h"

#include "../include/constants/item.h"
#include "../include/map_events_internal.h"
#include "../include/save.h"
#include "../include/script.h"

#define ITEM_BALL_GFX_ID     87
#define ITEM_BALL_SCRIPT_MIN 7000
#define ITEM_BALL_SCRIPT_MAX 8000
#define DIR_NORTH            0
#define DIR_SOUTH            1
#define DIR_WEST             2
#define DIR_EAST             3

enum VisibleItemPoolId {
    VISIBLE_ITEM_POOL_COMMON,
    VISIBLE_ITEM_POOL_GOOD,
    VISIBLE_ITEM_POOL_RARE,
    VISIBLE_ITEM_POOL_VERY_RARE,
    VISIBLE_ITEM_POOL_EXTREMELY_RARE,
    VISIBLE_ITEM_POOL_COUNT,
};

typedef struct VisibleItemPool {
    const u16 *items;
    u16 count;
} VisibleItemPool;

static const u16 sVisibleItemPoolCommon[] = {
    // Healing
    // ITEM_POTION,
    // ITEM_SUPER_POTION,
    // ITEM_ANTIDOTE,
    // ITEM_BURN_HEAL,
    // ITEM_ICE_HEAL,
    // ITEM_AWAKENING,
    // ITEM_PARALYZE_HEAL,
    // ITEM_FULL_HEAL,
    // Berries
    ITEM_ORAN_BERRY,
    ITEM_PECHA_BERRY,
    ITEM_CHERI_BERRY,
    ITEM_CHESTO_BERRY,
    ITEM_RAWST_BERRY,
    ITEM_ASPEAR_BERRY,
    ITEM_PERSIM_BERRY,
    ITEM_LEPPA_BERRY,
    // EV-reducing berries
    ITEM_POMEG_BERRY,
    ITEM_KELPSY_BERRY,
    ITEM_QUALOT_BERRY,
    ITEM_HONDEW_BERRY,
    ITEM_GREPA_BERRY,
    ITEM_TAMATO_BERRY,
    // Balls
    ITEM_POKE_BALL,
    ITEM_GREAT_BALL,
    ITEM_PREMIER_BALL,
    ITEM_NET_BALL,
    ITEM_DIVE_BALL,
    ITEM_NEST_BALL,
    ITEM_HEAL_BALL,
    // Utility
    ITEM_ESCAPE_ROPE,
    ITEM_REPEL,
    // Valuables
    ITEM_PEARL,
    ITEM_STARDUST,
    ITEM_TINY_MUSHROOM,
    // Hold items - weak/niche
    ITEM_SMOKE_BALL,
    ITEM_CLEANSE_TAG,
    ITEM_EVERSTONE,
    ITEM_SOOTHE_BELL,
    ITEM_AMULET_COIN,
    ITEM_LUCK_INCENSE,
    ITEM_DESTINY_KNOT,
    ITEM_LAGGING_TAIL,
    ITEM_STICKY_BARB,
    ITEM_IRON_BALL,
    ITEM_GRIP_CLAW,
    ITEM_BINDING_BAND,
    ITEM_FLOAT_STONE,
    ITEM_ABSORB_BULB,
    ITEM_CELL_BATTERY,
    ITEM_LUMINOUS_MOSS,
    ITEM_SNOWBALL,
    ITEM_RING_TARGET,
    // TMs - weak/utility/situational
    ITEM_TM005, // Roar
    ITEM_TM009, // Bullet Seed
    ITEM_TM012, // Taunt
    ITEM_TM028, // Dig
    ITEM_TM034, // Shock Wave
    ITEM_TM039, // Rock Tomb
    ITEM_TM040, // Aerial Ace
    ITEM_TM043, // Secret Power
    ITEM_TM046, // Thief
    ITEM_TM054, // False Swipe
    ITEM_TM055, // Brine
    ITEM_TM057, // Charge Beam
    ITEM_TM058, // Endure
    ITEM_TM070, // Flash
    ITEM_TM078, // Captivate
    ITEM_TM083, // Natural Gift
    ITEM_TM088, // Pluck
};

static const u16 sVisibleItemPoolGood[] = {
    // Healing
    ITEM_HYPER_POTION,
    ITEM_MAX_POTION,
    ITEM_REVIVE,
    ITEM_MOOMOO_MILK,
    // ITEM_ETHER,
    // ITEM_ELIXIR,
    // Berries
    ITEM_LUM_BERRY,
    ITEM_SITRUS_BERRY,
    // Resistance berries
    ITEM_OCCA_BERRY,
    ITEM_PASSHO_BERRY,
    ITEM_WACAN_BERRY,
    ITEM_RINDO_BERRY,
    ITEM_YACHE_BERRY,
    ITEM_CHOPLE_BERRY,
    ITEM_KEBIA_BERRY,
    ITEM_SHUCA_BERRY,
    ITEM_COBA_BERRY,
    ITEM_PAYAPA_BERRY,
    ITEM_TANGA_BERRY,
    ITEM_CHARTI_BERRY,
    ITEM_KASIB_BERRY,
    ITEM_HABAN_BERRY,
    ITEM_COLBUR_BERRY,
    ITEM_BABIRI_BERRY,
    ITEM_ROSELI_BERRY,
    // Balls
    ITEM_ULTRA_BALL,
    ITEM_DUSK_BALL,
    ITEM_QUICK_BALL,
    ITEM_TIMER_BALL,
    ITEM_REPEAT_BALL,
    ITEM_LUXURY_BALL,
    // Apricorn balls
    ITEM_LEVEL_BALL,
    ITEM_LURE_BALL,
    ITEM_MOON_BALL,
    ITEM_FRIEND_BALL,
    ITEM_LOVE_BALL,
    ITEM_HEAVY_BALL,
    ITEM_FAST_BALL,
    // Utility
    ITEM_SUPER_REPEL,
    ITEM_MAX_REPEL,
    // Progression
    ITEM_PP_UP,
    // Valuables
    ITEM_BIG_MUSHROOM,
    /* Type-boosting held items
    ITEM_CHARCOAL,
    ITEM_MYSTIC_WATER,
    ITEM_MAGNET,
    ITEM_MIRACLE_SEED,
    ITEM_NEVER_MELT_ICE,
    ITEM_POISON_BARB,
    ITEM_SOFT_SAND,
    ITEM_SHARP_BEAK,
    ITEM_TWISTED_SPOON,
    ITEM_SPELL_TAG,
    ITEM_DRAGON_FANG,
    ITEM_BLACK_BELT,
    ITEM_BLACK_GLASSES,
    ITEM_SILK_SCARF,
    ITEM_SILVER_POWDER,
    ITEM_HARD_STONE,
    */
    // Plates
    ITEM_FLAME_PLATE,
    ITEM_SPLASH_PLATE,
    ITEM_ZAP_PLATE,
    ITEM_MEADOW_PLATE,
    ITEM_ICICLE_PLATE,
    ITEM_FIST_PLATE,
    ITEM_TOXIC_PLATE,
    ITEM_EARTH_PLATE,
    ITEM_SKY_PLATE,
    ITEM_MIND_PLATE,
    ITEM_INSECT_PLATE,
    ITEM_STONE_PLATE,
    ITEM_SPOOKY_PLATE,
    ITEM_DRACO_PLATE,
    ITEM_DREAD_PLATE,
    ITEM_IRON_PLATE,
    ITEM_PIXIE_PLATE,
    // Other held items - useful utility
    ITEM_SHELL_BELL,
    ITEM_BLACK_SLUDGE,
    ITEM_QUICK_CLAW,
    ITEM_FOCUS_BAND,
    ITEM_BIG_ROOT,
    ITEM_MACHO_BRACE,
    ITEM_RED_CARD,
    ITEM_EJECT_BUTTON,
    ITEM_ADRENALINE_ORB,
    ITEM_ROOM_SERVICE,
    ITEM_CLEAR_AMULET,
    // Weather extenders
    ITEM_HEAT_ROCK,
    ITEM_DAMP_ROCK,
    ITEM_ICY_ROCK,
    ITEM_SMOOTH_ROCK,
    ITEM_LIGHT_CLAY,
    // TMs - solid support and decent offensive
    ITEM_TM006, // Toxic
    ITEM_TM007, // Hail
    ITEM_TM010, // Hidden Power
    ITEM_TM011, // Sunny Day
    ITEM_TM016, // Light Screen
    ITEM_TM017, // Protect
    ITEM_TM018, // Rain Dance
    ITEM_TM020, // Safeguard
    ITEM_TM027, // Return
    ITEM_TM031, // Brick Break
    ITEM_TM032, // Double Team
    ITEM_TM033, // Reflect
    ITEM_TM037, // Sandstorm
    ITEM_TM042, // Facade
    ITEM_TM044, // Rest
    ITEM_TM047, // Steel Wing
    ITEM_TM051, // Roost
    ITEM_TM065, // Shadow Claw
    ITEM_TM066, // Payback
    ITEM_TM069, // Rock Polish
    ITEM_TM072, // Avalanche
    ITEM_TM073, // Thunder Wave
    ITEM_TM082, // Sleep Talk
    ITEM_TM085, // Dream Eater
};

static const u16 sVisibleItemPoolRare[] = {
    // Healing
    ITEM_FULL_RESTORE,
    ITEM_MAX_REVIVE,
    ITEM_MAX_ETHER,
    // Vitamins
    // ITEM_PROTEIN,
    // ITEM_IRON,
    // ITEM_CALCIUM,
    // ITEM_CARBOS,
    // ITEM_ZINC,
    // Progression
    ITEM_RARE_CANDY,
    // Berries - pinch stat berries
    ITEM_LIECHI_BERRY,
    ITEM_GANLON_BERRY,
    ITEM_SALAC_BERRY,
    ITEM_PETAYA_BERRY,
    ITEM_APICOT_BERRY,
    // Balls
    ITEM_SPORT_BALL,
    ITEM_DREAM_BALL,
    // Valuables
    ITEM_NUGGET,
    ITEM_BIG_PEARL,
    ITEM_STAR_PIECE,
    // Hold items - strong competitive utility
    ITEM_SCOPE_LENS,
    ITEM_WIDE_LENS,
    ITEM_ZOOM_LENS,
    ITEM_MUSCLE_BAND,
    ITEM_WISE_GLASSES,
    ITEM_METRONOME,
    ITEM_BRIGHT_POWDER,
    ITEM_WHITE_HERB,
    ITEM_MENTAL_HERB,
    ITEM_POWER_HERB,
    ITEM_DEEP_SEA_TOOTH,
    ITEM_DEEP_SEA_SCALE,
    ITEM_ROCKY_HELMET,
    ITEM_AIR_BALLOON,
    ITEM_SHED_SHELL,
    ITEM_SAFETY_GOGGLES,
    ITEM_UTILITY_UMBRELLA,
    ITEM_THROAT_SPRAY,
    ITEM_BLUNDER_POLICY,
    ITEM_EJECT_PACK,
    ITEM_LOADED_DICE,
    ITEM_COVERT_CLOAK,
    ITEM_PUNCHING_GLOVE,
    ITEM_MIRROR_HERB,
    // EV training items
    // ITEM_POWER_WEIGHT,
    // ITEM_POWER_BRACER,
    // ITEM_POWER_BELT,
    // ITEM_POWER_LENS,
    // ITEM_POWER_BAND,
    // ITEM_POWER_ANKLET,
    // TMs - strong competitive staples
    ITEM_TM001, // Focus Punch
    ITEM_TM002, // Dragon Claw
    ITEM_TM004, // Calm Mind
    ITEM_TM008, // Bulk Up
    ITEM_TM013, // Ice Beam
    ITEM_TM019, // Giga Drain
    ITEM_TM022, // Solar Beam
    ITEM_TM024, // Thunderbolt
    ITEM_TM029, // Psychic
    ITEM_TM030, // Shadow Ball
    ITEM_TM035, // Flamethrower
    ITEM_TM036, // Sludge Bomb
    ITEM_TM052, // Focus Blast
    ITEM_TM053, // Energy Ball
    ITEM_TM059, // Dragon Pulse
    ITEM_TM060, // Drain Punch
    ITEM_TM061, // Will-O-Wisp
    ITEM_TM074, // Gyro Ball
    ITEM_TM075, // Swords Dance
    ITEM_TM079, // Dark Pulse
    ITEM_TM080, // Rock Slide
    ITEM_TM081, // X-Scissor
    ITEM_TM084, // Poison Jab
    ITEM_TM086, // Grass Knot
    ITEM_TM089, // U-Turn
    ITEM_TM090, // Substitute
    ITEM_TM091, // Flash Cannon
};

static const u16 sVisibleItemPoolVeryRare[] = {
    // Healing / progression
    ITEM_PP_MAX,
    // ITEM_MAX_ELIXIR,
    // ITEM_HP_UP,
    // Evolution stones
    ITEM_FIRE_STONE,
    ITEM_WATER_STONE,
    ITEM_THUNDER_STONE,
    ITEM_LEAF_STONE,
    ITEM_MOON_STONE,
    ITEM_SUN_STONE,
    ITEM_SHINY_STONE,
    ITEM_DUSK_STONE,
    ITEM_DAWN_STONE,
    ITEM_OVAL_STONE,
    // Balls
    ITEM_BEAST_BALL,
    // Hold items - top tier
    ITEM_KINGS_ROCK,
    ITEM_METAL_COAT,
    ITEM_DRAGON_SCALE,
    ITEM_UP_GRADE,
    ITEM_RAZOR_CLAW,
    ITEM_RAZOR_FANG,
    ITEM_LIFE_ORB,
    ITEM_EXPERT_BELT,
    ITEM_FOCUS_SASH,
    ITEM_LEFTOVERS,
    ITEM_LUCKY_EGG,
    ITEM_EVIOLITE,
    ITEM_ASSAULT_VEST,
    ITEM_WEAKNESS_POLICY,
    ITEM_HEAVY_DUTY_BOOTS,
    // Progression
    ITEM_BOTTLE_CAP,
    // Valuables / misc
    ITEM_HEART_SCALE,
    ITEM_RARE_BONE,
    // TMs - elite moves
    ITEM_TM014, // Blizzard
    ITEM_TM015, // Hyper Beam
    ITEM_TM025, // Thunder
    ITEM_TM026, // Earthquake
    ITEM_TM038, // Fire Blast
    ITEM_TM050, // Overheat
    ITEM_TM064, // Explosion
    ITEM_TM068, // Giga Impact
    ITEM_TM071, // Stone Edge
    ITEM_TM076, // Stealth Rock
    ITEM_TM092, // Trick Room
};

static const u16 sVisibleItemPoolExtremelyRare[] = {
    // Top-tier competitive hold items
    ITEM_CHOICE_BAND,
    ITEM_CHOICE_SPECS,
    ITEM_CHOICE_SCARF,
    ITEM_TOXIC_ORB,
    ITEM_FLAME_ORB,
    // Ultimate utility
    ITEM_ABILITY_CAPSULE,
    ITEM_MASTER_BALL,
    // Ultimate progression
    ITEM_GOLD_BOTTLE_CAP,
    ITEM_ABILITY_PATCH,
    // Ultimate healing
    ITEM_SACRED_ASH,
    // Rarest berries
    ITEM_LANSAT_BERRY,
    ITEM_STARF_BERRY,
};

static const VisibleItemPool sVisibleItemPools[VISIBLE_ITEM_POOL_COUNT] = {
    [VISIBLE_ITEM_POOL_COMMON] = { sVisibleItemPoolCommon, NELEMS(sVisibleItemPoolCommon) },
    [VISIBLE_ITEM_POOL_GOOD] = { sVisibleItemPoolGood, NELEMS(sVisibleItemPoolGood) },
    [VISIBLE_ITEM_POOL_RARE] = { sVisibleItemPoolRare, NELEMS(sVisibleItemPoolRare) },
    [VISIBLE_ITEM_POOL_VERY_RARE] = { sVisibleItemPoolVeryRare, NELEMS(sVisibleItemPoolVeryRare) },
    [VISIBLE_ITEM_POOL_EXTREMELY_RARE] = { sVisibleItemPoolExtremelyRare, NELEMS(sVisibleItemPoolExtremelyRare) },
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

static int GetUpgradedVisibleItemPoolId(int poolId, u32 seed)
{
    while (poolId < VISIBLE_ITEM_POOL_COUNT - 1) {
        seed = HashVisibleItemBallSeed(seed ^ (u32)(poolId + 1) * 0x27D4EB2D);
        if (seed % 100 >= VISIBLE_ITEM_BALL_TIER_UP_CHANCE) {
            break;
        }

        poolId++;
    }

    return poolId;
}

static LocalMapObject *GetActiveVisibleItemBallObject(FieldSystem *fsys)
{
    u16 *lastTalkedPtr;
    LocalMapObject *mapObject;
    int objectId;

    if (fsys == NULL || fsys->mapObjectMan == NULL) {
        return NULL;
    }

    lastTalkedPtr = GetEvScriptWorkMemberAdrs(fsys, SCRIPTENV_LAST_TALKED);
    if (lastTalkedPtr == NULL) {
        return NULL;
    }

    objectId = *lastTalkedPtr;
    mapObject = GetMapObjectByID(fsys->mapObjectMan, objectId);
    if (mapObject == NULL) {
        return NULL;
    }

    if (mapObject->gfxId != ITEM_BALL_GFX_ID) {
        return NULL;
    }

    if (mapObject->evFlagId == 0) {
        return NULL;
    }

    if (mapObject->scriptId < ITEM_BALL_SCRIPT_MIN || mapObject->scriptId >= ITEM_BALL_SCRIPT_MAX) {
        return NULL;
    }

    return mapObject;
}

static const OBJECT_EVENT *GetVisibleItemBallEventAhead(FieldSystem *fsys)
{
    int targetX;
    int targetY;
    int facing;
    u32 i;

    if (fsys == NULL || fsys->map_events == NULL || fsys->playerAvatar == NULL) {
        return NULL;
    }

    targetX = GetPlayerXCoord(fsys->playerAvatar);
    targetY = GetPlayerYCoord(fsys->playerAvatar);
    facing = fsys->playerAvatar->mapObject != NULL ? fsys->playerAvatar->mapObject->curFacing : fsys->location->direction;

    switch (facing) {
    case DIR_NORTH:
        targetY--;
        break;
    case DIR_SOUTH:
        targetY++;
        break;
    case DIR_WEST:
        targetX--;
        break;
    case DIR_EAST:
        targetX++;
        break;
    }

    for (i = 0; i < fsys->map_events->num_object_events; i++) {
        const OBJECT_EVENT *objectEvent = &fsys->map_events->object_events[i];

        if (objectEvent->ovid != ITEM_BALL_GFX_ID) {
            continue;
        }

        if (objectEvent->flag == 0) {
            continue;
        }

        if (objectEvent->scr < ITEM_BALL_SCRIPT_MIN || objectEvent->scr >= ITEM_BALL_SCRIPT_MAX) {
            continue;
        }

        if (objectEvent->x == targetX && objectEvent->y == targetY) {
            return objectEvent;
        }
    }

    return NULL;
}

static u32 GetVisibleItemBallSpotSeed(FieldSystem *fsys)
{
    const OBJECT_EVENT *objectEvent = GetVisibleItemBallEventAhead(fsys);
    LocalMapObject *mapObject = GetActiveVisibleItemBallObject(fsys);

    if (objectEvent != NULL) {
        return ((u32)objectEvent->flag << 16) ^ (u32)objectEvent->scr;
    }

    if (mapObject == NULL) {
        return 0;
    }

    return ((u32)mapObject->evFlagId << 16) ^ (u32)mapObject->scriptId;
}

static int GetVisibleItemPoolId(u16 originalItem)
{
    // These mappings follow how scarce the original HGSS field pickup is,
    // rather than how generically useful the item is.
    switch (originalItem) {
    case ITEM_POTION:
    case ITEM_ANTIDOTE:
    case ITEM_PARALYZE_HEAL:
    case ITEM_AWAKENING:
    case ITEM_BURN_HEAL:
    case ITEM_ICE_HEAL:
    case ITEM_REPEL:
    case ITEM_POKE_BALL:
        return VISIBLE_ITEM_POOL_COMMON;

    case ITEM_SUPER_POTION:
    case ITEM_FULL_HEAL:
    case ITEM_ESCAPE_ROPE:
    case ITEM_GREAT_BALL:
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

    case ITEM_PP_MAX:
    case ITEM_MAX_ELIXIR:
    case ITEM_HP_UP:
    case ITEM_HEART_SCALE:
    case ITEM_RARE_BONE:
    case ITEM_SHINY_STONE:
    case ITEM_DAWN_STONE:
    case ITEM_OVAL_STONE:
    case ITEM_KINGS_ROCK:
    case ITEM_LIFE_ORB:
    case ITEM_UP_GRADE:
        return VISIBLE_ITEM_POOL_VERY_RARE;

    case ITEM_PROTECTOR:
    case ITEM_ELECTIRIZER:
    case ITEM_DUBIOUS_DISC:
        return VISIBLE_ITEM_POOL_EXTREMELY_RARE;
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
    poolId = GetUpgradedVisibleItemPoolId(poolId, seed);
    seed = HashVisibleItemBallSeed(seed ^ (u32)(poolId + 1) * 0x165667B1);

    pool = &sVisibleItemPools[poolId];
    poolIndex = seed % pool->count;
    if (pool->count > 1 && pool->items[poolIndex] == originalItem) {
        poolIndex = (poolIndex + 1) % pool->count;
    }

    return pool->items[poolIndex];
}
