"""Versioned, data-only commands shared by Workshop, owctl and recipes."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def source_paths(root):
    """One input set for service freshness and run identity, including new tools."""
    root = Path(root)
    explicit = ("scripts/overworld_devtools_worker.py", "scripts/verify_overworld_runtime_fixture.py",
                "tools/overworld/control.py", "tools/overworld/validation.py", "tools/overworld/runs.py",
                "tools/overworld/actor_probe.py", "tools/overworld/behavior_schema.json",
                "tools/overworld/spawn_identity.py", "tools/overworld/normal_play_observer.py",
                "tools/overworld/runtime_cadence.py",
                "tools/overworld/melonds_backend.py", "build/melonds/manifest.json",
                "build/melonds/" + ("libow_melonds.dylib" if sys.platform == "darwin" else "libow_melonds.so"),
                "tools/overworld/runtime_proof_registry.json")
    return tuple(sorted({*explicit, *(path.relative_to(root).as_posix()
                                    for path in (root / "tools/overworld").glob("*.py")
                                    if not path.name.startswith("test_")),
                         *(path.relative_to(root).as_posix()
                           for path in (root / "tools/overworld/melonds_native").glob("*")
                           if path.suffix in (".cpp", ".h", ".py", ".txt"))}))

KEYS = ("A", "B", "X", "Y", "START", "SELECT", "UP", "DOWN", "LEFT", "RIGHT", "L", "R")
PREPARED_OPS = frozenset({"teleport", "spawn", "party", "resolver.probe", "condition.probe", "actor-inspect.probe", "walk-policy.reset", "mount-walk.configure", "mount-teleport.configure", "walk-corner.probe", "walk-corner.arm", "walk-corner.close", "walk-corner.calibrate", "walk-matrix.arm", "walk-matrix.close", "walk-matrix.calibrate", "walk-intent.arm", "walk-intent.close", "walk-policy-control.arm", "walk-policy-control.close", "mount-pacing.arm", "mount-pacing.close", "mount-pacing.calibrate", "wild-walk.arm", "wild-walk.close", "wild-walk.calibrate"})
PREPARED_OPS = PREPARED_OPS | {"stomp.arm", "stomp.close", "stomp.calibrate"}
PREPARED_OPS = PREPARED_OPS | {"crash.arm", "crash.close", "crash.calibrate"}
PREPARED_OPS = PREPARED_OPS | {"hop-candidate.probe", "hop-arc.arm", "hop-arc.close"}
PREPARED_OPS = PREPARED_OPS | {"wild-ledge.arm", "wild-ledge.close"}
PREPARED_OPS = PREPARED_OPS | {"mount-teleport.restore"}
PREPARED_OPS = PREPARED_OPS | {"obstacle-intent.arm", "obstacle-intent.close"}
PREPARED_OPS = PREPARED_OPS | {
    "condition-controller.fixture",
    "condition-controller.arm",
    "condition-controller.close",
}


def integer(low, high, default=None, required=False):
    value = {"type": "integer", "minimum": low, "maximum": high}
    if default is not None:
        value["default"] = default
    if required:
        value["required"] = True
    return value


def string(default=None, required=False, enum=None):
    value = {"type": "string", "maxLength": 512}
    if default is not None:
        value["default"] = default
    if required:
        value["required"] = True
    if enum:
        value["enum"] = enum
    return value


OPERATIONS = {
    "help": {}, "status": {}, "stop": {}, "reset": {}, "play": {}, "pause": {},
    "catalog": {"kind": string(required=True, enum=["species", "maps", "moves"]),
                "query": string(), "limit": integer(1, 100, 30)},
    "start": {"rom": string("test.nds"), "save": string("test.sav"),
              "mode": string("normal", enum=["normal", "prepared"])},
    "inspect": {"handle": integer(1, 0xffffffff)},
    "explain": {"handle": integer(1, 0xffffffff, required=True)},
    "checkpoint": {}, "compare": {"left": string(required=True), "right": string(required=True)},
    "events": {"handle": integer(1, 0xffffffff), "limit": integer(1, 120, 30)},
    "step": {"frames": integer(1, 600, 1), "keys": {"type": "array", "items": "key", "default": []}},
    "capture": {}, "diagnostics": {},
    "snapshot.probe": {"iterations": integer(1, 256, 128)},
    "spawn-cost.probe": {"mode": string("baseline", enum=["baseline"])},
    "main-loop-pacing.arm": {"maxFrames": integer(2, 5000, required=True)},
    "cpu-work.start": {"maxNativeFrames": integer(1, 1200, 600)},
    "cpu-work.read": {},
    "resolver.probe": {},
    "condition.probe": {},
    "actor-inspect.probe": {"handle": integer(1, 0xffffffff, required=True)},
    "walk-policy.reset": {"subject": {"type": "object", "required": True}},
    "mount-walk.configure": {"subject": {"type": "object", "required": True},
                             "directionMode": integer(0, 2, required=True),
                             "travelTime": integer(1, 32),
                             "stompTime": integer(0, 32),
                             "turning": string(enum=["free", "locked"]),
                             "crashSound": string(enum=["none", "wall-hit"])},
    "mount-teleport.restore": {"subject": {"type": "object", "required": True}},
    "mount-teleport.configure": {"subject": {"type": "object", "required": True},
                                 "locomotion": integer(6, 11, required=True),
                                 "teleportTime": integer(1, 32, required=True),
                                 "teleportPause": integer(0, 255, required=True)},
    "walk-corner.arm": {"subject": {"type": "object", "required": True},
                        "maxFrames": integer(1, 600, required=True)},
    "walk-corner.close": {},
    "walk-corner.calibrate": {},
    "walk-corner.probe": {"subject": {"type": "object", "required": True}},
    "walk-matrix.arm": {"subject": {"type": "object", "required": True},
                        "maxFrames": integer(1, 4096, required=True)},
    "walk-matrix.close": {},
    "walk-matrix.calibrate": {},
    "stomp.arm": {"subject": {"type": "object", "required": True},
                  "maxFrames": integer(1, 3000, required=True)},
    "stomp.close": {},
    "stomp.calibrate": {},
    "crash.arm": {"subject": {"type": "object", "required": True},
                  "maxFrames": integer(1, 600, required=True)},
    "crash.close": {},
    "crash.calibrate": {},
    "walk-intent.arm": {"subject": {"type": "object", "required": True},
                        "direction": integer(0, 7, required=True),
                        "maxFrames": integer(1, 600, required=True)},
    "walk-intent.close": {},
    "obstacle-intent.arm": {"subject": {"type": "object", "required": True},
                            "maxFrames": integer(1, 120, required=True)},
    "obstacle-intent.close": {},
    "walk-policy-control.arm": {"subject": {"type": "object", "required": True}},
    "walk-policy-control.close": {},
    "mount-pacing.arm": {"subject": {"type": "object", "required": True},
                         "maxFrames": integer(1, 1200, required=True)},
    "mount-pacing.close": {},
    "mount-pacing.calibrate": {},
    "hop-arc.arm": {"subject": {"type": "object", "required": True},
                     "maxFrames": integer(1, 4000, required=True)},
    "hop-arc.close": {},
    "hop-candidate.probe": {"subject": {"type": "object", "required": True}},
    "wild-walk.arm": {"subject": {"type": "object", "required": True},
                      "maxFrames": integer(1, 1200, required=True)},
    "wild-walk.close": {},
    "wild-walk.calibrate": {},
    "wild-ledge.arm": {"subject": {"type": "object", "required": True},
                       "maxFrames": integer(1, 1200, required=True)},
    "wild-ledge.close": {},
    "condition-controller.fixture": {},
    "condition-controller.arm": {
        "subject": {"type": "object", "required": True},
        "maxFrames": integer(1, 600, required=True),
    },
    "condition-controller.close": {},
    "terrain": {"radius": integer(0, 12, 6), "x": integer(0, 32767), "z": integer(0, 32767)},
    "test.list": {}, "test.validate": {"test": {"type": "object", "required": True}},
    "test.save": {"name": string(required=True), "test": {"type": "object", "required": True}},
    "test.start": {"name": string(required=True)},
    "test.status": {"runId": string()}, "test.cancel": {"runId": string(required=True)},
    "test.export": {"runId": string(required=True)},
    "teleport": {"map": integer(0, 539, required=True),
                 "x": integer(0, 32767, required=True), "z": integer(0, 32767, required=True),
                 "facing": integer(0, 3, 1)},
    "spawn": {"species": integer(1, 1075, required=True), "form": integer(0, 31, 0),
              "role": string("wild", enum=["wild", "follower", "mounted"]),
              "releaseDiagnostics": string(enum=["write", "irq"]),
              "profileDiagnostics": string(enum=["owner-transfer", "owner-transfer-control"]),
              "slot": integer(0, 5), "x": integer(0, 32767), "z": integer(0, 32767),
              "level": integer(1, 100, 5)},
    "party": {"slot": integer(0, 5, required=True), "species": integer(1, 1075), "form": integer(0, 31),
              "level": integer(1, 100), "hp": integer(0, 65535), "status": integer(0, 255),
              "personality": integer(1, 0xFFFFFFFF),
              "moves": {"type": "array", "items": "move", "itemMinimum": 0, "itemMaximum": 922,
                        "minItems": 4, "maxItems": 4}},
    "record.start": {"maxFrames": integer(60, 65535, 1800), "maxEvents": integer(100, 4000, 4000)},
    "record.stop": {}, "recording.export": {},
    "scenario.draft": {"name": string(required=True), "expectation": string(required=True),
                       "subject": {"type": "object"}},
    "recipe.save": {"name": string(required=True), "recipe": {"type": "object"}},
    "recipe.load": {"name": string(required=True)}, "recipe.list": {},
}


def validate_command(op, args=None):
    """Reject unknown fields, coercions and unbounded work before any side effect."""
    if not isinstance(op, str) or op not in OPERATIONS:
        raise ValueError("unknown operation; use help")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValueError("args must be an object")
    fields = OPERATIONS[op]
    extra = set(args) - set(fields)
    if extra:
        raise ValueError("unknown arguments: " + ", ".join(sorted(extra)))
    result = {}
    for name, spec in fields.items():
        if name not in args:
            if spec.get("required"):
                raise ValueError(f"{name} is required")
            if "default" not in spec:
                continue
            value = spec["default"]
        else:
            value = args[name]
        kind = spec["type"]
        if kind == "integer":
            if type(value) is not int or not spec["minimum"] <= value <= spec["maximum"]:
                raise ValueError(f"{name} must be an integer in {spec['minimum']}..{spec['maximum']}")
        elif kind == "string":
            if not isinstance(value, str) or not value.strip() or len(value) > spec["maxLength"]:
                raise ValueError(f"{name} must be nonempty text, at most {spec['maxLength']} characters")
            if "enum" in spec and value not in spec["enum"]:
                raise ValueError(f"{name} must be one of {spec['enum']}")
        elif kind == "array":
            if not isinstance(value, list):
                raise ValueError(f"{name} must be an array")
            if spec["items"] == "key":
                if len(value) > len(KEYS) or any(k not in KEYS for k in value) or len(set(value)) != len(value):
                    raise ValueError(f"keys must be distinct DS keys: {KEYS}")
                if {"UP", "DOWN"} <= set(value) or {"LEFT", "RIGHT"} <= set(value):
                    raise ValueError("opposed direction keys are not allowed")
            elif len(value) != 4 or any(type(m) is not int or not spec["itemMinimum"] <= m <= spec["itemMaximum"] for m in value):
                raise ValueError(f"moves must contain four integer move IDs in {spec['itemMinimum']}..{spec['itemMaximum']}")
            value = list(value)
        elif not isinstance(value, dict):
            raise ValueError(f"{name} must be an object")
        result[name] = value
    if "name" in result and (not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", result["name"])
                             or ".." in result["name"]):
        raise ValueError("name must use 1..64 lowercase letters, digits, dot, dash or underscore; no double dots")
    if op == "party" and len(result) == 1:
        raise ValueError("party needs at least one field to change")
    if op in ("walk-policy.reset", "mount-walk.configure", "mount-teleport.configure", "mount-teleport.restore", "walk-corner.probe", "walk-corner.arm", "walk-matrix.arm", "stomp.arm", "crash.arm", "walk-intent.arm", "obstacle-intent.arm", "walk-policy-control.arm", "mount-pacing.arm", "hop-arc.arm", "wild-walk.arm", "wild-ledge.arm", "condition-controller.arm"):
        # Import here: records uses this module's prepared-operation catalog.
        from tools.overworld.devtools_records import _subject, _copy_json, GENERATION_FIELDS
        selected = result["subject"]
        _subject(selected)
        if selected["role"] not in ("WILD", "MOUNTED") or any(
                type(selected.get(key)) is not int or not 1 <= selected[key] <= 0xffffffff
                for key in GENERATION_FIELDS):
            raise ValueError("Walk reset needs a Wild or Mounted subject with all current generations")
        result["subject"] = _copy_json(selected, 8192)
        if op == "mount-walk.configure" and selected["role"] != "MOUNTED":
            raise ValueError("Mount Walk setup requires a Mounted subject")
        if op == "mount-teleport.restore" and selected["role"] != "MOUNTED":
            raise ValueError("Mount Teleport restore requires a Mounted subject")
        if op == "mount-teleport.configure" and (
                selected["role"] != "MOUNTED"
                or result["locomotion"] not in (6, 9, 10, 11)):
            raise ValueError("Mount Teleport setup requires a Mounted subject and locomotion 6, 9, 10 or 11")
        if op in ("walk-corner.arm", "walk-corner.probe") and (selected["role"] != "MOUNTED" or selected["species"] != 155):
            raise ValueError("Walk corner reader requires Mounted Cyndaquil")
        if op == "walk-matrix.arm" and (selected["role"] != "MOUNTED" or selected["species"] != 155):
            raise ValueError("Walk matrix reader requires Mounted Cyndaquil")
        if op == "stomp.arm" and (selected["role"] != "MOUNTED" or selected["species"] != 155):
            raise ValueError("Stomp reader requires Mounted Cyndaquil")
        if op == "crash.arm" and (selected["role"] != "MOUNTED" or selected["species"] != 155):
            raise ValueError("Crash reader requires Mounted Cyndaquil")
        if op == "walk-intent.arm" and selected["role"] != "WILD":
            raise ValueError("Walk intent requires a Wild subject")
        if op == "obstacle-intent.arm" and (selected["role"] != "WILD" or selected["species"] != 234):
            raise ValueError("Obstacle intent requires a Wild Stantler")
        if op == "mount-pacing.arm" and selected["role"] != "MOUNTED":
            raise ValueError("Mount pacing requires a Mounted subject")
        if op == "hop-arc.arm" and (selected["role"] != "MOUNTED" or selected["species"] != 56):
            raise ValueError("Hop arc requires Mounted Mankey")
        if op == "wild-walk.arm" and (selected["role"] != "WILD" or selected["species"] != 19):
            raise ValueError("Wild Walk requires a Wild Rattata subject")
        if op == "wild-ledge.arm" and (selected["role"] != "WILD" or selected["species"] != 35):
            raise ValueError("Wild ledge requires a Wild Clefairy subject")
    if op in ("spawn", "terrain") and (("x" in result) != ("z" in result)):
        raise ValueError(op + " x and z must be supplied together")
    if op == "spawn" and result["role"] == "wild" and "releaseDiagnostics" in result:
        raise ValueError("releaseDiagnostics applies only to follower/mounted spawn")
    if op == "spawn" and result["role"] == "wild" and "profileDiagnostics" in result:
        raise ValueError("profileDiagnostics applies only to follower/mounted spawn")
    if op == "spawn" and result.get("profileDiagnostics") == "owner-transfer-control" and result["role"] != "mounted":
        raise ValueError("owner-transfer-control requires mounted setup")
    return result


def command_help():
    return {"schemaVersion": 1, "operations": OPERATIONS, "keys": list(KEYS),
            "preparedOperations": sorted(PREPARED_OPS),
            "notes": ["Session copies protect your ROM and save.",
                      "Screenshots are human-view only, never test proof. Use terrain with x, z and radius 0 for one live loaded tile; unknown is not passable, and tile attributes alone do not prove tree/roof height.",
                      "spawn form, level, x and z apply to wild actors. Follower/mounted spawn uses the selected party slot's existing data; use party to change it first.",
                      "Setup commands permanently mark this session prepared, even if they fail.",
                      "Reset boots a new process from the source save.",
                      "Recordings and drafts are diagnostic, not accepted runtime proof.",
                      "Use requestId to retry a request without repeating its action."]}
