#!/usr/bin/env python3
"""Check that wild Hop and Teleport do not own a second motion clock."""

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"wild motion ownership check failed: {message}")


def function(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start + len(name))
    return source[start:end]


def main() -> None:
    wild = (REPO / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    runtime = (REPO / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
    runtime_header = (REPO / "include/overworld_wild_runtime.h").read_text()
    internal = (REPO / "include/overworld_wild_spawns_internal.h").read_text()
    actor = (REPO / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
    mount = (REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c").read_text()
    hop_planner = (REPO / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c").read_text()
    teleport_planner = (REPO / "src/pokemon_move_history_task6_overlay/overworld_actor_teleport_planner.c").read_text()
    actor_internal = (REPO / "include/overworld_actor_system_internal.h").read_text()
    motion_model = (REPO / "lib/overworld/overworld_motion_model.c").read_text()
    combined = "\n".join(
        (wild, runtime, internal, actor, mount, hop_planner, teleport_planner,
         actor_internal, motion_model)
    )

    for retired in (
        "movementCustomJumpFrameCounts",
        "movementCustomJumpElapsedFrames",
        "movementCustomJumpSpinElapsedFrames",
        "movementCustomJumpSpinSpeeds",
        "movementCustomJumpSpinTimers",
        "movementCustomJumpSpinSteps",
        "OverworldWild_ApplyJumpRenderMotion",
        "applyJumpRenderMotion",
        "OverworldWildSpawns_FinalizeCustomJumpAfterRestore",
        "OverworldWildSpawns_EnsureTeleportFlickerObject",
        "OverworldWildSpawns_HideTeleportFlickerObject",
        "OverworldWildSpawns_SyncTeleportFlickerObject",
        "OVERWORLD_WILD_HOP_TRAJECTORY_ENTRY",
        "OverworldWildHopTrajectoryEntry",
    ):
        require(retired not in combined, f"retired local owner remains: {retired}")

    apply_sample = function(
        wild,
        "OverworldWildSpawns_ApplyCustomJumpRenderOffset(",
        "OverworldWildSpawns_CommitCustomJumpLanding(",
    )
    require("sample.facing" in apply_sample, "Hop facing does not use the actor sample")
    require("u32 elapsed" not in apply_sample, "Hop presentation still accepts local elapsed time")

    update_hop = function(
        wild,
        "OverworldWildSpawns_UpdateCustomJumpLanding(",
        "OverworldWildSpawns_UpdateSpawnerMovementCommandForSlot(",
    )
    require(
        "phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING" in update_hop,
        "Hop completion is not gated by the actor terminal phase",
    )
    require(
        "OVERWORLD_ACTOR_BOUNDARY_ENGINE_END" in update_hop,
        "Hop adapter no longer acknowledges the real engine END seam",
    )
    require(
        'noinline, optimize("Os")' in wild[
            wild.rfind("static BOOL", 0, wild.index("OverworldWildSpawns_UpdateCustomJumpLanding("))
            : wild.index("OverworldWildSpawns_UpdateCustomJumpLanding(")
        ],
        "Hop terminal handling can be duplicated into post-restore callers",
    )
    staged_hop_start = wild.rindex(
        "static BOOL OverworldWildSpawns_HandleFinishedStagedHopMovementCommand("
    )
    staged_hop_end = wild.index(
        "static BOOL OverworldWildSpawns_ExecutePendingStagedHop(",
        staged_hop_start,
    )
    staged_hop_finish = wild[staged_hop_start:staged_hop_end]
    require(
        "OverworldWildSpawns_UpdateCustomJumpLanding(" in staged_hop_finish,
        "post-restore Hop does not reuse the actor-owned terminal path",
    )
    require(
        "!= OW_WILD_CUSTOM_MOTION_WALK" in staged_hop_finish,
        "staged completion can clear Walk identity before its actor boundary",
    )
    intermediate_walk_terminal = staged_hop_finish.index(
        "OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);"
    )
    require(
        staged_hop_finish.rfind(
            "== OW_WILD_CUSTOM_MOTION_WALK",
            0,
            intermediate_walk_terminal,
        ) >= 0,
        "intermediate staged Walk does not close before its next tile",
    )
    require(
        "state->movementCooldowns[slot] = 0;"
            in staged_hop_finish[intermediate_walk_terminal:],
        "staged Hop adds a second segment cooldown",
    )
    require(
        "OW_WILD_SPAWNER_STAGED_WALK_PENDING" in wild
        and "state->movementStagedHopPending[slot] = flatWalk" in wild
        and "!= OW_WILD_SPAWNER_STAGED_WALK_PENDING" in wild,
        "staged Walk type is not preserved across path tiles",
    )
    continue_pending = function(
        wild,
        "OverworldWildSpawns_ContinuePendingStagedHop(",
        "OverworldWildSpawns_GetSpriteID(",
    )
    require(
        "OverworldWildSpawns_GetCurrentMovementLocomotion(" in continue_pending
        and "OW_WILD_BEHAVIOR_LOCOMOTION_HOP" in continue_pending
        and "OW_WILD_BEHAVIOR_LOCOMOTION_WANDER" in continue_pending,
        "staged path scheduler does not resume current-lane Walk and Hop",
    )
    require(
        "OverworldWildSpawns_IsChainActionReady(slot)" in continue_pending,
        "staged continuation can start before the actor settle pause ends",
    )
    require(
        "OverworldWildSpawns_ClearStagedHopTarget(state, slot);"
            in continue_pending,
        "a staged path remains pending after its lane stops supporting movement",
    )
    finish_pending_start = wild.rindex(
        "static void OverworldWildSpawns_FinishPendingStagedHop("
    )
    finish_pending_end = wild.index(
        "static BOOL OverworldWildSpawns_TickCanopyRenderHopMovementCommand(",
        finish_pending_start,
    )
    finish_pending = wild[finish_pending_start:finish_pending_end]
    staged_clear = finish_pending.index(
        "OverworldWildSpawns_ClearStagedHopTargetLocal(state, slot);"
    )
    walk_restore = finish_pending.index(
        "runtime->movementCustomMotionModes[slot] = OW_WILD_CUSTOM_MOTION_WALK;"
    )
    walk_terminal = finish_pending.index(
        "OverworldWildSpawns_HandleFinishedMovementCommand(state, slot);"
    )
    require(
        staged_clear < walk_restore < walk_terminal,
        "staged Walk identity is not restored before terminal dispatch",
    )
    finish_walk = function(
        wild,
        "OverworldWildSpawns_HandleFinishedWalkMovement(",
        "OverworldWildSpawns_CommitDeferredChainMovementPause(",
    )
    require(
        finish_walk.index("->terminalWalk(")
            < finish_walk.index("OverworldWildSpawns_ClearCustomJumpLocal(state, slot);"),
        "Walk presentation clears before the terminal actor boundary",
    )

    update_teleport = function(
        wild,
        "OverworldWildSpawns_TickTeleportMovementCommand(",
        "OverworldWildSpawns_TryStartChillWanderCommand(",
    )
    require("sample.visible" in update_teleport, "Teleport visibility does not use the actor sample")
    require(
        "phase != OVERWORLD_MOTION_PHASE_COMMIT_PENDING" in update_teleport,
        "Teleport completion is not gated by the actor terminal phase",
    )
    teleport_visual = function(
        wild,
        "OverworldWildSpawns_ApplyTeleportHiddenVisual(",
        "OverworldWildSpawns_UpdateTeleportFlicker(",
    )
    for source_value in (
        "movementCustomJumpStartX",
        "movementCustomJumpStartY",
        "movementCustomJumpStartBaseY",
    ):
        require(source_value in teleport_visual, f"Teleport source presentation omits {source_value}")
    for target_value in (
        "movementCustomJumpTargetX",
        "movementCustomJumpTargetY",
        "movementCustomJumpTargetBaseY",
    ):
        require(target_value in teleport_visual, f"Teleport target presentation omits {target_value}")
    require(
        "if (actorVisible)" in teleport_visual,
        "Teleport position selection is not driven by actor sample visibility",
    )
    require(
        "CreateSpecialFieldObjectWithParams" not in teleport_visual,
        "Teleport presentation still creates an adapter-owned duplicate object",
    )

    for field in ("u16 duration", "u8 spinSpeed", "u8 swayWidth"):
        require(field in runtime_header, f"runtime request omits actor intent field: {field}")
    require("intent.duration = duration;" in runtime, "runtime request rebuilds duration from private state")
    require("intent.spinSpeed = spinSpeed;" in runtime, "runtime request rebuilds spin from private state")
    require("intent.swayWidth = swayWidth;" in runtime, "runtime request rebuilds sway from private state")
    shared_motion_ready = function(
        wild,
        "OverworldWildSpawns_IsChainActionReady(",
        "OverworldWildSpawns_RunChainReposition(",
    )
    require(
        "OverworldActorPolicy_Inspect(" in shared_motion_ready
        and "policy.actorActive" in shared_motion_ready
        and "OVERWORLD_MOTION_PHASE_IDLE" in shared_motion_ready
        and "OVERWORLD_MOTION_PHASE_CANCELED" in shared_motion_ready,
        "chain actions do not use actor-owned shared-motion readiness",
    )
    require(
        "OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP" in actor_internal
        and "OverworldActorHopPlanCall *hopPlan" in actor_internal
        and "OverworldActorHopPlanner_Plan(call->hopPlan)" in actor
        and "OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_HOP" in wild,
        "Hop planning does not cross the Actor Motion request seam",
    )
    require(
        "OverworldWildSpawns_ValidateBehaviorHopLanding" in wild
        and "OverworldWildSpawns_BuildHopHelperConfig" in wild
        and "OverworldWildSpawns_RunChainReposition" in wild
        and "OverworldActorPolicy_Inspect" in wild,
        "wild Hop world and chain glue is not local to the wild adapter",
    )
    require(
        "OverworldActorHopPlanner_PlanVector" in hop_planner
        and "OverworldActorHopPlanner_PlanTrajectory" in hop_planner,
        "Actor Motion Hop planner does not own vector and trajectory policy",
    )

    for retired in (
        "OverworldWildSpawns_TryUseAdjacentTeleportCandidate(",
        "OverworldWildSpawns_TryGetAdjacentTeleportTarget(",
        "OverworldWildSpawns_TryGetDirectionalTeleportTarget(",
        "OverworldWildSpawns_TryGetChillTeleportTarget(",
        "OverworldWildSpawns_TryStartTeleportToTile(",
        "OverworldWildSpawns_BeginSharedTeleport(",
    ):
        require(retired not in wild, f"wild retains Teleport policy owner: {retired}")

    planned_teleport = function(
        wild,
        "OverworldWildSpawns_TryStartPlannedTeleport(",
        "OverworldWildSpawns_TryStartChillTeleportMovementCommand(",
    )
    require(
        planned_teleport.count("OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request)")
            == 1,
        "wild Teleport does not use one atomic Actor Motion request",
    )
    for world_glue in (
        "OverworldWildSpawns_ClassifyTeleportCandidate",
        "OverworldWildSpawns_IsTeleportDestinationTile",
        "OverworldWildSpawns_GetObjectGroundBaseYAt",
    ):
        require(
            world_glue in wild,
            f"wild Teleport adapter omits world glue: {world_glue}",
        )
    require(
        "OverworldWildSpawns_IsTileReservedByOtherWild" not in wild,
        "wild adapter retains a private target-reservation owner",
    )
    for seam in (
        "planCall.classify = OverworldWildSpawns_ClassifyTeleportCandidate;",
        "planCall.flags =\n        OVERWORLD_ACTOR_TELEPORT_FLAG_RESERVED_STOPS_SEARCH;",
        "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT;",
        "request.teleportPlan = &planCall;",
        "plan.duration",
        "plan.visibilityPolicy",
        "plan.pauseFrames",
        "plan.facing",
    ):
        require(
            seam in planned_teleport,
            f"wild Teleport does not consume the atomic plan: {seam}",
        )
    require(
        "if (plan.duration == 0" in planned_teleport
        and "OverworldWildSpawns_AcknowledgeSharedMotion(" in planned_teleport
        and "OverworldWildSpawns_CompleteTeleportMovement(" in planned_teleport,
        "zero-time wild Teleport does not sample and ACK in its start frame",
    )
    complete_teleport_start = wild.rindex(
        "static BOOL OverworldWildSpawns_CompleteTeleportMovement("
    )
    complete_teleport_end = wild.index(
        "\nstatic ", complete_teleport_start + 1
    )
    complete_teleport = wild[complete_teleport_start:complete_teleport_end]

    def teleport_relocation_contract(start: str, complete: str) -> bool:
        return (
            "OverworldWildSpawns_SetObjectTile("
            "object, plan.targetX, plan.targetY);" not in start
            and "OverworldWildSpawns_SetObjectLandingTile(" in complete
        )

    require(
        teleport_relocation_contract(planned_teleport, complete_teleport),
        "wild Teleport relocation does not wait for terminal landing",
    )
    early_relocation_mutant = planned_teleport.replace(
        "OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);",
        "OverworldWildSpawns_SetObjectTile(object, plan.targetX, plan.targetY);\n"
        "    OverworldWildSpawns_ReconcileNativeShadow(fieldSystem, object);",
        1,
    )
    require(
        not teleport_relocation_contract(
            early_relocation_mutant, complete_teleport
        ),
        "wild Teleport early-relocation mutant survived",
    )

    mount_teleport = function(
        mount,
        "OverworldMount_RequestTeleportPlan(",
        "OverworldMount_PlanHopTrajectory(",
    )
    require(
        mount_teleport.count("OVERWORLD_ACTOR_SYSTEM_MOTION_ENTRY->request(&request)")
            == 1
        and "request.operation = OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT;"
            in mount_teleport
        and "request.teleportPlan = &planCall;" in mount_teleport,
        "mounted Teleport does not use one atomic Actor Motion request",
    )
    require(
        "planCall.flags" not in mount_teleport,
        "mounted Teleport incorrectly stops after a reserved candidate",
    )
    mount_start = function(
        mount,
        "OverworldMount_TryStartCustomMotion(",
        "OverworldMount_HandleCustomInput(",
    )
    for duplicate in (
        "teleportTime",
        "OW_WILD_BEHAVIOR_TELEPORT_USES_PER_TILE_TIME",
        "OW_WILD_BEHAVIOR_TELEPORT_USES_FLICKER",
    ):
        require(
            duplicate not in mount_start,
            f"mounted Teleport retains deterministic policy: {duplicate}",
        )
    require(
        "if (frames == 0)" in mount_start
        and "OverworldMount_UpdateCustomMotion();" in mount_start
        and "OverworldMount_DrainLandStream();" in mount_start
        and "OverworldMount_TryFinalizeSharedMotion();" in mount_start,
        "zero-time mounted Teleport does not sample and ACK in its start frame",
    )

    require(
        "OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT" in actor_internal
        and "OverworldActorTeleportPlanCall *teleportPlan" in actor_internal
        and "OverworldActorTeleportPlanner_Plan(" in actor
        and "OVERWORLD_ACTOR_MOTION_SERVICE_PLAN_TELEPORT" in wild,
        "Teleport planning does not cross the Actor Motion request seam",
    )
    require(
        "OverworldActorTeleportCandidateSizeMustRemain16Bytes" in actor_internal
        and "sizeof(OverworldActorTeleportCandidate) == 16" in actor_internal
        and "OverworldActorTeleportPlanCallSizeMustRemain32Bytes" in actor_internal
        and "sizeof(OverworldActorTeleportPlanCall) == 32" in actor_internal
        and "OverworldActorMotionRequestCallSizeMustRemain44Bytes" in actor_internal,
        "Teleport request seam sizes are not fixed",
    )
    require(
        "u16 targetSurfaceId;" in actor_internal
        and "OverworldActorMotionRequestTargetSurfaceOffsetMustRemain36"
            in actor_internal
        and "OverworldActorPolicyTargetSurfaceOffsetMustRemain30"
            in actor_internal,
        "target surface identity is not ABI-neutral at the Actor Motion seam",
    )
    require(
        "OverworldActorTeleportPlanner_Plan" not in wild
        and "OverworldActorTeleportPlanner_Plan" not in mount,
        "field adapter bypasses the Actor Motion service",
    )
    require(
        "kind == OVERWORLD_MOTION_KIND_TELEPORT" in runtime,
        "generic wild runtime can still construct a Teleport plan",
    )

    actor_request = function(
        actor,
        "ActorSystem_RequestMotion(",
        "ActorSystem_TryAcknowledgeMotionCommit(",
    )
    for guard in (
        "!actor->active",
        "expectedFieldEpoch != gOverworldActorSystemState.fieldEpoch",
        "OverworldActorTeleportPlanner_Plan(call)",
        "OverworldMotion_Begin(&runtimeSlot->motion, plan)",
        "plan->kind == OVERWORLD_MOTION_KIND_TELEPORT",
        "plan->duration == 0",
        "OverworldMotion_Tick(",
        "ActorSystem_RecordPathAdvances(runtimeSlot, &immediateSample)",
        "ActorSystem_IsTargetReservedByOtherActor(",
        "call->targetSurfaceId",
    ):
        require(guard in actor_request, f"Actor Teleport seam omits: {guard}")
    cancel_actor = function(
        actor,
        "ActorSystem_CancelActor(",
        "ActorSystem_FillReply(",
    )
    commit_actor = function(
        actor,
        "ActorSystem_TryAcknowledgeMotionCommit(",
        "ActorSystem_EngineBoundary(",
    )
    require(
        "ActorSystem_ReleaseTarget(actor);" in cancel_actor
        and "ActorSystem_ReleaseTarget(actor);" in commit_actor,
        "actor target lease is not released on cancel and commit",
    )
    require(
        "OverworldWildSpawns_IsTileOccupiedOnSurface(" in wild
        and "targetSurface.height" in wild,
        "Hop landing occupancy is not scoped to its physical surface",
    )
    record_start = function(
        actor,
        "ActorSystem_RecordMotionStart(",
        "ActorSystem_RequestMotion(",
    )
    for snapshot_value in (
        "actor->originX = plan->startX;",
        "actor->targetX = plan->targetX;",
        "actor->motionPhase = OVERWORLD_MOTION_PHASE_MOVING;",
        "OVERWORLD_ACTOR_EVENT_PLAN_ACCEPTED",
        "OVERWORLD_ACTOR_EVENT_MOTION_STARTED",
    ):
        require(
            snapshot_value in record_start,
            f"Actor start snapshot omits: {snapshot_value}",
        )
    start_record = actor_request.index(
        "ActorSystem_RecordMotionStart(actor, runtimeSlot, plan);"
    )
    immediate_tick = actor_request.index("immediateFlags = OverworldMotion_Tick(")
    require(
        start_record < immediate_tick
        and actor_request.index(
            "actor->motionPhase = runtimeSlot->motion.phase;",
            immediate_tick,
        ) > immediate_tick
        and "actor->motionElapsed = runtimeSlot->motion.elapsed;"
            in record_start,
        "zero-time Teleport ticks before its actor snapshot and traces are coherent",
    )
    require(
        "(intent->duration == 0\n            && intent->kind != OVERWORLD_MOTION_KIND_TELEPORT)"
            in motion_model
        and "(plan->duration == 0\n            && plan->kind != OVERWORLD_MOTION_KIND_TELEPORT)"
            in motion_model,
        "zero duration is not restricted to Teleport",
    )

    # These compact assembly shapes are paired with the deterministic host
    # oracle. Keep the fixed-size production implementation tied to the same
    # bounded order and reservation rules.
    for owner in (
        '"subs r1, r1, r4\\n"',
        '"movs r2, #6\\n"',
        '"subs r1, r2, r1\\n"',
        '"cmp r4, #16\\n"',
        "OverworldActorTeleportPlanner_CandidateDecision",
        "OverworldActorTeleportPlanner_FillPlan",
        '"ldrb r0, [r2, #23]\\n"',
        '"ldrb r0, [r2, #24]\\n"',
        '"strb r0, [r7, #7]\\n"',
    ):
        require(owner in teleport_planner, f"Actor Motion omits Teleport owner: {owner}")
    require(
        '"cmp r2, #6\\n"' in teleport_planner
        and '"lsrs r1, r1, #1\\n"' in teleport_planner
        and '"negs r2, r2\\n"' in teleport_planner,
        "Teleport planner does not preserve the wild-reserved stop flag",
    )

    print("wild motion ownership source checks passed")


if __name__ == "__main__":
    main()
