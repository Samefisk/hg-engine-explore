# Overworld Wild Movement Attempt Log

## Usage Rule

Before trying a new custom overworld wild movement solution, read this log and verify the proposed change is not just a repeat of a previous attempt.

When adding a new attempt, record:

- the exact idea tried
- the files or symbols changed
- the build or ROM tested
- the runtime result
- what the result proves or suggests
- whether the same approach should be avoided, retried only with new evidence, or expanded

## Current Diagnostic State

Branch: `feature/custom-overworld-wild-movement`

Current ROM checkpoint: `test130.nds`

Current code intentionally idles movement `47`: the descriptor is still installed, but `OverworldWildCustomMovement_Init`, `OverworldWildCustomMovement_Update`, `OverworldWildCustomMovement_Finish`, `OverworldWildCustomMovement_Cleanup`, and `OverworldWildCustomMovement_SetFieldSystem` compile to no-op callbacks. Slot `47` remains aliased to stock no-op. Fresh spawns temporarily use stock movement `0`; the active custom-movement probe starts walk commands on player-step and advances them through a short-lived frame-level `SysTask`.

Previous active hypothesis:

- The descriptor's first word is a movement class/category, not the movement ID.
- Stock wander-like descriptors use first word `3`.
- `test100.nds` used first word `47`, which may have triggered invalid descriptor-class behavior during save/map load even though callbacks were no-op.
- `test101.nds` changes only that descriptor metadata word to `3`.

Previous active hypothesis:

- The crash is caused by slot `47` pointing at overlay 129 data/code during save/map load.
- A movement table entry that points at an existing ARM9-resident stock descriptor should be stable even if spawned objects or saved objects use movement `47`.
- `test102.nds` changes movement slot `47` to alias stock movement `3`.

Previous active hypothesis:

- `test102.nds` loading but crashing after one player step suggests save-load got past the overlay descriptor problem.
- The step crash may be from stale movement-47 objects whose stock movement-3 state was never initialized in earlier builds, or from freshly spawning movement-47 objects.
- `test103.nds` should make stale movement-47 objects no-op and make fresh spawns use stock movement `3` directly.

Previous active hypothesis:

- `test103.nds` still crashes after one player step, so stale movement-47 object execution is less likely.
- The next isolation point is the overworld wild spawner's player-step pipeline: stale-slot dropping, distance despawn, touch battle, ambient cry, or refill/spawn.
- `test104.nds` should run only map-state refresh inside `OverworldWildSpawns_OverlayOnPlayerStep` and skip every downstream step action.

Previous active hypothesis:

- `test104.nds` still crashes after one player step even though the overlay step path returns after map-state refresh.
- The crash may be in `OverworldWildSpawns_OnPlayerStep` before/around overlay loading, inside map-state refresh, or outside the spawner step hook entirely.
- `test105.nds` should disable `OverworldWildSpawns_OnPlayerStep` before it loads or calls the overlay.

Previous active hypothesis:

- `test105.nds` no longer crashes, but Pokemon no longer spawn because the entire player-step hook returns before doing work.
- The crash is inside the overworld-wild hook path.
- `test106.nds` should re-enable the wrapper enough to load overlay 149 and validate its entry pointer, then return before calling the overlay's step function.

Previous active hypothesis:

- `test106.nds` no longer crashes, but Pokemon still do not spawn because the overlay step function is not called.
- Overlay 149 loading itself is safe.
- `test107.nds` should call `entry->onPlayerStep` but make `OverworldWildSpawns_OverlayOnPlayerStep` return immediately before map-state refresh.

Previous active hypothesis:

- `test107.nds` no longer crashes.
- Calling into the overlay step function is safe.
- The crash is inside `OverworldWildSpawns_UpdateMapState`.
- `test108.nds` should run only read-only pointer/map eligibility work inside `OverworldWildSpawns_UpdateMapState`, then return before clearing or writing spawn state.

Previous active hypothesis:

- `test108.nds` no longer crashes.
- Read-only `fieldSystem->mapObjectMan`, `mapObjectMan->objects`, and map eligibility checks are safe.
- The next suspect is a side effect in `OverworldWildSpawns_UpdateMapState`.
- The next ROM should allow only map-state pointer/id writes and the currently no-op movement field-system publish, but skip `OverworldWildSpawns_Clear(state, FALSE)`.

Previous active hypothesis:

- `test109.nds` crashes.
- `test108.nds` did not touch the `OverworldWildSpawnState *state` argument and did not crash.
- `test109.nds` touched state by comparing/writing `state->mapId`, `state->mapObjectMan`, and `state->mapObjects`.
- The next ROM should perform read-only state access only, with no state writes and no field-system publish.

Previous active hypothesis:

- `test110.nds` no longer crashes.
- Reading `state->mapId` from overlay 149 is safe.
- The remaining bundled suspects from `test109.nds` are state writes and the cross-call to `OverworldWildCustomMovement_SetFieldSystem`.
- The next ROM should call the currently no-op field-system setter while still avoiding all state writes.

Previous active hypothesis:

- `test111.nds` crashes.
- The active path only calls `OverworldWildCustomMovement_SetFieldSystem` and returns.
- Disassembly shows the generated veneer switches from Thumb to ARM state, then branches to `0x023D97F4`, even though `OverworldWildCustomMovement_SetFieldSystem` is Thumb code.
- The next ROM should mark the setter as `LONG_CALL`, so the overlay call is generated through a Thumb-safe long-call path.

Purpose of this checkpoint:

- If the next ROM crashes with a corrected long-call veneer, more than call generation is wrong.
- If the next ROM does not crash, the crash was caused by the bad interworking veneer and state writes can be retested.

Previous active hypothesis:

- `test112.nds` keeps the setter-only diagnostic active, with no spawner state writes and no Pokemon spawning.
- The setter is now declared/defined as `LONG_CALL`.
- Disassembly now shows the overlay loads `0x023D97F5` and jumps via `bx r3`, preserving Thumb mode.
- The runtime test should verify whether the crash from `test111.nds` was solely caused by the bad non-`LONG_CALL` veneer.

Purpose of this checkpoint:

- If `test112.nds` does not crash after save load and one player step, the bad veneer is confirmed and state writes can be reintroduced next.
- If `test112.nds` still crashes, the corrected setter call itself or the called code path still has another runtime issue.

Previous active hypothesis:

- `test112.nds` did not crash, so the corrected `LONG_CALL` setter path is runtime-stable.
- The crash in `test109.nds` was likely caused by the broken plain setter call rather than the state writes themselves.
- The next ROM should re-enable map-state writes with the corrected setter call, while still returning before downstream spawn/despawn/battle work.

Purpose of this checkpoint:

- If the next ROM does not crash, map-state writes are safe and the downstream step actions can be reintroduced one at a time.
- If the next ROM crashes, the state writes themselves are still unsafe even after fixing the setter call.

Previous active hypothesis:

- `test113.nds` did not crash, so map-state writes are runtime-stable with the corrected `LONG_CALL` setter.
- The next untested downstream piece is stale-slot cleanup: validating stored spawn object pointers against the current map object list, saving shiny reservations if needed, and clearing stale slots without deleting objects.
- The next ROM should run `OverworldWildSpawns_DropStaleSlots` only, then return before distance despawn, touch battle, ambient cry, or refill/spawn.

Purpose of this checkpoint:

- If the next ROM does not crash, stale-slot validation and clearing are safe enough to keep while moving to distance despawn.
- If the next ROM crashes, the crash is likely in `OverworldWildSpawns_IsCurrentSpawnObject`, shiny-reservation save-on-clear, or `OverworldWildSpawns_ClearSlot`.

Previous active hypothesis:

- `test114.nds` did not crash, so stale-slot validation and clearing are runtime-stable.
- The next downstream piece is distance-based despawn: iterating active spawns, reading map object coordinates, measuring player distance, and deleting far non-shiny objects.
- The next ROM should run `OverworldWildSpawns_DespawnFarMons` after stale-slot cleanup, then return before touch battle, ambient cry, or refill/spawn.

Purpose of this checkpoint:

- If the next ROM does not crash, the empty-state distance-despawn path is safe and the touch-battle path can be isolated next.
- If the next ROM crashes, the crash is likely in distance despawn's object coordinate reads, player coordinate reads, or delete path.

Previous active hypothesis:

- `test115.nds` did not crash, so distance despawn is runtime-stable in the current empty/no-spawn state.
- The next downstream piece is touch-battle detection: grace-step handling, pending battle guards, `justSpawned` handling, player-touch coordinate checks, and potential battle script scheduling.
- The next ROM should run `OverworldWildSpawns_TryStartBattle` after distance despawn, then return before ambient cry or refill/spawn.

Purpose of this checkpoint:

- If the next ROM does not crash, the empty-state touch-battle path is safe and ambient cry can be isolated next.
- If the next ROM crashes, the crash is likely in `OverworldWildSpawns_TryStartBattle`, `OverworldWildSpawns_IsTouchingPlayer`, coordinate reads, or `EventSet_Script` if an old active spawn is still touching the player.

Previous active hypothesis:

- `test116.nds` did not crash, so touch-battle detection is runtime-stable in the current empty/no-spawn state.
- The user asked to spawn Pokemon next.
- The next untested downstream piece is refill/spawn: free-slot search, spawn position selection, encounter rolling, object creation, render params, shiny state, and spawn cooldowns.
- The next ROM should run `OverworldWildSpawns_TryRefill` after touch-battle detection, while still skipping ambient cry so refill/spawn is isolated.

Purpose of this checkpoint:

- If the next ROM spawns Pokemon and does not crash, the refill/spawn path is stable again with stock movement `3` spawns.
- If the next ROM crashes, the crash is likely in spawn position selection, encounter rolling, `CreateSpecialFieldObjectWithParams`, Pokemon render params, shiny setup, or spawn state writes after object creation.

Previous active hypothesis:

- `test117.nds` spawned Pokemon without crashing, so refill/spawn is stable with stock movement `3` and ambient cry skipped.
- The next remaining piece of the stock spawner pipeline is ambient cry: iterating active spawns, reading species/form/shiny metadata, choosing a cry, and calling the sound path.
- The next ROM should restore `OverworldWildSpawns_TryPlayAmbientCry` while keeping fresh spawns on stock movement `3`.

Purpose of this checkpoint:

- If the next ROM spawns Pokemon, plays ambient cries, and does not crash, the full stock spawner pipeline is stable again.
- If the next ROM crashes, the crash is likely in `OverworldWildSpawns_TryPlayAmbientCry`, cry selection, active-spawn metadata reads, or the sound call.

Previous active hypothesis:

- `test118.nds` did not crash, so the full stock spawner pipeline is stable with stock movement `3` and slot `47` no-op.
- Re-pointing slot `47` back at the overlay-resident custom descriptor would repeat Attempts 5 and 6, which crashed even with no-op callbacks.
- The safer next movement probe is spawner-driven: keep fresh spawns on stock movement `3`, keep slot `47` no-op, and only touch active spawned objects' movement params from the stable overlay step path.

Purpose of this checkpoint:

- If the next ROM does not crash, `MapObject_GetParam` and `MapObject_SetParam` are safe to call on active spawned Pokemon from the spawner step loop.
- If the next ROM crashes, the crash is likely in param access on these special objects, not coordinate reads, blocked-direction checks, movement command helpers, or slot-47 descriptor callbacks.

Previous active hypothesis:

- `test119.nds` did not crash, so spawner-driven `MapObject_GetParam`/`MapObject_SetParam` is safe on active spawned Pokemon.
- `test120.nds` isolates the next movement-specific piece: reading active spawned object coordinates, player coordinates, behavior param, and computing the preferred chase/flee direction from the stable overlay step path.
- `test120.nds` still avoids slot-47 callbacks, `object->fsys`, global movement `FieldSystem *`, blocked-direction checks, scratch writes, single-movement flags, and movement command helpers.

Purpose of this checkpoint:

- If `test120.nds` does not crash, position lookup and direction calculation are safe for spawned Pokemon from the spawner step loop.
- If `test120.nds` crashes, the crash is likely in object/player coordinate reads or behavior/direction calculation, not movement command execution.

Previous active hypothesis:

- `test120.nds` did not crash, so position lookup and chase/flee direction calculation are safe for spawned Pokemon from the spawner step loop.
- The next isolated movement-command piece is a non-walking look command issued from the spawner loop on cooldown reset.
- This should test `MapObject_IsSingleMovementActive`, `MapObject_MovementCommandFromDirection`, `MapObject_StartMovementCommand`, and `MapObject_SetSingleMovementActive` without walking commands, blocked-direction checks, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, or slot-47 callbacks.

Purpose of this checkpoint:

- If the next ROM does not crash, spawner-driven look-command setup is safe enough to expand toward actual walking or command update handling.
- If the next ROM crashes, the crash is likely in single-movement flag checking/setting, command construction/start, or conflicts with stock movement ownership.

Previous active hypothesis:

- `test121.nds` did not crash, so spawner-driven non-walking look-command setup is runtime-stable on active spawned Pokemon.
- The user could not visually confirm the look behavior because stock wander masks facing changes.
- The next isolated piece before actual walking is `MapObject_IsMovementDirectionBlocked`, called from the stable spawner loop on the same cooldown tick as the look command.
- This should test blocked-direction lookup without introducing walking commands, movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, or slot-47 callbacks.

Purpose of this checkpoint:

- If the next ROM does not crash, the blocked-direction helper is safe enough to use as the gate for a real spawner-driven walk command.
- If the next ROM crashes, the crash is likely in `MapObject_IsMovementDirectionBlocked` or in asking it during the stock-wander object's active lifecycle.

Previous active hypothesis:

- `test122.nds` did not crash, so `MapObject_IsMovementDirectionBlocked` is runtime-stable from the spawner loop on active spawned Pokemon.
- The next isolated piece is changing the already-safe command-start path from a look command (`0x00`) to a walk command (`0x08`), but only when the blocked check says the preferred direction is open.
- This should test a real spawner-driven walk command without introducing movement-command update/clear calls, scratch writes, `object->fsys`, global movement `FieldSystem *`, or slot-47 callbacks.

Purpose of this checkpoint:

- If the next ROM does not crash and movement is visible, the core spawner-driven chase/flee movement path is viable.
- If the next ROM does not crash but movement is not visible, the command may be masked or consumed by stock movement, and the next step should isolate command ownership/update timing.
- If the next ROM crashes, the crash is likely in starting a walking movement command on a stock-wander object from the spawner loop.

Previous active hypothesis:

- `test123.nds` did not crash, so starting a gated walk command on an active spawned Pokemon from the spawner step loop is runtime-stable.
- Stock movement `3` has its own command state machine and may mask, consume, or overwrite externally started movement commands.
- The next isolated piece is spawner-owned movement-command polling: only after the spawner starts a command, call `MapObject_UpdateMovementCommand` and clear the single-movement flag when it reports completion.
- This should test command ownership/update timing without reintroducing scratch writes, `object->fsys`, global movement `FieldSystem *`, or slot-47 callbacks.

Purpose of this checkpoint:

- If the next ROM does not crash, spawner-driven command update/clear is viable and we can start reducing stock wander's ownership of spawned Pokemon movement.
- If the next ROM crashes, the crash is likely in polling or clearing a movement command from the spawner loop, rather than in starting the command.

Previous active hypothesis:

- `test124.nds` did not crash, so spawner-owned command update/clear polling is runtime-stable.
- The user could not reliably tell whether movement was more directed because stock movement `3` can still mask the spawner command and the command may take multiple updates to complete.
- The next visibility probe should make movement unmistakable by temporarily giving fresh spawns stock idle movement `0`, setting the spawner cooldown to `0`, and burst-polling a spawner-started walk command up to 32 update iterations.
- This should produce a clear tile-step toward the player without using slot-47 callbacks, active custom movement scratch writes, `object->fsys`, or global movement `FieldSystem *`.

Purpose of this checkpoint:

- If the next ROM does not crash and movement is obvious, the spawner-driven movement path works and stock wander was hiding the signal.
- If the next ROM does not crash but movement is still not obvious, the spawner step hook may be the wrong timing surface for visual movement and we should look for a frame-level callback/task.
- If the next ROM crashes, the crash is likely from switching fresh spawns to stock idle movement `0`, burst-polling movement commands, or their combination.

Previous active hypothesis:

- `test125.nds` did not crash and made the movement signal visible, but the burst-poll completed a tile step inside one player-step tick, making the Pokemon look like it teleported.
- The movement-command path itself is viable; the problem is update timing.
- The next isolated piece is a short-lived frame-level `SysTask`: the spawner starts the walk command, creates a task if needed, and the task calls `MapObject_UpdateMovementCommand` once per frame until no spawned Pokemon has an in-progress spawner command.
- This should test smooth movement timing without reintroducing slot-47 callbacks, active custom movement scratch writes, `object->fsys`, or global movement `FieldSystem *`.

Purpose of this checkpoint:

- If the next ROM does not crash and movement animates smoothly toward the player, the frame-task timing surface is the right direction.
- If the next ROM does not crash but Pokemon do not move, the normal `CreateSysTask` queue may not run during this field context or the task may need a different queue/priority.
- If the next ROM crashes, the crash is likely in task creation, task lifetime, or frame-level command polling.

Previous active hypothesis:

- `test126.nds` did not crash and movement animates correctly, but user testing found follow-up behavior issues:
  - only one Pokemon seems able to move at a time
  - after battle, no Pokemon seem able to move
  - movement is not always active even outside those cases
- The stable frame-task timing should be kept, but movement ownership should move out of object param `0` and into per-spawn-slot spawner state.
- Battle start/end should explicitly clear any spawner-owned single-movement commands and reset movement cooldowns, so no stale in-progress marker can survive a battle transition.
- The direction picker should try a secondary axis if the primary chase/flee direction is blocked, rather than suppressing movement immediately.

Purpose of this checkpoint:

- If the next ROM lets multiple Pokemon move, recovers movement after battle, and feels more consistently active, then per-slot ownership plus battle reset is the right foundation.
- If movement still appears limited to one Pokemon, the limitation is likely inside the map-object movement-command system or collision/blocked-direction rules rather than our cooldown marker.
- If movement still dies after battle, the task lifecycle may need to be restarted from the battle cleanup hook or a different field callback.
- If the next ROM crashes, the likely new suspects are clearing single-movement flags during battle transitions or the added per-slot state fields.

Previous active hypothesis:

- `test128.nds` is a huge improvement and fixes the prior quirks, but Pokemon stop chasing after a threshold.
- The threshold is likely the object movement leash: `OverworldWildSpawns_ApplyMovementRange` currently sets X/Y range to `2`, and the chase path is gated by `MapObject_IsMovementDirectionBlocked`.
- The user requested increasing the range to `8` and making Pokemon chase even when the player is not moving.
- The next new test should keep per-slot ownership and frame-task movement updates, set X/Y range to `8`, and make the frame task continue issuing movement decisions from the last valid map context while active spawns exist.

Purpose of this checkpoint:

- If the next ROM keeps chasing past the old threshold, the leash range was the threshold.
- If Pokemon continue chasing while the player stands still, frame-task decision issuing is a viable idle-chase surface.
- If this crashes, the likely new suspect is the frame task retaining and using a `FieldSystem *` outside the player-step call.
- If chasing still stops, `MapObject_IsMovementDirectionBlocked` may enforce more than X/Y range, or the current command type may have another leash/occupancy rule.

New active hypothesis:

- `test129.nds` is starting to look good, but simultaneous movement can sometimes leave two spawned Pokemon on the same tile.
- This is different from earlier blocked-direction and movement-ownership attempts: the issue happens after movement has already succeeded, so prevention alone is not enough.
- The next new test should add a conservative after-the-fact untangle pass that scans active spawn pairs only when no spawner-owned command is in progress.
- When an overlap is found, the pass should start one normal spawner-owned walk command into a valid adjacent unoccupied tile, then wait for that movement to finish before trying another untangle.

Purpose of this checkpoint:

- If overlapped Pokemon separate without crashes, one-at-a-time after-the-fact cleanup is a viable polish layer.
- If overlap remains, the target-tile occupancy check or blocked-direction helper may be rejecting every nearby tile, or current coordinates may not expose the overlap at the frame we scan.
- If this crashes, the likely new suspects are overlap-pair scanning during the persistent frame task or the untangle direction/target validation helpers.
- If cleanup creates new pile-ups, the next direction should reserve target tiles for in-progress commands rather than only checking current map-object occupancy.

## Attempt History

### Attempt 1: Patch Movement Slot `47` To A Custom Descriptor

Idea:

Use vanilla movement slot `47`, which appeared to be unused/null, and point it at `gOverworldWildCustomMovementDescriptor` in overlay 129.

Files/symbols:

- `armips/asm/overworld_wild_movement.s`
- `armips/global.s`
- `scripts/generate_armips_symbols.py`
- `src/overworld_wild_movement.c`
- `include/overworld_wild_movement.h`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Verification:

- Built ROM successfully.
- Verified ARM9 word at `0x020FD2B0` points at `gOverworldWildCustomMovementDescriptor`.
- Verified descriptor word `0` is `47`.
- Verified callback pointers have Thumb bits set.

Runtime result:

- Spawned Pokemon appeared and did not crash.
- Pokemon did not visibly move.

Learning:

- Basic slot patching and descriptor installation are probably viable.
- A custom descriptor can exist without immediately crashing.
- Movement failure was likely inside callback logic or context lookup, not the table patch alone.

Do not repeat:

- Do not re-investigate whether the slot can be patched unless `test100.nds` proves descriptor wiring is actually unstable.

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

### Attempt 3: Publish Active `FieldSystem *` Globally And Add Scratch Init

Idea:

Have the spawner publish the active `FieldSystem *` to boot-resident movement code, then initialize movement scratch state similarly to stock wander. Also add a facing fallback when blocked, so a ticking but blocked callback shows visible activity.

Files/symbols:

- `src/overworld_wild_movement.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/overworld_wild_movement.h`

Runtime result:

- Built as `test98.nds`.
- User reported a crash after taking a single step.

Learning:

- Giving the movement code a real `FieldSystem *` likely allowed the chase path to advance farther than Attempt 2.
- The crash could have been from scratch initialization, movement-state manipulation, blocked-direction checks, command start/update, or the newly reachable player/object coordinate path.

Do not repeat:

- Do not re-enable the full package of global `FieldSystem *` plus scratch init plus movement command helpers all at once.
- Reintroduce only one helper group at a time after the idle diagnostic result is known.

### Attempt 4: Replace `MIi_CpuClearFast` With Direct Scratch Clears

Idea:

Remove the external `MIi_CpuClearFast` call from custom movement init and clear `object->unkD8` with direct word stores.

Files/symbols:

- `src/overworld_wild_movement.c`

Verification:

- Built as `test99.nds`.
- Verified `OverworldWildCustomMovement_Init` no longer calls the external clear helper.
- Verified movement slot `47` still points at the custom descriptor.

Runtime result:

- User reported the crash happened before issuing a player movement command.

Learning:

- The external clear helper was not the only issue.
- Manual scratch clearing plus the rest of the active update/init path is still not safe.
- The crash may occur during object creation, init, early update, or a helper called before the player moves.

Do not repeat:

- Do not treat scratch clearing as solved until isolated.
- Do not retry manual scratch clear together with active movement polling and command helpers without a narrower test.

### Attempt 5: Diagnostic Idle Callback

Idea:

Keep movement slot `47` and the descriptor installed, but make every custom callback no-op. This isolates descriptor/spawn wiring from movement logic.

Files/symbols:

- `src/overworld_wild_movement.c`
- `documentation/overworld_wild_movement_investigation.md`

Verification:

- Built as `test100.nds`.
- Verified descriptor callback pointers are valid Thumb pointers.
- Verified all custom callbacks compile to `bx lr`.

Runtime result:

- User reported the game still crashes when the save is loaded.

Learning:

- Because all callbacks compiled to `bx lr`, the crash is not caused by chase logic, movement-command helpers, coordinate reads, scratch clearing, or custom callback bodies.
- The remaining suspects are descriptor shape/metadata, descriptor storage/load timing, movement `47` object creation semantics, or the engine's handling of a previously null descriptor becoming non-null.

Next decision:

- Try a descriptor metadata-only change before reintroducing any helper logic.

### Attempt 6: Use Stock Step Descriptor Class `3`

Idea:

Keep movement slot `47` patched and keep every custom callback no-op, but change descriptor word `0` from `47` to stock class `3`, matching stock wander-like descriptors.

Why this is new:

- Earlier attempts tested slot `47`, active callbacks, scratch clearing, and no-op callbacks.
- None isolated only the descriptor metadata word while leaving callbacks no-op.

Files/symbols:

- `src/overworld_wild_movement.c`

Expected verification:

- Built ROM should still have ARM9 slot `47` pointing at `gOverworldWildCustomMovementDescriptor`.
- Descriptor word `0` should be `0x00000003`.
- Callback pointers should still be valid Thumb pointers.
- No-op callbacks should still compile to `bx lr`.

Verification:

- Built as `test101.nds`.
- ARM9 movement slot `47` at `0x020FD2B0` points at `0x023DF740`.
- Descriptor words are `0x00000003 0x023D97ED 0x023D97EF 0x023D97F1 0x023D97F3`.
- All callback pointers have Thumb bits set.
- All custom callbacks still compile to `bx lr`.

Runtime result:

- User reported the game still crashes.

Learning:

- Matching stock descriptor class `3` did not fix save-load crash.
- The descriptor's metadata word was not the only issue.
- Because the callbacks were still no-op, the strongest remaining suspect is the movement table entry pointing at overlay 129 rather than an ARM9-resident descriptor.

Do not repeat:

- Do not keep testing overlay 129 no-op/custom descriptors for slot `47` unless there is new evidence that overlay 129 is guaranteed loaded before the movement table is dereferenced.

### Attempt 7: Alias Movement `47` To Stock Movement `3` Descriptor

Idea:

Keep spawned wild Pokemon using movement ID `47`, but patch movement table slot `47` to point at the existing stock movement `3` descriptor in ARM9 (`0x020FD170`) instead of the custom overlay 129 descriptor.

Why this is new:

- Earlier attempts pointed slot `47` at custom overlay 129 descriptors.
- This attempt tests whether save/map load is stable when slot `47` resolves to a known-good ARM9-resident descriptor.

Files/symbols:

- `armips/asm/overworld_wild_movement.s`

Expected verification:

- Built ROM should have ARM9 movement slot `47` at `0x020FD2B0` pointing at `0x020FD170`.
- Slot `47` descriptor words should match stock movement `3`.
- Custom overlay callbacks may still exist in overlay 129, but movement `47` should not reference them.

Verification:

- Built as `test102.nds`.
- Slot `3` at `0x020FD200` points at `0x020FD170`.
- Slot `47` at `0x020FD2B0` also points at `0x020FD170`.
- Slot `3` and slot `47` descriptor words both read `0x00000003 0x020613A1 0x020613F9 0x0205FCBD 0x0205FCC1`.

Runtime result:

- User reported the save loaded, then the game crashed after a single player step.

Learning:

- Aliasing movement `47` to stock movement `3` likely avoids the save-load crash.
- The step-time crash remains.
- A plausible cause is that existing saved movement-47 objects now run stock movement-3 update without having gone through stock movement-3 init.
- Another plausible cause is that using movement ID `47` for freshly created objects is unsafe in some non-descriptor engine path.

Do not repeat:

- Do not alias stale movement `47` directly to active stock movement `3` again unless the object's movement scratch/init state is also migrated.

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

### Attempt 10: Disable The Entire Overworld-Wild Player-Step Hook

Idea:

Return `FALSE` immediately from `OverworldWildSpawns_OnPlayerStep`, before `OverworldWildSpawns_GetOverlayEntry` can load the overlay and before `entry->onPlayerStep` can run.

Why this is new:

- Attempt 9 still loaded and called overlay 129, then returned after map-state refresh.
- No previous attempt disabled the ARM9 wrapper hook before overlay loading.

Files/symbols:

- `src/overworld_wild_spawns.c`

Expected verification:

- `OW_WILD_DISABLE_PLAYER_STEP_HOOK` should be `1`.
- `OverworldWildSpawns_OnPlayerStep` should return `FALSE` without calling `OverworldWildSpawns_GetOverlayEntry`.
- The build should keep movement slot `47` pointing at the stock no-op descriptor from Attempt 8.

Verification:

- Built as `test105.nds`.
- Disassembly of `OverworldWildSpawns_OnPlayerStep` is `movs r0, #0; bx lr`, so it returns `FALSE` before any overlay-load path.
- `PlayerStepEvent_RepelCounterDecrement` still calls `OverworldWildSpawns_OnPlayerStep`, but the call now always falls through to normal repel handling.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported that the game no longer crashes, but Pokemon no longer spawn.

Learning:

- The one-step crash is caused by the overworld-wild player-step hook path.
- The movement table aliasing and general walking engine are not sufficient to crash on their own in this test.
- Spawns stop because the hook is fully disabled, so this is only a narrowing checkpoint rather than a usable solution.

Do not repeat:

- Do not leave `OverworldWildSpawns_OnPlayerStep` fully disabled except as a diagnostic.
- Continue by bisecting inside the hook: overlay load first, then overlay map-state refresh.

### Attempt 11: Load Overlay Entry But Do Not Call Overlay Step

Idea:

Re-enable `OverworldWildSpawns_OnPlayerStep` enough to call `OverworldWildSpawns_GetOverlayEntry` and check `entry->onPlayerStep`, then return `FALSE` before calling the overlay step function.

Why this is new:

- Attempt 10 returned before overlay loading.
- Attempt 9 loaded and called the overlay step function, which still crashed.
- This attempt isolates overlay loading and entry lookup from overlay step execution.

Files/symbols:

- `src/overworld_wild_spawns.c`

Expected verification:

- `OW_WILD_DISABLE_PLAYER_STEP_HOOK` should be `0`.
- `OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY` should be `1`.
- `OverworldWildSpawns_OnPlayerStep` should call `OverworldWildSpawns_GetOverlayEntry`, validate `entry->onPlayerStep`, and return `FALSE` before `entry->onPlayerStep(fieldSystem, &sOverworldWildSpawnState)`.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test106.nds`.
- Disassembly of `OverworldWildSpawns_OnPlayerStep` calls `OverworldWildSpawns_GetOverlayEntry` and then returns `FALSE`.
- The compiler optimized away the `entry->onPlayerStep` validation because the diagnostic path returns before using the entry; this ROM isolates overlay load only, not entry-pointer reading.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash, and no Pokemon spawn.

Learning:

- Overlay loading alone is safe.
- Pokemon do not spawn because the ROM intentionally returns before calling `entry->onPlayerStep`.
- The next boundary is the overlay step function entry itself versus map-state refresh.

Do not repeat:

- Do not keep testing overlay load-only behavior; it has been ruled safe.

### Attempt 12: Call Overlay Step But Return Immediately

Idea:

Allow `OverworldWildSpawns_OnPlayerStep` to call `entry->onPlayerStep`, but make `OverworldWildSpawns_OverlayOnPlayerStep` return `FALSE` immediately before `OverworldWildSpawns_UpdateMapState`.

Why this is new:

- Attempt 11 loaded overlay 149 but did not call the overlay step function.
- Attempt 9 called the overlay step function and then ran map-state refresh before returning.
- This attempt isolates the overlay function call boundary from map-state refresh.

Files/symbols:

- `src/overworld_wild_spawns.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OW_WILD_PLAYER_STEP_DIAGNOSTIC_LOAD_ONLY` should be `0`.
- `OW_WILD_STEP_DIAGNOSTIC_ENTRY_ONLY` should be `1`.
- `OverworldWildSpawns_OnPlayerStep` should call `entry->onPlayerStep`.
- `OverworldWildSpawns_OverlayOnPlayerStep` should return `FALSE` before `OverworldWildSpawns_UpdateMapState`.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test107.nds`.
- Disassembly of `OverworldWildSpawns_OnPlayerStep` shows it calls `OverworldWildSpawns_GetOverlayEntry`, validates the entry and `entry->onPlayerStep`, then calls through the overlay entry.
- Disassembly of `OverworldWildSpawns_OverlayOnPlayerStep` is `movs r0, #0; bx lr`, so it returns `FALSE` before `OverworldWildSpawns_UpdateMapState`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Overlay step entry itself is safe.
- The next suspect is the body of `OverworldWildSpawns_UpdateMapState`.

Do not repeat:

- Do not keep testing entry-only overlay calls; they have been ruled safe.

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

### Attempt 17: Mark Movement Setter As LONG_CALL

Idea:

Change `OverworldWildCustomMovement_SetFieldSystem` to a proper `LONG_CALL` declaration/definition, matching the repo's normal cross-region function declarations, while keeping the same setter-only diagnostic active.

Why this is new:

- Attempt 16 proved the plain generated veneer crashes.
- No previous attempt changed the setter's calling convention or verified the generated interworking veneer.

Files/symbols:

- `include/overworld_wild_movement.h`
- `src/overworld_wild_movement.c`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`

Expected verification:

- `OverworldWildCustomMovement_SetFieldSystem` should be declared and defined with `LONG_CALL`.
- The active overlay step path should still only call the setter and return `FALSE`.
- Disassembly should no longer show a veneer that switches to ARM state and branches to `0x023D97F4` without the Thumb bit.
- The setter itself should still compile to `bx lr`.
- Movement slot `47` should remain stock no-op.

Verification:

- Built as `test112.nds`.
- `OverworldWildCustomMovement_SetFieldSystem` is declared and defined with `LONG_CALL`.
- Disassembly shows the active overlay step path loads `0x023D97F5` and jumps via `bx r3`, so the Thumb bit is preserved.
- Disassembly of `OverworldWildCustomMovement_SetFieldSystem` is still `bx lr`.
- The active overlay path still only calls the setter and returns `FALSE`.
- Movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.

Runtime result:

- User reported no crash.

Learning:

- Build-time evidence supports the interworking hypothesis from Attempt 16.
- Runtime result confirms the corrected setter-only path is stable.
- The next retest can bring back map-state writes because the prior state-write crash included the broken setter call.

Expand:

- Re-enable map-state writes with `OW_WILD_UPDATE_DIAGNOSTIC_SETTER_ONLY` disabled, while keeping `OW_WILD_STEP_DIAGNOSTIC_UPDATE_ONLY` enabled.

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

### Attempt 29: Spawner-Owned Movement Command Update And Clear

Idea:

Keep spawned Pokemon on stock movement `3` and keep movement slot `47` aliased to stock no-op. When the spawner starts a walk command, mark the existing movement cooldown param as `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` (`-1`). On the next spawner tick for that object, call `MapObject_UpdateMovementCommand`; if it reports completion, call `MapObject_ClearSingleMovementActive` and restore the normal cooldown.

Why this is new:

- Attempt 28/`test123.nds` proved starting a gated spawner-driven walk command does not crash.
- Earlier update/clear attempts happened inside the slot-47 custom movement callback and were bundled with scratch writes, `object->fsys`, global movement `FieldSystem *`, or overlay movement descriptor concerns.
- No previous build has isolated `MapObject_UpdateMovementCommand` plus `MapObject_ClearSingleMovementActive` from the stable overlay-149 spawner step loop while keeping fresh spawns on stock movement `3`.

Files/symbols:

- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `documentation/overworld_wild_movement_attempt_log.md`

Expected verification:

- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND` should be `1`.
- The active probe should use `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` (`-1`) only after starting a spawner-driven walk command.
- The active probe should call `MapObject_UpdateMovementCommand` only when the cooldown param is in-progress.
- The active probe should call `MapObject_ClearSingleMovementActive` only if `MapObject_UpdateMovementCommand` returns complete.
- The active probe should still avoid scratch writes, `object->fsys`, global movement `FieldSystem *`, and slot-47 callbacks.
- Fresh spawns should still use stock movement `3`; movement slot `47` should remain stock no-op for stale objects.

Runtime result:

- User reported no crash.
- User could not reliably tell whether movement was more directed or less random.

Learning:

- Spawner-owned `MapObject_UpdateMovementCommand` and `MapObject_ClearSingleMovementActive` are runtime-stable in the current player-step hook.
- The visual signal is still too subtle while fresh spawns use stock movement `3`.
- The next diagnostic should remove stock-wander interference and exaggerate command progression.

Verification:

- Built as `test124.nds`.
- `OW_WILD_SPAWNER_MOVEMENT_DIAGNOSTIC_UPDATE_COMMAND` is enabled.
- Source verification shows `OW_WILD_SPAWNER_MOVEMENT_PARAM_IN_PROGRESS` (`-1`) is assigned only after the spawner starts a walk command.
- Source verification shows `MapObject_UpdateMovementCommand` is called only when the cooldown param is in-progress.
- Source verification shows `MapObject_ClearSingleMovementActive` is called only if `MapObject_UpdateMovementCommand` returns complete.
- Disassembly target scan shows the newly added `MapObject_UpdateMovementCommand` at `0x02062429` and `MapObject_ClearSingleMovementActive` at `0x0205F63D`.
- Disassembly target scan still shows the prior movement setup targets: `MapObject_IsMovementDirectionBlocked` at `0x02060BB9`, `MapObject_IsSingleMovementActive` at `0x0205F649`, `MapObject_MovementCommandFromDirection` at `0x0206234D`, `MapObject_StartMovementCommand` at `0x0206217D`, and `MapObject_SetSingleMovementActive` at `0x0205F631`.
- Source still avoids active custom movement scratch writes, `object->fsys`, and slot-47 callbacks; `OverworldWildCustomMovement_SetFieldSystem` remains no-op under the current idle diagnostic.
- Fresh spawns still use stock movement `3`; movement slot `47` at `0x020FD2B0` still points at stock no-op descriptor `0x020FCEC8`.
- Copied to Delta as `test124.nds`.
- `git diff --check` passed.

Expand:

- Temporarily switch fresh spawns from stock movement `3` to stock idle movement `0` so only the spawner-owned command should move them.
- Set `OW_WILD_SPAWNER_MOVEMENT_PARAM_RESET` to `0` so a new command can be started as soon as the previous command finishes.
- Burst-poll the command up to a bounded number of iterations immediately after starting it so a successful command should visibly complete a tile step.

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

- Pending user test.

Learning:

- Pending.

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
