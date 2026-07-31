# Summary move relearn — task 4 inline party flow

Task 4 adds an in-Summary candidate browser and confirmed move replacement for
the currently displayed party Pokémon. It does not add boxed Pokémon/switching
coverage, audit broad unusual acquisition paths, or enable the optional
all-compatible policy.

## Player controls

On the normal Summary **Moves** page, the bottom prompt reads `X: Relearn`.

- `X`: enter relearn mode.
- Candidate list: `Up/Down` scroll one candidate at a time, `A` chooses the
  highlighted candidate, and `B` returns to the ordinary Moves page.
- Replacement slots: `Up/Down` chooses one of the four known moves, `A`
  proceeds, and `B` returns to the candidate list.
- Confirmation: `A` performs the permanent replacement and `B` returns to
  slot selection without changing anything.
- HM-protected slots show the retail Summary HM-forget message and remain in a
  valid slot-selection flow. `A` or `B` dismisses the message.
- Success: `A` or `B` returns to the ordinary Moves page.

Touch controls and every existing Summary control remain retail while relearn
mode is inactive. The `X: Relearn` prompt is tappable; candidate and slot rows
are tappable. All rendered prompt/control labels occupy y=136..151: entry is
x=8..87, list/slot `A:Pick` is x=8..55, list/slot `B:Back` is x=56..128,
confirmation `A:OK` is x=8..37, and confirmation `B:Back` is x=38..128.
The retail blue `Cancel` button at y=165..188, x=190..249 is also Back.
The unrelated page buttons in that lower row are not modal actions. These
regions are separate: tapping Pick/OK never aliases Back, and tapping Back
never confirms.
The new modal states deliberately consume navigation input so party switching,
page changes, existing move swapping, ribbons, and stat/EV/IV modes cannot
collide with an unfinished replacement.

## State and presentation

The state sequence is:

```text
inactive -> list / empty -> slot -> confirm -> success
                ^            |       |
                |------------B       B
                             |
                        HM blocked
```

The list contains at most 65 task-2 candidates and displays four rows at once.
The selected row uses Summary's existing move-name, PP, type, category, power,
accuracy, and description rendering. Scrolling preserves the task-2
deterministic acquisition order. Slot selection restores the Pokémon's four
actual move rows, then previews the pending move directly in the highlighted
slot with full base PP. This shows the resulting four-move set and drives
Summary's normal type/category/power/accuracy/description pane without changing
the Pokémon. The prompt strip continues to show explicit `A:Pick B:Back`
controls while the player compares slots; confirmation changes those controls
to `A:OK B:Back`.

The candidate builder remains the single source of truth. Its history lookup
is now explicitly read-only: first-time browsing does not allocate a sidecar
record, change access order, increment a revision, or dirty history. Current
moves, invalid moves, unimplemented moves, and duplicates remain excluded by
task 2.

## Cancellation and success ownership

Candidate-list cancellation, empty-list dismissal, slot cancellation,
confirmation cancellation, HM rejection, and a Pokémon identity/position
boundary do not call a Pokémon setter, history recorder, or save writer.
UI-only cache changes are restored before
returning to the ordinary Moves page. The exit path uses retail's cursor-only
position helper and six-window move-detail cleanup before restoring BG5, so a
scrolled candidate cursor and stale detail text cannot leak into vanilla
Summary. Application teardown frees the enlarged Summary work block; because
no permanent mutation occurs before confirmation, destroying an active modal
state and reloading the unchanged battery has no persisted effect.

Only confirmation calls `PokemonMoveHistory_ReplaceMove`. That central task-3
transaction:

1. records the four old moves before mutation;
2. writes the selected slot through `SetBoxMonData`;
3. clears PP Ups and gives the new move its full unboosted PP;
4. verifies the move by canonical readback; and
5. appends the new move after success without duplicate/no-op pollution.

The task-4 UI re-resolves the party Pokémon with `Party_GetMonByIndex`, rejects
known/same moves and HM-protected old slots again at commit time, and sets
Summary arguments offset `+0x38` only after the transaction returns `TRUE`.
That is the existing Summary/parent ownership signal; no UI callback writes a
save directly.

## Residency and lifecycle

Retail Summary code and state dispatch are ARM9-resident. Its application
template at `0x02103A1C` now owns dynamic overlay 154 for the complete Summary
lifetime. Overlay 154 occupies `0x023C0400..0x023C22A0`, ending exactly before
stock overlay 133. A fixed `SRM4`/version-4 header and odd Thumb entry live at
the overlay base. The task-4 image uses `0xB48` bytes through `0x023C0F48`,
leaving `0x1358` bytes inside that reserved envelope for later Summary work.

The state-2 call at `0x02088494` directly targets overlay 154's fixed `+0x08`
entry. This is safe under the application-manager ownership invariant:
every named vanilla Summary launch site uses `FieldSystem_LaunchApplication`,
the manager loads the template overlay before Summary init/main, retains it
through Summary exit, and permits only one child application at a time.
Overlay ID 154 is classified as a cold application overlay, so loading it
first tears down the transient field 149–152 group (including untracked 152).
The direct call consumes no resident overlay-129 bytes; its packaged size
remains `0x7FC0`, preserving the task-3 `0x40` headroom. Existing
`Summary_IVEV` and Summary entry hooks are unchanged and remain reachable
through the retail handler.

Task state lives in a zeroed `0xC0` extension of Summary's retail `0x7D8` work
allocation rather than overlay BSS. This makes exit/teardown cancellation
automatic even though the application manager uses no-init asynchronous
overlay loading. Overlay 153 remains boot-resident and is called only through
its fixed odd Thumb ABI; task 4 never tries to load nonresident overlay 153.
The observational query is resident because task-2 callers can exist without
Summary/overlay 154. To avoid consuming task-3's safety margin, the duplicate
52-entry tutor move table was removed from overlay 153 and appended to the
authenticated tutor archive after its unchanged bitfield prefix. Overlay 153
is `0xFAC`, preserving `0x54` bytes of headroom (eight more than task 3).
Overlay 154 avoids division/jump-table runtime helpers, and binary verification
rejects unsafe ARM-state veneers into Thumb helpers.

## Verification and later-task exclusions

`scripts/verify_summary_move_relearn.py` authenticates the entry gesture,
read-only builder call, state/cancel graph, 65-entry bounds and four-row scroll
window, same/no-op and HM guards, confirmation-only mutation, dirty timing,
canonical party accessor, fixed overlay ABI, Thumb relocations, Summary hook
coexistence, packaged y9 metadata, and overlay 129/153/154 size guards.
`scripts/verify_summary_move_relearn_runtime.py` derives a temporary,
CRC-authenticated two-mirror fixture from the immutable DSV while leaving that
source byte-exact. The controlled baseline has clean history, eight candidates,
and a target slot with 1 PP and two PP Ups. Key and coordinate-touch input prove
entry, row/strip selection, Back/OK separation, immediate state transitions,
four-row viewport scrolling, full candidate PP in live state and pixels,
empty-list handling, HM rejection, pointer-identity and position boundaries,
and active-overlay teardown. The confirmed replacement alone dirties Summary
and history, resets the slot to full base PP with zero PP Ups, then persists
through a normal save and fresh-process reload. The reload authenticates the
selected history mirror and target record, all unrelated history records,
all six serialized `0xEC` party checksums, every unrelated party record, and
the shiny Pidgey.

Reserved for later tasks:

- task 5: boxed Pokémon and actual cross-Pokémon switching coverage (task 4
  only cancels safely when an owner identity/position boundary is observed);
- task 6: broad gift/trade/form/daycare/Pokéwalker and unusual scripted-source
  audits;
- task 7: optional all-compatible testing policy.
