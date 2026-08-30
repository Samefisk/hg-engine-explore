#ifndef OVERWORLD_WALK_DIRECTION_POLICY_H
#define OVERWORLD_WALK_DIRECTION_POLICY_H

#include "constants/buttons.h"
#include "types.h"

#define OVERWORLD_WALK_DIRECTION_NORTH 0
#define OVERWORLD_WALK_DIRECTION_SOUTH 1
#define OVERWORLD_WALK_DIRECTION_WEST 2
#define OVERWORLD_WALK_DIRECTION_EAST 3
#define OVERWORLD_WALK_DIRECTION_NORTH_WEST 4
#define OVERWORLD_WALK_DIRECTION_NORTH_EAST 5
#define OVERWORLD_WALK_DIRECTION_SOUTH_WEST 6
#define OVERWORLD_WALK_DIRECTION_SOUTH_EAST 7
#define OVERWORLD_WALK_DIRECTION_NONE 0xFF
#define OVERWORLD_WALK_DIRECTION_INLINE \
    static inline __attribute__((always_inline))
#ifdef __APPLE__
#define OVERWORLD_WALK_DIRECTION_RODATA
#else
#define OVERWORLD_WALK_DIRECTION_RODATA \
    __attribute__((section(".overworld_walk_module_rodata")))
#endif

OVERWORLD_WALK_DIRECTION_INLINE u8
OverworldWalkDirectionPolicy_FromKeys(u32 keys)
{
    BOOL north = (keys & PAD_KEY_UP) != 0;
    BOOL south = (keys & PAD_KEY_DOWN) != 0;
    BOOL west = (keys & PAD_KEY_LEFT) != 0;
    BOOL east = (keys & PAD_KEY_RIGHT) != 0;

    if (north != south && west != east) {
        if (north) {
            return west ? OVERWORLD_WALK_DIRECTION_NORTH_WEST
                        : OVERWORLD_WALK_DIRECTION_NORTH_EAST;
        }
        return west ? OVERWORLD_WALK_DIRECTION_SOUTH_WEST
                    : OVERWORLD_WALK_DIRECTION_SOUTH_EAST;
    }
    if (north != south) {
        return north ? OVERWORLD_WALK_DIRECTION_NORTH
                     : OVERWORLD_WALK_DIRECTION_SOUTH;
    }
    if (west != east) {
        return west ? OVERWORLD_WALK_DIRECTION_WEST
                    : OVERWORLD_WALK_DIRECTION_EAST;
    }
    return OVERWORLD_WALK_DIRECTION_NONE;
}

OVERWORLD_WALK_DIRECTION_INLINE u32
OverworldWalkDirectionPolicy_Key(u8 direction)
{
    static const u16 keys[] OVERWORLD_WALK_DIRECTION_RODATA = {
        PAD_KEY_UP,
        PAD_KEY_DOWN,
        PAD_KEY_LEFT,
        PAD_KEY_RIGHT,
        PAD_KEY_UP | PAD_KEY_LEFT,
        PAD_KEY_UP | PAD_KEY_RIGHT,
        PAD_KEY_DOWN | PAD_KEY_LEFT,
        PAD_KEY_DOWN | PAD_KEY_RIGHT,
    };

    return direction < 8 ? keys[direction] : 0;
}

OVERWORLD_WALK_DIRECTION_INLINE int
OverworldWalkDirectionPolicy_DeltaX(u8 direction)
{
    if (direction == OVERWORLD_WALK_DIRECTION_WEST
        || direction == OVERWORLD_WALK_DIRECTION_NORTH_WEST
        || direction == OVERWORLD_WALK_DIRECTION_SOUTH_WEST) {
        return -1;
    }
    return direction == OVERWORLD_WALK_DIRECTION_EAST
        || direction == OVERWORLD_WALK_DIRECTION_NORTH_EAST
        || direction == OVERWORLD_WALK_DIRECTION_SOUTH_EAST;
}

OVERWORLD_WALK_DIRECTION_INLINE int
OverworldWalkDirectionPolicy_DeltaY(u8 direction)
{
    if (direction == OVERWORLD_WALK_DIRECTION_NORTH
        || direction == OVERWORLD_WALK_DIRECTION_NORTH_WEST
        || direction == OVERWORLD_WALK_DIRECTION_NORTH_EAST) {
        return -1;
    }
    return direction == OVERWORLD_WALK_DIRECTION_SOUTH
        || direction == OVERWORLD_WALK_DIRECTION_SOUTH_WEST
        || direction == OVERWORLD_WALK_DIRECTION_SOUTH_EAST;
}

OVERWORLD_WALK_DIRECTION_INLINE u8
OverworldWalkDirectionPolicy_FromDelta(int dx, int dy)
{
    if (dx == 0) {
        return dy < 0 ? OVERWORLD_WALK_DIRECTION_NORTH
            : dy > 0 ? OVERWORLD_WALK_DIRECTION_SOUTH
                     : OVERWORLD_WALK_DIRECTION_NONE;
    }
    if (dy == 0) {
        return dx < 0 ? OVERWORLD_WALK_DIRECTION_WEST
                      : OVERWORLD_WALK_DIRECTION_EAST;
    }
    if (dy < 0) {
        return dx < 0 ? OVERWORLD_WALK_DIRECTION_NORTH_WEST
                      : OVERWORLD_WALK_DIRECTION_NORTH_EAST;
    }
    return dx < 0 ? OVERWORLD_WALK_DIRECTION_SOUTH_WEST
                  : OVERWORLD_WALK_DIRECTION_SOUTH_EAST;
}

OVERWORLD_WALK_DIRECTION_INLINE BOOL
OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn(u8 from, u8 to)
{
    if (from == OVERWORLD_WALK_DIRECTION_NONE
        || to == OVERWORLD_WALK_DIRECTION_NONE
        || from == to) {
        return FALSE;
    }
    return OverworldWalkDirectionPolicy_DeltaX(from)
            * OverworldWalkDirectionPolicy_DeltaX(to)
        + OverworldWalkDirectionPolicy_DeltaY(from)
            * OverworldWalkDirectionPolicy_DeltaY(to)
        > 0;
}

#undef OVERWORLD_WALK_DIRECTION_INLINE
#undef OVERWORLD_WALK_DIRECTION_RODATA

#endif // OVERWORLD_WALK_DIRECTION_POLICY_H
