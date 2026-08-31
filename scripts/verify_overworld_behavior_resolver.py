#!/usr/bin/env python3
"""Verify the portable overworld behavior resolver against golden requests."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


PROFILE_SIZE = 72
PROFILE_FIELD_OFFSETS = {
    "chillState": 0,
    "stamina": 5,
    "restTime": 6,
    "chillSpeed": 7,
    "chainPauseAction": 31,
    "walkPause": 68,
}
LANE_OFFSETS = {"owner": 0, "active": PROFILE_SIZE, "tired": PROFILE_SIZE * 2}
PRIMITIVE_FIELD_OFFSETS = {
    "spawnLocomotion": 0,
    "chillLocomotion": 1,
    "chillTarget": 2,
    "alertLogic": 3,
    "alertReaction": 4,
    "attentiveLocomotion": 5,
    "attentiveTarget": 6,
    "activeReaction": 7,
    "tiredLocomotion": 8,
    "tiredTarget": 9,
    "tiredReaction": 10,
}
EXACT_KEYS = (
    "status",
    "behaviorClass",
    "behaviorLimitKey",
    "speciesClassRuleIndex",
    "matchedClassRuleMask",
    "matchedOverrideMask",
    "forcedOverrideMask",
    "conditionalOverrideMask",
    "appliedOverrideMask",
    "fingerprint",
)


def _load_adapter(root: Path) -> Any:
    path = root / "tools/overworld-viewer-v2/native_resolver.py"
    specification = importlib.util.spec_from_file_location(
        "overworld_behavior_native_resolver",
        path,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load native resolver adapter: {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        value = json.load(source)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _profile_bytes(result: dict[str, Any]) -> bytes:
    encoded = result.get("profileHex")
    if not isinstance(encoded, str):
        raise AssertionError("profileHex is missing")
    try:
        profile = bytes.fromhex(encoded)
    except ValueError as error:
        raise AssertionError("profileHex is not hexadecimal") from error
    if len(profile) != PROFILE_SIZE * 3:
        raise AssertionError(
            f"profileHex has {len(profile)} bytes; expected {PROFILE_SIZE * 3}"
        )
    return profile


def _assert_field(profile: bytes, name: str, expected: int) -> None:
    try:
        lane, field = name.split(".", 1)
        offset = LANE_OFFSETS[lane] + PROFILE_FIELD_OFFSETS[field]
    except (KeyError, ValueError) as error:
        raise AssertionError(f"golden vector uses unknown profile field: {name}") from error
    actual = profile[offset]
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")


def _primitive_bytes(result: dict[str, Any]) -> bytes:
    encoded = result.get("primitivesHex")
    if not isinstance(encoded, str):
        raise AssertionError("primitivesHex is missing")
    try:
        primitives = bytes.fromhex(encoded)
    except ValueError as error:
        raise AssertionError("primitivesHex is not hexadecimal") from error
    if len(primitives) != len(PRIMITIVE_FIELD_OFFSETS):
        raise AssertionError(
            "primitivesHex has "
            f"{len(primitives)} bytes; expected {len(PRIMITIVE_FIELD_OFFSETS)}"
        )
    return primitives


def _trace_step_matches(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    for key in ("lane", "kind", "sourceIndex"):
        if key in expected and actual.get(key) != expected[key]:
            return False
    required_flags = expected.get("requiredFlags")
    return required_flags is None or actual.get("flags", 0) & required_flags == required_flags


def _verify_result(result: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in EXACT_KEYS:
        if key in expected and result.get(key) != expected[key]:
            raise AssertionError(f"{key}: expected {expected[key]}, got {result.get(key)}")
    for key in ("Matched", "Applied"):
        expected_key = f"required{key}OverrideMask"
        if expected_key not in expected:
            continue
        actual_key = f"{key.lower()}OverrideMask"
        required = expected[expected_key]
        actual = result.get(actual_key, 0)
        if actual & required != required:
            raise AssertionError(
                f"{actual_key}: expected bits 0x{required:08x}, got 0x{actual:08x}"
            )
    profile = _profile_bytes(result)
    for field, value in expected.get("profileFields", {}).items():
        _assert_field(profile, field, value)
    primitives = _primitive_bytes(result)
    for field, value in expected.get("primitiveFields", {}).items():
        if field not in PRIMITIVE_FIELD_OFFSETS:
            raise AssertionError(f"golden vector uses unknown primitive: {field}")
        actual = primitives[PRIMITIVE_FIELD_OFFSETS[field]]
        if actual != value:
            raise AssertionError(f"{field}: expected {value}, got {actual}")
    trace = result.get("trace")
    if not isinstance(trace, list):
        raise AssertionError("trace is missing")
    if result.get("traceDropped") != 0:
        raise AssertionError(f"trace dropped {result.get('traceDropped')} steps")
    trace_cursor = 0
    for required_step in expected.get("traceContains", []):
        match_index = next(
            (
                index
                for index in range(trace_cursor, len(trace))
                if isinstance(trace[index], dict)
                and _trace_step_matches(trace[index], required_step)
            ),
            None,
        )
        if match_index is None:
            raise AssertionError(f"trace step is missing: {required_step}")
        trace_cursor = match_index + 1
    if result.get("fingerprint", 0) == 0:
        raise AssertionError("fingerprint is zero")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--blob",
        type=Path,
        help="compact behavior blob (default: build/OverworldWildBehaviorData.bin)",
    )
    parser.add_argument(
        "--golden",
        type=Path,
        help="golden vector file",
    )
    parser.add_argument("--force-host-build", action="store_true")
    arguments = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    blob = (arguments.blob or root / "build/OverworldWildBehaviorData.bin").resolve()
    golden_path = (
        arguments.golden
        or root / "tools/overworld/native/behavior_resolver_golden.json"
    ).resolve()
    if not blob.is_file():
        parser.error(f"behavior blob does not exist: {blob}")
    corpus = _load_json(golden_path)
    if corpus.get("blobVersion") != 72:
        parser.error("golden vectors do not target behavior blob v72")
    vectors = corpus.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        parser.error("golden vector file has no vectors")

    adapter = _load_adapter(root)
    executable = adapter.build(root, force=arguments.force_host_build)
    failures: list[str] = []
    for vector in vectors:
        name = vector.get("name", "unnamed")
        try:
            first = adapter.resolve(
                blob,
                vector["request"],
                root=root,
                executable=executable,
            )
            second = adapter.resolve(
                blob,
                vector["request"],
                root=root,
                executable=executable,
            )
            if first != second:
                raise AssertionError("the same request produced different output")
            _verify_result(first, vector["expected"])
        except (AssertionError, KeyError, TypeError, ValueError, RuntimeError) as error:
            failures.append(f"{name}: {error}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print(f"PASS {len(vectors)} behavior resolver golden vectors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
