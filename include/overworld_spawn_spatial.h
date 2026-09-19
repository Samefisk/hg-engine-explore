#ifndef OVERWORLD_SPAWN_SPATIAL_H
#define OVERWORLD_SPAWN_SPATIAL_H

#include "types.h"

typedef struct FieldSystem FieldSystem;
typedef struct LocalMapObject LocalMapObject;

/* The helper and selector overlays own fixed, resident spatial-query tails. */
#define OVERWORLD_SPAWN_SPATIAL_PLAYER_TILE_ADDR 0x023C7F60
#define OVERWORLD_SPAWN_SPATIAL_PLAYER_FRONT_TILE_ADDR 0x023C7F98
#define OVERWORLD_SPAWN_SPATIAL_CURRENT_MAP_OBJECT_ADDR 0x023C2200
#define OVERWORLD_SPAWN_SPATIAL_DISTANCE_FROM_PLAYER_ADDR 0x023C2230
#define OVERWORLD_SPAWN_SPATIAL_OBJECT_ON_PLAYER_TILE_ADDR 0x023C2264

BOOL OverworldSpawnSpatial_IsPlayerTile(
    FieldSystem *fieldSystem,
    int x,
    int y);
BOOL OverworldSpawnSpatial_IsPlayerFrontTile(
    FieldSystem *fieldSystem,
    int x,
    int y);
BOOL OverworldSpawnSpatial_IsCurrentMapObject(
    FieldSystem *fieldSystem,
    LocalMapObject *object);
int OverworldSpawnSpatial_DistanceFromPlayer(
    FieldSystem *fieldSystem,
    int x,
    int y);
BOOL OverworldSpawnSpatial_IsObjectOnPlayerTile(
    FieldSystem *fieldSystem,
    LocalMapObject *object);

#endif /* OVERWORLD_SPAWN_SPATIAL_H */
