#!/usr/bin/env python3
"""Verify that hop emotes never pass packed look plans as directions."""

from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
SOURCE = (
    REPO
    / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^static[^\n]*\b{re.escape(name)}\s*\([^;]*?\)\s*\{{",
        source,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise SystemExit(f"missing function body: {name}")
    opening = source.find("{", match.start())
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
    raise SystemExit(f"unterminated function body: {name}")


def main() -> int:
    source = SOURCE.read_text()
    for name in (
        "OverworldWildSpawns_TryStartSpotEmote",
        "OverworldWildSpawns_TryStartManualHopEmote",
    ):
        body = function_body(source, name)
        if "buildLookPlan(direction)" in body:
            raise SystemExit(
                f"{name} packs a look plan into a cardinal hop direction"
            )
        if "state->movementEmoteDirections[slot] = direction;" not in body:
            raise SystemExit(f"{name} does not store its checked direction")

    chain = function_body(
        source,
        "OverworldWildSpawns_TryStartChainPauseAction",
    )
    if "buildLookPlan(direction)" not in chain:
        raise SystemExit("chain Look Around no longer stores its packed plan")

    start_step = function_body(
        source,
        "OverworldWildSpawns_StartNextSpotEmoteStep",
    )
    if "state->movementEmoteDirections[slot]" not in start_step:
        raise SystemExit("hop emote no longer consumes the stored direction")

    print("overworld wild hop-emote cardinal directions verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
