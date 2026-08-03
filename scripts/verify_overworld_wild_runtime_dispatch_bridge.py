#!/usr/bin/env python3
"""Focused source gate for the spawn overlay's runtime transition bridge."""

from pathlib import Path
import re


SOURCE = Path(__file__).resolve().parents[1] / (
    "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)


def function_body(source: str, name: str) -> str:
    match = re.search(
        r"static\s+[^;{}]*\b" + re.escape(name)
        + r"\s*\([^;{}]*\)\s*\{",
        source,
    )
    if match is None:
        raise SystemExit(f"missing function: {name}")
    brace = match.end() - 1
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:index + 1]
    raise SystemExit(f"unterminated function: {name}")


def require_order(body: str, labels: tuple[tuple[str, str], ...]) -> None:
    previous = -1
    for label, needle in labels:
        current = body.find(needle, previous + 1)
        if current < 0:
            raise SystemExit(f"missing {label}")
        if current <= previous:
            raise SystemExit(f"misordered {label}")
        previous = current


source = SOURCE.read_text()
dispatch = function_body(
    source, "OverworldWildSpawns_TryDispatchRuntimeTransition"
)
require_order(dispatch, (
    ("DATA_BUSY branch", "status == OW_WILD_RUNTIME_STATUS_DATA_BUSY"),
    ("alert-local busy retry", "trigger == OWBD_TRIGGER_ALERT_COMPLETE"),
    ("alert busy return", "return FALSE;"),
    ("generic pending assignment",
     "runtime->movementPendingRuntimeTransitions[slot] = trigger"),
))

reconcile = function_body(
    source, "OverworldWildSpawns_ReconcileRuntimeEffectiveEntry"
)
require_order(reconcile, (
    ("effective projection", "OverworldWildSpawns_ProjectRuntimeEffectiveBehavior"),
    ("RESET_ACTIVE_STEPS action", "OWBD_ACTION_RESET_ACTIVE_STEPS"),
    ("active-step reset", "state->movementActiveSteps[slot] = 0"),
    ("same-node presentation gate", "if (!entered) return TRUE;"),
    ("attentive entry presentation", "OverworldWildSpawns_PresentRuntimeAttentiveState"),
))

tick = function_body(source, "OverworldWildSpawns_TickSpotEmote")
require_order(tick, (
    ("alert completion dispatch", "OWBD_TRIGGER_ALERT_COMPLETE"),
    ("busy presentation retry", "return TRUE;"),
    ("single completion cleanup", "OverworldWildSpawns_CancelSpotEmotePresentation"),
    ("typed presentation token clear",
     "OverworldWildSpawns_SetMovementPresentationState"),
))

print("runtime dispatch bridge: same-node actions and alert retry ownership verified")
