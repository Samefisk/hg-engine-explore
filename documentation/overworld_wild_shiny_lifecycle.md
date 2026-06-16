# Shiny Lifecycle, Persistence, And Identity

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Tracks shiny overworld render setup, saved shiny persistence, battle identity handoff, and related cleanup.
- The movement log contains indirect HP/gender/PID notes; use this alongside shiny-specific investigation docs/code history.
- Saved shiny handling crosses spawn cleanup, battle cleanup, flee behavior, and object recreation paths.
- `ov01_021FE66C` is a user-liked visual candidate for shiny Pokemon presentation, separate from the failed headbutt leaf-effect search.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 8 | 8 | Make Stale Movement `47` No-Op And Spawn Fresh Objects With Stock Movement `3` |
| 14 | 14 | UpdateMapState Map Writes Without Clear |
| 15 | 15 | Read Spawn State Without Writing It |
| 16 | 16 | Call No-Op Movement Setter Without State Writes |
| 18 | 18 | Re-enable Map-State Writes After LONG_CALL Fix |
| 19 | 19 | Re-enable Stale-Slot Cleanup Only |
| 20 | 20 | Re-enable Distance Despawn Only |
| 21 | 21 | Re-enable Touch-Battle Detection Only |
| 22 | 22 | Re-enable Refill And Spawn Only |
| 23 | 23 | Restore Ambient Cry With Stock Movement |
| 30 | 30 | Obvious Spawner-Driven Tile Movement |
| 37 | 37 | Post-Movement Battle Settle Window |
| 38 | 38 | Pidgey Fast Movement Command |
| 39 | 39 | Movement Speed Levels 1-6 |
| 40 | 40 | Pidgey Speed 6 Test |
| 41 | 41 | Alias High Logical Speeds To Fastest Stock Walk |
| 43 | 43 | Cap High Speeds To Fluent Walk Command |
| 45 | 45 | Remove Redundant Speed 6 And Add Spot Emote |
| 53 | 53 | Three-Speed Scale And Speed-3 Double Hop |
| 63 | 63 | Behavior Profile Resolver |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
| 94 | 261 | Default Non-Phantom Reveal Guard |
| 95 | 262 | Charmander Probe Uses Normal Spawn Slot From Birth |
| 97 | 242 | Pair Tree-Top Candidates And Derive Top Row From Archive Bottom |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 117 | 237 | Cache Mankey Tree-Top Archive Predicate |
| 118 | 238 | Gate Mankey Bubble Probe On Final Tree-Top Landing |
| 125 | 245 | Coordinate-Latched Mankey Tree-Top Settlement |
| 130 | 250 | Follower-Sprite Tree-Top Proxy Probe |
| 135 | 255 | Snap Final Canopy Landing After Partner Restore |
| 145 | 67 | Normal Speed, Tile Stamina, Playful Aipom, And Onix Ram |
| 165 | 87 | Promote `aggressive_ram` Behavior And Strengthen Crash Feedback |
| 179 | 101 | Follower Object-ID Fallback For Ram Crash Battles |
| 180 | 102 | Fled Battle Sends Spawn To Tired State |
| 183 | 105 | Rename Aggressive Chase Profile |
| 206 | 128 | Phantom Stalker Hidden Movement |
| 211 | 133 | Refresh Phantom Sprite On Visible Flicker Phase |
| 212 | 134 | Phantom Flicker Apparition Object |
| 215 | 137 | Active Phantom Real-Object Flicker |
| 216 | 138 | Recreate Phantom Object After Teleport |
| 221 | 143 | One-Second Pause After Phantom Alert Arrival |
| 222 | 144 | Visible Teleport Pauses And Faster Alert Teleport |
| 223 | 145 | Restrict Directional Bump Battles To Phantom Stalkers |
| 224 | 146 | Recreate Real Phantom After Attentive Teleport |
| 227 | 149 | Recompute Active Spawn Behavior Class |
| 234 | 156 | Force Land Test Spawns To Mankey |
| 238 | 160 | Seven-Tile Canopy Hop Target And No Bounce-Back |
| 241 | 163 | Canopy Helper Object Far-Hop Visual |
| 244 | 166 | Real Object Deferred Logical Commit Render-Hop |
| 247 | 169 | Recreate Real Canopy Object After Each Segment |
| 253 | 175 | Recreate Final Tree Landing Without Manual Tile Rewrite |
| 261 | 194 | Forced Mankey Tree-Tile Occupancy Render Probe |
| 262 | 195 | Forced Mankey Canopy-Top Occupancy Render Probe |
| 263 | 196 | Normal-Path Canopy-Top Occupancy Probe |
| 268 | 220 | Mankey Tree-Top Render Height Lift |
| 269 | 221 | Mankey Tree-Top Priority Flag Probe |
| 271 | 223 | Mankey Tree-Top Draw-Mode Probe |

## Original Attempt Sections

### Attempt 8: Make Stale Movement `47` No-Op And Spawn Fresh Objects With Stock Movement `3`

Idea:

Split stale-object safety from fresh-spawn behavior:

- Patch movement table slot `47` to stock movement `0`'s no-op descriptor at `0x020FCEC8`.
- Create new overworld wild spawn objects with stock movement `3` instead of movement `47`.

Why this is new:

- Attempt 7 aliased movement `47` to active stock movement `3`, which may run uninitialized movement state on old saved movement-47 objects.
- This attempt keeps stale movement-47 objects inert while proving whether new stock movement-3 spawns can step safely on the same save.

Files/symbols:

- `armips/asm/overworld_wild_movement.s`
- `include/overworld_wild_movement.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- Built ROM should have movement slot `47` at `0x020FD2B0` pointing at stock no-op descriptor `0x020FCEC8`.
- New spawns should call `CreateSpecialFieldObjectWithParams` with movement `3`.

Verification:

- Built as `test103.nds`.
- Slot `0` at `0x020FD1F4` points at `0x020FCEC8`.
- Slot `3` at `0x020FD200` points at `0x020FD170`.
- Slot `47` at `0x020FD2B0` points at `0x020FCEC8`.
- Slot `47` descriptor words match stock no-op movement `0`: `0x00000000 0x0205FCB5 0x0205FCB9 0x0205FCBD 0x0205FCC1`.
- Source verification: `OverworldWildSpawns_CreateObject` passes `OW_WILD_MOVE_STOCK_WANDER`, currently movement `3`, to `CreateSpecialFieldObjectWithParams`.

Runtime result:

- User reported the game still crashes.

Learning:

- Stale movement `47` running stock movement `3` was not the only cause.
- Fresh spawns using stock movement `3` plus stale movement `47` idling is still not enough to survive the one-step test.
- The next likely culprit is the spawner's player-step pipeline, or something that runs independently after the player step.

Do not repeat:

- Do not keep changing only movement-slot aliasing for this crash unless the player-step pipeline is ruled out.

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

### Attempt 16: Call No-Op Movement Setter Without State Writes

Idea:

Let `OverworldWildSpawns_UpdateMapState` call `OverworldWildCustomMovement_SetFieldSystem(fieldSystem)` while still returning before any `OverworldWildSpawnState` writes, before `OverworldWildSpawns_Clear`, and before downstream spawner work.

Why this is new:

- Attempt 14 bundled state writes with the movement setter call and crashed.
- Attempt 15 read `state->mapId` without writing state or calling the movement setter and did not crash.
- This attempt isolates whether the cross-call from overlay 149 to the currently no-op ARM9 movement setter is safe.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `src/overworld_wild_movement.c` for verification that `OverworldWildCustomMovement_SetFieldSystem` still compiles to `bx lr`

Expected verification:

- `OW_WILD_UPDATE_DIAGNOSTIC_STATE_READ_ONLY` should be `0`.
- `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` should be `1`.
- The active update path should call `OverworldWildCustomMovement_SetFieldSystem(fieldSystem)`.
- The active update path should not write `state`, should not call `OverworldWildSpawns_Clear`, and should not run downstream spawner work.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test111.nds`.
- Disassembly shows the active overlay step path calls `__OverworldWildCustomMovement_SetFieldSystem_from_thumb`, then returns `FALSE`.
- Disassembly of `OverworldWildCustomMovement_SetFieldSystem` is still `bx lr`.
- The active overlay path does not write `state`, does not call `OverworldWildSpawns_Clear`, and does not run downstream spawner work.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported a crash.

Learning:

- The direct overlay-to-ARM9 setter call is unsafe as currently generated.
- This is probably not movement logic: `OverworldWildCustomMovement_SetFieldSystem` still compiles to `bx lr`.
- The likely bug is call generation/interworking: overlay 149's veneer switches to ARM state and branches to the Thumb function address without preserving the Thumb bit.

Do not repeat:

- Do not call `OverworldWildCustomMovement_SetFieldSystem` from overlay code through a plain, non-`LONG_CALL` declaration.

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
