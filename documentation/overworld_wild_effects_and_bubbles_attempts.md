# Effects, Bubbles, Smoke, And Sounds

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Tracks non-movement presentation: spot hops, tired bubbles, Onix smoke, step sounds, and crash sounds.
- Direct follower bubble creator worked; bubble ids were mapped, with water droplet chosen for tired.
- Onix smoke required the correct flag context around the stock effect helper; several adjacent helpers did nothing or left trails.
- User liked the `ov01_021FE66C` visual for shiny Pokemon; keep it as a promising shiny presentation candidate even though it was not the headbutt leaf effect.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 9 | 9 | Disable Spawner Step Actions After Map-State Refresh |
| 13 | 13 | Read-Only UpdateMapState Diagnostic |
| 14 | 14 | UpdateMapState Map Writes Without Clear |
| 15 | 15 | Read Spawn State Without Writing It |
| 18 | 18 | Re-enable Map-State Writes After LONG_CALL Fix |
| 19 | 19 | Re-enable Stale-Slot Cleanup Only |
| 20 | 20 | Re-enable Distance Despawn Only |
| 21 | 21 | Re-enable Touch-Battle Detection Only |
| 22 | 22 | Re-enable Refill And Spawn Only |
| 23 | 23 | Restore Ambient Cry With Stock Movement |
| 24 | 24 | Spawner-Driven Movement Param Tick |
| 25 | 25 | Spawner-Driven Coordinate Read And Direction Calculation |
| 39 | 39 | Movement Speed Levels 1-6 |
| 45 | 45 | Remove Redundant Speed 6 And Add Spot Emote |
| 46 | 46 | Short Independent Spot Range |
| 47 | 47 | Use Jump-Site Movement Command For Spot Emote |
| 48 | 48 | Manual PosVec Height Bob For Spot Emote |
| 49 | 49 | Use WaitJumpSite Movement Command |
| 50 | 50 | LockDir Jump2 Smoke Release Sequence |
| 51 | 51 | LockDir JumpSite Smoke Release Sequence |
| 52 | 52 | Partner Pokemon JumpSite Wrapper |
| 53 | 53 | Three-Speed Scale And Speed-3 Double Hop |
| 54 | 54 | Hop Cry, Tired Cooldown, And Chill Wander |
| 55 | 55 | Tired WaitJumpSite Then Stat-Fell Sound |
| 56 | 56 | Tired Follower Emotion Bubble Helper |
| 57 | 57 | Direct Follower Bubble Effect Creator |
| 58 | 58 | Silent Direct Tired Bubble |
| 59 | 59 | Tired Bubble Id Probe Cycle |
| 60 | 60 | Skip Known Heart And Smiley Bubble Ids |
| 61 | 61 | Name Known Bubble Ids And Skip Angry |
| 62 | 62 | Use Water Droplet Tired Bubble |
| 63 | 63 | Behavior Profile Resolver |
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
| 77 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 78 | 237 | Allow Two-Tile Final Tree-Top Landings In Mankey Path Search |
| 79 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 80 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 82 | 231 | Revert Shared Row Lift And Keep Direct Fallback Only |
| 83 | 226 | One Row Above Archive Mankey Tree-Top Target |
| 84 | 227 | Restore Archive MinY Tree-Top Logic After Too-High Row |
| 85 | 228 | Sparse Archive Tree-Top Row Lift |
| 89 | 224 | Mankey Tree-Top Late Map-Object Redraw Effect |
| 90 | 225 | Mankey Tree-Top Effect-Owned Marker Canary |
| 91 | 214 | Bias Forced Verifier Ahead Of Player |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 96 | 259 | Boundary-Derived Headbutt Tree-Top Locator |
| 97 | 242 | Pair Tree-Top Candidates And Derive Top Row From Archive Bottom |
| 98 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 100 | 213 | Score Forced Verifier By Resolved Perch |
| 106 | 201 | Guaranteed Forced Headbutt Mankey Spawn |
| 108 | 203 | Lower Tree-Top Test Tile And Preserve Forced Idle Visibility |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 114 | 228 | Mankey Tree-Top Synced Visual Proxy |
| 116 | 236 | Mankey Tree-Top Effect-Layer Bubble Probe |
| 117 | 237 | Cache Mankey Tree-Top Archive Predicate |
| 118 | 238 | Gate Mankey Bubble Probe On Final Tree-Top Landing |
| 119 | 239 | Align Mankey Tree-Top Settled Rows With Target Rows |
| 120 | 240 | Strict Top-Row Mankey Target Set With Broad X Candidates |
| 121 | 241 | Pair-Derived Mankey Tree-Top X Footprints |
| 125 | 245 | Coordinate-Latched Mankey Tree-Top Settlement |
| 127 | 247 | Strict-Only Mankey Tree-Top Final Targets |
| 129 | 249 | Target Two Tiles Above Headbutt Archive Row |
| 130 | 250 | Follower-Sprite Tree-Top Proxy Probe |
| 132 | 252 | Generic Field Effect Probe For Tree-Top Mankey |
| 133 | 253 | Down-First Mankey Tree-Top Target Selection |
| 135 | 255 | Snap Final Canopy Landing After Partner Restore |
| 136 | 256 | Skip Final Mankey Tree-Top Partner Restore |
| 137 | 257 | Re-enable Tree-Top Anchored Effect Probe After Movement Fix |
| 138 | 258 | Late-Draw Mankey Through Field-Effect Render Callback |
| 142 | 230 | Mankey 2x6 Headbutt Tree Top-Row Targeting |
| 143 | 231 | Prefer Nearest Direct Mankey Tree-Top Jump |
| 145 | 67 | Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram |
| 146 | 68 | Tune Onix Ram Start, Range, Crash State, And Feedback |
| 147 | 69 | Use Site Walk Commands And Scripted Crash Feedback For Onix Ram |
| 148 | 70 | Restore Normal Ram Movement And Make Alertness A Facing Line |
| 149 | 71 | Keep Normal Ram Walking But Borrow Site Visual Parameter |
| 150 | 72 | Direct Stock Ground-Dust Effect Without Step Sound |
| 151 | 73 | Run WaitJumpSite After Each Onix Ram Step |
| 152 | 74 | Direct Boulder Step Effect Helper During Normal Ram Movement |
| 153 | 75 | Fixed Run-Style Boulder Effect Id |
| 154 | 76 | Direct WaitJumpSite Smoke Launcher During Ram Movement |
| 155 | 77 | Try Adjacent Overlay Effect Constructor `ov01_02200040` |
| 156 | 78 | Try Map-Object Anchored Effect Helper `ov01_02200730` |
| 157 | 79 | Try Short-Lived Map-Object Effect Helper `ov01_021FF74C` |
| 158 | 80 | Try Alternate Stock Ground Effect Helper `ov01_021FD684` |
| 159 | 81 | Add WaitJumpSite Flag Context Around `ov01_022000DC` |
| 160 | 82 | Use HGSS Push Sound For Onix Ram Steps |
| 161 | 83 | Try Paired HGSS Push Sound `SEQ_SE_GS_PUSH03` |
| 162 | 84 | Load Push Sequence Before Playing It |
| 163 | 85 | Load Push Sound With `NNS_SND_ARC_LOAD_ALL` |
| 164 | 86 | Try Field Rock Sound `SEQ_SE_GS_IWAOTOSHI02` |
| 165 | 87 | Promote `aggressive_ram` Behavior And Strengthen Crash Feedback |
| 166 | 88 | Use Field Wall-Hit Sound And Shake The Crashed Overworld Object |
| 167 | 89 | Non-Locking Object Shake And `SEQ_SE_DP_GASHIN` Crash Thud |
| 168 | 90 | Non-Locking Object Shake And HGSS Gondola Wall-Hit Sound |
| 169 | 91 | Sound-Only `SEQ_SE_GS_IWA_TRAP` Crash Feedback |
| 170 | 92 | Sound-Only `SEQ_SE_GS_IWAOTOSHI01` Crash Feedback |
| 171 | 93 | Restore Decent Crash Sound And Shorten Speech-Only Alert |
| 172 | 94 | C-Side Ram Crash Object Wobble |
| 173 | 95 | Direct Camera Shake Work Driven By SysTask |
| 174 | 96 | Stronger Ram Crash Object Wobble And Shorter Speech Alert |
| 175 | 97 | Aggressive Ram Rest-Only Tired State |
| 176 | 98 | Restore Smaller Ram Crash Wobble Offset |
| 177 | 99 | Player Wall-Hit Ram Crash Sound |
| 178 | 100 | Ram Crash-Only Automatic Battle Trigger |
| 179 | 101 | Follower Object-ID Fallback For Ram Crash Battles |
| 181 | 103 | Behavior-Gated Ledge Far Jump |
| 184 | 106 | Aipom-Only Playful Chase Pass |
| 189 | 111 | Revert Playful Attentive Speed Rhythm |
| 197 | 119 | Eight-Way Orbit Neighbor Filter |
| 198 | 120 | Playful Orbit Hop Every Five Neighbor Steps |
| 199 | 121 | Penalize Playful Orbit Moves Away Instead of Rejecting |
| 200 | 122 | Randomized Playful Orbit Hop Expression |
| 201 | 123 | Pause Playful Hop Timer Outside Orbit |
| 202 | 124 | Score Playful Ledge Jumps By Landing Tile |
| 203 | 125 | Include Moving Target Trail For Playful Scoring |
| 205 | 127 | Double Playful Movement Range |
| 213 | 135 | Phantom Teleport Alert Build-Up |
| 217 | 139 | Origin/Destination Teleport Flicker And Face Player |
| 218 | 140 | Active Phantom Teleport-Step Movement |
| 222 | 144 | Visible Teleport Pauses And Faster Alert Teleport |
| 230 | 152 | Disable Phantom Stalk Alert-State Teleport |
| 231 | 153 | Mankey Canopy Hopper Headbutt-Tree Profile |
| 232 | 154 | Canopy Hopper Attentive Ambush Target |
| 233 | 155 | Canopy Hopper Tired Return-To-Tree Case |
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
| 264 | 216 | Remove Forced Mankey Canopy Tests And Restore Land Mankey |
| 265 | 217 | Mankey Chill Jump To Two Tiles Above Headbutt Tree |
| 266 | 218 | Mankey Multi-Jump Pathfinding To Tree-Top Target |
| 267 | 219 | Mankey Lands On Headbutt Tree Top Row |
| 268 | 220 | Mankey Tree-Top Render Height Lift |
| 269 | 221 | Mankey Tree-Top Priority Flag Probe |
| 270 | 222 | Mankey Failed Tree-Path Backoff And Target Grid |
| 272 | 232 | Mankey Low Land Row Tree-Top Correction |
| 274 | 235 | Direct Two-Tile Mankey Tree-Top Final Hop |
| 275 | 236 | Use Prepared Internal Jump For Two-Tile Mankey Final Target |
| 276 | 237 | Revert Two-Tile Mankey Canopy-Hop Relaxation |
| 278 | 239 | Accept Single-Column Headbutt Tree-Top Archive Entries |
| 279 | 240 | Add Obscured Vertical Tree-Top Stack Rows |
| 280 | 241 | Filter Generated Tree-Top Rows By Blocked Canopy Surface |

## Original Attempt Sections

### Attempt 9: Disable Spawner Step Actions After Map-State Refresh

Idea:

Keep map-state refresh alive but skip every action after it in `OverworldWildSpawns_OverlayOnPlayerStep`:

- no stale-slot dropping
- no distance despawn
- no touch battle checks
- no ambient cry
- no refill/spawn attempt

Why this is new:

- Earlier attempts focused on movement descriptor wiring, callback behavior, and fresh object movement IDs.
- No earlier attempt isolated the spawner's player-step pipeline after a successful save load.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` should be `1`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should return `FALSE` immediately after `OverworldWildSpawns_UpdateMapState` succeeds.
- The rest of the step actions should remain compiled but unreachable behind the diagnostic switch.

Verification:

- Built as `test104.nds`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Disassembly of `OverworldWildSpawns_OverlayOnPlayerStep` shows it reaches `OverworldWildSpawns_UpdateMapState` behavior and then returns `FALSE`; calls to `OverworldWildSpawns_DropStaleSlots`, `OverworldWildSpawns_DespawnFarMons`, `OverworldWildSpawns_TryStartBattle`, `OverworldWildSpawns_TryPlayAmbientCry`, and `OverworldWildSpawns_TryRefill` are not present in the active step path.

Runtime result:

- User reported the game still crashes.

Learning:

- Disabling the overlay's downstream step actions did not stop the one-step crash.
- The crash is now narrowed to either the ARM9 `OverworldWildSpawns_OnPlayerStep` wrapper/overlay load/map-state refresh, or code running independently of that hook.

Do not repeat:

- Do not keep toggling individual overlay step actions until the outer wrapper hook has been ruled in or out.

### Attempt 13: Read-Only UpdateMapState Diagnostic

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` call `OverworldWildSpawns_UpdateMapState`, but make `OverworldWildSpawns_UpdateMapState` only:

- read `fieldSystem->mapObjectMan`
- read `mapObjectMan->objects`
- store those observed pointers to volatile diagnostic globals so the reads are not optimized away
- run `OverworldWildSpawns_IsEnabledMap(fieldSystem)`
- return before clearing spawn state, writing map state, or publishing the movement field system

Why this is new:

- Attempt 12 returned before `OverworldWildSpawns_UpdateMapState`.
- Attempt 9 ran the full map-state refresh and crashed.
- This attempt separates read-only pointer/map checks from state-clearing side effects.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY` should be `1`.
- `OverworldWildSpawns_UpdateMapState` should return before `OverworldWildSpawns_Clear` and before `OverworldWildCustomMovement_SetFieldSystem`.
- Movement slot `47` should remain stock no-op.

Runtime result:

- Built as `test108.nds`.
- User reported no crash.

Learning:

- Calling `OverworldWildSpawns_UpdateMapState` is safe when it only performs read-only map-object-manager observation and enabled-map detection.
- The crash is likely caused by side effects after those reads, especially `OverworldWildSpawns_Clear(state, FALSE)` or state field writes.

Do not repeat:

- Do not keep testing read-only map-state diagnostics; they have been ruled safe.

### Attempt 14: UpdateMapState Map Writes Without Clear

Idea:

Let `OverworldWildSpawns_UpdateMapState` run past read-only checks and update only:

- `state->mapId`
- `state->mapObjectMan`
- `state->mapObjects`
- `OverworldWildCustomMovement_SetFieldSystem(fieldSystem)`, which is currently compiled as a no-op

Keep `OverworldWildSpawns_OverlayOnPlayerStep` returning immediately after update-map-state, so no spawn/refill/battle work can run. Skip `OverworldWildSpawns_Clear(state, FALSE)` on both enabled-map and disabled-map transitions.

Why this is new:

- Attempt 13 returned before any `OverworldWildSpawnState` writes.
- Attempt 9 ran full map-state refresh and crashed.
- This attempt tests map-state pointer/id mutation without the slot clear loop and without `OverworldWildSpawns_ResetAmbientCryCooldown`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_READ_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` should be `1`.
- `OverworldWildSpawns_UpdateMapState` should write map state fields but should not call `OverworldWildSpawns_Clear`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should still return before downstream spawner work.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test109.nds`.
- Disassembly shows the active overlay step path writes `state->mapId`, `state->mapObjectMan`, and `state->mapObjects`, calls `OverworldWildCustomMovement_SetFieldSystem`, and returns before downstream spawner work.
- The active path does not call `OverworldWildSpawns_Clear`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported a crash.

Learning:

- State-free update-map-state reads were safe in `test108.nds`, but update-map-state with state comparison/writes crashes in `test109.nds`.
- The crash is not caused by `OverworldWildSpawns_Clear`, refill, battle checks, ambient cries, or custom movement callbacks in this build, because all of those were still unreachable.
- The next boundary is read-only `OverworldWildSpawnState` access versus mutating that state.

Do not repeat:

- Do not retest map-state writes bundled with `OverworldWildCustomMovement_SetFieldSystem`; split state reads, state writes, and the setter separately.

### Attempt 15: Read Spawn State Without Writing It

Idea:

Let `OverworldWildSpawns_UpdateMapState` run the same read-only field-system and map eligibility path as `test108.nds`, but also read these state fields into diagnostics:

- `state->mapId`
- `state->mapObjectMan`
- `state->mapObjects`

Return before any state write, before `OverworldWildSpawns_Clear`, and before `OverworldWildCustomMovement_SetFieldSystem`.

Why this is new:

- Attempt 13 did not touch `state`.
- Attempt 14 touched and wrote `state` fields, then crashed.
- This attempt isolates whether simply reading the ARM9/field-extension state pointer from overlay 149 is safe.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY` should be `1`.
- `OverworldWildSpawns_UpdateMapState` should read state fields into volatile globals.
- The active update path should not write `state`, should not call `OverworldWildSpawns_Clear`, and should not call `OverworldWildCustomMovement_SetFieldSystem`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should still return before downstream spawner work.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test110.nds`.
- Disassembly shows the compiler narrowed the active overlay step path to only read `state->mapId`, store it to the volatile diagnostic integer, and return `FALSE`.
- The active path does not write `state`, does not call `OverworldWildSpawns_Clear`, does not call `OverworldWildCustomMovement_SetFieldSystem`, and does not run downstream spawner work.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Adjusted meaning:

- This ROM is now an even narrower diagnostic than the source-level intent: it tests whether reading one scalar field, `state->mapId`, from the overlay is safe.
- It does not test state pointer fields, map eligibility, or the field-system pointer reads because those side effects optimized away.

Runtime result:

- User reported no crash.

Learning:

- Reading one scalar field, `state->mapId`, from overlay 149 is safe.
- The crash in `test109.nds` is not caused by simply passing or reading the `OverworldWildSpawnState *state` pointer.
- The next split should isolate the no-op movement field-system setter before blaming state writes.

Do not repeat:

- Do not repeat state-read-only probes unless they force additional specific fields to survive compiler optimization.

### Attempt 18: Re-enable Map-State Writes After LONG_CALL Fix

Idea:

Let `OverworldWildSpawns_UpdateMapState` perform its normal `state->mapId`, `state->mapObjectMan`, and `state->mapObjects` writes using the corrected `LONG_CALL` setter path, but keep the overlay step diagnostic returning before spawn/despawn/battle work.

Why this is new:

- Attempt 14/`test109.nds` wrote state and crashed, but that build still included the broken plain setter call.
- Attempt 17/`test112.nds` proved the corrected setter-only call is stable.
- No previous build has tested state writes with the corrected Thumb-safe setter call.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` should remain `1`.
- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` should remain `1`.
- The active overlay step path should call `OverworldWildSpawns_UpdateMapState`, then return `FALSE` before stale-slot dropping, despawn checks, touch battle, ambient cry, or refill/spawn.
- The active update path should write map-state fields when map context changes, call `OverworldWildCustomMovement_SetFieldSystem` through the Thumb-safe long-call path, and avoid `OverworldWildSpawns_Clear`.

Verification:

- Built as `test113.nds`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` is `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SKIP_CLEAR` remains `1`.
- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` remains `1`.
- Disassembly shows the active overlay step path writes `state->mapId`, `state->mapObjectMan`, and `state->mapObjects` when the map context changes.
- Disassembly shows the setter call still uses the Thumb-safe `0x023D97F5` target via `bx r3`.
- Disassembly shows the active overlay step returns `FALSE` before stale-slot dropping, distance despawn, touch battle, ambient cry, or refill/spawn.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended state-write-only probe.
- Runtime result confirms map-state writes are stable with the corrected setter path.

Expand:

- Re-enable `OverworldWildSpawns_DropStaleSlots` only, while returning before distance despawn, touch battle, ambient cry, and refill/spawn.

### Attempt 19: Re-enable Stale-Slot Cleanup Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run `OverworldWildSpawns_DropStaleSlots` after the now-stable map-state update, then immediately return `FALSE`.

Why this is new:

- Attempt 18/`test113.nds` returned before every downstream step action.
- Earlier crashy probes either stopped before stale-slot cleanup or bundled it with more downstream spawner logic.
- No previous build has isolated stale-slot validation and clearing after the `LONG_CALL` setter fix.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` should be `1`.
- The active overlay step path should run map-state update, run `OverworldWildSpawns_DropStaleSlots`, then return `FALSE`.
- The active overlay step path should not run distance despawn, touch battle, ambient cry, or refill/spawn.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test114.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` is `1`.
- Disassembly shows the active overlay step path runs map-state update, then the stale-slot validation/clear loop, then returns `FALSE`.
- Disassembly shows no distance-despawn, touch-battle, ambient-cry, or refill/spawn path after stale-slot cleanup in the active step path.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended stale-slot-only probe.
- Runtime result confirms stale-slot validation and clearing are stable.

Expand:

- Re-enable `OverworldWildSpawns_DespawnFarMons` only, while returning before touch battle, ambient cry, and refill/spawn.

### Attempt 20: Re-enable Distance Despawn Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run map-state update, stale-slot cleanup, and `OverworldWildSpawns_DespawnFarMons`, then immediately return `FALSE`.

Why this is new:

- Attempt 19/`test114.nds` returned before distance despawn.
- Earlier crashy probes bundled distance despawn with touch battle, ambient cry, and refill/spawn.
- No previous build has isolated distance despawn after the `LONG_CALL` setter fix and stable stale-slot cleanup.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` should be `1`.
- The active overlay step path should run map-state update, stale-slot cleanup, distance despawn, then return `FALSE`.
- The active overlay step path should not run touch battle, ambient cry, or refill/spawn.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test115.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_DROP_STALE_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` is `1`.
- Disassembly shows the active overlay step path runs map-state update, stale-slot cleanup, distance despawn, then returns `FALSE`.
- Disassembly shows no touch-battle, ambient-cry, or refill/spawn path after distance despawn in the active step path.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended distance-despawn-only probe.
- Runtime result confirms distance despawn is stable in the current empty/no-spawn state.

Expand:

- Re-enable `OverworldWildSpawns_TryStartBattle` only, while returning before ambient cry and refill/spawn.

### Attempt 21: Re-enable Touch-Battle Detection Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run map-state update, stale-slot cleanup, distance despawn, and `OverworldWildSpawns_TryStartBattle`, then immediately return `FALSE` if no battle was started.

Why this is new:

- Attempt 20/`test115.nds` returned before touch-battle detection.
- Earlier crashy probes bundled touch-battle detection with ambient cry and refill/spawn.
- No previous build has isolated touch-battle detection after the `LONG_CALL` setter fix and stable stale/despawn paths.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` should be `1`.
- The active overlay step path should run map-state update, stale-slot cleanup, distance despawn, and touch-battle detection.
- If `OverworldWildSpawns_TryStartBattle` returns `TRUE`, the active path should still return `TRUE`.
- If no battle is started, the active path should return `FALSE` before ambient cry or refill/spawn.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test116.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_DESPAWN_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` is `1`.
- Disassembly shows the active overlay step path runs map-state update, stale-slot cleanup, distance despawn, and touch-battle detection.
- Disassembly shows the battle-start path can set pending battle state, call `EventSet_Script`, and return `TRUE`.
- Disassembly shows the no-battle path returns `FALSE` before ambient cry or refill/spawn.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence shows this is the intended touch-battle-only probe.
- Runtime result confirms touch-battle detection is stable in the current empty/no-spawn state.

Expand:

- Re-enable `OverworldWildSpawns_TryRefill` to spawn Pokemon, while skipping ambient cry for now.

### Attempt 22: Re-enable Refill And Spawn Only

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run map-state update, stale-slot cleanup, distance despawn, touch-battle detection, and refill/spawn. Skip ambient cry so this build specifically tests Pokemon object creation and spawn state.

Why this is new:

- Attempt 21/`test116.nds` returned before refill/spawn.
- Earlier crashy probes bundled refill/spawn with unresolved setter/state issues.
- No previous build has isolated refill/spawn after the `LONG_CALL` setter fix and stable stale/despawn/battle paths.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` should be `1`.
- The active overlay step path should run map-state update, stale-slot cleanup, distance despawn, touch-battle detection, and `OverworldWildSpawns_TryRefill`.
- The active overlay step path should not run `OverworldWildSpawns_TryPlayAmbientCry`.
- Fresh spawns should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test117.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_BATTLE_ONLY` is `0`.
- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` is `1`.
- Disassembly shows the active overlay step path reaches `OverworldWildSpawns_SpawnOne` from refill/spawn call sites.
- Source-level diagnostic gating keeps `OverworldWildSpawns_TryPlayAmbientCry` skipped for this build.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test117.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- Refill/spawn is stable again with stock movement `3` and ambient cry skipped.
- This rules out spawn position selection, encounter rolling, `CreateSpecialFieldObjectWithParams`, Pokemon render params, shiny setup, and post-create spawn state writes as immediate crash causes for this checkpoint.

Expand:

- Restore `OverworldWildSpawns_TryPlayAmbientCry` while keeping stock movement `3` spawns, so the full stock spawner pipeline is tested before custom movement work resumes.

### Attempt 23: Restore Ambient Cry With Stock Movement

Idea:

Let `OverworldWildSpawns_OverlayOnPlayerStep` run the full stock spawner pipeline again: map-state update, stale-slot cleanup, distance despawn, touch-battle detection, ambient cry, and refill/spawn. Fresh spawns still use stock movement `3`; custom movement slot `47` remains no-op.

Why this is new:

- Attempt 22/`test117.nds` skipped ambient cry and did not crash.
- Earlier crashy probes bundled ambient cry with unresolved setter/state issues and custom movement uncertainty.
- No previous build has restored ambient cry after the `LONG_CALL` setter fix and stable stale/despawn/battle/refill paths.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` should be `0`.
- The active overlay step path should run `OverworldWildSpawns_TryPlayAmbientCry` before `OverworldWildSpawns_TryRefill`.
- Fresh spawns should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test118.nds`.
- `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` is `0`.
- Disassembly shows the active overlay step path reaches `PlayCry` at `0x02006219`.
- Disassembly shows the active overlay step path still reaches `OverworldWildSpawns_SpawnOne` from refill/spawn call sites after the ambient-cry section.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test118.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- The full stock spawner pipeline is stable again: stale-slot cleanup, distance despawn, touch-battle detection, ambient cry, and refill/spawn all run with stock movement `3`.
- This rules out ambient cry as the current crash source and gives a clean baseline before custom movement probes resume.

Expand:

- Avoid re-pointing slot `47` to the overlay-resident descriptor because Attempts 5 and 6 already showed that crashes even with no-op callbacks.
- Start custom movement again from the stable spawner step loop by ticking `MapObject` params only.

### Attempt 24: Spawner-Driven Movement Param Tick

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Add a spawner-step diagnostic that iterates active spawned Pokemon and only reads/writes their movement cooldown param with `MapObject_GetParam` and `MapObject_SetParam`.

Why this is new:

- Attempts 5 and 6 tested slot-47 overlay callbacks and crashed even when callbacks were no-op.
- Earlier movement attempts bundled param access with coordinate reads, scratch writes, movement command helpers, or slot-47 descriptor wiring.
- No previous build has tested `MapObject_GetParam`/`MapObject_SetParam` on active spawned Pokemon from the stable overlay-149 spawner step path while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- The active overlay step path should call `OverworldWildSpawns_TickMovementParams` after touch-battle detection and before ambient cry/refill.
- `OverworldWildSpawns_TickMovementParams` should only call `MapObject_GetParam` and `MapObject_SetParam` for active spawned objects.
- The active movement probe should not use `object->fsys`, global `FieldSystem *`, coordinate reads, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test119.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- Disassembly shows the active overlay path contains `MapObject_GetParam` at `0x0205F2F5` and `MapObject_SetParam` at `0x0205F2D1`.
- Source verification shows `OverworldWildSpawns_TickMovementParams` only reads/writes `OW_WILD_MOVEMENT_PARAM_COOLDOWN` for active spawned objects.
- The new movement probe does not use `object->fsys`, global `FieldSystem *`, coordinate reads, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test119.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- `MapObject_GetParam` and `MapObject_SetParam` are safe to call on active spawned Pokemon from the stable overlay-149 spawner step path.
- This keeps the next probe focused on coordinate reads and direction calculation.

Expand:

- Add player/object coordinate reads and chase/flee direction calculation from the spawner step loop.
- Still avoid slot-47 callbacks, movement command helpers, blocked-direction checks, scratch writes, and single-movement flags.

### Attempt 25: Spawner-Driven Coordinate Read And Direction Calculation

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Extend the spawner-step movement diagnostic to read active spawned object coordinates, player coordinates, behavior param, compute chase/flee deltas, choose a preferred direction, and store the result into volatile diagnostics.

Why this is new:

- Attempt 24/`test119.nds` only tested spawner-driven movement param get/set and did not crash.
- Earlier movement attempts bundled coordinate reads with slot-47 descriptor callbacks, scratch writes, blocked-direction checks, and movement command helpers.
- No previous build has isolated coordinate reads and direction calculation from the stable overlay-149 spawner step path while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- The active overlay step path should still call `OverworldWildSpawns_TickMovementParams` after touch-battle detection and before ambient cry/refill.
- The movement probe should call `MapObject_GetCurrentX`, `MapObject_GetCurrentY`, `GetPlayerXCoord`, `GetPlayerYCoord`, and `MapObject_GetParam` for active spawned objects, then store calculated values in volatile diagnostics.
- The active movement probe should not use slot-47 callbacks, `object->fsys`, global movement `FieldSystem *`, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test120.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` is `1`.
- Source verification shows `OverworldWildSpawns_TickMovementParams` calls `MapObject_GetCurrentX`, `MapObject_GetCurrentY`, `GetPlayerXCoord`, `GetPlayerYCoord`, and `MapObject_GetParam`, then stores calculated values in volatile diagnostics.
- Disassembly target scan shows `MapObject_GetCurrentX` at `0x0205F915`, `MapObject_GetCurrentY` at `0x0205F935`, `GetPlayerXCoord` at `0x0205C67D`, `GetPlayerYCoord` at `0x0205C689`, `MapObject_GetParam` at `0x0205F2F5`, and `MapObject_SetParam` at `0x0205F2D1`.
- Disassembly target scan did not find `MapObject_StartMovementCommand` at `0x0206217D`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, or `MapObject_SetSingleMovementActive` at `0x0205F631` in the overlay object.
- Source verification shows the active spawner movement probe does not use slot-47 callbacks, `object->fsys`, global movement `FieldSystem *`, blocked-direction checks, scratch writes, single-movement flags, or movement command helpers.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test120.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- Position lookup and chase/flee direction calculation are safe for spawned Pokemon from the stable overlay-149 spawner step path.
- This keeps the next probe focused on non-walking movement-command setup.

Expand:

- Add a spawner-driven look command on cooldown reset.
- Still avoid walking commands, blocked-direction checks, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

### Attempt 39: Movement Speed Levels 1-6

Idea:

Replace the one-off Pidgey fast-walk special case with an explicit overworld-wild movement speed scale. Sentret stays at speed `1`, Pidgey stays at speed `2`, and speeds `3`, `4`, `5`, and `6` are available for future species tuning by mapping them to stock movement command families.

Why this is new:

- Attempt 38 proved only a hardcoded Pidgey `0x0C` command path against the default `0x08` command path.
- No previous attempt exposed a reusable per-species speed parameter or reserved speed levels above `2`.
- This still uses stock movement command families rather than the previously crash-prone custom movement descriptor path, burst updates, or direct coordinate changes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test136.nds` and copied to Delta.
- `git diff --check` passed.
- Verified Sentret maps to speed `1`, Pidgey maps to speed `2`, and every other species defaults to speed `1`.
- Verified speed levels `3`, `4`, `5`, and `6` are selectable through the same speed-to-command helper for future species tuning.
- Local ARM9 movement command table already shows valid stock direction families for speed levels `1` through `6`: `0x08`, `0x0C`, `0x10`, `0x14`, `0x18`, and `0x1C`.

Runtime result:

- User reported this did nothing visible and also clarified this was not the desired effect.
- The requested effect is an actual screen shake, not wobbling the crashed object or adding another non-screen visual.

Learning:

- Manual X/Z `posVec` wobble is not a useful substitute for screen shake.
- Remove this code and do not retry object-wobble crash feedback unless the requested effect changes.
- The next attempt should trace or call the underlying camera/screen shake routine directly instead of scheduling field scripts or offsetting the object.

### Attempt 45: Remove Redundant Speed 6 And Add Spot Emote

Idea:

Remove the redundant logical speed `6`, because it was identical to speed `5` after high speeds were capped to the fastest confirmed safe walk command. Add a first spot-emote state so a spawned Pokemon starts chill, detects the player entering spot range, hops in place with a jump sound, waits briefly, and only then enters the active chase/flee movement path.

Why this is new:

- Attempt 39 added logical speed levels through `6`; Attempts 41 and 43 later made the high levels aliases to the same safe command family.
- No previous attempt has removed the duplicate highest speed level while preserving Pidgey's fastest tested behavior.
- No previous attempt has added per-slot spotted/emoting state or tried a same-tile map-object hop before chase/flee.
- This avoids the old risky paths: no custom movement descriptor is re-enabled, no coordinate writes are used, and the chase/flee walk command path remains the existing spawner-owned path.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test142.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified speed `6` was removed from `OverworldWildSpawns_GetMovementWalkCommandForSpeed`.
- Verified Pidgey now uses logical speed `5`, which still maps to the fastest confirmed safe walk command family through the speed `3` alias.
- Verified `OverworldWildSpawnState` now stores per-slot `movementSpotStates` and `movementEmoteTimers`.
- Verified a chill spawn only starts the spot emote when the player is within `OW_WILD_SPAWNER_SPOT_RANGE` and a chase/flee direction exists.
- Verified the emote path sets `BIT_JUMP_START`, plays `SEQ_SE_GS_UFO_JUMP`, waits `OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES`, then allows the existing spawner-owned chase/flee command path to run.

Runtime result:

- User requested making the spot/emote trigger range distinct from chase range and much shorter.

Learning:

- Spot range should be a separate behavior parameter from chase/leash range. A Pokemon can notice the player nearby, emote, and then use a larger chase/flee range after it becomes active.

### Attempt 46: Short Independent Spot Range

Idea:

Keep chase/leash range at `8`, but stop deriving `OW_WILD_SPAWNER_SPOT_RANGE` from `OW_WILD_SPAWNER_MOVEMENT_RANGE`. Set spot range to `3` so the hop/sound emote only triggers when the player is close, while the already-spotted Pokemon can still chase/flee over the larger movement range.

Why this is new:

- Attempt 45 added spotting, but defined `OW_WILD_SPAWNER_SPOT_RANGE` as an alias of `OW_WILD_SPAWNER_MOVEMENT_RANGE`.
- No previous attempt has made spot/emote distance shorter than the movement/chase range.
- This changes only the spot threshold; it does not touch the proven spawner-owned movement command path, emote state machine, jump flag, or sound call.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test143.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified `OW_WILD_SPAWNER_MOVEMENT_RANGE` remains `8`.
- Verified `OW_WILD_SPAWNER_SPOT_RANGE` is now a distinct literal `3`.
- Verified `OverworldWildSpawns_IsPlayerInSpotRange` still uses the spot range only for the chill-to-emote transition.

Runtime result:

- User reported the spot -> chase logic works, but neither the hop nor the sound happens.

Learning:

- The chill/emote/active state machine and short spot range are working.
- Setting `BIT_JUMP_START` on these spawned idle objects is not enough to produce a visible same-tile hop.
- `PlaySE(SEQ_SE_GS_UFO_JUMP)` from this spot-emote path did not produce an audible sound in runtime.
- Do not retry the same `BIT_JUMP_START` + `SEQ_SE_GS_UFO_JUMP` presentation path without new evidence.

### Attempt 47: Use Jump-Site Movement Command For Spot Emote

Idea:

Replace the raw `BIT_JUMP_START` spot presentation with an actual single movement command from the script movement table: `JumpUpSite`/`JumpDownSite`/`JumpLeftSite`/`JumpRightSite` (`0x30`-`0x33`). Drive that command through the already stable spawner-owned frame updater, then transition to chase/flee when the command finishes or the emote timer expires. Also swap the test sound from `SEQ_SE_GS_UFO_JUMP` to common `SEQ_SE_DP_KON` so the next test can distinguish "wrong sound asset" from "sound call path broken."

Why this is new:

- Attempt 45 and Attempt 46 used only `BIT_JUMP_START` plus `SEQ_SE_GS_UFO_JUMP`.
- Earlier movement attempts proved spawner-owned look/walk commands and frame-updated single movement are viable, but none used the script jump-site command family.
- This still avoids the risky custom descriptor path, coordinate writes, and slot-47 callback execution.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test144.nds` and copied to Delta.
- `git diff --check` passed before and after the build.
- Verified active spot emote code no longer sets or clears `BIT_JUMP_START`.
- Verified the emote now starts a direction-specific jump-site movement command from the `0x30`-`0x33` family with `MapObject_StartMovementCommand` and `MapObject_SetSingleMovementActive`.
- Verified `OverworldWildSpawns_TickSpotEmote` drives the emote command through `OverworldWildSpawns_UpdateSpawnerMovementCommand` and still falls through to active chase/flee if the emote timer expires.
- Verified the test sound is now `SEQ_SE_DP_KON`.

Runtime result:

- User reported no visible hop, but the `SEQ_SE_DP_KON` sound does play.

Learning:

- The spot-emote trigger and sound call are working.
- The `Jump*Site` command family either is not visibly animating these spawned idle objects or is completing/clearing before any visible render frame.
- Do not retry the same `0x30`-`0x33` jump-site command path without new evidence.

### Attempt 48: Manual PosVec Height Bob For Spot Emote

Idea:

Stop relying on the stock jump-site movement command for the spot hop. When the Pokemon spots the player, save `object->posVec[1]`, play the now-confirmed audible `SEQ_SE_DP_KON`, and manually apply a 20-frame up/down fixed-point height offset before restoring the original `posVec[1]` and entering chase/flee. This tests whether spawned Pokemon can be visually lifted without tile-coordinate writes or custom movement descriptor callbacks.

Why this is new:

- Attempts 45 and 46 used `BIT_JUMP_START`.
- Attempt 47 used `Jump*Site` movement commands and proved the sound path works, but the jump command is still not visibly animating.
- No previous attempt has directly applied a temporary same-tile `posVec[1]` render-height bob.
- This avoids tile `xCurr`/`yCurr` writes, movement descriptor reactivation, and movement command polling for the emote.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test145.nds` and copied to Delta.
- `git diff --check` passed before and after the build.
- Verified `OverworldWildSpawnState` now stores `movementEmoteBasePosY` per spawn slot.
- Verified `OverworldWildSpawns_TryStartSpotEmote` saves `object->posVec[1]`, starts a 20-frame emote timer, plays `SEQ_SE_DP_KON`, and does not start a stock jump movement command.
- Verified `OverworldWildSpawns_TickSpotEmote` applies a triangular fixed-point offset up to `OW_WILD_SPAWNER_SPOT_HOP_PEAK_PIXELS` and restores the original `posVec[1]` when the emote ends.
- Verified reset paths restore `posVec[1]` if a slot is cleared while still emoting.

Runtime result:

- User reported no visible hop.

Learning:

- Directly changing `object->posVec[1]` from the spawner overlay does not produce a visible hop for these spawned Pokemon.
- The renderer likely derives the visible object height from another movement/render state, or overwrites `posVec[1]` before draw.
- Do not retry manual `posVec[1]` bobbing without new evidence.

### Attempt 49: Use WaitJumpSite Movement Command

Idea:

Use the default script movement command `WaitJumpSite` (`0x65`) directly for the spot emote. The user pointed out Lyra/Ethan perform an excited hop near the start of the game, and the script macro table has a specific same-tile waiting jump command distinct from the previously tested directional `Jump*Site` commands. Start `0x65` as a single movement command, drive it through the stable frame updater, and keep the confirmed-audible `SEQ_SE_DP_KON` sound.

Why this is new:

- Attempts 45 and 46 used `BIT_JUMP_START`.
- Attempt 47 used directional `Jump*Site` commands (`0x30`-`0x33`).
- Attempt 48 used manual `posVec[1]` height changes.
- No previous attempt has tried `WaitJumpSite` (`0x65`), which is a separate default movement command listed in `armips/include/scriptmacros.s`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test146.nds` and copied to Delta.
- `git diff --check` passed before and after the build.
- Verified the failed manual `posVec[1]` bob state was removed from `OverworldWildSpawnState`.
- Verified active spot emote code starts `OW_WILD_SPAWNER_SPOT_EMOTE_COMMAND` / `WaitJumpSite` (`0x65`) directly with `MapObject_StartMovementCommand` and `MapObject_SetSingleMovementActive`.
- Verified `OverworldWildSpawns_TickSpotEmote` drives the command through `OverworldWildSpawns_UpdateSpawnerMovementCommand` and falls back to active chase/flee after `OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES`.
- Verified the sound remains `SEQ_SE_DP_KON`.

Runtime result:

- User reported this produced the ground "smoke" that appears to be part of the hop visual presentation, but the Pokemon still did not visibly hop or jump.

Learning:

- `WaitJumpSite` reaches the movement/FX layer and can trigger the landing/smoke presentation on spawned Pokemon.
- `WaitJumpSite` alone does not provide the visible vertical hop for these objects.
- The stock excited-hop sequence likely pairs `WaitJumpSite` with another movement command that applies the vertical object motion.
- Do not retry `0x65` by itself.

### Attempt 50: LockDir Jump2 Smoke Release Sequence

Idea:

Run a multi-command spot-emote sequence instead of a single command. Decode of compiled script movement pointers found stock movement lists that use `LockDir -> Jump*2 -> ReleaseDir` for hop-like moments. Since Attempt 49 proved `WaitJumpSite` can produce the ground smoke, this attempt sequences `LockDir` (`0x47`), direction-specific `Jump*2` (`0x38`-`0x3B`), `WaitJumpSite` (`0x65`), and `ReleaseDir` (`0x48`) before entering chase/flee.

Why this is new:

- Attempts 45 and 46 used `BIT_JUMP_START`.
- Attempt 47 used a single directional `Jump*Site` command (`0x30`-`0x33`).
- Attempt 48 used manual `posVec[1]` height changes.
- Attempt 49 used only `WaitJumpSite` (`0x65`).
- No previous attempt has run a stock-style multi-command emote sequence with `LockDir`, `Jump*2`, smoke, and `ReleaseDir`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test147.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified `OverworldWildSpawnState` now stores per-slot emote step and emote direction state.
- Verified the active spot-emote sequence starts `LockDir`, then direction-specific `Jump*2`, then `WaitJumpSite`, then `ReleaseDir`.
- Verified the emote sequence is advanced by `OverworldWildSpawns_UpdateSpawnerMovementCommand` instead of retrying direct object height edits or `BIT_JUMP_START`.
- Verified the sound remains `SEQ_SE_DP_KON`.

Runtime result:

- User reported the Pokemon now visibly hops, but the hop is not in place; it hops while moving toward the player.

Learning:

- The stock `Jump*2` command family produces the visible lift animation on spawned Pokemon.
- `Jump*2` also advances the object toward the player, so it cannot be used directly for a same-tile spot emote.
- The successful visibility likely comes from the stock jump movement command path, not from `WaitJumpSite` alone.
- Do not retry direction-specific `Jump*2` as the spot emote unless the tile movement is intentionally desired.

### Attempt 51: LockDir JumpSite Smoke Release Sequence

Idea:

Keep the multi-command spot-emote machinery from Attempt 50, because that finally produced a visible hop, but replace the moving `Jump*2` command family (`0x38`-`0x3B`) with the same-tile `Jump*Site` command family (`0x30`-`0x33`). The sequence becomes `LockDir` (`0x47`), direction-specific `Jump*Site` (`0x30`-`0x33`), `WaitJumpSite` (`0x65`), and `ReleaseDir` (`0x48`) before chase/flee starts.

Why this is new:

- Attempt 47 used a single `Jump*Site` command without a stock-style `LockDir`/`ReleaseDir` wrapper and did not produce a visible hop.
- Attempt 49 used only `WaitJumpSite` and produced smoke but no visible hop.
- Attempt 50 used the wrapper plus `Jump*2`, producing the visible hop but also moving the Pokemon.
- No previous attempt has combined `LockDir`, direction-specific same-tile `Jump*Site`, `WaitJumpSite`, and `ReleaseDir`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test148.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified active code uses `OW_WILD_SPAWNER_SPOT_EMOTE_JUMP_SITE_COMMAND` / `0x30` as the emote jump command family.
- Verified the sequence still starts with `LockDir`, advances through the same frame-updated single-movement command path, then runs `WaitJumpSite` and `ReleaseDir`.
- Verified this does not reintroduce `BIT_JUMP_START` or direct `posVec[1]` edits.

Runtime result:

- User reported this still does not visibly hop.

Learning:

- The `LockDir`/`ReleaseDir` wrapper does not make the same-tile `Jump*Site` command family visibly hop on spawned Pokemon.
- Attempt 50's visible lift remains specific to the moving `Jump*2` command family so far.
- The next solution should explore more shipped movement examples and avoid retrying `Jump*Site` unless a different stock sequence provides new evidence.

### Attempt 52: Partner Pokemon JumpSite Wrapper

Idea:

Use a movement sequence copied from shipped partner-Pokemon movement examples instead of human NPC examples. A compiled script scan of `build/a012` found four directional variants in script file `2_163` applied to `obj_partner_poke` (`253`): `0x49 -> Jump*Site -> Freeze -> 0x4A`. Since spawned overworld Pokemon are created through the follower/special-object style path, this is a closer match than the earlier `LockDir`/`ReleaseDir` NPC examples. The spot emote now runs `0x49`, direction-specific `Jump*Site` (`0x30`-`0x33`), `Freeze` (`0x3E`), and `0x4A`, then enters chase/flee.

Why this is new:

- Attempt 47 used a single `Jump*Site` command.
- Attempt 51 used `LockDir -> Jump*Site -> WaitJumpSite -> ReleaseDir`.
- No previous attempt has used the unnamed `0x49`/`0x4A` wrapper found around stock partner-Pokemon `Jump*Site` movement.
- This is based on compiled shipped script movement lists, not just command macro names.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test149.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified active code uses the partner-Pokemon wrapper command sequence `0x49 -> Jump*Site -> Freeze -> 0x4A`.
- Verified the shipped-script evidence came from decoded `apply_movement` lists in `build/a012`, including `obj_partner_poke` (`253`) directional variants in script file `2_163`.
- Verified this does not retry `BIT_JUMP_START`, direct `posVec[1]` edits, `WaitJumpSite` alone, `LockDir -> Jump*Site -> WaitJumpSite -> ReleaseDir`, or moving `Jump*2`.

Runtime result:

- User reported jumping now works.

Learning:

- The partner-Pokemon wrapper sequence is the first confirmed same-tile visible hop path for spawned overworld Pokemon.
- The likely critical pieces are the unnamed `0x49` setup command and `0x4A` restore command around `Jump*Site`, matching the shipped `obj_partner_poke` movement examples.
- Keep using this wrapper for spot-emote jumps unless a future test reveals a regression.

### Attempt 53: Three-Speed Scale And Speed-3 Double Hop

Idea:

Remove logical speed `4` and speed `5`, because both were aliases to the same safe stock movement command family as speed `3`. Keep speed `1`, speed `2`, and speed `3` only. Set Pidgey to speed `3`, and use the now-confirmed partner-Pokemon hop wrapper twice for speed-3 Pokemon when they spot the player. Lower-speed Pokemon still hop once.

Why this is new:

- Attempt 45 removed speed `6`, but kept speed `4` and `5` as aliases.
- No previous attempt has collapsed the scale to the three distinct safe walk command families.
- Attempt 52 found the working same-tile hop sequence, but only played it once for every speed.
- No previous attempt has tied the number of spot-emote jumps to movement speed.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test150.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified speed `4` and speed `5` command constants and switch cases were removed from active source.
- Verified Pidgey now uses logical speed `3`.
- Verified speed `3` maps to `OW_WILD_SPAWNER_MOVEMENT_SPEED_3_COMMAND` / stock command family `0x10`; speed `1` and speed `2` remain `0x08` and `0x0C`.
- Verified speed-3 spawns set `movementEmoteJumpsRemaining` to `2`, while lower speeds set it to `1`.
- Verified the hop sound now plays from the jump step itself, so a speed-3 double-hop plays the sound twice.

Runtime result:

- User reported "Nice!" and requested keeping the jump behavior while adding a hop cry, tired behavior, and chill wandering.

Learning:

- The three-speed scale and speed-3 double-hop are good enough to build on.
- Keep Pidgey at speed `3` for current testing.

### Attempt 54: Hop Cry, Tired Cooldown, And Chill Wander

Idea:

Layer richer behavior on top of the now-confirmed spot-hop and chase/flee system without adding a new movement-command family. When a spot-emote jump command completes, play that spawn's actual cry via the same `PlayCry(species, form)` API already proven by ambient overworld cries. Count completed chase/flee walk commands while a spawn is in the active spotted state; after a few completed active steps, play a distinct tired sound, reset the spawn to chill, and start a per-slot spot cooldown so it cannot immediately spot or re-engage the player again. While chill, choose random directions and start the same proven spawner-owned walk commands so chill Pokemon wander instead of standing still.

Why this is new:

- Attempts 52 and 53 made the spot-hop visual work, but only played the generic hop sound from the jump step.
- Ambient cries already use `PlayCry`, but no previous attempt has tied a species/form cry to completion of a spot-hop jump command.
- Previous chase/flee attempts kept active Pokemon pursuing indefinitely until blocked, battled, or effectively leashed by map/object movement constraints.
- No previous attempt has counted completed active chase/flee steps and transitioned back to chill with a temporary no-spot cooldown.
- No previous attempt has suppressed the proximity battle retry during that tired no-spot cooldown.
- Earlier "stock wander masks behavior" attempts used stock movement ownership; this chill wander keeps ownership in the same spawner-driven command path that is currently stable.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test151.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified the spot-emote path calls `PlayCry(state->spawns[slot].species, state->spawns[slot].form)` when the jump command finishes and the emote step advances to `FREEZE`.
- Verified completed spawner-owned movement commands call `OverworldWildSpawns_HandleFinishedMovementCommand`.
- Verified only the active spotted state increments `movementActiveSteps`; chill wander movement does not count toward tiredness.
- Verified active chase/flee transitions to tired after `OW_WILD_SPAWNER_TIRED_AFTER_STEPS` / `5` completed movement commands.
- Verified tired behavior plays `OW_WILD_SPAWNER_TIRED_EMOTE_SE`, returns the slot to chill, starts `movementSpotCooldowns[slot]`, and pauses wandering briefly.
- Verified proximity battle retry is suppressed while a chill slot still has a tired no-spot cooldown.
- Verified chill wandering uses random directions through the existing spawner-owned walk command path and skips occupied target tiles.

Runtime result:

- User reported that the playful behavior did not feel like it naturally fell back into approach behavior.
- The user also suggested that playful likely does not need two distinct chase branches.

Learning:

- The hard branch between "not adjacent, chase target tile" and "adjacent, seek adjacent/orbit tile" can make the behavior feel sticky instead of naturally unified.
- Next attempt should remove the explicit approach-vs-close split and use one scoring rule for all playful movement decisions.

### Attempt 55: Tired WaitJumpSite Then Stat-Fell Sound

Idea:

Change the tired presentation so tiredness does not immediately play the sound and snap back to chill. When a Pokemon completes enough active chase/flee steps, put that slot into a distinct tired state, start only the default `WaitJumpSite` movement command (`0x65`), and keep battle detection suppressed while that tired command is running. When `WaitJumpSite` finishes, play `SEQ_SE_GS_PARAMETER_DOWN` as the stat-fell sound, then return the Pokemon to chill with the existing no-spot cooldown and brief wander pause.

Why this is new:

- Attempt 49 used `WaitJumpSite` as a spot-hop attempt and proved it could trigger the ground/smoke presentation, but it was not used as a tired-only emote.
- Attempt 54 played the tired sound immediately when the Pokemon became tired and did not run a tired movement-command animation first.
- No previous attempt has added a distinct tired state between active chase/flee and chill.
- No previous attempt has delayed the stat-fell sound until after a tired presentation command completes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test152.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified tiredness now starts `OW_WILD_SPAWNER_TIRED_EMOTE_COMMAND` / `0x65` (`WaitJumpSite`) instead of immediately entering chill cooldown.
- Verified tired slots use the distinct `OW_WILD_SPAWNER_SPOT_STATE_TIRED` state while the command is running.
- Verified `OverworldWildSpawns_TickTiredEmote` advances the single movement command through the existing frame-updated command path.
- Verified the stat-fell sound is `SEQ_SE_GS_PARAMETER_DOWN` and plays from `OverworldWildSpawns_StartTiredCooldown` after the tired command finishes or times out.
- Verified battle detection returns false while a slot is in the tired state.

Runtime result:

- Superseded by user request to try a different sound and explore follower-style chat/emotion bubbles instead of another `WaitJumpSite` presentation.

Learning:

- `WaitJumpSite` remains useful as a fallback, but the next investigation should move away from movement-command emotes and toward the follower emotion-bubble helper.

### Attempt 56: Tired Follower Emotion Bubble Helper

Idea:

Use the vanilla follower emotion-bubble task helper directly on spawned Pokemon when they become tired. Reference tracing found that `ScrCmd_597` calls `ov01_02203AB4(fieldSystem, partnerPokeObj, 0)`, and the normal follower interaction path can also call the same helper with ids `0..13` through `ov02_0224FB54`. The helper creates an overlay effect above the target map object, guarded by overlay slot `0x12`, instead of starting a map-object movement command.

Wire tired spawns to call `ov01_02203AB4` with a named `OW_WILD_SPAWNER_TIRED_BUBBLE_ID` constant, currently `0` because that is the vanilla script-command path shown after follower cries in `scr_seq_0163`. Keep `WaitJumpSite` as a fallback if the field context is not current. Replace the delayed tired sound with `SEQ_SE_PL_BALLOON05` so this test also tries a different tired sound.

Why this is new:

- Attempt 49 and Attempt 55 used `WaitJumpSite` (`0x65`), which is a movement command.
- Attempt 52 used the partner hop command sequence `0x49 -> Jump*Site -> Freeze -> 0x4A`, which is also a movement-command path.
- No previous attempt has exposed or called `ov01_02203AB4`.
- No previous attempt has used the follower emotion-bubble overlay slot or a named bubble id for spawned wild Pokemon.
- No previous tired attempt has used `SEQ_SE_PL_BALLOON05`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built successfully with `./docker-makerom.cmd`.
- `git diff --check` passed before build.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test153.nds`.

Runtime result:

- User reported no balloon appeared above the tired Pokemon.

Learning:

- Directly calling `ov01_02203AB4(fieldSystem, spawnedObject, 0)` is not enough to show the follower-style emotion balloon on a spawned wild Pokemon.
- The next attempt should not simply retry the same helper call or bubble id. It should verify whether the helper has a missing prerequisite, whether another wrapper passes different object/effect data, or whether the spawned object needs a different overlay/emote path.

### Attempt 57: Direct Follower Bubble Effect Creator

Idea:

Bypass the script-task wrapper `ov01_02203AB4` and call the lower-level bubble effect creator `ov01_02203A48(spawnedObject, bubbleId)` directly when a spawned Pokemon becomes tired. Reference tracing shows `ov01_02203AB4` only allocates a tiny environment and queues a `TaskManager` task; that task later calls `ov01_02203A48`, which does the real overlay-slot `0x12` effect creation. Since the spawned-wild movement logic runs from spawner/frame tasks rather than a vanilla script command, this tests whether the wrapper's queued task path was the part that failed silently.

Why this is new:

- Attempt 56 called only `ov01_02203AB4(fieldSystem, spawnedObject, 0)`.
- No previous attempt has exposed or called `ov01_02203A48` directly.
- This keeps the same vanilla follower bubble resources and effect slot, so it isolates the entry point instead of changing the visual asset or retrying a movement-command emote.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built successfully with `./docker-makerom.cmd`.
- `git diff --check` passed before build.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test154.nds`.

Runtime result:

- User reported it worked: a balloon message appeared above the tired Pokemon's head. The icon was a heart, which does not fit the intended tired state, but confirms the follower bubble effect can attach to spawned wild Pokemon.

Learning:

- Direct `ov01_02203A48(spawnedObject, 0)` is the first confirmed visible follower-balloon path for spawned wild Pokemon.
- The failed part of Attempt 56 was likely the queued `TaskManager` wrapper path, not the overlay resource/effect itself.
- Bubble id `0` currently shows a heart, so future icon work should test other ids instead of changing the now-proven direct entry point.

### Attempt 58: Silent Direct Tired Bubble

Idea:

Keep the now-confirmed direct follower bubble creator from Attempt 57, but suppress sound while the tired balloon appears. Reference disassembly shows the bubble effect init plays `SEQ_SE_DP_DECIDE` internally, so call `StopSE(SEQ_SE_DP_DECIDE)` immediately after `ov01_02203A48`. Also gate the separate delayed tired cooldown sound behind `OW_WILD_SPAWNER_TIRED_PLAY_COOLDOWN_SE`, currently disabled, so tired balloon presentation can be tested silently.

Why this is new:

- Attempt 57 proved direct `ov01_02203A48` displays a balloon, but still allowed the vanilla bubble init sound and the later tired cooldown sound.
- No previous attempt has exposed or called `StopSE`.
- No previous tired-balloon attempt has explicitly separated the visual balloon from both the vanilla `SEQ_SE_DP_DECIDE` sound and our own delayed tired sound.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/sound.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built successfully with `./docker-makerom.cmd`.
- `git diff --check` passed before build.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test155.nds`.

Runtime result:

- User reported the balloon is still just a heart. Sound result was not reported.

Learning:

- Sound controls do not affect the icon choice; the icon is still determined by `OW_WILD_SPAWNER_TIRED_BUBBLE_ID`.
- The next attempt should keep the direct `ov01_02203A48` entry point and change the bubble id.

### Attempt 59: Tired Bubble Id Probe Cycle

Idea:

Keep the confirmed direct follower bubble creator and sound suppression from Attempts 57 and 58, but stop hardcoding bubble id `0`. Add a small probe cycle that starts at id `1`, advances through id `13`, then wraps back to `1`. This skips the confirmed heart icon at id `0` and lets runtime testing map the remaining follower balloon icons without requiring one ROM build per id.

Why this is new:

- Attempts 56, 57, and 58 all used bubble id `0`.
- Attempt 57 proved the direct creator works, but did not vary the id.
- Attempt 58 changed sound behavior only and confirmed the icon stayed heart.
- No previous attempt has cycled or otherwise probed alternate follower bubble ids.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test156.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test156.nds`.
- `git diff --check` passed after the build.
- Verified tired bubbles now call `OverworldWildSpawns_GetTiredBubbleId()` instead of hardcoding `0`.
- Verified the probe cycles through ids `1` through `13`, then wraps back to `1`, intentionally skipping the confirmed heart icon at id `0`.
- Verified `sOverworldWildMovementDiagnosticLookCommand` records the bubble id used for the tired balloon.

Runtime result:

- User reported the icon changed from the heart, but the next observed balloon was a smiley face.

Learning:

- The bubble id parameter is confirmed to affect the displayed icon.
- Bubble id `1` appears to be a smiley face, so the next tired-icon probe should continue through ids `2` through `13` rather than returning to id `0` or `1`.

### Attempt 60: Skip Known Heart And Smiley Bubble Ids

Idea:

Keep the confirmed direct follower bubble creator and id probe, but start the probe at id `2` instead of id `1`. This avoids making a fresh test session show the already-mapped smiley face first, while still cycling through the remaining unknown ids through `13`.

Why this is new:

- Attempt 57 confirmed id `0` shows a heart through the direct creator.
- Attempt 59 confirmed id `1` appears to be a smiley face and proved the id argument controls the icon.
- No previous attempt has skipped both known non-tired icons and started the probe at id `2`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test157.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test157.nds`.
- `git diff --check` passed before the build.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN` is now `2`, so fresh sessions skip the known heart id `0` and smiley id `1`.
- Verified the probe still wraps through `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MAX` / `13`.

Runtime result:

- User reported the next observed balloon was an angry face.

Learning:

- Bubble id `2` appears to be an angry face.
- Angry does not fit the intended tired state, so the probe should continue from id `3`.
- The known icon ids should be named in code as they are discovered so future behavior can use them directly.

### Attempt 61: Name Known Bubble Ids And Skip Angry

Idea:

Define the discovered follower bubble ids in source as reusable names: heart `0`, smile `1`, and angry `2`. Then move the active tired probe start to the first still-unknown id, `3`, while keeping the same direct `ov01_02203A48` creator and sound suppression.

Why this is new:

- Attempt 57 confirmed id `0` shows a heart.
- Attempt 59 confirmed id `1` appears to be a smiley face.
- Attempt 60 confirmed id `2` appears to be an angry face.
- No previous attempt has codified the discovered id map in source or started the probe at id `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test158.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test158.nds`.
- `git diff --check` passed before the build.
- Verified source now defines `OW_WILD_SPAWNER_BUBBLE_ID_HEART`, `OW_WILD_SPAWNER_BUBBLE_ID_SMILE`, and `OW_WILD_SPAWNER_BUBBLE_ID_ANGRY`.
- Verified `OW_WILD_SPAWNER_TIRED_BUBBLE_ID_PROBE_MIN` now derives from `OW_WILD_SPAWNER_BUBBLE_ID_ANGRY + 1`, so fresh sessions start at id `3`.

Runtime result:

- User reported this build appeared to get a different icon each time, then mapped the remaining ids:
- `3`: Sad
- `4`: Mildly happy
- `5`: Angry and shaking head / disapproval
- `6`: Music note
- `7`: Question mark
- `8`: Exclamation mark
- `9`: Water droplet / sweat / nervousness
- `10`: Screaming in despair
- `11`: Poison
- `12`: Ellipsis
- `13`: Sleep

Learning:

- Attempt 61's apparent randomness was the intentional id cycle through ids `3` through `13`.
- The full follower bubble id range is now mapped.
- The water droplet at id `9` fits the tired state best.

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

### Attempt 63: Behavior Profile Resolver

Idea:

Replace the current scattered movement constants with a composable behavior profile. The profile contains `chill_State`, `alert_State`, `alertness`, `attentive_State`, `stamina`, `tired_State`, `rest_Time`, `max_speed`, and `range`. Resolve behavior in this order: default profile, optional behavior-class override, then species-specific override. Keep the default profile aligned with the current working behavior, move Pidgey's speed into the species override table, and keep tired Pokemon on the mapped water-droplet bubble.

Why this is new:

- Attempts 54 and 55 added tired/chill behavior directly through hardcoded counters and constants.
- Attempts 57 through 62 focused on tired bubble presentation and icon mapping.
- No previous attempt has introduced a data-driven behavior profile with default, behavior-class, and species-specific override layers.
- No previous attempt has made stamina spending depend on `max_speed`.
- No previous attempt has made movement range, alertness, rest time, attentive movement, chill behavior, and tired presentation resolve from one behavior contract.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test160.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test160.nds`.
- `git diff --check` passed before the build.
- Verified `OverworldWildBehaviorProfile` contains `chillState`, `alertState`, `alertness`, `attentiveState`, `stamina`, `tiredState`, `restTime`, `maxSpeed`, and `range`.
- Verified profile resolution merges default profile, behavior-class override, then species-specific override.
- Verified Pidgey's speed is now supplied by the species override table instead of a direct species switch in the movement-speed function.
- Verified movement range, alertness, attentive chase/flee/none decision, chill wandering, stamina spending, tired rest duration, and tired bubble id are read from the resolved profile.
- Verified completed attentive moves spend stamina equal to `maxSpeed`, capped at the profile's `stamina`.
- Verified cleared spawn slots reset their stored behavior class.

Runtime result:

- Superseded before user runtime testing.
- User clarified the intended hierarchy is `Default behavior -> Behavior class override -> Behavior variable override`, not `Default behavior -> Behavior class override -> species-specific override`.

Learning:

- Avoid repeating the Attempt 63 species-specific third layer. Species, broader groups, terrain/pool, level, shiny state, and other context should be used to select behavior classes or match behavior-variable overrides; the final layer itself is a generic variable override layer.

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

### Leaf Effect Probe: Isolated Headbutt Dispatcher ID `0x14`

Context:

- The real Headbutt trace starts its dispatcher burst with ID `0x14`.
- The full real Headbutt dispatcher sequence froze when replayed on player step, so this probe isolated just ID `0x14`.

Attempted:

- Set the player-step probe to call `ov01_021F14F4(ov01_021F146C(playerObject), 0x14, 0x17)`.
- Built `test739.nds`.
- Verified headless with hooks on `0x021F14F4`, `0x021FD1B8`, `0x022006A8`, and `0x021F146C`.

Runtime result:

- Failed. The game froze.
- `documentation/verification_screenshots/player_step_dispatch_id14_trace.json` reports `freeze_at=1464`, `max_identical_run=20`, and `nonzero_diff_samples=0 / 20`.
- Contact sheet: `documentation/verification_screenshots/player_step_dispatch_id14_contact.png`.

Learning:

- Do not retry isolated dispatcher ID `0x14` as a player-step leaf candidate.
- The real Headbutt burst starting with ID `0x14` is not safe to replay directly outside the stock Headbutt task lifecycle.

### Leaf Effect Probe: Isolated Headbutt Dispatcher ID `0x15`

Context:

- The real Headbutt trace reaches `0x022006A8` through dispatcher ID `0x15`.
- This was tested after ID `0x14` froze, to avoid replaying the entire Headbutt effect list.

Attempted:

- Set the player-step probe to call `ov01_021F14F4(ov01_021F146C(playerObject), 0x15, 0x17)`.
- Built `test740.nds`.
- Verified headless with hooks on `0x021F14F4`, `0x022006A8`, `0x022006C4`, and `0x021F146C`.

Runtime result:

- Failed. The game froze.
- `documentation/verification_screenshots/player_step_dispatch_id15_trace.json` reports `freeze_at=1464`, `max_identical_run=20`, and `nonzero_diff_samples=0 / 20`.
- The hook saw `leaf_ctor_calls=2` and `leaf_dtor_calls=0`, which supports that the isolated lifecycle is unsafe in this context.
- Contact sheet: `documentation/verification_screenshots/player_step_dispatch_id15_contact.png`.

Learning:

- Do not retry isolated dispatcher ID `0x15` or raw `022006A8` for player-step leaves without a new lifecycle wrapper.
- Continue with nearby late Headbutt impact IDs one at a time: `0x07`, then `0x06`, then `0x0E`.

### Leaf Effect Probe: Isolated Headbutt Dispatcher ID `0x07`

Context:

- Static trace review identified `0x0E -> 0x06 -> 0x07 -> 0x15` as the late Headbutt impact cluster.
- ID `0x07` was tested after `0x14` and `0x15` both froze.

Attempted:

- Set the player-step probe to call `ov01_021F14F4(ov01_021F146C(playerObject), 0x07, 0x17)`.
- Built `test741.nds`.
- Verified headless with hooks on `0x021F14F4`, `0x021FED9C`, `0x021FEDB8`, and `0x021F146C`.

Runtime result:

- Failed. The game froze.
- `documentation/verification_screenshots/player_step_dispatch_id07_trace.json` reports `freeze_at=1464`, `max_identical_run=20`, and `nonzero_diff_samples=0 / 20`.
- Contact sheet: `documentation/verification_screenshots/player_step_dispatch_id07_contact.png`.

Learning:

- Do not retry isolated dispatcher ID `0x07` as a player-step leaf candidate.
- The isolated dispatcher route is increasingly suspect outside the stock Headbutt task lifecycle.

### Leaf Effect Probe: Isolated Headbutt Dispatcher ID `0x06`

Context:

- ID `0x06` is in the late Headbutt impact cluster before `0x07` and `0x15`.
- Earlier verifier runs over-counted stock map-load effect setup, so this was rerun with a clean boot that stops at the overworld before the Headbutt prompt is advanced.

Attempted:

- Set the player-step probe to call `ov01_021F14F4(ov01_021F146C(playerObject), 0x06, 0x17)`.
- Built `test742.nds`.
- Verified headless with hooks on `0x021F14F4`, `0x021FEC38`, `0x021FEC54`, and `0x021F146C`.

Runtime result:

- Failed. The player-step probe call at frame `1056` froze the game by frame `1200`.
- `documentation/verification_screenshots/player_step_dispatch_id06_cleanboot_trace.json` reports `freeze_at=1200`, `max_identical_run=20`, and `nonzero_diff_samples=0 / 20`.
- Contact sheet: `documentation/verification_screenshots/player_step_dispatch_id06_cleanboot_contact.png`.

Learning:

- Do not retry isolated dispatcher ID `0x06` as a player-step leaf candidate.
- Clean verifier note: use seven boot `A` taps for this save, then movement only. More `A` taps interact with the Headbutt tree.

### Leaf Effect Probe: Isolated Headbutt Dispatcher ID `0x0E`

Context:

- ID `0x0E` was the remaining late Headbutt impact-cluster candidate after `0x06`, `0x07`, and `0x15`.

Attempted:

- Set the player-step probe to call `ov01_021F14F4(ov01_021F146C(playerObject), 0x0E, 0x17)`.
- Built `test743.nds`.
- Verified headless with the clean seven-`A` boot, hooks on `0x021F14F4`, `0x021FFECC`, `0x021FFEE8`, and `0x021F146C`.

Runtime result:

- Failed. The player-step probe froze the game.
- `documentation/verification_screenshots/player_step_dispatch_id0E_cleanboot_trace.json` reports `freeze_at=1200`, `max_identical_run=20`, and `nonzero_diff_samples=0 / 20`.
- Contact sheet: `documentation/verification_screenshots/player_step_dispatch_id0E_cleanboot_contact.png`.

Learning:

- Do not retry isolated dispatcher ID `0x0E` as a player-step leaf candidate.
- The isolated dispatcher route is not the safe way to play the leaf visual.

### Leaf Effect Probe: Wrapper `0x022008B4`

Context:

- Static trace review suggested `0x022008B4(fieldSystem->playerAvatar)` as a wrapper near the Headbutt effect context path.
- This was tested after isolated dispatcher IDs froze.

Attempted:

- Set the player-step probe to call `ov01_022008B4(fieldSystem->playerAvatar)`.
- Stored the returned handle and cleared it with the generic `ov01_021F1640` destroyer before replacing it.
- Built `test744.nds`.
- Verified headless with hooks on `0x022008B4`, `0x021F1620`, `0x021F1640`, `0x021F146C`, and `0x02200858`.

Runtime result:

- Stable but visually wrong.
- `documentation/verification_screenshots/player_step_wrapper_022008B4_cleanboot_trace.json` reports no freeze, `max_identical_run=2`, and `nonzero_diff_samples=228 / 299`.
- Contact sheet: `documentation/verification_screenshots/player_step_wrapper_022008B4_cleanboot_contact.png`.
- Visual review shows no falling Headbutt leaf particles at the player.

Learning:

- `022008B4` is a safe wrapper candidate but not the requested Headbutt leaf particle visual.
- Keep wrapper-level probing, but move to the stock avatar Headbutt wrapper rather than more isolated dispatcher IDs.

### Leaf Effect Probe: Avatar Wrapper `0x021FCFEC`

Context:

- `021FCFEC(fieldSystem->playerAvatar)` is the stock avatar Headbutt motion wrapper and was tested after `022008B4` proved safe but visually wrong.

Attempted:

- Set the player-step probe to call `ov01_021FCFEC(fieldSystem->playerAvatar)`.
- Built `test745.nds`.
- Verified headless with hooks on `0x021FCFEC`, `0x021FD064`, `0x021F14F4`, `0x022006A8`, and `0x021F146C`.

Runtime result:

- Stable but visually wrong.
- `documentation/verification_screenshots/player_step_wrapper_021FCFEC_cleanboot_trace.json` reports no freeze, `max_identical_run=2`, and `nonzero_diff_samples=249 / 359`.
- Contact sheet: `documentation/verification_screenshots/player_step_wrapper_021FCFEC_cleanboot_contact.png`.
- Visual review shows player/headbutt-ish movement, but no falling Headbutt leaf particles at the player.
- The only `022006A8` hit in this trace is from the map-load effect burst at frame `888`, not from the player-step `021FCFEC` calls.

Learning:

- `021FCFEC` is not the leaf-particle player-step entrypoint.
- Retest `ov01_022006A8(ov01_021F146C(playerObject))` under the cleaned verifier, because older direct-helper screenshots were taken before the A-tap contamination was understood.

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

### Leaf Effect Probe: Clean Direct Context Retest And Existing-Handle Restart

Context:

- The older Attempt 243 note said `ov01_022006A8(ov01_021F146C(playerObject))` worked, but that result was captured before the verifier boot contamination was understood.
- The clean verifier now boots with exactly seven A taps, avoiding accidental Headbutt prompt/sequence startup before the player-step probe.
- The user clarified that identical screenshots mean freeze, so long identical screenshot runs are treated as a hard failure.

Clean retest result:

- Rebuilt the direct `ov01_022006A8(ov01_021F146C(playerObject))` player-step probe as `test746.nds`.
- Headless clean-boot verifier result:
  - `leaf_ctor_calls=2`
  - `leaf_dtor_calls=0`
  - `effect_context_calls=12`
  - `freeze_at=1178`
  - `max_identical_run=30`
  - `nonzero_diff_samples=1`
- Trace:
  - `documentation/verification_screenshots/player_step_direct_022006A8_cleanboot_trace.json`
- Contact sheets:
  - `documentation/verification_screenshots/player_step_direct_022006A8_cleanboot_contact.png`
  - `documentation/verification_screenshots/player_step_direct_022006A8_cleanboot_first_step_contact.png`

Learning:

- Do not rely on the older Attempt 243 conclusion that direct `022006A8(effectContext)` is stable.
- The direct constructor path can freeze even when the argument is a valid effect context.
- Real vanilla Headbutt reaches `022006A8` through the preloaded map-object effect list:
  - `021E64F6` calls `021F13D0(context, 0x02208BFC)`.
  - `0x02208BFC` is the exact ID list seen in the real Headbutt trace: `0x14, 0x13, 0x11, 0x01, 0x10, 0x05, 0x16, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0F, 0x12, 0x00, 0x02, 0x03, 0x04, 0x0E, 0x06, 0x07, 0x15, 0x17`.
  - The final `0x15` entry maps to `022006A8/022006C4`.
- Therefore the next new probe should not allocate another `0x15` effect. It should reuse the existing `0x15` handle from the player's already-initialized effect context.

New probe:

- Add a temporary player-step mode that:
  - gets the player's effect context with `ov01_021F146C(playerObject)`;
  - gets the existing `0x15` effect handle with `ov01_021F1450(effectContext, 0x15)`;
  - restarts it with `ov01_022006D4(effect)`.
- This does not call `022006A8`, does not own the returned effect, and does not destroy it.
- This has not been tried before; previous probes either called dispatcher IDs, `022008B4`, `021FCFEC`, or the raw/direct `022006A8` constructor.

Verification:

- Pending.

### Attempt 243: Corrected Headbutt Leaf Effect Context Hook

Runtime result from the effect probes:

- Direct `022006A8` froze the game and should not be retried as a raw map-object call.
- `021FE66C` produced a shiny-like visual. This may be useful later for shiny wild overworld Pokemon, but it is not the headbutt leaf effect.
- `021FC748(fieldSystem, 0, 0/1)` appears to be the high-level vanilla headbutt visual task, but standalone use in the open-field verifier did not show the leaf burst.
- `021FCB90` with IDs `0x31..0x34` produced fishing/dialog text such as "Not even a nibble...", not leaves.
- `02200730` was stable in `test668.nds`, but showed a red target square around the player instead of leaves.
- `0220329C` variants were stable in `test669.nds`, but showed a small dark ground/blob effect instead of leaves.
- `ov01_02200540(playerObject, 0, TRUE)` built as `test672.nds` and was stable, but the screenshots showed an exclamation-style object effect instead of the floating green leaves.
- `ov01_022006A8(ov01_021F146C(playerObject))` built as `test673.nds` and was stable. The screenshots showed the desired floating green/yellow leaf particles.
- The real headbutt interaction setup can reach the text "There's a large, formidable tree that looks like it can be headbutted!", but this verifier save does not currently have a natural Headbutt field-action path to the tree impact sequence.

Learning:

- The earlier direct `022006A8` crash was caused by passing a `LocalMapObject *` where the function expects an effect context.
- The safe path is to derive the context with `ov01_021F146C(object)` and then call `ov01_022006A8(effectContext)`.
- `02200540` remains part of the vanilla headbutt task neighborhood, but runtime screenshots show it is not the visible floating-leaf effect needed for canopy takeoff in this integration.

Implementation shape:

- Add `ov01_022006A8` and `ov01_022006C4` as long-call symbols.
- On canopy-hopper takeoff, call `ov01_022006A8(ov01_021F146C(object))`.
- Store the returned handle per wild-spawn slot.
- Tick a short cleanup timer through the existing frame movement task.
- Destroy the handle with `ov01_022006C4` after the leaf window or immediately on slot clear/context loss/task shutdown.
- Keep the player-move probe disabled (`OW_WILD_SPAWNER_PLAYER_MOVE_EFFECT_PROBE 0`) and keep the forced `L+R` diagonal RAM probe disabled in the final ROM.

Verification:

- Built the rejected `02200540` player-move probe successfully as `test672.nds`.
- Headless screenshots:
  - `documentation/verification_screenshots/headbutt_leaf_02200540_probe_01_early.png`
  - `documentation/verification_screenshots/headbutt_leaf_02200540_probe_02_mid.png`
- These showed an exclamation-style object effect, so `02200540` was rejected for canopy leaf takeoff.
- Built the corrected `022006A8(effectContext)` player-move probe successfully as `test673.nds`.
- Headless screenshots:
  - `documentation/verification_screenshots/headbutt_leaf_022006a8_context_probe_01_early.png`
  - `documentation/verification_screenshots/headbutt_leaf_022006a8_context_probe_02_mid.png`
  - `documentation/verification_screenshots/headbutt_leaf_022006a8_context_probe_03_late.png`
- These showed the floating green/yellow leaf particles and the game remained responsive.
- Built the temporary forced-hop verifier with `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RAM_PROBE 1` successfully as `test674.nds`.
- Headless `L+R+LEFT` verifier screenshots:
  - `documentation/verification_screenshots/canopy_takeoff_leaf_lr_probe_01_after_combo.png`
  - `documentation/verification_screenshots/canopy_takeoff_leaf_lr_probe_02_plus6.png`
  - `documentation/verification_screenshots/canopy_takeoff_leaf_lr_probe_03_late.png`
- These showed the same leaf particles during the forced-hop run and no freeze.
- Verified the failed probe calls are not referenced by active code: `rg -n "02200730|0220329C|PLAYER_MOVE_EFFECT_PROBE 1|ov01_02200730|ov01_0220329C" src include rom.ld` returned no matches.
- Disabled temporary probes again:
  - `OW_WILD_SPAWNER_PLAYER_MOVE_EFFECT_PROBE 0`
  - `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RAM_PROBE 0`
- Built final production ROM successfully with `./docker-makerom.cmd`.
- Copied the first final ROM to Delta as `test675.nds`.
- Removed the stale rejected `02200540` / `02200400` probe symbols and rebuilt.
- Copied the cleaned final ROM to Delta as `test676.nds`.
- Final clean headless sanity passed with `test.dsv` against `test676.nds`.
- Final screenshots:
  - `documentation/verification_screenshots/canopy_takeoff_leaf_final_clean_00_ready.png`
  - `documentation/verification_screenshots/canopy_takeoff_leaf_final_clean_01_after_move.png`
  - `documentation/verification_screenshots/canopy_takeoff_leaf_final_clean_02_late.png`
- These show stable ordinary movement with no player-move leaf probe, no `L+R` forced-hop probe side effects, no red target square, no spawned grass tile, no dark blob, and no dialog/emote artifact.

### Leaf Effect Probe: Vanilla Headbutt Task And `021FCB90` Direct Actor

Context:

- User is looking for the floating green leaf visual from vanilla Headbutt, not the puff/smoke, grass-tile replacement, musical note bubble, or sound-only tree startle effects.
- Direct `022006A8` is unsafe and previously caused a freeze. Do not retry that direct call.
- User liked `021FE66C` as a shiny-pokemon visual candidate, but it is not the Headbutt leaf effect.

Attempted:

- Added a one-shot player-move probe for `ov01_021FC748(fieldSystem, 0, 0)`, the high-level vanilla Headbutt visual task starter found in overlay 1 disassembly.
- Built `test663.nds`.
- Verified headless that the hook fired and did not crash (`triggers=2`, `started=1`), but the open-field visual did not show the requested leaf burst.
- Added a direct actor probe using `ov01_021FCB14`, `ov01_021FCB90`, `ov01_021FCBCC`, and `ov01_021FCB4C`, cycling animation ids `0x31` through `0x34`.
- Built `test664.nds`.
- Verified headless that the direct actor was stable, but it opened dialogue text ("Not even a nibble...") instead of rendering the leaf effect. This means the nearby `021FCB90` path is not the leaf particle renderer in this context.

Cleanup:

- Disabled `OW_WILD_SPAWNER_PLAYER_MOVE_EFFECT_PROBE` so the failed direct actor does not run in-game.
- Built `test665.nds`.
- Verified headless movement after disabling the probe; the bad dialogue side effect is gone.

Learning:

- The leaf effect is still not found.
- `021FC748` appears to require the real Headbutt interaction state to reach the impact visual states.
- `021FCB90` looked promising from the state machine but is wrong for this use; do not repeat it as a leaf probe without new evidence.
- Next useful direction is to capture/trace the real vanilla Headbutt interaction near an actual headbutt tree, then identify the effect actor created at the exact impact frame.

Runtime result:

- Pending.

Learning:

- Pending.

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

### Attempt 67: Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram

Idea:

Revise the behavior profile table again:

- Rename `restRate` back to `restTime`.
- Add `normalSpeed` so chill wandering can use one speed while attentive behavior uses `maxSpeed`.
- Make stamina tile-based: one completed attentive movement command spends one stamina, regardless of speed.
- Update default/aggressive/skittish values to the new table.
- Add `Playful` behavior for Aipom: normal wandering at speed 2, excited double-hop alert, playful chase, near-player circling, and occasional happy double-hop emotes.
- Add Onix as aggressive with an Onix-specific ram attentive state: alertness 14 in a facing cone, lock the initial direction toward the player, keep moving straight until blocked, ramp speed every 3 completed tiles up to speed 3, then crash back to chill.
- Force land test spawns to alternate Onix and Aipom by slot while leaving saved shiny respawns untouched.

Why this is new:

- Attempt 66 implemented the first table semantics but still had `restRate`, no `normalSpeed`, and stamina spending based on speed.
- No previous attempt has separated chill movement speed from attentive max speed.
- No previous attempt has made stamina count completed tiles.
- No previous attempt has added a playful near-player circling behavior.
- No previous attempt has implemented a locked-direction ram behavior with crash handling.
- No previous attempt has forced Onix/Aipom spawns for behavior testing.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built once as `test164.nds`, then removed an unused alert-bubble helper and rebuilt.
- Final build copied as `test165.nds`.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test165.nds`.
- `git diff --check` passed before the final build and after the final build.
- Verified local `test.nds` exists at 176 MB.
- Verified the Delta folder contains `test165.nds`.
- Verified no stale `restRate` or `REST_RATE` references remain.
- Verified land test spawns are forced to Onix on even slots and Aipom on odd slots, while saved shiny respawns are not overridden.
- Verified the overlay compiles with the new profile shape, Aipom playful behavior, and Onix ram behavior.
- Onix ram currently approximates ground smoke/crash feedback with `BIT_JUMP_START` plus sound effects. A direct C-side camera-shake API was not identified in this pass.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 68: Tune Onix Ram Start, Range, Crash State, And Feedback

Idea:

Refine the first Onix ram implementation after runtime feedback:

- Start Onix ram at speed 2 instead of speed 1.
- Give Onix an explicit movement range of 16 instead of inheriting the default range 8.
- Let Onix inherit the aggressive profile's water-droplet tired state and rest time, then enter tired state after a ram crash instead of returning directly to chill.
- Switch the ram step sound from `SEQ_SE_DP_DANSA` to the stronger boulder-like `SEQ_SE_DP_DANSA5`.
- Switch the crash sound from `SEQ_SE_DP_DODON` to `SEQ_SE_GS_DODON`.
- Move the `BIT_JUMP_START` ram-step feedback to after the ram walk command starts, so the walk-command setup is less likely to immediately overwrite the visual bit.

Why this is new:

- Attempt 67 introduced Onix ram but started at speed 1, left the object range at the default 8, disabled tired state through the Onix variable override, and set the jump bit before issuing the walk command.
- No previous attempt has made Onix ram enter the behavior tired state after crashing.
- No previous attempt has tested the `DANSA5`/`GS_DODON` sound pair for Onix ram feedback.
- The script macro layer exposes `ShakeOverworld` and `ShakeCamera`, but this attempt intentionally does not inject a field script from the movement frame task because that would add a larger timing risk than the requested profile/feedback tuning.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test166.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test166.nds`.
- `git diff --check` passed before the build.
- Verified Onix now overrides normal speed to `2`, max speed to `3`, range to `16`, and ram alertness to `14`.
- Verified Onix no longer overrides stamina, tired state, or rest time, so it inherits aggressive water-droplet tired behavior and rest timing.
- Verified the ram crash path clears ram direction/counters and calls `OverworldWildSpawns_StartTiredEmote` instead of setting the spot state directly to chill.
- Verified ram step feedback now uses `SEQ_SE_DP_DANSA5` and crash feedback now uses `SEQ_SE_GS_DODON`.

Runtime result:

- User reported no ground smoke, no thud, no screen shake, and no strength movement sound. The audible result sounded like the hop sound instead.

Learning:

- `BIT_JUMP_START` is likely the wrong primitive for Onix ram feedback. It can produce hop-like feedback, and moving it after the walk command did not make it behave like ground smoke or a crash effect.

### Attempt 69: Use Site Walk Commands And Scripted Crash Feedback For Onix Ram

Idea:

Replace the failed jump-bit feedback path with two different built-in systems:

- Use `Walk*FastSite` / `Walk*VeryFastSite` movement commands for Onix ram movement at speed 2 or higher, while leaving normal walking commands intact for other Pokemon behavior.
- Remove `BIT_JUMP_START` from Onix ram step and crash handling entirely, because Attempt 68 produced hop-like feedback instead of smoke/thud.
- Add common script `2075` / `scr_seq_0003_075_overworld_wild_ram_crash_feedback` for Onix ram crashes.
- On ram crash, schedule the common script from the movement field context when available.
- The crash script plays `SEQ_SE_GS_DODON`, runs `ShakeCamera 3, 3, 4, 2`, waits briefly, then ends.
- Keep the C-side crash sound fallback if there is no current movement field context.

Why this is new:

- Attempts 67 and 68 approximated Onix ground/crash feedback with `BIT_JUMP_START`; this attempt removes that bit from the ram path.
- No previous attempt has used `Walk*Site` movement commands for Onix ram movement.
- No previous attempt has added a dedicated common script for ram crash sound and screen shake.
- No previous attempt has scheduled a non-battle overworld wild common script from the movement frame task for feedback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/config.h`
- `armips/include/scriptmacros.s`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test167.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test167.nds`.
- `git diff --check` passed before the build.
- Verified the overlay compiles after removing `BIT_JUMP_START` from the Onix ram step and crash paths.
- Verified the script NARC rebuild accepts the new `scr_seq_0003_075_overworld_wild_ram_crash_feedback` common script.
- Verified Onix ram speed 2 and 3 movement now choose `Walk*FastSite` / `Walk*VeryFastSite` command families instead of the normal walk command families.

Runtime result:

- User reported Onix no longer moves.

Learning:

- The `Walk*FastSite` / `Walk*VeryFastSite` command families are not safe replacements for Onix ram movement on these spawned Pokemon.
- Do not use the `Walk*Site` command family for the active ram step path unless a future isolated test proves how to make it move.
- The dedicated crash common script has not been fairly tested yet, because Onix did not reach its moving/crashing state.

### Attempt 70: Restore Normal Ram Movement And Make Alertness A Facing Line

Idea:

Recover Onix ram movement by undoing the failed site-walk substitution while keeping the new non-jump crash script available:

- Remove the Onix ram use of `Walk*FastSite` / `Walk*VeryFastSite`.
- Make Onix ram use the same normal speed-based walk command path that moved correctly before Attempt 69.
- Keep the `BIT_JUMP_START` removal from Attempt 69, because Attempt 68 made the feedback sound/feel like a hop.
- Keep common script `2075` for crash thud and screen shake so it can be tested once Onix moves again.
- Change alertness checks from a facing cone to a straight line in front of the Pokemon.
- The line check only succeeds when the player is on the same row/column, in the Pokemon's facing direction, and within `profile.alertness`.

Why this is new:

- Attempt 66 introduced facing-cone alertness.
- Attempts 67 and 68 used cone-based Onix ram alertness.
- Attempt 69 tested site-walk ram movement and failed at runtime.
- No previous attempt has used a strict straight-line alertness check for the behavior-profile system.
- This deliberately avoids retrying `BIT_JUMP_START` and avoids retrying site-walk ram movement.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test168.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test168.nds`.
- `git diff --check` passed before the build.
- Verified Onix ram movement no longer uses the failed `Walk*Site` movement command family.
- Verified ram movement now calls the normal speed-based walk command selector again.
- Verified alert checks now use `OverworldWildSpawns_IsPlayerInFacingLine`, requiring the player to be directly in front of the Pokemon within `profile.alertness`.
- Verified the script NARC still accepts the existing `scr_seq_0003_075_overworld_wild_ram_crash_feedback` common script.

Runtime result:

- User reported Onix moves again.
- Onix still plays a hop-like sound each step.
- Onix still does not produce ground smoke.

Learning:

- Restoring the normal walk command family recovered ram movement.
- `SEQ_SE_DP_DANSA5` is not a good Onix ram step sound; in runtime it reads like the hop sound.
- Normal walk commands alone do not produce the desired ground smoke.
- Reference decomp inspection shows normal walk and site-walk commands both set the lower movement-start bit, so retrying only `BIT_MOVE_START` would not be meaningfully new.
- Reference decomp inspection shows `Walk*Site` commands differ from normal walk commands by movement timing/type parameters, including a site visual parameter of `5` for `Walk*FastSite`.
- Attempt 69 already proved whole `Walk*Site` movement commands are unsafe for Onix ram, but no prior attempt has kept normal walking while borrowing only the site visual parameter.

### Attempt 71: Keep Normal Ram Walking But Borrow Site Visual Parameter

Idea:

Preserve the movement path that works, while changing only the feedback pieces:

- Change Onix ram step sound from `SEQ_SE_DP_DANSA5` to stock `SEQ_SE_DP_DANSA`, because the reference decomp shows the heavy field movement helpers play `SEQ_SE_DP_DANSA`.
- Add a local import for the movement visual parameter setter at `sub_0205F328`.
- After the first update frame of an active Onix ram step, override the movement visual parameter to `5`, matching the value used by `Walk*FastSite`.
- Re-set the lower movement-start bit after that override so the renderer has a fresh chance to consume the site-style visual parameter.
- Do not use `BIT_JUMP_START`, because Attempt 68 produced hop-like behavior.
- Do not replace ram walking with `Walk*Site` commands, because Attempt 69 made Onix stop moving.

Why this is new:

- Attempt 68 used the jump flag and failed.
- Attempt 69 used whole `Walk*Site` movement commands and failed.
- Attempt 70 restored normal ram walking but left feedback wrong.
- No previous attempt has combined normal walk commands with only the site visual parameter override.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test169.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test169.nds`.
- `git diff --check` passed before the build.
- Verified the overlay compiles after importing `sub_0205F328` at `0x0205F328`.
- Verified Onix ram step sound now uses `SEQ_SE_DP_DANSA` instead of `SEQ_SE_DP_DANSA5`.
- Verified active ram movement still starts from the normal speed-based walk command path, not the failed `Walk*Site` command family.
- Verified the site visual parameter override is latched once per ram step and only runs for active ram Pokemon with speed `2` or higher.

Runtime result:

- User reported no visible or audible improvement.
- Onix still uses the hop-like sound each step.
- Onix still does not produce ground smoke.

Learning:

- The site visual parameter override did not reach the desired visible effect.
- Changing the explicit sound from `SEQ_SE_DP_DANSA5` to `SEQ_SE_DP_DANSA` did not remove the hop-like sound in runtime.
- Do not continue trying to get Onix ram dust through whole `Walk*Site` commands, `BIT_JUMP_START`, or the post-init site visual parameter override without new evidence.
- The next direction should bypass movement-command feedback and call a stock field-effect helper directly.

### Attempt 72: Direct Stock Ground-Dust Effect Without Step Sound

Idea:

Stop trying to trigger Onix ram dust through movement command flags:

- Remove the failed Attempt 71 site visual override and `sub_0205F328` import.
- Stop playing an explicit sound on every Onix ram step, because both tested `DANSA5` and `DANSA` read as hop-like in runtime.
- Import `ov01_021FD640`, a stock field-effect helper used by map-object movement effect logic for ground/step presentation.
- Call `ov01_021FD640(object)` directly when an Onix ram step starts at speed `2` or higher.
- Keep the normal walk command family that still makes Onix move.

Why this is new:

- Attempt 68 used `BIT_JUMP_START` and failed.
- Attempt 69 used whole `Walk*Site` commands and failed.
- Attempt 71 tried borrowing only the site visual parameter and failed.
- No previous attempt has directly called `ov01_021FD640` from the Onix ram step path.
- No previous Onix ram feedback attempt has removed the explicit per-step sound to isolate visual dust from audio.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test170.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test170.nds`.
- `git diff --check` passed before the build.
- Verified the overlay compiles and links after importing `ov01_021FD640` at `0x021FD640`.
- Verified `OverworldWildSpawns_PlayRamStepFeedback` calls `ov01_021FD640(object)` only for active ram Pokemon at speed `2` or higher.
- Verified the Onix ram path no longer plays an explicit per-step `PlaySE`.
- Verified the failed Attempt 71 `sub_0205F328` site-visual override was removed from active code.

Runtime result:

- User reported no sound and no smoke effect.

Learning:

- Removing the explicit per-step sound did remove sound.
- Directly calling `ov01_021FD640(object)` did not create visible smoke for spawned Onix ram movement.
- Do not retry direct `ov01_021FD640` as the Onix ram dust solution without new evidence.
- The known smoke-producing primitive remains `WaitJumpSite` (`0x65`) from Attempt 49.

### Attempt 73: Run WaitJumpSite After Each Onix Ram Step

Idea:

Use the command already proven to produce smoke, but isolate it from the ram walking command:

- Remove the failed direct `ov01_021FD640` call and import.
- Keep normal ram walking unchanged so Onix still moves.
- After an Onix ram walk command finishes at speed `2` or higher, count the ram step, update ram speed, then start a separate `WaitJumpSite` (`0x65`) single-movement command.
- Track `movementRamSmokeActive` per slot so the follow-up `WaitJumpSite` completion is not counted as another ram movement step.
- Do not add an explicit per-step sound yet; this attempt tests whether `WaitJumpSite` alone gives the desired smoke in the ram context.

Why this is new:

- Attempt 49 used `WaitJumpSite` as a spot emote and produced smoke, but did not use it in the Onix ram path.
- Attempt 68 used `BIT_JUMP_START` directly and failed.
- Attempt 69 used whole `Walk*Site` commands and failed.
- Attempt 71 used a site visual parameter override and failed.
- Attempt 72 called `ov01_021FD640` directly and failed.
- No previous attempt has inserted `WaitJumpSite` as a separate post-step Onix ram smoke command.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test171.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test171.nds`.
- `git diff --check` passed before the build.
- Verified the failed direct `ov01_021FD640` call and import are not active code.
- Verified the failed `sub_0205F328` site-visual override is not active code.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_SMOKE_COMMAND` is `0x65` (`WaitJumpSite`).
- Verified the ram path starts `WaitJumpSite` only after a ram walk command finishes at speed `2` or higher.
- Verified `movementRamSmokeActive` prevents the follow-up `WaitJumpSite` completion from being counted as another ram movement step.
- Verified no explicit per-step sound was added in this attempt, so this build isolates whether `WaitJumpSite` alone creates the ram smoke.

Runtime result:

- User reported that `WaitJumpSite` does not work for ram feedback because it stops Onix's movement each time the animation runs.

Learning:

- `WaitJumpSite` can produce a smoke-like presentation, but it is a movement command and takes over the same single-movement slot the ram step needs.
- Do not use post-step `WaitJumpSite` as Onix ram smoke; it creates a visible stop/start interruption.
- The next direction should keep normal ram movement active and layer the feedback as a side effect instead of as another movement command.

### Attempt 74: Direct Boulder Step Effect Helper During Normal Ram Movement

Idea:

Keep Onix on the normal ram walk commands that already move correctly, but layer a boulder-style side effect onto the start of each ram step:

- Remove the failed post-step `WaitJumpSite` ram command and its `movementRamSmokeActive` bookkeeping.
- Import `ov01_021FFF5C`, a stock overlay helper that attaches a small ground/step effect to a `LocalMapObject` without starting a movement command.
- When an active ram step starts at speed `2` or higher, call `ov01_021FFF5C(object, effectId)` from the current movement field context.
- Use ram speed clamped to `3` as the effect id for this test, because the helper's resource table has four valid effect slots and the stock movement-effect code uses small category ids.
- Play `SEQ_SE_DP_DANSA` at the same time, matching the sound emitted by the vanilla movement-command paths around `sub_02062958`/`sub_020632B0`.

Why this is new:

- Attempt 68 used `BIT_JUMP_START` and failed with hop-like feedback.
- Attempt 69 replaced ram movement with `Walk*Site` commands and made Onix stop moving.
- Attempt 71 borrowed only the site visual parameter through `sub_0205F328` and failed.
- Attempt 72 directly called `ov01_021FD640(object)` and failed.
- Attempt 73 used `WaitJumpSite` as a separate movement command and interrupted ram movement.
- No previous attempt has called `ov01_021FFF5C` directly from the Onix ram path while keeping the normal walk command active.

Files/symbols:

- `include/map_events_internal.h`
- `include/overworld_wild_spawns_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test172.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test172.nds`.
- `git diff --check` passed before the build.
- Verified the failed post-step `WaitJumpSite` ram follow-up path and `movementRamSmokeActive` bookkeeping are not active code.
- Verified `ov01_021FFF5C` is imported at `0x021FFF5C` and called from `OverworldWildSpawns_PlayRamStepFeedback`.
- Verified the direct effect call is guarded by the current movement field context and only runs for active ram Pokemon at speed `2` or higher.
- Verified Onix ram still starts the normal ram walk command before playing ram-step feedback, so this attempt keeps movement on the proven walking path.
- Verified per-step sound now uses `SEQ_SE_DP_DANSA`.

Runtime result:

- User reported a weird trail effect instead of smoke. Screenshot showed green/footprint-like trail marks following Onix's ram path.

Learning:

- `ov01_021FFF5C` successfully creates a side effect without stopping Onix, so the helper path itself is viable.
- Using ram speed as the effect id was wrong for the desired dust/smoke: speed `2`/`3` selects the later `0x66`/`0x67` effect resources, which present as a trail.
- Do not retry speed-derived effect ids with `ov01_021FFF5C` for Onix ram smoke.
- The stock movement-effect code maps command groups `0x0C-0x0F`, `0x10-0x13`, and `0x14-0x17` to effect ids `3`, `2`, and `1`, so fixed id `1` remains an untested direct-helper candidate.

### Attempt 75: Fixed Run-Style Boulder Effect Id

Idea:

Keep the successful nonblocking direct helper from Attempt 74, but stop deriving the effect id from ram speed:

- Replace the speed-clamped `ov01_021FFF5C` effect id with a fixed `OW_WILD_SPAWNER_ONIX_RAM_STEP_EFFECT_ID`.
- Set the fixed id to `1`, because vanilla movement-effect logic maps the `Run*` command group (`0x14-0x17`) to effect id `1`.
- Keep normal Onix ram walking unchanged.
- Keep the per-step `SEQ_SE_DP_DANSA` sound unchanged for this visual-only probe.

Why this is new:

- Attempt 74 called `ov01_021FFF5C` with speed-derived ids `2`/`3` and produced trail marks.
- Attempts 68-73 did not call `ov01_021FFF5C` with a fixed id.
- No previous attempt has tested fixed id `1`, the remaining stock movement-effect id that is used by the `Run*` command group.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test173.nds` and copied to Delta.
- Delta copy: `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test173.nds`.
- `git diff --check` passed before the build.
- Verified active ram step feedback calls `ov01_021FFF5C(object, OW_WILD_SPAWNER_ONIX_RAM_STEP_EFFECT_ID)`.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_STEP_EFFECT_ID` is fixed to `1`, not derived from ram speed.
- Verified normal Onix ram walking still starts before ram-step feedback plays.
- Verified the failed post-step `WaitJumpSite` ram follow-up path remains absent from active code.

Runtime result:

- User reported this produced a different-color trail, not smoke. Screenshot showed pale/grey trail marks following Onix's ram path.

Learning:

- Fixed id `1` is also a trail resource in practice.
- The `ov01_021FFF5C` helper appears to be the wrong visual family for Onix ram dust/smoke, even though it does not interrupt movement.
- Do not continue cycling `ov01_021FFF5C` ids for this effect without new evidence.
- `WaitJumpSite` command `101` calls `ov01_022000DC` before it starts the vertical/facing-vector wait animation, so the smoke-producing part can be separated from the movement-stopping part.

### Attempt 76: Direct WaitJumpSite Smoke Launcher During Ram Movement

Idea:

Keep Onix on the proven normal ram walk command, but borrow only the visual launcher from `WaitJumpSite`:

- Import `ov01_022000DC`, the helper called by `MapObjectMovementCmd101_Step0` (`WaitJumpSite`) before that command animates the object vertically.
- Replace the `ov01_021FFF5C` trail-family call with `ov01_022000DC(object)`.
- Do not start movement command `101`, do not set `movementRamSmokeActive`, and do not add any post-step movement command.
- Keep the per-step `SEQ_SE_DP_DANSA` sound unchanged for this first direct smoke-launcher test.

Why this is new:

- Attempt 73 started the full `WaitJumpSite` movement command after each ram step and interrupted Onix movement.
- Attempts 74 and 75 called `ov01_021FFF5C` and produced trail resources.
- No previous attempt has called `ov01_022000DC` directly from the ram path while keeping normal ram movement active.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the blocked build attempts.
- Verified active ram step feedback calls `ov01_022000DC(object)` instead of `ov01_021FFF5C`.
- Verified `ov01_022000DC` is imported at `0x022000DC`.
- Verified the failed post-step `WaitJumpSite` ram follow-up path remains absent from active code.
- Built as `test174.nds` and copied to Delta after Docker recovered.

Runtime result:

- User reported this still produced only a trail. Screenshot showed pale footprint-like decals along Onix's path, matching the same visual family as Attempts 74 and 75 rather than a short dust/smoke puff.

Learning:

- Direct `ov01_022000DC` is not the separated smoke-only primitive after all. It behaves like another decal/trail effect when called independently.
- Do not keep pursuing `ov01_021FFF5C`/`ov01_022000DC` for Onix ram dust without new evidence.

### Attempt 77: Try Adjacent Overlay Effect Constructor `ov01_02200040`

Idea:

Keep Onix on the proven normal ram walk command, but switch ram step feedback to the adjacent standalone overlay effect constructor at `0x02200040`:

- Import `ov01_02200040(LocalMapObject *mapObject)`.
- Replace the direct `ov01_022000DC(object)` call with `ov01_02200040(object)`.
- Keep the normal ram movement command active and do not start any `WaitJumpSite` or post-step movement command.
- Keep the explicit `SEQ_SE_DP_DANSA` ram step sound for this first visual probe.

Why this is new:

- Attempts 74 and 75 used `ov01_021FFF5C` and produced trail/decal resources.
- Attempt 76 used `ov01_022000DC` and also produced trail/decal resources.
- Attempt 73 used the full `WaitJumpSite` movement command and interrupted movement.
- No previous attempt has called the standalone constructor at `0x02200040`.
- Disassembly shows `0x02200040` initializes a different effect resource set (`9/10/11`) and descriptor table `0x022092A8`, while `0x022000DC` uses descriptor `0x02209294`.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test175.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_02200040(object)`.
- Verified `ov01_02200040` is imported at `0x02200040`.
- Verified active code no longer calls `ov01_022000DC(object)` for ram step feedback.

Runtime result:

- User reported the game freezes when Onix tries to move.

Learning:

- `ov01_02200040` is not safe to call with a `LocalMapObject *`. Disassembly shows it passes raw `r0` directly into `ov01_021F1430` and then uses that stored pointer as an effect/resource system, so the imported prototype was likely wrong.
- Do not call adjacent constructors that expect an effect-system pointer with a map object just because they are near the known map-object helpers.

### Attempt 78: Try Map-Object Anchored Effect Helper `ov01_02200730`

Idea:

Back away from the unsafe `ov01_02200040` constructor and try a different one-shot helper that visibly treats its input as a `LocalMapObject`:

- Import `ov01_02200730(LocalMapObject *mapObject)`.
- Replace the freeze-prone `ov01_02200040(object)` ram step call with `ov01_02200730(object)`.
- Keep the normal ram walk command active and do not start `WaitJumpSite` or any post-step movement command.
- Keep `SEQ_SE_DP_DANSA` for this probe so the visual change is isolated from the rest of the ram behavior.

Why this is new:

- Attempts 74 and 75 used `ov01_021FFF5C` and produced trail/decal resources.
- Attempt 76 used `ov01_022000DC` and also produced trail/decal resources.
- Attempt 77 used `ov01_02200040` and froze because it likely expects an effect-system pointer, not a map object.
- No previous attempt has called `ov01_02200730`.
- Disassembly shows `ov01_02200730` derives the effect context from the map object via `ov01_021F146C`, reads map-object data with ARM9 helpers, and launches descriptor table `0x02209308`, so this is a new map-object anchored effect path rather than another unsafe constructor call.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test176.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_02200730(object)`.
- Verified `ov01_02200730` is imported at `0x02200730`.
- Verified the unsafe `ov01_02200040` import was removed from active code.

Runtime result:

- User reported Onix now has a bright red outline / targeting square when it moves.
- Screenshot showed the rectangle attached around Onix rather than a ground dust/smoke effect.

Learning:

- `ov01_02200730` is a selection/target-outline style visual, not the strength boulder dust/smoke family.
- Do not use descriptor table `0x02209308` for ram step feedback.

### Attempt 79: Try Short-Lived Map-Object Effect Helper `ov01_021FF74C`

Idea:

Replace the red-outline helper with another map-object anchored effect helper:

- Import `ov01_021FF74C(LocalMapObject *mapObject)`.
- Replace `ov01_02200730(object)` in the ram step feedback path with `ov01_021FF74C(object)`.
- Keep the normal ram walk command active and do not start `WaitJumpSite` or any post-step movement command.
- Keep `SEQ_SE_DP_DANSA` for this probe so the visual change is isolated.

Why this is new:

- No previous attempt in this log has called `ov01_021FF74C`.
- Attempts 74 and 75 used `ov01_021FFF5C` and produced trail/decal resources.
- Attempt 76 used `ov01_022000DC` and also produced trail/decal resources.
- Attempt 77 used `ov01_02200040` and froze because it likely expects an effect-system pointer, not a map object.
- Attempt 78 used `ov01_02200730` and produced a red target/outline effect.
- Disassembly shows `ov01_021FF74C` derives context from the map object and launches a different descriptor table, `0x022091EC`, so this is not a repeat of the trail helpers or the red-outline helper.

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test177.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_021FF74C(object)`.
- Verified `ov01_021FF74C` is imported at `0x021FF74C`.
- Verified `ov01_02200730` was removed from active code imports/call sites.

Runtime result:

- User reported nothing visible happened.

Learning:

- `ov01_021FF74C` is not useful for Onix ram step feedback in this context.
- It is safe enough to call, but either its effect is invisible/subtle here or it is not a ground-smoke presentation.

### Attempt 80: Try Alternate Stock Ground Effect Helper `ov01_021FD684`

Idea:

Try the neighboring helper to the failed direct stock ground-dust effect:

- Import `ov01_021FD684(LocalMapObject *mapObject)`.
- Replace `ov01_021FF74C(object)` in the ram step feedback path with `ov01_021FD684(object)`.
- Keep the normal ram walk command active and do not start `WaitJumpSite` or any post-step movement command.
- Keep `SEQ_SE_DP_DANSA` for this probe so only the visual helper changes.

Why this is new:

- Attempt 72 called `ov01_021FD640(object)` directly and did not create visible smoke.
- No previous attempt in this log has called `ov01_021FD684`.
- Disassembly shows `ov01_021FD684` uses the same safe `LocalMapObject *` setup pattern as `ov01_021FD640`, but launches descriptor table `0x02208EC8` with a different launch argument instead of descriptor table `0x02208EA0`.
- This is not a repeat of the trail-family helpers (`ov01_021FFF5C` / `ov01_022000DC`), the unsafe constructor (`ov01_02200040`), the red-outline helper (`ov01_02200730`), or the no-visible-effect helper (`ov01_021FF74C`).

Files/symbols:

- `include/map_events_internal.h`
- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before the build.
- Built as `test178.nds` and copied to Delta.
- Verified active ram step feedback calls `ov01_021FD684(object)`.
- Verified `ov01_021FD684` is imported at `0x021FD684`.

Runtime result:

- User reported nothing was visible.

Learning:

- `ov01_021FD684` is safe enough to call in this context, but it does not create visible Onix ram step feedback.
- Do not use `ov01_021FD684` as the active ram smoke path unless new evidence shows it needs extra setup.

### Attempt 81: Add WaitJumpSite Flag Context Around `ov01_022000DC`

Idea:

Try the effect helper that `WaitJumpSite` calls again, but with the map-object flag context that stock `WaitJumpSite` applies:

- Keep Onix ram using the normal walk command.
- Before `ov01_022000DC(object)`, set map-object bits `0x00010004`.
- After the helper, clear map-object bit `0x00100000`.
- Do not start the `WaitJumpSite` movement command and do not advance the movement command state from the feedback path.
- Keep `SEQ_SE_DP_DANSA` for this probe so the visual setup is isolated.

Why this is new:

- Attempt 73 used full post-step `WaitJumpSite` and got smoke-like feedback, but it interrupted Onix ram movement.
- Attempt 76 called `ov01_022000DC(object)` directly and produced a trail/decal rather than smoke.
- No previous attempt has called `ov01_022000DC(object)` while applying only the stock `WaitJumpSite` set/clear bit context and leaving the current ram walk command active.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing symbols `MapObject_SetBits`, `MapObject_ClearBits`, and `ov01_022000DC`

Verification:

- `git diff --check` passed before the build.
- Built as `test179.nds` and copied to Delta.
- Verified active ram step feedback sets `0x00010004`, calls `ov01_022000DC(object)`, then clears `0x00100000`.
- Verified `MapObject_SetBits`, `MapObject_ClearBits`, and `ov01_022000DC` are already imported.

Runtime result:

- User reported the smoke effect is in.

Learning:

- Applying the stock `WaitJumpSite` map-object flag context around `ov01_022000DC(object)` creates the desired Onix ram smoke without interrupting ram movement.
- The active visual path should keep this `MapObject_SetBits` / `ov01_022000DC` / `MapObject_ClearBits` structure while sound is tuned separately.

### Attempt 82: Use HGSS Push Sound For Onix Ram Steps

Idea:

Keep the successful Attempt 81 smoke path and change only the explicit ram step sound:

- Add `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`.
- Set it to `SEQ_SE_GS_PUSH02`, one of the HGSS `PUSH` sound effects near the field/rock sound constants.
- Replace the per-step `PlaySE(SEQ_SE_DP_DANSA)` call with `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Why this is new:

- Attempts 68, 71, and later visual probes used `SEQ_SE_DP_DANSA5` or `SEQ_SE_DP_DANSA`, and the runtime result sounded hop-like/wrong.
- No previous Onix ram attempt has used either `SEQ_SE_GS_PUSH02` or `SEQ_SE_GS_PUSH03`.
- The local sound table names `PUSH02` / `PUSH03` make this a better candidate for the strength-boulder push sound than cycling more `DANSA` variants.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_PUSH02`

Verification:

- `git diff --check` passed before the build.
- Built as `test180.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now uses `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`, defined as `SEQ_SE_GS_PUSH02`.

Runtime result:

- User reported no sound played.

Learning:

- `SEQ_SE_GS_PUSH02` is not a usable Onix ram step sound through this direct C `PlaySE` path, at least in the current overworld context.
- Keep the successful smoke path intact and continue sound probes separately.

### Attempt 83: Try Paired HGSS Push Sound `SEQ_SE_GS_PUSH03`

Idea:

Keep the successful Attempt 81 smoke path and change only the explicit ram step sound from the silent push candidate to its paired neighbor:

- Keep `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`.
- Change it from `SEQ_SE_GS_PUSH02` to `SEQ_SE_GS_PUSH03`.
- Leave the smoke effect, ram movement, and crash feedback unchanged.

Why this is new:

- Attempt 82 tested `SEQ_SE_GS_PUSH02` and it produced no audible sound.
- No previous Onix ram attempt has used `SEQ_SE_GS_PUSH03`.
- `SEQ_SE_GS_PUSH03` is the only other locally named HGSS `PUSH` sound, so testing it completes the named push pair before moving to rockfall/trap candidates like `IWAOTOSHI` or `IWA_TRAP`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_PUSH03`

Verification:

- `git diff --check` passed before the build.
- Built as `test181.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now uses `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`, defined as `SEQ_SE_GS_PUSH03`.

Runtime result:

- User reported no sound played.

Learning:

- `SEQ_SE_GS_PUSH03` is also not audible through the direct C `PlaySE` path in the current overworld context.
- SDAT inspection showed both push sounds are real SSEQ entries, not missing constants:
  - `SEQ_SE_GS_PUSH02`: bank `770`, player `3`, volume `100`, event data present.
  - `SEQ_SE_GS_PUSH03`: bank `770`, player `4`, volume `127`, event data present.
- Bank `770` uses wave archives `[700, 770]`; this suggests the silence may be because direct `PlaySE` does not load the extra bank/wave archive needed by these HGSS push sounds in the field context.

### Attempt 84: Load Push Sequence Before Playing It

Idea:

Keep the successful Attempt 81 smoke path and keep the current `SEQ_SE_GS_PUSH03` sound candidate, but explicitly load the sequence before playing it:

- Call `GF_Snd_LoadSeq(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.
- Then call `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.
- Leave ram movement, smoke, and crash feedback unchanged.

Why this is new:

- Attempts 82 and 83 only called `PlaySE` directly for `SEQ_SE_GS_PUSH02` and `SEQ_SE_GS_PUSH03`.
- SDAT inspection shows those push sounds exist but use bank `770` and wave archive `770`, unlike known direct-play field/global sounds such as `SEQ_SE_DP_KON` / `SEQ_SE_DP_DANSA`, which use bank `700`.
- No previous Onix ram attempt has explicitly loaded the selected step sound sequence before playing it.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing function `GF_Snd_LoadSeq`
- Existing sound constant `SEQ_SE_GS_PUSH03`

Verification:

- `git diff --check` passed before the build.
- Built as `test182.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now calls `GF_Snd_LoadSeq(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)` before `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Runtime result:

- User reported no sound played.

Learning:

- `GF_Snd_LoadSeq` alone is not enough to make `SEQ_SE_GS_PUSH03` audible in this field context.
- This supports the idea that the missing piece is bank/wave loading rather than the SSEQ itself.

### Attempt 85: Load Push Sound With `NNS_SND_ARC_LOAD_ALL`

Idea:

Keep the successful Attempt 81 smoke path and current `SEQ_SE_GS_PUSH03` sound candidate, but use the extended sound-archive load path:

- Expose `GF_Snd_LoadSeqEx` in `include/sound.h`.
- Mark `GF_Snd_LoadSeqEx` as `LONG_CALL` in `src/sound.c` so overlay code can call it safely.
- Replace `GF_Snd_LoadSeq(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)` with `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)`.
- Then call `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Why this is new:

- Attempt 84 loaded only the sequence before playback and still produced no sound.
- `NNS_SND_ARC_LOAD_ALL` requests sequence, bank, and wave data, which targets the SDAT finding that `SEQ_SE_GS_PUSH03` uses bank `770` and wave archive `770`.
- No previous Onix ram attempt has used `GF_Snd_LoadSeqEx` or `NNS_SND_ARC_LOAD_ALL`.

Files/symbols:

- `include/sound.h`
- `src/sound.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_PUSH03`

Verification:

- `git diff --check` passed before the build.
- Built as `test183.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now calls `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)` before `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Runtime result:

- User reported no sound played.

Learning:

- Full sequence/bank/wave loading was not enough to make `SEQ_SE_GS_PUSH03` audible in this field context.
- The named `PUSH` pair has now failed through direct playback, sequence-only loading, and full archive loading.
- Avoid more `PUSH02` / `PUSH03` retries unless new evidence identifies a different required caller or player setup.

### Attempt 86: Try Field Rock Sound `SEQ_SE_GS_IWAOTOSHI02`

Idea:

Keep the successful Attempt 81 smoke path and the safer full sound-archive load path, but change the sound candidate away from the silent `PUSH` bank:

- Change `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE` from `SEQ_SE_GS_PUSH03` to `SEQ_SE_GS_IWAOTOSHI02`.
- Keep `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)`.
- Keep `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)` after the load call.

Why this is new:

- Attempts 82 through 85 only tested the named HGSS `PUSH` pair and loading variants for `PUSH03`.
- No previous Onix ram attempt has used `SEQ_SE_GS_IWAOTOSHI`, `SEQ_SE_GS_IWAOTOSHI01`, `SEQ_SE_GS_IWAOTOSHI02`, or `SEQ_SE_GS_IWA_TRAP`.
- SDAT inspection showed `SEQ_SE_GS_IWAOTOSHI02` uses the field rock bank `750` and field player `3`, while `SEQ_SE_GS_PUSH03` uses bank `770` and player `4`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_IWAOTOSHI02`
- Existing function `GF_Snd_LoadSeqEx`
- Existing constant `NNS_SND_ARC_LOAD_ALL`

Verification:

- `git diff --check` passed before the build.
- Built as `test184.nds` and copied to Delta.
- Verified active ram step feedback still uses the successful Attempt 81 smoke path.
- Verified active ram step sound now uses `OW_WILD_SPAWNER_ONIX_RAM_STEP_SE`, defined as `SEQ_SE_GS_IWAOTOSHI02`.
- Verified the sound path still calls `GF_Snd_LoadSeqEx(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE, NNS_SND_ARC_LOAD_ALL)` before `PlaySE(OW_WILD_SPAWNER_ONIX_RAM_STEP_SE)`.

Runtime result:

- User reported the Onix ram step sound works.

Learning:

- `SEQ_SE_GS_IWAOTOSHI02` is a usable Onix ram step sound in this field context when loaded with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)`.
- Keep the successful smoke path and this field rock sound for active ram steps.

### Attempt 87: Promote `aggressive_ram` Behavior And Strengthen Crash Feedback

Idea:

Make ram a first-class behavior profile instead of an Onix-specific variable patch, and make crash presentation explicit:

- Add `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`.
- Add a non-hop angry alert state, `OW_WILD_BEHAVIOR_ALERT_STATE_SPEECH_ANGRY`.
- Move Onix from `AGGRESSIVE` plus variable overrides to the new `AGGRESSIVE_RAM` behavior class.
- Put the ram alertness, ram attentive state, stamina, tired state, rest time, normal speed, max speed, and range directly in the behavior class override.
- Make `AGGRESSIVE_RAM` alert with only the angry speech bubble and the Pokemon cry, not a hop.
- Play the crash thud from C with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep the common crash script for camera shake, and make it stronger/more visible.

Why this is new:

- Earlier Onix ram builds used `AGGRESSIVE` behavior with a species-specific variable override for ram values.
- No previous attempt has introduced `AGGRESSIVE_RAM` as a behavior class.
- Attempt 69 added a crash script with sound and a light camera shake, but it did not use the newer full archive load path for the crash thud and did not promote ram into the behavior hierarchy.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing script `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`
- Existing sound constant `SEQ_SE_GS_DODON`

Verification:

- `git diff --check` passed before the build.
- Built as `test185.nds` and copied to Delta.
- Verified Pidgey still maps to `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE`.
- Verified Onix maps to `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`.
- Verified `AGGRESSIVE_RAM` profile owns ram alertness, ram attentive state, stamina, tired state, rest time, normal speed, max speed, and range.
- Verified the non-hop angry speech alert shows the angry bubble and plays the Pokemon cry.
- Verified crash feedback loads `SEQ_SE_GS_DODON` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified the crash script now only handles the stronger `ShakeCamera 5, 4, 8, 2` presentation.

Runtime result:

- User reported no crash sound or shake.

Learning:

- `SEQ_SE_GS_DODON` is still silent in this field context even when loaded with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)`.
- The common script's `ShakeCamera 5, 4, 8, 2` path did not produce visible crash feedback.
- Avoid retrying `SEQ_SE_GS_DODON` or `ShakeCamera` for Onix ram crashes unless new evidence shows a missing caller/context requirement.

### Attempt 88: Use Field Wall-Hit Sound And Shake The Crashed Overworld Object

Idea:

Replace the failed crash-feedback path with two signals that have not been tested on ram crashes:

- Change the crash thud from `SEQ_SE_GS_DODON` to `SEQ_SE_GS_TOUMEINAKABEHIT`.
- Keep the successful full sound-archive load path before playing the crash thud.
- Store the crashed spawned object's object ID in `VAR_SPECIAL_x8004` from C before scheduling the crash feedback script.
- Change the crash feedback script from `ShakeCamera` to `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`.
- Add `lockall` / `releaseall` around the crash feedback script so the object-shake command has a normal script envelope.

Why this is new:

- Attempt 87 fairly tested `SEQ_SE_GS_DODON` plus `ShakeCamera`; both failed at runtime.
- No previous Onix ram attempt has used `SEQ_SE_GS_TOUMEINAKABEHIT`, the named HGSS transparent-wall-hit sound.
- No previous Onix ram attempt has passed a spawned object ID into a script variable and used `ShakeOverworld` on that object.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing script `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`
- Existing script variable `VAR_SPECIAL_x8004`
- Existing sound constant `SEQ_SE_GS_TOUMEINAKABEHIT`

Verification:

- `git diff --check` passed before the build.
- Built as `test186.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_TOUMEINAKABEHIT` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified `OverworldWildSpawns_PlayRamCrashFeedback` writes the crashed object's ID into `VAR_SPECIAL_x8004` before scheduling `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`.
- Verified the crash script now uses `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2` inside `lockall` / `releaseall`.

Runtime result:

- User reported the crash causes the player to freeze while other Pokemon still move.
- User also reported the sound plays, but it is not the desired thud.

Learning:

- `SEQ_SE_GS_TOUMEINAKABEHIT` is audible in this field context with the current C-side full-load sound path, but it has the wrong character for Onix crashing.
- `ShakeOverworld` with `lockall`, `wait`, and `releaseall` likely leaves player input locked or stuck in a script wait even though the movement frame task continues to move other spawned Pokemon.
- Do not retry a locked/waiting `ShakeOverworld` common script for ram crash feedback.

### Attempt 89: Non-Locking Object Shake And `SEQ_SE_DP_GASHIN` Crash Thud

Idea:

Keep the object-ID handoff from Attempt 88, but remove the script envelope that can freeze the player and try a different impact sound:

- Change the crash thud from `SEQ_SE_GS_TOUMEINAKABEHIT` to `SEQ_SE_DP_GASHIN`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep writing the crashed spawned object's object ID to `VAR_SPECIAL_x8004`.
- Change the crash script to call `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`, then end immediately.
- Remove `lockall`, `wait`, and `releaseall` from the crash script.

Why this is new:

- Attempt 88 proved the locked/waiting `ShakeOverworld` script can freeze the player and that `SEQ_SE_GS_TOUMEINAKABEHIT` is the wrong sound.
- No previous Onix ram attempt has tested `SEQ_SE_DP_GASHIN`.
- No previous Onix ram attempt has tested `ShakeOverworld` as a fire-and-finish script without locking player input or waiting on a script result.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `armips/scr_seq/scr_seq_00003_commonscript.s`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing script `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`
- Existing script variable `VAR_SPECIAL_x8004`
- Existing sound constant `SEQ_SE_DP_GASHIN`

Verification:

- `git diff --check` passed before the build.
- Built as `test187.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_DP_GASHIN` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified the crash script still uses `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`, but now ends immediately without `lockall`, `wait`, or `releaseall`.

Runtime result:

- User reported no crash feedback or sound from this build.
- User also requested that future attempts do not lock out the player or other Pokemon.

Learning:

- Removing `lockall`, `wait`, and `releaseall` avoided the player-lock problem from Attempt 88.
- `SEQ_SE_DP_GASHIN` did not produce the desired audible crash sound in this field context.
- Keep future ram-crash feedback on non-locking/non-waiting paths.

### Attempt 90: Non-Locking Object Shake And HGSS Gondola Wall-Hit Sound

Idea:

Keep the non-locking crash script from Attempt 89 and try a field-bank HGSS impact sound:

- Change the crash thud from `SEQ_SE_DP_GASHIN` to `SEQ_SE_GS_GONDORA_KABEHIT`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep the `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2` script as a fire-and-finish script with no `lockall`, no `wait`, and no `releaseall`.

Why this is new:

- Attempt 89 tested the non-locking script shape with `SEQ_SE_DP_GASHIN`, which was not audible.
- No previous Onix ram attempt has used `SEQ_SE_GS_GONDORA_KABEHIT`.
- `SEQ_SE_GS_GONDORA_KABEHIT` uses the HGSS field sound family rather than the silent DP impact sound path, while still avoiding the already-wrong `SEQ_SE_GS_TOUMEINAKABEHIT`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_GONDORA_KABEHIT`

Verification:

- `git diff --check` passed before the build.
- Built as `test188.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_GONDORA_KABEHIT` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified the crash script remains non-locking: `ShakeOverworld VAR_SPECIAL_x8004, 5, 4, 8, 2`, then `endstd` / `end`.

Runtime result:

- User reported the sound now plays and is acceptable, but should be more impactful.
- User reported no screen shake.
- User reported the player still locks afterward.

Learning:

- `SEQ_SE_GS_GONDORA_KABEHIT` is audible and usable as a fallback crash thud, but it is not quite impactful enough.
- Even a fire-and-finish common script with only `ShakeOverworld` can still leave the player locked after ram crash feedback.
- Treat crash feedback field-script scheduling as unsafe for now; remove `EventSet_Script` from ram crash feedback before further sound auditions.

### Attempt 91: Sound-Only `SEQ_SE_GS_IWA_TRAP` Crash Feedback

Idea:

Remove the crash feedback script path entirely and try a stronger rock-field sound:

- Change the crash thud from `SEQ_SE_GS_GONDORA_KABEHIT` to `SEQ_SE_GS_IWA_TRAP`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Stop writing a script object ID to `VAR_SPECIAL_x8004`.
- Stop calling `EventSet_Script` for `OVERWORLD_WILD_SPAWNS_RAM_CRASH_FEEDBACK_SCRIPT`.
- Leave the crash common script uncalled for this checkpoint.

Why this is new:

- Attempts 88 through 90 all scheduled a field script for crash feedback and produced either player lock or no visible screen shake.
- No previous Onix ram attempt has used `SEQ_SE_GS_IWA_TRAP` as the ram crash sound.
- This is the first crash-feedback checkpoint that fully removes script scheduling from `OverworldWildSpawns_PlayRamCrashFeedback`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_IWA_TRAP`

Verification:

- `git diff --check` passed before the build.
- Built as `test189.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_IWA_TRAP` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified `OverworldWildSpawns_PlayRamCrashFeedback` only plays the C-side thud and no longer calls `EventSet_Script` or writes `VAR_SPECIAL_x8004`.

Runtime result:

- User reported this sound was worse.
- User also reported no shake.

Learning:

- `SEQ_SE_GS_IWA_TRAP` is not a good Onix ram crash sound; it is worse than `SEQ_SE_GS_GONDORA_KABEHIT`.
- The no-shake result is expected because this checkpoint intentionally removed script-based shake to avoid player lock.
- Keep crash feedback script scheduling disabled while auditioning additional sounds.

### Attempt 92: Sound-Only `SEQ_SE_GS_IWAOTOSHI01` Crash Feedback

Idea:

Keep the stable sound-only crash-feedback path and try a different field-rock impact:

- Change the crash thud from `SEQ_SE_GS_IWA_TRAP` to `SEQ_SE_GS_IWAOTOSHI01`.
- Keep `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Keep crash feedback script scheduling disabled.

Why this is new:

- Attempt 91 tested sound-only crash feedback with `SEQ_SE_GS_IWA_TRAP`, which sounded worse.
- `SEQ_SE_GS_IWAOTOSHI02` works as the ram step sound, but `SEQ_SE_GS_IWAOTOSHI01` has not been tested as the ram crash sound.
- This keeps the no-script crash path that avoids the player-lock problem from Attempts 88 through 90.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- Existing sound constant `SEQ_SE_GS_IWAOTOSHI01`

Verification:

- `git diff --check` passed before the build.
- Built as `test190.nds` and copied to Delta.
- Verified crash feedback now loads `SEQ_SE_GS_IWAOTOSHI01` with `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- Verified crash feedback script scheduling remains disabled.

Runtime result:

- User reported this sound was worse.
- User reported no screen shake.

Learning:

- `SEQ_SE_GS_IWAOTOSHI01` is not a good Onix ram crash sound.
- The no-shake result is expected because crash feedback script scheduling remains disabled.
- Return to the previously acceptable `SEQ_SE_GS_GONDORA_KABEHIT` sound and keep screen shake out of the crash feedback path for now.

### Attempt 93: Restore Decent Crash Sound And Shorten Speech-Only Alert

Idea:

Keep the stable, non-locking crash feedback path and address the latest feel issues:

- Restore the ram crash sound from `SEQ_SE_GS_IWAOTOSHI01` to the previously acceptable `SEQ_SE_GS_GONDORA_KABEHIT`.
- Keep screen shake disabled; do not schedule any crash feedback field script.
- Add a separate speech-only alert timer so non-hop alerts such as aggressive_ram's mad speech bubble plus cry do not wait for the full jump-emote duration.
- Leave hop-alert timing unchanged to avoid regressing the working jump animation.

Why this is new:

- Attempt 90 used `SEQ_SE_GS_GONDORA_KABEHIT` together with a script-scheduled shake path, which still locked the player.
- Attempts 91 and 92 removed script scheduling while auditioning different crash sounds.
- No previous attempt has combined the stable sound-only feedback path with `SEQ_SE_GS_GONDORA_KABEHIT`.
- No previous attempt has split speech-only alert timing from hop alert timing.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE`
- `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test191.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE` now resolves to `SEQ_SE_GS_GONDORA_KABEHIT`.
- Verified crash feedback still only loads and plays the thud; the only remaining `EventSet_Script` call in the overlay is the battle-start path.
- Verified speech-only spot emotes now use `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES` / `24` frames instead of `OW_WILD_SPAWNER_SPOT_EMOTE_FRAMES_PER_JUMP` / `64` frames.
- Verified hop-alert timing remains unchanged.

Runtime result:

- User reported there is still no screen shake.

Learning:

- The no-shake result is expected because Attempt 93 intentionally kept crash feedback sound-only.
- The user still wants visible shake feedback, so the next attempt should add visual crash feedback without reusing script-scheduled `ShakeCamera` or `ShakeOverworld`.

### Attempt 94: C-Side Ram Crash Object Wobble

Idea:

Add a visible, reversible crash wobble without scheduling a field script:

- Keep the crash thud as `SEQ_SE_GS_GONDORA_KABEHIT`.
- Keep `EventSet_Script` out of ram crash feedback.
- Store the crashed object's original `posVec[0]` and `posVec[2]`.
- For 18 frames, offset the crashed object diagonally by a small fixed-point amount from the existing movement frame task.
- Restore the original render position when the wobble ends or when the slot resets/clears.

Why this is new:

- Attempts 87 through 90 tested `ShakeCamera` or `ShakeOverworld` through a common script and produced no visible shake and/or player lock.
- Attempt 91 through Attempt 93 removed script scheduling entirely and were sound-only.
- Attempt 48 tried a vertical `posVec[1]` hop bob for alert presentation, but no previous attempt has tried a short post-crash X/Z wobble on the ram object itself.
- This does not call `EventSet_Script`, does not use `ShakeCamera`, and does not use `ShakeOverworld`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementRamCrashShakeTimers`
- `OverworldWildSpawns_StartRamCrashShake`
- `OverworldWildSpawns_TickRamCrashShake`

Verification:

- `git diff --check` passed before the build.
- Built as `test192.nds` and copied to Delta.
- Verified the crash thud remains `SEQ_SE_GS_GONDORA_KABEHIT`.
- Verified the ram crash path calls `OverworldWildSpawns_StartRamCrashShake` and still does not schedule a crash feedback field script.
- Verified `OverworldWildSpawns_FrameMovementTask` advances `OverworldWildSpawns_TickRamCrashShake`.
- Verified slot reset restores any active ram crash wobble before clearing the shake state.

Runtime result:

- User reported this did nothing visible and also clarified this was not the desired effect.
- The requested effect is an actual screen shake, not wobbling the crashed object or adding another non-screen visual.

Learning:

- Manual X/Z `posVec` wobble is not a useful substitute for screen shake.
- Remove this code and do not retry object-wobble crash feedback unless the requested effect changes.
- The next attempt should trace or call the underlying camera/screen shake routine directly instead of scheduling field scripts or offsetting the object.

### Attempt 95: Direct Camera Shake Work Driven By SysTask

Idea:

Trace the actual `ShakeCamera` script command instead of scheduling it again:

- Field script command `561` points to `0x02201A50` in overlay 1.
- That handler reads four script parameters and calls `0x02246714` in overlay 2 with `fieldSystem->taskman`.
- `0x02246714` creates a camera-shake work object through `0x02246744`, then schedules a `TaskManager` task at `0x02246798`.
- The task updates the shake via `0x0224663C`, restores via `0x0224662C`, and frees via `0x02246534`.

For this attempt, bypass both `EventSet_Script` and the `TaskManager_Call` wrapper:

- Add linker names for the lower-level camera-shake work functions.
- Create the same camera-shake work directly on Onix ram crash.
- Drive it from a small `SysTask`.
- Restore/free the shake work when it finishes or when movement/map context resets.
- Keep the existing `SEQ_SE_GS_GONDORA_KABEHIT` crash thud.

Why this is new:

- Attempts 87 through 90 scheduled common scripts using `ShakeCamera` or `ShakeOverworld`; they produced no visible shake and/or player lock.
- Attempt 94 offset the crashed object's render position, which the user correctly rejected as not a screen shake.
- No previous attempt has traced command `561` to the lower-level overlay-2 camera-shake work functions or driven those functions directly from a spawner-owned `SysTask`.
- This follows the successful follower-bubble lesson: bypass the vanilla task/script wrapper when the direct lower-level effect creator is available.

Files/symbols:

- `rom.ld`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `FieldCamera_CreateShakeWork` / `0x02246744`
- `FieldCamera_UpdateShakeWork` / `0x0224663C`
- `FieldCamera_RestoreShakeWork` / `0x0224662C`
- `FieldCamera_FreeShakeWork` / `0x02246534`
- `OverworldWildSpawns_StartRamCrashScreenShake`
- `OverworldWildSpawns_RamCrashScreenShakeTask`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test193.nds` and copied to Delta.
- Verified the rejected Attempt 94 object-wobble state was removed from `OverworldWildSpawnState`.
- Verified the ram crash path no longer calls `OverworldWildSpawns_StartRamCrashShake` / `OverworldWildSpawns_TickRamCrashShake`.
- Verified `rom.ld` exposes the direct camera-shake work functions at `0x02246744`, `0x0224663C`, `0x0224662C`, and `0x02246534`.
- Verified `OverworldWildSpawns_PlayRamCrashFeedback` still plays the accepted `SEQ_SE_GS_GONDORA_KABEHIT` thud and now starts `OverworldWildSpawns_StartRamCrashScreenShake` only when the movement field context is current.
- Verified the only remaining `EventSet_Script` call in the overlay is the battle-start path, not ram crash feedback.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- User clarified that the screen-shake direction should be abandoned.
- User also clarified the object-wobble attempt did work, but was too subtle.

Learning:

- Retire the direct camera-shake work path for now.
- Reintroduce object wobble as the requested crash feedback, but make it much more obvious.
- Keep the crash feedback out of `EventSet_Script`, `ShakeCamera`, `ShakeOverworld`, and the direct camera-shake work functions.

### Attempt 96: Stronger Ram Crash Object Wobble And Shorter Speech Alert

Idea:

Return to the working Attempt 94 presentation, but tune it for visibility:

- Remove the direct camera-shake work symbols and task from Attempt 95.
- Re-add slot-owned ram crash wobble state.
- Store the crashed object's original `posVec[0]` and `posVec[2]`.
- Wobble the crashed object for 32 frames instead of 18 frames.
- Use a larger `3/8` tile fixed-point X/Z offset so the feedback is not barely visible.
- Restore the original render position when the wobble ends or when the slot/movement state resets.
- Shorten speech-only alert timing from 24 frames to 8 frames so aggressive_ram starts moving sooner after its mad bubble and cry.

Why this is new:

- Attempt 94 used object wobble, but the amplitude/duration were too subtle.
- Attempt 95 tried the direct camera-shake work path; the user asked to abandon screen shake.
- No previous attempt has tested the working object-wobble path with a deliberately stronger amplitude and the shorter speech-only alert state.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `rom.ld`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementRamCrashShakeTimers`
- `OverworldWildSpawns_StartRamCrashShake`
- `OverworldWildSpawns_TickRamCrashShake`
- `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test194.nds` and copied to Delta.
- Verified the direct camera-shake work symbols were removed from active code and `rom.ld`.
- Verified the ram crash path calls `OverworldWildSpawns_StartRamCrashShake` again.
- Verified `OverworldWildSpawns_FrameMovementTask` advances `OverworldWildSpawns_TickRamCrashShake`.
- Verified slot reset restores active ram crash wobble before clearing movement/spot state.
- Verified `OW_WILD_SPAWNER_SPOT_EMOTE_SPEECH_FRAMES` is now `8`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 97: Aggressive Ram Rest-Only Tired State

Idea:

Keep aggressive_ram's tired/rest timing, but remove its tired visual cue:

- Add a `NO_VISUAL` tired state distinct from `NONE`.
- Set the aggressive_ram behavior profile's tired state to `NO_VISUAL`.
- Let `StartTiredEmote` still put the slot into `OW_WILD_SPAWNER_SPOT_STATE_TIRED` and start the rest timer.
- If the tired state is `NO_VISUAL`, skip the water-droplet bubble and fallback tired animation, then let `TickTiredEmote` count down normally.

Why this is new:

- Setting tired state to `NONE` would skip the tired/rest phase, which is not what the user asked for.
- Earlier tired-state attempts focused on finding the right bubble/icon, and aggressive_ram previously used the water-droplet tired visual.
- No previous attempt has created a rest-only tired state that preserves cooldown/rest behavior while intentionally showing no visual cue.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_BEHAVIOR_TIRED_STATE_NO_VISUAL`
- `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`
- `OverworldWildSpawns_StartTiredEmote`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test195.nds` and copied to Delta.
- Verified `OW_WILD_BEHAVIOR_TIRED_STATE_NO_VISUAL` is distinct from `OW_WILD_BEHAVIOR_TIRED_STATE_NONE`.
- Verified aggressive_ram now uses `OW_WILD_BEHAVIOR_TIRED_STATE_NO_VISUAL` instead of `OW_WILD_BEHAVIOR_TIRED_STATE_WATER_DROPLET`.
- Verified `OverworldWildSpawns_StartTiredEmote` still sets `OW_WILD_SPAWNER_SPOT_STATE_TIRED` and starts the rest timer before skipping the visual presentation for `NO_VISUAL`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 98: Restore Smaller Ram Crash Wobble Offset

Idea:

Keep the restored object-wobble feedback, but return its offset to the earlier subtle value:

- Keep the 32-frame wobble duration from Attempt 96.
- Change `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FX32_AMPLITUDE` from `3/8` tile to `1/8` tile.
- Leave the ram crash thud, tired-state flow, and no-screen-shake decision unchanged.

Why this is new:

- Attempt 96 deliberately boosted the offset to `3/8` tile after the old wobble seemed too subtle.
- The user now specifically asked to return only the offset to the previous version.
- No new screen-shake path is involved.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FX32_AMPLITUDE`

Verification:

- `git diff --check` passed before and after the build.
- Built as `test196.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FX32_AMPLITUDE` is now `OW_WILD_SPAWNER_FX32_ONE / 8`.
- Verified `OW_WILD_SPAWNER_RAM_CRASH_SHAKE_FRAMES` remains `32`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 99: Player Wall-Hit Ram Crash Sound

Idea:

Change the aggressive ram crash sound to the same sound family used when the player bumps into a wall:

- Change `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE` from `SEQ_SE_GS_GONDORA_KABEHIT` to `SEQ_SE_DP_WALL_HIT`.
- Keep the no-script crash feedback path, object wobble, no screen shake, and aggressive_ram tired-state flow unchanged.

Why this is new:

- Earlier crash-sound attempts tried `SEQ_SE_GS_DODON`, `SEQ_SE_GS_TOUMEINAKABEHIT`, `SEQ_SE_DP_GASHIN`, `SEQ_SE_GS_GONDORA_KABEHIT`, `SEQ_SE_GS_IWA_TRAP`, and `SEQ_SE_GS_IWAOTOSHI01`.
- `SEQ_SE_GS_TOUMEINAKABEHIT` was a transparent-wall-hit sound and was already proven audible but wrong for Onix crash feedback.
- `SEQ_SE_DP_WALL_HIT` is the direct player wall-bump sound constant, has not been used in this ram crash path before, and matches the user's requested sound more closely than the transparent-wall variant.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE`
- `SEQ_SE_DP_WALL_HIT`

Verification:

- `git diff --check` passed before the build.
- Built as `test197.nds` and copied to Delta.
- Verified `OW_WILD_SPAWNER_ONIX_RAM_CRASH_SE` now resolves to `SEQ_SE_DP_WALL_HIT`.
- Verified the crash feedback path still uses `GF_Snd_LoadSeqEx(..., NNS_SND_ARC_LOAD_ALL)` before `PlaySE`.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 100: Ram Crash-Only Automatic Battle Trigger

Idea:

Make `aggressive_ram` stop using the generic automatic contact-battle detector. Ram should only self-start a battle when its straight-line attentive movement crashes into the player or the active follower Pokemon. The universal A-button facing interaction remains unchanged and can still start battles with any spawned Pokemon.

Implementation shape:

- Remove `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE` from the generic `OverworldWildSpawns_TryStartBattle` touch loop.
- Pass the active `FieldSystem *` into `OverworldWildSpawns_TryStartRamMovementCommand`.
- When ram movement is blocked, predict the tile in front of the ram from its current tile plus ram direction.
- If that blocked tile is the player tile or the active follower object's tile, call `OverworldWildSpawns_TryStartBattleForSlot`.
- If the blocked tile is anything else, keep the existing crash feedback and tired-state behavior without starting a battle.

Why this is new:

- Attempts 35 and 36 tuned generic contact timing after movement settled, but still treated ram as an automatic contact battle behavior.
- Attempt 65 added the universal A-button facing interaction, but did not change ram's automatic battle condition.
- Attempt 67 introduced Onix ram movement, but its battle behavior was still represented as `RAM_START_BATTLE` and later shared the generic touch detector.
- No previous attempt has made ram's automatic battle trigger depend on the ram crash target, and no previous attempt has included follower Pokemon as a ram crash battle target.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryStartRamMovementCommand`
- `OverworldWildSpawns_TryStartBattleForRamCrash`
- `OverworldWildSpawns_TryStartBattle`
- `fieldSystem->followMon.mapObject`

Verification:

- `git diff --check` passed before the build.
- Built as `test198.nds` and copied to Delta.
- Verified `OverworldWildSpawns_TryStartBattle` now only includes `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_CHASE_START_BATTLE` in the generic automatic touch battle loop.
- Verified `OverworldWildSpawns_TryStartRamMovementCommand` receives the active `FieldSystem *`.
- Verified ram blocked-direction handling still calls `OverworldWildSpawns_EndRamCrash`, then calls `OverworldWildSpawns_TryStartBattleForRamCrash` only for the predicted blocked tile.
- Verified `OverworldWildSpawns_TryStartBattleForRamCrash` checks the predicted tile against the player tile and the active follower object's tile.
- Verified `OverworldWildSpawns_TryStartBattleFromAButton` remains unchanged, so the universal A-button interaction still starts battles.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- User reported the player crash trigger works, but crashing into the follower Pokemon does not start a battle.

Learning:

- The ram crash battle path and predicted player tile check are sound.
- The follower miss is likely in follower object lookup or follower active-state detection, not in `OverworldWildSpawns_TryStartBattleForSlot`.
- Do not rely only on `fieldSystem->followMon.active` for this ram crash target check without more evidence that it is valid in this context.

### Attempt 101: Follower Object-ID Fallback For Ram Crash Battles

Idea:

Keep the working player ram crash trigger from Attempt 100, but make follower detection less dependent on `fieldSystem->followMon.active`:

- Define the vanilla follower map-object id as `253`, matching `obj_partner_poke` / `Following` in `armips/include/scriptmacros.s`.
- First try `fieldSystem->followMon.mapObject`, but require only that the pointer belongs to the current map-object table, is active, and occupies the predicted crash tile.
- If that direct pointer check misses, scan the current map-object table for an active object with id `253` on the predicted crash tile.
- Keep the generic automatic touch battle loop ram-free, and keep the universal A-button interaction unchanged.

Why this is new:

- Attempt 100 required `fieldSystem->followMon.active` before accepting the follower object as a ram crash battle target.
- Runtime proved player crash battles work while follower crash battles do not, pointing specifically at follower lookup/active-state detection.
- Earlier attempts used follower APIs for shiny palette and speech bubbles, but no previous ram crash attempt has identified the follower by its vanilla object id.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_FOLLOWER_OBJECT_ID`
- `OverworldWildSpawns_IsRamCrashBattleTarget`
- `fieldSystem->followMon.mapObject`
- `LocalMapObject::id`

Verification:

- `git diff --check` passed before the build.
- Built as `test199.nds` and copied to Delta.
- Verified `OW_WILD_FOLLOWER_OBJECT_ID` is defined as `253`, matching `obj_partner_poke` / `Following` in `armips/include/scriptmacros.s`.
- Verified `OverworldWildSpawns_IsRamCrashBattleTarget` no longer depends on `fieldSystem->followMon.active`.
- Verified the direct follower pointer path still requires the follower object to be current, active, and on the predicted crash tile.
- Verified the fallback scans the current map-object table for an active object with id `253` on the predicted crash tile.
- The build still emitted the pre-existing unused diagnostics warnings, but completed successfully.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 103: Behavior-Gated Ledge Far Jump

Idea:

Let spawned overworld Pokemon jump over one-tile ledges when their behavior profile allows it. Add a profile variable, `jumpLevel`, so default behavior can allow jumps while specific behavior classes or variable overrides can disable or restrict jumping later.

Implementation shape:

- Add `jumpLevel` to `OverworldWildBehaviorProfile`.
- Add `OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL` to the normal behavior override hierarchy.
- Default `jumpLevel` to `2`, meaning all current Pokemon profiles can jump both downhill and uphill.
- Define:
  - `0`: no ledge jump ability.
  - `1`: downhill ledges only.
  - `2`: downhill and uphill ledges.
- Detect HGSS one-tile ledge metatile behaviors `56..59`.
- Before issuing normal movement, check whether the adjacent tile is a ledge.
- If it is a ledge, check the tile after the ledge; if that landing tile is blocked, occupied, or out of bounds, treat the movement as blocked.
- If the ledge direction is allowed by `jumpLevel` and the landing tile is valid, issue the far-jump movement command family from base command `0x38`.
- Route normal wandering/chasing/fleeing/playful movement, untangle movement, and aggressive ram movement through the same ledge decision.
- For aggressive ram, a failed/disabled ledge jump is treated like a crash.

Why this is new:

- The movement log had no previous ledge-jump attempt.
- Previous jump work was alert/emote hopping in place, using the in-place jump command family.
- This approach uses the far-jump command family and a map collision/landing validation pass before movement starts.
- It avoids changing the fragile custom movement descriptor path; the spawner still owns movement decisions.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `jumpLevel`
- `OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL`
- `OW_WILD_BEHAVIOR_JUMP_LEVEL_NONE`
- `OW_WILD_BEHAVIOR_JUMP_LEVEL_DOWNHILL`
- `OW_WILD_BEHAVIOR_JUMP_LEVEL_BOTH`
- `OW_WILD_SPAWNER_MOVEMENT_LEDGE_JUMP_COMMAND`
- `OverworldWildSpawns_TryStartLedgeJumpCommand`
- `OverworldWildSpawns_IsValidLedgeLandingTile`
- `OverworldWildSpawns_StartMovementCommandForSlot`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test201.nds`.
- Verified `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c` compiled with only the existing unused-diagnostic warnings.
- Verified `jumpLevel` defaults to `OW_WILD_BEHAVIOR_JUMP_LEVEL_BOTH`, so all current behavior profiles inherit bidirectional ledge jumping unless an override sets `OW_WILD_BEHAVIOR_OVERRIDE_JUMP_LEVEL`.
- Verified ledge detection uses HGSS one-tile ledge behaviors `56..59`, and successful jumps issue the far-jump movement command family from base command `0x38`.
- Verified failed or disabled ledge jumps are treated as blocked movement, including the aggressive-ram path.
- Verified untangle movement no longer filters blocked directions before the ledge helper, so ledge jumps can still be considered there.
- Audited movement coverage after the user clarified this should work for all movement, including chase and flee:
  - active chase uses `OverworldWildSpawns_DiagnosticBuildDirections(dx, dy, directions)` and then calls `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - active flee negates `dx/dy`, builds directions the same way, and then calls `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - active playful movement builds playful directions and then calls `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - chill wander and untangle also call `OverworldWildSpawns_TryStartSpawnerMovementCommand`;
  - aggressive ram has its own direct `OverworldWildSpawns_TryStartLedgeJumpCommand` call before its normal blocked check.
- Confirmed the older `src/overworld_wild_movement.c` custom chase/flee path still contains direct movement-command code, but `OW_WILD_CUSTOM_MOVEMENT_DIAGNOSTIC_IDLE` keeps that descriptor in no-op mode in the current build; the active behavior system is owned by `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.

Runtime result:

- Pending user test.

Learning:

- The implementation is build-clean and ready for runtime ledge testing.
- Landing validation currently checks map blockage and object occupancy, but not terrain/pool compatibility. If runtime testing shows Pokemon jumping onto inappropriate terrain, add a terrain compatibility check to `OverworldWildSpawns_IsValidLedgeLandingTile`.

### Attempt 106: Aipom-Only Playful Chase Pass

Idea:

Focus the test build on playful behavior by spawning only Aipom, reducing cry spam, and replacing the playful near-player random sidestep with a more deliberate adjacent-target chase.

Implementation shape:

- Force behavior test spawns to `SPECIES_AIPOM` instead of alternating Aipom and Onix.
- Suppress ambient overworld cries during this focused playful test pass.
- Play Pokemon cries only for alert-state hops; speech-only alerts and later non-alert hop experiments should not play cries.
- Disable the current playful chill/active random hop presentation for now, because the new attentive movement should be tested without hop noise.
- Track the tile a spawn leaves from when the spawner starts a movement command.
- While playful is active and adjacent to the player, choose directions that move toward a different cardinal-adjacent tile around the player, excluding the spawn's current tile and the tile it just came from.
- Let the existing shared movement starter try those directions in order, so blocked paths and ledge cases fall through to the next candidate.

Why this is new:

- Earlier playful attempts added random near-player side movement and occasional active hops.
- No previous attempt has made playful orbit around adjacent player tiles while avoiding immediate backtracking.
- No previous attempt has made cries alert-hop-only while suppressing ambient cry spam for a focused playful test.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before build.
- First build copied `test203.nds`, but exposed new avoidable warnings from zero-percent playful hop checks and disabled ambient cries.
- Cleaned the warning sources by compiling out disabled playful hop branches and compiling out the ambient cry player while `OW_WILD_STEP_DIAGNOSTIC_SKIP_AMBIENT_CRY` is enabled.
- Final build with `./docker-makerom.cmd` succeeded and copied the ROM to Delta as `test204.nds`.
- Verified behavior test spawns now force `SPECIES_AIPOM`.
- Verified ambient cries are disabled for this focused pass.
- Verified `movementEmotePlayCryOnHop` lets alert-hop emotes play cries, while speech-only alerts and manual/non-alert hop paths do not play cries.
- Verified playful active movement now calls the new `OverworldWildSpawns_BuildPlayfulDirections` with state, field system, and slot context.
- Verified playful movement stores the tile a spawn leaves from in `movementPreviousTileX/Y`, then excludes that tile while choosing next adjacent-target directions.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 111: Revert Playful Attentive Speed Rhythm

Idea:

Remove Attempt 110's speed-rhythm experiment and return playful attentive movement to the profile's normal active speed.

Implementation shape:

- Remove the playful attentive speed-cycle constants.
- Remove `OverworldWildSpawns_GetPlayfulAttentiveSpeed`.
- Remove the playful-only active-speed branch from `OverworldWildSpawns_GetMovementWalkCommand`.
- Leave playful stamina `48`, no-backtracking guards, Aipom-only test spawns, and cry behavior unchanged.

Why this is new:

- This is an explicit revert of Attempt 110 after runtime feel testing, not another speed-rhythm variant.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test209.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:38 timestamp.
- Verified no active source symbols remain for `OW_WILD_SPAWNER_PLAYFUL_ATTENTIVE_SPEED_2_STEPS`, `OW_WILD_SPAWNER_PLAYFUL_ATTENTIVE_SPEED_3_STEPS`, or `OverworldWildSpawns_GetPlayfulAttentiveSpeed`.
- Verified `OverworldWildSpawns_GetMovementWalkCommand` again uses `profile.normalSpeed` while chill, ram speed for active ram movement, and `profile.maxSpeed` for other active movement including playful.

Runtime result:

- Pending user test of reverted feel.

Learning:

- Attempt 110 is now removed from active source. Keep the rejection recorded so future playful tuning does not repeat the exact 3/6 speed rhythm by accident.

### Attempt 119: Eight-Way Orbit Neighbor Filter

Idea:

Make playful "next to" mean all 8 neighboring tiles around the player/follower, and make orbit movement hard-reject candidate moves that increase the closest player/follower neighbor distance. Once Aipom is next to a target, it may move around the target, but it may not move away from the player/follower ring and may not move to the previous tile.

Implementation shape:

- Replace `OverworldWildSpawns_IsCardinalAdjacentToTarget` with `OverworldWildSpawns_IsPlayfulNeighboringTarget`.
- Change `OverworldWildSpawns_GetPlayfulTargetDistance` to use Chebyshev/8-way distance instead of Manhattan distance.
- Expand the target-adjacent offset table in `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance` from 4 cardinal offsets to 8 neighboring offsets.
- Treat `currentAnyTargetDistance <= 1` as already next to the player/follower.
- In orbit mode, hard-reject candidate directions whose closest 8-way target distance is greater than the current closest 8-way target distance.
- Keep previous-tile hard rejection, target-tile rejection, movement command execution, ledge handling, speed, stamina, alertness, and Aipom-only test spawning unchanged.

Why this is new:

- Earlier playful attempts treated adjacency as cardinal-only in the orbit target ring.
- Attempt 118 split approach/orbit priority but still treated `currentAnyTargetDistance == 1` as adjacency using the old distance helper.
- No previous attempt has defined playful adjacency as the full 8 neighboring tiles while hard-filtering orbit moves that increase 8-way distance from the player/follower.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsPlayfulNeighboringTarget`
- `OverworldWildSpawns_GetPlayfulTargetDistance`
- `OverworldWildSpawns_GetClosestPlayfulAdjacentTargetDistance`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test217.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 23:52 timestamp.
- Verified active source contains `OverworldWildSpawns_IsPlayfulNeighboringTarget` and no longer contains `OverworldWildSpawns_IsCardinalAdjacentToTarget`.
- Verified active source uses an 8-entry target-neighbor offset table.
- Verified orbit mode hard-rejects candidates when `closestAnyTargetDistance > currentAnyTargetDistance`.

Runtime result:

- User requested a deterministic playful emote: every 5 movement steps while next to the player/follower, the Pokemon should hop.

Learning:

- The next attempt should add a separate neighbor-step counter instead of reusing attentive stamina, so playful orbit flavor does not shorten/extend tired-state timing.

### Attempt 120: Playful Orbit Hop Every Five Neighbor Steps

Idea:

When a playful Pokemon is already next to the player or follower Pokemon, count completed movement steps in that neighboring ring. On every fifth completed neighboring step, start a silent in-place hop emote, then resume the active playful state.

Implementation shape:

- Add `movementPlayfulNeighborSteps` to `OverworldWildSpawnState`.
- Add `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS` set to `5`.
- Compile `OverworldWildSpawns_TryStartManualHopEmote` even when random playful hop chances are `0`, while leaving those random hop paths disabled.
- Add `OverworldWildSpawns_IsPlayfulNeighboringAnyTarget` using the existing 8-way player/follower target list and Chebyshev distance.
- Add `OverworldWildSpawns_TryHandlePlayfulOrbitStep`, called after a spawner-owned movement command finishes in active playful state.
- Reset the new counter when the Pokemon is no longer next to a player/follower target, enters chill/tired/alert state, resets movement state, or respawns into a slot.
- Keep alert-state hop cries unchanged; the periodic orbit hop is silent and has no speech bubble.

Why this is new:

- Earlier playful hop work used random chill/active hop chance constants, both currently disabled.
- Previous playful movement attempts changed approach/orbit direction choice, adjacency semantics, and previous-tile filtering, but none added a deterministic "completed steps while adjacent" emote cadence.
- Reusing `movementActiveSteps` would repeat the stamina/tired-state mechanism and risk changing tired timing; this attempt adds a separate counter.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `movementPlayfulNeighborSteps`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS`
- `OverworldWildSpawns_IsPlayfulNeighboringAnyTarget`
- `OverworldWildSpawns_TryHandlePlayfulOrbitStep`
- `OverworldWildSpawns_TryStartManualHopEmote`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test218.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:01 timestamp.
- Verified active source contains `movementPlayfulNeighborSteps`, `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS`, and `OverworldWildSpawns_TryHandlePlayfulOrbitStep`.

Runtime result:

- User reported that the orbit-mode hard filter from Attempt 119 likely was not the right feel; moves that increase distance from the player/follower should be lowest priority rather than impossible.

Learning:

- Deterministic hops are separate from the orbit direction priority issue.
- The next attempt should preserve hard previous-tile and target-tile blocks, but make "move away from the player/follower ring" a low-priority fallback instead of a hard reject.

### Attempt 121: Penalize Playful Orbit Moves Away Instead of Rejecting

Idea:

Keep playful orbit's preference for staying next to the player/follower, but allow candidate moves that increase the closest 8-way distance as a last resort. This should reduce the chance of Aipom getting stuck or doing awkward local loops when every ideal orbit tile is blocked, while still making near-player/follower movement the dominant behavior.

Implementation shape:

- Add `OW_WILD_SPAWNER_PLAYFUL_MOVE_AWAY_SCORE_PENALTY`.
- In `OverworldWildSpawns_BuildPlayfulDirections`, remove the hard `continue` that rejected orbit candidates when `closestAnyTargetDistance > currentAnyTargetDistance`.
- Add the new move-away penalty to those candidates after the normal orbit score is computed.
- Keep target-tile rejection and previous-tile rejection as hard blocks.
- Keep approach-mode scoring, 8-way adjacency, deterministic five-step hop behavior, movement execution, stamina, ledges, and Aipom-only test spawning unchanged.

Why this is new:

- Attempt 119 made orbit mode hard-reject moves that increase 8-way target distance.
- Earlier playful scoring attempts allowed looser movement, but did not combine the current 8-way adjacency semantics with a specific "move away is allowed but lowest priority" orbit penalty.
- This is not a reversion to pre-119 behavior; it keeps the current neighbor model and only softens one rejection into scoring.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_MOVE_AWAY_SCORE_PENALTY`
- `OverworldWildSpawns_BuildPlayfulDirections`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test219.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:04 timestamp.
- Verified active source contains `OW_WILD_SPAWNER_PLAYFUL_MOVE_AWAY_SCORE_PENALTY` and scores move-away orbit candidates instead of rejecting them.

Runtime result:

- User requested more organic playful hop expression: exact every-five-step hops felt robotic, and hop sequences should sometimes double-hop and sometimes show one heart/smile bubble after the sequence.

Learning:

- The next attempt should keep the same adjacent-step hook point, but randomize cadence and presentation without changing alert-state cry behavior.

### Attempt 122: Randomized Playful Orbit Hop Expression

Idea:

Make playful adjacent hop emotes feel less robotic by randomizing when they happen, occasionally making the hop sequence a double hop, and sometimes showing one friendly speech bubble after the hop sequence.

Implementation shape:

- Replace exact `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_STEPS` timing with:
  - `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MIN_STEPS` = `4`;
  - `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MAX_STEPS` = `7`;
  - `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_CHANCE_PERCENT` = `45`.
- Add `OW_WILD_SPAWNER_PLAYFUL_ORBIT_DOUBLE_HOP_CHANCE_PERCENT` = `25`.
- Add `OW_WILD_SPAWNER_PLAYFUL_ORBIT_BUBBLE_CHANCE_PERCENT` = `45`.
- Add helper functions:
  - `OverworldWildSpawns_ShouldStartPlayfulOrbitHop`;
  - `OverworldWildSpawns_GetPlayfulOrbitJumpCount`;
  - `OverworldWildSpawns_GetPlayfulOrbitBubbleId`.
- Split `OverworldWildSpawns_TickSpotEmote` bubble display from cry playback so silent manual hops can still display bubbles.
- Keep `movementEmoteShowBubbleEachJump` false for playful orbit hops, so double-hop sequences display at most one bubble after the final hop.
- Keep alert-state hops playing cry; playful orbit hops remain silent.

Why this is new:

- Attempt 120 added exact five-step deterministic orbit hops with no bubble.
- Earlier random hop chance constants were for old chill/active random paths and are still disabled.
- No previous attempt has randomized the deterministic adjacent-step hook while adding sequence-level heart/smile bubble presentation.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MIN_STEPS`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_MAX_STEPS`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_HOP_CHANCE_PERCENT`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_DOUBLE_HOP_CHANCE_PERCENT`
- `OW_WILD_SPAWNER_PLAYFUL_ORBIT_BUBBLE_CHANCE_PERCENT`
- `OverworldWildSpawns_ShouldStartPlayfulOrbitHop`
- `OverworldWildSpawns_GetPlayfulOrbitJumpCount`
- `OverworldWildSpawns_GetPlayfulOrbitBubbleId`
- `OverworldWildSpawns_TickSpotEmote`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test220.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:13 timestamp.
- Verified active source contains the randomized orbit hop timing, double-hop chance, bubble chance, and sequence-level bubble helper.

Runtime result:

- User asked that the hop timing should not restart when Aipom loses orbiting/adjacent state.

Learning:

- The randomized hop timer still resets when Aipom temporarily leaves the neighboring ring, which can make orbit expression feel delayed after reacquiring the player/follower.
- The next attempt should pause the timer while out of orbit instead of clearing it, while still clearing it for invalid map context, state resets, tired state, alert starts, and respawns.

### Attempt 123: Pause Playful Hop Timer Outside Orbit

Idea:

When playful Aipom temporarily leaves the 8-way neighboring ring around the player/follower, preserve its current hop-timer progress instead of restarting from zero. The timer should only advance while actually orbiting/neighboring, but leaving and re-entering orbit should resume from the previous count.

Implementation shape:

- Split the guard in `OverworldWildSpawns_TryHandlePlayfulOrbitStep`.
- If the movement `FieldSystem *` is no longer current, still clear `movementPlayfulNeighborSteps`.
- If the Pokemon is merely not neighboring any playful target, return without incrementing or clearing `movementPlayfulNeighborSteps`.
- Keep counter reset after a hop sequence starts, and keep existing resets for full movement-state reset, tired state, alert start, chill handling, and respawn.
- Keep randomized 4-7 step timing, double-hop chance, heart/smile bubble chance, and silent orbit hops unchanged.

Why this is new:

- Attempt 120 reset the neighbor-step counter whenever the Pokemon was no longer next to a player/follower target.
- Attempt 122 randomized the hop timing but kept that reset behavior.
- No previous attempt has treated the adjacent-hop timer as paused while out of orbit.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryHandlePlayfulOrbitStep`
- `movementPlayfulNeighborSteps`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test221.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:22 timestamp.
- Verified active source clears the hop timer for invalid movement field context but preserves it when the Pokemon is merely not neighboring a playful target.

Runtime result:

- User reported the chase/orbit/rechase behavior is almost perfect, but Aipom sometimes loses direction completely, chases the wrong way, or spins the wrong way.
- User suspects ledge jumps may be involved, though it may also be another scoring/history issue.

Learning:

- The next focused change should inspect ledge interactions before changing the general orbit/chase priority rules again.
- A concrete mismatch exists: playful direction scoring evaluates the one-tile candidate, but the movement executor can turn that same direction into a two-tile ledge jump.

### Attempt 124: Score Playful Ledge Jumps By Landing Tile

Idea:

Make playful chase/orbit direction scoring evaluate the tile the Pokemon will actually reach. If a direction would trigger a ledge jump, score the two-tile landing position instead of the ledge tile one step away.

Implementation shape:

- Add `OverworldWildSpawns_TryGetPlayfulMovementDestination`.
- For normal movement, return the one-step destination.
- For ledge movement, check the behavior profile's `jumpLevel`, validate the landing tile with `OverworldWildSpawns_IsValidLedgeLandingTile`, and return the two-step landing destination.
- In `OverworldWildSpawns_BuildPlayfulDirections`, score candidate directions using this helper destination.
- Exclude invalid ledge jumps from the scored direction list.
- Keep the existing hard previous-tile rejection, target-tile rejection, 8-way target adjacency, orbit move-away penalty, randomized hop timing, and hop timer pause behavior unchanged.

Why this is new:

- Ledge jumping was added before, but the playful scorer still evaluated one-tile destinations.
- No previous attempt has aligned playful target scoring with the actual two-tile destination used by ledge jump execution.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryGetPlayfulMovementDestination`
- `OverworldWildSpawns_BuildPlayfulDirections`
- `OverworldWildSpawns_TryStartLedgeJumpCommand`
- `OverworldWildSpawns_IsValidLedgeLandingTile`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test222.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:32 timestamp.
- Verified active source contains `OverworldWildSpawns_TryGetPlayfulMovementDestination`, and `OverworldWildSpawns_BuildPlayfulDirections` now scores candidate moves through that helper destination.

Runtime result:

- User found another clue: when the player runs and then stops, Aipom can act weird as if the player/follower position was not updated coherently.
- This suggests the remaining wrong-direction/spin issue may be caused by target coordinates changing mid-movement, not only by ledge destination scoring.

Learning:

- The next focused test should keep the movement executor unchanged and make playful target selection more tolerant of in-flight player/follower map-object positions.

### Attempt 125: Include Moving Target Trail For Playful Scoring

Idea:

When the player or follower Pokemon is actively moving, playful movement should treat that target as occupying a tiny two-tile trail: its current tile plus its previous tile. This should make Aipom less likely to snap to the wrong side when the player runs and stops, or when the follower is still catching up.

Implementation shape:

- Increase `OW_WILD_SPAWNER_PLAYFUL_TARGET_MAX` from `2` to `6`.
- Add `OverworldWildSpawns_TryAddPlayfulMapObjectTargets`.
- For a player/follower map object, always add `MapObject_GetCurrentX/Y`.
- If that target object reports `MapObject_IsSingleMovementActive`, also add `object->xPrev/yPrev` when it is valid and differs from the current tile.
- Resolve the player through `fieldSystem->playerAvatar->mapObject` when possible, falling back to `GetPlayerXCoord/YCoord`.
- Resolve follower targets through both the direct `fieldSystem->followMon.mapObject` path and the follower object-id fallback, using the same current-plus-previous trail helper.
- Keep the playful movement command executor, ledge landing scorer, hard previous-tile block, target-tile block, orbit penalties, speed, stamina, and hop logic unchanged.

Why this is new:

- Attempt 112 added player/follower target selection, but only with one current tile per target.
- Attempt 124 aligned ledge scoring with the actual ledge landing tile, but did not change player/follower target freshness.
- Earlier attempts found spawned Pokemon `xPrev/yPrev` unreliable for their own no-backtrack bookkeeping, but no attempt has used player/follower `xPrev/yPrev` only while those target objects are actively moving.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_PLAYFUL_TARGET_MAX`
- `OverworldWildSpawns_TryAddPlayfulMapObjectTargets`
- `OverworldWildSpawns_BuildPlayfulTargets`
- `MapObject_IsSingleMovementActive`
- `LocalMapObject::xPrev`
- `LocalMapObject::yPrev`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test223.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:41 timestamp.
- Verified active source contains `OverworldWildSpawns_TryAddPlayfulMapObjectTargets`, the playful target cap is `6`, and `OverworldWildSpawns_BuildPlayfulTargets` now adds current-plus-previous target tiles for moving player/follower map objects.

Runtime result:

- User agreed the moving player/follower trail probably should be default handling for other behavior/state logic that relies on calculating the player's position.

Learning:

- Attempt 125 only helped playful scoring. The next change should promote the moving-target trail helper to shared movement intent, while keeping exact tile checks for battles, spawn placement, and despawn distance.

### Attempt 127: Double Playful Movement Range

Idea:

Let Playful Pokemon roam/chase/orbit within twice the normal movement leash, so Aipom can keep its playful behavior active over a larger local area.

Implementation shape:

- Add `OW_WILD_SPAWNER_PLAYFUL_RANGE` as `OW_WILD_SPAWNER_MOVEMENT_RANGE * 2`.
- Give the Playful behavior class an explicit `OW_WILD_BEHAVIOR_OVERRIDE_RANGE`.
- Set Playful's profile range to `OW_WILD_SPAWNER_PLAYFUL_RANGE`.
- Leave Playful alertness, stamina, speed, target scoring, ledge handling, orbit hops, and battle rules unchanged.

Why this is new:

- Earlier attempts widened the shared movement range from `2` to `8`.
- Onix/aggressive_ram later received its own explicit range override.
- No previous attempt has given Playful an explicit doubled range override.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `OW_WILD_SPAWNER_PLAYFUL_RANGE`
- `OW_WILD_BEHAVIOR_CLASS_PLAYFUL`
- `OW_WILD_BEHAVIOR_OVERRIDE_RANGE`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test225.nds`.
- Verified active source defines `OW_WILD_SPAWNER_PLAYFUL_RANGE` as twice `OW_WILD_SPAWNER_MOVEMENT_RANGE`.
- Verified the Playful behavior class now sets `OW_WILD_BEHAVIOR_OVERRIDE_RANGE` and uses `OW_WILD_SPAWNER_PLAYFUL_RANGE`.

Runtime result:

- Pending user test.

Learning:

- Pending.

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
