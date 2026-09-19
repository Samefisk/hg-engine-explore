#!/usr/bin/env python3
"""Plan, then remove only verified duplicate ROMs from stopped devtools sessions.

Saves, manifests and evidence are never changed. No symlinks are installed:
the durable plan maps each removed historical path to its identical keeper.
Reported bytes are logical bytes, not an APFS space-reclaim estimate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "build/overworld-devtools"
EXCLUDED = {"session-_26__tej"}  # Stale ready manifest; never infer stopped state.


def digest(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"not a regular file: {path}")
        hasher = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
        value = hasher.hexdigest()
        after = os.fstat(stream.fileno())
    current = path.lstat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if stamp(before) != stamp(after) or stamp(after) != stamp(current):
        raise ValueError(f"file changed while hashing: {path}")
    return value, after.st_size


def candidate(root, directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("session is not a real directory")
    if not re.fullmatch(r"session-[A-Za-z0-9_-]+", directory.name):
        raise ValueError("unexpected session name")
    manifest = directory / "session.json"
    manifest_hash, _ = digest(manifest)
    data = json.loads(manifest.read_text())
    if digest(manifest)[0] != manifest_hash:
        raise ValueError("manifest changed")
    if data.get("state") != "stopped":
        raise ValueError("session is not stopped")
    if data.get("id") != directory.name or data.get("directory") != str(directory):
        raise ValueError("session identity/directory mismatch")
    identity = data.get("identity", {})
    if identity.get("sessionId") != directory.name:
        raise ValueError("identity session mismatch")
    rom = identity.get("rom", {})
    target = directory / "game.nds"
    if rom.get("copy") != str(target) or target.resolve() != target:
        raise ValueError("ROM copy path mismatch or symlink")
    if type(rom.get("size")) is not int or rom["size"] <= 0:
        raise ValueError("invalid ROM size")
    if not re.fullmatch(r"[0-9a-f]{64}", str(rom.get("sha256", ""))):
        raise ValueError("invalid ROM hash")
    value, size = digest(target)
    if (value, size) != (rom["sha256"], rom["size"]):
        raise ValueError("ROM bytes do not match manifest")
    return {"path": str(target), "sha256": value, "size": size,
            "manifestSha256": manifest_hash}


def make_plan(root):
    root = Path(root)
    if root != root.resolve() or not root.is_dir():
        raise ValueError("root must be an existing canonical directory")
    groups, skipped = {}, []
    for directory in sorted(root.glob("session-*")):
        try:
            if directory.name in EXCLUDED:
                raise ValueError("explicitly excluded stale session")
            item = candidate(root, directory)
            groups.setdefault((item["sha256"], item["size"]), []).append(item)
        except (OSError, ValueError, KeyError, TypeError) as error:
            skipped.append({"path": str(directory), "reason": str(error)})
    keepers, removals = [], []
    for _, items in sorted(groups.items()):
        keepers.append(items[0])
        removals.extend({**item, "keeper": items[0]["path"]} for item in items[1:])
    if not keepers:
        raise ValueError("no verified session ROMs found")
    return {"schemaVersion": 1, "root": str(root), "keepers": keepers,
            "removals": removals, "skipped": skipped,
            "logicalBytesToRemove": sum(item["size"] for item in removals)}


def shared_status():
    result = {}
    for name, args in (("session", ["status"]), ("job", ["test", "status"])):
        run = subprocess.run([str(REPO / "scripts/owctl"), "dev", *args,
                              "--json", "--summary"], capture_output=True,
                             text=True, timeout=30)
        data = json.loads(run.stdout)
        if run.returncode or data.get("ok") is not True:
            raise ValueError("shared status unavailable")
        body = data.get("session") if name == "session" else data.get("result")
        if name == "session":
            snapshot = data.get("result", {})
            if snapshot.get("playing") is not False or snapshot.get("recording") is not False:
                raise ValueError("shared service is playing, recording, or unknown")
            if "session" in data and body is None:
                result[name] = {"state": "idle", "id": None}
                continue
        if not isinstance(body, dict):
            raise ValueError("shared status has unknown shape")
        result[name] = {k: body.get(k) for k in ("id", "state", "phase", "sessionId")}
        if name == "session" and body.get("state") != "stopped":
            raise ValueError("shared session is live or unknown")
        if name == "job" and body == {"state": "idle", "execution": "shared-devtools", "acceptedProof": False}:
            continue
        if name == "job" and (body.get("state") not in {"failed", "completed", "canceled"}
                              or body.get("phase") != "terminal"):
            raise ValueError("shared job is live or unknown")
    return result


def write_new(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def apply_plan(plan, journal_path, status_check=shared_status):
    root = Path(plan["root"])
    status_check()
    fresh = make_plan(root)  # Hash every candidate again; refuse a changed plan.
    if fresh != plan or not plan["removals"]:
        raise ValueError("plan changed or has no duplicates; create and review a new plan")
    keepers = {item["path"]: item for item in plan["keepers"]}
    # Exclusive durable journal must succeed before any unlink. It contains the
    # entire reviewed mapping even if a later disk write fails.
    write_new(journal_path, {"operation": "apply-intent", "plan": plan})
    removed = []
    for item in plan["removals"]:
        status_check()
        keeper = keepers[item["keeper"]]
        if candidate(root, Path(keeper["path"]).parent) != keeper:
            raise ValueError("keeper changed")
        expected = {k: v for k, v in item.items() if k != "keeper"}
        if candidate(root, Path(item["path"]).parent) != expected:
            raise ValueError("duplicate changed")
        Path(item["path"]).unlink()  # One exact validated regular game.nds only.
        removed.append(item["path"])
    return {"removed": removed, "keeperCount": len(keepers),
            "logicalBytesRemoved": plan["logicalBytesToRemove"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dry = sub.add_parser("plan")
    dry.add_argument("--report", type=Path, required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--journal", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "plan":
        status = shared_status()
        plan = make_plan(ROOT)
        write_new(args.report, plan)
        print(json.dumps({"report": str(args.report.resolve()), "status": status,
                          "keepers": len(plan["keepers"]), "duplicates": len(plan["removals"]),
                          "skipped": len(plan["skipped"]),
                          "logicalBytesToRemove": plan["logicalBytesToRemove"]}))
    else:
        plan = json.loads(args.plan.read_text())
        if plan.get("root") != str(ROOT):
            raise ValueError("plan does not target this repository's session root")
        print(json.dumps(apply_plan(plan, args.journal)))


if __name__ == "__main__":
    main()
