#include "../../include/overworld_condition_subject_native.h"
#include "../../include/map_events_internal.h"

void __attribute__((noinline, section(".overworld_condition_subject")))
OverworldConditionSubject_Populate(
    OverworldWildBehaviorConditionRuntime *runtime,
    FieldSystem *fieldSystem,
    const OverworldBehaviorConditionPreparedActor *prepared,
    const LocalMapObject *object,
    u8 slot,
    u8 subjectMovementSpeed,
    OverworldBehaviorConditionTerrainFunc terrainAt)
{
    OverworldBehaviorConditionWorldView *world = &runtime->frame.world;

    world->subjectTerrainMask = terrainAt(
        fieldSystem, object->xCurr, object->yCurr);
    world->subject = prepared->subject;
    world->subjectX = (s16)object->xCurr;
    world->subjectY = (s16)object->yCurr;
    world->subjectFacing = object->curFacing;
    world->subjectMovementSpeed = subjectMovementSpeed;
    world->subjectVisionRange = runtime->currentVisions[slot].range;
    world->subjectVisionOptions = runtime->currentVisions[slot].options;
    world->bindings = &runtime->bindings[slot];
    world->subjectRoleMask = 0;
    world->reservedBinding = 0;
    const OverworldBehaviorConditionActorObservation *actor = world->actors;
    const OverworldBehaviorConditionCandidate *candidate = runtime->frame.candidates;
    for (u32 remaining = world->actorCount; remaining != 0;
            remaining--, actor++, candidate++) {
        if (actor->actor.slot == slot) {
            world->subjectRoleMask = candidate->roleMask;
            break;
        }
    }
}

/* These are the same checked Thumb imports used by the resident adapter. */
extern void OverworldBehaviorConditionAdapter_ClearResolution(
    OverworldWildBehaviorConditionRuntime *, u8);
__asm__(
    ".global OverworldBehaviorConditionAdapter_ClearResolution\n"
    ".thumb_func\n"
    ".thumb_set OverworldBehaviorConditionAdapter_ClearResolution, 0x01FFBD00\n"
    ".global memset\n"
    ".thumb_func\n"
    ".thumb_set memset, 0x023DEEA2\n");

void __attribute__((noinline, section(".overworld_condition_subject_clear")))
OverworldConditionSubject_ClearActor(
    OverworldWildBehaviorConditionRuntime *runtime,
    u8 slot)
{
    OverworldBehaviorConditionPreparedActor *prepared =
        &runtime->actors[slot];

    if (prepared->states != NULL) {
        sys_FreeMemoryEz(prepared->states);
    }
    memset(prepared, 0, sizeof(*prepared));
    memset(&runtime->bindings[slot], 0, sizeof(runtime->bindings[slot]));
    runtime->currentVisions[slot].range = 0;
    runtime->currentVisions[slot].options = 0;
    OverworldBehaviorConditionAdapter_ClearResolution(runtime, slot);
}

typedef u16 OverworldBehaviorConditionHandleHalfword
    __attribute__((may_alias));

BOOL __attribute__((noinline, section(".overworld_condition_subject_equal")))
OverworldConditionSubject_HandleEquals(
    const OverworldActorHandle *left,
    const OverworldActorHandle *right)
{
    const OverworldBehaviorConditionHandleHalfword *leftValues =
        (const OverworldBehaviorConditionHandleHalfword *)left;
    const OverworldBehaviorConditionHandleHalfword *rightValues =
        (const OverworldBehaviorConditionHandleHalfword *)right;
    u8 index;

    /* World observations are only halfword aligned. ARM9 unaligned word
     * loads rotate data, so compare the native halfword fields. */
    for (index = 0; index < 5; index++) {
        if (leftValues[index] != rightValues[index]) {
            return FALSE;
        }
    }
    return TRUE;
}
