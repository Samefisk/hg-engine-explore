#ifndef PLAYER_HEALTH_PRESENTATION_H
#define PLAYER_HEALTH_PRESENTATION_H

#include "player_health.h"

/* Resident warning source: live Ram alert or held Throw/airborne flight. */
BOOL PlayerHealthContact_Danger(FieldSystem *fieldSystem);

/* The field service calls Update after HP settles, before field OAM is applied. */
void PlayerHealthPresentation_Update(FieldSystem *fieldSystem,
    const PlayerHealthState *health, BOOL danger);
void PlayerHealthPresentation_End(FieldSystem *fieldSystem);

/* A draw receipt is set only after the field OAM manager accepts the bar. */
typedef struct PlayerHealthPresentationReceipt {
    u8 requestedFill;
    u8 drawnFill;
    u8 danger;
    u8 submittedSprites;
} PlayerHealthPresentationReceipt;

const PlayerHealthPresentationReceipt *PlayerHealthPresentation_GetReceipt(void);

#endif
