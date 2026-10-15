# Map style system

How agents make new map chunks that look like HeartGold without anyone
judging screenshots: never invent geometry, only recombine vanilla pieces in
arrangements vanilla already uses, then measure how vanilla-like the result is.

```
vanilla chunks ──slice──► kit (per map tileset)        tools/maps/style/kit.py
                            cells: geometry + tile attrs + corner heights
                            adjacency: which cell sits next to which
layout (ASCII, by an LLM) ──► solver (patch quilting; WFC for pinned seams)  style/quilt.py, wfc.py
                            ──► cell grid ──► compose: NSBMD + tiles   style/kit.py
                                           ──► BDHC from corner heights  style/bdhc_gen.py
                            ──► score vs vanilla (fidelity, budgets)     style/score.py
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
arrangement and only window seams are new. It solves a full layout in about
1 second per seed.

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
are cheap, walls/water cost more, ledges most) plus incompatible seams, then
repairs single tiles that fit all four neighbours. Seam compatibility uses
edge labels: union-find over every vanilla neighbour pair, so two cells may
touch when their facing edges share a label.

`wfc.solve(kit, layout, seed, edges=...)` is the tile-level solver (wave
function collapse with arc consistency over the same edge labels). Use it
only to pin a chunk's border to existing neighbour chunks (`edges`); it is
slow and needs generous `*` transitions.

### Score (`score.py`)

`score(kit, grid, rows) -> dict`, gated by `score.GATES`:

| Gate | Meaning |
|---|---|
| `criticalMismatches` = 0 | no wall, water or ledge where the layout wants a path, or the reverse |
| `walkableComponents` = 1 | open tiles form one region |
| `edgeRate` ≥ 0.93 | neighbour pairs joined along a vanilla edge label; the rest are seams where a visible join can appear |

Informational: `layoutMatch` (cosmetic swaps allowed), `pairRate` and
`windowRate` (exact vanilla pairs and 2×2 windows: how much is copied).
Measured on the trial layout: edgeRate 0.93–0.96, layoutMatch 0.92–0.96,
windowRate 0.65–0.68, 0 critical mismatches.

The style tools need numpy on the host; they never run inside the ROM build.
