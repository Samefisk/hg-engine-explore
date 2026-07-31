# Summary move relearn — task 5 PC ownership and switching

Task 5 extends the modern Summary relearn flow to the retail PC Summary path
and makes real Summary Pokémon switching an identity boundary. It preserves
the task 1–4 history, candidate, inline preview, confirmation, PP, touch,
save, and overlay-lifecycle contracts.

## Entry paths and controls

The party path remains the normal field/Party-menu Summary:

- `dataType == 1`, `ppd` is the retail `Party *`, and `pos` is resolved by
  `Summary_GetPokemonData` through `Party_GetMonByIndex`.
- While relearn is inactive, retail Up/Down and direct party-position touch
  controls switch Pokémon normally.

The boxed path is the nested Summary launched by the retail PC application:

- the PC parent passes the active box's canonical slot-zero pointer,
  `dataType == 2`, `limit == 30`, and the selected box slot in `pos`;
- `Summary_GetPokemonData` resolves the selected encrypted `BoxPokemon`;
- the PC previous/next arrows remain the real boxed switching controls.

The acceptance controls use the retail party icon hitboxes (actions 4–9;
left/right columns at approximately `x=184/224` and rows
`y=52/60`, `84/92`, and `116/124`) and the retail PC previous/next arrows
at `(215,50)` and `(215,115)`. These are delegated to retail Summary rather
than reimplemented.

On the normal Moves page, both paths show `X: Relearn` with the same key and
touch behavior documented for task 4. Candidate and slot Up/Down remain list
navigation. During any relearn substate, direct party-position touch or the PC
previous/next arrows cancel the old transaction, perform the retail switch,
and restart at a fresh candidate list for the new identity. Left/Right page
changes and retail Cancel also cancel the modal and delegate to retail; they
do not carry candidate state to another page or owner. Custom candidate,
slot, confirmation, HM, success, prompt-strip, and blue-Cancel hitboxes retain
priority, including their exact blank gaps.

## Ownership and mutation

Summary never indexes a serialized party or box array. It validates the
supported owner and bounds, then uses `Summary_GetPokemonData`. Party results
are reduced to their named `box` prefix; PC results are already the canonical
boxed record. Raw contiguous `dataType == 0`, non-PC boxed limits, eggs, empty
slots, checksum failures, and unsupported owners fail closed.

Candidate construction remains the task-2
`PokemonMoveRelearn_BuildCandidates` call. It is read-only, excludes known
moves, and preserves deterministic acquisition order for both party and boxed
records.

Only explicit confirmation calls task 3's
`PokemonMoveHistory_ReplaceMove(BoxPokemon *, move, slot)`. That transaction
captures the before-history once, uses canonical encrypted
`SetBoxMonData` operations for the move, zero PP Ups, and full base PP, verifies
the readback, and appends the after-history once. Summary sets the named
`pokemonChanged` output at arguments offset `+0x38` only after that call
succeeds.

For a boxed result, the PC parent consumes `pokemonChanged` after the nested
Summary exits and calls `PCStorage_SetBoxModified` for the active box. Summary
does not own the storage pointer or box number and never dirties storage
directly. Browse, scroll, preview, confirmation cancellation, HM rejection,
switching, page changes, empty/egg rejection, and exit perform no Pokémon
setter, history observation, PC dirty operation, or save write. A prior
successful change remains dirty even if the player subsequently switches.

## Identity and cancellation boundaries

Each modal transaction records the exact arguments object, position, and
canonical `BoxPokemon *`. UI cache restoration is allowed only while all
three still identify the old owner. Before a delegated retail switch, the old
move rows, temporary argument move, prompt, prospective window, detail pane,
and modal state are cleared. Retail then owns the position update, Pokémon
refresh, cry/picture animation, page buttons, cursor, and touch behavior.

After the transition, candidates, cursor, scroll top, pending move, selected
slot, and preview are rebuilt from zero for the newly resolved identity.
Switching from list, empty, slot, confirmation, HM-blocked, or success state
cannot copy an old move, candidate, slot, or history record into the new
Pokémon. A success-state switch keeps the already confirmed mutation but
discards only its UI transaction.

## Normal PC transfers

Retail deposit, withdraw, box move, and party/box swap paths copy the complete
`BoxPokemon` through `CopyBoxPokemonToPokemon`, `Mon_GetBoxMon`,
`PCStorage_PlaceMonInBoxByIndexPair`, and the corresponding canonical removal
or placement operations. PID and OTID do not change. Because move history is
keyed by PID plus OTID rather than party/box position, the same history record
and candidate order follow a normal transfer without migration, duplication,
or orphan records. Canonical PC placement/removal owns its separate box dirty
signals.

The focused runtime round trip uses only actual retail UI:

1. terminal → Someone's PC → Withdraw Pokémon → Box 1 slot 0 → WITHDRAW;
2. exit the PC, open party slot 5 through the field Party menu, and enter
   relearn to verify the identity's rebuilt candidate order;
3. return to the terminal → Deposit Pokémon → party slot 5 → DEPOSIT →
   Box 1 slot 0;
4. exit, retail-save, fresh-load, and reopen Box 1 slot 0 through Move Pokémon
   and nested Summary.

The transfer itself never calls a history migration API. Runtime acceptance
requires the same PID/OTID, the same single history record, byte-exact restored
party and boxed records, Box 1 dirty before save, authenticated normal and PC
generation advancement, and valid checksums for all six `0xEC` party records
and all 900 `0x88` boxed records.

## Lifecycle and exclusions

PC Summary uses the same `gOverlayTemplate_PokemonSummary` nested application
template, so overlay 154 is loaded for the complete child lifetime and
unloaded on return to the PC exactly as it is for field Summary. Task state
remains in the zeroed Summary work extension, and overlay 153 remains the
resident history/candidate ABI owner.

Task 5 does not audit daycare, trade, gift, scripted, form-change, Pokéwalker,
or other unusual acquisition paths (task 6). It does not enable the optional
all-compatible testing policy (task 7). Raw temporary/rental Summary owners
are deliberately excluded.

## Verified packaged artifact

The task-5 Workshop artifact used by the final headless acceptance has:

- ROM SHA-256
  `5048ce95266dbf62e1bf9e2a2eb56c8831730badf744d5a4636dd255fe6e1a11`;
- publication manifest SHA-256
  `cf1b79d1f4b5dd497669b2457e879d3686e94f5fc596c4f562bf7f1659525188`;
- overlay 154 SHA-256
  `7828a5c4d1359501c7445c914aca09930a5d1b249a2bc282ef13acde5b366c47`,
  size `0xCDC` (3292 bytes), base `0x023C0400`, reserved size `0x1EA0`,
  and remaining headroom `0x11C4` (4548 bytes).

The controlled fixture is derived from the immutable source DSV with SHA-256
`75ddaf8a974d50c70d403e6658bd8497351a5fca0b729a854d6483c39018054d`.
Generated ROMs, saves, screenshots, and result JSON remain build artifacts and
are not committed.
