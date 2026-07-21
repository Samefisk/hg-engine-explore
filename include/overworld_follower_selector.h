#ifndef OVERWORLD_FOLLOWER_SELECTOR_H
#define OVERWORLD_FOLLOWER_SELECTOR_H

#include "types.h"

typedef struct FieldSystem FieldSystem;

#define OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG 0x80
#define OVERWORLD_FOLLOWER_SELECTOR_DIRECT_LOADED_FLAG 0x40
/* Published by overlay 131 at a fixed ABI address for overlays 151 and 152. */
#define OVERWORLD_FOLLOWER_SELECTOR_STATE \
    (*(volatile u8 *)0x023C8148)

static inline BOOL OverworldFollowerSelector_IsReleaseGated(void)
{
    return (OVERWORLD_FOLLOWER_SELECTOR_STATE
        & OVERWORLD_FOLLOWER_SELECTOR_RELEASE_GATE_FLAG) != 0;
}

static inline void OverworldFollowerSelector_SetReleaseGate(void)
{
    OVERWORLD_FOLLOWER_SELECTOR_STATE |=
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

#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR 0x023C0400
#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR 0x023C3000
#define OVERWORLD_FOLLOWER_SELECTOR_MAGIC 0x3153464F /* "OFS1" */
#define OVERWORLD_FOLLOWER_SELECTOR_VERSION 1

typedef BOOL (*OverworldFollowerSelectorValidateFunc)(void);
typedef BOOL (*OverworldFollowerSelectorUIOpenFunc)(
    FieldSystem *fieldSystem,
    u8 highlightedSlot);
typedef void (*OverworldFollowerSelectorUISetSelectionFunc)(u8 highlightedSlot);
typedef void (*OverworldFollowerSelectorUIUpdateFunc)(void);
typedef void (*OverworldFollowerSelectorUICloseFunc)(void);
typedef BOOL (*OverworldFollowerSelectorUIIsOpenFunc)(void);
typedef void (*OverworldFollowerSelectorInputFilterFunc)(
    FieldSystem *fieldSystem,
    u16 *newKeys,
    u16 *heldKeys);
typedef void (*OverworldFollowerSelectorInputCancelFunc)(FieldSystem *fieldSystem);
typedef BOOL (*OverworldFollowerSelectorInputIsActiveFunc)(void);

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
} OverworldFollowerSelectorOverlayEntry;

typedef char OverworldFollowerSelectorOverlayEntrySizeMustRemain44Bytes[
    sizeof(OverworldFollowerSelectorOverlayEntry) == 44 ? 1 : -1];

#define OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY \
    ((const OverworldFollowerSelectorOverlayEntry *) \
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR)

BOOL OverworldFollowerSelectorUI_Open(
    FieldSystem *fieldSystem,
    u8 highlightedSlot);
void OverworldFollowerSelectorUI_SetSelection(u8 highlightedSlot);
void OverworldFollowerSelectorUI_Update(void);
void OverworldFollowerSelectorUI_Close(void);
BOOL OverworldFollowerSelectorUI_IsOpen(void);

void OverworldFollowerSelectorInput_Filter(
    FieldSystem *fieldSystem,
    u16 *newKeys,
    u16 *heldKeys);
void OverworldFollowerSelectorInput_Cancel(FieldSystem *fieldSystem);
BOOL OverworldFollowerSelectorInput_IsActive(void);

/* Implemented by transient overlay 152 and used only while it is loaded. */
u8 OverworldWildSpawns_GetSelectedFollowerPartySlot(FieldSystem *fieldSystem);
BOOL OverworldWildSpawns_IsFollowerPartySlotEligible(
    FieldSystem *fieldSystem,
    u8 partySlot);
u8 OverworldWildSpawns_GetEligibleFollowerPartyMask(FieldSystem *fieldSystem);
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

    return entry->inputCancel != NULL
        && (rawCancelAddress & 1u) != 0
        && cancelAddress >= OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY_ADDR
        && cancelAddress < OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_END_ADDR;
}

static inline void OverworldFollowerSelector_InputFilter(
    FieldSystem *fieldSystem,
    u16 *newKeys,
    u16 *heldKeys)
{
    const OverworldFollowerSelectorOverlayEntry *entry =
        OVERWORLD_FOLLOWER_SELECTOR_OVERLAY_ENTRY;

    if (entry->inputFilter != NULL) {
        entry->inputFilter(fieldSystem, newKeys, heldKeys);
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
