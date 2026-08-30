#!/usr/bin/env python3
"""Verify exact-frame wild Walk motion and shared momentum rules."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str) -> str:
    start = -1
    while True:
        start = source.find(name, start + 1)
        if start < 0:
            raise ValueError(f"missing function body: {name}")
        line_start = source.rfind("\n", 0, start) + 1
        declaration_prefix = source[line_start:start]
        if declaration_prefix and not any(
            token in declaration_prefix
            for token in ("static", "BOOL", "u8", "void")
        ):
            continue
        opening = source.find("{", start)
        declaration = source.find(";", start)
        if opening >= 0 and (declaration < 0 or opening < declaration):
            break
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise ValueError(f"unterminated body: {name}")


def require(source: str, values: tuple[str, ...], label: str) -> None:
    missing = [value for value in values if value not in source]
    if missing:
        raise SystemExit(f"{label} is incomplete: {', '.join(missing)}")


def reject(source: str, values: tuple[str, ...], label: str) -> None:
    found = [value for value in values if value in source]
    if found:
        raise SystemExit(f"{label} still contains: {', '.join(found)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=REPO
        / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c",
    )
    parser.add_argument(
        "--runtime-source",
        type=Path,
        default=REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c",
    )
    parser.add_argument(
        "--movement-header",
        type=Path,
        default=REPO / "include/overworld_wild_movement.h",
    )
    parser.add_argument(
        "--timing-policy-header",
        type=Path,
        default=REPO / "include/overworld_walk_timing_policy.h",
    )
    parser.add_argument(
        "--direction-policy-header",
        type=Path,
        default=REPO / "include/overworld_walk_direction_policy.h",
    )
    parser.add_argument(
        "--walk-module-source",
        type=Path,
        default=REPO
        / "src/pokemon_move_history_overlay/overworld_walk_module.c",
    )
    parser.add_argument(
        "--walk-module-header",
        type=Path,
        default=REPO / "include/overworld_walk_module.h",
    )
    parser.add_argument(
        "--mount-source",
        type=Path,
        default=REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c",
    )
    args = parser.parse_args()

    source = args.source.read_text()
    runtime = args.runtime_source.read_text()
    header = args.movement_header.read_text()
    timing_policy = args.timing_policy_header.read_text()
    direction_policy = args.direction_policy_header.read_text()
    module = args.walk_module_source.read_text()
    module_header = args.walk_module_header.read_text()
    mount_source = args.mount_source.read_text()

    require(
        module_header,
        (
            "#define OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY_ADDR 0x023BF474",
            "typedef struct OverworldWalkWildPolicyModuleEntry",
            "OverworldWalkWildPolicyModuleEntrySizeMustRemain20Bytes",
            "resolvePrimitives",
            "groupFlagsForTypes",
            "selectConditionalOverrideMask",
        ),
        "resident wild policy ABI",
    )
    require(
        module,
        (
            "Walk_WildResolvePrimitives(",
            "Walk_WildGroupFlagsForTypes(",
            "Walk_WildSelectConditionalOverrideMask(",
            "gOverworldWalkWildPolicyModuleEntry",
        ),
        "resident wild policy implementation",
    )
    require(
        source,
        (
            "OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY->groupFlagsForTypes(",
            "->selectConditionalOverrideMask(",
        ),
        "overlay149 resident policy routing",
    )
    if (
        "OVERWORLD_WALK_WILD_POLICY_MODULE_ENTRY->resolvePrimitives(" not in source
        and not (
            '"1: .word 0x023BF474\\n"' in source
            and '"ldr r2, [r2, #8]\\n"' in source
        )
    ):
        raise SystemExit("overlay149 primitive-resolution ABI routing is missing")

    entry = re.search(
        r"typedef struct OverworldWalkModuleEntry \{(?P<body>.*?)"
        r"\} OverworldWalkModuleEntry;",
        module_header,
        re.DOTALL,
    )
    entry_fields = (
        "clampTime",
        "accelerateTime",
        "skidTiles",
        "skidTime",
        "stompApplies",
        "directionFromKeys",
        "directionKey",
        "deltaX",
        "deltaY",
        "isFortyFiveDegreeTurn",
        "resolveMountedDiagonal",
        "strictDiagonalAllowed",
        "diagonalFacing",
        "directionFromDelta",
    )
    entry_positions = [] if entry is None else [
        entry.group("body").find(field) for field in entry_fields
    ]
    if entry is None or any(position < 0 for position in entry_positions) \
            or entry_positions != sorted(entry_positions):
        raise SystemExit("fixed 0x40 Walk entry field order changed")
    require(
        module_header,
        (
            "OVERWORLD_WALK_MODULE_ENTRY_ADDR 0x023BF400",
            "OVERWORLD_WALK_PROFILE_MODULE_ENTRY_ADDR 0x023BF440",
            "OVERWORLD_WALK_MOUNT_MODULE_ENTRY_ADDR 0x023BF458",
            "OVERWORLD_WALK_FACE_MODULE_ENTRY_ADDR 0x023BF468",
            "OverworldWalkModuleEntrySizeMustRemain64Bytes",
        ),
        "resident Walk service ABI",
    )

    require(
        header,
        (
            "#define OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG 0x80",
            "#define OW_WILD_WALK_TRAVEL_TIME_MIN 1",
            "#define OW_WILD_WALK_TRAVEL_TIME_MAX 32",
        ),
        "Walk frame-time range",
    )
    clamp = function_body(timing_policy, "OverworldWalkTimingPolicy_Clamp")
    require(
        clamp,
        (
            "travelTime < OVERWORLD_WALK_TIMING_MIN",
            "travelTime > OVERWORLD_WALK_TIMING_MAX",
        ),
        "Walk frame-time clamp",
    )
    accelerate = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_Accelerate",
    )
    require(
        accelerate,
        (
            "(currentTravelTime + 1u) / 2u",
            "nextTravelTime < fastestTravelTime",
        ),
        "Walk half-step acceleration",
    )
    skid_tiles = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_SkidTiles",
    )
    require(
        skid_tiles,
        (
            "travelTime >= 5",
            "travelTime >= 3",
            "travelTime == 2 ? 2 : 4",
        ),
        "Walk skid distance bands",
    )
    skid_time = function_body(
        timing_policy,
        "OverworldWalkTimingPolicy_SkidTime",
    )
    require(
        skid_time,
        ("OVERWORLD_WALK_TIMING_MAX / 2", "travelTime * 2u"),
        "Walk skid frame time",
    )

    start = function_body(runtime, "OverworldWildRuntime_WalkMomentumStart")
    require(
        start,
        (
            "preventTurnSkid = (requestedDirection",
            "~OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG",
            "OVERWORLD_WALK_MODULE_ENTRY->isFortyFiveDegreeTurn(",
            "OVERWORLD_WALK_MODULE_ENTRY->skidTiles(state->speed)",
            "OVERWORLD_WALK_MODULE_ENTRY->skidTime(state->speed)",
        ),
        "wild Walk turn and skid rules",
    )
    reject(
        start,
        (
            "requestedDirection &= 3",
            "requestedDirection & 3",
            "requestedDirection < OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG",
            "state->speed--;",
            "state->speed++;",
            "1u <<",
        ),
        "wild Walk direction or speed-tier handling",
    )
    flag_strip = start.find("~OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG")
    forty_five = start.find("isFortyFiveDegreeTurn(")
    skid_branch = start.find("skidTiles =", forty_five)
    if not (0 <= flag_strip < forty_five < skid_branch):
        raise SystemExit(
            "wild Walk must strip only the 0x80 flag, accept 45-degree turns, "
            "then test 90-degree skids"
        )

    finish = function_body(runtime, "OverworldWildRuntime_WalkMomentumFinish")
    require(
        finish,
        (
            "completedDistance != 1",
            "completedDirection != state->direction",
            "state->tileCounter >= tilesToAccelerate",
            "OVERWORLD_WALK_MODULE_ENTRY->accelerateTime(",
            "fastestTravelTime",
        ),
        "wild Walk completion and acceleration",
    )
    reject(
        finish,
        ("state->speed--;", "state->speed++;", "1u <<"),
        "wild Walk completion speed-tier handling",
    )

    chain_pause = function_body(
        mount_source,
        "OverworldWildMovementPolicy_PrepareChainPause",
    )
    require(
        chain_pause,
        (
            "pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE",
            "*deferredPauseTicks = 0;",
            "goto chain_disabled;",
            "chain_disabled:",
            "*stepsRemaining = 0;",
            "*deferredPauseAction = 0;",
        ),
        "disabled chain-pause cleanup",
    )
    if chain_pause.find(
        "pauseAction == OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_NONE"
    ) > chain_pause.find(
        "OverworldWildMovementPolicy_RecordCompletedWalkTile("
    ):
        raise SystemExit(
            "chain-pause None must disable the lane before movement counting"
        )

    direction_from_delta = function_body(
        direction_policy,
        "OverworldWalkDirectionPolicy_FromDelta",
    )
    require(
        direction_from_delta,
        (
            "OVERWORLD_WALK_DIRECTION_NORTH_WEST",
            "OVERWORLD_WALK_DIRECTION_NORTH_EAST",
            "OVERWORLD_WALK_DIRECTION_SOUTH_WEST",
            "OVERWORLD_WALK_DIRECTION_SOUTH_EAST",
            "OVERWORLD_WALK_DIRECTION_NONE",
        ),
        "eight-way direction encoding",
    )
    forty_five_rule = function_body(
        direction_policy,
        "OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn",
    )
    require(
        forty_five_rule,
        (
            "OverworldWalkDirectionPolicy_DeltaX(from)",
            "OverworldWalkDirectionPolicy_DeltaX(to)",
            "OverworldWalkDirectionPolicy_DeltaY(from)",
            "OverworldWalkDirectionPolicy_DeltaY(to)",
            "> 0",
        ),
        "45-degree dot-product rule",
    )
    strict_diagonal = function_body(module, "Walk_StrictDiagonalAllowed")
    if strict_diagonal.count("Walk_CanCardinal(avatar,") != 2:
        raise SystemExit(
            "strict diagonal movement must clear both cardinal neighbor tiles"
        )
    require(
        strict_diagonal,
        ("targetX", "targetY", "validateHopLanding("),
        "strict diagonal destination validation",
    )

    planned = function_body(
        source,
        "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand",
    )
    require(
        planned,
        (
            "OVERWORLD_WALK_MODULE_ENTRY->directionFromDelta(",
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(",
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(",
            "distance = 1;",
            "OverworldWildSpawns_TryStartAcceleratedWalkStep(",
            "state->movementStagedHopPending[slot] = TRUE;",
        ),
        "wild flat Walk planning",
    )
    reject(
        planned,
        (
            "OverworldWildSpawns_MovementDirectionDeltaX(direction)",
            "OverworldWildSpawns_MovementDirectionDeltaY(direction)",
            "MapObject_MovementCommandFromDirection(",
        ),
        "wild diagonal Walk stock-direction handling",
    )

    prepared = function_body(
        source,
        "OverworldWildSpawns_StartPreparedCustomJumpCommand",
    )
    require(
        prepared,
        (
            "frameCount = runtime->movementWalkMomentum[slot].speed;",
            "runtime->movementCustomMotionModes[slot] = flatWalk",
            "OW_WILD_CUSTOM_MOTION_WALK",
            "movementCustomJumpArcHeightsQ4[slot] = !flatWalk",
            "OVERWORLD_WALK_MODULE_ENTRY->diagonalFacing(",
            "runtime->movementCustomJumpPrepActive[slot] = !flatWalk;",
            "if (chainReposition && !repositionUsesArc)",
            "(object->flags & MAPOBJECTFLAG_UNK7) != 0",
        ),
        "wild exact flat-motion setup",
    )
    reject(
        prepared,
        ("frameCount = 1u <<", "frameCount = 1 <<"),
        "wild flat Walk frame timing",
    )

    landing = function_body(
        source,
        "OverworldWildSpawns_IsBehaviorAllowedHopLandingTile",
    )
    require(
        landing,
        (
            "OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER",
            "x != movingObject->xCurr",
            "y != movingObject->yCurr",
            "x,\n                movingObject->yCurr",
            "movingObject->xCurr,\n                y",
        ),
        "wild strict diagonal clearance",
    )

    reservation = function_body(
        source,
        "OverworldWildSpawns_IsTileReservedByOtherWild",
    )
    guard = reservation.find(
        "movementPendingDirections[i]\n"
        "                <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT"
    )
    delta = reservation.find("OverworldWildSpawns_MovementDirectionDeltaX(")
    if guard < 0 or delta < 0 or guard > delta:
        raise SystemExit(
            "diagonal pending directions can reach a stock cardinal delta helper"
        )

    gate = function_body(source, "OverworldWildWalkMomentum_GateTurnSkid")
    require(gate, ('"add r1, r1, #128\\n"',), "wild no-skid flag assembly")
    reject(gate, ('"add r1, r1, #4\\n"',), "old diagonal/no-skid collision")

    start_step = function_body(source, "OverworldWildSpawns_StartMomentumWalkStep")
    require(
        start_step,
        (
            "movementPreviousTileLocked[stepContext->slot] += skidStep;",
            "OW_WILD_SPAWNER_CUSTOM_MOTION_WALK_FLAG",
            "OVERWORLD_WALK_MODULE_ENTRY->deltaX(direction)",
            "OVERWORLD_WALK_MODULE_ENTRY->deltaY(direction)",
            "OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER",
            "direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT",
            "validateStep = FALSE;",
            "if (skidStep && validateStep)",
            "OverworldWildSpawns_PlayMovementCrashFeedback(",
        ),
        "wild skid history isolation",
    )
    if start_step.count("OverworldWildSpawns_PlayMovementCrashFeedback(") != 1:
        raise SystemExit("a blocked skid must request crash feedback exactly once")
    blocked_label = start_step.find("validated_step_blocked:")
    feedback = start_step.find("OverworldWildSpawns_PlayMovementCrashFeedback(")
    validation_complete = start_step.find("validateStep = FALSE;")
    prepared_start = start_step.find(
        "OverworldWildSpawns_StartPreparedCustomJumpCommand("
    )
    if not (0 <= validation_complete < prepared_start < blocked_label < feedback):
        raise SystemExit(
            "blocked skid feedback must only run for failed collision validation"
        )
    crash_feedback = function_body(
        source,
        "OverworldWildSpawns_PlayMovementCrashFeedback",
    )
    require(
        crash_feedback,
        (
            "OW_WILD_BEHAVIOR_WALK_CRASH_SOUND(lane->walkOptions)",
            "OW_WILD_BEHAVIOR_WALK_CRASH_SOUND_WALL_HIT",
            "PlaySE(OW_WILD_SPAWNER_WALK_CRASH_SE);",
        ),
        "authored blocked skid crash feedback",
    )
    effect = function_body(source, "OverworldWildSpawns_ApplyWalkMomentumEffect")
    require(
        effect,
        (
            "movementPreviousTileLocked[stepContext->slot] = FALSE;",
            "movementLastDistances[stepContext->slot] = 0;",
        ),
        "wild skid completion isolation",
    )

    accelerated = function_body(
        source,
        "OverworldWildSpawns_TryStartAcceleratedWalkStep",
    )
    require(
        accelerated,
        (
            "movementSpawnRunActive[stepContext->slot]",
            "? OW_WILD_SPAWNER_SPOT_STATE_ACTIVE",
            "direction | OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG",
            "OverworldWildWalkMomentum_GateTurnSkid(",
        ),
        "spawn-run fixed momentum",
    )
    single_step = function_body(
        source,
        "OverworldWildSpawns_TryStartSingleDirectionMovementStep",
    )
    require(
        single_step,
        (
            "direction <= OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT",
            "movementSpawnRunActive[stepContext->slot]",
            "OverworldWildSpawns_TryStartAcceleratedWalkStep(",
        ),
        "spawn-run exact flat-motion route",
    )
    reject(
        single_step,
        ("if (!stepContext->state->movementSpawnRunActive",),
        "spawn-run stock command bypass",
    )
    spawn_finish = function_body(
        source,
        "OverworldWildSpawns_HandleFinishedSpawnRunMovementCommand",
    )
    require(
        spawn_finish,
        (
            "customWalkWasActive",
            "movementCustomJumpTargetX[slot]",
            "movementCustomJumpTargetY[slot]",
        ),
        "spawn-run one-tile custom Walk completion",
    )
    spawn_start = function_body(source, "OverworldWildSpawns_SetSpawnRunState")
    spawn_clear = function_body(source, "OverworldWildSpawns_ClearSpawnRunState")
    require(
        spawn_start,
        ("walkMomentumReset(", "movementWalkMomentum[slot]"),
        "spawn-run fixed-speed start",
    )
    require(
        spawn_clear,
        ("movementWalkMomentum[slot].speed = 0;",),
        "spawn-run momentum finish",
    )
    reject(
        source,
        ("OverworldWildSpawns_GetMovementWalkCommandForProfile",),
        "obsolete quantized profile Walk command",
    )
    directed = function_body(
        source,
        "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand",
    )
    require(
        directed,
        (
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(movementDirections)",
            "!OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_CARDINAL(movementDirections)",
        ),
        "wild directed diagonal/cardinal policy",
    )
    reject(
        directed,
        ("hopAllowNonCardinal == OW_WILD_BEHAVIOR_BOOL_YES",),
        "old diagonal-only exclusion",
    )
    active = function_body(
        source,
        "OverworldWildSpawns_TryStartFrameDrivenActiveMovementCommand",
    )
    require(
        active,
        (
            "primitives->attentiveLocomotion\n"
            "                == OW_WILD_BEHAVIOR_LOCOMOTION_WANDER",
            "OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(",
            "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand(",
        ),
        "directed diagonal Wander/Chase routing",
    )

    require(
        source,
        (
            "#define OW_WILD_SPAWNER_MOVEMENT_SPEED_DEFAULT "
            "OW_WILD_BEHAVIOR_WALK_TIME_DEFAULT",
            "boostedProfile.attentiveSpeed > "
            "profile->attentiveChaseBoostSpeed",
        ),
        "wild frame-time fallback and scheduler",
    )
    reject(
        source,
        (
            "OverworldWildSpawns_GetFrameMovementDecisionIntervalForSpeed",
            "OverworldWildSpawns_ShouldRunFrameMovementDecisionForSpeed",
            "boostedProfile.attentiveSpeed > OW_WILD_SPAWNER_MOVEMENT_SPEED_4",
        ),
        "old tier-only wild speed policy",
    )

    print(
        "wild exact-frame Walk timing, skid, diagonal, and completion rules verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
