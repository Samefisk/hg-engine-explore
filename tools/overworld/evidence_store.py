"""Isolate immutable proof from collectors' replaceable staging files."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
from pathlib import Path
import tempfile
from typing import Any

from tools.overworld.validation import ValidationFailure


@contextmanager
def scenario_lock(repo: Path):
    """Collectors still have fixed output names; one owns them at a time.

    The kernel releases this lock after a crash. A leftover lock file is safe.
    Do not wait on another agent or delete its lock/process.
    """
    path = repo / "build/overworld-runs/.collector.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValidationFailure("another owctl scenario owns the collector; use progress before retrying") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def artifact_directory(repo: Path) -> Path:
    parent = repo / "build/overworld-artifacts"
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="run-", dir=parent))


def archive_command_output(step: dict[str, Any], repo: Path, directory: Path,
                           index: int, stdout: bytes, stderr: bytes) -> None:
    """Keep both complete byte streams, including empty and failed output.

    Exclusive creation prevents a retry from replacing an earlier command.
    If one stream cannot be saved, still try the other and retain its link.
    """
    errors = []
    for name, data in (("stdout", stdout), ("stderr", stderr)):
        target = directory / f"{index}-{name}.log"
        try:
            relative = target.relative_to(repo).as_posix()
            with target.open("xb") as stream:
                stream.write(data)
            step[name + "Artifact"] = {
                "path": relative, "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        except (OSError, ValueError) as error:
            errors.append(f"{name}: {error}")
    if errors:
        raise ValidationFailure("command output could not be preserved: " + "; ".join(errors))


def require_command_output(step: dict[str, Any], repo: Path) -> None:
    """Authenticate both run-owned logs before an accepted result is reused."""
    for name in ("stdout", "stderr"):
        record = step.get(name + "Artifact")
        if (not isinstance(record, dict) or set(record) != {"path", "size", "sha256"}
                or not isinstance(record.get("path"), str)
                or type(record.get("size")) is not int or record["size"] < 0):
            raise ValidationFailure(f"{name} log identity is missing or invalid")
        path = repo / record["path"]
        owned_root = (repo / "build/overworld-artifacts").resolve()
        if path.is_symlink() or not path.resolve().is_relative_to(owned_root):
            raise ValidationFailure(f"{name} log is not a run-owned file")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if (len(data) != record["size"] or digest != record["sha256"]
                or digest != step.get(name + "Sha256")):
            raise ValidationFailure(f"{name} log identity differs")


def archive_step(step: dict[str, Any], repo: Path, directory: Path, index: int) -> None:
    """Copy authenticated bytes once and record their run-owned location."""
    for field in ("evidence", "visualArtifact"):
        record = step.get(field)
        if not isinstance(record, dict):
            continue
        source = Path(record["path"])
        if not source.is_absolute():
            source = repo / source
        data = source.read_bytes()
        if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValidationFailure(f"{field} changed before it could be preserved")
        target = directory / f"{index}-{field}{source.suffix}"
        with target.open("xb") as stream:
            stream.write(data)
        step[field] = {**record, "path": target.relative_to(repo).as_posix()}
