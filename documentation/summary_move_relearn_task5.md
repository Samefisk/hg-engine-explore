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
boxed record. Party resolution first caches the signed `Party_GetCount`
result and requires count and Summary limit to both be in `1..6`, with
position below count, limit, and the physical six-record capacity. Raw
contiguous `dataType == 0`, non-PC boxed limits, invalid positions, eggs,
empty slots, checksum failures, species outside the base-species domain,
invalid forms, and unsupported owners fail closed before the prompt or
candidate builder. A malformed owner or position is consumed by the custom
dispatcher and is never delegated to retail Summary code that could resolve
the invalid storage reference.

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

Focused lifecycle acceptance reads the live overlay registry during the
actual terminal → Move Pokémon → boxed context menu → Summary nesting. It
requires overlay 154 active in the first child, inactive after the parent
resumes, a complete fresh-zero `0xC0` extension on a second Summary opening,
and a second registry-confirmed unload. Party switching acceptance separately
uses the real party icons from HM-blocked and success states: HM cancellation
is byte-exact, while success preserves the single committed mutation/history
only on the original identity and rebuilds the correct candidates on return.

Controlled fail-closed acceptance opens the retail Summary Info page first.
Party and PC record fixtures are injected on the exact frame retail page mode
changes to Moves. PC owner-metadata fixtures are injected only after the same
real retail transition reaches a stable Moves page, because transition code
resolves the current boxed slot before the hooked main-state callback.
Expected owner, party, complete PC storage, and history bytes are captured
immediately after injection and before another emulated frame. The custom
guard then consumes malformed owner input without delegating it to retail
lookup code. This proves that position 30 has the same pre-frame PC hash as
owner-only `dataType` and limit probes. Party probes cover
signed counts `-1`, `0`, and `7`, limits `0` and `7`, position `6`,
`dataType == 0`, empty, egg, checksum-failed, species `MAX_MON_NUM + 1`, and
Tentacool form 31. The real PC child covers `dataType == 0`, boxed limit 29,
position 30, and the same record faults. Every probe requires the entire
extension to remain zero, owner and PC dirty flags to remain clear, and party,
PC storage, and history bytes to remain exact. The valid natural zero-
candidate case remains a separate mode-2 test.

Species and form are also revalidated immediately before both possible
`SummaryMoveRelearn_Enter` calls: the resumed-switch path and the shared
key/touch prompt path. Authenticated party and PC fixtures first display the
real prompt, then inject invalid species for key activation and invalid form
for touch activation. Rejection clears the prompt to a zero extension without
candidate construction, history observation, setters, dirtying, or byte
changes beyond the controlled injected record.

Runtime results are provenance-bound evidence. The publication manifest seals
the external runtime launcher, runtime verifier worker, manifest helper,
headless helper, and party-integrity helper. The launcher is the only supported
entry point. Its top-level prelude uses only `os` and `sys`; it resolves and
unlinks every requested result target before argument parsing, helper imports,
DeSmuME loading, or verifier compilation. Syntax, import, missing-dependency,
authentication, and argument failures therefore cannot leave an old passing
result in place. Only the authenticated verifier worker may atomically publish
a replacement.

Before any authenticated helper executes, the launcher independently hashes
and strictly parses the publication manifest, pins the expected launcher and
verifier revisions, reads all five source files once, and checks their exact
retained bytes against the manifest. It compiles those retained buffers with
no import loader, injects the retained headless module into the retained party
helper, and executes module namespaces with `__cached__ = None`. Timestamp-
valid `.pyc` files and later filesystem source replacements are never eligible
for execution. The manifest helper does not authenticate itself: its retained
source must first match the independently parsed manifest record.

Authentication is repeated against the live manifest, ROM, and every source
at the start and end of emulation. Serialized child scenarios launch through
the same authenticated launcher and must return an artifact-authentication
block exactly equal to the parent before their evidence is consumed. The JSON
records the ROM, publication manifest, launcher, verifier, manifest helper,
and runtime-helper SHA-256 records, plus retained-buffer and pycache-bypass
claims. Focused host fixtures prove rejection of a corrupted manifest-helper
source, prove a normal source loader executes three valid-header poisoned
`.pyc` fixtures while the retained-buffer path does not, and prove stale-result
removal before syntax, import, dependency, and argument failures.

Task 5 does not audit daycare, trade, gift, scripted, form-change, Pokéwalker,
or other unusual acquisition paths (task 6). It does not enable the optional
all-compatible testing policy (task 7). Raw temporary/rental Summary owners
are deliberately excluded.

## Verified packaged artifact

The task-5 Workshop artifact used by the final headless acceptance has:

- ROM SHA-256
  `24afe7078d3986c0f282d4908d22fd8eda4e5d7df0721092da9b986f8c6a0177`;
- publication manifest SHA-256
  `1d45c9ffb19c0242acbad0e497c31a5ce34ec698552a25ef7d8c09cef7e9de3f`;
- runtime launcher SHA-256
  `e9dccb131889afa847ccf18aaa425b302a5862b2e05bcbb61325394b5bcaac0f`;
- runtime verifier SHA-256
  `829e68f5f3e4a102cbc1097627da24e5565ec8cd3911ead128d73b098803f391`;
- runtime result SHA-256
  `9c257169d68ea8a63c89765a04a39b5d58b9bf6bf35ccaa1e94b77e03556f175`;
- overlay 154 SHA-256
  `bec4bed715e1d8282c71e077075b0dd2c71627f579a91a62b6cc6aa38b96435b`,
  size `0xE68` (3688 bytes), base `0x023C0400`, reserved size `0x1EA0`,
  and remaining headroom `0x1038` (4152 bytes).

The controlled fixture is derived from the immutable source DSV with SHA-256
`75ddaf8a974d50c70d403e6658bd8497351a5fca0b729a854d6483c39018054d`.
Generated ROMs, saves, screenshots, and result JSON remain build artifacts and
are not committed.
