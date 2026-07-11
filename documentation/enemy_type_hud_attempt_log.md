# Enemy Type HUD Attempt Log

Date: June 13, 2026

Purpose: track every change and verification attempt for showing enemy Pokemon
types during battle. Before trying a new fix, check this file first. If a
candidate is already represented here, do not repeat it unless the new attempt
changes a specific variable and records that difference.

## Change Trial Protocol

1. Search this log for the proposed mechanism, file, or hypothesis before
   editing.
2. Add a new attempt entry with the exact difference from previous attempts.
3. Make the smallest code change that exercises that difference.
4. Build only when needed for verification.
5. Verify with a fresh screenshot or command result.
6. Update the entry with pass/fail evidence before trying another fix.

## Current State

- Branch: `feature/custom-overworld-wild-movement`.
- Startup branch refresh was attempted, but switching to `main` was blocked by
  the existing dirty worktree. Work stayed scoped to the current branch.
- The battle test suite has not been run because the repo keyword gate for
  tests was not opened by a standalone `test` sentence.
- The normal `./docker-makerom.cmd` build is currently blocked by unrelated
  dirty code in `src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c`.
- Targeted ROM packaging succeeds when the unrelated overworld-spawn overlay
  build artifacts are marked old.
- `scripts/headless-overworld-test.py --sav test.sav` is now opt-in and loads
  raw `.sav` files only when explicitly requested.
- The temporary forced-Water debug patch has been removed from
  `src/battle/battle_type_display.c`.

## Implemented Pieces

- Added type icon graphics to `rawdata/weather_icons` for all 18 Pokemon types,
  using existing 32x32 type icon PNGs.
- Added `TYPE_ICON_*_GFX` constants in `include/constants/file.h` for NARC
  indices 369 through 403.
- Added `BattleSystem_UpdateEnemyTypeIcons` declaration in `include/battle.h`.
- Called `BattleSystem_UpdateEnemyTypeIcons(bsys, ctx)` after the player battle
  command dispatch in `src/battle/battle_controller_player.c`.
- Added `src/battle/battle_type_display.c` to map enemy battler types to icon
  OAM sprites.
- Extended `scripts/headless-overworld-test.py` with mutually exclusive
  `--dsv` and `--sav`; default behavior remains `.dsv`.

## Attempts And Evidence

### A01 Initial Main-Screen OAM Type Display

Change:
- Added `src/battle/battle_type_display.c`.
- Used main-screen OAM: `NNS_G2D_VRAM_TYPE_2DMAIN`, `FADE_MAIN_OBJ`.
- Used four slots for enemy single/double battles.
- Loaded char/palette from `ARC_BATTLE_GFX`.
- Loaded cell/cell animation from `ARC_ITEM_GFX_DATA`, matching the Mega icon
  pattern.

Verification:
- Full `./docker-makerom.cmd` succeeded before later unrelated overlay build
  failures appeared.
- ROM was copied to Delta as `test648.nds`.
- Headless `.dsv` route attempts reached overworld/tree prompt paths rather
  than a useful battle.

Result:
- No reliable battle HUD proof from this attempt.

### A02 Raw `test.sav` Loading

Change:
- Added opt-in `--sav PATH` support to `scripts/headless-overworld-test.py`.
- Added result fields: `dsv`, `sav`, and `save_kind`.
- Kept `.dsv` as the default path unless `--sav` is explicitly passed.

Verification:
- `scripts/headless-overworld-test.py --sav test.sav ...` reported
  `"save_kind": "sav"` and loaded New Bark from `test.sav`.

Result:
- Passed. `test.sav` usage is opt-in for verification.

### A03 Mistaken Save-Flag Feature Toggle

Change:
- Briefly changed a free bit in `include/save.h` to gate showing enemy types.

Verification:
- User clarified that "opt in" meant only `test.sav` usage in the verifier,
  not an in-game feature toggle.

Result:
- Reverted. `include/save.h` should not be part of this feature.

### A04 `test.sav` Rival Route Discovery

Change:
- No source-code change.
- Probed routes from `test.sav` to trigger the rival fight.

Verification:
- Reliable route found: boot/load, move right/right/up/right/down/right, wait,
  then tap A through the rival dialog.
- Useful route proof:
  `documentation/verification_screenshots/test_sav_rival_battle_route_07_wait360.png`.

Result:
- Passed. We can consistently reach the rival fight from `test.sav`.

### A05 Right-Only Rival Attempt

Change:
- No source-code change.
- Tried a simpler "go right and mash A" route from `test.sav`.

Verification:
- Reached the rival battle command menu:
  `documentation/verification_screenshots/enemy_type_hud_testsav_right_06_final.png`.

Result:
- Battle was reached, but no type icon was visible.

### A06 Hide Gate Fix

Change:
- Changed the display hide condition from hiding for
  `ctx->server_seq_no >= CONTROLLER_COMMAND_42` to hiding only for
  `ctx->server_seq_no == CONTROLLER_COMMAND_45`.

Why:
- The old condition hid icons at the command menu, exactly where the screenshot
  verification was landing.

Verification:
- Targeted ROM packaging succeeded with the unrelated overworld-spawn overlay
  artifacts marked old.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_testsav_gatefix_final.png`.

Result:
- Failed. Totodile was visible at the command menu, but no Water icon appeared.

### A07 Targeted Build Workaround

Change:
- No game-code change.
- Used `make -o` for:
  `build/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.o`,
  `build/overworld_wild_spawns_overlay_linked.o`, and
  `build/output_overworld_wild_spawns_overlay.bin`.

Why:
- Full normal build was blocked by unrelated compile errors in dirty
  overworld-spawn overlay code.

Verification:
- Dry-run first confirmed the battle overlay would rebuild and the unrelated
  overworld-spawn overlay would not.
- Actual targeted build succeeded and produced `test.nds`.
- Copied to Delta as `test652.nds`.

Result:
- Passed as a verification workaround. Not a replacement for a clean full build.

### A08 Max Battler Accessor

Change:
- Replaced direct `bsys->maxBattlers` visibility check with
  `BattleWorkClientSetMaxGet(bsys)`.

Why:
- Other battle code uses the accessor, and the partial `BattleSystem` struct
  field could be unreliable.

Verification:
- Targeted ROM packaging succeeded.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_testsav_maxget_final.png`.

Result:
- Failed. No Water icon appeared.

### A09 Forced-Water Debug Patch

Change:
- Temporarily bypassed enemy type collection and forced slot 0 to display
  `TYPE_WATER`, then returned early.

Why:
- To distinguish "type lookup is wrong" from "sprite/display path is not
  drawing".

Verification:
- Targeted ROM packaging succeeded.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_debug_forced_water.png`.

Result:
- Failed. Even a forced Water icon did not appear. This strongly suggests the
  current display path, update call timing, resource IDs, cell data, or
  main-screen OAM allocation is not producing a visible sprite.

### A10 Remove Forced-Water Debug Patch

Change:
- Removed the temporary early-return that forced slot 0 to display `TYPE_WATER`.

Why:
- A09 had served its purpose and should not remain in the production patch.

Verification:
- Searched this log and the source for the forced-Water code before editing.
- Removed only the temporary debug block.

Result:
- Passed as cleanup. No gameplay verification was needed because this restores
  the non-debug display logic.

### A11 Forced-Water Probe With No `CONTROLLER_COMMAND_45` Hide Gate

Change:
- Temporarily removed `ctx->server_seq_no == CONTROLLER_COMMAND_45` from
  `EnemyTypeIcon_ShouldHideAll`.
- Temporarily forced slot 0 to display `TYPE_WATER` after the null/resource
  checks, then returned early.

Why this is not a duplicate:
- A09 forced `TYPE_WATER`, but only after `EnemyTypeIcon_ShouldHideAll`.
- If the visible command-menu frame has already advanced to
  `CONTROLLER_COMMAND_45`, A09 would still hide all icons before reaching the
  forced display call.
- This attempt changes that single variable: bypass the `CONTROLLER_COMMAND_45`
  hide gate while forcing Water.

Verification:
- Targeted ROM packaging succeeded.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_debug_no45_forced_water.png`.

Result:
- Failed. No Water icon appeared. This rules out the specific possibility that
  A09 failed only because the visible command-menu frame was hidden by
  `CONTROLLER_COMMAND_45`.

### A12 Remove A11 Probe

Change:
- Restored the `CONTROLLER_COMMAND_45` hide condition.
- Removed the temporary forced-Water early-return.

Why:
- A11 was only a diagnostic probe and failed.

Verification:
- Source was patched back to the non-debug display path.

Result:
- Passed as cleanup. No gameplay verification was needed because this restored
  the pre-A11 logic.

### A13 Forced-Water Probe On Bottom-Screen OAM

Change:
- Temporarily switched the display template/resource loading from
  `NNS_G2D_VRAM_TYPE_2DMAIN` / `FADE_MAIN_OBJ` to
  `NNS_G2D_VRAM_TYPE_2DSUB` / `FADE_SUB_OBJ`.
- Temporarily bypassed the `CONTROLLER_COMMAND_45` hide gate and forced slot 0
  to display `TYPE_WATER`, matching the A11 probe except for draw surface.

Why this is not a duplicate:
- A11 forced Water and bypassed the `CONTROLLER_COMMAND_45` hide gate, but still
  used main-screen OAM.
- This attempt changes the draw surface to the known-working battle icon side:
  `NNS_G2D_VRAM_TYPE_2DSUB` and `FADE_SUB_OBJ`.

Verification:
- Targeted ROM packaging succeeded.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_debug_sub_forced_water.png`.

Result:
- Failed. No Water icon appeared on the bottom screen. This rules out the
  simple explanation that the same OAM/resource path would work if moved from
  main-screen to sub-screen OAM.

### A14 Remove A13 Probe

Change:
- Restored main-screen OAM/fade constants.
- Restored the `CONTROLLER_COMMAND_45` hide gate.
- Removed the temporary forced-Water early-return.

Why:
- A13 was only a diagnostic probe and failed.

Verification:
- Source was patched back to the non-debug display path.

Result:
- Passed as cleanup. No gameplay verification was needed because this restored
  the pre-A13 logic.

### A15 Execution Sentinel Probe

Change:
- Pending.

Why this is not a duplicate:
- A09, A11, and A13 changed icon rendering behavior but did not prove whether
  `BattleSystem_UpdateEnemyTypeIcons` actually ran during the final rival
  command-menu frame.
- This attempt adds temporary memory-readable counters/flags and verifies them
  through `scripts/headless-overworld-test.py --read`.

Verification:
- First targeted parallel ROM packaging attempt failed before verification:
  `armips/data/monoverworlds.s` could not open `base/arm9.bin`.
- Retrying the same code change serially to avoid a packaging race.
- Serial targeted ROM packaging succeeded.
- Debug symbol addresses from `build/battle_linked.o`:
  `gEnemyTypeIconDebugCounter = 0x023D3FD0`,
  `gEnemyTypeIconDebugFlags = 0x023D3FD4`,
  `gEnemyTypeIconDebugLastSeq = 0x023D4660`.
- Headless `--sav test.sav` rival route with `--read` reported:
  counter `1016`, flags `0x20F`, last sequence `5`.
- Additional static reads from the same build reported:
  `sEnemyTypeIconCellLoaded = 1`, slot 0 actor `0x0232AC20`, and slot 0
  type `0x0B` (Water).

Result:
- Passed. `BattleSystem_UpdateEnemyTypeIcons` runs on the final command-menu
  frame, has non-null CATS system/resource pointers, sees max battlers `2`, is
  not hidden, records Water for Totodile, and creates a non-null actor. The
  remaining issue is actor/resource visibility, not type lookup or call timing.

### A16 Remove A15 Sentinel

Change:
- Removed `gEnemyTypeIconDebugCounter`, `gEnemyTypeIconDebugLastSeq`, and
  `gEnemyTypeIconDebugFlags`.
- Removed the temporary writes to those sentinel variables.

Why:
- A15 proved execution and actor creation; the sentinel should not remain in
  feature code.

Verification:
- Source was patched back to the non-debug display path.

Result:
- Passed as cleanup. No gameplay verification was needed because this restored
  the pre-A15 logic.

### A17 Battle GFX NARC Member Check

Change:
- No source-code change.

Why this is not a duplicate:
- Prior attempts assumed `TYPE_ICON_WATER_GFX` member `391` existed but did not
  directly verify the built NARC member.

Verification:
- `build/battlegfx/8_391_type_water_hud-00.NCGR` and
  `build/battlegfx/8_391_type_water_hud-01.NCLR` exist.
- Extracted `build/narc/battlegfx.narc` and confirmed members `391` and `392`
  exist.
- `cmp` confirmed extracted member `391` matches the generated Water NCGR and
  member `392` matches the generated Water NCLR.

Result:
- Passed. The Water icon char/palette assets are present at the expected NARC
  member indices.

### A18 Forced-Water Probe With Weather Cell Resources

Change:
- Temporarily switched to bottom-screen OAM/fade.
- Temporarily bypassed the `CONTROLLER_COMMAND_45` hide gate and forced slot 0
  to display `TYPE_WATER`.
- Temporarily switched the shared cell/animation resources from
  `ARC_ITEM_GFX_DATA` to `ARC_BATTLE_GFX/BATTLE_GFX_NCER` and
  `ARC_POKEICON/3`, with the same animation cap call used by weather icons.

Why this is not a duplicate:
- A13 used bottom-screen OAM with the same item-icon cell resources as the
  original type display and failed.
- This attempt keeps the controlled forced-Water/bottom-screen setup but changes
  the cell/animation resources to the existing weather icon path:
  `ARC_BATTLE_GFX/BATTLE_GFX_NCER` and `ARC_POKEICON/3`, including the weather
  animation setup.

Verification:
- Serial targeted ROM packaging succeeded.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_debug_weather_cell_forced_water.png`.

Result:
- Failed. No Water icon appeared. This rules out the specific theory that the
  item-icon cell/animation resources were the only reason the actor was
  invisible.

### A19 Remove A18 Probe

Change:
- Restored main-screen OAM/fade constants.
- Restored the `CONTROLLER_COMMAND_45` hide gate.
- Restored the item-icon cell/animation resource loads.
- Removed the temporary forced-Water early-return and weather animation cap.

Why:
- A18 was only a diagnostic probe and failed.

Verification:
- Source was patched back to the non-debug display path.

Result:
- Passed as cleanup. No gameplay verification was needed because this restored
  the pre-A18 logic.

### A20 Forced-Water Probe From Battle-Input Lifecycle

Change:
- Temporarily added a separate forced Water icon actor in
  `src/battle/battle_input.c` using `Sub_PokeIconResourceLoad` and
  `LoadMegaIcon`.
- Used independent resource tags so the probe did not collide with the main
  type-display actor.

Why this is not a duplicate:
- A15 proved the normal update path runs and creates an actor, but that actor is
  invisible.
- This attempt creates a separate forced Water icon from
  `Sub_PokeIconResourceLoad` / `LoadMegaIcon`, the same lifecycle that existing
  Mega/weather command-menu icons use.

Verification:
- Serial targeted ROM packaging succeeded.
- Headless `--sav test.sav` rival route reached the command menu:
  `documentation/verification_screenshots/enemy_type_hud_debug_lifecycle_forced_water.png`.
- Additional run tried one more A press toward the Fight screen:
  `documentation/verification_screenshots/enemy_type_hud_debug_lifecycle_fight_forced_water.png`.
- Memory read of `sEnemyTypeLifecycleProbeOAM` at `0x023D402C` reported
  `0x023250F8`, proving the lifecycle probe actor was created.

Result:
- Failed. The lifecycle-created actor was non-null but still invisible. This
  suggests the issue is not limited to `BattleContext_Main` timing.

### A21 Built-In Mega Icon Probe From Battle-Input Lifecycle

Change:
- Removed before completion in favor of the requested BG/tilemap prototype.
- Reuse the A20 battle-input lifecycle probe, but swap only the probe
  char/palette resources from `TYPE_ICON_WATER_GFX` to the known built-in
  `MEGA_ICON_FIGHT_GFX`.

Why this is not a duplicate:
- A20 proved a lifecycle-created actor using the new Water type icon asset is
  non-null but invisible.
- This attempt changes only the graphic/palette pair to an existing battle
  icon that is already used by `LoadMegaIcon`, separating "new type asset
  format/indexing" from "the probe actor path is invisible for any graphic".

Verification:
- Not run. The probe and all of its temporary OAM resources were removed.

Result:
- Superseded.

### A22 Command-Select BG Tilemap Markers

Change:
- Replaced the free-floating enemy type OAM actors with one 32x144, 4-bit
  marker atlas containing four 8x8 tiles for each standard type.
- Reused the existing LoadMegaOam hook inside BGCallback_CommandSelect to call
  BattleSystem_UpdateEnemyTypeMarkers.
- Loaded the atlas into reserved main BG0 character tiles and stamped one or
  two marker rows with LoadRectToBgTilemapRect, followed by
  ScheduleBgTilemapBufferTransfer.
- Removed the lifecycle probe and the broad per-frame battle-context call.

Why this is not a duplicate:
- All previous display attempts used OAM actors. This uses the battle
  background character/tilemap path and is tied to the proven command-select
  BG lifecycle.

Verification:
- The generated atlas is a valid 32x144 indexed PNG with 16 palette entries.
- ARM-target Clang syntax checking passed for all three changed battle C files;
  only pre-existing libc declaration warnings were emitted.
- A full Docker build could not start because this worktree has no rom.nds;
  the Makefile stopped at its ROM-code check before compilation.

Result:
- Static verification passed. In-game placement remains unverified.

### A23 Standard Controller Lifecycle Gate

Change:
- Moved one-time atlas preparation out of the Mega button hook and into the
  common `BattleContext_Main` update, gated until command-selection input.
- Added owner/reset state so later battles cannot inherit stale marker state.

Why this is not a duplicate:
- A22 depended on a Mega UI assembly hook. This uses the controller function
  that the built ROM disassembly proved calls the marker updater every frame.

Verification:
- Full Docker ROM build passed.
- The opt-in `test.sav` route reached the rival command screen after holding
  Right and tapping A 75 times.
- No marker appeared in `enemy_type_hud_fixed_command.png`.

Result:
- Lifecycle was fixed, but rendering still failed.

### A24 BG0 VRAM Inspection

Change:
- No product-code change. Read main BG registers, character VRAM, tilemap
  VRAM, and palette VRAM after reaching the command screen.

Why this is not a duplicate:
- Earlier memory probes inspected OAM actors. This directly inspected the new
  BG implementation and separated loading from tilemap placement.

Verification:
- BG0 used character base 0 and screen base `0xF000`.
- Atlas character bytes were present at `0x06007000`.
- Intended tilemap cells at `0x0600F11C` remained zero.
- The upstream `bg_window.c` implementation confirmed
  `LoadRectToBgTilemapRect` silently returns when a BG has no tilemap buffer;
  battle BG0 has no such buffer.

Result:
- Root cause identified: buffered tilemap helpers cannot modify this battle
  layer.

### A25 Forced-Water Restamp Probe

Change:
- Temporarily forced a Water marker at preparation, then on every controller
  update, to test whether the stock renderer merely cleared a one-time write.

Why this is not a duplicate:
- A15 and A20 forced OAM actors. This forced the new BG tilemap representation
  after its lifecycle was proven.

Verification:
- Full incremental builds passed for both variants.
- Neither `enemy_type_hud_forced_water.png` nor
  `enemy_type_hud_restamped.png` displayed a marker.

Result:
- Failed as expected from A24; both temporary probes were removed.

### A26 Direct BG0 Screen-Range Upload

Change:
- Exported the stock `BgCopyOrUncompressTilemapBufferRangeToVram` symbol and
  used it to upload only each marker's four tile entries, preserving all
  surrounding screen data.

Why this is not a duplicate:
- A22-A25 used the unavailable CPU tilemap buffer. This is the first direct,
  bounded screen-VRAM update.

Verification:
- VRAM contained `C3AC C3AD C3AE C3AF` at the intended Water-marker cells.
- The marker remained invisible on BG0.

Result:
- Tilemap upload succeeded; palette placement and layer ordering remained.

### A27 Palette Offset Correction

Change:
- Corrected palette destination units from bytes (`12 * 0x20`) to colors
  (`12 * 16`).

Why this is not a duplicate:
- Earlier asset tests checked palette content and OAM loading. This corrects
  the BG palette manager's destination-unit mismatch discovered through VRAM.

Verification:
- Palette bank 12 changed from untouched repeated values to the atlas's 16
  expected BGR555 colors.
- BG0 still did not show the marker.

Result:
- Palette loading fixed; higher-priority BG1 still masked BG0.

### A28 Direct BG1 Type Markers

Change:
- Moved the atlas and bounded screen-range writes from BG0 to higher-priority
  BG1. Kept the 32x8 marker at tile `(14, 4)`, with a second type at `(14, 5)`.

Why this is not a duplicate:
- A26 proved the same direct write on BG0 but also proved that layer was
  occluded. This changes only the battle layer to test ordering.

Verification:
- Full Docker ROM build passed.
- `enemy_type_hud_bg1.png` visibly showed `WAT` beside Totodile's gauge.
- It also revealed an unwanted `NUL` marker from the `TYPE_TYPELESS` third
  slot.

Result:
- First successful in-game rendering; one data filter remained.

### A29 Typeless Filter And Persistent Visual Check

Change:
- Excluded `TYPE_TYPELESS` from ordinary displayed types while retaining
  `TYPE_STELLAR` for a Stellar tera type.
- Kept direct four-entry restamps so battle effects cannot clear a marker
  without the next controller update restoring it.

Why this is not a duplicate:
- Type lookup was not changed speculatively: A28's successful screenshot
  specifically demonstrated the typeless sentinel as the remaining defect.

Verification:
- Generator freshness check and `git diff --check` passed.
- Full Docker ROM build passed.
- Opt-in raw-save test used `--sav test.sav`, held Right for 180 frames, and
  tapped A 90 times with checkpoints.
- `enemy_type_hud_final_a75.png` shows one Water marker at command selection.
- `enemy_type_hud_final_a80.png`, `_a85.png`, and `_a90.png` show it remains
  visible while the turn begins and Fell Stinger animates.

Result:
- Passed. The single-type rival displays one compact marker; the adjacent
  row remains transparent and available for a true second type.

### A30 Unmodified-ROM Resource Ownership Audit

Change:
- Compared BG1 character VRAM, marker tilemap cells, and palette bank 12 on an
  unmodified ROM using the identical opt-in `test.sav` rival route.
- Rejected an initially selected physical range at `0x4C0` after review noted
  text-BG map entries can address only tiles `0x000-0x3FF`.
- Moved the atlas from tiles `0x380-0x3CF` to legal tiles `0x130-0x17F`.

Why this is not a duplicate:
- Earlier checks proved file indexing and runtime rendering. This is the first
  direct before-feature ownership check against the same battle states.

Verification:
- The old range contained 680 nonzero bytes and was rejected.
- A full legal-range audit found tiles `0x130-0x1CF` all zero at both command
  selection and Fell Stinger; the selected subset is `0x130-0x17F`.
- The two intended tilemap rows and palette bank 12 were zero before the
  feature.

Result:
- Passed. The final range is based on observed unused stock resources rather
  than the initial unverified reservation.

### A31 Scripted Double-Battle Visual Harness

Change:
- Temporarily added an `AUTO_TEST=Y` double battle with Bulbasaur and
  Charizard as dual-type enemy slots 1 and 2.

Why this is not a duplicate:
- The required rival save verifies a single monotype enemy. This attempted to
  exercise both vertical rows and both enemy slots through the repo's native
  scripted battle harness.

Verification:
- `build_tests.py enemy_type_hud_visual` selected the temporary scenario.
- The debug ROM failed to link because the existing fixed `rom` region
  overflowed by 2,752 bytes when `DEBUG_BATTLE_SCENARIOS` was enabled.

Result:
- Blocked before runtime by test-harness code size. The temporary scenario was
  removed and is not part of the product diff.

### A32 Forced Secondary-Type Row Probe

Change:
- Temporarily appended Fire after Totodile's real Water type in the normal ROM
  to exercise the second marker row without the oversized debug harness.

Why this is not a duplicate:
- A28 exposed and removed a false `TYPE_TYPELESS` second row. This probe uses a
  valid second type after the final BG1 path and legal tile range were chosen.

Verification:
- Normal Docker ROM build passed.
- The opt-in rival route produced
  `enemy_type_hud_dual_row_probe.png`, visibly showing `WAT` over `FIR` in the
  two requested rows.

Result:
- Passed. The forced Fire line was removed before the final product build.

### A33 Limit Markers To The Verified Primary Enemy Gauge

Change:
- Removed the unverified enemy-2 rows from the product implementation.
- Retained one or two vertically stacked types for `BATTLER_ENEMY`, including
  in double battles.

Why this is not a duplicate:
- A31 tried and could not launch a real double battle. Review then identified
  enemy-2 placement and clearing as the only remaining unverified behavior.
  This removes those writes instead of claiming unsupported coverage.

Verification:
- The requested mockup and all successful runtime captures target the primary
  enemy gauge at tiles `(14,4)` and `(14,5)`.
- A32 separately verified both rows at that gauge.
- The final normal Docker build passed with generated-atlas validation included
  in `all`.
- `enemy_type_hud_primary_final.png` shows the shipped monotype behavior after
  all temporary probes were removed.

Result:
- The final scope is the smallest fully evidenced implementation: the primary
  enemy Pokemon's one or two types, without modifying a second HUD region.

### A34 Final Isolated Feature-Worktree Verification

Change:
- Cherry-picked the two reviewed implementation commits into the requested
  `feature/battle-type-hud-v2` worktree and rebuilt there from scratch.

Why this is not a duplicate:
- All earlier builds used the BG prototype worktree. This verifies the exact
  branch and worktree delivered to the user after integration.

Verification:
- The normal Docker build passed, including the atlas freshness check wired
  into `all`, and produced `test.nds`.
- The explicit `--sav test.sav` flow held Right for 180 frames and tapped A 75
  times to reach the rival command screen.
- `enemy_type_hud_feature_worktree_final.png` shows the final `WAT` marker
  beside Totodile's status gauge.

Result:
- Passed. The delivered feature branch reproduces the reviewed visual result.

### A35 Overlay Markers On The Enemy Status Panel

Change:
- Shifted both marker anchors from tiles `(14,4)/(14,5)` to
  `(13,3)/(13,4)`, moving them eight pixels left and eight pixels up.
- Temporarily added Fire as a secondary type to inspect both rows, then removed
  the probe before the final build.

Why this is not a duplicate:
- Earlier probes verified rendering and stacking beside the panel. This tests
  the user's follow-up placement request: overlap the slanted status-panel tip.

Verification:
- Normal Docker builds passed for the real monotype and temporary dual-row
  variants.
- Against the untouched base ROM, BG1 rows `(13-16,3)` and `(13-16,4)` each
  read as eight zero bytes at both command selection and Fell Stinger, proving
  the new cells are blank before the feature draws or clears them.
- The explicit `--sav test.sav` rival route produced
  `enemy_type_hud_over_panel.png` with the real Water marker.
- `enemy_type_hud_over_panel_dual_probe.png` shows Water and Fire stacked over
  the panel edge at the new anchors.

Result:
- Passed. The temporary Fire probe was removed; only the coordinate change
  remains in the product diff.

## Duplicate-Check Notes

- Do not retry OAM positioning/resource tags without new evidence; A1-A21
  exhausted that path.
- Do not use buffered tilemap helpers on battle BG0/BG1; A24 proved those
  layers have no CPU tilemap buffer.
- Direct screen-range uploads are the working bounded tilemap path.
- Do not reuse BG1 tiles `0x380-0x3CF`; the unmodified battle populated them.
- Do not display `TYPE_TYPELESS`; it is the empty third-type sentinel.
- Do not make `test.sav` the verifier default. Raw save import remains opt-in
  through the explicit `--sav test.sav` argument.
