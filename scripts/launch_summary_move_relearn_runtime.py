#!/usr/bin/env python3
"""Authenticate retained runtime sources before executing Summary acceptance."""

import sys


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


if (
    __name__ == "__main__"
    and (
        not sys.dont_write_bytecode
        or sys.pycache_prefix != "/dev/null"
        or sys.flags.no_site != 1
        or "site" in sys.modules
    )
):
    stage_zero_failures = _stage_zero_invalidate_results(sys.argv[1:])
    print(
        "Summary relearn runtime launcher failed: start Python with "
        "-S -B and PYTHONPYCACHEPREFIX=/dev/null"
        + (
            "; stale-result invalidation failed: "
            + "; ".join(stage_zero_failures)
            if stage_zero_failures
            else ""
        ),
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
    if os.path.isfile(python):
        os.execv(
            python,
            [python, "-S", "-B", os.path.abspath(__file__), *sys.argv[1:]],
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


def _primitive_runtime_authentication(document):
    runtime = _runtime_environment(document)
    _require(
        set(runtime)
        == {
            "schema",
            "status",
            "platform",
            "python",
            "packages",
            "modules",
            "native",
        },
        "runtime environment field set differs",
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
            "no_site",
            "pycache_prefix",
            "scope",
        }
        and {
            key: value
            for key, value in bytecode_policy.items()
            if key != "absent_zip_paths"
        }
        == {
            "bytecode_reads_disabled": True,
            "dont_write_bytecode": True,
            "no_site": True,
            "pycache_prefix": "/dev/null",
            "scope": (
                "Interpreter startup and every acceptance child skip "
                "site/.pth processing and compile Python sources without "
                "reading or writing filesystem pyc."
            ),
        }
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and sys.flags.no_site == 1
        and "site" not in sys.modules
        and os.stat("/dev/null").st_mode & 0o170000 == 0o020000,
        "runtime Python bytecode-bypass policy differs",
    )
    current_zip_paths = sorted(
        os.path.abspath(entry)
        for entry in sys.path
        if isinstance(entry, str) and entry.endswith(".zip")
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
    module.__loader__ = None
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
