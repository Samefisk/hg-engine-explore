#ifndef OVERWORLD_WATER_SINK_H
#define OVERWORLD_WATER_SINK_H

#include "map_events_internal.h"
#include "config.h"

/* Wild water sink presentation, hosted in the retired vanilla
 * follower-interaction graph of overlay 2 (loaded with the field); see
 * src/overworld_follower_release_overlay2/overworld_water_sink.c. */
#define OVERWORLD_WATER_SINK_ADDR 0x0224F8FC
/* Per-frame pass chained after the appearance capsule's RefreshAll. */
#define OVERWORLD_WATER_SINK_FRAME_ADDR 0x02250000
/* Splash placer called by the stock splash draw (overlay 1, 0x021FF6A8). */
#define OVERWORLD_WATER_SINK_SPLASH_ADDR 0x0224FFF0
/* Mirror placer called by the stock reflection draw (overlay 1, 0x021FDC48). */
#define OVERWORLD_WATER_SINK_MIRROR_ADDR 0x0224FFF8
/* Player step collision return hook (arm9 0x0205DAA2): mounted water running. */
#define OVERWORLD_WATER_SINK_PLAYER_COLLISION_ADDR 0x022504A0
/* Wild tall-grass rustle gate called by the stock move-start terrain update. */
#define OVERWORLD_WATER_SINK_GRASS_ADDR 0x022500B0
#define OVERWORLD_WATER_SINK_EASE 0x100
#define OVERWORLD_WATER_SINK_DEPTH \
    (OVERWORLD_WATER_SUBMERGE ? OVERWORLD_WATER_SUBMERGE_DEPTH : 0)

/* Private user SBC (24 bytes) plus the cropped quad display list (56 bytes). */
#define OVERWORLD_WATER_SINK_QUAD_WORDS 20

/* Pass a tile behavior after a terrain reconcile, or EASE once per motion
 * frame. Depth is in sprite pixels. While submerged, the bottom rows of this
 * object's sprite are cropped at the waterline; a hop arc lifts the body back
 * out. A submerged body gets the stock shallow-water splash; this owner clears
 * that splash flag for Wild objects, which the stock terrain update leaves
 * set (armips/asm/overworld_wild_shadow.s). Returns whether the reconciled
 * tile is deep water. */
BOOL OverworldWaterSink_Update(LocalMapObject *object, u32 behavior, u32 depth);

#endif
