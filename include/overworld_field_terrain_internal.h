#ifndef OVERWORLD_FIELD_TERRAIN_INTERNAL_H
#define OVERWORLD_FIELD_TERRAIN_INTERNAL_H

#include "map_teleport.h"

/* Private Field state. The resident code host must not retain this pointer. */
typedef struct OverworldFieldTerrainStreamRuntime {
    VecFx32 watchedAnchor;
    FieldSystem *fieldSystem;
    u32 fieldContext;
    u16 motionIdentity;
    u8 active;
    u8 reserved;
} OverworldFieldTerrainStreamRuntime;

OverworldFieldTerrainStreamResult OverworldFieldTerrainStream_Apply(
    const OverworldFieldTerrainStreamCall *call,
    OverworldFieldTerrainStreamRuntime *runtime);

/* Stateless Field leaf, physically hosted in the resident HP code gap. */
void OverworldFieldTerrainStream_RetireEmptyAxis(
    void *manager, const s32 *position);

#endif
