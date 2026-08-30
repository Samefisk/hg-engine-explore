#!/usr/bin/env python3
"""Verify callback context required by chained wild Walk skid steps."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str) -> str:
    start = -1
    opening = -1
    while True:
        start = source.find(name, start + 1)
        if start < 0:
            raise ValueError(f"missing function body: {name}")
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
        "--mount-source",
        type=Path,
        default=REPO / "src/overworld_mount_overlay/overworld_mount_overlay.c",
    )
    parser.add_argument(
        "--behavior-source",
        type=Path,
        default=REPO / "data/OverworldWildBehaviorData.c",
    )
    args = parser.parse_args()
    source = args.source.read_text()

    finish = function_body(
        source,
        "OverworldWildSpawns_HandleFinishedWalkMovement",
    )
    callback_call = finish.find("walkMomentumFinish(")
    if callback_call < 0:
        raise SystemExit("walk momentum finish callback is missing")
    setup = finish[:callback_call]
    required = (
        "stepContext.profile = profile;",
        "stepContext.primitives = primitives;",
    )
    missing = [assignment for assignment in required if assignment not in setup]
    if missing:
        raise SystemExit(
            "walk momentum continuation context is incomplete: "
            + ", ".join(missing)
        )
    callback_guard = setup.find("if (object == NULL)")
    if (
        callback_guard < 0
        or "OverworldWildSpawns_ClearWalkMovementState(state, slot, NULL);"
        not in setup[callback_guard:]
    ):
        raise SystemExit(
            "walk momentum completion can call skid callbacks after its object is gone"
        )

    start_step = function_body(
        source,
        "OverworldWildSpawns_StartMomentumWalkStep",
    )
    if "stepContext->profile" not in start_step:
        raise SystemExit("blocked skid path no longer consumes the profile context")

    skid_formula = re.compile(
        r"skidRemaining\s*=\s*1u\s*<<\s*\(\s*"
        r"(?:state->speed|sOverworldMountState\.speed)\s*-\s*"
        r"\(OW_WILD_WALK_SPEED_MIN\s*\+\s*(\d+)u\)\s*\);"
    )
    for label, path in (
        ("wild", args.runtime_source),
        ("mount", args.mount_source),
    ):
        shifts = skid_formula.findall(path.read_text())
        if shifts != ["2", "2"]:
            raise SystemExit(
                f"{label} Walk skid formulas differ from speed 3/4 = 1/2 tiles: "
                f"{shifts}"
            )

    runtime_source = args.runtime_source.read_text()
    wild_start = function_body(
        runtime_source,
        "OverworldWildRuntime_WalkMomentumStart",
    )
    for invariant in (
        "requestedDirection < OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG",
        "requestedDirection &= OW_WILD_WALK_DIRECTION_NO_TURN_SKID_FLAG - 1u;",
    ):
        if invariant not in wild_start:
            raise SystemExit(
                f"wild Walk turn-skid suppression is incomplete: {invariant}"
            )
    if "speedGain" in wild_start:
        raise SystemExit(
            "wild Walk still requires acceleration above base speed to skid"
        )
    if wild_start.count(
        "state->speed > (OW_WILD_WALK_SPEED_MIN + 1u)"
    ) != 2:
        raise SystemExit(
            "wild Walk stop and turn skids are not both gated by absolute speed"
        )
    wild_turn = wild_start[wild_start.find(
        "state->turnDirection = requestedDirection;"
    ) :]
    wild_turn = wild_turn[:wild_turn.find("if (startStep(")]
    if (
        "state->resumeSpeed = state->speed;" not in wild_turn
        or "state->speed--;" not in wild_turn
    ):
        raise SystemExit(
            "wild Walk turn skid does not reduce speed only after saving it"
        )
    wild_stop = wild_start[
        wild_start.find(
            "state->turnDirection = OW_WILD_WALK_DIRECTION_NONE;"
        ) : wild_start.find("if (startStep(")
    ]
    if (
        "state->resumeSpeed = state->baseSpeed;" not in wild_stop
        or wild_stop.count("state->speed--;") != 1
    ):
        raise SystemExit("wild Walk stop skid does not lower speed exactly once")

    wild_finish = function_body(
        runtime_source,
        "OverworldWildRuntime_WalkMomentumFinish",
    )
    skid_continuation = wild_finish[
        wild_finish.find("if (state->skidRemaining != 0)") :
        wild_finish.find("if (turnDirection == OW_WILD_WALK_DIRECTION_NONE)")
    ]
    if "state->speed--;" in skid_continuation:
        raise SystemExit("wild Walk skid loses more than one speed tier")
    if "state->speed = state->resumeSpeed;" not in wild_finish:
        raise SystemExit("wild Walk turn skid does not restore its entry speed")
    if not re.search(
        r"if \(effect != NULL\s*&& state->skidRemaining == 1\)\s*\{\s*"
        r"effect\(context, turnDirection, TRUE\);",
        wild_finish,
    ):
        raise SystemExit("wild Walk emits a landing effect for every skid tile")

    for wrapper_name in (
        "OverworldWildRuntime_PlayStepDirtParticle",
        "OverworldWildRuntime_PlayLandingHopParticle",
    ):
        wrapper = function_body(runtime_source, wrapper_name)
        if "if (object == NULL)" not in wrapper:
            raise SystemExit(f"{wrapper_name} dereferences a null object")

    mount_source = args.mount_source.read_text()
    mount_filter = function_body(
        mount_source,
        "OverworldMount_FilterMovementInput",
    )
    for invariant in (
        "sOverworldMountState.turnDirection",
        ">= sOverworldMountState.snapshot.profile.tilesBeforeTurnSkid",
    ):
        if invariant not in mount_filter:
            raise SystemExit(
                f"mounted Walk turn-skid buildup is incomplete: {invariant}"
            )
    if "speed > sOverworldMountState.baseSpeed" in mount_filter:
        raise SystemExit(
            "mounted Walk still requires acceleration above base speed to skid"
        )
    if mount_filter.count(
        "> (OW_WILD_WALK_SPEED_MIN + 1u)"
    ) != 2:
        raise SystemExit(
            "mounted Walk stop and turn skids are not both gated by absolute speed"
        )
    mount_turn = mount_filter[mount_filter.find(
        "sOverworldMountState.turnDirection = requestedDirection;"
    ) :]
    mount_turn = mount_turn[:mount_turn.find("OverworldMount_ForceDirection(")]
    if (
        "sOverworldMountState.resumeSpeed = sOverworldMountState.speed;"
        not in mount_turn
        or mount_turn.count("sOverworldMountState.speed--;") != 1
    ):
        raise SystemExit(
            "mounted Walk turn skid does not reduce speed only after saving it"
        )
    mount_stop_start = mount_filter.find(
        "sOverworldMountState.turnDirection = OVERWORLD_MOUNT_DIRECTION_NONE;"
    )
    mount_stop = mount_filter[
        mount_stop_start : mount_filter.find(
            "OverworldMount_ForceDirection(",
            mount_stop_start,
        )
    ]
    if (
        "sOverworldMountState.resumeSpeed = "
        "sOverworldMountState.baseSpeed;" not in mount_stop
        or mount_stop.count("sOverworldMountState.speed--;") != 1
    ):
        raise SystemExit("mounted Walk stop skid does not lower speed exactly once")

    mount_finish = function_body(
        mount_source,
        "OverworldMount_CompletePendingStep",
    )
    buildup_increment = mount_finish.find(
        "sOverworldMountState.turnDirection++;"
    )
    resume_return = mount_finish.find(
        "if (sOverworldMountState.resumeSpeed != 0)"
    )
    if buildup_increment < 0 or buildup_increment > resume_return:
        raise SystemExit(
            "mounted Walk does not count the committed post-skid tile"
        )
    completion_point = mount_finish.find(
        "sOverworldMountState.pendingStep = FALSE;"
    )
    if completion_point < 0:
        raise SystemExit("mounted Walk completion point is missing")
    if "MapObject_IsMovementPaused(follower)" in mount_finish[:completion_point]:
        raise SystemExit(
            "mounted Walk still waits indefinitely for the visual follower"
        )
    if "OverworldMount_NormalizeFollowerAfterStep(" not in mount_finish:
        raise SystemExit(
            "mounted Walk does not normalize the visual follower after a step"
        )
    mount_skid_continuation = mount_finish[
        mount_finish.find("if (sOverworldMountState.skidRemaining != 0)") :
        mount_finish.find("turnDirection = sOverworldMountState.turnDirection;")
    ]
    if "sOverworldMountState.speed--;" in mount_skid_continuation:
        raise SystemExit("mounted Walk skid loses more than one speed tier")
    if (
        "sOverworldMountState.speed = "
        "sOverworldMountState.resumeSpeed;" not in mount_finish
    ):
        raise SystemExit("mounted Walk turn skid does not restore its entry speed")
    if not re.search(
        r"if \(sOverworldMountState\.skidRemaining == 1\)\s*\{\s*"
        r"OverworldMount_EmitStepEffect\(TRUE\);",
        mount_finish,
    ):
        raise SystemExit("mounted Walk emits a landing effect for every skid tile")

    mount_normalize = function_body(
        mount_source,
        "OverworldMount_NormalizeFollowerAfterStep",
    )
    if "MapObject_SetPositionFromVectorAndDirection(" not in mount_normalize:
        raise SystemExit(
            "mounted Walk follower normalization does not clear and snap movement"
        )

    mount_issue = function_body(
        mount_source,
        "OverworldMount_IssueHeldMovement",
    )
    for invariant in (
        "BOOL trackedStep = FALSE;",
        "else if (mountedPlayer)",
        "if (trackedStep && sOverworldMountState.pendingSkid)",
    ):
        if invariant not in mount_issue:
            raise SystemExit(
                "mounted Walk does not cancel stale skid state for every "
                f"special movement command: {invariant}"
            )
    if (
        "OverworldMount_GetWalkCommand(sOverworldMountState.speed)"
        not in mount_issue
    ):
        raise SystemExit("mounted Walk skid command does not use temporary speed")
    special_interrupt = mount_issue.find("else if (mountedPlayer)")
    special_reset = mount_issue.find(
        "OverworldMount_ResetMomentum();",
        special_interrupt,
    )
    if (
        special_interrupt < 0
        or special_reset < 0
        or "OverworldMount_NormalizeFollowerAfterStep(object);"
        not in mount_issue[special_interrupt:special_reset]
    ):
        raise SystemExit(
            "mounted special movement does not cancel the visual follower command"
        )

    try_start = function_body(
        source,
        "OverworldWildSpawns_TryStartAcceleratedWalkStep",
    )
    for invariant in (
        "OverworldWildWalkMomentum_GateTurnSkid(",
        "lane->tilesBeforeTurnSkid",
    ):
        if invariant not in try_start:
            raise SystemExit(
                f"wild Walk turn-skid buildup gate is incomplete: {invariant}"
            )
    chain_pause = function_body(
        source,
        "OverworldWildSpawns_ApplyUniversalChainMovementPause",
    )
    for invariant in (
        "&runtime->movementWalkMomentum[slot]",
    ):
        if invariant not in chain_pause:
            raise SystemExit(
                f"wild Walk buildup completion rule is incomplete: {invariant}"
            )
    policy = function_body(
        mount_source,
        "OverworldWildMovementPolicy_PrepareChainPause",
    )
    for invariant in (
        "locomotion == OW_WILD_BEHAVIOR_LOCOMOTION_WALK",
        "lane->walkPause != 0",
        "OverworldWildMovementPolicy_RecordCompletedWalkTile(",
    ):
        if invariant not in policy:
            raise SystemExit(
                f"shared Walk buildup completion rule is incomplete: {invariant}"
            )
    chain_commit = function_body(
        source,
        "OverworldWildSpawns_CommitDeferredChainMovementPause",
    )
    if "runtime->movementWalkMomentum[slot].turnDirection" not in chain_commit:
        raise SystemExit("Movement Chain pauses do not reset turn-skid buildup")

    behavior_source = args.behavior_source.read_text()
    nervous_start = behavior_source.find("/* profile: Nervous scavenger */")
    nervous_end = behavior_source.find(
        "/* profile: Follower Pokemon */",
        nervous_start,
    )
    if nervous_start < 0 or nervous_end < 0:
        raise SystemExit("Nervous scavenger profile is missing")
    nervous = behavior_source[nervous_start:nervous_end]
    if not re.search(
        r"10,\s*3,\s*20,\s*10,\s*3,\s*32,",
        nervous,
    ):
        raise SystemExit("Nervous scavenger base speed is not 3")
    if not re.search(
        r"100,\s*100,\s*2,\s*3,",
        nervous,
    ):
        raise SystemExit("Nervous scavenger maximum Walk speed is not 3")
    for invariant in (
        "OW_WILD_BEHAVIOR_OVERRIDE3_ACTIVE_PROFILE",
        "OW_WILD_BEHAVIOR_OVERRIDE3_TIRED_PROFILE",
    ):
        if invariant not in nervous:
            raise SystemExit(f"Nervous scavenger lifecycle mask is missing: {invariant}")
    if nervous.count(
        "OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_NERVOUS_SCAVENGER"
    ) != 2:
        raise SystemExit("Nervous scavenger does not keep speed 3 in both lifecycle lanes")
    for invariant in (
        "OW_WILD_BEHAVIOR_OVERRIDE3_TILES_BEFORE_TURN_SKID",
        "OW_WILD_BEHAVIOR_OVERRIDE3_WALK_PAUSE",
    ):
        if invariant not in nervous:
            raise SystemExit(
                f"Nervous scavenger skid buildup mask is missing: {invariant}"
            )
    if not re.search(
        r"30,\s*60,\s*OW_WILD_BEHAVIOR_WALK_PAUSE_DEFAULT,\s*3,\s*\}",
        nervous,
    ):
        raise SystemExit(
            "Nervous scavenger must use its normal tile wait and require three tiles"
        )

    print(
        "overworld Walk skid context, continuous buildup, and mounted parity verified"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
