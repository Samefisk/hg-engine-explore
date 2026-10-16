"""Rebuild benchmark: can the generator reproduce vanilla from vanilla's own description?

  python3 -B -m tools.maps.style.rebuild [--case NAME ...] [--builder paint|quilt] [--label L]
  python3 -B -m tools.maps.style.rebuild accept --run RUN_DIR --note "idea: what changed; numbers"
  python3 -B -m tools.maps.style.rebuild reject --run RUN_DIR --note "idea: result; lesson: why"
  python3 -B -m tools.maps.style.rebuild status

For each held-out vanilla chunk: extract its semantic map (semantic.py), build
a new chunk from it with the chunk itself excluded from the kit, and render
both, from straight above and from the game's camera at standable tiles
spread over the chunk (tools.maps.render). If the generator cannot rebuild
Route 29 from Route 29's own description, it cannot make a new route look
like Route 29 either; this is the measure the generator is judged by.

Scores per case (all from images, nothing from the kit's own statistics):

* `void`: pixels black in the rebuild where vanilla is not (top + camera).
  Any is a failure: black void is never acceptable.
* `tileMatch`: share of tiles whose top-down look (8 px per tile, averaged to
  2x2 blocks so texture phase does not count) is within MATCH_DIFF of vanilla.
* `cameraDiff`: mean absolute colour difference of the camera views (0-255).
* `labelMatch`: share of tiles whose re-extracted label equals the target's.

Images go to build/map-style/rebuild/<run>/ (side by side: vanilla | rebuild),
the summary to build/map-style/rebuild/<run>/summary.json. Nothing is written
to data/maps: rebuilt lands live only in memory.

Decisions go to documentation/map-system/lab/rebuild-ledger.jsonl. `accept`
takes only a full run (every case, paint builder) measured on the current
code (code hash over the pipeline's files), and only if it beats the last
accepted run: total void must not grow, mean tileMatch must not drop by more
than NOISE, and one of them must improve (void down, or tileMatch up by NOISE).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np

from .. import codecs, render, world
from . import bdhc_gen, kit as kits, semantic

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "build" / "map-style" / "rebuild"
PPT = 8
MATCH_DIFF = 18.0
NOISE = 0.005
LEDGER = REPO / "documentation" / "map-system" / "lab" / "rebuild-ledger.jsonl"
CODE_FILES = ("semantic.py", "paint.py", "kit.py", "seams.py", "coverage.py", "bdhc_gen.py",
              "rebuild.py")
CASES = [
    {"name": "route29-a", "map": 33, "land": 2},
    {"name": "route29-b", "map": 33, "land": 9},
    {"name": "lake-a", "map": 46, "land": 87},
    {"name": "lake-b", "map": 46, "land": 94},
    {"name": "cave-a", "map": 107, "land": 389},
    {"name": "cave-b", "map": 124, "land": 605},
]


def _builder(name: str):
    if name == "paint":
        from . import paint
        return lambda kit, sem, exclude, seed: paint.paint(kit, sem, exclude, seed)
    if name == "quilt":
        from . import quilt

        def build(kit, sem, exclude, seed):
            rows = [row.replace("?", "T") for row in sem.walk]
            return np.array(quilt.Solver(kit, quilt.load_config(), exclude).solve(rows, seed))
        return build
    raise SystemExit(f"unknown builder {name}")


def land_bytes(kit: dict, grid: np.ndarray, vanilla_land: dict, anim_materials) -> bytes:
    model, tiles, corners = kits.compose(kit, grid.tolist(), "rebuild", anim_materials=anim_materials)
    spec = {"backgroundSound": vanilla_land["backgroundSound"], "tiles": tiles,
            "buildings": vanilla_land["buildings"], "bdhc": bdhc_gen.bdhc_from_corners(corners)}
    return codecs.encode_land(spec, model)


def _scene_with(scene: render.MapScene, land: int, data: bytes) -> render.MapScene:
    clone = render.MapScene.__new__(render.MapScene)
    clone.__dict__.update(scene.__dict__)
    raw = dict(scene.world.raw)
    raw["land"] = list(raw["land"])
    raw["land"][land] = data
    clone.world = dataclasses.replace(scene.world, raw=raw, _cache={})
    clone._meshes, clone._props = {}, scene._props
    return clone


def _chunk_of(scene: render.MapScene, land: int) -> tuple[int, int]:
    m = scene.matrix
    for cz in range(m["height"]):
        for cx in range(m["width"]):
            if scene.land_at(cx, cz) == land:
                return cx, cz
    raise SystemExit(f"land {land} is not in map {scene.map_id}'s matrix")


def _view_tiles(sem: semantic.SemanticMap, chunk: tuple[int, int]) -> list[tuple[int, int]]:
    """Up to 4 standable tiles, one per chunk quarter, nearest each quarter's centre."""
    out = []
    for qx, qz in ((8, 8), (24, 8), (8, 24), (24, 24)):
        best = None
        for z in range(32):
            for x in range(32):
                if sem.walk[z][x] in ".,":
                    d = abs(x - qx) + abs(z - qz)
                    if best is None or d < best[0]:
                        best = (d, x, z)
        if best and best[0] <= 12:
            out.append((chunk[0] * 32 + best[1], chunk[1] * 32 + best[2]))
    return out


def _blocks(image: np.ndarray) -> np.ndarray:
    """Tile-wise 2x2 block means: (32, 32, 2, 2, 3)."""
    a = image[:, :, :3].astype(np.float32).reshape(32, 2, PPT // 2, 32, 2, PPT // 2, 3)
    return a.mean(axis=(2, 5)).transpose(0, 2, 1, 3, 4)


def compare(vanilla: np.ndarray, built: np.ndarray) -> dict:
    black_v = (vanilla[:, :, :3] == 0).all(axis=-1)
    black_b = (built[:, :, :3] == 0).all(axis=-1)
    return {"void": int((black_b & ~black_v).sum()),
            "diff": float(np.abs(vanilla[:, :, :3].astype(np.float32) - built[:, :, :3]).mean())}


def side_by_side(images: list[tuple[np.ndarray, np.ndarray]], path: Path) -> None:
    from PIL import Image
    rows = []
    for a, b in images:
        h = max(a.shape[0], b.shape[0])
        pad = lambda im: np.pad(im[:, :, :3], ((0, h - im.shape[0]), (0, 0), (0, 0)), constant_values=255)
        rows.append(np.concatenate([pad(a), np.full((h, 8, 3), 255, np.uint8), pad(b)], axis=1))
    width = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 8), (0, width - r.shape[1]), (0, 0)), constant_values=255) for r in rows]
    Image.fromarray(np.concatenate(rows).astype(np.uint8)).save(path)


def run_case(case: dict, builder, seed: int, out_dir: Path) -> dict:
    started = time.time()
    scene = render.MapScene(case["map"], overrides=None)
    tileset = scene.area["mapTileset"]
    kit = kits.load_or_build_kit(world.RomSource(REPO / "rom.nds"), tileset)
    land = case["land"]
    target = semantic.extract(kit, kit["chunks"][land])
    grid = builder(kit, target, frozenset({land}), seed)
    built_sem = semantic.extract(kit, grid)
    label_match = float(np.mean([[target.label(x, z) == built_sem.label(x, z) for x in range(32)]
                                 for z in range(32)]))
    anim = kits.area_animation_materials(scene.source, scene.area["dynamicTextureType"])
    built = _scene_with(scene, land, land_bytes(kit, grid, scene.world.member("land", land), anim))
    chunk = _chunk_of(scene, land)
    top_v, _ = scene.overview(ppt=PPT, top=True, chunks=[chunk])
    top_b, _ = built.overview(ppt=PPT, top=True, chunks=[chunk])
    bv, bb = _blocks(top_v), _blocks(top_b)
    tile_diff = np.abs(bv - bb).mean(axis=(2, 3, 4))
    top = compare(top_v, top_b)
    views, cam = [], []
    for x, z in _view_tiles(target, chunk):
        a, b = scene.view(x, z), built.view(x, z)
        views.append((a, b))
        cam.append(compare(a, b))
    side_by_side([(top_v, top_b)] + views, out_dir / f"{case['name']}.png")
    np.save(out_dir / f"{case['name']}-grid.npy", grid)
    return {"case": case["name"], "map": case["map"], "land": land, "seed": seed,
            "void": top["void"] + sum(c["void"] for c in cam),
            "tileMatch": round(float((tile_diff < MATCH_DIFF).mean()), 4),
            "topDiff": round(top["diff"], 2),
            "cameraDiff": round(float(np.mean([c["diff"] for c in cam])) if cam else 0.0, 2),
            "labelMatch": round(label_match, 4),
            "seconds": round(time.time() - started, 1)}


def code_hash() -> str:
    import hashlib
    h = hashlib.sha256()
    for name in CODE_FILES:
        h.update(name.encode() + b"\0" + (Path(__file__).with_name(name)).read_bytes())
    return h.hexdigest()[:16]


def _ledger() -> list[dict]:
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()] if LEDGER.exists() else []


def champion() -> dict | None:
    accepted = [e for e in _ledger() if e["decision"] == "accepted"]
    return accepted[-1] if accepted else None


def totals(summary: dict) -> tuple[int, float]:
    return sum(c["void"] for c in summary["cases"]), summary["mean"]["tileMatch"]


def beats(summary: dict, champ: dict | None) -> tuple[bool, str]:
    if champ is None:
        return True, "first rebuild champion"
    void, match = totals(summary)
    cvoid, cmatch = champ["void"], champ["tileMatch"]
    if void > cvoid:
        return False, f"more void ({void} > {cvoid})"
    if match < cmatch - NOISE:
        return False, f"tileMatch dropped ({cmatch} -> {match})"
    if void < cvoid or match >= cmatch + NOISE:
        return True, f"void {cvoid} -> {void}, tileMatch {cmatch} -> {match}"
    return False, f"no gain beyond noise (void {void}, tileMatch {cmatch} -> {match})"


def decide(run_dir: Path, decision: str, note: str) -> int:
    summary = json.loads((run_dir / "summary.json").read_text())
    full = {c["name"] for c in CASES} == {c["case"] for c in summary["cases"]} and summary["builder"] == "paint"
    ok, reason = beats(summary, champion())
    if decision == "accepted":
        if not full:
            print("refused: only a full paint run (every case) can be accepted")
            return 1
        if summary.get("codeHash") != code_hash():
            print("refused: the pipeline changed since this run was measured; run it again")
            return 1
        if not ok:
            print(f"refused: {reason}")
            return 1
    void, match = totals(summary)
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "decision": decision, "run": summary["run"],
             "codeHash": summary.get("codeHash"), "void": void, "tileMatch": match,
             "voidFree": summary["voidFree"], "perCase": {c["case"]: [c["tileMatch"], c["void"]] for c in summary["cases"]},
             "note": note, "reason": reason}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"{decision} {summary['run']}: {reason}")
    return 0


def run(names: list[str] | None, builder_name: str, seed: int = 0, label: str = "") -> dict:
    cases = [c for c in CASES if not names or c["name"] in names]
    run_id = time.strftime("%Y%m%d-%H%M%S") + (f"-{label}" if label else "")
    out_dir = OUT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    builder = _builder(builder_name)
    results = []
    for case in cases:
        r = run_case(case, builder, seed, out_dir)
        results.append(r)
        print(json.dumps(r), flush=True)
    summary = {"run": run_id, "builder": builder_name, "codeHash": code_hash(), "cases": results,
               "mean": {k: round(float(np.mean([r[k] for r in results])), 4)
                        for k in ("void", "tileMatch", "topDiff", "cameraDiff", "labelMatch")},
               "voidFree": sum(r["void"] == 0 for r in results), "dir": str(out_dir)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("accept", "reject", "status"):
        ap = argparse.ArgumentParser(prog=f"tools.maps.style.rebuild {argv[0]}")
        if argv[0] != "status":
            ap.add_argument("--run", required=True, type=Path)
            ap.add_argument("--note", required=True)
        args = ap.parse_args(argv[1:])
        if argv[0] == "status":
            champ = champion()
            print(json.dumps({"champion": champ, "codeHash": code_hash(),
                              "championIsTree": bool(champ) and champ.get("codeHash") == code_hash()}, indent=1))
            return 0
        run_dir = args.run if args.run.is_absolute() or args.run.exists() else OUT / args.run
        return decide(run_dir, "accepted" if argv[0] == "accept" else "rejected", args.note)
    ap = argparse.ArgumentParser(prog="tools.maps.style.rebuild", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", action="append")
    ap.add_argument("--builder", default="paint", choices=("paint", "quilt"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--label", default="")
    args = ap.parse_args(argv)
    summary = run(args.case, args.builder, args.seed, args.label)
    print(json.dumps({k: summary[k] for k in ("run", "builder", "mean", "voidFree", "dir")}))
    ok, reason = beats(summary, champion())
    print(f"vs champion: {'better' if ok else 'not better'} ({reason})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
