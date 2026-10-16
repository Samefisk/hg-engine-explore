---
name: design-map-look
description: Design and generate new or changed HeartGold map chunks that look like vanilla, from an ASCII layout, then prove them. Use for new routes, areas, rooms or reshaped terrain; use documentation/map-system/README.md for event/warp/header-only edits.
---

# Design a vanilla-looking map chunk

The look comes from construction, and you check it yourself in game before
handing off (step 5):
every piece of geometry is a vanilla tile cell, every new join continues the
polygons on both sides (or is one vanilla has), and pieces that overhang their
tile keep the neighbours vanilla gave them. Your job is the layout, the intent; the solver supplies
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
| `walkableComponents` = 1 | no sealed pockets of standable land |
| `rigidViolations` = 0 | no tree, cliff, ledge or slope cut off from its vanilla neighbours |
| `holes` = 0 | no tile missing the ground vanilla always had |
| `voidExposed` = 0 | no floorless void beside standable land |
| `seamRate` ≥ 0.95 | joins whose textures and heights continue, or that vanilla has |
| game limits | model ≤ 0xF000 bytes, BDHC, polygons (checked on write) |

The solver copies whole vanilla windows (8×8 down to 4×4), so cosmetic
swaps (grass ↔ ground) are allowed and reported as `layoutMatch`. The
report's `hotspots` are the 8×8 areas with the most bad joins: give them to
the user as the first places to look.

If a gate fails, change the layout, never the gates: use shapes the
`examples` show (2-tile tree blocks, ledge rows, grass patches), widen
transitions with `*`, and try more `--seeds`. The realized layout is in
`build/map-style/report-N.json`; diff it against yours.

Once the chunk is wired into a map (step 4), look at it before any build:
`python3 -B -m tools.maps.render sheet --map M` and `overview --map M`
(read the PNGs in `build/map-render/`), and `render.voids` for void beside
reachable ground (see the map README, "Look at it without building"). The
renders match melonDS geometry, so fix what they show now.

Fix one spot without re-rolling the map: `python3 -B -m tools.maps.style
resolve --map M --region X0 Z0 W H [--set X Z C] --seeds 4` (dry run), or
`--hotspots K` for the report's worst 8×8 areas. Cells outside the regions
stay; a region changes only if it strictly improves with no new gate
failure. Read before/after, repeat with `--write`, then re-render. Look at a
tile with `python3 -B -m tools.maps.style inspect --map M --x X --z Z
--radius 2` (cell, vanilla sources, bad joins per side, overhang/hole/void
flags, events). Reports older than stored layouts need `--layout FILE
--relax N` (the showcase maps used `--relax 1`).

## 4. Wire it into a map

- Existing map: the chunk replaces land `N` in place.
- New map: `python3 -B -m tools.maps.style new-map --map 541 --template 33
  --land N --start X Z` adds a 1×1 matrix, an events file with one warp tile
  and a header for map 541 (IDs 540–591 can be stored). Add NPCs, signs and
  real warps with the normal edit loop.

Then `python3 -B -m tools.maps lint` must report 0 errors.

## 5. Prove and hand off

Build with `hg-engine-delta-build`. Prove behavior in melonDS with memory
reads:
teleport onto the start tile, step in two directions, and read
`owctl dev terrain` → `landModels` (the chunk's model name is `gen_NNNN`) and
`events` (hash of your events file). `tools/maps/proof_model.py` is the
template. Then review the look yourself: `python3 -B -m tools.maps.showcase
shots` (or the same capture loop for your map) and inspect every sheet for
black void beside floors, floating or cut-off walls/trees/cliffs, hard-edged
texture squares and moving non-water textures. Each problem becomes a lab
defect and gets fixed before hand-off. Then tell the user exactly where to look: map ID, coordinates and how
to reach it (teleport or warp). Offer the review page, `python3 -B -m
tools.maps.review --map M` (they click a spot and record what looks wrong).
Their visual review closes the task; record any "looks wrong" note as a
defect (`python3 -B -m tools.maps.style.lab defect add --map M --x X --z Z
--note "..."`, or the page's Record defect) so the improvement loop
([improve-map-generator](../improve-map-generator/SKILL.md)) learns from it.
If `inspect` shows nothing wrong at a flagged spot, that is a metric gap:
say so in the defect.
