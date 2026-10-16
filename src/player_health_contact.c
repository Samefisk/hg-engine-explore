#ifdef PLAYER_HEALTH_CONTACT_CLIP_HOST
#include <stdint.h>
typedef int32_t s32;
typedef uint32_t u32;
typedef uint8_t u8;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define PLAYER_HEALTH_CLIP_ATTRIBUTE __attribute__((noinline))
#else
#include "../include/player_health.h"
#include "../include/overworld_combat.h"
#include "../include/overworld_mount_internal.h"
#include "../include/constants/sndseq.h"
#include "../include/sound.h"
#include "../include/overworld_actor_system_internal.h"
#include "../include/constants/file.h"
#include "../include/map_events_internal.h"
#include "../include/overlay.h"
#include "../include/overworld_motion_model.h"
#include "../include/overworld_wild_spawns_internal.h"
#include "../include/overworld_wild_runtime_state_internal.h"
#include "../include/overworld_query_code_addon_service.h"
#define PLAYER_HEALTH_CLIP_ATTRIBUTE \
    __attribute__((noinline, section(".player_health_tail")))
#endif

#include "../include/overworld_contact_geometry.h"

#ifndef PLAYER_HEALTH_CONTACT_CLIP_HOST
/* Only the shared prefix is needed. Wild validates the launched target before
 * passing its runtime pointer, and the resident service owns pose sampling. */
typedef struct PlayerHealthWildRuntimePrefix {
    OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;
} PlayerHealthWildRuntimePrefix;

typedef struct PlayerHealthThrowTracker {
    FieldSystem *fieldSystem;
    u16 generation;
    u16 mapGeneration;
    s32 projectileX, projectileY, projectileZ;
    s32 relativeX, relativeY, relativeZ;
    u8 active;
    u8 suppressContact;
    u8 attacking;
    u8 minImpactSpeed;
    u8 collisionDamage;
    u8 knockbackOptions;
    u8 groundAttacking;
    u8 groundMinImpactSpeed;
    u8 groundDamage;
    u8 groundKnockback;
    u8 throwBound;
    u8 ownerSlot;
    u16 ownerGeneration;
    /* The old tail padding keeps one heading across a vertical sample. */
    u8 impactDirection;
} PlayerHealthThrowTracker;

#ifndef PLAYER_HEALTH_HOST
typedef char PlayerHealthThrowTrackerSizeMustRemain48[
    sizeof(PlayerHealthThrowTracker) == 48 ? 1 : -1];
typedef char PlayerHealthThrowTrackerImpactDirectionMustRemain46[
    __builtin_offsetof(PlayerHealthThrowTracker, impactDirection) == 46 ? 1 : -1];
#endif

static PlayerHealthThrowTracker sThrow[OW_WILD_MAX_SPAWNS]
    __attribute__((section(".overworld_combat_state"))) = {0};

typedef struct CombatContactPose {
    s32 x, y, z;
    u16 generation;
    u8 valid;
} CombatContactPose;
static CombatContactPose sContactPose[OW_WILD_MAX_SPAWNS]
    __attribute__((section(".overworld_combat_state"))) = {0};
/* This measured local compiler policy keeps both fixed HP sections inside
 * their caps. Evidence: build/tickets/tkt64/hp-field-fit/winning-fit-receipt.json. */
#define COMBAT_CODE __attribute__((noinline, \
    optimize("Os,no-inline-small-functions,inline-functions-called-once," \
        "no-partial-inlining,no-tree-dominator-opts,no-tree-forwprop," \
        "no-tree-loop-ivcanon,no-tree-loop-im,move-loop-invariants,no-ipa-sra," \
        "no-expensive-optimizations,no-early-inlining,no-schedule-insns2," \
        "no-ipa-pta,tree-tail-merge,no-tree-bit-ccp,jump-tables"), \
    section(".overworld_combat_text")))

static BOOL COMBAT_CODE CombatContact_Current(const OverworldWildSpawnState *wild, u8 slot)
{
    const OverworldWildSpawn *spawn = &wild->spawns[slot];
    FieldSystem *field = wild->movementFieldSystem;
    /* This predicate runs for every slot pair each frame, so it must not call
     * the stock ID lookup, which scans the whole object array. The Field
     * generation gate comes first: within one generation the manager array is
     * stable, so the stored pointer is read only while it is that array's
     * slot. Ownership is then the engine-owned unique ID (0xE0 + slot) on an
     * active object. */
    return field != NULL && field == gFieldSysPtr && field->location != NULL
        && OverworldActorSystem_IsReady()
        && field->mapObjectMan != NULL && spawn->active && spawn->object != NULL
        && spawn->mapId == field->location->mapId
        && OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(
            OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext()) == wild->mapGeneration
        && spawn->object->id == spawn->objectId
        && (spawn->object->flags & MAPOBJECTFLAG_ACTIVE) != 0;
}

void COMBAT_CODE PlayerHealthContact_BeginFrame(const OverworldWildSpawnState *wild)
{
    u8 i;
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        CombatContactPose *pose = &sContactPose[i];
        pose->valid = CombatContact_Current(wild, i);
        if (pose->valid) {
            const LocalMapObject *object = wild->spawns[i].object;
            pose->x = (s32)object->posVec[0] + (s32)object->faceVec[0];
            pose->y = (s32)object->posVec[1] + (s32)object->faceVec[1]
                + (s32)object->unk88[1];
            pose->z = (s32)object->posVec[2] + (s32)object->faceVec[2];
            pose->generation = wild->spawns[i].encounterGeneration;
        }
    }
}

static BOOL COMBAT_CODE CombatContact_IsMounted(FieldSystem *field)
{
    const OverworldMountOverlayEntry *entry = OVERWORLD_MOUNT_OVERLAY_ENTRY;
    const OverworldMountRuntimeState *mount =
        (const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR;
    return entry->magic == OVERWORLD_MOUNT_OVERLAY_MAGIC
        && entry->version == OVERWORLD_MOUNT_OVERLAY_VERSION
        && entry->size == sizeof(*entry) && mount->fieldSystem == field
        && mount->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING;
}

/* Only accepted damage reaches this private dispatch. It fits the existing
 * health tail; all event storage and full source checks stay in shared code. */
static void __attribute__((noinline))
CombatContact_PublishPlayerDamage(const OverworldWildSpawnState *wild, u8 source)
{
    const OverworldQueryCodeAddonEntry *entry;
    const OverworldBehaviorConditionPreparedActor *prepared;
    OverworldQueryCodeAddonOwner owner;
    u8 slot = source & ~OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE;
    const OverworldWildOverlayRuntimeState *runtime = wild->movementRuntimeState;
    if (slot >= OW_WILD_MAX_SPAWNS || runtime == NULL || runtime->conditions == NULL
        || OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE() == NULL) return;
    prepared = &runtime->conditions->actors[slot];
    owner = (OverworldQueryCodeAddonOwner){(u32)(uintptr_t)wild->movementFieldSystem,
        prepared->subject.fieldEpoch, prepared->subject.mapGeneration};
    entry = ((const OverworldQueryCodeAddonServiceEntry *)OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR)->acquire(&owner);
    if (entry != NULL) entry->playerDamagePublish(wild,source,CombatContact_Current);
}

static void COMBAT_CODE CombatContact_HitPokemon(const OverworldWildSpawnState *wild,
    u8 source, u8 target, u8 attacking, u8 minSpeed, u8 damage,
    u16 speed, u8 options, u8 direction)
{
    u16 sourceHp, sourceMax;
    if (!OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALLOWED(options,
            target == OW_WILD_FOLLOWER_SLOT ? 4 : 2)
        || source == target || !CombatContact_Current(wild, target)
        || !PlayerHealthField_ContactsEnabled(wild->movementFieldSystem)
        || !PlayerHealth_ContactCanDamage(attacking, minSpeed, damage, speed)
        || !OverworldCombat_ReadHp(wild, source, &sourceHp, &sourceMax) || sourceHp == 0) {
        return;
    }
    if (OverworldCombat_TryHit(wild, target, damage, options, direction)) {
        CombatContact_PublishPlayerDamage(wild,
            target | OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE);
        PlaySE(SEQ_SE_DP_WALL_HIT2);
        if (target == OW_WILD_FOLLOWER_SLOT
            && CombatContact_IsMounted(wild->movementFieldSystem)) {
            PlayerHealthField_QueueKnockback(wild->movementFieldSystem, options, direction);
        }
    }
}

static void __attribute__((noinline, section(".player_health_tail"))) CombatContact_HitPlayer(const OverworldWildSpawnState *wild,
    u8 source, u8 attacking, u8 minSpeed, u8 damage,
    u16 speed, u8 options, u8 direction)
{
    u16 hp, maxHp;
    if (!OverworldCombat_ReadHp(wild, source, &hp, &maxHp) || hp == 0) return;
    /* Rider and mount are separate HP targets with one movement anchor. */
    if (OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_ALLOWED(options, 1)) {
        if (PlayerHealthField_TryContact(wild->movementFieldSystem,
                attacking, minSpeed, damage, speed, options, direction)
                == PLAYER_HEALTH_OK) {
            CombatContact_PublishPlayerDamage(wild, source);
        }
    }
}

void PlayerHealthContact_ResetAll(void)
{
    memset(sThrow, 0, sizeof(sThrow));
    memset(sContactPose, 0, sizeof(sContactPose));
}

BOOL __attribute__((noinline, section(".player_health_tail")))
PlayerHealthContact_Danger(FieldSystem *fieldSystem)
{
    const OverworldWildSpawnState *wild = &sOverworldWildSpawnState;
    const PlayerHealthWildRuntimePrefix *runtime =
        (const PlayerHealthWildRuntimePrefix *)wild->movementRuntimeState;
    OverworldActorPolicyView policy;
    s32 playerX, playerZ;
    u32 i;

    if (fieldSystem == NULL
        || fieldSystem->location == NULL
        || fieldSystem->playerAvatar == NULL
        || !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        || wild->movementFieldSystem != fieldSystem) {
        return FALSE;
    }
    playerX = GetPlayerXCoord(fieldSystem->playerAvatar);
    playerZ = GetPlayerYCoord(fieldSystem->playerAvatar);
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        PlayerHealthThrowTracker *tracker = &sThrow[i];

        if (wild->spawns[i].active
            && wild->spawns[i].object != NULL
            && wild->spawns[i].mapId == fieldSystem->location->mapId
            && tracker->fieldSystem == fieldSystem
            && tracker->generation == wild->spawns[i].encounterGeneration
            && tracker->mapGeneration == wild->mapGeneration) {
            s32 dx = wild->spawns[i].object->xCurr - playerX;
            s32 dz = wild->spawns[i].object->yCurr - playerZ;

            /* A Throw can travel up to eight tiles from its actor's tile. */
            if (dx < -8 || dx > 8 || dz < -8 || dz > 8) {
                continue;
            }
            if (tracker->active
                && (runtime == NULL
                    || !runtime->movementCustomJumpActive[i])) {
                tracker->active = FALSE;
                tracker->throwBound = FALSE;
            }
            if (tracker->active && tracker->attacking) {
                return TRUE;
            }
            if (!tracker->groundAttacking) {
                continue;
            }
            /* A warning covers profiled attackers during the alert and Walk.
             * A held target alone does not have attack authority. */
            if (wild->movementSpotStates[i]
                    == OW_WILD_SPAWNER_SPOT_STATE_EMOTING
                    && wild->movementEmoteBubbleIds[i] == 2) {
                return TRUE;
            }
            if (OverworldActorPolicy_Inspect((u8)i, &policy)
                && policy.actorActive
                && policy.walkMomentum.direction
                    != OW_WILD_WALK_DIRECTION_NONE) {
                return TRUE;
            }
        }
    }
    return FALSE;
}

static const OverworldWildBehaviorProfileData *
PlayerHealthContact_GetAttackLane(const OverworldWildBehaviorProfile *profile,
    u32 spotState);

static u8 PlayerHealthContact_AwayDirection(s32 sourceDx, s32 sourceDz)
{
    if (sourceDx == 0 && sourceDz == 0) {
        return 4;
    }
    if (sourceDx < 0) {
        sourceDx = -sourceDx;
        if (sourceDx >= (sourceDz < 0 ? -sourceDz : sourceDz)) {
            return 3;
        }
    } else if (sourceDx >= (sourceDz < 0 ? -sourceDz : sourceDz)) {
        return 2;
    }
    return sourceDz < 0 ? 1 : 0;
}

/* The caller has already rejected a real Walk proposal. Raw held keys are
 * not proof: a turn, a mount pause, or a skid can consume or redirect them. */
void __attribute__((noinline, section(".overworld_combat_text")))
__attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,"
    "no-if-conversion,no-tree-loop-im,no-schedule-insns2")))
PlayerHealthContact_ReportBlockedStep(
    FIELD_PLAYER_AVATAR *avatar, u8 direction)
{
    const OverworldWildSpawnState *wild = &sOverworldWildSpawnState;
    const PlayerHealthWildRuntimePrefix *runtime =
        (const PlayerHealthWildRuntimePrefix *)wild->movementRuntimeState;
    FieldSystem *fieldSystem;
    LocalMapObject *player;
    s32 targetX, targetZ;
    u32 i;

    if (avatar == NULL || avatar->mapObject == NULL || direction > 7) {
        return;
    }
    player = avatar->mapObject;
    /* The Wild owner is the current field. MapObject+0x128 is not a field
     * pointer; the avatar check below binds this callback to that field. */
    fieldSystem = wild->movementFieldSystem;
    if (fieldSystem == NULL
        || !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        || fieldSystem->location == NULL
        || fieldSystem->playerAvatar != avatar) {
        return;
    }
    targetX = player->xCurr;
    targetZ = player->yCurr;
    if (direction >= 4) {
        /* Mounted callers have already checked both side tiles. */
        targetZ += direction < 6 ? -1 : 1;
        targetX += (direction & 1u) ? 1 : -1;
    } else if (direction == 0) {
        targetZ--;
    } else if (direction == 1) {
        targetZ++;
    } else if (direction == 2) {
        targetX--;
    } else {
        targetX++;
    }
    for (i = 0; i < OW_WILD_MAX_SPAWNS; i++) {
        const OverworldWildSpawn *spawn = &wild->spawns[i];
        const PlayerHealthThrowTracker *tracker = &sThrow[i];
        OverworldActorPolicyView policy;
        u16 speed = 0;

        if (i == OW_WILD_FOLLOWER_SLOT || !spawn->active
            || spawn->object == NULL
            || (runtime != NULL && runtime->movementCustomJumpActive[i])
            || spawn->mapId != fieldSystem->location->mapId
            || fieldSystem->mapObjectMan == NULL
            || GetMapObjectByID(fieldSystem->mapObjectMan,
                spawn->objectId) != spawn->object
            || (spawn->object->flags & MAPOBJECTFLAG_ACTIVE) == 0
            || spawn->object->xCurr != targetX
            || spawn->object->yCurr != targetZ
            || OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(
                OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY->getContext())
                    != wild->mapGeneration
            || tracker->fieldSystem != fieldSystem
            || tracker->generation != spawn->encounterGeneration
            || tracker->mapGeneration != wild->mapGeneration) {
            continue;
        }
        /* Wild supplies the resolved attack lane through CONTACT_PROFILE.
         * Re-entering its resolver from the stock collision callback can
         * interrupt an in-progress condition update. */
        if (MapObject_IsSingleMovementActive(spawn->object)
            && OverworldActorPolicy_Inspect((u8)i, &policy)
            && policy.lastWalkTime != 0) {
            speed = 256u / policy.lastWalkTime;
        }
        if (CombatContact_IsMounted(fieldSystem)) {
            const OverworldWildBehaviorProfileData *lane =
                &((const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR)->snapshot.profile;
            u16 mountSpeed = 0;
            if (OverworldActorPolicy_Inspect(OW_WILD_FOLLOWER_SLOT, &policy)
                && policy.lastWalkTime != 0) mountSpeed = 256u / policy.lastWalkTime;
            CombatContact_HitPokemon(wild, OW_WILD_FOLLOWER_SLOT, i,
                lane->attacking, lane->minImpactSpeed, lane->collisionDamage,
                mountSpeed, lane->knockbackOptions,
                PlayerHealthContact_AwayDirection(player->xCurr - targetX, player->yCurr - targetZ));
        }
        CombatContact_HitPlayer(wild, i,
            tracker->groundAttacking, tracker->groundMinImpactSpeed,
            tracker->groundDamage, speed, tracker->groundKnockback,
            PlayerHealthContact_AwayDirection(
                (s32)spawn->object->xCurr - player->xCurr,
                (s32)spawn->object->yCurr - player->yCurr));
        return;
    }
}

/* This replaces only sub_0205D4B4's call to the stock collision query. That
 * site runs after the stock turn gate and before the blocked-step branch. */
int __attribute__((noinline, used, section(".player_health_extended_text")))
PlayerHealthContact_StockCollision(
    FIELD_PLAYER_AVATAR *avatar, LocalMapObject *player, int direction)
{
    int (*collision)(FIELD_PLAYER_AVATAR *, LocalMapObject *, int) =
        (int (*)(FIELD_PLAYER_AVATAR *, LocalMapObject *, int))0x0205DA35;
    int result = collision(avatar, player, direction);

    /* Surf accepts the special 0x20 result as an open step. */
    if (result != 0 && !(avatar->state == 2 && result == 0x20)
        && direction >= 0 && direction <= 3) {
        PlayerHealthContact_ReportBlockedStep(avatar, (u8)direction);
    }
    return result;
}

/* The two fixed Thumb stubs keep ARM9 and resident Mount calls independent of
 * the health overlay's internal code layout. */
int __attribute__((naked, used, section(".player_health_stock_collision_entry")))
PlayerHealthContact_StockCollisionEntry(
    FIELD_PLAYER_AVATAR *avatar, LocalMapObject *player, int direction)
{
    __asm__("ldr r3, 1f\n bx r3\n .align 2\n 1: .word PlayerHealthContact_StockCollision + 1");
}

void __attribute__((naked, used, section(".player_health_blocked_step_entry")))
PlayerHealthContact_BlockedStepEntry(FIELD_PLAYER_AVATAR *avatar, u8 direction)
{
    __asm__("ldr r3, 1f\n bx r3\n .align 2\n 1: .word PlayerHealthContact_ReportBlockedStep + 1");
}
#endif

#ifdef PLAYER_HEALTH_CONTACT_CLIP_HOST
#include "../lib/overworld/overworld_contact_geometry.c"
#define PlayerHealthContact_ThrowIntersectsPlayer OverworldContactGeometry_Intersects
#else
/* The sole slab calculation is pure heap code. This entry uses no actor or
 * movement state; acquire still proves the loaded package before calling it. */
static BOOL PlayerHealthContact_ThrowIntersectsPlayer(const PlayerHealthContactSegment *sample)
{
    const OverworldQueryCodeAddonServiceEntry *service;
    const OverworldQueryCodeAddonEntry *entry;
    if (OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE() == NULL) return FALSE;
    service = (const OverworldQueryCodeAddonServiceEntry *)OVERWORLD_QUERY_CODE_ADDON_SERVICE_ADDR;
    entry = service->acquire(&service->state->owner);
    return entry != NULL && entry->contactIntersects(sample);
}
#endif

#ifndef PLAYER_HEALTH_CONTACT_CLIP_HOST
static void COMBAT_CODE CombatContact_Sweep(const OverworldWildSpawnState *wild,
    u8 source, u8 owner, s32 oldX, s32 oldY, s32 oldZ,
    s32 newX, s32 newY, s32 newZ, u8 landing,
    u8 attacking, u8 minSpeed, u8 damage, u16 speed, u8 options, u32 direction)
{
    u8 target;
    for (target = 0; target < OW_WILD_MAX_SPAWNS; target++) {
        const LocalMapObject *object;
        const CombatContactPose *pose = &sContactPose[target];
        PlayerHealthContactSegment segment;
        s32 x, y, z;
        if (target == source || (target == owner
                && sThrow[source].ownerGeneration == wild->spawns[target].encounterGeneration)
            || !CombatContact_Current(wild, target)) {
            continue;
        }
        object = wild->spawns[target].object;
        x = (s32)object->posVec[0] + (s32)object->faceVec[0];
        y = (s32)object->posVec[1] + (s32)object->faceVec[1]
                + (s32)object->unk88[1];
        z = (s32)object->posVec[2] + (s32)object->faceVec[2];
        segment.oldX = (oldX - (pose->valid
            && pose->generation == wild->spawns[target].encounterGeneration ? pose->x : x)) >> 6;
        segment.oldY = (oldY - (pose->valid
            && pose->generation == wild->spawns[target].encounterGeneration ? pose->y : y)) >> 6;
        segment.oldZ = (oldZ - (pose->valid
            && pose->generation == wild->spawns[target].encounterGeneration ? pose->z : z)) >> 6;
        segment.newX = (newX - x) >> 6;
        segment.newY = (newY - y) >> 6;
        segment.newZ = (newZ - z) >> 6;
        segment.landingSample = landing;
        if (PlayerHealthContact_ThrowIntersectsPlayer(&segment)) {
            CombatContact_HitPokemon(wild, source, target,
                attacking, minSpeed, damage, speed, options,
                direction);
        }
    }
}

void COMBAT_CODE PlayerHealthContact_EndFrame(const OverworldWildSpawnState *wild)
{
    const PlayerHealthWildRuntimePrefix *runtime =
        (const PlayerHealthWildRuntimePrefix *)wild->movementRuntimeState;
    u8 slot;
    if (!PlayerHealthField_ContactsEnabled(wild->movementFieldSystem)) {
        return;
    }
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; slot++) {
        const PlayerHealthThrowTracker *tracker = &sThrow[slot];
        const CombatContactPose *pose = &sContactPose[slot];
        const LocalMapObject *object;
        const OverworldWildBehaviorProfileData *mountLane = NULL;
        s32 x, y, z, dx, dz;
        u16 speed;
        u8 attacking = tracker->groundAttacking;
        u8 minSpeed = tracker->groundMinImpactSpeed;
        u8 damage = tracker->groundDamage;
        u8 options = tracker->groundKnockback;
        if (slot == OW_WILD_FOLLOWER_SLOT && CombatContact_IsMounted(wild->movementFieldSystem)) {
            mountLane = &((const OverworldMountRuntimeState *)OVERWORLD_MOUNT_RUNTIME_STATE_ADDR)->snapshot.profile;
            attacking = mountLane->attacking;
            minSpeed = mountLane->minImpactSpeed;
            damage = mountLane->collisionDamage;
            options = mountLane->knockbackOptions;
        }
        if (!pose->valid || !CombatContact_Current(wild, slot)
            || pose->generation != wild->spawns[slot].encounterGeneration
            || (mountLane == NULL && (tracker->generation != pose->generation
                || tracker->mapGeneration != wild->mapGeneration
                || tracker->fieldSystem != wild->movementFieldSystem))
            || !attacking
            || (runtime != NULL && runtime->movementCustomJumpActive[slot])) {
            continue;
        }
        object = wild->spawns[slot].object;
        x = (s32)object->posVec[0] + (s32)object->faceVec[0];
        y = (s32)object->posVec[1] + (s32)object->faceVec[1]
                + (s32)object->unk88[1];
        z = (s32)object->posVec[2] + (s32)object->faceVec[2];
        dx = x - pose->x;
        dz = z - pose->z;
        if (dx < 0) dx = -dx;
        if (dz < 0) dz = -dz;
        speed = (u32)(dx > dz ? dx : dz) >> 8;
        CombatContact_Sweep(wild, slot, slot, pose->x, pose->y, pose->z, x, y, z, FALSE,
            attacking, minSpeed, damage, speed, options,
            PlayerHealthContact_AwayDirection(pose->x - x, pose->z - z));
    }
}

static void COMBAT_CODE CombatContact_Blocked(const OverworldWildSpawnState *wild,
    u8 slot, const OverworldWildBehaviorProfileData *lane, u32 aux)
{
    const LocalMapObject *source = wild->spawns[slot].object;
    FieldSystem *field = wild->movementFieldSystem;
    u8 direction = aux >> 16;
    s32 x, z;
    u8 target;
    if (lane == NULL || !CombatContact_Current(wild, slot) || direction > 7) return;
    x = source->xCurr + (direction == 2 || direction == 4 || direction == 6 ? -1
        : direction == 3 || direction == 5 || direction == 7 ? 1 : 0);
    z = source->yCurr + (direction == 0 || direction == 4 || direction == 5 ? -1
        : direction == 1 || direction == 6 || direction == 7 ? 1 : 0);
    if (field->playerAvatar != NULL && x == GetPlayerXCoord(field->playerAvatar)
        && z == GetPlayerYCoord(field->playerAvatar)) {
        if (lane->attacking == 1) sThrow[slot].suppressContact = TRUE;
        CombatContact_HitPlayer(wild, slot, lane->attacking, lane->minImpactSpeed,
            lane->collisionDamage, (u16)aux, lane->knockbackOptions,
            PlayerHealthContact_AwayDirection(source->xCurr - x, source->yCurr - z));
    }
    for (target = 0; target < OW_WILD_MAX_SPAWNS; target++) {
        const LocalMapObject *object;
        const PlayerHealthThrowTracker *other = &sThrow[target];
        OverworldActorPolicyView policy;
        u16 otherSpeed = 0;
        if (target == slot || !CombatContact_Current(wild, target)) continue;
        object = wild->spawns[target].object;
        if (object->xCurr != x || object->yCurr != z) continue;
        CombatContact_HitPokemon(wild, slot, target, lane->attacking, lane->minImpactSpeed,
            lane->collisionDamage, (u16)aux, lane->knockbackOptions,
            PlayerHealthContact_AwayDirection(source->xCurr - x, source->yCurr - z));
        /* An actor that walks into a stationary attacker is also a contact.
         * Use the attacker's measured speed, never the victim's speed. */
        if (other->fieldSystem != field || other->mapGeneration != wild->mapGeneration
            || other->generation != wild->spawns[target].encounterGeneration) continue;
        if (MapObject_IsSingleMovementActive(object)
            && OverworldActorPolicy_Inspect(target, &policy) && policy.lastWalkTime != 0)
            otherSpeed = 256u / policy.lastWalkTime;
        CombatContact_HitPokemon(wild, target, slot, other->groundAttacking,
            other->groundMinImpactSpeed, other->groundDamage, otherSpeed, other->groundKnockback,
            PlayerHealthContact_AwayDirection(x - source->xCurr, z - source->yCurr));
    }
}

static void __attribute__((noinline)) PlayerHealthContact_StepMotion(
    PlayerHealthThrowTracker *tracker, const OverworldWildSpawnState *wild, u8 slot,
    const OverworldMotionSample *motion, u32 aux)
{
    FieldSystem *fieldSystem = wild->movementFieldSystem;
    PlayerHealthContactSegment segment;
    const LocalMapObject *player;
    u32 stepX, stepY, stepZ;
    s32 travelX, travelZ;
    u32 impactSpeed;
    u8 direction;
    BOOL intersects;

    if ((aux & 1) == 0
        || (tracker->throwBound && (aux & 4) == 0)) {
        tracker->active = FALSE;
        return;
    }
    player = fieldSystem != NULL && fieldSystem->playerAvatar != NULL
        ? fieldSystem->playerAvatar->mapObject : NULL;
    if (motion == NULL || player == NULL) {
        tracker->active = FALSE;
        return;
    }
    segment.oldX = tracker->relativeX;
    segment.oldY = tracker->relativeY;
    segment.oldZ = tracker->relativeZ;
    segment.newX = (motion->renderX - (s32)player->posVec[0]
        - (s32)player->faceVec[0]) >> 6;
    segment.newY = (motion->renderY - (s32)player->posVec[1]
        - (s32)player->faceVec[1]) >> 6;
    segment.newZ = (motion->renderZ - (s32)player->posVec[2]
        - (s32)player->faceVec[2]) >> 6;
    segment.landingSample = (aux & 2) != 0;
    travelX = motion->renderX - tracker->projectileX;
    travelZ = motion->renderZ - tracker->projectileZ;
    direction = PlayerHealthContact_AwayDirection(-travelX, -travelZ);
    if (direction < 4) tracker->impactDirection = direction;
    else direction = tracker->impactDirection;
    /* Signed native poses; unsigned magnitudes avoid negating INT_MIN. */
    stepX = (u32)motion->renderX - (u32)tracker->projectileX;
    stepY = (u32)motion->renderY - (u32)tracker->projectileY;
    stepZ = (u32)motion->renderZ - (u32)tracker->projectileZ;
    if (motion->renderX < tracker->projectileX) stepX = 0u - stepX;
    if (motion->renderY < tracker->projectileY) stepY = 0u - stepY;
    if (motion->renderZ < tracker->projectileZ) stepZ = 0u - stepZ;
    impactSpeed = stepX > stepZ ? stepX : stepZ;
    if (stepY > impactSpeed) impactSpeed = stepY;
    impactSpeed >>= 8;
    if (impactSpeed > 255) {
        impactSpeed = 255;
    }
    intersects = PlayerHealthContact_ThrowIntersectsPlayer(&segment);
    CombatContact_Sweep(wild, slot, tracker->ownerSlot,
        tracker->projectileX, tracker->projectileY, tracker->projectileZ,
        motion->renderX, motion->renderY, motion->renderZ, segment.landingSample,
        tracker->attacking, tracker->minImpactSpeed, tracker->collisionDamage,
        (u16)impactSpeed, tracker->knockbackOptions, direction);
    tracker->projectileX = motion->renderX;
    tracker->projectileY = motion->renderY;
    tracker->projectileZ = motion->renderZ;
    tracker->relativeX = segment.newX;
    tracker->relativeY = segment.newY;
    tracker->relativeZ = segment.newZ;
    if (intersects) {
        CombatContact_HitPlayer(wild, slot,
            tracker->attacking, tracker->minImpactSpeed,
            tracker->collisionDamage, (u16)impactSpeed,
            tracker->knockbackOptions,
            direction);
    }
    if ((aux & 2) != 0) {
        tracker->active = FALSE;
        tracker->suppressContact = TRUE;
    }
}

static void __attribute__((noinline)) PlayerHealthContact_LaunchMotion(
    PlayerHealthThrowTracker *tracker, const OverworldWildSpawnState *wild,
    u16 slot, u8 attacking, u8 minImpactSpeed, u8 collisionDamage,
    u8 knockbackOptions,
    BOOL throwBound)
{
    const PlayerHealthWildRuntimePrefix *runtime =
        (const PlayerHealthWildRuntimePrefix *)wild->movementRuntimeState;
    FieldSystem *fieldSystem = wild->movementFieldSystem;
    const LocalMapObject *player =
        fieldSystem != NULL && fieldSystem->playerAvatar != NULL
            ? fieldSystem->playerAvatar->mapObject : NULL;
    s32 projectileY;

    if (runtime == NULL || player == NULL) {
        tracker->active = FALSE;
        return;
    }
    tracker->fieldSystem = fieldSystem;
    tracker->generation = wild->spawns[slot].encounterGeneration;
    tracker->mapGeneration = wild->mapGeneration;
    tracker->projectileX =
        (s32)runtime->movementCustomJumpStartX[slot]
            * (16 << 12) + (8 << 12);
    projectileY = runtime->movementCustomJumpStartBaseY[slot];
    tracker->projectileY = projectileY;
    tracker->projectileZ =
        (s32)runtime->movementCustomJumpStartY[slot]
            * (16 << 12) + (8 << 12);
    tracker->relativeX = (tracker->projectileX
        - (s32)player->posVec[0] - (s32)player->faceVec[0]) >> 6;
    tracker->relativeY = (projectileY
        - (s32)player->posVec[1] - (s32)player->faceVec[1]) >> 6;
    tracker->relativeZ = (tracker->projectileZ
        - (s32)player->posVec[2] - (s32)player->faceVec[2]) >> 6;
    tracker->active = PlayerHealth_ContactCanDamage(
        attacking, minImpactSpeed, collisionDamage, 255);
    tracker->suppressContact = FALSE;
    tracker->throwBound = throwBound;
    tracker->ownerSlot = slot;
    tracker->ownerGeneration = wild->spawns[slot].encounterGeneration;
    tracker->impactDirection = PlayerHealthContact_AwayDirection(
        runtime->movementCustomJumpStartX[slot] - runtime->movementCustomJumpTargetX[slot],
        runtime->movementCustomJumpStartY[slot] - runtime->movementCustomJumpTargetY[slot]);
    tracker->attacking = attacking;
    tracker->minImpactSpeed = minImpactSpeed;
    tracker->collisionDamage = collisionDamage;
    tracker->knockbackOptions = knockbackOptions;
}

/* Mirror the movement controller's owner/tired lane selection. Ground reads
 * its own slot's state; Throw supplies the carrier's state through aux. */
static const OverworldWildBehaviorProfileData *
PlayerHealthContact_GetAttackLane(const OverworldWildBehaviorProfile *profile,
    u32 spotState)
{
    if (profile == NULL) {
        return NULL;
    }
    return spotState == OW_WILD_SPAWNER_SPOT_STATE_TIRED
        ? &profile->tired : &profile->owner;
}

BOOL __attribute__((optimize("Os,no-tree-forwprop,no-expensive-optimizations,"
    "no-if-conversion,no-tree-loop-im,no-schedule-insns2")))
PlayerHealthContact_HandleEvent(const void *wildState,
    u32 code, const void *sample, u32 aux)
{
    PlayerHealthThrowTracker *tracker;
    const LocalMapObject *spawn;
    const OverworldWildBehaviorProfileData *attackProfile;
    const OverworldWildSpawnState *wild;
    FieldSystem *fieldSystem;
    u16 slot = code >> 8;
    u8 kind = code;
    u16 generation;
    u16 mapGeneration;
    s32 dx, dy;

    if (slot >= OW_WILD_MAX_SPAWNS || wildState == NULL) {
        return FALSE;
    }
    wild = (const OverworldWildSpawnState *)wildState;
    fieldSystem = wild->movementFieldSystem;
    tracker = &sThrow[slot];
    if (kind == PLAYER_HEALTH_MOTION_CANCEL) {
        if (tracker->fieldSystem == fieldSystem) {
            tracker->active = FALSE;
            tracker->throwBound = FALSE;
        }
        return FALSE;
    }
    generation = wild->spawns[slot].encounterGeneration;
    mapGeneration = wild->mapGeneration;
    if (kind == PLAYER_HEALTH_CONTACT_PROFILE) {
        attackProfile = PlayerHealthContact_GetAttackLane(
            (const OverworldWildBehaviorProfile *)sample,
            wild->movementSpotStates[slot]);
        if (tracker->fieldSystem != fieldSystem
            || tracker->generation != generation
            || tracker->mapGeneration != mapGeneration) {
            tracker->active = FALSE;
            tracker->suppressContact = FALSE;
        }
        tracker->fieldSystem = fieldSystem;
        tracker->generation = generation;
        tracker->mapGeneration = mapGeneration;
        tracker->groundAttacking = attackProfile != NULL
            && attackProfile->attacking == 1
            && attackProfile->collisionDamage != 0
            && attackProfile->collisionDamage <= PLAYER_HEALTH_DAMAGE_CAP;
        tracker->groundMinImpactSpeed = attackProfile != NULL
            ? attackProfile->minImpactSpeed : 0;
        tracker->groundDamage = attackProfile != NULL
            ? attackProfile->collisionDamage : 0;
        tracker->groundKnockback = attackProfile != NULL
            ? attackProfile->knockbackOptions : 0;
        return FALSE;
    }
    if (kind == PLAYER_HEALTH_THROW_LAUNCH) {
        attackProfile = PlayerHealthContact_GetAttackLane(
            (const OverworldWildBehaviorProfile *)sample, aux & 0xFF);
        PlayerHealthContact_LaunchMotion(tracker, wild, slot,
            attackProfile != NULL ? attackProfile->attacking : 0,
            attackProfile != NULL ? attackProfile->minImpactSpeed : 0,
            attackProfile != NULL ? attackProfile->collisionDamage : 0,
            attackProfile != NULL ? attackProfile->knockbackOptions : 0,
            TRUE);
        tracker->ownerSlot = aux >> 8;
        tracker->ownerGeneration = tracker->ownerSlot < OW_WILD_MAX_SPAWNS
            ? wild->spawns[tracker->ownerSlot].encounterGeneration : 0;
        return FALSE;
    }
    if (kind == PLAYER_HEALTH_CONTACT_SUPPRESS_BATTLE) {
        spawn = wild->spawns[slot].object;
        if (spawn == NULL || fieldSystem == NULL
            || fieldSystem->playerAvatar == NULL
            || tracker->fieldSystem != fieldSystem
            || tracker->generation != generation
            || tracker->mapGeneration != mapGeneration) {
            tracker->suppressContact = FALSE;
            return FALSE;
        }
        dx = (s32)spawn->xCurr
            - GetPlayerXCoord(fieldSystem->playerAvatar);
        dy = (s32)spawn->yCurr
            - GetPlayerYCoord(fieldSystem->playerAvatar);
        if (dx < 0) {
            dx = -dx;
        }
        if (dy < 0) {
            dy = -dy;
        }
        if (dx + dy > 1) {
            tracker->suppressContact = FALSE;
        }
        return tracker->suppressContact;
    }
    if (tracker->fieldSystem != fieldSystem
        || tracker->generation != generation
        || tracker->mapGeneration != mapGeneration) {
        tracker->active = FALSE;
        tracker->suppressContact = FALSE;
        return FALSE;
    }
    if (kind == PLAYER_HEALTH_CONTACT_BLOCKED_ATTACK) {
        CombatContact_Blocked(wild, slot, (const OverworldWildBehaviorProfileData *)sample, aux);
        return FALSE;
    }
    if (kind == PLAYER_HEALTH_MOTION_LAND) {
        if (tracker->active) {
            tracker->suppressContact = TRUE;
        }
        tracker->active = FALSE;
        tracker->throwBound = FALSE;
        return FALSE;
    }
    if (kind != PLAYER_HEALTH_MOTION_STEP || sample == NULL) {
        return FALSE;
    }
    if (((const OverworldMotionSample *)sample)->elapsed == 1
        && (aux & 4) == 0) {
        /* The first accepted pose starts an ordinary wild motion. A thrown
         * target already carries the throwing Pokémon's launch profile. */
        tracker->active = FALSE;
        tracker->throwBound = FALSE;
        if (tracker->groundAttacking) {
            PlayerHealthContact_LaunchMotion(tracker, wild, slot,
                tracker->groundAttacking, tracker->groundMinImpactSpeed,
                tracker->groundDamage, tracker->groundKnockback, FALSE);
        }
    }
    if (!tracker->active) {
        return FALSE;
    }
    PlayerHealthContact_StepMotion(tracker, wild, slot,
        (const OverworldMotionSample *)sample, aux);
    return FALSE;
}
#endif
