# Battle Handoff And Interaction Rules

> **Status: historical attempt collection.** Use it as evidence, not current
> design. Start at [`overworld-system/README.md`](overworld-system/README.md).

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Tracks how overworld spawns enter battle: contact, frame-task retry, A button, ram crash, phantom visibility gates, and cleanup.
- Battle should not start while a spawner-owned movement command is unstable unless the behavior explicitly supports it.
- Pending-slot setup, cleanup on flee/defeat, and materializing visible phantom tiles are the central safety points.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 2 | 2 | Chase Logic Using `object->fsys` |
| 9 | 9 | Disable Spawner Step Actions After Map-State Refresh |
| 14 | 14 | UpdateMapState Map Writes Without Clear |
| 18 | 18 | Re-enable Map-State Writes After LONG_CALL Fix |
| 19 | 19 | Re-enable Stale-Slot Cleanup Only |
| 20 | 20 | Re-enable Distance Despawn Only |
| 21 | 21 | Re-enable Touch-Battle Detection Only |
| 22 | 22 | Re-enable Refill And Spawn Only |
| 23 | 23 | Restore Ambient Cry With Stock Movement |
| 24 | 24 | Spawner-Driven Movement Param Tick |
| 25 | 25 | Spawner-Driven Coordinate Read And Direction Calculation |
| 26 | 26 | Spawner-Driven Look Command |
| 27 | 27 | Spawner-Driven Blocked Direction Check |
| 28 | 28 | Spawner-Driven Walk Command |
| 31 | 31 | Frame Task Movement Command Updates |
| 32 | 32 | Per-Slot Movement Ownership And Battle Reset |
| 33 | 33 | Range 8 And Idle Frame Chase |
| 34 | 34 | One-At-A-Time Overlap Untangle |
| 35 | 35 | Guard Idle Frame Context And Moving Battle Contact |
| 36 | 36 | Frame Task Battle Detection |
| 37 | 37 | Post-Movement Battle Settle Window |
| 40 | 40 | Pidgey Speed 6 Test |
| 41 | 41 | Alias High Logical Speeds To Fastest Stock Walk |
| 42 | 42 | Proximity-Only Battle Settle |
| 43 | 43 | Cap High Speeds To Fluent Walk Command |
| 44 | 44 | Non-Blocking Battle Retry Between Chained Commands |
| 45 | 45 | Remove Redundant Speed 6 And Add Spot Emote |
| 46 | 46 | Short Independent Spot Range |
| 47 | 47 | Use Jump-Site Movement Command For Spot Emote |
| 48 | 48 | Manual PosVec Height Bob For Spot Emote |
| 49 | 49 | Use WaitJumpSite Movement Command |
| 50 | 50 | LockDir Jump2 Smoke Release Sequence |
| 51 | 51 | LockDir JumpSite Smoke Release Sequence |
| 52 | 52 | Partner Pokemon JumpSite Wrapper |
| 54 | 54 | Hop Cry, Tired Cooldown, And Chill Wander |
| 55 | 55 | Tired WaitJumpSite Then Stat-Fell Sound |
| 63 | 63 | Behavior Profile Resolver |
| 81 | 230 | Direct Mankey Tree-Top Lifted-Row Fallback |
| 82 | 231 | Revert Shared Row Lift And Keep Direct Fallback Only |
| 83 | 226 | One Row Above Archive Mankey Tree-Top Target |
| 84 | 227 | Restore Archive MinY Tree-Top Logic After Too-High Row |
| 85 | 228 | Sparse Archive Tree-Top Row Lift |
| 88 | 229 | Live Blocked-Row Tree-Top Confirmation |
| 90 | 225 | Mankey Tree-Top Effect-Owned Marker Canary |
| 101 | 65 | A-Button Facing Interaction Starts Spawn Battle |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 110 | 224 | Mankey Tree-Top Stock Large-Pokemon Draw Callback |
| 111 | 225 | Mankey Tree-Top Stock Helper Draw Callback |
| 112 | 226 | Mankey Tree-Top Post-Draw Sprite Priority Probe |
| 114 | 228 | Mankey Tree-Top Synced Visual Proxy |
| 115 | 229 | Mankey Tree-Top BG Layer Identification Probe |
| 120 | 240 | Strict Top-Row Mankey Target Set With Broad X Candidates |
| 121 | 241 | Pair-Derived Mankey Tree-Top X Footprints |
| 122 | 242 | Exposed Mankey Tree-Top Rows With Pair-Derived X |
| 123 | 243 | Full Mankey Tree-Top Vertical Band |
| 124 | 244 | Direct Cardinal Mankey Tree-Band Target |
| 125 | 245 | Coordinate-Latched Mankey Tree-Top Settlement |
| 126 | 246 | Prioritize Strict Structural Mankey Tree Tops |
| 127 | 247 | Strict-Only Mankey Tree-Top Final Targets |
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
| 140 | 235 | Dedicated HEADBUTT_TREE_TOPS Archive Target Set |
| 141 | 233 | Split Mankey Tree Targets From Settled Perches |
| 142 | 230 | Mankey 2x6 Headbutt Tree Top-Row Targeting |
| 143 | 231 | Prefer Nearest Direct Mankey Tree-Top Jump |
| 144 | 232 | Include Exposed Archive Top Row For Mankey Tree Targets |
| 147 | 69 | Use Site Walk Commands And Scripted Crash Feedback For Onix Ram |
| 171 | 93 | Restore Decent Crash Sound And Shorten Speech-Only Alert |
| 173 | 95 | Direct Camera Shake Work Driven By SysTask |
| 177 | 99 | Player Wall-Hit Ram Crash Sound |
| 178 | 100 | Ram Crash-Only Automatic Battle Trigger |
| 179 | 101 | Follower Object-ID Fallback For Ram Crash Battles |
| 180 | 102 | Fled Battle Sends Spawn To Tired State |
| 181 | 103 | Behavior-Gated Ledge Far Jump |
| 182 | 104 | Aggressive Ram Cardinal Alert Line |
| 183 | 105 | Rename Aggressive Chase Profile |
| 191 | 113 | Close All-Direction Alert Radius |
| 203 | 125 | Include Moving Target Trail For Playful Scoring |
| 204 | 126 | Shared Moving Player Target For Movement Intent |
| 205 | 127 | Double Playful Movement Range |
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
| 254 | 176 | Use One Manual Render Hop For Full Canopy Distance |
| 255 | 177 | Canopy Hopper Vanilla Movement-List Task |
| 267 | 219 | Mankey Lands On Headbutt Tree Top Row |
| 269 | 221 | Mankey Tree-Top Priority Flag Probe |
| 270 | 222 | Mankey Failed Tree-Path Backoff And Target Grid |
| 271 | 223 | Mankey Tree-Top Draw-Mode Probe |
| 272 | 232 | Mankey Low Land Row Tree-Top Correction |
| 273 | 233 | Mankey 2x3 Footprint Top-Row Targets |

## Original Attempt Sections

### Attempt 2: Chase Logic Using `object->fsys`

Idea:

Use `LocalMapObject::fsys` to locate the player and compute chase/flee directions. Start movement with stock movement-command helpers.

Files/symbols:

- `src/overworld_wild_movement.c`
- `include/map_events_internal.h`
- `rom.ld`

Helper path:

- `MapObject_IsSingleMovementActive`
- `MapObject_UpdateMovementCommand`
- `MapObject_ClearSingleMovementActive`
- `MapObject_GetParam`
- `MapObject_SetParam`
- `MapObject_GetCurrentX`
- `MapObject_GetCurrentY`
- `GetPlayerXCoord`
- `GetPlayerYCoord`
- `MapObject_IsMovementDirectionBlocked`
- `MapObject_MovementCommandFromDirection`
- `MapObject_StartMovementCommand`
- `MapObject_SetSingleMovementActive`

Runtime result:

- Pokemon spawned and were stable.
- Pokemon did not move.

Learning:

- `object->fsys` is likely missing, stale, or not reliable for these special spawned objects.
- The no-movement result does not prove the movement-command helpers are safe, because the code probably returned before starting movement.

Do not repeat:

- Do not rely only on `LocalMapObject::fsys` for spawned wild Pokemon unless the struct field is independently verified at runtime.

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

### Attempt 26: Spawner-Driven Look Command

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Extend the spawner-step movement diagnostic so that, when the cooldown resets and the preferred direction is valid, it issues a non-walking look command toward the chase/flee direction.

Why this is new:

- Attempt 25/`test120.nds` only tested coordinate reads and direction calculation and did not crash.
- Earlier command-helper attempts ran through slot-47 callbacks and bundled command setup with walking, blocked-direction checks, command update/clear, scratch writes, `object->fsys`, or global movement `FieldSystem *`.
- No previous build has isolated a non-walking `MapObject_MovementCommandFromDirection` plus `MapObject_StartMovementCommand` plus `MapObject_SetSingleMovementActive` path from the stable overlay-149 spawner step loop while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` should be `1`.
- The active probe should call `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive` only after a cooldown reset and a valid direction.
- The active probe should still avoid walking commands, `MapObject_IsMovementDirectionBlocked`, `MapObject_UpdateMovementCommand`, `MapObject_ClearSingleMovementActive`, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test121.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` is `1`.
- Source verification shows the active probe only issues the look command after cooldown reset and a non-`NONE` preferred direction.
- Source verification shows the active probe calls `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive`.
- Disassembly target scan shows `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Disassembly target scan did not find `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_UpdateMovementCommand` at `0x02062429`, or `MapObject_ClearSingleMovementActive` at `0x0205F63D` in the overlay object.
- Source verification shows the active probe still avoids walking commands, blocked-direction checks, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test121.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.
- Visual confirmation was not practical because stock wander masks occasional facing changes.

Learning:

- Spawner-driven `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive` are runtime-stable for a non-walking look command.
- Because stock wander remains active, this proves command setup safety but not visible behavior.

Expand:

- Add a spawner-driven `MapObject_IsMovementDirectionBlocked` check on the same cooldown tick.
- Still avoid walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

### Attempt 27: Spawner-Driven Blocked Direction Check

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. Before issuing the already-stable spawner-driven look command, call `MapObject_IsMovementDirectionBlocked` for the preferred chase/flee direction and store the result in volatile diagnostics. Do not use the blocked result to walk yet.

Why this is new:

- Attempt 26/`test121.nds` tested non-walking command setup and did not crash.
- Earlier movement attempts bundled blocked-direction checks with slot-47 callbacks, walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, or global movement `FieldSystem *`.
- No previous build has isolated `MapObject_IsMovementDirectionBlocked` from the stable overlay-149 spawner step loop while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK` should be `1`.
- The active probe should call `MapObject_IsMovementDirectionBlocked` only after a cooldown reset and a valid preferred direction.
- The active probe should still avoid walking commands, `MapObject_UpdateMovementCommand`, `MapObject_ClearSingleMovementActive`, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Verification:

- Built as `test122.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` is `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK` is `1`.
- Source verification shows the active probe calls `MapObject_IsMovementDirectionBlocked` only after cooldown reset and a non-`NONE` preferred direction.
- Disassembly target scan shows `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`.
- Disassembly target scan still shows the previously safe look-command setup targets: `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Disassembly target scan did not find `MapObject_UpdateMovementCommand` at `0x02062429` or `MapObject_ClearSingleMovementActive` at `0x0205F63D` in the overlay object.
- Source verification shows the active probe still avoids walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `test.nds` was copied to Delta as `test122.nds`.
- `git diff --check` passed.

Runtime result:

- User reported no crash.

Learning:

- Spawner-driven `MapObject_IsMovementDirectionBlocked` is runtime-stable for active spawned Pokemon when called after cooldown reset and a valid preferred direction.
- This clears the blocked-direction helper for a real walk-command probe.

Expand:

- Change the command base from non-walking look `0x00` to walking `0x08`.
- Gate the walk command on `!MapObject_IsMovementDirectionBlocked`.
- Still avoid movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

### Attempt 28: Spawner-Driven Walk Command

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. On cooldown reset, compute the preferred chase/flee direction, check that it is not blocked, and start a walk command using `MapObject_MovementCommandFromDirection(direction, 0x08)`, followed by `MapObject_StartMovementCommand` and `MapObject_SetSingleMovementActive`.

Why this is new:

- Attempt 26/`test121.nds` proved non-walking command setup does not crash.
- Attempt 27/`test122.nds` proved the blocked-direction helper does not crash.
- Earlier walk attempts bundled walking with slot-47 callbacks, movement-command update/clear calls, scratch writes, `object->fsys`, or global movement `FieldSystem *`.
- No previous build has isolated a gated walk command from the stable overlay-149 spawner step loop while keeping stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK` should be `1`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND` should be `1`.
- The active probe should call `MapObject_IsMovementDirectionBlocked`, then only start a walk command when the direction is not blocked and no single movement is already active.
- The active probe should use `OW_WILD_SPAWNER_MOVEMENT_WALK_UP_COMMAND` (`0x08`) as the command base.
- The active probe should still avoid `MapObject_UpdateMovementCommand`, `MapObject_ClearSingleMovementActive`, scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawn parameters should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- User reported no crash.

Learning:

- Starting a real walk command from the stable overlay-149 spawner step loop is runtime-stable when gated by `MapObject_IsMovementDirectionBlocked`.
- This does not prove the movement is visually controlled yet, because fresh spawns still use stock movement `3`, which has its own command state machine.

Verification:

- Built as `test123.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_PARAM_TICK`, `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_COORD_READ`, `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_LOOK_COMMAND`, `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_BLOCKED_CHECK`, and `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_WALK_COMMAND` are all enabled.
- Source verification shows the active probe starts a walk command only after cooldown reset, valid preferred direction, `!MapObject_IsMovementDirectionBlocked`, and `!MapObject_IsSingleMovementActive`.
- Source verification shows the command base is `OW_WILD_SPAWNER_MOVEMENT_WALK_UP_COMMAND` (`0x08`).
- Disassembly target scan shows `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Disassembly target scan did not find `MapObject_UpdateMovementCommand` at `0x02062429` or `MapObject_ClearSingleMovementActive` at `0x0205F63D` in the active overlay object.
- Source still avoids scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawns still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Copied to Delta as `test123.nds`.
- `git diff --check` passed.

Expand:

- Add spawner-owned command update/clear polling after a spawner-started command.
- Keep fresh spawns on stock movement `3` for this probe.
- Still avoid scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.

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

### Attempt 32: Per-Slot Movement Ownership And Battle Reset

Idea:

Keep the successful frame-task timing from `test126.nds`, but move movement ownership into `OverworldWildSpawnState`: each spawn slot has its own cooldown and a bit in an in-progress mask. The player-step hook starts commands per slot, and the frame task services every slot whose bit is set. Battle start and battle cleanup explicitly clear spawner-owned single-movement commands and reset movement cooldowns, so a battle cannot leave all Pokemon stuck in an in-progress state.

Why this is new:

- Attempt 31/`test126.nds` used a frame-level `SysTask`, but it still used object param `0` as the movement cooldown and in-progress marker.
- Earlier attempts did not test per-spawn-slot ownership in `OverworldWildSpawnState`.
- Earlier attempts did not reset all spawner-owned movement commands from both battle start and battle cleanup.
- Earlier spawner-driven movement only tried one preferred chase/flee direction before suppressing movement when blocked.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OverworldWildSpawnState` should contain per-slot movement cooldown storage and an in-progress mask.
- `OverworldWildSpawns_TickMovementParams` should use the per-slot state instead of reading object param `0` for cooldown/in-progress.
- `OverworldWildSpawns_FrameMovementTask` should loop every active bit in the in-progress mask, not only one object.
- Battle start and battle cleanup should call a movement reset path.
- The movement reset path should clear single-movement active only for currently active spawn objects.
- Direction selection should try both primary and secondary chase/flee axes before suppressing a walk.
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, `object->fsys`, and global movement `FieldSystem *`.

Runtime result:

- Built as `test128.nds`.
- User reported this is a huge improvement.
- User reported the previous quirks are no longer issues:
  - multiple Pokemon movement limitation
  - no movement after battle
  - movement not always active outside those cases
- New quirk: Pokemon seem to stop chasing the player after a certain threshold is reached.

Learning:

- Per-slot movement ownership plus battle reset fixes the major follow-up problems from `test126.nds`.
- The new threshold quirk is likely the engine's map-object movement range doing its job: `OverworldWildSpawns_ApplyMovementRange` sets X/Y range to `2`, and `MapObject_IsMovementDirectionBlocked` likely treats a chase step outside that leash as blocked.
- The threshold therefore appears expected for the current implementation, but it is probably not the desired final chase behavior.
- The next direction should test a leash adjustment rather than reworking frame-task timing or per-slot ownership.

Verification:

- `./docker-makerom.cmd` completed successfully.
- Copied to Delta as `test128.nds`.
- Source confirms `OverworldWildSpawnState` has `movementCooldowns[OW_WILD_MAX_SPAWNS]` and `movementInProgressMask`.
- Source confirms `OverworldWildSpawns_TickMovementParams` uses `state->movementCooldowns[i]` and `OverworldWildSpawns_IsMovementSlotInProgress` instead of using object param `0` as cooldown/in-progress.
- Source confirms `OverworldWildSpawns_FrameMovementTask` loops all slots whose in-progress bit is set and increments `sOverworldWildMovementDiagnosticFrameTaskUpdatedObjects` per updated object.
- Source confirms battle start and battle cleanup both call `OverworldWildSpawns_ResetAllMovementCommands(state, TRUE)`.
- Source confirms map-context changes call `OverworldWildSpawns_ResetAllMovementCommands(state, FALSE)`.
- Source confirms `OverworldWildSpawns_DiagnosticBuildDirections` builds up to two chase/flee axes and `OverworldWildSpawns_TryStartSpawnerMovementCommand` tries each direction before suppressing movement.
- Source scan confirms the active overlay path no longer writes `OW_WILD_MOVEMENT_PARAM_COOLDOWN` with `MapObject_SetParam`, and the old `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` marker was removed from the source.
- Linked overlay target scan found `CreateSysTask` target `0x0200E321`, `DestroySysTask` target `0x0200E391`, `MapObject_UpdateMovementCommand` target `0x02062429`, and `MapObject_ClearSingleMovementActive` target `0x0205F63D`.
- Linked overlay target scan still contains expected movement helper targets `0x02060BB9`, `0x0205F649`, `0x0206234D`, `0x0206217D`, and `0x0205F631`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- `git diff --check` passed.

Expand:

- Keep per-slot movement ownership and frame-task updates.
- Test whether increasing or removing `MapObject_SetXRange`/`MapObject_SetYRange` lets Pokemon keep chasing without reintroducing old movement issues.
- Alternatively, test recentering the movement leash after each successful spawner-owned step, if unlimited chase feels too chaotic.

### Attempt 33: Range 8 And Idle Frame Chase

Idea:

Keep the successful per-slot movement ownership from `test128.nds`, increase spawned Pokemon X/Y movement range from `2` to `8`, and make the frame task continue running while a compatible map context and active spawns exist. The task should still update in-progress commands, but when no command is in progress it should call the same spawner movement decision logic with the last valid `FieldSystem *`, allowing Pokemon to start new chase steps even when the player is not moving.

Why this is new:

- Attempt 31 used a frame task only to update commands that player-step had already started.
- Attempt 32 used per-slot ownership and battle reset, but movement decisions still came from the player-step hook.
- No previous build has tested a persistent active-spawn frame task that starts new chase commands while the player is idle.
- No previous build has tested widening the map-object X/Y range to `8`.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OverworldWildSpawns_ApplyMovementRange` should set X/Y range to `8`.
- `OverworldWildSpawnState` should retain a movement `FieldSystem *` only while the current map context is active.
- `OverworldWildSpawns_EnsureFrameMovementTask` should accept/update the current `FieldSystem *`.
- `OverworldWildSpawns_FrameMovementTask` should validate the retained field system with `OverworldWildSpawns_IsEnabledMap` before making decisions.
- The frame task should call `OverworldWildSpawns_TickMovementParams` when active spawns exist, so new movement commands can start without player movement.
- Map-context changes and battle reset should clear the retained field system and stop the frame task.
- The active probe should still avoid slot-47 callbacks, active custom movement scratch writes, and `object->fsys`.

Verification:

- Built as `test129.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_ApplyMovementRange` sets X/Y range to `8`.
- Verified `OverworldWildSpawnState` stores `movementFieldSystem`, clears it on movement reset, and refreshes it from player-step movement ticking.
- Verified `OverworldWildSpawns_EnsureFrameMovementTask` accepts the current `FieldSystem *`.
- Verified `OverworldWildSpawns_FrameMovementTask` stops if the retained field system is no longer an enabled map or if no active spawned objects remain.
- Verified the frame task calls `OverworldWildSpawns_TickMovementParams`, so movement decisions can be issued without a new player step.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.
- Verified active overlay code still avoids direct `object->fsys` and `object->unkD8` access; remaining references are in the dormant custom movement file.

Runtime result:

- User reported this is starting to look really good, with a minor issue where Pokemon that move at the same time can sometimes end on the same tile.

Learning:

- Range `8` and idle frame chase are viable enough to continue polishing.
- The next issue is not core movement timing; it is after-the-fact overlap cleanup for simultaneous successful moves.

### Attempt 34: One-At-A-Time Overlap Untangle

Idea:

Keep the successful range `8` and idle frame chase from `test129.nds`, but add a post-move untangle pass inside the spawner movement tick. When no spawner-owned command is in progress, scan active spawned Pokemon for duplicate current coordinates. If a pair overlaps, start one normal spawner-owned walk command for one of the pair into an adjacent unoccupied, unblocked tile, then return so only one untangle move is active at a time.

Why this is new:

- Previous attempts tested movement descriptors, safe command timing, per-slot ownership, battle reset, range, and idle chase.
- No previous attempt has scanned active spawned Pokemon for duplicate current coordinates.
- No previous attempt has used the proven spawner-owned walk command path specifically as an after-the-fact overlap resolver.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test130.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_TryUntangleOverlaps` runs before normal chase decisions inside `OverworldWildSpawns_TickMovementParams`.
- Verified the untangle pass only runs when `movementInProgressMask == 0`.
- Verified overlap detection compares current coordinates for active spawned Pokemon pairs.
- Verified untangle target validation rejects negative coordinates, currently occupied target tiles, and directions blocked by `MapObject_IsMovementDirectionBlocked`.
- Verified untangle movement reuses `OverworldWildSpawns_TryStartSpawnerMovementCommand`, so it stays on the proven spawner-owned command path.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.

Runtime result:

- User reported two issues:
  - route exits can slow down dramatically and sometimes freeze, and this was already present in the prior run
  - in `test130.nds`, battle engagement overshoots badly and starts fights before the player appears close to a spawned Pokemon

Learning:

- The route-exit problem likely predates the overlap untangle pass and points back to the persistent idle frame task added in Attempt 33.
- The battle overshoot could be caused by checking contact while a spawned Pokemon is still resolving a movement command.

### Attempt 35: Guard Idle Frame Context And Moving Battle Contact

Idea:

Keep range `8`, idle chase, and one-at-a-time untangling, but make the persistent frame task stop unless its retained `FieldSystem *` still matches the spawner's current map id, map-object manager, and object table. Also make `OverworldWildSpawns_IsTouchingPlayer` ignore a spawned Pokemon while that slot has a spawner-owned movement command in progress or while the object still has an engine single-movement command active.

Why this is new:

- Attempt 33 validated only `OverworldWildSpawns_IsEnabledMap(fieldSystem)` before using the retained `FieldSystem *`.
- Attempt 34 added overlap cleanup but did not add any stronger route-transition/lifetime guard.
- No previous attempt has suppressed battle detection while a spawned Pokemon is still moving.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test131.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_IsMovementFieldContextCurrent` checks enabled map, retained map id, retained map-object manager, and retained object table before the frame task keeps running.
- Verified `OverworldWildSpawns_FrameMovementTask` also requires a current active spawn via `OverworldWildSpawns_HasCurrentMovementSpawns`.
- Verified the frame task no longer updates a slot whose object is not current for the retained field context.
- Verified `OverworldWildSpawns_IsTouchingPlayer` returns false while the slot is in `movementInProgressMask` or the object reports `MapObject_IsSingleMovementActive`.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.

Runtime result:

- User reported the route-exit slowdown/freeze and contact timing still needed follow-up.

Learning:

- Stronger map-context guards remain useful, but route-transition and battle-timing behavior still needed follow-up.
- Keep suppressing contact while movement is active; use later battle timing attempts for the adjacency miss.

### Attempt 36: Frame Task Battle Detection

Idea:

Keep the player-step battle detector, but also call `OverworldWildSpawns_TryStartBattle` from `OverworldWildSpawns_FrameMovementTask` after all in-progress spawner movement commands have been updated. The frame-task call only runs when `movementInProgressMask == 0`, so battle detection happens after movement settles and before the next chase/untangle command can start. Add a `decrementBattleGrace` parameter so player-step checks still consume flee grace, while frame-task checks observe grace without burning it every frame.

Why this is new:

- Previous attempts proved `OverworldWildSpawns_TryStartBattle` on the player-step path.
- Previous attempts proved frame-task movement polling and idle chase.
- No previous attempt has scheduled the overworld-wild battle script from the frame-task path.
- No previous attempt has separated player-step flee-grace consumption from frame-task contact checks.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test132.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawns_FrameMovementTask` calls `OverworldWildSpawns_TryStartBattle(state, fieldSystem, FALSE)` only when `movementInProgressMask == 0`.
- Verified the frame-task battle check runs before `OverworldWildSpawns_TickMovementParams`, so it can schedule battle before starting another movement command.
- Verified the player-step path still calls `OverworldWildSpawns_TryStartBattle(state, fieldSystem, TRUE)`.
- Verified `battleGraceSteps` is decremented only when `decrementBattleGrace` is true.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020fcec8`.
- Linked overlay target scan still shows the expected movement helper targets and player coordinate helpers.

Runtime result:

- User reported no crash, and battle triggering works about 90% of the time.
- Remaining miss: when the player and spawned Pokemon move at the same time, they can end up adjacent without a battle starting.

Learning:

- Scheduling the battle script from the movement frame task is viable.
- The remaining issue appears to be a settle/timing race after simultaneous player and spawned-Pokemon movement, not a broad `EventSet_Script` or battle-start crash.

### Attempt 37: Post-Movement Battle Settle Window

Idea:

When a spawner-owned movement command finishes, start a short settle window before any new chase or untangle command can begin. During that window, retry the existing battle contact detector every frame without decrementing flee grace. This gives the engine a few frames to clear movement-active state and settle player/Pokemon coordinates after simultaneous movement, then starts the battle if they are adjacent.

Why this is new:

- Attempt 36 added one frame-task battle check after movement commands settled, but it did not hold off the next movement command for additional settle frames.
- Attempt 35 suppressed battle detection while movement was active, but it did not add a retry window after movement finished.
- No previous attempt has stored a per-state post-movement battle settle counter or blocked new spawner movement while that counter is active.

Files/symbols:

- `include/overworld_wild_spawns_internal.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test134.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OverworldWildSpawnState` stores `movementBattleSettleFrames`.
- Verified `OverworldWildSpawns_FrameMovementTask` sets the settle counter only when `OverworldWildSpawns_UpdateSpawnerMovementCommand` reports a completed spawner-owned command.
- Verified `OverworldWildSpawns_TryHoldForBattleSettle` blocks new movement while the settle counter is active, and only decrements/retries `OverworldWildSpawns_TryStartBattle(state, fieldSystem, FALSE)` after `movementInProgressMask` reaches `0`.
- Verified `OverworldWildSpawns_TickMovementParams` returns early while the settle window is active, so no new chase/untangle command can start before the retry window resolves.
- Verified the player-step path returns `TRUE` if the settle retry starts a pending battle during movement ticking.
- Verified ARM9 movement slot `47` still points at the stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported the build seems more stable.

Learning:

- The post-movement settle window appears to improve the remaining simultaneous-movement battle timing issue.
- Per-species speed should not be implemented by slowing other species with larger decision cooldowns when the requested test is for Pidgey to be faster.

### Attempt 40: Pidgey Speed 6 Test

Idea:

Keep the new speed-level abstraction from Attempt 39, but set only Pidgey to speed `6` while Sentret remains speed `1`. This creates an obvious runtime test for the highest currently exposed speed level.

Why this is new:

- Attempt 39 added speed levels `1` through `6`, but only built Pidgey at speed `2`.
- No previous built ROM has tested Pidgey using speed `6` / stock command family `0x1C`.
- This still changes only the per-species speed parameter, not movement timing, battle detection, custom descriptors, or coordinate writes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test137.nds` and copied to Delta.
- `git diff --check` passed.
- Verified `OW_WILD_SPAWNER_PIDGEY_MOVEMENT_SPEED` is `6`, while `OW_WILD_SPAWNER_SENTRET_MOVEMENT_SPEED` remains `1`.
- Verified speed `6` maps through `OverworldWildSpawns_GetMovementWalkCommandForSpeed` to stock command family `0x1C`.

Runtime result:

- User reported Pidgey does not move and just stands still.

Learning:

- Stock command family `0x1C` is not usable as a spawner-owned walk command in this context, even though it exists in the local movement command table.
- The earlier verification was too broad: table presence does not prove a command family uses the same walk update path as `0x08`, `0x0C`, `0x10`, or `0x14`.

### Attempt 41: Alias High Logical Speeds To Fastest Stock Walk

Idea:

Keep Pidgey at logical speed `6`, but map speed levels `5` and `6` to the fastest stock walk command family `0x14` instead of the non-walking `0x18` / `0x1C` command families.

Why this is new:

- Attempt 40 directly tested speed `6` mapped to `0x1C`, and runtime showed Pidgey standing still.
- No previous attempt has kept the speed `1` through `6` parameter scale while aliasing unsupported high speed levels back to the fastest confirmed stock walk command.
- This avoids returning to burst-polling, custom movement descriptors, coordinate writes, or global timing changes.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test138.nds` and copied to Delta.
- `git diff --check` passed.
- Verified Pidgey remains logical speed `6`.
- Verified speed `5` and speed `6` now map to `OW_WILD_SPAWNER_MOVEMENT_SPEED_4_COMMAND` / stock command family `0x14`.
- Local disassembly shows `0x08`, `0x0C`, `0x10`, and `0x14` share the stock walk update path, while `0x18` and `0x1C` switch to a different update path.

Runtime result:

- User reported movement looks jittery: one step, pause, one step, pause.

Learning:

- The high-speed command path still felt stop-start with speed `6` mapped to `0x14`.
- The first guess that this was caused by the global battle-settle pause was later corrected by the user and should not be treated as proven.

### Attempt 42: Proximity-Only Battle Settle

Idea:

Keep the six-frame post-movement battle-settle window, but only start that settle window when a finished movement ends near the player. Finished movement farther away from the player can immediately start the next spawner-owned movement command.

Why this is new:

- Attempt 37 added the global post-movement settle window after every completed movement command.
- Attempt 41 kept high logical speeds on the fastest stock walk command, making the global settle pause visibly jittery.
- No previous attempt has gated the settle window by proximity to the player.
- This avoids reducing the battle-settle duration globally, so the simultaneous player/Pokemon movement battle-retry case still has a buffer near contact.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test139.nds` and copied to Delta.
- `git diff --check` passed.
- Verified completed movement only starts `OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES` when a finished slot is within `OW_WILD_SPAWNER_BATTLE_SETTLE_RANGE` of the player.
- Verified movement that finishes farther from the player does not set the settle counter, allowing `OverworldWildSpawns_TickMovementParams` to start the next command immediately.

Runtime result:

- User corrected the assumption: this was not the cause of the jitter.

Learning:

- Proximity-gating the battle-settle window should not be treated as the smoothness fix.
- The active source for the next test restores the previous global settle behavior and instead changes the high-speed visual movement command mapping.

### Attempt 43: Cap High Speeds To Fluent Walk Command

Idea:

Keep Pidgey at logical speed `6`, but cap logical speeds `4`, `5`, and `6` to the 4-frame stock walk command family `0x10` instead of the 2-frame `0x14` family. The hypothesis is that `0x14` makes each tile step so short that the object appears to snap one tile and briefly stand still, while `0x10` should preserve a faster-than-Pidgey-speed-2 feel with more visible interpolation.

Why this is new:

- Attempt 40 showed `0x1C` does not move in this spawner path.
- Attempt 41 mapped high speeds to `0x14`, but runtime still felt jittery.
- Attempt 42 incorrectly tested the battle-settle timing; the user clarified that was not the cause.
- No previous attempt has kept Pidgey at logical speed `6` while capping the visual movement command to `0x10`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test140.nds` and copied to Delta.
- `git diff --check` passed.
- Verified Pidgey remains logical speed `6`.
- Verified logical speeds `4`, `5`, and `6` now map to `OW_WILD_SPAWNER_MOVEMENT_SPEED_3_COMMAND` / stock command family `0x10`.
- Verified the active source restored the previous global battle-settle behavior after Attempt 42 was corrected.

Runtime result:

- User clarified the core problem was not the high-speed command family. Movement feels jittery at all speeds because spawned Pokemon visibly stop and "think" between every tile instead of chaining movement like the player.

Learning:

- The visual-command cap does not address the main smoothness issue. The next solution should target command chaining and the pause between one-tile movement commands.

### Attempt 44: Non-Blocking Battle Retry Between Chained Commands

Idea:

Keep the post-movement battle retry check from Attempt 37, but stop using the retry counter as a movement hold. When a spawner-owned movement command finishes, perform a contact retry if no movement is currently active. If that retry does not start a battle, immediately continue into untangle/chase command selection so the next tile command can be queued without a visible "thinking" pause.

Why this is new:

- Attempt 37 explicitly blocked new movement while `movementBattleSettleFrames` was active.
- Attempt 42 only tried gating that same blocking settle window by proximity, and the user corrected that this did not address the real jitter.
- No previous attempt has made the battle retry non-blocking while still retaining the retry path before the next command can be issued.
- This targets the all-speeds stop-and-think behavior instead of changing walk command families or per-species speed values.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Verification:

- Built as `test141.nds` and copied to Delta.
- `git diff --check` passed before the build.
- Verified `OverworldWildSpawns_TryBattleSettleRetry` only returns `TRUE` when `OverworldWildSpawns_TryStartBattle(state, fieldSystem, FALSE)` actually schedules a battle.
- Verified a failed retry now decrements `movementBattleSettleFrames` and returns `FALSE`, allowing `OverworldWildSpawns_TickMovementParams` to continue into untangle/chase command selection.
- Verified the frame task still sets `movementBattleSettleFrames` after a completed spawner-owned movement command, so the contact retry path still runs before the next command can be issued.

Runtime result:

- User reported it works, and the current fastest movement is plenty fast for testing.

Learning:

- The non-blocking retry fixed the visible stop-and-think pause between tile commands enough to keep building on this path.
- Current safe speed command families are still limited: speed `1` maps to `0x08`, speed `2` maps to `0x0C`, and speed `3` maps to `0x10`. Logical speeds above that were aliases rather than new motion speeds.

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

### Attempt 102: Fled Battle Sends Spawn To Tired State

Idea:

When the player runs from a battle started by a spawned overworld Pokemon, keep that Pokemon spawned but put that slot into the behavior tired state. This makes the same Pokemon visibly recover instead of immediately returning to normal chase/spot behavior.

Implementation shape:

- Use the existing battle cleanup path because it still has `pendingSlot` and the final battle result.
- On `OverworldWildSpawns_BattleResultIsPlayerFlee`, keep the existing `OW_WILD_FLEE_GRACE_STEPS` protection.
- If the pending slot still has a current map object, set `movementFieldSystem` to the cleanup `FieldSystem *` and call `OverworldWildSpawns_StartTiredEmote`.
- Leave non-flee cleanup unchanged: defeated/caught/non-flee outcomes still clear the spawn slot.
- Give `StartTiredEmote` a fallback tired profile for Pokemon whose normal behavior has `tiredState = none`, so default/A-button-only Pokemon can still visibly become tired after the player runs.

Why this is new:

- Earlier flee cleanup only set `battleGraceSteps`, which prevented immediate re-battle but did not put the spawn into a tired/resting state.
- Attempts 53 through 62 built the tired-state presentation and cooldown system, but those transitions came from movement stamina, not from battle cleanup.
- The saved-shiny HP work preserved the same overworld Pokemon after running, but did not change its movement state after the run.
- No previous attempt has used `pendingSlot` during battle cleanup to transition the surviving spawn into tired state.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_OverlayCleanupPendingBattle`
- `OverworldWildSpawns_StartTiredEmote`
- `OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd` and copied to Delta as `test200.nds`.
- Verified flee cleanup still keeps `OW_WILD_FLEE_GRACE_STEPS`.
- Verified flee cleanup calls `OverworldWildSpawns_StartTiredEmote` for the current `pendingSlot`.
- Verified default/no-tired-profile Pokemon fall back to a water-droplet tired state with `OW_WILD_SPAWNER_FLEE_TIRED_REST_TIME`.
- Verified non-flee cleanup still clears the spawn slot.
- Build warnings were pre-existing unused-parameter/unused-symbol diagnostics in battle script, overlay diagnostics, and `OverworldWildSpawns_Clear`.

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

### Attempt 104: Aggressive Ram Cardinal Alert Line

Idea:

Let aggressive ram alertness work in every cardinal direction instead of only when the Pokemon is already facing the player. For ram profiles, if the player is directly north, south, east, or west within `profile.alertness`, the Pokemon should enter its alert state and lock the ram direction toward the player.

Implementation shape:

- Add `OverworldWildSpawns_IsPlayerInCardinalLine`, which succeeds when the player is on the same row or column within alertness.
- Add `OverworldWildSpawns_IsPlayerInAlertLine` as the behavior-aware alert gate.
- Keep non-ram behavior profiles on the existing `OverworldWildSpawns_IsPlayerInFacingLine` rule.
- Route `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE` through the new cardinal-line gate.
- Keep the existing `spotDirections[0]` direction assignment, so ram still starts in the cardinal direction toward the player.

Why this is new:

- Attempt 66 introduced a facing cone.
- Attempt 70 changed alertness to a strict facing line.
- No previous attempt made only aggressive ram use a four-direction cardinal alert line while preserving facing-line alertness for other profiles.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_IsPlayerInCardinalLine`
- `OverworldWildSpawns_IsPlayerInAlertLine`
- `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test202.nds`.
- Verified `OverworldWildSpawns_IsPlayerInAlertLine` keeps non-ram profiles on `OverworldWildSpawns_IsPlayerInFacingLine`.
- Verified `OW_WILD_BEHAVIOR_ATTENTIVE_STATE_RAM_START_BATTLE` uses `OverworldWildSpawns_IsPlayerInCardinalLine`, allowing same-row or same-column alerting in all four cardinal directions.
- Verified the alert start still passes `spotDirections[0]` into `OverworldWildSpawns_TryStartSpotEmote`, so aggressive ram locks its initial ram direction toward the player.

Runtime result:

- Pending user test.

Learning:

- Pending.

### Attempt 105: Rename Aggressive Chase Profile

Idea:

Rename the normal chase/battle behavior profile from `aggressive` to `agressiveChase`, while keeping the separate aggressive-ram behavior name unchanged.

Implementation shape:

- Rename `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE` to `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE`.
- Keep the numeric behavior class value as `2`, so existing behavior-class table indexing remains unchanged.
- Update Pidgey's behavior-class rule to use `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE`.
- Leave `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM` unchanged.

Why this is new:

- Earlier attempts split `aggressive_ram` away from the normal aggressive chase behavior, but did not rename the normal chase behavior profile.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE`
- `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM`

Verification:

- `git diff --check` passed.
- Verified active source now defines `OW_WILD_BEHAVIOR_CLASS_AGRESSIVE_CHASE` and uses it for Pidgey's behavior-class rule.
- Verified the separate `OW_WILD_BEHAVIOR_CLASS_AGGRESSIVE_RAM` symbol was not renamed.

Runtime result:

- Not applicable; symbol-only rename.

Learning:

- This is a naming-only cleanup; behavior class value `2` and runtime behavior remain unchanged.

### Attempt 113: Close All-Direction Alert Radius

Idea:

For behavior profiles using the normal `3`-tile facing alertness, also let the Pokemon spot the player within radius `1` in any direction. This keeps the longer alert range directional, but makes a very close player trigger alert even from behind or diagonally.

Implementation shape:

- Add `OW_WILD_SPAWNER_CLOSE_ALERT_RADIUS` with value `1`.
- Add `OverworldWildSpawns_IsPlayerInAlertRadius`, using a radius-1 all-direction check.
- Update `OverworldWildSpawns_IsPlayerInAlertLine` so non-ram profiles still use the facing line, but profiles whose resolved `alertness` is `OW_WILD_SPAWNER_SPOT_RANGE` also pass the close-radius check.
- Leave aggressive ram on its existing cardinal-line alertness path.
- Leave movement commands, speed, stamina, playful target selection, and battle triggers unchanged.

Why this is new:

- Attempt 70 changed normal alertness to a strict facing line.
- Attempt 104 made only aggressive ram alert in all cardinal directions.
- No previous attempt has combined normal facing-line alertness with a close-range all-direction fallback.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OW_WILD_SPAWNER_CLOSE_ALERT_RADIUS`
- `OverworldWildSpawns_IsPlayerInAlertRadius`
- `OverworldWildSpawns_IsPlayerInAlertLine`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test211.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 5 22:46 timestamp.
- Verified `OverworldWildSpawns_IsPlayerInAlertLine` keeps aggressive ram on the cardinal-line path before applying the close-radius fallback.
- Verified non-ram profiles still use facing-line alertness, with radius `1` all-direction alerting only when resolved `profile.alertness == OW_WILD_SPAWNER_SPOT_RANGE`.

Runtime result:

- Pending user test.

Learning:

- Pending.

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

### Attempt 126: Shared Moving Player Target For Movement Intent

Idea:

Use the current-plus-previous moving-player target trail as the default player-position source for movement intent. Behaviors that choose alert/chase/flee/ram/untangle directions should target the closest coherent moving-player tile instead of always reading only `GetPlayerXCoord/YCoord`.

Implementation shape:

- Rename the target-add helpers from playful-specific names to shared movement-target names:
  - `OverworldWildSpawns_TryAddMovementTarget`;
  - `OverworldWildSpawns_TryAddMovementMapObjectTargets`.
- Add `OverworldWildSpawns_BuildPlayerMovementTargets`.
- Add `OverworldWildSpawns_TrySelectClosestMovementTarget`.
- Add `OverworldWildSpawns_TryGetClosestPlayerMovementTarget`.
- Keep playful using the same helper for player targets, then add follower targets on top of it.
- Update untangle movement to move away from the closest moving-player target.
- Update the per-slot movement tick so alert detection, chase direction, flee direction, and ram's alert-start direction use the closest moving-player target.
- Leave exact-coordinate systems unchanged for now:
  - spawn placement;
  - despawn distance;
  - tile occupancy;
  - touch battle;
  - A-button battle;
  - ram crash battle collision.

Why this is new:

- Attempt 125 applied the moving-target trail only inside playful player/follower target scoring.
- No previous attempt has made this the shared source for player-position-based movement intent.
- Earlier coordinate experiments only proved player/object coordinate reads were stable; they did not smooth moving-player coordinates or define exact-vs-smoothed usage boundaries.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`
- `OverworldWildSpawns_TryAddMovementTarget`
- `OverworldWildSpawns_TryAddMovementMapObjectTargets`
- `OverworldWildSpawns_BuildPlayerMovementTargets`
- `OverworldWildSpawns_TrySelectClosestMovementTarget`
- `OverworldWildSpawns_TryGetClosestPlayerMovementTarget`
- `OverworldWildSpawns_BuildUntangleDirections`
- `OverworldWildSpawns_TickMovementParams`

Verification:

- `git diff --check` passed before build.
- Built with `./docker-makerom.cmd`; build succeeded and copied the ROM to Delta as `test224.nds`.
- Verified `test.nds` and the Delta copy are both present at 176M with a Jun 6 00:52 timestamp.
- Verified active source contains the shared moving-player target helper path, playful now uses `OverworldWildSpawns_BuildPlayerMovementTargets`, and untangle plus the per-slot movement tick call `OverworldWildSpawns_TryGetClosestPlayerMovementTarget`.

Runtime result:

- Pending user test.

Learning:

- Pending.

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
