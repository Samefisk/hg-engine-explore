#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int BOOL;
typedef uint32_t u32;
typedef int32_t s32;
#define TRUE 1
#define FALSE 0
#define MAPOBJECTFLAG_ACTIVE 1
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START 0xB0
#define OW_WILD_FOLLOWER_OBJECT_ID 253
#define OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID 0xF0
typedef struct LocalMapObject { u32 flags; int id, xCurr, yCurr; s32 posVec[3]; } LocalMapObject;
typedef struct MapObjectMan { LocalMapObject *objects; u32 object_count; } MapObjectMan;
typedef struct PlayerAvatar { LocalMapObject *mapObject; int x, y; } PlayerAvatar;
typedef struct FieldSystem { MapObjectMan *mapObjectMan; PlayerAvatar *playerAvatar; } FieldSystem;
enum { OVERWORLD_WILD_OCCUPANCY_OBJECTS, OVERWORLD_WILD_OCCUPANCY_NONPLAYER, OVERWORLD_WILD_OCCUPANCY_SURFACE, OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER };
static LocalMapObject *sOverworldWildCollisionIgnoredObject;
static int sOverworldWildPerfTargetScansThisFrame;
#define OW_WILD_PERF_INC(value) ((value)++)
#define OverworldWildSpawns_ObjectCurrentX(object) ((u32)(object)->xCurr)
#define OverworldWildSpawns_ObjectCurrentY(object) ((u32)(object)->yCurr)
static int GetPlayerXCoord(PlayerAvatar *player) { return player->x; }
static int GetPlayerYCoord(PlayerAvatar *player) { return player->y; }
/* @ACTUAL_C@ */
static int checks;
#define CHECK(expr) do { assert(expr); checks++; } while (0)
int main(void) {
    LocalMapObject object, player;
    MapObjectMan manager = { &object, 1 };
    PlayerAvatar avatar = { &player, 90, 91 };
    FieldSystem field = { &manager, &avatar };
    const int ids[] = { 1, 0xAF, 0xB0, 0xB9, 0xBA, 0xBF, 0xC0, 0xF0, 253 };
    for (unsigned id = 0; id < sizeof(ids)/sizeof(ids[0]); id++)
    for (int active = 0; active < 2; active++)
    for (int tile = 0; tile < 3; tile++)
    for (int height = 0; height < 2; height++)
    for (int ignored = 0; ignored < 2; ignored++)
    for (int collisionIgnored = 0; collisionIgnored < 2; collisionIgnored++) {
        memset(&object, 0, sizeof(object)); memset(&player, 0, sizeof(player));
        object.id = ids[id]; object.flags = active; object.xCurr = tile == 1 ? 11 : 10;
        object.yCurr = tile == 2 ? 21 : 20; object.posVec[1] = height ? 4096 : 0;
        sOverworldWildCollisionIgnoredObject = collisionIgnored ? &object : NULL;
        BOOL expected = active && !tile && !collisionIgnored && ids[id] != 0xF0
            && !(ids[id] >= 0xB0 && ids[id] < 0xBA);
#ifdef DISABLE_FOLLOWER_POKEMON
        expected = expected && ids[id] != 253;
#endif
        int before = sOverworldWildPerfTargetScansThisFrame;
        CHECK(OverworldWildSpawns_IsTileOccupiedByObject(&field, 10, 20) == expected);
        CHECK(sOverworldWildPerfTargetScansThisFrame == before + 1);
        CHECK(OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(&field, ignored ? &object : NULL, 10, 20) == (expected && !ignored));
        CHECK(OverworldWildSpawns_IsTileOccupiedOnSurface(&field, ignored ? &object : NULL, FALSE, 10, 20, 4096) == (expected && !ignored && height));
        CHECK(sOverworldWildPerfTargetScansThisFrame == before + 1);
    }
    sOverworldWildCollisionIgnoredObject = NULL;
    CHECK(!OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(NULL, NULL, 10, 20));
    CHECK(!OverworldWildSpawns_IsTileOccupiedOnSurface(NULL, NULL, TRUE, 10, 20, 0));
    field.mapObjectMan = NULL;
    avatar.x = 10; avatar.y = 20;
    CHECK(OverworldWildSpawns_IsTileOccupiedByObject(&field, 10, 20));
    CHECK(!OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(&field, NULL, 10, 20));
    CHECK(!OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, TRUE, 10, 20, 0));
    avatar.x = 90; avatar.y = 91;
    CHECK(!OverworldWildSpawns_IsTileOccupiedByObject(&field, 10, 20));
    field.mapObjectMan = &manager; manager.objects = NULL;
    player.xCurr = 10; player.yCurr = 20; player.posVec[1] = 4096;
    CHECK(OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, TRUE, 10, 20, 4096));
    CHECK(!OverworldWildSpawns_IsTileOccupiedOnSurface(&field, &player, TRUE, 10, 20, 4096));
    CHECK(!OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, FALSE, 10, 20, 4096));
    CHECK(!OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, TRUE, 10, 20, 0));
    sOverworldWildCollisionIgnoredObject = &player;
    CHECK(OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, TRUE, 10, 20, 4096));
    manager.objects = &player; player.flags = 1; player.id = 1;
    sOverworldWildCollisionIgnoredObject = NULL;
    CHECK(!OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(&field, NULL, 10, 20));
    CHECK(!OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, FALSE, 10, 20, 4096));
    field.playerAvatar = NULL; manager.objects = &object; object.flags = 1; object.id = 1;
    object.xCurr = 10; object.yCurr = 20; object.posVec[1] = 4096;
    CHECK(OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(&field, NULL, 10, 20));
    CHECK(OverworldWildSpawns_IsTileOccupiedOnSurface(&field, NULL, TRUE, 10, 20, 4096));
    printf("PASS occupancy actual-C parity: %d assertions\n", checks);
    return 0;
}
