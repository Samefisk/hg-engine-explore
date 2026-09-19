"""Deterministic identity and evidence manifests for overworld host runs."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validation import ValidationFailure


RUN_SCHEMA = "overworld-system-run-v4"
SOURCE_SCHEMA = "overworld-proof-inputs-v2"
# These are records or outputs, not product/proof inputs. Everything else
# visible to Git is included, including new files and build-tool submodules.
# Generated build inputs and toolchain settings remain bound by the sealed
# build manifest; packaged outputs, save and emulator are bound separately.
NON_INPUT_ROOTS = frozenset({
    "documentation", "docs", "Design Documents", "design_previews",
    "build", "base", "narc", "sdat", ".venv", ".headless_desmume",
})
NON_INPUT_PARTS = frozenset({"__pycache__", ".pytest_cache", "node_modules"})
NON_INPUT_SUFFIXES = frozenset({".md", ".pyc", ".pyo", ".o", ".d", ".nds", ".sav", ".dsv"})
HEADLESS_PYTHON_FLAGS = ("-I", "-S", "-B", "-X", "pycache_prefix=/dev/null")
OVERWORLD_PRODUCT_OUTPUTS = (
    (
        "actor",
        "actorOverlay",
        158,
        Path("build/output_overworld_actor_system_overlay.bin"),
    ),
    (
        "wildSpawns",
        "wildSpawnsOverlay",
        149,
        Path("build/output_overworld_wild_spawns_overlay.bin"),
    ),
    (
        "wildRuntime",
        "wildRuntimeOverlay",
        156,
        Path("build/output_overworld_wild_runtime_overlay.bin"),
    ),
    (
        "mount",
        "mountOverlay",
        157,
        Path("build/output_overworld_mount_overlay.bin"),
    ),
    (
        "walk",
        "walkOverlay",
        153,
        Path("build/output_pokemon_move_history_overlay.bin"),
    ),
    (
        "hopRoleController",
        "hopRoleControllerOverlay",
        155,
        Path("build/output_pokemon_move_history_task6_overlay.bin"),
    ),
    (
        "helper",
        "helperOverlay",
        151,
        Path("build/output_overworld_wild_helper_overlay.bin"),
    ),
    (
        "behavior",
        "behaviorOverlay",
        150,
        Path("build/output_overworld_wild_behavior_data_overlay.bin"),
    ),
    (
        "selector",
        "selectorOverlay",
        152,
        Path("build/output_overworld_follower_selector_overlay.bin"),
    ),
    (
        "field",
        "fieldOverlay",
        131,
        Path("build/output_field.bin"),
    ),
)

OVERWORLD_LINKED_OUTPUTS = (
    ("actorLinked", Path("build/overworld_actor_system_overlay_linked.o")),
    ("mountLinked", Path("build/overworld_mount_overlay_linked.o")),
    ("walkLinked", Path("build/pokemon_move_history_overlay_linked.o")),
    (
        "selectorLinked",
        Path("build/overworld_follower_selector_overlay_linked.o"),
    ),
    (
        "wildSpawnsLinked",
        Path("build/overworld_wild_spawns_overlay_linked.o"),
    ),
    (
        "wildRuntimeLinked",
        Path("build/overworld_wild_runtime_overlay_linked.o"),
    ),
    (
        "hopRoleControllerLinked",
        Path("build/pokemon_move_history_task6_overlay_linked.o"),
    ),
    (
        "behaviorLinked",
        Path("build/overworld_wild_behavior_data_overlay_linked.o"),
    ),
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def run_id_for(
    identity: dict[str, Any],
    result: dict[str, Any],
    proof_level: str,
    cost_tier: int,
) -> tuple[str, str]:
    """Bind one run id to its inputs and complete result receipt."""
    result_sha256 = digest_value(result)
    receipt = {
        "identity": identity,
        "resultSha256": result_sha256,
        "proofLevel": proof_level,
        "costTier": cost_tier,
    }
    return digest_value(receipt)[:20], result_sha256


def file_record(path: Path | None, repo: Path) -> dict[str, Any] | None:
    if path is None:
        return None
    target = path if path.is_absolute() else repo / path
    if not target.is_file():
        return {"path": str(path), "present": False, "size": None, "sha256": None}
    digest = hashlib.sha256()
    size = 0
    with target.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    try:
        relative = target.resolve().relative_to(repo.resolve())
        label = relative.as_posix()
    except ValueError:
        label = target.name
    return {
        "path": label,
        "present": True,
        "size": size,
        "sha256": digest.hexdigest(),
    }


def _git(repo: Path, *arguments: str) -> str | None:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_bytes(repo: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments], cwd=repo, capture_output=True,
        )
    except OSError as error:
        raise ValidationFailure(f"proof input scan could not run Git: {error}") from error
    if completed.returncode != 0:
        raise ValidationFailure(
            "proof input scan failed: git " + " ".join(arguments)
            + ": " + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout


def _is_proof_input(path: Path) -> bool:
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ValidationFailure(f"invalid proof input path: {path}")
    return not (
        path.parts[0] in NON_INPUT_ROOTS
        or any(part in NON_INPUT_PARTS for part in path.parts)
        or path.suffix.lower() in NON_INPUT_SUFFIXES
        or ".sav." in path.name or ".dsv." in path.name
        or path.name in {".DS_Store", "PAPERCUTS.md"}
    )


def _input_paths(repo: Path, prefix: Path = Path()) -> list[Path]:
    """Read the working content, not index blobs or submodule commit IDs."""
    paths: set[Path] = set()
    indexed = _git_bytes(repo, "ls-files", "--stage", "-z")
    for row in indexed.split(b"\0"):
        if not row:
            continue
        try:
            metadata, raw_path = row.split(b"\t", 1)
            mode, _object_id, stage = metadata.split()
        except ValueError as error:
            raise ValidationFailure("malformed Git proof input inventory") from error
        relative = Path(os.fsdecode(raw_path))
        logical = prefix / relative
        if not _is_proof_input(logical):
            continue
        if stage != b"0":
            raise ValidationFailure(f"unmerged proof input: {logical}")
        target = repo / relative
        if mode == b"160000":
            if not (target / ".git").exists():
                raise ValidationFailure(f"proof input submodule is not initialized: {logical}")
            paths.update(_input_paths(target, logical))
        else:
            paths.add(logical)
    untracked = _git_bytes(repo, "ls-files", "--others", "--exclude-standard", "-z")
    paths.update(
        prefix / Path(os.fsdecode(raw_path))
        for raw_path in untracked.split(b"\0")
        if raw_path and _is_proof_input(prefix / Path(os.fsdecode(raw_path)))
    )
    # A tracked deletion is an absent input, both before and after commit.
    # A later unexpected disappearance while hashing is an error, not absence.
    deleted = _git_bytes(repo, "ls-files", "--deleted", "-z")
    paths.difference_update(
        prefix / Path(os.fsdecode(raw_path))
        for raw_path in deleted.split(b"\0") if raw_path
    )
    return sorted(paths)


def _input_record(repo: Path, relative: Path) -> dict[str, Any]:
    target = repo / relative
    try:
        before = target.lstat()
        link = os.readlink(target) if stat.S_ISLNK(before.st_mode) else None
        if link is not None:
            resolved = target.resolve(strict=True)
            if not resolved.is_relative_to(repo.resolve()):
                raise ValidationFailure(f"proof input symlink leaves repository: {relative}")
        if not target.is_file():
            raise ValidationFailure(f"proof input is not a regular file: {relative}")
        content_before = target.stat()
        record = file_record(relative, repo)
        content_after = target.stat()
        after = target.lstat()
    except OSError as error:
        raise ValidationFailure(f"proof input could not be read: {relative}: {error}") from error
    def fingerprint(value: os.stat_result) -> tuple[int, ...]:
        # Reading can change access time. It cannot change these input facts.
        return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                value.st_mtime_ns, value.st_ctime_ns)

    if fingerprint(before) != fingerprint(after) or fingerprint(content_before) != fingerprint(content_after):
        raise ValidationFailure(f"proof input changed during scan: {relative}")
    return {
        **record, "path": relative.as_posix(),
        "executable": bool(before.st_mode & 0o111), "symlink": link,
    }


def source_record(repo: Path) -> dict[str, Any]:
    """Commit-independent input identity. Git provenance is stored separately.

    No cache is used. A failed scan never becomes an empty/clean identity.
    Per-root hashes keep manifests small without dropping any input content.
    """
    root = repo.resolve()
    paths = _input_paths(root)
    if not paths:
        raise ValidationFailure("proof input inventory is empty")
    groups: dict[str, list[dict[str, Any]]] = {}
    for relative in paths:
        groups.setdefault(relative.parts[0], []).append(_input_record(root, relative))
    if _input_paths(root) != paths:
        raise ValidationFailure("proof input path set changed during scan")
    roots = {
        name: {
            "sha256": digest_value(records), "fileCount": len(records),
            "byteCount": sum(record["size"] for record in records),
        }
        for name, records in sorted(groups.items())
    }
    return {
        "schema": SOURCE_SCHEMA, "sha256": digest_value(roots), "roots": roots,
        "fileCount": sum(group["fileCount"] for group in roots.values()),
        "byteCount": sum(group["byteCount"] for group in roots.values()),
    }


def git_provenance(repo: Path) -> dict[str, Any]:
    """Keep full Git context for diagnosis without making it gameplay input."""
    revision = _git_bytes(repo, "rev-parse", "HEAD").decode("ascii").strip()
    state = _git_bytes(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    diff = _git_bytes(repo, "diff", "--binary", "--no-ext-diff", "HEAD", "--")
    return {
        "revision": revision, "branch": _git(repo, "branch", "--show-current"),
        "dirty": bool(state), "trackedDiffSha256": hashlib.sha256(diff).hexdigest(),
        "statusEntries": [os.fsdecode(row) for row in state.split(b"\0") if row],
    }


def headless_python(repo: Path) -> Path:
    """Return the exact interpreter used by repository headless adapters."""

    return repo / ".venv/bin/python3"


def emulator_record(repo: Path) -> dict[str, Any]:
    """Inspect the pinned melonDS bridge without opening a core."""

    python = headless_python(repo)
    record: dict[str, Any] = {
        "name": "melonDS",
        "present": False,
        "pythonExecutable": str(python),
        "pythonFlags": list(HEADLESS_PYTHON_FLAGS),
        "pythonPackage": None,
        "pythonPackageVersion": None,
    }
    if not python.is_file():
        record["detail"] = "repository headless interpreter is missing"
        return record

    inspection = (
        "import json,sys;"
        f"sys.path.insert(0,{str(repo)!r});"
        "from tools.overworld.melonds_backend import load_library;"
        "lib=load_library();"
        "from pathlib import Path;"
        f"manifest=json.loads(Path({str(repo / 'build/melonds/manifest.json')!r}).read_text());"
        "print(json.dumps({'executable':sys.executable,"
        "'version':lib.md_source_revision().decode(),'nativeBuild':manifest}))"
    )
    completed = subprocess.run(
        [str(python), *HEADLESS_PYTHON_FLAGS, "-c", inspection],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        record["detail"] = (
            completed.stderr.strip().splitlines()[-1]
            if completed.stderr.strip()
            else "melonDS bridge inspection failed"
        )
        return record
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        record["detail"] = "headless runtime inspection returned invalid JSON"
        return record
    if result.get("executable") != str(python):
        record["detail"] = "headless runtime reported a different interpreter"
        return record
    record["present"] = True
    record["pythonPackageVersion"] = result.get("version")
    record["nativeBuild"] = result["nativeBuild"]
    record["detail"] = "pinned melonDS bridge ABI and binary identity checked; no core started"
    return record


def utc_now() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch is not None:
        instant = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    else:
        instant = datetime.now(timezone.utc)
    return instant.isoformat(timespec="seconds").replace("+00:00", "Z")


def make_run_manifest(
    *,
    repo: Path,
    kind: str,
    target: str,
    proof_level: str,
    cost_tier: int,
    scenario: dict[str, Any] | None,
    commands: list[list[str]],
    results: list[dict[str, Any]],
    started_at: str,
    source_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fixture = scenario.get("fixture") if scenario is not None else None
    rom_path = Path(fixture["rom"]) if fixture and fixture.get("rom") else Path("test.nds")
    save_path = None
    if fixture and fixture.get("save"):
        save_path = Path(fixture["save"]["path"])
    build_manifest_path = Path("build/pokemon_move_history_capture_build.json")
    debug_descriptor_path = Path("build/overworld-system.debug.json")
    identity = {
        "kind": kind,
        "target": target,
        "source": source_identity if source_identity is not None else source_record(repo),
        "scenarioRevision": digest_value(scenario) if scenario is not None else None,
        "seed": fixture.get("seed") if fixture else None,
        "rom": file_record(rom_path, repo),
        "save": file_record(save_path, repo),
        "buildManifest": file_record(build_manifest_path, repo),
        "debugDescriptor": file_record(debug_descriptor_path, repo),
        "emulator": emulator_record(repo),
        "commands": commands,
    }
    identity.update({
        identity_name: file_record(path, repo)
        for _fixture_key, identity_name, _overlay_id, path
        in OVERWORLD_PRODUCT_OUTPUTS
    })
    identity.update({
        identity_name: file_record(path, repo)
        for identity_name, path in OVERWORLD_LINKED_OUTPUTS
    })
    result = {
        "passed": all(item.get("passed", False) for item in results),
        "steps": results,
    }
    run_id, result_sha256 = run_id_for(
        identity, result, proof_level, cost_tier
    )
    return {
        "schema": RUN_SCHEMA,
        "runId": run_id,
        "resultSha256": result_sha256,
        "startedAtUtc": started_at,
        "gitProvenance": git_provenance(repo),
        "identity": identity,
        "proofLevel": proof_level,
        "costTier": cost_tier,
        "result": result,
    }


def write_run_manifest(
    document: dict[str, Any], repo: Path, output: Path | None = None
) -> Path:
    if output is None:
        safe_target = re_safe(document["identity"]["target"])
        stamp = document["startedAtUtc"].replace(":", "").replace("-", "")
        output = (
            repo
            / "build/overworld-runs"
            / safe_target
            / f"{stamp}-{document['runId']}.json"
        )
    elif not output.is_absolute():
        output = repo / output
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(document, indent=2, sort_keys=True) + "\n"
    try:
        with output.open("x") as stream:
            stream.write(content)
    except FileExistsError:
        if output.is_symlink() or output.read_text() != content:
            raise ValidationFailure(f"run manifest already exists with different content: {output}")
    return output


def re_safe(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "-" for character in value)
