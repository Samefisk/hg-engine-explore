#define OVERWORLD_FIELD_CAPSULE_IMPLEMENTATION 1
#include "../../include/overworld_actor_appearance_internal.h"
#include "../../include/overworld_appearance_policy.h"
#include "../../include/overworld_combat.h"
#include "../../include/overworld_follower_selector.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_actor_system_internal.h"
#include "../../include/overworld_wild_runtime_state_internal.h"
#include "../../include/overworld_water_sink.h"
#include "../../include/constants/file.h"

/* The established core bridges enter stock ARM helpers and return in Thumb.
 * Function metadata prevents a linker-created ARM veneer to Thumb bytes. */
__asm__(
    ".thumb\n"
    ".global memset\n.thumb_func\n.thumb_set memset, 0x023DEEA2\n"
    ".global __aeabi_uidiv\n.thumb_func\n.thumb_set __aeabi_uidiv, 0x023DEE4C\n"
    ".global __aeabi_uidivmod\n.thumb_func\n.thumb_set __aeabi_uidivmod, 0x023DEE4C\n");

/* Overlay 1 is the physical code host. The field-update owner supplies the
 * current resident snapshot and authenticated catalog/condition view. */
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
__attribute__((section(".overworld_field_appearance_cleanup"), noinline))
#endif
BOOL AppearanceNative_RamSpan(const void *pointer, u32 bytes)
{
    u32 address = (u32)(uintptr_t)pointer;
    return address >= 0x02000000 && address <= 0x02400000
        && bytes <= 0x02400000 - address;
}

static BOOL AppearanceNative_SameHandle(
    const OverworldActorHandle *left, const OverworldActorHandle *right)
{
    return left->slot == right->slot && left->generation == right->generation
        && left->fieldEpoch == right->fieldEpoch
        && left->mapGeneration == right->mapGeneration
        && left->encounterGeneration == right->encounterGeneration;
}

OverworldActorAppearanceResult OverworldActorAppearance_RefreshNative(
    const OverworldActorAppearanceNativeInput *input)
{
    const OverworldWildSpawnState *state;
    const OverworldActorStateSnapshot *actor;
    const OverworldWildSpawn *spawn;
    MapObjectMan *manager;
    FieldSystem *field;
    OverworldActorAppearanceInput tint;
    u16 hp, maxHp;
    u8 slot;

    if (input == NULL
        || !AppearanceNative_RamSpan(input->actor, sizeof(*actor))
        || !AppearanceNative_RamSpan(input->spawns, sizeof(*state))) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    actor = input->actor;
    state = input->spawns;
    field = state->movementFieldSystem;
    slot = actor->handle.slot;
    if (actor->handle.slot >= OW_WILD_MAX_SPAWNS
        || !actor->active || !actor->presentationAttached
        || actor->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || actor->size != sizeof(*actor) || actor->handle.generation == 0
        || actor->handle.fieldEpoch == 0
        || actor->role < OVERWORLD_ACTOR_ROLE_WILD
        || actor->role > OVERWORLD_ACTOR_ROLE_MOUNTED
        || !AppearanceNative_RamSpan(field, sizeof(*field)) || field != gFieldSysPtr
        || !AppearanceNative_RamSpan(field->location, sizeof(*field->location))
        || field->location->mapId != state->mapId
        || state->mapGeneration != actor->handle.mapGeneration
        || state->mapGeneration == 0 || state->mapObjectMan != field->mapObjectMan) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    manager = state->mapObjectMan;
    if (!AppearanceNative_RamSpan(manager, sizeof(*manager))
        || manager->fsys != field || state->mapObjects != manager->objects) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    spawn = &state->spawns[slot];
    if (!spawn->active || spawn->mapId != state->mapId
        || spawn->encounterGeneration == 0
        || spawn->encounterGeneration != actor->handle.encounterGeneration
        || spawn->personality != actor->subjectIdentity
        || spawn->species != actor->species || spawn->form != actor->form
        || spawn->level != actor->level || spawn->objectId != OW_WILD_OBJECT_ID_START + slot) {
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    if (!OverworldCombat_IsReady()
        || !OVERWORLD_COMBAT_ENTRY->readHp(state, slot, &hp, &maxHp)) {
        OverworldActorAppearance_Forget(manager, slot);
        return OVERWORLD_ACTOR_APPEARANCE_INVALID;
    }
    tint.actor = actor;
    tint.pokemon = spawn->object;
    tint.damageActive = hp < maxHp;
    tint.redStrength = OverworldAppearancePolicy_DamageStrength(hp, maxHp, input->frame);
    tint.restTint = 0;
    if (!tint.damageActive && input->restEnabledApplications != 0
        && AppearanceNative_RamSpan(input->conditions, sizeof(*input->conditions))
        && AppearanceNative_SameHandle(&input->conditions->subject, &actor->handle)
        && AppearanceNative_RamSpan(input->behavior, sizeof(*input->behavior))) {
        tint.restTint = OverworldAppearancePolicy_ShouldRestTint(input->conditions,
            input->behavior, input->restEnabledApplications, input->frame, actor->role);
    }
    return OverworldActorAppearance_Update(manager, &tint);
}

static BOOL AppearanceNative_SelectorFunction(const void *function)
{
    u32 raw = (u32)(uintptr_t)function;
    return (raw & 1) != 0
        && (raw & ~1u) >= OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR
        && (raw & ~1u) < OVERWORLD_FOLLOWER_SELECTOR_CALLBACK_END_ADDR;
}

/* Query code and its work buffer use heap4. The loaded Wild owner must drain
 * them while both its Selector service and the parent Field are still alive. */
static BOOL __attribute__((noinline))
#if !defined(OVERWORLD_BEHAVIOR_HOST) && !defined(OVERWORLD_ACTOR_SYSTEM_HOST)
__attribute__((section(".overworld_field_appearance_cleanup")))
#endif
AppearanceNative_PrepareWildUnload(void)
{
    return !IsOverlayLoaded(OVERLAY_OVERWORLD_WILD_SPAWNS_EXTENSION)
        || OVERWORLD_WILD_SPAWNS_OVERLAY_ENTRY->cleanupResidentData();
}

BOOL OverworldActorAppearance_BeforeParentUnload(
    FieldSystem *field, MapObjectMan *manager)
{
    if (field != NULL && (!AppearanceNative_RamSpan(field, sizeof(*field))
        || field != gFieldSysPtr || manager != field->mapObjectMan)) {
        return FALSE;
    }
    if (field == NULL && manager != NULL) {
        return FALSE;
    }
    if (manager != NULL && (!AppearanceNative_RamSpan(manager, sizeof(*manager))
        || manager->fsys != field)) {
        return FALSE;
    }
    if (OverworldFollowerSelector_IsDirectLoaded()) {
        const OverworldFollowerSelectorOverlayEntry *entry =
            OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;
        /* Use ordinary cancellation while the current pool is alive. Its
         * false result retains stale-ball work; force/NULL teardown can
         * discard that saved state without restoring a live callback. */
        if (field == NULL || !OverworldFollowerSelector_Validate()
            || !AppearanceNative_SelectorFunction(entry->inputCancel)
            || !AppearanceNative_SelectorFunction(entry->inputIsActive)
            || !entry->inputCancel(field) || entry->inputIsActive()) {
            return FALSE;
        }
    }
    return Appearance_ClearForUnload(manager)
        && AppearanceNative_PrepareWildUnload();
}

/* The stock parent calls its exit template before any graphics are freed.
 * A pending recall keeps that parent and its objects alive for another tick. */
BOOL __attribute__((section(".overworld_field_appearance_exit")))
OverworldActorAppearance_FieldExit(void *manager, int *exitState)
{
    typedef BOOL (*StockFieldExit)(void *, int *);
    FieldSystem *field = gFieldSysPtr;

    if (*exitState == 0 && (field == NULL
        || !OverworldActorAppearance_BeforeParentUnload(field, field->mapObjectMan))) {
        return FALSE;
    }
    return ((StockFieldExit)0x021E5C25)(manager, exitState);
}

void __attribute__((section(".overworld_field_appearance_refresh")))
OverworldActorAppearance_RefreshAll(
    const OverworldWildSpawnState *spawns,
    const OverworldWildBehaviorDataBlob *behavior)
{
    const OverworldActorSystemState *actors =
        (const OverworldActorSystemState *)OVERWORLD_ACTOR_SYSTEM_STATE_ADDR;
    OverworldWildOverlayRuntimeState *runtime;
    OverworldActorAppearanceNativeInput input;
    u16 slot;

    if (!AppearanceNative_RamSpan(spawns, sizeof(*spawns))
        || !AppearanceNative_RamSpan(spawns->movementFieldSystem, sizeof(FieldSystem))
        || spawns->movementFieldSystem != gFieldSysPtr
        || spawns->mapObjectMan != gFieldSysPtr->mapObjectMan
        || !AppearanceNative_RamSpan(spawns->movementRuntimeState, sizeof(*runtime))
        || !OverworldActorSystem_IsReady()
        || actors->magic != OVERWORLD_ACTOR_SYSTEM_STATE_MAGIC
        || actors->version != OVERWORLD_ACTOR_SYSTEM_ABI_VERSION
        || actors->size != sizeof(*actors)
        || actors->fieldEpoch == 0 || actors->mapGeneration != spawns->mapGeneration) {
        return;
    }
    runtime = spawns->movementRuntimeState;
    input.spawns = spawns;
    input.behavior = behavior;
    input.frame = actors->frame;
    input.restEnabledApplications = AppearanceNative_RamSpan(behavior, sizeof(*behavior))
        && behavior->header.magic == OVERWORLD_WILD_BEHAVIOR_DATA_MAGIC
        && behavior->header.version == OVERWORLD_WILD_BEHAVIOR_DATA_VERSION
        && behavior->header.headerSize == sizeof(behavior->header)
        && behavior->header.blobSize == sizeof(*behavior)
        ? 0xFFFFFFFFu : 0;
    for (slot = 0; slot < OW_WILD_MAX_SPAWNS; ++slot) {
        input.actor = &actors->slots[slot].snapshot;
        input.conditions = AppearanceNative_RamSpan(runtime->conditions,
            sizeof(*runtime->conditions)) ? &runtime->conditions->actors[slot] : NULL;
        if (!input.actor->active || input.actor->handle.fieldEpoch != actors->fieldEpoch
            || OverworldActorAppearance_RefreshNative(&input)
                == OVERWORLD_ACTOR_APPEARANCE_INVALID) {
            OverworldActorAppearance_Forget(spawns->mapObjectMan, slot);
        }
    }
}

const OverworldActorAppearanceEntry gOverworldActorAppearanceEntry
    __attribute__((section(".overworld_actor_appearance_entry"), used)) = {
    OVERWORLD_ACTOR_APPEARANCE_MAGIC,
    OVERWORLD_ACTOR_APPEARANCE_VERSION,
    sizeof(OverworldActorAppearanceEntry),
    OverworldActorAppearance_RefreshNative,
    OverworldActorAppearance_Forget,
    OverworldActorAppearance_BeforeParentUnload,
    OverworldActorAppearance_Inspect,
    /* Overlay 2's water sink pass calls OverworldActorAppearance_RefreshAll
     * first, then settles new and idle Wild bodies on water. */
    (void (*)(const struct OverworldWildSpawnState *,
        const struct OverworldWildBehaviorDataBlob *))
        (OVERWORLD_WATER_SINK_FRAME_ADDR | 1),
};

typedef char AppearanceEntryMustRemain28Bytes[
    sizeof(OverworldActorAppearanceEntry) == 28 ? 1 : -1];
