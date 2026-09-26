#include "../../include/overworld_condition_visibility.h"

#include "../../include/map_events_internal.h"
#include "../../include/overworld_vision.h"
#include "../../include/pokemon.h"

extern int OverworldConditionVisibility_PlayerX(FIELD_PLAYER_AVATAR *avatar);
extern int OverworldConditionVisibility_PlayerY(FIELD_PLAYER_AVATAR *avatar);
#define GetPlayerXCoord OverworldConditionVisibility_PlayerX
#define GetPlayerYCoord OverworldConditionVisibility_PlayerY

extern BOOL OverworldConditionVisibility_MetatileBlocked(
    FieldSystem *fieldSystem, int x, int y);
#define IsMetatileBlockedAt OverworldConditionVisibility_MetatileBlocked

__asm__(
    ".thumb\n"
    ".global OverworldConditionVisibility_MetatileBlocked\n.thumb_func\n.thumb_set OverworldConditionVisibility_MetatileBlocked, 0x020548C0\n"
    ".global OverworldConditionVisibility_PlayerX\n.thumb_func\n.thumb_set OverworldConditionVisibility_PlayerX, 0x0205C67C\n"
    ".global OverworldConditionVisibility_PlayerY\n.thumb_func\n.thumb_set OverworldConditionVisibility_PlayerY, 0x0205C688\n");

static u32 OverworldConditionVisibility_Abs(s32 value)
{
    return value < 0 ? (u32)-value : (u32)value;
}

BOOL __attribute__((section(".overworld_condition_visibility_trace"),
    noinline, optimize("Os"), used))
OverworldConditionVisibility_TraceBlocked(
    FieldSystem *fieldSystem,
    const OverworldBehaviorConditionWorldView *world,
    s16 targetX,
    s16 targetY)
{
    s32 dx = (s32)OverworldConditionVisibility_Abs(
        targetX - world->subjectX);
    s32 dy = -(s32)OverworldConditionVisibility_Abs(
        targetY - world->subjectY);
    s32 stepX = world->subjectX < targetX ? 1 : -1;
    s32 stepY = world->subjectY < targetY ? 1 : -1;
    s32 error = dx + dy;
    s32 x = world->subjectX;
    s32 y = world->subjectY;

    if (dx > OVERWORLD_VISION_MAX_RANGE
        || -dy > OVERWORLD_VISION_MAX_RANGE) {
        return FALSE;
    }
    while (x != targetX || y != targetY) {
        s32 twiceError = error * 2;

        if (twiceError >= dy) {
            error += dy;
            x += stepX;
        }
        if (twiceError <= dx) {
            error += dx;
            y += stepY;
        }
        if (x == targetX && y == targetY) {
            break;
        }
        if (IsMetatileBlockedAt(fieldSystem, x, y)) {
            return TRUE;
        }
    }
    return FALSE;
}

void __attribute__((section(".overworld_condition_visibility_populate"),
    noinline, optimize("Os"), used))
OverworldConditionVisibility_PopulateWorld(
    FieldSystem *fieldSystem,
    OverworldBehaviorConditionWorldView *world)
{
    u8 i;

    world->playerValid = fieldSystem->playerAvatar != NULL;
    world->playerFacingAndOcclusion = 0;
    world->playerVisionRange = OVERWORLD_VISION_DEFAULT_RANGE;
    world->playerVisionOptions = OVERWORLD_VISION_DEFAULT_OPTIONS;
    if (world->playerValid) {
        world->playerX = (s16)GetPlayerXCoord(fieldSystem->playerAvatar);
        world->playerY = (s16)GetPlayerYCoord(fieldSystem->playerAvatar);
        world->playerFacingAndOcclusion =
            fieldSystem->playerAvatar->mapObject != NULL
                ? fieldSystem->playerAvatar->mapObject->curFacing
                : OVERWORLD_VISION_FACING_SOUTH;
        if (OverworldConditionVisibility_TraceBlocked(
                fieldSystem,
                world,
                world->playerX,
                world->playerY)) {
            world->playerFacingAndOcclusion |=
                OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT
                | OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT;
        }
    }
    for (i = 0; i < world->actorCount; i++) {
        OverworldBehaviorConditionActorObservation *actor =
            &world->actors[i];

        actor->facingAndOcclusion &=
            OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_FACING_MASK;
        if (!actor->valid) {
            continue;
        }
        if (OverworldConditionVisibility_TraceBlocked(
                fieldSystem,
                world,
                actor->x,
                actor->y)) {
            actor->facingAndOcclusion |=
                OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_FROM_SUBJECT
                | OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_OCCLUDED_TO_SUBJECT;
        }
    }
}
