#ifndef OVERWORLD_FOLLOWER_SELECTOR_H
#define OVERWORLD_FOLLOWER_SELECTOR_H

#include "types.h"

typedef struct FieldSystem FieldSystem;
typedef struct OverworldWildSpawnState OverworldWildSpawnState;
struct OverworldWildSurfaceCatalog;
struct OverworldWildSurfaceHit;
struct LocalMapObject;
struct PartyPokemon;

#define OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG 0x80
#define OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG 0x40
#define OVERWORLD_FOLLOWER_SELECTOR_STALE_BALL_FLAG 0x20
#define OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG 0x10
#define OVERWORLD_FOLLOWER_SELECTOR_UNLOAD_PENDING_FLAG 0x08
#define OVERWORLD_FOLLOWER_SELECTOR_PARTY_DIRTY_FLAG 0x04
#define OVERWORLD_FOLLOWER_SELECTOR_Y_PRESS_PENDING_FLAG 0x02
#define OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG 0x01
/* Published by overlay 131 at a fixed ABI address for overlays 151 and 152. */
#define OVERWORLD_FOLLOWER_SELECTOR_STATE \
    (*(volatile u8 *)0x023C8148)

#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_CAPACITY 10
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_COMMAND_BITS 3
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_DESPAWN_COMMAND 7
#define OVERWORLD_FOLLOWER_SELECTION_REQUEST_PENDING 0x80
#define OVERWORLD_FOLLOWER_SELECTION_REQUEST_MOUNT 0x40
#define OVERWORLD_FOLLOWER_SELECTION_REQUEST_SLOT_MASK 0x07
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_ADDR 0x023C8130
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND_ADDR 0x023C80D1
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_POP_ADDR 0x023C8109

typedef struct OverworldFollowerTransitionQueueStorage {
    u32 commands;
    u8 count;
    u8 headIssued;
    u8 headRetries;
    u8 reserved; /* pending selector request/mount-after-spawn state */
} OverworldFollowerTransitionQueueStorage;

#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE \
    ((volatile OverworldFollowerTransitionQueueStorage *) \
        OVERWORLD_FOLLOWER_TRANSITION_QUEUE_ADDR)
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND \
    ((BOOL (*)(u8))OVERWORLD_FOLLOWER_TRANSITION_QUEUE_APPEND_ADDR)
#define OVERWORLD_FOLLOWER_TRANSITION_QUEUE_POP \
    ((void (*)(void))OVERWORLD_FOLLOWER_TRANSITION_QUEUE_POP_ADDR)

static inline BOOL OverworldFollowerSelector_IsReleaseGated(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetReleaseGate(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE =
        (OVERWORLD_FOLLOWER_SELECTOR_STATE
            & (u8)~(OVERWORLD_FOLLOWER_SELECTOR_Y_PRESS_PENDING_FLAG
                | OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG))
        |
        OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG;
}

static inline void OverworldFollowerSelector_ClearReleaseGate(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsDirectLoaded(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetDirectLoaded(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG;
}

static inline void OverworldFollowerSelector_ClearDirectLoaded(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsActiveFlagSet(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetActiveFlag(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG;
}

static inline void OverworldFollowerSelector_ClearActiveFlag(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_ACTIVE_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsUnloadPending(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_UNLOAD_PENDING_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetUnloadPending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_UNLOAD_PENDING_FLAG;
}

static inline void OverworldFollowerSelector_ClearUnloadPending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_UNLOAD_PENDING_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsStaleBallCleanupPending(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_STALE_BALL_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetStaleBallCleanupPending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_STALE_BALL_FLAG;
}

static inline void OverworldFollowerSelector_ClearStaleBallCleanupPending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_STALE_BALL_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsPartySnapshotDirty(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_PARTY_DIRTY_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetPartySnapshotDirty(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_PARTY_DIRTY_FLAG;
}

static inline void OverworldFollowerSelector_ClearPartySnapshotDirty(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_PARTY_DIRTY_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsYPressPending(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_Y_PRESS_PENDING_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetYPressPending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_Y_PRESS_PENDING_FLAG;
}

static inline void OverworldFollowerSelector_ClearYPressPending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_Y_PRESS_PENDING_FLAG;
}

static inline BOOL OverworldFollowerSelector_IsYReleasePending(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetYReleasePending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
        OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG;
}

static inline void OverworldFollowerSelector_ClearYReleasePending(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE &=
        (u8)~OVERWORLD_FOLLOWER_SELECTOR_Y_RELEASE_PENDING_FLAG;
}

#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR 0x023C0400
#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR 0x023C22A0
#define OVERWORLD_FOLLOWER_SELECTOR_MAGIC 0x3153464F /* "OFS1" */
#define OVERWORLD_FOLLOWER_SELECTOR_VERSION 5

typedef BOOL (*OverworldFollowerSelectorValidateFunc)(void);
typedef BOOL (*OverworldFollowerSelectorUIOpenFunc)(
    FieldSystem *fieldSystem,
    u8 highlightedSlot);
typedef void (*OverworldFollowerSelectorUISetSelectionFunc)(u8 highlightedSlot);
typedef BOOL (*OverworldFollowerSelectorUIUpdateFunc)(void);
typedef void (*OverworldFollowerSelectorUICloseFunc)(void);
typedef BOOL (*OverworldFollowerSelectorUIIsOpenFunc)(void);
typedef void (*OverworldFollowerSelectorInputFilterFunc)(
    FieldSystem *fieldSystem);
typedef BOOL (*OverworldFollowerSelectorInputCancelFunc)(FieldSystem *fieldSystem);
typedef BOOL (*OverworldFollowerSelectorInputIsActiveFunc)(void);
typedef struct PartyPokemon *(*OverworldFollowerSelectorGetSelectedPokemonFunc)(
    FieldSystem *fieldSystem,
    u8 *partySlot);
typedef s32 (*OverworldFollowerSelectorGetReleaseDistanceFunc)(
    FieldSystem *fieldSystem);
typedef BOOL (*OverworldFollowerSelectorIsReleaseTileAvailableFunc)(
    FieldSystem *fieldSystem,
    int x,
    int y);
typedef int (*OverworldFollowerSelectorBuildDirectedDirectionsFunc)(
    int dx,
    int dy,
    u8 *directions);
typedef struct OverworldFollowerSelectorOverlayEntry {
    u32 magic;
    u16 version;
    u16 size;
    OverworldFollowerSelectorValidateFunc validate;
    OverworldFollowerSelectorUIOpenFunc uiOpen;
    OverworldFollowerSelectorUISetSelectionFunc uiSetSelection;
    OverworldFollowerSelectorUIUpdateFunc uiUpdate;
    OverworldFollowerSelectorUICloseFunc uiClose;
    OverworldFollowerSelectorUIIsOpenFunc uiIsOpen;
    OverworldFollowerSelectorInputFilterFunc inputFilter;
    OverworldFollowerSelectorInputCancelFunc inputCancel;
    OverworldFollowerSelectorInputIsActiveFunc inputIsActive;
    OverworldFollowerSelectorGetSelectedPokemonFunc getSelectedPokemon;
    OverworldFollowerSelectorGetReleaseDistanceFunc getReleaseDistance;
    OverworldFollowerSelectorIsReleaseTileAvailableFunc isReleaseTileAvailable;
    OverworldFollowerSelectorBuildDirectedDirectionsFunc buildDirectedDirections;
} OverworldFollowerSelectorOverlayEntry;

typedef char OverworldFollowerSelectorOverlayEntrySizeMustRemain60Bytes[
    sizeof(OverworldFollowerSelectorOverlayEntry) == 60 ? 1 : -1];

#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY \
    ((const OverworldFollowerSelectorOverlayEntry *) \
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR)

BOOL OverworldFollowerSelectorUI_Open(
    FieldSystem *fieldSystem,
    u8 highlightedSlot);
void OverworldFollowerSelectorUI_BeginPartySnapshot(void);
BOOL OverworldFollowerSelectorUI_SnapshotNextPartySlot(
    FieldSystem *fieldSystem);
u8 OverworldFollowerSelectorUI_GetEligibleMask(void);
void OverworldFollowerSelectorUI_SetSelection(u8 highlightedSlot);
BOOL OverworldFollowerSelectorUI_Update(void);
void OverworldFollowerSelectorUI_Close(void);
BOOL OverworldFollowerSelectorUI_IsOpen(void);

void OverworldFollowerSelectorInput_Filter(
    FieldSystem *fieldSystem);
BOOL OverworldFollowerSelectorInput_Cancel(FieldSystem *fieldSystem);
BOOL OverworldFollowerSelectorInput_IsActive(void);
struct PartyPokemon *OverworldFollowerSelector_GetSelectedPokemon(
    FieldSystem *fieldSystem,
    u8 *partySlot);
s32 OverworldFollowerSelector_GetReleaseDistance(FieldSystem *fieldSystem);
BOOL OverworldFollowerSelector_IsReleaseTileAvailable(
    FieldSystem *fieldSystem,
    int x,
    int y);
int OverworldFollowerSelector_BuildDirectedDirections(
    int dx,
    int dy,
    u8 *directions);

/* Implemented by transient overlay 152 and used only while it is loaded. */
u8 OverworldWildSpawns_GetSelectedFollowerPartySlot(FieldSystem *fieldSystem);
BOOL OverworldWildSpawns_IsFollowerPartySlotEligible(
    FieldSystem *fieldSystem,
    u8 partySlot);
BOOL OverworldWildSpawns_SelectFollowerPartySlot(
    FieldSystem *fieldSystem,
    u8 partySlot);

static inline BOOL OverworldFollowerSelector_Validate(void)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;
    u32 rawValidateAddress = (u32)entry->validate;
    u32 validateAddress = rawValidateAddress & ~1u;

    return entry->magic == OVERWORLD_FOLLOWER_SELECTOR_MAGIC
        && entry->version == OVERWORLD_FOLLOWER_SELECTOR_VERSION
        && entry->size == sizeof(*entry)
        && entry->validate != NULL
        && (rawValidateAddress & 1u) != 0
        && validateAddress >= OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR
        && validateAddress < OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR
        && entry->validate();
}

static inline BOOL OverworldFollowerSelector_CanCallInputCancel(void)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;
    u32 rawCancelAddress = (u32)entry->inputCancel;
    u32 cancelAddress = rawCancelAddress & ~1u;

    return (rawCancelAddress & 1u) != 0
        && cancelAddress >= OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR
        && cancelAddress < OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR;
}

static inline void OverworldFollowerSelector_InputFilter(
    FieldSystem *fieldSystem)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;

    if (entry->inputFilter != NULL) {
        entry->inputFilter(fieldSystem);
    }
}

static inline void OverworldFollowerSelector_Cancel(FieldSystem *fieldSystem)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;

    if (entry->inputCancel != NULL) {
        entry->inputCancel(fieldSystem);
    }
}

static inline BOOL OverworldFollowerSelector_IsActive(void)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;

    return entry->inputIsActive != NULL && entry->inputIsActive();
}

#endif // OVERWORLD_FOLLOWER_SELECTOR_H
