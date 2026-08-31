# Canopy Hopper Mankey Behavior

> **Status: historical attempt collection.** Use it as evidence, not current
> design. Start at [`overworld-system/README.md`](overworld-system/README.md).

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Mankey canopy hopper is the largest behavior thread and combines pathing, long hops, tree-top target selection, and rendering problems.
- The durable movement idea is constrained 3-8 tile canopy hops with real-object ownership where possible.
- Tree-top rendering behind canopy remains a separate compositor/layering problem from movement target selection.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 62 | 62 | Use Water Droplet Tired Bubble |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
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
| 76 | 215 | Direct Validated Route 29 Test Perch |
| 77 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 78 | 237 | Allow Two-Tile Final Tree-Top Landings In Mankey Path Search |
| 79 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 80 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 81 | 230 | Direct Mankey Tree-Top Lifted-Row Fallback |
| 82 | 231 | Revert Shared Row Lift And Keep Direct Fallback Only |
| 83 | 226 | One Row Above Archive Mankey Tree-Top Target |
| 84 | 227 | Restore Archive MinY Tree-Top Logic After Too-High Row |
| 85 | 228 | Sparse Archive Tree-Top Row Lift |
| 86 | 234 | Lift Single-Row Mankey Footprints |
| 87 | 234 | Lift Single-Row Mankey Footprints |
| 88 | 229 | Live Blocked-Row Tree-Top Confirmation |
| 89 | 224 | Mankey Tree-Top Late Map-Object Redraw Effect |
| 90 | 225 | Mankey Tree-Top Effect-Owned Marker Canary |
| 91 | 214 | Bias Forced Verifier Ahead Of Player |
| 92 | 242 | Charmander Canopy Locator Probe |
| 93 | 260 | Charmander Probe Fallback Marker |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 96 | 259 | Boundary-Derived Headbutt Tree-Top Locator |
| 97 | 242 | Pair Tree-Top Candidates And Derive Top Row From Archive Bottom |
| 98 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 99 | 238 | Generic Headbutt Tree-Top Location Filter |
| 100 | 213 | Score Forced Verifier By Resolved Perch |
| 101 | 65 | A-Button Facing Interaction Starts Spawn Battle |
| 102 | 197 | Route 29 Top-Cap Coordinate Probe |
| 103 | 198 | Route 29 Upper Top-Cap Coordinate Probe |
| 104 | 199 | Actual Headbutt Anchor With Render-Only Tree-Top Offset |
| 105 | 200 | Exact Headbutt Tile Occupancy, No Graphic Offset |
| 106 | 201 | Guaranteed Forced Headbutt Mankey Spawn |
| 107 | 202 | Spawn On Row Above Headbutt Tree Footprint |
| 108 | 203 | Lower Tree-Top Test Tile And Preserve Forced Idle Visibility |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 110 | 224 | Mankey Tree-Top Stock Large-Pokemon Draw Callback |
| 111 | 225 | Mankey Tree-Top Stock Helper Draw Callback |
| 112 | 226 | Mankey Tree-Top Post-Draw Sprite Priority Probe |
| 113 | 227 | Mankey Tree-Top Live Sprite Depth Zero Probe |
| 114 | 228 | Mankey Tree-Top Synced Visual Proxy |
| 115 | 229 | Mankey Tree-Top BG Layer Identification Probe |
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
| 130 | 250 | Follower-Sprite Tree-Top Proxy Probe |
| 131 | 251 | Prefer Unblocked Direct Mankey Tree-Top Directions |
| 132 | 252 | Generic Field Effect Probe For Tree-Top Mankey |
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
| 143 | 231 | Prefer Nearest Direct Mankey Tree-Top Jump |
| 144 | 232 | Include Exposed Archive Top Row For Mankey Tree Targets |
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
| 262 | 195 | Forced Mankey Canopy-Top Occupancy Render Probe |
| 263 | 196 | Normal-Path Canopy-Top Occupancy Probe |
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

### Attempt 62: Use Water Droplet Tired Bubble

Idea:

Turn off the tired bubble probe now that all ids are mapped. Define named constants for every discovered follower bubble id, set `OW_WILD_SPAWNER_TIRED_BUBBLE_ID` to `OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET`, and keep the direct `ov01_02203A48` creator plus sound suppression from the working bubble path.

Why this is new:

- Attempts 57 through 61 were discovery/probe builds.
- Attempt 61 mapped the remaining ids and identified water droplet id `9` as the best tired icon.
- No previous attempt has disabled the probe and used a stable water-droplet tired bubble.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test159.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test159.nds`.
- `git diff --check` passed before the build.
- Verified source defines named constants for all discovered follower bubble ids `0` through `13`.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE` is disabled.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID` is set to `OW_WILD_SPAWNER_BUBBLE_ID_WATER_DROPLET`.

Runtime result:

- User reported Mankey still blinks / becomes invisible when on trees.
- User clarified that the assumption "headbutt tree tiles themselves are unsafe render surfaces, so Mankey should use nearby landing/perch tiles instead" is wrong.

Learning:

- Boundary-only cleanup did not solve the tree-state blinking/invisibility.
- Do not pursue a tree-anchor rewrite that moves canopy hoppers to adjacent landing/perch tiles based on the rejected "tree tile render surface" assumption.
- Next attempt should preserve the design that Mankey is on the tree, and investigate the movement/object/render state transition that makes it blink while there.

### Attempt 64: Separate Behavior Class Rules From Behavior Variable Overrides

Idea:

Correct the resolver hierarchy to `Default behavior -> Behavior class override -> Behavior variable override`. Add one rule table for assigning behavior classes from spawn context, and a separate ordered rule table for variable overrides. A Pokemon can therefore be classified as `Skittish` by species/group/pool/etc. and still receive independent variable overrides like `max_speed = 1`.

Why this is new:

- Attempt 63 introduced the behavior profile contract, but its final layer was incorrectly species-specific.
- No previous attempt has separated behavior-class assignment from post-class variable overrides.
- No previous attempt has added broad group matching, such as baby Pokemon, as behavior input.
- The proposed hierarchy matches the user's corrected design: default values first, class changes second, and variable overrides last.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test161.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test161.nds`.
- `git diff --check` passed before the build.
- Verified `OverworldWildBehaviorClassRule` assigns behavior classes from spawn context separately from variable overrides.
- Verified `OverworldWildBehaviorVariableOverride` applies matched behavior variables after the default profile and behavior-class override.
- Verified the resolver now merges `default behavior -> behavior class override -> behavior variable override`.
- Verified baby Pokemon are grouped through `OW_WILD_BEHAVIOR_GROUP_BABY`, assigned `OW_WILD_BEHAVIOR_CLASS_SKITTISH`, and given a separate `maxSpeed` variable override.
- Verified Pidgey's test speed is still present, but now as a behavior-variable override rather than a species-specific resolver layer.

Runtime result:

- User reported:
  - Mankey still does not visibly travel; it blinks to trees or stands still invisible in trees.
  - Mankey is invisible.
  - Leaving the route still does not avoid the crash/freeze.

Learning:

- Clean straight-run target selection plus the internal jump starter did not solve the visibility problem.
- Removing movement-list fallback and phantom boundary cleanup was not enough; the object still becomes invisible around the tree/perch state.
- The next attempt should stop testing hop travel and isolate the spawn/anchor visibility state first.

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

### Attempt 224: Mankey Tree-Top Late Map-Object Redraw Effect

Idea:

Create a custom field-effect descriptor whose lifetime is tied to a settled Mankey on a verified headbutt-tree top tile, then call `MapObject_GfxDraw` from that effect render callback. The hope was that field-effect render timing would submit the same Mankey sprite after the canopy layer.

Why this was new:

- Earlier attempts changed map-object height, priority bits, draw mode, follower flags, or proxy objects.
- This attempt used a real field-effect descriptor and effect lifetime, but kept the payload as the existing Mankey map-object draw.

Implementation shape:

- Added `OverworldWildFieldEffectDescriptor`.
- Added `OverworldWildMankeyTreeTopLateDrawEffectInit` / `Work`.
- Created/cleared the effect through `ov01_021F1620` / `ov01_021F1640` only while Mankey was settled on a cached tree-top tile.
- Render callback called `MapObject_GfxDraw(effectWork->object)`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `FieldEffect_GetInitData`
- `ov01_021F146C`
- `ov01_021F1620`
- `ov01_021F1640`

Verification:

- Built successfully before this log was repaired.
- Runtime checkpoint reported in thread summary as `test420.nds`.

Runtime result:

- User reported: "still not fixed".

Learning:

- Drawing the same `LocalMapObject` through a field-effect render callback is still the losing map-object renderer family.
- Do not retry effect-timed `MapObject_GfxDraw`, object height, follower flags, `unkA0`, priority bits, or proxy map objects without new renderer evidence.
- The next direction must use an effect-owned visual payload, not a redraw of the existing map object.

### Attempt 225: Mankey Tree-Top Effect-Owned Marker Canary

Idea:

Keep the successful field-effect lifetime/anchoring from Attempt 224, but remove the failed `MapObject_GfxDraw` payload. Instead, have the effect own a small timer and spawn a known-good speech-bubble marker over Mankey while the Mankey slot is settled on a verified tree-top tile. This tests effect anchoring, lifetime, and above-canopy visibility without touching movement or map-object render flags.

Why this is new:

- Attempt 224 used a field effect, but its payload was still `MapObject_GfxDraw`.
- Earlier bubble probes were separate periodic frame-task probes and could start before Mankey was actually settled on a tree-top tile.
- This attempt makes the marker a child of the tree-top effect's own validity path, so it should only appear while the exact Mankey slot/object/tile state is valid.

Implementation shape:

- Add `markerTimer` to `OverworldWildMankeyTreeTopLateDrawEffectWork`.
- Initialize the timer so the marker appears quickly after the effect is created.
- In the effect update callback, validate the Mankey slot/object/map/tile, then periodically call `OverworldWildSpawns_ShowBubble`.
- Remove the `MapObject_GfxDraw` call from the effect render callback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_FRAMES`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_MARKER_ID`
- `OverworldWildSpawns_MankeyTreeTopLateDrawEffectUpdate`
- `OverworldWildSpawns_MankeyTreeTopLateDrawEffectRender`

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md include/map_events_internal.h rom.ld` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test421.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Pending user test.

Learning:

- Pending.

Learning:

- Pending.

Learning:

- Pending.

### Attempt 214: Bias Forced Verifier Ahead Of Player

Idea:

Attempt 213 still selected the same left-edge tree/perch. The scorer targeted a tile close to the player, but the forced spawn becomes eligible as soon as the player crosses the Route 29 threshold, so "close to player" still favors the old left-side tree. Bias the forced verifier toward a real Route 29 headbutt tree/perch ahead of the player, on the right side of the camera, so the capture can observe the hop instead of an edge object.

Why this is new:

- Attempt 210 changed pair ordering, not the camera-relative scoring target.
- Attempt 213 scored by resolved perch, but still aimed near the player.
- No previous attempt biases the forced Route 29 verifier toward an ahead/right camera-side perch.

Implementation plan:

- Add a real Route 29 headbutt coordinate from `armips/data/headbutt.s` (`594,389`) to the forced test pair list.
- Score fixed test perches toward `playerX + 6`, `playerY - 2` to prefer an ahead/right, top-screen-visible perch.
- Rebuild and capture a dense headless sequence.

Verification:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test444.nds`.

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

### Attempt 213: Score Forced Verifier By Resolved Perch

Idea:

Attempt 212 made the Route 29 test Mankey visible in early raw frames, but the actor is still at the left/bottom edge of the camera and the hop is not readable enough to verify. The fixed-pair verifier still chooses the first valid tree pair, then resolves that tree to a perch afterward. Instead, choose the forced test spawn by scoring the actual resolved perch relative to the player/camera.

Why this is new:

- Attempt 210 only reordered fixed tree pairs and still fell back to the old left-edge staging.
- Attempt 212 changed perch-side visibility preference, but did not change how fixed pairs are selected.
- No previous attempt scores forced Route 29 test candidates by the final resolved perch coordinate.

Implementation plan:

- In `OverworldWildSpawns_TryPickFixedRoute29CanopyTestSpawnPosition`, evaluate all fixed Route 29 pairs instead of returning the first valid one.
- Resolve each pair to a perch first, reject occupied/out-of-range perches, then score the perch toward a camera-centered tile near the player.
- Keep the one-tile vanilla `Jump*` movement-list carrier and the front/side perch preference.
- Rebuild and capture another dense headless sequence.

Verification:

- Pending.

Runtime result:

- Pending.

Learning:

- Pending.

### Attempt 65: A-Button Facing Interaction Starts Spawn Battle

Idea:

Add a deliberate A-button battle path for spawned overworld Pokemon. Keep the existing contact/settle detector for automatic battles, but add a frame-polled A-button check that finds the tile the player is facing and starts a battle if any active spawned Pokemon occupies that tile. This path should ignore the automatic contact filters such as tired cooldown, flee grace, and in-progress movement, because pressing A is an intentional interaction.

Why this is new:

- Attempts 35 through 38 focused on contact battle timing and settle retries after player/spawn movement.
- No previous attempt has used A-button input to start a spawned-Pokemon battle.
- No previous attempt has matched the player's facing tile against active spawned Pokemon as a battle trigger.
- No previous attempt has restarted the movement frame task after battle cleanup using the cleanup script's current `FieldSystem`.

Files/symbols:

- `include/overworld_wild_spawns.h`
- `include/overworld_wild_spawns_internal.h`
- `src/script_new_cmds.c`
- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test162.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test162.nds`.
- `git diff --check` passed before the build.
- Verified `OverworldWildSpawns_TryStartBattleForSlot` centralizes pending battle setup for both contact and A-button battle starts.
- Verified `OverworldWildSpawns_TryStartBattleFromAButton` polls a new A-button press, derives the player's facing tile from the player map object's `curFacing`, and starts battle for any active spawned Pokemon on that tile.
- Verified the A-button path does not call `OverworldWildSpawns_IsTouchingPlayer`, so tired cooldown, flee grace, and active movement-command filters do not block intentional A interactions.
- Verified battle cleanup now receives the script context's `FieldSystem` and restarts the movement frame task if active spawned Pokemon remain on the current map.

Runtime result:

- User reported Mankey is spawning on the wrong tree tiles. The screenshot shows the forced `594,388` point is on the side/shoulder canopy art below the desired flat top-cap tiles.

Learning:

- Removing the follower render bundle was still a separate, valid safety fix, but it did not answer the tile-class question because the test coordinate was visually wrong.
- Do not keep assuming `headbutt anchor Y - 1` is a tree-top/canopy-cap tile. The Route 29 headbutt archive shows this cluster has anchors at `(594,389)` and `(595,389)`, so the next non-repeating probe should move one more tile up to the likely top-cap row.

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

### Attempt 66: Implement Behavior Profile Table Semantics

Idea:

Make the behavior resolver match the requested profile table directly:

- Default: wander at max speed 1, show a question bubble when alert, then return to chill with no self-start battle.
- Aggressive: wander at max speed 2, hop plus angry speech when alert, chase the player, and start battle on contact while attentive.
- Skittish: wander at max speed 2, hop plus exclamation speech when alert, flee from the player, then show the water droplet tired bubble after stamina is spent.

Also rename `restTime` to `restRate`, keep Pidgey as an aggressive speed-3 variable override for testing, and make alertness use a facing cone inside radius 3 instead of radius-only spotting.

Why this is new:

- Attempt 63 created the general behavior profile contract, but left the older default chase/stamina values in place.
- Attempt 64 separated behavior-class rules from variable overrides, but did not implement the new default/aggressive/skittish table semantics.
- Attempt 65 added intentional A-button battle starts, but did not change which behavior profiles can start automatic battles.
- No previous attempt has made default Pokemon speech-only and A-button-only for battles while letting aggressive Pokemon self-start battles only during attentive chase.
- No previous attempt has required a facing cone for alertness.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test163.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test163.nds`.
- `git diff --check` passed before and after the build.
- Verified `OverworldWildBehaviorProfile` now uses `restRate` instead of `restTime`.
- Verified the default profile is speech-only (`PONDER`) with no attentive state, stamina, tired state, or automatic battle start.
- Verified the aggressive profile uses angry hop speech, chase-with-battle attentive state, stamina `12`, water droplet tired state, rest rate `1`, max speed `2`, and range `8`.
- Verified the skittish profile uses scared hop speech, flee attentive state, stamina `12`, water droplet tired state, rest rate `1`, max speed `2`, and range `8`.
- Verified Pidgey is assigned the aggressive class and then receives a max-speed `3` behavior-variable override.
- Verified alert checks use `OverworldWildSpawns_IsPlayerInFacingCone` with radius `3`.
- Verified contact battles require active aggressive attentive behavior; A-button facing interaction still starts a battle for any spawned Pokemon.

Runtime result:

- User reported Mankey is still hidden by the headbutt-tree canopy on `test379.nds`.

Learning:

- `LocalMapObject::unkA0` draw mode alone does not make spawned Mankey render above canopy-priority tiles.
- Follow-up disassembly showed both draw modes route through overlay 1's draw mode table and still apply the same `0x1000` sprite priority value.
- Avoid repeating the draw-mode-only probe. The next useful direction is a stock draw-callback/descriptor probe or a real sprite priority override.

### Attempt 224: Mankey Tree-Top Stock Large-Pokemon Draw Callback

Idea:

Do not repeat the failed height, follower-flag, `0x180` flag-only, or `unkA0` draw-mode probes. Instead, when spawned Mankey is settled on a verified headbutt-tree top tile, save its current `LocalMapObject::unkC8` draw callback and temporarily swap in the stock large-Pokemon draw callback from overlay 1 (`0x021F7811`). Restore the original callback when Mankey leaves the tree-top tile or the slot is cleaned up.

Why this is new:

- Attempt 223 changed `unkA0`, but left the draw callback unchanged. Disassembly suggests `unkA0` is only a sub-mode inside the same draw path.
- This attempt changes the actual map-object draw callback selected by callback descriptor index `17` (small Pokemon) to the already-existing descriptor index `16` large-Pokemon draw callback.
- It does not use a custom overlay callback, so it avoids the lifetime hazard of leaving a map object pointing at overlay 149 code during route/map transitions.
- It does not move the object, change object height, or reintroduce follower render flags.

Implementation shape:

- Replace the failed tree-top draw-mode save/restore state with per-slot draw-callback save/restore state.
- Add `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK ((void (*)(LocalMapObject *))0x021F7811)`.
- In `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`, keep clearing `0x180`/`BIT_VANISH`, but set `object->unkC8` to the stock large-Pokemon draw callback while Mankey is on the verified tree-top tile.
- Restore the saved callback in `OverworldWildSpawns_RestoreMankeyTreeTopRenderOverride` and clear saved callback state on spawn/slot cleanup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK`
- `sOverworldWildMankeyTreeTopDrawCallbacksSaved`
- `sOverworldWildMankeyTreeTopSavedDrawCallbacks`
- `OverworldWildSpawns_SaveMankeyTreeTopDrawCallback`
- `OverworldWildSpawns_RestoreMankeyTreeTopDrawCallback`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Verification:

- Checked the log first; stock draw-callback swapping had not been tried.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` passed before documenting the attempt.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test380.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- Superseded before user test.

Learning:

- A read-only renderer explorer reported that the large-Pokemon callback path is likely just another size/model family and not a true "above priority canopy" path.
- Keep this build result as a checkpoint, but do not spend runtime testing time on `test380.nds` unless the newer helper callback probe fails to build.

### Attempt 225: Mankey Tree-Top Stock Helper Draw Callback

Idea:

Follow the renderer explorer's more precise recommendation: keep the same Mankey-only `unkC8` callback save/restore probe from Attempt 224, but use the stock helper/special-object draw callback `0x021F7919` instead of the stock large-Pokemon draw callback `0x021F7811`.

Why this is new:

- Attempt 224 used the existing large-Pokemon draw callback. It was built but superseded before runtime testing after the explorer identified `0x021F7919` as the more relevant helper/special-object candidate.
- No previous runtime attempt has swapped spawned Mankey to the stock helper/special-object draw callback while it is on the verified tree-top tile.
- This still avoids a custom overlay callback lifetime hazard and still does not touch object height, `posVec`, follower render flags, or `unkA0`.

Implementation shape:

- Change `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK` from `0x021F7811` to `0x021F7919`.
- Keep the existing per-slot original-callback save/restore, priority-bit clearing, and `BIT_VANISH` clearing from Attempt 224.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_DRAW_CALLBACK`

Verification:

- Checked the log first; this exact helper callback swap had not been tried.
- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test381.nds`.
- Build warnings were limited to the existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User reported that Mankey is still hidden by the headbutt-tree canopy on `test381.nds`.

Learning:

- Swapping to the stock helper/special-object draw callback still does not change the relevant canopy ordering.
- Combined with Attempt 224's large-Pokemon callback probe, stock `unkC8` callback swapping is very likely the wrong level of the renderer. Do not keep cycling stock draw callbacks as the primary solution.
- The next useful direction is a real Mankey-only post-draw sprite/OAM priority or depth probe, while avoiding the already-failed object-height, follower-flag, `0x180` flag-only, `unkA0`, and stock-callback-swap approaches.

### Attempt 226: Mankey Tree-Top Post-Draw Sprite Priority Probe

Idea:

Stop using stock callback replacement as the solution. Instead, use the normal small-Pokemon draw callback for Mankey, then apply a narrowly scoped cell/OAM priority override to the sprite resource only while the spawned Mankey is on a verified headbutt-tree top tile. This keeps the logical tile unchanged and targets the renderer ordering layer directly.

Why this is new:

- Attempts 224 and 225 changed which stock draw callback ran, but did not apply any post-draw mutation to the object sprite itself.
- Attempts 220, 194, 195, 221, and 223 already ruled out object height/`posVec`, follower render flags, priority-bit clearing alone, and `unkA0` draw-mode changes.
- A renderer explorer clarified that `sub_02023F04`/`sprite + 0xB6`/`sprite + 0xB8` is animation/cell-frame state, not BG priority. This attempt therefore avoids the earlier depth/frame-index guess.
- This attempt clears cell/OAM `attr2` priority bits (`0x0C00`) for the loaded sprite cell entries after the normal small-Pokemon draw path has run, so the sprite should draw above BG priority layers on subsequent frames.

Implementation shape:

- Replace the tree-top stock-callback swap with a custom ARM9-resident wrapper that calls the normal small-Pokemon draw callback (`0x021F7895`), obtains the map-object sprite pointer from render data (`object + 0x108`), walks the loaded cell bank, and clears the priority bits from visible cell OAM entries.
- Keep the wrapper Mankey/tree-top gated and restore the original callback when the slot leaves the tree-top tile or is cleaned up.
- Leave the old Mankey/tree-top `0x180` and `BIT_VANISH` clearing in place because that was already part of the surrounding tree-top override, but do not rely on it as the primary solution.

Files/symbols:

- `include/overworld_wild_spawns.h`
- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_MankeyTreeTopDrawWrapper`
- `OW_WILD_MANKEY_TREE_TOP_CELL_PRIORITY_MASK`

Verification:

- Checked this log first and confirmed this is not a repeat of the failed object-height, follower-flag, `0x180` flag-only, `unkA0`, large-Pokemon callback, or helper callback attempts.
- `git diff --check -- include/overworld_wild_spawns.h src/overworld_wild_spawns.c src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied the ROM to Delta as `test382.nds`.
- Build warnings were limited to existing unused helper/diagnostic warnings on this movement branch plus the existing unused `bsys` battle warning.

Runtime result:

- User tested `test382.nds`:
  - Mankey still does not render above the headbutt-tree canopy.
  - Mankey stays visible and stable, but remains behind the tree.
  - Leaving the route still avoids crash/freeze.

Learning:

- Build confirmed the ARM9-resident wrapper and overlay callback install path compile/link cleanly.
- Loaded cell/OAM priority is not the renderer layer that controls this headbutt-tree canopy ordering, or the mutation is too early/resource-local to affect the final draw ordering.
- Since Mankey stays visible and route-stable, the remaining problem is specifically priority/layering, not spawn tile selection, invisibility cleanup, or route-transition ownership.
- Do not repeat object-side priority tweaks unless new renderer evidence identifies the actual final OAM/hardware slot or BG/object priority contract.

### Attempt 227: Mankey Tree-Top Live Sprite Depth Zero Probe

Idea:

Attempt 226 mutated the loaded cell/OAM resource and did not affect the canopy ordering. Disassembly of overlay 1 still shows the normal field-object draw variants call `sub_02023F04` with depth-like constants such as `0`, `0x800`, `0x1000`, and `0x2000`, and the current Mankey path was previously observed to keep reaching the `0x1000` family. Test a distinct, narrower live-sprite probe: while Mankey is on the verified tree-top tile, call the normal small-Pokemon draw callback, but force the live sprite depth/range value at `sprite + 0xB8` to `0` immediately before and after the normal draw.

Why this is new:

- Attempt 223 changed `LocalMapObject::unkA0` draw mode but did not directly set the live sprite depth value.
- Attempts 224 and 225 changed stock callback family but still let those callbacks choose their normal live sprite depth.
- Attempt 226 cleared loaded cell/OAM `attr2` priority bits in the cell bank, not the live sprite's `+0xB8` depth value.
- This does not retry object height, follower render flags, `0x180` flag-only clearing, stock callback cycling, or loaded cell-bank mutation.

Implementation shape:

- Keep the same Mankey/tree-top-gated ARM9-resident wrapper and original callback save/restore from Attempt 226.
- Replace the loaded cell-bank/OAM traversal with `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH ((void (*)(void *, u32))0x02023F1D)`.
- In `OverworldWildSpawns_MankeyTreeTopDrawWrapper`, obtain render data from `object + 0x108`, set primary/secondary live sprite depth to `0`, call the normal small-Pokemon draw callback (`0x021F7895`), then set depth to `0` again in case the callback rewrote it.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `OW_WILD_MANKEY_TREE_TOP_SET_SPRITE_DEPTH`
- `OW_WILD_MANKEY_TREE_TOP_FRONT_DEPTH`
- `OverworldWildSpawns_SetMankeyTreeTopRenderDataDepth`
- `OverworldWildSpawns_MankeyTreeTopDrawWrapper`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test383.nds`.
- Compile warnings were limited to existing unused-parameter / unused-helper diagnostics in unrelated or long-running debug code.
- User tested `test383.nds`:
  - Mankey still does not render above the canopy.
  - Mankey stays visible after a few seconds, but remains behind the tree.
  - Leaving the route still avoids crash/freeze.

Learning:

- Build confirms the live sprite depth setter probe compiles, links, and packages cleanly.
- Setting the live sprite depth/range value before and after the normal draw callback does not beat the headbutt-tree canopy layer.
- Together with Attempt 226, object-side priority/cell/depth mutation appears exhausted unless new renderer evidence identifies a different final draw layer.

### Attempt 228: Mankey Tree-Top Synced Visual Proxy

Idea:

Attempts 223-227 exhausted the real object's draw-mode, draw-callback, loaded cell/OAM priority, and live sprite depth levers. Instead of mutating the real Mankey object again, keep the real object as the logical actor and create a separate Mankey-only visual proxy object while the real object is settled on a verified headbutt-tree top tile. The proxy uses its own ignored object-id range and is synced to the real object's visual position each update, but its logical anchor is the headbutt-tree/front coordinate.

Why this is new:

- It does not change the real object's `unkA0`, `unkC8`, height fields, `posVec`, loaded OAM/cell data, live sprite depth, or follower render flags.
- It does not retry the rejected render-offset-on-real-object approach from Attempt 199.
- It adapts the already route-safe phantom helper-object pattern, but gives Mankey its own proxy object-id range and cleanup path.
- If this proxy still renders behind the canopy, the next useful path is a map/compositor layer identification probe rather than more map-object priority work.

Implementation shape:

- Add `movementMankeyTreeTopProxyObjects[OW_WILD_MAX_SPAWNS]` to `OverworldWildSpawnState`.
- Add `OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START` and make spawn-position occupancy ignore this visual-only id range.
- When Mankey is on `OverworldWildSpawns_IsMankeyOnHeadbuttTreeTopTile`, restore any old tree-top render override on the real object, clear `BIT_VANISH`, and ensure a proxy object at `(objectX, objectY + OW_WILD_SPAWNER_MANKEY_HEADBUTT_TREE_TOP_Y_OFFSET)`.
- Sync the proxy's `posVec` and facing to the real object each update, while leaving the real object active and visible for this first test.
- Delete or detach the proxy through slot cleanup, movement reset, route-context detach, and canopy visual-boundary cleanup.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_MANKEY_TREE_TOP_PROXY_OBJECT_ID_START`
- `movementMankeyTreeTopProxyObjects`
- `OverworldWildSpawns_EnsureMankeyTreeTopProxyObject`
- `OverworldWildSpawns_ClearMankeyTreeTopProxyObject`
- `OverworldWildSpawns_IsIgnoredVisualObjectId`

Runtime result:

- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test384.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics, the existing unused `bsys` battle warning, and the now-unused old Mankey tree-top priority-save helpers because this proxy probe no longer activates the failed priority-wrapper path.
- User tested `test384.nds`:
  - Mankey appears above the canopy for only roughly 1-2 frames.
  - After that, Mankey is visible only behind the tree.
  - Leaving the route still avoids crash/freeze.
  - Duplicate/offset Mankey weirdness is visible.

Learning:

- Build confirms the proxy object-id range, proxy state pointer, sync path, cleanup path, and occupancy-ignore path compile/link cleanly.
- A map-object proxy can briefly escape on creation, but the normal field object renderer quickly reasserts the same canopy ordering.
- Do not pursue a constantly recreated map-object proxy as a real fix; it would likely be brittle and visually noisy.
- The next useful direction is a map/compositor layer identification probe or a non-map-object effect layer, not another map-object priority/proxy variation.

### Attempt 229: Mankey Tree-Top BG Layer Identification Probe

Idea:

Attempt 228 showed that even a separate map-object proxy falls back behind the canopy after the first frame or two. Since Attempts 223-228 now rule out the normal map-object render levers, identify which Engine A layer owns the headbutt-tree canopy. While Mankey is settled on a verified tree-top tile, temporarily cycle visible BG layer masks using `GX_EngineAToggleLayers` so runtime testing can tell whether disabling one layer removes the canopy while the Pokemon remains visible.

Why this is new:

- It does not change Mankey's map object, sprite callback, sprite data, OAM priority, depth/range state, height, `posVec`, follower flags, or proxy objects.
- It follows Erdos' renderer investigation: overlay 1 uses `GX_EngineAToggleLayers = 0x02022C60 | 1` around field compositor setup, so this probes map/compositor planes rather than the object renderer.
- It removes the failed synced proxy behavior from the active tree-top path before adding the new diagnostic.

Implementation shape:

- Add a tiny diagnostic state machine with phases for masks `2`, `4`, `8`, and a restore phase.
- When any active Mankey is on a verified tree-top tile, cycle every fixed number of frames:
  - phase 0: disable mask `2`, enable masks `4` and `8`
  - phase 1: disable mask `4`, enable masks `2` and `8`
  - phase 2: disable mask `8`, enable masks `2` and `4`
  - phase 3: enable all three masks
- When no active Mankey is on the tree-top tile, restore all masks and reset the diagnostic timer.
- Keep the real Mankey visible and delete any leftover proxy object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `GX_EngineAToggleLayers`
- `OverworldWildSpawns_UpdateMankeyTreeTopLayerProbe`
- `OverworldWildSpawns_AnyMankeyOnHeadbuttTreeTopTile`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- Removed active creation/sync of the failed Mankey tree-top proxy from the tree-top update path; any leftover proxy object is deleted when the real Mankey is updated.
- Added `GX_EngineAToggleLayers` layer cycling while any active Mankey is on a verified headbutt-tree top tile:
  - phase 0 disables mask `2`
  - phase 1 disables mask `4`
  - phase 2 disables mask `8`
  - phase 3 restores all three masks
- The probe advances from the frame task rather than player-step only, so the layer cycle should continue while the player stands still.
- Added restoration on context loss, spawner clear, and frame-task stop so the route should not inherit a disabled layer.
- `git diff --check` passed.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test385.nds`.
- Build warnings were limited to the existing long-running movement/debug unused-helper diagnostics plus the existing battle unused-parameter warning; no fatal build errors.

Learning:

- Runtime result pending user test.

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

### Attempt 250: Follower-Sprite Tree-Top Proxy Probe

Idea:

Use the new bubble result to test one more renderer family before committing to a custom effect-layer clone. Do not repeat the old special-field proxy from Attempt 228, which was created with `CreateSpecialFieldObjectWithParams` and quickly fell behind the canopy. Instead, while the real Mankey remains the logical actor on the tree-top tile, create a visual-only proxy through the actual follower-sprite factory `CreateFollowingSpriteFieldObject` and keep it synced on the same tile.

Why this is new:

- Attempt 228 used a normal special field object proxy, not the follower-sprite factory.
- Attempts 194/195 mutated the real Mankey with follower-style flags and caused blinking/invisibility; this keeps the real actor untouched.
- Attempt 236 proved follower/emote overlay effects can draw above canopy, but it only rendered a bubble, not a Pokemon sprite.
- Dewey's read-only renderer investigation found no stock helper for arbitrary Pokemon sprites on the bubble layer, but confirmed the overlay/effect system is the likely layer family if this proxy still loses to the canopy.

Implementation shape:

- Add `OverworldWildSpawns_EnsureMankeyTreeTopProxyObject`, which creates a Mankey proxy with `CreateFollowingSpriteFieldObject` only while the real active Mankey is on a cached `HEADBUTT_TREE_TOPS` tile.
- Give the proxy the existing ignored visual object-id range so it does not block spawning or battle checks.
- Sync the proxy tile/facing to the real Mankey and clear `BIT_VANISH`.
- Delete the proxy when Mankey leaves the tree-top tile or the slot/context cleanup runs.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `CreateFollowingSpriteFieldObject`
- `OverworldWildSpawns_EnsureMankeyTreeTopProxyObject`
- `OverworldWildSpawns_UpdateMankeyTreeTopPriorityBits`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test409.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending. If this proxy is also behind the canopy, stop using map objects for this layer problem and move to a custom overlay/effect-layer visual clone based on `ov01_02203A48` / descriptor table `0x02209518`.

### Attempt 251: Prefer Unblocked Direct Mankey Tree-Top Directions

Idea:

Fix the case where Mankey appears to prefer a blocked upward direct tree-top candidate and never considers an obvious 3-tile downward jump. The direct tree-top picker currently returns before the BFS/path fallback and only ranks direct tree-top candidates by distance. Keep direct tree-top targeting, but add a first-step blocked tier: direct candidates whose immediate direction is not blocked beat direct candidates whose immediate direction is blocked, even if the blocked candidate was scanned first.

Why this is new:

- Attempts 247-249 changed which coordinates count as strict tree-top targets.
- Attempt 250 targeted tree-top rendering and did not change movement target priority.
- No previous attempt has ranked direct Mankey tree-top candidates by whether their immediate cardinal direction is blocked.
- This does not reintroduce `OW_WILD_TILE_HEADBUTT`, broad vertical bands, or exposed-row fallbacks.

Implementation shape:

- Pass the active Mankey object into `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`.
- For each same-axis direct tree-top candidate, derive its cardinal direction and check `MapObject_IsMovementDirectionBlocked(object, direction)`.
- Track `bestBlockedRank` across all scanned headbutt trees. Rank `0` unblocked candidates ahead of rank `1` blocked candidates; within the same rank, keep the existing nearest-distance selection and random tie-break.
- Keep blocked candidates as fallback if every direct tree-top option is blocked.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseDirectMankeyStructuralHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test411.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending user test. The screenshot case should now prefer the 3-tile downward jump when the upward direct candidate is blocked, while keeping blocked direct candidates as fallback only when no unblocked direct candidate exists.

### Attempt 252: Generic Field Effect Probe For Tree-Top Mankey

Idea:

Use the user-confirmed bubble result to stop map-object rendering work and test a broader effect family. The emotion bubble path is visible above canopy but can only display built-in icons. Before attempting a custom Mankey effect actor, call the generic anchored field-effect helper `ov01_021FFF5C(object, effectId)` from settled tree-top Mankey and cycle a small range of effect ids. If these effects render above canopy too, they provide a better template for a custom visual clone than more map-object mutations.

Why this is new:

- Attempts 223-228 and 250 exhausted real-object render levers and proxy map objects.
- Attempt 236 proved the follower/emote bubble effect layer is visible above canopy.
- Earlier Onix attempts used `ov01_021FFF5C` for ram step feedback, but not for settled Mankey tree-top layering.
- This does not retry `CreateFollowingSpriteFieldObject`, object height, draw mode, draw callbacks, OAM priority, live sprite depth, layer toggling, or emotion bubble icons as the final visual.

Implementation shape:

- Disable the Mankey tree-top bubble probe now that it has answered the layer question.
- Stop creating the Mankey tree-top proxy object while Mankey is on a verified tree-top tile; delete any stale proxy from that path.
- Add `OverworldWildSpawns_UpdateMankeyTreeTopEffectProbe`, called from the frame movement task after the layer/bubble probe hooks.
- While a settled active Mankey is on a verified tree-top tile, call `ov01_021FFF5C(object, effectId)` every 90 frames and cycle effect ids `0..12`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_MANKEY_TREE_TOP_EFFECT_PROBE_ENABLED`
- `OverworldWildSpawns_UpdateMankeyTreeTopEffectProbe`
- `ov01_021FFF5C`

Runtime result:

- `git diff --check -- src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c documentation/overworld_wild_movement_attempt_log.md` passed before the build.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test412.nds`.
- Build warnings were limited to existing movement-branch unused helper/diagnostic warnings plus the existing battle unused-parameter warning.

Learning:

- Pending user test. Test whether the cycling anchored effects appear above canopy, behind canopy, or not at all while Mankey remains on the tree-top tile.

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

### Attempt 231: Prefer Nearest Direct Mankey Tree-Top Jump

Idea:

The user reported a Mankey standing three tiles from a valid tree-top target but not jumping to it. Attempt 230 changed which tiles count as valid tree-top targets, but the direct target picker still preferred the farthest aligned direct tree-top jump from older long-hop testing. For chill-state tree return, the nearest valid direct top-row jump should win before any farther candidate.

Why this is new:

- This does not change the 2x6 footprint resolver from Attempt 230.
- This does not retry earlier render, proxy, forced-spawn, or offset approaches.
- This only changes the direct candidate priority rule: nearest valid direct jump beats farther valid direct jumps.

Implementation shape:

- Initialize Mankey direct target `bestDistance` to `maxHop + 1`.
- In `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`, reject candidates farther than the current best and reset tie counting when a closer candidate is found.
- Keep random tie-breaking among equally near direct top-row targets.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryUseMankeyHeadbuttTreeTopCandidate`
- `OverworldWildSpawns_TryPickMankeyHeadbuttTreeTopTarget`

Runtime result:

- Implemented in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- `git diff --check` passed.
- Built successfully with `./docker-makerom.cmd` and copied to Delta as `test387.nds`.
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

### Attempt 195: Forced Mankey Canopy-Top Occupancy Render Probe

Idea:

Correct Attempt 194 by moving the isolated render probe from the known Route 29 headbutt behavior tile to the adjacent canopy-top visual tile. The user specifically wants to test the red-box style tree-top tiles that can visually obscure the player/follower, so this test should not reject the target just because it is not classified as `OW_WILD_TILE_HEADBUTT`.

Why this is new:

- Attempt 194 tested `594,389`, a known headbutt behavior coordinate, and required behavior `15`.
- This attempt tests `594,388`, one tile north of that headbutt pair, as a canopy-top visual tile.
- The movement remains disabled and the follower-style render flag bundle remains the same, so the only intentional variable is the target tile class.

Implementation shape:

- Rename the forced test coordinate constants to canopy-top terminology.
- Set the forced Route 29 Mankey test coordinate to `594,388`.
- Remove the `OW_WILD_TILE_HEADBUTT` metatile-behavior requirement from the forced position picker.
- Keep the forced spawn terrain as headbutt so encounter/species plumbing remains simple, but set `position.startX/startY` directly to the canopy-top tile.
- Keep movement, alertness, and attentive behavior disabled for this test.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X`
- `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_Y`
- `OverworldWildSpawns_TryPickRoute29CanopyTopOccupancyTestSpawnPosition`
- `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams`

Verification:

- `git diff --check` passed before and after the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test362.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.

Runtime result:

- User reported that Mankey appears to blink and disappear.

Learning:

- The corrected canopy-top coordinate is likely hitting the intended tile class, but the follower-style render bundle is unsafe here.
- This matches the prior shiny investigation warning that full follower render flags on wild special-field objects can make them invisible or unstable. The next probe should keep the object on the normal special-field path and not call the follower flag/toggle helpers for non-shiny canopy-top testing.

### Attempt 196: Normal-Path Canopy-Top Occupancy Probe

Idea:

Keep the forced Route 29 canopy-top coordinate from Attempt 195, but remove the follower-style render bundle that prior shiny work already identified as unsafe for wild special-field objects. For this probe, Mankey should still spawn on `594,388` with no movement, but its render setup should stay on the normal special-field path and only clear `BIT_VANISH`.

Why this is new:

- Attempt 194/195 used the follower-style bundle: set `0x2400`, clear `0x180`, `MapObject_SetFlag29(TRUE)`, `sub_02069DC8(TRUE)`, then clear `BIT_VANISH`.
- `documentation/overworld_shiny_sprite_investigation.md` explicitly says full follower render flags on overworld wild objects can make them invisible.
- This attempt removes those follower-path flags/toggles instead of adding more visibility enforcement.

Implementation shape:

- Keep `OW_WILD_SPAWNER_CANOPY_TOP_OCCUPANCY_TEST_X/Y` at `594,388`.
- Keep the forced spawn idle/no-alert/no-attentive.
- Change `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams` to only clear `BIT_VANISH`.
- Leave the standard `FollowPokeMapObjectSetParams(...)` call in `OverworldWildSpawns_ApplyPokemonRenderParams`, since that is the stable normal overworld wild sprite metadata path used by regular/shiny spawns.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ApplyCanopyTopOccupancyTestRenderParams`
- `documentation/overworld_shiny_sprite_investigation.md`

Verification:

- `git diff --check` passed before and after the build.
- Built successfully with `./docker-makerom.cmd`.
- Copied ROM checkpoint `test363.nds` into the Delta ROM folder.
- Overlay compiled; the remaining warnings are expected unused legacy canopy/phantom helpers from disconnected diagnostic paths plus `sRoute29CanopyOpenAirVerifierOffsets`, which is compiled by the shared forced-canopy test guard but not used by this canopy-top probe.
- Sidecar render investigation independently confirmed that the follower bundle left follower-only bits on a normal special-field wild object and recommended this normal-path probe.

Runtime result:

- Pending user test.

Learning:

- Pending.

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
