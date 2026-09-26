#include "../../include/overworld_mount.h"
#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_mount_action_adapter.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_spawns_internal.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/map_teleport.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/overworld_wild_movement.h"
#include "../../include/overworld_wild_runtime.h"
#include "../../include/overworld_walk_module.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/sound.h"

/* Absolute linker imports do not carry ELF Thumb-function metadata. Mark the
 * resident helper entries here so direct BL relocations do not need veneers. */
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaX, 0x023BF59C\n"
    ".thumb_func\n.thumb_set OverworldWalk_DeltaY, 0x023BF5BE\n"
    ".thumb_func\n.thumb_set OverworldWalk_DirectionFromDelta, 0x023BF68C\n"
    ".thumb_func\n.thumb_set OverworldWalk_StrictDiagonalAllowed, 0x023BF6CE\n"
    ".thumb_func\n.thumb_set OverworldWalk_DiagonalFacing, 0x023BF74E\n"
    ".thumb_func\n.thumb_set OverworldWalk_ResolveMountedDiagonal, 0x023BF780\n"
    ".thumb_func\n.thumb_set OverworldWalk_StartMountedFlat, 0x023BF840\n"
    ".thumb_func\n.thumb_set OverworldWalk_FilterMountedInput, 0x023BF9A0\n"
    ".thumb_func\n.thumb_set OverworldWildSpawns_ResolveWalkPause, 0x023DFFCC\n"
    ".thumb_func\n.thumb_set OverworldMount_GetSurfaceId, 0x01FF9A70\n"
    ".thumb_func\n.thumb_set OverworldMount_UpdatePlayerBaseHeight, 0x01FF97E0\n"
    ".thumb_func\n.thumb_set OverworldMount_ClearFollowerDecisionCooldown, 0x01FF97D0\n"
    ".thumb_func\n.thumb_set OverworldMount_GetOrdinaryDirection, 0x01FF9780\n"
    ".thumb_func\n.thumb_set OverworldMount_FinalizeIsPending, 0x01FF97C0\n"
    ".thumb_func\n.thumb_set OverworldMount_IsLandingTileAllowed, 0x01FF9620\n"
    ".thumb_func\n.thumb_set OverworldMount_ClassifyTeleportCandidate, 0x01FF9661\n"
    ".thumb_func\n.thumb_set OverworldMount_ApplyWalkPolicyOutput, 0x01FF96C0\n"
    ".global OverworldMount_ClearObjectCommand\n"
    ".thumb_func\n.thumb_set OverworldMount_ClearObjectCommand, 0x020621F0\n"
    ".thumb_func\n.thumb_set OverworldActorPolicy_MountCommand, 0x023BA0E0\n"
    ".thumb_func\n.thumb_set OverworldMount_ChainControl, 0x01FF9800\n"
    ".thumb_func\n.thumb_set OverworldMount_ResetMomentum, 0x01FF9AB0\n"
    ".thumb_func\n.thumb_set OverworldMount_BufferedDirection, 0x01FF9AD4\n"
    ".thumb_func\n.thumb_set OverworldMount_FinishOneFrameWalk, 0x023BA0BC\n"
    ".thumb_func\n.thumb_set OverworldWalkMount_RebaseMotionTarget, 0x023BFFEA\n"
    ".thumb_func\n.thumb_set OverworldWalk_RefreshMountedGraphics, 0x01FF8700\n"
    ".thumb_func\n.thumb_set memcpy, 0x023DEEBE\n"
    ".thumb_func\n.thumb_set memset, 0x023DEEA2\n");

#pragma GCC optimize("Os")

#define OVERWORLD_MOUNT_TOGGLE_BUTTON PAD_BUTTON_SELECT
#define OVERWORLD_MOUNT_RIDER_HEIGHT_FX32 0x8000
#define OVERWORLD_MOUNT_IDLE_COOLDOWN 0xFF
#define OVERWORLD_MOUNT_DIRECTION_NONE OW_WILD_WALK_DIRECTION_NONE
#define OVERWORLD_MOUNT_DIRECTION_NORTH 0
#define OVERWORLD_MOUNT_DIRECTION_SOUTH 1
#define OVERWORLD_MOUNT_DIRECTION_WEST 2
#define OVERWORLD_MOUNT_DIRECTION_EAST 3
#define OVERWORLD_MOUNT_DIRECTION_NORTH_WEST 4
#define OVERWORLD_MOUNT_DIRECTION_NORTH_EAST 5
#define OVERWORLD_MOUNT_DIRECTION_SOUTH_WEST 6
#define OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST 7
#define OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE 0
#define OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT (1u << 0)
#define OVERWORLD_MOUNT_HOP_MAX_DISTANCE 16
#define OVERWORLD_MOUNT_CRASH_SHAKE_FRAMES 32
#define OVERWORLD_MOUNT_CRASH_SHAKE_FX32 0x2000
#define OVERWORLD_MOUNT_WALK_FREEZE_COMMAND 0x3C
#define OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND 0x3E
/* These object-event sprite IDs resolve to overworld models 0073
 * (swimhero.pal) and 0074 (swimheroine.pal), respectively. */
#define OVERWORLD_MOUNT_RIDER_SPRITE_MALE 178
#define OVERWORLD_MOUNT_RIDER_SPRITE_FEMALE 179
extern void OverworldMount_ChainControl(
    FIELD_PLAYER_AVATAR *avatar, u32 param1, s32 direction,
    u32 newKeys, u32 heldKeys, u32 param5);
extern u8 OverworldMount_BufferedDirection(u32 keys);
extern void OverworldMount_ResetMomentum(void);
extern u16 OverworldMount_GetSurfaceId(int targetX, int targetY);
extern void OverworldMount_UpdatePlayerBaseHeight(LocalMapObject *player);
extern void OverworldMount_ClearFollowerDecisionCooldown(void);
extern void OverworldMount_FinishOneFrameWalk(FIELD_PLAYER_AVATAR *avatar);
extern BOOL OverworldMount_GetOrdinaryDirection(
    u32 movementCommand, u8 *directionOut);
extern BOOL OverworldMount_FinalizeIsPending(void);
extern BOOL OverworldMount_IsLandingTileAllowed(int targetX, int targetY);
extern void OverworldMount_ClassifyTeleportCandidate(
    void *rawContext, OverworldActorTeleportCandidate *candidate);
extern void OverworldMount_ApplyWalkPolicyOutput(
    FIELD_PLAYER_AVATAR *avatar, LocalMapObject *follower,
    const OverworldActorWalkPolicyCall *call);
#define OverworldMount_ApplyPolicyCommand \
    OverworldActorPolicy_MountCommand
#define OverworldMount_ApplyPolicyValue(operation, value) \
    ((void)OverworldActorPolicy_MountCommand( \
        (operation), (void *)(u32)(value)))

typedef struct OverworldMountTeleportWorldContext {
    LocalMapObject *player;
} OverworldMountTeleportWorldContext;

extern void OverworldMount_ClearObjectCommand(LocalMapObject *player);

static OverworldMountRuntimeState sOverworldMountState
    __attribute__((section(".overworld_mount_state")));
typedef char OverworldMountReleaseHandoffFramesMustRemain1[
    OVERWORLD_MOUNT_RELEASE_HANDOFF_FRAMES == 1 ? 1 : -1];
typedef char OverworldMountFollowerCooldownOffsetMustRemainF4[
    offsetof(OverworldWildSpawnState, movementCooldowns)
            + OW_WILD_FOLLOWER_SLOT == 0xF4
        ? 1
        : -1];
#define OVERWORLD_MOUNT_BOUNDARY_FLAGS \
    (sOverworldMountState.reservedPolicyState[ \
        OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX])
#define OVERWORLD_MOUNT_BOUNDARY_MOTION \
    (sOverworldMountState.reservedPolicyState[ \
        OVERWORLD_MOUNT_BOUNDARY_MOTION_INDEX])
#define OVERWORLD_MOUNT_BOUNDARY_PHASE \
    (sOverworldMountState.reservedPolicyState[ \
        OVERWORLD_MOUNT_BOUNDARY_PHASE_INDEX])

static void OverworldMount_FinishCustomMotion(void);
static void OverworldMount_UpdateCustomMotion(void);
static void OverworldMount_DrainLandStream(void);
static BOOL OverworldMount_BeginSharedMotion(BOOL advanceFirstFrame);
static BOOL __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_BeginWalkMotion(BOOL advanceFirstFrame)
{
    BOOL started = OverworldMount_BeginSharedMotion(advanceFirstFrame);

    if (!started) {
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_NONE;
    }
    return started;
}
static BOOL OverworldMount_AcknowledgeSharedMotion(
    u8 acknowledgements,
    u16 appliedThrough,
    OverworldMotionSample *sample);
static void OverworldMount_CancelSharedMotion(u8 reason);
static BOOL OverworldMount_TryFinalizeSharedMotion(void);
static void OverworldMount_ResumeCustomMotionAfterMapTransition(void);
static BOOL __attribute__((noinline, noclone))
OverworldMount_CompletePendingStep(FIELD_PLAYER_AVATAR *avatar);
static BOOL OverworldMount_CommitWalkBoundary(FIELD_PLAYER_AVATAR *avatar);
static void OverworldMount_SetMountedFacing(u8 direction);
void OverworldMount_IssueHeldMovement(
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *object,
    u32 vanillaCommand);
static int OverworldMount_DirectionDeltaX(u8 direction);
static int OverworldMount_DirectionDeltaY(u8 direction);
static BOOL OverworldMount_PlanHopTrajectory(
    u8 distance,
    u32 *trajectory);
void OverworldMount_PlayCrashSound(u32 sequence);
static BOOL OverworldMount_HasCurrentPlayer(void);

static OverworldFieldTerrainStreamResult __attribute__((noinline,
    section(".overworld_mount_streaming")))
OverworldMount_ApplyTerrainStream(u8 operation)
{
    const OverworldFieldMountPresentationEntry *entry =
        OVERWORLD_FIELD_MOUNT_PRESENTATION_ENTRY;
    OverworldFieldTerrainStreamCall call;
    OverworldActorFieldContext context;
    LocalMapObject *player;

    if (entry->magic != OVERWORLD_FIELD_MOUNT_PRESENTATION_MAGIC
        || entry->version != OVERWORLD_FIELD_MOUNT_PRESENTATION_VERSION
        || entry->size != sizeof(*entry)
        || entry->terrainStream == NULL
        || sOverworldMountState.fieldSystem == NULL) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
    }
    memset(&call, 0, sizeof(call));
    context = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    call.version = OVERWORLD_FIELD_TERRAIN_STREAM_CALL_VERSION;
    call.size = sizeof(call);
    call.fieldSystem = sOverworldMountState.fieldSystem;
    call.fieldContext = context;
    call.motionIdentity = sOverworldMountState.motionIdentity;
    call.targetX = sOverworldMountState.motionTargetX;
    call.targetY = sOverworldMountState.motionTargetY;
    if (operation == OVERWORLD_FIELD_TERRAIN_STREAM_POLL
        && sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_HOP
        && OverworldMount_HasCurrentPlayer()) {
        player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
        call.targetX = (s16)player->xCurr;
        call.targetY = (s16)player->yCurr;
    }
    call.operation = operation;
    return entry->terrainStream(&call);
}

static BOOL __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_TerrainStreamIsIdle(void)
{
    return OverworldMount_ApplyTerrainStream(
            OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE)
        == OVERWORLD_FIELD_TERRAIN_STREAM_IDLE;
}

static BOOL __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_BeginTerrainStream(void)
{
    if (OverworldMount_ApplyTerrainStream(
            OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN)
            != OVERWORLD_FIELD_TERRAIN_STREAM_WAITING) {
        return FALSE;
    }
    sOverworldMountState.motionStreamPreparing = TRUE;
    return TRUE;
}

static BOOL __attribute__((noinline, section(".overworld_mount_streaming")))
OverworldMount_ReleaseTerrainStream(void)
{
    if (OverworldMount_ApplyTerrainStream(
            OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL)
            != OVERWORLD_FIELD_TERRAIN_STREAM_IDLE) {
        return FALSE;
    }
    sOverworldMountState.motionStreamPreparing = FALSE;
    return TRUE;
}

static u8 __attribute__((noinline,
    optimize("Os", "no-tree-forwprop")))
OverworldMount_ReduceRole(u32 request, u32 details)
{
    union {
        OverworldRoleControllerInput value;
        u32 words[3];
    } input;
    OverworldRoleControllerOutput output;
    u8 outputOffset = (u8)(request >> 8) + 5;

    input.words[0] = OVERWORLD_ROLE_CONTROLLER_VERSION
        | sizeof(input.value) << 16;
    input.words[1] = request;
    input.words[2] = details;
    OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->reduceRole(
        &input.value, &output);
    (void)OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED;
    (void)OVERWORLD_ROLE_CONTROLLER_DECISION_INTENT;
    (void)OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH;
    return ((const u8 *)(const void *)&output)[outputOffset];
}

static void __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_InspectPolicy(OverworldActorPolicyView *policy)
{
    (void)OverworldMount_ApplyPolicyCommand(
        OVERWORLD_ACTOR_WALK_POLICY_INSPECT,
        policy);
}

static void __attribute__((noinline))
OverworldMount_StartWalkCrash(void)
{
    OverworldActorPolicyView policy;

    if (OverworldMount_ReduceRole(
            OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED
                | OVERWORLD_ROLE_CONTROLLER_EVENT_BLOCKED << 8
                | OVERWORLD_ROLE_CONTROLLER_INTENT_WALK << 16
                | (u32)OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE << 24,
            OVERWORLD_ROLE_CONTROLLER_DIRECTION_NONE
                | OVERWORLD_ROLE_CONTROLLER_INPUT_RAM << 8)
        != OVERWORLD_ROLE_CONTROLLER_TERMINAL_CRASH) {
        return;
    }
    OverworldMount_InspectPolicy(&policy);
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        && !OW_WILD_BEHAVIOR_WALK_ALLOWS_TURNING(
            sOverworldMountState.snapshot.profile.walkOptions)
        && policy.walkMomentum.direction
            != OVERWORLD_MOUNT_DIRECTION_NONE) {
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_CRASH;
        sOverworldMountState.motionFrameCount =
            OVERWORLD_MOUNT_CRASH_SHAKE_FRAMES;
        sOverworldMountState.motionElapsed = 0;
    } else {
        sOverworldMountState.motionCooldown = 4;
    }
    OverworldMount_ApplyPolicyValue(
        OVERWORLD_ACTOR_WALK_POLICY_PUBLISH_EFFECT,
        OVERWORLD_ACTOR_WORLD_EFFECT_CRASH);
    OverworldMount_ResetMomentum();
}

static void __attribute__((noinline, section(".overworld_mount_control_tail_crash")))
OverworldMount_ApplyCrashPresentation(
    LocalMapObject *player,
    LocalMapObject *follower)
{
    s32 offset;

    if (sOverworldMountState.snapshot.motionMode
        != OVERWORLD_MOUNT_MOTION_CRASH) {
        return;
    }
    offset = ((s32)(sOverworldMountState.motionElapsed & 2) - 1)
        * OVERWORLD_MOUNT_CRASH_SHAKE_FX32;
    player->faceVec[0] = (u32)((s32)player->faceVec[0] + offset);
    player->faceVec[2] = (u32)((s32)player->faceVec[2] - offset);
    follower->faceVec[0] = (u32)offset;
    follower->faceVec[2] = (u32)-offset;
    OverworldWalk_RefreshMountedGraphics(player, follower);
}

static void __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_ClearBoundaryState(void)
{
    /* Walk proposal bytes share this fixed adapter buffer, but they are not
     * boundary state. BeginSharedMotion runs before START_RESULT consumes the
     * accepted direction and timing, so clearing the complete buffer here
     * silently changed that accepted step into direction 0 / time 0. */
    memset(sOverworldMountState.reservedPolicyState,
        0,
        OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX);
}

static u16 __attribute__((naked, noinline,
    section(".overworld_mount_step_extra")))
OverworldMount_GetAppliedThrough(void)
{
    /* The applied path value starts at aligned runtime offset 0x84. Keep this
     * compact accessor explicit because this overlay has a fixed ROM budget. */
    __asm__(
        "ldr r0, 1f\n"
        "ldrh r0, [r0, #0]\n"
        "bx lr\n"
        ".align 2\n"
        "1: .word sOverworldMountState + 0x84\n");
}

static void __attribute__((naked, noinline,
    section(".overworld_mount_field_input_extra")))
OverworldMount_SetAppliedThrough(u16 appliedThrough)
{
    __asm__(
        "ldr r3, 1f\n"
        "strh r0, [r3, #0]\n"
        "sub r3, r3, #1\n"
        "ldrb r2, [r3, #0]\n"
        "mov r1, #1\n"
        "orr r2, r1\n"
        "strb r2, [r3, #0]\n"
        "bx lr\n"
        ".align 2\n"
        "1: .word sOverworldMountState + 0x84\n");
}

static void __attribute__((naked, noinline,
    section(".overworld_mount_field_input_extra")))
OverworldMount_EndSession(u8 reason)
{
    __asm__(
        "ldr r3, 1f\n"
        "mov r2, #0\n"
        "str r2, [r3, #0]\n"
        "mov r1, #1\n"
        "lsl r1, r1, #8\n"
        "add r3, #100\n"
        "strh r1, [r3, #0]\n"
        "strb r0, [r3, #2]\n"
        "strh r2, [r3, #26]\n"
        "bx lr\n"
        ".align 2\n"
        "1: .word sOverworldMountState\n");
}

static BOOL __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_BindingMatchesFollower(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    const OverworldWildSpawn *spawn;
    OverworldMountBinding *binding =
        &sOverworldMountState.snapshot.binding;

    if (fieldSystem == NULL
        || state == NULL
        || fieldSystem != sOverworldMountState.fieldSystem
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || state->movementFieldSystem != fieldSystem
        || state->mapId != fieldSystem->location->mapId
        || state->activeFollowerPartySlot == CUSTOM_FOLLOWER_PARTY_SLOT_NONE) {
        return FALSE;
    }
    spawn = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    if (!spawn->active
        || spawn->object == NULL
        || spawn->mapId != state->mapId
        || spawn->personality != binding->personality
        || spawn->species != binding->species
        || spawn->encounterGeneration != binding->encounterGeneration
        || spawn->form != binding->form
        || spawn->level != binding->level
        || state->activeFollowerPartySlot != binding->partySlot
        || state->movementBehaviorClasses[OW_WILD_FOLLOWER_SLOT]
            != binding->behaviorClass) {
        return FALSE;
    }

    /* Seamless map-header transitions preserve the follower object and its
     * encounter identity, but intentionally advance these two context keys. */
    binding->mapId = spawn->mapId;
    binding->mapGeneration = state->mapGeneration;
    return TRUE;
}

static LocalMapObject * __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_GetFollowerObject(void)
{
    if (!OverworldMount_BindingMatchesFollower(
            sOverworldMountState.fieldSystem,
            &sOverworldWildSpawnState)) {
        return NULL;
    }
    return sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT].object;
}

static BOOL __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_HasCurrentPlayer(void)
{
    FieldSystem *fieldSystem = sOverworldMountState.fieldSystem;

    return fieldSystem != NULL
        && fieldSystem == gFieldSysPtr
        && fieldSystem->playerAvatar != NULL
        && fieldSystem->playerAvatar->mapObject != NULL;
}

static void __attribute__((naked, noinline,
    section(".overworld_mount_step_extra")))
OverworldMount_ResetAvatarAfterCancel(FIELD_PLAYER_AVATAR *avatar)
{
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word PlayerAvatar_ResetMovement\n");
}

static void OverworldMount_SyncPresentation(void)
{
    const OverworldFieldMountPresentationEntry *entry =
        OVERWORLD_FIELD_MOUNT_PRESENTATION_ENTRY;
    OverworldFieldMountPresentationCall call;
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (!sOverworldMountState.presentationAttached
        || follower == NULL
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    call.version = OVERWORLD_FIELD_MOUNT_PRESENTATION_VERSION;
    call.size = sizeof(call);
    call.mount = &sOverworldMountState;
    call.wild = &sOverworldWildSpawnState;
    call.player = player;
    call.follower = follower;
    /* The fixed field entry is link-time sealed into the resident field
     * overlay. The typed callee validates the version, size, and pointers. */
    (void)entry->sync(&call);
    OverworldMount_ApplyCrashPresentation(player, follower);
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        || sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_HOP
        || sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_TELEPORT
        || OverworldMount_FinalizeIsPending()) {
        u8 acknowledgements =
            OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED;
        u16 appliedThrough = OverworldMount_GetAppliedThrough();

        if ((OVERWORLD_MOUNT_BOUNDARY_FLAGS
                & OVERWORLD_MOUNT_BOUNDARY_HAS_APPLIED_PATH) != 0) {
            acknowledgements |= OVERWORLD_ACTOR_BOUNDARY_PATH_APPLIED;
        }
        (void)OverworldMount_AcknowledgeSharedMotion(
            acknowledgements,
            appliedThrough,
            NULL);
    }
}

static BOOL OverworldMount_AttachPresentation(void)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (sOverworldMountState.presentationAttached) {
        return TRUE;
    }
    if (follower == NULL || !OverworldMount_HasCurrentPlayer()) {
        return FALSE;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    sOverworldMountState.snapshot.reserved =
        (follower->flags & MAPOBJECTFLAG_MOVEMENT_PAUSED) != 0;
    sOverworldMountState.savedPlayerShadowSuppressed =
        (player->flags & MAPOBJECTFLAG_UNK20) != 0;
    sOverworldMountState.playerBaseFaceY = player->faceVec[1];
    sOverworldMountState.playerBaseUnk88Y = player->unk88[1];
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    sOverworldMountState.savedPlayerGfxId = (u16)MapObject_GetGfxID(player);
    ChangeMapObjSprite(
        player,
        sOverworldMountState.fieldSystem->playerAvatar->gender == 0
            ? OVERWORLD_MOUNT_RIDER_SPRITE_MALE
            : OVERWORLD_MOUNT_RIDER_SPRITE_FEMALE);
    sOverworldMountState.presentationAttached = TRUE;
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_RIDING;
    /* A paused map object does not push subsequent position-vector writes to
     * its renderer. The mount controller already removes the follower from AI
     * movement ownership, so keep the presentation object unpaused while it
     * mirrors the player. */
    OverworldMount_ClearObjectCommand(follower);
    MapObject_UnpauseMovement(follower);
    /* The released follower can face the player. Bind both presentations to
     * the player's current facing once; later motion still owns Hop spin. */
    OverworldMount_SetMountedFacing(player->curFacing);
    OverworldMount_SyncPresentation();
    return TRUE;
}

static void OverworldMount_DetachPresentation(void)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player = NULL;
    FIELD_PLAYER_AVATAR *avatar;

    sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
    sOverworldMountState.pendingFieldStep = FALSE;
    if (!sOverworldMountState.presentationAttached) {
        return;
    }
    if (OverworldMount_HasCurrentPlayer()) {
        avatar = sOverworldMountState.fieldSystem->playerAvatar;
        player = avatar->mapObject;
        /* A cancellation can arrive after stock code has changed the avatar
         * state but before pendingStep records the command. Always return
         * control ownership to the normal player controller on detach. */
        OverworldMount_ClearObjectCommand(player);
        avatar->unk0 &= ~OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
        OverworldMount_ResetAvatarAfterCancel(avatar);
        OverworldMount_UpdatePlayerBaseHeight(player);
        player->flags &= ~MAPOBJECTFLAG_UNK7;
        player->faceVec[1] = sOverworldMountState.playerBaseFaceY;
        player->faceVec[0] = 0;
        player->faceVec[2] = 0;
        player->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
        ChangeMapObjSprite(player, sOverworldMountState.savedPlayerGfxId);
        if (sOverworldMountState.savedPlayerShadowSuppressed) {
            player->flags |= MAPOBJECTFLAG_UNK20;
        } else {
            player->flags &= ~MAPOBJECTFLAG_UNK20;
        }
    }
    if (follower != NULL) {
        OverworldMount_ClearObjectCommand(follower);
        OverworldMount_ClearFollowerDecisionCooldown();
        follower->flags &= ~MAPOBJECTFLAG_UNK31;
        follower->xPrev = follower->xCurr;
        follower->hPrev = follower->hCurr;
        follower->yPrev = follower->yCurr;
        follower->faceVec[0] = 0;
        follower->faceVec[1] = 0;
        follower->faceVec[2] = 0;
        follower->unk88[0] = 0;
        follower->unk88[1] = 0;
        follower->unk88[2] = 0;
        if (sOverworldMountState.snapshot.reserved) {
            MapObject_PauseMovement(follower);
        } else {
            MapObject_UnpauseMovement(follower);
        }
    }
    sOverworldMountState.presentationAttached = FALSE;
    OverworldMount_ClearBoundaryState();
}

static void OverworldMount_Cancel(u8 reason)
{
    BOOL restorePriorPolicy;
    OverworldMountActionCall actionCall = { 0 };

    if (sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_NONE) {
        return;
    }
    if (reason == OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST
        && sOverworldMountState.preserveTransitionPrepared) {
        return;
    }

    restorePriorPolicy = OverworldMount_BindingMatchesFollower(
        sOverworldMountState.fieldSystem,
        &sOverworldWildSpawnState);
    if (restorePriorPolicy) {
        actionCall.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
        actionCall.size = sizeof(actionCall);
        actionCall.operation = OVERWORLD_MOUNT_ACTION_CANCEL_CHAIN;
        actionCall.state = &sOverworldMountState;
        (void)OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&actionCall);
    }

    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_NONE) {
        OverworldWalkMount_RebaseMotionTarget(&sOverworldMountState);
        OverworldMount_FinishCustomMotion();
        OverworldMount_CancelSharedMotion(reason);
    } else if (OverworldMount_FinalizeIsPending()) {
        OverworldMount_CancelSharedMotion(reason);
    }
    if (sOverworldMountState.motionStreamPreparing
        && OverworldMount_HasCurrentPlayer()) {
        (void)OverworldMount_ReleaseTerrainStream();
    }
    OverworldMount_DetachPresentation();
    if (restorePriorPolicy) {
        OverworldMount_ResetMomentum();
        (void)OverworldMount_ApplyPolicyCommand(
            OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE,
            &sOverworldMountState.priorFollowerBehaviorFingerprint);
    }
    OverworldMount_EndSession(reason);
}

static BOOL __attribute__((optimize("Os", "no-tree-dominator-opts")))
OverworldMount_Begin(
    FieldSystem *fieldSystem,
    const OverworldMountBinding *binding,
    const OverworldWildBehaviorProfile *profile,
    const OverworldWildSurfaceCatalog *surfaceCatalog,
    OverworldActorPolicyProfileTransaction *policyTransaction)
{
    u32 generation;
    u8 bufferedToggleDown = sOverworldMountState.bufferedToggleDown;

    if (fieldSystem == NULL
        || binding == NULL
        || profile == NULL
        || surfaceCatalog == NULL
        || binding->species == SPECIES_NONE
        || sOverworldMountState.snapshot.phase != OVERWORLD_MOUNT_PHASE_NONE) {
        return FALSE;
    }

    if (!OverworldMount_ApplyPolicyCommand(
            OVERWORLD_ACTOR_WALK_POLICY_SWAP_PROFILE,
            policyTransaction)) {
        return FALSE;
    }

    generation = sOverworldMountState.snapshot.sessionGeneration + 1;
    if (generation == 0) {
        generation = 1;
    }
    memset(&sOverworldMountState, 0, sizeof(sOverworldMountState));
    /* The Select press that starts this session can still be physically held.
     * Preserve its resident edge state so it cannot become an immediate
     * second toggle after the session reset. */
    sOverworldMountState.bufferedToggleDown = bufferedToggleDown;
    sOverworldMountState.fieldSystem = fieldSystem;
    sOverworldMountState.surfaceCatalog = surfaceCatalog;
    sOverworldMountState.snapshot.profile = profile->owner;
    sOverworldMountState.snapshot.binding = *binding;
    sOverworldMountState.snapshot.sessionGeneration = generation;
    sOverworldMountState.snapshot.phase = OVERWORLD_MOUNT_PHASE_BOUND;
    sOverworldMountState.priorFollowerBehaviorFingerprint =
        policyTransaction->prior.behaviorFingerprint;
    sOverworldMountState.priorFollowerMatchedLayerMask =
        policyTransaction->prior.matchedLayerMask;

    OverworldMount_ResetMomentum();
    return TRUE;
}

static BOOL OverworldMount_Transition(
    const OverworldActorTransitionCall *call)
{
    OverworldActorPolicyView policy;

    if (call == NULL
        || call->version != OVERWORLD_ACTOR_TRANSITION_CALL_VERSION
        || call->size != sizeof(*call)
        || call->work < OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE
        || call->work > OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD) {
        return FALSE;
    }
    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_RESUME) {
        if (sOverworldMountState.motionStreamPreparing
            && OverworldMount_ApplyTerrainStream(
                OVERWORLD_FIELD_TERRAIN_STREAM_REBIND)
                != OVERWORLD_FIELD_TERRAIN_STREAM_WAITING) {
            return FALSE;
        }
        if (sOverworldMountState.snapshot.phase
            == OVERWORLD_MOUNT_PHASE_NONE) {
            return TRUE;
        }
        /* This callback runs after wild-object canonicalization, in the same
         * frame as the map-header change. Resume and advance the pair now so
         * the mount is never rendered at ground height between Hop frames. */
        OverworldMount_ResumeCustomMotionAfterMapTransition();
        OverworldMount_UpdateCustomMotion();
        OverworldMount_SyncPresentation();
        return TRUE;
    }
    if (sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_NONE) {
        return TRUE;
    }
    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_DISCARD) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_MAP_CHANGE);
        return TRUE;
    }
    if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND) {
        /* Rebind clears the actor-owned boundary receipt. Presentation, path,
         * and stream are naturally sampled again, but END is locally latched.
         * Clear only that latch so the real completed engine boundary is
         * replayed instead of leaving the actor in COMMIT_PENDING forever. */
        OVERWORLD_MOUNT_BOUNDARY_FLAGS &=
            ~OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN;
        return TRUE;
    }
    if (call->work != OVERWORLD_ACTOR_TRANSITION_WORK_CANONICALIZE) {
        return FALSE;
    }
    OverworldMount_InspectPolicy(&policy);
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        && !policy.pendingStep) {
        OverworldMount_ResetMomentum();
        sOverworldMountState.motionCooldown = 0;
    }
    sOverworldMountState.preserveTransitionPrepared = TRUE;
    return TRUE;
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_ResumeCustomMotionAfterMapTransition(void)
{
    LocalMapObject *follower;
    LocalMapObject *player;
    u32 freezeCommand;

    if (!sOverworldMountState.preserveTransitionPrepared) {
        return;
    }
    sOverworldMountState.preserveTransitionPrepared = FALSE;
    if ((sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_HOP
            && sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_TELEPORT
            && sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_WALK)
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    follower = OverworldMount_GetFollowerObject();
    if (follower == NULL) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    /* Map-header canonicalization clears every wild object's held command.
     * Reassert the stationary shell without changing elapsed motion state. */
    freezeCommand = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        ? OVERWORLD_MOUNT_WALK_FREEZE_COMMAND
        : OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND;
    MapObject_StartMovementCommandInternal(
        player,
        freezeCommand);
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_WALK) {
        MapObject_StartMovementCommandInternal(follower, freezeCommand);
    }
}

static BOOL __attribute__((noinline, section(".overworld_mount_control_tail")))
OverworldMount_IsActive(void)
{
    typedef u16 OverworldMountOwnershipWord __attribute__((may_alias));

    return *(const OverworldMountOwnershipWord *)(const void *)
        &sOverworldMountState.snapshot.phase;
}

static u8 __attribute__((naked, noinline,
    section(".overworld_mount_control_tail")))
OverworldMount_GetInputDirection(u32 keys)
{
    __asm__(
        "ldr r3, 1f\n"
        "bx r3\n"
        ".align 2\n"
        "1: .word 0x023BF535\n");
}

static void __attribute__((noinline, section(".overworld_mount_precode")))
OverworldMount_SetMountedFacing(u8 direction)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (!OverworldMount_HasCurrentPlayer() || direction > 3) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    player->curFacing = direction;
    player->nextFacing = direction;
    player->curFacingBak = direction;
    player->nextFacingBak = direction;
    if (follower != NULL) {
        follower->curFacing = direction;
        follower->nextFacing = direction;
        follower->curFacingBak = direction;
        follower->nextFacingBak = direction;
    }
}

BOOL __attribute__((section(".overworld_mount_step"), noinline, used))
OverworldMount_PlayerStepBridge(FieldSystem *fieldSystem)
{
    typedef BOOL (*PlayerStepHandler)(FieldSystem *);
    BOOL eventConsumed;

    eventConsumed = ((PlayerStepHandler)
        OVERWORLD_WILD_PLAYER_STEP_HANDLER_ADDR)(fieldSystem);
    if (eventConsumed && fieldSystem == sOverworldMountState.fieldSystem) {
        sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_STOP;
    }
    return eventConsumed;
}

static void __attribute__((section(".overworld_mount_motion"), noinline, optimize("Os")))
OverworldMount_OnPlayerStep(void)
{
    /* Retain the public entry as a retry only. The pre-gate path owns END. */
    if (OverworldMount_HasCurrentPlayer()) {
        OverworldMount_DrainLandStream();
        (void)OverworldMount_CompletePendingStep(
            sOverworldMountState.fieldSystem->playerAvatar);
    }
}


int __attribute__((section(".overworld_mount_field_input"), noinline, used))
OverworldMount_FieldInputProcess(
    OverworldMountFieldInput *fieldInput,
    FieldSystem *fieldSystem)
{
    return OVERWORLD_MOUNT_FIELD_INPUT_HOST(fieldInput, fieldSystem,
        &sOverworldMountState,
        fieldSystem == sOverworldMountState.fieldSystem
            && OverworldMount_HasCurrentPlayer());
}

static BOOL __attribute__((noinline)) OverworldMount_ApplyWalkPolicy(
    FIELD_PLAYER_AVATAR *avatar,
    BOOL started,
    BOOL crashOnBlocked)
{
    OverworldActorWalkPolicyCall output;

    if (!OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
            ->finishMountedWalk(
                &sOverworldMountState,
                started,
                crashOnBlocked,
                &output)) {
        return FALSE;
    }
    OverworldMount_ApplyWalkPolicyOutput(
        avatar,
        OverworldMount_GetFollowerObject(),
        &output);
    return output.decision != OVERWORLD_ACTOR_WALK_POLICY_IGNORED;
}

static BOOL __attribute__((noinline, optimize("Os"),
    section(".overworld_mount_motion")))
OverworldMount_CommitWalkBoundary(FIELD_PLAYER_AVATAR *avatar)
{
    OverworldActorPolicyView policy;
    OverworldActorWalkPolicyCall output;

    OverworldMount_InspectPolicy(&policy);
    memset(&output, 0, sizeof(output));
    output.version = OVERWORLD_ACTOR_WALK_POLICY_VERSION;
    output.size = sizeof(output);
    output.lane = &sOverworldMountState.snapshot.profile;
    output.actorSlot = OW_WILD_FOLLOWER_SLOT;
    output.laneState = OW_WILD_SPAWNER_SPOT_STATE_CHILL;
    output.operation = OVERWORLD_ACTOR_WALK_POLICY_COMMIT;
    output.direction = policy.walkMomentum.direction;
    output.distance = 1;
    output.flags = OVERWORLD_ACTOR_WALK_POLICY_FLAG_WALK_ACCEPTED
        | OVERWORLD_ACTOR_WALK_POLICY_FLAG_CHAIN_ENABLED;
    if (!OVERWORLD_ACTOR_SYSTEM_MOVEMENT_POLICY_ENTRY->policy
            ->terminalWalk(
                &output,
                OVERWORLD_ACTOR_BOUNDARY_ENGINE_END,
                OverworldMount_GetAppliedThrough(),
                sOverworldMountState.motionIdentity)) {
        return FALSE;
    }
    OVERWORLD_MOUNT_BOUNDARY_PHASE = output.reserved[
        OVERWORLD_ACTOR_WALK_POLICY_RESULT_PHASE_INDEX];
    OVERWORLD_MOUNT_BOUNDARY_FLAGS |=
        OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN;
    if (OVERWORLD_MOUNT_BOUNDARY_PHASE != OVERWORLD_MOTION_PHASE_IDLE
        && OVERWORLD_MOUNT_BOUNDARY_PHASE
            != OVERWORLD_MOTION_PHASE_SETTLING) {
        return TRUE;
    }
    OverworldMount_ApplyWalkPolicyOutput(
        avatar,
        OverworldMount_GetFollowerObject(),
        &output);
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os"),
    section(".overworld_mount_motion")))
OverworldMount_AcknowledgeSharedMotion(
    u8 acknowledgements,
    u16 appliedThrough,
    OverworldMotionSample *sample)
{
    extern BOOL OverworldMount_CallActorMotionBoundary(
        int slot,
        u8 acknowledgements,
        u16 appliedThrough,
        OverworldMotionSample *sample,
        u8 *phase,
        u16 motionIdentity);

    return OverworldMount_CallActorMotionBoundary(
        OW_WILD_FOLLOWER_SLOT,
        acknowledgements,
        appliedThrough,
        sample,
        &OVERWORLD_MOUNT_BOUNDARY_PHASE,
        sOverworldMountState.motionIdentity);
}

static BOOL __attribute__((noinline, noclone))
OverworldMount_CompletePendingStep(FIELD_PLAYER_AVATAR *avatar)
{
    u8 endState = sOverworldMountState.walkEndState;
    OverworldActorPolicyView policy;

    OverworldMount_InspectPolicy(&policy);
    if (policy.pendingStep
            != OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED
        || avatar == NULL
        || (endState & OVERWORLD_MOUNT_WALK_END_PENDING) == 0) {
        return FALSE;
    }
    /* The normal player-step bridge stored the real END. Keep that receipt
     * while terrain streaming catches up; the current avatar state can move
     * on before all actor-boundary acknowledgements are ready. */
    OverworldMount_SyncPresentation();
    if (!OverworldMount_CommitWalkBoundary(avatar)) {
        return FALSE;
    }
    if (OVERWORLD_MOUNT_BOUNDARY_PHASE != OVERWORLD_MOTION_PHASE_IDLE
        && OVERWORLD_MOUNT_BOUNDARY_PHASE
            != OVERWORLD_MOTION_PHASE_SETTLING) {
        return FALSE;
    }
    OverworldMount_ClearBoundaryState();
    sOverworldMountState.walkEndState =
        endState == OVERWORLD_MOUNT_WALK_END_PENDING
            ? OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY
            : OVERWORLD_MOUNT_WALK_END_NONE;
    return TRUE;
}

static BOOL OverworldMount_CanControl(FIELD_PLAYER_AVATAR *avatar)
{
    return sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && sOverworldMountState.presentationAttached
        && (OVERWORLD_MOUNT_BOUNDARY_FLAGS
            & OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING) == 0
        && avatar != NULL
        && sOverworldMountState.fieldSystem != NULL
        && sOverworldMountState.fieldSystem->playerAvatar == avatar
        && avatar->state == PLAYER_STATE_WALKING
        && (avatar->unk0 & OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT) == 0;
}

static int OverworldMount_DirectionDeltaX(u8 direction)
{
    return OverworldWalk_DeltaX(direction);
}

static int OverworldMount_DirectionDeltaY(u8 direction)
{
    return OverworldWalk_DeltaY(direction);
}

static BOOL __attribute__((optimize("Os")))
OverworldMount_RequestTeleportPlan(
    const OverworldWildBehaviorProfileData *lane,
    LocalMapObject *player,
    u8 direction,
    OverworldMotionPlan *plan)
{
    OverworldMountTeleportWorldContext world;
    OverworldActorTeleportPlanCall planCall;
    OverworldActorMotionRequestCall request;

    world.player = player;
    memset(&planCall, 0, sizeof(planCall));
    planCall.lane = lane;
    planCall.directions = &direction;
    planCall.classify = OverworldMount_ClassifyTeleportCandidate;
    planCall.world = &world;
    planCall.targetMode = OVERWORLD_ACTOR_TELEPORT_TARGET_DIRECTIONAL;
    planCall.directionCount = 1;
    planCall.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;
    memset(&request, 0, sizeof(request));
    request.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    request.size = sizeof(request);
    request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT;
    request.actorSlot = OW_WILD_FOLLOWER_SLOT;
    request.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());
    request.startX = sOverworldMountState.motionStartX;
    request.startY = sOverworldMountState.motionStartY;
    request.startBaseY = sOverworldMountState.motionStartBaseY;
    request.plan = plan;
    request.teleportPlan = &planCall;
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request)
            != OVERWORLD_ACTOR_RESULT_OK
        || request.decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return FALSE;
    }
    sOverworldMountState.motionIdentity = request.motionIdentity;
    OverworldMount_ClearBoundaryState();
    return TRUE;
}

static BOOL __attribute__((noinline, optimize("Os"),
    section(".overworld_mount_motion")))
OverworldMount_PlanHopTrajectory(
    u8 distance,
    u32 *trajectory)
{
    OverworldMountActionCall call = { 0 };

    call.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
    call.size = sizeof(call);
    call.operation = OVERWORLD_MOUNT_ACTION_PLAN_HOP_TRAJECTORY;
    call.action = distance;
    call.state = &sOverworldMountState;
    call.avatar = sOverworldMountState.fieldSystem->playerAvatar;
    call.trajectory = trajectory;
    return OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&call);
}

static void __attribute__((section(".overworld_mount_motion")))
OverworldMount_ApplyTeleportVisibility(BOOL visible)
{
    LocalMapObject *follower = OverworldMount_GetFollowerObject();
    LocalMapObject *player;

    if (follower == NULL || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    player = sOverworldMountState.fieldSystem->playerAvatar->mapObject;
    if (visible) {
        player->flags &= ~BIT_VANISH;
        follower->flags &= ~BIT_VANISH;
        if (!sOverworldMountState.savedFollowerShadowSuppressed) {
            follower->flags &= ~MAPOBJECTFLAG_UNK20;
        }
    } else {
        player->flags |= BIT_VANISH;
        follower->flags |= BIT_VANISH | MAPOBJECTFLAG_UNK20;
    }
}

static void OverworldMount_CommitMotionTarget(LocalMapObject *player)
{
    s32 targetBaseY = sOverworldMountState.motionTargetBaseY;

    player->posVec[0] = ((u32)(u16)sOverworldMountState.motionTargetX << 16)
        + 0x8000;
    player->posVec[1] = (u32)targetBaseY;
    player->posVec[2] = ((u32)(u16)sOverworldMountState.motionTargetY << 16)
        + 0x8000;
    /* Use the engine's relocation protocol so current/previous logical tiles,
     * height, facing backups, held movement, and single-movement ownership all
     * agree with the rendered landing position. */
    MapObject_SetPositionFromVectorAndDirection(
        player,
        (VecFx32 *)player->posVec,
        player->curFacing);
    player->faceVec[1] = (u32)((s32)sOverworldMountState.playerBaseFaceY
        + OVERWORLD_MOUNT_RIDER_HEIGHT_FX32);
    player->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
}

static BOOL __attribute__((noinline, section(".overworld_mount_streaming")))
OverworldMount_UpdateLandStreamAnchor(void)
{
    if (!sOverworldMountState.motionStreamPreparing) {
        return TRUE;
    }
    return OverworldMount_ApplyTerrainStream(
            OVERWORLD_FIELD_TERRAIN_STREAM_POLL)
        == OVERWORLD_FIELD_TERRAIN_STREAM_READY;
}

static void __attribute__((noinline)) OverworldMount_DrainLandStream(void)
{
    BOOL streamReady;

    if (!OverworldMount_FinalizeIsPending()
        || sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_NONE
        || !OverworldMount_HasCurrentPlayer()
        || (OVERWORLD_MOUNT_BOUNDARY_FLAGS
            & OVERWORLD_MOUNT_BOUNDARY_HAS_APPLIED_PATH) == 0) {
        return;
    }
    /* Without a prepared anchor, cardinal Walk remains bound to the normal
     * live player streamer. This adapter owns no extra terrain receipt to
     * wait for. Diagonal and long motion still drain their staged anchor. */
    streamReady = !sOverworldMountState.motionStreamPreparing
        || OverworldMount_UpdateLandStreamAnchor();
    if (!streamReady) {
        return;
    }
    if (sOverworldMountState.motionStreamPreparing) {
        if (!OverworldMount_ReleaseTerrainStream()) {
            return;
        }
    }
    (void)OverworldMount_AcknowledgeSharedMotion(
        OVERWORLD_ACTOR_BOUNDARY_STREAM_READY,
        OverworldMount_GetAppliedThrough(),
        NULL);
}

static BOOL __attribute__((noinline))
OverworldMount_BeginSharedMotion(BOOL advanceFirstFrame)
{
    OverworldActorMotionRequestCall call;
    OverworldMotionIntent intent;
    OverworldMotionCandidate candidate;
    int distanceX;
    int distanceY;

    intent.version = OVERWORLD_MOTION_MODEL_VERSION;
    intent.kind = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        ? (sOverworldMountState.reservedPolicyState[
                OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX]
                & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0
            ? OVERWORLD_MOTION_KIND_SKID
            : OVERWORLD_MOTION_KIND_WALK
        : OVERWORLD_MOTION_KIND_HOP;
    intent.facing = sOverworldMountState.motionDirection;
    intent.fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());
    intent.behaviorFingerprint = 0;
    intent.duration = sOverworldMountState.motionFrameCount;
    distanceX = sOverworldMountState.motionTargetX
        - sOverworldMountState.motionStartX;
    distanceY = sOverworldMountState.motionTargetY
        - sOverworldMountState.motionStartY;
    /* Keep the signed tile delta until travel has been selected. Facing can
     * differ on a skid, and a stock held Walk need not have a saved proposal. */
    candidate.direction = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        ? OverworldWalk_DirectionFromDelta(distanceX, distanceY)
        : sOverworldMountState.motionDirection;
    if (distanceX < 0) {
        distanceX = -distanceX;
    }
    if (distanceY < 0) {
        distanceY = -distanceY;
    }
    intent.arcHeightQ4 = sOverworldMountState.motionArcHeightQ4;
    intent.spinSpeed = 0;
    intent.swayWidth = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        ? sOverworldMountState.snapshot.profile.walkSwayWidth : 0;
    intent.visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_VISIBLE;
    intent.pauseFrames = sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK
        ? OverworldWildSpawns_ResolveWalkPause(
            &sOverworldMountState.snapshot.profile) : 0;
    if (intent.kind == OVERWORLD_MOTION_KIND_HOP) {
        intent.spinSpeed = sOverworldMountState.motionFlicker & 0x0F;
        intent.swayWidth = sOverworldMountState.motionFlicker >> 4;
        intent.visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_VISIBLE;
    }
    intent.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;
    intent.commitPolicy = OVERWORLD_MOTION_COMMIT_NORMAL;
    intent.flags = 0;

    candidate.targetX = sOverworldMountState.motionTargetX;
    candidate.targetY = sOverworldMountState.motionTargetY;
    candidate.targetBaseY = sOverworldMountState.motionTargetBaseY;
    candidate.rejectionFlags = 0;
    candidate.distance = (u8)(distanceX > distanceY ? distanceX : distanceY);

    call.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    call.size = sizeof(call);
    call.actorSlot = OW_WILD_FOLLOWER_SLOT;
    call.operation = OVERWORLD_ACTOR_MOTION_SERVICE_REQUEST;
    call.candidateCount = 1;
    call.reserved = advanceFirstFrame;
    call.startX = sOverworldMountState.motionStartX;
    call.startY = sOverworldMountState.motionStartY;
    call.startBaseY = sOverworldMountState.motionStartBaseY;
    call.intent = &intent;
    call.candidates = &candidate;
    call.plan = NULL;
    call.targetSurfaceId = OverworldMount_GetSurfaceId(
        candidate.targetX,
        candidate.targetY);
    if (OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&call)
            == OVERWORLD_ACTOR_RESULT_OK
        && call.decision == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        sOverworldMountState.motionIdentity = call.motionIdentity;
        if (intent.kind == OVERWORLD_MOTION_KIND_WALK) {
            sOverworldMountState.reservedPolicyProfile[
                OVERWORLD_MOUNT_WALK_PAUSE_INDEX] =
                intent.pauseFrames;
        }
        OverworldMount_ClearBoundaryState();
        return TRUE;
    }
    return FALSE;
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_CancelSharedMotion(u8 reason)
{
    OverworldActorMotionBoundaryCall call;

    memset(&call, 0, sizeof(call));
    call.version = OVERWORLD_ACTOR_MOTION_CALL_VERSION;
    call.size = sizeof(call);
    call.actorSlot = OW_WILD_FOLLOWER_SLOT;
    call.operation = OVERWORLD_ACTOR_MOTION_SERVICE_ENGINE_BOUNDARY;
    call.acknowledgements = OVERWORLD_ACTOR_BOUNDARY_CANCEL;
    call.cancelReason = reason;
    call.motionIdentity = sOverworldMountState.motionIdentity;
    call.sample = NULL;
    (void)OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->boundary(&call);
}

static void OverworldMount_FinishCustomMotion(void)
{
    FIELD_PLAYER_AVATAR *avatar;
    LocalMapObject *follower;
    LocalMapObject *player;
    OverworldMotionSample finalSample;
    u16 pause;
    u8 finishedMotion;
    BOOL walkMotion;

    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        || !OverworldMount_HasCurrentPlayer()) {
        sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        sOverworldMountState.motionStreamPreparing = FALSE;
        sOverworldMountState.motionLandingPauseStarted = FALSE;
        return;
    }
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_CRASH) {
        sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
        sOverworldMountState.motionElapsed = 0;
        sOverworldMountState.motionFrameCount = 0;
        sOverworldMountState.motionLandingPauseStarted = FALSE;
        return;
    }
    avatar = sOverworldMountState.fieldSystem->playerAvatar;
    player = avatar->mapObject;
    follower = OverworldMount_GetFollowerObject();
    finishedMotion = sOverworldMountState.snapshot.motionMode;
    walkMotion = finishedMotion == OVERWORLD_MOUNT_MOTION_WALK;
    pause = walkMotion
        ? sOverworldMountState.reservedPolicyProfile[
            OVERWORLD_MOUNT_WALK_PAUSE_INDEX]
        : finishedMotion == OVERWORLD_MOUNT_MOTION_TELEPORT
            ? sOverworldMountState.motionArcHeightQ4
            : sOverworldMountState.walkEndState
                    == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP
                ? 0
            : sOverworldMountState.snapshot.profile.hopPause;
    if (!sOverworldMountState.motionLandingPauseStarted) {
        sOverworldMountState.motionCooldown = pause;
    }
    if (!walkMotion) {
        OverworldMount_CommitMotionTarget(player);
    }
    if (walkMotion) {
        /* Keep the stationary command alive through the next player update.
         * That gives vanilla exactly one real END boundary for step scripts,
         * encounters, map connections, and warps. Relocation would clear the
         * command before that boundary can be observed. */
        player->xPrev = player->xCurr;
        player->hPrev = player->hCurr;
        player->yPrev = player->yCurr;
        player->xCurr = sOverworldMountState.motionTargetX;
        player->hCurr = sOverworldMountState.motionTargetBaseY >> 15;
        player->yCurr = sOverworldMountState.motionTargetY;
        player->posVec[0] =
            ((u32)(u16)sOverworldMountState.motionTargetX << 16) + 0x8000;
        player->posVec[1] = (u32)sOverworldMountState.motionTargetBaseY;
        player->posVec[2] =
            ((u32)(u16)sOverworldMountState.motionTargetY << 16) + 0x8000;
    }
    memset(&finalSample, 0, sizeof(finalSample));
    if (OverworldMount_AcknowledgeSharedMotion(
            0,
            OverworldMount_GetAppliedThrough(),
            &finalSample)
        && (finalSample.flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
        OverworldMount_SetAppliedThrough(finalSample.lastPathAdvance);
    }
    OVERWORLD_MOUNT_BOUNDARY_FLAGS |=
        OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE
        | OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING;
    OVERWORLD_MOUNT_BOUNDARY_MOTION = finishedMotion;
    if (walkMotion) {
        OverworldMount_FinishOneFrameWalk(avatar);
    } else {
        OverworldMount_ClearObjectCommand(player);
    }
    if (follower != NULL) {
        OverworldMount_ClearObjectCommand(follower);
    }
    OverworldMount_ApplyTeleportVisibility(TRUE);
    if (!walkMotion) {
        if (OverworldMount_AcknowledgeSharedMotion(
                OVERWORLD_ACTOR_BOUNDARY_ENGINE_END,
                OverworldMount_GetAppliedThrough(),
                NULL)) {
            OVERWORLD_MOUNT_BOUNDARY_FLAGS |=
                OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN;
        }
    }
    sOverworldMountState.snapshot.motionMode = OVERWORLD_MOUNT_MOTION_NONE;
    sOverworldMountState.motionElapsed = 0;
    sOverworldMountState.motionFrameCount = 0;
    sOverworldMountState.motionLandingPauseStarted = FALSE;
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    OverworldMount_SyncPresentation();
}

static BOOL OverworldMount_TryFinalizeSharedMotion(void)
{
    FIELD_PLAYER_AVATAR *avatar;
    OverworldMotionSample sample;
    u8 finishedMotion;

    if (!OverworldMount_FinalizeIsPending()) {
        return FALSE;
    }
    finishedMotion = OVERWORLD_MOUNT_BOUNDARY_MOTION;
    if (finishedMotion != OVERWORLD_MOUNT_MOTION_WALK
        && (OVERWORLD_MOUNT_BOUNDARY_FLAGS
            & OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN) == 0
        && OverworldMount_AcknowledgeSharedMotion(
            OVERWORLD_ACTOR_BOUNDARY_ENGINE_END,
            OverworldMount_GetAppliedThrough(),
            NULL)) {
        OVERWORLD_MOUNT_BOUNDARY_FLAGS |=
            OVERWORLD_MOUNT_BOUNDARY_ENGINE_END_SEEN;
    }
    if ((OVERWORLD_MOUNT_BOUNDARY_FLAGS
            & OVERWORLD_MOUNT_BOUNDARY_HAS_APPLIED_PATH) == 0) {
        memset(&sample, 0, sizeof(sample));
        if (OverworldMount_AcknowledgeSharedMotion(0, 0, &sample)
            && (sample.flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
            OverworldMount_SetAppliedThrough(sample.lastPathAdvance);
        }
    } else {
        (void)OverworldMount_AcknowledgeSharedMotion(
            0,
            OverworldMount_GetAppliedThrough(),
            NULL);
    }
    avatar = OverworldMount_HasCurrentPlayer()
        ? sOverworldMountState.fieldSystem->playerAvatar
        : NULL;
    if (finishedMotion == OVERWORLD_MOUNT_MOTION_WALK) {
        /* Only a receipt created by the real player-step bridge can enter
         * these states. Retry its terminal actor commit after streaming adds
         * the remaining acknowledgement. */
        if ((sOverworldMountState.walkEndState
                & OVERWORLD_MOUNT_WALK_END_PENDING) != 0) {
            return OverworldMount_CompletePendingStep(avatar);
        }
        return FALSE;
    }
    if (OVERWORLD_MOUNT_BOUNDARY_PHASE != OVERWORLD_MOTION_PHASE_IDLE
        && OVERWORLD_MOUNT_BOUNDARY_PHASE
            != OVERWORLD_MOTION_PHASE_SETTLING) {
        return FALSE;
    }
    if (avatar != NULL) {
        avatar->unk0 &= ~OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
    }
    OverworldMount_ClearBoundaryState();
    if (avatar != NULL) {
        OverworldMount_ResetAvatarAfterCancel(avatar);
    }
    OverworldMount_ResetMomentum();
    sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
    return FALSE;
}

static void __attribute__((noinline, section(".overworld_mount_motion")))
OverworldMount_UpdateCustomMotion(void)
{
    FIELD_PLAYER_AVATAR *avatar;
    LocalMapObject *player;
    s32 baseX;
    s32 baseZ;
    s32 baseY;
    s32 arc;
    OverworldMotionSample sample;

    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_NONE
        || !OverworldMount_HasCurrentPlayer()) {
        return;
    }
    avatar = sOverworldMountState.fieldSystem->playerAvatar;
    player = avatar->mapObject;
    if ((sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_HOP
            || sOverworldMountState.snapshot.motionMode
                == OVERWORLD_MOUNT_MOTION_TELEPORT)
        && sOverworldMountState.motionElapsed
            >= sOverworldMountState.motionFrameCount
        && !sOverworldMountState.motionLandingPauseStarted) {
        /* The authored pause starts when the actor visibly lands. Any final
         * terrain-stream drain overlaps that pause instead of extending it. */
        sOverworldMountState.motionCooldown =
            sOverworldMountState.snapshot.motionMode
                    == OVERWORLD_MOUNT_MOTION_TELEPORT
                ? sOverworldMountState.motionArcHeightQ4
                : sOverworldMountState.walkEndState
                        == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP
                    ? 0
                : sOverworldMountState.snapshot.profile.hopPause;
        sOverworldMountState.motionLandingPauseStarted = TRUE;
    }
    (void)OverworldMount_UpdateLandStreamAnchor();
    if (sOverworldMountState.motionElapsed
        >= sOverworldMountState.motionFrameCount) {
        OverworldMount_FinishCustomMotion();
        return;
    }
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_CRASH) {
        sOverworldMountState.motionElapsed++;
        return;
    }
    if (!OverworldMount_AcknowledgeSharedMotion(
            0,
            OverworldMount_GetAppliedThrough(),
            &sample)) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
        return;
    }
    sOverworldMountState.motionElapsed = sample.elapsed;
    if (sOverworldMountState.snapshot.motionMode
        == OVERWORLD_MOUNT_MOTION_TELEPORT) {
        OverworldMount_ApplyTeleportVisibility(sample.visible);
        return;
    }

    baseX = sample.renderX;
    baseZ = sample.renderZ;
    baseY = sample.baseY;
    arc = sample.heightOffset;
    player->posVec[0] = (u32)baseX;
    player->posVec[1] = (u32)baseY;
    player->posVec[2] = (u32)baseZ;
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_WALK) {
        if (sOverworldMountState.motionStartY
                == sOverworldMountState.motionTargetY) {
            baseZ -= sample.swayOffset;
        } else {
            baseX -= sample.swayOffset;
        }
        if (player->xCurr != baseX >> 16
            || player->yCurr != baseZ >> 16) {
            player->xPrev = player->xCurr;
            player->yPrev = player->yCurr;
            player->xCurr = baseX >> 16;
            player->yCurr = baseZ >> 16;
        }
    }
    player->hCurr = baseY >> 15;
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_HOP
        && (sample.flags & OVERWORLD_MOTION_TICK_PATH_ADVANCED) != 0) {
        OverworldMount_SetAppliedThrough(sample.lastPathAdvance);
    }
    player->faceVec[1] = (u32)(arc
        + (s32)sOverworldMountState.playerBaseFaceY
        + OVERWORLD_MOUNT_RIDER_HEIGHT_FX32);
    player->unk88[1] = sOverworldMountState.playerBaseUnk88Y;
    sOverworldMountState.lastAppliedPlayerFaceY = player->faceVec[1];
    sOverworldMountState.lastAppliedPlayerUnk88Y = player->unk88[1];
    if (sOverworldMountState.snapshot.motionMode
            == OVERWORLD_MOUNT_MOTION_WALK) {
        if (sOverworldMountState.motionElapsed
            >= sOverworldMountState.motionFrameCount) {
            /* Commit on the Nth update. The stationary player command stays
             * active so vanilla still emits one movement-end boundary next. */
            OverworldMount_FinishCustomMotion();
            return;
        }
        /* PlayerAvatar_UpdateMovement runs before this controller. Hold its
         * state at MOVING until the visual step reaches the destination. */
        avatar->unk10 = 1;
        avatar->unk14 = 2;
        return;
    }
    if ((sOverworldMountState.motionFlicker & 0x0F) != 0) {
        OverworldMount_SetMountedFacing(sample.facing);
    }
}

typedef struct OverworldMountHopSearch {
    u8 lateral;
    u8 distance;
    u8 side;
} OverworldMountHopSearch;

static BOOL __attribute__((noinline, section(".overworld_mount_hop_search")))
OverworldMount_TryNextHopLandingCandidate(
    const OverworldWildBehaviorProfileData *lane,
    u8 direction,
    u8 minDistance,
    u8 maxDistance,
    OverworldMountHopSearch *search)
{
    int forwardX = OverworldMount_DirectionDeltaX(direction);
    int forwardY = OverworldMount_DirectionDeltaY(direction);
    int lateralMagnitude;
    int lateral;
    int sideCount;
    int targetX;
    int targetY;

    while (search->lateral <= maxDistance) {
        if (search->distance < minDistance) {
            search->lateral++;
            search->distance = maxDistance;
            search->side = 0;
            continue;
        }
        lateralMagnitude = search->lateral == maxDistance
            ? search->distance
            : search->lateral;
        if (search->lateral != maxDistance
            && lateralMagnitude >= search->distance) {
            search->distance--;
            search->side = 0;
            continue;
        }
        sideCount = lateralMagnitude == 0 ? 1 : 2;
        if (search->side >= sideCount) {
            search->distance--;
            search->side = 0;
            continue;
        }
        lateral = search->side++ == 0
            ? lateralMagnitude
            : -lateralMagnitude;
        if ((lateral == 0
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(
                    lane->hopAllowNonCardinal))
            || (lateral != 0
                && !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                    lane->hopAllowNonCardinal))) {
            continue;
        }
        targetX = sOverworldMountState.motionStartX
            + forwardX * search->distance - forwardY * lateral;
        targetY = sOverworldMountState.motionStartY
            + forwardY * search->distance + forwardX * lateral;
        if (!OverworldMount_IsLandingTileAllowed(targetX, targetY)) {
            continue;
        }
        sOverworldMountState.motionTargetX = (s16)targetX;
        sOverworldMountState.motionTargetY = (s16)targetY;
        return TRUE;
    }
    return FALSE;
}

static BOOL __attribute__((noinline, optimize("Os"), section(".overworld_mount_motion")))
OverworldMount_TryStartCustomMotion(
    FIELD_PLAYER_AVATAR *avatar,
    u8 direction,
    u8 facingDirection,
    BOOL advanceFirstFrame)
{
    const OverworldWildBehaviorProfileData *lane =
        &sOverworldMountState.snapshot.profile;
    LocalMapObject *follower;
    LocalMapObject *player;
    u8 rawLocomotion = lane->chillAction;
    u8 minDistance;
    u8 maxDistance;
    int startX;
    int startY;
    int targetX = 0;
    int targetY = 0;
    int distance;
    OverworldMountHopSearch hopSearch;
    OverworldMotionPlan teleportPlan;
    BOOL actorMotionStarted = FALSE;
    u32 trajectory = 0;
    u32 frames;
    u8 roleIntent;

    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK) {
        BOOL started;

        if (direction >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
            && !OverworldMount_TerrainStreamIsIdle()) {
            return FALSE;
        }
        follower = OverworldMount_GetFollowerObject();
        started = OverworldWalk_StartMountedFlat(
            &sOverworldMountState,
            avatar,
            follower,
            direction,
            facingDirection,
            advanceFirstFrame,
            OverworldMount_BeginWalkMotion);
        if (started
            && direction >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
            && !OverworldMount_BeginTerrainStream()) {
            OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
            return FALSE;
        }
        return started;
    }

    /* The caller establishes player ownership and validates Walk collision. */
    if (sOverworldMountState.motionCooldown != 0
        || sOverworldMountState.motionStreamPreparing) {
        return sOverworldMountState.walkEndState
            == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP ? 2 : FALSE;
    }
    if (rawLocomotion != OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        && !OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(rawLocomotion)) {
        return FALSE;
    }
    player = avatar->mapObject;
    follower = OverworldMount_GetFollowerObject();
    /* A seamless map connection can leave rolling-land work pending for a
     * few frames after the mount has rebound to the new map. Starting a new
     * custom motion in that window can occupy the stream anchor indefinitely
     * at its landing frame. The input hook still consumes the held direction,
     * so simply defer the Hop/Teleport until the stock loader is idle. */
    if (follower == NULL || !OverworldMount_TerrainStreamIsIdle()) {
        return sOverworldMountState.walkEndState
            == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP ? 2 : FALSE;
    }
    roleIntent = rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        ? OVERWORLD_ROLE_CONTROLLER_INTENT_HOP
        : OVERWORLD_ROLE_CONTROLLER_INTENT_TELEPORT;
    direction = OverworldMount_ReduceRole(
        OVERWORLD_ROLE_CONTROLLER_ROLE_MOUNTED
            | OVERWORLD_ROLE_CONTROLLER_EVENT_REQUEST << 8
            | (u32)roleIntent << 16 | (u32)direction << 24,
        direction);
    if (direction > OVERWORLD_ROLE_CONTROLLER_DIRECTION_MAX) {
        return FALSE;
    }
    startX = player->xCurr;
    startY = player->yCurr;
    sOverworldMountState.motionStartBaseY = (s32)player->posVec[1];
    sOverworldMountState.motionStartX = (s16)startX;
    sOverworldMountState.motionStartY = (s16)startY;
    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        if (sOverworldMountState.walkEndState
                == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP) {
            OverworldMountActionCall actionCall = { 0 };

            actionCall.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
            actionCall.size = sizeof(actionCall);
            actionCall.operation = OVERWORLD_MOUNT_ACTION_CHAIN_FORWARD_TARGET;
            actionCall.direction = direction;
            actionCall.state = &sOverworldMountState;
            actionCall.avatar = avatar;
            if (!OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&actionCall)) {
                return FALSE;
            }
            distance = 2;
            targetX = sOverworldMountState.motionTargetX;
            targetY = sOverworldMountState.motionTargetY;
            sOverworldMountState.motionTargetBaseY =
                OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
                    sOverworldMountState.fieldSystem,
                    sOverworldMountState.surfaceCatalog,
                    player,
                    targetX,
                    targetY);
            if (!OverworldMount_PlanHopTrajectory(
                    (u8)distance, &trajectory)) {
                return FALSE;
            }
            goto hop_target_found;
        }
        minDistance = lane->hopMinDistance != 0 ? lane->hopMinDistance : 1;
        maxDistance = lane->hopMaxDistance >= minDistance
            ? lane->hopMaxDistance
            : minDistance;
        if (maxDistance > OVERWORLD_MOUNT_HOP_MAX_DISTANCE) {
            maxDistance = OVERWORLD_MOUNT_HOP_MAX_DISTANCE;
        }
        /* Preserve the requested heading as closely as possible. Try every
         * straight landing first, then widen the lateral miss one tile at a
         * time. Equal-axis (45 degree) diagonals are the final fallback. */
        hopSearch.lateral = 0;
        hopSearch.distance = maxDistance;
        hopSearch.side = 0;
        while (OverworldMount_TryNextHopLandingCandidate(
                lane,
                direction,
                minDistance,
                maxDistance,
                &hopSearch)) {
            distance = hopSearch.distance;
            targetX = sOverworldMountState.motionTargetX;
            targetY = sOverworldMountState.motionTargetY;
            sOverworldMountState.motionTargetBaseY =
                OVERWORLD_WILD_RUNTIME_OVERLAY_ENTRY->getGroundBaseY(
                sOverworldMountState.fieldSystem,
                sOverworldMountState.surfaceCatalog,
                player,
                targetX,
                targetY);
            if (OverworldMount_PlanHopTrajectory(
                    (u8)distance,
                    &trajectory)) {
                sOverworldMountState.motionTargetX = (s16)targetX;
                sOverworldMountState.motionTargetY = (s16)targetY;
                goto hop_target_found;
            }
        }
        return FALSE;
hop_target_found:
        ;
    } else {
        if (!OverworldMount_RequestTeleportPlan(
                lane,
                player,
                direction,
                &teleportPlan)) {
            return FALSE;
        }
        actorMotionStarted = TRUE;
        sOverworldMountState.motionTargetBaseY = teleportPlan.targetBaseY;
        sOverworldMountState.motionTargetX = teleportPlan.targetX;
        sOverworldMountState.motionTargetY = teleportPlan.targetY;
    }
    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP) {
        /* Chain HOP_FORWARD is always two tiles at current Walk time. */
        frames = sOverworldMountState.walkEndState
                == OVERWORLD_MOUNT_WALK_END_CHAIN_HOP
            ? (u32)lane->hopTime << 1 : trajectory & 0xFFFF;
        if (frames == 0) {
            frames = 1;
        }
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_HOP;
        sOverworldMountState.motionArcHeightQ4 = (u8)(trajectory >> 16);
        sOverworldMountState.motionFlicker =
            (u8)((lane->hopSwayWidth << 4)
                | (lane->hopSpinSpeed & 0x0F));
    } else {
        frames = teleportPlan.duration;
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_TELEPORT;
        /* Teleport has no arc. Reuse this fixed-layout byte to carry the
         * Actor Motion planner's selected pause into the engine adapter. */
        sOverworldMountState.motionArcHeightQ4 = teleportPlan.pauseFrames;
        sOverworldMountState.motionFlicker = (u8)(
            (teleportPlan.visibilityPolicy
                == OVERWORLD_MOTION_VISIBILITY_FLICKER) << 4);
    }
    /* A spinning Hop starts from the mounted pair's current facing, matching
     * wild custom jumps. Non-spinning motion still faces its travel heading. */
    sOverworldMountState.motionDirection = direction;
    if ((sOverworldMountState.motionFlicker & 0x0F) != 0) {
        sOverworldMountState.motionDirection = player->curFacing;
    }
    sOverworldMountState.savedFollowerShadowSuppressed =
        (follower->flags & MAPOBJECTFLAG_UNK20) != 0;
    sOverworldMountState.motionLandingPauseStarted = FALSE;
    sOverworldMountState.motionFrameCount = (u16)frames;
    sOverworldMountState.motionElapsed = 0;
    if (!actorMotionStarted && !OverworldMount_BeginSharedMotion(FALSE)) {
        sOverworldMountState.snapshot.motionMode =
            OVERWORLD_MOUNT_MOTION_NONE;
        return FALSE;
    }
    avatar->unk0 |= OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT;
    OverworldMount_ResetAvatarAfterCancel(avatar);
    /* Normalize any just-finished stock step before custom motion takes
     * ownership. This prevents a stale SINGLE_MOVEMENT flag from surviving
     * the entire jump and blocking control after landing. */
    MapObject_SetPositionFromVectorAndDirection(
        player,
        (VecFx32 *)player->posVec,
        sOverworldMountState.motionDirection);
    OverworldMount_SetMountedFacing(sOverworldMountState.motionDirection);
    /* Match the existing Pokémon custom-jump shell: both render objects run
     * the same stationary held command while the mount controller owns their
     * shared position and render offsets. This prevents either object's
     * ordinary animation callback from adding an independent movement. */
    MapObject_StartMovementCommandInternal(
        player,
        OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND);
    MapObject_StartMovementCommandInternal(
        follower,
        OVERWORLD_MOUNT_CUSTOM_MOTION_FREEZE_COMMAND);
    if (!OverworldMount_BeginTerrainStream()) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_CONTEXT_LOST);
        return FALSE;
    }
    OverworldMount_ResetMomentum();
    if (frames == 0) {
        OverworldMount_UpdateCustomMotion();
        OverworldMount_DrainLandStream();
        (void)OverworldMount_TryFinalizeSharedMotion();
    }
    return TRUE;
}

static BOOL __attribute__((noinline)) OverworldMount_HandleCustomInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    u8 rawLocomotion = sOverworldMountState.snapshot.profile.chillAction;
    u8 direction;

    /* This hook is resident even after a mount session ends. A canceled Hop
     * can lose its old field context before its object cleanup is safe, so a
     * stale motion byte must never be allowed to consume controls by itself. */
    if (sOverworldMountState.snapshot.phase
            != OVERWORLD_MOUNT_PHASE_RIDING
        || !sOverworldMountState.presentationAttached
        || avatar == NULL
        || sOverworldMountState.fieldSystem == NULL
        || sOverworldMountState.fieldSystem->playerAvatar != avatar) {
        return FALSE;
    }
    if (sOverworldMountState.snapshot.motionMode
            != OVERWORLD_MOUNT_MOTION_NONE
        || OverworldMount_FinalizeIsPending()) {
        return TRUE;
    }
    direction = OverworldMount_GetInputDirection(*newKeys | *heldKeys);
    if (direction >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
        && direction <= OVERWORLD_MOUNT_DIRECTION_SOUTH_EAST) {
        direction = OverworldWalk_DiagonalFacing(
            avatar->mapObject,
            direction,
            *newKeys);
    }
    if (rawLocomotion == OW_WILD_BEHAVIOR_LOCOMOTION_HOP
        || OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(rawLocomotion)) {
        /* Overlay 1 asks the stock avatar collision helper about held input
         * after a custom Hop commits. That query changes unk10 to TURNING as
         * a side effect. Stock walking clears it on its next movement call,
         * but custom locomotion owns that call and must clear the stale state
         * itself. Otherwise field input stays unready and controls appear to
         * lock after landing, especially beside blocked tiles. */
        if (avatar->unk10 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE
            || avatar->unk14 != OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE) {
            OverworldMount_ResetAvatarAfterCancel(avatar);
        }
        if (direction != OVERWORLD_MOUNT_DIRECTION_NONE
            && OverworldMount_CanControl(avatar)) {
            (void)OverworldMount_TryStartCustomMotion(
                avatar,
                direction,
                direction,
                FALSE);
        }
        /* Custom locomotion owns the player for its complete idle/move/pause
         * cycle. Letting an idle frame reach stock control can start a second
         * movement state from the map object's stationary command. */
        return TRUE;
    }
    if (sOverworldMountState.motionCooldown != 0) {
        /* Field input has already resolved its direction before this wrapper.
         * Calling stock control with cleared key masks can still start that
         * stale direction and leave the avatar in MOVE_STATE_START after a
         * Hop landing. Consume the whole control call during the pause. */
        return TRUE;
    }
    return FALSE;
}

static void __attribute__((noinline, section(".overworld_mount_control_gap")))
OverworldMount_FilterMovementInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys)
{
    OverworldWalk_FilterMountedInput(
        &sOverworldMountState,
        avatar,
        newKeys,
        heldKeys);
}

static BOOL __attribute__((noinline))
OverworldMount_TryHandleDiagonalWalk(
    FIELD_PLAYER_AVATAR *avatar,
    u32 newKeys,
    u32 heldKeys,
    BOOL advanceFirstFrame)
{
    OverworldActorPolicyView policy;
    u8 requestedDirection;
    u8 facingDirection;

    OverworldMount_InspectPolicy(&policy);
    if (!OverworldMount_CanControl(avatar)
        || sOverworldMountState.snapshot.profile.chillAction
            != OW_WILD_BEHAVIOR_LOCOMOTION_WALK
        || sOverworldMountState.motionCooldown != 0) {
        return FALSE;
    }
    if (policy.pendingStep
        == OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED) {
        /* A flat diagonal tile still owns the stock movement-end boundary.
         * Do not start its successor before that boundary updates skid and
         * acceleration state. */
        return TRUE;
    }
    /* A diagonal tile streams X and Z as two cardinal land updates. Consume
     * held input while that anchor drains so the next tile cannot overrun it
     * or turn a loading wait into a false wall-crash response. */
    if (sOverworldMountState.motionStreamPreparing) {
        return TRUE;
    }
    requestedDirection = sOverworldMountState.reservedPolicyState[
        OVERWORLD_MOUNT_WALK_STEP_DIRECTION_INDEX];
    if (policy.pendingStep
            != OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL
        || requestedDirection == OVERWORLD_MOUNT_DIRECTION_NONE) {
        return FALSE;
    }
    {
        OverworldMountActionCall actionCall = { 0 };

        actionCall.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
        actionCall.size = sizeof(actionCall);
        actionCall.operation = OVERWORLD_MOUNT_ACTION_WALK_CORRIDOR;
        actionCall.direction = requestedDirection;
        actionCall.state = &sOverworldMountState;
        actionCall.avatar = avatar;
        if (!OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&actionCall)) {
            (void)OverworldMount_ApplyWalkPolicy(
                avatar, FALSE, FALSE);
            return TRUE;
        }
    }
    if (requestedDirection >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
        && !OverworldWalk_StrictDiagonalAllowed(
            &sOverworldMountState,
            avatar,
            requestedDirection)) {
        (void)OverworldMount_ApplyWalkPolicy(
            avatar,
            FALSE,
            FALSE);
        return TRUE;
    }
    if (requestedDirection >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST
        && !OverworldMount_TerrainStreamIsIdle()) {
        return TRUE;
    }
    facingDirection = sOverworldMountState.reservedPolicyState[
        OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX];
    if (facingDirection >= OVERWORLD_MOUNT_DIRECTION_NORTH_WEST) {
        /* FilterMountedInput rewrites keys to the old travel heading during a
         * skid. Use the requested diagonal's own keys for facing instead. */
        facingDirection = OverworldWalk_DiagonalFacing(
            avatar->mapObject,
            facingDirection,
            (sOverworldMountState.reservedPolicyState[
                    OVERWORLD_MOUNT_WALK_STEP_FLAGS_INDEX]
                    & OVERWORLD_ACTOR_WALK_STEP_SKID) != 0
                ? PAD_PLUS_KEY_MASK : newKeys);
    }
    (void)OverworldMount_ApplyWalkPolicy(
        avatar,
        OverworldMount_TryStartCustomMotion(
            avatar,
            requestedDirection,
            facingDirection,
            advanceFirstFrame),
        TRUE);
    return TRUE;
}

static BOOL OverworldMount_TryStartWalkFromInput(
    FIELD_PLAYER_AVATAR *avatar,
    u32 *newKeys,
    u32 *heldKeys,
    BOOL advanceFirstFrame)
{
    if (OverworldMount_CanControl(avatar)
        && sOverworldMountState.snapshot.profile.chillAction
            == OW_WILD_BEHAVIOR_LOCOMOTION_WALK
        /* Locked travel resolves the committed heading in the role reducer.
         * Raw keys must not bypass that direction or its crash policy. Keep
         * cardinal-only key normalization before the reducer, as before. */
        && ((sOverworldMountState.snapshot.profile.walkOptions
                & OW_WILD_BEHAVIOR_WALK_OPTION_LOCK_DIRECTION) == 0
            || !OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(
                sOverworldMountState.snapshot.profile
                    .hopAllowNonCardinal))
        && OverworldWalk_ResolveMountedDiagonal(
            &sOverworldMountState, avatar, newKeys, heldKeys) != 0) {
        return TRUE;
    }
    OverworldMount_FilterMovementInput(avatar, newKeys, heldKeys);
    return OverworldMount_TryHandleDiagonalWalk(
        avatar,
        *newKeys,
        *heldKeys,
        advanceFirstFrame);
}

static void __attribute__((noinline, used, optimize("Os")))
OverworldMount_ProcessPlayerControl(
    FIELD_PLAYER_AVATAR *avatar,
    u32 param1,
    s32 direction,
    u32 newKeys,
    u32 heldKeys,
    u32 param5)
{
    /* Finish the current stock tile, but do not admit another held step
     * while Select is waiting for the mount handoff. */
    if (sOverworldMountState.bufferedTogglePending) {
        newKeys &= ~PAD_PLUS_KEY_MASK;
        heldKeys &= ~PAD_PLUS_KEY_MASK;
    }
    if (sOverworldMountState.walkEndState
        == OVERWORLD_MOUNT_WALK_END_CONTINUATION_READY) {
        sOverworldMountState.walkEndState = OVERWORLD_MOUNT_WALK_END_NONE;
        /* Control runs before the actor tick updates directionInputHeld.
         * Decide this boundary from the keys supplied for this frame. */
        if (((newKeys | heldKeys) & PAD_PLUS_KEY_MASK) == 0) {
            /* NONE is a Walk-policy request. It can start the authored stop
             * skid; a direct reset would discard that motion and its pause. */
            (void)OverworldMount_TryStartWalkFromInput(
                avatar, &newKeys, &heldKeys, FALSE);
            return;
        }
        if (OverworldMount_TryStartWalkFromInput(
                avatar,
                &newKeys,
                &heldKeys,
                FALSE)) {
            /* Field input precedes the actor tick. Publish the origin here;
             * the normal tick advances both rider and mount once. Preloading
             * elapsed would skip the successor's first travel sample. */
            OverworldMount_UpdateCustomMotion();
            OverworldMount_SyncPresentation();
            return;
        }
    }
    if (OverworldMount_HandleCustomInput(avatar, &newKeys, &heldKeys)) {
        return;
    }
    if (OverworldMount_TryStartWalkFromInput(
            avatar,
            &newKeys,
            &heldKeys,
            FALSE)) {
        return;
    }
    PlayerAvatar_MoveControl(
        avatar,
        param1,
        direction,
        newKeys,
        heldKeys,
        param5);
}

void __attribute__((section(".overworld_mount_control"), noinline, used))
OverworldMount_PlayerMoveControl(
    FIELD_PLAYER_AVATAR *avatar,
    u32 param1,
    s32 direction,
    u32 newKeys,
    u32 heldKeys,
    u32 param5)
{
    OverworldMount_ChainControl(
        avatar, param1, direction, newKeys, heldKeys, param5);
}

void __attribute__((section(".overworld_mount_crash"), noinline, used))
OverworldMount_PlayCrashSound(u32 sequence)
{
    if (sOverworldMountState.snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING) {
        OverworldMount_StartWalkCrash();
        if (OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(
                sOverworldMountState.snapshot.profile.walkOptions)
            != OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT) {
            return;
        }
    }
    PlaySE(sequence);
}

void OverworldMount_IssueHeldMovement(
    FIELD_PLAYER_AVATAR *avatar,
    LocalMapObject *object,
    u32 vanillaCommand)
{
    u32 movementCommand = vanillaCommand;
    u8 direction;
    BOOL trackedStep = FALSE;
    BOOL mountedPlayer = OverworldMount_CanControl(avatar)
        && object == avatar->mapObject;

    if (mountedPlayer
        && OverworldMount_GetOrdinaryDirection(vanillaCommand, &direction)) {
        trackedStep = TRUE;
    } else if (mountedPlayer) {
        LocalMapObject *follower = OverworldMount_GetFollowerObject();

        /* Ledge jumps, bumps, forced steps, and other stock commands interrupt
         * ordinary Walk ownership. Clear any forced skid direction so the
         * special command cannot leave mounted input locked afterward. */
        if (follower != NULL) {
            OverworldMount_ClearObjectCommand(follower);
            OverworldMount_SyncPresentation();
        }
        OverworldMount_ResetMomentum();
    }
    if (trackedStep) {
        u8 facingDirection = direction;
        OverworldActorPolicyView policy;

        if (sOverworldMountState.snapshot.motionMode
                != OVERWORLD_MOUNT_MOTION_NONE) {
            /* The held-movement hook can run before the current exact-frame
             * Walk reaches its final update. Keep ownership with that motion;
             * replacing it here drops its last frame and logical boundary. */
            return;
        }
        OverworldMount_InspectPolicy(&policy);
        if (policy.pendingStep == OVERWORLD_ACTOR_WALK_PENDING_PROPOSAL) {
            /* The held-step hook receives the forced travel command. Keep the
             * reducer's separate facing when a turn skid owns that command. */
            facingDirection = sOverworldMountState.reservedPolicyState[
                OVERWORLD_MOUNT_WALK_FACING_DIRECTION_INDEX];
        }
        (void)OverworldMount_ApplyWalkPolicy(
            avatar,
            OverworldMount_TryStartCustomMotion(
                avatar,
                direction,
                facingDirection,
                FALSE),
            TRUE);
        return;
    }
    object->flags &= ~MAPOBJECTFLAG_UNK7;
    avatar->unk8 = movementCommand;
    MapObject_StartMovementCommandInternal(object, movementCommand);
}

static BOOL OverworldMount_CanToggle(FieldSystem *fieldSystem)
{
    FIELD_PLAYER_AVATAR *avatar;

    if (fieldSystem == NULL
        || fieldSystem->taskman != NULL
        || fieldSystem->playerAvatar == NULL) {
        return FALSE;
    }
    avatar = fieldSystem->playerAvatar;
    return !OverworldMount_FinalizeIsPending()
        && !sOverworldMountState.motionStreamPreparing
        && avatar->state == PLAYER_STATE_WALKING
        && (avatar->unk0 & OVERWORLD_MOUNT_AVATAR_FLAG_FORCED_MOVEMENT) == 0
        && avatar->unk14 == OVERWORLD_MOUNT_PLAYER_MOVE_STATE_NONE;
}

static void OverworldMount_HandleFollowerSelectionRequest(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state)
{
    volatile OverworldFollowerTransitionQueueStorage *queue =
        OVERWORLD_FOLLOWER_TRANSITION_QUEUE;
    OverworldWildSpawn *follower = &state->spawns[OW_WILD_FOLLOWER_SLOT];
    u8 request = queue->reserved;
    u8 partySlot = request
        & OVERWORLD_FOLLOWER_SELECTION_REQUEST_SLOT_MASK;
    u8 selectedSlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    u8 mount = request & OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT;

    if ((request & OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING) != 0) {
        (void)OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY->getSelectedPokemon(
            fieldSystem,
            &selectedSlot);
        if (!mount && selectedSlot == partySlot) {
            /* A second Y on the already selected follower only closes the
             * menu; it must not recall or respawn that follower. */
            queue->reserved = 0;
            return;
        }
        if (follower->active
            && state->activeFollowerPartySlot == partySlot) {
            if (!mount
                || (OverworldMount_IsActive() & OVERWORLD_MOUNT_ACTIVE_FLAG)
                || OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY
                    ->beginMountSelectedFollower(fieldSystem, state)) {
                queue->reserved = 0;
            }
            return;
        }
        if (queue->count != 0) {
            return;
        }
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_EXPLICIT);
        queue->reserved = mount
            ? OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT | partySlot
            : 0;
        (void)OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND(
            OVERWORLD_FOLLOWER_TRANSITION_QUEUE_DESPAWN_COMMAND);
        (void)OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND(partySlot + 1);
        return;
    }
    if (!mount || queue->count != 0) {
        return;
    }
    if (!follower->active
        || state->activeFollowerPartySlot != partySlot) {
        queue->reserved = 0;
    } else if ((OverworldMount_IsActive() & OVERWORLD_MOUNT_ACTIVE_FLAG)
        || OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY
            ->beginMountSelectedFollower(fieldSystem, state)) {
        queue->reserved = 0;
    }
}

static BOOL __attribute__((used)) OverworldMount_Tick(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 physicalKeys)
{
    u8 togglePressed = sOverworldMountState.bufferedTogglePending;
    OverworldActorPolicyView policy;
    OverworldMountActionCall actionCall = { 0 };

    sOverworldMountState.directionInputHeld =
        (u8)(physicalKeys & PAD_PLUS_KEY_MASK);

    if (!(OverworldMount_IsActive() & OVERWORLD_MOUNT_ACTIVE_FLAG)
        && sOverworldMountState.snapshot.reserved != 0) {
        sOverworldMountState.snapshot.reserved--;
    }

    OverworldMount_HandleFollowerSelectionRequest(fieldSystem, state);
    if (togglePressed
        && !OverworldFollowerSelector_IsActiveFlagSet()
        && !OverworldFollowerSelector_IsReleaseGated()
        && OverworldMount_CanToggle(fieldSystem)) {
        /* A buffered edge belongs to the mount controller until it is
         * accepted. Do not discard it merely because a Hop or a field update
         * made this particular frame unable to toggle. */
        sOverworldMountState.bufferedTogglePending = FALSE;
        if (OverworldMount_IsActive() & OVERWORLD_MOUNT_ACTIVE_FLAG) {
            OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_EXPLICIT);
        } else {
            (void)OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY
                ->beginMountSelectedFollower(fieldSystem, state);
        }
    }
    if (!(OverworldMount_IsActive() & OVERWORLD_MOUNT_ACTIVE_FLAG)) {
        return FALSE;
    }
    if (fieldSystem != sOverworldMountState.fieldSystem
        || !OverworldMount_BindingMatchesFollower(fieldSystem, state)) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_IDENTITY_CHANGED);
        return FALSE;
    }
    OverworldMount_ResumeCustomMotionAfterMapTransition();
    OverworldMount_InspectPolicy(&policy);
    if (policy.pendingStep
            == OVERWORLD_ACTOR_WALK_PENDING_ACCEPTED
        && policy.walkMomentum.skidRemaining == 0) {
        u8 requestedDirection = OverworldMount_BufferedDirection(physicalKeys);
        /* NONE clears an older turn when the player returns to the committed
         * heading or gives input that cannot select a direction. */
        u8 bufferedDirection = OVERWORLD_MOUNT_DIRECTION_NONE;

        if (requestedDirection != policy.walkMomentum.direction) {
            /* Buffer turns while the current tile owns PlayerMoveControl. */
            bufferedDirection = requestedDirection;
        }
        OverworldMount_ApplyPolicyValue(
            OVERWORLD_ACTOR_WALK_POLICY_BUFFER_DIRECTION,
            bufferedDirection);
    }
    if (sOverworldMountState.motionCooldown != 0) {
        sOverworldMountState.motionCooldown--;
    }
    OverworldMount_UpdateCustomMotion();
    OverworldMount_DrainLandStream();
    if (!OverworldMount_AttachPresentation()) {
        OverworldMount_Cancel(OVERWORLD_MOUNT_CANCEL_IDENTITY_CHANGED);
        return FALSE;
    }
    actionCall.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
    actionCall.size = sizeof(actionCall);
    actionCall.operation = OVERWORLD_MOUNT_ACTION_TICK_CHAIN;
    actionCall.state = &sOverworldMountState;
    actionCall.avatar = fieldSystem->playerAvatar;
    (void)OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&actionCall);
    (void)OverworldMount_TryFinalizeSharedMotion();
    OverworldMount_SyncPresentation();
    return TRUE;
}

static BOOL __attribute__((naked, noinline, used,
    section(".overworld_mount_toggle_latch")))
OverworldMount_TickLatched(
    FieldSystem *fieldSystem,
    OverworldWildSpawnState *state,
    u16 physicalKeys)
{
    __asm__(
        "push {r0}\n"
        "ldr r3, 2f\n"
        "ldrb r0, [r3, #0]\n"
        "lsl r0, r0, #2\n"
        "orr r2, r0\n"
        /* Leave the buffered edge owned by OverworldMount_Tick until a
         * toggle succeeds. */
        "nop\n"
        "nop\n"
        "pop {r0}\n"
        "ldr r3, 3f\n"
        "bx r3\n"
        ".align 2\n"
        "2: .word 0x023BC7DA\n"
        "3: .word OverworldMount_Tick + 1\n");
}

const OverworldMountOverlayEntry gOverworldMountOverlayEntry
    __attribute__((section(".overworld_mount_entry"), used)) = {
        OVERWORLD_MOUNT_OVERLAY_MAGIC,
        OVERWORLD_MOUNT_OVERLAY_VERSION,
        sizeof(OverworldMountOverlayEntry),
        OverworldMount_Begin,
        OverworldMount_Cancel,
        OverworldMount_Transition,
        OverworldMount_OnPlayerStep,
        OverworldMount_IsActive,
        OverworldMount_TickLatched,
    };
