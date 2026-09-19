#!/usr/bin/env python3
"""Fail closed when motion requests or engine receipts have stale identity."""

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"motion identity check failed: {message}")


def function(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start + len(name))
    return source[start:end]


def request_rejects_stale_field(actor: str) -> bool:
    body = function(
        actor,
        "ActorSystem_RequestMotion(",
        "ActorSystem_TryAcknowledgeMotionCommit(",
    )
    normal_epoch = "expectedFieldEpoch = call->intent->fieldEpoch;"
    teleport_epoch = "expectedFieldEpoch = call->fieldEpoch;"
    guard = (
        "if (expectedFieldEpoch "
        "!= gOverworldActorSystemState.fieldEpoch)"
    )
    if normal_epoch not in body or teleport_epoch not in body or guard not in body:
        return False
    guard_at = body.index(guard)
    return (
        guard_at < body.index("actor->lastIntent =")
        and guard_at < body.index("OverworldMotion_SelectPlan(")
        and guard_at < body.index("OverworldActorTeleportPlanner_Plan(call)")
        and "call->decision = OVERWORLD_MOTION_DECISION_STALE_FIELD;"
            in body[guard_at:]
    )


def request_rejects_active_transition(actor: str) -> bool:
    body = function(
        actor,
        "ActorSystem_RequestMotion(",
        "ActorSystem_TryAcknowledgeMotionCommit(",
    )
    guard = "if (ActorSystem_TransitionIsActive())"
    if guard not in body:
        return False
    guard_at = body.index(guard)
    return (
        guard_at < body.index("actor->lastIntent =")
        and guard_at < body.index("OverworldMotion_SelectPlan(")
        and guard_at < body.index("OverworldActorTeleportPlanner_Plan(call)")
        and "call->decision = OVERWORLD_MOTION_DECISION_RETRY_WORLD_BUSY;"
            in body[guard_at:]
    )


def boundary_rejects_wrong_motion(actor: str) -> bool:
    body = function(
        actor,
        "ActorSystem_EngineBoundary(",
        "ActorSystem_SyncLegacyActor(",
    )
    token_guard = (
        "call->motionIdentity == 0\n"
        "        || call->motionIdentity != actor->reservationId"
    )
    if token_guard not in body:
        return False
    guard_at = body.index(token_guard)
    return (
        guard_at < body.index("OVERWORLD_ACTOR_BOUNDARY_CANCEL")
        and "call->decision = OVERWORLD_MOTION_DECISION_CONTEXT_LOST;"
            in body[guard_at:]
        and "OverworldMotion_RebindField(" not in body
    )


def actor_assigns_fresh_identity(actor: str) -> bool:
    body = function(
        actor,
        "ActorSystem_RequestMotion(",
        "ActorSystem_TryAcknowledgeMotionCommit(",
    )
    assignment = "plan->reservationId = gOverworldActorSystemState.nextReservationId;"
    if assignment not in body or "if (plan->reservationId == 0)" in body:
        return False
    return (
        body.index("ActorSystem_IsTargetReservedByOtherActor(")
        < body.index(assignment)
        < body.index("OverworldMotion_Begin(")
    )


def wild_captures_identity(receipt: str) -> bool:
    name = "OverworldWildSpawns_AcknowledgeSharedMotion("
    if name not in receipt:
        return False
    body = receipt[receipt.index(name):]
    return all((
        "sOverworldWildSpawnState.movementRuntimeState;" in body,
        "return OverworldWildRuntime_ApplyMotionBoundary(\n"
        "        slot, acknowledgements, appliedThrough, sample, phase,\n"
        "        runtime->movementMotionIdentities[slot]);" in body,
        "OVERWORLD_MOUNT_RUNTIME_STATE_ADDR" not in receipt,
        "OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS;" in receipt,
    ))


def adapters_carry_identity(
    internal: str,
    runtime: str,
    mount_internal: str,
    mount: str,
    wild_internal: str,
    wild: str,
) -> bool:
    bridge = function(
        runtime,
        "OverworldWildRuntime_ApplyMotionBoundary(",
        "OverworldWildRuntime_SetFacingVectorUnlessMounted(",
    )
    return all((
        "u16 motionIdentity;" in internal,
        "runtime->movementMotionIdentities[slot] = call.motionIdentity;" in runtime,
        "u8 *phase,\n    u16 motionIdentity)" in bridge,
        "call.motionIdentity = motionIdentity;" in bridge,
        "OVERWORLD_MOUNT_RUNTIME_STATE_ADDR" not in bridge,
        "sOverworldWildSpawnState" not in bridge,
        "movementMotionIdentities" not in bridge,
        "OVERWORLD_ACTOR_BOUNDARY_REBIND_FIELD" not in runtime,
        "u16 motionIdentity;" in mount_internal,
        "sOverworldMountState.motionIdentity = request.motionIdentity;" in mount,
        "sOverworldMountState.motionIdentity = call.motionIdentity;" in mount,
        "sOverworldMountState.motionIdentity = 0;" in mount,
        "sOverworldMountState.motionIdentity" in mount[
            mount.index("OverworldMount_AcknowledgeSharedMotion("):
        ],
        "&OVERWORLD_MOUNT_BOUNDARY_PHASE,\n        sOverworldMountState.motionIdentity" in mount,
        "u16 movementMotionIdentities[OW_WILD_MAX_SPAWNS];" in wild_internal,
        "runtime->movementMotionIdentities[slot] = request.motionIdentity;" in wild,
        "u8 *phase);" in wild,
        ".thumb_func\\n.thumb_set OverworldWildSpawns_AcknowledgeSharedMotion, 0x023BD3C4\\n" in wild,
    ))


def retained_rebind_requires_actor_identity(wild: str) -> bool:
    body = function(
        wild,
        "OverworldWildSpawns_RebindRetainedSpawnObject(",
        "OverworldWildSpawns_ApplyTransitionWork(",
    )
    mask_guard = (
        "(call->retainedActorMask\n"
        "                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) == 0"
    )
    if mask_guard not in body:
        return False
    guard_at = body.index(mask_guard)
    return (
        guard_at < body.index("OVERWORLD_ACTOR_SYSTEM_ENTRY->inspect(")
        and guard_at < body.index(
            "OverworldActorTransition_RetainedHandleMatches("
        )
        and guard_at < body.index(
            "snapshot.actor.subjectIdentity != spawn->personality"
        )
        and "retainedActorMask & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) != 0"
            not in body
    )


def retained_mask_requires_active_spawns(wild: str) -> bool:
    helper = function(
        wild,
        "OverworldWildSpawns_RetainedMaskNamesActiveSpawns(",
        "OverworldWildSpawns_RebindRetainedSpawnObject(",
    )
    body = function(
        wild,
        "OverworldWildSpawns_ApplyTransitionWork(",
        "OverworldWildSpawns_CleanupPresentationBeforeUnload(",
    )
    rebind = "if (call->work == OVERWORLD_ACTOR_TRANSITION_WORK_REBIND)"
    loop = "int remaining = OW_WILD_MAX_SPAWNS;"
    guard = "((u32)retainedActorMask << 31) != 0 && !spawn->active"
    call = "OverworldWildSpawns_RetainedMaskNamesActiveSpawns("
    mutation = "state->mapGeneration = call->nextMapGeneration;"
    if (
        rebind not in body
        or loop not in helper
        or guard not in helper
        or "retainedActorMask >>= 1;" not in helper
        or "} while (--remaining != 0);" not in helper
        or call not in body
        or mutation not in body
    ):
        return False
    rebind_at = body.index(rebind)
    call_at = body.index(call, rebind_at)
    return rebind_at < call_at < body.index(mutation, rebind_at)


def main() -> None:
    actor_path = REPO / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
    internal_path = REPO / "include/overworld_actor_system_internal.h"
    runtime_path = REPO / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
    mount_internal_path = REPO / "include/overworld_mount_internal.h"
    mount_path = REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c"
    wild_internal_path = REPO / "include/overworld_wild_spawns_internal.h"
    wild_path = REPO / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"

    actor = actor_path.read_text()
    internal = internal_path.read_text()
    runtime = runtime_path.read_text()
    mount_internal = mount_internal_path.read_text()
    mount = mount_path.read_text()
    wild_internal = wild_internal_path.read_text()
    wild = wild_path.read_text()
    receipt = (REPO / "src/overworld_wild_runtime_overlay/overworld_wild_motion_receipt.c").read_text()

    require(wild_captures_identity(receipt),
            "Wild call adapter does not pass its saved receipt as argument six")
    for replacement in ("0", ""):
        mutant = receipt.replace("runtime->movementMotionIdentities[slot]", replacement, 1)
        require(not wild_captures_identity(mutant),
                "zero or missing Wild capture argument mutation survived")

    require(
        "OverworldActorMotionRequestCallSizeMustRemain44Bytes" in internal
        and "OverworldActorMotionBoundaryCallSizeMustRemain32Bytes" in internal,
        "fixed motion call ABI guards are missing",
    )
    require(
        request_rejects_stale_field(actor),
        "normal and Teleport requests do not share a pre-plan field guard",
    )
    require(
        request_rejects_active_transition(actor),
        "motion request can begin while the transition owner is active",
    )
    require(
        boundary_rejects_wrong_motion(actor),
        "engine receipts do not reject a missing or stale motion identity",
    )
    require(
        "call->motionIdentity = plan->reservationId;" in function(
            actor,
            "ActorSystem_RequestMotion(",
            "ActorSystem_TryAcknowledgeMotionCommit(",
        ),
        "accepted start does not return its reservation identity",
    )
    request = function(
        actor,
        "ActorSystem_RequestMotion(",
        "ActorSystem_TryAcknowledgeMotionCommit(",
    )
    require(
        actor_assigns_fresh_identity(actor),
        "Actor Motion can trust or retain a caller-supplied reservation ID",
    )
    require(
        adapters_carry_identity(
            internal,
            runtime,
            mount_internal,
            mount,
            wild_internal,
            wild,
        ),
        "Wild or Mount does not retain and return the accepted motion identity",
    )
    require(
        retained_rebind_requires_actor_identity(wild),
        "Wild rebind can preserve a spawn absent from the retained actor mask",
    )
    require(
        retained_mask_requires_active_spawns(wild),
        "Wild rebind can preserve an inactive spawn named by the retained mask",
    )

    stale_guard_mutant = actor.replace(
        "expectedFieldEpoch != gOverworldActorSystemState.fieldEpoch",
        "expectedFieldEpoch == gOverworldActorSystemState.fieldEpoch",
        1,
    )
    require(
        not request_rejects_stale_field(stale_guard_mutant),
        "reversed field-epoch guard mutation survived",
    )
    transition_guard_mutant = request.replace(
        "if (ActorSystem_TransitionIsActive())",
        "if (!ActorSystem_TransitionIsActive())",
        1,
    )
    require(
        not request_rejects_active_transition(
            actor.replace(request, transition_guard_mutant, 1)
        ),
        "reversed active-transition guard mutation survived",
    )
    caller_reservation_mutant = request.replace(
        "plan->reservationId = gOverworldActorSystemState.nextReservationId;",
        "if (plan->reservationId == 0) {\n"
        "        plan->reservationId = "
        "gOverworldActorSystemState.nextReservationId;\n"
        "    }",
        1,
    )
    require(
        not actor_assigns_fresh_identity(
            actor.replace(request, caller_reservation_mutant, 1)
        ),
        "caller-supplied reservation mutation survived",
    )
    token_guard_mutant = actor.replace(
        "call->motionIdentity != actor->reservationId",
        "call->motionIdentity == actor->reservationId",
        1,
    )
    require(
        not boundary_rejects_wrong_motion(token_guard_mutant),
        "recycled-motion identity mutation survived",
    )
    auto_rebind_mutant = runtime.replace(
        "call.motionIdentity = motionIdentity;",
        "call.motionIdentity = motionIdentity;\n"
        "    call.acknowledgements |= OVERWORLD_ACTOR_BOUNDARY_REBIND_FIELD;",
        1,
    )
    require(
        not adapters_carry_identity(
            internal,
            auto_rebind_mutant,
            mount_internal,
            mount,
            wild_internal,
            wild,
        ),
        "adapter-owned field rebind mutation survived",
    )
    bridge = function(
        runtime,
        "OverworldWildRuntime_ApplyMotionBoundary(",
        "OverworldWildRuntime_SetFacingVectorUnlessMounted(",
    )
    live_token_mutant = bridge.replace(
        "call.motionIdentity = motionIdentity;",
        "call.motionIdentity = ((const OverworldMountRuntimeState *)"
        "OVERWORLD_MOUNT_RUNTIME_STATE_ADDR)->motionIdentity;",
        1,
    )
    require(
        not adapters_carry_identity(
            internal,
            runtime.replace(bridge, live_token_mutant, 1),
            mount_internal,
            mount,
            wild_internal,
            wild,
        ),
        "live-token boundary bridge mutation survived",
    )
    retained_mask_mutant = wild.replace(
        "        || (call->retainedActorMask\n"
        "                & OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot)) == 0",
        "",
        1,
    )
    require(
        not retained_rebind_requires_actor_identity(retained_mask_mutant),
        "missing retained-mask guard mutation survived",
    )
    inactive_spawn_mutant = wild.replace(
        "((u32)retainedActorMask << 31) != 0 && !spawn->active",
        "((u32)retainedActorMask << 31) != 0 && spawn->active",
        1,
    )
    require(
        not retained_mask_requires_active_spawns(inactive_spawn_mutant),
        "inactive retained-spawn guard mutation survived",
    )

    print("motion identity source and mutation checks passed")


if __name__ == "__main__":
    main()
