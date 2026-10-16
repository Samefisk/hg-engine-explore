#include "../../include/overworld_behavior_resolver.h"
#include "../../include/overworld_application_bank.h"
#include <stddef.h>
#include "../../include/overworld_behavior_packed_options.h"
#if defined(__arm__)
void OverworldBehaviorPackedOptions_Apply(OverworldWildBehaviorProfileData *, const OverworldWildBehaviorOverrideProfile *, u32);
/* The separate Query imports object supplies one typed odd Thumb pointer. */
#else
#define OverworldBehaviorPackedOptions_Apply OverworldBehaviorPackedOptions_ApplyInline
#endif
#ifdef OVERWORLD_BEHAVIOR_RESOLVER_EXTERNAL_VALIDATOR
#include "../../include/overworld_behavior_condition_runtime.h"
#endif

/* Keep the public resolver within its fixed resident code slot. */
#pragma GCC optimize("Os,no-tree-forwprop,no-inline-small-functions,no-expensive-optimizations,no-if-conversion,no-tree-loop-im,no-schedule-insns2")

#define RESOLVER_MATCH_ANY_SPECIES 0
#define RESOLVER_MATCH_ANY_U8 0xFF
#define RESOLVER_MATCH_LEVEL_ANY 0
#define RESOLVER_GROUP_NONE 0

#define RESOLVER_BEHAVIOR_KIND_NONE 0
#define RESOLVER_BEHAVIOR_KIND_IDLE 1
#define RESOLVER_BEHAVIOR_KIND_WANDER 2
#define RESOLVER_BEHAVIOR_KIND_HEADBUTT_TREE_HOP 7
#define RESOLVER_BEHAVIOR_KIND_ASLEEP 8
#define RESOLVER_BEHAVIOR_KIND_THROW_HELD_ACTOR 12
#define RESOLVER_BEHAVIOR_KIND_MAX 12

#define RESOLVER_LOCOMOTION_NONE 0
#define RESOLVER_LOCOMOTION_WANDER 1
#define RESOLVER_LOCOMOTION_RAM 5
#define RESOLVER_SPAWN_LOCOMOTION_FLY_IN 9
#define RESOLVER_LOCOMOTION_MAX 11

#define RESOLVER_TARGET_NONE 0
#define RESOLVER_TARGET_MAX OW_WILD_BEHAVIOR_TARGET_PLAYER_AWAY_THROW_LINE
#define RESOLVER_TARGET_RANDOM_NEARBY 1
#define RESOLVER_TARGET_TOWARD_PLAYER 2
#define RESOLVER_TARGET_AWAY_FROM_PLAYER 3
#define RESOLVER_TARGET_TREE_TOP 4

#define RESOLVER_ALERT_SPECIAL_NONE 0
#define RESOLVER_ALERT_SPECIAL_CALL_FOR_HELP 1

#define RESOLVER_REACTION_TIRED 5

#define RESOLVER_SPAWN_STATE_APPEAR 0
#define RESOLVER_SPAWN_STATE_APPEAR_HOP 3
#define RESOLVER_SPAWN_STATE_FLY_IN 4
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
#define RESOLVER_WALK_ACCELERATION_DIVIDE_BY_2 33
#define RESOLVER_WALK_ACCELERATION_LINEAR_SPEED 34

#define RESOLVER_OVERRIDE_LIMIT_KEY_BASE OWBD_CLASS_PROFILE_COUNT
#define RESOLVER_MASKABLE_APPLICATION_COUNT \
    ((OWBD_OVERRIDE_PROFILE_COUNT < OWBD_MASKABLE_APPLICATION_COUNT) \
        ? OWBD_OVERRIDE_PROFILE_COUNT : OWBD_MASKABLE_APPLICATION_COUNT)
#define RESOLVER_RESERVED_OVERRIDE_MASK1 \
    ((1u << 1) | (1u << 4) | (1u << 14) | (1u << 16) | 0xF8000000u)

#if defined(__arm__)
#define RESOLVER_SECTION(name) __attribute__((section(name)))
#else
#define RESOLVER_SECTION(name)
#endif

static const u8 sRelativeFieldMaximums[] = {
    0, 0, 0, 255, 64, 64, 64, 32, 64, 0, 0, 0, 0, 0, 0, 0, 100, 0, 0,
    0, 12, 12, 255, 64, 255, 0, 10, 8, 8, 32, 255, 0, 0, 0, 64, 32, 32,
    15, 64, 15, 0, 0, 32, 255, 0, 0, 255, 255, 255, 32, 0, 0, 0, 8, 8, 8,
    32, 5, 0, 0, 0, 0, 0, 0, 255, 32, 32, 33, 32, 32, 0, 0,
    0, 0,
};

static const u8 sSpawnLocomotion[]
    RESOLVER_SECTION(".overworld_actor_tail_constants") = {
        0, 3, 4, 7, RESOLVER_SPAWN_LOCOMOTION_FLY_IN,
    };
static const u8 sDefaultTarget[]
    RESOLVER_SECTION(".overworld_condition_adapter_constants") = {
    RESOLVER_TARGET_NONE,
    RESOLVER_TARGET_NONE,
    RESOLVER_TARGET_RANDOM_NEARBY,
    RESOLVER_TARGET_TOWARD_PLAYER,
    RESOLVER_TARGET_AWAY_FROM_PLAYER,
    RESOLVER_TARGET_TOWARD_PLAYER,
    RESOLVER_TARGET_TOWARD_PLAYER,
    RESOLVER_TARGET_TREE_TOP,
};
/* Reuse the target-selector slot's five unused constant bytes. All entries
 * and state boundaries stay fixed; values match the legacy destination enum. */
static const u8 sLegacySpawnDestinationMask[]
    RESOLVER_SECTION(".overworld_actor_target_constants") = {
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY,
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND,
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS,
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER,
    OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER,
};
#undef RESOLVER_SECTION
/* The appended gait controls support replace only and use a packed merge. */
typedef char BehaviorResolverRelativeFieldCountMustCoverLegacyFields[
    sizeof(sRelativeFieldMaximums) == 74 ? 1 : -1];
typedef char BehaviorResolverProfileDataSizeMustRemain80[
    sizeof(OverworldWildBehaviorProfileData) == 80 ? 1 : -1];
typedef char BehaviorResolverProfileSizeMustRemain160[
    sizeof(OverworldWildBehaviorProfile) == 160 ? 1 : -1];

static u8 BehaviorResolver_FieldOffset(u8 fieldIndex)
{
    if (fieldIndex >= 72) {
        return fieldIndex + 1;
    }
    if (fieldIndex == 70 || fieldIndex == 71) {
        return 69;
    }
    if (fieldIndex == 69) {
        return 63;
    }
    if (fieldIndex == 68) {
        return 64;
    }
    if (fieldIndex < 34) {
        return fieldIndex;
    }
    return fieldIndex < 52 ? fieldIndex + 2 : fieldIndex + 4;
}

static u8 BehaviorResolver_ReadFieldValue(
    const OverworldWildBehaviorProfileData *profile,
    u8 fieldIndex,
    u8 offset)
{
    const u8 *bytes = (const u8 *)profile;

    if (fieldIndex == 53) {
        return OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMP_COUNT(bytes[offset]);
    }
    if (fieldIndex == 59) {
        return OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOWS_CARDINAL(bytes[offset]);
    }
    if (fieldIndex == 60) {
        return OW_WILD_BEHAVIOR_CHAIN_REPOSITION_ALLOWS_DIAGONAL(bytes[offset]);
    }
    if (fieldIndex == 68) {
        return OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE(bytes[offset]);
    }
    if (fieldIndex == 69) {
        return OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE(bytes[offset]);
    }
    if (fieldIndex == 65) {
        return OW_WILD_BEHAVIOR_TILES_BEFORE_TURN_SKID(bytes[offset]);
    }
    if (fieldIndex == 70) {
        return OW_WILD_BEHAVIOR_STOPS_WITH_SKID(bytes[offset]);
    }
    if (fieldIndex == 71) {
        return OW_WILD_BEHAVIOR_PLANS_TURN_SKID_PATH(bytes[offset]);
    }
    return bytes[offset];
}

static void BehaviorResolver_WriteFieldValue(
    OverworldWildBehaviorProfileData *profile,
    u8 fieldIndex,
    u8 offset,
    u8 value)
{
    u8 *bytes = (u8 *)profile;

    if (fieldIndex == 53) {
        OW_WILD_BEHAVIOR_SET_CHAIN_REPOSITION_JUMP_COUNT(bytes[offset], value);
    } else if (fieldIndex == 59) {
        OW_WILD_BEHAVIOR_SET_CHAIN_REPOSITION_ALLOW_CARDINAL(bytes[offset], value);
    } else if (fieldIndex == 60) {
        OW_WILD_BEHAVIOR_SET_CHAIN_REPOSITION_ALLOW_DIAGONAL(bytes[offset], value);
    } else if (fieldIndex == 68) {
        OW_WILD_BEHAVIOR_SET_WALK_TIME_VARIANCE(bytes[offset], value);
    } else if (fieldIndex == 69) {
        OW_WILD_BEHAVIOR_SET_WALK_PAUSE_VARIANCE(bytes[offset], value);
    } else if (fieldIndex == 65) {
        OW_WILD_BEHAVIOR_SET_TILES_BEFORE_TURN_SKID(bytes[offset], value);
    } else if (fieldIndex == 70) {
        OW_WILD_BEHAVIOR_SET_STOP_SKID(bytes[offset], value);
    } else if (fieldIndex == 71) {
        OW_WILD_BEHAVIOR_SET_PLAN_TURN_SKID_PATH(bytes[offset], value);
    } else {
        bytes[offset] = value;
    }
}

static int BehaviorResolver_RelativeFieldValue(u8 fieldIndex, u8 value)
{
    if (fieldIndex == 53) {
        return (s8)(value << 4) >> 4;
    }
    if (fieldIndex == 68 || fieldIndex == 69) {
        return (value & 0x40) != 0 ? (int)value - 0x80 : value;
    }
    return (s8)value;
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
    if (destination >= OW_WILD_SPAWN_DESTINATION_CANOPY
        && destination <= OW_WILD_SPAWN_DESTINATION_WATER) {
        return sLegacySpawnDestinationMask[
            destination - OW_WILD_SPAWN_DESTINATION_CANOPY];
    }
    return OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_LAND
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY
        | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_GRASS;
}

static void BehaviorResolver_ResolveInheritedPolicies(
    OverworldWildBehaviorProfileData *profile)
{
    u16 terrainOverride = profile->chillAllowedTerrainOverrideMask
        & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_POLICY_ALL;
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
    const OverworldWildBehaviorOverrideProfile *overrideProfile,
    u32 mask,
    u8 fieldIndex)
{
    u8 word = fieldIndex == 0 ? 0 : fieldIndex == 27 ? 1 : 2;
    const u8 *operators = (const u8 *)overrideProfile
        + offsetof(OverworldWildBehaviorOverrideProfile, relativeMask)
        + word * sizeof(u32);
    u32 relativeMask = *(const u32 *)operators;
    u32 atLeastMask = *(const u32 *)(operators + 3 * sizeof(u32));
    u32 atMostMask = *(const u32 *)(operators + 6 * sizeof(u32));
    /* Positive minima: 7, 27..28, 48..53 and 56..57. */
    u32 minimumMask = word == 0 ? 1u << 7 : word == 1 ? 3 : 0xCFC0;

    /* Calls start at 0, 27 or 42. A u32 mask exhausts after 32 shifts,
     * so even the last word can visit only field indices through 73. */
    while (mask != 0) {
        if (mask & 1u) {
            u8 offset = BehaviorResolver_FieldOffset(fieldIndex);
            u8 current = BehaviorResolver_ReadFieldValue(
                profile, fieldIndex, offset);
            u8 value = BehaviorResolver_ReadFieldValue(
                &overrideProfile->profile, fieldIndex, offset);

            /* Linear is a mode, not an arithmetic frame amount. Only an
             * exact replacement may enter or leave it. Retained legacy
             * numeric masks must not accidentally select the new mode. */
            if (fieldIndex == 67
                && current == RESOLVER_WALK_ACCELERATION_LINEAR_SPEED
                && ((relativeMask | atLeastMask | atMostMask) & 1u)) {
                goto nextField;
            }
            if ((relativeMask | (atLeastMask & atMostMask)) & 1u) {
                u8 divide = (atLeastMask & atMostMask) & 1u;
                int adjusted;
                int minimum = minimumMask & 1u;
                int maximum = sRelativeFieldMaximums[fieldIndex];

                /* The previously invalid double-bound spelling selects /N.
                 * Share the numeric clamp and packed write with relative. */
                if (divide) {
                    /* The caller removes retired/gait mask1 bits. Of the
                     * remaining numeric maxima, only skid and the legacy
                     * acceleration mode are replace-only; sway has max7. */
                    if ((relativeMask & 1u)
                        || (!maximum && fieldIndex != 44)
                        || fieldIndex == 65 || fieldIndex == 67
                        || (u8)(value - 1) > 126) {
                        goto nextField;
                    }
#if defined(__arm__)
                    adjusted = ((u32 (*)(u32, u32))0x023DEE4D)(current, value);
#else
                    adjusted = current / value;
#endif
                    if (fieldIndex == 5 || fieldIndex == 6) maximum = 255;
                    if (fieldIndex == 39) maximum = 8;
                    if (fieldIndex == 44) maximum = 7;
                } else {
                    adjusted = (int)current
                        + BehaviorResolver_RelativeFieldValue(fieldIndex, value);
                }
                if (adjusted < minimum) {
                    adjusted = minimum;
                } else if (adjusted > maximum) {
                    adjusted = maximum;
                }
                current = (u8)adjusted;
                if (divide) {
                    value = current;
                    goto writeField;
                }
            }
            if ((atLeastMask & 1u) || (atMostMask & 1u)) {
                u8 threshold = (relativeMask & 1u)
                    ? BehaviorResolver_ReadFieldValue(
                        &overrideProfile->compoundBoundProfile, fieldIndex, offset)
                    : value;

                if (fieldIndex == 67
                    && threshold > RESOLVER_WALK_ACCELERATION_DIVIDE_BY_2) {
                    threshold = RESOLVER_WALK_ACCELERATION_DIVIDE_BY_2;
                }
                if ((atLeastMask & 1u) && current < threshold) {
                    current = threshold;
                } else if ((atMostMask & 1u)
                    && current > threshold) {
                    current = threshold;
                }
                value = current;
            } else if (relativeMask & 1u) {
                value = current;
            }
writeField:
            BehaviorResolver_WriteFieldValue(profile, fieldIndex, offset, value);
        }
nextField:
        mask >>= 1;
        relativeMask >>= 1;
        atLeastMask >>= 1;
        atMostMask >>= 1;
        minimumMask >>= 1;
        fieldIndex++;
    }
}

static void BehaviorResolver_ApplyOverride(
    OverworldWildBehaviorProfileData *profile,
    const OverworldWildBehaviorOverrideProfile *overrideProfile)
{
    u16 explicitDestinationMask;
    u16 explicitTerrainMask;
    u32 mask = overrideProfile->mask & ~RESOLVER_RESERVED_OVERRIDE_MASK1;
    u32 mask2 = overrideProfile->mask2;
    u32 mask3 = overrideProfile->mask3;
    u32 authoredMask = overrideProfile->mask;
    u32 throwMask = mask2 >> 17;
    u8 throwField;
    u32 knockbackMask;
    /* Expand the four independent replace-mask bits into their two-bit
     * storage slices. Numeric operators never apply to gait controls. */
    u8 gaitMask = (((authoredMask >> 16) & 1)
        | ((authoredMask >> 25) & 4)
        | ((authoredMask >> 24) & 16)
        | ((authoredMask >> 23) & 64)) * 3;

    profile->mountBounce ^= (profile->mountBounce
        ^ overrideProfile->profile.mountBounce) & gaitMask;

    BehaviorResolver_ApplyMask(profile, overrideProfile, mask, 0);
    BehaviorResolver_ApplyMask(
        profile,
        overrideProfile,
        mask2 & ~(OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE2_CONTINUE_WHEN_ARRIVED
            | OW_WILD_BEHAVIOR_OVERRIDE2_AVOID_PREVIOUS_TILE
            | OW_WILD_BEHAVIOR_OVERRIDE2_RETURN_AFTER_MOVE
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_EXTRA_HOPS
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_EXTRA_CHANCE
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_HEART_CHANCE
            | OW_WILD_BEHAVIOR_OVERRIDE2_CHAIN_HOP_IN_PLACE_CRY_CHANCE
            | OW_WILD_BEHAVIOR_OVERRIDE2_CARGO_TARGET_CHECK_INTERVAL
            | OW_WILD_BEHAVIOR_OVERRIDE2_CARGO_TARGET_SWITCH_ADVANTAGE
            | OW_WILD_BEHAVIOR_OVERRIDE2_ATTACKING
            | OW_WILD_BEHAVIOR_OVERRIDE2_DAMAGE_RECIPIENTS
            | OW_WILD_BEHAVIOR_OVERRIDE2_ON_REACH_ACTION
            | OW_WILD_BEHAVIOR_OVERRIDE2_THROW_MAX_RANGE
            | OW_WILD_BEHAVIOR_OVERRIDE2_THROW_WINDUP_FRAMES
            | OW_WILD_BEHAVIOR_OVERRIDE2_THROW_RECOVERY_FRAMES
            | OW_WILD_BEHAVIOR_OVERRIDE2_KNOCKBACK_TYPE
            | OW_WILD_BEHAVIOR_OVERRIDE2_KNOCKBACK_DISTANCE
            | OW_WILD_BEHAVIOR_OVERRIDE2_TURN_SKID_TWO_TIME
            | OW_WILD_BEHAVIOR_OVERRIDE2_STOP_SKID_TIME),
        27);
    if (mask2 & OW_WILD_BEHAVIOR_OVERRIDE2_CHILL_ALLOWED_TERRAIN_OVERRIDE_MASK) {
        explicitTerrainMask =
            overrideProfile->profile.chillAllowedTerrainOverrideMask
            & OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_POLICY_ALL;
        profile->chillAllowedTerrainMask =
            (profile->chillAllowedTerrainMask & ~explicitTerrainMask)
            | (overrideProfile->profile.chillAllowedTerrainMask
                & explicitTerrainMask);
    }
    BehaviorResolver_ApplyMask(
        profile,
        overrideProfile,
        mask3 & ~(OW_WILD_BEHAVIOR_OVERRIDE3_HOP_ALLOW_VERTICAL_OBSTACLES
            | OW_WILD_BEHAVIOR_OVERRIDE3_CHAIN_REPOSITION_DUST
            | OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_MASK
            | OW_WILD_BEHAVIOR_OVERRIDE3_SPAWN_DESTINATION_OVERRIDE_MASK),
        42);
    if (mask2 & OW_WILD_BEHAVIOR_OVERRIDE2_ATTACKING) {
        profile->attacking = overrideProfile->profile.attacking;
    }
    knockbackMask = (((mask2 >> 20) & 1u) * 0x03)
        | ((((mask2 >> 19) & 0x04) | ((mask2 >> 17) & 0x20)) * 7);
    OverworldBehaviorPackedOptions_Apply(profile, overrideProfile, knockbackMask);
    for (throwField = 1; throwField < 4; throwField++, throwMask >>= 1) {
        if ((throwMask & 1u) != 0) {
            (&profile->onReachAction)[throwField] =
                (&overrideProfile->profile.onReachAction)[throwField];
        }
    }
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
            profile->spawnDestination == OW_WILD_SPAWN_DESTINATION_POOL
                ? 0
                : OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_ALL;
    }
}

static inline __attribute__((always_inline)) u32 BehaviorResolver_ClampWalkTime(u32 value)
{
#if defined(__arm__)
    /* Keep the exact unsigned 1..32 clamp local in the fixed native slot. */
    __asm__(".syntax unified\ncmp %0,#0\nbne 1f\nmovs %0,#1\n"
        "1:\ncmp %0,#32\nbls 2f\nmovs %0,#32\n2:\n.syntax divided\n"
        : "+l"(value) : : "cc");
    return value;
#else
    if (value < RESOLVER_WALK_TIME_MIN) {
        return RESOLVER_WALK_TIME_MIN;
    }
    if (value > RESOLVER_WALK_TIME_MAX) {
        return RESOLVER_WALK_TIME_MAX;
    }
    return value;
#endif
}

static __attribute__((optimize("Os,tree-forwprop,tree-dominator-opts,expensive-optimizations,if-conversion")))
void BehaviorResolver_NormalizeLane(
    OverworldWildBehaviorProfileData *profile,
    u8 invalidState)
{
    u32 speed = BehaviorResolver_ClampWalkTime(profile->chillSpeed);
    u32 maximum = BehaviorResolver_ClampWalkTime(profile->maxWalkSpeed);

    if (maximum > speed) {
        maximum = speed;
    }
    profile->chillSpeed = (u8)speed;
    profile->maxWalkSpeed = (u8)maximum;
    profile->chainRepositionSpeed = BehaviorResolver_ClampWalkTime(
        profile->chainRepositionSpeed);
    {
        u32 counts = profile->chainRepositionJumpCount;
#if defined(__arm__)
        u32 low;

        /* Preserve both independent slices with one bounded byte update. */
        __asm__(".syntax unified\nmovs %1,#15\nands %1,%0\nbne 1f\n"
            "adds %0,#1\nb 2f\n"
            "1:\ncmp %1,#8\nbls 2f\nmovs %1,#15\nbics %0,%1\nadds %0,#8\n"
            "2:\nmovs %1,#48\nands %1,%0\ncmp %1,#48\nbne 3f\nsubs %0,#16\n3:\n.syntax divided\n"
            : "+l"(counts), "=&l"(low) : : "cc");
#else
        u32 reposition = OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMP_COUNT(counts);

        if (reposition == 0) {
            counts |= 1u;
        } else if (reposition > OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMPS_MAX) {
            counts = (counts & ~15u) | OW_WILD_BEHAVIOR_CHAIN_REPOSITION_JUMPS_MAX;
        }
        if ((counts & 0x30u) == 0x30u) {
            counts ^= 0x10u;
        }
#endif
        profile->chainRepositionJumpCount = (u8)counts;
    }
#if defined(__arm__)
    {
        u32 options = profile->avoidPreviousTile;

        /* LSRS retains the independent low bit in carry for the 100 clamp. */
        __asm__(".syntax unified\ncmp %0,#201\nbls 1f\nlsrs %0,#1\n"
            "movs %0,#100\nadcs %0,%0\n1:\n.syntax divided\n"
            : "+l"(options) : : "cc");
        profile->avoidPreviousTile = (u8)options;
    }
#else
    if (OW_WILD_BEHAVIOR_CHAIN_HOP_IN_PLACE_EXTRA_CHANCE(
            profile->avoidPreviousTile) > 100) {
        OW_WILD_BEHAVIOR_SET_CHAIN_HOP_IN_PLACE_EXTRA_CHANCE(
            profile->avoidPreviousTile, 100);
    }
#endif
    if (profile->chaseBoostSpeed > RESOLVER_WALK_TIME_MAX) {
        profile->chaseBoostSpeed = RESOLVER_WALK_TIME_MAX;
    }
    if (profile->walkStompTime > RESOLVER_WALK_TIME_MAX) {
        profile->walkStompTime = RESOLVER_WALK_TIME_MAX;
    }
    if (profile->walkAccelerationStep > RESOLVER_WALK_ACCELERATION_LINEAR_SPEED) {
        profile->walkAccelerationStep = RESOLVER_WALK_ACCELERATION_DIVIDE_BY_2;
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
    if (profile->hopAllowNonCardinal > OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_MAX) {
        profile->hopAllowNonCardinal =
            OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_CARDINAL_ONLY;
    }
    if (OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE(profile->chainRepositionAllowDiagonal)
        > OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MAX) {
        OW_WILD_BEHAVIOR_SET_WALK_TIME_VARIANCE(
            profile->chainRepositionAllowDiagonal,
            OW_WILD_BEHAVIOR_WALK_TIME_VARIANCE_MAX);
    }
    if (OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE(profile->chainRepositionAllowCardinal)
        > OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MAX) {
        OW_WILD_BEHAVIOR_SET_WALK_PAUSE_VARIANCE(
            profile->chainRepositionAllowCardinal,
            OW_WILD_BEHAVIOR_WALK_PAUSE_VARIANCE_MAX);
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
    } else if (profile->walkAccelerationStep != RESOLVER_WALK_ACCELERATION_LINEAR_SPEED
        && profile->tilesToAccelerate > RESOLVER_MOVEMENT_RANGE) {
        profile->tilesToAccelerate = RESOLVER_MOVEMENT_RANGE;
    }
    if (profile->chainPauseAction
            > OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_FORWARD
        && profile->chainPauseAction
            <= OW_WILD_BEHAVIOR_CHAIN_PAUSE_RANDOM_CHOICE) {
        profile->chainPauseAction = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE;
    }
    if (profile->circleRadius > RESOLVER_CIRCLE_RADIUS_MAX) {
        profile->circleRadius = RESOLVER_CIRCLE_RADIUS_MAX;
    }
    if (profile->battleTrigger > RESOLVER_BATTLE_TRIGGER_MAX) {
        profile->battleTrigger = RESOLVER_TARGET_NONE;
    }
    profile->attacking = profile->attacking == 1;
#if defined(__arm__)
    {
        u32 options = profile->knockbackOptions;
        u32 slice;

        /* Type 3 becomes None; distance 0 becomes 1, preserving other bits. */
        __asm__(".syntax unified\nmovs %1,#3\nands %1,%0\ncmp %1,#3\n"
            "bne 1f\nbics %0,%1\n1:\nmovs %1,#28\ntst %0,%1\n"
            "bne 2f\nadds %0,#4\n2:\n.syntax divided\n"
            : "+l"(options), "=&l"(slice) : : "cc");
        profile->knockbackOptions = (u8)options;
    }
#else
    if (OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(profile->knockbackOptions)
            > OW_WILD_BEHAVIOR_KNOCKBACK_JUMP) {
        OW_WILD_BEHAVIOR_SET_KNOCKBACK_TYPE(
            profile->knockbackOptions, OW_WILD_BEHAVIOR_KNOCKBACK_NONE);
    }
    if (OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(profile->knockbackOptions) < 1) {
        OW_WILD_BEHAVIOR_SET_KNOCKBACK_DISTANCE(profile->knockbackOptions, 1);
    } else if (OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(profile->knockbackOptions) > 7) {
        OW_WILD_BEHAVIOR_SET_KNOCKBACK_DISTANCE(profile->knockbackOptions, 7);
    }
#endif
    if (profile->collisionDamage > 50) {
        profile->collisionDamage = 50;
    }
    if ((profile->onReachAction & 0x3Eu) != 0) {
        profile->onReachAction &= 0xC0u;
    }
    if (profile->throwMaxRange > 8) {
        profile->throwMaxRange = 8;
    }
}

static void BehaviorResolver_NormalizeProfile(
    OverworldWildBehaviorProfile *profile)
{
    BehaviorResolver_NormalizeLane(&profile->owner, RESOLVER_BEHAVIOR_KIND_IDLE);
    BehaviorResolver_NormalizeLane(&profile->tired, RESOLVER_BEHAVIOR_KIND_NONE);

    if (profile->alertSpecialAction > RESOLVER_ALERT_SPECIAL_CALL_FOR_HELP) {
        profile->alertSpecialAction = RESOLVER_ALERT_SPECIAL_NONE;
    }
    if (profile->overworldLimit > RESOLVER_MAX_OVERWORLD_ACTORS) {
        profile->overworldLimit = RESOLVER_MAX_OVERWORLD_ACTORS;
    }
    if (profile->chillState == RESOLVER_BEHAVIOR_KIND_ASLEEP) {
        profile->tiredState = RESOLVER_BEHAVIOR_KIND_ASLEEP;
        profile->stamina = 1;
    } else if (profile->tiredState == RESOLVER_BEHAVIOR_KIND_ASLEEP) {
        profile->stamina = 1;
    }
    if (profile->tiredState != RESOLVER_BEHAVIOR_KIND_NONE
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
    if (profile->spawnState > RESOLVER_SPAWN_STATE_FLY_IN) {
        profile->spawnState = RESOLVER_SPAWN_STATE_APPEAR;
    }
    if (profile->alertEmote > RESOLVER_BUBBLE_ID_SLEEP
        && profile->alertEmote != RESOLVER_BUBBLE_ID_NONE) {
        profile->alertEmote = RESOLVER_BUBBLE_ID_NONE;
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
        /* Release consumes its explicit target without carrier locomotion. */
        if (behaviorKind != RESOLVER_BEHAVIOR_KIND_THROW_HELD_ACTOR) {
            *target = RESOLVER_TARGET_NONE;
        }
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

static const OverworldWildBehaviorDataBlobHeader sExpectedBlobHeader = {
    .magic = OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC,
    .version = OVERWORLD_WILD_BEHAVIOR_DATA_VERSION,
    .headerSize = sizeof(OverworldWildBehaviorDataBlobHeader),
    .blobSize = sizeof(OverworldWildBehaviorDataBlob),
    .classProfilesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, classProfiles),
    .classProfileCount = OWBD_CLASS_PROFILE_COUNT,
    .classProfileSize = sizeof(OverworldWildBehaviorProfileData),
    .classRulesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, classRules),
    .classRuleCount = OWBD_CLASS_RULE_COUNT,
    .classRuleSize = sizeof(OverworldWildBehaviorClassRule),
    .speciesClassRulesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, speciesClassRules),
    .speciesClassRuleCount = OWBD_SPECIES_CLASS_RULE_COUNT,
    .speciesClassRuleSize = sizeof(OverworldWildBehaviorSpeciesClassRule),
    .overrideProfilesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, overrideProfiles),
    .overrideProfileCount = OWBD_OVERRIDE_PROFILE_COUNT,
    .overrideProfileSize = sizeof(OverworldWildBehaviorOverrideProfile),
    .overrideMembersOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, overrideMembers),
    .overrideMemberCount = OWBD_OVERRIDE_MEMBER_COUNT,
    .overrideMemberSize = sizeof(u16),
    .conditionEntriesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, conditionEntries),
    .conditionEntryCount = OWBD_CONDITION_ENTRY_COUNT,
    .conditionEntrySize = sizeof(OverworldWildBehaviorConditionEntry),
    .surfaceModelsOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceModels),
    .surfaceModelCount = OWBD_SURFACE_MODEL_COUNT,
    .surfaceModelSize = sizeof(OverworldWildSurfaceModelDirectoryEntry),
    .surfaceInstancesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceInstances),
    .surfaceInstanceCount = OWBD_SURFACE_INSTANCE_COUNT,
    .surfaceInstanceSize = sizeof(OverworldWildSurfaceInstance),
    .surfaceTemplatesOffset =
        __builtin_offsetof(OverworldWildBehaviorDataBlob, surfaceTemplates),
    .surfaceTemplateCount = OWBD_SURFACE_TEMPLATE_COUNT,
    .surfaceTemplateSize = sizeof(OverworldWildSurfaceTemplate),
};

static BOOL BehaviorResolver_BlobValid(
    const OverworldWildBehaviorDataBlob *blob,
    u32 blobSize)
{
    const u8 *actual;
    const u8 *expected = (const u8 *)&sExpectedBlobHeader;
    u8 i;

    if (blob == NULL
        || blobSize < sizeof(*blob)) {
        return FALSE;
    }
    actual = (const u8 *)&blob->header;
    for (i = 0; i < sizeof(sExpectedBlobHeader); i++) {
        if (actual[i] != expected[i]) {
            return FALSE;
        }
    }
    /* Every bank row is bounded; no global profile is hidden because its
     * ordinal exceeds the width of one subject's public mask. */
    if (blob->applicationBankDirectory[
            OWBD_APPLICATION_BANK_DIRECTORY_COUNT - 1].species != 0xFFFF)
        return FALSE;
    return TRUE;
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

#ifndef OVERWORLD_BEHAVIOR_RESOLVER_EXTERNAL_VALIDATOR
static BOOL BehaviorResolver_ConditionMatches(
    const OverworldWildBehaviorDataBlob *blob,
    u16 application,
    u16 conditionId,
    u8 targetKind,
    BOOL checkTargetKind)
{
    const OverworldWildBehaviorOverrideProfile *profile;
    u16 end;
    u16 i;

    if (application >= blob->header.overrideProfileCount
        || conditionId == BEHAVIOR_RESOLVER_NO_CONDITION) {
        return FALSE;
    }
    profile = &blob->overrideProfiles[application];
    end = (u16)(profile->conditionStart + profile->conditionCount);
    if (end > blob->header.conditionEntryCount) {
        return FALSE;
    }
    for (i = profile->conditionStart; i < end; i++) {
        if (blob->conditionEntries[i].conditionId == conditionId
            && (!checkTargetKind
                || blob->conditionEntries[i].targetKind == targetKind)) {
            return TRUE;
        }
    }
    return FALSE;
}

static BOOL BehaviorResolver_RequestValid(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request,
    OverworldApplicationBank *validatedBank)
{
    u32 validOverrideMask;
    u8 winningApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    OverworldApplicationBank selectedBank;
    const OverworldApplicationBank *bank = &selectedBank;
    u16 i;

    if (request == NULL || validatedBank == NULL) {
        return FALSE;
    }
    if (!OverworldApplicationBank_Select(blob, request->context.species, &selectedBank))
        return FALSE;
    validOverrideMask = bank->count == OWBD_MASKABLE_APPLICATION_COUNT
        ? 0xFFFFFFFFu : ((1u << bank->count) - 1u);
    if ((request->forcedOverrideMask & ~validOverrideMask) != 0
        || request->context.level > 100
        || request->context.terrain > OW_WILD_SPAWN_TERRAIN_FISHING
        || request->context.shiny > 1
        || request->requestVersion != BEHAVIOR_RESOLVE_REQUEST_VERSION) {
        return FALSE;
    }
    if ((request->activeConditionalMask & ~validOverrideMask) != 0
        || request->resolvedTarget.kind
            > BEHAVIOR_RESOLVE_TARGET_ACTOR) {
        return FALSE;
    }
    for (i = 0; i < bank->count; i++) {
        u32 bit = 1u << i;

        if ((request->activeConditionalMask & bit) != 0
            && OverworldApplicationBank_Profile(blob, bank, i)->profileKind
                != OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL) {
            return FALSE;
        }
        if (request->activeConditionalMask & bit) {
            winningApplication = (u8)i;
        }
        if ((request->forcedOverrideMask & bit) != 0
            && OverworldApplicationBank_Profile(blob, bank, i)->profileKind
                == OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL) {
            return FALSE;
        }
    }
    if (winningApplication == BEHAVIOR_RESOLVER_NO_APPLICATION) {
        if (request->winningConditionId != BEHAVIOR_RESOLVER_NO_CONDITION) {
            return FALSE;
        }
    } else if (!BehaviorResolver_ConditionMatches(
                   blob,
                   OverworldApplicationBank_Global(bank, winningApplication),
                   request->winningConditionId,
                   0,
                   FALSE)) {
        return FALSE;
    }
    if (request->resolvedTarget.kind
            == BEHAVIOR_RESOLVE_TARGET_NONE) {
        if (request->targetSourceApplication
                == BEHAVIOR_RESOLVER_NO_APPLICATION
            && request->resolvedTargetConditionId
                == BEHAVIOR_RESOLVER_NO_CONDITION) {
            *validatedBank = selectedBank;
            return TRUE;
        }
        return FALSE;
    }
    if (request->targetSourceApplication >= bank->count
        || request->resolvedTargetConditionId
            == BEHAVIOR_RESOLVER_NO_CONDITION
        || (request->activeConditionalMask
            & (1u << request->targetSourceApplication)) == 0) {
        return FALSE;
    }
    if (!BehaviorResolver_ConditionMatches(
        blob,
        OverworldApplicationBank_Global(bank, request->targetSourceApplication),
        request->resolvedTargetConditionId,
        request->resolvedTarget.kind,
        TRUE))
        return FALSE;
    *validatedBank = selectedBank;
    return TRUE;
}
#else
static BOOL BehaviorResolver_RequestValid(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request,
    OverworldApplicationBank *validatedBank)
{
    const OverworldBehaviorConditionServiceEntry *service =
        OVERWORLD_BEHAVIOR_CONDITION_SERVICE_ENTRY;


    return service->magic == OVERWORLD_BEHAVIOR_CONDITION_SERVICE_MAGIC
        && service->version == OVERWORLD_BEHAVIOR_CONDITION_RUNTIME_VERSION
        && service->size == sizeof(*service)
        && service->validateResolveRequest(blob, request, validatedBank);
}
#endif

BehaviorResolveStatus OverworldBehaviorResolver_ValidateRequest(
    const void *blobBytes, u32 blobSize, const BehaviorResolveRequest *request,
    OverworldApplicationBank *bank)
{
    const OverworldWildBehaviorDataBlob *blob = blobBytes;
    if (request == NULL || bank == NULL)
        return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;
    if (!BehaviorResolver_BlobValid(blob, blobSize))
        return BEHAVIOR_RESOLVE_INVALID_BLOB;
    if (request->requestVersion != BEHAVIOR_RESOLVE_REQUEST_VERSION)
        return BEHAVIOR_RESOLVE_UNSUPPORTED_REQUEST_VERSION;
    return BehaviorResolver_RequestValid(blob, request, bank)
        ? BEHAVIOR_RESOLVE_OK : BEHAVIOR_RESOLVE_INVALID_CONTEXT;
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
    OverworldApplicationBank validatedBank;

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
    if (request->requestVersion != BEHAVIOR_RESOLVE_REQUEST_VERSION) {
        return BEHAVIOR_RESOLVE_UNSUPPORTED_REQUEST_VERSION;
    }
    if (!BehaviorResolver_RequestValid(blob, request, &validatedBank)) {
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

/* Keep the profile merge/trace boundary shared by Owner and Tired calls. The
 * four replace-only gait controls must not duplicate this work at each call. */
static __attribute__((noinline)) void BehaviorResolver_ApplyRecorded(
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
    /* Linked Tired rows can follow the 32 maskable applications. Their
     * physical byte index remains available in the trace, not in a mask. */
    if (kind != BEHAVIOR_RESOLUTION_STEP_LANE_REFERENCE
        && index < OWBD_MASKABLE_APPLICATION_COUNT) {
        result->appliedOverrideMask |= 1u << index;
    }
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
    OverworldWildBehaviorProfileData *owner;
    OverworldWildBehaviorProfileData *tired;
    BehaviorClassSelection classSelection;
    OverworldApplicationBank bank;
    u32 applicableMask = 0;
    u32 conditionalMask = 0;
    u8 behaviorClass;
    u16 tiredIndex;
    u16 i;
    u32 hash;

    if (request == NULL || result == NULL) {
        return BEHAVIOR_RESOLVE_INVALID_ARGUMENT;
    }
    memset(result, 0, sizeof(*result));
    owner = &result->profile.owner;
    tired = &result->profile.tired;
    result->winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    result->resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    result->targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    if (trace != NULL) {
        trace->count = 0;
        trace->dropped = 0;
        trace->reserved = 0;
    }
    if (!BehaviorResolver_BlobValid(blob, blobSize)) {
        return BEHAVIOR_RESOLVE_INVALID_BLOB;
    }
    if (request->requestVersion != BEHAVIOR_RESOLVE_REQUEST_VERSION) {
        return BEHAVIOR_RESOLVE_UNSUPPORTED_REQUEST_VERSION;
    }
    if (!BehaviorResolver_RequestValid(blob, request, &bank)) {
        return BEHAVIOR_RESOLVE_INVALID_CONTEXT;
    }

    context = request->context;
    classSelection.matchedClassRuleMask = 0;
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
    tiredIndex = blob->tiredClassGlobalIds[behaviorClass];

    memcpy(owner, &blob->classProfiles[behaviorClass], sizeof(*owner));
    BehaviorResolver_ResolveInheritedPolicies(owner);
    memcpy(tired, owner, sizeof(*tired));
    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_OWNER,
        BEHAVIOR_RESOLUTION_STEP_BASE,
        behaviorClass,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        owner);

    /* Blob validation proved the exact compiled table count. Only this
     * compiled prefix can match, activate, or enter a mask. */
    for (i = 0; i < bank.count; i++) {
        u32 bit = 1u << i;
        BOOL matched = BehaviorResolver_OverrideTargetsContext(
            &context,
            OverworldApplicationBank_Profile(blob, &bank, i),
            blob->overrideMembers,
            blob->header.overrideMemberCount);

        if (matched) {
            result->matchedOverrideMask |= bit;
        }
        if (matched || (request->forcedOverrideMask & bit) != 0) {
            applicableMask |= bit;
        }
    }

    conditionalMask = request->activeConditionalMask;
    for (i = 0; i < bank.count; i++) {
        const OverworldWildBehaviorOverrideProfile *overrideProfile =
            OverworldApplicationBank_Profile(blob, &bank, i);
        u32 bit = 1u << i;
        BOOL conditional = overrideProfile->profileKind
            == OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
        u32 applyMask = conditional ? conditionalMask : applicableMask;
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
        if (conditional) {
            flags |= BEHAVIOR_RESOLUTION_STEP_CONDITIONAL;
        }
        BehaviorResolver_ApplyRecorded(
            owner,
            overrideProfile,
            i,
            BEHAVIOR_RESOLUTION_LANE_OWNER,
            conditional
                ? BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE
                : BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE,
            flags,
            result,
            trace);
        if (overrideProfile->mask3 & OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_PROFILE)
            tiredIndex = blob->tiredOverrideGlobalIds[
                OverworldApplicationBank_Global(&bank, i)];
        if (overrideProfile->mask
            & OW_WILD_BEHAVIOR_OVERRIDE_OVERWORLD_LIMIT) {
            result->behaviorLimitKey = blob->applicationLimitKeys[
                OverworldApplicationBank_Global(&bank, i)];
        }
    }
    result->conditionalOverrideMask = conditionalMask;
    if ((conditionalMask & result->appliedOverrideMask) != 0) {
        result->winningConditionId = request->winningConditionId;
    }
    if (request->resolvedTarget.kind
            != BEHAVIOR_RESOLVE_TARGET_NONE
        && (result->appliedOverrideMask
            & (1u << request->targetSourceApplication)) != 0) {
        result->resolvedTarget = request->resolvedTarget;
        result->resolvedTargetConditionId =
            request->resolvedTargetConditionId;
        result->targetSourceApplication =
            request->targetSourceApplication;
    }

    if (tiredIndex >= blob->header.overrideProfileCount) {
        tiredIndex = OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_REST;
    }

    BehaviorResolver_Trace(
        trace,
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_STEP_BASE,
        behaviorClass,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        tired);

    for (i = 0; i < bank.count; i++) {
        u32 bit = 1u << i;
        u8 flags;

        if ((applicableMask & bit) == 0
            || OverworldApplicationBank_Profile(blob, &bank, i)->profileKind
                != OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL) {
            continue;
        }
        flags = (result->matchedOverrideMask & bit)
                ? BEHAVIOR_RESOLUTION_STEP_MATCHED
                : 0;
        if (request->forcedOverrideMask & bit) {
            flags |= BEHAVIOR_RESOLUTION_STEP_FORCED;
        }
        if (OverworldApplicationBank_Global(&bank, i) != tiredIndex) {
            BehaviorResolver_ApplyRecorded(
                tired,
                OverworldApplicationBank_Profile(blob, &bank, i),
                i,
                BEHAVIOR_RESOLUTION_LANE_TIRED,
                BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE,
                flags,
                result,
                trace);
        }
    }
    BehaviorResolver_ApplyRecorded(
        tired,
        &blob->overrideProfiles[tiredIndex],
        tiredIndex,
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_STEP_LANE_REFERENCE,
        0,
        result,
        trace);
    for (i = 0; i < bank.count; i++) {
        u32 bit = 1u << i;

        if ((conditionalMask & bit) == 0) {
            continue;
        }
        if (OverworldApplicationBank_Global(&bank, i) != tiredIndex) {
            BehaviorResolver_ApplyRecorded(
                tired,
                OverworldApplicationBank_Profile(blob, &bank, i),
                i,
                BEHAVIOR_RESOLUTION_LANE_TIRED,
                BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE,
                BEHAVIOR_RESOLUTION_STEP_CONDITIONAL,
                result,
                trace);
        }
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
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_STEP_NORMALIZE,
        BEHAVIOR_RESOLVER_NO_SOURCE,
        BEHAVIOR_RESOLUTION_STEP_APPLIED,
        &result->profile.tired);
    BehaviorResolver_ResolvePrimitives(&result->profile, &result->primitives);

    hash = 2166136261u;
    hash = BehaviorResolver_FingerprintU32(
        hash,
        OVERWORLD_WILD_BEHAVIOR_SEMANTIC_VERSION);
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->behaviorClass,
        sizeof(result->behaviorClass));
    hash = BehaviorResolver_FingerprintU32(hash, applicableMask);
    hash = BehaviorResolver_FingerprintU32(hash, conditionalMask);
    hash = BehaviorResolver_FingerprintBytes(hash, bank.globalIds,
        (u32)bank.count * sizeof(bank.globalIds[0]));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &request->requestVersion,
        sizeof(request->requestVersion));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->resolvedTarget,
        sizeof(result->resolvedTarget));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->winningConditionId,
        sizeof(result->winningConditionId));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->targetSourceApplication,
        sizeof(result->targetSourceApplication));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->resolvedTargetConditionId,
        sizeof(result->resolvedTargetConditionId));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->profile,
        sizeof(result->profile));
    hash = BehaviorResolver_FingerprintBytes(
        hash,
        &result->primitives,
        sizeof(result->primitives));
    result->fingerprint = hash;
    if (trace != NULL) {
        for (i = 0; i < trace->count; ++i) {
            BehaviorResolutionStep *step = &trace->steps[i];
            if ((step->kind == BEHAVIOR_RESOLUTION_STEP_NORMAL_OVERRIDE
                    || step->kind == BEHAVIOR_RESOLUTION_STEP_CONDITIONAL_OVERRIDE)
                && step->sourceIndex < bank.count)
                step->sourceIndex = bank.globalIds[step->sourceIndex];
        }
    }

    return trace != NULL && trace->dropped != 0
        ? BEHAVIOR_RESOLVE_TRACE_TRUNCATED
        : BEHAVIOR_RESOLVE_OK;
}
