#ifndef OVERWORLD_SPAWN_IDENTITY_H
#define OVERWORLD_SPAWN_IDENTITY_H

#include "overworld_wild_spawns_internal.h"

/* Wild presentation lifecycle; physically hosted in resident overlay 153.
 * No pointers are retained and no actor or motion state is created here.
 * Return -1 without mutation on conflict, otherwise the native deletion count.
 */
#define OVERWORLD_SPAWN_IDENTITY_ENTRY_ADDR 0x023C0000
int OverworldWildSpawnIdentity_PrepareSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildPresentationState *presentation);

#endif
