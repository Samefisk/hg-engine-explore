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

Current ROM checkpoint: `test106.nds`

Current code intentionally idles movement `47`: the descriptor is still installed, but `OverworldWildCustomMovement_Init`, `OverworldWildCustomMovement_Update`, `OverworldWildCustomMovement_Finish`, `OverworldWildCustomMovement_Cleanup`, and `OverworldWildCustomMovement_SetFieldSystem` compile to no-op callbacks.

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

New active hypothesis:

- `test105.nds` no longer crashes, but Pokemon no longer spawn because the entire player-step hook returns before doing work.
- The crash is inside the overworld-wild hook path.
- `test106.nds` should re-enable the wrapper enough to load overlay 149 and validate its entry pointer, then return before calling the overlay's step function.

Purpose of this checkpoint:

- If `test106.nds` still crashes, overlay loading or entry lookup is the culprit.
- If `test106.nds` does not crash, the next culprit is inside `entry->onPlayerStep`, most likely map-state refresh.

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
