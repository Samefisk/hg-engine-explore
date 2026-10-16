"""Before/after diff of a map edit, rendered offline (no build, no emulator).

  python3 -B -m tools.maps.render_diff --map 543                        # git HEAD vs the working tree
  python3 -B -m tools.maps.render_diff --snapshot pre-resolve           # copy data/maps/ aside first
  python3 -B -m tools.maps.render_diff --map 543 --before snapshot:pre-resolve [--views] [--top]

`--before` / `--after` take a git ref (default before: HEAD), `snapshot:NAME`
(build/map-render/snapshots/NAME, made by --snapshot) or an override-tree
directory (default after: data/maps/). Both sides are rendered with the same
camera, so pixels align.

Writes build/map-render/diff/diff-M.png (before | after overview, changed tiles
outlined red on both, newly void tiles magenta on after, fixed void tiles green
on before), views-M.png with --views (the game camera at up to six changed
regions, before | after) and summary-M.json; prints the summary (tile lists
capped at 100) to stdout.

A tile is "changed" when its land.json collision/behavior/secondary differs,
or when its pixels differ in the top-down or camera-pitch overview (model
geometry, textures; detected at 8 pixels per tile). Per chunk it lists what
differs: land id, model, BDHC, buildings, tiles; `unlocated` marks a geometry
change no rendered pixel shows (hidden or sub-pixel). `voids` is render.voids() on both sides. `resolve` is the
last `resolves` entry of the build/map-style report holding the map's lands.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from . import codecs
from .render import GRID, TILE, OUT_DIR, REPO, MapScene, annotate_tiles, rasterize, save, voids

DIFF_DIR = OUT_DIR / "diff"
SNAPSHOT_DIR = OUT_DIR / "snapshots"
REPORT_DIR = REPO / "build/map-style"
DETECT_PPT = 8  # pixels per tile for change detection
PIXEL_THRESHOLD = 8  # max channel difference that counts as a changed pixel
MAX_VIEWS = 6
STDOUT_CAP = 100
LAYERS = ("collision", "behavior", "secondary")


# --- Sources -----------------------------------------------------------------------

def snapshot(name: str, source: Path = REPO / "data/maps", force: bool = False) -> Path:
    """Copy an override tree to build/map-render/snapshots/NAME."""
    if not name or "/" in name or name.startswith("."):
        raise ValueError(f"bad snapshot name {name!r}")
    dest = SNAPSHOT_DIR / name
    if dest.exists():
        if not force:
            raise FileExistsError(f"snapshot {name} exists ({dest}); pass --force to replace it")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    return dest


def materialize(spec: str | None, tmp: Path, default: str) -> tuple[Path, str]:
    """An override tree for `spec`: snapshot:NAME, a directory, or a git ref (extracted into tmp)."""
    spec = spec or default
    if spec.startswith("snapshot:"):
        path = SNAPSHOT_DIR / spec.split(":", 1)[1]
        if not path.is_dir():
            raise FileNotFoundError(f"no snapshot {path}")
        return path, spec
    path = Path(spec)
    if path.is_dir():
        if (path / "data/maps").is_dir():
            path = path / "data/maps"
        path = path.resolve()
        label = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
        return path, label + (" (working tree)" if path == (REPO / "data/maps").resolve() else "")
    ref = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--verify", "--quiet", f"{spec}^{{commit}}"],
                         capture_output=True, text=True)
    if ref.returncode:
        raise ValueError(f"{spec!r} is neither snapshot:NAME, a directory, nor a git commit")
    commit = ref.stdout.strip()
    out = tmp / commit[:12]
    out.mkdir(parents=True, exist_ok=True)
    listed = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-d", commit, "data/maps"],
                            capture_output=True, text=True, check=True)
    if listed.stdout.strip():  # a commit before data/maps existed has no overrides: vanilla
        archive = subprocess.run(["git", "-C", str(REPO), "archive", commit, "data/maps"],
                                 capture_output=True, check=True)
        subprocess.run(["tar", "-x", "-C", str(out)], input=archive.stdout, check=True)
    (out / "data/maps").mkdir(parents=True, exist_ok=True)
    return out / "data/maps", f"{spec} ({commit[:9]})"


# --- Pure diff logic -----------------------------------------------------------------

def _cells(row, layer: str) -> list[str]:
    return list(row) if layer == "collision" else row.split()


def tile_layer_diff(before: dict | None, after: dict | None, cx: int, cz: int) -> dict:
    """{(x, z): {layer, ...}} for tiles whose land.json tile layers differ (tiles dicts of one chunk)."""
    out: dict = {}
    for layer in LAYERS:
        a = before[layer] if before else None
        b = after[layer] if after else None
        for lz in range(GRID):
            ra = _cells(a[lz], layer) if a else [None] * GRID
            rb = _cells(b[lz], layer) if b else [None] * GRID
            for lx in range(GRID):
                if ra[lx] != rb[lx]:
                    out.setdefault((cx * GRID + lx, cz * GRID + lz), set()).add(layer)
    return out


def pixel_tiles(img_a: np.ndarray, img_b: np.ndarray, where_a: np.ndarray, where_b: np.ndarray,
                threshold: int = PIXEL_THRESHOLD) -> set[tuple[int, int]]:
    """Tiles under pixels that differ between two same-camera renders (world x/z per pixel from pick)."""
    diff = np.abs(img_a.astype(np.int16) - img_b.astype(np.int16)).max(axis=2) > threshold
    ys, xs = np.nonzero(diff)
    wb, wa = where_b[ys, xs], where_a[ys, xs]
    w = np.where(np.isnan(wb[:, :1]), wa, wb)  # the after surface, else what vanished
    w = w[~np.isnan(w[:, 0])]
    return {(int(x // TILE), int(z // TILE)) for x, z in w}


def cluster(tiles, gap: int = 2, cap: int = MAX_VIEWS) -> list[dict]:
    """Group tiles within `gap` (Chebyshev) of each other; largest first, at most `cap`.

    Each: {"center": (x, z) the member tile nearest the mean, "size", "bbox": [x0, z0, x1, z1]}."""
    tiles = sorted(set(tiles))
    index = {t: i for i, t in enumerate(tiles)}
    parent = list(range(len(tiles)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for (x, z), i in index.items():
        for dz in range(-gap, gap + 1):
            for dx in range(-gap, gap + 1):
                j = index.get((x + dx, z + dz))
                if j is not None:
                    parent[find(i)] = find(j)
    groups: dict = {}
    for t, i in index.items():
        groups.setdefault(find(i), []).append(t)
    out = []
    for members in groups.values():
        mx = sum(t[0] for t in members) / len(members)
        mz = sum(t[1] for t in members) / len(members)
        center = min(members, key=lambda t: ((t[0] - mx) ** 2 + (t[1] - mz) ** 2, t))
        xs, zs = [t[0] for t in members], [t[1] for t in members]
        out.append({"center": center, "size": len(members), "bbox": [min(xs), min(zs), max(xs), max(zs)]})
    out.sort(key=lambda c: (-c["size"], c["center"]))
    return out[:cap]


def void_change(before: dict, after: dict) -> dict:
    """Counts per side and the tiles newly void / fixed (union of top and camera)."""
    b = {tuple(t) for k in ("top", "camera") for t in before[k]}
    a = {tuple(t) for k in ("top", "camera") for t in after[k]}
    return {"before": {"top": len(before["top"]), "camera": len(before["camera"])},
            "after": {"top": len(after["top"]), "camera": len(after["camera"])},
            "newlyVoid": sorted(a - b), "fixed": sorted(b - a)}


# --- Scene comparison -----------------------------------------------------------------

def chunk_diff(before: MapScene, after: MapScene, chunks) -> tuple[list[dict], dict]:
    """Per chunk what differs, and {(x, z): {layer}} for tile-layer differences."""
    report, tiles = [], {}
    for cx, cz in chunks:
        la, lb = before.land_at(cx, cz), after.land_at(cx, cz)
        ra = before.world.raw["land"][la] if la is not None else None
        rb = after.world.raw["land"][lb] if lb is not None else None
        if la == lb and ra == rb:
            continue
        ma = before.world.member("land", la) if la is not None else None
        mb = after.world.member("land", lb) if lb is not None else None
        parts = []
        if la != lb:
            parts.append("landId")
        if ra is None or rb is None or codecs.decode_land_model(ra) != codecs.decode_land_model(rb):
            parts.append("model")
        for key in ("bdhc", "buildings", "tiles", "backgroundSound"):
            if (ma or {}).get(key) != (mb or {}).get(key):
                parts.append(key)
        report.append({"chunk": [cx, cz], "land": [la, lb], "changed": parts})
        for t, layers in tile_layer_diff(ma and ma["tiles"], mb and mb["tiles"], cx, cz).items():
            tiles.setdefault(t, set()).update(layers)
    return report, tiles


def render_pair(before: MapScene, after: MapScene, chunks, top: bool, ppt: int):
    """Both sides through the after side's overview camera: (img_b, where_b, img_a, where_a, cam)."""
    img_a, cam, where_a = after.overview(ppt, top=top, chunks=chunks, pick=True)
    img_b, where_b = rasterize(before.mesh(chunks), cam, pick=True)
    return img_b, where_b, img_a, where_a, cam


def resolve_note(lands) -> dict | None:
    """The last resolve of the generate report holding any of `lands`."""
    from .style import edit
    lands = set(lands)
    for path in sorted(REPORT_DIR.glob("report-*.json"), key=lambda p: -p.stat().st_mtime):  # newest first
        try:
            report = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if "grid" not in report and not report.get("lands"):
            continue
        if not lands & set(edit.report_lands(report)):
            continue
        resolves = report.get("resolves") or []
        if not resolves:
            return {"report": str(path), "resolves": 0}
        last = resolves[-1]
        out = {"report": str(path), "resolves": len(resolves), "time": last.get("time"),
               "seamRateBefore": last.get("seamRateBefore"), "seamRateAfter": last.get("seamRateAfter"),
               "regions": [{"region": r.get("region"), "accepted": r.get("accepted"),
                            "changedTiles": len(r.get("changedTiles") or [])} for r in last.get("regions", [])]}
        if out["seamRateBefore"] is not None and out["seamRateAfter"] is not None:
            out["seamRateDelta"] = round(out["seamRateAfter"] - out["seamRateBefore"], 4)
        return out
    return None


def diff(before: MapScene, after: MapScene, ppt: int = 8, top: bool = False, with_voids: bool = True) -> dict:
    """Everything the CLI reports, plus the rendered panels (key "_panels")."""
    # The edited map's chunks frame both sides (a map moved to a new matrix would otherwise drag in
    # its whole old matrix); chunks only the before side owned are counted, not drawn.
    chunks = sorted(after.own_chunks()) or sorted(before.own_chunks())
    owned = set(chunks)
    before_only = len(set(before.own_chunks()) - owned)
    chunk_report, layer_tiles = chunk_diff(before, after, chunks)
    reasons: dict = {t: set(v) for t, v in layer_tiles.items()}
    shown = None
    for is_top in (True, False):  # detect at DETECT_PPT at least: a small model edit can be sub-pixel
        img_b, where_b, img_a, where_a, cam = render_pair(before, after, chunks, is_top, max(ppt, DETECT_PPT))
        for t in pixel_tiles(img_b, img_a, where_b, where_a):
            if (t[0] // GRID, t[1] // GRID) in owned:
                reasons.setdefault(t, set()).add("pixelsTop" if is_top else "pixelsCamera")
        if is_top == top:
            shown = (img_b, img_a, cam)
    if ppt < DETECT_PPT:
        img_b, _, img_a, _, cam = render_pair(before, after, chunks, top, ppt)
        shown = (img_b, img_a, cam)
    tiles = sorted(reasons)
    located = {(x // GRID, z // GRID) for x, z in tiles}
    for entry in chunk_report:  # a geometry change no tile shows (hidden, or below a pixel)
        if tuple(entry["chunk"]) not in located and set(entry["changed"]) & {"model", "bdhc", "landId"}:
            entry["unlocated"] = True
    out = {"map": after.map_id, "chunks": chunk_report, "changedTileCount": len(tiles),
           "changedTiles": [{"x": x, "z": z, "why": sorted(reasons[(x, z)])} for x, z in tiles],
           "regions": cluster(tiles)}
    if before_only:
        out["beforeOnlyChunks"] = before_only
    if with_voids:
        out["voids"] = void_change(voids(before), voids(after))
    lands = {after.land_at(*c) for c in chunks} | {before.land_at(*c) for c in chunks}
    out["resolve"] = resolve_note(lands - {None})
    out["_panels"] = shown
    return out


# --- Images ---------------------------------------------------------------------------

def _outline(draw, scene: MapScene, cam, tiles, color, width=1):
    for x, z in tiles:
        y = scene.height(x, z)
        corners = [cam.screen_of((x * TILE + dx, y, z * TILE + dz)) for dx, dz in ((0, 0), (TILE, 0), (TILE, TILE), (0, TILE))]
        if all(corners):
            draw.polygon(corners, outline=color, width=width)


def diff_image(before: MapScene, after: MapScene, result: dict, labels: tuple[str, str]) -> "Image":
    from PIL import Image, ImageDraw
    img_b, img_a, cam = result["_panels"]
    tiles = [(t["x"], t["z"]) for t in result["changedTiles"]]
    voided = result.get("voids") or {"newlyVoid": [], "fixed": [], "before": {}, "after": {}}
    panels = []
    for scene, image, label, side, extra, extra_color in (
            (before, img_b, labels[0], "before", voided["fixed"], (60, 255, 60)),
            (after, img_a, labels[1], "after", voided["newlyVoid"], (255, 0, 255))):
        img = Image.fromarray(annotate_tiles(image, after, cam))
        draw = ImageDraw.Draw(img)
        _outline(draw, scene, cam, tiles, (255, 40, 40), 2 if len(tiles) < 200 else 1)
        _outline(draw, scene, cam, extra, extra_color, 2)
        for i, region in enumerate(result["regions"], 1):
            at = cam.screen_of(scene.tile_world(*region["center"]))
            if at:
                draw.text((at[0] + 6, at[1] - 14), f"#{i}", fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
        counts = voided.get(side) or {}
        title = f"{side}: {label}"
        if counts:
            title += f"   void top {counts['top']} / camera {counts['camera']}"
        panels.append((img, title))
    head, gap = 18, 6
    w = sum(p.width for p, _ in panels) + gap
    h = max(p.height for p, _ in panels) + head
    sheet = Image.new("RGB", (w, h), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    x = 0
    for img, title in panels:
        sheet.paste(img, (x, head))
        draw.text((x + 4, 3), title, fill=(255, 255, 255))
        x += img.width + gap
    return sheet


def views_image(before: MapScene, after: MapScene, regions) -> "Image":
    from PIL import Image, ImageDraw
    scale, head = 2, 16
    cw, ch = 256 * scale, 192 * scale
    sheet = Image.new("RGB", (cw * 2 + 6, (ch + head) * len(regions)), (40, 40, 40))
    draw = ImageDraw.Draw(sheet)
    for row, region in enumerate(regions):
        x, z = region["center"]
        y0 = row * (ch + head)
        for col, (scene, side) in enumerate(((before, "before"), (after, "after"))):
            shot = Image.fromarray(scene.view(x, z)).resize((cw, ch), Image.NEAREST)
            sheet.paste(shot, (col * (cw + 6), y0 + head))
            draw.text((col * (cw + 6) + 4, y0 + 2), f"#{row + 1} {side} at {x},{z} ({region['size']} tiles)",
                      fill=(255, 255, 255))
    return sheet


# --- CLI -----------------------------------------------------------------------------

def _capped(result: dict) -> dict:
    out = {k: v for k, v in result.items() if not k.startswith("_")}
    if "voids" in out:
        out["voids"] = dict(out["voids"])
    for holder, key in ((out, "changedTiles"), (out.get("voids"), "newlyVoid"), (out.get("voids"), "fixed")):
        if holder and len(holder[key]) > STDOUT_CAP:
            holder[key + "Omitted"] = len(holder[key]) - STDOUT_CAP
            holder[key] = holder[key][:STDOUT_CAP]
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.render_diff", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", type=int)
    parser.add_argument("--before", help="git ref, snapshot:NAME or directory (default HEAD)")
    parser.add_argument("--after", help="git ref, snapshot:NAME or directory (default data/maps/)")
    parser.add_argument("--out", type=Path, default=DIFF_DIR)
    parser.add_argument("--top", action="store_true", help="top-down panels (default: the camera's pitch)")
    parser.add_argument("--ppt", type=int, default=8, help="pixels per tile")
    parser.add_argument("--views", action="store_true", help="game-camera views at the changed regions")
    parser.add_argument("--no-voids", action="store_true", help="skip render.voids on both sides")
    parser.add_argument("--snapshot", metavar="NAME", help="copy data/maps/ to build/map-render/snapshots/NAME")
    parser.add_argument("--force", action="store_true", help="replace an existing snapshot")
    args = parser.parse_args(argv)
    if args.snapshot:
        print(json.dumps({"snapshot": str(snapshot(args.snapshot, force=args.force)),
                          "use": f"--before snapshot:{args.snapshot}"}))
        return 0
    if args.map is None:
        parser.error("--map is required (or --snapshot NAME)")
    with tempfile.TemporaryDirectory(prefix="render-diff-") as tmp:
        before_dir, before_label = materialize(args.before, Path(tmp) / "before", "HEAD")
        after_dir, after_label = materialize(args.after, Path(tmp) / "after", str(REPO / "data/maps"))
        before, after = MapScene(args.map, before_dir), MapScene(args.map, after_dir)
        result = diff(before, after, args.ppt, args.top, not args.no_voids)
        result["before"], result["after"] = before_label, after_label
        written = [save(np.asarray(diff_image(before, after, result, (before_label, after_label))),
                        args.out / f"diff-{args.map}.png")]
        if args.views and result["regions"]:
            written.append(save(np.asarray(views_image(before, after, result["regions"])),
                                args.out / f"views-{args.map}.png"))
    result["written"] = [str(p) for p in written]
    full = {k: v for k, v in result.items() if not k.startswith("_")}
    summary = args.out / f"summary-{args.map}.json"
    summary.write_text(json.dumps(full, indent=1) + "\n")
    result["written"].append(str(summary))
    capped = _capped(result)
    print("{\n" + ",\n".join(f" {json.dumps(k)}: {json.dumps(v)}" for k, v in capped.items()) + "\n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
