#ifndef OVERWORLD_CONDITION_VISIBILITY_H
#define OVERWORLD_CONDITION_VISIBILITY_H

#include "types.h"
#include "overworld_behavior_conditions.h"

typedef struct FieldSystem FieldSystem;

#define OVERWORLD_CONDITION_VISIBILITY_TRACE_ADDR 0x023C7EA8
#define OVERWORLD_CONDITION_VISIBILITY_POPULATE_ADDR 0x023C7DF8

typedef void (*OverworldConditionVisibilityPopulateFunc)(
    FieldSystem *fieldSystem,
    OverworldBehaviorConditionWorldView *world);

/* This callback crosses from overlay 149 into Thumb code in overlay 150.
 * An absolute .thumb_set symbol is safe for direct BL calls, but GCC does not
 * add bit 0 when its address is stored as a callback. Keep the interworking
 * bit explicit at the function-pointer boundary. */
#define OVERWORLD_CONDITION_VISIBILITY_POPULATE_ENTRY \
    ((OverworldConditionVisibilityPopulateFunc)( \
        OVERWORLD_CONDITION_VISIBILITY_POPULATE_ADDR | 1u))

void OverworldConditionVisibility_PopulateWorld(
    FieldSystem *fieldSystem,
    OverworldBehaviorConditionWorldView *world);

BOOL OverworldConditionVisibility_TraceBlocked(
    FieldSystem *fieldSystem,
    const OverworldBehaviorConditionWorldView *world,
    s16 targetX,
    s16 targetY);

#endif // OVERWORLD_CONDITION_VISIBILITY_H
