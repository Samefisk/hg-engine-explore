#ifndef PLAYER_HEALTH_RECOVERY_H
#define PLAYER_HEALTH_RECOVERY_H

#include "types.h"

typedef struct FieldSystem FieldSystem;

/* The field task calls this after a Center or home rest script marks completion. */
void PlayerHealthRecovery_ServiceHealing(FieldSystem *fieldSystem);

/* Queue one player-HP blackout when the field can accept a new task. */
BOOL PlayerHealthRecovery_BeginBlackout(FieldSystem *fieldSystem);

/* Drop an abandoned blackout owner when a new/Continue game replaces the save. */
void PlayerHealthRecovery_SessionReset(void);

#endif
