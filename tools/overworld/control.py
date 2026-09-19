"""Implementation of the ``scripts/owctl`` host facade."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import secrets
import subprocess
import sys
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from tools.overworld.actor_probe import (
    build_evidence_provenance,
    capture_memory_file,
    evaluate_behavior_negative_control,
    evaluate_scenario_evidence,
    evaluate_subject_negative_control,
    load_debug_descriptor,
    load_evidence,
    load_execution_record,
    require_descriptor_identity,
    require_scenario_provenance,
    write_evidence,
)
from tools.overworld.evidence_store import (
    archive_command_output, archive_step, artifact_directory,
    require_command_output, scenario_lock,
)
from tools.overworld.progress import read_manifest, record_resolution, resolution_for, shared_history, summarize
from tools.overworld.devtools_manifest_limits import MANIFEST_MAX_BYTES
from tools.overworld.devtools_evidence_stream import load_observations
from tools.overworld.proof_adapters import get_adapter
from tools.overworld.runs import (
    HEADLESS_PYTHON_FLAGS,
    OVERWORLD_LINKED_OUTPUTS,
    OVERWORLD_PRODUCT_OUTPUTS,
    RUN_SCHEMA,
    digest_value,
    emulator_record,
    file_record,
    headless_python,
    make_run_manifest,
    run_id_for,
    source_record,
    utc_now,
    write_run_manifest,
)
from tools.overworld.trace import decode_trace, filter_events, load_trace_schema
from tools.overworld.validation import (
    PROOF_LEVELS,
    ValidationFailure,
    cross_validate,
    load_feature_manifest,
    load_scenarios,
    validate_runtime_migration,
)


REPO = Path(__file__).resolve().parents[2]
FEATURE_MANIFEST = REPO / "tools/overworld/system_features.yaml"
SCENARIO_DIRECTORY = REPO / "tests/overworld/scenarios"
TRACE_SCHEMA = REPO / "tools/overworld/schemas/semantic-trace-v1.json"
DEBUG_DESCRIPTOR = REPO / "build/overworld-system.debug.json"
REPO_PYTHON = headless_python(REPO)
RUNTIME_PROOF_REGISTRY = json.loads(
    (REPO / "tools/overworld/runtime_proof_registry.json").read_text()
)
RUNTIME_PROOF_LEVELS = frozenset(("S3", "S4", "S5"))
ACTOR_SCOPED_TRACE_GROUPS = frozenset(
    ("actor", "intent", "motion", "presentation", "lifecycle")
)
_PACKAGED_RESOLVER_ORACLE: dict[str, Any] | None = None
_PROOF_INPUT_CONTEXT = ContextVar("overworld_proof_inputs", default=None)
_PENDING_PROOF_CACHE = ContextVar("overworld_pending_proof_cache", default=None)


def _controller_code_revision():
    """Bind loaded host code; never stamp old modules with edited source hashes.

    Workshop already guards requests from its startup revision. This check
    also catches edits during a running job and direct host acceptance calls.
    A checker-only recheck runs through owctl in a fresh interpreter.
    """
    from tools.overworld.devtools_contract import source_paths
    digest = hashlib.sha256()
    root = Path(__file__).resolve().parents[2]
    for name in source_paths(root):
        if not name.endswith(".py"):
            continue
        digest.update(name.encode() + b"\0")
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


_LOADED_CONTROLLER_CODE = _controller_code_revision()


def _require_current_controller():
    if _controller_code_revision() != _LOADED_CONTROLLER_CODE:
        raise ValidationFailure("loaded proof code changed; use scenario recheck in a fresh process or restart idle Workshop")


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.name


def _load_contracts(
    *,
    audit_runtime_proof_sources: bool = False,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_feature_manifest(FEATURE_MANIFEST)
    scenarios = load_scenarios(SCENARIO_DIRECTORY)
    cross_validate(
        manifest,
        scenarios,
        REPO,
        audit_runtime_proof_sources=audit_runtime_proof_sources,
    )
    return manifest, scenarios


def _expand_command(command: list[str]) -> list[str]:
    python = REPO_PYTHON if REPO_PYTHON.is_file() else Path(sys.executable)
    prefix: list[str] = []
    if command and command[0] == "{headless-python}":
        prefix = [str(python), *HEADLESS_PYTHON_FLAGS]
        command = command[1:]
    replacements = {"{python}": str(python), "{repo}": str(REPO)}
    return prefix + [
        token.replace("{python}", replacements["{python}"]).replace(
            "{repo}", replacements["{repo}"]
        )
        for token in command
    ]


def _runtime_runner_key(command: list[str]) -> str | None:
    if len(command) >= 5 and command[1] == "scripts/owctl" and command[2:4] == ["scenario", "run"] \
            and command[4].startswith("legacy."):
        return command[4]  # Non-executable migration requirement, not a runner.
    if "--scenario" not in command:
        return None
    scenario_index = command.index("--scenario")
    if scenario_index + 1 >= len(command):
        return None
    script = next(
        (
            token
            for token in reversed(command[:scenario_index])
            if token.endswith(".py")
        ),
        None,
    )
    if script is None:
        return None
    script_path = Path(script)
    if script_path.is_absolute():
        try:
            script = script_path.resolve().relative_to(REPO.resolve()).as_posix()
        except ValueError:
            return None
    else:
        script = script_path.as_posix()
    return f"{script}::{command[scenario_index + 1]}"


def _runtime_measurement_contract(
    command: list[str],
) -> dict[str, list[dict[str, Any]]] | None:
    runner_key = _runtime_runner_key(command)
    return (
        RUNTIME_PROOF_REGISTRY["measurementContracts"].get(runner_key)
        if runner_key is not None
        else None
    )


def _has_semantic_value(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, list):
        return bool(value) and any(_has_semantic_value(item) for item in value)
    if isinstance(value, dict):
        return bool(value) and any(_has_semantic_value(item) for item in value.values())
    return False


def _behavior_resolution_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()).hexdigest()


def _packaged_resolver_oracle() -> dict[str, Any] | None:
    """Build controller-owned expectations from authenticated product inputs."""
    global _PACKAGED_RESOLVER_ORACLE
    if _PACKAGED_RESOLVER_ORACLE is not None:
        return _PACKAGED_RESOLVER_ORACLE
    try:
        blob_path = REPO / "build/OverworldWildBehaviorData.bin"
        blob = blob_path.read_bytes()
        corpus = json.loads((
            REPO / "tools/overworld/native/behavior_resolver_golden.json"
        ).read_text())
        names = (
            "default-class-and-lanes",
            "species-class-selection",
            "forced-follower-profile",
            "relative-override",
            "conditional-rooftop-replay",
            "explicit-picked-up-class",
            "legacy-forced-asleep-match-token",
            "explicit-canopy-conditional-application",
        )
        by_name = {item.get("name"): item for item in corpus["vectors"]}
        if corpus.get("blobVersion") != 77 or any(name not in by_name for name in names):
            return None
        adapter_path = REPO / "tools/overworld-viewer-v2/native_resolver.py"
        module_spec = importlib.util.spec_from_file_location(
            "owctl_packaged_resolver_oracle", adapter_path
        )
        if module_spec is None or module_spec.loader is None:
            return None
        adapter = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(adapter)
        executable = adapter.build(REPO)
        results = adapter.resolve_many(
            blob_path,
            [by_name[name]["request"] for name in names],
            root=REPO,
            executable=executable,
        )
        descriptor = load_debug_descriptor(DEBUG_DESCRIPTOR)
        resolver = next(
            service for service in descriptor["privateServices"]
            if service.get("name") == "resolver"
        )
        metadata_keys = (
            "behaviorClass", "behaviorLimitKey", "speciesClassRuleIndex",
            "matchedClassRuleMask", "matchedOverrideMask",
            "forcedOverrideMask", "conditionalOverrideMask",
            "appliedOverrideMask",
        )
        metadata = [
            {key: result[key] for key in metadata_keys}
            for result in results
        ]
        _PACKAGED_RESOLVER_ORACLE = {
            "service": [
                0x5250574F,
                resolver["version"],
                resolver["size"],
                resolver["callbacks"]["resolve"] & ~1,
            ],
            "blob": [len(blob), hashlib.sha256(blob).hexdigest()],
            "profile": [
                hashlib.sha256(bytes.fromhex(result["profileHex"])).hexdigest()
                for result in results
            ],
            "primitives": [result["primitivesHex"] for result in results],
            "fingerprint": [result["fingerprint"] for result in results],
            "metadata": _behavior_resolution_digest(metadata),
            "provenance": [
                _behavior_resolution_digest({
                    "traceDropped": result["traceDropped"],
                    "trace": result["trace"],
                })
                for result in results
            ],
        }
        return _PACKAGED_RESOLVER_ORACLE
    except (KeyError, OSError, RuntimeError, ValidationFailure, ValueError):
        return None


def _registry_validator_passes(
    specification: dict[str, Any], actual: Any, expected: Any
) -> bool:
    validator = specification.get("validator")
    if validator == "meaningful-observation":
        return "expected" in specification or _has_semantic_value(actual)
    if validator == "actor-handle-current":
        if not isinstance(actual, dict):
            return False
        required = (
            "slot", "generation", "fieldEpoch", "mapGeneration",
            "encounterGeneration", "value",
        )
        if any(
            not isinstance(actual.get(key), int)
            or isinstance(actual.get(key), bool)
            for key in required
        ):
            return False
        return (
            0 <= actual["slot"] < 32
            and actual["generation"] > 0
            and actual["fieldEpoch"] > 0
            and actual["mapGeneration"] > 0
            and actual["encounterGeneration"] > 0
            and actual["value"]
                == ((actual["generation"] << 16) | actual["slot"])
        )
    if validator == "positive-identical-values":
        return (
            isinstance(actual, list)
            and bool(actual)
            and all(
                isinstance(item, int)
                and not isinstance(item, bool)
                and item > 0
                for item in actual
            )
            and len(set(actual)) == 1
        )
    if validator == "live-object-identity-flags":
        return (
            isinstance(actual, list)
            and len(actual) == 13
            and actual[0:2] == [1, 1]
            and isinstance(actual[2], int)
            and not isinstance(actual[2], bool)
            and actual[2] > 0
            and actual[3] == actual[2]
            and actual[4] == 2074
            and actual[5:10] == [1, 1, 1, 1, 1]
            and actual[10:] == [165, 1, 1]
        )
    if validator == "public-role-transition-v1":
        if not isinstance(actual, dict):
            return False
        try:
            roles = load_debug_descriptor(DEBUG_DESCRIPTOR)["enums"][
                "OverworldActorRole"
            ]
            from_name = specification["fromRole"]
            to_name = specification["toRole"]
            from_id = roles[f"OVERWORLD_ACTOR_ROLE_{from_name}"]
            to_id = roles[f"OVERWORLD_ACTOR_ROLE_{to_name}"]
        except (KeyError, OSError, ValidationFailure):
            return False
        return (
            actual.get("beforeRole") == from_name
            and actual.get("afterRole") == to_name
            and actual.get("traceFromRole") == from_id
            and actual.get("traceToRole") == to_id
            and isinstance(actual.get("beforeSubjectIdentity"), int)
            and not isinstance(actual.get("beforeSubjectIdentity"), bool)
            and actual["beforeSubjectIdentity"] > 0
            and actual.get("afterSubjectIdentity")
                == actual["beforeSubjectIdentity"]
            and isinstance(actual.get("beforeEncounterGeneration"), int)
            and not isinstance(actual.get("beforeEncounterGeneration"), bool)
            and actual["beforeEncounterGeneration"] > 0
            and actual.get("afterEncounterGeneration")
                == actual["beforeEncounterGeneration"]
            and isinstance(actual.get("traceActorHandle"), int)
            and actual["traceActorHandle"] > 0
            and actual.get("mountedActorHandle")
                == actual["traceActorHandle"]
        )
    if validator == "acceleration-terminal-series-v1":
        if not isinstance(actual, dict):
            return False
        initials = actual.get("initials")
        series = actual.get("series")
        if (
            not isinstance(initials, list)
            or len(initials) != 2
            or not isinstance(series, list)
            or len(series) != 2
            or any(not isinstance(values, list) or len(values) != 7
                   for values in series)
            or any(not isinstance(value, int) or isinstance(value, bool)
                   for value in initials)
            or any(not isinstance(value, int) or isinstance(value, bool)
                   for values in series for value in values)
        ):
            return False
        if specification.get("aspect") == "commits":
            return all(
                values == [
                    (initials[index] + step) & 0xFFFFFFFF
                    for step in range(1, 8)
                ]
                for index, values in enumerate(series)
            )
        durations = actual.get("durations")
        return (
            specification.get("aspect") == "profile"
            and all(values == [initials[index]] * 7
                    for index, values in enumerate(series))
            and isinstance(durations, list)
            and len(durations) == 2
            and all(isinstance(values, list) and len(values) == 7
                    for values in durations)
            and durations[0] == durations[1]
            and all(isinstance(value, int) and not isinstance(value, bool)
                    and value > 0 for value in durations[0])
            and len(set(durations[0])) > 1
        )
    if validator == "stationary-single-crash-v1":
        return (
            isinstance(actual, list)
            and len(actual) == 3
            and actual[0] == 1
            and isinstance(actual[1], list)
            and actual[1] == actual[2]
        )
    if validator == "complete-motion-observation-v1":
        return (
            isinstance(actual, list)
            and len(actual) == 2
            and all(isinstance(value, int) and not isinstance(value, bool)
                    for value in actual)
            and actual[0] == actual[1]
            and actual[1] >= specification.get("minimumTotal", 1)
        )
    if validator == "stream-target-reached-v1":
        return (
            isinstance(actual, list)
            and len(actual) == 3
            and all(isinstance(value, int) and not isinstance(value, bool)
                    for value in actual)
            and actual[1] == actual[0] + specification.get("distance", 0)
            and actual[2] >= actual[1]
        )
    if validator == "blocked-state-unchanged-v1":
        return isinstance(actual, list) and len(actual) == 2 \
            and actual[0] == actual[1]
    if validator == "terminal-boundary-target-v1":
        return (
            isinstance(actual, dict)
            and actual.get("boundaryCount") == specification.get("requiredCount")
            and isinstance(actual.get("final"), list)
            and len(actual["final"]) == 2
            and actual.get("target") == actual["final"]
        )
    if validator == "hop-arc-parabola-v1":
        cases = actual.get("cases") if isinstance(actual, dict) else None
        if not isinstance(cases, list) or len(cases) != specification.get("caseCount"):
            return False
        for case in cases:
            if not isinstance(case, dict):
                return False
            duration = case.get("duration")
            samples = case.get("samples")
            if (
                not isinstance(duration, int)
                or isinstance(duration, bool)
                or duration <= 0
                or not isinstance(samples, list)
                or len(samples) != duration + 1
            ):
                return False
            expected = [
                [
                    elapsed,
                    16 * (((4 * elapsed * (duration - elapsed) // duration)
                           << 12) // duration),
                ]
                for elapsed in range(duration + 1)
            ]
            if samples != expected:
                return False
        return True
    if validator == "nearest-diagonal-choice-v1":
        if not isinstance(actual, dict):
            return False
        vectors = {
            "UP": (0, -1), "DOWN": (0, 1),
            "LEFT": (-1, 0), "RIGHT": (1, 0),
        }
        direction = actual.get("direction")
        start = actual.get("start")
        ordered = actual.get("orderedNearTargets")
        equal = actual.get("equalDiagonalTargets")
        chosen = actual.get("chosen")
        if (
            direction not in vectors
            or not isinstance(start, list) or len(start) != 2
            or not isinstance(ordered, list) or not ordered
            or not isinstance(equal, list)
            or chosen != ordered[0]
            or actual.get("final") != chosen
            or chosen in equal
        ):
            return False
        dx, dy = vectors[direction]
        headings = []
        for index, target in enumerate(ordered):
            if not isinstance(target, list) or len(target) != 2:
                return False
            offset_x = target[0] - start[0]
            offset_y = target[1] - start[1]
            forward = offset_x * dx + offset_y * dy
            lateral = offset_y * dx - offset_x * dy
            if forward <= abs(lateral) or lateral == 0:
                return False
            headings.append((abs(lateral), -forward, 0 if lateral > 0 else 1, index))
        return headings == sorted(headings)
    if validator == "stable-selector-identity-v1":
        if not isinstance(actual, list):
            return False
        if specification.get("aspect") == "subject":
            return len(actual) == 2 and actual[0] == actual[1] \
                and isinstance(actual[0], int) and actual[0] > 0
        return (
            specification.get("aspect") == "object"
            and len(actual) == 3
            and actual[0] == 0
            and isinstance(actual[1], int)
            and actual[1] > 0
            and actual[2] == actual[1]
        )
    if validator == "mounted-frame-matrix-v1":
        if not isinstance(actual, dict):
            return False
        durations = [*range(1, 33), *range(1, 33), 5]
        if actual.get("durations") != durations:
            return False
        if specification.get("aspect") == "counts":
            attempt = actual.get("diagonalAttempt")
            return (
                actual.get("elapsedCounts") == durations
                and isinstance(attempt, dict)
                and attempt.get("before") == attempt.get("after")
                and attempt.get("mode") == "IDLE"
                and attempt.get("pending") == 0
            )
        return (
            specification.get("aspect") == "elapsed"
            and actual.get("sequences") == [list(range(value)) for value in durations]
        )
    if validator == "contiguous-elapsed-v1":
        if not isinstance(actual, dict):
            return False
        start = actual.get("start")
        duration = actual.get("duration")
        if (
            not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(duration, int) or isinstance(duration, bool)
            or duration <= 0 or start < 0 or start >= duration
        ):
            return False
        stop = duration if start == 0 else duration + 1
        return actual.get("elapsed") == list(range(start, stop))
    if validator == "all-render-samples-synced-v1":
        return (
            isinstance(actual, list)
            and len(actual) == 2
            and isinstance(actual[0], int)
            and isinstance(actual[1], int)
            and actual[1] > 0
            and actual[0] == actual[1]
        )
    if validator == "population-refill-v1":
        return (
            isinstance(actual, list)
            and len(actual) == 3
            and all(isinstance(value, int) and not isinstance(value, bool)
                    for value in actual)
            and actual[2] == 6
            and 0 <= actual[0] < actual[1] <= actual[2]
        )
    if validator == "teleport-timing-matrix-v1":
        if not isinstance(actual, list) or len(actual) != 10:
            return False
        expected_names = [
            "fixed_visible_right", "fixed_visible_left", "fixed_visible_up",
            "fixed_visible_down", "fixed_flicker", "per_tile_visible_left",
            "per_tile_visible_right", "per_tile_visible_up",
            "per_tile_visible_down", "per_tile_flicker",
        ]
        if [case.get("name") for case in actual
                if isinstance(case, dict)] != expected_names:
            return False
        aspect = specification.get("aspect")
        if aspect == "endpoints":
            distances = {"fixed": set(), "per_tile": set()}
            for case in actual:
                start, target, final = (
                    case.get("start"), case.get("target"), case.get("final")
                )
                if (
                    not isinstance(start, list) or len(start) != 2
                    or not isinstance(target, list) or len(target) != 2
                    or final != target or start == target
                ):
                    return False
                distance = abs(target[0] - start[0]) + abs(target[1] - start[1])
                mode = "per_tile" if case.get("perTile") else "fixed"
                required_frames = 3 * distance if mode == "per_tile" else 7
                if case.get("travelTime") != (3 if mode == "per_tile" else 7) \
                        or case.get("frames") != required_frames:
                    return False
                if "visible" in case["name"]:
                    distances[mode].add(distance)
            return len(distances["fixed"]) >= 2 \
                and any(distance > 1 for distance in distances["per_tile"])
        if aspect == "visibility":
            for index, case in enumerate(actual):
                frames, visibility = case.get("frames"), case.get("visibility")
                if not isinstance(frames, int) or not isinstance(visibility, list) \
                        or len(visibility) != frames:
                    return False
                expected = ([False] * frames if index % 5 < 4 else
                            [((elapsed // 2) & 1) == 0
                             for elapsed in range(1, frames + 1)])
                if visibility != expected:
                    return False
            return True
        return aspect == "elapsed" and all(
            isinstance(case.get("frames"), int)
            and case.get("elapsed") == list(range(1, case["frames"] + 1))
            for case in actual
        )
    if validator == "turn-skid-recovery-v1":
        return (
            isinstance(actual, list)
            and len(actual) == 5
            and actual[0] == 1
            and isinstance(actual[1], int) and actual[1] > 0
            and actual[2] == actual[1]
            and actual[3:] == [0, 1]
        )
    if validator == "completed-route-v1":
        return (
            isinstance(actual, list) and len(actual) == 2
            and isinstance(actual[0], int) and isinstance(actual[1], int)
            and actual[1] > 0 and actual[0] == actual[1]
        )
    if validator == "warp-destination-v1":
        warp_fixtures = {
            (564, 391): 69,
            (555, 391): 68,
            (547, 399): 70,
            (558, 401): 71,
            (567, 405): 72,
        }
        door = actual.get("door") if isinstance(actual, dict) else None
        return (
            isinstance(door, list) and len(door) == 2
            and actual.get("sourceMap") == 67
            and tuple(door) in warp_fixtures
            and actual.get("destinationMap") == warp_fixtures[tuple(door)]
            and actual["destinationMap"] != actual["sourceMap"]
        )
    if validator == "wild-teleport-terminal-v1":
        if not isinstance(actual, dict):
            return False
        target = actual.get("target")
        return (
            isinstance(actual.get("origin"), list)
            and isinstance(target, list) and len(target) == 2
            and actual["origin"] != target
            and isinstance(actual.get("preCommit"), int)
            and actual.get("terminalCommit")
                == ((actual["preCommit"] + 1) & 0xFFFFFFFF)
            and actual.get("terminalLogical")
                == {"x": target[0], "y": target[1]}
        )
    if validator in ("motion-sample-counts-v1", "motion-elapsed-schedules-v1"):
        if not isinstance(actual, dict):
            return False
        durations = actual.get("durations")
        values = actual.get(
            "sampleCounts" if validator == "motion-sample-counts-v1"
            else "sequences"
        )
        if (
            not isinstance(durations, list) or not durations
            or not isinstance(values, list) or len(values) != len(durations)
            or any(not isinstance(duration, int) or isinstance(duration, bool)
                   or duration <= 0 for duration in durations)
        ):
            return False
        if validator == "motion-sample-counts-v1":
            return values == durations
        return values == [list(range(1, duration + 1)) for duration in durations]
    if validator == "packaged-resolver-parity-v1":
        oracle = _packaged_resolver_oracle()
        aspect = specification.get("aspect")
        return oracle is not None and aspect in oracle and actual == oracle[aspect]
    return False


CONTROLLER_RELATION_VALIDATORS = {
    "actor-handle-current",
    "positive-identical-values",
    "live-object-identity-flags",
    "public-role-transition-v1",
    "acceleration-terminal-series-v1",
    "stationary-single-crash-v1",
    "complete-motion-observation-v1",
    "stream-target-reached-v1",
    "blocked-state-unchanged-v1",
    "terminal-boundary-target-v1",
    "hop-arc-parabola-v1",
    "nearest-diagonal-choice-v1",
    "stable-selector-identity-v1",
    "mounted-frame-matrix-v1",
    "contiguous-elapsed-v1",
    "all-render-samples-synced-v1",
    "population-refill-v1",
    "teleport-timing-matrix-v1",
    "turn-skid-recovery-v1",
    "completed-route-v1",
    "warp-destination-v1",
    "wild-teleport-terminal-v1",
    "motion-sample-counts-v1",
    "motion-elapsed-schedules-v1",
    "packaged-resolver-parity-v1",
}


def _valid_png(path: Path) -> bool:
    header = path.read_bytes()[:24]
    return (
        len(header) == 24
        and header[:8] == b"\x89PNG\r\n\x1a\n"
        and header[12:16] == b"IHDR"
        and int.from_bytes(header[16:20], "big") > 0
        and int.from_bytes(header[20:24], "big") > 0
    )


def _command_record(
    command: list[str], completed: subprocess.CompletedProcess,
    *, log_directory: Path | None = None, log_index: int = 0,
) -> dict[str, Any]:
    stdout = completed.stdout or b""
    stderr = completed.stderr or b""
    # Subprocess output is binary so invalid UTF-8 and line endings survive.
    # String support also keeps existing in-process command fixtures usable.
    stdout = stdout.encode("utf-8") if isinstance(stdout, str) else stdout
    stderr = stderr.encode("utf-8") if isinstance(stderr, str) else stderr
    record = {
        "command": command,
        "returnCode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdoutSha256": hashlib.sha256(stdout).hexdigest(),
        "stderrSha256": hashlib.sha256(stderr).hexdigest(),
    }
    try:
        archive_command_output(record, REPO, log_directory or artifact_directory(REPO),
                               log_index, stdout, stderr)
    except (OSError, ValidationFailure) as error:
        record.update(passed=False, resultError=str(error))
    record["stdoutTail"] = stdout.decode("utf-8", errors="replace")[-2000:]
    record["stderrTail"] = stderr.decode("utf-8", errors="replace")[-2000:]
    return record


def _run_command(
    command: list[str],
    result_kind: str,
    required_claims: list[str] | tuple[str, ...] = (),
    *,
    measurement_contract: dict[str, list[dict[str, Any]]] | None = None,
    minimum_frames: int = 0,
    maximum_frames: int = 0,
    visual_artifact: dict[str, Any] | None = None,
    log_directory: Path | None = None,
    log_index: int = 0,
) -> dict[str, Any]:
    if required_claims or measurement_contract is not None or _runtime_runner_key(command) is not None:
        raise ValidationFailure(
            "opaque runtime command dispatch is retired; use a registered shared-devtools test job"
        )
    proof_session = None
    environment = None
    artifact_path = None
    proof_read_fd = None
    timeout_seconds = None
    if measurement_contract is not None:
        proof_session = secrets.token_hex(16)
        environment = os.environ.copy()
        proof_read_fd, proof_write_fd = os.pipe()
        os.set_inheritable(proof_read_fd, True)
        os.write(proof_write_fd, proof_session.encode("ascii"))
        os.close(proof_write_fd)
        environment["OWCTL_RUNTIME_PROOF_FD"] = str(proof_read_fd)
        environment["OWCTL_RUNTIME_MINIMUM_FRAMES"] = str(minimum_frames)
        environment["OWCTL_RUNTIME_MAXIMUM_FRAMES"] = str(maximum_frames)
        timeout_seconds = max(
            120,
            min(900, (maximum_frames if maximum_frames > 0 else 2400) // 10),
        )
    if visual_artifact is not None:
        artifact_path = REPO / visual_artifact["path"]
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.unlink(missing_ok=True)
    started_ns = time.time_ns()
    started_clock = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=REPO,
            capture_output=True,
            text=False,
            env=environment,
            pass_fds=(() if proof_read_fd is None else (proof_read_fd,)),
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        record = _command_record(command, subprocess.CompletedProcess(
            command, None, error.stdout, error.stderr),
            log_directory=log_directory, log_index=log_index)
        record["resultError"] = "; ".join(filter(None, (
            f"runtime command exceeded {timeout_seconds} seconds", record.get("resultError"))))
        record["elapsedSeconds"] = round(time.monotonic() - started_clock, 6)
        return record
    finally:
        if proof_read_fd is not None:
            os.close(proof_read_fd)
    record = _command_record(command, completed, log_directory=log_directory, log_index=log_index)
    record["elapsedSeconds"] = round(time.monotonic() - started_clock, 6)
    if "resultError" in record:
        return record  # A collector cannot pass when its output could not be kept.
    if result_kind == "json-passed":
        try:
            payload = json.loads(completed.stdout)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            record["passed"] = False
            record["resultError"] = f"stdout is not JSON: {error}"
        else:
            reported_passed = (
                isinstance(payload, dict) and payload.get("passed") is True
            )
            result_errors = []
            if completed.returncode != 0:
                result_errors.append(
                    f"command exited with status {completed.returncode}"
                )
            if not reported_passed:
                result_errors.append("JSON result does not contain passed=true")
            record["passed"] = completed.returncode == 0 and reported_passed
            if required_claims:
                evidence = (
                    payload.get("proofEvidence")
                    if isinstance(payload, dict)
                    else None
                )
                claim_results: dict[str, bool] = {}
                claim_errors: list[str] = []
                if measurement_contract is not None and (
                    not isinstance(evidence, dict)
                    or set(evidence) != set(required_claims)
                ):
                    claim_errors.append(
                        "proof evidence claim set differs from the registry"
                    )
                for claim in required_claims:
                    measurements = (
                        evidence.get(claim)
                        if isinstance(evidence, dict)
                        else None
                    )
                    if not isinstance(measurements, list) or not measurements:
                        claim_errors.append(f"{claim}: missing measurements")
                        claim_results[claim] = False
                        continue
                    names: set[str] = set()
                    has_observed_value = False
                    passed = True
                    expected_measurements = (
                        measurement_contract.get(claim)
                        if measurement_contract is not None
                        else None
                    )
                    if expected_measurements is not None and [
                        measurement.get("name")
                        for measurement in measurements
                        if isinstance(measurement, dict)
                    ] != [item["name"] for item in expected_measurements]:
                        claim_errors.append(
                            f"{claim}: measurement names differ from the registry"
                        )
                        passed = False
                    for index, measurement in enumerate(measurements):
                        if not isinstance(measurement, dict):
                            claim_errors.append(
                                f"{claim}[{index}]: measurement is not an object"
                            )
                            passed = False
                            continue
                        name = measurement.get("name")
                        if not isinstance(name, str) or not name or name in names:
                            claim_errors.append(
                                f"{claim}[{index}]: name is missing or duplicated"
                            )
                            passed = False
                            continue
                        names.add(name)
                        if "actual" not in measurement or "expected" not in measurement:
                            claim_errors.append(
                                f"{claim}.{name}: actual and expected are required"
                            )
                            passed = False
                            continue
                        actual = measurement["actual"]
                        expected = measurement["expected"]
                        operator = measurement.get("operator", "eq")
                        specification = (
                            expected_measurements[index]
                            if expected_measurements is not None
                            and index < len(expected_measurements)
                            else None
                        )
                        if specification is not None:
                            expected_operator = specification["operator"]
                            if operator != expected_operator:
                                claim_errors.append(
                                    f"{claim}.{name}: operator differs from the registry"
                                )
                                passed = False
                            value_type = specification["type"]
                            type_matches = {
                                "integer": isinstance(actual, int)
                                    and not isinstance(actual, bool),
                                "array": isinstance(actual, list),
                                "object": isinstance(actual, dict),
                                "string": isinstance(actual, str),
                            }.get(value_type, False)
                            if not type_matches:
                                claim_errors.append(
                                    f"{claim}.{name}: actual value has the wrong shape"
                                )
                                passed = False
                            if "expected" in specification and (
                                expected != specification["expected"]
                                or actual != specification["expected"]
                            ):
                                claim_errors.append(
                                    f"{claim}.{name}: fixed expected value differs"
                                )
                                passed = False
                            minimum = specification.get("minimum")
                            if minimum is not None and (
                                not isinstance(actual, int)
                                or isinstance(actual, bool)
                                or actual < minimum
                            ):
                                claim_errors.append(
                                    f"{claim}.{name}: value is below the registry minimum"
                                )
                                passed = False
                            maximum = specification.get("maximum")
                            if maximum is not None and (
                                not isinstance(actual, int)
                                or isinstance(actual, bool)
                                or actual > maximum
                            ):
                                claim_errors.append(
                                    f"{claim}.{name}: value is above the registry maximum"
                                )
                                passed = False
                            minimum_items = specification.get("minItems")
                            if minimum_items is not None and (
                                not isinstance(actual, list)
                                or len(actual) < minimum_items
                            ):
                                claim_errors.append(
                                    f"{claim}.{name}: observation is too short"
                                )
                                passed = False
                            if not _registry_validator_passes(
                                specification, actual, expected
                            ):
                                claim_errors.append(
                                    f"{claim}.{name}: registry validator rejected the observation"
                                )
                                passed = False
                            required_keys = specification.get("requiredKeys", [])
                            if required_keys and (
                                not isinstance(actual, dict)
                                or any(key not in actual for key in required_keys)
                            ):
                                claim_errors.append(
                                    f"{claim}.{name}: identity fields are missing"
                                )
                                passed = False
                        has_observed_value |= (
                            actual is not None and not isinstance(actual, bool)
                        )
                        if (
                            specification is not None
                            and specification.get("validator")
                                in CONTROLLER_RELATION_VALIDATORS
                        ):
                            comparison = True
                        else:
                            try:
                                if operator == "eq":
                                    comparison = actual == expected
                                elif operator == "ne":
                                    comparison = actual != expected
                                elif operator == "lt":
                                    comparison = actual < expected
                                elif operator == "lte":
                                    comparison = actual <= expected
                                elif operator == "gt":
                                    comparison = actual > expected
                                elif operator == "gte":
                                    comparison = actual >= expected
                                else:
                                    raise KeyError(operator)
                            except (KeyError, TypeError):
                                claim_errors.append(
                                    f"{claim}.{name}: invalid comparison"
                                )
                                passed = False
                                continue
                        if not comparison:
                            claim_errors.append(
                                f"{claim}.{name}: actual did not satisfy expected"
                            )
                            passed = False
                    if not has_observed_value:
                        claim_errors.append(
                            f"{claim}: needs a non-boolean observed value"
                        )
                        passed = False
                    claim_results[claim] = passed
                record["proofClaims"] = claim_results
                record["proofEvidence"] = (
                    {
                        claim: evidence.get(claim)
                        for claim in required_claims
                        if claim in evidence
                    }
                    if isinstance(evidence, dict)
                    else None
                )
                if claim_errors:
                    record["passed"] = False
                    result_errors.append(
                        "JSON result does not prove required claims: "
                        + "; ".join(claim_errors)
                    )
            if measurement_contract is not None:
                execution = payload.get("proofExecution")
                if not isinstance(execution, dict):
                    result_errors.append("runtime proof has no execution receipt")
                    record["passed"] = False
                else:
                    frames_observed = execution.get("framesObserved")
                    iterations = execution.get("iterations")
                    iteration_passed = execution.get("iterationPassed")
                    iteration_frames = execution.get("iterationFrames")
                    iteration_hashes = execution.get("iterationEvidenceSha256")
                    evidence_hash = hashlib.sha256(json.dumps(
                        evidence,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()).hexdigest()
                    receipt_valid = (
                        execution.get("session") == proof_session
                        and execution.get("minimumFrames") == minimum_frames
                        and execution.get("maximumFrames") == maximum_frames
                        and isinstance(frames_observed, int)
                        and not isinstance(frames_observed, bool)
                        and frames_observed >= minimum_frames
                        and (maximum_frames <= 0 or frames_observed <= maximum_frames)
                        and isinstance(iterations, int)
                        and iterations == 1
                        and isinstance(iteration_passed, list)
                        and iteration_passed == [True]
                        and isinstance(iteration_frames, list)
                        and len(iteration_frames) == 1
                        and isinstance(iteration_frames[0], int)
                        and not isinstance(iteration_frames[0], bool)
                        and iteration_frames[0] == frames_observed
                        and iteration_frames[0] >= minimum_frames
                        and isinstance(iteration_hashes, list)
                        and iteration_hashes == [evidence_hash]
                        and evidence_hash != hashlib.sha256(b"{}").hexdigest()
                    )
                    if not receipt_valid:
                        result_errors.append(
                            "runtime execution receipt is invalid or contains a failed iteration"
                        )
                        record["passed"] = False
                    record["proofExecution"] = execution
            if visual_artifact is not None:
                reported_artifact = payload.get(visual_artifact["resultField"])
                artifact_valid = False
                if isinstance(reported_artifact, str) and artifact_path is not None:
                    reported_path = Path(reported_artifact).resolve()
                    if reported_path == artifact_path.resolve() and reported_path.is_file():
                        stat = reported_path.stat()
                        artifact_valid = (
                            stat.st_size >= visual_artifact["minimumBytes"]
                            and stat.st_mtime_ns >= started_ns
                            and _valid_png(reported_path)
                        )
                        if artifact_valid:
                            record["visualArtifact"] = {
                                "path": _relative(reported_path),
                                "size": stat.st_size,
                                "sha256": hashlib.sha256(
                                    reported_path.read_bytes()
                                ).hexdigest(),
                            }
                if not artifact_valid:
                    result_errors.append(
                        "visual proof artifact was not freshly captured"
                    )
                    record["passed"] = False
            if result_errors:
                record["resultError"] = "; ".join(result_errors)
    return record


def _doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []

    def add(name: str, state: str, detail: str) -> None:
        checks.append({"name": name, "state": state, "detail": detail})

    try:
        manifest, scenarios = _load_contracts()
    except ValidationFailure as error:
        add("contracts", "error", str(error))
        manifest = None
        scenarios = {}
    else:
        add(
            "contracts",
            "ok",
            f"{len(manifest['capabilities'])} capabilities; {len(scenarios)} scenarios",
        )
    try:
        load_trace_schema(TRACE_SCHEMA)
    except ValidationFailure as error:
        add("trace-schema", "error", str(error))
    else:
        add("trace-schema", "ok", _relative(TRACE_SCHEMA))

    feature_table = subprocess.run(
        [sys.executable, "scripts/generate_overworld_feature_table.py", "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    add(
        "feature-table",
        "ok" if feature_table.returncode == 0 else "error",
        (feature_table.stdout or feature_table.stderr).strip(),
    )

    if sys.version_info < (3, 10):
        add("python", "error", f"Python {sys.version_info.major}.{sys.version_info.minor} is too old")
    else:
        add("python", "ok", sys.version.split()[0])

    required_sources = [
        REPO / "scripts/verify_overworld_mount.py",
        REPO / "scripts/overworld_devtools_worker.py",
        REPO / "tools/overworld/devtools_engine.py",
        REPO / "tools/overworld/devtools_native.py",
        REPO / "tools/overworld/devtools_jobs.py",
        REPO / "tools/overworld/devtools_test_contract.py",
        REPO / "scripts/overworld_behavior_profile_viewer.py",
    ]
    missing_sources = [_relative(path) for path in required_sources if not path.is_file()]
    add(
        "source-adapters",
        "error" if missing_sources else "ok",
        ", ".join(missing_sources) if missing_sources else "present",
    )

    optional = (
        ("rom", REPO / "test.nds"),
        ("dsv", REPO / "test.dsv"),
        ("sav", REPO / "test.sav"),
        ("build-manifest", REPO / "build/pokemon_move_history_capture_build.json"),
    )
    for name, path in optional:
        add(name, "ok" if path.is_file() else "warning", _relative(path))
    if not DEBUG_DESCRIPTOR.is_file():
        add("debug-descriptor", "warning", _relative(DEBUG_DESCRIPTOR))
    else:
        try:
            descriptor = load_debug_descriptor(DEBUG_DESCRIPTOR)
        except ValidationFailure as error:
            add("debug-descriptor", "error", str(error))
        else:
            add(
                "debug-descriptor",
                "ok",
                f"overlay {descriptor['overlay']['sha256'][:12]} facade v{descriptor['facade']['version']}",
            )
    emulator = emulator_record(REPO)
    add(
        "emulator-python",
        "ok" if emulator["present"] else "warning",
        f"{emulator['pythonExecutable']}: {emulator['detail']}",
    )

    result = {
        "schemaVersion": 1,
        "passed": not any(check["state"] == "error" for check in checks),
        "warnings": sum(check["state"] == "warning" for check in checks),
        "checks": checks,
    }
    if args.json:
        _json(result)
    else:
        for check in checks:
            print(f"{check['state'].upper():7} {check['name']}: {check['detail']}")
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


def _scenario_list(args: argparse.Namespace) -> int:
    _, scenarios = _load_contracts()
    ordered = [scenarios[key] for key in sorted(scenarios)]
    if args.json:
        _json(
            [
                {
                    "id": item["id"],
                    "status": item["status"],
                    "proofLevel": item["proofLevel"],
                    "costTier": item["costTier"],
                    "title": item["title"],
                }
                for item in ordered
            ]
        )
    else:
        for item in ordered:
            print(
                f"{item['id']:<43} {item['status']:<7} "
                f"{item['proofLevel']}/C{item['costTier']}  {item['title']}"
            )
    return 0


def _scenario_validate(args: argparse.Namespace) -> int:
    manifest, scenarios = _load_contracts(audit_runtime_proof_sources=True)
    unknown = [scenario_id for scenario_id in args.scenario_ids if scenario_id not in scenarios]
    if unknown:
        raise ValidationFailure("unknown scenario(s): " + ", ".join(unknown))
    selected = args.scenario_ids or sorted(scenarios)
    result = {
        "schemaVersion": 1,
        "manifest": _relative(FEATURE_MANIFEST),
        "capabilities": len(manifest["capabilities"]),
        "scenarios": selected,
        "runtimeMigration": _runtime_migration_summary(),
        "passed": True,
    }
    if args.json:
        _json(result)
    else:
        print(f"validated {len(selected)} scenario(s) and the feature manifest")
    return 0


def _runtime_migration_summary() -> dict[str, Any]:
    from tools.overworld.validation import resolve_runtime_migration_targets
    path = REPO / "tools/overworld/runtime_proof_migration.json"
    document = validate_runtime_migration(json.loads(path.read_text()), RUNTIME_PROOF_REGISTRY)
    requirements = document["requirements"]
    pending = [{"requirement": key, "scenarios": item["scenarios"], "reason": item["reason"]}
               for key, item in requirements.items() if item["status"] == "pending"]
    superseded = [{"requirement": key, "replacements": resolve_runtime_migration_targets(document, key),
                   "review": item["review"]} for key, item in requirements.items() if item["status"] == "superseded"]
    obsolete = [{"requirement": key, "review": item["review"]}
                for key, item in requirements.items() if item["status"] == "obsolete"]
    return {"executionMethod": "shared-devtools", "legacyExecution": "retired",
            "path": _relative(path), "requirementCount": len(requirements),
            "pendingCount": len(pending), "pending": pending, "superseded": superseded,
            "supersededCount": len(superseded), "obsolete": obsolete,
            "obsoleteCount": len(obsolete), "complete": not pending}


_LEDYBA_REQUIREMENT = "legacy.ledyba-normal-profile"
_LEDYBA_RECORDER_REQUIREMENT = "legacy.live-observer-controls"
_LEDYBA_CLAIMS = ["live-actor-identity", "profile-resolution", "natural-input", "logical-commit",
                  "rendered-motion", "control-release"]
_LEDYBA_MEASUREMENT_RULES = (
    ("live-actor-identity", "identity-samples", "gte", 1),
    ("profile-resolution", "public-profile-count", "gte", 1),
    ("natural-input", "complete-chain-intervals", "gte", 3),
    ("logical-commit", "chain-errors", "eq", 0),
    ("rendered-motion", "render-errors", "eq", 0),
    ("rendered-motion", "complete-actions", "gte", 3),
    ("control-release", "spawn-and-terminal", "eq", 1),
)
_LEDYBA_REQUIRED_MEANINGS = ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
_RECORDER_CLAIMS = ["live-actor-identity", "controlled-action"]
_POOL_REQUIREMENT = "shared.ledyba-pool-site-v1"
_POOL_SURFACE_REQUIREMENT = "shared.ledyba-pool-surface-v1"
_HEIGHT_CONTROL_REQUIREMENT = "shared.spawn-height-recorder-control-v1"
_HEIGHT_CONTROL_KIND = "live-spawn-height-control-v1"
_ROUTE_CONTROL_KIND = "live-route-control-v1"
_CADENCE_KIND = "unmounted-cadence-v1"
_CADENCE_REQUIREMENT = "legacy.unmounted-long-travel"
_CADENCE_CLAIMS = ["live-actor-identity", "natural-input", "logical-commit", "rendered-motion",
                   "control-release", "host-cpu-pacing"]
_GAME_CADENCE_KIND = "unmounted-game-cadence-v1"
_GAME_CADENCE_REQUIREMENT = "current.unmounted-game-cadence"
_GAME_CADENCE_CLAIMS = _CADENCE_CLAIMS[:-1]
_CADENCE_KINDS = (_CADENCE_KIND, _GAME_CADENCE_KIND)
_ROUTE_CONTROL_REQUIREMENT = "legacy.live-route-observer-controls"
_WALK_POLICY_CONTROL_KIND = "live-walk-policy-control-v1"
_WALK_POLICY_CONTROL_REQUIREMENT = "shared.walk-policy-recorder-control-v1"
_MOUNT_PACING_KIND = "mounted-frame-pacing-v1"
_MOUNT_CONTROL_STRESS_KIND = "mounted-control-stress-v1"
_MOUNTED_HOP_ARC_KIND = "mounted-hop-arc-v1"
_MOUNTED_NEAREST_DIAGONAL_KIND = "mounted-nearest-diagonal-v1"
_APPEAR_HOP_KIND = "appear-hop-timing-v1"
_APPEAR_HOP_REQUIREMENT = "shared.appear-hop-timing-v1"
_MOUNT_POSE_CONTROL_KIND = "live-mount-pose-control-v1"
_MOUNT_POSE_CONTROL_REQUIREMENT = "shared.mounted-pose-recorder-control-v1"
_WILD_WALK_KIND = "wild-walk-v1"
_WILD_LEDGE_KIND = "wild-ledge-v1"
_WILD_TELEPORT_KIND = "wild-teleport-v1"
_RUNNER_STOP_SKID_KIND = "runner-stop-skid-v1"
_RUNNER_TURN_RUNWAY_KIND = "runner-turn-runway-v1"
_WILD_BATTLE_HANDOFF_KIND = "wild-battle-handoff-v1"
_WILD_TRANSITION_KIND = "wild-transition-invalidation-v1"
_FOLLOWER_TRANSITION_KIND = "follower-transition-rebind-v1"
_MOUNTED_STREAMING_KIND = "mounted-streaming-path-v1"
_MOUNTED_CARDINAL_STREAMING_KIND = "mounted-cardinal-streaming-v1"
_MOUNTED_WALK_TRANSITION_KIND = "mounted-walk-transition-v1"
_MOUNTED_HOP_TRANSITION_KIND = "mounted-hop-transition-v1"
_LAND_SURF_KIND = "land-surf-separation-v1"
_SPAWN_WORK_BUDGET_KIND = "spawn-work-budget-v1"
_UNMOUNTED_ZERO_STUTTER_KIND = "unmounted-zero-stutter-v1"
_POPULATION_FAST_TRAVEL_KIND = "population-fast-travel-v1"
_MOUNTED_TELEPORT_MATRIX_KIND = "mounted-teleport-matrix-v1"
_WARP_GATE_KIND = "warp-gate-v1"
_WILD_CLEAR_CONTROL_KIND = "live-wild-clear-control-v1"
_WILD_CLEAR_CONTROL_REQUIREMENT = "shared.wild-clear-recorder-control-v1"
_CORNER_KIND = "diagonal-corner-v1"
_CORNER_CONTROL_KIND = "live-corner-control-v1"
_CORNER_CONTROL_REQUIREMENT = "shared.corner-recorder-control-v1"
_MATRIX_KIND = "mounted-frame-matrix-v1"
_MATRIX_CONTROL_KIND = "live-walk-matrix-control-v1"


def _shared_cadence_queue_budget(rows):
    """Apply the full-route symptom budget to the retained native clock."""
    from tools.overworld.cadence_diagnostics import (
        UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS,
        _max_two_queue_ticks_check,
        summarize,
    )

    clock = summarize(rows)["guestQueueClock"]
    check = _max_two_queue_ticks_check(
        {"guestQueueClock": clock},
        UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS,
    )
    if not check["passed"]:
        reason = (
            "full route exact two-queue cadence " + check["reason"]
            + ": maximumTwoQueueArm9Ticks=" + str(check["maximumTwoQueueArm9Ticks"])
            + ", budgetArm9Ticks=" + str(check["budgetArm9Ticks"])
        )
        if clock["topTwoQueueIntervals"]:
            frames = clock["topTwoQueueIntervals"][0]["frames"]
            reason += ", frames=" + str(frames[0]) + "->" + str(frames[1])
        raise ValidationFailure(reason)
    return {
        **check,
        "scope": ("registered unmounted full-route exact ARM9 scheduler intervals; "
                  "not rendered-frame or cause proof"),
        "eligibleTwoQueueIntervals": clock["eligibleTwoQueueIntervals"],
        "observedTwoQueueIntervals": clock["observedTwoQueueIntervals"],
        "missingClockTriples": clock["missingClockTriples"],
        "topTwoQueueIntervals": clock["topTwoQueueIntervals"],
    }
_MATRIX_CONTROL_REQUIREMENT = "shared.walk-matrix-recorder-control-v1"
_STOMP_KIND = "mounted-stomp-v1"
_STOMP_CONTROL_KIND = "live-stomp-control-v1"
_STOMP_CONTROL_REQUIREMENT = "shared.stomp-recorder-control-v1"
_RESOLVER_KIND = "packaged-resolver-parity-v1"
_RESOLVER_REQUIREMENT = "legacy.packaged-resolver-parity"
_ACTOR_INSPECT_KIND = "actor-inspect-handle-v1"
_ACTOR_INSPECT_REQUIREMENT = "shared.actor-inspect-handle-v1"
_ACTOR_INSPECT_NAMES = ("packaged-inspect-entry", "bound-subject-identity",
    "current-actor-byte-parity", "stale-generation-rejection", "owned-buffer-cleanup", "native-call-boundaries")
_ROLE_TRANSFER_KIND = "follower-mounted-owner-transfer-v1"
_ROLE_TRANSFER_REQUIREMENT = "shared.follower-mounted-owner-transfer-v1"
_ROLE_CONTROL_KIND = "owner-reader-control-v1"
_ROLE_CONTROL_REQUIREMENT = "shared.owner-reader-control-v1"
_MOUNT_BEGIN_KIND = "mount-begin-current-follower-v1"
_MOUNT_BEGIN_REQUIREMENT = "legacy.mount-begin-current-follower"
_MOUNT_BEGIN_CLAIMS = ["natural-input", "live-actor-identity", "profile-resolution", "control-release"]
_ROUTE_CONTROL_NEGATIVES = ("absent-subject", "stale-subject", "route-missing-start",
    "route-missing-commit", "route-missing-finish", "route-missing-return", "route-missing-cpu",
    "route-missing-pin", "route-missing-cleanup")
_HEIGHT_MEANING_CONTROLS = ("height-control-missing-meaning", "height-control-unrestored")
_POOL_KINDS = ("pool-spawn-v1", "pool-spawn-surface-v1")
_POOL_CLAIMS = ["live-actor-identity", "profile-resolution", "natural-input", "logical-commit", "control-release"]
_POOL_SURFACE_CLAIMS = _POOL_CLAIMS + ["terrain-selection"]
_POOL_SURFACE_CONTROLS = ("pool-surface-missing-query", "pool-surface-missing-refresh",
                          "pool-surface-missing-terrain", "pool-surface-missing-height")
_POOL_MEASUREMENT_RULES = (
    ("live-actor-identity", "identity-samples", "gte", 1),
    ("profile-resolution", "profile-observations", "gte", 1),
    ("natural-input", "normal-own-finalization", "eq", 1),
    ("logical-commit", "pool-site-preserved", "eq", 1),
    ("control-release", "complete-spawn-hop", "eq", 1),
)


def _shared_recorder_contract(registry: dict[str, Any]) -> None:
    expected = {"live-actor-identity": [{"name": "live-recorder-baseline-identity", "operator": "eq",
        "type": "integer", "validator": "meaningful-observation", "expected": 1}],
        "controlled-action": [
            {"name": "live-recorder-baseline-and-faults", "operator": "eq", "type": "array",
             "validator": "meaningful-observation", "expected": [1, 1, 1]},
            {"name": "live-recorder-render-fault-frames", "operator": "gte", "type": "integer",
             "validator": "meaningful-observation", "minimum": 2}]}
    if registry.get("runners", {}).get(_LEDYBA_RECORDER_REQUIREMENT) != _RECORDER_CLAIMS \
            or registry.get("runnerKinds", {}).get(_LEDYBA_RECORDER_REQUIREMENT) != "observer-control" \
            or registry.get("measurementContracts", {}).get(_LEDYBA_RECORDER_REQUIREMENT) != expected:
        raise ValidationFailure("shared live recorder adapter changed its original control measurements")


def _shared_ledyba_contract(registry: dict[str, Any]) -> None:
    expected: dict[str, list[dict[str, Any]]] = {}
    for claim, suffix, operator, threshold in _LEDYBA_MEASUREMENT_RULES:
        expected.setdefault(claim, []).append({"name": "normal-ledyba-" + suffix,
            "operator": operator, "type": "integer", "validator": "meaningful-observation",
            "minimum" if operator == "gte" else "expected": threshold})
    if registry.get("runners", {}).get(_LEDYBA_REQUIREMENT) != _LEDYBA_CLAIMS \
            or registry.get("runnerKinds", {}).get(_LEDYBA_REQUIREMENT) != "normal-play" \
            or registry.get("measurementContracts", {}).get(_LEDYBA_REQUIREMENT) != expected:
        raise ValidationFailure("shared Ledyba adapter changed its original six claims/seven measurements")


def _shared_route_control_contract(registry):
    expected = {
        "live-actor-identity": [{"name":"live-route-recorder-baseline-identity", "operator":"eq",
            "type":"integer", "validator":"meaningful-observation", "expected":1}],
        "controlled-action": [{"name":"live-route-recorder-baseline-and-faults", "operator":"eq",
            "type":"array", "validator":"meaningful-observation", "expected":[1,1,1]}]}
    if registry.get("runners", {}).get(_ROUTE_CONTROL_REQUIREMENT) != _RECORDER_CLAIMS \
            or registry.get("runnerKinds", {}).get(_ROUTE_CONTROL_REQUIREMENT) != "observer-control" \
            or registry.get("measurementContracts", {}).get(_ROUTE_CONTROL_REQUIREMENT) != expected:
        raise ValidationFailure("route recorder adapter changed its original control contract")


def _shared_test_registration(test: dict[str, Any], repo: Path) -> tuple[dict[str, Any] | None, str]:
    from tools.overworld.devtools_test_contract import validate_test
    test = validate_test(test)
    registry = json.loads((repo / "tools/overworld/runtime_proof_registry.json").read_text())
    registration = registry.get("sharedTests", {}).get(test["id"])
    path = repo / "tests/overworld/test-recipes" / (test["id"] + ".json")
    recipe_hash = file_record(path, repo)["sha256"]
    if registration is None:
        return None, recipe_hash
    if not isinstance(registration, dict):
        raise ValidationFailure("shared test needs an implemented exact measurement adapter")
    if registration.get("recorderControlRequirement") is not None:
        _shared_recorder_kind(registration["recorderControlRequirement"])
    if registration.get("evaluator") == _ACTOR_INSPECT_KIND:
        expected = {"controlled-action": [{"name": name, "operator": "eq", "type": "integer",
            "validator": "meaningful-observation", "expected": 1} for name in _ACTOR_INSPECT_NAMES]}
        if registration.get("measurementContract") != expected \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != ["controlled-action"] \
                or test["requirements"] != [_ACTOR_INSPECT_REQUIREMENT] or test["mode"] != "prepared" \
                or test["subjects"] != [{"id": "mankey", "species": 56, "role": "FOLLOWER", "acquire": "existing"}] \
                or test.get("measurements") != [{"kind": _ACTOR_INSPECT_KIND, "subject": "mankey"}] \
                or registration.get("recorderControlRequirement") is not None:
            raise ValidationFailure("actor Inspect test changed its exact facade contract")
    elif registration.get("evaluator") == _RESOLVER_KIND:
        original = hashlib.sha256(json.dumps(registry.get("measurementContracts", {}).get(_RESOLVER_REQUIREMENT),
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if original != "af2751c1d9e100b226c2d75e8ac044c063f4335c79d9d2c7ec3b819a900a294e" \
                or registry.get("runners", {}).get(_RESOLVER_REQUIREMENT) != ["profile-resolution"] \
                or registry.get("runnerKinds", {}).get(_RESOLVER_REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != ["profile-resolution"] \
                or test["requirements"] != [_RESOLVER_REQUIREMENT] or test["mode"] != "prepared" \
                or test["subjects"] or test.get("measurements") != [{"kind": _RESOLVER_KIND}] \
                or registration.get("recorderControlRequirement") is not None:
            raise ValidationFailure("resolver test changed its original eight deployment measurements")
    elif registration.get("evaluator") in (_ROLE_TRANSFER_KIND, _ROLE_CONTROL_KIND):
        is_control = registration["evaluator"] == _ROLE_CONTROL_KIND
        if registration.get("proofLevel") != "S3" \
                or registration.get("claims") != ["live-actor-identity", "controlled-action" if is_control else "profile-resolution"] \
                or test["requirements"] != [_ROLE_CONTROL_REQUIREMENT if is_control else _ROLE_TRANSFER_REQUIREMENT] \
                or test["mode"] != ("observer-control" if is_control else "prepared") \
                or test["subjects"] != [{"id": "mankey", "species": 56, "role": "MOUNTED", "acquire": "existing"}] \
                or test.get("measurements") not in (None, []) \
                or registration.get("recorderControlRequirement") != (None if is_control else _ROLE_CONTROL_REQUIREMENT):
            raise ValidationFailure("role transfer differs from the exact prepared current-follower contract")
    elif registration.get("evaluator") == _MOUNT_BEGIN_KIND:
        original = hashlib.sha256(json.dumps(registry.get("measurementContracts", {}).get(_MOUNT_BEGIN_REQUIREMENT),
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if original != "65118364f47ee1ad27fb914b8205b467c2272c2122e9467d979ee1b5d6112b0d" \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != _MOUNT_BEGIN_CLAIMS \
                or registry.get("runners", {}).get(_MOUNT_BEGIN_REQUIREMENT) != _MOUNT_BEGIN_CLAIMS \
                or registry.get("runnerKinds", {}).get(_MOUNT_BEGIN_REQUIREMENT) != "controlled-case" \
                or test["requirements"] != [_MOUNT_BEGIN_REQUIREMENT] or test["mode"] != "prepared" \
                or test["subjects"] != [{"id":"mankey", "species":56, "role":"MOUNTED", "acquire":"existing"}] \
                or test.get("measurements") not in (None, []) \
                or registration.get("recorderControlRequirement") != _ROLE_CONTROL_REQUIREMENT:
            raise ValidationFailure("mount begin differs from its original seven-row current-follower contract")
    elif registration.get("evaluator") == "actor-binding-context-v1":
        expected_rows = [{"name": name, "operator": "eq", "type": "integer",
                          "validator": "meaningful-observation", "expected": expected}
                         for name, expected in (("binding-live-subject-count", 1),
                             ("binding-owner-context-mismatch-count", 0), ("binding-identity-failure-count", 0))]
        if registration.get("proofLevel") != "S3" or registration.get("claims") != ["live-actor-identity"] \
                or test["requirements"] != ["legacy.actor-binding-current-context"] or test["mode"] != "normal" \
                or test["subjects"] != [{"id": "rattata", "species": 19, "role": "WILD", "acquire": "existing"}] \
                or test.get("measurements") != [{"kind": "actor-binding-context-v1", "subject": "rattata"}] \
                or registry["measurementContracts"].get("legacy.actor-binding-current-context") != {"live-actor-identity": expected_rows}:
            raise ValidationFailure("binding test differs from its original public context contract")
    elif registration.get("evaluator") == "current-actor-identity-v1":
        if registration.get("proofLevel") not in ("S3", "S5") or registration.get("claims") != ["live-actor-identity"]:
            raise ValidationFailure("shared test needs an implemented exact measurement adapter")
    elif registration.get("evaluator") == "acceleration-parity-v1":
        from tools.overworld.devtools_acceleration_acceptance import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != CLAIMS \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != CLAIMS \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") != _WALK_POLICY_CONTROL_REQUIREMENT \
                or test["subjects"] != [dict(id="wild-onix", species=95, role="WILD", acquire="existing"),
                                        dict(id="mounted-onix", species=95, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind="acceleration-parity-v1",
                    subjects={"WILD": "wild-onix", "MOUNTED": "mounted-onix"})]:
            raise ValidationFailure("acceleration changed its full two-role native contract")
    elif registration.get("evaluator") == _MOUNT_PACING_KIND:
        from tools.overworld.devtools_mount_pacing_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registration.get("proofLevel") != "S4" or registration.get("claims") != list(CLAIMS) \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") != _MOUNT_POSE_CONTROL_REQUIREMENT \
                or test["subjects"] != [dict(id="cyndaquil", species=155, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNT_PACING_KIND, subject="cyndaquil")]:
            raise ValidationFailure("mounted pacing changed its original nine-row contract")
    elif registration.get("evaluator") == _MOUNT_CONTROL_STRESS_KIND:
        from tools.overworld.devtools_mount_control_stress_proof import (
            contract, CLAIMS, REQUIREMENTS, WALK_REQUIREMENT, HOP_REQUIREMENT,
        )
        registered_requirements = registration.get("requirements")
        requirement = registered_requirements[0] if isinstance(registered_requirements, list) \
            and len(registered_requirements) == 1 else None
        expected = {
            WALK_REQUIREMENT: ("cyndaquil", 155, "walk"),
            HOP_REQUIREMENT: ("mankey", 56, "hop"),
        }.get(requirement)
        if requirement not in REQUIREMENTS or expected is None \
                or registry.get("measurementContracts", {}).get(requirement) != contract(requirement) \
                or registry.get("runners", {}).get(requirement) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(requirement) != "controlled-case" \
                or registration.get("proofLevel") != "S5" \
                or registration.get("claims") != list(CLAIMS) \
                or test["requirements"] != [requirement] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id=expected[0], species=expected[1], role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNT_CONTROL_STRESS_KIND,
                                                      subject=expected[0], contract=expected[2])]:
            raise ValidationFailure("mounted control stress changed its original species contract")
    elif registration.get("evaluator") == _MOUNTED_HOP_ARC_KIND:
        from tools.overworld.devtools_mounted_hop_arc_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S4" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNTED_HOP_ARC_KIND,
                                                      subject="mankey", contract=REQUIREMENT)]:
            raise ValidationFailure("mounted Hop arc changed its exact three-case contract")
    elif registration.get("evaluator") == _MOUNTED_NEAREST_DIAGONAL_KIND:
        from tools.overworld.devtools_mounted_nearest_diagonal_proof import contract, CLAIMS
        from tools.overworld.devtools_mounted_nearest_diagonal import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNTED_NEAREST_DIAGONAL_KIND,
                                                      subject="mankey", contract=REQUIREMENT)]:
            raise ValidationFailure("nearest diagonal changed its exact one-case contract")
    elif registration.get("evaluator") == _WILD_LEDGE_KIND:
        from tools.overworld.devtools_wild_ledge_proof import contract, CLAIMS, REQUIREMENTS
        if any(registry.get("measurementContracts", {}).get(requirement) != contract(requirement)
               or registry.get("runners", {}).get(requirement) != list(CLAIMS)
               or registry.get("runnerKinds", {}).get(requirement) != "controlled-case"
               for requirement in REQUIREMENTS) \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != list(REQUIREMENTS) \
                or test["requirements"] != list(REQUIREMENTS) or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="clefairy", species=35, role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(kind=_WILD_LEDGE_KIND, subject="clefairy")]:
            raise ValidationFailure("wild ledge changed its exact bidirectional Hop contract")
    elif registration.get("evaluator") == _WILD_TELEPORT_KIND:
        from tools.overworld.devtools_wild_teleport_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="gastly", species=92, role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(kind=_WILD_TELEPORT_KIND, subject="gastly")]:
            raise ValidationFailure("wild Teleport changed its exact natural lifecycle contract")
    elif registration.get("evaluator") == _RUNNER_STOP_SKID_KIND:
        from tools.overworld.devtools_runner_stop_skid_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="stantler", species=234,
                                              role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(
                    kind=_RUNNER_STOP_SKID_KIND, subject="stantler")]:
            raise ValidationFailure(
                "Runner stop skid changed its exact normal NONE contract")
    elif registration.get("evaluator") == _RUNNER_TURN_RUNWAY_KIND:
        from tools.overworld.devtools_runner_turn_runway_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="stantler", species=234,
                                              role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(
                    kind=_RUNNER_TURN_RUNWAY_KIND, subject="stantler")]:
            raise ValidationFailure(
                "Runner turn runway changed its exact blocked-corridor contract")
    elif registration.get("evaluator") == _WILD_TRANSITION_KIND:
        from tools.overworld.devtools_wild_transition_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="rattata", species=19, role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(kind=_WILD_TRANSITION_KIND, subject="rattata")]:
            raise ValidationFailure("Wild transition changed its exact invalidation contract")
    elif registration.get("evaluator") == _FOLLOWER_TRANSITION_KIND:
        from tools.overworld.devtools_follower_transition_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("mode") != "prepared" \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="cyndaquil", species=155, role="FOLLOWER", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_FOLLOWER_TRANSITION_KIND, subject="cyndaquil")]:
            raise ValidationFailure("Follower transition changed its exact rebind contract")
    elif registration.get("evaluator") == _MOUNTED_STREAMING_KIND:
        from tools.overworld.devtools_mounted_streaming_proof import contract, CLAIMS
        from tools.overworld.devtools_mounted_streaming_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="ledyba", species=165,
                                              role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNTED_STREAMING_KIND,
                                                      subject="ledyba")]:
            raise ValidationFailure("mounted streaming changed its exact public path contract")
    elif registration.get("evaluator") == _MOUNTED_CARDINAL_STREAMING_KIND:
        from tools.overworld.devtools_mounted_cardinal_streaming_proof import contract, CLAIMS
        from tools.overworld.devtools_mounted_cardinal_streaming_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="cyndaquil", species=155,
                                              role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(
                    kind=_MOUNTED_CARDINAL_STREAMING_KIND, subject="cyndaquil")]:
            raise ValidationFailure("cardinal streaming changed its exact held-route contract")
    elif registration.get("evaluator") == _MOUNTED_HOP_TRANSITION_KIND:
        from tools.overworld.devtools_mounted_hop_transition_proof import contract, CLAIMS
        from tools.overworld.devtools_mounted_hop_transition_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S5" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56,
                                              role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(
                    kind=_MOUNTED_HOP_TRANSITION_KIND, subject="mankey")]:
            raise ValidationFailure("mounted Hop transition changed its exact rebound contract")
    elif registration.get("evaluator") == _MOUNTED_WALK_TRANSITION_KIND:
        from tools.overworld.devtools_mounted_walk_transition_proof import contract, CLAIMS
        from tools.overworld.devtools_mounted_walk_transition_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S4" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="cyndaquil", species=155,
                                              role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(
                    kind=_MOUNTED_WALK_TRANSITION_KIND, subject="cyndaquil")]:
            raise ValidationFailure("mounted Walk transition changed its exact rebound contract")
    elif registration.get("evaluator") == _LAND_SURF_KIND:
        from tools.overworld.devtools_land_surf_proof import contract, CLAIMS
        from tools.overworld.devtools_land_surf_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56,
                                              role="FOLLOWER", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_LAND_SURF_KIND,
                                                      subject="mankey")]:
            raise ValidationFailure("land/surf changed its exact Tentacool contract")
    elif registration.get("evaluator") == _SPAWN_WORK_BUDGET_KIND:
        from tools.overworld.devtools_spawn_work_budget_proof import contract, CLAIMS
        from tools.overworld.devtools_spawn_work_budget_measurement import REQUIREMENT
        if registration.get("measurementContract") != contract() \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "normal" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56,
                                              role="FOLLOWER", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_SPAWN_WORK_BUDGET_KIND,
                                                      subject="mankey")]:
            raise ValidationFailure("spawn-work changed its exact Route 30 contract")
    elif registration.get("evaluator") == _UNMOUNTED_ZERO_STUTTER_KIND:
        from tools.overworld.devtools_unmounted_zero_stutter_proof import contract, CLAIMS
        from tools.overworld.devtools_unmounted_zero_stutter_measurement import REQUIREMENT
        if registration.get("measurementContract") != contract() \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "normal" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56,
                                              role="FOLLOWER", acquire="existing")] \
                or test.get("measurements") != [dict(
                    kind=_UNMOUNTED_ZERO_STUTTER_KIND, subject="mankey")]:
            raise ValidationFailure("zero-stutter test changed its exact spawn-work route")
    elif registration.get("evaluator") == _POPULATION_FAST_TRAVEL_KIND:
        from tools.overworld.devtools_population_fast_travel_proof import contract, CLAIMS
        from tools.overworld.devtools_population_fast_travel_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mankey", species=56,
                                              role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_POPULATION_FAST_TRAVEL_KIND,
                                                      subject="mankey")]:
            raise ValidationFailure("population fast travel changed its exact refill contract")
    elif registration.get("evaluator") == _WARP_GATE_KIND:
        from tools.overworld.devtools_warp_gate_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" or registration.get("proofLevel") != "S3" or registration.get("claims") != list(CLAIMS) or registration.get("requirements") != [REQUIREMENT] or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" or registration.get("recorderControlRequirement") is not None or test.get("measurements") != [dict(kind=_WARP_GATE_KIND,subject="cyndaquil")]:
            raise ValidationFailure("warp gate changed its exact door contract")
    elif registration.get("evaluator") == _WILD_BATTLE_HANDOFF_KIND:
        from tools.overworld.devtools_wild_battle_handoff_proof import contract, CLAIMS
        from tools.overworld.devtools_wild_battle_handoff_measurement import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="rattata", species=19,
                                              role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(
                    kind=_WILD_BATTLE_HANDOFF_KIND, subject="rattata")]:
            raise ValidationFailure("Wild battle handoff changed its exact request contract")
    elif registration.get("evaluator") == _MOUNTED_TELEPORT_MATRIX_KIND:
        from tools.overworld.devtools_mounted_teleport_matrix_proof import contract, CLAIMS
        from tools.overworld.devtools_mounted_teleport_matrix import REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S4" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [REQUIREMENT] \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="cyndaquil", species=155, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNTED_TELEPORT_MATRIX_KIND,
                                                      subject="cyndaquil")]:
            raise ValidationFailure("mounted Teleport changed its exact ten-case timing contract")
    elif registration.get("evaluator") == _APPEAR_HOP_KIND:
        from tools.overworld.devtools_appear_hop_proof import contract, CLAIMS
        if registration.get("measurementContract") != contract() \
                or registration.get("proofLevel") != "S4" \
                or registration.get("claims") != list(CLAIMS) \
                or registration.get("requirements") != [_APPEAR_HOP_REQUIREMENT] \
                or test["requirements"] != [_APPEAR_HOP_REQUIREMENT] \
                or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="clefairy", species=35,
                                              role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(
                    kind=_APPEAR_HOP_KIND, subject="clefairy")]:
            raise ValidationFailure("Appear Hop changed its exact timing contract")
    elif (adapter := get_adapter(registration.get("evaluator"))) is not None:
        current_contract = not adapter.requirement.startswith("legacy.")
        actual_contract = (registration.get("measurementContract")
            if adapter.is_control or current_contract else
            registry.get("measurementContracts", {}).get(adapter.requirement))
        if actual_contract != adapter.contract() or registration.get("proofLevel") != adapter.proof_level \
                or registration.get("claims") != list(adapter.claims) \
                or test["requirements"] != [adapter.requirement] \
                or test["mode"] != ("observer-control" if adapter.is_control else "prepared") \
                or registration.get("recorderControlRequirement") != adapter.recorder_control_requirement \
                or test["subjects"] != [dict(id="cyndaquil", species=155, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=adapter.kind, subject="cyndaquil")] \
                or (not adapter.is_control and not current_contract
                    and registry.get("runners", {}).get(adapter.requirement) != list(adapter.claims)):
            raise ValidationFailure(adapter.kind + " changed its exact measurement or reader contract")
    elif registration.get("evaluator") == _WILD_WALK_KIND:
        from tools.overworld.devtools_wild_walk_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != list(CLAIMS) \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != list(CLAIMS) \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") != _WILD_CLEAR_CONTROL_REQUIREMENT \
                or test["subjects"] != [dict(id="rattata", species=19, role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(kind=_WILD_WALK_KIND, subject="rattata")]:
            raise ValidationFailure("natural Wild Walk changed its original seven-row contract")
    elif registration.get("evaluator") == _WILD_CLEAR_CONTROL_KIND:
        from tools.overworld.devtools_wild_clear_control_proof import contract
        if registration.get("measurementContract") != contract() \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != _RECORDER_CLAIMS \
                or test["requirements"] != [_WILD_CLEAR_CONTROL_REQUIREMENT] or test["mode"] != "observer-control" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="rattata", species=19, role="WILD", acquire="spawn")] \
                or test.get("measurements") != [dict(kind=_WILD_CLEAR_CONTROL_KIND, subject="rattata")]:
            raise ValidationFailure("Wild clear control changed its exact same-reader contract")
    elif registration.get("evaluator") == _MOUNT_POSE_CONTROL_KIND:
        from tools.overworld.devtools_mount_pose_control_proof import contract
        if registration.get("measurementContract") != contract() \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != _RECORDER_CLAIMS \
                or test["requirements"] != [_MOUNT_POSE_CONTROL_REQUIREMENT] or test["mode"] != "observer-control" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="cyndaquil", species=155, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_MOUNT_POSE_CONTROL_KIND, subject="cyndaquil")]:
            raise ValidationFailure("mounted pose control changed its exact same-reader contract")
    elif registration.get("evaluator") == _WALK_POLICY_CONTROL_KIND:
        from tools.overworld.devtools_walk_policy_control_proof import contract
        if registration.get("measurementContract") != contract() \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != _RECORDER_CLAIMS \
                or test["requirements"] != [_WALK_POLICY_CONTROL_REQUIREMENT] or test["mode"] != "observer-control" \
                or registration.get("recorderControlRequirement") is not None \
                or test["subjects"] != [dict(id="mounted-onix", species=95, role="MOUNTED", acquire="existing")] \
                or test.get("measurements") != [dict(kind=_WALK_POLICY_CONTROL_KIND, subject="mounted-onix")]:
            raise ValidationFailure("Walk policy control changed its exact same-reader contract")
    elif registration.get("evaluator") == "chain-retry-v1":
        from tools.overworld.chain_retry_proof import contract, CLAIMS, REQUIREMENT
        if registry.get("measurementContracts", {}).get(REQUIREMENT) != contract() \
                or registry.get("runners", {}).get(REQUIREMENT) != CLAIMS \
                or registry.get("runnerKinds", {}).get(REQUIREMENT) != "controlled-case" \
                or registration.get("proofLevel") != "S3" or registration.get("claims") != CLAIMS \
                or test["requirements"] != [REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") != _LEDYBA_RECORDER_REQUIREMENT:
            raise ValidationFailure("chain retry changed its reviewed native/profile contract")
    elif registration.get("evaluator") == "ledyba-chain-v1":
        _shared_ledyba_contract(registry)
        subjects = test["subjects"]
        if registration.get("proofLevel") != "S4" or registration.get("claims") != _LEDYBA_CLAIMS \
                or test["requirements"] != [_LEDYBA_REQUIREMENT] or test["mode"] != "normal" \
                or registration.get("recorderControlRequirement") != _LEDYBA_RECORDER_REQUIREMENT \
                or len(subjects) != 1 or any(subjects[0][key] != value for key, value in
                    (("species", 165), ("role", "WILD"), ("acquire", "spawn"))) \
                or test.get("measurements") != [{"kind": "ledyba-chain-v1", "subject": subjects[0]["id"]}]:
            raise ValidationFailure("shared Ledyba test differs from the exact normal S4 contract")
    elif registration.get("evaluator") == _HEIGHT_CONTROL_KIND:
        subjects = test["subjects"]
        if (registration.get("proofLevel") != "S3" or registration.get("claims") != _RECORDER_CLAIMS
                or test["requirements"] != [_HEIGHT_CONTROL_REQUIREMENT] or test["mode"] != "observer-control"
                or registration.get("recorderControlRequirement") is not None
                or len(subjects) != 1 or any(subjects[0][key] != value for key, value in
                    (("species", 165), ("role", "WILD"), ("acquire", "spawn")))
                or test.get("measurements") != [{"kind": _HEIGHT_CONTROL_KIND, "subject": subjects[0]["id"]}]):
            raise ValidationFailure("height reader control differs from its exact native fault contract")
    elif registration.get("evaluator") == _ROUTE_CONTROL_KIND:
        _shared_route_control_contract(registry)
        subjects = test["subjects"]
        if registration.get("proofLevel") != "S3" or registration.get("claims") != _RECORDER_CLAIMS \
                or test["requirements"] != [_ROUTE_CONTROL_REQUIREMENT] or test["mode"] != "observer-control" \
                or registration.get("recorderControlRequirement") is not None \
                or len(subjects) != 1 or any(subjects[0][key] != value for key,value in
                    (("species",155),("role","FOLLOWER"),("acquire","existing"))) \
                or test.get("measurements") != [{"kind":_ROUTE_CONTROL_KIND,"subject":subjects[0]["id"],"setupTransitions":[]}]:
            raise ValidationFailure("route recorder test differs from its exact saved follower contract")
    elif registration.get("evaluator") == _CADENCE_KIND:
        from tools.overworld.route_cadence_proof import RULES
        expected_contract = {}
        for claim, name, operator, threshold in RULES:
            expected_contract.setdefault(claim, []).append({"name": name, "operator": operator,
                "type": "integer", "validator": "meaningful-observation",
                "minimum" if operator == "gte" else "expected": threshold})
        if registry.get("runners", {}).get(_CADENCE_REQUIREMENT) != _CADENCE_CLAIMS \
                or registry.get("runnerKinds", {}).get(_CADENCE_REQUIREMENT) != "normal-play" \
                or registry.get("measurementContracts", {}).get(_CADENCE_REQUIREMENT) != expected_contract:
            raise ValidationFailure("route adapter changed its original ten measurements")
        subjects = test["subjects"]
        if registration.get("proofLevel") != "S5" or registration.get("claims") != _CADENCE_CLAIMS \
                or test["requirements"] != [_CADENCE_REQUIREMENT] or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") != _ROUTE_CONTROL_REQUIREMENT \
                or len(subjects) != 1 or any(subjects[0][key] != value for key,value in
                    (("species",155),("role","FOLLOWER"),("acquire","existing"))) \
                or test.get("measurements") != [{"kind":_CADENCE_KIND,"subject":subjects[0]["id"],"setupTransitions":[]}]:
            raise ValidationFailure("route differs from its exact prepared-fixture normal-movement contract")
    elif registration.get("evaluator") == _GAME_CADENCE_KIND:
        from tools.overworld.cadence_diagnostics import UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS
        from tools.overworld.route_cadence_proof import RULES
        expected_contract = {}
        for claim, name, operator, threshold in RULES[:-1]:
            expected_contract.setdefault(claim, []).append({"name": name, "operator": operator,
                "type": "integer", "validator": "meaningful-observation",
                "minimum" if operator == "gte" else "expected": threshold})
        if registration.get("measurementContract") != expected_contract \
                or registration.get("proofLevel") != "S5" \
                or registration.get("claims") != _GAME_CADENCE_CLAIMS \
                or registration.get("guestQueueBudgetArm9Ticks") != UNMOUNTED_FULL_ROUTE_MAX_TWO_QUEUE_ARM9_TICKS \
                or test["requirements"] != [_GAME_CADENCE_REQUIREMENT] \
                or test["mode"] != "prepared" \
                or registration.get("recorderControlRequirement") != _ROUTE_CONTROL_REQUIREMENT:
            raise ValidationFailure("current game cadence changed its exact nine-row guest contract")
        subjects = test["subjects"]
        if (len(subjects) != 1
                or any(subjects[0][key] != value for key, value in
                       (("species", 155), ("role", "FOLLOWER"), ("acquire", "existing")))
                or test.get("measurements") != [{"kind": _GAME_CADENCE_KIND,
                                                  "subject": subjects[0]["id"],
                                                  "setupTransitions": []}]):
            raise ValidationFailure("current game cadence differs from its exact prepared-fixture route")
    elif registration.get("evaluator") in _POOL_KINDS:
        subjects = test["subjects"]
        kind = registration["evaluator"]
        surface = kind == "pool-spawn-surface-v1"
        claims = _POOL_SURFACE_CLAIMS if surface else _POOL_CLAIMS
        requirements = [_POOL_REQUIREMENT, _POOL_SURFACE_REQUIREMENT] if surface else [_POOL_REQUIREMENT]
        if registration.get("proofLevel") != "S3" or registration.get("claims") != claims \
                or test["requirements"] != requirements or test["mode"] != "normal" \
                or registration.get("recorderControlRequirement") != _LEDYBA_RECORDER_REQUIREMENT \
                or len(subjects) != 1 or any(subjects[0][key] != value for key, value in
                    (("species", 165), ("role", "WILD"), ("acquire", "spawn"))) \
                or test.get("measurements") != [{"kind": kind, "subject": subjects[0]["id"]}]:
            raise ValidationFailure("shared POOL test differs from its exact normal own-site contract")
    elif registration.get("evaluator") == "live-observer-control-v1":
        _shared_recorder_contract(registry)
        _shared_ledyba_contract(registry)
        subjects = test["subjects"]
        if registration.get("proofLevel") != "S3" or registration.get("claims") != _RECORDER_CLAIMS \
                or test["requirements"] != [_LEDYBA_RECORDER_REQUIREMENT] or test["mode"] != "observer-control" \
                or registration.get("recorderControlRequirement") is not None \
                or len(subjects) != 1 or any(subjects[0][key] != value for key, value in
                    (("species", 165), ("role", "WILD"), ("acquire", "spawn"))) \
                or test.get("measurements") != [{"kind": "live-observer-control-v1", "subject": subjects[0]["id"]}]:
            raise ValidationFailure("shared live recorder test differs from the exact separate control contract")
    else:
        raise ValidationFailure("shared test needs an implemented exact measurement adapter")
    if registration.get("recipeSha256") != recipe_hash or validate_test(json.loads(path.read_text())) != test:
        raise ValidationFailure("shared test differs from its reviewed recipe identity")
    if registration.get("mode") != test["mode"] or registration.get("requirements") != test["requirements"]:
        raise ValidationFailure("shared test scope differs from its reviewed registration")
    minimum = registration.get("minimumObservedFrames")
    if type(minimum) is not int or minimum < 1 or test["budgets"]["minObservedFrames"] < minimum:
        raise ValidationFailure("shared test weakened its registered observation floor")
    if registration["proofLevel"] == "S5" and minimum < 5000:
        raise ValidationFailure("shared identity soak needs at least 5000 continuous observed frames")
    return registration, recipe_hash


def prepare_shared_test(test: dict[str, Any], repo: Path = REPO, *, deadline=None, cancel_event=None) -> dict[str, Any]:
    """Current non-gameplay preflight for registered shared proof, before boot."""
    _require_current_controller()
    registration, recipe_hash = _shared_test_registration(test, repo)
    if registration is None:
        return {"passed": True, "eligible": False, "acceptedProof": False,
                "reason": "unregistered tool test; diagnostic only"}
    from scripts.verify_overworld_runtime_fixture import verify
    from tools.overworld.proof_inputs import proof_inputs
    scoped = proof_inputs(repo, test)
    before = source_record(repo)
    fixture = verify(repo / test["fixture"]["rom"], deadline=deadline, cancel_event=cancel_event)
    after = source_record(repo)
    result = {"schemaVersion": 1, "passed": fixture.get("passed") is True and before == after,
            "eligible": True, "acceptedProof": False, "source": before, "proofInputs": scoped,
            "registration": registration, "testSourceSha256": recipe_hash,
            "fixture": fixture, "reason": None if before == after else "source changed during preflight"}
    if result["passed"] and registration.get("recorderControlRequirement") is not None:
        try:
            result["recorderControlArtifact"] = _find_shared_recorder_control(test, registration, before, repo,
                deadline=deadline, cancel_event=cancel_event)
        except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
            result.update(passed=False, reason="required current live recorder control unavailable: " + str(error))
    if result["passed"] and registration.get("evaluator") == "pool-spawn-surface-v1":
        try:
            result["surfaceRecorderControlArtifact"] = _find_shared_recorder_control(test,
                {"recorderControlRequirement": _HEIGHT_CONTROL_REQUIREMENT}, before, repo,
                deadline=deadline, cancel_event=cancel_event)
        except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
            result.update(passed=False, reason="required current height recorder control unavailable: " + str(error))
    return result


def _shared_artifact(record: Any, parent: Path) -> Path:
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        raise ValidationFailure("shared proof artifact is missing")
    path = Path(record["path"])
    if path.is_symlink() or not path.resolve().is_relative_to(parent.resolve()) or not path.is_file():
        raise ValidationFailure("shared proof artifact is not owned by this run")
    actual = file_record(path, parent)
    if actual["size"] < 1 or actual["sha256"] != record.get("sha256") \
            or ("size" in record and actual["size"] != record["size"]):
        raise ValidationFailure("shared proof artifact hash/size differs")
    return path


def _replay_shared_test(test: dict[str, Any], rows: list[dict[str, Any]], *, fault: str | None = None,
                        repo: Path = REPO) -> dict[str, Any]:
    """Controller-owned replay; optional controls alter input to the same checker."""
    from copy import deepcopy
    from tools.overworld.devtools_test_contract import TestEvaluator
    evaluator = TestEvaluator(test)
    from tools.overworld.devtools_test_inputs import measurement_inputs
    evaluator.install_measurements(measurement_inputs(test, repo))
    controlled = False
    route_control = None
    if fault is not None and "acceleration-parity-v1" in evaluator.measurements:
        from tools.overworld.devtools_acceleration_acceptance import AccelerationNegative, FAULTS
        if fault in FAULTS:
            route_control = AccelerationNegative(fault)
    elif fault is not None and _MOUNT_PACING_KIND in evaluator.measurements:
        from tools.overworld.devtools_mount_pacing_proof import MountedPacingNegative
        route_control = MountedPacingNegative(fault)
    elif fault is not None and _MOUNT_CONTROL_STRESS_KIND in evaluator.measurements:
        from tools.overworld.devtools_mount_control_stress_proof import MountControlStressNegative
        route_control = MountControlStressNegative(fault)
    elif fault is not None and _MOUNTED_HOP_ARC_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_hop_arc_proof import MountedHopArcNegative
        route_control = MountedHopArcNegative(fault)
    elif fault is not None and _MOUNTED_NEAREST_DIAGONAL_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_nearest_diagonal_proof import MountedNearestDiagonalNegative
        route_control = MountedNearestDiagonalNegative(fault)
    elif fault is not None and _WILD_LEDGE_KIND in evaluator.measurements:
        from tools.overworld.devtools_wild_ledge_proof import WildLedgeNegative
        route_control = WildLedgeNegative(fault)
    elif fault is not None and _WILD_TELEPORT_KIND in evaluator.measurements:
        from tools.overworld.devtools_wild_teleport_proof import WildTeleportNegative
        route_control = WildTeleportNegative(fault)
    elif fault is not None and _RUNNER_STOP_SKID_KIND in evaluator.measurements:
        from tools.overworld.devtools_runner_stop_skid_proof import RunnerStopSkidNegative
        route_control = RunnerStopSkidNegative(fault)
    elif fault is not None and _RUNNER_TURN_RUNWAY_KIND in evaluator.measurements:
        from tools.overworld.devtools_runner_turn_runway_proof import RunnerTurnRunwayNegative
        route_control = RunnerTurnRunwayNegative(fault)
    elif fault is not None and _WILD_TRANSITION_KIND in evaluator.measurements:
        from tools.overworld.devtools_wild_transition_proof import WildTransitionNegative
        route_control = WildTransitionNegative(fault)
    elif fault is not None and _FOLLOWER_TRANSITION_KIND in evaluator.measurements:
        from tools.overworld.devtools_follower_transition_proof import FollowerTransitionNegative
        route_control = FollowerTransitionNegative(fault)
    elif fault is not None and _MOUNTED_STREAMING_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_streaming_proof import MountedStreamingNegative
        route_control = MountedStreamingNegative(fault)
    elif fault is not None and _MOUNTED_CARDINAL_STREAMING_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_cardinal_streaming_proof import MountedCardinalStreamingNegative
        route_control = MountedCardinalStreamingNegative(fault)
    elif fault is not None and _MOUNTED_HOP_TRANSITION_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_hop_transition_proof import MountedHopTransitionNegative
        route_control = MountedHopTransitionNegative(fault)
    elif fault is not None and _MOUNTED_WALK_TRANSITION_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_walk_transition_proof import MountedWalkTransitionNegative
        route_control = MountedWalkTransitionNegative(fault)
    elif fault is not None and _LAND_SURF_KIND in evaluator.measurements:
        from tools.overworld.devtools_land_surf_proof import LandSurfNegative
        route_control = LandSurfNegative(fault)
    elif fault is not None and _SPAWN_WORK_BUDGET_KIND in evaluator.measurements:
        from tools.overworld.devtools_spawn_work_budget_proof import SpawnWorkBudgetNegative
        route_control = SpawnWorkBudgetNegative(fault)
    elif fault is not None and _UNMOUNTED_ZERO_STUTTER_KIND in evaluator.measurements:
        from tools.overworld.devtools_unmounted_zero_stutter_proof import UnmountedZeroStutterNegative
        route_control = UnmountedZeroStutterNegative(fault)
    elif fault is not None and _POPULATION_FAST_TRAVEL_KIND in evaluator.measurements:
        from tools.overworld.devtools_population_fast_travel_proof import PopulationFastTravelNegative
        route_control = PopulationFastTravelNegative(fault)
    elif fault is not None and _WARP_GATE_KIND in evaluator.measurements:
        from tools.overworld.devtools_warp_gate_proof import WarpGateNegative
        route_control = WarpGateNegative(fault)
    elif fault is not None and _WILD_BATTLE_HANDOFF_KIND in evaluator.measurements:
        from tools.overworld.devtools_wild_battle_handoff_proof import WildBattleHandoffNegative
        route_control = WildBattleHandoffNegative(fault)
    elif fault is not None and _MOUNTED_TELEPORT_MATRIX_KIND in evaluator.measurements:
        from tools.overworld.devtools_mounted_teleport_matrix_proof import MountedTeleportMatrixNegative
        route_control = MountedTeleportMatrixNegative(fault)
    elif fault is not None and _APPEAR_HOP_KIND in evaluator.measurements:
        from tools.overworld.devtools_appear_hop_proof import AppearHopNegative
        route_control = AppearHopNegative(fault)
    elif fault is not None and (adapter := next((get_adapter(kind) for kind in evaluator.measurements
                                                if get_adapter(kind) is not None), None)) is not None:
        route_control = adapter.negative(fault)
    elif fault is not None and _WILD_WALK_KIND in evaluator.measurements:
        from tools.overworld.devtools_wild_walk_proof import WildWalkNegative
        route_control = WildWalkNegative(fault)
    elif fault is not None and _WILD_CLEAR_CONTROL_KIND in evaluator.measurements:
        from tools.overworld.devtools_wild_clear_control_proof import WildClearControlNegative
        route_control = WildClearControlNegative(fault)
    elif fault is not None and _MOUNT_POSE_CONTROL_KIND in evaluator.measurements:
        from tools.overworld.devtools_mount_pose_control_proof import MountedPoseControlNegative
        route_control = MountedPoseControlNegative(fault)
    elif fault is not None and _WALK_POLICY_CONTROL_KIND in evaluator.measurements:
        from tools.overworld.devtools_walk_policy_control_proof import WalkPolicyNegative
        route_control = WalkPolicyNegative(fault)
    elif fault is not None and _ROUTE_CONTROL_KIND in evaluator.measurements:
        from tools.overworld.route_control_negatives import RouteControlNegative
        route_control = RouteControlNegative(fault)
    elif fault is not None and any(kind in evaluator.measurements for kind in _CADENCE_KINDS):
        from tools.overworld.route_cadence_negatives import CadenceNegative
        route_control = CadenceNegative(fault)
    elif fault is not None and "chain-retry-v1" in evaluator.measurements:
        from tools.overworld.devtools_chain_retry_measurement import ChainRetryNegative, RETRY_FAULTS
        if fault in RETRY_FAULTS:
            route_control = ChainRetryNegative(fault)
    pool_control_subject = None
    pool_control_finalization = None
    for row in rows:
        if not isinstance(row, dict): raise ValidationFailure("invalid observation stream row")
        if route_control is not None:
            row = route_control.mutate(row, evaluator.subjects)
            controlled = route_control.applied
        if row.get("command") == "route-control.close":
            receipt = row.get("receipt")
            if test["mode"] != "observer-control" or row.get("phase") != "cleanup" \
                    or not isinstance(receipt, dict) or evaluator.latest is None \
                    or receipt.get("frame") != evaluator.latest["frame"] \
                    or row.get("snapshot") != receipt.get("snapshot") or "samples" in row:
                raise ValidationFailure("route cleanup is not its exact same-frame terminal receipt")
            try:
                evaluator.observer_control_cleanup(receipt)
            except ValueError as error:
                if route_control is None or not route_control.applied:
                    raise
                evaluator.fail("route-control-cleanup-rejected", str(error))
                break
            continue
        if evaluator.uses_raw_records:
            if fault is not None and route_control is None:
                # Cadence controls need their own reviewed per-layer mutations;
                # never borrow a chain control or silently skip the requested fault.
                raise ValidationFailure("cadence replay controls are not yet registered")
            def verify_cadence_frame(sample, current):
                if {_MOUNTED_TELEPORT_MATRIX_KIND, _WARP_GATE_KIND}.intersection(current.measurements):
                    # These meters validate the same handle, source, engine
                    # owner and generation while Teleport visibility makes the
                    # generic attachment flag false.
                    return
                if "acceleration-parity-v1" in current.measurements and fault is None:
                    # Both motion windows are explicit prepared actions. Only
                    # their active subject is current; a sealed earlier role
                    # may have been removed by later setup.
                    active = current._acceleration_active
                    if active is not None:
                        _verify_shared_subject_observation(sample, current.subjects[active])
                elif row.get("phase") == "observe" and fault is None:
                    for subject in current.subjects.values():
                        _verify_shared_subject_observation(
                            sample,
                            subject,
                            allow_mounted_rebound=bool(
                                {_MOUNT_CONTROL_STRESS_KIND, _POPULATION_FAST_TRAVEL_KIND,
                                 _MOUNTED_WALK_TRANSITION_KIND, _MOUNTED_HOP_TRANSITION_KIND}
                                .intersection(current.measurements)
                            ),
                        )
            progress = evaluator.observe_record(row, frame_callback=verify_cadence_frame, full_report=False)
            if progress["state"] == "failed": break
            continue
        if row.get("command") in ("observer-control.close", "route-control.close"):
            receipt = row.get("receipt")
            if test["mode"] != "observer-control" or row.get("phase") != "cleanup" \
                    or not isinstance(receipt, dict) or evaluator.latest is None \
                    or receipt.get("frame") != evaluator.latest["frame"] \
                    or row.get("snapshot") != receipt.get("snapshot") or "samples" in row:
                raise ValidationFailure("native observer cleanup is not its exact same-frame terminal receipt")
            evaluator.observer_control_cleanup(receipt)
            continue  # Cleanup proves restoration, never an extra game frame.
        if "initialSnapshot" in row:
            if "actor-binding-context-v1" in evaluator.measurements:
                evaluator.observe_initial(row["initialSnapshot"], row.get("initialEvents", []),
                                          start_frame=row.get("initialEventStartFrame"))
            else:
                evaluator.observe(row["initialSnapshot"], count_frame=False)
        if row.get("command") == "chain-retry":
            action = next((item for item in test["actions"] if item["id"] == row.get("action")), None)
            if row.get("phase") != "observe" or not action or action["op"] != "chain-retry":
                raise ValidationFailure("chain retry is not its declared controlled action")
            evaluator.chain_retry_args(action["args"]["subject"])
            evaluator.measurements["chain-retry-v1"].observe_control(row.get("receipt"), row.get("snapshot"))
        if row.get("command") == "observer-control":
            action = next((item for item in test["actions"] if item["id"] == row.get("action")), None)
            receipt = row.get("receipt")
            if test["mode"] != "observer-control" or row.get("phase") != "observe" \
                    or not action or action["op"] != "observer-control" or not isinstance(receipt, dict):
                raise ValidationFailure("native observer control is not a declared control action")
            args = evaluator.observer_control_args(action["args"]["subject"], action["args"]["fault"])
            native = receipt.get("observerControl", {})
            armed = native.get("receipts", []) if isinstance(native, dict) else []
            if receipt.get("armed") is not True or receipt.get("prepared") is not True \
                    or evaluator.latest is None or receipt.get("frame") != evaluator.latest["frame"] \
                    or not isinstance(row.get("snapshot"), dict) or row["snapshot"].get("frame") != receipt["frame"] \
                    or not isinstance(native, dict) or native.get("state") != "armed" \
                    or native.get("subject") != args["subject"] or native.get("kind") != args["kind"] \
                    or not isinstance(armed, list) or len(armed) != 1 or not isinstance(armed[0], dict) \
                    or armed[0].get("action") != "armed" \
                    or armed[0].get("subject") != args["subject"] or armed[0].get("kind") != args["kind"] \
                    or armed[0].get("maxFrames") != args["maxFrames"] or armed[0].get("frame") != receipt["frame"]:
                raise ValidationFailure("retained native observer-control arm differs from the approved subject/fault/boundary")
        if row.get("command") in ("party", "spawn") and "setupBoundary" in row.get("receipt", {}):
            if evaluator.observe_prepared_command(row)["state"] == "failed":
                break
            continue
        boundary = row.get("boundarySnapshot")
        if boundary is None and row.get("command") not in (None, "bind"):
            boundary = row.get("snapshot")
        if boundary is not None:
            if not isinstance(boundary, dict) or type(boundary.get("frame")) is not int:
                raise ValidationFailure("setup boundary lacks its coherent frame")
            if test.get("id") == "mount.begin-current-follower" and "boundarySnapshot" in row:
                if set(row) != {"phase", "boundarySnapshot", "startEvents", "startFrame"} or row["phase"] != "observe":
                    raise ValidationFailure("mount start boundary lacks its exact retained prefix")
                evaluator.observe_start_boundary(boundary, row["startEvents"], start_frame=row["startFrame"])
                if evaluator.result()["state"] == "failed": break
            elif evaluator.latest is None or boundary["frame"] > evaluator.latest["frame"]:
                evaluator.observe(boundary, count_frame=False)
            elif boundary["frame"] != evaluator.latest["frame"]:
                raise ValidationFailure("setup boundary moved backwards")
        if row.get("command") == "bind":
            receipt, snapshot = row.get("receipt"), row.get("snapshot")
            action = next((item for item in test["setup"] + test["actions"] if item["id"] == row.get("action")), None)
            if not action or action["op"] != "bind" or not isinstance(snapshot, dict):
                raise ValidationFailure("binding receipt does not match a declared action")
            try:
                bound = evaluator.bind(action["args"]["subject"], snapshot)
            except ValueError as error:
                if fault and fault.startswith("binding-") and controlled:
                    evaluator.fail("binding-control-rejected", str(error))
                    return evaluator.finish()
                raise
            if bound != receipt: raise ValidationFailure("retained binding differs from current full identity")
        if row.get("command") == "skip":
            action = next((item for item in test["setup"] if item["id"] == row.get("action")), None)
            if not action or not action.get("skipIf") or not evaluator.check(action["skipIf"], row["snapshot"]):
                raise ValidationFailure("setup skip lacks its declared true observed condition")
        if "samples" not in row: continue
        samples, events = row["samples"], row.get("events", [])
        if not isinstance(samples, list) or row.get("completedGameFrames") != len(samples) or not samples:
            raise ValidationFailure("observation chunk has missing complete game frames")
        frames = [sample.get("frame") for sample in samples if isinstance(sample, dict)]
        if len(frames) != len(samples) or any(not isinstance(event, dict) or event.get("frame") not in frames for event in events):
            raise ValidationFailure("chunk events are not tied to its coherent frames")
        for sample in samples:
            sample_events = [event for event in events if event["frame"] == sample["frame"]]
            # The evaluator owns its retained snapshot copy. Only controller
            # fault injection can change this input; isolate that path without
            # copying every untouched setup and normal frame a second time.
            can_mutate = bool(fault) and (fault.startswith("pool-") or (
                (not controlled or fault == "binding-missing-return")
                and (fault.startswith("binding-") or fault in _HEIGHT_MEANING_CONTROLS
                     or (row.get("phase") == "observe" and evaluator.subjects))))
            if can_mutate:
                sample = deepcopy(sample)
                sample_events = [deepcopy(event) for event in sample_events]
            if fault in ("pool-missing-finalization", "pool-replaced-site"):
                for event in sample_events:
                    data = event.get("data", {})
                    if event.get("kind") != "native-observation" \
                            or data.get("observation") != "spawn-finalized" \
                            or data.get("returnValue") != 1 \
                            or data.get("preparedEncounter", {}).get("species") != 165 \
                            or pool_control_finalization is not None:
                        continue
                    if fault == "pool-missing-finalization":
                        data["observation"] = "spawn-finalization-removed"
                        pool_control_finalization = {}
                    else:
                        raw = bytearray.fromhex(data["inputPrefixHex"])
                        x = int.from_bytes(raw[:4], "little", signed=True)
                        x = x + 1 if x < 32767 else x - 1
                        raw[:4] = x.to_bytes(4, "little", signed=True)
                        data["inputPrefixHex"] = raw.hex()
                        data["inputPosition"][0] = x
                        pool_control_finalization = deepcopy(data)
                    controlled = True
                    break
            if fault and fault.startswith("binding-") and (not controlled or fault == "binding-missing-return"):
                if "actor-binding-context-v1" not in evaluator.measurements:
                    raise ValidationFailure("binding control requires its exact measurement")
                for event in sample_events:
                    data = event.get("data", {})
                    if fault in ("binding-wrong-return", "binding-missing-return") \
                            and event.get("kind") == "native-observation" \
                            and data.get("observation") == "actor-binding-context" and data.get("candidates"):
                        if fault == "binding-wrong-return":
                            data["packedContext"] ^= 0x10000
                            data["returnValue"] = data["packedContext"]
                        else:
                            data["observation"] = "binding-return-removed"
                        controlled = True
                        if fault == "binding-wrong-return":
                            break
                    if fault.startswith("binding-missing:") and event.get("kind") == "native" \
                            and data.get("event") == fault.split(":", 1)[1]:
                        binding_report = evaluator.measurements["actor-binding-context-v1"].result()
                        subject = binding_report.get("subject")
                        handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
                        meaning = data.get("event")
                        if meaning == "MOTION_STARTED" and data.get("valueA") != 1:
                            continue
                        if meaning in ("LOGICAL_COMMIT", "MOTION_FINISHED") and data.get("valueB") != 1:
                            continue
                        if meaning == "CONTROL_RETURNED" and not binding_report.get("lifecycleEvents") \
                                and not any(e.get("kind") == "native" and e.get("data", {}).get("event") == "MOTION_STARTED"
                                            and e["data"].get("valueA") == 1
                                            and {"value": e["data"].get("actorHandle"), **e["data"].get("actor", {})} == handle
                                            for e in sample_events):
                            continue
                        if subject and handle == subject["handle"]:
                            data["event"] = "WORLD_EFFECT"
                            controlled = True
                            break
            if fault in _HEIGHT_MEANING_CONTROLS and not controlled:
                if _HEIGHT_CONTROL_KIND not in evaluator.measurements:
                    raise ValidationFailure("height control requires the exact native height measurement")
                for event in sample_events:
                    data = event.get("data", {})
                    if (event.get("kind") == "native-observation"
                            and data.get("observation") == "spawn-height-read-control"
                            and data.get("clean", {}).get("sourceIdentity", {}).get("species") == 165):
                        if fault == "height-control-missing-meaning":
                            data["observation"] = "height-control-meaning-removed"
                        else:
                            data["restored"]["positionAfter"]["pos_y"] += 1
                        controlled = True
                        break
            if fault and fault.startswith("pool-"):
                if not any(kind in evaluator.measurements for kind in _POOL_KINDS):
                    raise ValidationFailure("POOL control requires the exact POOL measurement")
                for event in sample_events:
                    data = event.get("data", {})
                    if data.get("observation") == "spawn-prepared" and data.get("returnValue") == 1 \
                            and data.get("publicSubject", {}).get("species") == 165 \
                            and data.get("publicSubject", {}).get("role") == "WILD" and pool_control_subject is None:
                        pool_control_subject = data["publicSubject"]["handle"]
                        if fault == "pool-replaced-site" and isinstance(pool_control_finalization, dict) \
                                and pool_control_finalization \
                                and data.get("finalization", {}).get("receipt", {}).get("finalizationId") \
                                == pool_control_finalization.get("finalizationId"):
                            data["finalization"]["receipt"] = deepcopy(pool_control_finalization)
                        elif fault in _POOL_SURFACE_CONTROLS and not controlled:
                            if "pool-spawn-surface-v1" not in evaluator.measurements:
                                raise ValidationFailure("surface control requires the stronger POOL measurement")
                            _erase_pool_surface_meaning(data, sample_events, fault)
                            controlled = True
                if fault.startswith("pool-missing-meaning:"):
                    name = fault.split(":", 1)[1]
                    if name not in _LEDYBA_REQUIRED_MEANINGS:
                        raise ValidationFailure("unknown POOL terminal control")
                    if not controlled:
                        for event in sample_events:
                            data = event.get("data", {})
                            handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
                            if event.get("kind") == "native" and handle == pool_control_subject \
                                    and data.get("event") == name:
                                data["event"] = "WORLD_EFFECT"
                                controlled = True
                                break
                elif fault not in ("pool-missing-finalization", "pool-replaced-site", *_POOL_SURFACE_CONTROLS):
                    raise ValidationFailure("unknown POOL replay control")
            if row.get("phase") == "observe" and not fault and test["mode"] != "observer-control":
                for subject in evaluator.subjects.values():
                    _verify_shared_subject_observation(
                        sample,
                        subject,
                        allow_mounted_rebound=_MOUNT_CONTROL_STRESS_KIND in evaluator.measurements,
                    )
            if (row.get("phase") == "observe" and evaluator.subjects and fault and not controlled and route_control is None
                    and not fault.startswith(("pool-", "binding-")) and fault not in _HEIGHT_MEANING_CONTROLS):
                handles = [item["handle"] for item in evaluator.subjects.values()]
                if fault == "absent-subject":
                    sample["actors"] = [actor for actor in sample["actors"] if actor.get("handle") not in handles]
                elif fault == "stale-subject":
                    sample["context"]["mapGeneration"] += 1
                elif fault.startswith("missing-meaning:") and fault.split(":", 1)[1] in _LEDYBA_REQUIRED_MEANINGS:
                    for event in sample_events:
                        data = event.get("data", {})
                        handle = {"value": data.get("actorHandle"), **data.get("actor", {})}
                        if event.get("kind") == "native" and handle in handles and data.get("event") == fault.split(":", 1)[1]:
                            # Keep sequence/actor/frame coverage intact. Only
                            # erase the required meaning in this copied row.
                            data["event"] = "WORLD_EFFECT"
                            controlled = True
                            break
                else: raise ValidationFailure("unknown replay control")
                if fault in ("absent-subject", "stale-subject"):
                    controlled = True
            evaluator.observe(sample, sample_events,
                              count_frame=row.get("phase") == "observe")
            if fault and controlled and evaluator.result().get("state") == "failed":
                return evaluator.finish()  # Never arm a later live fault after a rejected baseline control.
            if row.get("phase") == "observe" and not fault and test["mode"] == "observer-control":
                for subject in evaluator.subjects.values():
                    if not evaluator.expected_control_identity_failure(sample, subject):
                        _verify_shared_subject_observation(sample, subject)
    result = evaluator.finish()
    if fault and not controlled: raise ValidationFailure("negative control never reached the selected live subject")
    return result


def _verify_shared_subject_observation(
    snapshot: dict[str, Any],
    subject: dict[str, Any],
    *,
    allow_mounted_rebound: bool = False,
) -> None:
    """Recheck retained engine membership data, not just identityVerified=True."""
    from tools.overworld.devtools_records import select_current_actor
    from tools.overworld.spawn_identity import live_spawn_flags
    if allow_mounted_rebound:
        actors = [
            item for item in snapshot.get("actors", [])
            if item.get("active") is True
            and item.get("subjectIdentity") == subject.get("subjectIdentity")
            and item.get("species") == subject.get("species")
            and item.get("role") in ("MOUNTED", "FOLLOWER")
        ]
        if len(actors) != 1:
            raise ValidationFailure("mounted rebound must name one current stable subject")
        actor = actors[0]
        subject = {key: actor[key] for key in ("handle", "subjectIdentity", "species", "role")}
    selected = select_current_actor(snapshot, subject)
    actor = next(item for item in snapshot["actors"] if item.get("handle") == selected["handle"])
    source, engine, context = actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}), snapshot["context"]
    slot = selected["handle"]["slot"]
    role_slot = (actor["role"] == "WILD" and slot < 7) or (actor["role"] in ("FOLLOWER", "MOUNTED") and slot == 7)
    checks = [role_slot, live_spawn_flags(source.get("active")), source.get("species") == actor["species"],
              source.get("personality") == actor["subjectIdentity"],
              source.get("encounter_generation") == selected["handle"]["encounterGeneration"],
              engine.get("in_manager") is True, engine.get("active") is True,
              engine.get("script_id") == 2074,
              source.get("object_id") == engine.get("object_id") == 0xE0 + slot,
              source.get("map_id") == engine.get("object_map_id") == context.get("mapId"),
              engine.get("current_map_id") == context.get("mapId")]
    for field in ("pointer", "current_manager", "object_manager"):
        value = engine.get(field)
        checks.append(type(value) is int and 0x02000000 <= value < 0x02400000)
    checks.extend([source.get("object") == engine.get("pointer"),
                   engine.get("object_manager") == engine.get("current_manager"),
                   type(engine.get("manager_index")) is int and engine["manager_index"] >= 0])
    if not all(checks): raise ValidationFailure("retained actor/source/engine identity does not agree")


def _shared_ledyba_measurements(replay: dict[str, Any]) -> list[dict[str, Any]]:
    meter = replay.get("measurements", {}).get("ledyba-chain-v1", {})
    if meter.get("passed") is not True or meter.get("ready") is not True \
            or any(meter.get(key) != [] for key in ("identityErrors", "observationErrors", "failures", "measurementErrors")):
        raise ValidationFailure("shared Ledyba replay lacks complete identity/motion/observation coverage")
    values = (meter.get("identitySamples"), meter.get("selectedProfileObservationCount"),
              len(meter["intervals"]), len(meter["chainErrors"]), len(meter["renderErrors"]),
              len(meter["actions"]), int(meter.get("spawnPassed") is True))
    measured = []
    for (claim, suffix, operator, threshold), value in zip(_LEDYBA_MEASUREMENT_RULES, values):
        if type(value) is not int or (value < threshold if operator == "gte" else value != threshold):
            raise ValidationFailure("shared Ledyba measurement failed: " + suffix)
        measured.append({"claim": claim, "name": "normal-ledyba-" + suffix,
                         "value": value, "operator": operator, "threshold": threshold, "passed": True})
    return measured


def _erase_pool_surface_meaning(spawn: dict[str, Any], events: list[dict[str, Any]], fault: str) -> None:
    """Change one native meaning in every exact copy; never the retained rows."""
    from copy import deepcopy
    height = spawn["jumpReceipts"][0]["landingHeight"]
    sequence = height["sequence"]
    if fault == "pool-surface-missing-query":
        height["surfaceQuery"] = None
    elif fault == "pool-surface-missing-refresh":
        height["heightRefresh"]["returnValue"] = None
    elif fault == "pool-surface-missing-terrain":
        height["loadedTerrain"] = {"status": "unknown", "cell": None}
    elif fault == "pool-surface-missing-height":
        height["positionAfter"].pop("pos_y", None)
    else:
        raise ValidationFailure("unknown surface meaning control")
    count = 0
    for event in events:
        data = event.get("data", {})
        if event.get("kind") != "native-observation":
            continue
        if data.get("observation") == "spawn-landing-height" and data.get("sequence") == sequence:
            event["data"] = deepcopy(height)
            count += 1
        if data.get("observation") == "spawn-motion" \
                and data.get("landingHeight", {}).get("sequence") == sequence:
            data["landingHeight"] = deepcopy(height)
    if count != 1:
        raise ValidationFailure("surface control has no unique native height receipt")


def _shared_pool_measurements(replay: dict[str, Any], kind: str = "pool-spawn-v1") -> list[dict[str, Any]]:
    if kind not in _POOL_KINDS:
        raise ValidationFailure("unknown POOL measurement kind")
    meter = replay.get("measurements", {}).get(kind, {})
    placement = meter.get("placement", {})
    if meter.get("passed") is not True or meter.get("ready") is not True \
            or meter.get("failures") != [] or meter.get("measurementErrors") != [] \
            or not isinstance(placement, dict) or placement.get("passed") is not True \
            or any(placement.get("subject", {}).get(key) != (meter.get("subject") or {}).get(key)
                   for key in ("handle", "species", "role", "subjectIdentity")) \
            or meter.get("stopBoundary") is None:
        raise ValidationFailure("shared POOL replay lacks its own complete native spawn landing")
    values = (meter.get("identitySamples"), meter.get("selectedProfileObservationCount"),
              int(type(placement.get("finalizationId")) is int and placement["finalizationId"] > 0),
              int(placement.get("sourcePosition") == placement.get("destination") == placement.get("landingTarget")
                  == meter.get("spawnGeometry", {}).get("spawnPosition")), int(meter.get("spawnPassed") is True))
    measured = []
    for (claim, suffix, operator, threshold), value in zip(_POOL_MEASUREMENT_RULES, values):
        if type(value) is not int or (value < threshold if operator == "gte" else value != threshold):
            raise ValidationFailure("shared POOL measurement failed: " + suffix)
        measured.append({"claim": claim, "name": "pool-spawn-" + suffix, "value": value,
                         "operator": operator, "threshold": threshold, "passed": True})
    if kind == "pool-spawn-surface-v1":
        from tools.overworld.devtools_spawn_surface_measurement import SCOPE
        surface = meter.get("surface")
        if (meter.get("surfaceErrors") != [] or not isinstance(surface, dict)
                or surface.get("passed") is not True or surface.get("scope") != SCOPE
                or surface.get("target") != placement.get("landingTarget")
                or any(surface.get("subject", {}).get(key) != (meter.get("subject") or {}).get(key)
                       for key in ("handle", "species", "role", "subjectIdentity"))
                or type(surface.get("nativeLandingY")) is not int
                or type(surface.get("terminalFrame")) is not int
                or surface["terminalFrame"] < 0
                or any(surface.get(key) is not True for key in
                       ("loadedTerrainVerified", "authoredSurfaceExcluded", "terminalHeightVerified"))):
            raise ValidationFailure("shared POOL replay lacks its native loaded surface and terminal height")
        measured.extend({"claim": "terrain-selection", "name": "pool-spawn-" + suffix,
                         "value": 1, "operator": "eq", "threshold": 1, "passed": True}
                        for suffix in ("loaded-surface-permitted", "native-terminal-height"))
    return measured


def _shared_live_control_measurements(replay: dict[str, Any], record: dict[str, Any]) -> list[dict[str, Any]]:
    meter = replay.get("measurements", {}).get("live-observer-control-v1", {})
    if meter.get("passed") is not True or meter.get("ready") is not True or meter.get("failures") != [] \
            or meter.get("measurementErrors") != [] or record.get("recorderControlArtifact") is not None:
        raise ValidationFailure("live recorder replay is incomplete or has a nested dependency")
    baseline = meter.get("baseline")
    if not isinstance(baseline, dict): raise ValidationFailure("live recorder normal baseline is missing")
    _shared_ledyba_measurements({"measurements": {"ledyba-chain-v1": baseline}})
    detections = meter.get("detections", {})
    if set(detections) != {"render-stall", "inactive-object"}:
        raise ValidationFailure("live recorder needs both exact native fault detections")
    render, inactive = detections["render-stall"], detections["inactive-object"]
    writes = [item for item in render.get("receipts", []) if item.get("action") == "render-restored"]
    pinned = [item for item in render.get("receipts", []) if item.get("action") == "render-pinned"]
    cleared = [item for item in inactive.get("receipts", []) if item.get("action") == "active-bit-cleared"]
    cleanup = meter.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup != record.get("observerControlCleanup") \
            or cleanup.get("closed") is not True or cleanup.get("frame") != replay["lastFrame"]:
        raise ValidationFailure("live recorder cleanup manifest differs from the exact replayed restore receipt")
    if type(render.get("faultFrames")) is not int or render["faultFrames"] < 2 \
            or len(writes) != 2 or len(pinned) != 1 \
            or [item.get("frame") for item in writes] != [pinned[0]["frame"] + 1, pinned[0]["frame"] + 2] \
            or not any(item.get("reason") == "render-stall" for item in render.get("failures", [])) \
            or not isinstance(inactive.get("failure"), str) or not inactive["failure"] \
            or len(cleared) != 1 or cleared[0].get("frame") != inactive.get("frame") \
            or type(render.get("frame")) is not int or type(inactive.get("frame")) is not int \
            or render["frame"] >= inactive["frame"]:
        raise ValidationFailure("live recorder faults lack actual ordered render/identity rejection receipts")
    subject = meter.get("subject")
    if not isinstance(subject, dict) or not isinstance(baseline.get("subject"), dict) \
            or any(subject.get(key) != baseline["subject"].get(key) for key in ("handle", "species", "role", "subjectIdentity")):
        raise ValidationFailure("live recorder faults differ from the measured baseline subject")
    return [
        {"claim": "live-actor-identity", "name": "live-recorder-baseline-identity", "value": 1,
         "operator": "eq", "threshold": 1, "passed": True},
        {"claim": "controlled-action", "name": "live-recorder-baseline-and-faults", "value": [1, 1, 1],
         "operator": "eq", "threshold": [1, 1, 1], "passed": True},
        {"claim": "controlled-action", "name": "live-recorder-render-fault-frames", "value": render["faultFrames"],
         "operator": "gte", "threshold": 2, "passed": True},
    ]


def _shared_height_control_measurements(replay: dict[str, Any]) -> list[dict[str, Any]]:
    meter = replay.get("measurements", {}).get(_HEIGHT_CONTROL_KIND, {})
    if (meter.get("passed") is not True or meter.get("ready") is not True
            or meter.get("failures") != [] or meter.get("measurementErrors") != []):
        raise ValidationFailure("height recorder lacks complete native calibration")
    _shared_pool_measurements({"measurements": {"pool-spawn-surface-v1": meter.get("baseline", {})}},
                              "pool-spawn-surface-v1")
    detection = meter.get("detections", {}).get("spawn-height-read", {})
    cleanup = meter.get("cleanup", {})
    if (detection.get("reason") != "terminal Y differs from native landing height"
            or cleanup.get("restored") is not True or cleanup.get("cleanupPending") is not False):
        raise ValidationFailure("height recorder lacks exact rejection and restoration")
    return [{"claim": claim, "name": name, "value": 1, "operator": "eq", "threshold": 1, "passed": True}
            for claim, name in (("live-actor-identity", "spawn-height-native-subject"),
                                ("controlled-action", "spawn-height-read-rejected-and-restored"))]


def _shared_surface_recorder_control(record: dict[str, Any], repo: Path) -> dict[str, Any]:
    fixture = record.get("fixtureProof", {})
    artifact = fixture.get("surfaceRecorderControlArtifact")
    if not isinstance(artifact, dict):
        raise ValidationFailure("required separate height recorder calibration is missing")
    return _shared_recorder_control({**record,
        "fixtureProof": {**fixture, "recorderControlArtifact": artifact},
        "recorderControlArtifact": artifact}, {"recorderControlRequirement": _HEIGHT_CONTROL_REQUIREMENT}, repo)


def _shared_recorder_kind(requirement: str) -> str:
    """Resolve dependencies before scanning evidence or starting a fixture."""
    kinds = {_LEDYBA_RECORDER_REQUIREMENT: "live-observer-control-v1",
             _WALK_POLICY_CONTROL_REQUIREMENT: _WALK_POLICY_CONTROL_KIND,
             _MOUNT_POSE_CONTROL_REQUIREMENT: _MOUNT_POSE_CONTROL_KIND,
             _WILD_CLEAR_CONTROL_REQUIREMENT: _WILD_CLEAR_CONTROL_KIND,
             _CORNER_CONTROL_REQUIREMENT: _CORNER_CONTROL_KIND,
             _MATRIX_CONTROL_REQUIREMENT: _MATRIX_CONTROL_KIND,
             _STOMP_CONTROL_REQUIREMENT: _STOMP_CONTROL_KIND,
             "shared.crash-recorder-control-v1": "live-crash-control-v1",
             _ROLE_CONTROL_REQUIREMENT: _ROLE_CONTROL_KIND,
             _HEIGHT_CONTROL_REQUIREMENT: _HEIGHT_CONTROL_KIND,
             _ROUTE_CONTROL_REQUIREMENT: _ROUTE_CONTROL_KIND}
    if requirement not in kinds:
        raise ValidationFailure("unknown live recorder requirement: " + str(requirement))
    return kinds[requirement]


def _shared_recorder_control(record: dict[str, Any], registration: dict[str, Any], repo: Path) -> dict[str, Any]:
    """Require a separate, independently rechecked current live control run.

    No evaluator-only pass supplies calibration. Recheck the separate current
    control adapter and its retained native fault/restore receipts.
    """
    requirement = registration["recorderControlRequirement"]
    kind = _shared_recorder_kind(requirement)
    preflight_artifact = record.get("fixtureProof", {}).get("recorderControlArtifact")
    artifact = record.get("recorderControlArtifact", preflight_artifact)
    if preflight_artifact is not None and artifact != preflight_artifact:
        raise ValidationFailure("live recorder control changed after normal preflight")
    if not isinstance(artifact, dict):
        raise ValidationFailure("required live recorder control artifact is missing")
    path = _shared_artifact(artifact, repo / "build/overworld-devtools")
    if path.name != "manifest.json" or not path.parent.name.startswith("test-") \
            or path.parent.name == record.get("runId") or path.stat().st_size > MANIFEST_MAX_BYTES:
        raise ValidationFailure("live recorder control is not a separate bounded test manifest")
    control = json.loads(path.read_text())
    if not isinstance(control, dict) or control.get("passed") is not True or control.get("acceptedProof") is not True:
        raise ValidationFailure("live recorder control manifest was not independently accepted")
    name = control.get("test")
    if not isinstance(name, str) or not name or Path(name).name != name \
            or control.get("runId") != path.parent.name or control.get("sessionId") == record.get("sessionId") \
            or path.parent.resolve() != (repo / "build/overworld-devtools" / path.parent.name).resolve():
        raise ValidationFailure("live recorder control has invalid run/session identity")
    test = json.loads((repo / "tests/overworld/test-recipes" / (name + ".json")).read_text())
    # Check scope before recursion. A linked control cannot have a dependency
    # of its own, including a self-link back to this normal-play manifest.
    registry = json.loads((repo / "tools/overworld/runtime_proof_registry.json").read_text())
    linked = registry.get("sharedTests", {}).get(name, {})
    if not isinstance(test, dict) or not isinstance(linked, dict) \
            or test.get("mode") != "observer-control" or linked.get("mode") != "observer-control" \
            or linked.get("evaluator") != kind \
            or linked.get("requirements") != [requirement] \
            or linked.get("recorderControlRequirement") is not None or control.get("recorderControlArtifact") is not None \
            or isinstance(control.get("fixtureProof"), dict) and control["fixtureProof"].get("recorderControlArtifact") is not None:
        raise ValidationFailure("live recorder control has wrong scope or a nested dependency")
    if not isinstance(control.get("fixtureProof"), dict) or not isinstance(control.get("identity"), dict) \
            or ("proofInputs" not in control["fixtureProof"]
                and control["fixtureProof"].get("source") != record["fixtureProof"]["source"]) \
            or any(not isinstance(control["identity"].get(key), dict)
                   or control["identity"][key].get("sha256") != record["identity"][key]["sha256"]
                   for key in ("rom", "save", "debugDescriptor")):
        raise ValidationFailure("live recorder control product/proof inputs are stale")
    checked = finalize_shared_test(test, control, repo)
    acceptance = checked.get("proofAcceptance", {})
    if checked.get("passed") is not True or checked.get("acceptedProof") is not True \
            or acceptance.get("mode") != "observer-control" \
            or acceptance.get("claims") != ["live-actor-identity", "controlled-action"] \
            or acceptance.get("requirements") != [registration["recorderControlRequirement"]]:
        raise ValidationFailure("live recorder control did not pass independent current acceptance")
    return {"requirement": requirement, "runId": control["runId"],
            "artifact": artifact, "revalidated": True}


def _find_shared_recorder_control(test: dict[str, Any], registration: dict[str, Any], source: dict[str, Any],
                                  repo: Path, *, deadline=None, cancel_event=None) -> dict[str, Any]:
    """Bounded current-control lookup; no launch, repair or historical credit."""
    import time
    def check_budget():
        if cancel_event is not None and cancel_event.is_set():
            raise ValidationFailure("recorder-control lookup canceled")
        if deadline is not None and time.monotonic() >= deadline:
            raise ValidationFailure("recorder-control lookup exceeded the preflight wall budget")
    check_budget()
    requirement = registration.get("recorderControlRequirement")
    _shared_recorder_kind(requirement)
    directory = repo / "build/overworld-devtools"
    if not directory.is_dir(): raise ValidationFailure("no shared control runs are recorded")
    from tools.overworld.proof_reuse import RECORDER_INDEX
    candidates = RECORDER_INDEX.candidates(directory, requirement, check_budget)
    current = {"runId": "test-preflight", "sessionId": "session-preflight", "fixtureProof": {"source": source},
        "identity": {key: file_record(repo / path, repo) for key, path in (
            ("rom", test["fixture"]["rom"]), ("save", test["fixture"]["save"]),
            ("debugDescriptor", "build/overworld-system.debug.json"))}}
    rejected = []
    for path in candidates:
        check_budget()
        if path.stat().st_size > MANIFEST_MAX_BYTES: continue
        try:
            candidate = json.loads(path.read_text())
            if not isinstance(candidate, dict) or candidate.get("acceptedProof") is not True \
                    or candidate.get("passed") is not True \
                    or not isinstance(candidate.get("proofAcceptance"), dict) \
                    or candidate["proofAcceptance"].get("requirements") != [registration["recorderControlRequirement"]]:
                continue
            artifact = file_record(path, repo)
            artifact = {"path": str(path), **{key: artifact[key] for key in ("sha256", "size")}}
            _shared_recorder_control({**current, "recorderControlArtifact": artifact}, registration, repo)
            check_budget()
            return artifact
        except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
            if len(rejected) < 3:
                rejected.append(path.parent.name + ": " + str(error))
            continue  # Historical/failed candidates stay recorded, never repaired.
    check_budget()
    raise ValidationFailure("no independently accepted current live recorder control for " + requirement
                            + ("; " + "; ".join(rejected) if rejected else "; no matching recorded control"))


def _resolver_probe_oracle(repo):
    """Fresh Workshop results and packaged identities, never a cached game verdict."""
    from tools.overworld.devtools_runtime import _elf_code, STOCK_CALLS
    from tools.overworld.devtools_engine import linked_symbols, linked_symbol
    from tools.overworld.devtools_resolver_parity import CASE_NAMES
    blob_path = repo / "build/OverworldWildBehaviorData.bin"
    blob = blob_path.read_bytes()
    corpus = json.loads((repo / "tools/overworld/native/behavior_resolver_golden.json").read_text())
    by_name = {vector.get("name"): vector for vector in corpus["vectors"]}
    vectors = [by_name.get(name) for name in CASE_NAMES]
    if corpus["blobVersion"] != 77 \
            or not all(isinstance(vector, dict) for vector in vectors):
        raise ValidationFailure("resolver golden cases changed")
    path = repo / "tools/overworld-viewer-v2/native_resolver.py"
    spec = importlib.util.spec_from_file_location("shared_resolver_oracle", path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    results = adapter.resolve_many(blob_path, [v["request"] for v in vectors], root=repo)
    descriptor = load_debug_descriptor(repo / "build/overworld-system.debug.json")
    service = next(s for s in descriptor["privateServices"] if s["name"] == "resolver")
    elf = repo / "build/overworld_actor_system_overlay_linked.o"
    address = linked_symbol(linked_symbols(elf), "BehaviorResolver_Resolve") & ~1
    if service["status"] != "available" or service["version"] != 1 or service["size"] != 16 \
            or service["callbacks"]["resolve"] != address | 1:
        raise ValidationFailure("resolver service differs from packaged linked function")
    return {"vectors": vectors, "hostResults": results,
        "blobIdentity": {"size": len(blob), "sha256": hashlib.sha256(blob).hexdigest()},
        "serviceIdentity": {"magic": 0x5250574F, "version": 1, "size": 16,
            "resolveAddress": address | 1, "entrySha256": hashlib.sha256(_elf_code(elf,address,32)).hexdigest()},
        "callAddresses": {"allocate_work_memory": STOCK_CALLS["allocate_work_memory"][0],
                          "free": STOCK_CALLS["free"][0], "resolve_behavior": address}}


def _actor_inspect_probe_oracle(repo):
    """Bind the public facade and Inspect entry to this exact packaged ELF."""
    import struct
    from scripts.verify_overworld_runtime_fixture import packaged_overlay
    from tools.overworld.devtools_runtime import _elf_code, STOCK_CALLS
    from tools.overworld.devtools_engine import linked_symbols, linked_symbol
    descriptor = load_debug_descriptor(repo / "build/overworld-system.debug.json")
    facade, overlay = descriptor["facade"], descriptor["overlay"]
    image = packaged_overlay((repo / "test.nds").read_bytes(), 158)
    if overlay["id"] != 158 or len(image) != overlay["fileSize"] \
            or hashlib.sha256(image).hexdigest() != overlay["sha256"] \
            or facade["version"] != 1 or facade["size"] != 24:
        raise ValidationFailure("actor Inspect package/descriptor differs")
    elf = repo / "build/overworld_actor_system_overlay_linked.o"
    symbols = linked_symbols(elf)
    callbacks = {name: linked_symbol(symbols, "OverworldActorSystem_" + name.title() + "Impl") | 1
                 for name in ("validate", "apply", "tick", "inspect")}
    if facade["callbacks"] != callbacks:
        raise ValidationFailure("actor Inspect facade callbacks differ from linked symbols")
    entry = struct.pack("<IHH4I", 0x5341574F, 1, 24,
                        *(callbacks[name] for name in ("validate", "apply", "tick", "inspect")))
    address = callbacks["inspect"] & ~1
    code = _elf_code(elf, address, 32)
    for start, expected in ((facade["address"], entry), (address, code)):
        offset = start - overlay["base"]
        if len(expected) not in (24, 32) or offset < 0 or offset + len(expected) > len(image) \
                or image[offset:offset + len(expected)] != expected \
                or _elf_code(elf, start, len(expected)) != expected:
            raise ValidationFailure("actor Inspect bytes differ between package and ELF")
    return {"serviceIdentity": {"address": facade["address"], "version": 1, "size": 24,
                "facadeHex": entry.hex(), "inspectAddress": address | 1,
                "entrySha256": hashlib.sha256(code).hexdigest()},
            "callAddresses": {"allocate_work_memory": STOCK_CALLS["allocate_work_memory"][0],
                              "inspect_actor": address, "free": STOCK_CALLS["free"][0]}}


def _walk_reset_oracle(repo):
    """Bind RESET to the current packaged public Walk service, not reader claims."""
    import struct
    from scripts.verify_overworld_runtime_fixture import packaged_overlay
    from tools.overworld.devtools_runtime import _elf_code
    from tools.overworld.devtools_engine import linked_symbols, linked_symbol
    descriptor = load_debug_descriptor(repo / "build/overworld-system.debug.json")
    services = [s for s in descriptor["privateServices"] if s["name"] == "movementPolicy"]
    if len(services) != 1:
        raise ValidationFailure("Walk RESET requires one public movement policy service")
    service, overlay = services[0], descriptor["overlay"]
    image = packaged_overlay((repo / "test.nds").read_bytes(), 158)
    if overlay["id"] != 158 or len(image) != overlay["fileSize"] \
            or hashlib.sha256(image).hexdigest() != overlay["sha256"] \
            or service["status"] != "available" or service["version"] != 4 \
            or service["size"] != 16 or service["reserved"] != 0:
        raise ValidationFailure("Walk RESET package/descriptor differs")
    elf = repo / "build/overworld_actor_system_overlay_linked.o"
    address = linked_symbol(linked_symbols(elf), "ActorSystem_ReduceWalk") & ~1
    entry = struct.pack("<IHHII", 0x504D574F, 4, 16, service["policy"], 0)
    table = _elf_code(elf, service["policy"], 24)
    code = _elf_code(elf, address, 32)
    if len(table) != 24 or struct.unpack_from("<I", table, 12)[0] != address | 1:
        raise ValidationFailure("Walk RESET callback differs from linked reducer")
    for start, expected in ((service["address"], entry), (service["policy"], table), (address, code)):
        offset = start - overlay["base"]
        if offset < 0 or offset + len(expected) > len(image) \
                or image[offset:offset + len(expected)] != expected \
                or _elf_code(elf, start, len(expected)) != expected:
            raise ValidationFailure("Walk RESET bytes differ between package and ELF")
    return dict(serviceIdentity=dict(address=service["address"], entryHex=entry.hex(),
                tableHex=table.hex(), reduceWalkAddress=address | 1,
                entrySha256=hashlib.sha256(code).hexdigest()),
                callAddresses=dict(reduce_walk=address))


def _shared_acceleration_resets(test, rows, *, oracle):
    """Authenticate both prepared RESETs independently of the movement meter."""
    from tools.overworld.devtools_acceleration_proof import checked_reset_receipt
    declared = [m for m in test.get("measurements", []) if m.get("kind") == "acceleration-parity-v1"]
    if len(declared) != 1 or set(declared[0].get("subjects", {})) != {"WILD", "MOUNTED"}:
        raise ValidationFailure("acceleration needs exact Wild and Mounted subjects")
    roles = declared[0]["subjects"]
    specs = {s["id"]: s for s in test["subjects"]}
    actions = {a["id"]: a for a in test["setup"]}
    bound, checked = {}, {}
    for row in rows:
        if row.get("command") not in ("bind", "acceleration.begin"):
            continue
        action = actions.get(row.get("action"), {})
        name = action.get("args", {}).get("subject")
        if row.get("phase") != "setup" or action.get("op") != row["command"] or name not in roles.values():
            raise ValidationFailure("acceleration setup row differs from declared action")
        if row["command"] == "bind":
            if name in bound:
                raise ValidationFailure("acceleration subject rebound")
            subject = row["receipt"]
            spec = specs[name]
            if subject.get("species") != spec["species"] or subject.get("role") != spec["role"]:
                raise ValidationFailure("acceleration bound species/role differs")
            bound[name] = subject
        else:
            if name not in bound or name in checked:
                raise ValidationFailure("acceleration RESET lacks unique prior binding")
            checked[name] = checked_reset_receipt(row, bound[name], oracle=oracle)
    if set(checked) != set(roles.values()):
        raise ValidationFailure("acceleration requires both authenticated RESETs")
    return checked


def _shared_role_transfer(rows, record, *, reader_control=False):
    """Exact short native transfer route; no input or movement credit."""
    from copy import deepcopy
    from tools.overworld.devtools_role_profile_proof import inspect_transfer, negative_controls
    from tools.overworld.devtools_raw_chunk import validate_raw_chunk
    from tools.overworld.devtools_records import select_current_actor
    if len(rows) != (4 if reader_control else 5) or set(rows[0]) != {"initialSnapshot", "phase"} \
            or rows[0]["phase"] != "setup":
        raise ValidationFailure("role transfer needs its exact recording route")
    initial, spawn, bound = rows[0]["initialSnapshot"], rows[1], rows[2]
    start = {"phase": "observe", "boundarySnapshot": bound["snapshot"]} if reader_control else rows[3]
    step = rows[-1]
    if (spawn.get("command"), spawn.get("phase"), spawn.get("action")) != \
            ("spawn", "setup", "mount-current-follower") \
            or (bound.get("command"), bound.get("phase"), bound.get("action")) != \
            ("bind", "setup", "bind-mount") \
            or (step.get("phase"), step.get("action")) != ("observe", "observe-owner") \
            or "command" in step:
        raise ValidationFailure("role transfer has an unexpected action")
    receipt = spawn["receipt"]
    if receipt.get("snapshot") != spawn.get("snapshot") \
            or receipt.get("preparedOnly") is not True \
            or receipt.get("profileDiagnostics") != ("owner-transfer-control" if reader_control else "owner-transfer") \
            or receipt.get("lifecycle") != "prepared-native-follower-lifecycle":
        raise ValidationFailure("role transfer lacks its owned prepared receipt")
    boundary = receipt.get("setupBoundary", {})
    snapshot = spawn["snapshot"]
    if boundary.get("eventsDrained") is not True \
            or (boundary.get("frame"), boundary.get("nativeCycle")) != (snapshot["frame"], snapshot["nativeCycle"]) \
            or bound["snapshot"]["frame"] != snapshot["frame"] \
            or bound["snapshot"]["nativeCycle"] != snapshot["nativeCycle"]:
        raise ValidationFailure("role transfer setup boundary differs")
    retained = receipt.get("profileObservation", {})
    events = retained.get("events")
    selected = [event for event in receipt["events"]
               if event.get("kind") == "native-observation"
               and event.get("data", {}).get("observation") in ("role-profile-getter", "role-profile-mount")]
    if retained.get("acceptedProof") is not False or events != selected:
        raise ValidationFailure("role transfer retained events differ from the native stream")
    if step.get("requestedGameFrames") != 1 or step.get("completedGameFrames") != 1:
        raise ValidationFailure("role transfer needs one complete endpoint frame")
    if set(start) != {"phase", "boundarySnapshot"} or start["phase"] != "observe":
        raise ValidationFailure("role transfer lacks its recording boundary")
    previous = start["boundarySnapshot"]
    for clock in ("frame", "nativeCycle"):
        if type(previous.get(clock)) is not int or previous[clock] < bound["snapshot"][clock]:
            raise ValidationFailure("role transfer recording clock moved backwards")
    selected = select_current_actor(previous, bound["receipt"])
    expected = dict(bound["receipt"], observedFrame=previous["frame"])
    if selected != expected or previous.get("context") != bound["snapshot"].get("context") \
            or previous.get("observationBoundary") != "main-task-queue-completion" \
            or previous.get("fieldAvailable") is not True:
        raise ValidationFailure("role transfer recording boundary changed identity or context")
    samples = validate_raw_chunk(step, previous)
    if len(samples) != 1:
        raise ValidationFailure("role transfer endpoint count differs")
    final = samples[0][0]
    evidence = inspect_transfer(events, initial, final, allow_reader_control=reader_control)
    # Copied-data transfer controls remain separate from live reader controls.
    clean_events = deepcopy(events)
    if reader_control:
        for event in clean_events:
            event.get("data", {}).pop("readerControl", None)
    negatives = negative_controls(clean_events, initial, final)
    if record.get("sessionCleanup") != {"sessionId": record["sessionId"], "closed": True, "errors": []}:
        raise ValidationFailure("role transfer private session cleanup is missing or failed")
    if reader_control:
        from tools.overworld.devtools_role_profile_proof import inspect_reader_control
        return {"readerControl": inspect_reader_control(events), "transferControls": negatives,
                "measurements": [{"claim": "controlled-action", "name": "native-owner-rejection-and-restore",
                    "value": 1, "operator": "eq", "threshold": 1, "passed": True}]}
    return {"transfer": evidence, "transferControls": negatives,
            "measurements": [{"claim": claim, "name": name, "value": 1,
                              "operator": "eq", "threshold": 1, "passed": True}
                for claim, name in (("live-actor-identity", "same-current-follower"),
                    ("profile-resolution", "getter-to-begin-byte-transfer"),
                    ("profile-resolution", "mounted-owner-byte-transfer"))]}


def _shared_mount_begin(test, rows, record, repo):
    """Seven original measurements plus complete normal-input Hop witness."""
    from tools.overworld.devtools_mount_begin_measurement import run, negative_controls
    evidence = run(rows, test)
    if evidence.get("passed") is not True:
        raise ValidationFailure("mount begin native replay failed: " + str(evidence.get("failures")))
    controls = negative_controls(rows, test)
    if controls.get("passed") is not True:
        raise ValidationFailure("mount begin required copied-meaning control did not reject")
    if record.get("sessionCleanup") != {"sessionId":record["sessionId"], "closed":True, "errors":[]}:
        raise ValidationFailure("mount begin private session cleanup is missing or failed")
    registry = json.loads((repo / "tools/overworld/runtime_proof_registry.json").read_text())
    contract = registry["measurementContracts"][_MOUNT_BEGIN_REQUIREMENT]
    values = evidence["measurements"]
    if set(values) != {rule["name"] for rules in contract.values() for rule in rules}:
        raise ValidationFailure("mount begin changed the original seven measurements")
    measurements = []
    for claim, rules in contract.items():
        for rule in rules:
            value = values[rule["name"]]
            expected = rule.get("expected", value)
            shape = {"integer":type(value) is int, "array":isinstance(value,list), "object":isinstance(value,dict)}
            if not shape.get(rule["type"], False) or ("expected" in rule and value != expected) \
                    or ("minimum" in rule and value < rule["minimum"]) \
                    or not _registry_validator_passes(rule, value, expected):
                raise ValidationFailure("mount begin original validator rejected " + rule["name"])
            measurements.append(dict(claim=claim, name=rule["name"], value=value,
                                     operator=rule["operator"], expected=expected, passed=True))
    return dict(measurements=measurements, mountBegin=evidence,
                mountBeginControls={name:dict(rejected=True, faultApplied=r["faultApplied"], failures=r["failures"])
                                    for name,r in controls["controls"].items()})


def _current_proof_inputs(repo, test):
    from tools.overworld.proof_inputs import proof_inputs
    context = _PROOF_INPUT_CONTEXT.get()
    key = (str(Path(repo).resolve()), digest_value(test))
    if context is None:
        return proof_inputs(repo, test)
    if key not in context:
        context[key] = (repo, test, proof_inputs(repo, test))
    return context[key][2]


_ISOLATED_CAPTURE_DEPENDENCIES = {
    "tools/overworld/devtools_crash_measurement.py": {
        "unmounted-cadence-v1", "unmounted-game-cadence-v1",
    },
    "tools/overworld/devtools_mounted_cardinal_streaming_measurement.py": {
        "mounted-cardinal-streaming-v1",
    },
    "tools/overworld/devtools_wild_transition_measurement.py": {
        "wild-transition-invalidation-v1", "follower-transition-rebind-v1",
    },
}


def _capture_update_is_unselected(test, record, recorded, current, repo):
    """Reuse raw data when only another evaluator's source changed.

    The service identity records every loadable tool file because one process
    hosts every evaluator.  The scoped proof hash therefore sees evaluator
    files that a given recipe never executes.  Keep selected evaluators strict,
    while allowing saved raw data to replay after an unrelated evaluator fix.
    """
    before_roots = recorded.get("capture", {}).get("roots", {})
    after_roots = current.get("capture", {}).get("roots", {})
    if not isinstance(before_roots, dict) or not isinstance(after_roots, dict) \
            or set(before_roots) != set(after_roots) \
            or any(before_roots[name] != after_roots[name]
                   for name in before_roots if name not in {"tools", "tests"}):
        return False
    retained = record.get("identity", {}).get("toolInputs")
    if not isinstance(retained, list) or any(not isinstance(item, dict)
            or set(item) != {"path", "sha256"} for item in retained):
        return False
    retained = {item["path"]: item["sha256"] for item in retained}
    from tools.overworld.devtools_contract import source_paths
    paths = set(source_paths(repo))
    if set(retained) != paths:
        return False
    selected = {item.get("kind") for item in test.get("measurements", [])}
    for path in paths:
        digest = file_record(repo / path, repo)["sha256"]
        if digest == retained[path]:
            continue
        name = Path(path).name
        if path == "tools/overworld/runtime_proof_registry.json" \
                or path in {"tools/overworld/control.py", "tools/overworld/proof_inputs.py",
                            "tools/overworld/proof_reuse.py", "tools/overworld/proof_adapters.py",
                            "tools/overworld/cadence_diagnostics.py"} \
                or name.startswith("devtools_") and name.endswith("_proof.py"):
            continue
        affected = _ISOLATED_CAPTURE_DEPENDENCIES.get(path)
        if affected is None or selected & affected:
            return False
    return True


def finalize_shared_test(test: dict[str, Any], record: dict[str, Any], repo: Path = REPO) -> dict[str, Any]:
    """One input snapshot per acceptance tree, including its reader dependency."""
    if _PROOF_INPUT_CONTEXT.get() is not None:
        return _finalize_shared_test_scoped(test, record, repo)
    token = _PROOF_INPUT_CONTEXT.set({})
    cache_token = _PENDING_PROOF_CACHE.set([])
    try:
        _require_current_controller()
        result = _finalize_shared_test_scoped(test, record, repo)
        if result.get("acceptedProof") is True:
            from tools.overworld.proof_inputs import proof_inputs
            for root, recipe, before in _PROOF_INPUT_CONTEXT.get().values():
                if before != proof_inputs(root, recipe):
                    return {"passed": False, "acceptedProof": False,
                            "proofAcceptance": {"eligible": True, "reason": "proof inputs changed during acceptance"}}
            _require_current_controller()
            from tools.overworld.proof_reuse import ACCEPTANCE_CACHE
            for key, value in _PENDING_PROOF_CACHE.get():
                ACCEPTANCE_CACHE.put(key, value)
        return result
    except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
        return {"passed": False, "acceptedProof": False,
                "proofAcceptance": {"eligible": True, "reason": str(error)}}
    finally:
        _PENDING_PROOF_CACHE.reset(cache_token)
        _PROOF_INPUT_CONTEXT.reset(token)


def _finalize_shared_test_scoped(test: dict[str, Any], record: dict[str, Any], repo: Path = REPO) -> dict[str, Any]:
    """Reuse exact checked results; replay checker-only changes without a boot.

    Legacy manifests lack dependency detail and keep strict full-source checks.
    Scoped inputs are captured before the run, never invented for old evidence.
    """
    if "diagnosticContinueHostHitches" in test:
        return {"passed": False, "acceptedProof": False,
                "proofAcceptance": {"eligible": False, "reason": "host-hitch continuation; diagnostic only"}}
    recorded = (record.get("fixtureProof") or {}).get("proofInputs")
    if recorded is None:
        return _finalize_shared_test_uncached(test, record, repo)
    from tools.overworld.proof_reuse import ACCEPTANCE_CACHE, acceptance_key
    try:
        current = _current_proof_inputs(repo, test)
        if not isinstance(recorded, dict) or recorded.get("schema") != current["schema"] \
                or recorded.get("capture") != current["capture"] \
                and not _capture_update_is_unselected(test, record, recorded, current, repo):
            raise ValidationFailure("game, reader or action inputs changed; fresh memory data required")
        key = acceptance_key(repo, test, record, current, inputs_for=_current_proof_inputs)
        cached = ACCEPTANCE_CACHE.get(key)
        if cached is not None:
            return cached
        result = _finalize_shared_test_uncached(test, record, repo, current_inputs=current)
        if result.get("acceptedProof") is True:
            if key != acceptance_key(repo, test, record, current, inputs_for=_current_proof_inputs):
                raise ValidationFailure("proof inputs changed during acceptance")
            result["proofAcceptance"]["proofInputs"] = current
            result["proofAcceptance"]["replayMode"] = (
                "checker-update" if recorded["checker"] != current["checker"] else "same-inputs")
            _PENDING_PROOF_CACHE.get().append((key, result))
        return result
    except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
        return {"passed": False, "acceptedProof": False,
                "proofAcceptance": {"eligible": True, "reason": str(error)}}


def _finalize_shared_test_uncached(test: dict[str, Any], record: dict[str, Any], repo: Path = REPO,
                                  *, current_inputs=None) -> dict[str, Any]:
    """Grant only exact registered claims after current retained replay.

    The service calls this before its exclusive final-manifest write. No legacy
    runtime command, arbitrary evaluator, or unported requirement is accepted.
    """
    if "diagnosticContinueHostHitches" in test:
        return {"passed": False, "acceptedProof": False,
                "proofAcceptance": {"eligible": False, "reason": "host-hitch continuation; diagnostic only"}}
    if "spawnObserverCost" in test or "spawnObserverCost" in (record.get("observationSetup") or {}):
        return {"passed": record.get("passed") is True, "acceptedProof": False,
                "proofAcceptance": {"eligible": False, "reason": "spawn observer cost experiment; diagnostic only"}}
    try:
        registration, recipe_hash = _shared_test_registration(test, repo)
        if registration is None:
            return {"passed": record.get("passed") is True, "acceptedProof": False,
                    "proofAcceptance": {"eligible": False, "reason": "unregistered tool test; diagnostic only"}}
        preflight_inputs = (record.get("fixtureProof") or {}).get("proofInputs")
        checker_changed = bool(
            current_inputs is not None
            and isinstance(preflight_inputs, dict)
            and preflight_inputs.get("checker") != current_inputs.get("checker")
        )
        completed_run = record.get("state") == "completed" and record.get("passed") is True
        replay_only_failure = (
            checker_changed
            and record.get("state") == "failed"
            and record.get("passed") is False
            and record.get("acceptedProof") is False
            and record.get("evaluation", {}).get("state") == "passed"
            and record.get("evaluation", {}).get("passed") is True
            and isinstance(record.get("proofAcceptance", {}).get("reason"), str)
            and bool(record["proofAcceptance"]["reason"])
        )
        if (not completed_run and not replay_only_failure) \
                or record.get("execution") != "shared-devtools":
            raise ValidationFailure("shared test did not complete successfully")
        preflight = record.get("fixtureProof")
        if not isinstance(preflight, dict) or preflight.get("passed") is not True or preflight.get("eligible") is not True \
                or preflight.get("registration") != registration or preflight.get("fixture", {}).get("passed") is not True:
            raise ValidationFailure("current registered fixture preflight is missing or failed")
        if current_inputs is None and preflight.get("source") != source_record(repo):
            raise ValidationFailure("product/proof source changed after shared test preflight")
        if record.get("testSourceSha256") != recipe_hash or preflight.get("testSourceSha256") != recipe_hash:
            raise ValidationFailure("shared recipe identity changed during the run")
        identity = record.get("identity")
        session_id = record.get("sessionId")
        if not isinstance(session_id, str) or not session_id.startswith("session-") \
                or Path(session_id).name != session_id \
                or not isinstance(identity, dict) or identity.get("sessionId") != session_id:
            raise ValidationFailure("shared proof session identity is missing or differs")
        for key in ("rom", "save", "debugDescriptor"):
            item = identity.get(key)
            if not isinstance(item, dict): raise ValidationFailure("shared proof input identity is missing: " + key)
            path = repo / test["fixture"][key] if key in ("rom", "save") else repo / "build/overworld-system.debug.json"
            if Path(item.get("path", "")).resolve() != path.resolve() or file_record(path, repo)["sha256"] != item.get("sha256"):
                raise ValidationFailure("shared proof input is stale: " + key)
        if preflight["fixture"].get("rom", {}).get("sha256") != identity["rom"]["sha256"]:
            raise ValidationFailure("tested ROM differs from the current fixture package")
        parent = repo / "build/overworld-devtools" / record.get("runId", "")
        if parent.name != record.get("runId") or not parent.name.startswith("test-"):
            raise ValidationFailure("shared proof run directory is invalid")
        observations = _shared_artifact(record.get("observationsArtifact"), parent)
        rows = load_observations(observations)
        if any(m.get("kind") == "acceleration-parity-v1" for m in test.get("measurements", [])):
            _shared_acceleration_resets(test, rows, oracle=_walk_reset_oracle(repo))
        replay = _replay_shared_test(test, rows, repo=repo)
        if (not checker_changed and replay != record.get("evaluation")) or replay.get("passed") is not True \
                or replay["observedFrames"] < registration["minimumObservedFrames"]:
            raise ValidationFailure("independent shared observation replay did not prove the declared result")
        if registration["evaluator"] == _ACTOR_INSPECT_KIND:
            from tools.overworld.devtools_actor_inspect_proof import actor_inspect_measurements, negative_controls
            oracle = _actor_inspect_probe_oracle(repo)
            evidence = actor_inspect_measurements(test, rows, record, repo, oracle=oracle)
            expected = [{"claim": "controlled-action", "name": name, "value": 1,
                         "operator": "eq", "expected": 1} for name in _ACTOR_INSPECT_NAMES]
            if evidence.get("measurements") != expected \
                    or any(type(row.get("value")) is not int or type(row.get("expected")) is not int
                           for row in evidence.get("measurements", [])) \
                    or type(evidence.get("observedFrames")) is not int \
                    or evidence.get("observedFrames") != replay["observedFrames"] \
                    or evidence.get("observedFrameUnit") != "native-inspect-cycles":
                raise ValidationFailure("actor Inspect exported evidence differs from exact facade rules")
            negatives = negative_controls(test, rows, record, repo, oracle=oracle)
            if not negatives.get("controls") or any(control.get("rejected") is not True
                                                    for control in negatives["controls"].values()):
                raise ValidationFailure("actor Inspect negative controls are missing or failed")
            if record.get("sessionCleanup") != {"sessionId": session_id, "closed": True, "errors": []}:
                raise ValidationFailure("actor Inspect private session cleanup is missing or failed")
            return {"passed": True, "acceptedProof": True, "proofAcceptance": {
                "eligible": True, "proofLevel": "S3", "mode": "prepared",
                "claims": ["controlled-action"], "requirements": [_ACTOR_INSPECT_REQUIREMENT],
                "scope": registration["scope"], "source": preflight["source"],
                "subjects": replay["subjects"], "controls": negatives["controls"],
                "controlScope": negatives["scope"], **evidence}}
        if registration["evaluator"] == _RESOLVER_KIND:
            from tools.overworld.devtools_resolver_proof import resolver_measurements, negative_controls
            oracle = _resolver_probe_oracle(repo)
            evidence = resolver_measurements(test, rows, record, repo, oracle=oracle)
            if evidence["observedFrames"] != replay["observedFrames"]:
                raise ValidationFailure("resolver native cycle credit differs between readers")
            negatives = negative_controls(test, rows, record, repo, oracle=oracle)
            cleanup = record.get("sessionCleanup", {})
            if cleanup != {"sessionId": session_id, "closed": True, "errors": []}:
                raise ValidationFailure("resolver private session cleanup is missing or failed")
            return {"passed": True, "acceptedProof": True, "proofAcceptance": {
                "eligible": True, "proofLevel": "S3", "mode": "prepared",
                "claims": ["profile-resolution"], "requirements": [_RESOLVER_REQUIREMENT],
                "scope": registration["scope"], "source": preflight["source"],
                "subjects": {}, "controls": negatives["controls"], "controlScope": negatives["scope"], **evidence}}
        if registration["proofLevel"] == "S5":
            measured = [sample["frame"] for row in rows if row.get("phase") == "observe"
                        for sample in row.get("samples", [])]
            if len(measured) < 5000 or any(right != left + 1 for left, right in zip(measured, measured[1:])):
                raise ValidationFailure("shared identity soak lost its continuous measured frame window")
        controls = ["absent-subject", "stale-subject"]
        additional = {}
        # Optional screenshots belong only to human-view artifacts. Neither
        # image content nor metadata can add, remove or substitute claim proof.
        if registration["evaluator"] == "actor-binding-context-v1":
            meter = replay["measurements"]["actor-binding-context-v1"]
            if meter.get("ready") is not True or not meter.get("bindingReceipt"):
                raise ValidationFailure("binding lacks public context and complete Walk")
            if any(type(meter.get("measurements", {}).get(name)) is not int
                   or meter["measurements"][name] != expected
                   for name, expected in (("binding-live-subject-count", 1),
                       ("binding-owner-context-mismatch-count", 0), ("binding-identity-failure-count", 0))):
                raise ValidationFailure("binding measurements do not meet the original exact rules")
            additional["measurements"] = [{"claim": "live-actor-identity", "name": name,
                "value": meter["measurements"][name], "operator": "eq", "expected": expected}
                for name, expected in (("binding-live-subject-count", 1),
                    ("binding-owner-context-mismatch-count", 0), ("binding-identity-failure-count", 0))]
            controls.extend(["binding-wrong-return", "binding-missing-return",
                *("binding-missing:" + name for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"))])
        elif registration["evaluator"] == _MOUNT_BEGIN_KIND:
            additional.update(_shared_mount_begin(test, rows, record, repo))
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
        elif registration["evaluator"] == _ROLE_TRANSFER_KIND:
            additional.update(_shared_role_transfer(rows, record))
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
        elif registration["evaluator"] == _ROLE_CONTROL_KIND:
            additional.update(_shared_role_transfer(rows, record, reader_control=True))
        elif registration["evaluator"] == "acceleration-parity-v1":
            from tools.overworld.devtools_acceleration_acceptance import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNT_PACING_KIND:
            from tools.overworld.devtools_mount_pacing_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNT_CONTROL_STRESS_KIND:
            from tools.overworld.devtools_mount_control_stress_proof import measurements, FAULTS
            requirement = registration["requirements"][0]
            additional["measurements"] = measurements(replay, requirement)
            cleanup = record.get("sessionCleanup")
            if not isinstance(cleanup, dict) or cleanup.get("sessionId") != session_id \
                    or cleanup.get("closed") is not True or cleanup.get("errors") != []:
                raise ValidationFailure("mounted control stress lacks successful owned-session cleanup")
            additional["sessionCleanup"] = cleanup
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_HOP_ARC_KIND:
            from tools.overworld.devtools_mounted_hop_arc_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_NEAREST_DIAGONAL_KIND:
            from tools.overworld.devtools_mounted_nearest_diagonal_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WILD_LEDGE_KIND:
            from tools.overworld.devtools_wild_ledge_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WILD_TELEPORT_KIND:
            from tools.overworld.devtools_wild_teleport_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _RUNNER_STOP_SKID_KIND:
            from tools.overworld.devtools_runner_stop_skid_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _RUNNER_TURN_RUNWAY_KIND:
            from tools.overworld.devtools_runner_turn_runway_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WILD_TRANSITION_KIND:
            from tools.overworld.devtools_wild_transition_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _FOLLOWER_TRANSITION_KIND:
            from tools.overworld.devtools_follower_transition_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_STREAMING_KIND:
            from tools.overworld.devtools_mounted_streaming_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_CARDINAL_STREAMING_KIND:
            from tools.overworld.devtools_mounted_cardinal_streaming_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_HOP_TRANSITION_KIND:
            from tools.overworld.devtools_mounted_hop_transition_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_WALK_TRANSITION_KIND:
            from tools.overworld.devtools_mounted_walk_transition_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _LAND_SURF_KIND:
            from tools.overworld.devtools_land_surf_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _SPAWN_WORK_BUDGET_KIND:
            from tools.overworld.devtools_spawn_work_budget_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _UNMOUNTED_ZERO_STUTTER_KIND:
            from tools.overworld.devtools_unmounted_zero_stutter_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _POPULATION_FAST_TRAVEL_KIND:
            from tools.overworld.devtools_population_fast_travel_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WARP_GATE_KIND:
            from tools.overworld.devtools_warp_gate_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WILD_BATTLE_HANDOFF_KIND:
            from tools.overworld.devtools_wild_battle_handoff_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNTED_TELEPORT_MATRIX_KIND:
            from tools.overworld.devtools_mounted_teleport_matrix_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _APPEAR_HOP_KIND:
            from tools.overworld.devtools_appear_hop_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif (adapter := get_adapter(registration["evaluator"])) is not None:
            additional["measurements"] = adapter.measurements(replay, record)
            controls = list(adapter.faults)
            if not adapter.is_control:
                additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
        elif registration["evaluator"] == _WILD_WALK_KIND:
            from tools.overworld.devtools_wild_walk_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WILD_CLEAR_CONTROL_KIND:
            from tools.overworld.devtools_wild_clear_control_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _MOUNT_POSE_CONTROL_KIND:
            from tools.overworld.devtools_mount_pose_control_proof import measurements, FAULTS
            additional["measurements"] = measurements(replay, record)
            controls = list(FAULTS)
        elif registration["evaluator"] == _WALK_POLICY_CONTROL_KIND:
            from tools.overworld.devtools_walk_policy_control_proof import measurements, FAULTS
            subject = replay["measurements"][_WALK_POLICY_CONTROL_KIND]["subject"]
            descriptor = load_debug_descriptor(repo / "build/overworld-system.debug.json")
            state, capacity = descriptor["state"], descriptor["capacities"]["actors"]
            slot = subject["handle"]["slot"]
            if type(slot) is not int or not 0 <= slot < capacity:
                raise ValidationFailure("Walk policy control slot differs from current descriptor")
            address = (state["address"] + state["offsets"]["actors"]
                       + state["actorStride"] * slot + state["actorPolicyOffset"])
            additional["measurements"] = measurements(replay, record, policy_address=address)
            controls = list(FAULTS)
        elif registration["evaluator"] == "chain-retry-v1":
            from tools.overworld.chain_retry_proof import measurements
            from tools.overworld.devtools_chain_retry_measurement import RETRY_FAULTS
            additional["measurements"] = measurements(replay, record)
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            controls.extend("missing-meaning:" + name for name in _LEDYBA_REQUIRED_MEANINGS)
            controls.extend(RETRY_FAULTS)
        elif registration["evaluator"] == "ledyba-chain-v1":
            additional["measurements"] = _shared_ledyba_measurements(replay)
            controls.extend("missing-meaning:" + name for name in _LEDYBA_REQUIRED_MEANINGS)
        elif registration["evaluator"] in _POOL_KINDS:
            additional["measurements"] = _shared_pool_measurements(replay, registration["evaluator"])
            controls.extend(["pool-missing-finalization", "pool-replaced-site"])
            controls.extend("pool-missing-meaning:" + name for name in _LEDYBA_REQUIRED_MEANINGS)
            if registration["evaluator"] == "pool-spawn-surface-v1":
                controls.extend(_POOL_SURFACE_CONTROLS)
        elif registration["evaluator"] == "live-observer-control-v1":
            additional["measurements"] = _shared_live_control_measurements(replay, record)
            additional["recorderControlCleanup"] = record["observerControlCleanup"]
        elif registration["evaluator"] == _HEIGHT_CONTROL_KIND:
            additional["measurements"] = _shared_height_control_measurements(replay)
            controls.extend(_HEIGHT_MEANING_CONTROLS)
        elif registration["evaluator"] == _ROUTE_CONTROL_KIND:
            from tools.overworld.route_control_proof import route_control_measurements
            additional["measurements"] = route_control_measurements(replay["measurements"][_ROUTE_CONTROL_KIND], record)
            additional["recorderControlCleanup"] = record["observerControlCleanup"]
            controls = list(_ROUTE_CONTROL_NEGATIVES)
        elif registration["evaluator"] == _CADENCE_KIND:
            from tools.overworld.route_cadence_proof import cadence_measurements
            from tools.overworld.route_cadence_negatives import FAULTS
            if registration["requirements"] != [_CADENCE_REQUIREMENT]:
                raise ValidationFailure("exact two-queue cadence budget belongs only to the registered full route")
            additional["measurements"] = cadence_measurements(replay["measurements"][_CADENCE_KIND])
            additional["guestQueueCadence"] = _shared_cadence_queue_budget(rows)
            cleanup = record.get("sessionCleanup")
            if not isinstance(cleanup, dict) or cleanup.get("sessionId") != session_id \
                    or cleanup.get("closed") is not True or cleanup.get("errors") != []:
                raise ValidationFailure("full route lacks successful owned-session cleanup")
            additional["sessionCleanup"] = record["sessionCleanup"]
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            controls = list(FAULTS)
        elif registration["evaluator"] == _GAME_CADENCE_KIND:
            from tools.overworld.route_cadence_proof import game_cadence_measurements
            from tools.overworld.route_cadence_negatives import BASE_FAULTS
            if registration["requirements"] != [_GAME_CADENCE_REQUIREMENT]:
                raise ValidationFailure("exact two-queue cadence budget belongs only to the current game route")
            measured = replay["measurements"][_GAME_CADENCE_KIND]
            additional["measurements"] = game_cadence_measurements(measured)
            additional["guestQueueCadence"] = _shared_cadence_queue_budget(rows)
            if additional["guestQueueCadence"]["budgetArm9Ticks"] != registration.get("guestQueueBudgetArm9Ticks"):
                raise ValidationFailure("current game route guest queue budget differs from its registered bound")
            cleanup = record.get("sessionCleanup")
            if not isinstance(cleanup, dict) or cleanup.get("sessionId") != session_id \
                    or cleanup.get("closed") is not True or cleanup.get("errors") != []:
                raise ValidationFailure("current game route lacks successful owned-session cleanup")
            additional["sessionCleanup"] = record["sessionCleanup"]
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            additional["hostCpuDiagnostics"] = {
                key: measured.get(key)
                for key in ("diagnosticContinueHostHitches", "hostCpuViolation", "hostCpuWorst", "hostCpuLatest")
                if key in measured
            }
            controls = [*BASE_FAULTS, "cadence-player-start-stall"]
        negatives = {name: _replay_shared_test(test, rows, fault=name, repo=repo) for name in controls}
        if registration["evaluator"] == _WILD_LEDGE_KIND:
            from tools.overworld.devtools_wild_ledge_proof import measurements
            for name, result in negatives.items():
                if result.get("passed") is True:
                    try:
                        measurements(result, record)
                    except (ValueError, KeyError, TypeError) as error:
                        result["passed"] = False
                        result["failures"] = [{"code": "proof-control-rejected", "message": str(error)}]
        if any(result.get("passed") is not False or not result.get("failures") for result in negatives.values()):
            raise ValidationFailure("shared identity checker failed a required subject control")
        if registration["evaluator"] == _ROUTE_CONTROL_KIND:
            from tools.overworld.route_control_negatives import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(name, result)
        if registration["evaluator"] == "acceleration-parity-v1":
            from tools.overworld.devtools_acceleration_acceptance import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNT_PACING_KIND:
            from tools.overworld.devtools_mount_pacing_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNT_CONTROL_STRESS_KIND:
            from tools.overworld.devtools_mount_control_stress_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_HOP_ARC_KIND:
            from tools.overworld.devtools_mounted_hop_arc_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_NEAREST_DIAGONAL_KIND:
            from tools.overworld.devtools_mounted_nearest_diagonal_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WILD_LEDGE_KIND:
            from tools.overworld.devtools_wild_ledge_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WILD_TELEPORT_KIND:
            from tools.overworld.devtools_wild_teleport_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _RUNNER_STOP_SKID_KIND:
            from tools.overworld.devtools_runner_stop_skid_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _RUNNER_TURN_RUNWAY_KIND:
            from tools.overworld.devtools_runner_turn_runway_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WILD_TRANSITION_KIND:
            from tools.overworld.devtools_wild_transition_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _FOLLOWER_TRANSITION_KIND:
            from tools.overworld.devtools_follower_transition_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_STREAMING_KIND:
            from tools.overworld.devtools_mounted_streaming_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_CARDINAL_STREAMING_KIND:
            from tools.overworld.devtools_mounted_cardinal_streaming_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_HOP_TRANSITION_KIND:
            from tools.overworld.devtools_mounted_hop_transition_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_WALK_TRANSITION_KIND:
            from tools.overworld.devtools_mounted_walk_transition_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _LAND_SURF_KIND:
            from tools.overworld.devtools_land_surf_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _SPAWN_WORK_BUDGET_KIND:
            from tools.overworld.devtools_spawn_work_budget_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _UNMOUNTED_ZERO_STUTTER_KIND:
            from tools.overworld.devtools_unmounted_zero_stutter_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _POPULATION_FAST_TRAVEL_KIND:
            from tools.overworld.devtools_population_fast_travel_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WARP_GATE_KIND:
            from tools.overworld.devtools_warp_gate_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WILD_BATTLE_HANDOFF_KIND:
            from tools.overworld.devtools_wild_battle_handoff_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNTED_TELEPORT_MATRIX_KIND:
            from tools.overworld.devtools_mounted_teleport_matrix_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _APPEAR_HOP_KIND:
            from tools.overworld.devtools_appear_hop_proof import validate_negative_result
            for name, result in negatives.items():
                if not validate_negative_result(result, name):
                    raise ValidationFailure("Appear Hop copied-data control did not reject")
        if (adapter := get_adapter(registration["evaluator"])) is not None:
            for name, result in negatives.items():
                adapter.validate_negative_result(result, name)
        if registration["evaluator"] == _WILD_WALK_KIND:
            from tools.overworld.devtools_wild_walk_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WILD_CLEAR_CONTROL_KIND:
            from tools.overworld.devtools_wild_clear_control_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _MOUNT_POSE_CONTROL_KIND:
            from tools.overworld.devtools_mount_pose_control_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _WALK_POLICY_CONTROL_KIND:
            from tools.overworld.devtools_walk_policy_control_proof import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(result, name)
        if registration["evaluator"] == _CADENCE_KIND:
            from tools.overworld.route_cadence_negatives import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(name, result)
        if registration["evaluator"] == _GAME_CADENCE_KIND:
            from tools.overworld.route_cadence_negatives import validate_negative_result
            for name, result in negatives.items():
                validate_negative_result(name, result, kind=_GAME_CADENCE_KIND)
        if registration["evaluator"] == _HEIGHT_CONTROL_KIND:
            for fault, reason in (("height-control-missing-meaning", "native spawn-height read control is missing"),
                                  ("height-control-unrestored", "native height control clean/restored source, context, point or data differs")):
                meter = negatives[fault].get("measurements", {}).get(_HEIGHT_CONTROL_KIND, {})
                if not any(error.get("code") == "invalid-spawn-height-control" and error.get("message") == reason
                           for error in meter.get("failures", [])):
                    raise ValidationFailure("height recorder control did not fail on its removed native meaning")
        if registration["evaluator"] == "ledyba-chain-v1":
            for name in _LEDYBA_REQUIRED_MEANINGS:
                meter = negatives["missing-meaning:" + name].get("measurements", {}).get("ledyba-chain-v1", {})
                reason = "missing-motion-start-event" if name == "MOTION_STARTED" else "missing-or-duplicate-terminal-event"
                if not any(error.get("reason") == reason and (name == "MOTION_STARTED" or error.get("event") == name)
                           for error in meter.get("measurementErrors", [])):
                    raise ValidationFailure("required-event control did not fail for its missing meaning: " + name)
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
        elif registration["evaluator"] in _POOL_KINDS:
            for name in _LEDYBA_REQUIRED_MEANINGS:
                meter = negatives["pool-missing-meaning:" + name].get("measurements", {}).get(registration["evaluator"], {})
                reason = "missing-motion-start-event" if name == "MOTION_STARTED" else "missing-or-duplicate-terminal-event"
                if not any(error.get("reason") == reason and (name == "MOTION_STARTED" or error.get("event") == name)
                           for error in meter.get("measurementErrors", [])):
                    raise ValidationFailure("POOL control did not fail on the missing meaning: " + name)
            for fault, expected in (("pool-missing-finalization", "invalid-pool-receipt"),
                                    ("pool-replaced-site", "pool-destination-replaced")):
                meter = negatives[fault].get("measurements", {}).get(registration["evaluator"], {})
                if not any(error.get("code") == expected for error in meter.get("failures", [])):
                    raise ValidationFailure("POOL control did not fail on its exact placement fault")
            if registration["evaluator"] == "pool-spawn-surface-v1":
                for fault in _POOL_SURFACE_CONTROLS:
                    meter = negatives[fault].get("measurements", {}).get(registration["evaluator"], {})
                    if not any(error.get("code") == "invalid-spawn-surface" for error in meter.get("surfaceErrors", [])):
                        raise ValidationFailure("POOL surface control did not fail on its removed native meaning")
            additional["recorderControl"] = _shared_recorder_control(record, registration, repo)
            if registration["evaluator"] == "pool-spawn-surface-v1":
                additional["surfaceRecorderControl"] = _shared_surface_recorder_control(record, repo)
        return {"passed": True, "acceptedProof": True, "proofAcceptance": {
            "eligible": True, "proofLevel": registration["proofLevel"], "mode": test["mode"],
            "claims": registration["claims"], "requirements": registration["requirements"],
            "scope": registration["scope"], "source": preflight["source"],
            "observedFrames": replay["observedFrames"], "subjects": replay["subjects"],
            "controls": {name: {"rejected": True, "failures": result["failures"]} for name, result in negatives.items()},
            "controlScope": "controller evaluator controls; live recorder calibration is separate",
            **additional}}
    except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
        return {"passed": False, "acceptedProof": False, "proofAcceptance": {"eligible": True, "reason": str(error)}}


def _scenario_recheck(args: argparse.Namespace) -> int:
    """Check one retained run in this fresh host process, without a game boot.

    The original manifest is immutable. Return current acceptance separately;
    final roadmap acceptance still checks the same data and current inputs.
    """
    name = args.run_id
    if not isinstance(name, str) or not name.startswith("test-") or Path(name).name != name:
        raise ValidationFailure("recheck needs one shared test run ID")
    path = REPO / "build/overworld-devtools" / name / "manifest.json"
    if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > MANIFEST_MAX_BYTES:
        raise ValidationFailure("recheck needs a bounded owned test manifest")
    record = json.loads(path.read_text())
    if record.get("runId") != name:
        raise ValidationFailure("recheck manifest run identity differs")
    test_id = record.get("test")
    if not isinstance(test_id, str) or Path(test_id).name != test_id:
        raise ValidationFailure("recheck test identity differs")
    test = json.loads((REPO / "tests/overworld/test-recipes" / (test_id + ".json")).read_text())
    result = finalize_shared_test(test, record, REPO)
    proof = result.get("proofAcceptance", {})
    # Compact by default. Never print the entire nested control evidence.
    summary = {"runId": name, "manifest": _relative(path), "gameStarted": False,
               "manifestChanged": False, "passed": result.get("passed") is True,
               "acceptedProof": result.get("acceptedProof") is True,
               "requirements": proof.get("requirements", []), "replayMode": proof.get("replayMode"),
               "reason": proof.get("reason")}
    if args.json:
        _json(summary)
    else:
        print(name + (": current proof accepted" if summary["acceptedProof"] else
                      ": " + str(summary["reason"])))
    return 0 if summary["acceptedProof"] else 1


def _scenario_run(args: argparse.Namespace) -> int:
    _, scenarios = _load_contracts(audit_runtime_proof_sources=True)
    scenario = scenarios.get(args.scenario_id)
    if args.scenario_id in RUNTIME_PROOF_REGISTRY["runners"]:
        raise ValidationFailure("runtime requirement is migration-pending; no shared test is mapped: " + args.scenario_id)
    adapter = (scenario or {}).get("adapter") or {}
    test_name = adapter.get("test") if adapter.get("kind") == "devtools-test" else None
    if scenario is not None and scenario.get("proofLevel") in RUNTIME_PROOF_LEVELS and test_name is None:
        raise ValidationFailure(
            f"runtime scenario {args.scenario_id} is a retained migration requirement, not an executable "
            "legacy runner; author its shared-devtools test (runtime_proof_migration.json)"
        )
    # New data-only tests can also be named directly. They remain diagnostic
    # unless the shared controller has reviewed, exact measurement mappings.
    if scenario is None and isinstance(args.scenario_id, str) \
            and args.scenario_id and all(c in "abcdefghijklmnopqrstuvwxyz0123456789._-" for c in args.scenario_id) \
            and ".." not in args.scenario_id:
        candidate = REPO / "tests/overworld/test-recipes" / (args.scenario_id + ".json")
        if candidate.is_file(): test_name = args.scenario_id
    if test_name is not None:
        if args.evidence is not None or args.manifest_output is not None:
            raise ValidationFailure("shared tests own their immutable artifacts; evidence replay and manifest overrides are unavailable")
        if scenario is not None and scenario.get("status") != "active":
            raise ValidationFailure("planned shared scenario is not executable")
        if args.dry_run:
            result = {"scenario": args.scenario_id, "test": test_name, "executionMethod": "shared-devtools",
                      "executed": False, "passed": False, "acceptedProof": False}
        else:
            from tools.overworld.devtools_cli import DEFAULT_URL, request
            response = request(getattr(args, "url", DEFAULT_URL), {"op": "test.start", "args": {"name": test_name}})
            result = {**response, "scenario": args.scenario_id, "executionMethod": "shared-devtools",
                      "passed": False, "acceptedProof": False}
            if response.get("ok") is not True:
                _json(result)
                return 1
        _json(result)
        return 0  # Start acknowledged, explicitly NOT a completed proof pass.
    if args.dry_run:
        return _scenario_run_locked(args)
    with scenario_lock(REPO):
        return _scenario_run_locked(args)


def _scenario_inputs(scenario: dict[str, Any]) -> dict[str, Any]:
    fixture = scenario.get("fixture", {})
    paths = [Path(fixture.get("rom", "test.nds")),
             Path("build/pokemon_move_history_capture_build.json"), DEBUG_DESCRIPTOR,
             *(item[3] for item in OVERWORLD_PRODUCT_OUTPUTS),
             *(item[1] for item in OVERWORLD_LINKED_OUTPUTS)]
    if fixture.get("save"):
        paths.append(Path(fixture["save"]["path"]))
    return {"source": source_record(REPO),
            "files": [file_record(path, REPO) for path in paths]}


def _actor_evaluation(scenario: dict[str, Any], evidence_path: Path,
                      results: list[dict[str, Any]], artifacts: Path) -> dict[str, Any]:
    # Preserve even malformed raw output before attempting to parse it.
    result: dict[str, Any] = {"passed": False, "resultKind": "actor-observation-error"}
    try:
        record = file_record(evidence_path, REPO)
        if record is None or not record.get("present"):
            raise ValidationFailure("actor evidence was not produced")
        result["evidence"] = {key: record[key] for key in ("path", "size", "sha256")}
        archive_step(result, REPO, artifacts, len(results))
        archived = result["evidence"]
        trace_schema = load_trace_schema(TRACE_SCHEMA)
        evidence = load_evidence(REPO / archived["path"], trace_schema)
        descriptor = load_debug_descriptor(DEBUG_DESCRIPTOR)
        require_descriptor_identity(evidence, descriptor)
        require_scenario_provenance(evidence, scenario, REPO, _actor_evidence_session(results))
        result = evaluate_scenario_evidence(scenario, evidence, trace_schema)
        negative = evaluate_subject_negative_control(scenario, evidence, trace_schema)
        behavior_negative = evaluate_behavior_negative_control(scenario, evidence, trace_schema)
        result.update(subjectNegativeControl=negative, behaviorNegativeControl=behavior_negative,
                      evidence=archived,
                      passed=result["passed"] and negative["passed"] and behavior_negative["passed"])
    except (OSError, ValueError, ValidationFailure) as error:
        result.update(passed=False, resultError=f"actor evidence rejected: {error}")
    return result


def _scenario_run_locked(args: argparse.Namespace) -> int:
    _, scenarios = _load_contracts(audit_runtime_proof_sources=True)
    scenario = scenarios.get(args.scenario_id)
    if scenario is None:
        raise ValidationFailure(f"unknown scenario: {args.scenario_id}")
    if scenario.get("proofLevel") in RUNTIME_PROOF_LEVELS:
        raise ValidationFailure("runtime execution uses shared-devtools jobs, never command adapters")
    if scenario["status"] != "active" or scenario["adapter"] is None:
        raise ValidationFailure(
            f"scenario is planned and has no truthful runtime adapter: {args.scenario_id}"
        )
    adapter = scenario["adapter"]
    if args.evidence is not None and adapter.get("claims"):
        raise ValidationFailure(
            "explicit evidence replay cannot re-prove runtime claims; "
            "run the scenario's declared command"
        )
    fixture_commands = []  # S0-S2 host checks only; runtime preflight belongs to the shared job.
    if adapter["kind"] == "command-sequence":
        if args.evidence is not None:
            raise ValidationFailure("--evidence needs an actor-observation adapter")
        commands = fixture_commands + [
            _expand_command(command) for command in adapter["commands"]
        ]
    else:
        commands = fixture_commands + (
            [_expand_command(command) for command in adapter.get("commands", [])]
            if args.evidence is None
            else []
        )
    evidence_path = None
    if adapter["kind"] == "actor-observation":
        if args.evidence is not None:
            evidence_path = (
                args.evidence if args.evidence.is_absolute() else REPO / args.evidence
            )
        elif "evidence" in adapter:
            evidence_path = REPO / adapter["evidence"]
    if args.dry_run:
        result = {
            "schemaVersion": 1,
            "scenario": args.scenario_id,
            "proofLevel": scenario["proofLevel"],
            "costTier": scenario["costTier"],
            "commands": commands,
            "evidence": _relative(evidence_path) if evidence_path is not None else None,
            "evidenceRequired": (
                adapter["kind"] == "actor-observation"
                and evidence_path is None
            ),
            "executed": False,
        }
        if args.json:
            _json(result)
        else:
            print(f"DRY RUN {args.scenario_id}")
            if commands:
                for command in commands:
                    print("  " + " ".join(command))
            elif evidence_path is None:
                print("  supply --evidence <actor-observation.json>")
            else:
                print(f"  evaluate {_relative(evidence_path)}")
        return 0

    started_at = utc_now()
    initial_inputs = _scenario_inputs(scenario)
    artifacts = artifact_directory(REPO)
    results = []
    if adapter["kind"] == "actor-observation":
        if evidence_path is None:
            raise ValidationFailure(
                f"scenario needs --evidence from scripts/owctl actor capture: {args.scenario_id}"
            )
        if commands:
            evidence_path.unlink(missing_ok=True)
    for command_index, command in enumerate(commands):
        result = {"command": command, "passed": False, "returnCode": None}
        fixture_command = command_index < len(fixture_commands)
        try:
            measurement_contract = _runtime_measurement_contract(command)
            if (
                adapter.get("claims")
                and measurement_contract is None
                and not fixture_command
            ):
                raise ValidationFailure(
                    "runtime command has no registered measurement contract: "
                    + " ".join(command)
                )
            result = _run_command(
                command,
                "json-passed" if fixture_command else adapter["result"],
                () if fixture_command else adapter.get("claims", ()),
                measurement_contract=measurement_contract,
                minimum_frames=adapter.get("minimumFrames", 0),
                maximum_frames=scenario["stop"]["frameBudget"],
                visual_artifact=(
                    None if fixture_command else adapter.get("visualArtifact")
                ),
                log_directory=artifacts,
                log_index=command_index,
            )
            result["failureStage"] = "fixture-preflight" if fixture_command else "runtime"
            archive_step(result, REPO, artifacts, len(results))
        except (OSError, ValueError, ValidationFailure) as error:
            # Only a missing executable is proven to precede gameplay.
            result["failureStage"] = ("collector-launch" if isinstance(error, FileNotFoundError)
                                      and result.get("returnCode") is None
                                      else "fixture-preflight" if fixture_command else "runtime")
            result.update(passed=False, resultError=f"collector failed: {error}")
            # Output is saved before result parsing. Retain its links even if
            # parsing or visual-evidence inspection raises instead of returning.
            for name in ("stdout", "stderr"):
                try:
                    saved = file_record(artifacts / f"{command_index}-{name}.log", REPO)
                    if saved and saved.get("present"):
                        result[name + "Artifact"] = {
                            key: saved[key] for key in ("path", "size", "sha256")}
                        result[name + "Sha256"] = saved["sha256"]
                except OSError as log_error:
                    result["resultError"] += f"; {name} log unreadable: {log_error}"
            if result.get("stdoutArtifact") or result.get("stderrArtifact"):
                # A missing file after capture is not a collector-launch failure.
                result["failureStage"] = "fixture-preflight" if fixture_command else "runtime"
        results.append(result)
        if not result["passed"]:
            break
    if adapter["kind"] == "actor-observation":
        assert evidence_path is not None
        if not results or all(result["passed"] for result in results):
            results.append(_actor_evaluation(scenario, evidence_path, results, artifacts))
        elif evidence_path.is_file():
            # Keep the raw recording from a failed collector; do not turn it
            # into accepted actor proof by running the evaluator alone.
            record = file_record(evidence_path, REPO)
            raw = {"passed": False, "resultKind": "failed-collector-evidence",
                   "evidence": {key: record[key] for key in ("path", "size", "sha256")}}
            try:
                archive_step(raw, REPO, artifacts, len(results))
            except (OSError, ValidationFailure) as error:
                raw["resultError"] = str(error)
            results.append(raw)
    try:
        inputs_changed = _scenario_inputs(scenario) != initial_inputs
        input_error = "product or proof inputs changed during the run"
    except (OSError, ValidationFailure) as error:
        inputs_changed, input_error = True, str(error)
    if inputs_changed:
        results.append({"passed": False, "resultKind": "input-identity-error",
                        "resultError": input_error})
    document = make_run_manifest(
        repo=REPO,
        kind="scenario",
        target=args.scenario_id,
        proof_level=scenario["proofLevel"],
        cost_tier=scenario["costTier"],
        scenario=scenario,
        commands=commands,
        results=results,
        started_at=started_at,
        source_identity=initial_inputs["source"],
    )
    document["inputIdentityAtStart"] = initial_inputs
    output = write_run_manifest(document, REPO, args.manifest_output)
    response = {
        "passed": document["result"]["passed"],
        "runId": document["runId"],
        "manifest": _relative(output),
        "steps": results,
    }
    if args.json:
        _json(response)
    else:
        print("PASS" if response["passed"] else "FAIL", args.scenario_id)
        print(f"manifest: {_relative(output)}")
    return 0 if response["passed"] else 1


def _trace_decode(args: argparse.Namespace) -> int:
    schema_path = args.schema if args.schema.is_absolute() else REPO / args.schema
    trace_path = args.trace if args.trace.is_absolute() else REPO / args.trace
    schema = load_trace_schema(schema_path)
    document = filter_events(
        decode_trace(trace_path, schema), args.actor, args.event
    )
    if args.json:
        _json(document)
    else:
        header = document["header"]
        print(
            f"events={len(document['events'])} fieldEpoch={header.get('fieldEpoch', '?')} "
            f"overwritten={header.get('overwrittenCount', '?')}"
        )
        for event in document["events"]:
            print(
                f"{event['sequence']:>6} f={event['frame']:<7} "
                f"actor=0x{event['actorHandle']:08X} "
                f"{event['event']:<22} {event['reason']:<18} "
                f"a={event['valueA']} b={event['valueB']}"
            )
    return 0


def _actor_source(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source if args.source.is_absolute() else REPO / args.source
    data = source.read_bytes()
    schema = load_trace_schema(TRACE_SCHEMA)
    descriptor_path = (
        args.descriptor if args.descriptor.is_absolute() else REPO / args.descriptor
    )
    descriptor = load_debug_descriptor(descriptor_path)
    if data.lstrip().startswith(b"{"):
        evidence = load_evidence(source, schema)
        require_descriptor_identity(evidence, descriptor)
        return evidence
    base = args.base if args.base is not None else descriptor["state"]["address"]
    return capture_memory_file(
        source,
        base,
        descriptor,
        schema,
        include_inactive=args.include_inactive,
    )


def _actor_inspect(args: argparse.Namespace) -> int:
    evidence = _actor_source(args)
    actors = evidence["observation"]["actors"]
    if args.index is not None:
        actors = [actor for actor in actors if actor["index"] == args.index]
        if not actors:
            raise ValidationFailure(f"actor index is not present in the capture: {args.index}")
    if args.json:
        _json(
            {
                "schemaVersion": 1,
                "fieldEpoch": evidence["observation"]["fieldEpoch"],
                "actors": actors,
            }
        )
    else:
        print(
            f"fieldEpoch={evidence['observation']['fieldEpoch']} actors={len(actors)}"
        )
        for actor in actors:
            handle = actor["handle"]
            print(
                f"[{actor['index']:>2}] 0x{handle['value']:08X} "
                f"{actor['role']:<9} species={actor['species']:<3} "
                f"motion={actor['motionKind']}/{actor['motionPhase']} "
                f"logical=({actor['logical']['x']},{actor['logical']['y']}) "
                f"render=({actor['render']['x']},{actor['render']['y']}) "
                f"input={actor['inputOwnership']} commit={actor['commitSequence']}"
            )
    return 0


def _actor_trace(args: argparse.Namespace) -> int:
    evidence = _actor_source(args)
    document = filter_events(
        evidence["observation"]["trace"], args.actor, args.event
    )
    if args.json:
        _json(document)
    else:
        header = document["header"]
        print(
            f"events={len(document['events'])} fieldEpoch={header['fieldEpoch']} "
            f"overwritten={header['overwrittenCount']}"
        )
        for event in document["events"]:
            print(
                f"{event['sequence']:>6} f={event['frame']:<7} "
                f"actor=0x{event['actorHandle']:08X} "
                f"{event['event']:<22} {event['reason']:<18} "
                f"a={event['valueA']} b={event['valueB']}"
            )
    return 0


def _actor_capture(args: argparse.Namespace) -> int:
    source = args.source if args.source.is_absolute() else REPO / args.source
    descriptor_path = (
        args.descriptor if args.descriptor.is_absolute() else REPO / args.descriptor
    )
    descriptor = load_debug_descriptor(descriptor_path)
    schema = load_trace_schema(TRACE_SCHEMA)
    base = args.base if args.base is not None else descriptor["state"]["address"]
    provenance = None
    execution = None
    provenance_arguments = (args.scenario_id, args.rom, args.save, args.seed)
    if any(value is not None for value in provenance_arguments):
        if args.scenario_id is None or args.rom is None or args.seed is None:
            raise ValidationFailure(
                "reusable evidence provenance needs --scenario-id, --rom, and --seed"
            )
        rom = args.rom if args.rom is None or args.rom.is_absolute() else REPO / args.rom
        save = (
            args.save if args.save is None or args.save.is_absolute() else REPO / args.save
        )
        provenance = build_evidence_provenance(
            scenario_id=args.scenario_id,
            rom=rom,
            save=save,
            seed=args.seed,
        )
    if args.execution is not None:
        execution_path = (
            args.execution if args.execution.is_absolute() else REPO / args.execution
        )
        execution = load_execution_record(execution_path)
        if not execution["completed"]:
            raise ValidationFailure("actor evidence input execution did not complete")
        if (
            provenance is not None
            and execution["scenarioId"] != provenance["scenarioId"]
        ):
            raise ValidationFailure(
                "execution record belongs to a different provenance scenario"
            )
    if args.output is not None and provenance is None:
        raise ValidationFailure(
            "reusable evidence output needs explicit --scenario-id, --rom, and --seed provenance"
        )
    if args.output is not None and execution is None:
        raise ValidationFailure(
            "reusable evidence output needs a completed --execution receipt"
        )
    evidence = capture_memory_file(
        source,
        base,
        descriptor,
        schema,
        include_inactive=args.include_inactive,
        provenance=provenance,
        execution=execution,
    )
    if args.output is None:
        _json(evidence)
    else:
        output = args.output if args.output.is_absolute() else REPO / args.output
        write_evidence(evidence, output)
        print(_relative(output))
    return 0


def _add_actor_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="Actor evidence or raw memory dump")
    parser.add_argument(
        "--descriptor", type=Path, default=DEBUG_DESCRIPTOR, help="Generated debug descriptor"
    )
    parser.add_argument("--base", type=lambda value: int(value, 0))
    parser.add_argument("--include-inactive", action="store_true")


def _git_changed_paths(base: str | None) -> list[str]:
    commands = []
    if base:
        commands.append(["git", "diff", "--name-only", f"{base}...HEAD", "--"])
    commands.append(["git", "diff", "--name-only", "HEAD", "--"])
    paths: set[str] = set()
    for command in commands:
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        if completed.returncode != 0:
            raise ValidationFailure(completed.stderr.strip() or "git diff failed")
        paths.update(line for line in completed.stdout.splitlines() if line)
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if untracked.returncode != 0:
        raise ValidationFailure(untracked.stderr.strip() or "git ls-files failed")
    paths.update(line for line in untracked.stdout.splitlines() if line)
    return sorted(paths)


def _matches(path: str, patterns: list[str]) -> bool:
    from fnmatch import fnmatch

    return any(fnmatch(path, pattern) for pattern in patterns)


def _exact_runtime_scenarios(
    check: dict[str, Any],
    scenario_ids: set[str],
    scenarios: dict[str, dict[str, Any]],
    accepted_runtime_evidence: dict[str, dict[str, Any]] | None = None,
    *, migration: dict[str, Any] | None = None,
) -> set[str]:
    """Return current passing scenarios for the exact runner and proof level."""
    expected = _runtime_runner_key(check["command"])
    if RUNTIME_PROOF_REGISTRY.get("executionMethod") == "shared-devtools":
        from tools.overworld.validation import resolve_runtime_migration_targets
        if migration is None:
            migration = validate_runtime_migration(json.loads((REPO /
                "tools/overworld/runtime_proof_migration.json").read_text()), RUNTIME_PROOF_REGISTRY)
        if expected not in migration["requirements"]:
            return set()
        leaves = resolve_runtime_migration_targets(migration, expected)
        expects_control = migration["requirements"][expected]["verificationKind"] == "observer-control"
        matches = {leaf: set() for leaf in leaves}
        for scenario_id in scenario_ids:
            scenario = scenarios.get(scenario_id, {})
            adapter = scenario.get("adapter") or {}
            registration = RUNTIME_PROOF_REGISTRY.get("sharedTests", {}).get(adapter.get("test"), {})
            evidence = (accepted_runtime_evidence or {}).get(scenario_id, {})
            if scenario.get("status") != "active" or scenario.get("proofLevel") != check["proofLevel"] \
                    or (scenario.get("verification", {}).get("kind") == "observer-control") != expects_control \
                    or adapter.get("kind") != "devtools-test" or not registration \
                    or (registration.get("mode") == "observer-control") != expects_control \
                    or registration.get("proofLevel") != check["proofLevel"] \
                    or adapter.get("claims") != registration.get("claims"):
                continue
            if accepted_runtime_evidence is not None and (evidence.get("execution") != "shared-devtools" \
                    or evidence.get("proofLevel") != check["proofLevel"] \
                    or evidence.get("claims") != registration["claims"]):
                continue
            for leaf in leaves:
                endpoint = migration["requirements"][leaf]
                if endpoint["status"] == "ported" and adapter["test"] in endpoint["tests"] \
                        and leaf in registration.get("requirements", []) \
                        and set(endpoint["claims"]).issubset(registration["claims"]) \
                        and (accepted_runtime_evidence is None or leaf in evidence.get("requirements", [])):
                    matches[leaf].add(scenario_id)
        return set().union(*matches.values()) if matches and all(matches.values()) else set()
    registered_claims = RUNTIME_PROOF_REGISTRY["runners"].get(expected)
    measurement_contract = RUNTIME_PROOF_REGISTRY["measurementContracts"].get(
        expected
    )
    if (
        expected is None
        or not isinstance(registered_claims, list)
        or not registered_claims
        or not isinstance(measurement_contract, dict)
        or set(measurement_contract) != set(registered_claims)
    ):
        return set()
    matched = set()
    for scenario_id in scenario_ids:
        scenario = scenarios.get(scenario_id)
        adapter = scenario.get("adapter") if scenario is not None else None
        accepted = (
            accepted_runtime_evidence.get(scenario_id)
            if accepted_runtime_evidence is not None
            else None
        )
        if (
            scenario is None
            or scenario["status"] != "active"
            or scenario.get("verification", {}).get("kind") == "observer-control"
            or scenario["proofLevel"] != check["proofLevel"]
            or not isinstance(adapter, dict)
            or adapter.get("claims") != registered_claims
            or (
                accepted_runtime_evidence is not None
                and (
                    not isinstance(accepted, dict)
                    or accepted.get("proofLevel") != check["proofLevel"]
                    or expected not in accepted.get("runners", [])
                )
            )
        ):
            continue
        if any(
            _runtime_runner_key(command) == expected
            for command in adapter.get("commands", [])
        ):
            matched.add(scenario_id)
    return matched


def _roadmap_static_results(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute every S0-S2 feature check and retain its current result."""
    results = []
    for check in sorted(
        (
            check
            for check in manifest["checks"]
            if check["proofLevel"] not in RUNTIME_PROOF_LEVELS
        ),
        key=lambda item: (
            item.get("costTier", 0),
            PROOF_LEVELS.index(item["proofLevel"]),
            item["id"],
        ),
    ):
        requirements = []
        ready = True
        for requirement in check.get("requires", []):
            present, detail = _requirement_state(requirement)
            requirements.append({
                "name": requirement,
                "present": present,
                "detail": detail,
            })
            ready &= present
        command = _expand_command(check["command"])
        if ready:
            result = _run_command(command, "exit-zero")
        else:
            result = {
                "command": command,
                "returnCode": None,
                "passed": False,
                "resultError": "required input is missing",
            }
        results.append({
            "id": check["id"],
            "proofLevel": check["proofLevel"],
            "requirements": requirements,
            **result,
        })
    return results


def _runtime_step_proves_claims(
    step: Any,
    runner: str,
    claims: list[str],
    *,
    minimum_frames: int,
    maximum_frames: int,
) -> bool:
    if (
        not isinstance(step, dict)
        or step.get("passed") is not True
        or _runtime_runner_key(step.get("command", [])) != runner
    ):
        return False
    proof_claims = step.get("proofClaims")
    proof_evidence = step.get("proofEvidence")
    contract = RUNTIME_PROOF_REGISTRY["measurementContracts"].get(runner)
    if (
        proof_claims != {claim: True for claim in claims}
        or not isinstance(proof_evidence, dict)
        or set(proof_evidence) != set(claims)
        or not isinstance(contract, dict)
        or set(contract) != set(claims)
    ):
        return False
    for claim in claims:
        measurements = proof_evidence.get(claim)
        specifications = contract.get(claim)
        if (
            not isinstance(measurements, list)
            or not measurements
            or not isinstance(specifications, list)
            or len(measurements) != len(specifications)
        ):
            return False
        for measurement, specification in zip(measurements, specifications):
            if not isinstance(measurement, dict):
                return False
            actual = measurement.get("actual")
            expected = measurement.get("expected")
            operator = measurement.get("operator", "eq")
            if (
                measurement.get("name") != specification.get("name")
                or operator != specification.get("operator")
                or "actual" not in measurement
                or "expected" not in measurement
            ):
                return False
            type_matches = {
                "integer": isinstance(actual, int)
                    and not isinstance(actual, bool),
                "array": isinstance(actual, list),
                "object": isinstance(actual, dict),
                "string": isinstance(actual, str),
            }.get(specification.get("type"), False)
            if not type_matches:
                return False
            if "expected" in specification and (
                actual != specification["expected"]
                or expected != specification["expected"]
            ):
                return False
            minimum = specification.get("minimum")
            maximum = specification.get("maximum")
            min_items = specification.get("minItems")
            required_keys = specification.get("requiredKeys", [])
            if (
                minimum is not None
                and (not isinstance(actual, int) or actual < minimum)
            ) or (
                maximum is not None
                and (not isinstance(actual, int) or actual > maximum)
            ) or (
                min_items is not None
                and (not isinstance(actual, list) or len(actual) < min_items)
            ) or (
                required_keys
                and (
                    not isinstance(actual, dict)
                    or any(key not in actual for key in required_keys)
                )
            ) or not _registry_validator_passes(
                specification, actual, expected
            ):
                return False
            if specification.get("validator") in CONTROLLER_RELATION_VALIDATORS:
                comparison = True
            else:
                try:
                    comparison = {
                        "eq": actual == expected,
                        "ne": actual != expected,
                        "lt": actual < expected,
                        "lte": actual <= expected,
                        "gt": actual > expected,
                        "gte": actual >= expected,
                    }[operator]
                except (KeyError, TypeError):
                    return False
            if not comparison:
                return False
    execution = step.get("proofExecution")
    if not isinstance(execution, dict):
        return False
    evidence_hash = hashlib.sha256(json.dumps(
        proof_evidence,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()).hexdigest()
    session = execution.get("session")
    frames = execution.get("framesObserved")
    return (
        isinstance(session, str)
        and len(session) == 32
        and all(character in "0123456789abcdef" for character in session)
        and execution.get("minimumFrames") == minimum_frames
        and execution.get("maximumFrames") == maximum_frames
        and isinstance(frames, int)
        and not isinstance(frames, bool)
        and frames >= minimum_frames
        and (maximum_frames <= 0 or frames <= maximum_frames)
        and execution.get("iterations") == 1
        and execution.get("iterationPassed") == [True]
        and execution.get("iterationFrames") == [frames]
        and execution.get("iterationEvidenceSha256") == [evidence_hash]
        and evidence_hash != hashlib.sha256(b"{}").hexdigest()
    )


def _is_runtime_fixture_command(command: Any) -> bool:
    return (
        isinstance(command, list)
        and "scripts/verify_overworld_runtime_fixture.py" in command
    )


def _roadmap_actor_evaluation_rejection(
    scenario: dict[str, Any],
    steps: list[dict[str, Any]],
) -> str | None:
    """Re-evaluate the current actor evidence and match the stored result."""
    adapter = scenario["adapter"]
    if adapter.get("kind") != "actor-observation":
        return None
    evaluations = [
        step
        for step in steps
        if isinstance(step, dict)
        and step.get("resultKind") == "actor-observation"
    ]
    if len(evaluations) != 1:
        return "actor-observation evaluation is missing or duplicated"
    stored_evidence = evaluations[0].get("evidence")
    evidence_name = stored_evidence.get("path") if isinstance(stored_evidence, dict) else None
    if not isinstance(evidence_name, str) or not evidence_name:
        return "actor-observation evidence path is missing"
    evidence_path = Path(evidence_name)
    if not evidence_path.is_absolute():
        evidence_path = REPO / evidence_path
    evidence_record = file_record(evidence_path, REPO)
    if not isinstance(evidence_record, dict) or evidence_record.get("present") is not True:
        return "actor-observation evidence is missing"
    expected_evidence = {
        "path": evidence_record["path"],
        "size": evidence_record["size"],
        "sha256": evidence_record["sha256"],
    }
    if stored_evidence != expected_evidence:
        return "actor-observation evidence identity differs"
    try:
        trace_schema = load_trace_schema(TRACE_SCHEMA)
        evidence = load_evidence(evidence_path, trace_schema)
        descriptor = load_debug_descriptor(DEBUG_DESCRIPTOR)
        require_descriptor_identity(evidence, descriptor)
        require_scenario_provenance(
            evidence,
            scenario,
            REPO,
            _actor_evidence_session(steps),
        )
        expected = evaluate_scenario_evidence(scenario, evidence, trace_schema)
        subject_negative = evaluate_subject_negative_control(
            scenario, evidence, trace_schema
        )
        behavior_negative = evaluate_behavior_negative_control(
            scenario, evidence, trace_schema
        )
    except (OSError, ValidationFailure, ValueError) as error:
        return f"actor-observation evidence is invalid: {error}"
    expected["subjectNegativeControl"] = subject_negative
    expected["behaviorNegativeControl"] = behavior_negative
    expected["passed"] = (
        expected["passed"]
        and subject_negative["passed"]
        and behavior_negative["passed"]
    )
    expected["evidence"] = expected_evidence
    if expected["passed"] is not True:
        return "actor-observation evaluation or negative control failed"
    if evaluations[0] != expected:
        return "stored actor-observation evaluation differs from current evidence"
    return None


def _roadmap_run_manifest_rejection(
    document: Any,
    scenario_id: str,
    scenario: dict[str, Any],
    runtime_fixture: dict[str, Any],
    current_source: dict[str, Any],
    current_emulator: dict[str, Any],
) -> tuple[str | None, bool]:
    """Return the rejection and whether it was a current declared attempt."""
    if not isinstance(document, dict) or document.get("schema") != RUN_SCHEMA:
        return "run schema differs", False
    identity = document.get("identity")
    result = document.get("result")
    if not isinstance(identity, dict) or not isinstance(result, dict):
        return "run identity or result is missing", False
    run_id, result_sha256 = run_id_for(
        identity,
        result,
        document.get("proofLevel"),
        document.get("costTier"),
    )
    if document.get("resultSha256") != result_sha256:
        return "run result digest differs", False
    if document.get("runId") != run_id:
        return "run identity digest differs", False
    if (
        identity.get("kind") != "scenario"
        or identity.get("target") != scenario_id
    ):
        return "scenario identity differs", False
    if document.get("proofLevel") != scenario["proofLevel"]:
        return "proof level differs", False
    if identity.get("scenarioRevision") != digest_value(scenario):
        return "scenario revision differs", False
    if identity.get("source") != current_source:
        return "source identity differs", False
    fixture_identity = runtime_fixture.get("identity", {})
    for name in (
        "rom",
        "buildManifest",
        "debugDescriptor",
        *(item[1] for item in OVERWORLD_PRODUCT_OUTPUTS),
        *(item[0] for item in OVERWORLD_LINKED_OUTPUTS),
    ):
        if identity.get(name) != fixture_identity.get(name):
            return f"{name} identity differs", False
    save = scenario.get("fixture", {}).get("save")
    save_path = Path(save["path"]) if isinstance(save, dict) else None
    if identity.get("save") != file_record(save_path, REPO):
        return "save identity differs", False
    if identity.get("seed") != scenario.get("fixture", {}).get("seed"):
        return "random seed differs", False
    if identity.get("emulator") != current_emulator:
        return "emulator identity differs", False
    adapter = scenario.get("adapter")
    if not isinstance(adapter, dict):
        return "scenario adapter is missing", False
    expected_commands = [
        _expand_command(command) for command in adapter.get("commands", [])
    ]
    recorded_commands = identity.get("commands")
    if not isinstance(recorded_commands, list):
        return "recorded command sequence is missing", False
    recorded_non_fixture = [
        command
        for command in recorded_commands
        if not _is_runtime_fixture_command(command)
    ]
    if recorded_non_fixture != expected_commands:
        return "recorded command sequence differs", False

    # From this point the manifest identifies a current execution of the exact
    # declared scenario. Any failed result is an unresolved current failure.
    if result.get("passed") is not True:
        return "run failed", True
    steps = result.get("steps")
    if not isinstance(steps, list) or not steps:
        return "run steps are missing", True
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("command"), list):
            try:
                require_command_output(step, REPO)
            except (OSError, ValidationFailure) as error:
                return f"command output rejected: {error}", True
    command_steps = [
        step
        for step in steps
        if isinstance(step, dict)
        and isinstance(step.get("command"), list)
        and not _is_runtime_fixture_command(step["command"])
    ]
    if [step["command"] for step in command_steps] != expected_commands:
        return "runtime result command sequence differs", True
    claims = adapter.get("claims")
    if not isinstance(claims, list) or not claims:
        return "scenario claims are missing", True
    expected_runners = [_runtime_runner_key(command) for command in expected_commands]
    if not expected_runners or any(runner is None for runner in expected_runners):
        return "scenario runner is missing", True
    for runner, step in zip(expected_runners, command_steps):
        assert runner is not None
        registered = RUNTIME_PROOF_REGISTRY["runners"].get(runner)
        contract = RUNTIME_PROOF_REGISTRY["measurementContracts"].get(runner)
        if (
            registered != claims
            or not isinstance(contract, dict)
            or set(contract) != set(claims)
        ):
            return "runner proof contract differs", True
        if not _runtime_step_proves_claims(
            step,
            runner,
            claims,
            minimum_frames=adapter.get("minimumFrames", 0),
            maximum_frames=scenario.get("stop", {}).get("frameBudget", 0),
        ):
            return "runner result does not prove its claims", True
        if adapter.get("visualArtifact") is not None:
            artifact = step.get("visualArtifact")
            if not isinstance(artifact, dict) or not isinstance(artifact.get("path"), str):
                return "visual evidence is missing", True
            path = Path(artifact["path"])
            if not path.is_absolute():
                path = REPO / path
            current = file_record(path, REPO)
            if (not current or current.get("present") is not True
                    or {key: current[key] for key in ("path", "size", "sha256")} != artifact
                    or not _valid_png(path)):
                return "visual evidence identity differs", True
    actor_rejection = _roadmap_actor_evaluation_rejection(scenario, steps)
    if actor_rejection is not None:
        return actor_rejection, True
    if not all(
        isinstance(step, dict) and step.get("passed") is True
        for step in steps
    ):
        return "one or more run steps failed", True
    return None, True


def _roadmap_runtime_evidence(
    scenarios: dict[str, dict[str, Any]],
    runtime_fixture: dict[str, Any],
    *,
    run_directory: Path | None = None,
    current_source: dict[str, Any] | None = None,
    current_emulator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Find current passing run manifests without starting an emulator."""
    accepted: dict[str, dict[str, Any]] = {}
    rejected = []
    if not runtime_fixture.get("passed"):
        return {
            "acceptedScenarios": accepted,
            "rejectedRuns": [{"reason": "runtime fixture is not current"}],
            "currentFailures": [],
        }
    directory = run_directory or REPO / "build/overworld-runs"
    source = current_source if current_source is not None else source_record(REPO)
    emulator = (
        current_emulator if current_emulator is not None else emulator_record(REPO)
    )
    current_failures = []
    failed_documents = []
    accepted_ids: dict[str, set[str]] = {}
    paths = sorted(directory.glob("**/*.json")) if directory.is_dir() else []
    runtime_scenarios = {
        scenario_id: scenario
        for scenario_id, scenario in scenarios.items()
        if scenario.get("status") == "active"
        and scenario.get("proofLevel") in RUNTIME_PROOF_LEVELS
    }
    for path in paths:
        try:
            document = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as error:
            rejected.append({"manifest": _relative(path), "reason": str(error)})
            continue
        identity = document.get("identity") if isinstance(document, dict) else None
        scenario_id = identity.get("target") if isinstance(identity, dict) else None
        scenario = runtime_scenarios.get(scenario_id)
        if scenario is None:
            continue
        reason, current_attempt = _roadmap_run_manifest_rejection(
            document,
            scenario_id,
            scenario,
            runtime_fixture,
            source,
            emulator,
        )
        if reason is not None:
            rejection = {
                "manifest": _relative(path),
                "scenario": scenario_id,
                "reason": reason,
            }
            rejected.append(rejection)
            if current_attempt:
                failed_documents.append((rejection, document))
            continue
        runners = sorted({
            runner
            for command in scenario["adapter"].get("commands", [])
            if (runner := _runtime_runner_key(command)) is not None
        })
        accepted[scenario_id] = {
            "manifest": _relative(path),
            "runId": document["runId"],
            "proofLevel": document["proofLevel"],
            "runners": runners,
        }
        accepted_ids.setdefault(scenario_id, set()).add(document["runId"])
    if run_directory is None:
        shared, shared_invalid = shared_history(REPO, runtime_scenarios, source)
        rejected.extend({"manifest": item["path"], "reason": item["reason"]} for item in shared_invalid)
        for item in shared:
            if item["state"] == "recorded-pass":
                try:
                    document = json.loads((REPO / item["manifest"]).read_text())
                    test = json.loads((REPO / "tests/overworld/test-recipes" / (document["test"] + ".json")).read_text())
                    checked = finalize_shared_test(test, document, repo=REPO)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    checked = {"acceptedProof": False, "proofAcceptance": {"reason": str(error)}}
                if checked.get("acceptedProof") is True:
                    proof = checked["proofAcceptance"]
                    accepted[item["scenario"]] = {"manifest": item["manifest"], "runId": item["runId"],
                        "proofLevel": proof["proofLevel"], "runners": [], "execution": "shared-devtools",
                        "requirements": proof["requirements"], "claims": proof["claims"]}
                    continue
                rejection = {"manifest": item["manifest"], "scenario": item["scenario"],
                             "reason": checked.get("proofAcceptance", {}).get("reason", "shared proof replay rejected")}
                rejected.append(rejection); current_failures.append(rejection)
            elif item["state"] in ("failed", "unfinished") and item["currentInputs"]:
                rejection = {"manifest": item["manifest"], "scenario": item["scenario"],
                             "reason": "shared test is " + item["outcome"]}
                rejected.append(rejection); current_failures.append(rejection)
            else:
                rejected.append({"manifest": item["manifest"], "scenario": item["scenario"], "reason": item["state"]})
    resolved_failures = []
    for rejection, document in failed_documents:
        disposition = resolution_for(REPO, document, accepted_ids.get(rejection["scenario"], set()))
        if disposition is None:
            current_failures.append(rejection)
        else:
            resolved_failures.append({**rejection, "disposition": disposition})
    return {
        "acceptedScenarios": accepted,
        "rejectedRuns": rejected,
        "currentFailures": current_failures,
        "resolvedFailures": resolved_failures,
        "emulator": emulator,
    }


def _progress(args: argparse.Namespace) -> int:
    # Deliberately no doctor, fixture preflight, static check, or emulator probe.
    scenarios = load_scenarios(SCENARIO_DIRECTORY)
    result = summarize(REPO, scenarios, source_record(REPO))
    if args.json:
        _json(result)
    else:
        for item in result["scenarios"]:
            print(f"{item['state']:<14} {item['proofLevel']} {item['id']}")
        print(result["note"])
    return 0


def _scenario_recorded_status(args: argparse.Namespace) -> int:
    scenarios = load_scenarios(SCENARIO_DIRECTORY)
    if args.scenario_id not in scenarios:
        raise ValidationFailure("unknown scenario: " + args.scenario_id)
    result = summarize(REPO, scenarios, source_record(REPO))
    row = next(item for item in result["scenarios"] if item["id"] == args.scenario_id)
    response = {**row, "acceptance": result["acceptance"], "note": result["note"],
                "invalidReceipts": result["invalidReceipts"]}
    if args.json:
        _json(response)
    else:
        print(f"{row['state']} {row['id']}")
        for run in row["runs"]:
            print(f"{run['state']:<14} {run['runId']} {run['manifest']}")
        print(result["note"])
    return 0


def _runs_resolve(args: argparse.Namespace) -> int:
    _, scenarios = _load_contracts(audit_runtime_proof_sources=True)
    failed = read_manifest(args.failed if args.failed.is_absolute() else REPO / args.failed)
    replacement = read_manifest(args.replacement if args.replacement.is_absolute() else REPO / args.replacement)
    key = replacement["identity"].get("target")
    if key not in scenarios:
        raise ValidationFailure("replacement scenario is not in the current catalog")
    scenario = scenarios[key]
    fixture = _roadmap_runtime_fixture(Path(scenario["fixture"]["rom"]))
    if not fixture.get("passed"):
        raise ValidationFailure("replacement runtime fixture is not current")
    rejection, _ = _roadmap_run_manifest_rejection(
        replacement, key, scenario, fixture, source_record(REPO), emulator_record(REPO)
    )
    if rejection is not None:
        raise ValidationFailure(f"replacement proof rejected: {rejection}")
    with scenario_lock(REPO):
        result = record_resolution(REPO, failed, replacement, args.category,
                                   args.reason, args.reviewer, args.evidence)
    if args.json:
        _json(result)
    else:
        print(f"Recorded {args.category} review for {failed['runId']}; original failure retained.")
    return 0


def _roadmap_contract_audit(
    manifest: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
    static_results: list[dict[str, Any]],
    accepted_runtime_evidence: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Audit the complete roadmap proof catalog without running gameplay."""
    checks = {check["id"]: check for check in manifest["checks"]}
    capabilities = {
        capability["id"]: capability
        for capability in manifest["capabilities"]
    }
    migration = None
    superseded_scenarios = []
    if RUNTIME_PROOF_REGISTRY.get("executionMethod") == "shared-devtools":
        migration = validate_runtime_migration(json.loads((REPO /
            "tools/overworld/runtime_proof_migration.json").read_text()), RUNTIME_PROOF_REGISTRY)
        for scenario_id, scenario in scenarios.items():
            owners = [key for key, item in migration["requirements"].items() if scenario_id in item["scenarios"]]
            if not owners or not all(migration["requirements"][key]["status"] == "superseded" for key in owners):
                continue
            linked = {sid for cap in capabilities.values() if scenario_id in cap["scenarios"] for sid in cap["scenarios"]}
            if all(_exact_runtime_scenarios(dict(command=["python3", "scripts/owctl", "scenario", "run", key],
                    proofLevel=scenario["proofLevel"]), linked, scenarios, accepted_runtime_evidence,
                    migration=migration) for key in owners):
                superseded_scenarios.append(scenario_id)
        # Do not mutate the catalog or discard failed run records. This audit
        # omits only reviewed old obligations with complete current replacement proof.
        scenarios = {key: value for key, value in scenarios.items() if key not in superseded_scenarios}
    planned_scenarios = [
        {
            "id": scenario_id,
            "proofLevel": scenario["proofLevel"],
            "capabilities": list(scenario["capabilities"]),
        }
        for scenario_id, scenario in sorted(scenarios.items())
        if scenario["status"] == "planned"
    ]
    runtime_scenario_evidence = [
        {
            "id": scenario_id,
            "proofLevel": scenario["proofLevel"],
            "manifest": (
                accepted_runtime_evidence.get(scenario_id, {}).get("manifest")
            ),
            "passed": scenario_id in accepted_runtime_evidence,
        }
        for scenario_id, scenario in sorted(scenarios.items())
        if scenario["status"] == "active"
        and scenario["proofLevel"] in RUNTIME_PROOF_LEVELS
    ]
    runtime_scenario_evidence_gaps = [
        item for item in runtime_scenario_evidence if not item["passed"]
    ]

    check_capabilities: dict[str, set[str]] = {
        check_id: set() for check_id in checks
    }
    for capability in capabilities.values():
        for check_id in capability["checks"]:
            check_capabilities.setdefault(check_id, set()).add(capability["id"])

    runtime_check_coverage = []
    for check_id, check in sorted(checks.items()):
        if check["proofLevel"] not in RUNTIME_PROOF_LEVELS:
            continue
        capability_ids = check_capabilities.get(check_id, set())
        linked_scenario_ids = {
            scenario_id
            for capability_id in capability_ids
            for scenario_id in capabilities[capability_id]["scenarios"]
        }
        exact_scenarios = _exact_runtime_scenarios(
            check,
            linked_scenario_ids,
            scenarios,
            accepted_runtime_evidence,
            migration=migration,
        )
        runtime_check_coverage.append(
            {
                "id": check_id,
                "proofLevel": check["proofLevel"],
                "expectedRunner": _runtime_runner_key(check["command"]),
                "capabilities": sorted(capability_ids),
                "linkedScenarios": sorted(linked_scenario_ids),
                "exactScenarios": sorted(exact_scenarios),
                "passed": bool(exact_scenarios),
            }
        )
    runtime_check_coverage_gaps = [
        item for item in runtime_check_coverage if not item["passed"]
    ]

    capability_proof = []
    passed_static_checks = {
        result["id"]
        for result in static_results
        if result.get("passed") is True
    }
    for capability_id, capability in sorted(capabilities.items()):
        proof_sources: dict[str, list[str]] = {
            level: [] for level in PROOF_LEVELS
        }
        for check_id in capability["checks"]:
            check = checks[check_id]
            if (
                check["proofLevel"] not in RUNTIME_PROOF_LEVELS
                and check_id in passed_static_checks
            ):
                proof_sources[check["proofLevel"]].append("check." + check_id)
        for scenario_id in capability["scenarios"]:
            scenario = scenarios.get(scenario_id)
            if scenario is None or scenario["status"] != "active":
                continue
            if (
                scenario["proofLevel"] not in RUNTIME_PROOF_LEVELS
                or scenario_id not in accepted_runtime_evidence
                or scenario.get("verification", {}).get("kind") == "observer-control"
            ):
                continue
            proof_sources[scenario["proofLevel"]].append(
                "scenario." + scenario_id
            )
        available_levels = [
            level for level in PROOF_LEVELS if proof_sources[level]
        ]
        gaps = [
            level
            for level in capability["minimumProof"]
            if level not in available_levels
        ]
        capability_proof.append(
            {
                "id": capability_id,
                "minimumProof": list(capability["minimumProof"]),
                "availableProof": available_levels,
                "sources": {
                    level: proof_sources[level]
                    for level in available_levels
                },
                "gaps": gaps,
                "passed": not gaps,
            }
        )
    capability_proof_gaps = [
        item for item in capability_proof if not item["passed"]
    ]

    role_name = {
        "WILD": "Wild",
        "FOLLOWER": "Follower",
        "MOUNTED": "Mounted",
        "SCRIPTED": "Scripted",
    }
    capability_role_proof = []
    for capability_id, capability in sorted(capabilities.items()):
        for requirement in capability.get("roleProof", []):
            proof_level = requirement["proofLevel"]
            role_sources: dict[str, list[str]] = {
                role: [] for role in requirement["roles"]
            }
            for scenario_id in capability["scenarios"]:
                scenario = scenarios.get(scenario_id)
                if (
                    scenario is None
                    or scenario["status"] != "active"
                    or scenario["proofLevel"] != proof_level
                    or scenario_id not in accepted_runtime_evidence
                    or scenario.get("verification", {}).get("kind") == "observer-control"
                ):
                    continue
                observed_roles = {
                    role_name[subject["role"]]
                    for subject in scenario.get("subjects", [])
                    if subject.get("motionActor") is True
                    and subject.get("role") in role_name
                }
                observed_roles.update(
                    witness["role"]
                    for witness in scenario.get("roleProof", [])
                )
                for role in requirement["roles"]:
                    if role in observed_roles:
                        role_sources[role].append("scenario." + scenario_id)
            missing_roles = [
                role for role in requirement["roles"] if not role_sources[role]
            ]
            capability_role_proof.append(
                {
                    "id": capability_id,
                    "proofLevel": proof_level,
                    "requiredRoles": list(requirement["roles"]),
                    "sources": {
                        role: role_sources[role]
                        for role in requirement["roles"]
                        if role_sources[role]
                    },
                    "missingRoles": missing_roles,
                    "passed": not missing_roles,
                }
            )
    capability_role_proof_gaps = [
        item for item in capability_role_proof if not item["passed"]
    ]

    weak_actor_scoped_scenarios = []
    for scenario_id, scenario in sorted(scenarios.items()):
        if (
            scenario["status"] != "active"
            or scenario["proofLevel"] not in RUNTIME_PROOF_LEVELS
        ):
            continue
        trace_groups = {
            trace_group
            for capability_id in scenario["capabilities"]
            for trace_group in capabilities[capability_id]["traceGroups"]
        }
        if not trace_groups.intersection(ACTOR_SCOPED_TRACE_GROUPS):
            continue
        adapter = scenario.get("adapter")
        reasons = []
        if isinstance(adapter, dict) and adapter.get("kind") == "devtools-test":
            try:
                test = json.loads((REPO / "tests/overworld/test-recipes" / (adapter["test"] + ".json")).read_text())
                registered, _ = _shared_test_registration(test, REPO)
                declared = [{key: item[key] for key in ("id", "species", "role")} for item in scenario.get("subjects", [])]
                expected = [{key: item[key] for key in ("id", "species", "role")} for item in test["subjects"]]
                if (registered is None or registered["proofLevel"] != scenario["proofLevel"]
                        or registered["claims"] != adapter["claims"] or not declared or declared != expected
                        or any(item.get("minimum") != 1 or item.get("maximum") != 1
                               or item.get("requirePresentation") is not True for item in scenario["subjects"])):
                    reasons.append("shared test lacks the exact registered live-subject contract")
            except (OSError, ValueError, KeyError, TypeError, ValidationFailure) as error:
                reasons.append("shared actor test registration is invalid: " + str(error))
        elif not isinstance(adapter, dict) or adapter.get("kind") != "actor-observation":
            reasons.append("adapter is not actor-observation")
        if not scenario.get("subjects"):
            reasons.append("structured subjects are missing")
        if reasons:
            weak_actor_scoped_scenarios.append(
                {
                    "id": scenario_id,
                    "proofLevel": scenario["proofLevel"],
                    "capabilities": list(scenario["capabilities"]),
                    "traceGroups": sorted(trace_groups),
                    "reasons": reasons,
                }
            )

    return {
        "runtimeMigration": _runtime_migration_summary(),
        "supersededScenarios": sorted(superseded_scenarios),
        "staticCheckResults": static_results,
        "verificationSetupGaps": [
            {"id": key, "reason": "collector setup mutation audit is pending"}
            for key, scenario in sorted(scenarios.items())
            if scenario["status"] == "active"
            and scenario.get("verification", {}).get("setupAudit") == "pending"
        ],
        "staticCheckGaps": [
            result for result in static_results if result.get("passed") is not True
        ],
        "plannedScenarios": planned_scenarios,
        "runtimeScenarioEvidence": runtime_scenario_evidence,
        "runtimeScenarioEvidenceGaps": runtime_scenario_evidence_gaps,
        "runtimeCheckCoverage": runtime_check_coverage,
        "runtimeCheckCoverageGaps": runtime_check_coverage_gaps,
        "capabilityProof": capability_proof,
        "capabilityProofGaps": capability_proof_gaps,
        "capabilityRoleProof": capability_role_proof,
        "capabilityRoleProofGaps": capability_role_proof_gaps,
        "weakActorScopedScenarios": weak_actor_scoped_scenarios,
    }


def _valid_runtime_fixture_file(record: Any) -> bool:
    return (
        isinstance(record, dict)
        and record.get("present") is True
        and isinstance(record.get("size"), int)
        and not isinstance(record.get("size"), bool)
        and record["size"] > 0
        and isinstance(record.get("sha256"), str)
        and len(record["sha256"]) == 64
        and all(character in "0123456789abcdef" for character in record["sha256"])
    )


def _actor_evidence_session(steps: list[dict[str, Any]]) -> str:
    sessions = {
        execution.get("session")
        for step in steps
        if isinstance(step, dict)
        for execution in [step.get("proofExecution")]
        if isinstance(execution, dict)
    }
    if (
        len(sessions) != 1
        or not isinstance(next(iter(sessions), None), str)
    ):
        raise ValidationFailure(
            "actor evidence needs one controller-issued runtime session"
        )
    return next(iter(sessions))


def _roadmap_runtime_fixture(rom: Path) -> dict[str, Any]:
    command = _expand_command([
        "{python}",
        "scripts/verify_overworld_runtime_fixture.py",
        "--rom",
        str(rom),
        "--json",
    ])
    completed = subprocess.run(
        command,
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        return {
            "command": command,
            "passed": False,
            "returnCode": completed.returncode,
            "error": f"runtime fixture output is not JSON: {error}",
            "stderrTail": (completed.stderr or "")[-2000:],
        }
    checks = payload.get("checks") if isinstance(payload, dict) else None
    check_by_name = {
        item.get("name"): item
        for item in checks
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(checks, list) else {}
    descriptor_check = check_by_name.get("debug-descriptor-overlay", {})
    product_check = check_by_name.get("overworld-product-outputs", {})
    linked_check = check_by_name.get("runtime-linked-symbol-inputs", {})
    product_outputs = product_check.get("outputs")
    required_product_outputs = {
        key: (overlay_id, identity_name)
        for key, identity_name, overlay_id, _path in OVERWORLD_PRODUCT_OUTPUTS
    }
    product_contract_valid = (
        isinstance(product_outputs, dict)
        and set(product_outputs) == set(required_product_outputs)
        and all(
            isinstance(product_outputs.get(key), dict)
            and product_outputs[key].get("overlayId") == overlay_id
            and product_outputs[key].get("matched") is True
            and _valid_runtime_fixture_file(product_outputs[key].get("output"))
            and _valid_runtime_fixture_file(product_outputs[key].get("packaged"))
            for key, (overlay_id, _identity_name) in required_product_outputs.items()
        )
    )
    linked_outputs = linked_check.get("outputs")
    required_linked_outputs = {
        identity_name: path.as_posix()
        for identity_name, path in OVERWORLD_LINKED_OUTPUTS
    }
    linked_contract_valid = (
        isinstance(linked_outputs, dict)
        and set(required_linked_outputs).issubset(linked_outputs)
        and all(
            isinstance(linked_outputs.get(name), dict)
            and linked_outputs[name].get("matched") is True
            and _valid_runtime_fixture_file(linked_outputs[name].get("output"))
            and linked_outputs[name]["output"].get("path") == path
            for name, path in required_linked_outputs.items()
        )
        and all(
            isinstance(record, dict)
            and record.get("matched") is True
            and _valid_runtime_fixture_file(record.get("output"))
            for record in linked_outputs.values()
        )
    )
    identity = {
        "rom": payload.get("rom") if isinstance(payload, dict) else None,
        "buildManifest": (
            payload.get("buildManifest") if isinstance(payload, dict) else None
        ),
        "debugDescriptor": descriptor_check.get("descriptor"),
    }
    if isinstance(product_outputs, dict):
        identity.update({
            identity_name: product_outputs.get(key, {}).get("output")
            for key, (_overlay_id, identity_name) in required_product_outputs.items()
            if isinstance(product_outputs.get(key), dict)
        })
    if isinstance(linked_outputs, dict):
        identity.update({
            name: linked_outputs.get(name, {}).get("output")
            for name in required_linked_outputs
            if isinstance(linked_outputs.get(name), dict)
        })
    required_checks = (
        "make-target-current",
        "sealed-build-manifest",
        "packaged-actor-system",
        "packaged-mount-system",
        "overworld-product-outputs",
        "runtime-linked-symbol-inputs",
        "debug-descriptor-overlay",
        "stock-main-queue-observation",
        "shared-devtools-isolated-startup",
    )
    passed = (
        completed.returncode == 0
        and isinstance(payload, dict)
        and payload.get("schemaVersion") == 1
        and payload.get("passed") is True
        and product_contract_valid
        and linked_contract_valid
        and identity.get("actorOverlay") == descriptor_check.get("overlay")
        and all(
            isinstance(check_by_name.get(name), dict)
            and check_by_name[name].get("passed") is True
            for name in required_checks
        )
        and all(_valid_runtime_fixture_file(record) for record in identity.values())
    )
    result = {
        "command": command,
        "passed": passed,
        "returnCode": completed.returncode,
        "identity": identity,
        "checks": [
            {
                "name": name,
                "passed": (
                    check_by_name.get(name, {}).get("passed") is True
                ),
            }
            for name in required_checks
        ],
    }
    if not passed:
        result["error"] = "runtime fixture identity is missing, stale, or inconsistent"
        result["stderrTail"] = (completed.stderr or "")[-2000:]
    return result


def _verify_roadmap(args: argparse.Namespace) -> int:
    manifest, scenarios = _load_contracts(audit_runtime_proof_sources=True)
    runtime_fixture = _roadmap_runtime_fixture(args.rom)
    static_results = _roadmap_static_results(manifest)
    runtime_evidence = _roadmap_runtime_evidence(scenarios, runtime_fixture)
    result = {
        "schemaVersion": 1,
        **_roadmap_contract_audit(
            manifest,
            scenarios,
            static_results,
            runtime_evidence["acceptedScenarios"],
        ),
        "runtimeEvidence": runtime_evidence,
        "runtimeFixture": runtime_fixture,
    }
    result["passed"] = (
        result["runtimeMigration"]["complete"]
        and
        not result["plannedScenarios"]
        and not result["verificationSetupGaps"]
        and not result["staticCheckGaps"]
        and not result["runtimeScenarioEvidenceGaps"]
        and not result["runtimeEvidence"]["currentFailures"]
        and not result["runtimeCheckCoverageGaps"]
        and not result["capabilityProofGaps"]
        and not result["capabilityRoleProofGaps"]
        and not result["weakActorScopedScenarios"]
        and result["runtimeFixture"]["passed"]
    )
    if args.json:
        _json(result)
    else:
        print("PASS" if result["passed"] else "FAIL", "roadmap verification")
        print(f"runtime requirements awaiting shared tests: {result['runtimeMigration']['pendingCount']}")
        print(f"planned scenarios: {len(result['plannedScenarios'])}")
        print(f"setup audit gaps: {len(result['verificationSetupGaps'])}")
        print(f"static check gaps: {len(result['staticCheckGaps'])}")
        print(
            "runtime scenario evidence gaps: "
            f"{len(result['runtimeScenarioEvidenceGaps'])}"
        )
        print(
            "current runtime failures: "
            f"{len(result['runtimeEvidence']['currentFailures'])}"
        )
        print(
            "runtime coverage gaps: "
            f"{len(result['runtimeCheckCoverageGaps'])}"
        )
        print(
            "capability proof gaps: "
            f"{len(result['capabilityProofGaps'])}"
        )
        print(
            "capability role proof gaps: "
            f"{len(result['capabilityRoleProofGaps'])}"
        )
        print(
            "weak actor-scoped scenarios: "
            f"{len(result['weakActorScopedScenarios'])}"
        )
        print(
            "runtime fixture: "
            + ("current" if result["runtimeFixture"]["passed"] else "invalid")
        )
    return 0 if result["passed"] else 1


def _requirement_state(requirement: str) -> tuple[bool, str]:
    paths = {
        "rom": REPO / "test.nds",
        "dsv": REPO / "test.dsv",
        "sav": REPO / "test.sav",
        "debugDescriptor": REPO / "build/overworld-system.debug.json",
    }
    if requirement == "source":
        return True, "source"
    if requirement == "build":
        required = (
            REPO / "build/overworld_mount_overlay_linked.o",
            REPO / "build/overworld_wild_spawns_overlay_linked.o",
            REPO / "build/overworld_wild_runtime_overlay_linked.o",
            REPO / "build/pokemon_move_history_task6_overlay_linked.o",
        )
        missing = [_relative(path) for path in required if not path.is_file()]
        return not missing, "linked objects" if not missing else ", ".join(missing)
    if requirement == "emulator":
        emulator = emulator_record(REPO)
        return emulator["present"], (
            f"{emulator['pythonExecutable']}: {emulator['detail']}"
        )
    path = paths[requirement]
    return path.is_file(), _relative(path)


def _verify_affected(args: argparse.Namespace) -> int:
    manifest, scenarios = _load_contracts()
    paths = sorted(set(args.path or _git_changed_paths(args.base)))
    if not paths:
        raise ValidationFailure("no affected paths; pass --path or --base")
    check_by_id = {check["id"]: check for check in manifest["checks"]}
    selected_ids: set[str] = set()
    selected_scenario_ids: set[str] = set()
    runtime_check_coverage: dict[str, set[str]] = {}
    capability_hits = []
    for capability in manifest["capabilities"]:
        matched = [
            path for path in paths if _matches(path, capability["sourcePatterns"])
        ]
        if matched:
            capability_hits.append({"id": capability["id"], "paths": matched})
            selected_ids.update(capability["checks"])
            active_runtime_scenarios = {
                scenario_id
                for scenario_id in capability["scenarios"]
                if scenario_id in scenarios
                and scenarios[scenario_id]["status"] == "active"
                and scenarios[scenario_id]["proofLevel"] in ("S3", "S4", "S5")
                and scenarios[scenario_id].get("adapter") is not None
                and scenarios[scenario_id]["adapter"].get("commands")
            }
            selected_scenario_ids.update(active_runtime_scenarios)
            for check_id in capability["checks"]:
                check = check_by_id[check_id]
                if check["proofLevel"] in ("S3", "S4", "S5"):
                    runtime_check_coverage.setdefault(check_id, set()).update(
                        _exact_runtime_scenarios(
                            check,
                            set(capability["scenarios"]),
                            scenarios,
                        )
                    )
    for check in manifest["checks"]:
        if any(_matches(path, check["sourcePatterns"]) for path in paths):
            selected_ids.add(check["id"])
    if any(
        path == "scripts/verify_overworld_walk_runtime.py"
        or path == "tools/overworld/runtime_proof_registry.json"
        for path in paths
    ):
        selected_scenario_ids.update(
            scenario_id
            for scenario_id, scenario in scenarios.items()
            if scenario["status"] == "active"
            and scenario["proofLevel"] in ("S3", "S4", "S5")
            and scenario.get("adapter") is not None
            and scenario["adapter"].get("commands")
        )
    if not selected_ids:
        raise ValidationFailure(
            "affected paths have no feature-map owner: " + ", ".join(paths)
        )
    if selected_scenario_ids or any(
        check_by_id[check_id]["proofLevel"] in ("S3", "S4", "S5")
        for check_id in selected_ids
    ):
        selected_ids.add("host.proof-gate")
    selected = sorted(
        (check_by_id[check_id] for check_id in selected_ids),
        key=lambda check: (
            check["costTier"],
            PROOF_LEVELS.index(check["proofLevel"]),
            check["id"],
        ),
    )
    uncovered_runtime_checks = [
        check["id"]
        for check in selected
        if check["proofLevel"] in ("S3", "S4", "S5")
        and not runtime_check_coverage.get(check["id"])
    ]
    if uncovered_runtime_checks:
        raise ValidationFailure(
            "runtime checks need a claim-bearing scenario before affected "
            "verification can run: " + ", ".join(uncovered_runtime_checks)
        )
    plan = []
    for check in selected:
        if check["proofLevel"] in ("S3", "S4", "S5"):
            continue
        requirements = []
        ready = True
        for requirement in check["requires"]:
            present, detail = _requirement_state(requirement)
            requirements.append(
                {"name": requirement, "present": present, "detail": detail}
            )
            ready &= present
        plan.append(
            {
                "id": check["id"],
                "title": check["title"],
                "proofLevel": check["proofLevel"],
                "costTier": check["costTier"],
                "command": _expand_command(check["command"]),
                "requirements": requirements,
                "ready": ready,
                "resultKind": "exit-zero",
                "kind": "check",
            }
        )
    for scenario_id in sorted(
        selected_scenario_ids,
        key=lambda value: (
            scenarios[value]["costTier"],
            PROOF_LEVELS.index(scenarios[value]["proofLevel"]),
            value,
        ),
    ):
        scenario = scenarios[scenario_id]
        requirements = []
        ready = True
        required_inputs = ["emulator", "rom"]
        save = scenario["fixture"].get("save")
        if isinstance(save, dict):
            required_inputs.append(save["kind"])
        if scenario["adapter"]["kind"] == "actor-observation":
            required_inputs.append("debugDescriptor")
        for requirement in dict.fromkeys(required_inputs):
            present, detail = _requirement_state(requirement)
            requirements.append(
                {"name": requirement, "present": present, "detail": detail}
            )
            ready &= present
        plan.append(
            {
                "id": "scenario." + scenario_id,
                "title": scenario["title"],
                "proofLevel": scenario["proofLevel"],
                "costTier": scenario["costTier"],
                "command": _expand_command([
                    "{python}",
                    "scripts/owctl",
                    "scenario",
                    "run",
                    scenario_id,
                    "--json",
                ]),
                "requirements": requirements,
                "ready": ready,
                "resultKind": "json-passed",
                "kind": "scenario",
            }
        )

    if not args.run:
        result = {
            "schemaVersion": 1,
            "executed": False,
            "paths": paths,
            "capabilities": capability_hits,
            "checks": plan,
        }
        if args.json:
            _json(result)
        else:
            print("DRY RUN: cheapest checks are listed first")
            for check in plan:
                state = "READY" if check["ready"] else "MISSING INPUT"
                print(
                    f"C{check['costTier']} {check['proofLevel']} {state:<13} {check['id']}"
                )
                print("  " + " ".join(check["command"]))
            print("Use --run to execute this exact plan.")
        return 0

    not_ready = [check for check in plan if not check["ready"]]
    ready_plan = [check for check in plan if check["ready"]]
    started_at = utc_now()
    artifacts = artifact_directory(REPO)
    results = []
    commands = [check["command"] for check in plan]
    for check in ready_plan:
        result = _run_command(check["command"], check["resultKind"],
                              log_directory=artifacts, log_index=len(results))
        result["checkId"] = check["id"]
        results.append(result)
        if not result["passed"]:
            break
    for check in not_ready:
        results.append(
            {
                "checkId": check["id"],
                "passed": False,
                "skipped": True,
                "missingRequirements": [
                    item["name"]
                    for item in check["requirements"]
                    if not item["present"]
                ],
            }
        )
    highest_proof = max(
        (check["proofLevel"] for check in selected),
        key=PROOF_LEVELS.index,
    )
    document = make_run_manifest(
        repo=REPO,
        kind="affected-verification",
        target="affected-" + hashlib.sha256("\n".join(paths).encode()).hexdigest()[:12],
        proof_level=highest_proof,
        cost_tier=max(check["costTier"] for check in selected),
        scenario=None,
        commands=commands,
        results=results,
        started_at=started_at,
    )
    output = write_run_manifest(document, REPO, args.manifest_output)
    response = {
        "passed": document["result"]["passed"],
        "runId": document["runId"],
        "manifest": _relative(output),
        "steps": results,
        "skipped": [
            {
                "checkId": check["id"],
                "missingRequirements": [
                    item["name"]
                    for item in check["requirements"]
                    if not item["present"]
                ],
            }
            for check in not_ready
        ],
    }
    if args.json:
        _json(response)
    else:
        print("PASS" if response["passed"] else "FAIL", "affected verification")
        print(f"manifest: {_relative(output)}")
        if not_ready:
            detail = "; ".join(
                f"{check['id']}: "
                + ", ".join(
                    item["name"]
                    for item in check["requirements"]
                    if not item["present"]
                )
                for check in not_ready
            )
            print("SKIPPED missing inputs: " + detail)
    return 0 if response["passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/owctl",
        description="Inspect and verify the overworld actor system.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    from tools.overworld.devtools_cli import register as register_devtools
    register_devtools(commands)

    progress = commands.add_parser("progress", help="Read recorded progress without running proof")
    progress.add_argument("--json", action="store_true")
    progress.set_defaults(handler=_progress)

    runs = commands.add_parser("runs", help="Review run failures without erasing evidence")
    run_commands = runs.add_subparsers(dest="runs_command", required=True)
    resolve = run_commands.add_parser("resolve", help="Record an evidenced non-product failure review")
    resolve.add_argument("failed", type=Path)
    resolve.add_argument("--category", choices=("setup", "harness", "host"), required=True)
    resolve.add_argument("--reason", required=True)
    resolve.add_argument("--reviewer", required=True)
    resolve.add_argument("--evidence", type=Path, required=True)
    resolve.add_argument("--replacement", type=Path, required=True)
    resolve.add_argument("--json", action="store_true")
    resolve.set_defaults(handler=_runs_resolve)

    doctor = commands.add_parser("doctor", help="Check host-control readiness")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=_doctor)

    scenario = commands.add_parser("scenario", help="List, validate, or run scenarios")
    scenario_commands = scenario.add_subparsers(dest="scenario_command", required=True)
    scenario_list = scenario_commands.add_parser("list")
    scenario_list.add_argument("--json", action="store_true")
    scenario_list.set_defaults(handler=_scenario_list)
    for name in ("status", "history"):
        recorded = scenario_commands.add_parser(name, help="Read all recorded scenario attempts without running proof")
        recorded.add_argument("scenario_id")
        recorded.add_argument("--json", action="store_true")
        recorded.set_defaults(handler=_scenario_recorded_status)
    scenario_validate = scenario_commands.add_parser("validate")
    scenario_validate.add_argument("scenario_ids", nargs="*")
    scenario_validate.add_argument("--json", action="store_true")
    scenario_validate.set_defaults(handler=_scenario_validate)
    scenario_recheck = scenario_commands.add_parser("recheck", help="Recheck one saved run; no emulator or artifact rewrite")
    scenario_recheck.add_argument("run_id")
    scenario_recheck.add_argument("--json", action="store_true")
    scenario_recheck.set_defaults(handler=_scenario_recheck)
    scenario_run = scenario_commands.add_parser("run")
    scenario_run.add_argument("scenario_id")
    scenario_run.add_argument("--dry-run", action="store_true")
    scenario_run.add_argument("--evidence", type=Path)
    scenario_run.add_argument("--json", action="store_true")
    scenario_run.add_argument("--manifest-output", type=Path)
    scenario_run.add_argument("--url", default="http://127.0.0.1:8766", help="Shared Workshop service URL")
    scenario_run.set_defaults(handler=_scenario_run)

    trace = commands.add_parser("trace", help="Decode a semantic trace")
    trace_commands = trace.add_subparsers(dest="trace_command", required=True)
    trace_decode = trace_commands.add_parser("decode")
    trace_decode.add_argument("trace", type=Path)
    trace_decode.add_argument("--schema", type=Path, default=TRACE_SCHEMA)
    trace_decode.add_argument("--actor", type=lambda value: int(value, 0))
    trace_decode.add_argument("--event")
    trace_decode.add_argument("--json", action="store_true")
    trace_decode.set_defaults(handler=_trace_decode)

    actor = commands.add_parser("actor", help="Inspect public actor observation")
    actor_commands = actor.add_subparsers(dest="actor_command", required=True)
    actor_inspect = actor_commands.add_parser("inspect", help="Inspect actor snapshots")
    _add_actor_source_arguments(actor_inspect)
    actor_inspect.add_argument("--index", type=int)
    actor_inspect.add_argument("--json", action="store_true")
    actor_inspect.set_defaults(handler=_actor_inspect)
    actor_trace = actor_commands.add_parser("trace", help="Inspect actor semantic trace")
    _add_actor_source_arguments(actor_trace)
    actor_trace.add_argument("--actor", type=lambda value: int(value, 0))
    actor_trace.add_argument("--event")
    actor_trace.add_argument("--json", action="store_true")
    actor_trace.set_defaults(handler=_actor_trace)
    actor_capture = actor_commands.add_parser(
        "capture", help="Create reusable actor observation evidence"
    )
    _add_actor_source_arguments(actor_capture)
    actor_capture.add_argument("--scenario-id")
    actor_capture.add_argument("--rom", type=Path)
    actor_capture.add_argument("--save", type=Path)
    actor_capture.add_argument("--seed", type=lambda value: int(value, 0))
    actor_capture.add_argument(
        "--execution",
        type=Path,
        help="Completed input execution record produced by the scenario runner",
    )
    actor_capture.add_argument("--output", type=Path)
    actor_capture.set_defaults(handler=_actor_capture)

    verify = commands.add_parser("verify", help="Select proof from the feature map")
    verify_commands = verify.add_subparsers(dest="verify_command", required=True)
    affected = verify_commands.add_parser("affected")
    affected.add_argument("--base")
    affected.add_argument("--path", action="append")
    affected.add_argument("--run", action="store_true")
    affected.add_argument("--json", action="store_true")
    affected.add_argument("--manifest-output", type=Path)
    affected.set_defaults(handler=_verify_affected)
    roadmap = verify_commands.add_parser(
        "roadmap",
        help="Fail closed on incomplete roadmap proof and stale runtime identity",
    )
    roadmap.add_argument("--rom", type=Path, default=Path("test.nds"))
    roadmap.add_argument("--json", action="store_true")
    roadmap.set_defaults(handler=_verify_roadmap)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ValidationFailure as error:
        print(f"owctl: {error}", file=sys.stderr)
        return 2
    except FileNotFoundError as error:
        print(f"owctl: missing file: {error.filename}", file=sys.stderr)
        return 2
