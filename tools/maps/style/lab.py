"""Improvement loop for the map generator: measure, change one thing, keep it only if it wins.

  python3 -B -m tools.maps.style.lab status                 # champion, open defects, recent ledger
  python3 -B -m tools.maps.style.lab bench [--quick] [--label L] [--config F]
  python3 -B -m tools.maps.style.lab accept --run R --note "what changed and why"
  python3 -B -m tools.maps.style.lab reject --run R --note "what was tried, what it showed"
  python3 -B -m tools.maps.style.lab tune --trials 8        # unattended solver-setting search
  python3 -B -m tools.maps.style.lab defect add --map 541 --x 40 --z 28 --note "floating cliff"
  python3 -B -m tools.maps.style.lab defect check           # do the metrics see each defect?
  python3 -B -m tools.maps.style.lab defect close --id D3 --note "fixed by ..."

The benchmark (bench.json) solves the showcase layouts plus held-out
vanilla chunks: a vanilla chunk's own class layout, solved without that chunk
in the kit (no windows, no learned joins from it). Every case is scored with
score.py; `quality` (score.summarize) is the mean seamRate minus 0.05 per
failed hard gate (route change, broken overhang, hole, exposed void, split
region) per case and seed.

The ledger (documentation/map-system/lab/ledger.jsonl) is the loop's memory:
every accepted and rejected attempt with its numbers and lesson. A run can
only be accepted when it was measured on the current tree (code hash) and
beats the champion's quality without more hard-gate failures. User review
notes become defects (defects.jsonl); a defect the metrics cannot see is a
metric gap, the first thing to fix.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from ..cli import REPO

HERE = Path(__file__).resolve().parent
BENCH = HERE / "bench.json"
CONFIG = HERE / "solver_config.json"
LAB_DOCS = REPO / "documentation/map-system/lab"
LEDGER = LAB_DOCS / "ledger.jsonl"
DEFECTS = LAB_DOCS / "defects.jsonl"
RUNS = REPO / "build/map-style/lab"
MIN_GAIN = 0.002  # seed noise on this bench is ~0.001; smaller gains are not evidence



def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def code_hash() -> str:
    """Everything that decides a benchmark result: solver, metrics, settings, cases."""
    h = hashlib.sha256()
    for path in sorted(HERE.glob("*.py")) + [CONFIG, BENCH] + sorted((HERE / "bench_layouts").glob("*.txt")):
        if path.name.startswith("test_"):
            continue
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


JUDGE_FILES = ("seams.py", "score.py", "bench.json")


def judge_hash() -> str:
    """The parts that define the score; a player change must leave them alone."""
    h = hashlib.sha256()
    for name in JUDGE_FILES:
        h.update(name.encode())
        h.update((HERE / name).read_bytes())
    h.update(bench_hash().encode())
    return h.hexdigest()[:16]


def judge_check(tilesets: list[int] | None = None) -> list[str]:
    """Every vanilla chunk of the benchmark's tilesets must score perfectly against its full kit."""
    import numpy as np
    from .. import world
    from . import kit as kits, score, seams as seams_mod
    from .cli import _base, _tileset_of_map  # noqa: F811
    if tilesets is None:
        base = _base()
        tilesets = sorted({_tileset_of_map(base, c["map"]) for c in json.loads(BENCH.read_text())["cases"]})
    problems = []
    for tileset in tilesets:
        kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
        s = seams_mod.for_kit(kit)
        for land in s.self_excluded:
            print(f"note: tileset {tileset} land {land}: floor beside empty tiles (walls are props); not learned from")
        for land, grid in sorted(kit["chunks"].items()):
            if land in s.self_excluded:
                continue
            g = np.array(grid)
            found = {"badSeams": s.profile_seams(g)[0], "rigidViolations": len(s.rigid_violations(g)),
                     "holes": len(s.holes(g)), "bareEdges": len(s.bare_edges(g, margin=2)),
                     "heightBreaks": len(s.height_breaks(g))}
            exposed = score.void_exposed(kit, grid)
            found = {k: v for k, v in found.items() if v}
            if found:
                problems.append(f"tileset {tileset} land {land}: {found}")
            if exposed:  # vanilla has a few at chunk borders; report, do not fail
                print(f"note: tileset {tileset} land {land}: {exposed} void tiles beside land in vanilla")
    return problems


def bench_hash() -> str:
    """bench.json plus its frozen layouts (bench_layouts/), so editing a live map never moves the benchmark."""
    h = hashlib.sha256(BENCH.read_bytes())
    for path in sorted((HERE / "bench_layouts").glob("*.txt")):
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_jsonl(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def champion() -> dict | None:
    accepted = [e for e in _read_jsonl(LEDGER) if e["decision"] == "accepted"]
    return accepted[-1] if accepted else None


# --- benchmark ---------------------------------------------------------------

def _case_rows(case: dict, base, kit) -> tuple[list[str], frozenset]:
    from . import layout
    if case["kind"] == "layout":
        return layout.parse((REPO / case["layout"]).read_text()), frozenset()
    rows = layout.render(kit["chunks"][case["land"]], kit)
    return [row.replace("?", "T") for row in rows], frozenset({case["land"]})


def run_case(case: dict, seeds: list[int], config: dict) -> dict:
    from .. import world
    from . import kit as kits, quilt, score
    from .cli import _base, _tileset_of_map
    base = _base()
    tileset = _tileset_of_map(base, case["map"])
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    rows, exclude = _case_rows(case, base, kit)
    solver = quilt.Solver(kit, config, exclude)
    # A vanilla chunk may be split into regions joined through other chunks; held-out
    # cases may have as many regions as their vanilla original.
    components = score.walkable_components(kit, kit["chunks"][case["land"]]) if exclude else 1
    out = []
    for seed in seeds:
        started = time.time()
        grid = solver.solve(rows, seed)
        result = score.score(kit, grid, rows, exclude=exclude)
        failed = [g for g in score.passes(result)
                  if not (g == "walkableComponents" and result["walkableComponents"] <= components)]
        out.append({"seed": seed, "seconds": round(time.time() - started, 1),
                    **{k: result[k] for k in ("seamRate", "badSeams", "layoutMatch", "pairRate", *score.HARD_GATES)},
                    "failed": failed})
    return {"case": case["name"], "tileset": tileset, "seeds": out}


def bench(config: dict | None = None, quick: bool = False, label: str = "", workers: int = 6,
          only: list[str] | None = None) -> dict:
    from . import quilt, score
    spec = json.loads(BENCH.read_text())
    config = config or quilt.load_config()
    seeds = spec["quickSeeds"] if quick else spec["seeds"]
    cases = [c for c in spec["cases"] if not only or c["name"] in only]
    started = time.time()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run_case, cases, [seeds] * len(cases), [config] * len(cases)))
    run = {"id": f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{label or 'run'}",
           "time": now(), "label": label, "quick": quick, "codeHash": code_hash(), "benchHash": bench_hash(),
           "judgeHash": judge_hash(),
           "config": config, "summary": score.summarize(results), "cases": results,
           "wallSeconds": round(time.time() - started, 1)}
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{run['id']}.json").write_text(json.dumps(run, indent=1) + "\n")
    return run


def load_run(run_id: str) -> dict:
    path = Path(run_id) if run_id.endswith(".json") else RUNS / f"{run_id}.json"
    return json.loads(path.read_text())


def beats(run: dict, champ: dict | None) -> tuple[bool, str]:
    if champ is None:
        return True, "no champion yet"
    if champ.get("benchHash") != run["benchHash"] or champ.get("judgeHash") != run.get("judgeHash"):
        return False, ("the judge (seams.py, score.py, bench.json) changed since the champion; "
                       "only a defect or vanilla false alarm justifies that: judge-check, then accept --rebaseline")
    a, b = run["summary"], champ["summary"]
    if a["hardGateFailures"] > b["hardGateFailures"]:
        return False, f"more hard-gate failures ({a['hardGateFailures']} > {b['hardGateFailures']})"
    if a["quality"] < b["quality"] + MIN_GAIN:
        return False, (f"quality {a['quality']} does not beat champion {b['quality']} "
                       f"by the noise margin {MIN_GAIN}")
    if a["seconds"] > 2.5 * max(1.0, b["seconds"]):
        return False, f"too slow ({a['seconds']} s vs champion {b['seconds']} s)"
    return True, f"quality {b['quality']} -> {a['quality']}"


def record(run: dict, decision: str, note: str, reason: str = "") -> dict:
    entry = {"time": now(), "decision": decision, "run": run["id"], "codeHash": run["codeHash"],
             "benchHash": run["benchHash"], "judgeHash": run.get("judgeHash"), "summary": run["summary"], "config": run["config"],
             "note": note, "reason": reason,
             "perCase": {c["case"]: round(sum(s["seamRate"] for s in c["seeds"]) / len(c["seeds"]), 4)
                         for c in run["cases"]}}
    _append_jsonl(LEDGER, entry)
    return entry


def accept(run_id: str, note: str, rebaseline: bool = False) -> int:
    run = load_run(run_id)
    if run["quick"]:
        print("refused: quick runs cannot be accepted; run the full bench")
        return 1
    if run["codeHash"] != code_hash():
        print("refused: the tree changed since this run was measured; bench again")
        return 1
    if rebaseline:
        problems = judge_check()
        if problems:
            print("refused: the judge flags vanilla chunks:\n  " + "\n  ".join(problems[:10]))
            return 1
    ok, reason = (True, "rebaseline") if rebaseline else beats(run, champion())
    if not ok:
        print(f"refused: {reason}")
        return 1
    from . import quilt
    if run["config"] != quilt.load_config():
        data = json.loads(CONFIG.read_text())
        data["solver"] = run["config"]
        CONFIG.write_text(json.dumps(data, indent=1) + "\n")
        print("solver_config.json updated; the code hash changes, which is expected for a config acceptance")
    record(run, "accepted", note, reason)
    print(f"accepted {run['id']}: {reason}")
    return 0


# --- unattended tuning ---------------------------------------------------------

def search_space() -> dict:
    """Settings `tune` may change, with the values it may pick (player side, solver_config.json)."""
    return json.loads(CONFIG.read_text())["search"]


def mutate(config: dict, rng: random.Random, changes: int = 2) -> dict:
    out = copy.deepcopy(config)
    space = search_space()
    for key in rng.sample(sorted(space), changes):
        options = [v for v in space[key] if v != out.get(key)]
        out[key] = rng.choice(options)
    return out


def tune(trials: int, seed: int | None = None) -> int:
    """Quick-bench mutations of the champion, full-bench the best, accept it if it wins."""
    from . import quilt
    rng = random.Random(seed if seed is not None else time.time())
    base_config = quilt.load_config()
    base = bench(base_config, quick=True, label="tune-base")
    best = (base["summary"], base_config)
    print(f"base quick quality {base['summary']['quality']}")
    tried, log = set(), []
    for trial in range(trials):
        config = mutate(best[1], rng)
        key = json.dumps(config, sort_keys=True)
        if key in tried:
            continue
        tried.add(key)
        run = bench(config, quick=True, label=f"tune-{trial}")
        s = run["summary"]
        diff = {k: v for k, v in config.items() if base_config.get(k) != v}
        print(f"trial {trial}: quality {s['quality']} failures {s['hardGateFailures']} {s['seconds']} s {diff}")
        log.append({"settings": diff, "quality": s["quality"], "failures": s["hardGateFailures"]})
        if (s["hardGateFailures"], -s["quality"]) < (best[0]["hardGateFailures"], -best[0]["quality"]) \
                and s["seconds"] <= 2.5 * max(1.0, base["summary"]["seconds"]):
            best = (s, config)
    if best[1] == base_config:
        print("no quick-bench improvement")
        record(base, "rejected", f"tune: {len(log)} setting mutations, none beat the champion on the quick bench",
               "quick bench: " + json.dumps(log))
        return 0
    full = bench(best[1], label="tune-best")
    ok, reason = beats(full, champion())
    diff = {k: v for k, v in best[1].items() if base_config.get(k) != v}
    if ok:
        return accept(full["id"], f"tune: settings {diff}")
    record(full, "rejected", f"tune: settings {diff}", reason)
    print(f"rejected: {reason}")
    return 0


# --- defects from user review ------------------------------------------------------

def _generated_cell(map_id: int, x: int, z: int):
    """(kit, grid, local x, local z, exclude) for a tile of a generated map, from its generate report."""
    from .. import world
    from . import kit as kits
    from .cli import REPORT_DIR, _base
    edited = world.apply_overrides(_base(), REPO / "data/maps")
    matrix = edited.matrix_for(map_id)
    land = matrix["landData"][z // 32][x // 32]
    reports = sorted(REPORT_DIR.glob("report-*.json"))
    for path in reports:
        report = json.loads(path.read_text())
        if land in report.get("lands", []) and "grid" in report:
            first = report["lands"][0]
            width = report["chunks"][0]
            index = land - first
            ox, oz = (index % width) * 32, (index // width) * 32
            kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), report["tileset"])
            return kit, report["grid"], ox + x % 32, oz + z % 32
    return None


def defect_check(radius: int = 2) -> int:
    import numpy as np
    from . import seams as seams_mod
    defects = [d for d in _read_jsonl(DEFECTS) if d["status"] == "open"]
    if not defects:
        print("no open defects")
        return 0
    gaps = 0
    for d in defects:
        found = _generated_cell(d["map"], d["x"], d["z"])
        if found is None:
            print(f"{d['id']}: no generate report with a grid for map {d['map']}; regenerate the map first")
            continue
        kit, grid, gx, gz = found
        g = np.array(grid)
        s = seams_mod.for_kit(kit)
        near = lambda x, z: abs(x - gx) <= radius and abs(z - gz) <= radius  # noqa: E731
        seam = s.seam_map(g)
        counts = {
            "badSeams": int(seam[max(0, gz - radius):gz + radius + 1, max(0, gx - radius):gx + radius + 1].sum()),
            "rigidViolations": sum(near(x, z) or near(x + dx, z + dz) for x, z, dx, dz in s.rigid_violations(g)),
            "holes": sum(near(x, z) for x, z in s.holes(g)),
        }
        seen = any(counts.values())
        gaps += not seen
        print(f"{d['id']} map {d['map']} ({d['x']},{d['z']}) {d['note']!r}: "
              + ("detected " + json.dumps(counts) if seen else "METRIC GAP: no check flags this spot"))
    return 1 if gaps else 0


def defect_add(map_id: int, x: int, z: int, note: str) -> dict:
    existing = _read_jsonl(DEFECTS)
    entry = {"id": f"D{len(existing) + 1}", "time": now(), "map": map_id, "x": x, "z": z, "note": note,
             "status": "open"}
    _append_jsonl(DEFECTS, entry)
    return entry


def defect_close(defect_id: str, note: str) -> int:
    entries = _read_jsonl(DEFECTS)
    hit = [e for e in entries if e["id"] == defect_id]
    if not hit:
        print(f"no defect {defect_id}")
        return 1
    hit[0].update(status="closed", closed=now(), resolution=note)
    DEFECTS.write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in entries))
    return 0


def status() -> int:
    champ = champion()
    print(f"code hash {code_hash()}, bench {bench_hash()}")
    if champ:
        s = champ["summary"]
        print(f"champion {champ['run']} ({champ['time']}): quality {s['quality']}, "
              f"hard-gate failures {s['hardGateFailures']}, {s['seconds']} s")
        print("  per case: " + ", ".join(f"{k} {v}" for k, v in sorted(champ["perCase"].items(), key=lambda kv: kv[1])))
        print(f"  champion code {'matches' if champ['codeHash'] == code_hash() else 'DIFFERS from'} the tree; "
              f"judge {'unchanged' if champ.get('judgeHash') == judge_hash() else 'CHANGED'}")
    else:
        print("no champion: run `bench --label baseline` and `accept --rebaseline`")
    open_defects = [d for d in _read_jsonl(DEFECTS) if d["status"] == "open"]
    print(f"open defects: {len(open_defects)}")
    for d in open_defects:
        print(f"  {d['id']} map {d['map']} ({d['x']},{d['z']}): {d['note']}")
    print("recent ledger:")
    for e in _read_jsonl(LEDGER)[-6:]:
        print(f"  {e['time']} {e['decision']:8} q={e['summary']['quality']} {e['note'][:90]}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.style.lab", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("judge-check", help="vanilla chunks must score perfectly (after any judge change)")
    b = sub.add_parser("bench")
    b.add_argument("--quick", action="store_true")
    b.add_argument("--label", default="")
    b.add_argument("--config", type=Path, help="JSON file with solver settings (default: champion)")
    b.add_argument("--case", action="append", help="only these case names (not acceptable)")
    b.add_argument("--workers", type=int, default=6)
    for name in ("accept", "reject"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        p.add_argument("--note", required=True)
        if name == "accept":
            p.add_argument("--rebaseline", action="store_true",
                           help="first champion, or the benchmark itself changed")
    t = sub.add_parser("tune")
    t.add_argument("--trials", type=int, default=8)
    t.add_argument("--seed", type=int)
    d = sub.add_parser("defect")
    dsub = d.add_subparsers(dest="action", required=True)
    add = dsub.add_parser("add")
    add.add_argument("--map", type=int, required=True)
    add.add_argument("--x", type=int, required=True)
    add.add_argument("--z", type=int, required=True)
    add.add_argument("--note", required=True)
    dsub.add_parser("check")
    close = dsub.add_parser("close")
    close.add_argument("--id", required=True)
    close.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    if args.command == "status":
        return status()
    if args.command == "judge-check":
        problems = judge_check()
        print("\n".join(problems) if problems else "judge-check: every vanilla chunk scores perfectly")
        return 1 if problems else 0
    if args.command == "bench":
        config = json.loads(args.config.read_text()) if args.config else None
        run = bench(config, args.quick, args.label, args.workers, args.case)
        print(json.dumps({"id": run["id"], **run["summary"], "wallSeconds": run["wallSeconds"],
                          "perCase": {c["case"]: [s["seamRate"] for s in c["seeds"]] for c in run["cases"]},
                          "failed": {c["case"]: [s["failed"] for s in c["seeds"]] for c in run["cases"]}}, indent=1))
        ok, reason = beats(run, champion())
        print(f"vs champion: {'better' if ok else 'not better'} ({reason})")
        return 0
    if args.command == "accept":
        return accept(args.run, args.note, args.rebaseline)
    if args.command == "reject":
        run = load_run(args.run)
        record(run, "rejected", args.note, beats(run, champion())[1])
        return 0
    if args.command == "tune":
        return tune(args.trials, args.seed)
    if args.action == "add":
        print(json.dumps(defect_add(args.map, args.x, args.z, args.note)))
        return 0
    if args.action == "check":
        return defect_check()
    return defect_close(args.id, args.note)


if __name__ == "__main__":
    sys.exit(main())
