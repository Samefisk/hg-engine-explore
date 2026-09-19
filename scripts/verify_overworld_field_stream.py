#!/usr/bin/env python3
"""S1 witness for the Field-owned terrain adapter's resident code move.

Compile the complete production service body and Field wrapper. Only includes,
deployment sections, and engine boundary objects are adapted for the host.
This does not prove ARM packaging, map loading, or visible game behavior.
"""

from pathlib import Path
import re

from verify_overworld_actor_view import execute


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "src/pokemon_move_history_overlay/overworld_field_terrain_stream.c"
FIXTURE = ROOT / "tools/overworld/fixtures/field_stream_harness.c"


def between(source: str, first: str, last: str) -> str:
    start = source.index(first)
    finish = source.index(last, start) + len(last)
    return source[start:finish]


def function(source: str, name: str) -> str:
    match = re.search(
        r"^OverworldFieldTerrainStreamResult\s+(?:__attribute__\(\([^\n]+\)\)\s+)?"
        + re.escape(name)
        + r"\(",
        source,
        re.M,
    )
    if match is None:
        raise ValueError("missing Field stream wrapper: " + name)
    brace = source.index("{", match.start())
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    result = source[match.start():end]
    return re.sub(r"\n__attribute__\(\([^\n]+\)\)", "", result, count=1)


def harness_source() -> str:
    public = (ROOT / "include/map_teleport.h").read_text()
    internal = (ROOT / "include/overworld_field_terrain_internal.h").read_text()
    actor = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    wrapper = (ROOT / "src/field/map_teleport.c").read_text()
    product = PRODUCT.read_text()
    product = re.sub(r'^#include "[^"\n]+"\n', "", product, flags=re.M)
    product = product.replace(
        '#define FIELD_STREAM_CODE \\\n    __attribute__((section(".overworld_field_terrain_stream_code")))',
        '#define FIELD_STREAM_CODE',
    ).replace(
        '__attribute__((noinline, used, section(".overworld_field_terrain_stream_entry")))', "",
    )
    if "__attribute__" in product:
        raise ValueError("unrecognized deployment attribute in Field stream host input")
    substitutions = {
        "/* @CALL_TYPES@ */": between(public,
            "#define OVERWORLD_FIELD_TERRAIN_STREAM_CALL_VERSION", "} OverworldFieldTerrainStreamCall;"),
        "/* @RUNTIME_TYPE@ */": between(internal,
            "typedef struct OverworldFieldTerrainStreamRuntime", "} OverworldFieldTerrainStreamRuntime;"),
        "/* @COMPATIBILITY_TYPES@ */": between(actor,
            "typedef OverworldActorResult (*OverworldActorCompatibilityBindFunc)", "} OverworldActorCompatibilityEntry;"),
        "/* @PRODUCT_SERVICE@ */": product,
        "/* @FIELD_WRAPPER@ */": function(
            wrapper, "OverworldFieldService_TerrainStream"),
    }
    result = FIXTURE.read_text()
    for marker, replacement in substitutions.items():
        if result.count(marker) != 1:
            raise ValueError(f"Field stream fixture marker differs: {marker}")
        result = result.replace(marker, replacement)
    return result


def main() -> int:
    source = harness_source()
    baseline = execute(source)
    if baseline.returncode:
        print(baseline.stdout + baseline.stderr, end="")
        return 1
    print(baseline.stdout, end="")
    mutants = {
        "wrong motion token": (
            "call->motionIdentity\n            == runtime->motionIdentity", "call->motionIdentity != 0"),
        "two-tile anchor advance": (
            "? 0x10000\n                : -0x10000", "? 0x20000\n                : -0x10000"),
        "ignoring sampled X": (
            "== runtime->watchedAnchor.x", "== *(s32 *)((u8 *)manager + 0xD0)"),
        "missing terminal ready": (
            "return OVERWORLD_FIELD_TERRAIN_STREAM_READY;", "return OVERWORLD_FIELD_TERRAIN_STREAM_WAITING;"),
    }
    for label, (old, new) in mutants.items():
        if old not in source:
            raise ValueError(f"Field stream mutation seam changed: {label}")
        result = execute(source.replace(old, new, 1))
        if result.returncode != 1 or "field stream invariant failed" not in result.stderr:
            raise RuntimeError(f"known-bad Field stream did not fail its assertion: {label}")
        print(f"PASS known-bad Field stream rejected: {label}")
    print("PASS S1 Field stream boundary contract; no ROM/gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
