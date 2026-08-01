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
HEADER = "summary-move-relearn-native-bootstrap-inventory-v1\n"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
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


class InventoryError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_absolute_clean(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    if "\t" in str(absolute) or "\n" in str(absolute):
        raise InventoryError(f"inventory path contains a delimiter: {absolute}")
    return absolute


def add_directory(records: dict[Path, tuple[str, int, str]], path: Path) -> None:
    path = ensure_absolute_clean(path)
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.resolve() != path:
        raise InventoryError(f"inventory directory is not canonical: {path}")
    prior = records.get(path)
    value = ("D", 0, EMPTY_SHA256)
    if prior is not None and prior != value:
        raise InventoryError(f"conflicting inventory directory: {path}")
    records[path] = value


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
    for relative in RUNTIME_SOURCES:
        add_regular(records, REPO / relative)
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
