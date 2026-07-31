#!/usr/bin/env python3
"""Authenticate retained runtime sources before executing Summary acceptance."""

import os
import sys


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
        path = os.path.abspath(target)
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
    if os.path.realpath(sys.prefix) == os.path.realpath(venv):
        return
    if os.path.isfile(python):
        os.execv(python, [python, os.path.abspath(__file__), *sys.argv[1:]])


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
        == {"build_context", "inputs", "outputs", "schema", "tools"},
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


def _execute_module(name, path, code, injected=None):
    module = types.ModuleType(name)
    module.__file__ = path
    module.__cached__ = None
    module.__loader__ = None
    module.__package__ = ""
    module.__spec__ = None
    if injected:
        module.__dict__.update(injected)
    sys.modules[name] = module
    exec(code, module.__dict__)
    return module


def _authentication_record(
    manifest_record,
    rom_record,
    records,
):
    return {
        "schema": "summary-move-relearn-runtime-artifact-v2",
        "rom": dict(rom_record),
        "publication_manifest": dict(manifest_record),
        "runtime_launcher": dict(records[LAUNCHER_RELATIVE]),
        "runtime_verifier": dict(records[VERIFIER_RELATIVE]),
        "manifest_helper": dict(records[MANIFEST_HELPER_RELATIVE]),
        "runtime_helpers": {
            HEADLESS_RELATIVE: dict(records[HEADLESS_RELATIVE]),
            PARTY_RELATIVE: dict(records[PARTY_RELATIVE]),
        },
        "authenticated_at_start_and_end": True,
        "executed_from_retained_source_buffers": True,
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
    compiled = _compile_buffers(buffers, paths)

    manifest_module = _execute_module(
        "summary_relearn_manifest",
        paths[MANIFEST_HELPER_RELATIVE],
        compiled[MANIFEST_HELPER_RELATIVE],
    )
    manifest_module.verify_manifest(
        manifest_module.Path(manifest_path),
        manifest_module.Path(rom_path),
    )
    headless_module = _execute_module(
        "summary_relearn_headless",
        paths[HEADLESS_RELATIVE],
        compiled[HEADLESS_RELATIVE],
    )
    party_module = _execute_module(
        "summary_relearn_party",
        paths[PARTY_RELATIVE],
        compiled[PARTY_RELATIVE],
        {"AUTHENTICATED_HEADLESS": headless_module},
    )
    authentication = _authentication_record(
        manifest_record,
        rom_record,
        records,
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
        _require(
            _path_record(rom_path) == rom_record,
            "runtime ROM changed during execution",
        )
        manifest_module.verify_manifest(
            manifest_module.Path(manifest_path),
            manifest_module.Path(rom_path),
        )
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
