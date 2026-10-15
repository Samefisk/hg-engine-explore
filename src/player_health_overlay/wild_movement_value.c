#include "../../include/wild_movement_value.h"
#include "../../include/overworld_wild_behavior_data.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/sound.h"
#include "../../include/constants/sndseq.h"

/* The stock effect initializer plays the menu-confirm sound synchronously.
 * Keep its visual effect, then cancel that sequence before the sound update. */
void __attribute__((noinline, used, section(".overworld_wild_quiet_bubble")))
OverworldWildBubble_ShowQuiet(LocalMapObject *object, u8 bubbleId)
{
    ov01_02203A48(object, bubbleId);
    StopSE(SEQ_SE_DP_DECIDE);
}

typedef struct WildMovementRuntimePrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} WildMovementRuntimePrefix;

static int WildMovementValue_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int WildMovementValue_Max(int left, int right)
{
    return left > right ? left : right;
}

BOOL WildMovementValue_SelectCircleTarget(WildMovementCircleQuery *query)
{
    int selectedX[2] = {0, 0};
    int selectedY[2] = {0, 0};
    int selectedScore[2] = {0x7FFF, 0x7FFF};
    int selectedCount[2] = {0, 0};
    int dx;
    int dy;
    u16 allowedTile;
    u8 radius;
    BOOL currentIsTarget;
    BOOL continueWhenArrived;
    BOOL avoidPreviousTile;

    if (query == NULL || query->state == NULL || query->fieldSystem == NULL
        || query->lane == NULL || query->tileAllowed == NULL
        || query->slot < 0 || query->slot >= OW_WILD_MAX_SPAWNS) {
        return FALSE;
    }

    allowedTile = query->lane->chillAllowedTerrainMask;
    radius = query->lane->circleRadius;
    currentIsTarget = WildMovementValue_Max(
            WildMovementValue_Abs(query->objectX - query->playerX),
            WildMovementValue_Abs(query->objectY - query->playerY)) == radius;
    continueWhenArrived = OW_WILD_BEHAVIOR_CONTINUES_WHEN_ARRIVED(
        query->lane->continueWhenArrived);
    avoidPreviousTile = OW_WILD_BEHAVIOR_AVOIDS_PREVIOUS_TILE(query->lane->avoidPreviousTile);
    if (currentIsTarget && !continueWhenArrived) {
        query->targetX = query->objectX;
        query->targetY = query->objectY;
        return TRUE;
    }

    for (dy = -(int)radius; dy <= (int)radius; dy++) {
        int dxStep = (dy == -(int)radius || dy == (int)radius)
            ? 1 : 2 * (int)radius;

        for (dx = -(int)radius; dx <= (int)radius; dx += dxStep) {
            int candidateX = query->playerX + dx;
            int candidateY = query->playerY + dy;
            int score;
            BOOL isPreviousTile;
            int selection;

            if (candidateX == query->objectX
                && candidateY == query->objectY) {
                continue;
            }
            if (!query->tileAllowed(query->fieldSystem, allowedTile,
                    candidateX, candidateY)) {
                continue;
            }

            score = WildMovementValue_Max(
                WildMovementValue_Abs(candidateX - query->objectX),
                WildMovementValue_Abs(candidateY - query->objectY));
            isPreviousTile = avoidPreviousTile
                && query->state->movementPreviousTileLocked[query->slot]
                && query->state->movementPreviousTileX[query->slot] == candidateX
                && query->state->movementPreviousTileY[query->slot] == candidateY;
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
        query->targetX = selectedX[0];
        query->targetY = selectedY[0];
        return TRUE;
    }
    if (selectedCount[1] != 0) {
        query->targetX = selectedX[1];
        query->targetY = selectedY[1];
        return TRUE;
    }
    if (currentIsTarget) {
        query->targetX = query->objectX;
        query->targetY = query->objectY;
        return TRUE;
    }
    return FALSE;
}

void WildMovementValue_AppendFleeDirections(
    u8 *directions, int *directionCount, int fleeDx, int fleeDy)
{
    static const u8 baseDirections[4] = {0, 3, 1, 2};
    int start;

    if (directions == NULL || directionCount == NULL || *directionCount >= 4
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

            score = (direction == 3 ? fleeDx : direction == 2 ? -fleeDx
                : direction == 1 ? fleeDy : -fleeDy);
            if (bestDirection < 0 || score > bestScore) {
                bestDirection = direction;
                bestScore = score;
            }
        }
        directions[*directionCount] = (u8)bestDirection;
        (*directionCount)++;
    }
}

u16 WildMovementValue_GetThrowUnstableMask(
    OverworldWildSpawnState *state, const u8 *motionModes)
{
    const WildMovementRuntimePrefix *runtime;
    u16 unstableMask = 0;
    int i;

    if (state == NULL || state->movementRuntimeState == NULL
        || motionModes == NULL) {
        return 0;
    }
    runtime = (const WildMovementRuntimePrefix *)state->movementRuntimeState;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        if (runtime->movementEmotePartnerPrepObjects[i] != NULL
            || runtime->movementCustomJumpActive[i]
            || runtime->movementCustomJumpPrepActive[i]
            || motionModes[i] >= 3
            || state->movementCrashShakeTimers[i] != 0) {
            unstableMask |= 1u << i;
        }
    }
    return unstableMask;
}
