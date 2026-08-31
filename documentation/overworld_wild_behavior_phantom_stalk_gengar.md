# Phantom Stalk Gengar Behavior

> **Status: historical attempt collection.** Use it as evidence, not current
> design. Start at [`overworld-system/README.md`](overworld-system/README.md).

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Phantom stalk is the one intentional opt-in user of BIT_VANISH and flicker/teleport presentation.
- Real-object vanish toggling was unreliable; helper/apparition/materialization paths were explored for safe battle entry.
- A-button and bump battle gates must only fire on stable visible phantom states.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 30 | 30 | Obvious Spawner-Driven Tile Movement |
| 31 | 31 | Frame Task Movement Command Updates |
| 38 | 38 | Pidgey Fast Movement Command |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
| 66 | 182 | Tree-Anchor Single Stock Jump Probe |
| 67 | 183 | Tree-Anchor Stock Jump2 Probe |
| 68 | 184 | Tree-Anchor Chained Jump2 Four-Tile Probe |
| 69 | 185 | Chained Jump2 Without Midpoint Tile Normalization |
| 70 | 186 | Chained Jump2 With Logical-Only Midpoint Commit |
| 71 | 187 | Partner-Wrapped Moving Jump2 Probe |
| 72 | 188 | Partner-Wrapped Chained Jump2 Four-Tile Probe |
| 73 | 189 | Single Partner Wrapper Around Two Jump2 Commands |
| 74 | 190 | Partner-Prepped Single Internal Four-Tile Jump |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 102 | 197 | Route 29 Top-Cap Coordinate Probe |
| 103 | 198 | Route 29 Upper Top-Cap Coordinate Probe |
| 104 | 199 | Actual Headbutt Anchor With Render-Only Tree-Top Offset |
| 105 | 200 | Exact Headbutt Tile Occupancy, No Graphic Offset |
| 106 | 201 | Guaranteed Forced Headbutt Mankey Spawn |
| 107 | 202 | Spawn On Row Above Headbutt Tree Footprint |
| 108 | 203 | Lower Tree-Top Test Tile And Preserve Forced Idle Visibility |
| 114 | 228 | Mankey Tree-Top Synced Visual Proxy |
| 206 | 128 | Phantom Stalker Hidden Movement |
| 207 | 129 | Phantom Flicker And Follower Behind Targeting |
| 208 | 130 | Phantom Blink Behind Player Then Flicker Chase |
| 209 | 131 | Faster Phantom Destination Flicker And Battle Reveal |
| 210 | 132 | Deterministic Phantom Flicker Pulse |
| 211 | 133 | Refresh Phantom Sprite On Visible Flicker Phase |
| 212 | 134 | Phantom Flicker Apparition Object |
| 213 | 135 | Phantom Teleport Alert Build-Up |
| 214 | 136 | Active Phantom 60 Percent Flicker Loop |
| 215 | 137 | Active Phantom Real-Object Flicker |
| 216 | 138 | Recreate Phantom Object After Teleport |
| 217 | 139 | Origin/Destination Teleport Flicker And Face Player |
| 218 | 140 | Active Phantom Teleport-Step Movement |
| 219 | 141 | Front-Of-Player Phantom Teleport Movement |
| 220 | 142 | One-Second Pause After Active Phantom Teleport |
| 221 | 143 | One-Second Pause After Phantom Alert Arrival |
| 222 | 144 | Visible Teleport Pauses And Faster Alert Teleport |
| 223 | 145 | Restrict Directional Bump Battles To Phantom Stalkers |
| 224 | 146 | Recreate Real Phantom After Attentive Teleport |
| 225 | 147 | Limit Phantom Bump Battles To Visible Pause |
| 226 | 148 | Phantom Chill Wander Teleportation |
| 227 | 149 | Recompute Active Spawn Behavior Class |
| 228 | 150 | Stable Phantom Battle Entry Gate |
| 229 | 151 | Materialize Visible Phantom Flicker For A-Button Battles |
| 230 | 152 | Disable Phantom Stalk Alert-State Teleport |
| 231 | 153 | Mankey Canopy Hopper Headbutt-Tree Profile |
| 234 | 156 | Force Land Test Spawns To Mankey |
| 240 | 162 | Custom Rendered Far Canopy Hop |
| 241 | 163 | Canopy Helper Object Far-Hop Visual |
| 244 | 166 | Real Object Deferred Logical Commit Render-Hop |
| 245 | 167 | Horizontal WaitJump Command Probe |
| 247 | 169 | Recreate Real Canopy Object After Each Segment |
| 248 | 170 | Canopy Hopper Always-Visible Invariant |
| 249 | 171 | Boundary-Only Canopy Visual Cleanup |
| 254 | 176 | Use One Manual Render Hop For Full Canopy Distance |
| 255 | 177 | Canopy Hopper Vanilla Movement-List Task |
| 257 | 179 | Direct Engine-Owned Long Canopy Jump |
| 258 | 180 | Clean Straight-Run Canopy Driver |
| 259 | 192 | Range-Gated Canopy Long-Jump Carrier |
| 260 | 193 | Exact Headbutt Perches And Pre-Stage Carrier Validation |
| 261 | 194 | Forced Mankey Tree-Tile Occupancy Render Probe |
| 262 | 195 | Forced Mankey Canopy-Top Occupancy Render Probe |
| 263 | 196 | Normal-Path Canopy-Top Occupancy Probe |

## Original Attempt Sections

### Attempt 30: Obvious Spawner-Driven Tile Movement

Idea:

Make the movement result unmistakable for runtime testing. Fresh spawned Pokemon temporarily use stock idle movement `0` instead of stock wander `3`. After the spawner starts a walk command, it immediately burst-polls `MapObject_UpdateMovementCommand` up to 32 iterations and clears the single-movement flag if the command finishes. The cooldown reset is `0`, so a finished command can be followed by another command on the next player-step tick.

Why this is new:

- Attempt 29/`test124.nds` proved update/clear polling does not crash but was visually ambiguous.
- Previous no-op movement tests used slot `47` aliasing or disabled spawn paths; no previous build spawned Pokemon directly with movement `0` while driving their walk commands from the stable overlay-149 spawner step loop.
- No previous build has tried bounded burst-polling to force a started spawner command to visually complete for testing.

Files/symbols:

- `include/overworld_wild_movement.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_IDLE_OBJECT_MOVEMENT` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT` should resolve to `OW_WILD_MOVE_STOCK_IDLE`.
- Fresh spawns should pass movement `0` into `CreateSpecialFieldObjectWithParams`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_PARAM_RESET` should be `0`.
- `OverworldWildSpawns_UpdateSpawnerMovementCommand` should cap burst polling at `OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS` (`32`).
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`.
- Movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- User reported no crash.
- Pokemon rarely moved toward the player.
- When movement happened, it felt like an instant teleport to the adjacent tile rather than animated movement.

Learning:

- Switching fresh spawns to stock idle movement `0` and burst-polling the command does not crash.
- The burst-poll proves the command can complete a tile step, but completing all update iterations inside one player-step tick is not visually acceptable.
- The next direction should preserve spawner-owned commands but advance them over frames.

Verification:

- Built as `test125.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_IDLE_OBJECT_MOVEMENT` is enabled.
- `OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT` resolves to `OW_WILD_MOVE_STOCK_IDLE`.
- Fresh spawns pass `OW_WILD_SPAWNER_MOVEMENT_OBJECT_MOVEMENT` into `CreateSpecialFieldObjectWithParams`; source now defines `OW_WILD_MOVE_STOCK_IDLE` as movement `0`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` is enabled.
- `OW_WILD_SPAWNER_MOVEMENT_PARAM_RESET` is `0`.
- Source verification shows `OverworldWildSpawns_UpdateSpawnerMovementCommand` caps burst polling at `OW_WILD_SPAWNER_MOVEMENT_BURST_UPDATE_STEPS` (`32`).
- Disassembly of `OverworldWildSpawns_UpdateSpawnerMovementCommand` shows the loop bound compare against `#32`, and target calls to `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_UpdateMovementCommand` at `0x02062429`, and `MapObject_ClearSingleMovementActive` at `0x0205F63D`.
- Disassembly target scan still shows the walk setup targets: `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Source still avoids slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`; references in `src/overworld_wild_movement.c` remain behind the idle diagnostic and are not part of the active overlay movement path.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Copied to Delta as `test125.nds`.
- `git diff --check` passed.

Expand:

- Disable burst polling.
- Keep fresh spawns on stock idle movement `0` to avoid stock wander masking the test.
- Create a short-lived `SysTask` when a spawner-owned command starts.
- Let the task call `MapObject_UpdateMovementCommand` once per frame and destroy itself when no in-progress commands remain.

### Attempt 31: Frame Task Movement Command Updates

Idea:

Keep fresh spawned Pokemon on stock idle movement `0`, but stop completing their walk command in the player-step hook. When the spawner starts a walk command, mark the object in-progress and create a frame-level `SysTask` if one is not already running. The task loops active spawned Pokemon, updates only objects with the in-progress marker, clears the single-movement flag when the command finishes, resets the cooldown, and destroys itself once no in-progress commands remain.

Why this is new:

- Attempt 30/`test125.nds` proved burst-polling can complete a tile step, but it visually teleports.
- Earlier update/clear attempts were either player-step based or inside slot-47 callbacks.
- No previous build has isolated a `CreateSysTask`-driven frame updater for spawner-owned wild Pokemon movement while keeping slot `47` no-op and fresh spawns on stock idle movement `0`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` should be `0`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK` should be `1`.
- The active path should call `CreateSysTask` when a spawner-owned movement command starts.
- The frame task should call `MapObject_UpdateMovementCommand` at most once per object per task tick.
- The frame task should call `MapObject_ClearSingleMovementActive` only when update reports completion.
- The frame task should call `DestroySysTask` after no active spawned Pokemon has `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS`.
- Map-context changes and battle start should stop the frame task.
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`.
- Movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- Built as `test126.nds`.
- User reported no crash.
- User reported the movement works.

Learning:

- Advancing the spawner-owned walk command through a frame-level `SysTask` fixes the instant-tile-snap behavior seen in `test125.nds`.
- The stable path is: keep slot `47` no-op, spawn Pokemon with stock idle movement `0`, start a spawner-owned walk command from the player-step hook, and update that command once per frame until complete.
- This confirms the previous bug was update timing, not the walk command helper itself.

Verification:

- `./docker-makerom.cmd` completed successfully.
- Copied to Delta as `test126.nds`.
- Source flags confirm `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BURST_UPDATE` is `0` and `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_FRAME_TASK` is `1`.
- Source confirms fresh spawns still use `OW_WILD_MOVE_STOCK_IDLE`.
- Source confirms the active path creates `OverworldWildSpawns_FrameMovementTask` with `CreateSysTask`, stops it with `DestroySysTask`, and calls the stop path on battle start and map-context changes.
- Source confirms `OverworldWildSpawns_UpdateSpawnerMovementCommand` calls `MapObject_UpdateMovementCommand` and clears the single-movement flag only when update reports completion.
- Linked overlay target scan found `CreateSysTask` target `0x0200E321`, `DestroySysTask` target `0x0200E391`, `MapObject_UpdateMovementCommand` target `0x02062429`, and `MapObject_ClearSingleMovementActive` target `0x0205F63D`.
- Linked overlay target scan still contains the expected movement helper targets `0x02060BB9`, `0x0205F649`, `0x0206234D`, `0x0206217D`, and `0x0205F631`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `git diff --check` passed.

Expand:

- Keep the frame-task update timing from `test126.nds`.
- Stop using object param `0` as the spawner-owned cooldown/in-progress marker.
- Track movement cooldown and in-progress ownership per spawn slot.
- Clear/reset spawner-owned movement state when battle starts and when battle cleanup runs.
- Try a secondary chase/flee direction if the primary direction is blocked.

### Attempt 38: Pidgey Fast Movement Command

Idea:

Keep the existing global movement decision cooldown at `0`, and make Pidgey faster by changing only its movement command family from normal stock walk `0x08` to stock fast walk `0x0C`. Sentret and every other species stay on the current `0x08` baseline.

Why this is new:

- Earlier attempts changed global movement cadence and command ownership, but did not select movement command speed per species.
- A partial cooldown-only idea would have made Sentret slower rather than Pidgey faster; that was rejected before building and is not the active solution.
- Local ARM9 disassembly shows the `0x08` direction family uses a 16-frame movement setup, while the `0x0C` direction family uses an 8-frame movement setup, so this tests a stock faster movement command instead of direct coordinate writes or burst-poll teleporting.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test135.nds` and copied to Delta.
- `git diff --check` passed.
- Verified source uses `OW_WILD_SPAWNER_MOVEMENT_FAST_WALK_UP_COMMAND 0x0C` only when `spawn->species == SPECIES_PIDGEY`.
- Verified Sentret has no species-specific slowdown path and remains on the default `OW_WILD_SPAWNER_MOVEMENT_WALK_UP_COMMAND 0x08`.
- Verified local ARM9 command table entries for `0x08` and `0x0C` are valid stock movement command families.

Runtime result:

- User clarified that Pidgey should become faster, not that Sentret should become slower.
- This led into generalizing movement speed levels instead of using a one-off species-only fast path.

Learning:

- Per-species speed should use faster stock movement command families rather than slowing baseline Pokemon down.
- The speed concept should become a behavior/profile parameter, which is expanded in the next attempt.

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

### Attempt 128: Phantom Stalker Hidden Movement

Idea:

Add a ghost behavior that spots the player, shows a short ellipsis alert, disappears, takes several normal movement steps while invisible, then reappears while continuing to stalk behind the player. This should make Gengar feel like it is moving unseen rather than simply walking at the player.

Implementation shape:

- Add `phantomStalker` as a behavior class for ghost-group Pokemon.
- Add `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.
- Add `OW_WILD_BEHAVIOR_ALERT_STATE_SPEECH_ELLIPSIS`.
- Add per-slot hidden state:
  - `movementPhantomHidden`;
  - `movementPhantomHiddenSteps`.
- Use `MapObject_SetBits(object, BIT_VANISH)` to hide the Pokemon after the alert cue.
- Use `MapObject_ClearBits(object, BIT_VANISH)` to reveal it after `OW_WILD_SPAWNER_PHANTOM_STALK_HIDDEN_STEPS` completed movement steps.
- Build phantom stalking directions toward the tile behind the player's current facing.
- Keep movement command execution on the existing collision-safe spawner command path.
- Reveal hidden phantoms on reset, tired/rest transition, blocked hidden movement, and before A-button battles can target them.
- Force behavior test spawns to Gengar for this focused test build.

Why this is new:

- Earlier attempts used `BIT_VANISH` only as a render fix for shiny overworld Pokemon, not as timed behavior presentation.
- Earlier movement attempts tested visible chase/flee/playful/ram movement, but none made a Pokemon move invisibly for several completed steps and then reappear.
- Earlier player-position smoothing helped chase intent, but no previous attempt targeted the tile behind the player's current facing.
- This deliberately avoids true phasing/collision bypass for the first ghost pass.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_BEHAVIOR_CLASS_PHANTOM_STALKER`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`
- `OW_WILD_BEHAVIOR_ALERT_STATE_SPEECH_ELLIPSIS`
- `OW_WILD_SPAWNER_PHANTOM_STALK_HIDDEN_STEPS`
- `OverworldWildSpawns_MaybeStartPhantomStalkerVanish`
- `OverworldWildSpawns_RevealPhantomStalker`
- `OverworldWildSpawns_BuildPhantomStalkerDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test226.nds`.
- Verified active source defines the phantom stalker class, attentive state, ellipsis alert state, hidden-step state arrays, and forced Gengar test spawn.
- Verified hidden phantoms use `BIT_VANISH`, reveal after completed hidden movement steps, reveal on reset/tired transition, and are skipped by the universal A-button battle path while hidden.
- Verified phantom movement direction scoring targets the tile behind the player's current facing and still uses the existing spawner movement command path.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 129: Phantom Flicker And Follower Behind Targeting

Idea:

Make phantom stalkers flicker visible during some hidden movement steps so the player occasionally sees the Pokemon moving, and make the stalking target choose the closest tile behind either the player or the follower Pokemon instead of only behind the player.

Implementation shape:

- Add a per-slot `movementPhantomFlickerTimers` state array.
- When a hidden phantom starts a movement command, randomly open a short visibility window.
- Tick the flicker window from the frame movement task and restore `BIT_VANISH` when the window expires.
- Reset the flicker timer whenever a phantom reveals, despawns, respawns, or resets its movement state.
- Replace the player-only behind-target helper with a target builder that adds the tile behind the active player object, direct follower object, and fallback scanned follower object.
- Select the closest behind-target candidate from the ghost's current position and keep using the existing collision-safe movement command path.

Why this is new:

- Attempt 128 made phantoms fully invisible until the hidden-step counter finished.
- Attempt 128 targeted only the tile behind the player's facing direction.
- No previous attempt has exposed brief hidden-movement flicker windows or used the follower's facing to create phantom stalk targets.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `movementPhantomFlickerTimers`
- `OverworldWildSpawns_TryStartPhantomFlicker`
- `OverworldWildSpawns_UpdatePhantomFlicker`
- `OverworldWildSpawns_BuildPhantomBehindTargets`
- `OverworldWildSpawns_TryGetClosestPhantomBehindTarget`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test227.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test227.nds` both exist at 176 MB.
- Verified active source no longer references the player-only `OverworldWildSpawns_TryGetPlayerBehindTarget` helper.
- Verified hidden phantoms reset `movementPhantomFlickerTimers` on reveal, slot reset, and fresh spawn initialization.
- Verified the frame movement task ticks phantom flicker windows before updating in-progress movement commands.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 130: Phantom Blink Behind Player Then Flicker Chase

Idea:

Change phantom stalker attentive behavior from "walk toward a behind-target" to a clearer blink-and-chase pattern. When the ghost enters attentive state, it vanishes, teleports up to 5 tiles behind the player's current facing direction, then uses the same chase movement and contact-battle behavior as the aggressive chase attentive state while remaining in flicker mode.

Implementation shape:

- Replace `OW_WILD_SPAWNER_PHANTOM_STALK_HIDDEN_STEPS` with `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_DISTANCE`.
- Add a phantom teleport helper that tries 5 tiles behind the player first, then falls back to 4/3/2/1 if the farther tile is blocked or occupied.
- Validate teleport landing tiles with the existing map-object occupancy, metatile-blocked, surf, and headbutt-tile checks.
- Teleport with `MapObject_SetCurrentX/Y`, reset previous-tile and pending movement history, and update object init/previous/render tile state.
- Remove the old phantom behind-target direction builder; active phantom movement now keeps the default chase direction list already used by chase behavior.
- Keep `movementPhantomHidden` active through the whole attentive chase so movement commands can start random flicker windows.
- Treat active phantom contact with the player as battle-starting, like `agressiveChase`.
- Allow A-button battle targeting while a phantom is currently flickered visible, but still skip fully invisible phantoms.

Why this is new:

- Attempt 128 made the phantom walk invisibly toward a tile behind the player and then reveal after a fixed hidden-step count.
- Attempt 129 added flicker windows and follower-aware behind-target selection to that walking-behind-target approach.
- No previous attempt has teleported the phantom up to 5 tiles behind the player as the attentive-state entry action.
- No previous attempt has made phantom active movement reuse the chase attentive behavior while keeping flicker presentation.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_DISTANCE`
- `OverworldWildSpawns_TryGetPhantomTeleportTarget`
- `OverworldWildSpawns_TryTeleportPhantomBehindPlayer`
- `OverworldWildSpawns_MaybeStartPhantomStalkerVanish`
- `OverworldWildSpawns_TryStartBattle`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test228.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test228.nds` both exist at 176 MB.
- Verified active source defines `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_DISTANCE` as `5`.
- Verified the old phantom behind-target direction builder is removed from active source.
- Verified phantom active movement now keeps the default chase direction list, while active contact battle accepts both `CHASE_START_BATTLE` and `PHANTOM_STALK`.
- Verified hidden/flicker state no longer reveals after a fixed hidden-step count.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 131: Faster Phantom Destination Flicker And Battle Reveal

Idea:

Tune the phantom stalker presentation after the blink-and-chase pass. The first visible flicker should happen at the teleport destination before the ghost begins chasing, ordinary movement flickers should be shorter/faster, and a phantom should be fully visible before it starts a battle.

Implementation shape:

- Reduce `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_FRAMES` from `8` to `2` for faster normal movement flickers.
- Add `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES` as a separate short destination flash length.
- Add `OverworldWildSpawns_StartPhantomTeleportFlicker`.
- Call the teleport flicker helper after `MapObject_SetCurrentX/Y` and render-position updates, so the visible flash happens at the destination tile.
- Give the teleport flash a tiny movement cooldown before chase begins, preventing the first chase command from immediately overwriting the destination flicker.
- Explicitly call `OverworldWildSpawns_RevealPhantomStalker` from `OverworldWildSpawns_TryStartBattleForSlot` before pending battle setup.

Why this is new:

- Attempt 129 added random flicker windows only when hidden movement commands started.
- Attempt 130 teleported behind the player, but immediately hid after teleport and let the first chase command own the next flicker decision.
- No previous attempt has started a guaranteed flicker after the teleport destination is applied.
- No previous attempt has explicitly revealed phantoms at the central battle-start entry point.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES`
- `OverworldWildSpawns_StartPhantomTeleportFlicker`
- `OverworldWildSpawns_TryTeleportPhantomBehindPlayer`
- `OverworldWildSpawns_TryStartBattleForSlot`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test229.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test229.nds` both exist at 176 MB.
- Verified normal phantom flicker pulse length is now `2` frames.
- Verified teleport flicker uses `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES`.
- Verified teleport flicker starts after the map object's current/render position is updated to the destination.
- Verified the teleport path holds movement cooldown briefly so chase does not immediately overwrite the destination flicker.
- Verified `OverworldWildSpawns_TryStartBattleForSlot` reveals hidden phantoms before pending battle setup.

Runtime result:

- User reported that flicker was not working, and that it also did not appear to work in the previous iteration.

Learning:

- The short visible-window approach is not reliable enough visually, even with a guaranteed teleport-destination flash.
- Avoid treating "make the visible window shorter" as the fix; the problem needs a more explicit pulse/cadence or a different render toggle path.

### Attempt 132: Deterministic Phantom Flicker Pulse

Idea:

Replace the tiny one-shot visible windows with an explicit flicker pulse. A pulse starts visible, alternates visible/hidden every two frames, lasts long enough to see at the teleport destination, and also starts for every hidden movement command during the test build.

Implementation shape:

- Keep using `BIT_VANISH`, but stop interpreting `movementPhantomFlickerTimers` as "visible for all remaining frames".
- Add `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_PHASE_FRAMES` and `OverworldWildSpawns_ShouldShowPhantomFlicker`.
- Set normal hidden-movement pulses to `10` frames and teleport-destination pulses to `18` frames.
- Temporarily make the pulse chance `100%` so the behavior is testable and not dependent on random rolls.
- Call `OverworldWildSpawns_EnsureFrameMovementTask` when a normal or teleport pulse starts, so the visual timer is serviced even during cooldown or non-movement frames.

Why this is new:

- Attempt 129 used random visible windows during hidden movement.
- Attempt 131 made those visible windows shorter and added a guaranteed teleport-destination window.
- No previous attempt has alternated visible/hidden phases inside a single pulse or forced the frame task awake from pulse startup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_PHASE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_FLICKER_FRAMES`
- `OverworldWildSpawns_ShouldShowPhantomFlicker`
- `OverworldWildSpawns_ApplyPhantomHiddenVisual`
- `OverworldWildSpawns_UpdatePhantomFlicker`
- `OverworldWildSpawns_TryStartPhantomFlicker`
- `OverworldWildSpawns_StartPhantomTeleportFlicker`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test230.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test230.nds` both exist at 176 MB.
- Verified normal hidden-movement pulses now last `10` frames and teleport-destination pulses last `18` frames.
- Verified `OverworldWildSpawns_ShouldShowPhantomFlicker` alternates visible/hidden phases every `2` frames.
- Verified both normal and teleport flicker pulse startup paths call `OverworldWildSpawns_EnsureFrameMovementTask`.

Runtime result:

- User reported the flicker still did not work.

Learning:

- Alternating `BIT_VANISH` in a deterministic pulse still does not produce a visible flicker in runtime.
- Do not keep cycling `BIT_VANISH` timing, odds, or phase lengths as the primary solution.
- The likely missing piece is that clearing the vanish bit during active movement does not force the spawned special/follower-style object's visible render resource back into the draw path.

### Attempt 133: Refresh Phantom Sprite On Visible Flicker Phase

Idea:

Keep the hidden phases on the existing `BIT_VANISH` path, but when a flicker phase becomes visible, explicitly refresh the object's current overworld sprite tag with `ChangeMapObjSprite` before clearing `BIT_VANISH`. This tests whether the failed flicker is not the timer itself, but the renderer/resource side failing to re-enter the visible draw path from a hidden moving object.

Implementation shape:

- Add `movementPhantomFlickerVisible` per spawn slot so the visible-phase refresh runs once per visible phase, not every frame.
- Add `OverworldWildSpawns_GetSpawnSpriteIdForSlot` to recover the correct species/form sprite tag from the saved spawn metadata.
- Add `OverworldWildSpawns_RefreshPhantomVisibleSprite`, which calls `ChangeMapObjSprite(object, spriteId)` for the current spawn sprite.
- Update `OverworldWildSpawns_ApplyPhantomHiddenVisual` so a visible flicker phase refreshes the sprite and then clears `BIT_VANISH`; hidden phases still set `BIT_VANISH`.
- Reset the new visible-phase bookkeeping when phantoms reveal, enter hidden state, start a pulse, reset movement, or spawn.
- Tighten universal A-button targeting so a hidden phantom is targetable only during a currently visible flicker phase.

Why this is new:

- Attempts 129 through 132 only changed the `BIT_VANISH` timer/chance/cadence and frame-task wakeup.
- Earlier shiny work used `ChangeMapObjSprite` only during spawn-time shiny palette setup, not as an in-motion visible-phase refresh.
- No previous attempt has combined `ChangeMapObjSprite` with each visible flicker phase while keeping hidden phases on `BIT_VANISH`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `movementPhantomFlickerVisible`
- `OverworldWildSpawns_GetSpawnSpriteIdForSlot`
- `OverworldWildSpawns_RefreshPhantomVisibleSprite`
- `OverworldWildSpawns_ApplyPhantomHiddenVisual`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test231.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test231.nds` both exist at 176 MB.
- Verified `movementPhantomFlickerVisible` is reset on reveal, hidden-state entry, pulse start, movement reset, and spawn initialization.
- Verified visible flicker phases call `ChangeMapObjSprite` once when entering the phase, then clear `BIT_VANISH`.
- Verified hidden phases still set `BIT_VANISH`.
- Verified A-button targeting now skips hidden phantoms unless the current flicker timer phase is visible.

Runtime result:

- User reported two failures:
  - Flicker still did not work.
  - Leaving a route where Pokemon had spawned crashed the game.

Learning:

- Refreshing the hidden object with `ChangeMapObjSprite` during visible flicker phases still did not produce the desired visible flicker.
- The same sprite-refresh path is unsafe during route cleanup: `OverworldWildSpawns_RevealPhantomStalker` ran from generic movement reset/map-transition paths and could call `ChangeMapObjSprite` on an object whose map/render context was being torn down.
- Do not call `ChangeMapObjSprite` from phantom reveal/reset/flicker cleanup paths. Keep heavy sprite reloads at normal object creation/spawn-time only.

### Attempt 134: Phantom Flicker Apparition Object

Idea:

Stop trying to make the hidden moving object itself visible. Keep the real phantom hidden with `BIT_VANISH`, and show a short-lived separate special-field-object apparition at the phantom's current position during visible flicker phases. This should avoid the failed "clear vanish on the same object" render path and avoid `ChangeMapObjSprite` during route cleanup.

Implementation shape:

- Replace `movementPhantomFlickerVisible` with `movementPhantomFlickerObjects`, a per-slot temporary apparition object pointer.
- Add `OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START` for apparition object IDs.
- Add `OverworldWildSpawns_ClearPhantomFlickerObject`, which only calls `DeleteMapObject` when the current field context is still valid; route teardown just clears the pointer.
- Add `OverworldWildSpawns_EnsurePhantomFlickerObject`, which creates a temporary special field object using the saved species/form/shiny metadata, syncs it to the real phantom's current position, and leaves the real phantom hidden.
- Add `OverworldWildSpawns_SyncPhantomFlickerObject` to keep the apparition aligned with the real phantom while it exists.
- Add `OverworldWildSpawns_HidePhantomFlickerObject` so the apparition can persist for a full flicker pulse and use `BIT_VANISH` only on the temporary apparition during hidden phases.
- Update `OverworldWildSpawns_ApplyPhantomHiddenVisual` so visible flicker phases ensure/sync the apparition, hidden phases hide the existing apparition, the pulse end deletes it, and the real phantom stays vanished either way.
- Move `movementFieldSystem` clearing to after per-slot movement reset so normal in-map resets can delete a live apparition, while route transitions still fail the current-field guard before deleting.
- Make tile-occupancy checks ignore apparition object IDs so the visual clone does not block movement or spawn placement.
- Remove the Attempt 133 visible-phase `ChangeMapObjSprite` refresh from reveal/reset/flicker paths.

Why this is new:

- Attempts 129 through 132 toggled `BIT_VANISH` on the real phantom.
- Attempt 133 tried reloading the real phantom sprite when the real object should become visible.
- No previous attempt has used a separate temporary map object as a visible flicker apparition while the real phantom remains hidden.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_PHANTOM_FLICKER_OBJECT_ID_START`
- `movementPhantomFlickerObjects`
- `OverworldWildSpawns_ClearPhantomFlickerObject`
- `OverworldWildSpawns_EnsurePhantomFlickerObject`
- `OverworldWildSpawns_SyncPhantomFlickerObject`
- `OverworldWildSpawns_HidePhantomFlickerObject`
- `OverworldWildSpawns_IsPhantomFlickerObjectId`

Verification:

- `git diff --check` passed before and after build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test232.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test232.nds` both exist at 176 MB.
- Verified the old Attempt 133 source symbols `movementPhantomFlickerVisible`, `OverworldWildSpawns_GetSpawnSpriteIdForSlot`, and `OverworldWildSpawns_RefreshPhantomVisibleSprite` are gone from active source.
- Verified route cleanup no longer calls `ChangeMapObjSprite` from phantom reveal/reset/flicker cleanup paths.
- Verified the apparition object ID range is ignored by tile-occupancy checks.
- Verified a temporary apparition is kept alive across the whole flicker pulse instead of being recreated every visible phase.

Runtime result:

- User reported the flicker is now working, but the visible phases are a bit hard to follow.

Learning:

- The separate temporary apparition object solved the failed real-object `BIT_VANISH` flicker path.
- Expand the apparition approach; do not go back to toggling/reloading the real hidden object for flicker.
- The flicker cadence needs longer readable visible phases.

### Attempt 135: Phantom Teleport Alert Build-Up

Idea:

Keep the working apparition-object flicker from Attempt 134, but make it easier to read and move the teleport presentation into the alert state. When a phantom stalker spots the player, it now pauses with its alert bubble, enters a stand-still flicker charge that starts slowly and accelerates, teleports behind the player with a teleport sound, then briefly flickers at the arrival point before entering active stalking.

Implementation shape:

- Increase normal phantom flicker from `10` to `18` frames.
- Replace the old fixed `2`-frame alternating phase with `5` visible frames and `2` hidden frames for normal/arrival flicker.
- Add explicit phantom alert emote steps:
  - `OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PHANTOM_NOTICE`
  - `OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PHANTOM_CHARGE`
  - `OW_WILD_SPAWNER_SPOT_EMOTE_STEP_PHANTOM_ARRIVE`
- Add a `24`-frame notice pause, a `96`-frame accelerating charge, and a `36`-frame arrival flicker.
- Route `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK` through `OverworldWildSpawns_TryStartPhantomTeleportAlert` instead of the generic speech-alert path.
- Use `SEQ_SE_DP_TELE` for the teleport sound, loaded through `GF_Snd_LoadSeqEx` immediately when the teleport succeeds.
- Keep the real phantom hidden during the charge/arrival phases and reuse the Attempt 134 apparition object for the visible flicker.

Why this is new:

- Attempt 134 proved the separate apparition object works, but kept the teleport as an immediate active-state transition.
- No previous attempt has moved phantom teleport timing into the alert/emote state.
- No previous attempt has used an accelerating flicker cadence or a notice/charge/arrival sequence.
- This does not retry the failed real-object `BIT_VANISH` flicker or the unsafe `ChangeMapObjSprite` visible refresh.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_VISIBLE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_FLICKER_HIDDEN_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_NOTICE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_CHARGE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_ARRIVE_FRAMES`
- `OverworldWildSpawns_ShouldShowPhantomFlickerForSlot`
- `OverworldWildSpawns_TryStartPhantomTeleportAlert`
- `OverworldWildSpawns_TickPhantomTeleportAlert`
- `OverworldWildSpawns_PlayPhantomTeleportSE`

Verification:

- `git diff --check` passed before and after build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test233.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test233.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled successfully.

Runtime result:

- User reported Gengar is not visible at all during its attentive state.

Learning:

- The alert build-up can finish with the real phantom still hidden and the finite apparition pulse expired.
- A finite arrival/movement-start pulse is not enough for active stalking; attentive state needs a continuous flicker loop.
- Keep the alert build-up, but make active phantom stalking continuously drive the apparition visibility instead of relying on one-shot pulses.

### Attempt 136: Active Phantom 60 Percent Flicker Loop

Idea:

Keep the Attempt 135 alert teleport presentation, but make the attentive/active phantom stalking state constantly flicker with a 60% visible ratio. The active stalker should never drop into permanent invisibility after the arrival pulse ends.

Implementation shape:

- Add active-state flicker constants:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_VISIBLE_FRAMES = 3`
  - `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_HIDDEN_FRAMES = 2`
  - `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_FLICKER_FRAMES = 5`
- Add `OverworldWildSpawns_IsActivePhantomStalker` to identify `OW_WILD_SPAWNER_SPOT_STATE_ACTIVE` phantoms using the phantom-stalk attentive state.
- Add `OverworldWildSpawns_EnsureActivePhantomFlickerTimer`, which restarts the 5-frame active flicker loop whenever the active phantom timer reaches zero.
- Update `OverworldWildSpawns_ShouldShowPhantomFlickerForSlot` so active phantom stalking uses the 3-visible/2-hidden cadence.
- Update `OverworldWildSpawns_UpdatePhantomFlicker` so active phantom stalking refreshes its loop timer before applying the apparition visual.
- Update `OverworldWildSpawns_TryStartPhantomFlicker` so movement starts in active phantom state restart the active 5-frame loop instead of starting a finite normal pulse.

Why this is new:

- Attempt 134 created the working apparition object.
- Attempt 135 moved teleport into the alert state but still let active visibility depend on finite pulses.
- No previous attempt has made active phantom stalking run a persistent 60/40 apparition loop.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_VISIBLE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_HIDDEN_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_FLICKER_FRAMES`
- `OverworldWildSpawns_IsActivePhantomStalker`
- `OverworldWildSpawns_EnsureActivePhantomFlickerTimer`
- `OverworldWildSpawns_ShouldShowPhantomFlickerForSlot`
- `OverworldWildSpawns_UpdatePhantomFlicker`
- `OverworldWildSpawns_TryStartPhantomFlicker`

Verification:

- `git diff --check` passed before and after build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test234.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test234.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled successfully.

Runtime result:

- User reported Gengar is still completely invisible during attentive state.

Learning:

- A persistent 60/40 loop on the temporary apparition object is not enough during active stalking.
- The active stalking state still depends on the real object staying hidden after the teleport alert, and the apparition layer is not reliable as the active-state visible representation.
- Next attempt should make attentive stalking use the real map object again, while keeping the apparition object only for the teleport/hidden presentation.

### Attempt 137: Active Phantom Real-Object Flicker

Idea:

Keep the slow teleport build-up from Attempt 135 and the apparition object from Attempt 134 for hidden/teleport frames, but stop using the apparition as the active attentive-state representation. When the teleport alert finishes, reveal the real Gengar object, delete any temporary apparition, and drive a 3-visible/2-hidden flicker directly on the real object during attentive stalking.

Implementation shape:

- Add `OverworldWildSpawns_ShouldShowActivePhantomRealFlicker` so the active loop starts on a visible frame and then runs 3 visible frames followed by 2 hidden frames.
- Add `OverworldWildSpawns_StartActivePhantomRealFlicker`, called when the phantom teleport alert finishes:
  - delete the temporary apparition object;
  - clear `movementPhantomHidden`;
  - reset hidden-step state;
  - seed the active 5-frame flicker loop;
  - clear `BIT_VANISH` on the real object.
- Add `OverworldWildSpawns_UpdateActivePhantomRealFlicker`, serviced by the frame movement task before the hidden/apparition flicker path.
- Keep `OverworldWildSpawns_UpdatePhantomFlicker` for hidden teleport/arrival frames only.

Why this is new:

- Attempts 129-132 toggled `BIT_VANISH` while the phantom remained in the hidden path.
- Attempt 133 refreshed the sprite on the real object and caused unsafe route cleanup behavior.
- Attempts 134-136 used a separate apparition object for visible phantom frames.
- This attempt reveals the real object at the attentive-state boundary and flickers only that real object during active stalking, with no sprite refresh and no active apparition dependency.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_ShouldShowActivePhantomRealFlicker`
- `OverworldWildSpawns_StartActivePhantomRealFlicker`
- `OverworldWildSpawns_UpdateActivePhantomRealFlicker`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`
- `OverworldWildSpawns_FrameMovementTask`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test235.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test235.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User reported Gengar is still completely invisible in attentive state after the teleport.

Learning:

- Revealing the old real object and flickering `BIT_VANISH` directly during active stalking still does not restore post-teleport visibility.
- The problem is likely not just a stale `BIT_VANISH` bit. The teleport path hand-writes render `posVec[0/2]` from tile coordinates, while stock object creation owns the correct map-object render setup.
- Do not keep trying to revive the same hidden/teleported object with `BIT_VANISH` timing.

### Attempt 138: Recreate Phantom Object After Teleport

Idea:

Stop trying to make the old hidden/teleported real object visible again. At the moment the teleport alert enters attentive state, create a fresh special field object at the teleported tile with the same species/form/shiny/render params, delete the old hidden object, swap the spawn slot pointer to the fresh object, and keep that fresh object visible for this test checkpoint.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_REAL_FLICKER = 0` for this checkpoint so active stalking does not immediately hide the fresh object again.
- Add `OverworldWildSpawns_RecreatePhantomObjectForActiveState`:
  - validate the current field/map-object context;
  - read the old object's current tile after teleport;
  - create a fresh special field object through `CreateSpecialFieldObjectWithParams`;
  - apply the spawn slot's species/form/shiny params;
  - apply the resolved behavior range;
  - delete the old real object;
  - store the replacement in `state->spawns[slot].object`.
- Call the recreate helper from `OverworldWildSpawns_FinishPhantomTeleportAlert` before starting the active visible state.
- Keep `OverworldWildSpawns_UpdateActivePhantomRealFlicker` as an active-state visibility service, but with active real flicker disabled it only clears `BIT_VANISH`.

Why this is new:

- Attempts 129-133 tried to revive or refresh the same hidden real object.
- Attempts 134-136 used a separate temporary apparition object while the real object stayed hidden.
- Attempt 137 revealed the old real object at active-state entry and flickered that same old object.
- No previous attempt has replaced the actual spawn object with a fresh stock-created object at the teleport destination before active stalking starts.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ACTIVE_REAL_FLICKER`
- `OverworldWildSpawns_RecreatePhantomObjectForActiveState`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`
- `OverworldWildSpawns_UpdateActivePhantomRealFlicker`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test236.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test236.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User moved on to teleport presentation tuning instead of reporting the post-teleport active invisibility as the current blocker.

Learning:

- Replacing the active phantom with a fresh stock-created object is a workable baseline for post-teleport visibility.
- The next problem is no longer just "make Gengar visible"; it is communicating the teleport clearly during the alert/charge before active stalking begins.

### Attempt 139: Origin/Destination Teleport Flicker And Face Player

Idea:

Make the teleport charge flicker between two visible positions instead of flickering between visible and invisible. When the phantom starts its teleport alert, turn the real object toward the player-facing direction already selected by alert detection. At charge start, record the origin tile and precompute the destination behind the player. During the charge/arrival, keep the real object hidden and alternate temporary apparition objects at the origin and destination tiles so the teleport reads as Gengar blinking between "here" and "there".

Implementation shape:

- Add per-slot teleport visual state:
  - `movementPhantomTeleportFlickerObjects`;
  - `movementPhantomTeleportOriginX/Y`;
  - `movementPhantomTeleportTargetX/Y`;
  - `movementPhantomTeleportHasTarget`.
- Add `OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START` so the destination apparition has its own object ID range, and update `OverworldWildSpawns_IsPhantomFlickerObjectId` so both apparition ranges are ignored by occupancy checks.
- Refactor apparition creation into `OverworldWildSpawns_EnsurePhantomFlickerObjectAtPosition`, then use it for:
  - the origin apparition;
  - the target apparition;
  - the existing one-position hidden flicker path.
- Add teleport target bookkeeping helpers:
  - `OverworldWildSpawns_ClearPhantomTeleportTarget`;
  - `OverworldWildSpawns_PreparePhantomTeleportTarget`.
- Update `OverworldWildSpawns_StartPhantomTeleportCharge` so it precomputes the teleport destination before the flicker begins.
- Update `OverworldWildSpawns_TryTeleportPhantomBehindPlayer` so it uses the precomputed target if still valid, or recalculates if something moved into the destination during the charge.
- Update `OverworldWildSpawns_ApplyPhantomHiddenVisual` to call `OverworldWildSpawns_ApplyPhantomTeleportPositionVisual` during phantom charge/arrival.
- Add `OverworldWildSpawns_SetObjectFacing` and call it from `OverworldWildSpawns_TryStartPhantomTeleportAlert` before the bubble appears.
- Reset the new teleport visual state on reveal, slot reset, and fresh spawn initialization.

Why this is new:

- Attempts 129-133 toggled visibility or refreshed the old real object.
- Attempts 134-136 used one temporary apparition object at the real object's current position.
- Attempt 137 tried real-object active flicker after teleport.
- Attempt 138 recreated the active object after teleport.
- No previous attempt alternated two visible temporary apparition objects at the origin and the destination during the teleport charge itself.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_PHANTOM_TELEPORT_FLICKER_OBJECT_ID_START`
- `OverworldWildSpawns_SetObjectFacing`
- `OverworldWildSpawns_ClearPhantomTeleportTarget`
- `OverworldWildSpawns_PreparePhantomTeleportTarget`
- `OverworldWildSpawns_EnsurePhantomFlickerObjectAtPosition`
- `OverworldWildSpawns_ApplyPhantomTeleportPositionVisual`
- `OverworldWildSpawns_StartPhantomTeleportCharge`
- `OverworldWildSpawns_TryTeleportPhantomBehindPlayer`
- `OverworldWildSpawns_TryStartPhantomTeleportAlert`

Verification:

- `git diff --check` passed before and after the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test237.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test237.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User reported the origin/destination flicker does not feel good for the standard teleport alert.
- User also reported that this visual idea does seem promising as a movement type where the phantom teleports instead of walking.

Learning:

- Do not keep the two-position origin/destination flicker on the standard alert teleport.
- The visual is worth reusing as active stalking locomotion, but it needs to be about twice as fast and isolated to attentive-state movement.

### Attempt 140: Active Phantom Teleport-Step Movement

Idea:

Revert the origin/destination flicker out of the standard phantom alert teleport, but reuse the same "old tile / new tile" presentation as the phantom stalker's active movement type. While active stalking, the behavior resolver still picks chase directions as before, but the phantom teleports one tile to the chosen valid destination instead of starting a stock walk command. The real object moves to the target immediately for behavior continuity, then stays hidden while temporary apparitions flicker between origin and destination for a short transition.

Implementation shape:

- Keep `OverworldWildSpawns_SetObjectFacing` from Attempt 139 so the standard alert still turns toward the player before the speech bubble.
- Stop precomputing the standard alert destination in `OverworldWildSpawns_StartPhantomTeleportCharge`.
- Restore `OverworldWildSpawns_TryTeleportPhantomBehindPlayer` to choosing its destination at the actual teleport moment and not setting the two-position visual target state.
- Gate `OverworldWildSpawns_ApplyPhantomTeleportPositionVisual` behind `OverworldWildSpawns_IsActivePhantomTeleportMove` so two-position flicker only runs during active attentive movement.
- Add active teleport movement timing:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_FRAMES`, half of the older teleport flicker window;
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_PHASE_FRAMES`, a short origin/target alternation phase.
- Add `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand`:
  - uses the existing active stalking direction list;
  - requires a valid, unoccupied target tile;
  - records origin/target;
  - moves the real object to target;
  - hides the real object;
  - starts the frame-task-owned teleport-step visual.
- Add `OverworldWildSpawns_TickPhantomTeleportMovementCommand` so the active movement slot completes after the visual timer and then runs the normal finished-movement handler for history, stamina, tired-state, and battle settle behavior.
- Update the frame task so active teleport-step visuals own their timer and are not also decremented by the generic phantom hidden-flicker updater.

Why this is new:

- Attempt 139 used origin/destination flicker only for the standard teleport alert/arrival presentation.
- Previous active stalking attempts used walking movement, active real-object visibility, or hidden apparition flicker, but did not replace active stalk movement with a frame-task-owned teleport step.
- This attempt keeps the standard teleport presentation reverted while moving the two-position effect into a separate locomotion path.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_PHASE_FRAMES`
- `OverworldWildSpawns_SetObjectTile`
- `OverworldWildSpawns_IsActivePhantomTeleportMove`
- `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`
- `OverworldWildSpawns_FrameMovementTask`

Verification:

- `git diff --check` passed before and after the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test238.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test238.nds` both exist at 176 MB.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User asked to change active stalking movement away from the one-tile chase teleport. The desired behavior is now to teleport toward the front of the player, with up to 5 tiles of movement per blink, and to avoid passive proximity battle starts.

Learning:

- The one-tile chase-direction teleport is not the intended fantasy for the stalking profile. Active stalking should treat "front of the player" as the locomotion goal, while keeping the standard alert teleport separate.

### Attempt 141: Front-Of-Player Phantom Teleport Movement

Idea:

Change active phantom stalking movement so it tries to teleport to the tile in front of the player instead of teleporting one tile along the existing chase direction list. Each attentive-state blink can move up to 5 tiles. If the exact front tile is farther than 5 tiles from the ghost, the ghost should blink up to 5 tiles toward that front target rather than stalling. Also remove phantom stalk from the automatic proximity battle path: it should battle only through the universal A-button interaction or by the player actively pressing into the occupied facing tile.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_DISTANCE` as the active blink distance limit.
- Add front-target helpers:
  - `OverworldWildSpawns_TryGetPhantomFrontTeleportTarget`;
  - `OverworldWildSpawns_TryUsePhantomFrontTeleportCandidate`;
  - `OverworldWildSpawns_ClampDeltaToStep`;
  - `OverworldWildSpawns_GetOppositeDirection`;
  - `OverworldWildSpawns_GetFacingTowardTile`.
- Make `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand` ignore the normal chase/flee direction list for phantom stalkers and instead:
  - prefer valid tiles on the ray in front of the player's current facing;
  - fall back to a clamped 5-tile blink toward the closest front tile;
  - record the movement distance and origin/target tiles for the existing active teleport visual;
  - face the ghost toward the player after the blink target is selected.
- Add `OverworldWildSpawns_TryStartBattleFromDirectionalBump`, which starts a battle when the player is pressing the D-pad direction matching their current facing and a spawned Pokemon occupies that facing tile.
- Keep `OverworldWildSpawns_TryStartBattleFromAButton` unchanged as the universal intentional interaction.
- Remove `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK` from the generic `OverworldWildSpawns_TryStartBattle` automatic touching loop, leaving only aggressive chase there.

Why this is new:

- Attempt 128 targeted behind-player stalking with ordinary movement.
- Attempt 130 teleported behind the player on alert and then reused chase/contact behavior.
- Attempt 140 made active stalking teleport one tile along the existing chase direction list.
- No previous attempt has made the active stalk locomotion explicitly target the front of the player, nor separated phantom battles into A-button/directional-bump interactions while removing passive phantom proximity battles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_MOVE_DISTANCE`
- `OverworldWildSpawns_TryGetPhantomFrontTeleportTarget`
- `OverworldWildSpawns_TryUsePhantomFrontTeleportCandidate`
- `OverworldWildSpawns_TryStartPhantomTeleportMovementCommand`
- `OverworldWildSpawns_TryStartBattleFromDirectionalBump`
- `OverworldWildSpawns_TryStartBattle`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test239.nds`.
- Verified `test.nds` and `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test239.nds` both exist at 176 MB.
- `git diff --check` passed after updating the log.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User asked for a 1-second wait after each active teleport movement before the next phantom stalk movement can begin.

Learning:

- The front-of-player movement target still needs pacing: without an explicit post-teleport cooldown, the frame task can immediately enter another movement decision after the teleport visual finishes.

### Attempt 142: One-Second Pause After Active Phantom Teleport

Idea:

After an active phantom stalk teleport movement finishes, wait one second before allowing the next attentive teleport movement. The pause should apply after the teleport-step visual completes, not before or during the visual, and should not override tired-state transitions.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES` set to `60`.
- In `OverworldWildSpawns_TickPhantomTeleportMovementCommand`, after the active teleport clears its movement-in-progress bit and runs `OverworldWildSpawns_HandleFinishedMovementCommand`, set `state->movementCooldowns[slot]` to the new cooldown only if:
  - the spawn is still active;
  - the spot state is still `OW_WILD_SPAWNER_SPOT_STATE_ACTIVE`;
  - the resolved attentive state is still `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.

Why this is new:

- Earlier cooldown work controlled generic movement cadence, tired cooldowns, chill wandering pauses, and alert-arrival flicker timing.
- Attempt 131 briefly held movement after the alert teleport destination flicker, but that was before active chase and was part of the old behind-player alert presentation.
- No previous attempt has added a post-completion cooldown specifically after each active attentive-state phantom teleport movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test240.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User asked to add the same 1-second wait to the alert-arrival phase as well.

Learning:

- The post-active-teleport pause covers repeated active movement, but the first movement after the alert arrival still needs the same pacing pause so the arrival can breathe before stalking resumes.

### Attempt 143: One-Second Pause After Phantom Alert Arrival

Idea:

Use the same 60-frame pause after the phantom alert teleport arrival finishes and the Pokemon enters active stalking. This should make the arrival read before the first attentive teleport movement begins.

Implementation shape:

- Reuse `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`.
- In `OverworldWildSpawns_FinishPhantomTeleportAlert`, replace the immediate `OW_WILD_SPAWNER_MOVEMENT_DECISION_COOLDOWN` reset with the 60-frame phantom teleport cooldown.
- This applies whenever the phantom alert resolves into active stalking, including the normal arrival path and the fallback path where the alert teleport cannot find a destination.

Why this is new:

- Attempt 131 had a short movement hold after a now-reworked destination flicker.
- Attempt 142 added the explicit 60-frame pause after each active attentive-state teleport movement.
- No previous attempt has applied the same explicit 60-frame pacing pause at the current `OverworldWildSpawns_FinishPhantomTeleportAlert` transition.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`
- `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test241.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User reported the phantom is invisible during the new pause and asked to make it visible. User also asked for the alert-state teleport to be twice as fast.

Learning:

- The 60-frame pause is useful for pacing, but it must explicitly force the phantom into a visible state at pause start. Simply delaying the next movement decision is not enough if hidden/teleport visual state is still active.

### Attempt 144: Visible Teleport Pauses And Faster Alert Teleport

Idea:

Make the phantom visible during both 1-second teleport pauses, and make the alert-state teleport presentation twice as fast. The pause should no longer leave hidden/apparition/teleport target state active while the Pokemon is waiting.

Implementation shape:

- Halve alert teleport timing:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_CHARGE_FRAMES` from `96` to `48`;
  - `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_ARRIVE_FRAMES` from `36` to `18`.
- Keep `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_NOTICE_FRAMES` unchanged so the alert bubble still has readable time before the teleport begins.
- Add `OverworldWildSpawns_StartPhantomVisibleCooldown`, which:
  - calls `OverworldWildSpawns_RevealPhantomStalker`;
  - clears hidden/flicker/teleport target state through the reveal path;
  - clears `BIT_VANISH` on the real object;
  - sets the 60-frame phantom cooldown;
  - keeps the frame task awake.
- Use the visible-cooldown helper after:
  - active phantom teleport movement finishes and the Pokemon remains in active phantom stalking;
  - phantom alert arrival finishes and the Pokemon enters active phantom stalking.
- Preserve the active teleport's reveal before post-movement state handling so tired-state transitions do not inherit a hidden real object.

Why this is new:

- Attempts 134-138 established that active visibility is reliable only after using the recreated real object and clearing hidden state, but did not connect that to the new cooldown pauses.
- Attempt 142 added a post-active-teleport cooldown but did not centralize visibility cleanup at pause start.
- Attempt 143 added an alert-arrival cooldown but did not force visibility during that wait.
- No previous attempt has paired the explicit 60-frame pause with a shared "make the real phantom visible now" helper.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_CHARGE_FRAMES`
- `OW_WILD_SPAWNER_PHANTOM_STALK_TELEPORT_ALERT_ARRIVE_FRAMES`
- `OverworldWildSpawns_StartPhantomVisibleCooldown`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`
- `OverworldWildSpawns_FinishPhantomTeleportAlert`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test242.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.
- Verified both `test.nds` and the Delta copy exist and are 176 MB.

Runtime result:

- User reported a regression: all spawned Pokemon now start battles when the player gets close/presses into them. That was not intended.

Learning:

- The likely culprit is the directional-bump battle helper added during phantom stalking work: `OverworldWildSpawns_TryStartBattleFromDirectionalBump` loops every active spawn, even though that interaction was meant for the phantom stalker profile only.

### Attempt 145: Restrict Directional Bump Battles To Phantom Stalkers

Idea:

Keep the universal A-button battle path for all spawned Pokemon, keep automatic contact battles for `agressiveChase`, but restrict directional bump battles to active phantom stalkers only. This should remove unintended "all Pokemon start battle when close/pressed into" behavior without losing the intentional Gengar-style "player runs into the ghost" interaction.

Implementation shape:

- In `OverworldWildSpawns_TryStartBattleFromDirectionalBump`, check each slot's behavior profile before allowing the battle:
  - `movementSpotStates[i]` must be `OW_WILD_SPAWNER_SPOT_STATE_ACTIVE`;
  - `profile.attentiveState` must be `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_PHANTOM_STALK`.
- Skip fully hidden phantom stalkers unless their flicker window is currently visible.
- Leave `OverworldWildSpawns_TryStartBattleFromAButton` unchanged, so pressing A on any visible spawned Pokemon still starts a battle.
- Leave `OverworldWildSpawns_TryStartBattle` unchanged, so only active `agressiveChase` Pokemon auto-start battles on contact.

Why this is new:

- Attempt 141 added directional bump battles while removing phantom stalkers from the generic proximity-battle loop, but the new directional-bump loop was accidentally broad and applied to every spawn.
- No previous attempt has profile-gated `OverworldWildSpawns_TryStartBattleFromDirectionalBump` back to the phantom stalker behavior that motivated it.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryStartBattleFromDirectionalBump`
- `OverworldWildSpawns_TryStartBattleFromAButton`
- `OverworldWildSpawns_TryStartBattle`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test243.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- No battle-trigger runtime result was reported yet. User reported a separate phantom-stalk issue: the visible-pause fix is working after the alert-state teleport, but not after attentive-state teleport movement.

Learning:

- The profile guard should still stand for directional bump battles, but attentive-state teleport visibility needs its own follow-up.
- Alert arrival works because `OverworldWildSpawns_FinishPhantomTeleportAlert` recreates the real object before starting the visible pause.
- Active attentive teleport still only revealed the same object that was hidden for the teleport visual, so it can fall back into the old unreliable "clear vanish on the just-hidden object" path.

### Attempt 146: Recreate Real Phantom After Attentive Teleport

Idea:

Use the proven alert-arrival handoff for active attentive teleport movement too: when an active phantom teleport finishes, recreate the real Pokemon object at the teleport destination before running finished-movement state handling and before starting the 1-second visible cooldown.

Implementation shape:

- In `OverworldWildSpawns_TickPhantomTeleportMovementCommand`, when the active teleport visual timer reaches zero:
  - call `OverworldWildSpawns_RecreatePhantomObjectForActiveState(state, slot, object)`;
  - then clear the movement-in-progress bit;
  - then run `OverworldWildSpawns_HandleFinishedMovementCommand`;
  - then, if the Pokemon remains an active phantom stalker, start `OverworldWildSpawns_StartPhantomVisibleCooldown`.
- This mirrors the successful alert-arrival path where `OverworldWildSpawns_FinishPhantomTeleportAlert` recreates the real object before the visible pause.
- It also means tired-state transitions after the final stamina-spending teleport see a fresh visible object rather than the object that was just hidden for teleport movement.

Why this is new:

- Attempt 138 recreated the real phantom only when the alert teleport entered attentive state.
- Attempt 144 shared the visible cooldown helper between alert-arrival and active-teleport pauses, but the active-teleport path still only cleared `BIT_VANISH` on the same hidden object.
- No previous attempt has recreated the real object after each active attentive-state teleport movement before starting the post-teleport pause.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TickPhantomTeleportMovementCommand`
- `OverworldWildSpawns_RecreatePhantomObjectForActiveState`
- `OverworldWildSpawns_StartPhantomVisibleCooldown`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test244.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User requested a behavior update: bumping into a phantom stalker should only start battle during the visible pause, not during other visible flicker/teleport frames.

Learning:

- The visible pause should be treated as a specific interaction window, distinct from alert-charge flicker, alert-arrival flicker, and active teleport position flicker.

### Attempt 147: Limit Phantom Bump Battles To Visible Pause

Idea:

Make directional bump battles for phantom stalkers trigger only during the explicit post-teleport visible pause created by `OverworldWildSpawns_StartPhantomVisibleCooldown`. Visible flicker frames during alert/arrival/active teleport should communicate movement, but should not be battle-start windows.

Implementation shape:

- Add `OverworldWildSpawns_IsPhantomVisiblePause`, which requires:
  - the slot is an active phantom stalker;
  - `movementPhantomHidden[slot]` is false;
  - no spawner-owned movement command is in progress;
  - `movementCooldowns[slot]` is nonzero;
  - `movementCooldowns[slot]` is within `OW_WILD_SPAWNER_PHANTOM_STALK_POST_TELEPORT_COOLDOWN_FRAMES`.
- Update `OverworldWildSpawns_TryStartBattleFromDirectionalBump` to use only this helper.
- Remove the previous hidden/flicker-visible exception from directional bump battles, so flicker visibility no longer implies bump-battle eligibility.
- Leave the universal A-button path unchanged.

Why this is new:

- Attempt 141 added directional bump battles for phantom stalking.
- Attempt 145 restricted directional bump battles to active phantom stalkers, but still allowed them during visible flicker frames.
- Attempt 146 made attentive teleport pauses visible, but did not narrow the battle window.
- No previous attempt has treated the post-teleport visible cooldown as the only directional bump battle window.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_IsPhantomVisiblePause`
- `OverworldWildSpawns_TryStartBattleFromDirectionalBump`
- `OverworldWildSpawns_StartPhantomVisibleCooldown`

Verification:

- `git diff --check` passed before the build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test245.nds`.
- Verified the overworld wild spawns overlay compiled and linked successfully.

Runtime result:

- User requested the phantom stalker's normal/chill movement become `wanderTeleportation`: each chill step should teleport a random distance from 3-6 tiles using the same flicker movement as attentive-state teleport, followed by a 1-second visible pause.

Learning:

- The explicit visible-pause window is now useful beyond battle gating: chill phantom teleport movement can share the same pause contract.

### Attempt 148: Phantom Chill Wander Teleportation

Idea:

Make phantom stalkers use a new `wanderTeleportation` chill movement instead of ordinary walking. While chill/default, each movement decision should choose a random cardinal direction and a random landing distance from 3-6 tiles, use the same origin/target flicker teleport visual as attentive-state phantom movement, then recreate/reveal the real object and pause visibly for 1 second.

Implementation shape:

- Add `OW_WILD_BEHAVIOR_CHILL_STATE_WANDER_TELEPORT` and assign it to the phantom stalker behavior-class override.
- Add wander teleport distance constants:
  - `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MIN_DISTANCE = 3`;
  - `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MAX_DISTANCE = 6`.
- Add `movementPhantomVisiblePause[slot]` so the post-teleport pause is an explicit interaction window rather than inferred from a cooldown value.
- Generalize the phantom teleport visual runner so it works when the phantom stalker is either:
  - active/attentive; or
  - chill/default.
- Add `OverworldWildSpawns_TryGetPhantomWanderTeleportTarget`, which:
  - randomizes direction order;
  - randomizes distance order from 3-6;
  - accepts only valid, unoccupied, non-blocked, non-surf, non-headbutt landing tiles.
- Add `OverworldWildSpawns_TryStartPhantomWanderTeleportMovementCommand` and route chill `WANDER_TELEPORT` decisions through it.
- Keep active attentive phantom movement targeting the front of the player unchanged.
- On teleport completion, recreate the real phantom object and call `OverworldWildSpawns_StartPhantomVisibleCooldown` for both active and chill phantom teleport movement.
- Keep directional bump battles restricted to the explicit visible-pause flag.

Why this is new:

- Attempts 140-147 changed alert and attentive-state phantom teleport behavior, but chill/default phantom movement still used ordinary chill walking.
- Attempt 147 made visible pause explicit for battle gating, but did not use it as a chill movement cadence.
- No previous attempt has added a phantom-only chill movement mode that randomly teleports 3-6 tiles and then uses the same post-teleport visible pause.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_BEHAVIOR_CHILL_STATE_WANDER_TELEPORT`
- `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MIN_DISTANCE`
- `OW_WILD_SPAWNER_PHANTOM_STALK_WANDER_TELEPORT_MAX_DISTANCE`
- `movementPhantomVisiblePause`
- `OverworldWildSpawns_TryStartPhantomWanderTeleportMovementCommand`
- `OverworldWildSpawns_TryGetPhantomWanderTeleportTarget`

Verification:

- `git diff --check` passed.
- `./docker-makerom.cmd` produced a fresh `test.nds` at `2026-06-06 19:57`.
- The Docker wrapper did not return to the post-build copy helper after the ROM was created, so the stale wrapper session was closed and the repo helper was run directly.
- `./scripts/copy-test-nds-to-delta.sh` copied the ROM to Delta as `test246.nds`.

Runtime result:

- User reported that Gengar still simply wanders normally, so the chill/default `wanderTeleportation` behavior is not reaching runtime Gengar in `test246.nds`.

Learning:

- The phantom class override table contains `OW_WILD_BEHAVIOR_CHILL_STATE_WANDER_TELEPORT`, and Gengar is in `OW_WILD_BEHAVIOR_GROUP_GHOST`.
- The failure is more likely behavior-class resolution/caching on the active slot than the table definition itself.

### Attempt 149: Recompute Active Spawn Behavior Class

Idea:

Treat `movementBehaviorClasses[slot]` as a cache instead of the source of truth. If an active Gengar slot has a stale/default behavior class, `OverworldWildSpawns_GetBehaviorProfile` can keep resolving the default wander profile even though the species should resolve to `OW_WILD_BEHAVIOR_CLASS_PHANTOM_STALKER`.

Implementation shape:

- Change `OverworldWildSpawns_GetBehaviorProfile` so it always recomputes `behaviorClass` from the current behavior context.
- For active spawns, write the recomputed class back to `state->movementBehaviorClasses[slot]`.
- Keep the existing spawn-time behavior class assignment unchanged.

Why this is new:

- Attempt 148 added the `WANDER_TELEPORT` chill state and movement implementation, but still trusted the active slot's stored class byte when resolving behavior each tick.
- No previous attempt has repaired stale active-slot behavior classes by recomputing them from species/level/terrain/shiny.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_GetBehaviorProfile`
- `movementBehaviorClasses`

Verification:

- `git diff --check` passed.
- Built with `./docker-makerom.cmd`.
- Build succeeded and copied the ROM to Delta as `test247.nds`.
- Existing warnings remained diagnostic/noise warnings, including unused diagnostic symbols and unused `OverworldWildSpawns_Clear`.

Runtime result:

- User reported that Gengar now uses the phantom behavior, but sometimes the game freezes on the black battle-transition screen when entering combat with Gengar.

Learning:

- Recomputing the behavior class appears to have made Gengar use the intended phantom profile, but battle entry can now race against phantom teleport/flicker state.

### Attempt 150: Stable Phantom Battle Entry Gate

Idea:

Do not let a phantom stalker battle start while Gengar is in a teleport/flicker/hidden/intermediate alert state. The older battle-start fix only revealed hidden phantoms before queuing battle; it did not reject battles that were initiated during unsafe phantom movement frames, especially through the universal A-button path.

Implementation shape:

- Add `OverworldWildSpawns_IsSlotStableForBattle`.
- For non-phantom Pokemon, keep existing battle behavior.
- For phantom stalkers, require all of the following before battle can be scheduled:
  - the real object is not hidden;
  - no phantom flicker timer is active;
  - no phantom teleport target is active;
  - no spawner-owned movement command is in progress;
  - the real object has no active single movement command;
  - the slot is not in a phantom alert/charge/arrival emote step.
- Add `OverworldWildSpawns_PrepareSlotForBattle`, which reveals the stable phantom and clears any remaining phantom helper objects before pending battle setup.
- Harden `Script_QueueOverworldWildBattle` so if `OverworldWildSpawns_PopPendingBattle` fails, it jumps to a small `releaseall/end` script instead of falling through to the Rattata fallback battle.

Why this is new:

- Attempt 134 revealed hidden phantoms before battle setup, but did not block battle during unstable teleport/flicker states.
- Attempt 147 limited directional-bump battles to the visible pause, but the universal A-button path could still attempt phantom battles while flicker frames were visible or movement state was active.
- No previous attempt has centralized a phantom-specific "stable real object only" gate before queuing the battle script.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/script_new_cmds.c`
- `OverworldWildSpawns_IsSlotStableForBattle`
- `OverworldWildSpawns_PrepareSlotForBattle`
- `Script_QueueOverworldWildBattle`

Verification:

- `git diff --check` passed.
- `./docker-makerom.cmd` produced a fresh `test.nds` at `2026-06-07 12:11`.
- The Docker wrapper did not return to the post-build copy helper after the ROM was created, so the stale wrapper session was closed and the repo helper was run directly.
- `./scripts/copy-test-nds-to-delta.sh` copied the ROM to Delta as `test249.nds`.

Runtime result:

- User clarified that A-button interaction should still work during visible Gengar flicker frames, but should be made stable instead of disabled.

Learning:

- Blocking all flicker-state phantom battle starts is too conservative for intended feel.
- A-button battles need a separate path from bump/contact battles: pressing A on a visible apparition should materialize that visible tile into the real object before battle setup.

### Attempt 151: Materialize Visible Phantom Flicker For A-Button Battles

Idea:

Allow A-button battles during visible Gengar flicker frames by converting the currently visible apparition tile into the real, stable Gengar object before queuing battle. This keeps A responsive without carrying hidden movement state, teleport targets, or helper objects into the black battle transition.

Implementation shape:

- Add `OverworldWildSpawns_TryGetPhantomBattleVisibleTile`.
  - Stable visible phantom: returns the real object's current tile.
  - Teleport-position flicker: returns the currently displayed origin or target tile.
  - Normal/alert flicker: returns the real object's tile only on visible flicker frames.
  - Hidden invisible frames remain non-interactable.
- Add `OverworldWildSpawns_IsPlayerFacingTile` so the A-button path can target a visible apparition tile directly.
- Add `OverworldWildSpawns_StabilizePhantomForBattleAtTile`.
  - Clears single movement/in-progress movement.
  - Deletes phantom flicker helper objects.
  - Moves the real object to the visible apparition tile.
  - Clears `BIT_VANISH`, hidden/flicker timers, teleport target state, and phantom alert emote state.
- Update `OverworldWildSpawns_TryStartBattleFromAButton`:
  - If a phantom visible tile is facing the player, stabilize it first, then call `OverworldWildSpawns_TryStartBattleForSlot`.
  - Keep hidden invisible frames ignored.
  - Keep normal non-phantom A-button battles unchanged.

Why this is new:

- Attempt 150 blocked unsafe phantom battle starts during flicker/teleport state.
- Earlier attempts revealed hidden phantoms before battle, but did not move the real object to the currently visible flicker tile or support A-button targeting of the apparition itself.
- No previous attempt has stabilized a visible phantom helper frame into the real object before battle setup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OverworldWildSpawns_TryGetPhantomBattleVisibleTile`
- `OverworldWildSpawns_IsPlayerFacingTile`
- `OverworldWildSpawns_StabilizePhantomForBattleAtTile`
- `OverworldWildSpawns_TryStartBattleFromAButton`

Verification:

- `git diff --check` passes.
- Clean rebuild was required after an earlier interrupted build removed generated headers; removed generated `build/` and `base/`, then rebuilt with `./docker-makerom.cmd`.
- Build succeeded and copied the ROM to Delta as `test250.nds`.

Runtime result:

- Pending user test on hardware/emulator.

Learning:

- Code/build side supports the intended stable A-button path: visible phantom frames are materialized into the real object before the battle script is queued, while invisible frames remain ignored.

### Attempt 152: Disable Phantom Stalk Alert-State Teleport

Idea:

Try Phantom Stalk without the alert-state teleport. Gengar should still spot the player and enter its attentive state, but the initial alert should be the normal speech-bubble beat instead of the slow flicker/teleport/arrival sequence.

Implementation shape:

- Add `OW_WILD_SPAWNER_PHANTOM_STALK_ALERT_TELEPORT_ENABLED`, currently set to `0`.
- When the toggle is off, do not route phantom stalkers through `OverworldWildSpawns_TryStartPhantomTeleportAlert`.
- Let phantom stalkers use the generic speech alert path, then enter active state through `OverworldWildSpawns_EnterActiveStateFromGenericAlert`.
- For phantom stalkers leaving a generic alert, call the same stable active-entry helper used after the old alert teleport: reveal/recreate the real object, start active-state real flicker handling, and apply the visible cooldown.
- Keep chill/attentive teleport movement unchanged.

Why this is new:

- Earlier phantom attempts refined the alert teleport, active teleport movement, flicker timing, and battle stability around teleport/flicker frames.
- No previous attempt has disabled only the alert-state teleport while preserving Phantom Stalk's teleport-style movement in chill/attentive states.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PHANTOM_STALK_ALERT_TELEPORT_ENABLED`
- `OverworldWildSpawns_EnterActiveStateFromGenericAlert`
- `OverworldWildSpawns_TryStartSpotEmote`

Verification:

- `git diff --check` passed.
- `./docker-makerom.cmd` built successfully and copied the ROM to Delta as `test251.nds`.
- After wrapping the disabled alert-teleport starter in `#if OW_WILD_SPAWNER_PHANTOM_STALK_ALERT_TELEPORT_ENABLED`, `./docker-makerom.cmd` built successfully again and copied the clean ROM to Delta as `test252.nds`.

Runtime result:

- Pending user test on `test252.nds`.

Learning:

- Build-side result is stable. This ROM isolates the feel of removing only Phantom Stalk's alert-state teleport while preserving later teleport movement.

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
