#!/usr/bin/env python3
"""Live tool smoke, not accepted gameplay proof. Uses the shared Workshop API.

Refuses an existing live session. Every source input is copied by the service.
Run explicitly after tool changes; the host suite does not boot this script.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from tools.overworld.devtools_cli import request
from tools.overworld.devtools_records import select_current_actor


def sha(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()


def load_json_artifact(path):
    path = Path(path)
    data = path.read_bytes()
    if path.suffix == ".gz":
        data = gzip.decompress(data)
    return json.loads(data)


def run(args):
    report = {"schemaVersion": 1, "acceptedProof": False,
              "scope": "development tool operations, not game behavior", "passed": False,
              "checks": [], "responses": []}
    session_id = None
    before = {str(path): sha(path) for path in (args.rom, args.save)}

    def call(op, values=None, *, expect_ok=True, request_id=None, timeout=120):
        envelope = {"op": op, "args": values or {}}
        if request_id:
            envelope["requestId"] = request_id
        response = request(args.url, envelope, timeout=timeout)
        report["responses"].append({"op": op, "args": values or {}, "response": response})
        if expect_ok and not response["ok"]:
            raise AssertionError(f"{op}: {response.get('error')}")
        return response

    def check(name, condition):
        report["checks"].append({"name": name, "passed": bool(condition)})
        if not condition:
            raise AssertionError(name)

    try:
        current = call("status").get("session")
        check("does not take over an existing session", not current or current["state"] in ("stopped", "failed"))
        started = call("start", {"rom": str(args.rom), "save": str(args.save), "mode": "normal"})
        session_id = started["session"]["id"]
        report["sourceIdentity"] = started["session"]["identity"]
        initial = call("inspect")["result"]
        check("loaded party is present and verified", bool(initial["party"]) and all(mon["identityVerified"] for mon in initial["party"]))
        check("party read matches native getters", len(initial["partyObservation"]["nativeGetterChecks"]) >= len(initial["party"]) * 3)
        terrain = call("terrain", {"radius": 2})["result"]["terrain"]
        check("terrain returns the requested grid", len(terrain["cells"]) == 25 and any(c["loaded"] for c in terrain["cells"]))
        absent = call("inspect", {"handle": 0xffffffff}, expect_ok=False)
        check("missing actor is rejected", not absent["ok"] and absent["error"]["code"] == "actor-not-present")
        call("record.start", {"maxFrames": 120, "maxEvents": 1000})
        step_id = str(uuid.uuid4())
        stepped = call("step", {"frames": 12}, request_id=step_id)
        replay = call("step", {"frames": 12}, request_id=step_id)
        check("retry cannot repeat game input", replay == stepped)
        check("step advances exactly twelve observed game frames",
              stepped["result"]["operation"].get("completedGameFrames") == 12 and
              stepped["result"]["operation"].get("observedFieldFrames") == 12)
        call("record.stop")
        record = call("recording.export")["result"]
        check("recording stays diagnostic", record["recording"]["acceptedProof"] is False)
        draft = call("scenario.draft", {"name": "devtools-live-smoke", "expectation": "Tool setup reaches the requested actor and location."})["result"]["draft"]
        check("draft cannot claim gameplay success", draft["acceptedProof"] is False and draft["verificationStatus"] == "unverified")
        call("record.start", {"maxFrames": 1800, "maxEvents": 4000})
        # Use a different loaded tile: reloading the same map need not advance
        # its context counter, and an unchanged requested position proves no move.
        player = initial["player"]
        targets = [c for c in terrain["cells"] if c.get("loaded") is True and c.get("collision") is False
                   and c.get("terrain_class") == 0 and type(c.get("x")) is int and type(c.get("z")) is int
                   and (c["x"], c["z"]) != (player["x"], player["y"])
                   and not any((w.get("x"), w.get("z", w.get("y"))) == (c["x"], c["z"]) for w in terrain.get("warps", []))]
        check("a different loaded land tile is available", bool(targets))
        target = min(targets, key=lambda c: (abs(c["x"] - player["x"]) + abs(c["z"] - player["y"]), c["z"], c["x"]))
        destination = {"map": initial["context"]["mapId"], "x": target["x"], "z": target["z"], "facing": player["facing"]}
        moved = call("teleport", destination)
        check("teleport returns the requested loaded location", moved["result"]["context"]["mapId"] == destination["map"] and
              [moved["result"]["player"][k] for k in ("x", "y")] == [destination["x"], destination["z"]])
        check("teleport performed a real transition, not a no-op",
              [moved["result"]["player"][k] for k in ("x", "y")] != [player["x"], player["y"]] and
              any(c["routine"] == "create_field_task" for c in moved["result"]["operation"].get("calls", [])))
        check("setup marks session prepared", moved["session"]["mode"] == "prepared")
        # Use a known healthy party subject; edits go through native data calls.
        edited = call("party", {"slot": 0, "species": 56, "level": 10, "hp": 1, "status": 0, "moves": [10, 43, 116, 343]})["result"]
        mon = edited["party"][0]
        check("party fields read back exactly", mon["species"] == 56 and mon["level"] == 10 and mon["hp"] == 1 and mon["status"] == 0 and mon["moves"] == [10, 43, 116, 343])
        for role in ("follower", "mounted"):
            snapshot = call("spawn", {"species": 56, "role": role, "slot": 0})["result"]
            matching = [a for a in snapshot["actors"] if a["role"] == role.upper() and a["subjectIdentity"] == mon["personality"] and a["species"] == 56]
            check(f"exact {role} exists", len(matching) == 1)
            select_current_actor(snapshot, matching[0])
        call("record.stop")
        trace = call("recording.export")["result"]
        trace_data = load_json_artifact(trace["artifact"]["path"])
        check("recording contains real native events", any(e["kind"] == "native" for e in trace_data["events"]))
        reset = call("reset")
        session_id = reset["session"]["id"]
        restored = call("inspect")["result"]
        check("reset restores source party in a new normal session", restored["party"] == initial["party"] and reset["session"]["mode"] == "normal")
        wild = call("spawn", {"species": 165, "role": "wild", "level": 5})["result"]
        receipt = wild["operation"]["value"]
        matching = [a for a in wild["actors"] if a["role"] == "WILD" and a["species"] == 165 and
                    a["identityVerified"] and a["subjectIdentity"] == receipt["personality"] and a["handle"]["slot"] == receipt["slot"]]
        check("the exact spawned Ledyba really exists", len(matching) == 1)
        select_current_actor(wild, matching[0])
        recipe = call("recipe.load", {"name": "devtools-idle-smoke"})
        session_id = recipe["session"]["id"]
        deadline = time.monotonic() + 120
        while True:
            progress = call("status")["session"]["recipe"]
            if progress["state"] != "running":
                break
            if time.monotonic() >= deadline:
                raise AssertionError("recipe did not finish before deadline")
            time.sleep(0.25)
        check("named recipe finishes in a fresh normal session", progress["state"] == "completed")
        # Keep the existing setup/action prefix above unchanged. This checks
        # real completed game frames, not only a successful Play receipt or
        # native emulator cycles. All new waits share a ten-second budget.
        deadline = time.monotonic() + 10

        def playback_call(op):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError("play/pause did not finish within ten seconds")
            return call(op, timeout=remaining)

        def owned_frame(response):
            session = response.get("session") or {}
            frame = response.get("result", {}).get("frame")
            return (session.get("id") == session_id and session.get("state") == "ready"
                    and type(frame) is int and 0 <= frame <= 0xffffffff)

        baseline = playback_call("status")
        check("play starts from a valid owned game frame", owned_frame(baseline))
        start_frame = baseline["result"]["frame"]
        playback_call("play")
        advanced = False
        while time.monotonic() < deadline:
            playing = playback_call("status")
            if not owned_frame(playing) or playing["result"].get("playing") is not True:
                break
            elapsed = (playing["result"]["frame"] - start_frame) & 0xffffffff
            if 3 <= elapsed < 0x80000000:
                advanced = True
                break
            if elapsed >= 0x80000000:
                break  # A backwards/reset clock cannot count as progress.
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        check("play advances at least three completed game frames", advanced)
        paused = playback_call("pause")
        check("pause releases live playback", paused["result"].get("playing") is False)
        paused = playback_call("status")
        check("pause has a valid owned game frame", owned_frame(paused) and paused["result"].get("playing") is False)
        paused_frame = paused["result"]["frame"]
        for _ in range(2):
            time.sleep(0.1)
            held = playback_call("status")
            check("pause holds the completed game frame across delayed status reads",
                  owned_frame(held) and held["result"].get("playing") is False
                  and held["result"]["frame"] == paused_frame)
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if session_id is not None:
            try:
                current = call("status").get("session")
                if current and current["id"] == session_id:
                    call("stop")
            except Exception as error:
                report["cleanupError"] = str(error)
                report["passed"] = False
        report["sourceFilesUnchanged"] = True
        for path, digest in before.items():
            try:
                if sha(path) != digest:
                    report["sourceFilesUnchanged"] = False
            except OSError as error:
                report["sourceFilesUnchanged"] = False
                report.setdefault("sourceCheckErrors", []).append({
                    "path": path, "error": f"{type(error).__name__}: {error}",
                })
        report["passed"] &= report["sourceFilesUnchanged"]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    parser.add_argument("--save", type=Path, default=REPO / "test.sav")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.rom, args.save = args.rom.resolve(), args.save.resolve()
    if args.output.exists():
        parser.error("output exists; choose a new evidence file")
    report = run(args)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: v for k, v in report.items() if k != "responses"}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
