"""Deterministic identity and evidence manifests for overworld host runs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_SCHEMA = "overworld-system-run-v1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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


def source_record(repo: Path) -> dict[str, Any]:
    revision = _git(repo, "rev-parse", "HEAD")
    diff = subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"],
        cwd=repo,
        capture_output=True,
    )
    diff_bytes = diff.stdout if diff.returncode == 0 else b""
    changed = _git(repo, "diff", "--name-only", "HEAD", "--")
    paths = [] if not changed else sorted(line for line in changed.splitlines() if line)
    untracked_output = subprocess.run(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "scripts/owctl",
            "tools/overworld",
            "tests/overworld",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    untracked_paths = (
        sorted(line for line in untracked_output.stdout.splitlines() if line)
        if untracked_output.returncode == 0
        else []
    )
    untracked_records = [file_record(Path(path), repo) for path in untracked_paths]
    return {
        "revision": revision,
        "dirty": bool(paths or untracked_paths),
        "trackedDiffSha256": hashlib.sha256(diff_bytes).hexdigest(),
        "trackedChangedPaths": paths,
        "controlUntrackedFiles": untracked_records,
    }


def emulator_record() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("desmume")
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"name": "DeSmuME", "pythonPackageVersion": version}


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
        "source": source_record(repo),
        "scenarioRevision": digest_value(scenario) if scenario is not None else None,
        "seed": fixture.get("seed") if fixture else None,
        "rom": file_record(rom_path, repo),
        "save": file_record(save_path, repo),
        "buildManifest": file_record(build_manifest_path, repo),
        "debugDescriptor": file_record(debug_descriptor_path, repo),
        "emulator": emulator_record(),
        "commands": commands,
    }
    return {
        "schema": RUN_SCHEMA,
        "runId": digest_value(identity)[:20],
        "startedAtUtc": started_at,
        "identity": identity,
        "proofLevel": proof_level,
        "costTier": cost_tier,
        "result": {
            "passed": all(item.get("passed", False) for item in results),
            "steps": results,
        },
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
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return output


def re_safe(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "-" for character in value)
