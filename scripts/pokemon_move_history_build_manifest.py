#!/usr/bin/env python3
"""Seal and verify task-3 build provenance with content hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
SCHEMA = "pokemon-move-history-capture-build-v1"
PACKAGED_ROM_LOGICAL_PATH = "@packaged-rom"
BUILD_CONTEXT_KEYS = {
    "ARMIPS",
    "ARMIPS_FLAGS",
    "AS",
    "ASFLAGS",
    "CC",
    "CFLAGS",
    "LD",
    "LDFLAGS",
    "NDSTOOL",
    "OBJCOPY",
}
TOOL_CONTEXT_KEYS = {"ARMIPS", "AS", "CC", "LD", "NDSTOOL", "OBJCOPY"}

DEPENDENCY_FILES = (
    "build/pokemon.d",
    "build/party_menu.d",
    "build/pokemon_move_history_overlay/pokemon_move_history.d",
    "build/pokemon_move_history_overlay/pokemon_move_relearn.d",
)
FIXED_INPUTS = (
    "Makefile",
    "hooks",
    "overlays.mk",
    "rom.nds",
    "rom.ld",
    "rom_gen.ld",
    "armips/global.s",
    "armips/asm/pokemon_move_history_capture.s",
    "asm/pokemon_move_history_overlay/entry.s",
    "asm/pokemon_move_history_overlay/thumb_help.s",
    "src/pokemon_move_history_overlay/linker.ld",
    "scripts/pokemon_move_history_build_manifest.py",
    "scripts/generate_ld.py",
    "scripts/make.py",
    "scripts/verify_pokemon_move_history_capture.py",
    "scripts/verify_pokemon_move_history.py",
)
OUTPUTS = {
    "core_linked": "build/linked.o",
    "core_binary": "build/output.bin",
    "pokemon_object": "build/pokemon.o",
    "party_menu_object": "build/party_menu.o",
    "history_object":
        "build/pokemon_move_history_overlay/pokemon_move_history.o",
    "relearn_object":
        "build/pokemon_move_history_overlay/pokemon_move_relearn.o",
    "entry_object": "build/pokemon_move_history_overlay/entry.o",
    "thumb_help_object": "build/pokemon_move_history_overlay/thumb_help.o",
    "history_linked": "build/pokemon_move_history_overlay_linked.o",
    "history_binary": "build/output_pokemon_move_history_overlay.bin",
    "patched_arm9": "base/arm9.bin",
    "overlay_table": "base/overarm9.bin",
    "patched_overlay12": "base/overlay/overlay_0012.bin",
    "patched_overlay68": "base/overlay/overlay_0068.bin",
    "patched_overlay129": "base/overlay/overlay_0129.bin",
    "patched_overlay153": "base/overlay/overlay_0153.bin",
}


class ManifestError(ValueError):
    """The manifest does not describe the current build generation."""


def _relative(path: Path, root: Path = REPO) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManifestError(f"path is outside the repository: {path}") from exc


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ManifestError(f"required manifest file is absent: {path}")
    data = path.read_bytes()
    return {"size": len(data), "sha256": _sha256(data)}


def _dependency_paths(path: Path) -> set[str]:
    if not path.is_file():
        raise ManifestError(f"dependency file is absent: {path}")
    logical = path.read_text().replace("\\\n", " ")
    if ":" not in logical:
        raise ManifestError(f"dependency file has no target separator: {path}")
    dependencies = logical.split(":", 1)[1].split()
    result: set[str] = set()
    for dependency in dependencies:
        resolved = (REPO / dependency).resolve()
        relative = _relative(resolved)
        if not resolved.is_file():
            raise ManifestError(
                f"dependency from {path} is absent: {relative}"
            )
        result.add(relative)
    return result


def armips_dependency_paths(root: Path, entry: Path) -> set[str]:
    paths: set[str] = set()
    pending = [entry]
    visited: set[str] = set()
    while pending:
        source_path = pending.pop()
        relative = _relative(source_path, root)
        if relative in visited:
            continue
        visited.add(relative)
        if not source_path.is_file():
            raise ManifestError(f"ARMIPS input is absent: {relative}")
        paths.add(relative)
        source_text = source_path.read_text()
        for directive, included_text in re.findall(
            r'(?m)^\s*\.(include|incbin|importobj)\s+"([^"]+)"',
            source_text,
        ):
            included = (root / included_text).resolve()
            if not included.is_file():
                raise ManifestError(
                    f"ARMIPS {directive} from {relative} is absent: "
                    f"{included_text}"
                )
            included_relative = _relative(included, root)
            paths.add(included_relative)
            if directive == "include":
                pending.append(included)
    return paths


def expected_inputs() -> tuple[str, ...]:
    paths = set(FIXED_INPUTS)
    paths.update(DEPENDENCY_FILES)
    for dependency_file in DEPENDENCY_FILES:
        paths.update(_dependency_paths(REPO / dependency_file))
    paths.update(armips_dependency_paths(REPO, REPO / "armips/global.s"))
    return tuple(sorted(paths))


def _tool_identity(role: str, command: str) -> dict[str, Any]:
    words = shlex.split(command)
    if not words:
        raise ManifestError(f"empty build tool command: {role}")
    executable = words[0]
    repo_candidate = (REPO / executable).resolve()
    resolved_text = (
        str(repo_candidate)
        if repo_candidate.is_file()
        else shutil.which(executable)
    )
    if resolved_text is None:
        raise ManifestError(f"required build tool is absent: {role}={command}")
    resolved = Path(resolved_text).resolve()
    try:
        output = subprocess.check_output(
            [str(resolved), "--version"],
            text=True,
            stderr=subprocess.STDOUT,
        ).splitlines()
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        output = []
    return {
        "command": command,
        "version": output[0] if output else "",
        "binary": file_record(resolved),
    }


def tool_identities(build_context: dict[str, str]) -> dict[str, Any]:
    return {
        role: _tool_identity(role, build_context[role])
        for role in sorted(TOOL_CONTEXT_KEYS)
    }


def _hash_inputs(paths: tuple[str, ...]) -> dict[str, Any]:
    return {path: file_record(REPO / path) for path in paths}


def _hash_outputs(rom_path: Path) -> dict[str, Any]:
    outputs = {
        role: {"path": path, **file_record(REPO / path)}
        for role, path in sorted(OUTPUTS.items())
    }
    outputs["packaged_rom"] = {
        "path": PACKAGED_ROM_LOGICAL_PATH,
        **file_record(rom_path),
    }
    return outputs


def create_manifest(
    rom_path: Path,
    build_context: dict[str, str],
) -> dict[str, Any]:
    if set(build_context) != BUILD_CONTEXT_KEYS:
        raise ManifestError("build context key set differs")
    input_paths = expected_inputs()
    first_inputs = _hash_inputs(input_paths)
    document = {
        "schema": SCHEMA,
        "build_context": dict(sorted(build_context.items())),
        "inputs": first_inputs,
        "outputs": _hash_outputs(rom_path),
        "tools": tool_identities(build_context),
    }
    if _hash_inputs(input_paths) != first_inputs:
        raise ManifestError("an input changed while the build was being sealed")
    return document


def _validate_file_map(
    root: Path,
    records: dict[str, Any],
    expected_paths: set[str],
    label: str,
) -> None:
    if set(records) != expected_paths:
        raise ManifestError(
            f"{label} path set differs: expected {sorted(expected_paths)}, "
            f"got {sorted(records)}"
        )
    for relative, record in records.items():
        if not isinstance(record, dict) or set(record) != {"size", "sha256"}:
            raise ManifestError(f"{label} record is malformed: {relative}")
        actual = file_record(root / relative)
        if actual != record:
            raise ManifestError(f"{label} content hash differs: {relative}")


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise ManifestError(f"build manifest is absent: {manifest_path}")
    try:
        document = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError("build manifest is not valid JSON") from exc
    if not isinstance(document, dict):
        raise ManifestError("build manifest top level is not an object")
    return document


def _validate_tool_records(
    tools: Any,
    expected_names: set[str],
    build_context: dict[str, str],
) -> None:
    if not isinstance(tools, dict) or set(tools) != expected_names:
        raise ManifestError("build tool role set differs")
    for name, record in tools.items():
        expected_fields = {"command", "binary", "version"}
        if not isinstance(record, dict) or set(record) != expected_fields:
            raise ManifestError(f"build tool record is malformed: {name}")
        binary = record["binary"]
        if (
            not isinstance(record["command"], str)
            or build_context.get(name) != record["command"]
            or not isinstance(record["version"], str)
            or not isinstance(binary, dict)
            or set(binary) != {"size", "sha256"}
            or not isinstance(binary["size"], int)
            or not isinstance(binary["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", binary["sha256"]) is None
        ):
            raise ManifestError(f"build tool identity is malformed: {name}")


def verify_manifest_document(
    document: dict[str, Any],
    root: Path,
    input_paths: set[str],
    output_paths: dict[str, str],
    rom_path: Path,
    tool_names: set[str],
    context_keys: set[str],
) -> None:
    if not isinstance(document, dict) or set(document) != {
        "schema",
        "build_context",
        "inputs",
        "outputs",
        "tools",
    }:
        raise ManifestError("build manifest top-level fields differ")
    if document["schema"] != SCHEMA:
        raise ManifestError("build manifest schema differs")
    _validate_file_map(
        root,
        document["inputs"],
        input_paths,
        "build input",
    )
    expected_roles = set(output_paths) | {"packaged_rom"}
    outputs = document["outputs"]
    if not isinstance(outputs, dict) or set(outputs) != expected_roles:
        raise ManifestError("build output role set differs")
    expected_output_paths = dict(output_paths)
    expected_output_paths["packaged_rom"] = PACKAGED_ROM_LOGICAL_PATH
    seen_paths: set[str] = set()
    for role, expected_path in expected_output_paths.items():
        record = outputs[role]
        if not isinstance(record, dict) or set(record) != {
            "path",
            "size",
            "sha256",
        }:
            raise ManifestError(f"build output record is malformed: {role}")
        if record["path"] != expected_path or expected_path in seen_paths:
            raise ManifestError(f"build output path differs/duplicates: {role}")
        seen_paths.add(expected_path)
        actual_path = rom_path if role == "packaged_rom" else root / expected_path
        if file_record(actual_path) != {
            "size": record["size"],
            "sha256": record["sha256"],
        }:
            raise ManifestError(f"build output content hash differs: {role}")
    context = document["build_context"]
    if (
        not isinstance(context, dict)
        or set(context) != context_keys
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in context.items()
        )
    ):
        raise ManifestError("build context differs or is malformed")
    _validate_tool_records(document["tools"], tool_names, context)


def verify_manifest(manifest_path: Path, rom_path: Path) -> dict[str, Any]:
    document = load_manifest(manifest_path)
    verify_manifest_document(
        document,
        REPO,
        set(expected_inputs()),
        OUTPUTS,
        rom_path,
        TOOL_CONTEXT_KEYS,
        BUILD_CONTEXT_KEYS,
    )
    return document


def seal(
    manifest_path: Path,
    rom_path: Path,
    build_context: dict[str, str],
) -> None:
    document = create_manifest(rom_path, build_context)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=manifest_path.name + ".",
        dir=manifest_path.parent,
    )
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary_name, manifest_path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        metavar="KEY=VALUE",
    )
    args = parser.parse_args()
    if (args.seal is None) == (args.verify is None):
        raise SystemExit("choose exactly one of --seal or --verify")
    try:
        if args.seal is not None:
            context: dict[str, str] = {}
            for item in args.context:
                if "=" not in item:
                    raise ManifestError(f"invalid build context: {item}")
                key, value = item.split("=", 1)
                if key in context:
                    raise ManifestError(f"duplicate build context: {key}")
                context[key] = value
            seal(args.seal, args.rom, context)
        else:
            if args.context:
                raise ManifestError("--context is valid only with --seal")
            verify_manifest(args.verify, args.rom)
    except ManifestError as exc:
        raise SystemExit(f"move-history build manifest failed: {exc}") from exc


if __name__ == "__main__":
    main()
