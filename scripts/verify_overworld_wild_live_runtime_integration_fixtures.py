#!/usr/bin/env python3
"""Mutation fixtures for the live stack/effective integration verifier."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/verify_overworld_wild_live_runtime_integration.py"
SPEC = importlib.util.spec_from_file_location("live_runtime_verifier", PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("cannot load live runtime verifier")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    spawns = MODULE.DEFAULT_SPAWNS.read_text()
    state = MODULE.DEFAULT_STATE.read_text()
    helper = MODULE.DEFAULT_HELPER.read_text()
    sidecars = MODULE.DEFAULT_SIDECARS.read_text()
    require(
        not MODULE.verify_sources(spawns, state, helper, sidecars),
        "current sources fail verifier",
    )
    checks = 1

    mutations = (
        (
            "legacy authority",
            (spawns, state.replace("void *movementRuntimeState;", "void *movementRuntimeState;\n    u8 movementBehaviorClasses[10];"), helper, sidecars),
            "movementBehaviorClasses",
        ),
        (
            "missing transition reconciliation",
            (spawns.replace("transition.effectiveAfter,\n            transition.actionFlags", "transition.effectiveAfter,\n            0", 1), state, helper, sidecars),
            "action flags",
        ),
        (
            "unauthenticated timer replay",
            (spawns.replace("event.replayExpiry = expiry;", "event.replayExpiry = (OverworldWildRuntimeTimerExpiry){0};", 1), state, helper, sidecars),
            "replayExpiry",
        ),
        (
            "possession reveal omitted",
            (spawns.replace("state, targetSlot, beforeNodeId, &current, 0", "state, targetSlot, beforeNodeId, &current, 1", 1), state, helper, sidecars),
            "underlying state",
        ),
        (
            "pending slot comparison inverted",
            (
                spawns.replace(
                    "runtime->movementEmoteSlotGenerations[slot]\n                != runtime->behaviorStackRuntime.slots[slot].slotGeneration",
                    "runtime->movementEmoteSlotGenerations[slot]\n                == runtime->behaviorStackRuntime.slots[slot].slotGeneration",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "movementEmoteSlotGenerations",
        ),
        (
            "pending object comparison inverted",
            (
                spawns.replace(
                    "runtime->movementPendingObjectGenerations[slot]\n                != runtime->movementObjectGenerations[slot]",
                    "runtime->movementPendingObjectGenerations[slot]\n                == runtime->movementObjectGenerations[slot]",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "movementPendingObjectGenerations",
        ),
        (
            "capture status inverted",
            (
                spawns.replace(
                    "status = OverworldWildRuntime_CaptureCommandOrigin(\n        &runtime->behaviorStackRuntime, &runtime->movementCommandOrigins,\n        slot, slotGeneration, &identity);\n    if (status != OW_WILD_RUNTIME_STATUS_OK)",
                    "status = OverworldWildRuntime_CaptureCommandOrigin(\n        &runtime->behaviorStackRuntime, &runtime->movementCommandOrigins,\n        slot, slotGeneration, &identity);\n    if (status == OW_WILD_RUNTIME_STATUS_OK)",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "exact OK status",
        ),
        (
            "capture object identity cleared",
            (
                spawns.replace(
                    "identity.objectGeneration = runtime->movementObjectGenerations[slot];",
                    "identity.objectGeneration = 0;",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "current object generation",
        ),
        (
            "capture stamina identity cleared",
            (
                spawns.replace(
                    "identity.staminaPolicyGeneration = effective.effectiveGeneration;",
                    "identity.staminaPolicyGeneration = 0;",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "current stamina policy generation",
        ),
        (
            "consume object identity cleared",
            (
                spawns.replace(
                    "identity.commandSerial = runtime->movementCommandSerials[slot];\n"
                    "    identity.objectGeneration = runtime->movementObjectGenerations[slot];",
                    "identity.commandSerial = runtime->movementCommandSerials[slot];\n"
                    "    identity.objectGeneration = 0;",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "current object generation",
        ),
        (
            "slot cleanup guard removed",
            (
                spawns.replace(
                    "if (!OverworldWildSpawns_ClearThrowStateForSlot(state, slot))\n        return FALSE;",
                    "(void)OverworldWildSpawns_ClearThrowStateForSlot(state, slot);",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "invalidation precedes possession cleanup",
        ),
        (
            "possession handle authentication changed",
            (
                spawns.replace(
                    "relation->possessionHandle.slotGeneration,\n            transition.ownerId,",
                    "runtime->behaviorStackRuntime.slots[targetSlot].slotGeneration,\n            transition.ownerId,",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "authenticate commit/handle identity",
        ),
        (
            "throw relation forgotten before stack cleanup",
            (
                spawns.replace(
                    "restoreMask = helperEntry->clearPickupThrowState(",
                    "OverworldWildSpawns_ForgetPickupRelation(runtime, slot);\n    restoreMask = helperEntry->clearPickupThrowState(",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "forgets/normalizes relation before stack removal",
        ),
        (
            "direct presentation field access",
            (
                spawns.replace(
                    "OverworldWildSpawns_GetMovementPresentationState(state, slot)",
                    "state->movementPresentationStates[slot]",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "bypasses the typed presentation API",
        ),
        (
            "numeric presentation comparison",
            (
                spawns.replace(
                    "== OW_WILD_MOVEMENT_PRESENTATION_SPOT_EMOTE",
                    "== 1",
                    1,
                ),
                state,
                helper,
                sidecars,
            ),
            "compares presentation state numerically",
        ),
    )
    for name, sources, expected in mutations:
        issues = MODULE.verify_sources(*sources)
        require(any(expected in issue for issue in issues), f"{name} mutation was accepted: {issues}")
        checks += 1
    print(f"live runtime integration fixtures: {checks} checks green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
