#ifndef OVERWORLD_THROW_AWAY_WILD_H
#define OVERWORLD_THROW_AWAY_WILD_H

#include "overworld_throw_away_aim.h"
#include "overworld_pickup_route_wild.h"
struct PlayerHealthThrowServiceEntry;

/* Private query over the existing pickup-read callback ABI. */
#define OW_WILD_HELPER_PICKUP_THROW_QUERY_AWAY_LINE 4
#define OVERWORLD_THROW_AWAY_SETTINGS(distance, terrain) \
    ((u32)(distance) | ((u32)(terrain) << 8))

typedef struct OverworldThrowAwayWildCall {
    OverworldPickupRouteWildWorld *world;
    const struct PlayerHealthThrowServiceEntry *throwService;
    const OverworldThrowAwayAim *required;
    OverworldThrowAwayAim *result;
    u32 settings;
    u8 targetSlot, reserved[3];
} OverworldThrowAwayWildCall;

/* Only requiredNULL can choose an endpoint. requirednonNULL checks the same
 * saved endpoint and support Y. resultNULL checks without publishing a value.
 * Uses the existing native Landing path, never motion or a second workspace.
 * The caller owns the small local world, which this call adjusts for Cargo. */
BOOL OverworldThrowAwayWild_Read(const OverworldThrowAwayWildCall *);
#ifndef OVERWORLD_ACTOR_SYSTEM_HOST
typedef char ThrowAwayWildCallMustRemain24[sizeof(OverworldThrowAwayWildCall)==24?1:-1];
#endif
#endif
