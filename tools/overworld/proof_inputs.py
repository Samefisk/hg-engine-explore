"""Scoped provenance, not acceptance: collector changes still require a new run.

Unknown inputs retain runs.py's broad product/build scope. Only explicit host
boundaries are removable, and a collector import always takes precedence.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
from pathlib import Path

from . import runs
from .validation import ValidationFailure

SCHEMA = "overworld-scoped-proof-inputs-v1"
ROOTS = (
    "scripts/overworld_devtools_worker.py",
    "tools/overworld/devtools_runtime.py",
    "tools/overworld/devtools_jobs.py",
    # Runtime loads this module by filename, not a Python import statement.
    "tools/overworld/devtools_native.py",
)
BOUNDARY = "tools/overworld/control.py"
REGISTRY = "tools/overworld/runtime_proof_registry.json"
HOST_ONLY = {BOUNDARY, "tools/overworld/proof_adapters.py",
             "tools/overworld/cadence_diagnostics.py",
             "tools/overworld/proof_inputs.py", "tools/overworld/proof_reuse.py"}
_CACHE = {}
_CACHE_LIMIT = 65536


def _facts(repo, relative):
    target = repo / relative
    try:
        own = target.lstat()
        link = os.readlink(target) if stat.S_ISLNK(own.st_mode) else None
        if link is not None and not target.resolve(strict=True).is_relative_to(repo):
            raise ValidationFailure(f"proof input symlink leaves repository: {relative}")
        def stat_key(value):
            return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
                    value.st_mtime_ns, value.st_ctime_ns)
        return (stat_key(own), stat_key(target.stat()), link)
    except OSError as error:
        raise ValidationFailure(f"proof input could not be read: {relative}: {error}") from error


def _record(repo, relative):
    """Stat-validated process-local reuse; never a persistent trust cache."""
    key = (str(repo), relative.as_posix())
    before = _facts(repo, relative)
    cached = _CACHE.get(key)
    record = cached[1] if cached and cached[0] == before else runs._input_record(repo, relative)
    after = _facts(repo, relative)
    if before != after:
        raise ValidationFailure(f"proof input changed during scan: {relative}")
    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.clear()
    _CACHE[key] = (after, record)
    return dict(record)


def _host_only(path: str) -> bool:
    p = Path(path)
    return (path in HOST_ONLY or p.name.startswith("test_") and p.suffix == ".py"
            and (path.startswith("tools/overworld/") or path.startswith("scripts/"))
            or path.startswith("tools/overworld/devtools_") and path.endswith("_proof.py")
            or path.startswith("tests/overworld/test-recipes/")
            or path.startswith("tests/overworld/scenarios/"))


def proof_inputs(repo: Path, test: dict) -> dict:
    """Hash one inventory once; callers should reuse this result within a check.

    ``test`` is the current validated recipe. Its value and its on-disk bytes
    are both bound, so an action change cannot reuse a prior capture.
    No fallback to an empty scope is permitted. Legacy callers keep using
    runs.source_record; this function does not reinterpret old manifests.
    """
    # Jobs receive validated recipes; recheck/history read the authored JSON.
    # Bind the same default-expanded actions in both paths. On-disk recipe
    # bytes remain a separate input, so this does not ignore authored changes.
    if "schemaVersion" in test:
        from .devtools_test_contract import validate_test
        test = validate_test(test)
    repo = Path(repo).resolve()
    paths = runs._input_paths(repo)
    if not paths:
        raise ValidationFailure("proof input inventory is empty")
    records = {p.as_posix(): _record(repo, p) for p in paths}

    def read(path):
        if path not in records:
            raise ValidationFailure(f"scoped proof input missing: {path}")
        data = (repo / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != records[path]["sha256"]:
            raise ValidationFailure(f"proof input changed during scan: {path}")
        return data

    # Resolve static local imports, including function-local imports and package
    # initializers. External libraries remain covered by broad lock/build files.
    closure = set()
    pending = list(ROOTS)

    def module(name, required=False):
        stem = name.replace(".", "/")
        candidates = [stem + ".py", stem + "/__init__.py"]
        found = next((p for p in candidates if p in records), None)
        if found:
            pending.append(found)
        elif required and not any(p.startswith(stem + "/") for p in records):
            raise ValidationFailure(f"scoped collector import missing: {name}")
        for i in range(1, len(name.split("."))):
            init = "/".join(name.split(".")[:i]) + "/__init__.py"
            if init in records:
                pending.append(init)

    while pending:
        path = pending.pop()
        if path == BOUNDARY or path in closure:
            continue
        closure.add(path)
        try:
            tree = ast.parse(read(path), filename=path)
        except (SyntaxError, UnicodeError) as error:
            raise ValidationFailure(f"scoped collector cannot parse: {path}") from error
        package = Path(path).parent.parts
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module(alias.name, alias.name.split(".")[0] in {"tools", "scripts"})
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    if node.level > len(package):
                        raise ValidationFailure(f"scoped collector invalid relative import: {path}")
                    parts = package[:len(package) - node.level + 1]
                    base = ".".join((*parts, *((node.module or "").split(".") if node.module else ())))
                else:
                    base = node.module or ""
                local = node.level or base.split(".")[0] in {"tools", "scripts"}
                module(base, bool(local))
                for alias in node.names:
                    if alias.name != "*":
                        module(base + "." + alias.name)

    test_id = test.get("id")
    if not isinstance(test_id, str) or not test_id or "/" in test_id or "\\" in test_id:
        raise ValidationFailure("scoped proof test id is invalid")
    recipe = f"tests/overworld/test-recipes/{test_id}.json"
    read(recipe)
    try:
        registry = json.loads(read(REGISTRY))
        shared = registry["sharedTests"][test_id]
        requirements = test["requirements"]
        if requirements != shared["requirements"]:
            raise ValueError("requirements differ")
        contracts = {key: registry.get("measurementContracts", {}).get(key)
                     for key in requirements}
        if any(value is None for value in contracts.values()) and not shared.get("measurementContract"):
            # Some existing contracts are implemented by the controller, not
            # a JSON measurement table. Use its exact registration validator;
            # never infer validity from an evaluator name. The full selected
            # registry entry, missing table values and controller source remain
            # checker inputs. This does not grant acceptance.
            from .control import _shared_test_registration
            validated, _ = _shared_test_registration(test, repo)
            if validated != shared:
                raise ValueError("measurement contract missing")
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationFailure("scoped proof registry binding is missing or differs") from error
    selection = {"sharedTests": {test_id: shared}, "measurementContracts": contracts,
                 **{name: {key: registry.get(name, {}).get(key) for key in requirements}
                    for name in ("runners", "runnerKinds")}}
    registry_record = {**records[REGISTRY], "sha256": runs.digest_value(selection),
                       "size": len(runs.canonical_bytes(selection)),
                       "selector": {"test": test_id, "requirements": requirements}}
    capture = [record for path, record in records.items()
               if path in closure or path == recipe or path != REGISTRY and not _host_only(path)]
    checker = [record for path, record in records.items()
               if path == recipe or path.startswith("tools/overworld/")
               and path.endswith(".py") and not Path(path).name.startswith("test_")]
    checker.append(registry_record)
    if runs._input_paths(repo) != paths:
        raise ValidationFailure("proof input path set changed during scan")

    def scope(files):
        files = sorted(files, key=lambda row: row["path"])
        groups = {}
        for record in files:
            groups.setdefault(Path(record["path"]).parts[0], []).append(record)
        roots = {name: {"sha256": runs.digest_value(rows), "fileCount": len(rows),
                        "byteCount": sum(row["size"] for row in rows)}
                 for name, rows in sorted(groups.items())}
        return {"sha256": runs.digest_value({"files": files, "recipe": test}),
                "roots": roots, "fileCount": len(files),
                "byteCount": sum(row["size"] for row in files)}

    return {"schema": SCHEMA, "capture": scope(capture), "checker": scope(checker)}
