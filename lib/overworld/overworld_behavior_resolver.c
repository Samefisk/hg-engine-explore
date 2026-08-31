#include "../../include/overworld_behavior_resolver.h"

#define RESOLVER_MATCH_ANY_SPECIES 0
#define RESOLVER_MATCH_ANY_U8 0xFF
#define RESOLVER_MATCH_LEVEL_ANY 0
#define RESOLVER_GROUP_NONE 0

#define RESOLVER_BEHAVIOR_CLASS_PICKED_UP 3
#define RESOLVER_BEHAVIOR_KIND_NONE 0
#define RESOLVER_BEHAVIOR_KIND_IDLE 1
#define RESOLVER_BEHAVIOR_KIND_WANDER 2
#define RESOLVER_BEHAVIOR_KIND_HEADBUTT_TREE_HOP 7
#define RESOLVER_BEHAVIOR_KIND_ASLEEP 8
#define RESOLVER_BEHAVIOR_KIND_MAX 11

#define RESOLVER_LOCOMOTION_NONE 0
#define RESOLVER_LOCOMOTION_WANDER 1
#define RESOLVER_LOCOMOTION_RAM 5
#define RESOLVER_LOCOMOTION_MAX 11

#define RESOLVER_TARGET_NONE 0
#define RESOLVER_TARGET_MAX 9
#define RESOLVER_TARGET_RANDOM_NEARBY 1
#define RESOLVER_TARGET_TOWARD_PLAYER 2
#define RESOLVER_TARGET_AWAY_FROM_PLAYER 3
#define RESOLVER_TARGET_TREE_TOP 4

#define RESOLVER_ALERT_RANGE_NONE 0
#define RESOLVER_ALERT_RANGE_TERRAIN_ONLY 5
#define RESOLVER_ALERT_STATE_SPEECH 2
#define RESOLVER_ALERT_SPECIAL_NONE 0
#define RESOLVER_ALERT_SPECIAL_PICKUP_THROW 2

#define RESOLVER_REACTION_NONE 0
#define RESOLVER_REACTION_CONTACT 1
#define RESOLVER_REACTION_FLEE 2
#define RESOLVER_REACTION_EMOTE 4
#define RESOLVER_REACTION_TIRED 5

#define RESOLVER_SPAWN_STATE_APPEAR 0
#define RESOLVER_SPAWN_STATE_APPEAR_HOP 3
#define RESOLVER_JUMP_LEVEL_BOTH 2
#define RESOLVER_BUBBLE_ID_SLEEP 13
#define RESOLVER_BUBBLE_ID_NONE 0xFF
#define RESOLVER_MAX_OVERWORLD_ACTORS 10
#define RESOLVER_MIN_PLAYER_RELATIVE_DISTANCE 1
#define RESOLVER_MAX_PLAYER_RELATIVE_DISTANCE 8

#define RESOLVER_MOVEMENT_RANGE 32
#define RESOLVER_CIRCLE_RADIUS_MAX 8
#define RESOLVER_BATTLE_TRIGGER_MAX 2
#define RESOLVER_WALK_TIME_MIN 1
#define RESOLVER_WALK_TIME_MAX 32

#define RESOLVER_OVERRIDE_LIMIT_KEY_BASE OWBD_CLASS_PROFILE_COUNT

static const u8 sRelativeFieldMaximums[] = {
    0, 0, 0, 255, 64, 64, 64, 32, 64, 0, 0, 0, 0, 0, 0, 0, 100, 0, 0,
    0, 12, 12, 255, 64, 255, 0, 10, 8, 8, 32, 255, 0, 0, 0, 64, 32, 32,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 32, 32, 0, 0, 0, 8, 8, 8,
    32, 5, 0, 0, 0, 0, 0, 0, 255, 32, 32,
};

static const u8 sSpawnLocomotion[] = {0, 3, 4, 7};
static const u8 sDefaultTarget[] = {
    RESOLVER_TARGET_NONE,
    RESOLVER_TARGET_NONE,
    RESOLVER_TARGET_RANDOM_NEARBY,
    RESOLVER_TARGET_TOWARD_PLAYER,
    RESOLVER_TARGET_AWAY_FROM_PLAYER,
    RESOLVER_TARGET_TOWARD_PLAYER,
    RESOLVER_TARGET_TOWARD_PLAYER,
    RESOLVER_TARGET_TREE_TOP,
};
static const u8 sActiveReaction[] = {
    RESOLVER_REACTION_NONE,
    RESOLVER_REACTION_NONE,
    RESOLVER_REACTION_NONE,
    RESOLVER_REACTION_CONTACT,
    RESOLVER_REACTION_FLEE,
    RESOLVER_REACTION_EMOTE,
    RESOLVER_REACTION_CONTACT,
    RESOLVER_REACTION_CONTACT,
};

typedef char BehaviorResolverRelativeFieldCountMustRemain67[
    sizeof(sRelativeFieldMaximums) == 67 ? 1 : -1];
typedef char BehaviorResolverProfileDataSizeMustRemain72[
    sizeof(OverworldWildBehaviorProfileData) == 72 ? 1 : -1];
typedef char BehaviorResolverProfileSizeMustRemain216[
    sizeof(OverworldWildBehaviorProfile) == 216 ? 1 : -1];

static u8 BehaviorResolver_FieldOffset(u8 fieldIndex)
{
    if (fieldIndex < 34) {
        return fieldIndex;
    }
    return fieldIndex < 52 ? fieldIndex + 2 : fieldIndex + 4;
}

static void BehaviorResolver_Trace(
    BehaviorResolutionTrace *trace,
    u8 lane,
    u8 kind,
    u16 sourceIndex,
    u8 flags,
    const OverworldWildBehaviorProfileData *profile)
{
    BehaviorResolutionStep *step;

    if (trace == NULL) {
        return;
    }
    if (trace->steps == NULL || trace->count >= trace->capacity) {
        trace->dropped++;
        return;
    }
    step = &trace->steps[trace->count++];
    memset(step, 0, sizeof(*step));
    step->lane = lane;
    step->kind = kind;
    step->sourceIndex = sourceIndex;
    step->flags = flags;
    if (profile != NULL) {
        step->profile = *profile;
    }
}

static BOOL BehaviorResolver_MatchApplies(
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorMatch *match)
{
    return context != NULL
        && match != NULL
        && (match->species == RESOLVER_MATCH_ANY_SPECIES
            || match->species == context->species)
        && (match->groupMask == RESOLVER_GROUP_NONE
            || (context->groupFlags & match->groupMask) != 0)
        && (match->terrain == RESOLVER_MATCH_ANY_U8
            || match->terrain == context->terrain)
        && (match->minLevel == RESOLVER_MATCH_LEVEL_ANY
            || context->level >= match->minLevel)
        && (match->maxLevel == RESOLVER_MATCH_LEVEL_ANY
            || context->level <= match->maxLevel)
        && (match->shiny == RESOLVER_MATCH_ANY_U8
            || match->shiny == context->shiny)
        && (match->behaviorClass == RESOLVER_MATCH_ANY_U8
            || match->behaviorClass == context->behaviorClass);
}

static BOOL BehaviorResolver_OverrideTargetsContext(
    const OverworldWildBehaviorContext *context,
    const OverworldWildBehaviorOverrideProfile *overrideProfile,
    const u16 *members,
    u16 memberCount)
{
    u32 end;
    u32 i;

    if (overrideProfile == NULL
        || overrideProfile->targetMode
            == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED
        || !BehaviorResolver_MatchApplies(context, &overrideProfile->match)) {
        return FALSE;
    }
    if (overrideProfile->targetMode == OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL) {
        return TRUE;
    }
    if (overrideProfile->targetMode
            != OW_WILD_BEHAVIOR_OVERRIDE_TARGET_MEMBERS
        || overrideProfile->memberCount == 0
        || members == NULL) {
        return FALSE;
    }
    end = (u32)overrideProfile->memberStart + overrideProfile->memberCount;
    if (end > memberCount) {
        return FALSE;
    }
    for (i = overrideProfile->memberStart; i < end; i++) {
        if (members[i] == context->species) {
            return TRUE;
        }
    }
    return FALSE;
}

static u16 BehaviorResolver_LegacySpawnDestinationMask(u8 destination)
{
    if (destination >= OW_WILD_SPAWN_DESTINATION_ROOFTOP
        && destination <= OW_WILD_SPAWN_DESTINATION_FLOWERBED) {
        return 1u << (destination - OW_WILD_SPAWN_DESTINATION_ROOFTOP + 6u);
    }
    if (destination == OW_WILD_SPAWN_DESTINATION_FIVE_TILES_BEHIND_PLAYER
        || (destination >= OW_WILD_SPAWN_DESTINATION_ONE_TILE_BEHIND_PLAYER
            && destination <= OW_WILD_SPAWN_DESTINATION_NEXT_TO_PLAYER)) {
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER;
    }
    if (destination >= OW_WILD_SPAWN_DESTINATION_FRONT_OF_PLAYER
        && destination
            <= OW_WILD_SPAWN_DESTINATION_FIVE_TILES_FRONT_OF_PLAYER) {
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_PLAYER_FRONT;
    }
    switch ((OverworldWildSpawnDestination)destination) {
    case OW_WILD_SPAWN_DESTINATION_CANOPY:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY;
    case OW_WILD_SPAWN_DESTINATION_LAND:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND;
    case OW_WILD_SPAWN_DESTINATION_GRASS:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
    case OW_WILD_SPAWN_DESTINATION_SHORE:
    case OW_WILD_SPAWN_DESTINATION_WATER:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER;
    case OW_WILD_SPAWN_DESTINATION_POOL:
    default:
        return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY
            | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
    }
}

static void BehaviorResolver_ResolveInheritedPolicies(
    OverworldWildBehaviorProfileData *profile)
{
    u16 terrainOverride = profile->chillAllowedTerrainOverrideMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    u16 destinationOverride = profile->spawnDestinationOverrideMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    u16 legacyDestination = BehaviorResolver_LegacySpawnDestinationMask(
        profile->spawnDestination);

    profile->chillAllowedTerrainMask =
        (profile->chillAllowedTerrainMask & terrainOverride)
        | (OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_DEFAULT & ~terrainOverride);
    profile->spawnDestinationMask =
        (profile->spawnDestinationMask & destinationOverride)
        | (legacyDestination & ~destinationOverride);
    profile->spawnDestinationOverrideMask = destinationOverride;
}

static void BehaviorResolver_ApplyMask(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorProfileData *values,
    u32 mask,
    u32 relativeMask,
    u32 atLeastMask,
    u32 atMostMask,
    const OverworldWildBehaviorProfileData *bounds,
    u8 fieldIndex)
{
    u8 *profileBytes = (u8 *)profile;
    const u8 *valueBytes = (const u8 *)values;
    const u8 *boundBytes = (const u8 *)bounds;

    while (mask != 0 && fieldIndex < sizeof(sRelativeFieldMaximums)) {
        if (mask & 1u) {
            u8 offset = BehaviorResolver_FieldOffset(fieldIndex);

            if (relativeMask & 1u) {
                int adjusted = (int)profileBytes[offset]
                    + (int)(s8)valueBytes[offset];
                int minimum = fieldIndex == 7
                    || fieldIndex == 27
                    || fieldIndex == 28
                    || (fieldIndex >= 48 && fieldIndex < 54)
                    || fieldIndex == 56
                    || fieldIndex == 57;
                int maximum = sRelativeFieldMaximums[fieldIndex];

                if (adjusted < minimum) {
                    adjusted = minimum;
                } else if (adjusted > maximum) {
                    adjusted = maximum;
                }
                profileBytes[offset] = (u8)adjusted;
            }
            if ((atLeastMask & 1u) || (atMostMask & 1u)) {
                u8 threshold = (relativeMask & 1u)
                    ? boundBytes[offset]
                    : valueBytes[offset];

                if ((atLeastMask & 1u) && profileBytes[offset] < threshold) {
                    profileBytes[offset] = threshold;
                } else if ((atMostMask & 1u)
                    && profileBytes[offset] > threshold) {
                    profileBytes[offset] = threshold;
                }
            } else if (!(relativeMask & 1u)) {
                profileBytes[offset] = valueBytes[offset];
            }
        }
        mask >>= 1;
        relativeMask >>= 1;
        atLeastMask >>= 1;
        atMostMask >>= 1;
        fieldIndex++;
    }
}

static void BehaviorResolver_ApplyOverride(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorOverrideProfile *overrideProfile)
{
    u16 explicitDestinationMask;
    u16 explicitTerrainMask;
    u16 mask2 = overrideProfile->mask2;
    u32 mask3 = overrideProfile->mask3;

    BehaviorResolver_ApplyMask(
        profile,
        &overrideProfile->profile,
        overrideProfile->mask,
        overrideProfile->relativeMask,
        overrideProfile->atLeastMask,
        overrideProfile->atMostMask,
        &overrideProfile->compoundBoundProfile,
        0);
    BehaviorResolver_ApplyMask(
        profile,
        &overrideProfile->profile,
        mask2 & ~(OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK),
        overrideProfile->relativeMask2,
        overrideProfile->atLeastMask2,
        overrideProfile->atMostMask2,
        &overrideProfile->compoundBoundProfile,
        27);
    if (mask2 & OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK) {
        explicitTerrainMask =
            overrideProfile->profile.chillAllowedTerrainOverrideMask
            & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
        profile->chillAllowedTerrainMask =
            (profile->chillAllowedTerrainMask & ~explicitTerrainMask)
            | (overrideProfile->profile.chillAllowedTerrainMask
                & explicitTerrainMask);
    }
    BehaviorResolver_ApplyMask(
        profile,
        &overrideProfile->profile,
        mask3 & ~(OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_OVERRIDE_MASK),
        overrideProfile->relativeMask3,
        overrideProfile->atLeastMask3,
        overrideProfile->atMostMask3,
        &overrideProfile->compoundBoundProfile,
        42);
    if (mask3 & OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_OVERRIDE_MASK) {
        explicitDestinationMask =
            overrideProfile->profile.spawnDestinationOverrideMask
            & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
        profile->spawnDestinationMask =
            (profile->spawnDestinationMask & ~explicitDestinationMask)
            | (overrideProfile->profile.spawnDestinationMask
                & explicitDestinationMask);
        profile->spawnDestinationOverrideMask |= explicitDestinationMask;
    } else if (overrideProfile->mask
        & OW_WILD_BEHAVIOR_OVERRIDE_SPAWN_DESTINATION) {
        profile->spawnDestinationMask =
            BehaviorResolver_LegacySpawnDestinationMask(
                profile->spawnDestination);
        profile->spawnDestinationOverrideMask =
            OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    }
}

static u8 BehaviorResolver_ClampWalkTime(u8 value)
{
    if (value < RESOLVER_WALK_TIME_MIN) {
        return RESOLVER_WALK_TIME_MIN;
    }
    if (value > RESOLVER_WALK_TIME_MAX) {
        return RESOLVER_WALK_TIME_MAX;
    }
    return value;
}

static void BehaviorResolver_NormalizeLane(
    OverworldWildBehaviorProfileData *profile,
    u8 invalidState)
{
    profile->chillSpeed = BehaviorResolver_ClampWalkTime(profile->chillSpeed);
    profile->maxWalkSpeed = BehaviorResolver_ClampWalkTime(profile->maxWalkSpeed);
    if (profile->maxWalkSpeed > profile->chillSpeed) {
        profile->maxWalkSpeed = profile->chillSpeed;
    }
    profile->chainRepositionSpeed = BehaviorResolver_ClampWalkTime(
        profile->chainRepositionSpeed);
    if (profile->chaseBoostSpeed > RESOLVER_WALK_TIME_MAX) {
        profile->chaseBoostSpeed = RESOLVER_WALK_TIME_MAX;
    }
    if (profile->walkStompTime > RESOLVER_WALK_TIME_MAX) {
        profile->walkStompTime = RESOLVER_WALK_TIME_MAX;
    }
    if (profile->chillState > RESOLVER_BEHAVIOR_KIND_MAX) {
        profile->chillState = invalidState;
    }
    if (profile->chillAction > RESOLVER_LOCOMOTION_MAX) {
        profile->chillAction = RESOLVER_LOCOMOTION_NONE;
    }
    if (profile->chillTarget > RESOLVER_TARGET_MAX) {
        profile->chillTarget = RESOLVER_TARGET_NONE;
    }
    if (profile->hopAllowNonCardinal
        > OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_MAX) {
        profile->hopAllowNonCardinal =
            OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
    }
    if (profile->hopMaxDistance < profile->hopMinDistance) {
        profile->hopMaxDistance = profile->hopMinDistance;
    }
    if (profile->ramAccelerationSteps > RESOLVER_MOVEMENT_RANGE) {
        profile->ramAccelerationSteps = RESOLVER_MOVEMENT_RANGE;
    }
    if (profile->chainMovementVariance > RESOLVER_MOVEMENT_RANGE) {
        profile->chainMovementVariance = RESOLVER_MOVEMENT_RANGE;
    }
    if (profile->tilesToAccelerate == 0) {
        profile->tilesToAccelerate =
            OW_WILD_BEHAVIOR_TILES_TO_ACCELERATE_DEFAULT;
    } else if (profile->tilesToAccelerate > RESOLVER_MOVEMENT_RANGE) {
        profile->tilesToAccelerate = RESOLVER_MOVEMENT_RANGE;
    }
    if (profile->chainPauseAction
        > OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS) {
        profile->chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE;
    }
    if (profile->circleRadius > RESOLVER_CIRCLE_RADIUS_MAX) {
        profile->circleRadius = RESOLVER_CIRCLE_RADIUS_MAX;
    }
    if (profile->battleTrigger > RESOLVER_BATTLE_TRIGGER_MAX) {
        profile->battleTrigger = RESOLVER_TARGET_NONE;
    }
}

static void BehaviorResolver_NormalizeProfile(
    OverworldWildBehaviorProfile *profile)
{
    BehaviorResolver_NormalizeLane(&profile->owner, RESOLVER_BEHAVIOR_KIND_IDLE);
    BehaviorResolver_NormalizeLane(&profile->active, RESOLVER_BEHAVIOR_KIND_NONE);
    BehaviorResolver_NormalizeLane(&profile->tired, RESOLVER_BEHAVIOR_KIND_NONE);

    if (profile->alertSpecialAction > RESOLVER_ALERT_SPECIAL_PICKUP_THROW) {
        profile->alertSpecialAction = RESOLVER_ALERT_SPECIAL_NONE;
    }
    if (profile->overworldLimit > RESOLVER_MAX_OVERWORLD_ACTORS) {
        profile->overworldLimit = RESOLVER_MAX_OVERWORLD_ACTORS;
    }
    if (profile->chillState == RESOLVER_BEHAVIOR_KIND_ASLEEP) {
        profile->tiredState = RESOLVER_BEHAVIOR_KIND_ASLEEP;
        profile->stamina = 1;
        profile->alertness = 0;
        profile->alertChance = 0;
    } else if (profile->tiredState == RESOLVER_BEHAVIOR_KIND_ASLEEP) {
        profile->stamina = 1;
    }
    if ((profile->attentiveState != RESOLVER_BEHAVIOR_KIND_NONE
            || profile->targetSelector != RESOLVER_TARGET_NONE
            || profile->movementStyle != RESOLVER_LOCOMOTION_NONE
            || profile->attentiveBattle != 0)
        && profile->tiredState != RESOLVER_BEHAVIOR_KIND_NONE
        && profile->stamina == 0) {
        profile->stamina = 1;
    }
    if (profile->tiredState != RESOLVER_BEHAVIOR_KIND_NONE
        && profile->tiredState != RESOLVER_BEHAVIOR_KIND_ASLEEP
        && profile->restTime == 0) {
        profile->restTime = 1;
    }
    if (profile->jumpLevel > RESOLVER_JUMP_LEVEL_BOTH) {
        profile->jumpLevel = RESOLVER_JUMP_LEVEL_BOTH;
    }
    if (profile->spawnState > RESOLVER_SPAWN_STATE_APPEAR_HOP) {
        profile->spawnState = RESOLVER_SPAWN_STATE_APPEAR;
    }
    if (profile->alertState > RESOLVER_ALERT_STATE_SPEECH) {
        profile->alertState = RESOLVER_ALERT_RANGE_NONE;
    }
    if (profile->alertEmote > RESOLVER_BUBBLE_ID_SLEEP
        && profile->alertEmote != RESOLVER_BUBBLE_ID_NONE) {
        profile->alertEmote = RESOLVER_BUBBLE_ID_NONE;
    }
    if (profile->alertRange > RESOLVER_ALERT_RANGE_TERRAIN_ONLY) {
        profile->alertRange = RESOLVER_ALERT_RANGE_NONE;
    }
    if (profile->spawnDestination > OW_WILD_SPAWN_DESTINATION_FLOWERBED) {
        profile->spawnDestination = OW_WILD_SPAWN_DESTINATION_POOL;
    }
    profile->spawnDestinationMask &= OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    profile->spawnDestinationOverrideMask &=
        OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    if (profile->spawnDestinationMinDistance
        < RESOLVER_MIN_PLAYER_RELATIVE_DISTANCE) {
        profile->spawnDestinationMinDistance =
            RESOLVER_MIN_PLAYER_RELATIVE_DISTANCE;
    } else if (profile->spawnDestinationMinDistance
        > RESOLVER_MAX_PLAYER_RELATIVE_DISTANCE) {
        profile->spawnDestinationMinDistance =
            RESOLVER_MAX_PLAYER_RELATIVE_DISTANCE;
    }
    if (profile->spawnDestinationMaxDistance
        < RESOLVER_MIN_PLAYER_RELATIVE_DISTANCE) {
        profile->spawnDestinationMaxDistance =
            RESOLVER_MIN_PLAYER_RELATIVE_DISTANCE;
    } else if (profile->spawnDestinationMaxDistance
        > RESOLVER_MAX_PLAYER_RELATIVE_DISTANCE) {
        profile->spawnDestinationMaxDistance =
            RESOLVER_MAX_PLAYER_RELATIVE_DISTANCE;
    }
    if (profile->spawnDestinationMaxDistance
        < profile->spawnDestinationMinDistance) {
        profile->spawnDestinationMaxDistance =
            profile->spawnDestinationMinDistance;
    }
}

static void BehaviorResolver_NormalizePrimitive(
    u8 behaviorKind,
    u8 *locomotion,
    u8 *target)
{
    if (behaviorKind < RESOLVER_BEHAVIOR_KIND_WANDER
        || behaviorKind > RESOLVER_BEHAVIOR_KIND_HEADBUTT_TREE_HOP) {
        *locomotion = RESOLVER_LOCOMOTION_NONE;
        *target = RESOLVER_TARGET_NONE;
    } else if (*target == RESOLVER_TARGET_NONE) {
        *target = sDefaultTarget[behaviorKind];
    }
}

static void BehaviorResolver_ResolvePrimitives(
    const OverworldWildBehaviorProfile *profile,
    OverworldWildBehaviorPrimitives *primitives)
{
    memset(primitives, 0, sizeof(*primitives));
    if (profile->spawnState < sizeof(sSpawnLocomotion)) {
        primitives->spawnLocomotion = sSpawnLocomotion[profile->spawnState];
    }
    primitives->chillLocomotion = profile->chillAction;
    primitives->chillTarget = profile->chillTarget;
    if (primitives->chillLocomotion == RESOLVER_LOCOMOTION_RAM) {
        primitives->chillLocomotion = RESOLVER_LOCOMOTION_WANDER;
    } else if (OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(
                   primitives->chillLocomotion)) {
        primitives->chillLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
    }
    BehaviorResolver_NormalizePrimitive(
        profile->chillState,
        &primitives->chillLocomotion,
        &primitives->chillTarget);

    primitives->attentiveLocomotion = profile->movementStyle;
    primitives->attentiveTarget = profile->targetSelector;
    if (primitives->attentiveLocomotion == RESOLVER_LOCOMOTION_RAM) {
        primitives->attentiveLocomotion = RESOLVER_LOCOMOTION_WANDER;
    } else if (OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(
                   primitives->attentiveLocomotion)) {
        primitives->attentiveLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
    }
    if (profile->attentiveState < sizeof(sActiveReaction)) {
        primitives->activeReaction = sActiveReaction[profile->attentiveState];
        if (profile->attentiveState >= RESOLVER_BEHAVIOR_KIND_WANDER
            && primitives->attentiveTarget == RESOLVER_TARGET_NONE) {
            primitives->attentiveTarget =
                sDefaultTarget[profile->attentiveState];
        }
    }
    if (profile->alertness != 0
        && profile->alertChance != 0
        && profile->alertRange <= RESOLVER_ALERT_RANGE_TERRAIN_ONLY) {
        primitives->alertLogic = profile->alertRange;
        primitives->alertReaction =
            profile->alertRange == RESOLVER_ALERT_RANGE_NONE
            ? RESOLVER_REACTION_NONE
            : RESOLVER_REACTION_EMOTE;
    }

    primitives->tiredLocomotion = profile->tired.chillAction;
    primitives->tiredTarget = profile->tired.chillTarget;
    if (primitives->tiredLocomotion == RESOLVER_LOCOMOTION_RAM) {
        primitives->tiredLocomotion = RESOLVER_LOCOMOTION_WANDER;
    } else if (OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(
                   primitives->tiredLocomotion)) {
        primitives->tiredLocomotion = OW_WILD_BEHAVIOR_LOCOMOTION_TELEPORT;
    }
    BehaviorResolver_NormalizePrimitive(
        profile->tiredState,
        &primitives->tiredLocomotion,
        &primitives->tiredTarget);
    if (profile->tiredState != RESOLVER_BEHAVIOR_KIND_NONE) {
        primitives->tiredReaction = RESOLVER_REACTION_TIRED;
    }
}

static u32 BehaviorResolver_SelectConditionalMask(
    const OverworldWildBehaviorDataBlob *blob,
    const OverworldWildBehaviorContext *context,
    u32 applicableMask,
    u8 movementSpeed)
{
    u32 selected = 0;
    u16 i;

    for (i = 0; i < blob->header.conditionalStateCount; i++) {
        const OverworldWildBehaviorConditionalState *condition =
            &blob->conditionalStates[i];
        u16 explicitTerrainMask = condition->terrainOverrideMask;
        u16 acceptedTerrainMask = condition->terrainMask
            & explicitTerrainMask;

        if (condition->parentProfile >= blob->header.overrideProfileCount
            || condition->overrideProfile >= blob->header.overrideProfileCount
            || (applicableMask & (1u << condition->parentProfile)) == 0
            || (explicitTerrainMask != 0
                && (context->conditionTerrainMask == 0
                    || (acceptedTerrainMask != 0
                        && (context->conditionTerrainMask
                            & acceptedTerrainMask) == 0)
                    || (context->conditionTerrainMask
                        & (explicitTerrainMask & ~acceptedTerrainMask)) != 0))
            || (condition->minMovementSpeed != 0
                && movementSpeed < condition->minMovementSpeed)
            || (condition->maxMovementSpeed != 0
                && movementSpeed > condition->maxMovementSpeed)) {
            continue;
        }
        selected |= 1u << condition->overrideProfile;
    }
    return selected;
}

static BOOL BehaviorResolver_BlobValid(
    const OverworldWildBehaviorDataBlob *blob,
    u32 blobSize)
{
    const OverworldWildBehaviorDataBlobHeader *header;

    if (blob == NULL || blobSize < sizeof(*blob)) {
        return FALSE;
    }
    header = &blob->header;
    return header->magic == OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        && header->version == OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        && header->headerSize == sizeof(*header)
        && header->blobSize == sizeof(*blob)
        && header->blobSize <= blobSize
        && header->classProfilesOffset
            == __builtin_offsetof(OverworldWildBehaviorDataBlob, classProfiles)
        && header->classProfileCount == OWBD_CLASS_PROFILE_COUNT
        && header->classProfileSize == sizeof(OverworldWildBehaviorProfileData)
        && header->classRulesOffset
            == __builtin_offsetof(OverworldWildBehaviorDataBlob, classRules)
        && header->classRuleCount == OWBD_CLASS_RULE_COUNT
        && header->classRuleSize == sizeof(OverworldWildBehaviorClassRule)
        && header->speciesClassRulesOffset
            == __builtin_offsetof(
                OverworldWildBehaviorDataBlob,
                speciesClassRules)
        && header->speciesClassRuleCount == OWBD_SPECIES_CLASS_RULE_COUNT
        && header->speciesClassRuleSize
            == sizeof(OverworldWildBehaviorSpeciesClassRule)
        && header->overrideProfilesOffset
            == __builtin_offsetof(
                OverworldWildBehaviorDataBlob,
                overrideProfiles)
        && header->overrideProfileCount == OWBD_OVERRIDE_PROFILE_COUNT
        && header->overrideProfileSize
            == sizeof(OverworldWildBehaviorOverrideProfile)
        && header->overrideMembersOffset
            == __builtin_offsetof(OverworldWildBehaviorDataBlob, overrideMembers)
        && header->overrideMemberCount == OWBD_OVERRIDE_MEMBER_COUNT
        && header->overrideMemberSize == sizeof(u16)
        && header->conditionalStatesOffset
            == __builtin_offsetof(
                OverworldWildBehaviorDataBlob,
                conditionalStates)
        && header->conditionalStateCount == OWBD_CONDITIONAL_STATE_COUNT
        && header->conditionalStateSize
            == sizeof(OverworldWildBehaviorConditionalState)
        && header->surfaceModelsOffset
            == __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceModels)
        && header->surfaceModelCount == OWBD_SURFACE_MODEL_COUNT
        && header->surfaceModelSize
            == sizeof(OverworldWildSurfaceModelDirectoryEntry)
        && header->surfaceInstancesOffset
            == __builtin_offsetof(
                OverworldWildBehaviorDataBlob,
                surfaceInstances)
        && header->surfaceInstanceCount == OWBD_SURFACE_INSTANCE_COUNT
        && header->surfaceInstanceSize == sizeof(OverworldWildSurfaceInstance)
        && header->surfaceTemplatesOffset
            == __builtin_offsetof(
                OverworldWildBehaviorDataBlob,
                surfaceTemplates)
        && header->surfaceTemplateCount == OWBD_SURFACE_TEMPLATE_COUNT
        && header->surfaceTemplateSize == sizeof(OverworldWildSurfaceTemplate);
}

static u8 BehaviorResolver_SelectClassInternal(
    const OverworldWildBehaviorDataBlob *blob,
    OverworldWildBehaviorContext *context,
    u8 requestedClass,
    BehaviorClassSelection *selection,
    BehaviorResolutionTrace *trace)
{
    u8 behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    u16 i;

    selection->speciesClassRuleIndex = BEHAVIOR_RESOLVER_NO_SOURCE;
    if (requestedClass != BEHAVIOR_RESOLVER_CLASS_AUTO) {
        context->behaviorClass = requestedClass;
        behaviorClass = requestedClass < blob->header.classProfileCount
            ? requestedClass
            : OW_WILD_BEHAVIOR_CLASS_DEFAULT;
        selection->behaviorClass = behaviorClass;
        return behaviorClass;
    }

    context->behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    for (i = 0; i < blob->header.classRuleCount; i++) {
        if (!BehaviorResolver_MatchApplies(context, &blob->classRules[i].match)) {
            continue;
        }
        behaviorClass = blob->classRules[i].behaviorClass;
        if (i < 32) {
            selection->matchedClassRuleMask |= 1u << i;
        }
        BehaviorResolver_Trace(
            trace,
            BEHAVIOR_RESOLUTION_LANE_NONE,
            BEHAVIOR_RESOLUTION_STEP_CLASS_RULE,
            i,
            BEHAVIOR_RESOLUTION_STEP_MATCHED
                | BEHAVIOR_RESOLUTION_STEP_APPLIED,
            NULL);
    }
    for (i = 0; i < blob->header.speciesClassRuleCount; i++) {
        if (blob->speciesClassRules[i].species != context->species) {
            continue;
        }
        behaviorClass = blob->speciesClassRules[i].behaviorClass;
        selection->speciesClassRuleIndex = i;
        BehaviorResolver_Trace(
            trace,
            BEHAVIOR_RESOLUTION_LANE_NONE,
            BEHAVIOR_RESOLUTION_STEP_SPECIES_CLASS_RULE,
            i,
            BEHAVIOR_RESOLUTION_STEP_MATCHED
                | BEHAVIOR_RESOLUTION_STEP_APPLIED,
            NULL);
    }
    if (behaviorClass >= blob->header.classProfileCount) {
        behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    }
    context->behaviorClass = behaviorClass;
    selection->behaviorClass = behaviorClass;
    return behaviorClass;
}

static BOOL BehaviorResolver_RequestValid(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request)
{
    u32 validOverrideMask;

    if (request == NULL) {
        return FALSE;
    }
    validOverrideMask = blob->header.overrideProfileCount == 32
        ? 0xFFFFFFFFu
        : ((1u << blob->header.overrideProfileCount) - 1u);
    return (request->forcedOverrideMask & ~validOverrideMask) == 0
        && request->context.level <= 100
        && request->context.terrain <= OW_WILD_SPAWN_TERRAIN_FISHING
        && request->context.shiny <= 1;
}

BehaviorResolveStatus BehaviorResolver_InspectClass(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request,
    BehaviorClassSelection *selection,
    BehaviorResolutionTrace *trace)
{
    const OverworldWildBehaviorDataBlob *blob =
        (const OverworldWildBehaviorDataBlob *)blobBytes;
    OverworldWildBehaviorContext context;

    if (request == NULL || selection == NULL) {
        return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;
    }
    memset(selection, 0, sizeof(*selection));
    if (trace != NULL) {
        trace->count = 0;
        trace->dropped = 0;
        trace->reserved = 0;
    }
    if (!BehaviorResolver_BlobValid(blob, blobSize)) {
        return BEHAVIOR_RESOLVE_INVALID_BLOB;
    }
    if (!BehaviorResolver_RequestValid(blob, request)) {
        return BEHAVIOR_RESOLVE_INVALID_CONTEXT;
    }

    context = request->context;
    BehaviorResolver_SelectClassInternal(
        blob,
        &context,
        request->behaviorClass,
        selection,
        trace);
    return trace != NULL && trace->dropped != 0
        ? BEHAVIOR_RESOLVE_TRACE_TRUNCATED
        : BEHAVIOR_RESOLVE_OK;
}

static void BehaviorResolver_ApplyRecorded(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorOverrideProfile *overrideProfile,
    u16 index,
    u8 lane,
    u8 kind,
    u8 flags,
    BehaviorResolveResult *result,
    BehaviorResolutionTrace *trace)
{
    BehaviorResolver_ApplyOverride(profile, overrideProfile);
    result->appliedOverrideMask |= 1u << index;
    BehaviorResolver_Trace(
        trace,
        lane,
        kind,
        index,
        flags | BEHAVIOR_RESOLUTION_STEP_APPLIED,
        profile);
}

static u32 BehaviorResolver_FingerprintBytes(
    u32 hash,
    const void *bytes,
    u32 size)
{
    const u8 *cursor = (const u8 *)bytes;

    while (size-- != 0) {
        hash ^= *cursor++;
        hash *= 16777619u;
    }
    return hash;
}

static u32 BehaviorResolver_FingerprintU32(u32 hash, u32 value)
{
    u8 bytes[4];

    bytes[0] = (u8)value;
    bytes[1] = (u8)(value >> 8);
    bytes[2] = (u8)(value >> 16);
    bytes[3] = (u8)(value >> 24);
    return BehaviorResolver_FingerprintBytes(hash, bytes, sizeof(bytes));
}

BehaviorResolveStatus BehaviorResolver_Resolve(
    const void *blobBytes,
    u32 blobSize,
    const BehaviorResolveRequest *request,
    BehaviorResolveResult *result,
    BehaviorResolutionTrace *trace)
{
    const OverworldWildBehaviorDataBlob *blob =
        (const OverworldWildBehaviorDataBlob *)blobBytes;
    OverworldWildBehaviorContext context;
    OverworldWildBehaviorProfileData owner;
    OverworldWildBehaviorProfileData active;
    OverworldWildBehaviorProfileData tired;
    BehaviorClassSelection classSelection;
    u32 applicableMask = 0;
    u32 conditionalMask = 0;
    u8 behaviorClass;
    u8 activeIndex;
    u8 tiredIndex;
    u16 i;
    int pass;
    u32 hash;

    if (request == NULL || result == NULL) {
        return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;
    }
    memset(result, 0, sizeof(*result));
    if (trace != NULL) {
        trace->count = 0;
        trace->dropped = 0;
        trace->reserved = 0;
    }
    if (!BehaviorResolver_BlobValid(blob, blobSize)) {
        return BEHAVIOR_RESOLVE_INVALID_BLOB;
    }
    if (!BehaviorResolver_RequestValid(blob, request)) {
        return BEHAVIOR_RESOLVE_INVALID_CONTEXT;
    }

    context = request->context;
    memset(&classSelection, 0, sizeof(classSelection));
    behaviorClass = BehaviorResolver_SelectClassInternal(
        blob,
        &context,
        request->behaviorClass,
        &classSelection,
        trace);
    result->behaviorClass = behaviorClass;
    result->behaviorLimitKey = behaviorClass;
    result->matchedClassRuleMask = classSelection.matchedClassRuleMask;
    result->speciesClassRuleIndex = classSelection.speciesClassRuleIndex;
    result->forcedOverrideMask = request->forcedOverrideMask;

    memcpy(&owner, &blob->classProfiles[behaviorClass], sizeof(owner));
    BehaviorResolver_ResolveInheritedPolicies(&owner);
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_OWNER,
        BEHAVIOR_RESOLUTION_STEP_BASE,
        behaviorClass,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &owner);

    if (behaviorClass != RESOLVER_BEHAVIOR_CLASS_PICKED_UP) {
        for (i = 0; i < blob->header.overrideProfileCount; i++) {
            u32 bit = 1u << i;
            BOOL matched = BehaviorResolver_OverrideTargetsContext(
                &context,
                &blob->overrideProfiles[i],
                blob->overrideMembers,
                blob->header.overrideMemberCount);

            if (matched) {
                result->matchedOverrideMask |= bit;
            }
            if (matched || (request->forcedOverrideMask & bit) != 0) {
                applicableMask |= bit;
            }
        }

        /* Resolve the condition predicate from the ordinary Owner lane. */
        for (i = 0; i < blob->header.overrideProfileCount; i++) {
            if (applicableMask & (1u << i)) {
                BehaviorResolver_ApplyOverride(&owner, &blob->overrideProfiles[i]);
            }
        }
        conditionalMask = BehaviorResolver_SelectConditionalMask(
            blob,
            &context,
            applicableMask,
            owner.chillSpeed);

        memcpy(&owner, &blob->classProfiles[behaviorClass], sizeof(owner));
        BehaviorResolver_ResolveInheritedPolicies(&owner);
        for (pass = 0; pass < 2; pass++) {
            u32 applyMask = pass == 0
                ? applicableMask & ~conditionalMask
                : conditionalMask;

            for (i = 0; i < blob->header.overrideProfileCount; i++) {
                u32 bit = 1u << i;
                u8 flags;

                if ((applyMask & bit) == 0) {
                    continue;
                }
                flags = (result->matchedOverrideMask & bit)
                        ? BEHAVIOR_RESOLUTION_STEP_MATCHED
                        : 0;
                if (request->forcedOverrideMask & bit) {
                    flags |= BEHAVIOR_RESOLUTION_STEP_FORCED;
                }
                if (pass != 0) {
                    flags |= BEHAVIOR_RESOLUTION_STEP_CONDITIONAL;
                }
                BehaviorResolver_ApplyRecorded(
                    &owner,
                    &blob->overrideProfiles[i],
                    i,
                    BEHAVIOR_RESOLUTION_LANE_OWNER,
                    pass == 0
                        ? BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE
                        : BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE,
                    flags,
                    result,
                    trace);
                if (blob->overrideProfiles[i].mask
                    & OW_WILD_BEHAVIOR_OVERRIDE_OVERWORLD_LIMIT) {
                    result->behaviorLimitKey =
                        (u8)(RESOLVER_OVERRIDE_LIMIT_KEY_BASE + i);
                }
            }
        }
    }
    result->conditionalOverrideMask = conditionalMask;

    activeIndex = owner.activeProfile;
    if (activeIndex >= blob->header.overrideProfileCount) {
        activeIndex = OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_ACTIVE;
    }
    tiredIndex = owner.tiredProfile;
    if (tiredIndex >= blob->header.overrideProfileCount) {
        tiredIndex = OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_TIRED;
    }

    memcpy(&active, &blob->classProfiles[behaviorClass], sizeof(active));
    BehaviorResolver_ResolveInheritedPolicies(&active);
    memcpy(&tired, &active, sizeof(tired));
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_ACTIVE,
        BEHAVIOR_RESOLUTION_STEP_BASE,
        behaviorClass,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &active);
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_STEP_BASE,
        behaviorClass,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &tired);

    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        u32 bit = 1u << i;
        u8 flags;

        if ((applicableMask & ~conditionalMask & bit) == 0) {
            continue;
        }
        flags = (result->matchedOverrideMask & bit)
                ? BEHAVIOR_RESOLUTION_STEP_MATCHED
                : 0;
        if (request->forcedOverrideMask & bit) {
            flags |= BEHAVIOR_RESOLUTION_STEP_FORCED;
        }
        if (i != activeIndex) {
            BehaviorResolver_ApplyRecorded(
                &active,
                &blob->overrideProfiles[i],
                i,
                BEHAVIOR_RESOLUTION_LANE_ACTIVE,
                BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE,
                flags,
                result,
                trace);
        }
        if (i != tiredIndex) {
            BehaviorResolver_ApplyRecorded(
                &tired,
                &blob->overrideProfiles[i],
                i,
                BEHAVIOR_RESOLUTION_LANE_TIRED,
                BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE,
                flags,
                result,
                trace);
        }
    }
    BehaviorResolver_ApplyRecorded(
        &active,
        &blob->overrideProfiles[activeIndex],
        activeIndex,
        BEHAVIOR_RESOLUTION_LANE_ACTIVE,
        BEHAVIOR_RESOLUTION_STEP_LANE_REFERENCE,
        0,
        result,
        trace);
    BehaviorResolver_ApplyRecorded(
        &tired,
        &blob->overrideProfiles[tiredIndex],
        tiredIndex,
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_STEP_LANE_REFERENCE,
        0,
        result,
        trace);
    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        u32 bit = 1u << i;

        if ((conditionalMask & bit) == 0) {
            continue;
        }
        if (i != activeIndex) {
            BehaviorResolver_ApplyRecorded(
                &active,
                &blob->overrideProfiles[i],
                i,
                BEHAVIOR_RESOLUTION_LANE_ACTIVE,
                BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE,
                BEHAVIOR_RESOLUTION_STEP_CONDITIONAL,
                result,
                trace);
        }
        if (i != tiredIndex) {
            BehaviorResolver_ApplyRecorded(
                &tired,
                &blob->overrideProfiles[i],
                i,
                BEHAVIOR_RESOLUTION_LANE_TIRED,
                BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE,
                BEHAVIOR_RESOLUTION_STEP_CONDITIONAL,
                result,
                trace);
        }
    }

    memset(&result->profile, 0, sizeof(result->profile));
    memcpy(&result->profile.owner, &owner, sizeof(owner));
    memcpy(&result->profile.active, &active, sizeof(active));
    memcpy(&result->profile.tired, &tired, sizeof(tired));
    if (active.alertSpecialAction == RESOLVER_ALERT_SPECIAL_PICKUP_THROW
        || result->profile.alertSpecialAction
            == RESOLVER_ALERT_SPECIAL_PICKUP_THROW) {
        result->profile.alertSpecialAction = active.alertSpecialAction;
    }
    BehaviorResolver_NormalizeProfile(&result->profile);
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_OWNER,
        BEHAVIOR_RESOLUTION_STEP_NORMALIZE,
        BEHAVIOR_RESOLVER_NO_SOURCE,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &result->profile.owner);
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_ACTIVE,
        BEHAVIOR_RESOLUTION_STEP_NORMALIZE,
        BEHAVIOR_RESOLVER_NO_SOURCE,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &result->profile.active);
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_STEP_NORMALIZE,
        BEHAVIOR_RESOLVER_NO_SOURCE,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &result->profile.tired);
    BehaviorResolver_ResolvePrimitives(&result->profile, &result->primitives);

    hash = 2166136261u;
    hash = BehaviorResolver_FingerprintU32(
        hash,
        OVERWORLD_WILD_BEHAVIOR_DATA_VERSION);
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->behaviorClass,
        sizeof(result->behaviorClass));
    hash = BehaviorResolver_FingerprintU32(hash, applicableMask);
    hash = BehaviorResolver_FingerprintU32(hash, conditionalMask);
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->profile,
        sizeof(result->profile));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->primitives,
        sizeof(result->primitives));
    result->fingerprint = hash;

    return trace != NULL && trace->dropped != 0
        ? BEHAVIOR_RESOLVE_TRACE_TRUNCATED
        : BEHAVIOR_RESOLVE_OK;
}
