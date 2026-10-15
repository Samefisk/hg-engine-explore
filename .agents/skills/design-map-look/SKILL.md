---
name: design-map-look
description: Design and generate new or changed HeartGold map chunks that look like vanilla, from an ASCII layout, then prove them. Use for new routes, areas, rooms or reshaped terrain; use documentation/map-system/README.md for event/warp/header-only edits.
---

# Design a vanilla-looking map chunk

Agents do not judge looks from images. The look comes from construction:
every piece of geometry is a vanilla tile cell, and every neighbour pair is one
vanilla already uses. Your job is the layout, the intent; the solver supplies
the craft. Design truth: [style-system.md](../../../documentation/map-system/style-system.md).

## 1. Learn the tileset

Pick an existing map whose look you want (its area tileset is the palette):

```bash
python3 -B -m tools.maps.style examples --map 33 --count 4
```

Read the class layouts: how thick tree walls are, where grass sits relative to
paths, how ledges run, how water edges meet land. Copy those habits.

## 2. Write the layout

32 lines × 32 characters, saved under `build/map-style/` (layouts are
scratch; the committed result is the override in `data/maps/`):

- `.` open ground, `,` tall grass, `~` water, `T` blocked (trees, rocks,
  cliffs), `v ^ < >` one-way ledges, `*` let the solver choose.
- Border a standalone chunk with `T` at least two tiles thick.
- Put `*` between classes where vanilla uses decorated edges (shorelines,
  tree lines, grass borders). Or pass `--relax 1` to free blocked tiles that
  touch other classes.
- Keep paths at least 2 tiles wide; encounter grass in patches, not stripes.
- Leave the warp/start tile on `.`.

## 3. Generate and read the score

```bash
python3 -B -m tools.maps.style generate --layout build/map-style/L.txt --map 33 --land N --seeds 16
```

`--land` is an existing land id to replace (only if no other map uses it, see
`checkout` refusals) or the archive length to append. The command keeps the
best seed that passes every gate:

| Gate | Meaning |
|---|---|
| `criticalMismatches` = 0 | no wall, water or ledge where you asked for a path, or the reverse |
| `walkableComponents` = 1 | no sealed open pockets |
| `edgeRate` ≥ 0.93 | joins between copied vanilla windows use edges vanilla also joins |
| game limits | model ≤ 0xF000 bytes, BDHC, polygons (checked on write) |

The solver copies whole vanilla windows (8×8 down to 4×4), so cosmetic
swaps (grass ↔ ground) are allowed and reported as `layoutMatch`. Every
seam below 1.0 `edgeRate` is a place where a texture join may show: list
the lowest-scoring area for the user's visual review.

If a gate fails, change the layout, never the gates: use shapes the
`examples` show (2-tile tree blocks, ledge rows, grass patches), widen
transitions with `*`, and try more `--seeds`. The realized layout is in
`build/map-style/report-N.json`; diff it against yours.

## 4. Wire it into a map

- Existing map: the chunk replaces land `N` in place.
- New map: `python3 -B -m tools.maps.style new-map --map 541 --template 33
  --land N --start X Z` adds a 1×1 matrix, an events file with one warp tile
  and a header for map 541 (IDs 540–591 can be stored). Add NPCs, signs and
  real warps with the normal edit loop.

Then `python3 -B -m tools.maps lint` must report 0 errors.

## 5. Prove and hand off

Build with `hg-engine-delta-build`. Prove in melonDS (no screenshots):
teleport onto the start tile, step in two directions, and read
`owctl dev terrain` → `landModels` (the chunk's model name is `gen_NNNN`) and
`events` (hash of your events file). `tools/maps/proof_model.py` is the
template. Then tell the user exactly where to look: map ID, coordinates and how
to reach it (teleport or warp). Their visual review closes the task; record
any "looks wrong" notes against the layout, not the gates.
