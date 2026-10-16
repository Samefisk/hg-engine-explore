#ifndef PLAYER_HEALTH_MODEL_H
#define PLAYER_HEALTH_MODEL_H

#ifdef PLAYER_HEALTH_HOST
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
#else
#include "types.h"
#endif

#define PLAYER_HEALTH_MAX_HP 100
#define PLAYER_HEALTH_DAMAGE_CAP 50
#define PLAYER_HEALTH_FIELD_FRAMES_PER_SECOND 60
#define PLAYER_HEALTH_REST_FRAMES (5 * PLAYER_HEALTH_FIELD_FRAMES_PER_SECOND)
#define PLAYER_HEALTH_PROTECTION_FRAMES PLAYER_HEALTH_FIELD_FRAMES_PER_SECOND
#define PLAYER_HEALTH_HEAL_PER_SECOND 10

typedef enum PlayerHealthDecision {
    PLAYER_HEALTH_OK = 0,
    PLAYER_HEALTH_INVALID,
    PLAYER_HEALTH_STALE_FRAME,
    PLAYER_HEALTH_DUPLICATE_FRAME,
    PLAYER_HEALTH_PAUSED,
    PLAYER_HEALTH_PROTECTED,
    PLAYER_HEALTH_RECOVERING,
} PlayerHealthDecision;

typedef struct PlayerHealthState {
    u32 lastFrame;
    u32 acceptedHits;
    u16 restFrames;
    u16 protectionFrames;
    u16 healRemainder;
    u8 hp;
    u8 frameActive;
    u8 hitThisFrame;
    u8 protectionAdvancedThisFrame;
    u8 recoveryPending;
    u8 lastDamage;
} PlayerHealthState;

/* Save only hp, not transient clocks or field-frame identity. */
void PlayerHealth_Init(PlayerHealthState *state, u8 savedHp);
PlayerHealthDecision PlayerHealth_BeginFrame(
    PlayerHealthState *state, u32 frame, u8 fieldEligible);
PlayerHealthDecision PlayerHealth_TryHit(
    PlayerHealthState *state, u8 damage);
u8 PlayerHealth_ContactCanDamage(u8 attacking, u8 minImpactSpeed,
    u8 collisionDamage, u16 impactSpeed);
/* Movement does not stop healing. Keep playerMoving for the native ABI. */
PlayerHealthDecision PlayerHealth_EndFrame(
    PlayerHealthState *state, u8 playerMoving);
void PlayerHealth_AbortFrame(PlayerHealthState *state);
void PlayerHealth_Restore(PlayerHealthState *state);
u8 PlayerHealth_InjuryBand(const PlayerHealthState *state);

#endif
