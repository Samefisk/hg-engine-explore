#include "../../include/overworld_wild_helper.h"

static int OverworldWildHelper_Abs(int value)
{
    return value < 0 ? -value : value;
}

static int OverworldWildHelper_Max(int lhs, int rhs)
{
    return lhs > rhs ? lhs : rhs;
}

static int OverworldWildHelper_DirectionDeltaX(u8 direction)
{
    switch (direction) {
    case OW_WILD_HELPER_DIRECTION_LEFT:
        return -1;
    case OW_WILD_HELPER_DIRECTION_RIGHT:
        return 1;
    default:
        return 0;
    }
}

static int OverworldWildHelper_DirectionDeltaY(u8 direction)
{
    switch (direction) {
    case OW_WILD_HELPER_DIRECTION_UP:
        return -1;
    case OW_WILD_HELPER_DIRECTION_DOWN:
        return 1;
    default:
        return 0;
    }
}

static int OverworldWildHelper_BuildDirections(int dx, int dy, u8 *directions)
{
    int count = 0;

    if (directions == NULL || (dx == 0 && dy == 0)) {
        return 0;
    }

    if (OverworldWildHelper_Abs(dx) >= OverworldWildHelper_Abs(dy)) {
        if (dx > 0) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_RIGHT;
        }
        if (dx < 0 && count < 4) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_LEFT;
        }
        if (dy > 0 && count < 4) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_DOWN;
        }
        if (dy < 0 && count < 4) {
            directions[count++] = OW_WILD_HELPER_DIRECTION_UP;
        }
        return count;
    }

    if (dy > 0) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_DOWN;
    }
    if (dy < 0 && count < 4) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_UP;
    }
    if (dx > 0 && count < 4) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_RIGHT;
    }
    if (dx < 0 && count < 4) {
        directions[count++] = OW_WILD_HELPER_DIRECTION_LEFT;
    }

    return count;
}

static BOOL OverworldWildHelper_IsHopVectorShape(
    const OverworldWildHelperHopConfig *config,
    int dx,
    int dy)
{
    int absDx = OverworldWildHelper_Abs(dx);
    int absDy = OverworldWildHelper_Abs(dy);

    if (absDx == 0 && absDy == 0) {
        return FALSE;
    }
    if (absDx == 0 || absDy == 0) {
        return TRUE;
    }
    return config != NULL
        && config->allowNonCardinal
        && absDx == absDy;
}

static BOOL OverworldWildHelper_TryGetHopVector(
    const OverworldWildHelperHopConfig *config,
    int dx,
    int dy,
    u8 *direction,
    u8 *distance)
{
    int jumpDistance;
    u8 directions[4];

    if (config == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance
        || !OverworldWildHelper_IsHopVectorShape(config, dx, dy)
        || OverworldWildHelper_BuildDirections(dx, dy, directions) == 0) {
        return FALSE;
    }

    jumpDistance = OverworldWildHelper_Max(
        OverworldWildHelper_Abs(dx),
        OverworldWildHelper_Abs(dy));
    if (jumpDistance < config->minDistance || jumpDistance > config->maxDistance) {
        return FALSE;
    }

    if (direction != NULL) {
        *direction = directions[0];
    }
    if (distance != NULL) {
        *distance = (u8)jumpDistance;
    }
    return TRUE;
}

static BOOL OverworldWildHelper_IsLandingAllowed(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    int landingX,
    int landingY)
{
    return config != NULL
        && validator != NULL
        && validator(
            landingX,
            landingY,
            config->targetX,
            config->targetY,
            context);
}

static BOOL OverworldWildHelper_SetHopResult(
    const OverworldWildHelperHopConfig *config,
    int landingX,
    int landingY,
    int finalTargetX,
    int finalTargetY,
    u8 flags,
    OverworldWildHelperHopResult *result)
{
    u8 direction;
    u8 distance;

    if (config == NULL
        || result == NULL
        || !OverworldWildHelper_TryGetHopVector(
            config,
            landingX - config->objectX,
            landingY - config->objectY,
            &direction,
            &distance)) {
        return FALSE;
    }

    result->landingX = landingX;
    result->landingY = landingY;
    result->finalTargetX = finalTargetX;
    result->finalTargetY = finalTargetY;
    result->direction = direction;
    result->distance = distance;
    result->flags = flags;
    result->reserved = 0;
    return TRUE;
}

static void OverworldWildHelper_AddHopPlanDirection(
    s8 *stepXs,
    s8 *stepYs,
    int *directionCount,
    int stepX,
    int stepY)
{
    int i;

    if (stepXs == NULL
        || stepYs == NULL
        || directionCount == NULL
        || (stepX == 0 && stepY == 0)) {
        return;
    }

    for (i = 0; i < *directionCount; i++) {
        if (stepXs[i] == stepX && stepYs[i] == stepY) {
            return;
        }
    }

    if (*directionCount >= OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS) {
        return;
    }

    stepXs[*directionCount] = (s8)stepX;
    stepYs[*directionCount] = (s8)stepY;
    (*directionCount)++;
}

static int OverworldWildHelper_BuildHopPlanDirections(
    const OverworldWildHelperHopConfig *config,
    int fromX,
    int fromY,
    s8 *stepXs,
    s8 *stepYs)
{
    int directionCount = 0;
    int dx;
    int dy;
    u8 targetDirections[4];
    int targetDirectionCount;
    int i;

    if (config == NULL || stepXs == NULL || stepYs == NULL) {
        return 0;
    }

    dx = config->targetX - fromX;
    dy = config->targetY - fromY;
    if (config->allowNonCardinal && dx != 0 && dy != 0) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            dx > 0 ? 1 : -1,
            dy > 0 ? 1 : -1);
    }

    targetDirectionCount = OverworldWildHelper_BuildDirections(
        dx,
        dy,
        targetDirections);
    for (i = 0; i < targetDirectionCount; i++) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            OverworldWildHelper_DirectionDeltaX(targetDirections[i]),
            OverworldWildHelper_DirectionDeltaY(targetDirections[i]));
    }

    for (i = 0; i < config->directionCount; i++) {
        OverworldWildHelper_AddHopPlanDirection(
            stepXs,
            stepYs,
            &directionCount,
            OverworldWildHelper_DirectionDeltaX(config->directions[i]),
            OverworldWildHelper_DirectionDeltaY(config->directions[i]));
    }

    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, 0);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, 0);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 0, 1);
    OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 0, -1);

    if (config->allowNonCardinal) {
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, 1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, 1, -1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, 1);
        OverworldWildHelper_AddHopPlanDirection(stepXs, stepYs, &directionCount, -1, -1);
    }

    return directionCount;
}

static int OverworldWildHelper_GetHopPlanDistance(
    int x,
    int y,
    int targetX,
    int targetY)
{
    return OverworldWildHelper_Max(
        OverworldWildHelper_Abs(targetX - x),
        OverworldWildHelper_Abs(targetY - y));
}

static BOOL OverworldWildHelper_IsHopTargetOneHopAway(
    const OverworldWildHelperHopConfig *config,
    int fromX,
    int fromY,
    int targetX,
    int targetY)
{
    return OverworldWildHelper_TryGetHopVector(
        config,
        targetX - fromX,
        targetY - fromY,
        NULL,
        NULL);
}

static BOOL OverworldWildHelper_HopPlanHasVisited(
    const s16 *nodeXs,
    const s16 *nodeYs,
    int nodeCount,
    int x,
    int y)
{
    int i;

    for (i = 0; i < nodeCount; i++) {
        if (nodeXs[i] == x && nodeYs[i] == y) {
            return TRUE;
        }
    }

    return FALSE;
}

static BOOL OverworldWildHelper_IsHopPlanCandidate(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    int fromX,
    int fromY,
    int toX,
    int toY)
{
    return OverworldWildHelper_TryGetHopVector(
            config,
            toX - fromX,
            toY - fromY,
            NULL,
            NULL)
        && OverworldWildHelper_IsLandingAllowed(
            config,
            validator,
            context,
            toX,
            toY);
}

static BOOL OverworldWildHelper_PickRandomBehaviorHop(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result)
{
    int dx;
    int dy;
    int targetX = 0;
    int targetY = 0;
    u32 candidateCount = 0;

    if (config == NULL
        || validator == NULL
        || result == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance) {
        return FALSE;
    }

    for (dy = -config->maxDistance; dy <= config->maxDistance; dy++) {
        for (dx = -config->maxDistance; dx <= config->maxDistance; dx++) {
            int candidateX;
            int candidateY;

            if (dx == 0 && dy == 0) {
                continue;
            }

            candidateX = config->objectX + dx;
            candidateY = config->objectY + dy;
            if (!OverworldWildHelper_TryGetHopVector(config, dx, dy, NULL, NULL)
                || !OverworldWildHelper_IsLandingAllowed(
                    config,
                    validator,
                    context,
                    candidateX,
                    candidateY)) {
                continue;
            }

            candidateCount++;
            if ((gf_rand() % candidateCount) == 0) {
                targetX = candidateX;
                targetY = candidateY;
            }
        }
    }

    if (candidateCount == 0) {
        return FALSE;
    }

    return OverworldWildHelper_SetHopResult(
        config,
        targetX,
        targetY,
        targetX,
        targetY,
        OW_WILD_HELPER_HOP_RESULT_FLAG_DIRECT,
        result);
}

static BOOL OverworldWildHelper_PlanBehaviorHopStep(
    const OverworldWildHelperHopConfig *config,
    OverworldWildHelperHopTileValidator validator,
    void *context,
    OverworldWildHelperHopResult *result)
{
    s16 nodeXs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 nodeYs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 firstXs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    s16 firstYs[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    u8 nodeDepths[OW_WILD_HELPER_HOP_PLAN_NODE_COUNT];
    int head = 0;
    int tail = 0;
    int bestFirstX = 0;
    int bestFirstY = 0;
    int bestTerminalX = 0;
    int bestTerminalY = 0;
    int bestDistance = 0x7FFF;
    u8 bestDepth = 0xFF;
    BOOL bestFound = FALSE;

    if (config == NULL
        || validator == NULL
        || result == NULL
        || config->minDistance == 0
        || config->maxDistance < config->minDistance) {
        return FALSE;
    }

    if ((config->stopOneHopAway
            || !OverworldWildHelper_IsLandingAllowed(
                config,
                validator,
                context,
                config->targetX,
                config->targetY))
        && (config->objectX != config->targetX || config->objectY != config->targetY)
        && OverworldWildHelper_IsHopTargetOneHopAway(
            config,
            config->objectX,
            config->objectY,
            config->targetX,
            config->targetY)) {
        return FALSE;
    }

    nodeXs[tail] = (s16)config->objectX;
    nodeYs[tail] = (s16)config->objectY;
    firstXs[tail] = (s16)config->objectX;
    firstYs[tail] = (s16)config->objectY;
    nodeDepths[tail] = 0;
    tail++;

    while (head < tail) {
        int fromX = nodeXs[head];
        int fromY = nodeYs[head];
        int nodeDistance = OverworldWildHelper_GetHopPlanDistance(
            fromX,
            fromY,
            config->targetX,
            config->targetY);
        s8 stepXs[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
        s8 stepYs[OW_WILD_HELPER_HOP_PLAN_MAX_DIRECTIONS];
        int planDirectionCount = OverworldWildHelper_BuildHopPlanDirections(
            config,
            fromX,
            fromY,
            stepXs,
            stepYs);
        int directionIndex;

        if (nodeDepths[head] >= OW_WILD_HELPER_HOP_PLAN_MAX_HOPS) {
            head++;
            continue;
        }

        for (directionIndex = 0; directionIndex < planDirectionCount; directionIndex++) {
            int stepX = stepXs[directionIndex];
            int stepY = stepYs[directionIndex];
            int distance;

            for (distance = config->maxDistance; distance >= config->minDistance; distance--) {
                int landingX = fromX + stepX * distance;
                int landingY = fromY + stepY * distance;
                int landingDistance = OverworldWildHelper_GetHopPlanDistance(
                    landingX,
                    landingY,
                    config->targetX,
                    config->targetY);
                int firstX = nodeDepths[head] == 0 ? landingX : firstXs[head];
                int firstY = nodeDepths[head] == 0 ? landingY : firstYs[head];
                BOOL landingIsTarget;
                BOOL landingCanReachTarget;

                if (landingDistance >= nodeDistance) {
                    continue;
                }
                if (!OverworldWildHelper_IsHopPlanCandidate(
                        config,
                        validator,
                        context,
                        fromX,
                        fromY,
                        landingX,
                        landingY)) {
                    continue;
                }

                landingIsTarget = landingX == config->targetX
                    && landingY == config->targetY;
                landingCanReachTarget =
                    !landingIsTarget
                    && OverworldWildHelper_IsHopTargetOneHopAway(
                        config,
                        landingX,
                        landingY,
                        config->targetX,
                        config->targetY);

                if (!bestFound
                    || landingDistance < bestDistance
                    || (landingDistance == bestDistance
                        && nodeDepths[head] + 1 < bestDepth)) {
                    bestFound = TRUE;
                    bestFirstX = firstX;
                    bestFirstY = firstY;
                    bestTerminalX = firstX;
                    bestTerminalY = firstY;
                    bestDistance = landingDistance;
                    bestDepth = nodeDepths[head] + 1;
                }

                if ((!config->stopOneHopAway && landingIsTarget)
                    || (config->stopOneHopAway && landingCanReachTarget)) {
                    return OverworldWildHelper_SetHopResult(
                        config,
                        firstX,
                        firstY,
                        landingX,
                        landingY,
                        OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED,
                        result);
                }

                if (config->stopOneHopAway && landingIsTarget) {
                    continue;
                }

                if (nodeDepths[head] + 1 >= OW_WILD_HELPER_HOP_PLAN_MAX_HOPS
                    || tail >= OW_WILD_HELPER_HOP_PLAN_NODE_COUNT
                    || OverworldWildHelper_HopPlanHasVisited(
                        nodeXs,
                        nodeYs,
                        tail,
                        landingX,
                        landingY)) {
                    continue;
                }

                nodeXs[tail] = (s16)landingX;
                nodeYs[tail] = (s16)landingY;
                firstXs[tail] = (s16)firstX;
                firstYs[tail] = (s16)firstY;
                nodeDepths[tail] = nodeDepths[head] + 1;
                tail++;
            }
        }

        head++;
    }

    if (!bestFound) {
        return FALSE;
    }

    return OverworldWildHelper_SetHopResult(
        config,
        bestFirstX,
        bestFirstY,
        bestTerminalX,
        bestTerminalY,
        OW_WILD_HELPER_HOP_RESULT_FLAG_PLANNED,
        result);
}

const OverworldWildHelperOverlayEntry gOverworldWildHelperOverlayEntry
    __attribute__((section(".overworld_wild_helper_entry"), used)) = {
    OVERWORLD_WILD_HELPER_OVERLAY_MAGIC,
    OVERWORLD_WILD_HELPER_OVERLAY_VERSION,
    sizeof(OverworldWildHelperOverlayEntry),
    OverworldWildHelper_PickRandomBehaviorHop,
    OverworldWildHelper_PlanBehaviorHopStep,
};
