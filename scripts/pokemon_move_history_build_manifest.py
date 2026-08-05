#!/usr/bin/env python3
"""Seal and verify task-3 build provenance with content hashes."""

from __future__ import annotations

import sys


_NATIVE_BOOTSTRAP_PROTOCOL = "summary-move-relearn-native-bootstrap-v1"
_NATIVE_BOOTSTRAP_READY = b"SUMMARY_MOVE_RELEARN_PYTHON_READY_V1\n"
_NATIVE_BOOTSTRAP_GO = b"SUMMARY_MOVE_RELEARN_NATIVE_GO_V1\n"


def _native_bootstrap_gate() -> dict[str, str]:
    if __name__ != "__main__":
        return {}
    binding = any(
        argument == "--bind-runtime"
        or argument.startswith("--bind-runtime=")
        or argument == "--require-bound-runtime"
        for argument in sys.argv[1:]
    )
    import posix

    environment = posix.environ
    present = environment.get(
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_PROTOCOL"
    ) == _NATIVE_BOOTSTRAP_PROTOCOL.encode("ascii")
    if not binding and not present:
        return {}
    if not present:
        raise SystemExit(
            "runtime manifest binding requires the authenticated native bootstrap"
        )
    try:
        ready_fd = int(
            environment[b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_READY_FD"].decode(
                "ascii"
            )
        )
        go_fd = int(
            environment[b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_GO_FD"].decode(
                "ascii"
            )
        )
    except (KeyError, ValueError, UnicodeDecodeError) as error:
        raise SystemExit("native bootstrap handshake is malformed") from error
    if ready_fd < 3 or go_fd < 3 or ready_fd == go_fd:
        raise SystemExit("native bootstrap handshake descriptors are invalid")
    if posix.write(ready_fd, _NATIVE_BOOTSTRAP_READY) != len(
        _NATIVE_BOOTSTRAP_READY
    ):
        raise SystemExit("native bootstrap readiness write was incomplete")
    received = b""
    while len(received) < len(_NATIVE_BOOTSTRAP_GO):
        chunk = posix.read(go_fd, len(_NATIVE_BOOTSTRAP_GO) - len(received))
        if not chunk:
            break
        received += chunk
    posix.close(ready_fd)
    posix.close(go_fd)
    if received != _NATIVE_BOOTSTRAP_GO:
        raise SystemExit("native bootstrap did not release Python execution")
    keys = (
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_PATH",
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256",
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_PATH",
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_SHA256",
    )
    try:
        return {
            key.decode("ascii"): environment[key].decode("utf-8")
            for key in keys
        }
    except (KeyError, UnicodeDecodeError) as error:
        raise SystemExit("native bootstrap authentication record is absent") from error


NATIVE_BOOTSTRAP_AUTHENTICATION = _native_bootstrap_gate()


def _isolated_startup_sys_path() -> tuple[str, str, str]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    zip_version = f"python{sys.version_info.major}{sys.version_info.minor}.zip"
    library = sys.base_prefix + "/lib/" + version
    return (
        sys.base_prefix + "/lib/" + zip_version,
        library,
        library + "/lib-dynload",
    )


def _expected_isolated_sys_path() -> tuple[str, str]:
    return _isolated_startup_sys_path()[1:]


if (
    sys.flags.isolated == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_site == 1
    and sys.dont_write_bytecode
    and sys.pycache_prefix == "/dev/null"
    and "site" not in sys.modules
    and tuple(sys.path) == _isolated_startup_sys_path()
):
    sys.path[:] = _expected_isolated_sys_path()
    _external = sys.modules["_frozen_importlib_external"]
    sys.path_hooks[:] = [
        _external.FileFinder.path_hook(
            (_external.SourceFileLoader, _external.SOURCE_SUFFIXES),
            (_external.ExtensionFileLoader, _external.EXTENSION_SUFFIXES),
        )
    ]
    sys.path_importer_cache.clear()
    del _external


def _isolated_startup_ok() -> bool:
    return (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and "site" not in sys.modules
        and tuple(sys.path) == _expected_isolated_sys_path()
    )


if __name__ == "__main__" and not _isolated_startup_ok():
    raise SystemExit(
        "move-history build manifest failed: start exact repository Python "
        "with -I -S -B -X pycache_prefix=/dev/null"
    )


_PINNED_STAGE_ZERO_LAUNCHER_SHA256 = (
    "e8626576a6b204808b93aca1a3bb8bc86622c158fc37adeb4d3dc36d2e591e94"
)
_PINNED_STAGE_ZERO_PYTHON = {
    "darwin": {
        "repo": None,
        "entry": None,
        "executable": {
            "path": "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3.10",
            "size": 152624,
            "sha256": "8a2727d72c1c94360762724bc333040776f84b49830008e4ca5f45d3d79553c8",
        },
        "shared_runtime": {
            "path": "/Library/Frameworks/Python.framework/Versions/3.10/Python",
            "size": 9762928,
            "sha256": "5f6fad7e987aba159bd81251413697f7bf6258a46a54641b4ee93c7447dc5672",
        },
        "pyvenv_cfg": {
            "size": 71,
            "sha256": "db6c8a96f25493eda9f74f23f0b5f248a8b50a5b469b15c5ee7313875b416364",
        },
        "stdlib": {
            "root": "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10",
            "files": 1788,
            "size": 51435256,
            "sha256": "4cebc4dbc8ee10c816bc500e0e95c24448657727ef065c66650d0627ebe26229",
        },
    },
    "linux": {
        "repo": "/hg-engine",
        "entry": "/tmp/hg-engine-venv/bin/python3",
        "executable": {
            "path": "/usr/bin/python3.10",
            "size": 5672072,
            "sha256": "03bb5d246e83c44204ef38044b062fdc46c2835881874e763c44c48b4304c490",
        },
        "shared_runtime": None,
        "pyvenv_cfg": {
            "size": 71,
            "sha256": "db6c8a96f25493eda9f74f23f0b5f248a8b50a5b469b15c5ee7313875b416364",
        },
        "stdlib": {
            "root": "/usr/lib/python3.10",
            "files": 696,
            "size": 13697749,
            "sha256": "24390712683ee2a599ec3140ad90abd246b8efee9c4782a2deb8f24a9a70d312",
        },
    },
}


def _pinned_stage_zero_sha256(data: bytes) -> str:
    initial = [
        0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
        0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
    ]
    rounds = (
        0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5, 0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
        0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3, 0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
        0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC, 0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
        0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7, 0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
        0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13, 0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
        0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3, 0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
        0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5, 0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
        0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208, 0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
    )
    original_length = len(data)
    data += b"\x80" + bytes((55 - original_length) % 64)
    data += (original_length * 8).to_bytes(8, "big")
    for offset in range(0, len(data), 64):
        block = data[offset:offset + 64]
        words = [int.from_bytes(block[index:index + 4], "big") for index in range(0, 64, 4)]
        for index in range(16, 64):
            x, y = words[index - 15], words[index - 2]
            s0 = ((x >> 7) | (x << 25)) ^ ((x >> 18) | (x << 14)) ^ (x >> 3)
            s1 = ((y >> 17) | (y << 15)) ^ ((y >> 19) | (y << 13)) ^ (y >> 10)
            words.append((words[index - 16] + s0 + words[index - 7] + s1) & 0xFFFFFFFF)
        a, b, c, d, e, f, g, h = initial
        for index in range(64):
            s1 = ((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7))
            choose = (e & f) ^ ((~e) & g)
            t1 = (h + s1 + choose + rounds[index] + words[index]) & 0xFFFFFFFF
            s0 = ((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10))
            t2 = (s0 + ((a & b) ^ (a & c) ^ (b & c))) & 0xFFFFFFFF
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & 0xFFFFFFFF, c, b, a, (t1 + t2) & 0xFFFFFFFF
        initial = [(old + new) & 0xFFFFFFFF for old, new in zip(initial, (a, b, c, d, e, f, g, h))]
    return b"".join(value.to_bytes(4, "big") for value in initial).hex()


if __name__ == "__main__" and any(
    argument == mode or argument.startswith(mode + "=")
    for mode in ("--bind-runtime", "--require-bound-runtime")
    for argument in sys.argv[1:]
):
    import posix

    script_path = __file__ if __file__.startswith("/") else posix.getcwd() + "/" + __file__
    repo_path = script_path.rsplit("/scripts/", 1)[0]
    launcher_path = repo_path + "/scripts/launch_summary_move_relearn_runtime.py"
    with open(launcher_path, "rb") as stage_zero_stream:
        stage_zero_source = stage_zero_stream.read()
    if _pinned_stage_zero_sha256(stage_zero_source) != _PINNED_STAGE_ZERO_LAUNCHER_SHA256:
        raise SystemExit("move-history build manifest failed: pinned stage-zero launcher differs")
    stage_zero_prefix = stage_zero_source.split(b"\nimport os\n", 1)
    if len(stage_zero_prefix) != 2:
        raise SystemExit("move-history build manifest failed: stage-zero boundary is absent")
    stage_zero_namespace = {"__name__": "manifest_binder_stage_zero", "__file__": launcher_path}
    exec(compile(stage_zero_prefix[0], launcher_path, "exec", dont_inherit=True, optimize=0), stage_zero_namespace)
    file_record_zero = stage_zero_namespace["_stage_zero_file_record"]
    tree_record_zero = stage_zero_namespace["_stage_zero_tree_record"]
    pinned = _PINNED_STAGE_ZERO_PYTHON.get(sys.platform)
    if pinned is None:
        raise SystemExit("move-history build manifest failed: unsupported pinned platform")
    expected_repo = pinned["repo"] if pinned["repo"] is not None else repo_path
    expected_entry = pinned["entry"] if pinned["entry"] is not None else repo_path + "/.venv/bin/python3"
    if repo_path != expected_repo or sys.executable != expected_entry:
        raise SystemExit("move-history build manifest failed: pinned Python entry differs")
    if file_record_zero(pinned["executable"]["path"]) != {key: pinned["executable"][key] for key in ("size", "sha256")}:
        raise SystemExit("move-history build manifest failed: pinned Python executable differs")
    if pinned["shared_runtime"] is not None and file_record_zero(pinned["shared_runtime"]["path"]) != {key: pinned["shared_runtime"][key] for key in ("size", "sha256")}:
        raise SystemExit("move-history build manifest failed: pinned Python runtime differs")
    pyvenv_record = file_record_zero(expected_entry.rsplit("/bin/", 1)[0] + "/pyvenv.cfg")
    if pyvenv_record != pinned["pyvenv_cfg"]:
        raise SystemExit("move-history build manifest failed: pinned pyvenv.cfg differs")
    if tree_record_zero(pinned["stdlib"]["root"]) != pinned["stdlib"]:
        raise SystemExit("move-history build manifest failed: pinned stdlib differs")

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import struct
import subprocess
import sysconfig
import tempfile
import types
import unicodedata
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parents[1]
SCHEMA = "pokemon-move-history-capture-build-v1"
RUNTIME_ENVIRONMENT_SCHEMA = "summary-move-relearn-runtime-environment-v1"
PACKAGED_ROM_LOGICAL_PATH = "@packaged-rom"
RUNTIME_LAUNCHER_INPUT = "scripts/launch_summary_move_relearn_runtime.py"
RUNTIME_RETAINED_SOURCE_INPUTS = (
    "scripts/pokemon_move_history_build_manifest.py",
    RUNTIME_LAUNCHER_INPUT,
    "scripts/verify_summary_move_relearn_runtime.py",
    "scripts/headless-overworld-test.py",
    "scripts/verify_pokemon_move_history_party_integrity.py",
    "scripts/summary_move_relearn_protected_spawn.py",
)
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
    "build/pokemon_storage_system.d",
    "build/individual/GetMonEvolutionInternal.d",
    "build/field/script_commands.d",
    "build/party_menu.d",
    "build/overworld_wild_spawns.d",
    "build/save.d",
    "build/overlay.d",
    "build/pokemon_move_history_overlay/pokemon_move_history.d",
    "build/pokemon_move_history_overlay/pokemon_move_relearn.d",
    "build/pokemon_move_history_task6_overlay/pokemon_move_history_task6.d",
    "build/summary_move_relearn_overlay/summary_move_relearn.d",
)
FIXED_INPUTS = (
    "Makefile",
    "bytereplacement",
    "docker-makerom.cmd",
    "data/text/302.txt",
    "hooks",
    "overlays.mk",
    "rom.nds",
    "rom.ld",
    "rom_gen.ld",
    "armips/global.s",
    "armips/include/macros.s",
    "armips/asm/pokemon_move_history_capture.s",
    "asm/other_hook.s",
    "asm/pokemon_move_history_overlay/entry.s",
    "asm/pokemon_move_history_overlay/thumb_help.s",
    "asm/pokemon_move_history_task6_overlay/entry.s",
    "asm/summary_move_relearn_overlay/entry.s",
    "src/pokemon_move_history_overlay/linker.ld",
    "src/pokemon_move_history_task6_overlay/linker.ld",
    "src/summary_move_relearn_overlay/linker.ld",
    "src/field/linker.ld",
    "scripts/generate_armips_symbols.py",
    "scripts/build_move_relearn_parents.py",
    "scripts/generate_ld.py",
    "scripts/make.py",
    "scripts/verify_pokemon_move_history_capture.py",
    "scripts/verify_pokemon_move_history.py",
    "scripts/verify_move_relearn_candidates.py",
    "scripts/verify_summary_move_relearn.py",
    "scripts/build_summary_move_relearn_native_bootstrap.sh",
    "scripts/generate_summary_move_relearn_native_inventory.py",
    "scripts/summary_move_relearn_native_bootstrap.c",
    "scripts/summary_move_relearn_protected_spawn.swift",
    "scripts/summary_move_relearn_native_inventory.txt",
    *RUNTIME_RETAINED_SOURCE_INPUTS,
    "documentation/summary_move_relearn_task6.md",
)
OUTPUTS = {
    "core_linked": "build/linked.o",
    "core_binary": "build/output.bin",
    "pokemon_object": "build/pokemon.o",
    "pokemon_storage_object": "build/pokemon_storage_system.o",
    "evolution_object": "build/individual/GetMonEvolutionInternal.o",
    "field_script_commands_object": "build/field/script_commands.o",
    "field_linked": "build/field_linked.o",
    "field_binary": "build/output_field.bin",
    "party_menu_object": "build/party_menu.o",
    "save_object": "build/save.o",
    "history_object":
        "build/pokemon_move_history_overlay/pokemon_move_history.o",
    "relearn_object":
        "build/pokemon_move_history_overlay/pokemon_move_relearn.o",
    "entry_object": "build/pokemon_move_history_overlay/entry.o",
    "thumb_help_object": "build/pokemon_move_history_overlay/thumb_help.o",
    "task6_object":
        "build/pokemon_move_history_task6_overlay/pokemon_move_history_task6.o",
    "task6_entry_object":
        "build/pokemon_move_history_task6_overlay/entry.o",
    "overlay_object": "build/overlay.o",
    "other_hook_object": "build/other_hook.o",
    "history_linked": "build/pokemon_move_history_overlay_linked.o",
    "history_binary": "build/output_pokemon_move_history_overlay.bin",
    "task6_linked":
        "build/pokemon_move_history_task6_overlay_linked.o",
    "task6_binary":
        "build/output_pokemon_move_history_task6_overlay.bin",
    "summary_object":
        "build/summary_move_relearn_overlay/summary_move_relearn.o",
    "summary_entry_object":
        "build/summary_move_relearn_overlay/entry.o",
    "summary_linked": "build/summary_move_relearn_overlay_linked.o",
    "summary_binary": "build/output_summary_move_relearn_overlay.bin",
    "patched_arm9": "base/arm9.bin",
    "overlay_table": "base/overarm9.bin",
    "patched_overlay12": "base/overlay/overlay_0012.bin",
    "patched_overlay23": "base/overlay/overlay_0023.bin",
    "patched_overlay65": "base/overlay/overlay_0065.bin",
    "patched_overlay68": "base/overlay/overlay_0068.bin",
    "patched_overlay70": "base/overlay/overlay_0070.bin",
    "patched_overlay112": "base/overlay/overlay_0112.bin",
    "patched_overlay129": "base/overlay/overlay_0129.bin",
    "patched_overlay131": "base/overlay/overlay_0131.bin",
    "patched_overlay153": "base/overlay/overlay_0153.bin",
    "patched_overlay154": "base/overlay/overlay_0154.bin",
    "patched_overlay155": "base/overlay/overlay_0155.bin",
}


class ManifestError(ValueError):
    """The manifest does not describe the current build generation."""


RUNTIME_OS_TRUST_ROOTS = {
    "darwin": (
        "/System/Library",
        "/usr/lib",
        "/System/Volumes/Preboot/Cryptexes/OS/System/Library",
        "/System/Volumes/Preboot/Cryptexes/OS/usr/lib",
    ),
    "linux": ("/lib", "/lib64", "/usr/lib", "/usr/lib64"),
}
RUNTIME_MODULE_RELATIVES = (
    "desmume/__init__.py",
    "desmume/i18n_util.py",
    "desmume/controls.py",
    "desmume/emulator.py",
)
RUNTIME_STARTUP_MODULES = (
    "abc",
    "codecs",
    "encodings",
    "encodings.aliases",
    "encodings.utf_8",
    "io",
)
RUNTIME_NATIVE_SUFFIXES = (".dylib", ".dll", ".so")
NATIVE_BOOTSTRAP_RELATIVE = (
    "build/summary_move_relearn_native/summary_move_relearn_native_bootstrap"
)
NATIVE_BOOTSTRAP_SOURCE_RELATIVE = (
    "scripts/summary_move_relearn_native_bootstrap.c"
)
NATIVE_BOOTSTRAP_INVENTORY_RELATIVE = (
    "scripts/summary_move_relearn_native_inventory.txt"
)
NATIVE_BOOTSTRAP_BUILD_RELATIVE = (
    "scripts/build_summary_move_relearn_native_bootstrap.sh"
)
PROTECTED_SPAWN_SOURCE_RELATIVE = (
    "scripts/summary_move_relearn_protected_spawn.swift"
)
PROTECTED_SPAWN_SYSTEM_CONTROLLER = Path("/usr/bin/swift")
NATIVE_BOOTSTRAP_COMPILER = Path(
    "/Library/Developer/CommandLineTools/usr/bin/clang"
)


def unbound_runtime_environment() -> dict[str, Any]:
    return {
        "schema": RUNTIME_ENVIRONMENT_SCHEMA,
        "status": "unbound",
    }


def _canonical_runtime_path(path: Path, label: str) -> Path:
    absolute = Path(os.path.abspath(path))
    resolved = Path(os.path.realpath(absolute))
    if not resolved.is_file():
        raise ManifestError(f"runtime {label} is absent: {resolved}")
    return resolved


def runtime_file_record(path: Path, label: str) -> dict[str, Any]:
    resolved = _canonical_runtime_path(path, label)
    return {"path": str(resolved), **file_record(resolved)}


def _runtime_tree_record(
    root: Path,
    label: str,
    *,
    suffixes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    resolved_root = Path(os.path.realpath(os.path.abspath(root)))
    if not resolved_root.is_dir():
        raise ManifestError(f"runtime {label} root is absent: {resolved_root}")
    digest = hashlib.sha256()
    count = 0
    size = 0
    for candidate in sorted(resolved_root.rglob("*")):
        relative = candidate.relative_to(resolved_root).as_posix()
        parts = candidate.relative_to(resolved_root).parts
        if (
            "__pycache__" in parts
            or "site-packages" in parts
            or candidate.suffix == ".pyc"
        ):
            continue
        if suffixes is not None and not any(
            candidate.name.endswith(suffix) for suffix in suffixes
        ):
            continue
        metadata = candidate.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            target = os.readlink(candidate).encode("utf-8")
            digest.update(b"L\0" + relative.encode("utf-8") + b"\0")
            digest.update(len(target).to_bytes(8, "little") + target)
            count += 1
            size += len(target)
        elif stat.S_ISREG(metadata.st_mode):
            data = candidate.read_bytes()
            digest.update(b"F\0" + relative.encode("utf-8") + b"\0")
            digest.update(len(data).to_bytes(8, "little"))
            digest.update(hashlib.sha256(data).digest())
            count += 1
            size += len(data)
    if count == 0:
        raise ManifestError(f"runtime {label} closure is empty")
    return {
        "root": str(resolved_root),
        "files": count,
        "size": size,
        "sha256": digest.hexdigest(),
    }


def _runtime_package_root(package: str) -> Path:
    candidates: set[Path] = set()
    for entry in sys.path:
        root = Path(entry if entry else os.getcwd())
        candidate = root / package
        if candidate.is_dir():
            candidates.add(Path(os.path.realpath(candidate)))
    venv_root = Path(os.path.abspath(sys.executable)).parent.parent
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for library in ("lib", "lib64"):
        candidate = venv_root / library / version / "site-packages" / package
        if candidate.is_dir():
            candidates.add(Path(os.path.realpath(candidate)))
    if len(candidates) != 1:
        raise ManifestError(
            f"runtime package {package} does not resolve uniquely: "
            f"{sorted(str(path) for path in candidates)}"
        )
    return next(iter(candidates))


def _python_runtime_binary() -> Path:
    if sys.platform == "darwin":
        candidate = Path(sys.base_prefix) / "Python"
    else:
        library = sysconfig.get_config_var("LDLIBRARY")
        directory = sysconfig.get_config_var("LIBDIR")
        if not isinstance(library, str) or not isinstance(directory, str):
            raise ManifestError("Python shared runtime path is unavailable")
        candidate = Path(directory) / library
    return _canonical_runtime_path(candidate, "Python shared runtime")


def _native_records(roots: tuple[Path, ...]) -> list[dict[str, Any]]:
    paths: set[Path] = set()
    for root in roots:
        for candidate in root.rglob("*"):
            if candidate.is_file() and any(
                candidate.name.endswith(suffix)
                for suffix in RUNTIME_NATIVE_SUFFIXES
            ):
                paths.add(Path(os.path.realpath(candidate)))
    return [
        runtime_file_record(path, "mutable native closure")
        for path in sorted(paths)
    ]


def _loaded_native_paths() -> set[Path]:
    paths: set[Path] = set()
    if sys.platform == "darwin":
        process = ctypes.CDLL(None)
        count = process._dyld_image_count
        count.argtypes = []
        count.restype = ctypes.c_uint32
        name = process._dyld_get_image_name
        name.argtypes = [ctypes.c_uint32]
        name.restype = ctypes.c_char_p
        for index in range(count()):
            raw = name(index)
            if raw:
                candidate = Path(os.path.realpath(os.fsdecode(raw)))
                if candidate.is_file():
                    paths.add(candidate)
    elif sys.platform.startswith("linux"):
        maps = Path("/proc/self/maps")
        if not maps.is_file():
            raise ManifestError("Linux loaded-image map is unavailable")
        for line in maps.read_text().splitlines():
            fields = line.split(None, 5)
            if len(fields) == 6 and fields[5].startswith("/"):
                candidate = Path(os.path.realpath(fields[5]))
                if candidate.is_file():
                    paths.add(candidate)
    else:
        raise ManifestError(
            f"unsupported runtime loaded-image platform: {sys.platform}"
        )
    return paths


def _under_runtime_root(path: Path, roots: tuple[str, ...]) -> bool:
    text = os.fspath(path)
    return any(text == root or text.startswith(root + os.sep) for root in roots)


def _loader_name(loader: object) -> str:
    if loader is None:
        return "None"
    loader_type = loader if isinstance(loader, type) else type(loader)
    return loader_type.__module__ + "." + loader_type.__qualname__


def _validate_binding_modules(stdlib_root: Path) -> None:
    exact_sources = {
        (REPO / relative).resolve()
        for relative in RUNTIME_RETAINED_SOURCE_INPUTS
    }
    package_roots = tuple(
        _runtime_package_root(package) for package in ("desmume", "PIL")
    )
    forbidden = {"SourcelessFileLoader", "zipimporter"}
    for name, module in sorted(sys.modules.items()):
        if not isinstance(module, types.ModuleType):
            continue
        spec = getattr(module, "__spec__", None)
        spec_origin = getattr(spec, "origin", None)
        file_origin = getattr(module, "__file__", None)
        loader_name = _loader_name(getattr(module, "__loader__", None))
        short_loader = loader_name.rsplit(".", 1)[-1]
        if short_loader in forbidden:
            raise ManifestError(
                f"runtime binder loaded forbidden Python loader: {name}"
            )
        if spec_origin in ("built-in", "frozen"):
            continue
        origin = spec_origin if isinstance(spec_origin, str) else file_origin
        if not isinstance(origin, str) or not origin:
            raise ManifestError(
                f"runtime binder module has no authenticated origin: {name}"
            )
        canonical = Path(os.path.realpath(os.path.abspath(origin)))
        if canonical != Path(origin) or not canonical.is_file():
            raise ManifestError(
                f"runtime binder module origin is not canonical: {name}"
            )
        if isinstance(file_origin, str) and Path(
            os.path.realpath(os.path.abspath(file_origin))
        ) != canonical:
            raise ManifestError(
                f"runtime binder module origins differ: {name}"
            )
        if short_loader == "SourceFileLoader":
            allowed = (
                canonical.suffix == ".py"
                and (
                    _under_runtime_root(canonical, (str(stdlib_root),))
                    or canonical in exact_sources
                )
            )
        elif short_loader == "ExtensionFileLoader":
            allowed = (
                _under_runtime_root(canonical, (str(stdlib_root),))
                or any(
                    _under_runtime_root(canonical, (str(root),))
                    for root in package_roots
                )
            )
        elif short_loader in {"RetainedSourceLoader", "RetainedPackageLoader"}:
            allowed = (
                canonical.suffix == ".py"
                and (
                    canonical in exact_sources
                    or any(
                        _under_runtime_root(canonical, (str(root),))
                        for root in package_roots
                    )
                )
            )
        else:
            allowed = False
        if not allowed:
            raise ManifestError(
                f"runtime binder module loader/origin is unsealed: "
                f"{name}: {loader_name}: {canonical}"
            )


def _codesign_metadata(path: Path, label: str) -> dict[str, str]:
    completed = subprocess.run(
        ["/usr/bin/codesign", "-d", "--verbose=4", str(path)],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        raise ManifestError(f"{label} code signature is invalid")
    fields: dict[str, str] = {}
    for line in output.splitlines():
        code_directory = re.search(r"\bflags=(0x[0-9a-f]+\([^)]*\))", line)
        if line.startswith("CodeDirectory ") and code_directory is not None:
            fields["CodeDirectoryFlags"] = code_directory.group(1)
        if line.startswith("Runtime Version="):
            fields["RuntimeVersion"] = line.split("=", 1)[1]
        if "=" in line:
            key, value = line.split("=", 1)
            if key in {
                "Identifier",
                "CDHash",
                "Signature",
                "TeamIdentifier",
            }:
                fields[key] = value
    if (
        not fields.get("Identifier")
        or not fields.get("CDHash")
        or not fields.get("CodeDirectoryFlags")
    ):
        raise ManifestError(f"{label} code-sign identity is incomplete")
    return fields


def _code_signature_provenance(path: Path, label: str) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 32 or struct.unpack_from("<I", data, 0)[0] != 0xFEEDFACF:
        raise ManifestError(f"{label} is not the exact thin 64-bit Mach-O")
    command_count = struct.unpack_from("<I", data, 16)[0]
    command_bytes = struct.unpack_from("<I", data, 20)[0]
    cursor = 32
    command_end = cursor + command_bytes
    if command_end > len(data):
        raise ManifestError(f"{label} load commands are truncated")
    signature_ranges: list[tuple[int, int]] = []
    for _ in range(command_count):
        if cursor + 8 > command_end:
            raise ManifestError(f"{label} load command header is truncated")
        command, size = struct.unpack_from("<II", data, cursor)
        if size < 8 or cursor + size > command_end:
            raise ManifestError(f"{label} load command is malformed")
        if command == 0x1D:
            if size != 16:
                raise ManifestError(f"{label} code-sign command is malformed")
            signature_ranges.append(struct.unpack_from("<II", data, cursor + 8))
        cursor += size
    if cursor != command_end or len(signature_ranges) != 1:
        raise ManifestError(f"{label} code-sign command count differs")
    signature_offset, signature_size = signature_ranges[0]
    if (
        signature_size < 12
        or signature_offset > len(data)
        or signature_size > len(data) - signature_offset
    ):
        raise ManifestError(f"{label} code signature is out of bounds")
    allocation = data[signature_offset : signature_offset + signature_size]
    magic, logical_size, slot_count = struct.unpack_from(">III", allocation, 0)
    if (
        magic != 0xFADE0CC0
        or logical_size < 12 + slot_count * 8
        or logical_size > len(allocation)
    ):
        raise ManifestError(f"{label} signature superblob is malformed")
    logical = allocation[:logical_size]
    padding = allocation[logical_size:]
    if any(padding):
        raise ManifestError(f"{label} signature allocation padding is nonzero")
    slots: list[dict[str, object]] = []
    slot_types: list[int] = []
    occupied: list[tuple[int, int]] = []
    code_directory: bytes | None = None
    for index in range(slot_count):
        slot_type, offset = struct.unpack_from(">II", logical, 12 + index * 8)
        if offset < 12 + slot_count * 8 or offset + 8 > logical_size:
            raise ManifestError(f"{label} signature slot offset is malformed")
        blob_magic, blob_size = struct.unpack_from(">II", logical, offset)
        if blob_size < 8 or blob_size > logical_size - offset:
            raise ManifestError(f"{label} signature slot is truncated")
        if slot_type in slot_types:
            raise ManifestError(f"{label} signature slot is duplicated")
        for start, end in occupied:
            if offset < end and start < offset + blob_size:
                raise ManifestError(f"{label} signature slots overlap")
        occupied.append((offset, offset + blob_size))
        slot_types.append(slot_type)
        blob = logical[offset : offset + blob_size]
        slots.append(
            {
                "type": slot_type,
                "magic": f"0x{blob_magic:08x}",
                "size": blob_size,
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
        )
        if slot_type == 0:
            if blob_magic != 0xFADE0C02:
                raise ManifestError(f"{label} CodeDirectory magic differs")
            code_directory = blob
    if slot_types != [0, 2, 0x10000] or code_directory is None:
        raise ManifestError(f"{label} signature slot set differs")
    entitlement_probe = subprocess.run(
        ["/usr/bin/codesign", "-d", "--entitlements", "-", str(path)],
        check=False,
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if entitlement_probe.returncode != 0 or entitlement_probe.stdout != b"":
        raise ManifestError(f"{label} entitlement dictionary is not empty")
    code_directory_sha256 = hashlib.sha256(code_directory).hexdigest()
    return {
        "schema": "summary-move-relearn-code-signature-v1",
        "slots": slots,
        "code_directory": {
            "size": len(code_directory),
            "sha256": code_directory_sha256,
        },
        "superblob": {
            "size": logical_size,
            "sha256": hashlib.sha256(logical).hexdigest(),
        },
        "allocation": {
            "size": signature_size,
            "padding_size": len(padding),
            "padding_sha256": hashlib.sha256(padding).hexdigest(),
        },
        "entitlements": {
            "policy": "exactly-empty",
            "keys": [],
            "xml_slot": False,
            "der_slot": False,
            "codesign_stdout": {
                "size": 0,
                "sha256": hashlib.sha256(b"").hexdigest(),
            },
        },
    }


def _native_bootstrap_runtime_record() -> dict[str, Any]:
    if sys.platform != "darwin":
        raise ManifestError("native runtime bootstrap is Darwin-specific")
    names = {
        "path": "SUMMARY_MOVE_RELEARN_BOOTSTRAP_PATH",
        "sha256": "SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256",
        "inventory_path": "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_PATH",
        "inventory_sha256": (
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_SHA256"
        ),
    }
    values = {key: os.environ.get(name) for key, name in names.items()}
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise ManifestError("native bootstrap authentication environment is absent")
    bootstrap_path = Path(os.path.abspath(values["path"]))
    inventory_path = Path(os.path.abspath(values["inventory_path"]))
    if bootstrap_path != REPO / NATIVE_BOOTSTRAP_RELATIVE:
        raise ManifestError("native bootstrap path differs")
    if inventory_path != REPO / NATIVE_BOOTSTRAP_INVENTORY_RELATIVE:
        raise ManifestError("native bootstrap inventory path differs")
    bootstrap_record = runtime_file_record(
        bootstrap_path, "native bootstrap binary"
    )
    inventory_record = runtime_file_record(
        inventory_path, "native bootstrap inventory"
    )
    if bootstrap_record["sha256"] != values["sha256"]:
        raise ManifestError("native bootstrap external SHA-256 pin differs")
    if inventory_record["sha256"] != values["inventory_sha256"]:
        raise ManifestError("native bootstrap compiled inventory pin differs")
    linked = subprocess.run(
        ["/usr/bin/otool", "-L", str(bootstrap_path)],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    dependency_lines = [
        line.strip() for line in linked.stdout.splitlines()[1:] if line.strip()
    ]
    if linked.returncode != 0 or len(dependency_lines) != 1 or not (
        dependency_lines[0].startswith("/usr/lib/libSystem.B.dylib ")
    ):
        raise ManifestError("native bootstrap has a non-OS runtime dependency")
    compiler = NATIVE_BOOTSTRAP_COMPILER
    compiler_version = subprocess.run(
        [str(compiler), "--version"],
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if compiler_version.returncode != 0 or not compiler_version.stdout:
        raise ManifestError("native bootstrap compiler provenance is absent")
    bootstrap_codesign = _codesign_metadata(
        bootstrap_path, "native bootstrap binary"
    )
    bootstrap_signature = _code_signature_provenance(
        bootstrap_path, "native bootstrap binary"
    )
    expected_flags = (
        "0x12b02(adhoc,hard,kill,restrict,library-validation,runtime)"
    )
    if (
        bootstrap_codesign.get("CodeDirectoryFlags") != expected_flags
        or not bootstrap_codesign.get("RuntimeVersion")
    ):
        raise ManifestError(
            "native bootstrap lacks the exact hardened/restricted launch policy"
        )
    if bootstrap_codesign.get("CDHash") != bootstrap_signature[
        "code_directory"
    ]["sha256"][:40]:
        raise ManifestError(
            "native bootstrap CodeDirectory provenance differs"
        )
    return {
        "schema": "summary-move-relearn-native-bootstrap-v1",
        "binary": bootstrap_record,
        "inventory": inventory_record,
        "source": runtime_file_record(
            REPO / NATIVE_BOOTSTRAP_SOURCE_RELATIVE,
            "native bootstrap source",
        ),
        "build_helper": runtime_file_record(
            REPO / NATIVE_BOOTSTRAP_BUILD_RELATIVE,
            "native bootstrap build helper",
        ),
        "protected_spawn_source": runtime_file_record(
            REPO / PROTECTED_SPAWN_SOURCE_RELATIVE,
            "protected spawn source",
        ),
        "protected_spawn_controller": {
            "path": str(PROTECTED_SPAWN_SYSTEM_CONTROLLER),
            "codesign": _codesign_metadata(
                PROTECTED_SPAWN_SYSTEM_CONTROLLER,
                "protected spawn system controller",
            ),
            "dynamic_code_flags": "0x22012b01",
            "primitive": (
                "POSIX_SPAWN_START_SUSPENDED then live-PID csops CDHash, "
                "code-status, and executable-path authentication before SIGCONT"
            ),
        },
        "compile": {
            "compiler_path": str(compiler),
            "compiler_version": compiler_version.stdout.splitlines()[0],
            "compiler_codesign": _codesign_metadata(
                compiler, "native bootstrap compiler"
            ),
            "command": (
                "/usr/bin/xcrun --sdk macosx clang "
                "-std=c11 -O2 -Wall -Wextra -Werror -pedantic -Wl,-no_uuid "
                "-DSMR_EXPECTED_INVENTORY_SHA256=<sealed-inventory-sha256> "
                "scripts/summary_move_relearn_native_bootstrap.c "
                "-o build/summary_move_relearn_native/"
                "summary_move_relearn_native_bootstrap"
            ),
            "codesign_command": (
                "/usr/bin/codesign --force --sign - --timestamp=none "
                "--options runtime,restrict,library,hard,kill "
                "--identifier com.samefisk.hgengine.summary-relearn-bootstrap "
                "build/summary_move_relearn_native/"
                "summary_move_relearn_native_bootstrap"
            ),
        },
        "codesign": bootstrap_codesign,
        "code_signature": bootstrap_signature,
        "external_seal": {
            "sha256": bootstrap_record["sha256"],
            "cdhash": bootstrap_codesign["CDHash"],
        },
        "linked_images": dependency_lines,
        "root_of_trust": (
            "The external publication caller supplies the reviewed bootstrap "
            "SHA-256 and CDHash. The build helper authenticates the temporary "
            "candidate and atomically published file against both pins, with "
            "strict signature, exact-empty entitlement slots, sole-libSystem "
            "linkage, and no-UUID checks repeated after publication; executable "
            "stdout is never an identity authority. Every production launch "
            "is instead made by the Apple-signed, sealed-system-volume Swift "
            "controller with POSIX_SPAWN_START_SUSPENDED. The controller "
            "validates the kernel-bound child PID's exact external CDHash, "
            "dynamic code flags, and executable path before SIGCONT; a path "
            "replacement is killed and reaped before dyld or user code. "
            "Darwin AMFI validates the "
            "ad-hoc CodeDirectory/pages and the binary self-checks the external "
            "full-file digest. Pre-main trust is limited to the kernel, dyld "
            "shared cache, and Apple-protected libSystem. Hardened runtime, "
            "restrict, library validation, hard, and kill CodeDirectory flags "
            "are enforced by dyld/AMFI before main, with an exactly empty "
            "entitlement set. The bootstrap retains "
            "and monitors the complete mutable Python/native closure until "
            "the child exits. Ad-hoc signing alone is not claimed as an "
            "identity root."
        ),
    }


def capture_runtime_environment() -> dict[str, Any]:
    if not _isolated_startup_ok():
        raise ManifestError(
            "runtime binding requires -I -S -B -X "
            "pycache_prefix=/dev/null"
        )
    expected_entry = os.path.abspath(REPO / ".venv/bin/python3")
    if os.path.abspath(sys.executable) != expected_entry:
        raise ManifestError(
            "runtime binding requires exact repository .venv/bin/python3"
        )
    if os.stat(os.devnull).st_mode & 0o170000 != 0o020000:
        raise ManifestError("runtime pycache sink is not a character device")
    platform_name = sys.platform.lower()
    trust_roots = RUNTIME_OS_TRUST_ROOTS.get(platform_name)
    if trust_roots is None:
        raise ManifestError(
            f"unsupported runtime platform for native closure: {sys.platform}"
        )
    desmume_root = _runtime_package_root("desmume")
    pil_root = _runtime_package_root("PIL")
    module_records = {
        relative: runtime_file_record(
            desmume_root.parent / relative,
            f"module {relative}",
        )
        for relative in RUNTIME_MODULE_RELATIVES
    }
    libdesmume_name = {
        "darwin": "libdesmume.dylib",
        "linux": "libdesmume.so",
    }[platform_name]
    libdesmume = desmume_root / libdesmume_name
    stdlib_root = Path(sysconfig.get_path("stdlib"))
    _validate_binding_modules(stdlib_root)
    stdlib_suffixes = (".py", ".so", ".dylib", ".dll")
    executable_entry = Path(os.path.abspath(sys.executable))
    venv_root = executable_entry.parent.parent
    venv_config = venv_root / "pyvenv.cfg"
    runtime_binary = _python_runtime_binary()
    native_roots = (desmume_root, pil_root, stdlib_root / "lib-dynload")
    absent_zip_paths = sorted(
        os.path.abspath(entry)
        for entry in sys.path
        if isinstance(entry, str) and entry.endswith(".zip")
    )
    if any(Path(path).exists() for path in absent_zip_paths):
        raise ManifestError(
            "runtime zip import path must be absent under source-only policy"
        )
    native_records = _native_records(native_roots)
    explicitly_required = {
        str(Path(record["path"])) for record in native_records
    }
    explicitly_required.add(str(runtime_binary))
    for loaded in _loaded_native_paths():
        if not _under_runtime_root(loaded, trust_roots):
            explicitly_required.add(str(loaded))
    native_records = [
        runtime_file_record(Path(path), "mutable native closure")
        for path in sorted(explicitly_required)
    ]
    return {
        "schema": RUNTIME_ENVIRONMENT_SCHEMA,
        "status": "bound",
        "native_bootstrap": _native_bootstrap_runtime_record(),
        "platform": {
            "system": platform_name,
            "machine": os.uname().machine,
            "implementation": sys.implementation.name,
            "cache_tag": sys.implementation.cache_tag,
        },
        "python": {
            "bytecode_policy": {
                "absent_zip_paths": absent_zip_paths,
                "bytecode_reads_disabled": True,
                "dont_write_bytecode": True,
                "forbidden_loaders": [
                    "SourcelessFileLoader",
                    "zipimporter",
                ],
                "ignore_environment": True,
                "isolated": True,
                "no_site": True,
                "pycache_prefix": os.devnull,
                "sys_path": list(_expected_isolated_sys_path()),
                "scope": (
                    "Interpreter startup, host binders, retained helpers, and "
                    "every acceptance child use isolated mode, ignore Python "
                    "environment configuration, skip site/.pth processing, "
                    "and restrict import lookup to the sealed stdlib paths. "
                    "Every loaded module origin and loader is authenticated; "
                    "zipimporter and sourceless bytecode are forbidden."
                ),
            },
            "entry_path": str(executable_entry),
            "executable": runtime_file_record(
                executable_entry, "Python executable"
            ),
            "shared_runtime": runtime_file_record(
                runtime_binary, "Python shared runtime"
            ),
            "pyvenv_cfg": runtime_file_record(
                venv_config, "virtual-environment configuration"
            ),
            "stdlib": _runtime_tree_record(
                stdlib_root,
                "Python standard library",
                suffixes=stdlib_suffixes,
            ),
            "startup_bootstrap": {
                "modules": {
                    name: runtime_file_record(
                        Path(sys.modules[name].__file__),
                        f"pre-script startup module {name}",
                    )
                    for name in RUNTIME_STARTUP_MODULES
                },
                "scope": (
                    "CPython loads these canonical source modules after the "
                    "OS/Python runtime but before script stage zero. They are "
                    "an explicit bootstrap trust boundary and are rehashed "
                    "by stage zero and the start/end module-origin audit."
                ),
            },
        },
        "packages": {
            "desmume": _runtime_tree_record(desmume_root, "DeSmuME package"),
            "PIL": _runtime_tree_record(pil_root, "Pillow package"),
        },
        "modules": module_records,
        "native": {
            "libdesmume": runtime_file_record(
                libdesmume, "libdesmume"
            ),
            "mutable_closure": native_records,
            "os_trust_roots": list(trust_roots),
            "scope": (
                "All loaded native images outside the listed OS-owned trust "
                "roots must be content-addressed by mutable_closure."
            ),
        },
    }


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
        "runtime_environment": unbound_runtime_environment(),
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


def _validate_runtime_environment(
    runtime: Any,
    *,
    require_bound: bool,
) -> None:
    if runtime == unbound_runtime_environment():
        if require_bound:
            raise ManifestError("runtime environment is not host-bound")
        return
    if not isinstance(runtime, dict) or set(runtime) != {
        "schema",
        "status",
        "native_bootstrap",
        "platform",
        "python",
        "packages",
        "modules",
        "native",
    }:
        raise ManifestError("runtime environment record is malformed")
    if (
        runtime.get("schema") != RUNTIME_ENVIRONMENT_SCHEMA
        or runtime.get("status") != "bound"
    ):
        raise ManifestError("runtime environment schema/status differs")
    current = capture_runtime_environment()
    if runtime != current:
        raise ManifestError(
            "runtime environment content/path closure differs"
        )


def verify_manifest_document(
    document: dict[str, Any],
    root: Path,
    input_paths: set[str],
    output_paths: dict[str, str],
    rom_path: Path,
    tool_names: set[str],
    context_keys: set[str],
    *,
    require_bound_runtime: bool = False,
) -> None:
    if not isinstance(document, dict) or set(document) != {
        "schema",
        "build_context",
        "inputs",
        "outputs",
        "runtime_environment",
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
    _validate_runtime_environment(
        document["runtime_environment"],
        require_bound=require_bound_runtime,
    )


def verify_manifest(
    manifest_path: Path,
    rom_path: Path,
    *,
    require_bound_runtime: bool = False,
) -> dict[str, Any]:
    document = load_manifest(manifest_path)
    verify_manifest_document(
        document,
        REPO,
        set(expected_inputs()),
        OUTPUTS,
        rom_path,
        TOOL_CONTEXT_KEYS,
        BUILD_CONTEXT_KEYS,
        require_bound_runtime=require_bound_runtime,
    )
    return document


def bind_runtime_environment(manifest_path: Path, rom_path: Path) -> None:
    manifest_path = Path(os.path.abspath(manifest_path))
    _require_regular_publish_leaf(
        manifest_path,
        "runtime-bind manifest",
        allow_missing=False,
    )
    original = load_manifest(manifest_path)
    verify_manifest(manifest_path, rom_path, require_bound_runtime=False)
    runtime = capture_runtime_environment()
    document = json.loads(json.dumps(original))
    document["runtime_environment"] = runtime
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{manifest_path.name}.runtime-bind.",
        suffix=".tmp",
        dir=manifest_path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        verify_manifest(temporary, rom_path, require_bound_runtime=True)
        if capture_runtime_environment() != runtime:
            raise ManifestError(
                "runtime environment changed while it was being bound"
            )
        os.replace(temporary, manifest_path)
        _fsync_directory(manifest_path.parent)
        verify_manifest(
            manifest_path,
            rom_path,
            require_bound_runtime=True,
        )
    finally:
        temporary.unlink(missing_ok=True)


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
    parser.add_argument("--bind-runtime", type=Path)
    parser.add_argument("--require-bound-runtime", action="store_true")
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
        args.bind_runtime is not None,
        args.publish_pair,
    )
    if sum(modes) != 1:
        raise SystemExit(
            "choose exactly one of --seal, --verify, --bind-runtime, or "
            "--publish-pair"
        )
    publish_values = (
        args.candidate_manifest,
        args.candidate_rom,
        args.final_manifest,
        args.final_rom,
    )
    try:
        if args.seal is not None:
            if args.require_bound_runtime or args.rom is None or any(
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
            verify_manifest(
                args.verify,
                args.rom,
                require_bound_runtime=args.require_bound_runtime,
            )
        elif args.bind_runtime is not None:
            if (
                args.rom is None
                or args.context
                or args.require_bound_runtime
                or any(value is not None for value in publish_values)
            ):
                raise ManifestError(
                    "--bind-runtime requires --rom and no other mode options"
                )
            bind_runtime_environment(args.bind_runtime, args.rom)
        else:
            if (
                args.rom is not None
                or args.context
                or args.require_bound_runtime
                or any(value is None for value in publish_values)
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
