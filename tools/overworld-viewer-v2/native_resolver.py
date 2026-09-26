"""Build and call the portable overworld behavior resolver.

This module is an adapter only. Resolution stays in the same C source that the
Nintendo DS runtime can link, so Workshop tools do not grow a second policy
implementation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Mapping


_BUILD_LOCK = threading.Lock()
REQUEST_VERSION = 2


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _stage_native_sources(
    root: Path,
    generated_root: Path,
    relative_paths: tuple[str, ...],
) -> tuple[Path, ...]:
    """Copy native sources so their relative includes use generated headers."""

    staged: list[Path] = []
    for relative_path in relative_paths:
        source = root / relative_path
        destination = generated_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        staged.append(destination)
    return tuple(staged)


def _sources(
    root: Path,
    catalog: Path,
    source_template: Path,
    header_template: Path,
) -> tuple[Path, ...]:
    return (
        root / "lib/overworld/overworld_behavior_resolver.c",
        root
        / "tools/overworld-viewer-v2/native/overworld_behavior_resolver_main.c",
        catalog,
        source_template,
        header_template,
        root / "scripts/generate_overworld_behavior_catalog.py",
        root / "scripts/overworld_behavior_profile_viewer.py",
        root / "scripts/build_overworld_wild_spawn_metadata.py",
        root / "tools/overworld/behavior_schema.json",
        root / "data/generated/overworld_wild_roof_catalog.inc",
        root / "include/config.h",
        root / "include/constants/species.h",
        root / "include/constants/buttons.h",
        root / "include/debug.h",
        root / "include/io_reg.h",
        root / "include/types.h",
        root / "include/overworld_behavior_resolver.h",
        root
        / "include/constants/generated/overworld_wild_roof_catalog_counts.h",
        Path(__file__).resolve(),
    )


def build(
    root: Path | None = None,
    *,
    force: bool = False,
    catalog: Path | None = None,
    source_template: Path | None = None,
    header_template: Path | None = None,
    output: Path | None = None,
) -> Path:
    """Return a current host executable, compiling it when required."""

    root = (root or _repo_root()).resolve()
    catalog = (catalog or root / "data/overworld_behavior_profiles.json").resolve()
    source_template = (
        source_template or root / "data/OverworldWildBehaviorData.c"
    ).resolve()
    header_template = (
        header_template or root / "include/overworld_wild_behavior_data.h"
    ).resolve()
    output = (output or root / "build/overworld_behavior_resolver_host").resolve()
    sources = _sources(root, catalog, source_template, header_template)
    missing = [source for source in sources if not source.is_file()]
    if missing:
        names = ", ".join(str(path.relative_to(root)) for path in missing)
        raise FileNotFoundError(f"resolver source is missing: {names}")

    with _BUILD_LOCK:
        current = output.is_file() and all(
            output.stat().st_mtime_ns >= source.stat().st_mtime_ns
            for source in sources
        )
        if current and not force:
            return output

        compiler_setting = os.environ.get("CC")
        compiler = shlex.split(compiler_setting) if compiler_setting else []
        if not compiler:
            default_compiler = shutil.which("cc")
            compiler = [default_compiler] if default_compiler else []
        if not compiler:
            raise RuntimeError("a host C compiler is required (set CC or install cc)")
        output.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.",
            dir=output.parent,
        )
        os.close(file_descriptor)
        temporary = Path(temporary_name)
        try:
            with tempfile.TemporaryDirectory(
                prefix=f".{output.name}.catalog.",
                dir=output.parent,
            ) as generated_name:
                generated_root = Path(generated_name)
                generated_source = generated_root / "data/OverworldWildBehaviorData.c"
                generated_header = generated_root / "include/overworld_wild_behavior_data.h"
                generate_command = [
                    sys.executable,
                    str(root / "scripts/generate_overworld_behavior_catalog.py"),
                    "--catalog",
                    str(catalog),
                    "--source-template",
                    str(source_template),
                    "--header-template",
                    str(header_template),
                    "--source-output",
                    str(generated_source),
                    "--header-output",
                    str(generated_header),
                ]
                generated = subprocess.run(
                    generate_command,
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if generated.returncode != 0:
                    detail = generated.stderr.strip() or generated.stdout.strip()
                    raise RuntimeError(f"could not generate resolver input: {detail}")
                staged_resolver, staged_main, _staged_header = _stage_native_sources(
                    root,
                    generated_root,
                    (
                        "lib/overworld/overworld_behavior_resolver.c",
                        "tools/overworld-viewer-v2/native/overworld_behavior_resolver_main.c",
                        "include/overworld_behavior_resolver.h",
                    ),
                )
                command = compiler + [
                    "-std=c99",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-DOVERWORLD_BEHAVIOR_HOST",
                    "-I",
                    str(generated_root / "include"),
                    "-I",
                    str(root / "include"),
                    "-I",
                    str(root / "data"),
                    str(staged_resolver),
                    str(staged_main),
                    str(generated_source),
                    "-o",
                    str(temporary),
                ]
                completed = subprocess.run(
                    command,
                    cwd=root,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if completed.returncode != 0:
                    detail = completed.stderr.strip() or completed.stdout.strip()
                    raise RuntimeError(f"could not compile resolver host: {detail}")
            temporary.chmod(0o755)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)
    return output


def build_condition_preview(
    root: Path | None = None,
    *,
    catalog: Path | None = None,
    source_template: Path | None = None,
    header_template: Path | None = None,
    output: Path | None = None,
) -> Path:
    """Build the shared condition-evaluator plus resolver preview host."""

    root = (root or _repo_root()).resolve()
    catalog = (catalog or root / "data/overworld_behavior_profiles.json").resolve()
    source_template = (source_template or root / "data/OverworldWildBehaviorData.c").resolve()
    header_template = (header_template or root / "include/overworld_wild_behavior_data.h").resolve()
    output = (output or root / "build/overworld_behavior_condition_preview_host").resolve()
    compiler_setting = os.environ.get("CC")
    compiler = shlex.split(compiler_setting) if compiler_setting else []
    if not compiler:
        default_compiler = shutil.which("cc")
        compiler = [default_compiler] if default_compiler else []
    if not compiler:
        raise RuntimeError("a host C compiler is required (set CC or install cc)")
    output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        dir=output.parent,
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        with tempfile.TemporaryDirectory(
            prefix=f".{output.name}.catalog.",
            dir=output.parent,
        ) as generated_name:
            generated_root = Path(generated_name)
            generated_source = generated_root / "data/OverworldWildBehaviorData.c"
            generated_header = generated_root / "include/overworld_wild_behavior_data.h"
            generate_command = [
                sys.executable,
                str(root / "scripts/generate_overworld_behavior_catalog.py"),
                "--catalog", str(catalog),
                "--source-template", str(source_template),
                "--header-template", str(header_template),
                "--source-output", str(generated_source),
                "--header-output", str(generated_header),
            ]
            generated = subprocess.run(
                generate_command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            if generated.returncode != 0:
                detail = generated.stderr.strip() or generated.stdout.strip()
                raise RuntimeError(f"could not generate condition preview input: {detail}")
            (
                staged_conditions,
                staged_runtime,
                staged_resolver,
                staged_vision,
                staged_main,
                _staged_actor_header,
                _staged_conditions_header,
                _staged_runtime_header,
                _staged_resolver_header,
                _staged_vision_header,
            ) = _stage_native_sources(
                root,
                generated_root,
                (
                    "lib/overworld/overworld_behavior_conditions.c",
                    "lib/overworld/overworld_behavior_condition_runtime.c",
                    "lib/overworld/overworld_behavior_resolver.c",
                    "lib/overworld/overworld_vision.c",
                    "tools/overworld-viewer-v2/native/overworld_behavior_condition_preview_main.c",
                    "include/overworld_actor_system.h",
                    "include/overworld_behavior_conditions.h",
                    "include/overworld_behavior_condition_runtime.h",
                    "include/overworld_behavior_resolver.h",
                    "include/overworld_vision.h",
                ),
            )
            command = compiler + [
                "-std=c99", "-O2", "-Wall", "-Wextra",
                "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                "-I", str(generated_root / "include"),
                "-I", str(root / "include"),
                "-I", str(root / "data"),
                str(staged_conditions),
                str(staged_runtime),
                str(staged_resolver),
                str(staged_vision),
                str(staged_main),
                str(generated_source),
                "-o", str(temporary),
            ]
            completed = subprocess.run(
                command,
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(f"could not compile condition preview host: {detail}")
        temporary.chmod(0o755)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def preview_conditions(
    request: Mapping[str, Any],
    *,
    root: Path | None = None,
    executable: Path | None = None,
) -> dict[str, Any]:
    """Evaluate prepared conditions and resolve their explicit result."""

    root = (root or _repo_root()).resolve()
    executable = executable or build_condition_preview(root)
    subject = request["subject"]
    observation = request["observation"]
    subject_handle = subject["handle"]
    candidates = request.get("candidates", [])
    states = request.get("conditionState", [])
    player = observation["player"]
    header = (
        subject["species"], subject["level"], subject["terrain"], subject["shiny"],
        subject["groupFlags"], subject["behaviorClass"], observation["terrainMask"],
        subject_handle["slot"], subject_handle["generation"], subject_handle["fieldEpoch"],
        subject_handle["mapGeneration"], subject_handle["encounterGeneration"],
        observation["frame"], observation["x"], observation["y"],
        player["x"], player["y"], player["valid"], observation["facing"],
        observation["movementSpeed"], request.get("chanceSeed", observation["frame"]),
        player["facingAndOcclusion"], len(candidates), len(states),
    )
    lines = [" ".join(str(int(value)) for value in header)]
    for candidate in candidates:
        handle = candidate["handle"]
        lines.append(" ".join(str(int(value)) for value in (
            candidate["species"], candidate["level"], candidate["terrain"], candidate["shiny"],
            candidate["groupFlags"], candidate["behaviorClass"], candidate["roleMask"],
            handle["slot"], handle["generation"], handle["fieldEpoch"],
            handle["mapGeneration"], handle["encounterGeneration"],
            candidate["x"], candidate["y"], candidate["valid"],
            candidate["facingAndOcclusion"],
        )))
    for state in states:
        lines.append(" ".join(str(int(value)) for value in (
            state["conditionId"], state["active"], state["hasTriggered"],
            state["activeUntil"], state["cooldownUntil"],
            state["targetKind"], state.get("targetCandidateIndex", -1),
        )))
    completed = subprocess.run(
        [str(executable)],
        cwd=root,
        input="\n".join(lines) + "\n",
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"condition preview host failed: {detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("condition preview host returned invalid JSON") from error
    if not isinstance(result, dict):
        raise RuntimeError("condition preview host did not return a JSON object")
    return result


def _condition_request_values(request: Mapping[str, Any]) -> tuple[int, ...]:
    for removed in ("conditionInputMode", "conditionTerrain" + "Mask"):
        if removed in request:
            raise ValueError(
                f"native resolver {removed} was removed; use requestVersion 2"
            )
    request_version = request.get("requestVersion", REQUEST_VERSION)
    try:
        request_version = int(request_version)
    except (TypeError, ValueError) as error:
        raise ValueError("native resolver requestVersion must be an integer") from error
    if request_version != REQUEST_VERSION:
        raise ValueError(
            f"unsupported native resolver requestVersion {request_version}; "
            f"expected {REQUEST_VERSION}"
        )
    target = request.get("resolvedTarget") or {}
    if not isinstance(target, Mapping):
        raise ValueError("resolvedTarget must be an object")
    kind = target.get("kind", "none")
    if isinstance(kind, str):
        try:
            kind = {"none": 0, "player": 1, "actor": 2}[kind]
        except KeyError as error:
            raise ValueError(f"unknown resolved target kind: {kind}") from error
    values = (
        request.get("activeConditionalMask", 0),
        request_version,
        kind,
        target.get("actorSlot", 0),
        target.get("actorGeneration", 0),
        target.get("fieldEpoch", 0),
        target.get("mapGeneration", 0),
        target.get("encounterGeneration", 0),
        target.get("actorReserved", 0),
        request.get("winningConditionId", 0xFFFF),
        request.get("targetSourceApplication", 0xFF),
        request.get("resolvedTargetConditionId", 0xFFFF),
    )
    try:
        return tuple(int(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError("native condition request values must be integers") from error


def resolve(
    blob: Path | None,
    request: Mapping[str, Any],
    *,
    root: Path | None = None,
    executable: Path | None = None,
) -> dict[str, Any]:
    """Resolve one request through the native portable C implementation."""

    root = (root or _repo_root()).resolve()
    executable = executable or build(root)
    behavior_class = request.get("behaviorClass", "auto")
    condition_values = _condition_request_values(request)
    arguments = [
        str(executable),
        "--species",
        str(request.get("species", 0)),
        "--level",
        str(request.get("level", 1)),
        "--terrain",
        str(request.get("terrain", 0)),
        "--shiny",
        str(request.get("shiny", 0)),
        "--groups",
        str(request.get("groupFlags", 0)),
        "--forced-override-mask",
        str(request.get("forcedOverrideMask", 0)),
        "--behavior-class",
        str(behavior_class),
        "--active-conditional-mask",
        str(condition_values[0]),
        "--request-version",
        str(condition_values[1]),
        "--target-kind",
        str(condition_values[2]),
        "--target-actor-slot",
        str(condition_values[3]),
        "--target-actor-generation",
        str(condition_values[4]),
        "--target-field-epoch",
        str(condition_values[5]),
        "--target-map-generation",
        str(condition_values[6]),
        "--target-encounter-generation",
        str(condition_values[7]),
        "--target-actor-reserved",
        str(condition_values[8]),
        "--winning-condition-id",
        str(condition_values[9]),
        "--target-source-application",
        str(condition_values[10]),
        "--resolved-target-condition-id",
        str(condition_values[11]),
    ]
    if blob is not None:
        blob = blob.resolve()
        if not blob.is_file():
            raise FileNotFoundError(f"behavior blob does not exist: {blob}")
        arguments[1:1] = ["--blob", str(blob)]
    completed = subprocess.run(
        arguments,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"resolver host failed: {detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("resolver host returned invalid JSON") from error
    if not isinstance(result, dict):
        raise RuntimeError("resolver host did not return a JSON object")
    return result


def resolve_many(
    blob: Path | None,
    requests: list[Mapping[str, Any]],
    *,
    root: Path | None = None,
    executable: Path | None = None,
) -> list[dict[str, Any]]:
    """Resolve many requests in one native process and one blob load."""

    if not requests:
        return []
    root = (root or _repo_root()).resolve()
    executable = executable or build(root)
    arguments = [str(executable), "--batch"]
    if blob is not None:
        blob = blob.resolve()
        if not blob.is_file():
            raise FileNotFoundError(f"behavior blob does not exist: {blob}")
        arguments.extend(["--blob", str(blob)])

    lines: list[str] = []
    for request in requests:
        behavior_class = request.get("behaviorClass", "auto")
        if behavior_class == "auto":
            behavior_class = 0xFF
        values = (
            request.get("species", 0),
            request.get("level", 1),
            request.get("terrain", 0),
            request.get("shiny", 0),
            request.get("groupFlags", 0),
            request.get("forcedOverrideMask", 0),
            behavior_class,
        ) + _condition_request_values(request)
        try:
            lines.append(" ".join(str(int(value)) for value in values))
        except (TypeError, ValueError) as error:
            raise ValueError("native resolver request values must be integers") from error

    completed = subprocess.run(
        arguments,
        cwd=root,
        input="\n".join(lines) + "\n",
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"resolver host batch failed: {detail}")
    output_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(output_lines) != len(requests):
        raise RuntimeError(
            "resolver host returned "
            f"{len(output_lines)} batch results for {len(requests)} requests"
        )
    results: list[dict[str, Any]] = []
    for line in output_lines:
        try:
            result = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError("resolver host returned invalid batch JSON") from error
        if not isinstance(result, dict):
            raise RuntimeError("resolver host batch result was not a JSON object")
        results.append(result)
    return results
