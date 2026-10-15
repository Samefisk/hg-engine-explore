"""Host proof for explicit conditional-profile resolver composition."""

from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


HARNESS = r"""
#include <assert.h>
#include <stdlib.h>
#include <string.h>

#include "overworld_behavior_resolver.h"

extern const OverworldWildBehaviorDataBlob gOverworldWildBehaviorDataBlob;

static void ClearApplication(OverworldWildBehaviorOverrideProfile *profile)
{
    memset(profile, 0, sizeof(*profile));
    profile->targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED;
    profile->profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL;
}

static void SetSpeed(
    OverworldWildBehaviorOverrideProfile *profile,
    u8 speed)
{
    profile->mask = OW_WILD_BEHAVIOR_OVERRIDE_CHILL_SPEED;
    profile->profile.chillSpeed = speed;
}

static BehaviorResolveRequest ExplicitRequest(u32 activeMask)
{
    BehaviorResolveRequest request;

    memset(&request, 0, sizeof(request));
    request.context.level = 5;
    request.context.terrain = OW_WILD_SPAWN_TERRAIN_LAND;
    request.behaviorClass = OW_WILD_BEHAVIOR_CLASS_DEFAULT;
    request.activeConditionalMask = activeMask;
    request.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    request.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    return request;
}

static void SetPlayerTarget(
    BehaviorResolveRequest *request,
    u8 application,
    u16 conditionId)
{
    request->resolvedTarget.kind = BEHAVIOR_RESOLVE_TARGET_PLAYER;
    request->targetSourceApplication = application;
    request->resolvedTargetConditionId = conditionId;
}

static void SetActorTarget(
    BehaviorResolveRequest *request,
    u8 application,
    u16 conditionId)
{
    request->resolvedTarget.kind = BEHAVIOR_RESOLVE_TARGET_ACTOR;
    request->resolvedTarget.actorSlot = 4;
    request->resolvedTarget.actorGeneration = 8;
    request->resolvedTarget.fieldEpoch = 12;
    request->resolvedTarget.mapGeneration = 16;
    request->resolvedTarget.encounterGeneration = 20;
    request->targetSourceApplication = application;
    request->resolvedTargetConditionId = conditionId;
}

static void Resolve(
    const OverworldWildBehaviorDataBlob *blob,
    const BehaviorResolveRequest *request,
    BehaviorResolveResult *result,
    BehaviorResolutionTrace *trace)
{
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), request, result, trace) == BEHAVIOR_RESOLVE_OK);
}

int main(void)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    BehaviorResolutionStep steps[96];
    BehaviorResolutionTrace trace = {steps, 96, 0, 0, 0};
    BehaviorResolveRequest request;
    BehaviorResolveResult first;
    BehaviorResolveResult second;
    u16 i;

    assert(blob != NULL);
    assert(sizeof(OverworldWildBehaviorProfileData) == 80);
    assert(sizeof(OverworldWildBehaviorProfile) == 160);
    assert(sizeof(OverworldWildBehaviorPrimitives) == 8);
    assert(sizeof(BehaviorResolveRequest) == 44);
    assert(sizeof(BehaviorResolveResult) == 216);
    assert(BEHAVIOR_RESOLUTION_LANE_OWNER == 0);
    assert(BEHAVIOR_RESOLUTION_LANE_RESERVED == 1);
    assert(BEHAVIOR_RESOLUTION_LANE_TIRED == 2);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    assert(blob->header.overrideProfileCount >= 4);
    assert(blob->header.conditionEntryCount >= 2);
    memset(&request, 0, sizeof(request));
    request.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);
    request = ExplicitRequest(0);
    Resolve(blob, &request, &first, NULL);
    blob->header.version = OVERWORLD_WILD_BEHAVIOR_DATA_VERSION - 1;
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_INVALID_BLOB);
    blob->header.version = OVERWORLD_WILD_BEHAVIOR_DATA_VERSION;
    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        ClearApplication(&blob->overrideProfiles[i]);
    }

    /* Fly In is a spawn primitive. It must not normalize to Appear. */
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].spawnState =
        OW_WILD_BEHAVIOR_SPAWN_STATE_FLY_IN;
    request = ExplicitRequest(0);
    Resolve(blob, &request, &first, NULL);
    assert(first.primitives.spawnLocomotion == 9);
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].spawnState = 0;

    /* Walk sway reused mask3 bit 2. The resolver must no longer discard it
     * as the reserved field that occupied this bit before schema version 80. */
    blob->overrideProfiles[0].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    blob->overrideProfiles[0].match.behaviorClass = 0xFF;
    blob->overrideProfiles[0].mask3 =
        OW_WILD_BEHAVIOR_OVERRIDE3_WALK_SWAY_WIDTH;
    blob->overrideProfiles[0].profile.walkSwayWidth = 4;
    request = ExplicitRequest(0);
    Resolve(blob, &request, &first, NULL);
    assert(first.profile.owner.walkSwayWidth == 4);
    ClearApplication(&blob->overrideProfiles[0]);

    /* normal, conditional, conditional, normal */
    blob->overrideProfiles[0].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    blob->overrideProfiles[0].match.behaviorClass = 0xFF;
    SetSpeed(&blob->overrideProfiles[0], 10);

    blob->overrideProfiles[1].profileKind =
        OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[1].conditionStart = 0;
    blob->overrideProfiles[1].conditionCount = 1;
    SetSpeed(&blob->overrideProfiles[1], 20);
    blob->overrideProfiles[1].mask |= OW_WILD_BEHAVIOR_OVERRIDE_STAMINA;
    blob->overrideProfiles[1].profile.stamina = 41;

    blob->overrideProfiles[2].profileKind =
        OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[2].conditionStart = 1;
    blob->overrideProfiles[2].conditionCount = 1;
    SetSpeed(&blob->overrideProfiles[2], 25);
    blob->overrideProfiles[2].mask |= OW_WILD_BEHAVIOR_OVERRIDE_REST_TIME;
    blob->overrideProfiles[2].profile.restTime = 42;

    blob->overrideProfiles[3].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    blob->overrideProfiles[3].match.behaviorClass = 0xFF;
    SetSpeed(&blob->overrideProfiles[3], 30);

    /* Held actor control lives outside the resolver, so ordinary profile
     * composition has no special held-class branch. */
    request = ExplicitRequest(0);
    Resolve(blob, &request, &first, NULL);
    assert(first.behaviorClass == OW_WILD_BEHAVIOR_CLASS_DEFAULT);
    assert((first.matchedOverrideMask & ((1u << 0) | (1u << 3)))
        == ((1u << 0) | (1u << 3)));
    assert(first.profile.owner.chillSpeed == 30);

    blob->conditionEntries[0].applicationIndex = 1;
    blob->conditionEntries[0].conditionId = 101;
    blob->conditionEntries[0].targetKind =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    blob->conditionEntries[1].applicationIndex = 2;
    blob->conditionEntries[1].conditionId = 102;
    blob->conditionEntries[1].targetKind =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR;

    request = ExplicitRequest(0);
    Resolve(blob, &request, &first, NULL);
    assert(first.profile.owner.chillSpeed == 30);
    assert(first.profile.owner.stamina != 41);
    assert(first.conditionalOverrideMask == 0);

    request = ExplicitRequest(1u << 1);
    request.winningConditionId = 101;
    Resolve(blob, &request, &first, &trace);
    /* This is 30 only when application 3 runs after conditional app 1. */
    assert(first.profile.owner.chillSpeed == 30);
    assert(first.profile.owner.stamina == 41);
    assert(first.conditionalOverrideMask == (1u << 1));
    assert(trace.steps[1].sourceIndex == 0);
    assert(trace.steps[2].sourceIndex == 1);
    assert(trace.steps[3].sourceIndex == 3);

    /* Without the trailing normal write, later conditional app 2 wins. */
    blob->overrideProfiles[3].targetMode =
        OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED;
    request = ExplicitRequest((1u << 1) | (1u << 2));
    request.winningConditionId = 102;
    SetActorTarget(&request, 2, 102);
    Resolve(blob, &request, &first, NULL);
    Resolve(blob, &request, &second, NULL);
    assert(first.profile.owner.chillSpeed == 25);
    assert(first.profile.owner.stamina == 41);
    assert(first.profile.owner.restTime == 42);
    assert(first.resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_ACTOR);
    assert(first.resolvedTarget.actorSlot == 4);
    assert(first.targetSourceApplication == 2);
    assert(first.winningConditionId == 102);
    assert(first.resolvedTargetConditionId == 102);
    assert(first.fingerprint == second.fingerprint);

    /* A later targetless condition changes fields but preserves app 1 target. */
    blob->conditionEntries[1].targetKind =
        OW_WILD_BEHAVIOR_CONDITION_TARGET_NONE;
    request = ExplicitRequest((1u << 1) | (1u << 2));
    request.winningConditionId = 102;
    SetPlayerTarget(&request, 1, 101);
    Resolve(blob, &request, &second, NULL);
    assert(second.profile.owner.chillSpeed == 25);
    assert(second.resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_PLAYER);
    assert(second.targetSourceApplication == 1);
    assert(second.winningConditionId == 102);
    assert(second.resolvedTargetConditionId == 101);
    assert(first.fingerprint != second.fingerprint);

    /* Active bits cannot name normal applications or mismatched targets. */
    request = ExplicitRequest(1u << 0);
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);

    request = ExplicitRequest(0);
    request.requestVersion = 1;
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_UNSUPPORTED_REQUEST_VERSION);
    request.requestVersion = 0;
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_UNSUPPORTED_REQUEST_VERSION);
    request = ExplicitRequest(1u << 1);
    request.winningConditionId = 101;
    SetActorTarget(&request, 1, 101);
    assert(BehaviorResolver_Resolve(
        blob, sizeof(*blob), &request, &first, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);

    free(blob);
    return 0;
}
"""


RELEASE_TARGET_HARNESS = HARNESS[:HARNESS.index("int main(void)")] + r"""
int main(void)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    BehaviorResolveRequest request;
    BehaviorResolveResult result;
    static const u8 defaults[] = {1, 2, 3, 2, 2, 4};
    u16 i;
    assert(blob != NULL);
    assert(sizeof(OverworldWildBehaviorProfileData) == 80);
    assert(sizeof(OverworldWildBehaviorProfile) == 160);
    assert(sizeof(OverworldWildBehaviorPrimitives) == 8);
    assert(sizeof(BehaviorResolveResult) == 216);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    for (i = 0; i < blob->header.overrideProfileCount; ++i) {
        ClearApplication(&blob->overrideProfiles[i]);
    }
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].tiredProfile = 0;
    blob->overrideProfiles[1].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[1].conditionStart = 0;
    blob->overrideProfiles[1].conditionCount = 1;
    blob->overrideProfiles[1].mask = OW_WILD_BEHAVIOR_OVERRIDE_CHILL_STATE
        | OW_WILD_BEHAVIOR_OVERRIDE_CHILL_ACTION | OW_WILD_BEHAVIOR_OVERRIDE_CHILL_TARGET;
    blob->overrideProfiles[1].profile.chillState = OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR;
    /* A release is not a locomotion. A stale Hop cannot survive normalization. */
    blob->overrideProfiles[1].profile.chillAction = 2;
    blob->overrideProfiles[1].profile.chillTarget = OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;
    blob->conditionEntries[0].applicationIndex = 1;
    blob->conditionEntries[0].conditionId = 101;

    /* These are the exact resolver inputs after role/binding admission:
     * Wild Geodude uses the PLAYER Trigger; Follower Mankey uses an ACTOR
     * Trigger. The resolver is role-neutral; this does not prove admission. */
    for (i = 0; i < 2; ++i) {
        request = ExplicitRequest(1u << 1);
        request.context.species = i == 0 ? 74 : 56;
        request.winningConditionId = 101;
        blob->conditionEntries[0].targetKind = i == 0
            ? OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER : OW_WILD_BEHAVIOR_CONDITION_TARGET_ACTOR;
        if (i == 0) SetPlayerTarget(&request, 1, 101);
        else SetActorTarget(&request, 1, 101);
        Resolve(blob, &request, &result, NULL);
        assert(result.profile.owner.chillState == OW_WILD_BEHAVIOR_KIND_THROW_HELD_ACTOR);
        assert(result.profile.owner.chillTarget == OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE);
        assert(result.primitives.chillLocomotion == 0);
        assert(result.primitives.chillTarget == OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE);
        assert(result.primitives.tiredLocomotion == 0);
        assert(result.primitives.tiredTarget == OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE);
        assert(memcmp(&result.resolvedTarget, &request.resolvedTarget,
            sizeof(result.resolvedTarget)) == 0);
        assert(result.targetSourceApplication == 1 && result.resolvedTargetConditionId == 101);
    }

    /* Missing Trigger and explicit target NONE never invent a PLAYER fallback. */
    request = ExplicitRequest(1u << 1);
    request.winningConditionId = 101;
    Resolve(blob, &request, &result, NULL);
    assert(result.primitives.chillTarget == OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE);
    assert(result.resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_NONE);
    assert(result.targetSourceApplication == BEHAVIOR_RESOLVER_NO_APPLICATION);
    blob->overrideProfiles[1].profile.chillTarget = 0;
    Resolve(blob, &request, &result, NULL);
    assert(result.primitives.chillLocomotion == 0 && result.primitives.chillTarget == 0);
    assert(result.primitives.tiredLocomotion == 0 && result.primitives.tiredTarget == 0);
    assert(result.resolvedTarget.kind == BEHAVIOR_RESOLVE_TARGET_NONE);
    ClearApplication(&blob->overrideProfiles[1]);
    request = ExplicitRequest(0);

    /* All ordinary non-movement kinds, including NONE and IDLE, still clear
     * locomotion and target. The exception is exactly ThrowHeldActor12. */
    for (i = 0; i < 12; ++i) {
        if (i >= 2 && i <= 7) continue;
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillState = i;
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillAction = 1;
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillTarget = OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;
        Resolve(blob, &request, &result, NULL);
        assert(result.primitives.chillLocomotion == 0 && result.primitives.chillTarget == 0);
        assert(result.primitives.tiredLocomotion == 0 && result.primitives.tiredTarget == 0);
    }
    /* Existing moving kinds keep their exact defaults and explicit targets. */
    for (i = 2; i <= 7; ++i) {
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillState = i;
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillAction = 1;
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillTarget = 0;
        Resolve(blob, &request, &result, NULL);
        assert(result.primitives.chillLocomotion == 1 && result.primitives.chillTarget == defaults[i-2]);
        assert(result.primitives.tiredLocomotion == 1 && result.primitives.tiredTarget == defaults[i-2]);
        blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillTarget = OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE;
        Resolve(blob, &request, &result, NULL);
        assert(result.primitives.chillLocomotion == 1 && result.primitives.chillTarget == OW_WILD_BEHAVIOR_TARGET_TRIGGER_THROW_LINE);
    }
    free(blob);
    return 0;
}
"""


LINKED_TIRED_HARNESS = HARNESS[:HARNESS.index("int main(void)")] + r"""
int main(void)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    BehaviorResolutionStep steps[96];
    BehaviorResolutionTrace trace = {steps, 96, 0, 0, 0};
    BehaviorResolveRequest request;
    BehaviorResolveResult result;
    BehaviorClassSelection selection;
    const u8 tail = OWBD_MASKABLE_APPLICATION_COUNT;
    const u8 last = OWBD_MASKABLE_APPLICATION_COUNT - 1;
    const u32 lastBit = 1u << last;
    u16 i;
    BOOL foundLink = FALSE;

    assert(blob != NULL);
    assert(OWBD_MASKABLE_APPLICATION_COUNT == 32);
    memcpy(blob, &gOverworldWildBehaviorDataBlob, sizeof(*blob));
    assert(blob->header.overrideProfileCount > tail);
    assert(sizeof(BehaviorResolveRequest) == 44);
    assert(sizeof(BehaviorResolveResult) == 216);
    for (i = 0; i < blob->header.overrideProfileCount; i++) {
        ClearApplication(&blob->overrideProfiles[i]);
    }
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].tiredProfile = tail;
    blob->classProfiles[OW_WILD_BEHAVIOR_CLASS_DEFAULT].chillSpeed = 7;
    blob->overrideProfiles[tail].conditionStart = 255; /* unused with count0 */
    SetSpeed(&blob->overrideProfiles[tail], 25);
    SetSpeed(&blob->overrideProfiles[last], 12);
    blob->overrideProfiles[last].targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    blob->overrideProfiles[last].match.terrain = 0xFF;
    blob->overrideProfiles[last].match.shiny = 0xFF;
    blob->overrideProfiles[last].match.behaviorClass = 0xFF;

    /* Bit31 remains a normal matching application. The physical tail adds
     * only its direct Tired contribution, with no mask bit or Owner change. */
    request = ExplicitRequest(0);
    Resolve(blob, &request, &result, &trace);
    assert(result.profile.owner.chillSpeed == 12);
    assert(result.profile.tired.chillSpeed == 25);
    assert(result.matchedOverrideMask == lastBit);
    assert(result.appliedOverrideMask == lastBit);
    assert(result.conditionalOverrideMask == 0);
    for (i = 0; i < trace.count; i++) {
        if (steps[i].kind == BEHAVIOR_RESOLUTION_STEP_LANE_REFERENCE) {
            assert(steps[i].sourceIndex == tail);
            assert(steps[i].lane == BEHAVIOR_RESOLUTION_LANE_TIRED);
            foundLink = TRUE;
        }
    }
    assert(foundLink);
    blob->overrideProfiles[last].targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED;
    request.forcedOverrideMask = lastBit;
    Resolve(blob, &request, &result, NULL);
    assert(result.profile.owner.chillSpeed == 12);
    assert(result.profile.tired.chillSpeed == 25);
    assert(result.matchedOverrideMask == 0 && result.forcedOverrideMask == lastBit);

    /* Bit31 also remains a valid conditional result slot and target source. */
    blob->overrideProfiles[last].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    blob->overrideProfiles[last].conditionStart = 0;
    blob->overrideProfiles[last].conditionCount = 1;
    blob->conditionEntries[0].applicationIndex = last;
    blob->conditionEntries[0].conditionId = 1337;
    blob->conditionEntries[0].targetKind = OW_WILD_BEHAVIOR_CONDITION_TARGET_PLAYER;
    request = ExplicitRequest(lastBit);
    request.winningConditionId = 1337;
    SetPlayerTarget(&request, last, 1337);
    Resolve(blob, &request, &result, NULL);
    assert(result.profile.owner.chillSpeed == 12 && result.profile.tired.chillSpeed == 12);
    assert(result.conditionalOverrideMask == lastBit);
    assert(result.targetSourceApplication == last);
    SetPlayerTarget(&request, tail, 1337);
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &request, &result, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);
    assert(BehaviorResolver_InspectClass(blob, sizeof(*blob), &request, &selection, NULL)
        == BEHAVIOR_RESOLVE_INVALID_CONTEXT);

    /* Tail rows cannot gain a normal match, condition, or conditional kind. */
    request = ExplicitRequest(0);
    blob->overrideProfiles[tail].targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_ALL;
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &request, &result, NULL)
        == BEHAVIOR_RESOLVE_INVALID_BLOB);
    blob->overrideProfiles[tail].targetMode = OW_WILD_BEHAVIOR_OVERRIDE_TARGET_DISABLED;
    blob->overrideProfiles[tail].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_CONDITIONAL;
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &request, &result, NULL)
        == BEHAVIOR_RESOLVE_INVALID_BLOB);
    blob->overrideProfiles[tail].profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL;
    blob->overrideProfiles[tail].conditionCount = 1;
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &request, &result, NULL)
        == BEHAVIOR_RESOLVE_INVALID_BLOB);
    free(blob);
    return 0;
}
"""


DAMAGE_RECIPIENT_HARNESS = r"""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_behavior_resolver.h"

static BehaviorResolveRequest Request(u16 species, u8 groups, u32 forced)
{
    BehaviorResolveRequest r;
    memset(&r, 0, sizeof(r));
    r.context.species = species;
    r.context.level = 50;
    r.context.groupFlags = groups;
    r.behaviorClass = 0;
    r.forcedOverrideMask = forced;
    r.requestVersion = BEHAVIOR_RESOLVE_REQUEST_VERSION;
    r.winningConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    r.resolvedTargetConditionId = BEHAVIOR_RESOLVER_NO_CONDITION;
    r.targetSourceApplication = BEHAVIOR_RESOLVER_NO_APPLICATION;
    return r;
}

static BehaviorResolveResult Resolve(const OverworldWildBehaviorDataBlob *blob,
    BehaviorResolveRequest request)
{
    BehaviorResolveResult r;
    assert(BehaviorResolver_Resolve(blob, sizeof(*blob), &request, &r, NULL)
        == BEHAVIOR_RESOLVE_OK);
    return r;
}

static void Check(const BehaviorResolveResult *r, u8 speed, u8 recipients)
{
    assert(r->profile.owner.maxWalkSpeed == speed);
    assert(r->profile.tired.maxWalkSpeed == speed);
    assert(OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(r->profile.owner.knockbackOptions) == recipients);
    assert(OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(r->profile.tired.knockbackOptions) == recipients);
}

int main(int argc, char **argv)
{
    OverworldWildBehaviorDataBlob *blob = malloc(sizeof(*blob));
    OverworldWildBehaviorOverrideProfile *override;
    BehaviorResolveResult r;
    FILE *file;
    unsigned i, role, op;
    assert(argc == 2 && blob != NULL);
    file = fopen(argv[1], "rb");
    assert(file != NULL);
    assert(fread(blob, 1, sizeof(*blob), file) == sizeof(*blob));
    assert(fgetc(file) == EOF && fclose(file) == 0);
    /* This is the real current packed Follower/Sprint composition. */
    r = Resolve(blob, Request(234, 4, 1u << OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER));
    printf("packed follower max=%u/%u recipient=%u/%u\n",
        r.profile.owner.maxWalkSpeed, r.profile.tired.maxWalkSpeed,
        OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(r.profile.owner.knockbackOptions),
        OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(r.profile.tired.knockbackOptions));
    fflush(stdout);
    Check(&r, 4, OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_WILD);
    r = Resolve(blob, Request(234, 0, 0));
    Check(&r, 4, OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALL);
    /* A recipient-only layer cannot write the unrelated numeric field.
     * Exercise all role sets and the real max-speed arithmetic owners. */
    for (i = 0; i < blob->header.overrideProfileCount; i++)
        memset(&blob->overrideProfiles[i], 0, sizeof(blob->overrideProfiles[i]));
    blob->classProfiles[0].chillSpeed = 16;
    blob->classProfiles[0].maxWalkSpeed = 4;
    blob->classProfiles[0].knockbackOptions = OW_WILD_BEHAVIOR_KNOCKBACK_OPTIONS(1, 3);
    override = &blob->overrideProfiles[0];
    override->profileKind = OW_WILD_BEHAVIOR_PROFILE_KIND_NORMAL;
    for (role = 0; role <= 7; role++) {
        for (op = 0; op <= 4; op++) {
            u8 expected = op == 0 ? 4 : op == 1 || op == 2 ? 6 : op == 3 ? 3 : 5;
            override->mask2 = OW_WILD_BEHAVIOR_OVERRIDE2_DAMAGE_RECIPIENTS;
            override->profile.knockbackOptions = OW_WILD_BEHAVIOR_COLLISION_OPTIONS(2, 7, role);
            override->mask3 = op == 0 ? 0 : OW_WILD_BEHAVIOR_OVERRIDE3_MAX_WALK_SPEED;
            override->profile.maxWalkSpeed = op == 2 || op == 4 ? 2 : op == 3 ? 3 : 6;
            override->relativeMask3 = op == 2 || op == 4 ? override->mask3 : 0;
            override->atLeastMask3 = 0;
            override->atMostMask3 = op == 3 || op == 4 ? override->mask3 : 0;
            override->compoundBoundProfile.maxWalkSpeed = 5;
            r = Resolve(blob, Request(1, 0, 1));
            Check(&r, expected, role);
            assert(OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(r.profile.owner.knockbackOptions) == 1);
            assert(OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(r.profile.owner.knockbackOptions) == 3);
        }
    }
    free(blob);
    puts("current packed Follower/Wild plus40 recipient/operator compositions pass");
    return 0;
}
"""


def run_resolver_harness(harness, resolver_source=None, arguments=()):
    """Compile the whole production C with its real headers/catalog, not a reducer copy."""
    compiler = shlex.split(os.environ.get("CC", "cc"))
    with tempfile.TemporaryDirectory(prefix="resolver-release-target-") as directory:
        temporary = Path(directory)
        (temporary / "include").symlink_to(ROOT / "include", target_is_directory=True)
        native = temporary / "lib/overworld/overworld_behavior_resolver.c"
        native.parent.mkdir(parents=True)
        native.write_text(resolver_source if resolver_source is not None else (
            ROOT / "lib/overworld/overworld_behavior_resolver.c").read_text())
        source, executable = temporary / "release.c", temporary / "release"
        source.write_text(harness)
        compiled = subprocess.run(compiler + ["-std=c99", "-O2", "-Wall", "-Wextra",
            "-DOVERWORLD_BEHAVIOR_HOST", "-I", str(ROOT / "include"), "-I", str(ROOT / "data"),
            str(native), str(ROOT / "data/OverworldWildBehaviorData.c"), str(source), "-o", str(executable)],
            capture_output=True, text=True)
        completed = subprocess.run([str(executable), *map(str, arguments)], capture_output=True, text=True) if compiled.returncode == 0 else None
        return compiled, completed


class BehaviorResolverConditionTests(unittest.TestCase):
    def test_linked_tired_tail_preserves_mask_capacity(self) -> None:
        compiled, completed = run_resolver_harness(LINKED_TIRED_HARNESS)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_damage_recipient_layer_preserves_current_walk_speed(self) -> None:
        compiled, completed = run_resolver_harness(
            DAMAGE_RECIPIENT_HARNESS,
            arguments=(ROOT / "build/OverworldWildBehaviorData.bin",),
        )
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_throw_release_keeps_explicit_trigger_target(self) -> None:
        compiled, completed = run_resolver_harness(RELEASE_TARGET_HARNESS)
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_explicit_condition_order_targets_and_fingerprint(self) -> None:
        compiler_setting = os.environ.get("CC")
        compiler = shlex.split(compiler_setting) if compiler_setting else []
        if not compiler:
            default_compiler = shutil.which("cc")
            compiler = [default_compiler] if default_compiler else []
        self.assertTrue(compiler, "a host C compiler is required")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "resolver_conditions.c"
            executable = Path(directory) / "resolver_conditions"
            source.write_text(HARNESS, encoding="utf-8")
            command = compiler + [
                "-std=c99",
                "-O2",
                "-Wall",
                "-Wextra",
                "-DOVERWORLD_BEHAVIOR_HOST",
                "-I",
                str(ROOT / "include"),
                "-I",
                str(ROOT / "data"),
                str(ROOT / "lib/overworld/overworld_behavior_resolver.c"),
                str(ROOT / "data/OverworldWildBehaviorData.c"),
                str(source),
                "-o",
                str(executable),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )
            completed = subprocess.run(
                [str(executable)], capture_output=True, text=True
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )


if __name__ == "__main__":
    unittest.main()
