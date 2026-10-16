#include <assert.h>
#include <stdio.h>

#include "player_health_model.h"

static void Step(PlayerHealthState *state, u32 frame, u8 eligible, u8 moving)
{
    PlayerHealthDecision decision = PlayerHealth_BeginFrame(state, frame, eligible);
    if (eligible && !state->recoveryPending) {
        assert(decision == PLAYER_HEALTH_OK);
        assert(PlayerHealth_EndFrame(state, moving) == PLAYER_HEALTH_OK);
    } else {
        assert(decision == (eligible
            ? PLAYER_HEALTH_RECOVERING : PLAYER_HEALTH_PAUSED));
    }
}

static void TestDamageAndProtection(void)
{
    PlayerHealthState state;
    u32 frame;

    PlayerHealth_Init(&state, 100);
    assert(PlayerHealth_BeginFrame(&state, 1, 1) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_TryHit(&state, 0) == PLAYER_HEALTH_INVALID);
    assert(PlayerHealth_TryHit(&state, 51) == PLAYER_HEALTH_INVALID);
    assert(state.hp == 100 && state.acceptedHits == 0);
    assert(PlayerHealth_TryHit(&state, 33) == PLAYER_HEALTH_OK);
    assert(state.hp == 67 && state.protectionFrames == 60
        && state.lastDamage == 33);
    assert(PlayerHealth_TryHit(&state, 20)
        == PLAYER_HEALTH_PROTECTED);
    assert(state.hp == 67 && state.acceptedHits == 1);
    assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);

    for (frame = 2; frame < 61; frame++) {
        assert(PlayerHealth_BeginFrame(&state, frame, 1) == PLAYER_HEALTH_OK);
        assert(PlayerHealth_TryHit(&state, 20)
            == PLAYER_HEALTH_PROTECTED);
        assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);
    }
    assert(PlayerHealth_BeginFrame(&state, 61, 1) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_TryHit(&state, 20) == PLAYER_HEALTH_OK);
    assert(state.hp == 47 && state.acceptedHits == 2
        && state.lastDamage == 20);
    assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_InjuryBand(&state) == 2);
}

static void TestProfileContactAuthority(void)
{
    /* Motion names never grant damage. The resolved profile and measured
     * speed decide, for either a Walk or a flying collision body. */
    assert(!PlayerHealth_ContactCanDamage(0, 0, 33, 256));
    assert(!PlayerHealth_ContactCanDamage(2, 0, 33, 256));
    assert(!PlayerHealth_ContactCanDamage(1, 0, 0, 256));
    assert(!PlayerHealth_ContactCanDamage(1, 0, 51, 256));
    assert(!PlayerHealth_ContactCanDamage(1, 32, 33, 31));
    assert(PlayerHealth_ContactCanDamage(1, 32, 33, 32));
    assert(PlayerHealth_ContactCanDamage(1, 0, 20, 0));
}

static void TestRestAndPause(void)
{
    PlayerHealthState state;
    u32 frame;

    PlayerHealth_Init(&state, 1);
    for (frame = 1; frame <= 300; frame++) {
        Step(&state, frame, 1, 0);
    }
    assert(state.hp == 1 && state.restFrames == 300);
    for (frame = 301; frame <= 360; frame++) {
        Step(&state, frame, 1, 0);
    }
    assert(state.hp == 11);
    for (frame = 361; frame <= 400; frame++) {
        Step(&state, frame, 0, 0);
    }
    assert(state.hp == 11 && state.restFrames == 300);
    for (frame = 401; frame <= 460; frame++) {
        Step(&state, frame, 1, 0);
    }
    assert(state.hp == 21);
    Step(&state, 461, 1, 1);
    assert(state.hp == 21 && state.restFrames == 300
        && state.healRemainder == 10);
    for (frame = 462; frame <= 466; frame++) {
        Step(&state, frame, 1, 1);
    }
    assert(state.hp == 22 && state.healRemainder == 0);
    Step(&state, 467, 0, 1);
    assert(state.hp == 22 && state.restFrames == 300
        && state.healRemainder == 0);

    /* A real hit restarts the delay, even when movement continues. */
    assert(PlayerHealth_BeginFrame(&state, 468, 1) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_TryHit(&state, 10) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_EndFrame(&state, 1) == PLAYER_HEALTH_OK);
    assert(state.hp == 12 && state.restFrames == 0
        && state.healRemainder == 0);
    for (frame = 469; frame <= 768; frame++) {
        Step(&state, frame, 1, 1);
    }
    assert(state.hp == 12 && state.restFrames == 300
        && state.healRemainder == 0);

    /* A canceled or menu frame cannot contribute a healing tick. */
    assert(PlayerHealth_BeginFrame(&state, 769, 1) == PLAYER_HEALTH_OK);
    PlayerHealth_AbortFrame(&state);
    Step(&state, 770, 0, 1);
    assert(state.hp == 12 && state.restFrames == 300
        && state.healRemainder == 0);
    Step(&state, 771, 1, 1);
    assert(state.hp == 12 && state.healRemainder == 10);
    for (frame = 772; frame <= 776; frame++) {
        Step(&state, frame, 1, 1);
    }
    assert(state.hp == 13 && state.healRemainder == 0);
}

static void TestMaximumDamage(void)
{
    PlayerHealthState state;

    PlayerHealth_Init(&state, 50);
    assert(state.lastDamage == 0);
    assert(PlayerHealth_BeginFrame(&state, 1, 1) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_TryHit(&state, PLAYER_HEALTH_DAMAGE_CAP)
        == PLAYER_HEALTH_OK);
    assert(state.hp == 0 && state.lastDamage == PLAYER_HEALTH_DAMAGE_CAP
        && state.recoveryPending);
    assert(PlayerHealth_EndFrame(&state, 1) == PLAYER_HEALTH_RECOVERING);
    assert(state.hp == 0 && state.restFrames == 0);
}

static void TestZeroAndRecovery(void)
{
    PlayerHealthState state;
    u32 frame;

    PlayerHealth_Init(&state, 0);
    assert(state.recoveryPending);
    assert(PlayerHealth_BeginFrame(&state, 1, 1) == PLAYER_HEALTH_RECOVERING);
    assert(PlayerHealth_TryHit(&state, 33)
        == PLAYER_HEALTH_RECOVERING);
    PlayerHealth_Restore(&state);
    assert(state.hp == 100 && !state.recoveryPending);
    for (frame = 2; frame <= 182; frame++) {
        if (frame % 60 == 2) {
            assert(PlayerHealth_BeginFrame(&state, frame, 1) == PLAYER_HEALTH_OK);
            assert(PlayerHealth_TryHit(&state, 33)
                == PLAYER_HEALTH_OK);
            if (state.recoveryPending) {
                assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_RECOVERING);
            } else {
                assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);
            }
        } else if (!state.recoveryPending) {
            Step(&state, frame, 1, 0);
        }
    }
    assert(state.hp == 0 && state.recoveryPending);
    assert(PlayerHealth_BeginFrame(&state, 183, 1) == PLAYER_HEALTH_RECOVERING);
}

static void TestFullRecoveryTime(void)
{
    PlayerHealthState state;
    u32 frame;

    PlayerHealth_Init(&state, 1);
    for (frame = 1; frame < 894; frame++) {
        Step(&state, frame, 1, 1);
    }
    assert(state.hp == 99);
    Step(&state, 894, 1, 1);
    assert(state.hp == 100 && state.healRemainder == 0);
    assert(PlayerHealth_InjuryBand(&state) == 0);
    for (frame = 895; frame <= 900; frame++) {
        Step(&state, frame, 1, 1);
    }
    assert(state.hp == 100 && state.healRemainder == 0);
}

static void TestFrameIdentity(void)
{
    PlayerHealthState state;

    PlayerHealth_Init(&state, 80);
    assert(PlayerHealth_BeginFrame(&state, 8, 1) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_BeginFrame(&state, 8, 1) == PLAYER_HEALTH_DUPLICATE_FRAME);
    assert(PlayerHealth_BeginFrame(&state, 7, 1) == PLAYER_HEALTH_STALE_FRAME);
    assert(PlayerHealth_BeginFrame(&state, 9, 0) == PLAYER_HEALTH_PAUSED);
    assert(PlayerHealth_TryHit(&state, 20)
        == PLAYER_HEALTH_PAUSED);
    assert(state.hp == 80);

    assert(PlayerHealth_BeginFrame(&state, 10, 1) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_TryHit(&state, 33) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);
    assert(PlayerHealth_BeginFrame(&state, 11, 1) == PLAYER_HEALTH_OK);
    assert(state.protectionFrames == 59);
    PlayerHealth_AbortFrame(&state);
    assert(state.protectionFrames == 60);
    assert(PlayerHealth_BeginFrame(&state, 12, 1) == PLAYER_HEALTH_OK);
    assert(state.protectionFrames == 59);
    assert(PlayerHealth_EndFrame(&state, 0) == PLAYER_HEALTH_OK);
}

int main(void)
{
    TestProfileContactAuthority();
    TestDamageAndProtection();
    TestRestAndPause();
    TestMaximumDamage();
    TestZeroAndRecovery();
    TestFullRecoveryTime();
    TestFrameIdentity();
    puts("player health model: pass");
    return 0;
}
