"""Bounded, process-local reuse of independently checked proof.

No disk verdict is trusted. A hit needs the same recipe, inputs, manifest and
all referenced artifact bytes. A new process replays once. Failed results are
never cached; the cache stores no ROM, observation stream or mutable caller data.
"""
from collections import OrderedDict
from copy import deepcopy
import json
from pathlib import Path
from threading import RLock

from .runs import digest_value, file_record, OVERWORLD_LINKED_OUTPUTS
from .validation import ValidationFailure
from .devtools_manifest_limits import MANIFEST_MAX_BYTES


class AcceptanceCache:
    def __init__(self, capacity=32):
        self.capacity = capacity
        self.values = OrderedDict()
        self.lock = RLock()

    def get(self, key):
        with self.lock:
            if key not in self.values:
                return None
            self.values.move_to_end(key)
            return deepcopy(self.values[key])

    def put(self, key, result):
        if result.get("acceptedProof") is not True or result.get("passed") is not True:
            return
        with self.lock:
            self.values[key] = deepcopy(result)
            self.values.move_to_end(key)
            while len(self.values) > self.capacity:
                self.values.popitem(last=False)


def acceptance_key(repo, test, record, inputs, *, inputs_for=None):
    """Rehash owned artifacts including separate recorder data before a hit.

Current linked objects matter to native ABI oracles even if ROM is unchanged.
The complete input record binds native transport and product/build sources.
No trust is placed in acceptedProof or a user-editable cache file.
"""
    root = Path(repo).resolve()
    owned = root / "build/overworld-devtools"
    artifacts = {}
    dependencies = {}
    visiting = set()

    def visit(value, depth=0):
        if depth > 12:
            raise ValidationFailure("proof artifact dependencies exceed depth limit")
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                path = Path(value["path"])
                path = path if path.is_absolute() else root / path
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValidationFailure("proof dependency leaves repository or is a symlink")
                path = path.resolve()
                # Only owned evidence and tested fixture files are consumed.
                # Other historical file records are bound by record/input hash.
                if path.resolve().is_relative_to(owned) or path == root / "test.nds" \
                        or path == root / "build/overworld-system.debug.json" \
                        or any(path == root / test["fixture"].get(k, "") for k in ("rom", "save")):
                    actual = file_record(path, root)
                    if actual["sha256"] != value["sha256"] or (
                            "size" in value and actual["size"] != value["size"]):
                        raise ValidationFailure("proof dependency hash/size differs: " + str(path.relative_to(root)))
                    artifacts[str(path.relative_to(root))] = actual
                    if path.name == "manifest.json":
                        if path in visiting:
                            raise ValidationFailure("cyclic proof artifact dependency")
                        if actual["size"] > MANIFEST_MAX_BYTES:
                            raise ValidationFailure("proof dependency manifest exceeds limit")
                        visiting.add(path)
                        child = json.loads(path.read_text())
                        name = child.get("test")
                        if not isinstance(name, str) or Path(name).name != name:
                            raise ValidationFailure("proof dependency test identity differs")
                        recipe_path = root / "tests/overworld/test-recipes" / (name + ".json")
                        recipe = json.loads(recipe_path.read_text())
                        if inputs_for is None:
                            from .proof_inputs import proof_inputs
                            child_inputs = proof_inputs(root, recipe)
                        else:
                            child_inputs = inputs_for(root, recipe)
                        dependencies[str(path)] = child_inputs
                        visit({k: v for k, v in child.items()
                               if k not in ("proofAcceptance", "acceptedProof")}, depth + 1)
                        visiting.remove(path)
            for item in value.values():
                visit(item, depth)
        elif isinstance(value, list):
            for item in value:
                visit(item, depth)

    # Do not descend through old acceptance summaries (these repeat dependencies).
    core = {k: v for k, v in record.items() if k not in ("proofAcceptance", "acceptedProof")}
    visit(core)
    for _, relative in OVERWORLD_LINKED_OUTPUTS:
        path = root / relative
        if path.exists():
            artifacts[str(relative)] = file_record(path, root)
    return digest_value({"repo": str(root), "test": test, "record": core,
                         "inputs": inputs, "artifacts": artifacts, "dependencies": dependencies})


ACCEPTANCE_CACHE = AcceptanceCache()


class RecorderIndex:
    """Small in-memory requirement index; stat changes invalidate parsed entries.

    Selection is a hint only. The controller always hashes/rechecks the selected
    manifest and its evidence. No unchanged manifest is parsed on each lookup.
    """
    def __init__(self):
        self.entries = {}
        self.lock = RLock()

    def candidates(self, directory, requirement, check_budget):
        import os
        directory = Path(directory)
        found, live = [], set()
        with self.lock, os.scandir(directory) as entries:
            for count, entry in enumerate(entries):
                check_budget()
                if count >= 4096:
                    raise ValidationFailure("shared run inventory exceeds bounded control lookup")
                if not entry.name.startswith("test-") or not entry.is_dir(follow_symlinks=False):
                    continue
                path = Path(entry.path) / "manifest.json"
                if path.is_symlink() or not path.is_file():
                    continue
                info = path.stat()
                if info.st_size > MANIFEST_MAX_BYTES:
                    continue
                fingerprint = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                live.add(path)
                cached = self.entries.get(path)
                if cached is None or cached[0] != fingerprint:
                    try:
                        document = json.loads(path.read_text())
                        proof = document.get("proofAcceptance", {})
                        requirements = proof.get("requirements", []) if isinstance(proof, dict) else []
                        requirements = requirements if isinstance(requirements, list) else []
                        accepted = document.get("passed") is True and document.get("acceptedProof") is True
                    except (OSError, ValueError, AttributeError):
                        requirements, accepted = [], False
                    cached = (fingerprint, requirements, accepted)
                    self.entries[path] = cached
                if cached[2] and cached[1] == [requirement]:
                    found.append((info.st_mtime_ns, path))
            self.entries = {p: e for p, e in self.entries.items() if p in live}
        return [p for _, p in sorted(found, reverse=True)[:64]]


RECORDER_INDEX = RecorderIndex()
