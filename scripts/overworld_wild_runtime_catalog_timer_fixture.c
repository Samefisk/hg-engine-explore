#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define OVERWORLD_WILD_SPAWNS_INTERNAL_H
#define OW_WILD_MAX_SPAWNS 10
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int8_t s8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define TYPES_H

#include "../include/overworld_wild_behavior_data.h"
#define OWBD_VALIDATION_NO_PROJECTION_BUILDER
#include "overworld_wild_behavior_v40_validation_shared.h"
#include "../src/overworld_wild_spawns_overlay/overworld_wild_runtime_sidecars.h"
#include "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_layers_internal.h"

/* Compile the actual overlay-157 accessor implementation and the production
 * overlay-159 resolver into one host binary.  Section GC discards unrelated
 * timer/runtime entry points, so no overlay-158 substitutes participate in
 * this recovery-candidate path. */
#define OW_WILD_RUNTIME_ACCESSOR_HOST_TEST
#include "../src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
#include "../src/overworld_wild_runtime_timers_overlay/overworld_wild_runtime_timers.c"

static const u8 sGeneratedV40Catalog[
    OVERWORLD_WILD_BEHAVIOR_DATA_EXPECTED_SIZE] = {
#include "../data/OverworldWildBehaviorDataV40.generated.inc"
};

static int sChecks;

static void require(BOOL condition, const char *message)
{
    sChecks++;
    if (!condition) {
        fprintf(stderr, "runtime catalog/timer fixture failed: %s\n", message);
        exit(1);
    }
}

typedef struct FixtureMovementProjectionCase {
    u8 semanticRole;
    u8 locomotion;
    u8 target;
    u8 pickupThrowEntry;
    u32 capabilityMask;
    u8 expectedFlags;
} FixtureMovementProjectionCase;

static void verify_movement_projection_flags(void)
{
    static const FixtureMovementProjectionCase cases[] = {
        { OWBD_ROLE_CALM, 0, 0, 0, 0, 0 },
        { OWBD_ROLE_CALM, 0, 0, 1, 0,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL },
        { OWBD_ROLE_CALM, OW_WILD_BEHAVIOR_LOCOMOTION_HOP,
            OW_WILD_BEHAVIOR_TARGET_TREE_TOP, 0, 0,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL },
        { OWBD_ROLE_CALM, OW_WILD_BEHAVIOR_LOCOMOTION_HOP, 0, 0, 0, 0 },
        { OWBD_ROLE_CALM, OW_WILD_BEHAVIOR_LOCOMOTION_RAM, 0, 0, 0,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL },
        { OWBD_ROLE_CALM, OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT,
            0, 0, 0, OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL_PHANTOM },
        { OWBD_ROLE_ATTENTIVE,
            OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT, 0, 0, 0,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE_PHANTOM },
        { OWBD_ROLE_ATTENTIVE, OW_WILD_BEHAVIOR_LOCOMOTION_RAM, 0, 1, 0, 0 },
        { OWBD_ROLE_TIRED, OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT,
            OW_WILD_BEHAVIOR_TARGET_TREE_TOP, 1,
            OW_WILD_RUNTIME_CAP_FRAME_WORK,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE },
        { OWBD_ROLE_CALM, OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT,
            0, 1, OW_WILD_RUNTIME_CAP_FRAME_WORK,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL
                | OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE
                | OW_WILD_RUNTIME_MOVEMENT_PROJECTION_CHILL_PHANTOM },
        { OWBD_ROLE_ATTENTIVE,
            OW_WILD_BEHAVIOR_LOCOMOTION_PHANTOM_TELEPORT, 0, 0,
            OW_WILD_RUNTIME_CAP_FRAME_WORK,
            OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE
                | OW_WILD_RUNTIME_MOVEMENT_PROJECTION_ACTIVE_PHANTOM },
    };
    OverworldWildRuntimeStaticCache staticCache;
    OverworldWildRuntimeEffectiveCache effective;
    size_t i;

    for (i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        memset(&staticCache, 0, sizeof(staticCache));
        memset(&effective, 0, sizeof(effective));
        staticCache.spawnConfiguration.pickupThrowEntry =
            cases[i].pickupThrowEntry;
        effective.semanticRole = cases[i].semanticRole;
        effective.primitives[0] = cases[i].locomotion;
        effective.primitives[1] = cases[i].target;
        effective.capabilityMask = cases[i].capabilityMask;
        require(OverworldWildRuntime_GetMovementProjectionFlags(
                    &staticCache, &effective) == cases[i].expectedFlags,
            "production movement projection flags differ");
    }
}

int main(void)
{
    OverworldWildRuntimeStaticContext context;
    OverworldWildRuntimeStaticComposition composition;
    OverworldWildRuntimeRecoveryCandidate candidate;

    sOverworldWildValidatedV40 = sGeneratedV40Catalog;
    memset(&context, 0, sizeof(context));
    context.species = 56;
    context.groupFlags = 8;
    context.level = 1;
    verify_movement_projection_flags();

    require(OverworldWildRuntime_CopyInstalledStaticComposition(
            &context, NULL, &composition)
            && composition.valid
            && composition.controllerId == 0x3001
            && composition.baseNodeId == 0x3101
            && composition.baseProfileId == 0x2304
            && composition.boundNodeCount == 7
            && composition.semanticRoleMask == 0x7F,
        "actual overlay157 canonical Mankey composition differs");
    require(OverworldWildRuntime_ResolveRecoveryCandidate(
            &context, OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA, &candidate)
            == OW_WILD_RUNTIME_STATUS_OK
            && candidate.definitionId == 0x7004
            && candidate.ownerId == 0x8105
            && candidate.recoveryTransitionId == 0xA003
            && candidate.controllerId == 0x3001
            && candidate.nodeId == 0x3103
            && candidate.profileId == 0x2203
            && candidate.origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_STAMINA
            && candidate.selection
                == OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC
            && candidate.selectorKind
                == OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
            && candidate.semanticRole == OWBD_ROLE_TIRED,
        "actual overlay157-to-overlay159 stamina recovery differs");
    require(OverworldWildRuntime_ResolveRecoveryCandidate(
            &context, OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED, &candidate)
            == OW_WILD_RUNTIME_STATUS_OK
            && candidate.definitionId == 0x7005
            && candidate.ownerId == 0x8107
            && candidate.recoveryTransitionId == 0xA005
            && candidate.controllerId == 0x3001
            && candidate.nodeId == 0x3103
            && candidate.profileId == 0x2203
            && candidate.origin == OW_WILD_RUNTIME_RECOVERY_ORIGIN_BATTLE_FLED
            && candidate.selection
                == OW_WILD_RUNTIME_RECOVERY_SELECTION_AUTHORED_SEMANTIC
            && candidate.selectorKind
                == OW_WILD_RUNTIME_SELECTOR_SEMANTIC_ROLE
            && candidate.semanticRole == OWBD_ROLE_TIRED,
        "actual overlay157-to-overlay159 semantic recovery differs");

    printf("runtime catalog/timer host fixture: %d checks; "
           "stamina=0x7004 semantic=0x%04X transition=0x%04X\n",
        sChecks, candidate.definitionId, candidate.recoveryTransitionId);
    return 0;
}
