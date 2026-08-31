# Overworld Wild Diagonal Canopy Jump Attempts

> **Status: historical attempt collection.** Use it as evidence, not current
> design. Start at [`overworld-system/README.md`](overworld-system/README.md).

Created: 2026-06-10 04:19 CEST

This file records the diagonal 3-8 canopy jump work for Mankey and the research done after the
first runtime tests failed.

Use this before trying another diagonal canopy jump fix. The old movement log was split into topic
files; this file is the focused diagonal supplement.

## Source Files To Read First

- `documentation/overworld_wild_movement_index.md`
- `documentation/overworld_wild_canopy_long_hop_attempts.md`
- `documentation/overworld_wild_behavior_canopy_hopper_mankey.md`
- `documentation/overworld_wild_mankey_canopy_rendering_attempts.md`
- `documentation/overworld_wild_movement_architecture.md`
- `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`
- `include/map_events_internal.h`
- `armips/include/scriptmacros.s`
- `rom.ld`

## Research Method

The user requested deep research using agents. Four helper agents were used:

- Historical attempt sweep: prior canopy/Mankey movement/rendering attempts.
- Current code trace: diagonal target selection, staging, command start, frame update, landing commit.
- Engine primitive review: stock movement macros and `MapObject_StartJumpMovementInternal`.
- Novelty review: which future approaches appear already tried versus genuinely new.

The agents agreed on the central constraint:

- There is no exposed stock diagonal overworld jump primitive.
- The stock movement command family is cardinal: `JumpUp/Down/Left/Right`, `Jump*2`, `Jump*Site`, and horizontal-only wait-jump variants.
- `MapObject_StartJumpMovementInternal` takes one `direction`, not an `(x, y)` vector, and the active caller passes only one cardinal direction.
- Any diagonal Mankey canopy jump built on the current carrier is therefore a hybrid: a safe cardinal engine jump plus extra project-layer state.

## Current Diagonal Implementation State

As of this log, diagonal code exists in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.

Key switches:

- `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_OFFSET`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_RESTORE_FINALIZE`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_SETTLE`
- `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_VISIBLE_LEGS`

Key code paths:

- `sCanopyLongJumpOffsets`: adds diagonal rays to target/path scanning.
- `OverworldWildSpawns_IsCanopyLongJumpVectorShape`: accepts cardinal vectors and exact 45-degree diagonals.
- `OverworldWildSpawns_TryGetCanopyLongJumpVector`: accepts a diagonal target but returns only the first cardinal direction from `DiagnosticBuildDirections`.
- `OverworldWildSpawns_StartPreparedCanopyLongJumpCommand`: starts the working partner-prepped internal long jump using that one cardinal direction.
- `OverworldWildSpawns_StartCanopyLongJumpDiagonal`: stores diagonal side-channel target state.
- `OverworldWildSpawns_UpdateCanopyLongJumpDiagonalLanding`: updates diagonal side-channel state during frame movement and commits final target when the cardinal command finishes.
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`: writes the secondary axis of `posVec` when the diagonal render offset switch is enabled.
- `OverworldWildSpawns_CommitCanopyLongJumpDiagonalLanding`: commits diagonal target with `SetObjectLogicalTileOnly` plus final X/Z render settling.
- `OverworldWildSpawns_FinalizeCanopyLongJumpDiagonalAfterRestore`: re-applies the diagonal landing after the partner freeze/restore boundary, then clears diagonal side-channel state.

Important: the engine-owned jump itself remains cardinal.

## Attempts From This Diagonal Session

### Diagonal Attempt D1: Enable 3-8 Diagonal Targets And Render Secondary Axis

Idea:

Allow 3-8 canopy long jumps to target exact diagonal tiles. Keep the known working partner-prepped internal long-jump carrier, use its primary cardinal axis, and interpolate the missing diagonal axis through side-channel `posVec` updates.

Implementation shape:

- Added diagonal offsets to canopy long-jump search.
- Replaced same-axis validation with cardinal-or-45-degree validation.
- Updated Mankey direct/path search to consider diagonal vectors.
- Staged diagonal targets through `StageCanopyHopTarget`.
- Added static per-slot diagonal state.
- Wrapped movement update with a slot-aware updater.
- During in-flight frames, wrote the non-primary axis of `object->posVec`.
- On command finish, snapped the object to the diagonal target.

Build:

- The code passed `git diff --check`.
- No build was run before the first runtime report because the build keyword gate had not been opened.

Runtime result:

- User reported: when performing a diagonal jump, Mankey becomes invisible.

Learning:

- The broad side-channel render interpolation was not safe.
- This resembles prior failed raw `posVec` travel attempts, especially Attempts 162, 166, and 176.
- Do not repeat full or broad real-object X/Z render travel without new evidence.

Status:

- Rejected in this form.

### Diagonal Attempt D2: Remove In-Flight Render Offset, Commit Diagonal Landing Only

Idea:

Avoid invisibility by removing per-frame raw diagonal render correction. Let the stock partner-prepped cardinal jump remain visible, then commit the diagonal target at the end with a lighter logical-tile commit instead of a full `SetObjectTile`.

Implementation shape:

- Removed diagonal frame/elapsed render state.
- Removed per-frame secondary-axis interpolation.
- Made `SetObjectLogicalTileOnly` available outside the old disabled probe block.
- On command finish, committed diagonal target with logical tile fields plus one-axis render settle.
- Added the revert switch `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP`.

Build:

- Built with `./docker-makerom.cmd`.
- ROM copied to Delta as `test517.nds`.

Runtime result:

- User reported it no longer visually felt like a diagonal jump.
- User reported Mankey did not land where it looked like it landed.

Learning:

- This solved the most obvious invisibility risk by not moving the secondary axis during flight, but it made the behavior dishonest: the visual path was cardinal while the logical target was diagonal.
- The stock carrier cannot visually communicate diagonal motion by itself because it only receives one cardinal direction.

Status:

- Rejected for game feel/visual-target mismatch.

### Diagonal Attempt D3: Reintroduce Secondary-Axis Render Offset With Lightweight Landing

Idea:

Keep D2's safer lightweight landing commit, but reintroduce a narrower secondary-axis interpolation only during the stock cardinal jump. The intent was to make the visual path and final committed diagonal target agree without restoring the full harmful snap.

Implementation shape:

- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_OFFSET`.
- Restored diagonal frame/elapsed side-channel state.
- Recorded the stock jump frame count when starting diagonal state.
- During airborne update, wrote only the non-primary axis of `posVec`.
- On command finish, used `SetObjectLogicalTileOnly` and final secondary-axis correction.

Build:

- Built with `./docker-makerom.cmd`.
- ROM copied to Delta as `test518.nds`.

Runtime result:

- User reported it did not work.

Learning:

- A narrow secondary-axis `posVec` overlay is still not enough.
- This is not a known stock diagonal jump. It remains a cardinal engine movement with a render-side correction.
- The result should be treated as failed unless a future headless/video diagnostic proves a more precise cause.

Status:

- Rejected in current form.

### Diagonal Attempt D4: Post-Restore Final Diagonal Settle

Idea:

D3 may have landed logically before the partner freeze/restore boundary, then had its final render
position disturbed or left partially cardinal afterward. Keep the in-flight secondary-axis correction,
but make the final diagonal landing survive the post-jump boundary by applying a narrow final settle
after partner restore and canopy visual cleanup.

Implementation shape:

- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_RESTORE_FINALIZE`.
- Added `OverworldWildSpawns_SetObjectRenderTileOnly`, which writes only `posVec[0]` and `posVec[2]`.
- Changed `OverworldWildSpawns_CommitCanopyLongJumpDiagonalLanding` to set the logical tile and both final render axes.
- When the command finishes, keep the diagonal side-channel state alive until
  `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand` runs the partner freeze/restore and
  `ClearCanopyHopperVisualStateAtBoundary`.
- After that boundary, re-apply the final diagonal logical/render settle and clear the diagonal state.

Build:

- Pending at time of writing.

Runtime result:

- Pending user test.

Learning:

- This is still a hybrid cardinal-engine diagonal helper, not a true engine-native diagonal jump.
- It does not repeat the full final `OverworldWildSpawns_SetObjectTile` snap from Attempt 255.
- It still uses the D3 in-flight secondary-axis `posVec` correction, so if D3 failed because any
  in-flight real-object X/Z correction is unsafe, this will still fail.
- It specifically tests whether the visible/logical landing mismatch came from finalization order.

Status:

- Active attempt.

Runtime result:

- User reported Mankey becomes invisible.

Learning:

- Post-restore final settling did not rescue the D3-style real-object render correction.
- The failure now strongly points at the family of real-object X/Z render mutation used by D1/D3/D4.

Status:

- Rejected.

### Diagonal Attempt D5: Disable Real-Object Diagonal Render Mutation

Idea:

Stop making Mankey invisible first. Keep diagonal target acceptance and the proven partner-prepped
engine carrier, but disable every real-object X/Z render mutation added for diagonal presentation:
no in-flight secondary-axis interpolation, no post-restore diagonal finalization, and no final render
tile settle.

Implementation shape:

- Kept `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP` enabled.
- Set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_OFFSET` to `0`.
- Set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_RESTORE_FINALIZE` to `0`.
- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_SETTLE` and set it to `0`.
- `OverworldWildSpawns_CommitCanopyLongJumpDiagonalLanding` now only commits the diagonal logical
  target unless render settle is explicitly enabled.

Build:

- Built with `./docker-makerom.cmd`.
- ROM copied to Delta as `test521.nds`.

Runtime result:

- User reported the logical Mankey position and visible Mankey position still did not match after a
  diagonal jump.

Learning:

- This intentionally does not solve diagonal presentation by itself; it tests whether the diagonal
  target can remain functional without invisibility once all real-object render-axis writes are off.
- With the render mutation disabled, committing the diagonal logical target at command finish creates
  a hidden logical teleport while the visible sprite only completes the cardinal engine jump.

Status:

- Rejected.

### Diagonal Attempt D6: Visible Two-Leg Diagonal Fallback

Idea:

When render correction is disabled, do not pretend one cardinal engine jump landed diagonally. Let
the first leg finish exactly where it visibly lands, keep the original diagonal canopy target pending,
and allow the existing canopy hopper executor to start the remaining cardinal leg after the normal
settle window.

Implementation shape:

- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_VISIBLE_LEGS`.
- When a diagonal side-channel jump finishes and both render offset and render settle are disabled,
  clear only the diagonal side-channel state.
- Do not call `OverworldWildSpawns_CommitCanopyLongJumpDiagonalLanding` in that mode.
- `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand` therefore sees `finalLanding == FALSE`
  and keeps the original canopy target pending.
- The next `TryStartNextCanopyHopMovementCommand` pass should move the remaining cardinal axis with
  the same proven partner-prepped internal long-jump carrier.

Build:

- Built with `./docker-makerom.cmd`.
- ROM copied to Delta as `test522.nds`.

Runtime result:

- User reported Mankey disappears after the diagonal jump.

Learning:

- This is not a true one-arc diagonal jump. It is a visibility-safe fallback meant to keep logical
  and visual positions matched while avoiding the real-object X/Z render mutation that made Mankey
  invisible.
- The intermediate visible cardinal leg can still put Mankey on a tile that is not visually safe.
- Decomposing diagonal targets into cardinal legs is not safe for canopy hopping unless every
  intermediate leg is proven to land on a valid visible canopy tile.

Status:

- Rejected.

### Diagonal Attempt D7: Logical-Only Visible-Leg Midpoint

Idea:

D6 made the diagonal target decompose into visible cardinal legs, but the first leg still entered the
generic non-final canopy midpoint handler, which performs a full `SetObjectTile`. That repeats the
historical heavy midpoint reset family that can make Mankey vanish. Replace that heavy midpoint reset
only for the D6 visible-leg path with a logical-only midpoint commit.

Implementation shape:

- Added `sOverworldWildCanopyLongJumpDiagonalVisibleLegFinished`.
- When a diagonal visible leg command finishes, clear the diagonal side-channel and mark that one
  visible leg just finished.
- In `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`, if `finalLanding` is false and
  that marker is set, call `OverworldWildSpawns_SetObjectLogicalTileOnly(object, landingX, landingY)`
  instead of full `OverworldWildSpawns_SetObjectTile(object, landingX, landingY)`.
- Clear the marker immediately after the finish handler consumes it.

Build:

- Built with `./docker-makerom.cmd`.
- ROM copied to Delta as `test524.nds`.

Runtime result:

- User reported it was still not working.

Learning:

- This is still a segmented visible fallback, not a true diagonal arc.
- It avoids the D6 disappearance candidate without reintroducing real-object diagonal X/Z render
  travel.
- Because diagonal target acceptance was later found disabled in source during follow-up inspection,
  D7 was not a reliable final signal for diagonal runtime behavior.

Status:

- Rejected.

### Diagonal Attempt D8: Correct Tile-To-Render Scale And RAM-Verified Diagonal Render

Idea:

The headless RAM probe showed that engine `posVec[0]` / `posVec[2]` tile-aligned coordinates are
tile coordinate times `16 * OW_WILD_SPAWNER_FX32_ONE`, not tile coordinate times only
`OW_WILD_SPAWNER_FX32_ONE`. Earlier render-settle and in-flight diagonal attempts wrote final and
interpolated render positions at the wrong scale, which explains the invisibility and
visual/logical mismatch reports.

Implementation shape:

- Re-enabled `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP`.
- Added `OW_WILD_SPAWNER_TILE_FX32` as `OW_WILD_SPAWNER_FX32_ONE * 16`.
- Updated `OverworldWildSpawns_SetObjectTile`, `OverworldWildSpawns_SetObjectRenderTileOnly`, and
  diagonal render interpolation to use `OW_WILD_SPAWNER_TILE_FX32`.
- Re-enabled in-flight diagonal secondary-axis render offset, final render settle, and post-restore
  finalization using the corrected scale.
- Added RAM-readable volatile diagnostics for diagonal start/target/current/render/flags state.
- Extended `scripts/headless-overworld-test.py` with `combo:KEY+KEY:frames[:release]`.
- Added `scripts/verify-diagonal-canopy-ram.py`, which discovers diagnostic symbol addresses with
  `arm-none-eabi-nm`, runs the headless overworld save, presses `SELECT+R+RIGHT`, reads RAM, and
  asserts:
  - target is a 3-8 diagonal
  - final logical tile equals target
  - final render tile equals target
  - `BIT_VANISH` is clear

Build:

- Built with `./docker-makerom.cmd`.
- ROM copied to Delta as `test528.nds`.

Verification:

- Ran `scripts/verify-diagonal-canopy-ram.py`.
- Result:

```text
diagonal canopy RAM: start=(589,406) target=(582,413) current=(582,413) render=(582,413) flags=0x00124119 stage=15 triggers=1 starts=0 failures=1
PASS: diagonal jump lands logically and visually with Mankey visible
```

- Screenshot: `documentation/verification_screenshots/diagonal_canopy_ram_test_02_after_wait.png`
  showed Mankey visible after the jump.

Learning:

- D1/D3/D4 were not invalid merely because they touched `posVec`; they wrote tile render coordinates
  at the wrong scale.
- A corrected-scale real-object render offset is materially different from the previous failed raw
  render attempts.
- RAM reads are now the required first verification before relying on Delta visual testing.

Status:

- Superseded by D9 after Delta showed a mid-jump blink on long diagonals whose secondary-axis
  displacement was greater than 3 tiles.

### Diagonal Attempt D9: Cap In-Flight Secondary-Axis Render Correction

Idea:

The D8 RAM verifier proved that final logical and render tiles can match, but Delta testing showed
that Mankey starts blinking toward the target during long diagonal jumps when the non-primary axis
is corrected by more than 3 tiles during the jump. Keep the corrected-scale final commit from D8,
but cap only the in-flight secondary-axis render offset to 3 tiles.

This is materially different from earlier raw `posVec` travel attempts because it does not ask the
real object to render-travel the full diagonal. It only allows the secondary axis to visually drift
within the observed safe window while the stock primary-axis jump command runs, then the existing D8
landing commit/settle writes the full target tile after the movement command finishes.

Implementation shape:

- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_MAX_SECONDARY_TILES`.
- Added `OverworldWildSpawns_ClampCanopyLongJumpDiagonalSecondaryFx32`.
- `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset` now clamps the live secondary-axis
  target to at most 3 tiles from the start tile before interpolating.
- Final logical tile, final render tile, post-restore finalization, and the RAM probe are unchanged.

Expected verification:

- `scripts/verify-diagonal-canopy-ram.py` should still pass because it checks the end state after
  final commit, not the capped mid-flight render offset.
- Delta manual verification should focus on whether the mid-jump blink disappears on >3-tile
  secondary-axis diagonals.

Build:

- Built successfully with `./docker-makerom.cmd`.
- Copied ROM to Delta as:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test536.nds`.

Verification:

- `python3 -m py_compile scripts/headless-overworld-test.py scripts/verify-diagonal-canopy-ram.py`
  passed.
- `scripts/verify-diagonal-canopy-ram.py` passed with a forced 4-tile diagonal Mankey jump:

```text
diagonal canopy RAM: start=(582,403) target=(586,407) current=(586,407) render=(586,407) flags=0x0012C019 stage=15 triggers=2 starts=1 failures=1 slots(active/current/mankey/object)=1/1/1/1 last_species=56
PASS: diagonal jump lands logically and visually with Mankey visible
```

- Screenshot:
  `documentation/verification_screenshots/diagonal_canopy_ram_test_02_after_wait.png`.
- The verifier intentionally reads immediately after the forced diagnostic chord release. Longer
  post-trigger waits can let normal overworld AI start a later hop and overwrite the diagnostic
  RAM state, which hides the forced diagonal result.

Status:

- Active attempt built and RAM-verified.
- Delta manual verification is still required for the subjective mid-jump blink, because the RAM
  verifier confirms the final forced landing and visibility but does not sample every visual frame
  during the jump.
- If this still blinks, the next distinct approach should be a mid-flight visual carrier or
  frame-sampled video/RAM probe. Do not repeat earlier full-distance real-object `posVec` travel.

### Diagonal Attempt D10: Post-Landing Render Settle

Idea:

D9 prevented the worst mid-jump blink by capping the live secondary-axis render correction to
3 tiles, but that also left a visible gap at command finish. The old finalization path wrote the
full render tile immediately, so long diagonals could snap into place after the jump. Keep D9's
in-flight cap, commit the true logical landing when the stock movement command finishes, then settle
the remaining render gap over a short post-landing interpolation before the canopy hop is marked
finished.

Implementation shape:

- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE`.
- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE_FRAMES`.
- Added per-slot post-landing settle state for the render start point and elapsed frames.
- `OverworldWildSpawns_CommitCanopyLongJumpDiagonalLanding` now commits logical tile only.
- `OverworldWildSpawns_FinalizeCanopyLongJumpDiagonalAfterRestore` starts the post-landing render
  settle when the render position is still short of the true target.
- `OverworldWildSpawns_TickCanopyLongJumpDiagonalRenderSettle` owns the remaining render
  interpolation and only finishes the canopy hop once render and logical tiles match.

Why this is distinct from earlier failed render travel:

- D1/D3 and the older raw `posVec` attempts tried to make the real object travel the full diagonal
  during the jump.
- D10 does not remove the D9 in-flight cap and does not ask the stock carrier to render-travel more
  than the observed safe 3-tile secondary-axis window while airborne.
- The only extra render movement is a bounded 12-frame post-landing settle after the logical target
  is already correct.

Build:

- Built successfully with `./docker-makerom.cmd`.
- Copied ROM to Delta as:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test537.nds`.

Verification:

- `python3 -m py_compile scripts/headless-overworld-test.py scripts/verify-diagonal-canopy-ram.py`
  passed.
- `git diff --check` passed.
- `scripts/verify-diagonal-canopy-ram.py` passed with a forced 4-tile diagonal Mankey jump:

```text
diagonal canopy RAM: start=(583,405) target=(587,409) current=(587,409) render=(587,409) flags=0x00104011 stage=15 triggers=1 starts=1 failures=0 slots(active/current/mankey/object)=1/1/1/1 last_species=56
PASS: diagonal jump lands logically and visually with Mankey visible
```

- Screenshot:
  `documentation/verification_screenshots/diagonal_canopy_ram_test_02_after_wait.png`.

Status:

- Active attempt built and RAM-verified.
- Delta manual verification is still required for the subjective snap check, because the RAM
  verifier confirms the final settled state but does not judge whether the 12-frame settle feels
  natural.

### Diagonal Attempt D11: Full In-Flight Arc With Secondary Logical Sync

Idea:

D10 removed the snap but made the last part of the jump read as a post-landing drag. The desired
behavior is for the whole diagonal displacement to happen during the jump arc. Return the
secondary-axis render interpolation to the full 3-8 tile distance, disable the post-landing settle,
and keep the object's logical secondary tile close to the rendered secondary tile during the stock
cardinal jump. The hypothesis is that the prior long-diagonal blink came from the rendered position
moving several tiles away from the map object's logical anchor.

Implementation shape:

- Set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_MAX_SECONDARY_TILES` to `8`.
- Added `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_SYNC_LOGICAL_SECONDARY`.
- Disabled `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE`.
- Added `OverworldWildSpawns_SyncCanopyLongJumpDiagonalSecondaryLogicalTile`.
- During in-flight diagonal render offset, update only the non-primary logical axis to the rounded
  rendered tile. The stock movement command still owns the primary cardinal axis.
- On the finishing movement frame, apply the diagonal render offset at the full frame count before
  finalization, so the endpoint belongs to the jump path rather than a later settle.

Why this is distinct from earlier failed render travel:

- D1/D3 and Attempts 162/166/176 moved render position without keeping the map object's logical
  anchor close to the rendered position during the jump.
- D11 still uses the corrected `OW_WILD_SPAWNER_TILE_FX32` scale from D8.
- D11 does not use a helper/proxy object, chained stock segments, or a post-landing drag.

Build:

- Built successfully with `./docker-makerom.cmd`.
- Copied ROM to Delta as:
  `/Users/christofferandersen/Library/Mobile Documents/com~apple~CloudDocs/Delta/ROMs/test538.nds`.

Verification:

- `python3 -m py_compile scripts/headless-overworld-test.py scripts/verify-diagonal-canopy-ram.py`
  passed.
- `git diff --check` passed.
- `scripts/verify-diagonal-canopy-ram.py` passed with a forced 4-tile diagonal Mankey jump:

```text
diagonal canopy RAM: start=(586,405) target=(590,409) current=(590,409) render=(590,409) flags=0x0012C019 stage=15 triggers=1 starts=1 failures=0 slots(active/current/mankey/object)=1/1/1/1 last_species=56
PASS: diagonal jump lands logically and visually with Mankey visible
```

- Screenshot:
  `documentation/verification_screenshots/diagonal_canopy_ram_test_02_after_wait.png`.

Status:

- Active attempt built and RAM-verified.
- Delta manual verification is required for the actual visual arc. The RAM verifier proves final
  landing/visibility, but it does not judge whether the full in-flight diagonal arc feels right.

## Prior Attempts That Must Not Be Repeated Blindly

### Raw `posVec[0]` / `posVec[2]` Travel

Already tried:

- Attempt 162: Custom Rendered Far Canopy Hop.
- Attempt 166: Real Object Deferred Logical Commit Render-Hop.
- Attempt 176: Use One Manual Render Hop For Full Canopy Distance.

Observed results:

- Teleport/no readable hop.
- Mankey became invisible.
- Large real-object X/Z render offsets are unsafe for canopy hopping.

Relevant docs:

- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempt 162.
- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempt 166.
- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempt 176.

Conclusion:

- Do not retry raw X/Z render travel on the real map object without new renderer evidence.

### Helper Or Proxy Object Travel

Already tried:

- Attempt 163: Canopy Helper Object Far-Hop Visual.
- Attempt 164: Helper Object Stock-Jump Segments.
- Later Mankey tree-top proxy attempts, including visual proxy approaches.

Observed results:

- Helper interpolation still did not create a readable hop.
- Helper stock jumps were unreliable/invisible.
- Tree-top proxy approaches lost to canopy/layer ordering.

Relevant docs:

- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempts 163 and 164.
- `documentation/overworld_wild_mankey_canopy_rendering_attempts.md`, tree-top proxy attempts.

Conclusion:

- Do not retry map-object helper/proxy travel as the main solution without new evidence.

### Chained Stock `Jump*2` Or Movement Lists

Already tried:

- Attempts 184-189: plain `Jump*2`, midpoint normalization, logical-only midpoint commit, partner-wrapped `Jump*2`, one/two wrapper arrangements.
- Attempt 177: vanilla movement-list task runner.

Observed results:

- Plain chained `Jump*2` could cover distance but lost visibility after the first segment.
- Wrapped `Jump*2` improved presentation but still read as multiple two-tile arcs.
- Movement lists improved ownership/route safety but did not solve long visible travel or tree visibility.

Relevant docs:

- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempts 184-189.
- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempt 177.

Conclusion:

- Do not retry chained `Jump*2` or movement-list jump runs as the primary 3-8 hop solution.

### Full `OverworldWildSpawns_SetObjectTile` Landing Snaps

Already tried:

- Midpoint `SetObjectTile` in chained jump probes.
- Attempt 255: Snap Final Canopy Landing After Partner Restore.

Observed results:

- Full tile/vector rewrites can corrupt visibility.
- Attempt 255 made Mankey vanish after every jump.

Relevant docs:

- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempts 184, 185, and 255.

Conclusion:

- Do not use full `SetObjectTile(object, targetX, targetY)` after partner restore as a generic landing correction.

### Logical-Only Midpoint Commits

Already tried:

- Attempt 186: Chained Jump2 With Logical-Only Midpoint Commit.

Observed results:

- Logical fields and render vectors were not separable enough to repair chained stock jump handoff.

Relevant docs:

- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempt 186.

Conclusion:

- Logical-only commit is acceptable as a narrow final bookkeeping tool, but should not be assumed to fix movement/render mismatch by itself.

### Broad Generalization Of The Internal Long-Jump Carrier

Already tried:

- Attempt 191 generalized the successful Attempt 190 carrier.
- Attempt 192 constrained it to the behavior's active 3-8 range.

Observed results:

- Broad raw frame-budget generalization caused bugs and disappearing Mankey.
- Range-gated 3-8 carrier remains the durable base.

Relevant docs:

- `documentation/overworld_wild_canopy_long_hop_attempts.md`, Attempts 190-192.

Conclusion:

- Keep the partner-prepped internal long-jump carrier constrained to proven behavior ranges.

## What Appears Not Yet Fully Tried

The agents found no documented `Attempt N` for a complete diagonal Mankey canopy runtime test before this session.

However, the D1/D3 diagonal approaches are not truly novel in their render mechanism. They reuse a known-dangerous ingredient:

- direct map-object `posVec[0]` / `posVec[2]` offset during canopy travel.

The difference is that D1/D3 only offset one secondary axis while the native engine owns the primary axis. Runtime still failed, so this variant is now logged and should not be repeated unchanged.

Potentially novel directions, if pursued later:

1. Diagnostic-only forced diagonal scenario

   Force one known same-length diagonal target, disable fallback pathing, and log/observe:

   - exact origin and target
   - primary cardinal direction
   - frame count
   - whether `BIT_VANISH` ever becomes set
   - primary and secondary `posVec` every frame
   - final logical tile and final render tile

   Purpose:

   - Establish whether the secondary axis is being overwritten, ignored, occluded, or committed at the wrong time.

   Novelty:

   - The docs contain many runtime attempts but not a focused diagnostic-only diagonal trace.

2. Research the internal jump function contract before another implementation

   Investigate `MapObject_StartJumpMovementInternal` and surrounding stock command wrappers in disassembly:

   - whether it stores target deltas anywhere besides direction
   - whether `faceVec`, `unk88`, or `unk94` encode movement vectors
   - whether a lower-level function accepts a vector or only direction
   - whether a diagonal direction enum exists elsewhere but is not exposed through scripts

   Purpose:

   - Avoid more guesswork around a cardinal-only wrapper.

   Novelty:

   - Existing notes infer cardinal-only from exposed APIs/macros; a focused disassembly/vector-field audit may find a lower-level option.

3. Effect-layer visual carrier, not map-object proxy travel

   The logs say bubble/effect-layer markers can render above canopy while map-object redraw/proxy approaches do not.

   A genuinely new visual family would:

   - keep the real Mankey as the logical actor
   - either keep it visible at origin until handoff or hide only with a proven replacement active
   - render an effect-owned Mankey-like visual on the diagonal arc
   - hand off cleanly at landing

   Purpose:

   - Escape the map-object render ordering and `posVec` snapping family.

   Risk:

   - This is larger work and likely needs sprite/effect payload research before implementation.

   Novelty:

   - Field-effect map-object redraw was tried and failed, but an effect-owned Pokemon visual payload has not been proven attempted in the docs reviewed.

4. Disable diagonal visuals but change target rule

   If a true diagonal visual is not viable, another product decision is to reject diagonal 3-8 targets and keep cardinal-only movement until a real diagonal carrier exists.

   Purpose:

   - Prevent misleading visual/logical mismatch.

   Novelty:

   - This is not a feature solution, but it is the safest revert path.

## Revert Switches

Current source has these switches for quick rollback:

- Disable all diagonal long-jump target acceptance:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP 0
```

- Keep diagonal target acceptance but disable secondary-axis render offset:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_OFFSET 0
```

- Keep D8 diagonal render behavior but remove the D9 in-flight secondary-axis cap:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_MAX_SECONDARY_TILES 8
```

- Disable only the D11 in-flight secondary logical-tile sync:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_SYNC_LOGICAL_SECONDARY 0
```

- Disable only the D10 post-landing render settle:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE 0
```

- Tune the D10 post-landing render settle duration:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE_FRAMES 12
```

- Disable the D4 post-restore final settle while keeping the earlier diagonal path:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_RESTORE_FINALIZE 0
```

- Disable the final render tile settle:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_SETTLE 0
```

- Disable the D6 two-leg fallback:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_VISIBLE_LEGS 0
```

- Disable the RAM/headless diagnostic key probe:

```c
#define OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RAM_PROBE 0
```

If D9 regresses in manual Delta testing, the fastest behavior-preserving rollback is to set
`OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP` to `0`. If only the diagnostic input hook is
undesired, set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RAM_PROBE` to `0`. If only the D9 visual cap
is suspect, set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_MAX_SECONDARY_TILES` to `8`. If only
the D10 post-landing settle feels wrong, set
`OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE` to `0` or tune
`OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_POST_LANDING_RENDER_SETTLE_FRAMES`. If only the D11 logical
sync is suspect, set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_SYNC_LOGICAL_SECONDARY` to `0`.

## Novelty Checklist Before The Next Code Attempt

Before editing code again:

1. Name the proposed mechanism in one sentence.
2. Search these terms in `documentation/`:
   - `posVec`
   - `helper`
   - `proxy`
   - `Jump*2`
   - `movement-list`
   - `SetObjectTile`
   - `logical-only`
   - `partner-prepped`
   - `field effect`
   - `bubble`
   - `diagonal`
3. Verify the mechanism is not one of:
   - raw real-object X/Z render travel
   - helper/proxy map-object travel
   - chained stock jump segments
   - movement-list jump runs
   - full final `SetObjectTile` snap after partner restore
   - broad unconstrained internal jump carrier
4. If the mechanism uses `posVec`, explain why it is materially different from Attempts 162, 166, 176, D1, and D3.
5. If the mechanism uses helper/proxy objects, explain why it is materially different from Attempts 163, 164, 228, and 250.
6. If the mechanism uses stock movement commands, explain why it is materially different from Attempts 184-189 and 177.
7. Define the runtime success/failure observation before building a ROM.
8. Add the result to this file immediately after user testing.

## Attempt D12 - Frame-Sampled Full-Render Diagonal Arc

Date: 2026-06-10

Problem observed after D11:

- Manual Delta still had a slight end correction.
- The old RAM verifier only checked final tile state, so it could miss a small visual snap/drag.

Verification-process changes:

- Added raw fixed-point render RAM probes for X/Y plus elapsed/frame-count.
- Added `sample` and `combo_sample` actions to `scripts/headless-overworld-test.py`.
- Updated `scripts/verify-diagonal-canopy-ram.py` to sample every frame around the jump, report the
  last samples before landing, fail on large final render steps, and check final render/logical
  alignment.

Code changes:

- The diagonal helper now owns both render axes during the jump instead of only the secondary axis.
- The helper uses a 15-frame render window because the stock movement command finishes well before
  the previous distance-scaled helper frame count.
- Final canopy landing reasserts render position from the object's current logical tile after
  generic cleanup, so post-landing state does not rely on stale diagonal side-channel targets.

Result:

- Built successfully and copied to Delta as `test545.nds`.
- `scripts/verify-diagonal-canopy-ram.py` passed.
- Last sampled end step was `0.267` tiles instead of the earlier multi-tile correction.

Rollback:

- Set `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_LONG_JUMP` to `0` to disable the diagonal long-jump
  helper entirely.
- To keep D11 but remove D12's full-arc timing, revert:
  - `OW_WILD_SPAWNER_CANOPY_HOPPER_DIAGONAL_RENDER_FRAMES`
  - the two-axis writes in `OverworldWildSpawns_ApplyCanopyLongJumpDiagonalRenderOffset`
  - the final render-to-current tile in `OverworldWildSpawns_HandleFinishedCanopyHopMovementCommand`

## Current Recommendation

D12 is the current active attempt. Before manual Delta testing, rerun:

```bash
scripts/verify-diagonal-canopy-ram.py
```

Do not retry earlier `posVec` diagonal attempts unless they use `OW_WILD_SPAWNER_TILE_FX32` scale,
keep the logical anchor close to the rendered position, and pass the RAM verifier first. If Delta
still shows a visual problem despite the RAM pass, the next debugging target should be a video/RAM
comparison around the first final marker, not another final-state-only check.
