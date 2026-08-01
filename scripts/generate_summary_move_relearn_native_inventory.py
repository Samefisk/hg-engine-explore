#!/usr/bin/env python3
"""Generate the reviewed host closure consumed before CPython starts.

This is an authoring utility, not a runtime launcher.  The generated inventory
is committed, content-addressed by the build manifest, and compiled into the
native bootstrap by digest.  Production binding and acceptance never generate
or trust a fresh inventory.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HEADER = "summary-move-relearn-native-bootstrap-inventory-v2\n"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
DIRECTORY_DIGEST_DOMAIN = b"summary-move-relearn-directory-membership-v1\0"
RUNTIME_SOURCES = (
    "scripts/pokemon_move_history_build_manifest.py",
    "scripts/launch_summary_move_relearn_runtime.py",
    "scripts/verify_summary_move_relearn_runtime.py",
    "scripts/headless-overworld-test.py",
    "scripts/verify_pokemon_move_history_party_integrity.py",
)
BASE = Path("/Library/Frameworks/Python.framework/Versions/3.10")
STDLIB = BASE / "lib/python3.10"
PYTHON = BASE / "bin/python3.10"
EXTRA_NATIVE = (
    BASE / "Python",
    BASE / "Resources/Python.app/Contents/MacOS/Python",
    BASE / "lib/libcrypto.1.1.dylib",
    BASE / "lib/libssl.1.1.dylib",
)
REVIEWED_TREE_SYMLINKS = {
    STDLIB / "config-3.10-darwin/libpython3.10.a",
    STDLIB / "config-3.10-darwin/libpython3.10.dylib",
}


class InventoryError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_absolute_clean(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    if "\t" in str(absolute) or "\n" in str(absolute):
        raise InventoryError(f"inventory path contains a delimiter: {absolute}")
    return absolute


def directory_membership(path: Path) -> tuple[int, str]:
    members: list[tuple[bytes, bytes]] = []
    with os.scandir(path) as entries:
        for entry in entries:
            name = os.fsencode(entry.name)
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISREG(metadata.st_mode):
                kind = b"F"
            elif stat.S_ISDIR(metadata.st_mode):
                kind = b"D"
            elif stat.S_ISLNK(metadata.st_mode):
                kind = b"L"
            else:
                raise InventoryError(
                    f"unsupported inventory directory member: {path / entry.name}"
                )
            members.append((name, kind))
    members.sort(key=lambda item: item[0])
    payload = bytearray(DIRECTORY_DIGEST_DOMAIN)
    for name, kind in members:
        payload.extend(kind)
        payload.extend(len(name).to_bytes(8, "big"))
        payload.extend(name)
    return len(payload), digest(bytes(payload))


def add_directory(records: dict[Path, tuple[str, int, str]], path: Path) -> None:
    path = ensure_absolute_clean(path)
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.resolve() != path:
        raise InventoryError(f"inventory directory is not canonical: {path}")
    prior = records.get(path)
    value = ("D", 0, EMPTY_SHA256)
    if prior is not None and prior[0] == "M":
        return
    if prior is not None and prior != value:
        raise InventoryError(f"conflicting inventory directory: {path}")
    records[path] = value


def add_membership_directory(
    records: dict[Path, tuple[str, int, str]], path: Path
) -> None:
    path = ensure_absolute_clean(path)
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.resolve() != path:
        raise InventoryError(f"inventory membership directory is not canonical: {path}")
    payload_size, membership_digest = directory_membership(path)
    value = ("M", payload_size, membership_digest)
    prior = records.get(path)
    if prior is not None and prior != value:
        if prior[0] == "D":
            records[path] = value
            return
        raise InventoryError(f"conflicting inventory membership directory: {path}")
    records[path] = value


def add_directory_graph(
    records: dict[Path, tuple[str, int, str]], root: Path, *,
    prune: tuple[str, ...] = ("__pycache__",),
) -> None:
    root = ensure_absolute_clean(root)
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or root.resolve() != root:
        raise InventoryError(f"inventory graph root is not canonical: {root}")
    pending = [root]
    visited: set[Path] = set()
    while pending:
        directory = pending.pop()
        if directory in visited:
            raise InventoryError(f"inventory directory graph cycle: {directory}")
        visited.add(directory)
        add_membership_directory(records, directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                candidate = ensure_absolute_clean(directory / entry.name)
                member = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(member.st_mode):
                    if entry.name not in prune:
                        pending.append(candidate)
                elif stat.S_ISLNK(member.st_mode):
                    if candidate not in REVIEWED_TREE_SYMLINKS:
                        raise InventoryError(
                            f"unsupported inventory graph symlink: {candidate}"
                        )
                    resolved = add_symlink_chain(records, candidate)
                    terminal = resolved.lstat()
                    if not stat.S_ISREG(terminal.st_mode):
                        raise InventoryError(
                            "inventory directory graph symlink does not end "
                            f"at a regular file: {candidate}"
                        )
                    add_regular(records, resolved)
                elif not stat.S_ISREG(member.st_mode):
                    raise InventoryError(
                        f"unsupported inventory graph member: {candidate}"
                    )


def add_regular(
    records: dict[Path, tuple[str, int, str]],
    path: Path,
    *,
    kind: str = "F",
) -> None:
    path = ensure_absolute_clean(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.resolve() != path:
        raise InventoryError(f"inventory file is not canonical: {path}")
    data = path.read_bytes()
    value = (kind, len(data), digest(data))
    prior = records.get(path)
    if prior is not None and prior != value:
        raise InventoryError(f"conflicting inventory file: {path}")
    records[path] = value


def add_symlink_chain(
    records: dict[Path, tuple[str, int, str]],
    path: Path,
    *,
    first_kind: str = "L",
) -> Path:
    current = ensure_absolute_clean(path)
    kind = first_kind
    visited: set[Path] = set()
    while current.is_symlink():
        if current in visited:
            raise InventoryError(f"inventory symlink cycle: {current}")
        visited.add(current)
        target = os.readlink(current).encode("utf-8")
        if current.parent not in records:
            add_directory(records, current.parent)
        value = (kind, len(target), digest(target))
        prior = records.get(current)
        if prior is not None and prior != value:
            raise InventoryError(f"conflicting inventory symlink: {current}")
        records[current] = value
        decoded = os.fsdecode(target)
        current = ensure_absolute_clean(
            Path(decoded)
            if decoded.startswith("/")
            else current.parent / decoded
        )
        current = Path(os.path.normpath(current))
        kind = "L"
    return current


def add_tree(
    records: dict[Path, tuple[str, int, str]],
    root: Path,
    *,
    suffixes: tuple[str, ...] | None = None,
) -> None:
    root = root.resolve()
    if not root.is_dir():
        raise InventoryError(f"inventory tree is absent: {root}")
    for candidate in sorted(root.rglob("*")):
        relative = candidate.relative_to(root)
        if (
            "__pycache__" in relative.parts
            or "site-packages" in relative.parts
            or candidate.suffix == ".pyc"
        ):
            continue
        if suffixes is not None and not any(
            candidate.name.endswith(suffix) for suffix in suffixes
        ):
            continue
        metadata = candidate.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            resolved = add_symlink_chain(records, candidate)
            add_regular(records, resolved)
        elif stat.S_ISREG(metadata.st_mode):
            add_regular(records, candidate)


def build_inventory() -> str:
    records: dict[Path, tuple[str, int, str]] = {}
    alias = REPO / ".venv/bin/python3"
    resolved_python = add_symlink_chain(records, alias, first_kind="A")
    if resolved_python.resolve() != PYTHON:
        raise InventoryError(
            f"repository Python resolves to {resolved_python}, expected {PYTHON}"
        )
    add_regular(records, PYTHON, kind="E")
    add_regular(records, REPO / ".venv/pyvenv.cfg")
    add_membership_directory(records, REPO / ".venv")
    add_membership_directory(records, REPO / "scripts")
    add_membership_directory(records, BASE)
    add_membership_directory(records, BASE / "lib")
    for relative in RUNTIME_SOURCES:
        add_regular(records, REPO / relative)
    add_directory_graph(records, STDLIB, prune=("__pycache__", "site-packages"))
    add_tree(
        records,
        STDLIB,
        suffixes=(".py", ".so", ".dylib", ".dll"),
    )
    version_zip = BASE / "lib/python310.zip"
    if version_zip.exists() or version_zip.is_symlink():
        raise InventoryError(f"default startup ZIP path must be absent: {version_zip}")
    add_directory(records, version_zip.parent)
    records[version_zip] = ("N", 0, EMPTY_SHA256)
    site_packages = REPO / ".venv/lib/python3.10/site-packages"
    add_directory_graph(records, site_packages / "desmume")
    add_directory_graph(records, site_packages / "PIL")
    add_tree(records, site_packages / "desmume")
    add_tree(records, site_packages / "PIL")
    for path in EXTRA_NATIVE:
        add_regular(records, path.resolve())
    lines = [HEADER]
    for path in sorted(records, key=lambda item: str(item).encode("utf-8")):
        kind, size, sha256 = records[path]
        lines.append(f"{kind}\t{size}\t{sha256}\t{path}\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "scripts/summary_move_relearn_native_inventory.txt",
    )
    arguments = parser.parse_args()
    output = ensure_absolute_clean(arguments.output)
    rendered = build_inventory().encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    print(
        f"{output}\t{len(rendered)}\t{hashlib.sha256(rendered).hexdigest()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
