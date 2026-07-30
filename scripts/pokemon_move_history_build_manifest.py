#!/usr/bin/env python3
"""Seal and verify task-3 build provenance with content hashes."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Callable


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
    "build/save.d",
    "build/pokemon_move_history_overlay/pokemon_move_history.d",
    "build/pokemon_move_history_overlay/pokemon_move_relearn.d",
)
FIXED_INPUTS = (
    "Makefile",
    "docker-makerom.cmd",
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
    "scripts/generate_armips_symbols.py",
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
    "save_object": "build/save.o",
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


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in {errno.EINVAL, errno.ENOTSUP}:
                raise
    finally:
        os.close(descriptor)


def _require_regular_publish_leaf(
    path: Path,
    label: str,
    *,
    allow_missing: bool,
) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if allow_missing:
            return
        raise ManifestError(f"{label} is absent: {path}") from None
    if stat.S_ISLNK(mode):
        raise ManifestError(f"{label} must not be a symlink: {path}")
    if not stat.S_ISREG(mode):
        raise ManifestError(f"{label} is not a regular file: {path}")


def _lexically_normal_publish_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _require_distinct_publish_paths(paths: tuple[Path, ...]) -> None:
    filesystem_keys = {
        unicodedata.normalize("NFC", os.fspath(path)).casefold()
        for path in paths
    }
    if (
        len(set(paths)) != len(paths)
        or len(filesystem_keys) != len(paths)
    ):
        raise ManifestError(
            "candidate, final, and journal publish paths must be distinct"
        )
    journal = paths[-1]
    for role in paths[:-1]:
        try:
            aliases = os.path.samefile(role, journal)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ManifestError(
                "candidate, final, and journal identity check failed"
            ) from exc
        if aliases:
            raise ManifestError(
                "candidate, final, and journal publish paths must be "
                "distinct"
            )


def _clone_for_replace(source: Path, destination_directory: Path) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{source.name}.publish.",
        dir=destination_directory,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    try:
        try:
            os.link(source, temporary)
        except OSError:
            shutil.copyfile(source, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        _fsync_directory(destination_directory)
        return temporary
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_publish_journal(
    journal_path: Path,
    finals: tuple[Path, Path],
    prior_records: dict[Path, dict[str, Any] | None],
    backups: dict[Path, Path],
    stages: dict[Path, Path],
) -> None:
    document = {
        "schema": "pokemon-move-history-pair-publish-v1",
        "entries": [
            {
                "final": str(final.resolve()),
                "prior": prior_records[final],
                "backup": (
                    str(backups[final].resolve())
                    if final in backups
                    else None
                ),
                "stage": str(stages[final].resolve()),
            }
            for final in finals
        ],
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{journal_path.name}.",
        dir=journal_path.parent,
    )
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, journal_path)
        _fsync_directory(journal_path.parent)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _restore_publish_journal(
    journal_path: Path,
    finals: tuple[Path, Path],
    replace: Callable[[str | Path, str | Path], Any],
) -> None:
    _require_regular_publish_leaf(
        journal_path,
        "pair-publish recovery journal",
        allow_missing=False,
    )
    for final in finals:
        _require_regular_publish_leaf(
            final,
            "pair-publish final",
            allow_missing=True,
        )
    try:
        document = json.loads(journal_path.read_text())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ManifestError("pair-publish recovery journal is invalid") from exc
    entries = document.get("entries") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("schema")
        != "pokemon-move-history-pair-publish-v1"
        or not isinstance(entries, list)
        or len(entries) != 2
        or not all(isinstance(entry, dict) for entry in entries)
    ):
        raise ManifestError("pair-publish recovery journal schema differs")
    if any(
        set(entry) != {"final", "prior", "backup", "stage"}
        for entry in entries
    ):
        raise ManifestError("pair-publish recovery entry fields differ")
    expected_finals = [str(path.resolve()) for path in finals]
    if [entry.get("final") for entry in entries] != expected_finals:
        raise ManifestError("pair-publish recovery paths differ")

    final_resolved = {path.resolve() for path in finals}
    journal_resolved = journal_path.resolve()
    owned_temporaries: set[Path] = set()
    for entry, final in zip(entries, finals):
        prior = entry["prior"]
        backup_text = entry["backup"]
        stage_text = entry["stage"]
        temporary_texts = [stage_text]
        if prior is None:
            if backup_text is not None:
                raise ManifestError(
                    "pair-publish absent prior unexpectedly has a backup"
                )
        elif not isinstance(backup_text, str):
            raise ManifestError("pair-publish recovery backup path is invalid")
        else:
            temporary_texts.append(backup_text)
        for temporary_text in temporary_texts:
            if not isinstance(temporary_text, str):
                raise ManifestError(
                    "pair-publish recovery temporary path is invalid"
                )
            temporary = Path(temporary_text)
            _require_regular_publish_leaf(
                temporary,
                "pair-publish recovery temporary",
                allow_missing=True,
            )
            resolved = temporary.resolve()
            if (
                not temporary.is_absolute()
                or temporary.parent != final.parent
                or resolved.parent != final.parent.resolve()
                or re.fullmatch(
                    r"\..+\.publish\.[A-Za-z0-9_-]+",
                    resolved.name,
                )
                is None
                or resolved in final_resolved
                or resolved == journal_resolved
                or resolved in owned_temporaries
            ):
                raise ManifestError(
                    "pair-publish recovery temporary ownership differs"
                )
            owned_temporaries.add(resolved)

    restore_errors: list[str] = []
    for entry, final in zip(entries, finals):
        prior = entry.get("prior")
        backup_text = entry.get("backup")
        stage_text = entry.get("stage")
        if not isinstance(stage_text, str):
            restore_errors.append(f"{final}: malformed stage path")
            continue
        if prior is None:
            try:
                final.unlink(missing_ok=True)
                _fsync_directory(final.parent)
            except OSError as exc:
                restore_errors.append(f"{final}: {exc}")
            continue
        if (
            not isinstance(prior, dict)
            or set(prior) != {"size", "sha256"}
            or not isinstance(backup_text, str)
        ):
            restore_errors.append(f"{final}: malformed prior record")
            continue
        backup = Path(backup_text)
        restored = final.is_file() and file_record(final) == prior
        last_error: BaseException | None = None
        for _attempt in range(3 if not restored else 0):
            try:
                if not backup.is_file() or file_record(backup) != prior:
                    raise ManifestError(
                        f"recovery backup differs for {final}"
                    )
                replace(backup, final)
                _fsync_directory(final.parent)
                restored = file_record(final) == prior
                if restored:
                    break
            except BaseException as exc:
                last_error = exc
        if not restored:
            restore_errors.append(f"{final}: {last_error}")

    for entry, final in zip(entries, finals):
        prior = entry["prior"]
        if prior is None:
            if final.exists():
                restore_errors.append(f"{final}: expected absence")
        elif not final.is_file() or file_record(final) != prior:
            restore_errors.append(f"{final}: restored content differs")
    if restore_errors:
        raise ManifestError(
            "pair-publish rollback incomplete; recovery journal/backups "
            "retained: " + "; ".join(restore_errors)
        )
    cleanup_directories: set[Path] = set()
    for entry in entries:
        for field in ("backup", "stage"):
            path_text = entry.get(field)
            if isinstance(path_text, str):
                path = Path(path_text)
                path.unlink(missing_ok=True)
                cleanup_directories.add(path.parent)
    for directory in cleanup_directories:
        _fsync_directory(directory)
    journal_path.unlink()
    _fsync_directory(journal_path.parent)


def publish_pair(
    candidate_manifest: Path,
    candidate_rom: Path,
    final_manifest: Path,
    final_rom: Path,
    *,
    verify: Callable[[Path, Path], Any] = verify_manifest,
    failure_hook: Callable[[str], None] | None = None,
    replace: Callable[[str | Path, str | Path], Any] = os.replace,
) -> None:
    candidate_inputs = tuple(
        _lexically_normal_publish_path(Path(path))
        for path in (candidate_manifest, candidate_rom)
    )
    final_inputs = tuple(
        _lexically_normal_publish_path(Path(path))
        for path in (final_manifest, final_rom)
    )
    journal_input = final_inputs[0].with_name(
        final_inputs[0].name + ".publish-journal"
    )
    lexical_paths = candidate_inputs + final_inputs + (journal_input,)
    _require_distinct_publish_paths(lexical_paths)
    for candidate in candidate_inputs:
        _require_regular_publish_leaf(
            candidate,
            "pair-publish candidate",
            allow_missing=False,
        )
    for final in final_inputs:
        _require_regular_publish_leaf(
            final,
            "pair-publish final",
            allow_missing=True,
        )
    _require_regular_publish_leaf(
        journal_input,
        "pair-publish recovery journal",
        allow_missing=True,
    )

    candidates = tuple(path.resolve() for path in candidate_inputs)
    finals = tuple(path.resolve() for path in final_inputs)
    journal_path = journal_input.resolve()
    resolved_paths = candidates + finals + (journal_path,)
    _require_distinct_publish_paths(resolved_paths)
    candidate_manifest, candidate_rom = candidates
    final_manifest, final_rom = finals
    final_manifest.parent.mkdir(parents=True, exist_ok=True)
    final_rom.parent.mkdir(parents=True, exist_ok=True)
    final_paths = (final_manifest, final_rom)
    if journal_path.exists():
        _restore_publish_journal(journal_path, final_paths, replace)
    verify(candidate_manifest, candidate_rom)
    for candidate in candidates:
        _require_regular_publish_leaf(
            candidate,
            "pair-publish candidate",
            allow_missing=False,
        )
    for final in finals:
        _require_regular_publish_leaf(
            final,
            "pair-publish final",
            allow_missing=True,
        )
    _require_regular_publish_leaf(
        journal_path,
        "pair-publish recovery journal",
        allow_missing=True,
    )
    post_verify_paths = tuple(
        path.resolve()
        for path in (*candidate_inputs, *final_inputs, journal_input)
    )
    _require_distinct_publish_paths(post_verify_paths)
    if post_verify_paths != resolved_paths:
        raise ManifestError("pair-publish path topology changed during verify")

    prior_records = {
        final: file_record(final) if final.is_file() else None
        for final in final_paths
    }
    backups: dict[Path, Path] = {}
    stages: dict[Path, Path] = {}
    mutated = False
    try:
        for final, candidate in (
            (final_manifest, candidate_manifest),
            (final_rom, candidate_rom),
        ):
            if prior_records[final] is not None:
                backups[final] = _clone_for_replace(final, final.parent)
            stages[final] = _clone_for_replace(candidate, final.parent)

        _write_publish_journal(
            journal_path,
            final_paths,
            prior_records,
            backups,
            stages,
        )
        mutated = True
        replace(stages[final_manifest], final_manifest)
        _fsync_directory(final_manifest.parent)
        if failure_hook is not None:
            failure_hook("after_manifest_replace")

        replace(stages[final_rom], final_rom)
        _fsync_directory(final_rom.parent)
        if failure_hook is not None:
            failure_hook("after_rom_replace")

        verify(final_manifest, final_rom)
        candidate_manifest.unlink()
        candidate_rom.unlink()
        _fsync_directory(candidate_manifest.parent)
        if candidate_rom.parent != candidate_manifest.parent:
            _fsync_directory(candidate_rom.parent)
        journal_path.unlink()
        _fsync_directory(journal_path.parent)
    except BaseException:
        if mutated:
            _restore_publish_journal(journal_path, final_paths, replace)
        elif journal_path.exists():
            journal_path.unlink()
            _fsync_directory(journal_path.parent)
        raise
    finally:
        cleanup_backups = not journal_path.exists()
        temporaries = tuple(stages.values())
        if cleanup_backups:
            temporaries += tuple(backups.values())
        for temporary in temporaries:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--publish-pair", action="store_true")
    parser.add_argument("--rom", type=Path)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--candidate-rom", type=Path)
    parser.add_argument("--final-manifest", type=Path)
    parser.add_argument("--final-rom", type=Path)
    parser.add_argument(
        "--context",
        action="append",
        default=[],
        metavar="KEY=VALUE",
    )
    args = parser.parse_args()
    modes = (
        args.seal is not None,
        args.verify is not None,
        args.publish_pair,
    )
    if sum(modes) != 1:
        raise SystemExit(
            "choose exactly one of --seal, --verify, or --publish-pair"
        )
    publish_values = (
        args.candidate_manifest,
        args.candidate_rom,
        args.final_manifest,
        args.final_rom,
    )
    try:
        if args.seal is not None:
            if args.rom is None or any(
                value is not None for value in publish_values
            ):
                raise ManifestError(
                    "--seal requires --rom and no publish paths"
                )
            context: dict[str, str] = {}
            for item in args.context:
                if "=" not in item:
                    raise ManifestError(f"invalid build context: {item}")
                key, value = item.split("=", 1)
                if key in context:
                    raise ManifestError(f"duplicate build context: {key}")
                context[key] = value
            seal(args.seal, args.rom, context)
        elif args.verify is not None:
            if (
                args.rom is None
                or args.context
                or any(value is not None for value in publish_values)
            ):
                raise ManifestError(
                    "--verify requires --rom and no seal/publish options"
                )
            verify_manifest(args.verify, args.rom)
        else:
            if args.rom is not None or args.context or any(
                value is None for value in publish_values
            ):
                raise ManifestError(
                    "--publish-pair requires exactly candidate/final "
                    "manifest and ROM paths"
                )
            injected_phase = os.environ.get(
                "POKEMON_MOVE_HISTORY_TEST_PUBLISH_FAILURE"
            )
            if injected_phase not in {
                None,
                "after_manifest_replace",
                "after_rom_replace",
            }:
                raise ManifestError("invalid injected publish-failure phase")

            def fail_for_fixture(phase: str) -> None:
                if phase == injected_phase:
                    raise ManifestError(
                        f"injected pair-publish failure: {phase}"
                    )

            publish_pair(
                args.candidate_manifest,
                args.candidate_rom,
                args.final_manifest,
                args.final_rom,
                failure_hook=(
                    fail_for_fixture if injected_phase is not None else None
                ),
            )
    except ManifestError as exc:
        raise SystemExit(f"move-history build manifest failed: {exc}") from exc


if __name__ == "__main__":
    main()
