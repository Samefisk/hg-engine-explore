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

Current ROM checkpoint: `test101.nds`

Current code intentionally idles movement `47`: the descriptor is still installed, but `OverworldWildCustomMovement_Init`, `OverworldWildCustomMovement_Update`, `OverworldWildCustomMovement_Finish`, `OverworldWildCustomMovement_Cleanup`, and `OverworldWildCustomMovement_SetFieldSystem` compile to no-op callbacks.

New active hypothesis:

- The descriptor's first word is a movement class/category, not the movement ID.
- Stock wander-like descriptors use first word `3`.
- `test100.nds` used first word `47`, which may have triggered invalid descriptor-class behavior during save/map load even though callbacks were no-op.
- `test101.nds` changes only that descriptor metadata word to `3`.

Purpose of this checkpoint:

- If `test100.nds` still crashes, the problem is likely descriptor/slot/spawn wiring rather than chase logic.
- If `test100.nds` does not crash, the next culprit is one of the disabled helper paths.

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

- Pending.

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
