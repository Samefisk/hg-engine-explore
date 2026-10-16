---
name: design-map-look
description: Design and build new or reshaped HeartGold maps that meet gameplay goals and look like vanilla, from a brief, then prove them. Use for new routes, caves, areas or reshaped terrain; use documentation/map-system/README.md for event/warp/header-only edits.
---

# Design a map that plays well and looks like vanilla

You write the *intent* (a brief); the tools draw shapes the way vanilla does,
name every tile (semantic map), and build it only from vanilla cells copied in
runs. You check it yourself before handing off (step 5). Design truth:
[style-system.md](../../../documentation/map-system/style-system.md),
"Semantic pipeline".

## 1. Pick the look and write the brief

The template map is the palette: its tileset, and its own chunks are the
patterns copied first (Route 29 = 33, Route 44's lake = 46, Union Cave = 107).
Write `data/maps/designs/NNN-name.brief.json`:

```json
{"name": "Twinwood Crossing", "map": 541, "template": 33, "kind": "route", "chunks": [2, 2], "seed": 7,
 "exits": [{"side": "south", "at": 32, "width": 2, "arrival": [32, 57]}, {"side": "north", "at": 22}],
 "wander": 0.7, "width": [3, 6], "clearings": 4, "grass": 6, "pond": 1, "flowers": 5,
 "clumps": 6, "ledge": 1, "path": "exits", "trainers": 2, "items": 2}
```

- `kind`: `route` (tree land, organic edges snapped to 2x2 trees) or `cave`
  (straight corridors and rectangular rooms; rock beyond the wall band is the
  dark outside).
- Gameplay: `exits` (every exit must reach every other), `grass` patches
  (encounters), `ledge` (one-way, placed only where a way around remains),
  `trainers` (spots that see 3+ tiles across the route), `items` (far from it).
- Look: `clearings`, `pond` (+ `pondSize`), `flowers`, `clumps`, `path`
  (`exits`, `full` or `none`), `wander`, `width`.
- A different `seed` gives a different map from the same intent.

## 2. Design

```bash
python3 -B -m tools.maps.style design --brief data/maps/designs/NNN-name.brief.json \
  --out data/maps/designs/NNN-name.semantic.txt --plan data/maps/designs/NNN-name.plan.json
```

It prints the gameplay check (problems, tall grass, trainer and item spots)
and the intent map. Exit code 1 means a gameplay problem (an exit cut off):
change the brief, not the checker. Read the semantic map's `[kind]` layer:
it should read like the template (for caves `R` outside, `#` rim, `W` wall
band, `=` floor). Keep ponds, grass and flower beds rectangular, as vanilla
does; organic outlines ask for edge pieces vanilla does not have.

## 3. Paint

```bash
python3 -B -m tools.maps.style paint --semantic data/maps/designs/NNN-name.semantic.txt --map TEMPLATE --land N [--seeds 2]
```

`--land` is the first land id (whole chunks, in reading order; replace only
lands no other map uses, or append at the archive length). The report
(`build/map-style/report-N.json`) has `paint`: walk/kind/level mismatches,
bad seams, overhang violations (sliced trees, cut walls), bare tiles (tree
shadows without trees) and void tiles; and `labelMatch` (how much of the
design came out as asked). Walk mismatches change where the player can go:
they must be 0 on the route, or fix the design. The showcase maps do all of
this in one step: `python3 -B -m tools.maps.showcase design [--map M]`.

## 4. Wire it into a map

- Existing map: the chunks replace their lands in place.
- New map: `python3 -B -m tools.maps.style new-map --map 541 --template 33
  --land N --start X Z [--chunks W H]` adds a matrix, events with one warp
  tile and a header (IDs 540–591 can be stored). Add NPCs, signs and warps
  at the plan's trainer and item spots with `python3 -B -m tools.maps events`.

Then `python3 -B -m tools.maps lint` must report 0 errors.

## 5. Look, prove, hand off

Look before any build: `python3 -B -m tools.maps.render sheet --map M` and
`overview --map M --top` (PNGs in `build/map-render/`). Any black void beside
a floor, a sliced tree, a cut wall, a pond without its bank or a stair-stepped
patch edge is a failure: change the design (shape, seed) or paint more seeds;
`style resolve` and `style inspect` work on painted reports too.

Build with `hg-engine-delta-build`. Prove walking in melonDS with memory
reads (the showcase probe jumps each designed ledge, fails to climb it, and
walks the route across a chunk seam: `python3 -B -m tools.maps.showcase
probe`). Then capture the sheets (`python3 -B -m tools.maps.showcase shots`)
and inspect every one yourself; every problem becomes a lab defect and a fix
before hand-off. Run `python3 -B -m tools.maps.style.lab scan --map M --write`
and, last, `python3 -B -m tools.maps.status --map M` (hand off only when it
reports nothing to do). Tell the user the map ID, how to reach it and where
to look; offer `python3 -B -m tools.maps.review --map M`. Record their
"looks wrong" notes as defects (`python3 -B -m tools.maps.style.lab defect add
--map M --x X --z Z --note "..."`) so
[improve-map-generator](../improve-map-generator/SKILL.md) learns from them.

The old walk-class path (`style generate --layout`, `precheck`) still runs
for the lab's old benchmark; do not use it for new maps.
