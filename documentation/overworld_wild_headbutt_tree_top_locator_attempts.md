# Headbutt Tree-Top Locator Attempts

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Tracks target semantics for headbutt/tree-top/canopy locations.
- Archive headbutt rows are sparse hints, not canonical full tree footprints.
- Generated tree-top targets must be constrained by live blocked canopy surface validation to avoid bad rows.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 76 | 215 | Direct Validated Route 29 Test Perch |
| 77 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 78 | 237 | Allow Two-Tile Final Tree-Top Landings In Mankey Path Search |
| 79 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 80 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 81 | 230 | Direct Mankey Tree-Top Lifted-Row Fallback |
| 82 | 231 | Revert Shared Row Lift And Keep Direct Fallback Only |
| 84 | 227 | Restore Archive MinY Tree-Top Logic After Too-High Row |
| 85 | 228 | Sparse Archive Tree-Top Row Lift |
| 86 | 234 | Lift Single-Row Mankey Footprints |
| 87 | 234 | Lift Single-Row Mankey Footprints |
| 88 | 229 | Live Blocked-Row Tree-Top Confirmation |
| 92 | 242 | Charmander Canopy Locator Probe |
| 93 | 260 | Charmander Probe Fallback Marker |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 95 | 262 | Charmander Probe Uses Normal Spawn Slot From Birth |
| 96 | 259 | Boundary-Derived Headbutt Tree-Top Locator |
| 97 | 242 | Pair Tree-Top Candidates And Derive Top Row From Archive Bottom |
| 98 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 99 | 238 | Generic Headbutt Tree-Top Location Filter |
| 102 | 197 | Route 29 Top-Cap Coordinate Probe |
| 103 | 198 | Route 29 Upper Top-Cap Coordinate Probe |
| 104 | 199 | Actual Headbutt Anchor With Render-Only Tree-Top Offset |
| 105 | 200 | Exact Headbutt Tile Occupancy, No Graphic Offset |
| 106 | 201 | Guaranteed Forced Headbutt Mankey Spawn |
| 107 | 202 | Spawn On Row Above Headbutt Tree Footprint |
| 108 | 203 | Lower Tree-Top Test Tile And Preserve Forced Idle Visibility |
| 116 | 236 | Mankey Tree-Top Effect-Layer Bubble Probe |
| 117 | 237 | Cache Mankey Tree-Top Archive Predicate |
| 118 | 238 | Gate Mankey Bubble Probe On Final Tree-Top Landing |
| 119 | 239 | Align Mankey Tree-Top Settled Rows With Target Rows |
| 120 | 240 | Strict Top-Row Mankey Target Set With Broad X Candidates |
| 121 | 241 | Pair-Derived Mankey Tree-Top X Footprints |
| 122 | 242 | Exposed Mankey Tree-Top Rows With Pair-Derived X |
| 123 | 243 | Full Mankey Tree-Top Vertical Band |
| 124 | 244 | Direct Cardinal Mankey Tree-Band Target |
| 125 | 245 | Coordinate-Latched Mankey Tree-Top Settlement |
| 126 | 246 | Prioritize Strict Structural Mankey Tree Tops |
| 127 | 247 | Strict-Only Mankey Tree-Top Final Targets |
| 128 | 248 | Use Archive Top Row For Mankey Tree Tops |
| 129 | 249 | Target Two Tiles Above Headbutt Archive Row |
| 133 | 253 | Down-First Mankey Tree-Top Target Selection |
| 134 | 254 | Restore Archive MinY As Strict Tree-Top Row |
| 135 | 255 | Snap Final Canopy Landing After Partner Restore |
| 136 | 256 | Skip Final Mankey Tree-Top Partner Restore |
| 137 | 257 | Re-enable Tree-Top Anchored Effect Probe After Movement Fix |
| 138 | 258 | Late-Draw Mankey Through Field-Effect Render Callback |
| 139 | 234 | Direct Straight Headbutt Tile Target For Mankey |
| 140 | 235 | Dedicated HEADBUTT_TREE_TOPS Archive Target Set |
| 141 | 233 | Split Mankey Tree Targets From Settled Perches |
| 142 | 230 | Mankey 2x6 Headbutt Tree Top-Row Targeting |
| 144 | 232 | Include Exposed Archive Top Row For Mankey Tree Targets |
| 264 | 216 | Remove Forced Mankey Canopy Tests And Restore Land Mankey |
| 265 | 217 | Mankey Chill Jump To Two Tiles Above Headbutt Tree |
| 266 | 218 | Mankey Multi-Jump Pathfinding To Tree-Top Target |
| 267 | 219 | Mankey Lands On Headbutt Tree Top Row |
| 268 | 220 | Mankey Tree-Top Render Height Lift |
| 269 | 221 | Mankey Tree-Top Priority Flag Probe |
| 270 | 222 | Mankey Failed Tree-Path Backoff And Target Grid |
| 271 | 223 | Mankey Tree-Top Draw-Mode Probe |
| 272 | 232 | Mankey Low Land Row Tree-Top Correction |
| 273 | 233 | Mankey 2x3 Footprint Top-Row Targets |
| 274 | 235 | Direct Two-Tile Mankey Tree-Top Final Hop |
| 275 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 276 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 277 | 238 | Generic Headbutt Tree-Top Location Filter |
| 278 | 239 | Accept Single-Column Headbutt Tree-Top Archive Entries |
| 279 | 240 | Add Obscured Vertical Tree-Top Stack Rows |
| 280 | 241 | Filter Generated Tree-Top Rows By Blocked Canopy Surface |

## Original Attempt Sections

### Attempt 215: Direct Validated Route 29 Test Perch

Idea:

Attempt 214 still fell back to the same left-edge staging, which means the ahead/right tree candidate is probably failing one of the normal pair-resolution checks. For the forced verifier only, try a direct real Route 29 headbutt tree coordinate and a specific adjacent perch coordinate before the scored pair list. Keep normal validation on the perch tile so this does not place Mankey on blocked terrain.

Why this is new:

- Attempts 210, 213, and 214 all relied on the fixed pair resolver choosing a valid pair.
- This uses the actual Route 29 headbutt source data but bypasses the pair resolver's fallback behavior for the test harness only.
- No previous attempt directly validates and uses a specific Route 29 real-tree/perch coordinate before pair scoring.

Implementation plan:

- Add a forced test perch table containing Route 29 tree `594,389` with perch `594,390`.
- In `OverworldWildSpawns_TryPickFixedRoute29CanopyTestSpawnPosition`, test these direct perches first, requiring the tree tile to be headbutt, the perch to pass `OverworldWildSpawns_IsHeadbuttLandingTile`, and the perch to be in despawn range.
- Build and capture another dense headless sequence.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test433.nds`.

Runtime result:

- User reported the exact same two-tiles-above-tree situation still did not move.

### Attempt 236: Use Prepared Internal Jump For Two-Tile Mankey Final Target

Learning:

- A read-only explorer agreed the picker should be able to find the Route 29 two-tile-down target when it is aligned with one of the marked headbutt tree-top tiles.
- The weak point in Attempt 235 was the executor: it used stock `Jump*2` for the distance-2 final hop.
- Earlier canopy-hop investigation showed stock `Jump*2` is not the stable long-hop carrier we want here; the working Mankey long-hop path uses the prepared internal jump carrier.

Implementation shape:

- Keep the Attempt 235 Mankey-only distance-2 target selection and staging rules.
- Relax `OverworldWildSpawns_GetCanopyLongJumpTiming` so timing can be calculated for distance `2` after the caller approves it.
- Move the minimum-distance rule into `OverworldWildSpawns_StartCanopyLongJumpCommand`, using `2` only when the active slot is Mankey and `sOverworldWildMankeyTreeTopLandingExpected` is set.
- Remove the stock `Jump*2` distance-2 fallback from `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, so the prepared internal jump path handles the final two-tile landing.
- Do not change the headbutt-tree footprint resolver.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test434.nds`.

Runtime result:

- User reported the issue still remained: Mankey still did not take the two-tile-down tree-top landing.

### Attempt 237: Allow Two-Tile Final Tree-Top Landings In Mankey Path Search

Learning:

- Attempt 236 ruled out the distance-2 jump executor as the only problem.
- The direct tree-top candidate picker allows distance-2 landings, but the broader Mankey tree-top path search still only iterated distances 3-8.
- If the direct picker misses the visually obvious target for any coordinate/classification reason, the pathfinder would refuse to consider the exact final two-tile landing and record another path failure.

Implementation shape:

- In `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`, lower the distance loop to `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_MIN_HOP_TILES`.
- Keep distance-2 hops valid only when the candidate is already marked in `sOverworldWildMankeyHeadbuttTreeTopTargets`.
- Keep intermediate/non-final canopy path nodes constrained to the normal `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES` minimum, so this does not reintroduce random short canopy hops.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_MIN_HOP_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test435.nds`.
- Runtime result: pending user test.

### Attempt 236: Use Prepared Internal Jump For Two-Tile Mankey Final Target

Runtime result from `test433.nds`:

- User reported the exact same two-tiles-above-tree situation still did not move.

Learning:

- A read-only explorer agreed the picker should be able to find the Route 29 two-tile-down target when it is aligned with one of the marked headbutt tree-top tiles.
- The weak point in Attempt 235 was the executor: it used stock `Jump*2` for the distance-2 final hop.
- Earlier canopy-hop investigation showed stock `Jump*2` is not the stable long-hop carrier we want here; the working Mankey long-hop path uses the prepared internal jump carrier.

Implementation shape:

- Keep the Attempt 235 Mankey-only distance-2 target selection and staging rules.
- Relax `OverworldWildSpawns_GetCanopyLongJumpTiming` so timing can be calculated for distance `2` after the caller approves it.
- Move the minimum-distance rule into `OverworldWildSpawns_StartCanopyLongJumpCommand`, using `2` only when the active slot is Mankey and `sOverworldWildMankeyTreeTopLandingExpected` is set.
- Remove the stock `Jump*2` distance-2 fallback from `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, so the prepared internal jump path handles the final two-tile landing.
- Do not change the headbutt-tree footprint resolver.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test436.nds`.

Runtime result:

- User clarified there was no bug here: the visible case was a two-tile hop, and Mankey should not be expected to make a two-tile canopy hop.

### Attempt 237: Revert Two-Tile Mankey Canopy-Hop Relaxation

Learning:

- Attempts 235 and 236 were based on a bad premise: treating the two-tile-down case as a valid Mankey tree-top hop.
- The intended canopy-hopper rule remains 3-8 tiles. A two-tile target should be ignored or reached through another valid hop/path, not by adding a special two-tile final landing exception.

Implementation shape:

- Remove the Mankey-specific `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_MIN_HOP_TILES` exception.
- Restore direct Mankey tree-top candidate selection to the normal `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES` minimum.
- Restore Mankey tree-top path search to 3-8 tile hops only.
- Restore canopy-hop staging, prepared long-jump timing, and execution to reject distances below the normal long-jump minimum.
- Remove the special pending-hop branch that allowed distance-2 final Mankey tree-top movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test440.nds`.

Learning:

- Pending.

## 2026-06-09 Follow-Up: `test432.nds`

Runtime result from `test431.nds`:

- User reported that Mankey was still two tiles too far down for same-row Route 29 headbutt-tree entries.

Adjustment:

- Single-row two-column Mankey footprint entries are now treated as lower/contact-row data and lifted by two tiles.
- Multi-row entries still use their minimum Y row as the top row to avoid reintroducing the earlier obstructed-tree “one/two tiles too high” regressions.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test432.nds`.

Runtime result:

- Pending user test.

### Attempt 230: Direct Mankey Tree-Top Lifted-Row Fallback

Idea:

The user reported no visible change after the live blocked-row lift. That means `IsMetatileBlockedAt` is not a useful discriminator for the specific Route 29 tree-top row mismatch. Do not repeat the rejected global `minY - 1` or `minY - 2` strict tree-top definitions. Instead, keep the shared `HEADBUTT_TREE_TOPS` definition stable, but let the direct Mankey tree-top jump picker consider up to two rows above the strict row when the lifted row is exactly cardinal-aligned and 3-8 tiles away.

Why this is new:

- Attempt 226 globally moved strict tree tops up one row and made some paired trees too high.
- Attempt 249 globally moved strict tree tops up two rows and caused direct/downward target regressions.
- Attempt 229 used live blocked-row checks in `OverworldWildSpawns_TryGetHeadbuttTreeTops`, and runtime showed no change.
- This attempt only affects `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`; it does not redefine settled tree-top recognition, BFS target grids, or generic headbutt behavior.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_DIRECT_ROW_LIFT_MAX 2`.
- In the direct Mankey structural tree-top picker, test the strict row plus row lifts `0..2`.
- Before applying lifted direct rows, detect whether the tree has a clean adjacent two-tile pair on its minimum archive row.
- If that clean min-row pair exists, cap the direct row lift at `0` so those trees stay pinned to the known-safe raw row.
- Keep the existing exact-cardinal, 3-8 tile distance, and direction-rank rules.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_DIRECT_ROW_LIFT_MAX`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`

Verification:

- Checked this log first and confirmed the previous attempts changed the shared row definition or collision discriminator, not this direct-only fallback.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed before updating this entry.
- A read-only explorer agent independently recommended guarding lifted candidates by whether the tree has an adjacent pair on the minimum archive row, to avoid reintroducing the clean paired-tree too-high bug.
- Built the first version successfully as `test427.nds`, then tightened the row-lift guard before runtime handoff.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the final build.
- Built the tightened version successfully with `./docker-makerom.cmd`.
- Copied the final ROM to Delta as `test428.nds`.
- Build warnings were limited to the existing unused movement diagnostics and the existing unused battle `bsys` warning.

Runtime result:

- User reported `test428.nds` made an already-working case worse: Mankey in the image-1 scenario stopped moving.

Learning:

- The direct lifted-row fallback was not isolated enough while the shared live blocked-row lift from Attempt 229 was still active in `OverworldWildSpawns_TryGetHeadbuttTreeTops`.
- `OverworldWildSpawns_TryGetHeadbuttTreeTops` feeds settled recognition, BFS target marking, and direct target picking, so any live/collision row lift there is too broad.
- Revert the shared blocked-row lift before testing direct lifted candidates again.

### Attempt 231: Revert Shared Row Lift And Keep Direct Fallback Only

Idea:

Fix the regression from `test428.nds` by removing the broad shared row lift from `OverworldWildSpawns_TryGetHeadbuttTreeTops`. Keep `HEADBUTT_TREE_TOPS` stable for settled recognition and BFS. Then apply the two-row lifted test only inside the direct one-hop Mankey picker, guarded by archive shape: trees with a clean adjacent two-tile pair on their minimum archive row keep lift `0`; only non-clean/min-row-asymmetric entries can test `strictY - 1` or `strictY - 2`.

Why this is new:

- Attempt 229 added the shared live blocked-row lift and runtime showed no useful change.
- Attempt 230 added direct lifted rows but left the shared lift in place, which regressed the image-1 case.
- This attempt removes the shared lift entirely and limits the change to direct candidate generation.

Implementation shape:

- Remove `OW_WILD_HEADBUTT_TREE_TOP_MAX_BLOCKED_ROW_LIFT`.
- Remove the `IsMetatileBlockedAt` loop from `OverworldWildSpawns_TryGetHeadbuttTreeTops`.
- Add `OverworldWildSpawns_HeadbuttTreeHasMinRowAdjacentPair`.
- In `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`, use row lift `0` for clean min-row pairs and `0..2` only for non-clean entries.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_DIRECT_ROW_LIFT_MAX`
- `OverworldWildSpawns_HeadbuttTreeHasMinRowAdjacentPair`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`

Verification:

- Checked this log first and confirmed global/shared row lifts were already tried and harmful or ineffective.
- A read-only explorer agent separately identified the shared `TryGetHeadbuttTreeTops` lift as the part that must be removed.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed before this log update.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test429.nds`.
- Build warnings were limited to the existing unused movement diagnostics and the existing unused battle `bsys` warning.

Runtime result:

- Pending user test on `test429.nds`.

Learning:

- Pending.

### Attempt 227: Restore Archive MinY Tree-Top Logic After Too-High Row

Idea:

Undo Attempt 226. The screenshot from `test422.nds` proves moving the strict tree-top row to `minY - 1` makes invalid upper tiles count as `HEADBUTT_TREE_TOPS`. Restore the logical target row to archive `minY` and keep the rendering/visibility problem separate from movement target selection.

Why this is new:

- Attempt 226 was the current strict-resolver middle-row test and failed.
- Attempt 254 previously made raw `minY` reachable; this attempt restores that rule after proving the one-row-up correction is wrong in the current build.
- This does not change rendering, field effects, proxy objects, movement carrier timing, settled-tile latching, or `OW_WILD_TILE_HEADBUTT` behavior.

Implementation shape:

- Set `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW` to `0`.
- Set `structuralTopY = minY` in `OverworldWildSpawns_TryGetHeadbuttTreeTops`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test424.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Restored raw archive `minY` as the logical `HEADBUTT_TREE_TOPS` row after the `minY - 1` probe made invalid upper canopy tiles count as tree tops.
- The visible one-tile-low/tree-obscured Mankey symptom should be investigated via render ordering or an overlay/effect-layer visual, not by shifting the accepted target row upward.

### Attempt 228: Sparse Archive Tree-Top Row Lift

Idea:

Fix the new screenshot where Mankey lands one row too low on a tree, without repeating the rejected global `minY - 1` shift from Attempt 226. Route 29 headbutt-tree data has mixed shapes: some trees contain a clean same-row adjacent two-tile pair, while sparse entries can have a single coordinate or only non-paired coordinates. Keep clean same-row pairs at raw archive `minY`, but let sparse entries derive their logical top row as `minY - 1`.

Why this is new:

- Attempt 226 moved every strict tree-top row to `minY - 1` and made image-2-style paired trees one tile too high.
- Attempt 227 restored raw `minY` globally, which fixed the too-high paired tree case but left the sparse/edge tree in image 1 one tile too low.
- This attempt changes the current archive resolver by tree-entry shape, not by a global row offset.
- It still does not use `OW_WILD_TILE_HEADBUTT` as a target definition and does not change map-object rendering, late-draw effects, proxy objects, movement carrier timing, or settled-state storage.

Implementation shape:

- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, detect actual adjacent coordinate pairs that share the same archive Y row.
- If any same-row pair exists, keep `structuralTopY = minY`.
- If no same-row pair exists, keep the existing X fallback but use `structuralTopY = minY - 1`.
- Leave paired image-2 trees on raw `minY` so the rejected one-row-too-high behavior is not reintroduced.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test425.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User reported `test431.nds` still places Mankey two tiles too far down on the top row of Route 29 trees.

Learning:

- For same-row two-coordinate entries, `minY` is not the visual top row. It is the lower/contact row of the 2x3 footprint, so the valid Mankey top row is `minY - 2`.
- Keep the multi-row case separate, because obstructed/overlapped 2x2 trees may already expose their top row as `minY`.

### Attempt 234: Lift Single-Row Mankey Footprints

Idea:

Fix the `test431.nds` result without reverting to broad global row offsets. When a Mankey headbutt-tree footprint entry proves exactly two adjacent X columns but only one Y row, treat that row as the lower/contact row and mark the valid top row two tiles above it. When an entry has multiple Y rows, keep using `minY` as the top row so obstructed 2x2 trees do not get pushed too high.

Why this is new:

- Attempt 233 used `minY` for every 2-wide Mankey footprint entry.
- The runtime result showed same-row pair entries are exactly two tiles too low.
- This attempt changes only the single-row case inside the Mankey-only footprint helper.

Implementation shape:

- In `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`, if `maxY == minY`, set `topY = minY - OW_WILD_MANKEY_HEADBUTT_TREE_MAX_FOOTPRINT_Y_SPAN`.
- Add a guard so single-row entries too close to the top of the map are skipped instead of underflowing.
- Leave multi-row entries at `topY = minY`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`

Verification:

- Checked the attempt log before editing.

Runtime result:

- User reported `test431.nds` still places Mankey two tiles too far down on the top row of Route 29 trees.

Learning:

- For same-row two-coordinate entries, `minY` is not the visual top row. It is the lower/contact row of the 2x3 footprint, so the valid Mankey top row is `minY - 2`.
- Keep the multi-row case separate, because obstructed/overlapped 2x2 trees may already expose their top row as `minY`.

### Attempt 234: Lift Single-Row Mankey Footprints

Idea:

Fix the `test431.nds` result without reverting to broad global row offsets. When a Mankey headbutt-tree footprint entry proves exactly two adjacent X columns but only one Y row, treat that row as the lower/contact row and mark the valid top row two tiles above it. When an entry has multiple Y rows, keep using `minY` as the top row so obstructed 2x2 trees do not get pushed too high.

Why this is new:

- Attempt 233 used `minY` for every 2-wide Mankey footprint entry.
- The runtime result showed same-row pair entries are exactly two tiles too low.
- This attempt changes only the single-row case inside the Mankey-only footprint helper.

Implementation shape:

- In `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`, if `maxY == minY`, set `topY = minY - OW_WILD_MANKEY_HEADBUTT_TREE_MAX_FOOTPRINT_Y_SPAN`.
- Add a guard so single-row entries too close to the top of the map are skipped instead of underflowing.
- Leave multi-row entries at `topY = minY`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`

Verification:

- Checked the attempt log before editing.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.

Runtime result:

- Pending user test.

Learning:

- Pending.

## 2026-06-09 Follow-Up: `test432.nds`

Runtime result from `test431.nds`:

- User reported that Mankey was still two tiles too far down for same-row Route 29 headbutt-tree entries.

Adjustment:

- Single-row two-column Mankey footprint entries are now treated as lower/contact-row data and lifted by two tiles.
- Multi-row entries still use their minimum Y row as the top row to avoid reintroducing the earlier obstructed-tree one/two-tiles-too-high regressions.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test432.nds`.

Runtime result:

- Pending user test.

### Attempt 229: Live Blocked-Row Tree-Top Confirmation

Idea:

The user corrected the previous water/base-row assumption: the row under Mankey in the new screenshot is normal walking land, and Mankey is two tiles too low. Do not repeat the rejected global `minY - 2` attempt. Instead, keep the archive-derived row from Attempt 228 as the first proposal, then consult the live map: if the proposed tree-top row is still ordinary unblocked ground, lift the row upward until a blocked/canopy-like row is found, capped at two rows.

Why this is new:

- Attempt 249 set the strict row to `minY - 2` globally and later made some direct/downward targets disappear.
- Attempt 226 set the row to `minY - 1` globally and made paired trees one tile too high.
- Attempt 228 used only archive shape, which still allowed a normal walking-land row in the latest screenshot.
- This attempt makes row correction conditional on live map blocking, not on a fixed global offset or `OW_WILD_TILE_HEADBUTT`.

Implementation shape:

- Pass `FieldSystem *` into `OverworldWildSpawns_TryGetHeadbuttTreeTops`.
- After choosing the archive-derived row, test the two candidate top tiles with `IsMetatileBlockedAt`.
- If neither tile is blocked, lift the row upward, up to `OW_WILD_HEADBUTT_TREE_TOP_MAX_BLOCKED_ROW_LIFT` rows.
- Route both direct target picking and BFS target-grid marking through this field-aware resolver so they do not disagree.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_MAX_BLOCKED_ROW_LIFT`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test426.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 242: Charmander Canopy Locator Probe

Runtime prompt:

- User reported the current tree-top/canopy locator still appears wrong and asked for a direct test spawner.

Learning:

- This is a diagnostic probe, not a behavior fix.
- Do not use normal wild spawn slots, normal spawn spacing, normal spawn count, or Mankey behavior to validate the locator.
- The probe should answer one question cleanly: which tile does the current canopy locator think is the closest valid canopy tile?

Implementation shape:

- Add a separate Charmander probe object ID range.
- Every 10 player steps, scan the current map's headbutt-tree top candidates through the shared locator and pick the closest candidate tile to the player.
- Spawn a stationary Charmander on that tile as a standalone map object.
- Ignore normal spawn spacing and normal spawn count.
- Reject only a tile that already has a Charmander probe object on it, so repeated steps fill additional closest candidates instead of stacking on one tile.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_CANOPY_CHARMANDER_PROBE_OBJECT_ID_START`
- `OverworldWildSpawns_TrySpawnCanopyCharmanderProbe`
- `OverworldWildSpawns_TryPickClosestCanopyCharmanderProbeTile`

Verification:

- Pending.

Runtime result from `test443.nds`:

- User reported no Charmander spawned.
- This means either the probe object path did not run/create an object, or the canopy locator returned zero candidates.

### Attempt 260: Charmander Probe Fallback Marker

Runtime prompt:

- The first Charmander canopy probe was silent when no canopy candidate existed.

Learning:

- A silent diagnostic is not good enough here: if the locator returns zero candidates, no Charmander appears and the result is ambiguous.
- The next probe must split "object spawning works" from "canopy locator works."

Implementation shape:

- Keep the normal success path: every 10 player steps, spawn Charmander on the closest candidate from `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`.
- If that locator returns no tile, spawn Charmander on a nearby normal land tile as a fallback marker.
- Continue to reject only tiles that already contain a Charmander probe, so repeated markers do not stack.
- If fallback Charmander appears, the locator is empty/broken. If no Charmander appears even with fallback, the probe tick/object creation path is broken.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TrySpawnCanopyCharmanderProbe`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test444.nds`.

### Attempt 261: Default Non-Phantom Reveal Guard

Runtime prompt:

- User reported the Charmander canopy probe can turn invisible.
- User clarified `BIT_VANISH` should not be something normal spawned Pokemon inherit or touch by default.
- `BIT_VANISH` should remain opt-in for phantom stalk movement only.

Learning:

- Previous phantom attempts showed repeated real-object `BIT_VANISH` toggling is fragile and should not leak into normal spawn behavior.
- The current phantom stalker implementation is the special case that intentionally uses vanish/flicker helper objects.
- Canopy hopper, Mankey, and diagnostic probe objects should be treated as normal visible map objects unless they are being deleted/despawned.

Implementation shape:

- Make `OverworldWildSpawns_CreateObject` clear `BIT_VANISH` immediately after any spawner-created object is allocated.
- Add a reusable non-phantom reveal guard that clears `BIT_VANISH` on all active normal spawn slots unless their resolved behavior profile is `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.
- Also clear `BIT_VANISH` on standalone Charmander canopy probe objects, since those are not tracked in normal spawn slots.
- Run the guard from the player-step path and the frame-movement task so stale vanish bits get corrected after both step-driven and frame-driven updates.
- Do not clear vanish on phantom flicker helper objects or active phantom stalk slots.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_CreateObject`
- `OverworldWildSpawns_RevealNonPhantomObjects`
- `OverworldWildSpawns_SpawnSlotAllowsVanish`

Verification:

- First build failed because `LocalMapObject` uses `flags & MAPOBJECTFLAG_ACTIVE`, not an `active` field; corrected the probe-object scan.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before rebuild.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test445.nds`.

Runtime result from `test445.nds`:

- User reported Charmander is still invisible.

Learning:

- Clearing `BIT_VANISH` after creation is not enough for the Charmander probe.
- The special standalone Charmander probe object path itself is suspect.
- Do not keep the separate probe object ID/state lifecycle for this locator test.

### Attempt 262: Charmander Probe Uses Normal Spawn Slot From Birth

Runtime prompt:

- User clarified the correct fix is to never put Charmander into the problematic hidden/probe state in the first place.

Learning:

- The Charmander locator probe should not be a separate object category with custom probe IDs.
- A visual test Pokemon should use the same normal spawn slot/object lifecycle as every other visible overworld Pokemon.

Implementation shape:

- Remove the custom `OW_WILD_CANOPY_CHARMANDER_PROBE_OBJECT_ID_START` probe ID range.
- Remove standalone probe-object ID allocation/scanning.
- Spawn Charmander into a normal `OverworldWildSpawnState` slot and assign `OW_WILD_OBJECT_ID_START + slot` immediately.
- Track existing test Charmander through normal active spawn slots instead of a custom object ID range.
- Keep the object stationary for the locator test by giving it zero object range and long movement/spot cooldowns.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TrySpawnCanopyCharmanderProbe`
- `OverworldWildSpawns_IsCanopyCharmanderProbeAt`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test446.nds`.

### Attempt 259: Boundary-Derived Headbutt Tree-Top Locator

Runtime result from `test441.nds`:

- User reported the paired archive-derived locator still did not help.
- User also reported the game became a bit laggy, likely because generated candidate sets were still too broad/expensive.

Learning:

- The previous archive min/max attempts still tried to infer tree-top positions from sparse archive geometry.
- The user proposed a better model: start from actual `OW_WILD_TILE_HEADBUTT` behavior tiles, then inspect immediately adjacent non-headbutt boundary tiles.
- This avoids broad vertical stacks and avoids treating archive coordinate rows as canonical tree footprints.
- Side boundaries are ambiguous, but the ambiguity can be represented as three local candidate scenarios: top, mid-body, or base.

Implementation shape:

- Keep `OverworldWildHeadbuttTreeTops` as concrete `(topLeftX, topY)` candidates.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`, inspect each archived coordinate only if the live map behavior at that coordinate is `OW_WILD_TILE_HEADBUTT`.
- For a non-headbutt tile below a headbutt tile, add top candidates three tiles above that boundary.
- For a non-headbutt tile above a headbutt tile, add top candidates one tile below that boundary.
- For a non-headbutt tile to the left/right of a headbutt tile, add the three possible side scenarios:
  - side tile is canopy
  - side tile is mid-body
  - side tile is base
- Validate each candidate through `OverworldWildSpawns_IsHeadbuttTreeTopSurface` before storing it.
- Remove the dead vertical-stack macro from the previous locator.
- Keep the 3-8 tile movement rule unchanged and do not reintroduce a two-tile Mankey hop exception.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`
- `OverworldWildSpawns_AddHeadbuttTreeTopCandidateFromHeadbuttTile`
- `OverworldWildSpawns_AddHeadbuttTreeTopColumnCandidatesFromHeadbuttTile`
- `OverworldWildSpawns_IsNonHeadbuttBoundaryTile`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test442.nds`.

### Attempt 242: Pair Tree-Top Candidates And Derive Top Row From Archive Bottom

Runtime result from `test440.nds`:

- User reported the locator was still miscalculating and Mankey was still stopping at bad positions.

Learning:

- Attempt 241 still used `OverworldWildHeadbuttTreeTops` as independent X and Y lists, so every stored left edge could be combined with every generated row.
- Route 29 `treecoords` are sparse headbutt/contact anchor tiles, not a canonical 2x3 footprint.
- For a 2-wide, 3-high logical tree, the safest derived top row from a sparse archive entry is `maxArchiveY - 2`.
  - Same-row entries lift by two tiles.
  - Two-row entries lift by one tile.
  - Three-row entries keep their top row.
- A Mankey hop should not permanently enter settled tree-top state just because the chosen target was labeled as a tree top before movement; the final tile must validate too.

Implementation shape:

- Change `OverworldWildHeadbuttTreeTops` to store concrete `(topLeftX, topY)` candidates instead of separate left and row lists.
- Validate each concrete candidate with `OverworldWildSpawns_IsHeadbuttTreeTopSurface` before storing it.
- Change `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations` to receive `FieldSystem *` and derive `topRow` as `maxY - OW_WILD_HEADBUTT_TREE_TOP_LOCATION_MAX_FOOTPRINT_Y_SPAN`.
- Update the public predicate, direct target picker, and path-grid marker to iterate concrete candidates only.
- Revalidate the final tile in `OverworldWildSpawns_FinishPendingCanopyHop` before setting `sOverworldWildMankeyTreeTopSettled`.
- Keep the 3-8 tile movement rule unchanged and do not reintroduce a two-tile Mankey hop exception.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildHeadbuttTreeTops`
- `OverworldWildSpawns_AddHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`
- `OverworldWildSpawns_FinishPendingCanopyHop`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test441.nds`.

Runtime result:

- Pending.

### Attempt 237: Revert Two-Tile Mankey Canopy-Hop Relaxation

Runtime clarification:

- User clarified there was no bug in the reported case: it was a two-tile hop, and Mankey should not be expected to make a two-tile canopy hop.

Learning:

- Attempts 235 and 236 were based on a bad premise: treating the two-tile-down case as a valid Mankey tree-top hop.
- The intended canopy-hopper rule remains 3-8 tiles. A two-tile target should be ignored or reached through another valid hop/path, not by adding a special two-tile final landing exception.

Implementation shape:

- Remove the Mankey-specific two-tile final tree-top exception.
- Restore direct Mankey tree-top candidate selection to the normal `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES` minimum.
- Restore Mankey tree-top path search to 3-8 tile hops only.
- Restore canopy-hop staging, prepared long-jump timing, and execution to reject distances below the normal long-jump minimum.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test436.nds`.

### Attempt 238: Generic Headbutt Tree-Top Location Filter

Idea:

Make the settled headbutt tree-top location resolver reusable for future behavior profiles instead of keeping it named as Mankey-specific logic.

Why this is new:

- Earlier Mankey tree-top attempts focused on correcting the tile semantics and rendering. This pass does not change those semantics.
- The current goal is an internal API cleanup: future behaviors should be able to ask for valid headbutt tree-top locations without depending on Mankey names.

Implementation shape:

- Rename the footprint resolver to `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`.
- Rename the field/tile predicate to `OverworldWildSpawns_IsHeadbuttTreeTopLocation`.
- Rename the footprint-span constants from Mankey-specific names to `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_*`.
- Keep `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` as a thin wrapper for existing Mankey-specific call sites.
- Remove the older unused `OverworldWildSpawns_TryGetHeadbuttTreeTops` helper so there is one canonical generic tree-top location filter.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`
- `OverworldWildSpawns_IsHeadbuttTreeTopLocation`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_FOOTPRINT_HEIGHT_TILES`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_MAX_FOOTPRINT_Y_SPAN`

Verification:

- Pending.

Learning:

- Pending.

### Attempt 197: Route 29 Top-Cap Coordinate Probe

Idea:

Keep the same stationary Mankey occupancy probe and normal render path from Attempt 196, but retarget the forced coordinate from `594,388` to `594,387`. This tests the visually higher top-cap row above the Route 29 headbutt anchors `(594,389)` / `(595,389)`.

Why this is new:

- Attempt 194 used the actual headbutt behavior tile `594,389`.
- Attempt 195/196 used `594,388`, which the user confirmed is the wrong visual tile class.
- This attempt changes only the forced coordinate to the likely top-cap row while keeping movement disabled and keeping the follower render bundle removed.

Implementation shape:

- Set `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y` to `387`.
- Keep `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X` at `594`.
- Keep the forced spawn idle/no-alert/no-attentive.
- Keep `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams` on the normal path, only clearing `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y`
- `OverworldWildSpawns_TryPickRoute29CanopyTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test364.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.

Runtime result:

- User reported this partially fixed the placement, but Mankey can still appear at the base/lower edge of the tree when that tile is closest to the walkable area.

Learning:

- `594,387` is closer to the desired canopy-top class than `594,388`, but it still reads as the walkable-adjacent lower canopy/base row.
- Do not treat the closest canopy tile above walkable ground as the desired tree-top perch. For this visual behavior, the target needs to be further inside/up on the canopy, not merely adjacent to the ground edge.

### Attempt 198: Route 29 Upper Top-Cap Coordinate Probe

Idea:

Keep the stationary Mankey occupancy probe and normal render path, but move one more tile upward from `594,387` to `594,386`. This tests whether the desired red-box tree-top tiles are the upper canopy cap rather than the walkable-adjacent lower edge.

Why this is new:

- Attempt 195/196 tested `594,388`, which was clearly too low/side-like.
- Attempt 197 tested `594,387`, which improved placement but still hit the lower base/edge row.
- This attempt changes only the forced coordinate to the next upper row while movement remains disabled and no follower render flags are reintroduced.

Implementation shape:

- Set `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y` to `386`.
- Keep `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X` at `594`.
- Keep the forced spawn idle/no-alert/no-attentive.
- Keep `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams` on the normal path, only clearing `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y`
- `OverworldWildSpawns_TryPickRoute29CanopyTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test365.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.

Runtime result:

- User reported this still did not place Mankey on the intended headbutt tree top.

Learning:

- Hardcoded Route 29 visual-coordinate guessing is not the right abstraction for this test.
- A future attempt should keep the logical object on a real headbutt-tree anchor from `ARC_HEADBUTT_TREES` and only adjust render placement, rather than pretending a nearby top-cap/base tile is the spawn tile.

### Attempt 199: Actual Headbutt Anchor With Render-Only Tree-Top Offset

Idea:

Stop relying on guessed Route 29 top/base coordinates. Pick a real headbutt tree tile directly from `ARC_HEADBUTT_TREES`, keep Mankey's logical object coordinates on that real tree anchor, and render it three tiles north through `posVec[2]` so it appears on top of the tree.

Why this is new:

- Attempts 194-198 moved the logical spawn coordinate between hardcoded Route 29 tiles.
- This attempt removes the hardcoded `594,386` style target and uses the actual headbutt-tree archive as the source of truth.
- It does not use the normal headbutt landing/perch spawner and does not call follower render flags.
- It keeps logical X/Y and render X/Z separate: collisions/state remain on the headbutt tree tile, while only the displayed Z position is offset upward.

Implementation shape:

- Replace the forced canopy-top coordinate constants with `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_RENDER_Y_OFFSET_TILES`.
- Add `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`, which iterates current-map headbutt tree archive entries, validates `OW_WILD_TILE_HEADBUTT`, and chooses a nearby actual tree anchor.
- Add `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual`, which keeps logical X/Y on the tree anchor, shifts `posVec[2]` by the visual offset, and clears `BIT_VANISH`.
- Refresh that visual every movement-frame tick for the forced stationary Mankey test so map-object updates cannot revert it after spawn.
- Replace stale active-spawn checks against hardcoded X/Y with "Mankey is on a current-map headbutt-tree tile."

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_RENDER_Y_OFFSET_TILES`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`
- `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual`
- `OverworldWildSpawns_IsObjectOnHeadbuttTree`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test366.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus old diagnostic globals.

Runtime result:

- User reported Mankey appeared to blink around.

Learning:

- Do not offset the rendered graphic separately from the actual headbutt-tree tile for this test.
- Do not retry render-only `posVec[2]` relocation or frame-refresh visual correction here; the user wants the actual object tile and displayed tile to be the same headbutt-tree tile.

### Attempt 200: Exact Headbutt Tile Occupancy, No Graphic Offset

Idea:

Keep the one useful part from Attempt 199: the forced test picks an actual current-map headbutt-tree tile from `ARC_HEADBUTT_TREES`. Remove the bad part: no render-only offset, no visual relocation, no frame refresh. The object's logical tile and displayed tile should both be exactly the chosen headbutt tree tile.

Why this is new:

- Attempts 194-198 moved hardcoded logical coordinates.
- Attempt 199 used the right source of truth for the logical tile, but added a render offset that made Mankey appear to blink around.
- This attempt keeps the archive-backed headbutt-tree spawn tile and explicitly synchronizes the object's X/Y and `posVec` back to that exact same tile.

Implementation shape:

- Remove the stale headbutt-tree top offset constant.
- Keep `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition` as the forced picker.
- Change `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual` to call `OverworldWildSpawns_SetObjectTile(object, position.startX, position.startY)` and clear `BIT_VANISH`.
- Do not adjust `posVec[2]` away from the actual tree tile.
- Do not refresh or move the graphic in the frame task.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test367.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus old diagnostic globals.

Runtime result:

- User reported no Pokemon spawned.

Learning:

- Exact-tile display is still the right visual direction, but the forced test cannot allow normal candidate filters or stale invisible slots to block the spawn entirely.
- A future attempt must guarantee that the forced test returns an archive coordinate whenever the map has headbutt-tree data, and must not rely on the normal headbutt encounter roll to produce the visible test Pokemon.

### Attempt 201: Guaranteed Forced Headbutt Mankey Spawn

Idea:

Fix the forced spawn path itself. Keep Mankey's logical/display tile exactly on the selected headbutt archive coordinate, but stop the forced test from failing because of normal spawner filters, invisible stale slots, or headbutt encounter-roll failures.

Why this is new:

- Attempt 200 used exact tile placement, but still allowed the forced picker to reject all candidates based on distance, nearby active spawns, and metatile behavior validation.
- Previous attempts still depended on the normal headbutt encounter roll before forcing the species to Mankey.
- This attempt makes the forced test deterministic: if the map has headbutt-tree archive entries, choose one, create Mankey, and clear stale invisible blockers.

Implementation shape:

- Remove distance, nearby-active-spawn, and metatile-behavior rejection from `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`.
- Keep scoring by distance so it prefers a nearby tree, but always accepts archive coordinates.
- Make invisible stale Mankey objects not count as an active forced test spawn, and clear them during forced-test refill preparation.
- Let forced-test refill cleanup run in any map context instead of only `MAP_R29`.
- In `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_OCCUPANCY_TEST`, create a fixed level 5 Mankey for headbutt terrain instead of requiring `OverworldWildSpawns_TryRollHeadbuttEncounter` to succeed.
- Keep `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual` exact: `OverworldWildSpawns_SetObjectTile(object, position.startX, position.startY)` and clear `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`
- `OverworldWildSpawns_HasActiveForcedCanopyHopperTestSpawn`
- `OverworldWildSpawns_PrepareForcedCanopyHopperTestRefill`
- `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_TEST_LEVEL`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test368.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus old diagnostic globals.

Runtime result:

- User rejected the interpretation: spawning on the headbutt/tree footprint contradicts the requested behavior.

Learning:

- The archive headbutt tile and the tree's own 2x2 footprint tiles are not valid Mankey spawn tiles for this test.
- The requested spawn tile is above that footprint, not on/inside it.
- Do not retry "spawn on archive tile" or "spawn on tree footprint" for this test.

### Attempt 202: Spawn On Row Above Headbutt Tree Footprint

Idea:

Treat each headbutt archive coordinate as part of the tree's 2x2 footprint, then spawn Mankey on the row immediately above that footprint. For the Route 29-style bottom-row headbutt coordinates, that means `spawnY = treeY - 2`; none of the tree footprint tiles themselves are valid.

Why this is new:

- Attempts 199-201 placed Mankey on the archive/headbutt coordinate or moved the rendered graphic from there.
- User clarified that the valid spawn tile is above the tree footprint, not any of the tree's four footprint tiles.
- This attempt changes the actual spawn tile before object creation; no render offset is involved.

Implementation shape:

- Add `OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES 2`.
- In `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`, compute `spawnX = treeX` and `spawnY = treeY - OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES`.
- Score candidates by distance to `spawnX/spawnY`.
- Set `position.startX/startY` and `position.headbuttPerchX/Y` to `spawnX/spawnY`.
- Keep `OverworldWildSpawns_ApplyHeadbuttTreeTopOccupancyVisual` exact: it sets the object tile to the chosen spawn tile and clears `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test369.nds` into the Delta ROM folder.
- Overlay compiled with the expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- User reported Mankey spawned one tile too high, then disappeared quickly.

Learning:

- This explicitly rejects the bad "tree footprint as spawn surface" model. The only valid test row is above the footprint.
- `spawnY = treeY - 2` overshoots by one tile for the current headbutt archive coordinate interpretation.
- Do not remove global distance despawn to solve this specific test; the user explicitly rejected that broad workaround.

### Attempt 203: Lower Tree-Top Test Tile And Preserve Forced Idle Visibility

Idea:

Move the forced Mankey test spawn one tile lower than Attempt 202 and keep it as an actual idle object. If the object temporarily has `BIT_VANISH`, reveal it instead of treating that as proof that the forced spawn is gone and deleting/refilling it.

Why this is new:

- Attempt 202 used `treeY - 2`, which user testing showed was one tile too high.
- Earlier attempts that moved graphics or used footprint tiles are still rejected.
- This attempt does not remove or bypass the normal distance despawn path.

Implementation shape:

- Replace `OW_WILD_SPAWNER_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES 2` with `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_ROW_OFFSET_TILES 1`.
- In `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`, compute `spawnY = treeY - 1`.
- For the forced occupancy test only, stop treating `BIT_VANISH` on the active forced Mankey as a stale/deleted spawn during forced-refill checks; clear the bit and keep the object.
- Leave `OverworldWildSpawns_DespawnFarMons` unchanged.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_HEADBUTT_TREE_TOP_ROW_OFFSET_TILES`
- `OverworldWildSpawns_HasActiveForcedCanopyHopperTestSpawn`
- `OverworldWildSpawns_PrepareForcedCanopyHopperTestRefill`
- `OverworldWildSpawns_TryPickHeadbuttTreeTopOccupancyTestSpawnPosition`

Verification:

- `git diff --check` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test370.nds` into the Delta ROM folder.
- Overlay compiled with expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- Pending user test.
*** End of File

Learning:

- Pending.
Learning:

- Pending.


Learning:

- Pending.

### Attempt 236: Mankey Tree-Top Effect-Layer Bubble Probe

Idea:

Now that Mankey reaches the intended tree-top tiles, revisit the sprite layering issue where the Pokemon remains behind the tree canopy. Do not repeat object-height, follower flags, object priority bits, draw mode, stock draw-callback swaps, loaded cell priority, live sprite depth, or map-object proxy attempts. Instead, test a different render family: the follower/emote bubble effect layer. If a bubble attached to a tree-top Mankey draws above the canopy, then a future custom effect-layer visual for Mankey is a better path than continuing to mutate map-object rendering.

Why this is new:

- Attempts 223-228 exhausted normal map-object render levers and proxy objects.
- Attempt 229 added BG layer cycling, but it was only a diagnostic and can confuse visual testing now.
- This attempt uses the existing follower/emote bubble effect path (`ov01_02203A48`) from the spawned Mankey's tree-top anchor, which is a separate layer family from map-object sprites.

Implementation shape:

- Disable the old Mankey tree-top BG layer cycling by adding `OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED 0`; the restore function still keeps all layers enabled.
- Add `OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_FRAMES`.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe`, which periodically calls `OverworldWildSpawns_ShowBubble` with an exclamation bubble while an active Mankey is on a `HEADBUTT_TREE_TOPS` tile.
- Run the bubble probe from the frame movement task so it continues while the player stands still.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_LAYER_PROBE_ENABLED`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_BUBBLE_PROBE_ID`
- `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe`
- `OverworldWildSpawns_ShowBubble`
- `ov01_02203A48`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test394.nds`.
- User confirmed the exclamation bubble is visible above the canopy while the real Mankey remains hidden behind the tree.
- The later follower-sprite proxy probe was also confirmed to remain behind the canopy.

Learning:

- The follower/emote bubble path (`ov01_02203A48`) is a proven above-canopy render family.
- The normal map-object family is still behind the canopy, including a separate following-sprite proxy object.
- Stop pursuing map-object render/proxy fixes for this tree-top layer issue; the next useful path is an overlay/effect-layer visual probe or clone.

### Attempt 237: Cache Mankey Tree-Top Archive Predicate

Idea:

The user reported Mankey has been incredibly laggy for several builds. Do not repeat Attempt 222's failed-path backoff, which only throttled no-path searches and removed archive checks from the BFS inner loop. The remaining repeated hotspot is the tree-top predicate itself: the Mankey chill branch, tree-top render update, and Attempt 236 bubble probe all ask whether the current Mankey tile is a `HEADBUTT_TREE_TOPS` tile. That predicate reloads/scans headbutt-tree archive data. Cache the result per slot/map/tile so the archive-backed predicate is only recomputed when that Mankey changes tile, map, or slot lifecycle.

Why this is new:

- Attempt 222 optimized failed path searches and target-grid lookup, but it did not cache the "am I currently on a tree-top tile" predicate.
- Attempt 236 added a per-frame bubble probe that also used that predicate, making the old repeated-check cost more visible.
- This does not change Mankey's path selection, target definition, hop timing, render flags, or layer behavior.

Implementation shape:

- Add per-slot static cache state for Mankey tree-top checks:
  - cached map id
  - cached x/y tile
  - cached boolean result
- Add `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached`.
- Route the runtime Mankey tree-top checks through the cached wrapper.
- Clear the cache on slot clear and spawn setup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildMankeyTreeTopCacheValid`
- `sOverworldWildMankeyTreeTopCacheResult`
- `sOverworldWildMankeyTreeTopCacheX`
- `sOverworldWildMankeyTreeTopCacheY`
- `sOverworldWildMankeyTreeTopCacheMapId`
- `OverworldWildSpawns_ClearMankeyTreeTopCache`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test395.nds`.
- User reported the exclamation bubble loop starts way before Mankey is actually on a tree.

Learning:

- Caching may still help performance, but the bubble probe was using the broad coordinate predicate as "perched" state.
- A coordinate matching `HEADBUTT_TREE_TOPS` is not enough to decide the layer probe should run; it needs a real completed final tree-hop/perched state.

### Attempt 238: Gate Mankey Bubble Probe On Final Tree-Top Landing

Idea:

Fix the premature exclamation bubble loop from `test395.nds`. Do not remove the layer probe or repeat object priority/render attempts. The problem is that the bubble probe uses the coordinate predicate directly, so any false-positive or pre-landing `HEADBUTT_TREE_TOPS` coordinate can start the bubble loop. Track whether the currently staged Mankey hop is expected to land on an actual final tree-top target, then only allow the bubble probe after that final hop has completed.

Why this is new:

- Attempt 236 added the bubble probe but keyed it directly off the tree-top coordinate predicate.
- Attempt 237 cached that predicate for performance but did not distinguish final tree-top landing from pre-tree/intermediate states.
- This attempt adds an explicit final-landing/perched gate for the bubble probe without changing the target definition, hop pathing, or render layer experiment.

Implementation shape:

- Add per-slot static flags:
  - `sOverworldWildMankeyTreeTopLandingExpected`
  - `sOverworldWildMankeyTreeTopSettled`
- Extend `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` to report whether its returned target is a final tree-top target or an intermediate path step.
- When Mankey stages a canopy hop, arm `sOverworldWildMankeyTreeTopLandingExpected` only for final tree-top targets.
- When the pending canopy hop finishes, set `sOverworldWildMankeyTreeTopSettled` only if that final target was expected.
- Make `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe` require `sOverworldWildMankeyTreeTopSettled`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildMankeyTreeTopLandingExpected`
- `sOverworldWildMankeyTreeTopSettled`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_FinishPendingCanopyHop`
- `OverworldWildSpawns_UpdateMankeyTreeTopBubbleProbe`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test396.nds`.
- Pending user runtime test.

Learning:

- Pending. Test specifically whether the exclamation loop no longer starts before Mankey reaches the tree and whether it still appears after final tree-top landing.

### Attempt 239: Align Mankey Tree-Top Settled Rows With Target Rows

Idea:

The user reported a Mankey behind the canopy that keeps moving back and forth even though it is on a visible tree-top tile. This is not the same as the premature bubble loop from Attempt 238. The target picker already allows both structural top rows and exposed top rows by calling `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., TRUE, ...)`, but the settled predicate still calls the same helper with `FALSE`. That means Mankey can legitimately target and land on an exposed tree-top row, then fail the idle settled check and immediately try to move again.

Why this is new:

- Attempt 235 defined the dedicated `HEADBUTT_TREE_TOPS` target set.
- Attempt 238 added a final-landing gate for the bubble probe but did not change which rows count as settled.
- No prior attempt aligned the settled predicate's row definition with the target picker's row definition.

Implementation shape:

- Change `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` to call `OverworldWildSpawns_TryGetHeadbuttTreeTops` with `includeExposedRows = TRUE`.
- This makes idle/perched detection match the Mankey target selection row set.
- The bubble probe remains guarded by `sOverworldWildMankeyTreeTopSettled`, so broad coordinate matches alone should still not restart the premature bubble loop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test397.nds`.
- Pending user runtime test.

Learning:

- Pending. Test specifically whether Mankey now stops moving once it reaches the visible/exposed tree-top tile shown in the screenshot.

### Attempt 240: Strict Top-Row Mankey Target Set With Broad X Candidates

Idea:

The user reported that Mankey is still not getting to a tree-top tile on `test397.nds`. Do not repeat the rejected `OW_WILD_TILE_HEADBUTT` shortcut from Attempt 234. Do not simply repeat Attempt 230 either: Attempt 230 used the strict 2x6 structural top row but still used a narrow primary X footprint. Attempt 235 fixed the X ambiguity by deriving possible 2-tile top-left candidates from every archive coord, but it also kept the exposed/archive `minY` row as an active target. This attempt keeps Attempt 235's broader X candidates while removing the exposed row from active Mankey top targeting and settling.

Why this is new:

- Attempt 230 targeted only the structural row, but did not have the later broad `coordX` / `coordX - 1` top-left candidate set.
- Attempt 235 introduced broad X candidates, but still allowed the extra exposed/archive row.
- Attempt 239 aligned settling with the broad target set, but that can still let tree-body/exposed rows count as good enough.
- This attempt defines active `HEADBUTT_TREE_TOPS` as the strict structural top row of the 2x6 tree footprint, with the broad X ambiguity retained.

Implementation shape:

- Keep `OverworldWildSpawns_TryGetHeadbuttTreeTops` and its broad top-left candidate generation.
- Change all active Mankey uses of that helper to pass `includeExposedRows = FALSE`:
  - current-tile settled predicate
  - direct top target picker
  - BFS target grid marker
- Leave `OW_WILD_TILE_HEADBUTT` unused for this targeting path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test398.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported that Mankey did not move on `test398.nds`.
- The screenshot showed an exclamation bubble over a Mankey on/near the path, which suggests the strict-row predicate can still falsely classify ground/path tiles as already valid tree-top tiles.
- The remaining suspect is the broad X candidate set from Attempt 235: treating every archive coord as both possible left and right side can make one tree entry cover too many neighboring X tiles.

### Attempt 241: Pair-Derived Mankey Tree-Top X Footprints

Idea:

Fix the `test398.nds` no-movement regression without using the rejected `OW_WILD_TILE_HEADBUTT` shortcut. Attempt 240 made the row strict, but the screenshot still showed a bubble on a non-tree-top Mankey, so the X footprint is likely too broad. Replace the broad "every coordX and coordX - 1" candidate set with pair-derived 2-wide footprints: if a headbutt tree archive entry contains adjacent X columns, use that adjacent pair as the tree's left edge. Only fall back to `minX` and `minX - 1` when the archive entry has no adjacent X pair.

Why this is new:

- Attempt 230 used only `minX`, which was too narrow for some trees.
- Attempt 235 added every `coordX` and `coordX - 1`, which can over-expand a tree into nearby path/ground tiles.
- Attempt 240 kept that broad X set while making rows strict, which produced no movement because Mankey could already be falsely considered settled.
- This attempt uses archive geometry to find actual 2-wide X pairs instead of either one narrow edge or every possible edge.

Implementation shape:

- Keep the dedicated `HEADBUTT_TREE_TOPS` system and strict top-row targeting from Attempt 240.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, collect distinct X columns from the tree entry.
- Add top-left candidates only from adjacent X pairs when present.
- Use `minX` and `minX - 1` only as a sparse-entry fallback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test399.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported that the highlighted visible canopy-top row is not treated as tree-top on `test399.nds`.
- Pair-derived X footprints appear to have fixed one axis of the false-positive problem, but the strict structural Y row is too narrow for the visible top-cap tiles.
- The next attempt should keep pair-derived X but re-enable exposed rows; this is not the same as Attempt 235/239 because those still used broad X candidates.

### Attempt 242: Exposed Mankey Tree-Top Rows With Pair-Derived X

Idea:

The user reported that the highlighted visible canopy-top row is not treated as a tree-top tile on `test399.nds`. Do not go back to the rejected `OW_WILD_TILE_HEADBUTT` path. Also do not repeat Attempt 235/239 exactly: those included exposed rows but used the over-broad "every coordX and coordX - 1" X set. Keep Attempt 241's safer pair-derived X footprint, then re-enable exposed rows for current-tile settling, direct target picking, and BFS target marking.

Why this is new:

- Attempt 235 used exposed rows with broad X candidates and could over-expand into nearby non-tree tiles.
- Attempt 239 aligned settling with the broad exposed target set and still inherited that X problem.
- Attempt 241 narrowed X footprints but kept rows strict, causing visible top-cap rows to be missed.
- This attempt combines exposed visible rows with narrowed pair-derived X footprints.

Implementation shape:

- Leave `OverworldWildSpawns_TryGetHeadbuttTreeTops` pair-derived X logic intact.
- Change the active Mankey tree-top calls back to `includeExposedRows = TRUE`:
  - current-tile settled predicate
  - direct top target picker
  - BFS target grid marker
- Continue leaving `OW_WILD_TILE_HEADBUTT` unused for this targeting path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test400.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported that Mankey still does not jump three tiles down to the visible tree-top tile on `test400.nds`.
- Re-enabling only the exposed endpoint row was still too narrow.
- The resolver only stored two Y rows, so it could miss visible canopy rows between the structural top row and archive exposed row.

### Attempt 243: Full Mankey Tree-Top Vertical Band

Idea:

Fix the repeated failure where Mankey will not jump three tiles down to a visible tree-top tile. Do not use `OW_WILD_TILE_HEADBUTT`, and do not return to the broad-X false positive from Attempt 235. Keep the pair-derived X footprint from Attempt 241, but stop representing the tree top as only one or two Y rows. Treat every row from the structural 2x6 top through the archive exposed row as part of `HEADBUTT_TREE_TOPS`.

Why this is new:

- Attempt 242 re-enabled the exposed endpoint row, but the highlighted visible tree-top tile can still sit between the structural row and that endpoint.
- Previous attempts kept `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS` at `2`, so the resolver could not represent a vertical band.
- This attempt keeps the narrowed X footprint and expands only the Y representation.

Implementation shape:

- Change `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS` from `2` to `OW_WILD_HEADBUTT_TREE_HEIGHT_TILES`.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, when exposed rows are requested, add every row from `structuralTopY + 1` through `minY`, capped by the tree height.
- Keep current-tile settling, direct target picking, and BFS target marking on the same shared `HEADBUTT_TREE_TOPS` result.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test401.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported this is still not fixed on `test401.nds`; Mankey still does not jump three tiles down to a tree-top tile.
- Broadening the shared vertical row band is not enough by itself.
- The failure now points at direct target selection or post-landing settled handling rather than only target-row membership.

### Attempt 244: Direct Cardinal Mankey Tree-Band Target

Idea:

Stop relying only on enumerated tree-top tiles to eventually include the visible target. Add a direct, explicit cardinal resolver for the user's repeated case: if a Mankey has a tile 3-8 tiles straight up/down/left/right that falls inside any archive-derived headbutt-tree top band, pick that tile as the final tree target. Keep this separate from `OW_WILD_TILE_HEADBUTT`; it still uses dedicated headbutt-tree archive geometry. Also make final tree-top landing state authoritative so a target chosen by this direct resolver does not immediately get rejected by the stricter current-tile predicate after landing.

Why this is new:

- Attempts 240-243 changed which rows/Xs counted in the shared `HEADBUTT_TREE_TOPS` set.
- No previous attempt added a direct cardinal scan from the current Mankey tile to a broad archive-derived tree-top band.
- No previous attempt made `sOverworldWildMankeyTreeTopSettled` authoritative for the idle/stop path.

Implementation shape:

- Add `OverworldWildSpawns_IsMankeyBroadHeadbuttTreeTopBandCandidate`.
- Add `OverworldWildSpawns_TryUseDirectMankeyHeadbuttTreeTopBandCandidate`, scanning distances `3..8` in each cardinal direction.
- Run the direct resolver before the older precise target enumerator in `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`.
- In the Mankey chill branch, if `sOverworldWildMankeyTreeTopSettled[slot]` is already set, idle immediately instead of requiring the current tile to pass the stricter predicate again.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsMankeyBroadHeadbuttTreeTopBandCandidate`
- `OverworldWildSpawns_TryUseDirectMankeyHeadbuttTreeTopBandCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `sOverworldWildMankeyTreeTopSettled`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test402.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported this still does not work on `test402.nds`: Mankey can clearly jump three tiles right to a tree-top tile but stands still.
- The direct cardinal target may still be skipped because Mankey can be classified as already settled/on a tree-top before target selection runs.
- Attempt 244's coordinate-less authoritative settled flag is unsafe because it can idle a slot without proving the current tile is the completed landing tile.

### Attempt 245: Coordinate-Latched Mankey Tree-Top Settlement

Idea:

Fix the `test402.nds` stand-still case without returning to `OW_WILD_TILE_HEADBUTT` and without broadening the target detector again. Stop treating the current tile detector as a reason for Mankey to idle. Mankey should only stop in its chill state after it has completed a canopy tree-top hop, and only while it remains on the exact tile where that hop landed.

Why this is new:

- Attempt 244 made `sOverworldWildMankeyTreeTopSettled[slot]` authoritative, but it was coordinate-less and could freeze any later tile for that slot.
- Attempts 240-243 changed the shared tree-top geometry; this attempt changes the movement state gate instead.
- This does not use `OW_WILD_TILE_HEADBUTT` and does not add another broader tree-top row/footprint heuristic.

Implementation shape:

- Add `sOverworldWildMankeyTreeTopSettledX/Y` alongside `sOverworldWildMankeyTreeTopSettled`.
- When `OverworldWildSpawns_FinishPendingCanopyHop` completes an expected Mankey tree-top landing, store the exact current tile as the settled tile.
- In `OverworldWildSpawns_TryStartHeadbuttTreeHop`, clear stale settled state if the object is no longer on that stored tile.
- Remove the Mankey chill-state early return that idled solely because `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTileCached` returned true.
- Clear stale landing-expected state in `OverworldWildSpawns_ClearCanopyHopTarget`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildMankeyTreeTopSettledX`
- `sOverworldWildMankeyTreeTopSettledY`
- `OverworldWildSpawns_ClearCanopyHopTarget`
- `OverworldWildSpawns_FinishPendingCanopyHop`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test403.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported Mankey still misses the mark on `test403.nds`: it moves, but lands beside/near the tree rather than on the intended tree-top tile.
- Coordinate-latched settling fixed the likely idle/stale-state issue, but did not fix final target choice.
- The broad fallback band is now suspect because it accepts rows through `minY` and can choose side/body tiles when they are closer than the strict visual top row.

### Attempt 246: Prioritize Strict Structural Mankey Tree Tops

Idea:

Fix the `test403.nds` "missing the mark" result by making direct Mankey tree-top selection prefer the strict structural top row first. Keep the broad row band only as a fallback. This uses `topY = maxY - (OW_WILD_HEADBUTT_TREE_HEIGHT_TILES - 1)` with pair-derived 2-wide X footprints, matching the 2-wide/6-high headbutt-tree model, while preserving the previous fallback for awkward sparse archive entries.

Why this is new:

- Attempts 240-241 tried strict structural rows while Mankey could still stop early from current-tile misclassification.
- Attempt 245 removed the current-tile early stop and coordinate-latched true completed landings.
- Attempt 244's broad direct band moved/selected targets but can land on side/body tiles because it accepts every row up to `minY`.
- This attempt does not use `OW_WILD_TILE_HEADBUTT` and does not broaden the target set.

Implementation shape:

- Add `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`.
- First pass through the headbutt-tree archive:
  - mark existing fallback target grid,
  - try direct cardinal jumps only to strict structural top-row candidates from `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., FALSE, ...)`,
  - return immediately if any strict direct candidate exists.
- Second pass keeps the previous broad direct/exposed-row candidate fallback.
- A read-only explorer confirmed `maxY - 5` is the most plausible strict top-row formula for sparse `treecoords`, with adjacent X pairs as the best X footprint.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test404.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- User reported `test404.nds` was still bugged, with Mankey landing beside/near the canopy instead of on the intended tree top.
- The strict candidate ran first, but the old broad fallback could still win after strict direct selection failed, so the build was still mixing incompatible target definitions.
- Next attempt should stop allowing broad/exposed-row candidates as final Mankey tree-top targets.

### Attempt 247: Strict-Only Mankey Tree-Top Final Targets

Idea:

The `test404.nds` result shows that prioritizing strict structural tree tops is not enough while the broad band fallback is still allowed to produce final targets. For this test, make Mankey tree-top targeting strict-only: direct jumps and BFS target grids both use `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., FALSE, ...)`, and the previous broad band/exposed-row final fallback is not called.

Why this is new:

- Attempts 240-241 used strict structural rows before the coordinate-latched landing fix from Attempt 245, so Mankey could still stop early from current-tile misclassification.
- Attempt 246 prioritized strict structural rows but still kept the broad final fallback, which the latest screenshot suggests was still selecting near-tree/body/side tiles.
- This attempt does not use `OW_WILD_TILE_HEADBUTT`, does not use exposed rows, and does not use the broad direct band as a final target source.

Implementation shape:

- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget` now marks only strict structural top rows in the BFS target grid.
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` no longer calls `OverworldWildSpawns_TryUseDirectMankeyHeadbuttTreeTopBandCandidate` or the exposed-row candidate fallback.
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep` now reports whether the selected first path step is itself a final target, so a direct BFS step onto a tree top can latch as settled.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before and after the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test405.nds`.
- Build warnings were limited to the existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning; the newly unused broad Mankey fallback helpers are expected because this attempt intentionally stops calling that fallback.

Learning:

- User reported `test405.nds` still has the same bug: Mankey stands above/near a visible tree top with the failure bubble and does not take the obvious hop.
- Strict-only final targets helped remove the broad fallback, but the strict top-row formula itself still appears wrong.
- Inspecting `armips/data/headbutt.s` for Route 29 shows entries like `treecoords 646, 385, 647, 385`, which look like the actual top-row pair the user expects Mankey to target. The `maxY - 5` formula would target row `380` for that tree, far above the visible top row and explaining why a 3-tile downward hop is not recognized.

### Attempt 248: Use Archive Top Row For Mankey Tree Tops

Idea:

Attempt 247 proved that strict-only targeting is not enough if the strict row is wrong. The headbutt archive appears to store the relevant top row directly as the minimum Y among a tree's coordinates. For Route 29, obvious visual top-row entries are present as adjacent coordinate pairs, so target `minY` as the strict tree-top row instead of `maxY - 5`.

Why this is new:

- Attempts 246-247 used `maxY - 5` and failed even after broad fallback removal.
- Earlier exposed-row attempts allowed multiple rows and broad bands, so they could still land beside/body/side tiles.
- This attempt keeps final targets strict and two tiles wide, but changes the strict row source to archive `minY`.

Implementation shape:

- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set the strict top row to `minY`.
- Keep the existing adjacent-X/top-left candidate logic so Route 29 pairs like `(646,385),(647,385)` become exactly the two top tiles.
- Keep the Attempt 247 strict-only selector path: no broad band fallback and no `OW_WILD_TILE_HEADBUTT` target definition.
- Remove the unused broad Mankey target helpers that still encoded the rejected `maxY - 5` model, so that fallback cannot be accidentally re-enabled.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test406.nds`.
- Removed the stale broad target helpers, reran `git diff --check`, then rebuilt successfully with `./docker-makerom.cmd` and copied the final cleaned ROM to Delta as `test407.nds`.
- A read-only explorer agent independently confirmed that Route 29-style visual tree-top targeting should use archive `minY`, not `maxY - 5`, and recommended keeping strict-only final targets while removing/quarantining the broad helper.

Learning:

- User reported `test407.nds` lands at the base/contact row of the tree, not the tree top.
- The archive row is therefore not the visual tree top. It behaves like the base/headbutt/contact row for this purpose.
- Next attempt should treat the tree top as two tiles above the archive row and make settled/top recognition use that same strict definition.

### Attempt 249: Target Two Tiles Above Headbutt Archive Row

Idea:

The user clarified that the base at the tree is not a tree top; Mankey needs to land two tiles above it. Attempt 248 proved `minY` is a real tree-associated row, but runtime showed it is the wrong visual row. Keep the strict-only target system, but define Mankey's visual tree top as `minY - 2`.

Why this is new:

- Attempt 246-247 used `maxY - 5`, which targeted too high/wrong rows.
- Attempt 248 used `minY`, which runtime showed is the base/contact row.
- This attempt keeps the successful strict-only cleanup but changes the strict visual row to exactly two tiles above the archive row, matching the latest user correction.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW 2`.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set the strict row to `minY - OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`.
- Reject negative strict rows.
- Change `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` to call `OverworldWildSpawns_TryGetHeadbuttTreeTops(..., FALSE, ...)`, so the base/contact row is not considered a settled tree-top tile.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test408.nds`.
- Build warnings were limited to the existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- User confirmed Mankey reaches the intended hidden tree-top position, and the exclamation bubble attached to that hidden Mankey is visible above the canopy.
- This proves the problem is not that Mankey is gone or on the wrong tile; it is specifically normal Pokemon map-object sprite ordering versus the canopy layer.
- The bubble is rendered through the follower/emote overlay effect path, so a true effect-layer visual remains the most promising long-term direction.

### Attempt 253: Down-First Mankey Tree-Top Target Selection

Idea:

Fix the repeated case where Mankey is above a valid tree-top target but does not jump down three tiles. Attempt 251 still used `MapObject_IsMovementDirectionBlocked` to rank direct tree-top candidates, but final Mankey tree-top targets are intentionally allowed even when normal passability/blocking would reject the destination. That means the blocked helper can wrongly downgrade the exact downward tree-top jump we want.

Why this is new:

- Attempt 251 ranked direct targets by blocked/unblocked immediate direction.
- Earlier target attempts changed which tree-top coordinates are valid, but did not make downward direct jumps deterministic.
- This attempt removes normal blocked-direction ranking from final tree-top target choice and changes only Mankey's tree-top target ordering.
- This does not change the long-hop carrier, render layer probes, headbutt-tree-top coordinate definition, or `OW_WILD_TILE_HEADBUTT` handling.

Implementation shape:

- Disable the generic tree-top effect probe so this ROM tests movement only.
- Add `OverworldWildSpawns_GetMankeyTreeTopDirectionRank`: down is rank `0`, left/right rank `1`, up rank `2`.
- In `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`, stop calling `MapObject_IsMovementDirectionBlocked`.
- Direct targets now rank by shortest distance first; if distance ties, prefer down, then sideways, then up.
- In `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`, search fallback jump directions in down/left/right/up order instead of up/down/left/right.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_GetMankeyTreeTopDirectionRank`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test413.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending user test. The screenshot case should now choose the downward 3-tile tree-top jump instead of stalling or preferring an upward candidate.

### Attempt 254: Restore Archive MinY As Strict Tree-Top Row

Idea:

Fix the remaining refusal to jump three tiles down by restoring the strict `HEADBUTT_TREE_TOPS` row to archive `minY`. Current code had drifted back to `minY - OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`, which targets rows above the actual archive top-row pair. That can make the real 3-tile-down target invisible to both the direct picker and the fallback target grid.

Why this is new:

- Attempt 247 already established from Route 29 archive examples that obvious visual top-row pairs are stored at `minY`.
- Attempt 253 fixed target ordering, but did not notice the strict row had drifted back upward.
- This is not a new broad-row or exposed-row fallback; it restores the strict single-row target definition to the previously verified archive row.
- This does not reintroduce `OW_WILD_TILE_HEADBUTT`, exposed rows, broad bands, render probes, or proxy objects.

Implementation shape:

- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set `structuralTopY = minY`.
- Leave direct target selection down-first from Attempt 253.
- Leave settled/current-tile recognition strict-only.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test415.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- Pending user test. The direct 3-tile-down jump should now be recognized as an actual tree-top target instead of aiming above it.

### Attempt 255: Snap Final Canopy Landing After Partner Restore

Idea:

The user reported that `test415.nds` finally jumps onto the intended tree-top tile, but then Mankey is pushed one tile upward afterward. That means Attempt 254 fixed target selection, and the remaining bug likely happens after the hop lands. The active long-hop path wraps the internal jump with partner prep/restore commands, and final landing was checked before the restore command ran. If the restore nudges object state, the landed object can drift after the correct target was reached.

Why this is new:

- Attempt 254 changed only the strict tree-top row used for target selection.
- Earlier canopy landing attempts changed refresh/recreate behavior, intermediate segment handling, or target rows.
- This attempt does not change tree-top detection, pathing, direct down-first ordering, render probes, object recreation, or `OW_WILD_TILE_HEADBUTT`.
- It only normalizes the final landing tile after the partner restore wrapper has run.

Implementation shape:

- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, cache the staged canopy target before any cleanup can clear it.
- After the long-jump partner restore command runs, if this was the final landing, call `OverworldWildSpawns_SetObjectTile(object, targetX, targetY)`.
- Then run the existing canopy visual cleanup, `OverworldWildSpawns_FinishPendingCanopyHop`, and Mankey tree-top visual update.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test416.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- User reported `test416.nds` made Mankey vanish after every jump.
- Do not retry a full `OverworldWildSpawns_SetObjectTile(object, targetX, targetY)` final snap after partner restore for canopy hoppers. That repeats the historical heavy tile/vector reset visibility failure.

### Attempt 256: Skip Final Mankey Tree-Top Partner Restore

Idea:

Undo the harmful Attempt 255 final tile/vector snap. The new runtime clue says the snap made Mankey vanish, which matches older findings that heavy `SetObjectTile` normalization can corrupt canopy-hop visibility. The remaining one-tile-up shove still appears to happen after the correct landing, so test the direct post-landing culprit instead: keep the partner prep that makes the jump visible, but skip the partner restore command only when this is a final Mankey `HEADBUTT_TREE_TOPS` landing.

Why this is new:

- Attempt 255 tried to correct the post-landing position by forcing the full tile/vector state after restore; runtime says that breaks visibility.
- Attempts 187-190 established the partner prep/restore family is important for jump presentation, but did not test skipping only the final restore on a final tree-top landing.
- This does not change target selection, tree-top rows, direct down-first ordering, pathing, render probes, object recreation, or `OW_WILD_TILE_HEADBUTT`.
- This keeps the scope Mankey tree-top specific instead of changing all canopy hopper jumps.

Implementation shape:

- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, remove the Attempt 255 target snap.
- Add `skipFinalMankeyTreeTopRestore`, true only for a final landing where the active spawn is Mankey and `sOverworldWildMankeyTreeTopLandingExpected[slot]` is armed.
- Still run the existing final `Freeze` command, but skip `OW_WILD_SPAWNER_CANOPY_HOPPER_PARTNER_RESTORE_COMMAND` for that specific landing.
- Continue clearing the prep-active flag, boundary visual state, and final settled-state handling normally.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test417.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- Pending user test. If Mankey remains visible and no longer gets nudged upward, the final partner restore was the post-landing correction source. If the nudge remains, the next narrower test should also skip the final freeze command for Mankey tree-top arrivals.

### Attempt 257: Re-enable Tree-Top Anchored Effect Probe After Movement Fix

Idea:

Return to the canopy rendering problem now that `test417.nds` fixed the final Mankey tree-top movement/settling issue. The earlier rendering evidence says map-object rendering is the wrong layer, while the emotion bubble path is confirmed visible above the canopy. Attempt 252 implemented a generic anchored-effect probe with `ov01_021FFF5C`, but runtime testing moved back to movement fixes before this renderer question was answered. Re-enable that probe now that Mankey reliably lands and settles, and make it fire more frequently so the result is easier to observe.

Why this is new:

- This is not repeating a failed map-object render/proxy approach; those are already ruled out by Attempts 223-228 and 250.
- Attempt 252 built the generic effect probe, but its runtime result was still pending.
- Movement and final tree-top settling were unstable then; `test417.nds` now gives a cleaner canopy-render checkpoint.
- This still does not change target selection, tree-top rows, pathing, object recreation, follower flags, draw callbacks, OAM/cell priority, or live sprite depth.

Implementation shape:

- Set `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED` to `1`.
- Lower `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_FRAMES` from `90` to `45`.
- Keep the existing effect id cycle `0..12`.
- Keep bubble and BG layer probes disabled.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_FRAMES`
- `OverworldWildSpawns_UpdateMankeyTreeTopEffectProbe`
- `ov01_021FFF5C`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test419.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- User reported the canopy rendering is still not fixed.
- The generic anchored-effect probe did not become a usable Mankey visibility solution.
- Do not continue `ov01_021FFF5C` effect-id cycling for the Mankey canopy visual without new evidence. The confirmed useful path remains the follower/emote bubble effect family, not the trail/effect-id family.

### Attempt 258: Late-Draw Mankey Through Field-Effect Render Callback

Idea:

Stop changing the real Mankey map object's render fields. Attempts 223-228, 250, and 257 show map-object/proxy/trail-effect approaches do not solve the canopy priority problem. Instead, create a small persistent field-effect actor while Mankey is settled on a verified headbutt tree-top tile. The effect actor stores the real Mankey object as its anchor and calls `MapObject_GfxDraw` from the effect render callback. This tests whether drawing the same anchored Pokemon sprite from the confirmed above-canopy effect render family changes the layer outcome.

Why this is new:

- Attempts 223-228 changed map-object draw mode, callbacks, priority bits, live OAM/cell depth, or field-object proxies.
- Attempt 250 used a follower-sprite map-object proxy, which still belongs to the losing map-object family.
- Attempt 257 used stock `ov01_021FFF5C` effect ids, but did not draw the Pokemon sprite itself.
- This attempt creates a custom effect descriptor and moves the draw timing/layer family, while leaving the real Mankey object as the logic/battle/movement anchor.

Implementation shape:

- Add imports for the stock field-effect helpers:
  - `ov01_021F146C`
  - `ov01_021F1620`
  - `ov01_021F1640`
  - `FieldEffect_GetInitData`
- Add `OverworldWildFieldEffectDescriptor`.
- Add a Mankey-only late-draw effect work/init struct.
- Disable the old `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED` id-cycling probe.
- While a Mankey slot is settled on a cached tree-top tile, ensure one persistent late-draw effect exists for that slot.
- The effect self-destroys if the slot is no longer an active, current-map, settled Mankey tree-top object.
- For this first test, keep the real Mankey visible too; do not hide it until the effect-layer visual proves stable.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_EnsureMankeyTreeTopLateDrawEffect`
- `OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender`
- `MapObject_GfxDraw`
- `ov01_021F1620`

Runtime result:

- `git diff --check -- include/map_events_internal.h rom.ld src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test420.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Learning:

- User reported the canopy rendering is still not fixed.
- Drawing `MapObject_GfxDraw` from a field-effect render callback is still not enough. The map-object renderer likely submits/sorts through the same losing sprite path even when called late.
- Do not retry effect-timed map-object drawing without new evidence. The next direction must be a true effect-owned sprite/resource payload, not `MapObject_GfxDraw`.

### Attempt 234: Direct Straight Headbutt Tile Target For Mankey

Idea:

The user reported that Mankey still will not jump down three tiles to a visually valid tree target. Attempts 230-233 all depended on interpreting the headbutt tree archive entry into one or more "top" rows. The repeated failure suggests the visually valid tree target may be better identified from the live map tile behavior than from the archive coordinates. Add a Mankey-only direct fallback: before archive-derived tree-top target selection, scan 3-8 tiles straight up/down/left/right from Mankey and choose the nearest actual `OW_WILD_TILE_HEADBUTT` tile.

Why this is new:

- Attempt 230 derived structural tree top rows from archive coordinates.
- Attempt 231 only changed direct candidate priority within that archive-derived set.
- Attempt 232 added exposed archive rows.
- Attempt 233 split targetable rows from settled rows and added X-edge ambiguity for sparse archive entries.
- This attempt bypasses archive interpretation for obvious straight-line jumps and uses the live metatile behavior at the candidate tile instead.

Implementation shape:

- Add `OverworldWildSpawns_TryPickMankeyStraightHeadbuttTileTarget`.
- The helper scans cardinal directions at distances `3..8`.
- A candidate is valid only if `GetMetatileBehaviorAt(fieldSystem, x, y) == OW_WILD_TILE_HEADBUTT` and no active spawn occupies that tile.
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` tries this direct live-tile fallback before scanning the headbutt tree archive.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryPickMankeyStraightHeadbuttTileTarget`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented, but the user correctly rejected the premise before runtime testing.
- The in-progress build still completed and copied to Delta as `test391.nds`; do not use that ROM to evaluate this feature.
- The code path was removed after the user clarified that `OW_WILD_TILE_HEADBUTT` is unrelated to this problem and must not define Mankey's tree-top targeting.

Learning:

- Do not use `OW_WILD_TILE_HEADBUTT` as a proxy for Mankey tree tops.
- Define a dedicated `HEADBUTT_TREE_TOPS` concept from headbutt tree data instead, so this behavior does not bleed into unrelated headbutt mechanics.

### Attempt 235: Dedicated HEADBUTT_TREE_TOPS Archive Target Set

Idea:

The user clarified that `OW_WILD_TILE_HEADBUTT` is unrelated to this Mankey tree-top problem and must not be used as the target definition. Define a dedicated `HEADBUTT_TREE_TOPS` concept from headbutt tree archive data. The important correction is X handling: for a 2-tile-wide tree top, each archive coord X may represent either the left or right tile of that visual two-tile top, so derive possible top-left X candidates from both `coordX` and `coordX - 1`.

Why this is new:

- Attempts 230-233 still assumed one primary left edge from `minX`, with at most one special `minX - 1` fallback for single-column entries.
- Attempt 234 used live `OW_WILD_TILE_HEADBUTT` behavior and was rejected.
- This attempt keeps Mankey tree tops separate from metatile behavior and broadens only the dedicated `HEADBUTT_TREE_TOPS` archive-derived target set.

Implementation shape:

- Add `OverworldWildHeadbuttTreeTops`, containing top rows and top-left X candidates.
- Add `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS` and `OW_WILD_HEADBUTT_TREE_TOPS_MAX_LEFTS`.
- Replace the old row/X helpers with `OverworldWildSpawns_TryGetHeadbuttTreeTops`.
- For every valid coord in one tree entry, add top-left candidates `coordX` and `coordX - 1`.
- Keep the row candidates from prior work:
  - structural row: `maxY - 5`
  - exposed row: `minY`, only when target-picking/path-marking asks for exposed rows
- Update settled recognition, direct candidate picking, and BFS target marking to consume `OverworldWildHeadbuttTreeTops`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOPS_MAX_ROWS`
- `OW_WILD_HEADBUTT_TREE_TOPS_MAX_LEFTS`
- `OverworldWildHeadbuttTreeTops`
- `OverworldWildSpawns_AddHeadbuttTreeTopLeftCandidate`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- Route 29 source-data spot check shows wider dedicated top X sets without using metatile behavior:
  - entry `[(638,389), (639,389), (639,388)]` now yields rows `[384,388]` and top Xs `[637,638,639,640]`
  - entry `[(630,395), (631,395), (630,394)]` now yields rows `[390,394]` and top Xs `[629,630,631,632]`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test392.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 233: Split Mankey Tree Targets From Settled Perches

Idea:

The user reported Mankey standing on a visually invalid tile even though it can jump three tiles left or right to a correct tree-top tile. Attempt 232 broadened target rows by adding the exposed archive `minY` row, but `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` used the same broad rows. That can make Mankey think it is already perched on a valid tree-top tile and short-circuit before target-picking. Split the concepts: use exposed rows and ambiguous X edges for target selection, but use only structural rows for "already settled" recognition.

Why this is new:

- Attempt 230 added one strict 2x6 structural top row.
- Attempt 231 changed nearest direct target priority.
- Attempt 232 added the exposed archive `minY` row everywhere.
- This attempt does not add another Y offset. It separates targetable cells from settled-perch cells and adds X-edge ambiguity only for sparse/single-column tree entries.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_X_CANDIDATES`.
- Add an `includeExposedRows` argument to `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`.
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` now calls the row resolver with `includeExposedRows = FALSE`, so exposed/archive fallback rows no longer count as "already correctly perched."
- Add `OverworldWildSpawns_TryGetHeadbuttTreeTopLeftCandidates`, which keeps `minX` as the primary left edge and adds `minX - 1` only when a tree entry has a single distinct X column.
- Direct target selection and BFS target marking use exposed rows plus those X-edge candidates, so Mankey can still jump to nearby visible targets.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_X_CANDIDATES`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLeftCandidates`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test390.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 230: Mankey 2x6 Headbutt Tree Top-Row Targeting

Idea:

The user noticed each headbutt tree should be treated as a 2-tile-wide, 6-tile-high visual footprint. Previous Mankey tree-top attempts targeted one tile above archive headbutt coordinates, but the archive coordinates are only part of the tree footprint, often lower/interaction-obscured cells. Change Mankey's chill tree-hop state to derive each whole tree footprint from the archive entry and target only the two tiles on the top row of that 2x6 footprint.

Why this is new:

- Attempts 197-199 and 217-219 tried hardcoded Route 29 offsets or `treeY - 1` / `treeY - 2` style offsets from individual archive coordinates.
- This attempt treats one `treecoords` entry as one tree, not as several independent top candidates.
- It derives `topLeftX = min(valid coord x)` and `topY = max(valid coord y) - 5`, matching the newly identified 2x6 tree footprint.
- It does not retry forced Mankey spawning, render-height changes, follower render flags, proxy objects, draw-callback swaps, OAM priority, or live sprite depth.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_WIDTH_TILES 2` and `OW_WILD_HEADBUTT_TREE_HEIGHT_TILES 6`.
- Add `OverworldWildSpawns_TryGetHeadbuttTreeTopRow`, which resolves a whole `OverworldWildHeadbuttTree` archive entry into the two top-row target tiles.
- Update `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` to recognize those two top-row tiles.
- Update direct target selection and BFS target marking to process each tree entry once and mark both top-row cells.
- Keep the final target allowed even if normal map passability says the tree-top tile is blocked; only intermediate hops still require normal landing tiles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_WIDTH_TILES`
- `OW_WILD_HEADBUTT_TREE_HEIGHT_TILES`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopRow`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check` passed.
- A quick Route 29 source-data check maps example entries as intended:
  - `[(588,396), (588,397), (589,397)] -> (588,392)/(589,392)`
  - `[(612,395), (612,396), (613,395), (613,396)] -> (612,391)/(613,391)`
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test386.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 232: Include Exposed Archive Top Row For Mankey Tree Targets

Idea:

The user reported another case where Mankey is three tiles from a valid tree target, this time directly downward, but still stands still. Since Attempt 231 made nearest direct targets win and the problem persisted, the likely issue is that the visible target row is not being marked as a target by the strict `maxY - 5` 2x6 resolver. Some headbutt tree entries are visually/structurally overlapped, so the full structural top may be hidden while the exposed top of the archive entry is the actual useful perch row. Add that exposed archive top row as a secondary target row.

Why this is new:

- This does not repeat the earlier `treeY - 1` or `treeY - 2` per-coordinate offset attempts.
- This still treats one `treecoords` entry as one tree.
- It keeps the 2x6 structural top from Attempt 230, but adds the entry's `minY` as a fallback target row when it differs.
- It does not touch render layers, proxy objects, movement command execution, forced spawning, or the nearest-direct priority from Attempt 231.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_ROW_CANDIDATES 2`.
- Replace the single-row resolver with `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`, returning:
  - structural row: `maxY - 5`
  - exposed row: `minY`, if different
- Update `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`, direct target picking, and BFS target marking to consider both rows.
- Keep both rows tied to the same archive-derived `topLeftX` and 2-tile width.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_CANDIDATES`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopRows`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c include/overworld_wild_spawns_internal.h documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test389.nds`.
- Build warnings were limited to existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

### Attempt 216: Remove Forced Mankey Canopy Tests And Restore Land Mankey

Idea:

Stop the canopy/tree occupancy probe entirely. The current goal is not to keep debugging Mankey on or near trees; it is to remove the forced Mankey headbutt/tree spawn path and make Mankey a normal land-spawn test Pokemon again.

Why this is new:

- Attempts 194-196 intentionally forced Mankey onto headbutt/tree-top test coordinates and disabled movement to isolate render behavior.
- This attempt reverses that test harness instead of trying another tree visibility fix.
- The remaining generic canopy-hopper behavior code is left disconnected from Mankey, so Mankey should not enter the near-tree/on-tree behavior path.

Implementation shape:

- Remove the forced canopy/headbutt spawn macros and forced refill branch.
- Remove the forced Route 29 canopy/headbutt position pickers and render-parameter helpers.
- Remove the forced visible/readable canopy-hop candidate helpers and forced-test debug bubble guards.
- Remove the Mankey behavior-class rule that mapped headbutt Mankey into `OW_WILD_BEHAVIOR_CLASS_CANOPY_HOPPER`.
- Keep the behavior test species override land-only: land spawns become `SPECIES_MANKEY`, while headbutt terrain goes back to normal encounter rolling.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyBehaviorTestSpecies`
- `OW_WILD_SPAWNER_FORCE_BEHAVIOR_TEST_SPECIES`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed.
- `rg` found no remaining forced canopy test macros or helper names in `overworld_wild_spawns_overlay.c`.
- `SPECIES_MANKEY` only remains in the land-only behavior test override.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test371.nds` into the Delta ROM folder.

Runtime result:

- Pending user test.

Learning:

- The forced canopy-top/headbutt Mankey probe had grown into a separate test harness. Removing it cleanly is safer than continuing to patch around tree visibility while the immediate test goal is plain land-spawn Mankey.

### Attempt 217: Mankey Chill Jump To Two Tiles Above Headbutt Tree

Idea:

Give land-spawn Mankey a chill behavior that jumps to the tile two rows above a real headbutt-tree coordinate, then stands still. This should not force Mankey to spawn on tree/canopy tiles and should not treat the destination as a special tree state; the destination is simply allowed even if normal tile blocking would reject it.

Why this is new:

- Attempts 194-196 forced Mankey onto tree/canopy test coordinates at spawn time.
- Attempt 216 removed that forced test harness and restored land-spawn Mankey.
- Earlier canopy hopper attempts used adjacent/headbutt landing validation, return-to-tree logic, or on-tree state checks. This attempt chooses only `(treeX, treeY - 2)` from headbutt-tree data and deliberately skips landing tile block/object checks for that destination.

Implementation shape:

- Add a Mankey behavior variable override: chill is `HEADBUTT_TREE_HOP`, alert and attentive states are disabled.
- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET 2`.
- Add a Mankey-only target picker that scans headbutt-tree archive coordinates and chooses a cardinal 3-8 tile jump to `(treeX, treeY - 2)`.
- Add a settled check using the same headbutt-tree archive data: if Mankey is already two tiles above a headbutt-tree coordinate, it clears stale canopy state and stands still.
- Route Mankey through this custom chill path before the old canopy hopper near-tree/on-tree return logic.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET`
- `OverworldWildSpawns_IsMankeyAboveHeadbuttTree`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test372.nds` into the Delta ROM folder.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 218: Mankey Multi-Jump Pathfinding To Tree-Top Target

Idea:

Keep Attempt 217's final target rule, but allow Mankey to reach that target through more than one jump. Each path edge is still a cardinal 3-8 tile hop. Intermediate landing tiles must be normal valid landing tiles, while the final tile two rows above a headbutt-tree coordinate keeps the special "allowed no matter what is there" behavior.

Why this is new:

- Attempt 217 only selected final targets that were directly reachable in one cardinal 3-8 tile jump.
- Earlier canopy pathing used adjacent/headbutt perch tiles and path steps through normal landing validation.
- This pathing searches for Mankey's exact `(treeX, treeY - 2)` destination and returns the first hop toward it, without reviving forced spawning or tree-occupancy state.

Implementation shape:

- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PATH_MAX_JUMPS 4`.
- Add `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`.
- Keep direct one-hop target selection first.
- If no direct final target is available, run a bounded jump graph search from Mankey's current tile.
- Reuse the canopy path node arrays, but treat each node edge as a full 3-8 tile jump rather than a one-tile walk.
- Return only the first hop target; after landing, the normal chill tick can plan the next hop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PATH_MAX_JUMPS`
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test373.nds` into the Delta ROM folder.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 219: Mankey Lands On Headbutt Tree Top Row

Idea:

Keep Attempt 218's direct and multi-jump pathing, but change Mankey's final landing row from two tiles above a headbutt-tree archive coordinate to the tree top row itself. For paired Route 29 headbutt coords like `(594,389)` and `(595,389)`, this should target `(594,388)` and `(595,388)` rather than `(594,387)` and `(595,387)`.

Why this is new:

- Attempts 217 and 218 deliberately used `treeY - 2`, which matched the earlier "two tiles above" instruction.
- The current request replaces that target rule with "on the headbutt tree on the 2 top tiles."
- This attempt only changes the final/settled target row to `treeY - 1`; it does not reintroduce forced Mankey spawning, tree visibility hacks, or a new movement system.

Implementation shape:

- Change `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET` from `2` to `1`.
- Rename the settled predicate to `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`.
- Keep the direct target scan, bounded jump graph search, and first-hop reconstruction from Attempt 218.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET`
- `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test374.nds` into the Delta ROM folder.
- Build warnings were limited to existing unused helpers/diagnostic symbols on this movement branch plus the existing unused `bsys` battle parameter warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 220: Mankey Tree-Top Render Height Lift

Idea:

Mankey is now correctly landing on the headbutt-tree top tile, but the normal map tile priority draws the tree over the Pokemon. Try a narrow Mankey-only render-height state when it is settled on a headbutt-tree top tile: keep the actual logical X/Y tile unchanged, but set the object's height fields to render level `1` so the object may draw above the tree canopy.

Why this is new:

- Attempts 194/195 tried the full follower-style render bundle (`MapObject_SetFlag29`, `sub_02069DC8`, follower bits) and caused blinking/invisibility.
- Attempt 196 deliberately removed that follower bundle and kept the normal special-field render path.
- Attempt 48 tried manual `posVec[1]` height bobbing for same-tile hop presentation and did not visibly lift spawned Pokemon.
- This attempt does not retry follower render flags or `posVec[1]` alone. It sets `hInit`, `hPrev`, and `hCurr` together with `posVec[1]`, only for settled Mankey on the verified headbutt-tree top tile.

Implementation shape:

- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_RENDER_HEIGHT 1`.
- Add `OverworldWildSpawns_SetObjectHeight`.
- Make generic `OverworldWildSpawns_SetObjectTile` reset height to `0` so this state cannot leak into later movement.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopRenderState`, which sets render height `1` only if the active slot is Mankey and `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` is true.
- Apply the render state after final canopy-hop landing and while Mankey is idling on a tree-top tile.
- Clear height in the canopy visual-state boundary path before future movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_RENDER_HEIGHT`
- `OverworldWildSpawns_SetObjectHeight`
- `OverworldWildSpawns_UpdateMankeyTreeTopRenderState`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build and after documenting the build result.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test375.nds`.

Runtime result:

- User reported Mankey appeared lower/inside the ground rather than higher.
- The effect also happened during every jump, not only after landing on a headbutt-tree top tile.

Learning:

- The `hInit`/`hPrev`/`hCurr` + `posVec[1]` lever is not a tree-priority override for spawned Pokemon.
- Positive object height in this context can visually sink the Pokemon and can leak into jump presentation through shared tile/landing normalization.
- Avoid retrying object-height based canopy priority unless there is new renderer evidence.
- The next direction should be an object-ID-gated draw/priority probe rather than follower render flags or object-height edits.

### Attempt 221: Mankey Tree-Top Priority Flag Probe

Idea:

Remove Attempt 220's height mutation entirely. Isolate the `0x180` map-object flag pair that was previously only tested as part of the unsafe follower render bundle. When a spawned Mankey is settled on a verified headbutt-tree top tile, save its current `flags & 0x180`, clear only those bits plus `BIT_VANISH`, and restore the saved bits when the canopy movement boundary or slot cleanup says it is no longer in that settled tree-top state.

Why this is new:

- Attempt 220 mutated object height fields and `posVec[1]`, which visually sank Mankey and affected jumps.
- Attempts 194/195 cleared `0x180`, but bundled that with `0x2400`, `MapObject_SetFlag29(TRUE)`, and `sub_02069DC8(TRUE)`, causing blinking/invisibility.
- Attempt 196 removed that whole follower-style bundle; it did not isolate `0x180`.
- This attempt does not use follower flags, does not touch object height, does not install a draw callback, and does not move the sprite or logical tile.

Implementation shape:

- Replace the failed render-height constant with `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS 0x00000180`.
- Add per-slot saved-bit storage: `sOverworldWildMankeyTreeTopPriorityBitsSaved` and `sOverworldWildMankeyTreeTopPrioritySavedBits`.
- Add `OverworldWildSpawns_SaveMankeyTreeTopPriorityBits` and `OverworldWildSpawns_RestoreMankeyTreeTopPriorityBits`.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`, which only runs the flag probe when the active slot is Mankey and `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` is true.
- Restore the saved bits in `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary` and clear saved state in `OverworldWildSpawns_ClearSlot`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_PRIORITY_BITS`
- `sOverworldWildMankeyTreeTopPriorityBitsSaved`
- `sOverworldWildMankeyTreeTopPrioritySavedBits`
- `OverworldWildSpawns_SaveMankeyTreeTopPriorityBits`
- `OverworldWildSpawns_RestoreMankeyTreeTopPriorityBits`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the final build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test377.nds`.
- Build warnings were limited to the existing unused helpers/diagnostic symbols on this movement branch plus the existing unused `bsys` battle parameter warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 222: Mankey Failed Tree-Path Backoff And Target Grid

Idea:

Investigate the user report that Mankey sometimes lags the game, possibly because it repeatedly tries and fails to path to a jump/tree target. The frame movement task intentionally ticks while the player is idle, so do not remove the frame task. Instead, make repeated failed Mankey tree-top searches cheaper and less frequent.

Why this is new:

- Attempts 217-221 focused on Mankey tree-top destination selection, hop presentation, and tree rendering/priority.
- No previous recorded attempt added a Mankey-only no-path backoff.
- No previous recorded attempt precomputed the local tree-top target set for the Mankey path search.
- This avoids changing the canopy movement behavior itself and only targets the suspected lag hotspot.

Implementation shape:

- Added per-slot Mankey path-failure state to remember the tile where a path failed.
- Repeated no-path failures from the same tile now back off from 60 to 120 to 180 to 240 frames.
- Moving to a different tile, finding a target, landing on a valid tree-top tile, context cleanup, slot reset, and respawn all clear the path-failure state.
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget` now builds a local grid of valid headbutt-tree top targets while it is already scanning the headbutt-tree archive.
- `OverworldWildSpawns_TryFindMankeyHeadbuttTreeTopPathStep` now checks that target grid in O(1) instead of calling `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` inside the BFS inner loop.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_BASE_COOLDOWN_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_MAX_COOLDOWN_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_PATH_FAILURE_MAX_COUNT`
- `movementMankeyPathFailureX`
- `movementMankeyPathFailureY`
- `movementMankeyPathFailureCounts`
- `sOverworldWildMankeyHeadbuttTreeTopTargets`
- `OverworldWildSpawns_RecordMankeyPathFailure`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- Checked the log first; no prior attempt had tried this exact performance fix.
- A read-only subagent investigation independently identified repeated failed Mankey path searches as a plausible hotspot, especially archive scans inside the BFS inner loop.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c include/overworld_wild_spawns_internal.h documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test378.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- The lag hypothesis is plausible from code inspection: the frame task can retry Mankey tree-top pathing while Mankey remains active, and failed searches previously reused only the short chill cooldown.
- The path search no longer performs archive-backed tree-top checks in its inner loop.

### Attempt 223: Mankey Tree-Top Draw-Mode Probe

Idea:

The user reported Mankey is still visually hidden by the headbutt-tree canopy after landing on the intended tree-top tile. Do not repeat the failed render-height lift, follower render bundle, render offset, or isolated `0x180` flag-only probe. Instead, use a narrow draw-mode probe: when an active Mankey is settled on a verified tree-top tile, save its current `LocalMapObject::unkA0` draw mode, set draw mode `1`, and restore the saved mode when it leaves the tree-top state or the slot is cleaned up.

Why this is new:

- Attempt 220 changed object height fields and `posVec[1]`, making Mankey appear lower/inside the ground.
- Attempts 194/195 used the unsafe follower-style render bundle and caused blinking/invisibility.
- Attempt 221 only cleared the `0x180` map-object priority bits and did not solve the user's screenshot issue.
- This attempt targets draw mode (`unkA0`), which overlay 1's map-object draw path uses to choose between real draw callbacks, without replacing the draw callback or touching object height.

Implementation shape:

- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_MODE 1`.
- Add per-slot saved draw-mode state:
  - `sOverworldWildMankeyTreeTopDrawModesSaved`
  - `sOverworldWildMankeyTreeTopSavedDrawModes`
- Add save/restore helpers for tree-top draw mode.
- Extend the existing Mankey tree-top render override so it saves priority bits and draw mode, clears the old `0x180` bits and `BIT_VANISH`, then sets `object->unkA0 = 1`.
- Restore both draw mode and priority bits when Mankey leaves the tree-top tile, when canopy visual state is cleared, and before slot cleanup releases/deletes the object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_MODE`
- `sOverworldWildMankeyTreeTopDrawModesSaved`
- `sOverworldWildMankeyTreeTopSavedDrawModes`
- `OverworldWildSpawns_SaveMankeyTreeTopDrawMode`
- `OverworldWildSpawns_RestoreMankeyTreeTopDrawMode`
- `OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Verification:

- Checked the log first; draw mode `unkA0` override had not been tried.
- Two read-only explorer agents investigated renderer/headbutt behavior. Their findings supported avoiding height/follower flags and targeting the draw path/draw mode or a future object-ID-gated draw callback.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c include/overworld_wild_spawns_internal.h documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test379.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 232: Mankey Low Land Row Tree-Top Correction

Idea:

Fix the specific case where Mankey settles two tiles too low under the canopy/base edge. Do not touch the shared headbutt-tree top detector, because the previous broad row-lift work made already-working Mankey tree cases stop moving. Instead, normalize only Mankey's tree-top target rows through one Mankey-specific helper: if the candidate already has a headbutt/contact anchor two rows below it, leave it alone; otherwise, if the candidate row is passable, lift it two rows.

Why this is new:

- Earlier attempts changed shared headbutt-tree top detection or tried broad direct-row lifting.
- The user reported the broad/shared approach reintroduced old failures where Mankeys stopped moving.
- This attempt is Mankey-only and applies the same narrow target correction to all three Mankey consumers: settled check, direct target picker, and path target grid.
- This uses the headbutt metatile only as a two-rows-below anchor guard, not as the destination set, and does not alter spawn logic, hop execution, rendering, or generic canopy hopper behavior.

Implementation shape:

- Replace the broad direct row-lift constant with `OW_WILD_HEADBUTT_TREE_TOP_LOW_LAND_ROW_LIFT`.
- Add `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY`.
- In that helper, keep candidates whose `candidateY + 2` tile is `OW_WILD_TILE_HEADBUTT`.
- Otherwise, lift passable candidate rows by two tiles.
- Use that helper in:
  - `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
  - `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
  - `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- Remove the direct-picker loop that generated multiple lifted rows from one archive target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_LOW_LAND_ROW_LIFT`
- `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY`

Verification:

- Checked the attempt log before editing.
- A read-only explorer confirmed the safest choke point is `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY`, and recommended avoiding `TryGetHeadbuttTreeTops`, movement carrier code, render/proxy/layer hacks, and broad row offsets.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed after the code edit.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test430.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 233: Mankey 2x3 Footprint Top-Row Targets

Idea:

Use the user's clarified tree model directly: each headbutt tree is a 2-wide x 3-high logical footprint, and the only valid Mankey target tiles are the two logical top-row tiles of that footprint. Overlapping/obstructed trees can hide lower rows, so the Mankey target resolver must not infer targets from lower/base/contact rows, metatile lifting, or exposed-row bands.

Why this is new:

- Attempt 232 still tried to repair old inferred rows with metatile/contact-row checks.
- Earlier attempts mutated the shared `OverworldWildSpawns_TryGetHeadbuttTreeTops` helper, which also feeds non-Mankey concepts and caused regressions.
- This attempt adds a Mankey-only footprint helper and does not use the old `includeExposedRows`, broad row offsets, `minY - 1`, `maxY - 2`, or single-column fallback candidates.

Implementation shape:

- Add `OW_WILD_MANKEY_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES` and `OW_WILD_MANKEY_HEADBUTT_TREE_MAX_FOOTPRINT_Y_SPAN`.
- Add `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`.
- The helper accepts only entries that prove exactly two adjacent X columns and no more than a 3-tile Y span.
- The helper marks only `minY` as the valid top row and only `minX`/`minX + 1` as the valid top tiles.
- Wire the helper into:
  - `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`
  - `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
  - `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- Remove the old `OverworldWildSpawns_GetMankeyHeadbuttTreeTopTargetY` metatile lift path from active code.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_MANKEY_HEADBUTT_TREE_FOOTPRINT_HEIGHT_TILES`
- `OW_WILD_MANKEY_HEADBUTT_TREE_MAX_FOOTPRINT_Y_SPAN`
- `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`

Verification:

- Checked the attempt log before editing.
- A read-only explorer recommended this exact Mankey-only footprint helper approach and warned against `maxY`-based top reconstruction and single-column fallbacks.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed before documenting the attempt.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test431.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning. `OverworldWildSpawns_TryGetHeadbuttTreeTops` is now also warned unused because Mankey no longer consumes that shared helper.

Runtime result:

- User reported that `test431.nds` still placed Mankey two tiles too far down for same-row Route 29 headbutt-tree entries.

Learning:

- Same-row two-column Mankey footprint entries can represent the tree's lower/contact row rather than the logical top row.
- These entries need to lift the target row by two tiles, while multi-row entries should keep using their minimum Y row to avoid reintroducing the obstructed-tree one/two-tiles-too-high regressions.

Follow-up verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test432.nds`.
- Runtime result: pending user test.

### Attempt 235: Direct Two-Tile Mankey Tree-Top Final Hop

Runtime result from `test432.nds`:

- User reported a Mankey standing two tiles above a valid tree-top target did not move down onto it.

Learning:

- This is a different failure from the previous row-classification issue.
- The active canopy hopper minimum distance is `3`, and both the direct Mankey tree-top picker and the pending canopy-hop executor reject a two-tile final target.
- Earlier investigation showed stock `Jump*2` can be a stable two-tile carrier, and the current long-hop restrictions were meant to avoid unstable general/random short hops, not to forbid a direct final tree-top landing.

Implementation shape:

- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_MIN_HOP_TILES` as a Mankey-only direct-final-tree-top minimum of `2`.
- Let `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate` accept distance-2 candidates.
- Mark `sOverworldWildMankeyTreeTopLandingExpected` before staging the Mankey tree-top hop so staging can use the Mankey-specific minimum.
- In `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, allow a pending Mankey tree-top distance-2 target and start the existing direction-specific `Jump*2` command for that final hop.
- Do not change `OverworldWildSpawns_TryGetMankeyHeadbuttTreeFootprintTops`, random canopy hop selection, or multi-step path search.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_MIN_HOP_TILES`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test433.nds`.

Runtime result:

- User reported the exact same two-tiles-above-tree situation still did not move.

### Attempt 236: Use Prepared Internal Jump For Two-Tile Mankey Final Target

Learning:

- A read-only explorer agreed the picker should be able to find the Route 29 two-tile-down target when it is aligned with one of the marked headbutt tree-top tiles.
- The weak point in Attempt 235 was the executor: it used stock `Jump*2` for the distance-2 final hop.
- Earlier canopy-hop investigation showed stock `Jump*2` is not the stable long-hop carrier we want here; the working Mankey long-hop path uses the prepared internal jump carrier.

Implementation shape:

- Keep the Attempt 235 Mankey-only distance-2 target selection and staging rules.
- Relax `OverworldWildSpawns_GetCanopyLongJumpTiming` so timing can be calculated for distance `2` after the caller approves it.
- Move the minimum-distance rule into `OverworldWildSpawns_StartCanopyLongJumpCommand`, using `2` only when the active slot is Mankey and `sOverworldWildMankeyTreeTopLandingExpected` is set.
- Remove the stock `Jump*2` distance-2 fallback from `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, so the prepared internal jump path handles the final two-tile landing.
- Do not change the headbutt-tree footprint resolver.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test434.nds`.

Runtime result:

- Pending.

### Attempt 237: Revert Two-Tile Mankey Canopy-Hop Relaxation

Runtime clarification:

- User clarified there was no bug in the reported case: it was a two-tile hop, and Mankey should not be expected to make a two-tile canopy hop.

Learning:

- Attempts 235 and 236 were based on a bad premise: treating the two-tile-down case as a valid Mankey tree-top hop.
- The intended canopy-hopper rule remains 3-8 tiles. A two-tile target should be ignored or reached through another valid hop/path, not by adding a special two-tile final landing exception.

Implementation shape:

- Remove the Mankey-specific two-tile final tree-top exception.
- Restore direct Mankey tree-top candidate selection to the normal `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES` minimum.
- Restore Mankey tree-top path search to 3-8 tile hops only.
- Restore canopy-hop staging, prepared long-jump timing, and execution to reject distances below the normal long-jump minimum.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test436.nds`.

### Attempt 238: Generic Headbutt Tree-Top Location Filter

Idea:

Make the settled headbutt tree-top location resolver reusable for future behavior profiles instead of keeping it named as Mankey-specific logic.

Why this is new:

- Earlier Mankey tree-top attempts focused on correcting the tile semantics and rendering. This pass does not change those semantics.
- The current goal is an internal API cleanup: future behaviors should be able to ask for valid headbutt tree-top locations without depending on Mankey names.

Implementation shape:

- Rename the footprint resolver to `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`.
- Rename the field/tile predicate to `OverworldWildSpawns_IsHeadbuttTreeTopLocation`.
- Rename the footprint-span constants from Mankey-specific names to `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_*`.
- Keep `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile` as a thin wrapper for existing Mankey-specific call sites.
- Remove the older unused `OverworldWildSpawns_TryGetHeadbuttTreeTops` helper so there is one canonical generic tree-top location filter.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`
- `OverworldWildSpawns_IsHeadbuttTreeTopLocation`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_FOOTPRINT_HEIGHT_TILES`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_MAX_FOOTPRINT_Y_SPAN`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test437.nds`.

### Attempt 239: Accept Single-Column Headbutt Tree-Top Archive Entries

Runtime result from `test437.nds`:

- User reported nearby tree-top targets #1 and #2 were not being validated by the generic headbutt tree-top locator, even though they were within the valid 3-4 tile jump range.
- User also clarified target #3 should remain invalid for movement selection because it is only 2 tiles away.

Learning:

- The generic locator still required each archive entry to contain exactly two adjacent X columns.
- Route 29 has valid headbutt tree entries represented by a single X column in the archive.
- Rejecting single-column entries makes reachable side tree-top targets invisible to Mankey's target picker.
- This is a locator fix, not a movement-range fix. The 3-8 tile canopy-hop rule should stay unchanged so two-tile targets remain rejected by movement selection.

Implementation shape:

- Keep the existing two-column case unchanged.
- If an archive entry has one distinct X column and otherwise fits the accepted vertical footprint span, infer both possible 2-wide top surfaces around that column:
  - `x - 1, x`
  - `x, x + 1`
- Keep rejecting wider/non-adjacent or overly tall archive footprints.
- Do not reintroduce any two-tile Mankey hop exception.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test438.nds`.

### Attempt 240: Add Obscured Vertical Tree-Top Stack Rows

Runtime result from `test438.nds`:

- User reported the locator still did not validate the intended side-column tree tops.
- User clarified the valid targets are the top rows of obscured 2x2 trees that do not show the base.

Learning:

- Attempt 239 fixed single-column archive entries, but the locator still exposed only one top row per archive-derived tree footprint.
- The side-column targets are repeated obscured canopy tops stacked vertically above the archive-derived row.
- This should be fixed in the locator, not by relaxing movement range: the 2-tile target remains invalid because canopy hops are still 3-8 tiles.

Implementation shape:

- Add `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_STACK_STEP_TILES`, matching the 3-tile tree footprint spacing.
- Add `OverworldWildSpawns_AddHeadbuttTreeTopRowCandidate` to de-duplicate top rows.
- For each accepted headbutt tree column, add the archive-derived top row and then additional top rows upward by the stack step until the per-tree row cap is reached.
- Keep the existing two-column and single-column X-location logic from Attempt 239.
- Do not reintroduce any two-tile Mankey hop exception.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_LOCATION_STACK_STEP_TILES`
- `OverworldWildSpawns_AddHeadbuttTreeTopRowCandidate`
- `OverworldWildSpawns_TryGetHeadbuttTreeTopLocations`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test439.nds`.

### Attempt 241: Filter Generated Tree-Top Rows By Blocked Canopy Surface

Runtime result from `test439.nds`:

- User reported Mankey completely lost the plot and started stopping on positions that were not intended tree tops.

Learning:

- Attempt 240's vertical stack was too broad.
- The locator generated possible rows but did not check whether each generated 2-wide surface was actually a tree/canopy surface on the current map.
- Because `OverworldWildHeadbuttTreeTops` stores left columns and rows separately, broad row generation can create invalid cross-product targets on ordinary grass.
- The fix should constrain generated row/left pairs at use time, rather than relaxing movement or reverting to a single archive row.

Implementation shape:

- Add `OverworldWildSpawns_IsHeadbuttTreeTopSurface`.
- Treat a generated 2-wide top surface as usable only when both map tiles are blocked and are not surf behavior.
- Apply the surface check in:
  - `OverworldWildSpawns_IsHeadbuttTreeTopLocation`
  - `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
  - `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`
- Keep the 3-8 tile movement rule unchanged and do not reintroduce a two-tile Mankey hop exception.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsHeadbuttTreeTopSurface`
- `OverworldWildSpawns_IsHeadbuttTreeTopLocation`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_MarkMankeyHeadbuttTreeTopTarget`

Verification:

- Pending.
