#!/usr/bin/env python3
"""Compile and run the shared exact-frame Walk timing policy."""

from __future__ import annotations

import argparse
import struct
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
    static const u8 fixedInput[] = { 20, 17, 14, 11, 8, 5, 2 };
    static const u8 fixedOutput[] = { 17, 14, 11, 8, 5, 2, 1 };
    unsigned int index;

    CHECK(OVERWORLD_WALK_TIMING_MIN == 1);
    CHECK(OVERWORLD_WALK_TIMING_MAX == 32);
    CHECK(OverworldWalkTimingPolicy_Clamp(0) == 1);
    CHECK(OverworldWalkTimingPolicy_Clamp(33) == 32);
    for (index = 0; index < sizeof(accelerationInput); index++) {
        CHECK(OverworldWalkTimingPolicy_Accelerate(
            accelerationInput[index], 1, OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2)
            == accelerationOutput[index]);
    }
    CHECK(OverworldWalkTimingPolicy_Accelerate(5, 4, 0) == 5);
    CHECK(OverworldWalkTimingPolicy_Accelerate(
        5, 4, OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2) == 4);
    CHECK(OverworldWalkTimingPolicy_Accelerate(
        4, 4, OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2) == 4);
    for (index = 0; index < sizeof(fixedInput); index++) {
        CHECK(OverworldWalkTimingPolicy_Accelerate(
            fixedInput[index], 1, 3) == fixedOutput[index]);
    }
    CHECK(OverworldWalkTimingPolicy_Accelerate(5, 4, 3) == 4);
    CHECK(OverworldWalkTimingPolicy_Accelerate(2, 1, 32) == 1);
    CHECK(OverworldWalkTimingPolicy_Decelerate(3, 20,
        OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2) == 5);
    CHECK(OverworldWalkTimingPolicy_Decelerate(8, 20,
        OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2) == 10);
    CHECK(OverworldWalkTimingPolicy_Decelerate(8, 20, 3) == 11);
    CHECK(OverworldWalkTimingPolicy_Decelerate(19, 20, 3) == 20);
    CHECK(OverworldWalkTimingPolicy_Decelerate(5, 20, 0) == 5);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(32) == 0);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(7) == 0);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(6) == 1);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(5) == 1);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(4) == 2);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(3) == 2);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(2) == 2);
    CHECK(OverworldWalkTimingPolicy_SkidTiles(1) == 4);
    CHECK(OverworldWalkTimingPolicy_SkidTime(20) == 32);
    CHECK(OverworldWalkTimingPolicy_SkidTime(5) == 10);
    CHECK(OverworldWalkTimingPolicy_SkidTime(1) == 2);

    CHECK(!OverworldWalkTimingPolicy_StompApplies(1, 0));
    CHECK(OverworldWalkTimingPolicy_StompApplies(4, 4));
    CHECK(OverworldWalkTimingPolicy_StompApplies(2, 4));
    CHECK(!OverworldWalkTimingPolicy_StompApplies(5, 4));
    CHECK(OverworldWalkTimingPolicy_ResumeAfterSkid(2, 8,
        OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2, FALSE) == 4);
    CHECK(OverworldWalkTimingPolicy_ResumeAfterSkid(2, 8,
        OVERWORLD_WALK_ACCELERATION_DIVIDE_BY_2, TRUE) == 8);

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
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(67, 0));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(67, 32));
    CHECK(OverworldWalkTimingPolicy_ValidateExactOverrideValue(67, 33));
    CHECK(!OverworldWalkTimingPolicy_ValidateExactOverrideValue(67, 34));

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
    CHECK(OverworldWalkDirectionPolicy_ApplyStartResult(
        OVERWORLD_WALK_DIRECTION_NORTH,
        OVERWORLD_WALK_DIRECTION_EAST,
        FALSE) == OVERWORLD_WALK_DIRECTION_NORTH);
    CHECK(OverworldWalkDirectionPolicy_ApplyStartResult(
        OVERWORLD_WALK_DIRECTION_NORTH,
        OVERWORLD_WALK_DIRECTION_EAST,
        TRUE) == OVERWORLD_WALK_DIRECTION_EAST);
    return 0;
}
"""


def _subtract_flags(left: int, right: int) -> tuple[bool, bool]:
    result = (left - right) & 0xFFFFFFFF
    return result == 0, left >= right


def execute_thumb_acceleration(code: bytes, time: int, fastest: int, step: int) -> int:
    """Execute the small Thumb-1 helper from its compiled product section."""
    registers = [time, fastest, step, 0, 0, 0, 0, 0]
    pc = 0
    zero = False
    carry = False
    for _ in range(64):
        if pc + 2 > len(code):
            raise AssertionError("compiled acceleration helper left its section")
        instruction = struct.unpack_from("<H", code, pc)[0]
        next_pc = pc + 2
        if instruction == 0x4770:  # bx lr
            return registers[0] & 0xFF
        if instruction & 0xF800 == 0x2800:  # cmp Rn, #imm8
            register = (instruction >> 8) & 7
            zero, carry = _subtract_flags(registers[register], instruction & 0xFF)
        elif instruction & 0xF800 == 0x2000:  # movs Rd, #imm8
            register = (instruction >> 8) & 7
            registers[register] = instruction & 0xFF
            zero = registers[register] == 0
        elif instruction & 0xF800 == 0x3000:  # adds Rdn, #imm8
            register = (instruction >> 8) & 7
            total = registers[register] + (instruction & 0xFF)
            registers[register] = total & 0xFFFFFFFF
            zero = registers[register] == 0
            carry = total > 0xFFFFFFFF
        elif instruction & 0xF800 == 0x0800:  # lsrs Rd, Rm, #imm5
            shift = (instruction >> 6) & 0x1F
            source = (instruction >> 3) & 7
            destination = instruction & 7
            if shift == 0:
                shift = 32
            carry = bool((registers[source] >> (shift - 1)) & 1)
            registers[destination] = registers[source] >> shift
            zero = registers[destination] == 0
        elif instruction & 0xFFC0 == 0x4280:  # cmp Rdn, Rm
            left = instruction & 7
            right = (instruction >> 3) & 7
            zero, carry = _subtract_flags(registers[left], registers[right])
        elif instruction & 0xFE00 == 0x1A00:  # subs Rd, Rn, Rm
            destination = instruction & 7
            left = (instruction >> 3) & 7
            right = (instruction >> 6) & 7
            zero, carry = _subtract_flags(registers[left], registers[right])
            registers[destination] = (
                registers[left] - registers[right]
            ) & 0xFFFFFFFF
        elif instruction & 0xF800 == 0x0000:  # lsls/movs Rd, Rm, #0
            shift = (instruction >> 6) & 0x1F
            if shift != 0:
                raise AssertionError("unexpected compiled left shift")
            source = (instruction >> 3) & 7
            destination = instruction & 7
            registers[destination] = registers[source]
            zero = registers[destination] == 0
        elif instruction & 0xF000 == 0xD000:  # conditional branch
            condition = (instruction >> 8) & 0xF
            take = {
                0x0: zero,
                0x1: not zero,
                0x2: carry,
                0x8: carry and not zero,
                0x9: not carry or zero,
            }.get(condition)
            if take is None:
                raise AssertionError(f"unexpected compiled condition {condition:#x}")
            if take:
                offset = instruction & 0xFF
                if offset & 0x80:
                    offset -= 0x100
                next_pc = pc + 4 + offset * 2
        elif instruction & 0xF800 == 0xE000:  # unconditional branch
            offset = instruction & 0x7FF
            if offset & 0x400:
                offset -= 0x800
            next_pc = pc + 4 + offset * 2
        else:
            raise AssertionError(f"unexpected Thumb instruction {instruction:#06x}")
        pc = next_pc
    raise AssertionError("compiled acceleration helper did not return")


def verify_compiled_thumb_acceleration(path: Path, objcopy: str) -> None:
    cases = (
        (20, 1, 0, 20), (5, 4, 0, 5),
        (20, 1, 33, 10), (10, 1, 33, 5), (5, 1, 33, 3),
        (3, 1, 33, 2), (2, 1, 33, 1),
        (20, 1, 3, 17), (17, 1, 3, 14), (14, 1, 3, 11),
        (11, 1, 3, 8), (8, 1, 3, 5), (5, 1, 3, 2),
        (2, 1, 3, 1), (5, 4, 3, 4), (2, 1, 32, 1),
        (0, 0, 0, 1), (33, 1, 33, 16),
    )
    with tempfile.TemporaryDirectory(prefix="walk-thumb-timing-") as temp:
        binary = Path(temp) / "accelerate.bin"
        subprocess.run(
            [
                objcopy,
                "-O", "binary",
                "--only-section=.overworld_walk_accelerate_time",
                str(path), str(binary),
            ],
            check=True,
        )
        code = binary.read_bytes()
    if not code or len(code) > 56:
        raise AssertionError(f"compiled acceleration helper has invalid size {len(code)}")
    for time, fastest, step, expected in cases:
        actual = execute_thumb_acceleration(code, time, fastest, step)
        if actual != expected:
            raise AssertionError(
                f"compiled acceleration helper ({time}, {fastest}, {step}) "
                f"returned {actual}, expected {expected}"
            )
    print(f"compiled Thumb acceleration helper verified ({len(code)} of 56 bytes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cc", default="cc")
    parser.add_argument(
        "--runtime-source",
        type=Path,
        default=REPO
        / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c",
    )
    parser.add_argument(
        "--walk-module-object",
        type=Path,
        help="execute the compiled Thumb acceleration helper from this object",
    )
    parser.add_argument("--arm-objcopy", default="arm-none-eabi-objcopy")
    args = parser.parse_args()

    if args.walk_module_object is not None:
        verify_compiled_thumb_acceleration(
            args.walk_module_object,
            args.arm_objcopy,
        )

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
        "OverworldWalk_ClampTime(",
        "OverworldWalk_AccelerateTime(",
        "OverworldWalk_SkidTiles(",
        "OverworldWalk_SkidTime(",
    )
    missing = [call for call in required_runtime_calls if call not in runtime_source]
    if missing:
        raise SystemExit(
            "runtime momentum does not use the shared Walk policy: "
            + ", ".join(missing)
        )
    if "OVERWORLD_WALK_MODULE_ENTRY" in runtime_source:
        raise SystemExit("runtime momentum still calls the retired Walk table")
    if "call->lane->walkAccelerationStep" not in runtime_source:
        raise SystemExit("runtime momentum does not use the resolved acceleration amount")
    if "#define OVERWORLD_WILD_RUNTIME_VERSION 17" not in runtime_header:
        raise SystemExit("runtime Walk ABI version was not advanced")
    if "expected_header = (0x3152574F, 17, expected_entry_size)" \
            not in packager_source:
        raise SystemExit("ROM packager expects a stale runtime Walk ABI version")

    print("exact-frame Walk timing policy verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
