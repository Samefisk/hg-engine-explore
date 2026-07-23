#include "../../include/overworld_follower_selector.h"

#include "../../include/constants/buttons.h"
#include "../../include/constants/file.h"
#include "../../include/constants/sndseq.h"
#include "../../include/constants/species.h"
#include "../../include/map_events_internal.h"
#include "../../include/overlay.h"
#include "../../include/overworld_wild_helper.h"
#include "../../include/overworld_wild_spawns_internal.h"
#include "../../include/save.h"
#include "../../include/script.h"
#include "../../include/sound.h"
#include "../../include/task.h"

#define FOLLOWER_SELECTOR_TASK_PRIORITY 89
#define FOLLOWER_SELECTOR_HOLD_CONFIRM_FRAMES 2
#define FOLLOWER_SELECTOR_RELEASE_CONFIRM_FRAMES 2
#define FOLLOWER_SELECTOR_SYSTEM_HELD_KEYS (*(vu32 *)0x021D1150)
#define FOLLOWER_SELECTOR_SYSTEM_NEW_KEYS (*(vu32 *)0x021D1154)
#define FOLLOWER_RECALL_BALL_WHITE_TAG 231
#define FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_OFFSET 0x50
#define FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET 0x54
#define FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_TIMING_OFFSET 0x55
#define FOLLOWER_RECALL_MATERIAL_COMMAND 4
#define FOLLOWER_RECALL_CALLBACK_AFTER_COMMAND 3
#define FOLLOWER_RECALL_RENDER_STATE_MATERIAL_RESULT_OFFSET 0xB0
#define FOLLOWER_RECALL_MATERIAL_TEXIMAGE_PARAM_OFFSET 0x10
#define FOLLOWER_RECALL_TEXIMAGE_FORMAT_SHIFT 26
#define FOLLOWER_RECALL_TEXIMAGE_FORMAT_MASK 7
#define FOLLOWER_RECALL_TEXIMAGE_FORMAT_PLTT16 3
#define FOLLOWER_RECALL_WHITE_PALETTE_SIZE 32
#define FOLLOWER_RECALL_FORWARD_OFFSET_FX32 0x4000
#define FOLLOWER_RECALL_RIGHT_HAND_OFFSET_FX32 0x6000
#define FOLLOWER_RECALL_HAND_HEIGHT_FX32 0x8000
#define FOLLOWER_RECALL_WAIT_TIMEOUT_FRAMES 16
#define FOLLOWER_RECALL_PROGRESS_MAX 4096

void OverworldFollowerSelector_ClearMemory(void *memory, u32 size)
{
    volatile u8 *dst = memory;

    while (size-- != 0) {
        *dst++ = 0;
    }
}

typedef void (*FollowerRecallSetActorScaleFunc)(
    void *actor,
    const VecFx32 *scale);
typedef VecFx32 *(*FollowerRecallGetActorScaleFunc)(void *actor);
typedef u32 (*FollowerRecallAllocPaletteFunc)(u32, BOOL, u32);
typedef int (*FollowerRecallFreePaletteFunc)(u32);
typedef void (*FollowerRecallFlushRangeFunc)(const void *, u32);
typedef void (*FollowerRecallBeginPaletteLoadFunc)(void);
typedef void (*FollowerRecallLoadPaletteFunc)(const void *, u32, u32);
typedef void (*FollowerRecallEndPaletteLoadFunc)(void);
#define FOLLOWER_RECALL_SET_ACTOR_SCALE \
    ((FollowerRecallSetActorScaleFunc)(0x02023E78 | 1))
#define FOLLOWER_RECALL_GET_ACTOR_SCALE \
    ((FollowerRecallGetActorScaleFunc)(0x02023E94 | 1))
#define FOLLOWER_RECALL_ALLOC_PALETTE \
    (*(FollowerRecallAllocPaletteFunc *)0x0211092C)
#define FOLLOWER_RECALL_FREE_PALETTE \
    (*(FollowerRecallFreePaletteFunc *)0x02110930)
#define FOLLOWER_RECALL_FLUSH_RANGE \
    ((FollowerRecallFlushRangeFunc)0x020D2894)
#define FOLLOWER_RECALL_BEGIN_PALETTE_LOAD \
    ((FollowerRecallBeginPaletteLoadFunc)0x020D0AD4)
#define FOLLOWER_RECALL_LOAD_PALETTE \
    ((FollowerRecallLoadPaletteFunc)0x020D0B08)
#define FOLLOWER_RECALL_END_PALETTE_LOAD \
    ((FollowerRecallEndPaletteLoadFunc)0x020D0B74)

u8 OverworldWildSpawns_GetSelectedFollowerPartySlot(FieldSystem *fieldSystem)
{
    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    }
    return SaveMisc_GetCustomFollowerPartySlot(
        Sav2_Misc_get(fieldSystem->savedata));
}

BOOL OverworldWildSpawns_IsFollowerPartySlotEligible(
    FieldSystem *fieldSystem,
    u8 partySlot)
{
    struct Party *party;
    struct PartyPokemon *pokemon;

    if (fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || partySlot >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT) {
        return FALSE;
    }
    party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party == NULL || partySlot >= party->count) {
        return FALSE;
    }
    pokemon = Party_GetMonByIndex(party, partySlot);
    return pokemon != NULL
        && GetMonData(pokemon, MON_DATA_SPECIES, NULL) != SPECIES_NONE
        && GetMonData(pokemon, MON_DATA_IS_EGG, NULL) == FALSE
        && GetMonData(pokemon, MON_DATA_LEVEL, NULL) != 0
        && GetMonData(pokemon, MON_DATA_HP, NULL) != 0;
}

struct PartyPokemon *OverworldFollowerSelector_GetSelectedPokemon(
    FieldSystem *fieldSystem,
    u8 *partySlot)
{
    struct Party *party;
    u8 selectedSlot;

    if (fieldSystem == NULL || fieldSystem->savedata == NULL) {
        return NULL;
    }
    if (sOverworldWildSpawnState.followerReleaseState
            == OW_WILD_FOLLOWER_RELEASE_READY
        && !OverworldFollowerSelector_IsReleaseTileAvailable(
            fieldSystem,
            sOverworldWildSpawnState.followerReleaseX,
            sOverworldWildSpawnState.followerReleaseY)) {
        sOverworldWildSpawnState.followerReleaseState =
            OW_WILD_FOLLOWER_RELEASE_REQUESTED;
    }
    selectedSlot = OverworldWildSpawns_GetSelectedFollowerPartySlot(
        fieldSystem);
    party = SaveData_GetPlayerPartyPtr(fieldSystem->savedata);
    if (party == NULL
        || selectedSlot >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT
        || selectedSlot >= party->count
        || !OverworldWildSpawns_IsFollowerPartySlotEligible(
            fieldSystem,
            selectedSlot)) {
        return NULL;
    }
    *partySlot = selectedSlot;
    return Party_GetMonByIndex(party, selectedSlot);
}

BOOL OverworldWildSpawns_SelectFollowerPartySlot(
    FieldSystem *fieldSystem,
    u8 partySlot)
{
    if (fieldSystem == NULL
        || fieldSystem->savedata == NULL
        || (partySlot != CUSTOM_FOLLOWER_PARTY_SLOT_NONE
            && !OverworldWildSpawns_IsFollowerPartySlotEligible(
                fieldSystem,
                partySlot))) {
        return FALSE;
    }
    if (partySlot != CUSTOM_FOLLOWER_PARTY_SLOT_NONE
        && sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT].active
        && sOverworldWildSpawnState.activeFollowerPartySlot == partySlot) {
        partySlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    }
    SaveMisc_SetCustomFollowerPartySlot(
        Sav2_Misc_get(fieldSystem->savedata),
        partySlot);
    sOverworldWildSpawnState.followerReleaseState =
        partySlot == CUSTOM_FOLLOWER_PARTY_SLOT_NONE
            ? OW_WILD_FOLLOWER_RELEASE_NONE
            : OW_WILD_FOLLOWER_RELEASE_REQUESTED;
    gOverworldWildFieldIdleRearmPending |=
        OW_WILD_FIELD_IDLE_REARM_PENDING
        | OW_WILD_FIELD_IDLE_ZERO_REFILL_PENDING
        | OW_WILD_FIELD_IDLE_FOLLOWER_REFILL_PENDING;
    return TRUE;
}

typedef enum OverworldFollowerRecallPhase {
    FOLLOWER_RECALL_PHASE_NONE = 0,
    FOLLOWER_RECALL_PHASE_WAIT_BALL,
    FOLLOWER_RECALL_PHASE_PULL,
    FOLLOWER_RECALL_PHASE_FINISH,
} OverworldFollowerRecallPhase;

typedef struct OverworldFollowerRecallState {
    FieldSystem *fieldSystem;
    MapObjectMan *manager;
    LocalMapObject *objects;
    LocalMapObject *follower;
    LocalMapObject *ball;
    void *whiteMaterialActor;
    void (*originalRenderCallback)(void *);
    u32 whitePaletteKey;
    u32 originalPosition[3];
    u32 originalFace[3];
    u32 originalUnk88[3];
    u32 originalUnk94[3];
    VecFx32 originalScale;
    u16 mapId;
    u16 mapGeneration;
    u16 encounterGeneration;
    u8 desiredSlot;
    u8 originalMovementCooldown;
    u8 originalHadSuppressedShadow;
    u8 originalRenderCallbackCommand;
    u8 originalRenderCallbackTiming;
    u8 frame;
    u8 phase;
    u8 pullFrames;
} OverworldFollowerRecallState;

static OverworldFollowerRecallState sFollowerRecall;
static const u32 sFollowerRecallWhitePalette[8] = {
    0x7FFF7FFF,
    0x7FFF7FFF,
    0x7FFF7FFF,
    0x7FFF7FFF,
    0x7FFF7FFF,
    0x7FFF7FFF,
    0x7FFF7FFF,
    0x7FFF7FFF,
};

static BOOL OverworldFollowerRecall_Begin(
    FieldSystem *fieldSystem,
    u8 desiredSlot);
static BOOL OverworldFollowerRecall_Tick(FieldSystem *fieldSystem);
static void OverworldFollowerRecall_Cancel(FieldSystem *fieldSystem);

typedef enum OverworldFollowerSelectorInputState {
    FOLLOWER_SELECTOR_INPUT_IDLE = 0,
    FOLLOWER_SELECTOR_INPUT_PREPARING,
    FOLLOWER_SELECTOR_INPUT_VISIBLE,
    FOLLOWER_SELECTOR_INPUT_RECALLING,
} OverworldFollowerSelectorInputState;

static FieldSystem *sFollowerSelectorFieldSystem;
static SysTask *sFollowerSelectorTask;
static u16 sFollowerSelectorMapId;
static u8 sFollowerSelectorHighlightedSlot;
static u8 sFollowerSelectorInputState;
static u8 sFollowerSelectorYHeldFrames;
static u8 sFollowerSelectorYReleaseFrames;

static void OverworldFollowerSelectorInput_ResetState(void)
{
    sFollowerSelectorFieldSystem = NULL;
    sFollowerSelectorTask = NULL;
    sFollowerSelectorMapId = 0;
    sFollowerSelectorHighlightedSlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
    sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_IDLE;
    sFollowerSelectorYHeldFrames = 0;
    sFollowerSelectorYReleaseFrames = 0;
    OverworldFollowerSelector_ClearActiveFlag();
}

static u16 OverworldFollowerSelectorInput_ReadHeldKeys(void)
{
    /* Follow HeartGold's configured button mode just like FieldInput_Update. */
    return (u16)(FOLLOWER_SELECTOR_SYSTEM_HELD_KEYS & PAD_ALL_MASK);
}

static u16 OverworldFollowerSelectorInput_ReadNewKeys(void)
{
    return (u16)(FOLLOWER_SELECTOR_SYSTEM_NEW_KEYS & PAD_ALL_MASK);
}

static BOOL OverworldFollowerSelectorInput_IsFieldPaused(
    FieldSystem *fieldSystem)
{
    const u8 *fieldState = fieldSystem == NULL
        ? NULL
        : *(const u8 *const *)fieldSystem;

    return fieldState == NULL || *(const u32 *)(fieldState + 8) != 0;
}

static BOOL OverworldFollowerSelectorInput_IsFieldContextCurrent(
    FieldSystem *fieldSystem)
{
    return fieldSystem != NULL
        && fieldSystem == gFieldSysPtr
        && fieldSystem->location != NULL
        && fieldSystem->taskman == NULL
        && sub_0203DF8C(fieldSystem)
        && !OverworldFollowerSelectorInput_IsFieldPaused(fieldSystem)
        && (u16)fieldSystem->location->mapId == sFollowerSelectorMapId;
}

static BOOL OverworldFollowerSelectorInput_IsPlayerBallActive(void)
{
    const OverworldWildHelperOverlayEntry *entry;

    if (!IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_HELPER)) {
        return FALSE;
    }
    entry = OVERWORLD_WILD_HELPER_OVERLAY_ENTRY;
    return entry->magic == OVERWORLD_WILD_HELPER_OVERLAY_MAGIC
        && entry->version == OVERWORLD_WILD_HELPER_OVERLAY_VERSION
        && entry->size == sizeof(*entry)
        && entry->getPlayerBallProjectileObject != NULL
        && entry->getPlayerBallProjectileObject() != NULL;
}

static int OverworldFollowerRecall_DirectionDeltaX(int direction)
{
    if (direction == 2) {
        return -1;
    }
    return direction == 3 ? 1 : 0;
}

static int OverworldFollowerRecall_DirectionDeltaY(int direction)
{
    if (direction == 0) {
        return -1;
    }
    return direction == 1 ? 1 : 0;
}

BOOL OverworldFollowerSelector_IsReleaseTileAvailable(
    FieldSystem *fieldSystem,
    int x,
    int y)
{
    u8 behavior;

    if (x < 0
        || y < 0
        || IsMetatileBlockedAt(fieldSystem, x, y)) {
        return FALSE;
    }
    behavior = GetMetatileBehaviorAt(fieldSystem, x, y);
    if (behavior == 0xFF
        || behavior == 6
        || behavior == 16
        || behavior == 18
        || behavior == 21
        || behavior == 42) {
        return FALSE;
    }
    return TRUE;
}

s32 OverworldFollowerSelector_GetReleaseDistance(FieldSystem *fieldSystem)
{
    LocalMapObject *player;
    int distance;
    int dx;
    int dy;
    int x;
    int y;

    if (fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL) {
        return 0;
    }
    player = fieldSystem->playerAvatar->mapObject;
    dx = OverworldFollowerRecall_DirectionDeltaX(player->curFacing);
    dy = OverworldFollowerRecall_DirectionDeltaY(player->curFacing);
    for (distance = 5; distance > 0; distance--) {
        x = MapObject_GetCurrentX(player) + dx * distance;
        y = MapObject_GetCurrentY(player) + dy * distance;
        if (OverworldFollowerSelector_IsReleaseTileAvailable(
                fieldSystem,
                x,
                y)) {
            sOverworldWildSpawnState.followerReleaseX = (s16)x;
            sOverworldWildSpawnState.followerReleaseY = (s16)y;
            return distance << 16;
        }
    }
    return 0;
}

static BOOL OverworldFollowerRecall_ObjectIsCurrent(
    FieldSystem *fieldSystem,
    LocalMapObject *object,
    int objectId)
{
    MapObjectMan *manager;

    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem != sFollowerRecall.fieldSystem
        || sFollowerRecall.manager == NULL
        || fieldSystem->mapObjectMan != sFollowerRecall.manager) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    return object != NULL
        && manager != NULL
        && manager->objects == sFollowerRecall.objects
        && object >= manager->objects
        && object < manager->objects + manager->object_count
        && (object->flags & MAPOBJECTFLAG_ACTIVE) != 0
        && object->id == objectId;
}

static BOOL OverworldFollowerRecall_FollowerIsCurrent(FieldSystem *fieldSystem)
{
    OverworldWildSpawn *spawn =
        &sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT];

    return sFollowerRecall.phase != FOLLOWER_RECALL_PHASE_NONE
        && fieldSystem != NULL
        && fieldSystem == gFieldSysPtr
        && fieldSystem == sFollowerRecall.fieldSystem
        && fieldSystem->location != NULL
        && fieldSystem->mapObjectMan == sFollowerRecall.manager
        && (u16)fieldSystem->location->mapId == sFollowerRecall.mapId
        && sOverworldWildSpawnState.mapGeneration
            == sFollowerRecall.mapGeneration
        && spawn->active
        && spawn->mapId == sFollowerRecall.mapId
        && spawn->encounterGeneration == sFollowerRecall.encounterGeneration
        && spawn->object == sFollowerRecall.follower
        && spawn->objectId == OW_WILD_OBJECT_ID_START + OW_WILD_FOLLOWER_SLOT
        && OverworldFollowerRecall_ObjectIsCurrent(
            fieldSystem,
            sFollowerRecall.follower,
            spawn->objectId)
        && sFollowerRecall.follower->scriptId
            == OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT;
}

static BOOL OverworldFollowerRecall_PositionBallAtHand(FieldSystem *fieldSystem)
{
    LocalMapObject *player;
    LocalMapObject *ball = sFollowerRecall.ball;
    int dx;
    int dy;
    s32 renderY;

    if (fieldSystem == NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || !OverworldFollowerRecall_ObjectIsCurrent(
            fieldSystem,
            ball,
            OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID)) {
        return FALSE;
    }
    player = fieldSystem->playerAvatar->mapObject;
    if (player->curFacing < 0 || player->curFacing > 3) {
        return FALSE;
    }
    dx = OverworldFollowerRecall_DirectionDeltaX(player->curFacing);
    dy = OverworldFollowerRecall_DirectionDeltaY(player->curFacing);
    renderY = (s32)player->posVec[1];
    MapObject_SetCurrentX(ball, MapObject_GetCurrentX(player));
    MapObject_SetCurrentY(ball, MapObject_GetCurrentY(player));
    ball->xInit = player->xInit;
    ball->yInit = player->yInit;
    ball->xPrev = player->xPrev;
    ball->yPrev = player->yPrev;
    ball->hPrev = player->hPrev;
    ball->posVec[0] = (u32)((s32)player->posVec[0]
        + dx * FOLLOWER_RECALL_FORWARD_OFFSET_FX32
        - dy * FOLLOWER_RECALL_RIGHT_HAND_OFFSET_FX32);
    ball->posVec[1] = (u32)renderY;
    ball->posVec[2] = (u32)((s32)player->posVec[2]
        + dy * FOLLOWER_RECALL_FORWARD_OFFSET_FX32
        + dx * FOLLOWER_RECALL_RIGHT_HAND_OFFSET_FX32);
    ball->hCurr = renderY >> 15;
    ball->curFacing = player->curFacing;
    ball->nextFacing = player->nextFacing;
    ball->faceVec[0] = 0;
    ball->faceVec[1] = player->faceVec[1]
        + FOLLOWER_RECALL_HAND_HEIGHT_FX32;
    ball->faceVec[2] = 0;
    ball->unk88[0] = 0;
    ball->unk88[1] = ball->faceVec[1];
    ball->unk88[2] = 0;
    ball->unk94[0] = 0;
    ball->unk94[1] = 0;
    ball->unk94[2] = 0;
    return TRUE;
}

static s32 OverworldFollowerRecall_Lerp(s32 start, s32 target, s32 progress)
{
    return start + (s32)(((s64)target - start) * progress
        / FOLLOWER_RECALL_PROGRESS_MAX);
}

static u8 __attribute__((noinline)) OverworldFollowerRecall_GetPullFrames(
    const LocalMapObject *follower,
    const LocalMapObject *player)
{
    int distanceX = follower->xCurr - player->xCurr;
    int distanceY = follower->yCurr - player->yCurr;

    if (distanceX < 0) {
        distanceX = -distanceX;
    }
    if (distanceY < 0) {
        distanceY = -distanceY;
    }
    if (distanceY > distanceX) {
        distanceX = distanceY;
    }
    if (distanceX > 5) {
        distanceX = 5;
    }
    if (distanceX < 1) {
        distanceX = 1;
    }
    return (u8)(distanceX * 2 + 6);
}

static void OverworldFollowerRecall_ApplyWhiteMaterial(void *renderState)
{
    void *materialResult = *(void **)((u8 *)renderState
        + FOLLOWER_RECALL_RENDER_STATE_MATERIAL_RESULT_OFFSET);
    u32 paletteKey = sFollowerRecall.whitePaletteKey;

    if (paletteKey != 0
        && materialResult != NULL
        && (((*(u32 *)((u8 *)materialResult
                    + FOLLOWER_RECALL_MATERIAL_TEXIMAGE_PARAM_OFFSET)
                >> FOLLOWER_RECALL_TEXIMAGE_FORMAT_SHIFT)
            & FOLLOWER_RECALL_TEXIMAGE_FORMAT_MASK)
            == FOLLOWER_RECALL_TEXIMAGE_FORMAT_PLTT16)) {
        reg_G3_TEXPLTT_BASE = (paletteKey & 0xFFFF) >> 1;
    }
}

static BOOL OverworldFollowerRecall_AttachWhiteMaterial(void *actor)
{
    void (**callback)(void *);
    u32 paletteKey = FOLLOWER_RECALL_ALLOC_PALETTE(
        FOLLOWER_RECALL_WHITE_PALETTE_SIZE,
        FALSE,
        0);

    if (paletteKey == 0) {
        return FALSE;
    }
    FOLLOWER_RECALL_FLUSH_RANGE(
        sFollowerRecallWhitePalette,
        sizeof(sFollowerRecallWhitePalette));
    FOLLOWER_RECALL_BEGIN_PALETTE_LOAD();
    FOLLOWER_RECALL_LOAD_PALETTE(
        sFollowerRecallWhitePalette,
        (paletteKey & 0xFFFF) << 3,
        sizeof(sFollowerRecallWhitePalette));
    FOLLOWER_RECALL_END_PALETTE_LOAD();

    callback = (void (**)(void *))((u8 *)actor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_OFFSET);
    sFollowerRecall.originalRenderCallback = *callback;
    sFollowerRecall.originalRenderCallbackCommand = *((u8 *)actor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET);
    sFollowerRecall.originalRenderCallbackTiming = *((u8 *)actor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_TIMING_OFFSET);
    sFollowerRecall.whiteMaterialActor = actor;
    sFollowerRecall.whitePaletteKey = paletteKey;
    *callback = OverworldFollowerRecall_ApplyWhiteMaterial;
    *((u8 *)actor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET) =
        FOLLOWER_RECALL_MATERIAL_COMMAND;
    *((u8 *)actor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_TIMING_OFFSET) =
        FOLLOWER_RECALL_CALLBACK_AFTER_COMMAND;
    return TRUE;
}

static void OverworldFollowerRecall_ReleaseWhiteMaterial(void *actor)
{
    void (**callback)(void *);
    u32 paletteKey = sFollowerRecall.whitePaletteKey;

    if (paletteKey == 0) {
        return;
    }
    if (actor == sFollowerRecall.whiteMaterialActor) {
        callback = (void (**)(void *))((u8 *)actor
            + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_OFFSET);
        if (*callback == OverworldFollowerRecall_ApplyWhiteMaterial) {
            *callback = sFollowerRecall.originalRenderCallback;
            *((u8 *)actor
                + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET) =
                sFollowerRecall.originalRenderCallbackCommand;
            *((u8 *)actor
                + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_TIMING_OFFSET) =
                sFollowerRecall.originalRenderCallbackTiming;
        }
    }
    sFollowerRecall.whiteMaterialActor = NULL;
    sFollowerRecall.whitePaletteKey = 0;
    (void)FOLLOWER_RECALL_FREE_PALETTE(paletteKey);
}

static void OverworldFollowerRecall_Finish(
    FieldSystem *fieldSystem,
    BOOL restoreFollower)
{
    OverworldWildSpawn *spawn =
        &sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT];
    LocalMapObject *follower = sFollowerRecall.follower;
    LocalMapObject *ball = sFollowerRecall.ball;
    void *actor = NULL;
    BOOL followerIsCurrent =
        OverworldFollowerRecall_FollowerIsCurrent(fieldSystem);

    if (restoreFollower) {
        sOverworldWildSpawnState.captureTargetMask &=
            (u16)~(1u << OW_WILD_FOLLOWER_SLOT);
    }
    if (restoreFollower
        && sOverworldWildSpawnState.mapGeneration
            == sFollowerRecall.mapGeneration
        && spawn->active
        && spawn->encounterGeneration == sFollowerRecall.encounterGeneration) {
        sOverworldWildSpawnState.movementCooldowns[
            OW_WILD_FOLLOWER_SLOT] =
            sFollowerRecall.originalMovementCooldown;
    }
    if (OverworldFollowerRecall_ObjectIsCurrent(
            fieldSystem,
            follower,
            OW_WILD_OBJECT_ID_START + OW_WILD_FOLLOWER_SLOT)) {
        actor = ov01_021F72DC(follower);
    }
    /*
     * An actor is submitted only through its active object in the current
     * manager. If this identity guard or actor lookup fails, the stored actor
     * is no longer renderable and must not be dereferenced. Otherwise Release
     * restores its callback before returning the private palette to VRAM.
     */
    OverworldFollowerRecall_ReleaseWhiteMaterial(actor);
    if (followerIsCurrent) {
        if (restoreFollower) {
            if (actor != NULL) {
                FOLLOWER_RECALL_SET_ACTOR_SCALE(
                    actor,
                    &sFollowerRecall.originalScale);
            }
            memcpy(
                follower->posVec,
                sFollowerRecall.originalPosition,
                sizeof(sFollowerRecall.originalPosition));
            memcpy(
                follower->faceVec,
                sFollowerRecall.originalFace,
                sizeof(sFollowerRecall.originalFace));
            memcpy(
                follower->unk88,
                sFollowerRecall.originalUnk88,
                sizeof(sFollowerRecall.originalUnk88));
            memcpy(
                follower->unk94,
                sFollowerRecall.originalUnk94,
                sizeof(sFollowerRecall.originalUnk94));
            if (sFollowerRecall.originalHadSuppressedShadow) {
                MapObject_SetBits(follower, MAPOBJECTFLAG_UNK20);
            } else {
                MapObject_ClearBits(follower, MAPOBJECTFLAG_UNK20);
            }
            MapObject_ClearBits(follower, BIT_VANISH);
        }
    }
    if (fieldSystem != NULL
        && OverworldFollowerRecall_ObjectIsCurrent(
            fieldSystem,
            ball,
            OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID)) {
        if (fieldSystem->taskman == NULL) {
            MapObject_ClearBits(
                ball,
                BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13);
            DeleteMapObject(ball);
        } else {
            MapObject_SetBits(ball, BIT_VANISH);
            OverworldFollowerSelector_SetStaleBallCleanupPending();
            sFollowerRecall.phase = FOLLOWER_RECALL_PHASE_NONE;
            return;
        }
    }
    OverworldFollowerSelector_ClearMemory(
        &sFollowerRecall,
        sizeof(sFollowerRecall));
}

static void OverworldFollowerRecall_Cancel(FieldSystem *fieldSystem)
{
    if (sFollowerRecall.phase != FOLLOWER_RECALL_PHASE_NONE) {
        OverworldFollowerRecall_Finish(fieldSystem, TRUE);
    }
}

static BOOL OverworldFollowerRecall_WaitOrCancel(FieldSystem *fieldSystem)
{
    if (++sFollowerRecall.frame < FOLLOWER_RECALL_WAIT_TIMEOUT_FRAMES) {
        return TRUE;
    }
    OverworldFollowerRecall_Cancel(fieldSystem);
    return FALSE;
}

static BOOL OverworldFollowerRecall_CleanupStaleBall(FieldSystem *fieldSystem)
{
    MapObjectMan *manager;
    int objectIndex;

    if (!OverworldFollowerSelector_IsStaleBallCleanupPending()) {
        return TRUE;
    }
    if (sFollowerRecall.fieldSystem == NULL) {
        if (fieldSystem == NULL
            || fieldSystem != gFieldSysPtr
            || fieldSystem->taskman != NULL
            || fieldSystem->location == NULL
            || fieldSystem->mapObjectMan == NULL
            || OverworldFollowerSelectorInput_IsPlayerBallActive()) {
            return FALSE;
        }
        manager = (MapObjectMan *)fieldSystem->mapObjectMan;
        if (manager->objects == NULL) {
            return FALSE;
        }
        for (objectIndex = 0;
             objectIndex < (int)manager->object_count;
             objectIndex++) {
            LocalMapObject *object = &manager->objects[objectIndex];

            if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
                && object->id
                    == OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID) {
                MapObject_ClearBits(
                    object,
                    BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13);
                DeleteMapObject(object);
                break;
            }
        }
        OverworldFollowerSelector_ClearStaleBallCleanupPending();
        return TRUE;
    }
    if (fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem != sFollowerRecall.fieldSystem
        || fieldSystem->location == NULL
        || (u16)fieldSystem->location->mapId != sFollowerRecall.mapId
        || sOverworldWildSpawnState.mapGeneration
            != sFollowerRecall.mapGeneration
        || fieldSystem->mapObjectMan != sFollowerRecall.manager) {
        OverworldFollowerSelector_ClearStaleBallCleanupPending();
        OverworldFollowerSelector_ClearMemory(
            &sFollowerRecall,
            sizeof(sFollowerRecall));
        return TRUE;
    }
    if (fieldSystem->taskman != NULL) {
        return FALSE;
    }
    if (OverworldFollowerRecall_ObjectIsCurrent(
            fieldSystem,
            sFollowerRecall.ball,
            OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID)) {
        MapObject_ClearBits(
            sFollowerRecall.ball,
            BIT_JUMP_START | BIT_MOVE_START | MAPOBJECTFLAG_UNK13);
        DeleteMapObject(sFollowerRecall.ball);
    }
    OverworldFollowerSelector_ClearStaleBallCleanupPending();
    OverworldFollowerSelector_ClearMemory(
        &sFollowerRecall,
        sizeof(sFollowerRecall));
    return TRUE;
}

static BOOL OverworldFollowerRecall_Begin(
    FieldSystem *fieldSystem,
    u8 desiredSlot)
{
    OverworldWildSpawn *spawn =
        &sOverworldWildSpawnState.spawns[OW_WILD_FOLLOWER_SLOT];
    LocalMapObject *follower;
    LocalMapObject *ball;
    MapObjectMan *manager;
    void *actor;
    VecFx32 *scale;
    int objectIndex;

    if (!OverworldFollowerRecall_CleanupStaleBall(fieldSystem)
        || sFollowerRecall.phase != FOLLOWER_RECALL_PHASE_NONE
        || fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || fieldSystem->taskman != NULL
        || fieldSystem->playerAvatar == NULL
        || fieldSystem->playerAvatar->mapObject == NULL
        || fieldSystem->mapObjectMan == NULL
        || !spawn->active
        || spawn->mapId != fieldSystem->location->mapId
        || spawn->object == NULL
        || spawn->objectId
            != OW_WILD_OBJECT_ID_START + OW_WILD_FOLLOWER_SLOT) {
        return FALSE;
    }
    manager = (MapObjectMan *)fieldSystem->mapObjectMan;
    if (manager->objects == NULL) {
        return FALSE;
    }
    follower = spawn->object;
    if (follower < manager->objects
        || follower >= manager->objects + manager->object_count
        || (follower->flags & MAPOBJECTFLAG_ACTIVE) == 0
        || follower->id != spawn->objectId
        || follower->scriptId != OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT) {
        return FALSE;
    }
    for (objectIndex = 0;
         objectIndex < (int)manager->object_count;
         objectIndex++) {
        LocalMapObject *object = &manager->objects[objectIndex];

        if ((object->flags & MAPOBJECTFLAG_ACTIVE) != 0
            && object->id == OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID) {
            return FALSE;
        }
    }
    actor = ov01_021F72DC(follower);
    if (actor == NULL
        || (scale = FOLLOWER_RECALL_GET_ACTOR_SCALE(actor)) == NULL) {
        return FALSE;
    }
    ball = CreateSpecialFieldObjectWithParams(
        manager,
        MapObject_GetCurrentX(fieldSystem->playerAvatar->mapObject),
        MapObject_GetCurrentY(fieldSystem->playerAvatar->mapObject),
        fieldSystem->playerAvatar->mapObject->curFacing,
        FOLLOWER_RECALL_BALL_WHITE_TAG,
        0,
        fieldSystem->location->mapId,
        0,
        0,
        0);
    if (ball == NULL) {
        return FALSE;
    }
    OverworldFollowerSelector_ClearMemory(
        &sFollowerRecall,
        sizeof(sFollowerRecall));
    sFollowerRecall.fieldSystem = fieldSystem;
    sFollowerRecall.manager = manager;
    sFollowerRecall.objects = manager->objects;
    sFollowerRecall.follower = follower;
    sFollowerRecall.ball = ball;
    memcpy(
        sFollowerRecall.originalPosition,
        follower->posVec,
        sizeof(sFollowerRecall.originalPosition));
    memcpy(
        sFollowerRecall.originalFace,
        follower->faceVec,
        sizeof(sFollowerRecall.originalFace));
    memcpy(
        sFollowerRecall.originalUnk88,
        follower->unk88,
        sizeof(sFollowerRecall.originalUnk88));
    memcpy(
        sFollowerRecall.originalUnk94,
        follower->unk94,
        sizeof(sFollowerRecall.originalUnk94));
    sFollowerRecall.originalScale = *scale;
    sFollowerRecall.mapId = (u16)fieldSystem->location->mapId;
    sFollowerRecall.mapGeneration = sOverworldWildSpawnState.mapGeneration;
    sFollowerRecall.encounterGeneration = spawn->encounterGeneration;
    sFollowerRecall.desiredSlot = desiredSlot;
    sFollowerRecall.originalMovementCooldown =
        sOverworldWildSpawnState.movementCooldowns[OW_WILD_FOLLOWER_SLOT];
    sFollowerRecall.originalHadSuppressedShadow =
        (follower->flags & MAPOBJECTFLAG_UNK20) != 0;
    if (!OverworldFollowerRecall_AttachWhiteMaterial(actor)) {
        DeleteMapObject(ball);
        OverworldFollowerSelector_ClearMemory(
            &sFollowerRecall,
            sizeof(sFollowerRecall));
        return FALSE;
    }
    sFollowerRecall.phase = FOLLOWER_RECALL_PHASE_WAIT_BALL;
    MapObject_SetID(ball, OW_WILD_PLAYER_BALL_PROJECTILE_OBJECT_ID);
    MapObject_SetBits(
        ball,
        MAPOBJECTFLAG_UNK18 | MAPOBJECTFLAG_UNK20 | BIT_VANISH);
    sOverworldWildSpawnState.captureTargetMask |=
        (u16)(1u << OW_WILD_FOLLOWER_SLOT);
    sOverworldWildSpawnState.movementCooldowns[OW_WILD_FOLLOWER_SLOT] = 0xFF;
    MapObject_SetBits(follower, MAPOBJECTFLAG_UNK20);
    if (!OverworldFollowerRecall_PositionBallAtHand(fieldSystem)) {
        OverworldFollowerRecall_Cancel(fieldSystem);
        return FALSE;
    }
    return TRUE;
}

static BOOL OverworldFollowerRecall_Tick(FieldSystem *fieldSystem)
{
    LocalMapObject *follower = sFollowerRecall.follower;
    LocalMapObject *ball = sFollowerRecall.ball;
    void *followerActor;
    void *ballActor;
    void (**renderCallback)(void *);
    VecFx32 scale;
    s32 progress;
    s32 previousProgress;
    s32 stepProgress;
    s32 inverseProgress;
    s32 frame;
    s32 pullFrames;
    s32 pullDurationCube;
    u8 desiredSlot;
    int vectorIndex;

    if (sFollowerRecall.phase == FOLLOWER_RECALL_PHASE_NONE) {
        return FALSE;
    }
    if (!OverworldFollowerRecall_FollowerIsCurrent(fieldSystem)
        || !OverworldFollowerRecall_PositionBallAtHand(fieldSystem)) {
        OverworldFollowerRecall_Cancel(fieldSystem);
        return FALSE;
    }
    followerActor = ov01_021F72DC(follower);
    ballActor = ov01_021F72DC(ball);
    if (followerActor == NULL || ballActor == NULL) {
        if (sFollowerRecall.phase != FOLLOWER_RECALL_PHASE_WAIT_BALL) {
            OverworldFollowerRecall_Cancel(fieldSystem);
            return FALSE;
        }
        return OverworldFollowerRecall_WaitOrCancel(fieldSystem);
    }
    if (sFollowerRecall.phase == FOLLOWER_RECALL_PHASE_WAIT_BALL) {
        if (ball->gfxId != FOLLOWER_RECALL_BALL_WHITE_TAG) {
            return OverworldFollowerRecall_WaitOrCancel(fieldSystem);
        }
        sFollowerRecall.pullFrames = OverworldFollowerRecall_GetPullFrames(
            follower,
            fieldSystem->playerAvatar->mapObject);
        MapObject_ClearBits(ball, BIT_VANISH);
        sFollowerRecall.phase = FOLLOWER_RECALL_PHASE_PULL;
        sFollowerRecall.frame = 0;
        PlaySE(SEQ_SE_DP_BALL_DRAW_IN);
        return TRUE;
    }
    if (sFollowerRecall.phase == FOLLOWER_RECALL_PHASE_FINISH) {
        desiredSlot = sFollowerRecall.desiredSlot;
        if (desiredSlot != CUSTOM_FOLLOWER_PARTY_SLOT_NONE
            && !OverworldWildSpawns_IsFollowerPartySlotEligible(
                fieldSystem,
                desiredSlot)) {
            desiredSlot = CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
        }
        if (!OverworldWildSpawns_SelectFollowerPartySlot(
                fieldSystem,
                desiredSlot)) {
            OverworldFollowerRecall_Cancel(fieldSystem);
            return FALSE;
        }
        MapObject_SetBits(follower, BIT_VANISH);
        OverworldFollowerRecall_Finish(fieldSystem, FALSE);
        return FALSE;
    }
    if (sFollowerRecall.whiteMaterialActor != followerActor
        || sFollowerRecall.whitePaletteKey == 0) {
        OverworldFollowerRecall_Cancel(fieldSystem);
        return FALSE;
    }
    renderCallback = (void (**)(void *))((u8 *)followerActor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_OFFSET);
    *renderCallback = OverworldFollowerRecall_ApplyWhiteMaterial;
    *((u8 *)followerActor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_COMMAND_OFFSET) =
        FOLLOWER_RECALL_MATERIAL_COMMAND;
    *((u8 *)followerActor
        + FOLLOWER_RECALL_ACTOR_RENDER_CALLBACK_TIMING_OFFSET) =
        FOLLOWER_RECALL_CALLBACK_AFTER_COMMAND;

    frame = sFollowerRecall.frame + 1;
    pullFrames = sFollowerRecall.pullFrames;
    pullDurationCube = pullFrames * pullFrames * pullFrames;
    previousProgress = sFollowerRecall.frame
        * sFollowerRecall.frame
        * sFollowerRecall.frame;
    progress = frame * frame * frame;
    stepProgress = (progress - previousProgress)
        * FOLLOWER_RECALL_PROGRESS_MAX
        / (pullDurationCube - previousProgress);
    progress = progress * FOLLOWER_RECALL_PROGRESS_MAX
        / pullDurationCube;
    inverseProgress = FOLLOWER_RECALL_PROGRESS_MAX - progress;
    for (vectorIndex = 0; vectorIndex < 3; vectorIndex++) {
        follower->posVec[vectorIndex] = (u32)OverworldFollowerRecall_Lerp(
            (s32)follower->posVec[vectorIndex],
            (s32)ball->posVec[vectorIndex],
            stepProgress);
        follower->faceVec[vectorIndex] = (u32)OverworldFollowerRecall_Lerp(
            (s32)follower->faceVec[vectorIndex],
            (s32)ball->faceVec[vectorIndex],
            stepProgress);
        follower->unk88[vectorIndex] = follower->faceVec[vectorIndex];
        follower->unk94[vectorIndex] = 0;
    }
    /* Couple scale to travel progress, with a 50% floor at the ball. */
    inverseProgress += progress / 2;
    scale.x = sFollowerRecall.originalScale.x * inverseProgress >> 12;
    scale.y = sFollowerRecall.originalScale.y * inverseProgress >> 12;
    scale.z = sFollowerRecall.originalScale.z * inverseProgress >> 12;
    FOLLOWER_RECALL_SET_ACTOR_SCALE(followerActor, &scale);
    sFollowerRecall.frame++;
    if (sFollowerRecall.frame < sFollowerRecall.pullFrames) {
        return TRUE;
    }
    sFollowerRecall.phase = FOLLOWER_RECALL_PHASE_FINISH;
    return TRUE;
}

static u8 OverworldFollowerSelectorInput_FirstEligibleSlot(u8 eligibleMask)
{
    u8 slot;

    for (slot = 0; slot < CUSTOM_FOLLOWER_PARTY_SLOT_COUNT; slot++) {
        if ((eligibleMask & (1 << slot)) != 0) {
            return slot;
        }
    }
    return CUSTOM_FOLLOWER_PARTY_SLOT_NONE;
}

static u8 OverworldFollowerSelectorInput_CycleSlot(
    u8 eligibleMask,
    u8 currentSlot,
    int direction)
{
    int step;
    int slot = currentSlot;

    for (step = 0; step < CUSTOM_FOLLOWER_PARTY_SLOT_COUNT; step++) {
        slot += direction;
        if (slot < 0) {
            slot = CUSTOM_FOLLOWER_PARTY_SLOT_COUNT - 1;
        } else if (slot >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT) {
            slot = 0;
        }
        if ((eligibleMask & (1 << slot)) != 0) {
            return (u8)slot;
        }
    }
    return currentSlot;
}

static void OverworldFollowerSelectorInput_Close(SysTask *task)
{
    OverworldFollowerRecall_Cancel(sFollowerSelectorFieldSystem);
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_PREPARING
        || sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_VISIBLE
        || OverworldFollowerSelectorUI_IsOpen()) {
        OverworldFollowerSelectorUI_Close();
    }
    OverworldFollowerSelectorInput_ResetState();
    if (task != NULL) {
        DestroySysTask(task);
    }
}

static void OverworldFollowerSelectorInput_Hide(void)
{
    sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_IDLE;
    OverworldFollowerSelector_ClearActiveFlag();
}

static void OverworldFollowerSelectorInput_Task(SysTask *task, void *data)
{
    FieldSystem *fieldSystem = (FieldSystem *)data;
    u8 eligibleMask;

    if (task != sFollowerSelectorTask
        || fieldSystem != sFollowerSelectorFieldSystem
        || !OverworldFollowerSelectorInput_IsFieldContextCurrent(fieldSystem)) {
        if (sFollowerSelectorInputState
                != FOLLOWER_SELECTOR_INPUT_IDLE) {
            OverworldFollowerSelector_SetReleaseGate();
        }
        OverworldFollowerSelectorInput_Close(task);
        return;
    }
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_IDLE
        && OverworldFollowerSelector_IsPartySnapshotDirty()) {
        if (OverworldFollowerSelectorUI_IsOpen()) {
            OverworldFollowerSelectorUI_Close();
        }
        sFollowerSelectorHighlightedSlot =
            OverworldWildSpawns_GetSelectedFollowerPartySlot(fieldSystem);
        OverworldFollowerSelectorUI_BeginPartySnapshot();
        OverworldFollowerSelector_ClearPartySnapshotDirty();
        return;
    }
    if (sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_RECALLING) {
        if (!OverworldFollowerSelectorUI_IsOpen()) {
            if (!OverworldFollowerSelectorUI_SnapshotNextPartySlot(
                    fieldSystem)) {
                return;
            }
            eligibleMask = OverworldFollowerSelectorUI_GetEligibleMask();
            if (eligibleMask == 0) {
                OverworldFollowerSelectorInput_Close(task);
                return;
            }
            if (sFollowerSelectorHighlightedSlot
                    >= CUSTOM_FOLLOWER_PARTY_SLOT_COUNT
                || (eligibleMask & (1 << sFollowerSelectorHighlightedSlot))
                    == 0) {
                sFollowerSelectorHighlightedSlot =
                    OverworldFollowerSelectorInput_FirstEligibleSlot(
                        eligibleMask);
            }
            if (!OverworldFollowerSelectorUI_Open(
                    fieldSystem,
                    sFollowerSelectorHighlightedSlot)) {
                OverworldFollowerSelectorInput_Close(task);
                return;
            }
        }
        while (!OverworldFollowerSelectorUI_Update()) {
            if (OverworldFollowerSelectorUI_IsOpen()) {
                /*
                 * Load one unit per frame even during idle preloading. This
                 * prevents NARC/VRAM setup from monopolizing a field frame;
                 * sprites are still submitted together only after READY.
                 */
                return;
            }
            if (sFollowerSelectorInputState
                    != FOLLOWER_SELECTOR_INPUT_IDLE) {
                OverworldFollowerSelector_SetReleaseGate();
            }
            OverworldFollowerSelectorInput_Close(task);
            return;
        }
        if (sFollowerSelectorInputState
                == FOLLOWER_SELECTOR_INPUT_PREPARING) {
            sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_VISIBLE;
        }
        return;
    }
    if (!OverworldFollowerRecall_Tick(fieldSystem)) {
        OverworldFollowerSelector_SetReleaseGate();
        OverworldFollowerSelectorInput_Hide();
    }
}

static BOOL OverworldFollowerSelectorInput_Begin(
    FieldSystem *fieldSystem,
    BOOL activate)
{
    if (sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_IDLE
        || fieldSystem == NULL
        || fieldSystem != gFieldSysPtr
        || fieldSystem->location == NULL
        || fieldSystem->taskman != NULL
        || (sFollowerSelectorTask != NULL
            && (fieldSystem != sFollowerSelectorFieldSystem
                || (u16)fieldSystem->location->mapId
                    != sFollowerSelectorMapId))
        || !sub_0203DF8C(fieldSystem)
        || OverworldFollowerSelectorInput_IsFieldPaused(fieldSystem)
        || !OverworldFollowerRecall_CleanupStaleBall(fieldSystem)) {
        return FALSE;
    }
    if (sFollowerSelectorTask == NULL) {
        sFollowerSelectorTask = CreateSysTask(
            OverworldFollowerSelectorInput_Task,
            fieldSystem,
            FOLLOWER_SELECTOR_TASK_PRIORITY);
        if (sFollowerSelectorTask == NULL) {
            return FALSE;
        }
        sFollowerSelectorFieldSystem = fieldSystem;
        sFollowerSelectorMapId = (u16)fieldSystem->location->mapId;
        sFollowerSelectorHighlightedSlot =
            OverworldWildSpawns_GetSelectedFollowerPartySlot(fieldSystem);
        OverworldFollowerSelectorUI_BeginPartySnapshot();
    }
    if (activate) {
        sFollowerSelectorYHeldFrames = 0;
        sFollowerSelectorYReleaseFrames = 0;
        sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_PREPARING;
        OverworldFollowerSelector_SetActiveFlag();
    }
    return TRUE;
}

void OverworldFollowerSelectorInput_Filter(FieldSystem *fieldSystem)
{
    u16 physicalKeys;
    u16 physicalNewKeys;
    u8 eligibleMask;
    u8 nextSlot;
    BOOL yHeld;

    physicalKeys = OverworldFollowerSelectorInput_ReadHeldKeys();
    physicalNewKeys = OverworldFollowerSelectorInput_ReadNewKeys();
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_IDLE) {
        if (sFollowerSelectorTask == NULL
            && OverworldFollowerSelectorInput_Begin(fieldSystem, FALSE)) {
            /* Start background preloading before the first Y press. */
            OverworldFollowerSelectorInput_Task(
                sFollowerSelectorTask,
                fieldSystem);
        }
        if ((physicalNewKeys & PAD_BUTTON_Y) == 0) {
            return;
        }
        if (!OverworldFollowerSelectorInput_Begin(fieldSystem, TRUE)) {
            return;
        }
    }
    if (fieldSystem != sFollowerSelectorFieldSystem
        || !OverworldFollowerSelectorInput_IsFieldContextCurrent(fieldSystem)) {
        /* Fail closed on the invalid frame and through the following release. */
        OverworldFollowerSelector_SetReleaseGate();
        OverworldFollowerSelectorInput_Cancel(fieldSystem);
        return;
    }

    yHeld = (physicalKeys & PAD_BUTTON_Y) != 0;

    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_PREPARING) {
        if (!yHeld) {
            if (sFollowerSelectorYHeldFrames
                    < FOLLOWER_SELECTOR_HOLD_CONFIRM_FRAMES) {
                /* Reject an unconfirmed one-frame Y pulse. */
                sFollowerSelectorYHeldFrames = 0;
                OverworldFollowerSelectorInput_Hide();
                return;
            }
            /* Preserve a real release until the first UI load is complete. */
            if (sFollowerSelectorYReleaseFrames
                    < FOLLOWER_SELECTOR_RELEASE_CONFIRM_FRAMES) {
                sFollowerSelectorYReleaseFrames++;
            }
            return;
        }
        if (sFollowerSelectorYHeldFrames
                < FOLLOWER_SELECTOR_HOLD_CONFIRM_FRAMES) {
            sFollowerSelectorYHeldFrames++;
        }
        sFollowerSelectorYReleaseFrames = 0;
        return;
    }
    if (sFollowerSelectorInputState == FOLLOWER_SELECTOR_INPUT_RECALLING) {
        return;
    }

    if (!yHeld) {
        if (sFollowerSelectorYHeldFrames
                < FOLLOWER_SELECTOR_HOLD_CONFIRM_FRAMES) {
            /* Reject a one-frame false Y edge without selecting anything. */
            sFollowerSelectorYHeldFrames = 0;
            OverworldFollowerSelectorInput_Hide();
            return;
        }
        if (sFollowerSelectorYReleaseFrames
                < FOLLOWER_SELECTOR_RELEASE_CONFIRM_FRAMES) {
            sFollowerSelectorYReleaseFrames++;
        }
        if (sFollowerSelectorYReleaseFrames
                < FOLLOWER_SELECTOR_RELEASE_CONFIRM_FRAMES) {
            return;
        }
        if (OverworldFollowerSelectorInput_IsPlayerBallActive()) {
            /*
             * The menu may coexist with a launched ball, but follower recall
             * uses the same reserved map-object ID. Keep the confirmed choice
             * visible and commit it as soon as the capture presentation gives
             * that object back.
             */
            return;
        }
        if (OverworldFollowerRecall_Begin(
                fieldSystem,
                sFollowerSelectorHighlightedSlot)) {
            sFollowerSelectorInputState = FOLLOWER_SELECTOR_INPUT_RECALLING;
            if (!OverworldFollowerRecall_Tick(fieldSystem)) {
                OverworldFollowerSelector_SetReleaseGate();
                OverworldFollowerSelectorInput_Hide();
            }
            return;
        }
        (void)OverworldWildSpawns_SelectFollowerPartySlot(
            fieldSystem,
            sFollowerSelectorHighlightedSlot);
        /* Keep a still-held shoulder from leaking into the Player Ball. */
        OverworldFollowerSelector_SetReleaseGate();
        OverworldFollowerSelectorInput_Hide();
        return;
    }
    if (sFollowerSelectorYHeldFrames
            < FOLLOWER_SELECTOR_HOLD_CONFIRM_FRAMES) {
        sFollowerSelectorYHeldFrames++;
    }
    sFollowerSelectorYReleaseFrames = 0;

    eligibleMask = OverworldFollowerSelectorUI_GetEligibleMask();
    if (eligibleMask == 0) {
        OverworldFollowerSelectorInput_Cancel(fieldSystem);
        return;
    }
    if ((eligibleMask & (1 << sFollowerSelectorHighlightedSlot)) == 0) {
        nextSlot = OverworldFollowerSelectorInput_FirstEligibleSlot(eligibleMask);
    } else if ((physicalNewKeys & (PAD_BUTTON_L | PAD_BUTTON_R))
            == PAD_BUTTON_L) {
        nextSlot = OverworldFollowerSelectorInput_CycleSlot(
            eligibleMask,
            sFollowerSelectorHighlightedSlot,
            -1);
    } else if ((physicalNewKeys & (PAD_BUTTON_L | PAD_BUTTON_R))
            == PAD_BUTTON_R) {
        nextSlot = OverworldFollowerSelectorInput_CycleSlot(
            eligibleMask,
            sFollowerSelectorHighlightedSlot,
            1);
    } else {
        nextSlot = sFollowerSelectorHighlightedSlot;
    }
    if (nextSlot != sFollowerSelectorHighlightedSlot) {
        sFollowerSelectorHighlightedSlot = nextSlot;
        OverworldFollowerSelectorUI_SetSelection(nextSlot);
    }
}

BOOL OverworldFollowerSelectorInput_Cancel(FieldSystem *fieldSystem)
{
    FieldSystem *ownedFieldSystem = sFollowerSelectorFieldSystem;
    BOOL teardownRequest = fieldSystem == NULL;
    BOOL staleCleanupDeferredPastUnload = FALSE;

    if (fieldSystem == NULL) {
        fieldSystem = ownedFieldSystem != NULL
            ? ownedFieldSystem
            : gFieldSysPtr;
    }
    if (OverworldFollowerSelector_IsStaleBallCleanupPending()) {
        if (teardownRequest) {
            OverworldFollowerSelector_ClearMemory(
                &sFollowerRecall,
                sizeof(sFollowerRecall));
            staleCleanupDeferredPastUnload = TRUE;
        } else {
            (void)OverworldFollowerRecall_CleanupStaleBall(fieldSystem);
        }
    }
    if (sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_IDLE
        || sFollowerSelectorTask != NULL
        || OverworldFollowerSelectorUI_IsOpen()) {
        OverworldFollowerSelector_SetReleaseGate();
        OverworldFollowerSelectorInput_Close(sFollowerSelectorTask);
    }
    return staleCleanupDeferredPastUnload
        || !OverworldFollowerSelector_IsStaleBallCleanupPending();
}

BOOL OverworldFollowerSelectorInput_IsActive(void)
{
    return sFollowerSelectorInputState != FOLLOWER_SELECTOR_INPUT_IDLE;
}
