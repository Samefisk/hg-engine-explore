# Summary move relearn — task 3 capture hooks

Task 3 owns only permanent move-history capture. It does not add the Summary
candidate/replacement UI, box switching, unusual acquisition audits, or testing
policy modes.

## Central transaction APIs

Cross-module calls target typed fixed Thumb entries in boot-resident overlay
153. Each commit resolves the active save through `SaveBlock2_get()` at that
moment; no `SaveData *` is retained between calls.

- `PokemonMoveHistory_RecordMove`: rejects invalid or unimplemented input
  before snapshot/store access, then records a confirmed non-destructive
  level-up append after success.
- `PokemonMoveHistory_ReplaceMove`: rejects invalid or unimplemented input
  before inspecting history or Pokémon data, captures and records the old
  four slots, mutates through
  `SetBoxMonData`, verifies the learned slot by readback, then records the new
  valid implemented move. A canonical read of only the requested slot returns
  `FALSE` for same-slot no-ops before the full snapshot or any save/history
  access. Snapshot failures also return before mutation.
- `PokemonMoveHistory_DeleteMoveSlot`: records the current four slots at the
  committed Move Deleter command, then delegates to retail
  `MonDeleteMoveSlot`.

`MOVE_NONE`, out-of-range moves, and `IsMoveUnimplemented` moves are rejected by
the shared append predicate. Duplicate current moves do not reorder or dirty
history.

## Exact commit hooks

- Level-up append: `MonTryLearnMoveOnLevelUp` records only after
  `TryAppendMonMove` returns a learned move, excluding full, already-known, and
  no-move results. This covers battle, Rare Candy, and evolution append paths.
- TM/HM and Rare Candy replacement: both converge on
  `PartyMenu_LearnMoveToSlot`, which delegates once to the central replacement
  transaction. Prompt cancellation and compatibility failures never enter it.
- Evolution replacement: ARM9 `0x020769F0`, the confirmed
  `MonSetMoveInSlot(mon, move, slot)` commit call.
- Battle level-up replacement: overlay 12 `0x02246344`, inside
  `Task_GetExp`’s `STATE_GET_EXP_LEARNED_MOVE`. Cancel/give-up states do not
  reach this call.
- Move Reminder and its special tutor UI: overlay 68
  `ov68_021E614C`, with the complete `0x021E6158..0x021E6165` span rewritten
  only after the UI has resolved a confirmed move and slot. A final Thumb NOP
  overwrites the retail BL suffix at `0x021E6164`, so return continues at
  `0x021E6166`. The retained PP writes are idempotent.
- Standard script tutor helper: only retail `PartyMonSetMoveInSlot`'s final
  setter call at `0x020542E0` is redirected. Its preceding
  `Party_GetMonByIndex` call at `0x020542D6` remains the canonical Party to
  PartyPokemon access boundary.
- Move Deleter: only the `ScrCmd_MonForgetMove` delete call at `0x0204DCCC` is
  redirected. The script reaches it after move selection and its second
  confirmation.

## Ownership reconciliation and overlap

Primary-save preparation reconciles the saved player party in slot order after
the active save and normal ownership state are established. It uses
`Party_GetCount` and `Party_GetMonByIndex`, never compiler array arithmetic
over serialized `PartyPokemon` records. The earlier load-side hook now loads
only the sidecar; it deliberately does not inspect PartyPokemon while the save
lifecycle is still settling. The save boundary seeds newly acquired normal
party Pokémon, including inherited egg moves, without repeated revision churn:
existing moves are deduplicated and retain first-observed order.

High-level replacement paths and low-level helpers have one transaction owner:
Party Menu delegates directly to `ReplaceMove`; battle/evolution/overlay 68
replace only their final setter call; and the standard tutor redirects only
the shared helper's final setter. Old slots are recorded before mutation and
the new move only after successful readback, so high-level and low-level paths
never double-record or invert acquisition order.

Overlay 153 links an overlay-local interworking helper containing only the
uniquely named retail `memcpy` and `memset` bridges it actually references.
All three copy calls and the one clear call resolve inside overlay 153 before
interworking to the retail ARM routines. This keeps the fixed `0x1000` code
guard intact without consuming overlay 129 headroom.

The build forces the six task-3 C/assembly objects to be rebuilt, packages the
temporary ROM, then seals a content-addressed manifest over their generated
dependency/ARMIPS include-and-incbin closure, generated linker script,
effective build flags, identities of the actual compiler/assembler/linker/
objcopy/ARMIPS/ndstool commands, `build/linked.o`, both linked binaries, the
patched ARM9/consumed overlays, y9, and the packaged ROM. The packaged ROM is a
logical content role, so the retained manifest remains valid after `.tmp` is
published as `test.nds` and can be rechecked on the macOS host without requiring Docker's
absolute tool paths. The capture verifier accepts `--rom` only with that exact
manifest. Hashes—not mtimes—make absent, modified, or coherently touched stale
generations fail closed.

Post-package checks authenticate unique dense overlay/file IDs and exact
y9/FAT metadata for overlays 12, 68, 129, and 153. Overlay 129's complete
`IsMoveUnimplemented` body and controlling call are exact-checked. Complete
packaged bodies and BL/BLX (including register-form) call allowlists cover
`MonTryLearnMoveOnLevelUp`, `PartyMenu_LearnMoveToSlot`, `RecordMoveImpl`,
`ReplaceMoveImpl`, and `DeleteMoveSlotImpl`; all earlier fixed-entry, hook
window/continuation, local-helper, relocation, interworking, `0xEC` layout,
candidate, and sidecar checks remain. Deterministic source mutation fixtures
reject wrong arguments, ignored/duplicate predicates, pre-guard mutations,
guard/result clobbers, and reordered deletion. Host fixtures retain invalid,
unimplemented, canceled, no-op, snapshot-failure, replacement-order, and
deletion coverage. Invalid `RecordMove` and `ReplaceMove` prove no allocation,
dirty flag, revision, Pokémon mutation, or successful return for empty and
existing stores; same-slot replacement additionally proves no snapshot/store
access and a `FALSE` result.

## Deliberate exclusions

Reserved for later tasks are the Summary list/replacement UI, PC box switching
and boxed acquisition reconciliation, broad scripted gift/trade/form/daycare/
Pokéwalker audits, and all-compatible testing mode. The shared script helper
captures calls that already use the normal permanent four-slot setter, but task
3 does not claim that as a complete audit of unusual scripted sources.
