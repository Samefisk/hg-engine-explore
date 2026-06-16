# Canopy Long-Hop Movement Attempts

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Tracks the movement carrier work for visible multi-tile Mankey jumps.
- Partner-prepped internal jump was the important breakthrough; broad generalization caused regressions.
- Keep hop distance constrained and avoid helper-object/recreate/raw-posVec paths unless there is new evidence.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 65 | 181 | Tree-Anchor Visibility Baseline |
| 66 | 182 | Tree-Anchor Single Stock Jump Probe |
| 67 | 183 | Tree-Anchor Stock Jump2 Probe |
| 68 | 184 | Tree-Anchor Chained Jump2 Four-Tile Probe |
| 69 | 185 | Chained Jump2 Without Midpoint Tile Normalization |
| 70 | 186 | Chained Jump2 With Logical-Only Midpoint Commit |
| 71 | 187 | Partner-Wrapped Moving Jump2 Probe |
| 72 | 188 | Partner-Wrapped Chained Jump2 Four-Tile Probe |
| 73 | 189 | Single Partner Wrapper Around Two Jump2 Commands |
| 74 | 190 | Partner-Prepped Single Internal Four-Tile Jump |
| 75 | 191 | Production Canopy Long-Jump Carrier |
| 77 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 78 | 237 | Allow Two-Tile Final Tree-Top Landings In Mankey Path Search |
| 79 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 80 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 83 | 226 | One Row Above Archive Mankey Tree-Top Target |
| 98 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 116 | 236 | Mankey Tree-Top Effect-Layer Bubble Probe |
| 117 | 237 | Cache Mankey Tree-Top Archive Predicate |
| 133 | 253 | Down-First Mankey Tree-Top Target Selection |
| 135 | 255 | Snap Final Canopy Landing After Partner Restore |
| 136 | 256 | Skip Final Mankey Tree-Top Partner Restore |
| 140 | 235 | Dedicated HEADBUTT_TREE_TOPS Archive Target Set |
| 231 | 153 | Mankey Canopy Hopper Headbutt-Tree Profile |
| 232 | 154 | Canopy Hopper Attentive Ambush Target |
| 233 | 155 | Canopy Hopper Tired Return-To-Tree Case |
| 234 | 156 | Force Land Test Spawns To Mankey |
| 235 | 157 | Universal Canopy Hopper Return-To-Tree Priority |
| 236 | 158 | Canopy Hopper Pre-Hop Wait |
| 237 | 159 | Canopy Hopper Visible Jump Chain |
| 238 | 160 | Seven-Tile Canopy Hop Target And No Bounce-Back |
| 239 | 161 | Canopy Hopper Far-Preferred Tree Selection |
| 240 | 162 | Custom Rendered Far Canopy Hop |
| 241 | 163 | Canopy Helper Object Far-Hop Visual |
| 242 | 164 | Helper Object Stock-Jump Segments |
| 243 | 165 | Real Object Stock-Jump Chain Without Segment Wait |
| 244 | 166 | Real Object Deferred Logical Commit Render-Hop |
| 245 | 167 | Horizontal WaitJump Command Probe |
| 246 | 168 | Strict Five-To-Seven Tile Canopy Hop Probe |
| 247 | 169 | Recreate Real Canopy Object After Each Segment |
| 248 | 170 | Canopy Hopper Always-Visible Invariant |
| 249 | 171 | Boundary-Only Canopy Visual Cleanup |
| 250 | 172 | Skip Object Refresh On Canopy Tree Landings |
| 251 | 173 | Keep Same Object Across Intermediate Canopy Landings |
| 252 | 174 | Settle Intermediate Canopy Segment Handoff |
| 253 | 175 | Recreate Final Tree Landing Without Manual Tile Rewrite |
| 254 | 176 | Use One Manual Render Hop For Full Canopy Distance |
| 255 | 177 | Canopy Hopper Vanilla Movement-List Task |
| 256 | 178 | Canopy Movement Lists Use Jump2 Runs And No Final Recreate |
| 257 | 179 | Direct Engine-Owned Long Canopy Jump |
| 258 | 180 | Clean Straight-Run Canopy Driver |
| 259 | 192 | Range-Gated Canopy Long-Jump Carrier |
| 260 | 193 | Exact Headbutt Perches And Pre-Stage Carrier Validation |
| 261 | 194 | Forced Mankey Tree-Tile Occupancy Render Probe |
| 274 | 235 | Direct Two-Tile Mankey Tree-Top Final Hop |
| 275 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 276 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |

## Original Attempt Sections

### Attempt 181: Tree-Anchor Visibility Baseline

Idea:

Pause canopy hopping entirely and put canopy Mankey back on the actual headbutt-tree coordinate used by ordinary headbutt spawns. Other headbutt spawns are visible on that coordinate, while the canopy path had been relocating Mankey to an adjacent perch and then running custom hop ownership. This test isolates whether the invisibility is caused by the perch/custom movement path rather than by the headbutt tree coordinate itself.

Implementation shape:

- Add a tree-anchor baseline switch for canopy hoppers.
- When spawning a canopy hopper from the headbutt pool, keep `position.startX/startY` as the tree coordinate instead of replacing it with `position.headbuttPerchX/Y`.
- Make `OverworldWildSpawns_TryStartHeadbuttTreeHop` return without starting movement while the baseline switch is active.
- Clear `BIT_VANISH` and set a normal cooldown so an idle Mankey remains visible and the frame task has no active canopy jump/list/internal movement to clean up on route transitions.
- Add a detach-only route context-loss reset that zeros custom movement bookkeeping and static canopy task pointers without calling `MapObject_*`, deleting helpers, or asking stale movement-list tasks to clean up.

Why this is new:

- Attempt 170 tried an always-visible invariant while movement was still active; this disables canopy movement instead.
- Attempts 177-180 all still attempted movement via movement lists or the internal jump starter; this does not.
- Earlier tree/perch attempts changed final landing refresh behavior; this tests stock-style initial tree anchoring before any canopy movement begins.
- This follows the user's observation that other Pokemon spawned on headbutt trees do not become fully invisible.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_VISIBILITY_BASELINE`
- `OverworldWildSpawns_DetachAllMovementStateOnContextLoss`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`
- `OverworldWildSpawns_SpawnOne`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test348.nds` and copied to Delta.
- Verified the active baseline switch keeps canopy Mankey at the original headbutt-tree spawn coordinate instead of relocating it to the perch coordinate.
- Verified `OverworldWildSpawns_TryStartHeadbuttTreeHop` exits before starting canopy movement while the baseline switch is active, clearing `BIT_VANISH` and setting a normal cooldown only.
- Verified route context-loss now uses `OverworldWildSpawns_DetachAllMovementStateOnContextLoss`, which zeros custom bookkeeping and static canopy task pointers without calling `MapObject_*`, deleting helpers, or cleaning up stale movement-list tasks.
- The edited overlay compiled; unused-helper warnings are expected in this baseline because the active canopy movement paths are intentionally disconnected.

Runtime result:

- User reported:
  - Mankey is visible while idle on/at headbutt trees.
  - Leaving the route does not freeze or crash.
  - Hop distance/movement feel was not tested because hopping is intentionally disabled in this baseline.

Learning:

- The headbutt-tree anchor itself is not what makes canopy Mankey invisible.
- The route-transition crash/freeze is tied to active canopy movement cleanup/state ownership, not to an idle Mankey on a tree.
- The next movement attempt should start from this stable tree-anchor baseline and add one movement owner back at a time.

### Attempt 182: Tree-Anchor Single Stock Jump Probe

Idea:

Start from the successful Attempt 181 tree-anchor baseline and add back exactly one stock real-object jump command. This tests whether movement itself is safe when Mankey remains anchored to the normal headbutt-tree spawn path and route context-loss uses detach-only cleanup.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_VISIBILITY_BASELINE`.
- Add `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE`.
- Keep canopy Mankey on the original headbutt-tree spawn coordinate.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, or the direct internal long-jump starter.
- When the canopy behavior ticks, clear stale canopy target state, clear `BIT_VANISH`, pick one adjacent valid canopy/headbutt landing tile, and start a normal direction-specific `Jump*` command on the real object.
- If no adjacent valid canopy tile exists, idle visibly instead of forcing movement.
- Let the existing generic movement-finish handler settle the one-tile command; no pending far target is staged.

Why this is new:

- Attempt 181 proved idle tree anchoring is visible and route-safe, but did not move.
- Attempts 162, 163, 166, and 176 used raw render-position travel or helper objects; this does not.
- Attempts 177-180 used movement lists or direct internal long-jump ownership for far targets; this does not.
- Attempts 159, 161, 165, 167, and 168 tested stock movement as a far-hop carrier from older canopy/perch movement state; this revalidates one stock movement owner from the stable tree-anchor baseline.
- A sidecar explorer confirmed there is no proven stock 5-7 tile visible jump primitive in the repo; stock commands are still useful as short-jump safety probes, but the eventual long-hop solution should trace the full stock jump state contract rather than retrying `Jump*2`, movement lists, or raw `posVec` travel.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE`
- `OverworldWildSpawns_TryPickAdjacentCanopyStepTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test349.nds` and copied to Delta.
- Verified the single-jump probe leaves the tree-anchor spawn override active by preventing the older perch relocation while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE` is enabled.
- Verified the active canopy tick clears stale canopy target state, clears `BIT_VANISH`, and starts one normal real-object `Jump*` command only when an adjacent valid canopy/headbutt landing tile exists.
- Verified the probe does not stage a far pending target, start a movement-list task, use helper/recreate paths, call the direct internal long-jump starter, or run raw render-position interpolation.
- The edited overlay compiled; unused-helper warnings are expected because the legacy canopy helper/recreate/movement-list paths remain disconnected during this probe.

Runtime result:

- User reported:
  - Mankey stays visible.
  - Mankey does a visible short jump.
  - Leaving the route still avoids crash/freeze.

Learning:

- The stable tree-anchor baseline can safely run a normal stock real-object jump command.
- Route-transition stability holds when the active movement owner is the normal single-command path and context-loss uses detach-only cleanup.
- This gives a safe base for testing slightly longer stock jump variants without reintroducing helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec`, or the internal long-jump starter.
- User suggested the practical hop maximum may be 4 and hop distance may be related to movement speed. The movement command table shows explicit `Jump*` and `Jump*2` families, but no named 3/4/5/6/7 jump commands, so the next probe should test `Jump*2` from the same stable tree-anchor baseline before assuming a custom long-hop contract.

### Attempt 183: Tree-Anchor Stock Jump2 Probe

Idea:

Keep the successful Attempt 182 setup, but switch the active probe from one-tile `Jump*` to two-tile `Jump*2`. The user suggested the practical hop ceiling may be around 4 and hop distance may be tied to speed; this first verifies whether the stock two-tile jump family actually lands two tiles safely when started from the stable tree-anchor baseline.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_JUMP_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE`.
- Keep canopy Mankey on the original headbutt-tree spawn coordinate by keeping the older perch relocation disabled while either tree-anchor probe is active.
- Generalize the one-step landing picker into `OverworldWildSpawns_TryPickStraightCanopyStepTarget`, taking a desired straight-line distance.
- Pick a straight two-tile valid canopy/headbutt landing target.
- Start a normal direction-specific `Jump*2` command on the real object through `OverworldWildSpawns_StartMovementCommandForSlot` with pending distance `2`.
- Do not stage a far pending target, use helper/recreate paths, start a movement-list task, call the internal long-jump starter, touch phantom cleanup, or run raw `posVec` interpolation.

Why this is new:

- Attempts 159, 161, 165, 167, and 168 tested stock jump families from the older canopy/perch movement path and did not establish route-safe tree-anchor movement.
- Attempt 182 proved one stock jump from the stable tree anchor is visible and route-safe.
- This is the first test of `Jump*2` from that stable tree-anchor baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE`
- `OverworldWildSpawns_TryPickStraightCanopyStepTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test350.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE` is enabled while the baseline and one-step probe flags are disabled.
- Verified the probe keeps the tree-anchor spawn override active by preventing the older perch relocation while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE` is enabled.
- Verified `OverworldWildSpawns_TryPickStraightCanopyStepTarget` picks a straight two-tile landing target and the active canopy tick starts a direction-specific stock `Jump*2` command with pending distance `2`.
- Verified the probe does not stage a far pending target, start a movement-list task, use helper/recreate paths, call the internal long-jump starter, touch phantom cleanup, or run raw `posVec` interpolation.
- The edited overlay compiled; unused-helper warnings are expected because the legacy canopy helper/recreate/movement-list paths remain disconnected during this probe.

Runtime result:

- User reported:
  - Mankey stays visible.
  - The hop visibly travels 2 tiles.
  - Leaving the route still avoids crash/freeze.

Learning:

- The stable tree-anchor baseline can safely run a stock real-object `Jump*2`.
- `Jump*2` is confirmed as a visible two-tile carrier in this context, contradicting the older failed canopy/perch results where the setup made the movement look like only 1-2 tile travel or became unstable.
- The next non-repeating probe is to chain two real-object `Jump*2` commands from the same tree-anchor baseline to test the user's possible practical 4-tile hop cap.

### Exploration Note: Directional Hop Accident

Prompt:

The user remembered that an earlier hop-in-place attempt accidentally did not lock the Pokemon in place, causing it to jump in the direction chosen by other behavior rules. Explore whether that accident points toward a canopy movement solution.

Relevant prior evidence:

- Attempt 50 used `LockDir -> Jump*2 -> WaitJumpSite -> ReleaseDir` for a spot emote. Runtime showed a visible hop, but the Pokemon moved toward the player instead of hopping in place.
- Attempt 51 replaced the moving `Jump*2` with `Jump*Site` under the same `LockDir`/`ReleaseDir` style wrapper. Runtime showed no visible hop.
- Attempt 52 used the follower/partner-style wrapper found in shipped scripts: `0x49 -> Jump*Site -> Freeze -> 0x4A`. Runtime finally showed a visible same-tile hop.
- Attempt 182 proved that a normal one-tile stock `Jump*` from the stable tree-anchor baseline is visible and route-safe.
- Attempt 183 is testing whether a normal two-tile stock `Jump*2` from the same stable tree-anchor baseline is visible and route-safe.

Interpretation:

- The old accident was likely not "hop-in-place almost worked"; it was evidence that moving jump commands (`Jump*` / `Jump*2`) correctly enter the visible airborne movement path when given a direction.
- The same-tile `Jump*Site` command only became visible after the follower/partner wrapper `0x49`/`0x4A`, which suggests that wrapper changes object presentation state, facing lock state, or follower-style jump prep/restore state.
- No prior attempt has combined the two useful ingredients from the stable tree-anchor baseline: `0x49`/`0x4A` partner wrapper plus a moving `Jump*` or `Jump*2` travel command.

Next non-repeating probe:

- Keep the stable tree-anchor setup from Attempts 181-183.
- Start a short moving canopy hop through a partner-style sequence: `0x49 -> direction-specific Jump*2 -> Freeze -> 0x4A`.
- Use only the real object and the existing frame-updated single-command path.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, or direct `MapObject_StartJumpMovementInternal`.
- If the wrapped `Jump*2` is visible and route-safe, test chaining two wrapped two-tile hops as the possible practical 4-tile hop cap.

### Attempt 184: Tree-Anchor Chained Jump2 Four-Tile Probe

Idea:

Attempt 183 proved plain stock `Jump*2` is a visible and route-safe two-tile carrier from the stable tree-anchor baseline. Before adding the partner/follower wrapper as another variable, test the user's possible 4-tile hop cap by chaining two plain real-object `Jump*2` commands toward one staged four-tile target.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE`.
- Keep canopy Mankey on the original headbutt-tree spawn coordinate by keeping the older perch relocation disabled while any tree-anchor probe is active.
- Reuse `OverworldWildSpawns_TryPickStraightCanopyStepTarget`, now validating intermediate two-tile landing points before accepting a four-tile target.
- Stage a normal pending canopy target four tiles away in one cardinal direction.
- While the chained probe is active, `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` starts a direction-specific stock `Jump*2` for each two-tile segment until the staged target is reached.
- Keep using the real object and the existing frame-updated single-command path.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 178 used movement lists with jump runs from the older canopy path.
- Attempt 179 and 180 used direct internal long-jump ownership or older far-hop state.
- Attempt 183 proved one plain tree-anchor `Jump*2` is safe; this is the first test of chaining two such confirmed-safe segments from the same stable baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE`
- `OverworldWildSpawns_TryPickStraightCanopyStepTarget`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test351.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE` is enabled while the baseline, one-step, and single `Jump*2` probe flags are disabled.
- Verified the four-tile target is only accepted after validating the final tile and the intermediate two-tile landing point.
- Verified the pending-hop executor uses stock direction-specific `Jump*2` segments until the staged target is reached.
- Verified this attempt does not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test351.nds`.
- Mankey stays visible until the first stock `Jump*2` segment completes.
- After the first two tiles of the four-tile hop, Mankey loses visibility and never regains it.
- The hop does cover four tiles.
- Leaving the route still avoids crash/freeze.

Learning:

- Chaining stock `Jump*2` commands proves the route-safe engine-owned path can cover a four-tile target.
- The failure is not target distance or route-leave cleanup.
- The failure appears at the segment handoff after the first two-tile stock jump completes, before or during the second stock segment.
- Next probes should focus on the midpoint finish/normalization/handoff state, not on tree-anchor spawn visibility or target selection.

### Attempt 185: Chained Jump2 Without Midpoint Tile Normalization

Idea:

Attempt 184 proves the two-segment stock `Jump*2` carrier can travel four tiles, but visibility is lost after the first two-tile segment. The current non-final segment handler rewrites object tile/init/prev state and X/Z render vectors with `OverworldWildSpawns_SetObjectTile` before the second segment. Test whether that midpoint normalization corrupts the stock jump/render state by skipping it only for the chained probe.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE`.
- Keep the same stable tree-anchor setup and the same staged four-tile cardinal target.
- Keep chaining stock direction-specific `Jump*2` commands through the existing pending-hop executor.
- On non-final segment completion, do not call `OverworldWildSpawns_SetObjectTile`; leave the stock movement command's landing state intact before the existing segment settle cooldown and second segment.
- Keep clearing `BIT_VANISH` at the canopy boundary.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 184 chained confirmed-safe stock `Jump*2` segments but still normalized the object at the midpoint.
- Earlier visibility attempts focused on helper objects, recreate/refresh, movement lists, raw render hopping, tree/perch selection, or direct internal long jumps.
- This is the first probe that isolates the midpoint `SetObjectTile` rewrite while keeping the otherwise successful four-tile stock chain.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test352.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE` is enabled while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_PROBE` is disabled.
- Verified the non-final canopy segment handler skips `OverworldWildSpawns_SetObjectTile` only for this probe.
- Verified the probe keeps the same stock direction-specific `Jump*2` segment chain and the same four-tile staged target from Attempt 184.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test352.nds`.
- Mankey only jumps two tiles at a time.

Learning:

- Fully skipping the midpoint tile normalization does not preserve the four-tile chained hop behavior from Attempt 184.
- The first segment likely still needs some logical midpoint commit before the second stock `Jump*2`.
- Since Attempt 184's full `SetObjectTile` midpoint commit preserved four-tile travel but broke visibility, the next probe should split logical tile commit from render-vector commit.

### Attempt 186: Chained Jump2 With Logical-Only Midpoint Commit

Idea:

Attempt 184 used full midpoint `OverworldWildSpawns_SetObjectTile` and preserved four-tile travel, but Mankey became invisible after the first two tiles. Attempt 185 skipped midpoint commit entirely and Mankey only jumped two tiles at a time. Test the middle path: commit only the logical tile/current/previous fields after the first segment, but leave the stock movement command's render vectors untouched.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_NO_MIDPOINT_NORMALIZE_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE`.
- Add `OverworldWildSpawns_SetObjectLogicalTileOnly`, which updates `MapObject_SetCurrentX/Y`, `xInit/yInit`, and `xPrev/yPrev` but does not rewrite `posVec[0]` or `posVec[2]`.
- On non-final canopy segment completion, call the logical-only helper instead of full `OverworldWildSpawns_SetObjectTile`.
- Keep the same stable tree-anchor setup, staged four-tile cardinal target, segment settle cooldown, and stock direction-specific `Jump*2` chain.
- Do not use helper objects, object recreate/refresh, phantom cleanup, movement-list tasks, raw `posVec` interpolation, the partner wrapper, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 184 proved full midpoint tile/vector normalization preserves four-tile travel but breaks visibility.
- Attempt 185 proved no midpoint normalization preserves neither full travel nor the intended chain.
- No previous attempt has separated logical map-object tile commit from render-vector commit at the stock jump segment boundary.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE`
- `OverworldWildSpawns_SetObjectLogicalTileOnly`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test353.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE` is enabled while the full-midpoint and no-midpoint chained probes are disabled.
- Verified `OverworldWildSpawns_SetObjectLogicalTileOnly` commits current/init/previous tile fields but leaves `posVec[0]` and `posVec[2]` untouched.
- Verified the non-final canopy segment handler uses the logical-only helper for this probe.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test353.nds`.
- Mankey still only hops two tiles.
- In addition, Mankey gains no vertical height.

Learning:

- Logical-only midpoint commit does not preserve four-tile travel and also breaks the visible airborne presentation.
- The logical tile fields and render vectors are not separable enough to repair the stock `Jump*2` chain this way.
- Next probe should stop changing midpoint commit fields and instead test the untried shipped partner/follower wrapper around a moving `Jump*2` from the stable tree-anchor baseline.

### Attempt 187: Partner-Wrapped Moving Jump2 Probe

Idea:

Attempts 184-186 show plain chained `Jump*2` can cover four tiles only with a full midpoint commit, but that commit breaks visibility, while lighter midpoint commits break travel and/or vertical lift. The attempt log's directional-hop exploration notes identified an untried semantic path: combine the stable tree-anchor baseline with the shipped partner/follower wrapper that made same-tile hop presentation work earlier. Test one wrapped moving `Jump*2` segment first before chaining.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_CHAINED_JUMP2_LOGICAL_MIDPOINT_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE`.
- Keep the stable tree-anchor setup from Attempts 181-186.
- Pick a straight two-tile canopy target with `OverworldWildSpawns_TryPickStraightCanopyStepTarget`.
- Stage that two-tile target as the pending canopy target.
- Start a partner-style wrapped movement sequence on the real object: `0x49 -> direction-specific Jump*2 -> Freeze -> 0x4A -> MovementEnd`.
- Use the existing canopy movement task storage for this single wrapped sequence, not helper objects, object recreate/refresh, phantom cleanup, raw `posVec` interpolation, midpoint tile normalization experiments, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 52 used the partner wrapper with `Jump*Site` for a same-tile emote, not moving `Jump*2`.
- Attempts 183-186 used moving `Jump*2` from the stable tree-anchor baseline, but never with the partner/follower `0x49`/`0x4A` wrapper.
- Earlier canopy movement-list attempts did not use this partner-wrapped single moving jump from the stable tree-anchor baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE`
- `OverworldWildSpawns_StartWrappedCanopyJump2Probe`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test354.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE` is enabled while the chained midpoint probes are disabled.
- Verified `OverworldWildSpawns_StartWrappedCanopyJump2Probe` builds the `0x49 -> Jump*2 -> Freeze -> 0x4A -> MovementEnd` sequence.
- Verified the wrapped probe stages a two-tile pending target and uses the existing canopy movement-task finish path.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test354.nds`.
- Vertical height is back.
- Mankey stays visible.
- Mankey only hops two tiles.

Learning:

- The partner/follower wrapper restores the visible airborne presentation for a moving `Jump*2` from the stable tree-anchor baseline.
- A single wrapped `Jump*2` is still a two-tile carrier, as expected.
- The next non-repeating probe is to chain two wrapped `Jump*2` segments inside one engine-owned movement list, avoiding any manual midpoint tile/vector commit.

### Attempt 188: Partner-Wrapped Chained Jump2 Four-Tile Probe

Idea:

Attempt 187 proved the partner/follower wrapper restores vertical height and visibility for a moving two-tile `Jump*2`. Earlier four-tile attempts failed at the manual midpoint handoff. Test whether two full wrapped `Jump*2` segments inside one engine-owned movement list can travel four tiles while preserving the wrapper's visual contract, with no manual midpoint normalization.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE`.
- Keep the stable tree-anchor setup.
- Pick a straight four-tile canopy target with `OverworldWildSpawns_TryPickStraightCanopyStepTarget`, including intermediate two-tile landing validation.
- Stage that four-tile target as the pending canopy target.
- Parameterize `OverworldWildSpawns_StartWrappedCanopyJump2Probe` with a segment count.
- Emit two full wrapped movement segments in one movement list: `0x49 -> Jump*2 -> Freeze -> 0x4A -> 0x49 -> Jump*2 -> Freeze -> 0x4A -> MovementEnd`.
- Do not use helper objects, object recreate/refresh, phantom cleanup, raw `posVec` interpolation, manual midpoint tile/vector normalization, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 184 chained plain `Jump*2` segments but needed a manual midpoint commit and lost visibility.
- Attempts 185-186 changed the midpoint commit, but lost full travel and/or vertical height.
- Attempt 187 used the partner wrapper but only for one two-tile segment.
- No previous attempt has chained two partner-wrapped moving `Jump*2` segments inside one engine-owned movement list from the stable tree-anchor baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE`
- `OverworldWildSpawns_StartWrappedCanopyJump2Probe`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint: `test355.nds`.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE` is enabled while the single wrapped probe is disabled.
- Verified `OverworldWildSpawns_StartWrappedCanopyJump2Probe` accepts a segment count and emits two full wrapped `Jump*2` sequences when the chained probe is active.
- Verified the chained wrapped probe stages a four-tile pending target and uses the existing canopy movement-task finish path.
- Overlay compiled; build emitted expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test355.nds`.
- Mankey jumps two tiles twice in sequence.
- It does not feel like a single full four-tile jump.

Learning:

- Two complete partner-wrapped movement segments preserve travel and visual presentation, but they also make the hop read as two distinct jumps.
- The break is now caused by the repeated wrapper/freeze/restore sequence, not by manual midpoint tile/vector normalization.
- Next probe should keep one partner wrapper open around both `Jump*2` commands to test whether removing the mid-sequence restore/prep/freeze makes the action feel continuous.

### Attempt 189: Single Partner Wrapper Around Two Jump2 Commands

Idea:

Attempt 188 proved two complete wrapped `Jump*2` segments travel four tiles while preserving height and visibility, but the result visibly reads as two separate two-tile jumps. Test whether the visual break comes from closing and reopening the wrapper between segments by using one partner wrapper around both `Jump*2` commands: `0x49 -> Jump*2 -> Jump*2 -> Freeze -> 0x4A -> MovementEnd`.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE`.
- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE`.
- Keep the stable tree-anchor setup and straight four-tile canopy target.
- Reuse `OverworldWildSpawns_StartWrappedCanopyJump2Probe`, but when the single-wrapper probe is active, emit `0x49` once, then two direction-specific `Jump*2` commands, then one `Freeze`, one `0x4A`, and `MovementEnd`.
- Do not use helper objects, object recreate/refresh, phantom cleanup, raw `posVec` interpolation, manual midpoint tile/vector normalization, or direct `MapObject_StartJumpMovementInternal`.

Why this is new:

- Attempt 188 used two complete partner wrappers, one around each `Jump*2`.
- Attempts 184-186 used plain `Jump*2` chaining and midpoint commit variants.
- No previous attempt has kept a single partner wrapper open across two moving `Jump*2` commands from the stable tree-anchor baseline.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE`
- `OverworldWildSpawns_StartWrappedCanopyJump2Probe`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test356.nds` into the Delta ROM folder.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE` is active while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_WRAPPED_CHAINED_JUMP2_PROBE` is disabled.
- Verified the helper emits one partner prep command, two direction-specific `Jump*2` commands, one `Freeze`, one partner restore command, then `MovementEnd`.
- Overlay compiled with the expected unused legacy-helper warnings.

Runtime result:

- User tested `test356.nds`.
- Mankey still performs two separate two-tile jumps.
- The single wrapper only made the sequence faster; it did not produce one continuous four-tile arc.

Learning:

- The visible split is structural to issuing two stock `Jump*2` commands.
- Keeping `0x49` open across both commands does not merge them into one jump state.
- Do not keep rearranging repeated `Jump*2` list entries to chase a single four-tile arc.
- The next probe should use one `MapObject_StartJumpMovementInternal` call scaled to four tiles, but combine it with the later-proven partner prep/restore commands that restored height and visibility in Attempts 187-189.

### Attempt 190: Partner-Prepped Single Internal Four-Tile Jump

Idea:

Attempt 189 confirmed two stock `Jump*2` commands always read as two arcs, even inside one partner wrapper. Try one actual engine jump state instead: run the same partner prep that made wrapped jumps visible, start one direct internal jump with the stock `Jump*2` parameters scaled to a four-tile duration, then run the partner restore on landing.

Implementation shape:

- Add and enable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE`.
- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE`.
- Keep the stable tree-anchor setup and straight four-tile target from Attempts 188-189.
- Before the jump, run `0x49` as an immediate real-object movement command so the object receives the same presentation prep used by follower-style hops.
- Do not emit any stock `Jump*2` commands.
- Start one direct internal jump on the real object via `MapObject_StartMovementCommandInternal` plus `MapObject_StartJumpMovementInternal`.
- Use the stock jump scale from disassembly, stretched to four tiles: `deltaFx32 = 0x2000`, `frameCount = 32`, `jumpType = 3`, `arcTableId = 0`, `arcStep = 0x80`.
- When the internal jump finishes, run `Freeze -> 0x4A` as immediate real-object movement commands before normal canopy finish.
- Do not use helper objects, object recreate/refresh, phantom cleanup, raw `posVec` interpolation, movement-list tasks, manual midpoint normalization, or repeated `Jump*2` commands.

Why this is new:

- Attempts 179-180 used direct internal long jumps before the partner prep/restore visibility contract was discovered.
- Attempts 187-189 used partner prep/restore with stock `Jump*2`, but never with one direct internal four-tile jump state.
- No previous attempt has combined the successful tree-anchor baseline, partner prep/restore, and one scaled direct internal jump call.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE`
- `OverworldWildSpawns_RunImmediateCanopyMovementCommand`
- `OverworldWildSpawns_StartPartnerPreppedCanopyInternalJumpProbe`
- `MapObject_StartJumpMovementInternal`

Verification:

- `git diff --check` passed before build.
- First build failed because `OverworldWildSpawns_TryPickStraightCanopyStepTarget` was still guarded only by the older stock-jump probes; this confirmed the new probe was not yet enabling the shared straight-target helper.
- Added `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE` to the straight-target helper guard and the forced headbutt-perch suppression guard.
- Rebuilt successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test357.nds` into the Delta ROM folder.
- Verified `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE` is active while `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_SINGLE_WRAPPER_CHAINED_JUMP2_PROBE` is disabled.
- Overlay compiled with the expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test357.nds` and reported: "it works!!!!!!"
- The partner-prepped single internal jump gives the desired full long-hop feel instead of two chained two-tile arcs.

Learning:

- The working carrier is one direct internal jump state, not repeated stock `Jump*2` commands.
- The tested four-tile values are `frameCount = distance * 8` and `arcStep = 0x1000 / frameCount`, which gives `32` frames and `0x80` arc step at four tiles.
- The partner prep/restore commands are required for stable presentation; the old unwrapped direct internal path should not be used for canopy long jumps.
- Production work should remove the probe gate and expose this as a distance-scaled helper for any cardinal jump within the frame budget.

### Attempt 191: Production Canopy Long-Jump Carrier

Idea:

Convert the successful Attempt 190 probe into a reusable movement carrier. The new helper should work for any cardinal tile distance that fits the internal jump frame budget, while the behavior/targeting layer remains free to choose normal ranges such as 5-7 tiles.

Implementation shape:

- Disable `OW_WILD_SPAWNER_CANOPY_TREE_ANCHOR_PARTNER_PREPPED_INTERNAL_JUMP_PROBE`.
- Keep the successful partner-prepped internal-jump behavior active through production helpers, not through the probe block.
- Add `OverworldWildSpawns_GetCanopyLongJumpTiming` to derive frame count and arc step from distance.
- Keep the tested timing formula: `frameCount = distance * 8`, `arcStep = 0x1000 / frameCount`.
- Add `sOverworldWildCanopyLongJumpPrepActive[slot]` so finish/reset paths know whether the object has active partner-prepped presentation state.
- Rename the working starter to `OverworldWildSpawns_StartPreparedCanopyLongJumpCommand`.
- Make `OverworldWildSpawns_StartCanopyLongJumpCommand` derive direction and distance from a target tile, validate same-axis/cardinal movement, and delegate to the prepared helper.
- Let `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` attempt the prepared long-jump carrier for all cardinal pending canopy hops before falling back to legacy cleanup behavior.
- Restore `Freeze -> 0x4A` only when the per-slot prep flag is active.
- Clear the prep flag on normal finish and on movement reset; if a reset interrupts a still-active jump, clear the active movement first, then run restore if possible.

Why this is new:

- Attempt 190 proved the carrier but was hard-wired to the four-tile probe path.
- Earlier production helpers either lacked partner prep/restore or still used stock jump command sequences.
- This keeps the working primitive but removes the test-only distance assumption.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES`
- `sOverworldWildCanopyLongJumpPrepActive`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartPreparedCanopyLongJumpCommand`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_ResetSlotMovementCommand`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test358.nds` into the Delta ROM folder.
- Overlay compiled with the expected unused legacy-helper warnings from disconnected canopy paths.

Runtime result:

- User tested `test358.nds` and reported that the behavior has "a lot of bugs" and that Mankey sometimes disappears and never reappears.

Learning:

- Generalizing the Attempt 190 carrier to any raw frame-budget distance was too broad.
- The production carrier should be constrained by the behavior's active tile range, not only by the internal jump frame budget.
- Short cleanup/return hops should not enter the partner-prepped long-jump path until they have their own proven presentation contract.

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

### Attempt 226: One Row Above Archive Mankey Tree-Top Target

Idea:

The user reported on `test421.nds` that Mankey is one tile too low on the canopy. Current code has a mismatch: `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW` still exists, but `OverworldWildSpawns_TryGetHeadbuttTreeTops` ignores it and uses `structuralTopY = minY`. Move the current strict `HEADBUTT_TREE_TOPS` target definition up one row by using `minY - 1`.

Why this is new:

- Attempt 249 used `minY - 2`, which later made some direct downward targets invisible.
- Attempt 254 restored raw `minY`, which made the movement target reachable but now lands one tile too low.
- Early `treeY - 1` attempts were from the old per-coordinate/forced-spawn model. This attempt changes the current strict-only archive resolver after the later down-first targeting, settled-tile latch, long-hop carrier, and no broad fallback fixes.
- This does not change rendering, field effects, proxy objects, movement carrier timing, or `OW_WILD_TILE_HEADBUTT` behavior.

Implementation shape:

- Change `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW` from `2` to `1`.
- In `OverworldWildSpawns_TryGetHeadbuttTreeTops`, set `structuralTopY = minY - OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`.
- Reject negative resolved rows before adding the top-row target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_HEADBUTT_TREE_TOP_ROW_ABOVE_ARCHIVE_ROW`
- `OverworldWildSpawns_TryGetHeadbuttTreeTops`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test422.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User reported this made the game think the row above the real canopy was a tree-top tile.
- Screenshot showed Mankey standing one tile too high, with the marker bubble attached there.

Learning:

- `minY - 1` is not a valid `HEADBUTT_TREE_TOPS` definition in the current strict resolver.
- The `test421.nds` "Mankey is one tile too low" symptom should not be solved by changing logical tree-top targets.
- Restore raw archive `minY` for logical target/settled recognition and continue rendering work separately.

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

### Attempt 153: Mankey Canopy Hopper Headbutt-Tree Profile

Idea:

Create a complete behavior profile for Mankey where headbutt-tree spawns jump from one headbutt tree to another, rather than using ordinary wander/chase movement.

Implementation shape:

- Add a new `canopy_hopper` behavior class.
- Match `SPECIES_MANKEY` only when it spawns from `OW_WILD_SPAWN_TERRAIN_HEADBUTT`.
- Give the profile:
  - chill state: headbutt tree hop
  - alert state: angry hop
  - alertness: standard 3-facing-player range plus the existing close-radius fallback
  - attentive state: headbutt tree hop
  - stamina/rest: 8 hops, water-droplet tired state, 4 rest units
  - speed/range: normal speed 2, max speed 3, range 16
  - jump level: both, so variable overrides can still disable ledge jumping later if needed
- Add archive-backed current-map headbutt tree target selection.
- Only hop to real headbutt-tree coordinates from `ARC_HEADBUTT_TREES`.
- Reject the current tree, occupied trees, trees with no valid adjacent landing tile, trees outside profile range, and trees beyond despawn distance.
- For testing, force headbutt-terrain behavior-test encounters to Mankey while leaving land behavior-test encounters as Gengar.

Why this is new:

- Previous movement attempts used normal walk commands, ledge jumps, ram movement, playful orbiting, and phantom teleporting.
- No previous attempt has reused the headbutt tree archive as a behavior target graph.
- This avoids another fragile custom animated movement-command experiment by first proving the tree-to-tree behavior layer with direct tile placement and hop feedback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_BEHAVIOR_CLASS_CANOPY_HOPPER`
- `OW_WILD_BEHAVIOR_CHILL_STATE_HEADBUTT_TREE_HOP`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_HEADBUTT_TREE_HOP`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`
- `OverworldWildSpawns_ApplyBehaviorTestSpecies`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test253.nds`.

Runtime result:

- Pending user test on `test253.nds`.

Learning:

- Build-side result is stable. Runtime should verify that headbutt Mankey spawns hop between nearby real headbutt trees and that the direct tree hop does not trigger route-transition or battle-start instability.

### Attempt 154: Canopy Hopper Attentive Ambush Target

Idea:

Refine Mankey's `canopy_hopper` attentive state so it uses trees to approach the player, then jumps from a tree down onto the tile in front of the player when close enough.

Implementation shape:

- Keep chill-state canopy movement as random real-headbutt-tree hopping.
- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE`, currently 6 tiles.
- Split headbutt-tree target validation from target selection so both random and directed modes reuse the same safety checks.
- In attentive state:
  - read the player's current facing and compute the tile directly in front of the player
  - require that tile to be a valid non-headbutt, non-surf, unblocked, unoccupied landing tile
  - if Mankey is currently on a headbutt tree and that front tile is within ambush range, jump directly to that tile
  - otherwise choose a valid headbutt tree within profile range that reduces distance to the player-front tile
- When the direct ambush jump succeeds, force the profile's normal tired transition so Mankey pauses in front of the player instead of immediately jumping away.

Why this is new:

- Attempt 153 proved the new class/profile shape and archive-backed random tree hopping.
- No previous attempt made canopy hopping a directed two-phase behavior: tree chase toward a player-relative target, then ground ambush.
- This still avoids custom animated movement descriptors and keeps using the stable direct placement path from Attempt 153.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE`
- `OverworldWildSpawns_TryUseCloserHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTargetToward`
- `OverworldWildSpawns_TryGetCanopyHopperPlayerFrontTarget`
- `OverworldWildSpawns_TryPickCanopyHopperAttentiveTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test254.nds`.

Runtime result:

- Pending user test on `test254.nds`.

Learning:

- Build-side result is stable. Runtime should verify that attentive Mankey first tree-hops closer when the player-front tile is out of range, then jumps down to that tile and pauses tired when it can make the ambush jump.

### Attempt 155: Canopy Hopper Tired Return-To-Tree Case

Idea:

Make Mankey explicitly return to a headbutt tree after its attentive ambush makes it tired on the ground. It should not rely on random chill hopping to maybe choose a tree; it should have a dedicated recovery path back into the canopy.

Implementation shape:

- Keep the tired timer and tired bubble state generic.
- After tired finishes, Mankey already returns to chill state through the normal tired cooldown path.
- In chill-state canopy movement, detect whether the canopy hopper is currently standing on a headbutt tree.
- If it is not on a headbutt tree, choose the nearest valid real headbutt tree from the current map's `ARC_HEADBUTT_TREES` data.
- Reuse the same tree validity checks as the other canopy hopper modes:
  - real headbutt tree coordinate
  - not current tile
  - within profile range
  - within despawn distance
  - not occupied
  - has a valid nearby landing tile
- Only after Mankey is back on a tree does chill movement fall back to random tree-to-tree hopping.

Why this is new:

- Attempt 153 added random tree-to-tree hopping.
- Attempt 154 added attentive tree chase plus direct ambush onto the player-front ground tile and a tired pause there.
- No previous attempt added a ground-to-tree recovery case for canopy hoppers after tired state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseReturnHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test255.nds`.

Runtime result:

- Pending user test on `test255.nds`.

Learning:

- Build-side result is stable. Runtime should verify that Mankey returns from the ground ambush/tired pause to the nearest valid real headbutt tree before resuming random canopy movement.

### Attempt 156: Force Land Test Spawns To Mankey

Idea:

Make land behavior-test spawns use Mankey instead of Gengar so Mankey can be tested from normal land spawns too.

Implementation shape:

- Keep `OW_WILD_SPAWNER_FORCE_BEHAVIOR_TEST_SPECIES` enabled.
- Keep headbutt-terrain test encounters forced to `SPECIES_MANKEY`.
- Change land-terrain test encounters from `SPECIES_GENGAR` to `SPECIES_MANKEY`.
- Leave saved shiny respawns untouched.

Why this is new:

- Attempts 153-155 focused on Mankey's headbutt-tree behavior.
- The test harness still forced land spawns to Gengar from the earlier Phantom Stalk work.
- No previous attempt changed land behavior-test spawns to Mankey.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyBehaviorTestSpecies`

Verification:

- `git diff --check` passed before the build.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test256.nds`.

Runtime result:

- Pending user test on `test256.nds`.

Learning:

- Build-side result is stable. Runtime should verify that normal land spawns are now Mankey instead of Gengar for behavior testing.

### Attempt 157: Universal Canopy Hopper Return-To-Tree Priority

Idea:

Make Mankey's return-to-tree logic universal for the canopy hopper behavior. If Mankey is off a headbutt tree for any reason, its next canopy movement decision should return it to a tree before any chill, attentive, chase, or ambush behavior.

Implementation shape:

- Change the Mankey behavior-class rule from headbutt terrain only to any terrain.
- Remove the headbutt-terrain guard from `OverworldWildSpawns_TryStartHeadbuttTreeHop`; the behavior profile now decides whether this movement applies.
- At the start of canopy hopper target selection, before attentive ambush or random roaming, check whether the object is currently on a headbutt tree.
- If it is not on a tree, use `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget` immediately.
- Only when Mankey is already on a tree can it continue into active ambush targeting or chill random tree hopping.

Why this is new:

- Attempt 155 returned Mankey to a tree only from chill-state canopy movement.
- Attempt 156 made land test spawns become Mankey, which exposed that Mankey should not depend on headbutt terrain to get canopy behavior.
- No previous attempt made off-tree recovery the first priority across Mankey's canopy movement states and terrains.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `sOverworldWildBehaviorClassRules`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`
- `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget`

Verification:

- Built as `test257.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the Mankey behavior-class rule now uses `OW_WILD_BEHAVIOR_MATCH_ANY_TERRAIN`.
- Verified `OverworldWildSpawns_TryStartHeadbuttTreeHop` no longer rejects non-headbutt-terrain spawns.
- Verified off-tree recovery via `OverworldWildSpawns_TryPickHeadbuttTreeReturnTarget` is selected before active ambush targeting or chill random tree hopping.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify that any canopy-hopper Mankey which ends up off a tree returns to a valid real headbutt tree before continuing chill, attentive, chase, ambush, or random tree-hop behavior.

### Attempt 158: Canopy Hopper Pre-Hop Wait

Idea:

Mankey became visible only on the spawn frame, likely because universal return-to-tree immediately direct-placed land-spawned Mankey onto a headbutt tree tile on the first movement decision. Add a visible half-second staging delay before every canopy hop so Mankey stays on its current tile, faces the target, and only executes the direct tile hop after the pause.

Implementation shape:

- Add per-slot pending canopy-hop target state.
- When `OverworldWildSpawns_TryStartHeadbuttTreeHop` chooses a target, store the target, direction, distance, and tired-transition flag instead of immediately calling `OverworldWildSpawns_SetObjectTile`.
- Set `OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES` to `30` frames.
- On the next canopy decision after the cooldown expires, execute the pending hop through the existing direct-placement and `OverworldWildSpawns_HandleFinishedMovementCommand` path.
- Clear pending canopy-hop state on slot reset and fresh spawn initialization.

Why this is new:

- Attempt 157 made off-tree recovery universal but still moved Mankey immediately in the same tick.
- Earlier hop-visibility attempts focused on spot-emote movement commands, `WaitJumpSite`, and partner-Pokemon jump wrappers, not on delaying canopy direct placement.
- No previous attempt added a pre-hop staging delay to the canopy hopper target path.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_ExecutePendingCanopyHop`
- `OverworldWildSpawns_TryStartHeadbuttTreeHop`

Verification:

- Built as `test258.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the canopy hopper path now stages a pending target before direct placement.
- Verified the staged path sets `OW_WILD_SPAWNER_CANOPY_HOPPER_PRE_HOP_WAIT_FRAMES` / `30` frames before the hop executes.
- Verified pending canopy-hop state is cleared on slot reset and fresh spawn initialization.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify whether land-spawned Mankey remains visible for about half a second before returning to a tree, and whether tree-to-tree or ambush hops now have a readable pre-hop pause.

### Attempt 159: Canopy Hopper Visible Jump Chain

Idea:

Replace canopy hopper direct tile placement with actual stock jump movement commands. Keep the half-second pre-hop wait from Attempt 158, but when the wait expires, move Mankey toward the stored target using visible `Jump*` / `Jump*2` commands instead of blinking to the target tile.

Implementation shape:

- Add canopy hopper jump command constants for one-tile `Jump*` (`0x34` family) and two-tile `Jump*2` (`0x38` family).
- When a staged canopy target is ready, start the next visible jump segment toward the stored target.
- Use a two-tile jump when at least two tiles remain on the chosen axis, otherwise use a one-tile jump.
- On each segment completion, keep the canopy target pending and wait another half second before the next hop if Mankey has not reached the target yet.
- Only run the canopy finished/stamina/tired/cooldown logic once, after the final jump segment reaches the stored target.

Why this is new:

- Attempt 50 proved `Jump*2` visibly lifts and moves spawned Pokemon, but rejected it for same-tile spot emotes because movement was unwanted there.
- Attempt 158 added a pre-hop wait but still used direct `OverworldWildSpawns_SetObjectTile` placement after the wait.
- No previous canopy attempt has chained stock visible jump movement commands toward the tree/ambush target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_1_COMMAND`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_JUMP_2_COMMAND`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_ExecutePendingCanopyHop`

Verification:

- Built as `test260.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the final build no longer has the new signedness warnings from the first `test259.nds` build; only older diagnostic unused warnings remain.
- Verified canopy hop segment completion is intercepted before generic movement completion so multi-segment hops do not spend stamina or trigger tired logic per segment.
- Verified the final canopy finished/stamina/tired/cooldown logic runs only after the stored target is reached.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify that Mankey now visibly hops in one- or two-tile stock jump segments toward tree/ambush targets instead of blinking directly to the final tile, and that long jumps still preserve the half-second wait before each segment.

### Attempt 160: Seven-Tile Canopy Hop Target And No Bounce-Back

Idea:

Make Mankey's canopy hop read as a larger movement choice for feel testing. Allow a single canopy target selection up to 7 tiles away, but keep the known-safe stock visible jump commands for the actual motion. Also prevent the next tree-hop target from immediately being the previous full-hop origin, so Mankey does not bounce back and forth between two trees.

Implementation shape:

- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES` with a test value of `7`.
- Store the full-hop origin when a canopy target is staged.
- After the final jump segment reaches the staged target, mark the staged origin as the next avoided tree target.
- Random and directed tree-hop pickers first reject the avoided origin, then fall back to allowing it only if no other valid candidate exists.
- Return-to-tree recovery ignores the avoided origin so off-tree Mankey cannot get stuck when the previous tree is the only valid recovery target.
- Keep the initial half-second pre-hop read, but continue internal 1- or 2-tile stock jump segments immediately so one staged decision can feel like a longer hop sequence.

Why this is new:

- Attempt 159 chained visible stock jump commands, but still used the older target range and intentionally waited between every segment.
- Earlier no-backtracking work was for Playful Aipom one-tile chase/orbit movement, not canopy hopper tree target selection.
- No previous canopy attempt has stored the previous full-hop origin and used it as an avoided next tree target with a safety fallback.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES`
- `movementCanopyHopOriginX/Y`
- `movementCanopyHopAvoidX/Y`
- `OverworldWildSpawns_IsValidHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_FinishPendingCanopyHop`

Verification:

- Built as `test261.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the touched overlay compiles with only older diagnostic unused warnings still present.
- Verified random and directed canopy tree-hop target selection now reject the previous full-hop origin on the first pass, then fall back if no other valid tree exists.
- Verified return-to-tree recovery ignores the avoided origin so off-tree Mankey still has a recovery path.

Runtime result:

- User reported Mankey still only jumps 1 tile and should want to jump far.

Learning:

- Raising the maximum hop distance alone is not enough; the picker still treats near and far valid trees equally, so nearby trees can dominate the visible behavior.
- The next attempt should change target scoring so canopy hoppers actively prefer far tree targets.

### Attempt 161: Canopy Hopper Far-Preferred Tree Selection

Idea:

Make Mankey actively want far canopy hops. Keep the 7-tile maximum from Attempt 160, but change target selection so chill/random canopy movement chooses among the farthest valid tree candidates, and directed canopy movement chooses among the farthest valid candidates that still make progress toward the desired target.

Implementation shape:

- Add a best-distance accumulator to random headbutt-tree target selection.
- When a farther valid random tree is found, reset the reservoir and pick among only that farthest-distance group.
- Add a best-distance accumulator to directed headbutt-tree target selection.
- Keep directed candidates progress-gated, but prefer larger hop distance before using desired-target distance as a tie-break.
- Preserve the Attempt 160 avoid-origin first pass and fallback pass.
- Leave return-to-tree recovery shortest-path based, since that path is about getting Mankey unstuck rather than style.

Why this is new:

- Attempt 160 only raised the maximum target distance and added previous-origin avoidance.
- No previous canopy attempt has scored tree targets by farthest hop distance.
- Playful no-backtracking and chase scoring attempts do not apply here because canopy movement uses archive-backed headbutt tree candidates, not one-tile movement directions.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseRandomHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryUseCloserHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTarget`
- `OverworldWildSpawns_TryPickHeadbuttTreeHopTargetToward`

Verification:

- Built as `test262.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the touched overlay compiles with only older diagnostic unused warnings still present.
- Verified chill/random tree-hop selection now tracks the largest candidate distance and resets the reservoir when a farther valid tree is found.
- Verified directed tree-hop selection still rejects candidates that do not improve desired-target distance, but now prefers larger hop distance before desired-distance tie-breaks.

Runtime result:

- User reported Mankey still never hops more than one tile.

Learning:

- Far-preferred target selection works on paper, but the visible motion still uses stock jump command behavior from Attempt 159.
- The stock `Jump*2` command family is not a multi-tile travel command for spawned Pokemon in this context; it visibly advances only one tile.
- The next attempt needs to stop relying on stock jump commands for the travel distance.

### Attempt 162: Custom Rendered Far Canopy Hop

Idea:

Make canopy hopping visually travel more than one tile by moving the logical object to the far target, then rendering it offset back at the origin and interpolating its rendered X/Z position to the target over a short hop timer. This uses `posVec[0]` and `posVec[2]`, which are already proven visible by the ram crash object-wobble effect, instead of relying on stock `Jump*2` movement commands.

Implementation shape:

- Add per-slot canopy render-hop start/target X/Z, base Y, and timer state.
- When a pending canopy target starts, record the origin and target fixed-point positions.
- Set the object's logical tile to the far target immediately for behavior continuity.
- Override `posVec[0]`/`posVec[2]` back to the origin so the sprite starts visually where it stood.
- Each frame, interpolate the visible `posVec[0]`/`posVec[2]` toward the target for `24` frames.
- Apply a small Y arc during the timer as a best-effort hop lift, while keeping the important long-distance travel on the known-visible X/Z axes.
- Finish the pending canopy hop only after the custom render-hop timer reaches the far target.

Why this is new:

- Attempt 158 delayed direct placement but still blinked to the target.
- Attempt 159 chained stock visible jump commands and was limited to one visible tile per command.
- Attempt 160 allowed 7-tile targets but still used stock jump commands.
- Attempt 161 preferred far targets but still used stock jump commands.
- Earlier manual `posVec[1]` hopping failed, but this attempt is different because it uses `posVec[0]`/`posVec[2]`, which later ram crash work proved can visibly move spawned objects.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `movementCanopyRenderHopStartX/Z`
- `movementCanopyRenderHopTargetX/Z`
- `movementCanopyRenderHopTimers`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test263.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the touched overlay compiles with only older diagnostic unused warnings still present.
- Verified canopy travel no longer starts a stock `Jump*` / `Jump*2` movement command.
- Verified the frame task now ticks `OverworldWildSpawns_TickCanopyRenderHopMovementCommand` before generic stock movement updates.
- Verified reset paths restore a partially rendered canopy hop back to its logical target position before clearing movement state.

Runtime result:

- User reported Mankey still instantly teleports.

Learning:

- Moving the real object's logical tile to the destination and then overriding its `posVec[0]`/`posVec[2]` back to the origin does not produce a visible travel arc.
- The renderer or map-object update path appears to snap the real object to its logical destination strongly enough that large render offsets are not visible, even though small same-tile wobble offsets work.
- The next attempt should avoid showing the real object during travel and instead use a separate temporary visual object.

### Attempt 163: Canopy Helper Object Far-Hop Visual

Idea:

Hide the real Mankey at the far landing tile and use a temporary helper object as the visible travelling sprite. The helper starts at the origin, interpolates across the full route, then gets deleted when the real Mankey is revealed at the target. This should prevent the instant logical-target snap from being visible.

Implementation shape:

- Add a dedicated temporary object id range for canopy hop helper objects.
- Add per-slot `movementCanopyRenderHopObjects`.
- Exclude canopy helper ids from occupancy checks, the same way phantom helper ids are ignored.
- When a far canopy hop starts:
  - move the real object logically to the target;
  - set `BIT_VANISH` on the real object;
  - create a helper object at the origin with the same species/form/shiny render params;
  - animate the helper's `posVec[0]`/`posVec[2]` over the stored render-hop timer.
- On completion or reset:
  - delete the helper;
  - restore/reveal the real object at the target.

Why this is new:

- Attempt 162 manipulated the real object's render position after changing its logical tile.
- Phantom movement has used temporary helper objects, but no canopy attempt has used a helper object as the visible travelling sprite.
- This still avoids retrying stock `Jump*2` as a multi-tile travel command.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_CANOPY_RENDER_HOP_OBJECT_ID_START`
- `movementCanopyRenderHopObjects`
- `OverworldWildSpawns_ClearCanopyRenderHopObject`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test265.nds` and copied to Delta.
- `git diff --check` passed before the final build.
- Verified the helper-object path compiles after removing an accidental unused local from the unrelated phantom teleport function.
- Verified active code hides the real canopy hopper at the far target, creates a temporary visual helper at the origin, excludes helper ids from occupancy checks, interpolates the helper's `posVec[0]`/`posVec[2]`, then deletes the helper and reveals the real object at completion/reset.

Runtime result:

- User reported there is still no hopping.

Learning:

- A temporary helper object with manually interpolated `posVec[0]`/`posVec[2]` still does not produce a readable hop.
- This makes the failure less likely to be only "the real object's logical tile snaps its render position"; helper objects also appear to have their large manual render offsets snapped/ignored.
- Do not keep retrying raw large `posVec` travel arcs for canopy hopping without new evidence.
- The next attempt should use stock movement-command rendering on the helper object, because stock `Jump*Site` is already proven to render visible same-tile hops on spawned Pokemon and stock moving jumps are proven to render airborne motion.

### Attempt 164: Helper Object Stock-Jump Segments

Idea:

Keep the Attempt 163 hidden-real/helper-object split, but stop manually interpolating the helper's render position. Instead, make the helper object run stock `Jump*2` / `Jump*` movement commands toward the far canopy target. The real Mankey remains hidden at the final target for gameplay state, while the helper performs visible jump segments and is deleted once it reaches the target.

Implementation shape:

- Reuse `movementCanopyRenderHopObjects` as the visible helper object.
- When the helper starts, move the real object logically to the final target and hide it.
- Start a stock helper jump segment toward the final target:
  - prefer `Jump*2` if the remaining distance in that direction is at least two tiles;
  - use `Jump*` for the final one-tile segment.
- Drive `MapObject_UpdateMovementCommand` on the helper object from the frame task.
- When a segment finishes, either start the next helper jump immediately or reveal the real object/delete the helper if the target has been reached.

Why this is new:

- Attempt 159 chained stock jump commands on the real spawn object.
- Attempts 162 and 163 tried raw render-position interpolation.
- No previous attempt has combined the hidden-real/helper-object split with stock jump movement commands on the helper object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_StartNextCanopyHelperJumpSegment`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test267.nds` and copied to Delta.
- `git diff --check` passed before the final build.
- Verified the final build no longer emits the new signedness warning from `OverworldWildSpawns_IsAtCanopyRenderHopTarget`; remaining overlay warnings are older unused diagnostic symbols/functions.
- Verified `OverworldWildSpawns_TickCanopyRenderHopMovementCommand` now updates the helper object with `OverworldWildSpawns_UpdateSpawnerMovementCommand` instead of manual `posVec` interpolation.
- Verified segment selection prefers stock `Jump*2` for two-tile chunks and `Jump*` for one-tile cleanup, then reveals the real object at the final target when the helper reaches it.

Runtime result:

- User reported this still does not work, Mankey is often invisible, and hop time should scale with distance.

Learning:

- The hidden-real/helper-object split is not stable enough for canopy hopping.
- Helper stock jumps did not solve visibility; they made Mankey unreliable/invisible in runtime.
- Do not keep pursuing helper-object canopy travel unless a new reason appears to believe helper visibility ownership can be made stable.
- Hop timing should be derived from travel distance, not a fixed manual timer.

### Attempt 165: Real Object Stock-Jump Chain Without Segment Wait

Idea:

Back out of helper-object canopy travel and keep the real Mankey visible for the whole hop. Use stock moving jump commands on the real object again, but remove the old half-second wait between every segment. Long canopy targets should now take proportionally longer because Mankey performs more stock jump segments, while avoiding the invisible helper handoff.

Implementation shape:

- Do not move the real object directly to the final target before visual travel.
- Do not create or hide behind `movementCanopyRenderHopObjects`.
- When a pending canopy target is ready:
  - choose the larger remaining axis toward the target;
  - start `Jump*2` when at least two tiles remain on that axis;
  - start `Jump*` for the final one-tile cleanup.
- Let `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand` finish the full hop only when the real object reaches the stored target.
- If the real object has not reached the target, immediately queue the next segment with normal decision cooldown `0`, so no artificial pause is inserted between segments.

Why this is new:

- Attempt 159 chained stock jumps on the real object but intentionally waited half a second before each segment.
- Attempts 163 and 164 used helper objects and produced no hop/invisibility issues.
- No previous attempt has used the real-object stock jump chain without the per-segment staging wait after the first jump.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- Built as `test268.nds` and copied to Delta.
- `git diff --check` passed before and after the code change.
- Verified the active path in `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` no longer creates a helper object, moves the real object directly to the final target, or hides the real object with `BIT_VANISH`.
- Verified the active path clears any stale canopy render helper, keeps the real object visible, and starts stock real-object `Jump*2` / `Jump*` movement commands based on remaining distance.
- Verified `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand` keeps the pending target alive and immediately queues another real-object stock jump segment with cooldown `0` until Mankey reaches the final target.

Runtime result:

- User reported Mankey only jumps one tile.

Learning:

- This confirms the Attempt 161 learning: the stock `Jump*2` command family is not a multi-tile travel command for spawned Pokemon in this context.
- The real-object stock-chain path is better for visibility than the helper-object path, but it cannot create a readable far hop.
- Do not keep pursuing stock `Jump*` / `Jump*2` commands as the distance carrier for canopy hopping without new evidence.

### Attempt 166: Real Object Deferred Logical Commit Render-Hop

Idea:

Make the real Mankey perform one full-distance rendered hop without helper objects and without stock moving jump commands. Keep the logical object tile at the origin while the hop is in flight, animate the real object's X/Z render position toward the far target over a duration derived from hop distance, then commit the logical tile to the far target only when the animation lands.

Implementation shape:

- When the staged canopy target is ready:
  - record the real object's current fixed-point X/Z as the render-hop start;
  - record the target fixed-point X/Z and base Y;
  - set `movementCanopyRenderHopTimers[slot]` to a distance-scaled duration;
  - mark the movement slot in progress without starting a stock movement command.
- In the frame task, while the render-hop timer is active:
  - keep the real object visible;
  - interpolate `object->posVec[0]` and `object->posVec[2]` from origin to target;
  - add a best-effort vertical arc through `object->posVec[1]`;
  - only call `OverworldWildSpawns_SetObjectTile` at the final frame.
- Finish the pending canopy hop through the existing `OverworldWildSpawns_FinishPendingCanopyHop` path after landing.

Why this is new:

- Attempt 162 moved the logical object to the far target first, then tried to offset the rendered position back to the origin; runtime snapped/teleported.
- Attempts 163 and 164 used helper objects and produced invisibility.
- Attempts 159, 161, and 165 used stock `Jump*` / `Jump*2` commands and only moved one tile.
- No previous attempt has kept the real object's logical tile at the origin for the full custom X/Z render-hop and committed the logical target only on landing.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- Built as `test269.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the overlay compiles; warnings shown during the build are the older unused diagnostic symbols/functions, not new canopy-hop compile failures.
- Verified the active canopy-hop starter no longer calls `MapObject_StartMovementCommand` / stock `Jump*` for distance travel.
- Verified the active canopy-hop starter records start X/Z, target X/Z, base Y, and a distance-scaled render-hop duration, then marks the slot in progress.
- Verified `OverworldWildSpawns_TickCanopyRenderHopMovementCommand` now interpolates the real object's `posVec[0]`/`posVec[2]` until the final frame, then commits the logical tile with `OverworldWildSpawns_SetObjectTile`.

Runtime result:

- User reported this failed: Mankey became invisible.

Learning:

- Moving the real object's X/Z render position far away from its logical tile makes Mankey disappear.
- This confirms that long-distance `posVec[0]`/`posVec[2]` travel is not safe for canopy hopping, even when the logical tile is committed only at landing.
- Do not keep pursuing real-object or helper-object raw X/Z render interpolation without new evidence.

### Attempt 167: Horizontal WaitJump Command Probe

Idea:

Test the less-used stock `WaitJumpLeft1/2` and `WaitJumpRight1/2` movement commands for canopy travel. These commands are distinct from the already-failed `JumpLeft2` / `JumpRight2` family and were not previously tried for Mankey. If `WaitJumpLeft2` / `WaitJumpRight2` are true two-tile waited jumps, they may provide a stable visible multi-tile horizontal hop without helper objects or manual render offsets.

Implementation shape:

- Revert the active canopy travel path away from manual X/Z render interpolation.
- Keep the real Mankey visible and use stock movement command ownership again.
- For horizontal canopy segments:
  - use `WaitJumpLeft2` / `WaitJumpRight2` when at least two horizontal tiles remain;
  - use `WaitJumpLeft1` / `WaitJumpRight1` for one horizontal tile.
- For vertical canopy segments, fall back to the previous stock `Jump*2` / `Jump*` family for now so the path remains functional even though vertical true far-hop remains unsolved.
- Continue chaining toward the staged far target with no artificial segment wait.

Why this is new:

- Attempts 159, 161, and 165 used `Jump*` / `Jump*2`, not the `WaitJumpLeft/Right` family.
- Attempts 162, 163, and 166 used raw render-position interpolation and produced teleport/no-hop/invisibility.
- Attempt 164 used helper objects with stock `Jump*` commands, not `WaitJumpLeft/Right`.
- No previous attempt has used `WaitJumpLeft1/2` or `WaitJumpRight1/2` as the active canopy travel command.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryGetCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Verified the active canopy starter no longer arms `movementCanopyRenderHopTimers[slot]` with a manual long-distance X/Z interpolation duration.
- Verified the active canopy starter clears stale render-hop state, keeps the real object visible with `MapObject_ClearBits(object, BIT_VANISH)`, and starts stock movement ownership through `OverworldWildSpawns_StartMovementCommandForSlot`.
- Verified horizontal segments use named `WaitJumpLeft1/2` and `WaitJumpRight1/2` constants (`0x5C`-`0x5F`), while vertical segments still fall back to the already-known `Jump*`/`Jump*2` family.
- Built as `test270.nds` and copied to Delta.

Runtime result:

- User reported Mankey still appears to only do one-tile jumps.

Learning:

- `WaitJumpLeft2` / `WaitJumpRight2` did not make the runtime feel like a readable multi-tile canopy hop.
- The next probe should remove one-tile target and command paths entirely so runtime testing can tell whether short targets or the stock movement command itself is the cause.

### Attempt 168: Strict Five-To-Seven Tile Canopy Hop Probe

Idea:

Disable short canopy hop choices for Mankey and only allow normal canopy tree-to-tree / attentive tree-chase targets whose Chebyshev distance is 5-7 tiles from the current tile. Also remove the explicit one-tile `WaitJumpLeft1` / `WaitJumpRight1` command path from active canopy travel, so a pending far target cannot deliberately issue a visible one-tile jump command as a segment.

Implementation shape:

- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES` with a value of `5`.
- Keep `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES` at `7`.
- Raise the attentive ambush range to `7`, and only allow direct player-front ambush jumps when the front tile is 5-7 tiles away.
- Pass the minimum distance into normal random tree-hop and attentive tree-chase candidate validation.
- Keep return-to-tree recovery exempt from the 5-tile minimum so off-tree Mankey can still get back onto a valid headbutt tree instead of getting stranded.
- Remove active use of the one-tile `WaitJumpLeft1` / `WaitJumpRight1` commands.
- If a previously staged odd-distance far target reaches a final one-tile remainder, silently land/finish the pending hop instead of starting another visible one-tile jump command.

Why this is new:

- Attempt 160 only raised the maximum target distance to 7 and still allowed short candidates.
- Attempt 161 preferred farther valid candidates, but still allowed short candidates if they were the best available or selected by context.
- Attempt 167 tested `WaitJumpLeft/Right1/2`, but still explicitly used one-tile wait-jump commands for one-tile remainders.
- No previous attempt has enforced a strict 5-tile minimum for normal canopy candidate selection while leaving return-to-tree recovery exempt.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`
- `OverworldWildSpawns_IsValidHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryGetCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Verified normal tree-hop and attentive tree-chase candidate validation now use a 5-tile minimum.
- Verified return-to-tree candidate validation still allows one-tile recovery movement.
- Verified direct player-front ambush requires `frontDistance >= OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`.
- Verified active canopy travel no longer references `OW_WILD_SPAWNER_CANOPY_HOPPER_WAIT_JUMP_LEFT_1_COMMAND` or `OW_WILD_SPAWNER_CANOPY_HOPPER_WAIT_JUMP_RIGHT_1_COMMAND`.
- Built as `test271.nds` and copied to Delta.

Runtime result:

- User reported Mankey sometimes becomes invisible.

Learning:

- Strict 5-7 tile candidate selection is not enough to make the current stock command carrier stable.
- Since helper-object travel and raw X/Z render offsets were already ruled out, the next probe should keep the real object as the gameplay object but refresh/recreate it after stock command completion so stale render state cannot persist between canopy segments.

### Attempt 169: Recreate Real Canopy Object After Each Segment

Idea:

Keep the Attempt 168 strict 5-7 tile target selection, but stabilize visibility by recreating the real spawned object at its current tile after each stock canopy movement segment finishes. This borrows the successful stabilization pattern from phantom stalking, where recreating the real object after hidden/teleport states restored visibility more reliably than clearing `BIT_VANISH` on the same object.

Implementation shape:

- Add `OverworldWildSpawns_RecreateSpawnObjectAtTile`, a generic real-spawn object refresh helper:
  - clears any active single-movement flag on the old object;
  - creates a new special field object at the requested tile;
  - reapplies object id, movement range, species/form/shiny render params, facing, tile position, and visible state;
  - updates `state->spawns[slot].object` to the replacement.
- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, recreate the real object at the segment landing tile before either finishing the pending canopy hop or scheduling the next segment.
- In the odd-distance final one-tile cleanup path, recreate the real object at the final target before finishing the pending hop.

Why this is new:

- Attempts 163 and 164 used a temporary helper object for canopy travel and produced invisibility; this attempt does not use a helper object as the visible traveller.
- Attempt 166 moved the real object's render position far from its logical tile and produced invisibility; this attempt does not manually interpolate X/Z render position.
- Attempt 167 and Attempt 168 kept the same real object through stock movement-command segments.
- Phantom attempts proved object recreation can restore stable visibility, but no canopy attempt has recreated the real Mankey after each completed stock movement segment.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test272.nds` and copied to Delta.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 170: Canopy Hopper Always-Visible Invariant

Idea:

Make `canopy_hopper` behavior explicitly never use hidden/flicker presentation state. Unless the object is being deleted/despawned, a canopy hopper should always clear `BIT_VANISH`, ignore stale phantom hidden flags, and clear stale helper/visual-hop state. Mankey should hop, not blink out.

Implementation shape:

- Add `OverworldWildSpawns_IsCanopyHopperProfile`.
- Add `OverworldWildSpawns_EnforceCanopyHopperVisibility`, which:
  - clears stale canopy render-hop helper objects without deleting the real Mankey if a stale pointer aliases it;
  - clears stale canopy render-hop timer/position state without clearing the pending canopy target;
  - clears stale phantom flicker helper objects and phantom teleport target state;
  - resets phantom hidden/flicker/visible-pause flags;
  - clears `BIT_VANISH` on the real canopy-hopper object;
  - normalizes the render position to the logical tile only when the object is not currently executing a movement command.
- Call the invariant from the normal movement tick, the frame-level movement task before phantom flicker handling, and after recreate-at-tile refresh.

Why this is new:

- Attempt 169 recreated the real object only after completed canopy movement segments.
- This attempt does not add another travel carrier or helper-object presentation path.
- This attempt adds an always-visible rule for the canopy profile itself, so stale phantom/helper state cannot keep hiding Mankey between movement decisions.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsCanopyHopperProfile`
- `OverworldWildSpawns_EnforceCanopyHopperVisibility`
- `OverworldWildSpawns_TickMovementParams`
- `OverworldWildSpawns_FrameMovementTask`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`

Verification:

- `git diff --check` passed before the build.
- Built as `test273.nds` and copied to Delta.

Runtime result:

- User reported Mankey is now much more often invisible.

Learning:

- The per-frame always-visible invariant is unsafe for canopy hoppers.
- Clearing helper/render/phantom state every update can interfere with stock movement-command ownership or render state and makes invisibility worse.
- Do not enforce canopy visibility by mutating visual state every frame.
- Back out the frame/tick enforcement path and only clean stale visual state at safe movement boundaries.

### Attempt 171: Boundary-Only Canopy Visual Cleanup

Idea:

Keep the useful part of Attempt 170, but remove the harmful part. Canopy hoppers should still clean stale hidden/helper state, but only at safe transition points: when a hop is staged, immediately before a stock movement command starts, and after the object is recreated at a landing tile. Do not touch render/helper state every frame while stock movement commands own the object.

Implementation shape:

- Replace `OverworldWildSpawns_EnforceCanopyHopperVisibility` with `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary`.
- Keep `OverworldWildSpawns_IsCanopyHopperProfile`.
- Remove the per-frame calls from:
  - `OverworldWildSpawns_TickMovementParams`;
  - `OverworldWildSpawns_FrameMovementTask`.
- Keep boundary cleanup calls in:
  - `OverworldWildSpawns_StageCanopyHopTarget`;
  - `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`;
  - `OverworldWildSpawns_RecreateSpawnObjectAtTile`.
- The boundary cleanup:
  - clears stale canopy render-hop helper/timer state only when the real object is not actively moving;
  - clears stale phantom hidden/flicker state;
  - clears `BIT_VANISH`;
  - does not normalize render position every frame.

Why this is new:

- Attempt 170 tried continuous per-frame enforcement and made invisibility worse.
- Attempt 171 keeps cleanup out of active movement frames and only runs at known transition boundaries.
- Earlier canopy attempts did not separate "always visible" cleanup into safe boundary-only moments.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsCanopyHopperProfile`
- `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary`
- `OverworldWildSpawns_StageCanopyHopTarget`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`

Verification:

- `git diff --check` passed before the build.
- Built as `test274.nds` and copied to Delta.

Runtime result:

- User reported Mankey still blinks / becomes invisible when on trees.
- User clarified that headbutt trees can affect visibility somewhat, but they do not make Pokemon completely invisible; other Pokemon that spawn on trees without canopy-hopper behavior do not have this issue.
- User clarified that the assumption "headbutt tree tiles themselves are unsafe render surfaces, so Mankey should use nearby landing/perch tiles instead" is wrong.

Learning:

- Boundary-only cleanup did not solve the tree-state blinking/invisibility.
- Do not pursue a tree-anchor rewrite that moves canopy hoppers to adjacent landing/perch tiles based on the rejected "tree tile render surface" assumption.
- Preserve the design that Mankey is on the tree.
- The stronger suspect is now the canopy arrival path, especially deleting/recreating the moving Mankey object when it lands on a headbutt-tree tile.

### Attempt 172: Skip Object Refresh On Canopy Tree Landings

Idea:

Keep Mankey on actual headbutt-tree tiles, but stop deleting/recreating the real object when a canopy movement segment lands on a tree. Ordinary tree spawns are stable because they can exist on tree tiles without being repeatedly recreated there. The risky part is likely the canopy behavior's arrival refresh, not the tree tile alone.

Implementation shape:

- Add `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`.
- For canopy-hopper profiles, return `FALSE` when the candidate refresh tile has metatile behavior `OW_WILD_TILE_HEADBUTT`.
- In `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, skip `OverworldWildSpawns_RecreateSpawnObjectAtTile` in the odd one-tile landing cleanup when the target is a headbutt-tree tile.
- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, skip `OverworldWildSpawns_RecreateSpawnObjectAtTile` when the just-landed tile is a headbutt-tree tile.
- Still clear `BIT_VANISH` when skipping the refresh.
- Preserve refresh behavior for non-tree canopy landings.

Why this is new:

- Attempt 168 kept the same real object through all stock command segments and still had some invisibility.
- Attempt 169 recreated after every completed stock command segment.
- Attempt 172 is narrower: keep the refresh path for off-tree landings, but avoid the recreation handoff specifically on headbutt-tree arrivals where the current bug appears.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test275.nds` and copied to Delta.

Runtime result:

- User noticed that after Mankey jumps two tiles, it starts blinking and bugs out badly.

Learning:

- Skipping refresh only on tree landings is too narrow.
- The bug appears at the two-tile segment landing, which can be an intermediate non-tree tile during a longer 5-7 tile canopy hop.
- The next attempt should avoid deleting/recreating the Mankey object in the middle of a multi-segment canopy hop, while still allowing final landing stabilization where needed.

### Attempt 173: Keep Same Object Across Intermediate Canopy Landings

Idea:

Preserve the live Mankey object through intermediate two-tile canopy segment landings. The current bug appears after a two-tile segment finishes, before the full stored canopy target is reached. That means the risky operation is likely the object refresh in the middle of the hop chain, not only the final tree landing.

Implementation shape:

- Add a `finalLanding` parameter to `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`.
- For canopy-hopper profiles, return `FALSE` when the landing is not the final stored canopy target.
- Continue skipping refresh on final headbutt-tree landings.
- Preserve the existing final non-tree refresh path for now, so ground ambush landings can still use the stabilization behavior.
- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, compute whether the object is already at the stored canopy target before deciding whether to recreate it.

Why this is new:

- Attempt 168 kept the same real object through stock movement segments, but did not include the later boundary cleanup/refined tree-landing rules.
- Attempt 169 recreated after every completed segment.
- Attempt 172 skipped recreation only on headbutt-tree landings.
- Attempt 173 is narrower than Attempt 168 and different from Attempt 172: only intermediate segment landings are forced to keep the same object, because the new runtime clue points at the two-tile segment boundary.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test276.nds` and copied to Delta.
- The first build caught a local declaration placement error before ROM output; that was fixed before the successful `test276.nds` build.

Runtime result:

- User clarified that the first two tiles animate fine. The bug begins after Mankey jumps more than two tiles, when the next segment in the chain should continue.

Learning:

- Attempt 173 corrected the mid-segment delete/recreate path, but the important runtime clue is more specific: the first stock segment is healthy, and the segment-to-segment handoff is suspect.
- The next attempt should stabilize the object after the first two-tile landing and avoid starting the next movement command immediately in the same handoff window.

### Attempt 174: Settle Intermediate Canopy Segment Handoff

Idea:

Treat a successful two-tile canopy segment landing as a boundary that needs a short stabilization window before the next stock movement command starts. The first two tiles animate correctly, so the travel command itself is probably viable. The bug begins when chaining beyond that first segment.

Implementation shape:

- Add `OW_WILD_SPAWNER_CANOPY_HOPPER_SEGMENT_SETTLE_FRAMES`.
- When a canopy segment lands but has not reached the stored full-hop target:
  - keep the same real object;
  - normalize the object to its landed logical tile with `OverworldWildSpawns_SetObjectTile`;
  - clear `BIT_VANISH`;
  - wait a short settle delay before the pending canopy hop can start the next segment.
- Preserve final landing behavior from Attempt 173:
  - skip final headbutt-tree refresh;
  - allow final non-tree refresh/stabilization.

Why this is new:

- Attempt 159 had a half-second wait between early stock jump-chain segments, but that was before strict 5-7 tile targets, before `WaitJumpLeft2` / `WaitJumpRight2`, before boundary-only cleanup, and before the no-intermediate-refresh rule.
- Attempt 173 kept the same object through intermediate segment landings, but still allowed the next segment to be queued immediately.
- Attempt 174 combines current carrier/cleanup rules with explicit landed-tile normalization and a short post-segment settle window.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_SEGMENT_SETTLE_FRAMES`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test277.nds` and copied to Delta.

Runtime result:

- User reported that Mankey is still completely invisible in trees.

Learning:

- The short segment-settle window does not fix the resting-on-tree visibility state.
- The first two tiles can animate, so the remaining issue looks less like the stock hop command itself and more like how the object is left when the full hop finishes on a headbutt-tree tile.
- Ordinary headbutt spawns are created directly at the tree tile and are not followed by the manual `OverworldWildSpawns_SetObjectTile` rewrite used by the canopy refresh helper.
- The next attempt should recreate only at the final tree landing, and should avoid manually normalizing the replacement object's tile after creation.

### Attempt 175: Recreate Final Tree Landing Without Manual Tile Rewrite

Idea:

When a canopy hop reaches its final target on a headbutt tree, rebuild the spawned object the way ordinary headbutt spawns are created, but do not immediately call `OverworldWildSpawns_SetObjectTile` on the replacement. This tests whether the manual coordinate/vector rewrite is what makes tree-resting Mankey differ from normal visible tree spawns.

Implementation shape:

- Keep the Attempt 174 intermediate-segment behavior:
  - no delete/recreate during intermediate canopy segment landings;
  - normalize the landed tile;
  - clear `BIT_VANISH`;
  - wait a short settle delay before the next segment.
- Change final canopy landings so they can refresh on headbutt-tree tiles again.
- Add `OverworldWildSpawns_ShouldNormalizeCanopyRefreshAtTile`.
- Add a `normalizeTileAfterCreate` argument to `OverworldWildSpawns_RecreateSpawnObjectAtTile`.
- Pass `FALSE` for final headbutt-tree refreshes, letting `CreateSpecialFieldObjectWithParams` initialize the replacement position like a normal headbutt spawn.
- Pass `TRUE` for non-tree final refreshes, preserving the previous stabilization behavior there.

Why this is new:

- Attempt 169 recreated after every completed segment and always used `OverworldWildSpawns_SetObjectTile` on the replacement.
- Attempt 172 skipped refresh specifically on headbutt-tree arrivals.
- Attempt 173/174 also skipped final tree refreshes while focusing on intermediate segment handoff.
- Attempt 175 is the first test that recreates only the final tree landing while deliberately skipping the manual post-create tile rewrite for that replacement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_ShouldRefreshCanopyObjectAtTile`
- `OverworldWildSpawns_ShouldNormalizeCanopyRefreshAtTile`
- `OverworldWildSpawns_RecreateSpawnObjectAtTile`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built once as `test278.nds`; that build succeeded but exposed new unused-parameter warnings in the edited refresh predicate.
- Added explicit unused-parameter markers for the predicate split.
- Rebuilt as `test279.nds` and copied to Delta.
- The rebuild no longer emits the new `x`/`y` unused-parameter warnings. Existing unrelated project warnings remain.

Runtime result:

- User reported this did not fix the real symptom: after Mankey jumps more than two tiles, the first two tiles animate fine, then Mankey starts bugging out.

Learning:

- The final tree refresh path was not the primary issue for this report.
- The runtime clue points back to the boundary after the first two-tile stock jump segment.
- The existing canopy render-hop timer/state is currently only ticked/restored; it is not started anywhere, so long hops are still being implemented by chaining stock two-tile jump commands.
- The next attempt should avoid the repeated stock two-tile command boundary entirely and use one spawner-owned render hop from origin to final target.

### Attempt 176: Use One Manual Render Hop For Full Canopy Distance

Idea:

Stop chaining stock two-tile jump commands for Mankey canopy hops. The first stock two-tile segment works, but the handoff into the next segment is where the bug starts. Use the existing canopy render-hop state as the actual movement: lerp the real object's X/Z render position from the current tile to the final target over a distance-scaled arc, then commit the logical tile only at the end.

Implementation shape:

- Add a starter for the existing `movementCanopyRenderHop*` state.
- In `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`, when the remaining distance is two or more tiles, start one full render hop to `movementCanopyHopTargetX/Y` instead of choosing a two-tile stock jump command.
- Preserve the one-tile final cleanup path.
- At render-hop completion:
  - commit the logical tile to the final target;
  - reuse the final refresh logic from Attempt 175, including skipping manual post-create tile normalization on headbutt-tree tiles;
  - finish the canopy hop normally.

Why this is new:

- Attempt 48 tried manual `posVec[1]` bobbing for a same-tile spot emote, but not full X/Z render movement for canopy travel.
- Attempts 159 and 173/174 changed timing around stock two-tile segment chaining, but still relied on multiple stock movement commands.
- Attempt 175 changed final tree refresh behavior, but still left long movement as chained two-tile stock commands.
- Attempt 176 is the first test that removes the segment-to-segment stock command boundary from Mankey's long canopy hop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_StartCanopyRenderHopMovementCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TickCanopyRenderHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built as `test280.nds` and copied to Delta.
- The edited overlay compiled without new Attempt 176-specific warnings. Existing unrelated project warnings remain.

Runtime result:

- User reported this feels like an instant teleport instead of a hop.

Learning:

- Removing the stock two-tile command boundary avoids the exact chained-command implementation, but direct real-object `posVec` interpolation still does not communicate visible motion.
- This matches earlier evidence from Attempt 48 that direct render-position edits can be overwritten, ignored, or visually collapse into a snap for these objects.
- The next step needs deeper investigation of the movement-command/render contract rather than another narrow timing tweak.
- New investigation questions:
  - whether stock movement lists can safely sequence multiple jump commands on spawned Pokemon;
  - whether multi-tile jump commands or wrappers exist in shipped scripts;
  - which object fields the renderer actually uses for smooth movement and visibility.

## Proposed Next New Experiments

Only use this section after checking that the current idea has not already been tried above.

### Experiment A: Add Back `MapObject_SetParam` Only

Purpose:

Check whether custom movement init/update can safely touch params without field-system lookup, scratch writes, or movement commands.

Would add:

- Init: set cooldown param only.
- Update: decrement cooldown param only.

Would still avoid:

- `object->fsys`
- global `FieldSystem *`
- `object->unkD8`
- single-movement flags
- movement command helpers
- coordinate reads

### Experiment B: Add Back Player/Object Coordinate Reads Only

Purpose:

Check whether position lookup is safe before command movement is attempted.

Would add:

- global `FieldSystem *` setter
- player coordinate reads
- object coordinate reads

Would still avoid:

- movement command helpers
- blocked-direction helper
- scratch writes
- single-movement flags

### Experiment C: Add A Look Command Before Any Walk Command

Purpose:

Check whether starting a non-moving facing command is safer than a walk command.

Would add:

- `MapObject_MovementCommandFromDirection`
- `MapObject_StartMovementCommand`
- `MapObject_SetSingleMovementActive`
- `MapObject_UpdateMovementCommand`

Would still avoid:

- walking commands
- blocked-direction helper

### Experiment D: Compare Stock Movement Descriptor Init/Update Requirements

Purpose:

Understand whether movement descriptor word `0` or callback semantics require stock values more specific than current assumptions.

Would inspect:

- stock descriptor table around movement `3`, `47`, and neighboring slots
- stock init/update/finalize/cleanup functions near `0x020612b4` and `0x020613f8`
- how movement manager calls descriptor callbacks

Would avoid:

- new runtime changes until the descriptor contract is clearer

### Experiment E: Obstruction-Blocked Aggressive Ram Alertness

Purpose:

Make `aggressive_ram` alertness use line of sight instead of raw cardinal range. The ram should only spot and lock onto the player if every tile between the ram and the selected player target is unobstructed.

Would add:

- a ram-specific obstruction scan after `OverworldWildSpawns_IsPlayerInCardinalLine` succeeds
- a check for each intermediate tile between the ram and target
- blocked metatiles and occupied blocking objects interrupting alertness
- the existing cardinal-direction range and moving-player target smoothing from Attempt 126

Would still avoid:

- changing non-ram alertness
- changing ram attentive movement once alert has already started
- changing ram crash collision/battle logic
- changing spawn/despawn/tile-occupancy exact-coordinate behavior

### Attempt 177: Canopy Hopper Vanilla Movement-List Task

Idea:

Replace the manual full-hop render interpolation from Attempt 176 with the game's vanilla movement-list task runner. Instead of repeatedly starting single movement commands from the spawner, build one stock movement list for the full canopy hop and let the engine own command sequencing, previous/current tile updates, movement scratch state, and jump rendering.

Why this is new:

- Attempt 159 and later stock-command attempts restarted independent `Jump*` / `Jump*2` commands from the spawner.
- Attempts 162, 163, and 176 tried manual large `posVec` interpolation on real or helper objects.
- Attempt 164 used a helper object plus stock command restarts.
- No previous canopy attempt has called the vanilla lower-level movement-list task directly with `(command, count)` entries that persist for the whole hop.

Implementation plan:

- Expose the vanilla movement-list helpers at `0x02062214`, `0x02062260`, and `0x0206226C`.
- Store a per-slot `SysTask *` and fixed movement-list buffer in overworld wild spawn state.
- Build lists such as `LockDir -> JumpRight2 x N -> optional JumpRight -> ReleaseDir -> MovementEnd`.
- Poll the list task from the existing movement frame task and run the normal canopy landing/refresh/finish logic once the list task completes.
- Clean up the task on slot reset, slot deletion, map context loss, and battle cleanup paths so no stale task points at a deleted object.

Verification:

- `git diff --check` passed before the build.
- First build attempt compiled the overlay but overflowed the base ROM/data region by `119` bytes because the movement-list task pointer/list buffers were stored inside `OverworldWildSpawnState`.
- Moved the movement-list task pointers and list buffers to overlay-local static storage so the base spawn state size stays stable.
- Built successfully as `test281.nds` and copied to Delta.
- The edited overlay compiled with only older unused diagnostics still present.

Runtime result:

- User reported:
  - Mankey now visibly hops instead of instant teleporting, except for in trees.
  - It can travel only 1-2 tiles at a time and never exceeds that.
  - It does not stay visible on/near trees.
  - Route leaving no longer crashes/freezes.

Learning:

- The vanilla movement-list task is safer for route transitions than the earlier helper/manual render-hop attempts.
- The active builder did not actually match the planned `JumpRight2 x N` shape; it emitted one `Jump*` command per path tile and did not add `LockDir`/`ReleaseDir`.
- Final canopy landing still recreates the object, keeping one of the suspect visibility handoffs alive.
- Continue from the movement-list path, but make the list actually use two-tile jump runs and avoid final canopy object recreation.

### Attempt 178: Canopy Movement Lists Use Jump2 Runs And No Final Recreate

Idea:

Keep the new vanilla `MapObject_StartMovementList` path from Attempt 177, but build the movement list as a real stock jump sequence:

- `LockDir`
- repeated `Jump*2` commands for same-direction runs
- an optional `Jump*` for an odd final tile
- `ReleaseDir`
- `MovementEnd`

Also stop recreating canopy-hopper objects on final landing. The current object should already be at the movement-list target, so final landing should normalize visibility and finish the canopy hop without deleting/recreating the real Mankey.

Why this is new:

- Attempt 177 introduced the movement-list task, but runtime showed the active list still behaved as 1-2 tile movement. Source verification showed `OverworldWildSpawns_BuildCanopyMovementList` emitted one one-tile `Jump*` command for each path step and did not append `LockDir`/`ReleaseDir`.
- Earlier attempts tried spawner-restarted stock jump commands, helper objects, and manual `posVec` interpolation. This keeps the engine-owned movement-list task but changes the list contents and removes the final recreate handoff.
- Earlier tree-landing attempts skipped only tree final refreshes or only intermediate refreshes; this attempt disables final refresh for canopy hoppers while keeping non-canopy refresh behavior intact.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test344.nds` and copied to Delta.
- The edited overlay compiled with only older unused diagnostics still present.

Runtime result:

- Pending user test.

Learning:

- Build-side result is stable. Runtime should verify whether Mankey now uses longer visible same-direction hop runs, remains visible on/near headbutt trees, and still survives route transitions without crashing/freezing.

### Attempt 179: Direct Engine-Owned Long Canopy Jump

Idea:

Stop treating `Jump*2` as a distance-two command. Disassembly and sidecar investigation show the stock jump wrappers use `MapObject_StartJumpMovementInternal` and that `Jump*` / `Jump*2` are timing variants around one-tile engine movement. For canopy hopper runs of at least 5 tiles, call the stock jump initializer directly with the normal one-tile delta but a longer frame count, so the engine owns the movement scratch, tile commits, and jump arc for one 5-7 tile straight run.

Implementation shape:

- Expose `MapObject_StartJumpMovementInternal` at `0x02062958 | 1`.
- Add the matching prototype to `include/map_events_internal.h`.
- Enable the previously disabled `OverworldWildSpawns_StartCanopyLongJumpCommand` path.
- Only use the direct internal jump when the first same-direction path run is at least `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`.
- Fall back to the vanilla movement-list task for shorter cleanup paths.
- Add one landing-boundary canopy visual cleanup after movement completion, without restoring the unsafe per-frame always-visible invariant from Attempt 170.

Why this is new:

- Attempts 159, 165, 167, 168, 177, and 178 used stock movement commands or movement lists as command sequences.
- Attempts 162, 163, 166, and 176 used manual or helper-object render interpolation.
- No previous attempt has called the stock internal jump initializer directly with a longer frame count for one engine-owned multi-tile run.

Files/symbols:

- `rom.ld`
- `include/map_events_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `MapObject_StartJumpMovementInternal`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test345.nds` and copied to Delta.
- The edited overlay compiled with only older unused diagnostics still present.

Runtime result:

- User reported:
  - Mankey never visibly travelled more than 1-2 tiles in one hop.
  - Mankey did not stay visible on/near trees after landing.
  - Leaving the route still did not avoid crashes/freezes.

Learning:

- Directly exposing `MapObject_StartJumpMovementInternal` was not enough because the active target picker could still choose a zig-zag path and the long-jump path only ran when the BFS path's first same-direction run was at least 5 tiles.
- The active path still kept legacy canopy movement-list fallback and canopy boundary cleanup still touched phantom hidden/flicker state, so this was not a clean canopy-only ownership model.
- Do not repeat Attempt 179 as "internal jump plus BFS first-run plus movement-list fallback plus phantom boundary cleanup."

### Attempt 180: Clean Straight-Run Canopy Driver

Idea:

Rebuild the active Mankey canopy movement path around one real object and one straight cardinal hop target. The new test should avoid the legacy systems that kept reappearing in failed canopy attempts: helper objects, object recreate/refresh, raw render-position interpolation, movement-list fallback, and phantom visibility cleanup.

Implementation shape:

- Add a direct straight-run target picker for canopy hoppers:
  - scan cardinal rays from the current tile;
  - prefer 5-7 tile landings;
  - require the landing tile to be a valid headbutt landing/perch tile;
  - avoid the previous landing, occupied tiles, and far-offscreen despawn targets.
- Use the direct internal jump starter only for same-axis target runs.
- Keep the normal internal one-tile jump delta and lengthen the frame count by run distance; disassembly shows the internal jump updater commits a tile whenever its accumulated delta reaches one tile, so scaling the delta would risk committing too many tiles too quickly.
- Remove the active movement-list fallback from canopy hopping while this test is active.
- Make canopy boundary cleanup canopy-only: clear `BIT_VANISH` on the real object and do not touch phantom flicker/hidden/helper state.
- On map-context reset, clear movement bookkeeping without revealing phantom objects or restoring ram wobble on stale map objects unless the caller explicitly requested current-object cleanup.

Why this is new:

- Attempt 179 used `MapObject_StartJumpMovementInternal`, but it depended on the BFS path's first run and still fell back to vanilla movement lists.
- Attempts 163-164 used helper objects; this does not.
- Attempts 166 and 176 used manual `posVec` travel; this does not.
- Attempts 169-175 used object recreate/refresh variations; this keeps the real object.
- Attempt 170 tried per-frame visibility enforcement; this only clears `BIT_VANISH` at controlled canopy boundaries and avoids phantom cleanup entirely.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryPickCanopyStraightRunTarget`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_ClearCanopyHopperVisualStateAtBoundary`
- `OverworldWildSpawns_ResetSlotMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built successfully as `test346.nds` and copied to Delta.
- The edited overlay compiled. The build now warns that several legacy canopy helpers are unused (`OverworldWildSpawns_RecreateSpawnObjectAtTile`, `OverworldWildSpawns_StartCanopyMovementListTask`, and `OverworldWildSpawns_GetCanopyPathFirstRunLength`) because this attempt intentionally disconnects the old recreate/list/BFS-first-run paths from active Mankey movement.
- Verified active canopy target selection now asks `OverworldWildSpawns_TryPickCanopyStraightRunTarget` before the older tree-pair pickers for both chill wandering and attentive "toward target" movement.
- Verified active canopy movement no longer falls back to `OverworldWildSpawns_StartCanopyMovementListTask` when the clean straight jump cannot start.
- Verified canopy boundary cleanup no longer clears phantom hidden/flicker/helper state.
- Verified map-context loss in the frame task now clears movement bookkeeping through `OverworldWildSpawns_ResetAllMovementStateOnly` without touching stale map objects.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 192: Range-Gated Canopy Long-Jump Carrier

Idea:

Keep the successful partner-prepped internal long-jump carrier from Attempt 190/191, but stop treating it as a general-purpose jump primitive. The user reported that `test358.nds` had a lot of bugs and that Mankey sometimes disappeared and never reappeared. The likely regression is that Attempt 191 allowed the carrier to accept any distance up to the raw `255` frame budget and let `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand` try that carrier before the older cleanup path.

Implementation shape:

- Set the active canopy hopper tile range to `3-8` tiles.
- Set the canopy ambush range to `8` so player-front ambushes can use the same maximum.
- Replace the raw frame-budget `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES` with behavior-gated `LONG_JUMP_MIN/MAX` aliases tied to the canopy hopper min/max constants.
- Make `OverworldWildSpawns_GetCanopyLongJumpTiming` reject distances below `3` or above `8`.
- Make `OverworldWildSpawns_StartCanopyLongJumpCommand` reject same-axis pending targets outside `3-8` before running partner prep.
- Make return-to-tree candidate selection use the same minimum `3` tile distance instead of allowing one-tile return hops.
- If a pending canopy target has a remaining distance of exactly `2`, clear the target, reveal the object, and cool down instead of entering the long-jump prep path or leaving an impossible short target staged.

Why this is new:

- Attempt 190 proved one partner-prepped four-tile internal jump.
- Attempt 191 generalized that carrier too broadly.
- Earlier visibility attempts either enforced visibility every frame, used helper/recreate handoffs, or cleaned phantom state. This attempt does not reintroduce those systems; it constrains the successful carrier to the behavior range and adds a narrow abort reveal for invalid short targets.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MIN_HOP_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_MAX_HOP_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_AMBUSH_RANGE`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MIN_TILES`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_LONG_JUMP_MAX_TILES`
- `OverworldWildSpawns_GetCanopyLongJumpTiming`
- `OverworldWildSpawns_StartCanopyLongJumpCommand`
- `OverworldWildSpawns_TryStartNextCanopyHopMovementCommand`
- `OverworldWildSpawns_TryUseReturnHeadbuttTreeHopCandidate`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test359.nds` into the Delta ROM folder.
- Overlay compiled with the expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- User reported that Mankey now rarely decides to jump.

Learning:

- The 3-8 carrier range stayed safe enough to continue, but the behavior layer became too restrictive and could stage targets that the carrier later rejected.
- The old "visible perch" radius still made tree/perch state fuzzy, so Mankey could be considered on/near a tree without being on a concrete tree-adjacent perch.

### Attempt 193: Exact Headbutt Perches And Pre-Stage Carrier Validation

Idea:

Remove the idea of a perch radius from canopy hopper movement. A Mankey perch should be a concrete tile: either the headbutt tree tile itself or one cardinal tile adjacent to a real headbutt tree. Also stop staging canopy targets that the 3-8 same-axis long-jump carrier cannot actually execute.

Implementation shape:

- Replace the old 2-tile "visible perch" scan with `OverworldWildSpawns_IsHeadbuttTreeAdjacentPerchTile`, which checks only the four cardinal neighbors for a headbutt metatile.
- Update canopy "on tree" detection to use the exact adjacent-perch helper instead of the radius scan.
- Update straight-run canopy target selection to require exact adjacent-tree perches.
- Update the Route 29 verifier helper to use cardinal adjacency to the specific tree coordinate, not a radius.
- Make `OverworldWildSpawns_TryResolveHeadbuttTreeHopCandidate` only return same-axis targets in the 3-8 long-jump range.
- Remove the BFS/passable-path gate from that resolver because the active carrier is one direct same-axis jump, not a step path.
- Change `OverworldWildSpawns_StageCanopyHopTarget` to return `BOOL` and reject non-cardinal or out-of-range targets before the pre-hop wait is set.

Why this is new:

- Attempt 192 only range-gated the carrier after target selection.
- Earlier canopy visibility fixes either used broad perch radius logic, path/BFS validation, or post-failure cleanup.
- This attempt changes the tree/perch definition itself and prevents invalid pending targets before the 30-frame windup starts.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsHeadbuttTreeAdjacentPerchTile`
- `OverworldWildSpawns_IsNearHeadbuttTreeForCanopyVerifier`
- `OverworldWildSpawns_TryResolveHeadbuttTreeHopCandidate`
- `OverworldWildSpawns_TryPickCanopyStraightRunTarget`
- `OverworldWildSpawns_IsCanopyHopperOnTree`
- `OverworldWildSpawns_StageCanopyHopTarget`

Verification:

- `git diff --check` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test360.nds` into the Delta ROM folder.
- Overlay compiled with the expected older unused-helper warnings from disconnected canopy/phantom diagnostic paths.

Runtime result:

- Pending build/runtime test.

Learning:

- Pending.

### Attempt 194: Forced Mankey Tree-Tile Occupancy Render Probe

Idea:

The long-hop carrier now appears promising enough to pause movement work and isolate the next tree behavior question: can Mankey occupy the actual headbutt tree tile without being hidden by the canopy? This should not reuse the old perch-radius, helper-object, phantom hiding, or hop-state cleanup paths. For this test, spawn exactly one Mankey on a known Route 29 headbutt tree tile, do not move it, and try a small follower-style render flag bundle so it can potentially draw above the tree.

Why this is new:

- Attempt 193 removed the broad perch radius and improved movement target validation.
- Earlier canopy attempts focused on hopping, helper sprites, object recreation, visibility cleanup, or exact adjacent perches.
- This attempt does not move Mankey at all and does not stage a perch/hop target; it tests tree-tile occupancy and object render flags directly.

Implementation shape:

- Add `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_OCCUPANCY_TEST`.
- Broaden only the shared forced-canopy spawn/refill guards to compile for either the old movement test or the new tree-occupancy test.
- Force the Route 29 test spawn to `594,389`, the known headbutt tree tile, while ignoring player/follower occupancy and still rejecting duplicate active spawned Pokemon.
- Override Mankey headbutt behavior to idle/no-alert/no-attentive movement while this test is enabled.
- Skip the canopy-hopper perch relocation while this test is enabled.
- Apply a test-only follower-style render bundle to the forced Mankey object: set `0x2400`, clear `0x180`, call `MapObject_SetFlag29(TRUE)`, call `sub_02069DC8(TRUE)`, and clear `BIT_VANISH`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_FORCE_CANOPY_TREE_OCCUPANCY_TEST`
- `OW_WILD_SPAWNER_FORCE_CANOPY_TEST_SPAWN`
- `OverworldWildSpawns_TryPickRoute29CanopyTreeOccupancyTestSpawnPosition`
- `OverworldWildSpawns_ApplyCanopyTreeOccupancyTestRenderParams`

Verification:

- `git diff --check` passed before and after the log update.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test361.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this tree-occupancy probe.

Runtime result:

- User clarified before runtime testing that this targeted the wrong tile class. The desired probe is the tree-top/canopy-cap metatile visually above/overlapping the player and follower, not the actual headbutt behavior tile.

Learning:

- Do not treat "tree behavior" and "headbutt tree coordinate" as equivalent for the render-order test. The next test should target a canopy-top visual tile and should not require `GetMetatileBehaviorAt(...) == OW_WILD_TILE_HEADBUTT`.

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
