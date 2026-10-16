# Showcase maps: how to view and test

Three maps designed by the [semantic pipeline](style-system.md#semantic-pipeline-current)
from briefs of gameplay intent in `data/maps/designs/` (brief, semantic map
and plan per map), then painted with vanilla cells. They replaced the first
generation (walk-class layouts in `data/maps/layouts/`, flat rock slabs, tree
stumps and holes) on 2026-10-16. Every piece of geometry is copied from
vanilla HeartGold; the tools check walkability, overhangs, black void (in the
painter and with the renderer), and a melonDS walk-through proves warps,
ledges and chunk seams. **How they look is for you to judge**, and the
review below lists what is still wrong.

## Getting there (normal play, no dev tools)

Continue your save. You start in Cherrygrove City, in front of the Pokémon
Center door. Three invisible warp panels sit two steps south-west of you:

```
            [ Pokémon Center door ]
                     (you)
  .  A  .  B  .  C           A = Twinwood Crossing (541)
     ^ step onto these        B = Mirrorlake Basin (542)
                              C = Echo Cavern (543)
```

From the start: walk **down 1**, then **left 5 / 3 / 1** for A / B / C,
then **down 1** onto the panel. (Walking left along the panel row itself
would step on C first.) Cherrygrove tiles: (559, 394), (561, 394), (563, 394).

In each map you arrive on a plain tile. The way back is the tile **directly
south of where you arrive**: step down once to return to Cherrygrove (you
land one tile north of panel B).

## The maps and what each one tests

| Map | Brief (template, size) | Gameplay in the plan |
|---|---|---|
| 541 Twinwood Crossing | Route 29 look, 2×2 chunks, winding route south → north | route through four clearings, a pond with its own clearing, tall-grass beds, flower beds, tree clumps, a one-way ledge with a way round, 2 trainer spots (Route 29 residents stand there), 2 item spots |
| 542 Mirrorlake Basin | Route 44 lake look, 2×1 chunks, west → east | two rectangular ponds, tall grass, a ledge, sand paths at the exits |
| 543 Echo Cavern | Union Cave look, 1×2 chunks, south → north | straight corridors and rooms with wall bands, rims and dark outside, rocks |

Paint results (`build/map-style/report-NNNN.json`): 0 walk mismatches on all
three; render-void tiles after repair 0 / 1 / 1; labels realised as designed
98 % / 96 % / 99.9 %.

## Known defects (agent review of the in-game sheets, 2026-10-16)

Recorded in the lab (`lab defect check`):

- D9, D10 (541): tree shadows without their tree ("stumps") below some clumps,
  and trees sliced at belt edges. Tree belts from different vanilla sources do
  not line up; the labels do not yet say which part of a tree a tile is.
- D11, D12, D13 (542): stray tree-shadow wedges, the south pond's bank broken
  (black strip, seam lines in the water), and void below the south border.
- D14 (543): one black sliver on a wall top in the south-west room.

## What the melonDS walk-through proved

`python3 -B -m tools.maps.showcase probe` (memory reads only) on the built
`test.nds` with your `test.sav`, 2026-10-16: passed. Each Cherrygrove panel
warps to its map's arrival tile, you stay there, the loaded chunks report the
generated models (`gen_0678`/`gen_0679`, `gen_0680`, `gen_0683`), and the
return panel brings you back. The plan's goals: Twinwood's and Mirrorlake's
ledges jump down and refuse the climb back; all three maps are walked across
a chunk seam on the same map. Echo Cavern's ledge did not survive refine (no
ledge goal for it).

## What was not checked by tools

- How it looks: textures at seams, lighting, anything visual.
- Wild encounters in the new maps: the headers use the template routes'
  encounter tables, but hg-engine's overworld Pokémon spawning is keyed by
  map ID and does not list 541–543, so overworld Pokémon may not appear.
- Map names on screen show the template's location (Route 29, Route 44,
  Union Cave).

## Redesign or remove

```bash
python3 -B -m tools.maps.showcase design [--map 541]   # brief -> semantic map + plan -> painted lands
python3 -B -m tools.maps.showcase write     # panels, return warps, NPCs, signs: ALWAYS after design
python3 -B -m tools.maps lint
python3 -B -m tools.maps.showcase probe     # after a build: panels, ledges and seams in melonDS
python3 -B -m tools.maps.showcase shots     # screenshot sheets for the map-look review
python3 -B -m tools.maps.render sheet --map 543   # the same kind of sheet offline, no build
python3 -B -m tools.maps.review --map 543         # click-to-inspect page; records defects
```

Change a map by editing its brief (`data/maps/designs/NNN-name.brief.json`;
a new `seed` gives a different map from the same intent), then redesign.

Something looks wrong? Record it so the improvement loop learns from it:
`python3 -B -m tools.maps.style.lab defect add --map 542 --x 40 --z 12 --note "..."`.

To remove everything, delete `data/maps/` entries for land 5, 676–683,
events 64 and 491–493, matrix 288–290 and headers 541–543, and
`data/maps/designs/`, then rebuild.
