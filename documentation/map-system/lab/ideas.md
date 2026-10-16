# Hypothesis backlog

Best guess first. Move an idea to the ledger (accepted or rejected, with the
numbers) when tried; add new ones with the evidence that suggests them.

1. **Irregular window boundaries (min-cut).** Most remaining bad joins are
   different materials meeting at a window edge (tree shadow beside plain
   grass, wall beside grass). Let a new window keep part of the old content:
   label each tile old/new, minimize incompatible joins + layout cost along
   the boundary (dynamic programming on a monotone cut per side, as in image
   quilting).
2. ~~Accept sideways moves.~~ Accepted 2026-10-15 (0.932 → 0.953). Next
   step tried: simulated annealing, rejected (T=1: +0.0006, noise; T=3:
   worse). Still open: re-tune `refineRounds` now that rounds keep making
   progress.
3. **Boundary-first placement.** Place windows along class boundaries
   (shorelines, tree lines, ledge ends) first, then fill uniform interiors,
   which have many equivalent candidates.
4. ~~Frequency-weighted choice.~~ Rejected 2026-10-15 (0.953 → 0.940, 6
   hard failures): common cells are plain interiors; boundaries need rare
   transition pieces. The opposite (prefer rare cells at class boundaries)
   is untested.
5. **Solver-side boundary freedom.** Treat layout tiles on a class boundary as
   "this class or a decorated edge" at a small cost, as `--relax` does for
   blocked tiles, so tree lines and shores can use vanilla edge pieces.
6. **Speed.** Incoming-overhang lists and seam tables per region are rebuilt
   for every attempt; caching them per refinement round would allow larger
   candidate pools within the 2.5× time limit.

7. **Lake tileset (tileset 8).** Mirrorlake and held-out lake chunk 87 are the
   worst cases (0.90–0.94 joins under the side-bond judge); shoreline pieces
   are rare and long. Try shoreline-first placement or larger windows for
   `~`/`*` regions only.
8. **Speed.** Side bonds and polish made a 2x2-chunk map take ~9 minutes per
   12 seeds; profile `_rigid_cost` and `evaluate` (pure-Python loops).

9. **Animated water, safely.** Composed geometry drawn through a textured
   animated slot crashed the game (ARM9 abort during a field reload;
   reproduction in the ledger entry of 2026-10-16T03:4x). Slots are now
   untextured, so generated water is static. Find the mechanism (compare a
   vanilla chunk's animated water polygons with ours: UV range, strip
   layout, texture matrix flags) before re-enabling.
10. **Water edges (D5).** Mirrorlake: water rectangles with black bars along
   their north edges and no shoreline. heightBreaks only compares floor with
   floor; extend the judge to floor-water edges (water surface vs bank
   height, closed by a bank face), then the solver.

11. ~~Polish rigid weight.~~ Accepted 2026-10-16 (0.842 -> 0.851, hard
   failures 38 -> 33). Remaining overhangs sit mostly in echo (7/2) and
   route-land9; the same trade for heightBreaks/criticalMismatches (polish
   weights for those terms, rank guard unchanged) is the untested follow-up.

Judge ideas (need a defect or a vanilla false alarm first):

- **2x2 junctions (D3).** Pairwise joins can all be vanilla-observed while
  a corner is not: a path's top/bottom edge pieces meeting plain grass at
  the path's end. Score each tile corner by its four edge profiles: seen in
  vanilla, or all four joins continuous.
  Measured 2026-10-16, not adoptable as stated: with the chunk held out,
  vanilla's own non-continuous corners are unseen 76% of the time (12
  chunks per tileset), versus 26%/30%/49% on maps 541/542/543, so the
  check would flag vanilla more than our output. The exact 8-profile
  signature is too specific (profiles carry texture coordinates). A usable
  version needs a coarser corner key (material and height per quadrant).
  Also, D3's spot (541 at 30,11) is plain grass in the current map; find a
  current path end before using D3 as the target.
- **Render void (D2).** `tools.maps.render.voids` sees what the tile
  metrics miss: black void beside reachable ground, from above and from the
  camera's pitch. Vanilla routes, towns and caves score 0 (38-map sample;
  two indoor rooms keep 9–15 edge tiles by design). The showcase maps score
  6/67, 19/41 and 34/109 (top/camera), and it flags (18–19, 47) next to D2.
  It needs the ROM's textures only for colour; the coverage itself is
  geometry, so a judge version can rasterize kit cells without textures.
  Adopt with `judge-check` on every tileset, then rebaseline.
- **Area statistics (D4).** Echo Cavern fills big `T` areas with flat rock
  tops; compare the share of visible top-surface material per class against
  vanilla.

- Vertex-colour continuity: Twinwood showed lighter grass rectangles with
  hard edges (baked lighting differs between joined cells); edge profiles do
  not compare vertex colours yet. Seen in my own review, 2026-10-16.

- Sample-level join compatibility (material pairs seen in vanilla at the same
  height) would accept many joins the profile rule rejects; adopt only if the
  user's review shows those joins look fine.
- Visible-area weighting: count bad joins within the camera's view of
  walkable tiles more than joins deep inside tree walls.
