# Movement Architecture And Frame Task

> **Status: historical attempt collection, not current architecture.** The
> canonical design is
> [`documentation/overworld-system/architecture.md`](overworld-system/architecture.md).
> The sections below preserve evidence from earlier movement experiments.

Generated from `documentation/overworld_wild_movement_attempt_log.md` during consolidation.
The original attempt sections are copied verbatim below. Attempts may appear in multiple topic files on purpose.

## Quick Reference

- Stable movement architecture: avoid slot-47 overlay callbacks unless descriptor lifetime is solved.
- Spawner-owned commands plus a frame SysTask are the safe base for custom movement.
- Per-slot movement ownership, route/context guards, command settle windows, and conservative stock command families are the main lessons.

## Included Attempts

| Source order | Attempt | Title |
|---:|---:|---|
| 1 | 1 | Patch Movement Slot `47` To A Custom Descriptor |
| 2 | 2 | Chase Logic Using `object->fsys` |
| 3 | 3 | Publish Active `FieldSystem *` Globally And Add Scratch Init |
| 4 | 4 | Replace `MIi_CpuClearFast` With Direct Scratch Clears |
| 5 | 5 | Diagnostic Idle Callback |
| 6 | 6 | Use Stock Step Descriptor Class `3` |
| 7 | 7 | Alias Movement `47` To Stock Movement `3` Descriptor |
| 8 | 8 | Make Stale Movement `47` No-Op And Spawn Fresh Objects With Stock Movement `3` |
| 9 | 9 | Disable Spawner Step Actions After Map-State Refresh |
| 10 | 10 | Disable The Entire Overworld-Wild Player-Step Hook |
| 11 | 11 | Load Overlay Entry But Do Not Call Overlay Step |
| 12 | 12 | Call Overlay Step But Return Immediately |
| 13 | 13 | Read-Only UpdateMapState Diagnostic |
| 14 | 14 | UpdateMapState Map Writes Without Clear |
| 15 | 15 | Read Spawn State Without Writing It |
| 16 | 16 | Call No-Op Movement Setter Without State Writes |
| 17 | 17 | Mark Movement Setter As LONG_CALL |
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
| 29 | 29 | Spawner-Owned Movement Command Update And Clear |
| 30 | 30 | Obvious Spawner-Driven Tile Movement |
| 31 | 31 | Frame Task Movement Command Updates |
| 32 | 32 | Per-Slot Movement Ownership And Battle Reset |
| 33 | 33 | Range 8 And Idle Frame Chase |
| 34 | 34 | One-At-A-Time Overlap Untangle |
| 35 | 35 | Guard Idle Frame Context And Moving Battle Contact |
| 36 | 36 | Frame Task Battle Detection |
| 37 | 37 | Post-Movement Battle Settle Window |
| 38 | 38 | Pidgey Fast Movement Command |
| 39 | 39 | Movement Speed Levels 1-6 |
| 40 | 40 | Pidgey Speed 6 Test |
| 41 | 41 | Alias High Logical Speeds To Fastest Stock Walk |
| 42 | 42 | Proximity-Only Battle Settle |
| 43 | 43 | Cap High Speeds To Fluent Walk Command |
| 44 | 44 | Non-Blocking Battle Retry Between Chained Commands |
| 63 | 63 | Behavior Profile Resolver |
| 64 | 64 | Separate Behavior Class Rules From Behavior Variable Overrides |
| 101 | 65 | A-Button Facing Interaction Starts Spawn Battle |
| 109 | 66 | Implement Behavior Profile Table Semantics |
| 181 | 103 | Behavior-Gated Ledge Far Jump |
| 183 | 105 | Rename Aggressive Chase Profile |
| 202 | 124 | Score Playful Ledge Jumps By Landing Tile |
| 203 | 125 | Include Moving Target Trail For Playful Scoring |
| 204 | 126 | Shared Moving Player Target For Movement Intent |

## Original Attempt Sections

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
