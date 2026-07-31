# Summary Move Relearn Task 6: unusual ownership paths

Task 6 audits permanent learned/forgotten-move history outside the ordinary
script setter, level-up, evolution, Move Reminder, tutor, and party/PC Summary
paths already covered by tasks 1–5. The named vanilla HeartGold source under
`.codex-reference/pokeheartgold/` is the behavioral authority. All task-6
hooks call task-3 history APIs; there is no second history store.

## Path matrix

| Path | Identity class | Canonical owner / commit | Existing task-3 observation | Task-6 handling |
| --- | --- | --- | --- | --- |
| Script `SetMonMove`, tutors, Move Deleter, battle EXP and evolution selection | Existing mutation | Player `PartyPokemon`; confirmed setter return | Yes | Unchanged; task-3 replace/delete/record hooks remain the sole owner. |
| `GiveMon`, starter, script gifts, Mystery Gift, NPC loan | New identity creation/import | Successful `PokeParty_Add` into the live player party | No first-observation baseline | The sole success tail advances party count, verifies the canonical player party, then seeds its committed slot. Full-party/failure and enemy/temporary parties do not observe. |
| Script-created eggs and Togepi egg | New identity creation | Successful player-party add while still an egg | Deliberately rejected | Eggs remain fail-closed. No parent or pre-slot history is allocated. |
| Hatch completion | Same new identity becoming usable | Hatch task clears `MON_DATA_IS_EGG` on the canonical party owner | Save-time fallback only | Path-specific wrapper performs the retail clear first, then seeds the inherited/current permanent moves as the first baseline. |
| NPC in-game trade | Existing outgoing plus new incoming identity | `NPCTrade_ReceiveMonToSlot` canonical slot copy after the animation | Neither side at this boundary | Capture outgoing snapshot without dirtying; after the infallible slot copy, record it and seed the received identity. Cancel never reaches the call. |
| Local/wireless party trade | Existing outgoing plus new incoming identity | Overlay 65 successful live party-slot replacement after communication/animation | Save-time fallback only | The success commit uses the same resident transaction as NPC trade: snapshot outgoing, perform the retail slot copy, record outgoing, then seed the canonical received owner. Disconnect/cancel never reaches the commit. |
| GTS deposit/export | Existing outgoing identity | Overlay 70 canonical box or party removal after a successful offer/paired exchange | No | Capture the selected canonical owner before removal, execute retail deletion, and record the snapshot only after the box delete or successful party remove. Failure/cancel states never reach these commits. |
| GTS receive with party space | New incoming identity | Successful `Party_AddMon` | Yes | The player-party success tail seeds the committed arrival; full/failure paths do not observe. |
| GTS receive with a full party | New incoming identity | Overlay 70 successful first-empty PC placement | No | Both receive variants resolve the exact empty slot before the retail placement, then seed only its canonical destination after success. Failure/cancel remains history-clean. |
| GTS trade-triggered evolution copy-back | Existing identity species mutation plus pure relocation | Named retail `ov70_022418A4` after the evolution scene | Existing evolution/move hooks; deliberately no copy-back hook | The prior receive seed establishes the PID/OTID record. Any permanent evolution-scene move mutation is recorded against that same identity. Party copy-back and boxed delete/first-empty replacement only relocate the evolved canonical owner and do not count as learning; current species/form drives candidates. Failure before copy-back leaves the save owner unchanged. |
| Ordinary party/PC box transfer | Pure transfer | Existing tasks 3–4 canonical transfer ownership | Yes | Unchanged; identity key and acquisition order survive without treating transfer as learning. |
| Rotom appliance/form rewrite | Existing mutation and form change | `Mon_UpdateRotomForm` on a persistent owner | Direct setters were missed | Reject form indices outside 0–5 before table access; route each replacement/deletion through task-3 APIs. Current-form Summary policy admits only that form's proved special move. |
| DNA Splicer Kyurem rewrite | Existing mutation and form change | Permanent party-menu fuse/separate commit | Direct helper setter was missed | `SwapPartyPokemonMove` receives an explicit permanent-history flag. Splicer and permanent form callers use task-3 replace; battle copies use retail transient writes. |
| Evolution with explicit target form zero | Existing identity species/form change | Evolution scene canonical species/form setters | History identity already stable; form-zero presence was lost | Evolution data carries a separate explicit-form marker, so form zero is written rather than inheriting an old form. Candidate rebuilding always uses the resulting canonical form. |
| Wormadam Sandy/Trash lineage | Existing species/form candidate semantics | Read-only candidate build | Parent generator omitted derived cloak species | Both derived cloak species resolve to Burmy for legal historical move filtering. |
| Daycare deposit | Pure transfer of existing identity | Retail daycare copy/remove function | No boundary observation | Call the retail commit, then seed the canonical deposited `DaycareMon`. Party cancellation before the commit is history-clean. |
| Daycare level-up with empty slot | Existing mutation | `MonTryLearnMoveOnLevelUp` append | Yes | Existing task-3 successful append hook remains authoritative. |
| Daycare level-up with full set | Existing replacement | The one daycare call to `DeleteMonFirstMoveAndAppend` | No | Resident wrapper observes the owner, executes the infallible retail shift, and records the appended move once. Egg-construction calls to the same retail helper are untouched. |
| Scripted daycare sanitizer / Mirror Herb inheritance | Existing mutation of either owner | Successful canonical move+PP write to the selected party `PartyPokemon` or deposited `DaycareMon` | Direct setters were missed | Each owner filters its own legal egg-move buffer/current set, then records through the resident task-3 transaction. Both callers compute max PP from the incoming move with zero PP Ups before mutation. The resident helper atomically writes the move, resets PP Ups, writes PP, then records. Party and deposited histories never share donor or scratch-buffer state. |
| Daycare withdrawal | Pure transfer | Successful `PokeParty_Add` | No explicit withdrawal hook | The canonical party-add success hook seeds the same PID/OTID record after withdrawal; it does not allocate a second identity. |
| Egg generation/inheritance | New identity construction | Temporary egg construction, then party add as egg | Intentionally none | Construction buffers and parent moves never observe. The accepted inherited/current set becomes baseline only at hatch completion. |
| Pokéwalker export | Pure transfer | Canonical PC lookup immediately before serialization/delete | No | Export-only get-and-seed wrapper observes the PC owner; the transit buffer is not recorded. |
| Pokéwalker successful return/catch placements | Existing transfer or new import | Three successful `PCStorage_PlaceMonInBoxByIndexPair` calls | No | Place first, resolve the canonical destination, then seed. Existing PID/OTID resumes one record; a new arrival receives one baseline. |
| Pokéwalker recovery/cancel | Failed transfer recovery | Separate placement at `0x021EC182` | None | Deliberately unpatched. No history revision/dirty change is permitted. |
| Castform/Cherrim battle forms, battle Kyurem/Zacian/Zamazenta, `NEEDS_REVERSION` extended forms | Temporary/battle-only | Battle copies, not save owners | Not applicable | Rejected by the canonical permanent-owner gate or explicitly routed through transient setters. They never enter permanent history or Summary relearn. |

## Integrity and ownership rules

- `IsCanonicalPermanentBoxPokemon` is shared by capture, candidate building,
  and Summary entry. It rejects null, empty, egg, Bad Egg, checksum-failed,
  out-of-range species/form, transient classic forms, unregistered extended
  forms, and extended forms marked `NEEDS_REVERSION`.
- Every successful mutation continues to use encrypted `GetBoxMonData` /
  `SetBoxMonData` accessors or a retail canonical copy routine; task 6 never
  edits encrypted substructures directly.
- History is keyed only by personality and OT ID. Transfer and species/form
  changes retain the record and deterministic acquisition order. New identity
  baselines are created only from the committed canonical owner.
- History dirty/revision changes follow task-3 APIs. Preview, animation,
  communication failure, full-party failure, egg construction, and temporary
  transit buffers do not allocate or dirty records.
- Save ownership is unchanged: the primary save/box/daycare/Pokéwalker code
  marks its ordinary owner dirty and task-3 prepare/finish/cancel publishes the
  sidecar transaction. Task 6 adds no independent save or commit path.
- Summary special-move admission is fail-closed and species/form scoped to
  proved Rotom and Kyurem rewrites. Persisted presence alone is never legality.

## Runtime evidence boundaries

- Actual retail/script evidence uses the Route 34 daycare lady's script 9501.
  The authenticated fixture walks through the real door, proves the script
  callback at map 331 `(3,7)`, and exercises both chooser cancel and slot-2
  STORE/confirm. The success path proves reciprocal party/deposited-owner move
  rewrites, nonzero max PP with zero PP Ups, exactly one append per PID/OTID,
  unrelated records and all 900 PC slots unchanged, and retail save/reload.
- Trade, Rotom form, egg/hatch, and Pokéwalker evidence uses real encrypted
  `0x88` BoxPokemon records, both authenticated PC save generations, and both
  sealed task-3 history mirrors. Trade cancel is byte-exact; form 32 rejects
  before mutation; eggs remain history-free until the egg bit is canonically
  cleared; and Pokéwalker recovery restores the complete save byte-for-byte.
  The Pokéwalker radio leg alone is labelled a source-exact serialization
  surrogate because no headless peripheral peer is available. It verifies
  exact export/import records, PC CRC ownership, round-trip identity/history,
  new-arrival baseline, reparse persistence, and all 900 boxed checksums.
- Candidate ordering and known-move exclusion remain proven by the task-2
  builder/source-static gate; the serialization surrogate does not model or
  claim execution of that builder.

Task 7's all-compatible testing mode is deliberately excluded.
