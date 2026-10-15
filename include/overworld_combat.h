#ifndef OVERWORLD_COMBAT_H
#define OVERWORLD_COMBAT_H

#include "overworld_wild_spawns_internal.h"
#include "overworld_motion_model.h"
struct BattleSystem;
struct BattleStruct;

/* Resident hit service. Actor identity is validated on every call. */
#define OVERWORLD_COMBAT_ENTRY_ADDR 0x01FFD580
#define OVERWORLD_COMBAT_MAGIC 0x434F4D42
#define OVERWORLD_COMBAT_VERSION 1
#define OVERWORLD_COMBAT_NONE 0
#define OVERWORLD_COMBAT_KNOCKBACK 1
#define OVERWORLD_COMBAT_FAINTED 2
#define OVERWORLD_COMBAT_CRASH_SETTLE 3
#define OVERWORLD_COMBAT_CRASH_PLAYING 4
#define OVERWORLD_COMBAT_MOUNT_FAINTED 1
#define OVERWORLD_COMBAT_MOUNT_KNOCKBACK_PENDING 2
#define OVERWORLD_COMBAT_MOUNT_CRASH_SETTLE 4
#define OVERWORLD_COMBAT_MOUNT_CRASH_PLAYING 8
#define OVERWORLD_COMBAT_PENDING_KNOCKBACK 1
#define OVERWORLD_COMBAT_PENDING_SETTLE 2
#define OVERWORLD_COMBAT_PENDING_CRASH 4
#define OVERWORLD_COMBAT_PENDING_MOUNTED 8
#define OVERWORLD_COMBAT_PENDING_CRASH_MASK 6
/* prepare's slot modifier requests only already-latched urgent work. Normal
 * NULL-plan callers retain their native HP/faint eligibility check. */
#define OVERWORLD_COMBAT_PROBE_URGENT 0x80

typedef struct OverworldCombatEntry {
    u32 magic;
    u16 version, size;
    BOOL (*readHp)(const OverworldWildSpawnState *, u8, u16 *, u16 *);
    int (*hpIV)(u32 personality);
    u8 (*prepare)(const OverworldWildSpawnState *, u8, OverworldMotionPlan *);
    void (*acknowledge)(const OverworldWildSpawnState *, u8);
    BOOL (*plan)(FieldSystem *, LocalMapObject *, u8, u8, OverworldMotionPlan *);
    BOOL (*mountedPending)(FieldSystem *);
    u16 (*battleHp)(u32 personality);
    void (*battleSync)(struct BattleSystem *, struct BattleStruct *, u8, u16);
    void (*battleUpdate)(struct BattleSystem *, struct BattleStruct *, u8, u32);
    u8 (*mountStatus)(const OverworldWildSpawnState *);
    void (*captureHp)(const OverworldWildSpawnState *, u8, struct PartyPokemon *);
} OverworldCombatEntry;

#define OVERWORLD_COMBAT_ENTRY ((const OverworldCombatEntry *)OVERWORLD_COMBAT_ENTRY_ADDR)
static inline BOOL OverworldCombat_IsReady(void)
{
    return OVERWORLD_COMBAT_ENTRY->magic == OVERWORLD_COMBAT_MAGIC
        && OVERWORLD_COMBAT_ENTRY->version == OVERWORLD_COMBAT_VERSION
        && OVERWORLD_COMBAT_ENTRY->size == sizeof(OverworldCombatEntry);
}

/* Internal to the resident health overlay. */
BOOL OverworldCombat_ReadHp(const OverworldWildSpawnState *, u8, u16 *, u16 *);
int OverworldCombat_HpIV(u32 personality);
BOOL OverworldCombat_TryHit(const OverworldWildSpawnState *, u8, u8, u8, u8);
void OverworldCombat_AcceptedHit(const OverworldWildSpawnState *, u8);
BOOL OverworldCombat_MountedCrashPending(FieldSystem *);
void OverworldCombat_BeginFrame(const OverworldWildSpawnState *);
void OverworldCombat_Reset(void);
u8 OverworldCombat_Prepare(const OverworldWildSpawnState *, u8, OverworldMotionPlan *);
void OverworldCombat_Acknowledge(const OverworldWildSpawnState *, u8);
BOOL OverworldCombat_Plan(FieldSystem *, LocalMapObject *, u8, u8, OverworldMotionPlan *);
BOOL OverworldCombat_MountedPending(FieldSystem *);
u16 OverworldCombat_BattleHp(u32 personality);
void OverworldCombat_BattleSync(struct BattleSystem *, struct BattleStruct *, u8, u16);
void OverworldCombat_BattleUpdate(struct BattleSystem *, struct BattleStruct *, u8, u32);
void OverworldCombat_CaptureHp(const OverworldWildSpawnState *, u8, struct PartyPokemon *);
u8 OverworldCombat_MountStatus(const OverworldWildSpawnState *);

#endif
