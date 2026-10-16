#include "../include/player_health.h"
#include "../include/overworld_combat.h"
#include "../include/overworld_mount_action_adapter.h"

#include "../include/constants/file.h"
#include "../include/constants/buttons.h"
#include "../include/constants/sndseq.h"
#include "../include/config.h"
#include "../include/map_events_internal.h"
#include "../include/overlay.h"
#include "../include/overworld_mount_internal.h"
#include "../include/overworld_actor_system_internal.h"
#include "../include/overworld_motion_model.h"
#include "../include/overworld_wild_occupancy.h"
#include "../include/map_teleport.h"
#include "../include/player_health_presentation.h"
#include "../include/player_health_recovery.h"
#include "../include/save.h"
#include "../include/script.h"
#include "../include/sound.h"
#include "../include/task.h"

/* These core helpers are Thumb code. A plain absolute import makes the linker
 * enter them in ARM state from the resident HP overlay. */
__asm__(
    ".thumb\n"
    ".global __aeabi_idiv\n.thumb_func\n.thumb_set __aeabi_idiv, 0x023DEE44\n"
    ".global __aeabi_idivmod\n.thumb_func\n.thumb_set __aeabi_idivmod, 0x023DEE44\n"
    ".global __aeabi_uidiv\n.thumb_func\n.thumb_set __aeabi_uidiv, 0x023DEE4C\n"
    ".global __aeabi_uidivmod\n.thumb_func\n.thumb_set __aeabi_uidivmod, 0x023DEE4C\n"
    ".global memset\n.thumb_func\n.thumb_set memset, 0x023DEEA2\n");

/* Resident actor motion helpers are Thumb. Preserve their mode when
 * this separately linked resident overlay calls them. */
__asm__(
    ".thumb\n"
    ".global OverworldMotion_Begin\n.thumb_func\n"
    ".thumb_set OverworldMotion_Begin, 0x023B97EC\n"
    ".global OverworldMotion_Tick\n.thumb_func\n"
    ".thumb_set OverworldMotion_Tick, 0x023B990A\n"
    ".global OverworldMotion_AcknowledgeCommit\n.thumb_func\n"
    ".thumb_set OverworldMotion_AcknowledgeCommit, 0x023B98C2\n"
    ".global OverworldMotion_Cancel\n.thumb_func\n"
    ".thumb_set OverworldMotion_Cancel, 0x023B9A2E\n");

#define PLAYER_HEALTH_END_TASK_PRIORITY 1400
#define PLAYER_HEALTH_KNOCKBACK_FREEZE_COMMAND 0x3E
#define PLAYER_HEALTH_KNOCKBACK_FORCED_FLAG (1u << 0)
#define PLAYER_HEALTH_KNOCKBACK_WAIT_LIMIT 90
#define PLAYER_HEALTH_KNOCKBACK_MAX_DISTANCE 7
#define PLAYER_HEALTH_BLOCKED_BY_OBJECT (1u << 2)

/* Stock held-command clear used by mounted Hop's player motion shell. */
extern void PlayerHealth_ClearObjectCommand(LocalMapObject *player);
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set PlayerHealth_ClearObjectCommand, 0x020621F0\n");

typedef struct PlayerHealthKnockbackRuntime {
    OverworldMotionState motion;
    FieldSystem *fieldSystem;
    LocalMapObject *playerObject;
    s32 baseFaceY;
    s32 baseUnk88Y;
    u32 fieldContext;
    u16 mapId;
    u16 motionIdentity;
    u8 direction;
    u8 type;
    u8 distance;
    u8 pending;
    u8 active;
    u8 streamActive;
    u8 waitFrames;
    u8 mounted;
} PlayerHealthKnockbackRuntime;

static PlayerHealthKnockbackRuntime sKnockback
    __attribute__((section(".player_health_extended_state"))) = {0};

static void PlayerHealthKnockback_Cancel(void);
static void PlayerHealthKnockback_Tick(void);
static u8 PlayerHealthKnockback_Control(FIELD_PLAYER_AVATAR *avatar,
    s32 *direction, u32 *newKeys, u32 *heldKeys);

typedef struct PlayerHealthFieldRuntime {
    PlayerHealthState health;
    SaveData *saveData;
    FieldSystem *fieldSystem;
    SysTask *endTask;
    LocalMapObject *playerObject;
    u32 sequence;
    s32 lastX;
    s32 lastZ;
    s32 beginX;
    s32 beginZ;
    u8 initialized;
    u8 havePose;
    u8 movedAtBegin;
} PlayerHealthFieldRuntime;

static PlayerHealthFieldRuntime sPlayerHealth
    __attribute__((section(".player_health_state"))) = {0};

/* A task manager alone does not cover paused field applications. */
static BOOL PlayerHealthField_IsEligible(FieldSystem *fieldSystem)
{
    const u8 *fieldState;

    if (fieldSystem == NULL || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || fieldSystem->savedata == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || fieldSystem->taskman != NULL
        || !sub_0203DF8C(fieldSystem)) {
        return FALSE;
    }
    fieldState = *(const u8 *const *)fieldSystem;
    return fieldState != NULL && *(const u32 *)(fieldState + 8) == 0;
}

static void PlayerHealthField_EnsureState(FieldSystem *fieldSystem)
{
    SaveData *saveData = (SaveData *)fieldSystem->savedata;
    u8 savedHp;

    if (sPlayerHealth.initialized && sPlayerHealth.saveData == saveData
        && sPlayerHealth.fieldSystem == fieldSystem) {
        return;
    }
    savedHp = PlayerHealthSave_GetHP(saveData);
    if (sPlayerHealth.initialized && sPlayerHealth.saveData == saveData
        && sPlayerHealth.health.hp == savedHp) {
        return;
    }
    PlayerHealth_Init(&sPlayerHealth.health, savedHp);
    sPlayerHealth.saveData = saveData;
    sPlayerHealth.initialized = TRUE;
    sPlayerHealth.sequence = 0;
    sPlayerHealth.havePose = FALSE;
    sPlayerHealth.playerObject = NULL;
}

static BOOL __attribute__((noinline,
    section(".player_health_extended_text")))
PlayerHealthField_IsMounted(FieldSystem *fieldSystem)
{
    const OverworldMountOverlayEntry *entry = OVERWORLD_MOUNT_OVERLAY_ENTRY;
    const OverworldMountRuntimeState *mount;

    /* The resident mount is not tracked by the SDK overlay load table. */
    if (entry->magic != OVERWORLD_MOUNT_OVERLAY_MAGIC
        || entry->version != OVERWORLD_MOUNT_OVERLAY_VERSION
        || entry->size != sizeof(*entry)) {
        return FALSE;
    }
    mount = (const OverworldMountRuntimeState *)
        OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    return mount->fieldSystem == fieldSystem
        && mount->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING;
}

static BOOL PlayerHealthField_MountMoving(FieldSystem *fieldSystem)
{
    const OverworldMountRuntimeState *mount;

    if (!PlayerHealthField_IsMounted(fieldSystem)) {
        return FALSE;
    }
    mount = (const OverworldMountRuntimeState *)
        OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    return mount->snapshot.motionMode != OVERWORLD_MOUNT_MOTION_NONE
            || mount->motionStreamPreparing
            || (mount->reservedPolicyState[
                    OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX]
                & OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING) != 0;
}

static BOOL PlayerHealthField_PlayerMoving(FieldSystem *fieldSystem)
{
    FIELD_PLAYER_AVATAR *avatar = fieldSystem->playerAvatar;
    LocalMapObject *player = avatar->mapObject;
    s32 x = (s32)player->posVec[0];
    s32 z = (s32)player->posVec[2];
    BOOL moving = sPlayerHealth.movedAtBegin
        || x != sPlayerHealth.beginX
        || z != sPlayerHealth.beginZ
        || MapObject_IsSingleMovementActive(player)
        || PlayerHealthField_MountMoving(fieldSystem);

    sPlayerHealth.playerObject = player;
    sPlayerHealth.lastX = x;
    sPlayerHealth.lastZ = z;
    sPlayerHealth.havePose = TRUE;
    return moving;
}

static void __attribute__((section(".player_health_extended_text")))
PlayerHealthField_EndTask(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;
    u8 oldHp;

    if (fieldSystem != gFieldSysPtr) {
        PlayerHealthKnockback_Cancel();
        PlayerHealthPresentation_End(fieldSystem);
        PlayerHealth_AbortFrame(&sPlayerHealth.health);
        PlayerHealthContact_ResetAll();
        sPlayerHealth.endTask = NULL;
        sPlayerHealth.fieldSystem = NULL;
        sPlayerHealth.havePose = FALSE;
        sPlayerHealth.health.restFrames = 0;
        sPlayerHealth.health.healRemainder = 0;
        DestroySysTask(task);
        return;
    }
    if (!PlayerHealthField_IsEligible(fieldSystem)) {
        PlayerHealthKnockback_Cancel();
        PlayerHealthPresentation_End(fieldSystem);
        PlayerHealth_AbortFrame(&sPlayerHealth.health);
        return;
    }
    if (sPlayerHealth.health.frameActive) {
        PlayerHealthContact_EndFrame(&sOverworldWildSpawnState);
        oldHp = sPlayerHealth.health.hp;
        (void)PlayerHealth_EndFrame(&sPlayerHealth.health,
            PlayerHealthField_PlayerMoving(fieldSystem));
        if (sPlayerHealth.health.hp != oldHp) {
            PlayerHealthSave_SetHP(sPlayerHealth.saveData,
                sPlayerHealth.health.hp);
        }
    }
    PlayerHealthKnockback_Tick();
    PlayerHealthRecovery_ServiceHealing(fieldSystem);
    if (sPlayerHealth.health.recoveryPending) {
        (void)PlayerHealthRecovery_BeginBlackout(fieldSystem);
        PlayerHealthPresentation_End(fieldSystem);
        return;
    }
    PlayerHealthPresentation_Update(fieldSystem, &sPlayerHealth.health,
        PlayerHealthContact_Danger(fieldSystem));
}

void PlayerHealthField_Stop(FieldSystem *fieldSystem)
{
    if (fieldSystem != NULL
        && sPlayerHealth.fieldSystem != fieldSystem) {
        return;
    }
    PlayerHealthKnockback_Cancel();
    PlayerHealthPresentation_End(fieldSystem);
    PlayerHealth_AbortFrame(&sPlayerHealth.health);
    if (sPlayerHealth.endTask != NULL) {
        DestroySysTask(sPlayerHealth.endTask);
        sPlayerHealth.endTask = NULL;
    }
    PlayerHealthContact_ResetAll();
    OverworldCombat_Reset();
    sPlayerHealth.fieldSystem = NULL;
    sPlayerHealth.havePose = FALSE;
    sPlayerHealth.health.restFrames = 0;
    sPlayerHealth.health.healRemainder = 0;
}

/* Title New Game and successful Continue have replaced the save contents.
 * Force the next field entry to read HP even if the allocator reuses the
 * same SaveData and FieldSystem addresses and the stored HP is unchanged. */
void PlayerHealthField_SessionReset(void)
{
    PlayerHealthField_Stop(NULL);
    PlayerHealthRecovery_SessionReset();
    PlayerHealth_Init(&sPlayerHealth.health, PLAYER_HEALTH_MAX_HP);
    sPlayerHealth.saveData = NULL;
    sPlayerHealth.playerObject = NULL;
    sPlayerHealth.sequence = 0;
    sPlayerHealth.initialized = FALSE;
    sPlayerHealth.movedAtBegin = FALSE;
}

void __attribute__((noinline, section(".player_health_extended_text")))
PlayerHealthField_Begin(FieldSystem *fieldSystem)
{
    LocalMapObject *player;

    if (!PlayerHealthField_IsEligible(fieldSystem)) {
        PlayerHealthKnockback_Cancel();
        PlayerHealth_AbortFrame(&sPlayerHealth.health);
        return;
    }
    PlayerHealthField_EnsureState(fieldSystem);
    if (sPlayerHealth.health.recoveryPending) {
        PlayerHealthRecovery_ServiceHealing(fieldSystem);
        if (sPlayerHealth.health.recoveryPending) {
            (void)PlayerHealthRecovery_BeginBlackout(fieldSystem);
            return;
        }
    }
    if (sPlayerHealth.endTask == NULL
        || sPlayerHealth.fieldSystem != fieldSystem) {
        if (sPlayerHealth.endTask != NULL) {
            DestroySysTask(sPlayerHealth.endTask);
        }
        sPlayerHealth.health.restFrames = 0;
        sPlayerHealth.health.healRemainder = 0;
        sPlayerHealth.endTask = CreateSysTask(
            PlayerHealthField_EndTask, fieldSystem,
            PLAYER_HEALTH_END_TASK_PRIORITY);
        sPlayerHealth.fieldSystem = fieldSystem;
        sPlayerHealth.havePose = FALSE;
        /* A SysTask created during this queue update skips its first run. */
        return;
    }
    if (sPlayerHealth.health.frameActive) {
        PlayerHealth_AbortFrame(&sPlayerHealth.health);
    }
    player = fieldSystem->playerAvatar->mapObject;
    sPlayerHealth.movedAtBegin = !sPlayerHealth.havePose
        || sPlayerHealth.playerObject != player
        || sPlayerHealth.lastX != (s32)player->posVec[0]
        || sPlayerHealth.lastZ != (s32)player->posVec[2]
        || MapObject_IsSingleMovementActive(player)
        || PlayerHealthField_MountMoving(fieldSystem);
    sPlayerHealth.beginX = (s32)player->posVec[0];
    sPlayerHealth.beginZ = (s32)player->posVec[2];
    sPlayerHealth.sequence++;
    if (sPlayerHealth.sequence == 0) {
        sPlayerHealth.sequence = 1;
    }
    (void)PlayerHealth_BeginFrame(&sPlayerHealth.health,
        sPlayerHealth.sequence, TRUE);
    OverworldCombat_BeginFrame(&sOverworldWildSpawnState);
    PlayerHealthContact_BeginFrame(&sOverworldWildSpawnState);
}

BOOL __attribute__((section(".overworld_combat_text")))
PlayerHealthField_ContactsEnabled(FieldSystem *fieldSystem)
{
    return PlayerHealthField_IsEligible(fieldSystem)
        && sPlayerHealth.initialized
        && sPlayerHealth.saveData == (SaveData *)fieldSystem->savedata
        && sPlayerHealth.fieldSystem == fieldSystem
        && sPlayerHealth.health.frameActive;
}

void __attribute__((section(".overworld_combat_text")))
PlayerHealthField_QueueKnockback(FieldSystem *fieldSystem, u8 options, u8 direction)
{
    if (!sKnockback.pending && !sKnockback.active
        && OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(options) != OW_WILD_BEHAVIOR_KNOCKBACK_NONE
        && OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(options) != 0
        && direction < 4 && sPlayerHealth.health.hp != 0) {
        sKnockback.pending = TRUE;
        sKnockback.waitFrames = 0;
        sKnockback.direction = direction;
        sKnockback.type = OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(options);
        sKnockback.distance = OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(options);
        sKnockback.mapId = fieldSystem->location->mapId;
        sKnockback.fieldSystem = fieldSystem;
        sKnockback.mounted = PlayerHealthField_IsMounted(fieldSystem);
    }
}

BOOL __attribute__((section(".player_health_extended_text")))
OverworldCombat_MountedPending(FieldSystem *fieldSystem)
{
    return OverworldCombat_MountedCrashPending(fieldSystem)
        || (sKnockback.fieldSystem == fieldSystem && sKnockback.mounted
            && (sKnockback.pending || sKnockback.active));
}

u8 __attribute__((section(".overworld_combat_prepare")))
OverworldCombat_MountStatus(const OverworldWildSpawnState *state)
{
    u16 hp, maxHp;
    u8 status = OverworldCombat_ReadHp(state, OW_WILD_FOLLOWER_SLOT, &hp, &maxHp)
        && hp != 0 ? 0 : OVERWORLD_COMBAT_MOUNT_FAINTED;
    u8 crash = OverworldCombat_Prepare(state,
        OW_WILD_FOLLOWER_SLOT | OVERWORLD_COMBAT_PROBE_URGENT, NULL);
    if (crash == OVERWORLD_COMBAT_CRASH_SETTLE) {
        status |= OVERWORLD_COMBAT_MOUNT_CRASH_SETTLE;
    } else if (crash == OVERWORLD_COMBAT_CRASH_PLAYING) {
        status |= OVERWORLD_COMBAT_MOUNT_CRASH_PLAYING;
    }
    if (OverworldCombat_MountedPending(state->movementFieldSystem)) {
        status |= OVERWORLD_COMBAT_MOUNT_KNOCKBACK_PENDING;
    }
    return status;
}

const OverworldCombatEntry gOverworldCombatEntry
    __attribute__((used, section(".overworld_combat_api"))) = {
    OVERWORLD_COMBAT_MAGIC, OVERWORLD_COMBAT_VERSION, sizeof(OverworldCombatEntry),
    OverworldCombat_ReadHp, OverworldCombat_HpIV, OverworldCombat_Prepare,
    OverworldCombat_Acknowledge, OverworldCombat_Plan, OverworldCombat_MountedPending,
    OverworldCombat_BattleHp, OverworldCombat_BattleSync,
    OverworldCombat_BattleUpdate,
    OverworldCombat_MountStatus,
    OverworldCombat_CaptureHp,
};

PlayerHealthDecision __attribute__((noinline,
    section(".overworld_combat_text"))) PlayerHealthField_TryContact(
    FieldSystem *fieldSystem, u8 attacking, u8 minImpactSpeed,
    u8 collisionDamage, u16 impactSpeed, u8 knockbackOptions,
    u8 knockbackDirection)
{
    PlayerHealthDecision result;

    if (!PlayerHealth_ContactCanDamage(attacking, minImpactSpeed,
            collisionDamage, impactSpeed)) {
        return PLAYER_HEALTH_INVALID;
    }
    if (!PlayerHealthField_IsEligible(fieldSystem)
        || !sPlayerHealth.initialized
        || sPlayerHealth.saveData != (SaveData *)fieldSystem->savedata
        || sPlayerHealth.fieldSystem != fieldSystem
        || !sPlayerHealth.health.frameActive) {
        return PLAYER_HEALTH_PAUSED;
    }
    result = PlayerHealth_TryHit(&sPlayerHealth.health, collisionDamage);
    if (result == PLAYER_HEALTH_OK) {
        PlayerHealthSave_SetHP(sPlayerHealth.saveData,
            sPlayerHealth.health.hp);
        PlaySE(SEQ_SE_DP_WALL_HIT2);
        if (PlayerHealthField_IsMounted(fieldSystem)) {
            OverworldCombat_AcceptedHit(&sOverworldWildSpawnState,
                OW_WILD_FOLLOWER_SLOT);
        }
        PlayerHealthField_QueueKnockback(fieldSystem, knockbackOptions, knockbackDirection);
    }
    return result;
}

static BOOL __attribute__((noinline, section(".player_health_extended_text")))
PlayerHealthField_IsScriptedTile(FieldSystem *fieldSystem,
    s32 x, s32 z)
{
    const MAP_EVENTS *events = fieldSystem->map_events;
    u32 i;

    if (events == NULL) {
        return TRUE;
    }
    for (i = 0; i < events->num_warp_events; i++) {
        if (events->warp_events[i].x == x
            && events->warp_events[i].y == z) {
            return TRUE;
        }
    }
    for (i = 0; i < events->num_coord_events; i++) {
        const COORD_EVENT *event = &events->coord_events[i];

        if (x >= event->x && x < event->x + event->w
            && z >= event->y && z < event->y + event->h) {
            return TRUE;
        }
    }
    return FALSE;
}

#define PLAYER_HEALTH_KNOCKBACK_CODE \
    __attribute__((noinline, section(".player_health_extended_text")))

static BOOL PLAYER_HEALTH_KNOCKBACK_CODE
PlayerHealthKnockback_IsFixedObjectBlocked(FieldSystem *fieldSystem,
    LocalMapObject *player, s32 x, s32 z)
{
    MapObjectMan *manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    u32 i;

    if (manager == NULL || manager->objects == NULL) {
        return FALSE;
    }
    for (i = 0; i < manager->object_count; i++) {
        LocalMapObject *object = &manager->objects[i];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) == 0
            || object == player
            || object->id == OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID
            || object->id == OW_WILD_FOLLOWER_OBJECT_ID
            || (object->id >= OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START
                && object->id < OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START
                    + OW_WILD_MAX_SPAWNS)
            || (object->id >= OW_WILD_OBJECT_ID_START
                && object->id < OW_WILD_OBJECT_ID_START
                    + OW_WILD_MAX_SPAWNS
                && object->scriptId == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT)) {
            continue;
        }
        if (object->xCurr == x && object->yCurr == z) {
            return TRUE;
        }
    }
    return FALSE;
}

static OverworldFieldTerrainStreamResult PLAYER_HEALTH_KNOCKBACK_CODE
PlayerHealthKnockback_Stream(u8 operation)
{
    const OverworldFieldMountPresentationEntry *entry =
        OVERWORLD_FIELD_MOUNT_PRESENTATION_ENTRY;
    OverworldFieldTerrainStreamCall call;

    if (entry->magic != OVERWORLD_FIELD_MOUNT_PRESENTATION_MAGIC
        || entry->version != OVERWORLD_FIELD_MOUNT_PRESENTATION_VERSION
        || entry->size != sizeof(*entry)
        || entry->terrainStream == NULL
        || sKnockback.fieldSystem == NULL) {
        return OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED;
    }
    memset(&call, 0, sizeof(call));
    call.version = OVERWORLD_FIELD_TERRAIN_STREAM_CALL_VERSION;
    call.size = sizeof(call);
    call.fieldSystem = sKnockback.fieldSystem;
    call.fieldContext = OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    call.motionIdentity = sKnockback.motionIdentity;
    call.targetX = sKnockback.motion.plan.targetX;
    call.targetY = sKnockback.motion.plan.targetY;
    call.operation = operation;
    return entry->terrainStream(&call);
}

static void PLAYER_HEALTH_KNOCKBACK_CODE
PlayerHealthKnockback_Cancel(void)
{
    FIELD_PLAYER_AVATAR *avatar = NULL;
    LocalMapObject *player = NULL;

    if (sKnockback.streamActive
        && sKnockback.fieldSystem != NULL
        && sKnockback.fieldSystem == gFieldSysPtr) {
        if (sKnockback.fieldContext
            != OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext()) {
            (void)PlayerHealthKnockback_Stream(
                OVERWORLD_FIELD_TERRAIN_STREAM_REBIND);
        }
        (void)PlayerHealthKnockback_Stream(
            OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL);
    }
    sKnockback.streamActive = FALSE;
    if (sKnockback.active && !sKnockback.mounted
        && sKnockback.fieldSystem == gFieldSysPtr
        && gFieldSysPtr != NULL
        && gFieldSysPtr->playerAvatar != NULL
        && gFieldSysPtr->playerAvatar->mapObject
            == sKnockback.playerObject) {
        avatar = gFieldSysPtr->playerAvatar;
        player = avatar->mapObject;
        player->posVec[0] = ((u32)(u16)player->xCurr << 16) + 0x8000;
        player->posVec[2] = ((u32)(u16)player->yCurr << 16) + 0x8000;
        player->posVec[1] = (u32)sKnockback.motion.plan.startBaseY;
        player->faceVec[1] = (u32)sKnockback.baseFaceY;
        player->unk88[1] = (u32)sKnockback.baseUnk88Y;
        MapObject_SetPositionFromVectorAndDirection(
            player, (VecFx32 *)player->posVec, player->curFacing);
        (void)MapObject_RefreshHeightFromTerrain(player);
        player->unkA0 = 0;
        PlayerHealth_ClearObjectCommand(player);
        avatar->unk0 &= ~PLAYER_HEALTH_KNOCKBACK_FORCED_FLAG;
        PlayerAvatar_ResetMovement(avatar);
        /* The field's normal sprite pass ran before this end-task cleanup.
         * Publish the idle pose through that same registered stock callback. */
        player->unkC8(player); /* Stock sub_0205F484. */
    }
    if (sKnockback.motion.phase != OVERWORLD_MOTION_PHASE_IDLE) {
        if (OverworldActorSystem_IsReady()) {
            OverworldMotion_Cancel(&sKnockback.motion, 1);
        } else {
            sKnockback.motion.phase = OVERWORLD_MOTION_PHASE_CANCELED;
        }
    }
    sKnockback.pending = FALSE;
    sKnockback.active = FALSE;
    sKnockback.fieldSystem = NULL;
    sKnockback.playerObject = NULL;
    sKnockback.waitFrames = 0;
}

BOOL __attribute__((noinline, section(".overworld_combat_text")))
OverworldCombat_Plan(FieldSystem *fieldSystem, LocalMapObject *player,
    u8 options, u8 requestedDirection, OverworldMotionPlan *plan)
{
    u8 type = OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(options);
    u8 requestedDistance = OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(options);
    s32 targetX, targetZ;
    u8 distance = 0, direction = requestedDirection, candidate, step;
    u8 candidateCount = type == OW_WILD_BEHAVIOR_KNOCKBACK_JUMP
        && requestedDistance == 1 ? 4 : 1;

    if (fieldSystem == NULL || player == NULL || plan == NULL
        || requestedDirection > 3 || type == OW_WILD_BEHAVIOR_KNOCKBACK_NONE
        || type > OW_WILD_BEHAVIOR_KNOCKBACK_JUMP || requestedDistance == 0
        || requestedDistance > PLAYER_HEALTH_KNOCKBACK_MAX_DISTANCE) {
        return FALSE;
    }
    for (candidate = 0; candidate < candidateCount; candidate++) {
        s32 dx;
        s32 dz;

        if (candidate != 0) {
            if (candidate == 1) {
                direction = requestedDirection ^ 1;
            } else {
                direction = requestedDirection < 2
                    ? candidate : candidate - 2;
            }
        }
        targetX = player->xCurr;
        targetZ = player->yCurr;
        distance = 0;
        if ((MapObject_IsMovementDirectionBlocked(player, direction)
                & ~PLAYER_HEALTH_BLOCKED_BY_OBJECT) != 0) {
            continue;
        }
        dx = direction == 2 ? -1 : direction == 3 ? 1 : 0;
        dz = direction == 0 ? -1 : direction == 1 ? 1 : 0;
        for (step = 1; step <= requestedDistance; step++) {
            s32 nextX = player->xCurr + dx * step;
            s32 nextZ = player->yCurr + dz * step;

            if (nextX < 0 || nextZ < 0 || nextX > 32767 || nextZ > 32767
                || GetMetatileBehaviorAt(fieldSystem, nextX, nextZ) == 0xFF
                || IsMetatileBlockedAt(fieldSystem, nextX, nextZ)
                || PlayerHealthField_IsScriptedTile(
                    fieldSystem, nextX, nextZ)
                || PlayerHealthKnockback_IsFixedObjectBlocked(
                    fieldSystem, player, nextX, nextZ)) {
                break;
            }
            targetX = nextX;
            targetZ = nextZ;
            distance = step;
        }
        if (distance != 0) {
            break;
        }
    }
    if (distance == 0) {
        return FALSE;
    }
    memset(plan, 0, sizeof(*plan));
    plan->version = OVERWORLD_MOTION_MODEL_VERSION;
    plan->kind = OVERWORLD_MOTION_KIND_HOP;
    plan->facing = player->curFacing;
    plan->fieldEpoch = OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext());
    plan->startX = player->xCurr;
    plan->startY = player->yCurr;
    plan->targetX = targetX;
    plan->targetY = targetZ;
    plan->startBaseY = (s32)player->posVec[1];
    plan->targetBaseY = plan->startBaseY;
    plan->direction = direction;
    plan->distance = distance;
    plan->duration = type
            == OW_WILD_BEHAVIOR_KNOCKBACK_JUMP
        ? 8 + distance * 5 : 4 + distance * 4;
    plan->arcHeightQ4 = type
            == OW_WILD_BEHAVIOR_KNOCKBACK_JUMP ? 16 : 0;
    plan->visibilityPolicy = OVERWORLD_MOTION_VISIBILITY_VISIBLE;
    plan->pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_AUTHORITY;
    plan->commitPolicy = OVERWORLD_MOTION_COMMIT_NO_CHAIN;
    plan->flags = OVERWORLD_MOTION_FLAG_FORCED;
    return TRUE;
}

/* Stock Run can publish its next logical tile before its pose arrives. */
static BOOL __attribute__((noinline, section(".text")))
PlayerHealthKnockback_IsAtGroundCenter(const LocalMapObject *player)
{
    return player->posVec[0] == ((u32)(u16)player->xCurr << 16) + 0x8000
        && player->posVec[2] == ((u32)(u16)player->yCurr << 16) + 0x8000;
}

static u8 __attribute__((section(".player_health_extended_text")))
PlayerHealthKnockback_TryStart(FIELD_PLAYER_AVATAR *avatar)
{
    FieldSystem *fieldSystem = sKnockback.fieldSystem;
    LocalMapObject *player = avatar->mapObject;
    OverworldMotionPlan plan;
    if (MapObject_IsSingleMovementActive(player)
        || PlayerHealthField_MountMoving(fieldSystem)) {
        return FALSE;
    }
    /* Begin the shared stream only from the current tile's ground center. */
    if (!sKnockback.mounted && !PlayerHealthKnockback_IsAtGroundCenter(player)) {
        return FALSE;
    }
    if (!OverworldCombat_Plan(fieldSystem, player,
            sKnockback.type | (sKnockback.distance << 2),
            sKnockback.direction, &plan)) {
        PlayerHealthKnockback_Cancel();
        return FALSE;
    }
    if (sKnockback.mounted) {
        OverworldMountActionCall call = {0};
        u8 result;

        call.version = OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION;
        call.size = sizeof(call);
        call.operation = OVERWORLD_MOUNT_ACTION_START_KNOCKBACK;
        call.state = (OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
        call.avatar = avatar;
        call.trajectory = (u32 *)&plan;
        result = OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(&call);
        if (result == OVERWORLD_MOUNT_ACTION_STARTED) {
            sKnockback.pending = FALSE;
            sKnockback.active = TRUE;
            sKnockback.playerObject = player;
        } else if (result == OVERWORLD_MOUNT_ACTION_FINAL) {
            PlayerHealthKnockback_Cancel();
        }
        return result == OVERWORLD_MOUNT_ACTION_STARTED;
    }
    if (PlayerHealthKnockback_Stream(OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE)
        != OVERWORLD_FIELD_TERRAIN_STREAM_IDLE) {
        return FALSE;
    }
    plan.pathAdvancePolicy = OVERWORLD_MOTION_PATH_ADVANCE_PLAYER;
    sKnockback.direction = plan.direction;
    if (OverworldMotion_Begin(&sKnockback.motion, &plan)
        != OVERWORLD_MOTION_DECISION_ACCEPTED) {
        PlayerHealthKnockback_Cancel();
        return FALSE;
    }
    sKnockback.motionIdentity++;
    if (sKnockback.motionIdentity == 0) {
        sKnockback.motionIdentity = 1;
    }
    sKnockback.fieldContext =
        OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext();
    if (PlayerHealthKnockback_Stream(
            OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN)
        != OVERWORLD_FIELD_TERRAIN_STREAM_WAITING) {
        PlayerHealthKnockback_Cancel();
        return FALSE;
    }
    sKnockback.streamActive = TRUE;
    sKnockback.baseFaceY = (s32)player->faceVec[1];
    sKnockback.baseUnk88Y = (s32)player->unk88[1];
    sKnockback.playerObject = player;
    sKnockback.pending = FALSE;
    sKnockback.active = TRUE;
    sKnockback.waitFrames = 0;
    avatar->unk0 |= PLAYER_HEALTH_KNOCKBACK_FORCED_FLAG;
    PlayerAvatar_ResetMovement(avatar);
    MapObject_SetPositionFromVectorAndDirection(
        player, (VecFx32 *)player->posVec, player->curFacing);
    MapObject_StartMovementCommandInternal(
        player, PLAYER_HEALTH_KNOCKBACK_FREEZE_COMMAND);
    return TRUE;
}

static u8 __attribute__((section(".player_health_extended_text")))
PlayerHealthKnockback_Control(FIELD_PLAYER_AVATAR *avatar,
    s32 *direction, u32 *newKeys, u32 *heldKeys)
{
    FieldSystem *fieldSystem = sKnockback.fieldSystem;

    /* Crash is forced control even when this profile has no knockback. The
     * role adapter restores the ground boundary and owns its Crash timer. */
    if (OverworldCombat_MountedCrashPending(gFieldSysPtr)
        && PlayerHealthField_IsEligible(gFieldSysPtr)
        && avatar == gFieldSysPtr->playerAvatar
        && direction != NULL && newKeys != NULL && heldKeys != NULL) {
        *direction = -1;
        *newKeys = 0;
        *heldKeys = 0;
        return TRUE;
    }

    if (!sKnockback.pending && !sKnockback.active) {
        return FALSE;
    }
    if (avatar == NULL || direction == NULL || newKeys == NULL
        || heldKeys == NULL || fieldSystem == NULL
        || !PlayerHealthField_IsEligible(fieldSystem)
        || fieldSystem->playerAvatar != avatar
        || fieldSystem->location->mapId != sKnockback.mapId) {
        PlayerHealthKnockback_Cancel();
        return FALSE;
    }
    if (sKnockback.mounted && !PlayerHealthField_IsMounted(fieldSystem)) {
        /* A fainted mount has detached. Finish the rider's hit on foot. */
        sKnockback.mounted = FALSE;
        sKnockback.active = FALSE;
        sKnockback.pending = TRUE;
        sKnockback.waitFrames = 0;
    } else if (!sKnockback.mounted && PlayerHealthField_IsMounted(fieldSystem)) {
        PlayerHealthKnockback_Cancel();
        return FALSE;
    }
    if (sKnockback.pending) {
        if (++sKnockback.waitFrames > PLAYER_HEALTH_KNOCKBACK_WAIT_LIMIT) {
            PlayerHealthKnockback_Cancel();
        } else {
            (void)PlayerHealthKnockback_TryStart(avatar);
        }
    }
    if (!sKnockback.mounted && !sKnockback.active) {
        return FALSE;
    }
    /* The player controller owns both slide and jump until landing. */
    *direction = -1;
    *newKeys = 0;
    *heldKeys = 0;
    return TRUE;
}

static void PLAYER_HEALTH_KNOCKBACK_CODE
PlayerHealthKnockback_Tick(void)
{
    FieldSystem *fieldSystem = sKnockback.fieldSystem;
    LocalMapObject *player = sKnockback.playerObject;
    OverworldMotionSample sample;
    OverworldFieldTerrainStreamResult stream;
    u16 flags;
    s32 x;
    s32 z;

    if (!sKnockback.active) {
        return;
    }
    if (fieldSystem == NULL || fieldSystem != gFieldSysPtr
        || !PlayerHealthField_IsEligible(fieldSystem)
        || fieldSystem->location->mapId != sKnockback.mapId
        || fieldSystem->playerAvatar->mapObject != player
        || (!sKnockback.mounted && PlayerHealthField_IsMounted(fieldSystem))
        || (!sKnockback.mounted && sKnockback.fieldContext
            != OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext())) {
        PlayerHealthKnockback_Cancel();
        return;
    }
    if (sKnockback.mounted) {
        if (!PlayerHealthField_IsMounted(fieldSystem)) {
            sKnockback.active = FALSE;
            sKnockback.pending = TRUE;
            sKnockback.mounted = FALSE;
            sKnockback.waitFrames = 0;
        } else if (!PlayerHealthField_MountMoving(fieldSystem)) {
            PlayerHealthKnockback_Cancel();
        }
        return;
    }
    flags = OverworldMotion_Tick(&sKnockback.motion,
        OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(sKnockback.fieldContext),
        &sample);
    if (sKnockback.motion.phase == OVERWORLD_MOTION_PHASE_SUSPENDED) {
        PlayerHealthKnockback_Cancel();
        return;
    }
    if ((flags & OVERWORLD_MOTION_TICK_MOVED) != 0) {
        x = sample.renderX >> 16;
        z = sample.renderZ >> 16;
        if ((player->xCurr != x || player->yCurr != z)
            && (IsMetatileBlockedAt(fieldSystem, x, z)
                || PlayerHealthKnockback_IsFixedObjectBlocked(
                    fieldSystem, player, x, z))) {
            PlayerHealthKnockback_Cancel();
            return;
        }
        player->posVec[0] = (u32)sample.renderX;
        player->posVec[1] = (u32)sample.baseY;
        player->posVec[2] = (u32)sample.renderZ;
        player->hPrev = player->hCurr;
        player->hCurr = sample.baseY >> 15;
        player->faceVec[1] = (u32)(sKnockback.baseFaceY
            + sample.heightOffset);
        player->unk88[1] = (u32)sKnockback.baseUnk88Y;
        if (player->xCurr != x || player->yCurr != z) {
            player->xPrev = player->xCurr;
            player->yPrev = player->yCurr;
            player->xCurr = x;
            player->yCurr = z;
        }
    }
    stream = PlayerHealthKnockback_Stream(
        OVERWORLD_FIELD_TERRAIN_STREAM_POLL);
    if (stream == OVERWORLD_FIELD_TERRAIN_STREAM_REJECTED) {
        PlayerHealthKnockback_Cancel();
        return;
    }
    if (sKnockback.motion.phase == OVERWORLD_MOTION_PHASE_COMMIT_PENDING) {
        if (stream == OVERWORLD_FIELD_TERRAIN_STREAM_READY) {
            (void)OverworldMotion_AcknowledgeCommit(
                &sKnockback.motion,
                OVERWORLD_ACTOR_FIELD_CONTEXT_FIELD_EPOCH(
                    sKnockback.fieldContext));
            PlayerHealthKnockback_Cancel();
        } else if (++sKnockback.waitFrames
            > PLAYER_HEALTH_KNOCKBACK_WAIT_LIMIT) {
            PlayerHealthKnockback_Cancel();
        }
    }
}

u8 __attribute__((section(".player_health_extended_text")))
PlayerHealthField_OverrideControl(FIELD_PLAYER_AVATAR *avatar,
    s32 *direction, u32 *newKeys, u32 *heldKeys)
{
    return PlayerHealthKnockback_Control(
        avatar, direction, newKeys, heldKeys);
}

void __attribute__((naked, used,
    section(".player_health_knockback_entry")))
PlayerHealthField_OverrideControlEntryImpl(void)
{
    /* Four arguments arrive in r0-r3. Keep r3 (heldKeys) while the fixed
     * entry loads its real destination. */
    __asm__("push {r3}\n ldr r3, 1f\n mov ip, r3\n pop {r3}\n"
        "bx ip\n .align 2\n"
        "1: .word PlayerHealthField_OverrideControl + 1");
}

/* This API is reached through its entry-table pointer. Use the existing tail
 * code reserve so terminal knockback cleanup fits its fixed resident slot. */
const PlayerHealthState *__attribute__((section(".player_health_tail")))
PlayerHealthField_GetState(void)
{
    return sPlayerHealth.initialized ? &sPlayerHealth.health : NULL;
}

void PlayerHealthField_Restore(FieldSystem *fieldSystem)
{
    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return;
    }
    PlayerHealthField_EnsureState(fieldSystem);
    PlayerHealth_Restore(&sPlayerHealth.health);
    PlayerHealthSave_SetHP((SaveData *)fieldSystem->savedata,
        PLAYER_HEALTH_MAX_HP);
}

u8 PlayerHealthField_RecoveryPending(FieldSystem *fieldSystem)
{
    return PlayerHealthField_IsEligible(fieldSystem)
        && sPlayerHealth.initialized
        && sPlayerHealth.saveData == (SaveData *)fieldSystem->savedata
        && sPlayerHealth.health.recoveryPending;
}

const PlayerHealthOverlayEntry gPlayerHealthOverlayEntry
    __attribute__((section(".player_health_api"), used)) = {
    PLAYER_HEALTH_OVERLAY_MAGIC,
    PLAYER_HEALTH_OVERLAY_VERSION,
    sizeof(PlayerHealthOverlayEntry),
    PlayerHealthField_Begin,
    PlayerHealthField_TryContact,
    PlayerHealthField_GetState,
    PlayerHealthField_Restore,
    PlayerHealthField_RecoveryPending,
    PlayerHealthField_Stop,
    PlayerHealthContact_HandleEvent,
    PlayerHealthField_SessionReset,
    WildMovementValue_SelectCircleTarget,
    WildMovementValue_AppendFleeDirections,
    WildMovementValue_GetThrowUnstableMask,
};
