#ifndef OVERWORLD_TARGET_BINDINGS_H
#define OVERWORLD_TARGET_BINDINGS_H

#include "overworld_behavior_conditions.h"

/* Value storage only. This module does not claim actors, choose stages,
 * transfer control, move cargo, or select a replacement target. */
typedef enum OverworldTargetBindingName {
    OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST = 0,
    OVERWORLD_TARGET_BINDING_CARGO = 1,
    OVERWORLD_TARGET_BINDING_COUNT = 2,
} OverworldTargetBindingName;

/* usesBinding normally names a prerequisite (name +1). This explicit
 * selector also restricts actor candidates to Object of Interest itself. */
#define OVERWORLD_TARGET_SELECT_OBJECT_OF_INTEREST 3

typedef enum OverworldTargetBindingLifetime {
    OVERWORLD_TARGET_BINDING_UNTIL_CLEAR = 0,
    OVERWORLD_TARGET_BINDING_FRAMES = 1,
} OverworldTargetBindingLifetime;

typedef enum OverworldTargetBindingStatus {
    OVERWORLD_TARGET_BINDING_OK = 0,
    OVERWORLD_TARGET_BINDING_EMPTY = 1,
    OVERWORLD_TARGET_BINDING_NOT_ADMITTED = 2,
    OVERWORLD_TARGET_BINDING_ALREADY_BOUND = 3,
    OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT = 4,
    OVERWORLD_TARGET_BINDING_STALE_SUBJECT = 5,
    OVERWORLD_TARGET_BINDING_STALE_TARGET = 6,
    OVERWORLD_TARGET_BINDING_EXPIRED = 7,
    OVERWORLD_TARGET_BINDING_CONFLICT = 8,
} OverworldTargetBindingStatus;

typedef enum OverworldTargetBindingClearReason {
    OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT = 16,
    OVERWORLD_TARGET_BINDING_CLEAR_COMPLETE = 17,
    OVERWORLD_TARGET_BINDING_CLEAR_ABORT = 18,
    OVERWORLD_TARGET_BINDING_CLEAR_CONTEXT = 19,
    OVERWORLD_TARGET_BINDING_CLEAR_ROLE = 20,
    OVERWORLD_TARGET_BINDING_CLEAR_DESPAWN = 21,
    OVERWORLD_TARGET_BINDING_CLEAR_BATTLE = 22,
} OverworldTargetBindingClearReason;

#define OVERWORLD_TARGET_BINDING_BOUND (1u << 0)

typedef struct OverworldTargetBinding {
    OverworldBehaviorConditionTargetReference target;
    u16 sourceConditionId;
    u32 expiresAt;
    u8 sourceApplication;
    u8 lifetime;
    u8 flags;
    u8 reason;
} OverworldTargetBinding;

typedef struct OverworldTargetBindingsState {
    OverworldActorHandle subject;
    OverworldTargetBinding bindings[OVERWORLD_TARGET_BINDING_COUNT];
} OverworldTargetBindingsState;

typedef struct OverworldTargetBindingPosition {
    OverworldBehaviorConditionTargetReference target;
    s16 x;
    s16 y;
} OverworldTargetBindingPosition;

typedef char OverworldTargetBindingSizeMustRemain24Bytes[
    sizeof(OverworldTargetBinding) == 24 ? 1 : -1];
typedef char OverworldTargetBindingsStateSizeMustRemain60Bytes[
    sizeof(OverworldTargetBindingsState) == 60 ? 1 : -1];

/* Initialize once for an attached full subject identity. Lifecycle callers
 * clear the old identity before initializing a replacement. */
OverworldTargetBindingStatus OverworldTargetBindings_Init(
    OverworldTargetBindingsState *state,
    const OverworldActorHandle *subject);

/* Pass the exact admitted entry result, before a later condition overwrites
 * the application's final target. An existing binding is never refreshed or
 * retargeted here, even when its identity is now invalid or expired. */
OverworldTargetBindingStatus OverworldTargetBindings_CaptureEntry(
    OverworldTargetBindingsState *state,
    const OverworldBehaviorConditionWorldView *world,
    const OverworldActorHandle *admittedSubject,
    const OverworldBehaviorConditionEntryResult *entry,
    u8 name,
    u8 lifetime,
    u16 durationFrames);

/* Read the bound identity's current position. Failure writes no fallback
 * position and keeps the stored identity for the authored failure response. */
OverworldTargetBindingStatus OverworldTargetBindings_Resolve(
    OverworldTargetBindingsState *state,
    const OverworldBehaviorConditionWorldView *world,
    u8 name,
    OverworldTargetBindingPosition *position);

/* Clearing a value does not release a cargo claim or held control. The role
 * owner must perform that existing cleanup at a legal action boundary. */
OverworldTargetBindingStatus OverworldTargetBindings_Clear(
    OverworldTargetBindingsState *state,
    const OverworldActorHandle *subject,
    u8 name,
    u8 reason);
OverworldTargetBindingStatus OverworldTargetBindings_ClearAll(
    OverworldTargetBindingsState *state,
    const OverworldActorHandle *subject,
    u8 reason);

#endif // OVERWORLD_TARGET_BINDINGS_H
