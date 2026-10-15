"""Focused host checks for mounted action adapter target planning."""

from pathlib import Path
import os
import re
import shlex
import struct
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import action_switch_import_contract, function_body


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_mount_action_overlay/overworld_mount_action_overlay.c"
HEADER = ROOT / "include/overworld_mount_action_adapter.h"
WILD_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
MOUNT_SOURCE = ROOT / "src/overworld_mount_overlay/overworld_mount_overlay.c"


STUBS = r'''
#include <stdio.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef short s16;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER 0x8000
#define OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER (1u << 1)
#define OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION 1
#define OW_WILD_FOLLOWER_SLOT 7
typedef struct {
    struct { struct { u16 chillAllowedTerrainMask; } profile; } snapshot;
    void *fieldSystem;
    s16 motionStartX, motionStartY, motionTargetX, motionTargetY;
} OverworldMountRuntimeState;
typedef struct {
    u8 action;
    u8 direction;
    OverworldMountRuntimeState *state;
} OverworldMountActionCall;
static int calls, allowLanding;
static int seenX, seenY, seenFinalX, seenFinalY;
static u16 seenMask;
static BOOL Validate(u16 version, u8 slot, void *fieldSystem, u16 mask,
    int x, int y, int finalX, int finalY) {
    if (version != OVERWORLD_WILD_LANDING_VALUE_SERVICE_VERSION
        || slot != OW_WILD_FOLLOWER_SLOT || fieldSystem == 0) return FALSE;
    calls++;
    seenX = x; seenY = y; seenFinalX = finalX; seenFinalY = finalY;
    seenMask = mask;
    return allowLanding;
}
static struct { BOOL (*validateHopLanding)(u16, u8, void *, u16,
    int, int, int, int); } entry = { Validate };
#define OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY (&entry)
static int OverworldWalkDirectionPolicy_DeltaX(u8 direction) {
    static const signed char values[8] = {0, 0, -1, 1, -1, 1, -1, 1};
    return direction < 8 ? values[direction] : 0;
}
static int OverworldWalkDirectionPolicy_DeltaY(u8 direction) {
    static const signed char values[8] = {-1, 1, 0, 0, -1, -1, 1, 1};
    return direction < 8 ? values[direction] : 0;
}
'''


CASES = r'''
#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; \
} } while (0)
int main(void) {
    OverworldMountRuntimeState state = {0};
    OverworldMountActionCall call = {0};
    int field;
    state.fieldSystem = &field;
    state.snapshot.profile.chillAllowedTerrainMask = 0x1234;
    state.motionStartX = 10;
    state.motionStartY = 20;
    call.state = &state;
    allowLanding = TRUE;

    /* A ledge Hop passes two tiles; a B Jump passes its exact reach. */
    call.action = 2;
    call.direction = 3;
    CHECK(OverworldMountAction_ChainForwardTarget(&call));
    CHECK(state.motionTargetX == 12 && state.motionTargetY == 20);
    CHECK(calls == 1 && seenX == 12 && seenY == 20);
    CHECK(seenFinalX == 12 && seenFinalY == 20);
    /* A cardinal (ledge) Hop must not select one-tile Walk edges. */
    /* Every mount may land in water. */
    CHECK(seenMask == (u16)(0x1234 | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER));

    call.direction = 5;
    CHECK(OverworldMountAction_ChainForwardTarget(&call));
    CHECK(state.motionTargetX == 12 && state.motionTargetY == 18);
    CHECK(calls == 2 && seenX == 12 && seenY == 18);
    CHECK(seenFinalX == 12 && seenFinalY == 18);
    CHECK(seenMask == (u16)(0x1234 | OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_WATER | 0x8000));

    allowLanding = FALSE;
    state.motionTargetX = 77;
    state.motionTargetY = 88;
    call.direction = 3;
    CHECK(!OverworldMountAction_ChainForwardTarget(&call));
    CHECK(calls == 3);
    CHECK(state.motionTargetX == 77 && state.motionTargetY == 88);

    call.direction = 8;
    CHECK(!OverworldMountAction_ChainForwardTarget(&call));
    CHECK(calls == 3);

    allowLanding = TRUE;
    call.action = 4;
    call.direction = 0;
    CHECK(OverworldMountAction_ChainForwardTarget(&call));
    CHECK(state.motionTargetX == 10 && state.motionTargetY == 16);
    CHECK(calls == 4 && seenX == 10 && seenY == 16);
    call.action = 3;
    call.direction = 2;
    CHECK(OverworldMountAction_ChainForwardTarget(&call));
    CHECK(state.motionTargetX == 7 && state.motionTargetY == 20);
    return 0;
}
'''


HOP_STUBS = r'''
#define OVERWORLD_MOTION_HOST
#include "overworld_motion_model.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef signed char s8;
typedef int BOOL;
#define PLAYER_STATE_WALKING 0
#define OVERWORLD_MOUNT_MOTION_NONE 0
#define OVERWORLD_MOUNT_ACTION_FINAL 0
#define OVERWORLD_MOUNT_ACTION_STARTED 1
#define OVERWORLD_MOUNT_ACTION_RETRY 2
#define OVERWORLD_MOUNT_ACTION_START_CHAIN 2
#define OVERWORLD_MOUNT_ACTION_TICK_CHAIN 3
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE 1
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND 2
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_JUMPS 3
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_STEPS 4
#define OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS 5
#define OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT 7
#define OVERWORLD_ACTOR_LOOK_FIRST 0
#define OVERWORLD_ACTOR_LOOK_SECOND 1
#define OVERWORLD_ACTOR_LOOK_RETURN 2
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_BEGIN 1
#define OVERWORLD_ACTOR_WALK_POLICY_CHAIN_REPOSITION_FINISH 2
#define OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT 3
#define OVERWORLD_ACTOR_WORLD_EFFECT_CRASH 1
#define OVERWORLD_MOUNT_BOUNDARY_APPLIED_LO_INDEX 1
#define OVERWORLD_MOUNT_BOUNDARY_APPLIED_HI_INDEX 2
#define OW_WILD_BEHAVIOR_SKID_BOOLEAN(value) ((value) & 1)
#define SEQ_SE_GS_UFO_JUMP 1
#define SEQ_SE_DP_WALL_HIT 2
typedef struct { s16 xCurr, yCurr; u8 curFacing; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; u32 unk0; u8 state; } FIELD_PLAYER_AVATAR;
typedef struct {
    struct { u8 motionMode; struct { u8 chainRepositionDust; } profile; } snapshot;
    u32 reservedPriorFollowerPolicy;
    u8 reservedPolicyState[9];
    u16 motionCooldown;
    s16 motionTargetX, motionTargetY;
} OverworldMountRuntimeState;
typedef struct {
    u8 actorActive, motionPhase, chainPauseTicks, chainPauseAction, chainStepsRemaining;
} OverworldActorPolicyView;
typedef struct {
    OverworldMountRuntimeState *state;
    FIELD_PLAYER_AVATAR *avatar;
    const OverworldActorPolicyView *policy;
    u8 action, operation;
} OverworldMountActionCall;
static OverworldActorPolicyView currentPolicy;
static int inspectAvailable, requests, accepted, sounds;
static u8 nextResult, seenDirection;
static s16 seenX, seenY;
static u8 OverworldMountAction_StartMotion(OverworldMountActionCall *call,
    u8 kind, u8 direction, s16 x, s16 y, u8 distance, u16 duration, u8 arc) {
    assert(kind == OVERWORLD_MOTION_KIND_HOP && distance == 0);
    assert(duration == 64 && arc == 16);
    assert(call->state->snapshot.motionMode == OVERWORLD_MOUNT_MOTION_NONE);
    assert(currentPolicy.motionPhase == OVERWORLD_MOTION_PHASE_IDLE
        || currentPolicy.motionPhase == OVERWORLD_MOTION_PHASE_CANCELED);
    requests++;
    seenDirection = direction; seenX = x; seenY = y;
    if (nextResult == OVERWORLD_MOUNT_ACTION_STARTED) {
        accepted++;
        call->state->motionTargetX = x; call->state->motionTargetY = y;
        call->state->snapshot.motionMode = 1;
        currentPolicy.motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
    }
    return nextResult;
}
static BOOL OverworldActorPolicy_Inspect(u8 slot, OverworldActorPolicyView *out) {
    assert(slot == OVERWORLD_ACTOR_SYSTEM_FOLLOWER_SLOT);
    if (!inspectAvailable) return FALSE;
    *out = currentPolicy;
    return TRUE;
}
static void PlaySE(int effect) { assert(effect == SEQ_SE_GS_UFO_JUMP); sounds++; }
/* Look services return chosen results; Hop must never call them. */
static int lookAllowed, lookCalls, facingCalls, buildCalls;
static u8 buildDirection, facingDirection;
static int lookResults[3];
static u8 lookArgs[3][4];
static u8 ObserveLook(u8 direction) {
    assert(lookAllowed); buildCalls++; buildDirection = direction; return 0xA5;
}
static int ObserveResolve(u8 plan, u8 mode, u8 total, u8 remaining) {
    assert(lookAllowed && mode <= 2 && lookCalls < 3);
    lookArgs[lookCalls][0] = plan; lookArgs[lookCalls][1] = mode;
    lookArgs[lookCalls][2] = total; lookArgs[lookCalls][3] = remaining;
    lookCalls++; return lookResults[mode];
}
static struct { u8 (*buildLookPlan)(u8); int (*resolveLook)(u8,u8,u8,u8); }
    lookPolicy = {ObserveLook, ObserveResolve};
static struct { __typeof__(lookPolicy) *policy; } policyEntry = {&lookPolicy};
#define OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY (&policyEntry)
static void UnexpectedParticle(LocalMapObject *object) { (void)object; abort(); }
static struct { void (*playLandingHopParticle)(LocalMapObject *); }
    wildEntry = {UnexpectedParticle};
#define OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY (&wildEntry)
static void OverworldMountAction_SetFacing(OverworldMountRuntimeState *state, u8 direction) {
    assert(lookAllowed && state != NULL); facingCalls++; facingDirection = direction;
}
static BOOL OverworldMountAction_Reduce(OverworldMountRuntimeState *state,
    u8 operation, u8 first, u8 second) {
    (void)state; (void)operation; (void)first; (void)second; abort();
}
static u8 OverworldMountAction_RunReposition(OverworldMountActionCall *call, u8 mode) {
    (void)call; (void)mode; abort();
}
static LocalMapObject *OverworldMountAction_Follower(void) { abort(); }
'''


HOP_CASES = r'''
#define CHECK(value) do { if (!(value)) { \
    fprintf(stderr, "line %d: %s\n", __LINE__, #value); return 1; \
} } while (0)
static void Returned(OverworldMountRuntimeState *state, u8 phase) {
    state->snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
    currentPolicy.motionPhase = phase;
}
int main(void) {
    OverworldMountRuntimeState state;
    LocalMapObject object = {10, 20, 3};
    FIELD_PLAYER_AVATAR avatar = {&object, 0, PLAYER_STATE_WALKING};
    OverworldMountActionCall call = {&state, &avatar, &currentPolicy,
        OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_HOP_IN_PLACE,
        OVERWORLD_MOUNT_ACTION_START_CHAIN};
    u8 *scratch;
    int count, completed;
    inspectAvailable = TRUE;
    for (count = 0; count <= 3; count++) {
        int wanted = count ? count : 1;
        memset(&state, 0, sizeof(state));
        memset(&currentPolicy, 0, sizeof(currentPolicy));
        object.xCurr = 10; object.yCurr = 20; object.curFacing = 3;
        currentPolicy.actorActive = TRUE;
        currentPolicy.chainPauseTicks = count;
        call.operation = OVERWORLD_MOUNT_ACTION_START_CHAIN;
        call.policy = &currentPolicy;
        requests = accepted = sounds = 0;
        nextResult = OVERWORLD_MOUNT_ACTION_RETRY;
        CHECK(OverworldMountAction_StartChain(&call) == OVERWORLD_MOUNT_ACTION_RETRY);
        CHECK(state.reservedPriorFollowerPolicy == 0 && accepted == 0 && sounds == 0);
        nextResult = OVERWORLD_MOUNT_ACTION_STARTED;
        CHECK(OverworldMountAction_StartChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
        scratch = OverworldMountAction_State(&state);
        CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == wanted - 1);
        CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_SECOND] == 3);
        CHECK(accepted == 1 && sounds == 1 && seenX == 10 && seenY == 20);
        call.operation = OVERWORLD_MOUNT_ACTION_TICK_CHAIN;
        for (completed = 0; completed < wanted; completed++) {
            int before = requests;
            u32 saved = state.reservedPriorFollowerPolicy;
            /* Neither active motion owner nor a settling shared Hop may restart. */
            CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
            CHECK(requests == before && state.reservedPriorFollowerPolicy == saved);
            currentPolicy.motionPhase = OVERWORLD_MOTION_PHASE_IDLE;
            CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
            CHECK(requests == before && state.reservedPriorFollowerPolicy == saved);
            currentPolicy.motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
            state.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
            CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
            currentPolicy.motionPhase = OVERWORLD_MOTION_PHASE_SETTLING;
            CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
            CHECK(requests == before && state.reservedPriorFollowerPolicy == saved);
            Returned(&state, OVERWORLD_MOTION_PHASE_IDLE);
            if (completed + 1 < wanted) {
                object.xCurr = 99; object.yCurr = 88; object.curFacing = 0;
                currentPolicy.chainPauseTicks = 0; /* A new profile cannot redraw the count. */
                nextResult = OVERWORLD_MOUNT_ACTION_RETRY;
                CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_RETRY);
                CHECK(state.reservedPriorFollowerPolicy == saved && sounds == accepted);
                nextResult = OVERWORLD_MOUNT_ACTION_STARTED;
                CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
                CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == wanted - completed - 2);
                CHECK(seenX == 10 && seenY == 20 && seenDirection == 3);
                CHECK(accepted == completed + 2 && sounds == accepted);
            } else {
                CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_FINAL);
                CHECK(state.reservedPriorFollowerPolicy == 0 && requests == before);
                CHECK(accepted == wanted && sounds == wanted);
                CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_FINAL);
                CHECK(requests == before);
            }
        }
    }
    /* Canceled motion ends the remaining pair, rather than issuing another Hop. */
    for (count = 0; count < 2; count++) {
        memset(&state, 0, sizeof(state));
        currentPolicy.actorActive = TRUE;
        currentPolicy.chainPauseTicks = 3;
        call.operation = OVERWORLD_MOUNT_ACTION_START_CHAIN;
        call.policy = &currentPolicy;
        Returned(&state, OVERWORLD_MOTION_PHASE_IDLE);
        nextResult = OVERWORLD_MOUNT_ACTION_STARTED;
        CHECK(OverworldMountAction_StartChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
        call.operation = OVERWORLD_MOUNT_ACTION_TICK_CHAIN;
        completed = requests;
        if (count == 0) {
            Returned(&state, OVERWORLD_MOTION_PHASE_CANCELED);
            CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_FINAL);
            CHECK(requests == completed);
        } else {
            Returned(&state, OVERWORLD_MOTION_PHASE_IDLE);
            nextResult = OVERWORLD_MOUNT_ACTION_FINAL;
            CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_FINAL);
            CHECK(requests == completed + 1);
        }
        CHECK(state.reservedPriorFollowerPolicy == 0);
    }
    /* Every first-only guard rejects before an accepted motion or scratch write. */
    for (count = 0; count < 9; count++) {
        memset(&state, 0, sizeof(state));
        memset(&currentPolicy, 0, sizeof(currentPolicy));
        currentPolicy.actorActive = TRUE;
        avatar.mapObject = &object; avatar.state = PLAYER_STATE_WALKING; avatar.unk0 = 0;
        call.state = &state; call.avatar = &avatar; call.policy = &currentPolicy;
        if (count == 0) call.state = NULL;
        if (count == 1) call.avatar = NULL;
        if (count == 2) avatar.mapObject = NULL;
        if (count == 3) call.policy = NULL;
        if (count == 4) currentPolicy.actorActive = FALSE;
        if (count == 5) avatar.state = 1;
        if (count == 6) avatar.unk0 = OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
        if (count == 7) state.motionCooldown = 1;
        if (count == 8) currentPolicy.motionPhase = OVERWORLD_MOTION_PHASE_MOVING;
        completed = requests;
        CHECK(OverworldMountAction_StartChain(&call) == OVERWORLD_MOUNT_ACTION_RETRY);
        CHECK(requests == completed && state.reservedPriorFollowerPolicy == 0);
    }
    call.state = &state; call.avatar = &avatar; call.policy = &currentPolicy;
    avatar.mapObject = &object; avatar.state = PLAYER_STATE_WALKING; avatar.unk0 = 0;
    memset(&state, 0, sizeof(state));
    currentPolicy.motionPhase = OVERWORLD_MOTION_PHASE_IDLE;
    scratch = OverworldMountAction_State(&state);
    scratch[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = 1;
    completed = requests;
    CHECK(OverworldMountAction_StartChain(&call) == OVERWORLD_MOUNT_ACTION_RETRY);
    CHECK(requests == completed && scratch[OVERWORLD_MOUNT_ACTION_STATE_ACTION] == 1);
    /* Real Look initialization clamps all byte inputs, with exact initial arguments. */
    lookAllowed = TRUE;
    call.action = OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_LOOK_AROUND;
    for (count = 0; count <= 255; count++) {
        int frames = count * 2;
        if (frames < 3) frames = 3;
        if (frames > 255) frames = 255;
        memset(&state, 0, sizeof(state));
        currentPolicy.chainPauseTicks = count;
        object.curFacing = 3;
        lookCalls = facingCalls = buildCalls = 0;
        lookResults[OVERWORLD_ACTOR_LOOK_FIRST] = 2;
        completed = requests;
        CHECK(OverworldMountAction_StartChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
        CHECK(requests == completed && buildCalls == 1 && buildDirection == 3);
        CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == frames);
        CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_SECOND] == frames);
        CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_THIRD] == 0xA5);
        CHECK(lookCalls == 1 && facingCalls == 1 && facingDirection == 2);
        CHECK(lookArgs[0][0] == 0xA5 && lookArgs[0][1] == OVERWORLD_ACTOR_LOOK_FIRST);
        CHECK(lookArgs[0][2] == 0 && lookArgs[0][3] == 0);
    }
    /* Tick tries Return, then Second, then First with the old exact arguments. */
    for (count = 0; count < 3; count++) {
        memset(&state, 0, sizeof(state));
        scratch[OVERWORLD_MOUNT_ACTION_STATE_ACTION] = call.action;
        scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = 5;
        scratch[OVERWORLD_MOUNT_ACTION_STATE_SECOND] = 10;
        scratch[OVERWORLD_MOUNT_ACTION_STATE_THIRD] = 0xA5;
        lookResults[0] = 1; lookResults[1] = count == 2 ? -1 : 2;
        lookResults[2] = count == 0 ? 3 : -1;
        lookCalls = facingCalls = 0;
        CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
        CHECK(lookCalls == count + 1 && facingCalls == 1);
        CHECK(facingDirection == (count == 0 ? 3 : count == 1 ? 2 : 1));
        CHECK(scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == 4);
        for (completed = 0; completed <= count; completed++) {
            int mode = OVERWORLD_ACTOR_LOOK_RETURN - completed;
            CHECK(lookArgs[completed][0] == 0xA5 && lookArgs[completed][1] == mode);
            CHECK(lookArgs[completed][2] == 10);
            CHECK(lookArgs[completed][3] == 4);
        }
    }
    inspectAvailable = FALSE;
    lookCalls = 0;
    CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_STARTED);
    CHECK(lookCalls == 0 && scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] == 4);
    inspectAvailable = TRUE;
    scratch[OVERWORLD_MOUNT_ACTION_STATE_FIRST] = 1;
    lookCalls = facingCalls = 0;
    CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_FINAL);
    CHECK(state.reservedPriorFollowerPolicy == 0 && facingCalls == 1);
    CHECK(lookArgs[0][2] == 10 && lookArgs[0][3] == 0);
    CHECK(OverworldMountAction_TickChain(&call) == OVERWORLD_MOUNT_ACTION_FINAL);
    /* The actual shared First resolver ignores timer arguments for every plan. */
    for (count = 0; count <= 255; count++) {
        int expected = ActorSystem_ResolveLook(count, OVERWORLD_ACTOR_LOOK_FIRST, 0, 0);
        for (completed = 0; completed <= 255; completed++) {
            CHECK(ActorSystem_ResolveLook(count, OVERWORLD_ACTOR_LOOK_FIRST,
                completed, 0) == expected);
            CHECK(ActorSystem_ResolveLook(count, OVERWORLD_ACTOR_LOOK_FIRST,
                completed, completed) == expected);
            CHECK(ActorSystem_ResolveLook(count, OVERWORLD_ACTOR_LOOK_FIRST,
                completed, 255) == expected);
        }
    }
    return 0;
}
'''


class MountActionAdapterTests(unittest.TestCase):
    def test_switch_helper_requires_thumb_metadata_and_direct_packaged_bl(self):
        name, target, call_at = "__gnu_thumb1_case_uqi", 0x023DEE54, 0x01FF8820
        source = SOURCE.read_text()
        imported = (target, 0, "*ABS*", "F")
        linked = {name: (target+1, 0, "*ABS*", "")}
        def bl(destination):
            delta = destination - call_at - 4
            return struct.pack("<HH", 0xF000 | ((delta >> 12) & 0x7FF),
                               0xF800 | ((delta >> 1) & 0x7FF))
        good = bl(target)
        calls = [("R_ARM_THM_CALL", good, good, call_at)]
        action_switch_import_contract(source, imported, linked, calls)
        bad = bl(0x01FF95C8)
        veneer = {**linked, "____gnu_thumb1_case_uqi_from_thumb":
                  (0x01FF95C8, 8, ".text", "F")}
        for label, changed_source, changed_import, changed_linked, changed_calls in (
            ("missing source Thumb mode", source.replace(
                ".thumb_func\\n.thumb_set "+name, ".thumb_set "+name), imported, linked, calls),
            ("missing object function metadata", source, (target, 0, "*ABS*", ""), linked, calls),
            ("original ARM veneer fault", source, None, veneer,
             [("R_ARM_THM_CALL", bad, bad, call_at)]),
            ("veneer retained with metadata", source, imported, veneer, calls),
            ("BL points to veneer", source, imported, linked,
             [("R_ARM_THM_CALL", bad, bad, call_at)]),
            ("wrong relocation kind", source, imported, linked,
             [("R_ARM_ABS32", good, good, call_at)]),
            ("package differs from ELF", source, imported, linked,
             [("R_ARM_THM_CALL", good, bad, call_at)]),
            ("missing caller", source, imported, linked, []),
        ):
            with self.subTest(fault=label), self.assertRaises(SystemExit):
                action_switch_import_contract(changed_source, changed_import,
                                              changed_linked, changed_calls)

    def test_cancel_does_not_clear_a_replacement_follower_chain(self):
        body = function_body(MOUNT_SOURCE.read_text(), "OverworldMount_Cancel")
        identity_check = body.index("restorePriorPolicy = OverworldMount_BindingMatchesFollower")
        guarded_cancel = body.index("if (restorePriorPolicy) {", identity_check)
        cancel = body.index("OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN", guarded_cancel)
        guard_end = body.index("\n    }", guarded_cancel)
        guarded_reset = body.index("if (restorePriorPolicy) {", guard_end)
        reset = body.index("OverworldMount_ResetMomentum();", guarded_reset)
        reset_guard_end = body.index("\n    }", guarded_reset)
        self.assertLess(identity_check, guarded_cancel)
        self.assertLess(guarded_cancel, cancel)
        self.assertLess(cancel, guard_end)
        self.assertLess(guarded_reset, reset)
        self.assertLess(reset, reset_guard_end)

    def test_stream_rejection_is_terminal_not_an_unbounded_retry(self):
        body = function_body(SOURCE.read_text(), "OverworldMountAction_StartMotion")
        query = body.index("OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE")
        begin = body.index("targetBaseY =", query)
        classification = body[query:begin]
        self.assertIn(
            "streamResult == OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED\n"
            "                ? OVERWORLD_MOUNT_ACTION_FINAL\n"
            "                : OVERWORLD_MOUNT_ACTION_RETRY;",
            classification)

    def test_forward_target_is_exact_and_has_no_fallback(self):
        source = SOURCE.read_text()
        program = (STUBS
            + "static u8 OverworldMountAction_ChainForwardTarget("
              "OverworldMountActionCall *call) {"
            + function_body(source, "OverworldMountAction_ChainForwardTarget")
            + "}\n"
            + CASES)
        with tempfile.TemporaryDirectory(prefix="mount-action-") as temporary:
            binary = Path(temporary) / "forward-target"
            compile_result = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")),
                 "-std=c11", "-O0", "-x", "c", "-", "-o", str(binary)],
                input=program, text=True, capture_output=True)
            self.assertEqual(compile_result.returncode, 0,
                             compile_result.stdout + compile_result.stderr)
            run_result = subprocess.run([str(binary)], capture_output=True,
                                        text=True)
            self.assertEqual(run_result.returncode, 0,
                             run_result.stdout + run_result.stderr)

    def test_mount_and_wild_strict_diagonal_markers_match(self):
        mount = re.search(
            r"OVERWORLD_MOUNT_ACTION_STRICT_DIAGONAL_MARKER\s+(0x[0-9A-Fa-f]+)",
            HEADER.read_text())
        wild = re.search(
            r"OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER\s+(0x[0-9A-Fa-f]+)",
            WILD_SOURCE.read_text())
        self.assertIsNotNone(mount)
        self.assertIsNotNone(wild)
        self.assertEqual(int(mount.group(1), 0), int(wild.group(1), 0))

    def test_hop_count_uses_shared_motion_terminal_and_retains_retry(self):
        source = SOURCE.read_text()
        constants = "\n".join(line for line in source.splitlines()
            if line.startswith("#define OVERWORLD_MOUNT_"))
        program = HOP_STUBS + constants + "\n"
        actor_source = (ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
        program += "\n".join(line for line in actor_source.splitlines()
            if line.startswith("#define OW_ACTOR_LOOK_")) + "\n"
        program += ("static int ActorSystem_ResolveLook(u8 lookPlan, u8 phase, "
                    "u8 totalFrames, u8 remainingFrames) {"
                    + function_body(actor_source, "ActorSystem_ResolveLook") + "}\n")
        bodies = [("u8 *", "OverworldMountAction_State"),
                  ("u8 ", "OverworldMountAction_RunChain")]
        for result, name in bodies:
            argument = ("OverworldMountRuntimeState *state" if name.endswith("_State")
                        else "OverworldMountActionCall *call")
            program += (f"static {result}{name}({argument}) {{"
                        + function_body(source, name) + "}\n")
        program += r"""
static u8 OverworldMountAction_StartChain(OverworldMountActionCall *call) {
    call->operation = OVERWORLD_MOUNT_ACTION_START_CHAIN;
    return OverworldMountAction_RunChain(call);
}
static u8 OverworldMountAction_TickChain(OverworldMountActionCall *call) {
    call->operation = OVERWORLD_MOUNT_ACTION_TICK_CHAIN;
    return OverworldMountAction_RunChain(call);
}
""" + HOP_CASES
        with tempfile.TemporaryDirectory(prefix="mount-hop-") as temporary:
            binary = Path(temporary) / "hop-count"
            compiled = subprocess.run(
                [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11",
                 "-O0", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "include"),
                 "-x", "c", "-", "-o", str(binary)],
                input=program, text=True, capture_output=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
