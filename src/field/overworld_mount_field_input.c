#include "../../include/overworld_mount_internal.h"
#include "../../include/overworld_actor_system_internal.h"

/* Called only by the resident mount field-input entry while field is loaded. */
int __attribute__((section(".overworld_mount_field_input_host"), noinline, used))
OverworldMount_ProcessFieldInput(
    OverworldMountFieldInput *fieldInput,
    FieldSystem *fieldSystem,
    OverworldMountRuntimeState *state,
    BOOL currentMount)
{
    typedef int (*FieldInputProcessor)(OverworldMountFieldInput *, FieldSystem *);
    OverworldActorQuery query;
    OverworldActorSnapshot snapshot;

    /* WORLD_GATE waits for this Walk's terminal commit. Deliver its real
     * stock END before querying that gate, not through the gated step path.
     * Keep the ordinary field step until all terminal acks have completed. */
    if (fieldInput != NULL && currentMount
        && (fieldInput->flags & (OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT
                | OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT))
            == (OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT
                | OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT)
        && state->snapshot.phase == OVERWORLD_MOUNT_PHASE_RIDING
        && state->reservedPolicyState[OVERWORLD_MOUNT_BOUNDARY_MOTION_INDEX] == OVERWORLD_MOUNT_MOTION_WALK
        && (state->reservedPolicyState[OVERWORLD_MOUNT_BOUNDARY_FLAGS_INDEX]
            & (OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE
                | OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING))
            == (OVERWORLD_MOUNT_BOUNDARY_FINAL_WRITES_DONE
                | OVERWORLD_MOUNT_BOUNDARY_FINALIZE_PENDING)
        && state->walkEndState == OVERWORLD_MOUNT_WALK_END_NONE) {
        state->pendingFieldStep = TRUE;
        state->walkEndState = OVERWORLD_MOUNT_WALK_END_PENDING;
        OVERWORLD_MOUNT_OVERLAY_ENTRY->onPlayerStep();
    }

    query.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    query.size = sizeof(query);
    query.kind = OVERWORLD_ACTOR_INSPECT_WORLD_GATE;
    query.index = OVERWORLD_ACTOR_WORLD_GATE_WARP;
    if (fieldInput != NULL
        && (OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(&query, &snapshot)
                != OVERWORLD_ACTOR_RESULT_OK
            || (currentMount
                && state->snapshot.profile.chillAction
                    != OW_WILD_BEHAVIOR_LOCOMOTION_WALK))) {
        /* The stationary held command used by custom motion repeatedly looks
         * like a completed player step. Vanilla processes coordinate events
         * and warps before its forced-movement guard, so those synthetic step
         * boundaries must not escape while the mount controller owns the player.
         * A custom mount profile also owns direction input before Actor Motion
         * starts, so block the held-direction door check for its full cycle.
         * Keep ordinary A/menu input intact, but disable every transition
         * signal. Mounted Walk still reaches normal doors when its gate opens. */
        fieldInput->flags &= ~(OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT
            | OVERWORLD_MOUNT_FIELD_INPUT_SIGN
            | OVERWORLD_MOUNT_FIELD_INPUT_MAP_TRANSITION
            | OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT);
    } else if (fieldInput != NULL && currentMount
        && state->pendingFieldStep) {
        fieldInput->flags |= OVERWORLD_MOUNT_FIELD_INPUT_END_MOVEMENT
            | OVERWORLD_MOUNT_FIELD_INPUT_MOVEMENT;
        state->pendingFieldStep = FALSE;
    }
    return ((FieldInputProcessor)0x021E6AF5)(fieldInput, fieldSystem);
}
