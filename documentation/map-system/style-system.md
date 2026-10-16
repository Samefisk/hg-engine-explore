# Map style system

How agents make new map chunks that look like HeartGold without anyone
judging screenshots: never invent geometry, only recombine vanilla pieces in
arrangements vanilla already uses, then measure how vanilla-like the result is.

```
vanilla chunks ──slice──► kit (per map tileset)        tools/maps/style/kit.py
                            cells: geometry + tile attrs + corner heights
                            adjacency: which cell sits next to which
layout (ASCII, by an LLM) ──► solver (patch quilting + refinement)  style/quilt.py, seams.py
                            ──► cell grid ──► compose: NSBMD + tiles   style/kit.py
                                           ──► BDHC from corner heights  style/bdhc_gen.py
                            ──► score vs vanilla (joins, overhangs, holes) style/score.py
                            ──► improvement loop (bench, ledger, defects)  style/lab.py
                            ──► land override ──► lint ──► build ──► in-game proof
```

## Interfaces (all code in `tools/maps/style/`)

Units: world units, 16 per tile, 512 per chunk. Model X/Z of tile (x, z) spans
`-256 + 16x … -256 + 16(x+1)` (same for z). Heights are world-unit floats.

### Kit (`kit.py`)

`build_kit(source, map_tileset: int) -> dict` slices every vanilla land chunk
whose maps use an area with that `mapTileset` (a/0/4/2 → a/0/4/4):

```python
kit = {
  "tileset": int,                 # mapTileset (a/0/4/4 member)
  "areas": [int],                 # area data ids using it
  "materials": {key: material},   # deduplicated by content; nsbmd material dicts
  "cells": [{                     # one entry per distinct cell
      "sig": str,                 # content hash: polys + attrs + corners
      "cls": str,                 # layout class, see below
      "behavior": int, "collision": bool, "secondary": int,
      "corners": [nw, ne, se, sw],    # floor height at the 4 tile corners
      "polys": [{"mat": key, "verts": [[x, y, z, s, t, nx, ny, nz, r, g, b], ...]}],
          # x/z relative to the cell's NW corner (0..16, may overhang),
          # y absolute; s/t texels or None; normal or color may be None
      "count": int,               # occurrences in vanilla
  }],
  "chunks": {land_id: [[cell index] * 32] * 32},   # vanilla placement
}
```

Polygons are assigned to the cell containing their centroid (overhanging
canopies stay whole). Flat ground polygons wider than one tile are clipped
per tile with interpolated UVs/colors so ground can be recombined.

`compose(kit, grid, name) -> (model_bytes, tiles_spec, corners)` stitches the
cells of a 32×32 grid of cell indices into one NSBMD (via `tools.maps.nsbmd`),
a `tiles` spec (codecs format) and a 32×32 grid of corner heights.

Pass `anim_materials=area_animation_materials(source, area["dynamicTextureType"])`
(`generate` does). An area's land texture animation (`a/1/4/0`, AreaData
field 3, named `dynamicTextureType` in the area codec) is bound to every land
model **by material index**, not by name (`map_prop_render.c`
`AreaMapAnimation_InitAnimObj`). Vanilla models therefore start their
material table with exactly the animation's materials (outdoor: `pond_on
swave_p pond_edge sea_line02 sea_un sea_on river river_r`; caves: `river
river_r sea_line02 sea_un sea_on`), used or not. Compose reserves those
slots; without them, paths, cliffs and flowers scrolled like water. The
slots hold untextured records (as most vanilla chunks do) and drawn water
follows them, so generated water is static: composed geometry drawn through
a textured animated slot crashed the game during a field reload (see the
lab ledger, 2026-10-16). Lint rule `land-anim-order` checks every land model
a map uses.

### BDHC (`bdhc_gen.py`)

- `bdhc_from_corners(corners) -> dict`: codecs-format BDHC spec of planar
  plates covering every tile (flat or single-axis slopes), merged where
  coplanar, with valid strips and access list.
- `height_at(bdhc, x, z) -> float | None`: the game's height query (port of
  `src/field/bdhc.c` in `.codex-reference/pokeheartgold-full`).

### Why quilting, not tile-by-tile collapse

Vanilla chunks are modelled scenes, not tile sets. Tileset 2 (Route 29 and
neighbours) has 21 chunks and 5,846 distinct cells, most of which only ever
sit next to their original neighbours. Tile-level wave function collapse over
that vocabulary took ~6 minutes to fill a plain field and could not solve
ordinary layouts. Quilting copies whole 8×8, 6×6 or 4×4 vanilla windows
(13,125 windows for tileset 2), so most of every chunk is a real vanilla
arrangement and only window seams are new. With geometry-aware refinement a
32×32 chunk takes about 5–15 seconds per seed.

### Layout and solver (`layout.py`, `quilt.py`, `wfc.py`)

A layout is 32 lines of 32 characters. Classes:

| Char | Class | Cell rule |
|---|---|---|
| `.` | open ground | walkable, behavior not grass/water/ledge |
| `,` | tall grass | behavior 2 or 3 |
| `~` | water | surfable behavior |
| `T` | blocked | collision set (trees, rocks, cliffs, walls) |
| `v` `^` `<` `>` | ledge | jump south/north/west/east |
| `*` | anything | no constraint |

`quilt.solve(kit, layout, seed)` places windows in reading order, choosing
each by weighted layout mismatch (`quilt.mismatch_cost`: grass/ground swaps
are cheap, walls/water cost more, ledges most), incompatible joins and
broken overhangs, then refines: every bad tile gets a region re-solved around
it against all four sides (largest window first, down to single cells),
accepted only when the region's cost drops. Settings (weights, window sizes,
search widths) are in `solver_config.json`, owned by the improvement loop
([lab/README.md](lab/README.md)).

### What makes a join look right (`seams.py`)

The first showcase maps passed every tile-level gate and still looked broken
in game: holes, hard-edged path squares, cliffs and tree rows cut off,
floating cave walls. The cause: visuals are polygons, not tiles. Trees,
cliffs, ledges and sloped ground belong to the tile under their centroid and
reach into neighbours; flat ground is clipped per tile, so its texture only
continues if the neighbour's ground continues it. Union-find edge labels
(the old rule) were transitive, so almost any ground met any ground.

`seams.Seams(kit)` learns three geometric rules from vanilla:

| Rule | Learned | A placement breaks it when |
|---|---|---|
| Edge profiles | each tile side sampled at 8 points (material, height, texture coordinate modulo its repeat) plus vertical edges standing on it | facing sides are neither equal (non-empty) nor a profile pair vanilla has; no transitive closure |
| Rigid overhangs | offsets a cell's polygons reach into, and which cells vanilla had there | the cell at that offset is not one vanilla had |
| Ground feeders | cells whose ground always came from a neighbour's polygon | the feeding neighbour is missing (counted as a hole) |

Vanilla chunks score 0 on all three by construction, so every number is
"how far from vanilla", not a judgement of taste.

`wfc.solve(kit, layout, seed, edges=...)` is the old tile-level solver (wave
function collapse over union-find edge labels). It is kept only to pin a
chunk's border to existing neighbour chunks (`edges`); its output must still
pass the gates below.

### Score (`score.py`)

`score(kit, grid, rows) -> dict`, gated by `score.GATES`:

| Gate | Meaning |
|---|---|
| `criticalMismatches` = 0 | no wall, water or ledge where the layout wants a path, or the reverse |
| `walkableComponents` = 1 | standable land forms one region (water and void excluded) |
| `rigidViolations` = 0 | no tree, cliff, ledge or slope cut off from its vanilla neighbours |
| `holes` = 0 | no tile missing ground vanilla always had there |
| `voidExposed` = 0 | no floorless void tile beside standable land |
| `seamRate` ≥ 0.95 | joins whose edge profiles continue or that vanilla has; the rest can show as texture or height breaks |

`hotspots` lists the 8×8 areas with the most problems: where to look first
in game. Informational: `layoutMatch`, `pairRate`, `windowRate`.

The gates are necessary, not sufficient: the user's in-game review is the
final judge, and every "looks wrong" note becomes a defect the metrics must
detect (see the lab).

### Local edits (`edit.py`)

Fix one spot without regenerating (and re-rolling) the whole map:

```bash
python3 -B -m tools.maps.style resolve --land 682 --hotspots 2 --seeds 4      # dry run
python3 -B -m tools.maps.style resolve --map 541 --region 24 8 8 8 --set 30 11 T --write
python3 -B -m tools.maps.style inspect --map 543 --x 16 --z 44 --radius 2
```

Coordinates: `--land N` uses the report's whole-grid space (the multi-chunk
grid `generate` solved; chunk (cx, cz) is x 32cx…, z 32cz…, lands in reading
order from the report's `land`). `--map M` uses matrix-wide tile coordinates,
as in events.

`resolve` loads the report holding the land and pins every cell outside the
regions (`--region X0 Z0 W H`, repeatable; `--hotspots K` adds the report's
top K hotspots). Per region and seed it tries the current cells and a fresh
placement per `placeSizes`, then `quilt` refinement and polish with windows
kept inside the region, so joins and overhangs with the pinned surroundings
count. `--set X Z C` edits the intent inside a region first. Candidates rank
like `generate` (`cli.rank`), then by the solver's problems within
reach + 1 of the region. A region changes only if that rank strictly
improves and no gate fails that passed before (judged with the old and the
edited intent); otherwise it keeps its cells. Output: before/after score and
gates, per region its problems, changed tiles and realized layout.
`--write` composes with `cli.write_lands` (the same game-limit checks as
`generate`, all chunks checked before any file is written) and updates the
report (`grid`, `score`, `hotspots`, `realizedLayout`, `layout`, a `resolves`
entry). It is refused for a report whose grid was never written, and when a
land's `model.nsbmd` on disk no longer matches the report (checked against
its `modelHashes`, or the re-composed grid for older reports), so a later
generate or hand edit is never reverted. Files and the report are replaced
through temporary files.

`generate` now stores the relaxed intent as `layout` (and `relax`) in the
report; older reports need `--layout FILE --relax N` (the showcase maps used
`--relax 1`).

`inspect` (Python: `edit.inspect_tile(map_id, x, z, radius=0, land=None)`)
returns one tile as JSON: map, land and grid coordinates; the game's
behavior, collision, secondary and BDHC corner heights; events on the tile
(objects, warps, bgs, coord triggers) from the override tree; and, for a
generated land, the wanted and realized layout char, the cell (index, sig,
attrs, corners, vanilla count and first source placements), each side's join
(`profilesJoin` is the judge's rule, `vanillaPair` an exact vanilla
neighbour), overhang violations, hole, void, bare edge, its hotspot and
`matchesGame`. `--radius R` adds wanted/realized/problem rows around it.
Vanilla lands get the game data only. Kits, seam tables, reports and the
override tree are cached in-process (about 1 s first call, ms after).

After any `--write` the showcase maps need `python3 -B -m tools.maps.showcase
write` again (it restores their warp panels), then `lint`, as after `generate`.

The style tools need numpy on the host; they never run inside the ROM build.
