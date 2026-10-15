#ifndef PLAYER_HEALTH_H
#define PLAYER_HEALTH_H

#include "player_health_model.h"
#include "wild_movement_value.h"

typedef struct FieldSystem FieldSystem;
struct FIELD_PLAYER_AVATAR;

#define PLAYER_HEALTH_OVERLAY_ENTRY_ADDR 0x01FFA580
#define PLAYER_HEALTH_STOCK_COLLISION_ENTRY_ADDR 0x01FFC160
#define PLAYER_HEALTH_BLOCKED_STEP_ENTRY_ADDR 0x01FFC168
#define PLAYER_HEALTH_KNOCKBACK_CONTROL_ENTRY_ADDR 0x01FFC170
#define PLAYER_HEALTH_OVERLAY_MAGIC 0x484C5048
#define PLAYER_HEALTH_OVERLAY_VERSION 2

/* The field service opens a frame before wild movement tasks run. */
void PlayerHealthField_Begin(FieldSystem *fieldSystem);
void PlayerHealthField_Stop(FieldSystem *fieldSystem);

/* All wild contact uses the resolved profile's attack switch and speed gate. */
PlayerHealthDecision PlayerHealthField_TryContact(
    FieldSystem *fieldSystem, u8 attacking, u8 minImpactSpeed,
    u8 collisionDamage, u16 impactSpeed, u8 knockbackOptions,
    u8 knockbackDirection);

/* The player-control boundary gives the one knockback controller ownership. */
u8 PlayerHealthField_OverrideControl(struct FIELD_PLAYER_AVATAR *avatar,
    s32 *direction, u32 *newKeys, u32 *heldKeys);
#define PlayerHealthField_OverrideControlEntry \
    ((u8 (*)(struct FIELD_PLAYER_AVATAR *, s32 *, u32 *, u32 *)) \
        (PLAYER_HEALTH_KNOCKBACK_CONTROL_ENTRY_ADDR | 1))

/* Healing and presentation use the resident state, independent of map actors. */
const PlayerHealthState *PlayerHealthField_GetState(void);
void PlayerHealthField_Restore(FieldSystem *fieldSystem);
u8 PlayerHealthField_RecoveryPending(FieldSystem *fieldSystem);

typedef enum PlayerHealthContactEventKind {
    PLAYER_HEALTH_THROW_LAUNCH = 1,
    PLAYER_HEALTH_MOTION_STEP = 2,
    PLAYER_HEALTH_MOTION_LAND = 3,
    PLAYER_HEALTH_MOTION_CANCEL = 4,
    PLAYER_HEALTH_CONTACT_SUPPRESS_BATTLE = 5,
    PLAYER_HEALTH_CONTACT_PROFILE = 6,
    PLAYER_HEALTH_CONTACT_BLOCKED_ATTACK = 7,
} PlayerHealthContactEventKind;

#define PLAYER_HEALTH_EVENT_CODE(slot, kind) \
    (((u32)(slot) << 8) | (u32)(kind))

BOOL PlayerHealthContact_HandleEvent(
    const void *wildState, u32 code, const void *sample, u32 aux);
void PlayerHealthContact_ResetAll(void);
void PlayerHealthContact_BeginFrame(const OverworldWildSpawnState *state);
void PlayerHealthContact_EndFrame(const OverworldWildSpawnState *state);
BOOL PlayerHealthField_ContactsEnabled(FieldSystem *fieldSystem);
void PlayerHealthField_QueueKnockback(FieldSystem *fieldSystem, u8 options, u8 direction);
/* Called only after a real player Walk proposal was rejected by collision. */
void PlayerHealthContact_ReportBlockedStep(
    struct FIELD_PLAYER_AVATAR *avatar, u8 direction);

#define PlayerHealthContact_ReportBlockedStepEntry \
    ((void (*)(struct FIELD_PLAYER_AVATAR *, u8)) \
        (PLAYER_HEALTH_BLOCKED_STEP_ENTRY_ADDR | 1))

typedef struct PlayerHealthOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    void (*begin)(FieldSystem *fieldSystem);
    PlayerHealthDecision (*tryContact)(FieldSystem *fieldSystem,
        u8 attacking, u8 minImpactSpeed,
        u8 collisionDamage, u16 impactSpeed, u8 knockbackOptions,
        u8 knockbackDirection);
    const PlayerHealthState *(*getState)(void);
    void (*restore)(FieldSystem *fieldSystem);
    u8 (*recoveryPending)(FieldSystem *fieldSystem);
    void (*stop)(FieldSystem *fieldSystem);
    BOOL (*contactEvent)(const void *wildState, u32 code,
        const void *sample, u32 aux);
    void (*sessionReset)(void);
    BOOL (*wildCircleTarget)(WildMovementCircleQuery *query);
    void (*wildFleeDirections)(u8 *directions, int *directionCount,
        int fleeDx, int fleeDy);
    u16 (*wildThrowUnstableMask)(OverworldWildSpawnState *state,
        const u8 *motionModes);
} PlayerHealthOverlayEntry;

#define PLAYER_HEALTH_OVERLAY_ENTRY \
    ((const PlayerHealthOverlayEntry *)PLAYER_HEALTH_OVERLAY_ENTRY_ADDR)

static inline u8 PlayerHealthOverlay_IsReady(void)
{
    const PlayerHealthOverlayEntry *entry = PLAYER_HEALTH_OVERLAY_ENTRY;

    return entry->magic == PLAYER_HEALTH_OVERLAY_MAGIC
        && entry->version == PLAYER_HEALTH_OVERLAY_VERSION
        && entry->size == sizeof(*entry);
}

#endif
