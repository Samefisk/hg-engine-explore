"""Close the map loop: find defects before anyone reports them, and review the loop itself.

  python3 -B -m tools.maps.style.lab scan [--map M] [--write]
  python3 -B -m tools.maps.style.lab retro [--write]

`scan` is proactive bug finding. For every generated map (a map whose lands
have a written generate report) it compares two independent looks at the same
tiles: the offline renderer (`render.voids`, textures and props included) and
the judge (`score.py` checks on the report grid). Problem areas become
defect proposals:

- render flags, judge silent  -> METRIC GAP candidate (fix the judge first)
- judge flags                 -> detected defect (a player target)

Proposals near an open defect are merged into it, not filed again. `--write`
files them (`source: scan`) and closes scan defects that no longer reproduce.
Defects from people are never closed by a scan; it only says when no check
flags their spot any more, so someone looks again.

`retro` is self-improvement over the loop's own records (ledger, run files,
defects, ideas, the papercut log; never conversation transcripts). It
scores the loop with a fixed rubric and turns every failing item into a
proposed change to the skills, the judge or the backlog. `--write` appends
the result to documentation/map-system/lab/retro.md.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..cli import REPO

GRID = 32
BLOCK = 8          # proposals are grouped per 8x8 area, like hotspots
NEAR = 4           # a proposal within this many tiles of an open defect belongs to it
PER_MAP = 5        # most proposals per map and scan
RETRO = REPO / "documentation/map-system/lab/retro.md"
PAPERCUTS = REPO / "PAPERCUTS.md"


# --- scan ----------------------------------------------------------------------------

def generated_maps(overrides: Path = REPO / "data/maps") -> dict[int, list[tuple[Path, dict]]]:
    """{map id: [(report path, report)]} for maps whose matrix holds a written generated land."""
    from . import edit
    from .. import world
    reports = [(p, r) for p, r in edit.load_reports() if r.get("written") and "grid" in r]
    by_land = {land: (p, r) for p, r in reports for land in edit.report_lands(r)}
    edited = world.apply_overrides(edit._base_world(), overrides)
    out: dict[int, list] = {}
    for map_id, header in enumerate(edited.headers):
        if header["matrixId"] >= len(edited.raw["matrix"]):
            continue
        matrix = edited.member("matrix", header["matrixId"])
        if matrix["headers"] is not None and not any(map_id in row for row in matrix["headers"]):
            continue  # a shared matrix: only the map named in its header grid owns cells
        lands = {land for row in matrix["landData"] for land in row} & by_land.keys()
        for land in sorted(lands):
            entry = by_land[land]
            if entry not in out.setdefault(map_id, []):
                out[map_id].append(entry)
    return {m: v for m, v in out.items() if v}


def judge_tiles(map_id: int) -> dict[tuple[int, int], set[str]]:
    """Map tiles the judge flags, with the checks that flag them (from each report grid)."""
    import numpy as np
    from . import coverage, edit, seams as seams_mod
    from .. import render
    scene = render.MapScene(map_id)
    out: dict[tuple[int, int], set[str]] = {}
    done = set()
    for cx, cz in scene.own_chunks():
        try:
            path, report, gx0, gz0 = edit.map_to_grid(map_id, cx * GRID, cz * GRID)
        except edit.EditError:
            continue
        ox, oz = cx * GRID - gx0, cz * GRID - gz0
        if (path, ox, oz) in done:
            continue
        done.add((path, ox, oz))
        kit = edit.kit_for(report["tileset"])
        g = np.array(report["grid"])
        s = seams_mod.for_kit(kit)
        found = {"badSeams": [(int(x), int(z)) for z, x in zip(*np.nonzero(s.seam_map(g)))],
                 "rigidViolations": [(x, z) for x, z, _, _ in s.rigid_violations(g)],
                 "holes": s.holes(g), "bareEdges": s.bare_edges(g), "heightBreaks": s.height_breaks(g),
                 "renderVoid": coverage.render_void_tiles(kit, g)}
        for check, tiles in found.items():
            for x, z in tiles or []:
                out.setdefault((int(x) + ox, int(z) + oz), set()).add(check)
    return out


def _blocks(tiles) -> dict[tuple[int, int], list[tuple[int, int]]]:
    out: dict = {}
    for x, z in tiles:
        out.setdefault((x // BLOCK, z // BLOCK), []).append((x, z))
    return out


def _near(a: tuple[int, int], b: tuple[int, int], radius: int) -> bool:
    return abs(a[0] - b[0]) <= radius and abs(a[1] - b[1]) <= radius


def scan_map(map_id: int, defects: list[dict]) -> dict:
    """Proposals, and per open defect of this map whether any check still flags its spot."""
    from .. import render
    scene = render.MapScene(map_id)
    voids = render.voids(scene)
    rendered = {tuple(t): set() for t in voids["top"]}
    for t in voids["camera"]:
        rendered.setdefault(tuple(t), set())
    for t in voids["top"]:
        rendered[tuple(t)].add("top")
    for t in voids["camera"]:
        rendered[tuple(t)].add("camera")
    judged = judge_tiles(map_id)
    open_here = [d for d in defects if d["map"] == map_id and d["status"] == "open"]
    hard = {t: c - {"badSeams"} for t, c in judged.items() if c - {"badSeams"}}
    proposals, merged = [], []

    def owner(x, z):
        return next((d["id"] for d in open_here if _near((x, z), (d["x"], d["z"]), NEAR)), None)

    # Render void no judge check sees within 2 tiles: the judge is blind there. One proposal per area.
    for tiles in _blocks(rendered).values():
        silent = [t for t in tiles if not any(_near(t, j, 2) for j in hard)]
        if silent:
            p = _proposal(map_id, "metric-gap", silent,
                          f"render.voids shows black void ({_views(rendered, silent)}) beside reachable "
                          "ground; no judge check within 2 tiles")
            known = owner(p["x"], p["z"])
            (merged.append({**p, "defect": known}) if known else proposals.append(p))
    # Judge-detected problems share causes (one solver weakness shows up everywhere), so they
    # become one proposal per map and set of checks, at its worst 8x8 area, listing the others.
    groups: dict[tuple, list] = {}
    for tiles in _blocks(hard).values():
        checks = tuple(sorted({c for t in tiles for c in hard[t]}))
        area = _proposal(map_id, "detected", tiles, "")
        known = owner(area["x"], area["z"])
        if known:
            merged.append({**area, "defect": known, "why": f"judge flags {', '.join(checks)}"})
        else:
            groups.setdefault(checks, []).append((tiles, area))
    for checks, areas in groups.items():
        areas.sort(key=lambda a: -len(a[0]))
        tiles = [t for a in areas for t in a[0]]
        seen = sum(1 for t in tiles if t in rendered)
        worst = areas[0][1]
        others = ", ".join(f"({a[1]['x']},{a[1]['z']})" for a in areas[1:6]) + (" …" if len(areas) > 6 else "")
        proposals.append({**worst, "tiles": len(tiles), "areas": len(areas),
                          "why": f"judge flags {', '.join(checks)} on {len(tiles)} tiles in {len(areas)} areas"
                                 + (f" ({seen} also black in the render)" if seen else "")
                                 + (f"; worst here, also {others}" if others else "")})
    proposals.sort(key=lambda p: (p["kind"] != "metric-gap", -p["tiles"]))
    kept = proposals[:PER_MAP]
    flagged = set(rendered) | set(hard)
    spots = {d["id"]: any(_near((d["x"], d["z"]), t, 2) for t in flagged) for d in open_here}
    return {"map": map_id, "renderVoid": {k: len(v) for k, v in voids.items()},
            "judgeTiles": len(hard),
            "proposals": kept, "merged": merged, "openDefectsStillFlagged": spots}


def _views(rendered: dict, tiles) -> str:
    views = sorted({v for t in tiles for v in rendered[t]})
    return "/".join("from above" if v == "top" else "at the camera pitch" for v in views)


def _proposal(map_id: int, kind: str, tiles, why: str) -> dict:
    tiles = sorted(tiles, key=lambda t: (t[1], t[0]))
    x = sorted(t[0] for t in tiles)[len(tiles) // 2]
    z = sorted(t[1] for t in tiles)[len(tiles) // 2]
    centre = min(tiles, key=lambda t: abs(t[0] - x) + abs(t[1] - z))
    xs, zs = [t[0] for t in tiles], [t[1] for t in tiles]
    return {"map": map_id, "kind": kind, "x": centre[0], "z": centre[1], "tiles": len(tiles),
            "area": [min(xs), min(zs), max(xs), max(zs)], "why": why}


def scan(map_ids: list[int] | None = None, write: bool = False) -> dict:
    from . import lab
    defects = lab._read_jsonl(lab.DEFECTS)
    maps = generated_maps()
    results = [scan_map(m, defects) for m in sorted(maps) if not map_ids or m in map_ids]
    filed, closed, relook = [], [], []
    by_id = {d["id"]: d for d in defects}
    for r in results:
        for defect_id, flagged in r["openDefectsStillFlagged"].items():
            if flagged:
                continue
            d = by_id[defect_id]
            if d.get("source") == "scan":
                closed.append(defect_id)
            else:
                relook.append(defect_id)
    if write:
        for r in results:
            for p in r["proposals"]:
                label = "METRIC GAP candidate" if p["kind"] == "metric-gap" else "detected"
                note = f"scan ({label}): {p['why']}; area x {p['area'][0]}-{p['area'][2]}, z {p['area'][1]}-{p['area'][3]}"
                filed.append(lab.defect_add(p["map"], p["x"], p["z"], note, source="scan",
                                            evidence={"kind": p["kind"], "tiles": p["tiles"], "area": p["area"]})["id"])
        for defect_id in closed:
            lab.defect_close(defect_id, "scan: no check flags this spot any more")
    return {"maps": results, "filed": filed, "closed": closed if write else [],
            "wouldClose": [] if write else closed, "askForRelook": relook}


def format_scan(result: dict) -> str:
    lines = []
    for r in result["maps"]:
        lines.append(f"map {r['map']}: render void {r['renderVoid']['top']}/{r['renderVoid']['camera']} "
                     f"(top/camera), judge-flagged tiles {r['judgeTiles']}")
        for p in r["proposals"]:
            lines.append(f"  new {p['kind']:11} ({p['x']},{p['z']}) {p['tiles']} tiles: {p['why']}")
        for p in r["merged"]:
            lines.append(f"  known {p['defect']:9} ({p['x']},{p['z']}) {p['kind']}: {p['why']}")
    if result["filed"]:
        lines.append(f"filed: {', '.join(result['filed'])}")
    if result["closed"]:
        lines.append(f"closed (scan defects that no longer reproduce): {', '.join(result['closed'])}")
    if result["wouldClose"]:
        lines.append(f"would close with --write: {', '.join(result['wouldClose'])}")
    if result["askForRelook"]:
        lines.append(f"no check flags these reviewed spots any more; ask for a re-look before closing: "
                     f"{', '.join(result['askForRelook'])}")
    if not any(r["proposals"] for r in result["maps"]):
        lines.append("no new problems")
    return "\n".join(lines)


# --- retro ---------------------------------------------------------------------------

def _days(since: str, now: datetime) -> float:
    return (now - datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 86400


def _idea(note: str) -> str:
    return re.split(r"[:;]", note, 1)[0].strip().lower()


def retro(now: datetime | None = None) -> dict:
    """Score the loop's own records with a fixed rubric; every miss comes with a proposed change."""
    from . import lab
    now = now or datetime.now(timezone.utc)
    ledger = lab._read_jsonl(lab.LEDGER)
    defects = lab._read_jsonl(lab.DEFECTS)
    runs = sorted(lab.RUNS.glob("*.json")) if lab.RUNS.exists() else []
    recorded = {e["run"] for e in ledger}
    items = []

    def item(name, ok, evidence, proposal=""):
        items.append({"rubric": name, "pass": ok, "evidence": evidence, "proposal": "" if ok else proposal})

    # 1. Efficiency: how much measuring buys one accepted change.
    accepted = [e for e in ledger if e["decision"] == "accepted"]
    full_runs = []
    for path in runs:
        try:
            run = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if not run.get("quick"):
            full_runs.append(run)
    per_accept = len(full_runs) / max(1, len(accepted))
    item("benches per accepted change", per_accept <= 4,
         f"{len(full_runs)} full benches, {len(accepted)} accepted ({per_accept:.1f} each)",
         "iterate with `bench --quick` / `--case` before a full bench; write down why a hypothesis "
         "should work (worst cases broken down by cause) before measuring")
    # 2. Forgotten decisions: full benches nobody accepted or rejected.
    pending = [r["id"] for r in full_runs if r["id"] not in recorded and r.get("codeHash") != lab.code_hash()
               and not r.get("label", "").startswith("baseline")]
    item("every full bench decided", not pending, f"{len(pending)} undecided full runs on older code: {pending[:5]}",
         "end every iteration with `lab accept` or `lab reject`, so the ledger keeps the lesson")
    # 3. Repeated failures: the same idea rejected more than once.
    rejected: dict[str, int] = {}
    for e in ledger:
        if e["decision"] == "rejected":
            rejected[_idea(e["note"])] = rejected.get(_idea(e["note"]), 0) + 1
    repeats = {k: v for k, v in rejected.items() if v > 1}
    item("no idea rejected twice", not repeats, f"repeated rejections: {repeats}",
         "mark these ideas as dead in ideas.md with the lessons from the ledger notes")
    # 4. Lessons recorded: a rejection must say why.
    silent = [e["run"] for e in ledger if e["decision"] == "rejected" and "lesson" not in e["note"].lower()]
    item("rejections carry a lesson", not silent, f"rejected without 'lesson:': {silent[:5]}",
         "reject with `--note \"<idea>: <result>; lesson: <why>\"` (improve-map-generator step 3a)")
    # 5. Who finds the bugs: agents should find them before the user does.
    def finder(d):
        note = d["note"].lower()
        return "scan" if d.get("source") == "scan" else "user" if note.startswith("user") else "agent review"
    found = {}
    for d in defects:
        found[finder(d)] = found.get(finder(d), 0) + 1
    user_share = found.get("user", 0) / max(1, len(defects))
    item("most defects found before the user", user_share <= 0.34, f"found by: {found}",
         "run `lab scan --write` and the agent screenshot review (design-map-look step 5) before every "
         "hand-off; for each user-found defect, add the check that would have caught it")
    # 6. Metric gaps are priority 1 and must not sit.
    open_defects = [d for d in defects if d["status"] == "open"]
    old = [d["id"] for d in open_defects if _days(d["time"], now) > 3]
    item("no open defect older than 3 days", not old, f"open {len(open_defects)}, older than 3 days: {old}",
         "take the oldest open defect in the next iteration (metric gaps first), or record why it waits in ideas.md")
    # 7. Champion measured on the current tree.
    champ = lab.champion()
    fresh = bool(champ) and champ["codeHash"] == lab.code_hash()
    item("champion measured on the current tree", fresh,
         "no champion" if not champ else f"champion {champ['run']} code {champ['codeHash']}, tree {lab.code_hash()}",
         "bench the unchanged tree (`lab bench --label baseline`) before the next hypothesis")
    # 8. Tool friction, from the papercut log.
    cuts = []
    if PAPERCUTS.exists():
        cuts = [line.strip() for line in PAPERCUTS.read_text().splitlines()
                if re.search(r"tools[./]maps|map-style|map lab|\bmaps?\b.*(tool|lint|render|generate)",
                             re.sub(r"\b(feature|fix|chore)/\S+", "", line), re.I)]
    item("no open map-tool papercuts", not cuts, f"{len(cuts)} entries: " + " | ".join(c[:120] for c in cuts[:3]),
         "triage them (documentation/agent-workflows/papercuts.md) and fix the tool or the skill step")
    score = sum(i["pass"] for i in items)
    return {"time": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "score": f"{score}/{len(items)}", "items": items,
            "proposals": [i["proposal"] for i in items if not i["pass"]]}


def format_retro(result: dict) -> str:
    lines = [f"## Retro {result['time']}: {result['score']}", ""]
    for i in result["items"]:
        lines.append(f"- {'pass' if i['pass'] else 'MISS'}: {i['rubric']}: {i['evidence']}")
        if i["proposal"]:
            lines.append(f"  - proposal: {i['proposal']}")
    return "\n".join(lines) + "\n"


def write_retro(result: dict) -> Path:
    if not RETRO.exists():
        RETRO.write_text("# Lab retros\n\nAppended by `lab retro --write`: the loop's own records scored with a "
                         "fixed rubric (tools/maps/style/loop.py). Act on the proposals, newest first.\n\n")
    with RETRO.open("a") as f:
        f.write(format_retro(result) + "\n")
    return RETRO
