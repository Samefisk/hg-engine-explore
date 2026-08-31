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
import tempfile
import threading
from typing import Any, Mapping


_BUILD_LOCK = threading.Lock()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sources(root: Path) -> tuple[Path, ...]:
    return (
        root / "lib/overworld/overworld_behavior_resolver.c",
        root
        / "tools/overworld-viewer-v2/native/overworld_behavior_resolver_main.c",
        root / "data/OverworldWildBehaviorData.c",
        root / "data/generated/overworld_wild_roof_catalog.inc",
        root / "include/config.h",
        root / "include/constants/species.h",
        root / "include/constants/buttons.h",
        root / "include/debug.h",
        root / "include/io_reg.h",
        root / "include/types.h",
        root / "include/overworld_behavior_resolver.h",
        root / "include/overworld_wild_behavior_data.h",
        root
        / "include/constants/generated/overworld_wild_roof_catalog_counts.h",
        Path(__file__).resolve(),
    )


def build(root: Path | None = None, *, force: bool = False) -> Path:
    """Return a current host executable, compiling it when required."""

    root = (root or _repo_root()).resolve()
    output = root / "build/overworld_behavior_resolver_host"
    sources = _sources(root)
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
            command = compiler + [
                "-std=c99",
                "-O2",
                "-Wall",
                "-Wextra",
                "-DOVERWORLD_BEHAVIOR_HOST",
                "-I",
                str(root / "include"),
                str(sources[0]),
                str(sources[1]),
                str(sources[2]),
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
        "--condition-terrain-mask",
        str(request.get("conditionTerrainMask", 0)),
        "--forced-override-mask",
        str(request.get("forcedOverrideMask", 0)),
        "--behavior-class",
        str(behavior_class),
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
