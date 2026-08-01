#!/usr/bin/env python3
"""Task-3 static, host-fixture, relocation, and final hook verification."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pokemon_move_history_build_manifest import (
    DEPENDENCY_FILES,
    FIXED_INPUTS,
    OUTPUTS,
    PACKAGED_ROM_LOGICAL_PATH,
    SCHEMA as BUILD_MANIFEST_SCHEMA,
    ManifestError,
    armips_dependency_paths,
    file_record,
    load_manifest,
    publish_pair,
    unbound_runtime_environment,
    verify_manifest,
    verify_manifest_document,
)


REPO = Path(__file__).resolve().parents[1]
OVERLAY_BASE = 0x023BE400
OVERLAY_LIMIT = 0x1000
OVERLAY153_CALL_INVENTORY_SHA256 = (
    "21d0a504635c977e812d2f395445b3e7a2b8d416a0c5607c72b55865657250e2"
)
OVERLAY155_BASE = 0x023BD400
OVERLAY155_LIMIT = 0x1000
OVERLAY155_DIAGNOSTIC_SCRATCH = 0x023BE200
OVERLAY155_DIAGNOSTIC_SCRATCH_SIZE = 0x134
OVERLAY155_CALL_INVENTORY_SHA256 = (
    "d0c4d752ab5ea21863b8887d8a22282a16aa4dbcbb1dac2bf876e04d639b1fa3"
)
EXPECTED_MAKEFILE_SHA256 = (
    "f47a9465293925c3a5427218c869195c2448992aabb85c805581298b1f6124f8"
)
EXPECTED_BUILD_WRAPPER_SHA256 = (
    "b54204c156f2f8dce508ceea182c47233324bb5d3ac352c53a224c3a5ec5c026"
)
EXPECTED_INCLUDED_MAKE_SOURCES = {
    "data/codetables.mk":
        "d0fe26e89f80a5101339650e69ba205fe8a352b7dd8a09a13f1394583b84f5bd",
    "data/graphics/itemgra.mk":
        "3e90342beaa98774e2e1bb62fd0c0b32673edee65d69b1ce85603c81a8aad444",
    "data/graphics/pokegra.mk":
        "a48e47de1f0c7139755a1e437f29c4a32daddb0176854f369905b2ab75f2c994",
    "data/itemdata/itemdata.mk":
        "5f6fb210d6106c88edca22ce74b9e4c8e93a9dc29d54ad9dd86bc281e010bf51",
    "narcs.mk":
        "a9ac0903e08e654c1a34869ffd8998e55d394b46fbdc547c4e34495e69321d03",
    "overlays.mk":
        "d850825fa9a0e9c183f41d55c16c268d43ffe32faa9e54fe7259aa4dc7458c97",
}
MANAGED_BUILD_PATH = (
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)
MANAGED_BUILD_VENV = "/tmp/hg-engine-venv"
MANAGED_BUILD_PIP_CACHE = "/tmp/pip-cache"
FORBIDDEN_INHERITED_MAKE_CONTROLS = {
    "AUTO_TEST",
    "GNUMAKEFLAGS",
    "MAKEFILES",
}
FORBIDDEN_IMPORTED_BUILD_VARIABLES = {
    "ARMIPS",
    "ARMIPS_FLAGS",
    "AS",
    "ASFLAGS",
    "BUILD",
    "BUILDROM",
    "CC",
    "CFLAGS",
    "DEVKITARM",
    "FILESYS",
    "LD",
    "LDFLAGS",
    "LINK",
    "MAKE",
    "MOVE_HISTORY_CAPTURE_MANIFEST",
    "MOVE_HISTORY_CAPTURE_MANIFEST_TMP",
    "NARCHIVE",
    "NDSTOOL",
    "OBJCOPY",
    "OUTPUT",
    "PREFIX",
    "PYTHON",
    "PYTHON_NO_VENV",
    "ROMNAME",
    "SHELL",
    "VENV_ACTIVATE",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"move-history capture verification failed: {message}")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*\([^;]*?\)\s*\{{", source, re.S)
    require(match is not None, f"{name} body is missing")
    start = match.start()
    cursor = match.end()
    depth = 1
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    require(depth == 0, f"{name} body is unterminated")
    return source[start:cursor]


def ordered(body: str, tokens: list[str], label: str) -> None:
    cursor = 0
    for token in tokens:
        found = body.find(token, cursor)
        require(found >= 0, f"{label} is missing ordered token {token!r}")
        cursor = found + len(token)


def make_recipe_commands(makefile: str) -> list[str]:
    commands: list[str] = []
    current: list[str] = []
    for line in makefile.splitlines():
        if not line.startswith("\t"):
            require(
                not current,
                "Makefile recipe continuation is unterminated",
            )
            continue
        part = line[1:].rstrip()
        continued = part.endswith("\\")
        if continued:
            part = part[:-1].rstrip()
        current.append(part)
        if not continued:
            commands.append(" ".join(" ".join(current).split()))
            current = []
    require(not current, "Makefile ends inside a recipe continuation")
    return commands


def make_target_recipe_commands(makefile: str, target: str) -> list[str]:
    lines = makefile.splitlines()
    target_lines = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^{re.escape(target)}\s*:", line) is not None
    ]
    require(
        len(target_lines) == 1,
        f"Makefile target {target!r} is missing or duplicated",
    )
    recipe_lines: list[str] = []
    for line in lines[target_lines[0] + 1:]:
        if line.startswith("\t"):
            recipe_lines.append(line)
        elif recipe_lines:
            break
        elif line.strip():
            break
    require(recipe_lines, f"Makefile target {target!r} has no recipe")
    return make_recipe_commands("\n".join(recipe_lines))


def make_publication_contract_matches(
    makefile: str,
    target_declaration: str,
    complete_recipe: list[str],
    publication_tail: list[str],
) -> bool:
    target_pattern = re.compile(
        rf"(?m)^{re.escape(target_declaration)}$"
    )
    if len(target_pattern.findall(makefile)) != 1:
        return False
    if len(re.findall(r"(?m)^all\s*:", makefile)) != 1:
        return False
    try:
        recipe = make_target_recipe_commands(makefile, "all")
    except SystemExit:
        return False
    return (
        recipe == complete_recipe
        and recipe[-len(publication_tail):] == publication_tail
    )


def managed_build_environment() -> dict[str, str]:
    return {
        "LC_ALL": "C",
        "PATH": MANAGED_BUILD_PATH,
        "PIP_CACHE_DIR": MANAGED_BUILD_PIP_CACHE,
        "PWD": str(REPO),
    }


def managed_build_environment_is_exact(
    environment: dict[str, str] | None = None,
) -> bool:
    active_environment = os.environ if environment is None else environment
    observed = dict(active_environment)
    if sys.platform == "darwin":
        encoding = observed.pop("__CF_USER_TEXT_ENCODING", None)
        if (
            encoding is not None
            and re.fullmatch(r"0x[0-9A-Fa-f]+:0x[0-9A-Fa-f]+:0x[0-9A-Fa-f]+", encoding)
            is None
        ):
            return False
    return observed == managed_build_environment()


def safe_make_flag_tokens(tokens: list[str]) -> bool:
    return all(
        (
            token
            in {
                "-j",
                "-w",
                "w",
                "--print-directory",
                "--no-print-directory",
            }
            or re.fullmatch(r"-j[1-9][0-9]*", token) is not None
            or re.fullmatch(
                r"--jobserver-(?:fds|auth)=[0-9]+,[0-9]+",
                token,
            )
            is not None
        )
        for token in tokens
    )


def outer_make_invocation_is_safe(
    environment: dict[str, str] | None = None,
) -> bool:
    active_environment = os.environ if environment is None else environment
    if any(
        name in active_environment
        for name in FORBIDDEN_INHERITED_MAKE_CONTROLS
    ):
        return False
    makelevel = active_environment.get("MAKELEVEL")
    inside_make = makelevel is not None
    if inside_make and any(
        name in active_environment
        for name in FORBIDDEN_IMPORTED_BUILD_VARIABLES
    ):
        return False
    if inside_make and makelevel != "1":
        return False
    if (
        "VENV" in active_environment
        and (
            not inside_make
            or active_environment["VENV"] != MANAGED_BUILD_VENV
        )
    ):
        return False
    makeflags = active_environment.get("MAKEFLAGS", "").strip()
    makeoverrides = active_environment.get("MAKEOVERRIDES", "").strip()
    mflags = active_environment.get("MFLAGS")
    if not makeflags:
        return (
            not inside_make
            and not makeoverrides
            and mflags is None
        )
    if "\\" in makeflags or "\n" in makeflags:
        return False
    tokens = makeflags.split()
    command_variables: list[str] = []
    if "--" in tokens:
        separator = tokens.index("--")
        command_variables = tokens[separator + 1:]
        tokens = tokens[:separator]
    elif any("=" in token for token in tokens):
        command_variables = [
            token for token in tokens if "=" in token
        ]
        tokens = [
            token for token in tokens if "=" not in token
        ]
    if not safe_make_flag_tokens(tokens):
        return False
    if command_variables not in ([], [f"VENV={MANAGED_BUILD_VENV}"]):
        return False
    if command_variables:
        if makeoverrides != "${-*-command-variables-*-}":
            return False
    elif makeoverrides:
        return False
    if inside_make:
        if (
            mflags is None
            or not safe_make_flag_tokens(mflags.split())
        ):
            return False
    elif mflags is not None:
        return False
    return True


def make_compilation_source_topology_is_safe(root: Path = REPO) -> bool:
    safe_component = re.compile(r"[A-Za-z0-9_.+\-]+")
    for relative_root, suffix in (("src", ".c"), ("asm", ".s")):
        source_root = root / relative_root
        try:
            source_mode = source_root.lstat().st_mode
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(source_mode) or not stat.S_ISDIR(source_mode):
            return False
        for directory, directory_names, file_names in os.walk(
            source_root,
            followlinks=False,
        ):
            directory_path = Path(directory)
            for directory_name in directory_names:
                child = directory_path / directory_name
                if (
                    safe_component.fullmatch(directory_name) is None
                    or child.is_symlink()
                    or not child.is_dir()
                ):
                    return False
            for file_name in file_names:
                if (
                    relative_root == "src"
                    and directory_path == source_root
                    and "." not in file_name
                ):
                    return False
                if Path(file_name).suffix != suffix:
                    continue
                source = directory_path / file_name
                if (
                    safe_component.fullmatch(file_name) is None
                    or source.is_symlink()
                    or not source.is_file()
                ):
                    return False
    return True


def generated_dependency_inputs_are_safe(root: Path = REPO) -> bool:
    if not make_compilation_source_topology_is_safe(root):
        return False
    build_root = root / "build"
    source_root = root / "src"
    try:
        build_mode = build_root.lstat().st_mode
    except FileNotFoundError:
        return True
    if stat.S_ISLNK(build_mode) or not stat.S_ISDIR(build_mode):
        return False
    safe_token = re.compile(r"[A-Za-z0-9_./+\-]+")
    expected_dependencies = {
        build_root
        / source.relative_to(source_root).with_suffix(".d")
        for source in source_root.rglob("*.c")
    }
    for dependency in sorted(expected_dependencies):
        cursor = dependency.parent
        while cursor != build_root:
            try:
                cursor_mode = cursor.lstat().st_mode
            except FileNotFoundError:
                pass
            else:
                if (
                    stat.S_ISLNK(cursor_mode)
                    or not stat.S_ISDIR(cursor_mode)
                ):
                    return False
            cursor = cursor.parent
        if not dependency.exists() and not dependency.is_symlink():
            continue
        if dependency.is_symlink() or not dependency.is_file():
            return False
        try:
            source = dependency.read_text()
        except (OSError, UnicodeError):
            return False
        if (
            "\0" in source
            or "$" in source
            or "=" in source
            or "\t" in source
            or any(character in source for character in "`;&|")
        ):
            return False
        logical = source.replace("\\\n", " ")
        if "\\" in logical:
            return False
        lines = [
            line.strip()
            for line in logical.splitlines()
            if line.strip()
        ]
        if len(lines) != 1 or ":" not in lines[0]:
            return False
        target, prerequisites = lines[0].split(":", 1)
        target = target.strip()
        prerequisite_tokens = prerequisites.split()
        expected_target = dependency.with_suffix(".o").relative_to(root)
        if (
            target != expected_target.as_posix()
            or safe_token.fullmatch(target) is None
            or not prerequisite_tokens
            or any(
                safe_token.fullmatch(token) is None
                or Path(token).suffix not in {".c", ".h"}
                for token in prerequisite_tokens
            )
        ):
            return False
    return True


def trusted_pre_make_sources_are_exact(makefile: str) -> bool:
    if (
        hashlib.sha256(makefile.encode()).hexdigest()
        != EXPECTED_MAKEFILE_SHA256
    ):
        return False
    wrapper = REPO / "docker-makerom.cmd"
    if (
        not wrapper.is_file()
        or wrapper.is_symlink()
        or hashlib.sha256(wrapper.read_bytes()).hexdigest()
        != EXPECTED_BUILD_WRAPPER_SHA256
    ):
        return False
    for relative_path, expected_sha256 in (
        EXPECTED_INCLUDED_MAKE_SOURCES.items()
    ):
        path = REPO / relative_path
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest()
            != expected_sha256
        ):
            return False
    return generated_dependency_inputs_are_safe()


def enter_managed_build_environment(clean_mode: str) -> None:
    os.execve(
        sys.executable,
        [
            sys.executable,
            str(Path(__file__).resolve()),
            clean_mode,
        ],
        managed_build_environment(),
    )


def exec_managed_build() -> None:
    require(
        REPO == Path("/hg-engine"),
        "managed build entry must run inside the hg-engine Docker mount",
    )
    require(
        managed_build_environment_is_exact(),
        "managed build environment contains inherited variables",
    )
    makefile = (REPO / "Makefile").read_text()
    require(
        outer_make_invocation_is_safe(),
        "managed pre-Make environment contains controls or overrides",
    )
    require(
        trusted_pre_make_sources_are_exact(makefile),
        "managed pre-Make source/dependency trust gate differs",
    )
    try:
        parallelism = subprocess.check_output(
            ["nproc"],
            env=managed_build_environment(),
            text=True,
            timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        raise SystemExit(
            "move-history capture verification failed: nproc failed"
        ) from None
    require(
        re.fullmatch(r"[1-9][0-9]*", parallelism) is not None,
        "managed build parallelism is invalid",
    )
    print("move-history capture: managed pre-Make trust gate verified", flush=True)
    os.execvpe(
        "make",
        [
            "make",
            f"-j{parallelism}",
            f"VENV={MANAGED_BUILD_VENV}",
        ],
        managed_build_environment(),
    )


def effective_make_all_contract_matches(
    makefile: str,
    expected_makefile_sha256: str,
    expected_included_sources: dict[str, str],
    expected_prerequisites_sha256: str,
    expected_recipe: list[str],
    expected_recipe_variables_sha256: str,
    *,
    make_arguments: tuple[str, ...] = (),
) -> bool:
    if (
        hashlib.sha256(makefile.encode()).hexdigest()
        != expected_makefile_sha256
    ):
        return False
    for relative_path, expected_sha256 in expected_included_sources.items():
        path = REPO / relative_path
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest()
            != expected_sha256
        ):
            return False

    try:
        environment = {
            "LC_ALL": "C",
            "PATH": os.environ.get("PATH", os.defpath),
        }
        with tempfile.TemporaryDirectory(
            prefix="move-history-effective-make-"
        ) as isolated_directory:
            isolated_root = Path(isolated_directory)
            (isolated_root / "Makefile").write_text(makefile)
            for directory in (
                "armips",
                "asm",
                "data",
                "include",
                "scripts",
                "src",
                "tools",
            ):
                (isolated_root / directory).symlink_to(
                    REPO / directory,
                    target_is_directory=True,
                )
            for make_source in ("narcs.mk", "overlays.mk"):
                shutil.copyfile(
                    REPO / make_source,
                    isolated_root / make_source,
                )
            for root_input in ("hooks", "requirements.txt", "rom.ld"):
                (isolated_root / root_input).symlink_to(
                    REPO / root_input,
                )
            rom_header = bytearray(16)
            rom_header[12:16] = b"IPKE"
            (isolated_root / "rom.nds").write_bytes(rom_header)
            initialized = subprocess.run(
                ["git", "init", "-q"],
                cwd=isolated_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )
            if initialized.returncode != 0:
                return False
            completed = subprocess.run(
                [
                    "make",
                    "--no-print-directory",
                    "-qpRr",
                    "-f",
                    "Makefile",
                    "VENV=/tmp/hg-engine-venv",
                    *make_arguments,
                    "all",
                ],
                cwd=isolated_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode not in (0, 1) or completed.stderr.strip():
        return False
    makefile_lists = re.findall(
        r"(?m)^MAKEFILE_LIST\s*:?=\s*(.*)$",
        completed.stdout,
    )
    if (
        len(makefile_lists) != 1
        or any(
            path.endswith(".d")
            for path in makefile_lists[0].split()
        )
    ):
        return False

    lines = completed.stdout.splitlines()
    all_rule_indices = [
        index
        for index, line in enumerate(lines)
        if line.startswith("all:")
    ]
    if len(all_rule_indices) != 1:
        return False
    rule_index = all_rule_indices[0]
    prerequisites = " ".join(
        lines[rule_index].removeprefix("all:").split()
    )
    if (
        hashlib.sha256(prerequisites.encode()).hexdigest()
        != expected_prerequisites_sha256
    ):
        return False

    next_rule = next(
        (
            index
            for index in range(rule_index + 1, len(lines))
            if lines[index]
            and not lines[index].startswith(("#", "\t", " "))
            and ":" in lines[index]
        ),
        len(lines),
    )
    command_header = next(
        (
            index
            for index in range(rule_index + 1, next_rule)
            if lines[index].startswith(
                ("#  commands to execute", "#  recipe to execute")
            )
        ),
        None,
    )
    if command_header is None:
        return False
    all_rule_metadata = lines[rule_index + 1:command_header]
    if any(
        re.match(r"^# (?:makefile|command line|override|environment)", line)
        is not None
        and index + 1 < len(all_rule_metadata)
        and re.match(
            r"^#\s+[A-Za-z_][A-Za-z0-9_]*\s*(?::|\+|\?|!)?=",
            all_rule_metadata[index + 1],
        )
        is not None
        for index, line in enumerate(all_rule_metadata)
    ):
        return False
    recipe_lines: list[str] = []
    for line in lines[command_header + 1:]:
        if line.startswith("\t"):
            recipe_lines.append(line)
        elif recipe_lines:
            break
    while recipe_lines and not recipe_lines[-1].strip():
        recipe_lines.pop()
    try:
        effective_recipe = make_recipe_commands(
            "\n".join(recipe_lines)
        )
    except SystemExit:
        return False
    if effective_recipe != expected_recipe:
        return False

    variable_definitions: dict[str, list[tuple[str, str, str]]] = {}
    definition_pattern = re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*)\s*"
        r"((?::|\+|\?|!)?=)\s*(.*)$"
    )
    for index, line in enumerate(lines):
        assignment = definition_pattern.match(line)
        if assignment is None:
            continue
        name = assignment.group(1)
        origin_line = lines[index - 1] if index else ""
        origin_match = re.match(r"^# ([a-z ]+)", origin_line)
        origin = (
            origin_match.group(1).strip()
            if origin_match is not None
            else ""
        )
        variable_definitions.setdefault(name, []).append(
            (
                origin,
                assignment.group(2),
                " ".join(assignment.group(3).split()),
            )
        )

    simple_reference = re.compile(
        r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)"
        r"|\$\{([A-Za-z_][A-Za-z0-9_]*)\}"
    )
    direct_variables = {
        first or second
        for first, second in simple_reference.findall(
            "\n".join(expected_recipe)
        )
    }
    variable_closure: set[str] = set()
    visiting: set[str] = set()

    def visit_variable(name: str) -> bool:
        if name in variable_closure:
            return True
        if (
            name in visiting
            or name not in variable_definitions
            or len(variable_definitions[name]) != 1
        ):
            return False
        visiting.add(name)
        _origin, _operator, value = variable_definitions[name][0]
        references = {
            first or second
            for first, second in simple_reference.findall(value)
        }
        residual = simple_reference.sub("", value).replace("$$", "")
        if "$" in residual:
            return False
        for reference in references:
            if not visit_variable(reference):
                return False
        visiting.remove(name)
        variable_closure.add(name)
        return True

    if not all(
        visit_variable(name)
        for name in sorted(direct_variables)
    ):
        return False
    variable_records = [
        {
            "name": name,
            "operator": variable_definitions[name][0][1],
            "origin": variable_definitions[name][0][0],
            "value": (
                Path(variable_definitions[name][0][2]).name
                if name == "MAKE_COMMAND"
                else variable_definitions[name][0][2]
            ),
        }
        for name in sorted(variable_closure)
    ]
    if (
        "MAKE_COMMAND" in variable_closure
        and (
            variable_definitions["MAKE_COMMAND"][0][0] != "default"
            or Path(
                variable_definitions["MAKE_COMMAND"][0][2]
            ).name != "make"
        )
    ):
        return False
    variables_sha256 = hashlib.sha256(
        json.dumps(
            variable_records,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if variables_sha256 != expected_recipe_variables_sha256:
        return False

    makeflags = re.findall(
        r"(?m)^MAKEFLAGS\s*((?::|\+|\?|!)?=)\s*(.*)$",
        completed.stdout,
    )
    if makeflags not in (
        [
            (
                "=",
                "--no-print-directory -Rrqp -- $(MAKEOVERRIDES)",
            )
        ],
        [
            (
                "=",
                "pqrR --no-print-directory -- $(MAKEOVERRIDES)",
            )
        ],
    ):
        return False
    makeoverrides = re.findall(
        r"(?m)^MAKEOVERRIDES\s*((?::|\+|\?|!)?=)\s*(.*)$",
        completed.stdout,
    )
    if makeoverrides != [
        ("=", "${-*-command-variables-*-}"),
    ]:
        return False
    return True


def makeflags_suppress_failures_or_output(makefile: str) -> bool:
    return (
        re.search(
            r"(?m)^\s*(?:override\s+)?MAKEFLAGS\s*"
            r"(?::|\+|\?|!)?=",
            makefile,
        )
        is not None
    )


def without_comments(source: str) -> str:
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", source, flags=re.S)


def executable_function(source: str, name: str) -> str:
    return function_body(without_comments(source), name)


RECORDABLE_RETURN_RE = re.compile(
    r"\breturn\s+move\s*!=\s*MOVE_NONE"
    r"\s*&&\s*move\s*<\s*NUM_OF_MOVES"
    r"\s*&&\s*!\s*IsMoveUnimplemented\s*\(\s*move\s*\)\s*;"
)
APPEND_RECORDABLE_GUARD_RE = re.compile(
    r"\bif\s*\(\s*!PokemonMoveHistory_IsRecordableMove\s*\("
    r"\s*move\s*\)\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}",
    re.S,
)
LEVEL_UP_SUCCESS_RE = re.compile(
    r"\bif\s*\(\s*ret\s*!=\s*\(u16\)\s*-\s*1u"
    r"\s*&&\s*ret\s*!=\s*\(u16\)\s*-\s*2u"
    r"\s*&&\s*ret\s*!=\s*MOVE_NONE\s*\)\s*\{",
    re.S,
)
LEVEL_UP_TRANSACTION_RE = re.compile(
    r"\bret\s*=\s*TryAppendMonMove\s*\(\s*mon\s*,\s*\*sp0\s*\)\s*;"
    r"\s*if\s*\(\s*ret\s*!=\s*\(u16\)\s*-\s*1u"
    r"\s*&&\s*ret\s*!=\s*\(u16\)\s*-\s*2u"
    r"\s*&&\s*ret\s*!=\s*MOVE_NONE\s*\)\s*\{"
    r"\s*SaveData\s*\*\s*saveData\s*=\s*SaveBlock2_get\s*\(\s*\)\s*;"
    r"\s*if\s*\(\s*saveData\s*!=\s*NULL\s*\)\s*\{"
    r"\s*PokemonMoveHistory_RecordMove\s*\("
    r"\s*saveData\s*,\s*&mon->box\s*,\s*\*sp0\s*\)\s*;"
    r"\s*\}\s*\}",
    re.S,
)
RECORD_MOVE_IMPL_RE = re.compile(
    r"^PokemonMoveHistory_RecordMoveImpl\s*\("
    r"\s*SaveData\s*\*\s*saveData\s*,"
    r"\s*struct\s+BoxPokemon\s*\*\s*pokemon\s*,"
    r"\s*u16\s+move\s*\)\s*\{"
    r"\s*PokemonMoveHistorySnapshot\s+snapshot\s*;"
    r"\s*struct\s+PokemonMoveHistoryRecord\s*\*\s*record\s*;"
    r"\s*if\s*\(\s*!PokemonMoveHistory_IsRecordableMove\s*\(\s*move\s*\)"
    r"\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}"
    r"\s*if\s*\(\s*!PokemonMoveHistory_CaptureSnapshotImpl\s*\("
    r"\s*pokemon\s*,\s*&snapshot\s*\)\s*\)\s*\{"
    r"\s*return\s+FALSE\s*;\s*\}"
    r"\s*record\s*=\s*PokemonMoveHistory_ObserveSnapshot\s*\("
    r"\s*saveData\s*,\s*&snapshot\s*\)\s*;"
    r"\s*if\s*\(\s*record\s*==\s*NULL\s*\)\s*\{"
    r"\s*return\s+FALSE\s*;\s*\}"
    r"\s*PokemonMoveHistory_AppendMove\s*\("
    r"\s*saveData\s*,\s*&snapshot\s*,\s*record\s*,\s*move\s*\)\s*;"
    r"\s*return\s+TRUE\s*;\s*\}$",
    re.S,
)
PARTY_MENU_REPLACE_RE = re.compile(
    r"\bPokemonMoveHistory_ReplaceMove\s*\("
    r"\s*&mon->box\s*,\s*partyMenu->args->moveId\s*,\s*moveIdx\s*\)\s*;",
    re.S,
)
DELETE_MOVE_IMPL_RE = re.compile(
    r"^PokemonMoveHistory_DeleteMoveSlotImpl\s*\("
    r"\s*struct\s+PartyPokemon\s*\*\s*pokemon\s*,"
    r"\s*u32\s+slot\s*\)\s*\{"
    r"\s*if\s*\(\s*pokemon\s*==\s*NULL\s*\|\|\s*slot\s*>=\s*4\s*\)"
    r"\s*\{\s*return\s*;\s*\}"
    r"\s*PokemonMoveHistory_SeedImpl\s*\("
    r"\s*SaveBlock2_get\s*\(\s*\)\s*,\s*&pokemon->box\s*\)\s*;"
    r"\s*MonDeleteMoveSlot_Original\s*\(\s*pokemon\s*,\s*slot\s*\)\s*;"
    r"\s*\}$",
    re.S,
)
LEVEL_UP_COMMIT_REGION = (
    "if ((levelUpLearnset[*last_i] & LEVEL_UP_LEARNSET_LEVEL_MASK) == "
    "(level << LEVEL_UP_LEARNSET_LEVEL_SHIFT)) { "
    "*sp0 = LEVEL_UP_LEARNSET_MOVE(levelUpLearnset[*last_i]); "
    "(*last_i)++; "
    "#ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES "
    "if (!IsMoveUnimplemented(*sp0)) "
    "#endif "
    "{ "
    "ret = TryAppendMonMove(mon, *sp0); "
    "if (ret != (u16)-1u && ret != (u16)-2u && ret != MOVE_NONE) { "
    "SaveData *saveData = SaveBlock2_get(); "
    "if (saveData != NULL) { "
    "PokemonMoveHistory_RecordMove( saveData, &mon->box, *sp0); "
    "} "
    "} "
    "} "
    "} "
    "sys_FreeMemoryEz(levelUpLearnset); "
    "return ret; "
    "}"
)
LEVEL_UP_EXECUTABLE_SHA256 = (
    "6a58f4e384533000ea32263208648e2eb77cec497c8aa9c383abbcfefad2847a"
)
LIFECYCLE_SOURCE_SHA256 = {
    "SaveData_New":
        "8f08d1f8ded5be41e68ad1c0ca94ae7bea720e85755de09addd184d44734b75b",
    "Save_InitDynamicRegion":
        "894db9f97260cfde161484f9803f6d89496f4b1fdf8e9d915e3e092da05642ec",
    "Save_LoadDynamicRegion":
        "fb00e981d22f36006f39e7b52e69733d742de6ab8340117e1fd2330ec3fe785b",
    "Save_WriteManInit":
        "77e222a4cee3f6cc2556b255af9808480050364df277ef866e35d1eaf6fdf23d",
    "Save_PrepareForAsyncWrite":
        "cfff78b3382c88d76122f52b2ab280777e29c00e93e3c52d5df01c211cada1a7",
    "Save_WriteFileAsync":
        "3d1b0292daeb18f571ae4bed84985c40898ad2d72e48a5ea62471b6f4a7ac804",
    "Save_WriteManFinish":
        "7c5b2f25d9c3d9feb9eb6c433abd8968523e01b3167d3c95a048bdbc2271053b",
    "CancelAsyncSaveWithMoveHistory":
        "e80d6eeb8b029bd63ff8bcff5ac484205affe05a13307c21317a22724f59a566",
    "Save_Cancel":
        "48f0544af0aa738aee01640e14c7d3a32fe42296d5fcd3b79fdc45a0f71abdb3",
    "PokemonMoveHistory_SeedParty":
        "1f871802df018cf9adf78fc51f51d02960f3c1370da0a1589911bb5b2bbf6646",
    "PokemonMoveHistory_LoadAndSeedPartyImpl":
        "fdddca1535b4d654fce02afb11c2239e7745c5700590432cc5d304f7f85611bc",
    "PokemonMoveHistory_PrepareSaveImpl":
        "d3e7c1ca4984ee8173abe01bc2c0cfe44c6bcac997706116a79a5019f2e7a905",
    "PokemonMoveHistory_FinishSaveImpl":
        "37dc8758ca4dc19d3c12bf19009d84d5a3799833de0d05a6535bc1cb2d7f8e89",
    "PokemonMoveHistory_CancelSaveImpl":
        "71b04820cb3aa373a016534f78896360b9f6808009e61a6517a29d49b1448180",
}


def block_from_match(source: str, match: re.Match[str]) -> str:
    open_brace = source.find("{", match.start(), match.end())
    require(open_brace >= 0, "matched control block has no opening brace")
    cursor = open_brace + 1
    depth = 1
    while cursor < len(source) and depth:
        if source[cursor] == "{":
            depth += 1
        elif source[cursor] == "}":
            depth -= 1
        cursor += 1
    require(depth == 0, "matched control block is unterminated")
    return source[match.start():cursor]


def predicate_contract_matches(history_source: str) -> bool:
    predicate_code = executable_function(
        history_source,
        "PokemonMoveHistory_IsRecordableMove",
    )
    return (
        len(RECORDABLE_RETURN_RE.findall(predicate_code)) == 1
        and predicate_code.count("IsMoveUnimplemented") == 1
    )


def append_guard_contract_matches(history_source: str) -> bool:
    append_code = executable_function(
        history_source,
        "PokemonMoveHistory_AppendMove",
    )
    return (
        len(APPEND_RECORDABLE_GUARD_RE.findall(append_code)) == 1
        and append_code.count("PokemonMoveHistory_IsRecordableMove") == 1
    )


def level_up_success_contract_matches(pokemon_source: str) -> bool:
    level_up_code = executable_function(
        pokemon_source,
        "MonTryLearnMoveOnLevelUp",
    )
    if re.match(
        r"^MonTryLearnMoveOnLevelUp\s*\("
        r"\s*struct\s+PartyPokemon\s*\*\s*mon\s*,"
        r"\s*int\s*\*\s*last_i\s*,\s*u16\s*\*\s*sp0\s*\)\s*\{",
        level_up_code,
        re.S,
    ) is None:
        return False
    transactions = list(LEVEL_UP_TRANSACTION_RE.finditer(level_up_code))
    if len(transactions) != 1:
        return False
    transaction = transactions[0]
    tail = level_up_code[transaction.end():]
    brace_depth = (
        level_up_code[:transaction.start()].count("{")
        - level_up_code[:transaction.start()].count("}")
    )
    containing_brace = level_up_code.rfind("{", 0, transaction.start())
    guard_prefix = level_up_code[:containing_brace]
    commit_region_start = level_up_code.rfind(
        "if ((levelUpLearnset[*last_i]"
    )
    normalized_commit_region = (
        " ".join(level_up_code[commit_region_start:].split())
        if commit_region_start >= 0
        else ""
    )
    normalized_function = " ".join(level_up_code.split()).encode()
    return (
        hashlib.sha256(normalized_function).hexdigest()
        == LEVEL_UP_EXECUTABLE_SHA256
        and level_up_code.count("TryAppendMonMove(") == 1
        and level_up_code.count("PokemonMoveHistory_RecordMove(") == 1
        and level_up_code.count("SaveBlock2_get(") == 1
        and brace_depth == 3
        and containing_brace >= 0
        and re.search(
            r"#ifdef\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES"
            r"\s*if\s*\(\s*!IsMoveUnimplemented\s*\(\s*\*sp0\s*\)\s*\)"
            r"\s*#endif\s*$",
            guard_prefix,
            re.S,
        )
        is not None
        and not level_up_code[
            containing_brace + 1:transaction.start()
        ].strip()
        and re.search(r"\b(?:ret|saveData)\s*=", tail) is None
        and normalized_commit_region == LEVEL_UP_COMMIT_REGION
        and re.search(
            r"\b(?:SetMonData|SetBoxMonData|MonSetMoveInSlot|"
            r"PartyMonSetMoveInSlot)\s*\(",
            level_up_code,
        )
        is None
    )


def record_move_contract_matches(history_source: str) -> bool:
    return (
        RECORD_MOVE_IMPL_RE.fullmatch(
            executable_function(
                history_source,
                "PokemonMoveHistory_RecordMoveImpl",
            )
        )
        is not None
    )


def party_menu_contract_matches(party_source: str) -> bool:
    code = executable_function(party_source, "PartyMenu_LearnMoveToSlot")
    replacement = PARTY_MENU_REPLACE_RE.search(code)
    function_brace = code.find("{")
    return (
        re.match(
            r"^PartyMenu_LearnMoveToSlot\s*\("
            r"\s*struct\s+PartyMenu\s*\*\s*partyMenu\s*,"
            r"\s*struct\s+PartyPokemon\s*\*\s*mon\s*,"
            r"\s*int\s+moveIdx\s*\)\s*\{",
            code,
            re.S,
        )
        is not None
        and replacement is not None
        and len(PARTY_MENU_REPLACE_RE.findall(code)) == 1
        and code.count("PokemonMoveHistory_ReplaceMove(") == 1
        and function_brace >= 0
        and not code[function_brace + 1:replacement.start()].strip()
        and replacement.start()
        < code.find("if (partyMenu->args->itemId != ITEM_NONE)")
        and re.search(
            r"\b(?:SetMonData|SetBoxMonData|MonSetMoveInSlot|"
            r"PartyMonSetMoveInSlot)\s*\(",
            code,
        )
        is None
    )


def delete_move_contract_matches(history_source: str) -> bool:
    return (
        DELETE_MOVE_IMPL_RE.fullmatch(
            executable_function(
                history_source,
                "PokemonMoveHistory_DeleteMoveSlotImpl",
            )
        )
        is not None
    )


def normalized_function_sha256(source: str, name: str) -> str:
    normalized = " ".join(executable_function(source, name).split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def lifecycle_contract_matches(
    source: str,
    name: str,
) -> bool:
    return (
        normalized_function_sha256(source, name)
        == LIFECYCLE_SOURCE_SHA256[name]
    )


def lifecycle_source_mutation_fixtures(
    save_source: str,
    history_source: str,
) -> None:
    fixtures = (
        (
            save_source,
            "SaveData_New",
            "PokemonMoveHistory_Init(ret);",
            "PokemonMoveHistory_Init(NULL);",
            "NULL history initialization",
        ),
        (
            save_source,
            "Save_InitDynamicRegion",
            "PokemonMoveHistory_Reset(saveData);",
            "PokemonMoveHistory_Reset(NULL);",
            "NULL new-game history reset",
        ),
        (
            save_source,
            "Save_LoadDynamicRegion",
            "PokemonMoveHistory_LoadAndSeedParty(saveData);",
            "PokemonMoveHistory_LoadAndSeedParty(NULL);",
            "NULL load-boundary seeding",
        ),
        (
            save_source,
            "Save_LoadDynamicRegion",
            "sub_0202C6FC(saveData);\n"
            "    PokemonMoveHistory_LoadAndSeedParty(saveData);",
            "PokemonMoveHistory_LoadAndSeedParty(saveData);\n"
            "    sub_0202C6FC(saveData);",
            "reordered load-boundary seeding",
        ),
        (
            save_source,
            "Save_WriteManInit",
            "Sys_SetSleepDisableFlag(1);\n\n"
            "    \n    (void)PokemonMoveHistory_PrepareSave(saveData);",
            "PokemonMoveHistory_PrepareSave(saveData);\n"
            "    Sys_SetSleepDisableFlag(1);",
            "reordered prepare/sleep-disable lifecycle",
        ),
        (
            save_source,
            "Save_WriteManInit",
            "(void)PokemonMoveHistory_PrepareSave(saveData);",
            "(void)PokemonMoveHistory_PrepareSave(NULL);",
            "NULL save preparation",
        ),
        (
            save_source,
            "Save_PrepareForAsyncWrite",
            "Save_WriteManInit("
            "saveData, &saveData->asyncWriteMan, a1);",
            "Save_WriteManInit(NULL, &saveData->asyncWriteMan, a1);",
            "NULL prepare wrapper",
        ),
        (
            save_source,
            "Save_WriteFileAsync",
            "Save_WriteManFinish("
            "saveData, &saveData->asyncWriteMan, ret);",
            "Save_WriteManFinish("
            "saveData, &saveData->asyncWriteMan, WRITE_STATUS_TOTAL_FAIL);",
            "wrong asynchronous finish status",
        ),
        (
            save_source,
            "Save_WriteManFinish",
            "PokemonMoveHistory_FinishSave(\n"
            "        saveData,\n"
            "        a2 != WRITE_STATUS_TOTAL_FAIL);",
            "PokemonMoveHistory_FinishSave(NULL, TRUE);",
            "wrong save-finish arguments",
        ),
        (
            save_source,
            "CancelAsyncSaveWithMoveHistory",
            "PokemonMoveHistory_CancelSave(saveData);\n"
            "    Sys_ClearSleepDisableFlag(1);",
            "Sys_ClearSleepDisableFlag(1);\n"
            "    PokemonMoveHistory_CancelSave(NULL);",
            "NULL/reordered cancellation",
        ),
        (
            save_source,
            "Save_Cancel",
            "CancelAsyncSaveWithMoveHistory("
            "saveData, &saveData->asyncWriteMan);",
            "CancelAsyncSave(saveData, &saveData->asyncWriteMan);",
            "bypassed history-aware cancellation",
        ),
        (
            history_source,
            "PokemonMoveHistory_SeedParty",
            "pokemon = Party_GetMonByIndex(party, i);",
            "pokemon = &party->members[i];",
            "serialized party array indexing",
        ),
        (
            history_source,
            "PokemonMoveHistory_SeedParty",
            "saveData,\n            &pokemon->box",
            "NULL,\n            &pokemon->box",
            "NULL party-history seeding",
        ),
        (
            history_source,
            "PokemonMoveHistory_LoadAndSeedPartyImpl",
            "PokemonMoveHistory_LoadImpl(saveData);",
            "PokemonMoveHistory_LoadImpl(NULL);\n"
            "    PokemonMoveHistory_SeedParty(saveData);",
            "wrong load-only boundary",
        ),
        (
            history_source,
            "PokemonMoveHistory_PrepareSaveImpl",
            "PokemonMoveHistory_SeedParty(saveData);\n"
            "    historyReady = "
            "PokemonMoveHistory_CommitIfDirtyImpl(saveData);",
            "historyReady = "
            "PokemonMoveHistory_CommitIfDirtyImpl(saveData);\n"
            "    PokemonMoveHistory_SeedParty(NULL);",
            "reordered prepare seeding/commit",
        ),
        (
            history_source,
            "PokemonMoveHistory_FinishSaveImpl",
            "if (success\n"
            "            && saveData->pokemonMoveHistoryStagedSaveCounter",
            "if (!success\n"
            "            && saveData->pokemonMoveHistoryStagedSaveCounter",
            "inverted finish success",
        ),
        (
            history_source,
            "PokemonMoveHistory_CancelSaveImpl",
            "saveData->pokemonMoveHistoryStagedMirror = "
            "MOVE_HISTORY_NO_MIRROR;",
            "saveData->pokemonMoveHistoryStagedMirror = "
            "MOVE_HISTORY_NO_MIRROR;\n"
            "    saveData->pokemonMoveHistoryDirty = FALSE;",
            "cancellation clears retry state",
        ),
    )
    for source, name, needle, replacement, label in fixtures:
        raw = function_body(source, name)
        executable = without_comments(raw)
        require(
            needle in executable,
            f"{label} fixture does not match {name}",
        )
        mutated = executable.replace(needle, replacement, 1)
        require(mutated != executable, f"{label} fixture is inert")
        require(
            not lifecycle_contract_matches(
                source.replace(raw, mutated, 1),
                name,
            ),
            f"{label} passes exact lifecycle source authentication",
        )


def source_matcher_mutation_fixtures(
    history_source: str,
    pokemon_source: str,
    party_source: str,
) -> None:
    append_raw = function_body(
        history_source,
        "PokemonMoveHistory_AppendMove",
    )
    append_guard = APPEND_RECORDABLE_GUARD_RE.search(
        without_comments(append_raw)
    )
    require(append_guard is not None, "append mutation fixture lacks guard")
    executable_append = without_comments(append_raw)
    guard_text = append_guard.group(0)
    commented_append = executable_append.replace(
        guard_text,
        f"/* {guard_text} */",
        1,
    )
    ignored_append = executable_append.replace(
        guard_text,
        "PokemonMoveHistory_IsRecordableMove(move);",
        1,
    )
    require(
        not append_guard_contract_matches(
            history_source.replace(append_raw, commented_append, 1)
        ),
        "commented-out AppendMove guard passes source contracts",
    )
    require(
        not append_guard_contract_matches(
            history_source.replace(append_raw, ignored_append, 1)
        ),
        "ignored AppendMove predicate result passes source contracts",
    )

    predicate_raw = function_body(
        history_source,
        "PokemonMoveHistory_IsRecordableMove",
    )
    predicate_return = RECORDABLE_RETURN_RE.search(
        without_comments(predicate_raw)
    )
    require(
        predicate_return is not None,
        "predicate mutation fixture lacks executable return",
    )
    executable_predicate = without_comments(predicate_raw)
    return_text = predicate_return.group(0)
    comment_only_predicate = executable_predicate.replace(
        return_text,
        f"/* {return_text} */\n    return TRUE;",
        1,
    )
    ignored_implementation_result = executable_predicate.replace(
        return_text,
        "IsMoveUnimplemented(move);\n"
        "    return move != MOVE_NONE && move < NUM_OF_MOVES;",
        1,
    )
    require(
        not predicate_contract_matches(
            history_source.replace(
                predicate_raw,
                comment_only_predicate,
                1,
            )
        ),
        "comment-only recordable predicate passes source contracts",
    )
    require(
        not predicate_contract_matches(
            history_source.replace(
                predicate_raw,
                ignored_implementation_result,
                1,
            )
        ),
        "ignored IsMoveUnimplemented result passes source contracts",
    )

    level_up_raw = function_body(
        pokemon_source,
        "MonTryLearnMoveOnLevelUp",
    )
    executable_level_up = without_comments(level_up_raw)
    level_up_guard = LEVEL_UP_SUCCESS_RE.search(executable_level_up)
    require(
        level_up_guard is not None,
        "level-up mutation fixture lacks success guard",
    )
    level_up_header = executable_level_up[
        level_up_guard.start():executable_level_up.find(
            "{",
            level_up_guard.start(),
            level_up_guard.end(),
        )
    ]
    ignored_level_up = executable_level_up.replace(
        level_up_header,
        "ret != (u16)-1u;\n"
        "            ret != (u16)-2u;\n"
        "            ret != MOVE_NONE;\n"
        "            if (TRUE) ",
        1,
    )
    clobbered_level_up = (
        executable_level_up[:level_up_guard.start()]
        + "ret = 0;\n            "
        + executable_level_up[level_up_guard.start():]
    )
    save_assignment_text = "SaveData *saveData = SaveBlock2_get();"
    clobbered_save = executable_level_up.replace(
        save_assignment_text,
        save_assignment_text + "\n                saveData = NULL;",
        1,
    )
    wrong_record_arguments = executable_level_up.replace(
        "saveData,\n                        &mon->box,\n                        *sp0",
        "NULL,\n                        &mon->box,\n                        MOVE_NONE",
        1,
    )
    post_record_ret_clobber = executable_level_up.replace(
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);",
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);\n"
        "                    ret = 0;",
        1,
    )
    level_transaction = LEVEL_UP_TRANSACTION_RE.search(executable_level_up)
    require(
        level_transaction is not None,
        "level-up mutation fixture lacks exact transaction",
    )
    post_guard_save_clobber = (
        executable_level_up[:level_transaction.end()]
        + "\n            saveData = NULL;"
        + executable_level_up[level_transaction.end():]
    )
    wrapped_level_up = (
        executable_level_up[:level_transaction.start()]
        + "if (FALSE) {\n"
        + executable_level_up[
            level_transaction.start():level_transaction.end()
        ]
        + "\n            }"
        + executable_level_up[level_transaction.end():]
    )
    disabled_implementation_guard = executable_level_up.replace(
        "if (!IsMoveUnimplemented(*sp0))",
        "if (FALSE)",
        1,
    )
    unreachable_guard_prefix = executable_level_up.replace(
        "#ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES",
        "goto skip_history;\n"
        "        #ifdef BLOCK_LEARNING_UNIMPLEMENTED_MOVES",
        1,
    ).replace(
        "    sys_FreeMemoryEz(levelUpLearnset);",
        "skip_history:;\n"
        "    sys_FreeMemoryEz(levelUpLearnset);",
        1,
    )
    post_transaction_raw_setter = executable_level_up.replace(
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);",
        "PokemonMoveHistory_RecordMove(\n"
        "                        saveData,\n"
        "                        &mon->box,\n"
        "                        *sp0);\n"
        "                    SetBoxMonData \n"
        "                        (&mon->box, MON_DATA_MOVE1, NULL);",
        1,
    )
    outer_region_skip = executable_level_up.replace(
        "if ((levelUpLearnset[*last_i]",
        "goto skip_all_history;\n"
        "    if ((levelUpLearnset[*last_i]",
        1,
    ).replace(
        "    sys_FreeMemoryEz(levelUpLearnset);",
        "skip_all_history:;\n"
        "    sys_FreeMemoryEz(levelUpLearnset);",
        1,
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, ignored_level_up, 1)
        ),
        "ignored level-up success results pass source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, clobbered_level_up, 1)
        ),
        "clobbered level-up helper result passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, clobbered_save, 1)
        ),
        "clobbered SaveBlock2_get result passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, wrong_record_arguments, 1)
        ),
        "wrong level-up RecordMove arguments pass source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, post_record_ret_clobber, 1)
        ),
        "post-record level-up ret clobber passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, post_guard_save_clobber, 1)
        ),
        "after-guard level-up saveData clobber passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(level_up_raw, wrapped_level_up, 1)
        ),
        "unreachable wrapped level-up transaction passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                disabled_implementation_guard,
                1,
            )
        ),
        "replaced level-up implementation guard passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                unreachable_guard_prefix,
                1,
            )
        ),
        "unreachable prefix before level-up guard passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                post_transaction_raw_setter,
                1,
            )
        ),
        "post-transaction level-up raw setter passes source contracts",
    )
    require(
        not level_up_success_contract_matches(
            pokemon_source.replace(
                level_up_raw,
                outer_region_skip,
                1,
            )
        ),
        "outer-prefix skip around level-up region passes source contracts",
    )

    record_raw = function_body(
        history_source,
        "PokemonMoveHistory_RecordMoveImpl",
    )
    executable_record = without_comments(record_raw)
    record_mutations = {
        "ignored predicate": executable_record.replace(
            "if (!PokemonMoveHistory_IsRecordableMove(move)) {\n"
            "        return FALSE;\n"
            "    }",
            "PokemonMoveHistory_IsRecordableMove(move);",
            1,
        ),
        "duplicate predicate": executable_record.replace(
            "if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            "PokemonMoveHistory_IsRecordableMove(move);\n"
            "    if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            1,
        ),
        "pre-predicate dirty mutation": executable_record.replace(
            "if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            "saveData->pokemonMoveHistoryDirty = TRUE;\n"
            "    if (!PokemonMoveHistory_IsRecordableMove(move)) {",
            1,
        ),
        "post-guard saveData clobber": executable_record.replace(
            "if (!PokemonMoveHistory_CaptureSnapshotImpl",
            "saveData = NULL;\n"
            "    if (!PokemonMoveHistory_CaptureSnapshotImpl",
            1,
        ),
        "wrong append arguments": executable_record.replace(
            "saveData,\n        &snapshot,\n        record,\n        move",
            "NULL,\n        &snapshot,\n        record,\n        MOVE_NONE",
            1,
        ),
    }
    for label, mutation in record_mutations.items():
        require(
            not record_move_contract_matches(
                history_source.replace(record_raw, mutation, 1)
            ),
            f"{label} passes RecordMoveImpl source contracts",
        )

    delete_raw = function_body(
        history_source,
        "PokemonMoveHistory_DeleteMoveSlotImpl",
    )
    executable_delete = without_comments(delete_raw)
    delete_mutations = {
        "wrong seed save": executable_delete.replace(
            "SaveBlock2_get(),",
            "NULL,",
            1,
        ),
        "wrong seed Pokémon": executable_delete.replace(
            "&pokemon->box",
            "NULL",
            1,
        ),
        "wrong delete slot": executable_delete.replace(
            "MonDeleteMoveSlot_Original(pokemon, slot);",
            "MonDeleteMoveSlot_Original(pokemon, 0);",
            1,
        ),
        "reversed delete order": executable_delete.replace(
            "PokemonMoveHistory_SeedImpl(\n"
            "        SaveBlock2_get(),\n"
            "        &pokemon->box);\n"
            "    MonDeleteMoveSlot_Original(pokemon, slot);",
            "MonDeleteMoveSlot_Original(pokemon, slot);\n"
            "    PokemonMoveHistory_SeedImpl(\n"
            "        SaveBlock2_get(),\n"
            "        &pokemon->box);",
            1,
        ),
    }
    for label, mutation in delete_mutations.items():
        require(
            not delete_move_contract_matches(
                history_source.replace(delete_raw, mutation, 1)
            ),
            f"{label} passes DeleteMoveSlotImpl source contracts",
        )

    party_raw = function_body(party_source, "PartyMenu_LearnMoveToSlot")
    executable_party = without_comments(party_raw)
    for label, mutation in {
        "wrong Pokémon": executable_party.replace("&mon->box", "NULL", 1),
        "wrong learned move": executable_party.replace(
            "partyMenu->args->moveId",
            "moveIdx",
            1,
        ),
        "swapped move and slot": executable_party.replace(
            "partyMenu->args->moveId,\n        moveIdx",
            "moveIdx,\n        partyMenu->args->moveId",
            1,
        ),
        "duplicate replacement": executable_party.replace(
            "PokemonMoveHistory_ReplaceMove(",
            "PokemonMoveHistory_ReplaceMove(&mon->box, "
            "partyMenu->args->moveId, moveIdx);\n"
            "    PokemonMoveHistory_ReplaceMove(",
            1,
        ),
        "unreachable replacement": executable_party.replace(
            "PokemonMoveHistory_ReplaceMove(",
            "if (FALSE) {\n"
            "        PokemonMoveHistory_ReplaceMove(",
            1,
        ).replace(
            "moveIdx);\n    if (partyMenu->args->itemId",
            "moveIdx);\n    }\n"
            "    if (partyMenu->args->itemId",
            1,
        ),
        "raw pre-replacement setter": executable_party.replace(
            "PokemonMoveHistory_ReplaceMove(",
            "SetBoxMonData(&mon->box, MON_DATA_MOVE1 + moveIdx, NULL);\n"
            "    PokemonMoveHistory_ReplaceMove(",
            1,
        ),
        "spaced post-replacement setter": executable_party.replace(
            "moveIdx);\n    if (partyMenu->args->itemId",
            "moveIdx);\n"
            "    SetBoxMonData \n"
            "        (&mon->box, MON_DATA_MOVE1 + moveIdx, NULL);\n"
            "    if (partyMenu->args->itemId",
            1,
        ),
    }.items():
        require(
            not party_menu_contract_matches(
                party_source.replace(party_raw, mutation, 1)
            ),
            f"{label} passes PartyMenu replacement source contracts",
        )


def source_contracts() -> None:
    header = (REPO / "include/pokemon_move_history.h").read_text()
    history = (
        REPO / "src/pokemon_move_history_overlay/pokemon_move_history.c"
    ).read_text()
    relearn = (
        REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
    ).read_text()
    pokemon = (REPO / "src/pokemon.c").read_text()
    overworld_wild = (REPO / "src/overworld_wild_spawns.c").read_text()
    task6 = (
        REPO
        / "src/pokemon_move_history_task6_overlay/"
        "pokemon_move_history_task6.c"
    ).read_text()
    task6_entry = (
        REPO / "asm/pokemon_move_history_task6_overlay/entry.s"
    ).read_text()
    task6_linker = (
        REPO / "src/pokemon_move_history_task6_overlay/linker.ld"
    ).read_text()
    party_menu = (REPO / "src/party_menu.c").read_text()
    save = (REPO / "src/save.c").read_text()
    entry = (REPO / "asm/pokemon_move_history_overlay/entry.s").read_text()
    linker = (
        REPO / "src/pokemon_move_history_overlay/linker.ld"
    ).read_text()
    rom_ld = (REPO / "rom.ld").read_text()
    patches = (
        REPO / "armips/asm/pokemon_move_history_capture.s"
    ).read_text()
    hooks = (REPO / "hooks").read_text()
    makefile = (REPO / "Makefile").read_text()
    build_wrapper = (REPO / "docker-makerom.cmd").read_text()
    config = (REPO / "include/config.h").read_text()
    evolution = (
        REPO / "src/individual/GetMonEvolutionInternal.c"
    ).read_text()
    evolution_macros = (REPO / "armips/include/macros.s").read_text()
    parent_builder = (
        REPO / "scripts/build_move_relearn_parents.py"
    ).read_text()
    script_commands = (
        REPO / "src/field/script_commands.c"
    ).read_text()
    symbol_builder = (
        REPO / "scripts/generate_armips_symbols.py"
    ).read_text()
    require(
        outer_make_invocation_is_safe(),
        "outer Make invocation contains unsafe flags or command variables",
    )
    require(
        trusted_pre_make_sources_are_exact(makefile),
        "pre-Make source/dependency trust gate differs",
    )
    require(
        outer_make_invocation_is_safe({})
        and outer_make_invocation_is_safe(
            {
                "MAKEFLAGS":
                    "w -j --jobserver-fds=3,4 -- "
                    "VENV=/tmp/hg-engine-venv",
                "MAKELEVEL": "1",
                "MAKEOVERRIDES": "${-*-command-variables-*-}",
                "MFLAGS": "-w -j --jobserver-fds=3,4",
                "VENV": MANAGED_BUILD_VENV,
            }
        ),
        "known direct/managed outer Make invocations fail authentication",
    )
    for label, environment in {
        "ignore errors": {"MAKEFLAGS": "-i"},
        "keep going": {"MAKEFLAGS": "-k"},
        "redirected ROM": {
            "MAKEFLAGS": "-- BUILDROM=attacker.nds",
            "MAKEOVERRIDES": "${-*-command-variables-*-}",
        },
        "injected recipe variable": {
            "MAKEFLAGS": "-- ARMIPS_FLAGS=;cp rom.nds test.nds",
            "MAKEOVERRIDES": "${-*-command-variables-*-}",
        },
        "unexpected override metadata": {
            "MAKEOVERRIDES": "${-*-command-variables-*-}",
        },
        "injected makefile": {"MAKEFILES": "/tmp/attacker.mk"},
        "GNU ignore errors": {"GNUMAKEFLAGS": "-i"},
        "legacy ignore errors": {"MFLAGS": "-i"},
        "battle test mode": {"AUTO_TEST": "Y"},
    }.items():
        require(
            not outer_make_invocation_is_safe(environment),
            f"{label} outer Make invocation passes authentication",
        )
    expected_managed_environment = managed_build_environment()
    require(
        managed_build_environment_is_exact(expected_managed_environment)
        and build_wrapper.count(
            "/usr/bin/python3 "
            "scripts/verify_pokemon_move_history_capture.py "
            "--managed-build-clean"
        )
        == 2
        and build_wrapper.count("/usr/bin/env -i") == 4
        and build_wrapper.count("--workdir /hg-engine") == 2
        and "/bin/bash" not in build_wrapper
        and "--pre-make && make" not in build_wrapper
        and " && make " not in build_wrapper,
        "Docker wrapper does not exclusively use the scrubbed managed-build "
        "entry",
    )
    for name, value in {
        "MAKEFILES": "/tmp/attacker.mk",
        "GNUMAKEFLAGS": "-i",
        "MFLAGS": "-i",
        "AUTO_TEST": "Y",
        "ARMIPS": "/tmp/attacker-armips",
        "CC": "/tmp/attacker-cc",
    }.items():
        polluted_environment = {
            **expected_managed_environment,
            name: value,
        }
        require(
            not managed_build_environment_is_exact(polluted_environment)
            and name not in managed_build_environment(),
            f"{name} survives the managed-build environment scrub",
        )
    with tempfile.TemporaryDirectory(
        prefix="move-history-managed-environment-"
    ) as managed_fixture_directory:
        managed_fixture_root = Path(managed_fixture_directory)
        injected_makefile = managed_fixture_root / "injected.mk"
        injected_sentinel = managed_fixture_root / "make-injection-ran"
        injected_makefile.write_text(
            "override BUILDROM = attacker.nds\n"
            f"SIDE_EFFECT := $(file >{injected_sentinel},corrupted)\n"
        )

        def managed_path_snapshot(path: Path) -> tuple[object, ...]:
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                return ("missing",)
            if path.is_symlink():
                return ("symlink", metadata.st_ino, os.readlink(path))
            if path.is_file():
                return ("file", metadata.st_ino, path.read_bytes())
            return ("other", metadata.st_ino, metadata.st_mode)

        protected_paths = (
            REPO / "test.nds",
            REPO / "test.nds.tmp",
            REPO / "build/pokemon_move_history_capture_build.json",
            REPO / "build/pokemon_move_history_capture_build.json.tmp",
            REPO
            / "build/pokemon_move_history_capture_build.json.publish-journal",
            injected_makefile,
            injected_sentinel,
        )
        protected_before = {
            path: managed_path_snapshot(path)
            for path in protected_paths
        }
        for label, injection in {
            "MAKEFILES parse injection": {
                "MAKEFILES": str(injected_makefile),
            },
            "GNU ignore errors": {"GNUMAKEFLAGS": "-i"},
            "legacy Make flags": {"MFLAGS": "-i"},
            "AUTO_TEST build mode": {"AUTO_TEST": "Y"},
            "tool override": {"ARMIPS": "/tmp/attacker-armips"},
        }.items():
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--managed-build-probe",
                ],
                cwd=REPO,
                env={**os.environ, **injection},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            try:
                observed_environment = json.loads(completed.stdout)
            except json.JSONDecodeError:
                observed_environment = None
            require(
                completed.returncode == 0
                and observed_environment == expected_managed_environment
                and {
                    path: managed_path_snapshot(path)
                    for path in protected_paths
                }
                == protected_before,
                f"{label} survives or mutates the managed wrapper handoff",
            )
        make_probe = managed_fixture_root / "Makefile"
        make_probe_output = managed_fixture_root / "origins.txt"
        make_flags_output = managed_fixture_root / "gnu-make-flags.txt"
        origin_names = (
            "ALL_C_SRCS",
            "ARMIPS",
            "AUTO_TEST",
            "BUILDROM",
            "CC",
            "DEVKITARM",
            "GNUMAKEFLAGS",
            "MAKE",
            "MAKEFILES",
            "MOVE_HISTORY_CAPTURE_MANIFEST",
            "MOVE_HISTORY_CAPTURE_MANIFEST_TMP",
            "PYTHON",
            "REQUIRED_DIRECTORIES",
            "SHELL",
            "TEST_FILTER",
        )
        expected_origins = {
            name: (
                "default"
                if name in {"MAKE", "MAKEFILES", "SHELL"}
                else "undefined"
            )
            for name in origin_names
        }
        make_probe.write_text(
            "fail:\n"
            "\t@false\n"
            "origins:\n"
            "\t@printf '%s\\n' "
            + " ".join(
                f"'$(origin {name})'"
                for name in origin_names
            )
            + f" > {make_probe_output}\n"
            f"\t@printf '%s' '$(GNUMAKEFLAGS)' > {make_flags_output}\n"
        )
        failure_probe = subprocess.run(
            ["make", "-Rr", "-f", str(make_probe), "fail"],
            cwd=managed_fixture_root,
            env=expected_managed_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        origin_probe = subprocess.run(
            ["make", "-Rr", "-f", str(make_probe), "origins"],
            cwd=managed_fixture_root,
            env=expected_managed_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        observed_origins = make_probe_output.read_text().splitlines()
        expected_origin_lines = [
            expected_origins[name]
            for name in origin_names
        ]
        gnu_flags_index = origin_names.index("GNUMAKEFLAGS")
        origin_matches = observed_origins == expected_origin_lines
        if not origin_matches and len(observed_origins) == len(origin_names):
            gnu_make_43_origins = list(expected_origin_lines)
            gnu_make_43_origins[gnu_flags_index] = "override"
            origin_matches = observed_origins == gnu_make_43_origins
        require(
            failure_probe.returncode != 0
            and origin_probe.returncode == 0
            and origin_matches
            and make_flags_output.read_bytes() == b""
            and not injected_sentinel.exists()
            and {
                path: managed_path_snapshot(path)
                for path in protected_paths
            }
            == protected_before,
            "real GNU Make probe inherited controls, ignored failure, or "
            "changed protected artifacts",
        )
    header_code = without_comments(header)
    history_code = without_comments(history)
    pokemon_code = without_comments(pokemon)
    party_menu_code = without_comments(party_menu)
    config_code = without_comments(config)

    require(
        "build/save.d" in DEPENDENCY_FILES
        and "build/field/script_commands.d" in DEPENDENCY_FILES
        and "scripts/generate_armips_symbols.py" in FIXED_INPUTS
        and "src/field/linker.ld" in FIXED_INPUTS
        and OUTPUTS.get("save_object") == "build/save.o",
        "save/field lifecycle and generator provenance inputs are not sealed",
    )
    require(
        OUTPUTS.get("field_script_commands_object")
        == "build/field/script_commands.o"
        and OUTPUTS.get("field_linked") == "build/field_linked.o"
        and OUTPUTS.get("field_binary") == "build/output_field.bin"
        and OUTPUTS.get("patched_overlay131")
        == "base/overlay/overlay_0131.bin",
        "scripted daycare field binary/package provenance is not sealed",
    )
    for runtime_evidence_input in (
        "scripts/launch_summary_move_relearn_runtime.py",
        "scripts/verify_summary_move_relearn_runtime.py",
        "scripts/pokemon_move_history_build_manifest.py",
        "scripts/headless-overworld-test.py",
        "scripts/verify_pokemon_move_history_party_integrity.py",
        "scripts/build_summary_move_relearn_native_bootstrap.sh",
        "scripts/generate_summary_move_relearn_native_inventory.py",
        "scripts/summary_move_relearn_native_bootstrap.c",
        "scripts/summary_move_relearn_native_inventory.txt",
        "scripts/summary_move_relearn_protected_spawn.py",
        "scripts/summary_move_relearn_protected_spawn.swift",
    ):
        require(
            FIXED_INPUTS.count(runtime_evidence_input) == 1,
            f"runtime evidence input is not uniquely sealed: "
            f"{runtime_evidence_input}",
        )
    require(
        len(FIXED_INPUTS) == len(set(FIXED_INPUTS)),
        "fixed manifest inputs contain duplicate paths",
    )

    for api in (
        "PokemonMoveHistory_ReplaceMove",
        "PokemonMoveHistory_DeleteMoveSlot",
    ):
        require(
            re.search(rf"\bLONG_CALL\s+{api}\s*\(", header_code) is not None,
            f"{api} is not a typed long-call API",
        )

    require(
        predicate_contract_matches(history),
        "recordable-move predicate is not the exact executable valid/range/"
        "implemented expression",
    )
    require(
        append_guard_contract_matches(history),
        "AppendMove does not execute and consume exactly one recordable-move "
        "predicate before mutation",
    )
    query_record = function_body(
        history_code,
        "PokemonMoveHistory_QueryRecord",
    )
    query_observing = function_body(
        history_code,
        "PokemonMoveHistory_QueryImpl",
    )
    query_read_only = function_body(
        history_code,
        "PokemonMoveHistory_QueryReadOnlyImpl",
    )
    require(
        query_observing.count("PokemonMoveHistory_QueryRecord(") == 1
        and "TRUE" in query_observing
        and "FALSE" not in query_observing
        and query_read_only.count("PokemonMoveHistory_QueryRecord(") == 1
        and "FALSE" in query_read_only
        and "TRUE" not in query_read_only,
        "observing/read-only query wrappers do not select distinct exact paths",
    )
    require(
        query_record.count("PokemonMoveHistory_ObserveSnapshot(") == 1
        and query_record.count("PokemonMoveHistory_FindRecord(") == 1
        and query_record.index("if (observe)")
        < query_record.index("PokemonMoveHistory_ObserveSnapshot(")
        < query_record.index("else if (saveData == NULL")
        < query_record.index("PokemonMoveHistory_FindRecord("),
        "shared query does not branch from observation to lookup-only access",
    )
    for mutation in (
        "PokemonMoveHistory_AllocateStore(",
        "PokemonMoveHistory_AllocateRecord(",
        "PokemonMoveHistory_AppendMove(",
        "pokemonMoveHistoryDirty",
        "pokemonMoveHistoryRevision",
        "nextAccessSequence",
    ):
        require(
            mutation not in query_record and mutation not in query_read_only,
            f"read-only history query contains mutation path {mutation!r}",
        )
    append = function_body(history_code, "PokemonMoveHistory_AppendMove")
    append_guard = APPEND_RECORDABLE_GUARD_RE.search(append)
    require(append_guard is not None, "AppendMove executable guard is missing")
    ordered(
        append,
        [
            append_guard.group(0),
            "for (i = 0; i < record->moveCount; i++)",
            "if (record->moveCount == POKEMON_MOVE_HISTORY_MAX_MOVES)",
            "record->moveCount--;",
            "store = saveData->pokemonMoveHistory;",
            "record->moves[record->moveCount++] = move;",
            "record->lastTouched = ++store->header.nextAccessSequence;",
            "saveData->pokemonMoveHistoryDirty = TRUE;",
            "saveData->pokemonMoveHistoryRevision++;",
        ],
        "AppendMove predicate and mutation transaction",
    )
    for mutation in (
        "PokemonMoveHistory_OverlayMemcpy(",
        "record->moveCount--;",
        "record->moves[record->moveCount++] = move;",
        "record->speciesSnapshot = snapshot->species;",
        "record->lastTouched = ++store->header.nextAccessSequence;",
        "saveData->pokemonMoveHistoryDirty = TRUE;",
        "saveData->pokemonMoveHistoryRevision++;",
    ):
        require(
            append.find(mutation) > append_guard.end(),
            f"AppendMove mutation {mutation!r} can precede its executable "
            "predicate",
        )
    require(
        re.search(
            r"^\s*#\s*define\s+BLOCK_LEARNING_UNIMPLEMENTED_MOVES(?:\s|$)",
            config_code,
            re.MULTILINE,
        )
        is not None,
        "host unimplemented-move fixture requires the runtime policy enabled",
    )
    source_matcher_mutation_fixtures(history, pokemon, party_menu)
    for name in (
        "SaveData_New",
        "Save_InitDynamicRegion",
        "Save_LoadDynamicRegion",
        "Save_WriteManInit",
        "Save_PrepareForAsyncWrite",
        "Save_WriteFileAsync",
        "Save_WriteManFinish",
        "CancelAsyncSaveWithMoveHistory",
        "Save_Cancel",
    ):
        require(
            lifecycle_contract_matches(save, name),
            f"{name} complete executable lifecycle source differs",
        )
    for name in (
        "PokemonMoveHistory_SeedParty",
        "PokemonMoveHistory_LoadAndSeedPartyImpl",
        "PokemonMoveHistory_PrepareSaveImpl",
        "PokemonMoveHistory_FinishSaveImpl",
        "PokemonMoveHistory_CancelSaveImpl",
    ):
        require(
            lifecycle_contract_matches(history, name),
            f"{name} complete executable lifecycle source differs",
        )
    lifecycle_source_mutation_fixtures(save, history)

    replace_code = function_body(
        history_code,
        "PokemonMoveHistory_ReplaceMoveImpl",
    )
    ordered(
        replace_code,
        [
            "PokemonMoveHistory_IsRecordableMove(move)",
            "GetBoxMonData(",
            "MON_DATA_MOVE1 + slot",
            "NULL) == move",
            "PokemonMoveHistory_CaptureSnapshotImpl",
            "SaveBlock2_get()",
            "PokemonMoveHistory_ObserveSnapshot",
            "SetBoxMonData(pokemon, MON_DATA_MOVE1 + slot",
            "GetBoxMonData(pokemon, MON_DATA_MOVE1 + slot",
            "before.moves[slot] = move",
            "PokemonMoveHistory_AppendMove",
        ],
        "replacement transaction",
    )
    require(
        re.search(
            r"if\s*\(\s*\(u16\)\s*GetBoxMonData\s*\("
            r"\s*pokemon\s*,\s*MON_DATA_MOVE1\s*\+\s*slot\s*,"
            r"\s*NULL\s*\)\s*==\s*move\s*\)\s*\{"
            r"\s*return\s+FALSE\s*;\s*\}",
            replace_code,
            re.DOTALL,
        )
        is not None,
        "same-slot replacement does not return FALSE before full snapshot",
    )
    require(
        "before.moves[slot] == move" not in replace_code,
        "same-slot replacement still depends on the full snapshot",
    )
    require(
        re.search(
            r"if\s*\(\s*!PokemonMoveHistory_CaptureSnapshotImpl\s*\("
            r"[^)]*\)\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}",
            replace_code,
            re.DOTALL,
        )
        is not None,
        "snapshot failure does not return FALSE before mutation",
    )
    require(
        replace_code.count("SaveBlock2_get()") == 1,
        "replacement does not resolve exactly one current save per transaction",
    )
    require(
        record_move_contract_matches(history),
        "RecordMoveImpl is not the exact guarded capture/observe/append "
        "transaction",
    )
    record_move_code = function_body(
        history_code,
        "PokemonMoveHistory_RecordMoveImpl",
    )
    ordered(
        record_move_code,
        [
            "PokemonMoveHistory_IsRecordableMove(move)",
            "PokemonMoveHistory_CaptureSnapshotImpl",
            "PokemonMoveHistory_ObserveSnapshot",
            "PokemonMoveHistory_AppendMove",
        ],
        "record-move transaction",
    )
    require(
        re.search(
            r"if\s*\(\s*!PokemonMoveHistory_IsRecordableMove\s*\("
            r"\s*move\s*\)\s*\)\s*\{\s*return\s+FALSE\s*;\s*\}",
            record_move_code,
            re.DOTALL,
        )
        is not None,
        "RecordMove invalid guard does not return FALSE before snapshot access",
    )
    require(
        delete_move_contract_matches(history),
        "DeleteMoveSlotImpl does not use the exact seed-before-delete call flow",
    )
    delete = function_body(
        history_code,
        "PokemonMoveHistory_DeleteMoveSlotImpl",
    )
    ordered(
        delete,
        [
            "PokemonMoveHistory_SeedImpl",
            "SaveBlock2_get()",
            "MonDeleteMoveSlot_Original",
        ],
        "move deletion transaction",
    )

    level_up = function_body(pokemon_code, "MonTryLearnMoveOnLevelUp")
    require(
        level_up_success_contract_matches(pokemon),
        "level-up history recording is not controlled by the exact successful "
        "append result",
    )
    ordered(
        level_up,
        [
            "ret = TryAppendMonMove(mon, *sp0);",
            "ret != (u16)-1u",
            "ret != (u16)-2u",
            "ret != MOVE_NONE",
            "SaveBlock2_get()",
            "PokemonMoveHistory_RecordMove",
        ],
        "level-up append",
    )

    learn_slot = function_body(
        party_menu_code,
        "PartyMenu_LearnMoveToSlot",
    )
    require(
        party_menu_contract_matches(party_menu),
        "party-menu learning does not call exact "
        "ReplaceMove(&mon->box, moveId, moveIdx)",
    )
    require(
        "SetMonData(" not in learn_slot,
        "party-menu replacement still mutates outside the central transaction",
    )

    seed_party_code = function_body(
        history_code,
        "PokemonMoveHistory_SeedParty",
    )
    require(
        "Party_GetCount(party)" in seed_party_code
        and "Party_GetMonByIndex(party, i)" in seed_party_code,
        "party reconciliation does not use canonical accessors",
    )
    for forbidden in (
        "party->count",
        "party->members",
        "sizeof(struct PartyPokemon)",
        "0xEC",
        "0xF0",
    ):
        require(
            forbidden not in seed_party_code,
            f"party reconciliation contains forbidden stride/count access {forbidden}",
        )
    load_boundary = function_body(
        history_code,
        "PokemonMoveHistory_LoadAndSeedPartyImpl",
    )
    require(
        "PokemonMoveHistory_SeedParty" not in load_boundary,
        "party reconciliation runs before the active save is boot-stable",
    )
    save_boundary = function_body(
        history_code,
        "PokemonMoveHistory_PrepareSaveImpl",
    )
    ordered(
        save_boundary,
        [
            "PokemonMoveHistory_SeedParty(saveData);",
            "PokemonMoveHistory_CommitIfDirtyImpl(saveData);",
        ],
        "normal-save ownership reconciliation",
    )

    for offset, entry_name, alias_name in (
        (0x80, "ReplaceMove", "PokemonMoveHistory_ReplaceMove"),
        (0x88, "DeleteMoveSlot", "PokemonMoveHistory_DeleteMoveSlot"),
    ):
        require(
            f"MoveHistoryEntry_{entry_name}" in entry
            and f"ORIGIN(rom) + 0x{offset:X}" in linker
            and f"{alias_name} = 0x{OVERLAY_BASE + offset:08X} | 1;"
            in rom_ld,
            f"{entry_name} fixed overlay ABI is incomplete",
        )

    require(
        "PokemonMoveHistory_SetPartyMove" not in hooks,
        "obsolete full PartyMonSetMoveInSlot hook remains",
    )
    for address in (
        "0x0204DCCC",
        "0x020542E0",
        "0x020769F0",
        "0x02246344",
        "0x021E6158",
    ):
        require(address in patches, f"confirmed commit patch {address} is missing")
    for forbidden in (
        "021E60D8",  # yes/no prompt
        "022462D8",  # battle cancel/give-up neighborhood
        "PartyMenu_CheckCanLearnTMHMMove",
    ):
        require(
            forbidden not in patches,
            f"preview/cancel path unexpectedly owns history: {forbidden}",
        )
    reminder_patch = patches[
        patches.index(".org 0x021E6158"):patches.index(".endarea", patches.index(".org 0x021E6158"))
    ]
    require(
        "bl PokemonMoveHistory_ReplaceMove" in reminder_patch
        and re.search(r"\n\s+nop\s*(?:\n|$)", reminder_patch) is not None,
        "Move Reminder replacement does not fill the complete 14-byte span",
    )

    # Task 6: unusual scripted/transfer/form/daycare transaction ownership.
    capture_snapshot = function_body(
        without_comments(history),
        "PokemonMoveHistory_CaptureSnapshotImpl",
    )
    require(
        "!PokemonMoveHistoryTask6_IsCanonical(pokemon)"
        in capture_snapshot,
        "history capture does not fail closed through the canonical owner gate",
    )
    canonical = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_IsCanonicalImpl",
    )
    for fragment in (
        "MON_DATA_CHECKSUM_FAILED",
        "MON_DATA_SPECIES_EXISTS",
        "MON_DATA_IS_EGG",
        "SPECIES_BAD_EGG",
        "form >= 32",
        "SPECIES_CASTFORM",
        "SPECIES_CHERRIM",
        "SanitizeFormNumber",
        "NEEDS_REVERSION",
    ):
        require(fragment in canonical, f"canonical owner gate lost {fragment}")

    daycare_commit = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_DaycareDepositCommitImpl",
    )
    ordered(
        daycare_commit,
        ["retailCommit(", "PokemonMoveHistory_Seed("],
        "daycare deposit commit",
    )
    trade_commit = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_TradeReplacePartySlotImpl",
    )
    ordered(
        trade_commit,
        [
            "PokemonMoveHistory_CaptureSnapshot(",
            "retailCommit(",
            "PokemonMoveHistory_RecordSnapshot(",
            "PokemonMoveHistory_Seed(",
        ],
        "NPC trade slot replacement",
    )
    hatch_commit = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_HatchClearEggImpl",
    )
    ordered(
        hatch_commit,
        ["SetMonData(", "PokemonMoveHistory_Seed("],
        "hatch baseline",
    )
    swap_move = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl",
    )
    require(
        "if (recordPermanentHistory)" in swap_move
        and "PokemonMoveHistory_ReplaceMove(" in swap_move
        and "SetMonData(" in swap_move,
        "permanent/transient special-form move split differs",
    )
    special_form_sources = pokemon + "\n" + task6
    special_form_swap_calls = (
        special_form_sources.count("SwapPartyPokemonMove(")
        + special_form_sources.count(
            "PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl("
        )
    )
    require(
        special_form_swap_calls >= 15
        and len(re.findall(
            r"SwapPartyPokemonMove\s*\([^;]*?,\s*TRUE\s*\);",
            special_form_sources,
            re.S,
        )) >= 5
        and special_form_sources.count(", FALSE);") >= 10,
        "special-form call sites do not classify permanent and battle copies",
    )

    place_seed = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_PCStoragePlaceAndSeedImpl",
    )
    ordered(
        place_seed,
        [
            "PCStorage_PlaceMonInBoxByIndexPair(",
            "PCStorage_GetMonByIndexPair(",
            "PokemonMoveHistory_Seed(",
        ],
        "Pokewalker successful placement",
    )
    gts_place_seed = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_GTSPlaceAndSeedImpl",
    )
    ordered(
        gts_place_seed,
        [
            "PCStorage_FindFirstEmptySlot(",
            "retailCommit(",
            "PCStorage_GetMonByIndexPair(",
            "PokemonMoveHistory_Seed(",
        ],
        "GTS boxed receive placement",
    )
    require(
        "resolvedBox != (int)boxno" in gts_place_seed
        and "resolvedSlot >= MONS_PER_BOX" in gts_place_seed
        and "(GTSPlaceBoxRetailFunc)0x02073BFD" in gts_place_seed,
        "GTS boxed receive does not fail closed on destination drift",
    )
    gts_delete_box = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_GTSDeleteBoxAndRecordImpl",
    )
    ordered(
        gts_delete_box,
        [
            "PokemonMoveHistory_CaptureSnapshot(",
            "retailCommit(",
            "PokemonMoveHistory_RecordSnapshot(",
        ],
        "GTS boxed outgoing removal",
    )
    gts_remove_party = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_GTSRemovePartyAndRecordImpl",
    )
    ordered(
        gts_remove_party,
        [
            "PokemonMoveHistory_CaptureSnapshot(",
            "result = retailCommit(",
            "if (result && captured)",
            "PokemonMoveHistory_RecordSnapshot(",
            "return result;",
        ],
        "GTS party outgoing removal",
    )
    export_stage = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_PCStorageGetAndStageImpl",
    )
    ordered(
        export_stage,
        [
            "PCStorage_GetMonByIndexPair(",
            "sPokewalkerPendingValid = FALSE;",
            "PokemonMoveHistory_CaptureSnapshot(",
            "sPokewalkerPendingValid = TRUE;",
            "return pokemon;",
        ],
        "Pokewalker export pending stage",
    )
    require(
        "PokemonMoveHistory_Seed(" not in export_stage
        and "PokemonMoveHistory_RecordSnapshot(" not in export_stage
        and "SaveBlock2_get(" not in export_stage,
        "Pokewalker export stage can mutate persisted history",
    )
    walker_success = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl",
    )
    ordered(
        walker_success,
        [
            "retailSuccess(pokewalker);",
            "if (!sPokewalkerPendingValid)",
            "sPokewalkerPendingValid = FALSE;",
            "PokemonMoveHistory_RecordSnapshot(",
        ],
        "Pokewalker irreversible radio success",
    )
    walker_recovery = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscardImpl",
    )
    ordered(
        walker_recovery,
        [
            "if (pokewalkerApp != NULL)",
            "retailRecovery(pokewalkerApp);",
            "sPokewalkerPendingValid = FALSE;",
        ],
        "Pokewalker recovery discard",
    )
    require(
        "PokemonMoveHistory_Seed(" not in walker_recovery
        and "PokemonMoveHistory_RecordSnapshot(" not in walker_recovery,
        "Pokewalker recovery diagnostic boundary mutates persisted history",
    )
    diagnostic_poll = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_PokewalkerDiagnosticPollImpl",
    )
    ordered(
        diagnostic_poll,
        [
            "if (mailbox->magic != "
            "POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_MAGIC)",
            "requestSequence = mailbox->requestSequence;",
            "mailbox->magic = 0;",
            "mailbox->status = "
            "POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_RUNNING;",
            "requestSequence != mailbox->completionSequence + 1",
            "saveData = SaveBlock2_get();",
            "storage = (PCStorage *)SaveArray_Get(",
            "switch (operation)",
            "PokemonMoveHistoryTask6_PCStorageGetAndStage(",
            "PokemonMoveHistoryTask6_PokewalkerRadioSuccess(",
            "PokemonMoveHistoryTask6_PokewalkerRadioSuccessSecond(",
            "PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscard(NULL);",
            "mailbox->status = "
            "POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_COMPLETE;",
            "mailbox->completionSequence = requestSequence;",
        ],
        "ROM-executed Pokewalker diagnostic mailbox",
    )
    require(
        "#define TASK6_SAVE_PCSTORAGE 41" in task6
        and "TASK6_POKEWALKER_DIAGNOSTIC_WORDS" in task6
        and "boxno >= NUM_PC_BOXES" in diagnostic_poll
        and "slotno >= MONS_PER_BOX" in diagnostic_poll
        and "requestSequence == 0" in diagnostic_poll
        and diagnostic_poll.count(
            "POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_REJECTED"
        ) >= 4,
        "Pokewalker diagnostic validation/save ownership differs",
    )
    field_ready_poll = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_FieldReadyDiagnosticPollImpl",
    )
    ordered(
        field_ready_poll,
        [
            "(OverworldFieldReadyRetailPollFunc)0x023C8011;",
            "retailPoll(fieldSystem);",
            "PokemonMoveHistoryTask6_PokewalkerDiagnosticPollImpl();",
        ],
        "field-ready retail-preserving diagnostic poll",
    )
    field_ready_task = function_body(
        without_comments(overworld_wild),
        "OverworldWildSpawns_FieldReadyTask",
    )
    require(
        field_ready_task.count(
            "OverworldFollowerSelectorTaskPollEntry(fieldSystem);"
        ) == 1
        and ".set OverworldFollowerSelectorTaskPollEntry, 0x023BD4A1"
        in overworld_wild
        and '#include "../include/pokemon_move_history.h"'
        not in overworld_wild
        and "if (fieldSystem != gFieldSysPtr)" in field_ready_task
        and "if (fieldSystem->taskman != NULL)" in field_ready_task,
        "field-ready diagnostic hook owner/calling context differs",
    )
    require(
        "sizeof(PokemonMoveHistoryTask6DiagnosticMailbox) == 0x30"
        in task6
        and "POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_MAGIC 0x36574B50"
        in header
        and "POKEMON_MOVE_HISTORY_TASK6_DIAGNOSTIC_STATUS_COMPLETE "
        "0xC0016D48" in header,
        "Pokewalker diagnostic mailbox ABI differs",
    )
    sanitizer = function_body(
        without_comments(script_commands),
        "ScrCmd_DaycareSanitizeMon",
    )
    script_teach = function_body(
        without_comments(task6),
        "PokemonMoveHistoryTask6_ScriptTeachMoveImpl",
    )
    require(
        '#include "../../include/pokemon_move_history.h"'
        in script_commands
        and sanitizer.count(
            "PokemonMoveHistoryTask6_ScriptTeachMove("
        )
        == 2
        and sanitizer.count("if (temp_egg_moves[i]") == 1
        and sanitizer.count(
            "inheriterMoves[i] = GetBoxMonData("
            "daycareMon, MON_DATA_MOVE1 + i, NULL);"
        )
        == 1
        and "if (baby_egg_moves[i] != inheriterMoves[0]"
        in sanitizer,
        "daycare sanitizer owner/buffer history coverage differs",
    )
    ordered(
        sanitizer,
        [
            "pp = GetMoveMaxPP((u16)newMove, 0);",
            "PokemonMoveHistoryTask6_ScriptTeachMove(\n"
            "                                fieldSystem->savedata,\n"
            "                                &partyMon->box,\n"
            "                                (newMove << 8)\n"
            "                                    | potentialOverrideMoveSlot,\n"
            "                                pp);",
        ],
        "party daycare sanitizer move commit",
    )
    ordered(
        sanitizer,
        [
            "pp = GetMoveMaxPP((u16)newMove, 0);",
            "PokemonMoveHistoryTask6_ScriptTeachMove(\n"
            "                                fieldSystem->savedata,\n"
            "                                daycareMon,\n"
            "                                (newMove << 8)\n"
            "                                    | potentialOverrideMoveSlot,\n"
            "                                pp);",
        ],
        "deposited daycare sanitizer move commit",
    )
    ordered(
        script_teach,
        [
            "u32 moveSlot = encodedMoveSlot & 0xFF;",
            "u32 move = encodedMoveSlot >> 8;",
            "u32 ppUps = 0;",
            "SetBoxMonData(pokemon, MON_DATA_MOVE1 + moveSlot, &move);",
            "SetBoxMonData(pokemon, MON_DATA_MOVE1PPUP + moveSlot, &ppUps);",
            "SetBoxMonData(pokemon, MON_DATA_MOVE1PP + moveSlot, &pp);",
            "PokemonMoveHistory_RecordMove(saveData, pokemon, (u16)move);",
        ],
        "resident scripted daycare transaction",
    )
    for address in (
        "0x02074562",
        "0x0206BF04",
        "0x0206BF98",
        "0x02071EE0",
        "0x02071F20",
        "0x02071F2C",
        "0x02071F64",
        "0x02071F80",
        "0x02071F98",
        "0x02091156",
        "0x02259B7A",
        "0x0221F6C4",
        "0x02240B72",
        "0x02240C76",
        "0x02240A0E",
        "0x02240A44",
        "0x021EE65A",
        "0x021ED41A",
        "0x021EDBEE",
        "0x021EC0AA",
        "0x021EE86A",
        "0x021EEB8C",
        "0x021EEC7E",
    ):
        require(address in patches, f"task-6 commit patch {address} is missing")
    require(
        ".org 0x021EC182" not in patches,
        "Pokewalker failure-recovery placement dirties history",
    )
    require(
        "PokemonMoveHistory_PlayerPartyAddCommit equ 0x023BD438"
        in patches
        and "PokemonMoveHistory_DaycareShiftAndAppend equ 0x023BD440"
        in patches
        and "MoveHistoryTask6Entry_PlayerPartyAddCommit:" in task6_entry
        and "MoveHistoryTask6Entry_DaycareShiftAndAppend:" in task6_entry
        and "MoveHistoryTask6Entry_CorrectBattleFormMoves:" in task6_entry
        and "MoveHistoryTask6Entry_MarkHistoryMove:" in task6_entry
        and "MoveHistoryTask6Entry_AppendCandidate:" in task6_entry
        and "MoveHistoryTask6Entry_ScriptTeachMove:" in task6_entry
        and "MoveHistoryTask6Entry_GTSPlaceAndSeed:" in task6_entry
        and "MoveHistoryTask6Entry_GTSDeleteBoxAndRecord:" in task6_entry
        and "MoveHistoryTask6Entry_GTSRemovePartyAndRecord:" in task6_entry
        and "MoveHistoryTask6Entry_PokewalkerRadioSuccess:" in task6_entry
        and "MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond:"
        in task6_entry
        and "MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard:" in task6_entry
        and "MoveHistoryTask6Entry_PokewalkerDiagnosticReturn:"
        in task6_entry
        and "MoveHistoryTask6Entry_FieldReadyDiagnosticPoll:"
        in task6_entry
        and "ORIGIN(rom) + 0x38" in task6_linker
        and "ORIGIN(rom) + 0x40" in task6_linker
        and "ORIGIN(rom) + 0x48" in task6_linker
        and "ORIGIN(rom) + 0x50" in task6_linker
        and "ORIGIN(rom) + 0x58" in task6_linker
        and "ORIGIN(rom) + 0x60" in task6_linker
        and "ORIGIN(rom) + 0x64" in task6_linker
        and "ORIGIN(rom) + 0x68" in task6_linker
        and "ORIGIN(rom) + 0x70" in task6_linker
        and "ORIGIN(rom) + 0x78" in task6_linker
        and "ORIGIN(rom) + 0x80" in task6_linker
        and "ORIGIN(rom) + 0x88" in task6_linker
        and "ORIGIN(rom) + 0x90" in task6_linker
        and "ORIGIN(rom) + 0x98" in task6_linker
        and "ORIGIN(rom) + 0xA0" in task6_linker
        and "ORIGIN(rom) + 0xA8" in task6_linker
        and "PokemonMoveHistoryTask6_ScriptTeachMove = "
        "0x023BD464 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_GTSPlaceAndSeed = "
        "0x023BD468 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_GTSDeleteBoxAndRecord = "
        "0x023BD470 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_GTSRemovePartyAndRecord = "
        "0x023BD478 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_PCStorageGetAndStage = "
        "0x023BD420 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_PokewalkerRadioSuccess = "
        "0x023BD480 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_PokewalkerRadioSuccessSecond = "
        "0x023BD488 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscard = "
        "0x023BD490 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_PokewalkerDiagnosticReturn = "
        "0x023BD498 | 1;" in rom_ld
        and "PokemonMoveHistoryTask6_FieldReadyDiagnosticPoll = "
        "0x023BD4A0 | 1;" in rom_ld
        and "gPokemonMoveHistoryTask6DiagnosticMailbox = 0x023BD4A8;"
        in rom_ld
        and ".org 0x023D9ABC" not in patches,
        "task-6 resident stub ABI differs",
    )
    for entry_name, implementation in (
        (
            "MoveHistoryTask6Entry_DaycareDepositCommit",
            "PokemonMoveHistoryTask6_DaycareDepositCommitImpl",
        ),
        (
            "MoveHistoryTask6Entry_PCStoragePlaceAndSeed",
            "PokemonMoveHistoryTask6_PCStoragePlaceAndSeedImpl",
        ),
        (
            "MoveHistoryTask6Entry_ReplacePartyMove",
            "PokemonMoveHistoryTask6_SwapPartyPokemonMoveImpl",
        ),
        (
            "MoveHistoryTask6Entry_MarkHistoryMove",
            "PokemonMoveHistoryTask6_MarkHistoryMoveImpl",
        ),
        (
            "MoveHistoryTask6Entry_AppendCandidate",
            "PokemonMoveHistoryTask6_AppendCandidateImpl",
        ),
        (
            "MoveHistoryTask6Entry_ScriptTeachMove",
            "PokemonMoveHistoryTask6_ScriptTeachMoveImpl",
        ),
    ):
        entry_start = task6_entry.index(f"{entry_name}:")
        entry_end = task6_entry.find("\n.global ", entry_start)
        if entry_end < 0:
            entry_end = len(task6_entry)
        entry_body = task6_entry[entry_start:entry_end]
        require(
            f"b {implementation}" in entry_body
            and "ldr r3" not in entry_body,
            f"{entry_name} clobbers its fourth ARM EABI argument",
        )
    for entry_name, implementation in (
        (
            "MoveHistoryTask6Entry_PCStorageGetAndSeed",
            "PokemonMoveHistoryTask6_PCStorageGetAndStageImpl",
        ),
        (
            "MoveHistoryTask6Entry_PokewalkerRadioSuccess",
            "PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl",
        ),
        (
            "MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond",
            "PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl",
        ),
        (
            "MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard",
            "PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscardImpl",
        ),
        (
            "MoveHistoryTask6Entry_FieldReadyDiagnosticPoll",
            "PokemonMoveHistoryTask6_FieldReadyDiagnosticPollImpl",
        ),
    ):
        entry_start = task6_entry.index(f"{entry_name}:")
        entry_end = task6_entry.find("\n.global ", entry_start)
        if entry_end < 0:
            entry_end = len(task6_entry)
        entry_body = task6_entry[entry_start:entry_end]
        require(
            "ldr r3" in entry_body
            and "bx r3" in entry_body
            and f".word {implementation} + 1" in entry_body,
            f"{entry_name} long entry target differs",
        )
    diagnostic_return = task6_entry[
        task6_entry.index("MoveHistoryTask6Entry_PokewalkerDiagnosticReturn:"):
    ]
    require(
        "24: b 24b" in diagnostic_return
        and "host PC injection is forbidden" in diagnostic_return
        and patches.count(
            "PokemonMoveHistoryTask6_PokewalkerDiagnosticReturn"
        ) == 1,
        "Pokewalker diagnostic return trap is callable from retail",
    )
    for wrapper_name in (
        "PokemonMoveRelearn_MarkHistoryMove",
        "PokemonMoveRelearn_Append",
    ):
        wrapper = function_body(without_comments(relearn), wrapper_name)
        require(
            all(
                fragment in wrapper
                for fragment in (
                    '"push {r3}\\n"',
                    '"mov r12, r3\\n"',
                    '"pop {r3}\\n"',
                    '"bx r12\\n"',
                )
            )
            and '"bx r3\\n"' not in wrapper,
            f"{wrapper_name} clobbers its fourth ARM EABI argument",
        )
    for helper_name, literal_targets, blx_r3_count in (
        (
            "PokemonMoveHistoryTask6_PlayerPartyAddCommitImpl",
            ("PokemonMoveHistory_Seed",),
            3,
        ),
        (
            "PokemonMoveHistoryTask6_DaycareShiftAndAppendImpl",
            (
                "PokemonMoveHistory_Seed",
                "PokemonMoveHistory_RecordMove",
            ),
            3,
        ),
    ):
        helper_start = task6_entry.index(f"{helper_name}:")
        helper_end = task6_entry.find("\n.global ", helper_start)
        if helper_end < 0:
            helper_end = len(task6_entry)
        helper_body = task6_entry[helper_start:helper_end]
        require(
            all(f".word {target}" in helper_body for target in literal_targets)
            and helper_body.count("blx r3") == blx_r3_count
            and "bl PokemonMoveHistory_Seed" not in helper_body
            and "bl PokemonMoveHistory_RecordMove" not in helper_body,
            f"{helper_name} does not use explicit Thumb interworking",
        )
    require(
        "form << 11 | 0x8000" in evolution_macros
        and "form >= 16" in evolution_macros
        and "(evoTable[i].target & 0x7800) >> 11" in evolution
        and "(evoTable[i].target & 0x8000) != 0" in evolution
        and "if (hasExplicitForm)" in evolution
        and "u32 form = 32;" in pokemon
        and "if (form != 32)" in pokemon,
        "explicit evolution form-zero encoding differs",
    )
    require(
        '"SPECIES_WORMADAM_SANDY": "SPECIES_BURMY"' in parent_builder
        and '"SPECIES_WORMADAM_TRASHY": "SPECIES_BURMY"'
        in parent_builder,
        "Wormadam cloak parent reconciliation differs",
    )
    for helper, source in (
        ("PokemonMoveHistory_OverlayMemcpy", history),
        ("PokemonMoveHistory_OverlayMemcpy", (
            REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
        ).read_text()),
        ("PokemonMoveHistory_OverlayMemset", (
            REPO / "src/pokemon_move_history_overlay/pokemon_move_relearn.c"
        ).read_text()),
    ):
        require(helper in source, f"overlay source does not call local {helper}")
    thumb_help = (
        REPO / "asm/pokemon_move_history_overlay/thumb_help.s"
    ).read_text()
    for helper in (
        "PokemonMoveHistory_OverlayMemcpy",
        "PokemonMoveHistory_OverlayMemset",
    ):
        require(
            f".global {helper}" in thumb_help,
            f"unique local bridge {helper} is missing",
        )
    require(
        re.search(r"(?m)^\.global\s+(?:memcpy|memset)\s*$", thumb_help)
        is None,
        "overlay bridge still collides with global memcpy/memset symbols",
    )
    package_command = "$(NDSTOOL) -c $(BUILDROM).tmp"
    seal_command = "scripts/pokemon_move_history_build_manifest.py"
    verifier_command = (
        "scripts/verify_pokemon_move_history_capture.py \\\n"
        "\t\t--manifest $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--rom $(BUILDROM).tmp"
    )
    summary_verifier_command = (
        "scripts/verify_summary_move_relearn.py \\\n"
        "\t\t--arm9 $(BASE)/arm9.bin \\\n"
        "\t\t--y9 $(BASE)/overarm9.bin \\\n"
        "\t\t--overlay129 $(BASE)/overlay/overlay_0129.bin \\\n"
        "\t\t--overlay154 $(BASE)/overlay/overlay_0154.bin \\\n"
        "\t\t--linked-overlay154 "
        "$(BUILD)/output_summary_move_relearn_overlay.bin \\\n"
        "\t\t--summary-linked "
        "$(BUILD)/summary_move_relearn_overlay_linked.o \\\n"
        "\t\t--summary-object "
        "$(BUILD)/summary_move_relearn_overlay/summary_move_relearn.o \\\n"
        "\t\t--core-linked $(LINK)"
    )
    final_verifier_command = (
        "scripts/verify_pokemon_move_history.py --rom $(BUILDROM).tmp"
    )
    publish_command = (
        "scripts/pokemon_move_history_build_manifest.py \\\n"
        "\t\t--publish-pair"
    )
    recipe_commands = make_target_recipe_commands(makefile, "all")
    require(
        re.search(
            r"(?m)^\s*\.(?:ONESHELL|IGNORE|SILENT)\s*:",
            makefile,
        )
        is None
        and re.search(
            r"(?m)^\s*\.SHELLFLAGS\s*(?::|\+|\?|!)?=",
            makefile,
        )
        is None
        and not makeflags_suppress_failures_or_output(makefile),
        "Makefile global shell/error semantics can suppress all failures",
    )
    exact_package_commands = [
        "$(NDSTOOL) -c $(BUILDROM).tmp -9 $(BASE)/arm9.bin "
        "-7 $(BASE)/arm7.bin -y9 $(BASE)/overarm9.bin "
        "-y7 $(BASE)/overarm7.bin -d $(FILESYS) -y $(BASE)/overlay "
        "-t $(BASE)/banner.bin -h $(BASE)/header.bin",
        "$(VENV)/bin/python3 -I -S -B -X pycache_prefix=/dev/null "
        "scripts/pokemon_move_history_build_manifest.py "
        "--seal $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--rom $(BUILDROM).tmp "
        '--context "CC=$(CC)" --context "CFLAGS=$(CFLAGS)" '
        '--context "AS=$(AS)" --context "ASFLAGS=$(ASFLAGS)" '
        '--context "LD=$(LD)" --context "LDFLAGS=$(LDFLAGS)" '
        '--context "OBJCOPY=$(OBJCOPY)" --context "ARMIPS=$(ARMIPS)" '
        '--context "ARMIPS_FLAGS=$(ARMIPS_FLAGS)" '
        '--context "NDSTOOL=$(NDSTOOL)"',
        "$(PYTHON_NO_VENV) scripts/verify_summary_move_relearn.py "
        "--arm9 $(BASE)/arm9.bin --y9 $(BASE)/overarm9.bin "
        "--overlay129 $(BASE)/overlay/overlay_0129.bin "
        "--overlay154 $(BASE)/overlay/overlay_0154.bin "
        "--linked-overlay154 "
        "$(BUILD)/output_summary_move_relearn_overlay.bin "
        "--summary-linked "
        "$(BUILD)/summary_move_relearn_overlay_linked.o "
        "--summary-object "
        "$(BUILD)/summary_move_relearn_overlay/summary_move_relearn.o "
        "--core-linked $(LINK)",
        "$(PYTHON_NO_VENV) "
        "scripts/verify_pokemon_move_history_capture.py "
        "--manifest $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--rom $(BUILDROM).tmp",
        "$(PYTHON_NO_VENV) scripts/verify_pokemon_move_history.py "
        "--rom $(BUILDROM).tmp",
        "$(VENV)/bin/python3 -I -S -B -X pycache_prefix=/dev/null "
        "scripts/pokemon_move_history_build_manifest.py --publish-pair "
        "--candidate-manifest $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--candidate-rom $(BUILDROM).tmp "
        "--final-manifest $(MOVE_HISTORY_CAPTURE_MANIFEST) "
        "--final-rom $(BUILDROM)",
    ]
    expected_publication_tail = [
        "rm -f $(BUILDROM).tmp $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP)",
        *exact_package_commands,
        '@echo "Done. See output $(BUILDROM)."',
    ]
    expected_all_recipe = [
        "rm -rf $(BASE)",
        "@mkdir -p $(REQUIRED_DIRECTORIES)",
        "@# find and delete macOS and windows files",
        'find . \\( -name "*.DS_Store" -o '
        '-name "*:Zone.Identifier" \\) -delete',
        "$(NDSTOOL) -x $(ROMNAME) -9 $(BASE)/arm9.bin "
        "-7 $(BASE)/arm7.bin -y9 $(BASE)/overarm9.bin "
        "-y7 $(BASE)/overarm7.bin -d $(FILESYS) "
        "-y $(BASE)/overlay -t $(BASE)/banner.bin "
        "-h $(BASE)/header.bin",
        '@echo "$(ROMNAME) Decompression successful!!"',
        "$(NARCHIVE) extract $(FILESYS)/a/0/2/8 "
        "-o $(BUILD)/a028/ -nf",
        "$(PYTHON) scripts/make.py $(CFLAGS)",
        "$(MAKE) move_narc",
        "$(ARMIPS) armips/global.s $(ARMIPS_FLAGS)",
        "$(NARCHIVE) create $(FILESYS)/a/0/2/8 "
        "$(BUILD)/a028/ -nf",
        "$(PYTHON_NO_VENV) scripts/verify_pc_storage_any_box.py "
        "--source src/pokemon_storage_system.c "
        "--config include/config.h "
        "--save-constants include/constants/save.h "
        "--party-header include/party_menu.h "
        "--arm9 $(BASE)/arm9.bin "
        "--linker-script rom.ld --hooks hooks "
        "--linked-object $(LINK) --core-binary $(OUTPUT) "
        "--packaged-overlay129 $(BASE)/overlay/overlay_0129.bin "
        "--overlay-table $(BASE)/overarm9.bin",
        "$(PYTHON_NO_VENV) scripts/verify_overworld_learnset_cache.py "
        "--patched-arm9 $(BASE)/arm9.bin --require-patched-arm9",
        "$(PYTHON_NO_VENV) scripts/verify_move_relearn_candidates.py",
        '@echo "Making ROM..."',
        *expected_publication_tail,
    ]
    expected_recipe_variables_sha256 = (
        "255760941a1718662c7adb55c05cbb480b4cb4a62e04f02d55975b4730e755fc"
    )
    expected_makefile_sha256 = EXPECTED_MAKEFILE_SHA256
    expected_included_make_sources = EXPECTED_INCLUDED_MAKE_SOURCES
    expected_prerequisites_sha256 = (
        "e8ac941be193804f733059805bc2acfe28dae0c2a0612102339e0d0fc9861628"
    )
    require(
        make_publication_contract_matches(
            makefile,
            "all: $(TOOLS) $(OUTPUT) $(OVERLAY_OUTPUTS)",
            expected_all_recipe,
            expected_publication_tail,
        ),
        "complete all target declaration/recipe or exact publication tail "
        "differs",
    )
    require(
        effective_make_all_contract_matches(
            makefile,
            expected_makefile_sha256,
            expected_included_make_sources,
            expected_prerequisites_sha256,
            expected_all_recipe,
            expected_recipe_variables_sha256,
        ),
        "effective GNU Make all rule, prerequisites, recipe, or critical "
        "variables differ",
    )
    exact_command_positions = [
        recipe_commands.index(command)
        if recipe_commands.count(command) == 1
        else -1
        for command in exact_package_commands
    ]
    require(
        -1 not in exact_command_positions
        and exact_command_positions == sorted(exact_command_positions),
        "complete package/seal/verify/publish recipes differ or can ignore "
        "command failures",
    )
    ignored_prefix_makefile = makefile.replace(
        "\t$(PYTHON_NO_VENV) "
        "scripts/verify_pokemon_move_history_capture.py",
        "\t-$(PYTHON_NO_VENV) "
        "scripts/verify_pokemon_move_history_capture.py",
        1,
    )
    ignored_suffix_makefile = makefile.replace(
        "\t\t--manifest $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--rom $(BUILDROM).tmp",
        "\t\t--manifest $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--rom $(BUILDROM).tmp || true",
        1,
    )
    require(
        exact_package_commands[3]
        not in make_recipe_commands(ignored_prefix_makefile)
        and exact_package_commands[3]
        not in make_recipe_commands(ignored_suffix_makefile),
        "Make error-ignoring mutation fixture does not fail closed",
    )
    detached_target_makefile = makefile.replace(
        "\t$(PYTHON_NO_VENV) "
        "scripts/verify_pokemon_move_history_capture.py",
        "detached_capture_gate:\n"
        "\t$(PYTHON_NO_VENV) "
        "scripts/verify_pokemon_move_history_capture.py",
        1,
    )
    require(
        exact_package_commands[3]
        not in make_target_recipe_commands(
            detached_target_makefile,
            "all",
        )
        and re.search(
            r"(?m)^\s*\.(?:ONESHELL|IGNORE|SILENT)\s*:",
            ".ONESHELL:\n" + makefile,
        )
        is not None,
        "Make target/global-context mutation fixtures do not fail closed",
    )
    for makeflags_mutation in (
        "MAKEFLAGS=-i\n",
        "override MAKEFLAGS=-s\n",
        "MAKEFLAGS += --ignore-errors\n",
        "MAKEFLAGS+=--silent\n",
        "MAKEFLAGS=i\n",
        "FAIL_FLAGS=-i\nMAKEFLAGS=$(FAIL_FLAGS)\n",
    ):
        require(
            makeflags_suppress_failures_or_output(
                makeflags_mutation + makefile
            ),
            f"Make global flag mutation passes: {makeflags_mutation.strip()}",
        )
    exact_target = "all: $(TOOLS) $(OUTPUT) $(OVERLAY_OUTPUTS)"
    prerequisite_mutation = makefile.replace(
        exact_target,
        exact_target + " clobber-accepted-rom",
        1,
    )
    require(
        prerequisite_mutation != makefile
        and not make_publication_contract_matches(
            prerequisite_mutation,
            exact_target,
            expected_all_recipe,
            expected_publication_tail,
        ),
        "extra all-target prerequisite passes publication authentication",
    )
    effective_make_mutations = (
        (
            "expanded target recipe override",
            "\nALL_TARGET = all\n"
            "$(ALL_TARGET):\n"
            "\tcp test.nds.tmp test.nds\n",
        ),
        (
            "expanded target prerequisite",
            "\nALL_TARGET = all\n"
            "$(ALL_TARGET): clobber-accepted-rom\n",
        ),
        (
            "multi-target prerequisite",
            "\nall shadow-target: clobber-accepted-rom\n",
        ),
        (
            "late ROM override",
            "\noverride BUILDROM = attacker.nds\n",
        ),
        (
            "late manifest override",
            "\noverride MOVE_HISTORY_CAPTURE_MANIFEST = attacker.json\n",
        ),
        (
            "expanded target-specific ROM override",
            "\nALL_TARGET = all\n"
            "$(ALL_TARGET): BUILDROM = attacker.nds\n",
        ),
        (
            "expanded target-specific manifest override",
            "\nALL_TARGET = all\n"
            "$(ALL_TARGET): MOVE_HISTORY_CAPTURE_MANIFEST = attacker.json\n",
        ),
        (
            "expanded target-specific temporary manifest override",
            "\nALL_TARGET = all\n"
            "$(ALL_TARGET): MOVE_HISTORY_CAPTURE_MANIFEST_TMP = "
            "attacker.tmp\n",
        ),
        (
            "delayed ARMIPS flags write",
            "\noverride ARMIPS_FLAGS = -equ DEBUG_BATTLE_SCENARIOS 0 ; "
            "(sleep 1; cp rom.nds test.nds) & #\n",
        ),
        (
            "delayed VENV activation write",
            "\noverride VENV_ACTIVATE = /dev/null ; "
            "(sleep 1; cp rom.nds test.nds) & #\n",
        ),
        (
            "nested delayed VENV activation write",
            "\noverride VENV_ACTIVATE = $(MOVE_HISTORY_NESTED)\n"
            "MOVE_HISTORY_NESTED = /dev/null ; "
            "(sleep 1; cp rom.nds test.nds) & #\n",
        ),
        (
            "cyclic VENV activation reference",
            "\noverride VENV_ACTIVATE = $(MOVE_HISTORY_CYCLE)\n"
            "MOVE_HISTORY_CYCLE = $(VENV_ACTIVATE)\n",
        ),
        (
            "unknown VENV activation reference",
            "\noverride VENV_ACTIVATE = $(MOVE_HISTORY_UNKNOWN)\n",
        ),
        (
            "dynamic VENV activation reference",
            "\noverride VENV_ACTIVATE = $@\n",
        ),
    )
    for label, suffix in effective_make_mutations:
        mutated_makefile = makefile + suffix
        require(
            not effective_make_all_contract_matches(
                mutated_makefile,
                hashlib.sha256(mutated_makefile.encode()).hexdigest(),
                expected_included_make_sources,
                expected_prerequisites_sha256,
                expected_all_recipe,
                expected_recipe_variables_sha256,
            ),
            f"{label} passes effective Make authentication",
        )
    mismatched_included_sources = dict(expected_included_make_sources)
    mismatched_included_sources["overlays.mk"] = "0" * 64
    require(
        not effective_make_all_contract_matches(
            makefile,
            expected_makefile_sha256,
            mismatched_included_sources,
            expected_prerequisites_sha256,
            expected_all_recipe,
            expected_recipe_variables_sha256,
        ),
        "changed included Make source passes pre-evaluation authentication",
    )

    def source_path_snapshot(path: Path) -> tuple[object, ...]:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return ("missing",)
        if path.is_symlink():
            return ("symlink", metadata.st_ino, os.readlink(path))
        if path.is_file():
            return (
                "file",
                metadata.st_ino,
                metadata.st_mode,
                file_record(path),
            )
        return ("other", metadata.st_ino, metadata.st_mode)

    accepted_publication_paths = (
        REPO / "test.nds",
        REPO / "build/pokemon_move_history_capture_build.json",
    )
    with tempfile.TemporaryDirectory(
        prefix="move-history-make-side-effects-"
    ) as side_effect_directory:
        side_effect_root = Path(side_effect_directory)
        topology_root = side_effect_root / "source-topology"
        topology_source = topology_root / "src"
        topology_assembly = topology_root / "asm"
        topology_source.mkdir(parents=True)
        topology_assembly.mkdir()
        (topology_source / "probe.c").write_text("int probe;\n")
        (topology_assembly / "probe.s").write_text(".thumb\n")
        require(
            make_compilation_source_topology_is_safe(topology_root),
            "valid compilation-source topology fixture is rejected",
        )
        accepted_before = {
            path: source_path_snapshot(path)
            for path in accepted_publication_paths
        }
        malicious_source = topology_source / "bad$(file poison).c"
        malicious_source.write_text("int bad;\n")
        require(
            not make_compilation_source_topology_is_safe(topology_root),
            "Make-syntax C filename passes source-topology validation",
        )
        malicious_source.unlink()
        malicious_dotless_source = topology_source / "$(file poison)"
        malicious_dotless_source.write_text("not an overlay\n")
        require(
            not make_compilation_source_topology_is_safe(topology_root),
            "dotless Make-syntax source entry passes topology validation",
        )
        malicious_dotless_source.unlink()
        malicious_overlay = topology_source / "bad,$(shell poison)"
        malicious_overlay.mkdir()
        (malicious_overlay / "probe.c").write_text("int bad;\n")
        require(
            not make_compilation_source_topology_is_safe(topology_root),
            "Make-syntax overlay directory passes source-topology validation",
        )
        shutil.rmtree(malicious_overlay)
        malicious_assembly = topology_assembly / "bad$(eval poison).s"
        malicious_assembly.write_text(".thumb\n")
        require(
            not make_compilation_source_topology_is_safe(topology_root),
            "Make-syntax assembly filename passes source-topology validation",
        )
        malicious_assembly.unlink()
        symlink_source = topology_source / "linked.c"
        symlink_source.symlink_to(topology_source / "missing.c")
        require(
            not make_compilation_source_topology_is_safe(topology_root)
            and {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            == accepted_before,
            "symlink compilation source passes or changes accepted artifacts",
        )

        dependency_root = side_effect_root / "dependency-tree"
        dependency_build = dependency_root / "build"
        dependency_source = dependency_root / "src"
        dependency_assembly = dependency_root / "asm"
        dependency_build.mkdir(parents=True)
        dependency_source.mkdir()
        dependency_assembly.mkdir()
        (dependency_source / "probe.c").write_text("int probe;\n")
        dependency = dependency_build / "probe.d"
        dependency.write_text("build/probe.o: src/probe.c include/types.h\n")
        require(
            generated_dependency_inputs_are_safe(dependency_root),
            "valid generated dependency fixture is rejected",
        )
        accepted_before = {
            path: source_path_snapshot(path)
            for path in accepted_publication_paths
        }
        for label, malicious_dependency in (
            (
                "file function",
                "SIDE := $(file >accepted.nds,corrupted)\n",
            ),
            (
                "shell assignment",
                "SIDE != cp rom.nds accepted.nds\n",
            ),
            (
                "all-rule alteration",
                "all: clobber-accepted-rom\n",
            ),
            (
                "wrong object target",
                "build/probe.o: clean\n",
            ),
        ):
            dependency.write_text(malicious_dependency)
            require(
                not generated_dependency_inputs_are_safe(dependency_root)
                and {
                    path: source_path_snapshot(path)
                    for path in accepted_publication_paths
                }
                == accepted_before,
                f"malicious generated dependency {label} passes or "
                "changes accepted artifacts",
            )
        dependency.unlink()
        dependency.symlink_to(dependency_root / "missing.d")
        require(
            not generated_dependency_inputs_are_safe(dependency_root)
            and {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            == accepted_before,
            "generated dependency symlink passes or changes accepted "
            "artifacts",
        )
        dependency.unlink()
        nested_source = dependency_source / "nested"
        nested_source.mkdir()
        (nested_source / "probe.c").write_text("int nested_probe;\n")
        attacker_directory = side_effect_root / "dependency-attacker"
        attacker_directory.mkdir()
        (attacker_directory / "probe.d").write_text(
            "SIDE := $(file >accepted.nds,corrupted)\n"
        )
        (dependency_build / "nested").symlink_to(
            attacker_directory,
            target_is_directory=True,
        )
        require(
            not generated_dependency_inputs_are_safe(dependency_root)
            and {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            == accepted_before,
            "generated dependency parent-directory symlink passes or "
            "changes accepted artifacts",
        )
        dangling_root = side_effect_root / "dangling-dependency-tree"
        (dangling_root / "src").mkdir(parents=True)
        (dangling_root / "asm").mkdir()
        (dangling_root / "src/probe.c").write_text("int probe;\n")
        (dangling_root / "build").symlink_to(
            dangling_root / "missing-build",
            target_is_directory=True,
        )
        require(
            not generated_dependency_inputs_are_safe(dangling_root)
            and {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            == accepted_before,
            "dangling generated dependency root passes or changes "
            "accepted artifacts",
        )

        parse_time_mutations = (
            (
                "file function",
                "SIDE_EFFECT := $(file >{path},corrupted)\n",
            ),
            (
                "shell function",
                "SIDE_EFFECT := $(shell printf corrupted > {path})\n",
            ),
            (
                "shell assignment",
                "SIDE_EFFECT != cp rom.nds {path}\n",
            ),
        )
        for index, (label, mutation) in enumerate(
            parse_time_mutations
        ):
            sentinel = side_effect_root / f"sentinel-{index}"
            accepted_before = {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            mutated_makefile = (
                makefile + "\n" + mutation.format(path=sentinel)
            )
            require(
                not effective_make_all_contract_matches(
                    mutated_makefile,
                    expected_makefile_sha256,
                    expected_included_make_sources,
                    expected_prerequisites_sha256,
                    expected_all_recipe,
                    expected_recipe_variables_sha256,
                )
                and not sentinel.exists()
                and {
                    path: source_path_snapshot(path)
                    for path in accepted_publication_paths
                }
                == accepted_before,
                f"parse-time Make {label} executed before authentication",
            )

        environment_sentinel = side_effect_root / "environment-sentinel"
        accepted_before = {
            path: source_path_snapshot(path)
            for path in accepted_publication_paths
        }
        prior_armips_flags = os.environ.get("ARMIPS_FLAGS")
        prior_makeflags = os.environ.get("MAKEFLAGS")
        try:
            os.environ["ARMIPS_FLAGS"] = (
                "-equ DEBUG_BATTLE_SCENARIOS 0 ; "
                f"cp rom.nds {environment_sentinel}"
            )
            os.environ["MAKEFLAGS"] = "-e"
            environment_scrubbed = effective_make_all_contract_matches(
                makefile,
                expected_makefile_sha256,
                expected_included_make_sources,
                expected_prerequisites_sha256,
                expected_all_recipe,
                expected_recipe_variables_sha256,
            )
        finally:
            if prior_armips_flags is None:
                os.environ.pop("ARMIPS_FLAGS", None)
            else:
                os.environ["ARMIPS_FLAGS"] = prior_armips_flags
            if prior_makeflags is None:
                os.environ.pop("MAKEFLAGS", None)
            else:
                os.environ["MAKEFLAGS"] = prior_makeflags
        require(
            environment_scrubbed
            and not environment_sentinel.exists()
            and {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            == accepted_before,
            "host environment overrides reached effective Make evaluation",
        )

        command_line_sentinel = (
            side_effect_root / "command-line-sentinel"
        )
        command_line_value = (
            "ARMIPS_FLAGS=-equ DEBUG_BATTLE_SCENARIOS 0 ; "
            f"cp rom.nds {command_line_sentinel}"
        )
        require(
            not effective_make_all_contract_matches(
                makefile,
                expected_makefile_sha256,
                expected_included_make_sources,
                expected_prerequisites_sha256,
                expected_all_recipe,
                expected_recipe_variables_sha256,
                make_arguments=(command_line_value,),
            )
            and not command_line_sentinel.exists()
            and {
                path: source_path_snapshot(path)
                for path in accepted_publication_paths
            }
            == accepted_before,
            "command-line Make override passed or executed",
        )
    publisher_end = "\t\t--final-rom $(BUILDROM)\n"
    done_line = '\t@echo "Done.  See output $(BUILDROM)."\n'
    require(
        publisher_end in makefile and done_line in makefile,
        "publication mutation fixture anchors are absent",
    )
    publication_write_commands = (
        "cp $(BUILDROM).tmp $(BUILDROM)",
        "install $(BUILDROM).tmp $(BUILDROM)",
        "printf bad > $(BUILDROM)",
        "printf bad >> $(BUILDROM)",
        "cat $(BUILDROM).tmp | tee $(BUILDROM)",
        "dd if=$(BUILDROM).tmp of=$(BUILDROM)",
        "cp test.nds.tmp test.nds",
        "cp $(BUILDROM).tmp $(FINAL_ROM_ALIAS)",
        "cp stale.json $(MOVE_HISTORY_CAPTURE_MANIFEST)",
    )
    for command in publication_write_commands:
        for placement, mutated_makefile in (
            (
                "before publish",
                makefile.replace(
                    "\t$(VENV)/bin/python3 -I -S -B -X "
                    "pycache_prefix=/dev/null \\\n"
                    "\t\tscripts/pokemon_move_history_build_manifest.py \\\n"
                    "\t\t--publish-pair",
                    f"\t{command}\n"
                    "\t$(VENV)/bin/python3 -I -S -B -X "
                    "pycache_prefix=/dev/null \\\n"
                    "\t\tscripts/pokemon_move_history_build_manifest.py \\\n"
                    "\t\t--publish-pair",
                    1,
                ),
            ),
            (
                "after publish",
                makefile.replace(
                    publisher_end,
                    publisher_end + f"\t{command}\n",
                    1,
                ),
            ),
        ):
            if "FINAL_ROM_ALIAS" in command:
                mutated_makefile = (
                    "FINAL_ROM_ALIAS = $(BUILDROM)\n" + mutated_makefile
                )
            require(
                mutated_makefile != makefile
                and not make_publication_contract_matches(
                    mutated_makefile,
                    exact_target,
                    expected_all_recipe,
                    expected_publication_tail,
                ),
                f"{placement} command passes publication authentication: "
                f"{command}",
            )
    post_done_mutation = makefile.replace(
        done_line,
        done_line + "\tcp test.nds.tmp test.nds\n",
        1,
    )
    require(
        post_done_mutation != makefile
        and not make_publication_contract_matches(
            post_done_mutation,
            exact_target,
            expected_all_recipe,
            expected_publication_tail,
        ),
        "post-publication target mutation passes authentication",
    )
    seal_start = makefile.find(seal_command)
    summary_verifier_start = makefile.find(summary_verifier_command)
    verifier_start = makefile.find(verifier_command)
    seal_block = (
        makefile[seal_start:verifier_start]
        if seal_start >= 0 and verifier_start > seal_start
        else ""
    )
    require(
        makefile.count("scripts/verify_pokemon_move_history_capture.py") == 1
        and makefile.count("scripts/verify_summary_move_relearn.py") == 1
        and makefile.count(
            "scripts/pokemon_move_history_build_manifest.py"
        ) == 2
        and makefile.count(final_verifier_command) == 1
        and package_command in makefile
        and seal_command in makefile
        and summary_verifier_command in makefile
        and "--seal $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP) "
        "--rom $(BUILDROM).tmp" in seal_block
        and verifier_command in makefile
        and final_verifier_command in makefile
        and publish_command in makefile
        and "--candidate-manifest $(MOVE_HISTORY_CAPTURE_MANIFEST_TMP)"
        in makefile
        and "--candidate-rom $(BUILDROM).tmp" in makefile
        and "--final-manifest $(MOVE_HISTORY_CAPTURE_MANIFEST)" in makefile
        and "--final-rom $(BUILDROM)" in makefile
        and "mv $(BUILDROM).tmp $(BUILDROM)" not in makefile
        and makefile.index(package_command) < makefile.index(seal_command)
        < summary_verifier_start
        < makefile.index(verifier_command)
        < makefile.index(final_verifier_command)
        < makefile.index(publish_command),
        "capture manifest/verifiers are not wired once in fail-closed "
        "post-package/publish order",
    )
    require(
        set(re.findall(r'--context\s+"([A-Z_]+)=', seal_block))
        == {
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
        },
        "manifest seal does not record the exact effective build context",
    )
    forced_objects_match = re.search(
        r"MOVE_HISTORY_CAPTURE_OBJECTS\s*=\s*\\\n"
        r"(.*?)"
        r"\n\.PHONY:\s*FORCE_MOVE_HISTORY_CAPTURE_OBJECTS",
        makefile,
        re.S,
    )
    require(
        forced_objects_match is not None
        and {
            "$(BUILD)/pokemon.o",
            "$(BUILD)/pokemon_storage_system.o",
            "$(BUILD)/individual/GetMonEvolutionInternal.o",
            "$(BUILD)/field/script_commands.o",
            "$(BUILD)/party_menu.o",
            "$(BUILD)/save.o",
            "$(BUILD)/pokemon_move_history_overlay/pokemon_move_history.o",
            "$(BUILD)/pokemon_move_history_overlay/pokemon_move_relearn.o",
            "$(BUILD)/pokemon_move_history_overlay/entry.o",
            "$(BUILD)/pokemon_move_history_overlay/thumb_help.o",
            "$(BUILD)/pokemon_move_history_task6_overlay/pokemon_move_history_task6.o",
            "$(BUILD)/pokemon_move_history_task6_overlay/entry.o",
            "$(BUILD)/overlay.o",
            "$(BUILD)/other_hook.o",
            "$(BUILD)/summary_move_relearn_overlay/summary_move_relearn.o",
            "$(BUILD)/summary_move_relearn_overlay/entry.o",
        }
        == set(re.findall(r"\$\(BUILD\)/[^\s\\]+", forced_objects_match.group(1)))
        and "$(MOVE_HISTORY_CAPTURE_OBJECTS): "
        "FORCE_MOVE_HISTORY_CAPTURE_OBJECTS" in makefile,
        "move-history provenance does not force exactly the sixteen capture objects",
    )


def move_limits() -> tuple[int, int, int]:
    moves_header = (REPO / "include/constants/moves.h").read_text()
    executable = without_comments(moves_header)
    none_match = re.search(
        r"^#define\s+MOVE_NONE\s+(\d+)$",
        executable,
        re.MULTILINE,
    )
    canonical_match = re.search(
        r"^#define\s+NUM_OF_CANONICAL_MOVES\s+(\d+)$",
        executable,
        re.MULTILINE,
    )
    custom_match = re.search(
        r"^#define\s+NUM_OF_CUSTOM_MOVES\s+(\d+)$",
        executable,
        re.MULTILINE,
    )
    require(
        none_match is not None
        and canonical_match is not None
        and custom_match is not None,
        "move-count constants are not simple deterministic integers",
    )
    move_none = int(none_match.group(1))
    canonical = int(canonical_match.group(1))
    custom = int(custom_match.group(1))
    require(move_none == 0, "MOVE_NONE is no longer zero")
    require(canonical >= 2 and custom >= 0, "move-count constants are invalid")
    return canonical, custom, canonical + custom


def manifest_mutation_fixtures(
    packaged_manifest: Path | None,
    packaged_rom: Path | None,
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        input_path = root / "input.c"
        output_path = root / "linked.o"
        temporary_rom = root / "test.nds.tmp"
        final_rom = root / "test.nds"
        (root / "armips").mkdir()
        (root / "build").mkdir()
        armips_entry = root / "armips/global.s"
        armips_nested = root / "armips/nested.s"
        incbin_path = root / "build/payload.bin"
        importobj_path = root / "build/imported.o"
        armips_entry.write_text('.include "armips/nested.s"\n')
        armips_nested.write_text(
            '.incbin "build/payload.bin"\n'
            '.importobj "build/imported.o"\n'
        )
        incbin_path.write_bytes(b"generation-a incbin")
        importobj_path.write_bytes(b"generation-a imported object")
        fixture_input_paths = {
            "input.c",
            "armips/global.s",
            "armips/nested.s",
            "build/payload.bin",
            "build/imported.o",
        }
        require(
            armips_dependency_paths(root, armips_entry)
            == fixture_input_paths - {"input.c"},
            "ARMIPS fixture does not close over nested incbin inputs",
        )
        input_path.write_bytes(b"generation-a source")
        output_path.write_bytes(b"generation-a output")
        temporary_rom.write_bytes(b"generation-a packaged rom")
        document = {
            "schema": BUILD_MANIFEST_SCHEMA,
            "build_context": {"fixture-tool": "fixture-tool"},
            "inputs": {
                path: file_record(root / path)
                for path in sorted(fixture_input_paths)
            },
            "outputs": {
                "linked": {
                    "path": "linked.o",
                    **file_record(output_path),
                },
                "packaged_rom": {
                    "path": PACKAGED_ROM_LOGICAL_PATH,
                    **file_record(temporary_rom),
                },
            },
            "runtime_environment": unbound_runtime_environment(),
            "tools": {
                "fixture-tool": {
                    "command": "fixture-tool",
                    "version": "fixture 1",
                    "binary": {"size": 1, "sha256": "0" * 64},
                },
            },
        }

        def verify_fixture(candidate: dict[str, object], rom: Path) -> None:
            verify_manifest_document(
                candidate,
                root,
                fixture_input_paths,
                {"linked": "linked.o"},
                rom,
                {"fixture-tool"},
                {"fixture-tool"},
            )

        def must_reject(
            label: str,
            candidate: dict[str, object],
            rom: Path = final_rom,
        ) -> None:
            try:
                verify_fixture(candidate, rom)
            except ManifestError:
                return
            require(False, f"{label} passes full manifest schema verification")

        temporary_rom.rename(final_rom)
        verify_fixture(document, final_rom)

        os.utime(input_path, (1, 1))
        input_path.write_bytes(b"generation-b current source")
        os.utime(input_path, (1, 1))
        must_reject("coherent backdated stale generation", document)
        input_path.write_bytes(b"generation-a source")

        output_path.write_bytes(b"mutated output")
        os.utime(output_path, (2_000_000_000, 2_000_000_000))
        must_reject("future-dated changed output", document)
        output_path.write_bytes(b"generation-a output")

        incbin_path.write_bytes(b"mutated incbin")
        must_reject("changed recursively reached incbin", document)
        incbin_path.write_bytes(b"generation-a incbin")

        importobj_path.write_bytes(b"mutated imported object")
        must_reject("changed recursively reached importobj", document)
        importobj_path.write_bytes(b"generation-a imported object")

        missing_role = copy.deepcopy(document)
        del missing_role["outputs"]["linked"]
        must_reject("missing output role", missing_role)
        extra_role = copy.deepcopy(document)
        extra_role["outputs"]["extra"] = copy.deepcopy(
            document["outputs"]["linked"]
        )
        must_reject("unknown output role", extra_role)
        wrong_binding = copy.deepcopy(document)
        wrong_binding["inputs"]["input.c"]["sha256"] = "f" * 64
        must_reject("wrong input hash binding", wrong_binding)
        wrong_rom_path = copy.deepcopy(document)
        wrong_rom_path["outputs"]["packaged_rom"]["path"] = "test.nds.tmp"
        must_reject("temporary packaged-ROM path binding", wrong_rom_path)
        wrong_tool = copy.deepcopy(document)
        wrong_tool["tools"]["unknown"] = wrong_tool["tools"].pop(
            "fixture-tool"
        )
        must_reject("unknown tool role", wrong_tool)
        tampered_tool = copy.deepcopy(document)
        tampered_tool["tools"]["fixture-tool"]["command"] = "other-tool"
        must_reject("tool/build-context binding tamper", tampered_tool)
        malformed_tool_hash = copy.deepcopy(document)
        malformed_tool_hash["tools"]["fixture-tool"]["binary"]["sha256"] = "bad"
        must_reject("malformed tool identity hash", malformed_tool_hash)

        accepted_manifest = root / "accepted.json"
        candidate_manifest = root / "candidate.json"
        candidate_rom = root / "candidate.nds"
        accepted_manifest_bytes = b"previous accepted manifest\n"
        accepted_rom_bytes = b"previous accepted ROM\n"
        candidate_rom_bytes = b"new verified ROM generation\n"

        def write_candidate_pair() -> None:
            candidate_rom.write_bytes(candidate_rom_bytes)
            candidate_document = copy.deepcopy(document)
            candidate_document["outputs"]["packaged_rom"] = {
                "path": PACKAGED_ROM_LOGICAL_PATH,
                **file_record(candidate_rom),
            }
            candidate_manifest.write_text(
                json.dumps(candidate_document, sort_keys=True) + "\n"
            )

        def verify_publish_pair(manifest: Path, rom: Path) -> None:
            verify_fixture(load_manifest(manifest), rom)

        def path_snapshot(path: Path) -> tuple[object, ...]:
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                return ("missing",)
            if path.is_symlink():
                return (
                    "symlink",
                    metadata.st_ino,
                    os.readlink(path),
                )
            if path.is_file():
                return ("file", metadata.st_ino, path.read_bytes())
            return ("other", metadata.st_ino, metadata.st_mode)

        accepted_paths = (accepted_manifest, final_rom)
        candidate_paths = (candidate_manifest, candidate_rom)
        journal_path = accepted_manifest.with_name(
            accepted_manifest.name + ".publish-journal"
        )

        def reset_journal_alias_fixture() -> None:
            for path in (
                accepted_manifest,
                final_rom,
                candidate_manifest,
                candidate_rom,
                journal_path,
            ):
                path.unlink(missing_ok=True)
            for path in root.glob(".*.publish.*"):
                path.unlink(missing_ok=True)
            accepted_manifest.write_bytes(accepted_manifest_bytes)
            final_rom.write_bytes(accepted_rom_bytes)
            write_candidate_pair()

        def require_journal_alias_rejected(
            label: str,
            arguments: tuple[Path, Path, Path, Path],
            watched: tuple[Path, ...],
        ) -> None:
            verify_calls = 0
            replace_calls = 0

            def count_verify(_manifest: Path, _rom: Path) -> None:
                nonlocal verify_calls
                verify_calls += 1

            def count_replace(
                _source: str | Path,
                _destination: str | Path,
            ) -> None:
                nonlocal replace_calls
                replace_calls += 1

            before = {
                path: path_snapshot(path)
                for path in watched
            }
            publish_temporaries_before = {
                path: path_snapshot(path)
                for path in root.glob(".*.publish.*")
            }
            try:
                publish_pair(
                    *arguments,
                    verify=count_verify,
                    replace=count_replace,
                )
            except ManifestError as exc:
                require(
                    str(exc)
                    == "candidate, final, and journal publish paths must "
                    "be distinct",
                    f"{label} failed for the wrong reason: {exc}",
                )
            else:
                require(False, f"{label} journal identity alias passed")
            require(
                verify_calls == 0
                and replace_calls == 0
                and {
                    path: path_snapshot(path)
                    for path in watched
                }
                == before
                and {
                    path: path_snapshot(path)
                    for path in root.glob(".*.publish.*")
                }
                == publish_temporaries_before,
                f"{label} journal identity rejection mutated topology",
            )

        for label, role in (
            ("journal equals candidate manifest", "candidate_manifest"),
            ("journal equals candidate ROM", "candidate_rom"),
            ("journal equals existing final ROM", "final_rom"),
        ):
            reset_journal_alias_fixture()
            if role == "candidate_manifest":
                journal_path.write_bytes(candidate_manifest.read_bytes())
                candidate_manifest.unlink()
                arguments = (
                    journal_path,
                    candidate_rom,
                    accepted_manifest,
                    final_rom,
                )
            elif role == "candidate_rom":
                journal_path.write_bytes(candidate_rom.read_bytes())
                candidate_rom.unlink()
                arguments = (
                    candidate_manifest,
                    journal_path,
                    accepted_manifest,
                    final_rom,
                )
            else:
                journal_path.write_bytes(final_rom.read_bytes())
                arguments = (
                    candidate_manifest,
                    candidate_rom,
                    accepted_manifest,
                    journal_path,
                )
            require_journal_alias_rejected(
                label,
                arguments,
                (
                    *accepted_paths,
                    *candidate_paths,
                    journal_path,
                ),
            )

        reset_journal_alias_fixture()
        journal_path.unlink(missing_ok=True)
        require_journal_alias_rejected(
            "journal equals missing final ROM",
            (
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                journal_path,
            ),
            (*accepted_paths, *candidate_paths, journal_path),
        )

        reset_journal_alias_fixture()
        journal_path.unlink(missing_ok=True)
        casefold_final_rom = journal_path.with_name(
            journal_path.name.upper()
        )
        require_journal_alias_rejected(
            "casefold journal equals missing final ROM",
            (
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                casefold_final_rom,
            ),
            (
                *accepted_paths,
                *candidate_paths,
                journal_path,
                casefold_final_rom,
            ),
        )

        reset_journal_alias_fixture()
        decomposed_manifest = root / "acce\u0301pted.json"
        composed_final_rom = root / "acc\u00e9pted.json.publish-journal"
        decomposed_journal = decomposed_manifest.with_name(
            decomposed_manifest.name + ".publish-journal"
        )
        decomposed_manifest.write_bytes(accepted_manifest_bytes)
        composed_final_rom.unlink(missing_ok=True)
        require_journal_alias_rejected(
            "Unicode-normalized journal equals missing final ROM",
            (
                candidate_manifest,
                candidate_rom,
                decomposed_manifest,
                composed_final_rom,
            ),
            (
                *accepted_paths,
                *candidate_paths,
                decomposed_manifest,
                decomposed_journal,
                composed_final_rom,
            ),
        )
        decomposed_manifest.unlink(missing_ok=True)

        for label, role in (
            ("dot-dot candidate manifest", "candidate_manifest"),
            ("dot-dot candidate ROM", "candidate_rom"),
            ("dot-dot final ROM", "final_rom"),
        ):
            reset_journal_alias_fixture()
            missing_parent = root / f"{role}-missing-parent"
            missing_parent.rmdir() if missing_parent.is_dir() else None
            dotdot_journal = missing_parent / ".." / journal_path.name
            if role == "candidate_manifest":
                journal_path.write_bytes(candidate_manifest.read_bytes())
                candidate_manifest.unlink()
                arguments = (
                    dotdot_journal,
                    candidate_rom,
                    accepted_manifest,
                    final_rom,
                )
            elif role == "candidate_rom":
                journal_path.write_bytes(candidate_rom.read_bytes())
                candidate_rom.unlink()
                arguments = (
                    candidate_manifest,
                    dotdot_journal,
                    accepted_manifest,
                    final_rom,
                )
            else:
                journal_path.write_bytes(final_rom.read_bytes())
                arguments = (
                    candidate_manifest,
                    candidate_rom,
                    accepted_manifest,
                    dotdot_journal,
                )
            require_journal_alias_rejected(
                label,
                arguments,
                (
                    *accepted_paths,
                    *candidate_paths,
                    journal_path,
                    missing_parent,
                ),
            )

        for label, role in (
            ("resolved candidate manifest", "candidate_manifest"),
            ("resolved candidate ROM", "candidate_rom"),
            ("resolved final ROM", "final_rom"),
        ):
            reset_journal_alias_fixture()
            alias_parent = root / f"{role}-resolved-parent"
            alias_parent.unlink(missing_ok=True)
            alias_parent.symlink_to(".", target_is_directory=True)
            resolved_journal_alias = alias_parent / journal_path.name
            if role == "candidate_manifest":
                journal_path.write_bytes(candidate_manifest.read_bytes())
                candidate_manifest.unlink()
                arguments = (
                    resolved_journal_alias,
                    candidate_rom,
                    accepted_manifest,
                    final_rom,
                )
            elif role == "candidate_rom":
                journal_path.write_bytes(candidate_rom.read_bytes())
                candidate_rom.unlink()
                arguments = (
                    candidate_manifest,
                    resolved_journal_alias,
                    accepted_manifest,
                    final_rom,
                )
            else:
                journal_path.write_bytes(final_rom.read_bytes())
                arguments = (
                    candidate_manifest,
                    candidate_rom,
                    accepted_manifest,
                    resolved_journal_alias,
                )
            require_journal_alias_rejected(
                label,
                arguments,
                (
                    *accepted_paths,
                    *candidate_paths,
                    journal_path,
                    alias_parent,
                ),
            )
            alias_parent.unlink()

        for label, target in (
            ("journal symlink to candidate manifest", candidate_manifest),
            ("journal symlink to candidate ROM", candidate_rom),
            ("journal symlink to final manifest", accepted_manifest),
            ("journal symlink to final ROM", final_rom),
        ):
            reset_journal_alias_fixture()
            journal_path.symlink_to(target.name)
            require_journal_alias_rejected(
                label,
                (
                    candidate_manifest,
                    candidate_rom,
                    accepted_manifest,
                    final_rom,
                ),
                (
                    *accepted_paths,
                    *candidate_paths,
                    journal_path,
                ),
            )

        reset_journal_alias_fixture()
        journal_path.unlink(missing_ok=True)
        os.link(candidate_manifest, journal_path)
        require_journal_alias_rejected(
            "journal hardlink to candidate manifest",
            (
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
            ),
            (*accepted_paths, *candidate_paths, journal_path),
        )

        reset_journal_alias_fixture()
        malformed_journal_alias_bytes = b"{malformed journal alias\n"
        journal_path.write_bytes(malformed_journal_alias_bytes)
        require_journal_alias_rejected(
            "malformed journal equals final ROM",
            (
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                journal_path,
            ),
            (*accepted_paths, *candidate_paths, journal_path),
        )

        reset_journal_alias_fixture()
        recovery_backups = {
            path: root / f".{path.name}.publish.alias-backup"
            for path in accepted_paths
        }
        recovery_stages = {
            path: root / f".{path.name}.publish.alias-stage"
            for path in accepted_paths
        }
        for final in accepted_paths:
            recovery_backups[final].write_bytes(final.read_bytes())
            recovery_stages[final].write_bytes(b"alias recovery stage\n")
        valid_recovery_alias = {
            "schema": "pokemon-move-history-pair-publish-v1",
            "entries": [
                {
                    "final": str(final.resolve()),
                    "prior": file_record(final),
                    "backup": str(recovery_backups[final].resolve()),
                    "stage": str(recovery_stages[final].resolve()),
                }
                for final in accepted_paths
            ],
        }
        journal_path.write_text(
            json.dumps(valid_recovery_alias, sort_keys=True) + "\n"
        )
        candidate_manifest.unlink()
        require_journal_alias_rejected(
            "valid recovery journal equals candidate manifest",
            (
                journal_path,
                candidate_rom,
                accepted_manifest,
                final_rom,
            ),
            (
                *accepted_paths,
                *candidate_paths,
                journal_path,
                *recovery_backups.values(),
                *recovery_stages.values(),
            ),
        )
        for temporary in (
            *recovery_backups.values(),
            *recovery_stages.values(),
        ):
            temporary.unlink()
        reset_journal_alias_fixture()

        for label, leaf in (
            ("candidate manifest", candidate_manifest),
            ("candidate ROM", candidate_rom),
            ("final manifest", accepted_manifest),
            ("final ROM", final_rom),
        ):
            for dangling in (False, True):
                accepted_manifest.write_bytes(accepted_manifest_bytes)
                final_rom.write_bytes(accepted_rom_bytes)
                write_candidate_pair()
                leaf_bytes = leaf.read_bytes()
                target = root / (
                    f"{leaf.name}.{label.replace(' ', '-')}"
                    f".{'dangling' if dangling else 'target'}"
                )
                target.unlink(missing_ok=True)
                leaf.unlink()
                if not dangling:
                    target.write_bytes(leaf_bytes)
                leaf.symlink_to(target.name)
                watched = (
                    *accepted_paths,
                    *candidate_paths,
                    target,
                    journal_path,
                )
                before = {
                    path: path_snapshot(path)
                    for path in watched
                }
                try:
                    publish_pair(
                        candidate_manifest,
                        candidate_rom,
                        accepted_manifest,
                        final_rom,
                        verify=verify_publish_pair,
                    )
                except ManifestError:
                    pass
                else:
                    require(
                        False,
                        f"{label} "
                        f"{'dangling ' if dangling else ''}symlink passed",
                    )
                require(
                    {
                        path: path_snapshot(path)
                        for path in watched
                    }
                    == before
                    and not list(root.glob(".*.publish.*")),
                    f"{label} symlink rejection changed publication state",
                )
                leaf.unlink()
                target.unlink(missing_ok=True)
                leaf.write_bytes(leaf_bytes)

        for label, leaf in (
            ("final manifest", accepted_manifest),
            ("final ROM", final_rom),
        ):
            accepted_manifest.write_bytes(accepted_manifest_bytes)
            final_rom.write_bytes(accepted_rom_bytes)
            write_candidate_pair()
            leaf_bytes = leaf.read_bytes()
            target = root / f"{leaf.name}.dotdot-target"
            target.write_bytes(leaf_bytes)
            leaf.unlink()
            leaf.symlink_to(target.name)
            missing_parent = root / f"{leaf.name}.missing-parent"
            require(
                not missing_parent.exists(),
                "dot-dot symlink fixture parent unexpectedly exists",
            )
            dotdot_alias = missing_parent / ".." / leaf.name
            watched = (
                *accepted_paths,
                *candidate_paths,
                target,
                journal_path,
            )
            before = {
                path: path_snapshot(path)
                for path in watched
            }
            try:
                publish_pair(
                    candidate_manifest,
                    candidate_rom,
                    (
                        dotdot_alias
                        if label == "final manifest"
                        else accepted_manifest
                    ),
                    (
                        dotdot_alias
                        if label == "final ROM"
                        else final_rom
                    ),
                    verify=verify_publish_pair,
                )
            except ManifestError:
                pass
            else:
                require(False, f"missing/../{label} symlink passed")
            require(
                {
                    path: path_snapshot(path)
                    for path in watched
                }
                == before
                and not list(root.glob(".*.publish.*")),
                f"missing/../{label} rejection changed publication state",
            )
            leaf.unlink()
            target.unlink()
            leaf.write_bytes(leaf_bytes)

        for label, candidate, final in (
            ("manifest", candidate_manifest, accepted_manifest),
            ("ROM", candidate_rom, final_rom),
        ):
            accepted_manifest.write_bytes(accepted_manifest_bytes)
            final_rom.write_bytes(accepted_rom_bytes)
            write_candidate_pair()
            alias_parent = root / f"{label}-alias-parent"
            alias_parent.mkdir(exist_ok=True)
            final_alias = alias_parent / ".." / candidate.name
            watched = (*accepted_paths, *candidate_paths, journal_path)
            before = {
                path: path_snapshot(path)
                for path in watched
            }
            try:
                publish_pair(
                    candidate_manifest,
                    candidate_rom,
                    final_alias if label == "manifest" else accepted_manifest,
                    final_alias if label == "ROM" else final_rom,
                    verify=verify_publish_pair,
                )
            except ManifestError:
                pass
            else:
                require(False, f"resolved {label} path alias passed")
            require(
                {
                    path: path_snapshot(path)
                    for path in watched
                }
                == before
                and not list(root.glob(".*.publish.*")),
                f"resolved {label} alias changed publication state",
            )

        accepted_manifest.write_bytes(accepted_manifest_bytes)
        final_rom.write_bytes(accepted_rom_bytes)
        write_candidate_pair()
        swap_target = root / "candidate-rom-after-verify.nds"

        def swap_candidate_after_verify(
            manifest: Path,
            rom: Path,
        ) -> None:
            verify_publish_pair(manifest, rom)
            swap_target.write_bytes(rom.read_bytes())
            rom.unlink()
            rom.symlink_to(swap_target.name)

        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=swap_candidate_after_verify,
            )
        except ManifestError:
            pass
        else:
            require(False, "post-verify candidate symlink swap passed")
        require(
            accepted_manifest.read_bytes() == accepted_manifest_bytes
            and final_rom.read_bytes() == accepted_rom_bytes
            and candidate_rom.is_symlink()
            and swap_target.read_bytes() == candidate_rom_bytes
            and candidate_manifest.is_file()
            and not journal_path.exists()
            and not list(root.glob(".*.publish.*")),
            "post-verify candidate symlink rejection changed accepted state",
        )
        candidate_rom.unlink()
        swap_target.unlink()
        write_candidate_pair()

        accepted_manifest.write_bytes(accepted_manifest_bytes)
        final_rom.write_bytes(accepted_rom_bytes)
        write_candidate_pair()
        journal_swap_target = root / "journal-after-verify-target.json"
        journal_swap_snapshot: dict[Path, tuple[object, ...]] = {}

        def swap_journal_after_verify(
            manifest: Path,
            rom: Path,
        ) -> None:
            verify_publish_pair(manifest, rom)
            journal_swap_target.write_text("{}\n")
            journal_path.symlink_to(journal_swap_target.name)
            for path in (
                *accepted_paths,
                *candidate_paths,
                journal_path,
                journal_swap_target,
            ):
                journal_swap_snapshot[path] = path_snapshot(path)

        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=swap_journal_after_verify,
            )
        except ManifestError:
            pass
        else:
            require(False, "post-verify journal symlink swap passed")
        require(
            journal_swap_snapshot
            and {
                path: path_snapshot(path)
                for path in journal_swap_snapshot
            }
            == journal_swap_snapshot
            and not list(root.glob(".*.publish.*")),
            "post-verify journal symlink rejection changed topology",
        )
        journal_path.unlink()
        journal_swap_target.unlink()

        for field in ("backup", "stage"):
            for entry_index, final in enumerate(accepted_paths):
                accepted_manifest.write_bytes(accepted_manifest_bytes)
                final_rom.write_bytes(accepted_rom_bytes)
                write_candidate_pair()
                prior_records = {
                    path: file_record(path)
                    for path in accepted_paths
                }
                backups = {
                    path: root / f".{path.name}.publish.backup{entry_index}"
                    for path in accepted_paths
                }
                stages = {
                    path: root / f".{path.name}.publish.stage{entry_index}"
                    for path in accepted_paths
                }
                for path in backups.values():
                    path.write_bytes(b"journal backup fixture\n")
                for path in stages.values():
                    path.write_bytes(b"journal stage fixture\n")
                symlink_leaf = (
                    backups[final] if field == "backup" else stages[final]
                )
                symlink_target = root / (
                    f".{final.name}.publish.{field}-target{entry_index}"
                )
                symlink_target.write_bytes(symlink_leaf.read_bytes())
                symlink_leaf.unlink()
                symlink_leaf.symlink_to(symlink_target.name)
                journal_document = {
                    "schema": "pokemon-move-history-pair-publish-v1",
                    "entries": [
                        {
                            "final": str(path.resolve()),
                            "prior": prior_records[path],
                            "backup": str(backups[path].absolute()),
                            "stage": str(stages[path].absolute()),
                        }
                        for path in accepted_paths
                    ],
                }
                journal_path.write_text(
                    json.dumps(journal_document, sort_keys=True) + "\n"
                )
                watched = (
                    *accepted_paths,
                    *candidate_paths,
                    *backups.values(),
                    *stages.values(),
                    symlink_target,
                    journal_path,
                )
                before = {
                    path: path_snapshot(path)
                    for path in watched
                }
                try:
                    publish_pair(
                        candidate_manifest,
                        candidate_rom,
                        accepted_manifest,
                        final_rom,
                        verify=verify_publish_pair,
                    )
                except ManifestError:
                    pass
                else:
                    require(
                        False,
                        f"journal {field} symlink passed recovery",
                    )
                require(
                    {
                        path: path_snapshot(path)
                        for path in watched
                    }
                    == before,
                    f"journal {field} symlink changed recovery state",
                )
                journal_path.unlink()
                for path in (*backups.values(), *stages.values()):
                    path.unlink(missing_ok=True)
                symlink_target.unlink()

        accepted_manifest.write_bytes(accepted_manifest_bytes)
        final_rom.write_bytes(accepted_rom_bytes)
        write_candidate_pair()
        journal_target = root / "journal-target.json"
        journal_target.write_text("{}\n")
        journal_path.symlink_to(journal_target.name)
        watched = (
            *accepted_paths,
            *candidate_paths,
            journal_path,
            journal_target,
        )
        before = {path: path_snapshot(path) for path in watched}
        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=verify_publish_pair,
            )
        except ManifestError:
            pass
        else:
            require(False, "symlink recovery journal passed")
        require(
            {path: path_snapshot(path) for path in watched} == before,
            "symlink recovery journal changed publication state",
        )
        journal_path.unlink()
        journal_target.unlink()

        for failure_phase in (
            "after_manifest_replace",
            "after_rom_replace",
        ):
            accepted_manifest.write_bytes(accepted_manifest_bytes)
            final_rom.write_bytes(accepted_rom_bytes)
            write_candidate_pair()

            def fail_at_phase(phase: str, expected: str = failure_phase) -> None:
                if phase == expected:
                    raise RuntimeError(f"injected publish failure: {phase}")

            try:
                publish_pair(
                    candidate_manifest,
                    candidate_rom,
                    accepted_manifest,
                    final_rom,
                    verify=verify_publish_pair,
                    failure_hook=fail_at_phase,
                )
            except RuntimeError:
                pass
            else:
                require(False, f"{failure_phase} publish failure was ignored")
            require(
                accepted_manifest.read_bytes() == accepted_manifest_bytes
                and final_rom.read_bytes() == accepted_rom_bytes,
                f"{failure_phase} changed the prior accepted pair",
            )
            require(
                candidate_manifest.is_file() and candidate_rom.is_file(),
                f"{failure_phase} destroyed the candidate pair",
            )
            require(
                not list(root.glob(".*.publish.*")),
                f"{failure_phase} left transactional publish files",
            )

        accepted_manifest.write_bytes(accepted_manifest_bytes)
        final_rom.write_bytes(accepted_rom_bytes)
        write_candidate_pair()
        replace_count = 0

        def fail_once_during_second_restore(
            source: str | Path,
            destination: str | Path,
        ) -> None:
            nonlocal replace_count
            replace_count += 1
            if replace_count == 4:
                raise OSError("injected second-restore failure")
            os.replace(source, destination)

        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=verify_publish_pair,
                failure_hook=lambda phase: (
                    (_ for _ in ()).throw(RuntimeError(phase))
                    if phase == "after_rom_replace"
                    else None
                ),
                replace=fail_once_during_second_restore,
            )
        except RuntimeError:
            pass
        else:
            require(False, "rollback retry fixture ignored publish failure")
        require(
            replace_count == 5
            and accepted_manifest.read_bytes() == accepted_manifest_bytes
            and final_rom.read_bytes() == accepted_rom_bytes
            and not list(root.glob("*.publish-journal"))
            and not list(root.glob(".*.publish.*")),
            "rollback retry did not restore the accepted pair exactly",
        )

        accepted_manifest.write_bytes(accepted_manifest_bytes)
        final_rom.write_bytes(accepted_rom_bytes)
        write_candidate_pair()
        persistent_replace_count = 0

        def fail_persistently_during_second_restore(
            source: str | Path,
            destination: str | Path,
        ) -> None:
            nonlocal persistent_replace_count
            persistent_replace_count += 1
            if persistent_replace_count >= 4:
                raise OSError("persistent injected restore failure")
            os.replace(source, destination)

        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=verify_publish_pair,
                failure_hook=lambda phase: (
                    (_ for _ in ()).throw(RuntimeError(phase))
                    if phase == "after_rom_replace"
                    else None
                ),
                replace=fail_persistently_during_second_restore,
            )
        except ManifestError:
            pass
        else:
            require(False, "incomplete rollback discarded its recovery state")
        journals = list(root.glob("*.publish-journal"))
        require(
            len(journals) == 1
            and list(root.glob(".*.publish.*")),
            "incomplete rollback did not retain its journal/backup",
        )

        def stop_after_recovery(_manifest: Path, _rom: Path) -> None:
            raise RuntimeError("recovery-only fixture stop")

        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=stop_after_recovery,
            )
        except RuntimeError:
            pass
        else:
            require(False, "startup recovery fixture did not stop")
        require(
            accepted_manifest.read_bytes() == accepted_manifest_bytes
            and final_rom.read_bytes() == accepted_rom_bytes
            and not list(root.glob("*.publish-journal"))
            and not list(root.glob(".*.publish.*")),
            "startup journal recovery did not restore the accepted pair",
        )

        malformed_journal = accepted_manifest.with_name(
            accepted_manifest.name + ".publish-journal"
        )
        malformed_temporaries = (
            root / ".accepted.json.publish.backup",
            root / ".accepted.nds.publish.backup",
            root / ".accepted.nds.publish.stage",
        )
        for temporary in malformed_temporaries:
            temporary.write_bytes(b"malformed journal fixture\n")
        malformed_journal.write_text(
            json.dumps(
                {
                    "schema": "pokemon-move-history-pair-publish-v1",
                    "entries": [
                        {
                            "final": str(accepted_manifest.resolve()),
                            "prior": file_record(accepted_manifest),
                            "backup": str(
                                malformed_temporaries[0].resolve()
                            ),
                            "stage": str(accepted_manifest.resolve()),
                        },
                        {
                            "final": str(final_rom.resolve()),
                            "prior": file_record(final_rom),
                            "backup": str(
                                malformed_temporaries[1].resolve()
                            ),
                            "stage": str(
                                malformed_temporaries[2].resolve()
                            ),
                        },
                    ],
                },
                sort_keys=True,
            )
            + "\n"
        )
        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=verify_publish_pair,
            )
        except ManifestError:
            pass
        else:
            require(False, "malformed journal path was accepted")
        require(
            accepted_manifest.read_bytes() == accepted_manifest_bytes
            and final_rom.read_bytes() == accepted_rom_bytes
            and malformed_journal.is_file()
            and all(path.is_file() for path in malformed_temporaries),
            "malformed journal path altered or deleted accepted files",
        )
        malformed_journal.unlink()
        for temporary in malformed_temporaries:
            temporary.unlink()

        accepted_manifest.unlink()
        final_rom.unlink()
        write_candidate_pair()
        try:
            publish_pair(
                candidate_manifest,
                candidate_rom,
                accepted_manifest,
                final_rom,
                verify=verify_publish_pair,
                failure_hook=lambda phase: (
                    (_ for _ in ()).throw(RuntimeError(phase))
                    if phase == "after_manifest_replace"
                    else None
                ),
            )
        except RuntimeError:
            pass
        else:
            require(False, "first-publish failure was ignored")
        require(
            not accepted_manifest.exists() and not final_rom.exists(),
            "failed first publish left a partial final pair",
        )

        accepted_manifest.write_bytes(accepted_manifest_bytes)
        final_rom.write_bytes(accepted_rom_bytes)
        write_candidate_pair()
        publish_pair(
            candidate_manifest,
            candidate_rom,
            accepted_manifest,
            final_rom,
            verify=verify_publish_pair,
        )
        verify_publish_pair(accepted_manifest, final_rom)
        require(
            final_rom.read_bytes() == candidate_rom_bytes
            and not candidate_manifest.exists()
            and not candidate_rom.exists(),
            "successful transactional pair publication differs",
        )

        require(
            (packaged_manifest is None) == (packaged_rom is None),
            "real Make/publish fixture inputs are incomplete",
        )
        if packaged_manifest is not None and packaged_rom is not None:
            cli_candidate_rom = root / "cli-candidate.nds"
            cli_candidate_manifest = root / "cli-candidate.json"
            cli_final_rom = root / "cli-final.nds"
            cli_final_manifest = root / "cli-final.json"
            cli_sentinel = root / "make-continued"
            try:
                os.link(packaged_rom, cli_candidate_rom)
            except OSError:
                shutil.copyfile(packaged_rom, cli_candidate_rom)
            cli_candidate_manifest.write_bytes(
                packaged_manifest.read_bytes()
            )
            cli_final_rom.write_bytes(accepted_rom_bytes)
            cli_final_manifest.write_bytes(accepted_manifest_bytes)
            cli_makefile = root / "Makefile.publish-fixture"
            publish_arguments = [
                sys.executable,
                str(
                    REPO
                    / "scripts/pokemon_move_history_build_manifest.py"
                ),
                "--publish-pair",
                "--candidate-manifest",
                str(cli_candidate_manifest),
                "--candidate-rom",
                str(cli_candidate_rom),
                "--final-manifest",
                str(cli_final_manifest),
                "--final-rom",
                str(cli_final_rom),
            ]
            cli_makefile.write_text(
                "all:\n"
                "\tPOKEMON_MOVE_HISTORY_TEST_PUBLISH_FAILURE="
                "after_manifest_replace "
                + " ".join(
                    shlex.quote(word) for word in publish_arguments
                )
                + "\n"
                + "\ttouch "
                + shlex.quote(str(cli_sentinel))
                + "\n"
            )
            make_result = subprocess.run(
                ["make", "-f", str(cli_makefile)],
                cwd=REPO,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            require(
                make_result.returncode != 0
                and not cli_sentinel.exists()
                and cli_final_manifest.read_bytes()
                == accepted_manifest_bytes
                and cli_final_rom.read_bytes() == accepted_rom_bytes
                and cli_candidate_manifest.is_file()
                and cli_candidate_rom.is_file()
                and not list(root.glob("*.publish-journal")),
                "real Make/CLI failure did not stop before preserving the "
                "accepted pair:\n" + make_result.stdout,
            )

        malformed = root / "malformed.json"
        malformed.write_text('{"schema":')
        try:
            load_manifest(malformed)
        except ManifestError:
            pass
        else:
            require(False, "truncated manifest JSON is accepted")


def host_fixtures(
    packaged_manifest: Path | None = None,
    packaged_rom: Path | None = None,
) -> None:
    max_moves = 24
    _canonical, _custom, num_moves = move_limits()
    unimplemented = {777}

    def valid(move: int) -> bool:
        return move != 0 and move < num_moves and move not in unimplemented

    def record(history: list[int], moves: list[int]) -> bool:
        changed = False
        for move in moves:
            if valid(move) and move not in history:
                if len(history) == max_moves:
                    history.pop(0)
                history.append(move)
                changed = True
        return changed

    def make_public_state(existing_record: bool) -> dict[str, object]:
        return {
            "allocated": existing_record,
            "allocations": 0,
            "dirty": False,
            "revision": 0,
            "history": [31] if existing_record else [],
            "moves": [1, 2, 3, 4],
            "mutations": 0,
            "snapshot_reads": 0,
            "store_accesses": 0,
        }

    def clone_public_state(state: dict[str, object]) -> dict[str, object]:
        return {
            key: list(value) if isinstance(value, list) else value
            for key, value in state.items()
        }

    def public_append(state: dict[str, object], move: int) -> bool:
        history = state["history"]
        require(isinstance(history, list), "fixture history type differs")
        if not valid(move) or move in history:
            return False
        history.append(move)
        state["dirty"] = True
        state["revision"] = int(state["revision"]) + 1
        return True

    def public_observe(state: dict[str, object]) -> None:
        state["store_accesses"] = int(state["store_accesses"]) + 1
        if not state["allocated"]:
            state["allocated"] = True
            state["allocations"] = int(state["allocations"]) + 1
            state["dirty"] = True
            state["revision"] = int(state["revision"]) + 1
        moves = state["moves"]
        require(isinstance(moves, list), "fixture move-slot type differs")
        for current_move in moves:
            public_append(state, current_move)

    def record_move_public(state: dict[str, object], move: int) -> bool:
        if not valid(move):
            return False
        state["snapshot_reads"] = int(state["snapshot_reads"]) + 1
        public_observe(state)
        public_append(state, move)
        return True

    def replace_move_public(
        state: dict[str, object],
        slot: int,
        move: int,
    ) -> bool:
        moves = state["moves"]
        require(isinstance(moves, list), "fixture move-slot type differs")
        if not valid(move) or not 0 <= slot < 4:
            return False
        if moves[slot] == move:
            return False
        state["snapshot_reads"] = int(state["snapshot_reads"]) + 1
        public_observe(state)
        moves[slot] = move
        state["mutations"] = int(state["mutations"]) + 1
        public_append(state, move)
        return True

    def replace(
        history: list[int],
        current: list[int],
        slot: int,
        move: int,
        *,
        committed: bool = True,
        snapshot_ok: bool = True,
    ) -> tuple[list[int], list[int], bool, bool]:
        before = list(current)
        dirty = False
        mutated = False
        if (
            not committed
            or not valid(move)
            or not 0 <= slot < 4
            or not snapshot_ok
            or before[slot] == move
        ):
            return history, current, dirty, mutated
        dirty |= record(history, before)
        current[slot] = move
        mutated = True
        dirty |= record(history, [move])
        return history, current, dirty, mutated

    history: list[int] = []
    dirty = record(history, [10, 20, 30, 0])
    require(dirty and history == [10, 20, 30], "first observation order differs")
    dirty = record(history, [10, 20, 30, 40])
    require(dirty and history == [10, 20, 30, 40], "append order differs")
    before = list(history)
    require(
        not record(history, [10, 20, 30, 40]) and history == before,
        "second reconciliation churns history",
    )

    history, current, dirty, mutated = replace([], [1, 2, 3, 4], 1, 9)
    require(
        dirty
        and mutated
        and history == [1, 2, 3, 4, 9]
        and current == [1, 9, 3, 4],
        "replacement is not old-slot order followed by learned move",
    )
    before = (list(history), list(current))
    history, current, dirty, mutated = replace(history, current, 1, 9)
    require(
        not dirty and not mutated and (history, current) == before,
        "duplicate/no-op assignment changes Pokémon or history",
    )

    canceled_history, canceled_current, dirty, mutated = replace(
        [],
        [5, 6, 7, 8],
        2,
        9,
        committed=False,
    )
    require(
        not dirty
        and not mutated
        and canceled_history == []
        and canceled_current == [5, 6, 7, 8],
        "canceled prompt fixture changed state",
    )
    invalid_history = [31]
    invalid_before = list(invalid_history)
    dirty = record(invalid_history, [0, 777, num_moves])
    require(
        not dirty and invalid_history == invalid_before,
        "invalid-only observation dirties or changes history",
    )
    high_valid = num_moves - 23
    require(
        high_valid > 0
        and valid(high_valid)
        and record(invalid_history, [high_valid])
        and invalid_history == [31, high_valid],
        "implemented high move ID is incorrectly rejected",
    )
    for invalid_move in (0, 777, num_moves):
        invalid_history = [31]
        invalid_current = [1, 2, 3, 4]
        before_invalid = (list(invalid_history), list(invalid_current))
        (
            invalid_history,
            invalid_current,
            dirty,
            mutated,
        ) = replace(invalid_history, invalid_current, 1, invalid_move)
        require(
            not dirty
            and not mutated
            and (invalid_history, invalid_current) == before_invalid,
            f"invalid replacement {invalid_move} dirties or mutates state",
        )
        for existing_record in (False, True):
            for public_path in (record_move_public, replace_move_public):
                public_state = make_public_state(existing_record)
                public_before = clone_public_state(public_state)
                if public_path is record_move_public:
                    success = record_move_public(public_state, invalid_move)
                else:
                    success = replace_move_public(
                        public_state,
                        1,
                        invalid_move,
                    )
                require(
                    not success
                    and public_state == public_before
                    and public_state["allocations"] == 0
                    and public_state["dirty"] is False
                    and public_state["revision"] == 0
                    and public_state["snapshot_reads"] == 0
                    and public_state["store_accesses"] == 0
                    and public_state["mutations"] == 0,
                    f"invalid {public_path.__name__} input {invalid_move} "
                    f"changes empty/existing={existing_record} state",
                )
    for existing_record in (False, True):
        same_slot_state = make_public_state(existing_record)
        same_slot_before = clone_public_state(same_slot_state)
        same_slot_success = replace_move_public(same_slot_state, 1, 2)
        require(
            not same_slot_success
            and same_slot_state == same_slot_before
            and same_slot_state["allocations"] == 0
            and same_slot_state["dirty"] is False
            and same_slot_state["revision"] == 0
            and same_slot_state["mutations"] == 0
            and same_slot_state["snapshot_reads"] == 0
            and same_slot_state["store_accesses"] == 0,
            f"same-slot ReplaceMove changes or accesses "
            f"empty/existing={existing_record} state",
        )
    valid_record_state = make_public_state(False)
    require(
        record_move_public(valid_record_state, high_valid)
        and valid_record_state["allocated"] is True
        and valid_record_state["allocations"] == 1
        and valid_record_state["dirty"] is True
        and int(valid_record_state["revision"]) > 0
        and valid_record_state["snapshot_reads"] == 1
        and valid_record_state["store_accesses"] == 1
        and valid_record_state["mutations"] == 0,
        "valid high-ID RecordMove control does not succeed and record state",
    )
    valid_replace_state = make_public_state(False)
    require(
        replace_move_public(valid_replace_state, 1, high_valid)
        and valid_replace_state["allocated"] is True
        and valid_replace_state["allocations"] == 1
        and valid_replace_state["dirty"] is True
        and int(valid_replace_state["revision"]) > 0
        and valid_replace_state["mutations"] == 1
        and valid_replace_state["snapshot_reads"] == 1
        and valid_replace_state["store_accesses"] == 1
        and valid_replace_state["moves"] == [1, high_valid, 3, 4],
        "valid high-ID ReplaceMove control does not mutate and record state",
    )
    (
        capture_history,
        capture_current,
        dirty,
        mutated,
    ) = replace([], [1, 2, 3, 4], 1, 9, snapshot_ok=False)
    require(
        not dirty
        and not mutated
        and capture_history == []
        and capture_current == [1, 2, 3, 4],
        "snapshot failure mutates Pokémon or history",
    )

    delete_history: list[int] = []
    delete_current = [21, 22, 23, 24]
    require(
        record(delete_history, delete_current),
        "committed deletion did not capture the old slots",
    )
    delete_current = [21, 23, 24, 0]
    require(
        delete_history == [21, 22, 23, 24]
        and delete_current == [21, 23, 24, 0],
        "committed deletion lost the forgotten move or appended MOVE_NONE",
    )
    scanner_base = 0x02000000
    scanner_image = b"\x00\xf0\x00\xf8\x80\x47"
    require(
        packaged_thumb_calls(
            scanner_image,
            scanner_base,
            scanner_base,
            len(scanner_image),
        )
        == [
            (scanner_base, "bl", scanner_base + 4),
            (scanner_base + 4, "blx_reg", 0),
        ],
        "packaged call scanner does not decode BL and BLX-register forms",
    )
    manifest_mutation_fixtures(packaged_manifest, packaged_rom)


def symbol_table(path: Path) -> dict[str, int]:
    output = subprocess.check_output(
        ["arm-none-eabi-nm", "-n", str(path)], text=True
    )
    symbols: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            symbols[parts[2]] = int(parts[0], 16)
    return symbols


def symbol_sizes(path: Path) -> dict[str, int]:
    output = subprocess.check_output(
        ["arm-none-eabi-nm", "-S", str(path)],
        text=True,
    )
    sizes: dict[str, int] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            sizes[parts[3]] = int(parts[1], 16)
    return sizes


def thumb_bl_target(image: bytes, base: int, address: int) -> int:
    offset = address - base
    first, second = struct.unpack_from("<HH", image, offset)
    require(
        first & 0xF800 == 0xF000 and second & 0xF800 == 0xF800,
        f"0x{address:08X} is not a Thumb-1 BL",
    )
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return address + 4 + delta


def thumb_blx_target(image: bytes, base: int, address: int) -> int:
    offset = address - base
    first, second = struct.unpack_from("<HH", image, offset)
    require(
        first & 0xF800 == 0xF000 and second & 0xF800 == 0xE800,
        f"0x{address:08X} is not a Thumb-1 BLX immediate",
    )
    delta = ((first & 0x7FF) << 12) | ((second & 0x7FF) << 1)
    if delta & (1 << 22):
        delta -= 1 << 23
    return ((address + 4) & ~3) + delta


def thumb_conditional_branch(
    image: bytes,
    base: int,
    address: int,
    condition: int,
) -> int:
    halfword = struct.unpack_from("<H", image, address - base)[0]
    require(
        halfword & 0xF000 == 0xD000
        and (halfword >> 8) & 0xF == condition,
        f"0x{address:08X} is not the expected Thumb conditional branch",
    )
    delta = (halfword & 0xFF) << 1
    if delta & 0x100:
        delta -= 0x200
    return address + 4 + delta


def thumb_literal_load(
    image: bytes,
    base: int,
    address: int,
    register: int,
) -> tuple[int, int]:
    halfword = struct.unpack_from("<H", image, address - base)[0]
    require(
        halfword & 0xF800 == 0x4800
        and (halfword >> 8) & 0x7 == register,
        f"0x{address:08X} is not the expected Thumb literal load",
    )
    literal_address = ((address + 4) & ~3) + ((halfword & 0xFF) << 2)
    value = struct.unpack_from("<I", image, literal_address - base)[0]
    return literal_address, value


def encode_thumb_blx(address: int, target: int) -> bytes:
    delta = target - ((address + 4) & ~3)
    require(
        -(1 << 22) <= delta < (1 << 22)
        and delta % 4 == 0
        and target % 4 == 0,
        f"Thumb BLX 0x{address:08X}->0x{target:08X} is out of range/alignment",
    )
    first = 0xF000 | ((delta >> 12) & 0x7FF)
    second = 0xE800 | ((delta >> 1) & 0x7FF)
    return struct.pack("<HH", first, second)


def direct_thumb_calls(disassembly: str) -> list[tuple[int, str, int]]:
    call_line = re.compile(
        r"^\s*([0-9a-f]+):\s+"
        r"[0-9a-f]{4}(?:\s+[0-9a-f]{4})?\s+"
        r"(bl|blx)\s+([0-9a-f]+)\b"
    )
    calls: list[tuple[int, str, int]] = []
    for line in disassembly.splitlines():
        match = call_line.match(line)
        if match is not None:
            calls.append(
                (
                    int(match.group(1), 16),
                    match.group(2),
                    int(match.group(3), 16),
                )
            )
    return calls


def packaged_thumb_calls(
    image: bytes,
    base: int,
    address: int,
    size: int,
) -> list[tuple[int, str, int]]:
    calls: list[tuple[int, str, int]] = []
    cursor = address
    end = address + size
    while cursor + 2 <= end:
        halfword = struct.unpack_from("<H", image, cursor - base)[0]
        if cursor + 4 <= end and halfword & 0xF800 == 0xF000:
            second = struct.unpack_from("<H", image, cursor + 2 - base)[0]
            if second & 0xF800 == 0xF800:
                calls.append(
                    (
                        cursor,
                        "bl",
                        thumb_bl_target(image, base, cursor),
                    )
                )
                cursor += 4
                continue
            if second & 0xF800 == 0xE800:
                calls.append(
                    (
                        cursor,
                        "blx",
                        thumb_blx_target(image, base, cursor),
                    )
                )
                cursor += 4
                continue
        if halfword & 0xFF87 == 0x4780:
            calls.append((cursor, "blx_reg", (halfword >> 3) & 0xF))
        cursor += 2
    return calls


def call_inventory_sha256(
    calls: list[tuple[int, str, int]],
) -> str:
    canonical = "\n".join(
        f"{address:08x}:{kind}:{target:08x}"
        for address, kind, target in calls
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def elf_bytes_at(path: Path, address: int, size: int) -> bytes:
    image = path.read_bytes()
    require(image[:4] == b"\x7fELF", f"{path} is not ELF")
    require(image[4:6] == b"\x01\x01", f"{path} is not little-endian ELF32")
    section_offset = struct.unpack_from("<I", image, 0x20)[0]
    section_entry_size = struct.unpack_from("<H", image, 0x2E)[0]
    section_count = struct.unpack_from("<H", image, 0x30)[0]
    require(
        section_entry_size >= 40
        and section_offset + section_entry_size * section_count <= len(image),
        f"{path} section table is invalid",
    )
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        (
            _name,
            _type,
            _flags,
            section_address,
            file_offset,
            section_size,
        ) = struct.unpack_from("<6I", image, offset)
        if (
            section_address <= address
            and address + size <= section_address + section_size
        ):
            start = file_offset + address - section_address
            require(
                start + size <= len(image),
                f"{path} section payload is truncated",
            )
            return image[start:start + size]
    require(False, f"0x{address:08X}+0x{size:X} is absent from {path}")
    return b""


@dataclass(frozen=True)
class OverlayComponent:
    overlay_id: int
    ordinal: int
    ram_address: int
    ram_size: int
    bss_size: int
    static_init_start: int
    static_init_end: int
    file_id: int
    flags: int
    fat_start: int
    fat_end: int
    data: bytes


EXPECTED_OVERLAY_METADATA = {
    12: (
        0x022378C0,
        0x37380,
        0,
        0x0226EC08,
        0x0226EC10,
        12,
        0,
        0x1D3200,
        0x20A580,
    ),
    68: (
        0x021E5900,
        0x2800,
        0,
        0x021E80E4,
        0x021E80E8,
        68,
        0,
        0x2E5200,
        0x2E7A00,
    ),
    65: (
        0x0221BE20,
        0x4380,
        0,
        0x02220194,
        0x02220198,
        65,
        0,
        0x2DF800,
        0x2E3B80,
    ),
    70: (
        0x022378C0,
        0xEF40,
        0x160,
        0x02246090,
        0x02246094,
        70,
        0,
        0x2E9400,
        0x2F8340,
    ),
    112: (
        0x021E5900,
        0x1A0E0,
        0x2C0,
        0x021FF4E8,
        0x021FF4EC,
        112,
        0,
        0x3B5200,
        0x3CF2E0,
    ),
    129: (
        0x023D8000,
        0x7FC0,
        0,
        0,
        0,
        129,
        0,
        0x3DAA00,
        0x3E29C0,
    ),
    131: (
        0x023C8000,
        0x4FD2,
        0,
        0,
        0,
        131,
        0,
        0x3F3400,
        0x3F83D2,
    ),
    153: (
        OVERLAY_BASE,
        0xF6C,
        0,
        0,
        0,
        153,
        0,
        0x421600,
        0x42256C,
    ),
    154: (
        0x023C0400,
        0x14E8,
        0,
        0,
        0,
        154,
        0,
        0x422600,
        0x423AE8,
    ),
    155: (
        OVERLAY155_BASE,
        0x994,
        0,
        0,
        0,
        155,
        0,
        0x423C00,
        0x424594,
    ),
}
OVERLAY129_THUNKS = {
    0x023DA872: bytes.fromhex("18 47"),
    0x023DA878: bytes.fromhex("30 47"),
    0x023DCB20: bytes.fromhex("18 47"),
    0x023DCB24: bytes.fromhex("28 47"),
    0x023DE0D6: bytes.fromhex("18 47"),
    0x023DE0D8: bytes.fromhex("30 47"),
    0x023DE0DA: bytes.fromhex("38 47"),
}


def packaged_components_from_bytes(
    rom: bytes,
) -> tuple[int, bytes, dict[int, OverlayComponent]]:
    require(len(rom) >= 0x160, "packaged ROM header is truncated")
    arm9_offset, _entry, arm9_base, arm9_size = struct.unpack_from(
        "<4I",
        rom,
        0x20,
    )
    fat_offset, fat_size = struct.unpack_from("<2I", rom, 0x48)
    overlay_offset, overlay_size = struct.unpack_from("<2I", rom, 0x50)
    require(
        arm9_offset + arm9_size <= len(rom),
        "packaged ARM9 extends past the ROM",
    )
    require(
        fat_offset + fat_size <= len(rom) and fat_size % 8 == 0,
        "packaged FAT is invalid",
    )
    require(
        overlay_offset + overlay_size <= len(rom)
        and overlay_size % 32 == 0,
        "packaged ARM9 overlay table is invalid",
    )
    rows = [
        struct.unpack_from("<8I", rom, offset)
        for offset in range(
            overlay_offset,
            overlay_offset + overlay_size,
            32,
        )
    ]
    overlay_ids = [row[0] for row in rows]
    file_ids_list = [row[6] for row in rows]
    require(
        len(set(overlay_ids)) == len(overlay_ids),
        "packaged overlay table contains duplicate overlay IDs",
    )
    require(
        len(set(file_ids_list)) == len(file_ids_list),
        "packaged overlay table contains duplicate file IDs",
    )
    overlays: dict[int, OverlayComponent] = {}
    for ordinal, fields in enumerate(rows):
        (
            overlay_id,
            ram_address,
            ram_size,
            bss_size,
            static_init_start,
            static_init_end,
            file_id,
            flags,
        ) = fields
        require(
            overlay_id == ordinal,
            f"overlay ID {overlay_id} differs from ordinal {ordinal}",
        )
        require(
            file_id * 8 + 8 <= fat_size,
            f"overlay {overlay_id} file ID is outside the FAT",
        )
        start, end = struct.unpack_from(
            "<2I",
            rom,
            fat_offset + file_id * 8,
        )
        require(
            start <= end <= len(rom),
            f"overlay {overlay_id} file extent is invalid",
        )
        component = OverlayComponent(
            overlay_id,
            ordinal,
            ram_address,
            ram_size,
            bss_size,
            static_init_start,
            static_init_end,
            file_id,
            flags,
            start,
            end,
            rom[start:end],
        )
        overlays[overlay_id] = component

    for overlay_id, expected in EXPECTED_OVERLAY_METADATA.items():
        require(
            overlay_id in overlays,
            f"packaged overlay {overlay_id} is absent",
        )
        component = overlays[overlay_id]
        actual = (
            component.ram_address,
            component.ram_size,
            component.bss_size,
            component.static_init_start,
            component.static_init_end,
            component.file_id,
            component.flags,
            component.fat_start,
            component.fat_end,
        )
        require(
            actual == expected,
            f"overlay {overlay_id} y9/FAT metadata differs",
        )
        require(
            component.ram_size == len(component.data),
            f"overlay {overlay_id} RAM size differs from uncompressed payload",
        )
    return arm9_base, rom[arm9_offset:arm9_offset + arm9_size], overlays


def packaged_components(
    rom_path: Path,
) -> tuple[int, bytes, dict[int, OverlayComponent]]:
    require(rom_path.is_file(), f"packaged ROM is absent: {rom_path}")
    return packaged_components_from_bytes(rom_path.read_bytes())


def bytes_at(image: bytes, base: int, address: int, size: int) -> bytes:
    offset = address - base
    require(
        offset >= 0 and offset + size <= len(image),
        f"0x{address:08X}..0x{address + size:08X} is outside its image",
    )
    return image[offset:offset + size]


def overlay129_predicate_matches(image: bytes, base: int) -> bool:
    address = 0x023D94C4
    if not (base <= address and address + 0x0E <= base + len(image)):
        return False
    try:
        target = thumb_bl_target(image, base, address + 4)
    except SystemExit:
        return False
    return (
        bytes_at(image, base, address, 0x0E)
        == bytes.fromhex("10 b5 09 21 ff f7 c0 ff 80 06 c0 0f 10 bd")
        and target == 0x023D944C
        and packaged_thumb_calls(image, base, address, 0x0E)
        == [(address + 4, "bl", 0x023D944C)]
    )


def overlay129_thunks_match(image: bytes, base: int) -> bool:
    return all(
        base <= address
        and address + len(expected) <= base + len(image)
        and image[address - base:address - base + len(expected)] == expected
        for address, expected in OVERLAY129_THUNKS.items()
    )


def packaged_metadata_mutation_fixtures(rom: bytes) -> None:
    y9_offset = struct.unpack_from("<I", rom, 0x50)[0]
    mutations: list[tuple[str, bytearray]] = []
    duplicate = bytearray(rom)
    struct.pack_into("<I", duplicate, y9_offset + 153 * 32, 152)
    mutations.append(("duplicate overlay ID", duplicate))
    wrong_size = bytearray(rom)
    struct.pack_into("<I", wrong_size, y9_offset + 153 * 32 + 8, 0xFA8)
    mutations.append(("overlay 153 RAM size", wrong_size))
    wrong_flags = bytearray(rom)
    struct.pack_into("<I", wrong_flags, y9_offset + 129 * 32 + 28, 1)
    mutations.append(("overlay 129 flags", wrong_flags))
    for field, label in enumerate(
        (
            "ID",
            "base",
            "RAM size",
            "BSS size",
            "init start",
            "init end",
            "file ID",
            "flags",
        )
    ):
        wrong_overlay131 = bytearray(rom)
        value = struct.unpack_from(
            "<I", wrong_overlay131, y9_offset + 131 * 32 + field * 4
        )[0]
        struct.pack_into(
            "<I",
            wrong_overlay131,
            y9_offset + 131 * 32 + field * 4,
            value ^ 1,
        )
        mutations.append((f"overlay 131 {label}", wrong_overlay131))
    for field, label in enumerate(
        (
            "ID",
            "base",
            "RAM size",
            "BSS size",
            "init start",
            "init end",
            "file ID",
            "flags",
        )
    ):
        wrong_overlay154 = bytearray(rom)
        value = struct.unpack_from(
            "<I", wrong_overlay154, y9_offset + 154 * 32 + field * 4
        )[0]
        struct.pack_into(
            "<I",
            wrong_overlay154,
            y9_offset + 154 * 32 + field * 4,
            value ^ 1,
        )
        mutations.append((f"overlay 154 {label}", wrong_overlay154))
    for field, label in enumerate(
        (
            "ID",
            "base",
            "RAM size",
            "BSS size",
            "init start",
            "init end",
            "file ID",
            "flags",
        )
    ):
        wrong_overlay155 = bytearray(rom)
        value = struct.unpack_from(
            "<I", wrong_overlay155, y9_offset + 155 * 32 + field * 4
        )[0]
        struct.pack_into(
            "<I",
            wrong_overlay155,
            y9_offset + 155 * 32 + field * 4,
            value ^ 1,
        )
        mutations.append((f"overlay 155 {label}", wrong_overlay155))
    for label, mutation in mutations:
        try:
            packaged_components_from_bytes(bytes(mutation))
        except SystemExit:
            pass
        else:
            require(False, f"mutated {label} passes packaged metadata checks")


def binary_contracts(rom_path: Path, manifest_path: Path) -> None:
    linked = REPO / "build/pokemon_move_history_overlay_linked.o"
    overlay_path = REPO / "build/output_pokemon_move_history_overlay.bin"
    arm9_path = REPO / "base/arm9.bin"
    ov12_path = REPO / "base/overlay/overlay_0012.bin"
    ov68_path = REPO / "base/overlay/overlay_0068.bin"
    ov112_path = REPO / "base/overlay/overlay_0112.bin"
    ov129_path = REPO / "base/overlay/overlay_0129.bin"
    ov131_path = REPO / "base/overlay/overlay_0131.bin"
    ov153_path = REPO / "base/overlay/overlay_0153.bin"
    ov154_path = REPO / "base/overlay/overlay_0154.bin"
    ov155_path = REPO / "base/overlay/overlay_0155.bin"
    task6_linked = (
        REPO / "build/pokemon_move_history_task6_overlay_linked.o"
    )
    task6_overlay = (
        REPO / "build/output_pokemon_move_history_task6_overlay.bin"
    )
    task6_object = (
        REPO
        / "build/pokemon_move_history_task6_overlay/"
        "pokemon_move_history_task6.o"
    )
    task6_entry_object = (
        REPO / "build/pokemon_move_history_task6_overlay/entry.o"
    )
    pokemon_object = REPO / "build/pokemon.o"
    party_menu_object = REPO / "build/party_menu.o"
    save_object = REPO / "build/save.o"
    field_script_commands_object = (
        REPO / "build/field/script_commands.o"
    )
    field_linked = REPO / "build/field_linked.o"
    field_binary = REPO / "build/output_field.bin"
    history_object = (
        REPO / "build/pokemon_move_history_overlay/pokemon_move_history.o"
    )
    relearn_object = (
        REPO / "build/pokemon_move_history_overlay/pokemon_move_relearn.o"
    )
    summary_object = (
        REPO / "build/summary_move_relearn_overlay/summary_move_relearn.o"
    )
    summary_entry_object = (
        REPO / "build/summary_move_relearn_overlay/entry.o"
    )
    summary_linked = REPO / "build/summary_move_relearn_overlay_linked.o"
    summary_overlay = REPO / "build/output_summary_move_relearn_overlay.bin"
    overlay_object = REPO / "build/overlay.o"
    other_hook_object = REPO / "build/other_hook.o"
    core_linked = REPO / "build/linked.o"
    required_artifacts = (
        linked,
        overlay_path,
        arm9_path,
        ov12_path,
        ov68_path,
        ov112_path,
        ov129_path,
        ov131_path,
        ov153_path,
        ov154_path,
        ov155_path,
        task6_linked,
        task6_overlay,
        task6_object,
        task6_entry_object,
        pokemon_object,
        party_menu_object,
        save_object,
        field_script_commands_object,
        field_linked,
        field_binary,
        history_object,
        relearn_object,
        summary_object,
        summary_entry_object,
        summary_linked,
        summary_overlay,
        overlay_object,
        other_hook_object,
        core_linked,
        rom_path,
    )
    missing = [str(path) for path in required_artifacts if not path.is_file()]
    require(not missing, "required build artifacts are absent: " + ", ".join(missing))
    try:
        verify_manifest(manifest_path, rom_path)
    except ManifestError as exc:
        require(False, f"content-addressed build manifest rejected: {exc}")

    overlay = overlay_path.read_bytes()
    require(
        len(overlay) <= OVERLAY_LIMIT,
        f"overlay 153 exceeds guarded 0x{OVERLAY_LIMIT:X}-byte envelope",
    )
    symbols = symbol_table(linked)
    linked_symbol_sizes = symbol_sizes(linked)
    for name in (
        "PokemonMoveHistory_ReplaceMoveImpl",
        "PokemonMoveHistory_DeleteMoveSlotImpl",
    ):
        require(name in symbols, f"linked implementation {name} is missing")

    for object_name, api in (
        ("pokemon.o", "PokemonMoveHistory_RecordMove"),
        ("party_menu.o", "PokemonMoveHistory_ReplaceMove"),
    ):
        reloc = subprocess.check_output(
            [
                "arm-none-eabi-objdump",
                "-r",
                str(REPO / "build" / object_name),
            ],
            text=True,
        )
        require(
            re.search(rf"R_ARM_ABS32\s+{api}\b", reloc) is not None,
            f"{object_name} lacks long-call ABS32 relocation to {api}",
        )
        require(
            re.search(rf"R_ARM_THM_CALL\s+{api}\b", reloc) is None,
            f"{object_name} gained unsafe direct relocation to {api}",
        )
    pokemon_reloc = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(REPO / "build/pokemon.o"),
        ],
        text=True,
    )
    require(
        re.search(r"R_ARM_ABS32\s+SaveBlock2_get\b", pokemon_reloc)
        is not None,
        "pokemon.o lacks interworking-safe current-save resolution",
    )
    require(
        re.search(r"R_ARM_THM_CALL\s+SaveBlock2_get\b", pokemon_reloc)
        is None,
        "pokemon.o gained an unsafe direct SaveBlock2_get relocation",
    )
    save_reloc = subprocess.check_output(
        ["arm-none-eabi-objdump", "-r", str(save_object)],
        text=True,
    )
    for target in (
        "PokemonMoveHistory_Init",
        "PokemonMoveHistory_Reset",
        "PokemonMoveHistory_LoadAndSeedParty",
        "PokemonMoveHistory_PrepareSave",
        "PokemonMoveHistory_FinishSave",
        "PokemonMoveHistory_CancelSave",
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", save_reloc) is not None
            and re.search(rf"R_ARM_THM_CALL\s+{target}\b", save_reloc)
            is None,
            f"save.o lacks an interworking-safe lifecycle call to {target}",
        )
    require(
        re.search(r"R_ARM_THM_CALL\s+CancelAsyncSave\b", save_reloc)
        is None,
        "Save_Cancel still relocates to vanilla CancelAsyncSave",
    )
    field_script_reloc = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(field_script_commands_object),
        ],
        text=True,
    )
    for target in (
        "GetMoveMaxPP",
        "PokemonMoveHistoryTask6_ScriptTeachMove",
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", field_script_reloc)
            is not None
            and re.search(
                rf"R_ARM_THM_CALL\s+{target}\b",
                field_script_reloc,
            )
            is None,
            f"field script sanitizer lacks interworking-safe {target} calls",
        )

    history_reloc = subprocess.check_output(
        [
            "arm-none-eabi-objdump",
            "-r",
            str(REPO / "build/pokemon_move_history_overlay/pokemon_move_history.o"),
        ],
        text=True,
    )
    for target in (
        "SaveBlock2_get",
        "Party_GetCount",
        "Party_GetMonByIndex",
        "MonDeleteMoveSlot_Original",
        "IsMoveUnimplemented",
        "SetBoxMonData",
        "GetBoxMonData",
        "GetMoveMaxPP",
    ):
        require(
            re.search(rf"R_ARM_ABS32\s+{target}\b", history_reloc) is not None,
            f"overlay 153 lacks interworking-safe relocation to {target}",
        )
        require(
            re.search(rf"R_ARM_THM_CALL\s+{target}\b", history_reloc) is None,
            f"overlay 153 gained unsafe Thumb call relocation to {target}",
        )

    for object_path, expected_calls in (
        (history_object, ("PokemonMoveHistory_OverlayMemcpy",)),
        (
            relearn_object,
            (
                "PokemonMoveHistory_OverlayMemcpy",
                "PokemonMoveHistory_OverlayMemset",
            ),
        ),
    ):
        reloc = subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", str(object_path)],
            text=True,
        )
        for target in expected_calls:
            require(
                re.search(rf"R_ARM_THM_CALL\s+{target}\b", reloc) is not None,
                f"{object_path.name} does not call local bridge {target}",
            )

    rom_bytes = rom_path.read_bytes()
    arm9_base, packaged_arm9, packaged_overlays = (
        packaged_components_from_bytes(rom_bytes)
    )
    packaged_metadata_mutation_fixtures(rom_bytes)
    require(arm9_base == 0x02000000, "packaged ARM9 RAM base differs")
    ov12_component = packaged_overlays[12]
    ov65_component = packaged_overlays[65]
    ov68_component = packaged_overlays[68]
    ov70_component = packaged_overlays[70]
    ov112_component = packaged_overlays[112]
    ov129_component = packaged_overlays[129]
    ov131_component = packaged_overlays[131]
    ov153_component = packaged_overlays[153]
    ov154_component = packaged_overlays[154]
    ov155_component = packaged_overlays[155]
    ov12_base, packaged_ov12 = (
        ov12_component.ram_address,
        ov12_component.data,
    )
    ov65_base, packaged_ov65 = (
        ov65_component.ram_address,
        ov65_component.data,
    )
    ov68_base, packaged_ov68 = (
        ov68_component.ram_address,
        ov68_component.data,
    )
    ov70_base, packaged_ov70 = (
        ov70_component.ram_address,
        ov70_component.data,
    )
    ov112_base, packaged_ov112 = (
        ov112_component.ram_address,
        ov112_component.data,
    )
    ov129_base, packaged_ov129 = (
        ov129_component.ram_address,
        ov129_component.data,
    )
    ov131_base, packaged_ov131 = (
        ov131_component.ram_address,
        ov131_component.data,
    )
    ov153_base, packaged_ov153 = (
        ov153_component.ram_address,
        ov153_component.data,
    )
    ov154_base, packaged_ov154 = (
        ov154_component.ram_address,
        ov154_component.data,
    )
    ov155_base, packaged_ov155 = (
        ov155_component.ram_address,
        ov155_component.data,
    )
    require(ov12_base == 0x022378C0, "packaged overlay 12 base differs")
    require(
        ov65_base == 0x0221BE20
        and len(packaged_ov65) == 0x4380
        and ov65_component.ram_size == len(packaged_ov65)
        and ov65_component.bss_size == 0
        and ov65_component.static_init_start == 0x02220194
        and ov65_component.static_init_end == 0x02220198
        and ov65_component.file_id == 65
        and ov65_component.flags == 0,
        "packaged wireless-trade overlay 65 metadata differs",
    )
    require(ov68_base == 0x021E5900, "packaged overlay 68 base differs")
    require(
        ov70_base == 0x022378C0
        and len(packaged_ov70) == 0xEF40
        and ov70_component.ram_size == len(packaged_ov70)
        and ov70_component.bss_size == 0x160
        and ov70_component.static_init_start == 0x02246090
        and ov70_component.static_init_end == 0x02246094
        and ov70_component.file_id == 70
        and ov70_component.flags == 0,
        "packaged GTS overlay 70 metadata differs",
    )
    require(
        ov112_base == 0x021E5900
        and len(packaged_ov112) == 0x1A0E0
        and ov112_component.ram_size == len(packaged_ov112)
        and ov112_component.bss_size == 0x2C0
        and ov112_component.static_init_start == 0x021FF4E8
        and ov112_component.static_init_end == 0x021FF4EC
        and ov112_component.file_id == 112
        and ov112_component.flags == 0,
        "packaged Pokewalker overlay 112 metadata differs",
    )
    require(
        ov131_base == 0x023C8000
        and len(packaged_ov131) == 0x4FD2
        and ov131_component.ram_size == len(packaged_ov131)
        and ov131_component.bss_size == 0
        and ov131_component.static_init_start == 0
        and ov131_component.static_init_end == 0
        and ov131_component.file_id == 131
        and ov131_component.flags == 0
        and ov131_component.fat_start == 0x003F3400
        and ov131_component.fat_end == 0x003F83D2,
        "packaged scripted-daycare field overlay 131 metadata differs",
    )
    require(ov153_base == OVERLAY_BASE, "packaged overlay 153 base differs")
    require(ov154_base == 0x023C0400, "packaged overlay 154 base differs")
    require(
        ov155_base == OVERLAY155_BASE,
        "packaged overlay 155 base differs",
    )
    base_arm9 = arm9_path.read_bytes()
    require(
        base_arm9.startswith(packaged_arm9)
        and len(base_arm9) - len(packaged_arm9) <= 12,
        "packaged ARM9 bytes differ from the current patched ARM9",
    )
    require(
        packaged_ov12 == ov12_path.read_bytes(),
        "packaged overlay 12 differs from the current patched artifact",
    )
    require(
        packaged_ov65
        == (REPO / "base/overlay/overlay_0065.bin").read_bytes(),
        "packaged wireless-trade overlay differs from patched artifact",
    )
    require(
        packaged_ov68 == ov68_path.read_bytes(),
        "packaged overlay 68 differs from the current patched artifact",
    )
    require(
        packaged_ov70
        == (REPO / "base/overlay/overlay_0070.bin").read_bytes(),
        "packaged GTS overlay differs from patched artifact",
    )
    require(
        packaged_ov112 == ov112_path.read_bytes(),
        "packaged Pokewalker overlay differs from patched artifact",
    )
    require(
        packaged_ov65[
            0x0221F6C4 - ov65_base:0x0221F6D4 - ov65_base
        ]
        == bytes.fromhex(
            "38 1c 31 1c 22 1c 9d f1 a1 fe c0 46 c0 46 c0 46"
        )
        and thumb_bl_target(packaged_ov65, ov65_base, 0x0221F6CA)
        == OVERLAY155_BASE + 0x10
        and thumb_bl_target(packaged_ov70, ov70_base, 0x02240B72)
        == OVERLAY155_BASE + 0x68
        and thumb_bl_target(packaged_ov70, ov70_base, 0x02240C76)
        == OVERLAY155_BASE + 0x68
        and thumb_bl_target(packaged_ov70, ov70_base, 0x02240A0E)
        == OVERLAY155_BASE + 0x70
        and thumb_bl_target(packaged_ov70, ov70_base, 0x02240A44)
        == OVERLAY155_BASE + 0x78,
        "wireless/GTS packaged commit hooks differ",
    )
    require(
        thumb_bl_target(packaged_ov129, ov129_base, 0x023D9ABC)
        == OVERLAY155_BASE + 0xA0
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021EE65A)
        == OVERLAY155_BASE + 0x20
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021ED41A)
        == OVERLAY155_BASE + 0x80
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021EDBEE)
        == OVERLAY155_BASE + 0x88
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021EC0AA)
        == OVERLAY155_BASE + 0x90
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021EE86A)
        == OVERLAY155_BASE + 0x28
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021EEB8C)
        == OVERLAY155_BASE + 0x28
        and thumb_bl_target(packaged_ov112, ov112_base, 0x021EEC7E)
        == OVERLAY155_BASE + 0x28,
        "Pokewalker packaged transaction/poll-boundary hooks differ",
    )
    require(
        bytes_at(packaged_ov70, ov70_base, 0x022418A4, 0x68)
        == bytes.fromhex(
            "38 b5 82 b0 05 1c 69 6a ff f7 dc ff 4d 22 92 00 "
            "04 1c a8 58 12 28 0b d1 28 68 11 1d 80 68 69 58 "
            "32 f6 be fe 01 1c 20 1c 2f f6 de ff 02 b0 38 bd "
            "00 20 01 90 00 90 28 68 a9 58 12 1d c0 68 aa 58 "
            "32 f6 14 fa 28 68 01 a9 c0 68 00 aa 32 f6 54 fa "
            "20 1c 2f f6 5b fa 02 1c 28 68 01 99 c0 68 32 f6 "
            "7b f9 02 b0 38 bd 00 00"
        ),
        "retail GTS evolution copy-back/relocation body differs",
    )
    require(
        packaged_ov129 == ov129_path.read_bytes(),
        "packaged overlay 129 differs from the current patched artifact",
    )
    with tempfile.TemporaryDirectory(
        prefix="move-history-field-binary-"
    ) as field_binary_directory:
        reproduced_field_binary = (
            Path(field_binary_directory) / "output_field.bin"
        )
        subprocess.run(
            [
                "arm-none-eabi-objcopy",
                "-O",
                "binary",
                str(field_linked),
                str(reproduced_field_binary),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        linked_field_bytes = reproduced_field_binary.read_bytes()
    require(
        packaged_ov131
        == ov131_path.read_bytes()
        == field_binary.read_bytes()
        == linked_field_bytes,
        "packaged scripted-daycare overlay 131 differs from linked field output",
    )
    require(
        packaged_ov153 == ov153_path.read_bytes() == overlay,
        "packaged overlay 153 differs from the current linked output",
    )
    require(
        packaged_ov154
        == ov154_path.read_bytes()
        == summary_overlay.read_bytes()
        == elf_bytes_at(summary_linked, ov154_base, len(packaged_ov154)),
        "packaged overlay 154 differs from the current linked output",
    )
    require(
        packaged_ov155
        == ov155_path.read_bytes()
        == task6_overlay.read_bytes()
        == elf_bytes_at(task6_linked, ov155_base, len(packaged_ov155)),
        "packaged overlay 155 differs from the current linked output",
    )
    require(
        0 < len(packaged_ov155) <= OVERLAY155_LIMIT,
        "packaged overlay 155 exceeds its fixed reservation",
    )
    require(
        ov155_base + len(packaged_ov155)
        <= OVERLAY155_DIAGNOSTIC_SCRATCH
        and OVERLAY155_DIAGNOSTIC_SCRATCH
        + OVERLAY155_DIAGNOSTIC_SCRATCH_SIZE
        <= ov155_base + OVERLAY155_LIMIT,
        "packaged overlay 155 overlaps the sealed diagnostic scratch",
    )
    task6_symbols = symbol_table(task6_linked)
    for name, offset in (
        ("MoveHistoryTask6Entry_IsCanonical", 0x00),
        ("MoveHistoryTask6Entry_DaycareDepositCommit", 0x08),
        ("MoveHistoryTask6Entry_TradeReplacePartySlot", 0x10),
        ("MoveHistoryTask6Entry_HatchClearEgg", 0x18),
        ("MoveHistoryTask6Entry_PCStorageGetAndSeed", 0x20),
        ("MoveHistoryTask6Entry_PCStoragePlaceAndSeed", 0x28),
        ("MoveHistoryTask6Entry_ReplacePartyMove", 0x30),
        ("MoveHistoryTask6Entry_PlayerPartyAddCommit", 0x38),
        ("MoveHistoryTask6Entry_DaycareShiftAndAppend", 0x40),
        ("MoveHistoryTask6Entry_CorrectBattleFormMoves", 0x48),
        ("MoveHistoryTask6Entry_MarkHistoryMove", 0x50),
        ("MoveHistoryTask6Entry_AppendCandidate", 0x58),
        ("MoveHistoryTask6Entry_ScriptTeachMove", 0x64),
        ("MoveHistoryTask6Entry_GTSPlaceAndSeed", 0x68),
        ("MoveHistoryTask6Entry_GTSDeleteBoxAndRecord", 0x70),
        ("MoveHistoryTask6Entry_GTSRemovePartyAndRecord", 0x78),
        ("MoveHistoryTask6Entry_PokewalkerRadioSuccess", 0x80),
        ("MoveHistoryTask6Entry_PokewalkerRadioSuccessSecond", 0x88),
        ("MoveHistoryTask6Entry_PokewalkerRecoverAndDiscard", 0x90),
        ("MoveHistoryTask6Entry_PokewalkerDiagnosticReturn", 0x98),
        ("MoveHistoryTask6Entry_FieldReadyDiagnosticPoll", 0xA0),
        ("gPokemonMoveHistoryTask6DiagnosticMailbox", 0xA8),
    ):
        require(
            task6_symbols.get(name) == ov155_base + offset,
            f"packaged overlay 155 fixed entry differs: {name}",
        )
    for offset, implementation in (
        (0x20, "PokemonMoveHistoryTask6_PCStorageGetAndStageImpl"),
        (0x80, "PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl"),
        (0x88, "PokemonMoveHistoryTask6_PokewalkerRadioSuccessImpl"),
        (0x90, "PokemonMoveHistoryTask6_PokewalkerRecoverAndDiscardImpl"),
        (0xA0, "PokemonMoveHistoryTask6_FieldReadyDiagnosticPollImpl"),
    ):
        require(
            packaged_ov155[offset:offset + 4]
            == bytes.fromhex("00 4b 18 47")
            and struct.unpack_from("<I", packaged_ov155, offset + 4)[0]
            == task6_symbols.get(implementation, 0) + 1,
            f"packaged overlay 155 long entry target differs: {implementation}",
        )
    require(
        packaged_ov155[0x98:0xA0]
        == bytes.fromhex("fe e7 00 00 00 00 00 00"),
        "packaged overlay 155 diagnostic return trap differs",
    )
    require(
        packaged_ov155[0xA8:0xD8] == bytes(0x30),
        "packaged overlay 155 diagnostic mailbox is not zero-initialized",
    )
    task6_calls = packaged_thumb_calls(
        packaged_ov155,
        ov155_base,
        ov155_base,
        len(packaged_ov155),
    )
    require(
        len(task6_calls) == 75
        and sum(kind == "bl" for _address, kind, _target in task6_calls)
        == 68
        and sum(
            kind == "blx_reg"
            for _address, kind, _target in task6_calls
        ) == 7
        and call_inventory_sha256(task6_calls)
        == OVERLAY155_CALL_INVENTORY_SHA256,
        "complete overlay-155 call-site inventory differs",
    )
    require(
        not any("_from_thumb" in name for name in task6_symbols),
        "overlay 155 unexpectedly linked an ARM interworking veneer",
    )
    summary_symbols = symbol_table(summary_linked)
    require(
        struct.unpack_from("<II", packaged_ov154, 0)
        == (0x344D5253, 4)
        and summary_symbols.get("SummaryMoveRelearn_Entry")
        == ov154_base + 8,
        "packaged overlay 154 header or fixed entry differs",
    )
    linked_overlay = elf_bytes_at(
        linked,
        ov153_base,
        len(packaged_ov153),
    )
    packaged_call_inventory = packaged_thumb_calls(
        packaged_ov153,
        ov153_base,
        ov153_base,
        len(packaged_ov153),
    )
    linked_call_inventory = packaged_thumb_calls(
        linked_overlay,
        ov153_base,
        ov153_base,
        len(linked_overlay),
    )
    require(
        linked_overlay == packaged_ov153
        and packaged_call_inventory == linked_call_inventory
        and len(packaged_call_inventory) == 111
        and sum(
            kind == "bl" for _address, kind, _target
            in packaged_call_inventory
        ) == 109
        and sum(
            kind == "blx" for _address, kind, _target
            in packaged_call_inventory
        ) == 2
        and not [
            call for call in packaged_call_inventory
            if call[1] == "blx_reg"
        ]
        and call_inventory_sha256(packaged_call_inventory)
        == OVERLAY153_CALL_INVENTORY_SHA256,
        "complete overlay-153 packaged/linked call-site inventory differs",
    )
    added_indirect_call = bytearray(packaged_ov153)
    struct.pack_into("<H", added_indirect_call, 0x7A, 0x4798)
    require(
        packaged_thumb_calls(
            bytes(added_indirect_call),
            ov153_base,
            ov153_base,
            len(added_indirect_call),
        )
        != packaged_call_inventory,
        "inserted overlay-wide BLX-register call passes call authentication",
    )
    removed_direct_call = bytearray(packaged_ov153)
    first_call_address = packaged_call_inventory[0][0]
    removed_direct_call[
        first_call_address - ov153_base:
        first_call_address - ov153_base + 4
    ] = b"\xc0\x46\xc0\x46"
    require(
        packaged_thumb_calls(
            bytes(removed_direct_call),
            ov153_base,
            ov153_base,
            len(removed_direct_call),
        )
        != packaged_call_inventory,
        "removed overlay-wide direct call passes call authentication",
    )

    expected = OVERLAY_BASE + 0x80
    require(
        bytes_at(packaged_arm9, arm9_base, 0x020769E2, 14)
        == bytes.fromhex("21 1c 22 1c 6c 31 6e 32 09 88 12 78 a0 6a")
        and thumb_bl_target(packaged_arm9, arm9_base, 0x020769F0)
        == expected
        and bytes_at(packaged_arm9, arm9_base, 0x020769F4, 2)
        == b"\x20\x1c",
        "evolution argument window, replacement BL, or continuation differs",
    )
    require(
        bytes_at(packaged_ov12, ov12_base, 0x02246336, 14)
        == bytes.fromhex("21 6c 62 6c 09 04 12 06 30 1c 09 0c 12 0e")
        and thumb_bl_target(packaged_ov12, ov12_base, 0x02246344)
        == expected
        and bytes_at(packaged_ov12, ov12_base, 0x02246348, 2)
        == b"\x61\x68",
        "battle argument window, replacement BL, or continuation differs",
    )
    require(
        bytes_at(packaged_ov68, ov68_base, 0x021E6158, 8)
        == b"\x20\x68\xc2\x7e\x00\x68\x00\x99"
        and thumb_bl_target(packaged_ov68, ov68_base, 0x021E6160)
        == expected
        and bytes_at(packaged_ov68, ov68_base, 0x021E6164, 4)
        == b"\xc0\x46\x00\x20",
        "Move Reminder/tutor full patch or 0x021E6166 continuation differs",
    )
    require(
        thumb_bl_target(packaged_arm9, arm9_base, 0x0204DCCC)
        == OVERLAY_BASE + 0x88,
        "Move Deleter BL target differs",
    )
    require(
        bytes_at(packaged_arm9, arm9_base, 0x0204DCBE, 12)
        == bytes.fromhex("e8 68 26 f0 20 fe 31 1c 26 f0 bd fc")
        and bytes_at(packaged_arm9, arm9_base, 0x0204DCCA, 6)
        == b"\x21\x1c\x70\xf3\xdc\xfb"
        and bytes_at(packaged_arm9, arm9_base, 0x0204DCD0, 4)
        == b"\x00\x20\x70\xbd",
        "Move Deleter argument window, replacement BL, or continuation differs",
    )
    require(
        thumb_bl_target(packaged_arm9, arm9_base, 0x020542D6)
        == 0x02074644,
        "PartyMonSetMoveInSlot no longer uses Party_GetMonByIndex",
    )
    require(
        bytes_at(packaged_arm9, arm9_base, 0x020542D0, 6)
        == b"\x38\xb5\x15\x1c\x1c\x1c"
        and bytes_at(packaged_arm9, arm9_base, 0x020542DA, 6)
        == b"\x2a\x06\x21\x1c\x12\x0e"
        and thumb_bl_target(packaged_arm9, arm9_base, 0x020542E0)
        == expected
        and bytes_at(packaged_arm9, arm9_base, 0x020542E4, 2)
        == b"\x38\xbd",
        "PartyMonSetMoveInSlot final mutation does not target ReplaceMove",
    )

    for entry_offset, impl_name in (
        (0x80, "PokemonMoveHistory_ReplaceMoveImpl"),
        (0x88, "PokemonMoveHistory_DeleteMoveSlotImpl"),
    ):
        require(
            bytes_at(packaged_ov153, ov153_base, ov153_base + entry_offset, 4)
            == b"\x00\x4b\x18\x47",
            f"fixed entry 0x{entry_offset:X} instructions differ",
        )
        entry_target = struct.unpack_from(
            "<I",
            packaged_ov153,
            entry_offset + 4,
        )[0]
        require(
            entry_target == symbols[impl_name] + 1,
            f"fixed entry 0x{entry_offset:X} target differs",
        )

    core_symbols = symbol_table(core_linked)
    require(
        "IsMoveUnimplemented" in core_symbols,
        "resident core does not export IsMoveUnimplemented",
    )
    implemented_check_target = core_symbols["IsMoveUnimplemented"] + 1
    require(
        ov129_base <= implemented_check_target < ov129_base + len(packaged_ov129),
        "IsMoveUnimplemented is not resident in overlay 129",
    )
    implemented_address = implemented_check_target - 1
    require(
        implemented_address == 0x023D94C4
        and overlay129_predicate_matches(packaged_ov129, ov129_base),
        "overlay-129 IsMoveUnimplemented body/controlling data flow differs",
    )
    mutated_predicate = bytearray(packaged_ov129)
    mutated_predicate[implemented_address - ov129_base + 2] = 0
    require(
        not overlay129_predicate_matches(bytes(mutated_predicate), ov129_base),
        "always-false IsMoveUnimplemented mutation passes packaged checks",
    )
    resolved_targets = {
        "SaveBlock2_get": 0x020272B1,
        "GetBoxMonData": 0x0206E641,
        "SetBoxMonData": 0x0206ED71,
        "MonDeleteMoveSlot_Original": 0x020716C1,
        "GetMoveMaxPP": 0x0207332D,
        "IsMoveUnimplemented": implemented_check_target,
    }
    for name, address in resolved_targets.items():
        require(
            symbols.get(name) == address,
            f"final symbol {name} resolves to {symbols.get(name)!r}, "
            f"expected 0x{address:08X}",
        )

    core_function_sizes = symbol_sizes(core_linked)
    packaged_function_specs = (
        (
            "Save_InitDynamicRegion",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DD6C8,
            0x38,
            "1f1d2eece6cdadcf00a99da5e46c656d488207975dffa6390c3ae4c9d193f3d0",
            [
                (0x023DD6E0, "bl", 0x023DE0D6),
                (0x023DD6E8, "bl", 0x023DE0D6),
            ],
        ),
        (
            "Save_LoadDynamicRegion",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DD8B4,
            0xCC,
            "6cd2ca42c366bdacf938c67058e17559d60ffaedbb3b3c8c6f00b18d12eaffe6",
            [
                (0x023DD8C8, "bl", 0x023DE0D8),
                (0x023DD8D6, "bl", 0x023DD7F0),
                (0x023DD8E6, "bl", 0x023DE0D8),
                (0x023DD8F8, "bl", 0x023DD7F0),
                (0x023DD914, "bl", 0x023DE0DA),
                (0x023DD92C, "bl", 0x023DE0DA),
                (0x023DD938, "bl", 0x023DE0D6),
                (0x023DD940, "bl", 0x023DE0D6),
                (0x023DD948, "bl", 0x023DE0D6),
            ],
        ),
        (
            "Save_WriteManInit",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DDA20,
            0x58,
            "e48cab0c691f760112a4cb6de3aa855293345566f4e6ef4dd0308a4e77eba7bc",
            [
                (0x023DDA28, "bl", 0x023DE0D6),
                (0x023DDA30, "bl", 0x023DE0D6),
                (0x023DDA54, "bl", 0x023DE0D6),
                (0x023DDA5C, "bl", 0x023DE0D6),
            ],
        ),
        (
            "Save_WriteManFinish",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DDA8C,
            0x94,
            "d0ab077f4a074d4bdb9dd0d4a7cae88d312f3632cf4aa28881a6312e8de63ef0",
            [
                (0x023DDAB2, "bl", 0x023DE0D6),
                (0x023DDABA, "bl", 0x023DE0D6),
                (0x023DDAC2, "bl", 0x023DE0D6),
                (0x023DDAD6, "bl", 0x023DE0D6),
            ],
        ),
        (
            "Save_PrepareForAsyncWrite",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DDA78,
            0x14,
            "1a870f9245779d7c51a37ec7e2c59ed6f83f3d3fbc70bd84eab5c1d028866f88",
            [(0x023DDA80, "bl", 0x023DDA20)],
        ),
        (
            "Save_WriteFileAsync",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DE044,
            0x40,
            "84d8babc3bbbec9575f468493c19f98c08af8e0bc39a68594bc30cb93fdbfce0",
            [
                (0x023DE056, "bl", 0x023DDF18),
                (0x023DE066, "bl", 0x023DDA8C),
                (0x023DE070, "bl", 0x023DE0D6),
            ],
        ),
        (
            "CancelAsyncSaveWithMoveHistory",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DDB20,
            0x6C,
            "760a810448748647fed89c9ba587fdda6e4d439482dc478df2cc57e8336aa48e",
            [
                (0x023DDB34, "bl", 0x023DE0D6),
                (0x023DDB3E, "bl", 0x023DE0D6),
                (0x023DDB4C, "bl", 0x023DE0D6),
                (0x023DDB54, "bl", 0x023DE0D6),
                (0x023DDB60, "bl", 0x023DE0D6),
                (0x023DDB68, "bl", 0x023DE0D6),
            ],
        ),
        (
            "Save_Cancel",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DDB8C,
            0x10,
            "b58e7ced034221bcc71a863e62fe4c97a82f88b9d35e8d6b89e162462fa017b5",
            [(0x023DDB92, "bl", 0x023DDB20)],
        ),
        (
            "SaveData_New",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DDC18,
            0x118,
            "b077470b6728b6e5a54f89ae10afe4e00a26df1f3884071ab64c8552588d9296",
            [
                (0x023DDC20, "bl", 0x023DE0D6),
                (0x023DDC2E, "bl", 0x023DE0D6),
                (0x023DDC3A, "bl", 0x023DE0D6),
                (0x023DDC40, "bl", 0x023DE0D6),
                (0x023DDC5E, "bl", 0x023DE0D6),
                (0x023DDC68, "bl", 0x023DDB9C),
                (0x023DDC70, "bl", 0x023DE0D6),
                (0x023DDC90, "bl", 0x023DD6C8),
                (0x023DDC98, "bl", 0x023DD8B4),
                (0x023DDCB2, "bl", 0x023DE0D6),
                (0x023DDCD8, "bl", 0x023DE0D6),
            ],
        ),
        (
            "PartyMenu_LearnMoveToSlot",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DA158,
            0x6C,
            "fff8695ccb309e47286f0f4aeb8f67d1b1327c732a4b3896b3f91647e41f3357",
            [
                (0x023DA168, "bl", 0x023DA872),
                (0x023DA184, "bl", 0x023DA878),
                (0x023DA18C, "bl", 0x023DA872),
                (0x023DA198, "bl", 0x023DA872),
                (0x023DA1A2, "bl", 0x023DA872),
            ],
        ),
        (
            "MonTryLearnMoveOnLevelUp",
            core_linked,
            packaged_ov129,
            ov129_base,
            0x023DC708,
            0x158,
            "457614c6a8b8e13d158ca0dab84536a662443e233db5fd29570bf2df861d481c",
            [
                (0x023DC71C, "bl", 0x023DCB20),
                (0x023DC72A, "bl", 0x023DCB24),
                (0x023DC736, "bl", 0x023DCB24),
                (0x023DC742, "bl", 0x023DCB24),
                (0x023DC754, "bl", 0x023DCB20),
                (0x023DC7A2, "bl", 0x023DCB20),
                (0x023DC7B0, "bl", 0x023DCB20),
                (0x023DC7C8, "bl", 0x023DCB20),
                (0x023DC80A, "bl", 0x023DCB20),
                (0x023DC81E, "bl", 0x023DCB20),
                (0x023DC82E, "bl", 0x023DCB20),
            ],
        ),
        (
            "PokemonMoveHistory_RecordMoveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEE62,
            0x40,
            "01f2dac0aa30ed1ffe055eeb6226cde16c87ec8b7af61f6fdbe43854c316b835",
            [
                (0x023BEE6E, "bl", 0x023BE998),
                (0x023BEE80, "bl", 0x023BED64),
                (0x023BEE8C, "bl", 0x023BEC14),
                (0x023BEE9A, "bl", 0x023BEB54),
            ],
        ),
        (
            "PokemonMoveHistory_ReplaceMoveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEEAE,
            0xE2,
            "ef4ace59124ef75f5aef506f273369063a5f57e6276b767fa00866ada2f064ad",
            [
                (0x023BEECE, "bl", 0x023BE998),
                (0x023BEEE4, "bl", 0x023BF314),
                (0x023BEEF6, "bl", 0x023BED64),
                (0x023BEF00, "bl", 0x023BF314),
                (0x023BEF08, "bl", 0x023BEC14),
                (0x023BEF18, "bl", 0x023BF314),
                (0x023BEF2E, "bl", 0x023BF314),
                (0x023BEF38, "bl", 0x023BF314),
                (0x023BEF4C, "bl", 0x023BF314),
                (0x023BEF58, "bl", 0x023BF314),
                (0x023BEF7A, "bl", 0x023BEB54),
            ],
        ),
        (
            "PokemonMoveHistory_DeleteMoveSlotImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEF90,
            0x30,
            "5eb2b7cd1c9fb308667c36cb13fea4f799c7b13cd108c2420fb95f2045c56755",
            [
                (0x023BEFA0, "bl", 0x023BF314),
                (0x023BEFA6, "bl", 0x023BEE40),
                (0x023BEFB0, "bl", 0x023BF314),
            ],
        ),
        (
            "PokemonMoveHistory_InitImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BECEC,
            0x44,
            "2d00abfe7ef6b1ed89cb3a7c81ae5e5ade6173d32e8bd1ca09b3419a99754cd4",
            [
                (0x023BED08, "bl", 0x023BE9C0),
                (0x023BED12, "bl", 0x023BE910),
            ],
        ),
        (
            "PokemonMoveHistory_ResetImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BED30,
            0x24,
            "983d59ba89ec948d7262494b02b521a74e80c7d8bfc352c09ddf20151beb6e17",
            [
                (0x023BED3E, "bl", 0x023BE910),
                (0x023BED44, "bl", 0x023BE9C0),
            ],
        ),
        (
            "PokemonMoveHistory_LoadForCounter",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BE9F8,
            0x15C,
            "3f0b338efb81f270c8c832e7d0a6c73efcbf22b77d116ad7d4b98ca9d8af7276",
            [
                (0x023BEA16, "bl", 0x023BF31A),
                (0x023BEA20, "bl", 0x023BE820),
                (0x023BEA4E, "bl", 0x023BF31A),
                (0x023BEA58, "bl", 0x023BE820),
                (0x023BEA7C, "bl", 0x023BE910),
                (0x023BEA82, "bl", 0x023BE9C0),
                (0x023BEABE, "bl", 0x023BF314),
                (0x023BEAC8, "bl", 0x023BE820),
            ],
        ),
        (
            "PokemonMoveHistory_LoadImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BED54,
            0x10,
            "33991e37e6727cdb4ac714a5a21db5f8724ce8a6145aac8f6fc6df513b0881a8",
            [(0x023BED5A, "bl", 0x023BE9F8)],
        ),
        (
            "PokemonMoveHistory_CommitIfDirtyImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BEFCC,
            0x170,
            "7956b4e8e773c6999592049a21a76917339c45b8b127793cac51b3429bcbe65f",
            [
                (0x023BEFEE, "bl", 0x023BF314),
                (0x023BF008, "bl", 0x023BE910),
                (0x023BF04C, "bl", 0x023BF31A),
                (0x023BF06A, "bl", 0x023BE7B8),
                (0x023BF074, "bl", 0x023BE7B8),
                (0x023BF082, "bl", 0x023BF31A),
                (0x023BF096, "bl", 0x023BF314),
                (0x023BF0AE, "bl", 0x023BF314),
                (0x023BF0BE, "bl", 0x023BF314),
            ],
        ),
        (
            "PokemonMoveHistory_SeedParty",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF13C,
            0x48,
            "ef5bbb55838eff324a19af108d92b1ccf2a97a35ec60794303b8c4c6ef347623",
            [
                (0x023BF142, "bl", 0x023BF314),
                (0x023BF14C, "bl", 0x023BF314),
                (0x023BF168, "bl", 0x023BF314),
                (0x023BF170, "bl", 0x023BEE40),
            ],
        ),
        (
            "PokemonMoveHistory_LoadAndSeedPartyImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF184,
            0x08,
            "0bd2342f190999b88042fa9312a4d2b56090881c1a3e9b29d7626a7523fe654e",
            [(0x023BF186, "bl", 0x023BED54)],
        ),
        (
            "PokemonMoveHistory_PrepareSaveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF18C,
            0x2C,
            "7589290dd45d818465cb92b2cbf956e2323aa837fac7faba1c550db4d9d4e1d4",
            [
                (0x023BF19E, "bl", 0x023BE9F8),
                (0x023BF1A4, "bl", 0x023BF13C),
                (0x023BF1AA, "bl", 0x023BEFCC),
            ],
        ),
        (
            "PokemonMoveHistory_FinishSaveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF1B8,
            0x60,
            "7f037a772072138bfc251db15417674fdd2e239df1292eb17f012a982738b967",
            [],
        ),
        (
            "PokemonMoveHistory_CancelSaveImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF218,
            0x30,
            "485ddd855b50dbf52cd5b8a9de6d92ca1a28c20ced429c48e8575a5806f5b557",
            [],
        ),
        (
            "PokemonMoveHistory_WriteSaveNowImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF248,
            0x50,
            "cac9be4a9ac82731fe28e6abe16a97e51fa8de30bac5a70fae99dd5d3a4c636f",
            [
                (0x023BF254, "bl", 0x023BF314),
                (0x023BF266, "bl", 0x023BF314),
                (0x023BF278, "bl", 0x023BF314),
                (0x023BF282, "bl", 0x023BF318),
            ],
        ),
        (
            "SaveGameNormalImpl",
            linked,
            packaged_ov153,
            ov153_base,
            0x023BF298,
            0x7C,
            "9e428237d862e99d378f1d4427e22c15cddc60f40b509033398a5515634a6e4a",
            [
                (0x023BF2B0, "bl", 0x023BF314),
                (0x023BF2C0, "bl", 0x023BF316),
                (0x023BF2CE, "bl", 0x023BF316),
                (0x023BF2D8, "bl", 0x023BF316),
                (0x023BF2E2, "bl", 0x023BF316),
                (0x023BF2EA, "bl", 0x023BF314),
                (0x023BF2F0, "bl", 0x023BF248),
            ],
        ),
    )
    for (
        name,
        elf_path,
        image,
        image_base,
        address,
        size,
        expected_sha256,
        expected_calls,
    ) in packaged_function_specs:
        size_table = (
            core_function_sizes if elf_path == core_linked
            else linked_symbol_sizes
        )
        require(
            symbol_table(elf_path).get(name) == address
            and size_table.get(name) == size,
            f"{name} linked address/size differs",
        )
        packaged_body = bytes_at(image, image_base, address, size)
        require(
            packaged_body == elf_bytes_at(elf_path, address, size)
            and hashlib.sha256(packaged_body).hexdigest() == expected_sha256,
            f"{name} complete packaged body differs from authenticated ELF",
        )
        require(
            packaged_thumb_calls(image, image_base, address, size)
            == expected_calls,
            f"{name} packaged BL/BLX call allowlist differs",
        )

    for name in (
        "PokemonMoveHistory_QueryRecord",
        "PokemonMoveHistory_QueryImpl",
        "PokemonMoveHistory_QueryReadOnlyImpl",
        "PokemonMoveHistory_CaptureSnapshotImpl",
        "PokemonMoveHistory_ObserveSnapshot",
        "PokemonMoveHistory_FindRecord",
        "PokemonMoveHistory_OverlayMemcpy",
    ):
        require(name in symbols, f"linked query symbol is missing: {name}")
    query_record_address = symbols["PokemonMoveHistory_QueryRecord"]
    query_observing_address = symbols["PokemonMoveHistory_QueryImpl"]
    query_read_only_address = symbols[
        "PokemonMoveHistory_QueryReadOnlyImpl"
    ]
    require(
        linked_symbol_sizes.get("PokemonMoveHistory_QueryRecord") == 0x68
        and linked_symbol_sizes.get("PokemonMoveHistory_QueryImpl") == 0x0C
        and linked_symbol_sizes.get("PokemonMoveHistory_QueryReadOnlyImpl")
        == 0x0C,
        "observing/read-only query body sizes differ",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            query_observing_address,
            6,
        )
        == bytes.fromhex("13 b5 01 24 00 94")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            query_read_only_address,
            6,
        )
        == bytes.fromhex("13 b5 00 24 00 94"),
        "query wrappers do not pass exact TRUE/FALSE observation arguments",
    )
    require(
        packaged_thumb_calls(
            packaged_ov153,
            ov153_base,
            query_observing_address,
            0x0C,
        )
        == [
            (
                query_observing_address + 6,
                "bl",
                query_record_address,
            )
        ]
        and packaged_thumb_calls(
            packaged_ov153,
            ov153_base,
            query_read_only_address,
            0x0C,
        )
        == [
            (
                query_read_only_address + 6,
                "bl",
                query_record_address,
            )
        ],
        "query wrappers do not call only the shared query body",
    )
    query_record_calls = packaged_thumb_calls(
        packaged_ov153,
        ov153_base,
        query_record_address,
        0x68,
    )
    require(
        query_record_calls
        == [
            (
                query_record_address + 0x0E,
                "bl",
                symbols["PokemonMoveHistory_CaptureSnapshotImpl"],
            ),
            (
                query_record_address + 0x26,
                "bl",
                symbols["PokemonMoveHistory_ObserveSnapshot"],
            ),
            (
                query_record_address + 0x46,
                "bl",
                symbols["PokemonMoveHistory_OverlayMemcpy"],
            ),
            (
                query_record_address + 0x5E,
                "bl",
                symbols["PokemonMoveHistory_FindRecord"],
            ),
        ],
        "shared query gained an unauthenticated call or mutation path",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            query_record_address + 0x1C,
            4,
        )
        == bytes.fromhex("0a 9b 00 2b")
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            query_record_address + 0x20,
            0,
        )
        == query_record_address + 0x4E,
        "FALSE observation argument does not bypass ObserveSnapshot",
    )

    for entry_offset, implementation in (
        (0x00, "PokemonMoveHistory_InitImpl"),
        (0x08, "PokemonMoveHistory_LoadImpl"),
        (0x10, "PokemonMoveHistory_ResetImpl"),
        (0x40, "PokemonMoveHistory_CommitIfDirtyImpl"),
        (0x48, "PokemonMoveHistory_LoadAndSeedPartyImpl"),
        (0x50, "PokemonMoveHistory_PrepareSaveImpl"),
        (0x58, "PokemonMoveHistory_FinishSaveImpl"),
        (0x60, "PokemonMoveHistory_CancelSaveImpl"),
        (0x68, "PokemonMoveHistory_WriteSaveNowImpl"),
        (0x70, "SaveGameNormalImpl"),
    ):
        require(
            bytes_at(
                packaged_ov153,
                ov153_base,
                ov153_base + entry_offset,
                4,
            ) == b"\x00\x4b\x18\x47"
            and struct.unpack_from(
                "<I",
                packaged_ov153,
                entry_offset + 4,
            )[0] == symbols[implementation] + 1,
            f"lifecycle entry 0x{entry_offset:X} target/body differs",
        )
    for literal_address, expected_target in (
        (0x023DD6FC, OVERLAY_BASE + 0x11),
        (0x023DD97C, OVERLAY_BASE + 0x49),
        (0x023DDA74, OVERLAY_BASE + 0x51),
        (0x023DDAFC, OVERLAY_BASE + 0x59),
        (0x023DDB84, OVERLAY_BASE + 0x61),
        (0x023DDD08, OVERLAY_BASE + 0x01),
    ):
        require(
            struct.unpack_from(
                "<I",
                packaged_ov129,
                literal_address - ov129_base,
            )[0] == expected_target,
            f"save lifecycle literal 0x{literal_address:08X} differs",
        )
    for hook_address, expected_bytes in (
        (0x020271B0, "00 48 00 47 19 dc 3d 02"),
        (0x020274A8, "00 49 08 47 c9 d6 3d 02"),
        (0x02027550, "00 4a 10 47 79 da 3d 02"),
        (0x02027564, "00 49 08 47 45 e0 3d 02"),
        (0x020275A4, "00 49 08 47 8d db 3d 02"),
        (0x02027AD4, "00 49 08 47 b5 d8 3d 02"),
        (0x02027BDC, "00 4b 18 47 21 da 3d 02"),
        (0x02027CEC, "00 4b 18 47 8d da 3d 02"),
    ):
        require(
            bytes_at(packaged_arm9, arm9_base, hook_address, 8)
            == bytes.fromhex(expected_bytes),
            f"save lifecycle hook 0x{hook_address:08X} differs",
        )
    for literal_address, expected_target in (
        (0x023BF178, 0x02074905),
        (0x023BF17C, 0x02074641),
        (0x023BF180, 0x02074645),
    ):
        require(
            struct.unpack_from(
                "<I",
                packaged_ov153,
                literal_address - ov153_base,
            )[0] == expected_target,
            f"SeedParty accessor literal 0x{literal_address:08X} differs",
        )

    party_body = bytes_at(packaged_ov129, ov129_base, 0x023DA158, 0x6C)
    require(
        overlay129_thunks_match(packaged_ov129, ov129_base),
        "overlay-129 interworking thunk bodies/registers differ",
    )
    mutated_thunk = bytearray(packaged_ov129)
    mutated_thunk[0x023DA872 - ov129_base] = 0x20
    require(
        not overlay129_thunks_match(bytes(mutated_thunk), ov129_base),
        "mutated overlay-129 thunk register passes exact authentication",
    )
    for target in (
        OVERLAY_BASE + 0x81,
        0x023D8987,
        0x020828ED,
        0x0206FE91,
        0x02097F0D,
    ):
        require(
            party_body.count(struct.pack("<I", target)) == 1,
            f"PartyMenu_LearnMoveToSlot target 0x{target:08X} differs",
        )
    level_body = bytes_at(packaged_ov129, ov129_base, 0x023DC708, 0x158)
    for target in (
        0x0201AA8D,
        0x0206E541,
        0x02071FC9,
        implemented_check_target,
        0x0201AB0D,
        0x0207137D,
        0x020272B1,
        OVERLAY_BASE + 0x29,
    ):
        require(
            level_body.count(struct.pack("<I", target)) == 1,
            f"MonTryLearnMoveOnLevelUp target 0x{target:08X} differs",
        )
    replace_start = symbols["PokemonMoveHistory_ReplaceMoveImpl"] - ov153_base
    delete_start = symbols["PokemonMoveHistory_DeleteMoveSlotImpl"] - ov153_base
    delete_size = linked_symbol_sizes.get(
        "PokemonMoveHistory_DeleteMoveSlotImpl",
        0,
    )
    delete_end = delete_start + delete_size
    replace_bytes = packaged_ov153[replace_start:delete_start]
    delete_bytes = packaged_ov153[delete_start:delete_end]
    replace_address = symbols["PokemonMoveHistory_ReplaceMoveImpl"]
    replace_size = linked_symbol_sizes.get(
        "PokemonMoveHistory_ReplaceMoveImpl",
        0,
    )
    require(
        replace_size == 0xE2 and len(replace_bytes) == replace_size,
        "ReplaceMove packaged body size/layout differs from authenticated build",
    )
    require(
        delete_size == 0x30 and len(delete_bytes) == delete_size,
        "DeleteMoveSlot packaged body size/layout differs from authenticated build",
    )
    false_address = replace_address + 0x12
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            false_address,
            8,
        )
        == bytes.fromhex("00 24 20 00 0d b0 f0 bd"),
        "ReplaceMove FALSE return block differs",
    )
    same_slot_start = replace_address + 0x28
    literal_address, literal_value = thumb_literal_load(
        packaged_ov153,
        ov153_base,
        replace_address + 0x2A,
        3,
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            same_slot_start,
            2,
        )
        == bytes.fromhex("3e 00")
        and replace_address <= literal_address < replace_address + replace_size
        and literal_value == resolved_targets["GetBoxMonData"]
        and bytes_at(
            packaged_ov153,
            ov153_base,
            replace_address + 0x2C,
            10,
        )
        == bytes.fromhex("36 36 00 22 31 00 20 00 04 93"),
        "ReplaceMove early same-slot read setup differs",
    )
    same_slot_call = replace_address + 0x36
    same_slot_trampoline = thumb_bl_target(
        packaged_ov153,
        ov153_base,
        same_slot_call,
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            same_slot_trampoline,
            2,
        )
        == bytes.fromhex("18 47")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            replace_address + 0x3A,
            8,
        )
        == bytes.fromhex("2b 88 00 04 00 0c 83 42"),
        "ReplaceMove early same-slot call/compare differs",
    )
    equal_branch = replace_address + 0x42
    capture_call = replace_address + 0x48
    require(
        thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            equal_branch,
            0,
        )
        == false_address
        and bytes_at(
            packaged_ov153,
            ov153_base,
            replace_address + 0x44,
            4,
        )
        == bytes.fromhex("20 00 07 a9")
        and thumb_bl_target(
            packaged_ov153,
            ov153_base,
            capture_call,
        )
        == symbols["PokemonMoveHistory_CaptureSnapshotImpl"],
        "ReplaceMove equality edge does not return FALSE before snapshot access",
    )
    save_literal_address, save_literal_value = thumb_literal_load(
        packaged_ov153,
        ov153_base,
        replace_address + 0x50,
        3,
    )
    require(
        replace_address <= save_literal_address < replace_address + replace_size
        and save_literal_value == resolved_targets["SaveBlock2_get"]
        and thumb_bl_target(
            packaged_ov153,
            ov153_base,
            replace_address + 0x52,
        )
        == same_slot_trampoline
        and replace_address + 0x52 > capture_call,
        "ReplaceMove SaveBlock2_get call is not authenticated after snapshot",
    )
    for name in (
        "SaveBlock2_get",
        "GetBoxMonData",
        "SetBoxMonData",
        "GetMoveMaxPP",
    ):
        require(
            struct.pack("<I", resolved_targets[name]) in replace_bytes,
            f"ReplaceMove packaged body does not resolve {name}",
        )
    for name in ("SaveBlock2_get", "MonDeleteMoveSlot_Original"):
        require(
            struct.pack("<I", resolved_targets[name]) in delete_bytes,
            f"DeleteMoveSlot packaged body does not resolve {name}",
        )
    recordable_address = symbols["PokemonMoveHistory_IsRecordableMove"]
    recordable_start = recordable_address - ov153_base
    recordable_size = linked_symbol_sizes.get(
        "PokemonMoveHistory_IsRecordableMove",
        0,
    )
    recordable_bytes = packaged_ov153[
        recordable_start:recordable_start + recordable_size
    ]
    require(
        recordable_size == 0x28
        and struct.pack("<I", implemented_check_target) in recordable_bytes,
        "recordable-move predicate does not resolve resident "
        "IsMoveUnimplemented",
    )
    range_literal_address, range_literal_value = thumb_literal_load(
        packaged_ov153,
        ov153_base,
        recordable_address + 0x02,
        1,
    )
    implemented_literal_address, implemented_literal_value = (
        thumb_literal_load(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x12,
            3,
        )
    )
    recordable_false = recordable_address + 0x1E
    recordable_call = recordable_address + 0x16
    recordable_trampoline = thumb_bl_target(
        packaged_ov153,
        ov153_base,
        recordable_call,
    )
    _canonical_moves, _custom_moves, num_moves = move_limits()
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_address,
            16,
        )
        == bytes.fromhex(
            "43 1e 07 49 1b 04 02 00 10 b5 00 20 1b 0c 8b 42"
        )
        and range_literal_address == recordable_address + 0x20
        and range_literal_value == num_moves - 2
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x10,
            8,
        )
        == recordable_false,
        "recordable-move MOVE_NONE/range CFG does not return FALSE before "
        "the implementation check",
    )
    require(
        implemented_literal_address == recordable_address + 0x24
        and implemented_literal_value == implemented_check_target
        and bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x14,
            2,
        )
        == bytes.fromhex("10 00")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_trampoline,
            2,
        )
        == bytes.fromhex("18 47")
        and bytes_at(
            packaged_ov153,
            ov153_base,
            recordable_address + 0x1A,
            6,
        )
        == bytes.fromhex("43 42 58 41 10 bd"),
        "IsMoveUnimplemented result does not control the final predicate "
        "return through the authenticated interworking call",
    )

    append_address = next(
        (
            address
            for name, address in symbols.items()
            if name == "PokemonMoveHistory_AppendMove"
            or name.startswith("PokemonMoveHistory_AppendMove.")
        ),
        None,
    )
    require(
        append_address is not None,
        "linked move-history append implementation is missing",
    )
    append_size = next(
        (
            size
            for name, size in linked_symbol_sizes.items()
            if name == "PokemonMoveHistory_AppendMove"
            or name.startswith("PokemonMoveHistory_AppendMove.")
        ),
        0,
    )
    require(
        append_size == 0xC0
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address,
            14,
        )
        == bytes.fromhex(
            "f0 b5 06 00 85 b0 18 00 14 00 1f 00 00 91"
        )
        and thumb_bl_target(
            packaged_ov153,
            ov153_base,
            append_address + 0x0E,
        )
        == recordable_address
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x12,
            2,
        )
        == bytes.fromhex("00 28")
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x14,
            0,
        )
        == append_address + 0x80,
        "AppendMove does not consume its sole predicate result before "
        "record access or mutation",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x16,
            6,
        )
        == bytes.fromhex("00 23 a1 7b 8b 42")
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x1C,
            3,
        )
        == append_address + 0x84
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x20,
            1,
        )
        == append_address + 0x54
        and thumb_conditional_branch(
            packaged_ov153,
            ov153_base,
            append_address + 0x8E,
            0,
        )
        == append_address + 0x80
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x80,
            4,
        )
        == bytes.fromhex("05 b0 f0 bd"),
        "AppendMove invalid/duplicate CFG can reach mutation",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x1E,
            0x32,
        )
        == bytes.fromhex(
            "18 29 18 d1 00 25 23 00 6a 00 10 33 99 5a 00 9b "
            "00 9a 0a 33 12 32 18 88 88 42 37 d0 02 33 93 42 "
            "f9 d1 68 00 20 18 a3 7b 82 1c 01 35 01 92 9d 42 "
            "21 d3"
        )
        and bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x84,
            0x30,
        )
        == bytes.fromhex(
            "22 00 58 00 10 32 12 5a ba 42 f7 d0 01 33 c2 e7 "
            "01 9b 02 aa 1b 8a 91 1d 10 30 02 22 0b 80 00 f0 "
            "b5 fb 01 98 cc e7 01 35 18 2d b9 d1 00 25 c5 e7"
        ),
        "AppendMove duplicate/capacity/eviction CFG window differs",
    )
    require(
        bytes_at(
            packaged_ov153,
            ov153_base,
            append_address + 0x50,
            0x30,
        )
        == bytes.fromhex(
            "01 3b a3 73 17 4b f2 58 a3 7b 59 1c 08 33 5b 00 "
            "a1 73 1f 53 00 9b 1b 89 a3 81 53 69 01 33 53 61 "
            "01 22 a3 60 10 4b f2 54 10 4a b3 58 01 33 b3 50"
        )
        and struct.unpack_from(
            "<III",
            packaged_ov153,
            append_address + 0xB4 - ov153_base,
        )
        == (0x0002F30C, 0x0002F310, 0x0002F314),
        "AppendMove history/store/dirty/revision mutation window differs",
    )

    disassembly = subprocess.check_output(
        ["arm-none-eabi-objdump", "-d", str(linked)],
        text=True,
    )
    linked_calls = [
        call
        for call in direct_thumb_calls(disassembly)
        if ov153_base <= call[0] < ov153_base + len(packaged_ov153)
    ]
    replace_calls = [
        call
        for call in linked_calls
        if replace_address <= call[0] < replace_address + replace_size
    ]
    recordable_calls = [
        call
        for call in linked_calls
        if recordable_address <= call[0] < recordable_address + recordable_size
    ]
    require(
        recordable_calls
        == [(recordable_call, "bl", recordable_trampoline)],
        "recordable-move predicate has extra/missing external calls",
    )
    append_calls = [
        call
        for call in linked_calls
        if append_address <= call[0] < append_address + append_size
    ]
    require(
        append_calls
        == [
            (append_address + 0x0E, "bl", recordable_address),
            (
                append_address + 0xA2,
                "bl",
                symbols["PokemonMoveHistory_OverlayMemcpy"],
            ),
        ],
        "AppendMove call graph differs or predicate is not uniquely first",
    )
    require(
        [
            address
            for address, mnemonic, target in replace_calls
            if mnemonic == "bl"
            and target == symbols["PokemonMoveHistory_CaptureSnapshotImpl"]
        ]
        == [capture_call],
        "ReplaceMove does not have exactly one authenticated snapshot call",
    )
    require(
        [
            (address, mnemonic, target)
            for address, mnemonic, target in replace_calls
            if address < equal_branch
        ]
        == [
            (
                replace_address + 0x20,
                "bl",
                symbols["PokemonMoveHistory_IsRecordableMove"],
            ),
            (same_slot_call, "bl", same_slot_trampoline),
        ],
        "ReplaceMove equality path gained an unauthenticated call",
    )
    for later_label, later_address in (
        (
            "PokemonMoveHistory_ObserveSnapshot",
            symbols["PokemonMoveHistory_ObserveSnapshot"],
        ),
        ("PokemonMoveHistory_AppendMove", append_address),
    ):
        require(
            [
                address
                for address, mnemonic, target in replace_calls
                if mnemonic == "bl" and target == later_address
            ]
            and all(
                address > capture_call
                for address, mnemonic, target in replace_calls
                if mnemonic == "bl" and target == later_address
            )
            and len(
                [
                    address
                    for address, mnemonic, target in replace_calls
                    if mnemonic == "bl" and target == later_address
                ]
            )
            == 1,
            f"ReplaceMove {later_label} call is not uniquely after snapshot",
        )
    for call_address, mnemonic, disassembly_target in linked_calls:
        packaged_target = (
            thumb_bl_target(packaged_ov153, ov153_base, call_address)
            if mnemonic == "bl"
            else thumb_blx_target(packaged_ov153, ov153_base, call_address)
        )
        require(
            packaged_target == disassembly_target,
            f"packaged {mnemonic} at 0x{call_address:08X} targets "
            f"0x{packaged_target:08X}, linked object says "
            f"0x{disassembly_target:08X}",
        )

    helper_specs = (
        ("PokemonMoveHistory_OverlayMemcpy", 3, 0x020E5AD8),
        ("PokemonMoveHistory_OverlayMemset", 1, 0x020E5B44),
    )
    helper_addresses: dict[str, int] = {}
    for helper, expected_count, retail_target in helper_specs:
        require(helper in symbols, f"local bridge symbol {helper} is absent")
        helper_address = symbols[helper]
        helper_addresses[helper] = helper_address
        require(
            OVERLAY_BASE <= helper_address < OVERLAY_BASE + len(packaged_ov153),
            f"local bridge {helper} is outside overlay 153",
        )
        calls = [
            call_address
            for call_address, mnemonic, target in linked_calls
            if mnemonic == "bl" and target == helper_address
        ]
        require(
            len(calls) == expected_count,
            f"{helper} packaged call count is {len(calls)}, expected {expected_count}",
        )
        for call_address in calls:
            require(
                thumb_bl_target(
                    packaged_ov153,
                    ov153_base,
                    call_address,
                )
                == helper_address,
                f"0x{call_address:08X} does not target local {helper}",
            )
        expected_body = (
            b"\x00\xb5"
            + encode_thumb_blx(helper_address + 2, retail_target)
            + b"\x00\xbd"
        )
        require(
            linked_symbol_sizes.get(helper) == 8
            and bytes_at(
                packaged_ov153,
                ov153_base,
                helper_address,
                8,
            )
            == expected_body
            and thumb_blx_target(
                packaged_ov153,
                ov153_base,
                helper_address + 2,
            )
            == retail_target,
            f"{helper} is not the exact 8-byte local interworking bridge",
        )

    raw_retail_targets = {0x020E5AD8, 0x020E5B44}
    expected_raw_calls = {
        (
            helper_addresses["PokemonMoveHistory_OverlayMemcpy"] + 2,
            0x020E5AD8,
        ),
        (
            helper_addresses["PokemonMoveHistory_OverlayMemset"] + 2,
            0x020E5B44,
        ),
    }
    observed_raw_calls = {
        (call_address, target)
        for call_address, _mnemonic, target in linked_calls
        if target in raw_retail_targets
    }
    require(
        observed_raw_calls == expected_raw_calls,
        "raw retail copy/clear calls differ from the two local bridge bodies",
    )
    for old_bridge in (0x023DEE42, 0x023DEE5E):
        require(
            all(target != old_bridge for _address, _mnemonic, target in linked_calls),
            f"overlay 153 still calls overlay-129 bridge 0x{old_bridge:08X}",
        )

    relocation_text = "\n".join(
        subprocess.check_output(
            ["arm-none-eabi-objdump", "-r", str(object_path)],
            text=True,
        )
        for object_path in (
            history_object,
            relearn_object,
            REPO / "build/pokemon_move_history_overlay/entry.o",
            REPO / "build/pokemon_move_history_overlay/thumb_help.o",
        )
    )
    relocation_names = re.findall(
        r"R_ARM_(?:ABS32|THM_CALL)\s+([A-Za-z0-9_.$]+)",
        relocation_text,
    )
    require(
        relocation_names.count("PokemonMoveHistory_OverlayMemcpy") == 3
        and relocation_names.count("PokemonMoveHistory_OverlayMemset") == 1
        and relocation_names.count("MIi_CpuClearFast") == 3,
        "overlay copy/clear relocation multiset differs",
    )
    require(
        not [
            name
            for name in relocation_names
            if re.search(
                r"(?:memcpy|memset|memmove|bcopy|bzero)",
                name,
                re.IGNORECASE,
            )
            and name
            not in {
                "PokemonMoveHistory_OverlayMemcpy",
                "PokemonMoveHistory_OverlayMemset",
            }
        ],
        "overlay contains an unapproved raw copy/clear relocation",
    )
    cpu_copy_clear_relocations = [
        name
        for name in relocation_names
        if re.fullmatch(r"MIi?_Cpu(?:Copy|Clear|Fill)[A-Za-z0-9_]*", name)
    ]
    require(
        cpu_copy_clear_relocations == ["MIi_CpuClearFast"] * 3,
        "overlay gained an unapproved raw CPU copy/clear/fill relocation",
    )
    require(
        packaged_ov153.count(struct.pack("<I", 0x020D4858)) == 3,
        "packaged overlay does not resolve exactly three MIi_CpuClearFast "
        "literals",
    )
    for forbidden_literal in (
        0x020E5AD8,
        0x020E5B44,
        0x023DEE42,
        0x023DEE43,
        0x023DEE5E,
        0x023DEE5F,
    ):
        require(
            struct.pack("<I", forbidden_literal) not in packaged_ov153,
            f"packaged overlay contains forbidden raw copy/clear literal "
            f"0x{forbidden_literal:08X}",
        )

    nm_all = subprocess.check_output(
        ["arm-none-eabi-nm", str(linked)], text=True
    )
    require(
        "__PokemonMoveHistory_" not in nm_all,
        "overlay 153 contains generated move-history veneers",
    )
    print(
        "move-history capture: source, fixtures, ABI relocations, and final "
        "packaged hook/helper targets verified"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rom",
        type=Path,
        help="current packaged ROM; required unless --source-only is used",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="content-addressed build manifest; required with --rom",
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="run deterministic source and host checks before packaging",
    )
    parser.add_argument(
        "--pre-make",
        action="store_true",
        help="authenticate Make inputs before GNU Make parses the workspace",
    )
    parser.add_argument(
        "--managed-build",
        action="store_true",
        help="re-exec the authenticated Docker build under a scrubbed environment",
    )
    parser.add_argument(
        "--managed-build-clean",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--managed-build-probe",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--managed-build-probe-clean",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    require(
        sum(
            (
                args.pre_make,
                args.managed_build,
                args.managed_build_clean,
                args.managed_build_probe,
                args.managed_build_probe_clean,
                args.source_only,
                args.rom is not None,
            )
        )
        == 1,
        "choose exactly one build/source/package verification mode",
    )
    require(
        (args.rom is not None) == (args.manifest is not None),
        "--manifest is required exactly when --rom is used",
    )
    if args.managed_build:
        enter_managed_build_environment("--managed-build-clean")
    if args.managed_build_clean:
        exec_managed_build()
    if args.managed_build_probe:
        enter_managed_build_environment("--managed-build-probe-clean")
    if args.managed_build_probe_clean:
        require(
            managed_build_environment_is_exact(),
            "managed build probe environment contains inherited variables",
        )
        print(
            json.dumps(
                managed_build_environment(),
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return
    if args.pre_make:
        makefile = (REPO / "Makefile").read_text()
        require(
            outer_make_invocation_is_safe(),
            "pre-Make environment contains unsafe flags or overrides",
        )
        require(
            trusted_pre_make_sources_are_exact(makefile),
            "pre-Make source/dependency trust gate differs",
        )
        print("move-history capture: pre-Make trust gate verified")
        return
    source_contracts()
    host_fixtures(args.manifest, args.rom)
    if args.source_only:
        print("move-history capture: source and host fixtures verified")
    else:
        binary_contracts(args.rom, args.manifest)


if __name__ == "__main__":
    main()
