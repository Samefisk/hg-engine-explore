#include "../../include/overworld_wild_spawns_internal.h"

#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_behavior_condition_adapter.h"
#include "../../include/overworld_behavior_condition_runtime.h"
#include "../../include/overworld_condition_visibility.h"
#include "../../include/overworld_mount_action_adapter.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/overworld_mount_internal.h"

#include "../../include/config.h"

#ifdef IMPLEMENT_OVERWORLD_WILD_SPAWNS

__asm__(
    ".global OverworldWildSpawns_EnterAggroState\n"
    ".type OverworldWildSpawns_EnterAggroState, %function\n"
    ".set OverworldWildSpawns_EnterAggroState, 0x0225046D\n");

void OverworldWildSpawns_EnterAggroState(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *spawnedFollower);

#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/constants/maps.h"
#include "../../include/constants/save.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/map_teleport.h"
#include "../../include/overlay.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_spawn_identity.h"
#include "../../include/overworld_wild_occupancy.h"
#include "../../include/overworld_spawn_guard.h"
#include "../../include/overworld_spawn_spatial.h"

#define OverworldWildSpawns_IsNearActiveSpawn OverworldWildSpawnGuard_IsNearActiveSpawn
#define OverworldWildSpawns_IsSurfBehavior OverworldWildSpawnGuard_IsSurfBehavior
#define OverworldWildSpawns_IsPlayerTile OverworldSpawnSpatial_IsPlayerTile
#define OverworldWildSpawns_IsPlayerFrontTile OverworldSpawnSpatial_IsPlayerFrontTile
#define OverworldWildSpawns_IsCurrentMapObject OverworldSpawnSpatial_IsCurrentMapObject
#define OverworldWildSpawns_DistanceFromPlayer OverworldSpawnSpatial_DistanceFromPlayer
#define OverworldWildSpawns_IsObjectOnPlayerTile OverworldSpawnSpatial_IsObjectOnPlayerTile
#include "../../include/pokemon.h"
#include "../../include/pokemon_storage_system.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/sound.h"
#include "../../include/sprite.h"
#include "../../include/task.h"

extern BOOL OverworldWildSpawns_AcquireMonLock(struct PartyPokemon *pokemon);
extern BOOL OverworldWildSpawns_ReleaseMonLock(
    struct PartyPokemon *pokemon,
    BOOL locked);
extern u32 OverworldWildSpawns_ReadMonData(
    struct PartyPokemon *pokemon, int field, void *buffer);
extern BOOL OverworldWildSpawns_MonIsShiny(struct PartyPokemon *pokemon);
extern u8 OverworldWildSpawns_MonGender(u16 species, u32 personality);
extern int OverworldWildSpawns_PlayerX(FIELD_PLAYER_AVATAR *avatar);
extern int OverworldWildSpawns_PlayerY(FIELD_PLAYER_AVATAR *avatar);
extern u8 OverworldWildSpawns_MetatileBehavior(FieldSystem *fieldSystem, int x, int y);
extern void *OverworldWildSpawns_NARC_ctor(u32 narcId, u32 heapId);
extern void OverworldWildSpawns_NARC_dtor(void *narc);
extern u16 OverworldWildSpawns_NARC_GetFileCount(void *narc);
extern u32 OverworldWildSpawns_NARC_GetMemberSize(void *narc, u32 member);
extern void OverworldWildSpawns_NARC_ReadWholeMember(void *narc, u32 member, void *dest);
extern BOOL OverworldWildSpawns_IsSingleMovementActive(LocalMapObject *object);
/* Same resident getter ABI; direct Thumb calls fit this overlay's BL range
 * and avoid long-call veneers in its fixed code slot. */
#define GetPlayerXCoord OverworldWildSpawns_PlayerX
#define GetPlayerYCoord OverworldWildSpawns_PlayerY
#define GetMonData OverworldWildSpawns_ReadMonData
#define MonIsShiny OverworldWildSpawns_MonIsShiny
#define PokeSexGetMonsNo OverworldWildSpawns_MonGender
#define GetMetatileBehaviorAt OverworldWildSpawns_MetatileBehavior
#define NARC_ctor OverworldWildSpawns_NARC_ctor
#define NARC_dtor OverworldWildSpawns_NARC_dtor
#define NARC_GetFileCount OverworldWildSpawns_NARC_GetFileCount
#define NARC_GetMemberSize OverworldWildSpawns_NARC_GetMemberSize
#define NARC_ReadWholeMember OverworldWildSpawns_NARC_ReadWholeMember
#define MapObject_IsSingleMovementActive OverworldWildSpawns_IsSingleMovementActive

/* Absolute linker imports do not carry ELF Thumb-function metadata. Mark the
 * resident helper entries here so direct BL relocations do not need veneers. */
__asm__(
    ".thumb\n"
    ".global OverworldWildSpawns_AcquireMonLock\n.thumb_func\n.thumb_set OverworldWildSpawns_AcquireMonLock, 0x0206DD40\n"
    ".global OverworldWildSpawns_ReleaseMonLock\n.thumb_func\n.thumb_set OverworldWildSpawns_ReleaseMonLock, 0x0206DD8C\n"
    ".global OverworldWildSpawns_ReadMonData\n.thumb_func\n.thumb_set OverworldWildSpawns_ReadMonData, 0x0206E540\n"
    ".global OverworldWildSpawns_MonIsShiny\n.thumb_func\n.thumb_set OverworldWildSpawns_MonIsShiny, 0x0207003C\n"
    ".global OverworldWildSpawns_MonGender\n.thumb_func\n.thumb_set OverworldWildSpawns_MonGender, 0x0206FFC8\n"
    ".global OverworldWildSpawns_PlayerX\n.thumb_func\n.thumb_set OverworldWildSpawns_PlayerX, 0x0205C67C\n"
    ".global OverworldWildSpawns_PlayerY\n.thumb_func\n.thumb_set OverworldWildSpawns_PlayerY, 0x0205C688\n"
    ".global OverworldWildSpawns_MetatileBehavior\n.thumb_func\n.thumb_set OverworldWildSpawns_MetatileBehavior, 0x02054918\n"
    ".global OverworldWildSpawns_NARC_ctor\n.thumb_func\n.thumb_set OverworldWildSpawns_NARC_ctor, 0x02007688\n"
    ".global OverworldWildSpawns_NARC_dtor\n.thumb_func\n.thumb_set OverworldWildSpawns_NARC_dtor, 0x0200770C\n"
    ".global OverworldWildSpawns_NARC_GetFileCount\n.thumb_func\n.thumb_set OverworldWildSpawns_NARC_GetFileCount, 0x020078E8\n"
    ".global OverworldWildSpawns_NARC_GetMemberSize\n.thumb_func\n.thumb_set OverworldWildSpawns_NARC_GetMemberSize, 0x020077E8\n"
    ".global OverworldWildSpawns_NARC_ReadWholeMember\n.thumb_func\n.thumb_set OverworldWildSpawns_NARC_ReadWholeMember, 0x0200778C\n"
    ".global OverworldWildSpawns_IsSingleMovementActive\n.thumb_func\n.thumb_set OverworldWildSpawns_IsSingleMovementActive, 0x0205F648\n"
    ".thumb_func\n.thumb_set OverworldWalk_ClampTime, 0x023BF488\n"
    ".thumb_func\n.thumb_set OverworldWalk_SkidTiles, 0x023BF4D6\n"
    ".thumb_func\n.thumb_set OverworldWalk_DirectionKey, 0x023BF586\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaX, 0x023BF59C\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaY, 0x023BF5BE\n"
    ".thumb_func\n.thumb_set OverworldWalk_DirectionFromDelta, 0x023BF68C\n"
    ".thumb_func\n.thumb_set OverworldWalk_DiagonalFacing, 0x023BF74E\n"
    ".thumb_func\n.thumb_set OverworldWildSpawnIdentity_PrepareSlot, 0x023C0000\n"
    ".global OverworldWildOccupancy_Query\n.thumb_func\n.thumb_set OverworldWildOccupancy_Query, 0x023C0184\n"
    ".global OverworldWildSpawnGuard_Read\n.thumb_func\n.thumb_set OverworldWildSpawnGuard_Read, 0x023C025C\n"
    ".global OverworldWildSpawnGuard_IsNearActiveSpawn\n.thumb_func\n.thumb_set OverworldWildSpawnGuard_IsNearActiveSpawn, 0x023C034C\n"
    ".global OverworldWildSpawnGuard_IsSurfBehavior\n.thumb_func\n.thumb_set OverworldWildSpawnGuard_IsSurfBehavior, 0x023C03D0\n"
    ".global OverworldSpawnSpatial_IsPlayerTile\n.thumb_func\n.thumb_set OverworldSpawnSpatial_IsPlayerTile, 0x023C7F60\n"
    ".global OverworldSpawnSpatial_IsPlayerFrontTile\n.thumb_func\n.thumb_set OverworldSpawnSpatial_IsPlayerFrontTile, 0x023C7F98\n"
    ".global OverworldSpawnSpatial_IsCurrentMapObject\n.thumb_func\n.thumb_set OverworldSpawnSpatial_IsCurrentMapObject, 0x023C2200\n"
    ".global OverworldSpawnSpatial_DistanceFromPlayer\n.thumb_func\n.thumb_set OverworldSpawnSpatial_DistanceFromPlayer, 0x023C2230\n"
    ".global OverworldSpawnSpatial_IsObjectOnPlayerTile\n.thumb_func\n.thumb_set OverworldSpawnSpatial_IsObjectOnPlayerTile, 0x023C2264\n"
    ".global OverworldConditionVisibility_TraceBlocked\n.thumb_func\n.thumb_set OverworldConditionVisibility_TraceBlocked, 0x023C7EA8\n"
    ".global OverworldConditionVisibility_PopulateWorld\n.thumb_func\n.thumb_set OverworldConditionVisibility_PopulateWorld, 0x023C7DF8\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_SelectMovementLocomotion, 0x023B6BB8\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_SelectMovementTarget, 0x023B6BCC\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_AcknowledgeSharedMotion, 0x023BD3C4\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_MovementDirectionDeltaX, 0x023BF59C\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_MovementDirectionDeltaY, 0x023BF5BE\n"
    ".thumb_func\n.thumb_set OverworldActor_PlayStompSound, 0x023BA118\n");

/* These core exports are Thumb too. Preserve their ELF function metadata so
 * compiler helpers and facing cannot enter a generated ARM-mode veneer. */
__asm__(
    ".thumb\n"
    ".global __aeabi_uidivmod\n.thumb_func\n.thumb_set __aeabi_uidivmod, 0x023DEE4C\n"
    ".global memset\n.thumb_func\n.thumb_set memset, 0x023DEEA2\n"
    ".global __aeabi_idivmod\n.thumb_func\n.thumb_set __aeabi_idivmod, 0x023DEE44\n"
    ".global __gnu_thumb1_case_uhi\n.thumb_func\n.thumb_set __gnu_thumb1_case_uhi, 0x023DEE78\n"
    ".global __aeabi_idiv\n.thumb_func\n.thumb_set __aeabi_idiv, 0x023DEE44\n"
    ".global OverworldWildSpawns_ApplyFacePlayerFacing\n.thumb_func\n.thumb_set OverworldWildSpawns_ApplyFacePlayerFacing, 0x023D98F6\n"
    ".global __gnu_thumb1_case_uqi\n.thumb_func\n.thumb_set __gnu_thumb1_case_uqi, 0x023DEE54\n"
    ".global memcpy\n.thumb_func\n.thumb_set memcpy, 0x023DEEBE\n");

/* Tail-call frequent resident services. The wrappers share their fixed entry
 * literals so this fixed-size overlay does not repeat indirect-call setup. */
__asm__(
    ".thumb\n"
    ".align 2\n"
    ".global OverworldWildSpawns_MountCancel\n.thumb_func\n"
    "OverworldWildSpawns_MountCancel:\n"
    "ldr r3, 1f\n"
    "ldr r3, [r3, #12]\n"
    "bx r3\n"
    ".global OverworldWildSpawns_MountIsActive\n.thumb_func\n"
    "OverworldWildSpawns_MountIsActive:\n"
    "ldr r3, 1f\n"
    "ldr r3, [r3, #24]\n"
    "bx r3\n"
    ".align 2\n"
    "1: .word 0x023BB600\n"
    ".global OverworldWildSpawns_BuildDirectedDirections\n.thumb_func\n"
    "OverworldWildSpawns_BuildDirectedDirections:\n"
    "ldr r3, 2f\n"
    "ldr r3, [r3, #56]\n"
    "bx r3\n"
    ".align 2\n"
    "2: .word 0x023C0400\n"
    ".global OverworldWildSpawns_PopulationControl\n.thumb_func\n"
    "OverworldWildSpawns_PopulationControl:\n"
    "ldr r3, 3f\n"
    "ldr r3, [r3, #12]\n"
    "bx r3\n"
    ".align 2\n"
    "3: .word 0x023B6B98\n"
    ".global OverworldWildSpawns_ReduceWalk\n.thumb_func\n"
    "OverworldWildSpawns_ReduceWalk:\n"
    "ldr r3, 4f\n"
    "ldr r3, [r3, #8]\n"
    "ldr r3, [r3, #12]\n"
    "bx r3\n"
    ".align 2\n"
    "4: .word 0x023B6BA8\n");

/* Stock map_object.c implements these as plain word reads and flag writes.
 * Keep the stock u32 coordinate result and live-object precondition. Inlining
 * only this engine adapter avoids repeated long-call setup in the fixed slot. */
typedef char OverworldWildObjectAccessorLayoutMustMatchStock[
    offsetof(LocalMapObject, flags) == 0
        && offsetof(LocalMapObject, xCurr) == 0x64
        && offsetof(LocalMapObject, yCurr) == 0x6C
        && sizeof(((LocalMapObject *)0)->flags) == sizeof(u32)
        && sizeof(((LocalMapObject *)0)->xCurr) == sizeof(u32)
        && sizeof(((LocalMapObject *)0)->yCurr) == sizeof(u32)
        ? 1 : -1];

static inline __attribute__((always_inline)) u32
OverworldWildSpawns_ObjectCurrentX(LocalMapObject *object)
{
    return (u32)object->xCurr;
}

static inline __attribute__((always_inline)) u32
OverworldWildSpawns_ObjectCurrentY(LocalMapObject *object)
{
    return (u32)object->yCurr;
}

static inline __attribute__((always_inline)) void
OverworldWildSpawns_SetObjectFlags(LocalMapObject *object, u32 bits)
{
    object->flags |= bits;
}

static inline __attribute__((always_inline)) void
OverworldWildSpawns_ClearObjectFlags(LocalMapObject *object, u32 bits)
{
    object->flags &= ~bits;
}

#ifndef TYPE_NORMAL
#define TYPE_NORMAL 0
#endif
#ifndef TYPE_FIGHTING
#define TYPE_FIGHTING 1
#endif
#ifndef TYPE_FLYING
#define TYPE_FLYING 2
#endif
#ifndef TYPE_POISON
#define TYPE_POISON 3
#endif
#ifndef TYPE_GROUND
#define TYPE_GROUND 4
#endif
#ifndef TYPE_ROCK
#define TYPE_ROCK 5
#endif
#ifndef TYPE_BUG
#define TYPE_BUG 6
#endif
#ifndef TYPE_GHOST
#define TYPE_GHOST 7
#endif
#ifndef TYPE_STEEL
#define TYPE_STEEL 8
#endif
#ifndef TYPE_FAIRY
#define TYPE_FAIRY 9
#endif
#ifndef TYPE_FIRE
#define TYPE_FIRE 10
#endif
#ifndef TYPE_WATER
#define TYPE_WATER 11
#endif
#ifndef TYPE_GRASS
#define TYPE_GRASS 12
#endif
#ifndef TYPE_ELECTRIC
#define TYPE_ELECTRIC 13
#endif
#ifndef TYPE_PSYCHIC
#define TYPE_PSYCHIC 14
#endif
#ifndef TYPE_ICE
#define TYPE_ICE 15
#endif
#ifndef TYPE_DRAGON
#define TYPE_DRAGON 16
#endif
#ifndef TYPE_DARK
#define TYPE_DARK 17
#endif
#ifndef TYPE_TYPELESS
#define TYPE_TYPELESS 18
#endif
#ifndef TYPE_STELLAR
#define TYPE_STELLAR 19
#endif

void LONG_CALL GX_EngineAToggleLayers(int planes, int status);

typedef void (*OverworldWildMapObjectMovementFunc)(LocalMapObject *object);

#define OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT 10
#define OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN 10
#define OW_WILD_REFILL_BASE_INTERVAL_FRAMES 60
#define OW_WILD_PLAYER_BALL_PERSONAL_RECORD_SIZE 28
#define OW_WILD_PLAYER_BALL_PERSONAL_CATCH_RATE_OFFSET 8
#define OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_PARTY (-1)
#define OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE (-2)
#define OW_WILD_PLAYER_BALL_PC_STORAGE_SAVE_BLOCK 41
#define OW_WILD_FISHING_SPAWN_CHANCE_PERCENT 20
#define OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN 4
#define OW_WILD_SPAWN_MIN_DISTANCE 4
#define OW_WILD_SPAWN_MAX_DISTANCE 8
#define OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE 1
#define OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE OW_WILD_SPAWN_MAX_DISTANCE
#define OW_WILD_DESPAWN_DISTANCE 14
#define OW_WILD_DESPAWN_CULL_DISTANCE (OW_WILD_DESPAWN_DISTANCE + 2)
#define OW_WILD_SPAWN_MIN_MON_DISTANCE 3
#define OW_WILD_AMBIENT_CRY_MIN_COOLDOWN_STEPS 48
#define OW_WILD_AMBIENT_CRY_RANDOM_COOLDOWN_STEPS 96
#define OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK 4
#define OW_WILD_OBJECT_ID_START 0xE0
#define OW_WILD_TELEPORT_FLICKER_OBJECT_ID_START 0xD0
#define OW_WILD_VAR_SPECIAL_LAST_TALKED 0x800D
#define OW_WILD_FLEE_GRACE_STEPS 3
#define OW_WILD_TILE_ENCOUNTER_GRASS 2
#define OW_WILD_TILE_LONG_GRASS 3
#define OW_WILD_TILE_HEADBUTT 6
#define OW_WILD_TILE_LEDGE_EAST 56
#define OW_WILD_TILE_LEDGE_WEST 57
#define OW_WILD_TILE_LEDGE_NORTH 58
#define OW_WILD_TILE_LEDGE_SOUTH 59
typedef char OverworldWildLedgeIdsMustStayContiguous[
    OW_WILD_TILE_LEDGE_WEST == OW_WILD_TILE_LEDGE_EAST + 1
        && OW_WILD_TILE_LEDGE_NORTH == OW_WILD_TILE_LEDGE_EAST + 2
        && OW_WILD_TILE_LEDGE_SOUTH == OW_WILD_TILE_LEDGE_EAST + 3
        ? 1 : -1];
#define OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY 0
#define OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY 0
#define OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY 0
#define OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY 0
#define OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY 0
#define OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE 0
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_IDLE_OBJECT_MOVEMENT 1
#define OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_TRACE 0
#define OW_WILD_SPAWNER_PERF_DIAGNOSTICS 0
#define OW_WILD_SPAWNER_IMMEDIATE_AI_AFTER_COMMAND_COMPLETION 1
#define OW_WILD_SPAWNER_PROFILE_CACHE_FAST_HIT 1
#define OW_WILD_SPAWNER_SINGLE_PASS_WANDER_VALIDATION 1
#define OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN 0
#define OW_WILD_SPAWNER_MOVEMENT_RANGE 32
#define OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS 32
#define OW_WILD_SPAWNER_MOVEMENT_FRAME_TASK_PRIORITY 1300
#define OW_WILD_SPAWNER_MOVEMENT_FRAME_DECISION_INTERVAL 1
#define OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS 4
#define OW_WILD_MAP_OBJECT_BLOCKED_BY_OBJECT (1u << 2)
#define OW_WILD_SPAWNER_UNTANGLE_MAX_DIRECTIONS 4
#define OW_WILD_SPAWNER_HOP_PLAN_MAX_DIRECTIONS 8
#define OW_WILD_SPAWNER_HOP_PLAN_MAX_HOPS 5
#define OW_WILD_SPAWNER_HOP_PLAN_NODE_COUNT 64
#define OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES 16
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u << (slot))
#define OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT 16
#define OW_WILD_SPAWNER_FRAME_WORK_GLOBAL 0x80000000
#define OW_WILD_SPAWNER_MOVEMENT_LOOK_UP_COMMAND 0x00
#define OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT OW_WILD_BEHAVIOR_WALK_TIME_DEFAULT
#define OW_WILD_SPAWNER_MOVEMENT_SPEED_1_COMMAND 0x08
#define OW_WILD_SPAWNER_MOVEMENT_SPEED_2_COMMAND 0x0C
#define OW_WILD_SPAWNER_MOVEMENT_SPEED_3_COMMAND 0x10
#define OW_WILD_SPAWNER_MOVEMENT_SPEED_4_COMMAND 0x14
#define OW_WILD_SPAWNER_REAL_FRAMES_PER_LOGICAL_TICK 2
#define OW_WILD_SPAWNER_REAL_FRAMES_TO_LOGICAL_TICKS(frames) \
    (((frames) + OW_WILD_SPAWNER_REAL_FRAMES_PER_LOGICAL_TICK - 1) \
        / OW_WILD_SPAWNER_REAL_FRAMES_PER_LOGICAL_TICK)
#define OW_WILD_SPAWNER_MOVEMENT_LEDGE_JUMP_COMMAND 0x38
#define OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_1_COMMAND 0x34
#define OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_2_COMMAND 0x38
#define OW_WILD_SPAWNER_CANOPY_HOPPER_TRAVEL_COMMAND OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_1_COMMAND
#define OW_WILD_SPAWNER_CANOPY_HOPPER_WAIT_JUMP_LEFT_2_COMMAND 0x5E
#define OW_WILD_SPAWNER_CANOPY_HOPPER_WAIT_JUMP_RIGHT_2_COMMAND 0x5F
#define OW_WILD_SPAWNER_CANOPY_HOPPER_LOCK_DIR_COMMAND 0x47
#define OW_WILD_SPAWNER_CANOPY_HOPPER_RELEASE_DIR_COMMAND 0x48
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND 0x49
#define OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND 0x3E
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND 0x4A
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_END_COMMAND 0xFE
#define OW_WILD_SPAWNER_CUSTOM_JUMP_COMMAND OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_1_COMMAND
#define OW_WILD_SPAWNER_CUSTOM_JUMP_DELTA_FX32 0x2000
#define OW_WILD_SPAWNER_CUSTOM_JUMP_TYPE 3
#define OW_WILD_SPAWNER_CUSTOM_JUMP_ARC_TABLE 0
#define OW_WILD_SPAWNER_CUSTOM_JUMP_ARC_FULL 0x1000
#define OW_WILD_SPAWNER_CUSTOM_JUMP_FRAMES_PER_TILE 4
#define OW_WILD_SPAWNER_PIDGEY_MOVEMENT_SPEED 3
#define OW_WILD_SPAWNER_SPOT_RANGE 3
#define OW_WILD_SPAWNER_SWARM_MAX_EXTRA_SPAWNS 3
#define OW_WILD_SPAWNER_CIRCLE_PLAYER_MAX_RADIUS 8
#define OW_WILD_SPAWNER_CLOSE_ALERT_RADIUS 1
#define OW_WILD_SPAWNER_SPOT_EMOTE_PARTNER_PREP_COMMAND 0x49
#define OW_WILD_SPAWNER_SPOT_EMOTE_JUMP_SITE_COMMAND 0x30
#define OW_WILD_SPAWNER_SPOT_EMOTE_FREEZE_COMMAND 0x3E
#define OW_WILD_SPAWNER_SPOT_EMOTE_PARTNER_RESTORE_COMMAND 0x4A
#define OW_WILD_SPAWNER_ALERT_TIME_AUTO 0
#define OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP 64
#define OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES 10
#define OW_WILD_SPAWNER_THROW_RESERVATION_DECISIONS 120
#define OW_WILD_SPAWNER_THROW_WINDUP_FRAMES 20
#define OW_WILD_SPAWNER_THROW_RECOVERY_FRAMES 60
#define OW_WILD_SPAWNER_SPOT_EMOTE_JUMPS_DEFAULT 1
#define OW_WILD_SPAWNER_SPOT_EMOTE_JUMPS_SPEED_3 2
#define OW_WILD_SPAWNER_SPOT_EMOTE_SE SEQ_SE_GS_UFO_JUMP
#define OW_WILD_SPAWNER_HOP_START_SE SEQ_SE_DP_DANSA
#define OW_WILD_SPAWNER_CANOPY_HOP_RUSTLE_SE SEQ_SE_DP_FPASA2
#define OW_WILD_SPAWNER_CANOPY_HOP_BALLOON_SE SEQ_SE_PL_BALLOON03
#define OW_WILD_SPAWNER_CANOPY_HOP_SOUND_VARIANTS 2
#define OW_WILD_SPAWNER_HOP_START_SE_SUPPRESS_FRAMES 4
#define OW_WILD_MAP_OBJECT_UNPAUSE_MOVEMENT ((OverworldWildMapObjectMovementFunc)0x0205F709)
#define OW_WILD_SPAWNER_TIRED_AFTER_STEPS 5
#define OW_WILD_SPAWNER_TIRED_USE_FOLLOWER_BUBBLE 0
#define OW_WILD_SPAWNER_TIRED_USE_DIRECT_BUBBLE_CREATOR 1
#define OW_WILD_SPAWNER_TIRED_STOP_BUBBLE_SE 0
#define OW_WILD_SPAWNER_TIRED_PLAY_COOLDOWN_SE 0
#define OW_WILD_SPAWNER_BUBBLE_ID_HEART 0
#define OW_WILD_SPAWNER_BUBBLE_ID_SMILE 1
#define OW_WILD_SPAWNER_BUBBLE_ID_ANGRY 2
#define OW_WILD_SPAWNER_BUBBLE_ID_SAD 3
#define OW_WILD_SPAWNER_BUBBLE_ID_MILDLY_HAPPY 4
#define OW_WILD_SPAWNER_BUBBLE_ID_DISAPPROVAL 5
#define OW_WILD_SPAWNER_BUBBLE_ID_MUSIC_NOTE 6
#define OW_WILD_SPAWNER_BUBBLE_ID_QUESTION_MARK 7
#define OW_WILD_SPAWNER_BUBBLE_ID_EXCLAMATION_MARK 8
#define OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET 9
#define OW_WILD_SPAWNER_BUBBLE_ID_DESPAIR 10
#define OW_WILD_SPAWNER_BUBBLE_ID_POISON 11
#define OW_WILD_SPAWNER_BUBBLE_ID_ELLIPSIS 12
#define OW_WILD_SPAWNER_BUBBLE_ID_SLEEP 13
#define OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE 0
#define OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN OW_WILD_SPAWNER_BUBBLE_ID_HEART
#define OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MAX OW_WILD_SPAWNER_BUBBLE_ID_SLEEP
#define OW_WILD_SPAWNER_TIRED_BUBBLE_ID OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET
#define OW_WILD_SPAWNER_TIRED_EMOTE_COMMAND 0x65
#define OW_WILD_SPAWNER_TIRED_EMOTE_FRAMES 96
#define OW_WILD_SPAWNER_TIRED_SPOT_COOLDOWN_FRAMES 180
#define OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME 4
#define OW_WILD_SPAWNER_ASLEEP_REST_TIMER 255
#define OW_WILD_SPAWNER_TIRED_WANDER_PAUSE_FRAMES 24
#define OW_WILD_SPAWNER_TIRED_EMOTE_SE SEQ_SE_PL_BALLOON05
#define OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES 32
#define OW_WILD_SPAWNER_WALK_STOP_SKID_PAUSE_FRAMES 8
#define OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING 0x80
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_STEP 0x40
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID 0x20
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_DUST 0x10
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_FLAT_MASK 0x60
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER 0x90
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK 0xF0
#define OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_CENTER 0x95
#define OW_WILD_SPAWNER_TELEPORT_DISTANCE 5
#define OW_WILD_SPAWNER_TELEPORT_FLICKER_CHANCE_PERCENT 100
#define OW_WILD_SPAWNER_TELEPORT_FLICKER_FRAMES 18
#define OW_WILD_SPAWNER_TELEPORT_POST_COOLDOWN_FRAMES 30
#define OW_WILD_SPAWNER_TELEPORT_FAIL_COOLDOWN_FRAMES 8
#define OW_WILD_SPAWNER_TELEPORT_FLICKER_VISIBLE_FRAMES 5
#define OW_WILD_SPAWNER_TELEPORT_FLICKER_HIDDEN_FRAMES 2
#define OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_VISIBLE_FRAMES 3
#define OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_HIDDEN_FRAMES 2
#define OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES \
    (OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_VISIBLE_FRAMES + OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_HIDDEN_FRAMES)
#define OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_REAL_FLICKER 0
#define OW_WILD_SPAWNER_TELEPORT_RANGE (OW_WILD_SPAWNER_MOVEMENT_RANGE * 2)
#define OW_WILD_SPAWNER_PREVIOUS_TILE_NONE -1
#define OW_WILD_SPAWNER_PREVIOUS_TILE_LOGICAL 1
#define OW_WILD_SPAWNER_WALK_CRASH_SE SEQ_SE_DP_WALL_HIT
#define OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE 16
#define OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS 0
#define OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES 1
#define OW_WILD_SPAWNER_CANOPY_SHIFT_NORTH_LAND_ANCHORS 0
#define OW_WILD_SPAWNER_CANOPY_NORTH_LAND_SHIFT_TILES 1
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_VISIBILITY_BASELINE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE 0
#define OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE 0
#define OW_WILD_SPAWNER_CUSTOM_JUMP_ALLOW_DIAGONAL 1
#define OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_OFFSET 1
#define OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_MAX_SECONDARY_TILES 8
#define OW_WILD_SPAWNER_CUSTOM_JUMP_SYNC_LOGICAL_SECONDARY 1
#define OW_WILD_SPAWNER_CUSTOM_JUMP_SPIN_STEP_MASK 0x03
#define OW_WILD_SPAWNER_CUSTOM_JUMP_SPIN_SPEED_MASK 0x0F
#define OW_WILD_SPAWNER_CUSTOM_JUMP_POST_RESTORE_FINALIZE 1
#define OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_SETTLE 1
#define OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE 0
#define OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_FRAMES 12
#define OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_ENABLED \
    (OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_SETTLE \
        && OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE \
        && OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_FRAMES != 0)
#define OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS 0
#define OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE 0
#define OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE_MIN_TILES 4
#define OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE_KEYS \
    (PAD_BUTTON_L | PAD_BUTTON_R)
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES 3
#define OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE 8
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES 8
#define OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET 1
#define OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS 0x00000180
#define OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK \
    OverworldWildSpawns_MankeyTreeTopDrawWrapper
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_FRAMES 60
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_2 2
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_4 4
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_8 8
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_PHASES 4
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED 0
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ENABLED 0
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_FRAMES 90
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ID OW_WILD_SPAWNER_BUBBLE_ID_EXCLAMATION_MARK
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_FRAMES 45
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_ID OW_WILD_SPAWNER_BUBBLE_ID_EXCLAMATION_MARK
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_LATE_DRAW_EFFECT_ENABLED 0
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED 0
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_PRIORITY_OVERRIDE_ENABLED 0
#define OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED 0
#define OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PATH_MAX_JUMPS 4
#define OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_BASE_COOLDOWN_FRAMES 60
#define OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_MAX_COOLDOWN_FRAMES 240
#define OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_MAX_COUNT 4
#define OW_WILD_SPAWNER_CANOPY_HOPPER_TREE_ALERT_RADIUS 5
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES 30
#define OW_WILD_SPAWNER_CANOPY_HOPPER_SEGMENT_SETTLE_FRAMES 8
#define OW_WILD_SPAWNER_CANOPY_HOPPER_COOLDOWN_FRAMES 40
#define OW_WILD_SPAWNER_CUSTOM_JUMP_MIN_TILES OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES
#define OW_WILD_SPAWNER_CUSTOM_JUMP_MAX_TILES OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_RADIUS (OW_WILD_SPAWNER_CANOPY_HOPPER_RANGE - 1)
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_DIAMETER (OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_RADIUS * 2 + 1)
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_NODE_COUNT \
    (OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_DIAMETER * OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_DIAMETER)
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_WORD_COUNT \
    ((OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_NODE_COUNT + 31) / 32)
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_LIST_WORDS_PER_SEGMENT 2
#define OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_LIST_WRAPPER_WORDS 6
#define OW_WILD_SPAWNER_STAGED_HOP_MOVEMENT_TASK_WORDS 2
#define OW_WILD_SPAWNER_STAGED_HOP_MOVEMENT_COMMAND_WORDS \
    (OW_WILD_STAGED_HOP_MOVEMENT_LIST_WORDS \
        - OW_WILD_SPAWNER_STAGED_HOP_MOVEMENT_TASK_WORDS)
#define OW_WILD_SPAWNER_CANOPY_HOPPER_PATH_MAX_STEPS \
    ((OW_WILD_SPAWNER_STAGED_HOP_MOVEMENT_COMMAND_WORDS \
        - OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_LIST_WRAPPER_WORDS - 2) \
        / OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_LIST_WORDS_PER_SEGMENT)
#define OW_WILD_SPAWNER_FX32_ONE (1 << 12)
#define OW_WILD_SPAWNER_TILE_FX32 (OW_WILD_SPAWNER_FX32_ONE * 16)
#define OW_WILD_SPAWNER_TILE_CENTER_FX32 (OW_WILD_SPAWNER_TILE_FX32 / 2)
#define OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(tile) \
    ((s32)(tile) * OW_WILD_SPAWNER_TILE_FX32 + OW_WILD_SPAWNER_TILE_CENTER_FX32)
#define OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FRAMES 32
#define OW_WILD_SPAWNER_WALK_CRASH_SHAKE_FRAMES \
    ((OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FRAMES + 2) / 3)
#define OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FX32_AMPLITUDE (OW_WILD_SPAWNER_FX32_ONE / 8)
#define OW_WILD_SPAWNER_WAIT_JUMP_SITE_SET_BITS 0x00010004
#define OW_WILD_SPAWNER_WAIT_JUMP_SITE_CLEAR_BITS 0x00100000
#define OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS \
    (BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13)
#define OW_WILD_SPAWNER_FOLLOWER_CREATE_SET_BITS 0x00002400
#define OW_WILD_SPAWNER_FOLLOWER_CREATE_CLEAR_BITS 0x00000180
#define OW_WILD_SPAWNER_FORCE_BEHAVIOR_TEST_SPECIES 0
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_TRACE \
    || OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
#define OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE volatile
#else
#define OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE
#endif
#define OW_WILD_SPAWNER_BUBBLE_ID_NONE 0xFF

#define OW_WILD_SPAWNER_THROW_TARGET_NONE 0
#define OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG 0x80
#define OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG 0x40
#define OW_WILD_SPAWNER_THROW_TARGET_SLOT_MASK 0x3F
#define OW_WILD_SPAWNER_THROW_TARGET_ENCODE(slot) ((u8)((slot) + 1))
#define OW_WILD_SPAWNER_THROW_TARGET_ENCODE_CARRIED(slot) \
    ((u8)(OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG | OW_WILD_SPAWNER_THROW_TARGET_ENCODE(slot)))
#define OW_WILD_SPAWNER_THROW_TARGET_DECODE(value) \
    ((u8)(((value) & OW_WILD_SPAWNER_THROW_TARGET_SLOT_MASK) - 1))
#define OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG 0x80
#define OW_WILD_SPAWNER_STAGED_HOP_LEDGE_PENDING 2
#define OW_WILD_SPAWNER_STAGED_WALK_PENDING 3
#define OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING 4
#define OW_WILD_SPAWNER_STAGED_OBSTACLE_HOP_PENDING 6
#define OW_WILD_WALK_DIRECTION_OBSTACLE_APPROACH 0xFE
#define OW_WILD_SPAWNER_CHAIN_HOP_FORWARD_DISTANCE 2
#define OW_WILD_BEHAVIOR_KIND_NONE 0
#define OW_WILD_BEHAVIOR_KIND_IDLE 1
#define OW_WILD_BEHAVIOR_KIND_WANDER 2
#define OW_WILD_BEHAVIOR_KIND_CHASE 3
#define OW_WILD_BEHAVIOR_KIND_FLEE 4
#define OW_WILD_BEHAVIOR_KIND_PLAYFUL 5
#define OW_WILD_BEHAVIOR_KIND_RAM 6
#define OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP 7
#define OW_WILD_BEHAVIOR_KIND_ASLEEP 8
#define OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE 10
#define OW_WILD_BEHAVIOR_KIND_NO_VISUAL 11
#define OW_WILD_BEHAVIOR_ALERT_SPECIAL_NONE 0
#define OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP 1
#define OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW 2
#define OW_WILD_BEHAVIOR_BATTLE_TRIGGER_NONE 0
#define OW_WILD_BEHAVIOR_BATTLE_TRIGGER_CONTACT 1
#define OW_WILD_BEHAVIOR_BATTLE_TRIGGER_MOVEMENT_CRASH 2
#define OW_WILD_BEHAVIOR_JUMP_LEVEL_NONE 0
#define OW_WILD_BEHAVIOR_JUMP_LEVEL_DOWNHILL 1
#define OW_WILD_BEHAVIOR_JUMP_LEVEL_BOTH 2
#define OW_WILD_BEHAVIOR_PROFILE_DEFAULT 0
#define OW_WILD_CUSTOM_MOTION_NONE 0
#define OW_WILD_CUSTOM_MOTION_WALK 1
#define OW_WILD_CUSTOM_MOTION_JUMP 2
#define OW_WILD_CUSTOM_MOTION_TELEPORT_FLICKER 3
#define OW_WILD_CUSTOM_MOTION_TELEPORT_HIDDEN 4
#define OW_WILD_BEHAVIOR_LIMIT_KEY_OVERRIDE_BASE OWBD_CLASS_PROFILE_COUNT
#define OW_WILD_BEHAVIOR_SPAWN_STATE_APPEAR 0
#define OW_WILD_BEHAVIOR_SPAWN_STATE_MOVE_FROM_OFF_SCREEN 1
#define OW_WILD_BEHAVIOR_SPAWN_STATE_HOP_FROM_OFF_SCREEN 2
#define OW_WILD_BEHAVIOR_SPAWN_STATE_APPEAR_HOP 3
#define OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN 4
#define OW_WILD_BEHAVIOR_BOOL_NO 0
#define OW_WILD_BEHAVIOR_BOOL_YES 1
#define OW_WILD_BEHAVIOR_ALERT_RANGE_NONE 0
#define OW_WILD_BEHAVIOR_ALERT_RANGE_FACING_LINE 1
#define OW_WILD_BEHAVIOR_ALERT_RANGE_FACING_LINE_CLOSE_RADIUS 2
#define OW_WILD_BEHAVIOR_ALERT_RANGE_CARDINAL_LINE 3
#define OW_WILD_BEHAVIOR_ALERT_RANGE_RADIUS 4
#define OW_WILD_BEHAVIOR_ALERT_RANGE_TERRAIN_ONLY 5
#define OW_WILD_BEHAVIOR_LOCOMOTION_NONE 0
#define OW_WILD_BEHAVIOR_LOCOMOTION_WANDER 1
#define OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN 3
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN 4
#define OW_WILD_BEHAVIOR_LOCOMOTION_RAM 5
#define OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP 7
#define OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND 8
#define OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN 9
#define OW_WILD_BEHAVIOR_FRAME_DRIVEN_LOCOMOTION_MASK \
    ((1u << OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) \
        | (1u << OW_WILD_BEHAVIOR_LOCOMOTION_HOP) \
        | (1u << OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) \
        | (1u << OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND))
#define OW_WILD_BEHAVIOR_TARGET_NONE 0
#define OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY 1
#define OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER 2
#define OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER 3
#define OW_WILD_BEHAVIOR_TARGET_TREE_TOP 4
#define OW_WILD_BEHAVIOR_TARGET_PLAYFUL_ORBIT 5
#define OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER 6
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_FRONT OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER
#define OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE 8
#define OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER 9
#define OW_WILD_BEHAVIOR_REACTION_NONE 0
#define OW_WILD_BEHAVIOR_REACTION_CONTACT 1
#define OW_WILD_BEHAVIOR_REACTION_FLEE 2
#define OW_WILD_BEHAVIOR_REACTION_CRY 3
#define OW_WILD_BEHAVIOR_REACTION_EMOTE 4
#define OW_WILD_BEHAVIOR_REACTION_TIRED 5
#define OW_WILD_BEHAVIOR_MATCH_ANY_SPECIES SPECIES_NONE
#define OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN 0xFF
#define OW_WILD_BEHAVIOR_MATCH_ANY_CLASS 0xFF
#define OW_WILD_BEHAVIOR_MATCH_ANY_SHINY 0xFF
#define OW_WILD_BEHAVIOR_MATCH_CLASS_FORCED_ASLEEP 0xFD
#define OW_WILD_BEHAVIOR_MATCH_LEVEL_ANY 0
#define OW_WILD_BEHAVIOR_GROUP_NONE 0
#define OW_WILD_BEHAVIOR_GROUP_BABY (1u << 0)
#define OW_WILD_BEHAVIOR_GROUP_GHOST (1u << 1)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_NORMAL (1u << 2)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_FIGHTING (1u << 3)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_FLYING (1u << 4)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_POISON (1u << 5)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_GROUND (1u << 6)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_ROCK (1u << 7)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_BUG (1u << 8)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_GHOST (1u << 9)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_STEEL (1u << 10)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_FAIRY (1u << 11)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_FIRE (1u << 12)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_WATER (1u << 13)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_GRASS (1u << 14)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_ELECTRIC (1u << 15)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_PSYCHIC (1u << 16)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_ICE (1u << 17)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_DRAGON (1u << 18)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_DARK (1u << 19)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_TYPELESS (1u << 20)
#define OW_WILD_BEHAVIOR_GROUP_TYPE_STELLAR (1u << 21)
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_PREP 0
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_JUMP 1
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_FREEZE 2
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_RESTORE 3
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE 4
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_FIRST 5
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_SECOND 6
#define OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_RETURN 7
#define OW_WILD_SPAWNER_LOOK_PLAN_TWO_GLANCES (1u << 6)
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_IDLE_OBJECT_MOVEMENT
#define OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT OW_WILD_MOVE_STOCK_IDLE
#else
#define OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT OW_WILD_MOVE_STOCK_WANDER
#endif
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE 0xFF
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP 0
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN 1
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT 2
#define OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT 3
#define OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP 1
#define OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED (1u << 24)
#define OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT 8
#define OW_WILD_SPAWNER_ROLE_RESULT_TICKS_SHIFT 16
#define OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT 8
#define OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT 16
#define OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT 24
#define OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP 2
#define OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE 8
#define OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE 16
#define OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE 16
#define OW_WILD_SPAWNER_FLY_IN_DURATION_FRAMES 144
#define OW_WILD_SPAWNER_FLY_IN_HEIGHT_FX32 \
    (6 * OW_WILD_SPAWNER_TILE_FX32)
#define OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES 8
#define OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES 6
#define OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES 4
#define OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES 1
#define OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY 0
#define OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY 0
#define OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY 0
#define OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR 1
// Param 2 mirrors the follower palette metadata without switching to follower rendering.
#define OW_WILD_PAL_PARAM_SHINY 1
#define OW_WILD_PAL_PARAM_ENABLE 2
typedef enum OverworldWildDirectionStepResult {
    OW_WILD_DIRECTION_STEP_BUSY,
    OW_WILD_DIRECTION_STEP_BLOCKED,
    OW_WILD_DIRECTION_STEP_STARTED,
    OW_WILD_DIRECTION_STEP_OBSTACLE_HOP_STARTED,
} OverworldWildDirectionStepResult;

typedef struct OverworldWildDirectionStepContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    const OverworldWildBehaviorProfile *profile;
    const OverworldWildBehaviorPrimitives *primitives;
    u8 slot;
    u16 allowedTile;
    u8 jumpLevel;
    u8 avoidPreviousTile;
} OverworldWildDirectionStepContext;

typedef struct OverworldWildBehaviorHopValidationContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    OverworldWildHopLandingBaseValidatorFunc baseValidator;
    int slot;
    u16 allowedTile;
    BOOL rejectPreviousTile;
} OverworldWildBehaviorHopValidationContext;

typedef struct OverworldWildTeleportWorldContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    int slot;
    u16 allowedTile;
    s16 playerX;
    s16 playerY;
    u8 facePlayer;
} OverworldWildTeleportWorldContext;

typedef struct OverworldWildChainRepositionResult {
    u8 encodedRemaining;
    s8 gridDelta;
    u8 outcome;
    u8 reason;
} OverworldWildChainRepositionResult;

#define OW_WILD_CHAIN_RETRY 0
#define OW_WILD_CHAIN_STARTED 1
#define OW_WILD_CHAIN_COMPLETE 2
#define OW_WILD_CHAIN_ABORT 3

typedef struct OverworldWildBehaviorSlotCache {
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u16 species;
    u16 mapId;
    u8 form;
    u8 level;
    u8 terrain;
    u8 shiny;
    u8 behaviorClass;
    u8 valid;
} OverworldWildBehaviorSlotCache;

typedef struct OverworldWildSpawnDestinationScan {
    s16 playerX;
    s16 playerY;
    s16 nextX;
    s16 nextY;
    u16 destinationMask;
    u8 candidateCount;
} OverworldWildSpawnDestinationScan;

#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF
#define OW_WILD_SPAWN_STARTUP_PENDING 0xFE
#define OW_WILD_PROFILE_DESTINATION_CHECKS_PER_UPDATE 12

typedef struct OverworldWildOverlayRuntimeState {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
    s16 playerBallShadowTileX;
    s16 playerBallShadowTileY;
    u16 playerBallShadowGfxId;
    u8 playerBallShadowTrackingValid;
    u8 movementMankeyTreeTopCacheValid[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyTreeTopCacheResult[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopCacheX[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopCacheY[OW_WILD_MAX_SPAWNS];
    u16 movementMankeyTreeTopCacheMapId[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyTreeTopLandingExpected[OW_WILD_MAX_SPAWNS];
    u8 movementMankeyTreeTopSettled[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopSettledX[OW_WILD_MAX_SPAWNS];
    s16 movementMankeyTreeTopSettledY[OW_WILD_MAX_SPAWNS];
    u8 movementEmotePlayHopSound[OW_WILD_MAX_SPAWNS];
    u8 movementHopStartSoundSuppressFrames[OW_WILD_MAX_SPAWNS];
    u8 movementBehaviorLimitKeys[OW_WILD_MAX_SPAWNS];
    u8 playerBallCatchValues[OW_WILD_MAX_SPAWNS];
    u8 movementHelpSpawnParentSlotPlusOne;
    u8 movementHelpSpawnRemaining;
    u8 movementHelpSpawnPositionChecksRemaining;
    OverworldWildThrowState throwState;
    union {
        struct {
            u16 movementFrameDrivenOwnerMask;
            u16 movementFrameDrivenTiredMask;
            u16 movementOwnerTeleportMask;
            u16 movementTiredTeleportMask;
        };
        u16 movementRoutingMasks[4];
    };
    OverworldWildBehaviorSlotCache *movementBehaviorSlotCaches;
    OverworldWildPresentationState spawnPresentations;
    OverworldWildDespawnTelemetry despawnTelemetry;
    OverworldWildResidentData *residentData;
    u16 movementNativeHeldMask;
    u8 movementIdleAiCursor;
    u8 movementNativeShadowRestorePending;
    u8 movementCustomJumpArcHeightsQ4[OW_WILD_MAX_SPAWNS];
    u8 movementCustomMotionModes[OW_WILD_MAX_SPAWNS];
    /* One ordinary refill, owned by the existing maintenance schedule. No
     * engine object exists until the next usable frame validates this value. */
    OverworldWildPreparedSpawn queuedSpawn;
    OverworldWildQueuedSpawnGuard queuedSpawnGuard;
    OverworldWildSpawnDestinationScan spawnDestinationScan;
    OverworldWildBehaviorConditionRuntime *conditions;
} OverworldWildOverlayRuntimeState;

typedef char OverworldWildSpawnStateRuntimeOffsetMustRemainE4[
    offsetof(OverworldWildSpawnState, movementRuntimeState) == 0xE4 ? 1 : -1];
typedef char OverworldWildCustomJumpActiveOffsetMustRemainA[
    offsetof(OverworldWildOverlayRuntimeState, movementCustomJumpActive) == 0xA ? 1 : -1];
typedef char OverworldWildCustomJumpShadowBaseYOffsetMustRemain138[
    offsetof(OverworldWildOverlayRuntimeState, movementCustomJumpShadowBaseY) == 0x138 ? 1 : -1];
typedef char OverworldWildMotionCommitMustRequireAllFourEngineSeams[
    OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS
            == (OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY
                | OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_ENGINE_END)
        ? 1
        : -1];

#define OW_WILD_RUNTIME(state) ((OverworldWildOverlayRuntimeState *)((state)->movementRuntimeState))

static OverworldWildBehaviorConditionRuntime *
__attribute__((noinline, optimize("Os")))
OverworldWildSpawns_GetConditionRuntime(OverworldWildSpawnState *state)
{
    return state != NULL && state->movementRuntimeState != NULL
        ? OW_WILD_RUNTIME(state)->conditions
        : NULL;
}

void OverworldWildSpawns_MountCancel(u8 reason);
BOOL OverworldWildSpawns_MountIsActive(void);
int OverworldWildSpawns_BuildDirectedDirections(
    int dx,
    int dy,
    u8 *directions);
u8 OverworldWildSpawns_PopulationControl(u8 operation, u16 refillDelay);
BOOL OverworldWildSpawns_ReduceWalk(OverworldActorWalkPolicyCall *call);

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_InitPolicyCall(
    OverworldActorWalkPolicyCall *call,
    int slot,
    u8 operation)
{
    memset(call, 0, sizeof(*call));
    call->version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    call->size = sizeof(*call);
    call->actorSlot = (u8)slot;
    call->operation = operation;
}

static __attribute__((noinline)) const OverworldWildBehaviorProfileData *OverworldWildSpawns_GetControllerLane(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        return &profile->tired;
    }
    return &profile->owner;
}

static u32 OverworldWildSpawns_GetActiveConditionApplications(
    const OverworldWildSpawnState *state,
    int slot)
{
    const OverworldWildBehaviorConditionRuntime *conditions;

    conditions = OverworldWildSpawns_GetConditionRuntime(
        (OverworldWildSpawnState *)state);
    if (conditions == NULL) {
        return 0;
    }
    /* All static callers pass an owned actor slot. */
    return conditions->activeApplicationMasks[slot];
}

static inline __attribute__((always_inline)) u32 OverworldWildSpawns_SampleMovementVariance(
    int slot,
    u8 variance)
{
    OverworldActorWalkPolicyCall call;

    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_SAMPLE_VARIANCE);
    call.distance = variance;
    if (!OverworldWildSpawns_ReduceWalk(&call)) {
        return 0;
    }
    return call.chainTicks;
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_BindActorPolicyProfile(
    int slot,
    u32 behaviorFingerprint,
    u32 matchedLayerMask)
{
    OverworldActorPolicyProfileBinding binding;
    OverworldActorWalkPolicyCall call;

    /* Retained follower setup can resolve its ordinary profile during a map
     * rebind. Keep that cache work, but the mount still owns slot 7's policy
     * until its session ends. Normal Follower binds resume after dismount. */
    if (slot == OW_WILD_FOLLOWER_SLOT
        && OverworldWildSpawns_MountIsActive()) {
        return;
    }
    binding.behaviorFingerprint = behaviorFingerprint;
    binding.matchedLayerMask = matchedLayerMask;
    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE);
    call.profileBinding = &binding;
    (void)OverworldWildSpawns_ReduceWalk(&call);
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ApplyChainRepositionResult(
    int slot,
    const OverworldWildChainRepositionResult *result)
{
    OverworldActorWalkPolicyCall call;
    BOOL started = result->outcome == OW_WILD_CHAIN_STARTED;

    if (result->outcome == OW_WILD_CHAIN_RETRY
        && (result->encodedRemaining & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING)) {
        return TRUE;
    }
    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        started
            ? OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_ADVANCE
            : OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH);
    if (started) {
        call.distance = result->encodedRemaining;
        call.direction = (u8)result->gridDelta;
    }
    return OverworldWildSpawns_ReduceWalk(&call);
}

static void __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_ClearWalkMovementState(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    OverworldActorWalkPolicyCall call;

    (void)state;
    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_RESET);
    /* Field-header cleanup can run while the mount still owns follower slot 7.
     * Clear the old object's presentation below, but preserve the mounted
     * policy until its accepted motion reaches the engine END boundary. */
    if (slot != OW_WILD_FOLLOWER_SLOT
        || !OverworldWildSpawns_MountIsActive()) {
        (void)OverworldWildSpawns_ReduceWalk(&call);
    }
    if (object != NULL) {
        OverworldWildSpawns_ClearObjectFlags(object, MAPOBJECTFLAG_UNK7);
    }
}

typedef struct OverworldWildAlertPrimitiveMap {
    u8 logic;
    u8 reaction;
} OverworldWildAlertPrimitiveMap;

/* The profile tooling reads these canonical maps from source. Production
 * resolution lives in the resident Wild policy module to keep overlay 149
 * within its fixed FAT slot. */
#if 0
static const u8 sOverworldWildSpawnLocomotionBySpawnState[] = {
    OW_WILD_BEHAVIOR_LOCOMOTION_NONE,
    OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN,
    OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN,
    OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP,
};

static const u8 sOverworldWildDefaultTargetByBehaviorKind[] = {
    OW_WILD_BEHAVIOR_TARGET_NONE,
    OW_WILD_BEHAVIOR_TARGET_NONE,
    OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY,
    OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER,
    OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER,
    OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER,
    OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER,
    OW_WILD_BEHAVIOR_TARGET_TREE_TOP,
};

static const u8 sOverworldWildOwnerReactionByBehaviorKind[] = {
    OW_WILD_BEHAVIOR_REACTION_NONE,
    OW_WILD_BEHAVIOR_REACTION_NONE,
    OW_WILD_BEHAVIOR_REACTION_NONE,
    OW_WILD_BEHAVIOR_REACTION_CONTACT,
    OW_WILD_BEHAVIOR_REACTION_FLEE,
    OW_WILD_BEHAVIOR_REACTION_EMOTE,
    OW_WILD_BEHAVIOR_REACTION_CONTACT,
    OW_WILD_BEHAVIOR_REACTION_CONTACT,
};
#endif

static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void);

static u8 OverworldWildSpawns_CalculatePlayerBallShakes(
    OverworldWildSpawnState *state,
    int slot,
    u16 encounterGeneration)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->spawns[slot].encounterGeneration != encounterGeneration) {
        return 0;
    }
    runtime = OW_WILD_RUNTIME(state);
    if (runtime == NULL) {
        return 0;
    }
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL) {
        return 0;
    }
    return helperEntry->calculatePlayerBallShakes(
        runtime->playerBallCatchValues[slot]);
}

static u8 OverworldWildSpawns_GetPlayerBallCatchValue(u8 catchRate)
{
    return (u8)((catchRate + 2) / 3);
}

static int OverworldWildSpawns_FindCapturedPokemonDestination(
    FieldSystem *fieldSystem)
{
    struct Party *party;
    PCStorage *storage;
    int box;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE;
    }
    party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party != NULL && party->count < party->maxPossibleCount) {
        return OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_PARTY;
    }
    storage = SaveArray_Get(
        fieldSystem->savedata,
        OW_WILD_PLAYER_BALL_PC_STORAGE_SAVE_BLOCK);
    if (storage == NULL) {
        return OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE;
    }
    box = PCStorage_FindFirstBoxWithEmptySlot(storage);
    return box < NUM_PC_BOXES
        ? box
        : OW_WILD_PLAYER_BALL_CAPTURE_DESTINATION_NONE;
}

static void OverworldWildSpawns_InitBehaviorResolveRequest(
    BehaviorResolveRequest *request)
{
    memset(request, 0, sizeof(*request));
    request->requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    request->winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request->targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    request->resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
}

static void *sOverworldWildBehaviorDataBlob;
static struct {
    u8 behaviorDataLoadAttempted;
    u8 helperOverlayReady;
    u8 movementFrameDecisionCounter;
    u8 movementFrameTaskExecuting;
    u8 spawnHopPreparing;
    u8 spawnWarmupPhase;
} sOverworldWildFlags;
#define sOverworldWildBehaviorDataLoadAttempted sOverworldWildFlags.behaviorDataLoadAttempted
#define sOverworldWildHelperOverlayReady sOverworldWildFlags.helperOverlayReady
#define sOverworldWildMovementFrameDecisionCounter sOverworldWildFlags.movementFrameDecisionCounter
#define sOverworldWildMovementFrameTaskExecuting sOverworldWildFlags.movementFrameTaskExecuting
#define sOverworldWildSpawnHopPreparing sOverworldWildFlags.spawnHopPreparing

static LocalMapObject *sOverworldWildCollisionIgnoredObject;
static OverworldWildSpawnState *sOverworldWildLastState;
static void OverworldWildSpawns_CleanupPresentationBeforeUnload(OverworldWildSpawnState *state);
static void OverworldWildSpawns_CleanupResidentTasks(void);
static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void);
static void OverworldWildSpawns_ClearAllConditionState(
    OverworldWildBehaviorConditionRuntime *conditions);

static BOOL OverworldWildSpawns_CleanupResidentData(void)
{
    OverworldWildSpawnState *state = sOverworldWildLastState;
    BOOL helperLoaded = IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER);

    OverworldWildSpawns_MountCancel(
        OVERWORLD_MOUNT_CANCEL_OVERLAY_CLEANUP);

    if (!helperLoaded && sOverworldWildHelperOverlayReady) {
        return FALSE;
    }
    if (helperLoaded
        && !OVERWORLD_WILD_HELPER_OVERLAY_VALIDATE(
            sOverworldWildHelperOverlayReady
                ? OVERWORLD_WILD_HELPER_OWNED_BEHAVIOR
                : OVERWORLD_WILD_HELPER_VALIDATE_ONLY)) {
        return FALSE;
    }
    if (sOverworldWildHelperOverlayReady
        && !CanOverlayBeLoaded(OVERLAY_OVERWORLD_WILD_BEHAVIOR_DATA)) {
        return FALSE;
    }
    if (helperLoaded
        && !OVERWORLD_WILD_HELPER_OVERLAY_LIFECYCLE(
            OVERWORLD_WILD_HELPER_LIFECYCLE_PREPARE_CLEANUP,
            state != NULL
                ? state->movementFieldSystem
                : NULL)) {
        return FALSE;
    }
    OverworldWildSpawns_CleanupPresentationBeforeUnload(state);
    OverworldWildSpawns_CleanupResidentTasks();
    gOverworldWildNativeShadowSuppressedMask = 0;
    if (helperLoaded
        && !OVERWORLD_WILD_HELPER_OVERLAY_LIFECYCLE(
            sOverworldWildHelperOverlayReady
                ? OVERWORLD_WILD_HELPER_LIFECYCLE_FINISH_OWNED
                : OVERWORLD_WILD_HELPER_LIFECYCLE_FINISH_UNOWNED,
            NULL)) {
        return FALSE;
    }
    if (state != NULL && state->movementRuntimeState != NULL) {
        OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);

        if (runtime->movementBehaviorSlotCaches != NULL) {
            sys_FreeMemoryEz(runtime->movementBehaviorSlotCaches);
        }
        runtime->movementBehaviorSlotCaches = NULL;
        if (runtime->conditions != NULL) {
            OverworldWildSpawns_ClearAllConditionState(runtime->conditions);
            sys_FreeMemoryEz(runtime->conditions);
        }
        runtime->conditions = NULL;
        sys_FreeMemoryEz(runtime);
        state->movementRuntimeState = NULL;
    }
    sOverworldWildLastState = NULL;

    if (sOverworldWildBehaviorDataBlob != NULL) {
        sys_FreeMemoryEz(sOverworldWildBehaviorDataBlob);
    }
    sOverworldWildBehaviorDataBlob = NULL;

    sOverworldWildBehaviorDataLoadAttempted = FALSE;
    sOverworldWildFlags.spawnWarmupPhase = 0;

    sOverworldWildHelperOverlayReady = 0;
    UnloadOverlayByID(OVERLAY_OVERWORLD_WILD_HELPER);
    return TRUE;
}

static BOOL OverworldWildSpawns_LoadCodeAddonBlob(u32 memberId, u32 expectedSize, void **blob, u32 *loadedSize)
{
    void *narc;
    u32 size;
    void *loadedBlob;

    narc = NARC_ctor(
        ARC_CODE_ADDONS,
        HEAPID_WORLD);
    if (narc == NULL) {
        return FALSE;
    }
    if (NARC_GetFileCount(narc) <= memberId) {
        NARC_dtor(narc);
        return FALSE;
    }

    size = NARC_GetMemberSize(narc, memberId);
    if (size == 0 || (expectedSize != 0 && size != expectedSize)) {
        NARC_dtor(narc);
        return FALSE;
    }

    loadedBlob = sys_AllocMemory(
        OVERWORLD_WILD_BEHAVIOR_DATA_HEAP_ID,
        size);
    if (loadedBlob == NULL) {
        NARC_dtor(narc);
        return FALSE;
    }

    NARC_ReadWholeMember(narc, memberId, loadedBlob);
    NARC_dtor(narc);
    *blob = loadedBlob;
    if (loadedSize != NULL) {
        *loadedSize = size;
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_DecodeBehaviorDataBlob(void)
{
    BehaviorResolveRequest request;
    BehaviorClassSelection selection;

    if (sOverworldWildBehaviorDataBlob == NULL) {
        return FALSE;
    }
    OverworldWildSpawns_InitBehaviorResolveRequest(&request);
    request.behaviorClass = BEHAVIOR_RESOLVER_CLASS_AUTO;
    return OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->inspectClass(
            sOverworldWildBehaviorDataBlob,
            sizeof(OverworldWildBehaviorDataBlob),
            &request,
            &selection,
            NULL) == BEHAVIOR_RESOLVE_OK;
}

static const OverworldWildBehaviorDataBlob *OverworldWildSpawns_GetBehaviorDataBlob(void)
{
    if (!sOverworldWildBehaviorDataLoadAttempted) {
        sOverworldWildBehaviorDataLoadAttempted = TRUE;
        if (!OverworldWildSpawns_LoadCodeAddonBlob(
                CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA,
                sizeof(OverworldWildBehaviorDataBlob),
                &sOverworldWildBehaviorDataBlob,
                NULL)
            || !OverworldWildSpawns_DecodeBehaviorDataBlob()) {
            if (sOverworldWildBehaviorDataBlob != NULL) {
                sys_FreeMemoryEz(sOverworldWildBehaviorDataBlob);
            }
            sOverworldWildBehaviorDataBlob = NULL;
        }
    }

    return (const OverworldWildBehaviorDataBlob *)sOverworldWildBehaviorDataBlob;
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_QuerySurface(
    FieldSystem *fieldSystem,
    int x,
    int y,
    OverworldWildSurfaceHit *hit)
{
    const OverworldWildBehaviorDataBlob *blob =
        OverworldWildSpawns_GetBehaviorDataBlob();

    if (blob == NULL) {
        return FALSE;
    }
    return OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->querySurface(
        fieldSystem,
        (const OverworldWildSurfaceCatalog *)blob->surfaceModels,
        x,
        y,
        hit);
}

static void __attribute__((noinline)) OverworldWildSpawns_ApplySurfaceHeight(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int x,
    int y)
{
    OverworldWildSurfaceHit hit;

    if (!OverworldWildSpawns_QuerySurface(fieldSystem, x, y, &hit)
        || (u16)(hit.surfaceId + 1) == 0) {
        return;
    }
    if (hit.surfaceType == OW_WILD_SURFACE_TYPE_CANOPY) {
        hit.height += (s32)object->posVec[1];
    }
    object->posVec[1] = hit.height;
    object->hInit = hit.height >> 15;
    object->hPrev = object->hInit;
    object->hCurr = object->hInit;
}

typedef struct OverworldWildFieldEffectDescriptor {
    u32 workSize;
    BOOL (*init)(void *effect, void *work);
    void (*destroy)(void *effect, void *work);
    void (*update)(void *effect, void *work);
    void (*render)(void *effect, void *work);
} OverworldWildFieldEffectDescriptor;

typedef struct OverworldWildMankeyTreeTopLateDrawEffectInit {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    int slot;
} OverworldWildMankeyTreeTopLateDrawEffectInit;

typedef struct OverworldWildMankeyTreeTopLateDrawEffectWork {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    LocalMapObject *object;
    int slot;
    u8 markerTimer;
} OverworldWildMankeyTreeTopLateDrawEffectWork;

typedef struct OverworldWildSpawnPrepContext {
    OverworldWildSpawnState *state;
    FieldSystem *fieldSystem;
    OverworldWildSpawnTerrain terrain;
} OverworldWildSpawnPrepContext;

static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *fieldSystem, int x, int y);
static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void);
static BOOL OverworldWildSpawns_OverlayOnPlayerStep(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildResidentData *residentData);
static BOOL OverworldWildSpawns_OverlayOnPlayerFrame(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state);
static void OverworldWildSpawns_OverlayOnFieldBusy(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildResidentData *residentData);
static BOOL OverworldWildSpawns_TickPlayerBallProjectile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state);
static BOOL OverworldWildSpawns_ApplyPresentationCommand(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u8 operation,
    u8 slot);
static LocalMapObject *OverworldWildSpawns_GetPlayerBallProjectileObject(void);
static BOOL OverworldWildSpawns_IsPlayerBallProjectileActive(void);
static BOOL OverworldWildSpawns_OverlayTryPrimeBattleFromTalk(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject);
static int OverworldWildSpawns_FindBattleTalkSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject);
static u8 OverworldWildSpawns_OverlayCleanupPendingBattle(FieldSystem *fieldSystem, OverworldWildSpawnState *state, u16 battleResult);
static BOOL OverworldWildSpawns_CleanupResidentData(void);
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(
    FieldSystem *fieldSystem,
    const OverworldWildSpawn *spawn);
static BOOL OverworldWildSpawns_TryBuildFollowerMountBinding(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldMountBinding *binding)
{
    const OverworldWildSpawn *spawn;

    binding->partySlot = state->activeFollowerPartySlot;
    if (binding->partySlot == CUSTOM_FOLLOWER_PARTY_SLOT_NONE) {
        return FALSE;
    }
    spawn = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    if (!OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, spawn)) {
        return FALSE;
    }

    binding->personality = spawn->personality;
    binding->species = spawn->species;
    binding->mapId = spawn->mapId;
    binding->mapGeneration = state->mapGeneration;
    binding->encounterGeneration = spawn->encounterGeneration;
    binding->form = spawn->form;
    binding->level = spawn->level;
    binding->behaviorClass = state->movementBehaviorClasses[OW_WILD_FOLLOWER_SLOT];
    return TRUE;
}

static BOOL OverworldWildSpawns_BeginMountSelectedFollower(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state);
static void OverworldWildSpawns_ResetSlotMovementCommand(
    OverworldWildSpawnState *state,
    int slot,
    BOOL clearObjectCommand);
static void OverworldWildSpawns_ResetSlotState(OverworldWildSpawnState *state, int slot, BOOL deleteAuxiliaryObjects);
static void OverworldWildSpawns_PrepareSlotForCapture(OverworldWildSpawnState *state, int slot);
static int OverworldWildSpawns_GetSpawnHopVisibleTravelScore(
    u8 direction,
    int targetDx,
    int targetDy);
static BOOL OverworldWildSpawns_TryPickVisibleOffscreenOrigin(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int maximumDistance,
    int targetX,
    int targetY,
    int *startX,
    int *startY);
static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_StartSpawnAirborne(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildSpawnStartup *startup,
    const OverworldWildBehaviorProfile *resolvedProfile);
static BOOL OverworldWildSpawns_HandleFinishedSpawnHopMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot);
static BOOL OverworldWildSpawns_UpdateSpawnMoveTargetState(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object);
static BOOL OverworldWildSpawns_IsEnabledMap(FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_IsFieldContextAvailable(FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_IsHeadbuttTreeTopLocation(FieldSystem *fieldSystem, int x, int y);
static BOOL OverworldWildSpawns_IsLandMapTile(FieldSystem *fieldSystem, int x, int y);
static BOOL OverworldWildSpawns_TryGetLoadedMetatileBehavior(
    FieldSystem *fieldSystem,
    int x,
    int y,
    u8 *behavior);
static BOOL OverworldWildSpawns_IsPlayableMapMatrixTile(
    FieldSystem *fieldSystem,
    int x,
    int y);
static BOOL OverworldWildSpawns_IsBehaviorAllowedMovementTile(
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int x,
    int y);
static OverworldWildDirectionStepResult
OverworldWildSpawns_TryStartLedgeJumpCommand(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction,
    BOOL obstacleHopAllowed,
    BOOL probeOnly);
static BOOL OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
    OverworldWildSpawnState *state,
    int slot,
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int x,
    int y,
    int finalTargetX,
    int finalTargetY);
static BOOL OverworldWildSpawns_ValidateHopLandingValue(
    u16 serviceVersion,
    int slot,
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int x,
    int y,
    int finalTargetX,
    int finalTargetY);
BOOL __attribute__((noinline, optimize("Os", "no-gcse-lm"),
    section(".overworld_wild_native_shadow_value")))
OverworldWildSpawns_CopyNativeShadowValue(
    LocalMapObject *object,
    OverworldWildNativeShadowValue *value);
static BOOL OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(
    FieldSystem *fieldSystem,
    LocalMapObject *ignoredObject,
    int x,
    int y);
static BOOL OverworldWildSpawns_TryStartBattle(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_TryStartBattleForSlot(OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot);
static void OverworldWildSpawns_PrimePendingBattleForSlot(OverworldWildSpawnState *state, int slot);
static BOOL OverworldWildSpawns_QueueBattleForSlot(OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot);
static BOOL OverworldWildSpawns_TryStartBattleForSlotOrQueue(OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot);
static void OverworldWildSpawns_ResetPendingBattle(OverworldWildSpawnState *state);
#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
static void OverworldWildSpawns_ClearContextLite(OverworldWildSpawnState *state);
#endif
static BOOL OverworldWildSpawns_HasPendingBattle(OverworldWildSpawnState *state);
static BOOL OverworldWildSpawns_HasQueuedBattle(OverworldWildSpawnState *state);
static BOOL OverworldWildSpawns_TryStartQueuedBattle(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_TryStartBattleFromAButton(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_IsPlayerStableForBattle(FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_TryGetCustomJumpVector(
    int dx,
    int dy,
    u8 *direction,
    u8 *distance);
static int OverworldWildSpawns_GetCustomJumpDistance(int dx, int dy);
static BOOL OverworldWildSpawns_IsCustomJumpVectorShape(int dx, int dy);
#if !OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY || !OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
static void __attribute__((noinline)) OverworldWildSpawns_ResetAmbientCryCooldown(OverworldWildSpawnState *state);
#endif
static u32 OverworldWildSpawns_GetSpriteID(u16 species, u8 form);
static u32 OverworldWildSpawns_GetSpriteIDForSlot(
    u16 species,
    u8 form,
    u32 personality,
    int slot);
static BOOL OverworldWildSpawns_IsPresentationFieldContextCurrent(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_IsMovementFieldContextCurrent(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_IsFrameDrivenOwnerLocomotion(u8 locomotion);
static void OverworldWildSpawns_ApplyMovementRange(LocalMapObject *object, u8 range);
static void OverworldWildSpawns_ApplyPokemonRenderParams(
    LocalMapObject *object,
    u16 species,
    u8 form,
    u32 spriteId,
    BOOL shiny);
static void OverworldWildSpawns_RevealUnownedVanishedObjects(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 direction);
static void OverworldWildSpawns_SetObjectTile(LocalMapObject *object, int x, int y);
static void OverworldWildSpawns_SetObjectLogicalTileOnly(LocalMapObject *object, int x, int y);
static void __attribute__((noinline)) OverworldWildSpawns_SetObjectLandingTile(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int x,
    int y);
static s32 __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_GetObjectGroundBaseYAt(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int x,
    int y);
static u16 OverworldWildSpawns_GetElevatedTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y);
static u16 OverworldWildSpawns_GetCanopyTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y);
static u16 OverworldWildSpawns_GetTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y,
    BOOL includeNativeGround);
static void OverworldWildSpawns_ResetSlotSpotState(OverworldWildSpawnState *state, int slot);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
static void OverworldWildSpawns_FinishPresentationCommand(LocalMapObject *object);
static void OverworldWildSpawns_CancelSpotEmotePresentation(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object);
static void OverworldWildSpawns_ResetAllMovementCommands(
    OverworldWildSpawnState *state,
    BOOL clearObjectCommand,
    BOOL preserveMapHeaderState);
static void OverworldWildSpawns_ResetAllMovementStateOnly(
    OverworldWildSpawnState *state,
    BOOL clearObjectCommand,
    BOOL preserveMapHeaderState);
static void OverworldWildSpawns_DetachAllMovementStateOnContextLoss(
    OverworldWildSpawnState *state,
    BOOL preserveMapHeaderState);
static BOOL OverworldWildSpawns_ApplyTransitionWork(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    const OverworldActorTransitionCall *call);
static void OverworldWildSpawns_StartTiredEmoteWithProfile(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profileOverride,
    const OverworldWildBehaviorPrimitives *primitivesOverride);
static BOOL OverworldWildSpawns_ResolveConditionsAtIntentBoundary(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile,
    OverworldWildBehaviorPrimitives *primitives);
static BOOL OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile);
static void OverworldWildSpawns_StartTiredEmote(OverworldWildSpawnState *state, int slot);
static void OverworldWildSpawns_StartHopStartSoundSuppression(OverworldWildSpawnState *state, int slot);
static BOOL OverworldWildSpawns_TryStartManualHopEmote(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u8 requiredState,
    u8 endState,
    u8 direction,
    u8 jumpCount,
    u8 emoteFrames,
    u8 bubbleId,
    BOOL showBubbleEachJump,
    BOOL playHopSound);
static __attribute__((noinline)) u8 OverworldWildSpawns_TryStartChainPauseAction(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 pauseAction,
    u8 pauseTicks,
    u8 committedDirection);
static void OverworldWildSpawns_CommitDeferredChainMovementPause(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile);
static BOOL OverworldWildSpawns_TryStartWalkStopSkid(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorProfileData *lane);
static void OverworldWildSpawns_HandleFinishedMovementCommand(
    OverworldWildSpawnState *state,
    int slot);
static BOOL OverworldWildSpawns_StartCarriedThrowTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot,
    LocalMapObject *object);
static void OverworldWildSpawns_ClearStagedHopTarget(OverworldWildSpawnState *state, int slot);
static void OverworldWildSpawns_ClearSpawnRunState(OverworldWildSpawnState *state, int slot);
static void __attribute__((noinline)) OverworldWildSpawns_ShowBubble(LocalMapObject *object, u8 bubbleId);
static void OverworldWildSpawns_ClearTeleportFlickerObject(
    OverworldWildSpawnState *state,
    int slot,
    BOOL deleteObject);
static BOOL OverworldWildSpawns_IsTeleportMovementActive(
    OverworldWildSpawnState *state,
    int slot);
static int OverworldWildSpawns_BuildRandomDirections(u8 *directions);
u8 OverworldWildSpawns_SelectMovementLocomotion(
    const OverworldWildBehaviorPrimitives *primitives,
    u8 laneState);
#define OverworldWildSpawns_GetCurrentMovementLocomotion \
    OverworldWildSpawns_SelectMovementLocomotion
static BOOL OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    int *targetX,
    int *targetY);
static void OverworldWildSpawns_TrySpawnHelpChildren(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile);
static void OverworldWildSpawns_ClearQueuedHelpChildren(OverworldWildSpawnState *state);
static void OverworldWildSpawns_SpawnQueuedHelpChildren(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit(
    OverworldWildSpawnState *state,
    u8 behaviorLimitKey,
    const OverworldWildBehaviorProfile *profile);
static void OverworldWildSpawns_TryStartPickupThrowAction(
    OverworldWildSpawnState *state,
    int slot);
static void OverworldWildSpawns_ApplyHelpChildSpawnState(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object);
static void OverworldWildSpawns_RevealTeleportObject(OverworldWildSpawnState *state, int slot, LocalMapObject *object);
static void OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot);
static void OverworldWildSpawns_ClearStagedHopMovementListTask(
    OverworldWildSpawnState *state,
    int slot);
static void OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object);
static BOOL OverworldWildSpawns_ContinuePendingStagedHop(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot);
static BOOL OverworldWildSpawns_TryStartRandomBehaviorHopCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile);
static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    int dx,
    int dy,
    const u8 *directions,
    int directionCount,
    u8 planMode);
static BOOL __attribute__((optimize("Os", "tree-dominator-opts")))
OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u16 allowedTile,
    int landingX,
    int landingY,
    int finalTargetX,
    int finalTargetY,
    u8 pendingMarker);
static BOOL OverworldWildSpawns_TryStartTeleportMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const u8 *directions,
    int directionCount,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives);
static BOOL OverworldWildSpawns_CompleteTeleportMovement(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u16 appliedThrough);
BOOL OverworldWildSpawns_AcknowledgeSharedMotion(
    int slot,
    u8 acknowledgements,
    u16 appliedThrough,
    OverworldMotionSample *sample,
    u8 *phase);

static void OverworldWildSpawns_CancelSharedMotion(
    int slot,
    u8 reason);
static BOOL OverworldWildSpawns_HandleLockedWalkCrash(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction);
static void OverworldWildSpawns_PlayMovementCrashFeedback(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState);
u8 OverworldWildSpawns_SelectMovementTarget(
    const OverworldWildBehaviorPrimitives *primitives,
    u8 laneState);
#define OverworldWildSpawns_GetCurrentMovementTarget \
    OverworldWildSpawns_SelectMovementTarget
static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_StartPreparedCustomJumpCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    u8 distance,
    int targetX,
    int targetY,
    const OverworldWildBehaviorProfile *profile,
    BOOL suppressHopStartSound);
static OverworldMotionDecision __attribute__((optimize("Os")))
OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    u8 distance,
    int targetX,
    int targetY,
    const OverworldWildBehaviorProfile *profile,
    BOOL suppressHopStartSound,
    u8 walkTime);
static OverworldMotionDecision OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
    OverworldWildSpawnState *state, int slot, FieldSystem *fieldSystem,
    u16 allowedTile, int x, int y, int finalTargetX, int finalTargetY);
static BOOL OverworldWildSpawns_IsHeadbuttTreeTopLocation(FieldSystem *fieldSystem, int x, int y);
static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_HandleFinishedStagedHopMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    BOOL customJumpLandingFinalized);
static BOOL OverworldWildSpawns_ExecutePendingStagedHop(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile);

static OverworldMotionDecision __attribute__((optimize("Os")))
OverworldWildSpawns_RequestHopPlan(OverworldActorHopPlanCall *hopPlan)
{
    OverworldActorMotionRequestCall request;

    memset(&request, 0, sizeof(request));
    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP;
    request.hopPlan = hopPlan;
    return OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request)
            == OVERWORLD_ACTOR_RESULT_OK
        ? request.decision : OVERWORLD_MOTION_DECISION_PROFILE;
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_TryGetBehaviorHopVector(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    OverworldActorHopPlanCall hopPlan;

    memset(&hopPlan, 0, sizeof(hopPlan));
    hopPlan.operation = OVERWORLD_ACTOR_HOP_PLAN_VECTOR;
    hopPlan.profile = profile;
    hopPlan.spotState = spotState;
    hopPlan.deltaX = (s16)dx;
    hopPlan.deltaY = (s16)dy;
    if (OverworldWildSpawns_RequestHopPlan(&hopPlan)
        != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return FALSE;
    }
    if (direction != NULL) {
        *direction = hopPlan.direction;
        *distance = hopPlan.distance;
    }
    return TRUE;
}

static OverworldMotionDecision __attribute__((optimize("Os")))
OverworldWildSpawns_ResolveHopTrajectory(
    FieldSystem *fieldSystem,
    const OverworldWildSurfaceCatalog *surfaceCatalog,
    const OverworldWildBehaviorProfileData *lane,
    LocalMapObject *object,
    s32 startBaseY,
    s32 targetBaseY,
    int startX,
    int startY,
    int targetX,
    int targetY,
    u8 distance,
    BOOL usesArc,
    BOOL spawnEntry,
    u32 *trajectory)
{
    OverworldActorHopPlanCall hopPlan;
    OverworldMotionDecision decision;

    memset(&hopPlan, 0, sizeof(hopPlan));
    hopPlan.operation = usesArc
        ? OVERWORLD_ACTOR_HOP_PLAN_TRAJECTORY
        : OVERWORLD_ACTOR_HOP_PLAN_FLAT_TRAJECTORY;
    hopPlan.trajectory = *trajectory;
    hopPlan.lane = lane;
    hopPlan.fieldSystem = fieldSystem;
    hopPlan.surfaceCatalog = surfaceCatalog;
    hopPlan.object = object;
    hopPlan.startBaseY = startBaseY;
    hopPlan.targetBaseY = targetBaseY;
    hopPlan.startX = (s16)startX;
    hopPlan.startY = (s16)startY;
    hopPlan.targetX = (s16)targetX;
    hopPlan.targetY = (s16)targetY;
    hopPlan.distance = distance;
    hopPlan.spotState = spawnEntry
        ? OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY : 0;
    decision = OverworldWildSpawns_RequestHopPlan(&hopPlan);
    *trajectory = hopPlan.trajectory;
    return decision;
}

static BOOL OverworldWildSpawns_ValidateBehaviorHopLanding(
    int landingX,
    int landingY,
    int targetX,
    int targetY,
    void *rawContext)
{
    OverworldWildBehaviorHopValidationContext *context = rawContext;

    if (context->rejectPreviousTile
        && context->state->movementStagedHopAvoidValid[context->slot]
        && landingX
            == context->state->movementStagedHopAvoidX[context->slot]
        && landingY
            == context->state->movementStagedHopAvoidY[context->slot]) {
        return FALSE;
    }
    return context->baseValidator(
        context->state,
        context->slot,
        context->fieldSystem,
        context->allowedTile,
        landingX,
        landingY,
        targetX,
        targetY);
}

static void OverworldWildSpawns_BuildHopHelperConfig(
    const OverworldWildBehaviorProfileData *lane,
    int objectX,
    int objectY,
    int targetX,
    int targetY,
    const u8 *directions,
    int directionCount,
    u8 planMode,
    OverworldWildHelperHopConfig *config)
{
    config->objectX = objectX;
    config->objectY = objectY;
    config->targetX = targetX;
    config->targetY = targetY;
    config->minDistance = lane->hopMinDistance;
    config->maxDistance = lane->hopMaxDistance;
    config->allowNonCardinal = lane->hopAllowNonCardinal;
    config->planMode = planMode;
    config->directionCount = (u8)directionCount;
    while (directionCount != 0) {
        directionCount--;
        config->directions[directionCount] = directions[directionCount];
    }
}

static BOOL OverworldWildSpawns_IsChainActionReady(int slot)
{
    OverworldActorPolicyView policy;

    return (u32)slot < OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS
        && OverworldActorPolicy_Inspect((u8)slot, &policy)
        && policy.actorActive
        && (policy.motionPhase == OVERWORLD_MOTION_PHASE_IDLE
            || policy.motionPhase == OVERWORLD_MOTION_PHASE_CANCELED);
}

static BOOL __attribute__((optimize("Os", "no-jump-tables")))
OverworldWildSpawns_RunChainReposition(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 encodedRemaining,
    OverworldWildChainRepositionResult *result)
{
    const OverworldWildBehaviorProfileData *lane;
    LocalMapObject *object;
    u32 remaining;
    u32 packedOffset;
    u32 startIndex;
    u32 attempt;
    u32 directionIndex;
    u32 distance;
    int targetX;
    int targetY;
    BOOL retry = FALSE;
    OverworldMotionDecision decision = OVERWORLD_MOTION_DECISION_ACCEPTED;

    if (result == NULL) {
        return FALSE;
    }
    result->encodedRemaining = encodedRemaining;
    result->outcome = OW_WILD_CHAIN_COMPLETE;
    lane = OverworldWildSpawns_GetControllerLane(
        profile, state->movementSpotStates[slot]);
    remaining = lane->chainRepositionJumpCount;
    if ((encodedRemaining & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) != 0) {
        remaining = (encodedRemaining - 1) & 0x0F;
    }
    object = state->spawns[slot].object;
    if (remaining == 0) {
        goto finished;
    }
    result->outcome = OW_WILD_CHAIN_RETRY;
    decision = OVERWORLD_MOTION_DECISION_PROFILE;
    if (object == NULL) {
        goto finished;
    }
    startIndex = gf_rand();
    if ((encodedRemaining & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) != 0) {
        startIndex = 0x56703412u
            >> (state->movementPendingDirections[slot] << 2);
    }
    distance = (encodedRemaining & OW_WILD_SPAWNER_CHAIN_REPOSITION_FLAT_MASK)
            == OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID
        ? lane->chainRepositionDistance
        : 1;
    for (attempt = 0; attempt < 8; attempt++) {
        directionIndex = (startIndex + attempt) & 7;
        if (((&lane->chainRepositionAllowCardinal)[directionIndex >> 2]
                & OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOW_CARDINAL_MASK) == 0) {
            continue;
        }
        packedOffset = 0xA8206491u >> (directionIndex << 2);
        targetX = object->xCurr + ((packedOffset & 3) - 1) * distance;
        targetY = object->yCurr
            + (((packedOffset >> 2) & 3) - 1) * distance;
        decision = OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
                state,
                slot,
                state->movementFieldSystem,
                lane->chillAllowedTerrainMask,
                targetX,
                targetY,
                targetX,
                targetY);
        if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
            result->gridDelta = (s8)((packedOffset & 3) - 1
                + (((packedOffset >> 2) & 3) - 1) * 4);
            decision = OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
                state,
                state->movementFieldSystem,
                slot,
                object,
                directionIndex,
                distance,
                targetX,
                targetY,
                profile,
                TRUE,
                0);
        }
        if (decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
            result->encodedRemaining = remaining | (lane->chainRepositionDust << 4)
                | OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING
                | (encodedRemaining
                    & OW_WILD_SPAWNER_CHAIN_REPOSITION_FLAT_MASK);
            result->outcome = OW_WILD_CHAIN_STARTED;
            result->reason = OVERWORLD_MOTION_DECISION_ACCEPTED;
            state->movementStagedHopPending[slot] = TRUE;
            return TRUE;
        }
        if (decision != OVERWORLD_MOTION_DECISION_BLOCKED
            && decision != OVERWORLD_MOTION_DECISION_TERRAIN) {
            retry = TRUE;
            /* An unknown/prepared failure can have native prep side effects.
             * Only occupancy is safe to search past within this attempt. */
            if (decision != OVERWORLD_MOTION_DECISION_OCCUPIED) {
                goto finished;
            }
        }
    }
    if (!retry) {
        result->outcome = OW_WILD_CHAIN_ABORT;
        decision = OVERWORLD_MOTION_DECISION_NO_CANDIDATE;
    } else {
        decision = OVERWORLD_MOTION_DECISION_OCCUPIED;
    }
finished:
    result->gridDelta = 0;
    result->reason = decision;
    return FALSE;
}
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
static BOOL OverworldWildSpawns_StageHopTarget(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile,
    int targetX,
    int targetY,
    u8 direction,
    u8 distance,
    BOOL finishWithTired);
static BOOL OverworldWildSpawns_TryStartCustomJumpRamProbe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem);
#else
#define OverworldWildSpawns_TryStartCustomJumpRamProbe(state, fieldSystem) FALSE
#endif
static void OverworldWildSpawns_DespawnFarMons(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static BOOL OverworldWildSpawns_TryRefill(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static void OverworldWildSpawns_CommitQueuedSpawn(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static u16 OverworldWildSpawns_GetThrowParticipantMask(OverworldWildSpawnState *state);
static BOOL OverworldWildSpawns_TickCustomJumpRenderSettle(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot);
static void __attribute__((optimize("Os")))
OverworldWildSpawns_ReconcileNativeShadow(
    FieldSystem *fieldSystem,
    LocalMapObject *object);
static void OverworldWildSpawns_ResetPlayerBallShadowTracking(
    OverworldWildSpawnState *state);
static void OverworldWildSpawns_SyncPlayerBallShadowObject(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    LocalMapObject *ballObject);
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
static BOOL OverworldWildSpawns_StageHopTarget(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile,
    int targetX,
    int targetY,
    u8 direction,
    u8 distance,
    BOOL finishWithTired)
{
    int objectX;
    int objectY;
    int dx;
    int dy;
    u8 resolvedDistance;
    u8 resolvedDirection;
    u8 spotState;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || profile == NULL) {
        return FALSE;
    }

    objectX = object->xCurr;
    objectY = object->yCurr;
    dx = targetX - objectX;
    dy = targetY - objectY;
    spotState = state->movementSpotStates[slot];
#if OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS
    if (OverworldWildSpawns_IsShiftedSouthLandAnchorHop(
            fieldSystem,
            objectX,
            objectY,
            targetX,
            targetY)) {
        resolvedDirection = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP;
        resolvedDistance = OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES;
    } else
#endif
#if OW_WILD_SPAWNER_CANOPY_SHIFT_NORTH_LAND_ANCHORS
    if (OverworldWildSpawns_IsShiftedNorthLandAnchorHop(
            fieldSystem,
            objectX,
            objectY,
            targetX,
            targetY)) {
        resolvedDirection = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
        resolvedDistance = OW_WILD_SPAWNER_CANOPY_NORTH_LAND_SHIFT_TILES;
    } else
#endif
    if (!OverworldWildSpawns_TryGetBehaviorHopVector(
            profile,
            spotState,
            dx,
            dy,
            &resolvedDirection,
            &resolvedDistance)) {
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        return FALSE;
    }
    direction = resolvedDirection;
    distance = resolvedDistance;

    state->movementStagedHopOriginX[slot] = (s16)objectX;
    state->movementStagedHopOriginY[slot] = (s16)objectY;
    state->movementStagedHopTargetX[slot] = (s16)targetX;
    state->movementStagedHopTargetY[slot] = (s16)targetY;
    state->movementStagedHopDistances[slot] = distance;
    state->movementStagedHopFinishWithTired[slot] = finishWithTired;
    state->movementStagedHopPending[slot] = TRUE;
    state->movementCooldowns[slot] = OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES;
    OverworldWildSpawns_SetObjectFacing(object, direction);
    OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
    OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 8);

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#else
    (void)fieldSystem;
#endif
    return TRUE;
}

static void OverworldWildSpawns_RecordCustomJumpRamObject(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    int stage);
#else
#define OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, stage) ((void)0)
#endif
static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_FinishPendingStagedHop(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object);
static LocalMapObject *__attribute__((noinline)) OverworldWildSpawns_RecreateSpawnObjectAtTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    int x,
    int y);
static BOOL OverworldWildSpawns_TickStagedHopMovementListTask(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    BOOL *finished);
static void OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe(void);
static void OverworldWildSpawns_UpdateMankeyTreeTopLayerProbe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem);
static void OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem);
static void OverworldWildSpawns_ClearMankeyTreeTopLateDrawEffect(int slot);
static void OverworldWildSpawns_EnsureMankeyTreeTopLateDrawEffect(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object);
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_LATE_DRAW_EFFECT_ENABLED
static BOOL OverworldWildSpawns_MankeyTreeTopLateDrawEffectInit(void *effect, void *work);
static void OverworldWildSpawns_MankeyTreeTopLateDrawEffectDestroy(void *effect, void *work);
static void OverworldWildSpawns_MankeyTreeTopLateDrawEffectUpdate(void *effect, void *work);
static void OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender(void *effect, void *work);
#endif
#endif
static BOOL OverworldWildSpawns_RunImmediateCanopyMovementCommand(LocalMapObject *object, u32 movementCommand);
#if OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY \
    || OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY \
    || OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE void *sOverworldWildDiagnosticMapObjectMan;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE void *sOverworldWildDiagnosticMapObjects;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildDiagnosticStateMapId;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE void *sOverworldWildDiagnosticStateMapObjectMan;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE void *sOverworldWildDiagnosticStateMapObjects;
#endif
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u8 sOverworldWildMovementDiagnosticDirectionBlocked;
#if OW_WILD_SPAWNER_PERF_DIAGNOSTICS
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfProfileResolvesThisFrame;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfProfileCacheHitsThisFrame;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfTargetScansThisFrame;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfMapObjectCreatesThisFrame;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfMapObjectDeletesThisFrame;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfActiveFrameSlotsThisFrame;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE u16 sOverworldWildPerfMovementCommandsThisFrame;

static void OverworldWildSpawns_PerfResetFrameCounters(void)
{
    sOverworldWildPerfProfileResolvesThisFrame = 0;
    sOverworldWildPerfProfileCacheHitsThisFrame = 0;
    sOverworldWildPerfTargetScansThisFrame = 0;
    sOverworldWildPerfMapObjectCreatesThisFrame = 0;
    sOverworldWildPerfMapObjectDeletesThisFrame = 0;
    sOverworldWildPerfActiveFrameSlotsThisFrame = 0;
    sOverworldWildPerfMovementCommandsThisFrame = 0;
}

static void OverworldWildSpawns_PerfInc(u16 *counter)
{
    if (counter != NULL && *counter != 0xFFFF) {
        (*counter)++;
    }
}
#define OW_WILD_PERF_RESET_FRAME() OverworldWildSpawns_PerfResetFrameCounters()
#define OW_WILD_PERF_INC(counter) OverworldWildSpawns_PerfInc(&(counter))
#else
#define OW_WILD_PERF_RESET_FRAME() ((void)0)
#define OW_WILD_PERF_INC(counter) ((void)0)
#endif
#if OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE
static u8 sOverworldWildTiredBubbleIdProbe = OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN;
#endif

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND
static BOOL OverworldWildSpawns_UpdateSpawnerMovementCommand(LocalMapObject *object);
static BOOL OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot(
    OverworldWildSpawnState *state,
    int slot);
#endif
static void OverworldWildSpawns_TickFrameMovementDecisionCounter(void);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
static void OverworldWildSpawns_FrameMovementTask(SysTask *task, void *data);
static void OverworldWildSpawns_EnsureFrameMovementTask(OverworldWildSpawnState *state, FieldSystem *fieldSystem);
static void OverworldWildSpawns_StopFrameMovementTask(void);
#endif
static void OverworldWildSpawns_CancelDeferredBattleScript(void);
static BOOL OverworldWildSpawns_QueueBattleScriptTask(FieldSystem *fieldSystem, LocalMapObject *object);
static BOOL OverworldWildSpawns_RequestBattleScript(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot);
#if OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_ENABLED
static BOOL sOverworldWildCustomJumpRenderSettleActive[OW_WILD_MAX_SPAWNS];
static s32 sOverworldWildCustomJumpRenderSettleStartX[OW_WILD_MAX_SPAWNS];
static s32 sOverworldWildCustomJumpRenderSettleStartY[OW_WILD_MAX_SPAWNS];
static u32 sOverworldWildCustomJumpRenderSettleElapsedFrames[OW_WILD_MAX_SPAWNS];
#endif
#if OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS
static BOOL sOverworldWildCustomJumpVisibleLegFinished[OW_WILD_MAX_SPAWNS];
#endif
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamStage;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeTriggers;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeStarts;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeFailures;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeActiveSlots;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeCurrentSlots;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeMankeySlots;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeObjectSlots;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamProbeLastSpecies;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamSlot;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamStartX;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamStartY;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamTargetX;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamTargetY;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamCurrentX;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamCurrentY;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamRenderX;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamRenderY;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamRenderFx32X;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamRenderFx32Y;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamElapsedFrames;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamFrameCount;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamFlags;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamPending;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamActive;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamVisibleLeg;
static OW_WILD_SPAWNER_DIAGNOSTIC_STORAGE int sOverworldWildCustomJumpRamFinalLanding;
static BOOL sOverworldWildCustomJumpRamProbeKeyDown;
#endif
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
typedef struct OverworldWildStagedHopMovementList {
    SysTask *task;
    u16 commands[OW_WILD_SPAWNER_STAGED_HOP_MOVEMENT_COMMAND_WORDS];
} OverworldWildStagedHopMovementList;

typedef char OverworldWildStagedHopMovementListSizeMustRemain144Bytes[
    sizeof(OverworldWildStagedHopMovementList)
            == OW_WILD_STAGED_HOP_MOVEMENT_LIST_WORDS * sizeof(u16)
        ? 1
        : -1];

static SysTask *sOverworldWildMovementFrameTask;
static SysTask *sOverworldWildDeferredBattleScriptTask;
static OverworldWildSpawnState *sOverworldWildDeferredBattleState;
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED
static BOOL sOverworldWildMankeyTreeTopPriorityBitsSaved[OW_WILD_MAX_SPAWNS];
static u32 sOverworldWildMankeyTreeTopPrioritySavedBits[OW_WILD_MAX_SPAWNS];
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED
static BOOL sOverworldWildMankeyTreeTopDrawCallbacksSaved[OW_WILD_MAX_SPAWNS];
static void (*sOverworldWildMankeyTreeTopSavedDrawCallbacks[OW_WILD_MAX_SPAWNS])(LocalMapObject *);
#endif
#endif
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED
static BOOL sOverworldWildMankeyTreeTopLayerProbeActive;
static u8 sOverworldWildMankeyTreeTopLayerProbeTimer;
static u8 sOverworldWildMankeyTreeTopLayerProbePhase;
#endif
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ENABLED
static u8 sOverworldWildMankeyTreeTopBubbleProbeTimer;
#endif
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_LATE_DRAW_EFFECT_ENABLED
static void *sOverworldWildMankeyTreeTopLateDrawEffects[OW_WILD_MAX_SPAWNS];
#endif
#endif
static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_ValidateHopLandingValue(
    u16 serviceVersion,
    int slot,
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int x,
    int y,
    int finalTargetX,
    int finalTargetY)
{
    if (serviceVersion != OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION) {
        return FALSE;
    }
    return OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
        &sOverworldWildSpawnState,
        slot,
        fieldSystem,
        allowedTile,
        x,
        y,
        finalTargetX,
        finalTargetY);
}

BOOL __attribute__((noinline, optimize("Os", "no-gcse-lm"),
    section(".overworld_wild_native_shadow_value")))
OverworldWildSpawns_CopyNativeShadowValue(
    LocalMapObject *object,
    OverworldWildNativeShadowValue *value)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildSpawn *spawn;
    FieldSystem *fieldSystem;
    OverworldActorFieldContext context;
    int slot;

    if (object == NULL || value == NULL
        || value->version != OVERWORLD_WILD_NATIVE_SHADOW_VALUE_VERSION
        || value->size != sizeof(*value)) {
        return FALSE;
    }
    value->baseY = 0;
    value->active = FALSE;
    slot = object->id - OW_WILD_OBJECT_ID_START;
    if ((u32)slot >= OW_WILD_MAX_SPAWNS || value->slot != slot) {
        return FALSE;
    }
    spawn = &sOverworldWildSpawnState.spawns[slot];
    fieldSystem = sOverworldWildSpawnState.movementFieldSystem;
    context = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    if (!spawn->active
        || spawn->object != object
        || fieldSystem == NULL
        || fieldSystem->mapObjectMan == NULL
        || GetMapObjectByID(fieldSystem->mapObjectMan, spawn->objectId)
            != object
        || OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(context)
            != sOverworldWildSpawnState.mapGeneration
        || (value->encounterGeneration != 0
            && value->encounterGeneration != spawn->encounterGeneration)) {
        return FALSE;
    }
    value->encounterGeneration = spawn->encounterGeneration;
    runtime = OW_WILD_RUNTIME(&sOverworldWildSpawnState);
    if (runtime != NULL && runtime->movementCustomJumpActive[slot]) {
        value->baseY = runtime->movementCustomJumpShadowBaseY[slot];
        value->active = TRUE;
    }
    return TRUE;
}

const OverworldWildSpawnsOverlayEntry gOverworldWildSpawnsOverlayEntry __attribute__((section(".overworld_wild_spawns_entry"), used)) = {
    OverworldWildSpawns_OverlayOnPlayerStep,
    OverworldWildSpawns_OverlayTryPrimeBattleFromTalk,
    OverworldWildSpawns_OverlayCleanupPendingBattle,
    OverworldWildSpawns_CleanupResidentData,
    OverworldWildSpawns_OverlayOnPlayerFrame,
    OverworldWildSpawns_OverlayOnFieldBusy,
    OverworldWildSpawns_ApplyTransitionWork,
    OverworldWildSpawns_ValidateHopLandingValue,
    OverworldWildSpawns_CopyNativeShadowValue,
    OverworldWildSpawns_BeginMountSelectedFollower,
};

static OverworldWildOverlayRuntimeState *OverworldWildSpawns_EnsureRuntimeState(
    OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL) {
        return NULL;
    }

    sOverworldWildLastState = state;

    runtime = (OverworldWildOverlayRuntimeState *)state->movementRuntimeState;
    if (runtime == NULL) {
        runtime = sys_AllocMemory(HEAPID_WORLD, sizeof(*runtime));
        state->movementRuntimeState = runtime;
        if (runtime != NULL) {
            memset(runtime, 0, sizeof(*runtime));
        }
    }

    return runtime;
}

static inline OverworldWildBehaviorConditionRuntime *
OverworldWildSpawns_EnsureConditionRuntime(OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime =
        OverworldWildSpawns_EnsureRuntimeState(state);

    if (runtime == NULL) {
        return NULL;
    }
    if (runtime->conditions == NULL) {
        runtime->conditions = sys_AllocMemory(
            HEAPID_WORLD,
            sizeof(*runtime->conditions));
        if (runtime->conditions != NULL) {
            memset(runtime->conditions, 0, sizeof(*runtime->conditions));
        }
    }
    return runtime->conditions;
}


#define OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT 8

#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_LATE_DRAW_EFFECT_ENABLED
static const OverworldWildFieldEffectDescriptor sOverworldWildMankeyTreeTopLateDrawEffectDescriptor = {
    sizeof(OverworldWildMankeyTreeTopLateDrawEffectWork),
    OverworldWildSpawns_MankeyTreeTopLateDrawEffectInit,
    OverworldWildSpawns_MankeyTreeTopLateDrawEffectDestroy,
    OverworldWildSpawns_MankeyTreeTopLateDrawEffectUpdate,
    OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender,
};
#endif
static int OverworldWildSpawns_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildSpawns_Max(int a, int b)
{
    return a > b ? a : b;
}

#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_PRIORITY_OVERRIDE_ENABLED
static void OverworldWildSpawns_SaveMankeyTreeTopPriorityBits(int slot, LocalMapObject *object)
{
    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS || object == NULL
        || sOverworldWildMankeyTreeTopPriorityBitsSaved[slot]) {
        return;
    }

    sOverworldWildMankeyTreeTopPrioritySavedBits[slot] =
        object->flags & OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS;
    sOverworldWildMankeyTreeTopPriorityBitsSaved[slot] = TRUE;
}

static void OverworldWildSpawns_RestoreMankeyTreeTopPriorityBits(int slot, LocalMapObject *object)
{
    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS
        || !sOverworldWildMankeyTreeTopPriorityBitsSaved[slot]) {
        return;
    }

    if (object != NULL) {
        OverworldWildSpawns_ClearObjectFlags(object, OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS);
        OverworldWildSpawns_SetObjectFlags(object, sOverworldWildMankeyTreeTopPrioritySavedBits[slot]);
    }
    sOverworldWildMankeyTreeTopPrioritySavedBits[slot] = 0;
    sOverworldWildMankeyTreeTopPriorityBitsSaved[slot] = FALSE;
}
#endif

#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED
static void OverworldWildSpawns_SaveMankeyTreeTopDrawCallback(int slot, LocalMapObject *object)
{
    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS || object == NULL
        || sOverworldWildMankeyTreeTopDrawCallbacksSaved[slot]) {
        return;
    }

    sOverworldWildMankeyTreeTopSavedDrawCallbacks[slot] = object->unkC8;
    sOverworldWildMankeyTreeTopDrawCallbacksSaved[slot] = TRUE;
}

static void OverworldWildSpawns_RestoreMankeyTreeTopDrawCallback(int slot, LocalMapObject *object)
{
    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS
        || !sOverworldWildMankeyTreeTopDrawCallbacksSaved[slot]) {
        return;
    }

    if (object != NULL) {
        object->unkC8 = sOverworldWildMankeyTreeTopSavedDrawCallbacks[slot];
    }
    sOverworldWildMankeyTreeTopSavedDrawCallbacks[slot] = NULL;
    sOverworldWildMankeyTreeTopDrawCallbacksSaved[slot] = FALSE;
}
#endif

static void OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride(int slot, LocalMapObject *object)
{
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED
    OverworldWildSpawns_RestoreMankeyTreeTopDrawCallback(slot, object);
#endif
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_PRIORITY_OVERRIDE_ENABLED
    OverworldWildSpawns_RestoreMankeyTreeTopPriorityBits(slot, object);
#else
    (void)slot;
    (void)object;
#endif
#else
    (void)slot;
    (void)object;
#endif
}

static void OverworldWildSpawns_ApplyMankeyTreeTopRenderOverride(int slot, LocalMapObject *object)
{
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED
    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS || object == NULL) {
        return;
    }

#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_PRIORITY_OVERRIDE_ENABLED
    OverworldWildSpawns_SaveMankeyTreeTopPriorityBits(slot, object);
    OverworldWildSpawns_ClearObjectFlags(object, OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS);
#endif
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED
    OverworldWildSpawns_SaveMankeyTreeTopDrawCallback(slot, object);
    object->unkC8 = OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK;
#endif
#else
    (void)slot;
    (void)object;
#endif
}

static void OverworldWildSpawns_ClearMankeyTreeTopCache(OverworldWildSpawnState *state, int slot)
{
    OverworldWildOverlayRuntimeState *runtime = OverworldWildSpawns_EnsureRuntimeState(state);

    if (runtime == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    OverworldWildSpawns_ClearMankeyTreeTopLateDrawEffect(slot);
    runtime->movementMankeyTreeTopCacheValid[slot] = FALSE;
    runtime->movementMankeyTreeTopCacheResult[slot] = FALSE;
    runtime->movementMankeyTreeTopCacheX[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    runtime->movementMankeyTreeTopCacheY[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    runtime->movementMankeyTreeTopCacheMapId[slot] = MAP_NOTHING;
    runtime->movementMankeyTreeTopLandingExpected[slot] = FALSE;
    runtime->movementMankeyTreeTopSettled[slot] = FALSE;
    runtime->movementMankeyTreeTopSettledX[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    runtime->movementMankeyTreeTopSettledY[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
}

static void OverworldWildSpawns_ClearMankeyTreeTopProxyObject(
    OverworldWildSpawnState *state,
    int slot,
    BOOL deleteObject)
{
    FieldSystem *fieldSystem;
    LocalMapObject *proxyObject;

    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    proxyObject = state->movementMankeyTreeTopProxyObjects[slot];
    state->movementMankeyTreeTopProxyObjects[slot] = NULL;
    if (proxyObject == NULL || !deleteObject) {
        return;
    }

    fieldSystem = state->movementFieldSystem;
    if (OverworldWildSpawns_IsPresentationFieldContextCurrent(state, fieldSystem)
        && OverworldWildSpawns_IsCurrentMapObject(fieldSystem, proxyObject)
        && proxyObject->id == OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START + slot) {
        DeleteMapObject(proxyObject);
        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);
    }
}

static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *fieldSystem, const OverworldWildSpawn *spawn)
{
    if (fieldSystem == NULL
        || fieldSystem->location == NULL
        || !spawn->active
        || spawn->mapId != fieldSystem->location->mapId
        || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, spawn->object)) {
        return FALSE;
    }

    return (spawn->object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && spawn->object->id == spawn->objectId
        && spawn->object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
}

static void OverworldWildSpawns_PersistSavedShinies(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
#ifdef ALLOW_SAVE_CHANGES
    struct SAVE_MISC_DATA *saveMiscData;

    if (state == NULL || fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return;
    }

    saveMiscData = Sav2_Misc_get(fieldSystem->savedata);
    if (saveMiscData == NULL
        || sizeof(saveMiscData->overworldWildSavedShinies) < sizeof(state->savedShinies)) {
        return;
    }

    memcpy(
        saveMiscData->overworldWildSavedShinies,
        state->savedShinies,
        sizeof(state->savedShinies));
#else
    (void)state;
    (void)fieldSystem;
#endif
}

static void OverworldWildSpawns_LoadSavedShinies(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
#ifdef ALLOW_SAVE_CHANGES
    struct SAVE_MISC_DATA *saveMiscData;
    int i;

    if (state == NULL
        || state->savedShiniesLoaded
        || fieldSystem == NULL
        || fieldSystem->savedata == NULL) {
        return;
    }

    saveMiscData = Sav2_Misc_get(fieldSystem->savedata);
    if (saveMiscData == NULL
        || sizeof(saveMiscData->overworldWildSavedShinies) < sizeof(state->savedShinies)) {
        return;
    }

    if (saveMiscData->overworldWildShinyCounterMagic != OVERWORLD_WILD_SHINY_COUNTER_SAVE_MAGIC) {
        if (saveMiscData->overworldWildShinyCounterMagic != OVERWORLD_WILD_SHINY_COUNTER_SAVE_MAGIC_V1) {
            saveMiscData->overworldWildShinySpawnCounter = 0;
        }
        saveMiscData->overworldWildShinyCounterMagic = OVERWORLD_WILD_SHINY_COUNTER_SAVE_MAGIC;
        memset(saveMiscData->overworldWildSavedShinies, 0, sizeof(saveMiscData->overworldWildSavedShinies));
    }

    memcpy(
        state->savedShinies,
        saveMiscData->overworldWildSavedShinies,
        sizeof(state->savedShinies));
    for (i = 0; i < OW_WILD_MAX_SAVED_SHINIES; i++) {
        if ((state->savedShinies[i].terrainAndActive & OW_WILD_SAVED_SHINY_ACTIVE) != 0
            && (state->savedShinies[i].mapId == MAP_NOTHING
                || (state->savedShinies[i].speciesAndForm & OW_WILD_SPECIES_MASK) == SPECIES_NONE
                || state->savedShinies[i].level == 0)) {
            state->savedShinies[i].terrainAndActive = 0;
        }
    }

    state->savedShiniesLoaded = TRUE;
#else
    (void)state;
    (void)fieldSystem;
#endif
}

static void OverworldWildSpawns_ClearSavedShiny(OverworldWildSpawnState *state, int slot)
{
    state->savedShinies[slot].terrainAndActive = 0;
    OverworldWildSpawns_PersistSavedShinies(state, state->movementFieldSystem);
}

static void OverworldWildSpawns_TrySaveShinyReservation(OverworldWildSpawnState *state, const OverworldWildSpawn *spawn)
{
    int i;

    if (spawn == &state->spawns[OW_WILD_FOLLOWER_SLOT]
        || !spawn->active
        || !spawn->shiny
        || spawn->species == SPECIES_NONE
        || spawn->mapId == MAP_NOTHING) {
        return;
    }

    for (i = 0; i < OW_WILD_MAX_SAVED_SHINIES; i++) {
        if ((state->savedShinies[i].terrainAndActive & OW_WILD_SAVED_SHINY_ACTIVE) == 0) {
            state->savedShinies[i].mapId = spawn->mapId;
            state->savedShinies[i].speciesAndForm =
                spawn->species | (spawn->form << OW_WILD_FORM_SHIFT);
            state->savedShinies[i].level = spawn->level;
            state->savedShinies[i].terrainAndActive =
                OW_WILD_SAVED_SHINY_ACTIVE | (spawn->terrain & OW_WILD_SAVED_SHINY_TERRAIN_MASK);
            OverworldWildSpawns_PersistSavedShinies(state, state->movementFieldSystem);
            return;
        }
    }
}

static int OverworldWildSpawns_FindSavedShiny(OverworldWildSpawnState *state, u16 mapId, OverworldWildSpawnTerrain terrain)
{
    int i;

    for (i = 0; i < OW_WILD_MAX_SAVED_SHINIES; i++) {
        if ((state->savedShinies[i].terrainAndActive & OW_WILD_SAVED_SHINY_ACTIVE) != 0
            && state->savedShinies[i].mapId == mapId
            && (state->savedShinies[i].terrainAndActive & OW_WILD_SAVED_SHINY_TERRAIN_MASK) == terrain) {
            return i;
        }
    }

    return -1;
}

static void OverworldWildSpawns_LoadSavedShinyEncounter(OverworldWildSpawnState *state, int slot, OverworldWildRolledEncounter *encounter)
{
    encounter->personality = gf_rand() | (gf_rand() << 16);
    encounter->species = state->savedShinies[slot].speciesAndForm & OW_WILD_SPECIES_MASK;
    encounter->form = state->savedShinies[slot].speciesAndForm >> OW_WILD_FORM_SHIFT;
    encounter->level = state->savedShinies[slot].level;
}

static void OverworldWildSpawns_ClearSlotAndSaveShiny(OverworldWildSpawnState *state, int slot, BOOL deleteObject)
{
    OverworldWildSpawns_TrySaveShinyReservation(state, &state->spawns[slot]);
    OverworldWildSpawns_ResetSlotState(state, slot, deleteObject);
}

static BOOL OverworldWildSpawns_QuarantinePoisonedPresentation(
    FieldSystem *fieldSystem,
    int slot)
{
    MapObjectMan *manager;
    BOOL quarantined = FALSE;
    int i;

    if (fieldSystem == NULL || fieldSystem->mapObjectMan == NULL) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager->objects == NULL) {
        return FALSE;
    }

    for (i = 0; i < (int)manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && object->id == OW_WILD_OBJECT_ID_START + slot
            && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
            DeleteMapObject(object);
            quarantined = TRUE;
        }
    }
    return quarantined;
}

static BOOL OverworldWildSpawns_ReconcileSpawnPresentations(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    const OverworldWildHelperOverlayEntry *helperEntry =
        OverworldWildSpawns_GetHelperOverlayEntry();
    int result;
    int slot;

    if (helperEntry == NULL || helperEntry->reconcilePresentations == NULL) {
        state->presentationRestorePending = TRUE;
        return FALSE;
    }
    for (;;) {
        result = helperEntry->reconcilePresentations(
            fieldSystem,
            state,
            &OW_WILD_RUNTIME(state)->spawnPresentations,
            &OW_WILD_RUNTIME(state)->despawnTelemetry,
            OverworldWildSpawns_RecreateSpawnObjectAtTile);
        if (result == OW_WILD_RECONCILE_COMPLETE) {
            state->presentationRestorePending = FALSE;
            return TRUE;
        }
        state->presentationRestorePending = TRUE;
        slot = result - OW_WILD_RECONCILE_POISONED_SLOT_BASE;
        if (result < OW_WILD_RECONCILE_POISONED_SLOT_BASE
            || slot >= OW_WILD_MAX_SPAWNS
            || state->pendingSlot == slot
            || state->movementQueuedBattleSlot == slot
            || (OverworldWildSpawns_GetThrowParticipantMask(state)
                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0) {
            return FALSE;
        }
        (void)OverworldWildSpawns_QuarantinePoisonedPresentation(
            fieldSystem,
            slot);
        OverworldWildSpawns_ClearSlotAndSaveShiny(state, slot, TRUE);
    }
}

#if !OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY || !OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
static void __attribute__((noinline)) OverworldWildSpawns_ResetAmbientCryCooldown(OverworldWildSpawnState *state)
{
    state->ambientCryCooldown = OW_WILD_AMBIENT_CRY_MIN_COOLDOWN_STEPS
        + (gf_rand() % OW_WILD_AMBIENT_CRY_RANDOM_COOLDOWN_STEPS);
}
#endif

#if !OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY
static void OverworldWildSpawns_TryPlayAmbientCry(OverworldWildSpawnState *state)
{
    int i;
    int activeCount = 0;
    u8 cooldownTick;
    int chosen;
    u16 throwTargetMask = OW_WILD_RUNTIME(state)->throwState.targetMask;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (i != OW_WILD_FOLLOWER_SLOT
            && state->spawns[i].active
            && state->spawns[i].object != NULL
            && (throwTargetMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) == 0) {
            activeCount++;
        }
    }

    if (activeCount == 0) {
        OverworldWildSpawns_ResetAmbientCryCooldown(state);
        return;
    }

    cooldownTick = 1 + (activeCount / 3);
    if (cooldownTick > OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK) {
        cooldownTick = OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK;
    }

    if (state->ambientCryCooldown > cooldownTick) {
        state->ambientCryCooldown -= cooldownTick;
        return;
    }

    chosen = gf_rand() % activeCount;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (i != OW_WILD_FOLLOWER_SLOT
            && state->spawns[i].active
            && state->spawns[i].object != NULL
            && (throwTargetMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) == 0) {
            if (chosen == 0) {
                PlayCry(
                    state->spawns[i].species,
                    state->spawns[i].form);
                OverworldWildSpawns_ResetAmbientCryCooldown(state);
                return;
            }
            chosen--;
        }
    }

    OverworldWildSpawns_ResetAmbientCryCooldown(state);
}
#endif

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
static int OverworldWildSpawns_DiagnosticAbs(int value)
{
    return value < 0 ? -value : value;
}

static BOOL OverworldWildSpawns_IsMovementSlotInProgress(OverworldWildSpawnState *state, int slot)
{
    return (state->movementInProgressMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
}

static BOOL OverworldWildSpawns_IsNativeHeldMovementOwned(OverworldWildSpawnState *state, int slot)
{
    return (OW_WILD_RUNTIME(state)->movementNativeHeldMask
        & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
}

static u16 __attribute__((noinline)) OverworldWildSpawns_GetAllowedTileForSpotState(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    const OverworldWildBehaviorProfileData *lane =
        OverworldWildSpawns_GetControllerLane(profile, spotState);

    return lane->chillAllowedTerrainMask;
}

static u8 OverworldWildSpawns_GetTeleportPauseFrames(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    u8 teleportPause;

    if (profile == NULL) {
        return OW_WILD_SPAWNER_TELEPORT_POST_COOLDOWN_FRAMES;
    }

    teleportPause = OverworldWildSpawns_GetControllerLane(
        profile,
        spotState)->teleportPause;

    return teleportPause;
}

static BOOL OverworldWildSpawns_BehaviorUsesAsleep(u8 behavior)
{
    return behavior == OW_WILD_BEHAVIOR_KIND_ASLEEP;
}

static BOOL OverworldWildSpawns_BehaviorKindUsesMovement(u8 behavior)
{
    switch (behavior) {
    case OW_WILD_BEHAVIOR_KIND_WANDER:
    case OW_WILD_BEHAVIOR_KIND_CHASE:
    case OW_WILD_BEHAVIOR_KIND_FLEE:
    case OW_WILD_BEHAVIOR_KIND_PLAYFUL:
    case OW_WILD_BEHAVIOR_KIND_RAM:
    case OW_WILD_BEHAVIOR_KIND_HEADBUTT_TREE_HOP:
        return TRUE;
    default:
        return FALSE;
    }
}

static u32 OverworldWildSpawns_GetFrameMovementWorkForSlot(
    OverworldWildSpawnState *state,
    int slot)
{
    u16 slotMask;

    if (!state->spawns[slot].active
        || state->spawns[slot].object == NULL) {
        return FALSE;
    }
    slotMask = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);

    if (OverworldWildSpawns_IsMovementSlotInProgress(state, slot)
        || state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_HOP
        || state->movementStagedHopPending[slot]
        || state->movementQueuedBattleSlot == slot
        || state->movementCrashShakeTimers[slot] != 0
        || OW_WILD_RUNTIME(state)->movementCustomJumpActive[slot]
        || (state->movementTeleportVisiblePause[slot]
            && state->movementCooldowns[slot] != 0)
        || state->movementTeleportFlickerTimers[slot] != 0) {
        return slotMask | ((u32)slotMask << OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT);
    }

    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_EMOTING
        || (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_TIRED
            && state->movementEmoteTimers[slot] != 0)) {
        return slotMask | ((u32)slotMask << OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT);
    }
    if (state->movementCooldowns[slot] != 0) {
        return slotMask;
    }
    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        return OW_WILD_RUNTIME(state)->movementFrameDrivenOwnerMask & slotMask;
    }
    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        return OW_WILD_RUNTIME(state)->movementFrameDrivenTiredMask & slotMask;
    }

    return FALSE;
}

static u32 OverworldWildSpawns_GetFrameMovementWork(
    OverworldWildSpawnState *state)
{
    u32 frameWork;
    int i;

    if (state == NULL) {
        return FALSE;
    }
    frameWork = state->movementInProgressMask
        | ((u32)state->movementInProgressMask << OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT);
    if (OverworldWildSpawns_HasQueuedBattle(state)
        || (state->movementRuntimeState != NULL
            && ((OW_WILD_RUNTIME(state)->movementHelpSpawnParentSlotPlusOne != 0
                    && OW_WILD_RUNTIME(state)->movementHelpSpawnRemaining != 0)
                || OW_WILD_RUNTIME(state)->throwState.targetMask != 0
                || OW_WILD_RUNTIME(state)->throwState.carrierMask != 0))) {
        frameWork |= OW_WILD_SPAWNER_FRAME_WORK_GLOBAL;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        frameWork |= OverworldWildSpawns_GetFrameMovementWorkForSlot(state, i);
    }

    return frameWork;
}

static u16 OverworldWildSpawns_SelectIdleAiWork(
    OverworldWildSpawnState *state,
    u16 eligibleMask)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);

    if (++runtime->movementIdleAiCursor >= OW_WILD_MAX_SPAWNS) {
        runtime->movementIdleAiCursor = 0;
    }
    /* Timers already advance for every actor on the same field frame. Let
     * every actor whose timer expires make its next choice on that frame too.
     * Round-robin selection stretched short authored pauses by as much as one
     * full slot cycle and made otherwise independent Pokemon look serialized. */
    return eligibleMask;
}

static BOOL OverworldWildSpawns_IsPresentationFieldContextCurrent(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    const OverworldWildHelperOverlayEntry *helperEntry;

    if (fieldSystem == NULL
        || (!sOverworldWildHelperOverlayReady
            && !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER))) {
        return FALSE;
    }
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL) {
        return FALSE;
    }
    return helperEntry->isPresentationContextCurrent(fieldSystem, state);
}

static BOOL OverworldWildSpawns_IsMovementFieldContextCurrent(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    if (fieldSystem == NULL || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }
    return OverworldWildSpawns_IsPresentationFieldContextCurrent(state, fieldSystem);
}

static u16 OverworldWildSpawns_GetCurrentMovementSpawnMask(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    u16 currentMask = 0;
    int i;

    if (state == NULL || fieldSystem == NULL) {
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (!state->spawns[i].active) {
            continue;
        }
        if (OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[i])) {
            currentMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i);
        } else {
            state->presentationRestorePending = TRUE;
            OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask |=
                OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i);
        }
    }

    return currentMask;
}

static void OverworldWildSpawns_SetMovementSlotInProgress(OverworldWildSpawnState *state, int slot)
{
    state->movementInProgressMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
}

static void OverworldWildSpawns_CancelNativeHeldMovementForSlot(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    u16 slotMask;

    if (!OverworldWildSpawns_IsNativeHeldMovementOwned(state, slot)) {
        return;
    }
    slotMask = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    MapObject_ClearHeldMovement(object);
    MapObject_ClearSingleMovementActive(object);
    OW_WILD_RUNTIME(state)->movementNativeHeldMask &= ~slotMask;
    state->movementInProgressMask &= ~slotMask;
    state->movementPreviousTileLocked[slot] = FALSE;
    OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
}

static void OverworldWildSpawns_CancelNativeHeldMovement(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    int i;

    if (state->movementRuntimeState == NULL
        || OW_WILD_RUNTIME(state)->movementNativeHeldMask == 0
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)) {
        return;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (OverworldWildSpawns_IsNativeHeldMovementOwned(state, i)) {
            OverworldWildSpawns_CancelNativeHeldMovementForSlot(
                state,
                i,
                state->spawns[i].object);
        }
    }
}

static u32 OverworldWildSpawns_GetBehaviorGroupFlags(u16 species)
{
    OverworldWildSpawnMetadata metadata;

    if (OVERWORLD_WILD_SPAWN_METADATA_ENTRY->tryGet(
            species,
            0,
            &metadata)) {
        return metadata.groupFlags;
    }
    return 0;
}

static void OverworldWildSpawns_BuildBehaviorContext(
    OverworldWildBehaviorContext *context,
    const OverworldWildSpawn *spawn,
    u16 species,
    u8 level,
    u8 terrain,
    u8 shiny)
{
    if (spawn != NULL && spawn->active) {
        species = spawn->species;
        level = spawn->level;
        terrain = spawn->terrain;
        shiny = spawn->shiny;
    }

    context->species = species;
    context->groupFlags = OverworldWildSpawns_GetBehaviorGroupFlags(species);
    context->level = level;
    context->terrain = terrain;
    context->shiny = shiny;
    context->behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    context->reserved = 0;
}

typedef char OverworldWildBehaviorTerrainMaskOffsetMustRemain32[
    offsetof(OverworldWildBehaviorProfileData, chillAllowedTerrainMask) == 32 ? 1 : -1];
typedef char OverworldWildBehaviorTerrainOverrideMaskOffsetMustRemain34[
    offsetof(OverworldWildBehaviorProfileData, chillAllowedTerrainOverrideMask) == 34 ? 1 : -1];
typedef char OverworldWildBehaviorHopTimeOffsetMustRemain36[
    offsetof(OverworldWildBehaviorProfileData, hopTime) == 36 ? 1 : -1];
typedef char OverworldWildBehaviorArcScaleOffsetMustRemain49[
    offsetof(OverworldWildBehaviorProfileData, hopElevationArcScale) == 49 ? 1 : -1];
typedef char OverworldWildBehaviorTilesToAccelerateOffsetMustRemain50[
    offsetof(OverworldWildBehaviorProfileData, tilesToAccelerate) == 50 ? 1 : -1];
typedef char OverworldWildBehaviorMaxWalkSpeedOffsetMustRemain51[
    offsetof(OverworldWildBehaviorProfileData, maxWalkSpeed) == 51 ? 1 : -1];
typedef char OverworldWildBehaviorSpawnDestinationMaskOffsetMustRemain52[
    offsetof(OverworldWildBehaviorProfileData, spawnDestinationMask) == 52 ? 1 : -1];
typedef char OverworldWildBehaviorSpawnDestinationOverrideMaskOffsetMustRemain54[
    offsetof(OverworldWildBehaviorProfileData, spawnDestinationOverrideMask) == 54 ? 1 : -1];
typedef char OverworldWildBehaviorVerticalObstacleOptionOffsetMustRemain56[
    offsetof(OverworldWildBehaviorProfileData, hopAllowVerticalObstacles) == 56 ? 1 : -1];

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_GetFallbackBehaviorResolution(
    BehaviorResolveResult *result,
    u8 behaviorLimitKey)
{
    result = memset(result, 0, sizeof(*result));
    /* The data overlay normally supplies every value. If it is unavailable,
     * fail closed with a stationary profile that is safe on land. */
    result->profile.chillState = 1; /* Idle. */
    result->profile.chillSpeed = OW_WILD_BEHAVIOR_WALK_TIME_DEFAULT;
    result->profile.playerAdjacentDirectionMasks =
        OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES;
    result->profile.chillAllowedTerrainMask =
        OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT;
    result->profile.tiredAllowedTerrainMask =
        OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT;
    result->profile.tiredPlayerAdjacentDirectionMasks =
        OW_WILD_BEHAVIOR_PLAYER_ADJACENT_ALL_STATES;
    result->behaviorClass = behaviorLimitKey;
    result->behaviorLimitKey = behaviorLimitKey;
    result->winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    result->targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    result->resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
}

static u8 OverworldWildSpawns_GetBehaviorClassForContext(const OverworldWildBehaviorContext *context)
{
    const OverworldWildBehaviorDataBlob *behaviorData;
    BehaviorResolveRequest request;
    BehaviorClassSelection selection;

    if (context == NULL) {
        return OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    }

    behaviorData = OverworldWildSpawns_GetBehaviorDataBlob();
    if (behaviorData == NULL) {
        return OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    }
    OverworldWildSpawns_InitBehaviorResolveRequest(&request);
    request.context = *context;
    request.behaviorClass = BEHAVIOR_RESOLVER_CLASS_AUTO;
    if (OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->inspectClass(
            behaviorData,
            sizeof(*behaviorData),
            &request,
            &selection,
            NULL) != BEHAVIOR_RESOLVE_OK) {
        return OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    }
    return selection.behaviorClass;
}

static const OverworldWildBehaviorDataBlob * __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ResolveBehaviorProfileForContext(
    const OverworldWildBehaviorContext *context,
    u32 forcedOverrideMask,
    const BehaviorResolveRequest *conditionalAdmission,
    BehaviorResolveResult *result)
{
    const OverworldWildBehaviorDataBlob *behaviorData;
    BehaviorResolveRequest request;
    u8 fallbackLimit;

    behaviorData = OverworldWildSpawns_GetBehaviorDataBlob();
    fallbackLimit = context->behaviorClass < OWBD_CLASS_PROFILE_COUNT
        ? context->behaviorClass
        : OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    if (behaviorData == NULL) {
        goto fallback;
    }

    if (conditionalAdmission != NULL) {
        /* Preserve the admitted conditionalAdmission->activeConditionalMask,
         * conditionalAdmission->resolvedTarget,
         * conditionalAdmission->winningConditionId,
         * conditionalAdmission->targetSourceApplication, and
         * conditionalAdmission->resolvedTargetConditionId as one value. */
        request = *conditionalAdmission;
    } else {
        OverworldWildSpawns_InitBehaviorResolveRequest(&request);
    }
    request.context = *context;
    request.behaviorClass = context->behaviorClass;
    request.forcedOverrideMask = forcedOverrideMask;
    if (OVERWORLD_ACTOR_SYSTEM_RESOLVER_ENTRY->resolve(
            behaviorData,
            sizeof(*behaviorData),
            &request,
            result,
            NULL) != BEHAVIOR_RESOLVE_OK) {
        goto fallback;
    }
    return behaviorData;

fallback:
    OverworldWildSpawns_GetFallbackBehaviorResolution(result, fallbackLimit);
    return behaviorData;
}

static OverworldWildBehaviorSlotCache *OverworldWildSpawns_EnsureBehaviorSlotCaches(
    OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildBehaviorSlotCache *cache;

    runtime = OverworldWildSpawns_EnsureRuntimeState(state);
    if (runtime == NULL) {
        return NULL;
    }

    cache = runtime->movementBehaviorSlotCaches;
    if (cache == NULL) {
        cache = sys_AllocMemory(
            HEAPID_WORLD,
            OW_WILD_MAX_SPAWNS * sizeof(*cache));
        runtime->movementBehaviorSlotCaches = cache;
        if (cache != NULL) {
            memset(
                cache,
                0,
                OW_WILD_MAX_SPAWNS * sizeof(*cache));
        }
    }

    return cache;
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ClearCachedBehaviorProfile(OverworldWildSpawnState *state, int slot)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildBehaviorSlotCache *cache;
    u16 slotMask;
    int i;

    runtime = OverworldWildSpawns_EnsureRuntimeState(state);
    if (runtime == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    slotMask = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    for (i = 0; i < 4; i++) {
        runtime->movementRoutingMasks[i] &= ~slotMask;
    }
    cache = runtime->movementBehaviorSlotCaches;
    if (cache != NULL) {
        cache[slot].valid = FALSE;
    }
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_UpdateMovementRoutingMasks(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    OverworldWildOverlayRuntimeState *runtime;
    u16 slotMask;
    u8 routingBits;
    int i;

    runtime = OW_WILD_RUNTIME(state);
    slotMask = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    routingBits = (profile->alertSpecialAction == OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW
            || primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
            || primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND
            || (primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
                && OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile->owner.walkOptions)))
        | (OverworldWildSpawns_IsFrameDrivenOwnerLocomotion(
            primitives->tiredLocomotion) << 1)
        | ((primitives->chillLocomotion
            == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) << 2)
        | ((primitives->tiredLocomotion
            == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) << 3);
    for (i = 0; i < 4; i++, routingBits >>= 1) {
        runtime->movementRoutingMasks[i] =
            (runtime->movementRoutingMasks[i] & ~slotMask)
            | ((routingBits & 1) ? slotMask : 0);
    }
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_StoreBehaviorSlotCache(
    OverworldWildBehaviorSlotCache *cache,
    const OverworldWildSpawn *spawn,
    u8 behaviorClass,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives);

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ApplyBehaviorResolution(
    OverworldWildSpawnState *state,
    int slot,
    const BehaviorResolveResult *resolution)
{
    OverworldWildBehaviorSlotCache *caches;

    caches = OverworldWildSpawns_EnsureBehaviorSlotCaches(state);
    if (caches != NULL) {
        OverworldWildSpawns_StoreBehaviorSlotCache(
            &caches[slot],
            &state->spawns[slot],
            resolution->behaviorClass,
            &resolution->profile,
            &resolution->primitives);
    }
    OverworldWildSpawns_UpdateMovementRoutingMasks(
        state,
        slot,
        &resolution->profile,
        &resolution->primitives);
    if (resolution->fingerprint != 0) {
        OverworldWildSpawns_BindActorPolicyProfile(
            slot,
            resolution->fingerprint,
            resolution->matchedClassRuleMask
                | resolution->appliedOverrideMask);
    }
}

static void OverworldWildSpawns_SeedPreparedBehaviorProfile(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildPreparedSpawn *prepared)
{
    /* The create path has already validated these values. */
    OverworldWildSpawns_ApplyBehaviorResolution(
        state, slot, &prepared->behaviorResolution);
}

static const OverworldBehaviorConditionAdapterEntry *
__attribute__((noinline, optimize("Os")))
OverworldWildSpawns_GetConditionAdapter(void)
{
    const OverworldActorMovementPolicyServiceEntry *service =
        OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY;
    const OverworldBehaviorConditionAdapterEntry *adapter;

    if (service->magic != OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_MAGIC
        || service->version != OVERWORLD_ACTOR_MOVEMENT_POLICY_SERVICE_VERSION
        || service->size != sizeof(*service)
        || service->conditionAdapter == NULL) {
        return NULL;
    }
    adapter = service->conditionAdapter;
    if (adapter->magic != OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_MAGIC
        || adapter->version != OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION
        || adapter->size != sizeof(*adapter)) {
        return NULL;
    }
    return adapter;
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ClearConditionActorRecord(
    OverworldWildBehaviorConditionRuntime *conditions,
    int slot)
{
    OverworldBehaviorConditionPreparedActor *prepared =
        &conditions->actors[slot];

    if (prepared->states != NULL) {
        sys_FreeMemoryEz(prepared->states);
    }
    /* This runtime owns the nested allocation even when the adapter overlay
     * is unavailable. Invalidate the record and the only mask consumed by
     * movement. The adapter clears the remaining private caches before a
     * later prepare can make this slot valid again. */
    prepared->states = NULL;
    prepared->valid = FALSE;
    conditions->activeApplicationMasks[slot] = 0;
}

static void OverworldWildSpawns_ClearConditionSlot(
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldWildBehaviorConditionRuntime *conditions =
        OverworldWildSpawns_GetConditionRuntime(state);

    if (conditions != NULL && (u32)slot < OW_WILD_MAX_SPAWNS) {
        OverworldWildSpawns_ClearConditionActorRecord(
            conditions, slot);
    }
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ClearAllConditionState(
    OverworldWildBehaviorConditionRuntime *conditions)
{
    int slot;

    if (conditions == NULL) {
        return;
    }
    for (slot = OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS - 1; slot >= 0; slot--) {
        OverworldWildSpawns_ClearConditionActorRecord(conditions, slot);
    }
}

static BOOL OverworldWildSpawns_PrepareConditionsForSlot(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldActorHandle *handle,
    const OverworldWildBehaviorProfile *stableProfile)
{
    const OverworldBehaviorConditionAdapterEntry *adapter;
    const OverworldWildBehaviorDataBlob *behaviorData;
    OverworldWildBehaviorConditionRuntime *conditions;

    adapter = OverworldWildSpawns_GetConditionAdapter();
    behaviorData = OverworldWildSpawns_GetBehaviorDataBlob();
    conditions = OverworldWildSpawns_EnsureConditionRuntime(state);
    if (adapter == NULL || behaviorData == NULL || conditions == NULL) {
        return FALSE;
    }
    if (stableProfile == NULL) {
        return FALSE;
    }
    return adapter->prepareActor(
            conditions,
            state,
            behaviorData,
            sizeof(*behaviorData),
            handle,
            stableProfile,
            (u8)slot,
            OverworldWildSpawns_BuildBehaviorContext)
        == OVERWORLD_BEHAVIOR_CONDITION_OK;
}

#define OW_WILD_CONDITION_RESULT_TRIGGERED    (1u << 0)
#define OW_WILD_CONDITION_RESULT_TIMED_ENDED  (1u << 1)
#define OW_WILD_CONDITION_RESULT_FAIL_CLOSED  (1u << 2)

static u8 OverworldWildSpawns_FailClosedConditionResolution(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldBehaviorConditionAdapterEntry *adapter,
    OverworldWildBehaviorConditionRuntime *conditions)
{
    if (adapter != NULL && conditions != NULL) {
        adapter->clearResolution(conditions, (u8)slot);
    } else if (conditions != NULL) {
        conditions->activeApplicationMasks[slot] = 0;
        conditions->timedWinningApplicationMasks[slot] = 0;
        conditions->targetValidMask &= (u16)~(1u << slot);
        conditions->frame.valid = FALSE;
    }
    OverworldWildSpawns_ClearCachedBehaviorProfile(state, slot);
    return OW_WILD_CONDITION_RESULT_FAIL_CLOSED;
}

static u16 OverworldWildSpawns_GetConditionTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    return OverworldWildSpawns_GetTerrainBit(fieldSystem, x, y, TRUE);
}

static u16 __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_EvaluateConditionsForSlot(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    OverworldWildBehaviorProfile *profileOut,
    OverworldWildBehaviorPrimitives *primitivesOut)
{
    const OverworldBehaviorConditionAdapterEntry *adapter;
    const OverworldWildBehaviorDataBlob *behaviorData;
    OverworldWildBehaviorConditionRuntime *conditions;
    OverworldBehaviorConditionAdapterOutcome outcome;
    u8 direction;

    if (slot == OW_WILD_FOLLOWER_SLOT
        && OverworldWildSpawns_MountIsActive()) {
        return 0;
    }
    adapter = OverworldWildSpawns_GetConditionAdapter();
    behaviorData = OverworldWildSpawns_GetBehaviorDataBlob();
    conditions = OverworldWildSpawns_GetConditionRuntime(state);
    if (adapter == NULL || behaviorData == NULL || conditions == NULL
        || adapter->evaluateActor(
            conditions,
            state,
            fieldSystem,
            behaviorData,
            sizeof(*behaviorData),
            (u8)slot,
            profileOut->owner.chillSpeed,
            slot == OW_WILD_FOLLOWER_SLOT
                ? OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER
                : -1,
            OverworldWildSpawns_BuildBehaviorContext,
            OverworldWildSpawns_IsCurrentSpawnObject,
            OverworldWildSpawns_GetConditionTerrainBit,
            OVERWORLD_CONDITION_VISIBILITY_POPULATE_ENTRY,
            &outcome) != OVERWORLD_BEHAVIOR_CONDITION_OK) {
        return OverworldWildSpawns_FailClosedConditionResolution(
            state, slot, adapter, conditions);
    }
    if ((outcome.flags
            & OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED) != 0) {
        *profileOut = conditions->resolution.profile;
        *primitivesOut = conditions->resolution.primitives;
        OverworldWildSpawns_ApplyBehaviorResolution(
            state, slot, &conditions->resolution);
    }
    direction = conditions->frame.world.subjectFacing;
    if ((outcome.flags & OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED) != 0
        && (outcome.targetDx != 0 || outcome.targetDy != 0)) {
        direction = OverworldWalk_DirectionFromDelta(
            outcome.targetDx, outcome.targetDy);
    }
    return (outcome.flags
            & (OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED
                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED))
        | ((u16)direction << 8);
}
static BOOL OverworldWildSpawns_BehaviorSlotCacheMatches(
    const OverworldWildBehaviorSlotCache *cache,
    const OverworldWildSpawn *spawn,
    u8 behaviorClass)
{
    return cache->valid
        && cache->species == spawn->species
        && cache->mapId == spawn->mapId
        && cache->form == spawn->form
        && cache->level == spawn->level
        && cache->terrain == spawn->terrain
        && cache->shiny == spawn->shiny
        && cache->behaviorClass == behaviorClass;
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_StoreBehaviorSlotCache(
    OverworldWildBehaviorSlotCache *cache,
    const OverworldWildSpawn *spawn,
    u8 behaviorClass,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    cache->profile = *profile;
    cache->primitives = *primitives;
    cache->species = spawn->species;
    cache->mapId = spawn->mapId;
    cache->form = spawn->form;
    cache->level = spawn->level;
    cache->terrain = spawn->terrain;
    cache->shiny = spawn->shiny;
    cache->behaviorClass = behaviorClass;
    cache->valid = TRUE;
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profileOut,
    OverworldWildBehaviorPrimitives *primitivesOut)
{
    OverworldWildBehaviorContext context;
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    OverworldWildBehaviorSlotCache *cache;
    OverworldWildSpawn *spawn;
    BehaviorResolveResult resolution;
    u8 behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;

    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        OverworldWildSpawns_GetFallbackBehaviorResolution(
            &resolution,
            OW_WILD_BEHAVIOR_CLASS_DEFAULT);
        profile = resolution.profile;
        primitives = resolution.primitives;
        if (profileOut != NULL) {
            *profileOut = profile;
        }
        if (primitivesOut != NULL) {
            *primitivesOut = primitives;
        }
        return;
    }

    spawn = &state->spawns[slot];
    cache = OverworldWildSpawns_EnsureBehaviorSlotCaches(state);
    if (cache != NULL) {
        cache = &cache[slot];
    }
    if (spawn->active) {
        behaviorClass = state->movementBehaviorClasses[slot];
    }
#if OW_WILD_SPAWNER_PROFILE_CACHE_FAST_HIT
    if (spawn->active
        && cache != NULL
        && OverworldWildSpawns_BehaviorSlotCacheMatches(
            cache,
            spawn,
            behaviorClass)) {
        OW_WILD_PERF_INC(sOverworldWildPerfProfileCacheHitsThisFrame);
        profile = cache->profile;
        primitives = cache->primitives;
        goto copy_outputs;
    }
#endif
    OverworldWildSpawns_BuildBehaviorContext(
        &context,
        spawn,
        SPECIES_NONE,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    if (!spawn->active) {
        behaviorClass = OverworldWildSpawns_GetBehaviorClassForContext(&context);
    }
    context.behaviorClass = behaviorClass;
    context.reserved = 0;
#if !OW_WILD_SPAWNER_PROFILE_CACHE_FAST_HIT
    if (spawn->active
        && cache != NULL
        && OverworldWildSpawns_BehaviorSlotCacheMatches(
            cache,
            spawn,
            behaviorClass)) {
        OW_WILD_PERF_INC(sOverworldWildPerfProfileCacheHitsThisFrame);
        profile = cache->profile;
        primitives = cache->primitives;
    } else {
#else
    {
#endif
        OW_WILD_PERF_INC(sOverworldWildPerfProfileResolvesThisFrame);
        memset(&resolution, 0, sizeof(resolution));
        OverworldWildSpawns_ResolveBehaviorProfileForContext(
            &context,
            slot == OW_WILD_FOLLOWER_SLOT
                ? 1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER
                : 0,
            NULL,
            &resolution);
        profile = resolution.profile;
        if (resolution.fingerprint != 0) {
            OverworldWildSpawns_BindActorPolicyProfile(
                slot,
                resolution.fingerprint,
                resolution.matchedClassRuleMask
                    | resolution.appliedOverrideMask);
        }
        primitives = resolution.primitives;
        if (spawn->active) {
            OverworldWildSpawns_UpdateMovementRoutingMasks(
                state,
                slot,
                &profile,
                &primitives);
            /* Do not cache a Follower profile while Mounted owns slot 7.
             * Its old map-keyed cache then misses after dismount, so normal
             * Follower policy binds on the destination map. */
            if (cache != NULL
                && (slot != OW_WILD_FOLLOWER_SLOT
                    || !OverworldWildSpawns_MountIsActive())) {
                OverworldWildSpawns_StoreBehaviorSlotCache(
                    cache,
                    spawn,
                    behaviorClass,
                    &profile,
                    &primitives);
            }
        }
    }

#if OW_WILD_SPAWNER_PROFILE_CACHE_FAST_HIT
copy_outputs:
#endif
    if (profileOut != NULL) {
        *profileOut = profile;
    }
    if (primitivesOut != NULL) {
        *primitivesOut = primitives;
    }
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_BeginMountSelectedFollower(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    const OverworldWildBehaviorDataBlob *behaviorData;
    const BehaviorResolveRequest *conditionalAdmission = NULL;
    OverworldWildBehaviorConditionRuntime *conditions;
    union {
        OverworldWildBehaviorContext context;
        OverworldActorPolicyProfileTransaction policyTransaction;
    } role;
    BehaviorResolveResult resolution;
    OverworldMountBinding binding;

    /* The private mount tick passes its live Field and Wild owners. */
    if (fieldSystem->taskman != NULL
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(
            state,
            fieldSystem)
        || !OverworldWildSpawns_TryBuildFollowerMountBinding(
            fieldSystem,
            state,
            &binding)) {
        return FALSE;
    }

    OverworldWildSpawns_BuildBehaviorContext(
        &role.context,
        &state->spawns[OW_WILD_FOLLOWER_SLOT],
        SPECIES_NONE,
        0,
        OW_WILD_SPAWN_TERRAIN_LAND,
        FALSE);
    role.context.behaviorClass = binding.behaviorClass;
    conditions = OverworldWildSpawns_GetConditionRuntime(state);
    /* The resident helper checks conditions->request.activeConditionalMask,
     * conditions->request.forcedOverrideMask, and
     * &conditions->request.context before returning the equivalent of
     * conditionalAdmission = &conditions->request. */
    conditionalAdmission = OVERWORLD_MOUNT_CONDITIONAL_ADMISSION(
        conditions,
        &role.context);
    if (conditionalAdmission
            == OVERWORLD_MOUNT_CONDITIONAL_ADMISSION_INVALID) {
        return FALSE;
    }
    behaviorData = OverworldWildSpawns_ResolveBehaviorProfileForContext(
        &role.context,
        1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_MOUNTED,
        conditionalAdmission,
        &resolution);
    /* The resolver fallback guarantees the equivalent of
     * behaviorData == NULL || resolution.fingerprint == 0. */
    if (resolution.fingerprint == 0) {
        return FALSE;
    }
    role.policyTransaction.next.behaviorFingerprint = resolution.fingerprint;
    role.policyTransaction.next.matchedLayerMask = resolution.matchedClassRuleMask
        | resolution.appliedOverrideMask;
    if (!OVERWORLD_MOUNT_OVERLAY_ENTRY->begin(
            fieldSystem,
            &binding,
            &resolution.profile,
            (const OverworldWildSurfaceCatalog *)behaviorData->surfaceModels,
            &role.policyTransaction)) {
        return FALSE;
    }
    /* Begin has accepted and bound Mounted. The current follower now
     * becomes presentation-only, so no failed mount can disturb
     * Follower movement. */
    OverworldWildSpawns_ResetSlotMovementCommand(
        state,
        OW_WILD_FOLLOWER_SLOT,
        TRUE);
    return TRUE;
}

static u8 OverworldWildSpawns_GetBehaviorHopSpinSpeed(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    return OverworldWildSpawns_GetControllerLane(
        profile,
        spotState)->hopSpinSpeed;
}

static BOOL OverworldWildSpawns_SlotUsesConditionalTeleportMovement(
    OverworldWildSpawnState *state,
    int slot)
{
    return state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->spawns[slot].active
        && OverworldWildSpawns_GetActiveConditionApplications(state, slot) != 0
        && (OW_WILD_RUNTIME(state)->movementOwnerTeleportMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
}

static BOOL OverworldWildSpawns_SlotUsesTeleportMovement(
    OverworldWildSpawnState *state,
    int slot)
{
    return state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->spawns[slot].active
        && ((OW_WILD_RUNTIME(state)->movementOwnerTeleportMask
                | OW_WILD_RUNTIME(state)->movementTiredTeleportMask)
            & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
}

static void __attribute__((noinline)) OverworldWildSpawns_SetObjectPassThrough(LocalMapObject *object, BOOL passThrough)
{
    if (object == NULL) {
        return;
    }

    if (passThrough) {
        object->flags |= MAPOBJECTFLAG_UNK18;
    } else {
        object->flags &= ~MAPOBJECTFLAG_UNK18;
    }
}

static void OverworldWildSpawns_ApplySpawnPassThroughFlag(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    BOOL passThrough = slot == OW_WILD_FOLLOWER_SLOT
        || (state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && OverworldWildSpawns_SlotUsesTeleportMovement(state, slot)
        && (OverworldWildSpawns_IsTeleportMovementActive(state, slot)
            || state->movementTeleportFlickerTimers[slot] != 0
            || OverworldWildSpawns_IsObjectOnPlayerTile(state->movementFieldSystem, object)));

    OverworldWildSpawns_SetObjectPassThrough(object, passThrough);
}

static void OverworldWildSpawns_ReleaseHeldActorControl(
    OverworldWildSpawnState *state,
    int slot)
{
    if (state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->movementActorControlModes[slot]
            == OW_WILD_ACTOR_CONTROL_HELD) {
        const OverworldWildHelperOverlayEntry *helperEntry;

        state->movementActorControlModes[slot] =
            OW_WILD_ACTOR_CONTROL_AUTONOMOUS;
        OverworldWildSpawns_ClearWalkMovementState(
            state,
            slot,
            state->spawns[slot].object);
        helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
        if (helperEntry != NULL) {
            (void)OverworldWildSpawns_ApplyPresentationCommand(
                state->movementFieldSystem,
                state,
                OW_WILD_HELPER_PRESENTATION_NORMALIZE_SLOT,
                (u8)slot);
            OverworldWildSpawns_ReconcileNativeShadow(
                state->movementFieldSystem,
                state->spawns[slot].object);
        }
    }
}

static void OverworldWildSpawns_ClearThrowStateForSlot(OverworldWildSpawnState *state, int slot)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildOverlayRuntimeState *runtime;
    u16 restoreMask;
    int i;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL || helperEntry->clearPickupThrowState == NULL) {
        return;
    }
    restoreMask = helperEntry->clearPickupThrowState(
        state,
        &runtime->throwState,
        &runtime->spawnPresentations,
        slot);
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if ((restoreMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0) {
            OverworldWildSpawns_ReleaseHeldActorControl(state, i);
        }
    }
}

static u16 __attribute__((noinline)) OverworldWildSpawns_GetThrowParticipantMask(OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    return runtime->throwState.targetMask
        | runtime->throwState.carrierMask
        | state->captureTargetMask;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_QueryPickupThrowTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot,
    u8 query,
    u16 unavailableMask)
{
    const OverworldWildHelperOverlayEntry *helperEntry =
        OverworldWildSpawns_GetHelperOverlayEntry();

    return helperEntry != NULL
        && helperEntry->queryPickupThrowTarget(
            state,
            &OW_WILD_RUNTIME(state)->throwState,
            carrierSlot,
            targetSlot,
            query,
            unavailableMask);
}

static inline BOOL __attribute__((always_inline))
OverworldWildSpawns_IsValidPickupThrowTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot)
{
    if (state == NULL
        || state->movementRuntimeState == NULL
        || carrierSlot == OW_WILD_FOLLOWER_SLOT
        || targetSlot == OW_WILD_FOLLOWER_SLOT) {
        return FALSE;
    }
    return OverworldWildSpawns_QueryPickupThrowTarget(
            state,
            carrierSlot,
            targetSlot,
            OW_WILD_HELPER_PICKUP_THROW_QUERY_VALID,
            0);
}

static u16 OverworldWildSpawns_GetPickupThrowUnstableMask(
    OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    u16 unstableMask = 0;
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (runtime->movementEmotePartnerPrepObjects[i] != NULL
            || runtime->movementCustomJumpActive[i]
            || runtime->movementCustomJumpPrepActive[i]
            || runtime->movementCustomMotionModes[i]
                >= OW_WILD_CUSTOM_MOTION_TELEPORT_FLICKER
            || state->movementCrashShakeTimers[i] != 0) {
            unstableMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i);
        }
    }
    return unstableMask;
}

static inline BOOL __attribute__((always_inline))
OverworldWildSpawns_IsStablePickupThrowTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot)
{
    if (state == NULL || state->movementRuntimeState == NULL) {
        return FALSE;
    }
    return OverworldWildSpawns_QueryPickupThrowTarget(
            state,
            carrierSlot,
            targetSlot,
            OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE,
            OverworldWildSpawns_GetPickupThrowUnstableMask(state));
}

static BOOL OverworldWildSpawns_IsReservedPickupTargetNearCarrier(
    OverworldWildSpawnState *state,
    int targetSlot)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL
        || state->movementRuntimeState == NULL
        || targetSlot < 0
        || targetSlot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    runtime = OW_WILD_RUNTIME(state);
    if ((runtime->throwState.targetMask
            & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(targetSlot)) == 0
        || state->movementActorControlModes[targetSlot]
            == OW_WILD_ACTOR_CONTROL_HELD) {
        return FALSE;
    }
    return OverworldWildSpawns_QueryPickupThrowTarget(
            state,
            0,
            targetSlot,
            OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_NEAR,
            0);
}

static void OverworldWildSpawns_SyncCarriedThrowTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot)
{
    const OverworldWildHelperOverlayEntry *helperEntry;

    if (state == NULL
        || state->movementFieldSystem == NULL) {
        return;
    }

    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry != NULL) {
        helperEntry->syncCarriedThrowTarget(
            state->movementFieldSystem,
            state,
            &OW_WILD_RUNTIME(state)->spawnPresentations,
            carrierSlot,
            targetSlot);
    }
}

static void OverworldWildSpawns_TryStartPickupThrowAction(
    OverworldWildSpawnState *state,
    int slot)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL
        || state->movementRuntimeState == NULL
        || slot == OW_WILD_FOLLOWER_SLOT) {
        return;
    }
    runtime = OW_WILD_RUNTIME(state);
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry != NULL && helperEntry->tryStartPickupThrowAction != NULL) {
        (void)helperEntry->tryStartPickupThrowAction(
            state,
            &runtime->throwState,
            &runtime->spawnPresentations,
            slot,
            OverworldWildSpawns_GetPickupThrowUnstableMask(state));
    }
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_IsFrameDrivenOwnerLocomotion(u8 locomotion)
{
    return locomotion <= OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND
        && ((OW_WILD_BEHAVIOR_FRAME_DRIVEN_LOCOMOTION_MASK >> locomotion) & 1u) != 0;
}

static u8 OverworldWildSpawns_GetAlertStateFrameCount(
    const OverworldWildBehaviorProfile *profile,
    u8 jumpCount)
{
    if (profile != NULL && profile->alertTime != OW_WILD_SPAWNER_ALERT_TIME_AUTO) {
        return profile->alertTime;
    }
    if (jumpCount != 0) {
        return OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP * jumpCount;
    }

    return OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES;
}

static u32 OverworldWildSpawns_GetMovementWalkCommandForSpeed(u8 speed)
{
    if (speed <= 2) {
        return OW_WILD_SPAWNER_MOVEMENT_SPEED_4_COMMAND;
    }
    if (speed <= 4) {
        return OW_WILD_SPAWNER_MOVEMENT_SPEED_3_COMMAND;
    }
    return speed <= 8
        ? OW_WILD_SPAWNER_MOVEMENT_SPEED_2_COMMAND
        : OW_WILD_SPAWNER_MOVEMENT_SPEED_1_COMMAND;
}


static void OverworldWildSpawns_ClearMovementSlotInProgress(OverworldWildSpawnState *state, int slot)
{
    state->movementInProgressMask &= ~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
    state->movementTeleportVisiblePause[slot] = FALSE;
}

static BOOL OverworldWildSpawns_StartCarriedThrowTarget(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot,
    LocalMapObject *object)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildOverlayRuntimeState *runtime;

    (void)object;
    if (state == NULL || state->movementRuntimeState == NULL) {
        return FALSE;
    }
    runtime = OW_WILD_RUNTIME(state);
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry != NULL
        && helperEntry->startCarriedThrowTarget != NULL
        && helperEntry->startCarriedThrowTarget(
            state,
            &runtime->throwState,
            &runtime->spawnPresentations,
            carrierSlot,
            targetSlot)) {
        OverworldWildSpawns_ClearWalkMovementState(
            state,
            targetSlot,
            state->spawns[targetSlot].object);
        return TRUE;
    }
    return FALSE;
}

static s32 OverworldWildSpawns_GetMovementCrashShakeOffset(u8 timer)
{
    s32 amplitude = OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FX32_AMPLITUDE
        >> ((timer & 2) >> 1);

    return (timer & 1) ? -amplitude : amplitude;
}

static void OverworldWildSpawns_RestoreMovementCrashShake(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->movementCrashShakeTimers[slot] == 0) {
        return;
    }

    if (state->spawns[slot].active && state->spawns[slot].object != NULL) {
        state->spawns[slot].object->posVec[0] = state->movementCrashShakeBaseX[slot];
        state->spawns[slot].object->posVec[2] = state->movementCrashShakeBaseZ[slot];
    }

    state->movementCrashShakeTimers[slot] = 0;
}

static void OverworldWildSpawns_ClearCustomJumpPresentationState(OverworldWildSpawnState *state, int slot)
{
    FieldSystem *fieldSystem;
    LocalMapObject *object;

    fieldSystem = state->movementFieldSystem;
    object = state->spawns[slot].object;
    if (object != NULL
        && OverworldWildSpawns_IsPresentationFieldContextCurrent(state, fieldSystem)
        && OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        OverworldWildSpawns_ClearObjectFlags(
            object,
            OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS
                | (OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[slot]
                    ? MAPOBJECTFLAG_UNK8
                    : 0));
    }
}

static void OverworldWildSpawns_ClearCustomJumpLocal(
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    OverworldWildSpawns_ClearCustomJumpPresentationState(state, slot);
    runtime->movementCustomJumpActive[slot] = FALSE;
    runtime->movementCustomMotionModes[slot] = OW_WILD_CUSTOM_MOTION_NONE;
#if OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_ENABLED
    sOverworldWildCustomJumpRenderSettleActive[slot] = FALSE;
    sOverworldWildCustomJumpRenderSettleStartX[slot] = 0;
    sOverworldWildCustomJumpRenderSettleStartY[slot] = 0;
    sOverworldWildCustomJumpRenderSettleElapsedFrames[slot] = 0;
#endif
#if OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS
    sOverworldWildCustomJumpVisibleLegFinished[slot] = FALSE;
#endif
}

static void OverworldWildSpawns_ClearCustomJump(
    OverworldWildSpawnState *state,
    int slot)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }
    OverworldWildSpawns_CancelSharedMotion(
        slot,
        OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
    OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
}

static void OverworldWildSpawns_ClearStagedHopTargetLocal(
    OverworldWildSpawnState *state,
    int slot)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
    OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
    OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[slot] = FALSE;
    state->movementStagedHopOriginX[slot] = 0;
    state->movementStagedHopOriginY[slot] = 0;
    state->movementStagedHopTargetX[slot] = 0;
    state->movementStagedHopTargetY[slot] = 0;
    state->movementStagedHopAvoidX[slot] = 0;
    state->movementStagedHopAvoidY[slot] = 0;
    state->movementStagedHopDistances[slot] = 0;
    state->movementStagedHopFinishWithTired[slot] = FALSE;
    state->movementStagedHopPending[slot] = FALSE;
    state->movementStagedHopAvoidValid[slot] = FALSE;
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopLandingExpected[slot] = FALSE;
}

static void OverworldWildSpawns_ClearStagedHopTarget(
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldWildSpawns_CancelSharedMotion(
        slot,
        OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
    OverworldWildSpawns_ClearStagedHopTargetLocal(state, slot);
}

#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE
static OverworldWildStagedHopMovementList *OverworldWildSpawns_AllocStagedHopMovementList(
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldWildStagedHopMovementList *movementList;

    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return NULL;
    }

    movementList = OW_WILD_RUNTIME(state)->movementStagedHopMovementLists[slot];
    if (movementList == NULL) {
        movementList = sys_AllocMemory(
            HEAPID_WORLD,
            sizeof(*movementList));
        if (movementList == NULL) {
            return NULL;
        }
        OW_WILD_RUNTIME(state)->movementStagedHopMovementLists[slot] =
            movementList;
    }

    memset(
        movementList,
        0,
        sizeof(*movementList));
    movementList->commands[0] = OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_END_COMMAND;
    return movementList;
}
#endif

static void __attribute__((optimize("Os"))) OverworldWildSpawns_ClearStagedHopMovementListTask(OverworldWildSpawnState *state, int slot)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildStagedHopMovementList *movementList;
    SysTask *task;

    if (state == NULL
        || state->movementRuntimeState == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    movementList = runtime->movementStagedHopMovementLists[slot];
    if (movementList == NULL) {
        return;
    }
    task = movementList->task;
    runtime->movementStagedHopMovementLists[slot] = NULL;
    if (task != NULL) {
        MapObject_CleanupMovementListTask(task);
    }
    sys_FreeMemoryEz(movementList);
}

static void OverworldWildSpawns_SetObjectFacing(LocalMapObject *object, u8 direction)
{
    if (object == NULL || direction > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
        return;
    }

    object->facingInit = direction;
    object->curFacing = direction;
    object->nextFacing = direction;
    object->curFacingBak = direction;
    object->nextFacingBak = direction;
}

static void OverworldWildSpawns_SetObjectTile(LocalMapObject *object, int x, int y)
{
    if (object == NULL) {
        return;
    }

    object->xCurr = x;
    object->yCurr = y;
    object->xInit = x;
    object->yInit = y;
    object->xPrev = x;
    object->yPrev = y;
    object->posVec[0] = (u32)OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(x);
    object->posVec[2] = (u32)OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(y);
}

static void __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_SetObjectLogicalTileOnly(
    LocalMapObject *object,
    int x,
    int y)
{
    if (object == NULL) {
        return;
    }

    object->xCurr = x;
    object->yCurr = y;
    object->xInit = x;
    object->yInit = y;
    object->xPrev = x;
    object->yPrev = y;
}

#if OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_ENABLED
static void OverworldWildSpawns_SetObjectRenderTileOnly(LocalMapObject *object, int x, int y)
{
    if (object == NULL) {
        return;
    }

    object->posVec[0] = (u32)OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(x);
    object->posVec[2] = (u32)OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(y);
}
#endif

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ResolveObjectLandingHeight(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int x,
    int y)
{
    OverworldWildSpawns_SetObjectTile(object, x, y);
    (void)MapObject_RefreshHeightFromTerrain(object);
    (void)OverworldWildSpawns_ApplySurfaceHeight(fieldSystem, object, x, y);
}

static void OverworldWildSpawns_SetObjectLandingTile(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int x,
    int y)
{
    if (object == NULL) {
        return;
    }

    OverworldWildSpawns_ResolveObjectLandingHeight(fieldSystem, object, x, y);
    object->faceVec[0] = 0;
    object->faceVec[1] = 0;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = 0;
    object->unk94[1] = 0;
    OverworldWildSpawns_ClearObjectFlags(
        object,
        BIT_VANISH | OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS);
    OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);
}

static inline void __attribute__((always_inline))
OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile(
    OverworldWildSpawnState *state,
    int carrierSlot,
    int targetSlot,
    LocalMapObject *targetObject)
{
    if (state == NULL
        || targetSlot < 0
        || targetSlot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    OverworldWildSpawns_ClearThrowStateForSlot(state, carrierSlot);
    OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[targetSlot] = FALSE;
    OverworldWildSpawns_ClearCustomJump(state, targetSlot);
    if (targetObject != NULL) {
        OverworldWildSpawns_SetObjectLandingTile(
            state->movementFieldSystem,
            targetObject,
            OverworldWildSpawns_ObjectCurrentX(targetObject),
            OverworldWildSpawns_ObjectCurrentY(targetObject));
        OverworldWildSpawns_ClearObjectFlags(targetObject, BIT_VANISH | MAPOBJECTFLAG_UNK18);
    }
}

static s32 OverworldWildSpawns_GetObjectGroundBaseYAt(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int x,
    int y)
{
    const OverworldWildBehaviorDataBlob *blob =
        OverworldWildSpawns_GetBehaviorDataBlob();

    return OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
        fieldSystem,
        blob != NULL
            ? (const OverworldWildSurfaceCatalog *)blob->surfaceModels
            : NULL,
        object,
        x,
        y);
}

static BOOL OverworldWildSpawns_IsCanopyHopperTreeTopSlot(OverworldWildSpawnState *state, int slot)
{
    OverworldWildBehaviorProfile profile;
    const OverworldWildBehaviorProfileData *lane;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active) {
        return FALSE;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state,
        slot,
        &profile,
        NULL);
    lane = OverworldWildSpawns_GetControllerLane(
        &profile,
        state->movementSpotStates[slot]);
    return (lane->chillAllowedTerrainMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY) != 0;
}

#if 0
static BOOL OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    int x,
    int y,
    BOOL finalLanding)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    (void)x;
    (void)y;
    (void)finalLanding;

    if (!OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)) {
        return TRUE;
    }
    return FALSE;
}
#endif

static void OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    LocalMapObject *object;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || !OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)) {
        return;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        return;
    }

    if (fieldSystem != NULL && !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)) {
        return;
    }

    OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride(slot, object);
    OverworldWildSpawns_ClearMankeyTreeTopProxyObject(state, slot, TRUE);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
}

static void OverworldWildSpawns_RefreshCanopyHopperVisualStateAtLanding(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
    BOOL treeTopLanding;
    int objectX;
    int objectY;

    if (state == NULL
        || fieldSystem == NULL
        || object == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active) {
        return;
    }

    OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
    objectX = object->xCurr;
    objectY = object->yCurr;
    treeTopLanding = OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)
        && OverworldWildSpawns_IsHeadbuttTreeTopLocation(fieldSystem, objectX, objectY);
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettled[slot] = treeTopLanding;
    if (treeTopLanding) {
        OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettledX[slot] = (s16)objectX;
        OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettledY[slot] = (s16)objectY;
    } else {
        OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettledX[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
        OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettledY[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    }
    OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(state, fieldSystem, slot, object);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
}

static void OverworldWildSpawns_RevealTeleportObject(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{
    FieldSystem *fieldSystem;
    BOOL hadTeleportPresentation;
    BOOL objectIsCurrent;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    if (object == NULL && state->spawns[slot].active) {
        object = state->spawns[slot].object;
    }
    hadTeleportPresentation = state->movementTeleportHidden[slot]
        || state->movementTeleportFlickerTimers[slot] != 0
        || state->movementTeleportFlickerObjects[slot] != NULL
        || (state->movementRuntimeState != NULL
            && OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
                >= OW_WILD_CUSTOM_MOTION_TELEPORT_FLICKER);
    fieldSystem = state->movementFieldSystem;
    objectIsCurrent = object != NULL
        && object == state->spawns[slot].object
        && OverworldWildSpawns_IsPresentationFieldContextCurrent(state, fieldSystem)
        && OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot]);
    OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
    state->movementTeleportHidden[slot] = FALSE;
    state->movementTeleportHiddenSteps[slot] = 0;
    state->movementTeleportFlickerTimers[slot] = 0;
    state->movementTeleportVisiblePause[slot] = FALSE;
    if (hadTeleportPresentation && objectIsCurrent) {
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
        OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);
    }
}

static BOOL OverworldWildSpawns_ShouldShowTeleportFlickerWithDurations(
    u8 timer,
    u8 visibleFrames,
    u8 hiddenFrames)
{
    u8 cycleFrames;
    u8 phaseFrame;

    if (timer == 0 || visibleFrames == 0) {
        return FALSE;
    }
    if (hiddenFrames == 0) {
        return TRUE;
    }

    cycleFrames = visibleFrames + hiddenFrames;
    phaseFrame = (timer - 1) % cycleFrames;
    return phaseFrame < visibleFrames;
}

#if OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_REAL_FLICKER
static BOOL OverworldWildSpawns_ShouldShowConditionalTeleportRealFlicker(u8 timer)
{
    u8 elapsedFrames;

    if (timer == 0 || timer > OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES) {
        return TRUE;
    }

    elapsedFrames = OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES - timer;
    return elapsedFrames < OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_VISIBLE_FRAMES;
}
#endif

static BOOL OverworldWildSpawns_IsConditionalTeleportLocomotion(OverworldWildSpawnState *state, int slot)
{
    return state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_CHILL
        && OverworldWildSpawns_GetActiveConditionApplications(state, slot) != 0
        && OverworldWildSpawns_SlotUsesConditionalTeleportMovement(state, slot);
}

static BOOL OverworldWildSpawns_IsTeleportMovementActive(OverworldWildSpawnState *state, int slot)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state == NULL
        || state->movementRuntimeState == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    runtime = OW_WILD_RUNTIME(state);
    return state != NULL
        && runtime->movementCustomMotionModes[slot]
            >= OW_WILD_CUSTOM_MOTION_TELEPORT_FLICKER
        && state->movementTeleportHidden[slot]
        && OverworldWildSpawns_IsMovementSlotInProgress(state, slot);
}

static BOOL OverworldWildSpawns_HasConditionalTeleportPresentation(
    OverworldWildSpawnState *state,
    int slot)
{
    return state != NULL
        && state->movementRuntimeState != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && (OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
                >= OW_WILD_CUSTOM_MOTION_TELEPORT_FLICKER
            || state->movementTeleportHidden[slot]
            || state->movementTeleportFlickerTimers[slot] != 0
            || state->movementTeleportFlickerObjects[slot] != NULL);
}

static BOOL OverworldWildSpawns_ShouldShowTeleportFlickerForSlot(
    OverworldWildSpawnState *state,
    int slot)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }

    if (OverworldWildSpawns_IsConditionalTeleportLocomotion(state, slot)) {
        return OverworldWildSpawns_ShouldShowTeleportFlickerWithDurations(
            state->movementTeleportFlickerTimers[slot],
            OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_VISIBLE_FRAMES,
            OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_HIDDEN_FRAMES);
    }

    return OverworldWildSpawns_ShouldShowTeleportFlickerWithDurations(
        state->movementTeleportFlickerTimers[slot],
        OW_WILD_SPAWNER_TELEPORT_FLICKER_VISIBLE_FRAMES,
        OW_WILD_SPAWNER_TELEPORT_FLICKER_HIDDEN_FRAMES);
}

static BOOL OverworldWildSpawns_SpawnSlotAllowsVanish(OverworldWildSpawnState *state, int slot)
{
    /* The mount owns follower presentation flags for its full session, with
     * the player as its engine anchor. Wild cleanup must leave that slot. */
    return (slot == OW_WILD_FOLLOWER_SLOT
            && OverworldWildSpawns_MountIsActive())
        || OverworldWildSpawns_IsTeleportMovementActive(state, slot)
        || state->movementTeleportHidden[slot]
        || state->movementTeleportFlickerTimers[slot] != 0
        || (state->captureTargetMask
            & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
}

static void OverworldWildSpawns_RevealUnownedVanishedObjects(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int i;

    if (state == NULL || fieldSystem == NULL) {
        return;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *object = state->spawns[i].object;

        if (state->spawns[i].active
            && OverworldWildSpawns_IsCurrentSpawnObject(
                fieldSystem,
                &state->spawns[i])
            && (object->flags & BIT_VANISH) != 0
            && !OverworldWildSpawns_SpawnSlotAllowsVanish(state, i)) {
            OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        }
    }
}

#define OW_WILD_NATIVE_SHADOW_SUPPRESSED_SURFACE_TYPES \
    ((1u << OW_WILD_SURFACE_TYPE_SIGNPOST) \
        | (1u << OW_WILD_SURFACE_TYPE_MAILBOX) \
        | (1u << OW_WILD_SURFACE_TYPE_FLOWERBED) \
        | (1u << OW_WILD_SURFACE_TYPE_CANOPY))

static void OverworldWildSpawns_ReconcileNativeShadow(
    FieldSystem *fieldSystem,
    LocalMapObject *object)
{
    const u16 *descriptor;
    OverworldWildSurfaceHit surface;
    BOOL hasSurface = FALSE;
    u32 suppressSurfaceShadow;
    u8 behavior;
    int x;
    int y;

    if (fieldSystem != gFieldSysPtr
        || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)) {
        return;
    }

    x = object->xCurr;
    y = object->yCurr;
    if (object->id != OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID) {
        hasSurface = OverworldWildSpawns_QuerySurface(
            fieldSystem,
            x,
            y,
            &surface);
    }

    suppressSurfaceShadow = hasSurface
        ? OW_WILD_NATIVE_SHADOW_SUPPRESSED_SURFACE_TYPES
            & (1u << surface.surfaceType)
        : 0;
    OverworldWildSpawns_SetNativeShadowSuppressed(
        object,
        suppressSurfaceShadow);
    if (suppressSurfaceShadow) {
        OverworldWildSpawns_SetObjectFlags(object, MAPOBJECTFLAG_UNK20);
        return;
    }

    descriptor = ov01_021F9318(object);
    if (descriptor == NULL
        || ((*descriptor >> 4) & 7) == 0) {
        return;
    }

    if (hasSurface
        && surface.surfaceId != OW_WILD_SURFACE_ID_NATIVE_GROUND) {
        behavior = 0;
    } else {
        if (!hasSurface
            && OverworldWildSpawns_GetCanopyTerrainBit(fieldSystem, x, y) != 0) {
            OverworldWildSpawns_SetObjectFlags(object, MAPOBJECTFLAG_UNK20);
            return;
        }
        behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
        if (behavior == OW_WILD_TILE_HEADBUTT || behavior == 0xFF) {
            OverworldWildSpawns_SetObjectFlags(object, MAPOBJECTFLAG_UNK20);
            return;
        }
    }

    /* Custom movement bypasses the stock terrain transition that clears this. */
    OverworldWildSpawns_ClearObjectFlags(object, MAPOBJECTFLAG_UNK20);
    sub_020603F8(object, behavior, behavior, descriptor);
}

static void OverworldWildSpawns_ResetPlayerBallShadowTracking(
    OverworldWildSpawnState *state)
{
    if (state == NULL || state->movementRuntimeState == NULL) {
        return;
    }
    OW_WILD_RUNTIME(state)->playerBallShadowTrackingValid = FALSE;
}

static void OverworldWildSpawns_SyncPlayerBallShadowObject(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    LocalMapObject *ballObject)
{
    OverworldWildOverlayRuntimeState *runtime;
    int currentX;
    int currentY;

    if (state == NULL
        || state->movementRuntimeState == NULL
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        || fieldSystem->taskman != NULL
        || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, ballObject)
        || (ballObject->flags & MAPOBJECTFLAG_ACTIVE) == 0
        || ballObject->id != OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID) {
        OverworldWildSpawns_ResetPlayerBallShadowTracking(state);
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    currentX = (int)((s32)ballObject->posVec[0] >> 16);
    currentY = (int)((s32)ballObject->posVec[2] >> 16);
    if (runtime->playerBallShadowTrackingValid
        && runtime->playerBallShadowTileX == currentX
        && runtime->playerBallShadowTileY == currentY
        && runtime->playerBallShadowGfxId == ballObject->gfxId
        && (ballObject->flags & (MAPOBJECTFLAG_UNK15 | MAPOBJECTFLAG_UNK20)) != 0) {
        return;
    }

    runtime->playerBallShadowTileX = (s16)currentX;
    runtime->playerBallShadowTileY = (s16)currentY;
    runtime->playerBallShadowGfxId = (u16)ballObject->gfxId;
    runtime->playerBallShadowTrackingValid = TRUE;
    OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, ballObject);
}

static void OverworldWildSpawns_ClearTeleportFlickerObject(
    OverworldWildSpawnState *state,
    int slot,
    BOOL deleteObject)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }
    (void)deleteObject;
    state->movementTeleportFlickerObjects[slot] = NULL;
}

static void __attribute__((optimize("Os"))) OverworldWildSpawns_ApplyTeleportHiddenVisual(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    BOOL actorVisible)
{
    OverworldWildOverlayRuntimeState *runtime;
    s32 baseY;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || !state->movementTeleportHidden[slot]) {
        return;
    }

    if (OverworldWildSpawns_IsTeleportMovementActive(state, slot)) {
        runtime = OW_WILD_RUNTIME(state);
        OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
        if (runtime->movementCustomMotionModes[slot]
            == OW_WILD_CUSTOM_MOTION_TELEPORT_HIDDEN) {
            OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
            OverworldWildSpawns_SetObjectFlags(object, BIT_VANISH);
            return;
        }

        if (actorVisible) {
            object->posVec[0] = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
                runtime->movementCustomJumpStartX[slot]);
            object->posVec[2] = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
                runtime->movementCustomJumpStartY[slot]);
            baseY = runtime->movementCustomJumpStartBaseY[slot];
        } else {
            object->posVec[0] = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
                runtime->movementCustomJumpTargetX[slot]);
            object->posVec[2] = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
                runtime->movementCustomJumpTargetY[slot]);
            baseY = runtime->movementCustomJumpTargetBaseY[slot];
        }
        object->posVec[1] = (u32)baseY;
        object->hCurr = baseY >> 15;
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        return;
    }

    OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
    if (OverworldWildSpawns_ShouldShowTeleportFlickerForSlot(state, slot)) {
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    } else {
        OverworldWildSpawns_SetObjectFlags(object, BIT_VANISH);
    }
}

static void OverworldWildSpawns_UpdateTeleportFlicker(OverworldWildSpawnState *state, int slot)
{
    LocalMapObject *object;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || !state->movementTeleportHidden[slot]) {
        return;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        return;
    }

    OverworldWildSpawns_ApplyTeleportHiddenVisual(state, slot, object, TRUE);
    if (state->movementTeleportFlickerTimers[slot] != 0) {
        state->movementTeleportFlickerTimers[slot]--;
        if (state->movementTeleportFlickerTimers[slot] == 0) {
            OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
            OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
        }
    }
}

static void OverworldWildSpawns_StartConditionalTeleportRealFlicker(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL) {
        return;
    }

    OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
    state->movementTeleportHidden[slot] = FALSE;
    state->movementTeleportHiddenSteps[slot] = 0;
#if OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_REAL_FLICKER
    state->movementTeleportFlickerTimers[slot] = OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES;
#else
    state->movementTeleportFlickerTimers[slot] = 0;
#endif
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
}

static void OverworldWildSpawns_StartTeleportVisibleCooldown(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    OverworldWildSpawns_RevealTeleportObject(state, slot, object);
    state->movementTeleportVisiblePause[slot] = TRUE;
    state->movementCooldowns[slot] = OverworldWildSpawns_GetTeleportPauseFrames(
        profile,
        state->movementSpotStates[slot]);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
}

#if OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_REAL_FLICKER
static BOOL OverworldWildSpawns_UpdateConditionalTeleportRealFlicker(OverworldWildSpawnState *state, int slot)
{
    OverworldWildBehaviorProfile profile;
    LocalMapObject *object;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->movementTeleportHidden[slot]
        || !OverworldWildSpawns_IsConditionalTeleportLocomotion(state, slot)) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        return FALSE;
    }
    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, NULL);
    if (!OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER(profile.chillAction)) {
        state->movementTeleportFlickerTimers[slot] = 0;
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
        return TRUE;
    }

    OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
    if (state->movementTeleportFlickerTimers[slot] == 0
        || state->movementTeleportFlickerTimers[slot] > OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES) {
        state->movementTeleportFlickerTimers[slot] = OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES;
    }

    if (OverworldWildSpawns_ShouldShowConditionalTeleportRealFlicker(state->movementTeleportFlickerTimers[slot])) {
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    } else {
        OverworldWildSpawns_SetObjectFlags(object, BIT_VANISH);
    }
    OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);

    if (state->movementTeleportFlickerTimers[slot] != 0) {
        state->movementTeleportFlickerTimers[slot]--;
        if (state->movementTeleportFlickerTimers[slot] == 0) {
            OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
        }
    }
    return TRUE;
}
#endif

static LocalMapObject *OverworldWildSpawns_NormalizeTeleportObjectForOwner(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    FieldSystem *fieldSystem;
    int x;
    int y;

    if (!state->spawns[slot].active
        || state->spawns[slot].species == SPECIES_NONE) {
        return object;
    }

    if (object == NULL) {
        object = state->spawns[slot].object;
    }
    fieldSystem = state->movementFieldSystem;
    if (object == NULL
        || object != state->spawns[slot].object
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return object;
    }

    OverworldWildSpawns_CancelSpotEmotePresentation(state, slot, object);
    OverworldWildSpawns_FinishPresentationCommand(object);
    OverworldWildSpawns_RevealTeleportObject(state, slot, object);
    OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
    OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);

    x = object->xCurr;
    y = object->yCurr;
    OverworldWildSpawns_SetObjectLandingTile(fieldSystem, object, x, y);
    OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
    return object;
}

static void OverworldWildSpawns_TryStartTeleportFlicker(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || !state->movementTeleportHidden[slot]) {
        return;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, &primitives);
    if (primitives.chillLocomotion != OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT
        || !OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER(profile.chillAction)
        || primitives.chillTarget != OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER) {
        return;
    }

    if (OverworldWildSpawns_IsConditionalTeleportLocomotion(state, slot)) {
        state->movementTeleportFlickerTimers[slot] = OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_FLICKER_FRAMES;
    } else if ((gf_rand() % 100) < OW_WILD_SPAWNER_TELEPORT_FLICKER_CHANCE_PERCENT) {
        state->movementTeleportFlickerTimers[slot] = OW_WILD_SPAWNER_TELEPORT_FLICKER_FRAMES;
    } else {
        state->movementTeleportFlickerTimers[slot] = 0;
    }
    OverworldWildSpawns_ApplyTeleportHiddenVisual(state, slot, object, TRUE);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
}

static BOOL OverworldWildSpawns_IsTeleportDestinationTile(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    u16 allowedTile,
    int x,
    int y)
{
    if (fieldSystem == NULL
        || object == NULL
        || x < 0
        || y < 0
        || ((int)OverworldWildSpawns_ObjectCurrentX(object) == x && (int)OverworldWildSpawns_ObjectCurrentY(object) == y)) {
        return FALSE;
    }

    return OverworldWildSpawns_IsBehaviorAllowedMovementTile(fieldSystem, allowedTile, x, y);
}

static __attribute__((noinline)) u8 OverworldWildSpawns_GetFacingTowardTile(
    int fromX,
    int fromY,
    int toX,
    int toY,
    u8 fallback)
{
    u8 directions[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];

    if (OverworldWildSpawns_BuildDirectedDirections(toX - fromX, toY - fromY, directions) > 0) {
        return directions[0];
    }
    return fallback;
}

static void __attribute__((optimize("Os")))
OverworldWildSpawns_ClassifyTeleportCandidate(
    void *rawContext,
    OverworldActorTeleportCandidate *candidate)
{
    OverworldWildTeleportWorldContext *context = rawContext;
    OverworldWildSurfaceHit surface;

    if (context == NULL || candidate == NULL) {
        return;
    }
    if (!OverworldWildSpawns_IsTeleportDestinationTile(
            context->fieldSystem,
            context->object,
            context->allowedTile,
            candidate->targetX,
            candidate->targetY)) {
        candidate->rejectionFlags |= OVERWORLD_MOTION_CANDIDATE_BAD_TERRAIN;
        return;
    }
    candidate->targetSurfaceId = OverworldWildSpawns_QuerySurface(
            context->fieldSystem,
            candidate->targetX,
            candidate->targetY,
            &surface)
        ? surface.surfaceId
        : OW_WILD_SURFACE_ID_NATIVE_GROUND;
    candidate->targetBaseY = OverworldWildSpawns_GetObjectGroundBaseYAt(
        context->fieldSystem,
        context->object,
        candidate->targetX,
        candidate->targetY);
    if (context->facePlayer) {
        candidate->targetFacing = OverworldWildSpawns_GetFacingTowardTile(
            candidate->targetX,
            candidate->targetY,
            context->playerX,
            context->playerY,
            context->object->curFacing);
    }
}

static inline BOOL __attribute__((always_inline))
OverworldWildSpawns_IsTeleportOnPlayerAdjacentTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile)
{
    int targetX;
    int targetY;

    if (!OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
            state,
            fieldSystem,
            slot,
            profile,
            &targetX,
            &targetY)) {
        return FALSE;
    }
    return (int)OverworldWildSpawns_ObjectCurrentX(object) == targetX
        && (int)OverworldWildSpawns_ObjectCurrentY(object) == targetY;
}

static void OverworldWildSpawns_StartMovementCrashShake(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u8 frames)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL) {
        return;
    }

    OverworldWildSpawns_RestoreMovementCrashShake(state, slot);
    state->movementCrashShakeBaseX[slot] = object->posVec[0];
    state->movementCrashShakeBaseZ[slot] = object->posVec[2];
    state->movementCrashShakeTimers[slot] = frames;

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
}

static void OverworldWildSpawns_TickMovementCrashShake(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int i;

    if (state == NULL) {
        return;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *object;
        s32 offset;

        if (state->movementCrashShakeTimers[i] == 0) {
            continue;
        }

        if (!OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[i])) {
            state->movementCrashShakeTimers[i] = 0;
            continue;
        }

        if (state->movementCrashShakeTimers[i] <= 1) {
            OverworldWildSpawns_RestoreMovementCrashShake(state, i);
            continue;
        }

        state->movementCrashShakeTimers[i]--;
        object = state->spawns[i].object;
        offset = OverworldWildSpawns_GetMovementCrashShakeOffset(state->movementCrashShakeTimers[i]);
        object->posVec[0] = (u32)((s32)state->movementCrashShakeBaseX[i] + offset);
        object->posVec[2] = (u32)((s32)state->movementCrashShakeBaseZ[i] - offset);
    }
}

static void __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ResetEmotePresentationStyle(
    OverworldWildSpawnState *state,
    int slot,
    u8 bubbleId)
{
    state->movementEmoteBubbleIds[slot] = bubbleId;
    state->movementEmoteShowBubbleEachJump[slot] = FALSE;
    state->movementEmotePlayCryOnHop[slot] = FALSE;
    OW_WILD_RUNTIME(state)->movementEmotePlayHopSound[slot] = TRUE;
}

static void OverworldWildSpawns_ResetSlotSpotState(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    OverworldWildSpawns_ClearThrowStateForSlot(state, slot);
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    state->movementCooldowns[slot] = 0;
    state->movementEmoteTimers[slot] = 0;
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    state->movementEmoteDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    state->movementEmoteJumpsRemaining[slot] = 0;
    state->movementEmoteEndStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ResetEmotePresentationStyle(
        state, slot, OW_WILD_SPAWNER_BUBBLE_ID_NONE);
    OW_WILD_RUNTIME(state)->movementEmotePartnerPrepObjects[slot] = NULL;
    OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] = 0;
    if (state->movementQueuedBattleSlot == slot) {
        state->movementQueuedBattleSlot = -1;
    }
    state->movementPreviousTileX[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    state->movementPreviousTileY[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    state->movementPreviousTileLocked[slot] = FALSE;
    state->movementPendingDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    state->movementPendingDistances[slot] = 0;
    state->movementLastDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    state->movementLastDistances[slot] = 0;
    state->movementSpawnRunTargetX[slot] = 0;
    state->movementSpawnRunTargetY[slot] = 0;
    state->movementSpawnRunActive[slot] = FALSE;
    OverworldWildSpawns_ClearStagedHopTarget(state, slot);
    OverworldWildSpawns_ClearWalkMovementState(state, slot, NULL);
    state->movementCrashShakeTimers[slot] = 0;
    state->movementCrashShakeBaseX[slot] = 0;
    state->movementCrashShakeBaseZ[slot] = 0;
    state->movementTeleportHidden[slot] = FALSE;
    state->movementTeleportHiddenSteps[slot] = 0;
    state->movementTeleportFlickerTimers[slot] = 0;
    state->movementTeleportVisiblePause[slot] = FALSE;
    state->movementMankeyTreeTopProxyObjects[slot] = NULL;
    state->movementTeleportFlickerObjects[slot] = NULL;
}

static void OverworldWildSpawns_SetPreviousTile(
    OverworldWildSpawnState *state,
    int slot,
    int x,
    int y)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    state->movementPreviousTileX[slot] = (s16)x;
    state->movementPreviousTileY[slot] = (s16)y;
    state->movementPreviousTileLocked[slot] =
        OW_WILD_SPAWNER_PREVIOUS_TILE_LOGICAL;
}

static void OverworldWildSpawns_RecordFinishedMovementHistory(
    OverworldWildSpawnState *state,
    int slot)
{
    LocalMapObject *object;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    if (state->movementPendingDirections[slot] != OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE
        && state->movementPendingDistances[slot] != 0
        && state->movementPreviousTileLocked[slot]
            == OW_WILD_SPAWNER_PREVIOUS_TILE_LOGICAL) {
        state->movementLastDirections[slot] = state->movementPendingDirections[slot];
        state->movementLastDistances[slot] = state->movementPendingDistances[slot];
    }
    state->movementPendingDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    state->movementPendingDistances[slot] = 0;
    object = state->spawns[slot].object;
    if (object != NULL) {
        OverworldWildSpawns_ResolveObjectLandingHeight(
            state->movementFieldSystem,
            object,
            object->xCurr,
            object->yCurr);
        OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownX[slot] =
            (s16)object->xCurr;
        OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownY[slot] =
            (s16)object->yCurr;
    }
}

static void OverworldWildSpawns_FinishPresentationCommand(LocalMapObject *object)
{
    int i;

    if (object == NULL) {
        return;
    }

    for (i = 0;
         i < OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS
             && MapObject_IsSingleMovementActive(object);
         i++) {
        if (MapObject_UpdateMovementCommand(object)) {
            MapObject_ClearSingleMovementActive(object);
            return;
        }
    }

    if (MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }
}

static void OverworldWildSpawns_CancelSpotEmotePresentation(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    OverworldWildOverlayRuntimeState *runtime;
    LocalMapObject *owner;
    BOOL restoreAlreadyStarted;

    if (state == NULL
        || state->movementRuntimeState == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    owner = runtime->movementEmotePartnerPrepObjects[slot];
    restoreAlreadyStarted = state->movementEmoteSteps[slot]
        == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    runtime->movementEmotePartnerPrepObjects[slot] = NULL;
    if (owner == NULL
        || owner != object
        || object != state->spawns[slot].object) {
        return;
    }

    OverworldWildSpawns_FinishPresentationCommand(object);
    if (!restoreAlreadyStarted) {
        (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_SPOT_EMOTE_FREEZE_COMMAND);
        (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_SPOT_EMOTE_PARTNER_RESTORE_COMMAND);
    }
}

static void OverworldWildSpawns_ResetSlotMovementCommand(OverworldWildSpawnState *state, int slot, BOOL clearObjectCommand)
{
    LocalMapObject *object = NULL;

    OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
    if (state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->spawns[slot].active
        && state->movementFieldSystem != NULL
        && OverworldWildSpawns_IsPresentationFieldContextCurrent(state, state->movementFieldSystem)
        && OverworldWildSpawns_IsCurrentSpawnObject(state->movementFieldSystem, &state->spawns[slot])) {
        object = state->spawns[slot].object;
    }
    if (clearObjectCommand) {
        OverworldWildSpawns_CancelSpotEmotePresentation(state, slot, object);
        if (object != NULL) {
            OverworldWildSpawns_ClearObjectFlags(object, MAPOBJECTFLAG_UNK7);
        }
    }
    if (state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && clearObjectCommand
        && OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[slot]
        && object != NULL) {
        OverworldWildSpawns_FinishPresentationCommand(object);
        (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND);
        (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND);
    }
    if (slot >= 0 && slot < OW_WILD_MAX_SPAWNS) {
        OverworldWildSpawns_ClearCustomJump(state, slot);
        OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[slot] = FALSE;
    }
    if (clearObjectCommand) {
        OverworldWildSpawns_RestoreMovementCrashShake(state, slot);
        OverworldWildSpawns_RevealTeleportObject(state, slot, NULL);
        OverworldWildSpawns_ClearMankeyTreeTopProxyObject(state, slot, TRUE);
    } else {
        state->movementCrashShakeTimers[slot] = 0;
        OverworldWildSpawns_ClearMankeyTreeTopProxyObject(state, slot, FALSE);
        OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, FALSE);
    }

    if (clearObjectCommand && object != NULL) {
        OverworldWildSpawns_CancelNativeHeldMovementForSlot(state, slot, object);
        OverworldWildSpawns_ClearObjectFlags(
            object,
            OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS);
        OverworldWildSpawns_FinishPresentationCommand(object);
    }

    OW_WILD_RUNTIME(state)->movementNativeHeldMask &=
        ~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
    OverworldWildSpawns_ResetSlotSpotState(state, slot);
}

static void OverworldWildSpawns_ResetSlotMovementCommandForMapHeaderChange(
    OverworldWildSpawnState *state,
    int slot,
    BOOL clearObjectCommand)
{
    u8 spotState;
    u8 tiredTimer;
    u8 movementCooldown;

    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    spotState = state->movementSpotStates[slot];
    tiredTimer = spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? state->movementEmoteTimers[slot]
        : 0;
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_EMOTING) {
        spotState = state->movementEmoteEndStates[slot];
    }
    movementCooldown = state->movementCooldowns[slot];

    OverworldWildSpawns_ResetSlotMovementCommand(state, slot, clearObjectCommand);

    state->movementSpotStates[slot] = spotState;
    state->movementCooldowns[slot] = movementCooldown;
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        state->movementEmoteTimers[slot] = tiredTimer;
    }
}

static void OverworldWildSpawns_PrepareSlotForCapture(
    OverworldWildSpawnState *state,
    int slot)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT) {
        return;
    }
    OverworldWildSpawns_ClearThrowStateForSlot(state, slot);
    OverworldWildSpawns_ResetSlotMovementCommand(state, slot, TRUE);
    OverworldWildSpawns_ClearStagedHopTarget(state, slot);
    OverworldWildSpawns_ClearSpawnRunState(state, slot);
    OverworldWildSpawns_ClearWalkMovementState(state, slot, state->spawns[slot].object);
    if (state->movementQueuedBattleSlot == slot) {
        state->movementQueuedBattleSlot = -1;
        state->movementBattleSettleFrames = 0;
    }
}

static void OverworldWildSpawns_ResetAllMovementCommands(
    OverworldWildSpawnState *state,
    BOOL clearObjectCommand,
    BOOL preserveMapHeaderState)
{
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    if (!sOverworldWildMovementFrameTaskExecuting) {
        OverworldWildSpawns_StopFrameMovementTask();
    }
#endif

    if (state == NULL) {
        return;
    }

    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_CANCEL_MAINTENANCE,
        0);
    OverworldWildSpawns_ClearQueuedHelpChildren(state);
    OverworldWildSpawns_ResetAllMovementStateOnly(
        state,
        clearObjectCommand,
        preserveMapHeaderState);
    state->movementFieldSystem = NULL;
}

static void OverworldWildSpawns_ResetAllMovementStateOnly(
    OverworldWildSpawnState *state,
    BOOL clearObjectCommand,
    BOOL preserveMapHeaderState)
{
    int i;

    if (state == NULL) {
        return;
    }

    state->movementBattleSettleFrames = 0;
    state->movementQueuedBattleSlot = -1;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (preserveMapHeaderState) {
            OverworldWildSpawns_ResetSlotMovementCommandForMapHeaderChange(
                state,
                i,
                clearObjectCommand);
        } else {
            OverworldWildSpawns_ResetSlotMovementCommand(state, i, clearObjectCommand);
        }
    }
}

static void OverworldWildSpawns_DetachAllMovementStateOnContextLoss(
    OverworldWildSpawnState *state,
    BOOL preserveMapHeaderState)
{
    OverworldWildOverlayRuntimeState *runtime;
    FieldSystem *fieldSystem;
    int i;

    if (state == NULL) {
        return;
    }
    OverworldWildSpawns_MountCancel(
        OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
    OverworldWildSpawns_CancelDeferredBattleScript();
    OverworldWildSpawns_ResetPendingBattle(state);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_StopFrameMovementTask();
#endif
    fieldSystem = state->movementFieldSystem;
    if (!preserveMapHeaderState
        || OverworldWildSpawns_IsPlayerBallProjectileActive()) {
        (void)OverworldWildSpawns_ApplyPresentationCommand(
            fieldSystem,
            state,
            preserveMapHeaderState
                ? OW_WILD_HELPER_PRESENTATION_SUSPEND
                : OW_WILD_HELPER_PRESENTATION_DISCARD,
            0);
    }
    OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe();
    if (!preserveMapHeaderState) {
        state->captureTargetMask = 0;
    }
    state->movementBattleSettleFrames = 0;
    state->movementQueuedBattleSlot = -1;

    if (state->movementRuntimeState == NULL) {
        state->movementFieldSystem = NULL;
        return;
    }
    runtime = OW_WILD_RUNTIME(state);
    OverworldWildSpawns_ClearAllConditionState(runtime->conditions);
    runtime->queuedSpawnSlotPlusOne = 0;
    runtime->refillTerrainMask = 0;
    runtime->refillPositionChecksRemaining = 0;
    if (!preserveMapHeaderState) {
        runtime->movementNativeShadowRestorePending = FALSE;
    }
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_CANCEL_MAINTENANCE,
        0);
    OverworldWildSpawns_ResetPlayerBallShadowTracking(state);
    if (OverworldWildSpawns_IsPresentationFieldContextCurrent(state, fieldSystem)) {
        /* Finish every object-owned command, including the paired 0x4A restore. */
        OverworldWildSpawns_ResetAllMovementCommands(
            state,
            TRUE,
            preserveMapHeaderState);
    } else {
        /* The old manager is no longer safe to touch. Cancel code-owned tasks only. */
        OverworldWildSpawns_ResetAllMovementStateOnly(
            state,
            FALSE,
            preserveMapHeaderState);
        OverworldWildSpawns_ClearQueuedHelpChildren(state);
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            OverworldWildSpawns_ClearStagedHopTarget(state, i);
            OverworldWildSpawns_ClearSpawnRunState(state, i);
            OverworldWildSpawns_ClearWalkMovementState(state, i, NULL);
            OverworldWildSpawns_ClearMankeyTreeTopCache(state, i);
            runtime->movementEmotePartnerPrepObjects[i] = NULL;
            state->movementTeleportHidden[i] = FALSE;
            state->movementTeleportHiddenSteps[i] = 0;
            state->movementTeleportFlickerTimers[i] = 0;
            state->movementTeleportVisiblePause[i] = FALSE;
        }
    }

    memset(&runtime->throwState, 0, sizeof(runtime->throwState));
    memset(runtime->spawnPresentations.farSamples, 0,
        sizeof(runtime->spawnPresentations.farSamples));
    runtime->spawnPresentations.managerRestoreMask = 0;
    runtime->spawnPresentations.distanceDespawnPendingMask = 0;
    state->movementFieldSystem = NULL;
}

static const OverworldWildSpawn * __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_RetainedMaskNamesActiveSpawns(
    const OverworldWildSpawnState *state,
    u16 retainedActorMask)
{
    const OverworldWildSpawn *spawn = state->spawns;
    int remaining = OW_WILD_MAX_SPAWNS;

    do {
        /* Test the current low mask bit without loading a Thumb-1 literal. */
        if (((u32)retainedActorMask << 31) != 0 && !spawn->active) {
            return NULL;
        }
        retainedActorMask >>= 1;
        spawn++;
    } while (--remaining != 0);
    return spawn;
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_RebindRetainedSpawnObject(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    const OverworldActorTransitionCall *call,
    int slot,
    OverworldActorHandle *handleOut)
{
    OverworldActorQuery query;
    OverworldActorSnapshot snapshot;
    OverworldWildSpawn *spawn;
    LocalMapObject *object;

    if (fieldSystem == NULL || fieldSystem->location == NULL
        || fieldSystem->mapObjectMan == NULL || state == NULL || call == NULL
        || call->work != OVERWORLD_ACTOR_TRANSITION_WORK_REBIND
        || call->currentMapId != fieldSystem->location->mapId
        || handleOut == NULL
        || (u32)slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    spawn = &state->spawns[slot];
    if (!spawn->active || spawn->encounterGeneration == 0
        || spawn->objectId != OW_WILD_OBJECT_ID_START + slot
        || (call->retainedActorMask
                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) == 0) {
        return FALSE;
    }
    memset(&query, 0, sizeof(query));
    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX;
    query.index = (u8)slot;
    if (OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(&query, &snapshot)
            != OVERWORLD_ACTOR_RESULT_OK
        || !snapshot.hasActor
        || !OverworldActorTransition_RetainedHandleMatches(
            call,
            &snapshot.actor.handle,
            (u16)slot,
            spawn->encounterGeneration)
        || snapshot.actor.subjectIdentity != spawn->personality) {
        return FALSE;
    }
    object = GetMapObjectByID(fieldSystem->mapObjectMan, spawn->objectId);
    if (object == NULL
        || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)
        || (object->flags & MAPOBJECTFLAG_ACTIVE) == 0
        || object->id != spawn->objectId
        || object->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
        return FALSE;
    }
    spawn->object = object;
    *handleOut = snapshot.actor.handle;
    return TRUE;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_ApplyTransitionWork(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    const OverworldActorTransitionCall *call)
{
    OverworldWildOverlayRuntimeState *runtime;
    int i;

    if (fieldSystem == NULL || state == NULL || call == NULL) {
        return FALSE;
    }
    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE) {
        u16 partnerPrepMask = 0;
        u16 customJumpPrepMask = 0;

        if (state->movementRuntimeState != NULL) {
            runtime = OW_WILD_RUNTIME(state);
            for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
                if (state->spawns[i].active
                    && runtime->movementEmotePartnerPrepObjects[i]
                        == state->spawns[i].object) {
                    partnerPrepMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i);
                }
                if (state->spawns[i].active
                    && runtime->movementCustomJumpPrepActive[i]) {
                    customJumpPrepMask |= OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i);
                }
            }
        }
        OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, TRUE);
        if (state->movementRuntimeState != NULL) {
            runtime = OW_WILD_RUNTIME(state);
            for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
                if ((partnerPrepMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0) {
                    runtime->movementEmotePartnerPrepObjects[i] =
                        state->spawns[i].object;
                }
                runtime->movementCustomJumpPrepActive[i] =
                    (customJumpPrepMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0;
            }
        }
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            LocalMapObject *object = state->spawns[i].object;
            BOOL restoreSpotPartner;

            if (!state->spawns[i].active
                || object == NULL
                || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)
                || (object->flags & MAPOBJECTFLAG_ACTIVE) == 0
                || object->id != state->spawns[i].objectId
                || object->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
                continue;
            }
            restoreSpotPartner = state->movementRuntimeState != NULL
                && OW_WILD_RUNTIME(state)->movementEmotePartnerPrepObjects[i]
                    == object;
            if (restoreSpotPartner) {
                /* Complete any in-flight 0x4A before clearing held ownership. */
                OverworldWildSpawns_FinishPresentationCommand(object);
            }
            MapObject_ClearHeldMovement(object);
            MapObject_ClearSingleMovementActive(object);
            if (restoreSpotPartner) {
                OW_WILD_RUNTIME(state)->movementEmotePartnerPrepObjects[i] = NULL;
                (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
                    object,
                    OW_WILD_SPAWNER_SPOT_EMOTE_FREEZE_COMMAND);
                (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
                    object,
                    OW_WILD_SPAWNER_SPOT_EMOTE_PARTNER_RESTORE_COMMAND);
            }
            if (state->movementRuntimeState != NULL) {
                OverworldWildSpawns_ResetSlotMovementCommandForMapHeaderChange(
                    state,
                    i,
                    TRUE);
            }
            OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride(i, object);
            OverworldWildSpawns_ClearObjectFlags(object, OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS);
            OverworldWildSpawns_FinishPresentationCommand(object);
            if (state->movementRuntimeState != NULL) {
                OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownX[i] =
                    (s16)object->xCurr;
                OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownY[i] =
                    (s16)object->yCurr;
                OW_WILD_RUNTIME(state)->spawnPresentations.farSamples[i] = 0;
            }
        }
        return TRUE;
    }

    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND) {
        if (call->disposition == OVERWORLD_ACTOR_TRANSITION_DISPOSITION_DISCARD) {
            return TRUE;
        }
        if (OverworldWildSpawns_RetainedMaskNamesActiveSpawns(
                state, call->retainedActorMask) == NULL) {
            return FALSE;
        }
        if (fieldSystem->location == NULL || fieldSystem->mapObjectMan == NULL
            || ((MapObjectMan *)fieldSystem->mapObjectMan)->objects == NULL
            || call->currentMapId != fieldSystem->location->mapId) {
            return FALSE;
        }
        state->mapGeneration = call->nextMapGeneration;
        state->mapId = call->currentMapId;
        state->mapObjectMan = fieldSystem->mapObjectMan;
        state->mapObjects = ((MapObjectMan *)fieldSystem->mapObjectMan)->objects;
        state->movementFieldSystem = fieldSystem;
        state->pendingSlot = -1;
        state->movementQueuedBattleSlot = -1;
        state->pendingMapGeneration = 0;
        state->pendingEncounterGeneration = 0;
        state->battleGraceSteps = 0;
        state->presentationRestorePending = FALSE;
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            OverworldActorHandle handle;
            OverworldWildBehaviorProfile stableProfile;
            LocalMapObject *object;

            if (!state->spawns[i].active) {
                continue;
            }
            if (!OverworldWildSpawns_RebindRetainedSpawnObject(
                    fieldSystem, state, call, i, &handle)) {
                return FALSE;
            }
            state->spawns[i].mapId = call->currentMapId;
            OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
                state, i, &stableProfile, NULL);
            if (!OverworldWildSpawns_PrepareConditionsForSlot(
                    state, i, &handle, &stableProfile)) {
                return FALSE;
            }
            object = state->spawns[i].object;
            object->unkC = call->currentMapId;
            state->movementActorControlModes[i] =
                OW_WILD_ACTOR_CONTROL_AUTONOMOUS;
            if (!OverworldWildSpawns_ApplyPresentationCommand(
                    fieldSystem,
                    state,
                    OW_WILD_HELPER_PRESENTATION_NORMALIZE_SLOT,
                    (u8)i)) {
                return FALSE;
            }
            OverworldWildSpawns_ApplySpawnPassThroughFlag(state, i, object);
            OverworldWildSpawns_ClearObjectFlags(object, MAPOBJECTFLAG_UNK15);
            OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);
        }
        if (state->movementRuntimeState != NULL) {
            OW_WILD_RUNTIME(state)->movementNativeShadowRestorePending = FALSE;
        }
        return TRUE;
    }

    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_RESUME) {
        state->presentationRestorePending = FALSE;
        gOverworldWildFieldIdleRearmPending |=
            OW_WILD_FIELD_IDLE_REARM_PENDING
            | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        return OverworldWildSpawns_ApplyPresentationCommand(
            fieldSystem,
            state,
            OW_WILD_HELPER_PRESENTATION_REBIND,
            0);
    }

    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD) {
        OverworldWildSpawns_ClearContextLite(state);
        OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, FALSE);
        state->mapGeneration = call->nextMapGeneration;
        state->mapObjectMan = NULL;
        state->mapObjects = NULL;
        state->movementFieldSystem = NULL;
        state->mapId = MAP_NOTHING;
        state->pendingSlot = -1;
        state->movementQueuedBattleSlot = -1;
        state->pendingMapGeneration = 0;
        state->pendingEncounterGeneration = 0;
        state->presentationRestorePending = FALSE;
        gOverworldWildFieldIdleRearmPending |=
            OW_WILD_FIELD_IDLE_REARM_PENDING
            | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        return TRUE;
    }
    return FALSE;
}

static void __attribute__((noinline)) OverworldWildSpawns_CleanupPresentationBeforeUnload(OverworldWildSpawnState *state)
{
    if (state == NULL || state->movementRuntimeState == NULL) {
        return;
    }

    OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, FALSE);
}

static void OverworldWildSpawns_StartMovementCommandForSlot(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u32 movementCommand,
    u8 direction,
    u8 distance)
{
    OverworldWildSpawns_SetPreviousTile(
        state,
        slot,
        OverworldWildSpawns_ObjectCurrentX(object),
        OverworldWildSpawns_ObjectCurrentY(object));
    state->movementPendingDirections[slot] = direction;
    state->movementPendingDistances[slot] = distance;
    /* The native per-object task advances held movement exactly once a frame. */
    MapObject_StartMovementCommandInternal(object, movementCommand);
    OW_WILD_RUNTIME(state)->movementNativeHeldMask |=
        OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    MapObject_SetSingleMovementActive(object);
    state->movementBattleSettleFrames = 0;
    OverworldWildSpawns_SetMovementSlotInProgress(state, slot);
    OverworldWildSpawns_TryStartTeleportFlicker(state, slot, object);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND && OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE
    if (OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot(state, slot)) {
        OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
    }
#endif
    OW_WILD_PERF_INC(sOverworldWildPerfMovementCommandsThisFrame);
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_IsStopSkidTileOpen(
    const OverworldWildDirectionStepContext *stepContext,
    int x,
    int y)
{
    return OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
        stepContext->state,
        stepContext->slot,
        stepContext->fieldSystem,
        stepContext->allowedTile,
        x,
        y,
        -1,
        -1);
}

static BOOL __attribute__((noinline, optimize("O1")))
OverworldWildSpawns_IsStopSkidCorridorOpen(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction,
    u8 distance,
    u8 turnDirection)
{
    int currentX = OverworldWildSpawns_ObjectCurrentX(stepContext->object);
    int currentY = OverworldWildSpawns_ObjectCurrentY(stepContext->object);
    int deltaX = OverworldWalk_DeltaX(direction);
    int deltaY = OverworldWalk_DeltaY(direction);
    int nextX;
    int nextY;

    if (distance == 0) {
        return FALSE;
    }
    do {
        nextX = currentX + deltaX;
        nextY = currentY + deltaY;
        if ((deltaX & deltaY) != 0
            && (!OverworldWildSpawns_IsStopSkidTileOpen(
                    stepContext, nextX, currentY)
                || !OverworldWildSpawns_IsStopSkidTileOpen(
                    stepContext, currentX, nextY))) {
            return FALSE;
        }
        if (!OverworldWildSpawns_IsStopSkidTileOpen(
                stepContext, nextX, nextY)) {
            if (turnDirection == OW_WILD_WALK_DIRECTION_OBSTACLE_APPROACH
                && distance == 1
                && OverworldWildSpawns_TryStartLedgeJumpCommand(
                    stepContext, direction, TRUE, TRUE)
                    == OW_WILD_DIRECTION_STEP_OBSTACLE_HOP_STARTED) {
                return TRUE;
            }
            return FALSE;
        }
        currentX = nextX;
        currentY = nextY;
    } while (--distance != 0);
    if (turnDirection >= OW_WILD_WALK_DIRECTION_OBSTACLE_APPROACH) {
        return TRUE;
    }
    deltaX = OverworldWalk_DeltaX(turnDirection);
    deltaY = OverworldWalk_DeltaY(turnDirection);
    if ((deltaX & deltaY) != 0
        && (!OverworldWildSpawns_IsStopSkidTileOpen(
                stepContext, currentX + deltaX, currentY)
            || !OverworldWildSpawns_IsStopSkidTileOpen(
                stepContext, currentX, currentY + deltaY))) {
        return FALSE;
    }
    return OverworldWildSpawns_IsStopSkidTileOpen(
        stepContext, currentX + deltaX, currentY + deltaY);
}

static inline BOOL __attribute__((always_inline)) OverworldWildSpawns_StartMomentumWalkStep(
    const OverworldWildDirectionStepContext *stepContext,
    const OverworldActorWalkPolicyCall *call)
{
    u8 cardinalFacing;
    int targetX;
    int targetY;

    targetX = stepContext->object->xCurr
        + OverworldWalk_DeltaX(call->stepDirection);
    targetY = stepContext->object->yCurr
        + OverworldWalk_DeltaY(call->stepDirection);
    if ((call->stepFlags
            & OVERWORLD_ACTOR_WALK_STEP_PLANNED_SKID_PATH) != 0) {
        u8 plannedSkidTiles = call->reserved[
            OVERWORLD_ACTOR_WALK_POLICY_SKID_PATH_TILES_INDEX];
        u8 corridorDirection = OW_WILD_WALK_DIRECTION_NONE;

        if ((call->stepFlags & (OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID))
                == OVERWORLD_ACTOR_WALK_STEP_SKID) {
            corridorDirection = call->facingDirection;
        } else if (plannedSkidTiles == 1
            && (call->stepFlags & (OVERWORLD_ACTOR_WALK_STEP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_STOP_SKID
                    | OVERWORLD_ACTOR_WALK_STEP_VALIDATE))
                == OVERWORLD_ACTOR_WALK_STEP_VALIDATE) {
            corridorDirection = OW_WILD_WALK_DIRECTION_OBSTACLE_APPROACH;
        }
        if (!OverworldWildSpawns_IsStopSkidCorridorOpen(
                stepContext,
                call->stepDirection,
                (u8)(plannedSkidTiles
                    + ((call->stepFlags
                            & OVERWORLD_ACTOR_WALK_STEP_SKID) == 0)),
                corridorDirection)) {
            goto validated_step_blocked;
        }
    }
    if ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_VALIDATE) != 0) {
        if (!OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
                stepContext->state,
                stepContext->slot,
                stepContext->fieldSystem,
                stepContext->allowedTile
                    | OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER,
                targetX,
                targetY,
                targetX,
                targetY)) {
            goto validated_step_blocked;
        }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK
        if (OverworldWildSpawns_IsPlayerTile(
                stepContext->fieldSystem,
                targetX,
                targetY)
            || (call->stepDirection <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
                && (MapObject_IsMovementDirectionBlocked(
                        stepContext->object,
                        call->stepDirection)
                    & ~OW_WILD_MAP_OBJECT_BLOCKED_BY_OBJECT) != 0)) {
            goto validated_step_blocked;
        }
#endif
    }

    if ((call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0) {
        cardinalFacing = call->facingDirection;
        if (cardinalFacing > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
            cardinalFacing = OverworldWalk_DiagonalFacing(
                stepContext->object,
                cardinalFacing,
                OverworldWalk_DirectionKey(cardinalFacing));
        }
        OverworldWildSpawns_SetObjectFacing(stepContext->object, cardinalFacing);
        OverworldWildSpawns_SetObjectFlags(stepContext->object, MAPOBJECTFLAG_UNK7);
    }

    if (OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
            stepContext->state,
            stepContext->fieldSystem,
            stepContext->slot,
            stepContext->object,
            call->stepDirection,
            OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP,
            targetX,
            targetY,
            stepContext->profile,
            OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG,
            call->travelTime) != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        goto validated_step_blocked;
    }
    /* A skid uses state 2: still physically reserved, but not logical history. */
    stepContext->state->movementPreviousTileLocked[stepContext->slot] +=
        (call->stepFlags & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0;
    return TRUE;

validated_step_blocked:
    return FALSE;
}

static void __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_ApplyWalkPolicyOutput(
    OverworldWildDirectionStepContext *stepContext,
    OverworldActorWalkPolicyCall *call)
{
    if ((call->stepFlags
            & OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION) != 0) {
        call->stepFlags &= ~OVERWORLD_ACTOR_WALK_STEP_CLEAR_PRESENTATION;
        stepContext->state->movementPreviousTileLocked[stepContext->slot] =
            FALSE;
        stepContext->state->movementLastDistances[stepContext->slot] = 0;
        stepContext->object->flags &= ~MAPOBJECTFLAG_UNK7;
        if (call->facingDirection
                <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            && call->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP
            && call->startResult
                != OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED) {
            OverworldWildSpawns_SetObjectFacing(
                stepContext->object, call->facingDirection);
        }
    }
    if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_NONE) {
        return;
    }
    if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_SKID_DUST
        || call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_STOMP) {
        OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->playLandingHopParticle(
            stepContext->object);
        if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_STOMP) {
            OverworldActor_PlayStompSound(call->lane->walkOptions);
        } else if (call->facingDirection
            == OW_WILD_WALK_DIRECTION_NONE) {
            stepContext->state->movementCooldowns[stepContext->slot] =
                OW_WILD_SPAWNER_WALK_STOP_SKID_PAUSE_FRAMES;
        }
    } else if (call->effect == OVERWORLD_ACTOR_WORLD_EFFECT_CRASH) {
        OverworldWildSpawns_PlayMovementCrashFeedback(
            stepContext->profile,
            stepContext->state->movementSpotStates[stepContext->slot]);
        if ((call->lane->walkOptions
                & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) == 0) {
            OverworldWildSpawns_StartMovementCrashShake(
                stepContext->state,
                stepContext->slot,
                stepContext->object,
                OW_WILD_SPAWNER_WALK_CRASH_SHAKE_FRAMES);
        }
    }
    call->effect = OVERWORLD_ACTOR_WORLD_EFFECT_NONE;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ExecuteWalkPolicy(
    OverworldWildDirectionStepContext *stepContext,
    OverworldActorWalkPolicyCall *call)
{
    BOOL started;

    OverworldWildSpawns_ApplyWalkPolicyOutput(stepContext, call);
    if (call->decision != OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
        return call->decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
    }
    started = OverworldWildSpawns_StartMomentumWalkStep(stepContext, call);
    call->operation = OVERWORLD_ACTOR_WALK_POLICY_START_RESULT;
    call->startResult = started
        ? OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED
        : OVERWORLD_ACTOR_WALK_POLICY_START_BLOCKED;
    if (!OverworldWildSpawns_ReduceWalk(call)) {
        return FALSE;
    }
    OverworldWildSpawns_ApplyWalkPolicyOutput(stepContext, call);
    return call->decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
}

static u32 __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ReduceRole(
    int slot,
    u32 request,
    u32 details)
{
    OverworldRoleControllerInput roleInput;
    OverworldRoleControllerOutput roleOutput;
    u32 decision;

    roleInput.version = OVERWORLD_ROLE_CONTROLLER_VERSION;
    roleInput.size = sizeof(roleInput);
    roleInput.role = slot == OW_WILD_FOLLOWER_SLOT
        ? OVERWORLD_ROLE_CONTROLLER_ROLE_FOLLOWER
        : OVERWORLD_ROLE_CONTROLLER_ROLE_WILD;
    roleInput.event = (u8)request;
    roleInput.intentKind = (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT);
    roleInput.requestedDirection =
        (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT);
    roleInput.committedDirection =
        (u8)(request >> OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT);
    roleInput.flags = (u8)details;
    roleInput.chainAction =
        (u8)(details >> OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT);
    roleInput.chainTicks =
        (u8)(details >> OW_WILD_SPAWNER_ROLE_RESULT_TICKS_SHIFT);
    OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(
        &roleInput, &roleOutput);
    decision = ((const u32 *)(const void *)&roleOutput)[1];
    if (roleOutput.decision == OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT) {
        if (roleOutput.intentKind != roleInput.intentKind) {
            return 0;
        }
        (void)roleOutput.direction;
        return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED
            | (decision >> 16);
    }
    if (roleOutput.decision != OVERWORLD_ROLE_CONTROLLER_DECISION_TERMINAL) {
        return 0;
    }
    (void)OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH;
    return OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED
        | ((const u32 *)(const void *)&roleOutput)[2];
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_TryStartCanopyEntryHop(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction)
{
    const OverworldWildBehaviorProfileData *lane;
    int targetX;
    int targetY;
    u8 spotState;

    spotState = stepContext->state->movementSpotStates[stepContext->slot];
    lane = OverworldWildSpawns_GetControllerLane(
        stepContext->profile,
        spotState);
    targetX = OverworldWildSpawns_ObjectCurrentX(stepContext->object)
        + OverworldWildSpawns_MovementDirectionDeltaX(direction);
    targetY = OverworldWildSpawns_ObjectCurrentY(stepContext->object)
        + OverworldWildSpawns_MovementDirectionDeltaY(direction);
    if (OverworldWildSpawns_GetElevatedTerrainBit(
            stepContext->fieldSystem,
            targetX,
            targetY) != OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY
        || (lane->chillAllowedTerrainMask
            & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY) == 0
        || lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        return FALSE;
    }
    OverworldWildSpawns_ClearWalkMovementState(
        stepContext->state,
        stepContext->slot,
        stepContext->object);
    return OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
        stepContext->state,
        stepContext->fieldSystem,
        stepContext->slot,
        stepContext->profile,
        OverworldWildSpawns_GetAllowedTileForSpotState(
            stepContext->profile,
            spotState),
        targetX,
        targetY,
        targetX,
        targetY,
        0);
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_TryStartAcceleratedWalkStep(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction)
{
    OverworldActorWalkPolicyCall call;
    OverworldActorPolicyView policy;
    u32 roleDecision;
    u8 roleFlags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;
    u8 spotState = stepContext->state->movementSpotStates[stepContext->slot];
    const OverworldWildBehaviorProfileData *lane =
        OverworldWildSpawns_GetControllerLane(
            stepContext->profile,
            spotState);

    if (!OverworldActorPolicy_Inspect((u8)stepContext->slot, &policy)) {
        return FALSE;
    }

    if ((lane->walkOptions
            & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0) {
        roleFlags |= OVERWORLD_ROLE_CONTROLLER_INPUT_RAM;
    }
    roleDecision = OverworldWildSpawns_ReduceRole(
            stepContext->slot,
            OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST
                | (OVERWORLD_ROLE_CONTROLLER_INTENT_WALK
                    << OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT)
                | ((u32)direction
                    << OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT)
                | ((u32)policy.walkMomentum.direction
                    << OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT),
            roleFlags);
    if ((roleDecision & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0) {
        return FALSE;
    }

    OverworldWildSpawns_InitPolicyCall(
        &call,
        stepContext->slot,
        OVERWORLD_ACTOR_WALK_POLICY_INPUT);
    call.lane = lane;
    call.direction = (u8)roleDecision;
    call.laneState = spotState;
    call.flags = 0;
    if ((roleDecision
            & (OVERWORLD_ROLE_CONTROLLER_INTENT_ENABLE_CHAIN
                << OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT)) != 0) {
        call.flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    }
    if ((roleDecision
            & (OVERWORLD_ROLE_CONTROLLER_INTENT_CRASH_ON_BLOCKED
                << OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT)) != 0) {
        call.flags |= OVERWORLD_ACTOR_WALK_POLICY_FLAG_CRASH_ON_BLOCKED;
    }
    call.stepFlags = OVERWORLD_ACTOR_WALK_STEP_VALIDATE;
    if (!OverworldWildSpawns_ReduceWalk(&call)) {
        return FALSE;
    }
    return OverworldWildSpawns_ExecuteWalkPolicy(
        (OverworldWildDirectionStepContext *)stepContext, &call);
}

static BOOL OverworldWildSpawns_IsValidLedgeLandingTile(FieldSystem *fieldSystem, int landingX, int landingY)
{
    /* The allowed-tile policy can permit a player tile. */
    return !IsMetatileBlockedAt(fieldSystem, landingX, landingY)
        && !OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, landingX, landingY);
}

static BOOL OverworldWildSpawns_IsPreviousTileLockedAt(
    OverworldWildSpawnState *state,
    int slot,
    int x,
    int y)
{
    return state != NULL
        && slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && state->movementPreviousTileLocked[slot]
        && state->movementPreviousTileX[slot] == x
        && state->movementPreviousTileY[slot] == y;
}

static BOOL OverworldWildSpawns_ShouldAvoidPreviousTileForResolvedProfile(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile)
{
    const OverworldWildBehaviorProfileData *lane =
        OverworldWildSpawns_GetControllerLane(
            profile,
            state->movementSpotStates[slot]);

    return lane->avoidPreviousTile == OW_WILD_BEHAVIOR_BOOL_YES
        || (OverworldWildSpawns_GetActiveConditionApplications(state, slot) != 0
        && profile->chillState == OW_WILD_BEHAVIOR_KIND_CHASE
        && profile->chillTarget != OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY);
}

static BOOL OverworldWildSpawns_IsAvoidedBacktrackStep(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u8 direction,
    int distance,
    BOOL avoidPreviousTile)
{
    int targetX;
    int targetY;

    if (!avoidPreviousTile || object == NULL) {
        return FALSE;
    }

    targetX = (int)OverworldWildSpawns_ObjectCurrentX(object)
        + OverworldWildSpawns_MovementDirectionDeltaX(direction) * distance;
    targetY = (int)OverworldWildSpawns_ObjectCurrentY(object)
        + OverworldWildSpawns_MovementDirectionDeltaY(direction) * distance;

    return OverworldWildSpawns_IsPreviousTileLockedAt(state, slot, targetX, targetY);
}

static OverworldWildDirectionStepResult __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_TryStartLedgeJumpCommand(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction,
    BOOL obstacleHopAllowed,
    BOOL probeOnly)
{
    OverworldWildSpawnState *state = stepContext->state;
    FieldSystem *fieldSystem = stepContext->fieldSystem;
    LocalMapObject *object = stepContext->object;
    const OverworldWildBehaviorProfile *profile = stepContext->profile;
    int slot = stepContext->slot;
    int dx;
    int dy;
    int objectX;
    int objectY;
    int ledgeX;
    int ledgeY;
    int landingX;
    int landingY;
    int ledgeIndex;
    u8 obstacleHop;

    /* Neither a ledge nor a blocked obstacle may start a diagonal Hop. */
    if (direction > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
        return OW_WILD_DIRECTION_STEP_BUSY;
    }
    dx = OverworldWildSpawns_MovementDirectionDeltaX(direction);
    dy = OverworldWildSpawns_MovementDirectionDeltaY(direction);

    objectX = object->xCurr;
    objectY = object->yCurr;
    if (probeOnly) {
        objectX += dx;
        objectY += dy;
    }
    ledgeX = objectX + dx;
    ledgeY = objectY + dy;
    if (ledgeX < 0 || ledgeY < 0) {
        return OW_WILD_DIRECTION_STEP_BUSY;
    }

    ledgeIndex = GetMetatileBehaviorAt(fieldSystem, ledgeX, ledgeY)
        - OW_WILD_TILE_LEDGE_EAST;
    obstacleHop = (u32)ledgeIndex > 3;
    if (obstacleHop) {
        const OverworldWildBehaviorProfileData *lane =
            OverworldWildSpawns_GetControllerLane(
                profile, state->movementSpotStates[slot]);

        if (lane->hopMinDistance != 2
            || lane->hopAllowVerticalObstacles != OW_WILD_BEHAVIOR_BOOL_YES
            /* A blocked turn still belongs to the Walk turn planner. */
            || !obstacleHopAllowed) {
            return OW_WILD_DIRECTION_STEP_BUSY;
        }
        if (!IsMetatileBlockedAt(fieldSystem, ledgeX, ledgeY)
            && !OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(
                fieldSystem, object, ledgeX, ledgeY)) {
            return OW_WILD_DIRECTION_STEP_BUSY;
        }
    }

    landingX = objectX + dx * 2;
    landingY = objectY + dy * 2;
    if (!obstacleHop
        && (stepContext->jumpLevel == OW_WILD_BEHAVIOR_JUMP_LEVEL_NONE
            || (ledgeIndex ^ (direction ^ (2 | (direction >> 1))))
                > (stepContext->jumpLevel >= OW_WILD_BEHAVIOR_JUMP_LEVEL_BOTH))) {
        return OW_WILD_DIRECTION_STEP_BLOCKED;
    }
    if (!OverworldWildSpawns_IsBehaviorAllowedMovementTile(
            fieldSystem,
            stepContext->allowedTile,
            landingX,
            landingY)
        || (!obstacleHop
            && OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, ledgeX, ledgeY))
        || !OverworldWildSpawns_IsValidLedgeLandingTile(fieldSystem, landingX, landingY)
        || (!probeOnly && stepContext->avoidPreviousTile
            && OverworldWildSpawns_IsPreviousTileLockedAt(
                state, slot, landingX, landingY))) {
        return OW_WILD_DIRECTION_STEP_BLOCKED;
    }
    if (probeOnly) {
        goto hop_started;
    }

    /* Ledges and opted-in blocked-terrain Walks cross one tile. Stage the
     * distinct kind before the shared jump so the terminal boundary can
     * finish a two-tile movement without a staged target. */
    state->movementStagedHopPending[slot] =
        OW_WILD_SPAWNER_STAGED_HOP_LEDGE_PENDING + (obstacleHop << 2);
    if (!OverworldWildSpawns_StartPreparedCustomJumpCommand(
        state,
        fieldSystem,
        slot,
        object,
        direction,
        OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP,
        landingX,
        landingY,
        profile,
        FALSE)) {
        state->movementStagedHopPending[slot] = FALSE;
        return OW_WILD_DIRECTION_STEP_BLOCKED;
    }
hop_started:
    return OW_WILD_DIRECTION_STEP_STARTED + obstacleHop;
}

static OverworldWildDirectionStepResult __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_TryStartSingleDirectionMovementStep(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction,
    BOOL obstacleHopAllowed)
{
    OverworldWildDirectionStepResult ledgeResult;
    u32 walkCommand;
    u32 movementCommand;
    int targetX;
    int targetY;
    u8 locomotion;

    /* The only caller has checked the context, slot, object, profile and
     * active movement before building this step. Recheck actor lifetime. */
    if (!stepContext->state->spawns[stepContext->slot].active) {
        return OW_WILD_DIRECTION_STEP_BUSY;
    }

    ledgeResult = OverworldWildSpawns_TryStartLedgeJumpCommand(
        stepContext, direction, obstacleHopAllowed, FALSE);
    if (ledgeResult >= OW_WILD_DIRECTION_STEP_STARTED) {
        if (ledgeResult == OW_WILD_DIRECTION_STEP_OBSTACLE_HOP_STARTED) {
            /* Crossing one blocked tile does not end Sprint's Walk run. */
            OverworldWildSpawns_ClearObjectFlags(
                stepContext->object, MAPOBJECTFLAG_UNK7);
        } else {
            OverworldWildSpawns_ClearWalkMovementState(
                stepContext->state,
                stepContext->slot,
                stepContext->object);
        }
        return OW_WILD_DIRECTION_STEP_STARTED;
    }
    if (ledgeResult == OW_WILD_DIRECTION_STEP_BLOCKED) {
        sOverworldWildMovementDiagnosticDirectionBlocked = TRUE;
        return ledgeResult;
    }

    locomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
        stepContext->primitives,
        stepContext->state->movementSpotStates[stepContext->slot]);
    if (locomotion != OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) {
        targetX = OverworldWildSpawns_ObjectCurrentX(stepContext->object)
            + OverworldWildSpawns_MovementDirectionDeltaX(direction);
        targetY = OverworldWildSpawns_ObjectCurrentY(stepContext->object)
            + OverworldWildSpawns_MovementDirectionDeltaY(direction);
        if (!OverworldWildSpawns_IsBehaviorAllowedMovementTile(
                stepContext->fieldSystem,
                stepContext->allowedTile,
                targetX,
                targetY)) {
            sOverworldWildMovementDiagnosticDirectionBlocked = TRUE;
            return OW_WILD_DIRECTION_STEP_BLOCKED;
        }
    }
    if (OverworldWildSpawns_TryStartCanopyEntryHop(
            stepContext,
            direction)) {
        return OW_WILD_DIRECTION_STEP_STARTED;
    }
    if (locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) {
        return OverworldWildSpawns_TryStartAcceleratedWalkStep(
                   stepContext,
                   direction)
            ? OW_WILD_DIRECTION_STEP_STARTED
            : OW_WILD_DIRECTION_STEP_BLOCKED;
    }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK
    sOverworldWildMovementDiagnosticDirectionBlocked =
        OverworldWildSpawns_IsPlayerTile(
            stepContext->fieldSystem,
            targetX,
            targetY)
        || (direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            && (MapObject_IsMovementDirectionBlocked(
                    stepContext->object,
                    direction)
                & ~OW_WILD_MAP_OBJECT_BLOCKED_BY_OBJECT) != 0);
    if (sOverworldWildMovementDiagnosticDirectionBlocked) {
        return OW_WILD_DIRECTION_STEP_BLOCKED;
    }
#endif

    OverworldWildSpawns_ClearWalkMovementState(
        stepContext->state,
        stepContext->slot,
        stepContext->object);
    walkCommand = locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        ? OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_1_COMMAND
        : OverworldWildSpawns_GetMovementWalkCommandForSpeed(
            OverworldWildSpawns_GetControllerLane(
                stepContext->profile,
                stepContext->state->movementSpotStates[stepContext->slot])
                ->chillSpeed);
    movementCommand = MapObject_MovementCommandFromDirection(
        direction,
        walkCommand);
    OverworldWildSpawns_StartMovementCommandForSlot(
        stepContext->state,
        stepContext->slot,
        stepContext->object,
        movementCommand,
        direction,
        OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP);
    return OW_WILD_DIRECTION_STEP_STARTED;
}

#if !OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND
static OverworldWildDirectionStepResult OverworldWildSpawns_TryStartSingleDirectionLookCommand(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction)
{
    u32 movementCommand;
    int targetX;
    int targetY;

    if (stepContext == NULL
        || stepContext->state == NULL
        || stepContext->slot >= OW_WILD_MAX_SPAWNS
        || !stepContext->state->spawns[stepContext->slot].active
        || stepContext->object == NULL
        || MapObject_IsSingleMovementActive(stepContext->object)) {
        return OW_WILD_DIRECTION_STEP_BUSY;
    }

    targetX = OverworldWildSpawns_ObjectCurrentX(stepContext->object)
        + OverworldWildSpawns_MovementDirectionDeltaX(direction);
    targetY = OverworldWildSpawns_ObjectCurrentY(stepContext->object)
        + OverworldWildSpawns_MovementDirectionDeltaY(direction);
    if (!OverworldWildSpawns_IsBehaviorAllowedMovementTile(
            stepContext->fieldSystem,
            stepContext->allowedTile,
            targetX,
            targetY)) {
        sOverworldWildMovementDiagnosticDirectionBlocked = TRUE;
        return OW_WILD_DIRECTION_STEP_BLOCKED;
    }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK
    sOverworldWildMovementDiagnosticDirectionBlocked =
        MapObject_IsMovementDirectionBlocked(
            stepContext->object,
            direction);
    if (sOverworldWildMovementDiagnosticDirectionBlocked) {
        return OW_WILD_DIRECTION_STEP_BLOCKED;
    }
#endif

    movementCommand = MapObject_MovementCommandFromDirection(
        direction,
        OW_WILD_SPAWNER_MOVEMENT_LOOK_UP_COMMAND);
    MapObject_StartMovementCommand(stepContext->object, movementCommand);
    MapObject_SetSingleMovementActive(stepContext->object);
    sOverworldWildMovementDiagnosticLookIssued = TRUE;
    return OW_WILD_DIRECTION_STEP_STARTED;
}
#endif

static BOOL OverworldWildSpawns_TryStartBlockedWalkStopSkid(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorProfileData *lane,
    u8 locomotion,
    BOOL lockDirection,
    BOOL blockedAnyDirection,
    int directionCount)
{
    if (lockDirection
        || locomotion != OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        || (!blockedAnyDirection && directionCount != 0)
        || !OW_WILD_BEHAVIOR_STOPS_WITH_SKID(lane->tilesBeforeTurnSkid)) {
        return FALSE;
    }
    return OverworldWildSpawns_TryStartWalkStopSkid(
        state,
        slot,
        profile,
        lane);
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_TryStartSpawnerMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const u8 *directions,
    int directionCount,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    int pass;
    BOOL deferredBacktrack = FALSE;
    BOOL blockedAnyDirection = FALSE;
    LocalMapObject *object;
    OverworldWildBehaviorProfile fallbackProfile;
    OverworldWildBehaviorPrimitives fallbackPrimitives;
    OverworldWildDirectionStepContext stepContext;
    OverworldActorPolicyView policy;
    const OverworldWildBehaviorProfileData *lane;
    u8 locomotion;
    u8 movementTarget;
    u8 lockedDirection;
    int preferredDirectionIndex = -1;
    int attemptCount;
    BOOL lockDirection;
    BOOL avoidPreviousTile;

    if (profile == NULL || primitives == NULL) {
        OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
            state,
            slot,
            &fallbackProfile,
            &fallbackPrimitives);
        if (profile == NULL) {
            profile = &fallbackProfile;
        }
        if (primitives == NULL) {
            primitives = &fallbackPrimitives;
        }
    }

    object = state->spawns[slot].object;
    if (object == NULL || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }
    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        return FALSE;
    }
    if (policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE
        && policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED) {
        /* The shared motion still owns facing during its settling pause.
         * A rejected early AI retry must not fall through to turn_around. */
        return FALSE;
    }
    if (policy.walkMomentum.skidRemaining != 0) {
        /* The pre-skid decision owns the maneuver until it finishes. */
        return FALSE;
    }

    locomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
        primitives,
        state->movementSpotStates[slot]);
    if (locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND) {
        goto turn_around;
    }
    lane = OverworldWildSpawns_GetControllerLane(
        profile,
        state->movementSpotStates[slot]);
    lockDirection = locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        && (lane->walkOptions & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) != 0;
    lockedDirection = policy.walkMomentum.direction;
    attemptCount = lockDirection
            && lockedDirection <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
        ? 1
        : directionCount;
    movementTarget = OverworldWildSpawns_GetCurrentMovementTarget(
        primitives,
        state->movementSpotStates[slot]);
    if (!lockDirection
        && directionCount > 1
        && locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        && (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY
            || movementTarget == OW_WILD_BEHAVIOR_TARGET_NONE)) {
        preferredDirectionIndex = 0;
        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY
            && state->movementLastDistances[slot] == OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP
            && state->movementLastDirections[slot]
                <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
            preferredDirectionIndex =
                OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
                    ->chooseWanderDirection(
                    directions,
                    directionCount,
                    state->movementLastDirections[slot],
                    lane->wanderStraightChance);
        }
    }

    avoidPreviousTile = OverworldWildSpawns_ShouldAvoidPreviousTileForResolvedProfile(
        state,
        slot,
        profile);
    stepContext.state = state;
    stepContext.fieldSystem = fieldSystem;
    stepContext.object = object;
    stepContext.profile = profile;
    stepContext.primitives = primitives;
    stepContext.slot = (u8)slot;
    stepContext.allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        state->movementSpotStates[slot]);
    stepContext.jumpLevel = profile->jumpLevel;
    stepContext.avoidPreviousTile = (u8)avoidPreviousTile;

    for (pass = 0; pass < 2; pass++) {
        int j;

        if (pass != 0 && !deferredBacktrack) {
            break;
        }

        for (j = 0; j < attemptCount; j++) {
            OverworldWildDirectionStepResult stepResult;
            int directionIndex = j;
            u8 direction;
            BOOL avoidedBacktrack;

            if (!lockDirection && preferredDirectionIndex > 0) {
                directionIndex = j == 0
                    ? preferredDirectionIndex
                    : j == preferredDirectionIndex ? 0 : j;
            }
            direction = lockDirection
                    && lockedDirection <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
                ? lockedDirection
                : directions[directionIndex];
            if (preferredDirectionIndex < -1
                && direction == state->movementLastDirections[slot]) {
                continue;
            }
            avoidedBacktrack = OverworldWildSpawns_IsAvoidedBacktrackStep(
                state,
                slot,
                object,
                direction,
                1,
                avoidPreviousTile);

            if (avoidedBacktrack) {
                if (pass == 0) {
                    deferredBacktrack = TRUE;
                    blockedAnyDirection = TRUE;
                    continue;
                }
            } else if (pass != 0) {
                continue;
            }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND
            stepResult = OverworldWildSpawns_TryStartSingleDirectionMovementStep(
                &stepContext,
                direction,
                policy.walkMomentum.speed == 0
                    || policy.walkMomentum.direction == direction);
#else
            stepResult = OverworldWildSpawns_TryStartSingleDirectionLookCommand(
                &stepContext,
                direction);
#endif
            if (stepResult == OW_WILD_DIRECTION_STEP_STARTED) {
                return TRUE;
            }
            if (stepResult == OW_WILD_DIRECTION_STEP_BUSY) {
                return FALSE;
            }
            if (lockDirection
                && lockedDirection <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
                return OverworldWildSpawns_HandleLockedWalkCrash(
                    &stepContext,
                    direction);
            }
            blockedAnyDirection = TRUE;
        }
    }

    if (OverworldWildSpawns_TryStartBlockedWalkStopSkid(
            state,
            slot,
            profile,
            lane,
            locomotion,
            lockDirection,
            blockedAnyDirection,
            directionCount)) {
        return TRUE;
    }
    if (!lockDirection
        && blockedAnyDirection
        && preferredDirectionIndex == -1) {
        goto turn_around;
    }
    if (blockedAnyDirection) {
        state->movementCooldowns[slot] =
            OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
    }
    return FALSE;

turn_around:
    if (directions != NULL && directionCount > 0) {
        OverworldWildSpawns_SetObjectFacing(object, directions[0]);
    }
    return TRUE;
}

static void OverworldWildSpawns_AddChaseFallbackDirection(
    u8 *directions,
    int *directionCount,
    u8 direction)
{
    int i;

    for (i = 0; i < *directionCount; i++) {
        if (directions[i] == direction) {
            return;
        }
    }

    if (*directionCount >= OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS) {
        return;
    }

    directions[*directionCount] = direction;
    (*directionCount)++;
}

static void OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(
    u8 *directions,
    int *directionCount)
{
    u8 primaryDirection;

    if (*directionCount <= 0) {
        return;
    }

    primaryDirection = directions[0];
    if (primaryDirection < OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT) {
        OverworldWildSpawns_AddChaseFallbackDirection(
            directions,
            directionCount,
            OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT);
        OverworldWildSpawns_AddChaseFallbackDirection(
            directions,
            directionCount,
            OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT);
    } else {
        OverworldWildSpawns_AddChaseFallbackDirection(
            directions,
            directionCount,
            OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP);
        OverworldWildSpawns_AddChaseFallbackDirection(
            directions,
            directionCount,
            OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN);
    }
    OverworldWildSpawns_AddChaseFallbackDirection(
        directions,
        directionCount,
        primaryDirection ^ 1);
}

static inline void OverworldWildSpawns_ApplyWalkPursuitDirectionInertia(
    OverworldWildSpawnState *state,
    int slot,
    u8 *directions,
    int directionCount)
{
    u8 direction = state->movementLastDirections[slot];

    if (directionCount > 1
        && state->movementLastDistances[slot] == OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP
        && directions[1] == direction) {
        directions[1] = directions[0];
        directions[0] = direction;
    }
}

static void OverworldWildSpawns_AppendFleeFallbackDirections(
    u8 *directions,
    int *directionCount,
    int fleeDx,
    int fleeDy)
{
    static const u8 baseDirections[]
        __attribute__((section(".overworld_wild_spawns_prefix_bss"))) = {
        OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP,
        OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT,
        OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN,
        OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT,
    };
    int start;

    if (directions == NULL
        || directionCount == NULL
        || *directionCount >= 4
        || (fleeDx == 0 && fleeDy == 0)) {
        return;
    }
    if (*directionCount < 0) {
        *directionCount = 0;
    }

    start = gf_rand() % 4;
    while (*directionCount < 4) {
        int bestDirection = -1;
        int bestScore = 0;
        int i;

        for (i = 0; i < 4; i++) {
            u8 direction = baseDirections[(start + i) % 4];
            int score;
            int j;

            for (j = 0; j < *directionCount; j++) {
                if (directions[j] == direction) {
                    break;
                }
            }
            if (j < *directionCount) {
                continue;
            }

            score = OverworldWildSpawns_MovementDirectionDeltaX(direction)
                    * fleeDx
                + OverworldWildSpawns_MovementDirectionDeltaY(direction)
                    * fleeDy;
            if (bestDirection < 0 || score > bestScore) {
                bestDirection = direction;
                bestScore = score;
            }
        }

        directions[*directionCount] = (u8)bestDirection;
        (*directionCount)++;
    }
}

static int OverworldWildSpawns_BuildRandomDirections(u8 *directions)
{
    int start = gf_rand() & 3;
    int i;

    for (i = 0; i < 4; i++) {
        directions[i] = (u8)((start + i) & 3);
    }
    return 4;
}

static BOOL OverworldWildSpawns_IsCirclePlayerTargetTile(
    int x,
    int y,
    int playerX,
    int playerY,
    u8 radius)
{
    return OverworldWildSpawns_Max(
            OverworldWildSpawns_Abs(x - playerX),
            OverworldWildSpawns_Abs(y - playerY))
        == radius;
}

static BOOL OverworldWildSpawns_TryGetCirclePlayerMovementTarget(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 spotState,
    int objectX,
    int objectY,
    int playerX,
    int playerY,
    int *targetX,
    int *targetY)
{
    int selectedX[2] = {0, 0};
    int selectedY[2] = {0, 0};
    int selectedScore[2] = {0x7FFF, 0x7FFF};
    int selectedCount[2] = {0, 0};
    int dx;
    int dy;
    const OverworldWildBehaviorProfileData *lane;
    u16 allowedTile;
    u8 radius;
    BOOL currentIsTarget;
    BOOL continueWhenArrived;
    BOOL avoidPreviousTile;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || targetX == NULL
        || targetY == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }

    lane = OverworldWildSpawns_GetControllerLane(profile, spotState);
    allowedTile = lane->chillAllowedTerrainMask;
    radius = lane->circleRadius;
    currentIsTarget = OverworldWildSpawns_IsCirclePlayerTargetTile(
        objectX,
        objectY,
        playerX,
        playerY,
        radius);
    continueWhenArrived = lane->continueWhenArrived == OW_WILD_BEHAVIOR_BOOL_YES;
    avoidPreviousTile = lane->avoidPreviousTile == OW_WILD_BEHAVIOR_BOOL_YES;
    if (currentIsTarget && !continueWhenArrived) {
        *targetX = objectX;
        *targetY = objectY;
        return TRUE;
    }

    for (dy = -(int)radius; dy <= (int)radius; dy++) {
        int dxStep = (dy == -(int)radius || dy == (int)radius)
            ? 1
            : 2 * (int)radius;

        for (dx = -(int)radius; dx <= (int)radius; dx += dxStep) {
            int candidateX;
            int candidateY;
            int score;
            BOOL isPreviousTile;
            int selection;

            candidateX = playerX + dx;
            candidateY = playerY + dy;
            if (candidateX == objectX && candidateY == objectY) {
                continue;
            }
            if (!OverworldWildSpawns_IsBehaviorAllowedMovementTile(
                    fieldSystem,
                    allowedTile,
                    candidateX,
                    candidateY)) {
                continue;
            }

            score = OverworldWildSpawns_Max(
                OverworldWildSpawns_Abs(candidateX - objectX),
                OverworldWildSpawns_Abs(candidateY - objectY));
            isPreviousTile = avoidPreviousTile
                && OverworldWildSpawns_IsPreviousTileLockedAt(
                    state,
                    slot,
                    candidateX,
                    candidateY);
            selection = isPreviousTile != FALSE;
            selectedCount[selection]++;
            if (score < selectedScore[selection]
                || (score == selectedScore[selection]
                    && (gf_rand() % selectedCount[selection]) == 0)) {
                selectedScore[selection] = score;
                selectedX[selection] = candidateX;
                selectedY[selection] = candidateY;
            }
        }
    }

    if (selectedCount[0] != 0) {
        *targetX = selectedX[0];
        *targetY = selectedY[0];
        return TRUE;
    }
    if (selectedCount[1] != 0) {
        *targetX = selectedX[1];
        *targetY = selectedY[1];
        return TRUE;
    }
    if (currentIsTarget) {
        *targetX = objectX;
        *targetY = objectY;
        return TRUE;
    }

    return FALSE;
}

static inline BOOL __attribute__((always_inline))
OverworldWildSpawns_TryGetConditionTargetPosition(
    OverworldWildSpawnState *state,
    int slot,
    int *targetX,
    int *targetY)
{
    OverworldWildBehaviorConditionRuntime *conditions;

    conditions = OverworldWildSpawns_GetConditionRuntime(state);
    if (conditions == NULL) {
        return FALSE;
    }
    if ((conditions->targetValidMask & (1u << slot)) == 0) {
        return FALSE;
    }
    *targetX = conditions->targetX[slot];
    *targetY = conditions->targetY[slot];
    return TRUE;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    OverworldWildOverlayRuntimeState *runtime;
    FieldSystem *fieldSystem;
    LocalMapObject *targetObject;
    int objectX;
    int objectY;
    int playerX;
    int playerY;
    int impactX;
    int impactY;
    int dx;
    int dy;
    u8 movementTarget;
    u8 throwTarget;
    u8 targetSlot;
    u8 throwDistance;
    u8 directions[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];
    int directionCount;
    BOOL movementStarted;
    const OverworldWildBehaviorProfile *movementProfile = profile;
    OverworldWildBehaviorProfile boostedProfile;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || profile == NULL
        || primitives == NULL
        || state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        return FALSE;
    }

    /* A conditional Owner intent uses this dispatcher for every locomotion.
     * The routing mask only selects actors that need frame-owned idle work;
     * it must not reject an explicitly dispatched ordinary Walk. */

    fieldSystem = state->movementFieldSystem;
    if (fieldSystem == NULL || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }
    runtime = OW_WILD_RUNTIME(state);
    throwTarget = runtime->throwState.targets[slot];
    if (OverworldWildSpawns_GetActiveConditionApplications(state, slot) == 0
        && state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE
        && throwTarget == OW_WILD_SPAWNER_THROW_TARGET_NONE) {
        return FALSE;
    }
    movementTarget = state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_MOVE
        ? OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER
        : primitives->chillTarget;
    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    playerX = state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_MOVE
        ? state->movementSpawnRunTargetX[slot]
        : GetPlayerXCoord(fieldSystem->playerAvatar);
    playerY = state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_MOVE
        ? state->movementSpawnRunTargetY[slot]
        : GetPlayerYCoord(fieldSystem->playerAvatar);
    if (state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE
        && throwTarget == OW_WILD_SPAWNER_THROW_TARGET_NONE) {
        (void)OverworldWildSpawns_TryGetConditionTargetPosition(
            state, slot, &playerX, &playerY);
    }
    impactX = playerX;
    impactY = playerY;
    targetObject = object;
    targetSlot = (u8)slot;
    if (throwTarget != OW_WILD_SPAWNER_THROW_TARGET_NONE) {
        targetSlot = OW_WILD_SPAWNER_THROW_TARGET_DECODE(throwTarget);
        if (targetSlot >= OW_WILD_MAX_SPAWNS
            || !state->spawns[targetSlot].active
            || state->spawns[targetSlot].object == NULL
            || !OverworldWildSpawns_IsCurrentSpawnObject(
                fieldSystem,
                &state->spawns[targetSlot])) {
            OverworldWildSpawns_ClearThrowStateForSlot(state, slot);
            return FALSE;
        }
        targetObject = state->spawns[targetSlot].object;
        if ((throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) == 0) {
            if (!OverworldWildSpawns_IsValidPickupThrowTarget(state, slot, targetSlot)
                || state->movementEmoteTimers[slot] == 0) {
                OverworldWildSpawns_ClearThrowStateForSlot(state, slot);
                return FALSE;
            }
            state->movementEmoteTimers[slot]--;
            movementTarget = OW_WILD_BEHAVIOR_TARGET_TOWARD_PLAYER;
        }
    }
    if (throwTarget == OW_WILD_SPAWNER_THROW_TARGET_NONE
        && movementTarget == OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER) {
        OverworldWildSpawns_TryGetCirclePlayerMovementTarget(
            state,
            fieldSystem,
            slot,
            profile,
            OW_WILD_SPAWNER_SPOT_STATE_CHILL,
            objectX,
            objectY,
            playerX,
            playerY,
            &playerX,
            &playerY);
    } else if (throwTarget == OW_WILD_SPAWNER_THROW_TARGET_NONE) {
        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER) {
            if (!OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    &playerX,
                    &playerY)) {
                return FALSE;
            }
        }
    } else if ((throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) == 0) {
        playerX = OverworldWildSpawns_ObjectCurrentX(targetObject);
        playerY = OverworldWildSpawns_ObjectCurrentY(targetObject);
    }

    dx = playerX - objectX;
    dy = playerY - objectY;
    if (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) {
        /* Throw is a capability layered over any Routine. Once the target is
         * carried, approach a valid throwing line instead of inheriting the
         * Routine's target (for example Random Nearby). */
        movementTarget = OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE;
        if (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG) {
            impactX = runtime->movementCustomJumpTargetX[slot];
            impactY = runtime->movementCustomJumpTargetY[slot];
        }
        dx = impactX - objectX;
        dy = impactY - objectY;
        throwDistance = (u8)(OverworldWildSpawns_Abs(dx) + OverworldWildSpawns_Abs(dy));
        directions[0] = dx != 0
            ? OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT + (dx > 0)
            : (dy > 0);
        if (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG) {
            MapObject_ClearSingleMovementActive(targetObject);
            if (throwDistance != 0
                && OverworldWildSpawns_StartPreparedCustomJumpCommand(
                    state,
                    fieldSystem,
                    targetSlot,
                    targetObject,
                    directions[0],
                    throwDistance,
                    impactX,
                    impactY,
                    profile,
                    TRUE)) {
                runtime->spawnPresentations.lastKnownX[targetSlot] = (s16)impactX;
                runtime->spawnPresentations.lastKnownY[targetSlot] = (s16)impactY;
                runtime->throwState.targets[slot] = OW_WILD_SPAWNER_THROW_TARGET_NONE;
                runtime->throwState.carrierMask &= ~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
                state->movementCooldowns[slot] = OW_WILD_SPAWNER_THROW_RECOVERY_FRAMES;
                OverworldWildSpawns_StartTiredEmote(state, slot);
            } else {
                OverworldWildSpawns_ReleaseThrowTargetAtCurrentTile(
                    state,
                    slot,
                    targetSlot,
                    targetObject);
                state->movementCooldowns[slot] = OW_WILD_SPAWNER_THROW_RECOVERY_FRAMES;
            }
            return TRUE;
        }
        if ((dx == 0 || dy == 0)
            && throwDistance <= profile->hopMaxDistance) {
            runtime->movementCustomJumpTargetX[slot] = (s16)impactX;
            runtime->movementCustomJumpTargetY[slot] = (s16)impactY;
            runtime->throwState.targets[slot] =
                throwTarget | OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG;
            OverworldWildSpawns_SetObjectFacing(object, directions[0]);
            OverworldWildSpawns_ShowBubble(object, OW_WILD_SPAWNER_BUBBLE_ID_ANGRY);
            PlayCry(
                state->spawns[slot].species,
                state->spawns[slot].form);
            state->movementCooldowns[slot] = OW_WILD_SPAWNER_THROW_WINDUP_FRAMES;
            return TRUE;
        }
        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_PLAYER_CARDINAL_LINE) {
            if (OverworldWildSpawns_Abs(dx) > OverworldWildSpawns_Abs(dy)) {
                playerX = impactX + (dx < 0
                    ? profile->hopMaxDistance
                    : -profile->hopMaxDistance);
                playerY = impactY;
            } else {
                playerX = impactX;
                playerY = impactY + (dy < 0
                    ? profile->hopMaxDistance
                    : -profile->hopMaxDistance);
            }
        }
        dx = playerX - objectX;
        dy = playerY - objectY;
    }
    if (movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER) {
        dx = -dx;
        dy = -dy;
    } else if (movementTarget == OW_WILD_BEHAVIOR_TARGET_NONE) {
        dx = 0;
        dy = 0;
    }

    if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY) {
        directionCount = OverworldWildSpawns_BuildRandomDirections(directions);
    } else {
        directionCount = OverworldWildSpawns_BuildDirectedDirections(dx, dy, directions);
    }
    if (throwTarget != OW_WILD_SPAWNER_THROW_TARGET_NONE
        && (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) == 0) {
        if (directionCount == 0
            || (primitives->chillLocomotion != OW_WILD_BEHAVIOR_LOCOMOTION_HOP
                && OverworldWildSpawns_Max(
                    OverworldWildSpawns_Abs(dx),
                    OverworldWildSpawns_Abs(dy)) <= OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP)) {
            if (!OverworldWildSpawns_IsStablePickupThrowTarget(state, slot, targetSlot)) {
                state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
                return TRUE;
            }
            if (!OverworldWildSpawns_StartCarriedThrowTarget(
                    state,
                    slot,
                    targetSlot,
                    targetObject)) {
                OverworldWildSpawns_ClearThrowStateForSlot(state, slot);
                state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
            }
            return TRUE;
        }
    }
    if (directionCount == 0
        && primitives->chillLocomotion != OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) {
        return FALSE;
    }
    if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY) {
        dx = 0;
        dy = 0;
    } else if (movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER) {
        OverworldWildSpawns_AppendFleeFallbackDirections(
            directions,
            &directionCount,
            dx,
            dy);
    } else {
        if (primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) {
            OverworldWildSpawns_ApplyWalkPursuitDirectionInertia(
                state,
                slot,
                directions,
                directionCount);
        }
        OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(
            directions,
            &directionCount);
    }
    if (throwTarget == OW_WILD_SPAWNER_THROW_TARGET_NONE
        && profile->chaseBoostDistance != 0
        && profile->chaseBoostSpeed != 0
        && profile->chillState == OW_WILD_BEHAVIOR_KIND_CHASE
        && movementTarget != OW_WILD_BEHAVIOR_TARGET_NONE
        && movementTarget != OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY
        && movementTarget != OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER
        && OverworldWildSpawns_Max(
            OverworldWildSpawns_Abs(dx),
            OverworldWildSpawns_Abs(dy)) >= profile->chaseBoostDistance) {
        boostedProfile = *profile;
        if (boostedProfile.chillSpeed > profile->chaseBoostSpeed) {
            boostedProfile.chillSpeed = profile->chaseBoostSpeed;
        }
        movementProfile = &boostedProfile;
    }

    if (primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        && movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY
        && OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
            movementProfile->owner.hopAllowNonCardinal)) {
        return OverworldWildSpawns_TryStartRandomBehaviorHopCommand(
            state,
            fieldSystem,
            slot,
            movementProfile);
    }

    if (primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        || (primitives->chillLocomotion
                == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
            && OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                movementProfile->owner.hopAllowNonCardinal))) {
        if (throwTarget != OW_WILD_SPAWNER_THROW_TARGET_NONE
            && (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) == 0) {
            sOverworldWildCollisionIgnoredObject = targetObject;
            movementTarget = OW_WILD_BEHAVIOR_TARGET_NONE;
        }
        movementStarted = OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(
            state,
            fieldSystem,
            slot,
            movementProfile,
            dx,
            dy,
            directions,
            directionCount,
            movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER
                ? OW_WILD_HELPER_HOP_PLAN_FLEE
                : (movementTarget != OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY
                        && movementTarget != OW_WILD_BEHAVIOR_TARGET_NONE
                    ? OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY
                    : OW_WILD_HELPER_HOP_PLAN_DIRECT));
        if (!movementStarted
            && movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER) {
            movementStarted = OverworldWildSpawns_TryStartRandomBehaviorHopCommand(
                state,
                fieldSystem,
                slot,
                movementProfile);
        }
        sOverworldWildCollisionIgnoredObject = NULL;
        return movementStarted;
    }

    if (primitives->chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) {
        return OverworldWildSpawns_TryStartTeleportMovementCommand(
            state,
            fieldSystem,
            slot,
            directions,
            directionCount,
            movementProfile,
            primitives);
    }

    return OverworldWildSpawns_TryStartSpawnerMovementCommand(
        state,
        fieldSystem,
        slot,
        directions,
        directionCount,
        movementProfile,
        primitives);
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_TryStartPlannedTeleport(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u16 allowedTile,
    u8 targetMode,
    const u8 *directions,
    u8 directionCount,
    int desiredX,
    int desiredY,
    u32 directionRandom,
    u32 distanceRandom)
{
    const OverworldWildBehaviorProfileData *lane;
    OverworldActorTeleportPlanCall planCall;
    OverworldActorMotionRequestCall request;
    OverworldWildTeleportWorldContext world;
    OverworldMotionPlan plan;
    OverworldMotionSample immediateSample;
    OverworldWildOverlayRuntimeState *runtime;
    LocalMapObject *object;
    u16 appliedThrough;
    u8 phase;
    int objectX;
    int objectY;

    if (state == NULL || fieldSystem == NULL || profile == NULL
        || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    object = state->spawns[slot].object;
    if (object == NULL
        || MapObject_IsSingleMovementActive(object)
        || OverworldWildSpawns_IsMovementSlotInProgress(state, slot)) {
        return FALSE;
    }

    if (targetMode == OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT
        && state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE
        && fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }
    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    lane = OverworldWildSpawns_GetControllerLane(
        profile,
        state->movementSpotStates[slot]);
    memset(&world, 0, sizeof(world));
    world.state = state;
    world.fieldSystem = fieldSystem;
    world.object = object;
    world.slot = slot;
    world.allowedTile = allowedTile;
    world.facePlayer = targetMode
            == OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT
        && state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE;
    if (world.facePlayer) {
        world.playerX = (s16)GetPlayerXCoord(fieldSystem->playerAvatar);
        world.playerY = (s16)GetPlayerYCoord(fieldSystem->playerAvatar);
    }
    memset(&planCall, 0, sizeof(planCall));
    planCall.lane = lane;
    planCall.directions = directions;
    planCall.classify = OverworldWildSpawns_ClassifyTeleportCandidate;
    planCall.world = &world;
    planCall.directionRandom = directionRandom;
    planCall.distanceRandom = distanceRandom;
    planCall.desiredX = (s16)desiredX;
    planCall.desiredY = (s16)desiredY;
    planCall.targetMode = targetMode;
    planCall.directionCount = directionCount;
    planCall.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    planCall.flags =
        OVERWORLD_ACTOR_TELEPORT_FLAG_RESERVED_STOPS_SEARCH;
    memset(&request, 0, sizeof(request));
    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT;
    request.actorSlot = (u8)slot;
    request.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());
    request.startX = (s16)objectX;
    request.startY = (s16)objectY;
    request.startBaseY = (s32)object->posVec[1];
    request.plan = &plan;
    request.teleportPlan = &planCall;
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request)
            != OVERWORLD_ACTOR_RESULT_OK
        || request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return FALSE;
    }
    OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
    OverworldWildSpawns_ClearCustomJump(state, slot);
    runtime = OW_WILD_RUNTIME(state);
    /* ClearCustomJump can only cancel the previous adapter identity. Publish
     * this accepted Teleport identity after that local cleanup. */
    runtime->movementMotionIdentities[slot] = request.motionIdentity;
    runtime->movementCustomJumpActive[slot] = FALSE;
    runtime->movementCustomJumpStartX[slot] = (s16)objectX;
    runtime->movementCustomJumpStartY[slot] = (s16)objectY;
    runtime->movementCustomJumpTargetX[slot] = plan.targetX;
    runtime->movementCustomJumpTargetY[slot] = plan.targetY;
    runtime->movementCustomJumpStartBaseY[slot] = plan.startBaseY;
    runtime->movementCustomJumpTargetBaseY[slot] = plan.targetBaseY;
    runtime->movementCustomMotionModes[slot] =
        plan.visibilityPolicy == OVERWORLD_MOTION_VISIBILITY_FLICKER
        ? OW_WILD_CUSTOM_MOTION_TELEPORT_FLICKER
        : OW_WILD_CUSTOM_MOTION_TELEPORT_HIDDEN;
    OverworldWildSpawns_SetPreviousTile(state, slot, objectX, objectY);
    state->movementPendingDirections[slot] = plan.direction;
    state->movementPendingDistances[slot] = plan.distance;
    state->movementCooldowns[slot] = plan.pauseFrames;
    state->movementTeleportHidden[slot] = TRUE;
    state->movementTeleportHiddenSteps[slot] = 0;
    state->movementTeleportFlickerTimers[slot] = 0;
    state->movementTeleportVisiblePause[slot] = FALSE;
    OverworldWildSpawns_SetObjectFacing(object, plan.facing);
    OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);
    OverworldWildSpawns_SetObjectFlags(object, MAPOBJECTFLAG_UNK20);
    state->movementBattleSettleFrames = 0;
    OverworldWildSpawns_SetMovementSlotInProgress(state, slot);
    OverworldWildSpawns_ApplyTeleportHiddenVisual(state, slot, object, TRUE);
    if (plan.duration == 0
        && OverworldWildSpawns_AcknowledgeSharedMotion(
            slot, 0, 0, &immediateSample, &phase)
        && phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        appliedThrough = (immediateSample.flags
                & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0
            ? immediateSample.lastPathAdvance
            : 0;
        OverworldWildSpawns_ApplyTeleportHiddenVisual(
            state, slot, object, immediateSample.visible);
        (void)OverworldWildSpawns_CompleteTeleportMovement(
            state, slot, object, appliedThrough);
    }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
    sOverworldWildMovementDiagnosticDirectionBlocked = FALSE;
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartChillTeleportMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile)
{
    LocalMapObject *object;
    u32 directionRandom = 0;
    u32 distanceRandom = 0;
    int desiredX = 0;
    int desiredY = 0;
    u16 allowedTile;
    u8 targetMode;
    u8 movementTarget;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    movementTarget = state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? profile->tired.chillTarget
        : profile->chillTarget;
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        state->movementSpotStates[slot]);
    if (movementTarget == OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER) {
        if (!OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
                state,
                fieldSystem,
                slot,
                profile,
                &desiredX,
                &desiredY)
            || (object != NULL
                && desiredX == object->xCurr
                && desiredY == object->yCurr)) {
            state->movementCooldowns[slot] = OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
            return FALSE;
        }
        targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT;
    } else {
        targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_CHILL;
    }
    if ((OverworldWildSpawns_ReduceRole(
                slot,
                (u32)OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                    << OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                    << OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT
                    << OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST,
                OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL
                    | OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED)
            & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0) {
        state->movementCooldowns[slot] =
            OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
        return FALSE;
    }
    if (targetMode == OVERWORLD_ACTOR_TELEPORT_TARGET_CHILL) {
        directionRandom = gf_rand();
        distanceRandom = gf_rand();
    }

    if (!OverworldWildSpawns_TryStartPlannedTeleport(
            state,
            fieldSystem,
            slot,
            profile,
            allowedTile,
            targetMode,
            NULL,
            0,
            desiredX,
            desiredY,
            directionRandom,
            distanceRandom)) {
        state->movementCooldowns[slot] = OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
        sOverworldWildMovementDiagnosticDirectionBlocked = TRUE;
        return FALSE;
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartTeleportMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const u8 *directions,
    int directionCount,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    LocalMapObject *object;
    int desiredX = 0;
    int desiredY = 0;
    u16 allowedTile;
    u8 targetMode;

    if (state == NULL
        || fieldSystem == NULL
        || primitives == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        state->movementSpotStates[slot]);
    if (state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE
        && primitives->chillTarget == OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER
        && OverworldWildSpawns_IsTeleportOnPlayerAdjacentTile(
            state,
            fieldSystem,
            slot,
            object,
            profile)) {
        sOverworldWildMovementDiagnosticDirectionBlocked = FALSE;
        OverworldWildSpawns_StartTeleportVisibleCooldown(state, slot, object, profile);
        return TRUE;
    }

    if (state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_MOVE) {
        desiredX = state->movementSpawnRunTargetX[slot];
        desiredY = state->movementSpawnRunTargetY[slot];
        targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT;
    } else if (primitives->chillTarget == OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER) {
        if (!OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
                state,
                fieldSystem,
                slot,
                profile,
                &desiredX,
                &desiredY)
            || (object != NULL
                && desiredX == object->xCurr
                && desiredY == object->yCurr)) {
            state->movementCooldowns[slot] = OW_WILD_SPAWNER_TELEPORT_FAIL_COOLDOWN_FRAMES;
            sOverworldWildMovementDiagnosticDirectionBlocked = TRUE;
            return FALSE;
        }
        targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_ADJACENT;
    } else {
        targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_DIRECTIONAL;
    }

    if ((OverworldWildSpawns_ReduceRole(
                slot,
                (u32)OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                    << OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                    << OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT
                    << OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST,
                OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL
                    | OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED)
            & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0) {
        state->movementCooldowns[slot] =
            OW_WILD_SPAWNER_TELEPORT_FAIL_COOLDOWN_FRAMES;
        return FALSE;
    }

    if (OverworldWildSpawns_TryStartPlannedTeleport(
            state,
            fieldSystem,
            slot,
            profile,
            allowedTile,
            targetMode,
            directions,
            (u8)directionCount,
            desiredX,
            desiredY,
            0,
            0)) {
        return TRUE;
    }

    state->movementCooldowns[slot] = OW_WILD_SPAWNER_TELEPORT_FAIL_COOLDOWN_FRAMES;
    return FALSE;
}

static void OverworldWildSpawns_PlayMovementCrashFeedback(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    const OverworldWildBehaviorProfileData *lane;

    if (profile == NULL) {
        return;
    }
    lane = OverworldWildSpawns_GetControllerLane(profile, spotState);
    if (OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(lane->walkOptions)
        == OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT) {
        PlaySE(OW_WILD_SPAWNER_WALK_CRASH_SE);
    }
}

#ifndef DISABLE_FOLLOWER_POKEMON
static BOOL OverworldWildSpawns_IsActiveMapObjectAt(FieldSystem *fieldSystem, LocalMapObject *object, int x, int y)
{
    return OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)
        && (object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && (int)OverworldWildSpawns_ObjectCurrentX(object) == x
        && (int)OverworldWildSpawns_ObjectCurrentY(object) == y;
}
#endif

static BOOL OverworldWildSpawns_IsMovementCrashBattleTarget(FieldSystem *fieldSystem, int x, int y)
{
#ifndef DISABLE_FOLLOWER_POKEMON
    MapObjectMan *mapObjectMan;
    LocalMapObject *objects;
    LocalMapObject *followerObject;
    u32 i;
#endif

    if (fieldSystem == NULL || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }

    if (x == GetPlayerXCoord(fieldSystem->playerAvatar)
        && y == GetPlayerYCoord(fieldSystem->playerAvatar)) {
        return TRUE;
    }

#ifndef DISABLE_FOLLOWER_POKEMON
    followerObject = fieldSystem->followMon.mapObject;
    if (OverworldWildSpawns_IsActiveMapObjectAt(fieldSystem, followerObject, x, y)) {
        return TRUE;
    }

    mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (mapObjectMan == NULL || mapObjectMan->objects == NULL) {
        return FALSE;
    }

    objects = mapObjectMan->objects;
    for (i = 0; i < mapObjectMan->object_count; i++) {
        LocalMapObject *object = &objects[i];

        if (object->id == OW_WILD_FOLLOWER_OBJECT_ID
            && OverworldWildSpawns_IsActiveMapObjectAt(fieldSystem, object, x, y)) {
            return TRUE;
        }
    }
#endif

    return FALSE;
}

static BOOL OverworldWildSpawns_TryPrimeBattleForSlotWithoutMovementReset(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || OverworldWildSpawns_HasPendingBattle(state)
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }

    state->pendingPersonality = state->spawns[slot].personality;
    state->pendingSpecies = state->spawns[slot].species | (state->spawns[slot].form << OW_WILD_FORM_SHIFT);
    state->pendingLevel = state->spawns[slot].level;
    state->pendingShiny = state->spawns[slot].shiny;
    state->pendingSlot = slot;
    state->pendingMapGeneration = state->mapGeneration;
    state->pendingEncounterGeneration = state->spawns[slot].encounterGeneration;
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL,
        OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);
    state->battleGraceSteps = 0;
    state->justSpawned = FALSE;
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartBattleForMovementCrashAtTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    int targetX,
    int targetY,
    const OverworldWildBehaviorProfile *profile)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL) {
        return FALSE;
    }

    if (OverworldWildSpawns_GetActiveConditionApplications(state, slot) == 0
        || profile->battleTrigger != OW_WILD_BEHAVIOR_BATTLE_TRIGGER_MOVEMENT_CRASH) {
        return FALSE;
    }

    if (!OverworldWildSpawns_IsMovementCrashBattleTarget(fieldSystem, targetX, targetY)) {
        return FALSE;
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    if (sOverworldWildMovementFrameTaskExecuting) {
        if (!OverworldWildSpawns_TryPrimeBattleForSlotWithoutMovementReset(state, fieldSystem, slot)) {
            return FALSE;
        }
        if (!OverworldWildSpawns_RequestBattleScript(fieldSystem, state, slot)) {
            OverworldWildSpawns_ResetPendingBattle(state);
            return FALSE;
        }
        return TRUE;
    }
#endif

    return OverworldWildSpawns_TryStartBattleForSlotOrQueue(state, fieldSystem, slot);
}

static BOOL OverworldWildSpawns_TryStartBattleForMovementCrash(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    const OverworldWildBehaviorProfile *profile)
{
    int targetX;
    int targetY;

    if (object == NULL) {
        return FALSE;
    }

    targetX = (int)OverworldWildSpawns_ObjectCurrentX(object) + OverworldWildSpawns_MovementDirectionDeltaX(direction);
    targetY = (int)OverworldWildSpawns_ObjectCurrentY(object) + OverworldWildSpawns_MovementDirectionDeltaY(direction);
    return OverworldWildSpawns_TryStartBattleForMovementCrashAtTile(
        state,
        fieldSystem,
        slot,
        object,
        targetX,
        targetY,
        profile);
}

static void OverworldWildSpawns_ResetWalkAfterCrash(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
}

static BOOL OverworldWildSpawns_TryStartMovementCrashBattleImpact(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction)
{
    OverworldWildSpawnState *state = stepContext->state;
    int slot = stepContext->slot;

    if (!OverworldWildSpawns_TryStartBattleForMovementCrash(
            state,
            stepContext->fieldSystem,
            slot,
            stepContext->object,
            direction,
            stepContext->profile)) {
        return FALSE;
    }

    OverworldWildSpawns_PlayMovementCrashFeedback(
        stepContext->profile,
        state->movementSpotStates[slot]);
    OverworldWildSpawns_ResetWalkAfterCrash(
        state,
        slot,
        stepContext->object);
    return TRUE;
}

static void OverworldWildSpawns_EndMovementCrash(
    const OverworldWildDirectionStepContext *stepContext)
{
    OverworldWildSpawnState *state = stepContext->state;
    int slot = stepContext->slot;
    u8 spotState = state->movementSpotStates[slot];

    OverworldWildSpawns_PlayMovementCrashFeedback(
        stepContext->profile,
        spotState);
    OverworldWildSpawns_StartMovementCrashShake(
        state,
        slot,
        stepContext->object,
        OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FRAMES);
    OverworldWildSpawns_ResetWalkAfterCrash(
        state,
        slot,
        stepContext->object);
    if (spotState == OW_WILD_SPAWNER_SPOT_STATE_CHILL
        || spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FRAMES;
        return;
    }
    OverworldWildSpawns_StartTiredEmoteWithProfile(
        state,
        slot,
        stepContext->profile,
        stepContext->primitives);
    if (state->movementCooldowns[slot] < state->movementCrashShakeTimers[slot]) {
        state->movementCooldowns[slot] = state->movementCrashShakeTimers[slot];
    }
}

static BOOL OverworldWildSpawns_HandleLockedWalkCrash(
    const OverworldWildDirectionStepContext *stepContext,
    u8 direction)
{
    u32 roleResult;
    u8 roleFlags = 0;
    int targetX;
    int targetY;

    if (stepContext == NULL
        || stepContext->state == NULL
        || stepContext->slot >= OW_WILD_MAX_SPAWNS
        || !stepContext->state->spawns[stepContext->slot].active
        || stepContext->object == NULL
        || stepContext->profile == NULL
        || stepContext->primitives == NULL) {
        return FALSE;
    }
    if (stepContext->state->movementCrashShakeTimers[stepContext->slot] != 0) {
        return TRUE;
    }

    targetX = OverworldWildSpawns_ObjectCurrentX(stepContext->object)
        + OverworldWildSpawns_MovementDirectionDeltaX(direction);
    targetY = OverworldWildSpawns_ObjectCurrentY(stepContext->object)
        + OverworldWildSpawns_MovementDirectionDeltaY(direction);
    if (OverworldWildSpawns_GetActiveConditionApplications(
            stepContext->state, stepContext->slot) != 0
        && stepContext->profile->battleTrigger
            == OW_WILD_BEHAVIOR_BATTLE_TRIGGER_MOVEMENT_CRASH) {
        roleFlags |= OVERWORLD_ROLE_CONTROLLER_INPUT_CRASH_CAN_BATTLE;
    }
    if (OverworldWildSpawns_IsMovementCrashBattleTarget(
            stepContext->fieldSystem, targetX, targetY)) {
        roleFlags |= OVERWORLD_ROLE_CONTROLLER_INPUT_BLOCKED_BY_ACTOR;
    }
    roleResult = OverworldWildSpawns_ReduceRole(
        stepContext->slot,
        OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED
            | OVERWORLD_ROLE_CONTROLLER_INTENT_WALK
                << OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT
            | (u32)direction
                << OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT
            | (u32)direction
                << OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT,
        roleFlags | OVERWORLD_ROLE_CONTROLLER_INPUT_RAM);
    if ((u8)roleResult
            == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH_BATTLE
        && OverworldWildSpawns_TryStartMovementCrashBattleImpact(
            stepContext, direction)) {
        return TRUE;
    }
    if ((u8)roleResult
            == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH
        || (u8)roleResult
            == OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH_BATTLE) {
        OverworldWildSpawns_EndMovementCrash(stepContext);
    }
    return TRUE;
}

static void OverworldWildSpawns_StartTiredCooldown(OverworldWildSpawnState *state, int slot)
{
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ClearWalkMovementState(state, slot, state->spawns[slot].object);
    state->movementEmoteTimers[slot] = 0;
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    state->movementEmoteDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    state->movementEmoteJumpsRemaining[slot] = 0;
    state->movementCooldowns[slot] = OW_WILD_SPAWNER_TIRED_WANDER_PAUSE_FRAMES;
#if OW_WILD_SPAWNER_TIRED_PLAY_COOLDOWN_SE
    PlaySE(OW_WILD_SPAWNER_TIRED_EMOTE_SE);
#endif
}

#if OW_WILD_SPAWNER_TIRED_USE_FOLLOWER_BUBBLE
static u8 OverworldWildSpawns_GetTiredBubbleId(void)
{
#if OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE
    u8 bubbleId = sOverworldWildTiredBubbleIdProbe;

    if (bubbleId < OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN
        || bubbleId > OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MAX) {
        bubbleId = OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN;
    }

    sOverworldWildTiredBubbleIdProbe = bubbleId + 1;
    if (sOverworldWildTiredBubbleIdProbe > OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MAX) {
        sOverworldWildTiredBubbleIdProbe = OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN;
    }

    return bubbleId;
#else
    return OW_WILD_SPAWNER_TIRED_BUBBLE_ID;
#endif
}

static u8 OverworldWildSpawns_GetTiredBubbleIdForState(u8 tiredState)
{
    switch (tiredState) {
    case OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE:
        return OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET;
    case OW_WILD_BEHAVIOR_KIND_ASLEEP:
        return OW_WILD_SPAWNER_BUBBLE_ID_SLEEP;
    case OW_WILD_BEHAVIOR_KIND_IDLE:
    case OW_WILD_BEHAVIOR_KIND_NO_VISUAL:
        return OW_WILD_SPAWNER_BUBBLE_ID_NONE;
    case OW_WILD_BEHAVIOR_KIND_NONE:
    default:
        return OverworldWildSpawns_GetTiredBubbleId();
    }
}
#endif

static u8 OverworldWildSpawns_GetRestFrameCount(const OverworldWildBehaviorProfile *profile)
{
    if (profile == NULL
        || profile->tiredState == OW_WILD_BEHAVIOR_KIND_NONE
        || profile->stamina == 0
        || profile->restTime == 0) {
        return 0;
    }

    return profile->restTime
        - (profile->restTime == OW_WILD_SPAWNER_ASLEEP_REST_TIMER);
}

static void OverworldWildSpawns_StartTiredEmoteWithProfile(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profileOverride,
    const OverworldWildBehaviorPrimitives *primitivesOverride)
{
#if OW_WILD_SPAWNER_TIRED_USE_FOLLOWER_BUBBLE
    FieldSystem *fieldSystem;
#endif
    LocalMapObject *object;
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u8 restFrames;
#if OW_WILD_SPAWNER_TIRED_USE_FOLLOWER_BUBBLE
    u8 bubbleId;
#endif

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active) {
        return;
    }

    object = state->spawns[slot].object;
    if (profileOverride != NULL && primitivesOverride != NULL) {
        profile = *profileOverride;
        primitives = *primitivesOverride;
    } else {
        OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
            state, slot, &profile, &primitives);
    }
    if (primitives.chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) {
        OverworldWildSpawns_RevealTeleportObject(state, slot, object);
    }
    if (profile.tiredState == OW_WILD_BEHAVIOR_KIND_NONE
        && profile.tiredSpeed == 0) {
        profile.tiredState = OW_WILD_BEHAVIOR_KIND_TIRED_EMOTE;
        profile.stamina = 1;
        profile.restTime = OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME;
    }
    if (OverworldWildSpawns_BehaviorUsesAsleep(profile.tiredState)
        && object != NULL
        && MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }
    restFrames =
        OverworldWildSpawns_BehaviorUsesAsleep(profile.tiredState)
            && profile.restTime == 0
        ? OW_WILD_SPAWNER_ASLEEP_REST_TIMER
        : OverworldWildSpawns_GetRestFrameCount(&profile);
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_TIRED;
    OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
    state->movementEmoteTimers[slot] = restFrames;
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    state->movementEmoteDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    state->movementEmoteJumpsRemaining[slot] = 0;
    state->movementEmoteEndStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    state->movementEmoteBubbleIds[slot] = OW_WILD_SPAWNER_BUBBLE_ID_NONE;
    state->movementEmoteShowBubbleEachJump[slot] = FALSE;
    state->movementCooldowns[slot] = OW_WILD_SPAWNER_TIRED_WANDER_PAUSE_FRAMES;

    if (OverworldWildSpawns_BehaviorKindUsesMovement(profile.tiredState)) {
        if (restFrames == 0 || object == NULL) {
            OverworldWildSpawns_StartTiredCooldown(state, slot);
            return;
        }
        if (MapObject_IsSingleMovementActive(object)) {
            MapObject_ClearSingleMovementActive(object);
        }
        state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
        return;
    }

    if (restFrames == 0
        || profile.tiredState == OW_WILD_BEHAVIOR_KIND_NONE
        || object == NULL
        || MapObject_IsSingleMovementActive(object)) {
        OverworldWildSpawns_StartTiredCooldown(state, slot);
        return;
    }

    if (profile.tiredState == OW_WILD_BEHAVIOR_KIND_NO_VISUAL
        || profile.tiredState == OW_WILD_BEHAVIOR_KIND_IDLE) {
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
        return;
    }

#if OW_WILD_SPAWNER_TIRED_USE_FOLLOWER_BUBBLE
    fieldSystem = state->movementFieldSystem;
    if (OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)) {
        bubbleId = OverworldWildSpawns_GetTiredBubbleIdForState(profile.tiredState);
#if OW_WILD_SPAWNER_TIRED_USE_DIRECT_BUBBLE_CREATOR
        ov01_02203A48(object, bubbleId);
#if OW_WILD_SPAWNER_TIRED_STOP_BUBBLE_SE
        StopSE(SEQ_SE_DP_DECIDE);
#endif
#else
        ov01_02203AB4(fieldSystem, object, bubbleId);
#endif
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
        return;
    }
#endif

    MapObject_StartMovementCommand(object, OW_WILD_SPAWNER_TIRED_EMOTE_COMMAND);
    MapObject_SetSingleMovementActive(object);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
}

static void OverworldWildSpawns_StartTiredEmote(OverworldWildSpawnState *state, int slot)
{
    OverworldWildSpawns_StartTiredEmoteWithProfile(state, slot, NULL, NULL);
}

static inline BOOL __attribute__((always_inline)) OverworldWildSpawns_HandleFinishedWalkMovement(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives,
    BOOL stopAfterCommit)
{
    const OverworldWildBehaviorProfileData *lane;
    OverworldActorPolicyView policy;
    OverworldWildDirectionStepContext stepContext;
    OverworldActorWalkPolicyCall call;
    BOOL handled;
    BOOL sharedWalk;
    u8 spotState = state->movementSpotStates[slot];

    lane = OverworldWildSpawns_GetControllerLane(
        profile,
        spotState);
    if (object == NULL) {
        /* Spawn teardown can finish the command after its object is gone.
         * Do not pass that stale completion into skid callbacks. */
        OverworldWildSpawns_ClearWalkMovementState(state, slot, NULL);
        return TRUE;
    }
    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        return FALSE;
    }
    sharedWalk = OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
        == OW_WILD_CUSTOM_MOTION_WALK;
    handled = policy.pendingSkid != 0;
    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_COMMIT);
    call.lane = lane;
    call.direction = state->movementLastDirections[slot];
    call.distance = state->movementLastDistances[slot];
    call.laneState = spotState;
    /* This callback only runs after an accepted Walk finishes. The policy
     * must commit that Walk before it can advance the Movement Chain. The
     * custom presentation mode only chooses the terminal adapter; it is not
     * the semantic source of whether a Walk was active. */
    call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED
        | OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    if (sharedWalk) {
        if (!OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
                ->terminalWalk(
                    &call,
                    OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS,
                    policy.pendingLastPathAdvance,
                    OW_WILD_RUNTIME(state)->movementMotionIdentities[slot])
            || (call.reserved[OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX]
                    != OVERWORLD_MOTION_PHASE_IDLE
                && call.reserved[
                    OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX]
                    != OVERWORLD_MOTION_PHASE_SETTLING)) {
            return TRUE;
        }
        /* Keep the shared mode live until the actor has reduced and committed
         * the terminal Walk. A retry must not fall into the legacy reducer. */
        OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
    } else if (!OverworldWildSpawns_ReduceWalk(&call)) {
        return FALSE;
    }
    if (stopAfterCommit) {
        return FALSE;
    }
    /* The terminal transaction is complete. Build the engine-only step
     * adapter afterward so GCC can reuse the policy stack. */
    stepContext.state = state;
    stepContext.fieldSystem = state->movementFieldSystem;
    stepContext.object = object;
    stepContext.profile = profile;
    stepContext.primitives = primitives;
    stepContext.slot = (u8)slot;
    stepContext.allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        spotState);
    (void)OverworldWildSpawns_ExecuteWalkPolicy(&stepContext, &call);
    if (handled
        && OverworldActorPolicy_Inspect((u8)slot, &policy)
        && policy.walkMomentum.skidRemaining == 0) {
        OverworldWildSpawns_CommitDeferredChainMovementPause(
            state,
            slot,
            profile);
    }
    /* Handled skid completions return before Movement Chain accounting. */
    return handled;
}

static void __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_CommitDeferredChainMovementPause(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile)
{
    OverworldActorPolicyView policy;
    OverworldActorWalkPolicyCall policyCall;
    u32 roleResult;
    u8 encodedAction;
    u8 pauseAction;
    u8 pauseTicks;
    u8 outcome;

    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        return;
    }
    encodedAction = policy.chainPauseAction;
    if ((encodedAction & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) == 0) {
        return;
    }

    /* A movement can finish at the engine boundary while its shared actor
     * motion is still settling. Keep the chain action pending until that
     * motion returns control; starting now would be rejected as already
     * active and would silently discard the authored action. */
    if (!OverworldWildSpawns_IsChainActionReady(slot)) {
        state->movementCooldowns[slot] = 1;
        return;
    }
    /* A running reposition owns this byte as its grid position. Its high
     * bit is not a second deferred action. Resume the same action after a
     * settling/retry boundary instead of decoding the grid as action 16+. */
    if ((encodedAction & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)
        == OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER) {
        if ((policy.chainStepsRemaining & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) != 0) {
            OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
        }
        return;
    }

    if (!OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(
            state, slot, profile)) {
        return;
    }

    pauseAction = policy.chainPauseAction & 0x7F;
    pauseTicks = policy.chainPauseTicks;

    roleResult = OverworldWildSpawns_ReduceRole(
        slot,
        (u32)OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                << OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT
            | OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                << OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT
            | OVERWORLD_ROLE_CONTROLLER_EVENT_TERMINAL_COMMIT,
        OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED
            | (u32)pauseAction << OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT
            | (u32)pauseTicks << OW_WILD_SPAWNER_ROLE_RESULT_TICKS_SHIFT);
    if ((roleResult & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0
        || (u8)roleResult != OVERWORLD_ROLE_CONTROLLER_TERMINAL_CHAIN) {
        return;
    }
    pauseAction = (u8)(roleResult >> OW_WILD_SPAWNER_ROLE_RESULT_FLAGS_SHIFT);
    pauseTicks = (u8)(roleResult >> OW_WILD_SPAWNER_ROLE_RESULT_TICKS_SHIFT);
    OverworldWildSpawns_InitPolicyCall(
        &policyCall,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING);
    if (!OverworldWildSpawns_ReduceWalk(&policyCall)
        || policyCall.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED) {
        return;
    }
    state->movementCooldowns[slot] = pauseTicks;
    outcome = OverworldWildSpawns_TryStartChainPauseAction(
            state,
            slot,
            profile,
            pauseAction,
            pauseTicks,
            policy.walkMomentum.direction);
    if (outcome == OW_WILD_CHAIN_STARTED) {
        state->movementCooldowns[slot] = 0;
    } else if (outcome == OW_WILD_CHAIN_RETRY) {
        OverworldWildSpawns_InitPolicyCall(
            &policyCall,
            slot,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_PUT_PENDING);
        policyCall.chainAction = encodedAction & 0x7F;
        policyCall.chainTicks = policy.chainPauseTicks;
        (void)OverworldWildSpawns_ReduceWalk(&policyCall);
        state->movementCooldowns[slot] = 1;
    }
}

static BOOL
OverworldWildSpawns_TryStartWalkStopSkid(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorProfileData *lane)
{
    OverworldWildDirectionStepContext stepContext;
    OverworldActorWalkPolicyCall call;
    LocalMapObject *object = state->spawns[slot].object;

    stepContext.state = state;
    stepContext.fieldSystem = state->movementFieldSystem;
    stepContext.object = object;
    stepContext.profile = profile;
    stepContext.slot = (u8)slot;
    stepContext.allowedTile = lane->chillAllowedTerrainMask;
    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_INPUT);
    call.lane = lane;
    call.direction = OW_WILD_WALK_DIRECTION_NONE;
    call.laneState = state->movementSpotStates[slot];
    (void)OverworldWildSpawns_ReduceWalk(&call);
    if (call.decision == OVERWORLD_ACTOR_WALK_POLICY_TRY_STEP) {
        call.stepFlags |= OVERWORLD_ACTOR_WALK_STEP_PLANNED_STOP_SKID;
        call.reserved[OVERWORLD_ACTOR_WALK_POLICY_STOP_SKID_TILES_INDEX] =
            call.distance;
    }
    (void)OverworldWildSpawns_ExecuteWalkPolicy(&stepContext, &call);
    return call.startResult == OVERWORLD_ACTOR_WALK_POLICY_START_ACCEPTED;
}

static void __attribute__((optimize("Os"))) OverworldWildSpawns_ApplyUniversalChainMovementPause(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    OverworldActorWalkPolicyCall call;
    u8 spotState = state->movementSpotStates[slot];
    const OverworldWildBehaviorProfileData *lane =
        OverworldWildSpawns_GetControllerLane(profile, spotState);
    u8 locomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
        primitives,
        spotState);

    OverworldWildSpawns_InitPolicyCall(
        &call,
        slot,
        OVERWORLD_ACTOR_WALK_POLICY_CHAIN_COMMIT);
    call.lane = lane;
    call.locomotion = locomotion;
    call.laneState = spotState;
    call.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    if (!OverworldWildSpawns_ReduceWalk(&call)
        || call.decision != OVERWORLD_ACTOR_WALK_POLICY_CONSUMED) {
        return;
    }
    if (call.chainAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE) {
        state->movementCooldowns[slot] = call.chainTicks;
        call.operation = OVERWORLD_ACTOR_WALK_POLICY_CHAIN_TAKE_PENDING;
        call.decision = OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
        (void)OverworldWildSpawns_ReduceWalk(&call);
        return;
    }

    OverworldWildSpawns_CommitDeferredChainMovementPause(
        state,
        slot,
        profile);
}

static void __attribute__((optimize("Os"))) OverworldWildSpawns_HandleFinishedMovementCommand(OverworldWildSpawnState *state, int slot)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    const OverworldWildBehaviorProfileData *lane;
    OverworldActorPolicyView policy;
    OverworldWildChainRepositionResult repositionResult;
    LocalMapObject *object;
    u16 slotMask;
    BOOL pendingDistanceDespawn;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    slotMask = OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    object = state->spawns[slot].object;
    if (object == NULL) {
        return;
    }
    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        return;
    }
    if ((policy.chainStepsRemaining
            & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) == 0) {
        OverworldWildSpawns_RecordFinishedMovementHistory(state, slot);
    }
    if ((runtime->throwState.targetMask & slotMask) != 0
        && state->movementActorControlModes[slot]
            == OW_WILD_ACTOR_CONTROL_HELD) {
        runtime->throwState.targetMask &= ~slotMask;
        if (runtime->movementCustomJumpPrepActive[slot]) {
            (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
                object,
                OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND);
        }
        if (runtime->movementCustomJumpActive[slot]
            || runtime->movementCustomJumpPrepActive[slot]) {
            OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
        }
        runtime->movementCustomJumpPrepActive[slot] = FALSE;
        OverworldWildSpawns_ReleaseHeldActorControl(state, slot);
        OverworldWildSpawns_SetObjectLandingTile(
            state->movementFieldSystem,
            object,
            OverworldWildSpawns_ObjectCurrentX(object),
            OverworldWildSpawns_ObjectCurrentY(object));
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH | MAPOBJECTFLAG_UNK18);
        if (OverworldWildSpawns_IsObjectOnPlayerTile(state->movementFieldSystem, object)) {
            if (OverworldWildSpawns_TryStartBattleForSlotOrQueue(
                    state,
                    state->movementFieldSystem,
                    slot)) {
                return;
            }
        }
        return;
    }

    /* A reservation owns the carrier's active loop until pickup or expiry. */
    if (runtime->throwState.targets[slot] != OW_WILD_SPAWNER_THROW_TARGET_NONE) {
        return;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state,
        slot,
        &profile,
        &primitives);
    pendingDistanceDespawn =
        (runtime->spawnPresentations.distanceDespawnPendingMask & slotMask) != 0;
    if ((policy.chainStepsRemaining
            & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) != 0) {
        if (pendingDistanceDespawn) {
            goto request_distance_despawn;
        }
        if (!OverworldWildSpawns_IsChainActionReady(slot)) {
            return;
        }
        if (!OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(
                state, slot, &profile)) {
            return;
        }
        (void)OverworldWildSpawns_RunChainReposition(
            state,
            slot,
            &profile,
            policy.chainStepsRemaining,
            &repositionResult);

        if (!OverworldWildSpawns_ApplyChainRepositionResult(
                slot, &repositionResult)) {
            return;
        }
        if (repositionResult.outcome == OW_WILD_CHAIN_ABORT) {
            state->movementCooldowns[slot] = policy.chainPauseTicks;
        }
        return;
    }
    if (OverworldWildSpawns_HandleFinishedWalkMovement(
            state,
            slot,
            object,
            &profile,
            &primitives,
            pendingDistanceDespawn)) {
        return;
    }
    if (pendingDistanceDespawn) {
        goto request_distance_despawn;
    }
    lane = OverworldWildSpawns_GetControllerLane(
        &profile,
        state->movementSpotStates[slot]);
    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        if (OverworldWildSpawns_GetActiveConditionApplications(state, slot) != 0
            && primitives.chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT
            && state->movementTeleportHidden[slot]
            && state->movementTeleportHiddenSteps[slot] < 255) {
            state->movementTeleportHiddenSteps[slot]++;
        }
        if (primitives.chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
            && primitives.chillTarget == OW_WILD_BEHAVIOR_TARGET_TREE_TOP) {
            OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
            return;
        }
        if (primitives.chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
            /* Shared Motion already settles for lane->hopPause. Do not add
             * the authored interval a second time after MOTION_FINISHED. */
            state->movementCooldowns[slot] = 0;
        } else if (primitives.chillLocomotion
            == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) {
            state->movementCooldowns[slot] = lane->walkPause;
        }
        OverworldWildSpawns_ApplyUniversalChainMovementPause(
            state,
            slot,
            &profile,
            &primitives);
    } else if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        if (primitives.tiredLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
            && primitives.tiredTarget == OW_WILD_BEHAVIOR_TARGET_TREE_TOP) {
            OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
            return;
        }
        state->movementCooldowns[slot] =
            primitives.tiredLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
            ? 0
            : primitives.tiredLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
            ? lane->walkPause
            : OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
        OverworldWildSpawns_ApplyUniversalChainMovementPause(
            state,
            slot,
            &profile,
            &primitives);
    }
    return;

request_distance_despawn:
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE,
        0);
}

static BOOL OverworldWildSpawns_CompleteTeleportMovement(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u16 appliedThrough)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    u8 phase;

    OverworldWildSpawns_SetObjectLandingTile(
        state->movementFieldSystem,
        object,
        runtime->movementCustomJumpTargetX[slot],
        runtime->movementCustomJumpTargetY[slot]);
    OverworldWildSpawns_RevealTeleportObject(state, slot, object);
    if (!OverworldWildSpawns_AcknowledgeSharedMotion(
            slot,
            OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY,
            appliedThrough,
            NULL,
            &phase)
        || !OverworldWildSpawns_AcknowledgeSharedMotion(
            slot,
            OVERWORLD_ACTOR_BOUNDARY_ENGINE_END,
            0,
            NULL,
            &phase)) {
        goto teleport_commit_retry;
    }
    if (phase != OVERWORLD_MOTION_PHASE_IDLE
        && phase != OVERWORLD_MOTION_PHASE_SETTLING) {
        goto teleport_commit_retry;
    }
    OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
    OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
    state->movementTeleportVisiblePause[slot] =
        state->spawns[slot].active && state->movementCooldowns[slot] != 0;
    return TRUE;

teleport_commit_retry:
    /* Rebind clears seam ACKs. Keep the custom teleport schedulable so the
     * next frame can republish every final seam in the rebound field. */
    state->movementTeleportHidden[slot] = TRUE;
    OverworldWildSpawns_ApplyTeleportHiddenVisual(state, slot, object, TRUE);
    return FALSE;
}

static inline BOOL __attribute__((always_inline))
OverworldWildSpawns_TickTeleportMovementCommand(
    OverworldWildSpawnState *state,
    int slot,
    BOOL *finished)
{
    OverworldMotionSample sample;
    LocalMapObject *object;
    u16 appliedThrough = 0;
    u8 acknowledgements;
    u8 phase;

    if (!OverworldWildSpawns_IsTeleportMovementActive(state, slot)) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
        OverworldWildSpawns_ClearTeleportFlickerObject(state, slot, TRUE);
        OverworldWildSpawns_ClearCustomJump(state, slot);
        state->movementTeleportHidden[slot] = FALSE;
        state->movementTeleportHiddenSteps[slot] = 0;
        if (finished != NULL) {
            *finished = TRUE;
        }
        return TRUE;
    }

    if (!OverworldWildSpawns_AcknowledgeSharedMotion(
            slot,
            0,
            0,
            &sample,
            &phase)) {
        return TRUE;
    }
    appliedThrough = (sample.flags
            & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0
        ? sample.lastPathAdvance
        : 0;
    OverworldWildSpawns_ApplyTeleportHiddenVisual(
        state,
        slot,
        object,
        sample.visible);
    if (phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        acknowledgements = OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED;
        if ((sample.flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
            acknowledgements |= OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY;
        }
        if (!OverworldWildSpawns_AcknowledgeSharedMotion(
                slot,
                acknowledgements,
                appliedThrough,
                NULL,
                &phase)) {
            return TRUE;
        }
    }
    if (phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        return TRUE;
    }

    if (!OverworldWildSpawns_CompleteTeleportMovement(
            state,
            slot,
            object,
            appliedThrough)) {
        return TRUE;
    }
    if (finished != NULL) {
        *finished = TRUE;
    }
    return TRUE;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_TryStartChillWanderCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives)
{
    const OverworldWildBehaviorProfileData *lane;
    u8 directions[OW_WILD_SPAWNER_UNTANGLE_MAX_DIRECTIONS];
    int directionCount;
    u8 locomotion;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || profile == NULL
        || primitives == NULL
        || (state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_CHILL
            && state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_TIRED)) {
        return FALSE;
    }

    locomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
        primitives,
        state->movementSpotStates[slot]);
    lane = OverworldWildSpawns_GetControllerLane(
        profile,
        state->movementSpotStates[slot]);
    if (locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        if (OverworldWildSpawns_TryStartRandomBehaviorHopCommand(
                state,
                fieldSystem,
                slot,
                profile)) {
            return TRUE;
        }
    } else if (locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        && OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
            OverworldWildSpawns_GetControllerLane(
                profile,
                state->movementSpotStates[slot])->hopAllowNonCardinal)) {
        if (OverworldWildSpawns_TryStartRandomBehaviorHopCommand(
                state,
                fieldSystem,
                slot,
                profile)) {
            return TRUE;
        }
    } else {
        directionCount = OverworldWildSpawns_BuildRandomDirections(directions);
        if (directionCount > 0
            && OverworldWildSpawns_TryStartSpawnerMovementCommand(
                state,
                fieldSystem,
                slot,
                directions,
                directionCount,
                profile,
                primitives)) {
            return TRUE;
        }
    }

    /* A blocked choice must not replace the profile clock with a fixed wait.
     * The actor stays still, then retries when its own locomotion interval is
     * due. This also keeps short profiles independent of the slot count. */
    state->movementCooldowns[slot] = locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        ? lane->hopPause
        : locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        ? lane->walkPause
        : OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
    return FALSE;
}

static BOOL OverworldWildSpawns_TryBattleSettleRetry(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }
    if (!OverworldWildSpawns_HasQueuedBattle(state)) {
        return FALSE;
    }

    if (OverworldWildSpawns_TryStartQueuedBattle(state, fieldSystem)) {
        return TRUE;
    }
    return FALSE;
}

static BOOL OverworldWildSpawns_TryFrameBattleSettleRetry(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }

    if (OverworldWildSpawns_TryStartQueuedBattle(state, fieldSystem)) {
        return TRUE;
    }
    return FALSE;
}

static void OverworldWildSpawns_StartSpotEmoteCommand(LocalMapObject *object, u32 movementCommand)
{
    MapObject_StartMovementCommand(object, movementCommand);
    MapObject_SetSingleMovementActive(object);
}

static void OverworldWildSpawns_StartHopStartSoundSuppression(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] =
        OW_WILD_SPAWNER_HOP_START_SE_SUPPRESS_FRAMES;
    StopSE(OW_WILD_SPAWNER_HOP_START_SE);
}

static void OverworldWildSpawns_LoadAndPlayCanopyHopSE(
    OverworldWildSpawnState *state,
    u16 seqNo)
{
    (void)state;
    GF_Snd_LoadSeqEx(seqNo, NNS_SND_ARC_LOAD_ALL);
    PlaySE(seqNo);
}

static void OverworldWildSpawns_PlayCanopyHopSE(OverworldWildSpawnState *state)
{
    switch (gf_rand() % OW_WILD_SPAWNER_CANOPY_HOP_SOUND_VARIANTS) {
    case 0:
        OverworldWildSpawns_LoadAndPlayCanopyHopSE(
            state,
            OW_WILD_SPAWNER_CANOPY_HOP_RUSTLE_SE);
        break;
    case 1:
    default:
        OverworldWildSpawns_LoadAndPlayCanopyHopSE(
            state,
            OW_WILD_SPAWNER_CANOPY_HOP_BALLOON_SE);
        break;
    }
}

static void OverworldWildSpawns_TickHopStartSoundSuppression(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }
    if (OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] == 0) {
        return;
    }

    StopSE(OW_WILD_SPAWNER_HOP_START_SE);
    if (OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] != 0) {
        OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot]--;
    }
}

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND
static BOOL OverworldWildSpawns_UpdateSpawnerMovementCommandSuppressingHopStartSound(
    OverworldWildSpawnState *state,
    LocalMapObject *object,
    int slot)
{
    BOOL suppress;
    BOOL objectWasVanished;
    BOOL commandFinished;

    if (state == NULL || object == NULL) {
        return FALSE;
    }

    suppress = slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] != 0;
    if (!suppress) {
        return OverworldWildSpawns_UpdateSpawnerMovementCommand(object);
    }

    objectWasVanished = (object->flags & BIT_VANISH) != 0;
    OverworldWildSpawns_SetObjectFlags(object, BIT_VANISH);
    commandFinished = OverworldWildSpawns_UpdateSpawnerMovementCommand(object);
    if (!objectWasVanished) {
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    }
    StopSE(OW_WILD_SPAWNER_HOP_START_SE);
    return commandFinished;
}
#endif

static BOOL OverworldWildSpawns_IsLookAroundEmoteStep(u8 emoteStep)
{
    return emoteStep >= OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_FIRST
        && emoteStep <= OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_RETURN;
}

static BOOL OverworldWildSpawns_StartNextSpotEmoteStep(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{
    u32 movementCommand;
    BOOL playJumpSound = FALSE;

    if (object == NULL || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }

    switch (state->movementEmoteSteps[slot]) {
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_PREP:
        movementCommand = OW_WILD_SPAWNER_SPOT_EMOTE_PARTNER_PREP_COMMAND;
        break;
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_JUMP:
        movementCommand = MapObject_MovementCommandFromDirection(
            state->movementEmoteDirections[slot],
            OW_WILD_SPAWNER_SPOT_EMOTE_JUMP_SITE_COMMAND);
        playJumpSound = TRUE;
        break;
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_FREEZE:
        movementCommand = OW_WILD_SPAWNER_SPOT_EMOTE_FREEZE_COMMAND;
        break;
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_RESTORE:
        movementCommand = OW_WILD_SPAWNER_SPOT_EMOTE_PARTNER_RESTORE_COMMAND;
        break;
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_FIRST:
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_SECOND:
    case OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_RETURN:
        movementCommand = MapObject_MovementCommandFromDirection(
            OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
                ->resolveLook(
                state->movementEmoteDirections[slot],
                state->movementEmoteSteps[slot]
                    - OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_FIRST,
                0,
                0),
            OW_WILD_SPAWNER_MOVEMENT_LOOK_UP_COMMAND);
        break;
    default:
        state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
        return FALSE;
    }

    OverworldWildSpawns_StartSpotEmoteCommand(object, movementCommand);
    if (state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_PREP) {
        OW_WILD_RUNTIME(state)->movementEmotePartnerPrepObjects[slot] = object;
    }
    if (playJumpSound) {
        if (OW_WILD_RUNTIME(state)->movementEmotePlayHopSound[slot]) {
            PlaySE(OW_WILD_SPAWNER_SPOT_EMOTE_SE);
        } else {
            OverworldWildSpawns_StartHopStartSoundSuppression(state, slot);
        }
    }
    state->movementEmoteSteps[slot]++;
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartPendingLookAroundEmoteStep(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    if (object == NULL
        || MapObject_IsSingleMovementActive(object)
        || state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !OverworldWildSpawns_IsLookAroundEmoteStep(
            state->movementEmoteSteps[slot])
        || OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy->resolveLook(
                state->movementEmoteDirections[slot],
                state->movementEmoteSteps[slot]
                    - OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_FIRST,
                state->movementEmoteJumpsRemaining[slot],
                state->movementEmoteTimers[slot]) < 0) {
        return FALSE;
    }

    if (state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_SECOND
        && (state->movementEmoteDirections[slot]
            & OW_WILD_SPAWNER_LOOK_PLAN_TWO_GLANCES) == 0) {
        state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_RETURN;
    }
    if (state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_RETURN) {
        state->movementEmoteJumpsRemaining[slot] = 0;
    }

    return OverworldWildSpawns_StartNextSpotEmoteStep(state, slot, object);
}

static u8 OverworldWildSpawns_GetAlertBubbleIdForProfile(const OverworldWildBehaviorProfile *profile)
{
    if (profile->alertEmote <= OW_WILD_SPAWNER_BUBBLE_ID_SLEEP) {
        return profile->alertEmote;
    }
    return OW_WILD_SPAWNER_BUBBLE_ID_NONE;
}

static void __attribute__((noinline)) OverworldWildSpawns_ShowBubble(LocalMapObject *object, u8 bubbleId)
{
    if (bubbleId == OW_WILD_SPAWNER_BUBBLE_ID_NONE) {
        return;
    }

    ov01_02203A48(object, bubbleId);
}

static void OverworldWildSpawns_PrepareConditionalTeleport(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile)
{
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
    state->movementEmoteTimers[slot] = 0;
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    state->movementEmoteEndStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ResetEmotePresentationStyle(
        state, slot, OW_WILD_SPAWNER_BUBBLE_ID_NONE);
    object = OverworldWildSpawns_NormalizeTeleportObjectForOwner(state, slot, object);
    if (OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER(profile->chillAction)) {
        OverworldWildSpawns_StartConditionalTeleportRealFlicker(state, slot, object);
    }
    OverworldWildSpawns_StartTeleportVisibleCooldown(state, slot, object, profile);
}

static void OverworldWildSpawns_ResumeOwnerAfterAlert(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, &primitives);
    if (!OverworldWildSpawns_ResolveConditionsAtIntentBoundary(
            state, slot, &profile, &primitives)) {
        return;
    }
    if (primitives.chillLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) {
        OverworldWildSpawns_PrepareConditionalTeleport(
            state, slot, object, &profile);
        return;
    }

    OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
    state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
    if (state->movementQueuedBattleSlot == slot) {
        return;
    }
    if (profile.alertSpecialAction == OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW) {
        OverworldWildSpawns_TryStartPickupThrowAction(state, slot);
    }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    if ((OW_WILD_RUNTIME(state)->movementFrameDrivenOwnerMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0) {
        OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
    }
#endif
}

static BOOL OverworldWildSpawns_TickSpotEmote(OverworldWildSpawnState *state, int slot, LocalMapObject *object)
{
    BOOL commandFinished = FALSE;

    if (state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_EMOTING) {
        return FALSE;
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND
    if (object != NULL && MapObject_IsSingleMovementActive(object)) {
        commandFinished =
            OverworldWildSpawns_UpdateSpawnerMovementCommandSuppressingHopStartSound(state, object, slot);
    }
#endif
    if (commandFinished) {
        OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] = 0;
        if (state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE
            && OW_WILD_RUNTIME(state)->movementEmotePartnerPrepObjects[slot] == object) {
            OW_WILD_RUNTIME(state)->movementEmotePartnerPrepObjects[slot] = NULL;
        }
    } else {
        OverworldWildSpawns_TickHopStartSoundSuppression(state, slot);
    }

    if (state->movementEmoteTimers[slot] != 0) {
        state->movementEmoteTimers[slot]--;
    }

    if (commandFinished
        && state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_FREEZE
        && state->spawns[slot].active) {
        if (state->movementEmotePlayCryOnHop[slot]) {
            PlayCry(
                state->spawns[slot].species,
                state->spawns[slot].form);
        }
        if (state->movementEmoteShowBubbleEachJump[slot]
            || state->movementEmoteJumpsRemaining[slot] <= 1) {
            OverworldWildSpawns_ShowBubble(object, state->movementEmoteBubbleIds[slot]);
        }
    }

    if (commandFinished
        && OverworldWildSpawns_IsLookAroundEmoteStep(state->movementEmoteSteps[slot])
        && object != NULL
        && MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }

    if (OverworldWildSpawns_TryStartPendingLookAroundEmoteStep(state, slot, object)) {
        return TRUE;
    }
    if (OverworldWildSpawns_IsLookAroundEmoteStep(state->movementEmoteSteps[slot])) {
        return TRUE;
    }

    if (commandFinished
        && state->movementEmoteSteps[slot] != OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE
        && OverworldWildSpawns_StartNextSpotEmoteStep(state, slot, object)) {
        return TRUE;
    }

    if (commandFinished
        && state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE
        && state->movementEmoteJumpsRemaining[slot] > 1
        && state->movementEmoteTimers[slot] != 0) {
        state->movementEmoteJumpsRemaining[slot]--;
        state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_PREP;
        if (OverworldWildSpawns_StartNextSpotEmoteStep(state, slot, object)) {
            return TRUE;
        }
        state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    }

    if (commandFinished
        && state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE
        && object != NULL
        && MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }

    if (object == NULL
        || state->movementEmoteTimers[slot] == 0
        || (commandFinished
            && state->movementEmoteSteps[slot] == OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE
            && state->movementEmoteJumpsRemaining[slot] == 1)) {
        OverworldWildSpawns_CancelSpotEmotePresentation(state, slot, object);
        state->movementEmoteTimers[slot] = 0;
        state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
        state->movementEmoteJumpsRemaining[slot] = 0;
        state->movementSpotStates[slot] = state->movementEmoteEndStates[slot];
        if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_CHILL
            && OverworldWildSpawns_GetActiveConditionApplications(
                state, slot) != 0) {
            OverworldWildSpawns_ResumeOwnerAfterAlert(state, slot, object);
        }
        state->movementEmoteEndStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
        OverworldWildSpawns_ResetEmotePresentationStyle(
            state, slot, OW_WILD_SPAWNER_BUBBLE_ID_NONE);
    }

    return TRUE;
}

static BOOL OverworldWildSpawns_TickTiredEmote(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildBehaviorPrimitives *primitives,
    BOOL actorMotionOwnsFacing)
{
    const OverworldWildBehaviorProfileData *lane;
    BOOL commandFinished = FALSE;

    if (state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
        return FALSE;
    }

    if (OverworldWildSpawns_BehaviorKindUsesMovement(profile->tiredState)) {
        if (state->movementEmoteTimers[slot] != 0) {
            state->movementEmoteTimers[slot]--;
        }
        if (state->movementEmoteTimers[slot] != 0) {
            return FALSE;
        }
        /* The Tired clock can expire during the last Walk's settling tick.
         * Keep the old lane and momentum until Actor Motion returns IDLE. */
        if (actorMotionOwnsFacing) {
            return TRUE;
        }
        lane = OverworldWildSpawns_GetControllerLane(
            profile,
            OW_WILD_SPAWNER_SPOT_STATE_TIRED);
        if (primitives->tiredLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
            && OW_WILD_BEHAVIOR_STOPS_WITH_SKID(
                lane->tilesBeforeTurnSkid)
            && OverworldWildSpawns_TryStartWalkStopSkid(
                state,
                slot,
                profile,
                lane)) {
            return TRUE;
        }
        OverworldWildSpawns_StartTiredCooldown(state, slot);
        return TRUE;
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND
    if (object != NULL && MapObject_IsSingleMovementActive(object)) {
        commandFinished = OverworldWildSpawns_UpdateSpawnerMovementCommand(object);
    }
#endif
    if (commandFinished && object != NULL && MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }

    if (object != NULL
        && state->movementEmoteTimers[slot] == OW_WILD_SPAWNER_ASLEEP_REST_TIMER) {
        return TRUE;
    }

    if (state->movementEmoteTimers[slot] != 0) {
        state->movementEmoteTimers[slot]--;
    }

    if (object == NULL || state->movementEmoteTimers[slot] == 0) {
        if (object != NULL && MapObject_IsSingleMovementActive(object)) {
            MapObject_ClearSingleMovementActive(object);
        }
        OverworldWildSpawns_StartTiredCooldown(state, slot);
    }

    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartSpotEmote(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u8 direction,
    const OverworldWildBehaviorProfile *profile)
{
    u8 bubbleId;

    if (state->movementSpotStates[slot] != OW_WILD_SPAWNER_SPOT_STATE_CHILL
        || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }

    bubbleId = OverworldWildSpawns_GetAlertBubbleIdForProfile(profile);

    if (profile->alertSpecialAction == OW_WILD_BEHAVIOR_ALERT_SPECIAL_CALL_FOR_HELP) {
        OverworldWildSpawns_TrySpawnHelpChildren(
            state,
            state->movementFieldSystem,
            slot,
            profile);
    }

    if (profile->alertTime == 0
        && bubbleId == OW_WILD_SPAWNER_BUBBLE_ID_NONE) {
        OverworldWildSpawns_ResetEmotePresentationStyle(
            state, slot, OW_WILD_SPAWNER_BUBBLE_ID_NONE);
        state->movementBattleSettleFrames = 0;
        OverworldWildSpawns_ResumeOwnerAfterAlert(state, slot, object);
        return TRUE;
    }

    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_EMOTING;
    state->movementEmoteJumpsRemaining[slot] = 0;
    state->movementEmoteTimers[slot] =
        OverworldWildSpawns_GetAlertStateFrameCount(profile, 0);
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_DONE;
    state->movementEmoteDirections[slot] = direction;
    state->movementEmoteEndStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ResetEmotePresentationStyle(
        state, slot, bubbleId);
    state->movementBattleSettleFrames = 0;
    PlayCry(
        state->spawns[slot].species,
        state->spawns[slot].form);
    OverworldWildSpawns_ShowBubble(object, bubbleId);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartManualHopEmote(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u8 requiredState,
    u8 endState,
    u8 direction,
    u8 jumpCount,
    u8 emoteFrames,
    u8 bubbleId,
    BOOL showBubbleEachJump,
    BOOL playHopSound)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->movementSpotStates[slot] != requiredState
        || object == NULL
        || MapObject_IsSingleMovementActive(object)
        || jumpCount == 0) {
        return FALSE;
    }

    if (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE
        || direction > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
        direction = object->curFacing <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            ? object->curFacing
            : OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
    }

    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_EMOTING;
    state->movementEmoteJumpsRemaining[slot] = jumpCount;
    state->movementEmoteTimers[slot] = emoteFrames;
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PARTNER_PREP;
    state->movementEmoteDirections[slot] = direction;
    state->movementEmoteEndStates[slot] = endState;
    state->movementEmoteBubbleIds[slot] = bubbleId;
    state->movementEmoteShowBubbleEachJump[slot] = showBubbleEachJump;
    state->movementEmotePlayCryOnHop[slot] = FALSE;
    OW_WILD_RUNTIME(state)->movementEmotePlayHopSound[slot] = playHopSound;
    state->movementBattleSettleFrames = 0;
    OverworldWildSpawns_StartNextSpotEmoteStep(state, slot, object);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
    return TRUE;
}

static u8 __attribute__((always_inline))
OverworldWildSpawns_GetLookAroundFrames(u8 pauseTicks)
{
    /* The chain policy stores one tick for each two field frames. The
     * look-around timer runs once per field frame. Convert at that boundary. */
    if (pauseTicks < 2) {
        return 3;
    }
    if (pauseTicks > 127) {
        return 255;
    }
    return pauseTicks + pauseTicks;
}

static u8 __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_TryStartChainForwardHop(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 direction)
{
    LocalMapObject *object = state->spawns[slot].object;
    u8 spotState = state->movementSpotStates[slot];
    u16 allowedTile;
    int targetX;
    int targetY;

    targetX = OverworldWildSpawns_ObjectCurrentX(object)
        + OverworldWildSpawns_MovementDirectionDeltaX(direction)
            * OW_WILD_SPAWNER_CHAIN_HOP_FORWARD_DISTANCE;
    targetY = OverworldWildSpawns_ObjectCurrentY(object)
        + OverworldWildSpawns_MovementDirectionDeltaY(direction)
            * OW_WILD_SPAWNER_CHAIN_HOP_FORWARD_DISTANCE;
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile, spotState);
    if (OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
            state,
            state->movementFieldSystem,
            slot,
            profile,
            allowedTile | OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER,
            targetX,
            targetY,
            targetX,
            targetY,
            OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING)) {
        return OW_WILD_CHAIN_STARTED;
    }
    return OW_WILD_CHAIN_ABORT
        * (state->movementStagedHopFinishWithTired[slot] != FALSE);
}

static u8 __attribute__((optimize("Os"))) OverworldWildSpawns_TryStartChainPauseAction(
    OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u8 pauseAction,
    u8 pauseTicks,
    u8 committedDirection)
{
    OverworldActorWalkPolicyCall policyCall;
    OverworldWildChainRepositionResult repositionResult;
    LocalMapObject *object;
    u8 spotState;
    u8 direction;
    u8 lookFrames;

    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE
        || pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_PAUSE) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    spotState = state->movementSpotStates[slot];
    /* The chain boundary is reached only after profile/lane resolution. */
    if (object == NULL
        || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }

    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD) {
        return OverworldWildSpawns_TryStartChainForwardHop(
            state, slot, profile, committedDirection);
    }

    direction = object->curFacing <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
        ? object->curFacing
        : OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;

    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS
        || pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS
        || pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
        if (!OverworldWildSpawns_IsChainActionReady(slot)) {
            return FALSE;
        }
        OverworldWildSpawns_InitPolicyCall(
            &policyCall,
            slot,
            OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_BEGIN);
        policyCall.direction = OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_CENTER;
        if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS) {
            policyCall.distance = OW_WILD_SPAWNER_CHAIN_REPOSITION_STEP;
        } else if (pauseAction
            == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
            policyCall.distance = OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID;
        }
        if (!OverworldWildSpawns_ReduceWalk(&policyCall)) {
            return FALSE;
        }
        {
            (void)OverworldWildSpawns_RunChainReposition(
                    state,
                    slot,
                    profile,
                    policyCall.distance,
                    &repositionResult);

            if (!OverworldWildSpawns_ApplyChainRepositionResult(
                    slot, &repositionResult)) {
                return FALSE;
            }
            return repositionResult.outcome;
        }
    }

    if (pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE) {
        return OverworldWildSpawns_TryStartManualHopEmote(
            state,
            slot,
            object,
            spotState,
            spotState,
            direction,
            OW_WILD_SPAWNER_SPOT_EMOTE_JUMPS_DEFAULT,
            OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP
                * OW_WILD_SPAWNER_SPOT_EMOTE_JUMPS_DEFAULT,
            OW_WILD_SPAWNER_BUBBLE_ID_NONE,
            FALSE,
            TRUE);
    }

    if (pauseAction != OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND) {
        return FALSE;
    }

    lookFrames = OverworldWildSpawns_GetLookAroundFrames(pauseTicks);

    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_EMOTING;
    state->movementEmoteJumpsRemaining[slot] = lookFrames;
    state->movementEmoteTimers[slot] = lookFrames;
    state->movementEmoteSteps[slot] = OW_WILD_SPAWNER_SPOT_EMOTE_STEP_LOOK_FIRST;
    state->movementEmoteDirections[slot] =
        OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
            ->buildLookPlan(direction);
    state->movementEmoteEndStates[slot] = spotState;
    OverworldWildSpawns_ResetEmotePresentationStyle(
        state, slot, OW_WILD_SPAWNER_BUBBLE_ID_NONE);
    state->movementBattleSettleFrames = 0;
    OverworldWildSpawns_StartNextSpotEmoteStep(state, slot, object);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ResolveConditionsAtIntentBoundary(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile,
    OverworldWildBehaviorPrimitives *primitives)
{
    LocalMapObject *object = state->spawns[slot].object;
    u16 conditionResult = OverworldWildSpawns_EvaluateConditionsForSlot(
        state, state->movementFieldSystem, slot, profile, primitives);

    if ((conditionResult & OW_WILD_CONDITION_RESULT_FAIL_CLOSED) != 0) {
        return FALSE;
    }
    if ((conditionResult & OW_WILD_CONDITION_RESULT_TIMED_ENDED) != 0
        && OverworldWildSpawns_GetActiveConditionApplications(state, slot) == 0
        && primitives->tiredReaction != OW_WILD_BEHAVIOR_REACTION_NONE) {
        OverworldWildSpawns_StartTiredEmoteWithProfile(
            state, slot, profile, primitives);
        return FALSE;
    }
    if ((conditionResult & OW_WILD_CONDITION_RESULT_TRIGGERED) != 0) {
        if (OverworldWildSpawns_TryStartSpotEmote(
                state,
                slot,
                object,
                (u8)(conditionResult >> 8),
                profile)) {
            return FALSE;
        }
    }
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ResolveChainConditionsAtIntentBoundary(
    OverworldWildSpawnState *state,
    int slot,
    OverworldWildBehaviorProfile *profile)
{
    OverworldWildBehaviorPrimitives primitives;

    return OverworldWildSpawns_ResolveConditionsAtIntentBoundary(
        state,
        slot,
        profile,
        &primitives);
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_IssueIdleIntent(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    OverworldWildBehaviorProfile *profile,
    OverworldWildBehaviorPrimitives *primitives)
{
    if (!OverworldWildSpawns_ResolveConditionsAtIntentBoundary(
            state, slot, profile, primitives)) {
        return FALSE;
    }

    if (OverworldWildSpawns_GetActiveConditionApplications(state, slot)
            != 0) {
        BOOL movementStarted;

        if (profile->alertSpecialAction
                == OW_WILD_BEHAVIOR_ALERT_SPECIAL_PICKUP_THROW) {
            OverworldWildSpawns_TryStartPickupThrowAction(state, slot);
        }
        movementStarted = OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(
            state,
            slot,
            object,
            profile,
            primitives);
        return movementStarted
            && (OverworldWildSpawns_HasPendingBattle(state)
                || state->movementQueuedBattleSlot >= 0);
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ
    if (fieldSystem != NULL && fieldSystem->playerAvatar != NULL) {
        int objectX = OverworldWildSpawns_ObjectCurrentX(object);
        int objectY = OverworldWildSpawns_ObjectCurrentY(object);
        int playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
        int playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
        int dx;
        int dy;
        u8 directions[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];
        u8 currentLocomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
            primitives,
            state->movementSpotStates[slot]);
        u8 movementTarget = OverworldWildSpawns_GetCurrentMovementTarget(
            primitives,
            state->movementSpotStates[slot]);
        int directionCount;

        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_CIRCLE_PLAYER) {
            OverworldWildSpawns_TryGetCirclePlayerMovementTarget(
                state,
                fieldSystem,
                slot,
                profile,
                state->movementSpotStates[slot],
                objectX,
                objectY,
                playerX,
                playerY,
                &playerX,
                &playerY);
        } else if (movementTarget == OW_WILD_BEHAVIOR_TARGET_NEXT_TO_PLAYER) {
            if (!OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    &playerX,
                    &playerY)) {
                return FALSE;
            }
        }
        dx = playerX - objectX;
        dy = playerY - objectY;

        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER) {
            dx = -dx;
            dy = -dy;
        } else if (movementTarget == OW_WILD_BEHAVIOR_TARGET_NONE) {
            dx = 0;
            dy = 0;
        }

        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY) {
            directionCount = OverworldWildSpawns_BuildRandomDirections(directions);
        } else {
            directionCount = OverworldWildSpawns_BuildDirectedDirections(
                dx, dy, directions);
        }
        if (movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER) {
            OverworldWildSpawns_AppendFleeFallbackDirections(
                directions,
                &directionCount,
                dx,
                dy);
        } else if (movementTarget != OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY) {
            OverworldWildSpawns_AppendFrameDrivenChaseFallbackDirections(
                directions,
                &directionCount);
        }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND
        if (currentLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
            if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY) {
                OverworldWildSpawns_TryStartChillWanderCommand(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    primitives);
            } else {
                OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    dx,
                    dy,
                    directions,
                    directionCount,
                    movementTarget == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER
                        ? OW_WILD_HELPER_HOP_PLAN_FLEE
                        : (movementTarget != OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY
                                && movementTarget != OW_WILD_BEHAVIOR_TARGET_NONE
                            ? OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY
                            : OW_WILD_HELPER_HOP_PLAN_DIRECT));
            }
        } else if (currentLocomotion
                == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT) {
            OverworldWildSpawns_TryStartChillTeleportMovementCommand(
                state,
                fieldSystem,
                slot,
                profile);
        } else if (currentLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
                || currentLocomotion
                    == OW_WILD_BEHAVIOR_LOCOMOTION_TURN_AROUND) {
            if (movementTarget == OW_WILD_BEHAVIOR_TARGET_RANDOM_NEARBY) {
                OverworldWildSpawns_TryStartChillWanderCommand(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    primitives);
            } else {
                OverworldWildSpawns_TryStartSpawnerMovementCommand(
                    state,
                    fieldSystem,
                    slot,
                    directions,
                    directionCount,
                    profile,
                    primitives);
            }
        }
#endif
    }
#else
    (void)fieldSystem;
#endif
    return FALSE;
}

static void __attribute__((optimize("Os", "no-tree-forwprop"))) OverworldWildSpawns_TickMovementParams(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    BOOL frameTick,
    u16 frameWorkMask
)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    int i;

    state->movementFieldSystem = fieldSystem;
    if (frameTick) {
        OverworldWildSpawns_TickFrameMovementDecisionCounter();
    }
    if (!frameTick && runtime->throwState.targetMask == 0) {
        if (OverworldWildSpawns_TryBattleSettleRetry(state, fieldSystem)) {
            return;
        }
    } else if (OverworldWildSpawns_TryFrameBattleSettleRetry(state, fieldSystem)) {
        return;
    }
    if (OverworldWildSpawns_TryStartBattleFromAButton(state, fieldSystem)) {
        return;
    }
    if (!frameTick || runtime->movementIdleAiCursor == 0) {
        const OverworldWildHelperOverlayEntry *helperEntry =
            OverworldWildSpawns_GetHelperOverlayEntry();

        if (helperEntry != NULL
            && helperEntry->queryPickupThrowTarget != NULL
            && OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY->tryResolve != NULL
            && OVERWORLD_WILD_OVERLAP_RESOLVER_ENTRY->tryResolve(
                state,
                &runtime->throwState,
                OverworldWildSpawns_GetPickupThrowUnstableMask(state)
                    | runtime->movementNativeHeldMask,
                helperEntry->queryPickupThrowTarget,
                OverworldWildSpawns_TryStartSpawnerMovementCommand)) {
            return;
        }
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active
            && state->spawns[i].object != NULL
            && ((frameTick
                    && (frameWorkMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0)
                || (!frameTick
                    && OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[i])))) {
            LocalMapObject *object = state->spawns[i].object;
            int cooldown = state->movementCooldowns[i];
            int shouldIssueLookCommand = FALSE;
            u8 throwTarget = runtime->throwState.targets[i];
            OverworldWildBehaviorProfile profile;
            OverworldWildBehaviorPrimitives primitives;
            OverworldActorPolicyView policy;
            BOOL actorPolicyKnown;
            BOOL actorMotionOwnsFacing;

            if ((state->captureTargetMask
                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0) {
                continue;
            }
            if ((runtime->spawnPresentations.distanceDespawnPendingMask
                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0) {
                continue;
            }
            if ((state->spawns[i].active
                    & OW_WILD_SPAWN_AGGRO_PENDING_FLAG) != 0
                && state->movementSpotStates[i]
                    != OW_WILD_SPAWNER_SPOT_STATE_TIRED) {
                OverworldWildSpawns_EnterAggroState(state, i, NULL);
                OverworldWildSpawns_ApplyHelpChildSpawnState(state, i, object);
            }

            OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
                state,
                i,
                &profile,
                &primitives);
            actorPolicyKnown = OverworldActorPolicy_Inspect((u8)i, &policy);
            actorMotionOwnsFacing = actorPolicyKnown
                && policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE
                && policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED;
            if (OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile.owner.walkOptions)) {
                OverworldWildSpawns_ApplyFacePlayerFacing(
                    state,
                    i,
                    runtime->movementEmotePlayHopSound[i]);
            }

            if ((throwTarget & OW_WILD_SPAWNER_THROW_TARGET_CARRIED_FLAG) != 0) {
                u8 targetSlot = OW_WILD_SPAWNER_THROW_TARGET_DECODE(throwTarget);
                OverworldWildSpawns_SyncCarriedThrowTarget(state, i, targetSlot);
            }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND
            if (OverworldWildSpawns_IsMovementSlotInProgress(state, i)) {
                if (frameTick) {
                    continue;
                }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
                OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#else
                BOOL stagedHopRenderFinished = FALSE;
                if (OverworldWildSpawns_TickStagedHopMovementListTask(state, fieldSystem, i, &stagedHopRenderFinished)) {
                    if (stagedHopRenderFinished) {
                        state->movementBattleSettleFrames = OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES;
                    }
                    continue;
                }
                if (OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot(state, i)) {
                    OverworldWildSpawns_ClearMovementSlotInProgress(state, i);
                    if (OverworldWildSpawns_HandleFinishedStagedHopMovementCommand(
                            state,
                            fieldSystem,
                            i,
                            TRUE)) {
                        continue;
                    }
                    if (OverworldWildSpawns_HandleFinishedSpawnHopMovementCommand(state, fieldSystem, i)) {
                        continue;
                    }
                    OverworldWildSpawns_HandleFinishedMovementCommand(state, i);
                }
#endif
                continue;
            }
#endif

            if (!frameTick
                && OverworldWildSpawns_TickCustomJumpRenderSettle(state, fieldSystem, i)) {
                continue;
            }

            if (state->movementStagedHopPending[i]) {
                if (frameTick) {
                    continue;
                }
                if (cooldown > 0) {
                    state->movementCooldowns[i] = cooldown - 1;
                    continue;
                }
                OverworldWildSpawns_ContinuePendingStagedHop(state, fieldSystem, i);
                continue;
            }

            if (actorPolicyKnown
                && (policy.chainPauseAction
                    & OW_WILD_SPAWNER_CHAIN_PAUSE_PENDING) != 0) {
                if (cooldown > 0) {
                    state->movementCooldowns[i] = cooldown - 1;
                    continue;
                }
                OverworldWildSpawns_CommitDeferredChainMovementPause(
                    state,
                    i,
                    &profile);
                continue;
            }

            if (state->movementActorControlModes[i]
                == OW_WILD_ACTOR_CONTROL_HELD) {
                continue;
            }

            if (OverworldWildSpawns_TickSpotEmote(state, i, object)) {
                continue;
            }

            if (OverworldWildSpawns_TickTiredEmote(
                    state,
                    i,
                    object,
                    &profile,
                    &primitives,
                    actorMotionOwnsFacing)) {
                continue;
            }

            if (OverworldWildSpawns_UpdateSpawnMoveTargetState(
                    state,
                    fieldSystem,
                    i,
                    object)) {
                continue;
            }

            if (state->movementCrashShakeTimers[i] != 0) {
                if (cooldown > 0) {
                    state->movementCooldowns[i] = cooldown - 1;
                }
                continue;
            }

            if (OverworldWildSpawns_IsReservedPickupTargetNearCarrier(state, i)) {
                continue;
            }

            if (state->movementQueuedBattleSlot == i) {
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
                OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
                continue;
            }

            if (throwTarget != OW_WILD_SPAWNER_THROW_TARGET_NONE) {
                if (throwTarget & OW_WILD_SPAWNER_THROW_TARGET_WINDUP_FLAG) {
                    if (cooldown > 0) {
                        state->movementCooldowns[i] = cooldown - 1;
                        continue;
                    }
                    OverworldWildSpawns_TryStartFrameDrivenOwnerMovementCommand(
                        state,
                        i,
                        object,
                        &profile,
                        &primitives);
                    continue;
                }
            }

            if (actorMotionOwnsFacing) {
                /* Heavy work above continues the accepted motion. Idle AI,
                 * including failed-direction facing fallbacks, waits until
                 * the shared owner returns IDLE. */
                continue;
            }

            if (cooldown > 0) {
                state->movementCooldowns[i] = cooldown - 1;
                if (cooldown == 1) {
                    state->movementTeleportVisiblePause[i] = FALSE;
                }
                if (frameTick) {
                    if (cooldown == 1) {
                        shouldIssueLookCommand = TRUE;
                    }
                }
            } else {
                state->movementTeleportVisiblePause[i] = FALSE;
                state->movementCooldowns[i] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
                shouldIssueLookCommand = TRUE;
            }
            if (!shouldIssueLookCommand) {
                continue;
            }

            if (OverworldWildSpawns_IssueIdleIntent(
                    state,
                    fieldSystem,
                    i,
                    object,
                    &profile,
                    &primitives)) {
                return;
            }
        }
    }
}
#endif

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND
static BOOL OverworldWildSpawns_UpdateSpawnerMovementCommand(LocalMapObject *object)
{
    int i;

    for (i = 0; i < OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS; i++) {
        BOOL singleMovementActive = MapObject_IsSingleMovementActive(object);

        if (!singleMovementActive) {
            return TRUE;
        }

        if (MapObject_UpdateMovementCommand(object)) {
            MapObject_ClearSingleMovementActive(object);
            return TRUE;
        }

#if !OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE
        break;
#endif
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_StartCustomJumpRenderSettle(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
#if !OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_ENABLED
    (void)state;
    (void)slot;
    (void)object;
    return FALSE;
#else
    s32 targetX;
    s32 targetY;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || !OW_WILD_RUNTIME(state)->movementCustomJumpActive[slot]
        || OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_FRAMES == 0) {
        return FALSE;
    }

    targetX = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetX[slot]);
    targetY = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetY[slot]);
    if ((s32)object->posVec[0] == targetX && (s32)object->posVec[2] == targetY) {
        return FALSE;
    }

    sOverworldWildCustomJumpRenderSettleActive[slot] = TRUE;
    sOverworldWildCustomJumpRenderSettleStartX[slot] = (s32)object->posVec[0];
    sOverworldWildCustomJumpRenderSettleStartY[slot] = (s32)object->posVec[2];
    sOverworldWildCustomJumpRenderSettleElapsedFrames[slot] = 0;
    return TRUE;
#endif
}

#if OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_ENABLED
static BOOL OverworldWildSpawns_CompleteCustomJumpRenderSettle(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
    OverworldWildBehaviorProfile profile;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL) {
        return FALSE;
    }

    OverworldWildSpawns_SetObjectRenderTileOnly(
        object,
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetX[slot],
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetY[slot]);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH | OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS);
    sOverworldWildCustomJumpRenderSettleActive[slot] = FALSE;
    OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 20);
    if (OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
        != OW_WILD_CUSTOM_MOTION_WALK) {
        OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
    }

    if (state->movementStagedHopPending[slot]) {
        OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
            state, slot, &profile, NULL);
        OverworldWildSpawns_FinishPendingStagedHop(state, slot, object);
        OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(state, fieldSystem, slot, object);
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 15);
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_TickCustomJumpRenderSettle(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    LocalMapObject *object;
    u32 elapsed;
    u32 total;
    s32 targetX;
    s32 targetY;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !sOverworldWildCustomJumpRenderSettleActive[slot]) {
        return FALSE;
    }
    if (!OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        OverworldWildSpawns_ClearCustomJump(state, slot);
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        OverworldWildSpawns_ClearCustomJump(state, slot);
        return FALSE;
    }

    total = OW_WILD_SPAWNER_CUSTOM_JUMP_POST_LANDING_RENDER_SETTLE_FRAMES;
    elapsed = sOverworldWildCustomJumpRenderSettleElapsedFrames[slot] + 1;
    if (elapsed >= total) {
        return OverworldWildSpawns_CompleteCustomJumpRenderSettle(
            state,
            fieldSystem,
            slot,
            object);
    }

    sOverworldWildCustomJumpRenderSettleElapsedFrames[slot] = elapsed;
    targetX = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetX[slot]);
    targetY = OW_WILD_SPAWNER_TILE_CENTER_COORD_FX32(
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetY[slot]);
    object->posVec[0] = (u32)OverworldWildSpawns_LerpCustomJumpFx32(
        sOverworldWildCustomJumpRenderSettleStartX[slot],
        targetX,
        elapsed,
        total);
    object->posVec[2] = (u32)OverworldWildSpawns_LerpCustomJumpFx32(
        sOverworldWildCustomJumpRenderSettleStartY[slot],
        targetY,
        elapsed,
        total);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 19);
    return TRUE;
}
#else
static BOOL OverworldWildSpawns_TickCustomJumpRenderSettle(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    (void)state;
    (void)fieldSystem;
    (void)slot;
    return FALSE;
}
#endif

static OverworldMotionDecision OverworldWildSpawns_BeginSharedMotion(
    OverworldWildSpawnState *state,
    int slot,
    u8 facing,
    const OverworldWildBehaviorProfileData *lane,
    BOOL flatWalk,
    BOOL chainReposition,
    u16 duration,
    u8 spinSpeed,
    u8 swayWidth)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    OverworldWildSurfaceHit targetSurface;
    u8 kind = state->movementSpawnRunActive[slot]
            == OW_WILD_SPAWN_ENTRY_FLY_IN
        ? OVERWORLD_MOTION_KIND_FLY_IN
        : flatWalk
            ? OVERWORLD_MOTION_KIND_WALK
            : chainReposition
                ? OVERWORLD_MOTION_KIND_REPOSITION
                : OVERWORLD_MOTION_KIND_HOP;

    return OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->requestMotion(
            state,
            slot,
            lane,
            kind,
            OVERWORLD_MOTION_VISIBILITY_VISIBLE,
            runtime->movementCustomJumpArcHeightsQ4[slot],
            facing,
            duration,
            spinSpeed,
            swayWidth,
            OverworldWildSpawns_QuerySurface(
                    state->movementFieldSystem,
                    runtime->movementCustomJumpTargetX[slot],
                    runtime->movementCustomJumpTargetY[slot],
                    &targetSurface)
                ? targetSurface.surfaceId
                : OW_WILD_SURFACE_ID_NATIVE_GROUND);
}

static void OverworldWildSpawns_CancelSharedMotion(int slot, u8 reason)
{
    u8 phase;

    /* During BOUND, reset ends any old Follower motion before mount control
     * starts. Once RIDING, Wild cleanup must not cancel mounted motion. */
    if (slot == OW_WILD_FOLLOWER_SLOT
        && (OverworldWildSpawns_MountIsActive() & 3)
            == OVERWORLD_MOUNT_PHASE_RIDING) {
        return;
    }
    (void)OverworldWildSpawns_AcknowledgeSharedMotion(
        slot,
        OVERWORLD_ACTOR_BOUNDARY_CANCEL,
        reason,
        NULL,
        &phase);
    OW_WILD_RUNTIME(&sOverworldWildSpawnState)
        ->movementMotionIdentities[slot] = 0;
}

static inline BOOL __attribute__((always_inline, optimize("Os")))
OverworldWildSpawns_ApplyCustomJumpRenderOffset(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u16 *appliedThrough,
    u8 *phase)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldActorPolicyView policy;
    OverworldMotionSample sample;
    s32 logicalRenderX;
    s32 logicalRenderZ;
    s32 tileBaseY;
    BOOL flyIn;
    u8 acknowledgements;
    u8 motionPhase;
    runtime = OW_WILD_RUNTIME(state);

    if (!OverworldWildSpawns_AcknowledgeSharedMotion(
            slot,
            0,
            0,
            &sample,
            &motionPhase)) {
        return FALSE;
    }
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
    sOverworldWildCustomJumpRamElapsedFrames = sample.elapsed;
    sOverworldWildCustomJumpRamFrameCount = sample.duration;
#endif
    flyIn = state->movementSpawnRunActive[slot]
        == OW_WILD_SPAWN_ENTRY_FLY_IN;
    if (flyIn) {
        /* xPrev/yPrev track the rendered ground tile while xCurr/yCurr keep
         * the loaded landing tile between presentation samples. */
        object->xCurr = object->xPrev;
        object->yCurr = object->yPrev;
    }
    object->posVec[0] = (u32)sample.renderX;
    object->posVec[1] = (u32)(flyIn
        ? runtime->movementCustomJumpShadowBaseY[slot]
        : sample.baseY);
    object->posVec[2] = (u32)sample.renderZ;
    object->hCurr = (s32)object->posVec[1] >> 15;
    object->faceVec[0] = 0;
    object->faceVec[1] = 0;
    object->faceVec[2] = 0;
    object->unk88[0] = 0;
    object->unk88[1] = (u32)sample.heightOffset;
    object->unk94[1] = 0;
    object->flags = (object->flags
            & ~(BIT_JUMP_START | BIT_VANISH | MAPOBJECTFLAG_UNK4
                | MAPOBJECTFLAG_UNK8 | MAPOBJECTFLAG_UNK22
                | MAPOBJECTFLAG_UNK30))
        | BIT_MOVE_START
        | MAPOBJECTFLAG_UNK13
        | (runtime->movementCustomJumpArcHeightsQ4[slot] != 0
            ? BIT_JUMP_START
            : 0);
    logicalRenderX = sample.renderX;
    logicalRenderZ = sample.renderZ;
    if (runtime->movementCustomJumpStartY[slot]
        == runtime->movementCustomJumpTargetY[slot]) {
        logicalRenderZ -= sample.swayOffset;
    } else {
        logicalRenderX -= sample.swayOffset;
    }
    if (object->xCurr != logicalRenderX >> 16
        || object->yCurr != logicalRenderZ >> 16) {
        object->xPrev = object->xCurr;
        object->yPrev = object->yCurr;
        object->xCurr = logicalRenderX >> 16;
        object->yCurr = logicalRenderZ >> 16;
        tileBaseY = OverworldWildSpawns_GetObjectGroundBaseYAt(
            state->movementFieldSystem,
            object,
            object->xCurr,
            object->yCurr);
        runtime->movementCustomJumpShadowBaseY[slot] = tileBaseY;
        OverworldWildSpawns_ReconcileNativeShadow(
            state->movementFieldSystem,
            object);
        if (!flyIn && OverworldActorPolicy_Inspect((u8)slot, &policy)
            && (policy.chainStepsRemaining
                & (OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID
                    | OW_WILD_SPAWNER_CHAIN_REPOSITION_DUST))
            == (OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID
                | OW_WILD_SPAWNER_CHAIN_REPOSITION_DUST)) {
            OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->playLandingHopParticle(object);
        }
    }
    if (flyIn) {
        tileBaseY = runtime->movementCustomJumpShadowBaseY[slot];
        object->posVec[1] = (u32)tileBaseY;
        object->unk88[1] = (u32)(sample.renderY - tileBaseY);
        object->xPrev = object->xCurr;
        object->yPrev = object->yCurr;
        object->xCurr = object->xInit;
        object->yCurr = object->yInit;
    }
    OverworldWildSpawns_SetObjectFacing(object, sample.facing);
    if (appliedThrough != NULL) {
        *appliedThrough = (sample.flags
                & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0
            ? sample.lastPathAdvance
            : 0;
    }
    /* The last sample is not complete until the landing helper normalizes
     * engine flags, height, shadow, and render position. Keep its ACKs out of
     * the early command-END latch until that canonical write is done. */
    if (motionPhase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        acknowledgements = OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED;
        if ((sample.flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
            acknowledgements |= OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY;
        }
        if (!OverworldWildSpawns_AcknowledgeSharedMotion(
                slot,
                acknowledgements,
                sample.lastPathAdvance,
                NULL,
                &motionPhase)) {
            return FALSE;
        }
    }
    if (phase != NULL) {
        *phase = motionPhase;
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_CommitCustomJumpLanding(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    u16 appliedThrough)
{
    OverworldWildOverlayRuntimeState *runtime;
    int targetX;
    int targetY;
    u8 phase;

    runtime = OW_WILD_RUNTIME(state);
    targetX = runtime->movementCustomJumpTargetX[slot];
    targetY = runtime->movementCustomJumpTargetY[slot];

    OverworldWildSpawns_SetObjectLandingTile(
        state->movementFieldSystem,
        object,
        targetX,
        targetY);
    if (state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_FLY_IN) {
        /* Fly In commits the exact height validated before its presentation
         * began. The landing helper still owns tile, surface, flag, and
         * shadow normalization; no origin or intermediate tile can replace
         * this terminal height. */
        object->posVec[1] =
            (u32)runtime->movementCustomJumpTargetBaseY[slot];
        object->hInit = runtime->movementCustomJumpTargetBaseY[slot] >> 15;
        object->hPrev = object->hInit;
        object->hCurr = object->hInit;
    }
    if (!OverworldWildSpawns_AcknowledgeSharedMotion(
            slot,
            OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED
                | OVERWORLD_ACTOR_BOUNDARY_STREAM_READY,
            appliedThrough,
            NULL,
            &phase)) {
        return FALSE;
    }
    return phase == OVERWORLD_MOTION_PHASE_IDLE
        || phase == OVERWORLD_MOTION_PHASE_SETTLING
        || (runtime->movementCustomMotionModes[slot]
                == OW_WILD_CUSTOM_MOTION_WALK
            && phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING);
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_UpdateCustomJumpLanding(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    BOOL commandFinished)
{
    OverworldWildOverlayRuntimeState *runtime;
    u16 appliedThrough = 0;
    u8 phase;

    if (slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL) {
        return commandFinished;
    }
    runtime = OW_WILD_RUNTIME(state);
    if (!runtime->movementCustomJumpActive[slot]) {
        return commandFinished;
    }
    OverworldWildSpawns_RecordCustomJumpRamObject(
        state,
        slot,
        object,
        commandFinished ? 10 : 11);

#if OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_OFFSET
    if (!OverworldWildSpawns_ApplyCustomJumpRenderOffset(
            state,
            slot,
            object,
            &appliedThrough,
            &phase)) {
        return FALSE;
    }
    if (commandFinished
        && !OverworldWildSpawns_AcknowledgeSharedMotion(
            slot,
            OVERWORLD_ACTOR_BOUNDARY_ENGINE_END,
            0,
            NULL,
            &phase)) {
        return FALSE;
    }
    if (phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        return FALSE;
    }
#endif

    if (commandFinished
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_OFFSET
        || phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING
#endif
    ) {
        if (!commandFinished && MapObject_IsSingleMovementActive(object)) {
            /* The shared timeline reached its terminal sample before the
             * stationary engine shell. Complete the shell before releasing
             * it. Clearing its flags directly leaves short Walk commands in
             * an unfinished native state. */
            OverworldWildSpawns_FinishPresentationCommand(object);
        }
        if (!commandFinished
            && !OverworldWildSpawns_AcknowledgeSharedMotion(
                slot,
                OVERWORLD_ACTOR_BOUNDARY_ENGINE_END,
                0,
                NULL,
                &phase)) {
            return FALSE;
        }
#if OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS \
    && !OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_OFFSET \
    && !OW_WILD_SPAWNER_CUSTOM_JUMP_RENDER_SETTLE
        OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
        sOverworldWildCustomJumpVisibleLegFinished[slot] = TRUE;
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 12);
#else
        if (!OverworldWildSpawns_CommitCustomJumpLanding(
                state,
                slot,
                object,
                appliedThrough)) {
            return FALSE;
        }
#if !OW_WILD_SPAWNER_CUSTOM_JUMP_POST_RESTORE_FINALIZE
        OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
#endif
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 13);
#endif
        return TRUE;
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot(
    OverworldWildSpawnState *state,
    int slot)
{
    LocalMapObject *object;
    BOOL commandFinished;
    BOOL landingFinished;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->spawns[slot].object == NULL) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (OverworldWildSpawns_IsNativeHeldMovementOwned(state, slot)) {
        commandFinished = MapObject_ClearHeldMovementIfActive(object);
        if (commandFinished) {
            OW_WILD_RUNTIME(state)->movementNativeHeldMask &=
                ~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
        }
    } else {
        commandFinished =
            OverworldWildSpawns_UpdateSpawnerMovementCommandSuppressingHopStartSound(
                state,
                object,
                slot);
    }
    if (commandFinished) {
        if (OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] != 0) {
            StopSE(OW_WILD_SPAWNER_HOP_START_SE);
        }
        OW_WILD_RUNTIME(state)->movementHopStartSoundSuppressFrames[slot] = 0;
        MapObject_ClearSingleMovementActive(object);
    } else {
        OverworldWildSpawns_TickHopStartSoundSuppression(state, slot);
    }
    landingFinished = OverworldWildSpawns_UpdateCustomJumpLanding(
        state,
        slot,
        object,
        commandFinished);
    return landingFinished;
}
#endif

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
static void OverworldWildSpawns_TickFrameMovementDecisionCounter(void)
{
    sOverworldWildMovementFrameDecisionCounter++;
}

static void OverworldWildSpawns_StopFrameMovementTask(void)
{
    sOverworldWildMovementFrameTaskExecuting = FALSE;
    if (sOverworldWildMovementFrameTask != NULL) {
        SysTask *task = sOverworldWildMovementFrameTask;

        sOverworldWildMovementFrameTask = NULL;
        DestroySysTask(task);
    }
}

static BOOL OverworldWildSpawns_QueueBattleScriptTask(FieldSystem *fieldSystem, LocalMapObject *object)
{
    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->taskman != NULL
        || OverworldWildSpawns_IsPlayerBallProjectileActive()) {
        return FALSE;
    }

    EventSet_Script(fieldSystem, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT, object);
    return TRUE;
}

static void OverworldWildSpawns_CancelDeferredBattleScript(void)
{
    OverworldWildSpawnState *state = sOverworldWildDeferredBattleState;

    if (sOverworldWildDeferredBattleScriptTask != NULL) {
        SysTask *task = sOverworldWildDeferredBattleScriptTask;

        sOverworldWildDeferredBattleScriptTask = NULL;
        sOverworldWildDeferredBattleState = NULL;
        DestroySysTask(task);
    } else {
        sOverworldWildDeferredBattleState = NULL;
    }

    if (state != NULL) {
        OverworldWildSpawns_ResetPendingBattle(state);
    }
}

static void OverworldWildSpawns_CleanupResidentTasks(void)
{
    int i;

    OverworldWildSpawns_CancelDeferredBattleScript();
    OverworldWildSpawns_StopFrameMovementTask();
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        OverworldWildSpawns_ClearStagedHopMovementListTask(
            sOverworldWildLastState,
            i);
    }
}

static void OverworldWildSpawns_DeferredBattleScriptTask(SysTask *task, void *data)
{
    FieldSystem *fieldSystem;
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildSpawnState *state;
    LocalMapObject *object;
    u16 generation;
    int slot;

    (void)data;
    if (sOverworldWildMovementFrameTaskExecuting) {
        return;
    }

    state = sOverworldWildDeferredBattleState;
    fieldSystem = state != NULL ? state->movementFieldSystem : NULL;
    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->taskman != NULL) {
        OverworldWildSpawns_CancelDeferredBattleScript();
        return;
    }
    if (OverworldWildSpawns_IsPlayerBallProjectileActive()) {
        return;
    }

    generation = state->pendingEncounterGeneration;
    slot = state->pendingSlot;
    object = NULL;
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry != NULL
        && helperEntry->validateDeferredBattle != NULL
        && helperEntry->validateDeferredBattle(fieldSystem, state, slot, generation)) {
        object = state->spawns[slot].object;
    }
    sOverworldWildDeferredBattleScriptTask = NULL;
    sOverworldWildDeferredBattleState = NULL;

    OverworldWildSpawns_StopFrameMovementTask();
    if (fieldSystem != NULL && object != NULL) {
        OverworldWildSpawns_QueueBattleScriptTask(fieldSystem, object);
    } else if (state != NULL) {
        OverworldWildSpawns_ResetPendingBattle(state);
    }
    DestroySysTask(task);
}

static BOOL OverworldWildSpawns_DeferBattleScript(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    LocalMapObject *object;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }
    object = state->spawns[slot].object;
    if (fieldSystem != NULL
        && !sOverworldWildMovementFrameTaskExecuting
        && fieldSystem->taskman == NULL) {
        return OverworldWildSpawns_QueueBattleScriptTask(fieldSystem, object);
    }

    sOverworldWildDeferredBattleState = state;
    if (sOverworldWildDeferredBattleScriptTask == NULL) {
        sOverworldWildDeferredBattleScriptTask = CreateSysTask(
            OverworldWildSpawns_DeferredBattleScriptTask,
            NULL,
            OW_WILD_SPAWNER_MOVEMENT_FRAME_TASK_PRIORITY + 1);
    }
    if (sOverworldWildDeferredBattleScriptTask != NULL) {
        return TRUE;
    }
    return FALSE;
}

static void OverworldWildSpawns_EnsureFrameMovementTask(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    if (state == NULL || fieldSystem == NULL) {
        return;
    }

    state->movementFieldSystem = fieldSystem;
    if (sOverworldWildMovementFrameTask == NULL) {
        sOverworldWildMovementFrameTask = CreateSysTask(
            OverworldWildSpawns_FrameMovementTask,
            state,
            OW_WILD_SPAWNER_MOVEMENT_FRAME_TASK_PRIORITY);
        if (sOverworldWildMovementFrameTask != NULL) {
            sOverworldWildMovementFrameDecisionCounter = 0;
        }
    }
}

static BOOL OverworldWildSpawns_TickPlayerBallProjectile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildOverlayRuntimeState *runtime;
    LocalMapObject *ballObject;
    BOOL active;

    runtime = OverworldWildSpawns_EnsureRuntimeState(state);
    if (runtime == NULL) {
        return FALSE;
    }
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL) {
        OverworldWildSpawns_ResetPlayerBallShadowTracking(state);
        return FALSE;
    }
    active = helperEntry->tickPlayerBallProjectile(
            fieldSystem,
            state,
            &runtime->spawnPresentations,
            &runtime->despawnTelemetry,
            OverworldWildSpawns_ResetSlotState,
            OverworldWildSpawns_PrepareSlotForCapture,
            OverworldWildSpawns_CalculatePlayerBallShakes,
            OverworldWildSpawns_FindCapturedPokemonDestination);
    ballObject = helperEntry->getPlayerBallProjectileObject();
    OverworldWildSpawns_SyncPlayerBallShadowObject(
        state,
        fieldSystem,
        ballObject);
    return active;
}

static BOOL OverworldWildSpawns_ApplyPresentationCommand(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u8 operation,
    u8 slot)
{
    const OverworldWildHelperOverlayEntry *helperEntry =
        OverworldWildSpawns_GetHelperOverlayEntry();
    OverworldWildHelperPresentationCall call;
    BOOL applied = FALSE;

    if (helperEntry != NULL
        && helperEntry->applyPresentationCommand != NULL) {
        memset(&call, 0, sizeof(call));
        call.version = OVERWORLD_WILD_HELPER_PRESENTATION_CALL_VERSION;
        call.size = sizeof(call);
        call.operation = operation;
        call.slot = slot;
        applied = helperEntry->applyPresentationCommand(
            fieldSystem,
            state,
            &call);
    }
    OverworldWildSpawns_ResetPlayerBallShadowTracking(state);
    return applied;
}

static LocalMapObject *OverworldWildSpawns_GetPlayerBallProjectileObject(void)
{
    const OverworldWildHelperOverlayEntry *helperEntry =
        OverworldWildSpawns_GetHelperOverlayEntry();

    return helperEntry != NULL
            && helperEntry->getPlayerBallProjectileObject != NULL
        ? helperEntry->getPlayerBallProjectileObject()
        : NULL;
}

static BOOL OverworldWildSpawns_IsPlayerBallProjectileActive(void)
{
    return OverworldWildSpawns_GetPlayerBallProjectileObject() != NULL;
}

static void OverworldWildSpawns_OverlayOnFieldBusy(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildResidentData *residentData)
{
    int i;

    if (state->movementRuntimeState != NULL) {
        OW_WILD_RUNTIME(state)->queuedSpawnSlotPlusOne = 0;
        OW_WILD_RUNTIME(state)->refillTerrainMask = 0;
        OW_WILD_RUNTIME(state)->refillPositionChecksRemaining = 0;
    }
    OverworldWildSpawns_MountCancel(
        OVERWORLD_MOUNT_CANCEL_FIELD_BUSY);

    residentData->pendingFlags |= OW_WILD_FIELD_IDLE_REARM_PENDING;
    if (OverworldWildSpawns_PopulationControl(
            OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE,
            0)) {
        residentData->pendingFlags |=
            OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
    }
    if (IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)
        && OverworldWildSpawns_IsPlayerBallProjectileActive()) {
        (void)OverworldWildSpawns_ApplyPresentationCommand(
            fieldSystem,
            state,
            OW_WILD_HELPER_PRESENTATION_SUSPEND,
            0);
    }
    OverworldWildSpawns_CancelNativeHeldMovement(state, fieldSystem);
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (state->spawns[i].active
            && state->spawns[i].mapId == fieldSystem->location->mapId) {
            return;
        }
    }
    /* The frame task discards its interrupted staged refill while busy. */
    residentData->pendingFlags |=
        OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_OverlayOnPlayerFrame(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    OverworldActorPopulationFrameCall frameCall;
    OverworldActorFrameResult actorFrame;
    BOOL mountActive;
    int i;

    frameCall.version = OVERWORLD_ACTOR_POPULATION_FRAME_CALL_VERSION;
    frameCall.size = sizeof(frameCall);
    frameCall.fieldSystem = fieldSystem;
    frameCall.actorSource = state;
    frameCall.flags = 0;
    frameCall.resultFlags = 0;
    if (state != NULL
        && state->movementRuntimeState != NULL
        && gOverworldWildFieldIdleRearmPending == 0) {
        frameCall.flags = OVERWORLD_ACTOR_POPULATION_FRAME_TIMER_ELIGIBLE;
    }
    actorFrame = OVERWORLD_ACTOR_SYSTEM_POPULATION_ENTRY->frame(&frameCall);
    gOverworldWildFieldIdleRearmPending |= frameCall.resultFlags
        & OVERWORLD_ACTOR_POPULATION_FRAME_REFILL_DUE;
    mountActive = OVERWORLD_MOUNT_OVERLAY_ENTRY->tick(
        fieldSystem,
        state,
        PAD_Read());
    if (state != NULL
        && state->movementRuntimeState != NULL
        && OW_WILD_RUNTIME(state)->movementNativeShadowRestorePending) {
        OW_WILD_RUNTIME(state)->movementNativeShadowRestorePending = FALSE;
        if (OverworldWildSpawns_IsMovementFieldContextCurrent(
                state,
                fieldSystem)) {
            for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
                LocalMapObject *object = state->spawns[i].object;

                if (!state->spawns[i].active
                    || !OverworldWildSpawns_IsCurrentSpawnObject(
                        fieldSystem,
                        &state->spawns[i])) {
                    continue;
                }
                OverworldWildSpawns_ClearObjectFlags(
                    object,
                    MAPOBJECTFLAG_UNK15);
                OverworldWildSpawns_ReconcileNativeShadow(
                    fieldSystem,
                    object);
            }
        }
    }
    return OverworldWildSpawns_TickPlayerBallProjectile(fieldSystem, state)
        || mountActive
        || actorFrame == OVERWORLD_ACTOR_FRAME_PENDING
        || (PAD_Read() & PAD_BUTTON_R) != 0;
}

static BOOL OverworldWildSpawns_TickHeavyMovementSlots(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    u16 currentSpawnMask,
    u16 participantMaskAtFrameStart,
    u16 heavyWorkMask)
{
    BOOL movementFinishedThisFrame = FALSE;
    int i;

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        BOOL currentSpawnObject =
            (currentSpawnMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0;

        if ((state->captureTargetMask
            & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0) {
            continue;
        }

        if (!currentSpawnObject
            && participantMaskAtFrameStart != 0
            && (OverworldWildSpawns_GetThrowParticipantMask(state)
                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) != 0) {
            OverworldWildSpawns_ClearThrowStateForSlot(state, i);
        }

        if ((heavyWorkMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i)) == 0) {
            continue;
        }

        if (!currentSpawnObject) {
            OverworldWildSpawns_ResetSlotMovementCommand(state, i, FALSE);
            OverworldWildSpawns_ClearStagedHopTarget(state, i);
            OverworldWildSpawns_ClearSpawnRunState(state, i);
            continue;
        }

        OW_WILD_PERF_INC(sOverworldWildPerfActiveFrameSlotsThisFrame);
        if (OverworldWildSpawns_IsTeleportMovementActive(state, i)) {
            /* The teleport-step visual owns this timer; avoid the generic flicker tick. */
        }
#if OW_WILD_SPAWNER_TELEPORT_CONDITIONAL_REAL_FLICKER
        else if (!OverworldWildSpawns_UpdateConditionalTeleportRealFlicker(state, i)) {
            OverworldWildSpawns_UpdateTeleportFlicker(state, i);
        }
#else
        else {
            OverworldWildSpawns_UpdateTeleportFlicker(state, i);
        }
#endif

        if (OverworldWildSpawns_IsMovementSlotInProgress(state, i)) {
            if (OverworldWildSpawns_TickStagedHopMovementListTask(state, fieldSystem, i, &movementFinishedThisFrame)) {
                continue;
            }
            if (OverworldWildSpawns_IsTeleportMovementActive(state, i)) {
                if (OverworldWildSpawns_TickTeleportMovementCommand(
                        state,
                        i,
                        &movementFinishedThisFrame)) {
                    continue;
                }
            }
            if (OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot(state, i)) {
                OverworldWildSpawns_ClearMovementSlotInProgress(state, i);
                if (OverworldWildSpawns_HandleFinishedStagedHopMovementCommand(
                        state,
                        fieldSystem,
                        i,
                        TRUE)) {
                    movementFinishedThisFrame = TRUE;
                    continue;
                }
                if (OverworldWildSpawns_HandleFinishedSpawnHopMovementCommand(state, fieldSystem, i)) {
                    movementFinishedThisFrame = TRUE;
                    continue;
                }
                OverworldWildSpawns_HandleFinishedMovementCommand(state, i);
                movementFinishedThisFrame = TRUE;
            }
            continue;
        }

        if (OverworldWildSpawns_TickCustomJumpRenderSettle(state, fieldSystem, i)) {
            continue;
        }

        if (state->movementStagedHopPending[i]) {
            if (state->movementCooldowns[i] > 0) {
                state->movementCooldowns[i]--;
                continue;
            }
            OverworldWildSpawns_ContinuePendingStagedHop(state, fieldSystem, i);
            continue;
        }

    }

    return movementFinishedThisFrame;
}

static void __attribute__((optimize("Os"))) OverworldWildSpawns_FrameMovementTask(SysTask *task, void *data)
{
    OverworldWildSpawnState *state = (OverworldWildSpawnState *)data;
    OverworldWildOverlayRuntimeState *runtime;
    FieldSystem *fieldSystem;
    BOOL playerStepMaintenanceRan = FALSE;
    BOOL spawnSetMayHaveChanged = FALSE;
    BOOL movementFinishedThisFrame = FALSE;
    u16 participantMaskAtFrameStart;
    u16 currentSpawnMask;
    u16 roleOwnedMask;
    u16 heavyWorkMask;
    u16 frameWorkMask;
    u16 selectedIdleMask;
    u8 populationWork;
    u32 frameWork;
#if OW_WILD_SPAWNER_IMMEDIATE_AI_AFTER_COMMAND_COMPLETION
    u16 movementInProgressBefore;
#endif

    (void)task;
    OW_WILD_PERF_RESET_FRAME();

    if (state == NULL) {
        OverworldWildSpawns_StopFrameMovementTask();
        return;
    }

    sOverworldWildMovementFrameTaskExecuting = TRUE;
    runtime = OW_WILD_RUNTIME(state);
    fieldSystem = state->movementFieldSystem;
    if (fieldSystem != NULL && fieldSystem->taskman != NULL) {
        runtime->queuedSpawnSlotPlusOne = 0;
        runtime->refillTerrainMask = 0;
        runtime->refillPositionChecksRemaining = 0;
        /* Native transitions own the live map objects once the field is busy. */
        if (OverworldWildSpawns_PopulationControl(
                OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE,
                0)
            && runtime->residentData != NULL) {
            runtime->residentData->pendingFlags |=
                OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        }
        (void)OverworldWildSpawns_PopulationControl(
            OVERWORLD_ACTOR_POPULATION_CONTROL_CANCEL_MAINTENANCE,
            0);
        OverworldWildSpawns_CancelNativeHeldMovement(state, fieldSystem);
        if (OverworldWildSpawns_IsPlayerBallProjectileActive()) {
            (void)OverworldWildSpawns_ApplyPresentationCommand(
                fieldSystem,
                state,
                OW_WILD_HELPER_PRESENTATION_SUSPEND,
                0);
        }
        OverworldWildSpawns_StopFrameMovementTask();
        return;
    }
    if (!OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)) {
        state->presentationRestorePending = TRUE;
        OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, FALSE);
        return;
    }
    currentSpawnMask = OverworldWildSpawns_GetCurrentMovementSpawnMask(
        state,
        fieldSystem);
    if (state->presentationRestorePending
        || runtime->spawnPresentations.managerRestoreMask != 0) {
        sOverworldWildMovementFrameTaskExecuting = FALSE;
        return;
    }
    /* Creation and preparation must not share one queue update. Leave the
     * resident REVEAL item pending while this one creation consumes the budget. */
    if (runtime->queuedSpawnSlotPlusOne != 0) {
        OverworldWildSpawns_CommitQueuedSpawn(state, fieldSystem);
        playerStepMaintenanceRan = TRUE;
        populationWork = OVERWORLD_ACTOR_POPULATION_WORK_NONE;
    } else if (runtime->refillTerrainMask != 0
        || runtime->refillPositionChecksRemaining != 0
        || sOverworldWildFlags.spawnWarmupPhase < 2) {
        /* Warm only: once ready, the scheduler still owns DESPAWN/REFILL.
         * Pending terrain attempts finish before consuming REVEAL. */
        populationWork = OVERWORLD_ACTOR_POPULATION_WORK_REFILL;
    } else {
        populationWork = OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_ADVANCE_MAINTENANCE,
        0);
    }
    if (populationWork == OVERWORLD_ACTOR_POPULATION_WORK_DESPAWN) {
        OverworldWildSpawns_DespawnFarMons(state, fieldSystem);
        playerStepMaintenanceRan = TRUE;
    } else if (populationWork == OVERWORLD_ACTOR_POPULATION_WORK_REFILL) {
        OverworldWildSpawns_TryRefill(state, fieldSystem);
        playerStepMaintenanceRan = TRUE;
    } else if (populationWork == OVERWORLD_ACTOR_POPULATION_WORK_REVEAL) {
        OverworldWildSpawns_RevealUnownedVanishedObjects(state, fieldSystem);
        playerStepMaintenanceRan = TRUE;
    }
    if (!playerStepMaintenanceRan
        && runtime->movementHelpSpawnParentSlotPlusOne != 0
        && runtime->movementHelpSpawnRemaining != 0) {
        OverworldWildSpawns_SpawnQueuedHelpChildren(state, fieldSystem);
        spawnSetMayHaveChanged = TRUE;
    }
    if (playerStepMaintenanceRan || spawnSetMayHaveChanged) {
        currentSpawnMask = OverworldWildSpawns_GetCurrentMovementSpawnMask(
            state,
            fieldSystem);
    }
    if (currentSpawnMask == 0) {
        if (OverworldWildSpawns_PopulationControl(
                OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE,
                0)) {
            sOverworldWildMovementFrameTaskExecuting = FALSE;
            return;
        }
        OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe();
        OverworldWildSpawns_ResetAllMovementCommands(state, TRUE, FALSE);
        OverworldWildSpawns_StopFrameMovementTask();
        return;
    }

    if (OverworldWildSpawns_TryStartCustomJumpRamProbe(state, fieldSystem)) {
        sOverworldWildMovementFrameTaskExecuting = FALSE;
        return;
    }

    participantMaskAtFrameStart = OverworldWildSpawns_GetThrowParticipantMask(state);
    frameWork = OverworldWildSpawns_GetFrameMovementWork(state);
    /* Mounted control owns the follower actor's complete movement policy.
     * Keep the slot in currentSpawnMask for population and task lifetime, but
     * never let wild AI mutate the same policy while the mount adapter drives
     * it as dependent presentation. */
    roleOwnedMask = OverworldWildSpawns_MountIsActive()
        ? OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(OW_WILD_FOLLOWER_SLOT)
        : 0;
    heavyWorkMask = (u16)(frameWork >> OW_WILD_SPAWNER_FRAME_WORK_HEAVY_SHIFT)
        & ~roleOwnedMask;
    frameWorkMask = ((u16)frameWork | participantMaskAtFrameStart)
        & currentSpawnMask
        & ~roleOwnedMask;
    selectedIdleMask = OverworldWildSpawns_SelectIdleAiWork(
        state,
        currentSpawnMask
            & ~roleOwnedMask
            & ~(u16)frameWork
            & ~participantMaskAtFrameStart);
    frameWorkMask |= selectedIdleMask;
    if (heavyWorkMask == 0) {
        OverworldWildSpawns_TickMovementParams(
            state,
            fieldSystem,
            TRUE,
            frameWorkMask
        );
        sOverworldWildMovementFrameTaskExecuting = FALSE;
        return;
    }

#if OW_WILD_SPAWNER_IMMEDIATE_AI_AFTER_COMMAND_COMPLETION
    movementInProgressBefore = state->movementInProgressMask;
#endif

    movementFinishedThisFrame = OverworldWildSpawns_TickHeavyMovementSlots(
        state,
        fieldSystem,
        currentSpawnMask,
        participantMaskAtFrameStart,
        heavyWorkMask);

    if (movementFinishedThisFrame) {
        state->movementBattleSettleFrames = OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES;
    }

#if OW_WILD_SPAWNER_IMMEDIATE_AI_AFTER_COMMAND_COMPLETION
    frameWorkMask |= movementInProgressBefore & ~state->movementInProgressMask;
#endif
    /* Late completion work cannot reclaim a role-owned actor. */
    frameWorkMask &= ~roleOwnedMask;
    OverworldWildSpawns_TickMovementParams(
        state,
        fieldSystem,
        TRUE,
        frameWorkMask
    );
    OverworldWildSpawns_UpdateMankeyTreeTopLayerProbe(state, fieldSystem);
    OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe(state, fieldSystem);
    OverworldWildSpawns_TickMovementCrashShake(state, fieldSystem);
    if (movementFinishedThisFrame) {
        OverworldWildSpawns_RevealUnownedVanishedObjects(state, fieldSystem);
    }
    sOverworldWildMovementFrameTaskExecuting = FALSE;
}
#else
static void OverworldWildSpawns_CleanupResidentTasks(void)
{
}

static void OverworldWildSpawns_TickFrameMovementDecisionCounter(void)
{
}

#endif

static BOOL OverworldWildSpawns_RequestBattleScript(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    int slot)
{
    if (fieldSystem == NULL
        || state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    return OverworldWildSpawns_DeferBattleScript(fieldSystem, state, slot);
#else
    return OverworldWildSpawns_QueueBattleScriptTask(fieldSystem, state->spawns[slot].object);
#endif
}

static void OverworldWildSpawns_ResetSlotState(
    OverworldWildSpawnState *state,
    int slot,
    BOOL deleteAuxiliaryObjects)
{
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
    OverworldWildSpawns_ResetSlotMovementCommand(state, slot, deleteAuxiliaryObjects);
#endif

    if (state->spawns[slot].object != NULL) {
        OverworldWildSpawns_SetNativeShadowSuppressed(
            state->spawns[slot].object,
            FALSE);
    }

    if (state->spawns[slot].active
        && state->spawns[slot].object != NULL
        && OverworldWildSpawns_IsCurrentSpawnObject(gFieldSysPtr, &state->spawns[slot])) {
        OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride(slot, state->spawns[slot].object);
    }
#if !OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
    OverworldWildSpawns_ClearThrowStateForSlot(state, slot);
#endif
    OverworldWildSpawns_ClearMankeyTreeTopProxyObject(state, slot, deleteAuxiliaryObjects);
    OverworldWildSpawns_ClearMankeyTreeTopCache(state, slot);
    OW_WILD_RUNTIME(state)->residentData->savedHp[slot] = 0;

    state->spawns[slot].object = NULL;
    state->spawns[slot].personality = 0;
    state->spawns[slot].mapId = MAP_NOTHING;
    state->spawns[slot].species = SPECIES_NONE;
    state->spawns[slot].form = 0;
    state->spawns[slot].level = 0;
    state->spawns[slot].terrain = 0;
    state->spawns[slot].shiny = FALSE;
    state->spawns[slot].active = FALSE;
    if (slot == OW_WILD_FOLLOWER_SLOT) {
        state->activeFollowerPartySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    }
    OW_WILD_RUNTIME(state)->playerBallCatchValues[slot] = 0;
    state->captureTargetMask &=
        (u16)~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask &=
        (u16)~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    OW_WILD_RUNTIME(state)->spawnPresentations.farSamples[slot] = 0;
    state->movementBehaviorClasses[slot] = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    state->movementActorControlModes[slot] =
        OW_WILD_ACTOR_CONTROL_AUTONOMOUS;
    OW_WILD_RUNTIME(state)->movementBehaviorLimitKeys[slot] = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    OverworldWildSpawns_ClearCachedBehaviorProfile(state, slot);
    OverworldWildSpawns_ClearConditionSlot(state, slot);
    if (state->movementQueuedBattleSlot == slot) {
        state->movementQueuedBattleSlot = -1;
    }
    if (state->pendingSlot == slot) {
        OverworldWildSpawns_ResetPendingBattle(state);
    }
    state->movementSpawnRunTargetX[slot] = 0;
    state->movementSpawnRunTargetY[slot] = 0;
    state->movementSpawnRunActive[slot] = FALSE;
    state->movementMankeyTreeTopProxyObjects[slot] = NULL;
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED
    sOverworldWildMankeyTreeTopPrioritySavedBits[slot] = 0;
    sOverworldWildMankeyTreeTopPriorityBitsSaved[slot] = FALSE;
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED
    sOverworldWildMankeyTreeTopSavedDrawCallbacks[slot] = NULL;
    sOverworldWildMankeyTreeTopDrawCallbacksSaved[slot] = FALSE;
#endif
#endif
}

static void OverworldWildSpawns_ResetPendingBattle(OverworldWildSpawnState *state)
{
    state->pendingSlot = -1;
    state->pendingPersonality = 0;
    state->pendingSpecies = SPECIES_NONE;
    state->pendingLevel = 0;
    state->pendingShiny = FALSE;
    state->pendingMapGeneration = 0;
    state->pendingEncounterGeneration = 0;
}

#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
static void OverworldWildSpawns_ClearContextLite(OverworldWildSpawnState *state)
{
    int i;

    if (state == NULL) {
        return;
    }

    if (state->movementRuntimeState != NULL
        && OW_WILD_RUNTIME(state)->residentData != NULL) {
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            if (state->spawns[i].active) {
                OverworldWildSpawns_ClearSlotAndSaveShiny(state, i, FALSE);
            }
        }
    } else {
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            OverworldWildSpawns_TrySaveShinyReservation(state, &state->spawns[i]);
        }
        memset(state->spawns, 0, sizeof(state->spawns));
    }
    memset(
        state->movementActorControlModes,
        OW_WILD_ACTOR_CONTROL_AUTONOMOUS,
        sizeof(state->movementActorControlModes));
    state->captureTargetMask = 0;

    state->justSpawned = FALSE;
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_RESET,
        0);
    state->headbuttSpawnCooldown = OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN;
    state->fishingSpawnCooldown = OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN;
    state->battleGraceSteps = 0;
}
#endif

#if !OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
static void OverworldWildSpawns_Clear(OverworldWildSpawnState *state, BOOL deleteObjects)
{
    int i;

    OverworldWildSpawns_CancelDeferredBattleScript();
    OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe();
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        OverworldWildSpawns_ClearSlotAndSaveShiny(state, i, deleteObjects);
    }
    memset(
        state->movementActorControlModes,
        OW_WILD_ACTOR_CONTROL_AUTONOMOUS,
        sizeof(state->movementActorControlModes));
    state->captureTargetMask = 0;

    state->justSpawned = FALSE;
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_RESET,
        0);
    state->headbuttSpawnCooldown = OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN;
    state->fishingSpawnCooldown = OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN;
    OverworldWildSpawns_ResetAmbientCryCooldown(state);
    state->battleGraceSteps = 0;
    state->movementQueuedBattleSlot = -1;
    OverworldWildSpawns_ClearQueuedHelpChildren(state);
    OverworldWildSpawns_ResetPendingBattle(state);
    if (state->followerReleaseState != OW_WILD_FOLLOWER_RELEASE_NONE) {
        state->followerReleaseState =
            OW_WILD_FOLLOWER_RELEASE_REQUESTED
            | (state->followerReleaseState
                & OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG);
    }
}
#endif

static BOOL OverworldWildSpawns_TryGetEncounterDataId(FieldSystem *fieldSystem, int *encounterDataId)
{
    const OverworldWildHelperOverlayEntry *helperEntry;

    if (fieldSystem == NULL || fieldSystem->location == NULL || encounterDataId == NULL) {
        return FALSE;
    }

    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL) {
        return FALSE;
    }
    return OverworldFieldService_TryGetEncounterDataIdForMap(
        fieldSystem->location->mapId,
        encounterDataId);
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_IsEnabledMap(
    FieldSystem *fieldSystem)
{
    int encounterDataId;

    if (!OverworldWildSpawns_IsFieldContextAvailable(fieldSystem)) {
        return FALSE;
    }
    return OverworldWildSpawns_TryGetEncounterDataId(
        fieldSystem,
        &encounterDataId);
}

static BOOL OverworldWildSpawns_IsFieldContextAvailable(FieldSystem *fieldSystem)
{
    return fieldSystem != NULL
        && fieldSystem->location != NULL
        && fieldSystem->location->mapId != MAP_NOTHING
        && fieldSystem->mapObjectMan != NULL
        && fieldSystem->playerAvatar != NULL;
}

static BOOL OverworldWildSpawns_TryGetSpawnTerrain(FieldSystem *fieldSystem, int x, int y, OverworldWildSpawnTerrain *terrain)
{
    u8 behavior;

    if (fieldSystem == NULL || terrain == NULL || x < 0 || y < 0) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (OverworldWildSpawns_IsSurfBehavior(behavior)) {
        *terrain = OW_WILD_SPAWN_TERRAIN_SURF;
    } else if (behavior == OW_WILD_TILE_ENCOUNTER_GRASS
        || behavior == OW_WILD_TILE_LONG_GRASS
        || behavior == 5
        || behavior == 8
        || behavior == 11
        || behavior == 37
        || behavior == 112
        || behavior == 119
        || behavior == 123
        || behavior == 163
        || behavior == 164) {
        *terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    } else {
        return FALSE;
    }

    return TRUE;
}

static BOOL __attribute__((noinline)) OverworldWildSpawns_TryGetFreeSlot(
    OverworldWildSpawnState *state,
    u8 start,
    u8 end,
    int *slot)
{
    u8 i;

    for (i = start; i < end; i++) {
        if (i != OW_WILD_FOLLOWER_SLOT && !state->spawns[i].active
            && (state->movementRuntimeState == NULL
                || OW_WILD_RUNTIME(state)->queuedSpawnSlotPlusOne != i + 1)) {
            *slot = i;
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL __attribute__((noinline, used))
OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem *fieldSystem, int x, int y)
{
    OW_WILD_PERF_INC(sOverworldWildPerfTargetScansThisFrame);
    return OverworldWildOccupancy_Query(fieldSystem, NULL,
        sOverworldWildCollisionIgnoredObject, x, y, 0,
        OVERWORLD_WILD_OCCUPANCY_OBJECTS);
}

static BOOL __attribute__((noinline, used))
OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(
    FieldSystem *fieldSystem,
    LocalMapObject *ignoredObject,
    int x,
    int y)
{
    return OverworldWildOccupancy_Query(fieldSystem, ignoredObject,
        sOverworldWildCollisionIgnoredObject, x, y, 0,
        OVERWORLD_WILD_OCCUPANCY_NONPLAYER);
}

static BOOL __attribute__((noinline, used, optimize("Os")))
OverworldWildSpawns_IsTileOccupiedOnSurface(
    FieldSystem *fieldSystem,
    LocalMapObject *ignoredObject,
    BOOL includePlayer,
    int x,
    int y,
    s32 targetBaseY)
{
    return OverworldWildOccupancy_Query(fieldSystem, ignoredObject,
        sOverworldWildCollisionIgnoredObject, x, y, targetBaseY,
        includePlayer ? OVERWORLD_WILD_OCCUPANCY_SURFACE_PLAYER
                      : OVERWORLD_WILD_OCCUPANCY_SURFACE);
}

static BOOL OverworldWildSpawns_IsWalkableLandTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if ((x | y) < 0) {
        return FALSE;
    }
    if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)) {
        return FALSE;
    }
    if (IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }

    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (behavior == OW_WILD_TILE_HEADBUTT || OverworldWildSpawns_IsSurfBehavior(behavior)) {
        return FALSE;
    }

    return TRUE;
}

#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE
static BOOL OverworldWildSpawns_IsCanopyPathTile(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_IsWalkableLandTile(fieldSystem, x, y);
}
#endif

static int OverworldWildSpawns_GetCustomJumpDistance(int dx, int dy)
{
    return OverworldWildSpawns_Max(
        OverworldWildSpawns_Abs(dx),
        OverworldWildSpawns_Abs(dy));
}

static BOOL OverworldWildSpawns_IsCustomJumpVectorShape(int dx, int dy)
{
    int absDx = OverworldWildSpawns_Abs(dx);
    int absDy = OverworldWildSpawns_Abs(dy);

    if (absDx == 0 && absDy == 0) {
        return FALSE;
    }

    if (absDx == 0 || absDy == 0) {
        return TRUE;
    }

#if OW_WILD_SPAWNER_CUSTOM_JUMP_ALLOW_DIAGONAL
    return absDx == absDy;
#else
    return FALSE;
#endif
}

static BOOL OverworldWildSpawns_TryGetCustomJumpVector(
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    int jumpDistance;
    u8 directions[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];

    if (!OverworldWildSpawns_IsCustomJumpVectorShape(dx, dy)
        || OverworldWildSpawns_BuildDirectedDirections(dx, dy, directions) == 0) {
        return FALSE;
    }

    jumpDistance = OverworldWildSpawns_GetCustomJumpDistance(dx, dy);
    if (jumpDistance < OW_WILD_SPAWNER_CUSTOM_JUMP_MIN_TILES
        || jumpDistance > (sOverworldWildSpawnHopPreparing
            ? OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE
            : OW_WILD_SPAWNER_CUSTOM_JUMP_MAX_TILES)) {
        return FALSE;
    }

    *direction = directions[0];
    *distance = (u8)jumpDistance;
    return TRUE;
}

static u8 OverworldWildSpawns_GetBehaviorHopMinDistance(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    if (profile == NULL) {
        return OW_WILD_SPAWNER_CUSTOM_JUMP_MIN_TILES;
    }
    return OverworldWildSpawns_GetControllerLane(
        profile,
        spotState)->hopMinDistance;
}

static u8 OverworldWildSpawns_GetBehaviorHopMaxDistance(
    const OverworldWildBehaviorProfile *profile,
    u8 spotState)
{
    u8 minDistance = OverworldWildSpawns_GetBehaviorHopMinDistance(profile, spotState);
    u8 maxDistance;

    if (profile == NULL) {
        return OW_WILD_SPAWNER_CUSTOM_JUMP_MAX_TILES;
    }
    maxDistance = OverworldWildSpawns_GetControllerLane(
        profile,
        spotState)->hopMaxDistance;
    if (maxDistance < minDistance) {
        return minDistance;
    }
    return maxDistance;
}

static const OverworldWildHelperOverlayEntry *OverworldWildSpawns_GetHelperOverlayEntry(void)
{
    const OverworldWildHelperOverlayEntry *entry;

    if (sOverworldWildHelperOverlayReady) {
        return OVERWORLD_WILD_HELPER_OVERLAY_ENTRY;
    }
    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)) {
        if (!HandleLoadOverlay(OVERLAY_OVERWORLD_WILD_HELPER, 0)) {
            return NULL;
        }
    }
    entry = OVERWORLD_WILD_HELPER_OVERLAY_ENTRY;

    if (!OVERWORLD_WILD_HELPER_OVERLAY_VALIDATE(
            OVERWORLD_WILD_HELPER_ENSURE_BEHAVIOR)) {
        return NULL;
    }

    sOverworldWildHelperOverlayReady = TRUE;
    return entry;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u16 allowedTile,
    int landingX,
    int landingY,
    int finalTargetX,
    int finalTargetY,
    u8 pendingMarker)
{
    const OverworldWildBehaviorProfileData *lane;
    LocalMapObject *object;
    OverworldWildDirectionStepContext stepContext;
    u8 direction;
    u8 distance;
    int objectX;
    int objectY;
    u8 spotState;
    BOOL flatWalk;
    u32 roleDecision;
    OverworldMotionDecision landingDecision;

    object = state->spawns[slot].object;
    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    spotState = state->movementSpotStates[slot];
    lane = OverworldWildSpawns_GetControllerLane(profile, spotState);
    flatWalk = pendingMarker == 0
        && lane->chillAction == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
    landingDecision = OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
            state,
            slot,
            fieldSystem,
            allowedTile | (flatWalk
                ? OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER
                : 0),
            landingX,
            landingY,
            finalTargetX,
            finalTargetY);
    state->movementStagedHopFinishWithTired[slot] = landingDecision;
    if (landingDecision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return FALSE;
    }
    if (flatWalk) {
        if ((landingX == objectX && landingY == objectY)
            || OverworldWildSpawns_Abs(landingX - objectX) > 1
            || OverworldWildSpawns_Abs(landingY - objectY) > 1) {
            return FALSE;
        }
        direction = OverworldWalk_DirectionFromDelta(
            landingX - objectX,
            landingY - objectY);
        if ((direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                    lane->hopAllowNonCardinal))
            || (direction > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                    lane->hopAllowNonCardinal))) {
            return FALSE;
        }
        distance = 1;
    } else if (!OverworldWildSpawns_TryGetBehaviorHopVector(
                   profile,
                   spotState,
                   landingX - objectX,
                   landingY - objectY,
                   &direction,
                   &distance)) {
        return FALSE;
    }
    if (!flatWalk) {
        u8 roleFlags = OVERWORLD_ROLE_CONTROLLER_INPUT_CHAIN_ENABLED;

        if (direction == OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE) {
            roleFlags |= OVERWORLD_ROLE_CONTROLLER_INPUT_DIRECTION_OPTIONAL;
        }
        roleDecision = OverworldWildSpawns_ReduceRole(
                slot,
                OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                    << OW_WILD_SPAWNER_ROLE_INPUT_COMMITTED_SHIFT
                | (u32)direction
                    << OW_WILD_SPAWNER_ROLE_INPUT_DIRECTION_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_INTENT_HOP
                    << OW_WILD_SPAWNER_ROLE_INPUT_INTENT_SHIFT
                | OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST,
                roleFlags);
        if ((roleDecision & OW_WILD_SPAWNER_ROLE_RESULT_ACCEPTED) == 0) {
            return FALSE;
        }
        direction = (u8)roleDecision;
    }

    state->movementStagedHopOriginX[slot] = (s16)objectX;
    state->movementStagedHopOriginY[slot] = (s16)objectY;
    state->movementStagedHopTargetX[slot] = (s16)finalTargetX;
    state->movementStagedHopTargetY[slot] = (s16)finalTargetY;
    state->movementStagedHopDistances[slot] = distance;
    state->movementStagedHopPending[slot] = pendingMarker != 0
        ? pendingMarker
        : flatWalk ? OW_WILD_SPAWNER_STAGED_WALK_PENDING : TRUE;
    if (flatWalk) {
        stepContext.state = state;
        stepContext.fieldSystem = fieldSystem;
        stepContext.object = object;
        stepContext.profile = profile;
        stepContext.primitives = NULL;
        stepContext.slot = (u8)slot;
        stepContext.allowedTile = allowedTile;
        stepContext.jumpLevel = profile->jumpLevel;
        stepContext.avoidPreviousTile = FALSE;
        if (OverworldWildSpawns_TryStartAcceleratedWalkStep(
                &stepContext,
                direction)) {
            return TRUE;
        }
    } else if (OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
            state,
            fieldSystem,
            slot,
            object,
            direction,
            distance,
            landingX,
            landingY,
            profile,
            pendingMarker != 0,
            0) == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return TRUE;
    }

    OverworldWildSpawns_ClearStagedHopTarget(state, slot);
    return FALSE;
}

static BOOL
OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    u16 allowedTile,
    int targetX,
    int targetY,
    const u8 *directions,
    int directionCount,
    u8 planMode)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    const OverworldWildBehaviorProfileData *lane;
    OverworldWildHelperHopConfig config;
    OverworldWildHelperHopResult result;
    OverworldWildBehaviorHopValidationContext validationContext;
    LocalMapObject *object;
    int objectX;
    int objectY;
    u8 spotState;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    spotState = state->movementSpotStates[slot];
    lane = OverworldWildSpawns_GetControllerLane(profile, spotState);
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL) {
        return FALSE;
    }

    OverworldWildSpawns_BuildHopHelperConfig(
        lane,
        objectX,
        objectY,
        targetX,
        targetY,
        directions,
        directionCount,
        planMode,
        &config);
    if (lane->chillAction == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) {
        config.minDistance = 1;
        config.maxDistance = 1;
        config.directionCount |= 0x20;
        if (state->movementStagedHopAvoidValid[slot]) {
            config.directionCount |= 0x80;
            config.directions[5] = lane->wanderStraightChance;
            config.directions[6] = (u8)OverworldWalk_DeltaX(
                state->movementLastDirections[slot]);
            config.directions[7] = (u8)OverworldWalk_DeltaY(
                state->movementLastDirections[slot]);
        }
    }
    validationContext.state = state;
    validationContext.fieldSystem = fieldSystem;
    validationContext.baseValidator =
        OverworldWildSpawns_IsBehaviorAllowedHopLandingTile;
    validationContext.slot = slot;
    validationContext.allowedTile = allowedTile
        | (lane->chillAction == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
            ? OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER
            : 0);
    validationContext.rejectPreviousTile =
        planMode == OW_WILD_HELPER_HOP_PLAN_FLEE;
    if (!helperEntry->planBehaviorHopStep(
            &config,
            OverworldWildSpawns_ValidateBehaviorHopLanding,
            &validationContext,
            &result)) {
        return FALSE;
    }
    if (planMode == OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY) {
        result.finalTargetX = result.landingX;
        result.finalTargetY = result.landingY;
    }

    return OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
        state,
        fieldSystem,
        slot,
        profile,
        allowedTile,
        result.landingX,
        result.landingY,
        result.finalTargetX,
        result.finalTargetY,
        0);
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_TryStartRandomBehaviorHopCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildHelperHopConfig config;
    OverworldWildHelperHopResult result;
    OverworldWildBehaviorHopValidationContext validationContext;
    const OverworldWildBehaviorProfileData *lane;
    LocalMapObject *object;
    int objectX;
    int objectY;
    u16 allowedTile;
    u8 spotState;
    BOOL flatWalk;

    object = state->spawns[slot].object;
    if (object == NULL || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    spotState = state->movementSpotStates[slot];
    lane = OverworldWildSpawns_GetControllerLane(profile, spotState);
    flatWalk = lane->chillAction == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER;
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        spotState);
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL) {
        return FALSE;
    }

    OverworldWildSpawns_BuildHopHelperConfig(
        lane,
        objectX,
        objectY,
        0,
        0,
        NULL,
        0,
        OW_WILD_HELPER_HOP_PLAN_DIRECT,
        &config);
    if (flatWalk) {
        config.minDistance = 1;
        config.maxDistance = 1;
        if (state->movementStagedHopAvoidValid[slot]) {
            /* The random helper uses the prior origin to reject a repeat and
             * holds an immediate reversal as its caller-level fallback. */
            config.targetX = state->movementStagedHopAvoidX[slot];
            config.targetY = state->movementStagedHopAvoidY[slot];
            config.directionCount = 0x80
                | (lane->avoidPreviousTile == OW_WILD_BEHAVIOR_BOOL_YES ? 0x40 : 0);
            config.planMode = (gf_rand() % 100) < lane->wanderStraightChance
                ? OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY
                : OW_WILD_HELPER_HOP_PLAN_DIRECT;
        }
    }
    validationContext.state = state;
    validationContext.fieldSystem = fieldSystem;
    validationContext.baseValidator =
        OverworldWildSpawns_IsBehaviorAllowedHopLandingTile;
    validationContext.slot = slot;
    validationContext.allowedTile = allowedTile
        | (flatWalk ? OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER : 0);
    validationContext.rejectPreviousTile = FALSE;
    if (!helperEntry->pickRandomBehaviorHop(
            &config,
            OverworldWildSpawns_ValidateBehaviorHopLanding,
            &validationContext,
            &result)) {
        state->movementCooldowns[slot] =
            OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
        return FALSE;
    }
    if (flatWalk
        && !state->movementStagedHopAvoidValid[slot]
        && OW_WILD_BEHAVIOR_WALK_USES_FIXED_FACING(lane->walkOptions)) {
        OverworldWildSpawns_SetObjectFacing(object, (u8)(gf_rand() & 3));
    }
    return OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
        state,
        fieldSystem,
        slot,
        profile,
        allowedTile,
        result.landingX,
        result.landingY,
        result.finalTargetX,
        result.finalTargetY,
        0);
}

static BOOL OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    int dx,
    int dy,
    const u8 *directions,
    int directionCount,
    u8 planMode)
{
    const OverworldWildBehaviorProfileData *lane;
    LocalMapObject *object;
    int objectX;
    int objectY;
    int targetX;
    int targetY;
    int distance;
    int i;
    int adjacentIndex;
    u8 minDistance;
    u8 maxDistance;
    u8 movementDirections;
    u16 allowedTile;
    u8 spotState;
    BOOL avoidPlayerTarget;

    if (state == NULL
        || fieldSystem == NULL
        || profile == NULL
        || directions == NULL
        || directionCount <= 0
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    targetX = objectX + dx;
    targetY = objectY + dy;
    spotState = state->movementSpotStates[slot];
    lane = OverworldWildSpawns_GetControllerLane(profile, spotState);
    movementDirections = lane->hopAllowNonCardinal;
    minDistance = OverworldWildSpawns_GetBehaviorHopMinDistance(profile, spotState);
    maxDistance = OverworldWildSpawns_GetBehaviorHopMaxDistance(profile, spotState);
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        state->movementSpotStates[slot]);
    avoidPlayerTarget = planMode == OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY
        && OverworldWildSpawns_IsPlayerTile(fieldSystem, targetX, targetY);

    if (lane->chillAction != OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        && !avoidPlayerTarget
        && OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
            state,
            fieldSystem,
            slot,
            profile,
            allowedTile,
            targetX,
            targetY,
            targetX,
            targetY,
            0)) {
        return TRUE;
    }

    if (planMode == OW_WILD_HELPER_HOP_PLAN_FLEE) {
        if (OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(
                state,
                fieldSystem,
                slot,
                profile,
                allowedTile,
                targetX,
                targetY,
                directions,
                directionCount,
                OW_WILD_HELPER_HOP_PLAN_FLEE)) {
            return TRUE;
        }
        goto blocked;
    }

    if (OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(
            fieldSystem,
            object,
            targetX,
            targetY)) {
        for (adjacentIndex = 0;
             adjacentIndex < OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT;
             adjacentIndex++) {
            int adjacentX = targetX
                + OverworldWildSpawns_MovementDirectionDeltaX(adjacentIndex);
            int adjacentY = targetY
                + OverworldWildSpawns_MovementDirectionDeltaY(adjacentIndex);

            if (OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    allowedTile,
                    adjacentX,
                    adjacentY,
                    adjacentX,
                    adjacentY,
                    0)) {
                return TRUE;
            }
        }
    }

    if (!OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
            state,
            slot,
            fieldSystem,
            allowedTile,
            targetX,
            targetY,
            targetX,
            targetY)
        && (dx != 0 || dy != 0)
        && OverworldWildSpawns_TryGetBehaviorHopVector(
            profile,
            spotState,
            dx,
            dy,
            NULL,
            NULL)) {
        goto blocked;
    }

    if (planMode == OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY) {
        if (OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(
                state,
                fieldSystem,
                slot,
                profile,
                allowedTile,
                targetX,
                targetY,
                directions,
                directionCount,
                OW_WILD_HELPER_HOP_PLAN_STOP_ONE_HOP_AWAY)) {
            return TRUE;
        }
        if (avoidPlayerTarget) {
            goto blocked;
        }
    }

    if (OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(
            state,
            fieldSystem,
            slot,
            profile,
            allowedTile,
            targetX,
            targetY,
            directions,
            directionCount,
            OW_WILD_HELPER_HOP_PLAN_DIRECT)) {
        return TRUE;
    }

    if (OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(movementDirections)
        && dx != 0
        && dy != 0) {
        int stepX = dx > 0 ? 1 : -1;
        int stepY = dy > 0 ? 1 : -1;

        for (distance = maxDistance; distance >= minDistance; distance--) {
            if (OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    allowedTile,
                    objectX + stepX * distance,
                    objectY + stepY * distance,
                    objectX + stepX * distance,
                    objectY + stepY * distance,
                    0)) {
                return TRUE;
            }
        }
    }

    if (!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(movementDirections)) {
        goto blocked;
    }
    for (i = 0; i < directionCount; i++) {
        u8 direction = directions[i];
        int stepX = OverworldWildSpawns_MovementDirectionDeltaX(direction);
        int stepY = OverworldWildSpawns_MovementDirectionDeltaY(direction);

        for (distance = maxDistance; distance >= minDistance; distance--) {
            if (OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand(
                    state,
                    fieldSystem,
                    slot,
                    profile,
                    allowedTile,
                    objectX + stepX * distance,
                    objectY + stepY * distance,
                    objectX + stepX * distance,
                    objectY + stepY * distance,
                    0)) {
                return TRUE;
            }
        }
    }

blocked:
    if (!OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(lane->walkOptions)) {
        OverworldWildSpawns_SetObjectFacing(object, directions[0]);
    }
    state->movementCooldowns[slot] = lane->hopPause;
    return FALSE;
}

static BOOL OverworldWildSpawns_IsFishingShoreTile(FieldSystem *fieldSystem, int x, int y)
{
    return x >= 0
        && y >= 0
        && OverworldWildSpawns_IsSurfBehavior(GetMetatileBehaviorAt(fieldSystem, x, y))
        && !OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y);
}

static BOOL OverworldWildSpawns_IsSpawnRunStartTile(
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int x,
    int y)
{
    OverworldWildSpawnTerrain resolvedTerrain;

    if (x < 0 || y < 0) {
        return FALSE;
    }

    switch (terrain) {
    case OW_WILD_SPAWN_TERRAIN_HEADBUTT:
        return OverworldWildSpawns_IsWalkableLandTile(fieldSystem, x, y);
    case OW_WILD_SPAWN_TERRAIN_FISHING:
        return OverworldWildSpawns_IsFishingShoreTile(fieldSystem, x, y);
    case OW_WILD_SPAWN_TERRAIN_SURF:
    case OW_WILD_SPAWN_TERRAIN_LAND:
    default:
        if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)
            || IsMetatileBlockedAt(fieldSystem, x, y)
            || !OverworldWildSpawns_TryGetSpawnTerrain(fieldSystem, x, y, &resolvedTerrain)) {
            return FALSE;
        }
        return resolvedTerrain == terrain;
    }
}

static BOOL OverworldWildSpawns_TryPickSpawnRunStart(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int targetX,
    int targetY,
    int *startX,
    int *startY)
{
    return OverworldWildSpawns_TryPickVisibleOffscreenOrigin(
        state,
        fieldSystem,
        terrain,
        OW_WILD_SPAWNER_SPAWN_MOVE_MAX_DISTANCE,
        targetX,
        targetY,
        startX,
        startY);
}

static void OverworldWildSpawns_ClearSpawnRunState(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    state->movementSpawnRunTargetX[slot] = 0;
    state->movementSpawnRunTargetY[slot] = 0;
    state->movementSpawnRunActive[slot] = OW_WILD_SPAWN_ENTRY_NONE;
}

static void __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_SetSpawnRunState(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    int targetX,
    int targetY,
    u8 entryMode)
{
    state->movementFieldSystem = fieldSystem;
    state->movementSpawnRunTargetX[slot] = (s16)targetX;
    state->movementSpawnRunTargetY[slot] = (s16)targetY;
    state->movementSpawnRunActive[slot] = entryMode;
}

static void OverworldWildSpawns_StartSpawnRun(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    int targetX,
    int targetY)
{
    if (state == NULL
        || fieldSystem == NULL
        || (u32)slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->spawns[slot].object == NULL) {
        return;
    }

    OverworldWildSpawns_SetSpawnRunState(
        state,
        fieldSystem,
        slot,
        targetX,
        targetY,
        OW_WILD_SPAWN_ENTRY_MOVE);
    /* Move From Off Screen changes only the target of the normal Owner lane. */
    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ResumeOwnerAfterAlert(
        state,
        slot,
        state->spawns[slot].object);
}

static void OverworldWildSpawns_SetPostSpawnStartupCooldown(
    OverworldWildSpawnState *state,
    int slot)
{
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    const OverworldWildBehaviorProfileData *lane;
    u8 locomotion;

    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    if (state->movementSpawnRunActive[slot] == OW_WILD_SPAWN_ENTRY_MOVE) {
        state->movementCooldowns[slot] = OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        if ((OW_WILD_RUNTIME(state)->movementFrameDrivenOwnerMask
                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0) {
            OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
        }
#endif
        return;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state,
        slot,
        &profile,
        &primitives);
    lane = OverworldWildSpawns_GetControllerLane(
        &profile,
        state->movementSpotStates[slot]);
    locomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
        &primitives,
        state->movementSpotStates[slot]);
    state->movementCooldowns[slot] = locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        ? lane->hopPause
        : locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER
        ? lane->walkPause
        : locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT
        ? lane->teleportPause
        : OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN;
}

static BOOL OverworldWildSpawns_UpdateSpawnMoveTargetState(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
    int objectX;
    int objectY;
    int targetX;
    int targetY;
    OverworldActorPolicyView policy;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_MOVE
        || !state->spawns[slot].active) {
        return FALSE;
    }

    if (object == NULL) {
        OverworldWildSpawns_ClearSpawnRunState(state, slot);
        return TRUE;
    }
    if (MapObject_IsSingleMovementActive(object)
        || OverworldWildSpawns_IsMovementSlotInProgress(state, slot)) {
        return TRUE;
    }
    if (OverworldActorPolicy_Inspect((u8)slot, &policy)
        && policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE
        && policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    targetX = state->movementSpawnRunTargetX[slot];
    targetY = state->movementSpawnRunTargetY[slot];
    if (objectX == targetX && objectY == targetY) {
        OverworldWildSpawns_SetObjectLandingTile(fieldSystem, object, targetX, targetY);
        OverworldWildSpawns_RefreshCanopyHopperVisualStateAtLanding(
            state,
            fieldSystem,
            slot,
            object);
        state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
        OverworldWildSpawns_ClearSpawnRunState(state, slot);
        OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
        OverworldWildSpawns_SetPostSpawnStartupCooldown(state, slot);
        return TRUE;
    }

    /* A normal tired cycle can end before the actor reaches B. Resume the
     * explicit spawn command through the Owner lane. */
    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_CHILL) {
        OverworldWildSpawns_ResumeOwnerAfterAlert(state, slot, object);
        return TRUE;
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_HandleFinishedSpawnHopMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    LocalMapObject *object;
    int targetX;
    int targetY;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || (state->movementSpawnRunActive[slot] != OW_WILD_SPAWN_ENTRY_HOP
            && state->movementSpawnRunActive[slot]
                != OW_WILD_SPAWN_ENTRY_FLY_IN)) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL || !state->spawns[slot].active) {
        OverworldWildSpawns_ClearSpawnRunState(state, slot);
        return TRUE;
    }

    targetX = state->movementSpawnRunTargetX[slot];
    targetY = state->movementSpawnRunTargetY[slot];
    /* This is an ordinary profile movement. Close its shared Motion and Walk
     * transactions before another segment can start. */
    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
    if ((int)OverworldWildSpawns_ObjectCurrentX(object) == targetX
        && (int)OverworldWildSpawns_ObjectCurrentY(object) == targetY) {
        OverworldWildSpawns_SetObjectLandingTile(
            fieldSystem,
            object,
            targetX,
            targetY);
        OverworldWildSpawns_RefreshCanopyHopperVisualStateAtLanding(
            state,
            fieldSystem,
            slot,
            object);
        state->movementPendingDirections[slot] = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
        state->movementPendingDistances[slot] = 0;
        state->movementStagedHopDistances[slot] = 0;
        state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
        OverworldWildSpawns_ClearSpawnRunState(state, slot);
        OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
        OverworldWildSpawns_SetPostSpawnStartupCooldown(state, slot);
    }
    return TRUE;
}

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
static BOOL OverworldWildSpawns_TryGetPlayerAdjacentMovementTarget(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile,
    int *targetX,
    int *targetY)
{
    LocalMapObject *object = state->spawns[slot].object;
    LocalMapObject *playerObject;
    u8 directionMask;
    u16 allowedTile;
    int objectX;
    int objectY;
    int playerX;
    int playerY;
    int playerFacing;
    int playerLeft;
    int direction;
    int directionCount;

    directionMask = OverworldWildSpawns_GetControllerLane(
        profile,
        state->movementSpotStates[slot])->playerAdjacentDirectionMasks;
    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject == NULL) {
        return FALSE;
    }
    playerFacing = playerObject->curFacing;
    if (playerFacing > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
        return FALSE;
    }
    playerLeft = playerFacing ^ (2u | (playerFacing >> 1));
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        profile,
        state->movementSpotStates[slot]);
    direction = OverworldWildSpawns_GetFacingTowardTile(
        playerX,
        playerY,
        objectX,
        objectY,
        OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP);
    for (directionCount = 0;
         directionCount < 4;
         directionCount++, direction = (direction + 1) & 3) {
        int candidateX;
        int candidateY;
        u8 relativeDirection;

        if (direction == playerFacing) {
            relativeDirection = OW_WILD_BEHAVIOR_PLAYER_ADJACENT_FRONT;
        } else if (direction == (playerFacing ^ 1)) {
            relativeDirection = OW_WILD_BEHAVIOR_PLAYER_ADJACENT_BEHIND;
        } else if (direction == playerLeft) {
            relativeDirection = OW_WILD_BEHAVIOR_PLAYER_ADJACENT_LEFT;
        } else {
            relativeDirection = OW_WILD_BEHAVIOR_PLAYER_ADJACENT_RIGHT;
        }
        if ((directionMask & relativeDirection) == 0) {
            continue;
        }
        candidateX = playerX + OverworldWildSpawns_MovementDirectionDeltaX(direction);
        candidateY = playerY + OverworldWildSpawns_MovementDirectionDeltaY(direction);
        if ((candidateX != objectX || candidateY != objectY)
            && !OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
                state,
                slot,
                fieldSystem,
                allowedTile,
                candidateX,
                candidateY,
                -1,
                -1)) {
            continue;
        }
        *targetX = candidateX;
        *targetY = candidateY;
        return TRUE;
    }
    return FALSE;
}

static BOOL OverworldWildSpawns_IsHeadbuttMapTile(FieldSystem *fieldSystem, int x, int y)
{
    if (fieldSystem == NULL || x < 0 || y < 0) {
        return FALSE;
    }

    return GetMetatileBehaviorAt(fieldSystem, x, y) == OW_WILD_TILE_HEADBUTT;
}

static BOOL OverworldWildSpawns_IsPlayableMapMatrixTile(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    const u8 *matrix;
    u32 blockX;
    u32 blockY;
    u32 blockIndex;

    if (fieldSystem == NULL || x < 0 || y < 0) {
        return FALSE;
    }
    matrix = (const u8 *)fieldSystem->map_matrix;
    if (matrix == NULL) {
        return FALSE;
    }
    blockX = (u32)x >> OW_WILD_MAP_BLOCK_SHIFT;
    blockY = (u32)y >> OW_WILD_MAP_BLOCK_SHIFT;
    if (blockX >= matrix[0] || blockY >= matrix[1]) {
        return FALSE;
    }
    blockIndex = blockX + blockY * matrix[0];
    /* Header zero is MAP_EVERYWHERE. The outdoor matrix uses it for blank
     * padding cells. Their placeholder land model can still return ordinary
     * Land behavior, but it is not a playable destination. */
    return *(const u16 *)(matrix + OW_WILD_MAP_MATRIX_HEADERS_OFFSET
        + blockIndex * sizeof(u16)) != MAP_EVERYWHERE;
}

static BOOL OverworldWildSpawns_TryGetLoadedMetatileBehavior(
    FieldSystem *fieldSystem,
    int x,
    int y,
    u8 *behavior)
{
    if (behavior == NULL
        || !OverworldWildSpawns_IsPlayableMapMatrixTile(
            fieldSystem,
            x,
            y)) {
        return FALSE;
    }
    *behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    /* The stock reader returns 0xFF when the target is outside its loaded
     * terrain store. It is an unavailable tile, not ordinary Land. */
    return *behavior != 0xFF;
}

static BOOL OverworldWildSpawns_IsLandMapTile(FieldSystem *fieldSystem, int x, int y)
{
    u8 behavior;

    if (!OverworldWildSpawns_TryGetLoadedMetatileBehavior(
            fieldSystem,
            x,
            y,
            &behavior)) {
        return FALSE;
    }
    if (behavior == OW_WILD_TILE_HEADBUTT || OverworldWildSpawns_IsSurfBehavior(behavior)) {
        return FALSE;
    }

    return !IsMetatileBlockedAt(fieldSystem, x, y);
}

#if OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS
static BOOL OverworldWildSpawns_IsHeadbuttTreeTopSouthLandAnchor(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_IsHeadbuttMapTile(fieldSystem, x, y)
        && OverworldWildSpawns_IsLandMapTile(fieldSystem, x, y + 1);
}

static BOOL OverworldWildSpawns_IsShiftedSouthLandTreeTop(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_IsHeadbuttMapTile(fieldSystem, x, y)
        && OverworldWildSpawns_IsHeadbuttTreeTopSouthLandAnchor(
            fieldSystem,
            x,
            y + OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES);
}

static BOOL OverworldWildSpawns_TryGetShiftedSouthLandTreeTop(
    FieldSystem *fieldSystem,
    int anchorX,
    int anchorY,
    int *targetX,
    int *targetY)
{
    int shiftedY;

    if (targetX == NULL
        || targetY == NULL
        || !OverworldWildSpawns_IsHeadbuttTreeTopSouthLandAnchor(fieldSystem, anchorX, anchorY)) {
        return FALSE;
    }

    shiftedY = anchorY - OW_WILD_SPAWNER_CANOPY_SOUTH_LAND_SHIFT_TILES;
    if (!OverworldWildSpawns_IsShiftedSouthLandTreeTop(fieldSystem, anchorX, shiftedY)) {
        return FALSE;
    }

    *targetX = anchorX;
    *targetY = shiftedY;
    return TRUE;
}

static BOOL OverworldWildSpawns_IsShiftedSouthLandAnchorHop(
    FieldSystem *fieldSystem,
    int startX,
    int startY,
    int targetX,
    int targetY)
{
    int shiftedX;
    int shiftedY;

    return OverworldWildSpawns_TryGetShiftedSouthLandTreeTop(
            fieldSystem,
            startX,
            startY,
            &shiftedX,
            &shiftedY)
        && shiftedX == targetX
        && shiftedY == targetY;
}
#endif

#if OW_WILD_SPAWNER_CANOPY_SHIFT_NORTH_LAND_ANCHORS
static BOOL OverworldWildSpawns_IsHeadbuttTreeTopNorthLandAnchor(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_IsHeadbuttMapTile(fieldSystem, x, y)
        && OverworldWildSpawns_IsLandMapTile(fieldSystem, x, y - 1);
}

static BOOL OverworldWildSpawns_IsShiftedNorthLandTreeTop(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_IsHeadbuttMapTile(fieldSystem, x, y)
        && OverworldWildSpawns_IsHeadbuttTreeTopNorthLandAnchor(
            fieldSystem,
            x,
            y - OW_WILD_SPAWNER_CANOPY_NORTH_LAND_SHIFT_TILES);
}

static BOOL OverworldWildSpawns_TryGetShiftedNorthLandTreeTop(
    FieldSystem *fieldSystem,
    int anchorX,
    int anchorY,
    int *targetX,
    int *targetY)
{
    int shiftedY;

    if (targetX == NULL
        || targetY == NULL
        || !OverworldWildSpawns_IsHeadbuttTreeTopNorthLandAnchor(fieldSystem, anchorX, anchorY)) {
        return FALSE;
    }

    shiftedY = anchorY + OW_WILD_SPAWNER_CANOPY_NORTH_LAND_SHIFT_TILES;
    if (!OverworldWildSpawns_IsShiftedNorthLandTreeTop(fieldSystem, anchorX, shiftedY)) {
        return FALSE;
    }

    *targetX = anchorX;
    *targetY = shiftedY;
    return TRUE;
}

static BOOL OverworldWildSpawns_IsShiftedNorthLandAnchorHop(
    FieldSystem *fieldSystem,
    int startX,
    int startY,
    int targetX,
    int targetY)
{
    int shiftedX;
    int shiftedY;

    return OverworldWildSpawns_TryGetShiftedNorthLandTreeTop(
            fieldSystem,
            startX,
            startY,
            &shiftedX,
            &shiftedY)
        && shiftedX == targetX
        && shiftedY == targetY;
}
#endif

static u16 __attribute__((optimize("Os")))
OverworldWildSpawns_GetCanopyTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    OverworldWildSurfaceHit hit;

    return OverworldWildSpawns_QuerySurface(fieldSystem, x, y, &hit)
            && hit.surfaceType == OW_WILD_SURFACE_TYPE_CANOPY
        ? OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY
        : 0;
}

static u16 __attribute__((optimize("Os")))
OverworldWildSpawns_GetTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y,
    BOOL includeNativeGround)
{
    OverworldWildSurfaceHit hit;

    if (OverworldWildSpawns_QuerySurface(fieldSystem, x, y, &hit)) {
        if (!includeNativeGround
            && hit.surfaceId == OW_WILD_SURFACE_ID_NATIVE_GROUND) {
            return 0;
        }
        return OW_WILD_SURFACE_TYPE_TERRAIN_MASK(hit.surfaceType);
    }
    return 0;
}

static u16 OverworldWildSpawns_GetElevatedTerrainBit(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    return OverworldWildSpawns_GetTerrainBit(fieldSystem, x, y, FALSE);
}

static BOOL OverworldWildSpawns_IsHeadbuttTreeTopLocation(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_GetElevatedTerrainBit(fieldSystem, x, y)
        == OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_DoesAllowedTileMatch(
    FieldSystem *fieldSystem,
    u16 allowedTerrainMask,
    u8 behavior,
    int x,
    int y)
{
    /* A catalogued surface can veto underlying grass, but it cannot turn a
     * non-grass metatile into grass. Reject that common failed-spawn case
     * before the surface catalog lookup. */
    if (allowedTerrainMask == OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS
        && behavior != OW_WILD_TILE_ENCOUNTER_GRASS
        && behavior != OW_WILD_TILE_LONG_GRASS) {
        return FALSE;
    }
    OverworldWildSurfaceHit hit;
    u16 elevatedTerrain = 0;

    /* Always keep catalogued-surface vetoes. Canopy is catalog-only; native
     * collision edges are not crown surfaces. */
    if (OverworldWildSpawns_QuerySurface(fieldSystem, x, y, &hit)) {
        elevatedTerrain = OW_WILD_SURFACE_TYPE_TERRAIN_MASK(hit.surfaceType);
    }

    if ((elevatedTerrain & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL) != 0) {
        return (allowedTerrainMask & elevatedTerrain) != 0;
    }
    return ((allowedTerrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER)
            && OverworldWildSpawns_IsSurfBehavior(behavior))
        || ((allowedTerrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS)
            && (behavior == OW_WILD_TILE_ENCOUNTER_GRASS
                || behavior == OW_WILD_TILE_LONG_GRASS))
        || ((allowedTerrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER)
            && OverworldWildSpawns_IsPlayerTile(fieldSystem, x, y))
        || ((allowedTerrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT)
            && OverworldWildSpawns_IsPlayerFrontTile(fieldSystem, x, y))
        || ((allowedTerrainMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND)
            && OverworldWildSpawns_IsLandMapTile(fieldSystem, x, y));
}

static BOOL OverworldWildSpawns_IsBehaviorAllowedMovementTile(
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int x,
    int y)
{
    return OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
        NULL,
        -1,
        fieldSystem,
        allowedTile,
        x,
        y,
        -1,
        -1);
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_IsMountedPlayerScriptedLandingTile(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    MAP_EVENTS *events;
    u32 i;

    events = fieldSystem->map_events;
    for (i = 0; i < events->num_warp_events; i++) {
        if (events->warp_events[i].x == x
            && events->warp_events[i].y == y) {
            return TRUE;
        }
    }
    for (i = 0; i < events->num_coord_events; i++) {
        const COORD_EVENT *event = &events->coord_events[i];

        if (x >= event->x && x < event->x + event->w
            && y >= event->y && y < event->y + event->h) {
            return TRUE;
        }
    }
    return FALSE;
}

static OverworldMotionDecision __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
    OverworldWildSpawnState *state,
    int slot,
    FieldSystem *fieldSystem,
    u16 allowedTile,
    int x,
    int y,
    int finalTargetX,
    int finalTargetY)
{
    OverworldWildSurfaceHit sourceSurface;
    OverworldWildSurfaceHit targetSurface;
    OverworldActorPolicyView policy;
    u8 behavior;
    u8 repositionGrid;
    int repositionX;
    int repositionY;
    int repositionStepX;
    int repositionStepY;
    BOOL tileAllowed = FALSE;
    BOOL targetIsSurface = FALSE;
    BOOL strictDiagonalWalk;
    LocalMapObject *movingObject = NULL;
    LocalMapObject *heightObject;
    OverworldMotionDecision decision;

    if (fieldSystem == NULL) {
        return OVERWORLD_MOTION_DECISION_PROFILE;
    }
    if (x < 0 || y < 0) {
        return OVERWORLD_MOTION_DECISION_BLOCKED;
    }
    /* Surface entries describe the whole map matrix, including tiles that
     * are not currently loaded. Reject those tiles before the catalog can
     * make one look like a viable Hop landing. */
    if (!OverworldWildSpawns_TryGetLoadedMetatileBehavior(
            fieldSystem,
            x,
            y,
            &behavior)) {
        return OVERWORLD_MOTION_DECISION_BLOCKED;
    }
    if (state != NULL
        && slot == OW_WILD_FOLLOWER_SLOT
        && OverworldWildSpawns_IsMountedPlayerScriptedLandingTile(
            fieldSystem,
            x,
            y)) {
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    }

    strictDiagonalWalk = (allowedTile
        & OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER) != 0;
    allowedTile &= ~OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER;
    if (state != NULL && state->spawns[slot].active) {
        movingObject = state->spawns[slot].object;
    }
    if (strictDiagonalWalk
        && movingObject != NULL
        && x != movingObject->xCurr
        && y != movingObject->yCurr) {
        decision = OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
                state,
                slot,
                fieldSystem,
                allowedTile & ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER,
                x,
                movingObject->yCurr,
                finalTargetX,
                finalTargetY);
        if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            return decision;
        }
        decision = OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
                state,
                slot,
                fieldSystem,
                allowedTile & ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER,
                movingObject->xCurr,
                y,
                finalTargetX,
                finalTargetY);
        if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            return decision;
        }
    }
    if (movingObject != NULL) {
        if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
            return OVERWORLD_MOTION_DECISION_PROFILE;
        }
        repositionGrid = policy.chainPauseAction;
        if ((repositionGrid & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)
            == OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER) {
            repositionStepX = x - movingObject->xCurr;
            repositionStepY = y - movingObject->yCurr;
            if ((policy.chainStepsRemaining
                    & OW_WILD_SPAWNER_CHAIN_REPOSITION_SKID) != 0) {
                repositionStepX = (repositionStepX > 0)
                    - (repositionStepX < 0);
                repositionStepY = (repositionStepY > 0)
                    - (repositionStepY < 0);
            }
            repositionX = (repositionGrid & 3) - 1 + repositionStepX;
            repositionY = ((repositionGrid >> 2) & 3) - 1 + repositionStepY;
            if ((u32)(repositionX + 1) > 2
                || (u32)(repositionY + 1) > 2) {
                return OVERWORLD_MOTION_DECISION_BLOCKED;
            }
        }
    }
    if (OverworldWildSpawns_QuerySurface(fieldSystem, x, y, &targetSurface)) {
        tileAllowed = (allowedTile
            & OW_WILD_SURFACE_TYPE_TERRAIN_MASK(targetSurface.surfaceType)) != 0;
        targetIsSurface = targetSurface.surfaceId
            != OW_WILD_SURFACE_ID_NATIVE_GROUND;
        if (targetSurface.surfaceId == OW_WILD_SURFACE_ID_NATIVE_CANOPY) {
            heightObject = movingObject;
            if (heightObject == NULL && fieldSystem->playerAvatar != NULL) {
                heightObject = fieldSystem->playerAvatar->mapObject;
            }
            if (heightObject == NULL) {
                return OVERWORLD_MOTION_DECISION_PROFILE;
            }
            targetSurface.height = OverworldWildSpawns_GetObjectGroundBaseYAt(
                fieldSystem,
                heightObject,
                x,
                y);
        }
    } else {
        tileAllowed = OverworldWildSpawns_DoesAllowedTileMatch(
            fieldSystem,
            allowedTile
                & ~(OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_SURFACE_ALL
                    & ~OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY),
            behavior,
            x,
            y);
    }
    if (movingObject != NULL
        && targetIsSurface
        && OverworldWildSpawns_QuerySurface(
            fieldSystem,
            movingObject->xCurr,
            movingObject->yCurr,
            &sourceSurface)
        && sourceSurface.surfaceId != OW_WILD_SURFACE_ID_NATIVE_GROUND
        && sourceSurface.surfaceId != targetSurface.surfaceId) {
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    }
    if (!tileAllowed) {
        return OVERWORLD_MOTION_DECISION_TERRAIN;
    }
    if (OverworldWildSpawns_IsPlayerTile(fieldSystem, x, y)
        && ((allowedTile & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER) != 0
            || (x == finalTargetX && y == finalTargetY))) {
        if (targetIsSurface) {
            tileAllowed = !OverworldWildSpawns_IsTileOccupiedOnSurface(
                fieldSystem,
                movingObject,
                FALSE,
                x,
                y,
                targetSurface.height);
        } else {
            tileAllowed = !OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(
            fieldSystem,
            movingObject,
            x,
                y);
        }
    } else if (targetIsSurface) {
        tileAllowed = !OverworldWildSpawns_IsTileOccupiedOnSurface(
            fieldSystem,
            movingObject,
            TRUE,
            x,
            y,
            targetSurface.height);
    } else {
        tileAllowed = !OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y);
    }
    return tileAllowed ? OVERWORLD_MOTION_DECISION_ACCEPTED
        : OVERWORLD_MOTION_DECISION_OCCUPIED;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
    OverworldWildSpawnState *state, int slot, FieldSystem *fieldSystem,
    u16 allowedTile, int x, int y, int finalTargetX, int finalTargetY)
{
    return OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
        state, slot, fieldSystem, allowedTile, x, y, finalTargetX, finalTargetY)
        == OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static BOOL OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile(FieldSystem *fieldSystem, int x, int y)
{
    return OverworldWildSpawns_IsHeadbuttTreeTopLocation(fieldSystem, x, y);
}

static BOOL __attribute__((noinline)) OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    int x,
    int y)
{
    BOOL result;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->location == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || x < 0
        || y < 0
        || !state->spawns[slot].active
        || !OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)) {
        return FALSE;
    }

    if (OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheValid[slot]
        && OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheMapId[slot] == fieldSystem->location->mapId
        && OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheX[slot] == x
        && OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheY[slot] == y) {
        return OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheResult[slot];
    }

    result = OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile(fieldSystem, x, y);
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheValid[slot] = TRUE;
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheResult[slot] = result;
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheX[slot] = (s16)x;
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheY[slot] = (s16)y;
    OW_WILD_RUNTIME(state)->movementMankeyTreeTopCacheMapId[slot] = fieldSystem->location->mapId;
    return result;
}

#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_LATE_DRAW_EFFECT_ENABLED
static BOOL OverworldWildSpawns_IsMankeyTreeTopLateDrawEffectValid(
    const OverworldWildMankeyTreeTopLateDrawEffectWork *work)
{
    int x;
    int y;

    if (work == NULL
        || work->state == NULL
        || work->fieldSystem == NULL
        || work->object == NULL
        || work->slot < 0
        || work->slot >= OW_WILD_MAX_SPAWNS
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(work->state, work->fieldSystem)
        || !OverworldWildSpawns_IsCurrentMapObject(work->fieldSystem, work->object)
        || !work->state->spawns[work->slot].active
        || !OverworldWildSpawns_IsCanopyHopperTreeTopSlot(work->state, work->slot)
        || work->state->spawns[work->slot].object != work->object
        || !OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettled[work->slot]) {
        return FALSE;
    }

    x = OverworldWildSpawns_ObjectCurrentX(work->object);
    y = OverworldWildSpawns_ObjectCurrentY(work->object);
    return OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached(
        work->state,
        work->fieldSystem,
        work->slot,
        x,
        y);
}

static BOOL OverworldWildSpawns_MankeyTreeTopLateDrawEffectInit(void *effect, void *work)
{
    const OverworldWildMankeyTreeTopLateDrawEffectInit *init;
    OverworldWildMankeyTreeTopLateDrawEffectWork *effectWork = work;

    (void)effect;
    if (effectWork == NULL) {
        return FALSE;
    }

    init = FieldEffect_GetInitData(effect);
    if (init == NULL
        || init->slot < 0
        || init->slot >= OW_WILD_MAX_SPAWNS
        || init->state == NULL
        || init->fieldSystem == NULL
        || init->object == NULL) {
        effectWork->state = NULL;
        effectWork->fieldSystem = NULL;
        effectWork->object = NULL;
        effectWork->slot = -1;
        return FALSE;
    }

    effectWork->state = init->state;
    effectWork->fieldSystem = init->fieldSystem;
    effectWork->object = init->object;
    effectWork->slot = init->slot;
    effectWork->markerTimer = OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_FRAMES;
    return TRUE;
}

static void OverworldWildSpawns_MankeyTreeTopLateDrawEffectDestroy(void *effect, void *work)
{
    OverworldWildMankeyTreeTopLateDrawEffectWork *effectWork = work;
    int slot;

    (void)effect;
    if (effectWork == NULL) {
        return;
    }

    slot = effectWork->slot;
    if (slot >= 0
        && slot < OW_WILD_MAX_SPAWNS
        && sOverworldWildMankeyTreeTopLateDrawEffects[slot] == effect) {
        sOverworldWildMankeyTreeTopLateDrawEffects[slot] = NULL;
    }

    effectWork->state = NULL;
    effectWork->fieldSystem = NULL;
    effectWork->object = NULL;
    effectWork->slot = -1;
    effectWork->markerTimer = 0;
}

static void OverworldWildSpawns_MankeyTreeTopLateDrawEffectUpdate(void *effect, void *work)
{
    OverworldWildMankeyTreeTopLateDrawEffectWork *effectWork = work;

    if (!OverworldWildSpawns_IsMankeyTreeTopLateDrawEffectValid(effectWork)) {
        if (effectWork != NULL
            && effectWork->slot >= 0
            && effectWork->slot < OW_WILD_MAX_SPAWNS
            && sOverworldWildMankeyTreeTopLateDrawEffects[effectWork->slot] == effect) {
            sOverworldWildMankeyTreeTopLateDrawEffects[effectWork->slot] = NULL;
        }
        ov01_021F1640(effect);
        return;
    }

    effectWork->markerTimer++;
    if (effectWork->markerTimer >= OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_FRAMES) {
        effectWork->markerTimer = 0;
        OverworldWildSpawns_ShowBubble(
            effectWork->object,
            OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_ID);
    }
}

static void OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender(void *effect, void *work)
{
    OverworldWildMankeyTreeTopLateDrawEffectWork *effectWork = work;

    (void)effect;
    if (!OverworldWildSpawns_IsMankeyTreeTopLateDrawEffectValid(effectWork)) {
        return;
    }

    (void)effectWork;
}

static void OverworldWildSpawns_ClearMankeyTreeTopLateDrawEffect(int slot)
{
    void *effect;

    if (slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    effect = sOverworldWildMankeyTreeTopLateDrawEffects[slot];
    sOverworldWildMankeyTreeTopLateDrawEffects[slot] = NULL;
    if (effect != NULL) {
        ov01_021F1640(effect);
    }
}
#else
static void OverworldWildSpawns_ClearMankeyTreeTopLateDrawEffect(int slot)
{
    (void)slot;
}
#endif

static void OverworldWildSpawns_EnsureMankeyTreeTopLateDrawEffect(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
#if !OW_WILD_SPAWNER_MANKEY_TREE_TOP_LATE_DRAW_EFFECT_ENABLED
    (void)state;
    (void)fieldSystem;
    (void)slot;
    (void)object;
#else
    OverworldWildMankeyTreeTopLateDrawEffectInit init;
    VecFx32 position;
    void *effectContext;
    void *effect;

    if (state == NULL
        || fieldSystem == NULL
        || object == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || sOverworldWildMankeyTreeTopLateDrawEffects[slot] != NULL
        || !OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettled[slot]) {
        return;
    }

    effectContext = ov01_021F146C(object);
    if (effectContext == NULL) {
        return;
    }

    init.state = state;
    init.fieldSystem = fieldSystem;
    init.object = object;
    init.slot = slot;
    position.x = (fx32)object->posVec[0];
    position.y = (fx32)object->posVec[1];
    position.z = (fx32)object->posVec[2];

    effect = ov01_021F1620(
        effectContext,
        &sOverworldWildMankeyTreeTopLateDrawEffectDescriptor,
        &position,
        slot,
        &init,
        0);
    if (effect != NULL) {
        sOverworldWildMankeyTreeTopLateDrawEffects[slot] = effect;
    }
#endif
}

static void OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
    int objectX;
    int objectY;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || !OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)
        || object == NULL) {
        return;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    if (OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached(state, fieldSystem, slot, objectX, objectY)) {
        OverworldWildSpawns_ApplyMankeyTreeTopRenderOverride(slot, object);
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        OverworldWildSpawns_ClearMankeyTreeTopProxyObject(state, slot, TRUE);
        OverworldWildSpawns_EnsureMankeyTreeTopLateDrawEffect(state, fieldSystem, slot, object);
    } else {
        OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride(slot, object);
        OverworldWildSpawns_ClearMankeyTreeTopProxyObject(state, slot, TRUE);
        OverworldWildSpawns_ClearMankeyTreeTopLateDrawEffect(slot);
    }
}

#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED
static void OverworldWildSpawns_SetMankeyTreeTopLayerProbePhase(u8 phase)
{
    GX_EngineAToggleLayers(OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_2, phase != 0);
    GX_EngineAToggleLayers(OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_4, phase != 1);
    GX_EngineAToggleLayers(OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_8, phase != 2);
}

static void OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe(void)
{
    GX_EngineAToggleLayers(OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_2, TRUE);
    GX_EngineAToggleLayers(OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_4, TRUE);
    GX_EngineAToggleLayers(OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_MASK_8, TRUE);
    sOverworldWildMankeyTreeTopLayerProbeActive = FALSE;
    sOverworldWildMankeyTreeTopLayerProbeTimer = 0;
    sOverworldWildMankeyTreeTopLayerProbePhase = 0;
}

static BOOL OverworldWildSpawns_AnyMankeyOnHeadbuttTreeTopTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    int i;

    if (state == NULL
        || fieldSystem == NULL
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)) {
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *object = state->spawns[i].object;

        if (!state->spawns[i].active
            || !OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, i)
            || object == NULL
            || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)) {
            continue;
        }

        if (OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached(
                state,
                fieldSystem,
                i,
                OverworldWildSpawns_ObjectCurrentX(object),
                OverworldWildSpawns_ObjectCurrentY(object))) {
            return TRUE;
        }
    }

    return FALSE;
}
#else
static void OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe(void)
{
}
#endif

static void OverworldWildSpawns_UpdateMankeyTreeTopLayerProbe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
#if !OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED
    (void)state;
    (void)fieldSystem;
    return;
#else
    if (!OverworldWildSpawns_AnyMankeyOnHeadbuttTreeTopTile(state, fieldSystem)) {
        if (sOverworldWildMankeyTreeTopLayerProbeActive) {
            OverworldWildSpawns_RestoreMankeyTreeTopLayerProbe();
        }
        return;
    }

    if (!sOverworldWildMankeyTreeTopLayerProbeActive) {
        sOverworldWildMankeyTreeTopLayerProbeActive = TRUE;
        sOverworldWildMankeyTreeTopLayerProbeTimer = 0;
        sOverworldWildMankeyTreeTopLayerProbePhase = 0;
        OverworldWildSpawns_SetMankeyTreeTopLayerProbePhase(
            sOverworldWildMankeyTreeTopLayerProbePhase);
        return;
    }

    sOverworldWildMankeyTreeTopLayerProbeTimer++;
    if (sOverworldWildMankeyTreeTopLayerProbeTimer < OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_FRAMES) {
        return;
    }

    sOverworldWildMankeyTreeTopLayerProbeTimer = 0;
    sOverworldWildMankeyTreeTopLayerProbePhase++;
    if (sOverworldWildMankeyTreeTopLayerProbePhase >= OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_PHASES) {
        sOverworldWildMankeyTreeTopLayerProbePhase = 0;
    }
    OverworldWildSpawns_SetMankeyTreeTopLayerProbePhase(
        sOverworldWildMankeyTreeTopLayerProbePhase);
#endif
}

static void OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
#if !OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ENABLED
    (void)state;
    (void)fieldSystem;
    return;
#else
    int i;
    BOOL foundMankey = FALSE;

    if (state == NULL
        || fieldSystem == NULL
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)) {
        sOverworldWildMankeyTreeTopBubbleProbeTimer = 0;
        return;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        LocalMapObject *object = state->spawns[i].object;

        if (!state->spawns[i].active
            || !OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, i)
            || !OW_WILD_RUNTIME(state)->movementMankeyTreeTopSettled[i]
            || object == NULL
            || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, object)
            || !OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached(
                state,
                fieldSystem,
                i,
                OverworldWildSpawns_ObjectCurrentX(object),
                OverworldWildSpawns_ObjectCurrentY(object))) {
            continue;
        }

        foundMankey = TRUE;
        break;
    }

    if (!foundMankey) {
        sOverworldWildMankeyTreeTopBubbleProbeTimer = 0;
        return;
    }

    sOverworldWildMankeyTreeTopBubbleProbeTimer++;
    if (sOverworldWildMankeyTreeTopBubbleProbeTimer < OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_FRAMES) {
        return;
    }

    sOverworldWildMankeyTreeTopBubbleProbeTimer = 0;
    OverworldWildSpawns_ShowBubble(
        state->spawns[i].object,
        OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ID);
#endif
}

#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
static void OverworldWildSpawns_RecordCustomJumpRamObject(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object,
    int stage)
{
    sOverworldWildCustomJumpRamStage = stage;
    sOverworldWildCustomJumpRamSlot = slot;
    if (stage != 14 && stage != 15) {
        sOverworldWildCustomJumpRamFinalLanding = FALSE;
    }
    if (state != NULL && slot >= 0 && slot < OW_WILD_MAX_SPAWNS) {
        sOverworldWildCustomJumpRamPending = state->movementStagedHopPending[slot];
        sOverworldWildCustomJumpRamActive =
            OW_WILD_RUNTIME(state)->movementCustomJumpActive[slot];
#if OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS
        sOverworldWildCustomJumpRamVisibleLeg =
            sOverworldWildCustomJumpVisibleLegFinished[slot];
#else
        sOverworldWildCustomJumpRamVisibleLeg = FALSE;
#endif
        if (state->movementStagedHopPending[slot] || stage < 15) {
            sOverworldWildCustomJumpRamStartX = state->movementStagedHopOriginX[slot];
            sOverworldWildCustomJumpRamStartY = state->movementStagedHopOriginY[slot];
            sOverworldWildCustomJumpRamTargetX = state->movementStagedHopTargetX[slot];
            sOverworldWildCustomJumpRamTargetY = state->movementStagedHopTargetY[slot];
        }
    }
    if (object != NULL) {
        sOverworldWildCustomJumpRamCurrentX = OverworldWildSpawns_ObjectCurrentX(object);
        sOverworldWildCustomJumpRamCurrentY = OverworldWildSpawns_ObjectCurrentY(object);
        sOverworldWildCustomJumpRamRenderX =
            ((s32)object->posVec[0]) / OW_WILD_SPAWNER_TILE_FX32;
        sOverworldWildCustomJumpRamRenderY =
            ((s32)object->posVec[2]) / OW_WILD_SPAWNER_TILE_FX32;
        sOverworldWildCustomJumpRamRenderFx32X = (s32)object->posVec[0];
        sOverworldWildCustomJumpRamRenderFx32Y = (s32)object->posVec[2];
        sOverworldWildCustomJumpRamFlags = (int)object->flags;
    }
}

static BOOL OverworldWildSpawns_TryPickCustomJumpRamProbeTarget(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    int *targetX,
    int *targetY,
    u8 *direction,
    u8 *distance)
{
    int objectX;
    int objectY;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || targetX == NULL
        || targetY == NULL
        || direction == NULL
        || distance == NULL) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    *targetX = objectX + OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE_MIN_TILES;
    *targetY = objectY + OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE_MIN_TILES;
    return OverworldWildSpawns_TryGetCustomJumpVector(
        *targetX - objectX,
        *targetY - objectY,
        direction,
        distance);
}
#endif

#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
static BOOL OverworldWildSpawns_TryStartCustomJumpRamProbe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    u32 pad;
    int slot;

    if (state == NULL || fieldSystem == NULL) {
        return FALSE;
    }

    pad = PAD_Read();
    if ((pad & OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE_KEYS)
        != OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE_KEYS) {
        sOverworldWildCustomJumpRamProbeKeyDown = FALSE;
        return FALSE;
    }
    if (sOverworldWildCustomJumpRamProbeKeyDown) {
        return FALSE;
    }

    sOverworldWildCustomJumpRamProbeKeyDown = TRUE;
    sOverworldWildCustomJumpRamProbeTriggers++;
    sOverworldWildCustomJumpRamStage = 1;
    sOverworldWildCustomJumpRamProbeActiveSlots = 0;
    sOverworldWildCustomJumpRamProbeCurrentSlots = 0;
    sOverworldWildCustomJumpRamProbeMankeySlots = 0;
    sOverworldWildCustomJumpRamProbeObjectSlots = 0;
    sOverworldWildCustomJumpRamProbeLastSpecies = SPECIES_NONE;

    state->headbuttSpawnCooldown = 0;
    state->fishingSpawnCooldown = 0;
    OverworldWildSpawns_TryRefill(state, fieldSystem);
    OverworldWildSpawns_CommitQueuedSpawn(state, fieldSystem);

    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        LocalMapObject *object;
        OverworldWildBehaviorProfile profile;
        int targetX;
        int targetY;
        u8 direction;
        u8 distance;

        if (!state->spawns[slot].active
            || (slot == OW_WILD_FOLLOWER_SLOT
                && OverworldWildSpawns_MountIsActive())) {
            continue;
        }
        sOverworldWildCustomJumpRamProbeActiveSlots++;
        sOverworldWildCustomJumpRamProbeLastSpecies = state->spawns[slot].species;
        if (!OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
            continue;
        }
        sOverworldWildCustomJumpRamProbeCurrentSlots++;
        if (!OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)) {
            continue;
        }
        sOverworldWildCustomJumpRamProbeMankeySlots++;

        object = state->spawns[slot].object;
        if (object == NULL) {
            continue;
        }
        sOverworldWildCustomJumpRamProbeObjectSlots++;

        if (OverworldWildSpawns_IsMovementSlotInProgress(state, slot)) {
            OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
        }
        if (MapObject_IsSingleMovementActive(object)) {
            MapObject_ClearSingleMovementActive(object);
        }
        OverworldWildSpawns_ClearStagedHopTarget(state, slot);
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 2);
        if (!OverworldWildSpawns_TryPickCustomJumpRamProbeTarget(
                state,
                fieldSystem,
                slot,
                object,
                &targetX,
                &targetY,
                &direction,
                &distance)) {
            sOverworldWildCustomJumpRamProbeFailures++;
            OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 3);
            sOverworldWildCustomJumpRamProbeKeyDown = FALSE;
            return TRUE;
        }

        OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
            state, slot, &profile, NULL);
        if (!OverworldWildSpawns_StageHopTarget(
                state,
                fieldSystem,
                slot,
                object,
                &profile,
                targetX,
                targetY,
                direction,
                distance,
                FALSE)) {
            sOverworldWildCustomJumpRamProbeFailures++;
            OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 4);
            sOverworldWildCustomJumpRamProbeKeyDown = FALSE;
            return TRUE;
        }

        sOverworldWildCustomJumpRamProbeStarts++;
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 5);
        if (OverworldWildSpawns_ExecutePendingStagedHop(
                state,
                fieldSystem,
                slot,
                object,
                &profile)) {
            return TRUE;
        }

        sOverworldWildCustomJumpRamProbeFailures++;
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 17);
        sOverworldWildCustomJumpRamProbeKeyDown = FALSE;
        return TRUE;
    }

    sOverworldWildCustomJumpRamProbeFailures++;
    sOverworldWildCustomJumpRamStage = 6;
    sOverworldWildCustomJumpRamProbeKeyDown = FALSE;
    return TRUE;
}
#endif

static BOOL OverworldWildSpawns_IsAtStagedHopTarget(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    int objectX;
    int objectY;

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    return objectX == state->movementStagedHopTargetX[slot]
        && objectY == state->movementStagedHopTargetY[slot];
}

#if 0
static u8 OverworldWildSpawns_GetCanopyRenderHopDuration(u8 distance)
{
    u16 frames;

    if (distance == 0) {
        distance = OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP;
    }

    frames = (u16)distance * OW_WILD_SPAWNER_CANOPY_HOPPER_RENDER_HOP_FRAMES_PER_TILE;
    if (frames < OW_WILD_SPAWNER_CANOPY_HOPPER_RENDER_HOP_MIN_FRAMES) {
        frames = OW_WILD_SPAWNER_CANOPY_HOPPER_RENDER_HOP_MIN_FRAMES;
    }
    if (frames > 255) {
        frames = 255;
    }

    return (u8)frames;
}

static s32 OverworldWildSpawns_LerpCanopyRenderHopValue(s32 start, s32 target, u8 elapsed, u8 total)
{
    if (elapsed >= total) {
        return target;
    }

    return start + (((target - start) * elapsed) / total);
}

static s32 OverworldWildSpawns_GetCanopyRenderHopArcHeight(u8 elapsed, u8 total)
{
    s32 height;

    if (elapsed >= total || total == 0) {
        return 0;
    }

    height = (4
        * OW_WILD_SPAWNER_CANOPY_HOPPER_RENDER_HOP_HEIGHT_FX32
        * elapsed
        * (total - elapsed))
        / (total * total);
    return height;
}
#endif

static BOOL OverworldWildSpawns_RunImmediateCanopyMovementCommand(LocalMapObject *object, u32 movementCommand)
{
    int i;

    if (object == NULL || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }

    MapObject_StartMovementCommand(object, movementCommand);
    MapObject_SetSingleMovementActive(object);
    for (i = 0; i < OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS; i++) {
        if (!MapObject_IsSingleMovementActive(object)) {
            return TRUE;
        }
        if (MapObject_UpdateMovementCommand(object)) {
            MapObject_ClearSingleMovementActive(object);
            return TRUE;
        }
    }

    if (MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }
    return FALSE;
}

static void OverworldWildSpawns_StartCustomJump(
    OverworldWildSpawnState *state,
    int slot,
    int startX,
    int startY,
    int targetX,
    int targetY,
    s32 startBaseY,
    s32 targetBaseY)
{
    OverworldWildOverlayRuntimeState *runtime;

    /* A new local presentation has no accepted actor transaction to cancel. */
    OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
    runtime = OW_WILD_RUNTIME(state);

    runtime->movementCustomJumpActive[slot] = TRUE;
    runtime->movementCustomMotionModes[slot] = OW_WILD_CUSTOM_MOTION_JUMP;
    runtime->movementCustomJumpShadowBaseY[slot] = startBaseY;
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
    sOverworldWildCustomJumpRamFinalLanding = FALSE;
#endif
    runtime->movementCustomJumpStartX[slot] = (s16)startX;
    runtime->movementCustomJumpStartY[slot] = (s16)startY;
    runtime->movementCustomJumpTargetX[slot] = (s16)targetX;
    runtime->movementCustomJumpTargetY[slot] = (s16)targetY;
    runtime->movementCustomJumpStartBaseY[slot] = startBaseY;
    runtime->movementCustomJumpTargetBaseY[slot] = targetBaseY;
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
    sOverworldWildCustomJumpRamStage = 7;
    sOverworldWildCustomJumpRamSlot = slot;
    sOverworldWildCustomJumpRamStartX = startX;
    sOverworldWildCustomJumpRamStartY = startY;
    sOverworldWildCustomJumpRamTargetX = targetX;
    sOverworldWildCustomJumpRamTargetY = targetY;
    sOverworldWildCustomJumpRamActive = TRUE;
#endif
}

static OverworldMotionDecision __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    u8 distance,
    int targetX,
    int targetY,
    const OverworldWildBehaviorProfile *profile,
    BOOL suppressHopStartSound,
    u8 walkTime)
{
    const OverworldWildBehaviorDataBlob *behaviorData;
    const OverworldWildBehaviorProfileData *lane;
    OverworldWildOverlayRuntimeState *runtime;
    OverworldActorPolicyView policy;
    u32 frameCount;
    u32 trajectory = 0;
    u32 movementCommand;
    int objectX;
    int objectY;
    u8 spinSpeed;
    u8 spinStartFacing;
    u8 swayWidth;
    BOOL playHopStartSound;
    BOOL chainReposition;
    BOOL repositionUsesArc;
    BOOL flatWalk;
    BOOL flyIn;
    BOOL preserveFacing;
    s32 startBaseY;
    s32 targetBaseY;
    u8 reason = OVERWORLD_MOTION_DECISION_PROFILE;
    u8 previousDirection = state->movementPendingDirections[slot];
    u8 previousDistance = state->movementPendingDistances[slot];

    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        goto rejected;
    }
    /* The local cooldown can expire before the actor's final settling tick.
     * Reject before preparing presentation or replacing its motion identity. */
    if (policy.motionPhase != OVERWORLD_MOTION_PHASE_IDLE
        && policy.motionPhase != OVERWORLD_MOTION_PHASE_CANCELED) {
        reason = OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
        goto rejected;
    }
    runtime = OW_WILD_RUNTIME(state);
    flyIn = state->movementSpawnRunActive[slot]
        == OW_WILD_SPAWN_ENTRY_FLY_IN;
    /* BEGIN installs the grid before the first move. The remaining-count
     * pending bit is installed only after that move is accepted. */
    chainReposition = (policy.chainPauseAction
        & OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER_MASK)
        == OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER;
    if (chainReposition && MapObject_IsSingleMovementActive(object)) {
        reason = OVERWORLD_MOTION_DECISION_ALREADY_ACTIVE;
        goto rejected;
    }
    repositionUsesArc = !chainReposition
        || (policy.chainStepsRemaining
            & OW_WILD_SPAWNER_CHAIN_REPOSITION_FLAT_MASK) == 0;
    objectX = object->xCurr;
    objectY = object->yCurr;
    spinStartFacing = object->curFacing <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
        ? object->curFacing
        : direction;
    state->movementFieldSystem = fieldSystem;
    lane = OverworldWildSpawns_GetControllerLane(
        profile,
        state->movementSpotStates[slot]);
    preserveFacing = OW_WILD_BEHAVIOR_WALK_PRESERVES_FACING(
        lane->walkOptions);
    if (chainReposition) {
        if (!preserveFacing) {
            spinStartFacing = targetX != objectX
                ? OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT + (targetX > objectX)
                : (targetY > objectY);
        }
        preserveFacing = TRUE;
    }
    flatWalk = !chainReposition
        && suppressHopStartSound == OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG;
    playHopStartSound = !suppressHopStartSound
        && OverworldWildSpawns_IsHeadbuttTreeTopLocation(fieldSystem, objectX, objectY);
    startBaseY = (s32)object->posVec[1];
    if (flyIn) {
        targetBaseY = runtime->movementCustomJumpTargetBaseY[slot];
    } else if (sOverworldWildSpawnHopPreparing && !flatWalk) {
        do {
            OverworldWildSpawns_ResolveObjectLandingHeight(
                fieldSystem,
                object,
                object->xCurr + OverworldWildSpawns_MovementDirectionDeltaX(direction),
                object->yCurr + OverworldWildSpawns_MovementDirectionDeltaY(direction));
        } while (object->xCurr != targetX || object->yCurr != targetY);
        targetBaseY = (s32)object->posVec[1];
        OverworldWildSpawns_SetObjectTile(object, objectX, objectY);
        object->posVec[1] = (u32)startBaseY;
        object->hInit = startBaseY >> 15;
        object->hPrev = object->hInit;
        object->hCurr = object->hInit;
    } else {
        targetBaseY = OverworldWildSpawns_GetObjectGroundBaseYAt(
            fieldSystem,
            object,
            targetX,
            targetY);
    }
    if (flyIn) {
        trajectory = 0;
        frameCount = OW_WILD_SPAWNER_FLY_IN_DURATION_FRAMES;
    } else if (flatWalk) {
        frameCount = OverworldWalk_ClampTime(walkTime);
    } else {
        behaviorData = OverworldWildSpawns_GetBehaviorDataBlob();
        trajectory = policy.chainPauseTicks;
        reason = OverworldWildSpawns_ResolveHopTrajectory(
                fieldSystem,
                (const OverworldWildSurfaceCatalog *)behaviorData->surfaceModels,
                lane,
                object,
                startBaseY,
                targetBaseY,
                objectX,
                objectY,
                targetX,
                targetY,
                distance,
                repositionUsesArc,
                sOverworldWildSpawnHopPreparing,
                &trajectory);
        if (reason != OVERWORLD_MOTION_DECISION_ACCEPTED) {
            goto rejected;
        }
        frameCount = trajectory & 0xFFFF;
        if ((state->movementStagedHopPending[slot]
                & OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING) != 0) {
            frameCount = OverworldWalk_ClampTime(
                    policy.walkMomentum.speed != 0
                        ? policy.walkMomentum.speed
                        : lane->chillSpeed)
                * distance;
        }
    }
    if (chainReposition && !repositionUsesArc) {
        /* Reposition time is an authored motion duration, not frames per
         * crossed tile. Distance changes the endpoint only. Multiplying here
         * made a two-tile skid take twice the configured time. */
        frameCount = policy.chainPauseTicks;
    }
    spinSpeed = chainReposition || flatWalk || flyIn
        ? 0
        : OverworldWildSpawns_GetBehaviorHopSpinSpeed(
            profile,
            state->movementSpotStates[slot]);
    OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
    OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
    if (!chainReposition) {
        spinStartFacing = preserveFacing
            || (spinSpeed & OW_WILD_SPAWNER_CUSTOM_JUMP_SPIN_SPEED_MASK) != 0
            || (flatWalk && (object->flags & MAPOBJECTFLAG_UNK7) != 0)
            ? spinStartFacing
            : flatWalk
                && direction > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            ? OverworldWalk_DiagonalFacing(
                object,
                direction,
                OverworldWalk_DirectionKey(direction))
            : direction;
    }
    reason = OVERWORLD_MOTION_DECISION_PROFILE;
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH | OW_WILD_SPAWNER_CUSTOM_JUMP_OWNED_BITS);
    if (!flatWalk && !flyIn
        && !OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND)) {
        (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND);
        goto rejected;
    }
    OverworldWildSpawns_StartCustomJump(
        state,
        slot,
        objectX,
        objectY,
        targetX,
        targetY,
        startBaseY,
        targetBaseY);
    runtime->movementCustomMotionModes[slot] = flatWalk
        ? OW_WILD_CUSTOM_MOTION_WALK
        : OW_WILD_CUSTOM_MOTION_JUMP;
    runtime->movementCustomJumpArcHeightsQ4[slot] = !flatWalk && repositionUsesArc
            && !flyIn
        ? (u8)(trajectory >> 16)
        : 0;
    runtime->movementCustomJumpPrepActive[slot] = !flatWalk && !flyIn;
    if (flyIn) {
        /* The first sample reads xPrev/yPrev for its render tile. Seed the
         * native height query from a grounded actor, not the landing ledge. */
        runtime->movementCustomJumpShadowBaseY[slot] =
            (s32)fieldSystem->playerAvatar->mapObject->posVec[1];
    }
    OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);
    swayWidth = chainReposition || flyIn
        ? 0
        : flatWalk
            ? lane->walkSwayWidth
            : sOverworldWildSpawnHopPreparing
                ? lane->spawnHopSwayWidth
                : lane->hopSwayWidth;
    state->movementPendingDirections[slot] = direction;
    state->movementPendingDistances[slot] = distance;
    reason = OverworldWildSpawns_BeginSharedMotion(
            state,
            slot,
            spinStartFacing,
            lane,
            flatWalk,
            chainReposition,
            (u16)frameCount,
            spinSpeed,
            swayWidth);
    if (reason != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        /* Begin rejected the request, so no shared motion is owned here. */
        OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
        state->movementPendingDirections[slot] = previousDirection;
        state->movementPendingDistances[slot] = previousDistance;
        if (!flatWalk && !flyIn) {
            (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
                object,
                OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND);
            runtime->movementCustomJumpPrepActive[slot] = FALSE;
        }
        /* A post-preparation rejection is never a geometric search result. */
        if ((u32)(reason - OVERWORLD_MOTION_DECISION_BLOCKED)
            <= OVERWORLD_MOTION_DECISION_OCCUPIED - OVERWORLD_MOTION_DECISION_BLOCKED) {
            reason = OVERWORLD_MOTION_DECISION_PROFILE;
        }
        goto rejected;
    }
    OverworldWildSpawns_SetPreviousTile(state, slot, objectX, objectY);
    state->movementStagedHopDistances[slot] = distance;
    OverworldWildSpawns_SetObjectFacing(object, spinStartFacing);
    /* The stationary engine shell belongs only to an accepted actor motion.
     * In particular, a request during the preceding landing pause must not
     * leave SINGLE_MOVEMENT set with no controller to finish its command. */
    movementCommand = OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND;
    MapObject_StartMovementCommand(object, movementCommand);
    MapObject_SetSingleMovementActive(object);
    if (!flatWalk && !flyIn) {
        StopSE(OW_WILD_SPAWNER_SPOT_EMOTE_SE);
        if (playHopStartSound) {
            StopSE(OW_WILD_SPAWNER_HOP_START_SE);
            OverworldWildSpawns_PlayCanopyHopSE(state);
        } else {
            OverworldWildSpawns_StartHopStartSoundSuppression(state, slot);
        }
    }
    state->movementBattleSettleFrames = 0;
    OverworldWildSpawns_SetMovementSlotInProgress(state, slot);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
    OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 9);
    return OVERWORLD_MOTION_DECISION_ACCEPTED;
rejected:
    return reason;
}

static BOOL __attribute__((optimize("Os")))
OverworldWildSpawns_StartPreparedCustomJumpCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    u8 distance,
    int targetX,
    int targetY,
    const OverworldWildBehaviorProfile *profile,
    BOOL suppressHopStartSound)
{
    return OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
        state, fieldSystem, slot, object, direction, distance,
        targetX, targetY, profile, suppressHopStartSound, 0)
        == OVERWORLD_MOTION_DECISION_ACCEPTED;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_StartSpawnAirborne(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildSpawnStartup *startup,
    const OverworldWildBehaviorProfile *resolvedProfile)
{
    LocalMapObject *object;
    s32 startBaseY;
    BOOL flyIn;
    int startX = startup->startX;
    int startY = startup->startY;
    int targetX = startup->targetX;
    int targetY = startup->targetY;
    s32 targetBaseY = startup->targetBaseY;

    object = state->spawns[slot].object;
    flyIn = startup->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN;

    if (flyIn) {
        /* Preparation resolved the validated destination before choosing the
         * presentation origin. Never derive the terminal height from the
         * off-screen object position. */
        startBaseY = targetBaseY + OW_WILD_SPAWNER_FLY_IN_HEIGHT_FX32;
        OverworldWildSpawns_SetObjectTile(object, startX, startY);
        object->posVec[1] = (u32)startBaseY;
        object->hInit = startBaseY >> 15;
        object->hPrev = object->hInit;
        object->hCurr = object->hInit;
        OW_WILD_RUNTIME(state)->movementCustomJumpTargetBaseY[slot] = targetBaseY;
    } else {
        object->posVec[1] = fieldSystem->playerAvatar->mapObject->posVec[1];
        OverworldWildSpawns_ResolveObjectLandingHeight(
            fieldSystem,
            object,
            startX,
            startY);
        sOverworldWildSpawnHopPreparing = TRUE;
    }
    OverworldWildSpawns_SetSpawnRunState(
        state,
        fieldSystem,
        slot,
        targetX,
        targetY,
        flyIn ? OW_WILD_SPAWN_ENTRY_FLY_IN : OW_WILD_SPAWN_ENTRY_HOP);
    if (!OverworldWildSpawns_StartPreparedCustomJumpCommand(
            state,
            fieldSystem,
            slot,
            object,
            startup->hopDirection,
            flyIn
                ? OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE
                : OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE,
            targetX,
            targetY,
            resolvedProfile,
            TRUE)) {
        sOverworldWildSpawnHopPreparing = FALSE;
        OverworldWildSpawns_ClearSpawnRunState(state, slot);
        return FALSE;
    }
    sOverworldWildSpawnHopPreparing = FALSE;

    /* The actor remains owned by the loaded landing block. Only its shared
     * presentation sample travels from the off-screen origin. */
    OverworldWildSpawns_SetObjectLogicalTileOnly(object, targetX, targetY);
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartNextStagedHopMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object)
{
    int dx;
    int dy;
    int objectX;
    int objectY;
    int totalRemainingDistance;
    int targetX;
    int targetY;
    OverworldWildBehaviorProfile profile;
#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE
    u8 direction;
    u32 movementCommand;
#endif
    u8 behaviorDirection;
    u8 behaviorDistance;
    u8 plannedDirections[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];
    int plannedDirectionCount;
    u16 allowedTile;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || !state->movementStagedHopPending[slot]) {
        return FALSE;
    }

    if (MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }

    objectX = object->xCurr;
    objectY = object->yCurr;
    targetX = state->movementStagedHopTargetX[slot];
    targetY = state->movementStagedHopTargetY[slot];
    dx = targetX - objectX;
    dy = targetY - objectY;
    if (OverworldWildSpawns_IsAtStagedHopTarget(state, slot, object)) {
        return FALSE;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, NULL);
    allowedTile = OverworldWildSpawns_GetAllowedTileForSpotState(
        &profile,
        state->movementSpotStates[slot]);
    totalRemainingDistance = OverworldWildSpawns_Max(
        OverworldWildSpawns_Abs(dx),
        OverworldWildSpawns_Abs(dy));
    if (totalRemainingDistance < OverworldWildSpawns_GetBehaviorHopMinDistance(
            &profile,
            state->movementSpotStates[slot])
        && totalRemainingDistance > OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP
#if OW_WILD_SPAWNER_CANOPY_SHIFT_SOUTH_LAND_ANCHORS
        && !OverworldWildSpawns_IsShiftedSouthLandAnchorHop(
            fieldSystem,
            objectX,
            objectY,
            targetX,
            targetY)
#endif
#if OW_WILD_SPAWNER_CANOPY_SHIFT_NORTH_LAND_ANCHORS
        && !OverworldWildSpawns_IsShiftedNorthLandAnchorHop(
            fieldSystem,
            objectX,
            objectY,
            targetX,
            targetY)
#endif
        ) {
        OverworldWildSpawns_ClearStagedHopTarget(state, slot);
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        state->movementCooldowns[slot] = OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
        return FALSE;
    }

    if (state->movementStagedHopPending[slot]
            != OW_WILD_SPAWNER_STAGED_WALK_PENDING
        && OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
            state,
            slot,
            fieldSystem,
            allowedTile,
            targetX,
            targetY,
            targetX,
            targetY)
        && OverworldWildSpawns_TryGetBehaviorHopVector(
            &profile,
            state->movementSpotStates[slot],
            dx,
            dy,
            &behaviorDirection,
            &behaviorDistance)
        && OverworldWildSpawns_StartPreparedCustomJumpCommand(
            state,
            fieldSystem,
            slot,
            object,
            behaviorDirection,
            behaviorDistance,
            targetX,
            targetY,
            &profile,
            FALSE)) {
        return TRUE;
    }

    plannedDirectionCount = OverworldWildSpawns_BuildDirectedDirections(
        dx,
        dy,
        plannedDirections);
    if (plannedDirectionCount > 0
        && OverworldWildSpawns_TryStartBehaviorHopPlanStepCommand(
            state,
            fieldSystem,
            slot,
            &profile,
            allowedTile,
            targetX,
            targetY,
            plannedDirections,
            plannedDirectionCount,
            FALSE)) {
        return TRUE;
    }

    if (totalRemainingDistance <= OW_WILD_SPAWNER_MOVEMENT_DISTANCE_STEP
        && OverworldWildSpawns_IsBehaviorAllowedHopLandingTile(
            state,
            slot,
            fieldSystem,
            allowedTile,
            targetX,
            targetY,
            targetX,
            targetY)) {
        OverworldWildSpawns_SetObjectLandingTile(fieldSystem, object, targetX, targetY);
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        OverworldWildSpawns_FinishPendingStagedHop(state, slot, object);
        OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(state, fieldSystem, slot, object);
        return TRUE;
    }
#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE
    if (totalRemainingDistance >= OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP
        && (dx == 0 || dy == 0)) {
        if (dx > 0) {
            direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT;
        } else if (dx < 0) {
            direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT;
        } else if (dy > 0) {
            direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
        } else {
            direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP;
        }

        movementCommand = MapObject_MovementCommandFromDirection(
            direction,
            OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_2_COMMAND);
        state->movementFieldSystem = fieldSystem;
        state->movementStagedHopDistances[slot] = OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP;
        OverworldWildSpawns_StartMovementCommandForSlot(
            state,
            slot,
            object,
            movementCommand,
            direction,
            OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP);
        return TRUE;
    }
#endif
    OverworldWildSpawns_ClearStagedHopTarget(state, slot);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    state->movementCooldowns[slot] = OW_WILD_SPAWNER_DEFAULT_MOVEMENT_PAUSE_FRAMES;
    return FALSE;
}

static void OverworldWildSpawns_FinishPendingStagedHop(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    OverworldWildOverlayRuntimeState *runtime;
    BOOL treeTopLandingExpected;
    BOOL walkMovement;
    BOOL chainHopForward;
    BOOL finalTreeTopLanding = FALSE;
    s16 avoidX;
    s16 avoidY;

    runtime = OW_WILD_RUNTIME(state);
    walkMovement = runtime->movementCustomMotionModes[slot]
        == OW_WILD_CUSTOM_MOTION_WALK;
    chainHopForward = state->movementStagedHopPending[slot]
        == OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING;

    treeTopLandingExpected = runtime->movementMankeyTreeTopLandingExpected[slot];
    if (treeTopLandingExpected
        && OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)
        && state->movementFieldSystem != NULL) {
        finalTreeTopLanding = OverworldWildSpawns_IsHeadbuttTreeTopLocation(
            state->movementFieldSystem,
            object->xCurr,
            object->yCurr);
    }
    if ((state->movementStagedHopPending[slot] & 3)
            == OW_WILD_SPAWNER_STAGED_HOP_LEDGE_PENDING) {
        avoidX = state->movementPreviousTileX[slot];
        avoidY = state->movementPreviousTileY[slot];
    } else {
        avoidX = state->movementStagedHopOriginX[slot];
        avoidY = state->movementStagedHopOriginY[slot];
    }
    OverworldWildSpawns_ClearStagedHopTargetLocal(state, slot);
    if (walkMovement) {
        /* The staged presentation is clear, but the actor still needs its
         * terminal Walk boundary. Preserve the motion kind until that call
         * commits the shared Walk and clears it. */
        runtime->movementCustomMotionModes[slot] = OW_WILD_CUSTOM_MOTION_WALK;
    }
    runtime->movementMankeyTreeTopLandingExpected[slot] = FALSE;
    runtime->movementMankeyTreeTopSettled[slot] = finalTreeTopLanding;
    if (runtime->movementMankeyTreeTopSettled[slot]) {
        runtime->movementMankeyTreeTopSettledX[slot] = (s16)object->xCurr;
        runtime->movementMankeyTreeTopSettledY[slot] = (s16)object->yCurr;
    } else {
        runtime->movementMankeyTreeTopSettledX[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
        runtime->movementMankeyTreeTopSettledY[slot] = OW_WILD_SPAWNER_PREVIOUS_TILE_NONE;
    }
    state->movementStagedHopAvoidX[slot] = avoidX;
    state->movementStagedHopAvoidY[slot] = avoidY;
    state->movementStagedHopAvoidValid[slot] = TRUE;

    if (chainHopForward) {
        state->movementCooldowns[slot] = 0;
        return;
    }
    OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
}

#if 0
static BOOL OverworldWildSpawns_TickCanopyRenderHopMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    BOOL *finished)
{
    LocalMapObject *object;
    OverworldWildBehaviorProfile profile;
    u8 totalFrames;
    u8 remainingFrames;
    u8 elapsedFrames;
    s32 startX;
    s32 startZ;
    s32 targetX;
    s32 targetZ;
    s32 baseY;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || state->movementCanopyRenderHopTimers[slot] == 0) {
        return FALSE;
    }

    if (!OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        state->movementCanopyRenderHopTimers[slot] = 0;
        OverworldWildSpawns_ClearCanopyRenderHopObject(state, slot, TRUE);
        OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
        if (finished != NULL) {
            *finished = TRUE;
        }
        return TRUE;
    }

    object = state->spawns[slot].object;
    if (object == NULL) {
        state->movementCanopyRenderHopTimers[slot] = 0;
        OverworldWildSpawns_ClearCanopyRenderHopObject(state, slot, TRUE);
        OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
        if (finished != NULL) {
            *finished = TRUE;
        }
        return TRUE;
    }

    totalFrames = OverworldWildSpawns_GetCanopyRenderHopDuration(
        state->movementStagedHopDistances[slot]);
    remainingFrames = state->movementCanopyRenderHopTimers[slot];
    if (remainingFrames > totalFrames) {
        remainingFrames = totalFrames;
    }
    elapsedFrames = (u8)(totalFrames - remainingFrames + 1);
    startX = state->movementCanopyRenderHopStartX[slot];
    startZ = state->movementCanopyRenderHopStartZ[slot];
    targetX = state->movementCanopyRenderHopTargetX[slot];
    targetZ = state->movementCanopyRenderHopTargetZ[slot];
    baseY = state->movementCanopyRenderHopBaseY[slot];
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);

    if (elapsedFrames >= totalFrames) {
        OverworldWildSpawns_SetObjectTile(
            object,
            targetX / OW_WILD_SPAWNER_FX32_ONE,
            targetZ / OW_WILD_SPAWNER_FX32_ONE);
        object->posVec[0] = (u32)targetX;
        object->posVec[1] = (u32)baseY;
        object->posVec[2] = (u32)targetZ;
        state->movementCanopyRenderHopTimers[slot] = 0;
        OverworldWildSpawns_ClearCanopyRenderHopObject(state, slot, TRUE);
        OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
        OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
            state, slot, &profile, NULL);
        if (OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile(
                state,
                fieldSystem,
                slot,
                targetX / OW_WILD_SPAWNER_FX32_ONE,
                targetZ / OW_WILD_SPAWNER_FX32_ONE,
                TRUE)) {
            object = OverworldWildSpawns_RecreateSpawnObjectAtTile(
                state,
                fieldSystem,
                slot,
                object,
                targetX / OW_WILD_SPAWNER_FX32_ONE,
                targetZ / OW_WILD_SPAWNER_FX32_ONE,
                OverworldWildSpawns_ShouldNormalizeCanopyRefreshAtTile(
                    fieldSystem,
                    targetX / OW_WILD_SPAWNER_FX32_ONE,
                    targetZ / OW_WILD_SPAWNER_FX32_ONE));
        } else {
            OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        }
        OverworldWildSpawns_FinishPendingStagedHop(state, slot, object);
        if (finished != NULL) {
            *finished = TRUE;
        }
        return TRUE;
    }

    object->posVec[0] = (u32)OverworldWildSpawns_LerpCanopyRenderHopValue(
        startX,
        targetX,
        elapsedFrames,
        totalFrames);
    object->posVec[1] = (u32)(baseY
        + OverworldWildSpawns_GetCanopyRenderHopArcHeight(elapsedFrames, totalFrames));
    object->posVec[2] = (u32)OverworldWildSpawns_LerpCanopyRenderHopValue(
        startZ,
        targetZ,
        elapsedFrames,
        totalFrames);
    state->movementCanopyRenderHopTimers[slot] = (u8)(remainingFrames - 1);
    return TRUE;
}
#endif

static BOOL OverworldWildSpawns_TickStagedHopMovementListTask(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    BOOL *finished)
{
    OverworldWildStagedHopMovementList *movementList;
    SysTask *movementTask;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }
    movementList = OW_WILD_RUNTIME(state)->movementStagedHopMovementLists[slot];
    if (movementList == NULL || movementList->task == NULL) {
        return FALSE;
    }
    movementTask = movementList->task;

    if (!OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
        OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
        if (finished != NULL) {
            *finished = TRUE;
        }
        return TRUE;
    }

    if (!MapObject_MovementListTaskIsFinished(movementTask)) {
        return TRUE;
    }

    OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
    OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
    if (!OverworldWildSpawns_HandleFinishedStagedHopMovementCommand(
            state,
            fieldSystem,
            slot,
            FALSE)) {
        OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
    }
    if (finished != NULL) {
        *finished = TRUE;
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_HandleFinishedStagedHopMovementCommand(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    BOOL customJumpLandingFinalized)
{
    LocalMapObject *object;
    OverworldWildBehaviorProfile profile;
    OverworldActorPolicyView policy;
    BOOL finalLanding;
    BOOL skipFinalMankeyTreeTopRestore;
    BOOL customJumpWasActive;
    BOOL customJumpVisibleLegFinished;
    BOOL customJumpRenderSettleActive = FALSE;
#if !OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE
    int landingX;
    int landingY;
#endif

    if (state == NULL
        || fieldSystem == NULL
        || !state->movementStagedHopPending[slot]
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (!OverworldActorPolicy_Inspect((u8)slot, &policy)) {
        return FALSE;
    }
    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, NULL);
    finalLanding = (state->movementStagedHopPending[slot] & 3)
            == OW_WILD_SPAWNER_STAGED_HOP_LEDGE_PENDING
        || (policy.chainStepsRemaining & 0x80) != 0
        || OverworldWildSpawns_IsAtStagedHopTarget(state, slot, object);
    customJumpWasActive = OW_WILD_RUNTIME(state)->movementCustomJumpActive[slot];
#if OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS
    customJumpVisibleLegFinished =
        sOverworldWildCustomJumpVisibleLegFinished[slot];
#else
    customJumpVisibleLegFinished = FALSE;
#endif
#if OW_WILD_SPAWNER_CUSTOM_JUMP_RAM_PROBE
    sOverworldWildCustomJumpRamFinalLanding = finalLanding;
#endif
    OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 14);
    skipFinalMankeyTreeTopRestore =
        finalLanding
        && OverworldWildSpawns_IsCanopyHopperTreeTopSlot(state, slot)
        && OW_WILD_RUNTIME(state)->movementMankeyTreeTopLandingExpected[slot];
#if !OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE
    landingX = OverworldWildSpawns_ObjectCurrentX(object);
    landingY = OverworldWildSpawns_ObjectCurrentY(object);
#endif
    if (!finalLanding) {
#if !OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE
#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE
        OverworldWildSpawns_SetObjectLogicalTileOnly(object, landingX, landingY);
#else
        if (customJumpVisibleLegFinished) {
            OverworldWildSpawns_SetObjectLogicalTileOnly(object, landingX, landingY);
        } else {
            OverworldWildSpawns_SetObjectTile(object, landingX, landingY);
        }
#endif
#endif
    }
#if OW_WILD_SPAWNER_CUSTOM_JUMP_VISIBLE_LEGS
    sOverworldWildCustomJumpVisibleLegFinished[slot] = FALSE;
#endif
    if (OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[slot]) {
        (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
            object,
            OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND);
        if (!skipFinalMankeyTreeTopRestore) {
            (void)OverworldWildSpawns_RunImmediateCanopyMovementCommand(
                object,
                OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND);
        }
        OW_WILD_RUNTIME(state)->movementCustomJumpPrepActive[slot] = FALSE;
    }
    OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
#if OW_WILD_SPAWNER_CUSTOM_JUMP_POST_RESTORE_FINALIZE
    if (OW_WILD_RUNTIME(state)->movementCustomJumpActive[slot]) {
        customJumpRenderSettleActive = !customJumpLandingFinalized
            && !OverworldWildSpawns_UpdateCustomJumpLanding(
                state,
                slot,
                object,
                TRUE);
        if (!customJumpRenderSettleActive
            && !OverworldWildSpawns_StartCustomJumpRenderSettle(
                state,
                slot,
                object)
            && OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
                != OW_WILD_CUSTOM_MOTION_WALK) {
            OverworldWildSpawns_ClearCustomJumpLocal(state, slot);
        }
    }
#endif
    if (customJumpRenderSettleActive) {
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 18);
        return TRUE;
    }
    if (finalLanding) {
        if (!customJumpWasActive) {
            OverworldWildSpawns_SetObjectLandingTile(
                fieldSystem,
                object,
                OverworldWildSpawns_ObjectCurrentX(object),
                OverworldWildSpawns_ObjectCurrentY(object));
        }
        OverworldWildSpawns_FinishPendingStagedHop(state, slot, object);
        OverworldWildSpawns_RefreshCanopyHopperVisualStateAtLanding(state, fieldSystem, slot, object);
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 15);
    } else {
        state->movementCooldowns[slot] =
            OW_WILD_SPAWNER_CANOPY_HOPPER_SEGMENT_SETTLE_FRAMES;
        if (OW_WILD_RUNTIME(state)->movementCustomMotionModes[slot]
                == OW_WILD_CUSTOM_MOTION_WALK) {
            /* A directed Walk is one actor motion per tile. Close this tile
             * before the staged path asks the actor to begin the next one. */
            OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);
        } else {
            /* Shared Motion already completed the resolved Hop interval. */
            state->movementCooldowns[slot] = 0;
        }
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
        OverworldWildSpawns_RecordCustomJumpRamObject(state, slot, object, 16);
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_ExecutePendingStagedHop(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    const OverworldWildBehaviorProfile *profile)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || profile == NULL
        || !state->movementStagedHopPending[slot]) {
        return FALSE;
    }

    if (OverworldWildSpawns_IsAtStagedHopTarget(state, slot, object)) {
        OverworldWildSpawns_SetObjectLandingTile(
            fieldSystem,
            object,
            OverworldWildSpawns_ObjectCurrentX(object),
            OverworldWildSpawns_ObjectCurrentY(object));
        OverworldWildSpawns_FinishPendingStagedHop(state, slot, object);
        return TRUE;
    }

    return OverworldWildSpawns_TryStartNextStagedHopMovementCommand(
        state,
        fieldSystem,
        slot,
        object);
}

#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE
static BOOL OverworldWildSpawns_TryPickStraightCanopyStepTarget(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    u8 distance,
    int *targetX,
    int *targetY,
    u8 *direction)
{
    u32 startIndex;
    u32 i;
    int objectX;
    int objectY;

    if (fieldSystem == NULL
        || object == NULL
        || distance == 0
        || targetX == NULL
        || targetY == NULL
        || direction == NULL) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    if (objectX < 0 || objectY < 0) {
        return FALSE;
    }

    startIndex = gf_rand() & (OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT - 1);
    for (i = 0; i < OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT; i++) {
        u8 candidateDirection = (startIndex + i)
            & (OW_WILD_CUSTOM_JUMP_DIRECTION_COUNT - 1);
        int deltaX = OverworldWildSpawns_MovementDirectionDeltaX(
            candidateDirection);
        int deltaY = OverworldWildSpawns_MovementDirectionDeltaY(
            candidateDirection);
        int candidateX = objectX + deltaX * distance;
        int candidateY = objectY + deltaY * distance;
        int stepDistance;
        u8 directions[OW_WILD_SPAWNER_MOVEMENT_MAX_DIRECTIONS];

        if (!OverworldWildSpawns_IsCanopyPathTile(fieldSystem, candidateX, candidateY)
            || OverworldWildSpawns_BuildDirectedDirections(
                   candidateX - objectX,
                   candidateY - objectY,
                   directions) == 0) {
            continue;
        }
        for (stepDistance = OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP;
             stepDistance < distance;
             stepDistance += OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP) {
            if (!OverworldWildSpawns_IsCanopyPathTile(
                    fieldSystem,
                    objectX + deltaX * stepDistance,
                    objectY + deltaY * stepDistance)) {
                break;
            }
        }
        if (stepDistance < distance) {
            continue;
        }

        *targetX = candidateX;
        *targetY = candidateY;
        *direction = directions[0];
        return TRUE;
    }

    return FALSE;
}
#endif

#if OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE \
    || OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE
static BOOL OverworldWildSpawns_StartWrappedCanopyJump2Probe(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    u8 direction,
    u8 segmentCount)
{
    OverworldWildStagedHopMovementList *movementList;
    SysTask *movementTask;
    u16 wrappedJumpCommand;
    u8 segment;
    u8 wordIndex = 0;
    int objectX;
    int objectY;
    BOOL useSingleWrapper =
        OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || object == NULL
        || segmentCount == 0
        || segmentCount > 2) {
        return FALSE;
    }

    objectX = OverworldWildSpawns_ObjectCurrentX(object);
    objectY = OverworldWildSpawns_ObjectCurrentY(object);
    wrappedJumpCommand = (u16)MapObject_MovementCommandFromDirection(
        direction,
        OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_2_COMMAND);

    OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
    movementList = OverworldWildSpawns_AllocStagedHopMovementList(state, slot);
    if (movementList == NULL) {
        return FALSE;
    }

    if (useSingleWrapper) {
        movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND;
        movementList->commands[wordIndex++] = 1;
    }
    for (segment = 0; segment < segmentCount; segment++) {
        if (!useSingleWrapper) {
            movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_PREP_COMMAND;
            movementList->commands[wordIndex++] = 1;
        }
        movementList->commands[wordIndex++] = wrappedJumpCommand;
        movementList->commands[wordIndex++] = 1;
        if (!useSingleWrapper) {
            movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND;
            movementList->commands[wordIndex++] = 1;
            movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND;
            movementList->commands[wordIndex++] = 1;
        }
    }
    if (useSingleWrapper) {
        movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_FREEZE_COMMAND;
        movementList->commands[wordIndex++] = 1;
        movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND;
        movementList->commands[wordIndex++] = 1;
    }
    movementList->commands[wordIndex++] = OW_WILD_SPAWNER_CANOPY_HOPPER_MOVEMENT_END_COMMAND;
    movementList->commands[wordIndex++] = 0;

    OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
    OverworldWildSpawns_SetObjectFacing(object, direction);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    movementTask = MapObject_StartMovementList(object, movementList->commands);
    if (movementTask == NULL) {
        OverworldWildSpawns_ClearStagedHopMovementListTask(state, slot);
        return FALSE;
    }

    movementList->task = movementTask;
    state->movementFieldSystem = fieldSystem;
    OverworldWildSpawns_SetPreviousTile(state, slot, objectX, objectY);
    state->movementPendingDirections[slot] = direction;
    state->movementPendingDistances[slot] =
        (u8)(OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP * segmentCount);
    state->movementStagedHopDistances[slot] =
        (u8)(OW_WILD_SPAWNER_MOVEMENT_DISTANCE_LEDGE_JUMP * segmentCount);
    state->movementBattleSettleFrames = 0;
    OverworldWildSpawns_SetMovementSlotInProgress(state, slot);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
    return TRUE;
}
#endif

static BOOL OverworldWildSpawns_ContinuePendingStagedHop(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    LocalMapObject *object;
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    u8 locomotion;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || !state->movementStagedHopPending[slot]) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if (object == NULL
        || OverworldWildSpawns_IsMovementSlotInProgress(state, slot)) {
        return FALSE;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, &primitives);
    locomotion = OverworldWildSpawns_GetCurrentMovementLocomotion(
        &primitives,
        state->movementSpotStates[slot]);
    if ((unsigned)(locomotion - OW_WILD_BEHAVIOR_LOCOMOTION_WANDER) > 1) {
        OverworldWildSpawns_ClearStagedHopTarget(state, slot);
        OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
        return FALSE;
    }
    if (!OverworldWildSpawns_IsChainActionReady(slot)) {
        return FALSE;
    }
    if (MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }

    return OverworldWildSpawns_ExecutePendingStagedHop(
        state,
        fieldSystem,
        slot,
        object,
        &profile);
}
#endif

static u32 OverworldWildSpawns_GetSpriteID(u16 species, u8 form)
{
    return OVERWORLD_WILD_SPAWN_METADATA_ENTRY->getSpriteId(species, form);
}

static u32 OverworldWildSpawns_GetSpriteIDForSlot(
    u16 species,
    u8 form,
    u32 personality,
    int slot)
{
    if (slot == OW_WILD_FOLLOWER_SLOT
        && species <= SPECIES_ARCEUS
        && form == 0) {
        return FollowingPokemon_GetSpriteID(
            species,
            form,
            PokeSexGetMonsNo(species, personality));
    }

    return OverworldWildSpawns_GetSpriteID(species, form);
}

static u8 OverworldWildSpawns_GetLegacyMovementBehavior(
    const OverworldWildBehaviorPrimitives *primitives)
{
    if (primitives->chillTarget
        == OW_WILD_BEHAVIOR_TARGET_AWAY_FROM_PLAYER) {
        return OW_WILD_MOVEMENT_BEHAVIOR_FLEE_PLAYER;
    }

    return OW_WILD_MOVEMENT_BEHAVIOR_CHASE_PLAYER;
}

static LocalMapObject *OverworldWildSpawns_CreateObject(
    FieldSystem *fieldSystem,
    int x,
    int y,
    u32 spriteId,
    BOOL shiny,
    const OverworldWildBehaviorPrimitives *primitives)
{
    LocalMapObject *object;

    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);

    object = CreateSpecialFieldObjectWithParams(
        fieldSystem->mapObjectMan,
        x,
        y,
        1,
        spriteId,
        OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT,
        fieldSystem->location->mapId,
        0,
        OverworldWildSpawns_GetLegacyMovementBehavior(primitives),
        OW_WILD_PAL_PARAM_ENABLE | (shiny ? OW_WILD_PAL_PARAM_SHINY : 0));
    if (object != NULL) {
        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectCreatesThisFrame);
        object->flags = (object->flags & ~BIT_VANISH) | MAPOBJECTFLAG_KEEP;
    }

    return object;
}

static void OverworldWildSpawns_ApplyMovementRange(LocalMapObject *object, u8 range)
{
    MapObject_SetXRange(object, range);
    MapObject_SetYRange(object, range);
}

static void OverworldWildSpawns_ApplyPokemonRenderParams(
    LocalMapObject *object,
    u16 species,
    u8 form,
    u32 spriteId,
    BOOL shiny)
{
    OVERWORLD_WILD_SPAWN_METADATA_ENTRY->applyRenderParams(
        object,
        species,
        form,
        spriteId,
        shiny);
    if (shiny) {
        object->flags &= ~BIT_VANISH;
    }
}

static LocalMapObject *__attribute__((noinline)) OverworldWildSpawns_RecreateSpawnObjectAtTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    LocalMapObject *object,
    int x,
    int y)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildBehaviorProfile profile;
    OverworldWildBehaviorPrimitives primitives;
    LocalMapObject *replacement;
    BOOL oldObjectCurrent;
    BOOL managerRestore;
    int facing;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->spawns[slot].species == SPECIES_NONE) {
        return object;
    }

    if (object == NULL) {
        object = state->spawns[slot].object;
    }
    if (!OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        || state->spawns[slot].mapId != fieldSystem->location->mapId) {
        return NULL;
    }
    oldObjectCurrent = object != NULL
        && object == state->spawns[slot].object
        && OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot]);
    managerRestore = (OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask
        & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0;
    if (!oldObjectCurrent && !managerRestore) {
        return NULL;
    }

    if (oldObjectCurrent && MapObject_IsSingleMovementActive(object)) {
        MapObject_ClearSingleMovementActive(object);
    }

    facing = oldObjectCurrent
        ? object->curFacing
        : OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
    if (facing < OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP
        || facing > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
        facing = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
    }

    OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
        state, slot, &profile, &primitives);
    if (oldObjectCurrent) {
        /*
         * Canonicalize every existing primary record in place so every owner
         * keeps the same object identity.  Only a genuinely missing record
         * after a verified manager replacement may be recreated below.
         */
        OverworldWildSpawns_SetObjectFacing(object, (u8)facing);
        OverworldWildSpawns_SetObjectLandingTile(fieldSystem, object, x, y);
        OverworldWildSpawns_ClearObjectFlags(object, MAPOBJECTFLAG_UNK8 | MAPOBJECTFLAG_UNK18);
        OverworldWildSpawns_ApplyMovementRange(object, profile.range);
        OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, object);
        OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownX[slot] = (s16)x;
        OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownY[slot] = (s16)y;
        OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
        return object;
    }

    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    replacement = helperEntry != NULL && helperEntry->createPresentationObject != NULL
        ? helperEntry->createPresentationObject(
        fieldSystem,
        state,
        slot,
        x,
        y,
        (u8)facing,
        OverworldWildSpawns_GetLegacyMovementBehavior(&primitives),
        profile.range)
        : NULL;
    if (replacement == NULL) {
        return NULL;
    }

    OverworldWildSpawns_ApplySpawnPassThroughFlag(state, slot, replacement);

    state->spawns[slot].object = replacement;
    state->spawns[slot].objectId = OW_WILD_OBJECT_ID_START + slot;
    /*
     * A replacement object starts with the constructor's default vertical
     * position. Canonicalize it as a landing so route transitions restore
     * both native terrain height and any catalogued elevated surface.
     */
    OverworldWildSpawns_SetObjectLandingTile(
        fieldSystem,
        replacement,
        x,
        y);
    OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownX[slot] = (s16)x;
    OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownY[slot] = (s16)y;
    OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary(state, fieldSystem, slot);
    return replacement;
}

static BOOL OverworldWildSpawns_TryPickFishingSpawnPosition(
    FieldSystem *fieldSystem,
    OverworldWildSpawnPosition *position)
{
    int playerX;
    int playerY;
    u32 start;
    u32 i;

    if (fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || position == NULL) {
        return FALSE;
    }

    playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    start = gf_rand() & 3;
    for (i = 0; i < 4; i++) {
        u8 direction = (start + i) & 3;
        int x = playerX
            + OverworldWildSpawns_MovementDirectionDeltaX(direction);
        int y = playerY
            + OverworldWildSpawns_MovementDirectionDeltaY(direction);

        if (!OverworldWildSpawns_IsFishingShoreTile(fieldSystem, x, y)) {
            continue;
        }

        position->startX = x;
        position->startY = y;
        return TRUE;
    }

    return FALSE;
}

static BOOL OverworldWildSpawns_TryGetPlayerRelativeSpawnDestination(
    OverworldWildSpawnDestination destination,
    int *directionScale,
    int *distanceOut)
{
    if (directionScale == NULL || distanceOut == NULL) {
        return FALSE;
    }

    if (destination >= OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER
        && destination <= OW_WILD_SPAWN_DESTINATION_FIVE_TILES_FRONT_OF_PLAYER) {
        *directionScale = 1;
        *distanceOut = destination - OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER + 1;
        return TRUE;
    }
    if (destination >= OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER
        && destination <= OW_WILD_SPAWN_DESTINATION_FOUR_TILES_BEHIND_PLAYER) {
        *directionScale = -1;
        *distanceOut = destination - OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER + 1;
        return TRUE;
    }
    if (destination == OW_WILD_SPAWN_DESTINATION_FIVE_TILES_BEHIND_PLAYER) {
        *directionScale = -1;
        *distanceOut = 5;
        return TRUE;
    }
    return FALSE;
}

static void OverworldWildSpawns_GetPlayerRelativeSpawnDistanceRange(
    const OverworldWildBehaviorProfile *profile,
    int *minDistanceOut,
    int *maxDistanceOut)
{
    int minDistance = OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE;
    int maxDistance = OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE;

    if (profile != NULL) {
        minDistance = profile->spawnDestinationMinDistance;
        maxDistance = profile->spawnDestinationMaxDistance;
    }
    if (minDistance < OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE) {
        minDistance = OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE;
    } else if (minDistance > OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE) {
        minDistance = OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE;
    }
    if (maxDistance < OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE) {
        maxDistance = OW_WILD_PLAYER_RELATIVE_SPAWN_MIN_DISTANCE;
    } else if (maxDistance > OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE) {
        maxDistance = OW_WILD_PLAYER_RELATIVE_SPAWN_MAX_DISTANCE;
    }
    if (maxDistance < minDistance) {
        maxDistance = minDistance;
    }

    *minDistanceOut = minDistance;
    *maxDistanceOut = maxDistance;
}

static BOOL OverworldWildSpawns_IsUsablePlayerRangeSpawnTile(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    OverworldWildSpawnTerrain terrain;

    if (x < 0 || y < 0) {
        return FALSE;
    }
    if (OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y)
        || OverworldWildSpawns_IsNearActiveSpawn(state, x, y, OW_WILD_SPAWN_MIN_MON_DISTANCE)) {
        return FALSE;
    }
    if (OverworldWildSpawns_IsWalkableLandTile(fieldSystem, x, y)) {
        return TRUE;
    }
    return OverworldWildSpawns_TryGetSpawnTerrain(fieldSystem, x, y, &terrain)
        && terrain == OW_WILD_SPAWN_TERRAIN_SURF;
}

static BOOL OverworldWildSpawns_TryPickPlayerRelativeSpawnPosition(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    const OverworldWildBehaviorProfile *profile,
    OverworldWildSpawnDestination destination,
    OverworldWildSpawnPosition *position)
{
    LocalMapObject *playerObject;
    int playerX;
    int playerY;
    int x;
    int y;
    int directionScale;
    int exactDistance;
    int distance;
    int minDistance;
    int maxDistance;
    int candidateCount = 0;
    u8 facing;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || position == NULL) {
        return FALSE;
    }

    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject == NULL
        || !OverworldWildSpawns_IsCurrentMapObject(fieldSystem, playerObject)
        || (playerObject->flags & MAPOBJECTFLAG_ACTIVE) == 0) {
        return FALSE;
    }

    facing = playerObject->curFacing;
    if (facing > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT) {
        return FALSE;
    }

    playerX = OverworldWildSpawns_ObjectCurrentX(playerObject);
    playerY = OverworldWildSpawns_ObjectCurrentY(playerObject);
    if (!OverworldWildSpawns_TryGetPlayerRelativeSpawnDestination(
            destination,
            &directionScale,
            &exactDistance)) {
        return FALSE;
    }
    if (exactDistance > 0) {
        minDistance = exactDistance;
        maxDistance = exactDistance;
    } else {
        OverworldWildSpawns_GetPlayerRelativeSpawnDistanceRange(profile, &minDistance, &maxDistance);
    }

    for (distance = minDistance; distance <= maxDistance; distance++) {
        x = playerX + OverworldWildSpawns_MovementDirectionDeltaX(facing)
            * directionScale
            * distance;
        y = playerY + OverworldWildSpawns_MovementDirectionDeltaY(facing)
            * directionScale
            * distance;

        if (!OverworldWildSpawns_IsUsablePlayerRangeSpawnTile(state, fieldSystem, x, y)) {
            continue;
        }

        candidateCount++;
        if ((gf_rand() % candidateCount) == 0) {
            position->startX = x;
            position->startY = y;
        }
    }

    return candidateCount != 0;
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_TryPickSpawnDestinationMask(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    u16 destinationMask,
    OverworldWildSpawnPosition *position)
{
    OverworldWildSpawnDestinationScan *scan;
    OverworldWildOverlayRuntimeState *runtime;
    int x;
    int y;
    u8 checked;
    BOOL resumable;

    runtime = OW_WILD_RUNTIME(state);
    resumable = position == &runtime->queuedSpawn.position;
    scan = &runtime->spawnDestinationScan;
    if (!resumable
        || runtime->refillPositionChecksRemaining
            != OW_WILD_PROFILE_DESTINATION_SCAN_PENDING) {
        scan->playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
        scan->playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
        scan->nextX = scan->playerX - OW_WILD_SPAWN_MAX_DISTANCE;
        scan->nextY = scan->playerY - OW_WILD_SPAWN_MAX_DISTANCE;
        scan->destinationMask = destinationMask;
        scan->candidateCount = 0;
        /* Do not stack the helper and profile terrain batches in one update. */
        if (resumable) {
            runtime->refillPositionChecksRemaining =
                OW_WILD_PROFILE_DESTINATION_SCAN_PENDING;
            return FALSE;
        }
    }
    checked = 0;
    while (scan->nextY <= scan->playerY + OW_WILD_SPAWN_MAX_DISTANCE) {
        BOOL playerTile;

        x = scan->nextX;
        y = scan->nextY;
        if (++scan->nextX > scan->playerX + OW_WILD_SPAWN_MAX_DISTANCE) {
            scan->nextX = scan->playerX - OW_WILD_SPAWN_MAX_DISTANCE;
            scan->nextY++;
        }
        playerTile = x == scan->playerX && y == scan->playerY;
        if (x > scan->playerX - OW_WILD_SPAWN_MIN_DISTANCE
            && x < scan->playerX + OW_WILD_SPAWN_MIN_DISTANCE
            && y > scan->playerY - OW_WILD_SPAWN_MIN_DISTANCE
            && y < scan->playerY + OW_WILD_SPAWN_MIN_DISTANCE
            && !((destinationMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER)
                && playerTile)
            && !((destinationMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT)
                && OverworldWildSpawns_IsPlayerFrontTile(fieldSystem, x, y))) {
            continue;
        }
        checked++;
        if (OverworldWildSpawns_ClassifyBehaviorHopLandingTile(
                NULL,
                -1,
                fieldSystem,
                destinationMask,
                x,
                y,
                -1,
                -1) == OVERWORLD_MOTION_DECISION_ACCEPTED
            && !OverworldWildSpawns_IsNearActiveSpawn(
                state,
                x,
                y,
                OW_WILD_SPAWN_MIN_MON_DISTANCE)) {
            scan->candidateCount++;
            if ((gf_rand() % scan->candidateCount) == 0) {
                position->startX = x;
                position->startY = y;
            }
        }
        if (resumable
            && checked >= OW_WILD_PROFILE_DESTINATION_CHECKS_PER_UPDATE
            && scan->nextY <= scan->playerY + OW_WILD_SPAWN_MAX_DISTANCE) {
            return FALSE;
        }
    }

    if (resumable) {
        runtime->refillPositionChecksRemaining = 0;
    }
    return scan->candidateCount != 0;
}

static u16 OverworldWildSpawns_GetSpawnDestinationMask(
    const OverworldWildBehaviorProfile *profile)
{
    return profile->spawnDestinationMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
}

static BOOL OverworldWildSpawns_TryApplySpawnDestination(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    const OverworldWildBehaviorProfile *profile,
    OverworldWildSpawnPosition *position)
{
    u16 candidateMask;
    OverworldWildSpawnDestination legacyDestination;
    int directionScale;
    int exactDistance;
    BOOL resumable;
    BOOL resuming;

    /* Headbutt encounters remain anchored to their canopy source regardless
     * of the independently configured ordinary spawn-destination pool. */
    if (terrain == OW_WILD_SPAWN_TERRAIN_HEADBUTT) {
        return OverworldWildSpawns_TryPickSpawnDestinationMask(
            state, fieldSystem, OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY, position);
    }

    /* An untouched legacy Pool still owns an already prepared encounter
     * position. The shared mask becomes authoritative as soon as any of its
     * destination bits is explicitly configured. */
    if (profile->spawnDestination == OW_WILD_SPAWN_DESTINATION_POOL
        && profile->spawnDestinationOverrideMask == 0) {
        return position->startX >= 0 && position->startY >= 0;
    }

    candidateMask = OverworldWildSpawns_GetSpawnDestinationMask(profile);
    legacyDestination = (OverworldWildSpawnDestination)profile->spawnDestination;
    resumable = state != NULL
        && state->movementRuntimeState != NULL
        && position == &OW_WILD_RUNTIME(state)->queuedSpawn.position;
    resuming = resumable
        && OW_WILD_RUNTIME(state)->refillPositionChecksRemaining
            == OW_WILD_PROFILE_DESTINATION_SCAN_PENDING;
    if (!resuming
        && (candidateMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER) != 0
        && (terrain == OW_WILD_SPAWN_TERRAIN_FISHING
            || legacyDestination == OW_WILD_SPAWN_DESTINATION_SHORE)
        && OverworldWildSpawns_TryPickFishingSpawnPosition(fieldSystem, position)) {
        return TRUE;
    }
    if (!resuming
        && (candidateMask & (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT)) != 0) {
        if (OverworldWildSpawns_TryGetPlayerRelativeSpawnDestination(
                legacyDestination,
                &directionScale,
                &exactDistance)
            && (((candidateMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT) != 0
                    && directionScale > 0)
                || ((candidateMask & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER) != 0
                    && directionScale < 0))
            && OverworldWildSpawns_TryPickPlayerRelativeSpawnPosition(
                state,
                fieldSystem,
                profile,
                legacyDestination,
                position)) {
            return TRUE;
        }
    }
    if (OverworldWildSpawns_TryPickSpawnDestinationMask(
            state, fieldSystem, candidateMask, position)) {
        return TRUE;
    }

    /*
     * The untouched legacy Pool returned its prepared position above. Once a
     * destination policy is explicit, failure to find one of its destinations
     * must reject the spawn instead of leaking back to the rolled terrain.
     */
    return FALSE;
}

static int OverworldWildSpawns_GetSpawnHopVisibleTravelScore(
    u8 direction,
    int targetDx,
    int targetDy)
{
    if (direction < OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
        && OverworldWildSpawns_Abs(targetDx)
            > OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES) {
        return 0;
    }
    if (direction >= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
        && OverworldWildSpawns_Abs(targetDy)
            > OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES) {
        return 0;
    }
    if (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP) {
        return OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES - targetDy;
    }
    if (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN) {
        return OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES + targetDy;
    }
    return OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES
        + (direction == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            ? targetDx
            : -targetDx);
}

static BOOL OverworldWildSpawns_TryPickVisibleOffscreenOrigin(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int maximumDistance,
    int targetX,
    int targetY,
    int *startX,
    int *startY)
{
    int playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    int playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    int targetDx = targetX - playerX;
    int targetDy = targetY - playerY;
    u8 triedDirections = 0;
    int rank;

    for (rank = 0; rank < 4; rank++) {
        int bestVisibleTravel = state != NULL ? -0x7FFFFFFF : -1;
        u8 candidateDirection = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
        u8 direction;
        int entryDistance;
        int minimumCandidateDistance;
        int candidateDistance;

        for (direction = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_UP;
             direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT;
             direction++) {
            int visibleTravel;

            if ((triedDirections & (1u << direction)) != 0) {
                continue;
            }
            visibleTravel = OverworldWildSpawns_GetSpawnHopVisibleTravelScore(
                direction,
                targetDx,
                targetDy);
            if (visibleTravel > bestVisibleTravel) {
                bestVisibleTravel = visibleTravel;
                candidateDirection = direction;
            }
        }
        if (candidateDirection == OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE) {
            return FALSE;
        }
        triedDirections |= 1u << candidateDirection;
        entryDistance = OverworldWildSpawns_GetSpawnHopVisibleTravelScore(
            candidateDirection,
            targetDx,
            targetDy);
        minimumCandidateDistance = state == NULL ? maximumDistance : 1;
        for (candidateDistance = maximumDistance;
             candidateDistance >= minimumCandidateDistance;
             candidateDistance--) {
            int candidateX = targetX
                - OverworldWildSpawns_MovementDirectionDeltaX(candidateDirection)
                    * candidateDistance;
            int candidateY = targetY
                - OverworldWildSpawns_MovementDirectionDeltaY(candidateDirection)
                    * candidateDistance;

            if (candidateX < 0
                || candidateY < 0
                || (state == NULL
                    && entryDistance >= maximumDistance)
                || (OverworldWildSpawns_Abs(candidateX - playerX)
                        < OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_WIDTH_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES
                    && OverworldWildSpawns_Abs(candidateY - playerY)
                        < OW_WILD_SPAWNER_OFFSCREEN_VIEW_HALF_HEIGHT_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_SAFE_MARGIN_TILES
                            + OW_WILD_SPAWNER_OFFSCREEN_COMMIT_RUNWAY_TILES)
                || (state != NULL
                    && GetMetatileBehaviorAt(fieldSystem, candidateX, candidateY) == 0xFF)
                || (state == NULL
                    ? GetMetatileBehaviorAt(fieldSystem, candidateX, candidateY) == 0xFF
                    : !((terrain == OW_WILD_SPAWN_TERRAIN_LAND)
                            ? OverworldWildSpawns_IsWalkableLandTile(
                                fieldSystem, candidateX, candidateY)
                            : OverworldWildSpawns_IsSpawnRunStartTile(
                                fieldSystem, terrain, candidateX, candidateY)))
                || (state != NULL
                    && OverworldWildSpawns_IsNearActiveSpawn(
                        state, candidateX, candidateY, 0))) {
                continue;
            }
            *startX = candidateX;
            *startY = candidateY;
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL OverworldWildSpawns_PrepareSpawnAirborneStart(
    FieldSystem *fieldSystem,
    OverworldWildSpawnStartup *startup,
    u8 locomotion)
{
    int startX;
    int startY;
    if (!OverworldWildSpawns_TryPickVisibleOffscreenOrigin(
            NULL,
            fieldSystem,
            OW_WILD_SPAWN_TERRAIN_LAND,
            locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN
                ? OW_WILD_SPAWNER_SPAWN_FLY_IN_DISTANCE
                : OW_WILD_SPAWNER_SPAWN_HOP_DISTANCE,
            startup->targetX,
            startup->targetY,
            &startX,
            &startY)) {
        return FALSE;
    }

    startup->startX = (s16)startX;
    startup->startY = (s16)startY;
    startup->locomotion = locomotion;
    startup->hopDirection = startX == startup->targetX
        ? startY < startup->targetY
        : OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_LEFT
            + (startX < startup->targetX);
    return TRUE;
}

static BOOL __attribute__((optimize("Os", "tree-dominator-opts"))) OverworldWildSpawns_PrepareSpawnStartup(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    const OverworldWildBehaviorPrimitives *primitives,
    OverworldWildSpawnPosition *position,
    OverworldWildSpawnStartup *startup)
{
    startup->targetX = (s16)position->startX;
    startup->targetY = (s16)position->startY;
    startup->startX = startup->targetX;
    startup->startY = startup->targetY;
    startup->locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_NONE;

    if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN) {
        if (!OverworldWildSpawns_TryPickSpawnRunStart(
                state, fieldSystem, terrain, startup->targetX, startup->targetY,
                &position->startX, &position->startY)) {
            return FALSE;
        }
        startup->locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN;
    } else if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN) {
        return OverworldWildSpawns_PrepareSpawnAirborneStart(
            fieldSystem,
            startup,
            OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN);
    } else if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN) {
        startup->targetBaseY = OverworldWildSpawns_GetObjectGroundBaseYAt(
            fieldSystem,
            fieldSystem->playerAvatar->mapObject,
            startup->targetX,
            startup->targetY);
        return OverworldWildSpawns_PrepareSpawnAirborneStart(
            fieldSystem,
            startup,
            OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN);
    } else if (primitives->spawnLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP) {
        startup->locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP;
    }
    return TRUE;
}

static void OverworldWildSpawns_ResolveSpawnBehaviorProfile(
    OverworldWildPreparedSpawn *prepared,
    OverworldWildSpawnTerrain terrain,
    u32 forcedOverrideMask)
{
    OverworldWildBehaviorContext behaviorContext;
    OverworldWildSpawnMetadata metadata;
    u8 personal[OW_WILD_PLAYER_BALL_PERSONAL_RECORD_SIZE];
    const OverworldWildRolledEncounter *encounter = &prepared->encounter;

    if (OVERWORLD_WILD_SPAWN_METADATA_ENTRY->tryGet(
            encounter->species,
            encounter->form,
            &metadata)) {
        prepared->playerBallCatchValue = metadata.catchValue;
        behaviorContext.groupFlags = metadata.groupFlags;
    } else {
        ArchiveDataLoadOfs(
            personal,
            ARC_PERSONAL,
            PokeOtherFormMonsNoGet(encounter->species, encounter->form),
            0,
            sizeof(personal));
        prepared->playerBallCatchValue = OverworldWildSpawns_GetPlayerBallCatchValue(
            personal[OW_WILD_PLAYER_BALL_PERSONAL_CATCH_RATE_OFFSET]);
        behaviorContext.groupFlags = 0;
    }
    behaviorContext.species = encounter->species;
    behaviorContext.level = encounter->level;
    behaviorContext.terrain = terrain;
    behaviorContext.shiny = prepared->shiny;
    behaviorContext.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    behaviorContext.reserved = 0;
    behaviorContext.behaviorClass = OverworldWildSpawns_GetBehaviorClassForContext(
        &behaviorContext);
    OverworldWildSpawns_ResolveBehaviorProfileForContext(
        &behaviorContext,
        forcedOverrideMask,
        NULL,
        &prepared->behaviorResolution);
}

static BOOL __attribute__((noinline, optimize("Os", "tree-dominator-opts")))
OverworldWildSpawns_FinalizePreparedSpawn(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot,
    OverworldWildPreparedSpawn *prepared)
{
    struct PlayerProfile *profile;
    BOOL isFollower = slot == OW_WILD_FOLLOWER_SLOT;
    u8 pendingStage = 0;

    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || prepared == NULL
        || prepared->encounter.species == SPECIES_NONE
        || prepared->encounter.level == 0) {
        return FALSE;
    }

    if (!isFollower
        && state->movementRuntimeState != NULL
        && prepared == &OW_WILD_RUNTIME(state)->queuedSpawn) {
        pendingStage = OW_WILD_RUNTIME(state)->refillPositionChecksRemaining;
    }
    if (prepared->startup.locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_NONE) {
        OverworldWildSpawns_ResolveSpawnBehaviorProfile(
            prepared,
            terrain,
            isFollower
                ? 1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER
                : 0);
        if (!isFollower
            && OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit(
                state,
                prepared->behaviorResolution.behaviorLimitKey,
                &prepared->behaviorResolution.profile)) {
            return FALSE;
        }
        /* The prepared value is single-use. Keep resolved metadata across the
         * later one-candidate destination updates instead of repeating it. */
        prepared->startup.locomotion = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    }

    /*
     * Followers prefer their configured destination, but retain the player
     * tile supplied by TrySpawnFollower when wild placement rules reject it.
     */
    if (pendingStage != OW_WILD_SPAWN_STARTUP_PENDING) {
        if (!OverworldWildSpawns_TryApplySpawnDestination(
                state,
                fieldSystem,
                terrain,
                &prepared->behaviorResolution.profile,
                &prepared->position)
            && !isFollower) {
            return FALSE;
        }
        if (pendingStage == OW_WILD_PROFILE_DESTINATION_SCAN_PENDING) {
            OW_WILD_RUNTIME(state)->refillPositionChecksRemaining =
                OW_WILD_SPAWN_STARTUP_PENDING;
            return FALSE;
        }
    }
    if (!OverworldWildSpawns_PrepareSpawnStartup(
            state,
            fieldSystem,
            terrain,
            &prepared->behaviorResolution.primitives,
            &prepared->position,
            &prepared->startup)) {
        return FALSE;
    }
    if (isFollower) {
        /* Party ownership supplies the canonical personality and shiny state. */
        return TRUE;
    }
    profile = Sav2_PlayerData_GetProfileAddr(fieldSystem->savedata);
    if (profile == NULL) {
        return FALSE;
    }
    prepared->encounter.personality =
        OVERWORLD_WILD_CAPTURE_UTILITIES_ENTRY->finalizePersonality(
            prepared->encounter.personality,
            profile->id,
            prepared->shiny);
    return TRUE;
}

static BOOL OverworldWildSpawns_HelperGetPlayerState(
    void *context,
    OverworldWildHelperPlayerState *playerState)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;
    FieldSystem *fieldSystem;
    LocalMapObject *playerObject;

    if (prepContext == NULL
        || prepContext->fieldSystem == NULL
        || prepContext->fieldSystem->playerAvatar == NULL
        || playerState == NULL) {
        return FALSE;
    }

    fieldSystem = prepContext->fieldSystem;
    playerState->playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    playerState->playerY = GetPlayerYCoord(fieldSystem->playerAvatar);
    playerState->objectX = playerState->playerX;
    playerState->objectY = playerState->playerY;
    playerState->facing = OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_NONE;
    playerState->hasObject = FALSE;
    playerState->reserved[0] = 0;
    playerState->reserved[1] = 0;

    playerObject = fieldSystem->playerAvatar->mapObject;
    if (playerObject != NULL
        && OverworldWildSpawns_IsCurrentMapObject(fieldSystem, playerObject)
        && (playerObject->flags & MAPOBJECTFLAG_ACTIVE) != 0) {
        playerState->objectX = OverworldWildSpawns_ObjectCurrentX(playerObject);
        playerState->objectY = OverworldWildSpawns_ObjectCurrentY(playerObject);
        playerState->facing = playerObject->curFacing;
        playerState->hasObject = TRUE;
    }

    return TRUE;
}

static BOOL OverworldWildSpawns_HelperTryGetSpawnTerrain(
    void *context,
    int x,
    int y,
    OverworldWildSpawnTerrain *terrain)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    return OverworldWildSpawns_TryGetSpawnTerrain(
        prepContext->fieldSystem,
        x,
        y,
        terrain);
}

static BOOL OverworldWildSpawns_HelperIsTileOccupied(void *context, int x, int y)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    return OverworldWildSpawns_IsTileOccupiedByObject(prepContext->fieldSystem, x, y);
}

static BOOL OverworldWildSpawns_HelperIsNearActiveSpawn(
    void *context,
    int x,
    int y,
    int radius)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    return OverworldWildSpawns_IsNearActiveSpawn(prepContext->state, x, y, radius);
}

static BOOL OverworldWildSpawns_HelperGetMapId(void *context, u16 *mapId)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    if (prepContext == NULL
        || prepContext->fieldSystem == NULL
        || prepContext->fieldSystem->location == NULL
        || mapId == NULL) {
        return FALSE;
    }

    *mapId = prepContext->fieldSystem->location->mapId;
    return TRUE;
}

static BOOL OverworldWildSpawns_HelperLoadArchiveData(
    void *context,
    int arcId,
    int datId,
    int offset,
    void *dest,
    int size)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    if (dest == NULL || size <= 0) {
        return FALSE;
    }

    if (arcId == ARC_ENCOUNTERS
        && offset == 0
        && size == MAP_EVENTS_WILD_ENCOUNTERS_SIZE
        && prepContext != NULL
        && prepContext->fieldSystem != NULL
        && prepContext->fieldSystem->location != NULL
        && prepContext->fieldSystem->map_events != NULL) {
        u16 mapId = prepContext->fieldSystem->location->mapId;

        if (MapHeader_HasWildEncounters(mapId)
            && datId == MapHeader_GetWildEncounterBank(mapId)) {
            memcpy(
                dest,
                prepContext->fieldSystem->map_events->wildEncounters,
                MAP_EVENTS_WILD_ENCOUNTERS_SIZE);
            return TRUE;
        }
    }

    ArchiveDataLoadOfs(dest, arcId, datId, offset, size);
    return TRUE;
}

static BOOL OverworldWildSpawns_HelperTryGetEncounterDataId(
    void *context,
    int *encounterDataId)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    return OverworldWildSpawns_TryGetEncounterDataId(
        prepContext->fieldSystem,
        encounterDataId);
}

static int OverworldWildSpawns_HelperFindSavedShiny(
    void *context,
    OverworldWildSpawnTerrain terrain)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    if (prepContext == NULL
        || prepContext->fieldSystem == NULL
        || prepContext->fieldSystem->location == NULL) {
        return -1;
    }

    return OverworldWildSpawns_FindSavedShiny(
        prepContext->state,
        prepContext->fieldSystem->location->mapId,
        terrain);
}

static void OverworldWildSpawns_HelperLoadSavedShiny(
    void *context,
    int savedShinySlot,
    OverworldWildRolledEncounter *encounter)
{
    OverworldWildSpawnPrepContext *prepContext = (OverworldWildSpawnPrepContext *)context;

    if (prepContext == NULL || encounter == NULL) {
        return;
    }

    OverworldWildSpawns_LoadSavedShinyEncounter(prepContext->state, savedShinySlot, encounter);
}

static const OverworldWildHelperSpawnCallbacks sOverworldWildSpawnPrepCallbacks
    __attribute__((section(".overworld_wild_spawns_prefix_bss"))) = {
    OverworldWildSpawns_HelperGetPlayerState,
    OverworldWildSpawns_HelperTryGetSpawnTerrain,
    OverworldWildSpawns_HelperIsTileOccupied,
    OverworldWildSpawns_HelperIsNearActiveSpawn,
    OverworldWildSpawns_HelperGetMapId,
    OverworldWildSpawns_HelperLoadArchiveData,
    OverworldWildSpawns_HelperTryGetEncounterDataId,
    OverworldWildSpawns_HelperFindSavedShiny,
    OverworldWildSpawns_HelperLoadSavedShiny,
};

static OverworldWildHelperPrepareResult OverworldWildSpawns_TryPrepareSpawnWithHelper(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot,
    OverworldWildPreparedSpawn *prepared)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildSpawnPrepContext prepContext = { 0 };
    OverworldWildHelperPrepareResult result;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || prepared == NULL) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    runtime = OW_WILD_RUNTIME(state);
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL || helperEntry->tryPrepareSpawn == NULL) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    prepContext.state = state;
    prepContext.fieldSystem = fieldSystem;
    prepContext.terrain = terrain;
    result = helperEntry->tryPrepareSpawn(
            &sOverworldWildSpawnPrepCallbacks,
            &prepContext,
            terrain,
            slot,
            state->shinySpawned,
            OVERWORLD_WILD_SHINY_BASE_ODDS,
            runtime->refillPositionChecksRemaining,
            prepared);
    if (result != OW_WILD_HELPER_PREPARE_READY) {
        return result;
    }

    return result;
}

static OverworldWildHelperPrepareResult OverworldWildSpawns_TryPrepareEncounterSpawnWithHelper(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    int savedShinySlot,
    BOOL rollPersonality,
    OverworldWildPreparedSpawn *prepared)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    OverworldWildSpawnPrepContext prepContext = { 0 };
    OverworldWildHelperPrepareResult result;

    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || encounter == NULL
        || prepared == NULL) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry == NULL || helperEntry->tryPrepareEncounterSpawn == NULL) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    prepContext.state = state;
    prepContext.fieldSystem = fieldSystem;
    prepContext.terrain = terrain;
    result = helperEntry->tryPrepareEncounterSpawn(
            &sOverworldWildSpawnPrepCallbacks,
            &prepContext,
            terrain,
            slot,
            encounter,
            shiny,
            savedShinySlot,
            rollPersonality,
            OW_WILD_RUNTIME(state)->movementHelpSpawnPositionChecksRemaining,
            prepared);
    if (result != OW_WILD_HELPER_PREPARE_READY) {
        return result;
    }

    return OverworldWildSpawns_FinalizePreparedSpawn(
            state, fieldSystem, terrain, slot, prepared)
        ? OW_WILD_HELPER_PREPARE_READY
        : OW_WILD_HELPER_PREPARE_FAILED;
}

static void OverworldWildSpawns_ApplySpawnObjectSetup(
    int slot,
    LocalMapObject *object,
    const OverworldWildRolledEncounter *encounter,
    u32 spriteId,
    BOOL shiny,
    const OverworldWildBehaviorProfile *profile)
{
    OverworldWildSpawns_SetObjectPassThrough(object, FALSE);
    MapObject_SetID(object, OW_WILD_OBJECT_ID_START + slot);
    MapObject_SetScript(object, OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT);
    OverworldWildSpawns_ApplyMovementRange(object, profile->range);
    OverworldWildSpawns_ApplyPokemonRenderParams(
        object,
        encounter->species,
        encounter->form,
        spriteId,
        shiny);
}

static void OverworldWildSpawns_InitSpawnSlotState(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot,
    LocalMapObject *object,
    const OverworldWildRolledEncounter *encounter,
    BOOL shiny,
    u8 behaviorClass,
    u8 behaviorLimitKey,
    u8 playerBallCatchValue)
{
    u16 encounterGeneration = state->spawns[slot].encounterGeneration + 1;
    OverworldWildSpawn spawn = {
        object,
        encounter->personality,
        fieldSystem->location->mapId,
        encounter->species,
        encounter->form,
        encounter->level,
        terrain,
        shiny,
        TRUE,
        0,
        0
    };

    if (encounterGeneration == 0) {
        encounterGeneration = 1;
    }
    spawn.objectId = OW_WILD_OBJECT_ID_START + slot;
    spawn.encounterGeneration = encounterGeneration;
    state->spawns[slot] = spawn;
    OW_WILD_RUNTIME(state)->playerBallCatchValues[slot] = playerBallCatchValue;
    OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownX[slot] = (s16)OverworldWildSpawns_ObjectCurrentX(object);
    OW_WILD_RUNTIME(state)->spawnPresentations.lastKnownY[slot] = (s16)OverworldWildSpawns_ObjectCurrentY(object);
    OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask &=
        (u16)~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    OW_WILD_RUNTIME(state)->spawnPresentations.farSamples[slot] = 0;
    OW_WILD_RUNTIME(state)->spawnPresentations.distanceDespawnPendingMask &=
        (u16)~OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot);
    OverworldWildSpawns_ResetSlotSpotState(state, slot);
    state->movementBehaviorClasses[slot] = behaviorClass;
    state->movementActorControlModes[slot] =
        OW_WILD_ACTOR_CONTROL_AUTONOMOUS;
    OW_WILD_RUNTIME(state)->movementBehaviorLimitKeys[slot] = behaviorLimitKey;
    OverworldWildSpawns_ClearCachedBehaviorProfile(state, slot);
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_RENDER_OVERRIDE_SAVE_ENABLED
    sOverworldWildMankeyTreeTopPrioritySavedBits[slot] = 0;
    sOverworldWildMankeyTreeTopPriorityBitsSaved[slot] = FALSE;
#if OW_WILD_SPAWNER_MANKEY_TREE_TOP_DRAW_CALLBACK_OVERRIDE_ENABLED
    sOverworldWildMankeyTreeTopSavedDrawCallbacks[slot] = NULL;
    sOverworldWildMankeyTreeTopDrawCallbacksSaved[slot] = FALSE;
#endif
#endif
    OverworldWildSpawns_ClearMankeyTreeTopCache(state, slot);
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
    OverworldWildSpawns_ClearMovementSlotInProgress(state, slot);
#endif
}

static void OverworldWildSpawns_StartSpawnAppearHop(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    LocalMapObject *object;
    u8 direction;

    if (state == NULL
        || fieldSystem == NULL
        || (u32)slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->spawns[slot].object == NULL) {
        return;
    }

    object = state->spawns[slot].object;
    if (MapObject_IsSingleMovementActive(object)) {
        return;
    }

    direction = object->curFacing <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
        ? object->curFacing
        : OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_DOWN;
    state->movementFieldSystem = fieldSystem;
    OverworldWildSpawns_SetObjectFacing(object, direction);
    OverworldWildSpawns_ClearObjectFlags(object, BIT_VANISH);
    (void)OverworldWildSpawns_TryStartManualHopEmote(
        state,
        slot,
        object,
        OW_WILD_SPAWNER_SPOT_STATE_CHILL,
        OW_WILD_SPAWNER_SPOT_STATE_CHILL,
        direction,
        OW_WILD_SPAWNER_SPOT_EMOTE_JUMPS_DEFAULT,
        OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP
            * OW_WILD_SPAWNER_SPOT_EMOTE_JUMPS_DEFAULT,
        OW_WILD_SPAWNER_BUBBLE_ID_NONE,
        FALSE,
        FALSE);
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_StartSpawnStartup(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildPreparedSpawn *prepared)
{
    OverworldActorHandle handle;
    const OverworldWildSpawnStartup *startup;

    if (prepared == NULL) {
        return FALSE;
    }
    startup = &prepared->startup;

    /* A fresh bind resets actor policy. Do it before either setup helper can
     * resolve and cache this member's profile, for every spawn locomotion. */
    if (!OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->bindActor(
            fieldSystem, state, slot, &handle)) {
        return FALSE;
    }
    if (!OverworldWildSpawns_PrepareConditionsForSlot(
            state,
            slot,
            &handle,
            &prepared->behaviorResolution.profile)) {
        (void)OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->unbind(
            &handle,
            OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
        return FALSE;
    }
    OverworldWildSpawns_SeedPreparedBehaviorProfile(
        state,
        slot,
        prepared);
    OverworldWildSpawns_ApplySpawnPassThroughFlag(
        state, slot, state->spawns[slot].object);
    OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits(
        state, fieldSystem, slot, state->spawns[slot].object);

    if (startup->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN) {
        OverworldWildSpawns_StartSpawnRun(state, fieldSystem, slot, startup->targetX, startup->targetY);
    } else if (startup->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN
        || startup->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN) {
        if (OverworldWildSpawns_StartSpawnAirborne(
                state,
                fieldSystem,
                slot,
                startup,
                &prepared->behaviorResolution.profile)) {
            return TRUE;
        }
        (void)OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->unbind(
            &handle,
            OVERWORLD_ACTOR_REASON_CONTEXT_LOST);
        return FALSE;
    } else if (startup->locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_APPEAR_HOP) {
        OverworldWildSpawns_StartSpawnAppearHop(state, fieldSystem, slot);
    }
    return TRUE;
}

static u8 OverworldWildSpawns_CountActiveBehaviorLimitKey(
    OverworldWildSpawnState *state,
    u8 behaviorLimitKey)
{
    u8 count = 0;
    int i;

    if (state == NULL) {
        return 0;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (i != OW_WILD_FOLLOWER_SLOT
            && state->spawns[i].active
            && OW_WILD_RUNTIME(state)->movementBehaviorLimitKeys[i] == behaviorLimitKey) {
            count++;
        }
    }

    return count;
}

static BOOL OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit(
    OverworldWildSpawnState *state,
    u8 behaviorLimitKey,
    const OverworldWildBehaviorProfile *profile)
{
    if (profile == NULL || profile->overworldLimit == 0) {
        return FALSE;
    }

    return OverworldWildSpawns_CountActiveBehaviorLimitKey(state, behaviorLimitKey) >= profile->overworldLimit;
}

static BOOL __attribute__((noinline, optimize("Os")))
OverworldWildSpawns_SpawnPreparedEncounter(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain,
    int slot,
    const OverworldWildPreparedSpawn *prepared)
{
    LocalMapObject *object;
    u32 spriteId;
    const OverworldWildRolledEncounter *encounter;
    int objectX;
    int objectY;
    int deleted;

    if (state == NULL
        || fieldSystem == NULL
        || prepared == NULL
        || state->movementRuntimeState == NULL
        || prepared->encounter.species == SPECIES_NONE
        || prepared->encounter.level == 0) {
        return FALSE;
    }

    deleted = OverworldWildSpawnIdentity_PrepareSlot(
        fieldSystem, state, slot, &OW_WILD_RUNTIME(state)->spawnPresentations);
    if (deleted < 0) {
        return FALSE;
    }
#if OW_WILD_SPAWNER_PERF_DIAGNOSTICS
    while (deleted-- > 0) {
        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);
    }
#endif

    state->movementFieldSystem = fieldSystem;
    encounter = &prepared->encounter;
    spriteId = OverworldWildSpawns_GetSpriteIDForSlot(
        encounter->species,
        encounter->form,
        encounter->personality,
        slot);
    objectX = prepared->position.startX;
    objectY = prepared->position.startY;
    if (prepared->startup.locomotion
            == OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN
        || prepared->startup.locomotion
            == OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN) {
        /* CreateSpecialFieldObjectWithParams creates the visible field sprite
         * before it returns. Give it the presentation origin now; moving only
         * the map object afterward leaves one rendered frame at the landing
         * tile. */
        objectX = prepared->startup.startX;
        objectY = prepared->startup.startY;
    }
    object = OverworldWildSpawns_CreateObject(
        fieldSystem,
        objectX,
        objectY,
        spriteId,
        prepared->shiny,
        &prepared->behaviorResolution.primitives);
    if (object == NULL) {
        return FALSE;
    }

    OverworldWildSpawns_ApplySpawnObjectSetup(
        slot,
        object,
        encounter,
        spriteId,
        prepared->shiny,
        &prepared->behaviorResolution.profile);
    /* Publish the native spawn identity before resolving its first height.
     * The height reader and its diagnostics must bind the object to this
     * exact encounter. Height resolution cannot fail or consume policy. */
    OverworldWildSpawns_InitSpawnSlotState(
        state,
        fieldSystem,
        terrain,
        slot,
        object,
        encounter,
        prepared->shiny,
        prepared->behaviorResolution.behaviorClass,
        prepared->behaviorResolution.behaviorLimitKey,
        prepared->playerBallCatchValue);
    OverworldWildSpawns_ResolveObjectLandingHeight(
        fieldSystem,
        object,
        objectX,
        objectY);

    if (!OverworldWildSpawns_StartSpawnStartup(
            state,
            fieldSystem,
            slot,
            prepared)) {
        OverworldWildSpawns_ResetSlotState(state, slot, TRUE);
        DeleteMapObject(object);
        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);
        return FALSE;
    }
    if (prepared->savedShinySlot >= 0) {
        OverworldWildSpawns_ClearSavedShiny(state, prepared->savedShinySlot);
    }
    if (prepared->shiny && slot != OW_WILD_FOLLOWER_SLOT) {
        state->shinySpawned = TRUE;
        PlaySE(SEQ_SE_PL_KIRAKIRA);
    }

    return TRUE;
}

static void __attribute__((optimize("Os"))) OverworldWildSpawns_CommitQueuedSpawn(
    OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    OverworldWildPreparedSpawn *prepared = &runtime->queuedSpawn;
    OverworldWildQueuedSpawnGuard guard;
    int slot = runtime->queuedSpawnSlotPlusOne - 1;
    int x;
    int y;
    u32 byte;
    BOOL playerTile;
    BOOL destinationFinished = FALSE;

    if (runtime->refillPositionChecksRemaining >= OW_WILD_SPAWN_STARTUP_PENDING) {
        if (!OverworldWildSpawns_FinalizePreparedSpawn(
                state,
                fieldSystem,
                (OverworldWildSpawnTerrain)runtime->queuedSpawnTerrain,
                slot,
                prepared)) {
            if (runtime->refillPositionChecksRemaining >= OW_WILD_SPAWN_STARTUP_PENDING) {
                return;
            }
            runtime->queuedSpawnSlotPlusOne = 0;
            runtime->refillPositionChecksRemaining = 0;
            return;
        }
        destinationFinished = TRUE;
    }

    x = prepared->startup.targetX;
    y = prepared->startup.targetY;

    /* Consume before calling any engine work: cancel/failure cannot retry the
     * same value or clear another encounter's saved shiny record. */
    runtime->queuedSpawnSlotPlusOne = 0;
    runtime->refillPositionChecksRemaining = 0;
    if ((u32)slot >= OW_WILD_MAX_SPAWNS || slot == OW_WILD_FOLLOWER_SLOT
        || !OverworldWildSpawnGuard_Read(state, fieldSystem, prepared, slot,
            &guard, OverworldWildSpawns_QuerySurface)) {
        return;
    }
    if (!destinationFinished) {
        for (byte = 0; byte < sizeof(guard); byte++) {
            if (((const u8 *)&guard)[byte]
                    != ((const u8 *)&runtime->queuedSpawnGuard)[byte]) {
                return;
            }
        }
    }
    playerTile = OverworldWildSpawns_IsPlayerTile(fieldSystem, x, y);
    if ((playerTile
            ? OverworldWildSpawns_IsTileOccupiedByNonPlayerObject(fieldSystem, NULL, x, y)
            : OverworldWildSpawns_IsTileOccupiedByObject(fieldSystem, x, y))
        || OverworldWildSpawns_IsNearActiveSpawn(state, x, y, OW_WILD_SPAWN_MIN_MON_DISTANCE)
        || OverworldWildSpawns_IsBehaviorLimitKeyAtOverworldLimit(state,
            prepared->behaviorResolution.behaviorLimitKey,
            &prepared->behaviorResolution.profile)) {
        return;
    }
    if (OverworldWildSpawns_SpawnPreparedEncounter(state, fieldSystem,
            runtime->queuedSpawnTerrain, slot, prepared)) {
        state->justSpawned = TRUE;
    }
}

static OverworldWildHelperPrepareResult __attribute__((noinline)) OverworldWildSpawns_SpawnOne(OverworldWildSpawnState *state, FieldSystem *fieldSystem,
    OverworldWildSpawnTerrain terrain, int slot)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    OverworldWildPreparedSpawn *prepared = &runtime->queuedSpawn;
    OverworldWildHelperPrepareResult result;

    if (runtime->queuedSpawnSlotPlusOne != 0) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    result = OverworldWildSpawns_TryPrepareSpawnWithHelper(
            state,
            fieldSystem,
            terrain,
            slot,
            prepared);
    if (result != OW_WILD_HELPER_PREPARE_READY) {
        return result;
    }

    if (!OverworldWildSpawns_FinalizePreparedSpawn(
            state, fieldSystem, terrain, slot, prepared)) {
        if (runtime->refillPositionChecksRemaining
                == OW_WILD_PROFILE_DESTINATION_SCAN_PENDING) {
            runtime->queuedSpawnTerrain = terrain;
            runtime->queuedSpawnSlotPlusOne = slot + 1;
            return OW_WILD_HELPER_PREPARE_READY;
        }
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    if (!OverworldWildSpawnGuard_Read(state, fieldSystem, prepared,
            slot, &runtime->queuedSpawnGuard, OverworldWildSpawns_QuerySurface)) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }
    runtime->queuedSpawnTerrain = terrain;
    runtime->queuedSpawnSlotPlusOne = slot + 1;
    return OW_WILD_HELPER_PREPARE_READY;
}

static struct PartyPokemon *OverworldWildSpawns_GetSelectedFollowerPokemon(
    FieldSystem *fieldSystem,
    u8 *partySlot)
{
    return OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->getSelectedPokemon(
        fieldSystem,
        partySlot);
}

static BOOL OverworldWildSpawns_RemoveFollower(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    OverworldWildSpawn *spawn;
    LocalMapObject *object = NULL;

    if (state == NULL) {
        return FALSE;
    }
    spawn = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    if (!spawn->active) {
        state->activeFollowerPartySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
        return TRUE;
    }

    if (OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, spawn)) {
        object = spawn->object;
    } else if (OverworldWildSpawns_IsFieldContextAvailable(fieldSystem)
        && ((MapObjectMan *)fieldSystem->mapObjectMan)->objects != NULL
        && spawn->mapId == fieldSystem->location->mapId
        && OverworldWildSpawns_QuarantinePoisonedPresentation(
            fieldSystem,
            OW_WILD_FOLLOWER_SLOT)) {
        /* A verified ID/script match was removed without trusting the pointer. */
    } else {
        /* Preserve logical ownership until presentation reconciliation is safe. */
        state->presentationRestorePending = TRUE;
        if (state->movementRuntimeState != NULL) {
            OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask |=
                OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(OW_WILD_FOLLOWER_SLOT);
        }
        gOverworldWildResidentData.pendingFlags |=
            OW_WILD_FIELD_IDLE_REARM_PENDING
            | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        return FALSE;
    }

    OverworldWildSpawns_ResetSlotState(
        state,
        OW_WILD_FOLLOWER_SLOT,
        TRUE);
    if (object != NULL) {
        DeleteMapObject(object);
        OW_WILD_PERF_INC(sOverworldWildPerfMapObjectDeletesThisFrame);
    }
    state->activeFollowerPartySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    return TRUE;
}

static BOOL OverworldWildSpawns_FollowerMatchesSelection(
    OverworldWildSpawnState *state,
    struct PartyPokemon *pokemon,
    u8 partySlot)
{
    OverworldWildSpawn *spawn = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    BOOL locked;
    BOOL matches;

    if (!spawn->active || state->activeFollowerPartySlot != partySlot) {
        return FALSE;
    }
    /* The sole caller just validated this mon through the selector's native
     * GetMonData eligibility reads (including checksum/egg checks). Keep one
     * synchronous read lock instead of decrypting the same party data for
     * every identity field on every refill. Never retain it across updates. */
    locked = OverworldWildSpawns_AcquireMonLock(pokemon);
    matches = spawn->species == OverworldWildSpawns_ReadMonData(pokemon, MON_DATA_SPECIES, NULL)
        && spawn->form == OverworldWildSpawns_ReadMonData(pokemon, MON_DATA_FORM, NULL)
        && spawn->level == OverworldWildSpawns_ReadMonData(pokemon, MON_DATA_LEVEL, NULL)
        && spawn->personality
            == OverworldWildSpawns_ReadMonData(pokemon, MON_DATA_PERSONALITY, NULL)
        && spawn->shiny == OverworldWildSpawns_MonIsShiny(pokemon);
    OverworldWildSpawns_ReleaseMonLock(pokemon, locked);
    return matches;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_ReconcileFollowerSelection(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    struct PartyPokemon *pokemon;
    u8 partySlot;

    if (!state->spawns[OW_WILD_FOLLOWER_SLOT].active) {
        state->activeFollowerPartySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
        return TRUE;
    }
    pokemon = OverworldWildSpawns_GetSelectedFollowerPokemon(
        fieldSystem,
        &partySlot);
    if (pokemon == NULL
        || !OverworldWildSpawns_FollowerMatchesSelection(
            state,
            pokemon,
            partySlot)) {
        return OverworldWildSpawns_RemoveFollower(state, fieldSystem);
    }
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_TrySpawnFollower(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    BOOL *hasCandidate)
{
    struct PartyPokemon *pokemon;
    OverworldWildRolledEncounter encounter;
    OverworldWildPreparedSpawn prepared;
    u32 personality;
    BOOL shiny;
    u8 partySlot;
    BOOL spawned;

    if (hasCandidate != NULL) {
        *hasCandidate = FALSE;
    }
    if (state == NULL
        || fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || fieldSystem->playerAvatar == NULL
        || state->spawns[OW_WILD_FOLLOWER_SLOT].active) {
        return FALSE;
    }

    pokemon = OverworldWildSpawns_GetSelectedFollowerPokemon(
        fieldSystem,
        &partySlot);
    if (pokemon == NULL) {
        return FALSE;
    }

    encounter.species = (u16)GetMonData(pokemon, MON_DATA_SPECIES, NULL);
    encounter.form = (u8)GetMonData(pokemon, MON_DATA_FORM, NULL);
    encounter.level = (u8)GetMonData(pokemon, MON_DATA_LEVEL, NULL);
    personality = GetMonData(pokemon, MON_DATA_PERSONALITY, NULL);
    encounter.personality = personality;
    shiny = MonIsShiny(pokemon);
    if (hasCandidate != NULL) {
        *hasCandidate = TRUE;
    }

    if (state->followerReleaseState != OW_WILD_FOLLOWER_RELEASE_NONE
        && (state->followerReleaseState
                & OW_WILD_FOLLOWER_RELEASE_STATE_MASK)
            != OW_WILD_FOLLOWER_RELEASE_READY) {
        return FALSE;
    }

    memset(&prepared, 0, sizeof(prepared));
    prepared.encounter = encounter;
    prepared.position.startX = GetPlayerXCoord(fieldSystem->playerAvatar);
    prepared.position.startY = GetPlayerYCoord(fieldSystem->playerAvatar);
    prepared.shiny = shiny;
    prepared.savedShinySlot = -1;
    if (!OverworldWildSpawns_FinalizePreparedSpawn(
            state,
            fieldSystem,
            OW_WILD_SPAWN_TERRAIN_LAND,
            OW_WILD_FOLLOWER_SLOT,
            &prepared)) {
        return FALSE;
    }
    if (state->followerReleaseState != OW_WILD_FOLLOWER_RELEASE_NONE) {
        prepared.position.startX = state->followerReleaseX;
        prepared.position.startY = state->followerReleaseY;
        prepared.startup.locomotion = OW_WILD_BEHAVIOR_LOCOMOTION_NONE;
    }

    spawned = OverworldWildSpawns_SpawnPreparedEncounter(
        state,
        fieldSystem,
        OW_WILD_SPAWN_TERRAIN_LAND,
        OW_WILD_FOLLOWER_SLOT,
        &prepared);
    if (spawned) {
        state->activeFollowerPartySlot = partySlot;
        if ((state->followerReleaseState
                & OW_WILD_FOLLOWER_RELEASE_AGGRO_FLAG) != 0) {
            OverworldWildSpawns_EnterAggroState(
                state,
                OW_WILD_FOLLOWER_SLOT,
                state->spawns[OW_WILD_FOLLOWER_SLOT].object);
        }
        state->followerReleaseState =
            state->followerReleaseState != OW_WILD_FOLLOWER_RELEASE_NONE
                ? OW_WILD_FOLLOWER_RELEASE_SPAWNED
                : OW_WILD_FOLLOWER_RELEASE_NONE;
    }
    return spawned;
}

static void OverworldWildSpawns_ApplyHelpChildSpawnState(
    OverworldWildSpawnState *state,
    int slot,
    LocalMapObject *object)
{
    if (state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_EMOTING) {
        state->movementEmoteEndStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
        return;
    }

    state->movementSpotStates[slot] = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    OverworldWildSpawns_ClearWalkMovementState(state, slot, object);
    if (!OverworldWildSpawns_IsMovementSlotInProgress(state, slot)
        && (object == NULL || !MapObject_IsSingleMovementActive(object))) {
        OverworldWildSpawns_ResumeOwnerAfterAlert(state, slot, object);
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, state->movementFieldSystem);
#endif
}

static void OverworldWildSpawns_ClearQueuedHelpChildren(OverworldWildSpawnState *state)
{
    OverworldWildOverlayRuntimeState *runtime;

    if (state->movementRuntimeState == NULL) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    runtime->movementHelpSpawnParentSlotPlusOne = 0;
    runtime->movementHelpSpawnRemaining = 0;
    runtime->movementHelpSpawnPositionChecksRemaining = 0;
}

static OverworldWildHelperPrepareResult OverworldWildSpawns_TrySpawnOneHelpChild(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int parentSlot)
{
    int childSlot;
    OverworldWildRolledEncounter encounter = { 0 };
    OverworldWildPreparedSpawn prepared;
    OverworldWildSpawnTerrain terrain;
    OverworldWildHelperPrepareResult result;

    if (state == NULL
        || fieldSystem == NULL
        || parentSlot < 0
        || parentSlot >= OW_WILD_MAX_SPAWNS
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        || !OverworldWildSpawns_IsCurrentSpawnObject(
            fieldSystem,
            &state->spawns[parentSlot])) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    terrain = (OverworldWildSpawnTerrain)state->spawns[parentSlot].terrain;
    if (!OverworldWildSpawns_TryGetFreeSlot(
            state,
            0,
            OW_WILD_LAND_SURF_MAX_SPAWNS,
            &childSlot)) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    encounter.species = state->spawns[parentSlot].species;
    encounter.form = state->spawns[parentSlot].form;
    encounter.level = state->spawns[parentSlot].level;
    result = OverworldWildSpawns_TryPrepareEncounterSpawnWithHelper(
            state,
            fieldSystem,
            terrain,
            childSlot,
            &encounter,
            FALSE,
            -1,
            TRUE,
            &prepared);
    if (result != OW_WILD_HELPER_PREPARE_READY) {
        return result;
    }
    if (!OverworldWildSpawns_SpawnPreparedEncounter(
            state,
            fieldSystem,
            terrain,
            childSlot,
            &prepared)) {
        return OW_WILD_HELPER_PREPARE_FAILED;
    }

    OverworldWildSpawns_ApplyHelpChildSpawnState(
        state,
        childSlot,
        state->spawns[childSlot].object);
    return OW_WILD_HELPER_PREPARE_READY;
}

static void OverworldWildSpawns_SpawnQueuedHelpChildren(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    OverworldWildOverlayRuntimeState *runtime;
    OverworldWildHelperPrepareResult result;
    int parentSlot;

    if (state->movementRuntimeState == NULL) {
        return;
    }

    runtime = OW_WILD_RUNTIME(state);
    if (runtime->movementHelpSpawnParentSlotPlusOne == 0
        || runtime->movementHelpSpawnRemaining == 0) {
        return;
    }

    parentSlot = runtime->movementHelpSpawnParentSlotPlusOne - 1;
    if (runtime->movementHelpSpawnPositionChecksRemaining == 0) {
        runtime->movementHelpSpawnPositionChecksRemaining =
            OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES;
    }
    result = OverworldWildSpawns_TrySpawnOneHelpChild(
        state,
        fieldSystem,
        parentSlot);
    if (result == OW_WILD_HELPER_PREPARE_POSITION_PENDING) {
        runtime->movementHelpSpawnPositionChecksRemaining--;
        return;
    }
    runtime->movementHelpSpawnPositionChecksRemaining = 0;
    runtime->movementHelpSpawnRemaining--;
    if (runtime->movementHelpSpawnRemaining == 0) {
        OverworldWildSpawns_ClearQueuedHelpChildren(state);
    }
}

static void OverworldWildSpawns_TrySpawnHelpChildren(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot,
    const OverworldWildBehaviorProfile *profile)
{
    OverworldWildOverlayRuntimeState *runtime;
    u8 spawnCount = OW_WILD_SPAWNER_SWARM_MAX_EXTRA_SPAWNS;
    u8 activeCount;

    if (slot == OW_WILD_FOLLOWER_SLOT
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)) {
        return;
    }

    runtime = OverworldWildSpawns_EnsureRuntimeState(state);
    if (runtime == NULL) {
        return;
    }
    if (runtime->movementHelpSpawnRemaining != 0) {
        return;
    }

    if (profile->overworldLimit != 0) {
        activeCount = OverworldWildSpawns_CountActiveBehaviorLimitKey(
            state,
            runtime->movementBehaviorLimitKeys[slot]);
        if (activeCount >= profile->overworldLimit) {
            return;
        }
        spawnCount = profile->overworldLimit - activeCount;
    }

    runtime->movementHelpSpawnParentSlotPlusOne = (u8)(slot + 1);
    runtime->movementHelpSpawnRemaining = spawnCount;
    runtime->movementHelpSpawnPositionChecksRemaining = 0;

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
}

static void OverworldWildSpawns_DespawnFarMons(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    const OverworldWildHelperOverlayEntry *helperEntry =
        OverworldWildSpawns_GetHelperOverlayEntry();
    u16 hardProtectedMask =
        OverworldWildSpawns_GetThrowParticipantMask(state)
        | OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(OW_WILD_FOLLOWER_SLOT);

    if (runtime->throwState.targetMask != 0) {
        hardProtectedMask = 0xFFFF;
    }

    if (helperEntry != NULL && helperEntry->despawnFarEncounters != NULL) {
        helperEntry->despawnFarEncounters(
            fieldSystem,
            state,
            &runtime->spawnPresentations,
            &runtime->despawnTelemetry,
            hardProtectedMask,
            state->movementInProgressMask,
            OverworldWildSpawns_ResetSlotState);
    }
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_TryRefill(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    OverworldWildOverlayRuntimeState *runtime = OW_WILD_RUNTIME(state);
    OverworldWildHelperPrepareResult prepareResult =
        OW_WILD_HELPER_PREPARE_FAILED;
    BOOL followerCandidate = FALSE;
    OverworldWildSpawnTerrain preferredTerrain;
    u8 sharedSpawnCount;
    int slot;
    BOOL spawned = FALSE;

    /* Cold metadata and profile blobs must not load in the same update as
     * object creation. Retain the existing refill request until both attempts
     * finish; failure remains latched by the normal loaders. No RNG or timer
     * is consumed during warmup. Direct user release keeps its existing path. */
    if (sOverworldWildFlags.spawnWarmupPhase < 2) {
        if (sOverworldWildFlags.spawnWarmupPhase == 0) {
            if (OverworldWildSpawns_GetHelperOverlayEntry() == NULL) {
                return FALSE;
            }
            (void)OverworldWildSpawns_GetSpriteID(SPECIES_BULBASAUR, 0);
        } else {
            (void)OverworldWildSpawns_GetBehaviorDataBlob();
        }
        sOverworldWildFlags.spawnWarmupPhase++;
        return FALSE;
    }
    if (runtime->refillTerrainMask == 0
        && runtime->refillPositionChecksRemaining == 0) {
        (void)OverworldWildSpawns_PopulationControl(
            OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL,
            OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);
    }
    if (!OverworldWildSpawns_ReconcileFollowerSelection(
            state,
            fieldSystem)) {
        return FALSE;
    }
    if (!state->spawns[OW_WILD_FOLLOWER_SLOT].active) {
        if (OverworldWildSpawns_TrySpawnFollower(
                state,
                fieldSystem,
                &followerCandidate)) {
            return TRUE;
        }
        if (followerCandidate) {
            /* Never let an ordinary spawn consume this refill before the follower. */
            return FALSE;
        }
    }
    if ((OW_WILD_RUNTIME(state)->residentData->pendingFlags
            & OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING) != 0) {
        return TRUE;
    }
    /* Followers are valid everywhere; ordinary wild spawns are not. */
    if (!OverworldWildSpawns_IsEnabledMap(fieldSystem)) {
        runtime->refillTerrainMask = 0;
        runtime->refillPositionChecksRemaining = 0;
        return TRUE;
    }

    if (runtime->refillPositionChecksRemaining != 0) {
        slot = runtime->refillLandSurfSlot;
        if (state->spawns[slot].active) {
            prepareResult = OW_WILD_HELPER_PREPARE_FAILED;
            goto refill_attempt_finished;
        }
        preferredTerrain = ((slot & 1) != 0)
                == ((runtime->refillTerrainMask & 8) != 0)
            ? OW_WILD_SPAWN_TERRAIN_SURF : OW_WILD_SPAWN_TERRAIN_LAND;
        goto run_refill_attempt;
    }

    if (runtime->refillTerrainMask == 0) {
        /* Bits are ordered work, not a second timer: Headbutt, Fishing,
         * preferred Land/Surf, alternate Land/Surf. Roll the gates once. */
        runtime->refillTerrainMask = 4 | 8;
        if (state->headbuttSpawnCooldown != 0) {
            state->headbuttSpawnCooldown--;
        } else {
            state->headbuttSpawnCooldown = OW_WILD_HEADBUTT_REFILL_ATTEMPT_COOLDOWN;
            if ((gf_rand() % 100) < OW_WILD_HEADBUTT_SPAWN_CHANCE_PERCENT) {
                runtime->refillTerrainMask |= 1;
            }
        }

        if (state->fishingSpawnCooldown != 0) {
            state->fishingSpawnCooldown--;
        } else {
            state->fishingSpawnCooldown = OW_WILD_FISHING_REFILL_ATTEMPT_COOLDOWN;
            if ((gf_rand() % 100) < OW_WILD_FISHING_SPAWN_CHANCE_PERCENT) {
                runtime->refillTerrainMask |= 2;
            }
        }
    }

    while (runtime->refillTerrainMask != 0) {
        if (runtime->refillTerrainMask & 1) {
            runtime->refillTerrainMask &= ~1;
            if (!OverworldWildSpawns_TryGetFreeSlot(state,
                    OW_WILD_HEADBUTT_SLOT_START, OW_WILD_FISH_SLOT_START, &slot)) {
                continue;
            }
            preferredTerrain = OW_WILD_SPAWN_TERRAIN_HEADBUTT;
        } else if (runtime->refillTerrainMask & 2) {
            runtime->refillTerrainMask &= ~2;
            if (!OverworldWildSpawns_TryGetFreeSlot(state,
                    OW_WILD_FISH_SLOT_START, OW_WILD_MAX_SPAWNS, &slot)) {
                continue;
            }
            preferredTerrain = OW_WILD_SPAWN_TERRAIN_FISHING;
        } else {
            if (runtime->refillTerrainMask & 4) {
                runtime->refillTerrainMask &= ~4;
                if (!OverworldWildSpawns_TryGetFreeSlot(state,
                        0, OW_WILD_LAND_SURF_MAX_SPAWNS, &slot)) {
                    runtime->refillTerrainMask = 0;
                    break;
                }
                runtime->refillLandSurfSlot = slot;
                preferredTerrain = (slot & 1) != 0
                    ? OW_WILD_SPAWN_TERRAIN_SURF : OW_WILD_SPAWN_TERRAIN_LAND;
            } else {
                runtime->refillTerrainMask = 0;
                slot = runtime->refillLandSurfSlot;
                if (!OverworldWildSpawns_TryGetFreeSlot(state, slot, slot + 1, &slot)) {
                    break;
                }
                preferredTerrain = (slot & 1) != 0
                    ? OW_WILD_SPAWN_TERRAIN_LAND : OW_WILD_SPAWN_TERRAIN_SURF;
            }
        }
        runtime->refillPositionChecksRemaining =
            preferredTerrain <= OW_WILD_SPAWN_TERRAIN_SURF
            ? OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_UPDATES
            : 1;
run_refill_attempt:
        prepareResult = OverworldWildSpawns_SpawnOne(
            state, fieldSystem, preferredTerrain, slot);
        if (prepareResult == OW_WILD_HELPER_PREPARE_POSITION_PENDING) {
            runtime->refillPositionChecksRemaining--;
            return TRUE;
        }
        break; /* Never start a second terrain search in this update. */
    }
refill_attempt_finished:
    if (runtime->refillPositionChecksRemaining < OW_WILD_SPAWN_STARTUP_PENDING) {
        runtime->refillPositionChecksRemaining = 0;
    }
    spawned = prepareResult == OW_WILD_HELPER_PREPARE_READY;
    if (spawned) {
        runtime->refillTerrainMask = 0;
    }
    if (runtime->refillTerrainMask != 0) {
        return TRUE;
    }

    /* A successful ordinary attempt is queued until the next update. Count it
     * now without reading the queue again; optional groups do not add density. */
    sharedSpawnCount = spawned && slot < OW_WILD_LAND_SURF_MAX_SPAWNS;
    for (slot = 0; slot < OW_WILD_LAND_SURF_MAX_SPAWNS; slot++) {
        sharedSpawnCount += state->spawns[slot].active;
    }
    if (sharedSpawnCount == 0) {
        sharedSpawnCount = 1;
    }
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL,
        OW_WILD_REFILL_BASE_INTERVAL_FRAMES * sharedSpawnCount - 1);
    return TRUE;
}

static BOOL OverworldWildSpawns_IsTouchingPlayer(OverworldWildSpawnState *state, FieldSystem *fieldSystem, int slot)
{
    const OverworldWildSpawn *spawn = &state->spawns[slot];
    int dx;
    int dy;

    if (!spawn->active || spawn->object == NULL) {
        return FALSE;
    }

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
    if (OverworldWildSpawns_GetThrowParticipantMask(state) & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) {
        return FALSE;
    }
    if (OverworldWildSpawns_IsMovementSlotInProgress(state, slot)
        || MapObject_IsSingleMovementActive(spawn->object)) {
        return FALSE;
    }
#endif

    dx = (int)OverworldWildSpawns_ObjectCurrentX(spawn->object) - GetPlayerXCoord(fieldSystem->playerAvatar);
    dy = (int)OverworldWildSpawns_ObjectCurrentY(spawn->object) - GetPlayerYCoord(fieldSystem->playerAvatar);

    if (dx < 0) {
        dx = -dx;
    }
    if (dy < 0) {
        dy = -dy;
    }

    return (dx + dy) == 1;
}

static BOOL OverworldWildSpawns_HasPendingBattle(OverworldWildSpawnState *state)
{
    return state->pendingSlot >= 0;
}

static BOOL OverworldWildSpawns_HasQueuedBattle(OverworldWildSpawnState *state)
{
    return state->movementQueuedBattleSlot >= 0
        && state->movementQueuedBattleSlot < OW_WILD_MAX_SPAWNS;
}

static u8 OverworldWildSpawns_GetBattleTriggerForSlot(
    const OverworldWildSpawnState *state,
    int slot,
    const OverworldWildBehaviorProfile *profile)
{
    if (state == NULL
        || profile == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS) {
        return OW_WILD_BEHAVIOR_BATTLE_TRIGGER_NONE;
    }

    if (OverworldWildSpawns_GetActiveConditionApplications(state, slot) != 0) {
        return profile->battleTrigger;
    }

    return OW_WILD_BEHAVIOR_BATTLE_TRIGGER_NONE;
}

static BOOL __attribute__((optimize("Os"))) OverworldWildSpawns_IsSlotStableForBattle(OverworldWildSpawnState *state, int slot)
{
    LocalMapObject *object;

    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active
        || state->spawns[slot].object == NULL) {
        return FALSE;
    }

    object = state->spawns[slot].object;
    if ((OverworldWildSpawns_GetThrowParticipantMask(state) & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0
        || state->movementStagedHopPending[slot]
        || state->movementCrashShakeTimers[slot] != 0
        || state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_EMOTING
        || state->movementSpotStates[slot] == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        || OverworldWildSpawns_IsMovementSlotInProgress(state, slot)
        || MapObject_IsSingleMovementActive(object)) {
        return FALSE;
    }
    if (OverworldWildSpawns_HasConditionalTeleportPresentation(state, slot)) {
        return FALSE;
    }

    return TRUE;
}

static void OverworldWildSpawns_PrepareSlotForBattle(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || !state->spawns[slot].active) {
        return;
    }

    if (!OverworldWildSpawns_HasConditionalTeleportPresentation(state, slot)) {
        return;
    }

    OverworldWildSpawns_RevealTeleportObject(state, slot, state->spawns[slot].object);
}

static void OverworldWildSpawns_PrimePendingBattleForSlot(OverworldWildSpawnState *state, int slot)
{
    if (state == NULL || slot < 0 || slot >= OW_WILD_MAX_SPAWNS) {
        return;
    }

    state->movementBattleSettleFrames = 0;
    state->movementQueuedBattleSlot = -1;
    state->pendingPersonality = state->spawns[slot].personality;
    state->pendingSpecies = state->spawns[slot].species | (state->spawns[slot].form << OW_WILD_FORM_SHIFT);
    state->pendingLevel = state->spawns[slot].level;
    state->pendingShiny = state->spawns[slot].shiny;
    state->pendingSlot = slot;
    state->pendingMapGeneration = state->mapGeneration;
    state->pendingEncounterGeneration = state->spawns[slot].encounterGeneration;
    (void)OverworldWildSpawns_PopulationControl(
        OVERWORLD_ACTOR_POPULATION_CONTROL_SCHEDULE_REFILL,
        OW_WILD_REFILL_BASE_INTERVAL_FRAMES - 1);
    state->battleGraceSteps = 0;
}

static BOOL OverworldWildSpawns_IsPlayerStableForBattle(FieldSystem *fieldSystem)
{
    OverworldActorQuery query;
    OverworldActorSnapshot snapshot;

    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_WORLD_GATE;
    query.index = OVERWORLD_ACTOR_WORLD_GATE_BATTLE;
    return !MapObject_IsSingleMovementActive(
            fieldSystem->playerAvatar->mapObject)
        && OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(&query, &snapshot)
            == OVERWORLD_ACTOR_RESULT_OK;
}

static BOOL OverworldWildSpawns_TryStartBattleForSlot(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || OverworldWildSpawns_HasPendingBattle(state)
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || OW_WILD_RUNTIME(state)->throwState.targetMask != 0
        || !OverworldWildSpawns_IsPlayerStableForBattle(fieldSystem)
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }

    if (!OverworldWildSpawns_IsSlotStableForBattle(state, slot)) {
        return FALSE;
    }
    OverworldWildSpawns_PrepareSlotForBattle(state, slot);
    OverworldWildSpawns_ResetAllMovementCommands(state, TRUE, FALSE);
    state->movementFieldSystem = fieldSystem;

    OverworldWildSpawns_PrimePendingBattleForSlot(state, slot);

    if (!OverworldWildSpawns_RequestBattleScript(fieldSystem, state, slot)) {
        OverworldWildSpawns_ResetPendingBattle(state);
        return FALSE;
    }
    return TRUE;
}

static BOOL OverworldWildSpawns_QueueBattleForSlot(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || OverworldWildSpawns_HasPendingBattle(state)
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || OW_WILD_RUNTIME(state)->throwState.targetMask != 0
        || (OverworldWildSpawns_GetThrowParticipantMask(state) & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0
        || !OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }

    state->movementQueuedBattleSlot = slot;
    state->pendingMapGeneration = state->mapGeneration;
    state->pendingEncounterGeneration =
        state->spawns[slot].encounterGeneration;
    state->movementBattleSettleFrames = OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES;
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartBattleForSlotOrQueue(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    if (OverworldWildSpawns_TryStartBattleForSlot(state, fieldSystem, slot)) {
        return TRUE;
    }

    return OverworldWildSpawns_QueueBattleForSlot(state, fieldSystem, slot);
}

static BOOL OverworldWildSpawns_TryStartQueuedBattle(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    int slot;

    if (OverworldWildSpawns_HasPendingBattle(state)
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || !OverworldWildSpawns_HasQueuedBattle(state)) {
        return FALSE;
    }

    slot = state->movementQueuedBattleSlot;
    if (!OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        || state->pendingMapGeneration != state->mapGeneration
        || state->pendingEncounterGeneration
            != state->spawns[slot].encounterGeneration
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        state->movementQueuedBattleSlot = -1;
        return FALSE;
    }
    if (state->movementBattleSettleFrames != 0) {
        state->movementBattleSettleFrames--;
        return FALSE;
    }

    if (!OverworldWildSpawns_IsSlotStableForBattle(state, slot)) {
        state->movementBattleSettleFrames = OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES;
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
        OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
#endif
        return FALSE;
    }

    return OverworldWildSpawns_TryStartBattleForSlot(state, fieldSystem, slot);
}

static BOOL OverworldWildSpawns_TryPrimeBattleFromTalkSlot(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem,
    int slot)
{
    if (state == NULL
        || fieldSystem == NULL
        || slot < 0
        || slot >= OW_WILD_MAX_SPAWNS
        || slot == OW_WILD_FOLLOWER_SLOT
        || OverworldWildSpawns_HasPendingBattle(state)
        || OverworldWildSpawns_IsPlayerBallProjectileActive()
        || OW_WILD_RUNTIME(state)->throwState.targetMask != 0
        || (OverworldWildSpawns_GetThrowParticipantMask(state) & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0
        || !OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
        return FALSE;
    }

    if (!OverworldWildSpawns_IsPlayerStableForBattle(fieldSystem)) {
        return FALSE;
    }

    OverworldWildSpawns_PrepareSlotForBattle(state, slot);
    OverworldWildSpawns_ResetAllMovementCommands(state, TRUE, FALSE);
    state->movementFieldSystem = fieldSystem;
    OverworldWildSpawns_PrimePendingBattleForSlot(state, slot);
    return TRUE;
}

static int OverworldWildSpawns_FindBattleTalkSlot(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject)
{
    if (state == NULL || state->movementRuntimeState == NULL) {
        return -1;
    }
    {
        const OverworldWildHelperOverlayEntry *helperEntry =
            OverworldWildSpawns_GetHelperOverlayEntry();

        if (helperEntry == NULL) {
            return -1;
        }
        return helperEntry->findBattleTalkSlot(
            fieldSystem,
            state,
            talkedObject,
            OverworldWildSpawns_GetThrowParticipantMask(state)
                | OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(OW_WILD_FOLLOWER_SLOT));
    }
}

static BOOL OverworldWildSpawns_OverlayTryPrimeBattleFromTalk(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    LocalMapObject *talkedObject)
{
    int slot = OverworldWildSpawns_FindBattleTalkSlot(fieldSystem, state, talkedObject);

    if (slot < 0) {
        return FALSE;
    }

    return OverworldWildSpawns_TryPrimeBattleFromTalkSlot(state, fieldSystem, slot);
}

static BOOL OverworldWildSpawns_TryStartBattleFromAButton(
    OverworldWildSpawnState *state,
    FieldSystem *fieldSystem)
{
    LocalMapObject *facingObject = NULL;
    u16 physicalKeys = PAD_Read();
    int slot;

    if ((OVERWORLD_FOLLOWER_SELECTOR_STATE
            & (OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG
                | OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG)) != 0) {
        state->movementAButtonDown =
            (physicalKeys & PAD_BUTTON_A) != 0;
        return FALSE;
    }
    if ((physicalKeys & PAD_BUTTON_A) == 0) {
        state->movementAButtonDown = FALSE;
        return FALSE;
    }
    if (state->movementAButtonDown) {
        return FALSE;
    }

    slot = OverworldWildSpawns_FindBattleTalkSlot(fieldSystem, state, NULL);
    if (slot < 0) {
        return FALSE;
    }

    if (sub_0203DC64(fieldSystem, &facingObject)
        && facingObject != state->spawns[slot].object) {
        state->movementAButtonDown = TRUE;
        return FALSE;
    }

    if (!OverworldWildSpawns_TryStartBattleForSlotOrQueue(state, fieldSystem, slot)) {
        return FALSE;
    }

    state->movementAButtonDown = TRUE;
    return TRUE;
}

static BOOL OverworldWildSpawns_TryStartBattle(OverworldWildSpawnState *state, FieldSystem *fieldSystem)
{
    int i;

    if (state->battleGraceSteps != 0) {
        return FALSE;
    }

    if (OverworldWildSpawns_HasPendingBattle(state)) {
        return FALSE;
    }

    if (state->justSpawned) {
        state->justSpawned = FALSE;
        return FALSE;
    }

    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        OverworldWildBehaviorProfile profile;
        u8 battleTrigger;

        if (i == OW_WILD_FOLLOWER_SLOT || !state->spawns[i].active) {
            continue;
        }
        if (!OverworldWildSpawns_IsCurrentSpawnObject(
                fieldSystem,
                &state->spawns[i])) {
            state->presentationRestorePending = TRUE;
            continue;
        }

        if (!OverworldWildSpawns_IsTouchingPlayer(state, fieldSystem, i)) {
            continue;
        }

        OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot(
            state, i, &profile, NULL);
        battleTrigger = OverworldWildSpawns_GetBattleTriggerForSlot(
            state,
            i,
            &profile);
        if (battleTrigger == OW_WILD_BEHAVIOR_BATTLE_TRIGGER_CONTACT) {
            return OverworldWildSpawns_TryStartBattleForSlotOrQueue(state, fieldSystem, i);
        }
    }

    return FALSE;
}

static u8 OverworldWildSpawns_OverlayCleanupPendingBattle(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 battleResult)
{
    const OverworldWildHelperOverlayEntry *helperEntry;
    u8 disposition = OW_WILD_BATTLE_DISPOSITION_RETAIN;

    if (OverworldWildSpawns_EnsureRuntimeState(state) == NULL) {
        if (state != NULL) {
            OverworldWildSpawns_ResetPendingBattle(state);
            state->movementQueuedBattleSlot = -1;
            state->movementBattleSettleFrames = 0;
        }
        return OW_WILD_BATTLE_DISPOSITION_RETAIN;
    }
    helperEntry = OverworldWildSpawns_GetHelperOverlayEntry();
    if (helperEntry != NULL && helperEntry->finishBattle != NULL) {
        disposition = helperEntry->finishBattle(
            fieldSystem,
            state,
            &OW_WILD_RUNTIME(state)->spawnPresentations,
            &OW_WILD_RUNTIME(state)->despawnTelemetry,
            battleResult,
            OverworldWildSpawns_ResetSlotState);
    }

    if (state->pendingSlot >= 0 && state->pendingSlot < OW_WILD_MAX_SPAWNS) {
        int slot = state->pendingSlot;

        if (disposition == OW_WILD_BATTLE_DISPOSITION_FLED
            || disposition == OW_WILD_BATTLE_DISPOSITION_RETAIN) {
            state->battleGraceSteps = OW_WILD_FLEE_GRACE_STEPS;
            if (disposition == OW_WILD_BATTLE_DISPOSITION_FLED
                && OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
                && OverworldWildSpawns_IsCurrentSpawnObject(fieldSystem, &state->spawns[slot])) {
                state->movementFieldSystem = fieldSystem;
                OverworldWildSpawns_StartTiredEmote(state, slot);
            }
        }
    }

    OverworldWildSpawns_ResetPendingBattle(state);
    state->movementAButtonDown = (PAD_Read() & PAD_BUTTON_A) != 0;

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK && OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    if (fieldSystem != NULL
        && fieldSystem->taskman == NULL
        && OverworldWildSpawns_IsMovementFieldContextCurrent(state, fieldSystem)
        && OverworldWildSpawns_GetCurrentMovementSpawnMask(state, fieldSystem) != 0) {
        OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
    }
#endif
    return disposition;
}

static BOOL OverworldWildSpawns_UpdateMapState(FieldSystem *fieldSystem, OverworldWildSpawnState *state)
{
    MapObjectMan *mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    void *mapObjects = mapObjectMan != NULL ? mapObjectMan->objects : NULL;

#if OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY
    (void)state;
    sOverworldWildDiagnosticMapObjectMan = mapObjectMan;
    sOverworldWildDiagnosticMapObjects = mapObjects;
    return OverworldWildSpawns_IsFieldContextAvailable(fieldSystem);
#endif

#if OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY
    sOverworldWildDiagnosticMapObjectMan = mapObjectMan;
    sOverworldWildDiagnosticMapObjects = mapObjects;
    sOverworldWildDiagnosticStateMapId = state != NULL ? state->mapId : MAP_NOTHING;
    sOverworldWildDiagnosticStateMapObjectMan = state != NULL ? state->mapObjectMan : NULL;
    sOverworldWildDiagnosticStateMapObjects = state != NULL ? state->mapObjects : NULL;
    return OverworldWildSpawns_IsFieldContextAvailable(fieldSystem);
#endif

#if OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY
    (void)state;
    sOverworldWildDiagnosticMapObjectMan = mapObjectMan;
    sOverworldWildDiagnosticMapObjects = mapObjects;
    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    return OverworldWildSpawns_IsFieldContextAvailable(fieldSystem);
#endif

    OverworldWildSpawns_LoadSavedShinies(state, fieldSystem);

    if (!OverworldWildSpawns_IsFieldContextAvailable(fieldSystem)) {
        OverworldWildCustomMovement_SetFieldSystem(NULL);
        OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, FALSE);
#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
        OverworldWildSpawns_ClearContextLite(state);
#endif
        state->mapId = MAP_NOTHING;
        state->mapObjectMan = NULL;
        state->mapObjects = NULL;
        state->presentationRestorePending = FALSE;
        return FALSE;
    }

    if (state->mapId != fieldSystem->location->mapId) {
#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
        OverworldWildSpawns_ClearContextLite(state);
#endif
        OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, FALSE);
#if OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR
        /* The Actor transition already supplied the current generation.
         * Rearming the adapter after DISCARD must not advance it again. */
        state->mapId = fieldSystem->location->mapId;
        state->mapObjectMan = mapObjectMan;
        state->mapObjects = mapObjects;
#else
        OverworldWildSpawns_Clear(state, FALSE);
        state->mapId = fieldSystem->location->mapId;
        state->mapObjectMan = mapObjectMan;
        state->mapObjects = mapObjects;
#endif
    }

    if (state->mapObjectMan != mapObjectMan || state->mapObjects != mapObjects) {
        int i;

        OverworldWildSpawns_DetachAllMovementStateOnContextLoss(state, FALSE);
        state->presentationRestorePending = TRUE;
        for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
            if (state->spawns[i].active) {
                OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask |=
                    OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(i);
                OW_WILD_RUNTIME(state)->spawnPresentations.farSamples[i] = 0;
                state->spawns[i].object = NULL;
            }
        }
        state->mapObjectMan = mapObjectMan;
        state->mapObjects = mapObjects;
    }

    OverworldWildCustomMovement_SetFieldSystem(fieldSystem);
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os"))) OverworldWildSpawns_OverlayOnPlayerStep(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    OverworldWildResidentData *residentData)
{
    MapObjectMan *mapObjectMan;
    u16 currentSpawnMask;
    BOOL resumeOnly = residentData->pendingFlags
        == OW_WILD_FIELD_IDLE_REARM_PENDING;

#if OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY
    (void)fieldSystem;
    (void)state;
    return FALSE;
#endif

    if (OverworldWildSpawns_EnsureRuntimeState(state) == NULL) {
        return FALSE;
    }
    OW_WILD_RUNTIME(state)->residentData = residentData;

    mapObjectMan = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (resumeOnly
        && state->mapId == fieldSystem->location->mapId
        && (state->mapObjectMan != mapObjectMan
            || mapObjectMan == NULL
            || state->mapObjects != mapObjectMan->objects)) {
        residentData->pendingFlags |=
            OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING;
        resumeOnly = FALSE;
        state->battleGraceSteps = OW_WILD_FIELD_READY_DELAY_FRAMES;
    }

    if (!OverworldWildSpawns_UpdateMapState(fieldSystem, state)) {
        if (fieldSystem->mapObjectMan != NULL
            && fieldSystem->playerAvatar != NULL
            && IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)) {
            residentData->pendingFlags = 0;
        }
        return FALSE;
    }
#if OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY
    return FALSE;
#endif

    currentSpawnMask = OverworldWildSpawns_GetCurrentMovementSpawnMask(
        state,
        fieldSystem);
    if (state->presentationRestorePending
        || OW_WILD_RUNTIME(state)->spawnPresentations.managerRestoreMask != 0
        || !sOverworldWildHelperOverlayReady) {
        if (!OverworldWildSpawns_ReconcileSpawnPresentations(state, fieldSystem)) {
            return FALSE;
        }
        currentSpawnMask = OverworldWildSpawns_GetCurrentMovementSpawnMask(
            state,
            fieldSystem);
    }
    if ((resumeOnly
            || (residentData->pendingFlags
                & OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING) != 0)
        && (residentData->pendingFlags
            & OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING) == 0) {
        (void)OverworldWildSpawns_PopulationControl(
            OVERWORLD_ACTOR_POPULATION_CONTROL_REQUEST_MAINTENANCE,
            0);
        goto ensure_movement_task;
    }

#if OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY
    return FALSE;
#endif

    if (OverworldWildSpawns_TryStartCustomJumpRamProbe(state, fieldSystem)) {
        return TRUE;
    }

    if (OverworldWildSpawns_TryStartBattle(state, fieldSystem)) {
        return TRUE;
    }

#if OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY
    return FALSE;
#endif

#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK
#if !OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    OverworldWildSpawns_TickMovementParams(
        state,
        fieldSystem,
        FALSE,
        0
#if OW_WILD_SPAWNER_IMMEDIATE_AI_AFTER_COMMAND_COMPLETION
        , 0
#endif
    );
#endif
    if (OverworldWildSpawns_HasPendingBattle(state)) {
        return TRUE;
    }
#endif

#if !OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY
    OverworldWildSpawns_TryPlayAmbientCry(state);
#endif

    if ((residentData->pendingFlags
            & OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING) != 0) {
        /* The follower cannot become spawn-ready until its release ball
         * advances. FieldReady retries this branch before the normal frame
         * service, so advance that presentation here to avoid a wait loop. */
        (void)OverworldWildSpawns_TickPlayerBallProjectile(
            fieldSystem,
            state);
        if (!OverworldWildSpawns_TryRefill(state, fieldSystem)) {
            /* Every writer publishes FOLLOWER_REFILL together with REARM.
             * Keep the existing request intact for the next field frame. */
            return FALSE;
        }
        currentSpawnMask |=
            OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(OW_WILD_FOLLOWER_SLOT);
        goto ensure_movement_task;
    }
ensure_movement_task:
#if OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK && OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK
    if (OverworldWildSpawns_PopulationControl(
            OVERWORLD_ACTOR_POPULATION_CONTROL_HAS_PENDING_MAINTENANCE,
            0)
        || currentSpawnMask != 0) {
        OverworldWildSpawns_EnsureFrameMovementTask(state, fieldSystem);
        if (sOverworldWildMovementFrameTask == NULL) {
            /* The root monitor will retry the intact queued maintenance. */
            residentData->pendingFlags =
                OW_WILD_FIELD_IDLE_REARM_PENDING;
            return FALSE;
        }
    }
#endif
    residentData->pendingFlags = 0;
    return FALSE;
}

#endif // IMPLEMENT_OVERWORLD_WILD_SPAWNS
