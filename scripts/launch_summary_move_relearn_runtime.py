#!/usr/bin/env python3
"""Authenticate retained runtime sources before executing Summary acceptance."""

import sys


_NATIVE_BOOTSTRAP_PROTOCOL = "summary-move-relearn-native-bootstrap-v1"
_NATIVE_BOOTSTRAP_READY = b"SUMMARY_MOVE_RELEARN_PYTHON_READY_V1\n"
_NATIVE_BOOTSTRAP_GO = b"SUMMARY_MOVE_RELEARN_NATIVE_GO_V1\n"


def _native_bootstrap_gate():
    """Stop before stage zero unless the native trust parent releases us."""
    if __name__ != "__main__":
        return {}
    import posix

    environment = posix.environ
    if environment.get(b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_PROTOCOL") != (
        _NATIVE_BOOTSTRAP_PROTOCOL.encode("ascii")
    ):
        raise SystemExit(
            "Summary relearn runtime requires the authenticated native bootstrap"
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
    required = (
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_PATH",
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256",
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_PATH",
        b"SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_SHA256",
    )
    try:
        record = {
            name.decode("ascii"): environment[name].decode("utf-8")
            for name in required
        }
    except (KeyError, UnicodeDecodeError) as error:
        raise SystemExit("native bootstrap authentication record is absent") from error
    if any(not value for value in record.values()):
        raise SystemExit("native bootstrap authentication record is empty")
    return record


NATIVE_BOOTSTRAP_AUTHENTICATION = _native_bootstrap_gate()


def _stage_zero_startup_sys_path():
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    zip_version = f"python{sys.version_info.major}{sys.version_info.minor}.zip"
    library = sys.base_prefix + "/lib/" + version
    return (
        sys.base_prefix + "/lib/" + zip_version,
        library,
        library + "/lib-dynload",
    )


def _stage_zero_expected_sys_path():
    return _stage_zero_startup_sys_path()[1:]


if (
    sys.flags.isolated == 1
    and sys.flags.ignore_environment == 1
    and sys.flags.no_site == 1
    and sys.dont_write_bytecode
    and sys.pycache_prefix == "/dev/null"
    and "site" not in sys.modules
    and tuple(sys.path) == _stage_zero_startup_sys_path()
):
    # The default nonexistent pythonXY.zip entry must not become executable
    # through a mid-run filesystem substitution.
    sys.path[:] = _stage_zero_expected_sys_path()
    _external = sys.modules["_frozen_importlib_external"]
    sys.path_hooks[:] = [
        _external.FileFinder.path_hook(
            (_external.SourceFileLoader, _external.SOURCE_SUFFIXES),
            (_external.ExtensionFileLoader, _external.EXTENSION_SUFFIXES),
        )
    ]
    sys.path_importer_cache.clear()
    del _external


def _stage_zero_policy_ok():
    return (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and "site" not in sys.modules
        and tuple(sys.path) == _stage_zero_expected_sys_path()
    )


_S0_SHA256_INITIAL = (
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
)
_S0_SHA256_ROUND = (
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
)


class _StageZeroSha256:
    def __init__(self):
        self.state = list(_S0_SHA256_INITIAL)
        self.pending = b""
        self.length = 0

    def _block(self, block):
        words = [
            int.from_bytes(block[index:index + 4], "big")
            for index in range(0, 64, 4)
        ]
        for index in range(16, 64):
            x = words[index - 15]
            y = words[index - 2]
            s0 = ((x >> 7) | (x << 25)) ^ ((x >> 18) | (x << 14)) ^ (x >> 3)
            s1 = ((y >> 17) | (y << 15)) ^ ((y >> 19) | (y << 13)) ^ (y >> 10)
            words.append((words[index - 16] + s0 + words[index - 7] + s1) & 0xFFFFFFFF)
        a, b, c, d, e, f, g, h = self.state
        for index in range(64):
            s1 = ((e >> 6) | (e << 26)) ^ ((e >> 11) | (e << 21)) ^ ((e >> 25) | (e << 7))
            choose = (e & f) ^ ((~e) & g)
            t1 = (h + s1 + choose + _S0_SHA256_ROUND[index] + words[index]) & 0xFFFFFFFF
            s0 = ((a >> 2) | (a << 30)) ^ ((a >> 13) | (a << 19)) ^ ((a >> 22) | (a << 10))
            majority = (a & b) ^ (a & c) ^ (b & c)
            t2 = (s0 + majority) & 0xFFFFFFFF
            h, g, f, e, d, c, b, a = g, f, e, (d + t1) & 0xFFFFFFFF, c, b, a, (t1 + t2) & 0xFFFFFFFF
        self.state = [
            (old + new) & 0xFFFFFFFF
            for old, new in zip(self.state, (a, b, c, d, e, f, g, h))
        ]

    def update(self, data):
        self.length += len(data)
        data = self.pending + data
        full = len(data) & ~63
        for index in range(0, full, 64):
            self._block(data[index:index + 64])
        self.pending = data[full:]

    def digest(self):
        clone = _StageZeroSha256()
        clone.state = list(self.state)
        clone.pending = self.pending
        clone.length = self.length
        tail = clone.pending + b"\x80"
        tail += bytes((56 - len(tail) % 64) % 64)
        tail += (clone.length * 8).to_bytes(8, "big")
        for index in range(0, len(tail), 64):
            clone._block(tail[index:index + 64])
        return b"".join(value.to_bytes(4, "big") for value in clone.state)

    def hexdigest(self):
        return self.digest().hex()


def _stage_zero_bytes_record(data):
    digest = _StageZeroSha256()
    digest.update(data)
    return {"size": len(data), "sha256": digest.hexdigest()}


def _stage_zero_file_record(path):
    digest = _StageZeroSha256()
    size = 0
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return {"size": size, "sha256": digest.hexdigest()}


def _stage_zero_json(data):
    text = data.decode("utf-8")
    cursor = 0

    def whitespace():
        nonlocal cursor
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1

    def value():
        nonlocal cursor
        whitespace()
        if cursor >= len(text):
            raise ValueError("truncated JSON")
        token = text[cursor]
        if token == '"':
            cursor += 1
            output = []
            while cursor < len(text):
                token = text[cursor]
                cursor += 1
                if token == '"':
                    return "".join(output)
                if token == "\\":
                    escape = text[cursor]
                    cursor += 1
                    escapes = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
                    if escape == "u":
                        output.append(chr(int(text[cursor:cursor + 4], 16)))
                        cursor += 4
                    elif escape in escapes:
                        output.append(escapes[escape])
                    else:
                        raise ValueError("invalid JSON escape")
                else:
                    output.append(token)
            raise ValueError("unterminated JSON string")
        if token == "{":
            cursor += 1
            output = {}
            whitespace()
            if cursor < len(text) and text[cursor] == "}":
                cursor += 1
                return output
            while True:
                key = value()
                whitespace()
                if not isinstance(key, str) or cursor >= len(text) or text[cursor] != ":":
                    raise ValueError("invalid JSON object")
                cursor += 1
                output[key] = value()
                whitespace()
                if cursor < len(text) and text[cursor] == "}":
                    cursor += 1
                    return output
                if cursor >= len(text) or text[cursor] != ",":
                    raise ValueError("invalid JSON object separator")
                cursor += 1
        if token == "[":
            cursor += 1
            output = []
            whitespace()
            if cursor < len(text) and text[cursor] == "]":
                cursor += 1
                return output
            while True:
                output.append(value())
                whitespace()
                if cursor < len(text) and text[cursor] == "]":
                    cursor += 1
                    return output
                if cursor >= len(text) or text[cursor] != ",":
                    raise ValueError("invalid JSON array separator")
                cursor += 1
        for literal, parsed in (("true", True), ("false", False), ("null", None)):
            if text.startswith(literal, cursor):
                cursor += len(literal)
                return parsed
        start = cursor
        while cursor < len(text) and text[cursor] in "-+0123456789.eE":
            cursor += 1
        number = text[start:cursor]
        if not number:
            raise ValueError("invalid JSON token")
        return float(number) if any(marker in number for marker in ".eE") else int(number)

    document = value()
    whitespace()
    if cursor != len(text):
        raise ValueError("trailing JSON data")
    return document


def _stage_zero_option(arguments, name):
    matches = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == name and index + 1 < len(arguments):
            matches.append(arguments[index + 1])
            index += 2
            continue
        if argument.startswith(name + "="):
            matches.append(argument.split("=", 1)[1])
        index += 1
    if len(matches) != 1 or not matches[0]:
        raise ValueError(name + " is required exactly once")
    return matches[0]


def _stage_zero_tree_record(root):
    import posix
    paths = []

    def collect(directory, prefix=""):
        for name in posix.listdir(directory):
            relative = name if not prefix else prefix + "/" + name
            path = directory + "/" + name
            metadata = posix.lstat(path)
            mode = metadata.st_mode & 0o170000
            if mode == 0o040000:
                collect(path, relative)
            else:
                paths.append((relative, path, mode))

    collect(root)
    digest = _StageZeroSha256()
    count = 0
    size = 0
    for relative, path, mode in sorted(paths):
        parts = relative.split("/")
        if "__pycache__" in parts or "site-packages" in parts or relative.endswith(".pyc"):
            continue
        if not relative.endswith((".py", ".so", ".dylib", ".dll")):
            continue
        encoded = relative.encode("utf-8")
        if mode == 0o120000:
            target = posix.readlink(path).encode("utf-8")
            digest.update(b"L\0" + encoded + b"\0")
            digest.update(len(target).to_bytes(8, "little") + target)
            count += 1
            size += len(target)
        elif mode == 0o100000:
            with open(path, "rb") as stream:
                data = stream.read()
            leaf = _StageZeroSha256()
            leaf.update(data)
            digest.update(b"F\0" + encoded + b"\0")
            digest.update(len(data).to_bytes(8, "little"))
            digest.update(leaf.digest())
            count += 1
            size += len(data)
    return {"root": root, "files": count, "size": size, "sha256": digest.hexdigest()}


def _stage_zero_authenticate(arguments):
    manifest_path = _stage_zero_option(arguments, "--publication-manifest")
    expected_manifest = _stage_zero_option(arguments, "--expected-publication-manifest-sha256")
    expected_launcher = _stage_zero_option(arguments, "--expected-runtime-launcher-sha256")
    with open(__file__, "rb") as stream:
        launcher_record = _stage_zero_bytes_record(stream.read())
    if launcher_record["sha256"] != expected_launcher:
        raise ValueError("stage-zero launcher SHA-256 differs")
    with open(manifest_path, "rb") as stream:
        manifest_bytes = stream.read()
    manifest_record = _stage_zero_bytes_record(manifest_bytes)
    if manifest_record["sha256"] != expected_manifest:
        raise ValueError("stage-zero publication manifest SHA-256 differs")
    document = _stage_zero_json(manifest_bytes)
    inputs = document.get("inputs")
    if not isinstance(inputs, dict) or inputs.get("scripts/launch_summary_move_relearn_runtime.py") != launcher_record:
        raise ValueError("stage-zero manifest does not authenticate launcher")
    runtime = document.get("runtime_environment")
    if not isinstance(runtime, dict) or runtime.get("status") != "bound":
        raise ValueError("stage-zero runtime environment is not bound")
    bootstrap = runtime.get("native_bootstrap")
    if not isinstance(bootstrap, dict):
        raise ValueError("stage-zero native bootstrap record is absent")
    for name, environment_name in (
        ("binary", "SUMMARY_MOVE_RELEARN_BOOTSTRAP_PATH"),
        (
            "inventory",
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_PATH",
        ),
    ):
        record = bootstrap.get(name)
        if (
            not isinstance(record, dict)
            or record.get("path")
            != NATIVE_BOOTSTRAP_AUTHENTICATION.get(environment_name)
            or _stage_zero_file_record(record.get("path", ""))
            != {
                "size": record.get("size"),
                "sha256": record.get("sha256"),
            }
        ):
            raise ValueError("stage-zero native bootstrap record differs: " + name)
    if bootstrap["binary"]["sha256"] != NATIVE_BOOTSTRAP_AUTHENTICATION.get(
        "SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256"
    ) or bootstrap["inventory"]["sha256"] != (
        NATIVE_BOOTSTRAP_AUTHENTICATION.get(
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_SHA256"
        )
    ):
        raise ValueError("stage-zero native bootstrap digest pin differs")
    python = runtime.get("python")
    if not isinstance(python, dict):
        raise ValueError("stage-zero Python closure is malformed")
    repo = __file__.rsplit("/scripts/", 1)[0]
    if python.get("entry_path") != repo + "/.venv/bin/python3" or sys.executable != python.get("entry_path"):
        raise ValueError("stage-zero Python entry differs")
    for name in ("executable", "shared_runtime", "pyvenv_cfg"):
        record = python.get(name)
        if not isinstance(record, dict) or _stage_zero_file_record(record.get("path", "")) != {"size": record.get("size"), "sha256": record.get("sha256")}:
            raise ValueError("stage-zero Python record differs: " + name)
    stdlib = python.get("stdlib")
    if not isinstance(stdlib, dict) or _stage_zero_tree_record(stdlib.get("root", "")) != stdlib:
        raise ValueError("stage-zero stdlib closure differs")
    startup = python.get("startup_bootstrap")
    startup_names = (
        "abc", "codecs", "encodings", "encodings.aliases",
        "encodings.utf_8", "io",
    )
    if not isinstance(startup, dict) or set(startup.get("modules", {})) != set(startup_names):
        raise ValueError("stage-zero startup bootstrap record differs")
    for name in startup_names:
        record = startup["modules"][name]
        if _stage_zero_file_record(record.get("path", "")) != {"size": record.get("size"), "sha256": record.get("sha256")}:
            raise ValueError("stage-zero startup module differs: " + name)
    for name, module in tuple(sys.modules.items()):
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        if origin in ("built-in", "frozen"):
            continue
        file_origin = getattr(module, "__file__", None)
        origin = origin if isinstance(origin, str) else file_origin
        loader = getattr(module, "__loader__", None)
        loader_type = loader if isinstance(loader, type) else type(loader)
        loader_name = getattr(loader_type, "__name__", "")
        if loader_name in ("SourcelessFileLoader", "zipimporter"):
            raise ValueError("stage-zero forbidden loader: " + name)
        if not isinstance(origin, str) or not (origin == __file__ or origin.startswith(stdlib["root"] + "/")):
            raise ValueError("stage-zero module origin is outside closure: " + name)
    return True


def _stage_zero_result_targets(arguments):
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--result-json":
            if index + 1 < len(arguments):
                yield arguments[index + 1]
                index += 2
                continue
        elif argument.startswith("--result-json="):
            yield argument.split("=", 1)[1]
        index += 1


def _stage_zero_invalidate_results(arguments):
    import posix

    failures = []
    for target in _stage_zero_result_targets(arguments):
        if not target:
            continue
        try:
            posix.unlink(target)
        except FileNotFoundError:
            pass
        except OSError as error:
            failures.append(f"{target}: {error}")
    return failures


if __name__ == "__main__" and not _stage_zero_policy_ok():
    stage_zero_failures = _stage_zero_invalidate_results(sys.argv[1:])
    print(
        "Summary relearn runtime launcher failed: start Python with "
        "-I -S -B -X pycache_prefix=/dev/null"
        + (
            "; stale-result invalidation failed: "
            + "; ".join(stage_zero_failures)
            if stage_zero_failures
            else ""
        ),
        file=sys.stderr,
    )
    raise SystemExit(1)

if __name__ == "__main__":
    stage_zero_failures = _stage_zero_invalidate_results(sys.argv[1:])
    try:
        if stage_zero_failures:
            raise ValueError(
                "stale-result invalidation failed: "
                + "; ".join(stage_zero_failures)
            )
        _stage_zero_authenticate(sys.argv[1:])
    except Exception as stage_zero_error:
        print(
            f"Summary relearn runtime launcher failed before ordinary imports: "
            f"{stage_zero_error}",
            file=sys.stderr,
        )
        raise SystemExit(1)

import os


def _early_result_targets(arguments):
    targets = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--result-json":
            if index + 1 < len(arguments):
                targets.append(arguments[index + 1])
                index += 2
                continue
        elif argument.startswith("--result-json="):
            targets.append(argument.split("=", 1)[1])
        index += 1
    return targets


def _invalidate_results(arguments):
    failures = []
    resolved = []
    for target in _early_result_targets(arguments):
        if not target:
            continue
        path = os.path.realpath(os.path.abspath(target))
        if path in resolved:
            continue
        resolved.append(path)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except OSError as error:
            failures.append(f"{path}: {error}")
    if failures:
        raise RuntimeError(
            "could not invalidate stale runtime result: "
            + "; ".join(failures)
        )
    return tuple(resolved)


def _ensure_repo_venv(repo):
    venv = os.path.join(repo, ".venv")
    python = os.path.join(venv, "bin", "python3")
    if os.path.abspath(sys.executable) == os.path.abspath(python):
        return
    raise RuntimeError(
        "native bootstrap did not execute exact repository .venv/bin/python3"
    )


def _sanitize_process_environment():
    bootstrap_environment = {
        key: value
        for key, value in NATIVE_BOOTSTRAP_AUTHENTICATION.items()
    }
    os.environ.clear()
    os.environ.update(
        {
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "SDL_AUDIODRIVER": "dummy",
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_PROTOCOL": (
                _NATIVE_BOOTSTRAP_PROTOCOL
            ),
            **bootstrap_environment,
        }
    )


if __name__ == "__main__":
    try:
        EARLY_INVALIDATED_RESULTS = _invalidate_results(sys.argv[1:])
    except Exception as early_error:
        print(
            f"Summary relearn runtime launcher failed: {early_error}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    EARLY_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _ensure_repo_venv(EARLY_REPO)
    _sanitize_process_environment()
else:
    EARLY_INVALIDATED_RESULTS = ()
    EARLY_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


import hashlib
import json
import types


SCHEMA = "pokemon-move-history-capture-build-v1"
PACKAGED_ROM_LOGICAL_PATH = "@packaged-rom"
LAUNCHER_RELATIVE = "scripts/launch_summary_move_relearn_runtime.py"
VERIFIER_RELATIVE = "scripts/verify_summary_move_relearn_runtime.py"
MANIFEST_HELPER_RELATIVE = (
    "scripts/pokemon_move_history_build_manifest.py"
)
HEADLESS_RELATIVE = "scripts/headless-overworld-test.py"
PARTY_RELATIVE = (
    "scripts/verify_pokemon_move_history_party_integrity.py"
)
RUNTIME_MODULE_RELATIVES = (
    "desmume/__init__.py",
    "desmume/i18n_util.py",
    "desmume/controls.py",
    "desmume/emulator.py",
)
AUTHENTICATED_SOURCES = (
    LAUNCHER_RELATIVE,
    VERIFIER_RELATIVE,
    MANIFEST_HELPER_RELATIVE,
    HEADLESS_RELATIVE,
    PARTY_RELATIVE,
)


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _extract_single_option(arguments, name, required=True):
    matches = []
    index = 0
    prefix = name + "="
    while index < len(arguments):
        argument = arguments[index]
        if argument == name:
            _require(
                index + 1 < len(arguments),
                f"{name} requires a value",
            )
            matches.append(arguments[index + 1])
            index += 2
            continue
        if argument.startswith(prefix):
            matches.append(argument[len(prefix):])
        index += 1
    _require(
        len(matches) <= 1,
        f"{name} must be supplied at most once",
    )
    if required:
        _require(len(matches) == 1 and bool(matches[0]), f"{name} is required")
    return matches[0] if matches else None


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _bytes_record(data):
    return {"size": len(data), "sha256": _sha256(data)}


def _path_record(path):
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return {"size": size, "sha256": digest.hexdigest()}


def _runtime_tree_record(root, suffixes=None):
    root = os.path.realpath(os.path.abspath(root))
    _require(os.path.isdir(root), f"runtime closure root is absent: {root}")
    digest = hashlib.sha256()
    count = 0
    size = 0

    def visit(directory, prefix=""):
        nonlocal count, size
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda entry: entry.name)
        for entry in ordered:
            relative = entry.name if not prefix else prefix + "/" + entry.name
            parts = relative.split("/")
            if (
                "__pycache__" in parts
                or "site-packages" in parts
                or entry.name.endswith(".pyc")
            ):
                continue
            included = suffixes is None or any(
                entry.name.endswith(suffix) for suffix in suffixes
            )
            if entry.is_symlink():
                if included:
                    target = os.readlink(entry.path).encode("utf-8")
                    digest.update(b"L\0" + relative.encode("utf-8") + b"\0")
                    digest.update(len(target).to_bytes(8, "little") + target)
                    count += 1
                    size += len(target)
            elif entry.is_dir(follow_symlinks=False):
                visit(entry.path, relative)
            elif entry.is_file(follow_symlinks=False) and included:
                with open(entry.path, "rb") as stream:
                    data = stream.read()
                digest.update(b"F\0" + relative.encode("utf-8") + b"\0")
                digest.update(len(data).to_bytes(8, "little"))
                digest.update(hashlib.sha256(data).digest())
                count += 1
                size += len(data)

    visit(root)
    _require(count > 0, f"runtime closure is empty: {root}")
    return {
        "root": root,
        "files": count,
        "size": size,
        "sha256": digest.hexdigest(),
    }


def _validate_file_path_record(record, label):
    _require(
        isinstance(record, dict)
        and set(record) == {"path", "size", "sha256"}
        and isinstance(record["path"], str),
        f"runtime {label} record is malformed",
    )
    path = os.path.realpath(os.path.abspath(record["path"]))
    _require(path == record["path"], f"runtime {label} path is not canonical")
    _require(
        _path_record(path)
        == {"size": record["size"], "sha256": record["sha256"]},
        f"runtime {label} content differs",
    )
    return path


def _loader_name(loader):
    if loader is None:
        return "None"
    loader_type = loader if isinstance(loader, type) else type(loader)
    return loader_type.__module__ + "." + loader_type.__qualname__


def _path_under(path, root):
    return path == root or path.startswith(root + os.sep)


class RetainedSourceLoader:
    """Identity marker for code executed only from authenticated buffers."""


RETAINED_SOURCE_LOADER = RetainedSourceLoader()


def _authenticate_loaded_python_modules(runtime, authenticated_paths):
    python = runtime["python"]
    stdlib_root = python["stdlib"]["root"]
    package_roots = tuple(
        record["root"] for record in runtime["packages"].values()
    )
    native_paths = {
        record["path"] for record in runtime["native"]["mutable_closure"]
    }
    exact_sources = {
        os.path.realpath(os.path.abspath(path)) for path in authenticated_paths
    }
    forbidden = set(python["bytecode_policy"]["forbidden_loaders"])
    records = {}
    for name, module in sorted(sys.modules.items()):
        if not isinstance(module, types.ModuleType):
            continue
        spec = getattr(module, "__spec__", None)
        spec_origin = getattr(spec, "origin", None)
        file_origin = getattr(module, "__file__", None)
        loader = getattr(module, "__loader__", None)
        loader_name = _loader_name(loader)
        short_loader = loader_name.rsplit(".", 1)[-1]
        _require(
            short_loader not in forbidden,
            f"forbidden Python loader is active: {name}: {loader_name}",
        )
        if spec_origin in ("built-in", "frozen"):
            records[name] = {
                "loader": loader_name,
                "origin": spec_origin,
            }
            continue
        origin = spec_origin if isinstance(spec_origin, str) else file_origin
        _require(
            isinstance(origin, str) and bool(origin),
            f"loaded Python module has no authenticated origin: {name}",
        )
        canonical = os.path.realpath(os.path.abspath(origin))
        _require(
            canonical == origin and os.path.isfile(canonical),
            f"loaded Python module origin is not canonical: {name}: {origin}",
        )
        if isinstance(file_origin, str):
            _require(
                os.path.realpath(os.path.abspath(file_origin)) == canonical,
                f"loaded Python module file/spec origins differ: {name}",
            )
        if short_loader == "SourceFileLoader":
            _require(
                canonical.endswith(".py")
                and (
                    _path_under(canonical, stdlib_root)
                    or canonical in exact_sources
                ),
                f"source-loaded module is outside sealed source roots: {name}",
            )
        elif short_loader == "ExtensionFileLoader":
            _require(
                canonical in native_paths
                or _path_under(canonical, stdlib_root)
                or any(_path_under(canonical, root) for root in package_roots),
                f"extension module is outside sealed native roots: {name}",
            )
        elif short_loader in {"RetainedSourceLoader", "RetainedPackageLoader"}:
            _require(
                canonical.endswith(".py")
                and (
                    canonical in exact_sources
                    or any(
                        _path_under(canonical, root) for root in package_roots
                    )
                ),
                f"retained module is outside authenticated buffers: {name}",
            )
        else:
            _require(
                False,
                f"loaded Python module uses an unauthenticated loader: "
                f"{name}: {loader_name}",
            )
        records[name] = {"loader": loader_name, "origin": canonical}
    return records


def _primitive_runtime_authentication(document):
    runtime = _runtime_environment(document)
    _require(
        set(runtime)
        == {
            "schema",
            "status",
            "native_bootstrap",
            "platform",
            "python",
            "packages",
            "modules",
            "native",
        },
        "runtime environment field set differs",
    )
    bootstrap = runtime["native_bootstrap"]
    _require(
        isinstance(bootstrap, dict)
        and set(bootstrap)
        == {
            "schema",
            "binary",
            "inventory",
            "source",
            "build_helper",
            "compile",
            "codesign",
            "linked_images",
            "root_of_trust",
        }
        and bootstrap["schema"]
        == "summary-move-relearn-native-bootstrap-v1",
        "native bootstrap provenance is malformed",
    )
    bootstrap_path = os.path.realpath(
        os.path.join(EARLY_REPO, "build/summary_move_relearn_native_bootstrap")
    )
    inventory_path = os.path.realpath(
        os.path.join(
            EARLY_REPO,
            "scripts/summary_move_relearn_native_inventory.txt",
        )
    )
    _require(
        _validate_file_path_record(
            bootstrap["binary"], "native bootstrap binary"
        )
        == bootstrap_path
        and _validate_file_path_record(
            bootstrap["inventory"], "native bootstrap inventory"
        )
        == inventory_path
        and _validate_file_path_record(
            bootstrap["source"], "native bootstrap source"
        )
        == os.path.realpath(
            os.path.join(
                EARLY_REPO,
                "scripts/summary_move_relearn_native_bootstrap.c",
            )
        )
        and _validate_file_path_record(
            bootstrap["build_helper"], "native bootstrap build helper"
        )
        == os.path.realpath(
            os.path.join(
                EARLY_REPO,
                "scripts/build_summary_move_relearn_native_bootstrap.sh",
            )
        ),
        "native bootstrap sealed paths differ",
    )
    _require(
        NATIVE_BOOTSTRAP_AUTHENTICATION
        == {
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_PATH": bootstrap_path,
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_SELF_SHA256": bootstrap[
                "binary"
            ]["sha256"],
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_PATH": inventory_path,
            "SUMMARY_MOVE_RELEARN_BOOTSTRAP_INVENTORY_SHA256": bootstrap[
                "inventory"
            ]["sha256"],
        },
        "native bootstrap parent authentication differs",
    )
    _require(
        bootstrap["linked_images"]
        and len(bootstrap["linked_images"]) == 1
        and bootstrap["linked_images"][0].startswith(
            "/usr/lib/libSystem.B.dylib "
        )
        and isinstance(bootstrap["codesign"], dict)
        and bootstrap["codesign"].get("CDHash")
        and bootstrap["codesign"].get("CodeDirectoryFlags")
        == "0x12b02(adhoc,hard,kill,restrict,library-validation,runtime)"
        and bootstrap["codesign"].get("RuntimeVersion")
        and isinstance(bootstrap["compile"], dict)
        and bootstrap["compile"].get("compiler_codesign", {}).get("CDHash")
        and "external acceptance caller pins" in bootstrap["root_of_trust"]
        and "enforced by dyld/AMFI before main" in bootstrap["root_of_trust"],
        "native bootstrap trust boundary differs",
    )
    platform_record = runtime["platform"]
    _require(
        platform_record
        == {
            "system": sys.platform.lower(),
            "machine": os.uname().machine,
            "implementation": sys.implementation.name,
            "cache_tag": sys.implementation.cache_tag,
        },
        "runtime Python platform/implementation differs",
    )
    python = runtime["python"]
    _require(
        isinstance(python, dict)
        and set(python)
        == {
            "bytecode_policy",
            "entry_path",
            "executable",
            "shared_runtime",
            "pyvenv_cfg",
            "stdlib",
            "startup_bootstrap",
        },
        "runtime Python closure is malformed",
    )
    bytecode_policy = python["bytecode_policy"]
    _require(
        isinstance(bytecode_policy, dict)
        and set(bytecode_policy)
        == {
            "absent_zip_paths",
            "bytecode_reads_disabled",
            "dont_write_bytecode",
            "forbidden_loaders",
            "ignore_environment",
            "isolated",
            "no_site",
            "pycache_prefix",
            "scope",
            "sys_path",
        }
        and {
            key: value
            for key, value in bytecode_policy.items()
            if key != "absent_zip_paths"
        }
        == {
            "bytecode_reads_disabled": True,
            "dont_write_bytecode": True,
            "forbidden_loaders": [
                "SourcelessFileLoader",
                "zipimporter",
            ],
            "ignore_environment": True,
            "isolated": True,
            "no_site": True,
            "pycache_prefix": "/dev/null",
            "scope": (
                "Interpreter startup, host binders, retained helpers, and "
                "every acceptance child use isolated mode, ignore Python "
                "environment configuration, skip site/.pth processing, "
                "and restrict import lookup to the sealed stdlib paths. "
                "Every loaded module origin and loader is authenticated; "
                "zipimporter and sourceless bytecode are forbidden."
            ),
            "sys_path": list(_stage_zero_expected_sys_path()),
        }
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and "site" not in sys.modules
        and tuple(sys.path) == _stage_zero_expected_sys_path()
        and os.stat("/dev/null").st_mode & 0o170000 == 0o020000,
        "runtime Python bytecode-bypass policy differs",
    )
    current_zip_paths = sorted(
        os.path.abspath(entry)
        for entry in sys.path
        if isinstance(entry, str) and not os.path.exists(entry)
    )
    _require(
        bytecode_policy["absent_zip_paths"] == current_zip_paths
        and all(not os.path.exists(path) for path in current_zip_paths),
        "runtime zip import closure differs or became executable",
    )
    _require(
        python["entry_path"] == os.path.abspath(sys.executable),
        "runtime Python entry path differs",
    )
    _require(
        _validate_file_path_record(python["executable"], "Python executable")
        == os.path.realpath(sys.executable),
        "runtime Python executable resolution differs",
    )
    _validate_file_path_record(python["shared_runtime"], "shared Python runtime")
    _require(
        _validate_file_path_record(python["pyvenv_cfg"], "pyvenv.cfg")
        == os.path.realpath(
            os.path.join(
                os.path.dirname(os.path.dirname(python["entry_path"])),
                "pyvenv.cfg",
            )
        ),
        "runtime virtual-environment ownership differs",
    )
    stdlib = python["stdlib"]
    _require(
        isinstance(stdlib, dict)
        and set(stdlib) == {"root", "files", "size", "sha256"},
        "runtime standard-library closure is malformed",
    )
    expected_stdlib = os.path.realpath(
        os.path.join(
            sys.base_prefix,
            "lib",
            f"python{sys.version_info.major}.{sys.version_info.minor}",
        )
    )
    _require(stdlib["root"] == expected_stdlib, "runtime stdlib root differs")
    _require(
        _runtime_tree_record(
            expected_stdlib,
            (".py", ".so", ".dylib", ".dll"),
        )
        == stdlib,
        "runtime standard-library closure differs",
    )
    startup = python["startup_bootstrap"]
    startup_names = {
        "abc", "codecs", "encodings", "encodings.aliases",
        "encodings.utf_8", "io",
    }
    _require(
        isinstance(startup, dict)
        and set(startup) == {"modules", "scope"}
        and isinstance(startup["modules"], dict)
        and set(startup["modules"]) == startup_names,
        "runtime pre-script startup bootstrap record is malformed",
    )
    for name, record in startup["modules"].items():
        module = sys.modules.get(name)
        _require(module is not None, f"startup module is absent: {name}")
        origin = os.path.realpath(os.path.abspath(module.__file__))
        _require(
            _validate_file_path_record(record, f"startup module {name}")
            == origin
            and type(module.__loader__).__name__ == "SourceFileLoader",
            f"startup module loader/origin differs: {name}",
        )
    packages = runtime["packages"]
    _require(
        isinstance(packages, dict) and set(packages) == {"desmume", "PIL"},
        "runtime package closure is malformed",
    )
    for package, record in packages.items():
        _require(
            isinstance(record, dict)
            and set(record) == {"root", "files", "size", "sha256"}
            and _runtime_tree_record(record["root"]) == record,
            f"runtime {package} package closure differs",
        )
    _runtime_module_buffers(runtime)
    native = runtime["native"]
    _require(
        isinstance(native, dict)
        and set(native)
        == {"libdesmume", "mutable_closure", "os_trust_roots", "scope"}
        and isinstance(native["mutable_closure"], list)
        and isinstance(native["os_trust_roots"], list),
        "runtime native closure is malformed",
    )
    _validate_file_path_record(native["libdesmume"], "libdesmume")
    seen = set()
    for index, record in enumerate(native["mutable_closure"]):
        path = _validate_file_path_record(record, f"native closure item {index}")
        _require(path not in seen, "runtime native closure path duplicates")
        seen.add(path)
    _require(
        native["libdesmume"]["path"] in seen,
        "runtime native closure omits libdesmume",
    )
    return runtime


def _manifest_input_record(document, relative):
    inputs = document.get("inputs")
    _require(isinstance(inputs, dict), "publication manifest inputs malformed")
    record = inputs.get(relative)
    _require(
        isinstance(record, dict)
        and set(record) == {"size", "sha256"}
        and isinstance(record["size"], int)
        and record["size"] >= 0
        and isinstance(record["sha256"], str)
        and len(record["sha256"]) == 64,
        f"publication manifest input malformed: {relative}",
    )
    return record


def _load_authenticated_buffers(
    repo,
    manifest_path,
    rom_path,
    expected_manifest_sha256,
    expected_launcher_sha256,
    expected_verifier_sha256,
):
    with open(manifest_path, "rb") as stream:
        manifest_bytes = stream.read()
    manifest_record = _bytes_record(manifest_bytes)
    _require(
        manifest_record["sha256"] == expected_manifest_sha256,
        "publication manifest SHA-256 differs from required artifact",
    )
    try:
        document = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"publication manifest is not strict UTF-8 JSON: {error}"
        ) from error
    _require(
        isinstance(document, dict)
        and document.get("schema") == SCHEMA
        and set(document)
        == {
            "build_context",
            "inputs",
            "outputs",
            "runtime_environment",
            "schema",
            "tools",
        },
        "publication manifest schema differs or is malformed",
    )

    buffers = {}
    records = {}
    paths = {}
    for relative in AUTHENTICATED_SOURCES:
        path = os.path.join(repo, *relative.split("/"))
        with open(path, "rb") as stream:
            source = stream.read()
        record = _bytes_record(source)
        _require(
            record == _manifest_input_record(document, relative),
            f"authenticated source differs from manifest: {relative}",
        )
        buffers[relative] = source
        records[relative] = record
        paths[relative] = path
    _require(
        records[LAUNCHER_RELATIVE]["sha256"]
        == expected_launcher_sha256,
        "runtime launcher SHA-256 differs from required revision",
    )
    _require(
        records[VERIFIER_RELATIVE]["sha256"]
        == expected_verifier_sha256,
        "runtime verifier SHA-256 differs from required revision",
    )

    outputs = document.get("outputs")
    packaged = outputs.get("packaged_rom") if isinstance(outputs, dict) else None
    _require(
        isinstance(packaged, dict)
        and packaged.get("path") == PACKAGED_ROM_LOGICAL_PATH
        and set(packaged) == {"path", "size", "sha256"},
        "publication manifest packaged ROM record is malformed",
    )
    rom_record = _path_record(rom_path)
    _require(
        rom_record
        == {"size": packaged["size"], "sha256": packaged["sha256"]},
        "runtime ROM differs from publication manifest",
    )
    return (
        document,
        manifest_bytes,
        manifest_record,
        buffers,
        records,
        paths,
        rom_record,
    )


def _compile_buffers(buffers, paths):
    compiled = {}
    for relative in AUTHENTICATED_SOURCES:
        compiled[relative] = compile(
            buffers[relative],
            paths[relative],
            "exec",
            dont_inherit=True,
            optimize=0,
        )
    return compiled


def _runtime_environment(document):
    runtime = document.get("runtime_environment")
    _require(
        isinstance(runtime, dict)
        and runtime.get("schema")
        == "summary-move-relearn-runtime-environment-v1"
        and runtime.get("status") == "bound",
        "publication manifest runtime environment is not host-bound",
    )
    return runtime


def _runtime_module_buffers(runtime):
    records = runtime.get("modules")
    _require(
        isinstance(records, dict)
        and set(records) == set(RUNTIME_MODULE_RELATIVES),
        "runtime DeSmuME module closure is malformed",
    )
    buffers = {}
    paths = {}
    for relative in RUNTIME_MODULE_RELATIVES:
        record = records[relative]
        _require(
            isinstance(record, dict)
            and set(record) == {"path", "size", "sha256"},
            f"runtime module record is malformed: {relative}",
        )
        path = os.path.realpath(os.path.abspath(record["path"]))
        _require(
            path == record["path"],
            f"runtime module path is not canonical: {relative}",
        )
        with open(path, "rb") as stream:
            source = stream.read()
        _require(
            _bytes_record(source)
            == {"size": record["size"], "sha256": record["sha256"]},
            f"runtime module differs from publication manifest: {relative}",
        )
        buffers[relative] = source
        paths[relative] = path
    return buffers, paths


def _compile_runtime_modules(buffers, paths):
    return {
        relative: compile(
            buffers[relative],
            paths[relative],
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        for relative in RUNTIME_MODULE_RELATIVES
    }


def _install_retained_package_loader(runtime, package):
    root = runtime["packages"][package]["root"]
    sources = {}
    paths = {}
    packages = set()
    for directory, directory_names, file_names in os.walk(root):
        directory_names[:] = sorted(
            name for name in directory_names if name != "__pycache__"
        )
        for file_name in sorted(file_names):
            if not file_name.endswith(".py"):
                continue
            path = os.path.join(directory, file_name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            components = relative[:-3].split("/")
            is_package = components[-1] == "__init__"
            if is_package:
                components = components[:-1]
            module_name = ".".join((package, *components))
            with open(path, "rb") as stream:
                sources[module_name] = stream.read()
            paths[module_name] = path
            if is_package:
                packages.add(module_name)
    _require(package in packages, f"runtime {package} package source is absent")
    _require(
        not any(
            name == package or name.startswith(package + ".")
            for name in sys.modules
        ),
        f"runtime {package} was imported before retained-source loading",
    )

    bootstrap = sys.modules.get("_frozen_importlib")
    _require(
        bootstrap is not None and hasattr(bootstrap, "ModuleSpec"),
        "frozen import bootstrap is unavailable",
    )

    class RetainedPackageLoader:
        def find_spec(self, fullname, path=None, target=None):
            if fullname not in sources:
                return None
            return bootstrap.ModuleSpec(
                fullname,
                self,
                origin=paths[fullname],
                is_package=fullname in packages,
            )

        def create_module(self, spec):
            return None

        def exec_module(self, module):
            name = module.__name__
            module.__file__ = paths[name]
            module.__cached__ = None
            if name in packages:
                module.__path__ = [os.path.dirname(paths[name])]
            code = compile(
                sources[name],
                paths[name],
                "exec",
                dont_inherit=True,
                optimize=0,
            )
            exec(code, module.__dict__)

        def authenticate(self):
            for name, source in sources.items():
                with open(paths[name], "rb") as stream:
                    _require(
                        stream.read() == source,
                        f"retained {package} source changed: {name}",
                    )
            for name, module in tuple(sys.modules.items()):
                if name in sources:
                    _require(
                        module.__loader__ is self
                        and module.__cached__ is None,
                        f"runtime {package} module bypassed retained loader: "
                        f"{name}",
                    )

    loader = RetainedPackageLoader()
    sys.meta_path.insert(0, loader)
    return loader


def _execute_module(
    name,
    path,
    code,
    injected=None,
    *,
    package="",
    package_path=None,
):
    module = types.ModuleType(name)
    module.__file__ = path
    module.__cached__ = None
    module.__loader__ = RETAINED_SOURCE_LOADER
    module.__package__ = package
    module.__spec__ = None
    if package_path is not None:
        module.__path__ = [package_path]
    if injected:
        module.__dict__.update(injected)
    sys.modules[name] = module
    exec(code, module.__dict__)
    return module


def _execute_runtime_modules(compiled, paths):
    root = os.path.dirname(paths["desmume/__init__.py"])
    _execute_module(
        "desmume",
        paths["desmume/__init__.py"],
        compiled["desmume/__init__.py"],
        package="desmume",
        package_path=root,
    )
    for relative, name in (
        ("desmume/i18n_util.py", "desmume.i18n_util"),
        ("desmume/controls.py", "desmume.controls"),
        ("desmume/emulator.py", "desmume.emulator"),
    ):
        _execute_module(
            name,
            paths[relative],
            compiled[relative],
            package="desmume",
        )


def _path_identity(path):
    metadata = os.stat(path, follow_symlinks=False)
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _preload_runtime_native(runtime, manifest_module):
    import ctypes

    native = runtime.get("native")
    record = native.get("libdesmume") if isinstance(native, dict) else None
    _require(
        isinstance(record, dict)
        and set(record) == {"path", "size", "sha256"},
        "runtime libdesmume record is malformed",
    )
    path = os.path.realpath(os.path.abspath(record["path"]))
    _require(path == record["path"], "runtime libdesmume path is not canonical")
    before_identity = _path_identity(path)
    _require(
        _path_record(path)
        == {"size": record["size"], "sha256": record["sha256"]},
        "runtime libdesmume differs before native load",
    )
    handle = ctypes.CDLL(path)
    _require(
        _path_identity(path) == before_identity
        and _path_record(path)
        == {"size": record["size"], "sha256": record["sha256"]},
        "runtime libdesmume changed across native load",
    )
    _validate_loaded_native_closure(runtime, manifest_module)
    return handle, path


def _validate_loaded_native_closure(runtime, manifest_module):
    native = runtime["native"]
    closure = native.get("mutable_closure")
    roots = native.get("os_trust_roots")
    _require(
        isinstance(closure, list)
        and isinstance(roots, list)
        and all(isinstance(root, str) for root in roots),
        "runtime mutable native closure is malformed",
    )
    expected = {
        record["path"]: {"size": record["size"], "sha256": record["sha256"]}
        for record in closure
        if isinstance(record, dict)
        and set(record) == {"path", "size", "sha256"}
    }
    _require(
        len(expected) == len(closure),
        "runtime mutable native closure contains malformed/duplicate records",
    )
    loaded = manifest_module._loaded_native_paths()
    mutable = []
    for loaded_path in sorted(loaded):
        if manifest_module._under_runtime_root(loaded_path, tuple(roots)):
            continue
        path = os.path.realpath(os.path.abspath(loaded_path))
        _require(
            path in expected,
            f"loaded mutable native image is outside sealed closure: {path}",
        )
        _require(
            _path_record(path) == expected[path],
            f"loaded mutable native image differs: {path}",
        )
        mutable.append(path)
    libdesmume = native["libdesmume"]["path"]
    _require(
        libdesmume in mutable,
        "sealed libdesmume is not the loaded emulator image",
    )
    return tuple(mutable)


def _authentication_record(
    manifest_record,
    rom_record,
    records,
    runtime_environment,
):
    return {
        "schema": "summary-move-relearn-runtime-artifact-v3",
        "rom": dict(rom_record),
        "publication_manifest": dict(manifest_record),
        "runtime_launcher": dict(records[LAUNCHER_RELATIVE]),
        "runtime_verifier": dict(records[VERIFIER_RELATIVE]),
        "manifest_helper": dict(records[MANIFEST_HELPER_RELATIVE]),
        "runtime_helpers": {
            HEADLESS_RELATIVE: dict(records[HEADLESS_RELATIVE]),
            PARTY_RELATIVE: dict(records[PARTY_RELATIVE]),
        },
        "runtime_environment": json.loads(
            json.dumps(runtime_environment)
        ),
        "authenticated_at_start_and_end": True,
        "runtime_closure_authenticated_at_start_and_end": True,
        "loaded_native_images_restricted_to_sealed_closure": True,
        "executed_from_retained_source_buffers": True,
        "desmume_executed_from_retained_source_buffers": True,
        "pillow_python_executed_from_retained_source_buffers": True,
        "pycache_bypassed": True,
        "isolated_environment_ignored": True,
        "loaded_python_origins_authenticated_at_start_and_end": True,
        "sourceless_and_archive_loaders_rejected": True,
    }


def _late_main():
    arguments = sys.argv[1:]
    repo = EARLY_REPO
    rom_path = os.path.abspath(
        _extract_single_option(arguments, "--rom")
    )
    manifest_path = os.path.abspath(
        _extract_single_option(arguments, "--publication-manifest")
    )
    expected_manifest = _extract_single_option(
        arguments,
        "--expected-publication-manifest-sha256",
    )
    expected_launcher = _extract_single_option(
        arguments,
        "--expected-runtime-launcher-sha256",
    )
    expected_verifier = _extract_single_option(
        arguments,
        "--expected-runtime-verifier-sha256",
    )
    (
        document,
        manifest_bytes,
        manifest_record,
        buffers,
        records,
        paths,
        rom_record,
    ) = _load_authenticated_buffers(
        repo,
        manifest_path,
        rom_path,
        expected_manifest,
        expected_launcher,
        expected_verifier,
    )
    runtime_environment = _primitive_runtime_authentication(document)
    authenticated_module_paths = list(paths.values()) + [
        record["path"]
        for record in runtime_environment["modules"].values()
    ]
    initial_meta_path = tuple(sys.meta_path)
    initial_path_hooks = tuple(sys.path_hooks)
    _require(
        [_loader_name(finder) for finder in initial_meta_path]
        == [
            "_frozen_importlib.BuiltinImporter",
            "_frozen_importlib.FrozenImporter",
            "_frozen_importlib_external.PathFinder",
        ]
        and len(initial_path_hooks) == 1,
        "runtime import finder closure differs before helper execution",
    )
    _authenticate_loaded_python_modules(
        runtime_environment,
        authenticated_module_paths,
    )
    compiled = _compile_buffers(buffers, paths)

    manifest_module = _execute_module(
        "summary_relearn_manifest",
        paths[MANIFEST_HELPER_RELATIVE],
        compiled[MANIFEST_HELPER_RELATIVE],
    )
    manifest_module.verify_manifest(
        manifest_module.Path(manifest_path),
        manifest_module.Path(rom_path),
        require_bound_runtime=True,
    )
    _require(
        manifest_module.capture_runtime_environment()
        == runtime_environment,
        "runtime environment differs before DeSmuME source execution",
    )
    runtime_buffers, runtime_paths = _runtime_module_buffers(
        runtime_environment
    )
    runtime_compiled = _compile_runtime_modules(
        runtime_buffers,
        runtime_paths,
    )
    pil_loader = _install_retained_package_loader(
        runtime_environment,
        "PIL",
    )
    _execute_runtime_modules(runtime_compiled, runtime_paths)
    native_handle, libdesmume_path = _preload_runtime_native(
        runtime_environment,
        manifest_module,
    )
    native_bootstrap = runtime_environment["native_bootstrap"]
    native_prefix = [
        native_bootstrap["binary"]["path"],
        "--inventory",
        native_bootstrap["inventory"]["path"],
        "--expected-inventory-sha256",
        native_bootstrap["inventory"]["sha256"],
        "--expected-self-sha256",
        native_bootstrap["binary"]["sha256"],
    ]
    headless_module = _execute_module(
        "summary_relearn_headless",
        paths[HEADLESS_RELATIVE],
        compiled[HEADLESS_RELATIVE],
        {"AUTHENTICATED_LIBDESMUME_PATH": libdesmume_path},
    )
    party_module = _execute_module(
        "summary_relearn_party",
        paths[PARTY_RELATIVE],
        compiled[PARTY_RELATIVE],
        {
            "AUTHENTICATED_HEADLESS": headless_module,
            "AUTHENTICATED_LIBDESMUME_PATH": libdesmume_path,
            "AUTHENTICATED_NATIVE_PREFIX": tuple(native_prefix),
            "AUTHENTICATED_PYTHON_PATH": os.path.abspath(sys.executable),
            "AUTHENTICATED_CHILD_ENVIRONMENT": {
                "PATH": "/usr/bin:/bin",
                "LC_ALL": "C",
                "SDL_AUDIODRIVER": "dummy",
            },
        },
    )
    authentication = _authentication_record(
        manifest_record,
        rom_record,
        records,
        runtime_environment,
    )
    def reauthenticate():
        with open(manifest_path, "rb") as stream:
            _require(
                stream.read() == manifest_bytes,
                "publication manifest changed during runtime",
            )
        for relative, source in buffers.items():
            with open(paths[relative], "rb") as stream:
                _require(
                    stream.read() == source,
                    f"authenticated source changed during runtime: {relative}",
                )
        for relative, source in runtime_buffers.items():
            with open(runtime_paths[relative], "rb") as stream:
                _require(
                    stream.read() == source,
                    "authenticated runtime module changed during execution: "
                    + relative,
                )
        _require(
            _path_record(rom_path) == rom_record,
            "runtime ROM changed during execution",
        )
        manifest_module.verify_manifest(
            manifest_module.Path(manifest_path),
            manifest_module.Path(rom_path),
            require_bound_runtime=True,
        )
        _require(
            manifest_module.capture_runtime_environment()
            == runtime_environment,
            "runtime environment changed during execution",
        )
        _validate_loaded_native_closure(
            runtime_environment,
            manifest_module,
        )
        pil_loader.authenticate()
        _require(
            tuple(sys.path) == _stage_zero_expected_sys_path()
            and tuple(sys.path_hooks) == initial_path_hooks
            and tuple(sys.meta_path) == (pil_loader, *initial_meta_path),
            "runtime import path/finder closure changed during execution",
        )
        _authenticate_loaded_python_modules(
            runtime_environment,
            authenticated_module_paths,
        )
        _require(native_handle is not None, "sealed native handle was released")
        return json.loads(json.dumps(authentication))

    runtime_globals = {
        "__name__": "__main__",
        "__file__": paths[VERIFIER_RELATIVE],
        "__cached__": None,
        "__loader__": None,
        "__package__": "",
        "__spec__": None,
        "MANIFEST": manifest_module,
        "HEADLESS": headless_module,
        "PARTY": party_module,
        "BOOTSTRAP_AUTHENTICATION": json.loads(
            json.dumps(authentication)
        ),
        "BOOTSTRAP_REAUTHENTICATE": reauthenticate,
        "BOOTSTRAP_MANIFEST_PATH": manifest_path,
        "BOOTSTRAP_ROM_PATH": rom_path,
        "BOOTSTRAP_LAUNCHER_PATH": os.path.abspath(__file__),
        "BOOTSTRAP_LIBDESMUME_PATH": libdesmume_path,
        "BOOTSTRAP_PYTHON_PATH": os.path.abspath(sys.executable),
        "BOOTSTRAP_NATIVE_PREFIX": tuple(native_prefix),
        "BOOTSTRAP_CHILD_ENVIRONMENT": {
            "PATH": "/usr/bin:/bin",
            "LC_ALL": "C",
            "SDL_AUDIODRIVER": "dummy",
        },
        "BOOTSTRAP_INVALIDATED_RESULTS": EARLY_INVALIDATED_RESULTS,
    }
    exec(compiled[VERIFIER_RELATIVE], runtime_globals)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_late_main())
    except SystemExit:
        raise
    except Exception as error:
        print(
            f"Summary relearn runtime launcher failed: {error}",
            file=sys.stderr,
        )
        raise SystemExit(1)
