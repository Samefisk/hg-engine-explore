#include "player_health_model.h"

#if defined(PLAYER_HEALTH_HOST) || defined(OVERWORLD_BEHAVIOR_HOST)
#define PLAYER_HEALTH_TAIL_SECTION
#else
#define PLAYER_HEALTH_TAIL_SECTION __attribute__((section(".player_health_tail_end")))
#endif

void PlayerHealth_Init(PlayerHealthState *state, u8 savedHp)
{
    if (state == 0) {
        return;
    }
    state->lastFrame = 0;
    state->acceptedHits = 0;
    state->restFrames = 0;
    state->protectionFrames = 0;
    state->healRemainder = 0;
    state->hp = savedHp <= PLAYER_HEALTH_MAX_HP
        ? savedHp : PLAYER_HEALTH_MAX_HP;
    state->frameActive = 0;
    state->hitThisFrame = 0;
    state->protectionAdvancedThisFrame = 0;
    state->recoveryPending = state->hp == 0;
    state->lastDamage = 0;
}

PlayerHealthDecision PlayerHealth_BeginFrame(
    PlayerHealthState *state, u32 frame, u8 fieldEligible)
{
    if (state == 0 || frame == 0 || state->frameActive) {
        return PLAYER_HEALTH_INVALID;
    }
    if (state->lastFrame != 0) {
        s32 distance = (s32)(frame - state->lastFrame);
        if (distance == 0) {
            return PLAYER_HEALTH_DUPLICATE_FRAME;
        }
        if (distance < 0) {
            return PLAYER_HEALTH_STALE_FRAME;
        }
    }
    state->lastFrame = frame;
    state->hitThisFrame = 0;
    state->protectionAdvancedThisFrame = 0;
    if (!fieldEligible) {
        return PLAYER_HEALTH_PAUSED;
    }
    if (state->recoveryPending) {
        return PLAYER_HEALTH_RECOVERING;
    }
    if (state->protectionFrames != 0) {
        state->protectionFrames--;
        state->protectionAdvancedThisFrame = 1;
    }
    state->frameActive = 1;
    return PLAYER_HEALTH_OK;
}

PlayerHealthDecision PlayerHealth_TryHit(
    PlayerHealthState *state, u8 damage)
{
    if (state == 0 || damage == 0 || damage > PLAYER_HEALTH_DAMAGE_CAP) {
        return PLAYER_HEALTH_INVALID;
    }
    if (state->recoveryPending) {
        return PLAYER_HEALTH_RECOVERING;
    }
    if (!state->frameActive) {
        return PLAYER_HEALTH_PAUSED;
    }
    if (state->protectionFrames != 0 || state->hitThisFrame) {
        return PLAYER_HEALTH_PROTECTED;
    }
    state->hp = state->hp > damage ? state->hp - damage : 0;
    state->protectionFrames = PLAYER_HEALTH_PROTECTION_FRAMES;
    state->restFrames = 0;
    state->healRemainder = 0;
    state->hitThisFrame = 1;
    state->lastDamage = damage;
    state->acceptedHits++;
    state->recoveryPending = state->hp == 0;
    return PLAYER_HEALTH_OK;
}

u8 PLAYER_HEALTH_TAIL_SECTION PlayerHealth_ContactCanDamage(
    u8 attacking, u8 minImpactSpeed,
    u8 collisionDamage, u16 impactSpeed)
{
    return attacking == 1
        && collisionDamage != 0
        && collisionDamage <= PLAYER_HEALTH_DAMAGE_CAP
        && impactSpeed >= minImpactSpeed;
}

PlayerHealthDecision PlayerHealth_EndFrame(
    PlayerHealthState *state, u8 playerMoving)
{
    (void)playerMoving;
    if (state == 0 || !state->frameActive) {
        return PLAYER_HEALTH_INVALID;
    }
    state->frameActive = 0;
    state->protectionAdvancedThisFrame = 0;
    if (state->recoveryPending) {
        return PLAYER_HEALTH_RECOVERING;
    }
    if (state->hitThisFrame) {
        state->restFrames = 0;
        state->healRemainder = 0;
        return PLAYER_HEALTH_OK;
    }
    if (state->hp == PLAYER_HEALTH_MAX_HP) {
        return PLAYER_HEALTH_OK;
    }
    if (state->restFrames < PLAYER_HEALTH_REST_FRAMES) {
        state->restFrames++;
        return PLAYER_HEALTH_OK;
    }
    state->healRemainder += PLAYER_HEALTH_HEAL_PER_SECOND;
    if (state->healRemainder >= PLAYER_HEALTH_FIELD_FRAMES_PER_SECOND) {
        state->healRemainder -= PLAYER_HEALTH_FIELD_FRAMES_PER_SECOND;
        state->hp++;
        if (state->hp >= PLAYER_HEALTH_MAX_HP) {
            state->hp = PLAYER_HEALTH_MAX_HP;
            state->healRemainder = 0;
        }
    }
    return PLAYER_HEALTH_OK;
}

void PlayerHealth_AbortFrame(PlayerHealthState *state)
{
    if (state == 0) {
        return;
    }
    if (state->frameActive && state->protectionAdvancedThisFrame
        && !state->hitThisFrame) {
        state->protectionFrames++;
    }
    state->frameActive = 0;
    state->hitThisFrame = 0;
    state->protectionAdvancedThisFrame = 0;
}

#ifndef PLAYER_HEALTH_HOST
__attribute__((section(".player_health_extended_text")))
#endif
void
PlayerHealth_Restore(PlayerHealthState *state)
{
    if (state == 0) {
        return;
    }
    state->hp = PLAYER_HEALTH_MAX_HP;
    state->restFrames = 0;
    state->protectionFrames = 0;
    state->healRemainder = 0;
    state->frameActive = 0;
    state->hitThisFrame = 0;
    state->protectionAdvancedThisFrame = 0;
    state->recoveryPending = 0;
}

#if defined(PLAYER_HEALTH_HOST) || defined(OVERWORLD_BEHAVIOR_HOST)
/* This display helper has no ROM caller. Keep it for the model's host checks. */
u8 PlayerHealth_InjuryBand(const PlayerHealthState *state)
{
    if (state == 0 || state->hp == PLAYER_HEALTH_MAX_HP) {
        return 0;
    }
    if (state->hp >= 67) {
        return 1;
    }
    if (state->hp >= 34) {
        return 2;
    }
    return 3;
}
#endif
