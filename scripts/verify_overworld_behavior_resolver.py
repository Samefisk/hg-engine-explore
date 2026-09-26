#!/usr/bin/env python3
"""Verify the portable overworld behavior resolver against golden requests."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


PROFILE_SIZE = 72
PROFILE_FIELD_OFFSETS = {
    "chillState": 0,
    "visionRange": 1,
    "alertTime": 3,
    "stamina": 5,
    "restTime": 6,
    "chillSpeed": 7,
    "spawnState": 11,
    "chillAction": 12,
    "chillTarget": 13,
    "hopAllowNonCardinal": 19,
    "hopMinDistance": 20,
    "hopMaxDistance": 21,
    "hopPause": 22,
    "overworldLimit": 26,
    "ramAccelerationSteps": 29,
    "ramMaxSpeed": 30,
    "chainPause": 30,
    "chainPauseAction": 31,
    "hopTime": 36,
    "continueWhenArrived": 42,
    "avoidPreviousTile": 43,
    "chainMovementVariance": 44,
    "chainPauseVariance": 45,
    "hopElevationTimeScale": 48,
    "hopElevationArcScale": 49,
    "tilesToAccelerate": 50,
    "maxWalkSpeed": 51,
    "hopAllowVerticalObstacles": 56,
    "chainPauseActionChance": 67,
    "walkOptions": 65,
    "wanderStraightChance": 66,
    "walkPause": 68,
    "walkTimeVariance": 64,
    "walkPauseVariance": 63,
    "tilesBeforeTurnSkid": 69,
    "stopSkid": 69,
    "planTurnSkidPath": 69,
    "walkStompTime": 70,
    "walkAccelerationStep": 71,
    "walkSwayWidth": 46,
}
LANE_OFFSETS = {"owner": 0, "tired": PROFILE_SIZE}
PRIMITIVE_FIELD_OFFSETS = {
    "spawnLocomotion": 0,
    "chillLocomotion": 1,
    "chillTarget": 2,
    "alertLogic": 3,
    "alertReaction": 4,
    "tiredLocomotion": 5,
    "tiredTarget": 6,
    "tiredReaction": 7,
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
    "winningConditionId",
    "targetSourceApplication",
    "resolvedTargetConditionId",
)
PROFILE_SCENARIOS = (
    "profile.resolve.override-order",
    "profile.resolve.follower-mounted-parity",
)


def _verify_shared_source_contract(root: Path) -> None:
    """Prove the ROM and host adapters compile and publish one C resolver."""

    resolver_source = "lib/overworld/overworld_behavior_resolver.c"
    overlays = (root / "overlays.mk").read_text(encoding="utf-8")
    native_adapter = (
        root / "tools/overworld-viewer-v2/native_resolver.py"
    ).read_text(encoding="utf-8")
    actor_adapter = (
        root
        / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
    ).read_text(encoding="utf-8")

    if overlays.count(resolver_source) != 1:
        raise AssertionError(
            "the ROM overlay must compile the canonical resolver source exactly once"
        )
    if f'root / "{resolver_source}"' not in native_adapter:
        raise AssertionError(
            "the Workshop host must compile the canonical resolver source"
        )
    required_exports = (
        "BehaviorResolver_Resolve,",
        "BehaviorResolver_InspectClass,",
    )
    if any(export not in actor_adapter for export in required_exports):
        raise AssertionError(
            "the actor resolver service does not publish the canonical callbacks"
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


def _remove_recorded_rule(source: str, rule_index: int) -> str:
    """Omit one golden-covered rule from the actual portable C resolver."""
    seam = "{\n    BehaviorResolver_ApplyOverride(profile, overrideProfile);\n    result->appliedOverrideMask |= 1u << index;"
    if source.count(seam) != 1:
        raise ValueError("resolver rule-removal source seam differs")
    return source.replace(
        seam,
        "{\n    if (index == " + str(rule_index) + ") { return; }\n"
        "    BehaviorResolver_ApplyOverride(profile, overrideProfile);\n"
        "    result->appliedOverrideMask |= 1u << index;",
        1,
    )


def _application_indexes(root: Path) -> dict[str, int]:
    catalog = _load_json(root / "data/overworld_behavior_profiles.json")
    return {
        application["id"]: index
        for index, application in enumerate(catalog["applications"])
    }


def _select_rule_removal_index(root: Path, vectors: list[dict[str, Any]]) -> int:
    """Choose one golden-covered, unconditional application to mutate."""
    catalog = _load_json(root / "data/overworld_behavior_profiles.json")
    conditional_profiles = {
        profile["id"]
        for profile in catalog["profiles"]
        if profile.get("conditions")
    }
    covered_mask = 0
    for vector in vectors:
        covered_mask |= vector["expected"].get("requiredAppliedOverrideMask", 0)
    for index, application in enumerate(catalog["applications"]):
        if application["profile"] not in conditional_profiles \
                and covered_mask & (1 << index):
            return index
    raise AssertionError("golden vectors cover no unconditional resolver application")


def verify_rule_removal(root, blob, vectors, adapter, executable):
    """A successful mutant execution must fail unchanged golden expectations.

    Build/process/setup exceptions propagate; they are never a rejected rule.
    ROM and Workshop source wiring is checked by the caller. This is a host C
    sensitivity control, not a mutated ROM run or fresh deployment acceptance.
    """
    baseline = adapter.resolve_many(blob, [v["request"] for v in vectors], root=root, executable=executable)
    if len(baseline) != len(vectors):
        raise AssertionError("baseline resolver result count differs")
    for vector, result in zip(vectors, baseline):
        _verify_result(result, vector["expected"])
    rule_index = _select_rule_removal_index(root, vectors)
    source = (root / "lib/overworld/overworld_behavior_resolver.c").read_text()
    changed = _remove_recorded_rule(source, rule_index)
    with tempfile.TemporaryDirectory(prefix="ow-resolver-rule-control-") as directory:
        temporary = Path(directory)
        # All inputs other than this single C body remain the original files.
        for name in ("tools", "scripts", "include", "data"):
            (temporary / name).symlink_to(root / name, target_is_directory=True)
        target = temporary / "lib/overworld/overworld_behavior_resolver.c"
        target.parent.mkdir(parents=True)
        target.write_text(changed)
        mutant = adapter.build(temporary, force=True, output=temporary / "resolver-mutant")
        results = adapter.resolve_many(blob, [v["request"] for v in vectors], root=root, executable=mutant)
    if len(results) != len(vectors):
        raise AssertionError("mutant resolver result count differs")
    rejected = []
    for vector, result in zip(vectors, results):
        if type(result.get("status")) is not int or result["status"] != 0:
            raise AssertionError("rule-removal control did not produce successful resolver output")
        _profile_bytes(result)
        try:
            _verify_result(result, vector["expected"])
        except AssertionError as error:
            rejected.append({"name": vector["name"], "reason": str(error)})
    if not rejected:
        raise AssertionError("removed resolver rule was accepted by unchanged goldens")
    return {"ruleIndex": rule_index, "executedCases": len(results), "rejectedCases": rejected,
            "scope": "actual portable C host sensitivity; not native ROM execution"}


def _profile_bytes(result: dict[str, Any]) -> bytes:
    encoded = result.get("profileHex")
    if not isinstance(encoded, str):
        raise AssertionError("profileHex is missing")
    try:
        profile = bytes.fromhex(encoded)
    except ValueError as error:
        raise AssertionError("profileHex is not hexadecimal") from error
    if len(profile) != PROFILE_SIZE * 2:
        raise AssertionError(
            f"profileHex has {len(profile)} bytes; expected {PROFILE_SIZE * 2}"
        )
    return profile


def _assert_field(profile: bytes, name: str, expected: int) -> None:
    try:
        lane, field = name.split(".", 1)
        offset = LANE_OFFSETS[lane] + PROFILE_FIELD_OFFSETS[field]
    except (KeyError, ValueError) as error:
        raise AssertionError(f"golden vector uses unknown profile field: {name}") from error
    actual = profile[offset]
    if field == "walkPauseVariance":
        actual = (actual & 0xFE) >> 1
    elif field == "walkTimeVariance":
        actual = (actual & 0xFE) >> 1
    elif field == "tilesBeforeTurnSkid":
        actual &= 0x3F
    elif field == "stopSkid":
        actual = 1 if actual & 0x80 else 0
    elif field == "planTurnSkidPath":
        actual = 1 if actual & 0x40 else 0
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
    if "resolvedTarget" in expected \
            and result.get("resolvedTarget") != expected["resolvedTarget"]:
        raise AssertionError(
            "resolvedTarget: expected "
            f"{expected['resolvedTarget']}, got {result.get('resolvedTarget')}"
        )
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


def _find_vector(corpus: dict[str, Any], name: str) -> dict[str, Any]:
    for vector in corpus["vectors"]:
        if vector.get("name") == name:
            return vector
    raise AssertionError(f"resolver golden vector is missing: {name}")


def _run_override_order_scenario(
    adapter: Any,
    executable: Path,
    blob: Path,
    corpus: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    vector = _find_vector(corpus, "conditional-perch-replay")
    application_indexes = _application_indexes(root)
    bird_index = application_indexes["apply-small-bird-hop"]
    perch_index = application_indexes["apply-perch"]
    result = adapter.resolve(
        blob,
        vector["request"],
        root=root,
        executable=executable,
    )
    _verify_result(result, vector["expected"])
    trace = result["trace"]
    lane_orders: dict[str, list[int]] = {}
    for lane in (0, 2):
        steps = [
            (index, step)
            for index, step in enumerate(trace)
            if step.get("lane") == lane
            and (step.get("kind"), step.get("sourceIndex"))
            in ((3, bird_index), (4, perch_index))
        ]
        identities = [
            (step["kind"], step["sourceIndex"])
            for _, step in steps
        ]
        if identities != [(3, bird_index), (4, perch_index)]:
            raise AssertionError(
                f"lane {lane} override order/count is {identities}; "
                f"expected {[(3, bird_index), (4, perch_index)]}"
            )
        if steps[0][1]["profileHex"] == steps[1][1]["profileHex"]:
            raise AssertionError(f"lane {lane} later override made no profile change")
        lane_orders[str(lane)] = [steps[0][0], steps[1][0]]
    return {
        "passed": True,
        "scenario": "profile.resolve.override-order",
        "fingerprint": result["fingerprint"],
        "appliedOverrideMask": result["appliedOverrideMask"],
        "laneTraceOrder": lane_orders,
    }


def _run_follower_mounted_parity_scenario(
    adapter: Any,
    executable: Path,
    blob: Path,
    corpus: dict[str, Any],
    root: Path,
) -> dict[str, Any]:
    vector = _find_vector(corpus, "stantler-sprint-one-frame-acceleration")
    catalog = _load_json(root / "data/overworld_behavior_profiles.json")
    application_indexes = _application_indexes(root)
    follower_index = application_indexes[
        catalog["runtimeBindings"]["followerApplication"]
    ]
    mounted_index = application_indexes[
        catalog["runtimeBindings"]["mountedApplication"]
    ]
    normal_request = dict(vector["request"])
    follower_request = dict(normal_request)
    follower_request["forcedOverrideMask"] = 1 << follower_index
    mounted_request = dict(normal_request)
    mounted_request["forcedOverrideMask"] = 1 << mounted_index
    normal = adapter.resolve(
        blob,
        normal_request,
        root=root,
        executable=executable,
    )
    follower = adapter.resolve(
        blob,
        follower_request,
        root=root,
        executable=executable,
    )
    mounted = adapter.resolve(
        blob,
        mounted_request,
        root=root,
        executable=executable,
    )
    _verify_result(normal, vector["expected"])
    normal_profile = _profile_bytes(normal)
    follower_profile = _profile_bytes(follower)
    mounted_profile = _profile_bytes(mounted)
    for lane in LANE_OFFSETS:
        for field, expected in (
            ("tilesToAccelerate", 1),
            ("maxWalkSpeed", 4),
            ("walkAccelerationStep", 1),
            ("walkTimeVariance", 2),
            ("tilesBeforeTurnSkid", 1),
            ("planTurnSkidPath", 1),
            ("stopSkid", 1),
        ):
            _assert_field(follower_profile, f"{lane}.{field}", expected)
    if mounted_profile != normal_profile:
        raise AssertionError("Mounted changed the selected Sprint Owner profile")
    if follower_profile == normal_profile:
        raise AssertionError("Follower control did not change its own profile")
    if mounted["fingerprint"] in (normal["fingerprint"], follower["fingerprint"]):
        raise AssertionError("Mounted did not produce its own resolved profile")
    if mounted["primitivesHex"] != normal["primitivesHex"]:
        raise AssertionError("Mounted changed Sprint locomotion primitives")
    if mounted["forcedOverrideMask"] != 1 << mounted_index:
        raise AssertionError("Mounted unexpectedly forced the Follower layer")
    waddle_request = dict(_find_vector(corpus, "default-class-and-lanes")["request"])
    waddle_request["species"] = 69  # Bellsprout has authored Waddle sway.
    waddle_mounted_request = dict(waddle_request)
    waddle_mounted_request["forcedOverrideMask"] = 1 << mounted_index
    waddle_follower_request = dict(waddle_request)
    waddle_follower_request["forcedOverrideMask"] = 1 << follower_index
    waddle_normal = adapter.resolve(
        blob, waddle_request, root=root, executable=executable,
    )
    waddle_mounted = adapter.resolve(
        blob, waddle_mounted_request, root=root, executable=executable,
    )
    waddle_follower = adapter.resolve(
        blob, waddle_follower_request, root=root, executable=executable,
    )
    for lane in LANE_OFFSETS:
        _assert_field(_profile_bytes(waddle_normal),
                      f"{lane}.walkSwayWidth", 4)
        _assert_field(_profile_bytes(waddle_follower),
                      f"{lane}.chillSpeed", 8)
    if (_profile_bytes(waddle_mounted) != _profile_bytes(waddle_normal)
            or waddle_mounted["primitivesHex"] != waddle_normal["primitivesHex"]):
        raise AssertionError("Mounted changed the selected Waddle profile")
    request_header = (root / "include/overworld_behavior_resolver.h").read_text()
    request_fields = request_header.split(
        "typedef struct BehaviorResolveRequest {", 1
    )[1].split("} BehaviorResolveRequest;", 1)[0]
    if "role" in request_fields.lower():
        raise AssertionError("resolver request has grown a mount-specific role")
    forced_steps = [
        (step["lane"], step["sourceIndex"])
        for step in mounted["trace"]
        if step.get("kind") == 3
        and step.get("sourceIndex") == mounted_index
        and step.get("flags", 0) & 0x06 == 0x06
    ]
    if forced_steps != [
        (0, mounted_index), (2, mounted_index)
    ]:
        raise AssertionError(
            f"forced Mounted layer was not applied once per lane: {forced_steps}"
        )
    return {
        "passed": True,
        "scenario": "profile.resolve.follower-mounted-parity",
        "sprintFingerprint": normal["fingerprint"],
        "followerFingerprint": follower["fingerprint"],
        "mountedFingerprint": mounted["fingerprint"],
        "forcedOverrideMask": mounted["forcedOverrideMask"],
        "ownerProfileHex": mounted["profileHex"][: PROFILE_SIZE * 2],
        "waddleMountedFingerprint": waddle_mounted["fingerprint"],
    }


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
    parser.add_argument("--rule-removal-control", action="store_true",
                        help="omit one covered unconditional application and require unchanged goldens to reject it")
    parser.add_argument("--profile-case", dest="scenario",
                        choices=PROFILE_SCENARIOS)
    parser.add_argument("--scenario", dest="scenario",
                        choices=PROFILE_SCENARIOS,
                        help=argparse.SUPPRESS)
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
    if corpus.get("blobVersion") != 81:
        parser.error("golden vectors do not target behavior blob v81")
    vectors = corpus.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        parser.error("golden vector file has no vectors")

    adapter = _load_adapter(root)
    _verify_shared_source_contract(root)
    executable = adapter.build(root, force=arguments.force_host_build)
    if arguments.rule_removal_control:
        if arguments.scenario is not None:
            parser.error("rule-removal control uses the full unchanged golden corpus")
        result = verify_rule_removal(root, blob, vectors, adapter, executable)
        print(json.dumps(result, sort_keys=True))
        # Keep the normal single/batch checks below; this control adds coverage.
    if arguments.scenario is not None:
        runners = {
            "profile.resolve.override-order": _run_override_order_scenario,
            "profile.resolve.follower-mounted-parity":
                _run_follower_mounted_parity_scenario,
        }
        try:
            evidence = runners[arguments.scenario](
                adapter,
                executable,
                blob,
                corpus,
                root,
            )
        except (AssertionError, KeyError, TypeError, ValueError, RuntimeError) as error:
            print(json.dumps({
                "passed": False,
                "scenario": arguments.scenario,
                "error": str(error),
            }))
            return 1
        print(json.dumps(evidence, sort_keys=True))
        return 0
    try:
        batch_results = adapter.resolve_many(
            blob,
            [vector["request"] for vector in vectors],
            root=root,
            executable=executable,
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as error:
        print(f"FAIL batch resolver: {error}", file=sys.stderr)
        return 1
    failures: list[str] = []
    for vector, batch_result in zip(vectors, batch_results):
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
            if first != batch_result:
                raise AssertionError("single and batch Workshop adapters differ")
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
