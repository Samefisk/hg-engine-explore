#ifndef OVERWORLD_CONDITION_SUBJECT_NATIVE_H
#define OVERWORLD_CONDITION_SUBJECT_NATIVE_H

#include "overworld_behavior_condition_adapter.h"

typedef struct LocalMapObject LocalMapObject;

/* Private resident Field leaf, separate from the version-12 Actor adapter.
 * Its 352-byte slot ends before the existing helper at 0x02208360. */
#define OVERWORLD_CONDITION_SUBJECT_POPULATE_ADDR 0x02208200
#define OVERWORLD_CONDITION_SUBJECT_POPULATE_LIMIT 0x022082C0
#define OVERWORLD_CONDITION_SUBJECT_CLEAR_ADDR 0x022082C0
#define OVERWORLD_CONDITION_SUBJECT_EQUAL_ADDR 0x02208320
#define OVERWORLD_CONDITION_SUBJECT_LIMIT 0x02208360

void OverworldConditionSubject_Populate(
    OverworldWildBehaviorConditionRuntime *runtime,
    FieldSystem *fieldSystem,
    const OverworldBehaviorConditionPreparedActor *prepared,
    const LocalMapObject *object,
    u8 slot,
    u8 subjectMovementSpeed,
    OverworldBehaviorConditionTerrainFunc terrainAt);

void OverworldConditionSubject_ClearActor(
    OverworldWildBehaviorConditionRuntime *runtime, u8 slot);
BOOL OverworldConditionSubject_HandleEquals(
    const OverworldActorHandle *left, const OverworldActorHandle *right);

#endif /* OVERWORLD_CONDITION_SUBJECT_NATIVE_H */
