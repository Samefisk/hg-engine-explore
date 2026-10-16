#ifndef OVERWORLD_QUERY_CODE_ADDON_FIELD_H
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_H
#include "overworld_query_code_addon_service.h"
typedef struct FieldSystem FieldSystem;
struct OverworldActorTransitionCall;
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_CURRENT_ADDR 0x023C2A80
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_ADDR 0x023C2B00
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_UNLOAD_ADDR 0x023C2B70

/* The loaded Condition gate authenticates both Selector and parent Field.
 * Ops are supplied by that Field; drain clears the one query and old bindings.
 * Same-epoch map rebinds and exact next nonzero epoch/map pairs reuse the
 * image only after drain; the Field identity must remain unchanged. */
/* Private helper: its caller must pass the loaded Condition gate first.
 * A supplied transition must be current before any drain or publication. */
const OverworldQueryCodeAddonEntry *OverworldQueryCodeAddonField_AcquireCurrent(
    FieldSystem *, const struct OverworldActorTransitionCall *,
    const OverworldQueryCodeAddonOps *, void *queryOwner);
const OverworldQueryCodeAddonEntry *OverworldQueryCodeAddonField_Acquire(
    FieldSystem *, u16 fieldEpoch, u16 mapGeneration,
    const OverworldQueryCodeAddonOps *, void *queryOwner);
OverworldQueryCodeAddonStatus OverworldQueryCodeAddonField_Unload(
    const OverworldQueryCodeAddonOps *, void *queryOwner);
#if !defined(OVERWORLD_ACTOR_SYSTEM_HOST) && !defined(OVERWORLD_BEHAVIOR_HOST)
/* The caller checks the existing loaded Condition gate before entering this
 * Selector-owned code. Its body validates that gate/table again. */
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_CURRENT \
    ((const OverworldQueryCodeAddonEntry *(*)(FieldSystem *,const struct OverworldActorTransitionCall *, \
        const OverworldQueryCodeAddonOps *,void *)) \
        (OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_CURRENT_ADDR|1u))
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE \
    ((const OverworldQueryCodeAddonEntry *(*)(FieldSystem *,u16,u16, \
        const OverworldQueryCodeAddonOps *,void *)) \
        (OVERWORLD_QUERY_CODE_ADDON_FIELD_ACQUIRE_ADDR|1u))
#define OVERWORLD_QUERY_CODE_ADDON_FIELD_UNLOAD \
    ((OverworldQueryCodeAddonStatus (*)(const OverworldQueryCodeAddonOps *,void *)) \
        (OVERWORLD_QUERY_CODE_ADDON_FIELD_UNLOAD_ADDR|1u))
#endif
#endif
