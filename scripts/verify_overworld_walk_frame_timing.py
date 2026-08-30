#!/usr/bin/env python3
"""Compile and run the shared exact-frame Walk timing policy."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

POLICY_TEST = r"""
#include "overworld_walk_timing_policy.h"
#include "overworld_walk_direction_policy.h"

#define CHECK(condition) do { if (!(condition)) return __LINE__; } while (0)

int main(void)
{
    static const u8 accelerationInput[] = { 20, 10, 5, 3, 2 };
    static const u8 accelerationOutput[] = { 10, 5, 3, 2, 1 };
    unsigned int index;

    CHECK(OVERWORLD_WALK_TIMING_MIN == 1);
    CHECK(OVERWORLD_WALK_TIMING_MAX == 32);
    CHECK(OverworldWalkTimingPolicy_Clamp(0) == 1);
    CHECK(OverworldWalkTimingPolicy_Clamp(33) == 32);
    for (index = 0; index < sizeof(accelerationInput); index++) {
        CHECK(OverworldWalkTimingPolicy_Accelerate(
            accelerationInput[index], 1) == accelerationOutput[index]);
    }
    CHECK(OverworldWalkTimingPolicy_Accelerate(5, 4) == 4);
    CHECK(OverworldWalkTimingPolicy_Accelerate(4, 4) == 4);

    CHECK(OverworldWalkTimingPolicy_SkidTiles(32) == 0);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(5) == 0);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(4) == 1);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(3) == 1);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(2) == 2);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(1) == 4);
    CHECK(OverworldWalkTimingPolicy_SkidTime(20) == 32);
    CHECK(OverworldWalkTimingPolicy_SkidTime(5) == 10);
    CHECK(OverworldWalkTimingPolicy_SkidTime(1) == 2);

    CHECK(!OverworldWalkTimingPolicy_StompApplies(1, 0));
    CHECK(OverworldWalkTimingPolicy_StompApplies(4, 4));
    CHECK(OverworldWalkTimingPolicy_StompApplies(2, 4));
    CHECK(!OverworldWalkTimingPolicy_StompApplies(5, 4));

    CHECK(!OverworldWalkTimingPolicy_ValidateExactOverrideValue(7, 0));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(7, 32));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(36, 0));
    CHECK(!OverworldWalkTimingPolicy_ValidateExactOverrideValue(36, 33));
    CHECK(!OverworldWalkTimingPolicy_ValidateExactOverrideValue(49, 0));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(49, 32));
    CHECK(!OverworldWalkTimingPolicy_ValidateExactOverrideValue(56, 0));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(56, 32));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(66, 0));
    CHECK(!OverworldWalkTimingPolicy_ValidateExactOverrideValue(66, 33));

    CHECK(OverworldWalkDirectionPolicy_FromKeys(PAD_KEY_UP)
        == OVERWORLD_WALK_DIRECTION_NORTH);
    CHECK(OverworldWalkDirectionPolicy_FromKeys(PAD_KEY_UP | PAD_KEY_LEFT)
        == OVERWORLD_WALK_DIRECTION_NORTH_WEST);
    CHECK(OverworldWalkDirectionPolicy_FromKeys(PAD_KEY_DOWN | PAD_KEY_RIGHT)
        == OVERWORLD_WALK_DIRECTION_SOUTH_EAST);
    CHECK(OverworldWalkDirectionPolicy_FromKeys(PAD_KEY_UP | PAD_KEY_DOWN)
        == OVERWORLD_WALK_DIRECTION_NONE);
    CHECK(OverworldWalkDirectionPolicy_FromDelta(-3, -1)
        == OVERWORLD_WALK_DIRECTION_NORTH_WEST);
    CHECK(OverworldWalkDirectionPolicy_FromDelta(4, 0)
        == OVERWORLD_WALK_DIRECTION_EAST);
    CHECK(OverworldWalkDirectionPolicy_DeltaX(
        OVERWORLD_WALK_DIRECTION_SOUTH_WEST) == -1);
    CHECK(OverworldWalkDirectionPolicy_DeltaY(
        OVERWORLD_WALK_DIRECTION_NORTH_EAST) == -1);
    CHECK(OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn(
        OVERWORLD_WALK_DIRECTION_NORTH,
        OVERWORLD_WALK_DIRECTION_NORTH_EAST));
    CHECK(!OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn(
        OVERWORLD_WALK_DIRECTION_NORTH,
        OVERWORLD_WALK_DIRECTION_EAST));
    CHECK(!OverworldWalkDirectionPolicy_IsFortyFiveDegreeTurn(
        OVERWORLD_WALK_DIRECTION_NORTH_EAST,
        OVERWORLD_WALK_DIRECTION_SOUTH_WEST));
    return 0;
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", default="cc")
    parser.add_argument(
        "--runtime-source",
        type=Path,
        default=REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="walk-frame-timing-") as temp:
        temp_path = Path(temp)
        source_path = temp_path / "walk_frame_timing_test.c"
        binary_path = temp_path / "walk_frame_timing_test"
        source_path.write_text(POLICY_TEST)
        subprocess.run(
            [
                args.cc,
                "-std=c99",
                "-Wno-unknown-attributes",
                "-Wno-incompatible-library-redeclaration",
                f"-I{REPO / 'include'}",
                str(source_path),
                "-o",
                str(binary_path),
            ],
            check=True,
        )
        subprocess.run([str(binary_path)], check=True)

    runtime_source = args.runtime_source.read_text()
    runtime_header = (REPO / "include/overworld_wild_runtime.h").read_text()
    packager_source = (REPO / "scripts/make.py").read_text()
    required_runtime_calls = (
        "OVERWORLD_WALK_MODULE_ENTRY->clampTime(",
        "OVERWORLD_WALK_MODULE_ENTRY->accelerateTime(",
        "OVERWORLD_WALK_MODULE_ENTRY->skidTiles(",
        "OVERWORLD_WALK_MODULE_ENTRY->skidTime(",
    )
    missing = [call for call in required_runtime_calls if call not in runtime_source]
    if missing:
        raise SystemExit(
            "runtime momentum does not use the shared Walk policy: "
            + ", ".join(missing)
        )
    if "#define OVERWORLD_WILD_RUNTIME_VERSION 9" not in runtime_header:
        raise SystemExit("runtime Walk ABI version was not advanced")
    if "expected_header = (0x3152574F, 9, expected_entry_size)" \
            not in packager_source:
        raise SystemExit("ROM packager expects a stale runtime Walk ABI version")

    print("exact-frame Walk timing policy verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
