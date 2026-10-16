#ifndef OVERWORLD_MOUNT_JUMP_H
#define OVERWORLD_MOUNT_JUMP_H

#include "overworld_mount_internal.h"
#include "overworld_hop_clearance_native.h"

/* Mounted B Jump uses the shared Jump reach. Standing still, a held
 * direction Jumps two tiles; with no direction it is a short fast Hop in place. */
#define OVERWORLD_MOUNT_JUMP_REACH(framesPerTile) \
    ((framesPerTile) == 0 ? 0 : OVERWORLD_JUMP_REACH(framesPerTile))
#define OVERWORLD_MOUNT_JUMP_CRASH_DAMAGE 20
/* A short Jump hurts and knocks back only after this many landed tiles. */
#define OVERWORLD_MOUNT_JUMP_CRASH_MIN_DISTANCE 4
/* A non-water-runner that Jumps into water: rider damage, instant return. */
#define OVERWORLD_MOUNT_JUMP_WATER_DAMAGE 10
/* A crash damages only the rider and slides the pair one tile back. */
#define OVERWORLD_MOUNT_JUMP_CRASH_KNOCKBACK \
    OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(OW_WILD_BEHAVIOR_KNOCKBACK_SLIDE, 1)
#define OVERWORLD_MOUNT_JUMP_IN_PLACE_FRAMES 16
#define OVERWORLD_MOUNT_JUMP_IN_PLACE_ARC 12

/* Stock gSystem (0x021D110C) newKeys at +0x48; see pokeheartgold system.h. */
#define OVERWORLD_MOUNT_JUMP_SYSTEM_NEW_KEYS (0x021D110C + 0x48)

#define OVERWORLD_MOUNT_JUMP_IDLE 1u
#define OVERWORLD_MOUNT_JUMP_MARK_CRASH (1u << 1)
#define OVERWORLD_MOUNT_JUMP_APPLY_CRASH (1u << 2)

/* Boot-resident leaves: the boundary in overlay 155 and the Hop in place
 * after the mounted front admission in overlay 158. Linkers pin both. */
#define OVERWORLD_MOUNT_JUMP_BOUNDARY_ADDR 0x023BE140
#define OVERWORLD_MOUNT_JUMP_IN_PLACE_ADDR 0x023B86DA

u32 OverworldMountJump_Boundary(OverworldMountRuntimeState *state,
    const struct OverworldActorPolicyView *policy, u32 newKeys, u32 flags);
void OverworldMountJump_HopInPlace(OverworldMountRuntimeState *state,
    FIELD_PLAYER_AVATAR *avatar);

#endif
